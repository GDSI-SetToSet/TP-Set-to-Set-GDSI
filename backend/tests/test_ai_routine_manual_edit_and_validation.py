import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from backend.src.models.exercise import Exercise
from backend.src.models.protected_zone import ProtectedZone
from backend.src.services.ai_routine_adapter import (
    AIRoutineAdapterError,
    GeminiAIRoutineAdapter,
    GeminiRoutineAdaptationSchema,
    HeuristicAIRoutineAdapter,
    find_safe_substitute,
    is_valid_reps_format,
    normalize_exercise_name,
)
from backend.tests.test_ai_routine_api import (
    AI_GENERATE_PATH,
    create_exercise,
    create_template,
    register_and_login,
    setup_trainer_and_student_relationship,
)


@pytest.fixture(autouse=True)
def _isolate_default_ai_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "heuristic")
    monkeypatch.delenv("AI_ROUTINE_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


# ==============================================================================
# 1. Tests para is_valid_reps_format (formatos de repeticiones y tiempo)
# ==============================================================================
def test_reps_format_validation():
    # Válidos estándar
    assert is_valid_reps_format("10")
    assert is_valid_reps_format("8-12")
    assert is_valid_reps_format("12 c/l")
    assert is_valid_reps_format("15c/l")
    assert is_valid_reps_format("8 a 10") is False  # no cumple regex de sufijo/rango
    assert is_valid_reps_format("10 reps")

    # Válidos por tiempo (isométricos / intervalos)
    assert is_valid_reps_format("30s")
    assert is_valid_reps_format("45s")
    assert is_valid_reps_format("60 seg")
    assert is_valid_reps_format("30 seg")
    assert is_valid_reps_format("20-30s")

    # Inválidos
    assert is_valid_reps_format("") is False
    assert is_valid_reps_format("   ") is False
    assert is_valid_reps_format("abc") is False
    assert is_valid_reps_format("hasta el fallo") is False
    assert is_valid_reps_format("-5") is False
    assert is_valid_reps_format("150") is False  # > 99
    assert is_valid_reps_format(None) is False


# ==============================================================================
# 2. Tests para normalize_exercise_name y find_safe_substitute
# ==============================================================================
def test_normalize_exercise_name():
    assert normalize_exercise_name("Sentadilla con Barra") == "sentadillaconbarra"
    assert normalize_exercise_name("Extensión de Cuádriceps") == "extensiondecuadriceps"
    assert normalize_exercise_name(" PRESS MILITAR ") == "pressmilitar"
    assert normalize_exercise_name("") == ""
    assert normalize_exercise_name(None) == ""


def test_find_safe_substitute_priorities_and_safety():
    orig = Exercise(
        id="ex-orig",
        name="Sentadilla Profunda",
        category="FUERZA",
        target_muscle_group="Piernas",
        contraindicated_zones=["Knee"],
        trainer_id="t1",
    )

    same_group_and_cat = Exercise(
        id="ex-safe-1",
        name="Prensa Inclinada",
        category="FUERZA",
        target_muscle_group="Piernas",
        contraindicated_zones=[],
        trainer_id="t1",
    )

    same_group_diff_cat = Exercise(
        id="ex-safe-2",
        name="Puente de Glúteos",
        category="MOVILIDAD",
        target_muscle_group="Piernas",
        contraindicated_zones=[],
        trainer_id="t1",
    )

    diff_group_safe = Exercise(
        id="ex-safe-3",
        name="Press Banca",
        category="FUERZA",
        target_muscle_group="Pecho",
        contraindicated_zones=[],
        trainer_id="t1",
    )

    contraindicated_cand = Exercise(
        id="ex-unsafe",
        name="Estocadas",
        category="FUERZA",
        target_muscle_group="Piernas",
        contraindicated_zones=["Knee"],
        trainer_id="t1",
    )

    catalog = [orig, same_group_and_cat, same_group_diff_cat, diff_group_safe, contraindicated_cand]

    # Prioridad 1: mismo grupo muscular y misma categoría, sin contraindicaciones
    sub = find_safe_substitute(orig, ["Knee"], catalog, exclude_ids={"ex-orig"})
    assert sub is not None
    assert sub.id == "ex-safe-1"

    # Si ex-safe-1 no está disponible, cae a prioridad 2 (mismo grupo muscular)
    sub2 = find_safe_substitute(orig, ["Knee"], catalog, exclude_ids={"ex-orig", "ex-safe-1"})
    assert sub2 is not None
    assert sub2.id == "ex-safe-2"

    # Nunca retorna el original ni un ejercicio contraindicado
    sub3 = find_safe_substitute(orig, ["Knee"], [orig, contraindicated_cand], exclude_ids={"ex-orig"})
    assert sub3 is None


# ==============================================================================
# 3. Tests para GeminiAIRoutineAdapter (validaciones de sustitución y seguridad)
# ==============================================================================
def test_gemini_adapter_rejects_substituting_with_same_exercise_id():
    adapter = GeminiAIRoutineAdapter(api_key="fake-key")

    gemini_json_response = {
        "intensity": "MEDIA",
        "adaptation_summary": "Intento inválido",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {
                                "original_exercise_id": "ex-orig",
                                "action": "REPLACE",
                                "replacement_exercise_id": "ex-orig",  # Mismo ID
                                "sets": 3,
                                "reps": "10",
                                "rest_seconds": 60,
                                "reason": "Intento de reemplazar por sí mismo",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    ex1 = Exercise(
        id="ex-orig",
        name="Sentadilla",
        category="FUERZA",
        target_muscle_group="Piernas",
        contraindicated_zones=["Knee"],
        trainer_id="t1",
    )

    day_mock = MagicMock()
    day_mock.name = "Día 1"
    day_mock.order_index = 0
    block_mock = MagicMock()
    block_mock.name = "Bloque 1"
    block_mock.order_index = 0
    item_mock = MagicMock()
    item_mock.exercise_id = ex1.id
    item_mock.exercise = ex1
    item_mock.order_index = 0
    item_mock.sets = 4
    item_mock.reps = "10"
    item_mock.rest_seconds = 60
    block_mock.exercises = [item_mock]
    day_mock.blocks = [block_mock]

    template = MagicMock(intensity="MEDIA", days=[day_mock])
    template.name = "Rutina Piernas"
    student = MagicMock(fitness_goals=[])
    protected_zone = ProtectedZone(id="pz-1", student_id="s1", body_area="Knee", created_at=datetime.now(UTC))

    structured = GeminiRoutineAdaptationSchema.model_validate(gemini_json_response)

    with pytest.raises(AIRoutineAdapterError) as exc_info:
        adapter._validate_and_build_proposal(
            structured=structured,
            template=template,
            student=student,
            questionnaire=None,
            protected_zones=[protected_zone],
            trainer_exercises=[ex1],
        )

    assert "mismo ejercicio (mismo ID)" in str(exc_info.value)


def test_gemini_adapter_rejects_substituting_with_same_normalized_name():
    adapter = GeminiAIRoutineAdapter(api_key="fake-key")

    gemini_json_response = {
        "intensity": "MEDIA",
        "adaptation_summary": "Intento inválido",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {
                                "original_exercise_id": "ex-orig",
                                "action": "REPLACE",
                                "replacement_exercise_id": "ex-dup",
                                "sets": 3,
                                "reps": "10",
                                "rest_seconds": 60,
                                "reason": "Intento con mismo nombre",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    ex1 = Exercise(
        id="ex-orig",
        name="Sentadilla con Barra",
        category="FUERZA",
        target_muscle_group="Piernas",
        contraindicated_zones=["Knee"],
        trainer_id="t1",
    )
    ex2 = Exercise(
        id="ex-dup",
        name="Sentadilla Con Barra",  # Mismo nombre normalizado
        category="FUERZA",
        target_muscle_group="Piernas",
        contraindicated_zones=[],
        trainer_id="t1",
    )

    day_mock = MagicMock()
    day_mock.name = "Día 1"
    day_mock.order_index = 0
    block_mock = MagicMock()
    block_mock.name = "Bloque 1"
    block_mock.order_index = 0
    item_mock = MagicMock()
    item_mock.exercise_id = ex1.id
    item_mock.exercise = ex1
    item_mock.order_index = 0
    item_mock.sets = 4
    item_mock.reps = "10"
    item_mock.rest_seconds = 60
    block_mock.exercises = [item_mock]
    day_mock.blocks = [block_mock]

    template = MagicMock(intensity="MEDIA", days=[day_mock])
    template.name = "Rutina Base"
    student = MagicMock(fitness_goals=[])
    protected_zone = ProtectedZone(id="pz-1", student_id="s1", body_area="Knee", created_at=datetime.now(UTC))

    structured = GeminiRoutineAdaptationSchema.model_validate(gemini_json_response)

    with pytest.raises(AIRoutineAdapterError) as exc_info:
        adapter._validate_and_build_proposal(
            structured=structured,
            template=template,
            student=student,
            questionnaire=None,
            protected_zones=[protected_zone],
            trainer_exercises=[ex1, ex2],
        )

    assert "variante con el mismo nombre" in str(exc_info.value)


def test_gemini_adapter_rejects_substituting_with_contraindicated_exercise():
    adapter = GeminiAIRoutineAdapter(api_key="fake-key")

    gemini_json_response = {
        "intensity": "MEDIA",
        "adaptation_summary": "Intento inválido",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {
                                "original_exercise_id": "ex-orig",
                                "action": "REPLACE",
                                "replacement_exercise_id": "ex-unsafe",
                                "sets": 3,
                                "reps": "10",
                                "rest_seconds": 60,
                                "reason": "Sustituto peligroso",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    ex1 = Exercise(
        id="ex-orig",
        name="Sentadilla con Barra",
        category="FUERZA",
        target_muscle_group="Piernas",
        contraindicated_zones=["Knee"],
        trainer_id="t1",
    )
    ex_unsafe = Exercise(
        id="ex-unsafe",
        name="Estocadas Profundas",
        category="FUERZA",
        target_muscle_group="Piernas",
        contraindicated_zones=["Knee"],  # También contraindicado!
        trainer_id="t1",
    )

    day_mock = MagicMock()
    day_mock.name = "Día 1"
    day_mock.order_index = 0
    block_mock = MagicMock()
    block_mock.name = "Bloque 1"
    block_mock.order_index = 0
    item_mock = MagicMock()
    item_mock.exercise_id = ex1.id
    item_mock.exercise = ex1
    item_mock.order_index = 0
    item_mock.sets = 4
    item_mock.reps = "10"
    item_mock.rest_seconds = 60
    block_mock.exercises = [item_mock]
    day_mock.blocks = [block_mock]

    template = MagicMock(intensity="MEDIA", days=[day_mock])
    template.name = "Rutina Base"
    student = MagicMock(fitness_goals=[])
    protected_zone = ProtectedZone(id="pz-1", student_id="s1", body_area="Knee", created_at=datetime.now(UTC))

    structured = GeminiRoutineAdaptationSchema.model_validate(gemini_json_response)

    with pytest.raises(AIRoutineAdapterError) as exc_info:
        adapter._validate_and_build_proposal(
            structured=structured,
            template=template,
            student=student,
            questionnaire=None,
            protected_zones=[protected_zone],
            trainer_exercises=[ex1, ex_unsafe],
        )

    assert "incompatible con la zona protegida" in str(exc_info.value)

def test_gemini_adapter_allows_same_exercise_in_multiple_days():
    """Valida a nivel unitario que el adaptador acepte un mismo ejercicio en múltiples días (ej. Plancha en Día 1 y Día 3)."""
    adapter = GeminiAIRoutineAdapter(api_key="fake-key")

    ex_squat = Exercise(
        id="ex-squat",
        name="Sentadilla",
        category="FUERZA",
        target_muscle_group="Piernas",
        contraindicated_zones=[],
        trainer_id="t1",
    )
    ex_plank = Exercise(
        id="ex-plank",
        name="Plancha Abdominal",
        category="FUERZA",
        target_muscle_group="Core",
        contraindicated_zones=[],
        trainer_id="t1",
    )

    day1_item_squat = MagicMock(exercise_id="ex-squat", exercise=ex_squat, order_index=0, sets=4, reps="10", rest_seconds=90, target_weight_kg=80.0)
    day1_item_plank = MagicMock(exercise_id="ex-plank", exercise=ex_plank, order_index=1, sets=3, reps="45s", rest_seconds=60, target_weight_kg=None)
    day1_block = MagicMock(name="Bloque 1", order_index=0, exercises=[day1_item_squat, day1_item_plank], estimated_duration_minutes=30)
    day1_mock = MagicMock(name="Día 1", order_index=0, blocks=[day1_block])

    day2_item_plank = MagicMock(exercise_id="ex-plank", exercise=ex_plank, order_index=0, sets=3, reps="60s", rest_seconds=60, target_weight_kg=None)
    day2_block = MagicMock(name="Bloque 1", order_index=0, exercises=[day2_item_plank], estimated_duration_minutes=15)
    day2_mock = MagicMock(name="Día 2", order_index=1, blocks=[day2_block])

    template = MagicMock(intensity="MEDIA", days=[day1_mock, day2_mock])
    template.name = "Rutina Multi-Día"
    student = MagicMock(first_name="Juan", last_name="Perez", fitness_goals=[])

    gemini_json_response = {
        "intensity": "MEDIA",
        "adaptation_summary": "Adaptación multi-día exitosa",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {
                                "original_exercise_id": "ex-squat",
                                "action": "KEEP",
                                "replacement_exercise_id": None,
                                "sets": 4,
                                "reps": "10",
                                "rest_seconds": 90,
                                "reason": "Conservado Día 1",
                            },
                            {
                                "original_exercise_id": "ex-plank",
                                "action": "KEEP",
                                "replacement_exercise_id": None,
                                "sets": 3,
                                "reps": "45s",
                                "rest_seconds": 60,
                                "reason": "Conservado Día 1 Core",
                            },
                        ],
                    }
                ],
            },
            {
                "name": "Día 2",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {
                                "original_exercise_id": "ex-plank",
                                "action": "KEEP",
                                "replacement_exercise_id": None,
                                "sets": 3,
                                "reps": "60s",
                                "rest_seconds": 60,
                                "reason": "Conservado Día 2 Core",
                            },
                        ],
                    }
                ],
            },
        ],
    }

    structured = GeminiRoutineAdaptationSchema.model_validate(gemini_json_response)
    result = adapter._validate_and_build_proposal(
        structured=structured,
        template=template,
        student=student,
        questionnaire=None,
        protected_zones=[],
        trainer_exercises=[ex_squat, ex_plank],
    )

    assert len(result.days) == 2
    assert len(result.days[0].blocks[0].exercises) == 2
    assert len(result.days[1].blocks[0].exercises) == 1
    assert result.days[0].blocks[0].exercises[0].exercise_id == "ex-squat"
    assert result.days[0].blocks[0].exercises[0].target_weight_kg == 80.0
    assert result.days[0].blocks[0].exercises[1].exercise_id == "ex-plank"
    assert result.days[1].blocks[0].exercises[0].exercise_id == "ex-plank"


