#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BASE_REF="${CI_GATE_BASE_REF:-origin/main}"
REQUESTED_RISK="${CI_GATE_REQUESTED_RISK:-}"
PLAN_ONLY=0
FROZEN_RELEASE=0
ACCEPTED_INTEGRATION=0
USER_FACING=0
RELEASE_RUNTIME=0
REQUESTED_GATES=()
COLLECTOR="${ROOT_DIR}/scripts/validation_changed_files.py"

if [[ -z "${WOLFYSTOCK_TEST_RUN_ID:-}" ]]; then
  exec "${ROOT_DIR}/wolfy" exec --profile test -- bash "${BASH_SOURCE[0]}" "$@"
fi

usage() {
  cat <<'EOF'
Usage: scripts/ci_gate_fast.sh [options]

Select and execute cumulative R0-R5 validation from the structured risk plan.
The selector is fail-closed: missing, ambiguous, or mismatched evidence stops
the gate and never widens into an implicit universal fallback.

Options:
  --base-ref REF             Override CI_GATE_BASE_REF/origin/main.
  --requested-risk R0..R5    Apply an explicit task risk floor.
  --requested-gate GATE      Add an explicit gate; may be repeated.
  --frozen-release            Select R5 release-candidate requirements.
  --accepted-integration     Select accepted-batch canonical backend evidence.
  --user-facing              Require the R4 UAT trigger when applicable.
  --release-runtime          Require release startup/artifact validation.
  --plan-only                Emit the deterministic plan without executing it.
  -h, --help                 Show this help text.
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --base-ref)
      [[ "$#" -ge 2 ]] || { echo "[fast-gate] --base-ref requires a ref" >&2; exit 2; }
      BASE_REF="$2"
      shift 2
      ;;
    --requested-risk)
      [[ "$#" -ge 2 ]] || { echo "[fast-gate] --requested-risk requires R0..R5" >&2; exit 2; }
      REQUESTED_RISK="$2"
      shift 2
      ;;
    --requested-gate)
      [[ "$#" -ge 2 ]] || { echo "[fast-gate] --requested-gate requires a gate id" >&2; exit 2; }
      REQUESTED_GATES+=("$2")
      shift 2
      ;;
    --frozen-release)
      FROZEN_RELEASE=1
      shift
      ;;
    --accepted-integration)
      ACCEPTED_INTEGRATION=1
      shift
      ;;
    --user-facing)
      USER_FACING=1
      shift
      ;;
    --release-runtime)
      RELEASE_RUNTIME=1
      shift
      ;;
    --plan-only)
      PLAN_ONLY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[fast-gate] unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cd "${ROOT_DIR}"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "[fast-gate] Python interpreter not found (tried python3, python)" >&2
    exit 127
  fi
fi

mkdir -p "${ROOT_DIR}/output"
TMP_DIR="$(mktemp -d "${ROOT_DIR}/output/ci_gate_fast.XXXXXX")"
trap 'rm -rf "${TMP_DIR}"' EXIT
PLAN_PATH="${TMP_DIR}/validation-plan.json"
EXECUTION_DIR="${TMP_DIR}/validation-execution"

PLAN_ARGS=(
  --risk-plan
  --base-ref "${BASE_REF}"
  --candidate HEAD
  --shadow-change-source union
)
if [[ -n "${REQUESTED_RISK}" ]]; then
  PLAN_ARGS+=(--requested-risk "${REQUESTED_RISK}")
fi
if [[ "${FROZEN_RELEASE}" -eq 1 ]]; then
  PLAN_ARGS+=(--frozen-release)
fi
if [[ "${ACCEPTED_INTEGRATION}" -eq 1 ]]; then
  PLAN_ARGS+=(--accepted-integration)
fi
if [[ "${USER_FACING}" -eq 1 ]]; then
  PLAN_ARGS+=(--user-facing)
fi
if [[ "${RELEASE_RUNTIME}" -eq 1 ]]; then
  PLAN_ARGS+=(--release-runtime)
fi
if [[ -n "${REQUESTED_GATES[*]-}" ]]; then
  for gate in "${REQUESTED_GATES[@]}"; do
    PLAN_ARGS+=(--requested-gate "${gate}")
  done
fi

echo "==> fast-gate: build cumulative validation plan"
"${PYTHON_BIN}" "${COLLECTOR}" "${PLAN_ARGS[@]}" >"${PLAN_PATH}"
cat "${PLAN_PATH}"

if [[ "${PLAN_ONLY}" -eq 1 ]]; then
  echo "[PASS] validation plan emitted; execution intentionally not requested"
  exit 0
fi

echo "==> fast-gate: execute selected validation plan"
set +e
"${PYTHON_BIN}" "${COLLECTOR}" \
  --execute-validation-plan "${PLAN_PATH}" \
  --execution-output-dir "${EXECUTION_DIR}"
RC=$?
set -e
if [[ "${RC}" -ne 0 ]]; then
  echo "[FAIL] selected validation plan (exit ${RC})" >&2
  exit "${RC}"
fi

echo "[PASS] cumulative validation plan completed"
