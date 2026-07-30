from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.agents import (
    CopywritingAgent,
    CreativePlannerAgent,
    ImageCriticAgent,
    ProductAnalysisAgent,
    PromptEngineerAgent,
    VisualAnalysisAgent,
)
from app.models import (
    Copywriting,
    CreativePlan,
    CreativePlanBatch,
    GeneratedImage,
    GenerationTask,
    ImageReview,
    ProductAnalysis,
    ProductAsset,
    ProductVisualAnalysis,
    PromptPack,
    Project,
    QualityRun,
    QualityRound,
    WorkflowEvent,
)
from app.database import SessionLocal
from app.providers import get_image_provider, get_text_provider
from app.schemas import (
    CopywritingPayload,
    CopywritingRead,
    CreativePlanPayload,
    CreativePlanRead,
    CreativePlanBatchRead,
    GenerationTaskDetailRead,
    GeneratedImageRead,
    GeneratedImagesResponse,
    GenerationTaskRead,
    ImageReviewPayload,
    ImageReviewRead,
    ProductAnalysisPayload,
    ProductAnalysisRead,
    ProductVisualAnalysisRead,
    PromptPackPayload,
    PromptPackRead,
    VisualAnalysisPayload,
    WorkflowEventRead,
)
from app.utils.json import dumps, loads


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class LazyTextProvider:
    """Defers provider validation until an agent actually requests an LLM response."""

    name = "configured-provider"
    model = ""

    def generate_json(self, **kwargs):
        return get_text_provider().generate_json(**kwargs)

    def generate_multimodal_json(self, **kwargs):
        return get_text_provider().generate_multimodal_json(**kwargs)


def mark_interrupted_generation_tasks() -> None:
    """Fail only legacy in-process tasks after an API restart.

    Quality-run tasks are owned by the Celery worker and remain recoverable.
    """
    with SessionLocal() as db:
        rows = (
            db.query(GenerationTask)
            .filter(GenerationTask.status.in_(["queued", "running"]), GenerationTask.quality_run_id.is_(None))
            .all()
        )
        if not rows:
            return
        now = utcnow()
        for row in rows:
            row.status = "failed"
            row.progress_stage = "failed"
            row.completed_at = now
            row.error_message = "应用重启导致任务中断，可使用原 Prompt Pack 重试。"
        db.commit()


