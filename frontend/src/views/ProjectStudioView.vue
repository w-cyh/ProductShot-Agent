<template>
  <section class="page studio-page">
    <header class="studio-header">
      <div>
        <span class="eyebrow">Product Studio</span>
        <h1 class="page-title">{{ pageTitle }}</h1>
        <p class="page-description">{{ pageDescription }}</p>
      </div>
      <el-tag v-if="hasProject && sourceConfirmed" type="success" effect="plain">商品与原图已锁定</el-tag>
    </header>

    <WorkflowStatusCenter
      :status="workflowDisplay.status"
      :title="workflowDisplay.title"
      :message="workflowDisplay.message"
      :primary-label="workflowDisplay.primaryLabel"
      :started-at="workflowDisplay.startedAt"
      :steps="displaySteps"
      :events="store.current?.workflow_events || []"
      @primary="handleStatusPrimary"
      @select-step="selectWorkflowStep"
    />

    <div class="focused-workspace">
      <main class="stage-workspace">
        <section v-if="selectedStage === 'brief'" class="stage-section">
          <StageHeading kicker="01 · 商品与原图" title="先确认商品事实与原图" description="确认前可以修改；确认后商品事实和原图会锁定为后续生产的唯一参考。" />

          <div class="source-workspace" :class="{ locked: sourceConfirmed }">
            <el-form class="brief-form" label-position="top" :model="briefForm" @submit.prevent>
              <div class="form-grid">
                <el-form-item label="商品名称" required>
                  <el-input v-model="briefForm.product_name" :disabled="sourceConfirmed" placeholder="例如：手工香薰蜡烛" />
                </el-form-item>
                <el-form-item label="商品类别">
                  <el-input v-model="briefForm.product_category" :disabled="sourceConfirmed" placeholder="例如：家居香氛" />
                </el-form-item>
              </div>
              <el-form-item label="核心卖点">
                <el-input v-model="briefForm.core_selling_points" :disabled="sourceConfirmed" type="textarea" :rows="4" :placeholder="sourceConfirmed ? '' : '手工制作、香味舒缓、适合作为礼物'" />
              </el-form-item>
              <el-form-item label="目标人群">
                <el-input v-model="briefForm.target_audience" :disabled="sourceConfirmed" :placeholder="sourceConfirmed ? '' : '例如：年轻女性、礼物购买者'" />
              </el-form-item>
              <p v-if="sourceConfirmed" class="source-lock-note">商品事实与原图已锁定，后续阶段将以此作为唯一保真参考。</p>
            </el-form>

            <div class="source-panel">
              <div class="source-panel-head">
                <div>
                  <span>商品原图</span>
                  <small>{{ sourceConfirmed ? '保真参考已锁定' : '确认前可替换' }}</small>
                </div>
                <el-tag v-if="sourceConfirmed" size="small" type="success">已确认</el-tag>
              </div>
              <div class="source-frame">
                <img v-if="previewImageUrl" :src="previewImageUrl" alt="商品原图" />
                <div v-else class="upload-placeholder">
                  <span>Source image</span>
                  <strong>上传一张清晰商品原图</strong>
                  <p>建议主体完整、文字可辨识，避免严重遮挡。</p>
                </div>
              </div>
              <el-upload
                v-if="!sourceConfirmed"
                class="source-upload"
                drag
                :auto-upload="false"
                :show-file-list="false"
                accept=".jpg,.jpeg,.png,.webp"
                :on-change="handleFile"
              >
                <span>{{ previewImageUrl ? '选择替换图片' : '点击或拖拽上传商品图' }}</span>
                <small>支持 JPG、PNG、WebP</small>
              </el-upload>
              <el-button v-if="!sourceConfirmed && previewImageUrl" text class="reupload-button" @click="openFilePicker">
                重新上传
              </el-button>
            </div>
          </div>

          <footer v-if="!sourceConfirmed" class="stage-action-bar">
            <p>确认后不可再修改商品信息或换图，请先核对本阶段内容。</p>
            <div class="source-actions">
              <el-button v-if="!hasProject && hasDraft" text @click="discardDraft">清空草稿</el-button>
              <el-button class="orange-button" type="primary" size="large" :loading="savingSource" @click="saveAndConfirmSource">
                {{ hasProject ? '确认商品与原图' : '创建并确认商品与原图' }}
              </el-button>
            </div>
          </footer>
          <footer v-else class="stage-action-bar">
            <p>商品事实已锁定。下一步由系统理解原图，再由你确认关键保真约束。</p>
            <el-button type="primary" @click="selectStage('analysis')">进入分析与确认</el-button>
          </footer>
        </section>

        <section v-else-if="selectedStage === 'analysis'" class="stage-section">
          <StageHeading kicker="02 · 分析与确认" title="先确认理解，再生成策略" description="默认只展示最需要确认的内容。若识别有误，请直接用自然语言纠正。" />

          <el-empty v-if="!sourceConfirmed" description="请先确认商品与原图">
            <el-button type="primary" @click="selectStage('brief')">返回商品与原图</el-button>
          </el-empty>

          <template v-else-if="!visualAnalysis">
            <div class="empty-work-card">
              <strong>开始理解原图</strong>
              <p>系统会识别商品外观、材质、Logo 和保真约束；这一步不会自动生成创意方向。</p>
              <el-button class="orange-button" type="primary" :loading="runningVisual" @click="runVisual">开始原图理解</el-button>
            </div>
          </template>

          <template v-else>
            <div class="confirmation-layout">
              <div class="summary-card visual-summary">
                <div class="summary-card-head">
                  <div>
                    <span class="attention-label">{{ visualAnalysis.analysis.human_reviewed ? '理解已确认' : '等待你的确认' }}</span>
                    <h3>原图理解摘要</h3>
                  </div>
                  <el-tag :type="visualAnalysis.analysis.human_reviewed ? 'success' : 'warning'" effect="plain">
                    {{ visualAnalysis.analysis.human_reviewed ? '已确认' : '待确认' }}
                  </el-tag>
                </div>
                <dl class="summary-grid">
                  <div><dt>商品识别</dt><dd>{{ visualAnalysis.analysis.product_appearance }}</dd></div>
                  <div><dt>关键保真约束</dt><dd>{{ joinValues(visualAnalysis.analysis.fidelity_constraints) }}</dd></div>
                  <div><dt>可见文字 / Logo</dt><dd>{{ joinValues(visualAnalysis.analysis.visible_text_or_logo) }}</dd></div>
                  <div><dt>材质与质感</dt><dd>{{ joinValues(visualAnalysis.analysis.materials) }}</dd></div>
                </dl>
                <el-button class="detail-trigger" text @click="analysisDetailsOpen = true">查看完整原图理解</el-button>
              </div>

              <div v-if="!visualAnalysis.analysis.human_reviewed" class="correction-card">
                <span class="stage-kicker">自然语言纠正</span>
                <h3>识别有误？告诉系统哪里需要修正</h3>
                <p>例如：“Logo 是烫金而非印刷”，“瓶身是磨砂玻璃，不能改为透明”。</p>
                <el-input v-model="visualCorrection" type="textarea" :rows="4" placeholder="输入需要纠正的商品事实或保真约束" />
                <div class="inline-actions">
                  <el-button :loading="correctingVisual" :disabled="!visualCorrection.trim()" @click="correctVisual">提交纠正</el-button>
                  <el-button class="orange-button" type="primary" :loading="confirmingVisual" @click="confirmVisual">确认理解</el-button>
                </div>
              </div>
            </div>

            <div v-if="visualAnalysis.analysis.human_reviewed" class="strategy-section">
              <div v-if="!strategy" class="empty-work-card compact">
                <strong>原图理解已确认</strong>
                <p>现在生成商品策略；创意方向仍需你在下一阶段显式发起。</p>
                <el-button class="orange-button" type="primary" :loading="runningStrategy" @click="runStrategy">生成商品策略</el-button>
              </div>
              <div v-else class="summary-card strategy-card">
                <div class="summary-card-head">
                  <div><span class="attention-label">策略结论</span><h3>{{ strategy.analysis.product_type }}</h3></div>
                  <el-tag :type="strategyConfirmed ? 'success' : 'warning'" effect="plain">{{ strategyConfirmed ? '已确认' : '待确认' }}</el-tag>
                </div>
                <dl class="summary-grid">
                  <div><dt>核心卖点</dt><dd>{{ joinValues(strategy.analysis.recommended_selling_points) }}</dd></div>
                  <div><dt>目标人群</dt><dd>{{ strategy.analysis.target_audience_analysis }}</dd></div>
                  <div><dt>主视觉策略</dt><dd>{{ strategy.analysis.visual_summary || joinValues(strategy.analysis.recommended_visual_styles) }}</dd></div>
                  <div><dt>营销切入点</dt><dd>{{ joinValues(strategy.analysis.marketing_angles) }}</dd></div>
                </dl>
                <el-button class="detail-trigger" text @click="analysisDetailsOpen = true">查看完整商品策略</el-button>
                <template v-if="!strategyConfirmed">
                  <div class="strategy-correction">
                    <span class="stage-kicker">自然语言纠正</span>
                    <p>如卖点、人群或主视觉判断不准确，请说明你想调整的方向。</p>
                    <el-input v-model="strategyCorrection" type="textarea" :rows="3" placeholder="例如：目标人群应更偏向新手送礼，强调低门槛与仪式感" />
                    <div class="inline-actions">
                      <el-button :loading="correctingStrategy" :disabled="!strategyCorrection.trim()" @click="correctStrategy">更新策略</el-button>
                      <el-button class="orange-button" type="primary" :loading="confirmingStrategy" @click="confirmStrategy">确认策略并进入创意方向</el-button>
                    </div>
                  </div>
                </template>
                <p v-else class="source-lock-note">策略已确认并锁定；接下来可生成或调整创意方向。</p>
              </div>
            </div>
          </template>
        </section>

        <section v-else-if="selectedStage === 'plans'" class="stage-section">
          <StageHeading kicker="03 · 创意方向" title="先敲定方案，再开始生图" description="查看方案只会展示内容；只有点击“生成图片”时才会创建 Prompt Pack。" />

          <el-empty v-if="!strategy || !strategyConfirmed" description="请先确认原图理解与商品策略">
            <el-button type="primary" @click="selectStage('analysis')">前往分析与确认</el-button>
          </el-empty>

          <template v-else>
            <div class="planner-conditions">
              <div>
                <span class="condition-label">投放平台（可多选，也可不选）</span>
                <el-checkbox-group v-model="plannerPlatforms" class="choice-group">
                  <el-checkbox-button v-for="platform in platformOptions" :key="platform" :label="platform">{{ platform }}</el-checkbox-button>
                </el-checkbox-group>
              </div>
              <div>
                <span class="condition-label">风格偏好（可多选，也可不选）</span>
                <el-checkbox-group v-model="plannerStyles" class="choice-group">
                  <el-checkbox-button v-for="style in styleOptions" :key="style" :label="style">{{ style }}</el-checkbox-button>
                </el-checkbox-group>
              </div>
              <el-input v-model="plannerFeedback" type="textarea" :rows="2" placeholder="可选：补充创意要求，例如“避免节日元素，突出礼赠感”" />
              <div class="planner-condition-footer">
                <p>不选条件时，系统会主动生成差异化的方向组合。</p>
                <el-button class="orange-button" type="primary" :loading="refreshingPlans" @click="generateDirections">
                  {{ currentPlans.length ? '按当前条件重新生成 3 个方向' : '生成 3 个创意方向' }}
                </el-button>
              </div>
            </div>

            <div v-if="currentPlans.length" class="plan-grid" role="radiogroup" aria-label="创意方向选择">
              <article v-for="plan in currentPlans" :key="plan.id" class="plan-card" :class="{ selected: plan.id === selectedPlanId }" role="radio" :aria-checked="plan.id === selectedPlanId" :tabindex="0" @click="selectPlan(plan.id)" @keydown.enter.prevent="selectPlan(plan.id)" @keydown.space.prevent="selectPlan(plan.id)">
                <div class="plan-card-head">
                  <div>
                    <span class="plan-index">方向 {{ currentPlans.indexOf(plan) + 1 }}</span>
                    <h3>{{ plan.plan_name }}</h3>
                  </div>
                  <div class="plan-card-status"><el-tag effect="plain">{{ plan.target_platform }}</el-tag><el-tag v-if="plan.id === selectedPlanId" type="success" effect="plain">已选择</el-tag></div>
                </div>
                <div class="plan-tags"><span>{{ plan.visual_style }}</span><span>{{ plan.selling_angle }}</span></div>
                <p class="plan-description">{{ plan.plan_description }}</p>
                <el-collapse class="plan-details" @click.stop @keydown.stop>
                  <el-collapse-item title="展开详细设计" name="details">
                    <dl class="plan-facts">
                      <div><dt>画面描述</dt><dd>{{ plan.plan.visual_description }}</dd></div>
                      <div><dt>画面场景</dt><dd>{{ plan.plan.background_scene }}</dd></div>
                      <div><dt>主卖点</dt><dd>{{ plan.plan.main_selling_point }}</dd></div>
                      <div><dt>推荐理由</dt><dd>{{ plan.plan.recommendation_reason }}</dd></div>
                      <div><dt>文案方向</dt><dd>{{ plan.plan.copywriting_direction }}</dd></div>
                    </dl>
                  </el-collapse-item>
                </el-collapse>
                <div class="plan-revision" @click.stop @keydown.stop>
                  <el-input v-model="planFeedback[plan.id]" placeholder="想修改这个方向？用一句话说明" />
                  <el-button :loading="revisingPlanId === plan.id" :disabled="!planFeedback[plan.id]?.trim()" @click="revisePlan(plan)">修改方向</el-button>
                </div>
              </article>
            </div>

            <footer v-if="selectedPlan" class="stage-action-bar selection-bar">
              <p><strong>已选择：{{ selectedPlan.plan_name }}</strong><br />确认方案后才会为本轮生成 Prompt Pack 并开始出图。</p>
              <div class="generation-start-actions">
                <el-select v-if="!qualityModeEnabled" v-model="generationCount" aria-label="生成图片数量"><el-option v-for="count in generationCounts" :key="count" :label="`${count} 张`" :value="count" /></el-select>
                <el-button class="orange-button" type="primary" size="large" :loading="submittingTask" :disabled="Boolean(activeTask) || Boolean(activeQualityRun)" @click="startGeneration">
                  {{ qualityModeEnabled ? '启动 AI 审核生图' : '生成图片' }}
                </el-button>
              </div>
            </footer>

            <section v-if="selectedPlan" class="quality-mode-card">
              <div class="quality-mode-head">
                <div>
                  <span class="attention-label">可选 · 质量门控</span>
                  <h3>AI 审核生图</h3>
                  <p>让多模态模型审核每轮结果；低分会在预算内自动修订 Prompt，临界结果由你决定。</p>
                </div>
                <el-switch v-model="qualityModeEnabled" active-text="已开启" inactive-text="关闭" />
              </div>
              <div v-if="qualityModeEnabled" class="quality-mode-controls">
                <label>审核档位
                  <span class="quality-tier-options">
                    <el-tooltip content="宽松：优先提高出图效率；没有关键问题且整体可用即可推荐。" placement="top"><button type="button" :class="{ selected: qualityAcceptanceTier === 'loose' }" :aria-pressed="qualityAcceptanceTier === 'loose'" @click="qualityAcceptanceTier = 'loose'">宽松</button></el-tooltip>
                    <el-tooltip content="标准：适合常规投放；要求画面整体可靠、核心商品表现无明显短板。" placement="top"><button type="button" :class="{ selected: qualityAcceptanceTier === 'standard' }" :aria-pressed="qualityAcceptanceTier === 'standard'" @click="qualityAcceptanceTier = 'standard'">标准</button></el-tooltip>
                    <el-tooltip content="严格：适合高要求交付；核心商品、清晰度、商品性和文字都需接近无瑕。" placement="top"><button type="button" :class="{ selected: qualityAcceptanceTier === 'strict' }" :aria-pressed="qualityAcceptanceTier === 'strict'" @click="qualityAcceptanceTier = 'strict'">严格</button></el-tooltip>
                  </span>
                </label>
                <label>评分倾向
                  <el-select v-model="qualityProfile" aria-label="质量评分倾向">
                    <el-option label="还原优先" value="fidelity" />
                    <el-option label="平衡" value="balanced" />
                    <el-option label="商品性优先" value="commercial" />
                  </el-select>
                </label>
                <label>每轮生图数量
                  <el-select v-model="qualityImagesPerRound" aria-label="每轮生图数量"><el-option v-for="count in generationCounts" :key="count" :label="`${count} 张`" :value="count" /></el-select>
                  <small class="quality-field-help">每轮最多 4 张；本次最多 20 张。</small>
                </label>
                <label>最大轮数
                  <el-input-number v-model="qualityMaxRounds" :min="1" :max="qualityMaxRoundsLimit" :step="1" controls-position="right" />
                </label>
                <p class="quality-weight-note">{{ qualityProfileDescription }}</p>
                <p class="quality-budget">本次最多 {{ qualityBudget }} 张图片、{{ qualityBudget }} 次多模态审核、{{ Math.max(0, qualityMaxRounds - 1) }} 次 Prompt 修订。达到上限后必定等待你的决定。</p>
              </div>
            </section>

            <el-collapse v-if="historicalPlanBatches.length" class="history-collapse">
              <el-collapse-item title="查看历史创意方案" name="history">
                <div v-for="batch in historicalPlanBatches" :key="batch.id" class="history-batch">
                  <strong>{{ batch.kind === 'revision' ? '方向修改' : '方向批次' }}</strong>
                  <span>{{ batch.feedback || '无补充要求' }}</span>
                </div>
              </el-collapse-item>
            </el-collapse>
          </template>
        </section>

        <section v-else-if="selectedStage === 'generation'" class="stage-section">
          <StageHeading kicker="04 · 素材生成" title="按方向与轮次汇总素材" description="生成中的任务不会阻止你切换阶段或切换其他商品；每个商品的进度独立保存。" />

          <div v-if="previewImageUrl" class="material-reference">
            <img :src="previewImageUrl" alt="固定商品原图参考" />
            <div>
              <span class="attention-label">原图参考</span>
              <strong>始终以这张商品原图保持保真</strong>
              <p>选择任意素材后，可放大查看与原图的并排对比。</p>
            </div>
            <el-button :disabled="!focusedImage" @click="openComparison(focusedImage?.id)">放大对比</el-button>
          </div>

          <section v-if="latestQualityRun" class="quality-run-card" :class="`quality-${latestQualityRun.status}`">
            <div class="quality-run-head">
              <div>
                <span class="attention-label">AI 审核模式</span>
                <h3>{{ qualityRunTitle(latestQualityRun.status) }}</h3>
                <p>{{ qualityRunMessage(latestQualityRun) }}</p>
              </div>
              <el-tag effect="plain" :type="qualityRunTagType(latestQualityRun.status)">第 {{ latestQualityRun.current_round }}/{{ latestQualityRun.max_rounds }} 轮</el-tag>
            </div>
            <div class="quality-run-facts">
              <span>审核档位 · {{ qualityTierLabel(latestQualityRun.acceptance_tier) }}</span>
              <span>每轮 {{ latestQualityRun.images_per_round }} 张</span>
              <span>最高 {{ latestQualityRun.total_image_budget }} 张</span>
              <span v-if="latestQualityRun.recommended_image_id">推荐图片 #{{ latestQualityRun.recommended_image_id }}</span>
            </div>
            <div v-if="latestQualityRun.status === 'awaiting_human'" class="quality-decision-actions">
              <el-button type="primary" :loading="decidingQuality" @click="decideQuality('accept_recommended')">接受推荐候选</el-button>
              <template v-if="latestQualityRun.current_round < latestQualityRun.max_rounds">
                <el-button :loading="decidingQuality" @click="decideQuality('continue')">继续下一轮</el-button>
              </template>
              <span v-else>已达到设置的最大轮数；可接受候选或停止本次运行。</span>
              <el-button type="danger" plain :loading="stoppingQuality" @click="stopQuality">停止本次审核</el-button>
            </div>
            <div v-else-if="qualityRunCanStop(latestQualityRun.status)" class="quality-run-actions">
              <el-button type="danger" plain :loading="stoppingQuality" @click="stopQuality">停止 AI 审核</el-button>
              <span>停止会在当前模型调用完成后生效，不会再产生下一轮调用。</span>
            </div>
            <el-alert v-else-if="latestQualityRun.status === 'cancelled'" type="info" :closable="false" title="本次 AI 审核已停止，已生成的图片和评分都已保留。" />
            <el-alert v-else-if="latestQualityRun.status === 'failed'" type="error" :closable="false" :title="latestQualityRun.error_message || 'AI 审核运行失败，未自动重复外部调用。'" />
            <el-button v-if="latestQualityRun.status === 'failed'" type="primary" plain :loading="retryingQuality" @click="retryQuality">重新启动本次审核</el-button>
          </section>

          <el-empty v-if="!materialGroups.length" description="选择一个创意方向后即可发起第一轮生图">
            <el-button type="primary" @click="selectStage('plans')">选择创意方向</el-button>
          </el-empty>

          <div v-else class="material-groups">
            <article v-for="group in materialGroups" :key="group.task.id" class="material-group">
              <header class="material-group-head">
                <div>
                  <span>方向 · {{ group.planName }}</span>
                  <h3>第 {{ group.task.iteration }} 轮素材</h3>
                  <p>{{ taskStatusText(group.task) }}</p>
                </div>
                <el-tag :type="taskTagType(group.task.status)" effect="plain">{{ taskStatusLabel(group.task.status) }}</el-tag>
              </header>
              <el-progress v-if="['queued', 'running'].includes(group.task.status)" :percentage="taskProgress(group.task)" :show-text="false" />
              <el-alert v-if="group.task.status === 'failed'" type="error" :closable="false" :title="group.task.error_message || '本轮生成失败'" />
              <el-collapse v-if="promptForTask(group.task)" class="prompt-collapse">
                <el-collapse-item title="查看本轮提示词（只读）" name="prompt">
                  <dl class="detail-list">
                    <div><dt>正向提示词</dt><dd>{{ promptForTask(group.task)?.prompt.positive_prompt }}</dd></div>
                    <div><dt>负向提示词</dt><dd>{{ promptForTask(group.task)?.prompt.negative_prompt }}</dd></div>
                    <div><dt>一致性说明</dt><dd>{{ promptForTask(group.task)?.prompt.product_consistency_notes }}</dd></div>
                  </dl>
                </el-collapse-item>
              </el-collapse>
              <div v-if="group.images.length" class="image-grid">
                <article v-for="image in group.images" :key="image.id" class="material-card" :class="{ delivery: image.is_selected, focused: image.id === selectedImageId }">
                  <button class="material-image-button" type="button" :aria-label="`聚焦${group.planName}生成图`" @click="selectedImageId = image.id">
                    <img :src="assetUrl(image.image_url)" :alt="`${group.planName} 生成图`" />
                  </button>
                  <div class="material-card-meta">
                    <span v-if="image.is_selected" class="delivery-label">交付图</span>
                    <span v-else-if="image.is_recommended" class="recommended-label">AI 推荐</span>
                    <span v-else>待你挑选</span>
                    <strong v-if="image.score !== null && image.score !== undefined" class="image-score">AI 参考 {{ (image.score / 10).toFixed(1) }}/10</strong>
                  </div>
                  <el-collapse v-if="image.review" class="review-collapse">
                    <el-collapse-item title="查看 AI 审核结果" name="review">
                      <p class="review-result-title">评分结果</p>
                      <div class="review-score-grid">
                        <span>还原度 {{ image.review.review.product_consistency }}/10</span>
                        <span>清晰度 {{ image.review.review.product_clarity }}/10</span>
                        <span>商品性 {{ image.review.review.commercial_value }}/10</span>
                        <span>文字正确性 {{ image.review.review.text_accuracy }}/10</span>
                      </div>
                      <p v-if="image.review.review.summary" class="review-summary">{{ image.review.review.summary }}</p>
                      <p v-if="image.review.review.hard_defects.length" class="review-risk">问题：{{ image.review.review.hard_defects.join('；') }}</p>
                      <p v-else-if="image.review.review.defects.length" class="review-risk">问题：{{ image.review.review.defects.join('；') }}</p>
                      <ul v-if="image.review.review.evidence.length" class="review-evidence">
                        <li v-for="(evidence, evidenceIndex) in image.review.review.evidence" :key="`${image.id}-${evidenceIndex}`">{{ dimensionLabel(evidence.dimension) }}：{{ evidence.observation }}</li>
                      </ul>
                      <p v-if="image.review.review.prompt_revision" class="review-summary">下一轮建议：{{ image.review.review.prompt_revision }}</p>
                    </el-collapse-item>
                  </el-collapse>
                  <div class="material-card-actions">
                    <el-button class="delivery-button" type="primary" @click="selectDeliveryImage(image)">
                      {{ image.is_selected ? '当前交付图' : '设为交付图' }}
                    </el-button>
                    <el-popover placement="bottom-end" :width="176" trigger="click">
                      <template #reference><el-button aria-label="更多图片操作">更多</el-button></template>
                      <div class="more-actions">
                        <el-button text @click="openComparison(image.id)">原图对比</el-button>
                        <el-button text @click="openIteration(image)">基于此图修改</el-button>
                      </div>
                    </el-popover>
                  </div>
                </article>
              </div>
            </article>
          </div>
        </section>

        <section v-else-if="selectedStage === 'delivery'" class="stage-section">
          <StageHeading kicker="05 · 选图、文案与交付" title="下载交付图，复制当前文案" description="每张交付图只保留一份当前稿：停止输入约 800ms 后会自动保存。" />

          <el-empty v-if="!selectedImage" description="请先在素材区选定一张交付图">
            <el-button type="primary" @click="selectStage('generation')">前往素材生成</el-button>
          </el-empty>
          <template v-else>
            <div class="delivery-layout">
              <div class="delivery-image-card">
                <img :src="assetUrl(selectedImage.image_url)" alt="当前交付图" />
                <a :href="assetUrl(selectedImage.image_url)" :download="`${store.current?.product_name || 'productshot'}-${selectedImage.id}.png`">
                  <el-button class="orange-button" type="primary" size="large">下载图片</el-button>
                </a>
                <el-button text @click="selectStage('generation')">返回素材区更换交付图</el-button>
              </div>

              <div class="copy-card">
                <template v-if="!activeCopy">
                  <div class="empty-work-card compact">
                    <strong>为这张交付图生成文案</strong>
                    <p>生成后会得到小红书、朋友圈、淘宝、闲鱼四个平台的当前稿。</p>
                    <el-button class="orange-button" type="primary" :loading="creatingCopy" @click="generateCopy">生成文案</el-button>
                  </div>
                </template>
                <template v-else>
                  <div class="copy-card-head">
                    <div><span class="attention-label">当前稿</span><h3>{{ copyEditor.title || '未命名文案' }}</h3></div>
                    <span class="copy-save-state" :class="copySaveState">{{ copySaveStateLabel }}</span>
                  </div>
                  <el-input v-model="copyEditor.title" placeholder="文案标题" />
                  <el-tabs v-model="copyPlatform" class="copy-tabs">
                    <el-tab-pane label="小红书" name="xiaohongshu">
                      <el-input v-model="copyEditor.xiaohongshu_title" placeholder="小红书标题" />
                      <el-input v-model="copyEditor.xiaohongshu_text" type="textarea" :rows="8" placeholder="小红书正文" />
                      <el-button text @click="copyText(`${copyEditor.xiaohongshu_title}\n${copyEditor.xiaohongshu_text}`)">复制小红书文案</el-button>
                    </el-tab-pane>
                    <el-tab-pane label="朋友圈" name="moments">
                      <el-input v-model="copyEditor.moments_text" type="textarea" :rows="10" placeholder="朋友圈文案" />
                      <el-button text @click="copyText(copyEditor.moments_text)">复制朋友圈文案</el-button>
                    </el-tab-pane>
                    <el-tab-pane label="淘宝" name="taobao">
                      <el-input v-model="copyEditor.taobao_text" type="textarea" :rows="10" placeholder="淘宝文案" />
                      <el-button text @click="copyText(copyEditor.taobao_text)">复制淘宝文案</el-button>
                    </el-tab-pane>
                    <el-tab-pane label="闲鱼" name="xianyu">
                      <el-input v-model="copyEditor.xianyu_text" type="textarea" :rows="10" placeholder="闲鱼文案" />
                      <el-button text @click="copyText(copyEditor.xianyu_text)">复制闲鱼文案</el-button>
                    </el-tab-pane>
                  </el-tabs>
                  <div class="copy-rewrite">
                    <el-input v-model="copyRewriteInstruction" placeholder="例如：语气更克制，突出闲置转卖价值" />
                    <el-button :loading="rewritingCopy" :disabled="!copyRewriteInstruction.trim()" @click="rewriteCopy">AI 改写当前稿</el-button>
                  </div>
                </template>
              </div>
            </div>
          </template>
        </section>
      </main>
    </div>

    <el-dialog v-model="iterationOpen" width="min(680px, 92vw)" title="基于此图修改">
      <template v-if="iterationImage">
        <div class="iteration-dialog">
          <img :src="assetUrl(iterationImage.image_url)" alt="用于修改的生成图" />
          <div>
            <p>这轮将以当前图片作为视觉参考，同时继续遵守已锁定的商品事实与原图。</p>
            <el-input v-model="iterationInstruction" type="textarea" :rows="5" placeholder="描述你想调整的部分，例如“背景更有夏日感，商品保持相同角度”" />
            <div class="iteration-actions">
              <el-select v-model="generationCount" aria-label="修改图片生成数量"><el-option v-for="count in generationCounts" :key="count" :label="`${count} 张`" :value="count" /></el-select>
              <el-button class="orange-button" type="primary" :loading="submittingIteration" :disabled="!iterationInstruction.trim() || Boolean(activeTask)" @click="submitIteration">生成修改图</el-button>
            </div>
          </div>
        </div>
      </template>
    </el-dialog>

    <el-drawer v-model="analysisDetailsOpen" title="完整分析详情" direction="rtl" size="min(560px, 100vw)" append-to-body>
      <div v-if="visualAnalysis" class="drawer-detail-section">
        <span class="attention-label">原图理解</span>
        <dl class="detail-list">
          <div><dt>商品外观</dt><dd>{{ visualAnalysis.analysis.product_appearance }}</dd></div>
          <div><dt>主色调</dt><dd>{{ joinValues(visualAnalysis.analysis.dominant_colors) }}</dd></div>
          <div><dt>材质</dt><dd>{{ joinValues(visualAnalysis.analysis.materials) }}</dd></div>
          <div><dt>可见文字 / Logo</dt><dd>{{ joinValues(visualAnalysis.analysis.visible_text_or_logo) }}</dd></div>
          <div><dt>主体清晰度</dt><dd>{{ visualAnalysis.analysis.subject_clarity }}</dd></div>
          <div><dt>原图问题</dt><dd>{{ joinValues(visualAnalysis.analysis.background_issues) }}</dd></div>
          <div><dt>保真约束</dt><dd>{{ joinValues(visualAnalysis.analysis.fidelity_constraints) }}</dd></div>
          <div><dt>营销机会</dt><dd>{{ joinValues(visualAnalysis.analysis.marketing_opportunities) }}</dd></div>
        </dl>
      </div>
      <div v-if="strategy" class="drawer-detail-section">
        <span class="attention-label">商品策略</span>
        <dl class="detail-list">
          <div><dt>核心特征</dt><dd>{{ joinValues(strategy.analysis.core_features) }}</dd></div>
          <div><dt>建议视觉风格</dt><dd>{{ joinValues(strategy.analysis.recommended_visual_styles) }}</dd></div>
          <div><dt>图片注意点</dt><dd>{{ joinValues(strategy.analysis.image_issues) }}</dd></div>
          <div><dt>一致性规则</dt><dd>{{ joinValues(strategy.analysis.product_consistency_rules) }}</dd></div>
        </dl>
      </div>
    </el-drawer>

    <ImageComparisonDrawer
      v-if="hasProject"
      v-model="comparisonOpen"
      :source-url="previewImageUrl"
      :images="allImages"
      :selected-image-id="selectedImageId"
      @select="selectedImageId = $event"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import ImageComparisonDrawer from '../components/ImageComparisonDrawer.vue'
