"""Add persisted quality-gated generation state.

Revision ID: 20260730_quality_runs
Revises:
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

from app.database import Base
from app import models  # noqa: F401 - register models before metadata bootstrap
from app.models.entities import QualityRound, QualityRun


revision = "20260730_quality_runs"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite remains the legacy one-shot development mode. Runtime startup
        # applies its compatibility columns; quality runs themselves require
        # PostgreSQL, so SQLite does not need ALTER TABLE foreign-key support.
        Base.metadata.create_all(bind=bind)
        return
    inspector = inspect(bind)
    if "projects" not in inspector.get_table_names():
        # New environments use the existing metadata bootstrap as the baseline;
        # this revision then remains recorded for subsequent schema changes.
        Base.metadata.create_all(bind=bind)
        return

    generation_columns = {column["name"] for column in inspector.get_columns("generation_tasks")}
    review_column_info = {column["name"]: column for column in inspector.get_columns("image_reviews")}
    review_columns = set(review_column_info)

    if "overall_score" in review_column_info and not isinstance(review_column_info["overall_score"]["type"], sa.Float):
        op.alter_column(
            "image_reviews",
            "overall_score",
            existing_type=review_column_info["overall_score"]["type"],
            type_=sa.Float(),
            postgresql_using="overall_score::double precision",
        )

    if "evidence_json" not in review_columns:
        op.add_column("image_reviews", sa.Column("evidence_json", sa.Text(), nullable=False, server_default="[]"))
    if "hard_defects_json" not in review_columns:
        op.add_column("image_reviews", sa.Column("hard_defects_json", sa.Text(), nullable=False, server_default="[]"))
    if "prompt_revision" not in review_columns:
        op.add_column("image_reviews", sa.Column("prompt_revision", sa.Text(), nullable=False, server_default=""))
    if "summary" not in review_columns:
        op.add_column("image_reviews", sa.Column("summary", sa.Text(), nullable=False, server_default=""))

    QualityRun.__table__.create(bind=bind, checkfirst=True)
    quality_run_columns = {column["name"] for column in inspector.get_columns("quality_runs")}
    if "lease_token" not in quality_run_columns:
        op.add_column("quality_runs", sa.Column("lease_token", sa.String(length=64), nullable=True))
    if "lease_expires_at" not in quality_run_columns:
        op.add_column("quality_runs", sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
    if "quality_run_id" not in generation_columns:
        op.add_column("generation_tasks", sa.Column("quality_run_id", sa.Integer(), nullable=True))
        op.create_foreign_key("fk_generation_tasks_quality_run", "generation_tasks", "quality_runs", ["quality_run_id"], ["id"])
        op.create_index("ix_generation_tasks_quality_run_id", "generation_tasks", ["quality_run_id"])
    if "quality_run_id" not in review_columns:
        op.add_column("image_reviews", sa.Column("quality_run_id", sa.Integer(), nullable=True))
        op.create_foreign_key("fk_image_reviews_quality_run", "image_reviews", "quality_runs", ["quality_run_id"], ["id"])
        op.create_index("ix_image_reviews_quality_run_id", "image_reviews", ["quality_run_id"])
    QualityRound.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "quality_rounds" in inspector.get_table_names():
        QualityRound.__table__.drop(bind=bind)
    if "image_reviews" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("image_reviews")}
        if "quality_run_id" in columns:
            op.drop_constraint("fk_image_reviews_quality_run", "image_reviews", type_="foreignkey")
            op.drop_column("image_reviews", "quality_run_id")
        for name in ("summary", "prompt_revision", "hard_defects_json", "evidence_json"):
            if name in columns:
                op.drop_column("image_reviews", name)
        if "overall_score" in columns:
            op.alter_column(
                "image_reviews",
                "overall_score",
                existing_type=sa.Float(),
                type_=sa.Integer(),
                postgresql_using="round(overall_score)::integer",
            )
    if "generation_tasks" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("generation_tasks")}
        if "quality_run_id" in columns:
            op.drop_constraint("fk_generation_tasks_quality_run", "generation_tasks", type_="foreignkey")
            op.drop_column("generation_tasks", "quality_run_id")
    if "quality_runs" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("quality_runs")}
        if "lease_expires_at" in columns:
            op.drop_column("quality_runs", "lease_expires_at")
        if "lease_token" in columns:
            op.drop_column("quality_runs", "lease_token")
        QualityRun.__table__.drop(bind=bind)
