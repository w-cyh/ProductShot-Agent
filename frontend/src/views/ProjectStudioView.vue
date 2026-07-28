<template>
  <section class="page studio-page">
    <header class="studio-header">
      <div>
        <span class="eyebrow">Project Studio</span>
        <h1 class="page-title">{{ pageTitle }}</h1>
        <p class="page-description">{{ pageDescription }}</p>
      </div>
      <div v-if="hasProject" class="studio-header-actions">
        <el-button :href="markdownExportUrl(projectId)" tag="a" target="_blank">导出 Markdown</el-button>
        <el-button :href="jsonExportUrl(projectId)" tag="a" target="_blank">导出 JSON</el-button>
      </div>
    </header>

    <WorkflowStatusCenter
      :status="workflowDisplay.status"
      :title="workflowDisplay.title"
      :message="workflowDisplay.message"
      :primary-label="workflowDisplay.primaryLabel"
      :started-at="workflowDisplay.startedAt"
      :steps="store.steps"
      :events="store.current?.workflow_events || []"
      @primary="handleStatusPrimary"
    />

    <div class="focused-workspace">
      <aside class="stage-rail">
        <div class="stage-rail-heading">
          <span>Production path</span>
          <strong>5 个生产阶段</strong>
        </div>
        <StudioStageNav :model-value="selectedStage" :stages="studioStages" @update:model-value="selectStage" />
      </aside>

      <main class="stage-workspace">
        <section v-if="selectedStage === 'brief'" class="stage-section">
          <div class="stage-heading">
            <div>
              <span class="stage-kicker">01 · 商品与原图</span>
              <h2>{{ hasProject ? '商品生产简报' : '创建商品营销项目' }}</h2>
              <p>{{ hasProject ? '这里保留生产所需的商品上下文，需要时可以随时回来核对。' : '填写最少的商品信息并上传一张可靠原图。' }}</p>
            </div>
            <el-tag v-if="store.current">{{ statusLabel(store.current.status) }}</el-tag>
          </div>

          <template v-if="!hasProject">
            <div class="creation-layout">
              <el-form class="brief-form" label-position="top" :model="form" @submit.prevent>
                <div class="form-grid">
                  <el-form-item label="商品名称">
                    <el-input v-model="form.product_name" placeholder="例如：手工香薰蜡烛" />
                  </el-form-item>
                  <el-form-item label="商品类别">
                    <el-input v-model="form.product_category" placeholder="例如：家居香氛" />
                  </el-form-item>
                </div>
                <el-form-item label="核心卖点">
                  <el-input
                    v-model="form.core_selling_points"
                    type="textarea"
                    :rows="4"
                    placeholder="手工制作、香味舒缓、适合作为礼物"
                  />
                </el-form-item>
                <div class="form-grid">
                  <el-form-item label="目标平台">
                    <el-select v-model="form.target_platform">
                      <el-option label="小红书" value="小红书" />
                      <el-option label="朋友圈" value="朋友圈" />
                      <el-option label="淘宝" value="淘宝" />
                      <el-option label="抖音" value="抖音" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="风格偏好">
                    <el-select v-model="form.preferred_style">
                      <el-option label="小红书生活方式风" value="小红书生活方式风" />
                      <el-option label="高级极简白底风" value="高级极简白底风" />
                      <el-option label="节日礼物促销风" value="节日礼物促销风" />
                    </el-select>
                  </el-form-item>
                </div>
                <el-form-item label="目标人群">
                  <el-input v-model="form.target_audience" placeholder="例如：年轻女性、租房独居人群、礼物购买者" />
                </el-form-item>
              </el-form>

              <div class="upload-workbench">
                <div class="upload-preview">
                  <img v-if="localPreviewUrl" :src="localPreviewUrl" alt="待上传商品预览" />
                  <div v-else class="upload-placeholder">
                    <span>Source image</span>
                    <strong>一张清晰原图<br />开启整条生产线</strong>
                    <p>建议主体完整、文字可辨识，避免严重遮挡。</p>
                  </div>
                </div>
                <el-upload
                  drag
                  :auto-upload="false"
                  :show-file-list="false"
                  accept=".jpg,.jpeg,.png,.webp"
                  :on-change="handleFile"
                >
                  <div class="upload-copy">{{ selectedFile ? '更换商品图' : '点击或拖拽上传商品图' }}</div>
                  <div class="upload-subcopy">支持 JPG、PNG、WebP</div>
                </el-upload>
              </div>
            </div>

            <footer class="stage-action-bar">
              <p>创建后先进行原图理解，并由你确认商品保真约束。</p>
              <el-button class="orange-button" type="primary" size="large" :loading="creating" @click="createStudioProject">
                创建项目并开始分析
              </el-button>
            </footer>
          </template>

          <template v-else-if="store.current">
            <div class="brief-overview">
              <dl class="brief-summary">
                <div>
                  <dt>商品名称</dt>
                  <dd>{{ store.current.product_name }}</dd>
                </div>
                <div>
                  <dt>商品类别</dt>
                  <dd>{{ store.current.product_category || '未填写' }}</dd>
                </div>
                <div>
                  <dt>目标平台</dt>
                  <dd>{{ store.current.target_platform }}</dd>
                </div>
                <div>
                  <dt>风格偏好</dt>
                  <dd>{{ store.current.preferred_style || '未填写' }}</dd>
                </div>
                <div>
                  <dt>目标人群</dt>
                  <dd>{{ store.current.target_audience || '未填写' }}</dd>
                </div>
                <div>
                  <dt>核心卖点</dt>
                  <dd>{{ store.current.core_selling_points || '未填写' }}</dd>
                </div>
              </dl>
              <div class="source-card">
                <div class="source-card-head">
                  <span>商品原图</span>
                  <small>后续所有阶段的保真参考</small>
                </div>
                <div class="source-frame">
                  <img v-if="previewImageUrl" :src="previewImageUrl" alt="商品原图" />
                  <el-empty v-else description="暂无原图" />
                </div>
              </div>
            </div>

            <footer class="stage-action-bar">
              <p>商品信息已经就绪，下一步是理解原图并确认关键视觉特征。</p>
              <el-button type="primary" @click="goToAnalysis">查看分析与确认</el-button>
            </footer>
          </template>
        </section>

        <section v-else-if="selectedStage === 'analysis'" class="stage-section">
          <div class="stage-heading">
            <div>
              <span class="stage-kicker">02 · 分析与确认</span>
              <h2>确认商品理解，再形成营销策略</h2>
              <p>原图、人工修正和商品策略被放在同一个任务上下文中。</p>
            </div>
            <el-button
              v-if="!store.current?.latest_analysis"
              class="orange-button"
              type="primary"
              :loading="runningAnalysis"
              @click="runWorkflow"
            >
              {{ analysisActionLabel }}
            </el-button>
          </div>

          <el-skeleton v-if="store.loading" :rows="6" animated />

          <div v-else-if="visualReviewPending" class="analysis-review-layout">
            <div class="analysis-source">
              <div class="source-frame analysis-source-frame">
                <img v-if="previewImageUrl" :src="previewImageUrl" alt="待审核商品原图" />
              </div>
              <div>
                <span class="attention-label">需要你的确认</span>
                <h3>模型已经完成原图理解</h3>
                <p>重点核对外观、材质、可见文字和不能改变的商品特征。</p>
              </div>
            </div>

            <el-form class="visual-review-form" label-position="top" @submit.prevent>
              <el-form-item label="商品外观理解">
                <el-input v-model="visualReview.product_appearance" type="textarea" :rows="3" />
              </el-form-item>
              <div class="form-grid">
                <el-form-item label="主色调">
                  <el-input v-model="visualReview.dominant_colors" type="textarea" :rows="3" />
                </el-form-item>
                <el-form-item label="材质">
                  <el-input v-model="visualReview.materials" type="textarea" :rows="3" />
                </el-form-item>
              </div>
              <el-form-item label="可见文字 / Logo">
                <el-input v-model="visualReview.visible_text_or_logo" type="textarea" :rows="2" />
              </el-form-item>
              <el-form-item label="主体清晰度判断">
                <el-input v-model="visualReview.subject_clarity" type="textarea" :rows="2" />
              </el-form-item>
              <div class="form-grid">
                <el-form-item label="原图问题">
                  <el-input v-model="visualReview.background_issues" type="textarea" :rows="4" />
                </el-form-item>
                <el-form-item label="保真约束">
                  <el-input v-model="visualReview.fidelity_constraints" type="textarea" :rows="4" />
                </el-form-item>
              </div>
              <el-form-item label="营销机会">
                <el-input v-model="visualReview.marketing_opportunities" type="textarea" :rows="3" />
              </el-form-item>
              <el-form-item label="人工审核意见">
                <el-input
                  v-model="visualReview.review_notes"
                  type="textarea"
                  :rows="3"
                  placeholder="例如：Logo 必须保留；不要改变瓶身比例。"
                />
              </el-form-item>
              <div class="form-submit-row">
                <p>确认后将连续生成商品策略与 3 个创意方向。</p>
                <el-button class="orange-button" type="primary" :loading="runningAnalysis" @click="confirmVisualReview">
                  确认审核并生成方向
                </el-button>
              </div>
            </el-form>
          </div>

          <template v-else-if="store.current?.latest_analysis">
            <div class="analysis-result-grid">
              <article class="insight-card featured">
                <span>原图理解</span>
                <h3>{{ store.current.visual_analysis?.analysis.product_appearance || '商品外观已确认' }}</h3>
                <p v-if="store.current.visual_analysis?.analysis.human_review_notes">
                  人工意见：{{ store.current.visual_analysis.analysis.human_review_notes }}
                </p>
                <div class="tag-row">
                  <el-tag
                    v-for="item in store.current.visual_analysis?.analysis.fidelity_constraints || []"
                    :key="item"
                  >
                    {{ item }}
                  </el-tag>
                </div>
              </article>

              <article class="insight-card">
                <span>目标受众</span>
                <h3>平台表达策略</h3>
                <p>{{ store.current.latest_analysis.analysis.target_audience_analysis }}</p>
              </article>

              <article class="insight-card">
                <span>推荐卖点</span>
                <h3>优先传达的信息</h3>
                <ul>
                  <li v-for="item in store.current.latest_analysis.analysis.recommended_selling_points" :key="item">
                    {{ item }}
                  </li>
                </ul>
              </article>

              <article class="insight-card">
                <span>视觉判断</span>
                <h3>推荐风格与原图问题</h3>
                <ul>
                  <li v-for="item in store.current.latest_analysis.analysis.recommended_visual_styles" :key="item">
                    {{ item }}
                  </li>
                  <li v-for="item in store.current.latest_analysis.analysis.image_issues" :key="item">
                    原图：{{ item }}
                  </li>
                </ul>
              </article>
            </div>

            <footer class="stage-action-bar">
              <p>商品策略已经就绪，可以比较不同的营销创意方向。</p>
              <el-button type="primary" @click="selectStage('plans')">查看创意方向</el-button>
            </footer>
          </template>

          <div v-else class="stage-empty">
            <el-empty description="先让模型理解原图，再由你确认关键商品特征">
              <el-button class="orange-button" type="primary" :loading="runningAnalysis" @click="runWorkflow">
                开始理解原图
              </el-button>
            </el-empty>
          </div>
        </section>

        <section v-else-if="selectedStage === 'plans'" class="stage-section">
          <div class="stage-heading">
            <div>
              <span class="stage-kicker">03 · 创意方向</span>
              <h2>选择一个值得生产的营销方向</h2>
              <p>先比较核心卖点与画面差异，详细构想需要时再展开。</p>
            </div>
            <span v-if="store.current?.creative_plans.length" class="metric-pill">
              {{ store.current.creative_plans.length }} 个方向
            </span>
          </div>

          <div v-if="store.current?.creative_plans.length" class="plan-grid">
            <article
              v-for="(plan, index) in store.current.creative_plans"
              :key="plan.id"
              class="plan-card"
              :class="{ selected: generatingPlanId === plan.id }"
            >
              <div class="plan-card-number">{{ String(index + 1).padStart(2, '0') }}</div>
              <div class="plan-card-copy">
                <div class="plan-meta">
                  <span>{{ plan.target_platform }}</span>
                  <span>{{ plan.visual_style }}</span>
                </div>
                <h3>{{ plan.plan_name }}</h3>
                <p>{{ plan.plan.visual_description }}</p>
                <div class="plan-selling-point">
                  <span>主打卖点</span>
                  <strong>{{ plan.plan.main_selling_point }}</strong>
                </div>
                <el-collapse class="plan-details-collapse">
                  <el-collapse-item title="查看方案细节" name="details">
                    <dl>
                      <div>
                        <dt>推荐理由</dt>
                        <dd>{{ plan.plan.recommendation_reason }}</dd>
                      </div>
                      <div>
                        <dt>文案方向</dt>
                        <dd>{{ plan.plan.copywriting_direction }}</dd>
                      </div>
                      <div v-if="plan.plan.expected_outputs.length">
                        <dt>预计产出</dt>
                        <dd>{{ plan.plan.expected_outputs.join('、') }}</dd>
                      </div>
                    </dl>
                  </el-collapse-item>
                </el-collapse>
              </div>
              <el-button
                class="orange-button plan-generate-button"
                type="primary"
                :loading="generatingPlanId === plan.id"
                @click="selectPlan(plan)"
              >
                选择并生成素材
              </el-button>
            </article>
          </div>

          <div v-else class="stage-empty">
            <el-empty description="完成商品分析后，这里会展示 3 个可选方向">
              <el-button type="primary" :loading="runningAnalysis" @click="runWorkflow">生成创意方向</el-button>
            </el-empty>
          </div>
        </section>

        <section v-else-if="selectedStage === 'generation'" class="stage-section">
          <div class="stage-heading">
            <div>
              <span class="stage-kicker">04 · 素材生成</span>
              <h2>生成、评分并挑选营销图片</h2>
              <p>选中图片后可以重新评分，或按需与商品原图进行保真对比。</p>
            </div>
            <span v-if="filteredImages.length" class="metric-pill accent">{{ filteredImages.length }} 张图片</span>
          </div>

          <div v-if="generationIsRunning && !filteredImages.length" class="generation-waiting">
            <div class="generation-orbit" aria-hidden="true"><span></span></div>
            <div>
              <span>Image production</span>
              <h3>生成服务正在排队或出图</h3>
              <p>{{ workflowDisplay.message }}</p>
            </div>
          </div>

          <div v-if="filteredImages.length" class="image-grid">
            <article
              v-for="(image, index) in filteredImages"
              :key="image.id"
              class="generated-card"
              :class="{ selected: selectedImageId === image.id }"
            >
              <button
                class="generated-select"
                type="button"
                :aria-pressed="selectedImageId === image.id"
                :aria-label="`选择第 ${index + 1} 张生成图`"
                @click="selectedImageId = image.id"
              >
                <span v-if="image.is_recommended" class="recommended-ribbon">推荐</span>
                <img :src="assetUrl(image.image_url)" alt="生成营销图片" />
              </button>
              <div class="generated-meta">
                <div>
                  <strong>{{ image.score ? `${image.score} 分` : '待评分' }}</strong>
                  <span>{{ image.platform || '默认平台' }}</span>
                </div>
                <span>{{ image.generation_mode || 'image_to_image' }}</span>
              </div>
              <div class="generated-actions">
                <el-button text @click="openComparison(image.id)">与原图对比</el-button>
                <el-button text type="primary" @click="review(image)">重新评分</el-button>
              </div>
            </article>
          </div>

          <div v-else-if="!generationIsRunning" class="stage-empty">
            <el-empty description="选择一个创意方向后，图片、评分和文案会连续生成">
              <el-button type="primary" @click="selectStage('plans')">返回选择方向</el-button>
            </el-empty>
          </div>

          <footer v-if="filteredImages.length" class="stage-action-bar">
            <p>已选中 {{ selectedImage?.score ? `${selectedImage.score} 分` : '待评分' }} 图片，可继续完善文案或导出。</p>
            <el-button type="primary" @click="selectStage('delivery')">进入交付与迭代</el-button>
          </footer>
        </section>

        <section v-else class="stage-section">
          <div class="stage-heading">
            <div>
              <span class="stage-kicker">05 · 交付与迭代</span>
              <h2>完成文案、修改与素材交付</h2>
              <p>围绕选中的最佳图片完成平台文案、修改计划和导出。</p>
            </div>
            <div class="delivery-export-actions">
              <el-button :href="markdownExportUrl(projectId)" tag="a" target="_blank">Markdown</el-button>
              <el-button :href="jsonExportUrl(projectId)" tag="a" target="_blank">JSON</el-button>
            </div>
          </div>

          <div v-if="selectedImage" class="delivery-layout">
            <aside class="delivery-visual">
              <div class="delivery-image">
                <img :src="assetUrl(selectedImage.image_url)" alt="当前交付图片" />
              </div>
              <div class="delivery-image-head">
                <div>
                  <span>当前交付图</span>
                  <strong>{{ selectedImage.score ? `${selectedImage.score} 分` : '待评分' }}</strong>
                </div>
                <el-tag v-if="selectedImage.is_recommended" type="success">推荐</el-tag>
              </div>
              <div class="delivery-image-actions">
                <el-button @click="openComparison(selectedImage.id)">与原图对比</el-button>
                <el-button type="primary" @click="review(selectedImage)">重新评分</el-button>
              </div>
              <div v-if="filteredImages.length > 1" class="delivery-thumbnails" aria-label="切换交付图片">
                <button
                  v-for="image in filteredImages"
                  :key="image.id"
                  type="button"
                  :class="{ selected: image.id === selectedImage.id }"
                  :aria-pressed="image.id === selectedImage.id"
                  @click="selectedImageId = image.id"
                >
                  <img :src="assetUrl(image.image_url)" alt="" />
                </button>
              </div>
            </aside>

            <div class="delivery-content">
              <section class="delivery-block copy-block">
                <div class="delivery-block-head">
                  <div>
                    <span>Platform copy</span>
                    <h3>{{ store.current?.latest_copywriting?.copywriting.title || '平台发布文案' }}</h3>
                  </div>
                </div>
                <template v-if="store.current?.latest_copywriting">
                  <el-tabs>
                    <el-tab-pane label="小红书">
                      <strong>{{ store.current.latest_copywriting.copywriting.xiaohongshu_title }}</strong>
                      <p>{{ store.current.latest_copywriting.copywriting.xiaohongshu_text }}</p>
                    </el-tab-pane>
                    <el-tab-pane label="朋友圈">
                      <p>{{ store.current.latest_copywriting.copywriting.moments_text }}</p>
                    </el-tab-pane>
                    <el-tab-pane label="淘宝">
                      <p>{{ store.current.latest_copywriting.copywriting.taobao_text }}</p>
                    </el-tab-pane>
                    <el-tab-pane label="抖音">
                      <p>{{ store.current.latest_copywriting.copywriting.douyin_script }}</p>
                    </el-tab-pane>
                  </el-tabs>
                  <div class="tag-row">
                    <el-tag v-for="tag in store.current.latest_copywriting.copywriting.tags" :key="tag">{{ tag }}</el-tag>
                  </div>
                </template>
                <el-empty v-else description="图片生成完成后会自动生成配套文案" />
              </section>

              <section class="delivery-block revision-block">
                <div class="delivery-block-head">
                  <div>
                    <span>Natural language revision</span>
                    <h3>用一句话描述下一轮修改</h3>
                  </div>
                </div>
                <el-input
                  v-model="instruction"
                  type="textarea"
                  :rows="4"
                  placeholder="例如：背景更高级一点，商品再大一些，更适合小红书封面"
                />
                <div class="revision-submit">
                  <p>系统会先生成可检查的修改计划，不会直接覆盖当前素材。</p>
                  <el-button class="orange-button" type="primary" :loading="revising" @click="revise">
                    生成修改计划
                  </el-button>
                </div>
                <div v-if="revision" class="revision-result">
                  <span class="metric-pill">{{ revision.target }}</span>
                  <h4>新的 Prompt</h4>
                  <p>{{ revision.new_prompt.positive_prompt }}</p>
                  <h4>修改计划</h4>
                  <ul>
                    <li v-for="item in revision.modification_plan" :key="item">{{ item }}</li>
                  </ul>
                </div>
              </section>
            </div>
          </div>

          <div v-else class="stage-empty">
            <el-empty description="生成图片后才能进入交付与迭代">
              <el-button type="primary" @click="selectStage('plans')">选择创意方向</el-button>
            </el-empty>
          </div>
        </section>
      </main>
    </div>

    <ImageComparisonDrawer
      v-model="comparisonOpen"
      :source-url="previewImageUrl"
      :images="filteredImages"
      :selected-image-id="selectedImageId"
      @select="selectedImageId = $event"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import ImageComparisonDrawer from '../components/ImageComparisonDrawer.vue'
