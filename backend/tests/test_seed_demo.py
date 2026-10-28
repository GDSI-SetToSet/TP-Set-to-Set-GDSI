from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.scripts.seed_demo import (
    DEMO_DOMAIN,
    DEMO_PASSWORD,
    clean_demo_data,
    seed_demo_data,
)
from backend.src.core.database import Base
from backend.src.models.health_questionnaire import HealthQuestionnaire
from backend.src.models.notification import Notification
from backend.src.models.student_profile import StudentProfile
from backend.src.models.trainer_profile import TrainerProfile
from backend.src.models.training_plan import TrainingPlan
from backend.src.models.training_relationship import TrainingRelationship
from backend.src.models.training_request import TrainingRequest
from backend.src.models.user import User
from backend.src.schemas.discovery import TrainerSearchFilters
from backend.src.services.auth_service import login_user
from backend.src.services.discovery_service import (
    create_training_request,
    get_public_detail,
    search_trainers,
)
from backend.src.services.trainer_service import quota_summary


def create_test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return session_factory()


def test_seed_demo_creates_data():
    db = create_test_db()
    try:
        stats = seed_demo_data(db, verbose=False)

        assert stats["trainers"] == 5
        assert stats["plans"] >= 10
        assert stats["students"] == 8
        assert stats["questionnaires"] == 8
        assert stats["requests"] == 4
        assert stats["relationships"] == 2

        # Verificar que existan en la base de datos
        trainers = db.scalars(select(TrainerProfile)).all()
        assert len(trainers) == 5
        for t in trainers:
            assert t.status == "PUBLISHED"
            assert t.full_name is not None
            assert t.specialty is not None
            assert len(t.plans) >= 2

        students = db.scalars(select(StudentProfile)).all()
        assert len(students) == 8
        for s in students:
            assert s.status == "PUBLISHED"
            assert s.first_name is not None
            assert s.last_name is not None
            assert len(s.fitness_goals) >= 1
    finally:
        db.close()


def test_seed_demo_is_idempotent():
    db = create_test_db()
    try:
        # Primera ejecución
        stats1 = seed_demo_data(db, verbose=False)
        total_users1 = db.scalar(select(func.count(User.id)))
        total_plans1 = db.scalar(select(func.count(TrainingPlan.id)))
        total_requests1 = db.scalar(select(func.count(TrainingRequest.id)))

        # Segunda ejecución consecutiva
        stats2 = seed_demo_data(db, verbose=False)
        total_users2 = db.scalar(select(func.count(User.id)))
        total_plans2 = db.scalar(select(func.count(TrainingPlan.id)))
        total_requests2 = db.scalar(select(func.count(TrainingRequest.id)))

        assert stats1 == stats2
        assert total_users1 == total_users2
        assert total_plans1 == total_plans2
        assert total_requests1 == total_requests2
    finally:
        db.close()


def test_demo_users_can_authenticate():
    db = create_test_db()
    try:
        seed_demo_data(db, verbose=False)

        demo_users = db.scalars(select(User).where(User.email.like(f"%@{DEMO_DOMAIN}"))).all()
        assert len(demo_users) == 13  # 5 entrenadores + 8 alumnos

        for user in demo_users:
            authed_user, token, _ = login_user(db, user.email, DEMO_PASSWORD)
            assert authed_user.id == user.id
            assert token is not None
            assert len(token) > 20
    finally:
        db.close()


def test_trainer_search_and_filtering():
    db = create_test_db()
    try:
        seed_demo_data(db, verbose=False)

        # 1. Búsqueda sin filtros con only_available=True (omite a Gonzalo Morales que tiene cupos agotados)
        res_available = search_trainers(db, TrainerSearchFilters(only_available=True))
        assert res_available.total == 4
        trainer_names = [t.full_name for t in res_available.items]
        assert "Gonzalo Morales" not in trainer_names
        assert "Lucas Benítez" in trainer_names

        # 2. Búsqueda incluyendo entrenadores sin cupos disponibles
        res_all = search_trainers(db, TrainerSearchFilters(only_available=False))
        assert res_all.total == 5
        all_names = [t.full_name for t in res_all.items]
        assert "Gonzalo Morales" in all_names

        # 3. Filtrar por especialidad "Fuerza"
        res_fuerza = search_trainers(db, TrainerSearchFilters(specialty="Fuerza", only_available=False))
        assert res_fuerza.total == 2
        fuerza_names = {t.full_name for t in res_fuerza.items}
        assert fuerza_names == {"Lucas Benítez", "Gonzalo Morales"}

        # 4. Filtrar por especialidad "Movilidad"
        res_mov = search_trainers(db, TrainerSearchFilters(specialty="Movilidad", only_available=True))
        assert res_mov.total == 1
        assert res_mov.items[0].full_name == "Camila Navarro"

        # 5. Filtrar por precio máximo $20.000
        res_price = search_trainers(db, TrainerSearchFilters(max_price=20000.0, only_available=False))
        assert res_price.total == 1
        assert res_price.items[0].full_name == "Mariana Vega"
    finally:
        db.close()


