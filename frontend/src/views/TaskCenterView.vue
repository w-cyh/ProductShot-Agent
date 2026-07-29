<template>
  <section class="task-center-page">
    <header class="task-center-header">
      <div>
        <span class="task-kicker">GLOBAL PRODUCTION QUEUE</span>
        <h1>任务中心</h1>
        <p>集中查看所有商品的长耗时出图与评分任务；每个项目内部串行，不同项目可以并行处理。</p>
      </div>
      <div class="task-header-metrics">
        <strong>{{ pageData.total }}</strong>
        <span>当前筛选任务</span>
      </div>
    </header>

    <section class="task-toolbar" aria-label="任务筛选">
      <el-radio-group v-model="status" size="small" @change="loadTasks">
        <el-radio-button label="active">进行中</el-radio-button>
        <el-radio-button label="all">全部</el-radio-button>
        <el-radio-button label="success">已完成</el-radio-button>
        <el-radio-button label="failed">失败</el-radio-button>
      </el-radio-group>
      <el-button :loading="loading" @click="loadTasks">刷新</el-button>
    </section>

    <section v-loading="loading" class="task-list">
      <article v-for="task in pageData.items" :key="task.id" class="task-card" :class="`task-${task.status}`">
        <div class="task-status-rail" :aria-label="taskStatusLabel(task)"></div>
        <div class="task-card-main">
          <div class="task-card-topline">
            <span>任务 #{{ task.id }}</span>
            <el-tag :type="taskTagType(task.status)" effect="plain">{{ taskStatusLabel(task) }}</el-tag>
          </div>
          <h2>{{ task.project_name }}</h2>
          <p>{{ task.plan_name || '历史创意方向' }} · 第 {{ task.iteration }} 轮{{ task.parent_image_label ? ` · ${task.parent_image_label}` : ' · 商品原图' }}</p>
          <div class="task-progress-grid">
            <div>
              <span>素材返回</span>
              <strong>{{ task.generated_count }}/{{ task.requested_count }}</strong>
            </div>
            <div>
              <span>质量评分</span>
              <strong>{{ task.reviewed_count }}/{{ task.generated_count || task.requested_count }}</strong>
            </div>
            <div>
              <span>状态</span>
              <strong>{{ stageLabel(task.progress_stage) }}</strong>
            </div>
          </div>
          <p v-if="task.error_message" class="task-error">{{ task.error_message }}</p>
        </div>
        <div class="task-card-actions">
          <span>{{ elapsed(task) }}</span>
          <el-button text type="primary" @click="openProject(task.project_id)">进入项目</el-button>
          <el-button v-if="task.status === 'failed'" type="primary" :loading="retryingTaskId === task.id" @click="retry(task)">重试</el-button>
        </div>
      </article>

      <el-empty v-if="!loading && !pageData.items.length" description="这里会显示跨项目的出图与评分任务" />
    </section>

    <el-pagination
      v-if="pageData.total > pageSize"
      v-model:current-page="page"
      :page-size="pageSize"
      layout="prev, pager, next"
      :total="pageData.total"
      @current-change="loadTasks"
    />
  </section>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { errorMessage } from '../api/client'
import {
  listGenerationTasks,
  retryGenerationTask,
  type GenerationTaskCenterItem,
  type GenerationTaskPage
} from '../api/productshot'

const router = useRouter()
const status = ref('active')
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const retryingTaskId = ref<number | null>(null)
const pageData = ref<GenerationTaskPage>({ items: [], total: 0, page: 1, page_size: pageSize })
let pollTimer: ReturnType<typeof window.setInterval> | null = null

onMounted(() => {
  loadTasks()
  pollTimer = window.setInterval(() => {
    if (status.value === 'active') loadTasks(false)
  }, 2500)
})

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
})

watch(status, () => {
  page.value = 1
})

async function loadTasks(showLoading = true) {
  if (showLoading) loading.value = true
  try {
    pageData.value = await listGenerationTasks(status.value, page.value, pageSize)
  } catch (error) {
    if (showLoading) ElMessage.error(errorMessage(error))
  } finally {
    if (showLoading) loading.value = false
  }
}

async function retry(task: GenerationTaskCenterItem) {
  retryingTaskId.value = task.id
  try {
    await retryGenerationTask(task.project_id, task.id)
    status.value = 'active'
    page.value = 1
    await loadTasks()
    ElMessage.success('已使用原 Prompt Pack 重新提交任务')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    retryingTaskId.value = null
  }
}

