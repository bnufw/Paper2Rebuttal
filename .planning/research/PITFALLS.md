# Pitfalls Research

**Domain:** 论文 Rebuttal 多代理系统（Brownfield 增量改造）
**Researched:** 2026-03-03
**Confidence:** HIGH

## Phase 定义（用于坑点映射）

- **Phase 0：改造边界与契约冻结**（明确“不重写”、定义输入输出契约）
- **Phase 1：Reviewer 维度建模与结构化解析**
- **Phase 2：证据完整性与合规护栏**
- **Phase 3：会话恢复与并发隔离加固**
- **Phase 4：最小自动化回归与发布门禁**

## Critical Pitfalls

### Pitfall 1: 把“计划做”写成“已经证明”（证据完整性失守）

**What goes wrong:**
在生成 rebuttal 时将未完成实验表述为既有结果，或补出输入中不存在的数值，直接违反“禁止编造结果”约束。

**Why it happens:**
现有提示词与生成链路缺少“证据来源约束”，且没有强制区分“已有证据/待补证据”。

**Warning signs:**
- 输出出现输入材料中不存在的新数字、新表格结论。
- 文本大量使用“we show / we achieved”但找不到对应证据来源。
- 缺实验问题没有 `[[TBD: ...]]` 或等价占位。

**How to avoid:**
- 建立“证据账本”字段（claim → evidence_source → status）。
- 在生成后增加“数字溯源检查”（新数字一律拦截）。
- 统一要求缺证据时输出 `[[TBD: ...]]`，禁止自由发挥数值。

**Phase to address:**
Phase 2（证据完整性与合规护栏）

---

### Pitfall 2: Reviewer 维度丢失导致回复错配

**What goes wrong:**
问题抽取与回答仍按“全局 questions”流转，导致 A reviewer 的问题被 B reviewer 回复，或跨 reviewer 混写。

**Why it happens:**
数据模型没有把 `reviewer_id` 作为一级键，解析器仅依赖宽松标签文本切分。

**Warning signs:**
- 回复段落中出现“跨 reviewer 引用”或编号跳跃。
- 同一 Q 编号对应多个 reviewer 内容。
- 人工复核时频繁需要手工搬运段落。

**How to avoid:**
- Phase 1 先落地结构化 schema：`reviewer_id -> question_id -> response`。
- 解析阶段加一致性校验：问题数、编号连续性、reviewer 归属唯一性。
- 生成阶段按 reviewer 独立上下文调用，禁止跨 reviewer 共享草稿。

**Phase to address:**
Phase 1（Reviewer 维度建模与结构化解析）

---

### Pitfall 3: 合规检查放在末端，导致反复返工

**What goes wrong:**
先生成长文本，最后才发现超字符、匿名违规、格式违规，引发多轮压缩重写，质量持续下降。

**Why it happens:**
当前流程缺少“生成即约束”的预算与合规 guardrail，靠人工终检兜底。

**Warning signs:**
- 终稿频繁超过会议字符预算（如 5000 chars）。
- 输出含 URL、身份线索、不当时态（“已修改投稿 PDF”）。
- 压缩回合超过 2 次且语义明显漂移。

**How to avoid:**
- 将字符预算与匿名规则前置为硬约束（prompt + post-check 双层）。
- 引入“违规类型 -> 定向重写器”而非全文重写。
- 每轮改写后执行自动合规复检，直到达标或明确失败。

**Phase to address:**
Phase 2（证据完整性与合规护栏）

---

### Pitfall 4: LLM 失败文本被当作正常产物继续传播

**What goes wrong:**
上游调用失败后返回错误字符串，下游仍当正常内容解析，最终产出“看似成功、实则失真”的 rebuttal。

**Why it happens:**
错误语义与业务语义未分离（返回值复用字符串通道），缺少强类型失败信号。

**Warning signs:**
- 日志出现 `Error calling`，但流水线状态仍标记成功。
- 输出包含明显异常片段（报错栈、重试提示语）。
- 同一阶段耗时异常短但文本质量骤降。

**How to avoid:**
- 统一 LLM 调用契约：失败必须抛异常/错误对象，不返回可被误解析的字符串。
- 在关键阶段设置 `fail-closed`：上游失败即中断，不进入下游生成。
- 对“成功输出”加最小结构校验与关键词黑名单。

**Phase to address:**
Phase 2（证据完整性与合规护栏）

---

### Pitfall 5: 自由文本解析脆弱，静默污染下游决策

**What goes wrong:**
通过标签或 `{...}` 截取 JSON 的启发式解析在格式漂移时误切分，问题列表/参考文献选择被静默污染。

**Why it happens:**
依赖 LLM 自由格式输出，解析器缺少 schema 验证、重试与失败显式化。

**Warning signs:**
- 问题数量与 reviewer 原文明显不匹配。
- JSON 解析“成功”但字段缺失/类型不对。
- 参考文献索引异常（越界、重复、空集）。

