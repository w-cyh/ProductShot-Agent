import base64
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agents import ImageCriticAgent, ProductAnalysisAgent, VisualAnalysisAgent
from app.config import settings
from app.database import Base
from app.models import GeneratedImage, ProductAsset, Project, WorkflowEvent
from app.providers import get_text_provider
from app.providers.dashscope_image_provider import DashscopeImageProvider
from app.providers.dashscope_text_provider import DashscopeTextProvider
from app.providers.openai_image_provider import OpenAIImageProvider
from app.providers.openai_text_provider import OpenAITextProvider
from app.providers.text_provider import ProviderConfigurationError, ProviderRequestError
from app.schemas import CreativePlanPayload, ProductAnalysisPayload, VisualAnalysisPayload
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


def test_dashscope_text_provider_requires_vision_model(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "dashscope_api_key", "test-key")
    monkeypatch.setattr(settings, "dashscope_text_model", "qwen-test")
    monkeypatch.setattr(settings, "dashscope_vision_model", "")
    image = tmp_path / "source.png"
    image.write_bytes(b"image")

    with pytest.raises(ProviderConfigurationError, match="DASHSCOPE_VISION_MODEL.*multimodal"):
        DashscopeTextProvider().generate_multimodal_json(
            system_prompt="system",
            user_prompt="user",
            image_path=str(image),
            schema_name="Test",
            schema={},
        )


def test_dashscope_text_provider_uses_generation_sdk(monkeypatch):
    calls = {}
    dashscope_module = ModuleType("dashscope")
    dashscope_module.base_http_api_url = ""

    class FakeGeneration:
        @staticmethod
        def call(**kwargs):
            calls.update(kwargs)
            return SimpleNamespace(output=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=[{"text": '{"ok": true}'}]))]))

    dashscope_module.Generation = FakeGeneration
    monkeypatch.setitem(sys.modules, "dashscope", dashscope_module)
    monkeypatch.setattr(settings, "dashscope_api_key", "test-key")
    monkeypatch.setattr(settings, "dashscope_text_model", "qwen-test")
    monkeypatch.setattr(settings, "dashscope_workspace_id", "workspace-test")
    provider = DashscopeTextProvider()
    assert provider.generate_json(system_prompt="system", user_prompt="user", schema_name="Test", schema={"type": "object"}) == {"ok": True}
    assert calls["model"] == "qwen-test"
    assert calls["result_format"] == "message"
    assert calls["workspace"] == "workspace-test"
    assert calls["messages"][0]["role"] == "system"
    assert calls["messages"][1] == {"role": "user", "content": "user"}


def test_dashscope_text_provider_uses_multimodal_sdk_for_multiple_images(monkeypatch, tmp_path: Path):
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
    monkeypatch.setattr(settings, "dashscope_text_model", "qwen-vl-test")
    monkeypatch.setattr(settings, "dashscope_vision_model", "qwen3-vl-test")
    monkeypatch.setattr(settings, "dashscope_workspace_id", None)
    source = tmp_path / "source.png"
    generated = tmp_path / "generated.png"
    source.write_bytes(b"source")
    generated.write_bytes(b"generated")

    provider = DashscopeTextProvider()
    result = provider.generate_multimodal_json(
        system_prompt="system",
        user_prompt="user",
        image_paths=[str(source), str(generated)],
        schema_name="Test",
        schema={"type": "object"},
    )

    assert result == {"ok": True}
    assert calls["model"] == "qwen3-vl-test"
    assert calls["messages"][0]["content"][0]["image"] == source.resolve().as_uri()
    assert calls["messages"][0]["content"][1]["image"] == generated.resolve().as_uri()
    assert "workspace" not in calls


def test_image_critic_sends_source_and_candidate_to_multimodal_provider(tmp_path: Path):
    class CapturingProvider:
        name = "fake"
        model = "fake-vl"

        def __init__(self):
            self.image_paths = []

        def generate_multimodal_json(self, **kwargs):
            self.image_paths = kwargs["image_paths"]
            return {
                "product_consistency": 9,
                "product_clarity": 9,
                "commercial_value": 8,
                "text_accuracy": 8,
            }

    source = tmp_path / "source.png"
    candidate = tmp_path / "candidate.png"
    source.write_bytes(b"source")
    candidate.write_bytes(b"candidate")
    provider = CapturingProvider()
    image = GeneratedImage(id=2, task_id=1, project_id=1, image_url="/uploads/candidate.png", image_path=str(candidate))
    plan = CreativePlanPayload(
        plan_name="生活方式",
        applicable_platform="小红书",
        visual_description="自然场景",
        background_scene="窗边",
        visual_style="自然",
        main_selling_point="手工质感",
        recommendation_reason="适合目标用户",
        copywriting_direction="克制分享",
    )

    review = ImageCriticAgent(provider).run(sample_project(), image, plan, source_image_path=str(source))

    assert provider.image_paths == [str(source), str(candidate)]
    assert review.product_consistency == 9


