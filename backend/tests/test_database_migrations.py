"""Tests de regresión de migraciones de esquema para bases de datos persistentes.

Verifica la actualización de esquemas antiguos sin pérdida de datos,
la operatividad de los endpoints de la biblioteca y la idempotencia.
"""

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.src.api.errors import register_exception_handlers
from backend.src.api.v1.auth import router as auth_router
from backend.src.api.v1.deps import get_db
from backend.src.api.v1.exercises import router as exercises_router
from backend.src.core.database import Base
from backend.src.core.migrations import apply_migrations
from backend.src.core.security import hash_password


def make_legacy_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def create_legacy_database(engine):
    """Crea un esquema antiguo donde las tablas exercises y assigned_routines carecen de las columnas nuevas."""
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE users (
                id VARCHAR(36) PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(16) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                failed_login_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until DATETIME,
                created_at DATETIME NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE user_sessions (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL,
                jti VARCHAR(36) UNIQUE NOT NULL,
                expires_at DATETIME NOT NULL,
                revoked_at DATETIME
            )
        """))
        conn.execute(text("""
            CREATE TABLE trainer_profiles (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) UNIQUE NOT NULL,
                full_name VARCHAR(100),
                contact_phone VARCHAR(50),
                specialty VARCHAR(100),
                status VARCHAR(16) NOT NULL DEFAULT 'DRAFT',
                bio TEXT,
                certifications TEXT,
                max_students INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """))
        # Tabla exercises en versión antigua (US-05: sin technical_cues, breathing_cues ni contraindicated_zones)
        conn.execute(text("""
            CREATE TABLE exercises (
                id VARCHAR(36) PRIMARY KEY,
                trainer_id VARCHAR(36) NOT NULL,
                name VARCHAR(150) NOT NULL,
                description TEXT NOT NULL,
                category VARCHAR(16) NOT NULL,
                target_muscle_group VARCHAR(100) NOT NULL,
                equipment_needed VARCHAR(150) NOT NULL,
                has_no_materials_alternative BOOLEAN NOT NULL,
                video_url VARCHAR(500),
                video_platform VARCHAR(12) NOT NULL,
                deleted_at DATETIME,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """))
        # Tablas de rutinas en versión antigua
        conn.execute(text("""
            CREATE TABLE assigned_routines (
                id VARCHAR(36) PRIMARY KEY,
                trainer_id VARCHAR(36) NOT NULL,
                student_id VARCHAR(36) NOT NULL,
                template_id VARCHAR(36),
                name VARCHAR(150) NOT NULL,
                duration_weeks INTEGER NOT NULL,
                intensity VARCHAR(16) NOT NULL,
                status VARCHAR(16) NOT NULL,
                adaptation_summary TEXT,
                approved_at DATETIME,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE assigned_routine_days (
                id VARCHAR(36) PRIMARY KEY,
                routine_id VARCHAR(36) NOT NULL,
                order_index INTEGER NOT NULL,
                name VARCHAR(100) NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE assigned_routine_blocks (
                id VARCHAR(36) PRIMARY KEY,
                day_id VARCHAR(36) NOT NULL,
                order_index INTEGER NOT NULL,
                name VARCHAR(100) NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE assigned_routine_exercises (
                id VARCHAR(36) PRIMARY KEY,
                block_id VARCHAR(36) NOT NULL,
                exercise_id VARCHAR(36) NOT NULL,
                order_index INTEGER NOT NULL,
                sets INTEGER NOT NULL,
                reps VARCHAR(50) NOT NULL,
                rest_seconds INTEGER NOT NULL,
                adaptation_notes VARCHAR(255)
            )
        """))


def test_migration_upgrades_legacy_schema_preserves_data_and_enables_api():
    """Escenarios 1 a 8: Migración de esquema antiguo, preservación de datos, API GET/POST e idempotencia."""
    engine = make_legacy_engine()
    create_legacy_database(engine)

    # 1. Sembrar entrenador y ejercicio preexistente en la base antigua
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO users (id, email, password_hash, role, is_active, created_at)
                VALUES ('user-t1', 'trainer_legacy@example.com', :pwd, 'TRAINER', 1, :now)
            """),
            {"pwd": hash_password("StrongPass123!"), "now": now},
        )
        conn.execute(
            text("""
                INSERT INTO trainer_profiles (id, user_id, full_name, status, max_students, created_at, updated_at)
                VALUES ('prof-t1', 'user-t1', 'Entrenador Legado', 'PUBLISHED', 10, :now, :now)
            """),
            {"now": now},
        )
        conn.execute(
            text("""
                INSERT INTO exercises (
                    id, trainer_id, name, description, category, target_muscle_group,
                    equipment_needed, has_no_materials_alternative, video_platform, created_at, updated_at
                ) VALUES (
                    'ex-legacy-1', 'prof-t1', 'Press de Banca Antiguo', 'Ejercicio pectoral histórico',
                    'FUERZA', 'Pectoral', 'Barra y banco', 0, 'NONE', :now, :now
                )
            """),
            {"now": now},
        )

    # 2. Ejecutar la migración
    applied = apply_migrations(engine)
    assert "exercises.technical_cues" in applied
    assert "exercises.breathing_cues" in applied
    assert "exercises.contraindicated_zones" in applied
    assert "assigned_routines.has_no_materials_alternative" in applied
    assert "assigned_routine_days.estimated_duration_minutes" in applied
    assert "assigned_routine_blocks.estimated_duration_minutes" in applied
    assert "assigned_routine_exercises.target_weight_kg" in applied

    # 3. Verificar que las columnas existen en la base de datos
    inspector = inspect(engine)
    exercise_cols = {c["name"] for c in inspector.get_columns("exercises")}
    assert "technical_cues" in exercise_cols
    assert "breathing_cues" in exercise_cols
    assert "contraindicated_zones" in exercise_cols

    # 4. Confirmar que el registro anterior sigue intacto
    with engine.connect() as conn:
        stored = conn.execute(
            text("SELECT id, name, description, technical_cues, contraindicated_zones FROM exercises WHERE id='ex-legacy-1'")
        ).fetchone()
        assert stored is not None
        assert stored[0] == "ex-legacy-1"
        assert stored[1] == "Press de Banca Antiguo"
        assert stored[3] is None  # technical_cues en NULL
        assert stored[4] == "[]"  # contraindicated_zones en default '[]'

    # 5. Probar endpoints HTTP contra la base migrada
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(auth_router)
    app.include_router(exercises_router)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    # Login como entrenador
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "trainer_legacy@example.com", "password": "StrongPass123!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 5. Consultar la biblioteca mediante GET /api/v1/exercises
    get_resp = client.get("/api/v1/exercises", headers=headers)
    assert get_resp.status_code == 200
    exercises_list = get_resp.json()
    assert len(exercises_list) == 1
    assert exercises_list[0]["id"] == "ex-legacy-1"
    assert exercises_list[0]["name"] == "Press de Banca Antiguo"
    assert exercises_list[0]["contraindicated_zones"] == []
    assert "updated_at" in exercises_list[0]

    # 6. Crear un nuevo ejercicio mediante POST /api/v1/exercises
    create_payload = {
        "name": "Peso muerto rumano",
        "description": "Foco en isquiosurales y glúteos",
        "technical_cues": "Cadera hacia atrás manteniendo espalda neutra",
        "breathing_cues": "Inhalá al descender y exhalá en la extensión",
        "category": "FUERZA",
        "target_muscle_group": "Isquiosurales",
        "equipment_needed": "Barra olímpica",
        "has_no_materials_alternative": False,
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "contraindicated_zones": ["Lower back"],
    }
    post_resp = client.post("/api/v1/exercises", headers=headers, json=create_payload)
    assert post_resp.status_code == 201, post_resp.text
    new_ex = post_resp.json()
    assert new_ex["name"] == "Peso muerto rumano"
    assert new_ex["technical_cues"] == "Cadera hacia atrás manteniendo espalda neutra"
    assert new_ex["breathing_cues"] == "Inhalá al descender y exhalá en la extensión"
    assert new_ex["contraindicated_zones"] == ["Lower back"]
    assert new_ex["video_platform"] == "YOUTUBE"
    assert "updated_at" in new_ex

    # 7. Consultar nuevamente y verificar que ambos ejercicios aparecen
    get_after_resp = client.get("/api/v1/exercises", headers=headers)
    assert get_after_resp.status_code == 200
    updated_list = get_after_resp.json()
    assert len(updated_list) == 2
    names = {e["name"] for e in updated_list}
    assert "Press de Banca Antiguo" in names
    assert "Peso muerto rumano" in names

    # 8. Idempotencia: ejecutar la migración una segunda vez
    re_applied = apply_migrations(engine)
    assert re_applied == []  # No se aplican cambios adicionales


def test_migration_upgrades_legacy_assigned_routines_columns():
    """Escenario 9: Verifica que las columnas faltantes en tablas de rutinas se agreguen con sus tipos correctos."""
    engine = make_legacy_engine()
    create_legacy_database(engine)

    # Migrar
    apply_migrations(engine)

    inspector = inspect(engine)
    # assigned_routines
    ar_cols = {c["name"]: c for c in inspector.get_columns("assigned_routines")}
    assert "has_no_materials_alternative" in ar_cols
    assert ar_cols["has_no_materials_alternative"]["nullable"] is False

    # assigned_routine_days
    ard_cols = {c["name"]: c for c in inspector.get_columns("assigned_routine_days")}
    assert "estimated_duration_minutes" in ard_cols
    assert ard_cols["estimated_duration_minutes"]["nullable"] is True

    # assigned_routine_blocks
    arb_cols = {c["name"]: c for c in inspector.get_columns("assigned_routine_blocks")}
    assert "estimated_duration_minutes" in arb_cols
    assert arb_cols["estimated_duration_minutes"]["nullable"] is True

    # assigned_routine_exercises
    are_cols = {c["name"]: c for c in inspector.get_columns("assigned_routine_exercises")}
    assert "target_weight_kg" in are_cols
    assert are_cols["target_weight_kg"]["nullable"] is True


def test_fresh_database_initialization_includes_all_columns():
    """Escenario 10: Comprueba que las bases nuevas continúen inicializándose correctamente."""
    engine = make_legacy_engine()
    Base.metadata.create_all(bind=engine)
    apply_migrations(engine)

    inspector = inspect(engine)
    for table_name in ("exercises", "assigned_routines", "assigned_routine_days", "assigned_routine_blocks", "assigned_routine_exercises"):
        assert table_name in inspector.get_table_names()

    ex_cols = {c["name"] for c in inspector.get_columns("exercises")}
    for required in ("technical_cues", "breathing_cues", "contraindicated_zones"):
        assert required in ex_cols


def test_migration_alteration_specification_for_adaptation_notes():
    """Escenario 11: Comprueba que TARGET_TYPE_ALTERATIONS incluya la ampliación a 500 chars para adaptation_notes."""
    from backend.src.core.migrations import TARGET_TYPE_ALTERATIONS

    matching = [
        alt
        for alt in TARGET_TYPE_ALTERATIONS
        if alt.table == "assigned_routine_exercises" and alt.column == "adaptation_notes"
    ]
    assert len(matching) == 1
    assert matching[0].target_length == 500
    assert matching[0].postgres_type == "VARCHAR(500)"


def test_standalone_migrations_registers_all_models_including_personal_records():
    """Escenario 12 (MIGR-01): Comprueba que el módulo de migraciones registre todas las entidades en Base.metadata."""
    import backend.src.core.migrations  # noqa: F401
    from backend.src.core.database import Base

    assert "personal_records" in Base.metadata.tables
    pr_table = Base.metadata.tables["personal_records"]
    assert "student_id" in pr_table.c
    assert "exercise_id" in pr_table.c
    assert "weight_kg" in pr_table.c
    assert "workout_set_log_id" in pr_table.c


def test_apply_migrations_creates_personal_records_table_if_missing():
    """Escenario 13 (MIGR-01): Comprueba que apply_migrations cree la tabla personal_records en una base existente."""
    engine = make_legacy_engine()
    create_legacy_database(engine)
    inspector_before = inspect(engine)
    assert "personal_records" not in inspector_before.get_table_names()

    apply_migrations(engine)

    inspector_after = inspect(engine)
    assert "personal_records" in inspector_after.get_table_names()
    pr_cols = {c["name"] for c in inspector_after.get_columns("personal_records")}
    for col in ("id", "student_id", "exercise_id", "weight_kg", "reps_completed", "workout_set_log_id", "achieved_at"):
        assert col in pr_cols


def test_apply_migrations_adds_rpe_column_to_workout_sessions():
    """Escenario 14 (US-60): Comprueba que apply_migrations incorpore la columna rpe en workout_sessions si falta."""
    engine = make_legacy_engine()
    create_legacy_database(engine)
    # Crear workout_sessions en versión previa sin columna rpe
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE workout_sessions (
                id VARCHAR(36) PRIMARY KEY,
                student_id VARCHAR(36) NOT NULL,
                relationship_id VARCHAR(36) NOT NULL,
                routine_id VARCHAR(36) NOT NULL,
                day_name VARCHAR(100) NOT NULL,
                modality VARCHAR(16) NOT NULL,
                started_at DATETIME NOT NULL,
                finished_at DATETIME
            )
        """))
    inspector_before = inspect(engine)
    cols_before = {c["name"] for c in inspector_before.get_columns("workout_sessions")}
    assert "rpe" not in cols_before

    apply_migrations(engine)

    inspector_after = inspect(engine)
    cols_after = {c["name"] for c in inspector_after.get_columns("workout_sessions")}
    assert "rpe" in cols_after
