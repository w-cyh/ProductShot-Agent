<template>
  <section class="page">
    <el-result icon="info" title="交付已整合到商品工作台" sub-title="在工作台中下载图片并复制各平台当前文案。">
      <template #extra><RouterLink :to="`/studio/${id}`"><el-button type="primary">返回商品工作台</el-button></RouterLink></template>
    </el-result>
  </section>
</template>

<script setup lang="ts">
defineProps<{ id: string }>()
</script>
