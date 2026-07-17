#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"

resolve_repo_python() {
  local root="$1"
  local candidate
  for candidate in "${root}/.venv/bin/python" "${root}/.venv/Scripts/python.exe"; do
    if [[ -f "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  return 1
}

PYTHON_BIN="$(resolve_repo_python "${ROOT_DIR}" || true)"
if [[ -z "${PYTHON_BIN}" ]]; then
  CANONICAL_ROOT="$(git -C "${ROOT_DIR}" worktree list --porcelain | awk 'NR == 1 {sub(/^worktree /, ""); print; exit}')"
  PYTHON_BIN="$(resolve_repo_python "${CANONICAL_ROOT}" || true)"
fi
if [[ -z "${PYTHON_BIN}" ]]; then
  printf '%s\n' '{"status":"error","reason":"repository .venv Python is required for bootstrap","remediation":"Repair the canonical worktree .venv; no fallback interpreter will be used."}' >&2
  exit 1
fi

exec "${PYTHON_BIN}" "${SCRIPT_DIR}/worktree_preflight.py" bootstrap "$@"