import WorkflowStatusCenter from '../components/WorkflowStatusCenter.vue'
import { assetUrl, errorMessage } from '../api/client'
import { clearStudioDraft, loadStudioDraft, saveStudioDraft } from '../utils/studioDraft'
import {
  confirmProductAnalysis,
  confirmSource,
  confirmVisualAnalysis,
  correctProductAnalysis,
  correctVisualAnalysis,
  createCopywriting,
  createImagePromptPack,
  createPlanPromptPack,
  createProject,
  createQualityRun,
  decideQualityRun,
  refreshCreativePlans,
  replacePrimaryAsset,
  reviseCreativePlan,
  retryQualityRun,
  rewriteCopywriting,
  selectGeneratedImage,
  submitGenerationTask,
  stopQualityRun,
  type CopywritingPayload,
  type CreativePlan,
  type GeneratedImage,
  type GenerationTask,
  type PromptPack,
  type QualityAcceptanceTier,
  type QualityProfile,
  type QualityRun,
  updateCopywriting,
  updateProject,
  uploadAsset
} from '../api/productshot'
import { type StudioStage, type StudioStageKey, type WorkflowUiStatus, useProjectStore } from '../stores/project'

const StageHeading = {
  props: { kicker: { type: String, required: true }, title: { type: String, required: true }, description: { type: String, required: true } },
  template: '<div class="stage-heading"><div><span class="stage-kicker">{{ kicker }}</span><h2>{{ title }}</h2><p>{{ description }}</p></div></div>'
}

