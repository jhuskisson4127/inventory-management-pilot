from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import MetaData, create_engine, func, inspect, select

from app.db import Base, engine as target_engine

TABLE_NAMES = ("products", "physical_counts")


def migrate() -> None:
    source_url = os.environ.get("SOURCE_DATABASE_URL", "").strip()
    target_url = os.environ.get("DATABASE_URL", "").strip()
    if not source_url:
        raise SystemExit("SOURCE_DATABASE_URL is required. No source database was changed.")
    if not target_url:
        raise SystemExit("DATABASE_URL is required for the MySQL 8 destination.")

    source_engine = create_engine(source_url, pool_pre_ping=True)
    if source_engine.dialect.name != "postgresql":
        raise SystemExit("SOURCE_DATABASE_URL must point to the existing PostgreSQL database.")
    if target_engine.dialect.name != "mysql":
        raise SystemExit("DATABASE_URL must point to MySQL 8 for this migration.")

    Base.metadata.create_all(bind=target_engine)
    source_metadata = MetaData()
    source_metadata.reflect(bind=source_engine, only=TABLE_NAMES)
    target_metadata = Base.metadata

    for name in TABLE_NAMES:
        if name not in source_metadata.tables:
            raise SystemExit(f"Source table '{name}' is missing; migration stopped.")
        source_columns = set(source_metadata.tables[name].columns.keys())
        target_columns = set(target_metadata.tables[name].columns.keys())
        if source_columns != target_columns:
            raise SystemExit(f"Column mismatch in '{name}'; migration stopped without copying rows.")

    with target_engine.begin() as destination:
        for name in TABLE_NAMES:
            table = target_metadata.tables[name]
            existing = destination.scalar(select(func.count()).select_from(table))
            if existing:
                raise SystemExit(
                    f"Destination table '{name}' already has {existing} rows. "
                    "Migration requires an empty MySQL destination; no rows were changed."
                )

    copied: dict[str, int] = {}
    try:
        with source_engine.connect().execution_options(isolation_level="REPEATABLE READ") as source, target_engine.begin() as destination:
            for name in TABLE_NAMES:
                source_table = source_metadata.tables[name]
                target_table = target_metadata.tables[name]
                rows = [dict(row) for row in source.execute(select(source_table).order_by(source_table.c.id)).mappings()]
                for row in rows:
                    for column in target_table.columns:
                        value = row[column.name]
                        if isinstance(value, datetime) and value.tzinfo is not None:
                            row[column.name] = value.astimezone(timezone.utc).replace(tzinfo=None)
                if rows:
                    destination.execute(target_table.insert(), rows)
                copied[name] = len(rows)
                final_rows = [
                    dict(row)
                    for row in destination.execute(select(target_table).order_by(target_table.c.id)).mappings()
                ]
                if final_rows != rows:
                    raise RuntimeError(f"Data verification failed for '{name}'. The migration transaction was rolled back.")
    except Exception:
        raise
    finally:
        source_engine.dispose()

    for name, amount in copied.items():
        print(f"Copied {amount} rows from {name}.")
    print("Migration complete. The PostgreSQL source was read only; MySQL rows retain their IDs and UTC timestamps.")


if __name__ == "__main__":
    migrate()
