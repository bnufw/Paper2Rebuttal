# Feature Research

**Domain:** Personal rebuttal co-pilot (single-user internal extension)
**Researched:** 2026-03-03
**Confidence:** MEDIUM
**Milestone Context:** subsequent

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| MD-first input workflow (`paper.md` + `review.md`) | Project scope is explicitly MD-first, and users want less manual conversion friction | MEDIUM | Reuse existing upload/session flow in `app.py` + `RebuttalService.create_session`; add format detection and light validation |
| Per-reviewer extraction and rebuttal output | OpenReview-style workflows are reviewer-threaded, not single monolithic letters | HIGH | Requires adding reviewer ID ownership in issue extraction/state (`QuestionState` extension) and new per-reviewer generation path |
| Per-reviewer character budget enforcement (`<=5000`) | Rebuttal forms commonly enforce bounded text fields; hard limits are operational constraints | MEDIUM | Add char-budget utility loop after generation (`len()` + compressor retry); show counter in UI; dependency: per-reviewer generation first |
| Human-in-the-loop revise/regenerate before finalization | Existing product already establishes review-and-revise expectations | LOW | Already supported by `revise_with_feedback`; keep behavior and expose reviewer-level regenerate entry points |
| Session persistence + downloadable artifacts | Long rebuttal iterations require pause/resume and auditability | LOW | Already present in `gradio_uploads/<session>/logs`; extend exports to include reviewer-level outputs and provenance notes |
| Explicit provenance labeling for non-observed evidence | Required by project constraints to avoid ambiguous or misleading claims | MEDIUM | Add output schema tags like `[SYNTHETIC]`/`[OBSERVED]`; dependency: final assembly step and prompt contract updates |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Experiment-gap planner producing executable AI prompts | Converts reviewer criticism into concrete next-step experiment plans instead of vague advice | MEDIUM | Build on existing Agent6/7 strategy outputs; add structured sections (goal, steps, expected artifact, risk) |
| Comparison-paper markdown reasoning (user-supplied only) | Directly addresses “novelty/similarity” attacks with targeted differentiation arguments | HIGH | Requires ingesting multiple comparison markdowns and mapping evidence to each reviewer issue; no auto-web crawl by design |
| Consistency-guarded synthetic result drafting with explicit labels | Keeps flow unblocked when results are missing while preserving provenance clarity | HIGH | Needs rule checks against task/metric/model boundaries from source paper; add clear generated-evidence markers in final text |
| Compliance guard (anonymity/link/tense checks) before export | Reduces submission risk for rebuttal-phase policy violations | MEDIUM | Rule-based scan + optional rewrite pass; dependency: per-reviewer draft + char budget pass |
| Reviewer follow-up reply mode + minimal evidence TODO list | Supports post-rebuttal discussion rounds with faster turnaround | MEDIUM | New mode in UI/service, reusing reviewer-specific context and budget utilities |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Multi-user accounts and role permissions | Teams may ask for shared workspace by default | Out of scope for this project; large auth/session/security overhead for little single-user value | Keep single-user local workflow; export markdown/text artifacts for async collaboration |
| Auto-crawling and auto-selecting comparison papers from the web | Feels “more automated” | Violates current constraint (user-curated comparison inputs), increases relevance/hallucination risk | Keep user-provided comparison markdown as source of truth; add import checklist for quality |
| One-click posting to OpenReview | Seems to reduce manual work | High blast radius on mistakes; policy/compliance risk if wrong thread/content posted | Keep human copy-paste final gate with checklist and per-reviewer packaged output |
| Real-time collaborative editor in Gradio | Familiar from docs platforms | Significant UI/state complexity for limited internal usage | Keep concise single-user editor + iteration history |
| Always-on internet retrieval for every question | Perceived as “more intelligent” | Cost, latency, and unstable evidence quality; conflicts with deterministic internal workflow | Use optional retrieval only when reviewer issue explicitly needs external support |

## Feature Dependencies

```
[MD-first input workflow]
    └──requires──> [Reviewer-aware extraction]
                       └──requires──> [Per-reviewer rebuttal generation]
                                              └──requires──> [Per-reviewer 5000-char enforcement]
                                                                   └──requires──> [Compliance guard + export packaging]

[Experiment-gap planner] ──enhances──> [Per-reviewer rebuttal generation]
[Comparison-paper reasoning] ──enhances──> [Per-reviewer rebuttal generation]
[Provenance labeling] ──requires──> [Per-reviewer rebuttal generation]

[Auto web-crawled comparison papers] ──conflicts──> [User-provided comparison markdown constraint]
[Multi-user auth/collab] ──conflicts──> [Single-user internal tool scope]
```

### Dependency Notes

