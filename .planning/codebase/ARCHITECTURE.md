# Architecture

**Analysis Date:** 2026-03-03

## Pattern Overview

**Overall:** Gradio-driven monolithic application with a staged multi-agent orchestration pipeline.

**Key Characteristics:**
- Single Python process hosts UI, workflow orchestration, and integrations (`app.py`, `rebuttal_service.py`).
- Stateful session model with in-memory objects plus file-backed recovery (`gradio_uploads/<session_id>/logs`).
- Agent pipeline composed as deterministic stages (Agent1-9) with optional HITL revision loop.
- External dependencies wrapped behind adapter modules (`llm.py`, `arxiv.py`, `tools.py`).

## Layers

**UI & Interaction Layer:**
- Purpose: Accept user inputs, control page states, and bind all workflow actions to UI events.
- Contains: Gradio layout, event handlers, provider/model selectors, resume/poll/download actions.
- Location: `app.py`.
- Depends on: `rebuttal_service.py` public methods and state objects.
- Used by: End users via browser.

**Workflow Orchestration Layer:**
- Purpose: Manage lifecycle of a rebuttal session and coordinate every pipeline stage.
- Contains: `RebuttalService`, `SessionState`, `QuestionState`, `ProcessStatus`.
- Location: `rebuttal_service.py`.
- Depends on: Agent classes (same file), `tools.py`, `arxiv.py`, `llm.py`.
- Used by: `app.py` handlers (`run_initial_analysis`, `regenerate_strategy`, `confirm_and_next`, `skip_question`, `resume_session`).

**Agent Execution Layer:**
- Purpose: Encapsulate stage-specific reasoning and prompt assembly.
- Contains: `Agent1` through `Agent9`, `Agent2Checker`, `Agent7WithHumanFeedback`.
- Location: `rebuttal_service.py`.
- Depends on: `get_llm_client().generate(...)`, `load_prompt(...)`, text/PDF helpers.
- Used by: `RebuttalService.run_initial_analysis`, `RebuttalService.process_single_question`, `RebuttalService.revise_with_feedback`, `RebuttalService.generate_final_rebuttal`.

**Integration & Adapter Layer:**
- Purpose: Isolate external APIs/SDKs and format conversion concerns.
- Contains: LLM client abstraction, arXiv search/download/parsing, PDF-to-Markdown conversion, prompt loading.
- Location: `llm.py`, `arxiv.py`, `tools.py`.
- Depends on: OpenAI-compatible SDK, Gemini SDK, Docling, urllib/httpx.
- Used by: Orchestration and agent layers.

**Prompt & Knowledge Layer:**
- Purpose: Hold instruction contracts for each agent stage.
- Contains: YAML prompts mapped from legacy IDs (`1.txt`-`9.txt`).
- Location: `prompts/*.yaml` with mapping in `tools.py` (`PROMPT_NAME_MAPPING`).
- Depends on: None at runtime beyond file I/O.
- Used by: Agent `_build_context` methods.

**Persistence & Recovery Layer:**
- Purpose: Persist artifacts/logs and support session recovery after refresh/restart.
- Contains: Session folders, interaction logs, summary JSON, final rebuttal text, token usage export.
- Location: `gradio_uploads/<session_id>/`, especially `gradio_uploads/<session_id>/logs/`.
- Depends on: File system.
- Used by: `RebuttalService` create/save/restore methods and `app.py` resume flow.

## Data Flow

**Primary Flow (New Session to Final Rebuttal):**

1. User starts service with `python app.py --port 8080` (or `--device cuda`).
2. `app.py:start_analysis(...)` validates API key/files, initializes client via `init_llm_client(...)`, stores uploads in `gradio_uploads/<session_id>/`.
3. `rebuttal_service.py:RebuttalService.create_session(...)` creates session directories and initializes state/log collectors.
4. `app.py:run_initial_analysis(...)` calls `RebuttalService.run_initial_analysis(...)`:
5. PDF converted by `tools.py:pdf_to_md(...)`.
6. Agent1 summarizes paper, Agent2 extracts issues, Agent2Checker revises extraction.
7. `extract_review_questions(...)` materializes `QuestionState[]`.
8. `RebuttalService.process_all_questions_parallel(...)` runs per-question pipelines:
9. Agent3 decides retrieval strategy; arXiv queried via `arxiv.py:search_relevant_papers(...)` when needed.
10. Agent4 filters references; Agent5 analyzes each selected reference (parallel); Agent6 drafts strategy; Agent7 refines strategy.
11. UI shows strategy; user can revise via `app.py:regenerate_strategy(...)` -> `RebuttalService.revise_with_feedback(...)` (Agent7WithHumanFeedback).
12. User confirms/skip question via `app.py:confirm_and_next(...)` or `app.py:skip_question(...)`, which calls `RebuttalService.mark_question_satisfied(...)`.
13. After all questions satisfied, `RebuttalService.generate_final_rebuttal(...)` runs Agent8 then Agent9 and writes `final_rebuttal.txt`.
14. UI exposes final text and downloadable artifacts.