class ProductShotWorkflow:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.text_provider = LazyTextProvider()
        self.visual_agent = VisualAnalysisAgent(self.text_provider)
        self.analysis_agent = ProductAnalysisAgent(self.text_provider)
        self.planner_agent = CreativePlannerAgent(self.text_provider)
        self.prompt_agent = PromptEngineerAgent(self.text_provider)
        self.image_critic = ImageCriticAgent(self.text_provider)
        self.copywriting_agent = CopywritingAgent(self.text_provider)

    def confirm_source(self, project: Project) -> None:
        if project.source_confirmed_at is not None:
            return
        if self.primary_asset(project.id) is None:
            raise ValueError("请先上传商品原图后再确认。")
        project.source_confirmed_at = utcnow()
        project.status = "source_confirmed"
        self.db.commit()
        self.record_event(
            project.id,
            step_key="source",
            agent_name="Human Reviewer",
            status="success",
            summary="已确认商品信息与原图，后续内容将以此为准。",
        )

    def require_confirmed_source(self, project: Project) -> None:
        if project.source_confirmed_at is None:
            raise ValueError("请先确认商品与原图，再进入后续流程。")

    def ensure_visual_analysis(self, project: Project) -> ProductVisualAnalysisRead:
        self.require_confirmed_source(project)
        existing = self.latest_visual_analysis(project.id)
        if existing is not None:
            return self.visual_analysis_read(existing)

        started_at = utcnow()
        primary = self.primary_asset(project.id)
        try:
            payload = self.visual_agent.run(project, primary.file_path if primary else None)
            row = ProductVisualAnalysis(project_id=project.id, analysis_json=payload.model_dump_json())
            project.status = "visual_review"
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
            self.record_event(
                project.id,
                step_key="visual_analysis",
                agent_name="VisualAnalysisAgent",
                status="success",
                summary="完成原图视觉理解和商品保真约束提取。",
                detail=payload.model_dump(),
                started_at=started_at,
            )
            return self.visual_analysis_read(row)
        except Exception as exc:
            self.record_event(
                project.id,
                step_key="visual_analysis",
                agent_name="VisualAnalysisAgent",
                status="failed",
                summary="原图视觉理解失败。",
                detail={"has_primary_asset": bool(primary)},
                error_message=str(exc),
                started_at=started_at,
            )
            raise

    def correct_visual_analysis(
        self,
        project: Project,
        instruction: str,
    ) -> ProductVisualAnalysisRead:
        self.require_confirmed_source(project)
        row = self.latest_visual_analysis(project.id)
        if row is None:
            raise ValueError("请先完成原图理解后再提交纠正。")

        current = VisualAnalysisPayload.model_validate_json(row.analysis_json)
        primary = self.primary_asset(project.id)
        payload = self.visual_agent.correct(
            project,
            current,
            instruction,
            primary.file_path if primary else None,
        )
        row.analysis_json = payload.model_dump_json()
        project.status = "visual_review"
        self.db.commit()
        self.db.refresh(row)
        self.record_event(
            project.id,
            step_key="visual_review",
            agent_name="VisualAnalysisAgent",
            status="success",
            summary="已根据自然语言意见更新原图理解。",
            detail={
                "instruction": instruction.strip(),
                "product_appearance": payload.product_appearance,
                "fidelity_constraints": payload.fidelity_constraints,
            },
        )
        return self.visual_analysis_read(row)

    def confirm_visual_analysis(self, project: Project) -> ProductVisualAnalysisRead:
        self.require_confirmed_source(project)
        row = self.latest_visual_analysis(project.id)
        if row is None:
            raise ValueError("请先完成原图理解后再确认。")
        current = VisualAnalysisPayload.model_validate_json(row.analysis_json)
        payload = current.model_copy(update={"human_reviewed": True})
        row.analysis_json = payload.model_dump_json()
        project.status = "visual_reviewed"
        self.db.commit()
        self.db.refresh(row)
        self.record_event(
            project.id,
            step_key="visual_review",
            agent_name="Human Reviewer",
            status="success",
            summary="已确认原图理解，可继续生成商品策略。",
            detail={"fidelity_constraints": payload.fidelity_constraints},
        )
        return self.visual_analysis_read(row)

    def analyze(self, project: Project) -> ProductAnalysisRead:
        self.require_confirmed_source(project)
        if project.strategy_confirmed_at is not None:
            raise ValueError("商品策略已经确认，不能再修改。")
        started_at = utcnow()
        primary = self.primary_asset(project.id)
        visual_row = self.latest_visual_analysis(project.id)
        if visual_row is None:
            raise ValueError("请先完成原图理解并确认。")
        visual_read = self.visual_analysis_read(visual_row)
        if not visual_read.analysis.human_reviewed:
            raise ValueError("请先确认原图理解，再生成商品策略。")
        try:
            payload = self.analysis_agent.run(project, primary.file_path if primary else None, visual_read.analysis)
            row = ProductAnalysis(project_id=project.id, analysis_json=payload.model_dump_json())
            project.status = "analyzed"
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
            self.record_event(
                project.id,
                step_key="analysis",
                agent_name="ProductAnalysisAgent",
                status="success",
                summary=f"识别为 {payload.product_type}，提炼 {len(payload.recommended_selling_points)} 个推荐卖点。",
                detail={
                    "product_type": payload.product_type,
                    "recommended_selling_points": payload.recommended_selling_points,
                    "image_issues": payload.image_issues,
                },
                started_at=started_at,
            )
            return self.analysis_read(row)
        except Exception as exc:
            self.record_event(
                project.id,
                step_key="analysis",
                agent_name="ProductAnalysisAgent",
                status="failed",
                summary="商品分析失败。",
                detail={"has_primary_asset": bool(primary)},
                error_message=str(exc),
                started_at=started_at,
            )
            raise

    def correct_analysis(self, project: Project, instruction: str) -> ProductAnalysisRead:
        self.require_confirmed_source(project)
        if project.strategy_confirmed_at is not None:
            raise ValueError("商品策略已经确认，不能再修改。")
        row = self.latest_analysis(project.id)
        if row is None:
            raise ValueError("请先生成商品策略后再提交纠正。")
        current = ProductAnalysisPayload.model_validate_json(row.analysis_json)
        visual = self.visual_analysis_payload(self.latest_visual_analysis(project.id))
        started_at = utcnow()
        try:
            payload = self.analysis_agent.correct(project, current, instruction, visual)
            row.analysis_json = payload.model_dump_json()
            self.db.commit()
            self.db.refresh(row)
            self.record_event(
                project.id,
                step_key="analysis",
                agent_name="ProductAnalysisAgent",
                status="success",
                summary="已根据自然语言说明更新商品策略。",
                detail={"instruction": instruction.strip()},
                started_at=started_at,
            )
            return self.analysis_read(row)
        except Exception as exc:
            self.record_event(
                project.id,
                step_key="analysis",
                agent_name="ProductAnalysisAgent",
                status="failed",
                summary="商品策略纠正失败。",
                detail={"instruction": instruction.strip()},
                error_message=str(exc),
                started_at=started_at,
            )
            raise

    def confirm_analysis(self, project: Project) -> ProductAnalysisRead:
        self.require_confirmed_source(project)
        row = self.latest_analysis(project.id)
        if row is None:
            raise ValueError("请先生成商品策略后再确认。")
        if project.strategy_confirmed_at is None:
            project.strategy_confirmed_at = utcnow()
            project.status = "strategy_confirmed"
            self.db.commit()
            self.record_event(
                project.id,
                step_key="analysis",
                agent_name="Human Reviewer",
                status="success",
                summary="已确认商品策略，可继续生成创意方向。",
            )
        return self.analysis_read(row)

    def require_confirmed_strategy(self, project: Project) -> None:
        if project.strategy_confirmed_at is None:
            raise ValueError("请先确认商品策略，再生成创意方向。")

    def generate_plans(
        self,
        project: Project,
        feedback: str = "",
        platforms: list[str] | None = None,
        style_presets: list[str] | None = None,
    ) -> list[CreativePlanRead]:
        self.require_confirmed_source(project)
        self.require_confirmed_strategy(project)
        started_at = utcnow()
        analysis = self.latest_analysis(project.id)
        if analysis is None:
            raise ValueError("请先确认原图理解并生成商品策略。")
        analysis_payload = ProductAnalysisPayload.model_validate_json(analysis.analysis_json)
        platforms = platforms or []
        style_presets = style_presets or []

        try:
            has_existing = self.db.query(CreativePlan.id).filter(CreativePlan.project_id == project.id).first() is not None
            batch = CreativePlanBatch(
                project_id=project.id,
                kind="refresh" if has_existing else "initial",
                feedback=feedback.strip(),
                platforms_json=dumps(platforms),
                style_presets_json=dumps(style_presets),
            )
            self.db.add(batch)
            self.db.flush()

            self.db.query(CreativePlan).filter(CreativePlan.project_id == project.id, CreativePlan.is_current.is_(True)).update(
                {CreativePlan.is_current: False}
            )
            payloads = self.planner_agent.run(
                project,
                analysis_payload,
                feedback=feedback,
                platforms=platforms,
                style_presets=style_presets,
            )
            rows: list[CreativePlan] = []
            for display_order, payload in enumerate(payloads):
                row = self._creative_plan_row(project.id, payload, batch_id=batch.id, display_order=display_order)
                self.db.add(row)
                rows.append(row)
            project.status = "planned"
            self.db.commit()
            self.record_event(
                project.id,
                step_key="plans",
                agent_name="CreativePlannerAgent",
                status="success",
                summary=f"生成 {len(payloads)} 个创意方向。",
                detail={
                    "batch_id": batch.id,
                    "feedback": feedback.strip(),
                    "platforms": platforms,
                    "style_presets": style_presets,
                    "plans": [payload.plan_name for payload in payloads],
                },
                started_at=started_at,
            )
            return [self.creative_plan_read(row) for row in rows]
        except Exception as exc:
            self.record_event(
                project.id,
                step_key="plans",
                agent_name="CreativePlannerAgent",
                status="failed",
                summary="创意方案生成失败。",
                detail={"analysis_product_type": analysis_payload.product_type},
                error_message=str(exc),
                started_at=started_at,
            )
            raise

    def revise_plan(self, project: Project, plan: CreativePlan, instruction: str) -> CreativePlanRead:
        self.require_confirmed_source(project)
        if not plan.is_current:
            raise ValueError("只能修改当前创意方向。")
        started_at = utcnow()
        analysis = self.latest_analysis(project.id)
        if analysis is None:
            raise ValueError("请先生成商品策略。")
        analysis_payload = ProductAnalysisPayload.model_validate_json(analysis.analysis_json)
        source_payload = CreativePlanPayload.model_validate_json(plan.plan_json)
        try:
            payload = self.planner_agent.revise(project, analysis_payload, source_payload, instruction)
            batch = CreativePlanBatch(
                project_id=project.id,
                kind="revision",
                feedback=instruction.strip(),
                platforms_json=plan.batch.platforms_json if plan.batch else "[]",
                style_presets_json=plan.batch.style_presets_json if plan.batch else "[]",
                source_plan_id=plan.id,
            )
            self.db.add(batch)
            self.db.flush()
            plan.is_current = False
            row = self._creative_plan_row(
                project.id,
                payload,
                batch_id=batch.id,
                parent_plan_id=plan.id,
                version=plan.version + 1,
                display_order=plan.display_order,
                is_current=True,
            )
            self.db.add(row)
            project.status = "planned"
            self.db.commit()
            self.db.refresh(row)
            self.record_event(
                project.id,
                step_key="plans",
                agent_name="CreativePlannerAgent",
                status="success",
                summary=f"已基于“{plan.plan_name}”生成方向修改版本。",
                detail={"source_plan_id": plan.id, "plan_id": row.id, "instruction": instruction.strip()},
                started_at=started_at,
            )
            return self.creative_plan_read(row)
        except Exception as exc:
            self.record_event(
                project.id,
                step_key="plans",
                agent_name="CreativePlannerAgent",
                status="failed",
                summary="创意方向修改失败。",
                detail={"source_plan_id": plan.id, "instruction": instruction.strip()},
                error_message=str(exc),
                started_at=started_at,
            )
            raise

    def create_prompt_pack(
        self,
        project: Project,
        plan: CreativePlan,
        *,
        parent_image: GeneratedImage | None = None,
        instruction: str = "",
    ) -> PromptPackRead:
        self.require_confirmed_source(project)
        if parent_image is None and not plan.is_current:
            raise ValueError("请先选择当前创意方向再生成图片。")
        started_at = utcnow()
        payload = CreativePlanPayload.model_validate_json(plan.plan_json)
        analysis_row = self.latest_analysis(project.id)
        analysis_payload = ProductAnalysisPayload.model_validate_json(analysis_row.analysis_json) if analysis_row else None
        parent_prompt = None
        if parent_image and parent_image.task and parent_image.task.prompt_pack:
            parent_prompt = PromptPackPayload.model_validate_json(parent_image.task.prompt_pack.payload_json)
        elif parent_image and parent_image.prompt_pack_json:
            parent_prompt = PromptPackPayload.model_validate_json(parent_image.prompt_pack_json)
        try:
            prompt = self.prompt_agent.run(
                project,
                payload,
                analysis_payload,
                source_instruction=instruction,
                parent_prompt=parent_prompt,
            )
            row = PromptPack(
                project_id=project.id,
                plan_id=plan.id,
                parent_image_id=parent_image.id if parent_image else None,
                payload_json=prompt.model_dump_json(),
                source_instruction=instruction.strip(),
            )
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
            self.record_event(
                project.id,
                step_key="prompt",
                agent_name="PromptEngineerAgent",
                status="success",
                summary=f"构建 {prompt.size} 的图片生成 Prompt。",
                detail={
                    "prompt_pack_id": row.id,
                    "plan_name": payload.plan_name,
                    "parent_image_id": parent_image.id if parent_image else None,
                    "instruction": instruction.strip(),
                    "size": prompt.size,
                    "style": prompt.style,
                    "positive_prompt": prompt.positive_prompt,
                    "negative_prompt": prompt.negative_prompt,
                    "generation_mode": prompt.generation_mode,
                    "reference_strength": prompt.reference_strength,
                },
                started_at=started_at,
            )
            return self.prompt_pack_read(row)
        except Exception as exc:
            self.record_event(
                project.id,
                step_key="prompt",
                agent_name="PromptEngineerAgent",
                status="failed",
                summary="Prompt 构建失败。",
                detail={"plan_name": payload.plan_name, "parent_image_id": parent_image.id if parent_image else None},
                error_message=str(exc),
                started_at=started_at,
            )
            raise

    def submit_generation_task(
        self,
        project: Project,
        prompt_pack: PromptPack,
        count: int,
        *,
        quality_run_id: int | None = None,
        quality_round: QualityRound | None = None,
        iteration: int | None = None,
    ) -> GenerationTaskRead:
        self.require_confirmed_source(project)
        provider = get_image_provider()
        provider_model = getattr(provider, "model", provider.name)
        active = (
            self.db.query(GenerationTask.id)
            .filter(GenerationTask.project_id == project.id, GenerationTask.status.in_(["queued", "running"]))
            .first()
        )
        if active:
            raise ValueError("该项目已有正在处理的素材任务，请等待完成或失败后再提交。")
        if quality_run_id is None:
            active_quality_run = (
                self.db.query(QualityRun.id)
                .filter(
                    QualityRun.project_id == project.id,
                    QualityRun.status.in_(["preparing", "generating", "reviewing", "refining", "awaiting_human", "stop_requested"]),
                )
                .first()
            )
            if active_quality_run:
                raise ValueError("该项目已有未结束的 AI 审核运行，请先完成、停止或处理人工决策。")
        prompt = PromptPackPayload.model_validate_json(prompt_pack.payload_json)
        parent_image = self.db.get(GeneratedImage, prompt_pack.parent_image_id) if prompt_pack.parent_image_id else None
        task_iteration = iteration or ((parent_image.task.iteration + 1) if parent_image and parent_image.task else 1)
        task = GenerationTask(
            project_id=project.id,
            plan_id=prompt_pack.plan_id,
            prompt_pack_id=prompt_pack.id,
            parent_image_id=parent_image.id if parent_image else None,
            iteration=task_iteration,
            quality_run_id=quality_run_id,
            requested_count=count,
            generated_count=0,
            reviewed_count=0,
            progress_stage="queued",
            prompt=prompt.positive_prompt,
            negative_prompt=prompt.negative_prompt,
            model_name=provider_model,
            status="queued",
        )
        self.db.add(task)
        try:
            self.db.flush()
            if quality_round is not None:
                quality_round.generation_task_id = task.id
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("该项目已有正在处理的素材任务，请等待完成或失败后再提交。") from exc
        self.db.refresh(task)
        self.record_event(
            project.id,
            step_key="images",
            agent_name=f"{provider.name} ImageProvider",
            status="queued",
            summary="素材任务已提交，等待后台出图。",
            detail={
                "task_id": task.id,
                "plan_id": prompt_pack.plan_id,
                "prompt_pack_id": prompt_pack.id,
                "parent_image_id": task.parent_image_id,
                "iteration": task.iteration,
                "model_name": provider_model,
                "requested_count": count,
                "generation_mode": prompt.generation_mode,
                "size": prompt.size,
                "quality_run_id": quality_run_id,
            },
            started_at=utcnow(),
        )
        return self.task_read(task)

    def run_generation_task(self, task_id: int) -> None:
        task = self.db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
        if task is None or task.status != "queued":
            return
        project = self.db.get(Project, task.project_id)
        prompt_pack = self.db.get(PromptPack, task.prompt_pack_id) if task.prompt_pack_id else None
        plan = self.db.get(CreativePlan, task.plan_id) if task.plan_id else None
        if project is None or prompt_pack is None or plan is None:
            return
        prompt = PromptPackPayload.model_validate_json(prompt_pack.payload_json)
        provider = get_image_provider()
        started_at = utcnow()
        task.status = "running"
        task.progress_stage = "generating"
        task.started_at = task.started_at or started_at
        task.error_message = None
        self.db.commit()
        self.record_event(
            project.id,
            step_key="images",
            agent_name=f"{provider.name} ImageProvider",
            status="running",
            summary="图片服务已接单，正在生成素材。",
            detail={"task_id": task.id, "requested_count": task.requested_count, "iteration": task.iteration},
            started_at=started_at,
        )
        try:
            source_image = self.db.get(GeneratedImage, task.parent_image_id) if task.parent_image_id else None
            primary = self.primary_asset(project.id)
            source_path = source_image.image_path if source_image else (primary.file_path if primary else None)
            capabilities = getattr(provider, "capabilities", {"text_to_image"})
            if source_path and "image_to_image" not in capabilities:
                raise RuntimeError("当前图片模型不支持参考图生成，请在模型设置中更换支持参考图的模型。")

            batch_size = max(1, int(getattr(provider, "max_batch_size", 4)))
            remaining = task.requested_count
            created: list[GeneratedImage] = []
            while remaining > 0:
                generated = provider.generate_images(
                    project_id=project.id,
                    source_image_path=source_path,
                    positive_prompt=prompt.positive_prompt,
                    negative_prompt=prompt.negative_prompt,
                    size=prompt.size,
                    count=min(remaining, batch_size),
                )
                rows = [
                    GeneratedImage(
                        task_id=task.id,
                        project_id=project.id,
                        plan_id=plan.id,
                        platform=prompt.platform,
                        generation_mode=prompt.generation_mode,
                        prompt_pack_id=str(prompt_pack.id),
                        prompt_pack_json=prompt.model_dump_json(),
                        image_url=item.image_url,
                        image_path=str(item.image_path),
                        width=item.width,
                        height=item.height,
                    )
                    for item in generated
                ]
                self.db.add_all(rows)
                self.db.flush()
                created.extend(rows)
                task.generated_count += len(rows)
                remaining -= len(rows)
                if not rows:
                    raise RuntimeError("图片服务没有返回素材，请重试或检查图片模型配置。")
                self.db.commit()

            task.status = "success"
            task.progress_stage = "completed"
            task.completed_at = utcnow()
            project.status = "generated"
            self.db.commit()
            self.record_event(
                project.id,
                step_key="images",
                agent_name=f"{provider.name} ImageProvider",
                status="success",
                summary=f"素材任务完成，生成 {task.generated_count} 张图片。",
                detail={"task_id": task.id, "image_ids": [image.id for image in created], "count": task.generated_count},
                started_at=started_at,
            )
        except Exception as exc:
            task.status = "failed"
            task.progress_stage = "failed"
            task.completed_at = utcnow()
            task.error_message = self.task_error_message(exc)
            self.db.commit()
            self.record_event(
                project.id,
                step_key="images",
                agent_name=f"{provider.name} ImageProvider",
                status="failed",
                summary="图片生成失败。",
                detail={"task_id": task.id, "plan_id": plan.id, "model_name": getattr(provider, "model", provider.name)},
                error_message=str(exc),
                started_at=started_at,
            )
            return

    def run_generation_task_in_background(self, task_id: int) -> None:
        with SessionLocal() as background_db:
            ProductShotWorkflow(background_db).run_generation_task(task_id)

    def generation_task_detail(self, task: GenerationTask) -> GenerationTaskDetailRead:
        prompt_pack = self.db.get(PromptPack, task.prompt_pack_id) if task.prompt_pack_id else None
        images = (
            self.db.query(GeneratedImage)
            .filter(GeneratedImage.task_id == task.id)
            .order_by(GeneratedImage.created_at.asc(), GeneratedImage.id.asc())
            .all()
        )
        return GenerationTaskDetailRead(
            task=self.task_read(task),
            prompt_pack=self.prompt_pack_read(prompt_pack) if prompt_pack else None,
            images=[self.image_read(image) for image in images],
        )

    def retry_generation_task(self, project: Project, task: GenerationTask) -> GenerationTaskRead:
        if task.status != "failed" or not task.prompt_pack_id:
            raise ValueError("只有失败且保留 Prompt Pack 的任务可以重试。")
        prompt_pack = self.db.get(PromptPack, task.prompt_pack_id)
        if prompt_pack is None:
            raise ValueError("原 Prompt Pack 不存在，无法重试。")
        return self.submit_generation_task(project, prompt_pack, task.requested_count)

    def generate_images(self, project: Project, plan: CreativePlan, count: int) -> GeneratedImagesResponse:
        """Compatibility path for the legacy synchronous API."""
        prompt_pack = self.create_prompt_pack(project, plan)
        pack = self.db.get(PromptPack, prompt_pack.id)
        if pack is None:
            raise RuntimeError("Prompt Pack 创建失败。")
        task_read = self.submit_generation_task(project, pack, count)
        self.run_generation_task(task_read.id)
        task = self.db.get(GenerationTask, task_read.id)
        if task is None or task.status == "failed":
            raise RuntimeError(task.error_message if task else "素材任务不存在")
        images = self.db.query(GeneratedImage).filter(GeneratedImage.task_id == task.id).all()
        return GeneratedImagesResponse(
            task=self.task_read(task),
            prompt=prompt_pack.prompt,
            images=[self.image_read(image) for image in images],
        )

    def generate_pack(self, project: Project, plan: CreativePlan, count: int) -> GeneratedImagesResponse:
        return self.generate_images(project, plan, count)

    def create_copywriting(self, project: Project, image: GeneratedImage | None) -> CopywritingRead:
        self.require_confirmed_source(project)
        started_at = utcnow()
        plan = image.task.plan if image and image.task else self.latest_plan(project.id)
        if plan is None:
            raise ValueError("请先生成创意方案")
        plan_payload = CreativePlanPayload.model_validate_json(plan.plan_json)
        try:
            payload = self.copywriting_agent.run(project, plan_payload)
            row = self._save_copywriting(project, image.id if image else None, payload)
            self.record_event(
                project.id,
                step_key="copy",
                agent_name="CopywritingAgent",
                status="success",
                summary=f"生成标题和 {len(payload.tags)} 个标签。",
                detail={"title": payload.title, "tags": payload.tags, "image_id": image.id if image else None},
                started_at=started_at,
            )
            return self.copywriting_read(row)
        except Exception as exc:
            self.record_event(
                project.id,
                step_key="copy",
                agent_name="CopywritingAgent",
                status="failed",
                summary="文案生成失败。",
                detail={"image_id": image.id if image else None},
                error_message=str(exc),
                started_at=started_at,
            )
            raise

    def update_copywriting(
        self,
        project: Project,
        current: Copywriting,
        payload: CopywritingPayload,
    ) -> CopywritingRead:
        self.require_confirmed_source(project)
        self._apply_copywriting_payload(current, payload)
        project.status = "copywritten"
        self.db.commit()
        self.db.refresh(current)
        self.record_event(
            project.id,
            step_key="copy",
            agent_name="Human Copy Editor",
            status="success",
            summary="已自动保存当前文案。",
            detail={"copywriting_id": current.id},
        )
        return self.copywriting_read(current)

    def rewrite_copywriting(self, project: Project, current: Copywriting, instruction: str) -> CopywritingRead:
        self.require_confirmed_source(project)
        started_at = utcnow()
        try:
            payload = self.copywriting_agent.rewrite(project, self.copywriting_payload(current), instruction)
            self._apply_copywriting_payload(current, payload)
            project.status = "copywritten"
            self.db.commit()
            self.db.refresh(current)
            self.record_event(
                project.id,
                step_key="copy",
                agent_name="CopywritingAgent",
                status="success",
                summary="已根据修改要求更新当前文案。",
                detail={"copywriting_id": current.id, "instruction": instruction.strip()},
                started_at=started_at,
            )
            return self.copywriting_read(current)
        except Exception as exc:
            self.record_event(
                project.id,
                step_key="copy",
                agent_name="CopywritingAgent",
                status="failed",
                summary="文案改写失败。",
                detail={"copywriting_id": current.id, "instruction": instruction.strip()},
                error_message=str(exc),
                started_at=started_at,
            )
            raise

    def select_image(self, project: Project, image: GeneratedImage) -> GeneratedImageRead:
        self.db.query(GeneratedImage).filter(GeneratedImage.project_id == project.id).update({GeneratedImage.is_selected: False})
        image.is_selected = True
        self.db.commit()
        self.db.refresh(image)
        self.record_event(
            project.id,
            step_key="images",
            agent_name="Human Selector",
            status="success",
            summary=f"已将图片 {image.id} 设为交付候选图。",
            detail={"image_id": image.id},
        )
        return self.image_read(image)

    def workflow_event_read(self, row: WorkflowEvent) -> WorkflowEventRead:
        return WorkflowEventRead.model_validate(row)

    def record_event(
        self,
        project_id: int,
        *,
        step_key: str,
        agent_name: str,
        status: str,
        summary: str,
        detail: dict | None = None,
        error_message: str | None = None,
        started_at: datetime | None = None,
    ) -> WorkflowEvent:
        started = started_at or utcnow()
        ended = utcnow()
        row = WorkflowEvent(
            project_id=project_id,
            step_key=step_key,
            agent_name=agent_name,
            status=status,
            summary=summary[:300],
            detail_json=dumps(detail or {}),
            error_message=error_message,
            started_at=started,
            ended_at=ended,
            latency_ms=max(0, int((ended - started).total_seconds() * 1000)),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def primary_asset(self, project_id: int) -> ProductAsset | None:
        return (
            self.db.query(ProductAsset)
            .filter(ProductAsset.project_id == project_id)
            .order_by(ProductAsset.is_primary.desc(), ProductAsset.id.asc())
            .first()
        )

    def latest_analysis(self, project_id: int) -> ProductAnalysis | None:
        return (
            self.db.query(ProductAnalysis)
            .filter(ProductAnalysis.project_id == project_id)
            .order_by(ProductAnalysis.created_at.desc())
            .first()
        )

    def latest_visual_analysis(self, project_id: int) -> ProductVisualAnalysis | None:
        return (
            self.db.query(ProductVisualAnalysis)
            .filter(ProductVisualAnalysis.project_id == project_id)
            .order_by(ProductVisualAnalysis.created_at.desc())
            .first()
        )

    def latest_plan(self, project_id: int) -> CreativePlan | None:
        return (
            self.db.query(CreativePlan)
            .filter(CreativePlan.project_id == project_id, CreativePlan.is_current.is_(True))
            .order_by(CreativePlan.created_at.desc())
            .first()
        )

    def analysis_payload(self, row: ProductAnalysis | None) -> ProductAnalysisPayload | None:
        if row is None:
            return None
        return ProductAnalysisPayload.model_validate_json(row.analysis_json)

    def visual_analysis_payload(self, row: ProductVisualAnalysis | None) -> VisualAnalysisPayload | None:
        if row is None:
            return None
        return VisualAnalysisPayload.model_validate_json(row.analysis_json)

    def visual_analysis_read(self, row: ProductVisualAnalysis) -> ProductVisualAnalysisRead:
        return ProductVisualAnalysisRead(
            id=row.id,
            project_id=row.project_id,
            analysis=VisualAnalysisPayload.model_validate_json(row.analysis_json),
            created_at=row.created_at,
        )

    def analysis_read(self, row: ProductAnalysis) -> ProductAnalysisRead:
        return ProductAnalysisRead(
            id=row.id,
            project_id=row.project_id,
            analysis=ProductAnalysisPayload.model_validate_json(row.analysis_json),
            created_at=row.created_at,
        )

    def creative_plan_read(self, row: CreativePlan) -> CreativePlanRead:
        return CreativePlanRead(
            id=row.id,
            project_id=row.project_id,
            plan_batch_id=row.plan_batch_id,
            parent_plan_id=row.parent_plan_id,
            version=row.version,
            display_order=row.display_order,
            plan_name=row.plan_name,
            plan_description=row.plan_description,
            target_platform=row.target_platform,
            visual_style=row.visual_style,
            selling_angle=row.selling_angle,
            is_current=row.is_current,
            plan=CreativePlanPayload.model_validate_json(row.plan_json),
            created_at=row.created_at,
        )

    def creative_plan_batch_read(self, row: CreativePlanBatch) -> CreativePlanBatchRead:
        return CreativePlanBatchRead(
            id=row.id,
            project_id=row.project_id,
            kind=row.kind,
            feedback=row.feedback,
            platforms=loads(row.platforms_json, []),
            style_presets=loads(row.style_presets_json, []),
            source_plan_id=row.source_plan_id,
            created_at=row.created_at,
            plans=[self.creative_plan_read(plan) for plan in sorted(row.plans, key=lambda item: (item.display_order, item.id))],
        )

    def prompt_pack_read(self, row: PromptPack) -> PromptPackRead:
        return PromptPackRead(
            id=row.id,
            project_id=row.project_id,
            plan_id=row.plan_id,
            parent_image_id=row.parent_image_id,
            source_instruction=row.source_instruction,
            prompt=PromptPackPayload.model_validate_json(row.payload_json),
            created_at=row.created_at,
        )

    def task_read(self, row: GenerationTask) -> GenerationTaskRead:
        return GenerationTaskRead(
            id=row.id,
            project_id=row.project_id,
            plan_id=row.plan_id,
            prompt_pack_id=row.prompt_pack_id,
            parent_image_id=row.parent_image_id,
            quality_run_id=row.quality_run_id,
            iteration=row.iteration,
            requested_count=row.requested_count,
            generated_count=row.generated_count,
            reviewed_count=row.reviewed_count,
            progress_stage=row.progress_stage,
            prompt=row.prompt,
            negative_prompt=row.negative_prompt,
            model_name=row.model_name,
            status=row.status,
            error_message=row.error_message,
            started_at=row.started_at,
            completed_at=row.completed_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def image_read(self, row: GeneratedImage) -> GeneratedImageRead:
        latest_review = max(row.reviews, key=lambda item: item.id, default=None)
        return GeneratedImageRead(
            id=row.id,
            task_id=row.task_id,
            project_id=row.project_id,
            plan_id=row.plan_id,
            platform=row.platform,
            generation_mode=row.generation_mode,
            prompt_pack_id=row.prompt_pack_id,
            image_url=row.image_url,
            image_path=row.image_path,
            width=row.width,
            height=row.height,
            score=row.score,
            is_selected=row.is_selected,
            is_recommended=row.is_recommended,
            review=self.image_review_read(latest_review) if latest_review else None,
            created_at=row.created_at,
        )

    def image_review_read(self, row: ImageReview) -> ImageReviewRead:
        def score_on_ten(value: int | float | None) -> int:
            return max(1, min(10, round((value or 80) / 10)))

        return ImageReviewRead(
            id=row.id,
            image_id=row.image_id,
            review=ImageReviewPayload(
                overall_score=row.overall_score,
                product_clarity=score_on_ten(row.product_clarity_score),
                product_consistency=score_on_ten(row.product_consistency_score),
                commercial_value=score_on_ten(row.commercial_value_score),
                text_accuracy=score_on_ten(getattr(row, "text_accuracy_score", 80)),
                text_artifact_risk=row.text_artifact_risk,
                ai_artifact_risk=row.ai_artifact_risk,
                recommendation_level=row.recommendation_level,
                defects=loads(row.defects_json, []),
                suggestions=loads(row.suggestions_json, []),
                evidence=loads(getattr(row, "evidence_json", "[]"), []),
                hard_defects=loads(getattr(row, "hard_defects_json", "[]"), []),
                prompt_revision=getattr(row, "prompt_revision", "") or "",
                summary=getattr(row, "summary", "") or "",
            ),
            created_at=row.created_at,
        )

    def copywriting_payload(self, row: Copywriting) -> CopywritingPayload:
        return CopywritingPayload(
            title=row.title,
            selling_points=loads(row.selling_points_json, []),
            xiaohongshu_title=row.xiaohongshu_title,
            xiaohongshu_text=row.xiaohongshu_text,
            moments_text=row.moments_text,
            taobao_text=row.taobao_text,
            xianyu_text=getattr(row, "xianyu_text", "") or "",
            tags=loads(row.tags_json, []),
        )

    def copywriting_read(self, row: Copywriting) -> CopywritingRead:
        payload = self.copywriting_payload(row)
        return CopywritingRead(
            id=row.id,
            project_id=row.project_id,
            image_id=row.image_id,
            copywriting=payload,
            created_at=row.created_at,
        )

    def _creative_plan_row(
        self,
        project_id: int,
        payload: CreativePlanPayload,
        *,
        batch_id: int,
        parent_plan_id: int | None = None,
        version: int = 1,
        display_order: int = 0,
        is_current: bool = True,
    ) -> CreativePlan:
        return CreativePlan(
            project_id=project_id,
            plan_batch_id=batch_id,
            parent_plan_id=parent_plan_id,
            version=version,
            display_order=display_order,
            plan_name=payload.plan_name,
            plan_description=payload.visual_description,
            target_platform=payload.applicable_platform,
            visual_style=payload.visual_style,
            selling_angle=payload.main_selling_point,
            plan_json=payload.model_dump_json(),
            is_current=is_current,
        )

    def _save_copywriting(
        self,
        project: Project,
        image_id: int | None,
        payload: CopywritingPayload,
    ) -> Copywriting:
        row = (
            self.db.query(Copywriting)
            .filter(Copywriting.project_id == project.id, Copywriting.image_id == image_id)
            .order_by(Copywriting.created_at.desc(), Copywriting.id.desc())
            .first()
        )
        if row is None:
            row = Copywriting(project_id=project.id, image_id=image_id)
            self.db.add(row)
        self._apply_copywriting_payload(row, payload)
        project.status = "copywritten"
        self.db.commit()
        self.db.refresh(row)
        return row

    def _apply_copywriting_payload(self, row: Copywriting, payload: CopywritingPayload) -> None:
        row.title = payload.title
        row.selling_points_json = dumps(payload.selling_points)
        row.xiaohongshu_title = payload.xiaohongshu_title
        row.xiaohongshu_text = payload.xiaohongshu_text
        row.moments_text = payload.moments_text
        row.taobao_text = payload.taobao_text
        row.xianyu_text = payload.xianyu_text
        row.tags_json = dumps(payload.tags)

    def task_error_message(self, exc: Exception) -> str:
        message = str(exc)
        if "does not support asynchronous" in message or "AccessDenied" in message:
            return "当前图片模型权限或调用方式不匹配，请检查图片模型配置后重试。"
        if "not configured" in message or "must be configured" in message:
            return "图片模型尚未配置完成，请在模型设置中检查后重试。"
        if "reference" in message or "参考图" in message:
            return "当前图片模型不支持参考图生成，请更换模型或改为从创意方向生成。"
        return "图片服务未能完成任务，请稍后重试或检查模型设置。"