- **Reviewer-aware extraction requires MD-first input workflow:** reviewer IDs and question boundaries must be parsed from stable text inputs first.
- **Per-reviewer generation requires reviewer-aware extraction:** generation units are reviewer-scoped, so question ownership must already exist.
- **5000-char enforcement requires per-reviewer generation:** budget checks only make sense after reviewer-level drafts are produced.
- **Compliance guard depends on post-generation text:** anonymity/link/tense checks need concrete final drafts to scan and rewrite.
- **Experiment-gap planner enhances per-reviewer generation:** planned experiments provide stronger evidence strategy blocks per reviewer concern.
- **Comparison-paper reasoning enhances per-reviewer generation:** differentiation arguments become specific instead of generic claims.
- **Auto-crawled comparison papers conflict with current product constraint:** project explicitly requires user-supplied comparison markdown, not auto retrieval.
- **Multi-user auth conflicts with scope:** this milestone is intentionally single-user and should avoid tenant/security expansion.

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the concept.

- [ ] MD-first input workflow for paper/review files — core entry path defined in `PROJECT.md`
- [ ] Reviewer-aware extraction and reviewer-by-reviewer final output — core value is rebuttal package per reviewer
- [ ] Per-reviewer `<=5000` character budget enforcement — hard operational requirement
- [ ] Experiment-gap planning output as executable steps/prompts — required utility for missing evidence workflows
- [ ] Comparison-paper markdown ingestion and differentiation synthesis — required response quality uplift
- [ ] Provenance labeling for generated/synthetic evidence — required compliance/clarity boundary

### Add After Validation (v1.x)

Features to add once core is working.

- [ ] Compliance auto-rewriter with violation report (URL/anonymity/tense) — add when basic generation quality is stable
- [ ] Reviewer follow-up reply mode with `[[TBD: ...]]` evidence checklist — add when first-round rebuttal flow is stable
- [ ] One-click export bundle (`reviewer_responses.md`, `strategy_todos.md`, `compliance_report.md`) — add after users confirm artifact format preference

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] Optional OpenReview API-assisted draft sync (not auto-submit) — defer due policy and failure-risk surface
- [ ] Venue-specific rule packs (ICML/NeurIPS/ICLR presets) — defer until recurring multi-venue usage is validated
- [ ] Personal evidence memory/index across past rebuttals — defer until enough historical sessions exist to justify maintenance

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| MD-first input workflow | HIGH | MEDIUM | P1 |
| Reviewer-aware extraction + per-reviewer output | HIGH | HIGH | P1 |
| Per-reviewer `<=5000` budget enforcement | HIGH | MEDIUM | P1 |
| Comparison-paper markdown reasoning | HIGH | HIGH | P1 |
| Experiment-gap planner (actionable prompts) | HIGH | MEDIUM | P1 |
| Provenance labeling for synthetic evidence | HIGH | MEDIUM | P1 |
| Compliance guard and auto-rewrite | MEDIUM | MEDIUM | P2 |
| Follow-up reply mode + evidence TODOs | MEDIUM | MEDIUM | P2 |
| OpenReview API-assisted sync | LOW | HIGH | P3 |
| Multi-user collaboration/auth | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Competitor A | Competitor B | Our Approach |
|---------|--------------|--------------|--------------|
| Per-reviewer rebuttal workflow | OpenReview supports rebuttal stage configuration (including one rebuttal per review), but not strategy generation | Paperpal focuses on general academic writing and editing support, not reviewer-threaded rebuttal orchestration | Native reviewer-by-reviewer pipeline with extraction, strategy, drafting, and export |
| Character-constrained response drafting | OpenReview forms can enforce max-length fields, but drafting/compression is manual | Paperpal/Trinka provide writing help, not conference-response hard-limit optimization | Automatic per-reviewer budget enforcement with rewrite/compression loop |
| Experiment-gap-to-action conversion | OpenReview does not provide experiment planning | Paperpal/Trinka provide language and productivity features, not rebuttal experiment planning | Structured experiment plan blocks tailored to each reviewer claim |
| Compliance/anonymity guardrails | OpenReview provides workflow/form configuration, but not proactive text-level policy rewrites for user drafts | General writing assistants do not target venue-specific rebuttal compliance | Add focused pre-export checks for links, identity leakage, and rebuttal-phase wording |

## Sources

- Project scope and requirements: `.planning/PROJECT.md`
- Existing capability baseline: `README.md`, `rebuttal_service.py` (`run_initial_analysis`, `revise_with_feedback`, `generate_final_rebuttal`, `create_session`)
- OpenReview docs:  
  - https://docs.openreview.net/reference/stages/rebuttal-stage  
  - https://docs.openreview.net/reference/default-forms/default-comment-form  
  - https://docs.openreview.net/getting-started/customizing-forms
- Academic writing assistant references:  
  - https://www.web.paperpal.com/  
  - https://support.paperpal.com/support/solutions/articles/3000126445-what-all-can-paperpal-be-used-for-  
  - https://www.trinka.ai/features

---
*Feature research for: personal rebuttal co-pilot extension*
*Researched: 2026-03-03*
