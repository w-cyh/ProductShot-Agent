import { http } from './client'

export interface Project {
  id: number
  product_name: string
  product_category?: string | null
  core_selling_points?: string | null
  target_audience?: string | null
  status: string
  source_confirmed_at?: string | null
  strategy_confirmed_at?: string | null
  created_at: string
  updated_at: string
}

export interface ProjectCreate {
  product_name: string
  product_category?: string
  core_selling_points?: string
  target_audience?: string
}

export interface ProductAsset {
  id: number
  project_id: number
  file_url: string
  file_path: string
  file_type: string
  is_primary: boolean
  width?: number | null
  height?: number | null
  created_at: string
}

export interface ProductAnalysis {
  product_type: string
  core_features: string[]
  target_audience_analysis: string
  recommended_selling_points: string[]
  recommended_visual_styles: string[]
  image_issues: string[]
  marketing_angles: string[]
  visual_summary?: string | null
  product_consistency_rules: string[]
  platform_strategy?: string | null
}

export interface VisualAnalysis {
  product_appearance: string
  dominant_colors: string[]
  materials: string[]
  visible_text_or_logo: string[]
  subject_clarity: string
  background_issues: string[]
  fidelity_constraints: string[]
  marketing_opportunities: string[]
  human_reviewed: boolean
  human_review_notes: string
}

export interface ProductVisualAnalysisRead {
  id: number
  project_id: number
  analysis: VisualAnalysis
  created_at: string
}

export interface ProductAnalysisRead {
  id: number
  project_id: number
  analysis: ProductAnalysis
  created_at: string
}

export interface CreativePlanPayload {
  plan_name: string
  applicable_platform: string
  visual_description: string
  background_scene: string
  visual_style: string
  main_selling_point: string
  recommendation_reason: string
  copywriting_direction: string
  expected_outputs: string[]
}

export interface CreativePlan {
  id: number
  project_id: number
  plan_batch_id?: number | null
  parent_plan_id?: number | null
  version: number
  display_order: number
  plan_name: string
  plan_description: string
  target_platform: string
  visual_style: string
  selling_angle: string
  is_current: boolean
  plan: CreativePlanPayload
  created_at: string
}

export interface CreativePlanBatch {
  id: number
  project_id: number
  kind: string
  feedback: string
  platforms: string[]
  style_presets: string[]
  source_plan_id?: number | null
  created_at: string
  plans: CreativePlan[]
}

export interface PromptPayload {
  positive_prompt: string
  negative_prompt: string
  size: string
  style: string
  product_consistency_notes: string
}

export interface PromptPackPayload extends PromptPayload {
  platform: string
  generation_mode: string
  reference_strength: number
  consistency_rules: string[]
}

export interface PromptPack {
  id: number
  project_id: number
  plan_id: number
  parent_image_id?: number | null
  source_instruction: string
  prompt: PromptPackPayload
  created_at: string
}

export interface GenerationTask {
  id: number
  project_id: number
  plan_id?: number | null
  prompt_pack_id?: number | null
  parent_image_id?: number | null
  quality_run_id?: number | null
  iteration: number
  requested_count: number
  generated_count: number
  reviewed_count: number
  progress_stage: string
  prompt: string
  negative_prompt: string
  model_name: string
  status: string
  error_message?: string | null
  started_at?: string | null
  completed_at?: string | null
  created_at: string
  updated_at: string
}

export interface GenerationTaskDetail {
  task: GenerationTask
  prompt_pack?: PromptPack | null
  images: GeneratedImage[]
}

export interface GenerationTaskCenterItem extends GenerationTask {
  project_name: string
  plan_name?: string | null
  parent_image_label?: string | null
}

export interface GenerationTaskPage {
  items: GenerationTaskCenterItem[]
  total: number
  page: number
  page_size: number
}

