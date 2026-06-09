#!/usr/bin/env python3
"""Report-only DB retention preview for high-growth WolfyStock domains.

The helper is intentionally inert: it reads only SQLite catalog/count metadata
when an operator supplies a local database file and otherwise emits a conceptual
policy report. It never deletes rows, updates rows, vacuums storage, reads env
files, prints DSNs, or emits row-level/user payload data.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


POLICY_VERSION = "wolfystock_db_retention_preview_v1"
REPORT_MODE = "report_only"
SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DESTRUCTIVE_SQL_RE = re.compile(
    r"\b(delete|update|vacuum|drop|truncate|alter|insert|replace|create)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TablePolicy:
    name: str
    timestamp_columns: tuple[str, ...] = ("created_at",)
    requires_parent_join: bool = False
    parent_table: str | None = None
    protected_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class DomainPolicy:
    domain: str
    owner_scope: str
    tables: tuple[TablePolicy, ...]
    protected_reasons: tuple[str, ...] = ()


DOMAIN_POLICIES: tuple[DomainPolicy, ...] = (
    DomainPolicy(
        domain="admin_log_existing_retention_domain",
        owner_scope="admin_ops_system_scope",
        protected_reasons=(
            "admin_logs_are_only_existing_real_retention_domain",
            "report_does_not_call_admin_log_cleanup",
        ),
        tables=(
            TablePolicy("execution_log_sessions", ("created_at", "started_at", "updated_at")),
            TablePolicy(
                "execution_log_events",
                ("event_at",),
                requires_parent_join=True,
                parent_table="execution_log_sessions",
            ),
            TablePolicy("execution_sessions", ("created_at", "started_at", "updated_at")),
            TablePolicy(
                "execution_events",
                ("occurred_at",),
                requires_parent_join=True,
                parent_table="execution_sessions",
            ),
            TablePolicy("admin_logs", ("occurred_at", "created_at")),
            TablePolicy("system_actions", ("created_at", "completed_at")),
        ),
    ),
    DomainPolicy(
        domain="durable_task_state_progress",
        owner_scope="owner_scoped_user",
        protected_reasons=("report_only_no_cleanup_policy",),
        tables=(
            TablePolicy("durable_task_states", ("created_at", "updated_at", "started_at", "completed_at")),
            TablePolicy(
                "durable_task_progress_events",
                ("created_at",),
                requires_parent_join=True,
                parent_table="durable_task_states",
            ),
        ),
    ),
    DomainPolicy(
        domain="llm_usage_cost_ledger",
        owner_scope="owner_guest_or_system_aggregate",
        protected_reasons=("cost_accounting_preview_only", "no_invoice_or_quota_enforcement_change"),
        tables=(
            TablePolicy("llm_cost_ledger", ("created_at",)),
            TablePolicy("llm_usage", ("called_at",)),
            TablePolicy("quota_usage_windows", ("window_start", "updated_at")),
            TablePolicy("quota_reservations", ("created_at", "updated_at", "expires_at")),
        ),
    ),
    DomainPolicy(
        domain="provider_quota_circuit_probe_events",
        owner_scope="owner_guest_or_system_aggregate",
        protected_reasons=("provider_runtime_behavior_protected", "circuit_state_not_mutated"),
        tables=(
            TablePolicy("provider_quota_windows", ("window_start", "created_at", "updated_at")),
            TablePolicy("provider_circuit_events", ("created_at",)),
            TablePolicy("provider_probe_events", ("created_at",)),
            TablePolicy(
                "provider_circuit_states",
                ("created_at", "updated_at"),
                protected_reasons=("current_provider_circuit_state_protected",),
            ),
        ),
    ),
    DomainPolicy(
        domain="scanner_watchlist_backtest_artifacts",
        owner_scope="owner_or_system_artifact",
        protected_reasons=("scanner_backtest_semantics_protected", "artifact_preview_only"),
        tables=(
            TablePolicy("market_scanner_runs", ("run_at", "completed_at")),
            TablePolicy(
                "market_scanner_candidates",
                ("created_at",),
                requires_parent_join=True,
                parent_table="market_scanner_runs",
            ),
            TablePolicy("scanner_runs", ("created_at", "completed_at")),
            TablePolicy(
                "scanner_candidates",
                ("created_at",),
                requires_parent_join=True,
                parent_table="scanner_runs",
            ),
            TablePolicy("watchlists", ("created_at", "updated_at")),
            TablePolicy(
                "watchlist_items",
                ("created_at",),
                requires_parent_join=True,
                parent_table="watchlists",
            ),
            TablePolicy("backtest_runs", ("run_at", "created_at", "started_at", "completed_at")),
            TablePolicy(
                "backtest_artifacts",
                ("created_at",),
                requires_parent_join=True,
                parent_table="backtest_runs",
            ),
            TablePolicy("backtest_results", ("evaluated_at",)),
            TablePolicy("backtest_summaries", ("computed_at",)),
            TablePolicy("rule_backtest_runs", ("run_at",)),
            TablePolicy(
                "rule_backtest_trades",
                ("entry_date", "exit_date"),
                requires_parent_join=True,
                parent_table="rule_backtest_runs",
            ),
            TablePolicy("rule_backtest_universe_jobs", ("created_at", "updated_at")),
            TablePolicy(
                "rule_backtest_universe_symbol_results",
                ("created_at", "updated_at"),
                requires_parent_join=True,
                parent_table="rule_backtest_universe_jobs",
            ),
            TablePolicy(
                "user_watchlist_items",
                ("created_at", "updated_at"),
                protected_reasons=("user_watchlist_source_state_protected",),
            ),
            TablePolicy("user_alert_events", ("created_at",)),
            TablePolicy(
                "user_alert_rules",
                ("created_at", "updated_at"),
                protected_reasons=("user_alert_rule_source_state_protected",),
            ),
        ),
    ),
    DomainPolicy(
        domain="guest_cache_metadata",
        owner_scope="guest_or_cache_aggregate",
        protected_reasons=("cache_ttl_semantics_protected", "auth_session_behavior_protected"),
        tables=(
            TablePolicy("guest_sessions", ("created_at", "updated_at")),
            TablePolicy("auth_rate_limit_buckets", ("expires_at", "updated_at", "created_at")),
            TablePolicy("conversation_sessions", ("created_at", "updated_at")),
            TablePolicy(
                "conversation_messages",
                ("created_at",),
                requires_parent_join=True,
                parent_table="conversation_sessions",
            ),
            TablePolicy(
                "stock_daily",
                ("date", "created_at"),
                protected_reasons=("market_data_cache_source_semantics_protected",),
            ),
            TablePolicy(
                "news_intel",
                ("date", "created_at"),
                protected_reasons=("news_cache_source_semantics_protected",),
            ),
            TablePolicy(
                "fundamental_snapshot",
                ("created_at",),
                protected_reasons=("fundamental_snapshot_source_semantics_protected",),
            ),
            TablePolicy(
                "market_overview_snapshots",
                ("created_at",),
                protected_reasons=("market_overview_snapshot_source_semantics_protected",),
            ),
        ),
    ),
    DomainPolicy(
        domain="future_options_cache",
        owner_scope="future_options_cache_aggregate",
        protected_reasons=(
            "future_domain_no_cleanup_policy",
            "options_ranking_gates_recommendation_policy_protected",
        ),
        tables=(
            TablePolicy("options_cache_entries", ("created_at", "updated_at")),
            TablePolicy("options_chain_cache", ("created_at", "updated_at")),
            TablePolicy("options_quote_cache", ("created_at", "updated_at")),
            TablePolicy("options_strategy_cache", ("created_at", "updated_at")),
        ),
    ),
    DomainPolicy(
        domain="portfolio_source_of_truth_protected",
        owner_scope="owner_scoped_source_of_truth",
        protected_reasons=(
            "portfolio_accounting_source_of_truth_protected",
            "portfolio_cash_holdings_pnl_fx_cost_basis_protected",
            "no_ttl_or_cleanup_behavior_allowed",
        ),
        tables=(
            TablePolicy("portfolio_accounts", ("created_at", "updated_at")),
            TablePolicy("portfolio_broker_connections", ("created_at", "updated_at")),
            TablePolicy("portfolio_broker_sync_states", ("created_at", "updated_at", "synced_at")),
            TablePolicy(
                "portfolio_broker_sync_positions",
                ("created_at", "updated_at"),
                requires_parent_join=True,
                parent_table="portfolio_broker_sync_states",
            ),
            TablePolicy(
                "portfolio_broker_sync_cash_balances",
                ("created_at", "updated_at"),
                requires_parent_join=True,
                parent_table="portfolio_broker_sync_states",
            ),
            TablePolicy("portfolio_trades", ("created_at", "updated_at", "trade_date")),
            TablePolicy("portfolio_cash_ledger", ("created_at", "event_date")),
            TablePolicy("portfolio_corporate_actions", ("created_at", "effective_date")),
            TablePolicy("portfolio_positions", ("updated_at",)),
            TablePolicy(
                "portfolio_position_lots",
                ("updated_at", "open_date"),
                requires_parent_join=True,
                parent_table="portfolio_positions",
            ),
            TablePolicy("portfolio_daily_snapshots", ("created_at", "updated_at", "snapshot_date")),
            TablePolicy("portfolio_fx_rates", ("updated_at", "rate_date")),
        ),
    ),
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _quote_identifier(identifier: str) -> str:
    if not SAFE_IDENTIFIER_RE.fullmatch(identifier):
        raise ValueError("unsafe SQL identifier")
    return f'"{identifier}"'


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = _execute_readonly(conn, "SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {str(row[0]) for row in rows if row and isinstance(row[0], str)}


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    quoted = _quote_identifier(table_name)
    rows = _execute_readonly(conn, f"PRAGMA table_info({quoted})").fetchall()
    return {str(row[1]) for row in rows if len(row) > 1 and row[1]}


def _first_existing_column(columns: set[str], candidates: Iterable[str]) -> str | None:
    for column in candidates:
        if column in columns:
            return column
    return None


def _count_rows(conn: sqlite3.Connection, table_name: str) -> int:
    quoted = _quote_identifier(table_name)
    row = _execute_readonly(conn, f"SELECT COUNT(*) FROM {quoted}").fetchone()
    return int(row[0] or 0) if row else 0


def _timestamp_bounds(conn: sqlite3.Connection, table_name: str, column_name: str) -> tuple[str | None, str | None]:
    quoted_table = _quote_identifier(table_name)
    quoted_column = _quote_identifier(column_name)
    row = _execute_readonly(conn, f"SELECT MIN({quoted_column}), MAX({quoted_column}) FROM {quoted_table}").fetchone()
    if not row:
        return None, None
    return _clean_scalar(row[0]), _clean_scalar(row[1])


def _clean_scalar(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:64] if text else None


def _merge_bounds(current: tuple[str | None, str | None], incoming: tuple[str | None, str | None]) -> tuple[str | None, str | None]:
    current_oldest, current_newest = current
    incoming_oldest, incoming_newest = incoming
    oldest = min(value for value in (current_oldest, incoming_oldest) if value) if (current_oldest or incoming_oldest) else None
    newest = max(value for value in (current_newest, incoming_newest) if value) if (current_newest or incoming_newest) else None
    return oldest, newest


def _estimate_bytes(conn: sqlite3.Connection, table_names: Iterable[str]) -> int | None:
    safe_names = sorted({name for name in table_names if SAFE_IDENTIFIER_RE.fullmatch(name)})
    if not safe_names:
        return None
    placeholders = ",".join("?" for _ in safe_names)
    try:
        rows = _execute_readonly(
            conn,
            f"SELECT SUM(pgsize) FROM dbstat WHERE name IN ({placeholders})",
            safe_names,
        ).fetchone()
    except sqlite3.DatabaseError:
        return None
    if not rows or rows[0] is None:
        return None
    try:
        return max(0, int(rows[0]))
    except (TypeError, ValueError):
        return None


def _preview_domain(conn: sqlite3.Connection | None, domain_policy: DomainPolicy) -> dict[str, Any]:
    existing_tables = _table_names(conn) if conn is not None else set()
    matched_row_count = 0
    bounds: tuple[str | None, str | None] = (None, None)
    inspected_tables: list[str] = []
    missing_tables: list[str] = []
    protected_reasons = set(domain_policy.protected_reasons)
    leaf_table_names: list[str] = []

    for table_policy in domain_policy.tables:
        if table_policy.protected_reasons:
            protected_reasons.update(table_policy.protected_reasons)
        if table_policy.requires_parent_join:
            leaf_table_names.append(table_policy.name)
            protected_reasons.add(f"leaf_table_requires_parent_join:{table_policy.name}")
            if table_policy.parent_table:
                protected_reasons.add(f"parent_table_required:{table_policy.name}->{table_policy.parent_table}")

        if conn is None:
            missing_tables.append(table_policy.name)
            continue
        if table_policy.name not in existing_tables:
            missing_tables.append(table_policy.name)
            continue

        inspected_tables.append(table_policy.name)
        columns = _table_columns(conn, table_policy.name)
        matched_row_count += _count_rows(conn, table_policy.name)
        timestamp_column = _first_existing_column(columns, table_policy.timestamp_columns)
        if timestamp_column is not None:
            bounds = _merge_bounds(bounds, _timestamp_bounds(conn, table_policy.name, timestamp_column))
        else:
            protected_reasons.add(f"timestamp_column_missing:{table_policy.name}")

    if conn is None:
        protected_reasons.add("database_not_supplied")
    elif missing_tables:
        protected_reasons.add("some_expected_tables_missing")

    return {
        "policyVersion": POLICY_VERSION,
        "domain": domain_policy.domain,
        "ownerScope": domain_policy.owner_scope,
        "matchedRowCount": matched_row_count,
        "oldestCreatedAt": bounds[0],
        "newestCreatedAt": bounds[1],
        "protectedRowReasons": sorted(protected_reasons),
        "estimatedBytes": _estimate_bytes(conn, inspected_tables) if conn is not None else None,
        "deleteAllowed": False,
        "directCleanupAllowed": False,
        "leafTablesRequireParentJoin": bool(leaf_table_names),
        "ownerJoinStrategy": (
            "domain_parent_join_required_for_leaf_tables"
            if leaf_table_names
            else "aggregate_table_scope_only"
        ),
        "matchedTableCount": len(inspected_tables),
        "missingTableCount": len(missing_tables),
        "tablesInspected": inspected_tables,
        "leafTables": leaf_table_names,
    }


def build_report(sqlite_db: Path | None = None) -> dict[str, Any]:
    conn: sqlite3.Connection | None = None
    try:
        if sqlite_db is not None:
            conn = _open_sqlite_readonly(sqlite_db)
        domains = [_preview_domain(conn, policy) for policy in DOMAIN_POLICIES]
    finally:
        if conn is not None:
            conn.close()

    return {
        "policyVersion": POLICY_VERSION,
        "mode": REPORT_MODE,
        "dryRun": True,
        "deleteAllowed": False,
        "generatedAt": _utc_now_iso(),
        "databaseInspected": sqlite_db is not None,
        "databaseSource": "operator_supplied_sqlite_path" if sqlite_db is not None else "not_supplied",
        "databasePathIncluded": False,
        "domains": domains,
        "safety": {
            "reportOnly": True,
            "readOnlyConnection": sqlite_db is not None,
            "destructiveSqlAllowed": False,
            "rowLevelDataIncluded": False,
            "rawPayloadIncluded": False,
            "dsnTokenCookieIncluded": False,
            "portfolioSourceOfTruthProtected": True,
            "leafTablesRequireParentJoin": True,
            "adminLogCleanupPathAdded": False,
            "restoreOrPitrExecutionAdded": False,
        },
    }


def _open_sqlite_readonly(path: Path) -> sqlite3.Connection:
    if not path.exists() or not path.is_file():
        raise SystemExit("[FAIL] SQLite database file is required for inspection")
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.set_trace_callback(_guard_sql_trace)
    return conn


def _execute_readonly(
    conn: sqlite3.Connection,
    statement: str,
    parameters: Iterable[Any] = (),
) -> sqlite3.Cursor:
    _guard_sql_trace(statement)
    return conn.execute(statement, tuple(parameters))


def _guard_sql_trace(statement: str) -> None:
    if DESTRUCTIVE_SQL_RE.search(statement):
        raise RuntimeError("destructive SQL is forbidden in retention preview")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Emit a sanitized, report-only DB retention preview for high-growth WolfyStock domains.",
    )
    parser.add_argument(
        "--sqlite-db",
        type=Path,
        help="Optional SQLite database file to inspect using a read-only connection. The path is never emitted.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(argv or sys.argv[1:]))
    report = build_report(sqlite_db=args.sqlite_db)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
