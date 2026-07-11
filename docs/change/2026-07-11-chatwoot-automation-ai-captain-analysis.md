# Chatwoot「自动化与 AI 客服」模块深度分析与主项目迁移报告

| 字段 | 内容 |
|------|------|
| 日期 | 2026-07-11 |
| 分析对象 | `exeample/chatwoot`（目录名拼写为 `exeample`）中「6. 自动化与 AI 客服」 |
| 目标系统 | 主项目 Frappe Helpdesk（`helpdesk/` + `desk/`） |
| 目的 | 厘清 Chatwoot Captain / 集成 / 自动化实现，形成可落地的移植路径 |
| 状态 | 分析完成（尚未开始代码移植） |

---

## 0. 结论摘要（先看这个）

Chatwoot 的「自动化与 AI 客服」**不是单一模块**，而是三条可叠加能力线：

| 能力线 | 代表 | 定位 |
|--------|------|------|
| **A. 自动客服 Agent（Bot）** | Captain Assistant + Dialogflow | 在会话 `pending` 态自动回复 / handoff / resolve |
| **B. 坐席辅助（Agent Assist）** | Captain Tasks + Copilot | 人工写回复时：建议回复、摘要、改写、侧栏问答 |
| **C. 集成与编排** | App+Hook、Automation Rules、Slack/Shopify/Linear/Translate | 外部系统对接 + 确定性 if-then 规则 |

**主项目现状：**

- 已有：工单、SLA、Assignment Rule、知识库、Saved Reply、邮件工作流、ERPNext/电话集成
- **没有**：LLM / Embedding / Copilot / AI 自动回复 / Dialogflow / 通用 Integration Hook 框架

**迁移本质：** 在 Frappe 工单模型上**新建 AI 子系统**，复用领域切分与 Prompt/工具契约，**不要照搬 Rails/pgvector/enterprise prepend**。

**推荐最短路径：**

1. Phase 0 基建（AI Settings + LLM Client）
2. Phase 1 编辑器 AI（价值最快、风险最低）
3. Phase 2 Copilot 侧栏
4. Phase 3 RAG / FAQ 向量检索
5. Phase 4 工单自动助手（Bot + handoff）
6. Phase 5 集成平台化（Slack 等）与可选规则引擎

---

## 1. 产品语境：原文「6. 自动化与 AI 客服」对应什么

原文描述：

> Chatwoot 提供名为 **Captain** 的 AI 客服 Agent，可以自动处理常见问题、生成回复并降低人工客服工作量。  
> 它还支持 **Dialogflow、Slack、Shopify、Google Translate 和 Linear** 等集成。

对应代码落点：

| 产品表述 | 代码落点 |
|----------|----------|
| Captain AI Agent | `enterprise/app/models/captain/*`、`enterprise/app/services/captain/**`、`enterprise/app/jobs/captain/**` |
| 自动处理常见问题 | `ResponseBuilderJob` + FAQ 向量检索 + Scenario tools |
| 生成回复（坐席侧） | `lib/captain/*` Tasks + Copilot |
| Dialogflow | `lib/integrations/dialogflow/` + Hook |
| Slack | `lib/integrations/slack/**` |
| Shopify | `integrations/shopify` Controller（按需查单，非 bot） |
| Google Translate | `lib/integrations/google_translate/**` |
| Linear | `lib/integrations/linear/**` |
| 确定性自动化 | `AutomationRule`（与 AI 解耦，通过 `pending` 衔接） |

---

## 2. 总体架构

### 2.1 分层总图

```
┌─────────────────────────────────────────────────────────────────┐
│  Dashboard UI（Vue）                                             │
│  Captain 管理页 / Copilot 侧栏 / 编辑器 AI 按钮 / 集成设置         │
└───────────────────────────────┬─────────────────────────────────┘
                                │ REST API
┌───────────────────────────────▼─────────────────────────────────┐
│  Controllers                                                     │
│  captain/*  ·  integrations/*  ·  automation                     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐     ┌─────────────────┐     ┌──────────────────┐
│ Captain Core  │     │ Integration     │     │ Automation Rules │
│ (Enterprise)  │     │ App + Hook      │     │ (确定性 if-then) │
│ Agent/Copilot │     │ HookJob 分发    │     │ 可设 pending     │
│ FAQ/Embedding │     │ Dialogflow/...  │     │ 触发 bot 接管    │
└───────┬───────┘     └────────┬────────┘     └────────┬─────────┘
        │                      │                       │
        └──────────────────────┼───────────────────────┘
                               ▼
                    Conversation / Message
                    status: open|pending|resolved|snoozed
                    bot_handoff! → 人工接管
```