**Recovery Flow (Page Refresh / Resume):**

1. `app.py:refresh_session_list()` calls `RebuttalService.list_active_sessions()`.
2. Service restores from disk via `restore_sessions_from_disk()` and per-session `restore_session_from_disk()`.
3. State is reconstructed from `session_summary.json`, `interaction_q*.json`, `agent*_output.txt`, and `final_rebuttal.txt`.

**State Management:**
- In-memory source of truth: `RebuttalService.sessions` (guarded by `threading.Lock`).
- Durable state: `gradio_uploads/<session_id>/logs/session_summary.json` and related logs.
- Question state transitions: `NOT_STARTED -> PROCESSING -> WAITING_FEEDBACK -> COMPLETED` (or `ERROR`).

## Key Abstractions

**SessionState:**
- Purpose: End-to-end state container for one rebuttal run.
- Examples: `session_id`, file paths, `questions`, `progress_message`, `final_rebuttal`.
- Pattern: Dataclass state aggregate in `rebuttal_service.py`.

**QuestionState:**
- Purpose: Unit-of-work state for one extracted reviewer issue.
- Examples: `agent6_output`, `agent7_output`, `feedback_history`, `is_satisfied`.
- Pattern: Dataclass with mutable pipeline outputs.

**Agent Classes (Agent1-9 + HITL):**
- Purpose: Stage-local context building + single LLM execution responsibility.
- Examples: `Agent3.extract()`, `Agent7WithHumanFeedback.run()`.
- Pattern: Stateless-per-call worker objects instantiated per stage.

**LLMClient + TokenUsageTracker:**
- Purpose: Provider routing, retries/backoff, token accounting.
- Examples: `LLMClient.generate(...)`, `TokenUsageTracker.export_to_file(...)`.
- Pattern: Adapter + telemetry utility in `llm.py`.

**LogCollector:**
- Purpose: Thread-safe live log buffer for UI polling.
- Examples: `add(...)`, `get_recent(...)`.
- Pattern: In-memory ring-like collector with lock.

## Entry Points

**Application Entry:**
- Location: `app.py` (`if __name__ == "__main__":`).
- Triggers: CLI invocation (`python app.py ...`).
- Responsibilities: Parse args, launch Gradio app.

**Workflow Entry Handlers:**
- Location: `app.py:start_analysis(...)`, `app.py:run_initial_analysis(...)`, `app.py:confirm_and_next(...)`, `app.py:skip_question(...)`.
- Triggers: Gradio button events and chained callbacks.
- Responsibilities: Transition UI states and invoke service methods.

**Service Singleton Entry:**
- Location: `rebuttal_service.py` (`rebuttal_service = RebuttalService()`).
- Triggers: Imported and called from UI layer.
- Responsibilities: Session registry, orchestration, persistence.

## Error Handling

**Strategy:** Fail-fast within stage methods, bubble exceptions to UI handlers, convert to user-visible status messages.

**Patterns:**
- `try/except` in UI handlers returns friendly `gr.update(...)` error text rather than crashing UI.
- Service methods set `overall_status` or question `status` to `ERROR` on failures.
- Recovery is best-effort: missing logs/artifacts degrade gracefully with partial restoration.
- External calls use retries/backoff in `llm.py` and download retry logic in `tools.py`.

## Cross-Cutting Concerns

**Logging:**
- Runtime logs: `LogCollector` + `print(...)`.
- Persisted logs: `agent*_input.txt`, `agent*_output.txt`, `interaction_q*.json`, `session_summary.json`, `token_usage.json`.

**Validation:**
- Input validation in `app.py` for file/API key presence and custom model name.
- Parsing safeguards in `extract_review_questions(...)` and `extract_reference_paper_indices(...)`.

**Concurrency:**
- Question-level concurrency via `ThreadPoolExecutor` in `process_all_questions_parallel(...)`.
- Reference-level concurrency inside `process_single_question(...)` for Agent5.
- PDF conversion is serialized by `PDF_CONVERT_LOCK` in `tools.py`.

**Configuration:**
- Provider/model and env-key wiring in `app.py` + `llm.py`.
- Prompt indirection through `PROMPT_NAME_MAPPING` in `tools.py`.

---

*Architecture analysis: 2026-03-03*
*Update when major patterns change*
