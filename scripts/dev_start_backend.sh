#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

HOST="127.0.0.1"
PORT="8000"
PYTHON_BIN=""
LOCAL_US_PARQUET_OVERRIDE=""
RESTART_PORT="false"
PRINT_COMMAND="false"
EXTRA_ARGS=()
COMMAND=()

usage() {
  cat <<'EOF'
Usage: bash scripts/dev_start_backend.sh [options] [-- <extra main.py args>]

Start the local backend without sourcing .env.

Options:
  --host HOST                  Bind host for main.py --serve-only (default: 127.0.0.1)
  --port PORT                  Bind port for main.py --serve-only (default: 8000)
  --python PATH                Override Python interpreter
  --local-us-parquet-dir PATH  Export LOCAL_US_PARQUET_DIR for this process only
  --restart-port               Kill listeners on the selected port before start
  --print-command              Print the backend command and exit
  --help                       Show this help message

Notes:
  - This helper does not activate a virtualenv or source .env.
  - App config still loads .env on startup; use shell exports only for deliberate overrides.
  - Existing proxy variables from your current shell are preserved as-is.
  - If the selected port is already busy, rerun with --restart-port or choose another --port.
EOF
}

log() {
  printf '[dev-start] %s\n' "$1"
}

fail() {
  printf '[dev-start] %s\n' "$1" >&2
  exit 1
}

resolve_python() {
  if [[ -n "${PYTHON_BIN}" ]]; then
    [[ -x "${PYTHON_BIN}" ]] || fail "Python interpreter is not executable: ${PYTHON_BIN}"
    return 0
  fi

  if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
    PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
    return 0
  fi

  PYTHON_BIN="$(command -v python3 || true)"
  [[ -n "${PYTHON_BIN}" ]] || fail "python3 not found and ${ROOT_DIR}/.venv/bin/python is unavailable."
}

maybe_export_ssl_cert_file() {
  local cert_path=""

  if [[ -n "${SSL_CERT_FILE:-}" ]]; then
    return 0
  fi

  cert_path="$("${PYTHON_BIN}" -c 'import certifi; print(certifi.where())' 2>/dev/null || true)"
  if [[ -n "${cert_path}" && -f "${cert_path}" ]]; then
    export SSL_CERT_FILE="${cert_path}"
    log "SSL_CERT_FILE set from certifi CA bundle."
  fi
}

maybe_export_local_us_parquet_dir() {
  if [[ -n "${LOCAL_US_PARQUET_OVERRIDE}" ]]; then
    export LOCAL_US_PARQUET_DIR="${LOCAL_US_PARQUET_OVERRIDE}"
    return 0
  fi

  if [[ -n "${LOCAL_US_PARQUET_DIR:-}" ]]; then
    return 0
  fi

  if [[ -n "${US_STOCK_PARQUET_DIR:-}" ]]; then
    export LOCAL_US_PARQUET_DIR="${US_STOCK_PARQUET_DIR}"
  fi
}

find_port_pids() {
  local port="$1"

  if ! command -v lsof >/dev/null 2>&1; then
    fail "lsof is required to inspect port ${port}."
  fi

  lsof -ti "tcp:${port}" || true
}

ensure_port_is_available() {
  local pids=""

  pids="$(find_port_pids "${PORT}")"
  [[ -z "${pids}" ]] && return 0

  if [[ "${RESTART_PORT}" != "true" ]]; then
    fail "Port ${PORT} is already in use. Re-run with --restart-port or choose another --port."
  fi

  log "Stopping existing listener(s) on port ${PORT}."
  kill ${pids}
  sleep 1

  pids="$(find_port_pids "${PORT}")"
  [[ -z "${pids}" ]] || fail "Port ${PORT} is still busy after --restart-port."
}

build_command() {
  COMMAND=("${PYTHON_BIN}" "${ROOT_DIR}/main.py" --serve-only --host "${HOST}" --port "${PORT}")
  if ((${#EXTRA_ARGS[@]} > 0)); then
    COMMAND+=("${EXTRA_ARGS[@]}")
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      [[ $# -ge 2 ]] || fail "Missing value for --host"
      HOST="$2"
      shift 2
      ;;
    --port)
      [[ $# -ge 2 ]] || fail "Missing value for --port"
      PORT="$2"
      shift 2
      ;;
    --python)
      [[ $# -ge 2 ]] || fail "Missing value for --python"
      PYTHON_BIN="$2"
      shift 2
      ;;
    --local-us-parquet-dir)
      [[ $# -ge 2 ]] || fail "Missing value for --local-us-parquet-dir"
      LOCAL_US_PARQUET_OVERRIDE="$2"
      shift 2
      ;;
    --restart-port)
      RESTART_PORT="true"
      shift
      ;;
    --print-command)
      PRINT_COMMAND="true"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      EXTRA_ARGS+=("$@")
      break
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

resolve_python
maybe_export_local_us_parquet_dir
maybe_export_ssl_cert_file
build_command

if [[ "${PRINT_COMMAND}" == "true" ]]; then
  printf '%q ' "${COMMAND[@]}"
  printf '\n'
  exit 0
fi

ensure_port_is_available

log "Using Python: ${PYTHON_BIN}"
log "Serving on ${HOST}:${PORT}"
if [[ -n "${LOCAL_US_PARQUET_DIR:-}" ]]; then
  log "LOCAL_US_PARQUET_DIR is set for this process."
fi
if [[ -n "${HTTP_PROXY:-}${HTTPS_PROXY:-}${ALL_PROXY:-}${NO_PROXY:-}" ]]; then
  log "Proxy environment variables are preserved from the current shell."
fi

cd "${ROOT_DIR}"
exec "${COMMAND[@]}"
