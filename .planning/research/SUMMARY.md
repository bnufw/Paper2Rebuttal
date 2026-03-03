# Project Research Summary

**Project:** RebuttalAgent Solo Rebuttal Workflow
**Domain:** 论文 rebuttal 多代理工作流增量改造（solo-first / reviewer-first / persuasion-first）
**Researched:** 2026-03-03
**Confidence:** MEDIUM

## Executive Summary

本项目是一个**本地单人**（solo-first）的论文 rebuttal 工作流系统：用户上传论文 PDF 与 review 文本后，系统通过多代理流水线抽取问题、生成回应策略并产出可粘贴的 rebuttal 草稿。当前增量改造的核心目标非常明确：**按 reviewer 产出可直接粘贴的回复**，并在全局层面统一给出**跨 reviewer 的实验补充计划**，同时以“**说服力优先**”（主张-证据-行动）组织回应，并严守**证据完整性**与**会议合规**（匿名/字数/格式）约束。

推荐的实现路线是**保持现有 Python + Gradio + LLM 网关 + Docling** 主栈不变，在关键链路引入**结构化数据契约（Pydantic）**：从“reviewer 归属映射（question_id → reviewer_id）”开始，把问题级产物升级为可验证 artifact（策略、证据状态、候选实验等），再进行两条终稿轨的并行收敛：**Reviewer 输出轨**（每位 reviewer 一份可粘贴回复）与**全局实验轨**（去重、冲突消解、按收益/成本排序的实验计划）。

主要风险集中在：1) **把未做实验写成已证明**（学术诚信风险）；2) **reviewer 维度丢失**导致回复错配；3) **合规检查后置**导致多轮返工与质量塌缩；4) **自由文本解析脆弱/LLM 失败冒充成功**造成静默污染；5) **并发与恢复**中的全局状态串写。应对策略是采用“**确定性扫描（规则）→ 受约束生成（LLM）→ 二次扫描**”的闭环，并把关键产物落到结构化快照中（版本化 schema），再用最小回归测试作为发布门禁。

## Key Findings

### Recommended Stack

总体建议是**延续现有可运行 brownfield 栈**，仅新增少量“把自由文本变成可验证对象”的依赖（Pydantic）。这是最短路径：既能快速落地 reviewer-first 输出与全局实验汇总，又能显著降低解析漂移带来的回归风险。

**Core technologies:**
- Python `>=3.10,<3.12`：主运行时与多代理编排 — 已在现有系统与 Docling 上验证，升级范围收敛降低回归面。
- Gradio `>=6.2,<6.4`：本地 UI — 当前稳定可用，增量扩展面板与模式开关即可，无需前端重写。
- OpenAI SDK `>=2.14,<3`：统一 OpenAI-compatible 调用 — 复用现有 `llm.py` 网关封装（重试/统计），改造成本最低。
- Docling `>=2.30,<2.32`：PDF → Markdown — 满足 rebuttal 场景的信息抽取需求，避免替换解析引擎的系统性风险。
- Pydantic `>=2.8,<3`（新增）：结构化输出校验 — 为 reviewer 映射、实验清单、合规报告提供 schema 约束，替代“自由文本 + 正则”脆弱解析。

### Expected Features

**Must have (table stakes):**
- 按 reviewer 生成可直接粘贴回复 — rebuttal 的基础交付单元，必须从单份总稿升级为 reviewer 级产物。
- 统一实验补充计划（跨 reviewer）— 合并去重、避免重复实验，直接支撑“deadline 前最大化收益”。
- 说服力优先回复骨架（主张-证据-行动）— 把“礼貌改写”升级为“可说服的行动方案”。
- 证据完整性护栏（已有/待补分离）— 禁止编造结果，缺证据必须显式 `[[TBD: ...]]`。
- 匿名/字数/格式合规检查（发布前闸门）— 确保输出可提交，不以人工终检兜底。
- 会话可追溯产物（reviewer + 实验项）— 支持恢复与审计，减少返工成本。

**Should have (competitive):**
- 实验计划“说服力收益 × 实施成本”排序 — 把有限时间投入到最影响评审决策的实验上。
- 跨 reviewer 承诺一致性检查（冲突检测）— 避免对不同 reviewer 给出矛盾承诺。
- follow-up 回复模式（短回复 + 最小证据清单）— 支持 rebuttal 后续追问回合的快速闭环。
- 会议配置档（ICML/NeurIPS 等 profile）— 一键切换约束策略，减少手工改模板成本。
- 证据链追踪视图（claim→evidence→action）— 快速检查“每条回复是否有证据与动作”。