def test_gemini_adapter_rejects_duplicate_decision_in_same_block():
    """Valida a nivel unitario que decisiones duplicadas dentro del mismo bloque se rechacen con GEMINI_DUPLICATE_DECISION."""
    adapter = GeminiAIRoutineAdapter(api_key="fake-key")

    ex1 = Exercise(
        id="ex-1",
        name="Press Banca",
        category="FUERZA",
        target_muscle_group="Pecho",
        contraindicated_zones=[],
        trainer_id="t1",
    )

    item1 = MagicMock(exercise_id="ex-1", exercise=ex1, order_index=0, sets=4, reps="10", rest_seconds=60, target_weight_kg=None)
    block = MagicMock(name="Bloque 1", order_index=0, exercises=[item1], estimated_duration_minutes=20)
    day = MagicMock(name="Día 1", order_index=0, blocks=[block])
    template = MagicMock(intensity="MEDIA", days=[day])
    template.name = "Rutina"
    student = MagicMock(first_name="Juan", last_name="Perez", fitness_goals=[])

    duplicate_in_block = {
        "intensity": "MEDIA",
        "adaptation_summary": "Duplicado en el mismo bloque",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {
                                "original_exercise_id": "ex-1",
                                "action": "KEEP",
                                "replacement_exercise_id": None,
                                "sets": 4,
                                "reps": "10",
                                "rest_seconds": 60,
                                "reason": "Decisión 1",
                            },
                            {
                                "original_exercise_id": "ex-1",
                                "action": "REMOVE",
                                "replacement_exercise_id": None,
                                "sets": None,
                                "reps": None,
                                "rest_seconds": None,
                                "reason": "Decisión 2 duplicada en el mismo bloque",
                            },
                        ],
                    }
                ],
            }
        ],
    }

    structured = GeminiRoutineAdaptationSchema.model_validate(duplicate_in_block)

    with pytest.raises(AIRoutineAdapterError) as exc_info:
        adapter._validate_and_build_proposal(
            structured=structured,
            template=template,
            student=student,
            questionnaire=None,
            protected_zones=[],
            trainer_exercises=[ex1],
        )

    assert exc_info.value.error_code == "GEMINI_DUPLICATE_DECISION"
    assert "decisiones duplicadas o contradictorias" in exc_info.value.detail

def test_gemini_adapter_rejects_omission_of_occurrence_in_second_day():
    """Caso 2: Mismo ejercicio presente en Día 1 y Día 2. Gemini devuelve decisión para Día 1 pero omite Día 2.
    La propuesta debe ser rechazada con GEMINI_INCOMPLETE_DECISIONS."""
    adapter = GeminiAIRoutineAdapter(api_key="fake-key")

    ex1 = Exercise(id="ex-1", name="Sentadilla", category="FUERZA", target_muscle_group="Piernas", contraindicated_zones=[], trainer_id="t1")
    ex_plank = Exercise(id="ex-plank", name="Plancha Abdominal", category="FUERZA", target_muscle_group="Core", contraindicated_zones=[], trainer_id="t1")
    ex2 = Exercise(id="ex-2", name="Peso Muerto", category="FUERZA", target_muscle_group="Espalda", contraindicated_zones=[], trainer_id="t1")

    day1_e1 = MagicMock(exercise_id="ex-1", exercise=ex1, order_index=0, sets=4, reps="10", rest_seconds=60, target_weight_kg=None)
    day1_e2 = MagicMock(exercise_id="ex-plank", exercise=ex_plank, order_index=1, sets=3, reps="30s", rest_seconds=60, target_weight_kg=None)
    day1_b = MagicMock(name="Principal", order_index=0, exercises=[day1_e1, day1_e2])
    day1 = MagicMock(name="Día 1", order_index=0, blocks=[day1_b])

    day2_e1 = MagicMock(exercise_id="ex-2", exercise=ex2, order_index=0, sets=4, reps="10", rest_seconds=60, target_weight_kg=None)
    day2_e2 = MagicMock(exercise_id="ex-plank", exercise=ex_plank, order_index=1, sets=3, reps="45s", rest_seconds=60, target_weight_kg=None)
    day2_b = MagicMock(name="Principal", order_index=0, exercises=[day2_e1, day2_e2])
    day2 = MagicMock(name="Día 2", order_index=1, blocks=[day2_b])

    template = MagicMock(name="Plantilla", intensity="MEDIA", days=[day1, day2])
    student = MagicMock(first_name="Juan", last_name="Perez", fitness_goals=[])

    # Gemini devuelve decisión para ex-1 y ex-plank en Día 1, pero solo para ex-2 en Día 2 (omite ex-plank)
    gemini_resp = {
        "intensity": "MEDIA",
        "adaptation_summary": "Omisión de plancha en Día 2",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Principal",
                        "exercises": [
                            {"original_exercise_id": "ex-1", "action": "KEEP", "sets": 4, "reps": "10", "rest_seconds": 60, "reason": "Día 1 ok"},
                            {"original_exercise_id": "ex-plank", "action": "KEEP", "sets": 3, "reps": "30s", "rest_seconds": 60, "reason": "Día 1 plancha"},
                        ],
                    }
                ],
            },
            {
                "name": "Día 2",
                "blocks": [
                    {
                        "name": "Principal",
                        "exercises": [
                            {"original_exercise_id": "ex-2", "action": "KEEP", "sets": 4, "reps": "10", "rest_seconds": 60, "reason": "Día 2 ok"},
                            # Omitido: ex-plank
                        ],
                    }
                ],
            },
        ],
    }

    structured = GeminiRoutineAdaptationSchema.model_validate(gemini_resp)
    with pytest.raises(AIRoutineAdapterError) as exc_info:
        adapter._validate_and_build_proposal(
            structured=structured,
            template=template,
            student=student,
            questionnaire=None,
            protected_zones=[],
            trainer_exercises=[ex1, ex2, ex_plank],
        )

    assert exc_info.value.error_code == "GEMINI_INCOMPLETE_DECISIONS"
    assert "incompleta" in exc_info.value.detail.lower()
    assert "Plancha Abdominal" in exc_info.value.detail


