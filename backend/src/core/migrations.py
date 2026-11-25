"""Migraciones explícitas, aditivas e idempotentes para bases de datos persistentes.

Asegura la correspondencia entre los modelos SQLAlchemy y las tablas físicas
sin destruir tablas preexistentes ni sobrescribir datos.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, Engine, bindparam, inspect, text

import backend.src.models  # noqa: F401 - Asegura el registro de todas las entidades en Base.metadata
from backend.src.core.database import Base, engine

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ColumnMigration:
    table: str
    column: str
    sqlite_type: str
    postgres_type: str
    nullable: bool = True
    sqlite_default: str | None = None
    postgres_default: str | None = None


@dataclass(frozen=True)
class ColumnTypeAlteration:
    table: str
    column: str
    postgres_type: str
    target_length: int


@dataclass(frozen=True)
class CheckConstraintMigration:
    table: str
    name: str
    expression: str


# Definición explícita y versionada de columnas incorporadas en evoluciones de sprint.
TARGET_COLUMNS: tuple[ColumnMigration, ...] = (
    ColumnMigration(
        table="exercises",
        column="video_url",
        sqlite_type="VARCHAR(500)",
        postgres_type="VARCHAR(500)",
        nullable=True,
    ),
    ColumnMigration(
        table="exercises",
        column="video_platform",
        sqlite_type="VARCHAR(12)",
        postgres_type="video_platform",
        nullable=False,
        sqlite_default="'NONE'",
        postgres_default="'NONE'::video_platform",
    ),
    ColumnMigration(
        table="exercises",
        column="technical_cues",
        sqlite_type="TEXT",
        postgres_type="TEXT",
        nullable=True,
    ),
    ColumnMigration(
        table="exercises",
        column="breathing_cues",
        sqlite_type="TEXT",
        postgres_type="TEXT",
        nullable=True,
    ),
    ColumnMigration(
        table="exercises",
        column="contraindicated_zones",
        sqlite_type="JSON",
        postgres_type="JSONB",
        nullable=False,
        sqlite_default="'[]'",
        postgres_default="'[]'::jsonb",
    ),
    ColumnMigration(
        table="assigned_routines",
        column="has_no_materials_alternative",
        sqlite_type="BOOLEAN",
        postgres_type="BOOLEAN",
        nullable=False,
        sqlite_default="0",
        postgres_default="FALSE",
    ),
    ColumnMigration(
        table="assigned_routine_days",
        column="estimated_duration_minutes",
        sqlite_type="INTEGER",
        postgres_type="INTEGER",
        nullable=True,
    ),
    ColumnMigration(
        table="assigned_routine_blocks",
        column="estimated_duration_minutes",
        sqlite_type="INTEGER",
        postgres_type="INTEGER",
        nullable=True,
    ),
    ColumnMigration(
        table="assigned_routine_exercises",
        column="target_weight_kg",
        sqlite_type="NUMERIC(7, 2)",
        postgres_type="NUMERIC(7, 2)",
        nullable=True,
    ),
    ColumnMigration(
        table="training_relationships",
        column="routine_modality",
        sqlite_type="VARCHAR(16)",
        postgres_type="VARCHAR(16)",
        nullable=False,
        sqlite_default="'GYM'",
        postgres_default="'GYM'",
    ),
    ColumnMigration(
        table="training_relationships",
        column="routine_assigned_at",
        sqlite_type="DATETIME",
        postgres_type="TIMESTAMP WITH TIME ZONE",
        nullable=True,
    ),
    ColumnMigration(
        table="workout_set_logs",
        column="duration_seconds",
        sqlite_type="INTEGER",
        postgres_type="INTEGER",
        nullable=True,
    ),
    ColumnMigration(
        table="workout_set_logs",
        column="session_id",
        sqlite_type="VARCHAR(36)",
        postgres_type="VARCHAR(36)",
        nullable=True,
    ),
    ColumnMigration(
        table="workout_sessions",
        column="rpe",
        sqlite_type="INTEGER",
        postgres_type="INTEGER",
        nullable=True,
    ),
    ColumnMigration(
        table="notifications",
        column="related_student_id",
        sqlite_type="VARCHAR(36)",
        postgres_type="VARCHAR(36)",
        nullable=True,
    ),
    ColumnMigration(
        table="notifications",
        column="related_session_id",
        sqlite_type="VARCHAR(36)",
        postgres_type="VARCHAR(36)",
        nullable=True,
    ),
    ColumnMigration(
        table="training_relationships",
        column="routine_assignment_id",
        sqlite_type="VARCHAR(36)",
        postgres_type="VARCHAR(36)",
        nullable=True,
    ),
    # US-71: confirmación de pagos informados y comprobante (informal_payments, creada en US-34).
    ColumnMigration(
        table="informal_payments",
        column="source",
        sqlite_type="VARCHAR(16)",
        postgres_type="VARCHAR(16)",
        nullable=False,
        sqlite_default="'TRAINER'",
        postgres_default="'TRAINER'",
    ),
    ColumnMigration(
        table="informal_payments",
        column="confirmed_by_user_id",
        sqlite_type="VARCHAR(36) REFERENCES users(id)",
        postgres_type="VARCHAR(36) REFERENCES users(id)",
        nullable=True,
    ),
    ColumnMigration(
        table="informal_payments",
        column="confirmed_at",
        sqlite_type="DATETIME",
        postgres_type="TIMESTAMP WITH TIME ZONE",
        nullable=True,
    ),
    ColumnMigration(
        table="informal_payments",
        column="rejected_by_user_id",
        sqlite_type="VARCHAR(36) REFERENCES users(id)",
        postgres_type="VARCHAR(36) REFERENCES users(id)",
        nullable=True,
    ),
    ColumnMigration(
        table="informal_payments",
        column="rejected_at",
        sqlite_type="DATETIME",
        postgres_type="TIMESTAMP WITH TIME ZONE",
        nullable=True,
    ),
    ColumnMigration(
        table="informal_payments",
        column="rejection_reason",
        sqlite_type="TEXT",
        postgres_type="TEXT",
        nullable=True,
    ),
    ColumnMigration(
        table="informal_payments",
        column="receipt_path",
        sqlite_type="VARCHAR(500)",
        postgres_type="VARCHAR(500)",
        nullable=True,
    ),
    ColumnMigration(
        table="informal_payments",
        column="receipt_filename",
        sqlite_type="VARCHAR(255)",
        postgres_type="VARCHAR(255)",
        nullable=True,
    ),
    ColumnMigration(
        table="informal_payments",
        column="receipt_mime_type",
        sqlite_type="VARCHAR(100)",
        postgres_type="VARCHAR(100)",
        nullable=True,
    ),
    ColumnMigration(
        table="informal_payments",
        column="receipt_size",
        sqlite_type="INTEGER",
        postgres_type="INTEGER",
        nullable=True,
    ),
    ColumnMigration(
        table="training_relationships",
        column="termination_category",
        sqlite_type="VARCHAR(24)",
        postgres_type="VARCHAR(24)",
        nullable=True,
    ),
    ColumnMigration(
        table="student_routines",
        column="routine_assignment_id",
        sqlite_type="VARCHAR(36)",
        postgres_type="VARCHAR(36)",
        nullable=True,
    ),
    ColumnMigration(
        table="exercise_replacement_logs",
        column="session_id",
        sqlite_type="VARCHAR(36)",
        postgres_type="VARCHAR(36)",
        nullable=True,
    ),
    ColumnMigration(
        table="session_adjustments",
        column="baseline_blocks",
        sqlite_type="JSON",
        postgres_type="JSON",
        nullable=True,
    ),
    ColumnMigration(
        table="workout_sessions",
        column="weekly_target",
        sqlite_type="INTEGER",
        postgres_type="INTEGER",
        nullable=True,
    ),
)

# Definición explícita de ampliaciones de longitud de columnas en bases de datos que imponen límites de caracteres (ej. PostgreSQL)
TARGET_TYPE_ALTERATIONS: tuple[ColumnTypeAlteration, ...] = (
    ColumnTypeAlteration(
        table="assigned_routine_exercises",
        column="adaptation_notes",
        postgres_type="VARCHAR(500)",
        target_length=500,
    ),
)

# Definición explícita de restricciones CHECK para motores relacionales que admiten ALTER TABLE ADD CONSTRAINT (ej. PostgreSQL)
TARGET_CHECK_CONSTRAINTS: tuple[CheckConstraintMigration, ...] = (
    CheckConstraintMigration(
        table="workout_sessions",
        name="ck_workout_sessions_rpe_range",
        expression="rpe IS NULL OR (rpe >= 1 AND rpe <= 10)",
    ),
    CheckConstraintMigration(
        table="safety_alerts",
        name="ck_safety_alerts_type",
        expression="alert_type IN ('PAIN', 'REPEATED_DISCOMFORT', 'EXCESSIVE_EFFORT')",
    ),
    CheckConstraintMigration(
        table="safety_alerts",
        name="ck_safety_alerts_status",
        expression="status IN ('PENDING', 'REVIEWED')",
    ),
    CheckConstraintMigration(
        table="safety_alerts",
        name="ck_safety_alerts_action",
        expression="action_taken IS NULL OR action_taken IN ('ADJUSTED_ROUTINE', 'CONTACTED_STUDENT', 'NO_ACTION')",
    ),
    CheckConstraintMigration(
        table="safety_alerts",
        name="ck_safety_alerts_rpe",
        expression="rpe IS NULL OR rpe IN (9, 10)",
    ),
    CheckConstraintMigration(
        table="informal_payments",
        name="ck_informal_payments_source",
        expression="source IN ('TRAINER', 'STUDENT')",
    ),
    CheckConstraintMigration(
        table="informal_payments",
        name="ck_informal_payments_reject_fields",
        expression=(
            "(status = 'RECHAZADO' AND rejected_at IS NOT NULL AND rejected_by_user_id IS NOT NULL"
            " AND rejection_reason IS NOT NULL)"
            " OR (status <> 'RECHAZADO' AND rejected_at IS NULL AND rejected_by_user_id IS NULL"
            " AND rejection_reason IS NULL)"
        ),
    ),
    CheckConstraintMigration(
        table="training_relationships",
        name="ck_training_relationships_termination_category",
        expression=(
            "termination_category IS NULL OR termination_category IN "
            "('FALTA_DE_PAGO', 'RAZONES_PERSONALES', 'OTRO')"
        ),
    ),
)


def _migrate_sqlite_workout_sessions_check_constraint(eng: Engine, inspector) -> list[str]:
    """Aplica de forma segura y transaccional la restricción CHECK en workout_sessions para SQLite legacy."""
    fresh_inspector = inspect(eng)
    existing_tables = set(fresh_inspector.get_table_names())
    if "workout_sessions" not in existing_tables:
        return []

    existing_cks = {c.get("name") for c in fresh_inspector.get_check_constraints("workout_sessions")}
    if "ck_workout_sessions_rpe_range" in existing_cks:
        return []

    # 1. Validar que no existan valores de RPE fuera de rango antes de aplicar la restricción
    cols = {c["name"] for c in fresh_inspector.get_columns("workout_sessions")}
    if "rpe" in cols:
        with eng.connect() as conn:
            invalid_count = conn.execute(
                text("SELECT COUNT(*) FROM workout_sessions WHERE rpe IS NOT NULL AND (rpe < 1 OR rpe > 10)")
            ).scalar()
            if invalid_count and invalid_count > 0:
                raise ValueError(
                    f"No se puede aplicar la restricción CHECK 'ck_workout_sessions_rpe_range' en 'workout_sessions': "
                    f"se encontraron {invalid_count} registro(s) con valores de RPE fuera de rango (1 a 10)."
                )

    # 2. Reconstrucción segura de la tabla en SQLite preservando datos, índices y claves foráneas
    existing_indexes = fresh_inspector.get_indexes("workout_sessions")
    with eng.connect() as conn:
        dbapi = conn.connection.dbapi_connection
        if hasattr(dbapi, "execute"):
            dbapi.execute("PRAGMA foreign_keys=OFF;")

        try:
            with conn.begin():
                conn.execute(text("""
                    CREATE TABLE _workout_sessions_new (
                        id VARCHAR(36) PRIMARY KEY,
                        student_id VARCHAR(36) NOT NULL,
                        relationship_id VARCHAR(36) NOT NULL,
                        routine_id VARCHAR(36) NOT NULL,
                        day_name VARCHAR(100) NOT NULL,
                        modality VARCHAR(16) NOT NULL,
                        started_at DATETIME NOT NULL,
                        finished_at DATETIME,
                        rpe INTEGER,
                        weekly_target INTEGER,
                        CONSTRAINT ck_workout_sessions_rpe_range CHECK (rpe IS NULL OR (rpe >= 1 AND rpe <= 10)),
                        FOREIGN KEY(student_id) REFERENCES student_profiles (id) ON DELETE CASCADE,
                        FOREIGN KEY(relationship_id) REFERENCES training_relationships (id) ON DELETE CASCADE
                    )
                """))
                cols_target = [
                    "id", "student_id", "relationship_id", "routine_id",
                    "day_name", "modality", "started_at", "finished_at",
                ]
                if "rpe" in cols:
                    cols_target.append("rpe")
                if "weekly_target" in cols:
                    cols_target.append("weekly_target")
                cols_to_copy = [c for c in cols_target if c in cols]
                cols_str = ", ".join(cols_to_copy)
                conn.execute(text(f"INSERT INTO _workout_sessions_new ({cols_str}) SELECT {cols_str} FROM workout_sessions"))
                conn.execute(text("DROP TABLE workout_sessions"))
                conn.execute(text("ALTER TABLE _workout_sessions_new RENAME TO workout_sessions"))

                # Recrear índices preexistentes
                created_idx_names = set()
                for idx in existing_indexes:
                    idx_name = idx.get("name")
                    if idx_name:
                        idx_cols = ", ".join(f'"{c}"' for c in idx["column_names"])
                        unique_kw = "UNIQUE " if idx.get("unique") else ""
                        conn.execute(text(f"CREATE {unique_kw}INDEX IF NOT EXISTS {idx_name} ON workout_sessions ({idx_cols})"))
                        created_idx_names.add(idx_name)

                # Asegurar índices estándar de la entidad
                for std_idx, col_name in [
                    ("ix_workout_sessions_student_id", "student_id"),
                    ("ix_workout_sessions_relationship_id", "relationship_id"),
                    ("ix_workout_sessions_routine_id", "routine_id"),
                ]:
                    if std_idx not in created_idx_names:
                        conn.execute(text(f"CREATE INDEX IF NOT EXISTS {std_idx} ON workout_sessions ({col_name})"))
        finally:
            if hasattr(dbapi, "execute"):
                dbapi.execute("PRAGMA foreign_keys=ON;")

    key = "workout_sessions.ck_workout_sessions_rpe_range:sqlite_table_rebuild"
    logger.info("Restricción CHECK aplicada vía reconstrucción de tabla en SQLite: %s", key)
    return [key]


def _migrate_sqlite_body_map_pain_reports_unique_constraint(eng: Engine, inspector) -> list[str]:
    """Aplica de forma segura y transaccional la restricción de unicidad compuesta (student_id, idempotency_key)
    en body_map_pain_reports para SQLite legacy, sustituyendo la unicidad global anterior."""
    fresh_inspector = inspect(eng)
    existing_tables = set(fresh_inspector.get_table_names())
    if "body_map_pain_reports" not in existing_tables:
        return []

    # 1. Determinar si la tabla física requiere migración inspeccionando índices únicos
    with eng.connect() as conn:
        raw_indexes = conn.execute(text("PRAGMA index_list('body_map_pain_reports')")).fetchall()
        has_legacy_single_unique = False
        has_composite_unique = False
        for idx in raw_indexes:
            idx_name = idx[1]
            is_unique = bool(idx[2])
            if not is_unique:
                continue
            cols = [
                row[2]
                for row in conn.execute(text(f"PRAGMA index_info('{idx_name}')")).fetchall()
            ]
            if cols == ["idempotency_key"]:
                has_legacy_single_unique = True
            elif set(cols) == {"student_id", "idempotency_key"} and len(cols) == 2:
                has_composite_unique = True

    # Si ya posee la unicidad compuesta y no presenta la unicidad simple obsoleta, el esquema es óptimo
    if has_composite_unique and not has_legacy_single_unique:
        return []

    # 2. Validar que no existan registros duplicados para el par (student_id, idempotency_key)
    with eng.connect() as conn:
        dup_count = conn.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT student_id, idempotency_key
                FROM body_map_pain_reports
                WHERE idempotency_key IS NOT NULL
                GROUP BY student_id, idempotency_key
                HAVING COUNT(*) > 1
            )
        """)).scalar()
        if dup_count and dup_count > 0:
            raise ValueError(
                f"No se puede aplicar la restricción UNIQUE 'uq_body_map_student_idempotency' en 'body_map_pain_reports': "
                f"se encontraron {dup_count} par(es) (student_id, idempotency_key) duplicados."
            )

    # 3. Reconstrucción segura de la tabla en SQLite preservando datos, índices y claves foráneas
    existing_cols = {c["name"] for c in fresh_inspector.get_columns("body_map_pain_reports")}
    with eng.connect() as conn:
        dbapi = conn.connection.dbapi_connection
        if hasattr(dbapi, "execute"):
            dbapi.execute("PRAGMA foreign_keys=OFF;")

        try:
            with conn.begin():
                conn.execute(text("""
                    CREATE TABLE _body_map_pain_reports_new (
                        id VARCHAR(36) PRIMARY KEY,
                        student_id VARCHAR(36) NOT NULL,
                        relationship_id VARCHAR(36),
                        session_id VARCHAR(36),
                        exercise_id VARCHAR(36),
                        context VARCHAR(32) NOT NULL,
                        action_taken VARCHAR(32),
                        idempotency_key VARCHAR(64),
                        created_at DATETIME NOT NULL,
                        CONSTRAINT uq_body_map_student_idempotency UNIQUE (student_id, idempotency_key),
                        FOREIGN KEY(student_id) REFERENCES student_profiles (id) ON DELETE CASCADE,
                        FOREIGN KEY(relationship_id) REFERENCES training_relationships (id) ON DELETE SET NULL,
                        FOREIGN KEY(session_id) REFERENCES workout_sessions (id) ON DELETE SET NULL,
                        FOREIGN KEY(exercise_id) REFERENCES exercises (id) ON DELETE SET NULL
                    )
                """))
                cols_target = [
                    "id", "student_id", "relationship_id", "session_id",
                    "exercise_id", "context", "action_taken", "idempotency_key", "created_at"
                ]
                cols_to_copy = [c for c in cols_target if c in existing_cols]
                cols_str = ", ".join(cols_to_copy)
                conn.execute(text(
                    f"INSERT INTO _body_map_pain_reports_new ({cols_str}) "
                    f"SELECT {cols_str} FROM body_map_pain_reports"
                ))
                conn.execute(text("DROP TABLE body_map_pain_reports"))
                conn.execute(text("ALTER TABLE _body_map_pain_reports_new RENAME TO body_map_pain_reports"))

                # Crear índices estándar (con idempotency_key NO único)
                std_indexes = [
                    ("ix_body_map_pain_reports_student_id", "student_id"),
                    ("ix_body_map_pain_reports_relationship_id", "relationship_id"),
                    ("ix_body_map_pain_reports_session_id", "session_id"),
                    ("ix_body_map_pain_reports_exercise_id", "exercise_id"),
                    ("ix_body_map_pain_reports_idempotency_key", "idempotency_key"),
                    ("ix_body_map_pain_reports_created_at", "created_at"),
                ]
                for idx_name, col_name in std_indexes:
                    conn.execute(text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON body_map_pain_reports ({col_name})"))
        finally:
            if hasattr(dbapi, "execute"):
                dbapi.execute("PRAGMA foreign_keys=ON;")

    # 4. Validar integridad referencial post-reconstrucción
    with eng.connect() as conn:
        fk_violations = conn.execute(text("PRAGMA foreign_key_check('body_map_pain_reports');")).fetchall()
        if "body_map_pain_report_zones" in existing_tables:
            fk_violations.extend(conn.execute(text("PRAGMA foreign_key_check('body_map_pain_report_zones');")).fetchall())
        if fk_violations:
            raise ValueError(
                f"Violación de clave foránea detectada tras reconstrucción de 'body_map_pain_reports': {fk_violations}"
            )

    key = "body_map_pain_reports.uq_body_map_student_idempotency:sqlite_table_rebuild"
    logger.info("Restricción UNIQUE compuesta aplicada vía reconstrucción de tabla en SQLite: %s", key)
    return [key]


def _backfill_routine_assigned_at(
    conn,
    existing_tables: set[str],
) -> list[str]:
    """Completa routine_assigned_at en vínculos heredados con rutina asignada sin perder historial."""
    if "training_relationships" not in existing_tables:
        return []
    conn_inspector = inspect(conn)
    rel_cols = {c["name"] for c in conn_inspector.get_columns("training_relationships")}
    if not {"initial_routine_id", "routine_assigned_at"}.issubset(rel_cols):
        return []

    pending = conn.execute(
        text(
            "SELECT COUNT(*) FROM training_relationships "
            "WHERE initial_routine_id IS NOT NULL AND routine_assigned_at IS NULL"
        )
    ).scalar()
    if not pending:
        return []

    sr_cols = {c["name"] for c in conn_inspector.get_columns("student_routines")} if "student_routines" in existing_tables else set()
    ar_cols = {c["name"] for c in conn_inspector.get_columns("assigned_routines")} if "assigned_routines" in existing_tables else set()
    ws_cols = {c["name"] for c in conn_inspector.get_columns("workout_sessions")} if "workout_sessions" in existing_tables else set()

    applied: list[str] = []
    if {"relationship_id", "status", "created_at"}.issubset(sr_cols):
        conn.execute(
            text(
                "UPDATE training_relationships "
                "SET routine_assigned_at = ("
                "  SELECT sr.created_at FROM student_routines sr "
                "  WHERE sr.relationship_id = training_relationships.id "
                "    AND sr.status != 'UNASSIGNED' "
                "  LIMIT 1"
                ") "
                "WHERE initial_routine_id IS NOT NULL "
                "  AND routine_assigned_at IS NULL "
                "  AND EXISTS ("
                "    SELECT 1 FROM student_routines sr "
                "    WHERE sr.relationship_id = training_relationships.id "
                "      AND sr.status != 'UNASSIGNED'"
                "  )"
            )
        )

    if {"id", "status", "approved_at", "updated_at", "created_at"}.issubset(ar_cols):
        conn.execute(
            text(
                "UPDATE training_relationships "
                "SET routine_assigned_at = ("
                "  SELECT COALESCE(ar.approved_at, ar.updated_at, ar.created_at) "
                "  FROM assigned_routines ar "
                "  WHERE ar.id = training_relationships.initial_routine_id "
                "    AND ar.status = 'APPROVED' "
                "  LIMIT 1"
                ") "
                "WHERE initial_routine_id IS NOT NULL "
                "  AND routine_assigned_at IS NULL "
                "  AND EXISTS ("
                "    SELECT 1 FROM assigned_routines ar "
                "    WHERE ar.id = training_relationships.initial_routine_id "
                "      AND ar.status = 'APPROVED'"
                "  )"
            )
        )

    if {"relationship_id", "routine_id", "started_at"}.issubset(ws_cols):
        conn.execute(
            text(
                "UPDATE training_relationships "
                "SET routine_assigned_at = ("
                "  SELECT MIN(ws.started_at) FROM workout_sessions ws "
                "  WHERE ws.relationship_id = training_relationships.id "
                "    AND ws.routine_id = training_relationships.initial_routine_id"
                ") "
                "WHERE initial_routine_id IS NOT NULL "
                "  AND routine_assigned_at IS NULL "
                "  AND EXISTS ("
                "    SELECT 1 FROM workout_sessions ws "
                "    WHERE ws.relationship_id = training_relationships.id "
                "      AND ws.routine_id = training_relationships.initial_routine_id"
                "  )"
            )
        )

    remaining = conn.execute(
        text(
            "SELECT COUNT(*) FROM training_relationships "
            "WHERE initial_routine_id IS NOT NULL AND routine_assigned_at IS NULL"
        )
    ).scalar()
    if remaining:
        fallback_now = datetime.now(UTC).replace(tzinfo=None)
        stmt = text(
            "UPDATE training_relationships "
            "SET routine_assigned_at = :fallback_now "
            "WHERE initial_routine_id IS NOT NULL AND routine_assigned_at IS NULL"
        ).bindparams(bindparam("fallback_now", value=fallback_now, type_=DateTime(timezone=True)))
        conn.execute(stmt)

    key = "training_relationships.routine_assigned_at:backfill"
    applied.append(key)
    logger.info("Backfill aplicado: %s", key)
    return applied


def _backfill_routine_assignment_lineage(conn, existing_tables: set[str]) -> list[str]:
    """Completa routine_assignment_id en relaciones/rutinas existentes para preservar la continuidad histórica."""
    if "training_relationships" not in existing_tables:
        return []
    insp = inspect(conn)
    tr_cols = {c["name"] for c in insp.get_columns("training_relationships")}
    if not {"id", "initial_routine_id", "routine_assignment_id"}.issubset(tr_cols):
        return []

    applied: list[str] = []
    rows = conn.execute(
        text(
            "SELECT id FROM training_relationships "
            "WHERE initial_routine_id IS NOT NULL AND routine_assignment_id IS NULL"
        )
    ).fetchall()
    for (rel_id,) in rows:
        assignment_id = str(uuid4())
        conn.execute(
            text(
                "UPDATE training_relationships SET routine_assignment_id = :aid "
                "WHERE id = :rel_id AND routine_assignment_id IS NULL"
            ),
            {"aid": assignment_id, "rel_id": rel_id},
        )
    if rows:
        applied.append("training_relationships.routine_assignment_id:backfill")

    if "student_routines" in existing_tables:
        sr_cols = {c["name"] for c in insp.get_columns("student_routines")}
        if {"relationship_id", "routine_assignment_id"}.issubset(sr_cols):
            pending_sr = conn.execute(
                text(
                    "SELECT COUNT(*) FROM student_routines sr "
                    "JOIN training_relationships tr ON tr.id = sr.relationship_id "
                    "WHERE sr.routine_assignment_id IS NULL AND tr.routine_assignment_id IS NOT NULL"
                )
            ).scalar()
            if pending_sr:
                conn.execute(
                    text(
                        "UPDATE student_routines "
                        "SET routine_assignment_id = ("
                        "  SELECT tr.routine_assignment_id FROM training_relationships tr "
                        "  WHERE tr.id = student_routines.relationship_id"
                        ") "
                        "WHERE routine_assignment_id IS NULL "
                        "  AND EXISTS ("
                        "    SELECT 1 FROM training_relationships tr "
                        "    WHERE tr.id = student_routines.relationship_id "
                        "      AND tr.routine_assignment_id IS NOT NULL"
                        "  )"
                    )
                )
                applied.append("student_routines.routine_assignment_id:backfill")
    return applied


def _migrate_sqlite_exercise_replacement_logs(eng: Engine) -> list[str]:
    """Migra exercise_replacement_logs en SQLite para indexar por session_id sin colisión en la misma fecha UTC."""
    fresh_inspector = inspect(eng)
    existing_tables = set(fresh_inspector.get_table_names())
    if "exercise_replacement_logs" not in existing_tables:
        return []

    legacy_cols = {"student_id", "routine_id", "day_name", "session_date", "original_exercise_id"}
    has_legacy_unique = False
    has_session_unique = False
    has_legacy_lookup_index = False

    with eng.connect() as conn:
        raw_indexes = conn.execute(text("PRAGMA index_list('exercise_replacement_logs')")).fetchall()
        for idx in raw_indexes:
            idx_name = idx[1]
            is_unique = bool(idx[2])
            cols = [row[2] for row in conn.execute(text(f"PRAGMA index_info('{idx_name}')")).fetchall()]
            if is_unique and set(cols) == legacy_cols and len(cols) == len(legacy_cols):
                has_legacy_unique = True
            if is_unique and set(cols) == {"session_id", "original_exercise_id"} and len(cols) == 2:
                has_session_unique = True
            if idx_name == "ix_exercise_replacement_logs_legacy_lookup":
                has_legacy_lookup_index = True

    if has_session_unique and not has_legacy_unique and has_legacy_lookup_index:
        return []

    existing_cols = {c["name"] for c in fresh_inspector.get_columns("exercise_replacement_logs")}
    with eng.connect() as conn:
        dbapi = conn.connection.dbapi_connection
        if hasattr(dbapi, "execute"):
            dbapi.execute("PRAGMA foreign_keys=OFF;")
        try:
            with conn.begin():
                conn.execute(
                    text(
                        """
                        CREATE TABLE _exercise_replacement_logs_new (
                            id VARCHAR(36) PRIMARY KEY,
                            student_id VARCHAR(36) NOT NULL,
                            session_id VARCHAR(36),
                            routine_id VARCHAR(36) NOT NULL,
                            day_name VARCHAR(100) NOT NULL,
                            session_date DATE NOT NULL,
                            original_exercise_id VARCHAR(36) NOT NULL,
                            replacement_exercise_id VARCHAR(36),
                            updated_at DATETIME NOT NULL,
                            CONSTRAINT uq_exercise_replacement_session_exercise UNIQUE (session_id, original_exercise_id),
                            FOREIGN KEY(student_id) REFERENCES student_profiles (id) ON DELETE CASCADE,
                            FOREIGN KEY(session_id) REFERENCES workout_sessions (id) ON DELETE CASCADE,
                            FOREIGN KEY(original_exercise_id) REFERENCES exercises (id),
                            FOREIGN KEY(replacement_exercise_id) REFERENCES exercises (id)
                        )
                        """
                    )
                )
                target_cols = [
                    "id",
                    "student_id",
                    "session_id",
                    "routine_id",
                    "day_name",
                    "session_date",
                    "original_exercise_id",
                    "replacement_exercise_id",
                    "updated_at",
                ]
                copy_cols = [c for c in target_cols if c in existing_cols]
                cols_sql = ", ".join(copy_cols)
                conn.execute(
                    text(
                        f"INSERT INTO _exercise_replacement_logs_new ({cols_sql}) "
                        f"SELECT {cols_sql} FROM exercise_replacement_logs"
                    )
                )
                conn.execute(text("DROP TABLE exercise_replacement_logs"))
                conn.execute(text("ALTER TABLE _exercise_replacement_logs_new RENAME TO exercise_replacement_logs"))
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_exercise_replacement_logs_student_id "
                        "ON exercise_replacement_logs (student_id)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_exercise_replacement_logs_session_id "
                        "ON exercise_replacement_logs (session_id)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_exercise_replacement_logs_legacy_lookup "
                        "ON exercise_replacement_logs (student_id, routine_id, day_name, session_date, original_exercise_id)"
                    )
                )
        finally:
            if hasattr(dbapi, "execute"):
                dbapi.execute("PRAGMA foreign_keys=ON;")

    key = "exercise_replacement_logs.uq_exercise_replacement_session_exercise:sqlite_table_rebuild"
    logger.info("Migración de tabla aplicada en SQLite: %s", key)
    return [key]