import StudioStageNav from '../components/StudioStageNav.vue'
import WorkflowStatusCenter from '../components/WorkflowStatusCenter.vue'
import { assetUrl, errorMessage } from '../api/client'
import {
  createProject,
  type CreativePlan,
  type GeneratedImage,
  jsonExportUrl,
  markdownExportUrl,
  reviseProject,
  type RevisionResponse,
  type VisualAnalysis,
  type WorkflowEvent,
  uploadAsset
} from '../api/productshot'
import {
  type StudioStage,
  type StudioStageKey,
  type WorkflowUiStatus,
  useProjectStore
} from '../stores/project'

const route = useRoute()
const router = useRouter()
const store = useProjectStore()

const creating = ref(false)
const runningAnalysis = ref(false)
const generatingPlanId = ref<number | null>(null)
const revising = ref(false)
const selectedFile = ref<File | null>(null)
const localPreviewUrl = ref('')
const instruction = ref('')
const revision = ref<RevisionResponse | null>(null)
const selectedImageId = ref<number | null>(null)
const selectedPlanId = ref<number | null>(null)
const selectedStage = ref<StudioStageKey>('brief')
const stageManuallySelected = ref(false)
const comparisonOpen = ref(false)
let stopBackgroundPolling: (() => void) | null = null

