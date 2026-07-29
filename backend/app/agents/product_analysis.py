from __future__ import annotations

import json

from app.agents.llm import generate_payload
from app.models import Project
from app.providers import TextProvider, get_text_provider
from app.schemas import ProductAnalysisPayload, VisualAnalysisPayload


class ProductAnalysisAgent:
    """Analyzes product metadata and image context for the marketing workflow."""

    def __init__(self, text_provider: TextProvider | None = None) -> None:
        self.text_provider = text_provider or get_text_provider()

    def run(self, project: Project, image_path: str | None = None, visual: VisualAnalysisPayload | None = None) -> ProductAnalysisPayload:
        model_payload = generate_payload(
            provider=self.text_provider,
            payload_type=ProductAnalysisPayload,
            system_prompt=(
                "You are a product marketing strategist for small merchants. "
                "Analyze product metadata and produce concise, practical marketing context in Chinese."
            ),
            user_prompt=json.dumps(
                {
                    "product_name": project.product_name,
                    "product_category": project.product_category,
                    "core_selling_points": project.core_selling_points,
                    "target_audience": project.target_audience,
                    "has_source_image": bool(image_path),
                    "visual_analysis": visual.model_dump() if visual else None,
                    "required_fields": ProductAnalysisPayload.model_json_schema(),
                },
                ensure_ascii=False,
            ),
            schema_name="ProductAnalysisPayload",
        )
        return model_payload
