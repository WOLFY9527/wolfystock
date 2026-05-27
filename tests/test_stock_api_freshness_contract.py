from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import stocks


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    return TestClient(app)


def test_quote_endpoint_exposes_provider_source_and_market_timestamp_without_breaking_existing_fields() -> None:
    service = SimpleNamespace(
        get_realtime_quote=lambda stock_code: {
            "stock_code": stock_code,
            "stock_name": "Apple",
            "current_price": 214.55,
            "change": 2.35,
            "change_percent": 1.11,
            "open": 213.0,
            "high": 215.0,
            "low": 212.5,
            "prev_close": 212.2,
            "volume": 1000.0,
            "amount": 214550.0,
            "update_time": "2026-05-28T09:31:00Z",
            "source": "alpaca",
            "source_type": "provider_runtime",
            "market_timestamp": "2026-05-28T09:30:00Z",
            "observed_at": "2026-05-28T09:31:00Z",
            "freshness": "live",
            "is_fallback": False,
            "is_stale": False,
            "is_partial": False,
            "is_synthetic": False,
            "sourceConfidence": {
                "source": "alpaca",
                "sourceLabel": "Alpaca",
                "asOf": "2026-05-28T09:30:00Z",
                "freshness": "live",
                "isFallback": False,
                "isStale": False,
                "isPartial": False,
                "isSynthetic": False,
                "isUnavailable": False,
                "confidenceWeight": 1.0,
                "coverage": None,
                "degradationReason": None,
                "capReason": None,
            },
        }
    )

    with patch("api.v1.endpoints.stocks.StockService", return_value=service):
        response = _client().get("/api/v1/stocks/AAPL/quote")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stock_code"] == "AAPL"
    assert payload["stock_name"] == "Apple"
    assert payload["current_price"] == 214.55
    assert payload["update_time"] == "2026-05-28T09:31:00Z"
    assert payload["source"] == "alpaca"
    assert payload["sourceType"] == "provider_runtime"
    assert payload["marketTimestamp"] == "2026-05-28T09:30:00Z"
    assert payload["observedAt"] == "2026-05-28T09:31:00Z"
    assert payload["freshness"] == "live"
    assert payload["isFallback"] is False
    assert payload["isStale"] is False
    assert payload["isPartial"] is False
    assert payload["isSynthetic"] is False
    assert payload["sourceConfidence"]["source"] == "alpaca"
    assert payload["sourceConfidence"]["asOf"] == "2026-05-28T09:30:00Z"
    assert payload["sourceConfidence"]["freshness"] == "live"
    assert payload["update_time"] != payload["marketTimestamp"]


def test_quote_endpoint_can_surface_non_fresh_placeholder_metadata_without_404() -> None:
    service = SimpleNamespace(
        get_realtime_quote=lambda stock_code: {
            "stock_code": stock_code,
            "stock_name": f"股票{stock_code}",
            "current_price": 0.0,
            "change": None,
            "change_percent": None,
            "open": None,
            "high": None,
            "low": None,
            "prev_close": None,
            "volume": None,
            "amount": None,
            "update_time": "2026-05-28T09:31:00Z",
            "source": "placeholder",
            "source_type": "synthetic_placeholder",
            "market_timestamp": None,
            "observed_at": "2026-05-28T09:31:00Z",
            "freshness": "synthetic",
            "is_fallback": False,
            "is_stale": False,
            "is_partial": True,
            "is_synthetic": True,
            "sourceConfidence": {
                "source": "placeholder",
                "sourceLabel": "Placeholder",
                "asOf": None,
                "freshness": "synthetic",
                "isFallback": False,
                "isStale": False,
                "isPartial": True,
                "isSynthetic": True,
                "isUnavailable": False,
                "confidenceWeight": 0.0,
                "coverage": None,
                "degradationReason": "provider_runtime_unavailable_placeholder",
                "capReason": None,
            },
        }
    )

    with patch("api.v1.endpoints.stocks.StockService", return_value=service):
        response = _client().get("/api/v1/stocks/AAPL/quote")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "placeholder"
    assert payload["sourceType"] == "synthetic_placeholder"
    assert payload["marketTimestamp"] is None
    assert payload["freshness"] == "synthetic"
    assert payload["isFallback"] is False
    assert payload["isPartial"] is True
    assert payload["isSynthetic"] is True
    assert payload["observedAt"] == payload["update_time"]
