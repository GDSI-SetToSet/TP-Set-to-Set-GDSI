#!/usr/bin/env python3
"""Prepara escenarios completos e idempotentes para la Sprint Review del Sprint 5.

Complementa a `backend/scripts/seed_demo.py` sobre cuentas sintéticas `@demo.settoset.com`
sin alterar datos reales ni requerir configuración manual previa:
- Ejecuta migraciones oficiales (incluyendo `WorkoutSessionSnapshot` y `routine_assignment_id`).
- Genera sesiones de hoy (`Finalizada` y `Entrenando`) y `No comenzada` (US-22).
- Prepara comparaciones históricas con reemplazo y snapshot inmutable (US-24).
- Habilita contexto completo de ajustes, bloqueo por contraindicación en rodilla y ajuste pendiente
  con sesión en curso (US-26).
- Agrega reportes de molestia/dolor con descarte de `NORMAL` (US-28) y alertas `PENDING`
  de `PAIN`, `REPEATED_DISCOMFORT` y `EXCESSIVE_EFFORT` (US-29).
- Deja alumna con riesgo de abandono tras 16 días sin reportes (US-32).
- Agrega semana intermedia en 0 kg y ejercicio con <2 sesiones para evolución (US-30 y US-65).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.scripts.seed_demo import DEMO_PASSWORD, seed_demo_data
from backend.src.core.config import APP_ENV
from backend.src.core.database import Base, SessionLocal, engine
from backend.src.core.migrations import apply_migrations
from backend.src.models.body_map_report import BodyMapPainReport, BodyMapPainReportZone
from backend.src.models.exercise import Exercise
from backend.src.models.exercise_replacement_log import ExerciseReplacementLog
from backend.src.models.notification import Notification
from backend.src.models.protected_zone import ProtectedZone
from backend.src.models.routine_template import RoutineTemplate
from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User, new_id
from backend.src.models.workout_log import (
    WorkoutSession,
    WorkoutSessionSnapshot,
    WorkoutSetLog,
)
from backend.src.services.notification_service import create_notification
from backend.src.services.routine_template_service import _snapshot_day_blocks
from backend.src.services.safety_alert_service import (
    create_excessive_effort_alert,
    create_pain_alerts_for_report,
    evaluate_repeated_discomfort_alerts,
)


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _require_user(db: Session, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise RuntimeError(f"No se encontró el usuario demo requerido: {email}")
    return user


def _require_trainer(db: Session, email: str) -> TrainerProfile:
    user = _require_user(db, email)
    trainer = db.scalar(select(TrainerProfile).where(TrainerProfile.user_id == user.id))
    if trainer is None:
        raise RuntimeError(f"No se encontró perfil de entrenador para {email}")
    return trainer


def _require_student(db: Session, email: str) -> StudentProfile:
    user = _require_user(db, email)
    student = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
    if student is None:
        raise RuntimeError(f"No se encontró perfil de alumno para {email}")
    return student


def _ensure_snapshot(
    db: Session,
    session: WorkoutSession,
    template: RoutineTemplate,
    assignment_id: str | None,
) -> None:
    if db.get(WorkoutSessionSnapshot, session.id) is not None:
        return
    db.add(
        WorkoutSessionSnapshot(
            session_id=session.id,
            routine_assignment_id=assignment_id,
            planned_blocks=_snapshot_day_blocks(template, session.day_name),
        )
    )


def _add_set_log(
    db: Session,
    *,
    session: WorkoutSession,
    exercise: Exercise,
    set_number: int,
    reps: str,
    weight_kg: float | None,
    duration_seconds: int,
    recorded_at: datetime,
) -> None:
    db.add(
        WorkoutSetLog(
            id=new_id(),
            session_id=session.id,
            student_id=session.student_id,
            relationship_id=session.relationship_id,
            routine_id=session.routine_id,
            day_name=session.day_name,
            exercise_id=exercise.id,
            exercise_name=exercise.name,
            modality=session.modality,
            set_number=set_number,
            reps_completed=reps,
            weight_kg=weight_kg,
            duration_seconds=duration_seconds,
            recorded_at=recorded_at,
        )
    )


def prepare_sprint5_demo_data(db: Session, *, reference_now: datetime | None = None) -> None:
    """Siembra los escenarios idempotentes necesarios para demostrar el Sprint 5 completo."""
    now = reference_now or _utc_now()
    today_date = now.date()
    today_start = datetime(today_date.year, today_date.month, today_date.day, 11, 0, 0)
    yesterday_start = datetime(today_date.year, today_date.month, today_date.day, 16, 0, 0) - timedelta(days=1)

    # Asegura datos base de seed_demo si todavía no fueron sembrados
    if db.scalar(select(User).where(User.email == "lucas.benitez@demo.settoset.com")) is None:
        seed_demo_data(db)

    lucas_u = _require_user(db, "lucas.benitez@demo.settoset.com")
    lucas = _require_trainer(db, "lucas.benitez@demo.settoset.com")
    gonzalo = _require_trainer(db, "gonzalo.morales@demo.settoset.com")

    valentina_u = _require_user(db, "valentina.rossi@demo.settoset.com")
    valentina = _require_student(db, "valentina.rossi@demo.settoset.com")
    mateo = _require_student(db, "mateo.gomez@demo.settoset.com")
    lucia = _require_student(db, "lucia.fernandez@demo.settoset.com")

    plan_integral = db.scalar(
        select(TrainingPlan).where(
            TrainingPlan.trainer_id == lucas.id,
            TrainingPlan.title == "Fuerza y Rendimiento Integral",
        )
    )
    plan_iniciacion = db.scalar(
        select(TrainingPlan).where(
            TrainingPlan.trainer_id == lucas.id,
            TrainingPlan.title == "Iniciación al Entrenamiento de Fuerza",
        )
    )
    if plan_integral is None or plan_iniciacion is None:
        raise RuntimeError("Faltan planes base de Lucas Benítez del seed_demo.")

    # US-20 CA-1: dejar a Gonzalo con un único paquete vigente para demostrar ocultamiento del filtro
    plan_halterofilia = db.scalar(
        select(TrainingPlan).where(
            TrainingPlan.trainer_id == gonzalo.id,
            TrainingPlan.title == "Halterofilia y Levantamiento Olímpico",
        )
    )
    if plan_halterofilia is not None and plan_halterofilia.is_active:
        plan_halterofilia.is_active = False

    tpl_fuerza = db.scalar(
        select(RoutineTemplate).where(
            RoutineTemplate.trainer_id == lucas.id,
            RoutineTemplate.name == "Fuerza Base 3 Días",
        )
    )
    tpl_iniciacion = db.scalar(
        select(RoutineTemplate).where(
            RoutineTemplate.trainer_id == lucas.id,
            RoutineTemplate.name == "Iniciación Cuerpo Completo",
        )
    )
    if tpl_fuerza is None or tpl_iniciacion is None:
        raise RuntimeError("Faltan rutinas base de Lucas Benítez del seed_demo.")

    def ex_by_name(name: str) -> Exercise:
        exercise = db.scalar(select(Exercise).where(Exercise.trainer_id == lucas.id, Exercise.name == name))
        if exercise is None:
            raise RuntimeError(f"Falta ejercicio '{name}' en la biblioteca de Lucas.")
        return exercise

    ex_sentadilla = ex_by_name("Sentadilla con Barra")
    ex_press = ex_by_name("Press de Banca")
    ex_remo = ex_by_name("Remo con Barra")
    ex_plancha = ex_by_name("Plancha Abdominal")
    ex_curl_femoral = ex_by_name("Curl Femoral en Camilla")
    ex_extension_rodilla = ex_by_name("Extensión Terminal de Rodilla con Banda")

    rel_valentina = db.scalar(
        select(TrainingRelationship).where(
            TrainingRelationship.trainer_id == lucas.id,
            TrainingRelationship.student_id == valentina.id,
            TrainingRelationship.status == "ACTIVE",
        )
    )
    if rel_valentina is None:
        raise RuntimeError("Falta relación activa Lucas <-> Valentina Rossi.")
    if not rel_valentina.routine_assignment_id:
        rel_valentina.routine_assignment_id = new_id()
    db.flush()

    val_sessions = list(
        db.scalars(
            select(WorkoutSession)
            .where(WorkoutSession.relationship_id == rel_valentina.id)
            .order_by(WorkoutSession.started_at.asc())
        )
    )
    for sess in val_sessions:
        _ensure_snapshot(db, sess, tpl_fuerza, rel_valentina.routine_assignment_id)

    # A) Sesión temprana de Valentina (~14 días antes de su primera sesión sembrada) para dejar una
    #    semana intermedia completa con volumen 0 kg (US-65 CA-3 / US-30) y un ejercicio con 1 sola sesión.
    earliest_val = val_sessions[0].started_at if val_sessions else now - timedelta(days=60)
    early_at = earliest_val - timedelta(days=14)
    if rel_valentina.routine_assigned_at is None or rel_valentina.routine_assigned_at > early_at - timedelta(days=2):
        rel_valentina.routine_assigned_at = early_at - timedelta(days=2)

    has_curl_log = db.scalar(
        select(WorkoutSetLog.id).where(
            WorkoutSetLog.relationship_id == rel_valentina.id,
            WorkoutSetLog.exercise_id == ex_curl_femoral.id,
        )
    )
    if has_curl_log is None:
        s_early = WorkoutSession(
            id=new_id(),
            student_id=valentina.id,
            relationship_id=rel_valentina.id,
            routine_id=tpl_fuerza.id,
            day_name="Día 1 - Pierna",
            modality="GYM",
            started_at=early_at,
            finished_at=early_at + timedelta(minutes=42),
            rpe=6,
        )
        db.add(s_early)
        db.flush()
        _ensure_snapshot(db, s_early, tpl_fuerza, rel_valentina.routine_assignment_id)
        for sn in (1, 2, 3):
            _add_set_log(
                db,
                session=s_early,
                exercise=ex_sentadilla,
                set_number=sn,
                reps="8",
                weight_kg=22.5,
                duration_seconds=45,
                recorded_at=early_at + timedelta(minutes=5 + sn * 3),
            )
        for sn in (1, 2):
            _add_set_log(
                db,
                session=s_early,
                exercise=ex_curl_femoral,
                set_number=sn,
                reps="10",
                weight_kg=30.0,
                duration_seconds=40,
                recorded_at=early_at + timedelta(minutes=22 + sn * 3),
            )

    # B) Alertas y reportes previos de Valentina (PAIN + base de DISCOMFORT en Shoulder + NORMAL)
    pain_report_prev = db.scalar(
        select(BodyMapPainReport).where(BodyMapPainReport.idempotency_key == "seed-demo-valentina-knee-pain-v1")
    )
    if pain_report_prev is not None and pain_report_prev.session_id is not None:
        sess_prev = db.get(WorkoutSession, pain_report_prev.session_id)
        create_pain_alerts_for_report(
            db,
            report=pain_report_prev,
            relationship=rel_valentina,
            student=valentina,
            session=sess_prev,
            exercise=ex_sentadilla,
            now=pain_report_prev.created_at,
        )
        existing_pain_notif = db.scalar(
            select(Notification).where(
                Notification.recipient_id == lucas_u.id,
                Notification.type == "PAIN_ALERT",
                Notification.related_entity_id == pain_report_prev.id,
            )
        )
        if existing_pain_notif is None:
            create_notification(
                db,
                recipient_id=lucas_u.id,
                type="PAIN_ALERT",
                title="Alerta de dolor en Rodilla",
                message='Valentina Rossi reportó dolor en Rodilla durante el ejercicio "Sentadilla con Barra".',
                related_entity_type="BODY_MAP_REPORT",
                related_entity_id=pain_report_prev.id,
                related_student_id=valentina.id,
                related_session_id=pain_report_prev.session_id,
                commit=False,
            )

        if (
            db.scalar(
                select(BodyMapPainReport).where(
                    BodyMapPainReport.idempotency_key == "sprint5-val-prev-shoulder"
                )
            )
            is None
        ):
            r_prev_sh = BodyMapPainReport(
                id=new_id(),
                student_id=valentina.id,
                relationship_id=rel_valentina.id,
                session_id=pain_report_prev.session_id,
                exercise_id=ex_press.id,
                context="IN_EXERCISE",
                action_taken="NONE",
                idempotency_key="sprint5-val-prev-shoulder",
                created_at=pain_report_prev.created_at + timedelta(minutes=3),
            )
            db.add(r_prev_sh)
            db.flush()
            db.add(
                BodyMapPainReportZone(
                    id=new_id(),
                    report_id=r_prev_sh.id,
                    zone="Shoulder",
                    intensity="DISCOMFORT",
                    created_at=r_prev_sh.created_at,
                )
            )
            db.add(
                BodyMapPainReportZone(
                    id=new_id(),
                    report_id=r_prev_sh.id,
                    zone="Lower back",
                    intensity="NORMAL",
                    created_at=r_prev_sh.created_at,
                )
            )
            db.flush()

    # C) Sesión FINALIZADA HOY de Valentina (US-22, US-24 con reemplazo, US-26 contexto, US-29 RPE 9 + molestia repetida)
    day_floor = datetime(today_date.year, today_date.month, today_date.day, 0, 0, 0)
    s_val_today = db.scalar(
        select(WorkoutSession).where(
            WorkoutSession.relationship_id == rel_valentina.id,
            WorkoutSession.started_at >= day_floor,
        )
    )
    if s_val_today is None:
        s_val_today = WorkoutSession(
            id=new_id(),
            student_id=valentina.id,
            relationship_id=rel_valentina.id,
            routine_id=tpl_fuerza.id,
            day_name="Día 1 - Pierna",
            modality="GYM",
            started_at=today_start,
            finished_at=today_start + timedelta(minutes=48),
            rpe=9,
        )
        db.add(s_val_today)
        db.flush()
        _ensure_snapshot(db, s_val_today, tpl_fuerza, rel_valentina.routine_assignment_id)

        db.add(
            ExerciseReplacementLog(
                id=new_id(),
                student_id=valentina.id,
                routine_id=tpl_fuerza.id,
                session_id=s_val_today.id,
                day_name="Día 1 - Pierna",
                session_date=today_date,
                original_exercise_id=ex_sentadilla.id,
                replacement_exercise_id=ex_extension_rodilla.id,
                updated_at=today_start + timedelta(minutes=5),
            )
        )
        for sn in (1, 2, 3):
            _add_set_log(
                db,
                session=s_val_today,
                exercise=ex_extension_rodilla,
                set_number=sn,
                reps="12",
                weight_kg=15.0,
                duration_seconds=40,
                recorded_at=today_start + timedelta(minutes=8 + sn * 3),
            )
        for sn in (1, 2, 3):
            _add_set_log(
                db,
                session=s_val_today,
                exercise=ex_plancha,
                set_number=sn,
                reps="45 seg",
                weight_kg=None,
                duration_seconds=45,
                recorded_at=today_start + timedelta(minutes=25 + sn * 3),
            )
        db.flush()

    today_sh_key = f"sprint5-val-{today_date.isoformat()}-shoulder"
    if db.scalar(select(BodyMapPainReport).where(BodyMapPainReport.idempotency_key == today_sh_key)) is None:
        r_val_today = BodyMapPainReport(
            id=new_id(),
            student_id=valentina.id,
            relationship_id=rel_valentina.id,
            session_id=s_val_today.id,
            exercise_id=ex_press.id,
            context="POST_SESSION",
            action_taken="NONE",
            idempotency_key=today_sh_key,
            created_at=today_start + timedelta(minutes=49),
        )
        db.add(r_val_today)
        db.flush()
        db.add(
            BodyMapPainReportZone(
                id=new_id(),
                report_id=r_val_today.id,
                zone="Shoulder",
                intensity="DISCOMFORT",
                created_at=r_val_today.created_at,
            )
        )
        db.flush()
        evaluate_repeated_discomfort_alerts(
            db,
            report=r_val_today,
            relationship=rel_valentina,
            student=valentina,
            student_user=valentina_u,
            session=s_val_today,
            exercise=ex_press,
            now=r_val_today.created_at,
        )
    create_excessive_effort_alert(db, s_val_today, now=today_start + timedelta(minutes=48))

    # D) Vínculo Lucas <-> Mateo Gómez (zona protegida Knee, sesión ayer Finalizada, sesión hoy Entrenando)
    rel_mateo = db.scalar(
        select(TrainingRelationship).where(
            TrainingRelationship.trainer_id == lucas.id,
            TrainingRelationship.student_id == mateo.id,
            TrainingRelationship.status == "ACTIVE",
        )
    )
    if rel_mateo is None:
        rel_mateo = TrainingRelationship(
            id=new_id(),
            student_id=mateo.id,
            trainer_id=lucas.id,
            plan_id=plan_integral.id,
            agreed_monthly_price=plan_integral.monthly_price,
            agreed_currency=plan_integral.currency,
            status="ACTIVE",
            start_date=today_date - timedelta(days=6),
            welcome_message="Bienvenido Mateo, arrancamos con Iniciación Cuerpo Completo cuidando rodilla.",
            welcome_message_sent=True,
            initial_routine_id=tpl_iniciacion.id,
            routine_assignment_id=new_id(),
            routine_assigned_at=now - timedelta(days=6),
            routine_modality="GYM",
        )
        db.add(rel_mateo)
        db.flush()

    if db.scalar(select(ProtectedZone).where(ProtectedZone.student_id == mateo.id)) is None:
        db.add(
            ProtectedZone(
                id=new_id(),
                student_id=mateo.id,
                body_area="Knee",
                created_at=now - timedelta(days=6),
            )
        )
        db.flush()

    s_mateo_yest = db.scalar(
        select(WorkoutSession).where(
            WorkoutSession.relationship_id == rel_mateo.id,
            WorkoutSession.finished_at.is_not(None),
        )
    )
    if s_mateo_yest is None:
        s_mateo_yest = WorkoutSession(
            id=new_id(),
            student_id=mateo.id,
            relationship_id=rel_mateo.id,
            routine_id=tpl_iniciacion.id,
            day_name="Día 1",
            modality="GYM",
            started_at=yesterday_start,
            finished_at=yesterday_start + timedelta(minutes=42),
            rpe=7,
        )
        db.add(s_mateo_yest)
        db.flush()
        _ensure_snapshot(db, s_mateo_yest, tpl_iniciacion, rel_mateo.routine_assignment_id)
        for sn in (1, 2, 3):
            _add_set_log(
                db,
                session=s_mateo_yest,
                exercise=ex_press,
                set_number=sn,
                reps="10",
                weight_kg=25.0,
                duration_seconds=35,
                recorded_at=yesterday_start + timedelta(minutes=10 + sn * 3),
            )
            _add_set_log(
                db,
                session=s_mateo_yest,
                exercise=ex_remo,
                set_number=sn,
                reps="10",
                weight_kg=25.0,
                duration_seconds=35,
                recorded_at=yesterday_start + timedelta(minutes=25 + sn * 3),
            )

    s_mateo_live = db.scalar(
        select(WorkoutSession).where(
            WorkoutSession.relationship_id == rel_mateo.id,
            WorkoutSession.finished_at.is_(None),
        )
    )
    if s_mateo_live is None:
        live_start = datetime(today_date.year, today_date.month, today_date.day, 14, 15, 0)
        s_mateo_live = WorkoutSession(
            id=new_id(),
            student_id=mateo.id,
            relationship_id=rel_mateo.id,
            routine_id=tpl_iniciacion.id,
            day_name="Día 1",
            modality="GYM",
            started_at=live_start,
            finished_at=None,
            rpe=None,
        )
        db.add(s_mateo_live)
        db.flush()
        _ensure_snapshot(db, s_mateo_live, tpl_iniciacion, rel_mateo.routine_assignment_id)
        for sn in (1, 2):
            _add_set_log(
                db,
                session=s_mateo_live,
                exercise=ex_press,
                set_number=sn,
                reps="10",
                weight_kg=27.5,
                duration_seconds=32,
                recorded_at=live_start + timedelta(minutes=5 + sn * 2),
            )

    # E) Vínculo Lucas <-> Lucía Fernández (16 días desde asignación, 0 sesiones -> US-32 riesgo de abandono + US-22 No comenzada)
    rel_lucia = db.scalar(
        select(TrainingRelationship).where(
            TrainingRelationship.trainer_id == lucas.id,
            TrainingRelationship.student_id == lucia.id,
            TrainingRelationship.status == "ACTIVE",
        )
    )
    if rel_lucia is None:
        rel_lucia = TrainingRelationship(
            id=new_id(),
            student_id=lucia.id,
            trainer_id=lucas.id,
            plan_id=plan_iniciacion.id,
            agreed_monthly_price=plan_iniciacion.monthly_price,
            agreed_currency=plan_iniciacion.currency,
            status="ACTIVE",
            start_date=today_date - timedelta(days=17),
            welcome_message="Bienvenida Lucía, ante cualquier duda avisame.",
            welcome_message_sent=True,
            initial_routine_id=tpl_fuerza.id,
            routine_assignment_id=new_id(),
            routine_assigned_at=now - timedelta(days=16),
            routine_modality="GYM",
        )
        db.add(rel_lucia)

    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepara datos idempotentes de Sprint Review para Sprint 5 sobre usuarios @demo.settoset.com."
    )
    parser.parse_args()

    if APP_ENV == "production":
        parser.error("Este script no debe ejecutarse con APP_ENV=production.")
    if os.getenv("DISABLE_DEMO_PREP") == "1":
        return

    Base.metadata.create_all(bind=engine)
    apply_migrations(engine)

    with SessionLocal() as db:
        prepare_sprint5_demo_data(db)

    print("Datos de Sprint Review (Sprint 5) preparados correctamente.")
    print(f"Contraseña de cuentas @demo.settoset.com: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