def test_gemini_adapter_rejects_duplicate_decision_for_same_occurrence():
    """Caso 3: Duplicación de decisión para la misma aparición (dos decisiones KEEP para el mismo ejercicio en el bloque).
    La propuesta debe ser rechazada con GEMINI_DUPLICATE_DECISION."""
    adapter = GeminiAIRoutineAdapter(api_key="fake-key")

    ex1 = Exercise(id="ex-1", name="Sentadilla", category="FUERZA", target_muscle_group="Piernas", contraindicated_zones=[], trainer_id="t1")
    item1 = MagicMock(exercise_id="ex-1", exercise=ex1, order_index=0, sets=4, reps="10", rest_seconds=60, target_weight_kg=None)
    block = MagicMock(name="Bloque 1", order_index=0, exercises=[item1])
    day = MagicMock(name="Día 1", order_index=0, blocks=[block])
    template = MagicMock(name="Plantilla", intensity="MEDIA", days=[day])
    student = MagicMock(first_name="Juan", last_name="Perez", fitness_goals=[])

    duplicate_decisions_payload = {
        "intensity": "MEDIA",
        "adaptation_summary": "Dos decisiones KEEP para la misma aparición",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {"original_exercise_id": "ex-1", "action": "KEEP", "sets": 4, "reps": "10", "rest_seconds": 60, "reason": "Decisión 1"},
                            {"original_exercise_id": "ex-1", "action": "KEEP", "sets": 4, "reps": "12", "rest_seconds": 60, "reason": "Decisión 2 duplicada"},
                        ],
                    }
                ],
            }
        ],
    }

    structured = GeminiRoutineAdaptationSchema.model_validate(duplicate_decisions_payload)
    with pytest.raises(AIRoutineAdapterError) as exc_info:
        adapter._validate_and_build_proposal(
            structured=structured,
            template=template,
            student=student,
            questionnaire=None,
            protected_zones=[],
            trainer_exercises=[ex1],
        )

    assert exc_info.value.error_code == "GEMINI_DUPLICATE_DECISION"
    assert "duplicadas o contradictorias" in exc_info.value.detail.lower()


def test_gemini_adapter_allows_same_exercise_in_different_blocks_of_same_day():
    """Caso 5: Mismo ejercicio presente en dos bloques diferentes del mismo día (ej. Plancha en Calentamiento y en Finisher).
    Ambas apariciones reciben decisiones válidas y la propuesta es aceptada."""
    adapter = GeminiAIRoutineAdapter(api_key="fake-key")

    ex_squat = Exercise(id="ex-squat", name="Sentadilla", category="FUERZA", target_muscle_group="Piernas", contraindicated_zones=[], trainer_id="t1")
    ex_plank = Exercise(id="ex-plank", name="Plancha Abdominal", category="FUERZA", target_muscle_group="Core", contraindicated_zones=[], trainer_id="t1")

    b1_e1 = MagicMock(exercise_id="ex-plank", exercise=ex_plank, order_index=0, sets=2, reps="30s", rest_seconds=45, target_weight_kg=None)
    block1 = MagicMock(name="Calentamiento", order_index=0, exercises=[b1_e1], estimated_duration_minutes=10)

    b2_e1 = MagicMock(exercise_id="ex-squat", exercise=ex_squat, order_index=0, sets=4, reps="8", rest_seconds=120, target_weight_kg=70.0)
    b2_e2 = MagicMock(exercise_id="ex-plank", exercise=ex_plank, order_index=1, sets=3, reps="45s", rest_seconds=60, target_weight_kg=None)
    block2 = MagicMock(name="Principal", order_index=1, exercises=[b2_e1, b2_e2], estimated_duration_minutes=40)

    day1 = MagicMock(name="Día 1", order_index=0, blocks=[block1, block2])
    template = MagicMock(name="Plantilla Bi-bloque", intensity="MEDIA", days=[day1])
    student = MagicMock(first_name="Juan", last_name="Perez", fitness_goals=[])

    gemini_resp = {
        "intensity": "MEDIA",
        "adaptation_summary": "Plancha en calentamiento y bloque principal",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Calentamiento",
                        "exercises": [
                            {"original_exercise_id": "ex-plank", "action": "KEEP", "sets": 2, "reps": "30s", "rest_seconds": 45, "reason": "Activación core"},
                        ],
                    },
                    {
                        "name": "Principal",
                        "exercises": [
                            {"original_exercise_id": "ex-squat", "action": "KEEP", "sets": 4, "reps": "8", "rest_seconds": 120, "reason": "Sentadilla pesada"},
                            {"original_exercise_id": "ex-plank", "action": "KEEP", "sets": 3, "reps": "45s", "rest_seconds": 60, "reason": "Finisher core"},
                        ],
                    },
                ],
            }
        ],
    }

    structured = GeminiRoutineAdaptationSchema.model_validate(gemini_resp)
    result = adapter._validate_and_build_proposal(
        structured=structured,
        template=template,
        student=student,
        questionnaire=None,
        protected_zones=[],
        trainer_exercises=[ex_squat, ex_plank],
    )

    assert len(result.days) == 1
    assert len(result.days[0].blocks) == 2
    assert len(result.days[0].blocks[0].exercises) == 1
    assert result.days[0].blocks[0].exercises[0].exercise_id == "ex-plank"
    assert result.days[0].blocks[0].exercises[0].reps == "30s"

    assert len(result.days[0].blocks[1].exercises) == 2
    assert result.days[0].blocks[1].exercises[0].exercise_id == "ex-squat"
    assert result.days[0].blocks[1].exercises[0].target_weight_kg == 70.0
    assert result.days[0].blocks[1].exercises[1].exercise_id == "ex-plank"
    assert result.days[0].blocks[1].exercises[1].reps == "45s"


def test_gemini_adapter_rejects_substitution_collision_in_same_block():
    """Caso 6: Dos ejercicios de un mismo bloque terminan sustituidos por el mismo ejercicio del catálogo.
    La propuesta debe ser rechazada con GEMINI_DUPLICATE_EXERCISE."""
    adapter = GeminiAIRoutineAdapter(api_key="fake-key")

    ex1 = Exercise(id="ex-1", name="Remo con Barra", category="FUERZA", target_muscle_group="Espalda", contraindicated_zones=[], trainer_id="t1")
    ex2 = Exercise(id="ex-2", name="Press Militar", category="FUERZA", target_muscle_group="Hombro", contraindicated_zones=[], trainer_id="t1")
    ex_sub = Exercise(id="ex-sub", name="Press Banca", category="FUERZA", target_muscle_group="Pecho", contraindicated_zones=[], trainer_id="t1")

    item1 = MagicMock(exercise_id="ex-1", exercise=ex1, order_index=0, sets=4, reps="10", rest_seconds=60, target_weight_kg=None)
    item2 = MagicMock(exercise_id="ex-2", exercise=ex2, order_index=1, sets=3, reps="10", rest_seconds=60, target_weight_kg=None)
    block = MagicMock(name="Bloque 1", order_index=0, exercises=[item1, item2])
    day = MagicMock(name="Día 1", order_index=0, blocks=[block])
    template = MagicMock(name="Plantilla", intensity="MEDIA", days=[day])
    student = MagicMock(first_name="Juan", last_name="Perez", fitness_goals=[])

    # Ambos ejercicios ex-1 y ex-2 reemplazados por ex-sub
    collision_payload = {
        "intensity": "MEDIA",
        "adaptation_summary": "Doble reemplazo hacia el mismo ejercicio",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {"original_exercise_id": "ex-1", "action": "REPLACE", "replacement_exercise_id": "ex-sub", "sets": 4, "reps": "10", "rest_seconds": 60, "reason": "Reemplazo 1"},
                            {"original_exercise_id": "ex-2", "action": "REPLACE", "replacement_exercise_id": "ex-sub", "sets": 3, "reps": "10", "rest_seconds": 60, "reason": "Reemplazo 2 duplicado"},
                        ],
                    }
                ],
            }
        ],
    }

    structured = GeminiRoutineAdaptationSchema.model_validate(collision_payload)
    with pytest.raises(AIRoutineAdapterError) as exc_info:
        adapter._validate_and_build_proposal(
            structured=structured,
            template=template,
            student=student,
            questionnaire=None,
            protected_zones=[],
            trainer_exercises=[ex1, ex2, ex_sub],
        )

    assert exc_info.value.error_code == "GEMINI_DUPLICATE_EXERCISE"
    assert "duplicado" in exc_info.value.detail.lower()


