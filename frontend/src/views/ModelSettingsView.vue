<template>
  <section class="page model-page">
    <div class="page-header settings-header">
      <div>
        <p class="eyebrow">Model API Layer</p>
        <h1 class="page-title">模型管理</h1>
        <p class="page-description">仅支持 OpenAI 与百炼。密钥只从后端环境变量读取，未配置真实模型时工作流会返回错误。</p>
      </div>
      <div class="settings-actions">
        <el-button @click="loadSettings">刷新</el-button>
        <el-button :loading="testing" @click="testConnection">测试文字模型连接</el-button>
        <el-button class="orange-button" type="primary" :loading="saving" @click="saveSettings">保存配置</el-button>
      </div>
    </div>

    <el-alert v-if="error" class="settings-alert" type="error" :title="error" :closable="false" show-icon />

    <div class="settings-shell">
      <aside class="settings-rail panel panel-pad">
        <p class="section-kicker">Provider status</p>
        <h2 class="section-title">密钥状态</h2>
        <div class="status-stack">
          <div v-for="provider in providers" :key="provider" class="status-row">
            <span class="status-dot" :class="form.providers[provider].api_key_configured ? 'success' : ''"></span>
            <div><strong>{{ providerLabel(provider) }}</strong><small>{{ form.providers[provider].api_key_configured ? '后端密钥已配置' : '后端未检测到密钥' }}</small></div>
          </div>
          <div class="status-row"><span class="status-dot running"></span><div><strong>Secret policy</strong><small>密钥不会传入浏览器或保存在配置接口中</small></div></div>
        </div>
      </aside>

      <main class="settings-main">
        <div class="settings-grid">
          <section class="panel panel-pad settings-panel">
            <div class="panel-heading"><div><p class="section-kicker">Reasoning & vision</p><h2>推理与图片理解</h2><p>文字任务使用文本模型；原图理解和生成图评分必须使用支持图片输入的多模态模型。</p></div></div>
            <el-skeleton v-if="loading" :rows="5" animated />
            <el-form v-else label-position="top">
              <el-form-item label="Provider"><el-select v-model="form.text_provider"><el-option v-for="provider in providers" :key="provider" :label="providerLabel(provider)" :value="provider" /></el-select></el-form-item>
              <template v-if="form.text_provider">
                <el-form-item label="文字推理模型">
                  <el-input v-model="form.providers[form.text_provider].text_model" placeholder="填写普通文字模型 ID" />
                </el-form-item>
                <el-alert
                  v-if="form.text_provider === 'dashscope'"
                  class="vision-alert"
                  :type="form.providers.dashscope.vision_model.trim() ? 'info' : 'warning'"
                  :title="form.providers.dashscope.vision_model.trim() ? '图片理解将使用独立的 DashScope 多模态模型。' : '请配置图片理解模型，否则原图理解和图片评分无法运行。'"
                  :closable="false"
                  show-icon
                />
                <el-form-item v-if="form.text_provider === 'dashscope'" label="图片理解模型（多模态）" required>
                  <el-input v-model="form.providers.dashscope.vision_model" placeholder="例如 qwen3-vl-plus" />
                  <p class="field-help">必须是支持 MultiModalConversation 和图片输入的模型，不能填写普通文本模型。</p>
                </el-form-item>
                <el-form-item label="Base URL"><el-input v-model="form.providers[form.text_provider].base_url" /></el-form-item>
              </template>
            </el-form>
          </section>

          <section class="panel panel-pad settings-panel">
            <div class="panel-heading"><div><p class="section-kicker">Image generation</p><h2>图片生成</h2><p>生成和编辑均调用所选真实平台，不再复制原图或生成占位图。</p></div></div>
            <el-skeleton v-if="loading" :rows="5" animated />
            <el-form v-else label-position="top">
              <el-form-item label="Provider"><el-select v-model="form.image_provider"><el-option v-for="provider in providers" :key="provider" :label="providerLabel(provider)" :value="provider" /></el-select></el-form-item>
              <template v-if="form.image_provider"><el-form-item label="图片模型"><el-input v-model="form.providers[form.image_provider].image_model" placeholder="填写该平台的图片模型 ID" /></el-form-item><el-form-item label="Base URL"><el-input v-model="form.providers[form.image_provider].base_url" /></el-form-item></template>
            </el-form>
          </section>
        </div>

        <section v-if="testResult" class="panel panel-pad test-panel">
          <div class="panel-heading"><div><p class="section-kicker">Connection test</p><h2>最近一次连接测试</h2><p>{{ testResult.message }}</p></div><el-tag :type="testResult.status === 'success' ? 'success' : 'danger'" effect="plain">{{ testResult.status }}</el-tag></div>
          <div class="test-grid"><div><dt>Provider</dt><dd>{{ testResult.provider }}</dd></div><div><dt>模型</dt><dd>{{ testResult.model || '未配置' }}</dd></div><div><dt>耗时</dt><dd>{{ testResult.latency_ms }}ms</dd></div><div><dt>检测时间</dt><dd>{{ new Date(testResult.checked_at).toLocaleString() }}</dd></div></div>
        </section>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { errorMessage } from '../api/client'
