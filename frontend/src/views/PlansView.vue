<template>
  <section class="page">
    <el-result icon="info" title="创意方向已整合到商品工作台" sub-title="请在工作台中先确认商品策略，再选择方向并开始生图。">
      <template #extra><RouterLink :to="`/studio/${id}`"><el-button type="primary">返回商品工作台</el-button></RouterLink></template>
    </el-result>
  </section>
</template>

<script setup lang="ts">
defineProps<{ id: string }>()
</script>
