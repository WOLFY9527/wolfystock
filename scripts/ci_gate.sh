#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -z "${WOLFYSTOCK_TEST_RUN_ID:-}" ]]; then
  exec "${ROOT_DIR}/wolfy" exec --profile test -- bash "${BASH_SOURCE[0]}" "$@"
fi

cd "${ROOT_DIR}"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    echo "[backend-gate] Python interpreter not found (tried python, python3)" >&2
    exit 127
  fi
fi
export PYTHON_BIN

print_step() {
  echo "==> backend-gate: $1"
}

run_step() {
  local title="$1"
  shift

  print_step "${title}"
  if "$@"; then
    echo "[PASS] ${title}"
  else
    local rc=$?
    echo "[FAIL] ${title} (exit ${rc})" >&2
    return "${rc}"
  fi
}

run_flake8_critical() {
  print_step "environment / optional tools"
  echo "[INFO] Python: ${PYTHON_BIN}"
  if command -v flake8 >/dev/null 2>&1; then
    echo "[INFO] flake8: available on PATH"
  elif "${PYTHON_BIN}" -c "import flake8" >/dev/null 2>&1; then
    echo "[INFO] flake8: available as a Python module"
  else
    if [[ -n "${CI:-}" ]]; then
      echo "[ERROR] flake8 is required in CI but is not available" >&2
      exit 127
    fi
    echo "[WARN] flake8 is not installed locally; critical lint coverage is reported as a warning here, but remains required in CI."
  fi
  if "${PYTHON_BIN}" -c "import akshare" >/dev/null 2>&1; then
    echo "[INFO] akshare: available"
  else
    echo "[WARN] akshare is not installed locally; provider-dependent smoke checks may report environment/provider availability issues instead of code regressions."
  fi
  if "${PYTHON_BIN}" -c "import yfinance" >/dev/null 2>&1; then
    echo "[INFO] yfinance: available"
  else
    echo "[WARN] yfinance is not installed locally; yfinance smoke checks may report environment/provider availability issues instead of code regressions."
  fi

  if command -v flake8 >/dev/null 2>&1; then
    run_step "backend critical lint" flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
    return 0
  fi
  if "${PYTHON_BIN}" -c "import flake8" >/dev/null 2>&1; then
    run_step "backend critical lint" "${PYTHON_BIN}" -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
    return 0
  fi
  if [[ -n "${CI:-}" ]]; then
    echo "[ERROR] flake8 is required in CI but is not available" >&2
    exit 127
  fi
  echo "[WARN] flake8 not installed; install dev tools with: ${PYTHON_BIN} -m pip install -r requirements-dev.txt"
}

print_step "preflight status"
"${SCRIPT_DIR}/task_preflight.sh"

run_flake8_critical

run_step "backend syntax check (core app)" "${PYTHON_BIN}" -m py_compile main.py src/config.py src/auth.py src/analyzer.py src/notification.py
run_step "backend syntax check (storage + search)" "${PYTHON_BIN}" -m py_compile src/storage.py src/scheduler.py src/search_service.py
run_step "backend syntax check (market analyzers)" "${PYTHON_BIN}" -m py_compile src/market_analyzer.py src/stock_analyzer.py
run_step "backend syntax check (data providers)" "${PYTHON_BIN}" -m py_compile data_provider/*.py

print_step "local deterministic checks"
echo "[INFO] Provider-dependent test.sh warnings are treated as environment/provider issues when they mention missing modules or unavailable fetchers."
run_step "test.sh code" ./test.sh code
run_step "test.sh yfinance" ./test.sh yfinance

run_step "offline test suite (outbound denied + domain parity)" "${PYTHON_BIN}" -m pytest --domain-topology-verify-full

print_step "summary"
echo "[PASS] backend-gate completed successfully"