const route = useRoute()
const router = useRouter()
const store = useProjectStore()

const platformOptions = ['小红书', '朋友圈', '淘宝', '闲鱼']
const styleOptions = ['高级极简', '生活方式', '质感特写', '节日促销']
const generationCounts = [1, 2, 3, 4]

const briefForm = reactive({ product_name: '', product_category: '', core_selling_points: '', target_audience: '' })
const selectedFile = ref<File | null>(null)
const localPreviewUrl = ref('')
const localPreviewProjectId = ref<number | null>(null)
const savingSource = ref(false)
const runningVisual = ref(false)
const correctingVisual = ref(false)
const confirmingVisual = ref(false)
const runningStrategy = ref(false)
const correctingStrategy = ref(false)
const confirmingStrategy = ref(false)
const refreshingPlans = ref(false)
const revisingPlanId = ref<number | null>(null)
const submittingTask = ref(false)
const submittingIteration = ref(false)
const stoppingQuality = ref(false)
const decidingQuality = ref(false)
const retryingQuality = ref(false)
const creatingCopy = ref(false)
const rewritingCopy = ref(false)
const selectedStage = ref<StudioStageKey>('brief')
const selectedPlanId = ref<number | null>(null)
const selectedImageId = ref<number | null>(null)
const generationCount = ref(2)
const qualityModeEnabled = ref(false)
const qualityProfile = ref<QualityProfile>('balanced')
const qualityAcceptanceTier = ref<QualityAcceptanceTier>('standard')
const qualityImagesPerRound = ref(2)
const qualityMaxRounds = ref(3)
const plannerPlatforms = ref<string[]>([])
const plannerStyles = ref<string[]>([])
const plannerFeedback = ref('')
const planFeedback = reactive<Record<number, string>>({})
const visualCorrection = ref('')
const strategyCorrection = ref('')
const analysisDetailsOpen = ref(false)
const comparisonOpen = ref(false)
const iterationOpen = ref(false)
const iterationImage = ref<GeneratedImage | null>(null)
const iterationInstruction = ref('')
const hasDraft = ref(false)
const draftReady = ref(false)
const copyPlatform = ref('xiaohongshu')
const copyRewriteInstruction = ref('')
const copySaveState = ref<'idle' | 'pending' | 'saving' | 'saved' | 'failed'>('idle')
const copyEditorReady = ref(false)
let copySaveTimer: ReturnType<typeof window.setTimeout> | null = null
let draftSaveTimer: ReturnType<typeof window.setTimeout> | null = null
let routeLoadId = 0

