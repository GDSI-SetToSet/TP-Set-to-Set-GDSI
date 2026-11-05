import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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

INTENSITY_ORDER = ["BAJA", "MEDIA", "ALTA", "EXIGENTE"]
VALID_EXERCISE_ACTIONS = ("KEEP", "REPLACE", "REMOVE")
ExerciseActionLiteral = Literal["KEEP", "REPLACE", "REMOVE"]
IntensityLiteral = Literal["BAJA", "MEDIA", "ALTA", "EXIGENTE"]
SETS_MIN = 1
SETS_MAX = 20
REST_MIN_SECONDS = 0
REST_MAX_SECONDS = 600
REPS_MAX_LENGTH = 50
REPS_MIN_VALUE = 1
REPS_MAX_VALUE = 100
ADAPTATION_NOTE_MAX_LENGTH = 255

_REPS_FORMAT_PATTERN = re.compile(
    r"^(\d{1,3})(?:\s*-\s*(\d{1,3}))?(?:\s*[a-zA-ZáéíóúÁÉÍÓÚñÑ/.\s]{1,35})?$"
)


def normalize_exercise_name(name: str | None) -> str:
    """Normaliza el nombre de un ejercicio para comparaciones semánticas libres de acentos y puntuación."""
    import unicodedata

    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", name.strip().lower())
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", ascii_text)


def find_safe_substitute(
    orig_exercise: Exercise,
    protected_zones: list[ProtectedZone],
    catalog: list[Exercise],
    exclude_ids: set[str] | None = None,
) -> Exercise | None:
    """Encuentra un sustituto seguro y biomecánicamente compatible en el catálogo del entrenador.

    Reglas deterministas obligatorias:
    1. Nunca puede ser el mismo ejercicio (ni por ID ni por nombre normalizado).
    2. Nunca puede comprometer ninguna zona corporal protegida del alumno.
    3. No puede ser un ejercicio ya excluido (por ejemplo, ya conservado en la misma rutina/bloque).
    4. Prioridad de compatibilidad funcional:
       a) Mismo grupo muscular y misma categoría de ejercicio.
       b) Mismo grupo muscular.
       c) Misma categoría.
       d) Cualquier candidato del catálogo libre de contraindicaciones.
    """
    excluded = exclude_ids or set()
    orig_norm_name = normalize_exercise_name(orig_exercise.name)
    safe_candidates: list[Exercise] = []

    for cand in catalog:
        if cand.deleted_at is not None:
            continue
        if cand.id == orig_exercise.id or cand.id in excluded:
            continue
        if normalize_exercise_name(cand.name) == orig_norm_name:
            continue
        if _conflicts_with_zones(cand, protected_zones) is not None:
            continue
        safe_candidates.append(cand)

    if not safe_candidates:
        return None

    same_muscle_and_cat = [
        c for c in safe_candidates
        if c.target_muscle_group == orig_exercise.target_muscle_group and c.category == orig_exercise.category
    ]
    if same_muscle_and_cat:
        return same_muscle_and_cat[0]

    same_muscle = [c for c in safe_candidates if c.target_muscle_group == orig_exercise.target_muscle_group]
    if same_muscle:
        return same_muscle[0]

    same_cat = [c for c in safe_candidates if c.category == orig_exercise.category]
    if same_cat:
        return same_cat[0]

    return safe_candidates[0]


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
        "lumbar": ["lumbar", "espalda baja", "peso muerto", "dorsal", "raquis"],
        "lower back": ["lumbar", "espalda baja", "peso muerto", "dorsal", "raquis"],
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
        modifications_log: list[str] = []
        student_name = f"{student.first_name or ''} {student.last_name or ''}".strip() or "el alumno"
        goals = [g.upper() for g in (student.fitness_goals or [])]

        # 1. Ajuste de intensidad global
        current_intensity = template.intensity.upper()
        if current_intensity not in INTENSITY_ORDER:
            current_intensity = "MEDIA"
        target_intensity = current_intensity

        # Reducción por salud si hay afección cardíaca o dolor en actividad
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

        # 2. Procesamiento y adaptación de días, bloques y ejercicios
        adapted_days: list[AdaptedDayData] = []

        for day in template.days:
            adapted_blocks: list[AdaptedBlockData] = []
            for block in day.blocks:
                adapted_exercises: list[AdaptedExerciseData] = []
                for entry in block.exercises:
                    orig_ex = entry.exercise
                    conflict_zone = _conflicts_with_zones(orig_ex, protected_zones)

                    selected_exercise_id = orig_ex.id
                    adaptation_note = None

                    if conflict_zone:
                        # Buscar alternativa segura y compatible en la biblioteca del entrenador
                        used_in_routine = {
                            ex_item.exercise_id
                            for day_it in adapted_days
                            for blk_it in day_it.blocks
                            for ex_item in blk_it.exercises
                        } | {
                            ex_item.exercise_id
                            for blk_it in adapted_blocks
                            for ex_item in blk_it.exercises
                        }
                        replacement = find_safe_substitute(
                            orig_exercise=orig_ex,
                            protected_zones=protected_zones,
                            catalog=trainer_exercises,
                            exclude_ids=used_in_routine,
                        )
                        if replacement:
                            selected_exercise_id = replacement.id
                            adaptation_note = (
                                f"[REPLACE] Sustituido '{orig_ex.name}' por '{replacement.name}' para proteger {conflict_zone}."
                            )
                            modifications_log.append(adaptation_note)
                        else:
                            # Si no hay alternativa segura, eliminar el ejercicio de la rutina con aviso explícito
                            modifications_log.append(
                                f"[REMOVE] Eliminado '{orig_ex.name}' por contraindicación con zona protegida '{conflict_zone}' sin sustituto seguro disponible en el catálogo."
                            )
                            continue

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

                    # Ajustes adicionales si el cuestionario de salud lo amerita
                    if questionnaire and (questionnaire.has_heart_condition or questionnaire.has_chest_pain_activity):
                        adapted_sets = min(adapted_sets, 3)
                        adapted_rest = max(adapted_rest, 90)

                    orig_weight = float(entry.target_weight_kg) if getattr(entry, "target_weight_kg", None) is not None else None
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
                            name=block.name,
                            order_index=len(adapted_blocks),
                            exercises=adapted_exercises,
                            estimated_duration_minutes=getattr(block, "estimated_duration_minutes", None),
                        )
                    )

            if adapted_blocks:
                adapted_days.append(
                    AdaptedDayData(
                        name=day.name,
                        order_index=len(adapted_days),
                        blocks=adapted_blocks,
                    )
                )

        # 4. Síntesis del resumen de adaptaciones
        if not modifications_log:
            modifications_log.append("Rutina compatible: se mantuvieron los ejercicios base adaptando volumen y descanso.")

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
        summary_lines.append("\n* Requiere revisión y aprobación manual del entrenador (Human-in-the-Loop).")

        return AIRoutineProposalResult(
            name=f"{template.name} - Adaptada para {student_name}",
            duration_weeks=template.duration_weeks,
            intensity=target_intensity,
            adaptation_summary="\n".join(summary_lines),
            days=adapted_days,
            has_no_materials_alternative=getattr(template, "has_no_materials_alternative", False),
        )


