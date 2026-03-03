# Codebase Concerns

**Analysis Date:** 2026-03-03

## Tech Debt

**Monolithic workflow orchestration and UI coupling:**
- Issue: Core flow logic and UI/state handling are concentrated in very large files, making incremental changes risky and review cost high.
- Files: `app.py`, `rebuttal_service.py`
- Impact: Small feature changes can trigger regressions across upload, session restore, question processing, and final generation paths.
- Fix approach: Split orchestration into smaller modules (session lifecycle, question pipeline, output generation, UI handlers) with explicit interfaces.

**Global singleton runtime state:**
- Issue: LLM client and token tracker are process-global singletons rather than session-scoped dependencies.
- Files: `rebuttal_service.py`, `llm.py`
- Impact: Multi-user/multi-session behavior is non-isolated; config/logging can leak across sessions.
- Fix approach: Move to per-session service container; inject `LLMClient` and tracker into session objects.

**High repetition across agent wrappers:**
- Issue: Agent classes duplicate prompt building, logging, and invocation patterns with minimal abstraction.
- Files: `rebuttal_service.py`
- Impact: Fixes (logging format, retry policy, validation) require touching many places and are easy to miss.
- Fix approach: Introduce a shared agent base/helper for common `build → call → persist` behavior.

**Dead/unused state scaffolding:**
- Issue: Thread map is defined but unused.
- Files: `app.py`
- Impact: Increases maintenance noise and obscures actual concurrency model.
- Fix approach: Remove unused fields or implement and document intended lifecycle management.

## Known Bugs

**Error string treated as successful model output:**
- Symptoms: After retries fail, generation returns error text as normal output instead of raising.
- Files: `llm.py`, `rebuttal_service.py`
- Trigger: Provider/network failure, auth error, or repeated timeout.
- Workaround: Manually inspect logs for `"Error calling"` patterns; abort pipeline when detected.

**Question tag parsing is permissive and can mis-segment blocks:**
- Symptoms: Question extraction may merge/split content incorrectly when tag format deviates.
- Files: `rebuttal_service.py`
- Trigger: Non-standard Agent2/Checker output tags or repeated tag-like text.
- Workaround: Manually correct extracted questions in output logs before continuing.

**Rate-limit detector can false-trigger on normal content:**
- Symptoms: Responses containing generic words (for example “并发”) are treated as rate-limit errors and retried.
- Files: `llm.py`
- Trigger: Model response text includes configured keywords in non-error context.
- Workaround: Temporarily disable keyword-based detection and rely on provider exception/status parsing.

## Security Considerations

**Untrusted URL download path (SSRF/outbound abuse risk):**
- Risk: Agent-produced links are accepted and fetched without strict domain allowlist.
- Files: `rebuttal_service.py`, `tools.py`
- Current mitigation: Host classification only decides opener mode (`DIRECT_OPENER` vs `urlopen`), not trust.
- Recommendations: Enforce allowlist (`arxiv.org` only by default), block private IP ranges, require scheme/domain validation before fetch.

**Sensitive research content persisted in plaintext logs:**
- Risk: Full paper text, review text, prompts, and model outputs are written to session logs.
- Files: `rebuttal_service.py`, `app.py`
- Current mitigation: Runtime directories are git-ignored in `.gitignore`.
- Recommendations: Add configurable redaction/minimal logging mode, retention TTL, and explicit user consent for content persistence.

**Archive extraction hardening is incomplete:**
- Risk: Tar extraction uses a prefix check vulnerable to boundary confusion and does not reject link-type members.
- Files: `arxiv.py`
- Current mitigation: Uses absolute path prefix filter before `tar.extract`.
- Recommendations: Use strict path containment (`commonpath`), skip symlink/hardlink/device entries, and extract via safe member whitelist.

**Credential exposure risk in shared/public UI mode:**
- Risk: API key field is prefilled from environment and app supports public sharing.
- Files: `app.py`
- Current mitigation: Password textbox masks value on UI.
- Recommendations: Disable env-prefill when `--share` is enabled, add explicit warning/guard for remote deployment.

## Performance Bottlenecks

**PDF conversion serialization limits throughput:**
- Problem: Global lock serializes Docling conversion even when reference papers are processed in parallel.
- Files: `tools.py`, `rebuttal_service.py`
- Cause: `PDF_CONVERT_LOCK` wraps converter usage for all sessions/questions.
- Improvement path: Use bounded worker pool with converter instances per worker/process and explicit resource limits.

