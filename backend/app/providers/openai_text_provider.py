from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.providers.text_provider import ProviderConfigurationError, ProviderRequestError
from app.model_settings import ProviderRuntimeConfig


class OpenAITextProvider:
    name = "openai"

    def __init__(self, runtime_config: ProviderRuntimeConfig | None = None) -> None:
        self.api_key = settings.openai_api_key
        self.model = runtime_config.text_model if runtime_config else settings.openai_text_model
        self.base_url = (runtime_config.base_url if runtime_config else settings.openai_base_url).rstrip("/")

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        schema: dict[str, Any],
        temperature: float = 0.4,
    ) -> dict[str, Any]:
        return self._request_json(
            input_items=[{"role": "developer", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            schema_name=schema_name,
            schema=schema,
            temperature=temperature,
        )

    def generate_multimodal_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        schema: dict[str, Any],
        temperature: float = 0.2,
        image_path: str | None = None,
        image_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        resolved_paths = image_paths or ([image_path] if image_path else [])
        if not resolved_paths:
            raise ProviderRequestError("OpenAI multimodal requests require at least one image path.")
        return self._request_json(
            input_items=[
                {"role": "developer", "content": system_prompt},
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}]
                    + [
                        {"type": "input_image", "image_url": self._image_data_url(path), "detail": "high"}
                        for path in resolved_paths
                    ],
                },
            ],
            schema_name=schema_name,
            schema=schema,
            temperature=temperature,
        )

    def _request_json(
        self,
        *,
        input_items: list[dict[str, Any]],
        schema_name: str,
        schema: dict[str, Any],
        temperature: float,
    ) -> dict[str, Any]:
        self._validate_configuration()
        payload = {
            "model": self.model,
            "input": input_items,
            "temperature": temperature,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": self._strict_schema(schema),
                    "strict": True,
                }
            },
        }
        try:
            response = httpx.post(
                f"{self.base_url}/responses",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=settings.model_request_timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderRequestError(f"OpenAI request failed: {self._error_message(exc.response)}") from exc
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"OpenAI request failed: {exc}") from exc
        return self._parse_response(response.json())

    def _validate_configuration(self) -> None:
        if not self.api_key:
            raise ProviderConfigurationError("OPENAI_API_KEY is not configured.")
        if not self.model:
            raise ProviderConfigurationError("OpenAI text model is not configured.")

    def _parse_response(self, response: dict[str, Any]) -> dict[str, Any]:
        if response.get("status") not in {None, "completed"}:
            raise ProviderRequestError(f"OpenAI response was not completed: {response.get('status')}")
        text = response.get("output_text")
        if not text:
            for output in response.get("output", []):
                for content in output.get("content", []):
                    if content.get("type") == "output_text":
                        text = content.get("text")
                        break
                if text:
                    break
        if not isinstance(text, str):
            raise ProviderRequestError("OpenAI response did not include structured text output.")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderRequestError("OpenAI response was not valid JSON.") from exc
        if not isinstance(data, dict):
            raise ProviderRequestError("OpenAI structured response must be a JSON object.")
        return data

    def _image_data_url(self, image_path: str) -> str:
        path = Path(image_path)
        if not path.exists():
            raise ProviderRequestError("OpenAI multimodal image path does not exist.")
        mime_type, _ = mimetypes.guess_type(path.name)
        if not mime_type or not mime_type.startswith("image/"):
            raise ProviderRequestError(f"Unsupported OpenAI multimodal image type: {path.name}")
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def _strict_schema(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._strict_schema(item) for item in value]
        if not isinstance(value, dict):
            return value
        normalized = {key: self._strict_schema(item) for key, item in value.items() if key != "default"}
        properties = normalized.get("properties")
        if isinstance(properties, dict):
            normalized["additionalProperties"] = False
            normalized["required"] = list(properties)
        return normalized

    def _error_message(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return response.text
        error = data.get("error", data) if isinstance(data, dict) else data
        if isinstance(error, dict):
            return str(error.get("message") or error.get("code") or error)
        return str(error)