def test_gemini_adapter_preserves_independent_prescriptions_per_occurrence():
    """Caso 7: El mismo ejercicio aparece en dos días distintos con distintas cargas prescritas originales (80kg vs 100kg).
    Cada aparición debe conservar su propia prescripción original sin sobrescribirse."""
    adapter = GeminiAIRoutineAdapter(api_key="fake-key")

    ex_squat = Exercise(id="ex-squat", name="Sentadilla con Barra", category="FUERZA", target_muscle_group="Piernas", contraindicated_zones=[], trainer_id="t1")

    d1_e1 = MagicMock(exercise_id="ex-squat", exercise=ex_squat, order_index=0, sets=5, reps="5", rest_seconds=120, target_weight_kg=80.0)
    d1_b = MagicMock(name="Principal", order_index=0, exercises=[d1_e1])
    day1 = MagicMock(name="Día 1", order_index=0, blocks=[d1_b])

    d2_e1 = MagicMock(exercise_id="ex-squat", exercise=ex_squat, order_index=0, sets=3, reps="10", rest_seconds=90, target_weight_kg=100.0)
    d2_b = MagicMock(name="Principal", order_index=0, exercises=[d2_e1])
    day2 = MagicMock(name="Día 2", order_index=1, blocks=[d2_b])

    template = MagicMock(name="Plantilla Ondulada", intensity="ALTA", days=[day1, day2])
    student = MagicMock(first_name="Juan", last_name="Perez", fitness_goals=[])

    gemini_resp = {
        "intensity": "ALTA",
        "adaptation_summary": "Sentadilla en ambos días con distintas intensidades",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Principal",
                        "exercises": [
                            {"original_exercise_id": "ex-squat", "action": "KEEP", "sets": 5, "reps": "5", "rest_seconds": 120, "reason": "Fuerza pesada"},
                        ],
                    }
                ],
            },
            {
                "name": "Día 2",
                "blocks": [
                    {
                        "name": "Principal",
                        "exercises": [
                            {"original_exercise_id": "ex-squat", "action": "KEEP", "sets": 3, "reps": "10", "rest_seconds": 90, "reason": "Hipertrofia técnica"},
                        ],
                    }
                ],
            },
        ],
    }

    structured = GeminiRoutineAdaptationSchema.model_validate(gemini_resp)
    result = adapter._validate_and_build_proposal(
        structured=structured,
        template=template,
        student=student,
        questionnaire=None,
        protected_zones=[],
        trainer_exercises=[ex_squat],
    )

    assert len(result.days) == 2
    day1_ex = result.days[0].blocks[0].exercises[0]
    day2_ex = result.days[1].blocks[0].exercises[0]

    assert day1_ex.exercise_id == "ex-squat"
    assert day1_ex.target_weight_kg == 80.0
    assert day1_ex.sets == 5
    assert day1_ex.reps == "5"

    assert day2_ex.exercise_id == "ex-squat"
    assert day2_ex.target_weight_kg == 100.0
    assert day2_ex.sets == 3
    assert day2_ex.reps == "10"


# ==============================================================================
# 4. Tests para HeuristicAIRoutineAdapter (Determinismo)
# ==============================================================================
def test_heuristic_adapter_is_strictly_deterministic():
    ex1 = Exercise(
        id="ex-1",
        name="Sentadilla Profunda",
        category="FUERZA",
        target_muscle_group="Piernas",
        contraindicated_zones=["Knee"],
        trainer_id="t1",
    )
    ex2 = Exercise(
        id="ex-2",
        name="Puente de Glúteos",
        category="FUERZA",
        target_muscle_group="Glúteos",
        contraindicated_zones=[],
        trainer_id="t1",
    )

    day_mock = MagicMock()
    day_mock.name = "Día 1"
    day_mock.order_index = 0
    block_mock = MagicMock()
    block_mock.name = "Bloque A"
    block_mock.order_index = 0
    block_mock.estimated_duration_minutes = 20
    item_mock = MagicMock()
    item_mock.exercise = ex1
    item_mock.order_index = 0
    item_mock.sets = 4
    item_mock.reps = "10"
    item_mock.rest_seconds = 60
    item_mock.target_weight_kg = None
    block_mock.exercises = [item_mock]
    day_mock.blocks = [block_mock]

    tpl = MagicMock(
        intensity="EXIGENTE",
        duration_weeks=4,
        days=[day_mock],
    )
    tpl.name = "Rutina Base"

    student = MagicMock(
        first_name="Juan",
        last_name="Perez",
        fitness_goals=["Fuerza"],
    )

    pz = ProtectedZone(id="pz-1", student_id="s1", body_area="Knee", created_at=datetime.now(UTC))
    adapter = HeuristicAIRoutineAdapter()

    # Ejecutar 5 veces y comprobar idéntico resultado
    first_run = adapter.generate_adapted_routine(
        template=tpl,
        student=student,
        questionnaire=None,
        protected_zones=[pz],
        trainer_exercises=[ex1, ex2],
    )

    for _ in range(4):
        subsequent_run = adapter.generate_adapted_routine(
            template=tpl,
            student=student,
            questionnaire=None,
            protected_zones=[pz],
            trainer_exercises=[ex1, ex2],
        )
        assert first_run.name == subsequent_run.name
        assert first_run.intensity == subsequent_run.intensity
        assert first_run.adaptation_summary == subsequent_run.adaptation_summary
        assert len(first_run.days) == len(subsequent_run.days)
        assert (
            first_run.days[0].blocks[0].exercises[0].exercise_id
            == subsequent_run.days[0].blocks[0].exercises[0].exercise_id
        )
        assert (
            first_run.days[0].blocks[0].exercises[0].reps
            == subsequent_run.days[0].blocks[0].exercises[0].reps
        )


# ==============================================================================
# 5. Tests para edición manual vía PUT /api/v1/routines/assigned/{routine_id}
# ==============================================================================
def test_manual_editing_of_assigned_routine_full_flow(client):
    api, sessions = client
    trainer_headers = register_and_login(api, "coach_manual_edit@example.com", "TRAINER")
    student_headers = register_and_login(api, "student_manual_edit@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_manual_edit@example.com",
        "student_manual_edit@example.com",
        protected_zones=["Knee"],
        goals=["Hipertrofia"],
    )

    ex_safe1 = create_exercise(api, trainer_headers, name="Press Pecho", target_muscle_group="Pecho")
    ex_safe2 = create_exercise(api, trainer_headers, name="Remo con Barra", target_muscle_group="Espalda")
    ex_contra = create_exercise(
        api,
        trainer_headers,
        name="Sentadilla Profunda",
        target_muscle_group="Piernas",
        contraindicated_zones=["Knee"],
    )

    template = create_template(api, trainer_headers, [ex_safe1])

    # 1. Generar propuesta con IA
    gen_resp = api.post(
        AI_GENERATE_PATH,
        headers=trainer_headers,
        json={"student_id": student_id, "template_id": template["id"]},
    )
    assert gen_resp.status_code == 201
    routine_id = gen_resp.json()["id"]
    assert gen_resp.json()["status"] == "PENDING_REVIEW"

    # 2. Modificar manualmente la rutina:
    #    - Cambiar repeticiones a "30s" (tiempo)
    #    - Cambiar peso de null a 60.5 kg
    #    - Cambiar series a 5 y descanso a 90s
    #    - Agregar segundo ejercicio (ex_safe2)
    #    - Verificar que NO se llama a ningún adaptador de IA
    edit_payload = {
        "name": "Rutina Editada Personalizada",
        "duration_weeks": 6,
        "intensity": "ALTA",
        "has_no_materials_alternative": False,
        "days": [
            {
                "name": "Día A - Modificado",
                "blocks": [
                    {
                        "name": "Bloque Principal",
                        "estimated_duration_minutes": 45,
                        "exercises": [
                            {
                                "exercise_id": ex_safe1,
                                "sets": 5,
                                "reps": "30s",  # Prescripción por tiempo
                                "rest_seconds": 90,
                                "target_weight_kg": 60.5,
                                "adaptation_notes": "Ajuste manual de carga y tiempo",
                            },
                            {
                                "exercise_id": ex_safe2,
                                "sets": 3,
                                "reps": "8-12",
                                "rest_seconds": 60,
                                "target_weight_kg": 40.0,
                                "adaptation_notes": "Ejercicio añadido manualmente por el entrenador",
                            },
                        ],
                    }
                ],
            }
        ],
    }

    with patch("backend.src.services.ai_routine_adapter.HeuristicAIRoutineAdapter.generate_adapted_routine") as mock_heur:
        put_resp = api.put(
            f"/api/v1/routines/assigned/{routine_id}",
            headers=trainer_headers,
            json=edit_payload,
        )
        assert put_resp.status_code == 200
        # Comprobar que no se invocó ningún adaptador de IA
        mock_heur.assert_not_called()

    data = put_resp.json()
    assert data["name"] == "Rutina Editada Personalizada"
    assert data["duration_weeks"] == 6
    assert data["intensity"] == "ALTA"
    assert data["status"] == "PENDING_REVIEW"  # Permanece en revisión
    assert len(data["days"]) == 1
    assert data["days"][0]["name"] == "Día A - Modificado"
    assert len(data["days"][0]["blocks"][0]["exercises"]) == 2

    ex1_data = data["days"][0]["blocks"][0]["exercises"][0]
    assert ex1_data["sets"] == 5
    assert ex1_data["reps"] == "30s"
    assert ex1_data["rest_seconds"] == 90
    assert ex1_data["target_weight_kg"] == 60.5
    assert ex1_data["adaptation_notes"] == "Ajuste manual de carga y tiempo"

    # 3. Intentar agregar un ejercicio contraindicado para el alumno: debe ser rechazado con 422
    bad_payload = {
        **edit_payload,
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {
                                "exercise_id": ex_contra,  # Contraindicado para Knee
                                "sets": 3,
                                "reps": "10",
                                "rest_seconds": 60,
                            }
                        ],
                    }
                ],
            }
        ],
    }

    bad_resp = api.put(
        f"/api/v1/routines/assigned/{routine_id}",
        headers=trainer_headers,
        json=bad_payload,
    )
    assert bad_resp.status_code == 422
    assert "contraindicado para la zona protegida" in bad_resp.json()["detail"].lower()

    # 4. Aprobar la rutina editada
    approve_resp = api.post(f"/api/v1/routines/assigned/{routine_id}/approve", headers=trainer_headers)
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "APPROVED"

    # Comprobar que el alumno ve la rutina aprobada y sincronizada
    student_resp = api.get("/api/v1/students/me/assigned-routine", headers=student_headers)
    assert student_resp.status_code == 200
    student_data = student_resp.json()
    assert student_data["name"] == "Rutina Editada Personalizada"
    assert student_data["days"][0]["blocks"][0]["exercises"][0]["reps"] == "30s"

    # 5. Modificar manualmente una rutina que ya estaba aprobada: sincroniza con StudentRoutine
    update_after_approval_payload = {
        **edit_payload,
        "name": "Rutina Actualizada Post-Aprobación",
    }
    update_post_resp = api.put(
        f"/api/v1/routines/assigned/{routine_id}",
        headers=trainer_headers,
        json=update_after_approval_payload,
    )
    assert update_post_resp.status_code == 200
    assert update_post_resp.json()["name"] == "Rutina Actualizada Post-Aprobación"

    # Verificar sincronización inmediata en la vista del alumno
    student_resp2 = api.get("/api/v1/students/me/assigned-routine", headers=student_headers)
    assert student_resp2.status_code == 200
    assert student_resp2.json()["name"] == "Rutina Actualizada Post-Aprobación"


