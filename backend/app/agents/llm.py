from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel
from pydantic import ValidationError

from app.providers import TextProvider
from app.providers.text_provider import ProviderRequestError
PayloadT = TypeVar("PayloadT", bound=BaseModel)


def generate_payload(
    *,
    provider: TextProvider,
    payload_type: type[PayloadT],
    system_prompt: str,
    user_prompt: str,
    schema_name: str,
    temperature: float = 0.4,
) -> PayloadT:
    data = provider.generate_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema_name=schema_name,
        schema=payload_type.model_json_schema(),
        temperature=temperature,
    )
    try:
        return payload_type.model_validate(data)
    except ValidationError as exc:
        raise ProviderRequestError(f"Configured LLM returned an invalid {schema_name} payload.") from exc
