from types import SimpleNamespace

from backend.src.schemas.routine_template import RoutineTemplateInput
from backend.src.services.routine_template_service import build_days, own_template_exercise_ids


def test_build_days_preserves_day_block_order_estimates_and_target_weight():
    payload = RoutineTemplateInput.model_validate(
        {
            "name": "Rutina por días",
            "duration_weeks": 4,
            "intensity": "MEDIA",
            "days": [
                {
                    "name": "Día A",
                    "blocks": [
                        {
                            "name": "Entrada en calor",
                            "estimated_duration_minutes": 7,
                            "exercises": [
                                {
                                    "exercise_id": "exercise-a",
                                    "sets": 2,
                                    "reps": "10",
                                    "rest_seconds": 30,
                                    "target_weight_kg": 0,
                                }
                            ],
                        },
                        {
                            "name": "Principal",
                            "estimated_duration_minutes": 18,
                            "exercises": [
                                {
                                    "exercise_id": "exercise-b",
                                    "sets": 3,
                                    "reps": "8-10",
                                    "rest_seconds": 60,
                                    "target_weight_kg": 12.5,
                                }
                            ],
                        },
                    ],
                },
                {
                    "name": "Día C",
                    "blocks": [
                        {
                            "name": "Movilidad",
                            "estimated_duration_minutes": 12,
                            "exercises": [
                                {
                                    "exercise_id": "exercise-c",
                                    "sets": 1,
                                    "reps": "5 min",
                                    "rest_seconds": 0,
                                }
                            ],
                        }
                    ],
                },
            ],
        }
    )

    days = build_days(payload)

    assert [day.name for day in days] == ["Día A", "Día C"]
    assert [day.order_index for day in days] == [0, 1]
    assert [block.name for block in days[0].blocks] == ["Entrada en calor", "Principal"]
    assert [block.estimated_duration_minutes for block in days[0].blocks] == [7, 18]
    assert days[0].blocks[0].exercises[0].target_weight_kg == 0
    assert days[0].blocks[1].exercises[0].target_weight_kg == 12.5
    assert days[1].blocks[0].exercises[0].target_weight_kg is None


def test_own_template_exercise_ids_collects_ids_from_all_days_and_blocks():
    template = SimpleNamespace(
        days=[
            SimpleNamespace(
                blocks=[
                    SimpleNamespace(
                        exercises=[
                            SimpleNamespace(exercise_id="exercise-a"),
                            SimpleNamespace(exercise_id="exercise-b"),
                        ]
                    ),
                    SimpleNamespace(exercises=[SimpleNamespace(exercise_id="exercise-c")]),
                ]
            ),
            SimpleNamespace(blocks=[SimpleNamespace(exercises=[SimpleNamespace(exercise_id="exercise-a")])]),
        ]
    )

    assert own_template_exercise_ids(template) == {"exercise-a", "exercise-b", "exercise-c"}