def test_manual_editing_unauthorized_trainer_rejected(client):
    api, sessions = client
    trainer1_headers = register_and_login(api, "coach1_auth@example.com", "TRAINER")
    trainer2_headers = register_and_login(api, "coach2_auth@example.com", "TRAINER")
    register_and_login(api, "student_auth_test@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach1_auth@example.com",
        "student_auth_test@example.com",
    )

    ex = create_exercise(api, trainer1_headers, name="Curl Bíceps", target_muscle_group="Brazos")
    template = create_template(api, trainer1_headers, [ex])

    gen_resp = api.post(
        AI_GENERATE_PATH,
        headers=trainer1_headers,
        json={"student_id": student_id, "template_id": template["id"]},
    )
    routine_id = gen_resp.json()["id"]

    # Entrenador 2 intenta editar la rutina del Entrenador 1: debe rechazarse con 404
    put_resp = api.put(
        f"/api/v1/routines/assigned/{routine_id}",
        headers=trainer2_headers,
        json={
            "name": "Hack",
            "duration_weeks": 4,
            "intensity": "MEDIA",
            "days": [
                {
                    "name": "Día 1",
                    "blocks": [
                        {
                            "name": "Bloque 1",
                            "exercises": [{"exercise_id": ex, "sets": 3, "reps": "10", "rest_seconds": 60}],
                        }
                    ],
                }
            ],
        },
    )
    assert put_resp.status_code == 404


# ==============================================================================
# 6. Tests de endurecimiento del motor de IA (Secciones 4.1, 4.2, 4.3, 3.7 y 3.8)
# ==============================================================================


def test_functional_equivalence_rejects_incoherent_cross_region_substitutions():
    """4.1: Verifica que ejercicios seguros pero funcionalmente incompatibles (ej. Sentadilla -> Plancha o Press Banca)
    sean rechazados por evaluate_functional_equivalence y find_safe_substitute."""
    from backend.src.services.ai_routine_adapter import (
        evaluate_functional_equivalence,
        find_compatible_substitutes,
        infer_exercise_biomechanics,
    )

    squat = Exercise(
        id="ex-squat",
        name="Sentadilla con Barra",
        category="FUERZA",
        target_muscle_group="Cuádriceps",
        equipment_needed="Barra y rack",
        contraindicated_zones=["Knee", "Lower back"],
        trainer_id="t1",
    )
    plank = Exercise(
        id="ex-plank",
        name="Plancha Abdominal",
        category="FUERZA",
        target_muscle_group="Core",
        equipment_needed="Ninguno",
        contraindicated_zones=[],
        has_no_materials_alternative=True,
        trainer_id="t1",
    )
    bench = Exercise(
        id="ex-bench",
        name="Press de Banca",
        category="FUERZA",
        target_muscle_group="Pectoral",
        equipment_needed="Barra y banco",
        contraindicated_zones=[],
        trainer_id="t1",
    )
    row = Exercise(
        id="ex-row",
        name="Remo con Barra",
        category="FUERZA",
        target_muscle_group="Dorsales",
        equipment_needed="Barra",
        contraindicated_zones=[],
        trainer_id="t1",
    )
    treadmill = Exercise(
        id="ex-cardio",
        name="Caminata en Cinta",
        category="CARDIO",
        target_muscle_group="Sistema cardiovascular",
        equipment_needed="Cinta",
        contraindicated_zones=[],
        trainer_id="t1",
    )

    assert infer_exercise_biomechanics(squat).movement_pattern == "KNEE_DOMINANT"
    assert infer_exercise_biomechanics(plank).movement_pattern == "CORE_STABILITY"
    assert infer_exercise_biomechanics(bench).movement_pattern == "HORIZONTAL_PUSH"
    assert infer_exercise_biomechanics(row).movement_pattern == "HORIZONTAL_PULL"
    assert infer_exercise_biomechanics(treadmill).movement_pattern == "LOCOMOTION_CARDIO"

    for incompatible_cand in (plank, bench, row, treadmill):
        is_compat, priority, reasons = evaluate_functional_equivalence(squat, incompatible_cand)
        assert is_compat is False
        assert priority == 99
        assert any("incompatible" in r for r in reasons)

    # Si en el catálogo solo hay ejercicios seguros de core/pecho/espalda/cardio, NO debe sustituir Sentadilla por ninguno
    incoherent_catalog = [squat, plank, bench, row, treadmill]
    assert find_safe_substitute(squat, ["Knee"], incoherent_catalog) is None
    assert find_compatible_substitutes(squat, ["Knee"], incoherent_catalog) == []


def test_functional_equivalence_prioritizes_same_pattern_muscle_and_equipment_constraints():
    """4.1: Verifica sustituciones válidas (mismo patrón + grupo muscular, equipamiento alternativo y filtro Sin materiales)."""
    from backend.src.services.ai_routine_adapter import find_compatible_substitutes

    orig_row = Exercise(
        id="ex-row-bar",
        name="Remo con Barra",
        category="FUERZA",
        target_muscle_group="Dorsales",
        equipment_needed="Barra",
        contraindicated_zones=["Lower back"],
        has_no_materials_alternative=False,
        trainer_id="t1",
    )
    sub_row_db = Exercise(
        id="ex-row-db",
        name="Remo Unilateral con Mancuerna",
        category="FUERZA",
        target_muscle_group="Dorsales",
        equipment_needed="Mancuerna y banco",
        contraindicated_zones=[],
        has_no_materials_alternative=False,
        trainer_id="t1",
    )
    sub_row_band = Exercise(
        id="ex-row-band",
        name="Remo con Banda Elástica",
        category="FUERZA",
        target_muscle_group="Dorsales",
        equipment_needed="Banda elástica",
        contraindicated_zones=[],
        has_no_materials_alternative=True,
        trainer_id="t1",
    )
    sub_lat_pulldown = Exercise(
        id="ex-pulldown",
        name="Jalón al Pecho en Polea",
        category="FUERZA",
        target_muscle_group="Dorsales",
        equipment_needed="Polea alta",
        contraindicated_zones=[],
        has_no_materials_alternative=False,
        trainer_id="t1",
    )
    unsafe_deadlift = Exercise(
        id="ex-dl",
        name="Peso Muerto",
        category="FUERZA",
        target_muscle_group="Dorsales",
        equipment_needed="Barra",
        contraindicated_zones=["Lower back"],
        has_no_materials_alternative=False,
        trainer_id="t1",
    )

    catalog = [orig_row, sub_lat_pulldown, sub_row_db, sub_row_band, unsafe_deadlift]

    # 1) Sin restricción de materiales: prioriza mismo patrón HORIZONTAL_PULL + Dorsales (tier 1) sobre VERTICAL_PULL (tier 3)
    matches = find_compatible_substitutes(orig_row, ["Lower back"], catalog, require_no_materials=False)
    matched_ids = [m[0].id for m in matches]
    assert "ex-dl" not in matched_ids  # Excluido por zona protegida Lower back
    assert matched_ids[:2] == ["ex-row-db", "ex-row-band"] or set(matched_ids[:2]) == {"ex-row-db", "ex-row-band"}
    assert matched_ids[-1] == "ex-pulldown"  # Tracción vertical queda después de tracción horizontal

    # 2) Con requisito 'Sin materiales' (require_no_materials=True): solo devuelve candidatos con has_no_materials_alternative=True
    no_mat_matches = find_compatible_substitutes(orig_row, ["Lower back"], catalog, require_no_materials=True)
    assert len(no_mat_matches) == 1
    assert no_mat_matches[0][0].id == "ex-row-band"
    assert "no_materials_verified" in no_mat_matches[0][2]


