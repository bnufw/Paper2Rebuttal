# Architecture

**Analysis Date:** 2026-03-03

## Pattern Overview

**Overall:** Layered monolith with workflow orchestration and multi-agent pipeline.

**Key Characteristics:**
- Single-process Gradio application controls the full lifecycle in `app.py`.
- Workflow orchestration and state management are centralized in `rebuttal_service.py`.
- External capabilities are separated into integration modules: `llm.py`, `arxiv.py`, and `tools.py`.

## Layers

**Presentation Layer (UI + Interaction):**
- Purpose: Render UI, collect inputs, and dispatch event callbacks.
- Location: `app.py`
- Contains: Gradio view tree (`gr.Blocks`) and handlers like `start_analysis`, `run_initial_analysis`, `regenerate_strategy`, `confirm_and_next`, `resume_session`, `poll_logs`.
- Depends on: `rebuttal_service.py`, `gradio`, `fastapi`.
- Used by: Browser users connected to the app launched from `app.py`.

**Application Service Layer (Workflow Coordinator):**
- Purpose: Coordinate session creation, question processing, feedback revision, and final rebuttal generation.
- Location: `rebuttal_service.py`
- Contains: `RebuttalService`, `create_session`, `run_initial_analysis`, `process_all_questions_parallel`, `process_single_question`, `revise_with_feedback`, `generate_final_rebuttal`.
- Depends on: `llm.py`, `arxiv.py`, `tools.py`.
- Used by: UI callbacks in `app.py`.

**Domain Agent Layer (Prompt-Driven Stages):**
- Purpose: Encapsulate each reasoning stage as a dedicated class.
- Location: `rebuttal_service.py`
- Contains: `Agent1` to `Agent9`, `Agent7WithHumanFeedback`, and extraction helpers.
- Depends on: Prompt loader `load_prompt` from `tools.py` and LLM gateway `get_llm_client`.
- Used by: `RebuttalService` pipeline methods.

**Integration Layer (LLM + Retrieval + Conversion):**
- Purpose: Provide external API clients and document processing utilities.
- Location: `llm.py`, `arxiv.py`, `tools.py`
- Contains: Provider routing (`LLMClient`), arXiv search/download (`ArxivAgent`), PDF-to-Markdown conversion (`pdf_to_md`), prompt mapping (`PROMPT_NAME_MAPPING`).
- Depends on: external SDKs in `requirements.txt` and provider keys in `.env.example`.
- Used by: `rebuttal_service.py`.

**Prompt/Knowledge Layer:**
- Purpose: Store stage-specific prompt templates used by all agent classes.
- Location: `prompts/`
- Contains: YAML prompts such as `prompts/semantic_encoder.yaml`, `prompts/issue_extractor.yaml`, `prompts/strategy_reviewer.yaml`, `prompts/rebuttal_writer.yaml`.
- Depends on: `tools.py` (`load_prompt`).
- Used by: Agent classes in `rebuttal_service.py`.

**Runtime Persistence Layer:**
- Purpose: Persist session artifacts for resume and audit.
- Location: `gradio_uploads/<session_id>/` (created by `app.py` and `rebuttal_service.py`)
- Contains: uploaded files, logs (`logs/*.txt`, `logs/*.json`), per-question interactions, and downloaded references (`arxiv_papers/`).
- Depends on: filesystem under repository root.
- Used by: session restore methods (`restore_session_from_disk`, `restore_sessions_from_disk`) in `rebuttal_service.py`.

## Data Flow

**Primary Flow (Upload → Strategy Review → Final Rebuttal):**

1. `start_analysis` in `app.py` validates files/API key, calls `init_llm_client`, saves uploads, and creates a session via `rebuttal_service.create_session`.
2. `run_initial_analysis` in `app.py` triggers `rebuttal_service.run_initial_analysis` to run `pdf_to_md` then `Agent1` + `Agent2` + `Agent2Checker`.
3. `rebuttal_service.process_all_questions_parallel` dispatches one `process_single_question` per question with `ThreadPoolExecutor`.
4. Each question executes `Agent3` (search decision), optional `search_relevant_papers` + `Agent4`, parallel `Agent5` for references, then `Agent6` and `Agent7`.
5. User feedback from `regenerate_strategy` in `app.py` calls `rebuttal_service.revise_with_feedback` and `Agent7WithHumanFeedback`.
6. After all questions are confirmed, `generate_final_rebuttal` in `rebuttal_service.py` runs `Agent8` and `Agent9`, then writes `final_rebuttal.txt`.

