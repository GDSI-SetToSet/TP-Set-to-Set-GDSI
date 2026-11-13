"""Tests de regresión de migraciones de esquema para bases de datos persistentes.

Verifica la actualización de esquemas antiguos sin pérdida de datos,
la operatividad de los endpoints de la biblioteca y la idempotencia.
"""

from datetime import UTC, datetime

import pytest
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


def test_migration_adds_notification_navigation_metadata_without_losing_existing_rows():
    engine = make_legacy_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE notifications (
                id VARCHAR(36) PRIMARY KEY,
                recipient_id VARCHAR(36) NOT NULL,
                type VARCHAR(50) NOT NULL,
                title VARCHAR(150) NOT NULL,
                message TEXT NOT NULL,
                related_entity_type VARCHAR(50),
                related_entity_id VARCHAR(36),
                is_read BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                read_at DATETIME
            )
        """))
        conn.execute(text("""
            INSERT INTO notifications (
                id, recipient_id, type, title, message, related_entity_type,
                related_entity_id, is_read, created_at
            ) VALUES (
                'notification-legacy', 'trainer-1', 'PAIN_ALERT', 'Dolor',
                'Mensaje', 'BODY_MAP_PAIN_REPORT', 'report-1', 0, '2026-01-01'
            )
        """))

    applied = apply_migrations(engine)

    assert "notifications.related_student_id" in applied
    assert "notifications.related_session_id" in applied
    columns = {column["name"] for column in inspect(engine).get_columns("notifications")}
    assert "related_student_id" in columns
    assert "related_session_id" in columns
    with engine.connect() as conn:
        stored = conn.execute(text("""
            SELECT related_entity_id, related_student_id, related_session_id
            FROM notifications WHERE id = 'notification-legacy'
        """)).one()
    assert stored == ("report-1", None, None)
    engine.dispose()


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


def test_check_constraint_migration_and_model_specification_for_workout_sessions_rpe():
    """Escenario 15 (BAJ-01): Verifica la definición de ck_workout_sessions_rpe_range en modelo y migraciones."""
    from backend.src.core.database import Base
    from backend.src.core.migrations import TARGET_CHECK_CONSTRAINTS

    # 1. Comprobar que TARGET_CHECK_CONSTRAINTS incluya la restricción para PostgreSQL / motores estrictos
    ck_mig = next((ck for ck in TARGET_CHECK_CONSTRAINTS if ck.table == "workout_sessions" and ck.name == "ck_workout_sessions_rpe_range"), None)
    assert ck_mig is not None
    assert "rpe >= 1 AND rpe <= 10" in ck_mig.expression
    assert "rpe IS NULL" in ck_mig.expression

    # 2. Comprobar que el modelo Declarative Base.metadata registre la restricción CheckConstraint en workout_sessions
    table = Base.metadata.tables["workout_sessions"]
    ck_model = next((c for c in table.constraints if c.name == "ck_workout_sessions_rpe_range"), None)
    assert ck_model is not None

    # 3. Comprobar que en un motor fresco la restricción sea creada
    engine = make_legacy_engine()
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    db_cks = {c.get("name") for c in inspector.get_check_constraints("workout_sessions")}
    assert "ck_workout_sessions_rpe_range" in db_cks


def test_sqlite_legacy_table_rebuild_migrates_check_constraint_and_preserves_structure_and_data():
    """Escenarios A, B, C y D (BAJ-01 SQLite Legacy):
    Verifica que una base SQLite preexistente con tabla workout_sessions antigua:
    1. Reciba la restricción CHECK en su esquema real (Escenario A).
    2. Aplique la integridad de rango directa: NULL, 1..10 permitidos; 0 y 11 rechazados (Escenario B).
    3. Conserve todas las columnas, PK, FKs, índices y registros existentes (Escenario C).
    4. Sea completamente idempotente ante ejecuciones sucesivas de apply_migrations (Escenario D).
    """
    engine = make_legacy_engine()

    # 1. Sembrar estructura SQLite antigua con foreign keys y filas preexistentes
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE student_profiles (
                id VARCHAR(36) PRIMARY KEY
            )
        """))
        conn.execute(text("""
            CREATE TABLE training_relationships (
                id VARCHAR(36) PRIMARY KEY
            )
        """))
        conn.execute(text("""
            CREATE TABLE workout_sessions (
                id VARCHAR(36) PRIMARY KEY,
                student_id VARCHAR(36) NOT NULL,
                relationship_id VARCHAR(36) NOT NULL,
                routine_id VARCHAR(36) NOT NULL,
                day_name VARCHAR(100) NOT NULL,
                modality VARCHAR(16) NOT NULL,
                started_at DATETIME NOT NULL,
                finished_at DATETIME,
                rpe INTEGER,
                FOREIGN KEY(student_id) REFERENCES student_profiles (id) ON DELETE CASCADE,
                FOREIGN KEY(relationship_id) REFERENCES training_relationships (id) ON DELETE CASCADE
            )
        """))
        conn.execute(text("CREATE INDEX ix_custom_session_day ON workout_sessions (day_name)"))
        conn.execute(text("""
            CREATE TABLE workout_set_logs (
                id VARCHAR(36) PRIMARY KEY,
                session_id VARCHAR(36),
                FOREIGN KEY (session_id) REFERENCES workout_sessions (id) ON DELETE SET NULL
            )
        """))
        conn.execute(text("INSERT INTO student_profiles VALUES ('st1')"))
        conn.execute(text("INSERT INTO training_relationships VALUES ('rel1')"))
        conn.execute(text("INSERT INTO workout_sessions VALUES ('s1', 'st1', 'rel1', 'rou1', 'Día 1', 'GYM', '2026-01-01', '2026-01-01', NULL)"))
        conn.execute(text("INSERT INTO workout_sessions VALUES ('s2', 'st1', 'rel1', 'rou1', 'Día 2', 'GYM', '2026-01-02', '2026-01-02', 5)"))
        conn.execute(text("INSERT INTO workout_set_logs VALUES ('log1', 's1')"))

    # Antes de la migración: la restricción CHECK no existe en workout_sessions
    insp_before = inspect(engine)
    assert "ck_workout_sessions_rpe_range" not in {c.get("name") for c in insp_before.get_check_constraints("workout_sessions")}

    # Ejecutar la migración real
    results = apply_migrations(engine)
    assert any("sqlite_table_rebuild" in r for r in results)

    # Escenario A y C: Comprobar que la restricción CHECK aparece en el esquema real y se preservan columnas/índices
    insp_after = inspect(engine)
    db_cks = insp_after.get_check_constraints("workout_sessions")
    assert any(c.get("name") == "ck_workout_sessions_rpe_range" for c in db_cks)

    cols = {c["name"] for c in insp_after.get_columns("workout_sessions")}
    for expected_col in ("id", "student_id", "relationship_id", "routine_id", "day_name", "modality", "started_at", "finished_at", "rpe"):
        assert expected_col in cols

    indexes = {i["name"] for i in insp_after.get_indexes("workout_sessions")}
    assert "ix_custom_session_day" in indexes
    assert "ix_workout_sessions_student_id" in indexes
    assert "ix_workout_sessions_relationship_id" in indexes
    assert "ix_workout_sessions_routine_id" in indexes

    # Comprobar que los registros se conservaron íntegros (incluyendo rpe=NULL histórico)
    with engine.connect() as conn:
        s1 = conn.execute(text("SELECT * FROM workout_sessions WHERE id = 's1'")).fetchone()
        assert s1 is not None and s1[8] is None
        s2 = conn.execute(text("SELECT * FROM workout_sessions WHERE id = 's2'")).fetchone()
        assert s2 is not None and s2[8] == 5
        log = conn.execute(text("SELECT * FROM workout_set_logs WHERE id = 'log1'")).fetchone()
        assert log is not None and log[1] == "s1"

    # Escenario B: Integridad directa a nivel motor
    with engine.begin() as conn:
        # rpe = NULL: permitido
        conn.execute(text("INSERT INTO workout_sessions VALUES ('s_null', 'st1', 'rel1', 'rou1', 'D1', 'GYM', '2026-01-01', '2026-01-01', NULL)"))
        # rpe = 1: permitido
        conn.execute(text("INSERT INTO workout_sessions VALUES ('s_min', 'st1', 'rel1', 'rou1', 'D1', 'GYM', '2026-01-01', '2026-01-01', 1)"))
        # rpe = 10: permitido
        conn.execute(text("INSERT INTO workout_sessions VALUES ('s_max', 'st1', 'rel1', 'rou1', 'D1', 'GYM', '2026-01-01', '2026-01-01', 10)"))

    with engine.connect() as conn:
        # rpe = 0: rechazado por CHECK a nivel de motor relacional
        with pytest.raises(Exception) as exc_0, engine.begin() as conn_sub:
            conn_sub.execute(text("INSERT INTO workout_sessions VALUES ('s_bad0', 'st1', 'rel1', 'rou1', 'D1', 'GYM', '2026-01-01', '2026-01-01', 0)"))
        assert "CHECK constraint failed" in str(exc_0.value) or "ck_workout_sessions_rpe_range" in str(exc_0.value)

        # rpe = 11: rechazado por CHECK a nivel de motor relacional
        with pytest.raises(Exception) as exc_11, engine.begin() as conn_sub:
            conn_sub.execute(text("INSERT INTO workout_sessions VALUES ('s_bad11', 'st1', 'rel1', 'rou1', 'D1', 'GYM', '2026-01-01', '2026-01-01', 11)"))
        assert "CHECK constraint failed" in str(exc_11.value) or "ck_workout_sessions_rpe_range" in str(exc_11.value)

    # Escenario D: Idempotencia
    results2 = apply_migrations(engine)
    assert not any("sqlite_table_rebuild" in r for r in results2)
    insp_idem = inspect(engine)
    db_cks_idem = [c.get("name") for c in insp_idem.get_check_constraints("workout_sessions")]
    assert db_cks_idem.count("ck_workout_sessions_rpe_range") == 1
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM workout_sessions")).scalar()
        assert count == 5  # s1, s2, s_null, s_min, s_max


