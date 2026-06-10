# -*- coding: utf-8 -*-
"""Tests for the report-only storage migration readiness helper."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.storage_migration_readiness_report import (
    MUTATION_SQL_RE,
    REPORT_SCHEMA_VERSION,
    build_report,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "storage_migration_readiness_report.py"


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _create_quota_fixture(path: Path) -> None:
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE quota_usage_windows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_user_id TEXT,
                route_family TEXT,
                provider TEXT,
                model_tier TEXT,
                window_identity_key TEXT,
                window_type TEXT NOT NULL,
                window_start TEXT NOT NULL,
                window_end TEXT NOT NULL,
                reserved_units INTEGER NOT NULL DEFAULT 0,
                consumed_units INTEGER NOT NULL DEFAULT 0,
                request_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT
            );
            CREATE TABLE quota_reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reservation_id TEXT NOT NULL,
                owner_user_id TEXT,
                route_family TEXT,
                provider TEXT,
                model_tier TEXT,
                request_idempotency_key_hash TEXT,
                estimated_units INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                reason_code TEXT,
                metadata_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                expires_at TEXT NOT NULL
            );
            """
        )


def _window_identity(owner: str = "owner-secret") -> str:
    return (
        "qwin_scope_v1|"
        f"owner:{len(owner)}:{owner}|"
        "route:8:analysis|"
        "provider:6:openai|"
        "model:4:base"
    )


def _insert_window(
    conn: sqlite3.Connection,
    *,
    identity: str | None = None,
    owner: str | None = "owner-secret",
    window_type: str = "daily",
    window_start: str = "2026-06-10 00:00:00",
    reserved_units: int = 0,
    consumed_units: int = 0,
) -> None:
    conn.execute(
        """
        INSERT INTO quota_usage_windows (
            owner_user_id,
            route_family,
            provider,
            model_tier,
            window_identity_key,
            window_type,
            window_start,
            window_end,
            reserved_units,
            consumed_units,
            request_count,
            updated_at
        ) VALUES (?, 'analysis', 'openai', 'base', ?, ?, ?, '2026-06-11 00:00:00', ?, ?, 1, '2026-06-10 00:10:00')
        """,
        (owner, identity if identity is not None else _window_identity(owner or "system"), window_type, window_start, reserved_units, consumed_units),
    )


def _insert_reservation(
    conn: sqlite3.Connection,
    *,
    reservation_id: str = "qres-secret-1",
    owner: str | None = "owner-secret",
    request_hash: str | None = "qres_req_v1:secret-hash",
    estimated_units: int = 10,
    status: str = "reserved",
    created_at: str = "2026-06-10 12:00:00",
) -> None:
    conn.execute(
        """
        INSERT INTO quota_reservations (
            reservation_id,
            owner_user_id,
            route_family,
            provider,
            model_tier,
            request_idempotency_key_hash,
            estimated_units,
            status,
            reason_code,
            metadata_json,
            created_at,
            updated_at,
            expires_at
        ) VALUES (?, ?, 'analysis', 'openai', 'base', ?, ?, ?, 'fixture-reason', ?, ?, '2026-06-10 12:01:00', '2026-06-11 12:00:00')
        """,
        (
            reservation_id,
            owner,
            request_hash,
            estimated_units,
            status,
            json.dumps(
                {
                    "token": "sk-test-secret",
                    "raw_payload": {"owner_id": owner, "reservation_id": reservation_id},
                }
            ),
            created_at,
        ),
    )


def _risk_codes(report: dict[str, object]) -> set[str]:
    findings = report["findings"]
    assert isinstance(findings, list)
    return {str(item["riskCode"]) for item in findings if isinstance(item, dict)}


