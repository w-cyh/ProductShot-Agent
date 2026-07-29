from pathlib import Path
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.api.routes import get_project, update_project
from app.models import Copywriting, CreativePlan, CreativePlanBatch, GenerationTask, ProductAnalysis, ProductAsset, ProductVisualAnalysis, Project, PromptPack
from app.providers.image_provider import GeneratedImageFile
from app.schemas import (
    CopywritingPayload,
    CreativePlanPayload,
    ImageReviewPayload,
    ProductAnalysisPayload,
    PromptPackPayload,
    ProjectUpdate,
    VisualAnalysisPayload,
    WorkflowEventRead,
)
from app.services import ProductShotWorkflow


def plan_payload(name: str) -> CreativePlanPayload:
    return CreativePlanPayload(
        plan_name=name,
        applicable_platform="小红书",
        visual_description=f"{name} 的画面描述",
        background_scene="自然光场景",
        visual_style="轻盈生活方式",
        main_selling_point="手工质感",
        recommendation_reason="适合目标受众",
        copywriting_direction="克制分享",
        expected_outputs=["封面", "详情页"],
    )


class FakePlanner:
    def run(self, _project, _analysis, feedback="", platforms=None, style_presets=None):
        prefix = feedback or "初始"
        payloads = [plan_payload(f"{prefix}方向{index}") for index in range(1, 4)]
        for payload in payloads:
            if platforms:
                payload.applicable_platform = platforms[0]
            if style_presets:
                payload.visual_style = style_presets[0]
        return payloads

    def revise(self, _project, _analysis, source_plan, feedback):
        return source_plan.model_copy(update={"plan_name": f"{source_plan.plan_name}-{feedback}", "visual_description": f"已修改：{feedback}"})


class FakePromptAgent:
    def run(self, _project, _plan, _analysis=None, source_instruction="", parent_prompt=None):
        suffix = f" {source_instruction}" if source_instruction else ""
        return PromptPackPayload(
            positive_prompt=f"product photo{suffix}",
            negative_prompt="blur, text artifact",
            size="1024x1024",
            style="editorial",
            product_consistency_notes="保持商品材质和轮廓",
            platform="小红书",
            generation_mode="image_to_image",
            reference_strength=0.72,
            consistency_rules=["商品外形不变"],
        )


class FakeImageProvider:
    name = "fake"
    model = "fake-image"
    capabilities = {"text_to_image", "image_to_image"}
    max_batch_size = 2

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.calls: list[int] = []

    def generate_images(self, *, count: int, **_kwargs):
        self.calls.append(count)
        result = []
        for index in range(count):
            target = self.output_dir / f"generated-{len(self.calls)}-{index}.png"
            target.write_bytes(b"png")
            result.append(GeneratedImageFile(target, f"/uploads/{target.name}", 1024, 1024))
        return result


class FakeCritic:
    def run(self, *_args, **_kwargs):
        return ImageReviewPayload(
            overall_score=86,
            product_clarity=88,
            product_consistency=91,
            style_match=84,
            commercial_value=87,
            platform_fit=85,
            defects=[],
            suggestions=[],
        )


