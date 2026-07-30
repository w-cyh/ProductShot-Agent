from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import settings
from app.providers.text_provider import ProviderConfigurationError, ProviderRequestError, TextProviderError, TextProviderUnavailable
from app.model_settings import ProviderRuntimeConfig


class DashscopeTextProvider:
    name = "dashscope"

    def __init__(self, runtime_config: ProviderRuntimeConfig | None = None) -> None:
        self.api_key = settings.dashscope_api_key
        self.model = runtime_config.text_model if runtime_config else settings.dashscope_text_model
        self.vision_model = runtime_config.vision_model if runtime_config else settings.dashscope_vision_model
        self.base_url = (runtime_config.base_url if runtime_config else settings.dashscope_base_http_api_url).rstrip("/")
        self.workspace_id = settings.dashscope_workspace_id

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        schema: dict[str, Any],
        temperature: float = 0.4,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise ProviderConfigurationError("DASHSCOPE_API_KEY is not configured.")
        if not self.model:
            raise ProviderConfigurationError("DashScope text model is not configured.")

        messages = [
            {
                "role": "system",
                "content": (
                    f"{system_prompt}\n\n"
                    f"Return only valid JSON for the {schema_name} schema. Do not wrap the JSON in Markdown.\n\n"
                ),
            },
            {"role": "user", "content": user_prompt},
        ]
        response = self._call_text(messages=messages, temperature=temperature)
        return self._parse_json_content(self._response_text(response))

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
        if not self.api_key:
            raise ProviderConfigurationError("DASHSCOPE_API_KEY is not configured.")
        if not self.vision_model:
            raise ProviderConfigurationError(
                "DASHSCOPE_VISION_MODEL is not configured. Image understanding and image review require "
                "a DashScope multimodal model, such as qwen3-vl-plus."
            )

        resolved_paths = image_paths or ([image_path] if image_path else [])
        if not resolved_paths:
            raise ProviderRequestError("DashScope multimodal requests require at least one image path.")

        content = [
            *[{"image": self._image_reference(path)} for path in resolved_paths],
            {
                "text": (
                    f"{system_prompt}\n\n"
                    f"Return only valid JSON for the {schema_name} schema. Do not wrap the JSON in Markdown.\n\n"
                    f"User input:\n{user_prompt}"
                )
            },
        ]
        response = self._call_multimodal(content=content, temperature=temperature)
        return self._parse_json_content(self._response_text(response, request_kind="multimodal"))

    def _call_text(self, *, messages: list[dict[str, str]], temperature: float):
        try:
            import dashscope
        except ImportError as exc:
            raise TextProviderUnavailable("dashscope package is not installed. Run `pip install -r requirements.txt`.") from exc

        dashscope.base_http_api_url = self.base_url
        kwargs = {
            "api_key": self.api_key,
            "model": self.model,
            "messages": messages,
            "result_format": "message",
            "temperature": temperature,
        }
        if self.workspace_id:
            kwargs["workspace"] = self.workspace_id
        try:
            return dashscope.Generation.call(**kwargs)
        except Exception as exc:
            raise ProviderRequestError(f"DashScope SDK request failed: {exc}") from exc

    def _call_multimodal(self, *, content: list[dict[str, str]], temperature: float):
        try:
            import dashscope
        except ImportError as exc:
            raise TextProviderUnavailable("dashscope package is not installed. Run `pip install -r requirements.txt`.") from exc

        dashscope.base_http_api_url = self.base_url
        kwargs = {
            "api_key": self.api_key,
            "model": self.vision_model,
            "messages": [{"role": "user", "content": content}],
            "temperature": temperature,
        }
        if self.workspace_id:
            kwargs["workspace"] = self.workspace_id
        try:
            return dashscope.MultiModalConversation.call(**kwargs)
        except Exception as exc:
            raise ProviderRequestError(f"DashScope SDK request failed: {exc}") from exc

    def _response_text(self, response: Any, *, request_kind: str = "text") -> str:
        status_code = getattr(response, "status_code", None)
        if status_code is not None and status_code != 200:
            code = getattr(response, "code", None) or "unknown_error"
            message = getattr(response, "message", None) or "Unknown DashScope error."
            request_id = getattr(response, "request_id", None)
            request_detail = f" request_id={request_id}" if request_id else ""
            guidance = (
                " Verify that DASHSCOPE_VISION_MODEL is a multimodal model supported by MultiModalConversation."
                if request_kind == "multimodal" and "url error" in message.lower()
                else ""
            )
            raise ProviderRequestError(
                f"DashScope request failed: status_code={status_code} code={code} message={message}.{request_detail}{guidance}"
            )
        try:
            content = response.output.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise TextProviderError(f"DashScope SDK response did not include message content: {response}") from exc
        if isinstance(content, list):
            return "".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in content).strip()
        if isinstance(content, str):
            return content.strip()
        raise TextProviderError("DashScope SDK message content was not text.")

    def _parse_json_content(self, content: Any) -> dict[str, Any]:
        if isinstance(content, list):
            content = "".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in content)
        if not isinstance(content, str):
            raise TextProviderError("DashScope text content was not a string.")

        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise TextProviderError("DashScope text content was not valid JSON.") from exc
        if not isinstance(parsed, dict):
            raise TextProviderError("DashScope text content must be a JSON object.")
        return parsed

    def _image_reference(self, image_path: str) -> str:
        path = Path(image_path)
        if not path.exists():
            raise TextProviderError("DashScope multimodal image path does not exist.")
        return path.resolve().as_uri()
