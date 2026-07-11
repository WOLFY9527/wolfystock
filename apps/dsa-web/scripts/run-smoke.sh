#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${APP_DIR}/../.." && pwd)"

HOST="127.0.0.1"
DEFAULT_PORT="4173"
SMOKE_PORT="${DSA_WEB_SMOKE_PORT:-${DSA_WEB_PLAYWRIGHT_PORT:-${DEFAULT_PORT}}}"
SMOKE_SPEC="${DSA_WEB_SMOKE_SPEC:-e2e/runtime-contract.smoke.spec.ts}"
SMOKE_PROJECTS="${DSA_WEB_SMOKE_PROJECTS:-chromium,chromium-mobile}"
SMOKE_BASE_DIR="${DSA_WEB_SMOKE_OUTPUT_DIR:-${APP_DIR}/test-results/frontend-smoke}"
SMOKE_RUN_ID="${DSA_WEB_SMOKE_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
SMOKE_RUN_DIR="${SMOKE_BASE_DIR}/${SMOKE_RUN_ID}"
RUNNER_LOG="${SMOKE_RUN_DIR}/runner.log"
PREVIEW_LOG="${SMOKE_RUN_DIR}/preview.log"
REPORT_DIR="${SMOKE_RUN_DIR}/playwright-report"
PLAYWRIGHT_OUTPUT_DIR="${SMOKE_RUN_DIR}/test-results"
BUILD_ONCE="${DSA_WEB_SMOKE_BUILD:-1}"
HOLD_PREVIEW="${DSA_WEB_SMOKE_HOLD_PREVIEW:-0}"

PREVIEW_PID=""

print_usage() {
  cat <<'USAGE'
Usage: bash scripts/run-smoke.sh [--expect-failure] [--hold-preview] [playwright args...]

Environment:
  DSA_WEB_SMOKE_PORT        Preview port. Defaults to DSA_WEB_PLAYWRIGHT_PORT or 4173.
  DSA_WEB_SMOKE_SPEC        Smoke spec. Defaults to e2e/runtime-contract.smoke.spec.ts.
  DSA_WEB_SMOKE_PROJECTS    Comma-separated projects. Defaults to chromium,chromium-mobile.
  DSA_WEB_SMOKE_OUTPUT_DIR  Smoke artifact root. Defaults to apps/dsa-web/test-results/frontend-smoke.
  DSA_WEB_SMOKE_BUILD       Set to 0 to skip npm run build.
  DSA_WEB_SMOKE_HOLD_PREVIEW=1 keeps preview alive after tests for manual inspection.
USAGE
}

sanitize_log() {
  perl -0pi \
    -e "s/(password|token|secret|api[_-]?key|authorization|cookie|session[_-]?id)([\\\"'\\s:=]+)[^\\s\\\"']+/\\1\\2[REDACTED]/gi" \
    -e 's/Bearer\s+[A-Za-z0-9._~+\/=-]+/Bearer [REDACTED]/gi' \
    -e 's/sk-[A-Za-z0-9_-]{12,}/sk-[REDACTED]/g' \
    -e 's/ghp_[A-Za-z0-9_]{12,}/ghp_[REDACTED]/g' \
    -e 's/xox[baprs]-[A-Za-z0-9-]{12,}/xox[REDACTED]/g' \
    "$@" 2>/dev/null || true
}

is_integer_port() {
  [[ "$1" =~ ^[0-9]+$ ]] && (( "$1" >= 1 && "$1" <= 65535 ))
}

port_listeners() {
  local port="$1"
  if ! command -v lsof >/dev/null 2>&1; then
    echo "lsof is required to prove ${HOST}:${port} ownership on macOS." >&2
    return 1
  fi
  lsof -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true
}

terminate_process_tree() {
  local pid="$1"
  local children
  children="$(pgrep -P "${pid}" 2>/dev/null || true)"
  for child in ${children}; do
    terminate_process_tree "${child}"
  done
  kill "${pid}" >/dev/null 2>&1 || true
}

ensure_port_available() {
  local port="$1"
  local listeners
  listeners="$(port_listeners "${port}")"
  if [[ -n "${listeners}" ]]; then
    {
      echo "Blocked: ${HOST}:${port} already has a listener."
      echo "${listeners}"
      echo "Choose another port with DSA_WEB_SMOKE_PORT or stop the owning process explicitly."
    } >&2
    return 1
  fi
}