const copyEditor = reactive<CopywritingPayload>({
  title: '', selling_points: [], xiaohongshu_title: '', xiaohongshu_text: '', moments_text: '', taobao_text: '', xianyu_text: '', tags: []
})

const projectId = computed(() => {
  const value = route.params.id
  return typeof value === 'string' && Number(value) > 0 ? Number(value) : 0
})
const hasProject = computed(() => projectId.value > 0)
const sourceConfirmed = computed(() => Boolean(store.current?.source_confirmed_at))
const strategyConfirmed = computed(() => Boolean(store.current?.strategy_confirmed_at))
const primaryAsset = computed(() => store.current?.assets.find((asset) => asset.is_primary) || store.current?.assets[0])
const previewImageUrl = computed(() => localPreviewUrl.value && localPreviewProjectId.value === projectId.value ? localPreviewUrl.value : (primaryAsset.value ? assetUrl(primaryAsset.value.file_url) : ''))
const visualAnalysis = computed(() => store.current?.visual_analysis || null)
const strategy = computed(() => store.current?.latest_analysis || null)
const currentPlans = computed(() => (store.current?.creative_plans || []).filter((plan) => plan.is_current).sort((a, b) => a.display_order - b.display_order || a.id - b.id))
const selectedPlan = computed(() => currentPlans.value.find((plan) => plan.id === selectedPlanId.value) || null)
const allImages = computed(() => store.current?.generated_images || [])
const focusedImage = computed(() =>
  allImages.value.find((image) => image.id === selectedImageId.value) || allImages.value.find((image) => image.is_selected) || allImages.value[0] || null
)
const selectedImage = computed(() => allImages.value.find((image) => image.is_selected) || null)
const activeCopy = computed(() => store.current?.copywriting.find((copy) => copy.image_id === selectedImage.value?.id) || null)
const historicalPlanBatches = computed(() => (store.current?.creative_plan_batches || []).filter((batch) => !batch.plans.some((plan) => plan.is_current)))
const materialGroups = computed(() => {
  const tasks = [...(store.current?.generation_tasks || [])].sort((a, b) => a.id - b.id)
  return tasks.map((task) => ({
    task,
    planName: store.current?.creative_plans.find((plan) => plan.id === task.plan_id)?.plan_name || '历史创意方向',
    images: allImages.value.filter((image) => image.task_id === task.id)
  })).filter((group) => group.images.length || ['queued', 'running', 'failed'].includes(group.task.status))
})
const activeTask = computed(() => store.current?.generation_tasks.find((task) => ['queued', 'running'].includes(task.status)) || null)
const latestQualityRun = computed(() => store.current?.quality_runs?.[0] || null)
const activeQualityRun = computed(() =>
  store.current?.quality_runs?.find((run) => ['preparing', 'generating', 'reviewing', 'refining', 'awaiting_human', 'stop_requested'].includes(run.status)) || null
)
const qualityMaxRoundsLimit = computed(() => Math.max(1, Math.min(5, Math.floor(20 / qualityImagesPerRound.value))))
const qualityBudget = computed(() => qualityImagesPerRound.value * qualityMaxRounds.value)
const qualityProfileDescription = computed(() => ({
  fidelity: '还原优先：还原度 40%、清晰度 25%、商品性 15%、文字正确性 20%。',
  balanced: '平衡：还原度 30%、清晰度 25%、商品性 25%、文字正确性 20%。',
  commercial: '商品性优先：还原度 20%、清晰度 20%、商品性 40%、文字正确性 20%。'
} as Record<QualityProfile, string>)[qualityProfile.value])
const latestFailure = computed(() => {
  const latest = store.current?.workflow_events[0]
  return latest?.status === 'failed' ? latest : null
})
const currentOperation = computed(() => store.currentContext?.operation || null)
const displaySteps = computed(() => store.steps.map((step) => currentOperation.value?.stepKey === step.key ? { ...step, status: 'running' as const } : step))

