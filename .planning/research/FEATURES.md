# Feature Research

**Domain:** 论文 rebuttal 增量改造（solo-first，本地 Gradio 工作流）
**Researched:** 2026-03-03
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| 按 reviewer 生成可直接粘贴回复 | OpenReview/顶会 rebuttal 的基础交付单元就是每个 reviewer 独立回复 | MEDIUM | reviewer 结构化抽取；`question -> reviewer_id` 归属；per-reviewer 渲染器 | 当前仅有单份总 rebuttal，需改为按 reviewer 聚合输出 |
| 统一实验补充计划（跨 reviewer） | 作者需要一份合并后的实验待办，避免重复做实验 | HIGH | 跨 reviewer 问题归一化；冲突去重；优先级排序器 | 与“说服力优先”强绑定，属于核心业务价值 |
| 说服力优先回复骨架（主张-证据-行动） | 用户明确把“说服力”作为首要优化目标 | MEDIUM | 策略阶段结构化输出；writer/reviewer prompts 同步 | 需统一模板，避免仅“礼貌改写”而无证据推进 |
| 证据完整性护栏（已有/待补分离） | rebuttal 场景必须避免编造结果，缺失证据需显式标注 | MEDIUM | 证据状态标注器；`[[TBD: ...]]` 规范；后处理校验 | 直接响应 PROJECT 的 Evidence Integrity 约束 |
| 匿名/字数/格式合规检查 | 顶会 author response 有硬性字符预算与匿名约束 | MEDIUM | 规则扫描器；字符预算器；重写压缩链路 | 作为“发布前闸门”而非可选增强 |
| 会话可追溯产物（按 reviewer + 按实验项） | 用户需要可恢复、可审计的修改与证据链 | LOW | 现有 session/log 落盘机制；新增结构化 artifact 命名 | brownfield 改造成本低，收益高 |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|--------------|-------|
| 统一实验计划的“说服力收益 × 实施成本”排序 | 先做最能提升 AC/Reviewer 说服力的实验，最大化 deadline 前收益 | HIGH | 统一实验池；成本估计规则；论点影响评分 | 区别于普通“问题罗列式”rebuttal 工具 |
| 跨 reviewer 承诺一致性检查（冲突检测） | 防止对不同 reviewer 给出互相冲突承诺，降低风险 | HIGH | per-reviewer 草稿；语义归并；冲突规则 | 与统一实验计划联动，避免重复/矛盾工作 |
| follow-up 回复模式（短回复 + 最小证据清单） | 支持 rebuttal 后续追问回合，减少临场组织成本 | MEDIUM | per-reviewer 上下文；证据缺口提取器 | 强化闭环能力，不止初次 rebuttal |
| 会议配置档（ICML/NeurIPS 等） | 一键切换约束策略，减少手工改模板成本 | MEDIUM | 合规引擎；模板参数化；会议 profile 管理 | 提升可迁移性，降低重复配置 |
| 证据链追踪视图（claim→evidence→action） | 让作者快速检查“每条回复是否有证据支撑和执行动作” | MEDIUM | 结构化响应 schema；会话 artifact 索引 | 强化可信度与可审计性 |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Complexity | Why Problematic | Dependency / Conflict | Alternative |
|---------|---------------|------------|-----------------|-----------------------|-------------|
| 自动编造实验结果或数值补全 | 用户希望“先把文本补齐”以节省时间 | LOW | 直接违反证据完整性，存在学术诚信风险 | 冲突于 Evidence Integrity 约束 | 强制 `[[TBD: ...]]` 占位 + 最小证据清单 |
| 自动运行训练/评测实验 | 期望端到端自动化 | HIGH | 资源成本高、失败面广、超出当前产品边界 | 依赖作业调度/算力编排，现有系统无此能力 | 仅输出可执行实验计划与参数建议 |
| 自动提交 OpenReview/会议系统 | 期望“最后一步也自动化” | HIGH | 涉及账号凭据、不可逆提交和泄露风险 | 冲突于安全与可审计边界 | 导出可直接粘贴文本包，人工最终提交 |
| 提前引入多用户协作与权限系统 | 团队化场景常见诉求 | HIGH | 当前是 solo-first，会显著扩大复杂度与维护面 | 与现有全局单例/本地存储架构强冲突 | 保持单用户本地优先，后续按里程碑再评估 |
| 默认展示全量原始 prompt/日志给终端用户 | 便于“看细节” | MEDIUM | 信息噪声大，且可能暴露敏感内容 | 冲突于日志最小暴露与安全实践 | 默认摘要视图 + 按需展开调试明细 |