def create_project(db: Session, tmp_path: Path) -> Project:
    project = Project(
        product_name="香薰蜡烛",
        target_platform="多平台",
        source_confirmed_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(project)
    db.flush()
    source = tmp_path / "source.png"
    source.write_bytes(b"source")
    db.add(ProductAsset(project_id=project.id, file_url="/uploads/source.png", file_path=str(source), file_type="image/png", is_primary=True))
    db.add(
        ProductAnalysis(
            project_id=project.id,
            analysis_json=ProductAnalysisPayload(
                product_type="香薰蜡烛",
                core_features=["手工"],
                target_audience_analysis="居家用户",
                recommended_selling_points=["质感"],
                recommended_visual_styles=["自然"],
                image_issues=[],
                marketing_angles=["氛围"],
                product_consistency_rules=["保留外形"],
            ).model_dump_json(),
        )
    )
    db.commit()
    return project


def test_plan_refresh_preserves_previous_batch(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = create_project(db, tmp_path)
        workflow = ProductShotWorkflow(db)
        workflow.planner_agent = FakePlanner()

        first = workflow.generate_plans(project)
        second = workflow.generate_plans(project, "更有夏日感", ["闲鱼"], ["高级极简"])

        assert len(first) == 3
        assert len(second) == 3
        assert db.query(CreativePlan).filter(CreativePlan.project_id == project.id).count() == 6
        batches = db.query(CreativePlanBatch).filter(CreativePlanBatch.project_id == project.id).all()
        assert len(batches) == 2
        assert batches[-1].feedback == "更有夏日感"
        assert batches[-1].platforms_json == '["闲鱼"]'
        assert batches[-1].style_presets_json == '["高级极简"]'
        assert db.query(CreativePlan).filter(CreativePlan.project_id == project.id, CreativePlan.is_current.is_(True)).count() == 3


def test_plan_revision_replaces_only_that_current_direction_without_prompt(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = create_project(db, tmp_path)
        workflow = ProductShotWorkflow(db)
        workflow.planner_agent = FakePlanner()
        first = workflow.generate_plans(project)
        original = db.get(CreativePlan, first[0].id)

        revised = workflow.revise_plan(project, original, "更简洁")

        assert db.get(CreativePlan, original.id).is_current is False
        assert db.get(CreativePlan, revised.id).is_current is True
        assert db.query(CreativePlan).filter(CreativePlan.project_id == project.id, CreativePlan.is_current.is_(True)).count() == 3
        assert db.query(PromptPack).filter(PromptPack.project_id == project.id).count() == 0


def test_background_task_tracks_batches_and_reviews(monkeypatch, tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = create_project(db, tmp_path)
        batch = CreativePlanBatch(project_id=project.id, kind="initial")
        db.add(batch)
        db.flush()
        plan = CreativePlan(
            project_id=project.id,
            plan_batch_id=batch.id,
            plan_name="生活方式",
            plan_description="自然场景",
            target_platform="小红书",
            visual_style="自然",
            selling_angle="手工",
            plan_json=plan_payload("生活方式").model_dump_json(),
        )
        db.add(plan)
        db.commit()

        provider = FakeImageProvider(tmp_path)
        monkeypatch.setattr("app.services.workflow.get_image_provider", lambda: provider)
        workflow = ProductShotWorkflow(db)
        workflow.prompt_agent = FakePromptAgent()
        workflow.critic_agent = FakeCritic()

        prompt_pack = workflow.create_prompt_pack(project, plan)
        persisted_pack = db.get(PromptPack, prompt_pack.id)
        task = workflow.submit_generation_task(project, persisted_pack, 3)

        with pytest.raises(ValueError, match="正在处理"):
            workflow.submit_generation_task(project, persisted_pack, 1)

        workflow.run_generation_task(task.id)
        stored_task = db.get(GenerationTask, task.id)

        assert provider.calls == [2, 1]
        assert stored_task.status == "success"
        assert stored_task.generated_count == 3
        assert stored_task.reviewed_count == 3
        assert stored_task.progress_stage == "completed"
        assert sum(image.is_recommended for image in stored_task.images) == 1
        assert not any(image.is_selected for image in stored_task.images)
        task_detail = workflow.generation_task_detail(stored_task)
        assert len(task_detail.images) == 3
        detail = get_project(project.id, db)
        assert len(detail.creative_plan_batches) == 1
        assert detail.generation_tasks[0].generated_count == 3
        assert detail.generated_images[0].review is not None


def test_manual_copy_updates_the_current_draft(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = create_project(db, tmp_path)
        workflow = ProductShotWorkflow(db)
        payload = CopywritingPayload(
            title="初稿",
            selling_points=["质感"],
            xiaohongshu_title="初稿标题",
            xiaohongshu_text="初稿正文",
            moments_text="朋友圈",
            taobao_text="淘宝",
            xianyu_text="闲鱼描述",
            tags=["香薰"],
        )
        parent = workflow._save_copywriting(project, None, payload)
        revised = workflow.update_copywriting(project, parent, payload.model_copy(update={"title": "手改版本"}))

        assert revised.id == parent.id
        assert revised.copywriting.title == "手改版本"
        assert db.query(Copywriting).count() == 1


def test_source_must_be_confirmed_before_analysis(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = Project(product_name="香薰蜡烛", target_platform="多平台")
        db.add(project)
        db.flush()
        source = tmp_path / "source.png"
        source.write_bytes(b"source")
        db.add(ProductAsset(project_id=project.id, file_url="/uploads/source.png", file_path=str(source), file_type="image/png", is_primary=True))
        db.commit()
        workflow = ProductShotWorkflow(db)

        with pytest.raises(ValueError, match="确认商品与原图"):
            workflow.ensure_visual_analysis(project)

        workflow.confirm_source(project)
        assert project.source_confirmed_at is not None


def test_product_updates_are_rejected_after_source_confirmation(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = Project(product_name="香薰蜡烛", target_platform="多平台")
        db.add(project)
        db.commit()
        db.refresh(project)

        update_project(project.id, ProjectUpdate(product_name="香薰蜡烛（新版）"), db)
        assert project.product_name == "香薰蜡烛（新版）"

        source = tmp_path / "source.png"
        source.write_bytes(b"source")
        db.add(ProductAsset(project_id=project.id, file_url="/uploads/source.png", file_path=str(source), file_type="image/png", is_primary=True))
        db.commit()
        ProductShotWorkflow(db).confirm_source(project)

        with pytest.raises(HTTPException) as exc:
            update_project(project.id, ProjectUpdate(product_name="不应更新"), db)
        assert exc.value.status_code == 409


def test_visual_correction_uses_natural_language_and_utc_events(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = create_project(db, tmp_path)
        original = VisualAnalysisPayload(
            product_appearance="金色罐体",
            dominant_colors=["金色"],
            materials=["金属"],
            visible_text_or_logo=["品牌标志"],
            subject_clarity="清晰",
            background_issues=[],
            fidelity_constraints=["保留 Logo"],
            marketing_opportunities=["礼物"],
        )
        db.add(ProductVisualAnalysis(project_id=project.id, analysis_json=original.model_dump_json()))
        db.commit()
        workflow = ProductShotWorkflow(db)

        class CorrectingVisualAgent:
            def correct(self, _project, current, instruction, _image_path):
                return current.model_copy(update={"materials": ["玻璃"], "human_review_notes": instruction})

        workflow.visual_agent = CorrectingVisualAgent()
        corrected = workflow.correct_visual_analysis(project, "材质是玻璃")
        event = workflow.record_event(project.id, step_key="test", agent_name="test", status="success", summary="ok")

        assert corrected.analysis.materials == ["玻璃"]
        assert corrected.analysis.human_reviewed is False
        assert WorkflowEventRead.model_validate(event).model_dump(mode="json")["started_at"].endswith("Z")