### 2.2 关键设计原则（移植时必须保留）

1. **Bot 状态门控单一**：只在 `pending`（或等价 `bot_active`）自动回复；`bot_handoff!` 后停止。
2. **Auto-Bot 与 Agent-Assist 分离**：自动对外发消息 ≠ 坐席侧草稿/侧栏问答。
3. **Automation 不内嵌 LLM**：规则只做状态/分派/标签；通过把会话设为 bot 态衔接 AI。
4. **集成用 Catalog + Instance + Event Runner**：不要每个 SaaS 各写一套事件总线。
5. **知识 FAQ 化**：Document → Q/A → Embedding → TopK，比整页 chunk RAG 更适合客服。

---

## 3. Captain 核心实现详解

### 3.1 目录地图

```
exeample/chatwoot/
├── enterprise/app/models/captain/          # Assistant/Document/Response/Scenario/CustomTool
├── enterprise/app/models/captain_inbox.rb  # Assistant ↔ Inbox
├── enterprise/app/services/captain/
│   ├── assistant/agent_runner_service.rb   # V2 multi-agent
│   ├── copilot/chat_service.rb             # 坐席侧
│   ├── llm/*                               # FAQ/Embedding/Chat/...
│   ├── tools/*                             # 工具实现
│   └── tool_registry_service.rb
├── enterprise/app/jobs/captain/**          # 异步：回复/爬虫/embedding/sync
├── enterprise/app/services/enterprise/message_templates/
│   └── hook_execution_service.rb           # ★ 自动回复主触发入口
├── enterprise/lib/captain/                 # V2 tools + prompts
├── lib/captain/                            # Tasks：reply/summary/rewrite/...
├── lib/integrations/captain/               # Legacy 外部 Captain HTTP
├── app/controllers/api/v1/accounts/captain/
├── app/javascript/dashboard/
│   ├── routes/dashboard/captain/           # 管理 UI
│   ├── components-next/captain/            # 组件
│   └── api/captain/                        # 前端 API
├── config/agents/tools.yml                 # 内置 tool 元数据
└── config/installation_config.yml          # OpenAI/Firecrawl 等
```

### 3.2 领域模型（ER 文字版）

```
Account
  ├── Captain::Assistant[]          # AI 助手配置聚合根
  ├── Captain::Document[]           # 知识文档（URL/PDF）
  ├── Captain::CustomTool[]         # 账号级 HTTP 工具（最多 15）
  └── CopilotThread[]               # 坐席侧对话线程

Captain::Assistant
  ├── config jsonb                  # temperature, feature_faq, handoff_message...
  ├── response_guidelines / guardrails
  ├── Document[] / AssistantResponse[] / Scenario[]
  ├── CaptainInbox → Inbox (1:1，一个 inbox 只能绑一个 assistant)
  └── Message (as sender)           # AI 发出的消息以 Assistant 为 sender

Captain::AssistantResponse          # 实质是 FAQ 知识单元，不是聊天日志
  ├── question / answer
  ├── embedding vector(1536)        # pgvector + cosine neighbor
  ├── status: pending | approved
  └── documentable: Document | Conversation

Captain::Scenario                   # V2 子 Agent
  ├── instruction + tools[]         # instruction 内 tool://id 引用
  └── 与主 Assistant 双向 handoff

Captain::CustomTool
  ├── endpoint_url / http_method / auth_* / param_schema
  └── request_template / response_template (Liquid)
```

**关键不变量：**

- `inbox.captain_active?` = 已绑定 Assistant **且** 当月 responses 配额 > 0
- 自动回复成功 → `increment_response_usage`；handoff 通常不计费
- `AssistantResponse` 是检索单元，不是一次对话的日志

### 3.3 主链路：用户消息 → AI 回复

```
Message.create (客户 incoming)
  → Message#execute_message_template_hooks
  → MessageTemplates::HookExecutionService#perform
  → Enterprise::...::HookExecutionService#trigger_templates
       条件: conversation.pending?
             && message.incoming?
             && inbox.captain_assistant.present?
       ├─ !captain_active? → 发转人工文案 + bot_handoff!
       └─ active → ResponseBuilderJob.perform_later(conversation, assistant)
                    （有附件则 delay 1~5s 等 ActiveStorage）

ResponseBuilderJob
  ├─ 再次确认仍 pending
  ├─ feature captain_integration_v2?
  │    YES → AgentRunnerService（multi-agent, max_turns≈10）
  │    NO  → AssistantChatService（单 agent + tools）
  │          + 可选 ActionClassifier / FalsePromiseHandler
  └─ process_response
       ├─ handoff → 文案 + bot_handoff! → status=open
       └─ 否则 create outgoing Message(sender=assistant) + 计费
```