function openProject(projectId: number) {
  router.push(`/studio/${projectId}`)
}

function taskStatusLabel(task: GenerationTaskCenterItem) {
  if (task.status === 'failed') return '失败，可重试'
  if (task.status === 'success') return '已完成'
  if (task.progress_stage === 'reviewing') return '评分中'
  if (task.status === 'queued') return '等待处理'
  return '出图中'
}

function stageLabel(stage: string) {
  const labels: Record<string, string> = {
    queued: '等待处理',
    generating: '模型出图',
    reviewing: '质量评分',
    completed: '已完成',
    failed: '失败'
  }
  return labels[stage] || stage
}

function taskTagType(statusValue: string) {
  if (statusValue === 'success') return 'success'
  if (statusValue === 'failed') return 'danger'
  if (statusValue === 'queued') return 'warning'
  return 'primary'
}

function elapsed(task: GenerationTaskCenterItem) {
  const start = new Date(task.started_at || task.created_at).getTime()
  const end = task.completed_at ? new Date(task.completed_at).getTime() : Date.now()
  const minutes = Math.max(0, Math.floor((end - start) / 60000))
  return minutes ? `已耗时 ${minutes} 分钟` : '刚刚开始'
}
</script>

<style scoped>
.task-center-page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 34px 36px 54px;
}

.task-center-header {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 28px 30px;
  border: 1px solid var(--ps-border);
  border-radius: 20px;
  background: radial-gradient(circle at 88% 20%, rgba(238, 116, 43, 0.15), transparent 28%), #fffdfb;
}

.task-kicker {
  color: var(--ps-primary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.task-center-header h1 {
  margin: 6px 0 8px;
  font-family: 'Bodoni 72', Georgia, serif;
  font-size: 38px;
  font-weight: 600;
}

.task-center-header p {
  max-width: 660px;
  margin: 0;
  color: var(--ps-muted);
}

.task-header-metrics {
  display: grid;
  min-width: 120px;
  align-content: center;
  text-align: right;
}

.task-header-metrics strong {
  color: var(--ps-primary);
  font-family: 'Bodoni 72', Georgia, serif;
  font-size: 42px;
  line-height: 1;
}

.task-header-metrics span { color: var(--ps-muted); font-size: 12px; }

.task-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  margin: 22px 0 14px;
}

.task-list { display: grid; gap: 11px; min-height: 220px; }

.task-card {
  display: grid;
  grid-template-columns: 5px minmax(0, 1fr) auto;
  overflow: hidden;
  border: 1px solid var(--ps-border);
  border-radius: 15px;
  background: #fff;
}

.task-status-rail { background: var(--ps-primary); }
.task-success .task-status-rail { background: #5a9c72; }
.task-failed .task-status-rail { background: #c9554d; }
.task-queued .task-status-rail { background: #d49a36; }

.task-card-main { padding: 16px 18px; }
.task-card-topline { display: flex; justify-content: space-between; gap: 10px; color: var(--ps-muted); font-size: 12px; }
.task-card h2 { margin: 8px 0 2px; font-size: 17px; }
.task-card p { margin: 0; color: var(--ps-muted); font-size: 13px; }

.task-progress-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 14px;
}

.task-progress-grid div { padding: 8px 10px; border-radius: 8px; background: var(--ps-surface-soft); }
.task-progress-grid span { display: block; color: var(--ps-muted); font-size: 11px; }
.task-progress-grid strong { font-size: 13px; }
.task-error { margin-top: 10px !important; color: #b74942 !important; }

.task-card-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: center;
  gap: 7px;
  min-width: 126px;
  padding: 16px;
}

.task-card-actions > span { color: var(--ps-muted); font-size: 11px; }

@media (max-width: 720px) {
  .task-center-page { padding: 18px; }
  .task-center-header, .task-toolbar { align-items: stretch; flex-direction: column; }
  .task-header-metrics { text-align: left; }
  .task-card { grid-template-columns: 5px minmax(0, 1fr); }
  .task-card-actions { grid-column: 2; flex-direction: row; justify-content: flex-start; align-items: center; padding-top: 0; }
  .task-progress-grid { grid-template-columns: 1fr; }
}
</style>
