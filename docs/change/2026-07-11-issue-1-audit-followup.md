# Issue #1 审查收口跟进（2026-07-11）

| 字段 | 内容 |
|------|------|
| 对照报告 | [2026-07-11-issue-1-local-implementation-audit.md](./2026-07-11-issue-1-local-implementation-audit.md) |
| 动作时间 | 2026-07-11 |
| 范围 | 审查「必须/建议」缺口修复 + 文档入库 + 忽略本地参考树 + 推送准备 |

---

## 1. 本轮代码修复

| 缺口 | 处理 |
|------|------|
| `run_analysis` 失败时 `frappe.throw` 可能回滚 Failed 快照 | 分析器异常时先 `mark_failed` + `save`，**返回 Failed 记录**；仅当 Failed 本身无法落库时再 throw。权限/校验类异常仍直接 raise，不伪装 Failed |
| `useTicketAI(ticketId)` 非响应式 | 接受 `MaybeRef<string>`，`toRef(props, "ticketId")` + `watch` 切换工单时重置 draft/simulation 并 reload |
| simulate loading 语义不准 | 独立 `simulating`（仅 `simulateResource.loading`），Followup 不再用 `loading && simulation===null` |
| 详情页侧栏窄屏滚动 | `TicketDetailsTab` AI 区域 `max-h-[55vh] overflow-y-auto`，并加 `:key` 按工单重建 |
| 移动端无 AI 入口 | `MobileTicketAgent` 详情 Tab 挂载同一 `TicketAIWorkbench` |
| `exeample/`、scripts 扫描 JSON 误提风险 | `.gitignore` 增加忽略规则 |

---

## 2. 文档入库

- 审查报告：`docs/change/2026-07-11-issue-1-local-implementation-audit.md`
- Chatwoot Captain 参考：`docs/change/2026-07-11-chatwoot-automation-ai-captain-analysis.md`（非 MVP 必需，作后续对照）
- 本跟进：`docs/change/2026-07-11-issue-1-audit-followup.md`

**明确不入库：** `exeample/`、`scripts/*.json` 扫描产物。

---

## 3. 环境验收状态（诚实标注）

本工作站**无** `bench` / frappe-bench，因此以下仍未在本机执行：

```bash
bench --site <site> migrate
bench --site <site> clear-cache
bench --site <site> run-tests --app helpdesk --module helpdesk.api.test_ai
bench --site <site> run-tests --app helpdesk --module helpdesk.helpdesk.doctype.hd_ai_analysis.test_hd_ai_analysis
bench --site <site> execute helpdesk.ai.seed_demo.run
```

前端：可在有依赖的环境下执行 `cd desk && yarn && yarn build` 做编译校验。

---

## 4. 推送与 Issue 闭环

1. 将 AI MVP 相关 commit + 本轮收口 commit 推到 `origin/develop`。
2. 在有 bench 的环境完成 migrate / tests / seed / UI 演示后，于 Epic #1 补评论：
   - 远程 commit SHA
   - 测试命令与结果
   - 演示是否通过（Mock 路径）
3. 在未跑 bench 前，表述应保持：**代码与文档已落地；环境验收待 bench 环境执行。**

---

## 5. 关键路径增量

```
helpdesk/ai/service.py                 # Failed 可靠返回
desk/src/composables/useTicketAI.ts    # 响应式 ticketId + simulating
desk/src/components/ticket-agent/ai/TicketAIWorkbench.vue
desk/src/components/ticket-agent/TicketDetailsTab.vue
desk/src/pages/ticket/MobileTicketAgent.vue
.gitignore
docs/change/*
```
