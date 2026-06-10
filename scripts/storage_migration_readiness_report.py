#!/usr/bin/env python3
"""Offline storage migration readiness report for sanitized local evidence.

This helper is intentionally report-only. It inspects an explicitly supplied
SQLite database through a read-only URI, optionally reads sanitized evidence
files, and emits aggregate JSON only. It does not import runtime storage
managers, run migrations, connect to PostgreSQL, or execute cleanup.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPORT_SCHEMA_VERSION = "wolfystock_storage_migration_readiness_v1"
REPORT_MODE = "report_only"
SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MUTATION_SQL_RE = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|VACUUM|REPLACE|TRUNCATE)\b"
    r"|\bPRAGMA\s+writable_schema\b",
    re.IGNORECASE,
)

QUOTA_USAGE_REQUIRED_COLUMNS = {
    "window_identity_key",
    "window_type",
    "window_start",
    "reserved_units",
    "consumed_units",
}
QUOTA_RESERVATION_REQUIRED_COLUMNS = {
    "reservation_id",
    "owner_user_id",
    "route_family",
    "provider",
    "model_tier",
    "request_idempotency_key_hash",
    "estimated_units",
    "status",
    "created_at",
}
PG_REQUIRED_TABLES = (
    "quota_usage_windows",
    "quota_reservations",
    "llm_cost_ledger",
    "model_pricing_policies",
    "provider_quota_windows",
)
RESTORE_PITR_MARKERS = (
    "restoreCommandExecuted",
    "pitrTargetTimestamp",
    "verificationQueries",
    "evidenceRedactionVersion",
)
SENSITIVE_VALUE_RE = re.compile(
    r"(?:postgres(?:ql)?://|mysql://|redis://|sk-[A-Za-z0-9_-]{12,}|"
    r"\b(?:api[_-]?key|token|secret|password|cookie|session|dsn)\s*[=:]\s*[^\s,;]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ReadinessFinding:
    risk_code: str
    severity: str
    summary: str

    def to_dict(self) -> dict[str, str]:
        return {
            "riskCode": self.risk_code,
            "severity": self.severity,
            "summary": self.summary,
        }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _quote_identifier(identifier: str) -> str:
    if not SAFE_IDENTIFIER_RE.fullmatch(identifier):
        raise ValueError("unsafe SQL identifier")
    return f'"{identifier}"'


def _guard_sql(statement: str) -> None:
    if MUTATION_SQL_RE.search(statement):
        raise RuntimeError("SQL mutation is forbidden in storage migration readiness reports")


def _execute_readonly(
    conn: sqlite3.Connection,
    statement: str,
    parameters: Iterable[Any] = (),
) -> sqlite3.Cursor:
    _guard_sql(statement)
    return conn.execute(statement, tuple(parameters))


def _open_sqlite_readonly(path: Path) -> sqlite3.Connection:
    if not path.exists() or not path.is_file():
        raise SystemExit("[FAIL] SQLite database file is required for inspection")
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.set_trace_callback(_guard_sql)
    return conn


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = _execute_readonly(conn, "SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {str(row[0]) for row in rows if row and row[0]}


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    quoted = _quote_identifier(table_name)
    rows = _execute_readonly(conn, f"PRAGMA table_info({quoted})").fetchall()
    return {str(row[1]) for row in rows if len(row) > 1 and row[1]}


def _count_rows(conn: sqlite3.Connection, table_name: str) -> int:
    quoted = _quote_identifier(table_name)
    row = _execute_readonly(conn, f"SELECT COUNT(*) FROM {quoted}").fetchone()
    return int(row[0] or 0) if row else 0


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _parse_datetime(value: Any) -> datetime | None:
    text = _clean_text(value)
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed.replace(microsecond=0)


def _daily_window_start(value: Any) -> str | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    return parsed.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(sep=" ")


def _monthly_window_start(value: Any) -> str | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    return parsed.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat(sep=" ")


def _normalize_window_start(value: Any) -> str:
    parsed = _parse_datetime(value)
    return parsed.isoformat(sep=" ") if parsed is not None else _clean_text(value)[:64]


def _identity_component(value: Any, *, lowercase: bool = False) -> str:
    text = _clean_text(value)
    if lowercase:
        text = text.lower()
    return text[:128] if text else "none"


def _identity_segment(label: str, value: str) -> str:
    return f"{label}:{len(value)}:{value}"


def _quota_window_identity(
    *,
    owner_user_id: Any,
    route_family: Any,
    provider: Any,
    model_tier: Any,
) -> str:
    parts = (
        _identity_segment("owner", _identity_component(owner_user_id)),
        _identity_segment("route", _identity_component(route_family, lowercase=True)),
        _identity_segment("provider", _identity_component(provider, lowercase=True)),
        _identity_segment("model", _identity_component(model_tier, lowercase=True)),
    )
    return "qwin_scope_v1|" + "|".join(parts)


def _unavailable(reason: str) -> dict[str, Any]:
    return {"state": "unavailable", "reasonCode": reason}


def _check_duplicate_windows(conn: sqlite3.Connection, columns: set[str]) -> dict[str, Any]:
    required = {"window_identity_key", "window_type", "window_start"}
    if not required.issubset(columns):
        return _unavailable("required_columns_missing")
    rows = _execute_readonly(
        conn,
        """
        SELECT window_identity_key, window_type, window_start, COUNT(*) AS row_count
        FROM quota_usage_windows
        GROUP BY window_identity_key, window_type, window_start
        HAVING COUNT(*) > 1
        """,
    ).fetchall()
    duplicate_group_count = len(rows)
    duplicate_row_count = sum(int(row["row_count"] or 0) for row in rows)
    return {
        "state": "risk" if duplicate_group_count else "pass",
        "duplicateGroupCount": duplicate_group_count,
        "duplicateRowCount": duplicate_row_count,
    }


def _check_blank_or_default_window_identity(conn: sqlite3.Connection, columns: set[str]) -> dict[str, Any]:
    if "window_identity_key" not in columns:
        return _unavailable("required_columns_missing")
    row = _execute_readonly(
        conn,
        """
        SELECT COUNT(*) AS row_count
        FROM quota_usage_windows
        WHERE window_identity_key IS NULL
           OR TRIM(window_identity_key) = ''
           OR LOWER(TRIM(window_identity_key)) IN ('default', 'none', 'null')
           OR window_identity_key NOT LIKE 'qwin_scope_v1|%'
        """,
    ).fetchone()
    row_count = int(row["row_count"] or 0) if row else 0
    return {"state": "risk" if row_count else "pass", "rowCount": row_count}


def _check_duplicate_idempotency_hash(conn: sqlite3.Connection, columns: set[str]) -> dict[str, Any]:
    if "request_idempotency_key_hash" not in columns:
        return _unavailable("required_columns_missing")
    rows = _execute_readonly(
        conn,
        """
        SELECT request_idempotency_key_hash, COUNT(*) AS row_count
        FROM quota_reservations
        WHERE request_idempotency_key_hash IS NOT NULL
          AND TRIM(request_idempotency_key_hash) != ''
        GROUP BY request_idempotency_key_hash
        HAVING COUNT(*) > 1
        """,
    ).fetchall()
    duplicate_group_count = len(rows)
    duplicate_row_count = sum(int(row["row_count"] or 0) for row in rows)
    return {
        "state": "risk" if duplicate_group_count else "pass",
        "duplicateGroupCount": duplicate_group_count,
        "duplicateRowCount": duplicate_row_count,
    }


def _expected_counter_groups(conn: sqlite3.Connection) -> dict[tuple[str, str, str], dict[str, int]]:
    rows = _execute_readonly(
        conn,
        """
        SELECT owner_user_id, route_family, provider, model_tier, estimated_units, status, created_at
        FROM quota_reservations
        """,
    ).fetchall()
    expected: dict[tuple[str, str, str], dict[str, int]] = defaultdict(lambda: {"reserved": 0, "consumed": 0})
    for row in rows:
        daily_start = _daily_window_start(row["created_at"])
        monthly_start = _monthly_window_start(row["created_at"])
        if daily_start is None or monthly_start is None:
            continue
        estimated_units = _safe_int(row["estimated_units"])
        status = _clean_text(row["status"]).lower()
        reserved_units = estimated_units if status == "reserved" else 0
        consumed_units = estimated_units if status == "consumed" else 0
        identities = (
            _quota_window_identity(
                owner_user_id=row["owner_user_id"],
                route_family=row["route_family"],
                provider=row["provider"],
                model_tier=row["model_tier"],
            ),
            _quota_window_identity(
                owner_user_id=None,
                route_family=row["route_family"],
                provider=row["provider"],
                model_tier=row["model_tier"],
            ),
        )
        for identity in identities:
            for window_type, window_start in (("daily", daily_start), ("monthly", monthly_start)):
                bucket = expected[(identity, window_type, window_start)]
                bucket["reserved"] += reserved_units
                bucket["consumed"] += consumed_units
    return expected


def _observed_counter_groups(conn: sqlite3.Connection) -> dict[tuple[str, str, str], dict[str, int]]:
    rows = _execute_readonly(
        conn,
        """
        SELECT window_identity_key, window_type, window_start, reserved_units, consumed_units
        FROM quota_usage_windows
        """,
    ).fetchall()
    observed: dict[tuple[str, str, str], dict[str, int]] = defaultdict(lambda: {"reserved": 0, "consumed": 0})
    for row in rows:
        key = (
            _clean_text(row["window_identity_key"]),
            _clean_text(row["window_type"]).lower(),
            _normalize_window_start(row["window_start"]),
        )
        observed[key]["reserved"] += _safe_int(row["reserved_units"])
        observed[key]["consumed"] += _safe_int(row["consumed_units"])
    return observed


def _check_terminal_counter_mismatch(
    conn: sqlite3.Connection,
    window_columns: set[str],
    reservation_columns: set[str],
) -> dict[str, Any]:
    if not QUOTA_USAGE_REQUIRED_COLUMNS.issubset(window_columns):
        return _unavailable("quota_usage_windows_columns_missing")
    required_reservation_columns = {
        "owner_user_id",
        "route_family",
        "provider",
        "model_tier",
        "estimated_units",
        "status",
        "created_at",
    }
    if not required_reservation_columns.issubset(reservation_columns):
        return _unavailable("quota_reservations_columns_missing")

    expected = _expected_counter_groups(conn)
    observed = _observed_counter_groups(conn)
    mismatch_count = 0
    expected_reserved = 0
    observed_reserved = 0
    expected_consumed = 0
    observed_consumed = 0
    for key, observed_counts in observed.items():
        expected_counts = expected.get(key, {"reserved": 0, "consumed": 0})
        if (
            expected_counts["reserved"] != observed_counts["reserved"]
            or expected_counts["consumed"] != observed_counts["consumed"]
        ):
            mismatch_count += 1
            expected_reserved += expected_counts["reserved"]
            observed_reserved += observed_counts["reserved"]
            expected_consumed += expected_counts["consumed"]
            observed_consumed += observed_counts["consumed"]

    return {
        "state": "risk" if mismatch_count else "pass",
        "mismatchGroupCount": mismatch_count,
        "expectedReservedUnits": expected_reserved,
        "observedReservedUnits": observed_reserved,
        "minimumExpectedConsumedUnits": expected_consumed,
        "observedConsumedUnits": observed_consumed,
        "exactConsumedUnitsRecoverable": False,
    }


def _sqlite_readiness(conn: sqlite3.Connection | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if conn is None:
        return (
            {
                "state": "not_provided",
                "databasePathIncluded": False,
                "tablesInspected": [],
                "missingTables": ["quota_usage_windows", "quota_reservations"],
                "missingColumns": {},
            },
            {
                "duplicateQuotaWindowIdentity": _unavailable("sqlite_db_not_provided"),
                "blankOrDefaultWindowIdentity": _unavailable("sqlite_db_not_provided"),
                "duplicateReservationIdempotencyHash": _unavailable("sqlite_db_not_provided"),
                "terminalCounterMismatch": _unavailable("sqlite_db_not_provided"),
            },
        )

    table_names = _table_names(conn)
    missing_tables = [
        table_name
        for table_name in ("quota_usage_windows", "quota_reservations")
        if table_name not in table_names
    ]
    window_columns = _table_columns(conn, "quota_usage_windows") if "quota_usage_windows" in table_names else set()
    reservation_columns = _table_columns(conn, "quota_reservations") if "quota_reservations" in table_names else set()
    missing_columns: dict[str, list[str]] = {}
    if "quota_usage_windows" in table_names:
        missing = sorted(QUOTA_USAGE_REQUIRED_COLUMNS - window_columns)
        if missing:
            missing_columns["quota_usage_windows"] = missing
    if "quota_reservations" in table_names:
        missing = sorted(QUOTA_RESERVATION_REQUIRED_COLUMNS - reservation_columns)
        if missing:
            missing_columns["quota_reservations"] = missing

    if missing_tables or missing_columns:
        state = "partial"
    else:
        state = "inspected"

    quota_readiness = {
        "duplicateQuotaWindowIdentity": (
            _check_duplicate_windows(conn, window_columns)
            if "quota_usage_windows" in table_names
            else _unavailable("quota_usage_windows_missing")
        ),
        "blankOrDefaultWindowIdentity": (
            _check_blank_or_default_window_identity(conn, window_columns)
            if "quota_usage_windows" in table_names
            else _unavailable("quota_usage_windows_missing")
        ),
        "duplicateReservationIdempotencyHash": (
            _check_duplicate_idempotency_hash(conn, reservation_columns)
            if "quota_reservations" in table_names
            else _unavailable("quota_reservations_missing")
        ),
        "terminalCounterMismatch": (
            _check_terminal_counter_mismatch(conn, window_columns, reservation_columns)
            if {"quota_usage_windows", "quota_reservations"}.issubset(table_names)
            else _unavailable("quota_tables_missing")
        ),
    }
    sqlite_summary = {
        "state": state,
        "databasePathIncluded": False,
        "tablesInspected": sorted(
            table_name
            for table_name in ("quota_usage_windows", "quota_reservations")
            if table_name in table_names
        ),
        "missingTables": missing_tables,
        "missingColumns": missing_columns,
        "rowCounts": {
            table_name: _count_rows(conn, table_name)
            for table_name in ("quota_usage_windows", "quota_reservations")
            if table_name in table_names
        },
    }
    return sqlite_summary, quota_readiness


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise SystemExit("[FAIL] Evidence file was not found")


def _text_has_sensitive_values(text: str) -> bool:
    return bool(SENSITIVE_VALUE_RE.search(text))


def _postgres_evidence(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "state": "not_provided",
            "evidenceProvided": False,
            "liveConnectionAttempted": False,
            "requiredTablesPresentCount": 0,
            "requiredTablesMissing": list(PG_REQUIRED_TABLES),
        }
    text = _safe_read_text(path)
    if _text_has_sensitive_values(text):
        return {
            "state": "rejected",
            "evidenceProvided": True,
            "liveConnectionAttempted": False,
            "rejectionReason": "sensitive_value_marker_detected",
            "requiredTablesPresentCount": 0,
            "requiredTablesMissing": list(PG_REQUIRED_TABLES),
        }
    lowered = text.lower()
    present = [table for table in PG_REQUIRED_TABLES if table.lower() in lowered]
    missing = [table for table in PG_REQUIRED_TABLES if table not in present]
    return {
        "state": "present" if not missing else "partial",
        "evidenceProvided": True,
        "liveConnectionAttempted": False,
        "requiredTablesPresentCount": len(present),
        "requiredTablesMissing": missing,
    }


def _restore_pitr_evidence(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "state": "not_provided",
            "evidenceProvided": False,
            "restoreCommandsExecutedByHelper": False,
            "requiredMarkersPresentCount": 0,
            "requiredMarkersMissing": list(RESTORE_PITR_MARKERS),
        }
    text = _safe_read_text(path)
    if _text_has_sensitive_values(text):
        return {
            "state": "rejected",
            "evidenceProvided": True,
            "restoreCommandsExecutedByHelper": False,
            "rejectionReason": "sensitive_value_marker_detected",
            "requiredMarkersPresentCount": 0,
            "requiredMarkersMissing": list(RESTORE_PITR_MARKERS),
        }
    present = [marker for marker in RESTORE_PITR_MARKERS if marker in text]
    missing = [marker for marker in RESTORE_PITR_MARKERS if marker not in present]
    return {
        "state": "present" if not missing else "partial",
        "evidenceProvided": True,
        "restoreCommandsExecutedByHelper": False,
        "requiredMarkersPresentCount": len(present),
        "requiredMarkersMissing": missing,
    }


def _backtest_cleanup_constraints() -> dict[str, Any]:
    return {
        "state": "checklist",
        "leafTablesRequireParentJoin": True,
        "cleanupAllowed": False,
        "checklistEvidence": [
            {
                "leafTable": "rule_backtest_trades",
                "parentTable": "rule_backtest_runs",
                "constraint": "parent_join_required_before_cleanup",
            },
            {
                "leafTable": "rule_backtest_universe_symbol_results",
                "parentTable": "rule_backtest_universe_jobs",
                "constraint": "parent_join_required_before_cleanup",
            },
            {
                "leafTable": "backtest_artifacts",
                "parentTable": "backtest_runs",
                "constraint": "parent_join_required_before_cleanup",
            },
        ],
    }


def _findings_from_checks(
    quota_readiness: Mapping[str, Mapping[str, Any]],
    postgres: Mapping[str, Any],
    restore_pitr: Mapping[str, Any],
) -> list[ReadinessFinding]:
    findings: list[ReadinessFinding] = []
    if quota_readiness["duplicateQuotaWindowIdentity"].get("state") == "risk":
        findings.append(
            ReadinessFinding(
                "duplicate_quota_window_identity",
                "high",
                "Duplicate quota usage windows exist for one identity/window group.",
            )
        )
    if quota_readiness["blankOrDefaultWindowIdentity"].get("state") == "risk":
        findings.append(
            ReadinessFinding(
                "blank_or_default_window_identity",
                "high",
                "Quota usage windows include blank/default/unbackfilled identity values.",
            )
        )
    if quota_readiness["duplicateReservationIdempotencyHash"].get("state") == "risk":
        findings.append(
            ReadinessFinding(
                "duplicate_reservation_idempotency_hash",
                "high",
                "Duplicate non-null reservation idempotency hash groups exist.",
            )
        )
    if quota_readiness["terminalCounterMismatch"].get("state") == "risk":
        findings.append(
            ReadinessFinding(
                "terminal_reservation_window_counter_mismatch",
                "high",
                "Reservation lifecycle aggregates do not match quota window counters.",
            )
        )
    if postgres.get("state") in {"partial", "rejected"}:
        findings.append(
            ReadinessFinding(
                "quota_cost_pg_schema_evidence_absent_or_partial",
                "medium",
                "Quota/cost PostgreSQL schema evidence is absent, partial, or rejected.",
            )
        )
    if restore_pitr.get("state") in {"partial", "rejected"}:
        findings.append(
            ReadinessFinding(
                "restore_pitr_evidence_absent_or_partial",
                "medium",
                "Restore/PITR evidence is absent, partial, or rejected.",
            )
        )
    return findings


def _risk_summary(findings: Iterable[ReadinessFinding]) -> dict[str, Any]:
    materialized = list(findings)
    high_count = sum(1 for finding in materialized if finding.severity == "high")
    medium_count = sum(1 for finding in materialized if finding.severity == "medium")
    return {
        "findingCount": len(materialized),
        "highRiskFindingCount": high_count,
        "mediumRiskFindingCount": medium_count,
    }


def build_report(
    *,
    sqlite_db: Path | None = None,
    postgres_schema_evidence: Path | None = None,
    restore_pitr_evidence: Path | None = None,
) -> dict[str, Any]:
    conn: sqlite3.Connection | None = None
    try:
        if sqlite_db is not None:
            conn = _open_sqlite_readonly(sqlite_db)
        sqlite_summary, quota_readiness = _sqlite_readiness(conn)
    finally:
        if conn is not None:
            conn.close()

    postgres = _postgres_evidence(postgres_schema_evidence)
    restore_pitr = _restore_pitr_evidence(restore_pitr_evidence)
    findings = _findings_from_checks(quota_readiness, postgres, restore_pitr)
    summary = _risk_summary(findings)
    overall_risk = "high" if summary["highRiskFindingCount"] else ("medium" if summary["mediumRiskFindingCount"] else "low")

    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "mode": REPORT_MODE,
        "generatedAt": _utc_now_iso(),
        "readOnly": True,
        "mutationsExecuted": False,
        "cleanupExecuted": False,
        "migrationExecuted": False,
        "migrationApproved": False,
        "runtimeBehaviorChanged": False,
        "networkCallsEnabled": False,
        "productionStorageTouched": False,
        "rawArtifactBodiesIncluded": False,
        "livePostgresConnectionAttempted": False,
        "databasePathIncluded": False,
        "overallRisk": overall_risk,
        "summary": summary,
        "sqlite": sqlite_summary,
        "quotaReadiness": quota_readiness,
        "postgres": postgres,
        "restorePitr": restore_pitr,
        "backtestCleanupConstraints": _backtest_cleanup_constraints(),
        "findings": [finding.to_dict() for finding in findings],
        "sanitization": {
            "dsnIncluded": False,
            "absolutePathIncluded": False,
            "rowIdentifiersIncluded": False,
            "rawPayloadIncluded": False,
            "ownerIdentifiersIncluded": False,
            "reservationIdentifiersIncluded": False,
            "idempotencyHashesIncluded": False,
            "windowIdentityValuesIncluded": False,
            "tokensSecretsIncluded": False,
        },
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Emit sanitized report-only storage migration readiness JSON.",
    )
    parser.add_argument(
        "--sqlite-db",
        type=Path,
        help="Optional SQLite database file to inspect using a read-only connection. The path is never emitted.",
    )
    parser.add_argument(
        "--postgres-schema-evidence",
        type=Path,
        help="Optional sanitized PostgreSQL schema evidence file. No live PostgreSQL connection is attempted.",
    )
    parser.add_argument(
        "--restore-pitr-evidence",
        type=Path,
        help="Optional sanitized restore/PITR evidence file. The helper never runs restore commands.",
    )
    parser.add_argument(
        "--fail-on-risk",
        action="store_true",
        help="Exit nonzero when high-risk findings are present.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(argv or sys.argv[1:]))
    try:
        report = build_report(
            sqlite_db=args.sqlite_db,
            postgres_schema_evidence=args.postgres_schema_evidence,
            restore_pitr_evidence=args.restore_pitr_evidence,
        )
    except sqlite3.DatabaseError:
        print("[FAIL] SQLite inspection failed: malformed_or_unreadable_database", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"[FAIL] Invalid input: {exc}", file=sys.stderr)
        return 1
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 2 if args.fail_on_risk and report["summary"]["findingCount"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
