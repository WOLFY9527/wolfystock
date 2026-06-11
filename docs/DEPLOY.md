# 🚀 部署指南

本文档介绍如何将 A股自选股智能分析系统部署到服务器。

## 📋 部署方案对比

| 方案 | 优点 | 缺点 | 推荐场景 |
|------|------|------|----------|
| **Docker Compose** ⭐ | 一键部署、环境隔离、易迁移、易升级 | 需要安装 Docker | **推荐**：大多数场景 |
| **直接部署** | 简单直接、无额外依赖 | 环境依赖、迁移麻烦 | 临时测试 |
| **Systemd 服务** | 系统级管理、开机自启 | 配置繁琐 | 长期稳定运行 |
| **Supervisor** | 进程管理、自动重启 | 需要额外安装 | 多进程管理 |

**结论：推荐使用 Docker Compose，迁移最快最方便！**

## 🚦 当前部署边界

- **单实例 / 私有 beta / 运维演练：可做。** 当前默认安全路径仍是 API 单进程、单实例，适合受控成员、私有入口、部署前彩排。
- **公网 public multi-user：仍然 NO-GO。** 在以下证据补齐前，不要把本文档视为“可直接公网开放”的批准：
  - 已完成并接受 **隔离环境 PostgreSQL restore/PITR drill**
  - 已完成并接受 **HTTPS staging ingress smoke**
  - 已具备 **加密备份基础设施**
  - 已具备并验证 **rollback proof / last-known-good 回滚路径**
- 如果只是做单实例 rehearsal，请把入口放在私有网络或受控 HTTPS 反向代理后，并保留当前单进程 queue/SSE 假设。

---

## 🐳 方案一：Docker Compose 部署（推荐）

### 1. 安装 Docker

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# CentOS
sudo yum install -y docker docker-compose
sudo systemctl start docker
sudo systemctl enable docker
```

### 2. 准备配置文件

```bash
# 克隆代码（或上传代码到服务器）
git clone <your-repo-url> /opt/stock-analyzer
cd /opt/stock-analyzer

# 复制并编辑配置文件
cp .env.example .env
vim .env  # 填入真实的 API Key 等配置
```

### 3. 一键启动

```bash
# 构建并启动（同时包含定时分析和 Web 界面服务）
docker-compose -f ./docker/docker-compose.yml up -d

# 查看日志
docker-compose -f ./docker/docker-compose.yml logs -f

# 查看运行状态
docker-compose -f ./docker/docker-compose.yml ps
```

启动成功后，在浏览器输入 `http://服务器公网IP:8000` 即可打开 Web 管理界面。如果打不开，记得先在云服务器控制台的「安全组」里放行 8000 端口。

> 不知道怎么访问？→ [云服务器 Web 界面访问指南](deploy-webui-cloud.md)

### 4. 常用管理命令

```bash
# 停止服务
docker-compose -f ./docker/docker-compose.yml down

# 重启服务
docker-compose -f ./docker/docker-compose.yml restart

# 更新代码后重新部署
git pull
docker-compose -f ./docker/docker-compose.yml build --no-cache
docker-compose -f ./docker/docker-compose.yml up -d

# 进入容器调试
docker-compose -f ./docker/docker-compose.yml exec stock-analyzer bash

# 手动执行一次分析
docker-compose -f ./docker/docker-compose.yml exec stock-analyzer python main.py --no-notify
```

### 4.1 API 服务部署假设

- 当前 `/api/v1/analysis/*` 任务队列与 SSE 状态保存在进程内存中。
- 因此本阶段的默认安全部署方式是：**API 服务单进程运行**。
- 不要把提供 `/api/v1/analysis/*` 和 `/api/v1/analysis/tasks/stream` 的 API 服务直接扩成多 worker / 多实例负载均衡，除非你已经自行提供 sticky routing 且能接受进程级任务可见性边界。
- Docker Compose 当前 `server` 服务默认就是单容器单进程路径，符合这一前提。

### 4.2 公网反向代理安全基线

