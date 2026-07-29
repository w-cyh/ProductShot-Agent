<template>
  <section class="page">
    <el-result icon="info" title="工作流已整合到商品工作台" sub-title="原图理解、确认和商品策略现在按阶段显式推进。">
      <template #extra><RouterLink :to="`/studio/${id}`"><el-button type="primary">返回商品工作台</el-button></RouterLink></template>
    </el-result>
  </section>
</template>

<script setup lang="ts">
defineProps<{ id: string }>()
</script>
