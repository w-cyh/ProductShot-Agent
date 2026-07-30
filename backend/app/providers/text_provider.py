from __future__ import annotations

from typing import Any, Protocol


class TextProviderError(RuntimeError):
    """Raised when a configured text provider cannot complete a request."""


class TextProviderUnavailable(TextProviderError):
    """Raised when a text provider has not been configured."""


class ProviderConfigurationError(TextProviderUnavailable):
    """Raised when a required provider setting is missing or invalid."""


class ProviderRequestError(TextProviderError):
    """Raised when a configured upstream provider rejects or cannot complete a request."""


class TextProvider(Protocol):
    name: str
    model: str

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        schema: dict[str, Any],
        temperature: float = 0.4,
    ) -> dict[str, Any]:
        ...

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
        ...
