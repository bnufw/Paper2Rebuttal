# Technology Stack

**Analysis Date:** 2026-03-03

## Languages

**Primary:**
- Python 3.10 (recommended) - all runtime logic in `app.py`, `rebuttal_service.py`, `llm.py`, `arxiv.py`, `tools.py`.

**Secondary:**
- YAML - prompt definitions in `prompts/semantic_encoder.yaml`, `prompts/issue_extractor.yaml`, `prompts/rebuttal_writer.yaml` (loaded by `tools.py`).
- Markdown - generated artifacts (`*.md`) for parsed papers and exports under `gradio_uploads/<session_id>/`.
- Shell env syntax - provider/base-url configuration in `.env.example`.

## Runtime

**Environment:**
- CPython 3.10 (project recommendation in `AGENTS.md`: `conda create -n rebuttal python=3.10`).
- Local web runtime started by `python app.py` (`app.py`), optional GPU parsing via `python app.py --device cuda`.
- Docling runtime device controlled by `DOCLING_DEVICE` in `app.py` and `tools.py`.

**Package Manager:**
- `pip` + `requirements.txt`.
- Lockfile: none (`requirements.txt` only; no `poetry.lock`/`Pipfile.lock`).

## Frameworks

**Core:**
- Gradio 6.2.0 - UI, event wiring, and app launch in `app.py`.
- FastAPI 0.128.0 - imported in `app.py` for Gradio route behavior.
- Multi-agent orchestration (custom) - session lifecycle and Agent1-9 pipeline in `rebuttal_service.py`.
- Docling 2.30.0 - PDF-to-Markdown conversion in `tools.py`.

**Testing:**
- No dedicated automated test framework configured in repository root (no `tests/`, no pytest config).

**Build/Dev:**
- `python-dotenv` - `.env` loading in `app.py`.
- PyYAML - YAML prompt loading in `tools.py`.
- `ThreadPoolExecutor` (stdlib) - parallel question and reference processing in `rebuttal_service.py`.

## Key Dependencies

**Critical:**
- `gradio==6.2.0` (`requirements.txt`) - web interface and interactive workflow controls in `app.py`.
- `docling==2.30.0` (`requirements.txt`) - core paper parsing in `tools.py::pdf_to_md`.
- `openai==2.14.0` (`requirements.txt`) - OpenAI-compatible client for OpenRouter/Qwen/DeepSeek/OpenAI/ZhiPu in `llm.py`.
- `google-generativeai>=0.8.0` (`requirements.txt`) - native Gemini SDK path in `llm.py`.
- `httpx[socks]==0.28.1` (`requirements.txt`) - HTTP transport and proxy-aware client in `llm.py`.
- `Requests==2.32.5` (`requirements.txt`) - dependency baseline for HTTP workflows (direct usage is mainly `urllib` + `httpx`).
- `PyYAML>=6.0` (`requirements.txt`) - prompt parsing in `tools.py`.
- `python-dotenv>=1.0.0` (`requirements.txt`) - environment bootstrapping in `app.py`.
- `hf_xet>=1.0.0` (`requirements.txt`) - Hugging Face artifact transport support used by Docling model downloads.

**Infrastructure:**
- Standard library networking (`urllib.request`, `urllib.parse`, `xml.etree.ElementTree`) in `arxiv.py`/`tools.py`.
- Standard library concurrency (`threading`, `concurrent.futures`) in `app.py`, `rebuttal_service.py`, `tools.py`.

## Configuration

**Environment:**
- `.env` loaded at startup in `app.py` (if `python-dotenv` is installed).
- Provider credentials/base URLs declared in `.env.example`: `OPENROUTER_API_KEY`, `OPENROUTER_API_BASE_URL`, `QWEN_API_KEY`, `QWEN_API_BASE_URL`, `DEEPSEEK_API_KEY`, `DEEPSEEK_API_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_API_BASE_URL`, `GEMINI_API_KEY`, `ZHIPUAI_API_KEY`, `ZHIPUAI_API_BASE_URL`.
- Runtime toggles: `DOCLING_DEVICE` (`app.py`, `tools.py`), `GRADIO_LANGUAGE` (`app.py`), `HF_HUB_DISABLE_SYMLINKS_WARNING`/`HF_HUB_DISABLE_SYMLINKS` (`app.py`), `OMP_NUM_THREADS` (`tools.py`).

**Build:**
- Dependency manifest: `requirements.txt`.
- Prompt configuration source: `prompts/*.yaml` resolved via `tools.py::load_prompt` and `PROMPT_NAME_MAPPING`.

## Platform Requirements

**Development:**
- Linux/macOS/Windows with Python 3.10 + `pip` (commands documented in `README.md` and `AGENTS.md`).
- Writable local filesystem required for `gradio_uploads/` session artifacts.
- Optional CUDA-capable GPU for faster Docling conversion (`app.py --device cuda`).
- Optional `pandoc` for higher-fidelity `.tex -> .md` conversion in `arxiv.py::convert_source_archive_to_markdown`.

**Production:**
- Self-hosted process model via `python app.py` (no Docker/Kubernetes manifests in repo).
- Network egress required for LLM APIs (`llm.py`) and arXiv endpoints (`arxiv.py`, `tools.py`).
- Persistent writable storage expected for resume/recovery (`gradio_uploads/<session_id>/logs/session_summary.json`).

---

*Stack analysis: 2026-03-03*
*Update after major dependency changes*