const visualReview = reactive({
  product_appearance: '',
  dominant_colors: '',
  materials: '',
  visible_text_or_logo: '',
  subject_clarity: '',
  background_issues: '',
  fidelity_constraints: '',
  marketing_opportunities: '',
  review_notes: ''
})

const form = reactive({
  product_name: '',
  product_category: '',
  core_selling_points: '',
  target_platform: '小红书',
  target_audience: '',
  preferred_style: '小红书生活方式风'
})

const routeProjectId = computed(() => {
  const value = route.params.id
  return typeof value === 'string' ? Number(value) : 0
})
const projectId = computed(() => routeProjectId.value)
const hasProject = computed(() => Number.isFinite(projectId.value) && projectId.value > 0)
const primaryAsset = computed(() => store.current?.assets.find((asset) => asset.is_primary) || store.current?.assets[0])
const filteredImages = computed(() => {
  const images = store.current?.generated_images || []
  if (!selectedPlanId.value) return images
  return images.filter((image) => image.plan_id === selectedPlanId.value)
})
const selectedImage = computed(
  () =>
    filteredImages.value.find((image) => image.id === selectedImageId.value) ||
    filteredImages.value.find((image) => image.is_recommended) ||
    filteredImages.value[0]
)
const previewImageUrl = computed(() => {
  if (localPreviewUrl.value) return localPreviewUrl.value
  return primaryAsset.value ? assetUrl(primaryAsset.value.file_url) : ''
})
const pageTitle = computed(() => (hasProject.value ? store.current?.product_name || '项目工作台' : '创建商品营销项目'))
const pageDescription = computed(() =>
  hasProject.value ? '一次专注一个阶段，随时掌握 Agent 是等待、运行还是失败。' : '从一张可靠原图开始组织商品营销生产。'
)
const visualReviewPending = computed(
  () => Boolean(store.current?.visual_analysis && !store.current.latest_analysis && !store.current.visual_analysis.analysis.human_reviewed)
)
const analysisActionLabel = computed(() => {
  if (!store.current?.visual_analysis) return '开始理解原图'
  if (visualReviewPending.value) return '确认审核并生成方向'
  return '生成商品策略和方向'
})
const latestActiveEvent = computed(() => {
  const latestByStep = store.latestEventsByStep
  return (store.current?.workflow_events || []).find(
    (event) =>
      latestByStep[event.step_key]?.id === event.id && (event.status === 'running' || event.status === 'failed')
  )
})
const activeProgressItem = computed(
  () =>
    store.progress.items.find((item) => item.status === 'failed') ||
    store.progress.items.find((item) => item.status === 'running')
)
const progressStage = computed<StudioStageKey | null>(() => {
  if (!store.progress.active || !activeProgressItem.value) return null
  return stageForStep(activeProgressItem.value.key)
})
const recommendedStage = computed<StudioStageKey>(() => {
  if (!hasProject.value) return 'brief'
  if (progressStage.value) return progressStage.value
  if (latestActiveEvent.value) return stageForStep(latestActiveEvent.value.step_key)
  if (
    (!store.current?.visual_analysis && !store.current?.latest_analysis) ||
    visualReviewPending.value ||
    !store.current?.latest_analysis
  ) {
    return 'analysis'
  }
  if (!store.current.creative_plans.length || !store.current.generated_images.length) return 'plans'
  return 'delivery'
})
const generationIsRunning = computed(
  () =>
    workflowDisplay.value.status === 'running' &&
    (progressStage.value === 'generation' || stageForStep(latestActiveEvent.value?.step_key || '') === 'generation')
)
const workflowDisplay = computed<{
  status: WorkflowUiStatus
  title: string
  message: string
  primaryLabel?: string
  startedAt?: string | null
}>(() => {
  const failedProgress = store.progress.active && activeProgressItem.value?.status === 'failed'
  const runningProgress = store.progress.active && activeProgressItem.value?.status === 'running'
  const event = latestActiveEvent.value

  if (failedProgress) {
    return {
      status: 'failed',
      title: activeProgressItem.value?.title || '当前步骤失败',
      message: activeProgressItem.value?.detail || store.progress.message,
      primaryLabel: '重试当前步骤',
      startedAt: store.progress.startedAt
    }
  }
  if (runningProgress) {
    return {
      status: 'running',
      title: store.progress.title,
      message: store.progress.message,
      startedAt: store.progress.startedAt
    }
  }
  if (event?.status === 'failed') {
    return {
      status: 'failed',
      title: `${stepLabel(event.step_key)}失败`,
      message: event.error_message || event.summary,
      primaryLabel: '重试当前步骤',
      startedAt: event.started_at
    }
  }
  if (event?.status === 'running') {
    return {
      status: 'running',
      title: `正在${stepLabel(event.step_key)}`,
      message: event.summary,
      startedAt: event.started_at
    }
  }
  if (!hasProject.value) {
    return {
      status: 'idle',
      title: '准备商品信息',
      message: '填写简报并上传原图后，生产流程才会开始。'
    }
  }
  if (!store.current?.visual_analysis && !store.current?.latest_analysis) {
    return {
      status: 'action_required',
      title: '等待原图分析',
      message: '商品信息已就绪，可以开始理解原图。',
      primaryLabel: '开始理解原图'
    }
  }
  if (visualReviewPending.value) {
    return {
      status: 'action_required',
      title: '等待人工确认',
      message: '请核对模型识别的商品外观、材质、文字和保真约束。',
      primaryLabel: '去确认分析'
    }
  }
  if (!store.current?.creative_plans.length) {
    return {
      status: 'action_required',
      title: '等待生成创意方向',
      message: '原图理解已经确认，可以继续形成商品策略与创意方向。',
      primaryLabel: '生成创意方向'
    }
  }
  if (!store.current.generated_images.length) {
    return {
      status: 'action_required',
      title: '等待选择创意方向',
      message: '比较 3 个方向并选择一个生成图片、评分和文案。',
      primaryLabel: '选择创意方向'
    }
  }
  if (!store.current.latest_copywriting) {
    return {
      status: 'success',
      title: '图片素材已生成',
      message: '可以查看评分与原图对比；这个历史项目当前没有配套文案。',
      primaryLabel: '查看生成结果'
    }
  }
  return {
    status: 'success',
    title: '当前素材包已完成',
    message: '可以对比原图、修改文案或直接导出素材。',
    primaryLabel: '查看交付内容'
  }
})
const studioStages = computed<StudioStage[]>(() => {
  const completed: Record<StudioStageKey, boolean> = {
    brief: hasProject.value,
    analysis: Boolean(store.current?.latest_analysis),
    plans: Boolean(store.current?.creative_plans.length),
    generation: Boolean(store.current?.generated_images.length),
    delivery: Boolean(store.current?.latest_copywriting)
  }
  const available: Record<StudioStageKey, boolean> = {
    brief: true,
    analysis: hasProject.value,
    plans: Boolean(store.current?.latest_analysis),
    generation: Boolean(store.current?.creative_plans.length),
    delivery: Boolean(store.current?.generated_images.length)
  }
  const descriptions: Record<StudioStageKey, string> = {
    brief: hasProject.value ? '核对商品上下文' : '填写简报并上传原图',
    analysis: '确认原图理解与策略',
    plans: '比较并选择营销方向',
    generation: '生成、评分与挑选图片',
    delivery: '文案、修改与导出'
  }
  const titles: Record<StudioStageKey, string> = {
    brief: '商品与原图',
    analysis: '分析与确认',
    plans: '创意方向',
    generation: '素材生成',
    delivery: '交付与迭代'
  }
  const lockedReasons: Record<StudioStageKey, string> = {
    brief: '',
    analysis: '先创建项目',
    plans: '先完成商品分析',
    generation: '先生成创意方向',
    delivery: '先生成至少一张图片'
  }
  const activeEventStage = latestActiveEvent.value ? stageForStep(latestActiveEvent.value.step_key) : null

  return (Object.keys(titles) as StudioStageKey[]).map((key) => {
    let status: StudioStage['status'] = available[key] ? 'available' : 'locked'
    if (completed[key]) status = 'success'
    if (key === recommendedStage.value && available[key] && !completed[key]) status = 'current'
    if (key === progressStage.value && store.progress.active) {
      status = activeProgressItem.value?.status === 'failed' ? 'failed' : 'running'
    } else if (key === activeEventStage && latestActiveEvent.value?.status === 'failed') {
      status = 'failed'
    } else if (key === activeEventStage && latestActiveEvent.value?.status === 'running') {
      status = 'running'
    }
    return {
      key,
      title: titles[key],
      description: descriptions[key],
      status,
      available: available[key],
      lockedReason: lockedReasons[key]
    }
  })
})