**Recovery Flow (Refresh/Resume):**

1. `resume_session` in `app.py` initializes provider config and calls `rebuttal_service.get_session` or `restore_session_from_disk`.
2. `_load_session_from_dir` in `rebuttal_service.py` rebuilds `SessionState` using `logs/session_summary.json`, `logs/interaction_q*.json`, and `logs/agent*_output.txt`.
3. UI resumes at the first unsatisfied question or directly shows final outputs.

**State Management:**
- In-memory: `RebuttalService.sessions` dictionary with thread protection (`self._lock`) in `rebuttal_service.py`.
- UI-side: `gr.State` object storing `session_id` and `current_idx` in `app.py`.
- Persistent: filesystem session artifacts in `gradio_uploads/` and summary logs written by `_save_session_summary` in `rebuttal_service.py`.

## Key Abstractions

**Session and Question Models:**
- Purpose: Represent workflow progress and per-question status.
- Examples: `SessionState`, `QuestionState`, `ProcessStatus` in `rebuttal_service.py`.
- Pattern: dataclass-backed state with enum-driven status transitions.

**Agent Stage Objects:**
- Purpose: Isolate each pipeline step behind a `run()` contract.
- Examples: `Agent1`, `Agent2Checker`, `Agent5`, `Agent7WithHumanFeedback`, `Agent9` in `rebuttal_service.py`.
- Pattern: context builder + `get_llm_client().generate(...)` + log persistence.

**LLM Gateway:**
- Purpose: Abstract multiple providers behind one invocation API.
- Examples: `LLMClient.generate`, `_generate_gemini`, `_generate_openai_compatible` in `llm.py`.
- Pattern: provider strategy + retry/backoff + token accounting (`TokenUsageTracker`).

**Reference Material Pipeline:**
- Purpose: Acquire and normalize external literature for downstream reasoning.
- Examples: `search_relevant_papers` in `arxiv.py`, `download_pdf_and_convert_md` and `pdf_to_md` in `tools.py`.
- Pattern: best-effort retrieval with fallback markdown generation on failures.

## Entry Points

**Web Application Entry Point:**
- Location: `app.py`
- Triggers: CLI execution `python app.py ...`.
- Responsibilities: initialize Gradio app, wire UI callbacks, and launch server via `demo.launch(...)`.

**Service Singleton Entry Point:**
- Location: `rebuttal_service.py`
- Triggers: module import in `app.py`.
- Responsibilities: create shared `rebuttal_service = RebuttalService()` instance for all callbacks.

**LLM Initialization Entry Point:**
- Location: `rebuttal_service.py`
- Triggers: `start_analysis` and `resume_session` in `app.py`.
- Responsibilities: construct global LLM client through `init_llm_client(...)`.

## Error Handling

**Strategy:** Guard invalid state early, retry unstable external calls, and degrade gracefully for paper retrieval/conversion failures.

**Patterns:**
- Validation + explicit exceptions for missing sessions, invalid question indices, and missing uploads in `app.py` and `rebuttal_service.py`.
- Retry with exponential backoff in `LLMClient.generate` (`llm.py`) and network retries in `download_pdf_and_convert_md` (`tools.py`).
- Fallback content generation when reference download/parse fails (`create_fallback_markdown_file` in `tools.py`, abstract markdown fallback in `arxiv.py`).

## Cross-Cutting Concerns

**Logging:** Timestamped UI logs through `LogCollector` and persisted artifacts in `gradio_uploads/<session_id>/logs/` from `rebuttal_service.py`.
**Validation:** Input and state validation in `app.py` plus JSON sanitation via `_fix_json_escapes` in `tools.py`.
**Authentication:** Provider API keys come from `.env.example`-style environment variables or UI input; keys are injected into `LLMClient` via `init_llm_client` without separate user auth.

---

*Architecture analysis: 2026-03-03*
