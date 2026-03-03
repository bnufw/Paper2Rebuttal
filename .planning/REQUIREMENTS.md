# Requirements: RebuttalAgent Solo Rebuttal Workflow

**Defined:** 2026-03-03  
**Core Value:** 在 rebuttal 截止前，把评审意见转化为最有说服力且可执行的回应与实验行动

## v1 Requirements

### Reviewer Responses

- [ ] **RVW-01**: 系统可从原始 review 文本识别 reviewer 边界与 reviewer_id
- [ ] **RVW-02**: 每条抽取问题可稳定映射到唯一 reviewer_id
- [ ] **RVW-03**: 系统可按 reviewer 生成可直接粘贴的独立 rebuttal 文本
- [ ] **RVW-04**: 用户可逐 reviewer 查看与导出最终回复

### Unified Experiments

- [ ] **EXP-01**: 系统可跨 reviewer 汇总候选补充实验为统一清单
- [ ] **EXP-02**: 系统可识别并合并重复/近重复实验项
- [ ] **EXP-03**: 系统可按“说服力收益 × 实施成本”对实验项排序
- [ ] **EXP-04**: 每个实验项包含目标质疑点、预期支撑主张与执行说明

### Persuasion & Evidence

- [ ] **PRS-01**: 每条 reviewer 回复采用“主张-证据-行动”结构
- [ ] **PRS-02**: 回复中显式区分“已有证据”与“待补证据”
- [ ] **PRS-03**: 缺失证据时输出统一占位符 `[[TBD: ...]]`
- [ ] **PRS-04**: 系统阻止生成未提供依据的实验结果或新数值

### Compliance Gate

- [ ] **CMP-01**: 输出在发布前执行匿名风险检查（URL/邮箱/身份线索）
- [ ] **CMP-02**: 输出按会议字符预算执行长度检查与超限压缩
- [ ] **CMP-03**: 对“计划补充项”使用合规时态表达，避免“已修改投稿”表述
- [ ] **CMP-04**: 未通过合规检查时阻止进入可提交状态

### Session Traceability

- [ ] **LOG-01**: 会话中保存 reviewer 级输出与全局实验计划 artifact
- [ ] **LOG-02**: 中断后可恢复到上次会话状态并继续编辑
- [ ] **LOG-03**: 关键决策（实验合并、冲突处理、合规修订）可追溯

## v2 Requirements

### Advanced Workflow

- **ADV-01**: 支持 reviewer follow-up 追问回合的短回复生成模式
- **ADV-02**: 支持跨 reviewer 承诺冲突自动检测与修复建议
- **ADV-03**: 支持多会议规则配置档（如 ICML/NeurIPS/ICLR）
- **ADV-04**: 提供 claim→evidence→action 证据链可视化

### Collaboration (Deferred)

- **COL-01**: 多用户协作与角色权限管理
- **COL-02**: 审阅/批准流与团队版本对比

## Out of Scope

| Feature | Reason |
|---------|--------|
| 自动运行训练/评测实验 | 超出当前产品边界，资源与失败面不可控 |
| 自动提交会议系统/OpenReview | 高风险且不可逆，需人工最终确认 |
| 通用学术写作助手扩展 | 当前聚焦 rebuttal 场景，避免范围蔓延 |
| SaaS 化多租户平台 | 与“仅自己用”的当前目标不匹配 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| RVW-01 | TBD | Pending |
| RVW-02 | TBD | Pending |
| RVW-03 | TBD | Pending |
| RVW-04 | TBD | Pending |
| EXP-01 | TBD | Pending |
| EXP-02 | TBD | Pending |
| EXP-03 | TBD | Pending |
| EXP-04 | TBD | Pending |
| PRS-01 | TBD | Pending |
| PRS-02 | TBD | Pending |
| PRS-03 | TBD | Pending |
| PRS-04 | TBD | Pending |
| CMP-01 | TBD | Pending |
| CMP-02 | TBD | Pending |
| CMP-03 | TBD | Pending |
| CMP-04 | TBD | Pending |
| LOG-01 | TBD | Pending |
| LOG-02 | TBD | Pending |
| LOG-03 | TBD | Pending |

**Coverage:**
- v1 requirements: 19 total
- Mapped to phases: 0
- Unmapped: 19 ⚠️

---
*Requirements defined: 2026-03-03*  
*Last updated: 2026-03-03 after initial definition*
