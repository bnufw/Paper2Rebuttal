# Project Research Summary

**Project:** Personal Rebuttal Co-Pilot  
**Domain:** Single-user, MD-first rebuttal workflow extension in existing Gradio/Python app  
**Researched:** 2026-03-03  
**Confidence:** MEDIUM-HIGH

## Executive Summary

The research converges on an incremental extension strategy: keep the current monolithic Gradio + `RebuttalService` architecture, add stage boundaries inside existing files, and avoid framework/service rewrites. The proposed stack is conservative (`Python 3.10`, existing Gradio/Docling/OpenAI-compatible routing), with focused additions (`pydantic`, `markdown-it-py`) to make intermediate artifacts structured and auditable.

Roadmap-critical capability is reviewer-by-reviewer generation under hard character limits, not a single global rebuttal. The required launch set is MD-first ingestion, reviewer-aware extraction/output, per-reviewer `<=5000` budget enforcement, experiment-gap planning, comparison-paper reasoning from user-supplied markdown only, and explicit provenance labels for synthetic evidence.

Main delivery risks are also clear and already mapped to phases: provenance collapse (synthetic vs observed ambiguity), logical drift outside paper assumptions, reviewer-level budget breakage, and weak comparison logic. Mitigation requires contract-first data design, assumption/profile validation, iterative compression with coverage checks, and comparison quality gates before final assembly/export.

## Key Findings

### 1. Recommended Stack (from `STACK.md`)

- Keep existing runtime and orchestration baseline:
  - `Python 3.10`, current `Gradio` Blocks architecture, existing `rebuttal_service.py`/`llm.py` flow.
  - `Docling` remains fallback (PDF -> Markdown), not the primary path.
- Add only two core dependencies for this milestone:
  - `pydantic>=2.8,<3` for strict structured validation of LLM outputs and stage artifacts.
  - `markdown-it-py>=3.0,<4` for heading/list/code-aware markdown parsing (paper/review/comparison inputs).
- Enforce reviewer limits by deterministic character counting (`len()`), with retry compression loop; token counts remain cost/perf signals only.

### 2. Feature Priorities and Dependencies (from `FEATURES.md`)

**P1 launch scope (must-have):**
- MD-first input workflow.
- Reviewer-aware extraction + per-reviewer output.
- Per-reviewer `<=5000` character enforcement.
- Experiment-gap planner.
- Comparison-paper markdown reasoning (user-provided only).
- Synthetic/observed provenance labeling.

**P2 (after core flow is stable):**
- Compliance auto-rewrite/reporting.
- Follow-up reply mode + evidence TODOs.

**P3 (defer):**
- OpenReview API-assisted sync.
- Multi-user auth/collaboration.

**Dependency backbone:**
`MD-first ingestion -> reviewer-aware extraction -> per-reviewer generation -> per-reviewer budget/compliance/export`, with experiment/comparison/provenance enhancing generation quality and safety.

### 3. Architecture Direction (from `ARCHITECTURE.md`)

- Keep a stage-oriented modular monolith inside current structure; do not split services now.
- Build around a canonical context/state contract (`SessionState/QuestionState` extensions + persisted `session_summary.json` fields).
- Introduce/expand four stage boundaries in `RebuttalService`:
  1. `MDIngestion`
  2. `ExperimentSynthesis`
  3. `ComparisonAnalysis`
  4. `RebuttalAssembly` (with reviewer budget/compliance checks)
- Preserve current boundaries: `app.py <-> RebuttalService`, prompt contracts in `prompts/*.yaml`, and filesystem logs as recoverable fact source.

### 4. Critical Pitfalls (from `PITFALLS.md`)

1. **Synthetic Result Provenance Collapse**  
   Prevent with machine-readable provenance contract (`source_type`), mandatory explicit labels, and block untagged numeric claims.
2. **Logical Drift from Paper Assumptions**  
   Prevent with assumption profile extraction (task/dataset/metric/model bounds) and out-of-bound rejection/rewrites.
3. **Per-Reviewer Character Budget Breakage**  
   Prevent with strict per-reviewer char validation plus iterative compression that preserves answer coverage.
