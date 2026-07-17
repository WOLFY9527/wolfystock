# -*- coding: utf-8 -*-
"""Consumer-safe stock symbol validation API contract tests."""

from __future__ import annotations

import json
import re
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import stocks as stocks_endpoint


def _client() -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id="stock-member",
        username="stock-member",
        display_name="Stock Member",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )
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


def test_stock_parse_import_json_success_path_remains_unchanged() -> None:
    response = _client().post(
        "/api/v1/stocks/parse-import",
        json={"text": "600519 贵州茅台\n000001 平安银行"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["codes"] == ["600519", "000001"]
    assert payload["items"][0] == {
        "code": "600519",
        "name": "贵州茅台",
        "confidence": "medium",
    }


def test_stock_parse_import_malformed_json_returns_bounded_invalid_input_detail() -> None:
    response = _client().post(
        "/api/v1/stocks/parse-import",
        data='{"text": "600519"',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    payload = response.json()
    detail = payload.get("detail", payload)
    assert detail["error"] == "invalid_json"
    assert detail["message"] == "JSON 解析失败"
    serialized = json.dumps(payload, ensure_ascii=False)
    for marker in ("Expecting", "line", "column", "char", "JSONDecodeError"):
        assert marker not in serialized
