from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import ModelNameHistory, ModelRuntimeSettings, ProviderModelConfig


TEXT_PROVIDERS = ("openai", "dashscope")
IMAGE_PROVIDERS = ("openai", "dashscope")
MODEL_KINDS = ("text_model", "vision_model", "image_model")


@dataclass(frozen=True)
class ProviderRuntimeConfig:
    text_model: str
    vision_model: str
    image_model: str
    base_url: str


@dataclass(frozen=True)
class RuntimeModelConfig:
    text_provider: str
    image_provider: str
    providers: dict[str, ProviderRuntimeConfig]


def environment_model_config() -> RuntimeModelConfig:
    return RuntimeModelConfig(
        text_provider=settings.text_provider,
        image_provider=settings.image_provider,
        providers={
            "openai": ProviderRuntimeConfig(
                text_model=settings.openai_text_model,
                vision_model=settings.openai_text_model,
                image_model=settings.openai_image_model,
                base_url=settings.openai_base_url,
            ),
            "dashscope": ProviderRuntimeConfig(
                text_model=settings.dashscope_text_model,
                vision_model=settings.dashscope_vision_model,
                image_model=settings.dashscope_image_model,
                base_url=settings.dashscope_base_http_api_url,
            ),
        },
    )


def resolve_model_config(db: Session) -> RuntimeModelConfig:
    """Return persisted provider settings, with documented environment fallback."""

    fallback = environment_model_config()
    runtime = db.get(ModelRuntimeSettings, 1)
    if runtime is None:
        return fallback

    rows = {
        row.provider: row
        for row in db.query(ProviderModelConfig).filter(ProviderModelConfig.provider.in_(TEXT_PROVIDERS)).all()
    }
    providers: dict[str, ProviderRuntimeConfig] = {}
    for provider in TEXT_PROVIDERS:
        row = rows.get(provider)
        default = fallback.providers[provider]
        providers[provider] = ProviderRuntimeConfig(
            text_model=row.text_model if row else default.text_model,
            vision_model=row.vision_model if row else default.vision_model,
            image_model=row.image_model if row else default.image_model,
            base_url=row.base_url if row else default.base_url,
        )
    return RuntimeModelConfig(
        text_provider=runtime.text_provider or fallback.text_provider,
        image_provider=runtime.image_provider or fallback.image_provider,
        providers=providers,
    )


def resolve_model_config_for_process() -> RuntimeModelConfig:
    """Resolve the latest shared settings for a web or Celery process.

    First-run startup and isolated tests may not have persistence tables yet;
    those scenarios retain the environment variable fallback rather than
    surfacing an unrelated database exception.
    """

    try:
        with SessionLocal() as db:
            return resolve_model_config(db)
    except SQLAlchemyError:
        return environment_model_config()


def current_provider_values(config: RuntimeModelConfig, provider: str) -> dict[str, str]:
    values = config.providers[provider]
    return {
        "text_model": values.text_model,
        "vision_model": values.vision_model,
        "image_model": values.image_model,
        "base_url": values.base_url,
    }


def model_name_history(db: Session) -> dict[str, dict[str, list[ModelNameHistory]]]:
    grouped = {provider: {kind: [] for kind in MODEL_KINDS} for provider in TEXT_PROVIDERS}
    rows = (
        db.query(ModelNameHistory)
        .filter(ModelNameHistory.provider.in_(TEXT_PROVIDERS))
        .order_by(ModelNameHistory.updated_at.desc(), ModelNameHistory.id.desc())
        .all()
    )
    for row in rows:
        if row.provider in grouped and row.model_kind in grouped[row.provider]:
            grouped[row.provider][row.model_kind].append(row)
    return grouped


def upsert_model_name_history(db: Session, provider: str, model_kind: str, model_name: str) -> None:
    normalized = model_name.strip()
    if not normalized:
        return
    existing = (
        db.query(ModelNameHistory)
        .filter(
            ModelNameHistory.provider == provider,
            ModelNameHistory.model_kind == model_kind,
            ModelNameHistory.model_name == normalized,
        )
        .first()
    )
    if existing is None:
        db.add(ModelNameHistory(provider=provider, model_kind=model_kind, model_name=normalized))
