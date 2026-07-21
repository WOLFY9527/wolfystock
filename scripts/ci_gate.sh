#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -z "${WOLFYSTOCK_TEST_RUN_ID:-}" ]]; then
  exec "${ROOT_DIR}/wolfy" exec --profile test -- bash "${BASH_SOURCE[0]}" "$@"
fi

cd "${ROOT_DIR}"

VALIDATION_TIER="canonical"
TIER_EXPLICIT=0
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --tier)
      [[ "$#" -ge 2 ]] || { echo "[backend-gate] --tier requires canonical or release" >&2; exit 2; }
      VALIDATION_TIER="$2"
      TIER_EXPLICIT=1
      shift 2
      ;;
    -h|--help)
      echo "Usage: scripts/ci_gate.sh [--tier canonical|release]"
      exit 0
      ;;
    *)
      echo "[backend-gate] unknown argument: $1" >&2
      exit 2
      ;;
  esac
done
if [[ "${VALIDATION_TIER}" != "canonical" && "${VALIDATION_TIER}" != "release" ]]; then
  echo "[backend-gate] unknown validation tier: ${VALIDATION_TIER}" >&2
  exit 2
fi

RELEASE_CANDIDATE="output/release/candidate/release-candidate.json"
if [[ -f "${RELEASE_CANDIDATE}" ]]; then
  if [[ "${TIER_EXPLICIT}" -eq 1 && "${VALIDATION_TIER}" != "release" ]]; then
    echo "[backend-gate] release candidate evidence requires --tier release" >&2
    exit 2
  fi
  VALIDATION_TIER="release"
  echo "[backend-gate] release candidate evidence selected the release tier"
fi

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

TEST_EVIDENCE_DIR="output/domain-test-topology/${WOLFYSTOCK_TEST_RUN_ID}"
BASE_REF="${CI_GATE_BASE_REF:-origin/main}"
RISK_PLAN="${TEST_EVIDENCE_DIR}/t631-risk-plan.json"
RAW_FULL_PLAN="${TEST_EVIDENCE_DIR}/t633-full-plan.raw.json"
FULL_PLAN="${TEST_EVIDENCE_DIR}/t633-full-plan.json"
STAGE_PLAN="${TEST_EVIDENCE_DIR}/t637-${VALIDATION_TIER}-stage-plan.json"
SHARDED_DIR="${TEST_EVIDENCE_DIR}/sharded"
mkdir -p "${TEST_EVIDENCE_DIR}"

write_risk_plan() {
  local risk="R3"
  local plan_args=(
    --risk-plan --base-ref "${BASE_REF}" --candidate HEAD --shadow-change-source union
    --requested-risk "${risk}" --accepted-integration
  )
  if [[ "${VALIDATION_TIER}" == "release" ]]; then
    risk="R5"
    plan_args=(
      --risk-plan --base-ref "${BASE_REF}" --candidate HEAD --shadow-change-source union
      --requested-risk "${risk}" --accepted-integration
      --frozen-release --user-facing --release-runtime
    )
  fi
  "${PYTHON_BIN}" "${SCRIPT_DIR}/validation_changed_files.py" "${plan_args[@]}" > "${RISK_PLAN}"
}

write_stage_plan() {
  "${PYTHON_BIN}" "${SCRIPT_DIR}/validation_changed_files.py" \
    --backend-stage-plan "${RISK_PLAN}" --validation-tier "${VALIDATION_TIER}" > "${STAGE_PLAN}"
}

build_full_shard_plan() {
  "${PYTHON_BIN}" -m tests.conftest build-backend-shard-plan \
    --risk-plan "${RISK_PLAN}" --scope full --output "${RAW_FULL_PLAN}" >/dev/null
}

project_shard_plan() {
  "${PYTHON_BIN}" "${SCRIPT_DIR}/validation_changed_files.py" \
    --project-backend-shard-plan "${RAW_FULL_PLAN}" \
    --risk-plan-input "${RISK_PLAN}" --validation-tier "${VALIDATION_TIER}" > "${FULL_PLAN}"
}

run_step "T631 risk selection plan" write_risk_plan
run_step "T637 deterministic ${VALIDATION_TIER} stage plan" write_stage_plan
run_step "T633 deterministic full shard plan" build_full_shard_plan
run_step "T637 project T633 plan onto ${VALIDATION_TIER} stages" project_shard_plan

# Task-local serial equivalence remains available outside this canonical gate via
# domain_test_topology.py run-backend --retry-failures 0.
run_step "offline ${VALIDATION_TIER} backend shard suite (outbound denied + structured reconciliation)" \
  "${PYTHON_BIN}" -m tests.conftest run-backend-shard-suite \
  --plan "${FULL_PLAN}" --output-dir "${SHARDED_DIR}" --timeout-seconds 900

print_step "summary"
echo "[PASS] backend-gate ${VALIDATION_TIER} tier completed successfully"
echo "[INFO] release-ready=false; repository release qualification remains a separate stricter authority"
