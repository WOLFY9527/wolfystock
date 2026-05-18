# -*- coding: utf-8 -*-
"""Endpoint-level regressions for slow or hung market overview providers."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from api.v1.endpoints import market, market_overview
from src.services.market_overview_service import MarketOverviewService


CN_TZ = timezone(timedelta(hours=8))


@pytest.fixture(autouse=True)
def _reset_market_state() -> None:
    MarketOverviewService._market_cache.clear()
    MarketOverviewService._market_data_cache.clear()
    yield
    MarketOverviewService._market_cache.wait_for_refreshes(timeout=2)
    MarketOverviewService._market_cache.clear()
    MarketOverviewService._market_data_cache.clear()


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    app.include_router(market_overview.router, prefix="/api/v1/market-overview")
    return TestClient(app)


def _assert_bounded_non_live(payload: dict, elapsed: float) -> None:
    assert elapsed < 0.35
    assert payload["freshness"] in {"fallback", "stale"}
    assert payload["freshness"] != "live"
    assert payload["providerHealth"]["status"] not in {"live"}
    assert payload["providerHealth"]["isRefreshing"] is True


def test_market_sentiment_endpoint_serves_stale_snapshot_while_hung_refresh_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    stale_as_of = datetime(2026, 5, 15, 9, 0, tzinfo=CN_TZ).isoformat(timespec="seconds")
    MarketOverviewService._market_cache.set(
        MarketOverviewService.MARKET_SENTIMENT_CACHE_KEY,
        {
            "items": [
                {
                    "symbol": "FGI",
                    "label": "Fear & Greed",
                    "price": 33,
                    "change": -2.0,
                    "trend": [38, 36, 33],
                    "last_update": stale_as_of,
                    "source": "cnn",
                    "sourceLabel": "CNN",
                    "error": None,
                }
            ],
            "last_update": stale_as_of,
            "updatedAt": stale_as_of,
            "asOf": stale_as_of,
            "error": None,
            "fallback_used": False,
            "source": "cnn",
            "sourceLabel": "CNN",
        },
        ttl_seconds=1,
    )
    MarketOverviewService._market_cache.get(MarketOverviewService.MARKET_SENTIMENT_CACHE_KEY).expires_at = (
        MarketOverviewService._market_cache.get(MarketOverviewService.MARKET_SENTIMENT_CACHE_KEY).fetched_at - timedelta(seconds=1)
    )

    monkeypatch.setattr(MarketOverviewService, "MARKET_COLD_START_TIMEOUT_SECONDS", 0.05, raising=False)

    def slow_refresh(self: MarketOverviewService) -> dict:
        time.sleep(0.6)
        raise TimeoutError("cnn timeout")

    monkeypatch.setattr(MarketOverviewService, "_fetch_market_sentiment_snapshot", slow_refresh, raising=True)

    started = time.monotonic()
    response = client.get("/api/v1/market/sentiment")
    elapsed = time.monotonic() - started

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "cnn"
    assert payload["items"][0]["price"] == 33
    assert payload["isStale"] is True
    _assert_bounded_non_live(payload, elapsed)


def test_market_overview_macro_endpoint_returns_fallback_quickly_when_official_macro_hangs(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    monkeypatch.setattr(MarketOverviewService, "MARKET_COLD_START_TIMEOUT_SECONDS", 0.05, raising=False)

    def slow_macro(*, limit: int = 2, timeout: float | None = None) -> dict:
        time.sleep(0.6)
        raise TimeoutError(f"macro timeout {timeout}")

    monkeypatch.setattr(
        "src.services.market_overview_service.fetch_treasury_daily_rate_observation_points",
        slow_macro,
    )

    started = time.monotonic()
    response = client.get("/api/v1/market-overview/macro")
    elapsed = time.monotonic() - started

    assert response.status_code == 200
    payload = response.json()
    assert payload["panel_name"] == "MacroIndicatorsCard"
    assert payload["items"]
    assert payload["isFallback"] is True
    _assert_bounded_non_live(payload, elapsed)


def test_market_fx_commodities_endpoint_returns_fallback_quickly_when_proxy_hangs(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    monkeypatch.setattr(MarketOverviewService, "MARKET_COLD_START_TIMEOUT_SECONDS", 0.05, raising=False)

    def slow_history(ticker: str, *, timeout: float = 1.5) -> object:
        time.sleep(0.6)
        raise TimeoutError(f"{ticker} timeout {timeout}")

    monkeypatch.setattr("src.services.market_overview_service.fetch_yfinance_quote_history_frame", slow_history)

    started = time.monotonic()
    response = client.get("/api/v1/market/fx-commodities")
    elapsed = time.monotonic() - started

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "fallback"
    assert payload["isFallback"] is True
    assert payload["items"]
    _assert_bounded_non_live(payload, elapsed)


def test_market_futures_endpoint_returns_fallback_quickly_when_proxy_hangs(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    monkeypatch.setattr(MarketOverviewService, "MARKET_COLD_START_TIMEOUT_SECONDS", 0.05, raising=False)

    def slow_history(ticker: str, *, timeout: float = 1.5) -> object:
        time.sleep(0.6)
        raise TimeoutError(f"{ticker} timeout {timeout}")

    monkeypatch.setattr("src.services.market_overview_service.fetch_yfinance_quote_history_frame", slow_history)

    started = time.monotonic()
    response = client.get("/api/v1/market/futures")
    elapsed = time.monotonic() - started

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "fallback"
    assert payload["isFallback"] is True
    assert payload["items"]
    _assert_bounded_non_live(payload, elapsed)


def test_market_temperature_endpoint_returns_fallback_quickly_when_inputs_hang(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    monkeypatch.setattr(MarketOverviewService, "MARKET_COLD_START_TIMEOUT_SECONDS", 0.05, raising=False)

    def slow_inputs(self: MarketOverviewService, *, budget_seconds: float | None = None) -> dict:
        time.sleep(0.6)
        raise TimeoutError(f"temperature inputs timeout {budget_seconds}")

    monkeypatch.setattr(MarketOverviewService, "_build_market_temperature_inputs", slow_inputs, raising=True)

    started = time.monotonic()
    response = client.get("/api/v1/market/temperature")
    elapsed = time.monotonic() - started

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "fallback"
    assert payload["isFallback"] is True
    assert payload["scores"]["overall"]["label"] == "数据不足"
    _assert_bounded_non_live(payload, elapsed)


def test_market_briefing_endpoint_returns_fallback_quickly_when_inputs_hang(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    monkeypatch.setattr(MarketOverviewService, "MARKET_COLD_START_TIMEOUT_SECONDS", 0.05, raising=False)

    def slow_inputs(self: MarketOverviewService, *, budget_seconds: float | None = None) -> dict:
        time.sleep(0.6)
        raise TimeoutError(f"briefing inputs timeout {budget_seconds}")

    monkeypatch.setattr(MarketOverviewService, "_build_market_temperature_inputs", slow_inputs, raising=True)

    started = time.monotonic()
    response = client.get("/api/v1/market/market-briefing")
    elapsed = time.monotonic() - started

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "fallback"
    assert payload["isFallback"] is True
    assert payload["items"]
    _assert_bounded_non_live(payload, elapsed)
