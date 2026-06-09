#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BASE_REF="${CI_GATE_BASE_REF:-origin/main}"
MAX_FOCUSED_TESTS="${CI_GATE_FAST_MAX_TESTS:-24}"
COLLECTOR="${ROOT_DIR}/scripts/validation_changed_files.py"

usage() {
  cat <<'EOF'
Usage: scripts/ci_gate_fast.sh [--base-ref REF]

Changed-file-focused local iteration gate. This script is intentionally
conservative: unknown classifications, lock/workflow risk, or protected-domain
changes escalate to ./scripts/ci_gate.sh instead of narrowing validation.

Options:
  --base-ref REF  Override CI_GATE_BASE_REF/origin/main.
  -h, --help      Show this help text.
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --base-ref)
      if [[ "$#" -lt 2 ]]; then
        echo "[fast-gate] --base-ref requires a ref" >&2
        exit 2
      fi
      BASE_REF="$2"
      shift 2
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

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ci_gate_fast.XXXXXX")"
trap 'rm -rf "${TMP_DIR}"' EXIT

CHANGED_ALL="${TMP_DIR}/changed_all.txt"
BRANCH_CHANGED="${TMP_DIR}/changed_branch.txt"
LOCAL_CHANGED="${TMP_DIR}/changed_local.txt"
CHANGED_SORTED="${TMP_DIR}/changed_sorted.txt"
GATE_FILES="${TMP_DIR}/gate_files.txt"
PYTHON_FILES_LIST="${TMP_DIR}/python_files.txt"
FOCUSED_TESTS_LIST="${TMP_DIR}/focused_tests.txt"
DOC_TEXT_FILES_LIST="${TMP_DIR}/doc_text_files.txt"
CLASSIFICATION_JSON="${TMP_DIR}/classification.json"
FRONTEND_RELATED_FILES_LIST="${TMP_DIR}/frontend_related_files.txt"
FRONTEND_DESIGN_FILES_LIST="${TMP_DIR}/frontend_design_files.txt"

touch "${CHANGED_ALL}" "${BRANCH_CHANGED}" "${LOCAL_CHANGED}" "${CHANGED_SORTED}" "${GATE_FILES}" "${PYTHON_FILES_LIST}" "${FOCUSED_TESTS_LIST}" "${DOC_TEXT_FILES_LIST}" "${FRONTEND_RELATED_FILES_LIST}" "${FRONTEND_DESIGN_FILES_LIST}"

