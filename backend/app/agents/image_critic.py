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
                    "You are a strict ecommerce image reviewer. The first image is the confirmed source product "
                    "and the second image is a generated marketing candidate. Compare them against the product "
                    "constraints. Return exactly four integer scores from 1 to 10: product_consistency (fidelity to "
                    "the source), product_clarity, commercial_value, and text_accuracy. Text accuracy means source "
                    "labels and logos are not corrupted and the image contains no accidental or garbled promotional "
                    "text; the intended upper-right copy area should remain clean and blank. Report problems in defects, "
                    "only clear release-blocking defects in hard_defects, give concrete evidence, and provide a minimal "
                    "prompt_revision for a retry. "
                    "Do not decide the final overall score; the application calculates it."
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
                image_paths=[source_image_path, image.image_path],
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
                "You are a strict ecommerce creative reviewer. Return four integer scores from 1 to 10 for product "
                "consistency, product clarity, commercial value, and text accuracy. Text accuracy requires correct "
                "source labels/logos and no garbled or accidental promotional text; the upper-right copy area should "
                "remain clean and blank. List concrete problems and retry advice in Chinese JSON."
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