const pageTitle = computed(() => hasProject.value ? store.current?.product_name || '商品工作台' : '创建商品营销项目')
const pageDescription = computed(() => hasProject.value ? '按商品隔离进度；你可以随时切换商品和阶段。' : '从商品事实与可靠原图开始。')
const workflowDisplay = computed<{ status: WorkflowUiStatus; title: string; message: string; primaryLabel?: string; startedAt?: string | null }>(() => {
  if (!hasProject.value) return { status: 'idle', title: '准备商品与原图', message: '填写最少商品信息并上传原图，确认后才会进入后续工作流。' }
  if (currentOperation.value) return { status: 'running', title: currentOperation.value.title, message: currentOperation.value.message, startedAt: currentOperation.value.startedAt }
  if (activeQualityRun.value && qualityRunCanStop(activeQualityRun.value.status)) {
    return { status: 'running', title: qualityRunTitle(activeQualityRun.value.status), message: qualityRunMessage(activeQualityRun.value), startedAt: activeQualityRun.value.started_at || activeQualityRun.value.created_at }
  }
  if (activeQualityRun.value?.status === 'awaiting_human') {
    return { status: 'action_required', title: qualityRunTitle(activeQualityRun.value.status), message: qualityRunMessage(activeQualityRun.value), primaryLabel: '查看 AI 审核' }
  }
  if (latestFailure.value && !activeTask.value) return { status: 'failed', title: '最近一步需要处理', message: latestFailure.value.error_message || latestFailure.value.summary, primaryLabel: '查看对应阶段', startedAt: latestFailure.value.started_at }
  if (activeTask.value) return { status: 'running', title: '正在生成素材', message: taskStatusText(activeTask.value), startedAt: activeTask.value.started_at || activeTask.value.created_at }
  if (!sourceConfirmed.value) return { status: 'action_required', title: '等待确认商品与原图', message: '确认后商品信息和原图会锁定，成为后续保真基准。', primaryLabel: '去确认' }
  if (!visualAnalysis.value) return { status: 'action_required', title: '等待原图理解', message: '先提取商品外观与保真约束，不会自动生成创意方向。', primaryLabel: '开始理解原图' }
  if (!visualAnalysis.value.analysis.human_reviewed) return { status: 'action_required', title: '等待确认原图理解', message: '请用摘要核对关键商品事实；如有错误，可用自然语言纠正。', primaryLabel: '去确认理解' }
  if (!strategy.value) return { status: 'action_required', title: '等待生成商品策略', message: '确认理解后，仅生成策略；创意方向需要下一步显式发起。', primaryLabel: '生成商品策略' }
  if (!strategyConfirmed.value) return { status: 'action_required', title: '等待确认商品策略', message: '可先用自然语言纠正策略，确认后再进入创意方向。', primaryLabel: '去确认策略' }
  if (!currentPlans.value.length) return { status: 'action_required', title: '等待生成创意方向', message: '选择可选的平台和风格条件后，生成三条可比较的创意方向。', primaryLabel: '生成创意方向' }
  if (!allImages.value.length) return { status: 'action_required', title: '等待选择创意方向', message: '先敲定一个方向，再点击生成图片。', primaryLabel: '选择方向' }
  if (!selectedImage.value) return { status: 'action_required', title: '等待选择交付图', message: '请在素材区自行选择一张图片作为交付图。', primaryLabel: '去选择' }
  return { status: 'success', title: '交付图已选定', message: '可以继续生成其他方向素材，或下载图片并复制当前文案。', primaryLabel: '查看交付' }
})
const studioStages = computed<StudioStage[]>(() => {
  const available: Record<StudioStageKey, boolean> = {
    brief: true,
    analysis: sourceConfirmed.value,
    plans: Boolean(strategy.value && strategyConfirmed.value),
    generation: Boolean(currentPlans.value.length),
    delivery: Boolean(allImages.value.length)
  }
  const status: Record<StudioStageKey, StudioStage['status']> = {
    brief: sourceConfirmed.value ? 'success' : 'current',
    analysis: strategy.value ? 'success' : (visualAnalysis.value ? 'current' : 'available'),
    plans: currentPlans.value.length ? 'success' : 'available',
    generation: activeTask.value || activeQualityRun.value ? 'running' : (allImages.value.length ? 'success' : 'available'),
    delivery: selectedImage.value?.is_selected ? 'success' : 'available'
  }
  const labels: Record<StudioStageKey, [string, string, string]> = {
    brief: ['商品与原图', '确认并锁定生产参考', '先确认商品与原图'],
    analysis: ['分析与确认', '自然语言纠正原图理解', '先确认商品与原图'],
    plans: ['创意方向', '选择方案，暂不生成提示词', '先确认商品策略'],
    generation: ['素材生成', '按方向与轮次查看素材', '先生成创意方向'],
    delivery: ['交付与文案', '下载图片与复制当前稿', '先生成至少一张图片']
  }
  return (Object.keys(labels) as StudioStageKey[]).map((key) => ({
    key, title: labels[key][0], description: labels[key][1], lockedReason: labels[key][2], available: available[key], status: available[key] ? status[key] : 'locked'
  }))
})
const copySaveStateLabel = computed(() => ({ idle: '当前稿', pending: '待自动保存', saving: '保存中…', saved: '已保存', failed: '保存失败' })[copySaveState.value])

onMounted(loadFromRoute)
onBeforeUnmount(() => {
  if (localPreviewUrl.value) URL.revokeObjectURL(localPreviewUrl.value)
  if (copySaveTimer) window.clearTimeout(copySaveTimer)
  if (draftSaveTimer) window.clearTimeout(draftSaveTimer)
})
watch(() => route.params.id, loadFromRoute)
watch(currentPlans, (plans) => { if (!plans.some((plan) => plan.id === selectedPlanId.value)) selectedPlanId.value = plans[0]?.id || null }, { immediate: true })
watch(selectedImage, () => syncCopyEditor(), { immediate: true })
watch(activeCopy, () => syncCopyEditor())
watch(copyEditor, scheduleCopySave, { deep: true, flush: 'sync' })
watch(briefForm, scheduleDraftSave, { deep: true })
watch(qualityMaxRoundsLimit, (limit) => {
  if (qualityMaxRounds.value > limit) qualityMaxRounds.value = limit
})

async function loadFromRoute() {
  const requestId = ++routeLoadId
  clearCopySave()
  if (!hasProject.value) {
    resetTransientEditor()
    store.setCurrentProject(null)
    selectedStage.value = 'brief'
    await restoreDraft(requestId)
    return
  }
  resetTransientEditor()
  const targetProjectId = projectId.value
  store.setCurrentProject(targetProjectId)
  try {
    await store.load(targetProjectId)
    if (requestId !== routeLoadId || projectId.value !== targetProjectId) return
    syncBriefForm()
    selectedImageId.value = store.current?.generated_images.find((image) => image.is_selected)?.id || store.current?.generated_images[0]?.id || null
    selectedPlanId.value = currentPlans.value[0]?.id || null
    const savedStage = store.currentContext?.stage
    selectedStage.value = studioStages.value.find((item) => item.key === savedStage)?.available ? savedStage || recommendedStage() : recommendedStage()
    store.setStage(targetProjectId, selectedStage.value)
  } catch (error) {
    if (requestId === routeLoadId) ElMessage.error(errorMessage(error))
  }
}

function resetTransientEditor() {
  if (localPreviewUrl.value) URL.revokeObjectURL(localPreviewUrl.value)
  localPreviewUrl.value = ''
  localPreviewProjectId.value = null
  selectedFile.value = null
  Object.assign(briefForm, { product_name: '', product_category: '', core_selling_points: '', target_audience: '' })
  selectedPlanId.value = null
  selectedImageId.value = null
  visualCorrection.value = ''
  strategyCorrection.value = ''
  iterationImage.value = null
  iterationInstruction.value = ''
  iterationOpen.value = false
  hasDraft.value = false
  draftReady.value = false
}

async function restoreDraft(requestId: number) {
  draftReady.value = false
  try {
    const draft = await loadStudioDraft()
    if (requestId !== routeLoadId || hasProject.value) return
    hasDraft.value = Boolean(draft)
    if (draft) {
      Object.assign(briefForm, draft.form)
      if (draft.file) {
        selectedFile.value = new File([draft.file], draft.fileName || 'product-image', {
          type: draft.fileType || draft.file.type,
          lastModified: draft.fileLastModified || draft.updatedAt
        })
        localPreviewUrl.value = URL.createObjectURL(selectedFile.value)
        localPreviewProjectId.value = 0
      }
    }
  } catch {
    hasDraft.value = false
  } finally {
    if (requestId === routeLoadId && !hasProject.value) draftReady.value = true
  }
}

function scheduleDraftSave() {
  if (hasProject.value || !draftReady.value) return
  if (draftSaveTimer) window.clearTimeout(draftSaveTimer)
  draftSaveTimer = window.setTimeout(() => { void persistDraft() }, 250)
}

async function persistDraft() {
  if (hasProject.value || !draftReady.value) return
  try {
    await saveStudioDraft({
      form: { ...briefForm },
      file: selectedFile.value || undefined,
      fileName: selectedFile.value?.name,
      fileType: selectedFile.value?.type,
      fileLastModified: selectedFile.value?.lastModified,
      updatedAt: Date.now()
    })
    hasDraft.value = true
  } catch {
    // Storage can be unavailable in private browsing; creation remains usable.
  }
}

async function discardDraft() {
  if (draftSaveTimer) window.clearTimeout(draftSaveTimer)
  await clearStudioDraft()
  resetTransientEditor()
  hasDraft.value = false
  draftReady.value = true
}

function syncBriefForm() {
  if (!store.current) return
  Object.assign(briefForm, {
    product_name: store.current.product_name || '', product_category: store.current.product_category || '',
    core_selling_points: store.current.core_selling_points || '', target_audience: store.current.target_audience || ''
  })
}

function recommendedStage(): StudioStageKey {
  if (!sourceConfirmed.value) return 'brief'
  if (!strategy.value || !strategyConfirmed.value) return 'analysis'
  if (!currentPlans.value.length) return 'plans'
  if (!allImages.value.length || activeTask.value || !selectedImage.value) return 'generation'
  return 'delivery'
}

function selectStage(stage: StudioStageKey) {
  if (studioStages.value.find((item) => item.key === stage)?.available) {
    selectedStage.value = stage
    if (hasProject.value) store.setStage(projectId.value, stage)
  }
}

function handleFile(file: UploadFile) {
  if (localPreviewUrl.value) URL.revokeObjectURL(localPreviewUrl.value)
  selectedFile.value = file.raw || null
  localPreviewUrl.value = selectedFile.value ? URL.createObjectURL(selectedFile.value) : ''
  localPreviewProjectId.value = selectedFile.value ? projectId.value : null
  scheduleDraftSave()
}

function openFilePicker() {
  document.querySelector<HTMLInputElement>('.source-upload input[type="file"]')?.click()
}

function sourcePayload() {
  return {
    product_name: briefForm.product_name.trim(), product_category: briefForm.product_category.trim(),
    core_selling_points: briefForm.core_selling_points.trim(), target_audience: briefForm.target_audience.trim()
  }
}

async function saveAndConfirmSource() {
  if (!briefForm.product_name.trim()) return ElMessage.warning('请填写商品名称')
  if (!hasProject.value && !selectedFile.value) return ElMessage.warning('请上传商品原图')
  savingSource.value = true
  try {
    if (!hasProject.value) {
      const project = await createProject(sourcePayload())
      if (selectedFile.value) await uploadAsset(project.id, selectedFile.value)
      await confirmSource(project.id)
      await clearStudioDraft()
      hasDraft.value = false
      if (localPreviewUrl.value) URL.revokeObjectURL(localPreviewUrl.value)
      localPreviewUrl.value = ''
      localPreviewProjectId.value = null
      selectedFile.value = null
      await router.replace(`/studio/${project.id}`)
      ElMessage.success('商品与原图已确认并锁定')
      return
    }
    await updateProject(projectId.value, sourcePayload())
    if (selectedFile.value) await replacePrimaryAsset(projectId.value, selectedFile.value)
    await confirmSource(projectId.value)
    await store.load(projectId.value)
    selectedFile.value = null
    if (localPreviewUrl.value) URL.revokeObjectURL(localPreviewUrl.value)
    localPreviewUrl.value = ''
    localPreviewProjectId.value = null
    ElMessage.success('商品与原图已确认并锁定')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    savingSource.value = false
  }
}

async function runWithOperation<T>(stepKey: string, title: string, message: string, action: () => Promise<T>) {
  if (!hasProject.value) return undefined
  const operationId = store.beginOperation(projectId.value, { stepKey, title, message })
  try {
    return await action()
  } finally {
    store.endOperation(projectId.value, operationId)
  }
}

