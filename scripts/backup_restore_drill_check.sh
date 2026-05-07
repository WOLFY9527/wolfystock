#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SMOKE_TEST_PATH="${ROOT_DIR}/tests/test_backup_restore_drill_smoke.py"
DB_PATH="${DATABASE_PATH:-}"

usage() {
  cat <<'USAGE'
Usage: scripts/backup_restore_drill_check.sh [--db-path PATH]

Print a local-only backup/restore release drill checklist.
This is a smoke drill helper only. It does not restore databases or touch
production systems.
USAGE
}

is_temp_like_path() {
  case "$1" in
    /tmp/*|/private/tmp/*|/var/folders/*|/private/var/folders/*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

refuse_unsafe_db_path() {
  local path="$1"

  if [[ -z "${path}" ]]; then
    return 0
  fi

  if is_temp_like_path "${path}"; then
    return 0
  fi

  echo "[FAIL] Unsafe DB path refused: ${path}" >&2
  echo "Only temp-like paths under /tmp, /private/tmp, /var/folders, or /private/var/folders are accepted." >&2
  exit 1
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --db-path)
      if [[ "$#" -lt 2 ]]; then
        echo "[FAIL] --db-path requires a value" >&2
        usage >&2
        exit 2
      fi
      DB_PATH="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[FAIL] Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cd "${ROOT_DIR}"

if [[ ! -f "${SMOKE_TEST_PATH}" ]]; then
  echo "[FAIL] Required smoke test missing: tests/test_backup_restore_drill_smoke.py" >&2
  exit 1
fi

refuse_unsafe_db_path "${DB_PATH}"

echo "Local-only backup/restore release drill checklist"
echo "Smoke test: tests/test_backup_restore_drill_smoke.py: present"
echo "Focused test command: python3 -m pytest tests/test_backup_restore_drill_smoke.py -q"
echo "Optional check command: bash -n scripts/backup_restore_drill_check.sh"
if [[ -n "${DB_PATH}" ]]; then
  echo "DB path safety: accepted (temp-only) -> ${DB_PATH}"
else
  echo "DB path safety: not checked (no DB path provided)"
fi
echo "Reminder: this is a smoke drill, not proof of production restore success."
echo "No production DB, migration, PostgreSQL, or backup infrastructure action is performed."
