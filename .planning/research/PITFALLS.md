# Pitfalls Research

**Domain:** Subsequent extension of Personal Rebuttal Co-Pilot (MD-first, per-reviewer rebuttal, synthetic evidence handling)
**Researched:** 2026-03-03
**Confidence:** MEDIUM

## Critical Pitfalls

### Pitfall 1: Synthetic Result Provenance Collapse

**What goes wrong:**
Synthetic numbers are mixed with observed results in the same response, so readers cannot tell what is measured vs. generated.

**Why it happens:**
Generation prompts optimize for fluent rebuttal text; without a provenance schema, the model fills numeric gaps and writes them as factual results.

**How to avoid:**
Enforce structured provenance at generation time and render time:
- every numeric claim must carry `source_type` (`observed` or `synthetic`),
- synthetic claims must be explicitly labeled in text,
- any numeric claim without provenance metadata is blocked before final output.

**Warning signs:**
- Numeric claims appear without source pointer to input markdown or synthetic tag.
- Same metric appears once as factual and once as hypothetical with no distinction.
- Reviewer-facing text contains confident past-tense claims for missing experiments.

**Phase to address:**
Subsequent Phase 1: Provenance Contract and Output Labeling.

---

### Pitfall 2: Logical Drift from Original Paper Assumptions

**What goes wrong:**
Generated experiments or claims violate the original paper boundaries (task, dataset split, metrics, model family), creating internally inconsistent rebuttals.

**Why it happens:**
The pipeline uses broad prior knowledge; if paper assumptions are not extracted as hard constraints, generation drifts to common-but-inapplicable setups.

**How to avoid:**
Build an assumption profile from the paper markdown and validate all generated claims against it:
- allowed tasks/datasets/splits,
- allowed metrics and reporting style,
- allowed model scope and compute realism.
Reject or rewrite any out-of-bound claim.

**Warning signs:**
- New datasets/metrics appear that were never in paper context.
- Claimed improvements rely on baselines not used in the submission.
- Rebuttal text implies paper revisions that cannot happen during rebuttal period.

**Phase to address:**
Subsequent Phase 2: Assumption Extraction and Consistency Guard.

---

### Pitfall 3: Per-Reviewer Character Budget Breakage

**What goes wrong:**
Responses exceed venue limits or lose key answers after late truncation because budget is handled globally instead of per reviewer.

**Why it happens:**
Teams often count tokens or total response size, while venue constraints are usually per response field and character-based.

**How to avoid:**
Implement strict per-reviewer `len(text)` enforcement with iterative compression:
- validate each reviewer response independently,
- preserve mandatory answer coverage map (Q1/Q2/...),
- loop writer -> compressor -> validator until each response is compliant.

**Warning signs:**
- UI shows only one global length indicator.
- A compressed response passes length but drops explicit answers to some reviewer questions.
- Different char limits across venues are hard-coded as one constant.

**Phase to address:**
Subsequent Phase 3: Per-Reviewer Budget Engine and Compression Loop.

---

### Pitfall 4: Low-Quality Comparison Reasoning

**What goes wrong:**
Comparison arguments become weak or misleading (apples-to-oranges, cherry-picked baselines, unsupported superiority language), reducing rebuttal credibility.

**Why it happens:**
Similarity-only retrieval from user-provided comparison markdown encourages superficial overlap, not methodological comparability.

**How to avoid:**
Require a comparison quality rubric before drafting claims:
- explicit alignment matrix (task/data/split/metric/model setting),
- required mismatch caveats,
- claim strength policy (`supports`, `partially supports`, `cannot compare directly`),
- no superiority wording without matched conditions.

**Warning signs:**
- Phrases like “clearly outperforms” without matched setup evidence.
- Missing “limitations/mismatch” notes in comparison sections.
- Same comparison paper used as universal evidence for unrelated reviewer concerns.

