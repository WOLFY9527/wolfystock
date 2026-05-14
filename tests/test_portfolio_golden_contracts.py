# -*- coding: utf-8 -*-
"""Golden fixture contract tests for public portfolio DTO boundaries."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from api.v1.schemas.portfolio import (
    PortfolioBrokerConnectionItem,
    PortfolioCashLedgerListResponse,
    PortfolioCorporateActionListResponse,
    PortfolioFxRefreshResponse,
    PortfolioImportCommitResponse,
    PortfolioImportParseResponse,
    PortfolioIbkrSyncResponse,
    PortfolioLiveFxRateResponse,
    PortfolioSnapshotResponse,
    PortfolioTradeListResponse,
)
from src.services.market_data_source_registry import project_source_provenance


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "portfolio"
FORBIDDEN_PUBLIC_TERMS = (
    "authorization",
    "bearer ",
    "cookie",
    "set-cookie",
    "session_id",
    "session token",
    "session-token",
    "api_key",
    "access_token",
    "refresh_token",
    "password",
    "credential",
    "secret",
    "private_key",
    "raw_broker_payload",
    "raw_provider_payload",
    "provider_payload",
    "request_body",
    "response_body",
    "stack_trace",
    "traceback",
)
FORBIDDEN_UI_AUTHORITY_TERMS = (
    "ui_authoritative_accounting\": true",
    "frontend_authoritative_accounting\": true",
    "client_authoritative_accounting\": true",
    "ui_mutation_authority",
    "frontend_mutation_authority",
    "client_mutation_authority",
    "frontend_calculated_cost_basis",
    "ui_calculated_cost_basis",
)
SNAPSHOT_REQUIRED_KEYS = {
    "as_of",
    "cost_method",
    "currency",
    "account_count",
    "total_cash",
    "total_market_value",
    "total_equity",
    "realized_pnl",
    "unrealized_pnl",
    "fee_total",
    "tax_total",
    "fx_stale",
    "market_breakdown",
    "fx_rates",
    "portfolio_attribution",
    "analytics",
    "riskDiagnostics",
    "portfolioRiskEvidence",
    "sourceAuthorityState",
    "fxFreshnessState",
    "holdingsLineageState",
    "cashLedgerCompletenessState",
    "benchmarkMappingState",
    "factorMappingState",
    "confidenceCap",
    "accounts",
}
RISK_DIAGNOSTICS_REQUIRED_KEYS = {"version", "authority", "calculation_owner", "warnings"}
RISK_DIAGNOSTIC_WARNING_KEYS = {"code", "severity", "message"}
POSITION_REQUIRED_KEYS = {
    "symbol",
    "market",
    "currency",
    "quantity",
    "avg_cost",
    "total_cost",
    "last_price",
    "market_value_base",
    "unrealized_pnl_base",
    "valuation_currency",
    "cost_basis_native",
    "market_value_native",
    "unrealized_pnl_native",
    "unrealized_pnl_pct",
    "display_market_value",
    "display_unrealized_pnl",
    "display_currency",
    "display_fx_status",
}


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _iter_strings(item)
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)
        return
    if isinstance(value, str):
        yield value


def _assert_iso_timestamp(value: str | None) -> None:
    assert value
    datetime.fromisoformat(value.replace("Z", "+00:00"))


def _assert_no_sensitive_public_payload(value: Any) -> None:
    public_text = "\n".join(_iter_strings(value)).lower()
    for term in FORBIDDEN_PUBLIC_TERMS:
        assert term not in public_text


def _assert_no_ui_owned_accounting_authority(value: Any) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True).lower()
    for term in FORBIDDEN_UI_AUTHORITY_TERMS:
        assert term not in serialized


def test_portfolio_snapshot_golden_fixture_matches_public_read_model_contract() -> None:
    payload = _load_fixture("portfolio_snapshot_read_model_dto.json")

    assert SNAPSHOT_REQUIRED_KEYS <= set(payload)
    snapshot = PortfolioSnapshotResponse(**payload).model_dump()

    assert snapshot["cost_method"] == "fifo"
    assert snapshot["currency"] == "CNY"
    assert snapshot["account_count"] == len(snapshot["accounts"]) == 2
    assert snapshot["total_equity"] == snapshot["total_cash"] + snapshot["total_market_value"]
    assert snapshot["realized_pnl"] == 320.0
    assert snapshot["unrealized_pnl"] == 1700.0
    assert snapshot["fee_total"] >= 0
    assert snapshot["tax_total"] >= 0

    assert {item["market"] for item in snapshot["market_breakdown"]} == {"cn", "us"}
    assert round(sum(item["weight_pct"] for item in snapshot["market_breakdown"]), 4) == 100.0

    risk = snapshot["analytics"]["risk"]
    assert risk["holding_count"] == sum(len(account["positions"]) for account in snapshot["accounts"])
    assert risk["account_count"] == snapshot["account_count"]
    assert risk["warnings"] == ["usd_fx_rate_stale"]
    assert set(snapshot["riskDiagnostics"]) == RISK_DIAGNOSTICS_REQUIRED_KEYS
    assert snapshot["riskDiagnostics"]["authority"] == "backend_read_model"
    assert snapshot["riskDiagnostics"]["calculation_owner"] == "backend"
    assert all(set(item) == RISK_DIAGNOSTIC_WARNING_KEYS for item in snapshot["riskDiagnostics"]["warnings"])
    assert snapshot["portfolioRiskEvidence"]["source"] == "backend_snapshot"
    assert snapshot["portfolioRiskEvidence"]["source_payload_redacted"] is True
    assert snapshot["sourceAuthorityState"] == "backend_authoritative_read_model"
    assert snapshot["fxFreshnessState"] == "stale"
    assert snapshot["holdingsLineageState"] == "ledger_backed"
    assert snapshot["cashLedgerCompletenessState"] == "complete"
    assert snapshot["benchmarkMappingState"] == "mapped"
    assert snapshot["factorMappingState"] == "partial"

    for account in snapshot["accounts"]:
        assert account["total_equity"] == account["total_cash"] + account["total_market_value"]
        assert account["cost_method"] == snapshot["cost_method"]
        assert account["owner_id"] == "owner-fixture-1"
        for position in account["positions"]:
            assert POSITION_REQUIRED_KEYS <= set(position)
            assert position["quantity"] > 0
            assert position["market_value_base"] >= 0
            assert position["display_fx_status"] in {"live", "stale", "unavailable"}

    _assert_no_sensitive_public_payload(snapshot)
    _assert_no_ui_owned_accounting_authority(snapshot)


def test_portfolio_holding_fixture_preserves_native_currency_and_stale_fx_honesty() -> None:
    snapshot = PortfolioSnapshotResponse(**_load_fixture("portfolio_snapshot_read_model_dto.json")).model_dump()
    usd_account = next(account for account in snapshot["accounts"] if account["base_currency"] == "USD")
    usd_position = usd_account["positions"][0]
    fx_rate = snapshot["fx_rates"][0]

    assert usd_account["fx_stale"] is True
    assert usd_position["symbol"] == "AAPL"
    assert usd_position["currency"] == "USD"
    assert usd_position["valuation_currency"] == "CNY"
    assert usd_position["display_currency"] == "USD"
    assert usd_position["display_fx_status"] == "stale"
    assert usd_position["market_value_native"] is not None
    assert usd_position["market_value_base"] != usd_position["market_value_native"]
    assert fx_rate["from_currency"] == "USD"
    assert fx_rate["to_currency"] == "CNY"
    assert fx_rate["is_stale"] is True
    assert fx_rate["source"] == "manual_fixture"
    _assert_iso_timestamp(fx_rate["updated_at"])


def test_portfolio_ledger_and_transaction_fixtures_freeze_backend_owned_mutation_boundary() -> None:
    payload = _load_fixture("portfolio_ledger_transactions_dto.json")

    trades = PortfolioTradeListResponse(**payload["trade_list"]).model_dump()
    cash = PortfolioCashLedgerListResponse(**payload["cash_ledger"]).model_dump()
    corporate_actions = PortfolioCorporateActionListResponse(**payload["corporate_actions"]).model_dump()

    assert trades["total"] == len(trades["items"]) == 2
    assert {item["side"] for item in trades["items"]} == {"buy"}
    assert all(item["quantity"] > 0 and item["price"] > 0 for item in trades["items"])
    assert all(item["fee"] >= 0 and item["tax"] >= 0 for item in trades["items"])
    assert all(item["is_active"] is True for item in trades["items"])

    assert cash["total"] == len(cash["items"]) == 2
    assert {item["direction"] for item in cash["items"]} == {"in"}
    assert {item["currency"] for item in cash["items"]} == {"CNY", "USD"}
    assert all(item["amount"] > 0 for item in cash["items"])

    assert corporate_actions["total"] == len(corporate_actions["items"]) == 2
    actions_by_type = {item["action_type"]: item for item in corporate_actions["items"]}
    assert actions_by_type["cash_dividend"]["cash_dividend_per_share"] == 2.0
    assert actions_by_type["split_adjustment"]["split_ratio"] == 4.0

    assert payload["authority"] == {
        "mutation_owner": "backend",
        "read_model_owner": "backend",
        "ui_authoritative_accounting": False,
    }
    assert sorted(payload["authority"]) == [
        "mutation_owner",
        "read_model_owner",
        "ui_authoritative_accounting",
    ]
    _assert_no_sensitive_public_payload(payload)
    _assert_no_ui_owned_accounting_authority(payload)


def test_portfolio_cash_fx_fixture_freezes_public_staleness_and_native_display_semantics() -> None:
    payload = _load_fixture("portfolio_cash_fx_dto.json")

    refresh = PortfolioFxRefreshResponse(**payload["fx_refresh"]).model_dump()
    live_rate = PortfolioLiveFxRateResponse(**payload["live_fx_rate"]).model_dump()
    balances = payload["currency_balances"]

    assert refresh["refresh_enabled"] is False
    assert refresh["disabled_reason"] == "fixture_offline_no_live_provider"
    assert refresh["updated_count"] == 0
    assert refresh["stale_count"] == 1
    assert refresh["error_count"] == 0
    assert live_rate["provider"] == "fixture_manual_rate"
    assert live_rate["cache_hit"] is True
    assert live_rate["stale"] is True
    assert live_rate["error"] == "fixture_stale_rate"
    _assert_iso_timestamp(live_rate["fetched_at"])

    balances_by_currency = {item["currency"]: item for item in balances}
    assert balances_by_currency["CNY"]["fx_status"] == "live"
    assert balances_by_currency["USD"]["fx_status"] == "stale"
    assert balances_by_currency["USD"]["native_display_currency"] == "USD"
    assert payload["failure_state"]["degraded"] is True
    assert payload["failure_state"]["native_values_visible"] is True
    assert payload["failure_state"]["source_payload_redacted"] is True

    _assert_no_sensitive_public_payload(payload)
    _assert_no_ui_owned_accounting_authority(payload)


def test_portfolio_source_aliases_do_not_replace_backend_accounting_authority() -> None:
    snapshot = PortfolioSnapshotResponse(**_load_fixture("portfolio_snapshot_read_model_dto.json")).model_dump()
    expected = {
        "ledger_snapshot": "cache_snapshot",
        "projection_cache": "cache_snapshot",
        "fx_frankfurter_public": "official_public",
        "fx_fallback": "fallback_static",
        "board_lookup_provider": "public_proxy",
    }
    resolved = {
        source: project_source_provenance(source=source, freshness="cached")["sourceType"]
        for source in expected
    }

    assert resolved == expected
    assert snapshot["sourceAuthorityState"] == "backend_authoritative_read_model"
    assert snapshot["sourceAuthorityState"] not in set(resolved.values())


def test_portfolio_visible_surfaces_stay_snapshot_or_cached_not_live_market_feeds() -> None:
    snapshot = PortfolioSnapshotResponse(**_load_fixture("portfolio_snapshot_read_model_dto.json")).model_dump()
    cash_fx = _load_fixture("portfolio_cash_fx_dto.json")
    cached_sources = {
        source: project_source_provenance(source=source, freshness="cached")
        for source in ("ledger_snapshot", "projection_cache")
    }

    assert snapshot["portfolioRiskEvidence"]["source"] == "backend_snapshot"
    assert snapshot["sourceAuthorityState"] == "backend_authoritative_read_model"
    assert all(entry["sourceType"] == "cache_snapshot" for entry in cached_sources.values())
    assert cash_fx["fx_refresh"]["refresh_enabled"] is False
    assert cash_fx["live_fx_rate"]["provider"] == "fixture_manual_rate"
    assert cash_fx["live_fx_rate"]["stale"] is True


def test_portfolio_broker_import_and_sync_fixtures_expose_sanitized_public_status_only() -> None:
    payload = _load_fixture("portfolio_import_sync_dto.json")

    connection = PortfolioBrokerConnectionItem(**payload["broker_connection"]).model_dump()
    parsed = PortfolioImportParseResponse(**payload["import_parse"]).model_dump()
    committed = PortfolioImportCommitResponse(**payload["import_commit"]).model_dump()
    sync = PortfolioIbkrSyncResponse(**payload["ibkr_sync"]).model_dump()

    assert connection["broker_type"] == "ibkr"
    assert connection["broker_account_ref"] == "U123****567"
    assert connection["sync_metadata"]["source_payload_redacted"] is True
    assert parsed["broker"] == "ibkr"
    assert parsed["record_count"] == 1
    assert parsed["cash_record_count"] == 1
    assert parsed["corporate_action_count"] == 1
    assert parsed["skipped_count"] == 1
    assert parsed["error_count"] == 0
    assert parsed["metadata"]["broker_account_ref"] == "U123****567"
    assert parsed["metadata"]["source_payload_redacted"] is True
    assert committed["inserted_count"] == 1
    assert committed["cash_inserted_count"] == 1
    assert committed["corporate_action_inserted_count"] == 1
    assert committed["duplicate_count"] == 1
    assert committed["failed_count"] == 0
    assert committed["dry_run"] is False
    assert sync["snapshot_overlay_active"] is True
    assert sync["used_existing_connection"] is True
    assert sync["fx_stale"] is True
    assert sync["warnings"] == ["fixture_stale_rate"]
    assert payload["status_counts"]["reason_codes"] == ["duplicate_trade_skipped", "fixture_stale_rate"]
    _assert_iso_timestamp(sync["synced_at"])

    _assert_no_sensitive_public_payload(payload)
    _assert_no_ui_owned_accounting_authority(payload)


def test_all_portfolio_golden_fixtures_exclude_raw_secrets_payloads_and_stack_traces() -> None:
    fixture_paths = sorted(FIXTURE_DIR.glob("*.json"))

    assert {path.name for path in fixture_paths} == {
        "portfolio_cash_fx_dto.json",
        "portfolio_import_sync_dto.json",
        "portfolio_ledger_transactions_dto.json",
        "portfolio_snapshot_read_model_dto.json",
    }
    for path in fixture_paths:
        _assert_no_sensitive_public_payload(json.loads(path.read_text(encoding="utf-8")))
