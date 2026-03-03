# RebuttalAgent Solo Rebuttal Workflow

## What This Is

这是一个面向论文作者（当前为单人使用）的 rebuttal 工作流系统。  
它基于现有多代理流水线，把评审意见转成可执行的回应方案与实验补充计划。  
目标是按 reviewer 产出可直接粘贴的回复，同时统一给出跨 reviewer 的实验清单。

## Core Value

在 rebuttal 截止前，把评审意见转化为**最有说服力且可执行**的回应与实验行动。

## Requirements

### Validated

- ✓ 用户可上传论文 PDF 与 review 文本并完成自动解析 — existing
- ✓ 系统可抽取评审问题并生成逐问题回应策略 — existing
- ✓ 系统可检索并分析参考文献以支撑回应 — existing
- ✓ 用户可基于反馈循环迭代策略并生成最终 rebuttal 草稿 — existing
- ✓ 会话过程与关键产物可落盘并支持恢复 — existing

### Active

- [ ] 按 reviewer 输出可直接粘贴的 rebuttal 文本
- [ ] 基于所有 reviewer 意见统一生成实验补充清单
- [ ] 以“说服力优先”组织回复（主张-证据-行动）
- [ ] 显式区分“已有证据”与“待补证据”，避免编造结果
- [ ] 适配顶会匿名、字数与格式约束（可配置）

### Out of Scope

- 多用户协作与权限系统 — 当前仅个人使用，不引入协作复杂度
- 自动运行训练/评测实验 — 系统只给建议，不直接执行高成本任务
- 自动提交到会议系统/OpenReview — 涉及高风险外部操作，不属于核心流程
- 扩展为通用学术写作平台 — 当前仅聚焦 rebuttal 场景

## Context

- 现有代码是可运行的 brownfield 项目：`app.py` + `rebuttal_service.py` + `llm.py` + `arxiv.py` + `tools.py`。
- 当前流程已覆盖上传、问题抽取、策略生成、人工反馈迭代、最终 rebuttal 生成。
- 代码库映射已完成，文档位于 `.planning/codebase/`，可直接作为后续规划输入。
- 运行形态为本地 Gradio 应用，依赖外部 LLM API key 与网络可用性。
- 当前无自动化测试套件，质量验证以手工 E2E 为主。

## Constraints

- **User Scope**: 单人使用 — 方案优先本地效率与可控性
- **Platform**: 本地 Python + Gradio — 保持轻量部署
- **Dependencies**: 强依赖外部 LLM 提供商 API — 需容错与降级策略
- **Evidence Integrity**: 禁止编造实验结果 — 缺失证据必须标注待补
- **Conference Compliance**: 需满足匿名与字符预算约束 — 输出需可审计
- **Quality**: 当前测试基建薄弱 — 迭代时需补关键单测与回归检查

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 个人工作流优先（solo-first） | 用户明确“仅自己用” | — Pending |
| 输出按 reviewer 拆分 | 用户要求“按 reviewer 分 rebuttal” | — Pending |
| 实验计划统一汇总 | 用户要求“实验根据所有 reviewer 统一决定” | — Pending |
| 说服力作为首要优化目标 | 用户明确“最看重说服力” | — Pending |
| 基于现有流水线增量演进 | 现有系统已可运行，改造成本更低 | — Pending |

---
*Last updated: 2026-03-03 after initialization*
