<template>
  <el-drawer
    :model-value="modelValue"
    class="comparison-drawer"
    title="原图与生成图对比"
    direction="rtl"
    size="min(1080px, 100vw)"
    append-to-body
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div v-if="selectedImage" class="comparison-layout">
      <section class="comparison-pane">
        <div class="comparison-pane-head">
          <div>
            <span>Source</span>
            <h3>商品原图</h3>
          </div>
          <el-tag>保真参考</el-tag>
        </div>
        <div class="comparison-frame">
          <img v-if="sourceUrl" :src="sourceUrl" alt="商品原图" />
          <el-empty v-else description="暂无商品原图" />
        </div>
      </section>

      <section class="comparison-pane">
        <div class="comparison-pane-head">
          <div>
            <span>Generated</span>
            <h3>当前生成图</h3>
          </div>
          <el-tag v-if="selectedImage.is_selected" type="success">当前交付图</el-tag>
          <span v-else class="comparison-score">当前对比图</span>
        </div>
        <div class="comparison-frame">
          <img :src="assetUrl(selectedImage.image_url)" alt="当前选择的生成图" />
        </div>
      </section>
    </div>

    <div v-if="images.length > 1" class="comparison-strip" aria-label="选择要对比的生成图">
      <button
        v-for="(image, index) in images"
        :key="image.id"
        type="button"
        :class="{ selected: image.id === selectedImageId }"
        :aria-pressed="image.id === selectedImageId"
        :aria-label="`对比第 ${index + 1} 张生成图`"
        @click="$emit('select', image.id)"
      >
        <img :src="assetUrl(image.image_url)" alt="" />
        <span>{{ image.is_selected ? '交付图' : `图片 ${index + 1}` }}</span>
      </button>
    </div>

    <el-empty v-if="!selectedImage" description="请先选择一张生成图" />
  </el-drawer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { GeneratedImage } from '../api/productshot'
import { assetUrl } from '../api/client'

const props = defineProps<{
  modelValue: boolean
  sourceUrl: string
  images: GeneratedImage[]
  selectedImageId: number | null
}>()

defineEmits<{
  'update:modelValue': [value: boolean]
  select: [imageId: number]
}>()

const selectedImage = computed(
  () =>
    props.images.find((image) => image.id === props.selectedImageId) ||
    props.images[0]
)
</script>

<style scoped>
.comparison-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.comparison-pane {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.comparison-pane-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
}

.comparison-pane-head span {
  color: var(--ps-muted);
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.comparison-pane-head h3 {
  margin: 3px 0 0;
  color: var(--ps-heading);
  font-family: Georgia, "Times New Roman", "Songti SC", serif;
  font-size: 23px;
  font-weight: 650;
}

.comparison-pane-head .comparison-score {
  color: var(--ps-accent-dark);
  font-size: 13px;
  letter-spacing: 0;
}

.comparison-frame {
  display: grid;
  min-height: 480px;
  place-items: center;
  overflow: hidden;
  border: 1px solid var(--ps-border);
  border-radius: var(--ps-radius);
  background:
    linear-gradient(135deg, rgba(36, 88, 70, 0.05), rgba(201, 93, 66, 0.04)),
    var(--ps-surface-soft);
}

.comparison-frame img {
  display: block;
  width: 100%;
  height: 100%;
  max-height: 68vh;
  object-fit: contain;
}

.comparison-strip {
  display: flex;
  gap: 9px;
  overflow-x: auto;
  margin-top: 16px;
  padding: 12px 0 2px;
  border-top: 1px solid var(--ps-border);
}

.comparison-strip button {
  display: grid;
  width: 82px;
  flex: 0 0 82px;
  gap: 5px;
  padding: 5px;
  border: 1px solid var(--ps-border);
  border-radius: var(--ps-radius);
  color: var(--ps-muted);
  background: var(--ps-surface);
  cursor: pointer;
}

.comparison-strip button.selected {
  border-color: var(--ps-accent);
  color: var(--ps-accent-dark);
  box-shadow: 0 0 0 2px rgba(201, 93, 66, 0.1);
}

.comparison-strip img {
  width: 70px;
  height: 70px;
  border-radius: 5px;
  object-fit: cover;
}

.comparison-strip span {
  overflow: hidden;
  font-size: 10px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 760px) {
  .comparison-layout {
    grid-template-columns: 1fr;
  }

  .comparison-frame {
    min-height: 300px;
  }

  .comparison-frame img {
    max-height: 52vh;
  }
}
</style>
