#!/usr/bin/env bash

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CURRENT_DIR="$(pwd -P)"
READINESS_URL="http://127.0.0.1:8000/api/v1/market/data-readiness?symbols=ORCL,AAPL,SPY"
REPRESENTATIVE_SYMBOLS=("ORCL" "AAPL" "SPY")
WARNINGS=0

ok() {
  printf '[OK] %s\n' "$1"
}

info() {
  printf '[INFO] %s\n' "$1"
}

warn() {
  WARNINGS=$((WARNINGS + 1))
  printf '[WARN] %s\n' "$1"
}

section() {
  printf '\n== %s ==\n' "$1"
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

resolve_python() {
  if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
    printf '%s\n' "${ROOT_DIR}/.venv/bin/python"
    return 0
  fi

  if command_exists python3; then
    command -v python3
    return 0
  fi

  if command_exists python; then
    command -v python
    return 0
  fi

  return 1
}

check_repo_root() {
  local git_root

  section "Repository"
  info "Current directory: ${CURRENT_DIR}"
  info "Script repo root: ${ROOT_DIR}"

  git_root="$(git -C "${CURRENT_DIR}" rev-parse --show-toplevel 2>/dev/null || true)"
  if [[ -z "${git_root}" ]]; then
    warn "Current directory is not inside a git repository."
    return 0
  fi

  info "Current git root: ${git_root}"
  if [[ "${git_root}" == "${ROOT_DIR}" ]]; then
    ok "Current directory belongs to this repository."
  else
    warn "Current git root does not match the script repository root."
  fi

  if [[ "${CURRENT_DIR}" == "${ROOT_DIR}" ]]; then
    ok "Current directory is the repository root."
  else
    warn "Run from the repository root for the least surprising relative paths: cd ${ROOT_DIR}"
  fi
}

check_venv() {
  section "Python Environment"
  if [[ -d "${ROOT_DIR}/.venv" ]]; then
    ok ".venv directory exists."
    if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
      ok ".venv Python is executable."
    else
      warn ".venv exists but .venv/bin/python is not executable."
    fi
  else
    warn ".venv directory is missing."
  fi

  info "Activation command: source .venv/bin/activate"
  info "This script does not source the virtualenv, modify env vars, or install packages."
}

check_parquet_engine() {
  local python_bin
  local engine
  local engine_status

  section "Parquet Engine"
  if ! python_bin="$(resolve_python)"; then
    warn "No python/python3 interpreter found; cannot check pyarrow or fastparquet imports."
    return 0
  fi

  info "Import check interpreter: ${python_bin}"
  for engine in pyarrow fastparquet; do
    engine_status="$("${python_bin}" - "${engine}" <<'PY'
import importlib
import sys

name = sys.argv[1]
try:
    importlib.import_module(name)
except Exception as exc:
    print(exc.__class__.__name__)
    raise SystemExit(1)
else:
    print("available")
PY
    )"
    if [[ "${engine_status}" == "available" ]]; then
      ok "${engine}: import available"
    else
      warn "${engine}: import unavailable (${engine_status})"
    fi
  done
}

check_parquet_dir() {
  local parquet_dir=""
  local source_env=""
  local missing=0
  local symbol
  local path

  section "Local US Parquet"
  if [[ -n "${LOCAL_US_PARQUET_DIR:-}" ]]; then
    parquet_dir="${LOCAL_US_PARQUET_DIR}"
    source_env="LOCAL_US_PARQUET_DIR"
  elif [[ -n "${US_STOCK_PARQUET_DIR:-}" ]]; then
    parquet_dir="${US_STOCK_PARQUET_DIR}"
    source_env="US_STOCK_PARQUET_DIR"
  fi

  if [[ -z "${parquet_dir}" ]]; then
    warn "Neither LOCAL_US_PARQUET_DIR nor US_STOCK_PARQUET_DIR is set."
    info "Set LOCAL_US_PARQUET_DIR first; US_STOCK_PARQUET_DIR is legacy fallback compatibility."
    return 0
  fi

  info "Using ${source_env}: ${parquet_dir}"
  if [[ ! -e "${parquet_dir}" ]]; then
    warn "Configured parquet path does not exist."
    return 0
  fi

  if [[ ! -d "${parquet_dir}" ]]; then
    warn "Configured parquet path is not a directory."
    return 0
  fi

  ok "Configured parquet directory exists."
  for symbol in "${REPRESENTATIVE_SYMBOLS[@]}"; do
    path="${parquet_dir}/${symbol}.parquet"
    if [[ -f "${path}" ]]; then
      ok "Representative file exists: ${symbol}.parquet"
    else
      warn "Representative file missing: ${symbol}.parquet"
      missing=$((missing + 1))
    fi
  done

  if [[ "${missing}" -eq 0 ]]; then
    ok "Representative ORCL/AAPL/SPY parquet files are present."
  else
    info "This script checks file presence only; it does not read parquet contents."
  fi
}

check_tushare_token() {
  local token_env_name

  section "Tushare Token"
  token_env_name="TUSHARE""_TOKEN"
  if [[ -n "${!token_env_name:-}" ]]; then
    ok "TUSHARE_TOKEN present: true"
  else
    warn "TUSHARE_TOKEN present: false"
  fi
  info "Secret values are never printed."
}

check_readiness_api() {
  local tmp_body
  local http_code
  local python_bin

  section "Local Readiness API"
  if ! command_exists curl; then
    info "curl is unavailable; skipping optional local readiness API probe."
    return 0
  fi

  tmp_body="$(mktemp)"
  http_code="$(curl --silent --show-error --max-time 2 --output "${tmp_body}" --write-out '%{http_code}' "${READINESS_URL}" 2>/dev/null || true)"
  if [[ "${http_code}" == "000" || -z "${http_code}" ]]; then
    info "Backend not reachable on 127.0.0.1:8000; skipped optional readiness API probe."
    rm -f "${tmp_body}"
    return 0
  fi

  info "GET ${READINESS_URL}"
  info "HTTP status: ${http_code}"
  if [[ "${http_code}" == "200" ]]; then
    if python_bin="$(resolve_python)"; then
      "${python_bin}" - "${tmp_body}" <<'PY' || true
import json
import sys

try:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        payload = json.load(handle)
except Exception:
    print("[INFO] Readiness API returned a non-JSON or unreadable body; body not printed.")
else:
    status = payload.get("readinessStatus") or payload.get("readiness_status") or "unknown"
    checks = payload.get("checks")
    check_count = len(checks) if isinstance(checks, list) else 0
    print(f"[OK] readinessStatus: {status}; checks: {check_count}")
PY
    else
      ok "Readiness API returned HTTP 200."
    fi
  else
    warn "Readiness API returned non-200 status ${http_code}."
  fi

  rm -f "${tmp_body}"
}

section "Market Data Readiness Preflight"
info "Local-only diagnostic. No providers are called. No external network calls are made."
info "No environment variables are modified and no packages are installed."

check_repo_root
check_venv
check_parquet_engine
check_parquet_dir
check_tushare_token
check_readiness_api

section "Summary"
if [[ "${WARNINGS}" -eq 0 ]]; then
  ok "No warnings detected."
  exit 0
fi

printf '[WARN] Completed with %s warning(s). Review the items above before relying on local market data readiness.\n' "${WARNINGS}"
exit 1
