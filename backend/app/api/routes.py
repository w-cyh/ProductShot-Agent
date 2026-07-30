from datetime import datetime, timezone
from time import perf_counter

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.models import (
    Copywriting,
    CreativePlan,
    CreativePlanBatch,
    GeneratedImage,
    GenerationTask,
    ModelNameHistory,
    ModelRuntimeSettings,
    ProductAsset,
    Project,
    PromptPack,
    ProviderModelConfig,
    QualityRun,
    WorkflowEvent,
)
from app.model_settings import (
    IMAGE_PROVIDERS,
    MODEL_KINDS,
    TEXT_PROVIDERS,
    current_provider_values,
    model_name_history,
    resolve_model_config,
    upsert_model_name_history,
)
from app.providers import get_text_provider
from app.providers.text_provider import ProviderConfigurationError, TextProviderError, TextProviderUnavailable
from app.schemas import (
    CopywritingRead,
    CopywritingRequest,
    CopywritingRewriteRequest,
    CopywritingUpdate,
    CreativePlanBatchCreate,
    CreativePlanBatchRead,
    CreativePlanRevisionRequest,
    CreativePlanRead,
    GenerateImagesRequest,
    GeneratedImageRead,
    GenerationTaskCenterItem,
    GenerationTaskDetailRead,
    GenerationTaskPage,
    GenerationTaskRead,
    ModelConnectionTestRead,
    ModelNameHistoryRead,
    ModelSettingsRead,
    ModelSettingsUpdate,
    ProductAnalysisRead,
    ProductAssetRead,
    ProductVisualAnalysisRead,
    PromptPackCreate,
    PromptPackRead,
    ProjectCreate,
    ProjectDetail,
    ProjectRead,
    ProjectUpdate,
    QualityRunCreate,
    QualityRunDecisionRequest,
    QualityRunDetailRead,
    QualityRunRead,
    SelectImageRequest,
    StrategyCorrectionRequest,
    VisualAnalysisCorrectionRequest,
    WorkflowEventRead,
)
from app.services import ProductShotWorkflow
from app.services.quality import QualityRunWorkflow, QualityRuntimeUnavailable
from app.storage import remove_upload_file, save_upload_file

router = APIRouter(prefix="/api")


def get_project_or_404(db: Session, project_id: int) -> Project:
    project = (
        db.query(Project)
        .options(
            selectinload(Project.assets),
            selectinload(Project.analyses),
            selectinload(Project.creative_plans),
            selectinload(Project.creative_plan_batches).selectinload(CreativePlanBatch.plans),
            selectinload(Project.prompt_packs),
            selectinload(Project.generation_tasks).selectinload(GenerationTask.prompt_pack),
            selectinload(Project.generated_images).selectinload(GeneratedImage.task).selectinload(GenerationTask.plan),
            selectinload(Project.generated_images).selectinload(GeneratedImage.reviews),
            selectinload(Project.quality_runs),
            selectinload(Project.copywriting_items),
            selectinload(Project.workflow_events),
        )
        .filter(Project.id == project_id)
        .first()
    )
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


def require_editable_source(project: Project) -> None:
    if project.source_confirmed_at is not None:
        raise HTTPException(status_code=409, detail="商品与原图已经确认，不能再修改。")


@router.get("/model-settings", response_model=ModelSettingsRead)
def get_model_settings(db: Session = Depends(get_db)) -> ModelSettingsRead:
    return _model_settings_read(db)


