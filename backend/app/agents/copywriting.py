from __future__ import annotations

import json

from app.agents.llm import generate_payload
from app.models import Project
from app.providers import TextProvider, get_text_provider
from app.schemas import CopywritingPayload, CreativePlanPayload


class CopywritingAgent:
    """Generates platform-ready copy that matches the selected concept."""

    def __init__(self, text_provider: TextProvider | None = None) -> None:
        self.text_provider = text_provider or get_text_provider()

    def run(
        self,
        project: Project,
        plan: CreativePlanPayload,
    ) -> CopywritingPayload:
        model_payload = generate_payload(
            provider=self.text_provider,
            payload_type=CopywritingPayload,
            system_prompt=(
                "You are a Chinese ecommerce copywriter. Write concise, platform-ready copy "
                "that avoids exaggerated or unverifiable claims."
            ),
            user_prompt=json.dumps(
                {
                    "project": {
                    "product_name": project.product_name,
                    "product_category": project.product_category,
                    "core_selling_points": project.core_selling_points,
                    "target_audience": project.target_audience,
                    },
                    "plan": plan.model_dump(),
                    "required_fields": CopywritingPayload.model_json_schema(),
                },
                ensure_ascii=False,
            ),
            schema_name="CopywritingPayload",
            temperature=0.6,
        )
        return model_payload

    def rewrite(
        self,
        project: Project,
        current_copy: CopywritingPayload,
        instruction: str,
    ) -> CopywritingPayload:
        return generate_payload(
            provider=self.text_provider,
            payload_type=CopywritingPayload,
            system_prompt=(
                "You are a Chinese ecommerce copywriter. Revise the supplied copy according to the user's request. "
                "Keep any content not affected by the request and avoid exaggerated or unverifiable claims."
            ),
            user_prompt=json.dumps(
                {
                    "project": {
                        "product_name": project.product_name,
                        "product_category": project.product_category,
                    },
                    "current_copy": current_copy.model_dump(),
                    "revision_instruction": instruction.strip(),
                    "required_fields": CopywritingPayload.model_json_schema(),
                },
                ensure_ascii=False,
            ),
            schema_name="CopywritingPayload",
            temperature=0.45,
        )
