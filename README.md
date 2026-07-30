# ProductShot Agent

面向轻量商家的 AI 商品营销素材生产工作台。它把“普通商品原图”转化为可发布素材：确认商品与原图、原图理解、商品策略、创意方案、图片生成、人工选图，以及多平台文案都在同一个项目上下文中完成。

> 项目定位：不是单点图片生成器，而是围绕“小商家商品内容生产”的多 Agent 工作流系统。

![ProductShot 首页](docs/assets/productshot-home.png)

## 1. 项目简介

ProductShot 的核心价值是把原本分散的 AI 出图、提示词编写、人工选图和平台文案生成，收敛成一条可运行的商品素材生产线。

- 面向对象：淘宝、朋友圈、小红书、闲鱼等轻量商家和个体卖家。
- 输入材料：一张商品原图 + 少量商品信息。
- 输出结果：营销图、用户选定的交付图、各平台当前文案，以及可直接下载/复制的交付内容。
- 工程重点：多 Agent 编排、Provider 工具抽象、项目级 Memory、流程可观测性。
- 可选 AI 审核模式：通过多模态质量评估、受限自动重试和人工决策，降低“抽奖式”生图的返工成本。

## 2. 项目背景

轻量商家的真实痛点不是“有没有 AI 出图工具”，而是“从一张随手拍商品图到可发布素材”的整条链路没有被打通。

| 真实问题 | ProductShot 的解决方式 |
| --- | --- |
| 原图背景杂乱、主体不突出 | 先做原图视觉理解，提取商品外观、材质、背景问题和保真约束 |
| 不会选择视觉方向 | 先生成 3 个创意方向，让用户比较后再生成图片 |
| 不会写提示词 | Prompt Agent 根据选中方向生成 Prompt Pack 和负向约束 |
| 不知道该选哪张生成图 | 在原图对比和交付选择中由用户自主挑选，保留人工判断 |
| 图片和文案割裂 | Copywriting Agent 基于商品策略、创意方向和选定交付图生成多平台文案 |
| 模型调用慢、失败难定位 | workflow_events 记录每个 Agent / Provider 的状态、耗时、摘要和详情 |

## 3. 项目演示

### 3.1 整体生产流程

**功能**：工作室正文按“商品与原图、分析与确认、创意方向、素材生成、交付与迭代”5 个用户阶段聚焦展示；顶部状态中心按项目独立追踪来源确认、原图理解、商品策略、方向规划、Prompt Pack、素材生成和发布文案。

**效果**：页面一次只展开当前任务，已完成阶段可随时回看；等待用户、运行中和失败状态不会再被长页面内容遮住。

![工作流概览](docs/assets/workflow-overview.png)

### 3.2 首页与项目入口

**功能**：首页提供新建项目、最近项目和项目历史入口，用户可以快速回到已有商品素材生产任务。

![ProductShot 首页](docs/assets/productshot-home.png)

### 3.3 商品简报与原图上下文

**功能**：商品简报仅收集名称、类别、目标人群和核心卖点，并与原图放在同一工作区；确认前可修改或重新上传，确认后锁定为后续阶段的保真参考。

**效果**：用户可以随时回到第一阶段核对输入信息，但原图不会跟随页面滚动占用后续工作空间。

![商品简报与原图上下文](docs/assets/studio-brief.png)

### 3.4 原图理解与商品策略

**功能**：VisualAnalysisAgent 读取原图，提取外观、材质、背景问题和保真约束；用户通过自然语言纠正并确认后，ProductAnalysisAgent 再生成商品策略。

**效果**：后续 Prompt 和文案都能复用同一份商品上下文，避免图片好看但商品主体失真。

![原图分析与商品策略](docs/assets/studio-analysis.png)

### 3.5 创意方向规划

**功能**：CreativePlannerAgent 生成 3 个可选营销方向，每个方向包含画面描述、主打卖点、推荐理由、文案方向和预期产出。

**效果**：用户先在独立阶段比较方向，再决定生成哪一路素材；方案关键差异默认可见，详细构想按需展开，降低盲目出图成本和阅读负担。

![创意方向选择](docs/assets/studio-plans.png)

### 3.6 素材生成与人工选图

**功能**：PromptEngineerAgent 为选中方向构建 Prompt Pack；ImageProvider 生成图片；用户自行比较原图和生成图并选定交付图。

**效果**：生成图以更大的素材卡片展示，用户可以直接选择、基于此图修改或进入原图对比。

![素材生成与选图](docs/assets/studio-generation.png)

### 3.7 文案交付与自然语言修改

**功能**：CopywritingAgent 围绕选中图片生成小红书、朋友圈、淘宝和闲鱼文案；每张交付图只维护一份自动保存的当前稿，交付阶段仅提供图片下载与文案复制。

