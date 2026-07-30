from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_name: Mapped[str] = mapped_column(String(160), nullable=False)
    product_category: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    core_selling_points: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_platform: Mapped[str] = mapped_column(String(80), nullable=False)
    target_audience: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    preferred_style: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    source_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    strategy_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    assets: Mapped[list["ProductAsset"]] = relationship(cascade="all, delete-orphan", back_populates="project")
    analyses: Mapped[list["ProductAnalysis"]] = relationship(cascade="all, delete-orphan", back_populates="project")
    visual_analyses: Mapped[list["ProductVisualAnalysis"]] = relationship(cascade="all, delete-orphan", back_populates="project")
    creative_plan_batches: Mapped[list["CreativePlanBatch"]] = relationship(cascade="all, delete-orphan", back_populates="project")
    creative_plans: Mapped[list["CreativePlan"]] = relationship(cascade="all, delete-orphan", back_populates="project")
    prompt_packs: Mapped[list["PromptPack"]] = relationship(cascade="all, delete-orphan", back_populates="project")
    generation_tasks: Mapped[list["GenerationTask"]] = relationship(cascade="all, delete-orphan", back_populates="project")
    generated_images: Mapped[list["GeneratedImage"]] = relationship(cascade="all, delete-orphan", back_populates="project")
    copywriting_items: Mapped[list["Copywriting"]] = relationship(cascade="all, delete-orphan", back_populates="project")
    workflow_events: Mapped[list["WorkflowEvent"]] = relationship(cascade="all, delete-orphan", back_populates="project")
    quality_runs: Mapped[list["QualityRun"]] = relationship(cascade="all, delete-orphan", back_populates="project")


class ProductAsset(Base):
    __tablename__ = "product_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(80), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="assets")


class ProductAnalysis(Base):
    __tablename__ = "product_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    analysis_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="analyses")


class ProductVisualAnalysis(Base):
    __tablename__ = "product_visual_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    analysis_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="visual_analyses")


class CreativePlanBatch(Base):
    __tablename__ = "creative_plan_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(40), default="initial", nullable=False)
    feedback: Mapped[str] = mapped_column(Text, default="", nullable=False)
    platforms_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    style_presets_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    source_plan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("creative_plans.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="creative_plan_batches")
    plans: Mapped[list["CreativePlan"]] = relationship(foreign_keys="CreativePlan.plan_batch_id", back_populates="batch")


class CreativePlan(Base):
    __tablename__ = "creative_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    plan_batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("creative_plan_batches.id"), nullable=True, index=True)
    parent_plan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("creative_plans.id"), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    plan_name: Mapped[str] = mapped_column(String(160), nullable=False)
    plan_description: Mapped[str] = mapped_column(Text, nullable=False)
    target_platform: Mapped[str] = mapped_column(String(80), nullable=False)
    visual_style: Mapped[str] = mapped_column(String(160), nullable=False)
    selling_angle: Mapped[str] = mapped_column(String(200), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    plan_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="creative_plans")
    batch: Mapped[Optional[CreativePlanBatch]] = relationship(foreign_keys=[plan_batch_id], back_populates="plans")
    generation_tasks: Mapped[list["GenerationTask"]] = relationship(cascade="all, delete-orphan", back_populates="plan")
    prompt_packs: Mapped[list["PromptPack"]] = relationship(cascade="all, delete-orphan", back_populates="plan")


class PromptPack(Base):
    __tablename__ = "prompt_packs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("creative_plans.id"), nullable=False, index=True)
    parent_image_id: Mapped[Optional[int]] = mapped_column(ForeignKey("generated_images.id"), nullable=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_instruction: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="prompt_packs")
    plan: Mapped[CreativePlan] = relationship(back_populates="prompt_packs")
    parent_image: Mapped[Optional["GeneratedImage"]] = relationship(foreign_keys=[parent_image_id])
    generation_tasks: Mapped[list["GenerationTask"]] = relationship(back_populates="prompt_pack")


class GenerationTask(Base):
    __tablename__ = "generation_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    plan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("creative_plans.id"), nullable=True, index=True)
    prompt_pack_id: Mapped[Optional[int]] = mapped_column(ForeignKey("prompt_packs.id"), nullable=True, index=True)
    parent_image_id: Mapped[Optional[int]] = mapped_column(ForeignKey("generated_images.id"), nullable=True, index=True)
    quality_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("quality_runs.id"), nullable=True, index=True)
    iteration: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    requested_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    generated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reviewed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_stage: Mapped[str] = mapped_column(String(40), default="queued", nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="generation_tasks")
    plan: Mapped[Optional[CreativePlan]] = relationship(back_populates="generation_tasks")
    prompt_pack: Mapped[Optional[PromptPack]] = relationship(back_populates="generation_tasks")
    parent_image: Mapped[Optional["GeneratedImage"]] = relationship(foreign_keys=[parent_image_id])
    images: Mapped[list["GeneratedImage"]] = relationship(
        foreign_keys="GeneratedImage.task_id",
        cascade="all, delete-orphan",
        back_populates="task",
    )
    quality_run: Mapped[Optional["QualityRun"]] = relationship(back_populates="generation_tasks")