def _migrate_sqlite_achievement_congratulations(eng: Engine) -> list[str]:
    """Migra achievement_congratulations en SQLite para unicidad compuesta (achievement_id, trainer_id)."""
    fresh_inspector = inspect(eng)
    existing_tables = set(fresh_inspector.get_table_names())
    if "achievement_congratulations" not in existing_tables:
        return []

    has_legacy_single = False
    has_composite_unique = False
    with eng.connect() as conn:
        for idx in conn.execute(text("PRAGMA index_list('achievement_congratulations')")).fetchall():
            idx_name = idx[1]
            is_unique = bool(idx[2])
            if not is_unique:
                continue
            cols = [row[2] for row in conn.execute(text(f"PRAGMA index_info('{idx_name}')")).fetchall()]
            if cols == ["achievement_id"]:
                has_legacy_single = True
            elif set(cols) == {"achievement_id", "trainer_id"} and len(cols) == 2:
                has_composite_unique = True

    if has_composite_unique and not has_legacy_single:
        return []

    with eng.connect() as conn:
        dbapi = conn.connection.dbapi_connection
        if hasattr(dbapi, "execute"):
            dbapi.execute("PRAGMA foreign_keys=OFF;")
        try:
            with conn.begin():
                conn.execute(
                    text(
                        """
                        CREATE TABLE _achievement_congratulations_new (
                            id VARCHAR(36) PRIMARY KEY,
                            achievement_id VARCHAR(36) NOT NULL,
                            trainer_id VARCHAR(36) NOT NULL,
                            message TEXT NOT NULL,
                            created_at DATETIME NOT NULL,
                            seen_at DATETIME,
                            CONSTRAINT uq_achievement_congratulations_achievement_trainer
                                UNIQUE (achievement_id, trainer_id),
                            FOREIGN KEY(achievement_id) REFERENCES student_achievements (id) ON DELETE CASCADE,
                            FOREIGN KEY(trainer_id) REFERENCES trainer_profiles (id) ON DELETE CASCADE
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        "INSERT INTO _achievement_congratulations_new "
                        "(id, achievement_id, trainer_id, message, created_at, seen_at) "
                        "SELECT id, achievement_id, trainer_id, message, created_at, seen_at "
                        "FROM achievement_congratulations"
                    )
                )
                conn.execute(text("DROP TABLE achievement_congratulations"))
                conn.execute(
                    text("ALTER TABLE _achievement_congratulations_new RENAME TO achievement_congratulations")
                )
        finally:
            if hasattr(dbapi, "execute"):
                dbapi.execute("PRAGMA foreign_keys=ON;")

    key = "achievement_congratulations.uq_achievement_congratulations_achievement_trainer:sqlite_table_rebuild"
    logger.info("Migración de tabla aplicada en SQLite: %s", key)
    return [key]


def _migrate_sqlite_technical_notes_fk(eng: Engine) -> list[str]:
    """Agrega la clave foránea de technical_notes.acknowledged_session_id a workout_sessions en SQLite."""
    fresh_inspector = inspect(eng)
    existing_tables = set(fresh_inspector.get_table_names())
    if not {"technical_notes", "workout_sessions"}.issubset(existing_tables):
        return []

    has_fk = any(
        fk.get("referred_table") == "workout_sessions"
        and fk.get("constrained_columns") == ["acknowledged_session_id"]
        for fk in fresh_inspector.get_foreign_keys("technical_notes")
    )
    if has_fk:
        return []

    with eng.connect() as conn:
        dbapi = conn.connection.dbapi_connection
        if hasattr(dbapi, "execute"):
            dbapi.execute("PRAGMA foreign_keys=OFF;")
        try:
            with conn.begin():
                conn.execute(
                    text(
                        """
                        UPDATE technical_notes
                        SET acknowledged_session_id = NULL
                        WHERE acknowledged_session_id IS NOT NULL
                          AND NOT EXISTS (
                            SELECT 1 FROM workout_sessions ws
                            WHERE ws.id = technical_notes.acknowledged_session_id
                          )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE TABLE _technical_notes_new (
                            id VARCHAR(36) PRIMARY KEY,
                            relationship_id VARCHAR(36) NOT NULL,
                            message_id VARCHAR(36) UNIQUE NOT NULL,
                            exercise_id VARCHAR(36),
                            exercise_name VARCHAR(150) NOT NULL,
                            created_at DATETIME NOT NULL,
                            acknowledged_at DATETIME,
                            acknowledged_session_id VARCHAR(36),
                            FOREIGN KEY(relationship_id) REFERENCES training_relationships (id) ON DELETE CASCADE,
                            FOREIGN KEY(message_id) REFERENCES conversation_messages (id) ON DELETE CASCADE,
                            FOREIGN KEY(exercise_id) REFERENCES exercises (id) ON DELETE SET NULL,
                            FOREIGN KEY(acknowledged_session_id) REFERENCES workout_sessions (id) ON DELETE SET NULL
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        "INSERT INTO _technical_notes_new "
                        "(id, relationship_id, message_id, exercise_id, exercise_name, "
                        "created_at, acknowledged_at, acknowledged_session_id) "
                        "SELECT id, relationship_id, message_id, exercise_id, exercise_name, "
                        "created_at, acknowledged_at, acknowledged_session_id "
                        "FROM technical_notes"
                    )
                )
                conn.execute(text("DROP TABLE technical_notes"))
                conn.execute(text("ALTER TABLE _technical_notes_new RENAME TO technical_notes"))
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_technical_notes_relationship_id "
                        "ON technical_notes (relationship_id)"
                    )
                )
        finally:
            if hasattr(dbapi, "execute"):
                dbapi.execute("PRAGMA foreign_keys=ON;")

    key = "technical_notes.fk_technical_notes_acknowledged_session:sqlite_table_rebuild"
    logger.info("Migración de tabla aplicada en SQLite: %s", key)
    return [key]


