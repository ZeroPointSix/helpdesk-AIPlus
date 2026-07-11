# Issue #1 本机落地审查报告

| 字段 | 内容 |
|------|------|
| 审查对象 | [Epic #1](https://github.com/ZeroPointSix/helpdesk-AIPlus/issues/1)：AI 工单处理工作台 MVP（ZER-52） |
| 审查时间 | 2026-07-11 |
| 代码基线 | 本机 `develop`，相对 `origin/develop` **ahead 7** |
| 审查方式 | 对照 Issue 正文/子任务/验收标准 + 本机源码与 git 清单（**未在本机实际跑 bench migrate/tests**） |
| 结论摘要 | **代码侧 P0/P1 已基本落地并本地 commit；尚未 push 到 GitHub；环境级验收（migrate/测试/UI 演示）本审查未执行** |
| 收口跟进 | 见 [2026-07-11-issue-1-audit-followup.md](./2026-07-11-issue-1-audit-followup.md)（Failed 落库、响应式 ticketId、simulate loading、移动端入口、gitignore、文档入库） |

---

## 0. 一句话结论

| 维度 | 状态 |
|------|------|
| GitHub Issue 状态 | #1～#10 **均已 CLOSED**（评论宣称工作区已实现） |
| 本机代码实现 | **已实现**（DocType / API / Mock / 确认写回 / 前端面板 / 分支建议 / 测试 / 文档 / 样例 / LLM 骨架） |
| 本机 git | **7 个本地 commit 未 push**；`docs/change/*`、`exeample/`、部分 scripts JSON 仍 untracked |
| 运行时验收 | **本审查未执行** `bench migrate` / 单元测试 / 前端 build / 坐席 UI 演示 |
| 与 Epic 验收勾选 | 代码与文档**足以支撑**演示主流程；勾选仍取决于环境是否跑通 |

**落地完成度（代码层）：约 95%**  
**端到端可演示完成度（含环境）：未验证，估计 0～100% 取决于 bench 是否已 migrate**

---

## 1. Epic #1 要求对照

### 1.1 必须交付主流程

| 步骤 | Epic 要求 | 本机代码 | 说明 |
|------|-----------|----------|------|
| 1. 创建工单 | 已有 HD Ticket | ✅ 既有 | 非 AI 新增 |
| 2. 查看工单 | 坐席详情 | ✅ 既有 + AI 面板挂载 | `TicketDetailsTab.vue` |
| 3. 触发 AI 分析 | 需新增 | ✅ | `helpdesk.api.ai.analyze_ticket` + 面板按钮 |
| 4. 查看 AI 结果 | 需新增 | ✅ | `TicketAIWorkbench` / ResultForm / Evidence |
| 5. 人工确认或修改 | 需新增 | ✅ | `update_analysis` / `confirm_analysis` / `reject_analysis` |
| 6. 自动处理/转人工建议 | 需新增 | ✅ | `decide_branch` + `TicketAIFollowup` + `simulate_auto_handle` |
| 7. 更新工单状态 | 既有控件 | ✅ 设计遵守 | **确认 AI 不自动改 status**（文档与 `confirm_analysis` 注释明确） |

### 1.2 AI 结果 7 类字段

| 字段 | DocType / API | 前端展示 |
|------|---------------|----------|
| 分类 | `category` + `mapped_ticket_type` | ✅ ResultForm |
| 优先级 | `priority` | ✅ |
| 摘要 | `summary` | ✅ |
| 置信度 | `confidence`（0～1） | ✅（UI 百分比展示） |
| 证据 | `evidence` JSON | ✅ EvidenceList |
| 建议角色/团队/人员 | `suggested_role/team/agent` | ✅ |
| 是否可自动处理 | `auto_handleable` + plan/missing/handoff | ✅ Followup |

### 1.3 Epic 验收标准（代码层判断）

| 验收项 | 代码层 | 环境层 |
|--------|--------|--------|
| 现有 Helpdesk 上演示主流程 | 面板已挂详情页 | 需 migrate + 登录演示 |
| 7 类字段齐全可展示 | ✅ 模型+UI | 需 UI 点验 |
| 人工修改后确认采纳 | ✅ 白名单编辑 + 选择性写回 | 需点验 |
| 高置信自动 / 低置信转人工分支 | ✅ Mock 登录/退款/通用 | 需样例数据 |
| 基本测试 + 说明文档 | ✅ `test_ai.py` + `test_hd_ai_analysis.py` + `docs/AI_WORKBENCH.md` | 需 `bench run-tests` |

---

## 2. 子 Issue #2～#10 落地明细

### #2 数据模型 — ✅ 已落地

**路径：**

- `helpdesk/helpdesk/doctype/hd_ai_analysis/hd_ai_analysis.json`
- `helpdesk/helpdesk/doctype/hd_ai_analysis/hd_ai_analysis.py`
- `helpdesk/helpdesk/doctype/hd_ai_analysis/test_hd_ai_analysis.py`

**对照设计：**

| 决策 | 本机 |
|------|------|
| 独立 DocType，不塞满 Ticket | ✅ `HD AI Analysis` |
| 状态机 Pending/Completed/Failed/Confirmed/Rejected | ✅ Select options + 模型校验 |
| 7 类字段 + original_result / is_edited / 审计 | ✅ field_order 齐全 |
| 权限 Agent / Agent Manager / System Manager | ✅ permissions 配置 |
| 不在 Ticket 双写 latest 指针 | ✅ 未见 Ticket 字段改动 |

**小缺口：** 客户门户“不可访问”依赖角色权限；API 另有 `@agent_only` + Ticket permission 双检（见 service）。

---

### #3 分析 API（Mock 优先）— ✅ 已落地

**路径：**

- `helpdesk/api/ai.py` — whitelist 入口
- `helpdesk/ai/service.py` — 编排
- `helpdesk/ai/analyzers/mock.py` — 确定性规则
- `helpdesk/ai/validators.py` — 证据/退款缺单号等补充验证
- `helpdesk/ai/context.py` — 工单上下文

**API 契约：**

| 方法 | 状态 |
|------|------|
| `analyze_ticket` | ✅ |
| `get_latest_analysis` / `get_analysis` 别名 | ✅ |
| `list_analyses` | ✅ |

**Mock 三类场景：**

| 场景 | 关键词/规则 | 预期分支 |
|------|-------------|----------|
| 登录异常完整 | login/密码等 | 高置信 + `auto_handle` |
| 退款缺订单号 | 退款且无订单模式 | `missing_info` + 低置信 |
| 通用兜底 | 未命中 | 低置信 + manual/low_confidence |

**重复 Pending：** `get_pending_for_ticket` 复用，避免连点多条 Pending。  
**同步执行：** 无队列，符合 P0。

---

### #4 确认写回 — ✅ 已落地

**路径：** `helpdesk/ai/service.py`（`update_analysis_fields` / `confirm_analysis` / `reject_analysis`）

| 规则 | 本机 |
|------|------|
| 仅 Completed 可编辑 | ✅ |
| 白名单字段 | ✅ `EDITABLE_FIELDS` |
| 选择性 `apply_fields` 写回 | ✅ `APPLY_FIELD_MAP` |
| 不自动改 ticket status | ✅ 文档与 API 注释 |
| suggested_agent 走分配能力 | ✅（service 内处理，默认可选） |
| original_result 不被覆盖 | ✅ 模型层有测试 |
| 幂等 / 终态不可再改 | ✅ 状态校验 + 测试覆盖 |

写回映射：

| Analysis | Ticket |
|----------|--------|
| `mapped_ticket_type` | `ticket_type` |
| `priority` | `priority` |
| `summary` | `summary` |
| `suggested_team` | `agent_group` |

---

### #5 详情页 AI 面板 — ✅ 已落地

**路径：**

- 挂载：`desk/src/components/ticket-agent/TicketDetailsTab.vue`（`TicketAIWorkbench`）
- 组件：`desk/src/components/ticket-agent/ai/*`
- 状态与 API：`desk/src/composables/useTicketAI.ts`
- 类型：`desk/src/types/ai.ts`
- 中文：`helpdesk/locale/zh.po`（AI Workbench 段）

**UI 状态（代码存在）：** empty / loading / completed / failed / confirmed / rejected、编辑态、确认前字段勾选、重新分析。

**未在本审查验证：** 移动端体验、键盘焦点、窄侧栏滚动、`yarn build`。

---

### #6 自动处理 / 转人工分支 — ✅ 已落地

**路径：**

- 后端：`helpdesk/ai/validators.py` → `decide_branch`
- 序列化附带：`service._serialize` 注入 `branch`
- 模拟：`simulate_auto_handle`（无副作用）
- 前端：`TicketAIFollowup.vue`

**判定顺序（与 Issue 一致）：**

1. `missing_info` 非空 → `missing_info`
2. `confidence` < 阈值（默认 0.70，Settings 可配）→ `low_confidence`
3. `auto_handleable` 且有 plan → `auto_handle`
4. 其他 → `manual`

登录 Mock 的 plan 明确标注 **模拟 / 不真实改密发信**。

---

### #7 测试 — ✅ 代码已写 / ⚠ 本机未跑

| 文件 | 约行数 | 覆盖点（抽样） |
|------|--------|----------------|
| `helpdesk/api/test_ai.py` | ~297 | 三类 Mock、证据、Pending 复用、更新确认驳回、simulate、decide_branch、settings、LLM 缺 key 降级 |
| `helpdesk/helpdesk/doctype/hd_ai_analysis/test_hd_ai_analysis.py` | ~221 | 7 字段、多次历史、confidence、JSON、状态机、original_result、Failed |

文档给出的命令：

```bash
bench --site test_site run-tests --app helpdesk --module helpdesk.api.test_ai
bench --site test_site run-tests --app helpdesk --module helpdesk.helpdesk.doctype.hd_ai_analysis.test_hd_ai_analysis
```

**本审查未执行上述命令。**

---

### #8 交付文档 — ✅ 已落地

- `docs/AI_WORKBENCH.md`（已 commit：`fb29500ee`）
- 含架构、状态机、API、安装 migrate、测试命令、演示数据、边界说明

另有参考分析（未 commit）：

- `docs/change/2026-07-11-chatwoot-automation-ai-captain-analysis.md`（Chatwoot Captain 调研，非 #1 必需交付物）

---

### #9 样例数据 — ✅ 已落地

- `helpdesk/ai/demo_fixtures.py` — 固定 D1/D2/D3 等语义
- `helpdesk/ai/seed_demo.py` — `execute helpdesk.ai.seed_demo.run` 类入口
- 前缀 `[AI-Demo]`，测试与 fixture 共用

---

### #10 真实 LLM（P1）— ✅ 骨架已落地 / ⚠ 需配置才算“可用”

| 项 | 状态 |
|----|------|
| `HD AI Settings` Single | ✅ mode/provider/model/api_key(Password)/base_url/timeout/threshold/fallback |
| `helpdesk/ai/analyzers/llm.py` | ✅ 结构化解析 + 失败可降级 Mock |
| `helpdesk/ai/client.py` | ✅ chat_completion 封装 |
| 默认 Mock 无密钥可演示 | ✅ |
| 密钥不进前端 public settings | ✅ `get_ai_settings_public` |
| 生产级 LLM 实测 | ⚠ 未在本审查验证 |

---

## 3. 本机 Git 与远程对照（关键）

### 3.1 相对远程

```
develop...origin/develop [ahead 7]
```

**7 个本地 commit（尚未 push）：**

| Commit | 说明 | 对应 Issue |
|--------|------|------------|
| `edb6a5a88` | HD AI Analysis doctype | #2 |
| `5526e6cb7` | service / mock / LLM / APIs | #3 #4 #6 #10 部分 |
| `36f998907` | tests + demo fixtures | #7 #9 |
| `276906899` | HD AI Settings | #10 |
| `315baad29` | 前端 AI 面板 | #5 #6 |
| `fb29500ee` | `docs/AI_WORKBENCH.md` | #8 |
| `285b5b70b` | zh.po AI 文案 | #5 i18n |

### 3.2 仍未入库（untracked）

| 路径 | 与 #1 关系 |
|------|------------|
| `docs/change/` | 分析/审查文档，非 Epic 必需，但建议另提交流程 |
| `exeample/` | Chatwoot 参考树，**不应默认 push**（体积大） |
| `scripts/*.json` | 汉化扫描产物，与 #1 弱相关 |

### 3.3 Issue 评论 vs 本机事实

Issue 评论写「P0 #2–#9 与 P1 #10 均已在工作区实现并关闭」。  
**代码事实支持该说法**；但：

1. **实现仍主要在本地 commit，未确认已 push 到 GitHub 默认分支**（当前 ahead 7）。  
2. 评论中的 bench 验收清单（migrate / tests / seed / UI）**本审查没有证据证明本机已跑通**。  
3. 因此：**“Issue 关闭”≠“远程仓库已包含代码”≠“环境验收通过”。**

---

## 4. 完成度评分

| 子项 | 代码实现 | 测试代码 | 文档 | 推送远程 | 环境验收 |
|------|----------|----------|------|----------|----------|
| #2 模型 | 100% | 有 | 有 | ❌ 未 push | 未验 |
| #3 API Mock | 100% | 有 | 有 | ❌ | 未验 |
| #4 确认写回 | 100% | 有 | 有 | ❌ | 未验 |
| #5 前端面板 | ~95% | 无前端单测（设计允许） | 有 | ❌ | 未验 |
| #6 分支建议 | 100% | 有 | 有 | ❌ | 未验 |
| #7 测试 | 用例已写 | — | 有 | ❌ | **未跑** |
| #8 文档 | 100% | — | ✅ | ❌ | — |
| #9 样例 | 100% | fixture 断言 | 有 | ❌ | seed 未跑 |
| #10 LLM | ~85% 骨架 | 缺 key 降级测 | 有 | ❌ | 真 LLM 未验 |

**综合：**

- **设计落地（工作区代码）：~95%**
- **远程同步：0%（相对 origin 仍 ahead）**
- **运行验收：未知（未执行）**

---

## 5. 与 Epic 原文「现状表」的更新

Issue 正文在创建时写的是全部 ❌。按本机代码应更新为：

| 能力 | 创建时 | 本机现况（代码） |
|------|--------|------------------|
| 创建/列表/详情/改状态 | ✅ | ✅ |
| 中文汉化 | ✅ 一轮 | ✅ + AI 面板文案 |
| 触发 AI 分析 | ❌ | ✅ 代码已有 |
| AI 结果结构化展示 | ❌ | ✅ |
| 证据/补充验证 | ❌ | ✅ validators + evidence |
| 人工确认或修改 | ❌ | ✅ |
| 自动处理/修复建议 | ❌ | ✅ 建议/模拟 only |
| 信息不足/转人工 | ❌ | ✅ |
| AI 链路测试 + 交付说明 | ❌ | ✅ 代码+文档；运行未验 |

---

## 6. 风险与缺口清单

### 6.1 必须处理

1. **Push 缺失：** 7 个 AI commit 仅在本地；他人/CI/Issue 关闭状态容易造成“以为线上已有”的错觉。  
2. **migrate 未验证：** DocType 未 migrate 前 UI/API 会失败。  
3. **测试未在本审查执行：** 存在集成环境差异风险（Priority/Team 名称、create_agent 等）。

### 6.2 建议处理

4. `docs/change/` 审查与 Captain 分析未入库。  
5. `exeample/` 勿误提交。  
6. 前端无自动化单测（Issue 允许），但建议至少跑一次 `yarn build`。  
7. LLM 真连仅骨架：演示应坚持 Mock 默认路径。  
8. Agent 角色对 Analysis 无 `delete` 权限（仅 write）——符合“历史可审计”，需知悉。

### 6.3 设计符合度亮点（可保留）

- AI 建议与 Ticket 写回分离，确认前不污染业务字段  
- 确认不改 status，避免硬编码状态机  
- Mock 确定性 + 证据引用真实输入  
- 自动处理仅模拟，文案防伪装  
- LLM 降级标注 `degraded_to=Mock`  

---

## 7. 建议的“收口动作”清单

按优先级：

1. **Push 7 个 commit 到 `origin/develop`**（或开 PR），让 GitHub 与 Issue 关闭状态一致。  
2. 本机 bench：
   ```bash
   bench --site <site> migrate
   bench --site <site> clear-cache
   bench --site <site> run-tests --app helpdesk --module helpdesk.api.test_ai
   bench --site <site> run-tests --app helpdesk --module helpdesk.helpdesk.doctype.hd_ai_analysis.test_hd_ai_analysis
   ```
3. `execute helpdesk.ai.seed_demo.run`（或文档步骤）准备 D1/D2/D3。  
4. 坐席打开 demo 工单，走通：分析 → 证据 → 编辑 → 预览写回 → 确认 → 看 Followup → 手动改 status。  
5. （可选）提交 `docs/change/` 审查文档；忽略 `exeample/`。  
6. 环境验收通过后，在 #1 补一条 **“远程 commit SHA + 测试绿 + 演示通过”** 的评论，真正闭环。

---

## 8. 关键路径速查

```
helpdesk/helpdesk/doctype/hd_ai_analysis/
helpdesk/helpdesk/doctype/hd_ai_settings/
helpdesk/api/ai.py
helpdesk/api/test_ai.py
helpdesk/ai/service.py
helpdesk/ai/analyzers/mock.py
helpdesk/ai/analyzers/llm.py
helpdesk/ai/validators.py
helpdesk/ai/demo_fixtures.py
helpdesk/ai/seed_demo.py
desk/src/components/ticket-agent/TicketDetailsTab.vue
desk/src/components/ticket-agent/ai/
desk/src/composables/useTicketAI.ts
desk/src/types/ai.ts
docs/AI_WORKBENCH.md
helpdesk/locale/zh.po   # AI Workbench 段
```

---

## 9. 最终判定

| 问题 | 答案 |
|------|------|
| Issue #1 在本机**代码是否落地**？ | **是，P0 全套 + P1 LLM 骨架已在工作区并 commit** |
| 是否已经**推到 GitHub**？ | **否，develop 相对 origin ahead 7** |
| 是否已经**环境验收通过**？ | **本审查无法确认；需 migrate + tests + UI** |
| 能否认为 Epic 在工程上完成？ | **代码完成度高；发布/验收闭环未完成** |

**建议表述：**  
> AI 工单工作台 MVP 已在本地实现并通过设计对照审查；待 push 与 bench 验收后，Issue #1 可从“代码完成”升级为“交付完成”。