class GeneratedImage(Base):
    __tablename__ = "generated_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("generation_tasks.id"), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    plan_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    platform: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    generation_mode: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    prompt_pack_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    prompt_pack_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    task: Mapped[GenerationTask] = relationship(foreign_keys=[task_id], back_populates="images")
    project: Mapped[Project] = relationship(back_populates="generated_images")
    reviews: Mapped[list["ImageReview"]] = relationship(cascade="all, delete-orphan", back_populates="image")
    copywriting_items: Mapped[list["Copywriting"]] = relationship(cascade="all, delete-orphan", back_populates="image")


class ImageReview(Base):
    __tablename__ = "image_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("generated_images.id"), nullable=False, index=True)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    product_clarity_score: Mapped[int] = mapped_column(Integer, nullable=False)
    product_consistency_score: Mapped[int] = mapped_column(Integer, default=80, nullable=False)
    style_match_score: Mapped[int] = mapped_column(Integer, nullable=False)
    commercial_value_score: Mapped[int] = mapped_column(Integer, nullable=False)
    platform_fit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    text_accuracy_score: Mapped[int] = mapped_column(Integer, default=80, nullable=False)
    text_artifact_risk: Mapped[str] = mapped_column(String(40), default="low", nullable=False)
    ai_artifact_risk: Mapped[str] = mapped_column(String(40), default="low", nullable=False)
    recommendation_level: Mapped[str] = mapped_column(String(40), default="usable", nullable=False)
    defects_json: Mapped[str] = mapped_column(Text, nullable=False)
    suggestions_json: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    hard_defects_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    prompt_revision: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    quality_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("quality_runs.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    image: Mapped[GeneratedImage] = relationship(back_populates="reviews")
    quality_run: Mapped[Optional["QualityRun"]] = relationship(back_populates="reviews")


class QualityRun(Base):
    __tablename__ = "quality_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("creative_plans.id"), nullable=False, index=True)
    quality_profile: Mapped[str] = mapped_column(String(40), nullable=False)
    acceptance_tier: Mapped[str] = mapped_column(String(40), default="standard", nullable=False)
    target_score: Mapped[int] = mapped_column(Integer, nullable=False)
    images_per_round: Mapped[int] = mapped_column(Integer, nullable=False)
    max_rounds: Mapped[int] = mapped_column(Integer, nullable=False)
    total_image_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="preparing", nullable=False, index=True)
    current_round: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stop_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pending_revision: Mapped[str] = mapped_column(Text, default="", nullable=False)
    recommended_image_id: Mapped[Optional[int]] = mapped_column(ForeignKey("generated_images.id"), nullable=True, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    lease_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="quality_runs")
    plan: Mapped[CreativePlan] = relationship()
    rounds: Mapped[list["QualityRound"]] = relationship(cascade="all, delete-orphan", back_populates="quality_run")
    generation_tasks: Mapped[list[GenerationTask]] = relationship(back_populates="quality_run")
    reviews: Mapped[list[ImageReview]] = relationship(back_populates="quality_run")
    recommended_image: Mapped[Optional[GeneratedImage]] = relationship(foreign_keys=[recommended_image_id])


class QualityRound(Base):
    __tablename__ = "quality_rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    quality_run_id: Mapped[int] = mapped_column(ForeignKey("quality_runs.id"), nullable=False, index=True)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_pack_id: Mapped[Optional[int]] = mapped_column(ForeignKey("prompt_packs.id"), nullable=True, index=True)
    generation_task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("generation_tasks.id"), nullable=True, index=True)
    best_image_id: Mapped[Optional[int]] = mapped_column(ForeignKey("generated_images.id"), nullable=True, index=True)
    best_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="preparing", nullable=False)
    outcome: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    review_summary_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    quality_run: Mapped[QualityRun] = relationship(back_populates="rounds")
    prompt_pack: Mapped[Optional[PromptPack]] = relationship()
    generation_task: Mapped[Optional[GenerationTask]] = relationship(foreign_keys=[generation_task_id])
    best_image: Mapped[Optional[GeneratedImage]] = relationship(foreign_keys=[best_image_id])


class Copywriting(Base):
    __tablename__ = "copywriting"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    image_id: Mapped[Optional[int]] = mapped_column(ForeignKey("generated_images.id"), nullable=True, index=True)
    parent_copywriting_id: Mapped[Optional[int]] = mapped_column(ForeignKey("copywriting.id"), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    revision_kind: Mapped[str] = mapped_column(String(40), default="generated", nullable=False)
    revision_instruction: Mapped[str] = mapped_column(Text, default="", nullable=False)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    selling_points_json: Mapped[str] = mapped_column(Text, nullable=False)
    xiaohongshu_title: Mapped[str] = mapped_column(String(220), nullable=False)
    xiaohongshu_text: Mapped[str] = mapped_column(Text, nullable=False)
    moments_text: Mapped[str] = mapped_column(Text, nullable=False)
    taobao_text: Mapped[str] = mapped_column(Text, nullable=False)
    douyin_script: Mapped[str] = mapped_column(Text, default="", nullable=False)
    xianyu_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tags_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="copywriting_items")
    image: Mapped[Optional[GeneratedImage]] = relationship(back_populates="copywriting_items")


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    step_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    detail_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    project: Mapped[Project] = relationship(back_populates="workflow_events")
