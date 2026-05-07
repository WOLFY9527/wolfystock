#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SMOKE_TEST_PATH="${ROOT_DIR}/tests/test_backup_restore_drill_smoke.py"
METADATA_PATH=""
RESTORE_TARGET_PATH="${DATABASE_PATH:-}"
MAX_AGE_HOURS="72"
EXPECTED_SCHEMA_VERSION="backup_restore_preflight_v1"

usage() {
  cat <<'USAGE'
Usage: scripts/backup_restore_drill_check.sh --metadata PATH --restore-target PATH [--max-age-hours HOURS]

Run a dry-run, production-like backup/restore drill preflight against simulated
metadata. The checker validates artifact presence, timestamp freshness, schema
compatibility, and restore target isolation without restoring databases or
touching production systems.
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

refuse_unsafe_restore_target() {
  local path="$1"

  if [[ -z "${path}" ]]; then
    echo "[FAIL] Restore target path is required" >&2
    exit 1
  fi

  if is_temp_like_path "${path}"; then
    return 0
  fi

  echo "[FAIL] Unsafe restore target refused: ${path}" >&2
  echo "Only temp-like paths under /tmp, /private/tmp, /var/folders, or /private/var/folders are accepted." >&2
  exit 1
}

refuse_existing_restore_target() {
  local path="$1"

  if [[ -e "${path}" ]]; then
    echo "[FAIL] Restore target already exists: ${path}" >&2
    echo "Use a fresh temp-only target to avoid accidental overwrite planning." >&2
    exit 1
  fi
}

validate_backup_metadata() {
  python3 - "${METADATA_PATH}" "${MAX_AGE_HOURS}" "${EXPECTED_SCHEMA_VERSION}" <<'PY'
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

metadata_path = Path(sys.argv[1])
max_age_hours = int(sys.argv[2])
expected_schema = sys.argv[3]

if not metadata_path.is_file():
    print(f"[FAIL] Backup metadata is required and must exist: {metadata_path}", file=sys.stderr)
    sys.exit(1)

try:
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
except json.JSONDecodeError as exc:
    print(f"[FAIL] Backup metadata is not valid JSON: {exc}", file=sys.stderr)
    sys.exit(1)

required_fields = {"backup_id", "created_at", "artifact_path", "schema_version", "source_environment"}
missing_fields = sorted(required_fields - set(payload))
if missing_fields:
    print(f"[FAIL] Backup metadata missing fields: {', '.join(missing_fields)}", file=sys.stderr)
    sys.exit(1)

schema_version = str(payload.get("schema_version") or "")
if schema_version != expected_schema:
    print(
        f"[FAIL] Incompatible backup metadata schema: {schema_version} "
        f"(expected {expected_schema})",
        file=sys.stderr,
    )
    sys.exit(1)

raw_created_at = str(payload.get("created_at") or "")
try:
    created_at = datetime.fromisoformat(raw_created_at.replace("Z", "+00:00"))
except ValueError:
    print(f"[FAIL] Backup metadata timestamp is invalid: {raw_created_at}", file=sys.stderr)
    sys.exit(1)
if created_at.tzinfo is None:
    created_at = created_at.replace(tzinfo=timezone.utc)
created_at = created_at.astimezone(timezone.utc)

now = datetime.now(timezone.utc)
if created_at > now + timedelta(minutes=5):
    print(f"[FAIL] Backup metadata timestamp is in the future: {raw_created_at}", file=sys.stderr)
    sys.exit(1)
age = now - created_at
if age > timedelta(hours=max_age_hours):
    print(
        f"[FAIL] Stale backup metadata: age_hours={age.total_seconds() / 3600:.1f}, "
        f"max_age_hours={max_age_hours}",
        file=sys.stderr,
    )
    sys.exit(1)

raw_artifact_path = str(payload.get("artifact_path") or "")
artifact_path = Path(raw_artifact_path)
if not artifact_path.is_absolute():
    artifact_path = metadata_path.parent / artifact_path
artifact_path = artifact_path.resolve()
if not artifact_path.is_file():
    print(f"[FAIL] Backup artifact missing: {artifact_path}", file=sys.stderr)
    sys.exit(1)

source_environment = str(payload.get("source_environment") or "").strip().lower()
if source_environment not in {"synthetic", "sanitized", "anonymized"}:
    print(
        f"[FAIL] Backup metadata source_environment must be synthetic, sanitized, or anonymized: "
        f"{source_environment}",
        file=sys.stderr,
    )
    sys.exit(1)

print(f"Backup metadata: accepted ({metadata_path})")
print(f"Backup id: {payload['backup_id']}")
print(f"Backup artifact: present ({artifact_path})")
print(f"Backup timestamp: fresh ({created_at.isoformat().replace('+00:00', 'Z')}, max_age_hours={max_age_hours})")
print(f"Schema compatibility: ok ({schema_version})")
print(f"Source environment: {source_environment}")
PY
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --metadata)
      if [[ "$#" -lt 2 ]]; then
        echo "[FAIL] --metadata requires a value" >&2
        usage >&2
        exit 2
      fi
      METADATA_PATH="$2"
      shift 2
      ;;
    --restore-target)
      if [[ "$#" -lt 2 ]]; then
        echo "[FAIL] --restore-target requires a value" >&2
        usage >&2
        exit 2
      fi
      RESTORE_TARGET_PATH="$2"
      shift 2
      ;;
    --db-path)
      if [[ "$#" -lt 2 ]]; then
        echo "[FAIL] --db-path requires a value" >&2
        usage >&2
        exit 2
      fi
      RESTORE_TARGET_PATH="$2"
      shift 2
      ;;
    --max-age-hours)
      if [[ "$#" -lt 2 ]]; then
        echo "[FAIL] --max-age-hours requires a value" >&2
        usage >&2
        exit 2
      fi
      MAX_AGE_HOURS="$2"
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

if [[ -z "${METADATA_PATH}" ]]; then
  echo "[FAIL] Backup metadata is required; pass --metadata PATH" >&2
  exit 1
fi

if ! [[ "${MAX_AGE_HOURS}" =~ ^[0-9]+$ ]] || [[ "${MAX_AGE_HOURS}" -le 0 ]]; then
  echo "[FAIL] --max-age-hours must be a positive integer" >&2
  exit 2
fi

refuse_unsafe_restore_target "${RESTORE_TARGET_PATH}"
refuse_existing_restore_target "${RESTORE_TARGET_PATH}"

echo "Production-like backup/restore drill preflight"
echo "Mode: dry-run/simulated"
echo "Smoke test: tests/test_backup_restore_drill_smoke.py: present"
validate_backup_metadata
echo "Restore target isolation: accepted (temp-only) -> ${RESTORE_TARGET_PATH}"
echo "Dry-run evidence: suitable for launch readiness review"
echo "Focused test command: python3 -m pytest tests/test_backup_restore_drill_smoke.py -q"
echo "Optional check command: bash -n scripts/backup_restore_drill_check.sh"
echo "No production DB, migration, PostgreSQL, or backup infrastructure action is performed."
