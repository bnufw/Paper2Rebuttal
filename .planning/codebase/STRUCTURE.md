# Codebase Structure

**Analysis Date:** 2026-03-03

## Directory Layout

```text
`Paper2Rebuttal`/
├── `app.py`                  # Gradio 入口与事件编排
├── `rebuttal_service.py`     # 核心会话状态与多代理流程
├── `llm.py`                  # 多提供商 LLM 网关与 token 统计
├── `arxiv.py`                # arXiv 检索、下载与文献转换
├── `tools.py`                # PDF 转 Markdown、prompt 加载与通用工具
├── `prompts/`                # 各代理阶段 YAML 提示词
├── `assets/`                 # 静态资源（如图片）
├── `.planning/codebase/`     # 代码库映射文档输出目录
├── `.env.example`            # 环境变量模板
├── `requirements.txt`        # Python 依赖清单
└── `README.md`               # 项目说明与使用流程
```

## Directory Purposes

**`prompts/`:**
- Purpose: 存放代理阶段的提示词模板，驱动 `Agent1` 到 `Agent9` 的行为。
- Contains: `*.yaml` 提示词文件。
- Key files: `prompts/semantic_encoder.yaml`, `prompts/issue_extractor.yaml`, `prompts/literature_retrieval.yaml`, `prompts/strategy_human_refinement.yaml`, `prompts/rebuttal_writer.yaml`.

**`assets/`:**
- Purpose: 存放 UI/文档展示使用的静态资源。
- Contains: 图片等静态文件。
- Key files: `assets/wechat_group.png`.

**`.planning/codebase/`:**
- Purpose: 存放代码映射阶段输出（供后续规划与执行代理消费）。
- Contains: 架构、结构、规范、测试、风险等分析文档。
- Key files: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`.

**`.codex/`:**
- Purpose: 本地代理工作流与 skill 配置目录（开发辅助，不属于应用运行核心）。
- Contains: 代理定义、workflow 模板、skills。
- Key files: `.codex/agents/gsd-codebase-mapper.md`, `.codex/skills/`.

## Key File Locations

**Entry Points:**
- `app.py`: Web 应用主入口，定义 `gr.Blocks` 并在 `__main__` 中调用 `demo.launch(...)`。
- `rebuttal_service.py`: 服务单例入口（`rebuttal_service = RebuttalService()`）及主流程调度。

**Configuration:**
- `requirements.txt`: 运行依赖（`gradio`, `fastapi`, `openai`, `docling` 等）。
- `.env.example`: API key 与 base URL 模板。
- `.gitignore`: 运行产物与敏感文件忽略规则（如 `gradio_uploads/`, `.env`, `.codex`）。
- `AGENTS.md`: 仓库级开发与协作规范。

**Core Logic:**
- `rebuttal_service.py`: 状态模型、9 阶段代理、并行处理、会话恢复、最终生成。
- `llm.py`: 提供商路由、统一 `generate()` 调用、重试与 token 统计。
- `arxiv.py`: arXiv Atom API 检索、PDF/源码下载、摘要/Markdown回退。
- `tools.py`: `pdf_to_md`, `download_pdf_and_convert_md`, `load_prompt`, `_fix_json_escapes`。

**Testing:**
- `tests/`: Not detected。
- `test_*.py`: Not detected。

## Naming Conventions

**Files:**
- `snake_case.py`: Python 模块命名（示例：`rebuttal_service.py`, `arxiv.py`）。
- `lower_snake_case.yaml`: prompt 文件命名（示例：`strategy_generator.yaml`）。
- `UPPERCASE.md`: 规划输出文档命名（示例：`.planning/codebase/ARCHITECTURE.md`）。

**Directories:**
- 功能分区目录命名为简短小写（示例：`prompts/`, `assets/`）。
- 规划与代理目录使用前缀隐藏目录（示例：`.planning/`, `.codex/`）。

## Where to Add New Code

**New Feature:**
- Primary code: 将工作流阶段逻辑放在 `rebuttal_service.py`，UI交互放在 `app.py`。
- Tests: 新建 `tests/` 并使用 `test_*.py`（当前仓库未检测到现有测试目录）。

**New Component/Module:**
- Implementation: 新的外部集成优先放在独立模块（如 `llm.py` / `arxiv.py` 风格），并由 `rebuttal_service.py` 统一编排。
- Prompt support: 新阶段提示词放在 `prompts/`，并在 `tools.py` 的 `PROMPT_NAME_MAPPING` 中登记映射。

**Utilities:**
- Shared helpers: 可复用通用逻辑优先加入 `tools.py`，避免在 `app.py` 与 `rebuttal_service.py` 重复实现。

## Special Directories

**`gradio_uploads/`:**
- Purpose: 运行期会话目录，存储上传文件、日志与恢复元数据。
- Generated: Yes
- Committed: No

**`arxiv_papers/` / `arxiv_papers_md/`:**
- Purpose: 文献下载与转换产物目录（由检索流程生成）。
- Generated: Yes
- Committed: No

**`sessions/`:**
- Purpose: 历史运行会话产物目录（兼容性或旧流程产物）。
- Generated: Yes
- Committed: No

**`.codex/`:**
- Purpose: 本地代理与 skill 运行配置目录。
- Generated: Yes
- Committed: No

---

*Structure analysis: 2026-03-03*
