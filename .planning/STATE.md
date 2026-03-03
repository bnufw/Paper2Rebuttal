# STATE: RebuttalAgent Solo Rebuttal Workflow

**Last updated:** 2026-03-03  
**Owner:** solo

## Project Reference

- **Core Value**: 在 rebuttal 截止前，把评审意见转化为最有说服力且可执行的回应与实验行动
- **Constraints**:
  - 本地 Python + Gradio（轻量部署）
  - 强依赖外部 LLM API（需容错/降级）
  - 禁止编造实验结果（缺证据必须显式标注）
  - 需满足匿名与字符预算约束（可配置）

## Current Position

- **Milestone**: v1
- **Phase**: 1/5 — Reviewer 识别与归属映射
- **Plan**: Not planned yet
- **Status**: Not started
- **Progress**: 0/5 phases complete

## Performance Metrics

- v1 requirements mapped: 19/19
- phases complete: 0/5
- last planning action: roadmap created

## Accumulated Context

### Decisions

- 以单人工作流为前提（solo-first）
- 输出按 reviewer 拆分（reviewer-first）
- 跨 reviewer 统一实验清单（unified experiments）
- “说服力优先”组织回复（主张-证据-行动）
- 显式证据状态并禁止编造结果（evidence integrity）
- 发布前设置合规闸门（匿名/长度/时态）

### Open Questions / Blockers

- 目标会议/平台的字符预算与匿名规则：需要明确默认配置与可切换 profile
- reviewer 边界输入的畸形样例范围：需要定义最小可支持格式与失败提示策略

### Next Actions

- 进入 Phase 1 规划：`/gsd:plan-phase 1`

## Session Continuity

- 本文件用于记录当前阶段与关键决策；每次完成一个 plan 或 phase 后更新。
- 产物位置：
  - Roadmap: `.planning/ROADMAP.md`
  - Requirements: `.planning/REQUIREMENTS.md`