**Defer (v2+):**
- 多用户协作与权限系统 — 与 solo-first 边界冲突，显著扩大复杂度。
- 自动运行训练/评测实验 — 资源与失败面不可控，超出当前产品边界。
- 自动提交会议系统/OpenReview — 高风险、不可逆外部操作，应保留人工最终决策。

### Architecture Approach

推荐架构是**分层单体 + artifact-first**：Gradio 负责交互展示；`RebuttalService` 负责编排与并行；domain agent 层保持现有 Agent1~9 流水线，并新增两个聚合器（ReviewerComposer / ExperimentAggregator）；持久化层以结构化快照为主、日志为辅，新增 `reviewer_outputs/*.md` 与 `global_experiment_plan.{json,md}` 作为稳定产物。

**Major components:**
1. Reviewer Routing（新增）— 固定 `question_id -> reviewer_id` 映射，并全程透传，避免末端“猜 reviewer”。
2. Reviewer Composer（新增）— 按 reviewer 聚合问题策略并生成可粘贴回复（独立上下文、避免跨 reviewer 污染）。
3. Experiment Aggregator（新增）— 跨 reviewer 汇总候选实验，去重/冲突消解/优先级排序，并显式标注证据状态。

### Critical Pitfalls

1. **证据完整性失守（把计划做写成已证明）** — 建立 claim→evidence→status 账本；新增数字溯源检查；缺证据强制 `[[TBD: ...]]`。
2. **Reviewer 维度丢失导致回复错配** — Phase 1 先落地 `reviewer_id` 作为一级键；解析阶段加一致性校验；生成阶段按 reviewer 独立上下文调用。
3. **合规检查后置导致反复返工** — 前置字符预算与匿名规则（prompt + post-check）；按违规类型定向重写；每轮改写后自动复检。
4. **LLM 失败文本被当作正常产物传播** — 统一失败契约（异常/错误对象）；关键阶段 fail-closed；对成功输出做最小结构校验与黑名单检查。
5. **自由文本解析脆弱、静默污染下游决策** — 全链路结构化输出 + schema 校验 + 失败重试；为解析/合规/恢复补最小单测与畸形样例。

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 0: 边界与契约冻结（Schema-first）
**Rationale:** 这是 brownfield 增量改造，先冻结输入输出契约才能避免“边改边塌”。  
**Delivers:** Pydantic 数据模型（reviewer_map / question_artifact / experiment_item / compliance_report）；产物文件结构与版本号策略；失败语义（fail-closed）约定。  
**Addresses:** 结构化解析与可追溯产物的前置条件。  
**Avoids:** 自由文本解析脆弱、LLM 失败冒充成功的静默污染。

### Phase 1: Reviewer 维度建模与聚合输出（Reviewer-first）
**Rationale:** “按 reviewer 输出”是核心交付单元，且它是全局实验汇总与一致性检查的依赖。  
**Delivers:** `question_id -> reviewer_id` 路由；`QuestionState/SessionState` 扩展与持久化；ReviewerComposer 生成 `reviewer_outputs/*.md`；UI 增加 reviewer 面板与导出。  
**Addresses:** per-reviewer 可粘贴回复、会话可追溯产物。  
**Avoids:** Reviewer 维度丢失导致回复错配；末端一次性“猜 reviewer”的不可追溯反模式。

### Phase 2: 全局实验计划 + 证据完整性 + 合规闸门（Quality gates）
**Rationale:** 说服力提升的主要抓手是“证据与实验”；且合规/证据问题必须在终稿前成为硬门禁。  
**Delivers:** ExperimentAggregator 输出 `global_experiment_plan.{json,md}`（去重/冲突消解/优先级）；证据状态标注与 `[[TBD]]` 规范；数字溯源检查；会议 profile（字符预算、匿名规则）与定向重写器；抓取链路域名白名单与下载策略。  
**Addresses:** 统一实验补充清单、说服力骨架、证据完整性护栏、匿名/字数/格式合规检查。  
**Avoids:** 证据完整性失守、合规末端返工、文献抓取信任边界缺失、LLM 失败文本传播。

