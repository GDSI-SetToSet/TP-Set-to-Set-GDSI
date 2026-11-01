#!/usr/bin/env python3
"""Prueba manual de humo (Smoke Test) para GeminiAIRoutineAdapter en US-13.

Este script se encuentra separado de la suite automatizada de Pytest para no
consumir cuota de Google Gemini en CI ni en ejecuciones de regresión.

Uso manual (con GEMINI_API_KEY configurada en el entorno o en backend/.env):
    python backend/scripts/smoke_test_gemini_us13.py
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.core.config import get_gemini_api_key, get_gemini_model
from backend.src.models.exercise import Exercise, VideoPlatform
from backend.src.models.health_questionnaire import HealthQuestionnaire
from backend.src.models.protected_zone import ProtectedZone
from backend.src.models.routine_template import (
    RoutineTemplate,
    RoutineTemplateBlock,
    RoutineTemplateDay,
    RoutineTemplateExercise,
)
from backend.src.models.student_profile import StudentProfile
from backend.src.services.ai_routine_adapter import (
    AIRoutineAdapterError,
    GeminiAIRoutineAdapter,
)


def _safe_print(message: str = "") -> None:
    """Imprime texto en consola de forma compatible con codificaciones limitadas (ej. CP1252 en Windows)."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    safe_text = message.encode(encoding, errors="replace").decode(encoding, errors="replace")
    print(safe_text)


def run_smoke_test() -> int:
    api_key = get_gemini_api_key()
    if not api_key:
        _safe_print(
            "[SKIP] GEMINI_API_KEY no está configurada. "
            "Configurala en backend/.env o como variable de entorno para ejecutar esta prueba manual."
        )
        return 0

    now = datetime.now(UTC)
    ex_shoulder = Exercise(
        id="ex-ficticio-hombro-01",
        trainer_id="trainer-demo-01",
        name="Press Militar con Mancuernas",
        description="Empuje vertical de hombros sentado.",
        category="FUERZA",
        target_muscle_group="Hombro",
        equipment_needed="Mancuernas",
        video_platform=VideoPlatform.NONE,
        created_at=now,
        updated_at=now,
    )
    ex_chest = Exercise(
        id="ex-ficticio-pecho-02",
        trainer_id="trainer-demo-01",
        name="Press de Banca Plano",
        description="Empuje horizontal para pectoral mayor.",
        category="FUERZA",
        target_muscle_group="Pecho",
        equipment_needed="Barra y banco",
        video_platform=VideoPlatform.NONE,
        created_at=now,
        updated_at=now,
    )
    ex_back = Exercise(
        id="ex-ficticio-espalda-03",
        trainer_id="trainer-demo-01",
        name="Remo con Mancuerna a un Brazo",
        description="Tracción horizontal para dorsal ancho.",
        category="FUERZA",
        target_muscle_group="Espalda",
        equipment_needed="Mancuerna",
        video_platform=VideoPlatform.NONE,
        created_at=now,
        updated_at=now,
    )

    template = RoutineTemplate(
        id="tpl-ficticia-01",
        trainer_id="trainer-demo-01",
        name="Torso Base General",
        duration_weeks=4,
        intensity="ALTA",
        has_no_materials_alternative=False,
        created_at=now,
        updated_at=now,
        days=[
            RoutineTemplateDay(
                id="day-01",
                template_id="tpl-ficticia-01",
                order_index=0,
                name="Día 1 - Tren Superior",
                blocks=[
                    RoutineTemplateBlock(
                        id="block-01",
                        day_id="day-01",
                        order_index=0,
                        name="Bloque Principal",
                        exercises=[
                            RoutineTemplateExercise(
                                id="entry-01",
                                block_id="block-01",
                                exercise_id=ex_shoulder.id,
                                order_index=0,
                                sets=4,
                                reps="8-10",
                                rest_seconds=90,
                                exercise=ex_shoulder,
                            ),
                            RoutineTemplateExercise(
                                id="entry-02",
                                block_id="block-01",
                                exercise_id=ex_back.id,
                                order_index=1,
                                sets=4,
                                reps="10-12",
                                rest_seconds=60,
                                exercise=ex_back,
                            ),
                        ],
                    )
                ],
            )
        ],
    )

    student = StudentProfile(
        id="student-ficticio-01",
        user_id="user-ficticio-01",
        first_name="Alumno",
        last_name="Ficticio",
        fitness_goals=["HIPERTROFIA"],
        personal_motivation="Ganar fuerza en torso cuidando una molestia previa en el hombro.",
        status="PUBLISHED",
        created_at=now,
        updated_at=now,
    )
    questionnaire = HealthQuestionnaire(
        id="hq-ficticio-01",
        student_id=student.id,
        status="CURRENT",
        has_heart_condition=False,
        has_chest_pain_activity=False,
        has_dizziness_or_balance_loss=False,
        has_bone_joint_problem=True,
        takes_prescription_meds=False,
        other_medical_conditions="Molestia articular en hombro derecho al empujar sobre la cabeza.",
        completed_at=now,
    )
    protected_zones = [
        ProtectedZone(
            id="pz-ficticia-01",
            student_id=student.id,
            body_area="Hombro derecho",
            created_at=now,
        )
    ]

    model_name = get_gemini_model()
    _safe_print(f"[INFO] Ejecutando Smoke Test de GeminiAIRoutineAdapter con modelo '{model_name}'...")

    adapter = GeminiAIRoutineAdapter()
    try:
        proposal = adapter.generate_adapted_routine(
            template=template,
            student=student,
            questionnaire=questionnaire,
            protected_zones=protected_zones,
            trainer_exercises=[ex_shoulder, ex_chest, ex_back],
        )
    except AIRoutineAdapterError as exc:
        _safe_print(f"[ERROR] Falló la prueba de humo ({exc.error_code} - HTTP {exc.status_code}): {exc.detail}")
        return 1

    _safe_print("\n" + "=" * 70)
    _safe_print(f"PROPUESTA GENERADA EXITOSAMENTE: {proposal.name}")
    _safe_print(f"Intensidad: {proposal.intensity} | Duración: {proposal.duration_weeks} semanas")
    _safe_print("-" * 70)
    _safe_print(proposal.adaptation_summary)
    _safe_print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_smoke_test())
