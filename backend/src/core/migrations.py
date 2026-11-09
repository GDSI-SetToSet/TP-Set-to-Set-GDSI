"""Migraciones explícitas, aditivas e idempotentes para bases de datos persistentes.

Asegura la correspondencia entre los modelos SQLAlchemy y las tablas físicas
sin destruir tablas preexistentes ni sobrescribir datos.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import Engine, inspect, text

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
                cols_str = ", ".join(cols_target)
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


def apply_migrations(target_engine: Engine | None = None) -> list[str]:
    """Aplica de forma aditiva e idempotente las columnas faltantes y ampliaciones de tipo en tablas existentes."""
    eng = target_engine or engine
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
            cols = {c["name"] for c in inspector.get_columns(m.table)}
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

        # 2. Ampliaciones de tipo de columna en bases de datos relacionales estrictas (p. ej. PostgreSQL)
        if not is_sqlite:
            for alt in TARGET_TYPE_ALTERATIONS:
                if alt.table not in existing_tables:
                    continue
                cols = {c["name"]: c for c in inspector.get_columns(alt.table)}
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
                existing_cks = {c.get("name") for c in inspector.get_check_constraints(ck.table)}
                if ck.name not in existing_cks:
                    stmt = f"ALTER TABLE {ck.table} ADD CONSTRAINT {ck.name} CHECK ({ck.expression})"
                    conn.execute(text(stmt))
                    key = f"{ck.table}.{ck.name}:check_constraint"
                    applied.append(key)
                    logger.info("Restricción CHECK aplicada: %s", key)

    # 4. Migración de restricciones CHECK en SQLite existente mediante reconstrucción segura de tabla
    if is_sqlite:
        sqlite_ck_applied = _migrate_sqlite_workout_sessions_check_constraint(eng, inspector)
        applied.extend(sqlite_ck_applied)

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
