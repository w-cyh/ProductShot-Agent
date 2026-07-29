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

    def correct(
        self,
        project: Project,
        current: ProductAnalysisPayload,
        instruction: str,
        visual: VisualAnalysisPayload | None = None,
    ) -> ProductAnalysisPayload:
        return generate_payload(
            provider=self.text_provider,
            payload_type=ProductAnalysisPayload,
            system_prompt=(
                "You are a product marketing strategist for small merchants. Revise the current Chinese product "
                "strategy according to the user's instruction. Keep unaffected conclusions coherent with the "
                "confirmed product facts and do not invent unsupported product claims."
            ),
            user_prompt=json.dumps(
                {
                    "project": {
                        "product_name": project.product_name,
                        "product_category": project.product_category,
                        "core_selling_points": project.core_selling_points,
                        "target_audience": project.target_audience,
                    },
                    "visual_analysis": visual.model_dump() if visual else None,
                    "current_strategy": current.model_dump(),
                    "revision_instruction": instruction.strip(),
                    "required_fields": ProductAnalysisPayload.model_json_schema(),
                },
                ensure_ascii=False,
            ),
            schema_name="ProductAnalysisPayload",
        )
