from __future__ import annotations

import json
import logging
import re
import threading
import time
import unicodedata
from abc import ABC, abstractmethod
from collections import Counter, deque
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

import httpx
from fastapi import status
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import BaseModel, Field, ValidationError

from backend.src.core.config import (
    get_ai_provider,
    get_gemini_api_key,
    get_gemini_model,
    get_gemini_timeout_seconds,
)
from backend.src.core.constants import canonical_zone_key
from backend.src.models.exercise import Exercise
from backend.src.models.health_questionnaire import HealthQuestionnaire
from backend.src.models.protected_zone import ProtectedZone
from backend.src.models.routine_template import RoutineTemplate
from backend.src.models.student_profile import StudentProfile

logger = logging.getLogger(__name__)

# Orden de intensidades de menor a mayor exigencia
INTENSITY_ORDER = ["BAJA", "MEDIA", "ALTA", "EXIGENTE"]
VALID_EXERCISE_ACTIONS = {"KEEP", "REPLACE", "REMOVE"}

# Límites cuantitativos del dominio para validación de propuestas de IA (Spec 005 / Spec 006)
DURATION_MIN_WEEKS = 1
DURATION_MAX_WEEKS = 52
DAYS_MIN = 1
DAYS_MAX = 7
BLOCKS_MIN = 1
BLOCKS_MAX = 10
EXERCISES_PER_BLOCK_MIN = 1
EXERCISES_PER_BLOCK_MAX = 30
SETS_MIN = 1
SETS_MAX = 20
REST_MIN_SECONDS = 0
REST_MAX_SECONDS = 600
REPS_MAX_LENGTH = 50
REPS_MIN_VALUE = 1
REPS_MAX_VALUE = 99
ADAPTATION_NOTE_MAX_LENGTH = 500

# Códigos de error de dominio (RFC 7807)
ERROR_NO_SAFE_EXERCISES = "NO_SAFE_EXERCISES_AVAILABLE"
ERROR_NO_COMPATIBLE_SUBSTITUTES = "NO_COMPATIBLE_SUBSTITUTES"
ERROR_EMPTY_ROUTINE = "EMPTY_ROUTINE_GENERATED"
ERROR_INVALID_STRUCTURE = "INVALID_ROUTINE_STRUCTURE"
ERROR_ROUTINE_LIMIT_EXCEEDED = "ROUTINE_LIMIT_EXCEEDED"

# Clasificación explícita de errores corregibles vs no corregibles para la política de reintentos de Gemini
RETRYABLE_GEMINI_ERROR_CODES: frozenset[str] = frozenset(
    {
        "GEMINI_INVALID_JSON",
        "INVALID_ROUTINE_STRUCTURE",
        "GEMINI_INCOMPLETE_DAYS",
        "GEMINI_INCOMPLETE_BLOCKS",
        "GEMINI_INCOMPLETE_DECISIONS",
        "GEMINI_INVALID_EXERCISE",
        "GEMINI_INVALID_ACTION",
        "GEMINI_INVALID_SUBSTITUTE",
        "GEMINI_DUPLICATE_DECISION",
        "GEMINI_DUPLICATE_EXERCISE",
        "GEMINI_DOMAIN_RESTRICTION_VIOLATION",
        "GEMINI_OUT_OF_RANGE",
        "ROUTINE_LIMIT_EXCEEDED",
        "EMPTY_ROUTINE_GENERATED",
    }
)

NON_RETRYABLE_GEMINI_ERROR_CODES: frozenset[str] = frozenset(
    {
        ERROR_NO_SAFE_EXERCISES,
        ERROR_NO_COMPATIBLE_SUBSTITUTES,
        "GEMINI_QUOTA_EXCEEDED",
        "GEMINI_AUTH_ERROR",
        "GEMINI_NOT_CONFIGURED",
        "GEMINI_MODEL_NOT_CONFIGURED",
        "GEMINI_TIMEOUT",
        "GEMINI_SERVICE_UNAVAILABLE",
        "GEMINI_CONNECTION_ERROR",
        "GEMINI_API_ERROR",
    }
)

IntensityLiteral = Literal["BAJA", "MEDIA", "ALTA", "EXIGENTE"]
ExerciseActionLiteral = Literal["KEEP", "REPLACE", "REMOVE"]

# Patrón semántico para repeticiones deportivas válidas:
# Acepta entero positivo (ej. "10") o rango "min-max" (ej. "8-12"), seguido opcionalmente
# de sufijos cortos de modalidad ("c/l", "por lado", "s", "seg", "min", "reps", "m").
_REPS_FORMAT_PATTERN = re.compile(
    r"^(\d{1,3})(?:\s*-\s*(\d{1,3}))?(?:\s*(?:c/l|por lado|s|seg|min|reps?|m))?$",
    re.IGNORECASE,
)


def normalize_exercise_name(name: str | None) -> str:
    """Normaliza el nombre de un ejercicio quitando tildes, espacios y puntuación."""
    if not name:
        return ""
    decomposed = unicodedata.normalize("NFKD", name.strip().lower())
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", without_accents)


def _strip_accents_lower(text: str | None) -> str:
    if not text or not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _requires_no_materials(template: Any) -> bool:
    return getattr(template, "has_no_materials_alternative", False) is True


def _exercise_has_no_materials(exercise: Any) -> bool:
    return getattr(exercise, "has_no_materials_alternative", False) is True


def _template_duration_weeks(template: Any) -> int:
    raw = getattr(template, "duration_weeks", 4)
    return raw if isinstance(raw, int) and not isinstance(raw, bool) else 4


def _safe_float_weight(raw_wt: Any) -> float | None:
    if raw_wt is None or isinstance(raw_wt, bool):
        return None
    if isinstance(raw_wt, (int, float)):
        return float(raw_wt)
    try:
        return float(str(raw_wt))
    except (ValueError, TypeError):
        return None


def _safe_int_or_none(raw_val: Any) -> int | None:
    return raw_val if isinstance(raw_val, int) and not isinstance(raw_val, bool) else None


def _obj_name(obj: Any, default: str = "") -> str:
    val = getattr(obj, "name", None)
    if isinstance(val, str):
        return val
    mock_name = getattr(obj, "_mock_name", None)
    if isinstance(mock_name, str) and mock_name:
        return mock_name
    return default


@dataclass(frozen=True)
class ExerciseBiomechanics:
    """Metadatos funcionales y biomecánicos derivados determinísticamente de Exercise."""

    canonical_muscle_group: str
    functional_region: str
    movement_pattern: str
    equipment_type: str
    category: str
    has_no_materials_alternative: bool


def infer_exercise_biomechanics(exercise: Exercise) -> ExerciseBiomechanics:
    """Infiere el patrón de movimiento, grupo muscular canónico y región funcional de un ejercicio.

    No duplica columnas en la base de datos: utiliza como única fuente de verdad los atributos
    existentes de `Exercise` (`target_muscle_group`, `category`, `name`, `description`,
    `equipment_needed`, `has_no_materials_alternative`).
    """
    raw_muscle = _strip_accents_lower(getattr(exercise, "target_muscle_group", "") or "")
    raw_name = _strip_accents_lower(getattr(exercise, "name", "") or "")
    raw_desc = _strip_accents_lower(getattr(exercise, "description", "") or "")
    raw_equip = _strip_accents_lower(getattr(exercise, "equipment_needed", "") or "")
    category = (getattr(exercise, "category", "FUERZA") or "FUERZA").strip().upper()
    has_no_mat = bool(getattr(exercise, "has_no_materials_alternative", False))
    combined_text = f"{raw_name} {raw_muscle} {raw_desc}"

    # 1. Clasificación de equipamiento requerido
    if any(k in raw_equip for k in ("ninguno", "peso corporal", "sin material", "colchoneta", "suelo")):
        equipment_type = "BODYWEIGHT_NO_MATERIALS"
    elif any(k in raw_equip for k in ("barra", "rack")):
        equipment_type = "BARBELL"
    elif "mancuerna" in raw_equip:
        equipment_type = "DUMBBELL"
    elif any(k in raw_equip for k in ("kettlebell", "pesa rusa")):
        equipment_type = "KETTLEBELL"
    elif any(k in raw_equip for k in ("banda", "elastica", "elastico", "trx", "suspension")):
        equipment_type = "BAND"
    elif any(k in raw_equip for k in ("maquina", "polea", "prensa", "cinta", "ergometro", "bici", "camilla")):
        equipment_type = "MACHINE_CABLE"
    else:
        equipment_type = "OTHER_EQUIPMENT"

    # 2. Grupo muscular canónico
    if any(k in raw_muscle for k in ("cuadricep", "muslo anterior")):
        canonical_muscle = "cuadriceps"
    elif any(k in raw_muscle for k in ("isquio", "femoral")):
        canonical_muscle = "isquiotibiales"
    elif any(k in raw_muscle for k in ("gluteo", "cadera", "abductor", "aductor")):
        canonical_muscle = "gluteos"
    elif "cadena posterior" in raw_muscle:
        canonical_muscle = "cadena_posterior"
    elif any(k in raw_muscle for k in ("pierna", "tren inferior", "miembro inferior", "gemelo", "pantorrilla", "soleo")):
        canonical_muscle = "piernas"
    elif any(k in raw_muscle for k in ("pectoral", "pecho")):
        canonical_muscle = "pectoral"
    elif any(k in raw_muscle for k in ("dorsal", "espalda", "trapecio", "romboide")):
        canonical_muscle = "dorsales"
    elif any(k in raw_muscle for k in ("hombro", "deltoid")):
        canonical_muscle = "hombros"
    elif any(k in raw_muscle for k in ("brazo", "bicep", "tricep", "antebrazo")):
        canonical_muscle = "brazos"
    elif any(k in raw_muscle for k in ("core", "abdom", "zona media", "oblicuo", "lumbar")):
        canonical_muscle = "core"
    elif any(k in raw_muscle for k in ("cardio", "aerob", "circulatorio", "respiratorio")):
        canonical_muscle = "cardiovascular"
    elif any(k in raw_muscle for k in ("cuerpo completo", "full body", "global", "general")):
        canonical_muscle = "cuerpo_completo"
    else:
        canonical_muscle = raw_muscle or "general"

    # 3. Patrón de movimiento y región funcional
    # 3.a. Cardio / Locomoción
    if category == "CARDIO" or canonical_muscle == "cardiovascular" or any(
        k in combined_text
        for k in ("caminata", "cinta", "trote", "correr", "bicicleta", "eliptico", "ergometro", "burpee", "saltos de soga", "jumping jack")
    ):
        return ExerciseBiomechanics(
            canonical_muscle_group=canonical_muscle,
            functional_region="CARDIO_METABOLIC",
            movement_pattern="LOCOMOTION_CARDIO",
            equipment_type=equipment_type,
            category=category,
            has_no_materials_alternative=has_no_mat,
        )

    # 3.b. Levantamientos olímpicos / balísticos de cuerpo completo
    if any(k in raw_name for k in ("snatch", "arranque", "power clean", "clean", "cargada", "envion", "thruster")):
        return ExerciseBiomechanics(
            canonical_muscle_group=canonical_muscle,
            functional_region="FULL_BODY_POWER",
            movement_pattern="OLYMPIC_BALLISTIC",
            equipment_type=equipment_type,
            category=category,
            has_no_materials_alternative=has_no_mat,
        )

    # 3.c. Core / Estabilidad de zona media
    if canonical_muscle == "core" or any(
        k in raw_name
        for k in ("plancha", "plank", "pallof", "dead bug", "bird dog", "crunch", "abdominal", "rueda abdominal", "ab wheel", "hollow")
    ):
        return ExerciseBiomechanics(
            canonical_muscle_group="core",
            functional_region="CORE",
            movement_pattern="CORE_STABILITY",
            equipment_type=equipment_type,
            category=category,
            has_no_materials_alternative=has_no_mat,
        )

    # 3.d. Tren Inferior: Dominancia de Rodilla vs Dominancia de Cadera
    if canonical_muscle in ("cuadriceps", "isquiotibiales", "gluteos", "cadena_posterior", "piernas") or any(
        k in raw_name
        for k in (
            "sentadilla",
            "squat",
            "prensa",
            "estocada",
            "zancada",
            "bulgara",
            "step-up",
            "step up",
            "extension de cuadriceps",
            "peso muerto",
            "deadlift",
            "hip thrust",
            "puente de gluteo",
            "swing",
            "buenos dias",
            "curl femoral",
            "camilla femoral",
            "elevacion de talones",
            "gemelos",
        )
    ):
        is_hip_dominant = any(
            k in combined_text
            for k in (
                "peso muerto",
                "deadlift",
                "rumano",
                "hip thrust",
                "puente de gluteo",
                "glute bridge",
                "swing",
                "buenos dias",
                "good morning",
                "bisagra de cadera",
                "curl femoral",
                "camilla femoral",
                "isquiotibial",
                "abduccion de cadera",
            )
        ) or (
            canonical_muscle in ("isquiotibiales", "gluteos", "cadena_posterior")
            and not any(k in raw_name for k in ("sentadilla", "prensa", "estocada", "zancada", "step"))
        )
        pattern = "HIP_DOMINANT" if is_hip_dominant else "KNEE_DOMINANT"
        return ExerciseBiomechanics(
            canonical_muscle_group=canonical_muscle,
            functional_region="LOWER_BODY",
            movement_pattern=pattern,
            equipment_type=equipment_type,
            category=category,
            has_no_materials_alternative=has_no_mat,
        )

    # 3.e. Aislamiento de Brazos (Bíceps / Tríceps)
    if canonical_muscle == "brazos" or any(
        k in raw_name for k in ("curl", "biceps", "triceps", "extension de triceps", "press frances", "martillo", "predicador")
    ):
        return ExerciseBiomechanics(
            canonical_muscle_group="brazos",
            functional_region="ARM_ISOLATION",
            movement_pattern="ARM_ISOLATION",
            equipment_type=equipment_type,
            category=category,
            has_no_materials_alternative=has_no_mat,
        )

    # 3.f. Tren Superior — Tracción (Horizontal vs Vertical)
    if canonical_muscle == "dorsales" or any(
        k in raw_name for k in ("remo", "dominada", "pull-up", "jalon", "polea al pecho", "lat pulldown", "face pull", "pullover")
    ):
        is_vertical_pull = any(
            k in combined_text for k in ("dominada", "pull-up", "chin-up", "jalon", "polea al pecho", "lat pulldown", "traccion vertical")
        )
        pattern = "VERTICAL_PULL" if is_vertical_pull else "HORIZONTAL_PULL"
        return ExerciseBiomechanics(
            canonical_muscle_group="dorsales" if canonical_muscle not in ("dorsales", "hombros") else canonical_muscle,
            functional_region="UPPER_PULL",
            movement_pattern=pattern,
            equipment_type=equipment_type,
            category=category,
            has_no_materials_alternative=has_no_mat,
        )

    # 3.g. Tren Superior — Empuje (Horizontal vs Vertical)
    if canonical_muscle in ("pectoral", "hombros") or any(
        k in raw_name
        for k in (
            "press",
            "flexiones",
            "push-up",
            "push up",
            "apertura",
            "cruces",
            "fondos",
            "vuelos",
            "elevaciones laterales",
            "elevaciones frontales",
        )
    ):
        is_vertical_push = (
            any(
                k in combined_text
                for k in (
                    "press militar",
                    "press de hombro",
                    "press hombro",
                    "press arnold",
                    "empuje vertical",
                    "press vertical",
                    "vuelos laterales",
                    "elevaciones laterales",
                    "elevaciones frontales",
                    "pike push",
                )
            )
            or (
                canonical_muscle == "hombros"
                and not any(k in combined_text for k in ("banca", "plano", "inclinado", "declinado", "empuje horizontal", "pecho", "pectoral"))
            )
        )
        pattern = "VERTICAL_PUSH" if is_vertical_push else "HORIZONTAL_PUSH"
        return ExerciseBiomechanics(
            canonical_muscle_group=canonical_muscle,
            functional_region="UPPER_PUSH",
            movement_pattern=pattern,
            equipment_type=equipment_type,
            category=category,
            has_no_materials_alternative=has_no_mat,
        )

    # 3.h. Movilidad / Flexibilidad / Equilibrio puro
    if category in ("MOVILIDAD", "FLEXIBILIDAD", "EQUILIBRIO"):
        return ExerciseBiomechanics(
            canonical_muscle_group=canonical_muscle,
            functional_region="MOVILIDAD_FLEXIBILIDAD",
            movement_pattern="MOBILITY_FLOW",
            equipment_type=equipment_type,
            category=category,
            has_no_materials_alternative=has_no_mat,
        )

    return ExerciseBiomechanics(
        canonical_muscle_group=canonical_muscle,
        functional_region=f"CUSTOM_{canonical_muscle.upper()}",
        movement_pattern="GENERAL_STRENGTH",
        equipment_type=equipment_type,
        category=category,
        has_no_materials_alternative=has_no_mat,
    )


