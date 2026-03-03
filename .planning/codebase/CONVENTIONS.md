# Coding Conventions

**Analysis Date:** 2026-03-03

## Naming Patterns

**Files:**
- Python modules use lowercase/snake_case names at repo root: `app.py`, `rebuttal_service.py`, `llm.py`, `arxiv.py`, `tools.py`.
- Prompt files are stage-scoped snake_case YAML under `prompts/`, e.g. `prompts/semantic_encoder.yaml`, `prompts/strategy_reviewer.yaml`, `prompts/rebuttal_writer.yaml`.
- Runtime output uses dedicated artifact directories such as `gradio_uploads/`, `arxiv_papers/`, `arxiv_papers_md/`, `sessions/` and these are ignored in `.gitignore`.

**Functions:**
- `snake_case` for top-level functions and methods, e.g. `save_uploaded_files` in `app.py`, `extract_review_questions` in `rebuttal_service.py`, `search_relevant_papers` in `arxiv.py`.
- Single leading underscore for internal helpers, e.g. `_read_text`, `_fix_json_escapes` in `tools.py`, `_download_source_first` in `arxiv.py`.
- Agent methods follow stable names (`_build_context`, `run`, optional `extract`) across `Agent1`-`Agent9` in `rebuttal_service.py`.

**Variables:**
- `snake_case` for locals/attributes (`paper_summary`, `review_file_path`, `progress_callback`).
- `UPPER_SNAKE_CASE` for constants (`SESSIONS_BASE_DIR`, `QUESTIONS_UPPER_BOUND`, `ARXIV_API`, `PROMPTS_DIR`).
- Shared module-level state is used for long-lived objects (`llm_client`, `token_tracker` in `rebuttal_service.py`, `_docling_converter` in `tools.py`).

**Types:**
- `PascalCase` for classes, dataclasses, and enums (`LLMClient`, `TokenUsageTracker`, `QuestionState`, `SessionState`, `ProcessStatus`, `ArxivAgent`).
- Type hints are used broadly with `Optional`, `List`, `Dict`, `Tuple`, `Callable`, and PEP604 unions (`str | None`).
- Dataclasses use `field(default_factory=...)` for mutable defaults in `rebuttal_service.py`.

## Code Style

**Formatting:**
- 4-space indentation and standard Python block structure.
- Predominantly double-quoted strings.
- No formatter config found (`pyproject.toml`, `setup.cfg`, `.flake8`, `.ruff.toml` are absent in repo root).
- Docstrings are present for non-obvious behavior (examples: `pdf_to_md` and `load_prompt` in `tools.py`, state classes in `rebuttal_service.py`).

**Linting:**
- No lint tool configuration detected.
- Quality control is currently convention-driven (`AGENTS.md`) plus manual checks.

## Import Organization

**Order:**
1. Standard library imports first (e.g., `os`, `sys`, `json`, `threading`).
2. Third-party imports next (e.g., `gradio`, `fastapi`, `httpx`, `openai`).
3. Project-local imports last (e.g., `from rebuttal_service import ...`, `from tools import ...`).

**Grouping:**
- Blank lines usually separate import groups.
- Alphabetical ordering is not enforced; follow nearby style in each file.

**Path Aliases:**
- No path aliasing; imports use module names directly (`from arxiv import ...`, `from llm import ...`).

## Error Handling

**Patterns:**
- Hard precondition failures raise exceptions early (e.g., `get_llm_client` in `rebuttal_service.py`, session/index checks in `RebuttalService`).
- External I/O/network calls use `try/except` with graceful fallback returns (`None`, `[]`, default strings) in `tools.py` and `arxiv.py`.
- Retry/backoff exists around unstable dependencies in `llm.py` and PDF download logic in `tools.py`.

**Error Types:**
- Parsing errors are locally handled and downgraded to safe defaults (JSON parsing in `Agent3.extract` and `extract_reference_paper_indices`).
- Workflow-level exceptions bubble up to status transitions (`ProcessStatus.ERROR`) in `RebuttalService` orchestration methods.

## Logging

**Framework:**
- No `logging` package usage in core modules.
- Runtime tracing relies on tagged `print(...)` messages (`[DEBUG]`, `[INFO]`, `[WARNING]`, `[ERROR]`) in `app.py`, `llm.py`, `tools.py`, and `arxiv.py`.
- UI-visible progress uses thread-safe `LogCollector` in `rebuttal_service.py`.

**Patterns:**
- Log around external boundaries: API calls, downloads, conversion, session transitions.
- Include identifiers in logs when available (`[Q{question_id}]`, `[Parallel]`, `[Final]`).

## Comments

**When to Comment:**
- Comments are brief and purpose-oriented, usually describing constraints or compatibility decisions.
- Good examples: lazy import rationale for Docling in `tools.py`, environment/bootstrap notes in `app.py`.

**Docstrings:**
- Used for public helpers and non-trivial functions.
- Internal simple methods often omit docstrings when names are self-explanatory.

**TODO Comments:**
- No strict inline TODO format enforced in source modules.
- Project-level TODO checklist appears in `README.md`.

## Function Design

**Size:**
- Pipeline orchestrators can be long (e.g., `process_single_question` in `rebuttal_service.py`).
- Complexity is managed by extracting repeated work into helper methods and agent classes.

**Parameters:**
- Explicit, typed signatures are preferred.
- Callback injection is used for UI updates (`progress_callback`) instead of global event systems.

**Return Values:**
- Explicit return values are standard (`Tuple[...]`, `List[...]`, state objects).
- Guard clauses handle invalid input/state early.

## Module Design

**Responsibilities:**
- `app.py`: Gradio UI and event handlers.
- `rebuttal_service.py`: session lifecycle, multi-agent orchestration, persistence.
- `llm.py`: provider routing, retries, token tracking.
- `arxiv.py`: arXiv retrieval/download/format conversion.
- `tools.py`: shared utilities (prompt loading, PDF conversion, download helpers).

**Persistence and Artifacts:**
- Session-scoped runtime files are written under `gradio_uploads/` from `rebuttal_service.py` and `app.py`.
- Large/generated artifacts remain untracked via `.gitignore` (`gradio_uploads/`, `arxiv_papers/`, `arxiv_papers_md/`, `sessions/`).

**Practical Rule for New Code:**
- Extend the existing module that already owns the concern before creating a new module.
- Keep type hints, naming, and log-tag style consistent with adjacent code.
- Preserve graceful fallbacks around external dependencies.

---

*Convention analysis: 2026-03-03*
*Update when patterns change*
