from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from app.config import settings
from app.providers.image_provider import GeneratedImageFile
from app.providers.text_provider import ProviderConfigurationError, ProviderRequestError
from app.model_settings import ProviderRuntimeConfig


class OpenAIImageProvider:
    name = "openai"
    capabilities = {"text_to_image", "image_to_image", "reference_image"}
    max_batch_size = 4

    def __init__(self, runtime_config: ProviderRuntimeConfig | None = None) -> None:
        self.api_key = settings.openai_api_key
        self.model = runtime_config.image_model if runtime_config else settings.openai_image_model
        self.base_url = (runtime_config.base_url if runtime_config else settings.openai_base_url).rstrip("/")

    def generate_images(
        self,
        *,
        project_id: int,
        source_image_path: str | None,
        positive_prompt: str,
        negative_prompt: str,
        size: str,
        count: int,
    ) -> list[GeneratedImageFile]:
        self._validate_configuration()
        prompt = f"{positive_prompt}\n\nNegative constraints: {negative_prompt}"
        provider_size = self._normalize_size(size)
        images = self._edit_images(prompt, source_image_path, provider_size, count) if source_image_path else self._generate_images(prompt, provider_size, count)
        project_dir = settings.generated_dir / str(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        width, height = self._parse_size(provider_size)
        files: list[GeneratedImageFile] = []
        for index, data in enumerate(images):
            target = project_dir / f"openai_{uuid4().hex}_{index + 1}.png"
            target.write_bytes(data)
            files.append(
                GeneratedImageFile(
                    image_path=target,
                    image_url=f"/uploads/generated/{project_id}/{target.name}",
                    width=width,
                    height=height,
                )
            )
        return files

    def _generate_images(self, prompt: str, size: str, count: int) -> list[bytes]:
        data = self._post_json(
            "/images/generations",
            {"model": self.model, "prompt": prompt, "size": size, "n": count, "response_format": "b64_json"},
        )
        return self._decode_images(data)

    def _edit_images(self, prompt: str, source_image_path: str, size: str, count: int) -> list[bytes]:
        path = Path(source_image_path)
        if not path.exists():
            raise ProviderRequestError("OpenAI source image path does not exist.")
        mime_type, _ = mimetypes.guess_type(path.name)
        if not mime_type or not mime_type.startswith("image/"):
            raise ProviderRequestError(f"Unsupported OpenAI source image type: {path.name}")
        try:
            response = httpx.post(
                f"{self.base_url}/images/edits",
                headers={"Authorization": f"Bearer {self.api_key}"},
                data={"model": self.model, "prompt": prompt, "size": size, "n": str(count), "response_format": "b64_json"},
                files={"image": (path.name, path.read_bytes(), mime_type)},
                timeout=settings.model_request_timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderRequestError(f"OpenAI image edit failed: {self._error_message(exc.response)}") from exc
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"OpenAI image edit failed: {exc}") from exc
        return self._decode_images(response.json())

    def _post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(
                f"{self.base_url}{endpoint}",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=settings.model_request_timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderRequestError(f"OpenAI image generation failed: {self._error_message(exc.response)}") from exc
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"OpenAI image generation failed: {exc}") from exc
        return response.json()

    def _decode_images(self, response: dict[str, Any]) -> list[bytes]:
        images: list[bytes] = []
        for item in response.get("data", []):
            encoded = item.get("b64_json") if isinstance(item, dict) else None
            if not encoded:
                continue
            try:
                images.append(base64.b64decode(encoded))
            except (ValueError, TypeError) as exc:
                raise ProviderRequestError("OpenAI image response contained invalid base64 data.") from exc
        if not images:
            raise ProviderRequestError("OpenAI image response did not include image data.")
        return images

    def _validate_configuration(self) -> None:
        if not self.api_key:
            raise ProviderConfigurationError("OPENAI_API_KEY is not configured.")
        if not self.model:
            raise ProviderConfigurationError("OpenAI image model is not configured.")

    def _normalize_size(self, size: str) -> str:
        return size if size in {"1024x1024", "1024x1536", "1536x1024"} else "1024x1024"

    def _parse_size(self, size: str) -> tuple[int, int]:
        width, height = size.split("x", 1)
        return int(width), int(height)

    def _error_message(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return response.text
        error = data.get("error", data) if isinstance(data, dict) else data
        return str(error.get("message") or error.get("code") or error) if isinstance(error, dict) else str(error)