@router.put("/model-settings", response_model=ModelSettingsRead)
def update_model_settings(payload: ModelSettingsUpdate, db: Session = Depends(get_db)) -> ModelSettingsRead:
    updates = payload.model_dump(exclude_unset=True)
    current = resolve_model_config(db)
    runtime = db.get(ModelRuntimeSettings, 1)
    if runtime is None:
        runtime = ModelRuntimeSettings(
            id=1,
            text_provider=current.text_provider,
            image_provider=current.image_provider,
        )
        db.add(runtime)
    if "text_provider" in updates:
        value = updates["text_provider"].lower()
        if value not in TEXT_PROVIDERS:
            raise HTTPException(status_code=400, detail="不支持的文字模型 Provider")
        runtime.text_provider = value
    if "image_provider" in updates:
        value = updates["image_provider"].lower()
        if value not in IMAGE_PROVIDERS:
            raise HTTPException(status_code=400, detail="不支持的图片模型 Provider")
        runtime.image_provider = value
    for provider_name, provider_updates in updates.get("providers", {}).items():
        if provider_name not in TEXT_PROVIDERS:
            raise HTTPException(status_code=400, detail="不支持的模型 Provider 配置")
        provider_config = (
            db.query(ProviderModelConfig).filter(ProviderModelConfig.provider == provider_name).first()
        )
        if provider_config is None:
            provider_config = ProviderModelConfig(
                provider=provider_name,
                **current_provider_values(current, provider_name),
            )
            db.add(provider_config)
        for field in ("text_model", "vision_model", "image_model"):
            if field in provider_updates and provider_updates[field] is not None:
                setattr(provider_config, field, provider_updates[field].strip())
        if "base_url" in provider_updates and provider_updates["base_url"] and provider_updates["base_url"].strip():
            provider_config.base_url = provider_updates["base_url"].rstrip("/")
        for model_kind in MODEL_KINDS:
            if model_kind in provider_updates:
                upsert_model_name_history(db, provider_name, model_kind, getattr(provider_config, model_kind))
    db.commit()
    return _model_settings_read(db)


@router.delete("/model-settings/model-name-history/{history_id}", response_model=ModelSettingsRead)
def delete_model_name_history(history_id: int, db: Session = Depends(get_db)) -> ModelSettingsRead:
    row = db.get(ModelNameHistory, history_id)
    if row is None:
        raise HTTPException(status_code=404, detail="模型历史记录不存在")
    current = resolve_model_config(db)
    active_value = current_provider_values(current, row.provider).get(row.model_kind)
    if active_value == row.model_name:
        raise HTTPException(status_code=409, detail="正在使用的模型名称不能删除，请先保存并切换为其他模型。")
    db.delete(row)
    db.commit()
    return _model_settings_read(db)


@router.post("/model-settings/test-text", response_model=ModelConnectionTestRead)
def test_text_model_connection(db: Session = Depends(get_db)) -> ModelConnectionTestRead:
    started = perf_counter()
    checked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        provider = get_text_provider()
        model = provider.model
        result = provider.generate_json(
            system_prompt="You are a connection test endpoint. Return a minimal JSON object.",
            user_prompt='Return {"ok": true, "message": "connected"} as JSON.',
            schema_name="ConnectionTest",
            schema={"type": "object", "properties": {"ok": {"type": "boolean"}, "message": {"type": "string"}}, "required": ["ok"]},
            temperature=0,
        )
        ok = bool(result.get("ok", True))
        status = "success" if ok else "failed"
        message = str(result.get("message") or ("LLM 连接测试通过。" if ok else "LLM 返回了非成功结果。"))
    except (ProviderConfigurationError, TextProviderUnavailable, TextProviderError) as exc:
        provider = None
        model = ""
        status = "failed"
        message = str(exc)
    except Exception as exc:
        status = "failed"
        message = f"LLM connection test failed: {exc}"

    return ModelConnectionTestRead(
        provider=provider.name if provider else (resolve_model_config(db).text_provider or "unconfigured"),
        model=model,
        status=status,
        latency_ms=max(0, int((perf_counter() - started) * 1000)),
        message=message,
        checked_at=checked_at,
    )


def _model_settings_read(db: Session) -> ModelSettingsRead:
    current = resolve_model_config(db)
    history = {
        provider: {
            kind: [
                ModelNameHistoryRead(
                    id=item.id,
                    provider=item.provider,
                    model_kind=item.model_kind,
                    model_name=item.model_name,
                )
                for item in values
            ]
            for kind, values in grouped.items()
        }
        for provider, grouped in model_name_history(db).items()
    }
    return ModelSettingsRead(
        text_provider=current.text_provider,
        image_provider=current.image_provider,
        providers={
            "openai": {
                **current_provider_values(current, "openai"),
                "api_key_configured": bool(settings.openai_api_key),
            },
            "dashscope": {
                **current_provider_values(current, "dashscope"),
                "api_key_configured": bool(settings.dashscope_api_key),
            },
        },
        dashscope_workspace_id_configured=bool(settings.dashscope_workspace_id),
        available_text_providers=sorted(TEXT_PROVIDERS),
        available_image_providers=sorted(IMAGE_PROVIDERS),
        model_name_history=history,
    )


