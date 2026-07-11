## 实现方案决策（2026-07-11）

P1：在 **不破坏 P0 mock 演示** 的前提下，可选接入真实 LLM。  
承接 #3 已预留的 `analyzers/llm.py` 骨架与 `get_analyzer(source)`。

### 结论

**配置优先（site_config / 可选 Single DocType）+ LLMAnalyzer 结构化输出 + 严格降级 Mock；默认 provider=mock。**  
失败路径必须明确：错误可观测，演示仍可用 mock。

---

### 配置项

#### 最小集（site_config / `frappe.conf`）

```json
{
  "helpdesk_ai_enabled": 1,
  "helpdesk_ai_provider": "mock",
  "helpdesk_ai_api_key": "",
  "helpdesk_ai_model": "gpt-4.1-mini",
  "helpdesk_ai_base_url": "https://api.openai.com/v1",
  "helpdesk_ai_timeout": 60,
  "helpdesk_ai_fallback_to_mock": 1
}
```

| 键 | 说明 |
|----|------|
| `helpdesk_ai_provider` | `mock` 或 `llm`（默认 mock） |
| `helpdesk_ai_api_key` | 密钥；Password 语义，勿进前端 bundle |
| `helpdesk_ai_model` | 模型名 |
| `helpdesk_ai_base_url` | OpenAI 兼容 endpoint |
| `helpdesk_ai_timeout` | 秒 |
| `helpdesk_ai_fallback_to_mock` | 默认 true：LLM 失败则 mock |

#### 可选：`HD AI Settings`（Single DocType）

当需要 Desk UI 配置时再加（对齐迁移文档 Phase 0）：

- 字段同上；`api_key` 用 Password  
- 读配置优先级：`HD AI Settings`（若存在且 enabled）> `frappe.conf` > 默认 mock  
- **P1 可以只做 conf，不做 Settings UI**，仍算达标；UI 为加分项  

---

### 运行时选择逻辑

```text
analyze_ticket(ticket, source=None):
  provider = source or conf.provider or "mock"
  if provider == "llm":
    if not api_key:
      if fallback: use mock + mark analyzer="mock_fallback_no_key"
      else: throw 明确错误「未配置 API Key」
    try:
      result = LLMAnalyzer.analyze(context)
    except Exception as e:
      log_error
      if fallback: mock + mark analyzer="mock_fallback_error"
      else: analysis.error_message = str(e); re-raise 或 status 失败
  else:
    MockAnalyzer
  validators(result)   # 始终执行
  落库 source 字段：实际生效来源（Mock/LLM）
```

**硬约束：**

1. 未改 conf 时行为与 P0 **完全一致**（纯 mock）  
2. `fallback_to_mock=1` 时用户几乎总能拿到 Completed 结果  
3. 返回/文档中 `source` / `analyzer` / `model_name` 如实，避免「以为是 LLM 其实是 mock」不好排查  
4. 永不把 api_key 放进 API 响应  

---

### LLMAnalyzer 实现要点

```text
helpdesk/ai/
  client.py          # chat_completion(messages, response_format/json)
  analyzers/llm.py   # 拼 prompt + 调 client + parse → AnalysisResult
  prompts/
    ticket_analysis.j2   # 或 .md：要求输出 JSON 对齐 7 字段
```

- 输入：#3 `context.py` 的 ticket 文本（subject/description/可选最近沟通）  
- 输出：强制 JSON（response_format 或 prompt 约束 + json.loads 容错）  
- 解析失败 → 视为 LLM 失败走降级  
- timeout 用 conf  
- 可选：最大 description 截断，防爆 token  

Prompt 要求模型输出与 mock **同一契约**（category/priority/summary/confidence/evidence/…），便于 validators 共用。

依赖：优先 `httpx`/`requests` 调 OpenAI 兼容 API，**尽量不强制**新增大 SDK；若项目已有则复用。

---

### 与 Chatwoot 对照

| Chatwoot | 本项目 #10 |
|----------|------------|
| InstallationConfig + Hook OpenAI Key | conf / HD AI Settings |
| FeatureRouter 多模型 | MVP 单 model 字段足够 |
| Tasks 多 prompt 文件 | 仅 `ticket_analysis` 一条主 prompt |
| 无 Key 直接 error | 我们 **默认可 fallback mock**（演示优先） |

---

### API / UI 影响

- `analyze_ticket(..., source=None)`：已支持；UI 可隐藏 source，跟站点配置  
- （可选）#5 面板显示「来源: Mock / LLM」Badge——建议做，利于演示诚实性  
- Settings 页：P1 可选；有则放 Agent Manager 设置区  

---

### 失败与可观测

| 场景 | 行为 |
|------|------|
| 无 Key + fallback | mock 成功，analyzer 带 fallback 标记 |
| 无 Key + 不 fallback | 清晰 ValidationError / 401 文案 |
| 超时/网络错误 + fallback | mock + log_error |
| JSON 解析失败 | 同失败路径 |
| 成功 | source=LLM，model_name=配置模型 |

`raw_response` 存 LLM 原文（截断），便于排障。

---

### 测试（#7 扩展，不进默认不稳套件）

- conf 为 mock 时不调网络（patch client 断言未调用）  
- provider=llm 且 mock key + fallback → 仍 Completed 且 analyzer 含 fallback  
- parse 坏 JSON → fallback 或 error  
- **禁止** CI 默认打真实外网  

---

### 安全

- Password 字段 / conf 权限仅管理员  
- 日志脱敏  
- 客户数据进 LLM 的合规提示写在 #8 文档「限制」  

---

### 落地步骤

- [ ] `client.py` + conf 读取函数  
- [ ] `LLMAnalyzer` + prompt 模板  
- [ ] service 接入选择与 fallback  
- [ ] （可选）`HD AI Settings` Single  
- [ ] （可选）前端来源 Badge / 简单设置  
- [ ] #8 文档配置说明  
- [ ] 单元测试 mock 网络  

### 验收对照

- [ ] mock 默认可用（无任何配置）  
- [ ] 配置真实模型后可切换  
- [ ] 失败有明确错误与降级策略  

### 一句话

> **#10 = conf/可选 Settings 配 LLM；结构化 JSON 对齐 7 字段；默认 mock；失败可降级 mock 并如实标记来源；不破坏 P0 演示。**