def _migrate_sqlite_conversation_messages_fk(eng: Engine) -> list[str]:
    """Agrega la clave foránea de conversation_messages.session_id a workout_sessions en SQLite."""
    fresh_inspector = inspect(eng)
    existing_tables = set(fresh_inspector.get_table_names())
    if not {"conversation_messages", "workout_sessions"}.issubset(existing_tables):
        return []

    has_fk = any(
        fk.get("referred_table") == "workout_sessions"
        and fk.get("constrained_columns") == ["session_id"]
        for fk in fresh_inspector.get_foreign_keys("conversation_messages")
    )
    if has_fk:
        return []

    with eng.connect() as conn:
        dbapi = conn.connection.dbapi_connection
        if hasattr(dbapi, "execute"):
            dbapi.execute("PRAGMA foreign_keys=OFF;")
        try:
            with conn.begin():
                conn.execute(
                    text(
                        """
                        UPDATE conversation_messages
                        SET session_id = NULL
                        WHERE session_id IS NOT NULL
                          AND NOT EXISTS (
                            SELECT 1 FROM workout_sessions ws
                            WHERE ws.id = conversation_messages.session_id
                          )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE TABLE _conversation_messages_new (
                            id VARCHAR(36) PRIMARY KEY,
                            relationship_id VARCHAR(36) NOT NULL,
                            sender_user_id VARCHAR(36) NOT NULL,
                            sender_role VARCHAR(16) NOT NULL,
                            kind VARCHAR(24) NOT NULL,
                            body TEXT NOT NULL,
                            exercise_id VARCHAR(36),
                            exercise_name VARCHAR(150),
                            session_id VARCHAR(36),
                            set_number INTEGER,
                            reply_to_message_id VARCHAR(36),
                            created_at DATETIME NOT NULL,
                            read_at DATETIME,
                            CONSTRAINT ck_conversation_messages_sender_role CHECK (sender_role IN ('TRAINER', 'STUDENT')),
                            CONSTRAINT ck_conversation_messages_kind CHECK (kind IN ('TEXT', 'TECHNICAL_QUERY')),
                            CONSTRAINT ck_conversation_messages_query_exercise CHECK (kind <> 'TECHNICAL_QUERY' OR exercise_name IS NOT NULL),
                            CONSTRAINT ck_conversation_messages_reply_kind CHECK (reply_to_message_id IS NULL OR kind = 'TEXT'),
                            FOREIGN KEY(relationship_id) REFERENCES training_relationships (id) ON DELETE CASCADE,
                            FOREIGN KEY(sender_user_id) REFERENCES users (id) ON DELETE CASCADE,
                            FOREIGN KEY(exercise_id) REFERENCES exercises (id) ON DELETE SET NULL,
                            FOREIGN KEY(session_id) REFERENCES workout_sessions (id) ON DELETE SET NULL,
                            FOREIGN KEY(reply_to_message_id) REFERENCES conversation_messages (id) ON DELETE CASCADE
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        "INSERT INTO _conversation_messages_new "
                        "(id, relationship_id, sender_user_id, sender_role, kind, body, "
                        "exercise_id, exercise_name, session_id, set_number, reply_to_message_id, "
                        "created_at, read_at) "
                        "SELECT id, relationship_id, sender_user_id, sender_role, kind, body, "
                        "exercise_id, exercise_name, session_id, set_number, reply_to_message_id, "
                        "created_at, read_at "
                        "FROM conversation_messages"
                    )
                )
                conn.execute(text("DROP TABLE conversation_messages"))
                conn.execute(text("ALTER TABLE _conversation_messages_new RENAME TO conversation_messages"))
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_conversation_messages_relationship_created "
                        "ON conversation_messages (relationship_id, created_at)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_conversation_messages_reply_to "
                        "ON conversation_messages (reply_to_message_id)"
                    )
                )
        finally:
            if hasattr(dbapi, "execute"):
                dbapi.execute("PRAGMA foreign_keys=ON;")

    key = "conversation_messages.fk_conversation_messages_session_id:sqlite_table_rebuild"
    logger.info("Migración de tabla aplicada en SQLite: %s", key)
    return [key]


def apply_migrations(target_engine: Engine | None = None) -> list[str]:
    """Aplica de forma aditiva e idempotente las columnas faltantes y ampliaciones de tipo en tablas existentes."""
    eng = target_engine or engine
    if eng.dialect.name == "postgresql":
        enum_names = {enum["name"] for enum in inspect(eng).get_enums()}
        if "video_platform" not in enum_names:
            with eng.begin() as conn:
                conn.execute(
                    text(
                        "CREATE TYPE video_platform AS ENUM "
                        "('YOUTUBE', 'VIMEO', 'GOOGLE_DRIVE', 'NONE')"
                    )
                )

    # 1. Asegurar la creación de tablas que aún no existan
    Base.metadata.create_all(bind=eng)

    inspector = inspect(eng)
    existing_tables = set(inspector.get_table_names())
    is_sqlite = eng.dialect.name == "sqlite"
    applied: list[str] = []

    with eng.begin() as conn:
        for m in TARGET_COLUMNS:
            if m.table not in existing_tables:
                continue
            # Reflect through the migration connection. Using an Engine-bound
            # inspector here can check out a second connection while this
            # transaction holds ALTER TABLE locks, leaving that inspection
            # blocked by the migration itself.
            cols = {c["name"] for c in inspect(conn).get_columns(m.table)}
            if m.column not in cols:
                col_type = m.sqlite_type if is_sqlite else m.postgres_type
                default = m.sqlite_default if is_sqlite else m.postgres_default
                stmt = f"ALTER TABLE {m.table} ADD COLUMN {m.column} {col_type}"
                if not m.nullable:
                    stmt += f" DEFAULT {default} NOT NULL"
                conn.execute(text(stmt))
                key = f"{m.table}.{m.column}"
                applied.append(key)
                logger.info("Migración aplicada: %s", key)

        applied.extend(_backfill_routine_assigned_at(conn, existing_tables))
        applied.extend(_backfill_routine_assignment_lineage(conn, existing_tables))

        # 2. Ampliaciones de tipo de columna en bases de datos relacionales estrictas (p. ej. PostgreSQL)
        if not is_sqlite:
            for alt in TARGET_TYPE_ALTERATIONS:
                if alt.table not in existing_tables:
                    continue
                cols = {c["name"]: c for c in inspect(conn).get_columns(alt.table)}
                if alt.column in cols:
                    curr_col = cols[alt.column]
                    curr_len = getattr(curr_col["type"], "length", None)
                    if curr_len is not None and curr_len < alt.target_length:
                        stmt = f"ALTER TABLE {alt.table} ALTER COLUMN {alt.column} TYPE {alt.postgres_type}"
                        conn.execute(text(stmt))
                        key = f"{alt.table}.{alt.column}:type_{alt.postgres_type.lower()}"
                        applied.append(key)
                        logger.info("Migración de tipo de columna aplicada: %s", key)

        # 3. Restricciones CHECK en bases de datos relacionales estrictas (p. ej. PostgreSQL)
        if not is_sqlite:
            for ck in TARGET_CHECK_CONSTRAINTS:
                if ck.table not in existing_tables:
                    continue
                existing_cks = {c.get("name") for c in inspect(conn).get_check_constraints(ck.table)}
                if ck.name not in existing_cks:
                    stmt = f"ALTER TABLE {ck.table} ADD CONSTRAINT {ck.name} CHECK ({ck.expression})"
                    conn.execute(text(stmt))
                    key = f"{ck.table}.{ck.name}:check_constraint"
                    applied.append(key)
                    logger.info("Restricción CHECK aplicada: %s", key)

        # 4. Restricción de unicidad compuesta en body_map_pain_reports (PostgreSQL)
        if not is_sqlite and "body_map_pain_reports" in existing_tables:
            unique_constraints = inspect(conn).get_unique_constraints("body_map_pain_reports")
            for uq in unique_constraints:
                uq_cols = uq.get("column_names") or []
                uq_name = uq.get("name")
                if uq_cols == ["idempotency_key"] and uq_name:
                    conn.execute(text(f'ALTER TABLE body_map_pain_reports DROP CONSTRAINT IF EXISTS "{uq_name}"'))
                    key = f"body_map_pain_reports.{uq_name}:drop_legacy_unique"
                    applied.append(key)
                    logger.info("Restricción UNIQUE heredada eliminada: %s", key)

            indexes = inspect(conn).get_indexes("body_map_pain_reports")
            for idx in indexes:
                idx_cols = idx.get("column_names") or []
                idx_name = idx.get("name")
                if idx.get("unique") and idx_cols == ["idempotency_key"] and idx_name:
                    conn.execute(text(f'DROP INDEX IF EXISTS "{idx_name}"'))
                    key = f"body_map_pain_reports.{idx_name}:drop_legacy_unique_index"
                    applied.append(key)
                    logger.info("Índice UNIQUE heredado eliminado: %s", key)

            existing_uq_names = {u.get("name") for u in inspect(conn).get_unique_constraints("body_map_pain_reports")}
            if "uq_body_map_student_idempotency" not in existing_uq_names:
                conn.execute(
                    text(
                        "ALTER TABLE body_map_pain_reports "
                        "ADD CONSTRAINT uq_body_map_student_idempotency "
                        "UNIQUE (student_id, idempotency_key)"
                    )
                )
                key = "body_map_pain_reports.uq_body_map_student_idempotency:unique_constraint"
                applied.append(key)
                logger.info("Restricción UNIQUE compuesta aplicada: %s", key)

            existing_idx_names = {i.get("name") for i in inspect(conn).get_indexes("body_map_pain_reports")}
            if "ix_body_map_pain_reports_idempotency_key" not in existing_idx_names:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_body_map_pain_reports_idempotency_key "
                        "ON body_map_pain_reports (idempotency_key)"
                    )
                )

        if "safety_alerts" in existing_tables:
            existing_sa_idx_names = {i.get("name") for i in inspect(conn).get_indexes("safety_alerts")}
            if "ix_safety_alerts_trainer_status_created" not in existing_sa_idx_names:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_safety_alerts_trainer_status_created "
                        "ON safety_alerts (trainer_id, status, created_at)"
                    )
                )
                applied.append("safety_alerts.ix_safety_alerts_trainer_status_created:index")
            if "ix_safety_alerts_relationship_status" not in existing_sa_idx_names:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_safety_alerts_relationship_status "
                        "ON safety_alerts (relationship_id, status)"
                    )
                )
                applied.append("safety_alerts.ix_safety_alerts_relationship_status:index")

        if not is_sqlite and "exercise_replacement_logs" in existing_tables:
            pg_insp = inspect(conn)
            legacy_cols = {"student_id", "routine_id", "day_name", "session_date", "original_exercise_id"}
            for uq in pg_insp.get_unique_constraints("exercise_replacement_logs"):
                uq_cols = set(uq.get("column_names") or [])
                uq_name = uq.get("name")
                if uq_name and uq_cols == legacy_cols:
                    conn.execute(text(f'ALTER TABLE exercise_replacement_logs DROP CONSTRAINT IF EXISTS "{uq_name}"'))
                    applied.append(f"exercise_replacement_logs.{uq_name}:drop_legacy_unique")
            existing_uq_names = {u.get("name") for u in pg_insp.get_unique_constraints("exercise_replacement_logs")}
            if "uq_exercise_replacement_session_exercise" not in existing_uq_names:
                conn.execute(
                    text(
                        "ALTER TABLE exercise_replacement_logs "
                        "ADD CONSTRAINT uq_exercise_replacement_session_exercise "
                        "UNIQUE (session_id, original_exercise_id)"
                    )
                )
                applied.append("exercise_replacement_logs.uq_exercise_replacement_session_exercise:unique_constraint")
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_exercise_replacement_logs_session_id "
                    "ON exercise_replacement_logs (session_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_exercise_replacement_logs_legacy_lookup "
                    "ON exercise_replacement_logs (student_id, routine_id, day_name, session_date, original_exercise_id)"
                )
            )

        if "notifications" in existing_tables:
            notif_insp = inspect(conn)
            notif_cols = {c["name"] for c in notif_insp.get_columns("notifications")}
            notif_idx_names = {i.get("name") for i in notif_insp.get_indexes("notifications")}
            if (
                "uq_notifications_streak_reset" not in notif_idx_names
                and {"id", "recipient_id", "type", "related_entity_id"}.issubset(notif_cols)
            ):
                conn.execute(
                    text(
                        """
                        DELETE FROM notifications
                        WHERE type = 'STREAK_RESET'
                          AND related_entity_id IS NOT NULL
                          AND id NOT IN (
                            SELECT MIN(id) FROM notifications
                            WHERE type = 'STREAK_RESET' AND related_entity_id IS NOT NULL
                            GROUP BY recipient_id, related_entity_id
                          )
                        """
                    )
                )
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uq_notifications_streak_reset "
                        "ON notifications (recipient_id, related_entity_id) "
                        "WHERE type = 'STREAK_RESET'"
                    )
                )
                applied.append("notifications.uq_notifications_streak_reset:unique_index")

        if {"technical_notes", "workout_sessions"}.issubset(existing_tables):
            conn.execute(
                text(
                    """
                    UPDATE technical_notes
                    SET acknowledged_session_id = NULL
                    WHERE acknowledged_session_id IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM workout_sessions ws
                        WHERE ws.id = technical_notes.acknowledged_session_id
                      )
                    """
                )
            )
            if not is_sqlite:
                tn_insp = inspect(conn)
                has_tn_fk = any(
                    fk.get("referred_table") == "workout_sessions"
                    and fk.get("constrained_columns") == ["acknowledged_session_id"]
                    for fk in tn_insp.get_foreign_keys("technical_notes")
                )
                if not has_tn_fk:
                    conn.execute(
                        text(
                            "ALTER TABLE technical_notes "
                            "ADD CONSTRAINT fk_technical_notes_acknowledged_session "
                            "FOREIGN KEY (acknowledged_session_id) REFERENCES workout_sessions (id) ON DELETE SET NULL"
                        )
                    )
                    applied.append("technical_notes.fk_technical_notes_acknowledged_session:foreign_key")

        if {"conversation_messages", "workout_sessions"}.issubset(existing_tables):
            conn.execute(
                text(
                    """
                    UPDATE conversation_messages
                    SET session_id = NULL
                    WHERE session_id IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM workout_sessions ws
                        WHERE ws.id = conversation_messages.session_id
                      )
                    """
                )
            )
            if not is_sqlite:
                cm_insp = inspect(conn)
                has_cm_fk = any(
                    fk.get("referred_table") == "workout_sessions"
                    and fk.get("constrained_columns") == ["session_id"]
                    for fk in cm_insp.get_foreign_keys("conversation_messages")
                )
                if not has_cm_fk:
                    conn.execute(
                        text(
                            "ALTER TABLE conversation_messages "
                            "ADD CONSTRAINT fk_conversation_messages_session_id "
                            "FOREIGN KEY (session_id) REFERENCES workout_sessions (id) ON DELETE SET NULL"
                        )
                    )
                    applied.append("conversation_messages.fk_conversation_messages_session_id:foreign_key")

        if not is_sqlite and {"informal_payments", "users"}.issubset(existing_tables):
            ip_insp = inspect(conn)
            ip_fks = {
                tuple(fk.get("constrained_columns") or [])
                for fk in ip_insp.get_foreign_keys("informal_payments")
                if fk.get("referred_table") == "users"
            }
            for col_name, fk_name in (
                ("confirmed_by_user_id", "fk_informal_payments_confirmed_by_user"),
                ("rejected_by_user_id", "fk_informal_payments_rejected_by_user"),
            ):
                if (col_name,) not in ip_fks:
                    conn.execute(
                        text(
                            f"ALTER TABLE informal_payments "
                            f"ADD CONSTRAINT {fk_name} FOREIGN KEY ({col_name}) REFERENCES users (id)"
                        )
                    )
                    applied.append(f"informal_payments.{fk_name}:foreign_key")

        if not is_sqlite and "achievement_congratulations" in existing_tables:
            ac_insp = inspect(conn)
            for uq in ac_insp.get_unique_constraints("achievement_congratulations"):
                uq_cols = uq.get("column_names") or []
                uq_name = uq.get("name")
                if uq_name and uq_cols == ["achievement_id"]:
                    conn.execute(text(f'ALTER TABLE achievement_congratulations DROP CONSTRAINT IF EXISTS "{uq_name}"'))
                    applied.append(f"achievement_congratulations.{uq_name}:drop_legacy_unique")
            for idx in ac_insp.get_indexes("achievement_congratulations"):
                idx_cols = idx.get("column_names") or []
                idx_name = idx.get("name")
                if idx.get("unique") and idx_cols == ["achievement_id"] and idx_name:
                    conn.execute(text(f'DROP INDEX IF EXISTS "{idx_name}"'))
                    applied.append(f"achievement_congratulations.{idx_name}:drop_legacy_unique_index")
            ac_uqs = {u.get("name") for u in inspect(conn).get_unique_constraints("achievement_congratulations")}
            if "uq_achievement_congratulations_achievement_trainer" not in ac_uqs:
                conn.execute(
                    text(
                        "ALTER TABLE achievement_congratulations "
                        "ADD CONSTRAINT uq_achievement_congratulations_achievement_trainer "
                        "UNIQUE (achievement_id, trainer_id)"
                    )
                )
                applied.append(
                    "achievement_congratulations.uq_achievement_congratulations_achievement_trainer:unique_constraint"
                )

    # 5. Migración de restricciones CHECK y UNIQUE en SQLite existente mediante reconstrucción segura de tabla
    if is_sqlite:
        sqlite_ck_applied = _migrate_sqlite_workout_sessions_check_constraint(eng, inspector)
        applied.extend(sqlite_ck_applied)
        sqlite_uq_applied = _migrate_sqlite_body_map_pain_reports_unique_constraint(eng, inspector)
        applied.extend(sqlite_uq_applied)
        sqlite_repl_applied = _migrate_sqlite_exercise_replacement_logs(eng)
        applied.extend(sqlite_repl_applied)
        applied.extend(_migrate_sqlite_achievement_congratulations(eng))
        applied.extend(_migrate_sqlite_technical_notes_fk(eng))
        applied.extend(_migrate_sqlite_conversation_messages_fk(eng))

    return applied


if __name__ == "__main__":
    import sys

    print("Ejecutando migraciones de esquema...")
    results = apply_migrations()
    if results:
        print(f"Columnas agregadas o actualizadas ({len(results)}): {', '.join(results)}")
    else:
        print("El esquema ya se encuentra completamente actualizado. No se requirieron cambios.")
    sys.exit(0)
