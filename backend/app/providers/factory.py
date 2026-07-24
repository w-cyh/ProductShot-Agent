from app.config import settings
from app.providers.dashscope_image_provider import DashscopeImageProvider
from app.providers.dashscope_text_provider import DashscopeTextProvider
from app.providers.openai_image_provider import OpenAIImageProvider
from app.providers.openai_text_provider import OpenAITextProvider
from app.providers.text_provider import ProviderConfigurationError


def get_image_provider():
    if settings.image_provider == "openai":
        return OpenAIImageProvider()
    if settings.image_provider == "dashscope":
        return DashscopeImageProvider()
    raise ProviderConfigurationError("IMAGE_PROVIDER must be configured as 'openai' or 'dashscope'.")


def get_text_provider():
    if settings.text_provider == "dashscope":
        return DashscopeTextProvider()
    if settings.text_provider == "openai":
        return OpenAITextProvider()
    raise ProviderConfigurationError("TEXT_PROVIDER must be configured as 'openai' or 'dashscope'.")
