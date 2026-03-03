# Phase 1: MD Intake and Session Baseline - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 delivers an MD-first intake flow and reliable resume baseline inside the existing Gradio app. Scope is limited to `paper.md` + reviewer markdown intake, pre-run validation, reviewer-scoped issue extraction handoff, and session persistence/resume continuity.

Out of scope for this phase: experiment planning, comparison-paper reasoning, and final compliance/export controls.

</domain>

<decisions>
## Implementation Decisions

### MD Input Contract
- Primary paper input is strictly `paper.md` (required).
- Reviewer input is a single `review.md` file with reviewer sections.
- Canonical filenames are required: `paper.md` and `review.md`.
- Legacy non-MD inputs (`.pdf`, `.txt`) are rejected in Phase 1.
- Rejection must include clear corrective guidance telling the user exactly which markdown files are required.

### Claude's Discretion
- Exact reviewer-section header grammar in `review.md` (for example, accepted header variants) as long as reviewer-scoped issue extraction remains reliable.
- Exact wording style for validation errors (tone/format), while preserving actionable fix steps.
- Whether to provide lightweight migration hints for converting legacy files to markdown.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app.py:save_uploaded_files(...)`: Existing upload normalization and file persistence path that can be adapted from PDF/TXT handling to MD handling.
- `app.py:start_analysis(...)`: Existing pre-run guardrails and status-return pattern for validation failures.
- `rebuttal_service.py:run_initial_analysis(...)`: Existing initial pipeline handoff point where intake contract changes should plug in.
- `rebuttal_service.py:_save_session_summary(...)` and restore helpers: Existing persistence contract for resumable sessions.
- `rebuttal_service.py:extract_review_questions(...)`: Existing parser contract for question extraction output shape.

### Established Patterns
- Gradio UI event chaining pattern in `app.py` (`start_btn.click(...).then(...)`) should remain unchanged structurally.
- Session durability is filesystem-based under `gradio_uploads/<session_id>/logs/` with `session_summary.json` as primary resume artifact.
- Resume flow already routes through `list_active_sessions()` + `restore_session_from_disk()` and should stay compatible.

### Integration Points
- Upload controls in `app.py` currently define `paper.pdf` + `review(.md/.txt)` and need to switch to markdown-first contract.
- Intake validation in `start_analysis(...)` should enforce required markdown file presence and canonical filenames.
- Initial analysis path in `rebuttal_service.py` currently converts PDF to MD; Phase 1 should start directly from provided `paper.md`.
- Resume path should continue using existing summary/log artifacts without introducing external storage.

</code_context>

<specifics>
## Specific Ideas

No brand/reference-style requirements were specified. Priority is a strict, deterministic MD contract with clear user-facing correction guidance.

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope.

</deferred>

---

*Phase: 01-md-intake-and-session-baseline*
*Context gathered: 2026-03-03*