onMounted(loadFromRoute)
onBeforeUnmount(() => {
  stopPassivePolling()
  if (localPreviewUrl.value) URL.revokeObjectURL(localPreviewUrl.value)
})

watch(
  () => route.params.id,
  () => loadFromRoute()
)
watch(
  () => store.current?.visual_analysis?.id,
  () => syncVisualReviewForm()
)
watch(recommendedStage, (stage) => {
  if (!stageManuallySelected.value) selectedStage.value = stage
})
watch(
  () => store.hasRunningWorkflowEvent,
  (running) => {
    if (running) resumePassivePolling()
    else stopPassivePolling()
  }
)

async function loadFromRoute() {
  revision.value = null
  instruction.value = ''
  comparisonOpen.value = false
  stageManuallySelected.value = false
  stopPassivePolling()
  if (!hasProject.value) {
    store.resetCurrent()
    selectedImageId.value = null
    selectedPlanId.value = null
    selectedStage.value = 'brief'
    return
  }
  if (localPreviewUrl.value) URL.revokeObjectURL(localPreviewUrl.value)
  localPreviewUrl.value = ''
  selectedFile.value = null
  try {
    await store.load(projectId.value)
    syncVisualReviewForm()
    const recommended = store.current?.generated_images.find((image) => image.is_recommended)
    selectedPlanId.value = recommended?.plan_id || store.current?.generated_images[0]?.plan_id || null
    selectedImageId.value = recommended?.id || store.current?.generated_images[0]?.id || null
    selectedStage.value = recommendedStage.value
    resumePassivePolling()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function resumePassivePolling() {
  if (
    !hasProject.value ||
    !store.hasRunningWorkflowEvent ||
    stopBackgroundPolling ||
    generatingPlanId.value !== null ||
    runningAnalysis.value
  ) {
    return
  }
  stopBackgroundPolling = store.beginProjectPolling(projectId.value, true)
}

function stopPassivePolling() {
  stopBackgroundPolling?.()
  stopBackgroundPolling = null
}

function selectStage(stage: StudioStageKey) {
  const target = studioStages.value.find((item) => item.key === stage)
  if (!target?.available) return
  selectedStage.value = stage
  stageManuallySelected.value = stage !== recommendedStage.value
}

function goToAnalysis() {
  selectStage('analysis')
}

function handleFile(file: UploadFile) {
  if (localPreviewUrl.value) URL.revokeObjectURL(localPreviewUrl.value)
  selectedFile.value = file.raw || null
  localPreviewUrl.value = selectedFile.value ? URL.createObjectURL(selectedFile.value) : ''
}

async function createStudioProject() {
  if (!form.product_name.trim()) {
    ElMessage.warning('请填写商品名称')
    return
  }
  if (!selectedFile.value) {
    ElMessage.warning('请上传商品图片')
    return
  }
  creating.value = true
  try {
    const project = await createProject(form)
    await uploadAsset(project.id, selectedFile.value)
    ElMessage.success('项目创建成功，可以开始理解原图')
    if (localPreviewUrl.value) URL.revokeObjectURL(localPreviewUrl.value)
    localPreviewUrl.value = ''
    selectedFile.value = null
    await router.replace(`/studio/${project.id}`)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    creating.value = false
  }
}

async function runWorkflow() {
  if (!hasProject.value) return
  if (visualReviewPending.value) {
    await confirmVisualReview()
    return
  }
  runningAnalysis.value = true
  stageManuallySelected.value = false
  try {
    if (!store.current?.visual_analysis) {
      selectedStage.value = 'analysis'
      await store.runVisualAnalysis(projectId.value)
      ElMessage.success('原图理解已完成，请审核后继续')
      return
    }
    await confirmVisualReview()
  } catch (error) {
    store.setStep('analysis', 'failed')
    ElMessage.error(errorMessage(error))
  } finally {
    runningAnalysis.value = false
  }
}

async function confirmVisualReview() {
  if (!hasProject.value || !store.current?.visual_analysis) return
  runningAnalysis.value = true
  stageManuallySelected.value = false
  try {
    await store.continueAfterVisualReview(projectId.value, {
      analysis: visualReviewPayload(store.current.visual_analysis.analysis),
      review_notes: visualReview.review_notes.trim()
    })
    selectedStage.value = 'plans'
    ElMessage.success('审核已确认，创意方案已生成')
  } catch (error) {
    store.setStep('analysis', 'failed')
    ElMessage.error(errorMessage(error))
  } finally {
    runningAnalysis.value = false
  }
}

async function selectPlan(plan: CreativePlan) {
  if (!hasProject.value) return
  generatingPlanId.value = plan.id
  selectedPlanId.value = plan.id
  selectedStage.value = 'generation'
  stageManuallySelected.value = false
  try {
    await store.generateFromPlan(projectId.value, plan)
    selectedImageId.value =
      filteredImages.value.find((image) => image.is_recommended)?.id || filteredImages.value[0]?.id || null
    selectedStage.value = 'delivery'
    ElMessage.success('图片、评分和文案已生成')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    generatingPlanId.value = null
  }
}

async function review(image: GeneratedImage) {
  if (!hasProject.value) return
  selectedImageId.value = image.id
  try {
    await store.review(projectId.value, image)
    ElMessage.success('评分已更新')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function revise() {
  if (!hasProject.value) return
  if (!instruction.value.trim()) {
    ElMessage.warning('请输入修改要求')
    return
  }
  revising.value = true
  try {
    revision.value = await reviseProject(projectId.value, instruction.value, selectedImage.value?.id)
    ElMessage.success('修改计划已生成')
    await store.load(projectId.value)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    revising.value = false
  }
}

function openComparison(imageId: number) {
  selectedImageId.value = imageId
  comparisonOpen.value = true
}

function handleStatusPrimary() {
  if (workflowDisplay.value.status === 'failed') {
    retryCurrentStep()
    return
  }
  if (!store.current?.visual_analysis && !store.current?.latest_analysis) {
    selectStage('analysis')
    runWorkflow()
    return
  }
  if (visualReviewPending.value) {
    selectStage('analysis')
    return
  }
  if (!store.current?.creative_plans.length) {
    selectStage('analysis')
    runWorkflow()
    return
  }
  if (!store.current.generated_images.length) {
    selectStage('plans')
    return
  }
  selectStage('delivery')
}

function retryCurrentStep() {
  const step = activeProgressItem.value?.key || latestActiveEvent.value?.step_key || ''
  const stage = stageForStep(step)
  selectStage(stage)
  if (stage === 'analysis' || stage === 'plans') {
    runWorkflow()
    return
  }
  if (stage === 'generation') {
    const plan =
      store.current?.creative_plans.find((item) => item.id === selectedPlanId.value) || store.current?.creative_plans[0]
    if (plan) selectPlan(plan)
    return
  }
  if (step === 'revision') revise()
}

function stageForStep(stepKey: string): StudioStageKey {
  if (stepKey === 'visual_analysis' || stepKey === 'visual_review' || stepKey === 'analysis') return 'analysis'
  if (stepKey === 'plans') return 'plans'
  if (stepKey === 'prompt' || stepKey === 'images' || stepKey === 'review' || stepKey === 'copy') return 'generation'
  if (stepKey === 'revision' || stepKey === 'export') return 'delivery'
  return 'brief'
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: '草稿',
    visual_review: '待审核',
    visual_reviewed: '已审核',
    analyzed: '已分析',
    planned: '已出方案',
    generated: '已生成',
    reviewed: '已评分',
    copywritten: '已出文案',
    revised: '已修改',
    exported: '已导出'
  }
  return labels[status] || status
}

function stepLabel(stepKey: string) {
  const labels: Record<string, string> = {
    visual_analysis: '原图理解',
    visual_review: '人工确认',
    analysis: '商品策略',
    plans: '方向规划',
    prompt: ' Prompt 构建',
    images: '素材生成',
    review: '质量评价',
    copy: '发布文案',
    revision: '修改计划'
  }
  return labels[stepKey] || stepKey
}

function syncVisualReviewForm() {
  const analysis = store.current?.visual_analysis?.analysis
  if (!analysis) return
  visualReview.product_appearance = analysis.product_appearance
  visualReview.dominant_colors = listToLines(analysis.dominant_colors)
  visualReview.materials = listToLines(analysis.materials)
  visualReview.visible_text_or_logo = listToLines(analysis.visible_text_or_logo)
  visualReview.subject_clarity = analysis.subject_clarity
  visualReview.background_issues = listToLines(analysis.background_issues)
  visualReview.fidelity_constraints = listToLines(analysis.fidelity_constraints)
  visualReview.marketing_opportunities = listToLines(analysis.marketing_opportunities)
  visualReview.review_notes = analysis.human_review_notes || ''
}

function visualReviewPayload(current: VisualAnalysis): VisualAnalysis {
  return {
    ...current,
    product_appearance: visualReview.product_appearance.trim(),
    dominant_colors: linesToList(visualReview.dominant_colors),
    materials: linesToList(visualReview.materials),
    visible_text_or_logo: linesToList(visualReview.visible_text_or_logo),
    subject_clarity: visualReview.subject_clarity.trim(),
    background_issues: linesToList(visualReview.background_issues),
    fidelity_constraints: linesToList(visualReview.fidelity_constraints),
    marketing_opportunities: linesToList(visualReview.marketing_opportunities),
    human_review_notes: visualReview.review_notes.trim()
  }
}

function listToLines(items: string[]) {
  return items.join('\n')
}

function linesToList(value: string) {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}
</script>

<style scoped>
.studio-page {
  max-width: 1500px;
}

.studio-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 14px;
}

.studio-header .page-title {
  margin-bottom: 5px;
}

.studio-header-actions,
.delivery-export-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.focused-workspace {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 14px;
  align-items: start;
  margin-top: 14px;
}

.stage-rail {
  position: sticky;
  top: 174px;
  display: grid;
  gap: 10px;
  padding: 12px;
  border: 1px solid rgba(220, 219, 210, 0.9);
  border-radius: var(--ps-radius);
  background: rgba(247, 246, 240, 0.74);
}

.stage-rail-heading {
  display: grid;
  gap: 3px;
  padding: 3px 5px 9px;
  border-bottom: 1px solid var(--ps-border);
}

.stage-rail-heading span,
.stage-kicker,
.plan-meta,
.delivery-block-head span,
.source-card-head span,
.attention-label,
.generation-waiting > div > span,
.delivery-image-head span {
  color: var(--ps-muted);
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.stage-rail-heading strong {
  color: var(--ps-heading);
  font-size: 13px;
}

.stage-workspace {
  min-width: 0;
}

.stage-section {
  min-height: 590px;
  padding: 22px;
  border: 1px solid var(--ps-border);
  border-radius: var(--ps-radius);
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.45), transparent 42%),
    var(--ps-surface);
  box-shadow: var(--ps-shadow-soft);
  animation: stage-enter 240ms ease both;
}

@keyframes stage-enter {
  from {
    opacity: 0;
    transform: translateY(5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.stage-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 22px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--ps-border);
}

.stage-heading h2 {
  margin: 5px 0 6px;
  color: var(--ps-heading);
  font-family: Georgia, "Times New Roman", "Songti SC", serif;
  font-size: clamp(25px, 2.2vw, 34px);
  font-weight: 650;
  line-height: 1.15;
}

.stage-heading p {
  max-width: 680px;
  margin: 0;
  color: var(--ps-muted);
  line-height: 1.65;
}

.creation-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(300px, 0.85fr);
  gap: 24px;
}

.brief-form,
.visual-review-form {
  display: grid;
  align-content: start;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.upload-workbench {
  display: grid;
  align-content: start;
  gap: 12px;
  padding-left: 22px;
  border-left: 1px solid var(--ps-border);
}

.upload-preview {
  display: grid;
  aspect-ratio: 4 / 5;
  max-height: 480px;
  place-items: center;
  overflow: hidden;
  border: 1px solid var(--ps-border);
  border-radius: var(--ps-radius);
  background:
    radial-gradient(circle at 50% 34%, rgba(255, 255, 255, 0.9), transparent 30%),
    linear-gradient(145deg, rgba(36, 88, 70, 0.08), rgba(201, 93, 66, 0.08)),
    var(--ps-surface-soft);
}

.upload-preview img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.upload-placeholder {
  display: grid;
  gap: 10px;
  padding: 28px;
  text-align: center;
}

.upload-placeholder span {
  color: var(--ps-accent-dark);
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.upload-placeholder strong {
  color: var(--ps-primary-ink);
  font-family: Georgia, "Times New Roman", "Songti SC", serif;
  font-size: 25px;
  font-weight: 650;
  line-height: 1.28;
}

.upload-placeholder p,
.upload-subcopy {
  margin: 0;
  color: var(--ps-muted);
  line-height: 1.6;
}

.upload-copy {
  padding: 13px 0 5px;
  color: var(--ps-primary);
  font-weight: 800;
}

.brief-overview {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(260px, 0.75fr);
  gap: 22px;
}

.brief-summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  margin: 0;
  overflow: hidden;
  border: 1px solid var(--ps-border);
  border-radius: var(--ps-radius);
  background: var(--ps-border);
}

.brief-summary > div {
  min-height: 106px;
  padding: 16px;
  background: var(--ps-surface-quiet);
}

dt {
  color: var(--ps-primary);
  font-size: 11px;
  font-weight: 850;
}

dd {
  margin: 6px 0 0;
  color: var(--ps-muted-strong);
  line-height: 1.65;
}

.source-card {
  display: grid;
  gap: 10px;
}

.source-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.source-card-head small {
  color: var(--ps-muted);
  font-size: 11px;
}

.source-frame {
  display: grid;
  min-height: 320px;
  place-items: center;
  overflow: hidden;
  border: 1px solid var(--ps-border);
  border-radius: var(--ps-radius);
  background: var(--ps-surface-soft);
}

.source-frame img {
  display: block;
  width: 100%;
  height: 100%;
  max-height: 520px;
  object-fit: contain;
}

.stage-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 22px;
  padding-top: 16px;
  border-top: 1px solid var(--ps-border);
}

.stage-action-bar p,
.form-submit-row p,
.revision-submit p {
  margin: 0;
  color: var(--ps-muted);
  line-height: 1.55;
}

.analysis-review-layout {
  display: grid;
  grid-template-columns: minmax(260px, 0.7fr) minmax(0, 1.3fr);
  gap: 22px;
}

.analysis-source {
  display: grid;
  align-content: start;
  gap: 16px;
}

.analysis-source-frame {
  min-height: 280px;
  max-height: 460px;
}

.analysis-source h3 {
  margin: 8px 0;
  color: var(--ps-heading);
  font-family: Georgia, "Times New Roman", "Songti SC", serif;
  font-size: 24px;
  font-weight: 650;
}

.analysis-source p {
  margin: 0;
  color: var(--ps-muted);
  line-height: 1.65;
}

.attention-label {
  display: inline-flex;
  padding: 5px 8px;
  border-radius: 999px;
  color: var(--ps-accent-dark);
  background: var(--ps-accent-soft);
}

.form-submit-row,
.revision-submit {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding-top: 8px;
}

.analysis-result-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.insight-card {
  padding: 16px;
  border: 1px solid var(--ps-border);
  border-radius: var(--ps-radius);
  background: var(--ps-surface-quiet);
}

.insight-card.featured {
  border-color: rgba(36, 88, 70, 0.22);
  background:
    linear-gradient(130deg, rgba(36, 88, 70, 0.08), transparent 60%),
    var(--ps-surface-quiet);
}

.insight-card > span,
.plan-selling-point span {
  color: var(--ps-accent-dark);
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.insight-card h3 {
  margin: 8px 0;
  color: var(--ps-heading);
  font-size: 17px;
  line-height: 1.45;
}

.insight-card p {
  margin: 0;
  color: var(--ps-muted);
  line-height: 1.7;
}

.insight-card ul,
.revision-result ul {
  margin: 0;
  padding-left: 18px;
  color: var(--ps-muted);
  line-height: 1.72;
}

.tag-row {
  margin-top: 12px;
}

.tag-row .el-tag {
  margin: 0 7px 7px 0;
}

.plan-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.plan-card {
  position: relative;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--ps-border);
  border-radius: var(--ps-radius);
  background: var(--ps-surface-quiet);
  transition:
    border-color 160ms ease,
    transform 160ms ease,
    box-shadow 160ms ease;
}

.plan-card:hover,
.plan-card.selected {
  border-color: rgba(201, 93, 66, 0.38);
  box-shadow: var(--ps-shadow-soft);
  transform: translateY(-2px);
}

.plan-card-number {
  padding: 12px 14px 0;
  color: var(--ps-border-strong);
  font-family: Georgia, "Times New Roman", serif;
  font-size: 32px;
  line-height: 1;
}

.plan-card-copy {
  padding: 12px 14px;
}

.plan-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.plan-meta span + span::before {
  margin-right: 8px;
  color: var(--ps-border-strong);
  content: "·";
}

.plan-card h3 {
  margin: 10px 0 8px;
  color: var(--ps-heading);
  font-family: Georgia, "Times New Roman", "Songti SC", serif;
  font-size: 22px;
  font-weight: 650;
}

.plan-card-copy > p {
  display: -webkit-box;
  min-height: 70px;
  margin: 0;
  overflow: hidden;
  color: var(--ps-muted);
  line-height: 1.65;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.plan-selling-point {
  display: grid;
  gap: 5px;
  margin-top: 14px;
  padding: 10px;
  border-left: 3px solid var(--ps-accent);
  background: rgba(201, 93, 66, 0.06);
}

.plan-selling-point strong {
  color: var(--ps-heading);
  font-size: 13px;
  line-height: 1.5;
}

.plan-details-collapse {
  margin-top: 10px;
  --el-collapse-header-bg-color: transparent;
  --el-collapse-content-bg-color: transparent;
  border-top: 1px solid var(--ps-border);
  border-bottom: 0;
}

.plan-details-collapse dl {
  display: grid;
  gap: 8px;
  margin: 0;
}

.plan-generate-button {
  width: calc(100% - 28px);
  margin: 0 14px 14px;
}

.generation-waiting {
  display: grid;
  min-height: 360px;
  grid-template-columns: 130px minmax(0, 440px);
  place-content: center;
  gap: 28px;
  align-items: center;
  border: 1px dashed rgba(201, 93, 66, 0.34);
  border-radius: var(--ps-radius);
  background:
    radial-gradient(circle at 28% 50%, rgba(201, 93, 66, 0.1), transparent 28%),
    var(--ps-surface-quiet);
}

.generation-orbit {
  position: relative;
  width: 120px;
  height: 120px;
  border: 1px solid rgba(201, 93, 66, 0.28);
  border-radius: 999px;
  animation: orbit-spin 4s linear infinite;
}

.generation-orbit::before,
.generation-orbit::after {
  position: absolute;
  border: 1px solid rgba(36, 88, 70, 0.2);
  border-radius: inherit;
  content: "";
}

.generation-orbit::before {
  inset: 18px;
}

.generation-orbit::after {
  inset: 38px;
  background: var(--ps-primary);
}

.generation-orbit span {
  position: absolute;
  top: 10px;
  left: 50%;
  width: 12px;
  height: 12px;
  border-radius: 999px;
  background: var(--ps-accent);
  box-shadow: 0 0 0 6px rgba(201, 93, 66, 0.12);
}

@keyframes orbit-spin {
  to {
    transform: rotate(360deg);
  }
}

.generation-waiting h3 {
  margin: 8px 0;
  color: var(--ps-heading);
  font-family: Georgia, "Times New Roman", "Songti SC", serif;
  font-size: 25px;
  font-weight: 650;
}

.generation-waiting p {
  margin: 0;
  color: var(--ps-muted);
  line-height: 1.65;
}

.image-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.generated-card {
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--ps-border);
  border-radius: var(--ps-radius);
  background: var(--ps-surface-quiet);
  transition:
    border-color 160ms ease,
    transform 160ms ease;
}

.generated-card:hover,
.generated-card.selected {
  border-color: var(--ps-accent);
  transform: translateY(-1px);
}

.generated-select {
  position: relative;
  display: block;
  width: 100%;
  aspect-ratio: 1 / 1;
  overflow: hidden;
  padding: 0;
  border: 0;
  background: var(--ps-surface-soft);
  cursor: pointer;
}

.generated-select img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.recommended-ribbon {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 2;
  padding: 5px 8px;
  border-radius: 999px;
  color: #fff;
  background: var(--ps-primary);
  font-size: 10px;
  font-weight: 850;
}

.generated-meta {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  padding: 11px 11px 7px;
}

.generated-meta div {
  display: grid;
  gap: 3px;
}

.generated-meta strong {
  color: var(--ps-primary);
  font-size: 18px;
}

.generated-meta span {
  color: var(--ps-muted);
  font-size: 10px;
}

.generated-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 5px 6px;
  border-top: 1px solid var(--ps-border);
}

