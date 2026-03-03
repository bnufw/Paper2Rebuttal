# Codebase Concerns

**Analysis Date:** 2026-03-03

## Tech Debt

**Global runtime singletons shared by all sessions:**
- Issue: `LLMClient` and `TokenUsageTracker` are process-global and reconfigured per request.
- Files: `rebuttal_service.py:24`, `rebuttal_service.py:26`, `rebuttal_service.py:29`, `rebuttal_service.py:924`, `rebuttal_service.py:1180`, `app.py:261`, `app.py:665`
- Why: Fastest way to wire provider switching into a single-process Gradio app.
- Impact: Concurrent sessions can overwrite each other's provider/model/token log destination; cross-session behavior is non-deterministic.
- Fix approach: Move LLM client and token tracker into `SessionState`, inject per-session dependencies into agents.

**Question pipeline is a monolithic method with mixed concerns:**
- Issue: `process_single_question` handles retrieval strategy, external fetch, file conversion, paper analysis, and generation in one long function.
- Files: `rebuttal_service.py:1307`, `rebuttal_service.py:1404`, `rebuttal_service.py:1462`
- Why: Iterative feature growth in one orchestration path.
- Impact: Hard to test in isolation, hard to retry partially, and regressions are easy when changing one stage.
- Fix approach: Split into stage functions (`retrieve_refs`, `analyze_refs`, `generate_strategy`) and persist stage outputs.

**Private framework API monkey-patch:**
- Issue: Gradio internals are patched directly.
- Files: `app.py:34`, `app.py:37`
- Why: Quick workaround for route behavior.
- Impact: Minor Gradio upgrades can break startup or silently change health-route behavior.
- Fix approach: Replace with supported Gradio/FastAPI configuration hooks.

**UI callback contracts are tuple-position heavy:**
- Issue: Multiple callbacks return long positional tuples tied to output wiring order.
- Files: `app.py:1284`, `app.py:1310`, `app.py:1342`, `app.py:1354`
- Why: Native Gradio callback style used without response DTO abstraction.
- Impact: Any output list change can silently misroute values to wrong components.
- Fix approach: Consolidate per-page state objects and reduce callback output width.

## Known Bugs

**Resuming a completed session does not repopulate result content:**
- Symptoms: Result page may open after resume, but strategy/final rebuttal content is missing from UI components.
- Trigger: Resume a session where all questions are already marked satisfied.
- Files: `app.py:707`, `app.py:709`, `app.py:711`, `app.py:1310`
- Workaround: Re-generate final rebuttal in a live session flow instead of relying on completed-session resume UI.
- Root cause: `resume_session` computes `strategy_summary`/`final_text` but callback outputs for resume path do not include result text components.

**LLM hard failure is propagated as normal text payload:**
- Symptoms: Downstream stages continue with strings like `Error calling ...`, causing parse failures or low-quality outputs instead of fast-fail.
- Trigger: Provider/network/auth/rate-limit failure after retries.
- Files: `llm.py:211`, `rebuttal_service.py:1277`, `rebuttal_service.py:1341`, `rebuttal_service.py:1383`
- Workaround: Manually inspect logs and rerun the full session.
- Root cause: `generate()` returns error text instead of raising typed exceptions; callers mostly treat return values as valid model outputs.

## Security Considerations

**Raw sensitive content persisted to disk without redaction:**
- Risk: Uploaded paper/review text and user feedback are written verbatim to local logs and summaries.
- Files: `rebuttal_service.py:150`, `rebuttal_service.py:192`, `rebuttal_service.py:278`, `rebuttal_service.py:535`, `rebuttal_service.py:1116`, `rebuttal_service.py:1162`
- Current mitigation: Session isolation by directory only (`gradio_uploads/<session_id>/...`).
- Recommendations: Add redaction/sanitization policy, configurable log level, and optional no-persist mode for sensitive runs.

**Model-provided links are fetched without domain allowlist:**
- Risk: SSRF-like outbound requests or unexpected internal endpoint probing via untrusted URLs.
- Files: `rebuttal_service.py:1345`, `rebuttal_service.py:1351`, `tools.py:207`, `tools.py:241`, `tools.py:254`
- Current mitigation: Basic retry/timeouts only.
- Recommendations: Enforce allowlist (`arxiv.org`, known conference domains), block private IP ranges, validate URL schemes.

