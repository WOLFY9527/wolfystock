#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SMOKE_TEST_PATH="${ROOT_DIR}/tests/test_backup_restore_drill_smoke.py"
METADATA_PATH=""
RESTORE_TARGET_PATH="${DATABASE_PATH:-}"
RESTORE_DSN=""
REAL_RESTORE_EVIDENCE_PATH=""
MAX_AGE_HOURS="72"
EXPECTED_SCHEMA_VERSION="backup_restore_preflight_v1"
EXPECTED_APPLICATION_SCHEMA_VERSION="wolfystock_ops_readiness_v1"
SAFE_TEST_DSN_ENV="WOLFYSTOCK_RESTORE_PREFLIGHT_SAFE_TEST_DSN"
EXPECTED_REAL_EVIDENCE_SCHEMA_VERSION="wolfystock_restore_drill_evidence_v1"

usage() {
  cat <<'USAGE'
Usage: scripts/backup_restore_drill_check.sh --metadata PATH --restore-target PATH [--max-age-hours HOURS] [--restore-dsn DSN] [--real-restore-evidence PATH]

Run a dry-run, production-like PostgreSQL backup/restore/PITR preflight against
simulated metadata. The checker validates artifact presence, timestamp
freshness, schema compatibility, PITR/WAL evidence, and restore target
isolation without restoring databases or touching production systems.

--restore-dsn is validation-only. Any DSN is refused unless
WOLFYSTOCK_RESTORE_PREFLIGHT_SAFE_TEST_DSN=1 is set, and even then only local
synthetic/test restore targets are accepted.

--real-restore-evidence validates a sanitized JSON artifact from an externally
executed isolated PostgreSQL restore/PITR drill. The checker never executes the
restore itself; without this artifact, real restore execution remains pending.
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

  echo "[FAIL] Unsafe restore target refused" >&2
  echo "Only temp-like paths under /tmp, /private/tmp, /var/folders, or /private/var/folders are accepted." >&2
  exit 1
}

refuse_existing_restore_target() {
  local path="$1"

  if [[ -e "${path}" ]]; then
    echo "[FAIL] Restore target already exists" >&2
    echo "Use a fresh temp-only target to avoid accidental overwrite planning." >&2
    exit 1
  fi
}

validate_restore_dsn() {
  local dsn="$1"

  if [[ -z "${dsn}" ]]; then
    echo "Restore DSN: not provided (synthetic path-only preflight)"
    return 0
  fi

  python3 - "${dsn}" "${SAFE_TEST_DSN_ENV}" <<'PY'
import os
import sys
from urllib.parse import urlsplit

dsn = sys.argv[1]
safe_test_env = sys.argv[2]

def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    sys.exit(1)

if os.environ.get(safe_test_env) != "1":
    fail("Restore DSN refused: set explicit safe test mode for validation-only local DSNs")

parsed = urlsplit(dsn)
if parsed.scheme not in {"postgresql", "postgres"} or not parsed.hostname:
    fail("Restore DSN refused: expected local PostgreSQL DSN")

host = (parsed.hostname or "").lower()
database_name = parsed.path.lstrip("/").lower()
combined = f"{host}/{database_name}"

if host not in {"localhost", "127.0.0.1", "::1"}:
    fail("Restore DSN refused: host is not local")
if not database_name.startswith(("wolfystock_restore_", "synthetic_", "test_")):
    fail("Restore DSN refused: database name must be synthetic/test restore target")
if any(marker in combined for marker in ("prod", "production", "primary", "live")):
    fail("Restore DSN refused: production-like DSN marker")

print("Restore DSN: accepted (local synthetic/test target, value redacted)")
PY
}

