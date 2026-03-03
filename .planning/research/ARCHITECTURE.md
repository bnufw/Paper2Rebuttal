# Architecture Research

**Domain:** 单用户 Gradio + Python 论文 Rebuttal 工作流扩展（MD-first）
**Researched:** 2026-03-03
**Confidence:** HIGH（代码事实 HIGH；架构演进建议含少量推断）

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ UI / Orchestration Layer (Gradio Blocks + 事件链)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │ Upload/Resume UI │  │ Interaction Loop │  │ Result/Download UI       │  │
│  │ app.py handlers  │  │ HITL revise      │  │ strategy/final rebuttal  │  │
│  └────────┬─────────┘  └────────┬─────────┘  └───────────┬──────────────┘  │
│           │                      │                        │                 │
├───────────┴──────────────────────┴────────────────────────┴─────────────────┤
│ Workflow Layer (Monolithic Service, stage-oriented)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ RebuttalService                                                       │  │
│  │ 1) MD Ingestion  2) Experiment Synthesis  3) Comparison Analysis     │  │
│  │ 4) Rebuttal Assembly (reuses existing Agent1-9 + new stage methods)  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────────┤
│ Data / Integration Layer                                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌───────────────────────────┐   │
│  │ gradio_uploads/ │  │ prompts/*.yaml  │  │ External: LLM/arXiv/docling│   │
│  │ logs+artifacts  │  │ stage contracts  │  │ llm.py, arxiv.py, tools.py│   │
│  └─────────────────┘  └─────────────────┘  └───────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `MDIngestion` | 统一读取 paper/review/对比论文 Markdown，生成规范化输入上下文 | `app.py:save_uploaded_files` + `tools.py:pdf_to_md` + `RebuttalService` 私有方法（建议） |
| `ExperimentSynthesis` | 基于 issue/question 生成实验补充计划；缺失结果时生成“显式标注”的 synthetic evidence | `RebuttalService` 新增 stage 方法，复用 `llm.py` 与 prompts |
| `ComparisonAnalysis` | 处理用户提供的 comparison papers Markdown，输出可引用的差异化论据 | `RebuttalService` 新增 stage 方法，输入为 comparison md 文本集合 |
| `RebuttalAssembly` | 按 reviewer 聚合策略、实验证据、对比结论，执行字符预算与标签合规 | `generate_final_rebuttal` 前插入装配步骤或替换为 reviewer-aware assembly |
| `SessionState/QuestionState` | 跨 stage 的单一事实源（状态、进度、中间产物） | 扩展 dataclass 字段并落盘到 `session_summary.json` |

## Recommended Project Structure

```
.
├── app.py                           # Gradio UI 和事件编排入口（保持不拆）
├── rebuttal_service.py              # 单体工作流协调器（核心）
├── llm.py                           # LLM provider 路由
├── tools.py                         # PDF->MD、prompt 加载、通用工具
├── arxiv.py                         # 文献检索（保留现有）
├── prompts/
│   ├── ...                          # 现有 Agent1-9 prompt
│   ├── experiment_synthesizer.yaml  # 新增：实验补充
│   ├── comparison_analyzer.yaml     # 新增：对比分析
│   └── rebuttal_assembler.yaml      # 新增：最终装配
└── gradio_uploads/<session_id>/
    ├── review.txt / paper.md / ...  # 输入与转换产物
    └── logs/                        # session_summary.json + agent*.txt + final_rebuttal.txt
```

### Structure Rationale

- **`rebuttal_service.py` 继续作为单体协调器：** 这是当前系统真实中心，新增 4 个边界优先作为内部 stage 方法实现，避免过早拆服务。
- **`prompts/` 作为边界契约层：** 新能力优先通过 prompt 文件增加，而不是引入额外进程或复杂中间件。
- **`gradio_uploads/<session_id>/logs` 作为事实落盘：** 复用现有恢复机制（`session_summary.json` + 日志），确保刷新/恢复不丢上下文。

## Architectural Patterns

### Pattern 1: Stage-Oriented Modular Monolith

**What:** 在单进程中按业务阶段切分（MD ingestion / experiment / comparison / assembly），每段有清晰输入输出。
**When to use:** 单用户、本地部署、快速迭代且已有单体代码时。
**Trade-offs:** 开发和调试成本低；但需要纪律来避免阶段间“任意读写”耦合。

**Example:**
```python
# rebuttal_service.py (示意)
def run_extended_pipeline(self, session_id: str):
    ctx = self._run_md_ingestion(session_id)
    exp = self._run_experiment_synthesis(ctx)
    cmp = self._run_comparison_analysis(ctx)
    return self._run_rebuttal_assembly(ctx, exp, cmp)
```

### Pattern 2: Canonical Context Contract (inference)

**What:** 用一个规范化上下文对象承接四段流水线，避免每段重复解析原始文本。
**When to use:** 同一会话要被多 agent、多轮 HITL 反复消费时。
**Trade-offs:** 前期需要设计字段；长期显著降低 prompt 漂移和重复解析错误。

**Example:**
```python
from dataclasses import dataclass

@dataclass
class PipelineContext:
    session_id: str
    paper_md: str
    review_md: str
    questions: list[str]
    comparison_papers_md: list[str]
```

### Pattern 3: Controlled Parallelism + Serialized Assembly

**What:** I/O 密集阶段并行（如参考论文处理），最终装配串行执行并做预算检查。
**When to use:** 存在多 reference/comparison 文档、但最终输出需要严格一致性时。
**Trade-offs:** 性能与稳定性平衡；并发过高会导致 LLM/API 限流和可追溯性下降。

**Example:**
```python
with ThreadPoolExecutor(max_workers=min(3, len(tasks))) as pool:
    partial = [f.result() for f in as_completed([pool.submit(fn, t) for t in tasks])]
final = assemble_and_validate(partial, char_limit=5000)
```

## Data Flow

### Request Flow

```
[User Upload .pdf/.md/.txt]
    ↓
[app.py:start_analysis]
    ↓
[save_uploaded_files + create_session]
    ↓
[RebuttalService.run_initial_analysis]
    ↓
[MD Ingestion] → [Question Extraction] → [Per-question Processing]
    ↓                            ↓
[Experiment Synthesis]      [Comparison Analysis]
    ↓                            ↓
[Rebuttal Assembly + reviewer char budget + synthetic labels]
    ↓
[final_rebuttal.txt + UI preview/download]
```

### State Management

```
[gr.State(session_id,current_idx)]
    ↓ (event callbacks)
[app.py handlers] ↔ [RebuttalService.sessions[session_id]]
    ↓                               ↓
[SessionState / QuestionState] → [session_summary.json + agent logs]
```

### Key Data Flows

1. **MD ingestion flow:** 上传文件 -> `paper.pdf/review.txt` -> `paper.md` -> `paper_summary/questions` -> `SessionState`。
2. **Experiment flow:** `question + paper context` -> experiment plan -> (可选) synthetic result（必须显式标签）-> assembly inputs。
3. **Comparison flow:** `comparison md files + reviewer concern` -> structured diffs/evidence bullets -> assembly inputs。
4. **Assembly flow:** `agent7 outputs + exp evidence + cmp evidence` -> per-reviewer draft -> budget/compliance pass -> final text。

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-10 并发会话（当前目标） | 保持单体；仅控制 `ThreadPoolExecutor` worker 上限，维持可调试性 |
| 10-100 并发会话 | 启用并调优 Gradio queue/concurrency；将重 I/O stage 做并发分组 |
| 100+ 并发会话 | 才考虑把 PDF 转换/长任务下沉到后台 worker（仍可先保持同仓库单体边界） |

### Scaling Priorities

1. **First bottleneck:** PDF 转换 + 多参考文档解析（I/O 和 CPU 混合） -> 先限制并发和任务批次。
2. **Second bottleneck:** LLM 调用速率与上下文长度 -> 分段摘要、缓存中间产物、装配阶段只消费结构化结果。

## Anti-Patterns

### Anti-Pattern 1: Premature Service Split

**What people do:** 在需求仍频繁变化时，把四个新边界直接拆成独立微服务。
**Why it's wrong:** 运维和通信开销先于业务价值出现，边界尚未稳定时会放大返工成本。
**Do this instead:** 先在 `RebuttalService` 内建立清晰 stage 边界，稳定后再决定是否抽离。

### Anti-Pattern 2: Stage I/O Drift

**What people do:** 每个阶段都直接读原始 markdown，自定义各自格式。
**Why it's wrong:** 会产生 prompt 契约漂移，恢复会话时难以重放和审计。
**Do this instead:** 维护统一 `PipelineContext` + 结构化中间结果，并落盘到 `session_summary.json`。

### Anti-Pattern 3: Unlabeled Synthetic Evidence

**What people do:** 生成补全实验结果但不加来源标签。
**Why it's wrong:** 违反可追溯性要求，最终 rebuttal 可能误导审稿人。
**Do this instead:** 在 `ExperimentSynthesis` 输出层强制 `evidence_type=synthetic|real`，装配时保留标签。

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| LLM providers | `llm.py::LLMClient.generate()` 统一调用 | 现有重试与 token 统计可直接复用 |
| arXiv | `arxiv.py::search_relevant_papers()` + `tools.download_pdf_and_convert_md()` | 仅在需要外部参考时触发 |
| Docling | `tools.pdf_to_md()` | 已有全局锁，适合单体串行/受控并发 |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `app.py` ↔ `RebuttalService` | 直接函数调用 + `gr.State` | 继续保持；不引入消息总线 |
| `RebuttalService` ↔ `tools.py` | 同进程函数调用 | 适合 ingestion/下载/转换 |
| `RebuttalService` ↔ `prompts/*.yaml` | `load_prompt()` | prompt 即阶段契约，便于迭代 |
| `SessionState` ↔ 磁盘日志 | JSON/TXT 文件 | 支撑恢复与审计，避免引入 DB 复杂度 |

## Build Order Implications (for this milestone)

1. **先做数据契约，再做能力扩展：** 先扩展 `SessionState/QuestionState` 和 `session_summary.json` 字段，确保后续 stage 可恢复。
2. **先落 MD ingestion 边界：** 将 `paper/review/comparison` 输入统一成 canonical context，这是后续三段的共同依赖。
3. **再接 experiment synthesis：** 输出结构化 evidence（含 synthetic 标签）并最小化侵入现有 Agent6/7。
4. **再接 comparison analysis：** 基于已标准化 context 读取 comparison md，输出可装配的差异化要点。
5. **最后改 rebuttal assembly：** 在 `generate_final_rebuttal` 前后加入 reviewer-level budget/compliance gate，降低回归风险。

## Sources

- 项目代码：`app.py`, `rebuttal_service.py`, `tools.py`, `llm.py`, `arxiv.py`（本仓库）
- Gradio Blocks 与事件流（官方）：https://www.gradio.app/guides/blocks-and-event-listeners
- Gradio State（官方）：https://www.gradio.app/main/guides/state-in-blocks
- Gradio Queuing（官方）：https://www.gradio.app/main/guides/queuing
- Gradio File 组件行为（官方）：https://www.gradio.app/main/docs/gradio/file
- Python 并发执行（官方）：https://docs.python.org/3.14/library/concurrent.futures.html
- Monolith First（Martin Fowler）：https://martinfowler.com/bliki/MonolithFirst.html
- AWS 单体分解指导（官方）：https://docs.aws.amazon.com/prescriptive-guidance/latest/modernization-decomposing-monoliths/welcome.html
- AWS Strangler Fig（官方）：https://docs.aws.amazon.com/prescriptive-guidance/latest/modernization-decomposing-monoliths/strangler-fig.html

---
*Architecture research for: MD-first rebuttal pipeline extension in current monolithic Gradio app*
*Researched: 2026-03-03*
