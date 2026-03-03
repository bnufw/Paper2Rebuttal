# Coding Conventions

**Analysis Date:** 2026-03-03

## Naming Patterns

**Files:**
- Python entry/core modules使用简洁小写命名：`app.py`、`rebuttal_service.py`、`llm.py`、`arxiv.py`、`tools.py`。
- Prompt 文件采用阶段语义化 snake_case 命名：`prompts/semantic_encoder.yaml`、`prompts/issue_extractor.yaml`、`prompts/strategy_reviewer.yaml`。
- 静态资源放在独立目录，文件名直接表达用途：`assets/wechat_group.png`。

**Functions:**
- 函数统一使用 `snake_case`，并以动作开头：`app.py` 中的 `start_analysis`、`resume_session`，`rebuttal_service.py` 中的 `process_single_question`、`generate_final_rebuttal`。
- 解析/提取类函数使用 `extract_*` 前缀：`rebuttal_service.py` 中的 `extract_review_questions`、`extract_reference_paper_indices`。

**Variables:**
- 普通变量和实例属性使用 `snake_case`：`session_id`、`paper_summary`、`feedback_history`（见 `app.py`、`rebuttal_service.py`）。
- 模块级常量使用 `UPPER_SNAKE_CASE`：`SAVE_DIR`（`app.py`）、`SESSIONS_BASE_DIR` 与 `QUESTIONS_UPPER_BOUND`（`rebuttal_service.py`）、`PROVIDER_CONFIGS`（`llm.py`）。

**Types:**
- 类与数据结构使用 `PascalCase`：`LLMClient`（`llm.py`）、`ArxivAgent`（`arxiv.py`）、`RebuttalService`（`rebuttal_service.py`）。
- 状态枚举与 dataclass 使用显式类型：`ProcessStatus`、`QuestionState`、`SessionState`（`rebuttal_service.py`）。

## Code Style

**Formatting:**
- 采用 Python 常规风格（4 空格缩进、类型注解优先），基线规范来自 `AGENTS.md`。
- 代码中广泛使用类型标注与返回类型：`app.py`、`llm.py`、`arxiv.py`、`rebuttal_service.py`。
- 暂未检测到自动格式化配置文件；当前风格由现有代码与 `AGENTS.md` 约定驱动。

**Linting:**
- 暂未检测到仓库内静态检查配置；质量约束主要依赖人工规范文档 `AGENTS.md`。
- 合并前以可读性和一致性为主，遵循现有模块风格（`app.py`、`rebuttal_service.py`、`tools.py`）。

## Import Organization

**Order:**
1. 先导入标准库（如 `os`、`sys`、`json`、`time`），见 `app.py`、`llm.py`、`rebuttal_service.py`。
2. 再导入第三方库（如 `gradio`、`fastapi`、`openai`、`httpx`、`yaml`），见 `app.py`、`llm.py`、`tools.py`。
3. 最后导入项目内模块（如 `from rebuttal_service import ...`、`from arxiv import ...`），见 `app.py`、`rebuttal_service.py`、`tools.py`。

**Path Aliases:**
- 未使用路径别名；模块导入采用仓库根下直接模块名（`app.py`、`rebuttal_service.py`、`llm.py`、`arxiv.py`、`tools.py`）。

## Error Handling

**Patterns:**
- 输入验证失败时优先抛出显式异常：`app.py` 的上传解析流程会抛出 `ValueError`，`rebuttal_service.py` 会抛出 `ValueError`/`RuntimeError`。
- I/O 与外部调用大量使用 `try/except` 包裹，并在失败时返回降级结果（`None`/空字符串/空列表）：`tools.py`、`arxiv.py`、`rebuttal_service.py`。
- LLM 调用采用重试与指数退避：`llm.py` 的 `LLMClient.generate` 通过 `max_retries` + `retry_delay * 2^attempt` 处理瞬时失败。
- 会话级流程异常由状态字段承接：`rebuttal_service.py` 中 `session.overall_status` 与 `q_state.status` 在失败时切到 `ProcessStatus.ERROR`。

## Logging

**Framework:** console（`print`）+ 线程安全内存日志缓冲（`LogCollector`）。

**Patterns:**
- 控制台日志使用统一前缀标签：`[DEBUG]`、`[INFO]`、`[WARNING]`、`[ERROR]`（见 `tools.py`、`arxiv.py`、`llm.py`、`rebuttal_service.py`）。
- UI 侧实时日志通过 `LogCollector` + `gr.Timer` 轮询展示（`rebuttal_service.py`、`app.py`）。
- 关键中间产物落盘到 session logs 目录（如 `agent*_input.txt`、`agent*_output.txt`，写入逻辑在 `rebuttal_service.py`）。

## Comments

**When to Comment:**
- 对“非直观行为”给出简短注释：如环境变量兼容处理与设备初始化（`app.py`、`tools.py`）。
- 对核心流程节点给出说明性注释：如并行处理、恢复逻辑、交互日志持久化（`rebuttal_service.py`）。

**JSDoc/TSDoc:**
- 不适用（仓库为 Python）。
- Python docstring 使用“必要即写”策略，集中在公共函数与核心类方法：`tools.py`、`llm.py`、`rebuttal_service.py`。

## Function Design

**Size:**
- 采用“小工具函数 + 大编排函数”组合：工具函数在 `tools.py`/`arxiv.py`，编排函数在 `app.py` 与 `rebuttal_service.py`。
- UI 回调函数返回多组件更新元组（`app.py`），业务主链按阶段拆分为 `Agent1`~`Agent9`（`rebuttal_service.py`）。

**Parameters:**
- 多数函数有显式类型标注与默认值，便于调用方约束（`llm.py`、`arxiv.py`、`rebuttal_service.py`）。
- 进度回调统一采用可选回调参数：`progress_callback: Optional[Callable[[str], None]]`（`rebuttal_service.py`）。

**Return Values:**
- 失败可恢复场景返回 `Optional` 或空容器：`tools.py`、`arxiv.py`。
- 状态流转场景返回结构化对象或元组：`SessionState`/`QuestionState`（`rebuttal_service.py`），以及 Gradio `gr.update(...)` 元组（`app.py`）。

## Module Design

**Exports:**
- 模块级公开对象以“函数 + 类实例”为主：`rebuttal_service.py` 公开 `rebuttal_service = RebuttalService()`。
- `llm.py` 公开 `LLMClient` 与 `TokenUsageTracker`，供 `rebuttal_service.py` 组合使用。

**Barrel Files:**
- 未使用 barrel 文件；仓库采用扁平模块结构（`app.py`、`rebuttal_service.py`、`llm.py`、`arxiv.py`、`tools.py`）。

---

*Convention analysis: 2026-03-03*
