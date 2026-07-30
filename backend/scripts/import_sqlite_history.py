"""One-time, guarded import of local SQLite history into PostgreSQL.

Run with DATABASE_URL set to the PostgreSQL target. The target must not
already contain projects, which prevents accidental data merges or overwrites.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from sqlalchemy import create_engine, inspect, select, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import models  # noqa: F401 - register all metadata tables
from app.config import settings
from app.database import Base


# SQLAlchemy cannot infer an insert order for this schema because a few
# optional history links point forward (for example, a prompt pack can point
# to its parent generated image).  Insert the required graph first, then
# restore those optional links after all referenced rows exist.
IMPORT_ORDER = (
    "projects",
    "product_assets",
    "product_analyses",
    "product_visual_analyses",
    "creative_plan_batches",
    "creative_plans",
    "prompt_packs",
    "generation_tasks",
    "generated_images",
    "image_reviews",
    "quality_runs",
    "quality_rounds",
    "copywriting",
    "workflow_events",
)

FORWARD_REFERENCE_COLUMNS = {
    "creative_plan_batches": ("source_plan_id",),
    "creative_plans": ("parent_plan_id",),
    "prompt_packs": ("parent_image_id",),
    "generation_tasks": ("parent_image_id", "quality_run_id"),
    "image_reviews": ("quality_run_id",),
    "quality_runs": ("recommended_image_id",),
    "copywriting": ("parent_copywriting_id",),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        default=str(settings.data_dir / "productshot.db"),
        help="absolute or relative SQLite history database path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_path = Path(args.source).resolve()
    if not source_path.exists():
        raise SystemExit(f"SQLite history database does not exist: {source_path}")
    if not settings.database_url.startswith("postgresql"):
        raise SystemExit("DATABASE_URL must point to the PostgreSQL target.")

    source = create_engine(f"sqlite:///{source_path}")
    target = create_engine(settings.database_url)
    source_tables = set(inspect(source).get_table_names())
    target_tables = set(inspect(target).get_table_names())
    table_by_name = Base.metadata.tables
    required_tables = set(table_by_name)
    missing = required_tables - target_tables
    if missing:
        raise SystemExit(f"PostgreSQL schema is incomplete; run Alembic first. Missing: {sorted(missing)}")

    with target.connect() as connection:
        existing_projects = connection.execute(text("SELECT COUNT(*) FROM projects")).scalar_one()
    if existing_projects:
        raise SystemExit("PostgreSQL target already contains projects; refusing to merge history automatically.")

    imported: dict[str, int] = {}
    deferred_updates: list[tuple[str, int, str, object]] = []
    with source.connect() as source_connection, target.begin() as target_connection:
        for table_name in IMPORT_ORDER:
            table = table_by_name[table_name]
            if table_name not in source_tables:
                continue
            rows = source_connection.execute(select(table)).mappings().all()
            if not rows:
                continue
            values_to_insert = []
            for row in rows:
                values = dict(row)
                for column in FORWARD_REFERENCE_COLUMNS.get(table_name, ()):
                    reference_id = values.get(column)
                    if reference_id is not None:
                        deferred_updates.append((table_name, values["id"], column, reference_id))
                        values[column] = None
                values_to_insert.append(values)
            target_connection.execute(table.insert(), values_to_insert)
            imported[table_name] = len(rows)

        for table_name, row_id, column, reference_id in deferred_updates:
            table = table_by_name[table_name]
            target_connection.execute(
                table.update().where(table.c.id == row_id).values({column: reference_id})
            )

        for table_name in IMPORT_ORDER:
            table = table_by_name[table_name]
            if "id" not in table.c:
                continue
            target_connection.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence(:table_name, 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table.name}), 1), true)"
                ),
                {"table_name": table.name},
            )

    print("Imported SQLite history into PostgreSQL:")
    for name, count in sorted(imported.items()):
        print(f"- {name}: {count}")


if __name__ == "__main__":
    main()