def test_clean_db_passes_with_no_high_risk_findings(tmp_path: Path) -> None:
    db_path = tmp_path / "clean.db"
    _create_quota_fixture(db_path)
    with _connect(db_path) as conn:
        _insert_window(conn, reserved_units=10, consumed_units=0)
        _insert_reservation(conn, reservation_id="qres-secret-1", status="reserved", estimated_units=10)

    report = build_report(sqlite_db=db_path)

    assert report["schemaVersion"] == REPORT_SCHEMA_VERSION
    assert report["readOnly"] is True
    assert report["mutationsExecuted"] is False
    assert report["migrationApproved"] is False
    assert report["runtimeBehaviorChanged"] is False
    assert report["networkCallsEnabled"] is False
    assert report["productionStorageTouched"] is False
    assert report["rawArtifactBodiesIncluded"] is False
    assert report["overallRisk"] == "low"
    assert report["summary"]["highRiskFindingCount"] == 0
    assert _risk_codes(report) == set()
    assert report["sqlite"]["state"] == "inspected"
    assert report["postgres"]["state"] == "not_provided"
    assert report["restorePitr"]["state"] == "not_provided"


def test_duplicate_quota_window_identity_rows_are_reported(tmp_path: Path) -> None:
    db_path = tmp_path / "duplicates.db"
    _create_quota_fixture(db_path)
    with _connect(db_path) as conn:
        _insert_window(conn, reserved_units=4)
        _insert_window(conn, reserved_units=6)

    report = build_report(sqlite_db=db_path)

    quota = report["quotaReadiness"]
    assert quota["duplicateQuotaWindowIdentity"]["state"] == "risk"
    assert quota["duplicateQuotaWindowIdentity"]["duplicateRowCount"] == 2
    assert quota["duplicateQuotaWindowIdentity"]["duplicateGroupCount"] == 1
    assert "duplicate_quota_window_identity" in _risk_codes(report)


def test_blank_default_identity_rows_are_reported(tmp_path: Path) -> None:
    db_path = tmp_path / "blank.db"
    _create_quota_fixture(db_path)
    with _connect(db_path) as conn:
        _insert_window(conn, identity="", reserved_units=1)
        _insert_window(conn, identity="default", reserved_units=1)

    report = build_report(sqlite_db=db_path)

    identity = report["quotaReadiness"]["blankOrDefaultWindowIdentity"]
    assert identity["state"] == "risk"
    assert identity["rowCount"] == 2
    assert "blank_or_default_window_identity" in _risk_codes(report)


def test_duplicate_idempotency_hash_is_reported(tmp_path: Path) -> None:
    db_path = tmp_path / "idempotency.db"
    _create_quota_fixture(db_path)
    with _connect(db_path) as conn:
        _insert_reservation(conn, reservation_id="qres-secret-1", request_hash="qres_req_v1:raw-secret")
        _insert_reservation(conn, reservation_id="qres-secret-2", request_hash="qres_req_v1:raw-secret")
        _insert_reservation(conn, reservation_id="qres-secret-3", request_hash=None)
        _insert_reservation(conn, reservation_id="qres-secret-4", request_hash=None)

    report = build_report(sqlite_db=db_path)

    duplicate = report["quotaReadiness"]["duplicateReservationIdempotencyHash"]
    assert duplicate["state"] == "risk"
    assert duplicate["duplicateRowCount"] == 2
    assert duplicate["duplicateGroupCount"] == 1
    assert "duplicate_reservation_idempotency_hash" in _risk_codes(report)


def test_terminal_counter_mismatch_is_reported(tmp_path: Path) -> None:
    db_path = tmp_path / "mismatch.db"
    _create_quota_fixture(db_path)
    with _connect(db_path) as conn:
        _insert_reservation(conn, reservation_id="qres-secret-1", status="reserved", estimated_units=10)
        _insert_reservation(conn, reservation_id="qres-secret-2", status="consumed", estimated_units=7)
        _insert_window(conn, reserved_units=999, consumed_units=0)

    report = build_report(sqlite_db=db_path)

    mismatch = report["quotaReadiness"]["terminalCounterMismatch"]
    assert mismatch["state"] == "risk"
    assert mismatch["mismatchGroupCount"] == 1
    assert mismatch["expectedReservedUnits"] == 10
    assert mismatch["observedReservedUnits"] == 999
    assert mismatch["minimumExpectedConsumedUnits"] == 7
    assert mismatch["observedConsumedUnits"] == 0
    assert "terminal_reservation_window_counter_mismatch" in _risk_codes(report)