validate_backup_metadata() {
  python3 - "${METADATA_PATH}" "${MAX_AGE_HOURS}" "${EXPECTED_SCHEMA_VERSION}" "${EXPECTED_APPLICATION_SCHEMA_VERSION}" <<'PY'
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

metadata_path = Path(sys.argv[1])
max_age_hours = int(sys.argv[2])
expected_schema = sys.argv[3]
expected_application_schema = sys.argv[4]


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    sys.exit(1)


def parse_timestamp(field_name: str, raw_value: object) -> datetime:
    value = str(raw_value or "")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail(f"{field_name} timestamp is invalid")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resolve_required_file(raw_path: object, label: str) -> Path:
    path = Path(str(raw_path or ""))
    if not path.is_absolute():
        path = metadata_path.parent / path
    path = path.resolve()
    if not path.is_file():
        fail(f"{label} missing")
    return path

if not metadata_path.is_file():
    fail("Backup metadata is required and must exist")

try:
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
except json.JSONDecodeError as exc:
    fail(f"Backup metadata is not valid JSON: {exc}")

required_fields = {
    "backup_id",
    "created_at",
    "artifact_path",
    "schema_version",
    "application_schema_version",
    "database_engine",
    "source_environment",
    "pitr",
}
missing_fields = sorted(required_fields - set(payload))
if missing_fields:
    fail(f"Backup metadata missing fields: {', '.join(missing_fields)}")

schema_version = str(payload.get("schema_version") or "")
if schema_version != expected_schema:
    fail(
        f"Incompatible backup metadata schema: {schema_version} "
        f"(expected {expected_schema})",
    )

application_schema_version = str(payload.get("application_schema_version") or "")
if application_schema_version != expected_application_schema:
    fail(
        "Incompatible application schema metadata "
        f"(expected {expected_application_schema})"
    )

database_engine = str(payload.get("database_engine") or "").strip().lower()
if database_engine != "postgresql":
    fail("Backup metadata database_engine must be postgresql for this preflight")

raw_created_at = str(payload.get("created_at") or "")
created_at = parse_timestamp("Backup metadata", raw_created_at)

now = datetime.now(timezone.utc)
if created_at > now + timedelta(minutes=5):
    fail("Backup metadata timestamp is in the future")
age = now - created_at
if age > timedelta(hours=max_age_hours):
    fail(
        f"Stale backup metadata: age_hours={age.total_seconds() / 3600:.1f}, "
        f"max_age_hours={max_age_hours}",
    )

artifact_path = resolve_required_file(payload.get("artifact_path"), "Backup artifact")

source_environment = str(payload.get("source_environment") or "").strip().lower()
if source_environment not in {"synthetic", "sanitized", "anonymized"}:
    fail(
        f"Backup metadata source_environment must be synthetic, sanitized, or anonymized: "
        f"{source_environment}"
    )

raw_pitr = payload.get("pitr")
if not isinstance(raw_pitr, dict):
    fail("PITR metadata must be an object")
pitr_required_fields = {"target_time", "window_start", "window_end", "wal_archive_path", "restore_point_label"}
pitr_missing_fields = sorted(field for field in pitr_required_fields if not raw_pitr.get(field))
if pitr_missing_fields:
    fail(f"PITR metadata missing fields: {', '.join(pitr_missing_fields)}")

pitr_target = parse_timestamp("PITR target_time", raw_pitr.get("target_time"))
pitr_window_start = parse_timestamp("PITR window_start", raw_pitr.get("window_start"))
pitr_window_end = parse_timestamp("PITR window_end", raw_pitr.get("window_end"))
if pitr_window_start > pitr_window_end:
    fail("PITR window_start must be before window_end")
if not (pitr_window_start <= pitr_target <= pitr_window_end):
    fail("PITR target_time is outside the available restore window")

wal_archive_path = resolve_required_file(raw_pitr.get("wal_archive_path"), "WAL/archive metadata")
restore_point_label = str(raw_pitr.get("restore_point_label") or "")
if any(marker in restore_point_label.lower() for marker in ("password", "token", "secret", "dsn")):
    fail("PITR restore_point_label must be sanitized")

print("Backup metadata: accepted")
print(f"Backup id: {payload['backup_id']}")
print(f"Backup artifact: present (bytes={artifact_path.stat().st_size})")
print(f"Backup timestamp: fresh ({created_at.isoformat().replace('+00:00', 'Z')}, max_age_hours={max_age_hours})")
print(f"Schema compatibility: ok ({schema_version})")
print(f"Application schema compatibility: ok ({application_schema_version})")
print("PITR metadata: validated")
print(f"PITR target: within window ({pitr_target.isoformat().replace('+00:00', 'Z')})")
print(f"WAL/archive metadata: present (bytes={wal_archive_path.stat().st_size})")
print(f"Source environment: {source_environment}")
PY
}

