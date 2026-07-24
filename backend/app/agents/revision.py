from __future__ import annotations

import json

from app.agents.llm import generate_payload
from app.agents.prompt_engineer import PromptEngineerAgent
from app.models import Project
from app.providers import TextProvider, get_text_provider
from app.schemas import CreativePlanPayload, PromptPackPayload, RevisionResponse


class RevisionAgent:
    """Classifies natural-language revision intent and creates the next action plan."""

    def __init__(self, text_provider: TextProvider | None = None) -> None:
        self.text_provider = text_provider or get_text_provider()
        self.prompt_agent = PromptEngineerAgent(self.text_provider)

    def run(self, project: Project, plan: CreativePlanPayload, instruction: str) -> RevisionResponse:
        base_prompt = self.prompt_agent.run(project, plan)
        model_payload = generate_payload(
            provider=self.text_provider,
            payload_type=RevisionResponse,
            system_prompt=(
                "You are an agent workflow controller. Classify the user's revision request and decide "
                "whether image regeneration is needed. Return a practical modification plan."
            ),
            user_prompt=json.dumps(
                {
                    "project": {
                        "product_name": project.product_name,
                        "target_platform": project.target_platform,
                    },
                    "plan": plan.model_dump(),
                    "current_prompt": base_prompt.model_dump(),
                    "instruction": instruction,
                    "allowed_revision_types": ["copywriting", "platform", "prompt", "style", "creative_plan", "image"],
                    "required_fields": RevisionResponse.model_json_schema(),
                },
                ensure_ascii=False,
            ),
            schema_name="RevisionResponse",
            temperature=0.25,
        )
        return model_payload