def test_missing_optional_tables_produce_partial_state(tmp_path: Path) -> None:
    db_path = tmp_path / "partial.db"
    with _connect(db_path) as conn:
        conn.execute("CREATE TABLE quota_usage_windows (id INTEGER PRIMARY KEY, window_identity_key TEXT)")

    report = build_report(sqlite_db=db_path)

    assert report["sqlite"]["state"] == "partial"
    assert "quota_reservations" in report["sqlite"]["missingTables"]
    assert report["quotaReadiness"]["duplicateReservationIdempotencyHash"]["state"] == "unavailable"
    assert report["quotaReadiness"]["terminalCounterMismatch"]["state"] == "unavailable"


def test_sanitized_output_excludes_sensitive_values(tmp_path: Path) -> None:
    db_path = tmp_path / "secret-token-local-path.db"
    _create_quota_fixture(db_path)
    with _connect(db_path) as conn:
        _insert_window(conn, reserved_units=999, consumed_units=0)
        _insert_reservation(
            conn,
            reservation_id="qres-top-secret",
            owner="owner-private-1",
            request_hash="qres_req_v1:private-hash",
            status="consumed",
        )

    payload = json.dumps(build_report(sqlite_db=db_path), sort_keys=True)

    forbidden_fragments = [
        str(db_path),
        "secret-token-local-path.db",
        "sk-test-secret",
        "owner-private-1",
        "qres-top-secret",
        "qres_req_v1:private-hash",
        _window_identity("owner-private-1"),
        '"id"',
        "raw_payload",
        "reservation_id",
        "owner_id",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in payload


def test_no_sql_mutation_is_executed_with_guarded_connection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "guarded.db"
    _create_quota_fixture(db_path)
    with _connect(db_path) as conn:
        _insert_window(conn)

    executed: list[str] = []

    class GuardedConnection(sqlite3.Connection):
        def execute(self, sql: str, parameters: object = ()):  # type: ignore[override]
            executed.append(sql)
            assert MUTATION_SQL_RE.search(sql) is None, sql
            return super().execute(sql, parameters)

    original_connect = sqlite3.connect

    def guarded_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        kwargs["factory"] = GuardedConnection
        return original_connect(*args, **kwargs)

    monkeypatch.setattr("scripts.storage_migration_readiness_report.sqlite3.connect", guarded_connect)

    report = build_report(sqlite_db=db_path)

    assert report["mutationsExecuted"] is False
    assert executed
    assert all(MUTATION_SQL_RE.search(statement) is None for statement in executed)


def test_cli_returns_valid_json_and_default_does_not_fail_on_risk(tmp_path: Path) -> None:
    db_path = tmp_path / "cli.db"
    _create_quota_fixture(db_path)
    with _connect(db_path) as conn:
        _insert_window(conn, identity="")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--sqlite-db", str(db_path)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["readOnly"] is True
    assert payload["mutationsExecuted"] is False
    assert payload["overallRisk"] == "high"
    assert str(db_path) not in result.stdout + result.stderr


def test_cli_fail_on_risk_returns_nonzero(tmp_path: Path) -> None:
    db_path = tmp_path / "cli-fail.db"
    _create_quota_fixture(db_path)
    with _connect(db_path) as conn:
        _insert_window(conn, identity="")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--sqlite-db", str(db_path), "--fail-on-risk"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["summary"]["highRiskFindingCount"] == 1


def test_cli_fail_on_risk_returns_nonzero_for_partial_evidence(tmp_path: Path) -> None:
    evidence_path = tmp_path / "pg-schema-evidence.txt"
    evidence_path.write_text("quota_usage_windows\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--postgres-schema-evidence",
            str(evidence_path),
            "--fail-on-risk",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["summary"]["highRiskFindingCount"] == 0
    assert payload["summary"]["mediumRiskFindingCount"] == 1
    assert str(evidence_path) not in result.stdout + result.stderr
