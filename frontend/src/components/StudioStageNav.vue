<template>
  <nav class="stage-nav" aria-label="项目生产阶段">
    <button
      v-for="(stage, index) in stages"
      :key="stage.key"
      class="stage-nav-item"
      :class="[stage.status, { selected: modelValue === stage.key }]"
      type="button"
      :disabled="!stage.available"
      :aria-current="modelValue === stage.key ? 'step' : undefined"
      :title="stage.available ? stage.description : stage.lockedReason"
      @click="$emit('update:modelValue', stage.key)"
    >
      <span class="stage-number" aria-hidden="true">
        <el-icon v-if="stage.status === 'success'" :size="15"><Check /></el-icon>
        <el-icon v-else-if="stage.status === 'failed'" :size="15"><Warning /></el-icon>
        <el-icon v-else-if="stage.status === 'running'" class="is-loading" :size="15"><Loading /></el-icon>
        <span v-else>{{ index + 1 }}</span>
      </span>
      <span class="stage-copy">
        <strong>{{ stage.title }}</strong>
        <small>{{ stage.available ? stage.description : stage.lockedReason }}</small>
      </span>
      <span class="stage-state">{{ statusLabel(stage.status) }}</span>
    </button>
  </nav>
</template>

<script setup lang="ts">
import { Check, Loading, Warning } from '@element-plus/icons-vue'
import type { StudioStage, StudioStageKey, StudioStageStatus } from '../stores/project'

defineProps<{
  stages: StudioStage[]
  modelValue: StudioStageKey
}>()

defineEmits<{
  'update:modelValue': [value: StudioStageKey]
}>()

function statusLabel(status: StudioStageStatus) {
  const labels: Record<StudioStageStatus, string> = {
    locked: '未解锁',
    available: '可查看',
    current: '当前',
    running: '运行中',
    success: '已完成',
    failed: '失败'
  }
  return labels[status]
}
</script>

<style scoped>
.stage-nav {
  display: grid;
  gap: 6px;
}

.stage-nav-item {
  position: relative;
  display: grid;
  width: 100%;
  grid-template-columns: 30px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  padding: 12px;
  border: 1px solid transparent;
  border-radius: var(--ps-radius);
  color: var(--ps-muted-strong);
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 160ms ease,
    background 160ms ease,
    transform 160ms ease;
}

.stage-nav-item:hover:not(:disabled) {
  border-color: rgba(36, 88, 70, 0.14);
  background: rgba(251, 250, 246, 0.72);
  transform: translateX(2px);
}

.stage-nav-item.selected {
  border-color: rgba(36, 88, 70, 0.2);
  background: var(--ps-primary-soft);
}

.stage-nav-item.running {
  border-color: rgba(201, 93, 66, 0.28);
}

.stage-nav-item.failed {
  border-color: rgba(185, 64, 61, 0.28);
  background: rgba(185, 64, 61, 0.06);
}

.stage-nav-item:disabled {
  opacity: 0.54;
  cursor: not-allowed;
}

.stage-number {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border: 1px solid var(--ps-border-strong);
  border-radius: 999px;
  color: var(--ps-muted);
  background: var(--ps-surface);
  font-size: 12px;
  font-weight: 850;
}

.selected .stage-number,
.current .stage-number {
  border-color: var(--ps-primary);
  color: #fff;
  background: var(--ps-primary);
}

.success .stage-number {
  border-color: var(--ps-primary);
  color: #fff;
  background: var(--ps-primary);
}

.running .stage-number {
  border-color: var(--ps-accent);
  color: #fff;
  background: var(--ps-accent);
}

.failed .stage-number {
  border-color: var(--ps-danger);
  color: #fff;
  background: var(--ps-danger);
}

.stage-copy {
  min-width: 0;
}

.stage-copy strong,
.stage-copy small {
  display: block;
}

.stage-copy strong {
  color: var(--ps-heading);
  font-size: 14px;
  line-height: 1.35;
}

.stage-copy small {
  margin-top: 4px;
  overflow: hidden;
  color: var(--ps-muted);
  font-size: 11px;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stage-state {
  position: absolute;
  top: 12px;
  right: 10px;
  color: var(--ps-muted);
  font-size: 10px;
  font-weight: 800;
}

.stage-copy strong {
  padding-right: 42px;
}

@media (max-width: 1040px) {
  .stage-nav {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding-bottom: 4px;
    scrollbar-width: thin;
  }

  .stage-nav-item {
    width: 210px;
    flex: 0 0 210px;
  }

  .stage-nav-item:hover:not(:disabled) {
    transform: translateY(-1px);
  }
}

@media (max-width: 620px) {
  .stage-nav-item {
    width: 168px;
    flex-basis: 168px;
    padding: 10px;
  }

  .stage-copy small,
  .stage-state {
    display: none;
  }

  .stage-copy strong {
    padding-right: 0;
    font-size: 13px;
  }
}
</style>
