import base64
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agents import ProductAnalysisAgent, VisualAnalysisAgent
from app.api.routes import test_text_model_connection as run_text_model_connection_test
from app.config import settings
from app.database import Base
from app.models import Project, WorkflowEvent
from app.providers import get_text_provider
from app.providers.dashscope_image_provider import DashscopeImageProvider
from app.providers.dashscope_text_provider import DashscopeTextProvider
from app.providers.openai_image_provider import OpenAIImageProvider
from app.providers.openai_text_provider import OpenAITextProvider
from app.providers.text_provider import ProviderConfigurationError
from app.schemas import ProductAnalysisPayload, VisualAnalysisPayload
from app.services import ProductShotWorkflow


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.text = str(payload)

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FailingTextProvider:
    name = "openai"
    model = "test-model"

    def generate_json(self, **_):
        raise ProviderConfigurationError("OPENAI_API_KEY is not configured.")

    def generate_multimodal_json(self, **_):
        raise ProviderConfigurationError("OPENAI_API_KEY is not configured.")


def sample_project() -> Project:
    return Project(id=1, product_name="手工香薰蜡烛", product_category="家居香氛", core_selling_points="手工制作", target_platform="小红书")


def test_text_provider_factory_requires_real_provider(monkeypatch):
    monkeypatch.setattr(settings, "text_provider", "")
    with pytest.raises(ProviderConfigurationError, match="TEXT_PROVIDER"):
        get_text_provider()


def test_text_provider_factory_rejects_unknown_provider(monkeypatch):
    monkeypatch.setattr(settings, "text_provider", "mock")
    with pytest.raises(ProviderConfigurationError, match="TEXT_PROVIDER"):
        get_text_provider()


def test_dashscope_text_provider_requires_key_and_model(monkeypatch):
    monkeypatch.setattr(settings, "dashscope_api_key", None)
    monkeypatch.setattr(settings, "dashscope_text_model", "qwen-test")
    with pytest.raises(ProviderConfigurationError, match="DASHSCOPE_API_KEY"):
        DashscopeTextProvider().generate_json(system_prompt="x", user_prompt="y", schema_name="Test", schema={})

    monkeypatch.setattr(settings, "dashscope_api_key", "test-key")
    monkeypatch.setattr(settings, "dashscope_text_model", "")
    with pytest.raises(ProviderConfigurationError, match="text model"):
        DashscopeTextProvider().generate_json(system_prompt="x", user_prompt="y", schema_name="Test", schema={})


def test_dashscope_image_provider_requires_key_and_model(monkeypatch):
    monkeypatch.setattr(settings, "dashscope_api_key", None)
    monkeypatch.setattr(settings, "dashscope_image_model", "wan-test")
    with pytest.raises(ProviderConfigurationError, match="DASHSCOPE_API_KEY"):
        DashscopeImageProvider().generate_images(project_id=1, source_image_path=None, positive_prompt="x", negative_prompt="y", size="1024x1024", count=1)


def test_dashscope_text_provider_uses_multimodal_sdk(monkeypatch):
    calls = {}
    dashscope_module = ModuleType("dashscope")
    dashscope_module.base_http_api_url = ""

    class FakeConversation:
        @staticmethod
        def call(**kwargs):
            calls.update(kwargs)
            return SimpleNamespace(output=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=[{"text": '{"ok": true}'}]))]))

    dashscope_module.MultiModalConversation = FakeConversation
    monkeypatch.setitem(sys.modules, "dashscope", dashscope_module)
    monkeypatch.setattr(settings, "dashscope_api_key", "test-key")
    monkeypatch.setattr(settings, "dashscope_text_model", "qwen-test")
    provider = DashscopeTextProvider()
    assert provider.generate_json(system_prompt="system", user_prompt="user", schema_name="Test", schema={"type": "object"}) == {"ok": True}
    assert calls["model"] == "qwen-test"


