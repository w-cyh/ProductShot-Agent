<template>
  <section
    class="status-center"
    :class="status"
    :role="status === 'failed' ? 'alert' : 'status'"
    :aria-live="status === 'failed' ? 'assertive' : 'polite'"
  >
    <div class="status-summary">
      <div class="status-mark" :class="status" aria-hidden="true">
        <el-icon v-if="status === 'running'" class="is-loading" :size="20"><Loading /></el-icon>
        <el-icon v-else-if="status === 'failed'" :size="20"><Warning /></el-icon>
        <el-icon v-else-if="status === 'success'" :size="20"><CircleCheck /></el-icon>
        <el-icon v-else-if="status === 'action_required'" :size="20"><User /></el-icon>
        <el-icon v-else :size="20"><Clock /></el-icon>
      </div>

      <div class="status-copy">
        <div class="status-title-line">
          <span class="status-label">{{ statusLabel }}</span>
          <h2>{{ title }}</h2>
          <span v-if="elapsedLabel" class="elapsed-time">{{ elapsedLabel }}</span>
        </div>
        <p>{{ message }}</p>
        <p v-if="longRunning" class="long-running-note">等待时间较长，任务仍在运行。你可以查看运行记录确认服务状态。</p>
      </div>

      <div class="status-actions">
        <el-button v-if="primaryLabel" class="orange-button" type="primary" @click="$emit('primary')">
          {{ primaryLabel }}
        </el-button>
        <el-button @click="openEvents">查看运行记录</el-button>
      </div>
    </div>

    <div class="workflow-meter" aria-label="技术工作流进度">
      <div class="meter-head">
        <span>生产流程</span>
        <strong>{{ completedCount }}/{{ steps.length }}</strong>
      </div>
      <el-progress :percentage="completionPercent" :show-text="false" :status="status === 'failed' ? 'exception' : undefined" />
      <div class="compact-steps">
        <button
          v-for="step in steps"
          :key="step.key"
          class="compact-step"
          :class="step.status"
          type="button"
          :aria-label="`查看${step.title}阶段`"
          @click="$emit('select-step', step.key)"
        >
          <span class="compact-dot"></span>
          <span class="compact-step-label">{{ step.title }}</span>
        </button>
      </div>
    </div>
  </section>

  <el-drawer
    v-model="eventsOpen"
    class="workflow-drawer"
    title="运行记录"
    direction="rtl"
    size="min(580px, 100vw)"
    append-to-body
  >
    <div class="drawer-intro">
      <span class="status-label">{{ statusLabel }}</span>
      <p>最新事件排在最前。失败和运行中的事件会自动展开，技术输入输出可在详情中查看。</p>
    </div>

    <el-collapse v-if="events.length" v-model="expandedEvents" class="event-list">
      <el-collapse-item v-for="event in events" :key="event.id" :name="event.id">
        <template #title>
          <div class="event-title">
            <span class="event-dot" :class="normalizedEventStatus(event)"></span>
            <div>
              <strong>{{ stepLabel(event.step_key) }}</strong>
              <span>{{ event.agent_name }}</span>
            </div>
            <time>{{ formatEventTime(event.started_at) }}</time>
          </div>
        </template>

        <div class="event-body">
          <p>{{ event.error_message || event.summary }}</p>
          <dl>
            <div>
              <dt>状态</dt>
              <dd>{{ eventStatusLabel(event) }}</dd>
            </div>
            <div>
              <dt>耗时</dt>
              <dd>{{ formatLatency(event.latency_ms) }}</dd>
            </div>
            <div>
              <dt>开始时间</dt>
              <dd>{{ formatDate(event.started_at) }}</dd>
            </div>
          </dl>
          <el-collapse v-if="eventDetailText(event)" class="technical-detail">
            <el-collapse-item title="技术详情" name="detail">
              <pre>{{ eventDetailText(event) }}</pre>
            </el-collapse-item>
          </el-collapse>
        </div>
      </el-collapse-item>
    </el-collapse>
    <el-empty v-else description="运行工作流后，这里会显示可排查的事件记录" />
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { CircleCheck, Clock, Loading, User, Warning } from '@element-plus/icons-vue'
import type { WorkflowEvent } from '../api/productshot'
import type { WorkflowStep, WorkflowUiStatus } from '../stores/project'

