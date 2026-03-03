# Stack Research

**Domain:** 既有 rebuttal 系统增量改造（按 reviewer 输出 + 全局实验汇总 + 说服力优先）
**Researched:** 2026-03-03
**Confidence:** MEDIUM-HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | `>=3.10,<3.12` | 主运行时与多代理流程编排 | 现有代码与依赖（尤其 Docling）已在 3.10 验证；保持小范围升级可降低回归风险。 |
| Gradio | `>=6.2,<6.4` | 单人本地 UI（上传、逐 reviewer 展示、复制输出） | 当前 UI 已稳定可用；增量改造只需扩展结果面板与模式开关，无需重写前端。 |
| OpenAI SDK | `>=2.14,<3` | 统一 OpenAI-compatible / 多厂商 LLM 调用 | 现有 `llm.py` 已围绕该接口封装重试与统计，复用成本最低。 |
| Docling | `>=2.30,<2.32` | 论文 PDF 转 Markdown | 已接入现网流程，满足 rebuttal 场景信息抽取需求；无需替换文档解析引擎。 |
| Pydantic | `>=2.8,<3`（新增） | 结构化输出校验（reviewer 抽取、实验清单、合规检查报告） | 对“按 reviewer 输出 + 全局汇总”最关键：可把 LLM 自由文本约束为可验证对象，减少解析脆弱性。 |
| Python stdlib `dataclasses` + `enum` | Python 内置 | 运行态会话状态与流程状态机 | 现有 `SessionState/QuestionState/ProcessStatus` 已使用该范式；继续沿用能避免不必要迁移。 |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx[socks]` | `>=0.28,<0.29` | 统一网络层、超时/重试与代理支持 | 保持与当前 LLM 调用栈一致；仅在网络策略变化时调整。 |
| `PyYAML` | `>=6,<7` | prompt 配置读取 | 继续用于 ICML/OpenReview 新 prompts 与模式化提示词管理。 |
| `python-dotenv` | `>=1,<2` | 本地环境变量加载 | 单机运行与多 provider API key 管理仍是主路径。 |
| `unittest`（stdlib） | Python 内置 | 关键回归测试（schema、字符预算、合规扫描） | 当前仓库无测试基建，先用零依赖方案补关键测试。 |
| `pytest`（可选） | `>=8,<9` | 参数化/夹具增强测试体验 | 当测试规模扩大后再引入；不是本次里程碑硬依赖。 |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `pip-tools`（推荐） | 生成可复现锁定依赖 | 当前缺 lockfile；建议新增 `requirements.lock`，避免 `>=` 漂移。 |
| `ruff`（可选） | 快速静态检查与格式一致性 | 先用于新增模块（如合规扫描器）避免风格漂移。 |
| `mypy`（可选） | 强化结构化对象类型约束 | 当引入 Pydantic 模型后收益更大，适合逐步启用。 |

## Installation

```bash
# 基础（保持现有）
pip install -r requirements.txt

# 建议新增（结构化校验）
pip install "pydantic>=2.8,<3"

# 可选开发工具
pip install "pip-tools>=7,<8" "ruff>=0.6,<1" "mypy>=1.10,<2" "pytest>=8,<9"
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Pydantic v2 | 纯正则/手写 JSON 解析 | 仅在一次性脚本、无需长期维护时可接受；正式流程不建议。 |
| Gradio 增量扩展 | React + FastAPI 前后端分离 | 仅在明确转向多用户 SaaS、需要复杂权限与协作时考虑。 |
| 文件系统会话持久化 | SQLite/PostgreSQL | 当需要跨进程并发、审计检索或团队协作时再迁移。 |
| 现有 `llm.py` 统一网关 | 引入 LangChain/LlamaIndex | 仅在确有多工具编排/长期 RAG 平台化需求时考虑。 |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| 直接引入 Celery/Redis 任务队列 | 单机单人场景下运维复杂度远高于收益，且当前并发量可由线程池覆盖。 | 保持单进程 + `ThreadPoolExecutor`，先补可取消与超时控制。 |
| 在本里程碑重写为微服务架构 | 改造面过大，阻塞核心目标（reviewer 输出与说服力优化）落地。 | 保持分层单体，按模块拆分 `rebuttal_service.py`。 |
| 继续依赖“自由文本 + 正则”做关键解析 | 对 reviewer_id、实验清单等结构化字段极易误解析，回归风险高。 | 使用 Pydantic schema + 解析失败重试/回退策略。 |
| 全量依赖浮动版本（大量 `>=`） | 新环境安装结果不可复现，易出现线上线下行为不一致。 | 对运行时关键依赖给出上界并生成 lockfile。 |

## Stack Patterns by Variant

**If 目标是最快交付（当前里程碑默认）:**
- 保持 Python + Gradio + 现有 LLM 网关。
- 新增最小依赖：仅 `pydantic`。
- 因为该组合能最短路径支持“按 reviewer 输出 + 全局实验汇总”。

**If 后续扩展到高并发/多人协作:**
- 保留当前核心逻辑，外移会话状态到 SQLite/PostgreSQL，再考虑任务队列。
- 因为先稳定数据模型再扩容，能避免早期过度工程化。

**If 合规要求进一步提高（匿名/字数/证据审计）:**
- 强制“规则扫描（确定性）→ LLM 重写（受约束）→ 二次扫描”链路。
- 因为仅靠一次 LLM 生成无法稳定满足会议约束。

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `gradio>=6.2,<6.4` | `fastapi==0.128.x` | 与当前代码的健康检查 patch 方式保持一致，避免大版本破坏。 |
| `openai>=2.14,<3` | `httpx>=0.28,<0.29` | 维持现有 `llm.py` 调用签名与网络栈稳定。 |
| `pydantic>=2.8,<3` | `python>=3.10` | 支持 `BaseModel`/`TypeAdapter`，适合结构化输出校验。 |
| `docling>=2.30,<2.32` | `python>=3.10` + `DOCLING_DEVICE` 配置 | 与当前 PDF 转换流程和设备参数约定一致。 |

## Confidence Breakdown

| Area | Confidence | Reason |
|------|------------|--------|
| 保持现有核心栈（Python/Gradio/OpenAI/Docling） | HIGH | 与当前可运行系统完全一致，迁移风险最低。 |
| 引入 Pydantic 做结构化校验 | HIGH | 直接命中当前“自由文本解析脆弱”痛点，实施成本低。 |
| 版本范围上界设置 | MEDIUM | 基于现有仓库约束推导，未做跨版本完整回归。 |
| 可选工具（ruff/mypy/pytest） | MEDIUM | 对质量提升明确，但可按团队节奏分阶段引入。 |

## Sources

- `.planning/PROJECT.md` — 目标与约束（solo-first、reviewer 粒度、说服力优先、证据完整性）
- `.planning/codebase/STACK.md` — 现有依赖与运行环境基线
- `.planning/codebase/ARCHITECTURE.md` — 分层单体架构、并行处理与会话持久化现状
- `.planning/codebase/CONCERNS.md` — 解析脆弱性、依赖漂移与测试缺口
- `requirements.txt` — 当前版本锁定与浮动约束事实

---
*Stack research for: rebuttal 增量改造（reviewer 输出 + 全局实验汇总 + 说服力优先）*
*Researched: 2026-03-03*