validate_real_restore_evidence() {
  if [[ -z "${REAL_RESTORE_EVIDENCE_PATH}" ]]; then
    echo "Real restore/PITR execution: pending (no real evidence artifact supplied)"
    echo "Launch status: blocked until isolated PostgreSQL restore/PITR evidence is supplied and accepted"
    return 0
  fi

  python3 - "${REAL_RESTORE_EVIDENCE_PATH}" "${EXPECTED_REAL_EVIDENCE_SCHEMA_VERSION}" <<'PY'
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

evidence_path = Path(sys.argv[1])
expected_schema = sys.argv[2]

REDACTED_VALUES = {
    "",
    "[redacted]",
    "redacted",
    "<redacted>",
    "***",
    "not_recorded",
    "not_provided",
    "none",
}
SENSITIVE_KEY_MARKERS = (
    "dsn",
    "password",
    "token",
    "secret",
    "cookie",
    "api_key",
    "private_key",
    "webhook_url",
)
SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"\bpostgres(?:ql)?://", re.IGNORECASE),
    re.compile(r"\b(?:password|token|secret|api[_-]?key|cookie)\s*=", re.IGNORECASE),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
)
REQUIRED_CHECKS = (
    "app_boot",
    "storage_readiness",
    "auth_login",
    "owner_isolation",
    "durable_task_poll",
    "admin_logs_sanitized",
    "cost_observability",
    "provider_diagnostics_sanitized",
    "scanner_artifact_read",
    "backtest_artifact_read",
    "portfolio_replay",
    "batch_a_indexes",
)


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    sys.exit(1)


def parse_timestamp(field_name: str, raw_value: Any) -> datetime:
    value = str(raw_value or "")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail(f"Real restore evidence {field_name} timestamp is invalid")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def ensure_redacted_sensitive_values(value: Any, key_path: str = "") -> None:
    if isinstance(value, dict):
        for raw_key, raw_child in value.items():
            key = str(raw_key)
            child_path = f"{key_path}.{key}" if key_path else key
            lowered_key = key.lower()
            if any(marker in lowered_key for marker in SENSITIVE_KEY_MARKERS):
                if isinstance(raw_child, str) and raw_child.strip().lower() not in REDACTED_VALUES:
                    fail("Real restore evidence contains unredacted sensitive value")
            ensure_redacted_sensitive_values(raw_child, child_path)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            ensure_redacted_sensitive_values(item, f"{key_path}[{index}]")
        return
    if isinstance(value, str):
        if any(pattern.search(value) for pattern in SENSITIVE_VALUE_PATTERNS):
            fail("Real restore evidence contains unredacted sensitive value")


if not evidence_path.is_file():
    fail("Real restore evidence artifact is required and must exist when supplied")

try:
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
except json.JSONDecodeError as exc:
    fail(f"Real restore evidence is not valid JSON: {exc}")

if not isinstance(payload, dict):
    fail("Real restore evidence must be a JSON object")

ensure_redacted_sensitive_values(payload)

required_top_level = {
    "schema_version",
    "drill_id",
    "captured_at",
    "database_engine",
    "source_environment",
    "restore_target",
    "execution",
    "rpo_minutes_observed",
    "rto_minutes_observed",
    "post_restore_checks",
    "sanitization",
    "blockers",
}
missing_top_level = sorted(required_top_level - set(payload))
if missing_top_level:
    fail(f"Real restore evidence missing fields: {', '.join(missing_top_level)}")

if str(payload.get("schema_version") or "") != expected_schema:
    fail(f"Real restore evidence schema must be {expected_schema}")

parse_timestamp("captured_at", payload.get("captured_at"))

if str(payload.get("database_engine") or "").strip().lower() != "postgresql":
    fail("Real restore evidence database_engine must be postgresql")

source_environment = str(payload.get("source_environment") or "").strip().lower()
if source_environment not in {"staging", "synthetic", "sanitized", "anonymized"}:
    fail("Real restore evidence source_environment must be staging, synthetic, sanitized, or anonymized")

restore_target = payload.get("restore_target")
if not isinstance(restore_target, dict):
    fail("Real restore evidence restore_target must be an object")
if restore_target.get("isolated") is not True:
    fail("Real restore evidence restore target must be isolated")
