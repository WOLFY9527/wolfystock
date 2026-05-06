#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

ALLOW_NETWORK_SCANS="${SECURITY_SCAN_ALLOW_NETWORK:-false}"
RUN_CONTAINER_SCAN="${SECURITY_SCAN_CONTAINER:-false}"

print_step() {
  echo "==> security-scan: $1"
}

warn_missing() {
  echo "[WARN] $1 is not installed; skipped. Install it separately if you want to run this local gate." >&2
}

run_if_available() {
  local tool="$1"
  shift

  if ! command -v "${tool}" >/dev/null 2>&1; then
    warn_missing "${tool}"
    return 0
  fi

  "$@"
}

print_step "preflight"
git status --short

print_step "secret scan (redacted)"
run_if_available gitleaks gitleaks detect --source . --redact --no-banner --exit-code 1

print_step "Bandit SAST"
run_if_available bandit bandit -c pyproject.toml -r api bot data_provider src main.py server.py

if [[ "${ALLOW_NETWORK_SCANS}" == "true" ]]; then
  print_step "Python dependency audit"
  run_if_available pip-audit pip-audit -r requirements.txt -r requirements-dev.txt

  print_step "frontend production npm audit"
  if command -v npm >/dev/null 2>&1; then
    (cd apps/dsa-web && npm audit --omit=dev --audit-level=high)
  else
    warn_missing npm
  fi
else
  print_step "dependency audits"
  echo "[INFO] Skipped pip-audit and npm audit locally because they may contact package advisory services."
  echo "[INFO] Re-run with SECURITY_SCAN_ALLOW_NETWORK=true to enable them."
fi

if [[ "${RUN_CONTAINER_SCAN}" == "true" ]]; then
  print_step "container vulnerability scan"
  if command -v docker >/dev/null 2>&1 && command -v trivy >/dev/null 2>&1; then
    docker build -t daily-stock-analysis:security-scan -f docker/Dockerfile .
    trivy image --severity CRITICAL,HIGH --ignore-unfixed --exit-code 1 daily-stock-analysis:security-scan
  else
    echo "[WARN] docker and trivy are both required for local container scanning; skipped." >&2
  fi
else
  print_step "container vulnerability scan"
  echo "[INFO] Skipped local container scan. Re-run with SECURITY_SCAN_CONTAINER=true when docker and trivy are available."
fi