### Phase 3: 会话恢复与并发隔离加固（Reliability）
**Rationale:** 并行处理与可恢复是现有系统的优势，但全局可变状态与日志式恢复在改造后风险上升。  
**Delivers:** 版本化 `session_summary.json`（优先快照恢复、日志为补偿）；旧会话迁移适配；会话级 LLM client/tracker；线程安全聚合与串写防护；双会话并发回归样例。  
**Addresses:** 稳定恢复、并发下状态一致性、可审计性。  
**Avoids:** 会话恢复失真、并发下全局状态互相污染。

### Phase 4: 最小自动化回归与发布门禁（Tests as gates）
**Rationale:** 没有可重复回归，增量改造会在 deadline 前集中爆雷。  
**Delivers:** 60s 内可跑的最小回归套件（解析、reviewer 路由、合规扫描、字符预算、证据占位、会话恢复、并发隔离）；对 LLM/网络边界 mock；将“关键测试通过”作为阶段完成条件。  
**Addresses:** 质量保证与发布可控性。  
**Avoids:** 只能靠人工 E2E 的回归滞后与链式故障。

### Phase Ordering Rationale

- Reviewer-first 依赖早期固定 reviewer 映射；否则后续任何聚合都不可追溯且易错配。
- 全局实验计划依赖问题级 artifact（含候选实验与证据状态）先结构化，再聚合排序，避免“长文本自由总结”遗漏冲突。
- 合规/证据作为硬闸门应尽早落地，否则终稿阶段返工会引发多轮压缩重写并损害说服力。
- 并发/恢复加固与最小回归应在核心功能落地后尽快补齐，防止后期变更把已验证流程打碎。

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2（会议 profile 与合规规则）:** 需要针对目标会议/平台（字符预算、匿名要求、格式约束）做明确化与样例验证，否则容易出现“规则写错/漏写”。
- **Phase 2（数字溯源检查策略）:** 需要定义“允许出现的新数字”边界（例如来自输入/引用/显式 TBD），避免误杀或漏检。

Phases with standard patterns (skip research-phase):
- **Phase 0（Pydantic schema + fail-closed 契约）:** 成熟通用模式，主要是工程落地与覆盖关键字段。
- **Phase 1（reviewer 路由 + 聚合输出）:** 依赖内部数据流改造，模式清晰且研究已给出反模式与替代方案。
- **Phase 4（最小 unittest 回归）:** 以 mock 边界与畸形样例为主，属于成熟工程实践。

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | 现有栈高一致性；新增 Pydantic 低风险，但版本上界与跨版本回归未验证。 |
| Features | HIGH | 与 `.planning/PROJECT.md` 的 Active 需求高度一致，且依赖关系清晰。 |
| Architecture | MEDIUM | 对现状映射高把握；对演进实现细节（UI/持久化/并发边界）仍需在实现时验证。 |
| Pitfalls | HIGH | 风险点与防线明确，且与 brownfield 真实故障模式高度匹配。 |

**Overall confidence:** MEDIUM

### Gaps to Address

- 目标会议/平台的字符预算与匿名规则细节：在 Phase 2 规划时明确化并落地可重复样例。
- Reviewer 路由的边界样例（缺少 reviewer 标签、编号不连续、混合格式）：需要覆盖畸形输入并提供可观测失败。
- 全局实验去重/冲突消解的规则：需要定义“同实验不同表述/不同设置”的归并策略与保守输出策略。
- 依赖可复现性（lockfile）：是否引入 `requirements.lock` 以及与现有环境的兼容策略需在里程碑规划中确定。

## Sources

### Primary (HIGH confidence)
- `.planning/PROJECT.md` — 目标、约束、范围边界（solo-first / reviewer-first / evidence integrity）
- `.planning/research/STACK.md` — 推荐技术栈与版本范围
- `.planning/research/FEATURES.md` — MVP/差异化/反特性与依赖关系
- `.planning/research/ARCHITECTURE.md` — 分层架构与演进顺序建议
- `.planning/research/PITFALLS.md` — 风险清单与分阶段防线

### Secondary (MEDIUM confidence)
- `requirements.txt` — 当前依赖事实基线
- `.planning/codebase/*` — 现状映射与已知关注点（依赖漂移、解析脆弱、测试缺口）

---
*Research completed: 2026-03-03*
*Ready for roadmap: yes*