**效果**：图片、人工选图、平台文案、标签和后续修改集中在一个交付上下文中，形成可发布素材包。

![生成素材与文案](docs/assets/studio-output-copy.png)

**按需对比**：原图不再常驻右侧，只有用户需要检查商品保真时才打开并排对比抽屉。

![原图与生成图对比](docs/assets/studio-comparison.png)

**原图到营销图**：生成图保留白色毛绒主体、黑黄眼睛和红黄围巾等关键特征，同时去掉杂乱背景，形成更干净的商品展示画面（这是其中一种创意方向）。

<table>
  <tr>
    <th>原始商品图</th>
    <th>生成效果图</th>
  </tr>
  <tr>
    <td><img src="docs/assets/sample-original.jpeg" alt="猫头鹰玩偶原图" width="360"></td>
    <td><img src="docs/assets/sample-generated.png" alt="ProductShot 生成图" width="360"></td>
  </tr>
</table>

### 3.8 运行状态与流程诊断

**功能**：顶部状态中心始终显示当前节点、等待或失败状态、最新消息和运行时长。每个 Agent / Provider 节点的状态、耗时、摘要和结构化详情集中在“运行记录”抽屉中。

**效果**：模型调用慢、图片生成排队、文案异常等问题无需滚到页面底部即可定位；失败记录保留重试入口，历史启动记录不会被误认为仍在运行。

### 3.9 模型管理

**功能**：前端允许调整文字推理 Provider、图片生成 Provider、模型名和 Base URL 等非敏感配置；API Key 始终从后端系统环境变量读取。

**效果**：可独立配置 OpenAI 与百炼 Provider，同时避免把 secret 暴露给浏览器或提交到仓库。

![模型管理](docs/assets/model-settings.png)

## 4. 核心功能

1. 来源确认：填写商品事实并上传原图，确认后锁定。
2. 原图理解：识别商品外观、主色、材质、可见文字、背景问题和保真约束，并支持自然语言纠正。
3. 商品策略：仅在用户确认原图理解后提炼人群、卖点和视觉机会。
4. 创意规划：按可选的小红书、朋友圈、淘宝、闲鱼平台与主流风格生成 3 个方向；不选条件时生成差异化组合。
5. Prompt Pack：用户选定方向并点击生成图片时才创建正向提示词、负向约束、尺寸和一致性要求。
6. 图片生成与人工选图：按方向和轮次汇总图片，通过 DashScope / OpenAI Provider 出图并由用户选定交付图。
7. 文案交付：每张交付图生成小红书、朋友圈、淘宝、闲鱼当前稿，自动保存，可下载图片和复制文案。
8. AI 审核生图（可选）：用户选择还原优先、平衡或商品性优先，并设置通过分、每轮张数和最大轮数；低分结果在预算内自动修订 Prompt，临界结果和上限结果交给用户决策。

## 5. 技术架构

```mermaid
flowchart LR
    User["用户 / 商品原图"] --> Frontend["Vue 3 Studio 工作台"]
    Frontend --> API["FastAPI API 层"]
    API --> Workflow["ProductShotWorkflow 服务编排"]
    Workflow --> Agents["多 Agent 节点"]
    Workflow --> Providers["Text / Image Provider 工具层"]
    Workflow --> DB["SQLite 项目记忆"]
    Workflow --> Files["uploads 文件存储"]

    Agents --> Visual["VisualAnalysisAgent"]
    Agents --> Strategy["ProductAnalysisAgent"]
    Agents --> Planner["CreativePlannerAgent"]
    Agents --> Prompt["PromptEngineerAgent"]
    Agents --> Copy["CopywritingAgent"]
    Agents --> Copy["CopywritingAgent"]

    Providers --> DashScope["DashScope Provider"]
    Providers --> OpenAI["OpenAI Provider"]
```

| 模块 | 技术与职责 |
| --- | --- |
| 前端 | Vue 3, TypeScript, Vite, Pinia, Vue Router, Element Plus；承载连续式 Studio 工作台 |
| 后端 | FastAPI, SQLAlchemy, SQLite, Pydantic；负责 API、校验、持久化和任务状态 |
| Workflow | `ProductShotWorkflow` 编排 Agent、Provider、状态流转和 workflow_events |
| Agent 层 | 视觉理解、商品策略、创意规划、Prompt、文案和修改意图 |
| Tool / Provider 层 | `TextProvider` 与 `ImageProvider` 抽象，隔离 DashScope 和 OpenAI |
| Memory | SQLite 保存项目、原图、分析结果、方案、生成图、交付选择、文案和流程事件 |

## 6. Agent 工作流设计