**关键源码：**

| 文件 | 作用 |
|------|------|
| `enterprise/.../message_templates/hook_execution_service.rb` | 主触发；抑制 greeting/OOO 与 Captain 冲突 |
| `enterprise/.../jobs/captain/conversation/response_builder_job.rb` | 生成与落库 |
| `enterprise/.../services/captain/assistant/agent_runner_service.rb` | V2 runner |
| `enterprise/.../services/captain/llm/assistant_chat_service.rb` | V1 chat |
| `enterprise/app/models/enterprise/inbox.rb` | `captain_active?` |
| `app/models/conversation.rb` | `pending` / `bot_handoff!` |

触发条件摘录（enterprise hook）：

```ruby
def should_process_captain_response?
  conversation.pending? && message.incoming? && inbox.captain_assistant.present?
end
```

### 3.4 人工打断

坐席在 pending 会话发出**非 private** 人工回复时，enterprise Message 扩展会把会话 `open!`，阻止 AI 继续自动回复。

### 3.5 会话结束后的学习闭环

`CaptainListener#conversation_resolved`：

- `feature_memory` → 联系人记忆（ContactNotes）
- `feature_faq` → 从对话抽 FAQ（status=pending，需审批）+ 向量去重

### 3.6 知识流水线（Document → FAQ → Embedding → 检索）

```
创建 Document (URL / PDF)
  → CrawlJob
      ├─ PDF → PdfProcessingService
      ├─ Firecrawl（有 API Key）
      └─ SimplePageCrawl 多页解析
  → content 就绪
  → Documents::ResponseBuilderJob
      → FaqGeneratorService / PaginatedFaqGeneratorService
      → AssistantResponse(question, answer, approved)
  → UpdateEmbeddingJob → vector(1536)

检索:
  query → EmbeddingService → nearest_neighbors(cosine, limit 5)
  V2 FaqLookupTool 仅搜 approved
```

自动同步（可选 feature `captain_document_auto_sync`）：定时 re-fetch → fingerprint 变化则重建 FAQ。

### 3.7 工具系统

**两套并存（历史包袱）：**

| | V1 | V2（`captain_integration_v2`） |
|--|----|-------------------------------|
| 运行时 | RubyLLM chat + tools | `agents` gem multi-agent |
| 知识检索 | SearchDocumentationService | FaqLookupTool |
| 转人工 | 模型输出 `conversation_handoff` / classifier | 显式 HandoffTool |
| 场景 | 无 | Scenario 作为 sub-agent |

**内置 tools**（`config/agents/tools.yml`）：

- `faq_lookup`、`handoff`、`resolve_conversation`
- `add_contact_note`、`add_private_note`、`update_priority`、`add_label_to_conversation`

**Custom HTTP Tool：**

- Liquid 渲染 URL/body/response
- auth: none / bearer / basic / api_key
- `SafeFetch` 防 SSRF、超时与大小限制
- 注入 `X-Chatwoot-Account-Id` 等 metadata headers

**V2 主 Agent 默认只挂：** `FaqLookupTool` + `HandoffTool`；业务工具通过 Scenario 挂载。

### 3.8 Copilot vs 自动 Agent

| 维度 | 自动 Agent | Copilot |
|------|------------|---------|
| 触发 | 客户消息 + inbox 绑定 + pending | 坐席 UI 主动 |
| 输出 | Conversation Message（对外） | CopilotMessage（侧栏，不对客） |
| 改会话状态 | 可 handoff / resolve / 改标签优先级 | 基本只读查询 |
| Tools | FAQ + handoff + scenario | 搜会话/联系人/文章/Linear |
| 计费 | 成功自动回复 | 每次 generate |

一句话：**Agent 替代/前置机器人；Copilot 是坐席侧边助手。**

### 3.9 Captain Tasks（编辑器 AI）

入口：`Api::V1::Accounts::Captain::TasksController`  
基类：`lib/captain/base_task_service.rb`  
能力：

- reply_suggestion / summary / rewrite / fix_spelling_grammar / improve
- label_suggestion / follow_up / csat_utility_analysis / overview_summary

Prompt 模板：`lib/integrations/openai/openai_prompts/*.liquid`

凭证优先级：

