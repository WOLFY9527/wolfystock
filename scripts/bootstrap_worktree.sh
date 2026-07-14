#!/usr/bin/env bash

set -euo pipefail

MODE=""
ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || true)"

usage() {
  cat <<'EOF'
Usage: bash scripts/bootstrap_worktree.sh --check|--apply

Share the canonical main worktree's development dependencies with this linked
worktree. The script only validates or creates symlinks; it never installs,
upgrades, copies, or removes dependencies.

Links managed by this script:
  - .venv
  - apps/dsa-web/node_modules
  - .env, only when WORKTREE_BOOTSTRAP_ENV_FILE names an absolute, repo-external file

For dependency or lockfile changes, use an isolated environment instead:
  WORKTREE_BOOTSTRAP_ISOLATED=1 bash scripts/bootstrap_worktree.sh --check
EOF
}

fail() {
  printf '[bootstrap-worktree] %s\n' "$1" >&2
  exit 1
}

resolve_existing_path() {
  local path="$1"
  local parent=""
  local target=""

  [[ -e "${path}" || -L "${path}" ]] || return 1
  parent="$(cd -P "$(dirname "${path}")" && pwd)" || return 1
  path="${parent}/$(basename "${path}")"

  while [[ -L "${path}" ]]; do
    target="$(readlink "${path}")"
    if [[ "${target}" == /* ]]; then
      path="${target}"
    else
      path="$(dirname "${path}")/${target}"
    fi
    parent="$(cd -P "$(dirname "${path}")" && pwd)" || return 1
    path="${parent}/$(basename "${path}")"
  done

  printf '%s\n' "${path}"
}

paths_match() {
  local destination="$1"
  local source="$2"
  local resolved_destination=""
  local resolved_source=""

  resolved_destination="$(resolve_existing_path "${destination}")" || return 1
  resolved_source="$(resolve_existing_path "${source}")" || return 1
  [[ "${resolved_destination}" == "${resolved_source}" ]]
}

path_is_within() {
  local path="$1"
  local root="$2"

  [[ "${path}" == "${root}" || "${path}" == "${root}"/* ]]
}

register_link() {
  LINK_LABELS+=("$1")
  LINK_DESTINATIONS+=("$2")
  LINK_SOURCES+=("$3")
  LINK_KINDS+=("$4")
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check|--apply)
      [[ -z "${MODE}" ]] || fail "Specify exactly one of --check or --apply."
      MODE="$1"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

[[ -n "${MODE}" ]] || fail "Specify --check or --apply."

if [[ "${WORKTREE_BOOTSTRAP_ISOLATED:-}" == "1" ]]; then
  printf '[bootstrap-worktree] isolated environment requested; skipped shared links. Use this for dependency or lockfile changes.\n'
  exit 0
fi

[[ -n "${ROOT_DIR}" ]] || fail "Unable to locate the current Git worktree."
ROOT_DIR="$(resolve_existing_path "${ROOT_DIR}")" || fail "Unable to resolve the current Git worktree."

GIT_COMMON_DIR="$(git -C "${ROOT_DIR}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
[[ -n "${GIT_COMMON_DIR}" && "${GIT_COMMON_DIR}" == /* ]] || fail "Unable to resolve the shared Git metadata directory."
GIT_COMMON_DIR="$(resolve_existing_path "${GIT_COMMON_DIR}")" || fail "Unable to resolve the shared Git metadata directory."
INFO_EXCLUDE="${GIT_COMMON_DIR}/info/exclude"

CANONICAL_ROOT="$(git --git-dir="${GIT_COMMON_DIR}" worktree list --porcelain | awk '/^worktree / { sub(/^worktree /, ""); print; exit }')"
[[ -n "${CANONICAL_ROOT}" ]] || fail "Unable to locate the canonical main worktree from Git shared metadata."
CANONICAL_ROOT="$(resolve_existing_path "${CANONICAL_ROOT}")" || fail "Canonical main worktree reported by Git is missing."

[[ "${ROOT_DIR}" != "${CANONICAL_ROOT}" ]] || fail "Run this bootstrap from a linked worktree, not the canonical main worktree."

declare -a LINK_LABELS=()
declare -a LINK_DESTINATIONS=()
declare -a LINK_SOURCES=()
declare -a LINK_KINDS=()

register_link ".venv" "${ROOT_DIR}/.venv" "${CANONICAL_ROOT}/.venv" "directory"
register_link \
  "apps/dsa-web/node_modules" \
  "${ROOT_DIR}/apps/dsa-web/node_modules" \
  "${CANONICAL_ROOT}/apps/dsa-web/node_modules" \
  "directory"

if grep -Fqx '/.venv' "${INFO_EXCLUDE}" 2>/dev/null; then
  VENV_EXCLUDE_MISSING=0
else
  VENV_EXCLUDE_MISSING=1
fi

if [[ "${VENV_EXCLUDE_MISSING}" == "1" ]]; then
  if git -C "${CANONICAL_ROOT}" check-ignore -q --no-index -- .venv; then
    VENV_NEEDS_EXCLUDE=0
  else
    VENV_NEEDS_EXCLUDE=1
  fi
  if [[ "${MODE}" == "--check" && "${VENV_NEEDS_EXCLUDE}" == "1" ]]; then
    printf '[bootstrap-worktree] would add /.venv to shared Git info/exclude.\n'
  elif [[ "${MODE}" == "--apply" ]]; then
    mkdir -p "$(dirname "${INFO_EXCLUDE}")"
    if [[ -s "${INFO_EXCLUDE}" && "$(tail -c 1 "${INFO_EXCLUDE}")" != $'\n' ]]; then
      printf '\n' >>"${INFO_EXCLUDE}"
    fi
    printf '/.venv\n' >>"${INFO_EXCLUDE}"
    printf '[bootstrap-worktree] added /.venv to shared Git info/exclude.\n'
  fi
fi

if [[ -n "${WORKTREE_BOOTSTRAP_ENV_FILE:-}" ]]; then
  [[ "${WORKTREE_BOOTSTRAP_ENV_FILE}" == /* ]] || fail "WORKTREE_BOOTSTRAP_ENV_FILE must be an absolute repo-external file path."
  ENV_FILE_SOURCE="$(resolve_existing_path "${WORKTREE_BOOTSTRAP_ENV_FILE}")" || fail "Configured repo-external env file is missing."
  [[ -f "${ENV_FILE_SOURCE}" ]] || fail "Configured repo-external env file is not a regular file."
  if path_is_within "${ENV_FILE_SOURCE}" "${ROOT_DIR}" || path_is_within "${ENV_FILE_SOURCE}" "${CANONICAL_ROOT}"; then
    fail "WORKTREE_BOOTSTRAP_ENV_FILE must point outside both repository worktrees."
  fi
  register_link ".env" "${ROOT_DIR}/.env" "${ENV_FILE_SOURCE}" "file"
fi

for index in "${!LINK_SOURCES[@]}"; do
  source_path="${LINK_SOURCES[${index}]}"
  source_kind="${LINK_KINDS[${index}]}"
  if [[ "${source_kind}" == "directory" && ! -d "${source_path}" ]]; then
    fail "Canonical target is missing for ${LINK_LABELS[${index}]}. Install it in the canonical main worktree, or use WORKTREE_BOOTSTRAP_ISOLATED=1 for dependency or lockfile changes."
  fi
  if [[ "${source_kind}" == "file" && ! -f "${source_path}" ]]; then
    fail "Configured repo-external env file is missing."
  fi
done

for index in "${!LINK_DESTINATIONS[@]}"; do
  destination="${LINK_DESTINATIONS[${index}]}"
  source_path="${LINK_SOURCES[${index}]}"
  label="${LINK_LABELS[${index}]}"
  if [[ -L "${destination}" ]]; then
    paths_match "${destination}" "${source_path}" || fail "Refusing to replace ${label}: symlink points somewhere else."
  elif [[ -e "${destination}" ]]; then
    fail "Refusing to replace ${label}: destination is an existing real file or directory."
  fi
done

for index in "${!LINK_DESTINATIONS[@]}"; do
  destination="${LINK_DESTINATIONS[${index}]}"
  source_path="${LINK_SOURCES[${index}]}"
  label="${LINK_LABELS[${index}]}"
  if [[ -L "${destination}" ]]; then
    printf '[bootstrap-worktree] %s already linked.\n' "${label}"
  elif [[ "${MODE}" == "--check" ]]; then
    printf '[bootstrap-worktree] would link %s.\n' "${label}"
  else
    [[ -d "$(dirname "${destination}")" ]] || fail "Parent directory is missing for ${label}; refusing to create non-link paths."
    ln -s "${source_path}" "${destination}"
    printf '[bootstrap-worktree] linked %s.\n' "${label}"
  fi
done