print_step() {
  echo "==> fast-gate: $1"
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

skip_step() {
  local title="$1"
  local reason="$2"
  echo "[SKIP] ${title}: ${reason}"
}

base_ref_available() {
  git rev-parse --verify "${BASE_REF}" >/dev/null 2>&1
}

json_field() {
  local dotted_path="$1"
  "${PYTHON_BIN}" - "${CLASSIFICATION_JSON}" "${dotted_path}" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
value = payload
for part in sys.argv[2].split("."):
    value = value[part]
if isinstance(value, bool):
    print("true" if value else "false")
elif isinstance(value, list):
    for item in value:
        print(item)
else:
    print(value)
PY
}

run_full_gate_fallback_if_needed() {
  local has_protected
  local has_unknown
  local has_full_gate
  local tier

  has_protected="$(json_field "classification.hasProtectedDomain")"
  has_unknown="$(json_field "classification.hasUnknown")"
  has_full_gate="$(json_field "classification.hasFullGateRisk")"
  tier="$(json_field "classification.tier")"
  echo "[INFO] Fast-gate tier classification: ${tier}"

  if [[ "${has_protected}" == "true" ]]; then
    echo "[WARN] Protected-domain files detected; escalating to ./scripts/ci_gate.sh"
    json_field "classification.protectedFiles" | sed 's/^/[WARN]   /'
    run_step "full ci_gate.sh fallback (protected-domain)" ./scripts/ci_gate.sh
    exit 0
  fi

  if [[ "${has_unknown}" == "true" ]]; then
    echo "[WARN] Unknown changed-file classification; escalating to ./scripts/ci_gate.sh"
    json_field "classification.unknownFiles" | sed 's/^/[WARN]   /'
    run_step "full ci_gate.sh fallback (unknown classification)" ./scripts/ci_gate.sh
    exit 0
  fi

  if [[ "${has_full_gate}" == "true" ]]; then
    echo "[WARN] Full-gate risk files detected; escalating to ./scripts/ci_gate.sh"
    json_field "classification.fullGateFiles" | sed 's/^/[WARN]   /'
    run_step "full ci_gate.sh fallback (full-gate risk)" ./scripts/ci_gate.sh
    exit 0
  fi
}

collect_changed_files() {
  print_step "collect changed files"

  "${PYTHON_BIN}" "${COLLECTOR}" --base-ref "${BASE_REF}" --mode branch --format lines >"${BRANCH_CHANGED}"
  "${PYTHON_BIN}" "${COLLECTOR}" --base-ref "${BASE_REF}" --mode local --format lines >"${LOCAL_CHANGED}"
  "${PYTHON_BIN}" "${COLLECTOR}" --base-ref "${BASE_REF}" --mode active --format lines >"${GATE_FILES}"
  "${PYTHON_BIN}" "${COLLECTOR}" --base-ref "${BASE_REF}" --mode active --format json >"${CLASSIFICATION_JSON}"

  cat "${BRANCH_CHANGED}" "${LOCAL_CHANGED}" >"${CHANGED_ALL}"
  sort -u "${CHANGED_ALL}" | sed '/^$/d' >"${CHANGED_SORTED}"

  local count
  local branch_count
  local local_count
  count="$(wc -l <"${CHANGED_SORTED}" | tr -d ' ')"
  branch_count="$(wc -l <"${BRANCH_CHANGED}" | tr -d ' ')"
  local_count="$(wc -l <"${LOCAL_CHANGED}" | tr -d ' ')"
  echo "[INFO] Changed files considered: ${count}"
  echo "[INFO]   ${BASE_REF}...HEAD: ${branch_count}"
  echo "[INFO]   staged/unstaged/untracked: ${local_count}"

  if [[ "${local_count}" -gt 0 ]]; then
    echo "[INFO] Active local changes detected; gating the staged/unstaged/untracked set for this iteration."
    if [[ "${branch_count}" -gt 0 ]]; then
      echo "[INFO] Branch-ahead files are detected for awareness but left to a clean-branch fast run or the full gate."
    fi
  else
    echo "[INFO] No active local changes; gating committed changes from ${BASE_REF}...HEAD."
  fi

  local gate_count
  gate_count="$(wc -l <"${GATE_FILES}" | tr -d ' ')"
  echo "[INFO] Gate files: ${gate_count}"
  if [[ "${gate_count}" == "0" ]]; then
    echo "[INFO] No files selected for this fast-gate run."
  else
    sed 's/^/[INFO]   /' "${GATE_FILES}"
  fi
}

collect_python_files() {
  while IFS= read -r file_path; do
    if [[ "${file_path}" == *.py ]]; then
      if [[ -f "${file_path}" ]]; then
        echo "${file_path}" >>"${PYTHON_FILES_LIST}"
      else
        echo "[SKIP] py_compile candidate ${file_path}: file is not present in working tree"
      fi
    fi
  done <"${GATE_FILES}"
  sort -u "${PYTHON_FILES_LIST}" -o "${PYTHON_FILES_LIST}"
}

collect_focused_tests() {
  local file_path
  local stem
  local test_count

  while IFS= read -r file_path; do
    [[ "${file_path}" == *.py ]] || continue
    [[ -f "${file_path}" ]] || continue

    if [[ "${file_path}" == tests/*.py || "${file_path}" == tests/*/*.py || "${file_path}" == tests/*/*/*.py ]]; then
      echo "${file_path}" >>"${FOCUSED_TESTS_LIST}"
      continue
    fi

    [[ -d tests ]] || continue
    stem="$(basename "${file_path}" .py)"
    find tests -type f \( \
      -name "test_${stem}.py" -o \
      -name "test_${stem}_*.py" -o \
      -name "*_${stem}.py" -o \
      -name "*${stem}*_test.py" \
    \) -print >>"${FOCUSED_TESTS_LIST}"
  done <"${GATE_FILES}"

  sort -u "${FOCUSED_TESTS_LIST}" -o "${FOCUSED_TESTS_LIST}"
  test_count="$(wc -l <"${FOCUSED_TESTS_LIST}" | tr -d ' ')"
  if [[ "${test_count}" -gt "${MAX_FOCUSED_TESTS}" ]]; then
    echo "[WARN] Found ${test_count} focused pytest candidates; limiting to ${MAX_FOCUSED_TESTS}."
    head -n "${MAX_FOCUSED_TESTS}" "${FOCUSED_TESTS_LIST}" >"${FOCUSED_TESTS_LIST}.limited"
    mv "${FOCUSED_TESTS_LIST}.limited" "${FOCUSED_TESTS_LIST}"
  fi
}

run_python_checks() {
  collect_python_files

  local python_files=()
  local file_path
  while IFS= read -r file_path; do
    python_files+=("${file_path}")
  done <"${PYTHON_FILES_LIST}"

  if [[ "${#python_files[@]}" -eq 0 ]]; then
    skip_step "python py_compile" "no changed Python files"
  else
    run_step "python py_compile (${#python_files[@]} changed files)" "${PYTHON_BIN}" -m py_compile "${python_files[@]}"
  fi

  collect_focused_tests

  local focused_tests=()
  while IFS= read -r file_path; do
    focused_tests+=("${file_path}")
  done <"${FOCUSED_TESTS_LIST}"

  if [[ "${#focused_tests[@]}" -eq 0 ]]; then
    skip_step "focused pytest" "no obvious matching tests for changed Python files"
  else
    run_step "focused pytest (${#focused_tests[@]} files)" "${PYTHON_BIN}" -m pytest -q "${focused_tests[@]}"
  fi
}

frontend_changed() {
  grep -q '^apps/dsa-web/' "${GATE_FILES}"
}

run_frontend_checks() {
  if ! frontend_changed; then
    skip_step "frontend lint/test/build" "no apps/dsa-web changes"
    return 0
  fi

  if [[ ! -f apps/dsa-web/package.json ]]; then
    echo "[FAIL] frontend lint/test/build: apps/dsa-web/package.json not found" >&2
    return 1
  fi

  print_step "frontend checks (changed-file tier)"

  run_step "frontend lint changed" env VALIDATION_BASE_REF="${BASE_REF}" npm --prefix apps/dsa-web run lint:changed

  "${PYTHON_BIN}" "${COLLECTOR}" \
    --base-ref "${BASE_REF}" \
    --mode active \
    --scope design \
    --existing \
    --relative-to apps/dsa-web \
    --format lines >"${FRONTEND_DESIGN_FILES_LIST}"

  local design_files=()
  local file_path
  while IFS= read -r file_path; do
    design_files+=("${file_path}")
  done <"${FRONTEND_DESIGN_FILES_LIST}"

  if [[ "${#design_files[@]}" -eq 0 ]]; then
    skip_step "frontend design guard changed" "no changed frontend design source files"
  else
    run_step "frontend design guard changed (${#design_files[@]} files)" \
      env VALIDATION_BASE_REF="${BASE_REF}" npm --prefix apps/dsa-web run check:design -- --files "${design_files[@]}"
  fi

  "${PYTHON_BIN}" "${COLLECTOR}" \
    --base-ref "${BASE_REF}" \
    --mode active \
    --scope frontend-related \
    --existing \
    --relative-to apps/dsa-web \
    --format lines >"${FRONTEND_RELATED_FILES_LIST}"

  local related_files=()
  while IFS= read -r file_path; do
    related_files+=("${file_path}")
  done <"${FRONTEND_RELATED_FILES_LIST}"

  if [[ "${#related_files[@]}" -eq 0 ]]; then
    skip_step "frontend related tests" "no changed frontend files for Vitest related mode"
  else
    run_step "frontend related tests (${#related_files[@]} files)" \
      env VALIDATION_BASE_REF="${BASE_REF}" npm --prefix apps/dsa-web run test:related -- "${related_files[@]}"
  fi

  run_step "frontend typecheck" env VALIDATION_BASE_REF="${BASE_REF}" npm --prefix apps/dsa-web run typecheck
  run_step "frontend quiet build" env VALIDATION_BASE_REF="${BASE_REF}" npm --prefix apps/dsa-web run build:quiet
}

docs_changed() {
  grep -Eq '(^docs/|\.md$)' "${GATE_FILES}"
}

collect_doc_text_files() {
  while IFS= read -r file_path; do
    case "${file_path}" in
      docs/*.md|docs/*/*.md|docs/*/*/*.md|*.md|docs/*.txt|docs/*/*.txt|docs/*.rst|docs/*/*.rst|docs/*.json|docs/*/*.json|docs/*.yml|docs/*/*.yml|docs/*.yaml|docs/*/*.yaml)
        if [[ -f "${file_path}" ]]; then
          echo "${file_path}" >>"${DOC_TEXT_FILES_LIST}"
        fi
        ;;
    esac
  done <"${GATE_FILES}"
  sort -u "${DOC_TEXT_FILES_LIST}" -o "${DOC_TEXT_FILES_LIST}"
}

