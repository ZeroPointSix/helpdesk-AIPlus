## 实现方案决策（2026-07-11）

承接 #2–#6 契约与主项目测试习惯：`frappe.tests.IntegrationTestCase` + `helpdesk/test_utils.py`（`make_ticket` / `create_agent` 等）+ 现有 `helpdesk/api/test_*.py` 模式。

题目要求「基本测试」，不追求全量 E2E/前端单测。

### 结论

**后端 Integration 测试为主，一条 bench 命令可跑；覆盖 analyze 结构、落库、修改确认写回、mock 双分支。**  
前端 Playwright 非 P0；#10 LLM 用 mock/patch 隔离，默认套件不依赖外网。

---

### 测试文件布局

```text
helpdesk/
  ai/
    test_validators.py          # 纯函数：退款缺单号 / 登录推团队（可选）
    test_mock_analyzer.py       # mock 关键词 → 分支字段（可选，快）
  api/
    test_ai.py                  # ★ 主文件：API 端到端（analyze/get/update/confirm/reject）
  helpdesk/doctype/hd_ai_analysis/
    test_hd_ai_analysis.py      # DocType 最小：建档、状态约束（可选）
```

优先保证 **`helpdesk/api/test_ai.py`** 一张清单覆盖验收；其余按需拆分。

---

### 必须覆盖的用例（验收映射）

| # | 用例 | 断言要点 |
|---|------|----------|
| 1 | `analyze_ticket` 返回结构完整 | 7 类字段 + evidence 非空列表 + status=Completed + name/ticket/source |
| 2 | 结果可保存 | DB 存在 `HD AI Analysis`，`get_analysis(ticket)` 与 analyze 返回一致 |
| 3 | 人工修改 | `update_analysis` 改 priority/summary → `is_edited=1`，`original_result` 不变 |
| 4 | 确认写回 | `confirm_analysis` → status=Confirmed；Ticket 的 priority/summary（及可映射 type）已变 |
| 5 | mock 分支 A | 登录类工单 → `auto_handleable` 真 + plan 有 steps；置信度达标 |
| 6 | mock 分支 B | 退款无订单号 → missing_info 含订单号 + auto_handleable 假 + 置信度被压低 |
| 7 | （建议）驳回 | reject 后 Ticket 业务字段不变 |
| 8 | （建议）非法流转 | Completed 以外 confirm/update 抛错；重复 confirm 幂等或明确错误 |

权限（建议至少 1 条）：非 agent 调 analyze → PermissionError（对齐 `test_ticket_stats` 风格）。

---

### Fixture 策略

- 使用 `helpdesk.test_utils.make_ticket` / `create_agent` 等现有工具  
- 样例 description **写死关键词**，与 #3 mock 一致（中英皆可，测试里固定一种）：
  - A：`Cannot login, password reset email not received`
  - B：`I want a refund for my purchase`（无订单号）
- 不依赖 #9 种子脚本；测试自建工单，保持独立  
- `setUp`：agent 用户 + `frappe.set_user(agent)`  
- `tearDown`：恢复 Administrator；分析文档可 `delete_doc` 或依赖事务回滚（按 Frappe 测试惯例）

---

### 一条命令（文档与 CI 共用）

```bash
# 在 bench 站点上下文中（路径以实际 bench 为准）
bench --site <site> run-tests --app helpdesk --module helpdesk.api.test_ai
```

或跑整个 app：

```bash
bench --site <site> run-tests --app helpdesk
```

**#8 文档必须写明**上述命令；若 CI 已有 helpdesk tests job，无需新 pipeline，只要新测试被 app 发现即可。  
本仓库若无 CI 跑测试：在 `docs/AI_WORKBENCH.md` 写「如何跑」，满足 issue 验收「CI 可跑**或**文档写明」。

---

### 不测 / 缓测

| 项 | 原因 |
|----|------|
| 真实 LLM HTTP | #10；用 unittest.mock patch `LLMAnalyzer` 即可 |
| 前端组件 | P0 手工演示；可选后续 |
| simulate_auto_handle | 有则加 1 条；无则跳过 |
| 全量 Priority/Type 主数据矩阵 | 只测「能映射写回」与「不能映射 warnings」各 1 |

---

### 与 #3/#4/#6 契约断言示例（伪代码）

```python
def test_analyze_login_branch_a(self):
    t = make_ticket(subject="Login issue", description="Cannot login password reset...")
    res = analyze_ticket(t.name)
    self.assertEqual(res["status"], "Completed")
    for key in ("category", "priority", "summary", "confidence", "evidence",
                "suggested_role", "auto_handleable"):
        self.assertIn(key, res)
    self.assertTrue(res["auto_handleable"] in (1, True))
    self.assertTrue(frappe.db.exists("HD AI Analysis", res["name"]))

def test_confirm_writes_ticket(self):
    # analyze → update fields → confirm → ticket.priority/summary changed
    ...
```

---

### 落地步骤

- [ ] #2/#3/#4 API 可调用  
- [ ] 实现 `helpdesk/api/test_ai.py` 核心 6～8 例  
- [ ] 本地 bench 一条命令跑绿  
- [ ] #8 文档写入命令  
- [ ] （可选）validators/mock 单测  

### 验收对照

- [ ] analyze 结构完整 + 落库  
- [ ] 修改 + 确认写回符合预期  
- [ ] mock 可自动处理 / 需人工 两分支  
- [ ] 本地一条命令可跑；CI 或文档说明  

### 一句话

> **#7 = `test_ai.py` 集成测试钉死 API 契约与 mock 双分支；bench 一条命令；不拦在真实 LLM 和前端 E2E 上。**
