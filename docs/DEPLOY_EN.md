# Deployment Guide

This document explains how to deploy the AI Stock Analysis System to a server.

## Deployment Options Comparison

| Option | Pros | Cons | Recommended For |
|------|------|------|----------|
| **Docker Compose** ⭐ | One-click deploy, isolated environment, easy migration, easy upgrade | Requires Docker installation | **Recommended**: Most scenarios |
| **Direct Deployment** | Simple, no extra dependencies | Environment dependencies, migration difficulties | Temporary testing |
| **Systemd Service** | System-level management, auto-start on boot | Complex configuration | Long-term stable operation |
| **Supervisor** | Process management, auto-restart | Requires additional installation | Multi-process management |

**Conclusion: Docker Compose is recommended for the fastest and most convenient migration!**

## Current Deployment Boundary

- **Single-instance / private beta / operator rehearsal: allowed.** The current safe path is still a single API process and a single instance for controlled users and deployment rehearsal.
- **Public multi-user: still NO-GO.** Do not treat this document as public-launch approval until all of the following evidence exists and is accepted:
  - an **isolated PostgreSQL restore/PITR drill**
  - an **HTTPS staging ingress smoke**
  - **encrypted backup infrastructure**
  - verified **rollback proof / last-known-good recovery path**
- If you are only rehearsing a single-instance deployment, keep the service behind a private network or a controlled HTTPS reverse proxy and preserve the current single-process queue/SSE assumption.

---

## Option 1: Docker Compose Deployment (Recommended)

### 1. Install Docker

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# CentOS
sudo yum install -y docker docker-compose
sudo systemctl start docker
sudo systemctl enable docker
```

### 2. Prepare Configuration Files

```bash
# Clone code (or upload code to server)
git clone <your-repo-url> /opt/stock-analyzer
cd /opt/stock-analyzer

# Copy and edit configuration file
cp .env.example .env
vim .env  # Fill in real API Keys and configuration
```

### 3. One-Click Start

```bash
# Build and start
docker-compose -f ./docker/docker-compose.yml up -d

# View logs
docker-compose -f ./docker/docker-compose.yml logs -f

# View running status
docker-compose -f ./docker/docker-compose.yml ps
```

### 4. Common Management Commands

```bash
# Stop services
docker-compose -f ./docker/docker-compose.yml down

# Restart services
docker-compose -f ./docker/docker-compose.yml restart

# Redeploy after code update
git pull
docker-compose -f ./docker/docker-compose.yml build --no-cache
docker-compose -f ./docker/docker-compose.yml up -d

# Enter container for debugging
docker-compose -f ./docker/docker-compose.yml exec stock-analyzer bash