def _are_categories_compatible(orig_cat: str, cand_cat: str) -> bool:
    """Determina si dos categorías de ejercicio pueden sustituirse manteniendo coherencia funcional."""
    if orig_cat == cand_cat:
        return True
    # Un ejercicio de FUERZA puede adaptarse a una variante de MOVILIDAD/EQUILIBRIO del mismo grupo muscular
    # cuando existe una restricción articular, pero nunca por CARDIO puro ni viceversa.
    compatible_pairs = {
        ("FUERZA", "MOVILIDAD"),
        ("FUERZA", "EQUILIBRIO"),
        ("MOVILIDAD", "FLEXIBILIDAD"),
        ("FLEXIBILIDAD", "MOVILIDAD"),
        ("MOVILIDAD", "EQUILIBRIO"),
        ("EQUILIBRIO", "MOVILIDAD"),
    }
    return (orig_cat, cand_cat) in compatible_pairs


def evaluate_functional_equivalence(
    orig_exercise: Exercise,
    candidate: Exercise,
) -> tuple[bool, int, list[str]]:
    """Evalúa si un ejercicio candidato es funcionalmente equivalente al ejercicio original.

    Retorna `(es_compatible, nivel_prioridad, criterios_cumplidos)`.
    Niveles de prioridad (menor valor = mayor compatibilidad):
    - 1: Mismo patrón de movimiento + mismo grupo muscular + misma categoría.
    - 2: Mismo patrón de movimiento + misma región funcional + misma categoría.
    - 3: Mismo grupo muscular + misma categoría (dentro de la misma región funcional).
    - 4: Mismo grupo muscular + categoría compatible (ej. FUERZA -> MOVILIDAD del mismo grupo).
    - 5: Misma cadena biomecánica/región funcional + misma categoría (ej. empuje vertical -> horizontal para proteger hombro, o dominancia de rodilla -> cadera en tren inferior para proteger rodilla).
    - 6: Misma cadena biomecánica/región funcional + categoría compatible.
    - 99 (False): Funcionalmente incompatible (ej. Sentadilla -> Plancha, Sentadilla -> Press Banca, Remo -> Sentadilla).
    """
    orig_bio = infer_exercise_biomechanics(orig_exercise)
    cand_bio = infer_exercise_biomechanics(candidate)

    same_pattern = orig_bio.movement_pattern == cand_bio.movement_pattern
    same_muscle = orig_bio.canonical_muscle_group == cand_bio.canonical_muscle_group
    same_region = orig_bio.functional_region == cand_bio.functional_region
    same_category = orig_bio.category == cand_bio.category
    compat_category = _are_categories_compatible(orig_bio.category, cand_bio.category)

    # Caso especial: levantamientos olímpicos / potencia de cuerpo completo pueden sustituirse
    # por dominancia de cadera, dominancia de rodilla o acondicionamiento metabólico de potencia.
    if orig_bio.functional_region == "FULL_BODY_POWER":
        if cand_bio.functional_region in ("FULL_BODY_POWER", "LOWER_BODY", "CARDIO_METABOLIC"):
            criteria = [
                f"power_chain_adaptation:{orig_bio.movement_pattern}->{cand_bio.movement_pattern}",
                f"category:{orig_bio.category}->{cand_bio.category}",
            ]
            priority = 2 if same_pattern and same_category else 5
            return True, priority, criteria
        return False, 99, [f"incompatible_region:{orig_bio.functional_region}->{cand_bio.functional_region}"]

    # Regla estricta: prohibido cruzar regiones biomecánicas inconexas
    # (ej. LOWER_BODY <-> CORE, LOWER_BODY <-> UPPER_PUSH, UPPER_PUSH <-> UPPER_PULL, etc.)
    if not same_region and not same_muscle:
        return (
            False,
            99,
            [
                f"incompatible_region:{orig_bio.functional_region}->{cand_bio.functional_region}",
                f"incompatible_pattern:{orig_bio.movement_pattern}->{cand_bio.movement_pattern}",
            ],
        )

    if not compat_category:
        return (
            False,
            99,
            [f"incompatible_category:{orig_bio.category}->{cand_bio.category}"],
        )

    criteria: list[str] = []
    if same_pattern:
        criteria.append(f"same_movement_pattern:{cand_bio.movement_pattern}")
    else:
        criteria.append(f"compatible_chain_pattern:{orig_bio.movement_pattern}->{cand_bio.movement_pattern}")

    if same_muscle:
        criteria.append(f"same_muscle_group:{cand_bio.canonical_muscle_group}")
    else:
        criteria.append(f"synergistic_region:{cand_bio.functional_region}")

    if same_category:
        criteria.append(f"same_category:{cand_bio.category}")
    else:
        criteria.append(f"compatible_category:{orig_bio.category}->{cand_bio.category}")

    if orig_bio.equipment_type == cand_bio.equipment_type:
        criteria.append(f"same_equipment_type:{cand_bio.equipment_type}")
    else:
        criteria.append(f"alternative_equipment:{orig_bio.equipment_type}->{cand_bio.equipment_type}")

    if same_pattern and same_muscle and same_category:
        return True, 1, criteria
    if same_pattern and same_region and same_category:
        return True, 2, criteria
    if same_muscle and same_category:
        return True, 3, criteria
    if same_muscle and compat_category:
        return True, 4, criteria
    if same_region and same_category:
        return True, 5, criteria
    return True, 6, criteria


def find_compatible_substitutes(
    orig_exercise: Exercise,
    protected_zones: list[ProtectedZone | str],
    catalog: list[Exercise],
    exclude_ids: set[str] | None = None,
    require_no_materials: bool = False,
) -> list[tuple[Exercise, int, list[str]]]:
    """Devuelve todos los candidatos seguros y funcionalmente compatibles ordenados de forma determinista."""
    excluded = set(exclude_ids or set())
    excluded.add(orig_exercise.id)
    orig_norm_name = normalize_exercise_name(orig_exercise.name)
    orig_bio = infer_exercise_biomechanics(orig_exercise)

    compatible: list[tuple[int, int, int, Exercise, list[str]]] = []
    for idx, cand in enumerate(catalog):
        if cand.deleted_at is not None:
            continue
        if cand.id in excluded:
            continue
        if normalize_exercise_name(cand.name) == orig_norm_name:
            continue
        if require_no_materials and not getattr(cand, "has_no_materials_alternative", False):
            continue
        if _conflicts_with_zones(cand, protected_zones) is not None:
            continue

        is_compat, priority_tier, criteria = evaluate_functional_equivalence(orig_exercise, cand)
        if not is_compat:
            continue

        cand_bio = infer_exercise_biomechanics(cand)
        # Preferir igual tipo de equipamiento o alternativa sin materiales cuando empatan en prioridad biomecánica
        equip_Penalty = 0 if cand_bio.equipment_type == orig_bio.equipment_type else 1
        full_criteria = ["safety_zones_verified", *criteria]
        if require_no_materials:
            full_criteria.append("no_materials_verified")
        compatible.append((priority_tier, equip_Penalty, idx, cand, full_criteria))

    compatible.sort(key=lambda item: (item[0], item[1], item[2], normalize_exercise_name(item[3].name), item[3].id))
    return [(item[3], item[0], item[4]) for item in compatible]


def find_safe_substitute(
    orig_exercise: Exercise,
    protected_zones: list[ProtectedZone | str],
    catalog: list[Exercise],
    exclude_ids: set[str] | None = None,
    require_no_materials: bool = False,
) -> Exercise | None:
    """Selecciona un ejercicio sustituto seguro y funcionalmente coherente del catálogo del entrenador.

    Dimensiones obligatorias:
    1. Seguridad: sin conflicto con `protected_zones`, activo (`deleted_at is None`), distinto ID y nombre,
       y compatible con `require_no_materials` cuando aplica.
    2. Equivalencia funcional: conserva patrón de movimiento, grupo muscular o cadena biomecánica y categoría compatible.
       Se eliminó el fallback indiscriminado a misma categoría general o a cualquier ejercicio seguro del catálogo.
    """
    matches = find_compatible_substitutes(
        orig_exercise=orig_exercise,
        protected_zones=protected_zones,
        catalog=catalog,
        exclude_ids=exclude_ids,
        require_no_materials=require_no_materials,
    )
    if not matches:
        return None
    return matches[0][0]


def is_valid_reps_format(reps: str | None) -> bool:
    """Valida que el campo reps tenga un formato deportivo válido (ej. '10', '8-12', '12 c/l')."""
    if not isinstance(reps, str):
        return False
    cleaned = reps.strip()
    if not cleaned or len(cleaned) > REPS_MAX_LENGTH:
        return False
    match = _REPS_FORMAT_PATTERN.match(cleaned)
    if not match:
        return False
    first_val = int(match.group(1))
    if not (REPS_MIN_VALUE <= first_val <= REPS_MAX_VALUE):
        return False
    if match.group(2) is not None:
        second_val = int(match.group(2))
        if not (REPS_MIN_VALUE <= second_val <= REPS_MAX_VALUE) or second_val < first_val:
            return False
    return True


