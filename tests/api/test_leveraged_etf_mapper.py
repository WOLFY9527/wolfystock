# -*- coding: utf-8 -*-
"""API contract tests for the leveraged ETF mapper endpoint."""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.v1.endpoints.leveraged_etf_mapper as leveraged_etf_mapper
from api.deps import CurrentUser, get_current_user


def _client() -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id="watchlist-member",
        username="watchlist-member",
        display_name="Watchlist Member",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )
    app.include_router(leveraged_etf_mapper.router, prefix="/api/v1/leveraged-etf-mapper")
    return TestClient(app)


def _pure_boundary_patches() -> ExitStack:
    stack = ExitStack()
    stack.enter_context(
        patch(
            "data_provider.base.DataFetcherManager.get_realtime_quote",
            side_effect=AssertionError("leveraged ETF mapper must not fetch quotes"),
        )
    )
    stack.enter_context(
        patch(
            "data_provider.base.DataFetcherManager.get_daily_data",
            side_effect=AssertionError("leveraged ETF mapper must not fetch provider history"),
        )
    )
    stack.enter_context(
        patch(
            "src.services.stock_service.StockService.get_realtime_quote",
            side_effect=AssertionError("leveraged ETF mapper must not use quote flow"),
        )
    )
    stack.enter_context(
        patch(
            "src.services.market_cache.MarketCache.get_or_refresh",
            side_effect=AssertionError("leveraged ETF mapper must not use MarketCache"),
        )
    )
    stack.enter_context(
        patch(
            "src.services.portfolio_service.PortfolioService.get_portfolio_snapshot",
            side_effect=AssertionError("leveraged ETF mapper must not read portfolio state"),
        )
    )
    stack.enter_context(
        patch(
            "src.services.portfolio_service.PortfolioService.record_cash_ledger",
            side_effect=AssertionError("leveraged ETF mapper must not mutate portfolio ledger"),
        )
    )
    return stack


def test_mappings_endpoint_returns_curated_contract_without_runtime_calls() -> None:
    with _pure_boundary_patches():
        response = _client().get("/api/v1/leveraged-etf-mapper/mappings")

    assert response.status_code == 200
    payload = response.json()
    mapping_by_symbol = {item["etfSymbol"]: item for item in payload["mappings"]}
    assert set(mapping_by_symbol) == {"TSLL", "NVDL", "MSTU", "CONL", "TQQQ", "SOXL"}
    assert mapping_by_symbol["MSTU"]["underlyingSymbol"] == "MSTR"
    assert mapping_by_symbol["SOXL"]["underlyingSymbol"] == "SOXX"
    assert mapping_by_symbol["SOXL"]["referenceType"] == "proxy_etf"
    assert payload["metadata"]["externalProviderCalls"] is False
    assert payload["metadata"]["marketCacheMutation"] is False
    assert payload["metadata"]["noOrderPlacement"] is True
    assert payload["metadata"]["noPortfolioMutation"] is True
    assert "daily_reset_path_dependency" in payload["limitationCodes"]


def test_calculate_endpoint_returns_forward_and_reverse_pure_estimates() -> None:
    request_payload = {
        "etfSymbol": "TQQQ",
        "underlyingSymbol": "QQQ",
        "etfRefPrice": 60.0,
        "underlyingRefPrice": 500.0,
        "underlyingTargetPrice": 525.0,
        "etfTargetPrice": 69.0,
    }

    with _pure_boundary_patches():
        response = _client().post("/api/v1/leveraged-etf-mapper/calculate", json=request_payload)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["mapping"]["etfSymbol"] == "TQQQ"
    assert payload["mapping"]["underlyingSymbol"] == "QQQ"
    assert payload["estimatedEtfPrice"] == 69.0
    assert payload["impliedUnderlyingPrice"] == 525.0
    assert payload["metadata"]["calculationOnly"] is True
    assert payload["metadata"]["externalProviderCalls"] is False
    assert payload["metadata"]["providerRuntimeChanged"] is False
    assert payload["metadata"]["marketCacheMutation"] is False
    assert payload["metadata"]["noOrderPlacement"] is True
    assert payload["metadata"]["noPortfolioMutation"] is True
    assert payload["metadata"]["notInvestmentAdvice"] is True
    assert {
        "same_day_reference_anchor_approximation",
        "daily_reset_path_dependency",
        "fees_financing_tracking_error_excluded",
        "overnight_multi_day_drift_not_modelled",
        "not_investment_advice",
        "no_order_placement",
        "no_portfolio_mutation",
    } <= set(payload["limitationCodes"])


def test_calculate_endpoint_rejects_missing_reference_price() -> None:
    response = _client().post(
        "/api/v1/leveraged-etf-mapper/calculate",
        json={
            "etfSymbol": "TSLL",
            "underlyingSymbol": "TSLA",
            "underlyingRefPrice": 100.0,
            "underlyingTargetPrice": 110.0,
        },
    )

    assert response.status_code == 422


def test_calculate_endpoint_rejects_invalid_mapping_mismatch() -> None:
    response = _client().post(
        "/api/v1/leveraged-etf-mapper/calculate",
        json={
            "etfSymbol": "TSLL",
            "underlyingSymbol": "NVDA",
            "etfRefPrice": 10.0,
            "underlyingRefPrice": 100.0,
            "underlyingTargetPrice": 110.0,
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "unsupported_mapping_mismatch"


def test_calculate_endpoint_returns_invalid_low_confidence_for_non_positive_forward_output() -> None:
    response = _client().post(
        "/api/v1/leveraged-etf-mapper/calculate",
        json={
            "etfSymbol": "TQQQ",
            "underlyingSymbol": "QQQ",
            "etfRefPrice": 60.0,
            "underlyingRefPrice": 500.0,
            "underlyingTargetPrice": 300.0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "invalid_low_confidence"
    assert payload["estimatedEtfPrice"] is None
    assert payload["invalidReason"] == "non_positive_estimated_etf_price"
    assert "non_positive_estimated_etf_price" in payload["warningCodes"]
