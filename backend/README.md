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

未配置有效 Provider、密钥或模型名时，系统不会降级到本地规则或占位图，而是返回说明缺失配置的错误。

## 主要工作流接口

- `PATCH /api/projects/{project_id}`、`PUT /api/projects/{project_id}/primary-asset`：只在来源确认前更新商品与主图。
- `POST /api/projects/{project_id}/confirm-source`：确认并锁定商品事实与原图。
- `POST /api/projects/{project_id}/agent/visual-analysis/corrections`、`.../confirm`：自然语言纠正并确认原图理解。
- `POST /api/projects/{project_id}/agent/analyze`：在理解确认后生成商品策略，不自动生成创意方向。
- `POST /api/projects/{project_id}/creative-plan-batches`：按可选平台、风格与反馈生成 3 个方向。
- `POST /api/projects/{project_id}/creative-plans/{plan_id}/prompt-packs`：仅在用户决定出图时创建 Prompt Pack。
- `POST /api/projects/{project_id}/prompt-packs/{prompt_pack_id}/generation-tasks`：提交按方向/轮次隔离的出图任务。
- `PUT /api/projects/{project_id}/copywriting/{copywriting_id}`：更新该交付图的当前文案稿。