.delivery-layout {
  display: grid;
  grid-template-columns: minmax(280px, 0.72fr) minmax(0, 1.28fr);
  gap: 18px;
}

.delivery-visual {
  display: grid;
  align-content: start;
  gap: 10px;
}

.delivery-image {
  overflow: hidden;
  aspect-ratio: 1 / 1;
  border: 1px solid var(--ps-border);
  border-radius: var(--ps-radius);
  background: var(--ps-surface-soft);
}

.delivery-image img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.delivery-image-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.delivery-image-head div {
  display: grid;
  gap: 3px;
}

.delivery-image-head strong {
  color: var(--ps-primary);
  font-size: 20px;
}

.delivery-image-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.delivery-thumbnails {
  display: flex;
  gap: 7px;
  overflow-x: auto;
  padding-top: 8px;
  border-top: 1px solid var(--ps-border);
}

.delivery-thumbnails button {
  width: 58px;
  height: 58px;
  flex: 0 0 58px;
  overflow: hidden;
  padding: 3px;
  border: 1px solid var(--ps-border);
  border-radius: 6px;
  background: var(--ps-surface);
  cursor: pointer;
}

.delivery-thumbnails button.selected {
  border-color: var(--ps-accent);
}

.delivery-thumbnails img {
  width: 100%;
  height: 100%;
  border-radius: 3px;
  object-fit: cover;
}