**How to avoid:**
- 全链路改为“结构化输出 + JSON schema 验证 + 失败重试”。
- 对关键解析函数增加畸形输入单测与模糊样例。
- 解析失败时返回可观测错误，不允许 silent fallback。

**Phase to address:**
Phase 1（Reviewer 维度建模与结构化解析）

---

### Pitfall 6: 会话恢复依赖日志命名规则，升级后历史会话失真

**What goes wrong:**
系统通过文件名正则恢复状态；一旦命名变化或日志缺失，会话恢复顺序错乱、阶段丢失。

**Why it happens:**
缺少版本化状态快照，仅靠非结构化日志“反推状态机”。

**Warning signs:**
- 重启后历史会话问题数减少或顺序错位。
- 人工反馈轮次丢失，UI 显示与日志不一致。
- 升级后旧会话恢复失败率显著上升。

**How to avoid:**
- 引入 `session_summary` 版本化 schema（含阶段游标、reviewer/Q 索引）。
- 恢复路径优先读结构化快照，日志仅作补偿。
- 提供旧格式迁移适配器并做回归样例。

**Phase to address:**
Phase 3（会话恢复与并发隔离加固）

---

### Pitfall 7: 并发下全局状态互相污染

**What goes wrong:**
问题级并行处理中共享 token 统计与客户端状态，造成计费统计错乱、日志串写、会话互相干扰。

**Why it happens:**
全局单例 + 无锁可变状态在 `ThreadPoolExecutor` 下被并发写入。

**Warning signs:**
- token 统计出现负增长、突增或跨会话跳变。
- `interaction_q*.json` 内容错位到其他问题/会话。
- 同样输入重复运行结果差异过大。

**How to avoid:**
- 将 LLM client 与 tracker 下沉为会话级依赖。
- 共享统计改为线程安全聚合（lock/queue）或无共享设计。
- 增加并发回归测试（至少覆盖双会话 + 多问题并发）。

**Phase to address:**
Phase 3（会话恢复与并发隔离加固）

---

### Pitfall 8: 文献抓取链路缺少信任边界，带来安全与质量双风险

**What goes wrong:**
Agent 产出的链接被直接抓取，可能触发 SSRF、下载异常大文件，或引入低质量/伪造来源污染证据。

**Why it happens:**
当前链路更关注“能抓到内容”，缺少严格域名白名单与下载策略。

**Warning signs:**
- 抓取请求命中非 arXiv 域名或私网地址。
- 下载体积异常、转换失败率突然升高。
- 证据摘要来源不稳定、不可复现。

**How to avoid:**
- 默认仅允许 `arxiv.org` 及必要镜像域名，禁私网/IP 直连。
- 增加文件大小、内容类型、超时与重试上限。
- 记录来源指纹（URL + 哈希 + 抓取时间）保证可审计。

**Phase to address:**
Phase 2（证据完整性与合规护栏）

---

### Pitfall 9: 没有最小自动化回归，增量改造变成“手工踩雷”

**What goes wrong:**
每次改 prompt/解析/恢复逻辑后只能靠人工 E2E，回归发现滞后，问题在截止前集中爆发。

**Why it happens:**
当前仓库无测试基建，关键风险点（解析、合规、恢复、并发）未形成可重复验证。

**Warning signs:**
- 相同输入在不同提交上输出结构不一致且无告警。
- 发布前需要大量人工逐轮对比日志。
- 修一个 bug 后出现两个新 bug（回归链式反应）。

**How to avoid:**
- 建立最小测试集：解析器、合规扫描、字符预算、会话恢复。
- 对 LLM 与网络边界做 mock，保证 60s 内可完成本地回归。
- 将“关键测试通过”设为 phase 完成门禁。

**Phase to address:**
Phase 4（最小自动化回归与发布门禁）

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 证据完整性失守 | Phase 2 | 新数字溯源检查全通过，缺证据统一 `[[TBD]]` |
| Reviewer 回复错配 | Phase 1 | reviewer/Q 映射一致性校验 100% 通过 |
| 合规末端返工 | Phase 2 | 终稿一次过预算与匿名检查 |
| 错误文本冒充成功 | Phase 2 | LLM 失败分支全部 fail-closed |
| 解析静默污染 | Phase 1 | 结构化解析失败可观测且可重试 |
| 会话恢复失真 | Phase 3 | 历史会话回放结果与快照一致 |
| 并发状态污染 | Phase 3 | 双会话并发下统计与日志无串写 |
| 文献抓取信任边界缺失 | Phase 2 | 非白名单域名/私网地址全部阻断 |
| 无自动化回归 | Phase 4 | 最小回归套件纳入发布门禁 |

## Sources

- `.planning/PROJECT.md`（目标、约束、增量改造边界）
- `.planning/codebase/CONCERNS.md`（已知 bug、脆弱点、安全与并发风险）
- `.planning/codebase/TESTING.md`（当前测试缺口与可行最小测试策略）
- `.codex/get-shit-done/templates/research-project/PITFALLS.md`（文档结构模板）

---
*Pitfalls research for: RebuttalAgent solo rebuttal incremental retrofit*
*Researched: 2026-03-03*
