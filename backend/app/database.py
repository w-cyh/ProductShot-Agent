from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


settings.ensure_dirs()
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def ensure_sqlite_compat_schema() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "generated_images" not in inspector.get_table_names():
        return

    if "projects" in inspector.get_table_names():
        project_existing = {column["name"] for column in inspector.get_columns("projects")}
        with engine.begin() as connection:
            if "source_confirmed_at" not in project_existing:
                connection.execute(text("ALTER TABLE projects ADD COLUMN source_confirmed_at DATETIME"))
            connection.execute(
                text(
                    "UPDATE projects SET source_confirmed_at = COALESCE(source_confirmed_at, updated_at, CURRENT_TIMESTAMP) "
                    "WHERE source_confirmed_at IS NULL AND ("
                    "EXISTS (SELECT 1 FROM product_visual_analyses WHERE product_visual_analyses.project_id = projects.id) "
                    "OR EXISTS (SELECT 1 FROM creative_plans WHERE creative_plans.project_id = projects.id) "
                    "OR EXISTS (SELECT 1 FROM generation_tasks WHERE generation_tasks.project_id = projects.id)"
                    ")"
                )
            )

    existing = {column["name"] for column in inspector.get_columns("generated_images")}
    columns = {
        "plan_id": "INTEGER",
        "platform": "VARCHAR(80)",
        "generation_mode": "VARCHAR(80)",
        "prompt_pack_id": "VARCHAR(120)",
        "prompt_pack_json": "TEXT",
        "is_recommended": "BOOLEAN NOT NULL DEFAULT 0",
    }
    with engine.begin() as connection:
        for name, ddl in columns.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE generated_images ADD COLUMN {name} {ddl}"))

    if "image_reviews" in inspector.get_table_names():
        review_existing = {column["name"] for column in inspector.get_columns("image_reviews")}
        review_columns = {
            "product_consistency_score": "INTEGER NOT NULL DEFAULT 80",
            "text_artifact_risk": "VARCHAR(40) NOT NULL DEFAULT 'low'",
            "ai_artifact_risk": "VARCHAR(40) NOT NULL DEFAULT 'low'",
            "recommendation_level": "VARCHAR(40) NOT NULL DEFAULT 'usable'",
        }
        with engine.begin() as connection:
            for name, ddl in review_columns.items():
                if name not in review_existing:
                    connection.execute(text(f"ALTER TABLE image_reviews ADD COLUMN {name} {ddl}"))

    if "creative_plans" in inspector.get_table_names():
        plan_existing = {column["name"] for column in inspector.get_columns("creative_plans")}
        plan_columns = {
            "plan_batch_id": "INTEGER",
            "parent_plan_id": "INTEGER",
            "version": "INTEGER NOT NULL DEFAULT 1",
            "is_current": "BOOLEAN NOT NULL DEFAULT 1",
        }
        with engine.begin() as connection:
            for name, ddl in plan_columns.items():
                if name not in plan_existing:
                    connection.execute(text(f"ALTER TABLE creative_plans ADD COLUMN {name} {ddl}"))

            legacy_projects = connection.execute(
                text("SELECT DISTINCT project_id FROM creative_plans WHERE plan_batch_id IS NULL")
            ).scalars().all()
            for project_id in legacy_projects:
                result = connection.execute(
                    text(
                        "INSERT INTO creative_plan_batches (project_id, kind, feedback, created_at) "
                        "VALUES (:project_id, 'legacy', '', CURRENT_TIMESTAMP)"
                    ),
                    {"project_id": project_id},
                )
                connection.execute(
                    text("UPDATE creative_plans SET plan_batch_id = :batch_id, version = COALESCE(version, 1) "
                         "WHERE project_id = :project_id AND plan_batch_id IS NULL"),
                    {"batch_id": result.lastrowid, "project_id": project_id},
                )

            project_ids = connection.execute(text("SELECT DISTINCT project_id FROM creative_plans")).scalars().all()
            for project_id in project_ids:
                connection.execute(
                    text("UPDATE creative_plans SET is_current = 0 WHERE project_id = :project_id"),
                    {"project_id": project_id},
                )
                current_batch_id = connection.execute(
                    text(
                        "SELECT id FROM creative_plan_batches WHERE project_id = :project_id "
                        "AND kind IN ('initial', 'refresh', 'legacy') ORDER BY created_at DESC, id DESC LIMIT 1"
                    ),
                    {"project_id": project_id},
                ).scalar()
                if current_batch_id:
                    connection.execute(
                        text("UPDATE creative_plans SET is_current = 1 WHERE plan_batch_id = :batch_id"),
                        {"batch_id": current_batch_id},
                    )
                revisions = connection.execute(
                    text(
                        "SELECT id, parent_plan_id FROM creative_plans WHERE project_id = :project_id "
                        "AND parent_plan_id IS NOT NULL ORDER BY created_at ASC, id ASC"
                    ),
                    {"project_id": project_id},
                ).mappings()
                for revision in revisions:
                    parent_is_current = connection.execute(
                        text("SELECT is_current FROM creative_plans WHERE id = :plan_id"),
                        {"plan_id": revision["parent_plan_id"]},
                    ).scalar()
                    if parent_is_current:
                        connection.execute(
                            text("UPDATE creative_plans SET is_current = 0 WHERE id = :plan_id"),
                            {"plan_id": revision["parent_plan_id"]},
                        )
                        connection.execute(
                            text("UPDATE creative_plans SET is_current = 1 WHERE id = :plan_id"),
                            {"plan_id": revision["id"]},
                        )

    if "creative_plan_batches" in inspector.get_table_names():
        batch_existing = {column["name"] for column in inspector.get_columns("creative_plan_batches")}
        batch_columns = {
            "platforms_json": "TEXT NOT NULL DEFAULT '[]'",
            "style_presets_json": "TEXT NOT NULL DEFAULT '[]'",
        }
        with engine.begin() as connection:
            for name, ddl in batch_columns.items():
                if name not in batch_existing:
                    connection.execute(text(f"ALTER TABLE creative_plan_batches ADD COLUMN {name} {ddl}"))

    if "generation_tasks" in inspector.get_table_names():
        task_existing = {column["name"] for column in inspector.get_columns("generation_tasks")}
        task_columns = {
            "prompt_pack_id": "INTEGER",
            "parent_image_id": "INTEGER",
            "iteration": "INTEGER NOT NULL DEFAULT 1",
            "requested_count": "INTEGER NOT NULL DEFAULT 1",
            "generated_count": "INTEGER NOT NULL DEFAULT 0",
            "reviewed_count": "INTEGER NOT NULL DEFAULT 0",
            "progress_stage": "VARCHAR(40) NOT NULL DEFAULT 'queued'",
            "started_at": "DATETIME",
            "completed_at": "DATETIME",
        }
        with engine.begin() as connection:
            for name, ddl in task_columns.items():
                if name not in task_existing:
                    connection.execute(text(f"ALTER TABLE generation_tasks ADD COLUMN {name} {ddl}"))
            connection.execute(
                text(
                    "UPDATE generation_tasks SET requested_count = "
                    "MAX(1, (SELECT COUNT(*) FROM generated_images WHERE generated_images.task_id = generation_tasks.id)), "
                    "generated_count = (SELECT COUNT(*) FROM generated_images WHERE generated_images.task_id = generation_tasks.id), "
                    "reviewed_count = (SELECT COUNT(*) FROM image_reviews "
                    "WHERE image_id IN (SELECT id FROM generated_images WHERE task_id = generation_tasks.id)), "
                    "progress_stage = CASE WHEN status = 'success' THEN 'completed' "
                    "WHEN status = 'failed' THEN 'failed' ELSE COALESCE(progress_stage, 'queued') END"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_generation_tasks_one_active_per_project "
                    "ON generation_tasks(project_id) WHERE status IN ('queued', 'running')"
                )
            )

    if "copywriting" in inspector.get_table_names():
        copy_existing = {column["name"] for column in inspector.get_columns("copywriting")}
        copy_columns = {
            "douyin_script": "TEXT NOT NULL DEFAULT ''",
            "parent_copywriting_id": "INTEGER",
            "version": "INTEGER NOT NULL DEFAULT 1",
            "revision_kind": "VARCHAR(40) NOT NULL DEFAULT 'generated'",
            "revision_instruction": "TEXT NOT NULL DEFAULT ''",
            "xianyu_text": "TEXT NOT NULL DEFAULT ''",
        }
        with engine.begin() as connection:
            for name, ddl in copy_columns.items():
                if name not in copy_existing:
                    connection.execute(text(f"ALTER TABLE copywriting ADD COLUMN {name} {ddl}"))
            connection.execute(
                text("UPDATE copywriting SET xianyu_text = douyin_script WHERE xianyu_text = '' AND douyin_script != ''")
            )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