export interface GeneratedImage {
  id: number
  task_id: number
  project_id: number
  plan_id?: number | null
  platform?: string | null
  generation_mode?: string | null
  prompt_pack_id?: string | null
  image_url: string
  image_path: string
  width?: number | null
  height?: number | null
  score?: number | null
  is_selected: boolean
  is_recommended: boolean
  review?: ImageReview | null
  created_at: string
}

export interface ImageReviewEvidence {
  dimension: 'product_consistency' | 'product_clarity' | 'commercial_value' | 'text_accuracy' | 'style_match' | 'platform_fit'
  observation: string
  severity: 'info' | 'warning' | 'blocking'
}

export interface ImageReviewPayload {
  overall_score: number
  product_clarity: number
  product_consistency: number
  commercial_value: number
  text_accuracy: number
  text_artifact_risk: string
  ai_artifact_risk: string
  recommendation_level: string
  defects: string[]
  suggestions: string[]
  evidence: ImageReviewEvidence[]
  hard_defects: string[]
  prompt_revision: string
  summary: string
}

export interface ImageReview {
  id: number
  image_id: number
  review: ImageReviewPayload
  created_at: string
}

export type QualityProfile = 'fidelity' | 'balanced' | 'commercial'
export type QualityAcceptanceTier = 'loose' | 'standard' | 'strict'

export interface QualityRun {
  id: number
  project_id: number
  plan_id: number
  quality_profile: QualityProfile
  acceptance_tier: QualityAcceptanceTier
  target_score: number
  images_per_round: number
  max_rounds: number
  total_image_budget: number
  status: string
  current_round: number
  stop_requested: boolean
  recommended_image_id?: number | null
  error_message?: string | null
  started_at?: string | null
  completed_at?: string | null
  created_at: string
  updated_at: string
}

export interface QualityRound {
  id: number
  quality_run_id: number
  round_number: number
  prompt_pack_id?: number | null
  generation_task_id?: number | null
  best_image_id?: number | null
  best_score?: number | null
  status: string
  outcome: string
  review_summary: Record<string, unknown>
  created_at: string
  updated_at: string
  images: GeneratedImage[]
}

export interface QualityRunDetail extends QualityRun {
  profile_weights: Record<string, number>
  primary_dimension: string
  remaining_rounds: number
  max_review_calls: number
  max_prompt_revisions: number
  rounds: QualityRound[]
}

export interface GeneratedImagesResponse {
  task: GenerationTask
  prompt: PromptPackPayload
  images: GeneratedImage[]
}

export interface CopywritingPayload {
  title: string
  selling_points: string[]
  xiaohongshu_title: string
  xiaohongshu_text: string
  moments_text: string
  taobao_text: string
  xianyu_text: string
  tags: string[]
}

export interface CopywritingRead {
  id: number
  project_id: number
  image_id?: number | null
  copywriting: CopywritingPayload
  created_at: string
}

export interface ModelSettings {
  text_provider: string
  image_provider: string
  providers: Record<string, ProviderModelSettings>
  dashscope_workspace_id_configured: boolean
  available_text_providers: string[]
  available_image_providers: string[]
  model_name_history: Record<string, Record<ModelNameKind, ModelNameHistory[]>>
}

export interface ProviderModelSettings {
  text_model: string
  vision_model: string
  image_model: string
  base_url: string
  api_key_configured: boolean
}

export type ModelNameKind = 'text_model' | 'vision_model' | 'image_model'

export interface ModelNameHistory {
  id: number
  provider: 'openai' | 'dashscope'
  model_kind: ModelNameKind
  model_name: string
}

export type ModelSettingsUpdate = Partial<
  Pick<
    ModelSettings,
    | 'text_provider'
    | 'image_provider'
  >
> & { providers?: Record<string, Partial<Pick<ProviderModelSettings, 'text_model' | 'vision_model' | 'image_model' | 'base_url'>>> }

export interface ModelConnectionTest {
  provider: string
  model: string
  status: string
  latency_ms: number
  message: string
  checked_at: string
}