**Phase to address:**
Subsequent Phase 4: Comparison Reasoning Quality Gate.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Store provenance only in free text | Fast implementation | Cannot reliably audit synthetic vs observed claims | Never |
| One-shot truncation when over 5000 chars | Quick pass of length check | Drops critical Q/A coverage and creates reviewer-specific regressions | Never |
| Skip assumption profile extraction | Less parsing logic | High risk of out-of-bound claims and contradiction with submission | Only for internal dry-run drafts |
| Compare papers by keyword overlap only | Faster comparison stage | Weak, non-defensible reasoning and cherry-pick bias | Never for final rebuttal |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| OpenReview/venue rebuttal forms | Assume one universal rebuttal limit for all venues and all response types | Read current venue instructions and enforce per-field, per-reviewer limits in pipeline config |
| LLM provider clients | Treat token count as equivalent to character count | Keep token budgeting for cost, but enforce venue compliance with final character count check |
| Markdown ingestion for paper/comparison docs | Assume section headers are standardized | Add robust parsing fallbacks and explicit extraction diagnostics for assumptions/metrics |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full-context regeneration for every compression retry | Latency spikes during over-limit fixes | Reuse intermediate drafts and apply targeted compression prompts | >3 reviewers with long multi-point responses |
| Pairwise comparison against all papers for every reviewer question | Slow turnaround and noisy evidence | Pre-index comparison papers by assumption match, then rerank per question | >8 comparison papers per submission |
| Re-validating whole session after tiny edits | UI feels stalled during HITL iteration | Incremental validation by reviewer and changed section only | Frequent human revision cycles |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Leaking reviewer identifiers or private comments in logs/artifacts | De-anonymization and policy violations | Redact sensitive fields in persisted logs and exports by default |
| Allowing external links in final rebuttal text | Accidental identity leakage or policy non-compliance | Add compliance scan to block URLs unless venue explicitly allows |
| Mixing raw reviewer text with synthetic tags in uncontrolled exports | Evidence provenance confusion in shared files | Export separate structured evidence ledger with immutable source labels |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Only one combined rebuttal preview | User cannot see which reviewer is over budget or under-answered | Show per-reviewer cards with char count and coverage status |
| Synthetic evidence labels are subtle or inconsistent | User may submit ambiguous fabricated claims by accident | Use explicit, uniform synthetic markers and a pre-submit warning banner |
| Comparison caveats hidden behind collapsible details | User over-trusts weak comparisons | Surface mismatch caveats inline next to each comparison claim |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Synthetic evidence support:** Often missing machine-readable provenance — verify every numeric claim has `source_type` and source pointer.
- [ ] **Assumption consistency:** Often missing hard-boundary validation — verify no out-of-scope dataset/metric/model claims.
- [ ] **Per-reviewer compliance:** Often missing independent length checks — verify each reviewer response is `<= 5000` chars and complete.
- [ ] **Comparison quality:** Often missing mismatch disclosure — verify each claim includes comparability status and caveat when needed.
- [ ] **Submission compliance:** Often missing venue-specific guardrails — verify no forbidden links and no impossible “already revised PDF” claims.

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Synthetic Result Provenance Collapse | MEDIUM | Freeze release, run provenance backfill for all numeric claims, relabel synthetic content, regenerate only ambiguous sections |
| Logical Drift from Original Paper Assumptions | HIGH | Recompute assumption profile, auto-flag violations, rewrite conflicting sections, rerun consistency validation before publish |
| Per-Reviewer Character Budget Breakage | LOW | Trigger targeted compression per reviewer, preserve must-answer checklist, rerun char and coverage validators |
| Low-Quality Comparison Reasoning | MEDIUM | Rebuild comparison matrix, downgrade unsupported claims, add explicit mismatch caveats, regenerate reasoning paragraphs |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Synthetic Result Provenance Collapse | Subsequent Phase 1: Provenance Contract and Output Labeling | Random audit: every numeric claim resolves to observed or synthetic ledger entry |
| Logical Drift from Original Paper Assumptions | Subsequent Phase 2: Assumption Extraction and Consistency Guard | Constraint tests reject out-of-bound task/dataset/metric/model claims |
| Per-Reviewer Character Budget Breakage | Subsequent Phase 3: Per-Reviewer Budget Engine and Compression Loop | Automated check confirms each reviewer response `<= 5000` and all required Q/A anchors present |
| Low-Quality Comparison Reasoning | Subsequent Phase 4: Comparison Reasoning Quality Gate | Quality rubric pass: comparability matrix present, unsupported superiority claims blocked |

## Sources

- Internal project constraints: `.planning/PROJECT.md` (2026-03-03 snapshot)
- OpenReview docs, Rebuttal Stage: https://docs.openreview.net/reference/stages/rebuttal-stage
- ICML 2025 Reviewer Instructions (5000-char rebuttal/reply workflow details): https://icml.cc/Conferences/2025/ReviewerInstructions
- ICML 2025 Author Instructions (author response constraints): https://icml.cc/Conferences/2025/AuthorInstructions
- NeurIPS Paper Checklist Guidelines (claims/assumptions/limitations transparency): https://neurips.cc/public/guides/PaperChecklist
- Guidelines for Research Data Integrity (Scientific Data, 2025): https://www.nature.com/articles/s41597-024-04312-x
- ACM Artifact Review and Badging (reproducibility and evidence traceability): https://www.acm.org/publications/policies/artifact-review-and-badging-current

---
*Pitfalls research for: Personal Rebuttal Co-Pilot subsequent extension*
*Researched: 2026-03-03*
