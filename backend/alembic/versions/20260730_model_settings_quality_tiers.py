"""Persist model settings and add tiered quality review fields.

Revision ID: 20260730_model_cfg_tiers
Revises: 20260730_quality_runs
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

from app import models  # noqa: F401 - register models before metadata bootstrap
from app.database import Base
from app.models.entities import ImageReview, QualityRun
from app.models.model_settings import ModelNameHistory, ModelRuntimeSettings, ProviderModelConfig


revision = "20260730_model_cfg_tiers"
down_revision = "20260730_quality_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        Base.metadata.create_all(bind=bind)
        return

    inspector = inspect(bind)
    if "projects" not in inspector.get_table_names():
        Base.metadata.create_all(bind=bind)
        return

    ModelRuntimeSettings.__table__.create(bind=bind, checkfirst=True)
    ProviderModelConfig.__table__.create(bind=bind, checkfirst=True)
    ModelNameHistory.__table__.create(bind=bind, checkfirst=True)

    if "image_reviews" in inspector.get_table_names():
        review_columns = {column["name"] for column in inspector.get_columns("image_reviews")}
        if "text_accuracy_score" not in review_columns:
            op.add_column(
                "image_reviews",
                sa.Column("text_accuracy_score", sa.Integer(), nullable=False, server_default="80"),
            )

    if "quality_runs" in inspector.get_table_names():
        run_columns = {column["name"] for column in inspector.get_columns("quality_runs")}
        if "acceptance_tier" not in run_columns:
            op.add_column(
                "quality_runs",
                sa.Column("acceptance_tier", sa.String(length=40), nullable=False, server_default="standard"),
            )
            op.execute(
                "UPDATE quality_runs SET acceptance_tier = CASE "
                "WHEN target_score >= 90 THEN 'strict' "
                "WHEN target_score < 80 THEN 'loose' "
                "ELSE 'standard' END"
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "quality_runs" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("quality_runs")}
        if "acceptance_tier" in columns:
            op.drop_column("quality_runs", "acceptance_tier")
    if "image_reviews" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("image_reviews")}
        if "text_accuracy_score" in columns:
            op.drop_column("image_reviews", "text_accuracy_score")
    if "model_name_history" in inspector.get_table_names():
        ModelNameHistory.__table__.drop(bind=bind)
    if "provider_model_configs" in inspector.get_table_names():
        ProviderModelConfig.__table__.drop(bind=bind)
    if "model_runtime_settings" in inspector.get_table_names():
        ModelRuntimeSettings.__table__.drop(bind=bind)