# Manually run analysis once
docker-compose -f ./docker/docker-compose.yml exec stock-analyzer python main.py --no-notify
```

### 4.1 API Deployment Assumption

- The current `/api/v1/analysis/*` task queue and SSE fan-out are process-local.
- The safe default for this phase is therefore: **run the API as a single process**.
- Do not scale the API surface that serves `/api/v1/analysis/*` and `/api/v1/analysis/tasks/stream` to multiple workers or multiple instances unless you have your own sticky-routing strategy and accept process-local task visibility.
- The current Docker Compose `server` service matches this assumption.

### 4.2 Public Reverse-Proxy Safety Baseline

For internet-facing deployments, bind the API/Web service to `127.0.0.1:8000` or keep it private to the internal network. Put Nginx / a cloud load balancer / CDN in front to terminate HTTPS and forward traffic to the backend.

Minimum baseline:

- Expose only 80/443 publicly and redirect HTTP to HTTPS.
- Enable HSTS, `X-Content-Type-Options`, `Referrer-Policy`, frame deny / `frame-ancestors`, and `Permissions-Policy`.
- Set request-body limits and connection/read timeouts.
- Forward `Host`, `X-Real-IP`, `X-Forwarded-For`, and `X-Forwarded-Proto` correctly.
- Set `TRUST_X_FORWARDED_FOR=true` only behind a trusted proxy; keep it `false` on direct public exposure.
- In production, explicitly set `APP_ENV=production`, `ADMIN_AUTH_ENABLED=true`, `CORS_ALLOW_ALL=false`, `CORS_ORIGINS=https://your-domain`, and `CSRF_TRUSTED_ORIGINS=https://your-domain`.
- Also declare the current preflight contract flags explicitly: `WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_SCOPE=admin_only`, `WOLFYSTOCK_QUOTA_ENFORCEMENT_MODE=advisory`, `WOLFYSTOCK_BACKUP_PITR_EXECUTION_ENABLED=false`, `WOLFYSTOCK_STAGING_INGRESS_SMOKE=false`, plus the accepted RBAC fallback state.
- SSE / WebSocket paths need HTTP/1.1 upgrade support and a longer `proxy_read_timeout`.
- Cache static assets at the proxy if needed, but do not apply shared caching to API responses.

### 4.3 Public Env Flag Release Matrix

This table documents release-review semantics only; it does not change runtime
defaults. Public launch remains **NO-GO** until target-environment evidence for
HTTPS ingress, sanitized config snapshot, restore/PITR, WS2/SSE, auth/RBAC/MFA,
provider, quota, and the final release gate is accepted.

| Flag / feature | Current behavior | Classification | Launch evidence required |
| --- | --- | --- | --- |
| `APP_ENV` | Explicit `production` enables production security semantics; local/dev may be empty or non-production. | **GATED** | Sanitized production config contract and config snapshot evidence for the target environment, without raw `.env` or secret values. |
| `VITE_API_URL` | Frontend defaults to same-origin API; explicit value only for split static frontend/API deployments. | **GATED** | Evidence that the built frontend points to the intended HTTPS API origin, CORS/CSRF origins match, and backend `:8000` is not directly public. |
| `PUBLIC_API_ABUSE_LIMIT_*` | Process-local public API error-burst limiter with bounded knobs; not quota, billing, auth, or distributed rate-limit enforcement. | **SAFE** | Sanitized limiter config/snapshot evidence labeled `processLocal`; do not present it as live quota enforcement. |
| `CRYPTO_REALTIME_ENABLED` | Realtime crypto SSE background connection is enabled by default; `false` uses REST/cache fallback. | **AMBIGUOUS** | Target-env decision for outbound Binance/WebSocket access, degraded behavior, or explicit realtime disablement. |
| `SEARXNG_PUBLIC_INSTANCES_ENABLED` | Discovers public SearXNG instances when `SEARXNG_BASE_URLS` is empty. | **NO-GO** | Public launch must use vetted self-hosted endpoints, explicitly disable public discovery, or attach a separately accepted operator risk decision. |

Classification meanings:

- **SAFE**: bounded and test-backed locally, but still requires target-env evidence.
- **GATED**: must be explicit and matched by target-env evidence.
- **AMBIGUOUS**: acceptable for local/private use, but needs an operator decision before public launch.
- **NO-GO**: launch remains **NO-GO** if target-env evidence is missing, raw secrets would be needed, or the flag is used to imply provider/quota/auth live enforcement approval.

### 4.4 Post-Start Checks

```bash
# Liveness: confirms the process is responding
curl -fsS http://127.0.0.1:8000/api/health/live

# Readiness: confirms storage and task-queue deployment assumptions
curl -fsS http://127.0.0.1:8000/api/health/ready
```

### 4.5 WS1 Baseline Capture (Pre-deployment)

> Goal: baseline capture and validation only. No optimization or architecture refactor.

```bash
# 1) Start API in single-process mode (matches current queue/SSE assumption)
python3 main.py --serve-only --host 0.0.0.0 --port 8000
```

In another terminal:

```bash
# 2) Run WS1 baseline capture (scanner / portfolio snapshot / analysis-search / backtest)
python3 scripts/ws1_baseline_capture.py \
  --base-url http://127.0.0.1:8000 \
  --stock-code AAPL \
  --scanner-market cn \
  --scanner-profile cn_preopen_v1

# 3) Baseline output is written to reports/ws1_baseline/baseline_<UTC timestamp>.json
```

### 4.6 Canonical clean-checkout smoke (repo-committed scripts only)

```bash
# Clean-checkout example
git clone <your-repo-url> /tmp/dsa-ws1-smoke
cd /tmp/dsa-ws1-smoke
cp .env.example .env
pip install -r requirements.txt

# Canonical smoke path (no untracked local helpers)
python3 scripts/smoke_backtest_standard.py
python3 scripts/smoke_backtest_rule.py
```

### 4.7 Target-host queue/SSE single-process validation checklist

```bash
# 1) Start single-process API on target host
python3 main.py --serve-only --host 0.0.0.0 --port 8000

# 2) Health checks
curl -fsS http://127.0.0.1:8000/api/health/live
curl -fsS http://127.0.0.1:8000/api/health/ready

# 3) Submit an async analysis task and capture task_id
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

# 4) Observe SSE stream (should include events for this task_id)
curl -N "http://127.0.0.1:8000/api/v1/analysis/tasks/stream?task_id=${TASK_ID}" | sed -n '1,20p'

# 5) Poll task status (must not be 404 and should progress)
curl -fsS "http://127.0.0.1:8000/api/v1/analysis/status/${TASK_ID}"
```

### 4.8 Rollback checklist (WS1 deployment validation path)

```bash
# A. Stop the new version
docker-compose -f ./docker/docker-compose.yml down
# or systemd
# sudo systemctl stop stock-analyzer

# B. Switch to last known-good commit (example: <last-good-commit>)
git fetch --all --tags
git checkout <last-good-commit>

# C. Rebuild and restart
docker-compose -f ./docker/docker-compose.yml build --no-cache
docker-compose -f ./docker/docker-compose.yml up -d
# or systemd
# sudo systemctl start stock-analyzer

# D. Post-rollback validation
curl -fsS http://127.0.0.1:8000/api/health/live
curl -fsS http://127.0.0.1:8000/api/health/ready
python3 scripts/smoke_backtest_standard.py
python3 scripts/smoke_backtest_rule.py
```

### 5. Data Persistence

Data is automatically saved to host directories:
- `./data/` - Database files
- `./logs/` - Log files
- `./reports/` - Analysis reports

---

## Option 2: Direct Deployment

### 1. Install Python Environment

```bash
# Install Python 3.10+
sudo apt update
sudo apt install -y python3.10 python3.10-venv python3-pip

# Create virtual environment
python3.10 -m venv /opt/stock-analyzer/venv
source /opt/stock-analyzer/venv/bin/activate
```

### 2. Install Dependencies

```bash
cd /opt/stock-analyzer
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. Configure Environment Variables

```bash
cp .env.example .env
vim .env  # Fill in configuration
```

### 4. Run

```bash
# Single run
python main.py

# Scheduled task mode (foreground)
python main.py --schedule

# Background run (using nohup)
nohup python main.py --schedule > /dev/null 2>&1 &

# API / Web admin surface (recommended single-process deployment path)
python main.py --serve-only --host 0.0.0.0 --port 8000

# API / Web admin surface + one analysis run at startup
python main.py --serve --host 0.0.0.0 --port 8000

# Liveness / readiness checks
curl -fsS http://127.0.0.1:8000/api/health/live
curl -fsS http://127.0.0.1:8000/api/health/ready
```

---

## Option 3: Systemd Service

Create systemd service file for auto-start on boot and auto-restart:

### 1. Create Service File

```bash
sudo vim /etc/systemd/system/stock-analyzer.service
```

Contents:
```ini
[Unit]
Description=AI Stock Analysis System
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

### 2. Start Service

```bash
# Reload configuration
sudo systemctl daemon-reload

# Start service
sudo systemctl start stock-analyzer

# Enable auto-start on boot
sudo systemctl enable stock-analyzer

# View status
sudo systemctl status stock-analyzer

# View logs
journalctl -u stock-analyzer -f
```

If you also need scheduled analysis, run `--schedule` as a separate service instead of mixing it into the long-running API process.

---

## Configuration Guide

### Required Configuration

| Config Item | Description | How to Get |
|--------|------|----------|
| `GEMINI_API_KEY` | Required for AI analysis | [Google AI Studio](https://aistudio.google.com/) |
| `ADMIN_AUTH_ENABLED` | Admin authentication; must stay `true` in production | `.env.example` |
| `APP_ENV` | Set explicitly to `production` for public or formal rehearsal environments | `.env.example` |
| `VITE_API_URL` | Needed only for split frontend/API deployments; same-origin API is the default | Frontend build environment |

### Optional Configuration

| Config Item | Default | Description |
|--------|--------|------|
| `STOCK_LIST` | `600519,300750,002594` | Watchlist / scheduled analysis targets |
| `PUBLIC_API_ABUSE_LIMIT_*` | See `docs/audits/public-api-abuse-limiter-operator-note.md` | Process-local public API error-burst limiter; not quota/live enforcement |
| `CRYPTO_REALTIME_ENABLED` | `true` | Crypto SSE realtime background connection; record outbound/disablement decision before public launch |
| `SEARXNG_PUBLIC_INSTANCES_ENABLED` | `true` | Discover public instances when no self-hosted SearXNG is configured; record acceptance or disablement before public launch |
| `SCHEDULE_ENABLED` | `false` | Enable scheduled tasks |
| `SCHEDULE_TIME` | `18:00` | Daily execution time |
| `MARKET_REVIEW_ENABLED` | `true` | Enable market review |
| `TAVILY_API_KEYS` | - | News search (optional) |
| `MINIMAX_API_KEYS` | - | MiniMax search (optional) |
| Notification channel variables | - | All optional; configure one or more only if needed |

---

## Proxy Configuration

If server is in mainland China, accessing Gemini API requires proxy:

### Docker Method

Inject proxy environment variables:
```yaml
environment:
  - http_proxy=http://your-proxy:port
  - https_proxy=http://your-proxy:port
```

### Direct Deployment Method

Inject them through systemd, the shell profile, or the startup command:
```bash
export http_proxy=http://your-proxy:port
export https_proxy=http://your-proxy:port
```

---

## Monitoring & Maintenance

### View Logs

```bash
# Docker method
docker-compose -f ./docker/docker-compose.yml logs -f --tail=100

# Direct deployment
tail -f /opt/stock-analyzer/logs/stock_analysis_*.log
```

### Health Check

```bash
# Check process
ps aux | grep main.py

# Check recent reports
ls -la /opt/stock-analyzer/reports/
```

### Routine Maintenance

```bash
# Preview first, then delete only through a reviewed retention workflow
find /opt/stock-analyzer/logs -mtime +7 -print
find /opt/stock-analyzer/reports -mtime +30 -print
```

---

## FAQ

### 1. Docker build failed

```bash
# Clear cache and rebuild
docker-compose -f ./docker/docker-compose.yml build --no-cache
```

### 2. API access timeout

Check proxy configuration, ensure server can access Gemini API.

### 3. Database locked

Do not delete `*.lock` files directly. First confirm whether a process is still running, inspect recent error logs, and verify storage health. Only handle a lock as stale residue when an operator runbook and rollback path already exist.

### 4. Insufficient memory

Adjust memory limits in `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      memory: 1G
```

---

## Quick Migration

Migrate from one server to another:

```bash
# 1) Target server: deploy the code
mkdir -p /opt/stock-analyzer
cd /opt/stock-analyzer
git clone <your-repo-url> .

# 2) Re-inject secrets in the target environment (do not package or transfer raw .env)
cp .env.example .env
vim .env

# 3) Restore data through a controlled backup workflow, not an unencrypted
#    archive of environment files or database directories. Public multi-user
#    still requires isolated restore/PITR,
#    HTTPS staging ingress, backup infra, and rollback proof.

# 4) Start services
docker-compose -f ./docker/docker-compose.yml up -d
```

---

## Option 4: GitHub Actions Deployment (Serverless)

**The simplest option!** No server needed, leverages GitHub's free compute resources.

### Advantages
- ✅ **Completely free** (2000 minutes/month)
- ✅ **No server needed**
- ✅ **Auto-scheduled execution**
- ✅ **Zero maintenance cost**

### Limitations
- ⚠️ Stateless (fresh environment each run)
- ⚠️ Scheduled timing may have few minutes delay
- ⚠️ Cannot provide HTTP API

### Deployment Steps

#### 1. Create GitHub Repository

```bash
# Initialize git (if not already)
cd /path/to/daily_stock_analysis
git init
git add .
git commit -m "Initial commit"

# Create GitHub repo and push
# After creating new repo on GitHub web:
git remote add origin https://github.com/your-username/daily_stock_analysis.git
git branch -M main
git push -u origin main
```

#### 2. Configure Secrets (Important!)

Go to repo page → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these Secrets:

| Secret Name | Description | Required |
|------------|------|------|
| `GEMINI_API_KEY` | Gemini AI API Key | ✅ |
| `WECHAT_WEBHOOK_URL` | WeChat Work Bot Webhook | Optional* |
| `FEISHU_WEBHOOK_URL` | Feishu Bot Webhook | Optional* |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | Optional* |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | Optional* |
| `TELEGRAM_MESSAGE_THREAD_ID` | Telegram Topic ID | Optional* |
| `EMAIL_SENDER` | Sender email | Optional* |
| `EMAIL_PASSWORD` | Email authorization code | Optional* |
| `SERVERCHAN3_SENDKEY` | ServerChan v3 Sendkey | Optional* |
| `CUSTOM_WEBHOOK_URLS` | Custom Webhook (comma-separated for multiple) | Optional* |
| `STOCK_LIST` | Watchlist, e.g., `600519,300750` | ✅ |
| `TAVILY_API_KEYS` | Tavily Search API Key | Recommended |
| `MINIMAX_API_KEYS` | MiniMax Coding Plan Web Search | Optional |
| `SERPAPI_API_KEYS` | SerpAPI Key | Optional |
| `SEARXNG_BASE_URLS` | Self-hosted SearXNG instances; when empty, public instance discovery is the default fallback | Optional |
| `SEARXNG_PUBLIC_INSTANCES_ENABLED` | Whether to discover public instances from `searx.space` when `SEARXNG_BASE_URLS` is empty (default `true`) | Optional |
| `TUSHARE_TOKEN` | Tushare Token | Optional |
| `GEMINI_MODEL` | Model name (default gemini-2.0-flash) | Optional |

> *Note: Configure at least one notification channel, multiple channels supported for simultaneous push

#### 3. Verify Workflow File

Ensure `.github/workflows/daily_analysis.yml` file exists and is committed:

```bash
git add .github/workflows/daily_analysis.yml
git commit -m "Add GitHub Actions workflow"
git push
```

#### 4. Manual Test Run

1. Go to repo page → **Actions** tab
2. Select **"Daily Stock Analysis"** workflow
3. Click **"Run workflow"** button
4. Select run mode:
   - `full` - Full analysis (stocks + market)
   - `market-only` - Market review only
   - `stocks-only` - Stock analysis only
5. Click green **"Run workflow"** button

#### 5. View Execution Logs

- Actions page shows run history
- Click specific run record to view detailed logs
- Analysis reports are saved as Artifacts for 30 days

### Schedule Details

Default configuration: **Monday to Friday, 18:00 Beijing Time** auto-execution

Modify time: Edit cron expression in `.github/workflows/daily_analysis.yml`:

```yaml
schedule:
  - cron: '0 10 * * 1-5'  # UTC time, +8 = Beijing time
```

Common cron examples:
| Expression | Description |
|--------|------|
| `'0 10 * * 1-5'` | Mon-Fri 18:00 (Beijing) |
| `'30 7 * * 1-5'` | Mon-Fri 15:30 (Beijing) |
| `'0 10 * * *'` | Daily 18:00 (Beijing) |
| `'0 2 * * 1-5'` | Mon-Fri 10:00 (Beijing) |

### Modify Watchlist

Method 1: Modify repo Secret `STOCK_LIST`

Method 2: Modify code directly then push:
```bash
# Modify .env.example or set default value in code
git commit -am "Update stock list"
git push
```

### FAQ

**Q: Why isn't the scheduled task running?**
A: GitHub Actions scheduled tasks may have 5-15 minute delays, and only trigger when repo has activity. Long periods without commits may cause workflow to be disabled.

**Q: How to view historical reports?**
A: Actions → Select run record → Artifacts → Download `analysis-reports-xxx`

**Q: Is the free quota enough?**
A: Each run takes about 2-5 minutes, 22 workdays per month = 44-110 minutes, well below the 2000 minute limit.

---

**Wishing you a smooth deployment!**
