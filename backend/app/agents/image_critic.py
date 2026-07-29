from __future__ import annotations

import json

from app.agents.llm import generate_payload
from app.models import GeneratedImage, Project
from app.providers import TextProvider, get_text_provider
from app.providers.text_provider import ProviderRequestError
from app.schemas import CreativePlanPayload, ImageReviewPayload, VisualAnalysisPayload


class ImageCriticAgent:
    """Scores generated images for marketing usefulness, not just aesthetics."""

    def __init__(self, text_provider: TextProvider | None = None) -> None:
        self.text_provider = text_provider or get_text_provider()

    def run(
        self,
        project: Project,
        image: GeneratedImage,
        plan: CreativePlanPayload,
        visual: VisualAnalysisPayload | None = None,
        source_image_path: str | None = None,
    ) -> ImageReviewPayload:
        if source_image_path:
            data = self.text_provider.generate_multimodal_json(
                system_prompt=(
                    "You are a strict ecommerce image reviewer. Compare the generated image against "
                    "the original product constraints and score marketing usefulness in Chinese JSON."
                ),
                user_prompt=json.dumps(
                    {
                        "project": {
                            "product_name": project.product_name,
                            "target_platform": plan.applicable_platform,
                            "target_audience": project.target_audience,
                        },
                        "generated_image": {
                            "image_url": image.image_url,
                            "width": image.width,
                            "height": image.height,
                        },
                        "visual_analysis": visual.model_dump() if visual else None,
                        "plan": plan.model_dump(),
                        "required_fields": ImageReviewPayload.model_json_schema(),
                    },
                    ensure_ascii=False,
                ),
                image_path=image.image_path,
                schema_name="ImageReviewPayload",
                schema=ImageReviewPayload.model_json_schema(),
                temperature=0.2,
            )
            try:
                return ImageReviewPayload.model_validate(data)
            except ValueError as exc:
                raise ProviderRequestError("Configured LLM returned an invalid ImageReviewPayload.") from exc

        model_payload = generate_payload(
            provider=self.text_provider,
            payload_type=ImageReviewPayload,
            system_prompt=(
                "You are a strict ecommerce creative reviewer. Score the generated asset for product clarity, "
                "style match, commercial value, and platform fit. Use integers from 0 to 100."
            ),
            user_prompt=json.dumps(
                {
                    "project": {
                        "product_name": project.product_name,
                        "target_platform": plan.applicable_platform,
                        "target_audience": project.target_audience,
                    },
                    "image": {
                        "image_url": image.image_url,
                        "width": image.width,
                        "height": image.height,
                    },
                    "plan": plan.model_dump(),
                    "visual_analysis": visual.model_dump() if visual else None,
                    "required_fields": ImageReviewPayload.model_json_schema(),
                },
                ensure_ascii=False,
            ),
            schema_name="ImageReviewPayload",
            temperature=0.2,
        )
        return model_payload
