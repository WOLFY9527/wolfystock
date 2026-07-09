from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import stocks
from src.services.us_history_helper import LOCAL_US_PARQUET_SOURCE


class _FailingStockService:
    def __init__(self, message: str) -> None:
        self.message = message

    def get_intraday_data(self, **kwargs):
        raise RuntimeError(self.message)

    def get_history_data(self, **kwargs):
        raise RuntimeError(self.message)


def test_stock_history_endpoint_reads_cached_us_bars_without_provider_network() -> None:
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    client = TestClient(app)
    cached_frame = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-06-23"),
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.5,
                "volume": 1000,
                "amount": 101500,
                "pct_chg": 1.2,
            },
            {
                "date": pd.Timestamp("2026-06-24"),
                "open": 102.0,
                "high": 104.0,
                "low": 101.0,
                "close": 103.5,
                "volume": 1200,
                "amount": 124200,
                "pct_chg": 1.97,
            },
        ]
    )
    manager = SimpleNamespace(get_stock_name=lambda stock_code: f"{stock_code} Inc.")

    with (
        patch("data_provider.base.DataFetcherManager", return_value=manager),
        patch(
            "src.services.stock_service.fetch_daily_history_with_local_us_fallback",
            return_value=(cached_frame, LOCAL_US_PARQUET_SOURCE),
        ) as fetch_history,
    ):
        response = client.get("/api/v1/stocks/ORCL/history", params={"period": "daily", "days": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["stock_code"] == "ORCL"
    assert payload["source"] == LOCAL_US_PARQUET_SOURCE
    assert payload["diagnostics"]["status"] == "ok"
    assert payload["diagnostics"]["rows"] == 2
    assert payload["sourceConfidence"]["isFallback"] is True
    assert payload["data"] == [
        {
            "date": "2026-06-23",
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "close": 101.5,
            "volume": 1000.0,
            "amount": 101500.0,
            "change_percent": 1.2,
        },
        {
            "date": "2026-06-24",
            "open": 102.0,
            "high": 104.0,
            "low": 101.0,
            "close": 103.5,
            "volume": 1200.0,
            "amount": 124200.0,
            "change_percent": 1.97,
        },
    ]
    fetch_history.assert_called_once_with(
        "ORCL",
        days=2,
        manager=manager,
        log_context="[stock history]",
        allow_provider_fallback=True,
    )


def test_stock_history_endpoint_exposes_90_bar_ohlcv_readiness_when_cache_sufficient() -> None:
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    client = TestClient(app)
    cached_frame = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-01-01") + pd.Timedelta(days=index),
                "open": 100.0 + index,
                "high": 101.0 + index,
                "low": 99.0 + index,
                "close": 100.5 + index,
                "volume": 1000 + index,
            }
            for index in range(90)
        ]
    )
    manager = SimpleNamespace(get_stock_name=lambda stock_code: f"{stock_code} Inc.")

    with (
        patch("data_provider.base.DataFetcherManager", return_value=manager),
        patch(
            "src.services.stock_service.fetch_daily_history_with_local_us_fallback",
            return_value=(cached_frame, LOCAL_US_PARQUET_SOURCE),
        ),
    ):
        response = client.get("/api/v1/stocks/AAPL/history", params={"period": "daily", "days": 90})

    assert response.status_code == 200
    payload = response.json()
    readiness = payload["historicalOhlcvReadiness"]
    assert len(payload["data"]) == 90
    assert readiness["providerState"] == "available"
    assert readiness["overallState"] == "ready"
    assert readiness["requiredBars"] == 90
    assert readiness["usableBars"] == 90
    assert readiness["missingBars"] == 0
    assert readiness["missingRequirements"] == []


def test_stock_history_endpoint_reports_insufficient_coverage_without_provider_missing() -> None:
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    client = TestClient(app)
    cached_frame = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-04-01") + pd.Timedelta(days=index),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1000,
            }
            for index in range(40)
        ]
    )
    manager = SimpleNamespace(get_stock_name=lambda stock_code: f"{stock_code} Inc.")

    with (
        patch("data_provider.base.DataFetcherManager", return_value=manager),
        patch(
            "src.services.stock_service.fetch_daily_history_with_local_us_fallback",
            return_value=(cached_frame, LOCAL_US_PARQUET_SOURCE),
        ),
    ):
        response = client.get("/api/v1/stocks/TSLA/history", params={"period": "daily", "days": 90})

    assert response.status_code == 200
    readiness = response.json()["historicalOhlcvReadiness"]
    assert readiness["providerState"] == "available"
    assert readiness["overallState"] == "blocked"
    assert readiness["requiredBars"] == 90
    assert readiness["usableBars"] == 40
    assert readiness["missingBars"] == 50
    assert readiness["missingRequirements"] == ["insufficient_history"]


def test_stock_intraday_internal_error_does_not_echo_provider_exception() -> None:
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    client = TestClient(app)
    marker = "Traceback provider token secret raw failure"

    with patch("api.v1.endpoints.stocks.StockService", return_value=_FailingStockService(marker)):
        response = client.get("/api/v1/stocks/AAPL/intraday")

    payload = response.json()
    assert response.status_code == 500
    assert payload["detail"]["error"] == "internal_error"
    assert payload["detail"]["code"] == "internal_error"
    assert payload["detail"]["message"] == "获取日内行情失败"
    assert marker not in response.text


def test_stock_history_internal_error_does_not_echo_provider_exception() -> None:
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    client = TestClient(app)
    marker = "Traceback provider token secret raw failure"

    with patch("api.v1.endpoints.stocks.StockService", return_value=_FailingStockService(marker)):
        response = client.get("/api/v1/stocks/AAPL/history")

    payload = response.json()
    assert response.status_code == 500
    assert payload["detail"]["error"] == "internal_error"
    assert payload["detail"]["code"] == "internal_error"
    assert payload["detail"]["message"] == "获取历史行情失败"
    assert marker not in response.text
