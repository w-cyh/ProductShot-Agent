from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
import pytest

from app.models import CreativePlan, CreativePlanBatch, GenerationTask, ProductAnalysis, ProductAsset, Project, PromptPack
from app.providers.image_provider import GeneratedImageFile
from app.schemas import CreativePlanPayload, ImageReviewPayload, ProductAnalysisPayload, PromptPackPayload, QualityRunCreate
from app.services.quality import QualityRunWorkflow


def plan_payload() -> CreativePlanPayload:
    return CreativePlanPayload(
        plan_name="生活方式",
        applicable_platform="小红书",
        visual_description="自然场景",
        background_scene="窗边",
        visual_style="自然",
        main_selling_point="手工质感",
        recommendation_reason="适合目标用户",
        copywriting_direction="克制分享",
    )


class FakePromptAgent:
    def run(self, _project, _plan, _analysis=None, source_instruction="", parent_prompt=None):
        suffix = source_instruction or "初始"
        return PromptPackPayload(
            positive_prompt=f"product photo {suffix}",
            negative_prompt="blur",
            size="1024x1024",
            style="editorial",
            product_consistency_notes="保持商品外形",
            platform="小红书",
            generation_mode="image_to_image",
            consistency_rules=["商品外形不变"],
        )


class FakeImageProvider:
    name = "fake"
    model = "fake-image"
    capabilities = {"text_to_image", "image_to_image"}
    max_batch_size = 4

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.calls = 0

    def generate_images(self, *, count: int, **_kwargs):
        self.calls += 1
        images = []
        for index in range(count):
            target = self.output_dir / f"quality-{self.calls}-{index}.png"
            target.write_bytes(b"png")
            images.append(GeneratedImageFile(target, f"/uploads/{target.name}", 1024, 1024))
        return images


class FakeCritic:
    def __init__(self, score: int):
        self.score = score

    def run(self, *_args, **_kwargs):
        score_on_ten = max(1, min(10, round(self.score / 10)))
        return ImageReviewPayload(
            overall_score=100,
            product_consistency=score_on_ten,
            product_clarity=score_on_ten,
            commercial_value=score_on_ten,
            text_accuracy=score_on_ten,
            defects=[] if self.score >= 70 else ["商品材质不够清晰"],
            suggestions=["提升商品主体清晰度"],
            prompt_revision="保持商品外观，提升主体清晰度。",
            summary="审核完成",
        )


class HardDefectCritic(FakeCritic):
    def run(self, *_args, **_kwargs):
        payload = super().run(*_args, **_kwargs)
        return payload.model_copy(update={"hard_defects": ["商品主体与原图不一致"]})


def create_project(db: Session, tmp_path: Path) -> tuple[Project, CreativePlan]:
    project = Project(
        product_name="香薰蜡烛",
        target_platform="多平台",
        source_confirmed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        strategy_confirmed_at=datetime.now(timezone.utc).replace(tzinfo=None),
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
        plan_json=plan_payload().model_dump_json(),
    )
    db.add(plan)
    db.commit()
    return project, plan


def configure(workflow: QualityRunWorkflow, monkeypatch, tmp_path: Path, score: int):
    monkeypatch.setattr(workflow, "ensure_runtime", lambda: None)
    monkeypatch.setattr(workflow, "_schedule", lambda _run_id: None)
    workflow.workflow.prompt_agent = FakePromptAgent()
    workflow.workflow.image_critic = FakeCritic(score)
    provider = FakeImageProvider(tmp_path)
    monkeypatch.setattr("app.services.workflow.get_image_provider", lambda: provider)
    return provider


