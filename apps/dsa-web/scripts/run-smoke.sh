#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${APP_DIR}/../.." && pwd)"

BACKEND_LOG="${TMPDIR:-/tmp}/dsa-web-smoke-backend.log"
PREVIEW_LOG="${TMPDIR:-/tmp}/dsa-web-smoke-preview.log"
BACKEND_URL="${DSA_WEB_SMOKE_BACKEND_URL:-http://127.0.0.1:8000}"
FRONTEND_URL="${DSA_WEB_SMOKE_FRONTEND_URL:-http://127.0.0.1:4173}"

kill_port_listener() {
  local port="$1"
  if ! command -v lsof >/dev/null 2>&1; then
    return 0
  fi

  local pids
  pids="$(lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "${pids}" ]]; then
    return 0
  fi

  echo "Stopping stale listener(s) on 127.0.0.1:${port}: ${pids}"
  kill ${pids} >/dev/null 2>&1 || true
}

cleanup() {
  if [[ -n "${PREVIEW_PID:-}" ]]; then
    kill "${PREVIEW_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "${BACKEND_PID}" >/dev/null 2>&1 || true
  fi
}

wait_for_url() {
  local url="$1"
  local label="$2"
  local attempts=0
  until curl -fsS "${url}" >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [[ "${attempts}" -ge 60 ]]; then
      echo "Timed out waiting for ${label} at ${url}" >&2
      return 1
    fi
    sleep 1
  done
}

trap cleanup EXIT INT TERM

kill_port_listener 4173

cd "${APP_DIR}"
npm run build

if curl -fsS "${BACKEND_URL}/api/v1/auth/status" >/dev/null 2>&1; then
  echo "Using existing backend at ${BACKEND_URL}"
else
  cd "${REPO_ROOT}"
  python3 main.py --serve-only --host 127.0.0.1 --port 8000 >"${BACKEND_LOG}" 2>&1 &
  BACKEND_PID=$!
fi

cd "${APP_DIR}"
npm run preview -- --host 127.0.0.1 --port 4173 >"${PREVIEW_LOG}" 2>&1 &
PREVIEW_PID=$!

wait_for_url "${BACKEND_URL}/api/v1/auth/status" "backend smoke server"
wait_for_url "${FRONTEND_URL}/" "frontend smoke preview"

npm run test:e2e -- e2e/smoke.spec.ts "$@"
