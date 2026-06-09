#!/usr/bin/env bash

set -euo pipefail
shopt -s nocasematch

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BASE_REF="${RELEASE_SECRET_SCAN_BASE_REF:-origin/main}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
LOCAL_ONLY=0
FILES_FROM=""

cd "${ROOT_DIR}"

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/release_secret_scan.XXXXXX")"
trap 'rm -rf "${TMP_DIR}"' EXIT

BRANCH_FILES="${TMP_DIR}/branch_files.txt"
STAGED_FILES="${TMP_DIR}/staged_files.txt"
WORKTREE_FILES="${TMP_DIR}/worktree_files.txt"
UNTRACKED_FILES="${TMP_DIR}/untracked_files.txt"
FINDINGS="${TMP_DIR}/findings.txt"
FILES_FROM_LIST="${TMP_DIR}/files_from.txt"

touch "${BRANCH_FILES}" "${STAGED_FILES}" "${WORKTREE_FILES}" "${UNTRACKED_FILES}" "${FINDINGS}" "${FILES_FROM_LIST}"

usage() {
  cat <<'EOF'
Usage: scripts/release_secret_scan.sh [--local-only] [--files-from PATH] [--base-ref REF]

Conservative release secret scan. By default, scans committed branch changes from
the release base ref plus staged, unstaged, and untracked text files. Findings are
redacted; inspect the reported file and line locally.

Options:
  --local-only       Scan only staged, unstaged, and untracked files.
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

scan_line() {
  local source_label="$1"
  local file_path="$2"
  local line_no="$3"
  local line="$4"
  local trimmed_line
  trimmed_line="$(trim_value "${line}")"

  [[ -z "${trimmed_line}" ]] && return 0
  [[ "${trimmed_line}" == \#* || "${trimmed_line}" == //* ]] && return 0

  if [[ "${line}" =~ BEGIN[[:space:]]+(RSA[[:space:]]+|DSA[[:space:]]+|EC[[:space:]]+|OPENSSH[[:space:]]+|PGP[[:space:]]+)?PRIVATE[[:space:]]+KEY ]]; then
    record_finding "${source_label}" "${file_path}" "${line_no}" "private key material"
    return 0
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

  if [[ "${line}" =~ (^|[^A-Za-z0-9_.-])([A-Za-z0-9_.-]*(api[_-]?key|token|secret|password|passwd|credential|credentials|client[_-]?secret|access[_-]?key|secret[_-]?key|private[_-]?key|session[_-]?token|bearer)[A-Za-z0-9_.-]*)[[:space:]]*[:=][[:space:]]*([^[:space:]#][^#]*) ]]; then
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

  if [[ -n "${FILES_FROM}" ]]; then
    local file_path
    while IFS= read -r file_path; do
      [[ -n "${file_path}" ]] || continue
      [[ -f "${file_path}" ]] || continue
      scan_file_content "files-from" "${file_path}" "${file_path}"
    done <"${FILES_FROM_LIST}"
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
}

print_step "preflight"
echo "[INFO] Root: ${ROOT_DIR}"
echo "[INFO] Base ref: ${BASE_REF}"
if [[ "${LOCAL_ONLY}" -eq 1 ]]; then
  echo "[INFO] Mode: local-only"
elif [[ -n "${FILES_FROM}" ]]; then
  echo "[INFO] Mode: files-from"
else
  echo "[INFO] Mode: release default"
fi
echo "[INFO] This is a lightweight release smoke check, not a full enterprise DLP scanner."
echo "[INFO] Findings are redacted; inspect the reported file and line locally."

collect_changed_files
scan_changed_files

if [[ -s "${FINDINGS}" ]]; then
  print_step "findings"
  sort -u "${FINDINGS}"
  echo "[FAIL] High-confidence secret patterns were found in changed files." >&2
  exit 1
fi

print_step "summary"
echo "[PASS] No high-confidence secret patterns found in changed text files."
