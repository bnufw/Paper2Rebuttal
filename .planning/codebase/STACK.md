# Technology Stack

**Analysis Date:** 2026-03-03

## Languages

**Primary:**
- Python 3.10 - 主应用与多代理流程实现，入口在 `app.py`，核心流程在 `rebuttal_service.py`、`llm.py`、`arxiv.py`、`tools.py`

**Secondary:**
- Markdown - 文档与中间产物（如 `README.md`、`gradio_uploads/*/*.md`）
- YAML - 提示词配置，位于 `prompts/*.yaml`
- CSS - Gradio 样式字符串中内联使用，位于 `app.py`

## Runtime

**Environment:**
- Python 3.10（`README.md` 推荐 `conda create -n rebuttal python=3.10`）
- Docling 设备通过环境变量 `DOCLING_DEVICE` 控制（`app.py` 启动参数写入，`tools.py` 读取）

**Package Manager:**
- pip（`README.md` 使用 `pip install -r requirements.txt`）
- Lockfile: missing（仓库未检测到 `poetry.lock`、`Pipfile.lock`、`requirements.lock` 等）

## Frameworks

**Core:**
- Gradio 6.2.0 - Web UI 与事件编排（`requirements.txt`，实现于 `app.py`）
- FastAPI 0.128.0 - 被 Gradio 内部使用并在 `app.py` 中做健康检查路由 monkey patch
- Docling 2.30.0 - PDF 转 Markdown（`tools.py` 中 `pdf_to_md`）

**Testing:**
- Not detected（仓库无 `tests/` 与测试框架依赖）

**Build/Dev:**
- python-dotenv >=1.0.0 - 从 `.env` 加载环境变量（`app.py`）
- PyYAML >=6.0 - 加载 `prompts/*.yaml`（`tools.py`）
- hf_xet >=1.0.0 - Hugging Face 传输加速依赖（`requirements.txt`）

## Key Dependencies

**Critical:**
- `openai==2.14.0` - OpenAI 兼容接口客户端，驱动 OpenRouter/Qwen/DeepSeek/OpenAI/Zhipu（`llm.py`）
- `google-generativeai>=0.8.0` - Gemini 原生 SDK（`llm.py`）
- `docling==2.30.0` - 论文 PDF 解析为 Markdown（`tools.py`）
- `gradio==6.2.0` - 用户交互界面（`app.py`）

**Infrastructure:**
- `httpx[socks]==0.28.1` - LLM HTTP 客户端与代理环境兼容（`llm.py`）
- `Requests==2.32.5` - 依赖声明存在，核心流程主要使用 `urllib` 与 `httpx`（`requirements.txt`、`arxiv.py`、`tools.py`）
- `fastapi==0.128.0` - Gradio/FastAPI 兼容层（`app.py`）

## Configuration

**Environment:**
- 通过 `.env.example` 定义 provider API key 与可选 base URL：`OPENROUTER_API_KEY`、`QWEN_API_KEY`、`DEEPSEEK_API_KEY`、`OPENAI_API_KEY`、`GEMINI_API_KEY`、`ZHIPUAI_API_KEY` 及对应 `*_API_BASE_URL`
- `app.py` 在启动时尝试 `load_dotenv()`；`llm.py` 按 provider 读取对应环境变量并支持 `*_API_BASE_URL` 覆盖
- `tools.py` 设置 `OMP_NUM_THREADS=4`，并按 `DOCLING_DEVICE` 初始化 Docling

**Build:**
- 无独立构建系统（未检测到 `Makefile`/`pyproject.toml`/`package.json`）
- 运行方式为 `python app.py --port 8080` 或 `python app.py --device cuda --port 8080`（`README.md`）

## Platform Requirements

**Development:**
- Conda/Python 3.10 + pip（`README.md`）
- 若启用 GPU，需要预先安装与 CUDA 对应的 PyTorch（`README.md`）
- 需可访问外部服务：LLM 提供商 API、`arxiv.org`/`export.arxiv.org`、Google Fonts、Hugging Face（Docling 首次模型下载）

**Production:**
- 目标为本地部署优先（`README.md`）
- 可选演示部署在 Hugging Face Spaces（`README.md` 链接）
- 运行时会在本地产生会话与日志目录（`gradio_uploads/`，由 `app.py` 与 `rebuttal_service.py` 创建）

---

*Stack analysis: 2026-03-03*
