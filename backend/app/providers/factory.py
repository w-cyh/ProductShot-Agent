from app.model_settings import resolve_model_config_for_process
from app.providers.dashscope_image_provider import DashscopeImageProvider
from app.providers.dashscope_text_provider import DashscopeTextProvider
from app.providers.openai_image_provider import OpenAIImageProvider
from app.providers.openai_text_provider import OpenAITextProvider
from app.providers.text_provider import ProviderConfigurationError


def get_image_provider():
    config = resolve_model_config_for_process()
    if config.image_provider == "openai":
        return OpenAIImageProvider(config.providers["openai"])
    if config.image_provider == "dashscope":
        return DashscopeImageProvider(config.providers["dashscope"])
    raise ProviderConfigurationError("IMAGE_PROVIDER must be configured as 'openai' or 'dashscope'.")


def get_text_provider():
    config = resolve_model_config_for_process()
    if config.text_provider == "dashscope":
        return DashscopeTextProvider(config.providers["dashscope"])
    if config.text_provider == "openai":
        return OpenAITextProvider(config.providers["openai"])
    raise ProviderConfigurationError("TEXT_PROVIDER must be configured as 'openai' or 'dashscope'.")
