# Requirements: Personal Rebuttal Co-Pilot

**Defined:** 2026-03-03  
**Core Value:** Generate a complete, defensible reviewer-by-reviewer rebuttal package from user-provided markdown inputs, even when experiment evidence is partially missing.

## v1 Requirements

### Input & Parsing

- [ ] **INPT-01**: User can provide `paper.md` as primary paper input for the workflow.
- [ ] **INPT-02**: User can provide reviewer comments as markdown and the system can split them into reviewer-scoped issues.
- [ ] **INPT-03**: User can provide one or more comparison-paper markdown files for targeted differentiation analysis.
- [ ] **INPT-04**: System validates required markdown inputs and reports missing/invalid items before running generation.

### Experiment Planning

- [ ] **EXPT-01**: For each reviewer issue, system outputs required supplemental experiments with clear objective and rationale.
- [ ] **EXPT-02**: Each experiment suggestion includes step-by-step execution text that can be copied as prompt for third-party coding AI.
- [ ] **EXPT-03**: User can provide observed experiment results, and system can attach them to the corresponding reviewer issue.
- [ ] **EXPT-04**: If observed results are missing, system auto-generates synthetic results that remain consistent with original task/metric/model assumptions.
- [ ] **EXPT-05**: Every synthetic result is explicitly labeled as synthetic in intermediate and final outputs.

### Comparison Reasoning

- [ ] **COMP-01**: System links reviewer similarity/novelty concerns to relevant user-provided comparison papers.
- [ ] **COMP-02**: System generates structured differentiation points (similarities, differences, novelty angle) grounded in provided markdown evidence.
- [ ] **COMP-03**: System avoids unsupported superiority claims by tagging weakly supported claims for softer wording.

### Rebuttal Generation

- [ ] **RBTL-01**: System generates final responses in English, organized reviewer-by-reviewer.
- [ ] **RBTL-02**: Each reviewer response is constrained to <=5000 characters (including spaces and punctuation).
- [ ] **RBTL-03**: If a reviewer response exceeds 5000 characters, system iteratively compresses while preserving all key answer points.
- [ ] **RBTL-04**: Final rebuttal text includes explicit provenance markers where synthetic evidence is used.
- [ ] **RBTL-05**: System exports copy-ready rebuttal content with reviewer section boundaries preserved.

### Workflow & UX

- [ ] **FLOW-01**: User can run the full pipeline end-to-end in existing Gradio app without switching tools.
- [ ] **FLOW-02**: User can review and edit strategy/rebuttal drafts before final export.
- [ ] **FLOW-03**: Session artifacts are persisted and can be resumed.
- [ ] **FLOW-04**: System outputs a reusable experiment-plan artifact separate from final rebuttal text.

### Lightweight Compliance Checks

- [ ] **SAFE-01**: System blocks final export when a reviewer response exceeds 5000 characters.
- [ ] **SAFE-02**: System blocks final export when synthetic result labels are missing.
- [ ] **SAFE-03**: System validates required response structure per reviewer (issue -> response) before export.

## v2 Requirements

### Compliance & Iteration

- **SAFE-04**: System provides advanced compliance rewrite suggestions (tone/strength/style) beyond hard constraints.
- **FLOW-05**: System supports follow-up rebuttal round mode with evidence TODO tracking.
- **EXPT-06**: System proposes confidence scoring for synthetic-result reliability.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-user accounts and permissions | Project is explicitly personal-use only |
| Automatic web retrieval of comparison papers | User requires analysis based on user-provided comparison markdown files |
| One-click auto submission to OpenReview or conference systems | Keep human final approval and manual submission gate |
| Unlabeled fabricated evidence | Conflicts with explicit provenance requirement |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INPT-01 | Phase 1 | Pending |
| INPT-02 | Phase 1 | Pending |
| INPT-03 | Phase 2 | Pending |
| INPT-04 | Phase 1 | Pending |
| EXPT-01 | Phase 2 | Pending |
| EXPT-02 | Phase 2 | Pending |
| EXPT-03 | Phase 2 | Pending |
| EXPT-04 | Phase 2 | Pending |
| EXPT-05 | Phase 2 | Pending |
| COMP-01 | Phase 2 | Pending |
| COMP-02 | Phase 2 | Pending |
| COMP-03 | Phase 2 | Pending |
| RBTL-01 | Phase 2 | Pending |
| RBTL-02 | Phase 3 | Pending |
| RBTL-03 | Phase 3 | Pending |
| RBTL-04 | Phase 2 | Pending |
| RBTL-05 | Phase 3 | Pending |
| FLOW-01 | Phase 3 | Pending |
| FLOW-02 | Phase 2 | Pending |
| FLOW-03 | Phase 1 | Pending |
| FLOW-04 | Phase 2 | Pending |
| SAFE-01 | Phase 3 | Pending |
| SAFE-02 | Phase 3 | Pending |
| SAFE-03 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 24 total
- Mapped to phases: 24
- Unmapped: 0 ✅

---
*Requirements defined: 2026-03-03*  
*Last updated: 2026-03-03 after roadmap revision to 3 phases*
