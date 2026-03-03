# Codebase Structure

**Analysis Date:** 2026-03-03

## Directory Layout

```
Paper2Rebuttal/
├── .codex/                              # Local Codex workflows, skills, templates
│   ├── agents/                          # Agent configs/state for local workflow tooling
│   ├── get-shit-done/                   # GSD command/workflow/template assets
│   │   ├── templates/codebase/          # Source templates (incl. architecture/structure templates)
│   │   └── workflows/                   # Reusable GSD workflow docs
│   └── skills/                          # Project-local skill definitions
├── .planning/                           # Planning outputs generated during mapping/planning
│   └── codebase/                        # Codebase analysis docs (including this file)
├── prompts/                             # YAML prompts consumed by multi-agent pipeline
├── __pycache__/                         # Local Python bytecode cache (generated)
├── AGENTS.md                            # Repository operating instructions
├── README.md                            # User-facing project guide
├── app.py                               # Gradio app entry point and UI event wiring
├── arxiv.py                             # arXiv retrieval/parsing/downloading module
├── llm.py                               # LLM provider adapter + token tracking
├── rebuttal_service.py                  # Core session/pipeline orchestration
├── requirements.txt                     # Python dependencies
├── tools.py                             # Shared helpers: prompt loading, PDF conversion, downloads
├── todo.md                              # Local notes/todo items
└── 改进.md                               # Implementation notes / planned improvements
```

## Directory Purposes

**`prompts/`:**
- Purpose: Stage-specific prompt definitions for all agent steps.
- Contains: `*.yaml` files with `name`, `description`, `prompt`.
- Key files: `prompts/semantic_encoder.yaml`, `prompts/issue_extractor.yaml`, `prompts/strategy_generator.yaml`, `prompts/rebuttal_writer.yaml`.
- Subdirectories: None (flat prompt catalog).

**`.planning/codebase/`:**
- Purpose: Persisted architecture/structure/quality mapping artifacts for planning workflows.
- Contains: Markdown analysis documents.
- Key files: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`.
- Subdirectories: None currently.

**`.codex/get-shit-done/templates/codebase/`:**
- Purpose: Canonical templates used when generating codebase docs.
- Contains: Template markdown files.
- Key files: `.codex/get-shit-done/templates/codebase/architecture.md`, `.codex/get-shit-done/templates/codebase/structure.md`.
- Subdirectories: None under this node.

**Project root (`/home/zhu/code/Paper2Rebuttal`):**
- Purpose: Runtime application source plus repo-level configs/docs.
- Contains: Python modules, docs, dependency file, operational metadata.
- Key files: `app.py`, `rebuttal_service.py`, `llm.py`, `arxiv.py`, `tools.py`.
- Subdirectories: `.codex/`, `.planning/`, `prompts/`, runtime-generated caches.

## Key File Locations

**Entry Points:**
- `app.py`: Process entry (`__main__`) and Gradio UI composition.
- `app.py`: Workflow handlers (`start_analysis`, `run_initial_analysis`, `confirm_and_next`, `skip_question`, `resume_session`).
- `rebuttal_service.py`: Shared orchestrator instance (`rebuttal_service = RebuttalService()`).

**Configuration:**
- `.env.example`: Environment variable template for provider API keys/base URLs.
- `requirements.txt`: Dependency pin list.
- `.gitignore`: Runtime/artifact exclusion rules (`gradio_uploads/`, `arxiv_papers/`, `sessions/`, etc.).
- `app.py`: Provider/model selector maps (`PROVIDER_CONFIGS`, `MODEL_CHOICES_BY_PROVIDER`).

**Core Logic:**
- `rebuttal_service.py`: Session model, agent stages, orchestration, persistence/recovery.
- `llm.py`: Provider abstraction (`LLMClient`) and token telemetry (`TokenUsageTracker`).
- `arxiv.py`: Search/download/source extraction + metadata fetch.
- `tools.py`: Docling conversion, prompt loading, paper download helpers.

**Testing:**
- No dedicated `tests/` directory exists at current snapshot.
- Current validation path is smoke execution via `python app.py` and end-to-end manual run.

**Documentation:**
- `README.md`: Setup, workflow usage, pipeline overview.
- `AGENTS.md`: Repository conventions and collaboration constraints.
- `改进.md`: Change plan notes for extended workflows.
- `.planning/codebase/*.md`: Internal engineering map docs.

## Naming Conventions

**Files:**
- `snake_case.py` for Python modules (`rebuttal_service.py`, `tools.py`).
- `snake_case.yaml` for prompts (`strategy_human_refinement.yaml`).
- `UPPERCASE.md` for key repo instructions (`README.md`, `AGENTS.md`).

**Directories:**
- Lowercase names with underscores when needed (`__pycache__`, `.planning`, `prompts`).
- Hidden tool/control dirs start with dot (`.codex`, `.planning`).

**Special Patterns:**
- Prompt compatibility mapping uses legacy IDs (`"1.txt"`-`"9.txt"`) in `tools.py:PROMPT_NAME_MAPPING`.
- Session logs follow deterministic patterns in `gradio_uploads/<session_id>/logs/`:
- `agent{n}_*.txt`, `agent7_hitl_q{qid}_r{rev}_*.txt`, `interaction_q{qid}.json`, `session_summary.json`.

## Where to Add New Code

**New Pipeline Stage:**
- Primary code: `rebuttal_service.py` (new `AgentX` class + orchestration hook).
- Prompt contract: `prompts/<stage_name>.yaml`.
- Prompt mapping if legacy ID used: `tools.py` (`PROMPT_NAME_MAPPING`).

**New UI Functionality:**
- Interaction logic: `app.py` handler functions and event bindings (`*.click`, `.then`, `.tick`).
- Status/persistence integration: `rebuttal_service.py` session methods.
- Style tweaks: `app.py` (`APP_CSS`).

**New Provider/Model Integration:**
- Backend adapter: `llm.py` (`PROVIDER_CONFIGS`, generation path).
- Frontend selector wiring: `app.py` (`PROVIDER_CONFIGS`, `MODEL_CHOICES_BY_PROVIDER`).
- Env docs: `.env.example` and `README.md`.

**Utilities:**
- Shared parsing/download/conversion helpers: `tools.py`.
- arXiv-specific retrieval/parsing: `arxiv.py`.
- Avoid duplicating helper logic inside `app.py` or agent classes.

## Special Directories

**`gradio_uploads/` (runtime-generated):**
- Purpose: Per-session storage for uploaded files, logs, and outputs.
- Source: Created by `app.py:save_uploaded_files(...)` and `RebuttalService.create_session(...)`.
- Committed: No (`.gitignore` excludes it).

**`gradio_uploads/<session_id>/logs/` (runtime-generated):**
- Purpose: Durable workflow trace and recovery source.
- Source: Agent input/output dumps, interaction logs, summary snapshots, token usage export.
- Committed: No.

**`gradio_uploads/<session_id>/arxiv_papers/` (runtime-generated):**
- Purpose: Downloaded references and converted Markdown artifacts.
- Source: `download_pdf_and_convert_md(...)` in `tools.py`.
- Committed: No.

**`__pycache__/` (runtime-generated):**
- Purpose: CPython bytecode cache.
- Source: Python runtime import system.
- Committed: No.

---

*Structure analysis: 2026-03-03*
*Update when directory structure changes*