1. 账号级 OpenAI Hook API Key（若配置）
2. 系统级 `CAPTAIN_OPEN_AI_API_KEY`

> 注意：OpenAI 已**不再**走 HookJob 做 bot；Hook 仅作密钥与 label 偏好配置源。`Hook#process_event` 对 openai 已 stub。

### 3.10 Feature Flags / 配置 / 外部依赖

| 配置/Flag | 作用 |
|-----------|------|
| `captain_integration` | 总开关 |
| `captain_integration_v2` | multi-agent |
| `captain_tasks` | 编辑器 Tasks + 智能 auto-resolve |
| `captain_document_auto_sync` | 文档自动同步 |
| `custom_tools` | V1 自定义工具 |
| `CAPTAIN_OPEN_AI_API_KEY/MODEL/ENDPOINT` | LLM |
| `CAPTAIN_EMBEDDING_MODEL` | 默认 text-embedding-3-small |
| `CAPTAIN_FIRECRAWL_API_KEY` | 爬虫 |
| `CAPTAIN_CLOUD_PLAN_LIMITS` | 配额 |

外部依赖：OpenAI 兼容 API、PostgreSQL+pgvector、可选 Firecrawl、可选 Langfuse/OTel、可选 Linear。

---

## 4. 集成体系（Dialogflow / Slack / Shopify / Translate / Linear）

### 4.1 通用框架：App + Hook + Event + Job

| 层 | 类 | 存储 | 职责 |
|----|-----|------|------|
| Catalog | `Integrations::App` | YAML `config/integration/apps.yml` | 元数据、schema、hook_type、feature_flag |
| Instance | `Integrations::Hook` | DB `integrations_hooks` | token/settings/status/reference_id |
| Listener | `HookListener` | — | 领域事件 → 过滤 → 入队 |
| Runner | `HookJob` | Sidekiq | `app_id → processor` 分发 |

**HookJob 已注册处理器：**

```ruby
INTEGRATION_PROCESSORS = {
  'slack' => :process_slack_integration,
  'dialogflow' => :process_dialogflow_integration,
  'google_translate' => :google_translate_integration,
  'leadsquared' => :process_leadsquared_integration_with_lock,
  'linear' => :process_linear_integration
}.freeze
```

**不在 HookJob 内的：**

- **Captain 内嵌 Agent** → MessageTemplates Hook → ResponseBuilderJob
- **OpenAI Tasks** → Captain Tasks API
- **Shopify** → 前端按需 API 查订单

**Bot 基类门控**（`Integrations::BotProcessorService`）：

- 非 private、reportable、**conversation.pending?**
- action: `handoff` → `bot_handoff!`；`resolve` → `resolved!`

### 4.2 Dialogflow

| 项 | 说明 |
|----|------|
| 类型 | inbox 级 hook，允许多 hook |
| 触发 | message.created / updated |
| 流程 | detect_intent → fulfillment → 发消息或 handoff/resolve |
| 鉴权 | GCP service account JSON + project_id + region |
| 失败 | PermissionDenied → disable + reauth 通知 |
| 与 Captain | 同依赖 pending；**框架无互斥锁**，同 inbox 双开可能双写 |

### 4.3 Slack

| 项 | 说明 |
|----|------|
| 定位 | 协作镜像，**非 AI** |
| 出站 | message.created → SendOnSlackService（thread_ts） |
| 入站 | Slack Events → webhooks → IncomingMessageBuilder |
| 防环 | `external_source_id_slack` / `cw-origin-...` |
| OAuth | 创建时 disabled，选 channel 后 enabled |

### 4.4 Shopify

| 项 | 说明 |
|----|------|
| 定位 | 联系人侧栏查 customers/orders |
| 触发 | **不走 HookJob**，前端主动 GET |
| OAuth | shop domain + token 存 Hook |

### 4.5 Google Translate

| 项 | 说明 |
|----|------|
| 自动 | message.created → DetectLanguage → 写 conversation_language |
| 按需 | ProcessorService 翻译消息内容 |
| 与 AI | 为 Dialogflow `language_code: auto` 等提供语言信号 |

### 4.6 Linear

| 项 | 说明 |
|----|------|
| 主动 | teams / create_issue / link / unlink / search API |
| 自动 | private note 中解析 Linear URL → AutoLinkService |
| 与 AI | Copilot 可选 `SearchLinearIssuesService` |

### 4.7 Automation Rules 与 AI 边界

- 事件：conversation_created/opened/resolved/updated、message_created
- 动作：发消息、标签、分派、改状态（含 pending）、webhook 等——**无 LLM**
- 关系：规则可把会话设为 pending → 打开 Bot；Bot handoff 后规则可继续处理 open 会话