def test_heuristic_adapter_order_independent_determinism_and_traceability():
    """4.1 y 3.7: Verifica que el adaptador heurístico produzca el mismo resultado aunque cambie el orden del catálogo,
    y que registre la trazabilidad completa de sustituciones (SubstitutionTraceEntry)."""
    ex_squat = Exercise(
        id="ex-squat",
        name="Sentadilla con Barra",
        category="FUERZA",
        target_muscle_group="Cuádriceps",
        equipment_needed="Barra",
        contraindicated_zones=["Knee"],
        trainer_id="t1",
    )
    ex_glute_bridge = Exercise(
        id="ex-bridge",
        name="Puente de Glúteos en Suelo",
        category="FUERZA",
        target_muscle_group="Glúteos",
        equipment_needed="Colchoneta",
        contraindicated_zones=[],
        trainer_id="t1",
    )
    ex_hip_thrust = Exercise(
        id="ex-hip",
        name="Hip Thrust con Barra",
        category="FUERZA",
        target_muscle_group="Glúteos",
        equipment_needed="Barra",
        contraindicated_zones=[],
        trainer_id="t1",
    )
    ex_plank = Exercise(
        id="ex-plank",
        name="Plancha Abdominal",
        category="FUERZA",
        target_muscle_group="Core",
        equipment_needed="Ninguno",
        contraindicated_zones=[],
        trainer_id="t1",
    )

    item1 = MagicMock(exercise=ex_squat, exercise_id="ex-squat", order_index=0, sets=4, reps="8", rest_seconds=90, target_weight_kg=80.0)
    item2 = MagicMock(exercise=ex_plank, exercise_id="ex-plank", order_index=1, sets=3, reps="45s", rest_seconds=60, target_weight_kg=None)
    blk = MagicMock(name="Principal", order_index=0, estimated_duration_minutes=30, exercises=[item1, item2])
    day = MagicMock(name="Día 1", order_index=0, blocks=[blk])
    tpl = MagicMock(intensity="ALTA", duration_weeks=4, has_no_materials_alternative=False, days=[day])
    tpl.name = "Plantilla Tren Inferior"
    student = MagicMock(first_name="Lucía", last_name="Gómez", fitness_goals=["FUERZA"])
    pz = ProtectedZone(id="pz-1", student_id="s1", body_area="Knee", created_at=datetime.now(UTC))

    adapter = HeuristicAIRoutineAdapter()
    res_order_a = adapter.generate_adapted_routine(
        template=tpl,
        student=student,
        questionnaire=None,
        protected_zones=[pz],
        trainer_exercises=[ex_squat, ex_glute_bridge, ex_hip_thrust, ex_plank],
    )
    res_order_b = adapter.generate_adapted_routine(
        template=tpl,
        student=student,
        questionnaire=None,
        protected_zones=[pz],
        trainer_exercises=[ex_plank, ex_hip_thrust, ex_glute_bridge, ex_squat],
    )

    assert res_order_a.days[0].blocks[0].exercises[0].exercise_id == res_order_b.days[0].blocks[0].exercises[0].exercise_id
    # Prefiere Hip Thrust con Barra sobre Puente en Suelo porque comparte equipment_type BARBELL con Sentadilla con Barra
    assert res_order_a.days[0].blocks[0].exercises[0].exercise_id == "ex-hip"
    assert len(res_order_a.substitutions_trace) == 2

    replace_trace = res_order_a.substitutions_trace[0]
    assert replace_trace.action == "REPLACE"
    assert replace_trace.engine == "heuristic"
    assert replace_trace.original_exercise_id == "ex-squat"
    assert replace_trace.selected_exercise_id == "ex-hip"
    assert replace_trace.trigger_condition == "knee"
    assert "safety_zones_verified" in replace_trace.compatibility_criteria

    keep_trace = res_order_a.substitutions_trace[1]
    assert keep_trace.action == "KEEP"
    assert keep_trace.original_exercise_id == "ex-plank"
    assert keep_trace.selected_exercise_id == "ex-plank"