wait_for_url() {
  local url="$1"
  local label="$2"
  local attempts=0
  until curl -fsS "${url}" >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [[ "${attempts}" -ge 90 ]]; then
      echo "Timed out waiting for ${label} at ${url}" >&2
      return 1
    fi
    if [[ -n "${PREVIEW_PID}" ]] && ! kill -0 "${PREVIEW_PID}" >/dev/null 2>&1; then
      echo "Preview process exited before ${label} became reachable. See ${PREVIEW_LOG}" >&2
      return 1
    fi
    sleep 1
  done
}

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM

  if [[ "${HOLD_PREVIEW}" == "1" ]]; then
    echo "Holding preview process ${PREVIEW_PID:-unknown} on http://${HOST}:${SMOKE_PORT}"
  elif [[ -n "${PREVIEW_PID}" ]] && kill -0 "${PREVIEW_PID}" >/dev/null 2>&1; then
    terminate_process_tree "${PREVIEW_PID}"
    wait "${PREVIEW_PID}" >/dev/null 2>&1 || true
  fi

  sanitize_log "${RUNNER_LOG}" "${PREVIEW_LOG}"
  if [[ "${HOLD_PREVIEW}" != "1" ]]; then
    sleep 1
  fi
  local remaining_listeners=""
  if [[ "${HOLD_PREVIEW}" != "1" ]]; then
    remaining_listeners="$(port_listeners "${SMOKE_PORT}" || true)"
  fi
  {
    echo "exit_code=${exit_code}"
    echo "base_url=http://${HOST}:${SMOKE_PORT}"
    echo "run_dir=${SMOKE_RUN_DIR}"
    echo "report_dir=${REPORT_DIR}"
    echo "playwright_output_dir=${PLAYWRIGHT_OUTPUT_DIR}"
    echo "preview_pid=${PREVIEW_PID:-}"
    if [[ "${HOLD_PREVIEW}" == "1" ]]; then
      echo "preview_cleanup=held"
    else
      echo "preview_cleanup=stopped"
    fi
    if [[ -z "${remaining_listeners}" ]]; then
      echo "port_cleanup=released"
    else
      echo "port_cleanup=still_listening"
      echo "remaining_port_listener<<EOF"
      echo "${remaining_listeners}"
      echo "EOF"
    fi
  } >"${SMOKE_RUN_DIR}/runtime-summary.env"

  if [[ -n "${remaining_listeners}" ]]; then
    echo "Port ${HOST}:${SMOKE_PORT} still has a listener after cleanup." >&2
    echo "${remaining_listeners}" >&2
    return 1
  fi

  return "${exit_code}"
}

EXPECT_FAILURE="0"
PLAYWRIGHT_ARGS=()
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --help|-h)
      print_usage
      exit 0
      ;;
    --expect-failure)
      EXPECT_FAILURE="1"
      shift
      ;;
    --hold-preview)
      HOLD_PREVIEW="1"
      shift
      ;;
    --)
      shift
      PLAYWRIGHT_ARGS+=("$@")
      break
      ;;
    *)
      PLAYWRIGHT_ARGS+=("$1")
      shift
      ;;
  esac
done

if ! is_integer_port "${SMOKE_PORT}"; then
  echo "DSA_WEB_SMOKE_PORT must be an integer TCP port from 1 to 65535. Received: ${SMOKE_PORT}" >&2
  exit 2
fi

mkdir -p "${SMOKE_RUN_DIR}" "${REPORT_DIR}" "${PLAYWRIGHT_OUTPUT_DIR}"
touch "${RUNNER_LOG}" "${PREVIEW_LOG}"
trap cleanup EXIT INT TERM

{
  echo "repo_root=${REPO_ROOT}"
  echo "app_dir=${APP_DIR}"
  echo "smoke_spec=${SMOKE_SPEC}"
  echo "smoke_projects=${SMOKE_PROJECTS}"
  echo "base_url=http://${HOST}:${SMOKE_PORT}"
  echo "run_dir=${SMOKE_RUN_DIR}"
  echo "report_dir=${REPORT_DIR}"
  echo "playwright_output_dir=${PLAYWRIGHT_OUTPUT_DIR}"
} | tee -a "${RUNNER_LOG}"

ensure_port_available "${SMOKE_PORT}" | tee -a "${RUNNER_LOG}"

cd "${APP_DIR}"
if [[ "${BUILD_ONCE}" == "1" ]]; then
  npm run build 2>&1 | tee -a "${RUNNER_LOG}"
fi

npm run preview -- --host "${HOST}" --port "${SMOKE_PORT}" >"${PREVIEW_LOG}" 2>&1 &
PREVIEW_PID=$!
echo "preview_pid=${PREVIEW_PID}" | tee -a "${RUNNER_LOG}"

wait_for_url "http://${HOST}:${SMOKE_PORT}/" "frontend smoke preview"

PROJECT_ARGS=()
IFS=',' read -r -a PROJECTS <<<"${SMOKE_PROJECTS}"
for project in "${PROJECTS[@]}"; do
  trimmed_project="$(echo "${project}" | xargs)"
  if [[ -n "${trimmed_project}" ]]; then
    PROJECT_ARGS+=("--project=${trimmed_project}")
  fi
done

set +e
CI=1 \
DSA_WEB_PLAYWRIGHT_PORT="${SMOKE_PORT}" \
DSA_WEB_PLAYWRIGHT_BASE_URL="http://${HOST}:${SMOKE_PORT}" \
DSA_WEB_PLAYWRIGHT_EXTERNAL_SERVER=1 \
PLAYWRIGHT_HTML_REPORT="${REPORT_DIR}" \
PLAYWRIGHT_OUTPUT_DIR="${PLAYWRIGHT_OUTPUT_DIR}" \
npx playwright test "${SMOKE_SPEC}" ${PROJECT_ARGS+"${PROJECT_ARGS[@]}"} ${PLAYWRIGHT_ARGS+"${PLAYWRIGHT_ARGS[@]}"} 2>&1 | tee -a "${RUNNER_LOG}"
TEST_EXIT=${PIPESTATUS[0]}
set -e

sanitize_log "${RUNNER_LOG}" "${PREVIEW_LOG}"

if [[ "${EXPECT_FAILURE}" == "1" ]]; then
  if [[ "${TEST_EXIT}" -eq 0 ]]; then
    echo "Expected smoke failure, but Playwright passed." | tee -a "${RUNNER_LOG}" >&2
    exit 1
  fi
  echo "Observed expected smoke failure with exit code ${TEST_EXIT}." | tee -a "${RUNNER_LOG}"
  exit 0
fi

exit "${TEST_EXIT}"