def test_high_quality_candidate_completes_and_marks_recommendation(monkeypatch, tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project, plan = create_project(db, tmp_path)
        workflow = QualityRunWorkflow(db)
        configure(workflow, monkeypatch, tmp_path, 90)
        run = workflow.create(project, plan, QualityRunCreate(plan_id=plan.id, quality_profile="balanced", target_score=85, images_per_round=2, max_rounds=3))

        workflow.advance(run.id)
        workflow.advance(run.id)
        workflow.advance(run.id)
        db.refresh(run)

        assert run.status == "completed"
        assert run.recommended_image_id is not None
        assert run.current_round == 1
        assert workflow.detail(run).rounds[0].images[0].review is not None
        assert workflow.detail(run).rounds[0].images[0].review.review.overall_score == 90


def test_low_quality_candidate_uses_review_revision_for_next_round(monkeypatch, tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project, plan = create_project(db, tmp_path)
        workflow = QualityRunWorkflow(db)
        configure(workflow, monkeypatch, tmp_path, 65)
        run = workflow.create(project, plan, QualityRunCreate(plan_id=plan.id, target_score=85, images_per_round=1, max_rounds=2))

        workflow.advance(run.id)
        workflow.advance(run.id)
        workflow.advance(run.id)
        db.refresh(run)
        assert run.status == "refining"
        assert run.pending_revision == "保持商品外观，提升主体清晰度。"

        workflow.advance(run.id)
        db.refresh(run)
        assert run.status == "generating"
        assert run.current_round == 2
        assert workflow.detail(run).rounds[-1].prompt_pack_id is not None


def test_borderline_waits_for_human_and_stop_preserves_assets(monkeypatch, tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project, plan = create_project(db, tmp_path)
        workflow = QualityRunWorkflow(db)
        configure(workflow, monkeypatch, tmp_path, 80)
        run = workflow.create(project, plan, QualityRunCreate(plan_id=plan.id, target_score=85, images_per_round=1, max_rounds=2))

        workflow.advance(run.id)
        workflow.advance(run.id)
        workflow.advance(run.id)
        db.refresh(run)
        assert run.status == "awaiting_human"
        assert run.recommended_image_id is not None

        workflow.request_stop(run)
        db.refresh(run)
        assert run.status == "cancelled"


def test_hard_defect_never_auto_accepts_even_with_high_scores(monkeypatch, tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project, plan = create_project(db, tmp_path)
        workflow = QualityRunWorkflow(db)
        configure(workflow, monkeypatch, tmp_path, 95)
        workflow.workflow.image_critic = HardDefectCritic(95)
        run = workflow.create(project, plan, QualityRunCreate(plan_id=plan.id, target_score=85, images_per_round=1, max_rounds=1))

        workflow.advance(run.id)
        workflow.advance(run.id)
        workflow.advance(run.id)
        db.refresh(run)

        assert run.status == "awaiting_human"
        summary = workflow.detail(run).rounds[0].review_summary
        assert summary["has_hard_defect"] is True
        assert summary["is_accepted"] is False


def test_max_rounds_waits_for_human_without_exceeding_image_budget(monkeypatch, tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project, plan = create_project(db, tmp_path)
        workflow = QualityRunWorkflow(db)
        provider = configure(workflow, monkeypatch, tmp_path, 65)
        run = workflow.create(project, plan, QualityRunCreate(plan_id=plan.id, target_score=85, images_per_round=2, max_rounds=1))

        workflow.advance(run.id)
        workflow.advance(run.id)
        workflow.advance(run.id)
        db.refresh(run)

        assert run.status == "awaiting_human"
        assert workflow.detail(run).rounds[0].outcome == "max_rounds"
        assert provider.calls == 1
        assert len(workflow.detail(run).rounds[0].images) == run.total_image_budget


def test_duplicate_delivery_does_not_fail_or_repeat_a_running_generation(monkeypatch, tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project, plan = create_project(db, tmp_path)
        workflow = QualityRunWorkflow(db)
        provider = configure(workflow, monkeypatch, tmp_path, 90)
        run = workflow.create(project, plan, QualityRunCreate(plan_id=plan.id, target_score=85, images_per_round=1, max_rounds=2))

        workflow.advance(run.id)
        quality_round = workflow._current_round(run)
        assert quality_round is not None
        prompt_pack = db.get(PromptPack, quality_round.prompt_pack_id)
        assert prompt_pack is not None
        workflow.workflow.submit_generation_task(
            project,
            prompt_pack,
            1,
            quality_run_id=run.id,
            quality_round=quality_round,
            iteration=quality_round.round_number,
        )
        generation_task = db.get(GenerationTask, quality_round.generation_task_id)
        assert generation_task is not None
        generation_task.status = "running"
        db.commit()

        workflow.advance(run.id)
        db.refresh(run)
        assert run.status == "generating"
        assert provider.calls == 0


def test_stale_version_and_live_lease_do_not_advance_the_run(monkeypatch, tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project, plan = create_project(db, tmp_path)
        workflow = QualityRunWorkflow(db)
        provider = configure(workflow, monkeypatch, tmp_path, 90)
        run = workflow.create(project, plan, QualityRunCreate(plan_id=plan.id, images_per_round=1, max_rounds=2))

        workflow.advance(run.id)
        db.refresh(run)
        current_version = run.state_version

        workflow.advance(run.id, expected_state_version=current_version - 1)
        assert provider.calls == 0

        run.lease_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=1)
        db.commit()
        workflow.advance(run.id, expected_state_version=current_version)
        assert provider.calls == 0


def test_stop_before_generation_cancels_without_calling_the_provider(monkeypatch, tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project, plan = create_project(db, tmp_path)
        workflow = QualityRunWorkflow(db)
        provider = configure(workflow, monkeypatch, tmp_path, 90)
        run = workflow.create(project, plan, QualityRunCreate(plan_id=plan.id, images_per_round=1, max_rounds=2))

        workflow.advance(run.id)
        workflow.request_stop(run)
        workflow.advance(run.id)
        db.refresh(run)

        assert run.status == "cancelled"
        assert provider.calls == 0


@pytest.mark.parametrize(
    ("profile", "expected_primary", "dimensions", "expected_score"),
    [
        ("fidelity", "product_consistency", (9, 7, 8, 6), 77.5),
        ("balanced", "product_consistency", (9, 7, 8, 6), 76.5),
        ("commercial", "commercial_value", (9, 7, 8, 6), 76.0),
    ],
)
def test_server_calculates_profile_weights_without_trusting_model_total(monkeypatch, tmp_path: Path, profile, expected_primary, dimensions, expected_score):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project, plan = create_project(db, tmp_path)
        workflow = QualityRunWorkflow(db)
        configure(workflow, monkeypatch, tmp_path, 90)
        run = workflow.create(project, plan, QualityRunCreate(plan_id=plan.id, quality_profile=profile, target_score=85, images_per_round=1, max_rounds=1))
        payload = ImageReviewPayload(
            overall_score=100,
            product_consistency=dimensions[0],
            product_clarity=dimensions[1],
            commercial_value=dimensions[2],
            text_accuracy=dimensions[3],
        )

        result = workflow._score_review(run, payload)

        assert result["overall_score"] == expected_score
        assert result["primary_dimension"] == expected_primary


def test_acceptance_tiers_apply_distinct_hidden_thresholds(monkeypatch, tmp_path: Path):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project, plan = create_project(db, tmp_path)
        workflow = QualityRunWorkflow(db)
        configure(workflow, monkeypatch, tmp_path, 90)
        payload = ImageReviewPayload(
            product_consistency=8,
            product_clarity=8,
            commercial_value=8,
            text_accuracy=8,
        )
        loose = workflow.create(project, plan, QualityRunCreate(plan_id=plan.id, acceptance_tier="loose", images_per_round=1, max_rounds=1))
        assert workflow._score_review(loose, payload)["is_accepted"] is True

        loose.status = "cancelled"
        db.commit()
        strict = workflow.create(project, plan, QualityRunCreate(plan_id=plan.id, acceptance_tier="strict", images_per_round=1, max_rounds=1))
        score = workflow._score_review(strict, payload)
        assert strict.target_score == 92
        assert score["is_accepted"] is False


def test_quality_run_configuration_enforces_hard_budget():
    with pytest.raises(ValueError):
        QualityRunCreate(plan_id=1, images_per_round=4, max_rounds=6)
    assert QualityRunCreate(plan_id=1, images_per_round=4, max_rounds=5).total_image_budget == 20
    with pytest.raises(ValueError):
        QualityRunCreate(plan_id=1, target_score=69)