async function runVisual() {
  if (!hasProject.value) return
  runningVisual.value = true
  try {
    await runWithOperation('visual_analysis', '正在理解原图', '正在提取商品外观、材质与保真约束。', () => store.runVisualAnalysis(projectId.value))
    ElMessage.success('原图理解完成，请确认关键事实')
  } catch (error) { ElMessage.error(errorMessage(error)) } finally { runningVisual.value = false }
}

async function correctVisual() {
  if (!hasProject.value || !visualCorrection.value.trim()) return
  correctingVisual.value = true
  try {
    await runWithOperation('visual_analysis', '正在更新原图理解', '正在根据你的说明修正商品事实与保真约束。', () => correctVisualAnalysis(projectId.value, visualCorrection.value.trim()))
    visualCorrection.value = ''
    await store.refresh(projectId.value)
    ElMessage.success('已根据你的说明更新原图理解')
  } catch (error) { ElMessage.error(errorMessage(error)) } finally { correctingVisual.value = false }
}

async function confirmVisual() {
  if (!hasProject.value) return
  confirmingVisual.value = true
  try {
    await confirmVisualAnalysis(projectId.value)
    await store.refresh(projectId.value)
    ElMessage.success('原图理解已确认；下一步可生成商品策略')
  } catch (error) { ElMessage.error(errorMessage(error)) } finally { confirmingVisual.value = false }
}

async function runStrategy() {
  if (!hasProject.value) return
  runningStrategy.value = true
  try {
    await runWithOperation('analysis', '正在生成商品策略', '正在提炼目标人群、核心卖点与视觉策略。', () => store.runProductAnalysis(projectId.value))
    ElMessage.success('商品策略已生成，请确认或纠正后再进入创意方向')
  } catch (error) { ElMessage.error(errorMessage(error)) } finally { runningStrategy.value = false }
}

async function correctStrategy() {
  if (!hasProject.value || !strategyCorrection.value.trim()) return
  correctingStrategy.value = true
  try {
    await runWithOperation('analysis', '正在更新商品策略', '正在根据你的说明调整人群、卖点与视觉策略。', () => correctProductAnalysis(projectId.value, strategyCorrection.value.trim()))
    strategyCorrection.value = ''
    await store.refresh(projectId.value)
    ElMessage.success('商品策略已更新，请继续核对')
  } catch (error) { ElMessage.error(errorMessage(error)) } finally { correctingStrategy.value = false }
}

async function confirmStrategy() {
  if (!hasProject.value) return
  confirmingStrategy.value = true
  try {
    await confirmProductAnalysis(projectId.value)
    await store.refresh(projectId.value)
    selectStage('plans')
    ElMessage.success('商品策略已确认并锁定')
  } catch (error) { ElMessage.error(errorMessage(error)) } finally { confirmingStrategy.value = false }
}

function selectPlan(planId: number) {
  selectedPlanId.value = planId
}

async function generateDirections() {
  if (!hasProject.value) return
  refreshingPlans.value = true
  try {
    await runWithOperation('plans', '正在生成创意方向', '正在组合平台、风格与商品策略，生成可比较的方向。', () => refreshCreativePlans(projectId.value, { feedback: plannerFeedback.value.trim(), platforms: plannerPlatforms.value, style_presets: plannerStyles.value }))
    plannerFeedback.value = ''
    await store.refresh(projectId.value)
    selectedPlanId.value = currentPlans.value[0]?.id || null
    ElMessage.success('已生成 3 个可比较的创意方向')
  } catch (error) { ElMessage.error(errorMessage(error)) } finally { refreshingPlans.value = false }
}

async function revisePlan(plan: CreativePlan) {
  const instruction = planFeedback[plan.id]?.trim()
  if (!hasProject.value || !instruction) return
  revisingPlanId.value = plan.id
  try {
    const revised = await runWithOperation('plans', '正在修改创意方向', '正在按你的说明重写当前方向，并保持它原有的位置。', () => reviseCreativePlan(projectId.value, plan.id, instruction))
    planFeedback[plan.id] = ''
    await store.refresh(projectId.value)
    selectedPlanId.value = revised?.id || null
    ElMessage.success('已更新该创意方向；提示词尚未生成')
  } catch (error) { ElMessage.error(errorMessage(error)) } finally { revisingPlanId.value = null }
}

async function startGeneration() {
  const plan = selectedPlan.value
  if (!hasProject.value || !plan) return ElMessage.warning('请先选择一个创意方向')
  if (activeTask.value || activeQualityRun.value) return ElMessage.warning('当前商品已有未结束的素材任务或 AI 审核，请先等待完成或停止。')
  submittingTask.value = true
  try {
    if (qualityModeEnabled.value) {
      await createQualityRun(projectId.value, {
        plan_id: plan.id,
        quality_profile: qualityProfile.value,
        acceptance_tier: qualityAcceptanceTier.value,
        images_per_round: qualityImagesPerRound.value,
        max_rounds: qualityMaxRounds.value
      })
      await store.refresh(projectId.value)
      selectStage('generation')
      ElMessage.success('AI 审核模式已启动，将按质量结果决定是否继续生成')
      return
    }
    const promptPack = await runWithOperation('images', '正在构建 Prompt Pack', '正在把选定的创意方向转为图片生成提示词。', () => createPlanPromptPack(projectId.value, plan.id))
    if (!promptPack) return
    await submitGenerationTask(projectId.value, promptPack.id, generationCount.value)
    await store.refresh(projectId.value)
    selectStage('generation')
    ElMessage.success('本轮 Prompt Pack 已创建，素材任务已提交')
  } catch (error) { ElMessage.error(errorMessage(error)) } finally { submittingTask.value = false }
}

async function stopQuality() {
  if (!hasProject.value || !latestQualityRun.value) return
  stoppingQuality.value = true
  try {
    await stopQualityRun(projectId.value, latestQualityRun.value.id)
    await store.refresh(projectId.value)
    ElMessage.success('已请求停止 AI 审核；当前模型调用完成后将不再进入下一轮')
  } catch (error) { ElMessage.error(errorMessage(error)) } finally { stoppingQuality.value = false }
}

async function decideQuality(action: 'accept_recommended' | 'continue') {
  if (!hasProject.value || !latestQualityRun.value) return
  decidingQuality.value = true
  try {
    await decideQualityRun(projectId.value, latestQualityRun.value.id, action)
    await store.refresh(projectId.value)
    ElMessage.success(action === 'continue' ? '已继续下一轮 AI 审核' : '已接受推荐候选；仍可手动选择交付图')
  } catch (error) { ElMessage.error(errorMessage(error)) } finally { decidingQuality.value = false }
}

async function retryQuality() {
  if (!hasProject.value || !latestQualityRun.value) return
  retryingQuality.value = true
  try {
    await retryQualityRun(projectId.value, latestQualityRun.value.id)
    await store.refresh(projectId.value)
    ElMessage.success('已重新启动 AI 审核；不会重复使用失败的外部调用。')
  } catch (error) { ElMessage.error(errorMessage(error)) } finally { retryingQuality.value = false }
}

function openIteration(image: GeneratedImage) {
  iterationImage.value = image
  iterationInstruction.value = ''
  iterationOpen.value = true
}

async function submitIteration() {
  if (!hasProject.value || !iterationImage.value || !iterationInstruction.value.trim()) return
  if (activeTask.value) return ElMessage.warning('当前商品已有出图任务在运行，请等待完成后再发起下一轮。')
  submittingIteration.value = true
  try {
    const promptPack = await runWithOperation('images', '正在构建修改 Prompt Pack', '正在将你的修改要求与当前图片参考组合为新提示词。', () => createImagePromptPack(projectId.value, iterationImage.value!.id, iterationInstruction.value.trim()))
    if (!promptPack) return
    await submitGenerationTask(projectId.value, promptPack.id, generationCount.value)
    await store.refresh(projectId.value)
    iterationOpen.value = false
    ElMessage.success('已提交基于此图的修改任务')
  } catch (error) { ElMessage.error(errorMessage(error)) } finally { submittingIteration.value = false }
}

async function selectDeliveryImage(image: GeneratedImage) {
  if (!hasProject.value) return
  try {
    await selectGeneratedImage(projectId.value, image.id)
    await store.refresh(projectId.value)
    selectedImageId.value = image.id
    ElMessage.success('已设为交付图')
  } catch (error) { ElMessage.error(errorMessage(error)) }
}

function openComparison(imageId?: number | null) { if (imageId) selectedImageId.value = imageId; comparisonOpen.value = true }
function promptForTask(task: GenerationTask): PromptPack | undefined { return store.current?.prompt_packs.find((pack) => pack.id === task.prompt_pack_id) }
function taskProgress(task: GenerationTask) { return task.requested_count ? Math.min(100, Math.round((task.generated_count / task.requested_count) * 100)) : 0 }
function taskStatusLabel(status: string) { return ({ queued: '排队中', running: '生成中', success: '已完成', failed: '失败' } as Record<string, string>)[status] || status }
function taskTagType(status: string) { return ({ queued: 'warning', running: 'primary', success: 'success', failed: 'danger' } as Record<string, 'warning' | 'primary' | 'success' | 'danger'>)[status] || 'info' }
function taskStatusText(task: GenerationTask) {
  if (task.status === 'failed') return task.error_message || '任务失败，可重新发起本方向。'
  if (task.status === 'queued') return `已提交 ${task.requested_count} 张，正在排队。`
  if (task.status === 'running') return `已生成 ${task.generated_count}/${task.requested_count} 张，正在处理。`
  return `本轮已完成 ${task.generated_count} 张素材。`
}
function qualityRunCanStop(status: string) { return ['preparing', 'generating', 'reviewing', 'refining', 'stop_requested'].includes(status) }
function qualityRunTitle(status: string) {
  return ({ preparing: '正在准备审核 Prompt', generating: '正在生成审核候选', reviewing: '正在多模态审图', refining: '正在修订下一轮 Prompt', awaiting_human: '等待你的质量决策', stop_requested: '正在停止 AI 审核', completed: 'AI 审核已完成', cancelled: 'AI 审核已停止', failed: 'AI 审核失败' } as Record<string, string>)[status] || status
}
function qualityRunMessage(run: QualityRun) {
  if (run.status === 'awaiting_human') return '最佳候选处于临界分数或已达到最大轮数，请决定是否接受或继续。'
  if (run.status === 'completed') return '系统仅推荐候选图；是否设为交付图仍由你决定。'
  if (run.status === 'stop_requested') return '已阻止下一轮调用，正在等待当前模型调用完成。'
  if (run.status === 'cancelled') return '所有已生成图片和评分已保留，未再产生下一轮调用。'
  if (run.status === 'failed') return run.error_message || '外部调用失败，系统没有自动重复调用以避免成本失控。'
  return `当前为“${qualityTierLabel(run.acceptance_tier)}”档位，系统最多会生成 ${run.total_image_budget} 张图片。`
}
function qualityTierLabel(tier: QualityAcceptanceTier) { return ({ loose: '宽松', standard: '标准', strict: '严格' } as Record<QualityAcceptanceTier, string>)[tier] }
function qualityRunTagType(status: string): 'warning' | 'primary' | 'success' | 'danger' | 'info' {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'awaiting_human' || status === 'stop_requested') return 'warning'
  if (status === 'cancelled') return 'info'
  return 'primary'
}
function dimensionLabel(dimension: string) {
  return ({ product_consistency: '商品还原度', product_clarity: '主体清晰度', commercial_value: '商品性', text_accuracy: '文字正确性', style_match: '风格匹配', platform_fit: '平台适配' } as Record<string, string>)[dimension] || dimension
}

