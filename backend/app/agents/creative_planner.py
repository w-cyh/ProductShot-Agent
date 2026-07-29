from __future__ import annotations

import json

from pydantic import BaseModel

from app.agents.llm import generate_payload
from app.models import Project
from app.providers import TextProvider, get_text_provider
from app.providers.text_provider import ProviderRequestError
from app.schemas import CreativePlanPayload, ProductAnalysisPayload


class CreativePlanListPayload(BaseModel):
    plans: list[CreativePlanPayload]


class CreativePlannerAgent:
    """Creates platform-aware marketing concepts from product analysis."""

    def __init__(self, text_provider: TextProvider | None = None) -> None:
        self.text_provider = text_provider or get_text_provider()

    def run(
        self,
        project: Project,
        analysis: ProductAnalysisPayload,
        feedback: str = "",
        platforms: list[str] | None = None,
        style_presets: list[str] | None = None,
    ) -> list[CreativePlanPayload]:
        platforms = platforms or []
        style_presets = style_presets or []
        model_payload = generate_payload(
            provider=self.text_provider,
            payload_type=CreativePlanListPayload,
            system_prompt=(
                "You are a commercial visual planner. Create exactly three selectable product marketing directions: "
                "one ecommerce hero image, one social lifestyle cover, and one promotional poster. "
                "Honor selected platforms and style presets exactly when supplied. When they are omitted, create "
                "three meaningfully different combinations across 小红书、朋友圈、淘宝、闲鱼 and mainstream visual styles. "
                "Incorporate the user's creative feedback when present. Do not generate image prompts yet."
            ),
            user_prompt=json.dumps(
                {
                    "project": {
                        "product_name": project.product_name,
                        "product_category": project.product_category,
                        "target_audience": project.target_audience,
                    },
                    "analysis": analysis.model_dump(),
                    "creative_feedback": feedback.strip() or None,
                    "selected_platforms": platforms or None,
                    "selected_style_presets": style_presets or None,
                    "required_fields": CreativePlanListPayload.model_json_schema(),
                },
                ensure_ascii=False,
            ),
            schema_name="CreativePlanListPayload",
        )
        if len(model_payload.plans) != 3:
            raise ProviderRequestError("Configured LLM must return exactly three creative plans.")
        if platforms and any(plan.applicable_platform not in platforms for plan in model_payload.plans):
            raise ProviderRequestError("Configured LLM returned a plan outside the selected platform range.")
        if style_presets and any(plan.visual_style not in style_presets for plan in model_payload.plans):
            raise ProviderRequestError("Configured LLM returned a plan outside the selected style range.")
        return model_payload.plans

    def revise(
        self,
        project: Project,
        analysis: ProductAnalysisPayload,
        source_plan: CreativePlanPayload,
        feedback: str,
    ) -> CreativePlanPayload:
        return generate_payload(
            provider=self.text_provider,
            payload_type=CreativePlanPayload,
            system_prompt=(
                "You are a commercial visual planner. Revise one selected marketing direction. "
                "Keep the parts the user did not ask to change, make the requested changes concrete, "
                "and do not generate an image prompt."
            ),
            user_prompt=json.dumps(
                {
                    "project": {
                        "product_name": project.product_name,
                        "product_category": project.product_category,
                        "target_audience": project.target_audience,
                    },
                    "analysis": analysis.model_dump(),
                    "source_plan": source_plan.model_dump(),
                    "revision_feedback": feedback.strip(),
                    "required_fields": CreativePlanPayload.model_json_schema(),
                },
                ensure_ascii=False,
            ),
            schema_name="CreativePlanPayload",
        )
