# -*- coding: utf-8 -*-
"""Consumer-safe stock symbol validation API contract tests."""

from __future__ import annotations

import json
import re
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import stocks as stocks_endpoint


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(stocks_endpoint.router, prefix="/api/v1/stocks")
    return TestClient(app)


class _FakeStockService:
    def __init__(self, result: dict[str, Any] | Exception) -> None:
        self.result = result
        self.calls: list[str] = []

    def validate_ticker_exists(self, stock_code: str) -> dict[str, Any]:
        self.calls.append(stock_code)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _assert_consumer_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    assert re.search(
        r"traceback|https?://|api[_-]?key|secret|cookie|session|token|trustLevel|"
        r"reasonCode|fallback|sourceType",
        text,
        re.IGNORECASE,
    ) is None


def test_stock_validate_endpoint_normalizes_us_symbol_and_reports_valid(monkeypatch) -> None:
    service = _FakeStockService({"stock_code": "AAPL", "exists": True, "stock_name": "Apple"})
    monkeypatch.setattr(stocks_endpoint, "StockService", lambda: service)

    response = _client().get("/api/v1/stocks/aapl/validate")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "stock_code": "AAPL",
        "normalized_symbol": "AAPL",
        "market": "us",
        "status": "valid",
        "valid": True,
        "exists": True,
        "stock_name": "Apple",
        "message": "Symbol verified.",
    }
    assert service.calls == ["AAPL"]
    _assert_consumer_safe(payload)


def test_stock_validate_endpoint_rejects_invalid_format_without_lookup(monkeypatch) -> None:
    service = _FakeStockService({"stock_code": "AAPL", "exists": True, "stock_name": "Apple"})
    monkeypatch.setattr(stocks_endpoint, "StockService", lambda: service)

    response = _client().get("/api/v1/stocks/AAPL$/validate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "invalid_format"
    assert payload["valid"] is False
    assert payload["exists"] is False
    assert payload["normalized_symbol"] == "AAPL$"
    assert service.calls == []
    _assert_consumer_safe(payload)


def test_stock_validate_endpoint_reports_market_mismatch_without_lookup(monkeypatch) -> None:
    service = _FakeStockService({"stock_code": "AAPL", "exists": True, "stock_name": "Apple"})
    monkeypatch.setattr(stocks_endpoint, "StockService", lambda: service)

    response = _client().get("/api/v1/stocks/AAPL/validate", params={"market": "cn"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "unsupported_market"
    assert payload["market"] == "cn"
    assert payload["valid"] is False
    assert payload["exists"] is False
    assert service.calls == []
    _assert_consumer_safe(payload)


def test_stock_validate_endpoint_reports_ambiguous_hk_shorthand_without_lookup(monkeypatch) -> None:
    service = _FakeStockService({"stock_code": "HK00700", "exists": True, "stock_name": "Tencent"})
    monkeypatch.setattr(stocks_endpoint, "StockService", lambda: service)

    response = _client().get("/api/v1/stocks/00700/validate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ambiguous"
    assert payload["normalized_symbol"] == "00700"
    assert payload["market"] is None
    assert payload["valid"] is False
    assert payload["exists"] is False
    assert service.calls == []
    _assert_consumer_safe(payload)


def test_stock_validate_endpoint_reports_unknown_when_lookup_cannot_confirm(monkeypatch) -> None:
    service = _FakeStockService({"stock_code": "HK00700", "exists": False, "stock_name": None})
    monkeypatch.setattr(stocks_endpoint, "StockService", lambda: service)

    response = _client().get("/api/v1/stocks/hk700/validate", params={"market": "hk"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["stock_code"] == "HK00700"
    assert payload["normalized_symbol"] == "HK00700"
    assert payload["market"] == "hk"
    assert payload["status"] == "unknown"
    assert payload["valid"] is False
    assert payload["exists"] is False
    assert payload["stock_name"] is None
    assert service.calls == ["HK00700"]
    _assert_consumer_safe(payload)


def test_stock_validate_endpoint_sanitizes_lookup_dependency_failure(monkeypatch) -> None:
    service = _FakeStockService(
        RuntimeError(
            "Traceback from https://provider.example/query?token=secret "
            "sourceType=provider_runtime trustLevel=internal"
        )
    )
    monkeypatch.setattr(stocks_endpoint, "StockService", lambda: service)

    response = _client().get("/api/v1/stocks/AAPL/validate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stock_code"] == "AAPL"
    assert payload["status"] == "unavailable"
    assert payload["valid"] is False
    assert payload["exists"] is False
    assert payload["stock_name"] is None
    assert service.calls == ["AAPL"]
    _assert_consumer_safe(payload)