class AIRoutineAdapterError(Exception):
    """Excepción controlada de los adaptadores de IA para respuestas RFC 7807."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str = "AI_ADAPTER_ERROR",
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code
        super().__init__(detail)


@dataclass
class SubstitutionTraceEntry:
    """Registro trazable de una decisión de adaptación o sustitución de ejercicio (sin PII sensible)."""

    day_name: str
    block_name: str
    original_exercise_id: str
    original_exercise_name: str
    proposed_exercise_id: str | None
    selected_exercise_id: str | None
    selected_exercise_name: str | None
    action: str  # KEEP | REPLACE | REMOVE
    engine: str  # heuristic | gemini
    reason: str
    trigger_condition: str | None = None
    compatibility_criteria: list[str] = field(default_factory=list)


@dataclass
class AIGenerationMetrics:
    """Métricas técnicas de rendimiento y confiabilidad de una ejecución del subsistema de IA."""

    provider: str
    context_build_ms: float = 0.0
    candidate_filter_ms: float = 0.0
    gemini_latency_ms: float = 0.0
    validation_ms: float = 0.0
    total_generation_ms: float = 0.0
    available_candidates_count: int = 0
    rejected_candidates_count: int = 0
    retries_count: int = 0
    success: bool = False
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AIMetricsCollector:
    """Colector en memoria thread-safe para métricas técnicas agregadas (latencias P50/P95 y tasas de éxito/error)."""

    def __init__(self, max_samples: int = 500) -> None:
        self._lock = threading.Lock()
        self._max_samples = max_samples
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._total_requests = 0
            self._successful_requests = 0
            self._failed_requests = 0
            self._total_retries = 0
            self._errors_by_category: Counter[str] = Counter()
            self._total_latencies_ms: deque[float] = deque(maxlen=self._max_samples)
            self._gemini_latencies_ms: deque[float] = deque(maxlen=self._max_samples)
            self._last_metrics: dict[str, Any] | None = None

    @staticmethod
    def _percentile(samples: list[float], pct: float) -> float | None:
        if not samples:
            return None
        ordered = sorted(samples)
        idx = round((pct / 100.0) * (len(ordered) - 1))
        idx = max(0, min(idx, len(ordered) - 1))
        return round(ordered[idx], 2)

    def record(self, metrics: AIGenerationMetrics) -> None:
        with self._lock:
            self._total_requests += 1
            self._total_retries += metrics.retries_count
            self._total_latencies_ms.append(metrics.total_generation_ms)
            if metrics.gemini_latency_ms > 0:
                self._gemini_latencies_ms.append(metrics.gemini_latency_ms)
            if metrics.success:
                self._successful_requests += 1
            else:
                self._failed_requests += 1
                if metrics.error_code:
                    self._errors_by_category[metrics.error_code] += 1
            self._last_metrics = metrics.to_dict()

        if metrics.success:
            logger.info(
                "AI_ROUTINE_METRICS provider=%s success=true total_ms=%.2f context_ms=%.2f filter_ms=%.2f "
                "gemini_ms=%.2f validation_ms=%.2f candidates_ok=%d candidates_rejected=%d retries=%d",
                metrics.provider,
                metrics.total_generation_ms,
                metrics.context_build_ms,
                metrics.candidate_filter_ms,
                metrics.gemini_latency_ms,
                metrics.validation_ms,
                metrics.available_candidates_count,
                metrics.rejected_candidates_count,
                metrics.retries_count,
            )
        else:
            logger.warning(
                "AI_ROUTINE_METRICS provider=%s success=false error_code=%s total_ms=%.2f gemini_ms=%.2f "
                "candidates_ok=%d candidates_rejected=%d retries=%d",
                metrics.provider,
                metrics.error_code or "UNKNOWN",
                metrics.total_generation_ms,
                metrics.gemini_latency_ms,
                metrics.available_candidates_count,
                metrics.rejected_candidates_count,
                metrics.retries_count,
            )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            total = self._total_requests
            success_rate = round(self._successful_requests / total, 4) if total > 0 else 0.0
            error_rates = {
                code: round(count / total, 4) for code, count in self._errors_by_category.items()
            } if total > 0 else {}
            lat_list = list(self._total_latencies_ms)
            gem_list = list(self._gemini_latencies_ms)
            return {
                "total_requests": total,
                "successful_requests": self._successful_requests,
                "failed_requests": self._failed_requests,
                "total_retries": self._total_retries,
                "success_rate": success_rate,
                "errors_by_category": dict(self._errors_by_category),
                "error_rates_by_category": error_rates,
                "total_latency_p50_ms": self._percentile(lat_list, 50),
                "total_latency_p95_ms": self._percentile(lat_list, 95),
                "gemini_latency_p50_ms": self._percentile(gem_list, 50),
                "gemini_latency_p95_ms": self._percentile(gem_list, 95),
                "last_execution": self._last_metrics,
            }


_METRICS_COLLECTOR = AIMetricsCollector()


def get_ai_metrics_snapshot() -> dict[str, Any]:
    """Devuelve una instantánea de las métricas técnicas acumuladas del subsistema de IA."""
    return _METRICS_COLLECTOR.snapshot()


def reset_ai_metrics() -> None:
    """Reinicia las métricas acumuladas en memoria (útil para tests deterministas)."""
    _METRICS_COLLECTOR.reset()


@dataclass
class AdaptedExerciseData:
    exercise_id: str
    order_index: int
    sets: int
    reps: str
    rest_seconds: int
    adaptation_notes: str | None = None
    target_weight_kg: float | None = None


@dataclass
class AdaptedBlockData:
    name: str
    order_index: int
    exercises: list[AdaptedExerciseData] = field(default_factory=list)
    estimated_duration_minutes: int | None = None


@dataclass
class AdaptedDayData:
    name: str
    order_index: int
    blocks: list[AdaptedBlockData] = field(default_factory=list)


@dataclass
class AIRoutineProposalResult:
    name: str
    duration_weeks: int
    intensity: str
    adaptation_summary: str
    days: list[AdaptedDayData] = field(default_factory=list)
    has_no_materials_alternative: bool = False
    is_partial: bool = False
    unsubstituted_exercises: list[dict[str, str]] = field(default_factory=list)
    substitutions_trace: list[SubstitutionTraceEntry] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


class GeminiExerciseDecisionSchema(BaseModel):
    """Decisión estructurada de la IA para un ejercicio individual de la plantilla."""

    original_exercise_id: str = Field(
        description="Identificador exacto del ejercicio original en la plantilla genérica."
    )
    action: ExerciseActionLiteral = Field(
        description="Acción explícita propuesta: KEEP (conservar), REPLACE (reemplazar por otro ejercicio disponible) o REMOVE (eliminar)."
    )
    replacement_exercise_id: str | None = Field(
        default=None,
        description="Identificador del ejercicio sustituto del catálogo disponible cuando action es REPLACE; null si action es KEEP o REMOVE.",
    )
    sets: int | None = Field(
        default=None,
        description="Cantidad de series propuestas (rango permitido: 1 a 20).",
    )
    reps: str | None = Field(
        default=None,
        description="Repeticiones propuestas (ej. '8-12', '15', '5-6'; máx. 50 caracteres).",
    )
    rest_seconds: int | None = Field(
        default=None,
        description="Tiempo de descanso en segundos entre series (rango permitido: 0 a 600).",
    )
    reason: str = Field(
        description="Justificación breve en español de la modificación, sustitución o eliminación."
    )


class GeminiBlockAdaptationSchema(BaseModel):
    name: str = Field(description="Nombre del bloque de entrenamiento.")
    exercises: list[GeminiExerciseDecisionSchema] = Field(
        default_factory=list,
        description="Lista de decisiones explícitas para cada ejercicio del bloque.",
    )


class GeminiDayAdaptationSchema(BaseModel):
    name: str = Field(description="Nombre del día de entrenamiento.")
    blocks: list[GeminiBlockAdaptationSchema] = Field(
        default_factory=list,
        description="Bloques que componen el día de entrenamiento.",
    )


class GeminiRoutineAdaptationSchema(BaseModel):
    """Esquema de salida estructurada JSON esperado desde Google Gemini API."""

    intensity: IntensityLiteral = Field(
        description="Intensidad general propuesta para la rutina: BAJA, MEDIA, ALTA o EXIGENTE."
    )
    adaptation_summary: str = Field(
        description="Resumen general explicativo en español de las adaptaciones propuestas para la revisión del entrenador."
    )
    days: list[GeminiDayAdaptationSchema] = Field(
        default_factory=list,
        description="Días adaptados respetando la estructura de la rutina base.",
    )


class AIRoutineAdapter(ABC):
    """Interfaz abstracta para adaptadores de IA (Principio II de la Constitución)."""

    @abstractmethod
    def generate_adapted_routine(
        self,
        template: RoutineTemplate,
        student: StudentProfile,
        questionnaire: HealthQuestionnaire | None,
        protected_zones: list[ProtectedZone],
        trainer_exercises: list[Exercise],
    ) -> AIRoutineProposalResult:
        pass


def _conflicts_with_zones(exercise: Exercise, zones: list[ProtectedZone | str]) -> str | None:
    """Verifica si el ejercicio compromete alguna de las zonas corporales protegidas."""
    if not zones:
        return None

    def _area_str(z: ProtectedZone | str) -> str:
        return z.body_area if hasattr(z, "body_area") else str(z)

    # 1. Comparación canónica con exercise.contraindicated_zones
    student_canonical = {
        canonical_zone_key(_area_str(z)): _area_str(z)
        for z in zones
        if _area_str(z)
    }
    if exercise.contraindicated_zones:
        for cz in exercise.contraindicated_zones:
            cz_canon = canonical_zone_key(cz)
            if cz_canon and cz_canon in student_canonical:
                return student_canonical[cz_canon]

    # 2. Búsqueda por texto y palabras clave como fallback seguro
    searchable_text = f"{exercise.name} {exercise.target_muscle_group} {exercise.description}".lower()

    zone_keywords: dict[str, list[str]] = {
        "hombro": ["hombro", "deltoid", "manguito", "press militar"],
        "shoulder": ["hombro", "deltoid", "manguito", "press militar"],
        "rodilla": ["rodilla", "cuadricep", "cuádriceps", "isquio", "patel", "sentadilla", "estocada"],
        "knee": ["rodilla", "cuadricep", "cuádriceps", "isquio", "patel", "sentadilla", "estocada"],
        "lumbar": ["lumbar", "espalda baja", "peso muerto", "raquis"],
        "lower back": ["lumbar", "espalda baja", "peso muerto", "raquis"],
        "upper back": ["espalda alta", "trapecio", "romboides", "dorsal"],
        "espalda alta": ["espalda alta", "trapecio", "romboides", "dorsal"],
        "espalda": ["espalda", "dorsal", "trapecio", "lumbar"],
        "cadera": ["cadera", "glúteo", "gluteo", "pelvis", "abductor", "aductor"],
        "hip": ["cadera", "glúteo", "gluteo", "pelvis", "abductor", "aductor", "hip"],
        "codo": ["codo", "tricep", "tríceps", "bicep", "bíceps", "brazo"],
        "elbow": ["codo", "tricep", "tríceps", "bicep", "bíceps", "brazo"],
        "cuello": ["cuello", "cervical", "trapecio"],
        "neck": ["cuello", "cervical", "trapecio"],
        "tobillo": ["tobillo", "gemelo", "pantorrilla", "sóleo", "salto"],
        "ankle": ["tobillo", "gemelo", "pantorrilla", "sóleo", "salto"],
        "pecho": ["pecho", "pectoral", "press de banca"],
        "muneca": ["muñeca", "antebrazo"],
        "wrist": ["muñeca", "antebrazo"],
    }

    for zone in zones:
        area_str = _area_str(zone)
        area_lower = area_str.lower()
        if area_lower in searchable_text:
            return area_str
        for key, tokens in zone_keywords.items():
            if key in area_lower and any(token in searchable_text for token in tokens):
                return area_str
    return None


# ==============================================================================
# Validaciones separadas por categoría (Sección 3.3: A, B, C y D)
# ==============================================================================


def validate_routine_structure(proposal_result: AIRoutineProposalResult) -> None:
    """Categoría A: Validación estructural de la rutina generada."""
    if not isinstance(proposal_result, AIRoutineProposalResult):
        raise AIRoutineAdapterError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="El formato de la propuesta de rutina generada es inválido.",
            error_code=ERROR_INVALID_STRUCTURE,
        )

    if not (proposal_result.name or "").strip():
        raise AIRoutineAdapterError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="La propuesta de rutina carece de un nombre válido.",
            error_code=ERROR_INVALID_STRUCTURE,
        )

    if not (proposal_result.adaptation_summary or "").strip():
        raise AIRoutineAdapterError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="La propuesta de rutina carece de resumen de adaptación.",
            error_code=ERROR_INVALID_STRUCTURE,
        )

    if not proposal_result.days:
        raise AIRoutineAdapterError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="La propuesta de IA resultó en una rutina vacía sin días de entrenamiento.",
            error_code=ERROR_EMPTY_ROUTINE,
        )

    total_exercises = 0
    for day_idx, day in enumerate(proposal_result.days):
        if not (day.name or "").strip():
            raise AIRoutineAdapterError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"El día {day_idx + 1} de la rutina generada no tiene un nombre válido.",
                error_code=ERROR_INVALID_STRUCTURE,
            )
        if not day.blocks:
            raise AIRoutineAdapterError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"El día '{day.name}' de la rutina generada no contiene bloques de entrenamiento.",
                error_code=ERROR_INVALID_STRUCTURE,
            )
        for blk_idx, block in enumerate(day.blocks):
            if not (block.name or "").strip():
                raise AIRoutineAdapterError(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"El bloque {blk_idx + 1} del día '{day.name}' no tiene un nombre válido.",
                    error_code=ERROR_INVALID_STRUCTURE,
                )
            if not block.exercises:
                raise AIRoutineAdapterError(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"El bloque '{block.name}' del día '{day.name}' no contiene ejercicios.",
                    error_code=ERROR_INVALID_STRUCTURE,
                )
            for ex in block.exercises:
                if not (ex.exercise_id or "").strip():
                    raise AIRoutineAdapterError(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Un ejercicio en el bloque '{block.name}' carece de identificador válido.",
                        error_code=ERROR_INVALID_STRUCTURE,
                    )
                total_exercises += 1

    if total_exercises == 0:
        raise AIRoutineAdapterError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="La propuesta de IA resultó en una rutina vacía sin ejercicios.",
            error_code=ERROR_EMPTY_ROUTINE,
        )


def validate_routine_quantities(proposal_result: AIRoutineProposalResult) -> None:
    """Categoría B: Validación cuantitativa de rangos y límites del dominio."""
    if proposal_result.intensity not in INTENSITY_ORDER:
        raise AIRoutineAdapterError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"La propuesta de IA contiene una intensidad inválida ('{proposal_result.intensity}').",
            error_code=ERROR_ROUTINE_LIMIT_EXCEEDED,
        )

    if not (DURATION_MIN_WEEKS <= proposal_result.duration_weeks <= DURATION_MAX_WEEKS):
        raise AIRoutineAdapterError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"La propuesta de IA contiene una duración en semanas fuera del rango permitido "
                f"({DURATION_MIN_WEEKS} a {DURATION_MAX_WEEKS})."
            ),
            error_code=ERROR_ROUTINE_LIMIT_EXCEEDED,
        )

    if not (DAYS_MIN <= len(proposal_result.days) <= DAYS_MAX):
        raise AIRoutineAdapterError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"La cantidad de días de la rutina ({len(proposal_result.days)}) excede los límites del dominio "
                f"({DAYS_MIN} a {DAYS_MAX} días)."
            ),
            error_code=ERROR_ROUTINE_LIMIT_EXCEEDED,
        )

    for day in proposal_result.days:
        if not (BLOCKS_MIN <= len(day.blocks) <= BLOCKS_MAX):
            raise AIRoutineAdapterError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    f"La cantidad de bloques ({len(day.blocks)}) en el día '{day.name}' está fuera del rango permitido "
                    f"({BLOCKS_MIN} a {BLOCKS_MAX})."
                ),
                error_code=ERROR_ROUTINE_LIMIT_EXCEEDED,
            )
        for block in day.blocks:
            if not (EXERCISES_PER_BLOCK_MIN <= len(block.exercises) <= EXERCISES_PER_BLOCK_MAX):
                raise AIRoutineAdapterError(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=(
                        f"La cantidad de ejercicios ({len(block.exercises)}) en el bloque '{block.name}' "
                        f"está fuera del rango permitido ({EXERCISES_PER_BLOCK_MIN} a {EXERCISES_PER_BLOCK_MAX})."
                    ),
                    error_code=ERROR_ROUTINE_LIMIT_EXCEEDED,
                )
            for ex_data in block.exercises:
                if (
                    ex_data.sets is None
                    or not isinstance(ex_data.sets, int)
                    or isinstance(ex_data.sets, bool)
                    or not (SETS_MIN <= ex_data.sets <= SETS_MAX)
                ):
                    raise AIRoutineAdapterError(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"La propuesta de IA contiene series fuera del rango válido ({SETS_MIN}-{SETS_MAX}).",
                        error_code=ERROR_ROUTINE_LIMIT_EXCEEDED,
                    )
                reps_clean = (ex_data.reps or "").strip()
                if not is_valid_reps_format(reps_clean):
                    raise AIRoutineAdapterError(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"La propuesta de IA contiene repeticiones vacías o con un formato inválido ('{reps_clean}').",
                        error_code=ERROR_ROUTINE_LIMIT_EXCEEDED,
                    )
                if (
                    ex_data.rest_seconds is None
                    or not isinstance(ex_data.rest_seconds, int)
                    or isinstance(ex_data.rest_seconds, bool)
                    or not (REST_MIN_SECONDS <= ex_data.rest_seconds <= REST_MAX_SECONDS)
                ):
                    raise AIRoutineAdapterError(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"La propuesta de IA contiene un descanso fuera del rango válido ({REST_MIN_SECONDS}-{REST_MAX_SECONDS}s).",
                        error_code=ERROR_ROUTINE_LIMIT_EXCEEDED,
                    )


def validate_routine_semantics(
    proposal_result: AIRoutineProposalResult,
    template: RoutineTemplate,
    trainer_exercises: list[Exercise],
    protected_zones: list[ProtectedZone],
) -> None:
    """Categoría C: Validación semántica (catálogo autorizado, restricciones, equipamiento y coherencia funcional)."""
    allowed_exercises: dict[str, Exercise] = {
        ex.id: ex for ex in trainer_exercises if getattr(ex, "deleted_at", None) is None
    }
    for day in getattr(template, "days", []) or []:
        for block in getattr(day, "blocks", []) or []:
            for entry in getattr(block, "exercises", []) or []:
                ex_obj = getattr(entry, "exercise", None)
                if ex_obj is not None and getattr(ex_obj, "deleted_at", None) is None:
                    ex_id = getattr(ex_obj, "id", None) or getattr(entry, "exercise_id", None)
                    if isinstance(ex_id, str):
                        allowed_exercises.setdefault(ex_id, ex_obj)
                    if isinstance(getattr(entry, "exercise_id", None), str):
                        allowed_exercises.setdefault(entry.exercise_id, ex_obj)

    require_no_materials = _requires_no_materials(template)

    for day_data in proposal_result.days:
        for block_data in day_data.blocks:
            for ex_data in block_data.exercises:
                exercise = allowed_exercises.get(ex_data.exercise_id)
                if not exercise:
                    raise AIRoutineAdapterError(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"La propuesta de IA referencia un ejercicio inexistente o no permitido ('{ex_data.exercise_id}').",
                        error_code="GEMINI_INVALID_EXERCISE",
                    )
                conflict = _conflicts_with_zones(exercise, protected_zones)
                if conflict:
                    raise AIRoutineAdapterError(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"La propuesta de IA incluye el ejercicio '{exercise.name}' que compromete la zona protegida '{conflict}'.",
                        error_code="GEMINI_DOMAIN_RESTRICTION_VIOLATION",
                    )
                if require_no_materials and not _exercise_has_no_materials(exercise):
                    raise AIRoutineAdapterError(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=(
                            f"La propuesta de IA incluye el ejercicio '{exercise.name}', "
                            "el cual no posee alternativa 'Sin materiales' requerida por la plantilla."
                        ),
                        error_code="GEMINI_DOMAIN_RESTRICTION_VIOLATION",
                    )

    # Verificar coherencia funcional de todas las sustituciones registradas en la traza
    for trace in proposal_result.substitutions_trace:
        if trace.action == "REPLACE" and trace.selected_exercise_id:
            orig_ex = allowed_exercises.get(trace.original_exercise_id)
            sel_ex = allowed_exercises.get(trace.selected_exercise_id)
            if orig_ex and sel_ex:
                is_compat, _, _ = evaluate_functional_equivalence(orig_ex, sel_ex)
                if not is_compat:
                    raise AIRoutineAdapterError(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=(
                            f"La sustitución de '{orig_ex.name}' por '{sel_ex.name}' es funcionalmente incoherente "
                            "con el patrón de movimiento y propósito original."
                        ),
                        error_code="GEMINI_INVALID_SUBSTITUTE",
                    )


def validate_routine_integrity(
    proposal_result: AIRoutineProposalResult,
    template: RoutineTemplate,
) -> None:
    """Categoría D: Validación de integridad entre días, bloques, ejercicios y solicitud original."""
    template_days = list(getattr(template, "days", []) or [])
    if template_days and len(proposal_result.days) > len(template_days):
        raise AIRoutineAdapterError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"La rutina generada contiene más días ({len(proposal_result.days)}) "
                f"que la plantilla original ({len(template_days)})."
            ),
            error_code=ERROR_INVALID_STRUCTURE,
        )

    for day_idx, day_data in enumerate(proposal_result.days):
        if day_data.order_index != day_idx:
            raise AIRoutineAdapterError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Índice de orden inconsistente en el día '{day_data.name}'.",
                error_code=ERROR_INVALID_STRUCTURE,
            )
        for blk_idx, block_data in enumerate(day_data.blocks):
            if block_data.order_index != blk_idx:
                raise AIRoutineAdapterError(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Índice de orden inconsistente en el bloque '{block_data.name}'.",
                    error_code=ERROR_INVALID_STRUCTURE,
                )
            seen_in_block: set[str] = set()
            for ex_idx, ex_data in enumerate(block_data.exercises):
                if ex_data.order_index != ex_idx:
                    raise AIRoutineAdapterError(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Índice de orden inconsistente para el ejercicio '{ex_data.exercise_id}'.",
                        error_code=ERROR_INVALID_STRUCTURE,
                    )
                if ex_data.exercise_id in seen_in_block:
                    raise AIRoutineAdapterError(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"El bloque '{block_data.name}' contiene ejercicios duplicados ('{ex_data.exercise_id}').",
                        error_code="GEMINI_DUPLICATE_EXERCISE",
                    )
                seen_in_block.add(ex_data.exercise_id)


def validate_generated_routine_proposal(
    proposal_result: AIRoutineProposalResult,
    template: RoutineTemplate,
    trainer_exercises: list[Exercise],
    protected_zones: list[ProtectedZone],
) -> None:
    """Ejecuta las cuatro categorías de validación obligatoria (A: Estructural, B: Cuantitativa, C: Semántica, D: Integridad)."""
    validate_routine_structure(proposal_result)
    validate_routine_quantities(proposal_result)
    validate_routine_semantics(proposal_result, template, trainer_exercises, protected_zones)
    validate_routine_integrity(proposal_result, template)


class HeuristicAIRoutineAdapter(AIRoutineAdapter):
    """Adaptador de IA basado en reglas biomecánicas y fisiológicas de adaptación.

    Cumple con el Principio II al ser determinista, seguro y sin dependencias
    externas ni credenciales en desarrollo y pruebas automatizadas.
    """

    def generate_adapted_routine(
        self,
        template: RoutineTemplate,
        student: StudentProfile,
        questionnaire: HealthQuestionnaire | None,
        protected_zones: list[ProtectedZone],
        trainer_exercises: list[Exercise],
    ) -> AIRoutineProposalResult:
        t_start = time.perf_counter()
        metrics = AIGenerationMetrics(provider="heuristic")

        t_ctx_start = time.perf_counter()
        modifications_log: list[str] = []
        substitutions_trace: list[SubstitutionTraceEntry] = []
        unsubstituted_exercises: list[dict[str, str]] = []

        student_name = f"{student.first_name or ''} {student.last_name or ''}".strip() or "el alumno"
        goals = [g.upper() for g in (student.fitness_goals or [])]
        require_no_materials = _requires_no_materials(template)

        # 1. Ajuste de intensidad global
        current_intensity = (template.intensity or "MEDIA").upper()
        if current_intensity not in INTENSITY_ORDER:
            current_intensity = "MEDIA"
        target_intensity = current_intensity

        if questionnaire and (
            questionnaire.has_heart_condition
            or questionnaire.has_chest_pain_activity
            or questionnaire.has_bone_joint_problem
        ):
            idx = INTENSITY_ORDER.index(current_intensity)
            if idx > 0:
                target_intensity = INTENSITY_ORDER[max(0, idx - 1)]
                modifications_log.append(
                    f"Intensidad ajustada de {current_intensity} a {target_intensity} por antecedentes de salud informados."
                )
        metrics.context_build_ms = round((time.perf_counter() - t_ctx_start) * 1000.0, 2)

        # 2. Filtrado determinista de catálogo y conteo de candidatos
        t_filter_start = time.perf_counter()
        active_catalog = [ex for ex in trainer_exercises if getattr(ex, "deleted_at", None) is None]
        safe_catalog = [
            ex
            for ex in active_catalog
            if _conflicts_with_zones(ex, protected_zones) is None
            and (not require_no_materials or _exercise_has_no_materials(ex))
        ]
        # Ordenamiento canónico para garantizar determinismo absoluto independientemente del orden en DB
        deterministic_catalog = sorted(
            active_catalog,
            key=lambda ex: (normalize_exercise_name(ex.name), str(ex.id)),
        )
        metrics.available_candidates_count = len(safe_catalog)
        metrics.rejected_candidates_count = len(trainer_exercises) - len(safe_catalog)
        metrics.candidate_filter_ms = round((time.perf_counter() - t_filter_start) * 1000.0, 2)

        # 3. Procesamiento y adaptación de días, bloques y ejercicios
        adapted_days: list[AdaptedDayData] = []
        template_total_occurrences = 0

        try:
            for day in template.days:
                adapted_blocks: list[AdaptedBlockData] = []
                for block in day.blocks:
                    adapted_exercises: list[AdaptedExerciseData] = []
                    for entry in block.exercises:
                        template_total_occurrences += 1
                        orig_ex = entry.exercise
                        conflict_zone = _conflicts_with_zones(orig_ex, protected_zones)
                        equipment_conflict = (
                            require_no_materials and not _exercise_has_no_materials(orig_ex)
                        )

                        selected_exercise_id = orig_ex.id
                        adaptation_note = None

                        if conflict_zone or equipment_conflict:
                            trigger_desc = conflict_zone or "requisito Sin materiales"
                            used_in_routine = {
                                ex_item.exercise_id
                                for day_it in adapted_days
                                for blk_it in day_it.blocks
                                for ex_item in blk_it.exercises
                            } | {
                                ex_item.exercise_id
                                for blk_it in adapted_blocks
                                for ex_item in blk_it.exercises
                            } | {ex_item.exercise_id for ex_item in adapted_exercises}

                            compat_matches = find_compatible_substitutes(
                                orig_exercise=orig_ex,
                                protected_zones=protected_zones,
                                catalog=deterministic_catalog,
                                exclude_ids=used_in_routine,
                                require_no_materials=require_no_materials,
                            )
                            if compat_matches:
                                replacement, _, matched_criteria = compat_matches[0]
                                selected_exercise_id = replacement.id
                                adaptation_note = (
                                    f"[REPLACE] Sustituido '{orig_ex.name}' por '{replacement.name}' para proteger {trigger_desc}."
                                )[:ADAPTATION_NOTE_MAX_LENGTH]
                                modifications_log.append(adaptation_note)
                                substitutions_trace.append(
                                    SubstitutionTraceEntry(
                                        day_name=_obj_name(day, "Día"),
                                        block_name=_obj_name(block, "Bloque"),
                                        original_exercise_id=orig_ex.id,
                                        original_exercise_name=orig_ex.name,
                                        proposed_exercise_id=replacement.id,
                                        selected_exercise_id=replacement.id,
                                        selected_exercise_name=replacement.name,
                                        action="REPLACE",
                                        engine="heuristic",
                                        reason=adaptation_note,
                                        trigger_condition=canonical_zone_key(conflict_zone) if conflict_zone else "no_materials",
                                        compatibility_criteria=matched_criteria,
                                    )
                                )
                            else:
                                removal_msg = (
                                    f"[REMOVE] Eliminado '{orig_ex.name}' por contraindicación con zona protegida "
                                    f"'{trigger_desc}' sin sustituto funcionalmente compatible y seguro disponible en el catálogo."
                                )
                                modifications_log.append(removal_msg)
                                unsubstituted_exercises.append(
                                    {
                                        "day_name": _obj_name(day, "Día"),
                                        "block_name": _obj_name(block, "Bloque"),
                                        "exercise_id": orig_ex.id,
                                        "exercise_name": orig_ex.name,
                                        "reason": f"Sin sustituto funcionalmente compatible para proteger '{trigger_desc}'.",
                                    }
                                )
                                substitutions_trace.append(
                                    SubstitutionTraceEntry(
                                        day_name=_obj_name(day, "Día"),
                                        block_name=_obj_name(block, "Bloque"),
                                        original_exercise_id=orig_ex.id,
                                        original_exercise_name=orig_ex.name,
                                        proposed_exercise_id=None,
                                        selected_exercise_id=None,
                                        selected_exercise_name=None,
                                        action="REMOVE",
                                        engine="heuristic",
                                        reason=removal_msg,
                                        trigger_condition=canonical_zone_key(conflict_zone) if conflict_zone else "no_materials",
                                        compatibility_criteria=["no_compatible_substitute_found"],
                                    )
                                )
                                continue
                        else:
                            substitutions_trace.append(
                                SubstitutionTraceEntry(
                                    day_name=_obj_name(day, "Día"),
                                    block_name=_obj_name(block, "Bloque"),
                                    original_exercise_id=orig_ex.id,
                                    original_exercise_name=orig_ex.name,
                                    proposed_exercise_id=orig_ex.id,
                                    selected_exercise_id=orig_ex.id,
                                    selected_exercise_name=orig_ex.name,
                                    action="KEEP",
                                    engine="heuristic",
                                    reason="Ejercicio original compatible con las restricciones del alumno.",
                                    trigger_condition=None,
                                    compatibility_criteria=["original_safe_and_compatible"],
                                )
                            )

                        # Adaptar series, repeticiones y descansos según objetivos
                        adapted_sets = entry.sets
                        adapted_reps = entry.reps
                        adapted_rest = entry.rest_seconds

                        if "HIPERTROFIA" in goals:
                            adapted_sets = max(3, min(entry.sets, 4))
                            adapted_reps = "8-12"
                            adapted_rest = max(60, min(entry.rest_seconds, 90))
                        elif "FUERZA" in goals:
                            adapted_sets = max(3, min(entry.sets + 1, 5))
                            adapted_reps = "5-6"
                            adapted_rest = max(120, entry.rest_seconds)
                        elif "RESISTENCIA" in goals or "PERDIDA_GRASA" in goals or "PERDIDA_DE_PESO" in goals:
                            adapted_sets = max(3, entry.sets)
                            adapted_reps = "15-20"
                            adapted_rest = min(entry.rest_seconds, 45)
                        elif "SALUD_POSTURAL" in goals or "REHABILITACION" in goals or "MOVILIDAD_REHABILITACION" in goals:
                            adapted_sets = min(entry.sets, 3)
                            adapted_reps = "12-15"
                            adapted_rest = max(entry.rest_seconds, 60)

                        if questionnaire and (questionnaire.has_heart_condition or questionnaire.has_chest_pain_activity):
                            adapted_sets = min(adapted_sets, 3)
                            adapted_rest = max(adapted_rest, 90)

                        orig_weight = _safe_float_weight(getattr(entry, "target_weight_kg", None))
                        prescribed_weight = orig_weight if selected_exercise_id == orig_ex.id else None

                        adapted_exercises.append(
                            AdaptedExerciseData(
                                exercise_id=selected_exercise_id,
                                order_index=len(adapted_exercises),
                                sets=adapted_sets,
                                reps=adapted_reps,
                                rest_seconds=adapted_rest,
                                adaptation_notes=adaptation_note,
                                target_weight_kg=prescribed_weight,
                            )
                        )

                    if adapted_exercises:
                        adapted_blocks.append(
                            AdaptedBlockData(
                                name=_obj_name(block, "Bloque"),
                                order_index=len(adapted_blocks),
                                exercises=adapted_exercises,
                                estimated_duration_minutes=_safe_int_or_none(
                                    getattr(block, "estimated_duration_minutes", None)
                                ),
                            )
                        )

                if adapted_blocks:
                    adapted_days.append(
                        AdaptedDayData(
                            name=_obj_name(day, "Día"),
                            order_index=len(adapted_days),
                            blocks=adapted_blocks,
                        )
                    )

            # 4. Manejo explícito de rutinas vacías o sin alternativas (Sección 3.4)
            if not adapted_days:
                if template_total_occurrences == 0:
                    raise AIRoutineAdapterError(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="La plantilla seleccionada no contiene ejercicios para generar una rutina.",
                        error_code=ERROR_EMPTY_ROUTINE,
                    )
                if metrics.available_candidates_count == 0:
                    raise AIRoutineAdapterError(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=(
                            "No fue posible generar la rutina porque ningún ejercicio de la biblioteca es seguro "
                            "para las zonas protegidas o restricciones registradas del alumno."
                        ),
                        error_code=ERROR_NO_SAFE_EXERCISES,
                    )
                raise AIRoutineAdapterError(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "No fue posible generar la rutina porque los ejercicios incompatibles de la plantilla "
                        "no cuentan con sustitutos funcionalmente compatibles y seguros en la biblioteca del entrenador."
                    ),
                    error_code=ERROR_NO_COMPATIBLE_SUBSTITUTES,
                )

            # 5. Síntesis del resumen de adaptaciones
            if not modifications_log:
                modifications_log.append("Rutina compatible: se mantuvieron los ejercicios base adaptando volumen y descanso.")

            is_partial = len(unsubstituted_exercises) > 0
            goals_text = ", ".join(goals) if goals else "Generales"
            summary_lines = [
                f"Propuesta de rutina adaptada por IA para {student_name}:",
                "- Proveedor utilizado: Adaptador Heurístico",
                f"- Objetivos del alumno: {goals_text}",
                f"- Intensidad asignada: {target_intensity}",
                "- Modificaciones y adaptaciones:",
            ]
            for log in modifications_log:
                summary_lines.append(f"  • {log}")
            if is_partial:
                missing_names = ", ".join(item["exercise_name"] for item in unsubstituted_exercises)
                summary_lines.append(
                    f"\n⚠️ Resultado parcial: {len(unsubstituted_exercises)} ejercicio(s) ({missing_names}) "
                    "no pudieron sustituirse por falta de alternativas funcionalmente compatibles en la biblioteca. "
                    "Se requiere revisión manual del entrenador antes de aprobar."
                )
            summary_lines.append("\n* Requiere revisión y aprobación manual del entrenador (Human-in-the-Loop).")

            proposal = AIRoutineProposalResult(
                name=f"{_obj_name(template, 'Rutina')} - Adaptada para {student_name}"[:150],
                duration_weeks=_template_duration_weeks(template),
                intensity=target_intensity,
                adaptation_summary="\n".join(summary_lines),
                days=adapted_days,
                has_no_materials_alternative=require_no_materials,
                is_partial=is_partial,
                unsubstituted_exercises=unsubstituted_exercises,
                substitutions_trace=substitutions_trace,
            )

            t_val_start = time.perf_counter()
            validate_generated_routine_proposal(
                proposal_result=proposal,
                template=template,
                trainer_exercises=trainer_exercises,
                protected_zones=protected_zones,
            )
            metrics.validation_ms = round((time.perf_counter() - t_val_start) * 1000.0, 2)
            metrics.total_generation_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
            metrics.success = True
            proposal.metrics = metrics.to_dict()
            _METRICS_COLLECTOR.record(metrics)
            return proposal

        except AIRoutineAdapterError as exc:
            metrics.total_generation_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
            metrics.success = False
            metrics.error_code = exc.error_code
            _METRICS_COLLECTOR.record(metrics)
            raise


GEMINI_SYSTEM_INSTRUCTION = (
    "Sos un asistente técnico de planificación de entrenamiento físico para entrenadores personales en Set to Set.\n"
    "Tu única función es proponer una adaptación estructurada de una rutina genérica en base a los objetivos de entrenamiento, "
    "las zonas corporales a proteger y las restricciones reportadas por el alumno.\n\n"
    "REGLAS OBLIGATORIAS:\n"
    "1. Para cada ejercicio de la rutina genérica debés indicar una acción explícita en el campo 'action':\n"
    "   - 'KEEP': conservar el ejercicio original cuando NO comprometa zonas protegidas ni presente contraindicaciones.\n"
    "   - 'REPLACE': sustituir el ejercicio original cuando comprometa una zona protegida o restricción del alumno, "
    "eligiendo EXCLUSIVAMENTE un 'replacement_exercise_id' presente en 'allowed_replacement_exercise_ids' (o en 'available_exercises_catalog') "
    "que sea seguro y funcionalmente equivalente (mismo patrón de movimiento o cadena biomecánica). "
    "NUNCA propongas como sustituto el mismo ejercicio, una variante con el mismo nombre ni un ejercicio funcionalmente incompatible (ej. nunca sustituir una sentadilla por una plancha).\n"
    "   - 'REMOVE': eliminar el ejercicio únicamente cuando sea inadecuado para las zonas protegidas o restricciones del alumno y "
    "no exista un ejercicio sustituto funcionalmente compatible en 'allowed_replacement_exercise_ids'.\n"
    "2. Jamás inventes ni modifiques identificadores ('original_exercise_id' o 'replacement_exercise_id').\n"
    "3. Respetá estrictamente los rangos y formatos del dominio para ejercicios con acción KEEP o REPLACE:\n"
    "   - 'sets': entero entre 1 y 20.\n"
    "   - 'reps': texto no vacío de hasta 50 caracteres indicando repeticiones o duración (ej. '10', '8-12', '12 c/l', '30s', '45s').\n"
    "   - 'rest_seconds': entero entre 0 y 600.\n"
    "   - 'intensity': únicamente uno de 'BAJA', 'MEDIA', 'ALTA', 'EXIGENTE'.\n"
    "4. En 'reason' incluí una justificación breve en español para el entrenador, diferenciando si fue conservado, sustituido o eliminado.\n"
    "5. LÍMITE DE SEGURIDAD NO CLÍNICO: NO realices diagnósticos médicos, NO prescribas tratamientos clínicos para lesiones "
    "o enfermedades y NO afirmes que una rutina es médicamente segura. Toda propuesta queda sujeta a la "
    "revisión y edición manual obligatoria del entrenador (Human-in-the-Loop)."
)


class GeminiAIRoutineAdapter(AIRoutineAdapter):
    """Adaptador de IA que integra Google Gemini API mediante el SDK oficial google-genai."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        client: Any | None = None,
        max_retries: int = 1,
    ) -> None:
        self.api_key = api_key if api_key is not None else get_gemini_api_key()
        self.model = (model if model is not None else get_gemini_model()).strip()
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else get_gemini_timeout_seconds()
        )
        self._client = client
        self.max_retries = max(0, min(int(max_retries), 1))

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.api_key:
            logger.warning("Google Gemini no está configurado en el servidor (falta GEMINI_API_KEY, HTTP 503).")
            raise AIRoutineAdapterError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Google Gemini no está configurado en el servidor (falta GEMINI_API_KEY). "
                    "Configurá la clave de API o utilizá explícitamente el modo heurístico."
                ),
                error_code="GEMINI_NOT_CONFIGURED",
            )
        if not self.model:
            logger.warning("El modelo de Google Gemini (GEMINI_MODEL) no está configurado en el servidor (HTTP 503).")
            raise AIRoutineAdapterError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="El modelo de Google Gemini (GEMINI_MODEL) no está configurado.",
                error_code="GEMINI_MODEL_NOT_CONFIGURED",
            )
        timeout_ms = max(1000, int(self.timeout_seconds * 1000))
        http_options = genai_types.HttpOptions(
            timeout=timeout_ms,
            retry_options=genai_types.HttpRetryOptions(attempts=1),
        )
        self._client = genai.Client(api_key=self.api_key, http_options=http_options)
        return self._client

    @staticmethod
    def _build_prompt_payload(
        template: RoutineTemplate,
        student: StudentProfile,
        questionnaire: HealthQuestionnaire | None,
        protected_zones: list[ProtectedZone],
        trainer_exercises: list[Exercise],
    ) -> dict[str, Any]:
        """Construye el payload mínimo necesario para Gemini con candidatos pre-filtrados y sin PII sensible."""
        require_no_materials = _requires_no_materials(template)
        health_info: dict[str, Any] = {
            "has_heart_condition": bool(questionnaire.has_heart_condition) if questionnaire else False,
            "has_chest_pain_activity": bool(questionnaire.has_chest_pain_activity) if questionnaire else False,
            "has_dizziness_or_balance_loss": (
                bool(questionnaire.has_dizziness_or_balance_loss) if questionnaire else False
            ),
            "has_bone_joint_problem": bool(questionnaire.has_bone_joint_problem) if questionnaire else False,
            "takes_prescription_meds": bool(questionnaire.takes_prescription_meds) if questionnaire else False,
            "other_medical_conditions": (
                questionnaire.other_medical_conditions
                if questionnaire and isinstance(getattr(questionnaire, "other_medical_conditions", None), str)
                else None
            ),
        }

        template_days: list[dict[str, Any]] = []
        for day in getattr(template, "days", []) or []:
            day_blocks: list[dict[str, Any]] = []
            for block in getattr(day, "blocks", []) or []:
                block_exercises: list[dict[str, Any]] = []
                for entry in getattr(block, "exercises", []) or []:
                    ex = entry.exercise
                    bio = infer_exercise_biomechanics(ex)
                    conflict = _conflicts_with_zones(ex, protected_zones)
                    compat_subs = find_compatible_substitutes(
                        orig_exercise=ex,
                        protected_zones=protected_zones,
                        catalog=trainer_exercises,
                        exclude_ids={entry.exercise_id},
                        require_no_materials=require_no_materials,
                    )
                    block_exercises.append(
                        {
                            "original_exercise_id": entry.exercise_id,
                            "name": ex.name,
                            "category": ex.category,
                            "target_muscle_group": ex.target_muscle_group,
                            "movement_pattern": bio.movement_pattern,
                            "functional_region": bio.functional_region,
                            "equipment_needed": ex.equipment_needed if isinstance(getattr(ex, "equipment_needed", None), str) else None,
                            "sets": entry.sets,
                            "reps": entry.reps,
                            "rest_seconds": entry.rest_seconds,
                            "contraindicated_zones": list(ex.contraindicated_zones or []),
                            "requires_adaptation": conflict is not None,
                            "allowed_replacement_exercise_ids": [sub_ex.id for sub_ex, _, _ in compat_subs],
                        }
                    )
                day_blocks.append(
                    {
                        "name": _obj_name(block, "Bloque"),
                        "order_index": block.order_index if isinstance(getattr(block, "order_index", None), int) else 0,
                        "exercises": block_exercises,
                    }
                )
            template_days.append(
                {
                    "name": _obj_name(day, "Día"),
                    "order_index": day.order_index if isinstance(getattr(day, "order_index", None), int) else 0,
                    "blocks": day_blocks,
                }
            )

        catalog: list[dict[str, Any]] = []
        for ex in trainer_exercises:
            if getattr(ex, "deleted_at", None) is not None:
                continue
            if _conflicts_with_zones(ex, protected_zones) is not None:
                continue
            if require_no_materials and not _exercise_has_no_materials(ex):
                continue
            ex_bio = infer_exercise_biomechanics(ex)
            catalog.append(
                {
                    "exercise_id": ex.id,
                    "name": ex.name,
                    "category": ex.category,
                    "target_muscle_group": ex.target_muscle_group,
                    "movement_pattern": ex_bio.movement_pattern,
                    "functional_region": ex_bio.functional_region,
                    "equipment_needed": ex.equipment_needed if isinstance(getattr(ex, "equipment_needed", None), str) else None,
                    "description": ex.description if isinstance(getattr(ex, "description", None), str) else None,
                    "contraindicated_zones": list(ex.contraindicated_zones or []),
                }
            )

        raw_motivation = getattr(student, "personal_motivation", None)
        return {
            "student_training_context": {
                "fitness_goals": list(student.fitness_goals or []),
                "personal_motivation": raw_motivation if isinstance(raw_motivation, str) else None,
                "protected_zones": [z.body_area if hasattr(z, "body_area") else str(z) for z in protected_zones],
                "health_restrictions": health_info,
            },
            "generic_routine_template": {
                "name": _obj_name(template, "Rutina"),
                "duration_weeks": _template_duration_weeks(template),
                "intensity": str(getattr(template, "intensity", "MEDIA") or "MEDIA"),
                "days": template_days,
            },
            "available_exercises_catalog": catalog,
        }

    @staticmethod
    def _extract_structured_response(response: Any) -> GeminiRoutineAdaptationSchema:
        """Extrae y valida la estructura JSON devuelta por Gemini."""
        if response is None:
            raise AIRoutineAdapterError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Google Gemini devolvió una respuesta vacía.",
                error_code="GEMINI_INVALID_JSON",
            )

        raw_text = getattr(response, "text", None)
        parsed_obj = getattr(response, "parsed", None)

        if isinstance(raw_text, str) and raw_text.strip():
            try:
                data = json.loads(raw_text)
                return GeminiRoutineAdaptationSchema.model_validate(data)
            except (json.JSONDecodeError, ValidationError, TypeError) as exc:
                raise AIRoutineAdapterError(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=(
                        "Google Gemini devolvió una respuesta JSON inválida o que no respeta el esquema esperado. "
                        "Podés reintentar o utilizar el modo heurístico."
                    ),
                    error_code="GEMINI_INVALID_JSON",
                ) from exc

        if isinstance(parsed_obj, GeminiRoutineAdaptationSchema):
            return parsed_obj

        if isinstance(parsed_obj, dict):
            try:
                return GeminiRoutineAdaptationSchema.model_validate(parsed_obj)
            except ValidationError as exc:
                raise AIRoutineAdapterError(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=(
                        "Google Gemini devolvió una estructura de datos inválida. "
                        "Podés reintentar o utilizar el modo heurístico."
                    ),
                    error_code="GEMINI_INVALID_JSON",
                ) from exc

        raise AIRoutineAdapterError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Google Gemini no devolvió una propuesta estructurada válida. "
                "Podés reintentar o utilizar el modo heurístico."
            ),
            error_code="GEMINI_INVALID_JSON",
        )

    def _validate_and_build_proposal(
        self,
        structured: GeminiRoutineAdaptationSchema,
        template: RoutineTemplate,
        student: StudentProfile,
        questionnaire: HealthQuestionnaire | None,
        protected_zones: list[ProtectedZone],
        trainer_exercises: list[Exercise],
    ) -> AIRoutineProposalResult:
        """Valida en el backend todas las reglas de dominio sobre la respuesta de Gemini."""
        intensity = (structured.intensity or "").strip().upper()
        if intensity not in INTENSITY_ORDER:
            raise AIRoutineAdapterError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    f"La propuesta de Gemini contiene una intensidad fuera de rango o inválida ('{structured.intensity}'). "
                    f"Valores permitidos: {', '.join(INTENSITY_ORDER)}."
                ),
                error_code="GEMINI_OUT_OF_RANGE",
            )

        if not structured.days:
            raise AIRoutineAdapterError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="La propuesta de Gemini no contiene días de entrenamiento estructurados.",
                error_code="GEMINI_INVALID_JSON",
            )

        require_no_materials = _requires_no_materials(template)

        # Catálogo permitido de ejercicios activos del entrenador
        catalog_by_id: dict[str, Exercise] = {
            ex.id: ex for ex in trainer_exercises if getattr(ex, "deleted_at", None) is None
        }
        # Ejercicios originales presentes en la plantilla base
        template_exercises_by_id: dict[str, Exercise] = {}
        template_entries_by_id: dict[str, Any] = {}
        template_blocks_by_day_block: dict[tuple[int, int], Any] = {}
        for d_i, t_day in enumerate(template.days):
            for b_i, t_block in enumerate(t_day.blocks):
                template_blocks_by_day_block[(d_i, b_i)] = t_block
                for t_entry in t_block.exercises:
                    template_exercises_by_id[t_entry.exercise_id] = t_entry.exercise
                    template_entries_by_id[t_entry.exercise_id] = t_entry
                    if getattr(t_entry.exercise, "deleted_at", None) is None:
                        catalog_by_id.setdefault(t_entry.exercise_id, t_entry.exercise)

        t_days = list(template.days or [])
        if len(structured.days) != len(t_days):
            raise AIRoutineAdapterError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    f"La propuesta de Gemini contiene {len(structured.days)} día(s), "
                    f"pero la plantilla original define {len(t_days)} día(s)."
                ),
                error_code="GEMINI_INCOMPLETE_DAYS",
            )

        adapted_days: list[AdaptedDayData] = []
        action_logs: list[str] = []
        substitutions_trace: list[SubstitutionTraceEntry] = []
        unsubstituted_exercises: list[dict[str, str]] = []
        all_decided_original_ids: set[str] = set()

        for day_idx, day_schema in enumerate(structured.days):
            day_name = (day_schema.name or "").strip() or f"Día {day_idx + 1}"
            day_name = day_name[:100]
            adapted_blocks: list[AdaptedBlockData] = []
            t_day = t_days[day_idx]
            t_blocks = list(getattr(t_day, "blocks", []) or [])

            if len(day_schema.blocks) != len(t_blocks):
                raise AIRoutineAdapterError(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=(
                        f"La propuesta de Gemini para el día '{day_name}' contiene {len(day_schema.blocks)} bloque(s), "
                        f"pero la plantilla original define {len(t_blocks)} bloque(s)."
                    ),
                    error_code="GEMINI_INCOMPLETE_BLOCKS",
                )

            for block_idx, block_schema in enumerate(day_schema.blocks):
                block_name = (block_schema.name or "").strip() or f"Bloque {block_idx + 1}"
                block_name = block_name[:100]
                adapted_exercises: list[AdaptedExerciseData] = []
                block_final_exercise_ids: set[str] = set()
                block_seen_original_ids: set[str] = set()
                t_blk = t_blocks[block_idx]
                t_blk_orig_set: set[str] = {
                    e.exercise_id
                    for e in getattr(t_blk, "exercises", []) or []
                    if getattr(e, "exercise_id", None)
                }

                block_kept_exercise_ids: set[str] = {
                    (d.original_exercise_id or "").strip()
                    for d in block_schema.exercises
                    if (d.action or "").strip().upper() == "KEEP" and (d.original_exercise_id or "").strip()
                }
                block_replacement_counts: Counter[str] = Counter(
                    (d.replacement_exercise_id or "").strip()
                    for d in block_schema.exercises
                    if (d.action or "").strip().upper() == "REPLACE" and (d.replacement_exercise_id or "").strip()
                )

                for decision in block_schema.exercises:
                    orig_id = (decision.original_exercise_id or "").strip()
                    if not orig_id or orig_id not in template_exercises_by_id:
                        raise AIRoutineAdapterError(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=(
                                f"La propuesta de Gemini referencia un ejercicio original inexistente o manipulado ('{orig_id}')."
                            ),
                            error_code="GEMINI_INVALID_EXERCISE",
                        )

                    if orig_id not in t_blk_orig_set:
                        orig_ex_name = template_exercises_by_id[orig_id].name
                        raise AIRoutineAdapterError(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=(
                                f"La propuesta de Gemini incluye una decisión para el ejercicio '{orig_ex_name}' en el bloque '{block_name}', "
                                "pero dicho ejercicio no pertenece a ese bloque en la plantilla original."
                            ),
                            error_code="GEMINI_INVALID_EXERCISE",
                        )

                    if orig_id in block_seen_original_ids:
                        raise AIRoutineAdapterError(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=(
                                f"La propuesta de Gemini contiene decisiones duplicadas o contradictorias para el ejercicio original '{orig_id}'."
                            ),
                            error_code="GEMINI_DUPLICATE_DECISION",
                        )
                    block_seen_original_ids.add(orig_id)
                    all_decided_original_ids.add(orig_id)

                    orig_exercise = template_exercises_by_id[orig_id]
                    action = (decision.action or "").strip().upper()
                    if action not in VALID_EXERCISE_ACTIONS:
                        raise AIRoutineAdapterError(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=(
                                f"La propuesta de Gemini contiene una acción inválida ('{decision.action}'). "
                                "Las acciones permitidas son KEEP, REPLACE o REMOVE."
                            ),
                            error_code="GEMINI_INVALID_ACTION",
                        )

                    reason = (decision.reason or "").strip() or "Adaptado según objetivos y perfil del alumno."
                    orig_conflict = _conflicts_with_zones(orig_exercise, protected_zones)

                    if action == "REMOVE":
                        action_logs.append(f"[REMOVE] Eliminado '{orig_exercise.name}': {reason}")
                        unsubstituted_exercises.append(
                            {
                                "day_name": day_name,
                                "block_name": block_name,
                                "exercise_id": orig_exercise.id,
                                "exercise_name": orig_exercise.name,
                                "reason": reason,
                            }
                        )
                        substitutions_trace.append(
                            SubstitutionTraceEntry(
                                day_name=day_name,
                                block_name=block_name,
                                original_exercise_id=orig_exercise.id,
                                original_exercise_name=orig_exercise.name,
                                proposed_exercise_id=None,
                                selected_exercise_id=None,
                                selected_exercise_name=None,
                                action="REMOVE",
                                engine="gemini",
                                reason=reason,
                                trigger_condition=canonical_zone_key(orig_conflict) if orig_conflict else "model_removal",
                                compatibility_criteria=["removed_without_substitute"],
                            )
                        )
                        continue

                    matched_criteria: list[str] = ["safety_zones_verified"]
                    if action == "REPLACE":
                        rep_id = (decision.replacement_exercise_id or "").strip()
                        if not rep_id or rep_id not in catalog_by_id:
                            raise AIRoutineAdapterError(
                                status_code=status.HTTP_502_BAD_GATEWAY,
                                detail=(
                                    f"La propuesta de Gemini sugirió un ejercicio sustituto inexistente o fuera del catálogo permitido ('{rep_id}')."
                                ),
                                error_code="GEMINI_INVALID_SUBSTITUTE",
                            )
                        if rep_id == orig_id:
                            raise AIRoutineAdapterError(
                                status_code=status.HTTP_502_BAD_GATEWAY,
                                detail=(
                                    f"La propuesta de Gemini intentó sustituir el ejercicio '{orig_exercise.name}' por el mismo ejercicio (mismo ID)."
                                ),
                                error_code="GEMINI_INVALID_SUBSTITUTE",
                            )
                        candidate = catalog_by_id[rep_id]
                        if normalize_exercise_name(candidate.name) == normalize_exercise_name(orig_exercise.name):
                            raise AIRoutineAdapterError(
                                status_code=status.HTTP_502_BAD_GATEWAY,
                                detail=(
                                    f"La propuesta de Gemini intentó sustituir '{orig_exercise.name}' por una variante con el mismo nombre ('{candidate.name}')."
                                ),
                                error_code="GEMINI_INVALID_SUBSTITUTE",
                            )
                        if rep_id in block_kept_exercise_ids:
                            raise AIRoutineAdapterError(
                                status_code=status.HTTP_502_BAD_GATEWAY,
                                detail=(
                                    f"La propuesta de Gemini introdujo un reemplazo duplicado ('{rep_id}') respecto de un ejercicio ya conservado."
                                ),
                                error_code="GEMINI_DUPLICATE_EXERCISE",
                            )
                        if block_replacement_counts[rep_id] > 1 or rep_id in block_final_exercise_ids:
                            raise AIRoutineAdapterError(
                                status_code=status.HTTP_502_BAD_GATEWAY,
                                detail=(
                                    f"La propuesta de Gemini contiene ejercicios finales duplicados dentro del bloque ('{candidate.name}')."
                                ),
                                error_code="GEMINI_DUPLICATE_EXERCISE",
                            )

                        # Verificar que el sustituto no viole zonas protegidas antes de evaluar equivalencia
                        cand_conflict = _conflicts_with_zones(candidate, protected_zones)
                        if cand_conflict:
                            raise AIRoutineAdapterError(
                                status_code=status.HTTP_502_BAD_GATEWAY,
                                detail=(
                                    f"La propuesta de Gemini conserva o asigna el ejercicio '{candidate.name}', "
                                    f"el cual es incompatible con la zona protegida '{cand_conflict}' del alumno."
                                ),
                                error_code="GEMINI_DOMAIN_RESTRICTION_VIOLATION",
                            )

                        if require_no_materials and not _exercise_has_no_materials(candidate):
                            raise AIRoutineAdapterError(
                                status_code=status.HTTP_502_BAD_GATEWAY,
                                detail=(
                                    f"La propuesta de Gemini seleccionó el sustituto '{candidate.name}', "
                                    "que no cuenta con alternativa 'Sin materiales' requerida por la plantilla."
                                ),
                                error_code="GEMINI_DOMAIN_RESTRICTION_VIOLATION",
                            )

                        is_compat, _, compat_reasons = evaluate_functional_equivalence(orig_exercise, candidate)
                        if not is_compat:
                            raise AIRoutineAdapterError(
                                status_code=status.HTTP_502_BAD_GATEWAY,
                                detail=(
                                    f"La propuesta de Gemini sugirió un ejercicio sustituto funcionalmente incompatible: "
                                    f"'{candidate.name}' no conserva el patrón de movimiento ni la finalidad biomecánica de '{orig_exercise.name}'."
                                ),
                                error_code="GEMINI_INVALID_SUBSTITUTE",
                            )
                        matched_criteria.extend(compat_reasons)
                        target_exercise = candidate
                        note_prefix = f"[REPLACE] Sustituido '{orig_exercise.name}' por '{target_exercise.name}': "
                    else:  # KEEP
                        if (
                            decision.replacement_exercise_id
                            and decision.replacement_exercise_id.strip() != orig_id
                        ):
                            raise AIRoutineAdapterError(
                                status_code=status.HTTP_502_BAD_GATEWAY,
                                detail=(
                                    "La propuesta de Gemini indicó acción KEEP pero especificó un ejercicio sustituto distinto al original."
                                ),
                                error_code="GEMINI_INVALID_EXERCISE",
                            )
                        target_exercise = orig_exercise
                        matched_criteria.append("original_kept")
                        note_prefix = f"[KEEP] Conservado '{orig_exercise.name}': "

                    if target_exercise.id in block_final_exercise_ids:
                        raise AIRoutineAdapterError(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=(
                                f"La propuesta de Gemini contiene ejercicios finales duplicados dentro del bloque ('{target_exercise.name}')."
                            ),
                            error_code="GEMINI_DUPLICATE_EXERCISE",
                        )
                    block_final_exercise_ids.add(target_exercise.id)

                    # Verificación final determinista: asegurar que el ejercicio seleccionado nunca viole zonas protegidas
                    conflict_zone = _conflicts_with_zones(target_exercise, protected_zones)
                    if conflict_zone:
                        raise AIRoutineAdapterError(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=(
                                f"La propuesta de Gemini conserva o asigna el ejercicio '{target_exercise.name}', "
                                f"el cual es incompatible con la zona protegida '{conflict_zone}' del alumno."
                            ),
                            error_code="GEMINI_DOMAIN_RESTRICTION_VIOLATION",
                        )

                    if require_no_materials and not _exercise_has_no_materials(target_exercise):
                        raise AIRoutineAdapterError(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=(
                                f"La propuesta de Gemini conserva o asigna el ejercicio '{target_exercise.name}', "
                                "el cual carece de alternativa 'Sin materiales'."
                            ),
                            error_code="GEMINI_DOMAIN_RESTRICTION_VIOLATION",
                        )

                    # Validar rangos de series, repeticiones y descanso
                    sets = decision.sets
                    reps = (decision.reps or "").strip()
                    rest_seconds = decision.rest_seconds

                    if (
                        sets is None
                        or not isinstance(sets, int)
                        or isinstance(sets, bool)
                        or not (SETS_MIN <= sets <= SETS_MAX)
                    ):
                        raise AIRoutineAdapterError(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=(
                                f"La propuesta de Gemini contiene una cantidad de series fuera de rango ({sets}). "
                                f"El rango válido es de {SETS_MIN} a {SETS_MAX} series."
                            ),
                            error_code="GEMINI_OUT_OF_RANGE",
                        )

                    if not is_valid_reps_format(reps):
                        raise AIRoutineAdapterError(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=(
                                f"La propuesta de Gemini contiene un valor o formato de repeticiones fuera de rango o inválido ('{reps}'). "
                                "Debe ser un formato deportivo válido (ej. '10', '8-12', '12 c/l')."
                            ),
                            error_code="GEMINI_OUT_OF_RANGE",
                        )

                    if (
                        rest_seconds is None
                        or not isinstance(rest_seconds, int)
                        or isinstance(rest_seconds, bool)
                        or not (REST_MIN_SECONDS <= rest_seconds <= REST_MAX_SECONDS)
                    ):
                        raise AIRoutineAdapterError(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=(
                                f"La propuesta de Gemini contiene un tiempo de descanso fuera de rango ({rest_seconds}s). "
                                f"El rango válido es de {REST_MIN_SECONDS} a {REST_MAX_SECONDS} segundos."
                            ),
                            error_code="GEMINI_OUT_OF_RANGE",
                        )

                    full_note = f"{note_prefix}{reason}"[:ADAPTATION_NOTE_MAX_LENGTH]
                    action_logs.append(full_note)

                    substitutions_trace.append(
                        SubstitutionTraceEntry(
                            day_name=day_name,
                            block_name=block_name,
                            original_exercise_id=orig_exercise.id,
                            original_exercise_name=orig_exercise.name,
                            proposed_exercise_id=target_exercise.id,
                            selected_exercise_id=target_exercise.id,
                            selected_exercise_name=target_exercise.name,
                            action=action,
                            engine="gemini",
                            reason=reason,
                            trigger_condition=canonical_zone_key(orig_conflict) if orig_conflict else "goal_or_context_adaptation",
                            compatibility_criteria=matched_criteria,
                        )
                    )

                    t_blk = template_blocks_by_day_block.get((day_idx, block_idx))
                    orig_entry_match = None
                    if t_blk:
                        for candidate_entry in getattr(t_blk, "exercises", []):
                            if getattr(candidate_entry, "exercise_id", None) == decision.original_exercise_id:
                                orig_entry_match = candidate_entry
                                break
                    if orig_entry_match is None:
                        orig_entry_match = template_entries_by_id.get(decision.original_exercise_id)

                    target_wt = (
                        _safe_float_weight(getattr(orig_entry_match, "target_weight_kg", None))
                        if orig_entry_match and action == "KEEP"
                        else None
                    )

                    adapted_exercises.append(
                        AdaptedExerciseData(
                            exercise_id=target_exercise.id,
                            order_index=len(adapted_exercises),
                            sets=sets,
                            reps=reps,
                            rest_seconds=rest_seconds,
                            adaptation_notes=full_note,
                            target_weight_kg=target_wt,
                        )
                    )

                missing_in_block = t_blk_orig_set - block_seen_original_ids
                if missing_in_block:
                    missing_names = [
                        template_exercises_by_id[mid].name
                        for mid in sorted(missing_in_block)
                        if mid in template_exercises_by_id
                    ]
                    raise AIRoutineAdapterError(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=(
                            f"La propuesta de Gemini está incompleta para el bloque '{block_name}': faltan decisiones explícitas (KEEP, REPLACE o REMOVE) "
                            f"para {len(missing_in_block)} ejercicio(s) de la plantilla original ({', '.join(missing_names)})."
                        ),
                        error_code="GEMINI_INCOMPLETE_DECISIONS",
                    )

                if adapted_blocks is not None and adapted_exercises:
                    t_blk = template_blocks_by_day_block.get((day_idx, block_idx))
                    estimated_duration = (
                        _safe_int_or_none(getattr(t_blk, "estimated_duration_minutes", None))
                        if t_blk
                        else None
                    )
                    adapted_blocks.append(
                        AdaptedBlockData(
                            name=block_name,
                            order_index=len(adapted_blocks),
                            exercises=adapted_exercises,
                            estimated_duration_minutes=estimated_duration,
                        )
                    )

            if adapted_blocks:
                adapted_days.append(
                    AdaptedDayData(
                        name=day_name,
                        order_index=len(adapted_days),
                        blocks=adapted_blocks,
                    )
                )

        missing_original_ids = set(template_exercises_by_id.keys()) - all_decided_original_ids
        if missing_original_ids:
            missing_names = [template_exercises_by_id[mid].name for mid in sorted(missing_original_ids)]
            raise AIRoutineAdapterError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "La propuesta de Gemini está incompleta: faltan decisiones explícitas (KEEP, REPLACE o REMOVE) "
                    f"para {len(missing_original_ids)} ejercicio(s) de la plantilla original ({', '.join(missing_names)})."
                ),
                error_code="GEMINI_INCOMPLETE_DECISIONS",
            )

        if not adapted_days:
            raise AIRoutineAdapterError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "La propuesta de Gemini resultó en una rutina vacía porque se eliminaron todos los ejercicios "
                    "sin conservar ni sustituir ninguno."
                ),
                error_code=ERROR_EMPTY_ROUTINE,
            )

        student_name = f"{getattr(student, 'first_name', '') or ''} {getattr(student, 'last_name', '') or ''}".strip() or "el alumno"
        base_summary = (structured.adaptation_summary or "").strip()
        is_partial = len(unsubstituted_exercises) > 0
        summary_lines = [
            f"Propuesta de rutina adaptada por IA para {student_name}:",
            f"- Proveedor utilizado: Google Gemini ({self.model})",
            f"- Intensidad propuesta: {intensity}",
        ]
        if base_summary:
            summary_lines.append(f"- Síntesis de adaptación: {base_summary}")
        if action_logs:
            summary_lines.append("- Detalle de acciones por ejercicio:")
            for log_item in action_logs:
                summary_lines.append(f"  • {log_item}")

        if is_partial:
            missing_names_str = ", ".join(item["exercise_name"] for item in unsubstituted_exercises)
            summary_lines.append(
                f"\n⚠️ Resultado parcial: {len(unsubstituted_exercises)} ejercicio(s) ({missing_names_str}) "
                "fueron eliminados sin sustituto compatible. Requiere revisión del entrenador."
            )

        if questionnaire and getattr(questionnaire, "has_risk_answers", False) is True:
            summary_lines.append(
                "\n⚠️ Aviso importante: El alumno registra antecedentes en su declaración de salud. "
                "Esta propuesta no constituye consejo ni diagnóstico médico y no sustituye la evaluación de un profesional de salud."
            )
        summary_lines.append(
            "\n* Propuesta generada por IA en estado pendiente de revisión. Requiere aprobación manual del entrenador (Human-in-the-Loop)."
        )

        proposal = AIRoutineProposalResult(
            name=f"{_obj_name(template, 'Rutina')} - Adaptada para {student_name}"[:150],
            duration_weeks=_template_duration_weeks(template),
            intensity=intensity,
            adaptation_summary="\n".join(summary_lines),
            days=adapted_days,
            has_no_materials_alternative=require_no_materials,
            is_partial=is_partial,
            unsubstituted_exercises=unsubstituted_exercises,
            substitutions_trace=substitutions_trace,
        )
        validate_generated_routine_proposal(
            proposal_result=proposal,
            template=template,
            trainer_exercises=trainer_exercises,
            protected_zones=protected_zones,
        )
        return proposal

    def _invoke_gemini_once(self, client: Any, prompt_text: str) -> Any:
        try:
            return client.models.generate_content(
                model=self.model,
                contents=prompt_text,
                config=genai_types.GenerateContentConfig(
                    system_instruction=GEMINI_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=GeminiRoutineAdaptationSchema,
                    temperature=0.0,
                ),
            )
        except AIRoutineAdapterError:
            raise
        except genai_errors.APIError as exc:
            code = getattr(exc, "code", None)
            err_status = str(getattr(exc, "status", "") or "").upper()
            err_msg = str(getattr(exc, "message", "") or "").lower()

            if (
                code == 429
                or "RESOURCE_EXHAUSTED" in err_status
                or "quota" in err_msg
                or "rate limit" in err_msg
            ):
                logger.warning(
                    "Cuota agotada en Google Gemini API (HTTP 429, estado=%s, mensaje=%s).",
                    err_status,
                    err_msg,
                )
                raise AIRoutineAdapterError(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        "Se agotó la cuota disponible de Google Gemini (límite de solicitudes alcanzado). "
                        "Esperá unos instantes para reintentar o utilizá explícitamente el modo heurístico."
                    ),
                    error_code="GEMINI_QUOTA_EXCEEDED",
                ) from exc

            if (
                code in (401, 403)
                or err_status in ("UNAUTHENTICATED", "PERMISSION_DENIED")
                or "api key" in err_msg
                or "api_key" in err_msg
                or "authentication" in err_msg
                or "credential" in err_msg
            ):
                logger.error("Error de autenticación con Google Gemini API (código=%s).", code)
                raise AIRoutineAdapterError(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=(
                        "Error de autenticación con Google Gemini: verificá que GEMINI_API_KEY sea válida y tenga permisos activos."
                    ),
                    error_code="GEMINI_AUTH_ERROR",
                ) from exc

            if code in (408, 504) or "DEADLINE_EXCEEDED" in err_status or "timeout" in err_msg:
                logger.warning(
                    "Timeout reportado por Google Gemini API (HTTP 504 / DEADLINE_EXCEEDED, código=%s, estado=%s, mensaje=%s).",
                    code,
                    err_status,
                    err_msg,
                )
                raise AIRoutineAdapterError(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail=(
                        "Tiempo de espera agotado al consultar Google Gemini. "
                        "Podés reintentar la generación o utilizar explícitamente el modo heurístico."
                    ),
                    error_code="GEMINI_TIMEOUT",
                ) from exc

            if code == 503 or "UNAVAILABLE" in err_status or "service unavailable" in err_msg:
                logger.warning(
                    "Servicio no disponible en Google Gemini API (HTTP 503, código=%s, estado=%s, mensaje=%s).",
                    code,
                    err_status,
                    err_msg,
                )
                raise AIRoutineAdapterError(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "Google Gemini no se encuentra disponible temporalmente. "
                        "Podés reintentar en unos instantes o utilizar explícitamente el modo heurístico."
                    ),
                    error_code="GEMINI_SERVICE_UNAVAILABLE",
                ) from exc

            logger.error("Error de comunicación con Google Gemini API (código=%s, estado=%s).", code, err_status)
            raise AIRoutineAdapterError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "Google Gemini no pudo generar la propuesta de rutina en este momento. "
                    "Podés reintentar o utilizar explícitamente el modo heurístico."
                ),
                error_code="GEMINI_API_ERROR",
            ) from exc
        except (TimeoutError, httpx.TimeoutException) as exc:
            exc_name = type(exc).__name__
            logger.warning(
                "Timeout de red/socket esperando respuesta de Google Gemini API (tipo=%s, detalle=%s).",
                exc_name,
                exc,
            )
            raise AIRoutineAdapterError(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=(
                    "Tiempo de espera agotado al consultar Google Gemini. "
                    "Podés reintentar la generación o utilizar explícitamente el modo heurístico."
                ),
                error_code="GEMINI_TIMEOUT",
            ) from exc
        except (httpx.RequestError, ConnectionError, OSError) as exc:
            logger.error("Error de conexión hacia Google Gemini API.")
            raise AIRoutineAdapterError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "No fue posible conectar con Google Gemini para generar la propuesta. "
                    "Verificá tu conexión, reintentá o utilizá el modo heurístico."
                ),
                error_code="GEMINI_CONNECTION_ERROR",
            ) from exc

    def generate_adapted_routine(
        self,
        template: RoutineTemplate,
        student: StudentProfile,
        questionnaire: HealthQuestionnaire | None,
        protected_zones: list[ProtectedZone],
        trainer_exercises: list[Exercise],
    ) -> AIRoutineProposalResult:
        t_start = time.perf_counter()
        metrics = AIGenerationMetrics(provider="gemini")

        try:
            client = self._get_client()

            t_ctx_start = time.perf_counter()
            prompt_payload = self._build_prompt_payload(
                template=template,
                student=student,
                questionnaire=questionnaire,
                protected_zones=protected_zones,
                trainer_exercises=trainer_exercises,
            )
            metrics.context_build_ms = round((time.perf_counter() - t_ctx_start) * 1000.0, 2)

            t_filter_start = time.perf_counter()
            available_catalog = prompt_payload.get("available_exercises_catalog", [])
            metrics.available_candidates_count = len(available_catalog)
            metrics.rejected_candidates_count = max(0, len(trainer_exercises) - len(available_catalog))

            # Verificar pre-condiciones determinísticas del dominio antes de llamar a Gemini:
            # Si la plantilla tiene ejercicios, todos requieren adaptación por conflicto con zonas protegidas,
            # y no existe ningún ejercicio seguro ni sustituto compatible, abortar sin consumir cuota de Gemini.
            template_ex_items = [
                ex_item
                for day_item in prompt_payload.get("generic_routine_template", {}).get("days", [])
                for blk_item in day_item.get("blocks", [])
                for ex_item in blk_item.get("exercises", [])
            ]
            if template_ex_items and all(item.get("requires_adaptation") for item in template_ex_items):
                if metrics.available_candidates_count == 0:
                    metrics.candidate_filter_ms = round((time.perf_counter() - t_filter_start) * 1000.0, 2)
                    raise AIRoutineAdapterError(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=(
                            "No existen ejercicios seguros disponibles en el catálogo del entrenador "
                            "para las restricciones registradas del alumno."
                        ),
                        error_code=ERROR_NO_SAFE_EXERCISES,
                    )
                if all(len(item.get("allowed_replacement_exercise_ids", [])) == 0 for item in template_ex_items):
                    metrics.candidate_filter_ms = round((time.perf_counter() - t_filter_start) * 1000.0, 2)
                    raise AIRoutineAdapterError(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=(
                            "No existen ejercicios sustitutos funcionalmente compatibles y seguros en el catálogo "
                            "para adaptar los ejercicios de la plantilla."
                        ),
                        error_code=ERROR_NO_COMPATIBLE_SUBSTITUTES,
                    )
            metrics.candidate_filter_ms = round((time.perf_counter() - t_filter_start) * 1000.0, 2)

            base_prompt_text = (
                "Analizá el siguiente contexto de entrenamiento y devolvé exclusivamente un objeto JSON "
                "que respete el esquema indicado, definiendo una acción explícita (KEEP, REPLACE o REMOVE) "
                "para cada ejercicio de la rutina genérica:\n\n"
                f"{json.dumps(prompt_payload, ensure_ascii=False)}"
            )

            logger.info("Invocando proveedor de IA 'gemini' con modelo '%s' para US-13.", self.model)

            last_correctable_error: AIRoutineAdapterError | None = None
            for attempt in range(self.max_retries + 1):
                if attempt == 0:
                    current_prompt = base_prompt_text
                else:
                    metrics.retries_count += 1
                    assert last_correctable_error is not None
                    logger.warning(
                        "Reintentando generación con Gemini (intento %d/%d, motivo=%s): %s",
                        attempt + 1,
                        self.max_retries + 1,
                        last_correctable_error.error_code,
                        last_correctable_error.detail,
                    )
                    current_prompt = (
                        f"{base_prompt_text}\n\n"
                        f"CORRECCIÓN OBLIGATORIA (REINTENTO {attempt}/{self.max_retries}):\n"
                        f"Tu respuesta anterior fue rechazada por la validación del backend con el código '{last_correctable_error.error_code}':\n"
                        f'"{last_correctable_error.detail}"\n'
                        "Corregí este error específico respetando estrictamente todos los 'original_exercise_id' de cada bloque, "
                        "eligiendo sustitutos exclusivamente de 'allowed_replacement_exercise_ids' y respetando los rangos del dominio."
                    )

                t_gem_start = time.perf_counter()
                response = self._invoke_gemini_once(client, current_prompt)
                metrics.gemini_latency_ms = round(
                    metrics.gemini_latency_ms + (time.perf_counter() - t_gem_start) * 1000.0,
                    2,
                )

                t_val_start = time.perf_counter()
                try:
                    structured = self._extract_structured_response(response)
                    proposal = self._validate_and_build_proposal(
                        structured=structured,
                        template=template,
                        student=student,
                        questionnaire=questionnaire,
                        protected_zones=protected_zones,
                        trainer_exercises=trainer_exercises,
                    )
                    metrics.validation_ms = round(
                        metrics.validation_ms + (time.perf_counter() - t_val_start) * 1000.0,
                        2,
                    )
                    metrics.total_generation_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
                    metrics.success = True
                    proposal.metrics = metrics.to_dict()
                    _METRICS_COLLECTOR.record(metrics)
                    return proposal
                except AIRoutineAdapterError as val_exc:
                    metrics.validation_ms = round(
                        metrics.validation_ms + (time.perf_counter() - t_val_start) * 1000.0,
                        2,
                    )
                    if val_exc.error_code in RETRYABLE_GEMINI_ERROR_CODES and attempt < self.max_retries:
                        last_correctable_error = val_exc
                        continue
                    if attempt > 0:
                        logger.warning(
                            "Reintentos agotados en Gemini tras %d intentos (último código=%s).",
                            attempt + 1,
                            val_exc.error_code,
                        )
                    raise

            raise last_correctable_error or AIRoutineAdapterError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Google Gemini no devolvió una propuesta válida.",
                error_code="GEMINI_INVALID_JSON",
            )
        except AIRoutineAdapterError as exc:
            metrics.total_generation_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
            metrics.success = False
            metrics.error_code = exc.error_code
            _METRICS_COLLECTOR.record(metrics)
            raise


def get_ai_routine_adapter(provider_override: str | None = None) -> AIRoutineAdapter:
    """Factory para obtener la instancia del adaptador de IA configurado o solicitado explícitamente."""
    provider = (provider_override or get_ai_provider()).strip().lower()
    if provider == "gemini":
        logger.info("Seleccionado proveedor de IA: gemini")
        return GeminiAIRoutineAdapter()
    if provider == "heuristic":
        logger.info("Seleccionado proveedor de IA: heuristic")
        return HeuristicAIRoutineAdapter()
    raise AIRoutineAdapterError(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Proveedor de IA no soportado: '{provider}'. Valores válidos: 'gemini', 'heuristic'.",
        error_code="INVALID_AI_PROVIDER",
    )
