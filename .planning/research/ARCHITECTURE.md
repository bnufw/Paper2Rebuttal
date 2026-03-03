# Architecture Patterns

**Domain:** 论文 Rebuttal 多代理编排（按 reviewer 输出 + 全局实验汇总）  
**Researched:** 2026-03-03  
**Confidence:** HIGH（现状映射）/ MEDIUM（演进方案）

## Recommended Architecture

### System Overview

```text
┌────────────────────────────── Presentation Layer ──────────────────────────────┐
│ Gradio UI                                                                       │
│ - 上传与启动  - 问题逐条确认  - Reviewer 输出面板（新增）  - 实验汇总面板（新增） │
└───────────────────────┬───────────────────────────────┬───────────────────────┘
                        │                               │
                        ▼                               ▼
┌────────────────────── Application Orchestration Layer ─────────────────────────┐
│ RebuttalService                                                                 │
│ - run_initial_analysis                                                          │
│ - process_all_questions_parallel                                                │
│ - compose_reviewer_outputs (new)                                                │
│ - synthesize_global_experiments (new)                                           │
└───────────────────────┬───────────────────────────────┬───────────────────────┘
                        │                               │
                        ▼                               ▼
┌────────────────────────────── Domain Agent Layer ───────────────────────────────┐
│ Agent1/2/2Checker -> Agent3/4/5/6/7 -> Agent8/9                                 │
│ + ReviewerComposerAgent（新增，按 reviewer 聚合问题策略）                        │
│ + ExperimentAggregatorAgent（新增，全局实验去重与优先级）                        │
└───────────────────────┬───────────────────────────────┬───────────────────────┘
                        │                               │
                        ▼                               ▼
┌────────────────────────────── Persistence Layer ────────────────────────────────┐
│ session_summary.json / interaction_q*.json / agent*_output.txt                  │
│ reviewer_outputs/*.md（新增） / global_experiment_plan.{json,md}（新增）         │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|----------------|-------------------|
| Review Parsing | 从 Agent2/2Checker 结果提取问题列表 | Reviewer Routing, Question Pipeline |
| Reviewer Routing (new) | 识别 reviewer 边界，建立 `qid -> reviewer_id` 映射 | Session Model, UI |
| Question Pipeline | 逐问题运行 Agent3~7，生成策略与证据摘要 | Reviewer Composer, Experiment Aggregator |
| Reviewer Composer (new) | 按 reviewer 汇总问题策略并生成可粘贴回复 | UI, Persistence |
| Experiment Aggregator (new) | 跨 reviewer 合并实验诉求，去重并标注证据状态 | UI, Persistence |
| Final Formatter | 产出最终文本包（按 reviewer + 全局实验） | UI Download, Persistence |
| Session Persistence | 持久化结构化状态，支持恢复与追踪 | RebuttalService, Resume Flow |

## Data Flow

### End-to-End Flow

```text
[Paper PDF + Review Text]
          │
          ▼
  Agent1 / Agent2 / Agent2Checker
          │
          ▼
   Question List (q1...qn)
          │
          ▼
   Reviewer Routing (new)
   ├── reviewer_map: {question_id -> reviewer_id}
   └── reviewer_order: [R1, R2, ...]
          │
          ▼
Parallel Question Pipeline (Agent3~7 for each question)
          │
          ▼
