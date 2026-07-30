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
        source_instruction: str = "",
        parent_prompt: PromptPackPayload | None = None,
    ) -> PromptPackPayload:
        size = self._size_for_platform(plan.applicable_platform)
        model_payload = generate_payload(
            provider=self.text_provider,
            payload_type=PromptPackPayload,
            system_prompt=(
                "You are a prompt engineer for commercial product photography. "
                "Write model-ready image prompts in English, with Chinese consistency notes. "
                "Do not instruct the image model to render new promotional copy, slogans, price badges, or decorative "
                "typography. Reserve a clean, intentionally blank upper-right area for copy added in post-production; "
                "the negative prompt must prohibit accidental/generated promotional text. Preserve the source product's "
                "real labels and logo as fidelity constraints, rather than inventing new wording. "
                "When a parent Prompt Pack and revision instruction are supplied, preserve the selected image's "
                "useful composition while applying only the requested modification."
            ),
            user_prompt=json.dumps(
                {
                    "project": {
                        "product_name": project.product_name,
                        "product_category": project.product_category,
                        "core_selling_points": project.core_selling_points,
                    },
                    "plan": plan.model_dump(),
                    "product_consistency_rules": analysis.product_consistency_rules if analysis else [],
                    "parent_prompt_pack": parent_prompt.model_dump() if parent_prompt else None,
                    "revision_instruction": source_instruction.strip() or None,
                    "size": size,
                    "required_fields": PromptPackPayload.model_json_schema(),
                },
                ensure_ascii=False,
            ),
            schema_name="PromptPackPayload",
            temperature=0.35,
        )
        return model_payload.model_copy(
            update={
                "positive_prompt": self._append_constraint(
                    model_payload.positive_prompt,
                    "reserve a clean blank upper-right area for post-production copy; do not render new promotional text, slogans, or price badges",
                ),
                "negative_prompt": self._append_constraint(
                    model_payload.negative_prompt,
                    "generated promotional text, slogans, price badges, gibberish characters, accidental typography, watermark",
                ),
            }
        )

    def _size_for_platform(self, platform: str) -> str:
        if "小红书" in platform:
            return "1024x1365"
        if "淘宝" in platform or "朋友圈" in platform or "闲鱼" in platform:
            return "1024x1024"
        return "1024x1024"

    def _append_constraint(self, prompt: str, constraint: str) -> str:
        normalized = prompt.strip()
        if constraint.lower() in normalized.lower():
            return normalized
        return f"{normalized}, {constraint}" if normalized else constraint