def test_trainer_public_detail_and_quota():
    db = create_test_db()
    try:
        seed_demo_data(db, verbose=False)

        lucas_user = db.scalar(select(User).where(User.email == f"lucas.benitez@{DEMO_DOMAIN}"))
        assert lucas_user is not None
        lucas_detail = get_public_detail(db, lucas_user.trainer_profile.id)

        assert lucas_detail.full_name == "Lucas Benítez"
        assert len(lucas_detail.plans) == 3
        assert lucas_detail.max_students == 15
        assert lucas_detail.has_available_quota is True

        gonzalo_user = db.scalar(select(User).where(User.email == f"gonzalo.morales@{DEMO_DOMAIN}"))
        assert gonzalo_user is not None
        qs = quota_summary(db, gonzalo_user.trainer_profile)
        assert qs["max_students"] == 1
        assert qs["active_students"] == 1
        assert qs["available_slots"] == 0
        assert qs["has_available_quota"] is False
    finally:
        db.close()


def test_student_live_request_flow():
    db = create_test_db()
    try:
        seed_demo_data(db, verbose=False)

        # Mateo Gómez (estudiante1) no tiene relación previa con Camila Navarro (entrenadora 4)
        mateo = db.scalar(select(User).where(User.email == f"mateo.gomez@{DEMO_DOMAIN}"))
        camila = db.scalar(select(User).where(User.email == f"camila.navarro@{DEMO_DOMAIN}"))
        assert mateo is not None
        assert camila is not None

        plan = camila.trainer_profile.plans[0]

        # Simular creación de solicitud de entrenamiento real
        from backend.src.schemas.discovery import TrainingRequestCreate

        payload = TrainingRequestCreate(
            trainer_id=camila.trainer_profile.id,
            plan_id=plan.id,
            student_message="Hola Camila, me interesa comenzar con tu plan de Readaptación Funcional.",
        )
        created_req = create_training_request(db, mateo, payload)

        assert created_req.status == "PENDING"
        assert created_req.trainer_id == camila.trainer_profile.id
        assert created_req.plan_id == plan.id
        assert created_req.agreed_monthly_price == float(plan.monthly_price)

        # Verificar que el entrenador recibe una notificación
        notif = db.scalar(
            select(Notification).where(
                Notification.recipient_id == camila.id,
                Notification.related_entity_id == created_req.id,
            )
        )
        assert notif is not None
        assert "Mateo Gómez" in notif.message
    finally:
        db.close()


def test_clean_demo_data_preserves_non_demo_records():
    db = create_test_db()
    try:
        # 1. Crear un usuario real / no-demo previo
        real_user = User(
            email="usuario.real@institucional.edu.ar",
            password_hash="some_hash",
            role="STUDENT",
            is_active=True,
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(real_user)
        db.flush()

        real_profile = StudentProfile(
            user_id=real_user.id,
            first_name="Juan",
            last_name="Pérez",
            status="PUBLISHED",
            fitness_goals=["fuerza"],
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(real_profile)
        db.commit()

        # 2. Sembrar datos demo
        seed_demo_data(db, verbose=False)

        assert db.scalar(select(User).where(User.email == "usuario.real@institucional.edu.ar")) is not None
        assert len(db.scalars(select(User)).all()) == 14  # 13 demo + 1 real

        # 3. Limpiar únicamente demo
        counts = clean_demo_data(db, verbose=False)
        assert counts["users"] == 13

        # 4. Verificar que el usuario real sigue intacto
        surviving_user = db.scalar(select(User).where(User.email == "usuario.real@institucional.edu.ar"))
        assert surviving_user is not None
        assert surviving_user.student_profile is not None
        assert surviving_user.student_profile.first_name == "Juan"

        # 5. Verificar que no queda ningún usuario demo
        remaining_demo = db.scalars(select(User).where(User.email.like(f"%@{DEMO_DOMAIN}"))).all()
        assert len(remaining_demo) == 0
    finally:
        db.close()


def test_referential_integrity():
    db = create_test_db()
    try:
        seed_demo_data(db, verbose=False)

        # Verificar que cada plan pertenezca a un entrenador publicado
        plans = db.scalars(select(TrainingPlan)).all()
        for p in plans:
            assert p.trainer is not None
            assert p.trainer.status == "PUBLISHED"
            assert p.monthly_price > Decimal(0)

        # Verificar que cada cuestionario pertenezca a un alumno publicado
        questionnaires = db.scalars(select(HealthQuestionnaire)).all()
        for q in questionnaires:
            student = db.get(StudentProfile, q.student_id)
            assert student is not None
            assert student.status == "PUBLISHED"

        # Verificar que cada solicitud apunte a estudiante, entrenador y plan válidos
        requests = db.scalars(select(TrainingRequest)).all()
        for r in requests:
            assert r.student is not None
            assert r.trainer is not None
            assert r.plan is not None

        # Verificar que cada vínculo activo apunte a entidades válidas
        relationships = db.scalars(select(TrainingRelationship)).all()
        for rel in relationships:
            assert rel.student is not None
            assert rel.trainer is not None
            assert rel.plan is not None
            assert rel.status == "ACTIVE"
    finally:
        db.close()