```
Automation（编排）──set pending──► Bot/Captain（对话执行）──handoff──► 人工
       ▲                                                      │
       └──────────── 标签/分派/webhook 等可继续 ◄──────────────┘
```

### 4.8 集成关系总图

```
                    Conversation.status
                 open / pending / resolved
                          │
     pending 自动接管      │        任意状态旁路
  ┌───────────────────────┼────────────────────────┐
  ▼                       ▼                        ▼
Dialogflow            Captain Agent             Slack 镜像
(inbox hook)          + Tasks/Copilot           Linear 自动链
Google Translate detect                         Shopify 侧栏
  │                       │
  └──── bot_handoff! ─────┘
              │
              ▼
         status=open 人工
              │
              ▼
      Automation Rules 继续
```

---

## 5. 主项目（Frappe Helpdesk）现状与 Gap

### 5.1 已有相关能力

| 模块 | 路径 | 说明 |
|------|------|------|
| 工单核心 | `helpdesk/helpdesk/doctype/hd_ticket/` | 分配、SLA、邮件、合并 |
| 全局设置 | `hd_settings` | KB 优先、自动关单、搜索权重 |
| 预设回复 | `hd_saved_reply` + `api/saved_replies.py` | Jinja 渲染，人工选用 |
| 知识库 | `hd_article*` + `api/knowledge_base.py` | 全文/Redis 检索，**非向量** |
| 搜索 | `search.py` / `search_sqlite.py` | 文章与工单关键词检索 |
| 分配 | Assignment Rule + Agent Status | 规则版智能分配 |
| 集成 | `integrations/erpnext/`、Telephony | 业务/电话，非 AI |
| 实时 | `realtime/` | Socket，可推 AI 流式 |
| 前端 | `desk/src/...` | KB、Saved Reply、Assignment 等设置 |

**全库检索结论：** `openai` / `llm` / `embedding` / `vector` / `captain` / `copilot` / `dialogflow` **均无业务实现**。

### 5.2 能力对照表

| 能力 | Chatwoot | Helpdesk 现状 | 差距 |
|------|----------|---------------|------|
| AI 助手配置 | Captain::Assistant + Inbox | 无 | **大** |
| 文档摄入 | Document 爬取/PDF | 仅人工 HD Article | **大** |
| FAQ + Embedding | AssistantResponse + pgvector | 关键词检索 | **大** |
| 会话/工单机器人 | ResponseBuilderJob | 无 bot 发消息链路 | **大** |
| 坐席 Copilot | Copilot::ChatService + 侧栏 | 无 | **大** |
| 编辑器 AI | lib/captain Tasks | 仅 Saved Reply | **大（但最易做）** |
| LLM 路由 | FeatureRouter | 无 | **中** |
| 集成框架 | App+Hook+HookJob | 零散集成 | **中-大** |
| Automation 引擎 | AutomationRule | Assignment + 邮件钩子 | **中-大** |
| Saved Reply | canned_response | **已完整** | **小** |
| 知识库门户 | Help Center | HD Article 完整 | **小-中** |
| 自动分配 | 策略/规则 | Assignment + Status **较强** | **小** |
| SLA | 有 | **成熟** | **小** |
| 实时推送 | ActionCable | Socket.IO | **小** |

### 5.3 技术栈差异影响

| 维度 | Chatwoot | Helpdesk | 移植影响 |
|------|----------|----------|----------|
| 后端 | Rails Service/Job | Frappe DocType + whitelist + enqueue | **重写 Python，迁模型与契约** |
| 前端 | Vue3 + Pinia + Tailwind | Vue3 + Pinia + **frappe-ui** | UI 可参考信息架构，组件重写 |
| 会话模型 | Conversation/Message/Inbox | Ticket/Communication | Bot 绑定 Team/Email Account |
| 向量库 | Postgres pgvector | MariaDB 默认 | **需外部向量方案或降级** |
| Prompt | Liquid | Jinja（Frappe 已有） | 迁移成本低 |
| 异步 | Sidekiq | `frappe.enqueue` | 直接映射 |
| 企业拆分 | `enterprise/` | 单 app | 用功能开关代替目录拆分 |

---

## 6. 推荐迁移落点（主项目）

### 6.1 建议新增结构

