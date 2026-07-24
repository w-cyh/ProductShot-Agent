from __future__ import annotations

import json

from app.agents.llm import generate_payload
from app.models import Project
from app.providers import TextProvider, get_text_provider
from app.providers.text_provider import ProviderRequestError
from app.schemas import VisualAnalysisPayload


class VisualAnalysisAgent:
    """Extracts product fidelity and marketing cues from the uploaded source image."""

    def __init__(self, text_provider: TextProvider | None = None) -> None:
        self.text_provider = text_provider or get_text_provider()

    def run(self, project: Project, image_path: str | None = None) -> VisualAnalysisPayload:
        if image_path:
            data = self.text_provider.generate_multimodal_json(
                system_prompt=(
                    "You are a commercial product-photo analyst. Inspect the source product image and "
                    "return structured Chinese JSON for downstream image generation and marketing planning."
                ),
                user_prompt=json.dumps(
                    {
                        "product_name": project.product_name,
                        "product_category": project.product_category,
                        "target_platform": project.target_platform,
                        "required_fields": VisualAnalysisPayload.model_json_schema(),
                    },
                    ensure_ascii=False,
                ),
                image_path=image_path,
                schema_name="VisualAnalysisPayload",
                schema=VisualAnalysisPayload.model_json_schema(),
                temperature=0.2,
            )
            try:
                return VisualAnalysisPayload.model_validate(data)
            except ValueError as exc:
                raise ProviderRequestError("Configured LLM returned an invalid VisualAnalysisPayload.") from exc

        return generate_payload(
            provider=self.text_provider,
            payload_type=VisualAnalysisPayload,
            system_prompt="You are a commercial product-photo analyst. Return structured Chinese JSON for product planning.",
            user_prompt=json.dumps(
                {
                    "product_name": project.product_name,
                    "product_category": project.product_category,
                    "target_platform": project.target_platform,
                    "required_fields": VisualAnalysisPayload.model_json_schema(),
                },
                ensure_ascii=False,
            ),
            schema_name="VisualAnalysisPayload",
            temperature=0.2,
        )
