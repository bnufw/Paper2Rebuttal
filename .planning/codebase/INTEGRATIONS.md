# External Integrations

**Analysis Date:** 2026-03-03

## APIs & External Services

**LLM Inference Providers:**
- OpenRouter - 多模型聚合推理入口
  - SDK/Client: `openai.OpenAI` + `httpx.Client`（`llm.py`）
  - Auth: `OPENROUTER_API_KEY`（定义于 `.env.example`）
- Qwen (DashScope) - 通过 OpenAI 兼容接口调用
  - SDK/Client: `openai.OpenAI` + `httpx.Client`（`llm.py`）
  - Auth: `QWEN_API_KEY`
- DeepSeek - 通过 OpenAI 兼容接口调用
  - SDK/Client: `openai.OpenAI` + `httpx.Client`（`llm.py`）
  - Auth: `DEEPSEEK_API_KEY`
- OpenAI - 原生 OpenAI 兼容接口调用
  - SDK/Client: `openai.OpenAI` + `httpx.Client`（`llm.py`）
  - Auth: `OPENAI_API_KEY`
- Gemini - 使用 Google 原生 SDK
  - SDK/Client: `google.generativeai`（`llm.py`）
  - Auth: `GEMINI_API_KEY`
- ZhiPu (GLM) - 通过 OpenAI 兼容接口调用
  - SDK/Client: `openai.OpenAI` + `httpx.Client`（`llm.py`）
  - Auth: `ZHIPUAI_API_KEY`

**Academic Search & Retrieval:**
- arXiv API - 检索相关论文元数据（`arxiv.py` 中 `ARXIV_API = https://export.arxiv.org/api/query`）
  - SDK/Client: Python `urllib.request` + XML 解析（`arxiv.py`）
  - Auth: Not required
- arXiv PDF/e-print 下载 - 拉取 PDF 或源码包并转换（`arxiv.py`、`tools.py`）
  - SDK/Client: Python `urllib.request`（`DIRECT_OPENER`/`ARXIV_DIRECT_OPENER`）
  - Auth: Not required

**Web Assets:**
- Google Fonts - 前端字体加载（`app.py` 中 `@import url('https://fonts.googleapis.com/...')`）
  - SDK/Client: CSS `@import`
  - Auth: Not required

## Data Storage

**Databases:**
- None（未检测到数据库驱动、ORM、迁移脚本）

**File Storage:**
- Local filesystem only
- 会话文件：`gradio_uploads/<session_id>/paper.pdf`、`gradio_uploads/<session_id>/review.txt`（`app.py`）
- 会话日志：`gradio_uploads/<session_id>/logs/*.txt|*.json`（`rebuttal_service.py`）
- 参考论文与转换结果：`gradio_uploads/<session_id>/arxiv_papers/*`（`rebuttal_service.py` + `tools.py`）

**Caching:**
- None（未检测到 Redis/Memcached/本地缓存框架）

## Authentication & Identity

**Auth Provider:**
- Custom（按所选 LLM Provider 的 API Key 鉴权）
  - Implementation: UI 输入或环境变量读取 API Key，调用时注入客户端（`app.py`、`llm.py`、`.env.example`）

## Monitoring & Observability

**Error Tracking:**
- None（未检测到 Sentry/Datadog/New Relic 等）

**Logs:**
- 应用日志通过 `print` 输出到控制台（`app.py`、`rebuttal_service.py`、`arxiv.py`、`tools.py`）
- 结构化会话日志与摘要写入本地文件：`session_summary.json`、`interaction_q*.json`、`token_usage.json`（`rebuttal_service.py`、`llm.py`）

## CI/CD & Deployment

**Hosting:**
- Local Gradio server（`python app.py --port 8080`，见 `README.md`）
- Optional: Hugging Face Space（文档链接在 `README.md`）

**CI Pipeline:**
- None（未检测到 `.github/workflows/`、GitLab CI、Jenkins 配置）

## Environment Configuration

**Required env vars:**
- `OPENROUTER_API_KEY`
- `QWEN_API_KEY`
- `DEEPSEEK_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `ZHIPUAI_API_KEY`
- 可选 Base URL 覆盖：`OPENROUTER_API_BASE_URL`、`QWEN_API_BASE_URL`、`DEEPSEEK_API_BASE_URL`、`OPENAI_API_BASE_URL`、`ZHIPUAI_API_BASE_URL`
- 运行参数相关：`DOCLING_DEVICE`、`GRADIO_LANGUAGE`、`OMP_NUM_THREADS`（见 `app.py`、`tools.py`）

**Secrets location:**
- 本地 `.env`（模板在 `.env.example`，`.gitignore` 已忽略 `.env`）
- Gradio 表单输入（仅用于当前会话，见 `app.py`）

## Webhooks & Callbacks

**Incoming:**
- None（未定义外部 webhook endpoint）

**Outgoing:**
- None（未定义 webhook 回调投递）

---

*Integration audit: 2026-03-03*
