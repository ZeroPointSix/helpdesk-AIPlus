## 实现方案决策（2026-07-11）

P1，但 **#6 验收依赖至少 A/B 两条可演示工单**，建议与 P0 联调同期交付。  
覆盖 issue 要求的 3～5 类：退款、登录、发票、物流、信息缺失。

### 结论

**可重复执行的种子脚本 + 固定文案模板；默认只建 Ticket，不预置 Analysis（演示时现场点「AI 分析」更完整）。**  
入口：`bench execute helpdesk.ai.seed_demo.run`（或 `helpdesk.api.ai.seed_demo_tickets`），幂等可清可建。

---

### 样例清单（5 条）

| ID | 场景 | subject（示例） | description 关键词要点 | 期望 mock 分支 |
|----|------|-----------------|------------------------|----------------|
| D1 | 登录异常 | 无法登录账号 | login/password/重置邮件未收到，信息较全 | **A** 可自动处理 |
| D2 | 退款+缺信息 | 申请退款 | refund/退款，**无订单号** | **B** missing_info |
| D3 | 发票问题 | 需要开具发票 | 发票/invoice，可缺税号 → B 或中置信 | **B** 倾向 |
| D4 | 物流投诉 | 快递一周未送达 | 物流/快递/物流单号可给可不给 | 中置信 **B** 或人工 |
| D5 | 信息缺失（综合） | 我的订单有问题 | 极短、无订单号无商品 | **B** 强 missing_info |

最少交付：**D1 + D2**（锁 #6）；完整演示交付 D1–D5。

文案建议中英混合或中文为主（与 mock 双语关键词对齐，#3 已定）。

---

### 脚本设计

```text
helpdesk/ai/seed_demo.py
  DEMO_TICKETS: list[dict]     # subject, description, raised_by, priority?
  run(reset: bool = False)     # 入口
  ensure_demo_contact()
  create_or_update_ticket(spec)
  print 建成的 name 列表与建议演示顺序
```

行为：

- `reset=True`：删除带标记的旧演示单再建模  
- 幂等标记：subject 前缀 `[AI-Demo]` + 固定 raised_by 识别  
- `raised_by`：`ai-demo-customer@example.com`（无则建 Contact）  
- 权限：execute 时用 Administrator；仅开发/演示环境使用  

调用示例：

```bash
bench --site <site> execute helpdesk.ai.seed_demo.run
bench --site <site> execute helpdesk.ai.seed_demo.run --kwargs "{'reset': True}"
```

（可选）whitelist 仅 System Manager：`seed_demo_tickets`，方便 desk 控制台；P1 有 execute 即可。

---

### 是否预置 Analysis？

| 策略 | 优缺 | 建议 |
|------|------|------|
| 只建 Ticket | 演示完整「点分析」 | **默认** |
| 建 Ticket + 直接 insert Completed 分析 | 展示快，跳过分析按钮 | 可选 `with_analysis=True` |

默认 `with_analysis=False`。

---

### 与 mock 关键词对齐（硬约束）

种子 **description 必须命中** #3 mock 规则，否则 #6 现场翻车：

- D1 含：`login` 或 `登录` / `password` / `重置`  
- D2 含：`refund` 或 `退款`，且 **不出现** 订单号模式  
- 脚本旁注释写明「勿改关键词，否则分支断言失效」  
- #7 测试可复用同一常量：`helpdesk/ai/demo_fixtures.py` 供 seed 与 test import  

```python
# demo_fixtures.py
LOGIN_TICKET = {"subject": "[AI-Demo] ...", "description": "..."}
REFUND_TICKET = {...}
```

---

### 文档（#8）应写

1. 执行 seed 命令  
2. 打开 D1 → 分析 → 见自动处理卡片 → 模拟  
3. 打开 D2 → 分析 → 见缺信息/转人工  
4. （可选）D3–D5 浏览  

---

### 不做

- 生产环境自动 seed  
- 大量随机工单  
- 依赖真实客户邮箱外发  

---

### 落地步骤

- [ ] `demo_fixtures.py` 冻结 5 条文案  
- [ ] `seed_demo.run` 幂等创建  
- [ ] 本地跑通 D1/D2 与 mock 分支  
- [ ] #8 写入命令与演示顺序  
- [ ] （可选）reset / with_analysis  

### 验收对照

- [ ] 新环境快速准备演示数据  
- [ ] 覆盖自动处理（D1）与转人工/缺信息（D2）  

### 一句话

> **#9 = 带 `[AI-Demo]` 前缀的 5 条固定文案工单 + `bench execute` 幂等种子；默认同现场 AI 分析；D1/D2 锁死 A/B 演示。**