check_doc_text_whitespace() {
  local doc_files=()
  local file_path
  while IFS= read -r file_path; do
    doc_files+=("${file_path}")
  done <"${DOC_TEXT_FILES_LIST}"

  if [[ "${#doc_files[@]}" -eq 0 ]]; then
    skip_step "doc text whitespace" "no changed text docs to scan"
    return 0
  fi

  if grep -n '[[:blank:]]$' "${doc_files[@]}"; then
    echo "[FAIL] doc text whitespace: trailing whitespace found" >&2
    return 1
  fi
}

run_docs_checks() {
  if ! docs_changed; then
    skip_step "docs diff/check" "no docs or markdown changes"
    return 0
  fi

  if base_ref_available; then
    run_step "docs diff whitespace (${BASE_REF}...HEAD)" git diff --check "${BASE_REF}...HEAD" -- docs '*.md'
  else
    skip_step "docs diff whitespace (${BASE_REF}...HEAD)" "${BASE_REF} is not available"
  fi
  run_step "docs diff whitespace (staged)" git diff --cached --check -- docs '*.md'
  run_step "docs diff whitespace (working tree)" git diff --check -- docs '*.md'

  collect_doc_text_files
  run_step "doc text whitespace (changed text docs)" check_doc_text_whitespace
}

print_step "preflight"
echo "[INFO] Root: ${ROOT_DIR}"
echo "[INFO] Base ref: ${BASE_REF}"
echo "[INFO] Python: ${PYTHON_BIN}"
echo "[INFO] This fast gate is for iteration only. Run ./scripts/ci_gate.sh before final push or release."

collect_changed_files
run_full_gate_fallback_if_needed
run_python_checks
run_frontend_checks
run_docs_checks

print_step "summary"
echo "[PASS] fast-gate completed. It does not replace ./scripts/ci_gate.sh."
