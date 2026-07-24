from __future__ import annotations

import json

from app.agents.llm import generate_payload
from app.models import Project
from app.providers import TextProvider, get_text_provider
from app.schemas import CreativePlanPayload, ProductAnalysisPayload, PromptPackPayload


class PromptEngineerAgent:
    """Turns a selected creative plan into model-ready image prompts."""

    def __init__(self, text_provider: TextProvider | None = None) -> None:
        self.text_provider = text_provider or get_text_provider()

    def run(
        self,
        project: Project,
        plan: CreativePlanPayload,
        analysis: ProductAnalysisPayload | None = None,
    ) -> PromptPackPayload:
        size = self._size_for_platform(plan.applicable_platform or project.target_platform)
        model_payload = generate_payload(
            provider=self.text_provider,
            payload_type=PromptPackPayload,
            system_prompt=(
                "You are a prompt engineer for commercial product photography. "
                "Write model-ready image prompts in English, with Chinese consistency notes."
            ),
            user_prompt=json.dumps(
                {
                    "project": {
                        "product_name": project.product_name,
                        "product_category": project.product_category,
                        "target_platform": project.target_platform,
                        "core_selling_points": project.core_selling_points,
                    },
                    "plan": plan.model_dump(),
                    "product_consistency_rules": analysis.product_consistency_rules if analysis else [],
                    "size": size,
                    "required_fields": PromptPackPayload.model_json_schema(),
                },
                ensure_ascii=False,
            ),
            schema_name="PromptPackPayload",
            temperature=0.35,
        )
        return model_payload

    def _size_for_platform(self, platform: str) -> str:
        if "小红书" in platform:
            return "1024x1365"
        if "抖音" in platform:
            return "1080x1920"
        if "淘宝" in platform or "朋友圈" in platform:
            return "1024x1024"
        return "1024x1024"
