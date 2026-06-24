import json
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import stocks


def _regular_user() -> CurrentUser:
    return CurrentUser(
        user_id="user-1",
        username="alice",
        display_name="Alice",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )


def _raise_unauthorized() -> None:
    raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Login required"})


def _client(*, authenticated: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    app.dependency_overrides[get_current_user] = _regular_user if authenticated else _raise_unauthorized
    return TestClient(app)


def test_quote_endpoint_allows_guest_access_without_auth_dependency() -> None:
    service = SimpleNamespace(
        get_realtime_quote=lambda stock_code: {
            "stock_code": stock_code,
            "stock_name": f"{stock_code} Corp.",
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
        client = _client(authenticated=False)
        try:
            responses = {
                symbol: client.get(f"/api/v1/stocks/{symbol}/quote")
                for symbol in ("ORCL", "600519")
            }
        finally:
            client.close()

    assert {symbol: response.status_code for symbol, response in responses.items()} == {
        "ORCL": 200,
        "600519": 200,
    }
    for symbol, response in responses.items():
        payload = response.json()
        assert payload["stock_code"] == symbol
        assert payload["source"] == "Alpaca"
        assert "sourceType" not in payload
        assert "sourceConfidence" not in payload


def test_quote_endpoint_internal_error_is_consumer_safe_for_guest() -> None:
    service = SimpleNamespace(
        get_realtime_quote=lambda stock_code: (_ for _ in ()).throw(
            RuntimeError(
                "provider_runtime requestId=req-raw traceId=trace-raw "
                "cacheKey=cache-raw token=secret should not leak"
            )
        )
    )

    with patch("api.v1.endpoints.stocks.StockService", return_value=service):
        response = _client(authenticated=False).get("/api/v1/stocks/ORCL/quote")

    assert response.status_code == 500
    payload = response.json()["detail"]
    assert payload["error"] == "internal_error"
    assert "requestId" not in json.dumps(payload, ensure_ascii=False)
    assert "traceId" not in json.dumps(payload, ensure_ascii=False)
    assert "cacheKey" not in json.dumps(payload, ensure_ascii=False)
    assert "token" not in json.dumps(payload, ensure_ascii=False)


def test_quote_endpoint_exposes_safe_source_label_and_market_timestamp_without_runtime_taxonomy() -> None:
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
    assert payload["source"] == "Alpaca"
    assert "sourceType" not in payload
    assert payload["marketTimestamp"] == "2026-05-28T09:30:00Z"
    assert payload["observedAt"] == "2026-05-28T09:31:00Z"
    assert payload["freshness"] == "live"
    assert payload["isFallback"] is False
    assert payload["isStale"] is False
    assert payload["isPartial"] is False
    assert payload["isSynthetic"] is False
    assert "sourceConfidence" not in payload
    serialized = response.text
    for marker in ("provider_runtime", "providerName", "providerClass", "providerAttempted", "traceId", "requestId"):
        assert marker not in serialized
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
    assert payload["source"] == "Placeholder"
    assert "sourceType" not in payload
    assert "sourceConfidence" not in payload
    assert "marketTimestamp" not in payload
    assert payload["freshness"] == "synthetic"
    assert payload["isFallback"] is False
    assert payload["isPartial"] is True
    assert payload["isSynthetic"] is True
    assert payload["observedAt"] == payload["update_time"]


def test_intraday_endpoint_preserves_old_fields_and_adds_proxy_provenance_metadata() -> None:
    service = SimpleNamespace(
        get_intraday_data=lambda stock_code, interval, range_period: {
            "stock_code": stock_code,
            "stock_name": "Apple",
            "interval": interval,
            "range": range_period,
            "source": "yfinance",
            "source_type": "unofficial_proxy",
            "freshness": "delayed",
            "is_fallback": False,
            "is_stale": False,
            "is_partial": False,
            "is_synthetic": False,
            "is_unavailable": False,
            "sourceConfidence": {
                "source": "yfinance",
                "sourceLabel": "Yahoo Finance intraday proxy",
                "asOf": "2026-05-28T09:35:00Z",
                "freshness": "delayed",
                "isFallback": False,
                "isStale": False,
                "isPartial": False,
                "isSynthetic": False,
                "isUnavailable": False,
                "confidenceWeight": 0.7,
                "coverage": 1.0,
                "degradationReason": "delayed_source",
                "capReason": None,
            },
            "data": [
                {
                    "time": "2026-05-28T09:35:00Z",
                    "open": 214.1,
                    "high": 214.8,
                    "low": 213.9,
                    "close": 214.5,
                    "volume": 1200.0,
                }
            ],
        }
    )

    with patch("api.v1.endpoints.stocks.StockService", return_value=service):
        response = _client().get("/api/v1/stocks/AAPL/intraday", params={"interval": "5m", "range": "1d"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["stock_code"] == "AAPL"
    assert payload["stock_name"] == "Apple"
    assert payload["interval"] == "5m"
    assert payload["range"] == "1d"
    assert payload["source"] == "yfinance"
    assert payload["sourceType"] == "unofficial_proxy"
    assert payload["freshness"] == "delayed"
    assert payload["isFallback"] is False
    assert payload["isStale"] is False
    assert payload["isPartial"] is False
    assert payload["isSynthetic"] is False
    assert payload["isUnavailable"] is False
    assert payload["sourceConfidence"]["source"] == "yfinance"
    assert payload["sourceConfidence"]["asOf"] == "2026-05-28T09:35:00Z"
    assert payload["sourceConfidence"]["freshness"] == "delayed"
    assert payload["data"] == [
        {
            "time": "2026-05-28T09:35:00Z",
            "open": 214.1,
            "high": 214.8,
            "low": 213.9,
            "close": 214.5,
            "volume": 1200.0,
        }
    ]