```text
创建项目
  -> 上传并确认商品原图与商品事实（此后锁定）
  -> VisualAnalysisAgent：提取商品外观、背景问题和保真约束
  -> 用户自然语言纠正并确认原图理解
  -> ProductAnalysisAgent：生成商品策略、卖点、人群和视觉机会
  -> 用户确认策略（确认前支持自然语言纠正）
  -> 用户选择可选平台/风格后，CreativePlannerAgent 生成 3 个创意方向
  -> 用户选择方向
  -> PromptEngineerAgent：构建 Prompt Pack
  -> ImageProvider：生成营销图片
  -> 用户在原图对比后选择交付图
  -> CopywritingAgent：生成并更新多平台当前文案
  -> 下载交付图 / 复制文案
```

Agent 设计原则：

1. **职责单一**：每个 Agent 只处理一个明确节点，输出结构化 Pydantic Schema。
2. **人机协同**：先生成多个方向，关键决策由用户选择，而不是全自动黑盒出图。
3. **保真优先**：视觉分析阶段提取商品一致性规则，后续 Prompt 和图片修改都复用这些约束。
4. **真实调用可见**：模型未配置或调用失败时，流程记录错误并停止，不会伪造本地结果。

## 7. Tool Use 设计

本项目没有把外部能力散落在 Agent 代码里，而是通过 Provider 抽象把“工具调用”收敛成可替换接口：

| Tool / Provider | 输入 | 输出 | 设计目的 |
| --- | --- | --- | --- |
| `TextProvider.generate_json` | system prompt、user prompt、schema name | 结构化 JSON | 统一文字推理、策略和文案输出 |
| `generate_multimodal_json` | prompt + 图片路径 | 结构化视觉理解 | 支持原图理解 |
| `ImageProvider.generate_images` | source image、positive prompt、negative prompt、size、count | 本地图片文件与 URL | 隔离 DashScope、OpenAI 等图片生成实现 |
| `WorkflowEvent` 记录 | step、agent、status、detail、latency | 可视化流程诊断 | 让工具调用过程可追踪、可排错 |

关键处理：

1. 图片 Provider 声明 `capabilities`，当 Prompt 要求图生图但 Provider 不支持时，后端会明确报错。
2. DashScope 图片生成按模型能力选择调用方式：Qwen-Image 使用同步多模态端点，Wan 等模型使用异步任务创建与轮询；生成结果都会立即下载落盘。
3. API Key 只从后端环境变量读取，前端模型管理页不保存 secret。

## 8. Memory 设计

本项目的 Memory 不是向量数据库或长期用户画像，而是面向生产工作流的项目级记忆：

| Memory 类型 | 存储内容 | 作用 |
| --- | --- | --- |
| Project Memory | 已确认的商品信息、原图和人群 | 保证后续 Agent 使用同一份锁定上下文 |
| Visual Memory | 原图理解、材质、背景问题、保真约束、人工审核意见 | 让 Prompt 和修改持续遵守商品一致性 |
| Creative Memory | 3 个创意方向及用户选中的方向 | 避免生成和文案脱离用户选择 |
| Asset Memory | 原图、生成图、交付图、当前文案 | 支持回看、下载、复制和继续修改 |
| Trace Memory | workflow_events 中的节点状态、耗时、摘要和详情 | 支持问题排查与流程可观测性 |

这种设计的重点是“让多步 Agent 工作流有上下文和可追踪状态”，而不是为了技术展示强行引入 RAG。

## 9. 核心技术亮点

### 9.1 问题：单次图片生成无法覆盖真实营销链路

**方案**：将流程拆成“先分析与规划，再选择方向生成素材包”的两阶段工作流。

**效果**：用户能先比较创意方向，再决定是否生成图片；生成图、交付选择和当前文案都绑定到同一个项目上下文，形成完整业务闭环。

### 9.2 问题：LLM 输出容易散、难以进入工程流程

**方案**：所有运行中的 Agent 输出都落到 Pydantic Schema，例如 `VisualAnalysisPayload`、`ProductAnalysisPayload`、`PromptPackPayload` 和 `CopywritingPayload`。

**效果**：后端可以稳定持久化、复用和展示 Agent 输出，前端也能按固定字段渲染分析、标签和文案。

### 9.3 问题：图片生成模型调用慢、失败原因难定位

**方案**：将模型能力封装为 Provider，并持久化记录每个 Agent / Provider 节点的状态、耗时、摘要、错误和结构化详情。

**效果**：用户能在页面看到流程进度和 Agent Trace；开发时也能快速判断问题出在 Prompt、图片生成还是文案节点。

### 9.4 问题：AI 生成图可能改变商品主体

**方案**：在原图理解阶段提取商品保真约束，并在 Prompt Pack 和图片修改中持续使用这些约束。

**效果**：系统不仅追求“图片好看”，还会关注商品主体是否清晰、是否变形、是否保留关键颜色/标签/材质。

### 9.5 问题：真实模型接入与本地演示容易互相阻塞