export interface WorkflowEvent {
  id: number
  project_id: number
  step_key: string
  agent_name: string
  status: string
  summary: string
  detail_json: string
  error_message?: string | null
  started_at: string
  ended_at?: string | null
  latency_ms?: number | null
}

export interface ProjectDetail extends Project {
  assets: ProductAsset[]
  visual_analysis?: ProductVisualAnalysisRead | null
  product_strategy?: ProductAnalysisRead | null
  latest_analysis?: ProductAnalysisRead | null
  creative_plans: CreativePlan[]
  creative_plan_batches: CreativePlanBatch[]
  prompt_packs: PromptPack[]
  generation_tasks: GenerationTask[]
  quality_runs: QualityRun[]
  generated_images: GeneratedImage[]
  latest_copywriting?: CopywritingRead | null
  copywriting: CopywritingRead[]
  workflow_events: WorkflowEvent[]
}

export async function createProject(payload: ProjectCreate) {
  const { data } = await http.post<Project>('/api/projects', payload)
  return data
}

export async function updateProject(projectId: number, payload: ProjectCreate) {
  const { data } = await http.patch<Project>(`/api/projects/${projectId}`, payload)
  return data
}

export async function listProjects() {
  const { data } = await http.get<Project[]>('/api/projects')
  return data
}

export async function listGenerationTasks(status = 'active', page = 1, pageSize = 20) {
  const { data } = await http.get<GenerationTaskPage>('/api/generation-tasks', {
    params: { status, page, page_size: pageSize }
  })
  return data
}

export async function getProject(projectId: number) {
  const { data } = await http.get<ProjectDetail>(`/api/projects/${projectId}`)
  return data
}

export async function uploadAsset(projectId: number, file: File) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post<ProductAsset>(`/api/projects/${projectId}/assets`, form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return data
}

export async function replacePrimaryAsset(projectId: number, file: File) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.put<ProductAsset>(`/api/projects/${projectId}/primary-asset`, form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return data
}

export async function confirmSource(projectId: number) {
  const { data } = await http.post<Project>(`/api/projects/${projectId}/confirm-source`)
  return data
}

export async function analyzeProject(projectId: number) {
  const { data } = await http.post<ProductAnalysisRead>(`/api/projects/${projectId}/agent/analyze`)
  return data
}

export async function correctProductAnalysis(projectId: number, instruction: string) {
  const { data } = await http.post<ProductAnalysisRead>(`/api/projects/${projectId}/agent/analysis/corrections`, { instruction })
  return data
}

export async function confirmProductAnalysis(projectId: number) {
  const { data } = await http.post<ProductAnalysisRead>(`/api/projects/${projectId}/agent/analysis/confirm`)
  return data
}

export async function ensureVisualAnalysis(projectId: number) {
  const { data } = await http.post<ProductVisualAnalysisRead>(`/api/projects/${projectId}/agent/visual-analysis`)
  return data
}

export async function correctVisualAnalysis(projectId: number, instruction: string) {
  const { data } = await http.post<ProductVisualAnalysisRead>(
    `/api/projects/${projectId}/agent/visual-analysis/corrections`,
    { instruction }
  )
  return data
}

export async function confirmVisualAnalysis(projectId: number) {
  const { data } = await http.post<ProductVisualAnalysisRead>(`/api/projects/${projectId}/agent/visual-analysis/confirm`)
  return data
}

export async function refreshCreativePlans(
  projectId: number,
  payload: { feedback?: string; platforms?: string[]; style_presets?: string[] } = {}
) {
  const { data } = await http.post<CreativePlanBatch>(`/api/projects/${projectId}/creative-plan-batches`, payload)
  return data
}

export async function reviseCreativePlan(projectId: number, planId: number, instruction: string) {
  const { data } = await http.post<CreativePlan>(`/api/projects/${projectId}/creative-plans/${planId}/revisions`, { instruction })
  return data
}

export async function listPlans(projectId: number) {
  const { data } = await http.get<CreativePlan[]>(`/api/projects/${projectId}/creative-plans`)
  return data
}