@router.post("/projects", response_model=ProjectRead)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    project = Project(**payload.model_dump(), target_platform="多平台", status="draft")
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)) -> Project:
    project = get_project_or_404(db, project_id)
    require_editable_source(project)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "product_name" and value is None:
            raise HTTPException(status_code=422, detail="商品名称不能为空")
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return db.query(Project).order_by(Project.updated_at.desc()).all()


@router.get("/generation-tasks", response_model=GenerationTaskPage)
def list_generation_tasks(
    status: str = Query(default="active", pattern="^(active|queued|running|success|failed|all)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> GenerationTaskPage:
    query = (
        db.query(GenerationTask, Project.product_name, CreativePlan.plan_name)
        .join(Project, Project.id == GenerationTask.project_id)
        .outerjoin(CreativePlan, CreativePlan.id == GenerationTask.plan_id)
    )
    if status == "active":
        query = query.filter(GenerationTask.status.in_(["queued", "running"]))
    elif status != "all":
        query = query.filter(GenerationTask.status == status)
    total = query.count()
    rows = (
        query.order_by(GenerationTask.updated_at.desc(), GenerationTask.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    workflow = ProductShotWorkflow(db)
    return GenerationTaskPage(
        items=[
            GenerationTaskCenterItem(
                **workflow.task_read(task).model_dump(),
                project_name=project_name,
                plan_name=plan_name,
                parent_image_label=f"图片 #{task.parent_image_id}" if task.parent_image_id else None,
            )
            for task, project_name, plan_name in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_project(project_id: int, db: Session = Depends(get_db)) -> ProjectDetail:
    project = get_project_or_404(db, project_id)
    workflow = ProductShotWorkflow(db)
    latest_visual = workflow.latest_visual_analysis(project_id)
    latest_analysis = workflow.latest_analysis(project_id)
    copywriting_items = sorted(project.copywriting_items, key=lambda item: (item.created_at, item.id))
    current_copywriting_by_image: dict[int | None, Copywriting] = {}
    for item in copywriting_items:
        current_copywriting_by_image[item.image_id] = item
    current_copywriting = list(current_copywriting_by_image.values())
    latest_copy = max(current_copywriting, key=lambda item: (item.created_at, item.id), default=None)
    workflow_events = (
        db.query(WorkflowEvent)
        .filter(WorkflowEvent.project_id == project_id)
        .order_by(WorkflowEvent.started_at.desc(), WorkflowEvent.id.desc())
        .limit(80)
        .all()
    )
    return ProjectDetail(
        **ProjectRead.model_validate(project).model_dump(),
        assets=[ProductAssetRead.model_validate(item) for item in project.assets],
        visual_analysis=workflow.visual_analysis_read(latest_visual) if latest_visual else None,
        product_strategy=workflow.analysis_read(latest_analysis) if latest_analysis else None,
        latest_analysis=workflow.analysis_read(latest_analysis) if latest_analysis else None,
        creative_plans=[workflow.creative_plan_read(item) for item in project.creative_plans],
        creative_plan_batches=[workflow.creative_plan_batch_read(item) for item in project.creative_plan_batches],
        prompt_packs=[workflow.prompt_pack_read(item) for item in project.prompt_packs],
        generation_tasks=[workflow.task_read(item) for item in project.generation_tasks],
        quality_runs=[QualityRunWorkflow(db).read(item) for item in sorted(project.quality_runs, key=lambda item: item.id, reverse=True)],
        generated_images=[workflow.image_read(item) for item in project.generated_images],
        latest_copywriting=workflow.copywriting_read(latest_copy) if latest_copy else None,
        copywriting=[workflow.copywriting_read(item) for item in current_copywriting],
        workflow_events=[WorkflowEventRead.model_validate(item) for item in workflow_events],
    )


@router.delete("/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    project = get_project_or_404(db, project_id)
    db.delete(project)
    db.commit()
    return {"message": "项目已删除"}


def replace_primary_asset(project: Project, file: UploadFile, db: Session) -> ProductAsset:
    require_editable_source(project)
    try:
        file_path, file_url, file_type = save_upload_file(project.id, file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    previous_paths = [
        row.file_path
        for row in db.query(ProductAsset).filter(ProductAsset.project_id == project.id).all()
    ]
    db.query(ProductAsset).filter(ProductAsset.project_id == project.id).delete(synchronize_session=False)
    asset = ProductAsset(
        project_id=project.id,
        file_url=file_url,
        file_path=file_path,
        file_type=file_type,
        is_primary=True,
    )
    project.status = "draft"
    db.add(asset)
    db.commit()
    db.refresh(asset)
    for previous_path in previous_paths:
        remove_upload_file(previous_path)
    return asset


@router.post("/projects/{project_id}/assets", response_model=ProductAssetRead)
def upload_asset(project_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)) -> ProductAsset:
    project = get_project_or_404(db, project_id)
    return replace_primary_asset(project, file, db)


@router.put("/projects/{project_id}/primary-asset", response_model=ProductAssetRead)
def replace_uploaded_asset(project_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)) -> ProductAsset:
    project = get_project_or_404(db, project_id)
    return replace_primary_asset(project, file, db)


@router.post("/projects/{project_id}/confirm-source", response_model=ProjectRead)
def confirm_project_source(project_id: int, db: Session = Depends(get_db)) -> Project:
    project = get_project_or_404(db, project_id)
    try:
        ProductShotWorkflow(db).confirm_source(project)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.refresh(project)
    return project


@router.get("/projects/{project_id}/assets", response_model=list[ProductAssetRead])
def list_assets(project_id: int, db: Session = Depends(get_db)) -> list[ProductAsset]:
    get_project_or_404(db, project_id)
    return db.query(ProductAsset).filter(ProductAsset.project_id == project_id).order_by(ProductAsset.created_at.desc()).all()


@router.post("/projects/{project_id}/agent/analyze", response_model=ProductAnalysisRead)
def analyze_project(project_id: int, db: Session = Depends(get_db)) -> ProductAnalysisRead:
    project = get_project_or_404(db, project_id)
    try:
        return ProductShotWorkflow(db).analyze(project)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/projects/{project_id}/agent/analysis/corrections", response_model=ProductAnalysisRead)
def correct_product_analysis(
    project_id: int,
    payload: StrategyCorrectionRequest,
    db: Session = Depends(get_db),
) -> ProductAnalysisRead:
    project = get_project_or_404(db, project_id)
    try:
        return ProductShotWorkflow(db).correct_analysis(project, payload.instruction)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/projects/{project_id}/agent/analysis/confirm", response_model=ProductAnalysisRead)
def confirm_product_analysis(project_id: int, db: Session = Depends(get_db)) -> ProductAnalysisRead:
    project = get_project_or_404(db, project_id)
    try:
        return ProductShotWorkflow(db).confirm_analysis(project)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/projects/{project_id}/agent/visual-analysis", response_model=ProductVisualAnalysisRead)
def ensure_visual_analysis(project_id: int, db: Session = Depends(get_db)) -> ProductVisualAnalysisRead:
    project = get_project_or_404(db, project_id)
    try:
        return ProductShotWorkflow(db).ensure_visual_analysis(project)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/projects/{project_id}/agent/visual-analysis/corrections", response_model=ProductVisualAnalysisRead)
def correct_visual_analysis(
    project_id: int,
    payload: VisualAnalysisCorrectionRequest,
    db: Session = Depends(get_db),
) -> ProductVisualAnalysisRead:
    project = get_project_or_404(db, project_id)
    try:
        return ProductShotWorkflow(db).correct_visual_analysis(project, payload.instruction)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/projects/{project_id}/agent/visual-analysis/confirm", response_model=ProductVisualAnalysisRead)
def confirm_visual_analysis(project_id: int, db: Session = Depends(get_db)) -> ProductVisualAnalysisRead:
    project = get_project_or_404(db, project_id)
    try:
        return ProductShotWorkflow(db).confirm_visual_analysis(project)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/projects/{project_id}/creative-plan-batches", response_model=CreativePlanBatchRead)
def refresh_creative_plans(
    project_id: int,
    payload: CreativePlanBatchCreate,
    db: Session = Depends(get_db),
) -> CreativePlanBatchRead:
    project = get_project_or_404(db, project_id)
    workflow = ProductShotWorkflow(db)
    try:
        workflow.generate_plans(project, payload.feedback, payload.platforms, payload.style_presets)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    batch = (
        db.query(CreativePlanBatch)
        .options(selectinload(CreativePlanBatch.plans))
        .filter(CreativePlanBatch.project_id == project_id)
        .order_by(CreativePlanBatch.created_at.desc(), CreativePlanBatch.id.desc())
        .first()
    )
    if batch is None:
        raise HTTPException(status_code=500, detail="创意方向批次创建失败")
    return workflow.creative_plan_batch_read(batch)


@router.get("/projects/{project_id}/creative-plans", response_model=list[CreativePlanRead])
def list_plans(project_id: int, db: Session = Depends(get_db)) -> list[CreativePlanRead]:
    get_project_or_404(db, project_id)
    workflow = ProductShotWorkflow(db)
    rows = db.query(CreativePlan).filter(CreativePlan.project_id == project_id).order_by(CreativePlan.created_at.asc()).all()
    return [workflow.creative_plan_read(row) for row in rows]


@router.get("/projects/{project_id}/creative-plan-batches", response_model=list[CreativePlanBatchRead])
def list_plan_batches(project_id: int, db: Session = Depends(get_db)) -> list[CreativePlanBatchRead]:
    get_project_or_404(db, project_id)
    workflow = ProductShotWorkflow(db)
    rows = (
        db.query(CreativePlanBatch)
        .options(selectinload(CreativePlanBatch.plans))
        .filter(CreativePlanBatch.project_id == project_id)
        .order_by(CreativePlanBatch.created_at.desc(), CreativePlanBatch.id.desc())
        .all()
    )
    return [workflow.creative_plan_batch_read(row) for row in rows]


@router.post("/projects/{project_id}/creative-plans/{plan_id}/revisions", response_model=CreativePlanRead)
def revise_creative_plan(
    project_id: int,
    plan_id: int,
    payload: CreativePlanRevisionRequest,
    db: Session = Depends(get_db),
) -> CreativePlanRead:
    project = get_project_or_404(db, project_id)
    plan = db.query(CreativePlan).filter(CreativePlan.id == plan_id, CreativePlan.project_id == project_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail="创意方案不存在")
    try:
        return ProductShotWorkflow(db).revise_plan(project, plan, payload.instruction)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/projects/{project_id}/creative-plans/{plan_id}/prompt-packs", response_model=PromptPackRead)
def create_plan_prompt_pack(
    project_id: int,
    plan_id: int,
    payload: PromptPackCreate,
    db: Session = Depends(get_db),
) -> PromptPackRead:
    project = get_project_or_404(db, project_id)
    plan = db.query(CreativePlan).filter(CreativePlan.id == plan_id, CreativePlan.project_id == project_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail="创意方案不存在")
    try:
        return ProductShotWorkflow(db).create_prompt_pack(project, plan, instruction=payload.instruction)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/projects/{project_id}/generated-images/{image_id}/prompt-packs", response_model=PromptPackRead)
def create_image_iteration_prompt_pack(
    project_id: int,
    image_id: int,
    payload: PromptPackCreate,
    db: Session = Depends(get_db),
) -> PromptPackRead:
    project = get_project_or_404(db, project_id)
    image = (
        db.query(GeneratedImage)
        .options(selectinload(GeneratedImage.task).selectinload(GenerationTask.plan))
        .filter(GeneratedImage.id == image_id, GeneratedImage.project_id == project_id)
        .first()
    )
    if image is None or image.task.plan is None:
        raise HTTPException(status_code=404, detail="生成图片或其创意方向不存在")
    try:
        return ProductShotWorkflow(db).create_prompt_pack(project, image.task.plan, parent_image=image, instruction=payload.instruction)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/projects/{project_id}/prompt-packs/{prompt_pack_id}", response_model=PromptPackRead)
def get_prompt_pack(project_id: int, prompt_pack_id: int, db: Session = Depends(get_db)) -> PromptPackRead:
    get_project_or_404(db, project_id)
    row = db.query(PromptPack).filter(PromptPack.id == prompt_pack_id, PromptPack.project_id == project_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Prompt Pack 不存在")
    return ProductShotWorkflow(db).prompt_pack_read(row)


@router.post(
    "/projects/{project_id}/prompt-packs/{prompt_pack_id}/generation-tasks",
    response_model=GenerationTaskRead,
    status_code=202,
)
def submit_generation_task(
    project_id: int,
    prompt_pack_id: int,
    payload: GenerateImagesRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> GenerationTaskRead:
    project = get_project_or_404(db, project_id)
    prompt_pack = db.query(PromptPack).filter(PromptPack.id == prompt_pack_id, PromptPack.project_id == project_id).first()
    if prompt_pack is None:
        raise HTTPException(status_code=404, detail="Prompt Pack 不存在")
    workflow = ProductShotWorkflow(db)
    try:
        task = workflow.submit_generation_task(project, prompt_pack, payload.count)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    background_tasks.add_task(workflow.run_generation_task_in_background, task.id)
    return task


@router.get("/projects/{project_id}/generation-tasks/{task_id}", response_model=GenerationTaskDetailRead)
def get_generation_task(project_id: int, task_id: int, db: Session = Depends(get_db)) -> GenerationTaskDetailRead:
    get_project_or_404(db, project_id)
    task = db.query(GenerationTask).filter(GenerationTask.id == task_id, GenerationTask.project_id == project_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="素材任务不存在")
    return ProductShotWorkflow(db).generation_task_detail(task)


@router.post(
    "/projects/{project_id}/generation-tasks/{task_id}/retry",
    response_model=GenerationTaskRead,
    status_code=202,
)
def retry_generation_task(
    project_id: int,
    task_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> GenerationTaskRead:
    project = get_project_or_404(db, project_id)
    task = db.query(GenerationTask).filter(GenerationTask.id == task_id, GenerationTask.project_id == project_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="素材任务不存在")
    workflow = ProductShotWorkflow(db)
    try:
        retry = workflow.retry_generation_task(project, task)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    background_tasks.add_task(workflow.run_generation_task_in_background, retry.id)
    return retry


@router.post("/projects/{project_id}/quality-runs", response_model=QualityRunRead, status_code=202)
def create_quality_run(
    project_id: int,
    payload: QualityRunCreate,
    db: Session = Depends(get_db),
) -> QualityRunRead:
    project = get_project_or_404(db, project_id)
    plan = db.query(CreativePlan).filter(CreativePlan.id == payload.plan_id, CreativePlan.project_id == project_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail="创意方案不存在")
    quality = QualityRunWorkflow(db)
    try:
        run = quality.create(project, plan, payload)
        return quality.read(run)
    except QualityRuntimeUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/projects/{project_id}/quality-runs/{quality_run_id}", response_model=QualityRunDetailRead)
def get_quality_run(project_id: int, quality_run_id: int, db: Session = Depends(get_db)) -> QualityRunDetailRead:
    get_project_or_404(db, project_id)
    run = db.query(QualityRun).filter(QualityRun.id == quality_run_id, QualityRun.project_id == project_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="AI 审核运行不存在")
    return QualityRunWorkflow(db).detail(run)


@router.post("/projects/{project_id}/quality-runs/{quality_run_id}/stop", response_model=QualityRunRead, status_code=202)
def stop_quality_run(project_id: int, quality_run_id: int, db: Session = Depends(get_db)) -> QualityRunRead:
    get_project_or_404(db, project_id)
    run = db.query(QualityRun).filter(QualityRun.id == quality_run_id, QualityRun.project_id == project_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="AI 审核运行不存在")
    quality = QualityRunWorkflow(db)
    return quality.read(quality.request_stop(run))


@router.post("/projects/{project_id}/quality-runs/{quality_run_id}/retry", response_model=QualityRunRead, status_code=202)
def retry_quality_run(project_id: int, quality_run_id: int, db: Session = Depends(get_db)) -> QualityRunRead:
    get_project_or_404(db, project_id)
    run = db.query(QualityRun).filter(QualityRun.id == quality_run_id, QualityRun.project_id == project_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="AI 审核运行不存在")
    quality = QualityRunWorkflow(db)
    try:
        return quality.read(quality.retry(run))
    except QualityRuntimeUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/projects/{project_id}/quality-runs/{quality_run_id}/decision", response_model=QualityRunRead, status_code=202)
def decide_quality_run(
    project_id: int,
    quality_run_id: int,
    payload: QualityRunDecisionRequest,
    db: Session = Depends(get_db),
) -> QualityRunRead:
    get_project_or_404(db, project_id)
    run = db.query(QualityRun).filter(QualityRun.id == quality_run_id, QualityRun.project_id == project_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="AI 审核运行不存在")
    quality = QualityRunWorkflow(db)
    try:
        return quality.read(quality.decide(run, payload.action))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/projects/{project_id}/generated-images", response_model=list[GeneratedImageRead])
def list_generated_images(project_id: int, db: Session = Depends(get_db)) -> list[GeneratedImageRead]:
    get_project_or_404(db, project_id)
    workflow = ProductShotWorkflow(db)
    rows = db.query(GeneratedImage).filter(GeneratedImage.project_id == project_id).order_by(GeneratedImage.created_at.desc()).all()
    return [workflow.image_read(row) for row in rows]


@router.post("/projects/{project_id}/generated-images/{image_id}/select", response_model=GeneratedImageRead)
def select_generated_image(
    project_id: int,
    image_id: int,
    payload: SelectImageRequest,
    db: Session = Depends(get_db),
) -> GeneratedImageRead:
    project = get_project_or_404(db, project_id)
    image = db.query(GeneratedImage).filter(GeneratedImage.id == image_id, GeneratedImage.project_id == project_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail="生成图片不存在")
    if not payload.selected:
        image.is_selected = False
        db.commit()
        return ProductShotWorkflow(db).image_read(image)
    return ProductShotWorkflow(db).select_image(project, image)


@router.post("/projects/{project_id}/copywriting", response_model=CopywritingRead)
def create_copywriting(project_id: int, payload: CopywritingRequest, db: Session = Depends(get_db)) -> CopywritingRead:
    project = get_project_or_404(db, project_id)
    image = None
    if payload.image_id:
        image = (
            db.query(GeneratedImage)
            .options(
                selectinload(GeneratedImage.task).selectinload(GenerationTask.plan),
            )
            .filter(GeneratedImage.id == payload.image_id, GeneratedImage.project_id == project_id)
            .first()
        )
        if image is None:
            raise HTTPException(status_code=404, detail="生成图片不存在")
    try:
        return ProductShotWorkflow(db).create_copywriting(project, image)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/projects/{project_id}/copywriting/{copywriting_id}", response_model=CopywritingRead)
def update_copywriting(
    project_id: int,
    copywriting_id: int,
    payload: CopywritingUpdate,
    db: Session = Depends(get_db),
) -> CopywritingRead:
    project = get_project_or_404(db, project_id)
    current = db.query(Copywriting).filter(Copywriting.id == copywriting_id, Copywriting.project_id == project_id).first()
    if current is None:
        raise HTTPException(status_code=404, detail="文案不存在")
    try:
        return ProductShotWorkflow(db).update_copywriting(project, current, payload.copywriting)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/projects/{project_id}/copywriting/{copywriting_id}/rewrite", response_model=CopywritingRead)
def rewrite_copywriting(
    project_id: int,
    copywriting_id: int,
    payload: CopywritingRewriteRequest,
    db: Session = Depends(get_db),
) -> CopywritingRead:
    project = get_project_or_404(db, project_id)
    current = db.query(Copywriting).filter(Copywriting.id == copywriting_id, Copywriting.project_id == project_id).first()
    if current is None:
        raise HTTPException(status_code=404, detail="文案不存在")
    try:
        return ProductShotWorkflow(db).rewrite_copywriting(project, current, payload.instruction)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