def test_dashscope_multimodal_url_error_suggests_vision_model(monkeypatch, tmp_path: Path):
    dashscope_module = ModuleType("dashscope")
    dashscope_module.base_http_api_url = ""

    class FakeConversation:
        @staticmethod
        def call(**_kwargs):
            return SimpleNamespace(
                status_code=400,
                request_id="request-test",
                code="InvalidParameter",
                message="url error, please check url",
                output=None,
            )

    dashscope_module.MultiModalConversation = FakeConversation
    monkeypatch.setitem(sys.modules, "dashscope", dashscope_module)
    monkeypatch.setattr(settings, "dashscope_api_key", "test-key")
    monkeypatch.setattr(settings, "dashscope_text_model", "qwen-test")
    monkeypatch.setattr(settings, "dashscope_vision_model", "qwen-test")
    monkeypatch.setattr(settings, "dashscope_workspace_id", None)
    image = tmp_path / "source.png"
    image.write_bytes(b"image")

    with pytest.raises(ProviderRequestError, match="DASHSCOPE_VISION_MODEL.*multimodal"):
        DashscopeTextProvider().generate_multimodal_json(
            system_prompt="system",
            user_prompt="user",
            image_path=str(image),
            schema_name="Test",
            schema={},
        )


def test_dashscope_text_provider_reports_sdk_error_details(monkeypatch):
    dashscope_module = ModuleType("dashscope")
    dashscope_module.base_http_api_url = ""

    class FakeGeneration:
        @staticmethod
        def call(**_kwargs):
            return SimpleNamespace(
                status_code=400,
                request_id="request-test",
                code="InvalidParameter",
                message="url error",
                output=None,
            )

    dashscope_module.Generation = FakeGeneration
    monkeypatch.setitem(sys.modules, "dashscope", dashscope_module)
    monkeypatch.setattr(settings, "dashscope_api_key", "test-key")
    monkeypatch.setattr(settings, "dashscope_text_model", "qwen-test")
    monkeypatch.setattr(settings, "dashscope_workspace_id", None)

    with pytest.raises(ProviderRequestError, match="InvalidParameter.*url error.*request-test"):
        DashscopeTextProvider().generate_json(system_prompt="system", user_prompt="user", schema_name="Test", schema={})


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


def test_dashscope_qwen_image_provider_uses_synchronous_generation(monkeypatch, tmp_path: Path):
    calls = {}

    def fake_post(url, **kwargs):
        calls["post"] = (url, kwargs)
        return FakeResponse(
            {
                "output": {
                    "choices": [
                        {
                            "message": {
                                "content": [
                                    {"image": "https://example.com/image-1.png"},
                                    {"image": "https://example.com/image-2.png"},
                                ]
                            }
                        }
                    ]
                }
            }
        )

    def fake_download(self, _url, target):
        target.write_bytes(b"image")

    monkeypatch.setattr("app.providers.dashscope_image_provider.httpx.post", fake_post)
    monkeypatch.setattr(DashscopeImageProvider, "_download_image", fake_download)
    monkeypatch.setattr(settings, "generated_dir", tmp_path)
    monkeypatch.setattr(settings, "dashscope_api_key", "test-key")
    monkeypatch.setattr(settings, "dashscope_image_model", "qwen-image-2.0-pro-test")
    source = tmp_path / "source.png"
    source.write_bytes(b"source")

    results = DashscopeImageProvider().generate_images(
        project_id=1,
        source_image_path=str(source),
        positive_prompt="prompt",
        negative_prompt="negative",
        size="1024x1024",
        count=2,
    )

    request_url, request = calls["post"]
    assert len(results) == 2
    assert request_url.endswith("/services/aigc/multimodal-generation/generation")
    assert "X-DashScope-Async" not in request["headers"]
    assert request["json"]["parameters"]["negative_prompt"] == "negative"
    assert request["json"]["parameters"]["size"] == "1024*1024"
    assert request["json"]["parameters"]["n"] == 2
    assert request["json"]["input"]["messages"][0]["content"][0]["image"].startswith("data:image/png;base64,")


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


def test_agents_do_not_fall_back_to_local_rules():
    with pytest.raises(ProviderConfigurationError):
        VisualAnalysisAgent(FailingTextProvider()).run(sample_project())
    with pytest.raises(ProviderConfigurationError):
        ProductAnalysisAgent(FailingTextProvider()).run(sample_project())


def test_workflow_records_failed_model_event(monkeypatch, tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr("app.services.workflow.get_text_provider", lambda: FailingTextProvider())
    with Session(engine) as db:
        project = sample_project()
        project.id = None
        project.status = "draft"
        project.source_confirmed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(project)
        db.commit()
        db.refresh(project)
        source = tmp_path / "source.png"
        source.write_bytes(b"source")
        db.add(ProductAsset(project_id=project.id, file_url="/uploads/source.png", file_path=str(source), file_type="image/png", is_primary=True))
        db.commit()
        with pytest.raises(ProviderConfigurationError):
            ProductShotWorkflow(db).ensure_visual_analysis(project)
        event = db.query(WorkflowEvent).filter(WorkflowEvent.project_id == project.id).one()
    assert event.step_key == "visual_analysis"
    assert event.status == "failed"
    assert "OPENAI_API_KEY" in event.error_message
