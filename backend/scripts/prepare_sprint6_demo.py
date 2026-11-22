#!/usr/bin/env python3
"""Prepara escenarios idempotentes para la Sprint Review del Sprint 6.

Se ejecuta después de `seed_demo.py` (y aplica primero `prepare_sprint5_demo.py`) sobre cuentas
sintéticas `@demo.settoset.com`. Todo queda sobre el entrenador Lucas Benítez, más Tomás Castro
(Gonzalo Morales) para la celebración en vivo:

- US-34 / US-71: Valentina "Al día" (pago del entrenador + pago informado y confirmado), Mateo
  "Por vencer" (3 días) y Lucía "Vencida" con la rutina bloqueada y un pago informado con
  comprobante pendiente de confirmar.
- US-35: Sofía Martínez vinculada a Lucas para darla de baja en vivo.
- US-21 / US-62: chat Lucas–Valentina con un mensaje sin leer, una consulta técnica pendiente y
  otra respondida con nota técnica fijada sobre "Sentadilla con Barra" (Día 1: Valentina la ve al
  iniciar su próxima sesión).
- US-68: Valentina con 5 semanas de racha; Joaquín Díaz con la racha recién cortada (recibe el
  mensaje de aliento al abrir la app).
- US-67: logros de Valentina con una felicitación de Lucas sin ver; Tomás con 9 sesiones, así que
  al finalizar la 10.ª en vivo desbloquea "10 sesiones" con celebración.

Las fechas son relativas a hoy. Es idempotente: volver a correrlo el mismo día no duplica datos.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import UploadFile
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session
from starlette.datastructures import Headers

from backend.scripts.prepare_sprint5_demo import prepare_sprint5_demo_data
from backend.scripts.seed_demo import DEMO_PASSWORD, seed_demo_data
from backend.src.core.config import APP_ENV
from backend.src.core.database import Base, SessionLocal, engine
from backend.src.core.migrations import apply_migrations
from backend.src.models.achievement import AchievementCongratulation, StudentAchievement
from backend.src.models.conversation import ConversationMessage
from backend.src.models.exercise import Exercise
from backend.src.models.informal_payment import InformalPayment
from backend.src.models.routine_template import RoutineTemplate
from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User, new_id
from backend.src.models.workout_log import WorkoutSession
from backend.src.schemas.conversation import MessageCreate, TechnicalQueryCreate
from backend.src.schemas.informal_payment import PaymentCreate
from backend.src.services.achievement_service import congratulate, evaluate_achievements
from backend.src.services.conversation_service import send_message
from backend.src.services.informal_payment_service import (
    confirm_payment,
    register_payment,
)
from backend.src.services.student_subscription_service import report_payment
from backend.src.services.subscription_service import (
    DUE_SOON_DAYS,
    add_months,
    compute_due_date,
)
from backend.src.services.technical_query_service import create_query

DEMO_NOTE = "Demo Sprint 6"
LUCAS = "lucas.benitez@demo.settoset.com"
VALENTINA = "valentina.rossi@demo.settoset.com"
MATEO = "mateo.gomez@demo.settoset.com"
LUCIA = "lucia.fernandez@demo.settoset.com"
SOFIA = "sofia.martinez@demo.settoset.com"
JOAQUIN = "joaquin.diaz@demo.settoset.com"
TOMAS = "tomas.castro@demo.settoset.com"
RECEIPT_PDF = b"%PDF-1.4\n% Comprobante de transferencia (demo Sprint 6)\n%%EOF\n"


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def due_soon_start_date(today: date, target_days: int = 3) -> date:
    """Elige un `start_date <= today` cuyo vencimiento (+1 mes) quede `POR_VENCER` lo más cerca de `target_days`.

    Como `add_months(start, 1)` recorta al fin de mes (ej. 28/02 → 28/03), fechas como 29–31 de marzo
    o 31 de mayo no tienen un `start_date` a exactamente 1 mes atrás. Buscando alrededor de
    `add_months(today + target_days, -1)` se garantiza siempre `1 <= days_until_due <= DUE_SOON_DAYS`
    (estado `POR_VENCER` en los 365/366 días del año) y exactamente `target_days` siempre que exista.
    """
    target_due = today + timedelta(days=target_days)
    base = add_months(target_due, -1)
    candidates = [
        (abs(days - target_days), 0 if days >= 1 else 1, candidate)
        for delta in range(-DUE_SOON_DAYS, DUE_SOON_DAYS + 1)
        if (candidate := base + timedelta(days=delta)) <= today
        and 0 <= (days := (compute_due_date(candidate, 0) - today).days) <= DUE_SOON_DAYS
    ]
    return min(candidates)[2]


def _user(db: Session, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise RuntimeError(f"Falta la cuenta demo {email}. Corré antes backend/scripts/seed_demo.py.")
    return user


def _student(db: Session, email: str) -> StudentProfile:
    profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == _user(db, email).id))
    if profile is None:
        raise RuntimeError(f"Falta el perfil de alumno de {email}.")
    return profile


def _active(db: Session, trainer: TrainerProfile, student: StudentProfile) -> TrainingRelationship | None:
    return db.scalar(
        select(TrainingRelationship).where(
            TrainingRelationship.trainer_id == trainer.id,
            TrainingRelationship.student_id == student.id,
            TrainingRelationship.status == "ACTIVE",
        )
    )


def _ensure_relationship(
    db: Session,
    trainer: TrainerProfile,
    student: StudentProfile,
    plan: TrainingPlan,
    template: RoutineTemplate,
    *,
    start: date,
    assigned_at: datetime,
    welcome: str,
) -> TrainingRelationship:
    relationship = _active(db, trainer, student)
    if relationship is None:
        relationship = TrainingRelationship(
            id=new_id(),
            student_id=student.id,
            trainer_id=trainer.id,
            plan_id=plan.id,
            agreed_monthly_price=plan.monthly_price,
            agreed_currency=plan.currency,
            status="ACTIVE",
            start_date=start,
            welcome_message=welcome,
            welcome_message_sent=True,
            initial_routine_id=template.id,
            routine_assignment_id=new_id(),
            routine_assigned_at=assigned_at,
            routine_modality="GYM",
        )
        db.add(relationship)
        db.flush()
    return relationship


def _session_template(db: Session, relationship: TrainingRelationship) -> tuple[str, list[str]]:
    """routine_id y nombres de día para sesiones nuevas del vínculo."""
    template = db.get(RoutineTemplate, relationship.initial_routine_id)
    if template is None:
        raise RuntimeError("El vínculo demo no tiene rutina asignada.")
    days = [day.name for day in sorted(template.days, key=lambda day: day.order_index)] or ["Día 1"]
    return template.id, days


def _ensure_week_sessions(db: Session, relationship: TrainingRelationship, week_start: date, count: int) -> None:
    """Completa la semana con sesiones finalizadas hasta llegar a `count` (sin duplicar)."""
    week_end = datetime.combine(week_start + timedelta(weeks=1), datetime.min.time())
    begin = datetime.combine(week_start, datetime.min.time())
    existing = db.scalar(
        select(func.count(WorkoutSession.id)).where(
            WorkoutSession.relationship_id == relationship.id,
            WorkoutSession.finished_at.is_not(None),
            WorkoutSession.finished_at >= begin,
            WorkoutSession.finished_at < week_end,
        )
    ) or 0
    routine_id, days = _session_template(db, relationship)
    for index in range(existing, count):
        started = begin + timedelta(days=index * 2, hours=9)  # lunes, miércoles, viernes…
        db.add(
            WorkoutSession(
                student_id=relationship.student_id,
                relationship_id=relationship.id,
                routine_id=routine_id,
                day_name=days[index % len(days)],
                modality="GYM",
                started_at=started,
                finished_at=started + timedelta(minutes=55),
                rpe=7,
            )
        )
    db.flush()


def _has_demo_payment(db: Session, relationship: TrainingRelationship) -> bool:
    return db.scalar(
        select(InformalPayment.id).where(
            InformalPayment.relationship_id == relationship.id,
            InformalPayment.note.like(f"{DEMO_NOTE}%"),
        )
    ) is not None


def _receipt() -> UploadFile:
    return UploadFile(
        file=io.BytesIO(RECEIPT_PDF),
        filename="comprobante-transferencia.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )


def _exercise(db: Session, trainer: TrainerProfile, name: str) -> Exercise:
    exercise = db.scalar(select(Exercise).where(Exercise.trainer_id == trainer.id, Exercise.name == name))
    if exercise is None:
        raise RuntimeError(f"Falta el ejercicio '{name}' en la biblioteca de Lucas.")
    return exercise


def prepare_sprint6_demo_data(
    db: Session,
    *,
    today: date | None = None,
    password: str = DEMO_PASSWORD,
) -> dict[str, str]:
    """Siembra los escenarios del Sprint 6 y devuelve un resumen para imprimir."""
    prepare_sprint5_demo_data(db, password=password)
    today = today or _utc_now().date()
    this_monday = _monday(today)

    lucas_user = _user(db, LUCAS)
    lucas = db.scalar(select(TrainerProfile).where(TrainerProfile.user_id == lucas_user.id))
    valentina_user = _user(db, VALENTINA)
    lucia_user = _user(db, LUCIA)
    valentina, mateo, lucia = _student(db, VALENTINA), _student(db, MATEO), _student(db, LUCIA)
    sofia, joaquin = _student(db, SOFIA), _student(db, JOAQUIN)
    plan = db.scalar(
        select(TrainingPlan).where(TrainingPlan.trainer_id == lucas.id, TrainingPlan.title == "Iniciación al Entrenamiento de Fuerza")
    )
    tpl_iniciacion = db.scalar(
        select(RoutineTemplate).where(RoutineTemplate.trainer_id == lucas.id, RoutineTemplate.name == "Iniciación Cuerpo Completo")
    )
    if plan is None or tpl_iniciacion is None:
        raise RuntimeError("Faltan el paquete o la rutina de iniciación de Lucas del seed_demo.")
    lucas.max_students = max(lucas.max_students or 0, 10)

    rel_valentina = _active(db, lucas, valentina)
    rel_mateo = _active(db, lucas, mateo)
    rel_lucia = _active(db, lucas, lucia)
    if not (rel_valentina and rel_mateo and rel_lucia):
        raise RuntimeError("Faltan los vínculos de Lucas del Sprint 5 (Valentina, Mateo y Lucía).")

    # --- US-35: alumna para dar de baja en vivo ------------------------------------------
    _ensure_relationship(
        db, lucas, sofia, plan, tpl_iniciacion,
        start=today - timedelta(days=10),
        assigned_at=datetime.combine(today - timedelta(days=9), datetime.min.time()),
        welcome="¡Bienvenida Sofía! Arrancamos con una rutina de iniciación.",
    )

    # --- US-68: Valentina con 5 semanas de racha (objetivo = 3 días de "Fuerza Base 3 Días") ---
    for weeks_ago in range(5, 0, -1):
        _ensure_week_sessions(db, rel_valentina, this_monday - timedelta(weeks=weeks_ago), 3)
    _ensure_week_sessions(db, rel_valentina, this_monday, 1)  # avance de la semana en curso

    # Joaquín: cumplió 3 semanas (objetivo 1) y la semana pasada no entrenó → racha cortada.
    rel_joaquin = _ensure_relationship(
        db, lucas, joaquin, plan, tpl_iniciacion,
        start=this_monday - timedelta(weeks=5),
        assigned_at=datetime.combine(this_monday - timedelta(weeks=4), datetime.min.time()),
        welcome="¡Bienvenido Joaquín! Una sesión por semana para empezar.",
    )
    for weeks_ago in (4, 3, 2):
        _ensure_week_sessions(db, rel_joaquin, this_monday - timedelta(weeks=weeks_ago), 1)
    db.commit()

    # --- US-34 / US-71: tres estados de suscripción --------------------------------------
    rel_valentina.start_date = today - timedelta(days=5)
    rel_mateo.start_date = due_soon_start_date(today)  # siempre "Por vencer" (objetivo 3 días)
    rel_lucia.start_date = add_months(today, -2)  # venció hace un mes → Vencida (rutina bloqueada)
    db.commit()

    if not _has_demo_payment(db, rel_valentina):
        register_payment(
            db, lucas_user, valentina.id,
            PaymentCreate(paid_on=today - timedelta(days=14), amount=str(rel_valentina.agreed_monthly_price),
                          method="EFECTIVO", months_covered=1, note=f"{DEMO_NOTE}: cuota en efectivo"),
            today,
        )
        reported = asyncio.run(report_payment(
            db, valentina_user, rel_valentina.id,
            PaymentCreate(paid_on=today - timedelta(days=2), amount=str(rel_valentina.agreed_monthly_price),
                          method="TRANSFERENCIA", months_covered=1, note=f"{DEMO_NOTE}: transferencia de diciembre"),
            _receipt(), today,
        ))
        confirm_payment(db, lucas_user, reported.payment.id, today)

    if not _has_demo_payment(db, rel_joaquin):  # entrena hace 5 semanas: pagó su segundo mes
        register_payment(
            db, lucas_user, joaquin.id,
            PaymentCreate(paid_on=this_monday - timedelta(weeks=1), amount=str(rel_joaquin.agreed_monthly_price),
                          method="TRANSFERENCIA", months_covered=1, note=f"{DEMO_NOTE}: segundo mes"),
            today,
        )

    if not _has_demo_payment(db, rel_lucia):
        asyncio.run(report_payment(
            db, lucia_user, rel_lucia.id,
            PaymentCreate(paid_on=today - timedelta(days=1), amount=str(rel_lucia.agreed_monthly_price * 2),
                          method="TRANSFERENCIA", months_covered=2, note=f"{DEMO_NOTE}: pago de los dos meses adeudados"),
            _receipt(), today,
        ))

    # --- US-21 / US-62: chat Lucas–Valentina --------------------------------------------
    has_chat = db.scalar(select(ConversationMessage.id).where(ConversationMessage.relationship_id == rel_valentina.id))
    if has_chat is None:
        send_message(db, valentina_user, rel_valentina.id, MessageCreate(body="Hola Lucas, ¿podemos pasar el entrenamiento del jueves al viernes?"))
        send_message(db, lucas_user, rel_valentina.id, MessageCreate(body="¡Hola Valentina! Sí, sin problema: lo pasamos al viernes."))
        answered = create_query(
            db, valentina_user, rel_valentina.id,
            TechnicalQueryCreate(exercise_id=_exercise(db, lucas, "Sentadilla con Barra").id,
                                 body="En la última serie se me levantan los talones al bajar. ¿Qué estoy haciendo mal?", set_number=3),
        )
        send_message(
            db, lucas_user, rel_valentina.id,
            MessageCreate(body="Bajá hasta el paralelo con el peso en los talones y el pecho arriba. Esta semana bajá un 10 % la carga.",
                          reply_to_message_id=answered.id, pin_as_technical_note=True),
        )
        create_query(
            db, valentina_user, rel_valentina.id,
            TechnicalQueryCreate(exercise_id=_exercise(db, lucas, "Peso Muerto").id,
                                 body="En el peso muerto siento la zona lumbar al subir. ¿Cómo lo corrijo?"),
        )
        send_message(db, valentina_user, rel_valentina.id, MessageCreate(body="¡Gracias! Te dejé otra consulta sobre el peso muerto."))

    # --- US-67: logros de Valentina y felicitación de Lucas --------------------------------
    evaluate_achievements(db, valentina)
    db.commit()
    streak_achievement = db.scalar(
        select(StudentAchievement).where(
            StudentAchievement.student_id == valentina.id, StudentAchievement.code == "STREAK_4_WEEKS"
        )
    )
    if streak_achievement is not None and db.scalar(
        select(AchievementCongratulation.id).where(AchievementCongratulation.achievement_id == streak_achievement.id)
    ) is None:
        congratulate(db, lucas_user, streak_achievement.id, "¡4 semanas seguidas, Valentina! Esa constancia se nota en tus cargas.")

    tomas_sessions = db.scalar(
        select(func.count(WorkoutSession.id)).where(
            WorkoutSession.student_id == _student(db, TOMAS).id, WorkoutSession.finished_at.is_not(None)
        )
    )
    mateo_days = (compute_due_date(rel_mateo.start_date, 0) - today).days
    return {
        "Lucas (entrenador)": "Suscripciones con los 3 estados y 1 pago por confirmar; mensajes y 1 consulta técnica pendiente; Sofía para dar de baja.",
        "Valentina": "Al día · racha de 5 semanas · logros + felicitación y nota técnica al iniciar su próxima sesión.",
        "Mateo": f"Suscripción por vencer en {mateo_days} {'día' if mateo_days == 1 else 'días'} (aviso en el inicio).",
        "Lucía": "Suscripción vencida: rutina bloqueada y pago informado pendiente.",
        "Joaquín": "Racha cortada: recibe el mensaje de aliento al abrir la app.",
        "Tomás (Gonzalo)": f"{tomas_sessions} sesiones finalizadas: al terminar la próxima desbloquea '10 sesiones'."
        if tomas_sessions == 9 else f"{tomas_sessions} sesiones finalizadas (la celebración en vivo necesita 9; resembrá la demo).",
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepara datos idempotentes de Sprint Review para Sprint 6 sobre usuarios @demo.settoset.com."
    )
    parser.add_argument(
        "--production-demo",
        action="store_true",
        help="Permite preparar escenarios @demo en PostgreSQL de producción; requiere confirmación.",
    )
    parser.add_argument(
        "--confirm-production-demo",
        action="store_true",
        help="Confirma que autorizás escribir/actualizar escenarios de cuentas @demo en producción.",
    )
    args = parser.parse_args()

    production_password: str | None = None
    if args.production_demo:
        if not args.confirm_production_demo:
            parser.error("Usá --confirm-production-demo para confirmar la escritura en producción.")
        if APP_ENV != "production":
            parser.error("--production-demo requiere APP_ENV=production.")
        if engine.dialect.name != "postgresql":
            parser.error("--production-demo sólo se permite contra PostgreSQL.")

        production_password = os.getenv("DEMO_SEED_PASSWORD", "")
        if (
            len(production_password) < 12
            or len(production_password) > 128
            or any(char.isspace() for char in production_password)
            or not any(char.isupper() for char in production_password)
            or not any(char.islower() for char in production_password)
            or not any(char.isdigit() for char in production_password)
        ):
            parser.error(
                "Configurá DEMO_SEED_PASSWORD con entre 12 y 128 caracteres, sin espacios, "
                "y al menos una mayúscula, una minúscula y un número."
            )

        # En producción sólo comprobamos el esquema. Las migraciones pertenecen al despliegue,
        # nunca al script de preparación de datos.
        schema_inspector = inspect(engine)
        existing_tables = set(schema_inspector.get_table_names())
        missing_schema_items: list[str] = []
        for table_name, table in Base.metadata.tables.items():
            if table_name not in existing_tables:
                missing_schema_items.append(table_name)
                continue
            existing_columns = {
                column["name"] for column in schema_inspector.get_columns(table_name)
            }
            missing_schema_items.extend(
                f"{table_name}.{column.name}"
                for column in table.columns
                if column.name not in existing_columns
            )
        if missing_schema_items:
            parser.error(
                "Faltan tablas o columnas del esquema actual. Desplegá primero la versión y aplicá "
                "sus migraciones: " + ", ".join(sorted(missing_schema_items))
            )
    else:
        if args.confirm_production_demo:
            parser.error("--confirm-production-demo sólo se usa junto con --production-demo.")
        if APP_ENV == "production" or engine.dialect.name == "postgresql":
            parser.error(
                "En producción/PostgreSQL usá --production-demo --confirm-production-demo."
            )

        # En desarrollo/testing se permite inicializar una base local vacía.
        Base.metadata.create_all(bind=engine)
        apply_migrations(engine)

    if os.getenv("DISABLE_DEMO_PREP") == "1":
        return

    with SessionLocal() as db:
        if production_password is not None:
            # El seed sólo crea/actualiza cuentas @demo y sincroniza sus credenciales gestionadas.
            seed_demo_data(
                db,
                verbose=False,
                password=production_password,
                update_existing_demo_passwords=True,
            )
        summary = prepare_sprint6_demo_data(
            db,
            password=production_password or DEMO_PASSWORD,
        )

    print("Datos de Sprint Review (Sprint 6) preparados correctamente.\n")
    for who, what in summary.items():
        print(f" • {who}: {what}")
    if production_password is not None:
        print("La contraseña de las cuentas @demo está configurada mediante DEMO_SEED_PASSWORD.")
    else:
        print(f"\nContraseña de cuentas @demo.settoset.com: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
