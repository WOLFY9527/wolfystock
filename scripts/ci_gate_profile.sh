#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODE="${1:-backend}"

cd "${ROOT_DIR}"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "[gate-profile] Python interpreter not found (tried python3, python)" >&2
    exit 127
  fi
fi

print_step() {
  echo "==> gate-profile: $1"
}

run_timed() {
  local title="$1"
  shift

  print_step "${title}"
  if command -v time >/dev/null 2>&1; then
    time "$@"
  else
    local start
    local end
    start="$(date +%s)"
    "$@"
    end="$(date +%s)"
    echo "[INFO] elapsed_seconds=$((end - start))"
  fi
}

run_backend_profile() {
  run_timed "offline pytest durations" "${PYTHON_BIN}" -m pytest -m "not network" -p no:cacheprovider --durations=25 --durations-min=0.1
}

run_frontend_profile() {
  if [[ ! -f apps/dsa-web/package.json ]]; then
    echo "[SKIP] frontend test timing: apps/dsa-web/package.json not found"
    return 0
  fi

  run_timed "frontend vitest timing" bash -lc 'cd apps/dsa-web && npm run test --if-present'
}

print_step "preflight"
echo "[INFO] Root: ${ROOT_DIR}"
echo "[INFO] Mode: ${MODE}"
echo "[INFO] This helper profiles gate runtime only. It must not be used to waive ./scripts/ci_gate.sh."

case "${MODE}" in
  backend)
    run_backend_profile
    ;;
  frontend)
    run_frontend_profile
    ;;
  all)
    run_backend_profile
    run_frontend_profile
    ;;
  *)
    echo "Usage: $0 [backend|frontend|all]" >&2
    exit 2
    ;;
esac

print_step "summary"
echo "[PASS] gate profiling completed"
