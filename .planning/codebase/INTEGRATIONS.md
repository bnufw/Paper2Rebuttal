# External Integrations

**Analysis Date:** 2026-03-03

## APIs & External Services

**LLM Inference Services:**
- Multi-provider LLM APIs (OpenRouter, Qwen/DashScope, DeepSeek, OpenAI, Gemini, ZhiPu/GLM) - used for all Agent1-9 generation in `rebuttal_service.py` via `llm.py`.
  - SDK/Client:
    - OpenAI-compatible path (`openai.OpenAI` + `httpx.Client`) in `llm.py` for `openrouter`/`qwen`/`deepseek`/`openai`/`zhipu`.
    - Native Gemini path (`google.generativeai`) in `llm.py` for `gemini`.
  - Auth: API key from UI (`app.py` API textbox) or environment (`.env.example` vars).
  - Endpoints used:
    - `https://openrouter.ai/api/v1` (`OPENROUTER_API_BASE_URL`)
    - `https://dashscope.aliyuncs.com/compatible-mode/v1` (`QWEN_API_BASE_URL`)
    - `https://api.deepseek.com` (`DEEPSEEK_API_BASE_URL`)
    - `https://api.openai.com/v1` (`OPENAI_API_BASE_URL`)
    - `https://open.bigmodel.cn/api/paas/v4/` (`ZHIPUAI_API_BASE_URL`)
    - Gemini uses native SDK (no fixed base URL in `llm.py`).
  - Practical behavior:
    - Request timeout is `600s` (`llm.py::LLMClient.__init__`).
    - Retries are exponential backoff (`2s`, `4s`, `8s`) with `max_retries=3` (`llm.py::generate`).
    - OpenRouter adds `HTTP-Referer` and `X-Title` headers (`llm.py`).

**Research Retrieval APIs:**
- arXiv API + paper resources - used for literature search and reference download in `arxiv.py` and `tools.py`.
  - Integration method: REST/Atom feed over `urllib.request`.
  - Endpoints used:
    - Search feed: `https://export.arxiv.org/api/query` (`arxiv.py::ARXIV_API`)
    - PDF links: `https://arxiv.org/pdf/<id>.pdf` (parsed/generated in `arxiv.py`/`tools.py`)
    - Source archive: `https://arxiv.org/e-print/<id>` (`arxiv.py`)
    - Abstract links: `https://arxiv.org/abs/<id>` (`arxiv.py`)
  - Practical behavior:
    - Search timeout: `30s` (`arxiv.py::_search_arxiv`).
    - PDF/source download timeout up to `60s` (`arxiv.py`, `tools.py`).
    - Download retries with jitter in `tools.py::download_pdf_and_convert_md`.

**Model Artifact Hosting (indirect):**
- Hugging Face Hub (through Docling internals) - first-run model downloads noted in `README.md`.
  - Runtime flags in `app.py`: `HF_HUB_DISABLE_SYMLINKS_WARNING`, `HF_HUB_DISABLE_SYMLINKS`.
  - Related dependency: `hf_xet` (`requirements.txt`).

## Data Storage

**Databases:**
- None. No SQL/NoSQL driver or ORM is used; all state is in-memory + filesystem (`rebuttal_service.py`, `app.py`).

**File Storage:**
- Local filesystem under `gradio_uploads/` (created in `app.py` and `rebuttal_service.py`).
  - Session root: `gradio_uploads/<session_id>/`
  - Uploads: `paper.pdf`, `review.txt` (`app.py::save_uploaded_files`)
  - Converted paper markdown: `gradio_uploads/<session_id>/*.md` (`tools.py::pdf_to_md`)
  - Logs: `gradio_uploads/<session_id>/logs/`
  - Reference artifacts: `gradio_uploads/<session_id>/arxiv_papers/`
  - Final outputs: `logs/final_rebuttal.txt`, `logs/session_summary.json`, `logs/token_usage.json`, `logs/interaction_q*.json` (`rebuttal_service.py`).

**Caching:**
- In-memory session cache: `RebuttalService.sessions` in `rebuttal_service.py`.
- In-memory Docling converter singleton: `_docling_converter` in `tools.py`.
- No Redis or external cache.

## Authentication & Identity

**Auth Provider:**
- None for end users (no login/session auth system).

**Credential Handling:**
- LLM credentials are provider API keys.
  - Sources: UI input in `app.py` and env prefill from `.env`/`.env.example`.
  - Routing: provider key selection in `app.py::PROVIDER_CONFIGS`, consumed by `rebuttal_service.py::init_llm_client` and `llm.py`.
- No OAuth flow and no token refresh logic in repository.

## Monitoring & Observability

**Error Tracking:**
- No external service (no Sentry/Datadog integration).

**Analytics:**
- None.

**Logs:**
- Real-time in-memory log stream via `LogCollector` (`rebuttal_service.py`) surfaced by `app.py::poll_logs`.
- Persistent per-session operational logs in `gradio_uploads/<session_id>/logs/`:
  - Agent inputs/outputs (`agent*_input.txt`, `agent*_output.txt`)
  - Token usage (`token_usage.json`)
  - Session snapshot (`session_summary.json`)
  - Feedback interactions (`interaction_q*.json`)
  - Final rebuttal (`final_rebuttal.txt`)

## CI/CD & Deployment

**Hosting:**
- Primary target: local/self-hosted Gradio app launched by `python app.py`.
- Optional public demo reference exists in `README.md` (Hugging Face Space link), but this repo has no deployment config files.

**CI Pipeline:**
- None found (`.github/workflows/` not used for this app in current repo state).

## Environment Configuration

**Development:**
- Required env vars depend on chosen provider (`.env.example`):
  - `OPENROUTER_API_KEY`, `QWEN_API_KEY`, `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ZHIPUAI_API_KEY`
  - Optional overrides: `OPENROUTER_API_BASE_URL`, `QWEN_API_BASE_URL`, `DEEPSEEK_API_BASE_URL`, `OPENAI_API_BASE_URL`, `ZHIPUAI_API_BASE_URL`
- Runtime flags: `DOCLING_DEVICE`, `GRADIO_LANGUAGE`, `HF_HUB_DISABLE_SYMLINKS_WARNING`, `HF_HUB_DISABLE_SYMLINKS`, `OMP_NUM_THREADS`.
- Secrets location: `.env` (gitignored by project practice; initialized from `.env.example`).

**Staging:**
- Not explicitly separated in code; environment switching is achieved only by different env var sets.

**Production:**
- Same configuration model as development.
- Requires stable outbound network access to selected LLM provider and arXiv endpoints.
- Requires persistent writable storage for session restore (`rebuttal_service.py::restore_session_from_disk`).

## Webhooks & Callbacks

**Incoming:**
- None.

**Outgoing:**
- None.

---

*Integration audit: 2026-03-03*
*Update when adding/removing external services*
