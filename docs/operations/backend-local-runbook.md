# Backend Local Runbook

Status: active local operator runbook.

Use this runbook for local backend bring-up and health checks in the current
workspace. This is a local operator path only; it does not authorize live
provider checks, deployment changes, or runtime semantic changes.

## Local Proxy Mode (`127.0.0.1:7890`)

Use this block only when your local operator environment needs the existing
local proxy:

```bash
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
export NO_PROXY=127.0.0.1,localhost
export no_proxy=127.0.0.1,localhost
```

## Canonical Local Startup

Always start the backend with the project `.venv`. Do not put Framework Python
first for `api.app` import or uvicorn startup.

```bash
source .venv/bin/activate
python3 -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

If you want the explicit interpreter path instead of shell activation:

```bash
.venv/bin/python3 -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Do not use `/Library/Frameworks/Python.framework/.../python3` for this local
backend path. If `which python3` resolves to Framework Python after activation,
stop and reactivate `.venv`.

## Local Runtime Constraints

- The local task queue is `process_local`.
- `single_process_required=true` is part of readiness.
- Run local uvicorn as a single process; do not add multi-worker local startup
  flags for this operator path.

## Health Checks

After startup, verify all three endpoints:

```bash
curl -fsS http://127.0.0.1:8000/api/health
curl -fsS http://127.0.0.1:8000/api/health/live
curl -fsS http://127.0.0.1:8000/api/health/ready
```

Expected result: each endpoint returns `status=ok` for the current local-ready
state.

## Known Non-Blocking Warnings

LiteLLM may emit Bedrock/SageMaker botocore warnings during local startup or
import. For this runbook, treat them as non-blocking unless you are actively
using those providers.

## Do Not Use This Runbook For

- live provider verification
- multi-process or multi-instance queue/SSE validation
- deployment or release approval