4. **Low-Quality Comparison Reasoning**  
   Prevent with comparability matrix, mismatch caveats, and claim-strength policy (no unsupported superiority wording).

## Roadmap Implications

### Phase 1: Data Contract + MD Ingestion Foundation
**Rationale:** Architecture and dependencies both require a canonical context before adding new generation stages.  
**Delivers:** `SessionState/QuestionState` field extensions, `session_summary.json` contract updates, normalized MD-first ingestion path (Docling as fallback), reviewer-boundary extraction inputs.  
**Addresses:** Stage I/O drift risk; establishes prerequisites for all P1 features.

### Phase 2: Provenance + Assumption Guardrails
**Rationale:** Pitfalls research marks provenance collapse and logical drift as high-impact early failures; guardrails should precede broad generation expansion.  
**Delivers:** Structured provenance schema (`observed/synthetic`), numeric-claim validation gates, assumption profile extraction and consistency checks.  
**Addresses:** Pitfall 1 and Pitfall 2 directly.

### Phase 3: Reviewer-Aware Generation Core (Experiment + Comparison)
**Rationale:** After contracts and guardrails are stable, implement the main value layer that feeds reviewer-specific drafts.  
**Delivers:** Per-reviewer generation path, experiment-gap planner outputs, comparison-paper markdown reasoning mapped to reviewer issues.  
**Uses:** `pydantic` artifact validation + `markdown-it-py` parsing on MD inputs.

### Phase 4: Rebuttal Assembly, Budget Engine, and Export Compliance
**Rationale:** Final assembly should come after evidence-producing stages to minimize regressions and enforce policy at the actual output boundary.  
**Delivers:** Reviewer-level assembly, iterative `<=5000` character compression/validation loop, coverage checks, explicit provenance rendering, packaged exports.  
**Addresses:** Pitfall 3 and final submission quality controls.

### Phase 5: Post-MVP Enhancements (P2)
**Rationale:** Only after launch-path stability is proven.  
**Delivers:** Compliance auto-rewriter/report, follow-up reply mode with evidence TODO scaffolding.  
**Defers:** OpenReview API sync and multi-user features (P3).

## Phase Ordering Rationale

- Contract-first ordering is required by both architecture build-order guidance and feature dependency chain.
- Guardrails (provenance + assumptions) are placed before full generation expansion to reduce expensive downstream rewrites.
- Experiment/comparison generation precedes assembly because assembly is a consumer/gate layer, not the source of evidence.
- Budget/compliance enforcement is late-bound at reviewer output stage, matching venue constraints and minimizing false passes.
- Deferred items match explicit research prioritization (P2/P3) and avoid scope expansion (multi-user, auto-web retrieval, direct auto-submit flows).

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Conservative extension of current stack; only two new libs; strong fit to existing architecture. |
| Features | MEDIUM | Priority and dependency map is clear, but several P1 items are high complexity (reviewer-aware flow, comparison reasoning). |
| Architecture | HIGH | Strongly grounded in current code boundaries and explicit build-order implications. |
| Pitfalls | MEDIUM | Risk patterns are concrete and actionable, but effectiveness depends on implementation quality of validators/gates. |

**Overall confidence:** MEDIUM-HIGH

## Recommended Immediate Priorities

1. Define and freeze the canonical session/question/provenance schema before any new prompt-stage rollout.
2. Implement MD-first normalization and reviewer-aware extraction scaffolding in the existing session flow.
3. Add provenance + assumption validators early, then gate all numeric and scope-sensitive claims through them.
4. Implement per-reviewer assembly with iterative character-budget enforcement and coverage checks.
5. Keep P2/P3 features out of launch scope until P1 flow passes end-to-end smoke checks.

## Grounding Sources

- `.planning/research/STACK.md`
- `.planning/research/FEATURES.md`
- `.planning/research/ARCHITECTURE.md`
- `.planning/research/PITFALLS.md`
- `./.codex/get-shit-done/templates/research-project/SUMMARY.md`

---
*Research synthesis completed: 2026-03-03*  
*Ready for roadmap creation: yes*