.delivery-content {
  display: grid;
  gap: 12px;
}

.delivery-block {
  padding: 16px;
  border: 1px solid var(--ps-border);
  border-radius: var(--ps-radius);
  background: var(--ps-surface-quiet);
}

.delivery-block-head h3 {
  margin: 6px 0 12px;
  color: var(--ps-heading);
  font-family: Georgia, "Times New Roman", "Songti SC", serif;
  font-size: 22px;
  font-weight: 650;
}

.copy-block p,
.revision-result p {
  color: var(--ps-muted);
  line-height: 1.75;
  white-space: pre-wrap;
}

.revision-result {
  margin-top: 14px;
  padding: 14px;
  border: 1px solid rgba(36, 88, 70, 0.16);
  border-radius: var(--ps-radius);
  background: var(--ps-primary-soft);
}

.revision-result h4 {
  margin: 14px 0 6px;
  color: var(--ps-heading);
}

.stage-empty {
  display: grid;
  min-height: 420px;
  place-items: center;
  border: 1px dashed var(--ps-border-strong);
  border-radius: var(--ps-radius);
  background: var(--ps-surface-quiet);
}

@media (max-width: 1260px) {
  .plan-grid {
    grid-template-columns: 1fr;
  }

  .plan-card {
    grid-template-columns: 58px minmax(0, 1fr) auto;
    grid-template-rows: auto;
    align-items: center;
  }

  .plan-generate-button {
    width: auto;
    margin: 14px;
  }
}

