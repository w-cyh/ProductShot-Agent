from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.entities import utcnow


class ModelRuntimeSettings(Base):
    """The persisted provider choices used by web and worker processes.

    Provider API keys intentionally remain environment-only and are never
    represented by this model.
    """

    __tablename__ = "model_runtime_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text_provider: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    image_provider: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class ProviderModelConfig(Base):
    """Persisted non-secret model and endpoint settings for one provider."""

    __tablename__ = "provider_model_configs"
    __table_args__ = (UniqueConstraint("provider", name="uq_provider_model_configs_provider"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    text_model: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    vision_model: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    image_model: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    base_url: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class ModelNameHistory(Base):
    """Reusable model-name values shown in the settings dropdowns."""

    __tablename__ = "model_name_history"
    __table_args__ = (
        UniqueConstraint("provider", "model_kind", "model_name", name="uq_model_name_history_value"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    model_kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
