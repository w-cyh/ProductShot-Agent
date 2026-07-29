import { defineStore } from 'pinia'
import {
  analyzeProject,
  ensureVisualAnalysis,
  getProject,
  type GeneratedImage,
  type ImageReviewRead,
  type ProjectDetail,
  reviewImage
} from '../api/productshot'

export type StepStatus = 'pending' | 'running' | 'success' | 'failed'
export type WorkflowUiStatus = 'idle' | 'action_required' | 'running' | 'success' | 'failed'
export type StudioStageKey = 'brief' | 'analysis' | 'plans' | 'generation' | 'delivery'
export type StudioStageStatus = 'locked' | 'available' | 'current' | 'running' | 'success' | 'failed'

export interface WorkflowStep {
  key: string
  title: string
  status: StepStatus
  description: string
}

export interface StudioStage {
  key: StudioStageKey
  title: string
  description: string
  status: StudioStageStatus
  available: boolean
  lockedReason?: string
}

interface ProjectContext {
  detail: ProjectDetail | null
  loading: boolean
  lastReview: ImageReviewRead | null
  stage: StudioStageKey
}

const pollers = new Map<number, ReturnType<typeof window.setInterval>>()

function initialSteps(): WorkflowStep[] {
  return [
    { key: 'source', title: '商品确认', status: 'pending', description: '锁定商品事实与原图' },
    { key: 'visual_analysis', title: '原图理解', status: 'pending', description: '提取商品外观与保真约束' },
    { key: 'analysis', title: '商品策略', status: 'pending', description: '提炼卖点、人群与营销机会' },
    { key: 'plans', title: '创意方向', status: 'pending', description: '生成 3 个可选方向' },
    { key: 'prompt', title: '提示词', status: 'pending', description: '只在开始生图时构建' },
    { key: 'images', title: '素材生成', status: 'pending', description: '按方向沉淀图片素材' },
    { key: 'copy', title: '发布文案', status: 'pending', description: '为交付图生成当前稿' }
  ]
}

function hasActiveWork(detail: ProjectDetail | null | undefined) {
  if (!detail) return false
  return detail.generation_tasks.some((task) => ['queued', 'running'].includes(task.status)) || detail.workflow_events.some(
    (event) => ['queued', 'running'].includes(event.status)
  )
}

function stepsForDetail(detail: ProjectDetail | null | undefined): WorkflowStep[] {
  const steps = initialSteps()
  if (!detail) return steps
  const statusForEvent = (key: string): StepStatus | null => {
    const event = detail.workflow_events.find((item) => item.step_key === key)
    if (!event) return null
    if (event.status === 'failed') return 'failed'
    if (event.status === 'running' || event.status === 'queued') return 'running'
    return event.status === 'success' ? 'success' : null
  }
  const set = (key: string, status: StepStatus) => {
    const step = steps.find((item) => item.key === key)
    if (step) step.status = status
  }
  if (detail.source_confirmed_at) set('source', 'success')
  if (detail.visual_analysis) set('visual_analysis', detail.visual_analysis.analysis.human_reviewed ? 'success' : 'running')
  if (detail.latest_analysis) set('analysis', 'success')
  if (detail.creative_plans.some((plan) => plan.is_current)) set('plans', 'success')
  if (detail.prompt_packs.length) set('prompt', 'success')
  if (detail.generation_tasks.some((task) => ['queued', 'running'].includes(task.status))) set('images', 'running')
  else if (detail.generated_images.length) set('images', 'success')
  if (detail.copywriting.length) set('copy', 'success')
  steps.forEach((step) => {
    const eventStatus = statusForEvent(step.key)
    if (eventStatus === 'failed' || (eventStatus === 'running' && step.status !== 'success')) set(step.key, eventStatus)
  })
  return steps
}

export const useProjectStore = defineStore('project', {
  state: () => ({
    currentProjectId: null as number | null,
    contexts: {} as Record<number, ProjectContext>
  }),
  getters: {
    currentContext(state): ProjectContext | null {
      return state.currentProjectId ? state.contexts[state.currentProjectId] || null : null
    },
    current(): ProjectDetail | null {
      return this.currentContext?.detail || null
    },
    loading(): boolean {
      return this.currentContext?.loading || false
    },
    steps(): WorkflowStep[] {
      return stepsForDetail(this.currentContext?.detail)
    },
    latestEventsByStep(): Record<string, NonNullable<ProjectDetail['workflow_events']>[number]> {
      const events = this.current?.workflow_events || []
      return events.reduce<Record<string, (typeof events)[number]>>((latest, event) => {
        if (!latest[event.step_key]) latest[event.step_key] = event
        return latest
      }, {})
    },
    hasRunningWorkflowEvent(): boolean {
      return hasActiveWork(this.currentContext?.detail)
    }
  },
  actions: {
    ensureContext(projectId: number) {
      if (!this.contexts[projectId]) {
        this.contexts[projectId] = { detail: null, loading: false, lastReview: null, stage: 'brief' }
      }
      return this.contexts[projectId]
    },
    setCurrentProject(projectId: number | null) {
      this.currentProjectId = projectId
      if (projectId) this.ensureContext(projectId)
    },
    setStage(projectId: number, stage: StudioStageKey) {
      this.ensureContext(projectId).stage = stage
    },
    async load(projectId: number) {
      const context = this.ensureContext(projectId)
      context.loading = true
      try {
        context.detail = await getProject(projectId)
        this.ensurePolling(projectId)
      } finally {
        context.loading = false
      }
    },
    async refresh(projectId: number) {
      const context = this.ensureContext(projectId)
      context.detail = await getProject(projectId)
      this.ensurePolling(projectId)
    },
    clearCurrent() {
      this.currentProjectId = null
    },
    async runVisualAnalysis(projectId: number) {
      await ensureVisualAnalysis(projectId)
      await this.load(projectId)
    },
    async runProductAnalysis(projectId: number) {
      await analyzeProject(projectId)
      await this.load(projectId)
    },
    async review(projectId: number, image: GeneratedImage) {
      const context = this.ensureContext(projectId)
      context.lastReview = await reviewImage(projectId, image.id)
      await this.load(projectId)
    },
    stepsFor(projectId: number): WorkflowStep[] {
      return stepsForDetail(this.contexts[projectId]?.detail)
    },
    hasActiveWork(projectId: number | null) {
      if (!projectId) return false
      return hasActiveWork(this.contexts[projectId]?.detail)
    },
    ensurePolling(projectId: number) {
      if (!this.hasActiveWork(projectId)) {
        this.stopPolling(projectId)
        return
      }
      if (pollers.has(projectId)) return
      const timer = window.setInterval(async () => {
        try {
          await this.refresh(projectId)
        } catch {
          // The current page will surface a user-actionable error on the next interaction.
        }
      }, 2500)
      pollers.set(projectId, timer)
    },
    stopPolling(projectId: number) {
      const timer = pollers.get(projectId)
      if (timer) window.clearInterval(timer)
      pollers.delete(projectId)
    },
    stopAllPolling() {
      for (const projectId of pollers.keys()) this.stopPolling(projectId)
    }
  }
})