```
helpdesk/
  ai/                              # LLM 基础设施
    client.py                      # chat / embed 统一客户端
    feature_router.py
    prompts/                       # Jinja 化后的 prompt
    formatters/
      ticket_context.py            # Ticket+Communication → messages[]
    instrumentation.py
  helpdesk/doctype/
    hd_ai_settings/                # Single：密钥、模型、开关
    hd_ai_assistant/               # 对齐 Assistant
    hd_ai_document/                # 对齐 Document（Phase 3）
    hd_ai_response/                # FAQ 单元（Phase 3）
    hd_ai_copilot_thread/          # 可选
    hd_ai_copilot_message/
    hd_integration_app/            # 可选：集成目录（或 JSON 配置）
    hd_integration_hook/           # 可选：集成实例
  api/ai/
    editor.py                      # summary/reply/rewrite
    copilot.py
    assistant.py
    documents.py
```

### 6.2 概念映射

| Chatwoot | Helpdesk 落点 |
|----------|---------------|
| Account AI 配置 | `HD AI Settings`（Single） |
| Assistant ↔ Inbox | Assistant ↔ **HD Team / Email Account** |
| Conversation | **HD Ticket** + Communication + Comment |
| Contact | Contact / HD Customer |
| Canned Response | **HD Saved Reply**（已有） |
| Articles tool | HD Article + search → 后续向量 |
| 自动回复触发 | `HDTicket` / Communication 钩子 + `frappe.enqueue` |
| 坐席 UI | `TicketAgent` 侧栏 + EmailEditor 工具条 |
| 设置 UI | `desk/.../settingsModal.ts` 增加 AI 分组 |
| Bot 状态 | 新增 `bot_status` 或 `ai_handling` 字段（对齐 pending） |
| handoff | 清除 bot 态 + 走现有 Assignment Rule |

### 6.3 抽象接口建议（Python）

```python
class IntegrationProcessor(Protocol):
    supported_events: list[str]
    def process(self, hook, event_name: str, payload: dict) -> None: ...

class BotProvider(Protocol):
    def should_handle(self, ticket, message) -> bool: ...
    def reply(self, session_id: str, content: str) -> BotResponse: ...
    # BotResponse: messages[], action: handoff | resolve | none

class AssistProvider(Protocol):
    def summarize(self, ticket_id: str) -> str: ...
    def suggest_reply(self, ticket_id: str) -> str: ...
    def suggest_labels(self, ticket_id: str) -> list[str]: ...
```

**硬约束（从 Chatwoot 验证过的）：**

1. Bot 状态门控必须单一，防止多 bot 双写  
2. Channel/Team 级 hook 必须过滤，避免串线  
3. 密钥创建时校验  
4. 鉴权失败自动 disable + 通知  
5. Auto-bot 与 Assist 分离计费/开关  
6. Automation 不直接调 LLM  
7. 协作同步（如 Slack）必须防环  
8. Prompt 与代码分离（Jinja 文件）

---

## 7. 分阶段迁移路线

### Phase 0 — 基建（约 1–2 周）

- [ ] `HD AI Settings`：API Key、Base URL、默认模型、功能开关
- [ ] `helpdesk/ai/client.py` + 日志/错误处理
- [ ] Ticket 上下文格式化：`ticket + communications → messages[]`
- [ ] Settings UI 入口（Agent Manager 权限）
- [ ] 功能开关与审计字段设计

**验收：** 管理端可保存密钥，后端可完成一次最小 chat completion 探活。

### Phase 1 — 坐席编辑器 AI（MVP，优先）

对齐 `lib/captain/*`：

- [ ] 回复建议 / 总结 / 改写 / 语法润色
- [ ] API：`helpdesk.api.ai.editor.*`
- [ ] UI：`EmailEditor` / 工单编辑器工具条
- [ ] 结果插入编辑器；可选「存为 Saved Reply」

**不依赖向量库。** 风险最低、坐席体感最强。

### Phase 2 — Copilot 侧栏

- [ ] `HD AI Assistant` 最小配置（system prompt、temperature、绑定 Team）
- [ ] Copilot 会话（可先不持久化）
- [ ] Tools v1（关键词检索现有 API）：
  - 当前工单详情
  - 文章 / 全局搜索
  - 客户/联系人
- [ ] UI：`TicketAgent` 右侧面板（参考 chatwoot captain/copilot 信息架构）
- [ ] 实时：token 流式经 `realtime` 推送（可选）

### Phase 3 — 知识增强（RAG / FAQ）

- [ ] 文档摄入：URL/PDF → 文本 → 切块或 FAQ 抽取
- [ ] FAQ 生成服务（对齐 FaqGeneratorService）
- [ ] **向量存储选型决策**（关键路径）：
  - 外部向量库（Qdrant/Milvus/pgvector 旁路库）
  - 或云 embedding + 托管检索
  - 或阶段性继续关键词 + 同义词