def test_gemini_adapter_rejects_incoherent_substitute_outside_functional_equivalence():
    """4.2: Si Gemini propone reemplazar Sentadilla por Plancha Abdominal (segura pero funcionalmente incompatible),
    el backend rechaza la propuesta con GEMINI_INVALID_SUBSTITUTE."""
    adapter = GeminiAIRoutineAdapter(api_key="fake-key")

    ex_squat = Exercise(
        id="ex-squat",
        name="Sentadilla con Barra",
        category="FUERZA",
        target_muscle_group="Cuádriceps",
        contraindicated_zones=["Knee"],
        trainer_id="t1",
    )
    ex_plank = Exercise(
        id="ex-plank",
        name="Plancha Abdominal",
        category="FUERZA",
        target_muscle_group="Core",
        contraindicated_zones=[],
        trainer_id="t1",
    )

    item1 = MagicMock(exercise_id="ex-squat", exercise=ex_squat, order_index=0, sets=4, reps="8", rest_seconds=90, target_weight_kg=None)
    blk = MagicMock(name="Principal", order_index=0, exercises=[item1])
    day = MagicMock(name="Día 1", order_index=0, blocks=[blk])
    template = MagicMock(intensity="MEDIA", duration_weeks=4, has_no_materials_alternative=False, days=[day])
    template.name = "Plantilla Piernas"
    student = MagicMock(first_name="Ana", last_name="Torres", fitness_goals=["FUERZA"])
    pz = ProtectedZone(id="pz-k", student_id="s1", body_area="Knee", created_at=datetime.now(UTC))

    bad_replace_payload = {
        "intensity": "MEDIA",
        "adaptation_summary": "Intento de sustituir sentadilla por plancha.",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Principal",
                        "exercises": [
                            {
                                "original_exercise_id": "ex-squat",
                                "action": "REPLACE",
                                "replacement_exercise_id": "ex-plank",
                                "sets": 3,
                                "reps": "45s",
                                "rest_seconds": 60,
                                "reason": "Plancha no duele la rodilla.",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    structured = GeminiRoutineAdaptationSchema.model_validate(bad_replace_payload)
    with pytest.raises(AIRoutineAdapterError) as exc_info:
        adapter._validate_and_build_proposal(
            structured=structured,
            template=template,
            student=student,
            questionnaire=None,
            protected_zones=[pz],
            trainer_exercises=[ex_squat, ex_plank],
        )

    assert exc_info.value.error_code == "GEMINI_INVALID_SUBSTITUTE"
    assert "funcionalmente incompatible" in exc_info.value.detail.lower()


def test_gemini_bounded_retry_succeeds_on_second_attempt_with_corrective_feedback():
    """3.6 y 4.2: Cuando el primer intento de Gemini falla por un error corregible de validación
    (ej. JSON inválido o sustituto incompatible), se realiza exactamente 1 reintento con feedback correctivo
    y si el segundo intento es válido se devuelve la rutina con retries_count == 1."""
    from types import SimpleNamespace

    from backend.src.services.ai_routine_adapter import (
        get_ai_metrics_snapshot,
        reset_ai_metrics,
    )

    reset_ai_metrics()

    ex_squat = Exercise(
        id="ex-squat",
        name="Sentadilla con Barra",
        category="FUERZA",
        target_muscle_group="Cuádriceps",
        equipment_needed="Barra",
        contraindicated_zones=["Knee"],
        trainer_id="t1",
    )
    ex_plank = Exercise(
        id="ex-plank",
        name="Plancha Abdominal",
        category="FUERZA",
        target_muscle_group="Core",
        equipment_needed="Ninguno",
        contraindicated_zones=[],
        trainer_id="t1",
    )
    ex_hip = Exercise(
        id="ex-hip",
        name="Hip Thrust con Barra",
        category="FUERZA",
        target_muscle_group="Glúteos",
        equipment_needed="Barra",
        contraindicated_zones=[],
        trainer_id="t1",
    )

    item1 = MagicMock(exercise_id="ex-squat", exercise=ex_squat, order_index=0, sets=4, reps="8", rest_seconds=90, target_weight_kg=60.0)
    blk = MagicMock(name="Principal", order_index=0, estimated_duration_minutes=35, exercises=[item1])
    day = MagicMock(name="Día 1", order_index=0, blocks=[blk])
    template = MagicMock(intensity="ALTA", duration_weeks=6, has_no_materials_alternative=False, days=[day])
    template.name = "Plantilla Piernas"
    student = MagicMock(first_name="Mateo", last_name="Gómez", fitness_goals=["FUERZA"], personal_motivation="Ganar fuerza")
    pz = ProtectedZone(id="pz-1", student_id="s1", body_area="Knee", created_at=datetime.now(UTC))

    # Intento 1: propone Plancha (incompatible con Sentadilla -> GEMINI_INVALID_SUBSTITUTE)
    attempt1_payload = {
        "intensity": "ALTA",
        "adaptation_summary": "Intento 1 fallido",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Principal",
                        "exercises": [
                            {
                                "original_exercise_id": "ex-squat",
                                "action": "REPLACE",
                                "replacement_exercise_id": "ex-plank",
                                "sets": 4,
                                "reps": "30s",
                                "rest_seconds": 60,
                                "reason": "Intento incoherente.",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    # Intento 2: corrige eligiendo ex-hip (presente en allowed_replacement_exercise_ids)
    attempt2_payload = {
        "intensity": "ALTA",
        "adaptation_summary": "Sustitución biomecánicamente equivalente en tren inferior.",
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Principal",
                        "exercises": [
                            {
                                "original_exercise_id": "ex-squat",
                                "action": "REPLACE",
                                "replacement_exercise_id": "ex-hip",
                                "sets": 4,
                                "reps": "8",
                                "rest_seconds": 90,
                                "reason": "Sustituido por Hip Thrust para proteger rodilla manteniendo trabajo de tren inferior.",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [
        SimpleNamespace(text=json.dumps(attempt1_payload), parsed=None),
        SimpleNamespace(text=json.dumps(attempt2_payload), parsed=None),
    ]

    adapter = GeminiAIRoutineAdapter(api_key="fake-key", model="gemini-3.5-flash-lite", client=mock_client, max_retries=1)
    result = adapter.generate_adapted_routine(
        template=template,
        student=student,
        questionnaire=None,
        protected_zones=[pz],
        trainer_exercises=[ex_squat, ex_plank, ex_hip],
    )

    assert mock_client.models.generate_content.call_count == 2
    second_call_prompt = mock_client.models.generate_content.call_args_list[1].kwargs["contents"]
    assert "CORRECCIÓN OBLIGATORIA (REINTENTO 1/1)" in second_call_prompt
    assert "GEMINI_INVALID_SUBSTITUTE" in second_call_prompt

    assert result.days[0].blocks[0].exercises[0].exercise_id == "ex-hip"
    assert result.metrics["retries_count"] == 1
    assert result.metrics["success"] is True

    snap = get_ai_metrics_snapshot()
    assert snap["total_requests"] == 1
    assert snap["successful_requests"] == 1
    assert snap["total_retries"] == 1
    assert snap["success_rate"] == 1.0


def test_gemini_bounded_retry_exhausted_fails_after_two_attempts_and_never_retries_429_or_504():
    """3.6 y 4.2: Verifica que:
    1) Cuando el reintento también falla, se aborta tras exactamente 2 llamadas con error controlado.
    2) Errores no corregibles (429 cuota, 504 timeout, 503 no disponible, o falta de candidatos en catálogo) NO se reintentan."""
    from types import SimpleNamespace

    from google.genai import errors as genai_errors

    from backend.src.services.ai_routine_adapter import (
        get_ai_metrics_snapshot,
        reset_ai_metrics,
    )

    reset_ai_metrics()

    ex_row = Exercise(
        id="ex-row",
        name="Remo con Barra",
        category="FUERZA",
        target_muscle_group="Dorsales",
        contraindicated_zones=[],
        trainer_id="t1",
    )
    item1 = MagicMock(exercise_id="ex-row", exercise=ex_row, order_index=0, sets=4, reps="10", rest_seconds=60, target_weight_kg=None)
    blk = MagicMock(name="Principal", order_index=0, estimated_duration_minutes=25, exercises=[item1])
    day = MagicMock(name="Día 1", order_index=0, blocks=[blk])
    template = MagicMock(intensity="MEDIA", duration_weeks=4, has_no_materials_alternative=False, days=[day])
    template.name = "Plantilla Espalda"
    student = MagicMock(first_name="Juan", last_name="Perez", fitness_goals=["FUERZA"], personal_motivation=None)

    # Caso 1: JSON inválido en ambos intentos -> exactamente 2 llamadas
    mock_client_json = MagicMock()
    mock_client_json.models.generate_content.return_value = SimpleNamespace(text="{bad json", parsed=None)
    adapter = GeminiAIRoutineAdapter(api_key="fake-key", model="gemini-3.5-flash-lite", client=mock_client_json, max_retries=1)

    with pytest.raises(AIRoutineAdapterError) as exc_info:
        adapter.generate_adapted_routine(template, student, None, [], [ex_row])
    assert exc_info.value.error_code == "GEMINI_INVALID_JSON"
    assert mock_client_json.models.generate_content.call_count == 2

    # Caso 2: Error 429 Quota Exceeded -> NO reintenta (1 sola llamada)
    mock_client_429 = MagicMock()
    mock_client_429.models.generate_content.side_effect = genai_errors.ClientError(
        429, {"error": {"message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}}
    )
    adapter_429 = GeminiAIRoutineAdapter(api_key="fake-key", model="gemini-3.5-flash-lite", client=mock_client_429, max_retries=1)
    with pytest.raises(AIRoutineAdapterError) as exc_429:
        adapter_429.generate_adapted_routine(template, student, None, [], [ex_row])
    assert exc_429.value.status_code == 429
    assert exc_429.value.error_code == "GEMINI_QUOTA_EXCEEDED"
    assert mock_client_429.models.generate_content.call_count == 1

    # Caso 3: Catálogo sin ningún ejercicio seguro para las restricciones -> aborta en pre-filtro con 422 (0 llamadas a Gemini)
    ex_unsafe = Exercise(
        id="ex-unsafe",
        name="Sentadilla con Barra",
        category="FUERZA",
        target_muscle_group="Cuádriceps",
        contraindicated_zones=["Knee"],
        trainer_id="t1",
    )
    item_u = MagicMock(exercise_id="ex-unsafe", exercise=ex_unsafe, order_index=0, sets=4, reps="8", rest_seconds=90, target_weight_kg=None)
    blk_u = MagicMock(name="Principal", order_index=0, exercises=[item_u])
    day_u = MagicMock(name="Día 1", order_index=0, blocks=[blk_u])
    tpl_u = MagicMock(intensity="MEDIA", duration_weeks=4, has_no_materials_alternative=False, days=[day_u])
    tpl_u.name = "Plantilla Solo Sentadilla"
    pz_knee = ProtectedZone(id="pz-k", student_id="s1", body_area="Knee", created_at=datetime.now(UTC))

    mock_client_prefilter = MagicMock()
    adapter_prefilter = GeminiAIRoutineAdapter(api_key="fake-key", model="gemini-3.5-flash-lite", client=mock_client_prefilter, max_retries=1)
    with pytest.raises(AIRoutineAdapterError) as exc_no_safe:
        adapter_prefilter.generate_adapted_routine(tpl_u, student, None, [pz_knee], [ex_unsafe])
    assert exc_no_safe.value.status_code == 422
    assert exc_no_safe.value.error_code == "NO_SAFE_EXERCISES_AVAILABLE"
    assert mock_client_prefilter.models.generate_content.call_count == 0

    snap = get_ai_metrics_snapshot()
    assert snap["failed_requests"] == 3
    assert "GEMINI_INVALID_JSON" in snap["errors_by_category"]
    assert "GEMINI_QUOTA_EXCEEDED" in snap["errors_by_category"]
    assert "NO_SAFE_EXERCISES_AVAILABLE" in snap["errors_by_category"]


def test_four_category_routine_validations_structure_quantities_semantics_integrity():
    """3.3 y 4.3: Verifica separadamente las 4 categorías de validación:
    A. Estructural, B. Cuantitativa, C. Semántica, D. Integridad."""
    from backend.src.services.ai_routine_adapter import (
        AdaptedBlockData,
        AdaptedDayData,
        AdaptedExerciseData,
        AIRoutineProposalResult,
        SubstitutionTraceEntry,
        validate_generated_routine_proposal,
        validate_routine_integrity,
        validate_routine_quantities,
        validate_routine_semantics,
        validate_routine_structure,
    )

    ex_valid = Exercise(
        id="ex-1",
        name="Press de Banca",
        category="FUERZA",
        target_muscle_group="Pectoral",
        contraindicated_zones=[],
        has_no_materials_alternative=True,
        trainer_id="t1",
    )
    ex_valid_2 = Exercise(
        id="ex-2",
        name="Flexiones de Brazos",
        category="FUERZA",
        target_muscle_group="Pectoral",
        contraindicated_zones=[],
        has_no_materials_alternative=True,
        trainer_id="t1",
    )
    ex_incoherent = Exercise(
        id="ex-plank",
        name="Plancha Abdominal",
        category="FUERZA",
        target_muscle_group="Core",
        contraindicated_zones=[],
        has_no_materials_alternative=True,
        trainer_id="t1",
    )

    item1 = MagicMock(exercise_id="ex-1", exercise=ex_valid, order_index=0, sets=4, reps="10", rest_seconds=60)
    blk_t = MagicMock(name="Bloque 1", order_index=0, exercises=[item1])
    day_t = MagicMock(name="Día 1", order_index=0, blocks=[blk_t])
    template = MagicMock(name="Plantilla", duration_weeks=4, intensity="MEDIA", has_no_materials_alternative=False, days=[day_t])

    def _make_valid_proposal() -> AIRoutineProposalResult:
        return AIRoutineProposalResult(
            name="Rutina Válida",
            duration_weeks=4,
            intensity="MEDIA",
            adaptation_summary="Resumen válido",
            days=[
                AdaptedDayData(
                    name="Día 1",
                    order_index=0,
                    blocks=[
                        AdaptedBlockData(
                            name="Bloque 1",
                            order_index=0,
                            exercises=[
                                AdaptedExerciseData(
                                    exercise_id="ex-1",
                                    order_index=0,
                                    sets=4,
                                    reps="10",
                                    rest_seconds=60,
                                )
                            ],
                        )
                    ],
                )
            ],
        )

    # 0. Propuesta válida supera las 4 validaciones
    valid_prop = _make_valid_proposal()
    validate_generated_routine_proposal(valid_prop, template, [ex_valid, ex_valid_2], [])

    # A. Validación estructural: rutina sin días o con bloque vacío -> rechazada
    empty_days_prop = _make_valid_proposal()
    empty_days_prop.days = []
    with pytest.raises(AIRoutineAdapterError) as exc_empty:
        validate_routine_structure(empty_days_prop)
    assert exc_empty.value.error_code == "EMPTY_ROUTINE_GENERATED"

    empty_block_prop = _make_valid_proposal()
    empty_block_prop.days[0].blocks[0].exercises = []
    with pytest.raises(AIRoutineAdapterError) as exc_blk:
        validate_routine_structure(empty_block_prop)
    assert exc_blk.value.error_code == "INVALID_ROUTINE_STRUCTURE"

    blank_id_prop = _make_valid_proposal()
    blank_id_prop.days[0].blocks[0].exercises[0].exercise_id = "   "
    with pytest.raises(AIRoutineAdapterError) as exc_id:
        validate_routine_structure(blank_id_prop)
    assert exc_id.value.error_code == "INVALID_ROUTINE_STRUCTURE"

    # B. Validación cuantitativa: exceso de días (>7), semanas (>52), series (>20), descanso (>600)
    too_many_days_prop = _make_valid_proposal()
    too_many_days_prop.days = [
        AdaptedDayData(
            name=f"Día {i}",
            order_index=i,
            blocks=[
                AdaptedBlockData(
                    name="B1",
                    order_index=0,
                    exercises=[AdaptedExerciseData(exercise_id="ex-1", order_index=0, sets=3, reps="10", rest_seconds=60)],
                )
            ],
        )
        for i in range(8)
    ]
    with pytest.raises(AIRoutineAdapterError) as exc_days_lim:
        validate_routine_quantities(too_many_days_prop)
    assert exc_days_lim.value.error_code == "ROUTINE_LIMIT_EXCEEDED"

    bad_weeks_prop = _make_valid_proposal()
    bad_weeks_prop.duration_weeks = 60
    with pytest.raises(AIRoutineAdapterError) as exc_weeks:
        validate_routine_quantities(bad_weeks_prop)
    assert exc_weeks.value.error_code == "ROUTINE_LIMIT_EXCEEDED"

    # C. Validación semántica: ejercicio inexistente o traza de sustitución funcionalmente incoherente
    unknown_ex_prop = _make_valid_proposal()
    unknown_ex_prop.days[0].blocks[0].exercises[0].exercise_id = "non-existent-id"
    with pytest.raises(AIRoutineAdapterError) as exc_sem_id:
        validate_routine_semantics(unknown_ex_prop, template, [ex_valid], [])
    assert exc_sem_id.value.error_code == "GEMINI_INVALID_EXERCISE"

    incoherent_trace_prop = _make_valid_proposal()
    incoherent_trace_prop.days[0].blocks[0].exercises[0].exercise_id = "ex-plank"
    incoherent_trace_prop.substitutions_trace = [
        SubstitutionTraceEntry(
            day_name="Día 1",
            block_name="Bloque 1",
            original_exercise_id="ex-1",
            original_exercise_name="Press de Banca",
            proposed_exercise_id="ex-plank",
            selected_exercise_id="ex-plank",
            selected_exercise_name="Plancha Abdominal",
            action="REPLACE",
            engine="gemini",
            reason="Sustitución incoherente",
        )
    ]
    with pytest.raises(AIRoutineAdapterError) as exc_sem_sub:
        validate_routine_semantics(incoherent_trace_prop, template, [ex_valid, ex_incoherent], [])
    assert exc_sem_sub.value.error_code == "GEMINI_INVALID_SUBSTITUTE"

    # D. Validación de integridad: ejercicios duplicados en bloque o más días que la plantilla
    dup_block_prop = _make_valid_proposal()
    dup_block_prop.days[0].blocks[0].exercises.append(
        AdaptedExerciseData(exercise_id="ex-1", order_index=1, sets=3, reps="10", rest_seconds=60)
    )
    with pytest.raises(AIRoutineAdapterError) as exc_dup:
        validate_routine_integrity(dup_block_prop, template)
    assert exc_dup.value.error_code == "GEMINI_DUPLICATE_EXERCISE"

    more_days_than_tpl = _make_valid_proposal()
    more_days_than_tpl.days.append(
        AdaptedDayData(
            name="Día Extra Inventado",
            order_index=1,
            blocks=[
                AdaptedBlockData(
                    name="B1",
                    order_index=0,
                    exercises=[AdaptedExerciseData(exercise_id="ex-1", order_index=0, sets=3, reps="10", rest_seconds=60)],
                )
            ],
        )
    )
    with pytest.raises(AIRoutineAdapterError) as exc_extra_days:
        validate_routine_integrity(more_days_than_tpl, template)
    assert exc_extra_days.value.error_code == "INVALID_ROUTINE_STRUCTURE"


def test_seed_demo_exercises_dataset_variety_and_biomechanical_coverage():
    """3.2: Verifica que el dataset inicial de seed_demo contenga entre 40 y 50 ejercicios variados,
    cubriendo tren superior, tren inferior, core, empuje, tracción, dominancia de rodilla, dominancia de cadera,
    cardio, movilidad y ejercicios sin equipamiento."""
    from backend.scripts.seed_demo import EXERCISES_DEMO_DATA
    from backend.src.services.ai_routine_adapter import infer_exercise_biomechanics

    all_seed_exercises: list[Exercise] = []
    for trainer_key, items in EXERCISES_DEMO_DATA.items():
        for idx, data in enumerate(items):
            all_seed_exercises.append(
                Exercise(
                    id=f"{trainer_key}-{idx}",
                    trainer_id=trainer_key,
                    **data,
                )
            )

    assert 40 <= len(all_seed_exercises) <= 50

    patterns = {infer_exercise_biomechanics(ex).movement_pattern for ex in all_seed_exercises}
    regions = {infer_exercise_biomechanics(ex).functional_region for ex in all_seed_exercises}
    equip_types = {infer_exercise_biomechanics(ex).equipment_type for ex in all_seed_exercises}
    no_mat_count = sum(1 for ex in all_seed_exercises if ex.has_no_materials_alternative)

    assert "KNEE_DOMINANT" in patterns
    assert "HIP_DOMINANT" in patterns
    assert "HORIZONTAL_PUSH" in patterns
    assert "VERTICAL_PUSH" in patterns
    assert "HORIZONTAL_PULL" in patterns
    assert "VERTICAL_PULL" in patterns
    assert "CORE_STABILITY" in patterns
    assert "LOCOMOTION_CARDIO" in patterns

    assert "LOWER_BODY" in regions
    assert "UPPER_PUSH" in regions
    assert "UPPER_PULL" in regions
    assert "CORE" in regions

    assert "BARBELL" in equip_types
    assert "DUMBBELL" in equip_types
    assert "MACHINE_CABLE" in equip_types
    assert "BODYWEIGHT_NO_MATERIALS" in equip_types
    assert no_mat_count >= 12


# ==============================================================================
# 9. Tests para límites de longitud de adaptation_notes (HI-01: 500 caracteres)
# ==============================================================================
def test_adaptation_notes_boundary_lengths_persistence_and_manual_edit(client):
    """Verifica límites de longitud de adaptation_notes (255, 256, 500, 501 caracteres),
    persistencia en DB, edición manual vía API, rechazo de >500 y compatibilidad con notas previas (HI-01).
    """
    from pydantic import ValidationError

    from backend.src.models.assigned_routine import AssignedRoutineExercise
    from backend.src.schemas.assigned_routine import AssignedRoutineExerciseUpdateInput
    from backend.src.services.ai_routine_adapter import ADAPTATION_NOTE_MAX_LENGTH

    assert ADAPTATION_NOTE_MAX_LENGTH == 500

    # 1. Nota de 255 caracteres (límite antiguo / compatibilidad)
    note_255 = "A" * 255
    inp_255 = AssignedRoutineExerciseUpdateInput(
        exercise_id="ex-1", sets=3, reps="10", rest_seconds=60, adaptation_notes=note_255
    )
    assert inp_255.adaptation_notes == note_255
    assert len(inp_255.adaptation_notes) == 255

    # 2. Nota de 256 caracteres (antiguamente fallaba, ahora permitida)
    note_256 = "B" * 256
    inp_256 = AssignedRoutineExerciseUpdateInput(
        exercise_id="ex-1", sets=3, reps="10", rest_seconds=60, adaptation_notes=note_256
    )
    assert inp_256.adaptation_notes == note_256
    assert len(inp_256.adaptation_notes) == 256

    # 3. Nota de 500 caracteres (nuevo límite máximo permitido)
    note_500 = "C" * 500
    inp_500 = AssignedRoutineExerciseUpdateInput(
        exercise_id="ex-1", sets=3, reps="10", rest_seconds=60, adaptation_notes=note_500
    )
    assert inp_500.adaptation_notes == note_500
    assert len(inp_500.adaptation_notes) == 500

    # 4. Nota de 501 caracteres (debe ser rechazada por el schema)
    note_501 = "D" * 501
    with pytest.raises(ValidationError) as exc_info:
        AssignedRoutineExerciseUpdateInput(
            exercise_id="ex-1", sets=3, reps="10", rest_seconds=60, adaptation_notes=note_501
        )
    err_str = str(exc_info.value).lower()
    assert "at most 500" in err_str or "max_length" in err_str or "string_too_long" in err_str

    # 5. Persistencia directa en base de datos de notas y tipo de columna ORM
    api, sessions = client
    with sessions():
        col_type = AssignedRoutineExercise.__table__.columns["adaptation_notes"].type
        assert getattr(col_type, "length", None) == 500

    # 6. Edición manual vía API con nota de 500 caracteres y rechazo de nota de 501 caracteres
    trainer_headers = register_and_login(api, "coach_notes_500@example.com", "TRAINER")
    register_and_login(api, "student_notes_500@example.com", "STUDENT")

    _, student_id = setup_trainer_and_student_relationship(
        sessions,
        "coach_notes_500@example.com",
        "student_notes_500@example.com",
        protected_zones=[],
        goals=["Hipertrofia"],
    )

    ex_id = create_exercise(api, trainer_headers, name="Press Pecho 500", target_muscle_group="Pecho")
    template = create_template(api, trainer_headers, [ex_id])

    gen_resp = api.post(
        AI_GENERATE_PATH,
        headers=trainer_headers,
        json={"student_id": student_id, "template_id": template["id"]},
    )
    assert gen_resp.status_code == 201
    routine_id = gen_resp.json()["id"]

    # Edición manual con nota de 500 caracteres
    edit_payload_500 = {
        "name": "Rutina con Nota Extensa",
        "duration_weeks": 4,
        "intensity": "MEDIA",
        "has_no_materials_alternative": False,
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {
                                "exercise_id": ex_id,
                                "sets": 4,
                                "reps": "10-12",
                                "rest_seconds": 60,
                                "adaptation_notes": note_500,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    put_resp = api.put(
        f"/api/v1/routines/assigned/{routine_id}",
        headers=trainer_headers,
        json=edit_payload_500,
    )
    assert put_resp.status_code == 200
    saved_note = put_resp.json()["days"][0]["blocks"][0]["exercises"][0]["adaptation_notes"]
    assert saved_note == note_500
    assert len(saved_note) == 500

    # Edición manual con nota de 501 caracteres: debe retornar HTTP 422
    edit_payload_501 = {
        "name": "Rutina con Nota Excedida",
        "duration_weeks": 4,
        "intensity": "MEDIA",
        "has_no_materials_alternative": False,
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {
                                "exercise_id": ex_id,
                                "sets": 4,
                                "reps": "10-12",
                                "rest_seconds": 60,
                                "adaptation_notes": note_501,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    put_resp_501 = api.put(
        f"/api/v1/routines/assigned/{routine_id}",
        headers=trainer_headers,
        json=edit_payload_501,
    )
    assert put_resp_501.status_code == 422

    # Compatibilidad con notas cortas existentes
    edit_payload_compat = {
        "name": "Rutina con Nota Corta Previa",
        "duration_weeks": 4,
        "intensity": "MEDIA",
        "has_no_materials_alternative": False,
        "days": [
            {
                "name": "Día 1",
                "blocks": [
                    {
                        "name": "Bloque 1",
                        "exercises": [
                            {
                                "exercise_id": ex_id,
                                "sets": 4,
                                "reps": "10-12",
                                "rest_seconds": 60,
                                "adaptation_notes": "Nota corta tradicional de 32 chars",
                            }
                        ],
                    }
                ],
            }
        ],
    }
    put_resp_compat = api.put(
        f"/api/v1/routines/assigned/{routine_id}",
        headers=trainer_headers,
        json=edit_payload_compat,
    )
    assert put_resp_compat.status_code == 200
    assert (
        put_resp_compat.json()["days"][0]["blocks"][0]["exercises"][0]["adaptation_notes"]
        == "Nota corta tradicional de 32 chars"
    )