if restore_target.get("production_target") is not False:
    fail("Real restore evidence must not target production")
if str(restore_target.get("target_type") or "") != "isolated_postgresql":
    fail("Real restore evidence target_type must be isolated_postgresql")

execution = payload.get("execution")
if not isinstance(execution, dict):
    fail("Real restore evidence execution must be an object")
if execution.get("execution_opt_in") is not True:
    fail("Real restore evidence must record explicit operator opt-in")
if execution.get("restore_executed") is not True or execution.get("restore_status") != "pass":
    fail("Real restore evidence restore execution must be pass")
if execution.get("pitr_executed") is not True or execution.get("pitr_status") != "pass":
    fail("Real restore evidence PITR execution must be pass")
if execution.get("network_calls_performed_by_checker") is not False:
    fail("Real restore evidence must confirm checker performed no network calls")

for metric in ("rpo_minutes_observed", "rto_minutes_observed"):
    observed = payload.get(metric)
    if not isinstance(observed, int) or observed < 0:
        fail(f"Real restore evidence {metric} must be a non-negative integer")

post_restore_checks = payload.get("post_restore_checks")
if not isinstance(post_restore_checks, dict):
    fail("Real restore evidence post_restore_checks must be an object")
missing_checks = sorted(check for check in REQUIRED_CHECKS if check not in post_restore_checks)
if missing_checks:
    fail(f"Real restore evidence missing post-restore checks: {', '.join(missing_checks)}")
failing_checks = sorted(
    check for check in REQUIRED_CHECKS if str(post_restore_checks.get(check) or "").lower() != "pass"
)
if failing_checks:
    fail(f"Real restore evidence post-restore checks did not pass: {', '.join(failing_checks)}")

sanitization = payload.get("sanitization")
if not isinstance(sanitization, dict):
    fail("Real restore evidence sanitization must be an object")
required_sanitization = {
    "evidence_redacted": True,
    "secrets_printed": False,
    "raw_dsn_present": False,
    "raw_tokens_present": False,
    "raw_passwords_present": False,
}
for field, expected in required_sanitization.items():
    if sanitization.get(field) is not expected:
        fail(f"Real restore evidence sanitization {field} must be {expected}")

blockers = payload.get("blockers")
if not isinstance(blockers, list):
    fail("Real restore evidence blockers must be a list")
if blockers:
    fail("Real restore evidence blockers must be empty for accepted evidence")

print("Real restore/PITR evidence: accepted")
print("Real restore execution: externally supplied evidence only; checker did not execute restore")
print("Restore execution status: pass")
print("PITR execution status: pass")
print(f"Post-restore checks: {len(REQUIRED_CHECKS)} passed")
print(f"RPO observed: {payload['rpo_minutes_observed']} minutes")
print(f"RTO observed: {payload['rto_minutes_observed']} minutes")
print("Evidence sanitization: accepted (no raw DSNs, passwords, tokens, cookies, or private keys)")
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
    --restore-dsn)
      if [[ "$#" -lt 2 ]]; then
        echo "[FAIL] --restore-dsn requires a value" >&2
        usage >&2
        exit 2
      fi
      RESTORE_DSN="$2"
      shift 2
      ;;
    --real-restore-evidence)
      if [[ "$#" -lt 2 ]]; then
        echo "[FAIL] --real-restore-evidence requires a value" >&2
        usage >&2
        exit 2
      fi
      REAL_RESTORE_EVIDENCE_PATH="$2"
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
echo "Database engine: PostgreSQL"
echo "PITR evidence: enabled"
echo "Mode: dry-run/simulated"
echo "Smoke test: tests/test_backup_restore_drill_smoke.py: present"
validate_restore_dsn "${RESTORE_DSN}"
validate_backup_metadata
validate_real_restore_evidence
echo "Restore target isolation: accepted (temp-only, target does not exist)"
echo "Restore execution: disabled by default (preflight only; no restore command is invoked)"
echo "Dry-run evidence: suitable for launch readiness review"
echo "Focused test command: python3 -m pytest tests/test_backup_restore_drill_smoke.py -q"
echo "Optional check command: bash -n scripts/backup_restore_drill_check.sh"
echo "No production DB, migration, PostgreSQL restore, network, or backup infrastructure action is performed."
