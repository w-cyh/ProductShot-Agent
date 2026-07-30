from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import pytest
from fastapi import HTTPException

from app.api.routes import delete_model_name_history, update_model_settings
from app.config import settings
from app.database import Base
from app.model_settings import resolve_model_config
from app.providers import get_text_provider
from app.schemas import ModelSettingsUpdate


def _settings_update(text_model: str) -> ModelSettingsUpdate:
    return ModelSettingsUpdate(
        text_provider="dashscope",
        image_provider="openai",
        providers={
            "dashscope": {
                "text_model": text_model,
                "vision_model": "qwen3-vl-plus",
                "base_url": "https://dashscope.aliyuncs.com/api/v1",
            },
            "openai": {"image_model": "gpt-image-1"},
        },
    )


def test_model_settings_persist_names_and_protect_the_active_value():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        first = update_model_settings(_settings_update("qwen-plus"), db)
        assert first.text_provider == "dashscope"
        text_history = first.model_name_history["dashscope"]["text_model"]
        assert [item.model_name for item in text_history] == ["qwen-plus"]

        with pytest.raises(HTTPException, match="正在使用"):
            delete_model_name_history(text_history[0].id, db)

        second = update_model_settings(_settings_update("qwen-max"), db)
        assert {item.model_name for item in second.model_name_history["dashscope"]["text_model"]} == {"qwen-plus", "qwen-max"}
        previous = next(item for item in second.model_name_history["dashscope"]["text_model"] if item.model_name == "qwen-plus")
        after_delete = delete_model_name_history(previous.id, db)
        assert [item.model_name for item in after_delete.model_name_history["dashscope"]["text_model"]] == ["qwen-max"]


def test_provider_factory_resolves_database_settings_for_a_separate_process(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        update_model_settings(_settings_update("qwen-worker"), db)
        assert resolve_model_config(db).providers["dashscope"].text_model == "qwen-worker"

    monkeypatch.setattr("app.model_settings.SessionLocal", lambda: Session(engine))
    monkeypatch.setattr(settings, "text_provider", "")
    provider = get_text_provider()

    assert provider.name == "dashscope"
    assert provider.model == "qwen-worker"
    assert provider.vision_model == "qwen3-vl-plus"