const props = defineProps<{
  status: WorkflowUiStatus
  title: string
  message: string
  primaryLabel?: string
  startedAt?: string | null
  steps: WorkflowStep[]
  events: WorkflowEvent[]
}>()

defineEmits<{
  primary: []
  'select-step': [stepKey: string]
}>()

const eventsOpen = ref(false)
const expandedEvents = ref<number[]>([])
const now = ref(Date.now())
let elapsedTimer: ReturnType<typeof window.setInterval> | null = null

const completedCount = computed(() => props.steps.filter((step) => step.status === 'success').length)
const completionPercent = computed(() =>
  props.steps.length ? Math.round((completedCount.value / props.steps.length) * 100) : 0
)
const latestEventIdsByStep = computed(() =>
  props.events.reduce<Record<string, number>>((latest, event) => {
    if (!latest[event.step_key]) latest[event.step_key] = event.id
    return latest
  }, {})
)
const statusLabel = computed(() => {
  const labels: Record<WorkflowUiStatus, string> = {
    idle: '未开始',
    action_required: '等待操作',
    running: '运行中',
    success: '已完成',
    failed: '失败'
  }
  return labels[props.status]
})
const elapsedMs = computed(() => {
  if (props.status !== 'running' || !props.startedAt) return 0
  return Math.max(0, now.value - new Date(props.startedAt).getTime())
})
const elapsedLabel = computed(() => {
  if (!elapsedMs.value) return ''
  const totalSeconds = Math.floor(elapsedMs.value / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `已等待 ${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
})
const longRunning = computed(() => elapsedMs.value >= 10 * 60 * 1000)

watch(
  () => props.startedAt,
  () => {
    now.value = Date.now()
  }
)

onMounted(() => {
  elapsedTimer = window.setInterval(() => {
    now.value = Date.now()
  }, 1000)
})

onBeforeUnmount(() => {
  if (elapsedTimer) window.clearInterval(elapsedTimer)
})

function openEvents() {
  expandedEvents.value = props.events
    .filter(
      (event) =>
        latestEventIdsByStep.value[event.step_key] === event.id &&
        (event.status === 'running' || event.status === 'failed')
    )
    .map((event) => event.id)
  eventsOpen.value = true
}

function normalizedEventStatus(event: WorkflowEvent) {
  if (event.status === 'running' && latestEventIdsByStep.value[event.step_key] !== event.id) return 'pending'
  if (event.status === 'running' || event.status === 'failed' || event.status === 'success') return event.status
  return 'pending'
}

function eventStatusLabel(event: WorkflowEvent) {
  if (latestEventIdsByStep.value[event.step_key] !== event.id) {
    if (event.status === 'running') return '启动记录'
    if (event.status === 'failed') return '历史失败'
  }
  const labels: Record<string, string> = {
    pending: '等待中',
    running: '运行中',
    success: '已完成',
    failed: '失败'
  }
  return labels[event.status] || event.status
}

function stepLabel(stepKey: string) {
  const labels: Record<string, string> = {
    visual_analysis: '原图理解',
    visual_review: '人工确认',
    analysis: '商品策略',
    plans: '方向规划',
    prompt: 'Prompt 构建',
    images: '素材生成',
    review: '质量评价',
    copy: '发布文案',
    revision: '修改计划'
  }
  return labels[stepKey] || stepKey
}

function formatEventTime(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function formatDate(value: string) {
  return new Date(value).toLocaleString()
}

function formatLatency(value?: number | null) {
  if (!value) return '—'
  return value >= 1000 ? `${(value / 1000).toFixed(1)} 秒` : `${value} ms`
}

function eventDetailText(event: WorkflowEvent) {
  if (!event.detail_json) return ''
  try {
    return JSON.stringify(JSON.parse(event.detail_json), null, 2)
  } catch {
    return event.detail_json
  }
}
</script>

<style scoped>
.status-center {
  position: sticky;
  top: 12px;
  z-index: 24;
  display: grid;
  gap: 12px;
  padding: 14px 16px 12px;
  border: 1px solid rgba(36, 88, 70, 0.2);
  border-radius: var(--ps-radius);
  background:
    linear-gradient(100deg, rgba(36, 88, 70, 0.08), transparent 44%),
    rgba(251, 250, 246, 0.96);
  box-shadow: 0 14px 40px rgba(35, 38, 32, 0.1);
  backdrop-filter: blur(18px);
}

.status-center.running {
  border-color: rgba(201, 93, 66, 0.34);
  background:
    linear-gradient(100deg, rgba(201, 93, 66, 0.1), transparent 48%),
    rgba(251, 250, 246, 0.96);
}

.status-center.failed {
  border-color: rgba(185, 64, 61, 0.42);
  background:
    linear-gradient(100deg, rgba(185, 64, 61, 0.1), transparent 48%),
    rgba(251, 250, 246, 0.97);
}

.status-summary {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
}

.status-mark {
  display: grid;
  width: 40px;
  height: 40px;
  place-items: center;
  border-radius: 999px;
  color: var(--ps-muted-strong);
  background: var(--ps-surface-soft);
}

.status-mark.action_required {
  color: var(--ps-gold);
  background: #f4ecd9;
}

.status-mark.running {
  color: #fff;
  background: var(--ps-accent);
}

.status-mark.success {
  color: #fff;
  background: var(--ps-primary);
}

.status-mark.failed {
  color: #fff;
  background: var(--ps-danger);
}

.status-copy {
  min-width: 0;
}

.status-title-line {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.status-label {
  display: inline-flex;
  min-height: 24px;
  align-items: center;
  padding: 0 8px;
  border: 1px solid rgba(36, 88, 70, 0.16);
  border-radius: 999px;
  color: var(--ps-primary);
  background: var(--ps-primary-soft);
  font-size: 11px;
  font-weight: 850;
}

.running .status-label {
  border-color: rgba(201, 93, 66, 0.2);
  color: var(--ps-accent-dark);
  background: var(--ps-accent-soft);
}

.failed .status-label {
  border-color: rgba(185, 64, 61, 0.2);
  color: var(--ps-danger);
  background: #f7e4e2;
}

.status-copy h2 {
  min-width: 0;
  margin: 0;
  overflow: hidden;
  color: var(--ps-heading);
  font-size: 17px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-copy p {
  margin: 4px 0 0;
  overflow: hidden;
  color: var(--ps-muted-strong);
  font-size: 13px;
  line-height: 1.5;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-copy .long-running-note {
  color: var(--ps-accent-dark);
  white-space: normal;
}

.elapsed-time {
  color: var(--ps-muted);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.status-actions {
  display: flex;
  gap: 8px;
}

.workflow-meter {
  display: grid;
  grid-template-columns: 90px minmax(120px, 0.35fr) minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  padding-top: 10px;
  border-top: 1px solid rgba(220, 219, 210, 0.88);
}

.meter-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--ps-muted);
  font-size: 11px;
  font-weight: 800;
}

.meter-head strong {
  color: var(--ps-heading);
}

.compact-steps {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 7px;
  overflow: visible;
}

.compact-step {
  position: relative;
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 2px 0 0;
  border: 0;
  color: var(--ps-muted);
  background: transparent;
  text-align: center;
  font-size: 10px;
  cursor: pointer;
}

.compact-step::after {
  position: absolute;
  top: 5px;
  left: calc(50% + 4px);
  width: calc(100% + 3px);
  height: 2px;
  content: '';
  border-radius: 999px;
}

.compact-step::after {
  z-index: 0;
  background: var(--ps-primary);
  transform: scaleX(0);
  transform-origin: left center;
}

.compact-step:last-child::after {
  display: none;
}

.compact-step.success::after {
  transform: scaleX(1);
}

.compact-step.running::after {
  animation: extend-workflow-connector 2.8s cubic-bezier(.22, 1, .36, 1) forwards;
}

.compact-step:hover {
  color: var(--ps-heading);
}

.compact-step-label {
  position: relative;
  z-index: 2;
  overflow: hidden;
  max-width: 100%;
  padding: 0 2px;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-dot,
.event-dot {
  position: relative;
  z-index: 2;
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: 999px;
  background: #aaada6;
}

.compact-step.success .compact-dot,
.event-dot.success {
  background: var(--ps-primary);
}

.compact-step.running .compact-dot,
.event-dot.running {
  background: var(--ps-accent);
  box-shadow: 0 0 0 4px rgba(201, 93, 66, 0.12);
}

.compact-step.failed .compact-dot,
.event-dot.failed {
  background: var(--ps-danger);
}

@keyframes extend-workflow-connector {
  from { transform: scaleX(0); }
  to { transform: scaleX(1); }
}

.drawer-intro {
  margin-bottom: 16px;
  padding: 12px;
  border: 1px solid var(--ps-border);
  border-radius: var(--ps-radius);
  background: var(--ps-surface-soft);
}

.drawer-intro p {
  margin: 8px 0 0;
  color: var(--ps-muted);
  line-height: 1.6;
}

.event-list {
  --el-collapse-header-height: auto;
  --el-collapse-header-bg-color: transparent;
  --el-collapse-content-bg-color: transparent;
  border-top: 1px solid var(--ps-border);
}

.event-title {
  display: grid;
  width: 100%;
  grid-template-columns: 10px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 12px 10px 12px 2px;
}

.event-title strong,
.event-title span {
  display: block;
}

.event-title strong {
  color: var(--ps-heading);
  font-size: 13px;
}

.event-title span {
  margin-top: 2px;
  color: var(--ps-muted);
  font-size: 11px;
}

.event-title time {
  color: var(--ps-muted);
  font-size: 11px;
}

.event-body {
  display: grid;
  gap: 12px;
  padding: 0 2px 14px 20px;
}

.event-body > p {
  margin: 0;
  color: var(--ps-muted-strong);
  line-height: 1.65;
}

.event-body dl {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
}

.event-body dl > div {
  padding: 9px;
  border: 1px solid var(--ps-border);
  border-radius: var(--ps-radius);
  background: var(--ps-surface-quiet);
}

.event-body dt {
  color: var(--ps-muted);
  font-size: 10px;
  font-weight: 800;
}

.event-body dd {
  margin: 4px 0 0;
  color: var(--ps-heading);
  font-size: 12px;
}

.technical-detail {
  --el-collapse-header-bg-color: transparent;
  --el-collapse-content-bg-color: transparent;
  border-bottom: 0;
}

.technical-detail pre {
  max-height: 360px;
  margin: 0;
  overflow: auto;
  padding: 12px;
  border-radius: var(--ps-radius);
  color: #f7f4ea;
  background: var(--ps-bg-ink);
  font-size: 11px;
  line-height: 1.6;
  white-space: pre-wrap;
}

@media (max-width: 1120px) {
  .status-center {
    top: 76px;
  }
}

@media (max-width: 900px) {
  .workflow-meter {
    grid-template-columns: 80px minmax(120px, 1fr);
  }

  .compact-steps {
    grid-column: 1 / -1;
    overflow-x: auto;
    padding-bottom: 2px;
  }

  .compact-step {
    min-width: 84px;
  }
}

@media (max-width: 700px) {
  .status-center {
    top: 72px;
    padding: 12px;
  }

  .status-summary {
    grid-template-columns: 36px minmax(0, 1fr);
    align-items: start;
  }

  .status-mark {
    width: 34px;
    height: 34px;
  }

  .status-actions {
    grid-column: 1 / -1;
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .status-copy h2 {
    font-size: 15px;
  }

  .status-copy p {
    white-space: normal;
  }

  .compact-steps {
    display: flex;
  }

  .event-body dl {
    grid-template-columns: 1fr;
  }
}
</style>
