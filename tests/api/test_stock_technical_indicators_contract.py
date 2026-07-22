from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import stocks
from src.services.stock_service import StockService


class _HistoryService:
    def __init__(self, payload: dict[str, Any] | None = None, *, error: Exception | None = None) -> None:
        self.payload = payload or {}
        self.error = error

    def get_history_data(self, **_kwargs: Any) -> dict[str, Any]:
        if self.error is not None:
            raise self.error
        return self.payload


class _StockServiceFacade(StockService):
    def __init__(self, history_service: _HistoryService) -> None:
        self._technical_history_service = history_service

    def get_history_data(self, **kwargs: Any) -> dict[str, Any]:
        return self._technical_history_service.get_history_data(**kwargs)


def _rows(count: int) -> list[dict[str, Any]]:
    start = date(2025, 1, 1)
    return [
        {
            "date": (start + timedelta(days=index)).isoformat(),
            "open": 99.0 + index,
            "high": 101.0 + index,
            "low": 98.0 + index,
            "close": 100.0 + index,
            "adjustedClose": 100.0 + index,
            "volume": 1_000.0 + index,
        }
        for index in range(count)
    ]


def _history(rows: list[dict[str, Any]], *, unavailable: bool = False) -> dict[str, Any]:
    return {
        "stock_code": "AAPL",
        "period": "daily",
        "source": "unavailable" if unavailable else "fixture_adjusted_history",
        "diagnostics": {
            "status": "unavailable" if unavailable else "ok",
            "reason": "provider_unavailable" if unavailable else "history_available",
        },
        "historicalOhlcvReadiness": {
            "providerState": "provider_unavailable" if unavailable else "available",
            "freshnessState": "unknown" if unavailable else "fresh",
        },
        "sourceConfidence": {
            "source": "unavailable" if unavailable else "fixture_adjusted_history",
            "sourceLabel": "Unavailable" if unavailable else "Deterministic adjusted history fixture",
            "asOf": rows[-1]["date"] if rows else None,
            "freshness": "unknown" if unavailable else "fresh",
            "isUnavailable": unavailable,
        },
        "data": rows,
    }


def _app(*, authenticated: bool = True) -> FastAPI:
    app = FastAPI()
    if authenticated:
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
    else:
        def _raise_unauthorized() -> None:
            raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Login required"})

        app.dependency_overrides[get_current_user] = _raise_unauthorized
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    return app


@pytest.mark.parametrize(
    ("rows", "unavailable", "expected_status"),
    [
        (_rows(205), False, "available"),
        (_rows(20), False, "partial"),
        ([], False, "unavailable"),
        ([], True, "provider_unavailable"),
    ],
)
def test_endpoint_runtime_contract_with_injected_history(
    rows: list[dict[str, Any]],
    unavailable: bool,
    expected_status: str,
) -> None:
    service = _StockServiceFacade(_HistoryService(_history(rows, unavailable=unavailable)))
    with patch("api.v1.endpoints.stocks.StockService", return_value=service):
        response = TestClient(_app()).get("/api/v1/stocks/aapl/technical-indicators")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "AAPL"
    assert payload["status"] == expected_status
    assert payload["source"] == ("unavailable" if unavailable else "fixture_adjusted_history")
    assert payload["validBars"] == (len(rows) if rows and not unavailable else 0)
    values = [item["value"] for item in payload["indicators"].values()]
    if expected_status == "available":
        assert all(value is not None for value in values)
    elif expected_status == "partial":
        assert any(value is not None for value in values)
        assert any(value is None for value in values)
    else:
        assert all(value is None for value in values)


def test_endpoint_preserves_authentication_boundary() -> None:
    response = TestClient(_app(authenticated=False)).get("/api/v1/stocks/AAPL/technical-indicators")
    assert response.status_code == 401


def test_endpoint_unexpected_source_exception_is_safe_and_fail_closed() -> None:
    marker = "provider token rawPayload traceId secret"
    service = _StockServiceFacade(_HistoryService(error=RuntimeError(marker)))
    with patch("api.v1.endpoints.stocks.StockService", return_value=service):
        response = TestClient(_app()).get("/api/v1/stocks/AAPL/technical-indicators")

    assert response.status_code == 500
    payload = response.json()
    assert payload["detail"]["error"] == "internal_error"
    assert payload["detail"]["message"] == "Technical indicators are temporarily unavailable."
    assert marker not in response.text


def test_openapi_schema_has_no_numeric_indicator_defaults() -> None:
    schema = _app().openapi()["components"]["schemas"]
    indicator_schema = schema["StockTechnicalIndicatorValue"]
    response_schema = schema["StockTechnicalIndicatorsResponse"]

    assert "default" not in indicator_schema["properties"]["value"]
    assert response_schema["properties"]["indicators"]
