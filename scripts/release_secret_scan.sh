#!/usr/bin/env bash

set -euo pipefail
shopt -s nocasematch

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BASE_REF="${RELEASE_SECRET_SCAN_BASE_REF:-origin/main}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
LOCAL_ONLY=0
FILES_FROM=""
CANDIDATE_REF=""
EVIDENCE_PATH=""
EVIDENCE_ROOTS=()
SCANNED_COUNT=0
PRIVATE_PATH_FINDINGS=0

cd "${ROOT_DIR}"

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/release_secret_scan.XXXXXX")"
trap 'rm -rf "${TMP_DIR}"' EXIT

BRANCH_FILES="${TMP_DIR}/branch_files.txt"
STAGED_FILES="${TMP_DIR}/staged_files.txt"
WORKTREE_FILES="${TMP_DIR}/worktree_files.txt"
UNTRACKED_FILES="${TMP_DIR}/untracked_files.txt"
FINDINGS="${TMP_DIR}/findings.txt"
FILES_FROM_LIST="${TMP_DIR}/files_from.txt"
CANDIDATE_FILES="${TMP_DIR}/candidate_files.txt"
CANDIDATE_TREE="${TMP_DIR}/candidate-tree"
CANDIDATE_SUMMARY="${TMP_DIR}/candidate-summary.json"

touch "${BRANCH_FILES}" "${STAGED_FILES}" "${WORKTREE_FILES}" "${UNTRACKED_FILES}" "${FINDINGS}" "${FILES_FROM_LIST}" "${CANDIDATE_FILES}"

usage() {
  cat <<'EOF'
Usage: scripts/release_secret_scan.sh [--candidate-ref REF] [--evidence-root PATH]... [--evidence PATH]
       scripts/release_secret_scan.sh [--local-only] [--files-from PATH] [--base-ref REF]

Conservative release secret scan. By default, scans committed branch changes from
the release base ref plus staged, unstaged, and untracked text files. Findings are
redacted; inspect the reported file and line locally.

Options:
  --local-only       Scan only staged, unstaged, and untracked files.
  --candidate-ref REF
                     Scan every eligible tracked text file in the exact commit.
                     This is the required release mode and ignores untracked files.
  --evidence PATH    Write sanitized JSON evidence with commit and file count.
  --evidence-root PATH
                     Recursively scan one generated candidate/evidence tree,
                     including nested tar/gzip/OCI members. May be repeated.
  --files-from PATH  Scan only newline-delimited paths from PATH ("-" for stdin).
                     Paths are still filtered to skip generated/static/binary,
                     build, cache, dependency, and other non-source artifacts.
  --base-ref REF     Override RELEASE_SECRET_SCAN_BASE_REF/origin/main.
  -h, --help         Show this help text.
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --local-only)
      LOCAL_ONLY=1
      shift
      ;;
    --candidate-ref)
      if [[ "$#" -lt 2 ]]; then
        echo "[FAIL] --candidate-ref requires a ref" >&2
        exit 2
      fi
      CANDIDATE_REF="$2"
      shift 2
      ;;
    --evidence)
      if [[ "$#" -lt 2 ]]; then
        echo "[FAIL] --evidence requires a path" >&2
        exit 2
      fi
      EVIDENCE_PATH="$2"
      shift 2
      ;;
    --evidence-root)
      if [[ "$#" -lt 2 ]]; then
        echo "[FAIL] --evidence-root requires a path" >&2
        exit 2
      fi
      EVIDENCE_ROOTS+=("$2")
      shift 2
      ;;
    --files-from)
      if [[ "$#" -lt 2 ]]; then
        echo "[FAIL] --files-from requires a path" >&2
        exit 2
      fi
      FILES_FROM="$2"
      shift 2
      ;;
    --base-ref)
      if [[ "$#" -lt 2 ]]; then
        echo "[FAIL] --base-ref requires a ref" >&2
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
      echo "[FAIL] unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -n "${CANDIDATE_REF}" && ( "${LOCAL_ONLY}" -eq 1 || -n "${FILES_FROM}" ) ]]; then
  echo "[FAIL] --candidate-ref cannot be combined with --local-only or --files-from" >&2
  exit 2
fi

print_step() {
  echo "==> release-secret-scan: $1"
}

