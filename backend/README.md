# ProductShot Agent Backend

FastAPI 后端，提供商品与原图确认、原图与策略的自然语言纠正、创意方向规划、按方向图片生成和当前文案 API。

## 安装

需要 Python 3.9 或更高版本。

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 启动

```bash
uvicorn app.main:app --reload
```

服务默认运行在 `http://127.0.0.1:8000`。

### 使用远端中间件的一键本地开发

本机已通过 SSH 隧道准备好 PostgreSQL、Redis 凭据时，可将私有配置放入仓库根目录的 `.env.local`（该文件被 Git 忽略），然后一键启动 API、Celery worker 与前端：

```bash
./scripts/start-dev-services.sh start
```

停止该脚本启动的进程：

```bash
./scripts/start-dev-services.sh stop
```

脚本不会停止已占用 `8000` 或 `5173` 端口的既有开发进程；需先手动停止旧进程，才能让新的环境变量对 API 生效。

## 环境变量

- `DATABASE_URL`：默认 `sqlite:///backend/data/productshot.db`。
- `IMAGE_PROVIDER`：必须设为 `openai` 或 `dashscope`；未设置时，图片生成返回 `503`。
- `TEXT_PROVIDER`：必须设为 `openai` 或 `dashscope`；未设置时，Agent 工作流返回 `503`。
- `OPENAI_API_KEY`、`DASHSCOPE_API_KEY`：对应平台的密钥，只从系统环境变量读取。
- `OPENAI_BASE_URL`、`DASHSCOPE_BASE_HTTP_API_URL`：可选 Base URL，默认分别为 OpenAI 与百炼公开地址。
- `OPENAI_TEXT_MODEL`、`OPENAI_IMAGE_MODEL`：OpenAI 的文字和图片模型 ID。
- `DASHSCOPE_TEXT_MODEL`：百炼普通文字推理模型 ID；`TEXT_MODEL` 仅作为旧版配置兼容项。
- `DASHSCOPE_VISION_MODEL`：百炼原图理解使用的多模态模型 ID，必须支持 `MultiModalConversation`。
- `DASHSCOPE_IMAGE_MODEL`：百炼图片生成模型 ID。
- `DASHSCOPE_API_KEY`：百炼 API Key，只从系统环境变量读取，不要写入代码或提交到仓库。
- `DASHSCOPE_BASE_HTTP_API_URL`：百炼 SDK base URL，默认 `https://dashscope.aliyuncs.com/api/v1`。
- `DASHSCOPE_TEXT_BASE_URL`：兼容旧配置名；未设置 `DASHSCOPE_BASE_HTTP_API_URL` 时会作为 SDK base URL 使用。
- `DASHSCOPE_WORKSPACE_ID`：可选，RAM 子账号或业务空间隔离场景使用。
- `MODEL_REQUEST_TIMEOUT`：模型 API 请求超时时间，默认 `180` 秒。
- `CORS_ORIGINS`：前端允许来源。
- `CELERY_BROKER_URL`：AI 审核模式的 Celery Broker 地址；生产部署使用 Redis。
- `CELERY_RESULT_BACKEND`：可选的 Celery 结果后端地址。

开发阶段使用百炼时，只需要在本机或部署环境设置变量，例如：

```bash
export TEXT_PROVIDER=dashscope
export IMAGE_PROVIDER=dashscope
export DASHSCOPE_TEXT_MODEL=your_text_model
export DASHSCOPE_VISION_MODEL=your_multimodal_model
export DASHSCOPE_IMAGE_MODEL=your_image_model
export DASHSCOPE_BASE_HTTP_API_URL=https://dashscope.aliyuncs.com/api/v1
```

不要在 `.env`、README、代码、测试或前端请求中写入真实 Key、个人专属 Base URL、Workspace ID 或业务空间地址。前端模型管理页只展示 Key 是否已配置，并允许调整非敏感模型配置。

通过模型管理页保存后，选中的 Provider、模型名称和 Base URL 会持久化到数据库，文字、图片理解和图片生成模型名称也会分别保留在可删除的历史下拉列表中。密钥不会保存到数据库；API 与 Celery worker 都继续从环境变量读取密钥，并从数据库读取同一份非敏感模型配置。未保存过任何配置时，系统仍回退到上述环境变量。

未配置有效 Provider、密钥或模型名时，系统不会降级到本地规则或占位图，而是返回说明缺失配置的错误。

## AI 审核模式运行时

一次生图仍可使用本地 SQLite。开启 AI 审核模式时，后端要求 `DATABASE_URL` 指向 PostgreSQL，且已配置 `CELERY_BROKER_URL`；这是为了让“生成 → 多模态审核 → Prompt 修订”循环具备持久化状态、可停止和 worker 恢复能力。

本仓库提供本地演示环境：

```bash
docker compose up --build
```

它会启动 PostgreSQL、Redis、API 和 Celery worker。图片/文字模型密钥仍只应在本机或部署环境设置，不要写入 compose 文件。

手动启动 worker：

```bash
cd backend
alembic upgrade head
celery -A app.celery_app.celery_app worker --loglevel=INFO
```

## 主要工作流接口

- `PATCH /api/projects/{project_id}`、`PUT /api/projects/{project_id}/primary-asset`：只在来源确认前更新商品与主图。
- `POST /api/projects/{project_id}/confirm-source`：确认并锁定商品事实与原图。
- `POST /api/projects/{project_id}/agent/visual-analysis/corrections`、`.../confirm`：自然语言纠正并确认原图理解。
- `POST /api/projects/{project_id}/agent/analyze`：在理解确认后生成商品策略，不自动生成创意方向。
- `POST /api/projects/{project_id}/creative-plan-batches`：按可选平台、风格与反馈生成 3 个方向。
- `POST /api/projects/{project_id}/creative-plans/{plan_id}/prompt-packs`：仅在用户决定出图时创建 Prompt Pack。
- `POST /api/projects/{project_id}/prompt-packs/{prompt_pack_id}/generation-tasks`：提交按方向/轮次隔离的出图任务。
- `POST /api/projects/{project_id}/quality-runs`：启动可选 AI 审核生图循环，配置评分倾向、通过分、每轮张数和最大轮数。
- `POST /api/projects/{project_id}/quality-runs/{quality_run_id}/stop`：停止后续循环；当前外部调用完成后生效。
- `POST /api/projects/{project_id}/quality-runs/{quality_run_id}/retry`：仅对失败的审核运行显式创建一次新的质量循环，不会重复未知状态的外部调用。
- `POST /api/projects/{project_id}/quality-runs/{quality_run_id}/decision`：对临界结果接受推荐候选或继续预算内的下一轮。
- `PUT /api/projects/{project_id}/copywriting/{copywriting_id}`：更新该交付图的当前文案稿。