公网部署建议把 API/Web 服务绑定在 `127.0.0.1:8000` 或只允许内网访问，不要把后端 `:8000` 直接暴露到互联网。对外入口使用 Nginx / 云负载均衡 / CDN 终止 HTTPS，并转发到后端服务。

最低基线：

- 对外只开放 80/443，80 统一跳转到 HTTPS。
- 启用 HSTS、`X-Content-Type-Options`、`Referrer-Policy`、frame deny / `frame-ancestors`、`Permissions-Policy`。
- 设置请求体大小限制和连接/读取超时，避免无限制上传或长连接耗尽。
- 正确传递 `Host`、`X-Real-IP`、`X-Forwarded-For`、`X-Forwarded-Proto`。
- 仅在可信代理前置时设置 `TRUST_X_FORWARDED_FOR=true`；直连公网保持 `false`。
- 生产 `.env` 显式设置 `APP_ENV=production`、`ADMIN_AUTH_ENABLED=true`、`CORS_ALLOW_ALL=false`、`CORS_ORIGINS=https://你的域名`、`CSRF_TRUSTED_ORIGINS=https://你的域名`。
- 同时显式声明当前 preflight 合同旗标：`WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_SCOPE=admin_only`、`WOLFYSTOCK_QUOTA_ENFORCEMENT_MODE=advisory`、`WOLFYSTOCK_BACKUP_PITR_EXECUTION_ENABLED=false`、`WOLFYSTOCK_STAGING_INGRESS_SMOKE=false`，以及当前接受的 RBAC fallback 状态。
- SSE / WebSocket 路径需要 HTTP/1.1 upgrade 与较长 `proxy_read_timeout`。
- 前端静态资源可在代理层加短期缓存；API 响应不要做共享缓存。

