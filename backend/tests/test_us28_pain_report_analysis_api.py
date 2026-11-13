from sqlalchemy import select

from backend.src.models.body_map_report import BodyMapPainReport, BodyMapPainReportZone
from backend.src.models.exercise import Exercise
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.user import User
from backend.src.models.workout_log import WorkoutSession, WorkoutSetLog
from backend.tests.test_us61_body_map_pain_report_api import (
    REPORTS_PATH,
    STUDENT_REPORTS_PATH,
    TRAINER_STUDENTS_PATH,
    register_and_login,
    setup_test_environment,
)


def test_trainer_zone_history_includes_exercise_routine_day_and_muscle_group(client):
    api, sessions = client
    trainer = register_and_login(api, "entrenador_us28@example.com", "TRAINER")
    student = register_and_login(api, "alumno_us28@example.com", "STUDENT")
    data = setup_test_environment(sessions, "alumno_us28@example.com", "entrenador_us28@example.com")

    in_exercise = api.post(
        REPORTS_PATH,
        headers=student,
        json={
            "session_id": data["session_id"],
            "exercise_id": data["exercise_id"],
            "context": "IN_EXERCISE",
            "zones": [{"zone": "Shoulder", "intensity": "PAIN"}, {"zone": "Elbow", "intensity": "DISCOMFORT"}],
        },
    )
    post_session = api.post(
        REPORTS_PATH,
        headers=student,
        json={
            "session_id": data["session_id"],
            "context": "POST_SESSION",
            "zones": [{"zone": "Hip", "intensity": "DISCOMFORT"}],
        },
    )
    assert in_exercise.status_code == 201
    assert post_session.status_code == 201

    response = api.get(
        f"{TRAINER_STUDENTS_PATH}/{data['student_profile_id']}/body-map-reports/by-zone",
        headers=trainer,
    )

    assert response.status_code == 200
    items = {item["zone"]: item for item in response.json()}
    assert set(items) == {"Shoulder", "Elbow", "Hip"}
    assert items["Shoulder"]["exercise_muscle_group"] == "Pecho"
    assert items["Shoulder"]["exercise_name"]
    assert items["Shoulder"]["session_day_name"]
    assert items["Elbow"]["intensity"] == "DISCOMFORT"
    assert items["Hip"]["exercise_muscle_group"] is None
    assert items["Hip"]["exercise_name"] is None
    assert items["Hip"]["session_day_name"] == items["Shoulder"]["session_day_name"]


def test_student_zone_history_also_exposes_muscle_group(client):
    api, sessions = client
    student = register_and_login(api, "alumno_us28_self@example.com", "STUDENT")
    data = setup_test_environment(sessions, "alumno_us28_self@example.com")
    api.post(
        REPORTS_PATH,
        headers=student,
        json={
            "session_id": data["session_id"],
            "exercise_id": data["exercise_id"],
            "context": "IN_EXERCISE",
            "zones": [{"zone": "Knee", "intensity": "PAIN"}],
        },
    )

    history = api.get("/api/v1/students/me/body-map-reports/by-zone", headers=student).json()

    assert history[0]["exercise_muscle_group"] == "Pecho"


