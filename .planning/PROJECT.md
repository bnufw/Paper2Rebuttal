# Personal Rebuttal Co-Pilot

## What This Is

An internal, single-user rebuttal assistant for paper submission workflows.  
It extends the existing Gradio-based multi-agent system to run an MD-first rebuttal pipeline: experiment-gap planning, comparison-paper reasoning, and final rebuttal drafting per reviewer.  
The goal is to produce actionable and complete rebuttal artifacts with minimal manual stitching.

## Core Value

Generate a complete, defensible reviewer-by-reviewer rebuttal package from user-provided markdown inputs, even when experiment evidence is partially missing.

## Requirements

### Validated

- ✓ Browser-based workflow orchestration with staged rebuttal processing — existing Gradio app and callbacks
- ✓ Multi-agent rebuttal pipeline with per-question processing and final rebuttal synthesis — existing Agent1-9 flow
- ✓ Human-in-the-loop refinement loop for strategy updates — existing feedback/regenerate path
- ✓ Session artifact persistence and resume support — existing logs/session restoration
- ✓ Multi-provider LLM routing and token usage logging — existing provider abstraction

### Active

- [ ] Support MD-first input workflow for paper and reviewer comments as primary path for this feature set
- [ ] Produce supplemental experiment recommendations with concrete execution steps suitable as prompts for third-party coding AI
- [ ] Accept user-provided comparison-paper markdown files and generate focused differentiation arguments against reviewer similarity concerns
- [ ] Run end-to-end rebuttal flow that outputs reviewer-by-reviewer responses in English
- [ ] Enforce length budget at **per-reviewer** level: each reviewer response must be <=5000 characters (including spaces and punctuation)
- [ ] If experiment results are missing, auto-generate plausible synthetic results that remain consistent with the original paper setup (task/metrics/model boundaries)
- [ ] Explicitly label synthetic/generated results in outputs to avoid ambiguous provenance

### Out of Scope

- Multi-user accounts, authentication, and permission management — personal-use tool only
- Automatic retrieval of comparison papers from the web — user supplies comparison paper markdowns explicitly
- Unlabeled fabricated evidence in final text — conflicts with explicit provenance requirement

## Context

The repository already contains a working Gradio application (`app.py`) and a mature staged orchestration service (`rebuttal_service.py`) for rebuttal generation.  
Current system strengths include per-question strategy flow, optional literature retrieval, and resumable sessions.  
This initialization focuses on a new personal workflow centered on markdown inputs and stronger rebuttal packaging requirements: experiment augmentation guidance, comparison-driven argument quality, and strict per-reviewer character controls.

## Constraints

- **Usage Scope**: Single user only — no multi-tenant or auth design needed in v1
- **Interface**: Extend existing Gradio app — do not replace with CLI/API-first architecture
- **Input Source**: Comparison logic must rely on user-provided paper markdown files — no auto-search dependency
- **Output Language**: Final rebuttal output must default to English
- **Output Compliance**: Synthetic experiment results must be explicitly marked
- **Consistency**: Auto-generated results must stay inside original paper assumptions (task, metrics, model boundaries)
- **Non-Regressive Delivery**: New functionality must not break current rebuttal features

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Personal-use scope only | User explicitly targets solo workflow, not shared deployment | — Pending |
| Extend existing Gradio app | Fastest path using current architecture and UX | — Pending |
| Comparison analysis uses only user-provided markdown papers | User wants controlled evidence source and manual curation | — Pending |
| Final rebuttal language defaults to English | Directly aligned with conference submission needs | — Pending |
| Character budget enforced per reviewer (<=5000) | User selected per-reviewer constraint model | — Pending |
| Missing experiment results are auto-generated | User wants uninterrupted full rebuttal flow | — Pending |
| Synthetic results must be explicitly labeled | Prevents provenance ambiguity and misuse | — Pending |
| Synthetic results must be setup-consistent | Avoids contradictions with paper assumptions | — Pending |

---
*Last updated: 2026-03-03 after initialization*