完整 Nginx HTTPS 模板见 [云服务器 Web 界面访问指南](deploy-webui-cloud.md#可选nginx-反向代理公网推荐)。

### 4.3 公网环境变量发布矩阵

下表只描述当前发布审查语义，不改变运行时默认值。公网发布仍然是
**NO-GO**，直到目标环境的 HTTPS ingress、sanitized config snapshot、恢复/PITR、
WS2/SSE、auth/RBAC/MFA、provider、quota 和最终 release gate 证据被接受。

| 变量 / 功能 | 当前行为 | 分类 | 发布证据要求 |
| --- | --- | --- | --- |
| `APP_ENV` | 显式设为 `production` 时启用生产安全语义；本地/dev 可为空或非生产。 | **GATED** | 通过 sanitized 生产配置合同和 config snapshot 证明目标环境已复核，不附 raw `.env` 或 secret values。 |
| `VITE_API_URL` | 前端默认同源 API；仅在静态站点/API 分域部署时显式覆盖。 | **GATED** | 证明前端构建指向预期 HTTPS API origin，CORS/CSRF origin 匹配，且后端 `:8000` 未直接公网暴露。 |
| `PUBLIC_API_ABUSE_LIMIT_*` | 进程内 public API 错误突发 limiter，参数有上下界；不是 quota、计费、auth 或分布式限流。 | **SAFE** | 提供 sanitized limiter 配置/快照，并明确 `processLocal`；不得当作 live quota enforcement。 |
| `CRYPTO_REALTIME_ENABLED` | 默认启用加密货币 SSE 后台实时连接；设为 false 时使用 REST/cache fallback。 | **AMBIGUOUS** | 目标环境需明确是否允许外连 Binance/WebSocket、失败降级方式，或显式禁用实时连接。 |
| `SEARXNG_PUBLIC_INSTANCES_ENABLED` | `SEARXNG_BASE_URLS` 为空时默认发现公共 SearXNG 实例。 | **NO-GO** | 公网发布必须使用已复核的自建实例、显式禁用公共发现，或附单独接受的运营风险决策。 |

分类含义：

- **SAFE**：当前行为有边界和测试，但仍需要目标环境证据。
- **GATED**：必须显式配置并与目标环境证据匹配。
- **AMBIGUOUS**：本地/私有使用可接受，但公网发布前必须有运营决策。
- **NO-GO**：缺少目标环境证据、需要 raw secret 才能证明、或被用来暗示
  provider/quota/auth live enforcement approval 时，发布状态保持 **NO-GO**。

### 4.4 启动后检查

```bash
# 存活检查：仅确认进程能响应
curl -fsS http://127.0.0.1:8000/api/health/live

# 就绪检查：确认存储与任务队列部署前提都满足
curl -fsS http://127.0.0.1:8000/api/health/ready
```

### 4.5 WS1 基线捕获（部署前）

> 目标：只做基线采集与验证，不做任何性能优化或架构改造。

```bash
# 1) 单进程启动 API（保持 queue/SSE 的当前部署前提）
python3 main.py --serve-only --host 0.0.0.0 --port 8000
```

另开一个终端执行：

```bash
# 2) 执行 WS1 基线采集（scanner / portfolio snapshot / analysis-search / backtest）
python3 scripts/ws1_baseline_capture.py \
  --base-url http://127.0.0.1:8000 \
  --stock-code AAPL \
  --scanner-market cn \
  --scanner-profile cn_preopen_v1

# 3) 基线结果默认输出到 reports/ws1_baseline/baseline_<UTC时间>.json
```

### 4.6 Canonical clean-checkout smoke（仅使用仓库已提交脚本）

```bash
# 干净 checkout 示例
git clone <your-repo-url> /tmp/dsa-ws1-smoke
cd /tmp/dsa-ws1-smoke
cp .env.example .env
pip install -r requirements.txt

# Canonical smoke 路径（不依赖本地未跟踪 helper）
python3 scripts/smoke_backtest_standard.py
python3 scripts/smoke_backtest_rule.py
```

### 4.7 目标主机 queue/SSE 单进程验证清单

```bash
# 1) 目标主机单进程启动
python3 main.py --serve-only --host 0.0.0.0 --port 8000

# 2) 健康检查
curl -fsS http://127.0.0.1:8000/api/health/live
curl -fsS http://127.0.0.1:8000/api/health/ready

# 3) 提交一个异步分析任务并拿到 task_id
TASK_ID=$(python3 - <<'PY'
import json, urllib.request
req = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/analysis/analyze",
    data=json.dumps({"stock_code":"AAPL","async_mode":True,"report_type":"brief"}).encode("utf-8"),
    headers={"Content-Type":"application/json","Accept":"application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=60) as resp:
    body = json.loads(resp.read().decode("utf-8"))
print(body.get("task_id",""))
PY
)
echo "TASK_ID=${TASK_ID}"

# 4) 观察 SSE 流（至少应看到 task_id 对应事件）
curl -N "http://127.0.0.1:8000/api/v1/analysis/tasks/stream?task_id=${TASK_ID}" | sed -n '1,20p'

# 5) 查询任务状态（确认非 404 且状态流转）
curl -fsS "http://127.0.0.1:8000/api/v1/analysis/status/${TASK_ID}"
```

### 4.8 回滚检查清单（WS1 部署验证专用）

```bash
# A. 停止新版本
docker-compose -f ./docker/docker-compose.yml down
# 或 systemd
# sudo systemctl stop stock-analyzer

# B. 切回已验证提交（示例：<last-good-commit>）
git fetch --all --tags
git checkout <last-good-commit>

# C. 重建并启动
docker-compose -f ./docker/docker-compose.yml build --no-cache
docker-compose -f ./docker/docker-compose.yml up -d
# 或 systemd
# sudo systemctl start stock-analyzer

# D. 回滚后验证
curl -fsS http://127.0.0.1:8000/api/health/live
curl -fsS http://127.0.0.1:8000/api/health/ready
python3 scripts/smoke_backtest_standard.py
python3 scripts/smoke_backtest_rule.py
```

### 5. 数据持久化

数据自动保存在宿主机目录：
- `./data/` - 数据库文件
- `./logs/` - 日志文件
- `./reports/` - 分析报告

---

## 🖥️ 方案二：直接部署

### 1. 安装 Python 环境

```bash
# 安装 Python 3.10+
sudo apt update
sudo apt install -y python3.10 python3.10-venv python3-pip

# 创建虚拟环境
python3.10 -m venv /opt/stock-analyzer/venv
source /opt/stock-analyzer/venv/bin/activate
```

### 2. 安装依赖

```bash
cd /opt/stock-analyzer
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 配置环境变量

```bash
cp .env.example .env
vim .env  # 填入配置
```

### 4. 运行

```bash
# 单次运行
python main.py

# 定时任务模式（前台运行）
python main.py --schedule

# 后台运行（使用 nohup）
nohup python main.py --schedule > /dev/null 2>&1 &

# 启动 API / Web 管理界面（当前部署建议保持单进程）
python main.py --serve-only --host 0.0.0.0 --port 8000

# 启动 API / Web 管理界面，并在启动时执行一次分析
python main.py --serve --host 0.0.0.0 --port 8000

# 存活 / 就绪检查
curl -fsS http://127.0.0.1:8000/api/health/live
curl -fsS http://127.0.0.1:8000/api/health/ready
```

> 不知道怎么访问？→ [云服务器 Web 界面访问指南](deploy-webui-cloud.md)

---

## 🔧 方案三：Systemd 服务

创建 systemd 服务文件实现开机自启和自动重启：

### 1. 创建服务文件

```bash
sudo vim /etc/systemd/system/stock-analyzer.service
```

内容：
```ini
[Unit]
Description=A股自选股智能分析系统
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/stock-analyzer
Environment="PATH=/opt/stock-analyzer/venv/bin"
ExecStart=/opt/stock-analyzer/venv/bin/python main.py --serve-only --host 0.0.0.0 --port 8000
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

### 2. 启动服务

```bash
# 重载配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start stock-analyzer

# 开机自启
sudo systemctl enable stock-analyzer

# 查看状态
sudo systemctl status stock-analyzer

# 查看日志
journalctl -u stock-analyzer -f
```

如果你还需要定时分析，建议把 `--schedule` 单独放到另一个 systemd 服务，而不是和 API 服务混在同一个长期运行进程里。

---

## ⚙️ 配置说明

### 必须配置项

| 配置项 | 说明 | 获取方式 |
|--------|------|----------|
| `GEMINI_API_KEY` | AI 分析必需 | [Google AI Studio](https://aistudio.google.com/) |
| `ADMIN_AUTH_ENABLED` | 管理界面认证，生产必须保持 `true` | `.env.example` |
| `APP_ENV` | 公网或正式演练建议显式设为 `production` | `.env.example` |
| `VITE_API_URL` | 仅前端/API 分域部署时需要；默认同源 API | 前端构建环境 |

### 可选配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `STOCK_LIST` | `600519,300750,002594` | 定时分析 / 观察列表 |
| `PUBLIC_API_ABUSE_LIMIT_*` | 见 `docs/audits/public-api-abuse-limiter-operator-note.md` | 进程内 public API 错误突发 limiter；不是 quota/live enforcement |
| `CRYPTO_REALTIME_ENABLED` | `true` | 加密货币 SSE 后台实时连接；公网前需记录外连/禁用决策 |
| `SEARXNG_PUBLIC_INSTANCES_ENABLED` | `true` | 未配置自建 SearXNG 时发现公共实例；公网前需记录接受或禁用决策 |
| `SCHEDULE_ENABLED` | `false` | 是否启用定时任务 |
| `SCHEDULE_TIME` | `18:00` | 每日执行时间 |
| `MARKET_REVIEW_ENABLED` | `true` | 是否启用大盘复盘 |
| `TAVILY_API_KEYS` | - | 新闻搜索（可选） |
| `MINIMAX_API_KEYS` | - | MiniMax 搜索（可选） |
| 通知渠道变量 | - | 全部可选，按需配置至少一个 |

---

## 🌐 代理配置

如果服务器在国内，访问 Gemini API 需要代理：

### Docker 方式

通过环境变量注入代理：
```yaml
environment:
  - http_proxy=http://your-proxy:port
  - https_proxy=http://your-proxy:port
```

### 直接部署方式

在 systemd、shell profile 或启动命令前注入：
```bash
export http_proxy=http://your-proxy:port
export https_proxy=http://your-proxy:port
```

---

## 📊 监控与维护

### 日志查看

```bash
# Docker 方式
docker-compose -f ./docker/docker-compose.yml logs -f --tail=100

# 直接部署
tail -f /opt/stock-analyzer/logs/stock_analysis_*.log
```

### 健康检查

```bash
# 检查进程
ps aux | grep main.py

# 检查最近的报告
ls -la /opt/stock-analyzer/reports/
```

### 定期维护

```bash
# 先预览，再用平台级保留策略或人工确认删除
find /opt/stock-analyzer/logs -mtime +7 -print
find /opt/stock-analyzer/reports -mtime +30 -print
```

---

## ❓ 常见问题

### 1. Docker 构建失败

```bash
# 清理缓存重新构建
docker-compose -f ./docker/docker-compose.yml build --no-cache
```

### 2. API 访问超时

检查代理配置，确保服务器能访问 Gemini API。

### 3. 数据库锁定

不要直接删除 `*.lock` 文件。先确认仍在运行的进程、最近异常日志和底层存储状态；只有在明确该锁文件为陈旧残留且已有回滚/备份路径时，才按运维 runbook 处理。

### 4. 内存不足

调整 `docker-compose.yml` 中的内存限制：
```yaml
deploy:
  resources:
    limits:
      memory: 1G
```

---

## 🔄 快速迁移

从一台服务器迁移到另一台：

```bash
# 1) 目标服务器：部署代码
mkdir -p /opt/stock-analyzer
cd /opt/stock-analyzer
git clone <your-repo-url> .

# 2) 在目标环境重新注入 secrets（不要打包或传输原始 .env）
cp .env.example .env
vim .env

# 3) 通过受控备份体系恢复数据，不要使用未加密归档直接搬运环境文件或数据库目录
#    public multi-user 仍需先通过 isolated restore/PITR、HTTPS staging ingress、
#    backup infra、rollback proof 四项证据

# 4) 启动
docker-compose -f ./docker/docker-compose.yml up -d
```

---

## ☁️ 方案四：GitHub Actions 部署（免服务器）

**最简单的方案！** 无需服务器，利用 GitHub 免费计算资源。

### 优势
- ✅ **完全免费**（每月 2000 分钟）
- ✅ **无需服务器**
- ✅ **自动定时执行**
- ✅ **零维护成本**

### 限制
- ⚠️ 无状态（每次运行是新环境）
- ⚠️ 定时可能有几分钟延迟
- ⚠️ 无法提供 HTTP API

### 部署步骤

#### 1. 创建 GitHub 仓库

```bash
# 初始化 git（如果还没有）
cd /path/to/daily_stock_analysis
git init
git add .
git commit -m "Initial commit"

# 创建 GitHub 仓库并推送
# 在 GitHub 网页上创建新仓库后：
git remote add origin https://github.com/你的用户名/daily_stock_analysis.git
git branch -M main
git push -u origin main
```

#### 2. 配置 Secrets（重要！）

打开仓库页面 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

添加以下 Secrets：

| Secret 名称 | 说明 | 必填 |
|------------|------|------|
| `GEMINI_API_KEY` | Gemini AI API Key | ✅ |
| `WECHAT_WEBHOOK_URL` | 企业微信机器人 Webhook | 可选* |
| `FEISHU_WEBHOOK_URL` | 飞书机器人 Webhook | 可选* |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | 可选* |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | 可选* |
| `TELEGRAM_MESSAGE_THREAD_ID` | Telegram Topic ID | 可选* |
| `EMAIL_SENDER` | 发件人邮箱 | 可选* |
| `EMAIL_PASSWORD` | 邮箱授权码 | 可选* |
| `SERVERCHAN3_SENDKEY` | Server酱³ Sendkey | 可选* |
| `CUSTOM_WEBHOOK_URLS` | 自定义 Webhook（多个逗号分隔） | 可选* |
| `STOCK_LIST` | 自选股列表，如 `600519,300750` | ✅ |
| `TAVILY_API_KEYS` | Tavily 搜索 API Key | 推荐 |
| `MINIMAX_API_KEYS` | MiniMax Coding Plan Web Search | 可选 |
| `SERPAPI_API_KEYS` | SerpAPI Key | 可选 |
| `SEARXNG_BASE_URLS` | SearXNG 自建实例（无配额兜底，需在 settings.yml 启用 format: json）；留空时默认自动发现公共实例 | 可选 |
| `SEARXNG_PUBLIC_INSTANCES_ENABLED` | 是否在 `SEARXNG_BASE_URLS` 为空时自动从 `searx.space` 获取公共实例（默认 `true`） | 可选 |
| `TUSHARE_TOKEN` | Tushare Token | 可选 |
| `GEMINI_MODEL` | 模型名称（默认 gemini-2.0-flash） | 可选 |

> *注：通知渠道至少配置一个，支持多渠道同时推送

#### 3. 验证 Workflow 文件

确保 `.github/workflows/daily_analysis.yml` 文件存在且已提交：

```bash
git add .github/workflows/daily_analysis.yml
git commit -m "Add GitHub Actions workflow"
git push
```

#### 4. 手动测试运行

1. 打开仓库页面 → **Actions** 标签
2. 选择 **"每日股票分析"** workflow
3. 点击 **"Run workflow"** 按钮
4. 选择运行模式：
   - `full` - 完整分析（股票+大盘）
   - `market-only` - 仅大盘复盘
   - `stocks-only` - 仅股票分析
5. 点击绿色 **"Run workflow"** 按钮

#### 5. 查看执行日志

- Actions 页面可以看到运行历史
- 点击具体的运行记录查看详细日志
- 分析报告会作为 Artifact 保存 30 天

### 定时说明

默认配置：**周一到周五，北京时间 18:00** 自动执行

修改时间：编辑 `.github/workflows/daily_analysis.yml` 中的 cron 表达式：

```yaml
schedule:
  - cron: '0 10 * * 1-5'  # UTC 时间，+8 = 北京时间
```

常用 cron 示例：
| 表达式 | 说明 |
|--------|------|
| `'0 10 * * 1-5'` | 周一到周五 18:00（北京时间） |
| `'30 7 * * 1-5'` | 周一到周五 15:30（北京时间） |
| `'0 10 * * *'` | 每天 18:00（北京时间） |
| `'0 2 * * 1-5'` | 周一到周五 10:00（北京时间） |

### 修改自选股

方法一：修改仓库 Secret `STOCK_LIST`

方法二：直接修改代码后推送：
```bash
# 修改 .env.example 或在代码中设置默认值
git commit -am "Update stock list"
git push
```

### 常见问题

**Q: 为什么定时任务没有执行？**
A: GitHub Actions 定时任务可能有 5-15 分钟延迟，且仅在仓库有活动时才触发。长时间无 commit 可能导致 workflow 被禁用。

**Q: 如何查看历史报告？**
A: Actions → 选择运行记录 → Artifacts → 下载 `analysis-reports-xxx`

**Q: 免费额度够用吗？**
A: 每次运行约 2-5 分钟，一个月 22 个工作日 = 44-110 分钟，远低于 2000 分钟限制。

---

## 🌐 云服务器上部署了，但不知道怎么用浏览器访问？

详见 → [云服务器 Web 界面访问指南](deploy-webui-cloud.md)

涵盖：直接部署和 Docker 两种方式的启动与访问、安全组/防火墙配置、常见问题排查、Nginx 反向代理（可选）。

---

**祝部署顺利！🎉**