Structured Question Artifacts
  ├── strategy
  ├── reference_summary
  ├── evidence_status（已有/待补）
  └── candidate_experiments
          │
          ├──────────────► Reviewer Composer (new) ─► reviewer_outputs/*.md
          │
          └──────────────► Experiment Aggregator (new) ─► global_experiment_plan.{json,md}
                                             │
                                             ▼
                      Final Package: per-reviewer rebuttal + global experiment summary
```

### State Contract (建议增量)

| Model | New Fields | Purpose |
|------|------------|---------|
| `QuestionState` | `reviewer_id`, `reviewer_q_index`, `evidence_status`, `candidate_experiments` | 把“问题维度”提升为“reviewer+问题”双维度 |
| `SessionState` | `reviewers`, `global_experiment_summary`, `final_outputs` | 承载按 reviewer 输出与全局实验汇总产物 |
| `session_summary.json` | `reviewer_map`, `reviewer_outputs`, `global_experiment_plan` | 确保重启恢复后不丢聚合结果 |

## Current Gaps to Close

1. 现有 `QuestionState` 无 reviewer 归属字段，无法稳定输出 reviewer 级结果。  
2. `generate_final_rebuttal` 当前按问题串接，缺少 reviewer 视图与实验全局视图。  
3. 持久化文件仅记录问题级策略，未定义全局实验结构化 schema。  
4. UI 仅围绕 `current_question_idx` 导航，无法展示 reviewer 汇总与跨 reviewer 决策。

## Suggested Build Order

1. **扩展数据模型与持久化（先做）**  
   在 `QuestionState` / `SessionState` 与 `session_summary.json` 增加 reviewer 与实验字段，先打通恢复能力。  

2. **接入 Reviewer Routing**  
   在初始解析后建立 `question_id -> reviewer_id` 映射，保证后续所有产物都携带 reviewer 上下文。  

3. **保持原并行问答主线不变**  
   复用 `process_all_questions_parallel`，仅在 question 产物中补写证据状态与候选实验。  

4. **新增 Reviewer Composer**  
   基于“已确认问题策略”并行生成每个 reviewer 的可粘贴 rebuttal 文本。  

5. **新增 Global Experiment Aggregator**  
   汇总全部问题的候选实验，执行去重、冲突消解、优先级排序，并显式标注“已有证据/待补证据”。  

6. **更新 UI 与最终导出**  
   增加 reviewer 视图与全局实验视图，最终导出包含两部分：`reviewer_outputs` + `global_experiment_plan`。  

## Patterns to Follow

### Pattern 1: Reviewer-First Aggregation
**What:** 先确定 reviewer 边界，再把问题产物挂载到 reviewer。  
**When:** 需要“按 reviewer 直接粘贴”输出时。  
**Trade-offs:** 多一层映射维护成本，但换来输出结构稳定与可追溯。

### Pattern 2: Artifact-First Pipeline
**What:** 每阶段输出结构化 artifact（而非仅自由文本）。  
**When:** 需要恢复、审计、二次聚合（如实验去重）时。  
**Trade-offs:** 初期 schema 设计成本上升，但后续扩展成本显著下降。

### Pattern 3: Dual-Track Finalization
**What:** 最终阶段拆成两条并行轨：Reviewer 输出轨 + 全局实验轨。  
**When:** 需要同时满足“局部说服力”和“全局实验一致性”。  
**Trade-offs:** 协调逻辑更复杂，但可避免单一路径互相污染。

## Anti-Patterns to Avoid

### Anti-Pattern 1: 末端一次性“猜 reviewer”
**What:** 到最终生成阶段再让模型从整段策略中反推 reviewer 分组。  
**Why bad:** 不可重复、不可追溯，且难以恢复。  
**Instead:** 在问题抽取后立即固定 reviewer 映射并全程透传。

### Anti-Pattern 2: 用非结构化长文本做实验汇总
**What:** 直接拼接所有策略文本让模型“自由总结实验”。  
**Why bad:** 易遗漏冲突实验，且无法区分已有证据与待补证据。  
**Instead:** 先结构化提取 `candidate_experiments`，再聚合排序输出。

## Scalability Considerations

| Concern | 当前（1 会话，<20 问题） | 中期（20-80 问题） | 扩展（80+ 问题） |
|---------|---------------------------|--------------------|------------------|
| 并行吞吐 | `ThreadPoolExecutor` 足够 | 分 reviewer 分批并行 | 引入任务队列与重试队列 |
| 聚合成本 | 内存聚合即可 | 增加缓存与分阶段落盘 | 增量聚合 + 按 reviewer 分片 |
| 恢复一致性 | 单 `session_summary.json` | 增加 reviewer/experiment 子文件 | 使用版本化 schema 与迁移器 |

## Sources

- `.planning/PROJECT.md`  
- `.planning/codebase/ARCHITECTURE.md`  
- `.planning/codebase/STRUCTURE.md`  
- `.codex/agents/gsd-project-researcher.md`  
- `.codex/get-shit-done/templates/research-project/ARCHITECTURE.md`

---
*Architecture research for rebuttal multi-agent evolution*