@media (max-width: 1040px) {
  .focused-workspace {
    grid-template-columns: 1fr;
  }

  .stage-rail {
    position: static;
    overflow: hidden;
  }

  .stage-rail-heading {
    display: none;
  }

  .creation-layout,
  .analysis-review-layout {
    grid-template-columns: 1fr;
  }

  .upload-workbench {
    padding: 0;
    border: 0;
  }

  .upload-preview {
    aspect-ratio: 16 / 9;
  }
}

@media (max-width: 820px) {
  .studio-header,
  .stage-heading,
  .stage-action-bar,
  .form-submit-row,
  .revision-submit {
    align-items: stretch;
    flex-direction: column;
  }

  .brief-overview,
  .analysis-result-grid,
  .delivery-layout {
    grid-template-columns: 1fr;
  }

  .image-grid {
    grid-template-columns: 1fr 1fr;
  }

  .delivery-visual {
    max-width: 520px;
  }
}

@media (max-width: 620px) {
  .stage-section {
    min-height: 520px;
    padding: 15px;
  }

  .stage-heading {
    margin-bottom: 16px;
    padding-bottom: 14px;
  }

  .stage-heading h2 {
    font-size: 25px;
  }

  .form-grid,
  .brief-summary,
  .image-grid {
    grid-template-columns: 1fr;
  }

  .brief-summary > div {
    min-height: auto;
  }

  .plan-card {
    grid-template-columns: 1fr;
  }

  .plan-card-number {
    font-size: 25px;
  }

  .plan-generate-button {
    width: calc(100% - 28px);
    margin-top: 0;
  }

  .generation-waiting {
    grid-template-columns: 1fr;
    padding: 28px 18px;
    text-align: center;
  }

  .generation-orbit {
    margin: 0 auto;
  }
}

@media (prefers-reduced-motion: reduce) {
  .stage-section,
  .generation-orbit {
    animation: none;
  }
}
</style>