## Feature Dependencies

```text
[Reviewer 结构化抽取]
    └──requires──> [Review 解析与 reviewer_id 映射]

[按 reviewer 回复生成]
    ├──requires──> [Reviewer 结构化抽取]
    ├──requires──> [说服力骨架（主张-证据-行动）]
    └──requires──> [证据完整性护栏]

[统一实验补充计划]
    ├──requires──> [跨 reviewer 问题归一化]
    └──requires──> [证据缺口标注]
[统一实验补充计划] ──enhances──> [按 reviewer 回复生成]

[合规扫描 + 字符预算压缩]
    └──requires──> [会议约束配置档]
[合规扫描 + 字符预算压缩] ──gates──> [可提交最终输出]

[自动运行实验] ──conflicts──> [solo-first 轻量本地边界]
[自动提交会议系统] ──conflicts──> [高风险操作需人工确认原则]
```

### Dependency Notes

- **按 reviewer 回复生成 requires Reviewer 结构化抽取：** 没有 reviewer 归属就无法稳定输出“每位 reviewer 一条”的结果单元。
- **统一实验补充计划 requires 问题归一化与证据缺口标注：** 否则会出现重复实验、冲突承诺或缺少执行前提。
- **统一实验补充计划 enhances 按 reviewer 回复生成：** 统一实验池可为每位 reviewer 回复复用同一证据策略，提升一致性。
- **合规扫描 + 字符预算压缩 gates 最终输出：** 未通过匿名/字符约束的文本不能进入“可提交”状态。
- **自动运行实验 conflicts 当前产品边界：** 现有集成仅覆盖 LLM 与 arXiv，不具备稳健算力调度与作业治理能力。
- **自动提交会议系统 conflicts 安全原则：** 涉及不可逆外部操作，必须保留人工最终决策。

## MVP Definition

### Launch With (v1)

- [ ] 按 reviewer 输出可粘贴回复 — 直接满足核心交付格式
- [ ] 统一实验补充清单 — 统一跨 reviewer 行动，避免重复
- [ ] 说服力骨架（主张-证据-行动）— 聚焦“说服力优先”
- [ ] 证据完整性护栏（已有/待补）— 避免编造
- [ ] 合规与字符预算闸门 — 保证可提交性

### Add After Validation (v1.x)

- [ ] 跨 reviewer 承诺冲突检测 — 当回复规模增大时启用
- [ ] follow-up 短回复模式 — 当进入二轮追问时启用
- [ ] 会议配置档（多会议 profile）— 当跨 venue 使用频繁时启用

### Future Consideration (v2+)

- [ ] 协作/权限模型 — 仅在从 solo-first 升级为团队场景时考虑
- [ ] 与外部实验平台的受控联动 — 仅在资源与安全治理成熟后考虑

## Sources

- `.planning/PROJECT.md`
- `.planning/codebase/CONCERNS.md`
- `.planning/codebase/INTEGRATIONS.md`
- `.codex/get-shit-done/templates/research-project/FEATURES.md`
- `.codex/agents/gsd-project-researcher.md`

---
*Feature research for: rebuttal 增量改造（reviewer-first, persuasion-first）*
*Researched: 2026-03-03*