async function generateCopy() {
  if (!hasProject.value || !selectedImage.value) return
  creatingCopy.value = true
  try {
    await runWithOperation('copy', '正在生成发布文案', '正在根据交付图与创意方向生成多平台文案。', () => createCopywriting(projectId.value, selectedImage.value!.id))
    await store.refresh(projectId.value)
    ElMessage.success('已生成当前文案稿')
  } catch (error) { ElMessage.error(errorMessage(error)) } finally { creatingCopy.value = false }
}

function syncCopyEditor() {
  copyEditorReady.value = false
  clearCopySave()
  const copy = activeCopy.value?.copywriting
  if (!copy) {
    Object.assign(copyEditor, { title: '', selling_points: [], xiaohongshu_title: '', xiaohongshu_text: '', moments_text: '', taobao_text: '', xianyu_text: '', tags: [] })
    copySaveState.value = 'idle'
    return
  }
  Object.assign(copyEditor, { ...copy, selling_points: [...copy.selling_points], tags: [...copy.tags] })
  copySaveState.value = 'idle'
  nextTick(() => { copyEditorReady.value = true })
}

function scheduleCopySave() {
  if (!copyEditorReady.value || !activeCopy.value || !hasProject.value) return
  clearCopySave()
  copySaveState.value = 'pending'
  copySaveTimer = window.setTimeout(saveCurrentCopy, 800)
}

function clearCopySave() {
  if (copySaveTimer) window.clearTimeout(copySaveTimer)
  copySaveTimer = null
}

async function saveCurrentCopy() {
  clearCopySave()
  if (!hasProject.value || !activeCopy.value) return
  copySaveState.value = 'saving'
  try {
    await updateCopywriting(projectId.value, activeCopy.value.id, { ...copyEditor, selling_points: [...copyEditor.selling_points], tags: [...copyEditor.tags] })
    copySaveState.value = 'saved'
  } catch (error) {
    copySaveState.value = 'failed'
    ElMessage.error(`文案未保存：${errorMessage(error)}`)
  }
}

async function rewriteCopy() {
  if (!hasProject.value || !activeCopy.value || !copyRewriteInstruction.value.trim()) return
  rewritingCopy.value = true
  clearCopySave()
  copyEditorReady.value = false
  try {
    await runWithOperation('copy', '正在改写发布文案', '正在按你的说明更新当前文案。', () => rewriteCopywriting(projectId.value, activeCopy.value!.id, copyRewriteInstruction.value.trim()))
    copyRewriteInstruction.value = ''
    await store.refresh(projectId.value)
    syncCopyEditor()
    ElMessage.success('AI 已更新当前稿')
  } catch (error) { ElMessage.error(errorMessage(error)) } finally { rewritingCopy.value = false }
}

async function copyText(value: string) {
  try { await navigator.clipboard.writeText(value); ElMessage.success('已复制') } catch { ElMessage.warning('复制失败，请手动选择文字复制') }
}

function joinValues(values?: string[]) { return values?.filter(Boolean).join('；') || '未识别' }

function handleStatusPrimary() {
  if (activeQualityRun.value?.status === 'awaiting_human') { selectStage('generation'); return }
  if (!sourceConfirmed.value) { selectStage('brief'); return }
  if (!visualAnalysis.value) { selectStage('analysis'); runVisual(); return }
  if (!visualAnalysis.value.analysis.human_reviewed) { selectStage('analysis'); return }
  if (!strategy.value) { selectStage('analysis'); runStrategy(); return }
  if (!strategyConfirmed.value) { selectStage('analysis'); return }
  if (!currentPlans.value.length) { selectStage('plans'); return }
  if (!allImages.value.length || !selectedImage.value) { selectStage('generation'); return }
  selectStage('delivery')
}

function selectWorkflowStep(stepKey: string) {
  const stageByStep: Record<string, StudioStageKey> = {
    source: 'brief',
    visual_analysis: 'analysis',
    analysis: 'analysis',
    plans: 'plans',
    images: 'generation',
    review: 'generation',
    quality_run: 'generation',
    copy: 'delivery'
  }
  selectStage(stageByStep[stepKey] || 'brief')
}
</script>

