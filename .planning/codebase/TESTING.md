# Testing Patterns

**Analysis Date:** 2026-03-03

## Test Framework

**Runner:**
- 当前仓库未检测到自动化测试运行器配置；基线说明在 `AGENTS.md`（明确 `tests/` 当前不存在）。
- Config: Not detected（仓库根仅有依赖清单 `requirements.txt`，无独立测试配置文件）。

**Assertion Library:**
- Not detected（当前无自动化测试源码可归纳断言库）。

**Run Commands:**
```bash
python app.py --port 8080                 # 手工 smoke check（CPU）
python app.py --device cuda --port 8080   # 手工 smoke check（GPU）
# 自动化全量测试命令：Not detected
```
- 上述最小验证路径来自 `AGENTS.md` 与 `README.md`，并由入口脚本 `app.py` 实现。

## Test File Organization

**Location:**
- Not detected（当前仓库未包含 `tests/` 目录；证据来源 `AGENTS.md` 与仓库文件树）。

**Naming:**
- 若新增测试，约定使用 `test_*.py`（规范来源 `AGENTS.md`）。

**Structure:**
```text
Current state:
- No automated test files detected under repository root.
- Manual validation flows through `app.py` + `rebuttal_service.py`.
```

## Test Structure

**Suite Organization:**
```python
# Not detected (no committed test suites).
# Current quality gate is manual end-to-end flow:
# 1) Launch `app.py`
# 2) Upload PDF + review text
# 3) Complete strategy review and final rebuttal generation
```

**Patterns:**
- Setup pattern: 通过 `README.md` 初始化环境并启动 `app.py`。
- Teardown pattern: 手工重置会话（UI 按钮回调在 `app.py` 的 `restart_session`）。
- Assertion pattern: 人工核对 UI 状态、问题列表、策略生成与最终 rebuttal 输出（核心流程在 `rebuttal_service.py`）。

## Mocking

**Framework:**
- Not detected（当前仓库无 mocking 框架或测试基建代码）。

**Patterns:**
```python
# Not detected in committed tests.
# External boundaries that would require mocking when tests are added:
# - `LLMClient.generate` in `llm.py`
# - arXiv/network I/O in `arxiv.py` and `tools.py`
# - filesystem writes in `rebuttal_service.py`
```

**What to Mock:**
- 外部 API 与网络交互：`llm.py`、`arxiv.py`、`tools.py`。
- 会话落盘与日志写入：`rebuttal_service.py` 中 `session_summary.json`、`interaction_q*.json` 写路径。

**What NOT to Mock:**
- 纯文本/JSON 解析函数（如 `extract_review_questions`、`extract_reference_paper_indices`，位于 `rebuttal_service.py`）。
- 纯字符串处理函数（如 `_fix_json_escapes`，位于 `tools.py`）。

## Fixtures and Factories

**Test Data:**
```python
# Not detected (no fixture/factory modules committed).
# Runtime data directories are generated at execution time:
# - `gradio_uploads/`
# - `arxiv_papers/`
# - `arxiv_papers_md/`
# - `sessions/`
```

**Location:**
- 运行期产物目录由 `.gitignore` 排除，不作为版本化测试夹具。
- 输入样例依赖手工上传（流程在 `app.py` 的文件读取与保存逻辑）。

## Coverage

**Requirements:** None enforced（未检测到 coverage 门禁或阈值配置）。

**View Coverage:**
```bash
# Coverage command: Not detected in current repository.
```

## Test Types

**Unit Tests:**
- Not detected（无 `test_*.py` 文件）。

**Integration Tests:**
- Not detected（无自动化流程覆盖 `app.py` -> `rebuttal_service.py` 链路）。

**E2E Tests:**
- 采用人工 E2E：启动 `app.py`，完整走一轮上传、分析、反馈迭代、生成最终回复（依据 `AGENTS.md`、`README.md`）。

## Common Patterns

**Async Testing:**
```python
# Not detected in tests.
# Production code uses concurrency in `rebuttal_service.py`:
# - `ThreadPoolExecutor` for question-level parallelism
# - `ThreadPoolExecutor` for reference-paper parallel analysis
```

**Error Testing:**
```python
# Not detected in tests.
# Error branches are implemented in production code via:
# - explicit ValueError/RuntimeError raises (`app.py`, `rebuttal_service.py`)
# - broad try/except fallbacks (`tools.py`, `arxiv.py`, `llm.py`)
```

---

*Testing analysis: 2026-03-03*
