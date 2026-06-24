# -*- coding: utf-8 -*-
"""MAC-118 route contract regressions for API handler selection."""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user, get_database_manager
from api.v1 import api_v1_router
from api.v1.endpoints import backtest, market_provider_operations, scanner, stocks
from tests.api.test_stock_structure_decision_endpoint import _payload as _stock_structure_payload
from tests.api.route_table_helpers import iter_effective_api_routes


PREFLIGHT_CONTRACT_VERSION = "historical_ohlcv_cache_preflight_v1"


def _admin_user() -> CurrentUser:
    return CurrentUser(
        user_id="admin-1",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("ops:providers:read", "scanner:admin:read"),
    )


class _FakePreflightService:
    def preflight(self, **_: Any) -> dict[str, Any]:
        return {
            "contractVersion": PREFLIGHT_CONTRACT_VERSION,
            "mode": "preflight",
            "dryRun": True,
            "networkCallsEnabled": False,
            "mutationEnabled": False,
            "markets": {},
        }


class _FakeScannerOpsService:
    def get_operational_status(self, **_: Any) -> dict[str, Any]:
        return {
            "market": "us",
            "profile": "us_preopen_v1",
            "profileLabel": "US Pre-open",
            "watchlist_date": "2026-06-24",
            "today_trading_day": True,
            "schedule_enabled": False,
            "schedule_time": None,
            "schedule_run_immediately": False,
            "notification_enabled": False,
            "quality_summary": {"available": False},
            "dataReadiness": {
                "state": "partial",
                "universeReadiness": {"state": "available"},
                "quoteReadiness": {"state": "available"},
                "historyReadiness": {"state": "partial"},
                "benchmarkReadiness": {"state": "available"},
                "candidateGenerationState": "ready",
            },
        }


class _FakeStructureDecisionService:
    def get_structure_decision(self, ticker: str, **_: Any) -> dict[str, Any]:
        symbol = ticker.upper()
        payload = _stock_structure_payload(ticker=symbol, confidence="low")
        payload["structureComputation"] = {
            "status": "available",
            "stateReason": "completed",
            "message": "Structure computation completed from supplied evidence.",
        }
        return payload


class _FakeBacktestService:
    def get_global_summary(self, **_: Any) -> dict[str, Any]:
        return {
            "scope": "overall",
            "code": None,
            "eval_window_days": 10,
            "evaluation_window_trading_bars": 10,
            "engine_version": "v1",
            "computed_at": "2026-06-24T09:00:00Z",
            "total_evaluations": 3,
            "completed_count": 3,
            "insufficient_count": 0,
            "long_count": 2,
            "cash_count": 1,
            "win_count": 2,
            "loss_count": 1,
            "neutral_count": 0,
            "direction_accuracy_pct": 66.67,
            "win_rate_pct": 66.67,
            "neutral_rate_pct": 0.0,
            "avg_stock_return_pct": 1.2,
            "avg_simulated_return_pct": 1.0,
            "stop_loss_trigger_rate": None,
            "take_profit_trigger_rate": None,
            "ambiguous_rate": None,
            "avg_days_to_first_hit": None,
            "advice_breakdown": {},
            "diagnostics": {"source": "route_contract_fixture"},
            "evaluation_mode": "standard",
            "requested_mode": "auto",
            "resolved_source": "route_contract_fixture",
            "fallback_used": False,
            "execution_assumptions": {"mode": "stored_summary"},
        }


def _client(monkeypatch) -> TestClient:
    app = FastAPI()
    app.include_router(api_v1_router)
    app.dependency_overrides[get_current_user] = _admin_user
    app.dependency_overrides[get_database_manager] = lambda: object()
    app.dependency_overrides[market_provider_operations.get_historical_ohlcv_cache_preflight_service] = (
        lambda: _FakePreflightService()
    )
    monkeypatch.setattr(scanner, "_build_scanner_ops_service", lambda *_: _FakeScannerOpsService())
    monkeypatch.setattr(stocks, "StockStructureDecisionService", lambda: _FakeStructureDecisionService())
    monkeypatch.setattr(backtest, "_build_backtest_service", lambda *_: _FakeBacktestService())
    return TestClient(app)


def _json_text(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def test_mac118_api_routes_return_dedicated_contract_families(monkeypatch) -> None:
    client = _client(monkeypatch)
    try:
        admin_preflight = client.get("/api/v1/admin/historical-ohlcv/cache-preflight")
        scanner_status = client.get("/api/v1/scanner/status")
        stock_structure = client.get("/api/v1/stocks/ORCL/structure-decision")
        backtest_performance = client.get("/api/v1/backtest/performance")
    finally:
        client.close()

    assert admin_preflight.status_code == 200, admin_preflight.text
    assert scanner_status.status_code == 200, scanner_status.text
    assert stock_structure.status_code == 200, stock_structure.text
    assert backtest_performance.status_code == 200, backtest_performance.text

    admin_payload = admin_preflight.json()
    scanner_payload = scanner_status.json()
    stock_payload = stock_structure.json()
    backtest_payload = backtest_performance.json()

    assert admin_payload["contractVersion"] == PREFLIGHT_CONTRACT_VERSION
    assert scanner_payload["dataReadiness"]["universeReadiness"]["state"] == "available"
    assert scanner_payload["dataReadiness"]["quoteReadiness"]["state"] == "available"
    assert scanner_payload["dataReadiness"]["historyReadiness"]["state"] == "partial"
    assert scanner_payload["dataReadiness"]["benchmarkReadiness"]["state"] == "available"
    assert stock_payload["symbol"] == "ORCL"
    assert "structureComputation" in stock_payload
    assert "historicalOhlcvReadiness" in stock_payload
    assert stock_payload["confidence"] == "low"
    assert backtest_payload["scope"] == "overall"
    assert backtest_payload["execution_readiness"]["contract_version"] == "backtest_execution_readiness_v1"
    assert backtest_payload["data_status"] in {"ready", "fixture_or_example_data"}

    for payload in (scanner_payload, stock_payload, backtest_payload):
        assert payload.get("contractVersion") != PREFLIGHT_CONTRACT_VERSION
        assert PREFLIGHT_CONTRACT_VERSION not in _json_text(payload)


def test_mac118_app_route_table_binds_four_urls_to_distinct_handlers() -> None:
    app = FastAPI()
    app.include_router(api_v1_router)

    route_handlers = {
        (method, route.path): route.endpoint
        for route in iter_effective_api_routes(app.routes)
        for method in route.methods or set()
        if method not in {"HEAD", "OPTIONS"}
    }

    assert route_handlers[("GET", "/api/v1/admin/historical-ohlcv/cache-preflight")] is (
        market_provider_operations.get_historical_ohlcv_cache_preflight
    )
    assert route_handlers[("GET", "/api/v1/scanner/status")] is scanner.get_scanner_operational_status
    assert route_handlers[("GET", "/api/v1/stocks/{stock_code}/structure-decision")] is (
        stocks.get_stock_structure_decision
    )
    assert route_handlers[("GET", "/api/v1/backtest/performance")] is backtest.get_backtest_performance
    assert len(
        {
            route_handlers[("GET", "/api/v1/admin/historical-ohlcv/cache-preflight")],
            route_handlers[("GET", "/api/v1/scanner/status")],
            route_handlers[("GET", "/api/v1/stocks/{stock_code}/structure-decision")],
            route_handlers[("GET", "/api/v1/backtest/performance")],
        }
    ) == 4
