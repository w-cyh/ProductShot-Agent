from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator


def _utc_iso(value: datetime) -> str:
    """Return API timestamps as unambiguous UTC ISO 8601 strings.

    SQLite returns naive datetimes even when they originated in UTC. Treat those
    values as UTC at the response boundary so browsers do not interpret them as
    local time.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


UtcDateTime = Annotated[datetime, PlainSerializer(_utc_iso, return_type=str, when_used="json")]


class ProjectCreate(BaseModel):
    product_name: str = Field(min_length=1, max_length=160)
    product_category: Optional[str] = None
    core_selling_points: Optional[str] = None
    target_audience: Optional[str] = None


class ProjectUpdate(BaseModel):
    product_name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    product_category: Optional[str] = None
    core_selling_points: Optional[str] = None
    target_audience: Optional[str] = None


class ProjectRead(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    source_confirmed_at: Optional[UtcDateTime] = None
    strategy_confirmed_at: Optional[UtcDateTime] = None
    created_at: UtcDateTime
    updated_at: UtcDateTime


class ProductAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    file_url: str
    file_path: str
    file_type: str
    is_primary: bool
    width: Optional[int]
    height: Optional[int]
    created_at: UtcDateTime


class VisualAnalysisPayload(BaseModel):
    product_appearance: str
    dominant_colors: list[str]
    materials: list[str]
    visible_text_or_logo: list[str]
    subject_clarity: str
    background_issues: list[str]
    fidelity_constraints: list[str]
    marketing_opportunities: list[str]
    human_reviewed: bool = False
    human_review_notes: str = ""


class VisualAnalysisCorrectionRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=2000)


class ProductStrategyPayload(BaseModel):
    product_type: str
    core_features: list[str]
    target_audience_analysis: str
    recommended_selling_points: list[str]
    recommended_visual_styles: list[str]
    image_issues: list[str]
    marketing_angles: list[str]
    visual_summary: Optional[str] = None
    product_consistency_rules: list[str] = Field(default_factory=list)
    platform_strategy: Optional[str] = None


ProductAnalysisPayload = ProductStrategyPayload


class ProductVisualAnalysisRead(BaseModel):
    id: int
    project_id: int
    analysis: VisualAnalysisPayload
    created_at: UtcDateTime


class ProductAnalysisRead(BaseModel):
    id: int
    project_id: int
    analysis: ProductStrategyPayload
    created_at: UtcDateTime


class StrategyCorrectionRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=2000)


class CreativePlanPayload(BaseModel):
    plan_name: str
    applicable_platform: str
    visual_description: str
    background_scene: str
    visual_style: str
    main_selling_point: str
    recommendation_reason: str
    copywriting_direction: str
    expected_outputs: list[str] = Field(default_factory=list)


class CreativePlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    plan_batch_id: Optional[int] = None
    parent_plan_id: Optional[int] = None
    version: int = 1
    display_order: int = 0
    plan_name: str
    plan_description: str
    target_platform: str
    visual_style: str
    selling_angle: str
    is_current: bool
    plan: CreativePlanPayload
    created_at: UtcDateTime


class CreativePlanBatchCreate(BaseModel):
    feedback: str = Field(default="", max_length=2000)
    platforms: list[str] = Field(default_factory=list, max_length=4)
    style_presets: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("platforms")
    @classmethod
    def validate_platforms(cls, values: list[str]) -> list[str]:
        supported = {"小红书", "朋友圈", "淘宝", "闲鱼"}
        if len(values) != len(set(values)) or any(value not in supported for value in values):
            raise ValueError("平台仅支持小红书、朋友圈、淘宝、闲鱼，且不能重复。")
        return values

    @field_validator("style_presets")
    @classmethod
    def validate_style_presets(cls, values: list[str]) -> list[str]:
        supported = {"高级极简", "生活方式", "质感特写", "节日促销"}
        if len(values) != len(set(values)) or any(value not in supported for value in values):
            raise ValueError("风格仅支持高级极简、生活方式、质感特写、节日促销，且不能重复。")
        return values


class CreativePlanRevisionRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=2000)


class CreativePlanBatchRead(BaseModel):
    id: int
    project_id: int
    kind: str
    feedback: str
    platforms: list[str] = Field(default_factory=list)
    style_presets: list[str] = Field(default_factory=list)
    source_plan_id: Optional[int] = None
    created_at: UtcDateTime
    plans: list[CreativePlanRead] = Field(default_factory=list)


class PromptPayload(BaseModel):
    positive_prompt: str
    negative_prompt: str
    size: str
    style: str
    product_consistency_notes: str


class PromptPackPayload(PromptPayload):
    platform: str
    generation_mode: str
    reference_strength: float = Field(default=0.72, ge=0, le=1)
    consistency_rules: list[str] = Field(default_factory=list)


class PromptPackCreate(BaseModel):
    instruction: str = Field(default="", max_length=2000)


class PromptPackRead(BaseModel):
    id: int
    project_id: int
    plan_id: int
    parent_image_id: Optional[int] = None
    source_instruction: str
    prompt: PromptPackPayload
    created_at: UtcDateTime


class GenerateImagesRequest(BaseModel):
    count: int = Field(default=2, ge=1, le=8)


class GenerationTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    plan_id: Optional[int]
    prompt_pack_id: Optional[int] = None
    parent_image_id: Optional[int] = None
    quality_run_id: Optional[int] = None
    iteration: int = 1
    requested_count: int = 1
    generated_count: int = 0
    reviewed_count: int = 0
    progress_stage: str = "queued"
    prompt: str
    negative_prompt: str
    model_name: str
    status: str
    error_message: Optional[str]
    started_at: Optional[UtcDateTime] = None
    completed_at: Optional[UtcDateTime] = None
    created_at: UtcDateTime
    updated_at: UtcDateTime


class GenerationTaskDetailRead(BaseModel):
    task: GenerationTaskRead
    prompt_pack: Optional[PromptPackRead] = None
    images: list["GeneratedImageRead"] = Field(default_factory=list)


class ImageReviewEvidence(BaseModel):
    # style_match and platform_fit remain readable for existing stored reviews.
    dimension: Literal[
        "product_consistency",
        "product_clarity",
        "commercial_value",
        "text_accuracy",
        "style_match",
        "platform_fit",
    ]
    observation: str = Field(min_length=1, max_length=500)
    severity: Literal["info", "warning", "blocking"] = "info"


class ImageReviewPayload(BaseModel):
    # The application calculates the weighted total. The model scores each
    # concrete review dimension on the human-readable 1–10 scale.
    overall_score: float = Field(default=0, ge=0, le=100)
    product_clarity: int = Field(ge=1, le=10)
    product_consistency: int = Field(ge=1, le=10)
    commercial_value: int = Field(ge=1, le=10)
    text_accuracy: int = Field(ge=1, le=10)
    text_artifact_risk: str = "unknown"
    ai_artifact_risk: str = "low"
    recommendation_level: str = "usable"
    defects: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    evidence: list[ImageReviewEvidence] = Field(default_factory=list)
    hard_defects: list[str] = Field(default_factory=list)
    prompt_revision: str = ""
    summary: str = ""


class ImageReviewRead(BaseModel):
    id: int
    image_id: int
    review: ImageReviewPayload
    created_at: UtcDateTime


class GeneratedImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    project_id: int
    plan_id: Optional[int] = None
    platform: Optional[str] = None
    generation_mode: Optional[str] = None
    prompt_pack_id: Optional[str] = None
    image_url: str
    image_path: str
    width: Optional[int]
    height: Optional[int]
    score: Optional[float]
    is_selected: bool
    is_recommended: bool = False
    review: Optional[ImageReviewRead] = None
    created_at: UtcDateTime


class GeneratedImagesResponse(BaseModel):
    task: GenerationTaskRead
    prompt: PromptPackPayload
    images: list[GeneratedImageRead]


QUALITY_PROFILE_WEIGHTS: dict[str, dict[str, float]] = {
    "fidelity": {
        "product_consistency": 0.40,
        "product_clarity": 0.25,
        "commercial_value": 0.15,
        "text_accuracy": 0.20,
    },
    "balanced": {
        "product_consistency": 0.30,
        "product_clarity": 0.25,
        "commercial_value": 0.25,
        "text_accuracy": 0.20,
    },
    "commercial": {
        "product_consistency": 0.20,
        "product_clarity": 0.20,
        "commercial_value": 0.40,
        "text_accuracy": 0.20,
    },
}

QUALITY_PROFILE_PRIMARY_DIMENSION = {
    "fidelity": "product_consistency",
    "balanced": "product_consistency",
    "commercial": "commercial_value",
}

QUALITY_ACCEPTANCE_TIERS = {
    "loose": {"target_score": 75, "minimum_dimension": 60, "primary_minimum": 70},
    "standard": {"target_score": 85, "minimum_dimension": 65, "primary_minimum": 75},
    "strict": {"target_score": 92, "minimum_dimension": 75, "primary_minimum": 85},
}


class QualityRunCreate(BaseModel):
    plan_id: int
    quality_profile: Literal["fidelity", "balanced", "commercial"] = "balanced"
    acceptance_tier: Literal["loose", "standard", "strict"] = "standard"
    # Kept as an input-only compatibility escape hatch for existing clients.
    target_score: Optional[int] = Field(default=None, ge=70, le=95)
    images_per_round: int = Field(default=2, ge=1, le=4)
    max_rounds: int = Field(default=3, ge=1, le=5)

    @property
    def total_image_budget(self) -> int:
        return self.images_per_round * self.max_rounds

    @property
    def resolved_target_score(self) -> int:
        return self.target_score if self.target_score is not None else QUALITY_ACCEPTANCE_TIERS[self.acceptance_tier]["target_score"]

    @field_validator("max_rounds")
    @classmethod
    def validate_rounds(cls, value: int, info):
        images_per_round = info.data.get("images_per_round", 2)
        if value * images_per_round > 20:
            raise ValueError("单次 AI 审核最多生成 20 张图片。")
        return value


class QualityRunDecisionRequest(BaseModel):
    action: Literal["accept_recommended", "continue"]


class QualityScoreBreakdown(BaseModel):
    overall_score: float
    product_consistency: int
    product_clarity: int
    commercial_value: int
    text_accuracy: int
    target_score: int
    is_accepted: bool
    is_borderline: bool
    has_hard_defect: bool


class QualityRoundRead(BaseModel):
    id: int
    quality_run_id: int
    round_number: int
    prompt_pack_id: Optional[int] = None
    generation_task_id: Optional[int] = None
    best_image_id: Optional[int] = None
    best_score: Optional[float] = None
    status: str
    outcome: str
    review_summary: dict = Field(default_factory=dict)
    created_at: UtcDateTime
    updated_at: UtcDateTime
    images: list[GeneratedImageRead] = Field(default_factory=list)


class QualityRunRead(BaseModel):
    id: int
    project_id: int
    plan_id: int
    quality_profile: Literal["fidelity", "balanced", "commercial"]
    acceptance_tier: Literal["loose", "standard", "strict"]
    target_score: int
    images_per_round: int
    max_rounds: int
    total_image_budget: int
    status: str
    current_round: int
    stop_requested: bool
    recommended_image_id: Optional[int] = None
    error_message: Optional[str] = None
    started_at: Optional[UtcDateTime] = None
    completed_at: Optional[UtcDateTime] = None
    created_at: UtcDateTime
    updated_at: UtcDateTime


class QualityRunDetailRead(QualityRunRead):
    profile_weights: dict[str, float]
    primary_dimension: str
    remaining_rounds: int
    max_review_calls: int
    max_prompt_revisions: int
    rounds: list[QualityRoundRead] = Field(default_factory=list)


class CopywritingRequest(BaseModel):
    image_id: Optional[int] = None


class CopywritingPayload(BaseModel):
    title: str
    selling_points: list[str]
    xiaohongshu_title: str
    xiaohongshu_text: str
    moments_text: str
    taobao_text: str
    xianyu_text: str = ""
    tags: list[str]


class CopywritingRead(BaseModel):
    id: int
    project_id: int
    image_id: Optional[int]
    copywriting: CopywritingPayload
    created_at: UtcDateTime


class CopywritingUpdate(BaseModel):
    copywriting: CopywritingPayload


class CopywritingRewriteRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=2000)


class SelectImageRequest(BaseModel):
    selected: bool = True


class ProviderModelSettingsRead(BaseModel):
    text_model: str
    vision_model: str
    image_model: str
    base_url: str
    api_key_configured: bool


class ProviderModelSettingsUpdate(BaseModel):
    text_model: Optional[str] = Field(default=None, max_length=120)
    vision_model: Optional[str] = Field(default=None, max_length=120)
    image_model: Optional[str] = Field(default=None, max_length=120)
    base_url: Optional[str] = Field(default=None, max_length=300)


class ModelNameHistoryRead(BaseModel):
    id: int
    provider: Literal["openai", "dashscope"]
    model_kind: Literal["text_model", "vision_model", "image_model"]
    model_name: str


class ModelSettingsRead(BaseModel):
    text_provider: str
    image_provider: str
    providers: dict[str, ProviderModelSettingsRead]
    dashscope_workspace_id_configured: bool
    available_text_providers: list[str]
    available_image_providers: list[str]
    model_name_history: dict[str, dict[str, list[ModelNameHistoryRead]]] = Field(default_factory=dict)


class ModelSettingsUpdate(BaseModel):
    text_provider: Optional[str] = Field(default=None, max_length=40)
    image_provider: Optional[str] = Field(default=None, max_length=40)
    providers: dict[str, ProviderModelSettingsUpdate] = Field(default_factory=dict)


class ModelConnectionTestRead(BaseModel):
    provider: str
    model: str
    status: str
    latency_ms: int
    message: str
    checked_at: UtcDateTime


class WorkflowEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    step_key: str
    agent_name: str
    status: str
    summary: str
    detail_json: str
    error_message: Optional[str]
    started_at: UtcDateTime
    ended_at: Optional[UtcDateTime]
    latency_ms: Optional[int]


class ProjectDetail(ProjectRead):
    assets: list[ProductAssetRead]
    visual_analysis: Optional[ProductVisualAnalysisRead] = None
    product_strategy: Optional[ProductAnalysisRead] = None
    latest_analysis: Optional[ProductAnalysisRead]
    creative_plans: list[CreativePlanRead]
    creative_plan_batches: list[CreativePlanBatchRead] = Field(default_factory=list)
    prompt_packs: list[PromptPackRead] = Field(default_factory=list)
    generation_tasks: list[GenerationTaskRead] = Field(default_factory=list)
    quality_runs: list[QualityRunRead] = Field(default_factory=list)
    generated_images: list[GeneratedImageRead]
    latest_copywriting: Optional[CopywritingRead]
    copywriting: list[CopywritingRead] = Field(default_factory=list)
    workflow_events: list[WorkflowEventRead]


class GenerationTaskCenterItem(GenerationTaskRead):
    project_name: str
    plan_name: Optional[str] = None
    parent_image_label: Optional[str] = None


class GenerationTaskPage(BaseModel):
    items: list[GenerationTaskCenterItem]
    total: int
    page: int
    page_size: int
