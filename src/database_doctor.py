# -*- coding: utf-8 -*-
"""Compact database doctor/support bundle for SQLite-primary + PG coexistence runtime."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from src.config import Config, get_config
from src.postgres_analysis_chat_store import PostgresPhaseBStore
from src.postgres_backtest_store import PostgresPhaseEStore
from src.postgres_control_plane_store import PostgresPhaseGStore
from src.postgres_identity_store import PostgresPhaseAStore
from src.postgres_market_metadata_store import PostgresPhaseCStore
from src.postgres_portfolio_coexistence_store import PostgresPhaseFStore
from src.postgres_scanner_watchlist_store import PostgresPhaseDStore
from src.postgres_store_utils import probe_engine_connection, redact_database_url
from src.storage import DatabaseManager

_ROOT_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_MARKDOWN_OUTPUT = _ROOT_DIR / "tmp" / "database-doctor-report.md"
_DEFAULT_JSON_OUTPUT = _ROOT_DIR / "tmp" / "database-doctor-report.json"
_DEFAULT_REAL_PG_MARKDOWN_OUTPUT = _ROOT_DIR / "tmp" / "database-real-pg-bundle.md"
_DEFAULT_REAL_PG_JSON_OUTPUT = _ROOT_DIR / "tmp" / "database-real-pg-bundle.json"
_REAL_PG_TEMP_SQLITE_PLACEHOLDER = "<temporary>/database-real-pg-bundle.sqlite"
_REAL_PG_PROBE_SESSION_PLACEHOLDER = "<latest_probe_session_id>"
_REAL_PG_BOOTSTRAP_APPLIED_AT_PLACEHOLDER = "<bootstrap_applied_at>"

_URL_TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s]+")
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b([a-z0-9_]*(?:token|secret|password|api_key)[a-z0-9_]*)=([^\s,;]+)"
)
_SECRET_JSON_PATTERN = re.compile(
    r'(?i)("?[a-z0-9_]*(?:token|secret|password|api_key)[a-z0-9_]*"?\s*:\s*")[^"]*(")'
)

_STORE_SPECS = (
    {
        "phase": "phase_a",
        "label": "Phase A identity/preferences",
        "domain": "identity_preferences",
        "class": PostgresPhaseAStore,
        "module_path": "src/postgres_identity_store.py",
    },
    {
        "phase": "phase_b",
        "label": "Phase B analysis/chat",
        "domain": "analysis_chat",
        "class": PostgresPhaseBStore,
        "module_path": "src/postgres_analysis_chat_store.py",
    },
    {
        "phase": "phase_c",
        "label": "Phase C market metadata",
        "domain": "market_metadata",
        "class": PostgresPhaseCStore,
        "module_path": "src/postgres_market_metadata_store.py",
    },
    {
        "phase": "phase_d",
        "label": "Phase D scanner/watchlist",
        "domain": "scanner_watchlist",
        "class": PostgresPhaseDStore,
        "module_path": "src/postgres_scanner_watchlist_store.py",
    },
    {
        "phase": "phase_e",
        "label": "Phase E backtest",
        "domain": "backtest",
        "class": PostgresPhaseEStore,
        "module_path": "src/postgres_backtest_store.py",
    },
    {
        "phase": "phase_f",
        "label": "Phase F portfolio coexistence",
        "domain": "portfolio_coexistence",
        "class": PostgresPhaseFStore,
        "module_path": "src/postgres_portfolio_coexistence_store.py",
    },
    {
        "phase": "phase_g",
        "label": "Phase G control plane",
        "domain": "control_plane",
        "class": PostgresPhaseGStore,
        "module_path": "src/postgres_control_plane_store.py",
    },
)

_STORE_SPEC_BY_PHASE = {item["phase"]: item for item in _STORE_SPECS}

_BASE_READ_FIRST = [
    "src/storage.py",
    "src/storage_postgres_bridge.py",
    "src/storage_topology_report.py",
    "src/storage_phase_g_observability.py",
    "src/config.py",
    "src/postgres_schema_bootstrap.py",
]


def _sanitize_text(value: Any) -> str:
    text = str(value or "")
    if not text:
        return text

    for token in sorted(set(_URL_TOKEN_PATTERN.findall(text)), key=len, reverse=True):
        trimmed = token.rstrip("),.;")
        suffix = token[len(trimmed):]
        text = text.replace(token, f"{redact_database_url(trimmed)}{suffix}")

    text = _SECRET_ASSIGNMENT_PATTERN.sub(r"\1=***", text)
    text = _SECRET_JSON_PATTERN.sub(r"\1***\2", text)
    return text


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"


def _resolve_sqlite_path(database_path: str) -> Path:
    raw_path = Path(str(database_path or "").strip() or "./data/stock_analysis.db")
    if raw_path.is_absolute():
        return raw_path
    return (_ROOT_DIR / raw_path).resolve()


def _probe_sqlite_path(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "ok": False,
            "error": "SQLite database file does not exist yet.",
        }
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            conn.execute("select 1")
        finally:
            conn.close()
        return {
            "ok": True,
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{exc.__class__.__name__}: {exc}",
        }


def _build_sqlite_primary_report(
    *,
    config,
    db: DatabaseManager | None,
) -> dict[str, Any]:
    resolved_path = _resolve_sqlite_path(getattr(config, "database_path", ""))
    if db is not None:
        reachable = probe_engine_connection(db._engine)
    else:
        raw_probe = _probe_sqlite_path(resolved_path)
        reachable = {
            "requested": True,
            "ok": raw_probe["ok"],
            "error": raw_probe["error"],
        }
    return {
        "runtime_role": "primary_runtime",
        "configured_path": str(getattr(config, "database_path", "")),
        "resolved_path": str(resolved_path),
        "path_exists": resolved_path.exists(),
        "reachable": reachable,
    }


def _phase_f_allowlist_interpretation(*, feature_key: str, enabled: bool, account_ids: list[int]) -> str:
    if not enabled:
        return "disabled"
    if feature_key == "trades_list":
        return (
            "enabled with explicit allowlist; bounded to listed account ids"
            if account_ids
            else "enabled with empty allowlist; comparison may run broadly"
        )
    return (
        "enabled with explicit allowlist; bounded to listed account ids"
        if account_ids
        else "enabled but effectively skipped until account ids are allowlisted"
    )


def _build_phase_f_mode(config: Any, topology: dict[str, Any] | None) -> dict[str, Any]:
    comparisons = {}
    for feature_key, enabled_attr, ids_attr in (
        (
            "trades_list",
            "enable_phase_f_trades_list_comparison",
            "phase_f_trades_list_comparison_account_ids",
        ),
        (
            "cash_ledger",
            "enable_phase_f_cash_ledger_comparison",
            "phase_f_cash_ledger_comparison_account_ids",
        ),
        (
            "corporate_actions",
            "enable_phase_f_corporate_actions_comparison",
            "phase_f_corporate_actions_comparison_account_ids",
        ),
    ):
        enabled = bool(getattr(config, enabled_attr, False))
        account_ids = sorted(
            {int(item) for item in list(getattr(config, ids_attr, []) or []) if item is not None}
        )
        comparisons[feature_key] = {
            "enabled": enabled,
            "allowlisted_account_ids": account_ids,
            "allowlist_interpretation": _phase_f_allowlist_interpretation(
                feature_key=feature_key,
                enabled=enabled,
                account_ids=account_ids,
            ),
        }

    return {
        "mode": (
            topology["stores"]["phase_f"]["mode"]
            if topology is not None
            else getattr(PostgresPhaseFStore, "MODE", "comparison_only_shadow")
        ),
        "serving_truth": "sqlite",
        "postgres_role": "comparison_only_shadow",
        "serving_semantics": (
            topology["serving_semantics"]["phase_f"]
            if topology is not None
            else "legacy_serving_pg_comparison_only"
        ),
        "comparisons": comparisons,
    }


def _phase_f_effective_account_scope(*, feature_key: str, enabled: bool, account_ids: list[int]) -> str:
    if not enabled:
        return "no_accounts"
    if account_ids:
        return "allowlisted_accounts_only"
    if feature_key == "trades_list":
        return "all_requested_accounts"
    return "no_accounts"


def _phase_f_empty_allowlist_behavior(*, feature_key: str) -> str:
    if feature_key == "trades_list":
        return "comparison_may_run_broadly"
    return "comparison_skipped"


def _build_phase_f_authority_summary(config: Any, phase_f_mode: dict[str, Any]) -> dict[str, Any]:
    features: dict[str, Any] = {}
    non_empty_sets: dict[str, list[int]] = {}

    for feature_key in ("trades_list", "cash_ledger", "corporate_actions"):
        feature = dict(phase_f_mode["comparisons"][feature_key])
        allowlisted_account_ids = sorted(
            {int(item) for item in list(feature.get("allowlisted_account_ids") or []) if item is not None}
        )
        enabled = bool(feature.get("enabled"))
        feature_summary = {
            "enabled": enabled,
            "allowlisted_account_ids": allowlisted_account_ids,
            "allowlist_required_when_enabled": feature_key != "trades_list",
            "effective_account_scope": _phase_f_effective_account_scope(
                feature_key=feature_key,
                enabled=enabled,
                account_ids=allowlisted_account_ids,
            ),
            "empty_allowlist_behavior": _phase_f_empty_allowlist_behavior(feature_key=feature_key),
            "allowlist_interpretation": feature.get("allowlist_interpretation"),
            "comparison_only": True,
            "serving_truth": "sqlite",
            "postgres_role": "comparison_only_shadow",
            "non_empty_restriction_sets": (
                {"allowlisted_account_ids": allowlisted_account_ids}
                if allowlisted_account_ids
                else {}
            ),
        }
        features[feature_key] = feature_summary
        if allowlisted_account_ids:
            non_empty_sets[f"{feature_key}.allowlisted_account_ids"] = allowlisted_account_ids

    return {
        "summary_model": "phase_f_authority_permission_summary_v1",
        "comparison_mode": phase_f_mode["mode"],
        "serving_truth": phase_f_mode["serving_truth"],
        "postgres_role": phase_f_mode["postgres_role"],
        "request_actor_scope": {
            "permission_model": "legacy_owner_scope",
            "allowed_roles": ["admin", "user"],
            "owner_scope_enforced_at_api": True,
            "comparison_specific_role_gate": False,
            "note": (
                "Comparison diagnostics do not introduce a new role gate. "
                "Portfolio APIs remain authenticated owner-scoped, and comparison-only probes follow the same owner-scoped request path."
            ),
        },
        "features": features,
        "non_empty_sets": non_empty_sets,
        "feature_flag_env_vars": {
            "trades_list": {
                "enabled": "ENABLE_PHASE_F_TRADES_LIST_COMPARISON",
                "allowlisted_account_ids": "PHASE_F_TRADES_LIST_COMPARISON_ACCOUNT_IDS",
            },
            "cash_ledger": {
                "enabled": "ENABLE_PHASE_F_CASH_LEDGER_COMPARISON",
                "allowlisted_account_ids": "PHASE_F_CASH_LEDGER_COMPARISON_ACCOUNT_IDS",
            },
            "corporate_actions": {
                "enabled": "ENABLE_PHASE_F_CORPORATE_ACTIONS_COMPARISON",
                "allowlisted_account_ids": "PHASE_F_CORPORATE_ACTIONS_COMPARISON_ACCOUNT_IDS",
            },
        },
    }


def _build_unavailable_store_runtime(store_spec: dict[str, Any], *, reason: str, error: str | None = None) -> dict[str, Any]:
    store_cls = store_spec["class"]
    return {
        "enabled": False,
        "mode": getattr(store_cls, "MODE", "disabled"),
        "dialect": None,
        "schema": {
            "schema_key": getattr(store_cls, "SCHEMA_KEY", store_spec["phase"]),
            "source_path": None,
            "expected_tables": sorted(getattr(store_cls, "EXPECTED_TABLES", [])),
            "expected_indexes": sorted(getattr(store_cls, "EXPECTED_INDEXES", [])),
            "expected_constraints": [
                {"table": table_name, "name": constraint_name}
                for table_name, constraint_name in getattr(store_cls, "EXPECTED_CONSTRAINTS", ())
            ],
            "present_tables": [],
            "missing_tables": sorted(getattr(store_cls, "EXPECTED_TABLES", [])),
            "present_indexes": [],
            "missing_indexes": sorted(getattr(store_cls, "EXPECTED_INDEXES", [])),
            "last_apply_status": "unknown",
            "skip_reason": reason,
            "last_error": error,
            "last_apply_statement_count": 0,
            "bootstrap_recorded": False,
            "bootstrap": None,
        },
        "connection": {
            "requested": True,
            "ok": False,
            "error": error or reason,
        },
    }


def _manual_probe_store_runtime(
    store_spec: dict[str, Any],
    *,
    db_url: str,
    auto_apply_schema: bool,
) -> dict[str, Any]:
    store_cls = store_spec["class"]
    try:
        store = store_cls(db_url, auto_apply_schema=False)
    except Exception as exc:
        return _build_unavailable_store_runtime(
            store_spec,
            reason="doctor_manual_probe_init_failed",
            error=f"{exc.__class__.__name__}: {exc}",
        )

    try:
        runtime = store.describe_runtime(include_connection_probe=True)
        runtime["enabled"] = False
        if auto_apply_schema and runtime["schema"].get("last_apply_status") == "skipped":
            runtime["schema"]["last_apply_status"] = "unknown"
            runtime["schema"]["skip_reason"] = "doctor_manual_probe_no_apply"
        return runtime
    except Exception as exc:
        return _build_unavailable_store_runtime(
            store_spec,
            reason="doctor_manual_probe_describe_failed",
            error=f"{exc.__class__.__name__}: {exc}",
        )
    finally:
        try:
            store.dispose()
        except Exception:
            pass


def _store_status_from_runtime(
    runtime: dict[str, Any],
    *,
    pg_configured: bool,
    topology_available: bool,
) -> str:
    if not pg_configured:
        return "unavailable"
    if topology_available and runtime.get("enabled"):
        return "initialized"
    connection = runtime.get("connection") or {}
    if connection.get("ok"):
        return "configured"
    return "unavailable"


def _store_summary(
    store_spec: dict[str, Any],
    runtime: dict[str, Any],
    *,
    pg_configured: bool,
    topology_available: bool,
    inspection_mode: str,
) -> dict[str, Any]:
    schema = dict(runtime.get("schema") or {})
    connection = dict(runtime.get("connection") or {})
    bootstrap = schema.get("bootstrap") if isinstance(schema.get("bootstrap"), dict) else None
    return {
        "phase": store_spec["phase"],
        "label": store_spec["label"],
        "domain": store_spec["domain"],
        "module_path": store_spec["module_path"],
        "status": _store_status_from_runtime(
            runtime,
            pg_configured=pg_configured,
            topology_available=topology_available,
        ),
        "inspection_mode": inspection_mode,
        "enabled": bool(runtime.get("enabled")),
        "mode": runtime.get("mode"),
        "dialect": runtime.get("dialect"),
        "connection_ok": connection.get("ok"),
        "connection_error": connection.get("error"),
        "schema_key": schema.get("schema_key"),
        "schema_apply_status": schema.get("last_apply_status"),
        "schema_skip_reason": schema.get("skip_reason"),
        "schema_last_error": schema.get("last_error"),
        "expected_tables": list(schema.get("expected_tables") or []),
        "expected_table_count": len(list(schema.get("expected_tables") or [])),
        "present_tables": list(schema.get("present_tables") or []),
        "missing_tables": list(schema.get("missing_tables") or []),
        "expected_indexes": list(schema.get("expected_indexes") or []),
        "expected_index_count": len(list(schema.get("expected_indexes") or [])),
        "present_indexes": list(schema.get("present_indexes") or []),
        "missing_indexes": list(schema.get("missing_indexes") or []),
        "bootstrap_recorded": bool(schema.get("bootstrap_recorded")),
        "bootstrap_applied_at": bootstrap.get("applied_at") if bootstrap else None,
        "bootstrap_statement_count": bootstrap.get("statement_count") if bootstrap else None,
    }


def _build_store_reports(
    *,
    config: Any,
    topology: dict[str, Any] | None,
    manager_init_error: str | None,
) -> dict[str, Any]:
    pg_url = str(getattr(config, "postgres_phase_a_url", "") or "").strip()
    pg_configured = bool(pg_url)
    store_reports: dict[str, Any] = {}
    manual_probe_safe = pg_url.startswith("sqlite:///")

    for store_spec in _STORE_SPECS:
        phase_key = store_spec["phase"]
        if topology is not None:
            runtime = dict(topology["stores"][phase_key])
            inspection_mode = "runtime_topology"
        elif pg_configured and manager_init_error and not manual_probe_safe:
            runtime = _build_unavailable_store_runtime(
                store_spec,
                reason="bridge_init_failed_before_store_probe",
                error=manager_init_error,
            )
            inspection_mode = "bridge_init_error_only"
        elif pg_configured:
            runtime = _manual_probe_store_runtime(
                store_spec,
                db_url=pg_url,
                auto_apply_schema=bool(getattr(config, "postgres_phase_a_apply_schema", True)),
            )
            inspection_mode = "manual_no_apply_probe"
        else:
            runtime = _build_unavailable_store_runtime(
                store_spec,
                reason="postgres_bridge_disabled",
            )
            inspection_mode = "bridge_disabled"

        store_reports[phase_key] = _store_summary(
            store_spec,
            runtime,
            pg_configured=pg_configured,
            topology_available=topology is not None,
            inspection_mode=inspection_mode,
        )

    return store_reports


def _build_phase_g_control_plane(
    *,
    stores: dict[str, Any],
    phase_g_status: dict[str, Any] | None,
) -> dict[str, Any]:
    phase_g_store = stores["phase_g"]
    observability = {
        "bridge_enabled": bool(phase_g_status.get("bridge_enabled")) if phase_g_status else False,
        "shadow_enabled": bool(phase_g_status.get("shadow_enabled")) if phase_g_status else phase_g_store["status"] in {"configured", "initialized"},
        "mode": (
            phase_g_status.get("mode")
            if phase_g_status is not None
            else phase_g_store["mode"]
        ),
        "shadow_store": (
            phase_g_status.get("shadow_store")
            if phase_g_status is not None
            else "phase_g"
        ),
        "shadow_entities": (
            list(phase_g_status.get("shadow_entities") or [])
            if phase_g_status is not None
            else ["execution_sessions", "execution_events"]
        ),
        "schema_apply_status": phase_g_store["schema_apply_status"],
        "missing_tables": list(phase_g_store["missing_tables"]),
        "missing_indexes": list(phase_g_store["missing_indexes"]),
        "bootstrap_recorded": bool(phase_g_store["bootstrap_recorded"]),
        "serving_flags": (
            dict(phase_g_status.get("serving_flags") or {})
            if phase_g_status is not None
            else {
                "sqlite_primary": True,
                "pg_execution_logs_shadow": phase_g_store["status"] in {"configured", "initialized"},
                "pg_execution_logs_are_serving_truth": False,
            }
        ),
    }
    return {
        "mode": phase_g_store["mode"],
        "serving_truth": ".env + sqlite runtime path",
        "postgres_role": "snapshot_shadow",
        "live_source_reminder": ".env remains the live source of truth for control-plane config; PostgreSQL is snapshot/shadow only.",
        "execution_log_observability": observability,
    }


def _build_postgresql_coexistence(
    *,
    config: Any,
    topology: dict[str, Any] | None,
    manager_init_error: str | None,
) -> dict[str, Any]:
    pg_url = str(getattr(config, "postgres_phase_a_url", "") or "").strip()
    return {
        "configured": bool(pg_url),
        "config_env_var": "POSTGRES_PHASE_A_URL",
        "apply_schema_env_var": "POSTGRES_PHASE_A_APPLY_SCHEMA",
        "dsn_summary": redact_database_url(pg_url),
        "auto_apply_schema": bool(getattr(config, "postgres_phase_a_apply_schema", True)),
        "bridge_initialized": bool(topology and topology.get("postgres_bridge", {}).get("enabled")),
        "manager_init_error": manager_init_error,
    }


def _build_topology_summary(
    *,
    sqlite_primary: dict[str, Any],
    postgresql_coexistence: dict[str, Any],
    stores: dict[str, Any],
) -> dict[str, Any]:
    return {
        "config_layer": {
            "sqlite_database_path": sqlite_primary["configured_path"],
            "postgres_phase_a_url_configured": bool(postgresql_coexistence["configured"]),
            "postgres_phase_a_apply_schema": bool(postgresql_coexistence["auto_apply_schema"]),
        },
        "bridge_layer": {
            "sqlite_primary_reachable": bool(sqlite_primary["reachable"]["ok"]),
            "postgres_bridge_initialized": bool(postgresql_coexistence["bridge_initialized"]),
            "dsn_summary": postgresql_coexistence["dsn_summary"],
        },
        "domain_layer": [
            {
                "phase": phase_key,
                "status": store_summary["status"],
                "mode": store_summary["mode"],
                "schema_apply_status": store_summary["schema_apply_status"],
            }
            for phase_key, store_summary in stores.items()
        ],
    }


def _phase_f_config_trap(phase_f_mode: dict[str, Any]) -> str | None:
    cash = phase_f_mode["comparisons"]["cash_ledger"]
    corp = phase_f_mode["comparisons"]["corporate_actions"]
    if cash["enabled"] and not cash["allowlisted_account_ids"]:
        return "Phase F cash-ledger comparison is enabled but the allowlist is empty, so comparison requests will skip."
    if corp["enabled"] and not corp["allowlisted_account_ids"]:
        return "Phase F corporate-actions comparison is enabled but the allowlist is empty, so comparison requests will skip."
    return None


def _classification_files(category: str, likely_store: str | None) -> list[str]:
    files = list(_BASE_READ_FIRST)
    if category == "sqlite_primary_path_issue":
        return ["src/storage.py", "src/config.py"]
    if category == "config_issue":
        if likely_store == "phase_f":
            files.extend(["docs/operations/database.md#phase-f-configuration"])
        elif likely_store == "phase_g":
            files.extend(["src/services/system_config_service.py"])
        else:
            files.extend(["docs/operations/database.md#troubleshooting"])
    elif category == "schema_bootstrap_issue":
        files.extend(["src/postgres_schema_bootstrap.py"])
    elif category == "pg_bridge_init_issue":
        files.extend(["src/postgres_store_utils.py"])
    elif category == "domain_business_path_issue":
        files.extend(["src/services/execution_log_service.py"])

    if likely_store and likely_store in _STORE_SPEC_BY_PHASE:
        files.append(_STORE_SPEC_BY_PHASE[likely_store]["module_path"])

    deduped: list[str] = []
    for item in files:
        if item not in deduped:
            deduped.append(item)
    return deduped[:8]


def _classify_report(
    *,
    sqlite_primary: dict[str, Any],
    postgresql_coexistence: dict[str, Any],
    stores: dict[str, Any],
    phase_f_mode: dict[str, Any],
    phase_g_control_plane: dict[str, Any],
) -> dict[str, Any]:
    if not sqlite_primary["path_exists"] or not sqlite_primary["reachable"]["ok"]:
        category = "sqlite_primary_path_issue"
        reason = "SQLite is still the primary runtime path, and the file path is missing or not reachable."
        likely_store = None
    elif postgresql_coexistence["configured"] and not postgresql_coexistence["bridge_initialized"]:
        category = "pg_bridge_init_issue"
        reason = "PostgreSQL coexistence is configured, but the bridge failed before the runtime could initialize all stores."
        likely_store = next(
            (
                phase_key
                for phase_key, store_summary in stores.items()
                if store_summary["status"] == "unavailable"
            ),
            "phase_a",
        )
    else:
        schema_issue_store = next(
            (
                phase_key
                for phase_key, store_summary in stores.items()
                if store_summary["status"] in {"configured", "initialized"}
                and (
                    store_summary["schema_apply_status"] == "failed"
                    or bool(store_summary["missing_tables"])
                    or bool(store_summary["missing_indexes"])
                )
            ),
            None,
        )
        if schema_issue_store is not None:
            category = "schema_bootstrap_issue"
            reason = (
                f"{schema_issue_store} is reachable, but expected PostgreSQL tables/indexes or bootstrap records are missing."
            )
            likely_store = schema_issue_store
        else:
            phase_f_trap = _phase_f_config_trap(phase_f_mode)
            if phase_f_trap is not None or not postgresql_coexistence["configured"]:
                category = "config_issue"
                reason = phase_f_trap or (
                    "PostgreSQL coexistence is not configured. If you expected shadow/coexistence behavior, start with env/config."
                )
                likely_store = "phase_f" if phase_f_trap else None
            else:
                phase_g_observability = phase_g_control_plane["execution_log_observability"]
                if phase_g_observability["shadow_enabled"] and (
                    phase_g_observability["missing_tables"] or phase_g_observability["missing_indexes"]
                ):
                    category = "schema_bootstrap_issue"
                    reason = "Phase G execution-log shadowing is enabled, but execution-log schema objects are incomplete."
                    likely_store = "phase_g"
                else:
                    category = "domain_business_path_issue"
                    reason = (
                        "Topology, bridge initialization, and schema visibility look healthy enough that the next check is the domain/business layer."
                    )
                    likely_store = next(
                        (
                            phase_key
                            for phase_key, store_summary in stores.items()
                            if store_summary["status"] in {"configured", "initialized"}
                        ),
                        None,
                    )

    likely_domain = _STORE_SPEC_BY_PHASE[likely_store]["domain"] if likely_store in _STORE_SPEC_BY_PHASE else None
    files_to_read_first = _classification_files(category, likely_store)
    return {
        "category": category,
        "reason": reason,
        "likely_store": likely_store,
        "likely_domain": likely_domain,
        "files_to_read_first": files_to_read_first,
    }


def _build_ai_handoff(
    *,
    classification: dict[str, Any],
    sqlite_primary: dict[str, Any],
    postgresql_coexistence: dict[str, Any],
    phase_f_mode: dict[str, Any],
    phase_g_control_plane: dict[str, Any],
    stores: dict[str, Any],
) -> dict[str, Any]:
    store_health = ", ".join(
        f"{phase_key}={store_summary['status']}/{store_summary['schema_apply_status']}"
        for phase_key, store_summary in stores.items()
    )
    paste_lines = [
        "Database doctor snapshot",
        f"- probable_classification: {classification['category']}",
        f"- likely_store: {classification['likely_store'] or 'unknown'}",
        f"- likely_domain: {classification['likely_domain'] or 'unknown'}",
        (
            "- sqlite_primary: "
            f"path={sqlite_primary['resolved_path']} "
            f"exists={_yes_no(sqlite_primary['path_exists'])} "
            f"reachable={_yes_no(sqlite_primary['reachable']['ok'])}"
        ),
        (
            "- postgres_coexistence: "
            f"configured={_yes_no(postgresql_coexistence['configured'])} "
            f"bridge_initialized={_yes_no(postgresql_coexistence['bridge_initialized'])} "
            f"dsn={postgresql_coexistence['dsn_summary'] or 'not configured'} "
            f"auto_apply_schema={_yes_no(postgresql_coexistence['auto_apply_schema'])}"
        ),
        (
            "- phase_f: "
            f"serving_truth={phase_f_mode['serving_truth']} "
            f"postgres_role={phase_f_mode['postgres_role']} "
            f"trades_list={phase_f_mode['comparisons']['trades_list']['allowlist_interpretation']}"
        ),
        (
            "- phase_g: "
            f"live_source=.env "
            f"shadow_enabled={_yes_no(phase_g_control_plane['execution_log_observability']['shadow_enabled'])} "
            f"schema_apply_status={phase_g_control_plane['execution_log_observability']['schema_apply_status']}"
        ),
        f"- store_health: {store_health}",
        f"- files_to_read_first: {', '.join(classification['files_to_read_first'])}",
    ]
    return {
        "likely_responsible_store": classification["likely_store"],
        "likely_responsible_domain": classification["likely_domain"],
        "files_to_read_first": list(classification["files_to_read_first"]),
        "summary_text": classification["reason"],
        "paste_block": "\n".join(paste_lines),
    }


@contextmanager
def _temporary_environment(overrides: dict[str, str | None]):
    original_values = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        Config.reset_instance()
        DatabaseManager.reset_instance()
        yield
    finally:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        for key, value in original_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        Config.reset_instance()
        DatabaseManager.reset_instance()


@contextmanager
def _temporary_real_pg_bundle_environment(real_pg_dsn: str):
    with tempfile.TemporaryDirectory(prefix="database-real-pg-bundle-") as temp_dir:
        isolated_sqlite_path = Path(temp_dir) / "database-real-pg-bundle.sqlite"
        with _temporary_environment(
            {
                "DATABASE_PATH": str(isolated_sqlite_path),
                "POSTGRES_PHASE_A_URL": real_pg_dsn,
                "POSTGRES_PHASE_A_APPLY_SCHEMA": "true",
            }
        ):
            yield isolated_sqlite_path


def _build_real_pg_phase_store_initialization_check(stores: dict[str, Any]) -> dict[str, Any]:
    phases = {
        phase_key: {
            "status": store_summary["status"],
            "connection_ok": store_summary["connection_ok"],
            "schema_apply_status": store_summary["schema_apply_status"],
        }
        for phase_key, store_summary in stores.items()
    }
    passed = all(
        store_summary["status"] == "initialized"
        and bool(store_summary["connection_ok"])
        and store_summary["schema_apply_status"] == "applied"
        for store_summary in stores.values()
    )
    return {
        "passed": passed,
        "phases": phases,
    }


def _build_real_pg_schema_bootstrap_check(stores: dict[str, Any]) -> dict[str, Any]:
    missing_requirements: dict[str, Any] = {}
    recorded_schema_keys: list[str] = []
    tolerated_index_gaps: dict[str, list[str]] = {}

    for phase_key, store_summary in stores.items():
        if store_summary["bootstrap_recorded"]:
            recorded_schema_keys.append(phase_key)
        if store_summary["dialect"] == "sqlite" and store_summary["missing_indexes"]:
            tolerated_index_gaps[phase_key] = list(store_summary["missing_indexes"])
        if not store_summary["bootstrap_recorded"] or store_summary["missing_tables"]:
            missing_requirements[phase_key] = {
                "bootstrap_recorded": bool(store_summary["bootstrap_recorded"]),
                "missing_tables": list(store_summary["missing_tables"]),
                "missing_indexes": list(store_summary["missing_indexes"]),
            }
            continue
        if store_summary["dialect"] != "sqlite" and store_summary["missing_indexes"]:
            missing_requirements[phase_key] = {
                "bootstrap_recorded": bool(store_summary["bootstrap_recorded"]),
                "missing_tables": list(store_summary["missing_tables"]),
                "missing_indexes": list(store_summary["missing_indexes"]),
            }

    return {
        "passed": not missing_requirements,
        "recorded_schema_keys": sorted(recorded_schema_keys),
        "missing_requirements": missing_requirements,
        "tolerated_index_gaps": tolerated_index_gaps,
    }


def _build_real_pg_phase_g_shadow_check() -> dict[str, Any]:
    from src.services.execution_log_service import ExecutionLogService

    db = DatabaseManager.get_instance()
    db.create_or_update_app_user(
        user_id="database-real-pg-bundle",
        username="database-real-pg-bundle",
        role="admin",
        display_name="Database Real PG Bundle",
    )
    before_sessions = db.list_phase_g_execution_sessions(limit=200)
    service = ExecutionLogService()
    session_id = service.record_admin_action(
        action="database_real_pg_bundle_probe",
        message="Database real PG bundle probe completed",
        actor={
            "user_id": "database-real-pg-bundle",
            "username": "database-real-pg-bundle",
            "display_name": "Database Real PG Bundle",
            "role": "admin",
        },
        subsystem="system_control",
        destructive=False,
        detail={"origin": "database_real_pg_bundle", "probe": True},
    )
    after_sessions = db.list_phase_g_execution_sessions(limit=200)
    sqlite_detail = db.get_execution_log_session_detail(session_id)
    pg_detail = db.get_phase_g_execution_session_detail(session_id)

    sqlite_event_count = len(list((sqlite_detail or {}).get("events") or []))
    pg_event_count = len(list((pg_detail or {}).get("events") or []))
    return {
        "passed": bool(sqlite_detail) and bool(pg_detail) and sqlite_event_count > 0 and pg_event_count > 0,
        "probe_session_id": session_id,
        "sqlite_session_present": sqlite_detail is not None,
        "pg_session_present": pg_detail is not None,
        "sqlite_event_count": sqlite_event_count,
        "pg_event_count": pg_event_count,
        "pg_session_count_delta": max(0, len(after_sessions) - len(before_sessions)),
        "sqlite_overall_status": (sqlite_detail or {}).get("overall_status"),
        "pg_overall_status": (pg_detail or {}).get("overall_status"),
        "pg_related_phase_g_admin_log_count": (pg_detail or {}).get("related_phase_g_admin_log_count"),
        "pg_related_phase_g_system_action_count": (pg_detail or {}).get("related_phase_g_system_action_count"),
    }


def _build_real_pg_bundle_ai_handoff(
    *,
    report: dict[str, Any],
    disposable_dsn_summary: str,
    isolated_sqlite_path: str,
) -> dict[str, Any]:
    checks = report["real_pg_bundle"]["verification_checks"]
    lines = [
        "Real-PG bundle snapshot",
        f"- disposable_dsn={disposable_dsn_summary}",
        f"- isolated_sqlite_path={isolated_sqlite_path}",
        (
            "- runtime_safety: "
            "sqlite_primary_truth_changed=no "
            "phase_f_serving_changed=no "
            "phase_g_live_truth_changed=no"
        ),
        (
            "- phase_store_initialization: "
            f"passed={_yes_no(checks['phase_store_initialization']['passed'])}"
        ),
        (
            "- schema_bootstrap: "
            f"passed={_yes_no(checks['schema_bootstrap']['passed'])} "
            f"recorded_schema_keys={','.join(checks['schema_bootstrap']['recorded_schema_keys']) or 'none'}"
        ),
        (
            "- phase_g_execution_log_shadow: "
            f"passed={_yes_no(checks['phase_g_execution_log_shadow']['passed'])} "
            f"pg_session_count_delta={checks['phase_g_execution_log_shadow']['pg_session_count_delta']}"
        ),
        (
            "- phase_f_authority: "
            f"trades_list={report['phase_f_authority_summary']['features']['trades_list']['effective_account_scope']} "
            f"cash_ledger={report['phase_f_authority_summary']['features']['cash_ledger']['effective_account_scope']} "
            f"corporate_actions={report['phase_f_authority_summary']['features']['corporate_actions']['effective_account_scope']}"
        ),
        f"- files_to_read_first: {', '.join(report['ai_handoff']['files_to_read_first'])}",
    ]
    return {
        "files_to_read_first": list(report["ai_handoff"]["files_to_read_first"]),
        "paste_block": "\n".join(lines),
    }


def _normalize_real_pg_bundle_report(
    *,
    report: dict[str, Any],
    isolated_sqlite_path: Path,
) -> dict[str, Any]:
    actual_sqlite_path = str(isolated_sqlite_path)
    report["sqlite_primary"]["configured_path"] = _REAL_PG_TEMP_SQLITE_PLACEHOLDER
    report["sqlite_primary"]["resolved_path"] = _REAL_PG_TEMP_SQLITE_PLACEHOLDER
    report["topology_summary"]["config_layer"]["sqlite_database_path"] = _REAL_PG_TEMP_SQLITE_PLACEHOLDER
    report["real_pg_bundle"]["isolated_sqlite_path"] = _REAL_PG_TEMP_SQLITE_PLACEHOLDER
    report["real_pg_bundle"]["verification_checks"]["phase_g_execution_log_shadow"][
        "probe_session_id"
    ] = _REAL_PG_PROBE_SESSION_PLACEHOLDER
    report["ai_handoff"]["paste_block"] = str(report["ai_handoff"]["paste_block"]).replace(
        actual_sqlite_path,
        _REAL_PG_TEMP_SQLITE_PLACEHOLDER,
    )
    for store_summary in report.get("stores", {}).values():
        if store_summary.get("bootstrap_applied_at"):
            store_summary["bootstrap_applied_at"] = _REAL_PG_BOOTSTRAP_APPLIED_AT_PLACEHOLDER
    report["real_pg_bundle"]["ai_handoff_sample"] = _build_real_pg_bundle_ai_handoff(
        report=report,
        disposable_dsn_summary=report["real_pg_bundle"]["disposable_dsn_summary"],
        isolated_sqlite_path=_REAL_PG_TEMP_SQLITE_PLACEHOLDER,
    )
    return report


def build_database_doctor_report() -> dict[str, Any]:
    config = get_config()
    db: DatabaseManager | None = None
    topology: dict[str, Any] | None = None
    phase_g_status: dict[str, Any] | None = None
    manager_init_error: str | None = None

    try:
        db = DatabaseManager.get_instance()
        topology = db.describe_database_topology(include_connection_probe=True)
        phase_g_status = db.describe_phase_g_execution_log_status(include_connection_probe=True)
    except Exception as exc:
        manager_init_error = f"{exc.__class__.__name__}: {exc}"

    sqlite_primary = _build_sqlite_primary_report(config=config, db=db)
    postgresql_coexistence = _build_postgresql_coexistence(
        config=config,
        topology=topology,
        manager_init_error=manager_init_error,
    )
    stores = _build_store_reports(
        config=config,
        topology=topology,
        manager_init_error=manager_init_error,
    )
    phase_f_mode = _build_phase_f_mode(config, topology)
    phase_f_authority_summary = _build_phase_f_authority_summary(config, phase_f_mode)
    phase_g_control_plane = _build_phase_g_control_plane(
        stores=stores,
        phase_g_status=phase_g_status,
    )
    topology_summary = _build_topology_summary(
        sqlite_primary=sqlite_primary,
        postgresql_coexistence=postgresql_coexistence,
        stores=stores,
    )
    classification = _classify_report(
        sqlite_primary=sqlite_primary,
        postgresql_coexistence=postgresql_coexistence,
        stores=stores,
        phase_f_mode=phase_f_mode,
        phase_g_control_plane=phase_g_control_plane,
    )
    ai_handoff = _build_ai_handoff(
        classification=classification,
        sqlite_primary=sqlite_primary,
        postgresql_coexistence=postgresql_coexistence,
        phase_f_mode=phase_f_mode,
        phase_g_control_plane=phase_g_control_plane,
        stores=stores,
    )

    report = {
        "doctor_version": "database_doctor_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "runtime": {
            "database_manager_initialized": db is not None,
            "database_manager_init_error": manager_init_error,
        },
        "sqlite_primary": sqlite_primary,
        "postgresql_coexistence": postgresql_coexistence,
        "stores": stores,
        "phase_f_mode": phase_f_mode,
        "phase_f_authority_summary": phase_f_authority_summary,
        "phase_g_control_plane": phase_g_control_plane,
        "topology_summary": topology_summary,
        "probable_issue_classification": classification,
        "ai_handoff": ai_handoff,
    }
    return _sanitize_value(report)


def build_database_real_pg_bundle_report(*, real_pg_dsn: str | None = None) -> dict[str, Any]:
    requested_dsn = str(real_pg_dsn or os.getenv("POSTGRES_PHASE_A_REAL_DSN") or "").strip()
    if not requested_dsn:
        raise ValueError("Real-PG bundle mode requires --real-pg-dsn or POSTGRES_PHASE_A_REAL_DSN.")

    dsn_source = "argument" if real_pg_dsn else "POSTGRES_PHASE_A_REAL_DSN"
    disposable_dsn_summary = redact_database_url(requested_dsn)

    with _temporary_real_pg_bundle_environment(requested_dsn) as isolated_sqlite_path:
        report = build_database_doctor_report()
        phase_store_initialization = _build_real_pg_phase_store_initialization_check(report["stores"])
        schema_bootstrap = _build_real_pg_schema_bootstrap_check(report["stores"])
        try:
            phase_g_execution_log_shadow = _build_real_pg_phase_g_shadow_check()
        except Exception as exc:
            phase_g_execution_log_shadow = {
                "passed": False,
                "probe_session_id": None,
                "sqlite_session_present": False,
                "pg_session_present": False,
                "sqlite_event_count": 0,
                "pg_event_count": 0,
                "pg_session_count_delta": 0,
                "error": f"{exc.__class__.__name__}: {exc}",
                "pg_related_phase_g_admin_log_count": None,
                "pg_related_phase_g_system_action_count": None,
            }

        report["report_kind"] = "database_real_pg_bundle"
        report["real_pg_bundle"] = {
            "bundle_model": "database_real_pg_support_bundle_v1",
            "dsn_source": dsn_source,
            "disposable_dsn_summary": disposable_dsn_summary,
            "isolated_sqlite_path": str(isolated_sqlite_path),
            "safety_contract": {
                "sqlite_primary_truth_changed": False,
                "phase_f_serving_changed": False,
                "phase_g_live_truth_changed": False,
                "note": (
                    "This bundle runs against an isolated SQLite file plus a disposable DSN. "
                    "It does not promote PostgreSQL to runtime truth and does not change Phase F serving semantics."
                ),
            },
            "verification_checks": {
                "phase_store_initialization": phase_store_initialization,
                "schema_bootstrap": schema_bootstrap,
                "phase_g_execution_log_shadow": phase_g_execution_log_shadow,
                "phase_f_comparison_flags": {
                    "passed": (
                        report["phase_f_mode"]["serving_truth"] == "sqlite"
                        and report["phase_f_mode"]["postgres_role"] == "comparison_only_shadow"
                    ),
                    "mode": report["phase_f_mode"]["mode"],
                    "serving_truth": report["phase_f_mode"]["serving_truth"],
                    "postgres_role": report["phase_f_mode"]["postgres_role"],
                    "authority_summary_model": report["phase_f_authority_summary"]["summary_model"],
                },
            },
        }
        report["real_pg_bundle"]["ai_handoff_sample"] = _build_real_pg_bundle_ai_handoff(
            report=report,
            disposable_dsn_summary=disposable_dsn_summary,
            isolated_sqlite_path=str(isolated_sqlite_path),
        )
        return _sanitize_value(
            _normalize_real_pg_bundle_report(
                report=report,
                isolated_sqlite_path=isolated_sqlite_path,
            )
        )


def _store_table_rows(stores: dict[str, Any]) -> list[str]:
    rows = [
        "| Store | Status | Mode | Schema | Missing tables | Missing indexes | Bootstrap |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for phase_key, store_summary in stores.items():
        rows.append(
            "| {phase} | {status} | {mode} | {schema} | {missing_tables} | {missing_indexes} | {bootstrap} |".format(
                phase=phase_key,
                status=store_summary["status"],
                mode=store_summary["mode"],
                schema=store_summary["schema_apply_status"],
                missing_tables=len(store_summary["missing_tables"]),
                missing_indexes=len(store_summary["missing_indexes"]),
                bootstrap=_yes_no(store_summary["bootstrap_recorded"]),
            )
        )
    return rows


def _phase_f_authority_table_rows(summary: dict[str, Any]) -> list[str]:
    rows = [
        "| Feature | Enabled | Effective account scope | Empty allowlist behavior | Non-empty restriction sets |",
        "| --- | --- | --- | --- | --- |",
    ]
    for feature_key in ("trades_list", "cash_ledger", "corporate_actions"):
        feature = dict(summary["features"][feature_key])
        non_empty_sets = dict(feature.get("non_empty_restriction_sets") or {})
        rows.append(
            "| {feature} | {enabled} | {scope} | {empty_behavior} | {restriction_sets} |".format(
                feature=feature_key,
                enabled=_yes_no(feature.get("enabled")),
                scope=feature.get("effective_account_scope"),
                empty_behavior=feature.get("empty_allowlist_behavior"),
                restriction_sets=(
                    json.dumps(non_empty_sets, ensure_ascii=False, sort_keys=True)
                    if non_empty_sets
                    else "{}"
                ),
            )
        )
    return rows


def render_database_doctor_markdown(report: dict[str, Any]) -> str:
    sqlite_primary = report["sqlite_primary"]
    pg = report["postgresql_coexistence"]
    phase_f_mode = report["phase_f_mode"]
    phase_f_authority_summary = report["phase_f_authority_summary"]
    phase_g = report["phase_g_control_plane"]
    classification = report["probable_issue_classification"]
    ai_handoff = report["ai_handoff"]
    real_pg_bundle = report.get("real_pg_bundle")

    lines = [
        "# Database Doctor Report",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Probable classification: `{classification['category']}`",
        f"- Likely store/domain: `{classification['likely_store'] or 'unknown'}` / `{classification['likely_domain'] or 'unknown'}`",
        f"- Classification reason: {classification['reason']}",
        "",
        "## Runtime Summary",
        (
            "- SQLite primary: "
            f"path=`{sqlite_primary['resolved_path']}` "
            f"exists=`{_yes_no(sqlite_primary['path_exists'])}` "
            f"reachable=`{_yes_no(sqlite_primary['reachable']['ok'])}`"
        ),
        (
            "- PostgreSQL coexistence: "
            f"configured=`{_yes_no(pg['configured'])}` "
            f"bridge_initialized=`{_yes_no(pg['bridge_initialized'])}` "
            f"auto_apply_schema=`{_yes_no(pg['auto_apply_schema'])}` "
            f"dsn=`{pg['dsn_summary'] or 'not configured'}`"
        ),
    ]
    if pg["manager_init_error"]:
        lines.append(f"- PostgreSQL init error: `{pg['manager_init_error']}`")

    lines.extend(
        [
            "",
            "## Store Status",
            *_store_table_rows(report["stores"]),
            "",
            "## Phase F Mode",
            f"- Serving truth: `{phase_f_mode['serving_truth']}`",
            f"- PostgreSQL role: `{phase_f_mode['postgres_role']}`",
            f"- Trades-list comparison: {phase_f_mode['comparisons']['trades_list']['allowlist_interpretation']}",
            f"- Cash-ledger comparison: {phase_f_mode['comparisons']['cash_ledger']['allowlist_interpretation']}",
            f"- Corporate-actions comparison: {phase_f_mode['comparisons']['corporate_actions']['allowlist_interpretation']}",
            "",
            "## Phase F Authority Summary",
            (
                "- Request actor scope: "
                f"roles=`{','.join(phase_f_authority_summary['request_actor_scope']['allowed_roles'])}` "
                f"owner_scope_enforced_at_api=`{_yes_no(phase_f_authority_summary['request_actor_scope']['owner_scope_enforced_at_api'])}` "
                f"comparison_specific_role_gate=`{_yes_no(phase_f_authority_summary['request_actor_scope']['comparison_specific_role_gate'])}`"
            ),
            f"- Scope note: {phase_f_authority_summary['request_actor_scope']['note']}",
            *_phase_f_authority_table_rows(phase_f_authority_summary),
            "",
            "## Phase G Control Plane",
            f"- Live source reminder: {phase_g['live_source_reminder']}",
            (
                "- Execution-log observability: "
                f"shadow_enabled=`{_yes_no(phase_g['execution_log_observability']['shadow_enabled'])}` "
                f"schema_apply_status=`{phase_g['execution_log_observability']['schema_apply_status']}` "
                f"missing_tables=`{len(phase_g['execution_log_observability']['missing_tables'])}` "
                f"missing_indexes=`{len(phase_g['execution_log_observability']['missing_indexes'])}`"
            ),
        ]
    )
    if real_pg_bundle is not None:
        checks = real_pg_bundle["verification_checks"]
        lines.extend(
            [
                "",
                "## Real-PG Bundle Verification",
                f"- Disposable DSN: `{real_pg_bundle['disposable_dsn_summary']}`",
                f"- Isolated SQLite path: `{real_pg_bundle['isolated_sqlite_path']}`",
                (
                    "- Safety contract: "
                    f"sqlite_primary_truth_changed=`{_yes_no(real_pg_bundle['safety_contract']['sqlite_primary_truth_changed'])}` "
                    f"phase_f_serving_changed=`{_yes_no(real_pg_bundle['safety_contract']['phase_f_serving_changed'])}` "
                    f"phase_g_live_truth_changed=`{_yes_no(real_pg_bundle['safety_contract']['phase_g_live_truth_changed'])}`"
                ),
                (
                    "- Store initialization: "
                    f"passed=`{_yes_no(checks['phase_store_initialization']['passed'])}`"
                ),
                (
                    "- Schema/bootstrap: "
                    f"passed=`{_yes_no(checks['schema_bootstrap']['passed'])}` "
                    f"recorded_schema_keys=`{','.join(checks['schema_bootstrap']['recorded_schema_keys']) or 'none'}`"
                ),
                (
                    "- Phase G shadow verification: "
                    f"passed=`{_yes_no(checks['phase_g_execution_log_shadow']['passed'])}` "
                    f"pg_session_count_delta=`{checks['phase_g_execution_log_shadow']['pg_session_count_delta']}` "
                    f"pg_event_count=`{checks['phase_g_execution_log_shadow']['pg_event_count']}`"
                ),
                (
                    "- Phase F comparison flags: "
                    f"passed=`{_yes_no(checks['phase_f_comparison_flags']['passed'])}` "
                    f"serving_truth=`{checks['phase_f_comparison_flags']['serving_truth']}` "
                    f"postgres_role=`{checks['phase_f_comparison_flags']['postgres_role']}`"
                ),
            ]
        )
    lines.extend(
        [
            "",
            "## AI Handoff",
            "Paste the following with your error when asking AI for help:",
            "",
            "```text",
            ai_handoff["paste_block"],
            "```",
            "",
            "Files AI should read first:",
        ]
    )
    for item in ai_handoff["files_to_read_first"]:
        lines.append(f"- `{item}`")
    if real_pg_bundle is not None:
        lines.extend(
            [
                "",
                "## Real-PG Bundle AI Handoff",
                "Paste the following when the disposable DSN verification itself is the issue:",
                "",
                "```text",
                real_pg_bundle["ai_handoff_sample"]["paste_block"],
                "```",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def render_database_doctor_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)


def write_database_doctor_outputs(
    report: dict[str, Any],
    *,
    markdown_path: Path | None = None,
    json_path: Path | None = None,
) -> dict[str, str]:
    written: dict[str, str] = {}
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_database_doctor_markdown(report), encoding="utf-8")
        written["markdown"] = str(markdown_path)
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(render_database_doctor_json(report) + "\n", encoding="utf-8")
        written["json"] = str(json_path)
    return written


def _parse_args(argv: Iterable[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a compact database doctor support bundle.")
    parser.add_argument(
        "--real-pg-bundle",
        action="store_true",
        help="run the isolated disposable-DSN verification bundle using POSTGRES_PHASE_A_REAL_DSN or --real-pg-dsn",
    )
    parser.add_argument(
        "--real-pg-dsn",
        default=None,
        help="explicit disposable DSN for --real-pg-bundle; defaults to POSTGRES_PHASE_A_REAL_DSN",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="stdout format",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="write both markdown and json reports into tmp/ as well as printing stdout",
    )
    parser.add_argument(
        "--markdown-output",
        default=None,
        help="custom markdown output path",
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="custom json output path",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.real_pg_bundle:
            report = build_database_real_pg_bundle_report(real_pg_dsn=args.real_pg_dsn)
        else:
            report = build_database_doctor_report()
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2

    markdown_output = Path(args.markdown_output).expanduser() if args.markdown_output else None
    json_output = Path(args.json_output).expanduser() if args.json_output else None
    if args.write:
        if args.real_pg_bundle:
            markdown_output = markdown_output or _DEFAULT_REAL_PG_MARKDOWN_OUTPUT
            json_output = json_output or _DEFAULT_REAL_PG_JSON_OUTPUT
        else:
            markdown_output = markdown_output or _DEFAULT_MARKDOWN_OUTPUT
            json_output = json_output or _DEFAULT_JSON_OUTPUT

    written = write_database_doctor_outputs(
        report,
        markdown_path=markdown_output,
        json_path=json_output,
    )

    if args.format == "json":
        sys.stdout.write(render_database_doctor_json(report) + "\n")
    else:
        sys.stdout.write(render_database_doctor_markdown(report))

    for label, path in written.items():
        sys.stderr.write(f"Wrote {label} report to {path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