export async function createPlanPromptPack(projectId: number, planId: number, instruction = '') {
  const { data } = await http.post<PromptPack>(`/api/projects/${projectId}/creative-plans/${planId}/prompt-packs`, { instruction })
  return data
}

export async function createImagePromptPack(projectId: number, imageId: number, instruction: string) {
  const { data } = await http.post<PromptPack>(`/api/projects/${projectId}/generated-images/${imageId}/prompt-packs`, { instruction })
  return data
}

export async function submitGenerationTask(projectId: number, promptPackId: number, count = 2) {
  const { data } = await http.post<GenerationTask>(`/api/projects/${projectId}/prompt-packs/${promptPackId}/generation-tasks`, { count })
  return data
}

export async function getGenerationTask(projectId: number, taskId: number) {
  const { data } = await http.get<GenerationTaskDetail>(`/api/projects/${projectId}/generation-tasks/${taskId}`)
  return data
}

export async function retryGenerationTask(projectId: number, taskId: number) {
  const { data } = await http.post<GenerationTask>(`/api/projects/${projectId}/generation-tasks/${taskId}/retry`)
  return data
}

export async function createQualityRun(
  projectId: number,
  payload: {
    plan_id: number
    quality_profile: QualityProfile
    acceptance_tier: QualityAcceptanceTier
    images_per_round: number
    max_rounds: number
  }
) {
  const { data } = await http.post<QualityRun>(`/api/projects/${projectId}/quality-runs`, payload)
  return data
}

export async function getQualityRun(projectId: number, qualityRunId: number) {
  const { data } = await http.get<QualityRunDetail>(`/api/projects/${projectId}/quality-runs/${qualityRunId}`)
  return data
}

export async function stopQualityRun(projectId: number, qualityRunId: number) {
  const { data } = await http.post<QualityRun>(`/api/projects/${projectId}/quality-runs/${qualityRunId}/stop`)
  return data
}

export async function retryQualityRun(projectId: number, qualityRunId: number) {
  const { data } = await http.post<QualityRun>(`/api/projects/${projectId}/quality-runs/${qualityRunId}/retry`)
  return data
}

export async function decideQualityRun(projectId: number, qualityRunId: number, action: 'accept_recommended' | 'continue') {
  const { data } = await http.post<QualityRun>(`/api/projects/${projectId}/quality-runs/${qualityRunId}/decision`, { action })
  return data
}

export async function selectGeneratedImage(projectId: number, imageId: number) {
  const { data } = await http.post<GeneratedImage>(`/api/projects/${projectId}/generated-images/${imageId}/select`, { selected: true })
  return data
}

export async function createCopywriting(projectId: number, imageId?: number) {
  const { data } = await http.post<CopywritingRead>(`/api/projects/${projectId}/copywriting`, {
    image_id: imageId
  })
  return data
}

export async function updateCopywriting(projectId: number, copywritingId: number, copywriting: CopywritingPayload) {
  const { data } = await http.put<CopywritingRead>(`/api/projects/${projectId}/copywriting/${copywritingId}`, { copywriting })
  return data
}

export async function rewriteCopywriting(projectId: number, copywritingId: number, instruction: string) {
  const { data } = await http.post<CopywritingRead>(`/api/projects/${projectId}/copywriting/${copywritingId}/rewrite`, { instruction })
  return data
}

export async function getModelSettings() {
  const { data } = await http.get<ModelSettings>('/api/model-settings')
  return data
}

export async function updateModelSettings(payload: ModelSettingsUpdate) {
  const { data } = await http.put<ModelSettings>('/api/model-settings', payload)
  return data
}

export async function deleteModelNameHistory(historyId: number) {
  const { data } = await http.delete<ModelSettings>(`/api/model-settings/model-name-history/${historyId}`)
  return data
}

export async function testTextModelConnection() {
  const { data } = await http.post<ModelConnectionTest>('/api/model-settings/test-text')
  return data
}