base_ref_available() {
  git rev-parse --verify "${BASE_REF}" >/dev/null 2>&1
}

collect_files() {
  "${PYTHON_BIN}" "${ROOT_DIR}/scripts/validation_changed_files.py" \
    --base-ref "${BASE_REF}" \
    --scope secret \
    --format lines \
    "$@"
}

skip_path() {
  local path="$1"

  case "${path}" in
    .git/*|*/.git/*|node_modules/*|*/node_modules/*|vendor/*|*/vendor/*|.venv/*|*/.venv/*|venv/*|*/venv/*)
      return 0
      ;;
    .cache/*|*/.cache/*|.pytest_cache/*|*/.pytest_cache/*|__pycache__/*|*/__pycache__/*)
      return 0
      ;;
    dist/*|*/dist/*|build/*|*/build/*|coverage/*|*/coverage/*|htmlcov/*|*/htmlcov/*)
      return 0
      ;;
    *.png|*.jpg|*.jpeg|*.gif|*.webp|*.ico|*.pdf|*.zip|*.gz|*.tgz|*.bz2|*.xz|*.7z|*.tar|*.db|*.sqlite|*.sqlite3|*.duckdb|*.parquet|*.pkl|*.pyc|*.woff|*.woff2|*.ttf|*.otf|*.mp4|*.mov)
      return 0
      ;;
  esac

  return 1
}

is_text_file() {
  local file_path="$1"
  [[ -f "${file_path}" ]] || return 1
  grep -Iq . "${file_path}" 2>/dev/null
}

normalize_value() {
  local value="$1"

  value="${value%%#*}"
  value="${value%,}"
  value="${value%;}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  printf '%s' "${value}"
}

trim_value() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "${value}"
}

is_safe_placeholder_value() {
  local value
  value="$(normalize_value "$1")"
  local lower
  lower="$(printf '%s' "${value}" | tr '[:upper:]' '[:lower:]')"
  local github_expression_re='^\$\{\{[[:space:]]*(github|secrets|inputs|needs|steps|env|vars)\.[A-Za-z_][A-Za-z0-9_.-]*[[:space:]]*\}\}$'

  [[ -z "${value}" ]] && return 0
  [[ "${lower}" == "none" || "${lower}" == "null" || "${lower}" == "nil" ]] && return 0
  [[ "${lower}" == "true" || "${lower}" == "false" ]] && return 0
  [[ "${lower}" == "changeme" || "${lower}" == "change_me" || "${lower}" == "change-me" ]] && return 0
  [[ "${lower}" == "placeholder" || "${lower}" == "todo" || "${lower}" == "tbd" ]] && return 0
  [[ "${lower}" == "example" || "${lower}" == "sample" || "${lower}" == "dummy" || "${lower}" == "mock" || "${lower}" == "fake" ]] && return 0
  [[ "${lower}" == "x" || "${lower}" == "xx" || "${lower}" == "xxx" ]] && return 0
  [[ "${lower}" == *"your_"* || "${lower}" == *"your-"* || "${lower}" == *"your "* ]] && return 0
  [[ "${lower}" == *"example"* || "${lower}" == *"sample"* || "${lower}" == *"dummy"* || "${lower}" == *"mock"* || "${lower}" == *"fake"* ]] && return 0
  [[ "${lower}" == *"unit-test"* || "${lower}" == *"test-only"* || "${lower}" == *"not-a-real"* ]] && return 0
  [[ "${lower}" == *"redacted"* || "${lower}" == *"masked"* || "${lower}" == "<"*">" ]] && return 0
  [[ "${value}" =~ ^[$][{]?[A-Za-z_][A-Za-z0-9_]*[}]?$ ]] && return 0
  [[ "${value}" =~ ${github_expression_re} ]] && return 0
  [[ "${value}" =~ ^[*xX_./-]{4,}$ ]] && return 0

  return 1
}

is_scannable_assignment_value() {
  local file_path="$1"
  local raw_value
  raw_value="$(trim_value "$2")"

  [[ -z "${raw_value}" ]] && return 1
  [[ "${raw_value}" == *" + "* ]] && return 1
  [[ "${raw_value}" == *"("* || "${raw_value}" == *")"* ]] && return 1

  case "${file_path}" in
    tests/*|*/tests/*)
      return 1
      ;;
  esac

  case "${file_path}" in
    *.md|*.rst|*.txt)
      return 1
      ;;
  esac

  case "${file_path}" in
    *.env|*.env.*|.env|.env.*|*.example|*.example.*|*.json|*.yml|*.yaml|*.toml|*.ini|*.properties)
      return 0
      ;;
  esac

  [[ "${raw_value}" == \"* || "${raw_value}" == \'* ]] && return 0

  case "${file_path}" in
    *.py|*.pyi|*.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs)
      return 1
      ;;
  esac

  return 0
}

looks_secret_like() {
  local value
  value="$(normalize_value "$1")"

  [[ "${#value}" -ge 16 ]] || return 1
  [[ "${value}" =~ [A-Za-z] ]] || return 1
  [[ "${value}" =~ [0-9+/=_\.-] ]] || return 1

  return 0
}

is_provider_key_name() {
  local key
  key="$(printf '%s' "$1" | tr '[:lower:]' '[:upper:]')"

  [[ "${key}" =~ (OPENAI|ANTHROPIC|GEMINI|GOOGLE|DEEPSEEK|ZHIPU|TUSHARE|TICKFLOW|ALPACA|TRADIER|POLYGON|FMP|FINNHUB|ALPHA([_-]?VANTAGE)?|TWELVE([_-]?DATA)?|FRED|GNEWS|TAVILY|SERPAPI|BRAVE|DISCORD|TELEGRAM|SLACK|FEISHU|LARK|WECHAT|PUSHOVER|PUSHPLUS|IBKR|FUTU|LITELLM) ]]
}

is_secret_state_indicator_key() {
  local key
  key="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"

  [[ "${key}" =~ (^|[._-])(password|passwd|credential|credentials|token|secret|session)[._-](state|status)$ ]] && return 0
  [[ "${key}" =~ (^|[._-])(password|passwd|credential|credentials|token|secret|session)[._-]present$ ]] && return 0
  [[ "${key}" =~ (^|[._-])has[._-](password|passwd|credential|credentials|token|secret|session)$ ]] && return 0

  return 1
}

record_finding() {
  local source_label="$1"
  local file_path="$2"
  local line_no="$3"
  local rule="$4"

  printf '[FAIL] %s:%s [%s] %s\n' "${file_path}" "${line_no}" "${source_label}" "${rule}" >>"${FINDINGS}"
}

private_path_scan_applies() {
  local file_path="$1"
  case "${file_path}" in
    tests/*|*/tests/*|*/__tests__/*|*.test.*|*.spec.*)
      return 1
      ;;
    main.py|server.py|api/*|src/*|data_provider/*|bot/*|apps/dsa-web/src/*|apps/dsa-desktop/src/*|docker/*|.github/workflows/*)
      return 0
      ;;
  esac
  return 1
}

is_reviewed_topology_test_id() {
  local file_path="$1"
  local trimmed_line="$2"

  [[ "${file_path}" == "validation/domain_test_topology.json" ]] || return 1
  [[ "${trimmed_line}" =~ ^\"id\"[[:space:]]*:[[:space:]]*\" ]] && return 0
  [[ "${trimmed_line}" =~ ^\"tests/.*\",?$ ]] && return 0
  return 1
}

scan_line() {
  local source_label="$1"
  local file_path="$2"
  local line_no="$3"
  local line="$4"
  local trimmed_line
  trimmed_line="$(trim_value "${line}")"

  [[ -z "${trimmed_line}" ]] && return 0
  [[ "${trimmed_line}" == \#* || "${trimmed_line}" == //* ]] && return 0
  is_reviewed_topology_test_id "${file_path}" "${trimmed_line}" && return 0

  if [[ "${line}" =~ BEGIN[[:space:]]+(RSA[[:space:]]+|DSA[[:space:]]+|EC[[:space:]]+|OPENSSH[[:space:]]+|PGP[[:space:]]+)?PRIVATE[[:space:]]+KEY ]]; then
    record_finding "${source_label}" "${file_path}" "${line_no}" "private key material"
    return 0
  fi

  if private_path_scan_applies "${file_path}" && [[ "${line}" =~ /Users/[^/[:space:]\"\']+|/home/[^/[:space:]\"\']+|[A-Za-z]:\\Users\\[^\\[:space:]\"\']+ ]]; then
    record_finding "${source_label}" "${file_path}" "${line_no}" "private absolute path"
    PRIVATE_PATH_FINDINGS=$((PRIVATE_PATH_FINDINGS + 1))
  fi

  if [[ "${line}" =~ (^|[^A-Za-z0-9_])(AKIA|ASIA)[0-9A-Z]{16}([^A-Za-z0-9_]|$) ]]; then
    record_finding "${source_label}" "${file_path}" "${line_no}" "AWS access key id"
  fi

  if [[ "${line}" =~ (^|[^A-Za-z0-9_])sk-[A-Za-z0-9_-]{24,}([^A-Za-z0-9_]|$) ]]; then
    record_finding "${source_label}" "${file_path}" "${line_no}" "OpenAI-style API key"
  fi

  if [[ "${line}" =~ (^|[^A-Za-z0-9_])gh[pousr]_[A-Za-z0-9_]{24,}([^A-Za-z0-9_]|$) ]]; then
    record_finding "${source_label}" "${file_path}" "${line_no}" "GitHub token"
  fi

  if [[ "${line}" =~ (^|[^A-Za-z0-9_])xox[baprs]-[A-Za-z0-9-]{20,}([^A-Za-z0-9_]|$) ]]; then
    record_finding "${source_label}" "${file_path}" "${line_no}" "Slack token"
  fi

  if [[ "${line}" =~ (^|[^A-Za-z0-9_])AIza[0-9A-Za-z_-]{30,}([^A-Za-z0-9_]|$) ]]; then
    record_finding "${source_label}" "${file_path}" "${line_no}" "Google API key"
  fi

  if [[ "${line}" =~ [Bb]earer[[:space:]]+([A-Za-z0-9._~+/=-]{20,}) ]]; then
    if ! is_safe_placeholder_value "${BASH_REMATCH[1]}"; then
      record_finding "${source_label}" "${file_path}" "${line_no}" "bearer token"
    fi
  fi

  if [[ "${line}" =~ (^|[^A-Za-z0-9_.-])\"?([A-Za-z0-9_.-]*(api[_-]?key|token|secret|password|passwd|credential|credentials|client[_-]?secret|access[_-]?key|secret[_-]?key|private[_-]?key|session[_-]?token|bearer)[A-Za-z0-9_.-]*)\"?[[:space:]]*[:=][[:space:]]*([^[:space:]#][^#]*) ]]; then
    local key="${BASH_REMATCH[2]}"
    local value="${BASH_REMATCH[4]}"
    local lower_key
    lower_key="$(printf '%s' "${key}" | tr '[:upper:]' '[:lower:]')"

    if is_secret_state_indicator_key "${key}"; then
      return 0
    fi

    if ! is_scannable_assignment_value "${file_path}" "${value}"; then
      return 0
    fi

    if is_safe_placeholder_value "${value}"; then
      return 0
    fi

    if [[ "${lower_key}" =~ (password|passwd) ]]; then
      record_finding "${source_label}" "${file_path}" "${line_no}" "non-empty password assignment"
    elif is_provider_key_name "${key}"; then
      record_finding "${source_label}" "${file_path}" "${line_no}" "provider credential assignment"
    elif looks_secret_like "${value}"; then
      record_finding "${source_label}" "${file_path}" "${line_no}" "secret-like credential assignment"
    fi
  fi
}

scan_file_content() {
  local source_label="$1"
  local file_path="$2"
  local content_path="$3"

  if skip_path "${file_path}"; then
    return 0
  fi
  if ! is_text_file "${content_path}"; then
    return 0
  fi

  SCANNED_COUNT=$((SCANNED_COUNT + 1))

  local line_no=0
  local line
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line_no=$((line_no + 1))
    scan_line "${source_label}" "${file_path}" "${line_no}" "${line}"
  done <"${content_path}"
}

scan_git_blob() {
  local source_label="$1"
  local object_ref="$2"
  local file_path="$3"
  local content_path="${TMP_DIR}/blob.$(printf '%s' "${source_label}.${file_path}" | shasum | awk '{print $1}')"

  if skip_path "${file_path}"; then
    return 0
  fi
  if [[ -z "${object_ref}" ]]; then
    if git show ":${file_path}" >"${content_path}" 2>/dev/null; then
      scan_file_content "${source_label}" "${file_path}" "${content_path}"
    fi
    return 0
  fi
  if git cat-file -e "${object_ref}:${file_path}" 2>/dev/null; then
    git show "${object_ref}:${file_path}" >"${content_path}"
    scan_file_content "${source_label}" "${file_path}" "${content_path}"
  fi
}

collect_changed_files() {
  print_step "collect changed files"

  if [[ -n "${CANDIDATE_REF}" ]]; then
    local candidate_commit
    if ! candidate_commit="$(git rev-parse --verify "${CANDIDATE_REF}^{commit}" 2>/dev/null)"; then
      echo "[FAIL] Candidate ref is not an available commit: ${CANDIDATE_REF}" >&2
      exit 1
    fi
    git ls-tree -r --name-only "${candidate_commit}" >"${CANDIDATE_FILES}"
    mkdir -p "${CANDIDATE_TREE}"
    git archive "${candidate_commit}" | tar -xf - -C "${CANDIDATE_TREE}"
    CANDIDATE_REF="${candidate_commit}"
    echo "[INFO] Included tracked candidate tree at ${CANDIDATE_REF}"
    echo "[INFO]   candidate tracked files: $(wc -l <"${CANDIDATE_FILES}" | tr -d ' ')"
    return 0
  fi

  if [[ -n "${FILES_FROM}" ]]; then
    collect_files --files-from "${FILES_FROM}" --existing >"${FILES_FROM_LIST}"
    echo "[INFO] Included explicit files from ${FILES_FROM}"
    echo "[INFO]   files-from: $(wc -l <"${FILES_FROM_LIST}" | tr -d ' ')"
    return 0
  fi

  if [[ "${LOCAL_ONLY}" -eq 0 ]]; then
    if base_ref_available; then
      collect_files --mode branch-release >"${BRANCH_FILES}"
      echo "[INFO] Included committed changes from ${BASE_REF}..HEAD"
    else
      echo "[WARN] ${BASE_REF} is not available; committed-change scan skipped" >&2
    fi
  else
    echo "[INFO] --local-only enabled; committed branch changes are not scanned in this run"
  fi

  collect_files --mode staged >"${STAGED_FILES}"
  collect_files --mode worktree >"${WORKTREE_FILES}"
  collect_files --mode untracked >"${UNTRACKED_FILES}"

  echo "[INFO]   ${BASE_REF}..HEAD: $(wc -l <"${BRANCH_FILES}" | tr -d ' ')"
  echo "[INFO]   staged: $(wc -l <"${STAGED_FILES}" | tr -d ' ')"
  echo "[INFO]   working tree: $(wc -l <"${WORKTREE_FILES}" | tr -d ' ')"
  echo "[INFO]   untracked: $(wc -l <"${UNTRACKED_FILES}" | tr -d ' ')"
}

scan_changed_files() {
  print_step "scan changed text files"

  if [[ -n "${CANDIDATE_REF}" ]]; then
    "${PYTHON_BIN}" "${ROOT_DIR}/scripts/release_secret_scan_candidate.py" \
      --root "${CANDIDATE_TREE}" \
      --files "${CANDIDATE_FILES}" \
      --findings "${FINDINGS}" \
      --summary "${CANDIDATE_SUMMARY}"
    read -r SCANNED_COUNT PRIVATE_PATH_FINDINGS < <(
      "${PYTHON_BIN}" - "${CANDIDATE_SUMMARY}" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
print(payload["fileCount"], payload["privatePathFindings"])
PY
    )
    scan_evidence_roots
    return 0
  fi

  if [[ -n "${FILES_FROM}" ]]; then
    local file_path
    while IFS= read -r file_path; do
      [[ -n "${file_path}" ]] || continue
      [[ -f "${file_path}" ]] || continue
      scan_file_content "files-from" "${file_path}" "${file_path}"
    done <"${FILES_FROM_LIST}"
    scan_evidence_roots
    return 0
  fi

  local file_path
  while IFS= read -r file_path; do
    [[ -n "${file_path}" ]] || continue
    scan_git_blob "HEAD" "HEAD" "${file_path}"
  done <"${BRANCH_FILES}"

  while IFS= read -r file_path; do
    [[ -n "${file_path}" ]] || continue
    scan_git_blob "staged" "" "${file_path}"
  done <"${STAGED_FILES}"

  while IFS= read -r file_path; do
    [[ -n "${file_path}" ]] || continue
    [[ -f "${file_path}" ]] || continue
    scan_file_content "working-tree" "${file_path}" "${file_path}"
  done <"${WORKTREE_FILES}"

  while IFS= read -r file_path; do
    [[ -n "${file_path}" ]] || continue
    [[ -f "${file_path}" ]] || continue
    scan_file_content "untracked" "${file_path}" "${file_path}"
  done <"${UNTRACKED_FILES}"
  scan_evidence_roots
}

scan_evidence_roots() {
  if [[ "${#EVIDENCE_ROOTS[@]}" -eq 0 ]]; then
    return 0
  fi
  local index=0
  local root
  for root in "${EVIDENCE_ROOTS[@]}"; do
    index=$((index + 1))
    local extra_findings="${TMP_DIR}/evidence-findings-${index}.txt"
    local extra_summary="${TMP_DIR}/evidence-summary-${index}.json"
    : >"${extra_findings}"
    "${PYTHON_BIN}" "${ROOT_DIR}/scripts/release_secret_scan_candidate.py" \
      --root "${root}" \
      --scan-tree \
      --findings "${extra_findings}" \
      --summary "${extra_summary}"
    cat "${extra_findings}" >>"${FINDINGS}"
    local extra_count
    local extra_private
    read -r extra_count extra_private < <(
      "${PYTHON_BIN}" - "${extra_summary}" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
print(payload["fileCount"], payload["privatePathFindings"])
PY
    )
    SCANNED_COUNT=$((SCANNED_COUNT + extra_count))
    PRIVATE_PATH_FINDINGS=$((PRIVATE_PATH_FINDINGS + extra_private))
  done
}

write_evidence() {
  local status="$1"
  [[ -n "${EVIDENCE_PATH}" ]] || return 0
  local scanned_commit
  scanned_commit="${CANDIDATE_REF:-$(git rev-parse HEAD 2>/dev/null || true)}"
  local scan_mode="local"
  [[ -n "${CANDIDATE_REF}" ]] && scan_mode="candidate"
  "${PYTHON_BIN}" - "${EVIDENCE_PATH}" "${status}" "${scanned_commit}" "${SCANNED_COUNT}" "${PRIVATE_PATH_FINDINGS}" "${scan_mode}" <<'PY'
import json
import sys
from pathlib import Path

path, status, commit, file_count, private_findings, mode = sys.argv[1:7]
payload = {
    "schemaVersion": "wolfystock_release_secret_scan_v1",
    "mode": mode,
    "status": status,
    "scannedCommit": commit or None,
    "fileCount": int(file_count),
    "privatePathScan": "PASS" if int(private_findings) == 0 else "FAIL",
}
output = Path(path)
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

print_step "preflight"
echo "[INFO] Root: ${ROOT_DIR}"
echo "[INFO] Base ref: ${BASE_REF}"
if [[ "${LOCAL_ONLY}" -eq 1 ]]; then
  echo "[INFO] Mode: local-only"
elif [[ -n "${CANDIDATE_REF}" ]]; then
  echo "[INFO] Mode: candidate"
elif [[ -n "${FILES_FROM}" ]]; then
  echo "[INFO] Mode: files-from"
else
  echo "[INFO] Mode: release default"
fi
echo "[INFO] This is a lightweight release smoke check, not a full enterprise DLP scanner."
echo "[INFO] Findings are redacted; inspect the reported file and line locally."

collect_changed_files
scan_changed_files

echo "[INFO] Scanned text files: ${SCANNED_COUNT}"

if [[ "${SCANNED_COUNT}" -eq 0 ]]; then
  write_evidence "FAIL"
  echo "[FAIL] Secret scan selected zero files." >&2
  exit 1
fi

if [[ -s "${FINDINGS}" ]]; then
  print_step "findings"
  sort -u "${FINDINGS}"
  write_evidence "FAIL"
  echo "[FAIL] High-confidence secret patterns were found in changed files." >&2
  exit 1
fi

print_step "summary"
write_evidence "PASS"
echo "[PASS] No high-confidence secret patterns found in changed text files."
