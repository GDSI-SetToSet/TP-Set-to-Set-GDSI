"""Migraciones explícitas, aditivas e idempotentes para bases de datos persistentes.

Asegura la correspondencia entre los modelos SQLAlchemy y las tablas físicas
sin destruir tablas preexistentes ni sobrescribir datos.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import Engine, inspect, text

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
)


def apply_migrations(target_engine: Engine | None = None) -> list[str]:
    """Aplica de forma aditiva e idempotente las columnas faltantes en tablas existentes."""
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

    return applied


if __name__ == "__main__":
    import sys

    print("Ejecutando migraciones de esquema...")
    results = apply_migrations()
    if results:
        print(f"Columnas agregadas ({len(results)}): {', '.join(results)}")
    else:
        print("El esquema ya se encuentra completamente actualizado. No se requirieron cambios.")
    sys.exit(0)
