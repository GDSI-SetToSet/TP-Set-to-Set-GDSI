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
