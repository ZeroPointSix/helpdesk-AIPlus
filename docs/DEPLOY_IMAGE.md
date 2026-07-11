# 生产镜像说明（本 fork）

对齐 Issue [#11](https://github.com/ZeroPointSix/helpdesk-AIPlus/issues/11)。

## 镜像与标签

| 项 | 值 |
|----|-----|
| 镜像 | `ghcr.io/zeropointsix/helpdesk-aiplus` |
| 默认开发线 | 分支 **`develop`** → 标签 `develop` 与 `latest` |
| 稳定线 | 分支 **`main`** → 标签 `main` 与 `stable` |
| 仓库 **无** `master` 分支 | 不要用 `master` / 官方 `ghcr.io/frappe/helpdesk` 代替本 fork 的汉化与 AI 能力 |

本镜像由 `.github/workflows/build.yml` 构建，基于 [frappe/frappe_docker](https://github.com/frappe/frappe_docker) 的 **layered** `Containerfile`，并烘焙：

- `frappe`（`version-16` 基线；与本仓库 `pyproject.toml` / 当前 frappe_docker 默认一致）
- `telephony`（`develop`）
- **本仓库** `helpdesk`（触发构建的分支/tag）

> 若线上已是 **Frappe 15** 站点（运行时 `bench list-apps` 见 `15.x`），换用本镜像等于换主版本，需要按 Frappe 大版本升级流程 migrate，或用**新 volume 全新建站**。Issue #11 的验收以「干净 volume 纯镜像部署」为准。

`apps.json` 通过 **BuildKit secret**（`id=apps_json`）注入；**不要**再使用已废弃的 `APPS_JSON_BASE64` build-arg（否则会得到「仅有 frappe」的假成功镜像）。

仓库根目录 `apps.json` 为默认 app 清单（develop 线）；CI 会按触发分支重写 helpdesk 的 `branch` 字段。

## 验收：镜像里必须有 apps

```bash
docker pull ghcr.io/zeropointsix/helpdesk-aiplus:develop

cid=$(docker create ghcr.io/zeropointsix/helpdesk-aiplus:develop)
docker export "$cid" | tar -t | grep -E 'frappe-bench/apps/[^/]+/$' | sort -u
docker rm -f "$cid"
```

期望至少：

```text
home/frappe/frappe-bench/apps/frappe/
home/frappe/frappe-bench/apps/helpdesk/
home/frappe/frappe-bench/apps/telephony/
```

或：

```bash
docker run --rm --entrypoint bash ghcr.io/zeropointsix/helpdesk-aiplus:develop -lc \
  'ls /home/frappe/frappe-bench/apps && test -d /home/frappe/frappe-bench/apps/helpdesk'
```

## easy-install / compose 使用本镜像

```bash
# 示例：easy-install 风格
python3 ./easy-install.py deploy \
  --project=helpdesk_aiplus \
  --email=you@example.com \
  --image=ghcr.io/zeropointsix/helpdesk-aiplus \
  --version=develop \
  --app=helpdesk \
  --sitename helpdesk.example.com
```

或 compose env：

```env
CUSTOM_IMAGE=ghcr.io/zeropointsix/helpdesk-aiplus
CUSTOM_TAG=develop
PULL_POLICY=always
```

安装顺序建议：`telephony` → `helpdesk`（helpdesk 依赖 telephony）。

## 静态资源（desk SPA）

layered 镜像在构建时把 app 的 public assets 拷到镜像内：

```text
/home/frappe/frappe-bench/assets
```

容器启动 entrypoint 会把该目录软链到：

```text
/home/frappe/frappe-bench/sites/assets  →  ../assets（镜像层）
```

因此 **production 不需要 Node** 再 `yarn build`。若仍见 `/assets/helpdesk/desk/*` 404：

1. 确认镜像 smoke 已含 desk 产物（CI 门禁会检查）。
2. 确认 frontend/nginx 与 backend 使用同一 sites volume，且 entrypoint 已跑过。
3. 在 backend 容器：`ls -la sites/assets/helpdesk/desk | head`。

## 与官方镜像的区别

| | 官方 `ghcr.io/frappe/helpdesk` | 本 fork |
|--|-------------------------------|---------|
| 源码 | frappe/helpdesk | ZeroPointSix/helpdesk-AIPlus |
| 中文汉化 / AI 工作台 | 上游默认 | 本仓库 develop/main |
| 推荐 tag | `stable` 等 | `develop`/`latest` 或 `main`/`stable` |

## 故障对照（Issue #11 根因）

| 症状 | 原因 |
|------|------|
| CI success 但镜像无 helpdesk | 用了 `APPS_JSON_BASE64` build-arg；layered 只读 secret `apps_json` |
| `No module named 'helpdesk'` | 镜像未 bake app，运行时又未 get-app |
| production 无 Node，yarn 失败 | 应在 **镜像构建期** bake desk assets |
| 用户说 master | 仓库无此分支；用 `develop` 或 `main` |