import { getModelSettings, type ModelConnectionTest, type ModelSettings, type ProviderModelSettings, testTextModelConnection, updateModelSettings } from '../api/productshot'

const loading = ref(true), saving = ref(false), testing = ref(false), error = ref('')
const testResult = ref<ModelConnectionTest | null>(null)
const providers = ['openai', 'dashscope'] as const
const form = reactive<{ text_provider: string; image_provider: string; providers: Record<string, ProviderModelSettings> }>({
  text_provider: '', image_provider: '',
  providers: {
    openai: { text_model: '', vision_model: '', image_model: '', base_url: '', api_key_configured: false },
    dashscope: { text_model: '', vision_model: '', image_model: '', base_url: '', api_key_configured: false }
  }
})

function providerLabel(provider: string) { return provider === 'openai' ? 'OpenAI' : '百炼（DashScope）' }
function syncForm(next: ModelSettings) {
  form.text_provider = next.text_provider
  form.image_provider = next.image_provider
  for (const provider of providers) Object.assign(form.providers[provider], next.providers[provider])
}
async function loadSettings() { loading.value = true; error.value = ''; try { syncForm(await getModelSettings()) } catch (err) { error.value = errorMessage(err) } finally { loading.value = false } }
async function saveSettings() {
  saving.value = true; error.value = ''
  if (form.text_provider === 'dashscope' && !form.providers.dashscope.vision_model.trim()) {
    error.value = '请先填写 DashScope 图片理解模型；原图理解和图片评分需要多模态模型。'
    saving.value = false
    return
  }
  try { syncForm(await updateModelSettings({ text_provider: form.text_provider, image_provider: form.image_provider, providers: form.providers })); ElMessage.success('模型配置已更新') } catch (err) { error.value = errorMessage(err) } finally { saving.value = false }
}
async function testConnection() {
  testing.value = true; error.value = ''
  try { testResult.value = await testTextModelConnection(); ElMessage[testResult.value.status === 'success' ? 'success' : 'warning'](testResult.value.message) } catch (err) { error.value = errorMessage(err) } finally { testing.value = false }
}
onMounted(loadSettings)
</script>

<style scoped>
.model-page { max-width: 1280px; }.settings-header { align-items: flex-end; }.settings-alert { margin-bottom: 12px; }.settings-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }.settings-shell { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 14px; align-items: start; }.settings-rail { position: sticky; top: 22px; display: grid; gap: 14px; }.status-stack, .settings-main { display: grid; gap: 10px; }.status-row { display: grid; grid-template-columns: 10px minmax(0, 1fr); gap: 10px; padding: 10px; border: 1px solid var(--ps-border); border-radius: var(--ps-radius); background: var(--ps-surface-quiet); }.status-row strong, .status-row small { display: block; }.status-row small, .panel-heading p, .field-help, dd { color: var(--ps-muted); }.status-row small { margin-top: 4px; font-size: 12px; line-height: 1.45; }.settings-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }.panel-heading { display: flex; justify-content: space-between; gap: 14px; margin-bottom: 16px; }.panel-heading h2 { margin: 0; color: var(--ps-heading); font-size: 20px; }.panel-heading p { margin: 7px 0 0; line-height: 1.65; }.vision-alert { margin-bottom: 16px; }.field-help { margin: 7px 0 0; font-size: 12px; line-height: 1.6; }.test-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }dt { color: var(--ps-primary); font-size: 12px; font-weight: 800; }dd { margin: 6px 0 0; line-height: 1.6; word-break: break-word; }@media (max-width: 840px) { .settings-shell, .settings-grid { grid-template-columns: 1fr; }.settings-rail { position: static; } }
</style>