def test_dashscope_image_provider_uses_async_generation(monkeypatch, tmp_path: Path):
    calls = {}

    def fake_post(url, **kwargs):
        calls["post"] = (url, kwargs)
        return FakeResponse({"output": {"task_id": "task-123"}})

    def fake_get(url, **kwargs):
        calls["get"] = (url, kwargs)
        return FakeResponse({"output": {"task_status": "SUCCEEDED", "choices": [{"message": {"content": [{"image": "https://example.com/image.png"}]}}]}})

    def fake_download(self, _url, target):
        target.write_bytes(b"image")

    monkeypatch.setattr("app.providers.dashscope_image_provider.httpx.post", fake_post)
    monkeypatch.setattr("app.providers.dashscope_image_provider.httpx.get", fake_get)
    monkeypatch.setattr(DashscopeImageProvider, "_download_image", fake_download)
    monkeypatch.setattr(settings, "generated_dir", tmp_path)
    monkeypatch.setattr(settings, "dashscope_api_key", "test-key")
    monkeypatch.setattr(settings, "dashscope_image_model", "wan-test")
    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    results = DashscopeImageProvider().generate_images(project_id=1, source_image_path=str(source), positive_prompt="prompt", negative_prompt="negative", size="1024x1024", count=1)
    assert len(results) == 1
    assert calls["post"][0].endswith("/services/aigc/image-generation/generation")
    assert calls["get"][0].endswith("/tasks/task-123")


def test_openai_text_provider_uses_structured_responses(monkeypatch):
    calls = {}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["payload"] = kwargs["json"]
        return FakeResponse({"status": "completed", "output_text": '{"ok": true}'})

    monkeypatch.setattr("app.providers.openai_text_provider.httpx.post", fake_post)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_text_model", "gpt-test")
    result = OpenAITextProvider().generate_json(system_prompt="system", user_prompt="user", schema_name="Test", schema={"type": "object"})
    assert result == {"ok": True}
    assert calls["url"].endswith("/responses")
    assert calls["payload"]["text"]["format"]["type"] == "json_schema"


def test_openai_image_provider_generates_and_edits(monkeypatch, tmp_path: Path):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse({"data": [{"b64_json": base64.b64encode(b"png").decode()}]})

    monkeypatch.setattr("app.providers.openai_image_provider.httpx.post", fake_post)
    monkeypatch.setattr(settings, "generated_dir", tmp_path)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_image_model", "gpt-image-test")
    provider = OpenAIImageProvider()
    generated = provider.generate_images(project_id=1, source_image_path=None, positive_prompt="x", negative_prompt="y", size="1024x1024", count=1)
    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    edited = provider.generate_images(project_id=2, source_image_path=str(source), positive_prompt="x", negative_prompt="y", size="1024x1024", count=1)
    assert generated[0].image_path.read_bytes() == b"png"
    assert edited[0].image_path.read_bytes() == b"png"
    assert calls[0][0].endswith("/images/generations")
    assert calls[1][0].endswith("/images/edits")


def test_connection_test_reports_unconfigured_provider(monkeypatch):
    monkeypatch.setattr(settings, "text_provider", "")
    result = run_text_model_connection_test()
    assert result.status == "failed"
    assert result.provider == "unconfigured"
    assert "TEXT_PROVIDER" in result.message


def test_agents_do_not_fall_back_to_local_rules():
    with pytest.raises(ProviderConfigurationError):
        VisualAnalysisAgent(FailingTextProvider()).run(sample_project())
    with pytest.raises(ProviderConfigurationError):
        ProductAnalysisAgent(FailingTextProvider()).run(sample_project())


def test_workflow_records_failed_model_event(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr("app.services.workflow.get_text_provider", lambda: FailingTextProvider())
    with Session(engine) as db:
        project = sample_project()
        project.id = None
        project.status = "draft"
        db.add(project)
        db.commit()
        db.refresh(project)
        with pytest.raises(ProviderConfigurationError):
            ProductShotWorkflow(db).ensure_visual_analysis(project)
        event = db.query(WorkflowEvent).filter(WorkflowEvent.project_id == project.id).one()
    assert event.step_key == "visual_analysis"
    assert event.status == "failed"
    assert "OPENAI_API_KEY" in event.error_message