- [ ] 工具：`faq_lookup` / `search_documentation`
- [ ] 高置信 FAQ 可回写/关联 `HD Article`

### Phase 4 — 工单自动助手（Bot）

- [ ] 新消息/新工单 enqueue Assistant
- [ ] 策略：仅内部草稿 / 自动公开回复 / 置信度阈值
- [ ] `bot_status` + handoff → Assignment Rule
- [ ] 与 auto_close、SLA、邮件线程共存的状态机
- [ ] 防双写：同一 Team/通道同时仅一个 BotProvider

### Phase 5 — 平台化与集成（可选）

- [ ] Integration Catalog + Hook Instance + Event Runner
- [ ] 自定义 HTTP Tools
- [ ] Slack 镜像（若产品需要）
- [ ] Dialogflow/外部 NLU Adapter（若需要）
- [ ] Translate / Linear / Shopify 类侧栏集成按需
- [ ] 通用 Automation Rule 引擎（仅当 Assignment+钩子不够时）

---

## 8. 风险与决策清单

| 风险 | 说明 | 建议 |
|------|------|------|
| MariaDB 无 pgvector | 阻塞 Phase 3 原样移植 | 立项前做向量存储 ADR |
| 邮件工单 ≠ IM 会话 | 自动回复可能造成邮件风暴/线程混乱 | 默认「草稿模式」，置信度+人工确认 |
| 多 bot 双写 | Chatwoot 同 pending 可叠加 | 产品层互斥：Team 仅允许一个 BotProvider |
| 配额与成本 | OpenAI 调用费用 | Settings 限额 + 日志 + 可选按站点预算 |
| 密钥安全 | API Key 存站点 | 用 Frappe Password 字段；禁止进 client bundle |
| 过度设计 | 一上来搬 Automation 引擎+多通道 | 严格按 Phase 0→1→2 交付 |
| 法律/合规 | 客户数据进 LLM | 提供数据脱敏开关与私有化 endpoint |

---

## 9. 可直接复用 vs 必须重做

### 可借鉴（保留设计）

- Assistant / Document / FAQ Response / Scenario / CustomTool 领域切分
- Document → FAQ → Embedding 流水线
- Agent（自动）与 Copilot（辅助）与 Tasks（编辑器）三分
- Tool registry + HTTP custom tools 模式
- Prompt 模板外置
- pending/handoff 状态机思想（映射到自家字段）
- 前端信息架构：Overview / Documents / Responses / Scenarios / Playground / Settings

### 不可照搬

- Ruby / Rails / `prepend_mod_with` enterprise 注入
- pgvector schema 与 neighbor gem
- Inbox 1:1 绑定（需改 Team/Email Account）
- 双 Tool 栈（V1 RubyLLM + V2 agents gem）——新系统只保留一套
- Sidekiq 专用 Job 类层次——改为 `frappe.enqueue`
- 计费写死在业务路径的 Chatwoot 套餐逻辑——按自有商业模型重做

### 主项目优先复用资产

1. `HD Saved Reply` 渲染与插入管线  
2. `HD Article` + search 作 Copilot tools v1  
3. Assignment Rule + Agent Status 作 handoff 后分配  
4. `HD Notification` + Socket 作完成通知  
5. Agent / Agent Manager 权限模型  
6. `hooks.py` scheduler / enqueue 基础设施  

---

## 10. 关键代码索引（Chatwoot）

### Captain

| 主题 | 路径 |
|------|------|
| 主触发 | `exeample/chatwoot/enterprise/app/services/enterprise/message_templates/hook_execution_service.rb` |
| 回复 Job | `exeample/chatwoot/enterprise/app/jobs/captain/conversation/response_builder_job.rb` |
| V2 Runner | `exeample/chatwoot/enterprise/app/services/captain/assistant/agent_runner_service.rb` |
| V1 Chat | `exeample/chatwoot/enterprise/app/services/captain/llm/assistant_chat_service.rb` |
| Copilot | `exeample/chatwoot/enterprise/app/services/captain/copilot/chat_service.rb` |
| Assistant 模型 | `exeample/chatwoot/enterprise/app/models/captain/assistant.rb` |
| FAQ 模型 | `exeample/chatwoot/enterprise/app/models/captain/assistant_response.rb` |
| Document | `exeample/chatwoot/enterprise/app/models/captain/document.rb` |
| Scenario | `exeample/chatwoot/enterprise/app/models/captain/scenario.rb` |
| CustomTool | `exeample/chatwoot/enterprise/app/models/captain/custom_tool.rb` |
| Tasks | `exeample/chatwoot/lib/captain/*.rb` |
| Prompts | `exeample/chatwoot/lib/integrations/openai/openai_prompts/*.liquid` |
| Tools 配置 | `exeample/chatwoot/config/agents/tools.yml` |
| 前端路由 | `exeample/chatwoot/app/javascript/dashboard/routes/dashboard/captain/` |