<style scoped>
.studio-page { max-width: 1480px; }
.studio-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 22px; }
.focused-workspace { margin-top: 22px; }
.stage-workspace { min-width: 0; }
.stage-section { padding: clamp(20px, 3vw, 38px); border: 1px solid var(--ps-border); border-radius: var(--ps-radius-lg); background: var(--ps-surface); box-shadow: var(--ps-shadow); }
.stage-heading { margin-bottom: 24px; }
.stage-heading h2 { margin: 5px 0 7px; color: var(--ps-heading); font-size: clamp(22px, 3vw, 31px); line-height: 1.17; }
.stage-heading p, .empty-work-card p, .correction-card p, .planner-condition-footer p { margin: 0; color: var(--ps-muted-strong); line-height: 1.65; }
.stage-kicker, .attention-label { color: var(--ps-accent); font-size: 12px; font-weight: 780; letter-spacing: .08em; text-transform: uppercase; }
.source-workspace { display: grid; grid-template-columns: minmax(0, 1fr) minmax(320px, .84fr); gap: 30px; padding: 22px; border: 1px solid var(--ps-border); border-radius: var(--ps-radius); background: var(--ps-surface-muted); }
.source-workspace.locked { border-color: color-mix(in srgb, var(--ps-primary) 30%, var(--ps-border)); }
.source-lock-note { margin: 12px 0 0; color: var(--ps-muted); font-size: 12px; line-height: 1.55; }
.brief-form :deep(.el-form-item) { margin-bottom: 18px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.source-panel { min-width: 0; }
.source-panel-head, .summary-card-head, .copy-card-head, .material-group-head, .plan-card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.source-panel-head > div { display: grid; gap: 4px; font-weight: 760; color: var(--ps-heading); }
.source-panel-head small { color: var(--ps-muted); font-weight: 500; }
.source-frame { display: grid; min-height: 290px; margin-top: 13px; overflow: hidden; place-items: center; border: 1px solid var(--ps-border); border-radius: 14px; background: #f4f2ec; }
.source-frame img { display: block; width: 100%; height: 350px; object-fit: contain; background: #f4f2ec; }
.upload-placeholder { max-width: 290px; padding: 36px 24px; text-align: center; }
.upload-placeholder span { color: var(--ps-primary); font-size: 11px; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; }
.upload-placeholder strong { display: block; margin: 10px 0; color: var(--ps-heading); font-size: 19px; }
.upload-placeholder p { color: var(--ps-muted); font-size: 13px; line-height: 1.55; }
.source-upload { width: 100%; margin-top: 12px; }
.source-upload :deep(.el-upload), .source-upload :deep(.el-upload-dragger) { width: 100%; }
.source-upload :deep(.el-upload-dragger) { display: grid; gap: 4px; min-height: 80px; padding: 17px; border-color: var(--ps-border-strong); background: transparent; color: var(--ps-primary); font-weight: 720; }
.source-upload small { color: var(--ps-muted); font-weight: 500; }
.reupload-button { margin-top: 5px; }
.stage-action-bar { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-top: 26px; padding-top: 21px; border-top: 1px solid var(--ps-border); }
.stage-action-bar p { margin: 0; color: var(--ps-muted-strong); line-height: 1.55; }
.source-actions { display: flex; align-items: center; gap: 10px; }
.orange-button { --el-button-bg-color: var(--ps-accent); --el-button-border-color: var(--ps-accent); --el-button-hover-bg-color: #b74a33; --el-button-hover-border-color: #b74a33; }
.empty-work-card { display: grid; justify-items: start; gap: 12px; max-width: 720px; padding: 30px; border: 1px dashed var(--ps-border-strong); border-radius: var(--ps-radius); background: var(--ps-surface-muted); }
.empty-work-card.compact { max-width: none; }
.empty-work-card strong { color: var(--ps-heading); font-size: 19px; }
.confirmation-layout { display: grid; gap: 18px; }
.summary-card, .correction-card, .planner-conditions, .material-group, .copy-card, .delivery-image-card { padding: 23px; border: 1px solid var(--ps-border); border-radius: var(--ps-radius); background: var(--ps-surface-muted); }
.summary-card h3, .correction-card h3, .copy-card h3, .material-group h3, .plan-card h3 { margin: 5px 0 0; color: var(--ps-heading); font-size: 20px; line-height: 1.3; }
.summary-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px 22px; margin: 22px 0 0; }
.summary-grid div, .detail-list div, .plan-facts div { min-width: 0; }
.summary-grid dt, .detail-list dt, .plan-facts dt { margin-bottom: 5px; color: var(--ps-muted); font-size: 12px; font-weight: 700; }
.summary-grid dd, .detail-list dd, .plan-facts dd { margin: 0; color: var(--ps-heading); line-height: 1.62; white-space: pre-wrap; overflow-wrap: anywhere; }
.detail-collapse, .prompt-collapse, .history-collapse { margin-top: 17px; }
.detail-trigger { margin-top: 14px; padding-left: 0; }
.detail-list { display: grid; gap: 15px; margin: 0; }
.correction-card { background: color-mix(in srgb, var(--ps-accent) 5%, var(--ps-surface)); }
.inline-actions, .copy-rewrite, .plan-revision, .material-card-actions, .generation-start-actions { display: flex; gap: 9px; align-items: center; }
.inline-actions { justify-content: flex-end; margin-top: 14px; }
.strategy-section { margin-top: 18px; }
.strategy-correction { display: grid; gap: 10px; margin-top: 20px; padding-top: 18px; border-top: 1px solid var(--ps-border); }
.strategy-correction p { margin: 0; color: var(--ps-muted-strong); font-size: 13px; line-height: 1.6; }
.planner-conditions { display: grid; gap: 18px; }
.condition-label { display: block; margin-bottom: 9px; color: var(--ps-heading); font-size: 13px; font-weight: 750; }
.choice-group { display: flex; flex-wrap: wrap; gap: 7px; }
.choice-group :deep(.el-checkbox-button) { margin: 0; }
.choice-group :deep(.el-checkbox-button__inner) { border-left: 1px solid var(--el-border-color) !important; border-radius: 999px !important; }
.planner-condition-footer { display: flex; justify-content: space-between; align-items: center; gap: 15px; }
.plan-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-top: 22px; }
.plan-card { display: flex; flex-direction: column; min-width: 0; padding: 20px; border: 1px solid var(--ps-border); border-radius: var(--ps-radius); background: var(--ps-surface); cursor: pointer; transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease; }
.plan-card:hover, .plan-card:focus-visible { border-color: color-mix(in srgb, var(--ps-primary) 52%, var(--ps-border)); box-shadow: 0 8px 20px rgba(35, 38, 32, 0.08); outline: none; transform: translateY(-1px); }
.plan-card.selected { border-color: var(--ps-primary); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ps-primary) 13%, transparent); }
.plan-index { color: var(--ps-muted); font-size: 12px; font-weight: 700; }
.plan-tags { display: flex; flex-wrap: wrap; gap: 6px; margin: 15px 0; }
.plan-tags span { padding: 4px 8px; border-radius: 999px; color: var(--ps-primary); background: var(--ps-primary-soft); font-size: 12px; }
.plan-description { margin: 0; color: var(--ps-muted-strong); line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
.plan-details { margin-top: 15px; }
.plan-details :deep(.el-collapse-item__header) { color: var(--ps-primary); font-size: 12px; font-weight: 760; }
.plan-facts { display: grid; gap: 12px; margin: 0; padding: 4px 0 8px; }
.plan-card-status { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; }
.plan-revision { margin-top: 15px; }
.selection-bar { align-items: center; }
.generation-start-actions .el-select { width: 92px; }
.quality-mode-card, .quality-run-card { margin-top: 18px; padding: 20px; border: 1px solid color-mix(in srgb, var(--ps-primary) 25%, var(--ps-border)); border-radius: var(--ps-radius); background: color-mix(in srgb, var(--ps-primary-soft) 52%, var(--ps-surface)); }
.quality-mode-head, .quality-run-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.quality-mode-head h3, .quality-run-head h3 { margin: 5px 0; color: var(--ps-heading); font-size: 18px; }
.quality-mode-head p, .quality-run-head p { margin: 0; color: var(--ps-muted-strong); font-size: 13px; line-height: 1.55; }
.quality-mode-controls { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 18px; }
.quality-mode-controls label { display: grid; gap: 7px; color: var(--ps-muted-strong); font-size: 12px; font-weight: 720; }
.quality-mode-controls .el-select, .quality-mode-controls .el-input-number { width: 100%; }
.quality-tier-options { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 5px; }.quality-tier-options button { min-height: 32px; border: 1px solid var(--ps-border-strong); border-radius: 8px; color: var(--ps-muted-strong); background: var(--ps-surface); font: inherit; cursor: pointer; transition: border-color 150ms ease, background 150ms ease, color 150ms ease; }.quality-tier-options button:hover { border-color: var(--ps-primary); color: var(--ps-primary); }.quality-tier-options button.selected { border-color: var(--ps-primary); color: #fff; background: var(--ps-primary); }.quality-field-help { color: var(--ps-muted); font-size: 11px; font-weight: 500; line-height: 1.4; }
.quality-budget, .quality-weight-note { grid-column: 1 / -1; margin: 0; padding-top: 4px; font-size: 12px; line-height: 1.55; }
.quality-budget { color: var(--ps-primary); }
.quality-weight-note { color: var(--ps-muted-strong); }
.quality-run-card { display: grid; gap: 13px; margin-bottom: 18px; }
.quality-run-card.quality-awaiting_human { border-color: color-mix(in srgb, var(--ps-accent) 55%, var(--ps-border)); background: color-mix(in srgb, var(--ps-accent-soft) 58%, var(--ps-surface)); }
.quality-run-card.quality-failed { border-color: color-mix(in srgb, var(--ps-danger) 55%, var(--ps-border)); }
.quality-run-facts, .quality-decision-actions, .quality-run-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 9px; }
.quality-run-facts span { padding: 5px 8px; border-radius: 999px; color: var(--ps-primary); background: var(--ps-surface); font-size: 12px; font-weight: 700; }
.quality-decision-actions > span, .quality-run-actions > span { color: var(--ps-muted-strong); font-size: 12px; line-height: 1.45; }
.history-batch { display: grid; gap: 3px; padding: 9px 0; border-bottom: 1px solid var(--ps-border); color: var(--ps-muted-strong); font-size: 13px; }
.material-groups { display: grid; gap: 18px; }
.material-reference { position: sticky; top: 142px; z-index: 8; display: grid; grid-template-columns: 72px minmax(0, 1fr) auto; gap: 13px; align-items: center; margin-bottom: 18px; padding: 12px; border: 1px solid color-mix(in srgb, var(--ps-primary) 18%, var(--ps-border)); border-radius: var(--ps-radius); background: color-mix(in srgb, var(--ps-surface) 94%, transparent); box-shadow: 0 8px 22px rgba(35, 38, 32, 0.08); backdrop-filter: blur(14px); }
.material-reference img { width: 72px; height: 72px; border-radius: 9px; object-fit: contain; background: #f3f1eb; }
.material-reference strong, .material-reference p { display: block; }
.material-reference strong { margin-top: 3px; color: var(--ps-heading); font-size: 14px; }
.material-reference p { margin: 4px 0 0; color: var(--ps-muted); font-size: 12px; line-height: 1.45; }
.material-group { display: grid; gap: 16px; }
.material-group-head span, .material-group-head p { color: var(--ps-muted); font-size: 13px; }
.material-group-head p { margin: 6px 0 0; }
.image-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(205px, 1fr)); gap: 14px; }
.material-card { overflow: hidden; border: 1px solid var(--ps-border); border-radius: 12px; background: var(--ps-surface); }
.material-card.delivery { border-color: var(--ps-primary); box-shadow: 0 0 0 2px var(--ps-primary-soft); }
.material-card.focused { border-color: var(--ps-accent); box-shadow: 0 0 0 2px var(--ps-accent-soft); }
.material-image-button { display: block; width: 100%; padding: 0; border: 0; background: transparent; cursor: zoom-in; }
.material-image-button img { display: block; width: 100%; aspect-ratio: 1 / 1; object-fit: cover; background: #f3f1eb; }
.material-card-meta { display: flex; justify-content: space-between; gap: 6px; padding: 9px 11px 0; color: var(--ps-muted); font-size: 12px; }
.delivery-label { color: var(--ps-primary); font-weight: 800; }
.recommended-label, .image-score { color: var(--ps-accent-dark); font-weight: 800; }
.image-score { margin-left: auto; }
.review-collapse { margin: 9px 10px 0; }
.review-collapse :deep(.el-collapse-item__header) { height: 31px; color: var(--ps-primary); font-size: 12px; font-weight: 700; }
.review-result-title { margin: 0 0 8px; color: var(--ps-heading); font-size: 12px; font-weight: 780; }.review-score-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; color: var(--ps-muted-strong); font-size: 12px; }
.review-summary, .review-risk { margin: 9px 0 0; color: var(--ps-muted-strong); font-size: 12px; line-height: 1.5; }
.review-risk { color: var(--ps-danger); }
.review-evidence { display: grid; gap: 5px; margin: 9px 0 0; padding-left: 17px; color: var(--ps-muted-strong); font-size: 12px; line-height: 1.45; }
.material-card-actions { justify-content: space-between; padding: 10px; }
.delivery-button { min-width: 0; flex: 1; }
.more-actions { display: grid; justify-items: start; }
.delivery-layout { display: grid; grid-template-columns: minmax(260px, .72fr) minmax(0, 1.28fr); gap: 20px; }
.delivery-image-card { display: grid; align-content: start; gap: 11px; }
.delivery-image-card img { width: 100%; max-height: 560px; object-fit: contain; border-radius: 10px; background: #f3f1eb; }
.delivery-image-card a { display: block; }
.delivery-image-card a .el-button { width: 100%; }
.copy-card { min-width: 0; }
.copy-save-state { color: var(--ps-muted); font-size: 12px; }
.copy-save-state.saved { color: var(--ps-primary); }.copy-save-state.failed { color: var(--ps-danger); }.copy-save-state.saving { color: var(--ps-accent); }
.copy-card > .el-input { margin-top: 18px; }
.copy-tabs :deep(.el-textarea), .copy-tabs :deep(.el-input) { margin-bottom: 10px; }
.copy-rewrite { margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--ps-border); }
.copy-rewrite .el-input { flex: 1; }
.drawer-detail-section { display: grid; gap: 14px; margin-bottom: 28px; }
.iteration-dialog { display: grid; grid-template-columns: minmax(180px, .7fr) minmax(0, 1.3fr); gap: 18px; }
.iteration-dialog > img { width: 100%; aspect-ratio: 1 / 1; border-radius: 12px; object-fit: contain; background: #f3f1eb; }
.iteration-dialog p { margin: 0 0 12px; color: var(--ps-muted-strong); line-height: 1.6; }
.iteration-actions { display: flex; gap: 10px; margin-top: 12px; }
.iteration-actions .el-select { width: 92px; }
@media (max-width: 1040px) { .plan-grid { grid-template-columns: 1fr 1fr; } }
@media (max-width: 720px) { .studio-header, .stage-action-bar, .planner-condition-footer, .delivery-layout { grid-template-columns: 1fr; display: grid; }.source-workspace, .form-grid, .summary-grid, .plan-grid, .iteration-dialog, .quality-mode-controls { grid-template-columns: 1fr; }.stage-section { padding: 18px; }.source-workspace { padding: 15px; }.stage-action-bar { align-items: stretch; }.stage-action-bar .el-button { width: 100%; }.selection-bar { align-items: stretch; }.generation-start-actions { width: 100%; }.generation-start-actions .el-select { flex: 1; }.generation-start-actions .el-button { flex: 2; }.plan-revision, .copy-rewrite, .iteration-actions { align-items: stretch; flex-direction: column; }.inline-actions { align-items: stretch; flex-direction: column-reverse; }.inline-actions .el-button { width: 100%; }.material-reference { position: static; grid-template-columns: 56px minmax(0, 1fr); }.material-reference img { width: 56px; height: 56px; }.material-reference .el-button { grid-column: 1 / -1; }.quality-mode-head, .quality-run-head { align-items: stretch; flex-direction: column; } }
</style>
