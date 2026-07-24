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

    def run(self, project: Project, analysis: ProductAnalysisPayload) -> list[CreativePlanPayload]:
        model_payload = generate_payload(
            provider=self.text_provider,
            payload_type=CreativePlanListPayload,
            system_prompt=(
                "You are a commercial visual planner. Create exactly three selectable product marketing directions: "
                "one ecommerce hero image, one social lifestyle cover, and one promotional poster. "
                "Do not generate image prompts yet."
            ),
            user_prompt=json.dumps(
                {
                    "project": {
                        "product_name": project.product_name,
                        "product_category": project.product_category,
                        "target_platform": project.target_platform,
                        "target_audience": project.target_audience,
                        "preferred_style": project.preferred_style,
                    },
                    "analysis": analysis.model_dump(),
                    "required_fields": CreativePlanListPayload.model_json_schema(),
                },
                ensure_ascii=False,
            ),
            schema_name="CreativePlanListPayload",
        )
        if len(model_payload.plans) != 3:
            raise ProviderRequestError("Configured LLM must return exactly three creative plans.")
        return model_payload.plans