### 集成

| 主题 | 路径 |
|------|------|
| App 配置 | `exeample/chatwoot/config/integration/apps.yml` |
| Hook 模型 | `exeample/chatwoot/app/models/integrations/hook.rb` |
| HookJob | `exeample/chatwoot/app/jobs/hook_job.rb` |
| Bot 基类 | `exeample/chatwoot/lib/integrations/bot_processor_service.rb` |
| Dialogflow | `exeample/chatwoot/lib/integrations/dialogflow/processor_service.rb` |
| Slack | `exeample/chatwoot/lib/integrations/slack/**` |
| Translate | `exeample/chatwoot/lib/integrations/google_translate/**` |
| Linear | `exeample/chatwoot/lib/integrations/linear/**` |
| Shopify | `exeample/chatwoot/app/controllers/api/v1/accounts/integrations/shopify_controller.rb` |

### 主项目落点参考

| 主题 | 路径 |
|------|------|
| 工单 | `helpdesk/helpdesk/doctype/hd_ticket/` |
| 设置 | `helpdesk/helpdesk/doctype/hd_settings/` |
| 知识库 | `helpdesk/api/knowledge_base.py`、`helpdesk/search.py` |
| 预设回复 | `helpdesk/api/saved_replies.py` |
| 分配 | `helpdesk/overrides/assignment_rule.py` |
| 钩子 | `helpdesk/hooks.py` |
| 前端设置 | `desk/src/components/Settings/settingsModal.ts` |

---

## 11. 建议的下一步行动

1. **产品确认优先级：** 是否同意「先编辑器 AI，再 Copilot，再自动回复」？  
2. **向量存储 ADR：** Phase 3 前必须选型，避免返工。  
3. **Bot 默认策略：** 邮件通道建议默认「生成草稿不自动发送」。  
4. **立项拆分：**  
   - Epic A：AI 基建 + 编辑器 Tasks  
   - Epic B：Copilot  
   - Epic C：知识 RAG  
   - Epic D：自动助手 + handoff  
   - Epic E：集成框架（按需）  
5. **不要**在未完成 Phase 1 前并行大搬 Automation 引擎与 Slack 双向同步。

---

## 12. 一句话结论

Chatwoot 的「自动化与 AI 客服」= **Captain（自动 Agent + 知识中台 + Copilot + 编辑器 Tasks）** + **App/Hook 集成框架** + **确定性 Automation 编排**；三者通过会话 `pending/handoff` 松耦合。  
迁入 Frappe Helpdesk 时，应 **重建 AI 子系统并映射到 Ticket 生命周期**，优先交付坐席编辑器 AI 与 Copilot，再解决向量检索与自动回复；集成与规则引擎按需平台化，避免一次性照搬 enterprise 全量代码。

---

## 附录 A：端到端能力简图

```
Admin 配置 Assistant / Docs / Scenarios / Tools
                 │
Customer/邮件消息 ──► 事件钩子 ──► Bot Runner
                 │                    │
                 │         ┌──────────┴──────────┐
                 │         │ V1/V2 Agent + Tools │
                 │         │ FAQ lookup / handoff│
                 │         └──────────┬──────────┘
                 │                    │
                 │         对外回复 or 转人工分派
                 │
坐席打开工单 ──► Copilot 侧栏 / 编辑器 Tasks（不对客）
                 │
知识：Document ─crawl─► FAQ ─embed─► 向量检索
集成：Hook 事件 ─► Slack/Dialogflow/Translate/Linear/...
编排：Automation Rules ─► 状态/标签/分派（无 LLM）
```

## 附录 B：文档维护

| 项 | 说明 |
|----|------|
| 本文档路径 | `docs/change/2026-07-11-chatwoot-automation-ai-captain-analysis.md` |
| 后续变更 | 开始编码后另开 `docs/change/YYYY-MM-DD-hd-ai-*.md` 记录实现决策 |
| 源码基准 | 分析时仓库 `develop` 分支上的 `exeample/chatwoot` 快照 |
