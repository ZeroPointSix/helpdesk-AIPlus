# AI 工单处理工作台（MVP）

对齐 Epic [#1](https://github.com/ZeroPointSix/helpdesk-AIPlus/issues/1) / Linear ZER-52。  
基线分支：`develop`。

## 1. 目标与边界

在现有 Frappe Helpdesk 上提供**最小可用**的 AI 工单分析闭环：

1. 创建/打开工单  
2. 触发 AI 分析（默认确定性 Mock，无需 API Key）  
3. 查看结构化结论与证据  
4. 人工编辑后确认采纳 / 驳回  
5. 查看自动处理建议或信息不足/转人工分支  
6. **显式**用现有控件更新工单状态（确认 AI **不会**自动改 status）

**明确不做（P0）：**

- 真实自动修复（改密、退款、发信、跑脚本）  
- 完整 Captain / Copilot 对话式移植  
- 客户门户 AI 入口  
- 生产安装默认写入 demo 数据  

可选增强（P1 / #10）：真实 LLM provider + `HD AI Settings`。

## 2. 架构一览

```text
desk/src/components/ticket-agent/
  TicketDetailsTab.vue          # 挂载 AI 区块
  ai/TicketAIWorkbench.vue      # 面板容器
  ai/TicketAIResultForm.vue
  ai/TicketAIEvidenceList.vue
  ai/TicketAIFollowup.vue       # #6 分支展示
  ai/TicketAIStatusBadge.vue
desk/src/composables/useTicketAI.ts
desk/src/types/ai.ts

helpdesk/helpdesk/doctype/hd_ai_analysis/   # #2 DocType
helpdesk/api/ai.py                          # whitelist API
helpdesk/ai/
  service.py        # 编排：analyze / update / confirm / reject / simulate
  context.py
  validators.py     # 补充验证 + decide_branch
  types.py
  demo_fixtures.py  # #9 固定样例
  seed_demo.py
  analyzers/
    mock.py         # 默认
    llm.py          # 可选骨架，可降级 Mock
```

### 设计原则（对照 Chatwoot / clawbot 分析）

| 原则 | 落地 |
|------|------|
| AI 建议与人工审核分离 | 独立 `HD AI Analysis`，确认前不写 Ticket 业务字段 |
| 多次历史可审计 | 每次分析新建一行；`original_result` 冻结 |
| 自动 Bot ≠ 坐席辅助 | 本 MVP 只做坐席侧建议，不自动对外发消息 |
| Mock 可演示 | 无密钥默认同步 Mock |

## 3. 数据模型：`HD AI Analysis`

状态机：

```text
Pending → Completed / Failed
Completed → Confirmed / Rejected
Confirmed / Rejected / Failed 终态只读
```

核心字段（含题目 7 类 + 分支预埋）：

- 分类 `category` / `mapped_ticket_type`
- 优先级 `priority`
- 摘要 `summary`
- 置信度 `confidence`（0～1）
- 证据 `evidence`（JSON 数组）
- 建议角色/团队/人员 `suggested_role` / `suggested_team` / `suggested_agent`
- 是否可自动处理 `auto_handleable` + `auto_handle_plan` / `missing_info` / `handoff_reason`
- 审计：`original_result`、`is_edited`、`confirmed_by`、`confirmed_at`、`rejection_reason`

权限：System Manager / Agent Manager / Agent；客户门户无权限。  
所有 API 仍校验关联 **HD Ticket** 的 read/write。

本期**不**在 Ticket 上双写 `latest_ai_analysis` 指针。

## 4. API

均需坐席（`@agent_only`）。

| 方法 | 路径 | 说明 |
|------|------|------|
| 分析 | `helpdesk.api.ai.analyze_ticket` | 建/复用 Pending → Mock/LLM → Completed |
| 最新 | `helpdesk.api.ai.get_latest_analysis` | 按 ticket + creation desc |
| 历史 | `helpdesk.api.ai.list_analyses` | limit 默认 20，最大 100 |
| 编辑 | `helpdesk.api.ai.update_analysis` | 仅 Completed；白名单字段；`is_edited=1` |
| 确认 | `helpdesk.api.ai.confirm_analysis` | 选择性写回 Ticket；**不改 status**；幂等 |
| 驳回 | `helpdesk.api.ai.reject_analysis` | 不写业务字段 |
| 模拟 | `helpdesk.api.ai.simulate_auto_handle` | 只读预览，无副作用 |

### 写回映射（确认时 `apply_fields`）

| Analysis | Ticket |
|----------|--------|
| `mapped_ticket_type` | `ticket_type` |
| `priority` | `priority` |
| `summary` | `summary` |
| `suggested_team` | `agent_group` |
| `suggested_agent` | `assign_agent`（可选，默认不包含） |

无效 Link 会跳过并进入 `warnings[]`。

### 分支判定（`decide_branch`，前后端共用后端结果）

1. `missing_info` 非空 → `missing_info`  
2. `confidence` < 0.70 → `low_confidence`  
3. `auto_handleable` 且有 plan → `auto_handle`  
4. 其他 → `manual`  

## 5. 环境前提与安装

1. 基于 `develop` 安装/更新 app：

```bash
bench get-app /path/to/helpdesk-AIPlus   # 或 git pull
bench --site <site> migrate
bench --site <site> clear-cache
```

2. 前端构建：

```bash
cd apps/helpdesk   # 或本仓库根目录
yarn install
cd desk && yarn build
# 开发：yarn dev
```

3. 后端测试（仓库既有入口）：

```bash
bench --site test_site run-tests --app helpdesk --module helpdesk.api.test_ai
bench --site test_site run-tests --app helpdesk --module helpdesk.helpdesk.doctype.hd_ai_analysis.test_hd_ai_analysis
```

## 6. 演示数据（#9）

固定样例在 `helpdesk/ai/demo_fixtures.py`，subject 前缀 `[AI-Demo]`。

```bash
# 仅创建工单（推荐：现场点「AI 分析」）
bench --site <site> execute helpdesk.ai.seed_demo.run

# 重建
bench --site <site> execute helpdesk.ai.seed_demo.run --kwargs "{'reset': True}"

# 同时预跑分析
bench --site <site> execute helpdesk.ai.seed_demo.run --kwargs "{'with_analysis': True}"
```

| ID | 场景 | 期望分支 |
|----|------|----------|
| D1 | 登录异常（信息完整） | `auto_handle` |
| D2 | 退款缺订单号 | `missing_info` |
| D3 | 通用未分类 | `low_confidence` |
| D4 | 发票 | `manual` |
| D5 | 物流 | `manual` |

**不要**在生产 install 钩子里自动 seed。

## 7. 完整演示主流程

1. `seed_demo.run` 或手工建工单  
2. 坐席打开工单详情 → 右侧 **AI Workbench**  
3. 点击 **AI Analysis** → 查看 7 类字段与证据  
4. **Edit** 修改摘要/优先级 → **Save changes**（或确认时一并提交 draft）  
5. **Confirm & Apply** → 勾选写回字段预览 → 确认  
6. 观察 Ticket 字段与 Activity/内部评论；**状态仍用原有状态控件**手动改  
7. D1：**Simulate auto-handle** 只展示模拟结果  
8. D2：查看缺订单号清单与转人工建议  
9. **Re-analyze** 生成新历史记录，旧 Confirmed 保留  

## 8. Mock 与 LLM（#10）

- 默认 `source=Mock`，关键词规则见 `helpdesk/ai/analyzers/mock.py`  
- 验证层 `validators.py`：退款缺单号降置信；登录推技术支持  
- Single DocType：**HD AI Settings**（仅 System Manager）  
  - `enabled` / `mode`（Mock|LLM）/ `provider` / `model` / `base_url` / `timeout_seconds`  
  - `api_key`（Password）/ `fallback_to_mock` / `confidence_threshold`  
- 也可使用 `site_config`：

```json
{
  "helpdesk_ai_enabled": 1,
  "helpdesk_ai_provider": "llm",
  "helpdesk_ai_api_key": "...",
  "helpdesk_ai_model": "gpt-4.1-mini",
  "helpdesk_ai_base_url": "https://api.openai.com/v1",
  "helpdesk_ai_timeout": 30,
  "helpdesk_ai_fallback_to_mock": 1
}
```

- 配置优先级：`HD AI Settings` > `frappe.conf` > 默认 Mock  
- LLM 失败且 `fallback_to_mock=1`：结果 `source=Mock`，`analyzer`/`raw` 标注降级原因（**不**伪装成 LLM 成功）  
- 密钥不进入 API 响应、`raw_response` 或前端；公开配置见 `helpdesk.api.ai.get_ai_settings_public`  
- 将工单正文发送到外部模型前请自行评估合规要求

## 9. 验收对照

- [x] 独立 `HD AI Analysis` 可多次历史  
- [x] 7 类字段 + 分支字段可持久化  
- [x] Mock 三类场景确定可演示  
- [x] 确认选择性写回且不改 status  
- [x] 详情页闭环 + 分支 UI  
- [x] 测试模块 + 本文档 + seed  

## 10. 相关 Issue

| Issue | 内容 |
|-------|------|
| #2 | 数据模型 |
| #3 | 分析 API / Mock |
| #4 | 确认/驳回写回 |
| #5 | 详情页面板 |
| #6 | 自动处理/转人工分支 |
| #7 | 测试 |
| #8 | 本文档 |
| #9 | 样例数据 |
| #10 | 真实 LLM / HD AI Settings（P1，已落地可降级接入） |