**Tar extraction safety check is weak against prefix collisions/special entries:**
- Risk: Archive extraction can still be unsafe for crafted entries (path-prefix and link edge cases).
- Files: `arxiv.py:405`, `arxiv.py:412`, `arxiv.py:415`
- Current mitigation: `startswith` path check and exception swallowing.
- Recommendations: Use robust path normalization with separator boundary checks and reject symlink/hardlink members explicitly.

**API keys prefilled into browser UI from environment:**
- Risk: Keys are pushed into front-end state (password-masked but still present client-side).
- Files: `app.py:973`, `app.py:977`, `app.py:985`, `app.py:993`
- Current mitigation: Password textbox masking.
- Recommendations: Prefer server-only secret selection or one-time token handoff instead of key prefill.

## Performance Bottlenecks

**Global PDF conversion lock serializes all sessions:**
- Problem: Only one Docling conversion can run at a time.
- Files: `tools.py:27`, `tools.py:81`, `tools.py:85`
- Measurement: End-to-end workflow is documented as up to ~1 hour on CPU and ~15 minutes on GPU.
- Measurement source: `README.md:108`, `README.md:109`, `README.md:110`
- Cause: Single shared converter and global lock.
- Improvement path: Per-session conversion queue with bounded workers, or separate conversion service process.

**Nested concurrency amplifies API pressure and latency variance:**
- Problem: Question-level parallelism plus per-question reference parallelism can create bursty outbound load.
- Files: `rebuttal_service.py:1560`, `rebuttal_service.py:1599`, `rebuttal_service.py:1447`
- Measurement: Current caps are `max_workers=3` (questions) and `max_workers_ref<=3` (references), with exponential retries.
- Files: `app.py:305`, `rebuttal_service.py:1445`, `llm.py:204`
- Cause: Parallel fan-out without global rate limiter/backpressure.
- Improvement path: Add provider-aware request budgeting and shared concurrency semaphore.

**Repeated large text reads inflate token and CPU cost:**
- Problem: Each reference read can load up to 150,000 chars; original paper is re-read for each question.
- Files: `rebuttal_service.py:1419`, `rebuttal_service.py:1463`, `rebuttal_service.py:1508`
- Measurement: Hard cap per reference read is 150k chars.
- Cause: No content cache by file hash/stage.
- Improvement path: Cache parsed/cropped content in session artifacts and reuse across agents.

## Fragile Areas

**LLM JSON parsing relies on first/last brace slicing:**
- Why fragile: Non-JSON preambles, trailing braces, or markdown examples can break parsing.
- Files: `rebuttal_service.py:297`, `rebuttal_service.py:304`, `rebuttal_service.py:698`, `rebuttal_service.py:702`
- Common failures: `need_search` false negatives, empty selected paper indices.
- Safe modification: Switch to strict JSON response mode where supported and validate with schema.
- Test coverage: No parser-focused tests found (`tests/` missing).

**Session restoration depends on filename conventions and regex heuristics:**
- Why fragile: Restore logic infers state from log filenames and partial artifacts.
- Files: `rebuttal_service.py:742`, `rebuttal_service.py:753`, `rebuttal_service.py:771`, `rebuttal_service.py:913`
- Common failures: Incomplete restore after interrupted runs or renamed/missing files.
- Safe modification: Persist explicit stage/state checkpoints rather than reconstructing from side effects.
- Test coverage: No restore-flow regression tests present.

**Shared session progress fields are written by parallel workers:**
- Why fragile: Multiple threads update `session.progress_message` and statuses without consistent locking discipline.
- Files: `rebuttal_service.py:1325`, `rebuttal_service.py:1500`, `rebuttal_service.py:1572`
- Common failures: Out-of-order progress messages and confusing UI status.
- Safe modification: Make per-question progress channels and aggregate in a synchronized reducer.
- Test coverage: No concurrent behavior tests.

## Scaling Limits

**Session storage grows unbounded in memory and disk:**
- Current capacity: No explicit limit; all sessions kept in `self.sessions` and persisted under `gradio_uploads/`.
- Files: `rebuttal_service.py:716`, `rebuttal_service.py:1048`, `rebuttal_service.py:1172`
- Limit: Long-lived processes can accumulate large memory/disk usage.
- Symptoms at limit: Slow startup restore, larger I/O overhead, storage pressure.
- Scaling path: Add retention policy, LRU eviction, and background cleanup.

**Process-global provider state limits safe multi-tenant concurrency:**
- Current capacity: Effectively one active runtime config for `llm_client`/`token_tracker` globals.
- Files: `rebuttal_service.py:24`, `rebuttal_service.py:26`, `rebuttal_service.py:1180`
- Limit: Concurrent sessions with different providers or keys can conflict.
- Symptoms at limit: Wrong token logs, provider switching side effects.
- Scaling path: Per-session dependency containers and immutable runtime context.