def test_trainer_only_sees_reports_from_their_active_relationship_not_previous_trainers(client):
    api, sessions = client
    trainer_a = register_and_login(api, "entrenador_previo@example.com", "TRAINER")
    trainer_b = register_and_login(api, "entrenador_actual@example.com", "TRAINER")
    student = register_and_login(api, "alumno_cambio_trainer@example.com", "STUDENT")

    # 1. Vínculo original con Entrenador A: genera reportes IN_EXERCISE, POST_SESSION y legado sin relationship_id.
    data_a = setup_test_environment(sessions, "alumno_cambio_trainer@example.com", "entrenador_previo@example.com")
    rep_a1 = api.post(
        REPORTS_PATH,
        headers=student,
        json={
            "session_id": data_a["session_id"],
            "exercise_id": data_a["exercise_id"],
            "context": "IN_EXERCISE",
            "zones": [{"zone": "Shoulder", "intensity": "PAIN"}],
        },
    )
    rep_a2 = api.post(
        REPORTS_PATH,
        headers=student,
        json={"context": "POST_SESSION", "zones": [{"zone": "Knee", "intensity": "DISCOMFORT"}]},
    )
    assert rep_a1.status_code == 201
    assert rep_a2.status_code == 201

    from datetime import UTC, datetime
    from decimal import Decimal

    from backend.src.models.trainer_profile import TrainerProfile

    now = datetime.now(UTC).replace(tzinfo=None)
    with sessions() as db:
        # Reporte legado vinculado solo por session_id a la sesión de A (relationship_id = None).
        legacy_a = BodyMapPainReport(
            student_id=data_a["student_profile_id"],
            relationship_id=None,
            session_id=data_a["session_id"],
            exercise_id=data_a["exercise_id"],
            context="IN_EXERCISE",
            action_taken="NONE",
            created_at=now,
        )
        legacy_a.zones.append(BodyMapPainReportZone(zone="Wrist", intensity="DISCOMFORT", created_at=now))
        # Reporte huérfano sin relationship_id ni session_id.
        orphan = BodyMapPainReport(
            student_id=data_a["student_profile_id"],
            relationship_id=None,
            session_id=None,
            exercise_id=None,
            context="POST_SESSION",
            action_taken="NONE",
            created_at=now,
        )
        orphan.zones.append(BodyMapPainReportZone(zone="Neck", intensity="PAIN", created_at=now))
        db.add_all([legacy_a, orphan])

        # 2. Finalizar relación con A y vincular alumno con Entrenador B.
        rel_a = db.get(TrainingRelationship, data_a["relationship_id"])
        rel_a.status = "TERMINATED"

        user_b = db.scalar(select(User).where(User.email == "entrenador_actual@example.com"))
        trainer_b_profile = TrainerProfile(
            user_id=user_b.id,
            full_name="Entrenador B",
            status="PUBLISHED",
            created_at=now,
            updated_at=now,
        )
        db.add(trainer_b_profile)
        db.flush()
        plan_b = TrainingPlan(
            trainer_id=trainer_b_profile.id,
            title="Plan B",
            monthly_price=Decimal("20000.00"),
            currency="ARS",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(plan_b)
        db.flush()
        rel_b = TrainingRelationship(
            student_id=data_a["student_profile_id"],
            trainer_id=trainer_b_profile.id,
            plan_id=plan_b.id,
            agreed_monthly_price=Decimal("20000.00"),
            agreed_currency="ARS",
            status="ACTIVE",
            start_date=now.date(),
        )
        db.add(rel_b)
        db.flush()
        ex_b = Exercise(
            trainer_id=trainer_b_profile.id,
            name="Remo con barra",
            description="Espalda",
            category="FUERZA",
            target_muscle_group="Espalda",
            equipment_needed="Barra",
            contraindicated_zones=[],
            created_at=now,
            updated_at=now,
        )
        db.add(ex_b)
        db.flush()
        session_b = WorkoutSession(
            student_id=data_a["student_profile_id"],
            relationship_id=rel_b.id,
            routine_id="routine-b",
            day_name="Día B1",
            modality="GYM",
            started_at=now,
        )
        db.add(session_b)
        db.flush()
        db.add(
            WorkoutSetLog(
                student_id=data_a["student_profile_id"],
                relationship_id=rel_b.id,
                routine_id="routine-b",
                day_name="Día B1",
                exercise_id=ex_b.id,
                exercise_name=ex_b.name,
                modality="GYM",
                set_number=1,
                reps_completed="10",
                weight_kg=Decimal("40.00"),
                session_id=session_b.id,
                recorded_at=now,
            )
        )
        # Reporte legado dentro de la relación B sin relationship_id directo, pero vinculado vía session_b.
        legacy_b = BodyMapPainReport(
            student_id=data_a["student_profile_id"],
            relationship_id=None,
            session_id=session_b.id,
            exercise_id=ex_b.id,
            context="IN_EXERCISE",
            action_taken="NONE",
            created_at=now,
        )
        legacy_b.zones.append(BodyMapPainReportZone(zone="Lower back", intensity="PAIN", created_at=now))
        db.add(legacy_b)
        db.commit()
        session_b_id = session_b.id
        ex_b_id = ex_b.id
        legacy_b_id = legacy_b.id

    # Reporte normal creado durante el vínculo activo con Entrenador B.
    rep_b = api.post(
        REPORTS_PATH,
        headers=student,
        json={
            "session_id": session_b_id,
            "exercise_id": ex_b_id,
            "context": "IN_EXERCISE",
            "zones": [{"zone": "Ankle and foot", "intensity": "DISCOMFORT"}],
        },
    )
    assert rep_b.status_code == 201
    rep_b_id = rep_b.json()["id"]

    # Entrenador B solo ve los reportes de su vínculo (rep_b y legacy_b).
    reports_b = api.get(
        f"{TRAINER_STUDENTS_PATH}/{data_a['student_profile_id']}/body-map-reports",
        headers=trainer_b,
    )
    assert reports_b.status_code == 200
    assert {item["id"] for item in reports_b.json()} == {rep_b_id, legacy_b_id}

    zones_b = api.get(
        f"{TRAINER_STUDENTS_PATH}/{data_a['student_profile_id']}/body-map-reports/by-zone",
        headers=trainer_b,
    )
    assert zones_b.status_code == 200
    zone_items = {item["zone"]: item for item in zones_b.json()}
    assert set(zone_items) == {"Ankle and foot", "Lower back"}
    assert zone_items["Ankle and foot"]["exercise_muscle_group"] == "Espalda"
    assert zone_items["Ankle and foot"]["session_day_name"] == "Día B1"
    assert zone_items["Lower back"]["intensity"] == "PAIN"

    # Filtros siguen funcionando sin exponer datos ajenos.
    pain_only_b = api.get(
        f"{TRAINER_STUDENTS_PATH}/{data_a['student_profile_id']}/body-map-reports/by-zone",
        headers=trainer_b,
        params={"intensity": "PAIN"},
    )
    assert [item["zone"] for item in pain_only_b.json()] == ["Lower back"]

    # Entrenador A ya no tiene vínculo activo -> 403.
    assert (
        api.get(
            f"{TRAINER_STUDENTS_PATH}/{data_a['student_profile_id']}/body-map-reports",
            headers=trainer_a,
        ).status_code
        == 403
    )

    # El alumno conserva acceso completo a todo su historial (A + B + legado + huérfano).
    student_reports = api.get(STUDENT_REPORTS_PATH, headers=student)
    assert student_reports.status_code == 200
    assert len(student_reports.json()) == 6
    student_zones = api.get(f"{STUDENT_REPORTS_PATH}/by-zone", headers=student)
    assert student_zones.status_code == 200
    assert {item["zone"] for item in student_zones.json()} == {
        "Shoulder",
        "Knee",
        "Wrist",
        "Neck",
        "Lower back",
        "Ankle and foot",
    }