**方案**：文字和图片均通过 OpenAI 或 DashScope 真实 Provider 调用，并由环境变量选择平台。

**效果**：没有 API Key、模型名或 Provider 配置时会得到明确错误，避免误把本地结果当作模型输出。

## 10. 项目难点与解决方案

| 难点 | 解决方案 | 可面试讲解点 |
| --- | --- | --- |
| 多 Agent 输出需要串成稳定业务流 | 服务层统一编排，Agent 输出全部结构化 | 为什么不让 LLM 直接生成整份结果，而是拆节点 |
| 商品保真比图片美观更重要 | 原图理解提取保真约束，Prompt 和修改复用 | 商品图生成与普通文生图的差异 |
| 真实模型慢且不稳定 | 前端进度、后端 timeout、workflow_events 共同处理 | LLM 应用的可观测性与降级设计 |
| 前端流程容易割裂 | 统一 `/studio` 工作台，旧路由重定向 | 如何把多步工作流设计成连续体验 |
| Key 与模型配置安全 | Key 只读后端环境变量，前端只调非敏感配置 | AI 应用中的 secret 边界 |

## 11. 快速开始

### 11.1 启动后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

后端默认运行在 `http://127.0.0.1:8000`，API 文档在 `http://127.0.0.1:8000/docs`。

### 11.2 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://127.0.0.1:5173`。

### 11.3 接入 DashScope

```bash
export TEXT_PROVIDER=dashscope
export IMAGE_PROVIDER=dashscope
export DASHSCOPE_TEXT_MODEL=your_text_model
export DASHSCOPE_VISION_MODEL=your_multimodal_model
export DASHSCOPE_IMAGE_MODEL=your_image_model
export DASHSCOPE_BASE_HTTP_API_URL=https://dashscope.aliyuncs.com/api/v1
export DASHSCOPE_API_KEY=your_api_key
```

注意：不要把真实 Key、个人专属 Base URL、Workspace ID、业务空间地址写入 `.env`、README、代码、测试或前端请求中。当前前端模型管理页只展示 Key 是否已在后端配置，并允许调整非敏感模型参数。

### 11.4 接入 OpenAI

```bash
export TEXT_PROVIDER=openai
export IMAGE_PROVIDER=openai
export OPENAI_TEXT_MODEL=your_text_model
export OPENAI_IMAGE_MODEL=your_image_model
export OPENAI_API_KEY=your_api_key
```

未配置 Provider、密钥或对应模型名时，执行工作流会返回可操作错误，不会回退到本地规则或占位结果。

## 12. 验证方式

后端测试：

```bash
cd backend
pytest -q
```

前端构建：

```bash
cd frontend
npm run build
```

建议的手动验证路径：

1. 打开 `/studio`，创建商品项目、上传图片并确认来源锁定。
2. 运行原图理解，检查商品外观、材质、背景问题和保真约束；必要时使用自然语言纠正。
3. 确认理解后生成商品策略，再显式生成 3 个创意方向。
4. 选择一个方向生成图片，并可继续选择其他方向发起新一轮生成。
5. 设定交付图，生成或修改当前文案，下载图片并复制需要的平台文案。

## 13. 项目结构

```text
.
├── backend/
│   ├── app/
│   │   ├── agents/        # 商品分析、创意、Prompt、文案、修改 Agent
│   │   ├── api/           # FastAPI 路由
│   │   ├── providers/     # Text / Image Provider 抽象与实现
│   │   ├── services/      # 工作流编排
│   │   ├── storage/       # 上传文件保存
│   │   └── models/        # SQLAlchemy 数据模型
│   └── tests/
├── frontend/
│   └── src/
│       ├── views/         # 首页、项目工作台、模型管理
│       ├── stores/        # 项目流程状态
│       └── api/           # 后端 API Client
└── docs/
    ├── PRD.md
    └── assets/
```

## 14. 当前边界

- 这是本地 MVP，不是生产级 SaaS。
- 真实图片生成质量取决于所接入模型、原图质量、提示词和平台限制。
- 图片主体一致性、版权风险、平台合规、账号体系和权限控制仍需要继续完善。
- 数据默认存储在本地 SQLite 和 uploads 目录，暂未实现云端存储。
- AI 审核模式需使用 PostgreSQL、Redis 和 Celery worker；普通一次生图仍可在本地 SQLite 下运行。

## 15. 后续规划

- 补强图片生成任务的失败重试、状态解释和版本对比。
- 增加生成结果收藏、重生成和 A/B 对比。
- 支持更多平台尺寸。
- 扩展工作流测试，覆盖 Agent 输出结构、Provider 降级和更多任务状态。
- 继续优化真实模型下的商品一致性评价与局部重绘能力。

## 16. 相关文档

- [产品需求文档](docs/PRD.md)
- [后端说明](backend/README.md)
- [前端说明](frontend/README.md)
