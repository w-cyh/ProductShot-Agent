from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import settings
from app.models import CreativePlan, GeneratedImage, GenerationTask, ImageReview, ProductAnalysis, ProductVisualAnalysis, PromptPack, Project, QualityRound, QualityRun
from app.providers import get_text_provider
from app.providers.text_provider import ProviderConfigurationError
from app.schemas import (
    CreativePlanPayload,
    GeneratedImageRead,
    ImageReviewPayload,
    QUALITY_ACCEPTANCE_TIERS,
    QUALITY_PROFILE_PRIMARY_DIMENSION,
    QUALITY_PROFILE_WEIGHTS,
    PromptPackPayload,
    QualityRoundRead,
    QualityRunCreate,
    QualityRunDetailRead,
    QualityRunRead,
)
from app.services.workflow import ProductShotWorkflow, utcnow
from app.utils.json import dumps, loads


ACTIVE_RUN_STATUSES = {"preparing", "generating", "reviewing", "refining", "awaiting_human", "stop_requested"}
TERMINAL_RUN_STATUSES = {"completed", "cancelled", "failed"}


class QualityRuntimeUnavailable(RuntimeError):
    pass


class QualityRunWorkflow:
    """Persisted quality-gated generation loop.

    The worker advances only one state transition per delivery. Every generated
    asset, review, Prompt Pack, and decision is committed before the next task
    is queued so the run remains inspectable and safe to stop.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.workflow = ProductShotWorkflow(db)

    def ensure_runtime(self) -> None:
        if not settings.quality_runtime_ready:
            raise QualityRuntimeUnavailable("AI 审核模式需要 PostgreSQL 与 CELERY_BROKER_URL（Redis）配置完成。")
        try:
            provider = get_text_provider()
        except ProviderConfigurationError as exc:
            raise QualityRuntimeUnavailable(f"AI 审核模式需要已配置的多模态文字 Provider：{exc}") from exc
        if provider.name == "dashscope":
            missing = [
                name
                for name, value in {
                    "DASHSCOPE_API_KEY": settings.dashscope_api_key,
                    "DASHSCOPE_TEXT_MODEL": provider.model,
                    "DASHSCOPE_VISION_MODEL": provider.vision_model,
                }.items()
                if not value
            ]
            if missing:
                raise QualityRuntimeUnavailable(f"AI 审核模式缺少 DashScope 配置：{', '.join(missing)}。")
        if provider.name == "openai" and (not settings.openai_api_key or not provider.model):
            raise QualityRuntimeUnavailable("AI 审核模式需要配置 OPENAI_API_KEY 与支持视觉输入的 OPENAI_TEXT_MODEL。")

    def create(self, project: Project, plan: CreativePlan, payload: QualityRunCreate) -> QualityRun:
        self.ensure_runtime()
        self.workflow.require_confirmed_source(project)
        self.workflow.require_confirmed_strategy(project)
        if not plan.is_current:
            raise ValueError("只能对当前创意方向开启 AI 审核模式。")
        if self._has_active_generation(project.id):
            raise ValueError("该项目已有正在处理的素材任务，请等待完成或停止后再开启 AI 审核。")
        if self._has_active_run(project.id):
            raise ValueError("该项目已有未结束的 AI 审核运行，请先完成、停止或处理人工决策。")

        run = QualityRun(
            project_id=project.id,
            plan_id=plan.id,
            quality_profile=payload.quality_profile,
            acceptance_tier=payload.acceptance_tier,
            target_score=payload.resolved_target_score,
            images_per_round=payload.images_per_round,
            max_rounds=payload.max_rounds,
            total_image_budget=payload.total_image_budget,
            status="preparing",
            started_at=utcnow(),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        self.workflow.record_event(
            project.id,
            step_key="quality_run",
            agent_name="QualityRunController",
            status="queued",
            summary="AI 审核模式已启动，正在准备首轮 Prompt。",
            detail=self._run_budget_detail(run),
        )
        self._schedule(run)
        return run

    def request_stop(self, run: QualityRun) -> QualityRun:
        if run.status in TERMINAL_RUN_STATUSES:
            return run
        run.stop_requested = True
        if run.status in {"preparing", "refining", "awaiting_human"}:
            self._cancel(run, "用户停止了 AI 审核模式，已保留已有结果。")
        else:
            run.status = "stop_requested"
            run.state_version += 1
            self.db.commit()
            self.workflow.record_event(
                run.project_id,
                step_key="quality_run",
                agent_name="Human Controller",
                status="running",
                summary="已请求停止；当前模型调用完成后不会再发起下一轮。",
                detail={"quality_run_id": run.id, "status": run.status},
            )
            # Supersede any queued stale delivery. This new task can only
            # perform terminal cleanup because stop is checked before leases.
            self._schedule(run)
        return run

    def retry(self, run: QualityRun) -> QualityRun:
        if run.status != "failed":
            raise ValueError("只有失败的 AI 审核运行可以重新启动。")
        project = self.db.get(Project, run.project_id)
        plan = self.db.get(CreativePlan, run.plan_id)
        if project is None or plan is None:
            raise ValueError("项目或创意方向不存在，无法重新启动 AI 审核。")
        return self.create(
            project,
            plan,
            QualityRunCreate(
                plan_id=run.plan_id,
                quality_profile=run.quality_profile,
                acceptance_tier=run.acceptance_tier,
                target_score=run.target_score,
                images_per_round=run.images_per_round,
                max_rounds=run.max_rounds,
            ),
        )

    def decide(self, run: QualityRun, action: str) -> QualityRun:
        if run.status != "awaiting_human":
            raise ValueError("当前 AI 审核运行不需要人工决策。")
        if run.recommended_image_id is None:
            raise ValueError("当前运行没有可供决策的候选图片。")
        current_round = self._current_round(run)
        if current_round is None:
            raise ValueError("当前运行缺少轮次记录。")
        if action == "accept_recommended":
            image = self.db.get(GeneratedImage, run.recommended_image_id)
            if image is None:
                raise ValueError("推荐图片不存在。")
            self._complete(run, current_round, image, "human_accepted")
            return run
        if action != "continue":
            raise ValueError("不支持的人工决策。")
        if run.current_round >= run.max_rounds:
            raise ValueError("已达到本次 AI 审核的最大轮数，不能继续自动生成。")
        review = self._review_for_image(run.id, run.recommended_image_id)
        run.status = "refining"
        run.pending_revision = self._revision_instruction(review)
        run.state_version += 1
        current_round.status = "completed"
        current_round.outcome = "human_continue"
        self.db.commit()
        self.workflow.record_event(
            run.project_id,
            step_key="quality_run",
            agent_name="Human Controller",
            status="success",
            summary="已确认继续下一轮 AI 审核生成。",
            detail={"quality_run_id": run.id, "round": run.current_round},
        )
        self._schedule(run)
        return run

    def advance(self, run_id: int, expected_state_version: int | None = None) -> None:
        run = self.db.query(QualityRun).filter(QualityRun.id == run_id).with_for_update().first()
        if run is None or run.status in TERMINAL_RUN_STATUSES or run.status == "awaiting_human":
            return
        if expected_state_version is not None and run.state_version != expected_state_version:
            return
        if run.stop_requested or run.status == "stop_requested":
            self._cancel(run, "用户停止了 AI 审核模式，已保留已有结果。")
            return
        now = utcnow()
        if run.lease_expires_at is not None and run.lease_expires_at > now:
            return
        run.lease_token = uuid4().hex
        run.lease_expires_at = now + timedelta(seconds=max(60, int(settings.model_request_timeout) + 60))
        self.db.commit()
        self.db.refresh(run)

        project = self.db.get(Project, run.project_id)
        plan = self.db.get(CreativePlan, run.plan_id)
        if project is None or plan is None:
            self._fail(run, "项目或创意方向不存在，无法继续 AI 审核。")
            return
        try:
            if run.status in {"preparing", "refining"}:
                self._prepare_round(run, project, plan)
                return
            if run.status == "generating":
                self._generate_round(run, project)
                return
            if run.status == "reviewing":
                self._review_round(run, project, plan)
                return
            self._fail(run, f"不支持的 AI 审核运行状态：{run.status}")
        except Exception as exc:
            self._fail(run, str(exc))

    def read(self, run: QualityRun) -> QualityRunRead:
        return QualityRunRead(
            id=run.id,
            project_id=run.project_id,
            plan_id=run.plan_id,
            quality_profile=run.quality_profile,
            acceptance_tier=run.acceptance_tier,
            target_score=run.target_score,
            images_per_round=run.images_per_round,
            max_rounds=run.max_rounds,
            total_image_budget=run.total_image_budget,
            status=run.status,
            current_round=run.current_round,
            stop_requested=run.stop_requested,
            recommended_image_id=run.recommended_image_id,
            error_message=run.error_message,
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    def detail(self, run: QualityRun) -> QualityRunDetailRead:
        rounds = (
            self.db.query(QualityRound)
            .filter(QualityRound.quality_run_id == run.id)
            .order_by(QualityRound.round_number.asc(), QualityRound.id.asc())
            .all()
        )
        base = self.read(run).model_dump()
        return QualityRunDetailRead(
            **base,
            profile_weights=QUALITY_PROFILE_WEIGHTS[run.quality_profile],
            primary_dimension=QUALITY_PROFILE_PRIMARY_DIMENSION[run.quality_profile],
            remaining_rounds=max(0, run.max_rounds - run.current_round),
            max_review_calls=run.total_image_budget,
            max_prompt_revisions=max(0, run.max_rounds - 1),
            rounds=[self._round_read(item) for item in rounds],
        )

    def _prepare_round(self, run: QualityRun, project: Project, plan: CreativePlan) -> None:
        if self._cancel_if_stop_requested(run):
            return
        if run.current_round >= run.max_rounds:
            self._await_human(run, self._current_round(run), "max_rounds")
            return
        round_number = run.current_round + 1
        prior_round = self._current_round(run)
        prior_prompt = self._prompt_for_round(prior_round) if prior_round else None
        analysis = self.workflow.analysis_payload(self.workflow.latest_analysis(project.id))
        plan_payload = CreativePlanPayload.model_validate_json(plan.plan_json)
        prompt = self.workflow.prompt_agent.run(
            project,
            plan_payload,
            analysis,
            source_instruction=run.pending_revision,
            parent_prompt=prior_prompt,
        )
        if self._cancel_if_stop_requested(run):
            return
        prompt_pack = PromptPack(
            project_id=project.id,
            plan_id=plan.id,
            payload_json=prompt.model_dump_json(),
            source_instruction=run.pending_revision,
        )
        quality_round = QualityRound(
            quality_run_id=run.id,
            round_number=round_number,
            prompt_pack=prompt_pack,
            status="generating",
        )
        self.db.add_all([prompt_pack, quality_round])
        run.current_round = round_number
        run.pending_revision = ""
        run.status = "generating"
        run.state_version += 1
        self._clear_lease(run)
        self.db.commit()
        self.workflow.record_event(
            project.id,
            step_key="prompt",
            agent_name="PromptEngineerAgent",
            status="success",
            summary=f"已为 AI 审核第 {round_number} 轮构建 Prompt。",
            detail={"quality_run_id": run.id, "round": round_number, "prompt_pack_id": prompt_pack.id},
        )
        self._schedule(run)

    def _generate_round(self, run: QualityRun, project: Project) -> None:
        if self._cancel_if_stop_requested(run):
            return
        quality_round = self._current_round(run)
        if quality_round is None or quality_round.prompt_pack_id is None:
            raise RuntimeError("AI 审核轮次缺少 Prompt Pack。")
        if quality_round.generation_task_id is None:
            prompt_pack = self.db.get(PromptPack, quality_round.prompt_pack_id)
            if prompt_pack is None:
                raise RuntimeError("AI 审核 Prompt Pack 不存在。")
            self.workflow.submit_generation_task(
                project,
                prompt_pack,
                run.images_per_round,
                quality_run_id=run.id,
                quality_round=quality_round,
                iteration=quality_round.round_number,
            )
        if self._cancel_if_stop_requested(run):
            return
        task = self.db.get(GenerationTask, quality_round.generation_task_id)
        if task is None:
            raise RuntimeError("AI 审核轮次缺少生成任务。")
        if task.status == "queued":
            self.workflow.run_generation_task(task.id)
            self.db.expire_all()
            task = self.db.get(GenerationTask, task.id)
        if self._cancel_if_stop_requested(run):
            return
        # A duplicate Celery delivery may observe the task while another worker
        # is still inside the paid provider request. It must not treat that as
        # an error (or start another request); the original delivery will
        # persist success/failure and queue the next transition.
        if task is not None and task.status == "running":
            return
        if task is None or task.status == "failed":
            self._fail(run, task.error_message if task else "图片生成任务不存在。")
            return
        if task.status != "success":
            self._fail(run, "图片任务状态异常，为避免重复计费已停止 AI 审核。")
            return
        quality_round.status = "reviewing"
        run.status = "reviewing"
        run.state_version += 1
        self._clear_lease(run)
        self.db.commit()
        self.workflow.record_event(
            project.id,
            step_key="review",
            agent_name="ImageCriticAgent",
            status="running",
            summary=f"正在审核第 {quality_round.round_number} 轮图片质量。",
            detail={"quality_run_id": run.id, "round": quality_round.round_number, "task_id": task.id},
        )
        self._schedule(run)

    def _review_round(self, run: QualityRun, project: Project, plan: CreativePlan) -> None:
        if self._cancel_if_stop_requested(run):
            return
        quality_round = self._current_round(run)
        if quality_round is None or quality_round.generation_task_id is None:
            raise RuntimeError("AI 审核轮次缺少生成任务。")
        source = self.workflow.primary_asset(project.id)
        if source is None:
            raise RuntimeError("缺少商品原图，无法执行 AI 审核。")
        visual = self.workflow.visual_analysis_payload(self.workflow.latest_visual_analysis(project.id))
        plan_payload = CreativePlanPayload.model_validate_json(plan.plan_json)
        images = (
            self.db.query(GeneratedImage)
            .filter(GeneratedImage.task_id == quality_round.generation_task_id)
            .order_by(GeneratedImage.created_at.asc(), GeneratedImage.id.asc())
            .all()
        )
        if not images:
            raise RuntimeError("本轮没有可审核的生成图片。")
        for image in images:
            if self._cancel_if_stop_requested(run):
                return
            if self._review_for_image(run.id, image.id) is not None:
                continue
            review_payload = self.workflow.image_critic.run(
                project,
                image,
                plan_payload,
                visual,
                source.file_path,
            )
            if self._cancel_if_stop_requested(run):
                return
            score = self._score_review(run, review_payload)
            hard_defects = list(dict.fromkeys(score["hard_defects"]))
            review = ImageReview(
                image_id=image.id,
                quality_run_id=run.id,
                overall_score=score["overall_score"],
                product_clarity_score=review_payload.product_clarity * 10,
                product_consistency_score=review_payload.product_consistency * 10,
                # These legacy persistence columns remain populated for
                # historical compatibility; new quality decisions use the
                # four explicit dimensions below.
                style_match_score=review_payload.commercial_value * 10,
                commercial_value_score=review_payload.commercial_value * 10,
                platform_fit_score=review_payload.commercial_value * 10,
                text_accuracy_score=review_payload.text_accuracy * 10,
                text_artifact_risk=review_payload.text_artifact_risk,
                ai_artifact_risk=review_payload.ai_artifact_risk,
                recommendation_level=review_payload.recommendation_level,
                defects_json=dumps(review_payload.defects),
                suggestions_json=dumps(review_payload.suggestions),
                evidence_json=dumps([item.model_dump() for item in review_payload.evidence]),
                hard_defects_json=dumps(hard_defects),
                prompt_revision=review_payload.prompt_revision,
                summary=review_payload.summary,
            )
            image.score = score["overall_score"]
            self.db.add(review)
            self.db.commit()

        task = self.db.get(GenerationTask, quality_round.generation_task_id)
        if task is not None:
            task.reviewed_count = len(images)
        ranked = sorted(images, key=lambda item: (item.score or 0, item.id), reverse=True)
        best = ranked[0]
        best_review = self._review_for_image(run.id, best.id)
        if best_review is None:
            raise RuntimeError("最佳候选图片缺少审核结果。")
        score = self._score_review(run, self._review_payload(best_review))
        quality_round.best_image_id = best.id
        quality_round.best_score = score["overall_score"]
        quality_round.review_summary_json = dumps(score)
        run.recommended_image_id = best.id
        self.db.commit()

        if score["is_accepted"]:
            self._complete(run, quality_round, best, "accepted")
            return
        if score["is_borderline"]:
            self._await_human(run, quality_round, "borderline")
            return
        if run.current_round >= run.max_rounds:
            self._await_human(run, quality_round, "max_rounds")
            return
        quality_round.outcome = "retry"
        quality_round.status = "completed"
        run.pending_revision = self._revision_instruction(best_review)
        run.status = "refining"
        run.state_version += 1
        self._clear_lease(run)
        self.db.commit()
        self.workflow.record_event(
            project.id,
            step_key="review",
            agent_name="ImageCriticAgent",
            status="success",
            summary=f"第 {quality_round.round_number} 轮未达标，已生成定向 Prompt 修订建议。",
            detail={"quality_run_id": run.id, "round": quality_round.round_number, "best_image_id": best.id, **score},
        )
        self._schedule(run)

    def _score_review(self, run: QualityRun, payload: ImageReviewPayload) -> dict:
        dimensions = {
            "product_consistency": payload.product_consistency * 10,
            "product_clarity": payload.product_clarity * 10,
            "commercial_value": payload.commercial_value * 10,
            "text_accuracy": payload.text_accuracy * 10,
        }
        weights = QUALITY_PROFILE_WEIGHTS[run.quality_profile]
        overall_score = round(sum(dimensions[key] * weight for key, weight in weights.items()), 2)
        hard_defects = list(payload.hard_defects)
        hard_defects.extend(item.observation for item in payload.evidence if item.severity == "blocking")
        has_hard_defect = bool(hard_defects)
        primary_dimension = QUALITY_PROFILE_PRIMARY_DIMENSION[run.quality_profile]
        tier = QUALITY_ACCEPTANCE_TIERS.get(run.acceptance_tier, QUALITY_ACCEPTANCE_TIERS["standard"])
        all_dimensions_safe = all(value >= tier["minimum_dimension"] for value in dimensions.values())
        priority_safe = dimensions[primary_dimension] >= tier["primary_minimum"]
        is_accepted = not has_hard_defect and all_dimensions_safe and priority_safe and overall_score >= run.target_score
        is_borderline = (
            not has_hard_defect
            and all_dimensions_safe
            and priority_safe
            and run.target_score - 10 <= overall_score < run.target_score
        )
        return {
            "overall_score": overall_score,
            "target_score": run.target_score,
            "dimensions": dimensions,
            "primary_dimension": primary_dimension,
            "has_hard_defect": has_hard_defect,
            "hard_defects": hard_defects,
            "is_accepted": is_accepted,
            "is_borderline": is_borderline,
        }

    def _complete(self, run: QualityRun, quality_round: QualityRound, image: GeneratedImage, outcome: str) -> None:
        image.is_recommended = True
        quality_round.status = "completed"
        quality_round.outcome = outcome
        run.recommended_image_id = image.id
        run.status = "completed"
        run.completed_at = utcnow()
        run.state_version += 1
        self._clear_lease(run)
        self.db.commit()
        self.workflow.record_event(
            run.project_id,
            step_key="quality_run",
            agent_name="QualityRunController",
            status="success",
            summary=f"AI 审核完成，已推荐图片 {image.id}；交付选择仍由你决定。",
            detail={"quality_run_id": run.id, "round": quality_round.round_number, "image_id": image.id, "outcome": outcome},
        )

    def _await_human(self, run: QualityRun, quality_round: QualityRound | None, outcome: str) -> None:
        if quality_round is not None:
            quality_round.status = "awaiting_human"
            quality_round.outcome = outcome
        run.status = "awaiting_human"
        run.state_version += 1
        self._clear_lease(run)
        self.db.commit()
        self.workflow.record_event(
            run.project_id,
            step_key="quality_run",
            agent_name="QualityRunController",
            status="success",
            summary="AI 审核等待人工决策：可接受推荐候选或在预算内继续下一轮。",
            detail={"quality_run_id": run.id, "round": run.current_round, "outcome": outcome, "recommended_image_id": run.recommended_image_id},
        )

    def _cancel(self, run: QualityRun, message: str) -> None:
        if run.status in TERMINAL_RUN_STATUSES:
            return
        current_round = self._current_round(run)
        if current_round is not None and current_round.status not in {"completed", "awaiting_human"}:
            current_round.status = "cancelled"
            current_round.outcome = "stopped"
        run.stop_requested = True
        run.status = "cancelled"
        run.completed_at = utcnow()
        run.state_version += 1
        self._clear_lease(run)
        self.db.commit()
        self.workflow.record_event(
            run.project_id,
            step_key="quality_run",
            agent_name="QualityRunController",
            status="success",
            summary=message,
            detail={"quality_run_id": run.id, "round": run.current_round},
        )

    def _fail(self, run: QualityRun, message: str) -> None:
        run.status = "failed"
        run.error_message = message[:1000]
        run.completed_at = utcnow()
        run.state_version += 1
        self._clear_lease(run)
        current_round = self._current_round(run)
        if current_round is not None and current_round.status not in {"completed", "awaiting_human", "cancelled"}:
            current_round.status = "failed"
            current_round.outcome = "failed"
        self.db.commit()
        self.workflow.record_event(
            run.project_id,
            step_key="quality_run",
            agent_name="QualityRunController",
            status="failed",
            summary="AI 审核运行已停止，未自动重试外部图片调用。",
            detail={"quality_run_id": run.id, "round": run.current_round},
            error_message=message,
        )

    def _round_read(self, quality_round: QualityRound) -> QualityRoundRead:
        images: list[GeneratedImageRead] = []
        if quality_round.generation_task_id:
            rows = (
                self.db.query(GeneratedImage)
                .filter(GeneratedImage.task_id == quality_round.generation_task_id)
                .order_by(GeneratedImage.created_at.asc(), GeneratedImage.id.asc())
                .all()
            )
            images = [self.workflow.image_read(row) for row in rows]
        return QualityRoundRead(
            id=quality_round.id,
            quality_run_id=quality_round.quality_run_id,
            round_number=quality_round.round_number,
            prompt_pack_id=quality_round.prompt_pack_id,
            generation_task_id=quality_round.generation_task_id,
            best_image_id=quality_round.best_image_id,
            best_score=quality_round.best_score,
            status=quality_round.status,
            outcome=quality_round.outcome,
            review_summary=loads(quality_round.review_summary_json, {}),
            created_at=quality_round.created_at,
            updated_at=quality_round.updated_at,
            images=images,
        )

    def _current_round(self, run: QualityRun) -> QualityRound | None:
        if not run.current_round:
            return None
        return (
            self.db.query(QualityRound)
            .filter(QualityRound.quality_run_id == run.id, QualityRound.round_number == run.current_round)
            .order_by(QualityRound.id.desc())
            .first()
        )

    def _prompt_for_round(self, quality_round: QualityRound | None) -> PromptPackPayload | None:
        if quality_round is None or quality_round.prompt_pack_id is None:
            return None
        row = self.db.get(PromptPack, quality_round.prompt_pack_id)
        return PromptPackPayload.model_validate_json(row.payload_json) if row else None

    def _review_for_image(self, run_id: int, image_id: int) -> ImageReview | None:
        return (
            self.db.query(ImageReview)
            .filter(ImageReview.quality_run_id == run_id, ImageReview.image_id == image_id)
            .order_by(ImageReview.id.desc())
            .first()
        )

    def _review_payload(self, review: ImageReview) -> ImageReviewPayload:
        return self.workflow.image_review_read(review).review

    def _revision_instruction(self, review: ImageReview | None) -> str:
        if review is None:
            return "保持商品原图关键外观不变，提升商品清晰度与商业展示效果。"
        payload = self._review_payload(review)
        if payload.prompt_revision.strip():
            return payload.prompt_revision.strip()
        return "；".join(payload.suggestions) or "保持商品原图关键外观不变，修复审核发现的问题。"

    def _cancel_if_stop_requested(self, run: QualityRun) -> bool:
        """Observe a stop request committed by another API transaction."""
        self.db.refresh(run)
        if run.status in TERMINAL_RUN_STATUSES:
            return True
        if run.stop_requested or run.status == "stop_requested":
            self._cancel(run, "用户停止了 AI 审核模式，已保留当前轮次图片。")
            return True
        return False

    def _has_active_generation(self, project_id: int) -> bool:
        return (
            self.db.query(GenerationTask.id)
            .filter(GenerationTask.project_id == project_id, GenerationTask.status.in_(["queued", "running"]))
            .first()
            is not None
        )

    def _has_active_run(self, project_id: int) -> bool:
        return (
            self.db.query(QualityRun.id)
            .filter(QualityRun.project_id == project_id, QualityRun.status.in_(ACTIVE_RUN_STATUSES))
            .first()
            is not None
        )

    def _run_budget_detail(self, run: QualityRun) -> dict:
        return {
            "quality_run_id": run.id,
            "quality_profile": run.quality_profile,
            "acceptance_tier": run.acceptance_tier,
            "target_score": run.target_score,
            "images_per_round": run.images_per_round,
            "max_rounds": run.max_rounds,
            "max_images": run.total_image_budget,
            "max_review_calls": run.total_image_budget,
            "max_prompt_revisions": max(0, run.max_rounds - 1),
        }

    def _clear_lease(self, run: QualityRun) -> None:
        run.lease_token = None
        run.lease_expires_at = None

    def _schedule(self, run: QualityRun) -> None:
        from app.tasks import advance_quality_run

        advance_quality_run.delay(run.id, run.state_version)
