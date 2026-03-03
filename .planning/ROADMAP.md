# Roadmap: Personal Rebuttal Co-Pilot

## Overview

This roadmap extends the existing single-user Gradio rebuttal system with an MD-first workflow, evidence augmentation, reviewer-scoped drafting, and strict export compliance checks, while preserving current architecture and non-regressive behavior.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: MD Intake and Session Baseline** - Build the MD-first input path and resumable session foundation.
- [ ] **Phase 2: Evidence and Reviewer Draft Preparation** - Add experiment/comparison evidence generation and reviewer-scoped draft authoring.
- [ ] **Phase 3: Compliance Gating and Final Export** - Enforce per-reviewer constraints and release copy-ready final rebuttal.

## Phase Details

### Phase 1: MD Intake and Session Baseline
**Goal**: Users can start rebuttal work from markdown inputs and reliably resume sessions inside the existing Gradio app.
**Depends on**: Nothing (first phase)
**Requirements**: INPT-01, INPT-02, INPT-04, FLOW-03
**Success Criteria** (what must be TRUE):
  1. User can upload `paper.md` and reviewer markdown, then see reviewer-scoped issues parsed in the UI.
  2. User receives clear pre-run validation errors when required markdown inputs are missing or invalid.
  3. Session artifacts are persisted automatically and user can resume an interrupted session with prior state restored.
  4. User completes input-to-analysis handoff without leaving the current Gradio workflow.
**Plans**: TBD

### Phase 2: Evidence and Reviewer Draft Preparation
**Goal**: Users can generate issue-linked evidence and produce reviewer-by-reviewer English drafts with explicit provenance and human refinement.
**Depends on**: Phase 1
**Requirements**: INPT-03, EXPT-01, EXPT-02, EXPT-03, EXPT-04, EXPT-05, COMP-01, COMP-02, COMP-03, RBTL-01, RBTL-04, FLOW-02, FLOW-04
**Success Criteria** (what must be TRUE):
  1. User can upload one or more comparison-paper markdown files and see reviewer similarity/novelty concerns linked to relevant papers.
  2. For each reviewer issue, system outputs supplemental experiments with objective/rationale and step-by-step execution text that is prompt-ready for third-party coding AI.
  3. User can attach observed experiment results to the correct reviewer issue and see them included in generated evidence artifacts.
  4. When observed results are missing, system auto-generates setup-consistent synthetic results and explicitly labels them in intermediate outputs.
  5. System generates reviewer-by-reviewer English drafts with explicit synthetic-evidence provenance, and user can edit drafts before export.
  6. User receives a reusable experiment-plan artifact that is separate from final rebuttal text.
**Plans**: TBD

### Phase 3: Compliance Gating and Final Export
**Goal**: Users can complete full end-to-end pipeline execution and export compliant, copy-ready rebuttal text.
**Depends on**: Phase 2
**Requirements**: RBTL-02, RBTL-03, RBTL-05, FLOW-01, SAFE-01, SAFE-02, SAFE-03
**Success Criteria** (what must be TRUE):
  1. Every reviewer response is validated to be <=5000 characters before export.
  2. If any reviewer response exceeds 5000 characters, system iteratively compresses it while preserving key answer points.
  3. Export is blocked when any reviewer response still exceeds 5000 characters.
  4. Export is blocked when synthetic labels are missing or required reviewer issue->response structure is incomplete.
  5. User can run the full pipeline end-to-end in the existing Gradio app and obtain copy-ready rebuttal content with reviewer section boundaries preserved.
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. MD Intake and Session Baseline | 0/TBD | Not started | - |
| 2. Evidence and Reviewer Draft Preparation | 0/TBD | Not started | - |
| 3. Compliance Gating and Final Export | 0/TBD | Not started | - |