**Large synchronous I/O and in-memory buffering:**
- Problem: PDF downloads read full response into memory before validation/write.
- Files: `tools.py`, `arxiv.py`
- Cause: `resp.read()` pattern without streaming limits/chunk validation.
- Improvement path: Stream to disk in chunks with max-size guard and early abort for invalid content type.

**Frequent directory scans during session listing/restoration:**
- Problem: Active session listing repeatedly scans and hydrates disk state.
- Files: `rebuttal_service.py`, `app.py`
- Cause: `list_active_sessions()` invokes `restore_sessions_from_disk()` and iterates all session directories.
- Improvement path: Add cached index with mtime-based refresh and explicit refresh triggers.

## Fragile Areas

**Log-file-name-driven state restoration:**
- Files: `rebuttal_service.py`
- Why fragile: Restoration relies on regex and naming conventions of generated log files.
- Safe modification: Introduce versioned structured state schema; keep compatibility adapters for legacy logs.
- Test coverage: No automated regression tests for restoration permutations.

**JSON extraction from free-form LLM text:**
- Files: `rebuttal_service.py`, `tools.py`
- Why fragile: Uses `find('{')/rfind('}')` and escape patching heuristics that can break on nested braces or malformed payloads.
- Safe modification: Enforce strict JSON-only response format with schema validation and retry-on-parse-error contract.
- Test coverage: No parser fuzz tests for malformed/partial model outputs.

**Global stats mutation under parallel question processing:**
- Files: `llm.py`, `rebuttal_service.py`
- Why fragile: `TokenUsageTracker` mutates shared lists/counters without locks while multiple threads call `generate`.
- Safe modification: Add thread-safe tracker (`Lock`/queue) and session-scoped aggregation.
- Test coverage: No concurrency tests for counters/log file routing.

## Scaling Limits

**Session storage growth without lifecycle controls:**
- Current capacity: Session artifacts accumulate under one root directory with no cleanup routine.
- Limit: Disk usage grows unbounded and session listing/restore degrades over time.
- Scaling path: Add retention policy (TTL + max sessions), scheduled cleanup, and archive/export workflow.

**Single-process in-memory session registry:**
- Current capacity: Session state lives in process memory dictionary.
- Limit: Horizontal scaling and multi-instance consistency are not supported.
- Scaling path: Move session metadata/state to durable shared store (e.g., Redis/Postgres) with worker queue.

**Global provider client for all sessions:**
- Current capacity: One active client/config per process.
- Limit: Cross-session interference and weak tenant isolation under concurrent usage.
- Scaling path: Session-scoped clients with per-session credentials and request budget controls.

## Dependencies at Risk

**Partially unpinned dependency set:**
- Risk: `>=` constraints introduce non-deterministic behavior across environments.
- Impact: Runtime differences and subtle regressions after fresh installs.
- Migration plan: Pin all runtime dependencies and commit lockfile strategy for reproducible installs.

**Framework compatibility workaround indicates upgrade fragility:**
- Risk: Monkeypatching private Gradio internals for health routes may break on upstream updates.
- Impact: Broken startup/health behavior after dependency upgrades.
- Migration plan: Replace monkeypatch with supported Gradio/FastAPI configuration hooks.

## Missing Critical Features

**No authentication/authorization layer for web UI:**
- Problem: Any reachable user can trigger processing if service is exposed.
- Blocks: Safe shared deployment and multi-tenant usage.

**No strict upload/input safety controls:**
- Problem: Missing file size limits, content-type verification, and quota controls on user and fetched files.
- Blocks: Predictable resource usage and abuse resistance.

**No explicit cancellation/backpressure for long-running jobs:**
- Problem: Long pipelines run to completion without user-controlled cancellation or centralized queueing.
- Blocks: Reliable operation under burst workloads.

## Test Coverage Gaps

**Core parsers and extraction utilities:**
- What's not tested: Question extraction, selected-paper JSON extraction, JSON escape normalization, URL handling.
- Files: `rebuttal_service.py`, `tools.py`, `arxiv.py`
- Risk: Silent parsing drift can break downstream stages without immediate failure.
- Priority: High

**Session restore and state hydration paths:**
- What's not tested: Rebuild from partial logs, mixed HITL revisions, and corrupted JSON log recovery.
- Files: `rebuttal_service.py`
- Risk: Resume flow may produce incorrect UI state or lose prior work.
- Priority: High

**Concurrency and multi-session isolation:**
- What's not tested: Parallel question processing with shared trackers/clients and concurrent sessions.
- Files: `rebuttal_service.py`, `llm.py`, `app.py`
- Risk: Data races, mixed logs, and non-deterministic behavior under load.
- Priority: High

---

*Concerns audit: 2026-03-03*
