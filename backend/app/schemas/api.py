from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    product_name: str = Field(min_length=1, max_length=160)
    product_category: Optional[str] = None
    core_selling_points: Optional[str] = None
    target_platform: str = Field(min_length=1, max_length=80)
    target_audience: Optional[str] = None
    preferred_style: Optional[str] = None


class ProjectRead(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    created_at: datetime
    updated_at: datetime


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
    created_at: datetime


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


class VisualAnalysisReviewRequest(BaseModel):
    analysis: VisualAnalysisPayload
    review_notes: str = Field(default="", max_length=2000)


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
    created_at: datetime


class ProductAnalysisRead(BaseModel):
    id: int
    project_id: int
    analysis: ProductStrategyPayload
    created_at: datetime


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
    plan_name: str
    plan_description: str
    target_platform: str
    visual_style: str
    selling_angle: str
    plan: CreativePlanPayload
    created_at: datetime


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


class GenerateImagesRequest(BaseModel):
    count: int = Field(default=4, ge=1, le=6)


class GenerationTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    plan_id: Optional[int]
    prompt: str
    negative_prompt: str
    model_name: str
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime


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
    created_at: datetime


class GeneratedImagesResponse(BaseModel):
    task: GenerationTaskRead
    prompt: PromptPackPayload
    images: list[GeneratedImageRead]


class ImageReviewPayload(BaseModel):
    overall_score: int
    product_clarity: int
    product_consistency: int = 80
    style_match: int
    commercial_value: int
    platform_fit: int
    text_artifact_risk: str = "low"
    ai_artifact_risk: str = "low"
    recommendation_level: str = "usable"
    defects: list[str]
    suggestions: list[str]


class ImageReviewRead(BaseModel):
    id: int
    image_id: int
    review: ImageReviewPayload
    created_at: datetime


class CopywritingRequest(BaseModel):
    image_id: Optional[int] = None


class CopywritingPayload(BaseModel):
    title: str
    selling_points: list[str]
    xiaohongshu_title: str
    xiaohongshu_text: str
    moments_text: str
    taobao_text: str
    douyin_script: str = ""
    tags: list[str]


class CopywritingRead(BaseModel):
    id: int
    project_id: int
    image_id: Optional[int]
    copywriting: CopywritingPayload
    created_at: datetime


class RevisionRequest(BaseModel):
    target_image_id: Optional[int] = None
    instruction: str = Field(min_length=1)


class ProviderModelSettingsRead(BaseModel):
    text_model: str
    image_model: str
    base_url: str
    api_key_configured: bool


class ProviderModelSettingsUpdate(BaseModel):
    text_model: Optional[str] = Field(default=None, max_length=120)
    image_model: Optional[str] = Field(default=None, max_length=120)
    base_url: Optional[str] = Field(default=None, max_length=300)


class ModelSettingsRead(BaseModel):
    text_provider: str
    image_provider: str
    providers: dict[str, ProviderModelSettingsRead]
    dashscope_workspace_id_configured: bool
    available_text_providers: list[str]
    available_image_providers: list[str]


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
    checked_at: datetime


class RevisionResponse(BaseModel):
    revision_type: str
    target: str
    modification_plan: list[str]
    new_prompt: PromptPackPayload
    should_regenerate: bool
    notes: str


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
    started_at: datetime
    ended_at: Optional[datetime]
    latency_ms: Optional[int]


class ProjectDetail(ProjectRead):
    assets: list[ProductAssetRead]
    visual_analysis: Optional[ProductVisualAnalysisRead] = None
    product_strategy: Optional[ProductAnalysisRead] = None
    latest_analysis: Optional[ProductAnalysisRead]
    creative_plans: list[CreativePlanRead]
    generated_images: list[GeneratedImageRead]
    latest_copywriting: Optional[CopywritingRead]
    workflow_events: list[WorkflowEventRead]


class ExportReport(BaseModel):
    project: ProjectRead
    assets: list[ProductAssetRead]
    analysis: Optional[ProductAnalysisPayload]
    creative_plans: list[CreativePlanRead]
    generation_tasks: list[GenerationTaskRead]
    generated_images: list[GeneratedImageRead]
    image_reviews: list[ImageReviewRead]
    copywriting: list[CopywritingRead]
    revision: Optional[RevisionResponse] = None
    metadata: dict[str, Any]
