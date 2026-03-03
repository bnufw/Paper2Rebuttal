# Testing Patterns

**Analysis Date:** 2026-03-03

## Test Framework

**Runner:**
- No automated test runner is configured in the current repo.
- `requirements.txt` does not include `pytest`, `unittest` plugins, `coverage`, or CI test tooling.
- No test config file exists (`pytest.ini`, `pyproject.toml`, `tox.ini`, `setup.cfg` are absent).

**Assertion Library:**
- No in-repo assertion style exists yet because there are no committed automated tests.

**Run Commands (Current Manual Validation):**
```bash
python app.py --port 8080                 # Local smoke test on CPU
python app.py --device cuda --port 8080   # Local smoke test with CUDA Docling
```

**Run Commands (If Adding `pytest` Later):**
```bash
pytest
pytest path/to/test_file.py
pytest path/to/test_file.py::test_name
pytest -k "keyword"
pytest -x
```

## Test File Organization

**Location (Current State):**
- No `tests/` directory in repository root.
- No files matching `test_*.py` or `*_test.py` are present.

**Naming (Documented Expectation):**
- `AGENTS.md` specifies `test_*.py` naming when tests are added.

**Current Directory Reality:**
```
/home/zhu/code/Paper2Rebuttal/
  app.py
  rebuttal_service.py
  llm.py
  arxiv.py
  tools.py
  prompts/
  (no tests/ tree)
```

## Test Structure

**Existing Pattern:**
- There is no established automated test suite structure (`describe`/`class Test...`/fixture conventions are not yet defined).
- Quality is currently validated via full-flow manual run in `app.py`.

**Practical Structure to Introduce (Compatible with Current Repo):**
```python
# tests/test_rebuttal_service.py

def test_extract_review_questions_basic():
    text = "..."
    questions, num = extract_review_questions(text)
    assert isinstance(questions, list)
```

## Mocking

**Current State:**
- No mocking framework is in use because no automated tests are present.

**Practical Guidance for This Codebase:**
- Mock external boundaries first: LLM calls (`llm.py`), network calls (`arxiv.py`, `tools.py`), filesystem-heavy conversion (`tools.py`).
- Keep core parsing/transformation logic unmocked where possible (`extract_review_questions`, JSON extraction helpers).

## Fixtures and Factories

**Current State:**
- No shared fixtures/factories directory exists.

**Practical Starting Point:**
- Add small inline fixtures per file first.
- Introduce `tests/fixtures/` only when duplicate test data appears across multiple modules.

## Coverage

**Requirements:**
- No coverage target is defined.
- No enforcement mechanism exists in CI (no CI workflow found in repo).

**Configuration:**
- No coverage config files detected.

## Test Types

**Manual Smoke Test (Current Primary Pattern):**
1. Run `python app.py --port 8080`.
2. Upload a sample paper and review file through the Gradio UI.
3. Verify initial analysis runs (`Agent1`/`Agent2`), question-by-question processing works, and final rebuttal generation completes.
4. Validate generated session artifacts under `gradio_uploads/`.

**Unit Tests (Not Yet Present):**
- Best first targets: deterministic pure logic in `rebuttal_service.py`, `tools.py`, and `arxiv.py` parsing helpers.

**Integration Tests (Not Yet Present):**
- Next targets: `RebuttalService` session lifecycle with mocked LLM/network boundaries.

## Common Patterns

**Async/Parallel Behavior to Consider in Tests:**
- `ThreadPoolExecutor` is used in `rebuttal_service.py` and `tools.py`; tests should avoid depending on completion order unless explicitly sorted.

**Error Handling to Cover First:**
- Invalid JSON / parse fallback paths in `rebuttal_service.py`.
- Download/convert fallback-to-markdown behavior in `tools.py` and `arxiv.py`.
- Missing session / index boundary checks in `RebuttalService` methods.

## Evidence Sources (Repository)

- Testing policy guidance: `AGENTS.md`
- Manual run commands and workflow: `README.md`, `app.py`
- Current dependency surface: `requirements.txt`
- Runtime behavior needing tests: `rebuttal_service.py`, `tools.py`, `arxiv.py`, `llm.py`

---

*Testing analysis: 2026-03-03*
*Update when test patterns change*
