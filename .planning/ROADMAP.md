# ROADMAP: RebuttalAgent Solo Rebuttal Workflow

**Created:** 2026-03-03  
**Depth:** standard  
**Coverage:** 19/19 v1 requirements mapped

## Phases

- [ ] **Phase 1: Reviewer 识别与归属映射** - 从原始 review 文本识别 reviewer 并把问题稳定归属到 reviewer_id
- [ ] **Phase 2: Reviewer 级可粘贴回复（说服力 + 证据护栏）** - 按 reviewer 生成可直接粘贴回复，并显式证据状态、禁止编造结果
- [ ] **Phase 3: 跨 Reviewer 统一实验计划** - 汇总去重并排序跨 reviewer 的补充实验清单，输出可执行说明
- [ ] **Phase 4: 提交前合规闸门** - 匿名风险/字符预算/时态合规检查，不通过则阻止进入可提交状态
- [ ] **Phase 5: 会话追溯与恢复** - reviewer 输出与全局实验计划落盘、可恢复，并记录关键决策链路

## Phase Details

### Phase 1: Reviewer 识别与归属映射
**Goal**: 用户提供原始 review 文本后，系统能识别 reviewer 边界并为每条问题稳定赋予唯一 reviewer_id  
**Depends on**: Nothing (first phase)  
**Requirements**: RVW-01, RVW-02  
**Success Criteria** (what must be TRUE):
  1. 系统能从原始 review 文本中识别 reviewer 边界并生成 reviewer_id（可在界面中看到每位 reviewer 的分区/标识）。
  2. 抽取出的每条问题都包含且仅包含一个 reviewer_id，用户可按 reviewer 过滤查看问题列表。
  3. 对同一份输入，问题到 reviewer_id 的映射在后续流程中保持一致（不会在生成/导出阶段丢失或重映射）。
**Plans**: TBD

### Phase 2: Reviewer 级可粘贴回复（说服力 + 证据护栏）
**Goal**: 用户可按 reviewer 生成独立、可直接粘贴的 rebuttal 回复，并以“主张-证据-行动”组织，显式区分证据状态且禁止编造结果/新数值  
**Depends on**: Phase 1  
**Requirements**: RVW-03, RVW-04, PRS-01, PRS-02, PRS-03, PRS-04  
**Success Criteria** (what must be TRUE):
  1. 用户可为每个 reviewer 生成一段独立 rebuttal 文本（不混入其他 reviewer 内容），并可在 UI 中逐 reviewer 查看。
  2. 每条回复按“主张-证据-行动”结构输出，且明确标注“已有证据”与“待补证据”。
  3. 缺失证据时，系统使用统一占位符 `[[TBD: ...]]`，而不是输出看似确定的结论。
  4. 系统阻止生成未提供依据的新实验结果或新数值（不允许把计划补充写成已完成/已提升）。
  5. 用户可逐 reviewer 导出最终回复（可直接粘贴到 rebuttal 文档）。
**Plans**: TBD

### Phase 3: 跨 Reviewer 统一实验计划
**Goal**: 系统能跨 reviewer 汇总候选补充实验为统一清单，合并重复项，并按“说服力收益 × 实施成本”排序，且每项包含可执行说明  
**Depends on**: Phase 2  
**Requirements**: EXP-01, EXP-02, EXP-03, EXP-04  
**Success Criteria** (what must be TRUE):
  1. 用户可生成一份跨 reviewer 的统一实验清单，覆盖各 reviewer 的关键质疑点。
  2. 系统能识别并合并重复/近重复实验项（用户看到的清单中重复项被收敛）。
  3. 实验项按“说服力收益 × 实施成本”排序，用户可看到排序后的优先级结果。
  4. 每个实验项都包含：目标质疑点、预期支撑主张、执行说明（足以让用户照做）。
**Plans**: TBD

### Phase 4: 提交前合规闸门
**Goal**: 在导出/发布前执行匿名、长度与时态合规检查；任一失败则阻止进入可提交状态，并提供可修复输出  
**Depends on**: Phase 2, Phase 3  
**Requirements**: CMP-01, CMP-02, CMP-03, CMP-04  
**Success Criteria** (what must be TRUE):
  1. 系统能在发布前对输出做匿名风险检查（如 URL/邮箱/身份线索），并给出可定位的风险提示。
  2. 系统能按会议字符预算做长度检查；超限时能生成压缩版本并把长度控制在预算内。
  3. 对“计划补充项”，系统能强制使用合规时态表达，避免“已修改投稿/已新增结果”的不当表述。
  4. 合规检查未通过时，系统阻止进入“可提交/可导出最终版”状态；通过后才允许标记为可提交。
**Plans**: TBD

### Phase 5: 会话追溯与恢复
**Goal**: 会话产物（reviewer 输出、全局实验计划）可落盘并可恢复；关键决策可追溯，支持审计与回滚式修订  
**Depends on**: Phase 2, Phase 3, Phase 4  
**Requirements**: LOG-01, LOG-02, LOG-03  
**Success Criteria** (what must be TRUE):
  1. 会话中 reviewer 级输出与全局实验计划会保存为可复用 artifact（可在文件系统中找到并被系统重新加载）。
  2. 用户在中断/重启后可恢复到上次会话状态并继续编辑（不会丢失 reviewer 输出与实验计划）。
  3. 对实验合并、冲突处理、合规修订等关键决策，系统能记录可追溯日志（用户可查看或导出）。
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Reviewer 识别与归属映射 | 0/0 | Not started | - |
| 2. Reviewer 级可粘贴回复（说服力 + 证据护栏） | 0/0 | Not started | - |
| 3. 跨 Reviewer 统一实验计划 | 0/0 | Not started | - |
| 4. 提交前合规闸门 | 0/0 | Not started | - |
| 5. 会话追溯与恢复 | 0/0 | Not started | - |

