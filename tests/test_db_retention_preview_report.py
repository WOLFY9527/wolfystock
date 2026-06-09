# -*- coding: utf-8 -*-
"""Tests for the report-only DB retention preview helper."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from scripts.db_retention_preview_report import POLICY_VERSION, build_report


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "db_retention_preview_report.py"


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _create_preview_fixture(path: Path) -> None:
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE execution_log_sessions (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                started_at TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE execution_log_events (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                event_at TEXT,
                detail_json TEXT
            );
            CREATE TABLE durable_task_states (
                id INTEGER PRIMARY KEY,
                task_id TEXT,
                owner_user_id TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE durable_task_progress_events (
                id INTEGER PRIMARY KEY,
                task_id TEXT,
                owner_user_id TEXT,
                created_at TEXT,
                metadata_json TEXT
            );
            CREATE TABLE llm_cost_ledger (
                id INTEGER PRIMARY KEY,
                ledger_id TEXT,
                owner_user_id TEXT,
                guest_bucket_hash TEXT,
                total_tokens INTEGER,
                metadata_json TEXT,
                created_at TEXT
            );
            CREATE TABLE provider_quota_windows (
                id INTEGER PRIMARY KEY,
                guest_bucket_hash TEXT,
                provider TEXT,
                window_start TEXT,
                created_at TEXT,
                updated_at TEXT,
                metadata_json TEXT
            );
            CREATE TABLE provider_circuit_events (
                id INTEGER PRIMARY KEY,
                provider TEXT,
                reason_bucket TEXT,
                metadata_json TEXT,
                created_at TEXT
            );
            CREATE TABLE provider_probe_events (
                id INTEGER PRIMARY KEY,
                provider TEXT,
                result_bucket TEXT,
                metadata_json TEXT,
                created_at TEXT
            );
            CREATE TABLE market_scanner_runs (
                id INTEGER PRIMARY KEY,
                owner_id TEXT,
                run_at TEXT,
                completed_at TEXT,
                diagnostics_json TEXT
            );
            CREATE TABLE market_scanner_candidates (
                id INTEGER PRIMARY KEY,
                run_id INTEGER,
                symbol TEXT,
                score REAL,
                created_at TEXT,
                reasons_json TEXT
            );
            CREATE TABLE rule_backtest_runs (
                id INTEGER PRIMARY KEY,
                owner_id TEXT,
                code TEXT,
                run_at TEXT,
                summary_json TEXT
            );
            CREATE TABLE rule_backtest_trades (
                id INTEGER PRIMARY KEY,
                run_id INTEGER,
                code TEXT,
                entry_date TEXT,
                notes TEXT
            );
            CREATE TABLE auth_rate_limit_buckets (
                id INTEGER PRIMARY KEY,
                bucket_key TEXT,
                expires_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE guest_sessions (
                id INTEGER PRIMARY KEY,
                guest_bucket_hash TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE portfolio_accounts (
                id INTEGER PRIMARY KEY,
                owner_id TEXT,
                name TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE portfolio_trades (
                id INTEGER PRIMARY KEY,
                account_id INTEGER,
                symbol TEXT,
                trade_date TEXT,
                note TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO execution_log_sessions VALUES (1, 'session-1', '2025-12-31T00:00:00Z', '2025-12-31T00:00:00Z', '2025-12-31T00:02:00Z')"
        )
        conn.execute(
            "INSERT INTO execution_log_events VALUES (1, 'session-1', '2025-12-31T00:01:00Z', ?)",
            (json.dumps({"token": "secret"}),),
        )
        conn.execute(
            "INSERT INTO durable_task_states VALUES (1, 'task-1', 'owner-secret', '2026-01-01T00:00:00Z', '2026-01-02T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO durable_task_progress_events VALUES (1, 'task-1', 'owner-secret', '2026-01-01T00:01:00Z', ?)",
            (json.dumps({"token": "sk-test-secret", "raw_payload": {"x": 1}}),),
        )
        conn.execute(
            "INSERT INTO llm_cost_ledger VALUES (1, 'ledger-1', 'owner-secret', 'guest-secret', 100, ?, '2026-02-01T00:00:00Z')",
            (json.dumps({"cookie": "session=secret", "safe": "ok"}),),
        )
        conn.execute(
            "INSERT INTO provider_quota_windows VALUES (1, 'guest-secret', 'fmp', '2026-03-01T00:00:00Z', '2026-03-01T00:00:00Z', '2026-03-01T01:00:00Z', ?)",
            (json.dumps({"raw_response": "token=secret"}),),
        )
        conn.execute(
            "INSERT INTO provider_circuit_events VALUES (1, 'fmp', 'provider_429', ?, '2026-03-02T00:00:00Z')",
            (json.dumps({"authorization": "Bearer secret"}),),
        )
        conn.execute(
            "INSERT INTO provider_probe_events VALUES (1, 'tavily', 'provider_403', ?, '2026-03-03T00:00:00Z')",
            (json.dumps({"api_key": "secret"}),),
        )
        conn.execute(
            "INSERT INTO market_scanner_runs VALUES (1, 'owner-secret', '2026-04-01T00:00:00Z', '2026-04-01T00:10:00Z', ?)",
            (json.dumps({"raw_payload": "secret"}),),
        )
        conn.execute(
            "INSERT INTO market_scanner_candidates VALUES (1, 1, 'ORCL', 91.2, '2026-04-01T00:01:00Z', ?)",
            (json.dumps({"token": "secret"}),),
        )
        conn.execute(
            "INSERT INTO rule_backtest_runs VALUES (1, 'owner-secret', 'ORCL', '2026-05-01T00:00:00Z', ?)",
            (json.dumps({"raw_payload": "secret"}),),
        )
        conn.execute(
            "INSERT INTO rule_backtest_trades VALUES (1, 1, 'ORCL', '2026-05-02', 'token=secret')"
        )
        conn.execute(
            "INSERT INTO auth_rate_limit_buckets VALUES (1, 'guest-secret', '2026-06-01T00:00:00Z', '2026-05-31T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO guest_sessions VALUES (1, 'guest-secret', '2026-05-30T00:00:00Z', '2026-05-31T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO portfolio_accounts VALUES (1, 'owner-secret', 'Private account', '2026-01-01T00:00:00Z', '2026-01-02T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO portfolio_trades VALUES (1, 1, 'ORCL', '2026-01-03', 'private row note token=secret', '2026-01-03T00:00:00Z', '2026-01-04T00:00:00Z')"
        )


def _domain(report: dict[str, object], name: str) -> dict[str, object]:
    domains = report["domains"]
    assert isinstance(domains, list)
    for item in domains:
        assert isinstance(item, dict)
        if item["domain"] == name:
            return item
    raise AssertionError(f"domain not found: {name}")


def test_default_report_is_policy_only_and_destructive_actions_are_disabled() -> None:
    report = build_report()

    assert report["policyVersion"] == POLICY_VERSION
    assert report["mode"] == "report_only"
    assert report["dryRun"] is True
    assert report["deleteAllowed"] is False
    assert report["databaseInspected"] is False
    assert report["databasePathIncluded"] is False
    assert report["safety"]["destructiveSqlAllowed"] is False
    assert all(domain["deleteAllowed"] is False for domain in report["domains"])
    assert all(domain["directCleanupAllowed"] is False for domain in report["domains"])
    assert all("ownerJoinStrategy" in domain for domain in report["domains"])
    assert {domain["domain"] for domain in report["domains"]} >= {
        "admin_log_existing_retention_domain",
        "durable_task_state_progress",
        "llm_usage_cost_ledger",
        "provider_quota_circuit_probe_events",
        "scanner_watchlist_backtest_artifacts",
        "guest_cache_metadata",
        "future_options_cache",
        "portfolio_source_of_truth_protected",
    }


def test_sqlite_preview_counts_only_aggregates_and_does_not_mutate_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "preview.db"
    _create_preview_fixture(db_path)

    report = build_report(sqlite_db=db_path)

    assert report["databaseInspected"] is True
    assert report["databaseSource"] == "operator_supplied_sqlite_path"
    admin_logs = _domain(report, "admin_log_existing_retention_domain")
    assert admin_logs["matchedRowCount"] == 2
    assert admin_logs["oldestCreatedAt"] == "2025-12-31T00:00:00Z"
    assert admin_logs["newestCreatedAt"] == "2025-12-31T00:01:00Z"
    durable = _domain(report, "durable_task_state_progress")
    assert durable["matchedRowCount"] == 2
    assert durable["oldestCreatedAt"] == "2026-01-01T00:00:00Z"
    assert durable["newestCreatedAt"] == "2026-01-01T00:01:00Z"
    llm = _domain(report, "llm_usage_cost_ledger")
    assert llm["matchedRowCount"] == 1
    provider = _domain(report, "provider_quota_circuit_probe_events")
    assert provider["matchedRowCount"] == 3

    with _connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM durable_task_progress_events").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM portfolio_trades").fetchone()[0] == 1


def test_portfolio_source_of_truth_is_explicitly_protected(tmp_path: Path) -> None:
    db_path = tmp_path / "preview.db"
    _create_preview_fixture(db_path)

    portfolio = _domain(build_report(sqlite_db=db_path), "portfolio_source_of_truth_protected")

    assert portfolio["matchedRowCount"] == 2
    assert portfolio["deleteAllowed"] is False
    assert portfolio["directCleanupAllowed"] is False
    reasons = set(portfolio["protectedRowReasons"])
    assert "portfolio_accounting_source_of_truth_protected" in reasons
    assert "portfolio_cash_holdings_pnl_fx_cost_basis_protected" in reasons
    assert "no_ttl_or_cleanup_behavior_allowed" in reasons


def test_leaf_tables_are_reported_as_parent_join_protected(tmp_path: Path) -> None:
    db_path = tmp_path / "preview.db"
    _create_preview_fixture(db_path)

    report = build_report(sqlite_db=db_path)
    durable = _domain(report, "durable_task_state_progress")
    scanner = _domain(report, "scanner_watchlist_backtest_artifacts")

    assert durable["leafTablesRequireParentJoin"] is True
    assert durable["ownerJoinStrategy"] == "domain_parent_join_required_for_leaf_tables"
    assert scanner["leafTablesRequireParentJoin"] is True
    assert scanner["ownerJoinStrategy"] == "domain_parent_join_required_for_leaf_tables"
    reasons = set(durable["protectedRowReasons"]) | set(scanner["protectedRowReasons"])
    assert "leaf_table_requires_parent_join:durable_task_progress_events" in reasons
    assert "parent_table_required:durable_task_progress_events->durable_task_states" in reasons
    assert "leaf_table_requires_parent_join:market_scanner_candidates" in reasons
    assert "leaf_table_requires_parent_join:rule_backtest_trades" in reasons


def test_cli_output_is_sanitized_and_does_not_emit_path_or_row_values(tmp_path: Path) -> None:
    db_path = tmp_path / "secret-token-preview.db"
    _create_preview_fixture(db_path)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--sqlite-db", str(db_path)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["deleteAllowed"] is False
    combined = result.stdout + result.stderr
    forbidden_fragments = [
        str(db_path),
        "owner-secret",
        "guest-secret",
        "Private account",
        "sk-test-secret",
        "session=secret",
        "Bearer secret",
        "private row note",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in combined