GEMINI_SYSTEM_INSTRUCTION = (
    "Sos un asistente técnico de planificación de entrenamiento físico para entrenadores personales en Set to Set.\n"
    "Tu única función es proponer una adaptación estructurada de una rutina genérica en base a los objetivos de entrenamiento, "
    "las zonas corporales a proteger y las restricciones reportadas por el alumno.\n\n"
    "REGLAS OBLIGATORIAS:\n"
    "1. Para cada ejercicio de la rutina genérica debés indicar una acción explícita en el campo 'action':\n"
    "   - 'KEEP': conservar el ejercicio original cuando NO comprometa zonas protegidas ni presente contraindicaciones.\n"
    "   - 'REPLACE': sustituir el ejercicio original cuando comprometa una zona protegida o restricción del alumno, "
    "eligiendo EXCLUSIVAMENTE un 'replacement_exercise_id' presente en 'available_exercises_catalog' que sea seguro. "
    "NUNCA propongas como sustituto el mismo ejercicio ni una variante con el mismo nombre o contraindicación.\n"
    "   - 'REMOVE': eliminar el ejercicio cuando sea inadecuado para las zonas protegidas o restricciones del alumno y "
    "no exista un ejercicio sustituto seguro en 'available_exercises_catalog'.\n"
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
    ) -> None:
        self.api_key = api_key if api_key is not None else get_gemini_api_key()
        self.model = (model if model is not None else get_gemini_model()).strip()
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else get_gemini_timeout_seconds()
        )
        self._client = client

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
        """Construye el payload mínimo necesario para Gemini sin incluir PII sensible del alumno."""
        health_info: dict[str, Any] = {
            "has_heart_condition": bool(questionnaire.has_heart_condition) if questionnaire else False,
            "has_chest_pain_activity": bool(questionnaire.has_chest_pain_activity) if questionnaire else False,
            "has_dizziness_or_balance_loss": (
                bool(questionnaire.has_dizziness_or_balance_loss) if questionnaire else False
            ),
            "has_bone_joint_problem": bool(questionnaire.has_bone_joint_problem) if questionnaire else False,
            "takes_prescription_meds": bool(questionnaire.takes_prescription_meds) if questionnaire else False,
            "other_medical_conditions": questionnaire.other_medical_conditions if questionnaire else None,
        }

        template_days: list[dict[str, Any]] = []
        for day in template.days:
            day_blocks: list[dict[str, Any]] = []
            for block in day.blocks:
                block_exercises: list[dict[str, Any]] = []
                for entry in block.exercises:
                    ex = entry.exercise
                    block_exercises.append(
                        {
                            "original_exercise_id": entry.exercise_id,
                            "name": ex.name,
                            "category": ex.category,
                            "target_muscle_group": ex.target_muscle_group,
                            "equipment_needed": ex.equipment_needed,
                            "sets": entry.sets,
                            "reps": entry.reps,
                            "rest_seconds": entry.rest_seconds,
                            "contraindicated_zones": ex.contraindicated_zones or [],
                        }
                    )
                day_blocks.append(
                    {
                        "name": block.name,
                        "order_index": block.order_index,
                        "exercises": block_exercises,
                    }
                )
            template_days.append(
                {
                    "name": day.name,
                    "order_index": day.order_index,
                    "blocks": day_blocks,
                }
            )

        catalog: list[dict[str, Any]] = [
            {
                "exercise_id": ex.id,
                "name": ex.name,
                "category": ex.category,
                "target_muscle_group": ex.target_muscle_group,
                "equipment_needed": ex.equipment_needed,
                "description": ex.description,
                "contraindicated_zones": ex.contraindicated_zones or [],
            }
            for ex in trainer_exercises
            if ex.deleted_at is None and _conflicts_with_zones(ex, protected_zones) is None
        ]

        return {
            "student_training_context": {
                "fitness_goals": list(student.fitness_goals or []),
                "personal_motivation": student.personal_motivation,
                "protected_zones": [z.body_area for z in protected_zones],
                "health_restrictions": health_info,
            },
            "generic_routine_template": {
                "name": template.name,
                "duration_weeks": template.duration_weeks,
                "intensity": template.intensity,
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

        # Catálogo permitido de ejercicios activos del entrenador
        catalog_by_id: dict[str, Exercise] = {
            ex.id: ex for ex in trainer_exercises if ex.deleted_at is None
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
                    if t_entry.exercise.deleted_at is None:
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

                    if action == "REMOVE":
                        action_logs.append(f"[REMOVE] Eliminado '{orig_exercise.name}': {reason}")
                        continue

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
                        float(orig_entry_match.target_weight_kg)
                        if orig_entry_match and getattr(orig_entry_match, "target_weight_kg", None) is not None and action == "KEEP"
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
                    missing_names = [template_exercises_by_id[mid].name for mid in sorted(missing_in_block) if mid in template_exercises_by_id]
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
                    estimated_duration = getattr(t_blk, "estimated_duration_minutes", None) if t_blk else None
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

        student_name = f"{student.first_name or ''} {student.last_name or ''}".strip() or "el alumno"
        base_summary = (structured.adaptation_summary or "").strip()
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

        if questionnaire and questionnaire.has_risk_answers:
            summary_lines.append(
                "\n⚠️ Aviso importante: El alumno registra antecedentes en su declaración de salud. "
                "Esta propuesta no constituye consejo ni diagnóstico médico y no sustituye la evaluación de un profesional de salud."
            )
        summary_lines.append(
            "\n* Propuesta generada por IA en estado pendiente de revisión. Requiere aprobación manual del entrenador (Human-in-the-Loop)."
        )

        return AIRoutineProposalResult(
            name=f"{template.name} - Adaptada para {student_name}"[:150],
            duration_weeks=template.duration_weeks,
            intensity=intensity,
            adaptation_summary="\n".join(summary_lines),
            days=adapted_days,
            has_no_materials_alternative=getattr(template, "has_no_materials_alternative", False),
        )

    def generate_adapted_routine(
        self,
        template: RoutineTemplate,
        student: StudentProfile,
        questionnaire: HealthQuestionnaire | None,
        protected_zones: list[ProtectedZone],
        trainer_exercises: list[Exercise],
    ) -> AIRoutineProposalResult:
        client = self._get_client()
        prompt_payload = self._build_prompt_payload(
            template=template,
            student=student,
            questionnaire=questionnaire,
            protected_zones=protected_zones,
            trainer_exercises=trainer_exercises,
        )
        prompt_text = (
            "Analizá el siguiente contexto de entrenamiento y devolvé exclusivamente un objeto JSON "
            "que respete el esquema indicado, definiendo una acción explícita (KEEP, REPLACE o REMOVE) "
            "para cada ejercicio de la rutina genérica:\n\n"
            f"{json.dumps(prompt_payload, ensure_ascii=False)}"
        )

        logger.info("Invocando proveedor de IA 'gemini' con modelo '%s' para US-13.", self.model)

        try:
            response = client.models.generate_content(
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

        structured = self._extract_structured_response(response)
        return self._validate_and_build_proposal(
            structured=structured,
            template=template,
            student=student,
            questionnaire=questionnaire,
            protected_zones=protected_zones,
            trainer_exercises=trainer_exercises,
        )


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