def test_sqlite_legacy_table_migration_fails_safely_when_invalid_rpe_data_exists():
    """Escenario E (BAJ-01 SQLite Legacy):
    Si una base SQLite antigua contiene valores de RPE fuera de rango (1 a 10),
    la migración falla de forma segura con ValueError, sin modificar ni destruir la tabla original.
    """
    engine = make_legacy_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE student_profiles (id VARCHAR(36) PRIMARY KEY)
        """))
        conn.execute(text("""
            CREATE TABLE training_relationships (id VARCHAR(36) PRIMARY KEY)
        """))
        conn.execute(text("""
            CREATE TABLE workout_sessions (
                id VARCHAR(36) PRIMARY KEY,
                student_id VARCHAR(36) NOT NULL,
                relationship_id VARCHAR(36) NOT NULL,
                routine_id VARCHAR(36) NOT NULL,
                day_name VARCHAR(100) NOT NULL,
                modality VARCHAR(16) NOT NULL,
                started_at DATETIME NOT NULL,
                finished_at DATETIME,
                rpe INTEGER
            )
        """))
        conn.execute(text("INSERT INTO student_profiles VALUES ('st1')"))
        conn.execute(text("INSERT INTO training_relationships VALUES ('rel1')"))
        conn.execute(text("INSERT INTO workout_sessions VALUES ('s_invalid', 'st1', 'rel1', 'rou1', 'D1', 'GYM', '2026-01-01', '2026-01-01', 99)"))

    # La migración debe fallar de forma segura explicando el motivo
    with pytest.raises(ValueError) as exc_info:
        apply_migrations(engine)

    assert "fuera de rango" in str(exc_info.value)
    assert "ck_workout_sessions_rpe_range" in str(exc_info.value)

    # Verificar que la tabla original y sus registros permanecen íntegros y sin alteración
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM workout_sessions WHERE id = 's_invalid'")).fetchone()
        assert row is not None
        assert row[8] == 99


def test_standalone_migrations_registers_body_map_pain_report_models():
    """Escenario US-61: Comprueba que las tablas de reporte de mapa corporal estén registradas en Base.metadata."""
    from backend.src.core.database import Base

    assert "body_map_pain_reports" in Base.metadata.tables
    assert "body_map_pain_report_zones" in Base.metadata.tables
    report_table = Base.metadata.tables["body_map_pain_reports"]
    assert "student_id" in report_table.c
    assert "session_id" in report_table.c
    assert "exercise_id" in report_table.c
    assert "context" in report_table.c
    assert "action_taken" in report_table.c
    assert "idempotency_key" in report_table.c
    constraint_names = {c.name for c in report_table.constraints}
    assert "uq_body_map_student_idempotency" in constraint_names

    zone_table = Base.metadata.tables["body_map_pain_report_zones"]
    assert "report_id" in zone_table.c
    assert "zone" in zone_table.c
    assert "intensity" in zone_table.c


def test_apply_migrations_creates_body_map_pain_report_tables_if_missing():
    """Escenario US-61: Comprueba que apply_migrations cree las tablas de mapas de dolor en una base existente."""
    engine = make_legacy_engine()
    create_legacy_database(engine)
    inspector_before = inspect(engine)
    assert "body_map_pain_reports" not in inspector_before.get_table_names()
    assert "body_map_pain_report_zones" not in inspector_before.get_table_names()

    apply_migrations(engine)

    inspector_after = inspect(engine)
    assert "body_map_pain_reports" in inspector_after.get_table_names()
    assert "body_map_pain_report_zones" in inspector_after.get_table_names()

    report_cols = {c["name"] for c in inspector_after.get_columns("body_map_pain_reports")}
    for col in (
        "id",
        "student_id",
        "relationship_id",
        "session_id",
        "exercise_id",
        "context",
        "action_taken",
        "idempotency_key",
        "created_at",
    ):
        assert col in report_cols

    zone_cols = {c["name"] for c in inspector_after.get_columns("body_map_pain_report_zones")}
    for col in ("id", "report_id", "zone", "intensity", "created_at"):
        assert col in zone_cols


def test_sqlite_legacy_body_map_pain_reports_migrates_to_composite_unique_and_preserves_data():
    """H03 / Migración US-61:
    Verifica que en una base SQLite preexistente con la restricción antigua (unicidad global de idempotency_key):
    1. Se elimine la unicidad global anterior.
    2. Se aplique la unicidad compuesta (student_id, idempotency_key).
    3. Dos alumnos distintos puedan utilizar la misma clave de idempotencia.
    4. Un mismo alumno no pueda duplicar la misma clave para reportes distintos.
    5. Los registros y zonas históricas se preserven intactos.
    6. Múltiples registros con idempotency_key = NULL sigan permitidos.
    7. La migración sea idempotente ante ejecuciones repetidas.
    """
    engine = make_legacy_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE student_profiles (id VARCHAR(36) PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE training_relationships (id VARCHAR(36) PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE workout_sessions (id VARCHAR(36) PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE exercises (id VARCHAR(36) PRIMARY KEY)"))

        # Tabla body_map_pain_reports con el esquema heredado (idempotency_key con unicidad global)
        conn.execute(text("""
            CREATE TABLE body_map_pain_reports (
                id VARCHAR(36) PRIMARY KEY,
                student_id VARCHAR(36) NOT NULL,
                relationship_id VARCHAR(36),
                session_id VARCHAR(36),
                exercise_id VARCHAR(36),
                context VARCHAR(32) NOT NULL,
                action_taken VARCHAR(32),
                idempotency_key VARCHAR(64) UNIQUE,
                created_at DATETIME NOT NULL,
                FOREIGN KEY(student_id) REFERENCES student_profiles (id) ON DELETE CASCADE,
                FOREIGN KEY(relationship_id) REFERENCES training_relationships (id) ON DELETE SET NULL,
                FOREIGN KEY(session_id) REFERENCES workout_sessions (id) ON DELETE SET NULL,
                FOREIGN KEY(exercise_id) REFERENCES exercises (id) ON DELETE SET NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE body_map_pain_report_zones (
                id VARCHAR(36) PRIMARY KEY,
                report_id VARCHAR(36) NOT NULL,
                zone VARCHAR(50) NOT NULL,
                intensity VARCHAR(20) NOT NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY(report_id) REFERENCES body_map_pain_reports (id) ON DELETE CASCADE
            )
        """))

        # Sembrar datos base y registros históricos
        conn.execute(text("INSERT INTO student_profiles VALUES ('student-A')"))
        conn.execute(text("INSERT INTO student_profiles VALUES ('student-B')"))

        # Reporte 1: Alumno A con clave fija
        conn.execute(text("""
            INSERT INTO body_map_pain_reports VALUES
            ('rep-1', 'student-A', NULL, NULL, NULL, 'POST_SESSION', 'NONE', 'shared-idem-key-1', '2026-01-01 10:00:00')
        """))
        conn.execute(text("""
            INSERT INTO body_map_pain_report_zones VALUES
            ('zone-1', 'rep-1', 'Lower back', 'PAIN', '2026-01-01 10:00:00')
        """))

        # Reporte 2: Alumno A con clave NULL
        conn.execute(text("""
            INSERT INTO body_map_pain_reports VALUES
            ('rep-2', 'student-A', NULL, NULL, NULL, 'IN_EXERCISE', 'NONE', NULL, '2026-01-01 11:00:00')
        """))
        conn.execute(text("""
            INSERT INTO body_map_pain_report_zones VALUES
            ('zone-2', 'rep-2', 'Shoulder', 'DISCOMFORT', '2026-01-01 11:00:00')
        """))

        # Reporte 3: Alumno B con clave NULL
        conn.execute(text("""
            INSERT INTO body_map_pain_reports VALUES
            ('rep-3', 'student-B', NULL, NULL, NULL, 'POST_SESSION', 'NONE', NULL, '2026-01-01 12:00:00')
        """))

    # Validación previa a la migración: el esquema heredado rechaza que Alumno B use 'shared-idem-key-1'
    with pytest.raises(Exception) as exc_legacy, engine.begin() as conn_sub:
        conn_sub.execute(text("""
            INSERT INTO body_map_pain_reports VALUES
            ('rep-fail', 'student-B', NULL, NULL, NULL, 'POST_SESSION', 'NONE', 'shared-idem-key-1', '2026-01-01 13:00:00')
        """))
    assert "UNIQUE constraint failed" in str(exc_legacy.value)

    # Ejecutar la migración
    results = apply_migrations(engine)
    assert any("body_map_pain_reports.uq_body_map_student_idempotency:sqlite_table_rebuild" in r for r in results)

    # 1. Preservación íntegra de registros y zonas preexistentes
    with engine.connect() as conn:
        reports = conn.execute(text("SELECT id, student_id, idempotency_key FROM body_map_pain_reports ORDER BY id")).fetchall()
        assert len(reports) == 3
        assert reports[0] == ("rep-1", "student-A", "shared-idem-key-1")
        assert reports[1] == ("rep-2", "student-A", None)
        assert reports[2] == ("rep-3", "student-B", None)

        zones = conn.execute(text("SELECT id, report_id, zone, intensity FROM body_map_pain_report_zones ORDER BY id")).fetchall()
        assert len(zones) == 2
        assert zones[0] == ("zone-1", "rep-1", "Lower back", "PAIN")
        assert zones[1] == ("zone-2", "rep-2", "Shoulder", "DISCOMFORT")

    # 2. Dos alumnos distintos PUEDEN utilizar la misma clave de idempotencia
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO body_map_pain_reports VALUES
            ('rep-4', 'student-B', NULL, NULL, NULL, 'POST_SESSION', 'NONE', 'shared-idem-key-1', '2026-01-01 14:00:00')
        """))

    with engine.connect() as conn:
        r4 = conn.execute(text("SELECT id, student_id, idempotency_key FROM body_map_pain_reports WHERE id = 'rep-4'")).fetchone()
        assert r4 == ("rep-4", "student-B", "shared-idem-key-1")

    # 3. El mismo alumno NO PUEDE duplicar la misma clave para reportes distintos
    with pytest.raises(Exception) as exc_same_student, engine.begin() as conn_sub:
        conn_sub.execute(text("""
            INSERT INTO body_map_pain_reports VALUES
            ('rep-dup', 'student-A', NULL, NULL, NULL, 'POST_SESSION', 'NONE', 'shared-idem-key-1', '2026-01-01 15:00:00')
        """))
    assert "UNIQUE constraint failed" in str(exc_same_student.value) or "uq_body_map_student_idempotency" in str(exc_same_student.value)

    # 4. Múltiples registros con idempotency_key = NULL siguen siendo válidos
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO body_map_pain_reports VALUES
            ('rep-5', 'student-A', NULL, NULL, NULL, 'POST_SESSION', 'NONE', NULL, '2026-01-01 16:00:00')
        """))
        conn.execute(text("""
            INSERT INTO body_map_pain_reports VALUES
            ('rep-6', 'student-B', NULL, NULL, NULL, 'POST_SESSION', 'NONE', NULL, '2026-01-01 17:00:00')
        """))

    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM body_map_pain_reports")).scalar()
        assert total == 6  # rep-1, rep-2, rep-3, rep-4, rep-5, rep-6

    # 5. Idempotencia: re-ejecutar apply_migrations no altera datos ni produce errores
    results_second_run = apply_migrations(engine)
    assert not any("body_map_pain_reports" in r for r in results_second_run)
    with engine.connect() as conn:
        total_after = conn.execute(text("SELECT COUNT(*) FROM body_map_pain_reports")).scalar()
        assert total_after == 6


def test_sqlite_legacy_body_map_pain_reports_fails_safely_when_duplicate_composite_keys_exist():
    """H03 / Migración US-61:
    Si una base de datos contiene registros que violan la nueva unicidad compuesta (mismo alumno y misma clave no nula),
    la migración debe fallar de forma segura con ValueError, sin destruir ni alterar la tabla original.
    """
    engine = make_legacy_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE student_profiles (id VARCHAR(36) PRIMARY KEY)"))
        conn.execute(text("""
            CREATE TABLE body_map_pain_reports (
                id VARCHAR(36) PRIMARY KEY,
                student_id VARCHAR(36) NOT NULL,
                relationship_id VARCHAR(36),
                session_id VARCHAR(36),
                exercise_id VARCHAR(36),
                context VARCHAR(32) NOT NULL,
                action_taken VARCHAR(32),
                idempotency_key VARCHAR(64),
                created_at DATETIME NOT NULL
            )
        """))
        conn.execute(text("INSERT INTO student_profiles VALUES ('student-dup')"))
        # Insertar dos reportes del mismo alumno con la misma clave (posible si no había índice único antes)
        conn.execute(text("""
            INSERT INTO body_map_pain_reports VALUES
            ('r1', 'student-dup', NULL, NULL, NULL, 'POST_SESSION', 'NONE', 'dup-key', '2026-01-01 10:00:00')
        """))
        conn.execute(text("""
            INSERT INTO body_map_pain_reports VALUES
            ('r2', 'student-dup', NULL, NULL, NULL, 'POST_SESSION', 'NONE', 'dup-key', '2026-01-01 11:00:00')
        """))

    with pytest.raises(ValueError) as exc_info:
        apply_migrations(engine)

    assert "duplicados" in str(exc_info.value)
    assert "uq_body_map_student_idempotency" in str(exc_info.value)

    # Verificar que los datos originales siguen intactos
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id FROM body_map_pain_reports")).fetchall()
        assert len(rows) == 2



def test_sqlite_migration_preserves_foreign_key_integrity_and_passes_fk_check():
    """H03 / US-61: Comprueba que la migración conserve estrictamente la integridad referencial en SQLite:
    1. PRAGMA foreign_key_check devuelve 0 violaciones antes de la migración.
    2. apply_migrations() ejecuta la reconstrucción de tabla desactivando temporalmente FKs fuera de transacción.
    3. PRAGMA foreign_key_check devuelve 0 violaciones después de la migración.
    4. Las restricciones de clave foránea permanecen activas (rechazan inserciones con IDs inexistentes).
    5. Las eliminaciones en cascada de la tabla padre (body_map_pain_reports) eliminan sus zonas hijas.
    6. Ante cualquier excepción en la transacción, PRAGMA foreign_keys=ON se restaura en el bloque finally.
    """
    engine = make_legacy_engine()

    # Habilitar claves foráneas en la conexión DBAPI
    with engine.connect() as conn:
        dbapi = conn.connection.dbapi_connection
        if hasattr(dbapi, "execute"):
            dbapi.execute("PRAGMA foreign_keys=ON;")

    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE student_profiles (id VARCHAR(36) PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE training_relationships (id VARCHAR(36) PRIMARY KEY)"))
        conn.execute(text("""
            CREATE TABLE workout_sessions (
                id VARCHAR(36) PRIMARY KEY,
                student_id VARCHAR(36) NOT NULL,
                relationship_id VARCHAR(36) NOT NULL,
                routine_id VARCHAR(36) NOT NULL,
                day_name VARCHAR(100) NOT NULL,
                modality VARCHAR(16) NOT NULL,
                started_at DATETIME NOT NULL,
                finished_at DATETIME,
                rpe INTEGER
            )
        """))
        conn.execute(text("CREATE TABLE exercises (id VARCHAR(36) PRIMARY KEY)"))

        # Tabla body_map_pain_reports en versión legacy
        conn.execute(text("""
            CREATE TABLE body_map_pain_reports (
                id VARCHAR(36) PRIMARY KEY,
                student_id VARCHAR(36) NOT NULL,
                relationship_id VARCHAR(36),
                session_id VARCHAR(36),
                exercise_id VARCHAR(36),
                context VARCHAR(32) NOT NULL,
                action_taken VARCHAR(32),
                idempotency_key VARCHAR(64) UNIQUE,
                created_at DATETIME NOT NULL,
                FOREIGN KEY(student_id) REFERENCES student_profiles (id) ON DELETE CASCADE,
                FOREIGN KEY(relationship_id) REFERENCES training_relationships (id) ON DELETE SET NULL,
                FOREIGN KEY(session_id) REFERENCES workout_sessions (id) ON DELETE SET NULL,
                FOREIGN KEY(exercise_id) REFERENCES exercises (id) ON DELETE SET NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE body_map_pain_report_zones (
                id VARCHAR(36) PRIMARY KEY,
                report_id VARCHAR(36) NOT NULL,
                zone VARCHAR(50) NOT NULL,
                intensity VARCHAR(20) NOT NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY(report_id) REFERENCES body_map_pain_reports (id) ON DELETE CASCADE
            )
        """))

        # Poblar datos referenciales
        conn.execute(text("INSERT INTO student_profiles VALUES ('student-fk-1')"))
        conn.execute(text("INSERT INTO training_relationships VALUES ('rel-fk-1')"))
        conn.execute(text("INSERT INTO exercises VALUES ('ex-fk-1')"))
        conn.execute(text("""
            INSERT INTO workout_sessions VALUES
            ('sess-fk-1', 'student-fk-1', 'rel-fk-1', 'rou-1', 'D1', 'GYM', '2026-01-01', NULL, 8)
        """))

        # Insertar reporte con relaciones válidas y 2 zonas
        conn.execute(text("""
            INSERT INTO body_map_pain_reports VALUES
            ('rep-fk-1', 'student-fk-1', 'rel-fk-1', 'sess-fk-1', 'ex-fk-1', 'IN_EXERCISE', 'NONE', 'key-fk-1', '2026-01-01 10:00:00')
        """))
        conn.execute(text("""
            INSERT INTO body_map_pain_report_zones VALUES
            ('zone-fk-1', 'rep-fk-1', 'Shoulder', 'PAIN', '2026-01-01 10:00:00')
        """))
        conn.execute(text("""
            INSERT INTO body_map_pain_report_zones VALUES
            ('zone-fk-2', 'rep-fk-1', 'Knee', 'DISCOMFORT', '2026-01-01 10:00:00')
        """))

    # 1. foreign_key_check antes de la migración devuelve cero violaciones
    with engine.connect() as conn:
        violations_before = conn.execute(text("PRAGMA foreign_key_check;")).fetchall()
        assert len(violations_before) == 0

    # 2. Ejecutar la migración
    results = apply_migrations(engine)
    assert any("body_map_pain_reports.uq_body_map_student_idempotency:sqlite_table_rebuild" in r for r in results)

    # 3. foreign_key_check después de la migración devuelve exactamente cero violaciones
    with engine.connect() as conn:
        violations_after = conn.execute(text("PRAGMA foreign_key_check;")).fetchall()
        assert len(violations_after) == 0

        # Verificación explícita sobre las dos tablas del módulo
        table_fk_reports = conn.execute(text("PRAGMA foreign_key_check('body_map_pain_reports');")).fetchall()
        assert len(table_fk_reports) == 0
        table_fk_zones = conn.execute(text("PRAGMA foreign_key_check('body_map_pain_report_zones');")).fetchall()
        assert len(table_fk_zones) == 0

        # 4. Comprobar que los registros y sus relaciones foráneas persisten íntegros
        row = conn.execute(text("""
            SELECT r.id, r.student_id, r.relationship_id, r.session_id, r.exercise_id, COUNT(z.id)
            FROM body_map_pain_reports r
            JOIN body_map_pain_report_zones z ON z.report_id = r.id
            WHERE r.id = 'rep-fk-1'
            GROUP BY r.id
        """)).fetchone()
        assert row == ("rep-fk-1", "student-fk-1", "rel-fk-1", "sess-fk-1", "ex-fk-1", 2)

    # 5. Comprobar que las claves foráneas continúan activas y bloquean datos inválidos
    with engine.connect() as conn:
        dbapi = conn.connection.dbapi_connection
        if hasattr(dbapi, "execute"):
            dbapi.execute("PRAGMA foreign_keys=ON;")

        with pytest.raises(Exception) as exc_invalid_student, engine.begin() as conn_sub:
            conn_sub.execute(text("""
                INSERT INTO body_map_pain_reports VALUES
                ('rep-bad', 'non-existent-student', NULL, NULL, NULL, 'POST_SESSION', 'NONE', 'k-bad', '2026-01-01')
            """))
        assert "FOREIGN KEY constraint failed" in str(exc_invalid_student.value)

        with pytest.raises(Exception) as exc_invalid_report, engine.begin() as conn_sub:
            conn_sub.execute(text("""
                INSERT INTO body_map_pain_report_zones VALUES
                ('zone-bad', 'non-existent-report', 'Hip', 'PAIN', '2026-01-01')
            """))
        assert "FOREIGN KEY constraint failed" in str(exc_invalid_report.value)

    # 6. Comprobar ON DELETE CASCADE en la tabla hija tras la migración
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM body_map_pain_reports WHERE id = 'rep-fk-1'"))

    with engine.connect() as conn:
        remaining_zones = conn.execute(text("SELECT COUNT(*) FROM body_map_pain_report_zones WHERE report_id = 'rep-fk-1'")).scalar()
        assert remaining_zones == 0


def test_migration_adds_and_backfills_routine_assigned_at_without_losing_history():
    from backend.src.core.migrations import TARGET_COLUMNS

    col_def = next(c for c in TARGET_COLUMNS if c.table == "training_relationships" and c.column == "routine_assigned_at")
    assert col_def.sqlite_type == "DATETIME"
    assert col_def.postgres_type == "TIMESTAMP WITH TIME ZONE"
    assert col_def.nullable is True

    engine = make_legacy_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE training_relationships (
                id VARCHAR(36) PRIMARY KEY,
                trainer_id VARCHAR(36) NOT NULL,
                student_id VARCHAR(36) NOT NULL,
                plan_id VARCHAR(36) NOT NULL,
                agreed_monthly_price NUMERIC(10, 2) NOT NULL,
                agreed_currency VARCHAR(8) NOT NULL,
                status VARCHAR(16) NOT NULL,
                start_date DATE NOT NULL,
                initial_routine_id VARCHAR(36)
            )
        """))
        conn.execute(text("""
            CREATE TABLE student_routines (
                id VARCHAR(36) PRIMARY KEY,
                relationship_id VARCHAR(36) UNIQUE NOT NULL,
                source_template_id VARCHAR(36),
                source_kind VARCHAR(16) NOT NULL,
                name VARCHAR(150) NOT NULL,
                duration_weeks INTEGER NOT NULL,
                intensity VARCHAR(16) NOT NULL,
                has_no_materials_alternative BOOLEAN NOT NULL DEFAULT 0,
                desired_weekly_volume INTEGER,
                days JSON NOT NULL,
                draft JSON,
                draft_version INTEGER NOT NULL DEFAULT 0,
                status VARCHAR(16) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE assigned_routines (
                id VARCHAR(36) PRIMARY KEY,
                trainer_id VARCHAR(36) NOT NULL,
                student_id VARCHAR(36) NOT NULL,
                template_id VARCHAR(36),
                name VARCHAR(150) NOT NULL,
                duration_weeks INTEGER NOT NULL,
                intensity VARCHAR(16) NOT NULL,
                has_no_materials_alternative BOOLEAN NOT NULL DEFAULT 0,
                status VARCHAR(16) NOT NULL,
                adaptation_summary TEXT,
                approved_at DATETIME,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE workout_sessions (
                id VARCHAR(36) PRIMARY KEY,
                student_id VARCHAR(36) NOT NULL,
                relationship_id VARCHAR(36) NOT NULL,
                routine_id VARCHAR(36) NOT NULL,
                day_name VARCHAR(100) NOT NULL,
                modality VARCHAR(16) NOT NULL,
                started_at DATETIME NOT NULL,
                finished_at DATETIME,
                rpe INTEGER
            )
        """))

        # Vínculos históricos en distintos estados
        conn.execute(text("""
            INSERT INTO training_relationships
            (id, trainer_id, student_id, plan_id, agreed_monthly_price, agreed_currency, status, start_date, initial_routine_id)
            VALUES
            ('rel-sr', 'tr-1', 'st-1', 'pl-1', 10000, 'ARS', 'ACTIVE', '2026-01-01', 'tpl-1'),
            ('rel-ar', 'tr-1', 'st-2', 'pl-1', 10000, 'ARS', 'ACTIVE', '2026-01-01', 'ar-1'),
            ('rel-ws', 'tr-1', 'st-3', 'pl-1', 10000, 'ARS', 'ACTIVE', '2026-01-01', 'tpl-2'),
            ('rel-tpl-only', 'tr-1', 'st-4', 'pl-1', 10000, 'ARS', 'ACTIVE', '2026-01-01', 'tpl-3'),
            ('rel-none', 'tr-1', 'st-5', 'pl-1', 10000, 'ARS', 'ACTIVE', '2026-01-01', NULL)
        """))
        conn.execute(text("""
            INSERT INTO student_routines
            (id, relationship_id, source_template_id, source_kind, name, duration_weeks, intensity, has_no_materials_alternative, days, draft_version, status, created_at, updated_at)
            VALUES
            ('sr-1', 'rel-sr', 'tpl-1', 'GENERIC', 'Rutina SR', 4, 'MEDIA', 0, '[]', 0, 'ACTIVE', '2026-02-10 10:00:00', '2026-02-10 10:00:00')
        """))
        conn.execute(text("""
            INSERT INTO assigned_routines
            (id, trainer_id, student_id, template_id, name, duration_weeks, intensity, has_no_materials_alternative, status, approved_at, created_at, updated_at)
            VALUES
            ('ar-1', 'tr-1', 'st-2', NULL, 'Rutina IA', 4, 'MEDIA', 0, 'APPROVED', '2026-02-15 12:00:00', '2026-02-14 09:00:00', '2026-02-15 12:00:00')
        """))
        conn.execute(text("""
            INSERT INTO workout_sessions
            (id, student_id, relationship_id, routine_id, day_name, modality, started_at, finished_at, rpe)
            VALUES
            ('ws-1', 'st-3', 'rel-ws', 'tpl-2', 'Día 1', 'GYM', '2026-02-20 09:00:00', '2026-02-20 10:00:00', 7),
            ('ws-old-other', 'st-4', 'rel-tpl-only', 'tpl-old', 'Día 1', 'GYM', '2026-01-10 09:00:00', '2026-01-10 10:00:00', 8)
        """))

    applied = apply_migrations(engine)
    assert "training_relationships.routine_assigned_at" in applied
    assert "training_relationships.routine_assigned_at:backfill" in applied

    cols = {c["name"]: c for c in inspect(engine).get_columns("training_relationships")}
    assert "routine_assigned_at" in cols
    assert cols["routine_assigned_at"]["nullable"] is True

    with engine.connect() as conn:
        rows = dict(conn.execute(text("SELECT id, routine_assigned_at FROM training_relationships")).fetchall())
        assert str(rows["rel-sr"]).startswith("2026-02-10 10:00:00")
        assert str(rows["rel-ar"]).startswith("2026-02-15 12:00:00")
        assert str(rows["rel-ws"]).startswith("2026-02-20 09:00:00")
        assert rows["rel-tpl-only"] is not None
        assert rows["rel-none"] is None
        # No destruye sesiones ni StudentRoutine existentes
        assert conn.execute(text("SELECT COUNT(*) FROM workout_sessions")).scalar() == 2
        assert str(conn.execute(text("SELECT created_at FROM student_routines WHERE id = 'sr-1'")).scalar()).startswith("2026-02-10 10:00:00")

    # Idempotencia: una segunda ejecución no reaplica ni altera fechas ya migradas
    second = apply_migrations(engine)
    assert "training_relationships.routine_assigned_at" not in second
    assert "training_relationships.routine_assigned_at:backfill" not in second
    with engine.connect() as conn:
        rows_after = dict(conn.execute(text("SELECT id, routine_assigned_at FROM training_relationships")).fetchall())
        assert rows_after == rows