**No cancellation/backpressure for long-running pipelines:**
- Current capacity: Tasks run to completion once started.
- Files: `app.py:1284`, `app.py:1292`, `rebuttal_service.py:1560`
- Limit: Stuck tasks occupy worker threads and API budget.
- Symptoms at limit: Perceived UI freeze and prolonged retries.
- Scaling path: Add cancellable jobs, queueing, and timeout-aware stage checkpoints.

## Dependencies at Risk

**Partially unpinned dependencies reduce reproducibility:**
- Risk: `>=` constraints can introduce behavioral drift across environments.
- Files: `requirements.txt:7`, `requirements.txt:8`, `requirements.txt:9`, `requirements.txt:10`
- Impact: Non-deterministic runtime differences and harder incident reproduction.
- Migration plan: Pin exact versions for runtime-critical packages and add periodic controlled upgrade windows.

**Optional external tool path changes behavior:**
- Risk: Conversion path differs when `pandoc` is present vs absent.
- Files: `arxiv.py:319`, `arxiv.py:343`
- Impact: Output quality and speed vary by host, causing inconsistent reference analysis quality.
- Migration plan: Standardize one conversion backend or explicitly require `pandoc` in runtime docs.

**Docling/HF bootstrap dependency is heavy and environment-sensitive:**
- Risk: First-run model/material download can fail or stall in restricted networks.
- Files: `tools.py:88`, `README.md:124`
- Impact: Initial user run failures and long cold-start latency.
- Migration plan: Provide preflight dependency check and warm-up command before serving UI.

## Missing Critical Features

**No robust output-compliance guardrail despite high-risk prompt behavior:**
- Problem: Prompt rules explicitly encourage invented numeric placeholders, while UI warning is passive.
- Files: `prompts/rebuttal_writer.yaml:24`, `prompts/rebuttal_reviewer.yaml:24`, `app.py:1215`
- Current workaround: Manual user review of asterisk-marked values.
- Blocks: Safe deployment in settings requiring strict non-fabrication policy.
- Implementation complexity: Medium (post-generation compliance scanner + hard fail/repair loop).

**No artifact lifecycle management for generated files:**
- Problem: Temp downloads and per-session files are not auto-cleaned.
- Files: `app.py:1380`, `app.py:1395`, `rebuttal_service.py:1172`
- Current workaround: Manual filesystem cleanup.
- Blocks: Long-running service stability and predictable storage usage.
- Implementation complexity: Low-Medium (TTL cleanup job + explicit delete on session close).

**No user-facing cancel/retry control at stage granularity:**
- Problem: Users cannot cancel a bad run or retry a failed stage only.
- Files: `app.py:1284`, `app.py:1292`, `rebuttal_service.py:1251`, `rebuttal_service.py:1560`
- Current workaround: Restart whole session.
- Blocks: Efficient recovery from transient provider/network failures.
- Implementation complexity: Medium (job state machine + interrupt flags).

## Test Coverage Gaps

**No automated test suite in repository:**
- What's not tested: Core flows, parser robustness, session restore, and concurrency behavior.
- Evidence: `tests/` directory absent.
- Risk: Regressions in callback wiring and restore logic can ship unnoticed.
- Priority: High
- Difficulty to test: Medium (needs fixture sessions and mocked LLM/arXiv I/O).

**High-risk parsing and restore paths are unverified:**
- What's not tested: `extract_review_questions`, `extract_reference_paper_indices`, and log-based restore/hydration.
- Files: `rebuttal_service.py:648`, `rebuttal_service.py:697`, `rebuttal_service.py:861`, `rebuttal_service.py:913`
- Risk: Small prompt/output format drift can break pipeline silently.
- Priority: High
- Difficulty to test: Medium (requires malformed output fixtures and interrupted-run fixtures).

**Concurrency behavior lacks stress coverage:**
- What's not tested: Parallel question processing with shared session fields and global singletons.
- Files: `rebuttal_service.py:1560`, `rebuttal_service.py:1599`, `rebuttal_service.py:24`, `rebuttal_service.py:26`
- Risk: Race conditions and cross-session interference under real usage.
- Priority: High
- Difficulty to test: Medium-High (needs controlled multi-thread integration tests).

---

*Concerns audit: 2026-03-03*
*Update as issues are fixed or new ones discovered*
