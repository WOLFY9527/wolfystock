#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
if command -v python >/dev/null 2>&1; then
  PYTHON=(python)
elif command -v python3 >/dev/null 2>&1; then
  PYTHON=(python3)
elif command -v python.exe >/dev/null 2>&1; then
  PYTHON=(python.exe)
else
  printf '%s\n' '{"status":"error","reason":"Python 3 is required for bootstrap","remediation":"Install Python 3 or set it on PATH."}' >&2
  exit 1
fi
exec "${PYTHON[@]}" "${SCRIPT_DIR}/worktree_preflight.py" bootstrap "$@"
