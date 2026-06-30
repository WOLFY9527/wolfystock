from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import stocks
from src.services.starter_market_data import STARTER_MARKET_DATA_SYMBOLS


class _NoQuoteAdapter:
    def get_quote_snapshot(self, stock_code: str):
        return None


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    return TestClient(app)


def test_starter_quote_endpoint_returns_structured_unavailable_instead_of_raw_404(monkeypatch) -> None:
    for key in (
        "LOCAL_US_QUOTE_SNAPSHOT_CACHE_PATH",
        "US_QUOTE_SNAPSHOT_CACHE_PATH",
        "WOLFYSTOCK_US_QUOTE_SNAPSHOT_CACHE_PATH",
        "QUOTE_SNAPSHOT_CACHE_PATH",
    ):
        monkeypatch.delenv(key, raising=False)

    with patch("src.services.stock_service.StockServiceProviderAdapter", return_value=_NoQuoteAdapter()):
        for symbol in STARTER_MARKET_DATA_SYMBOLS:
            response = _client().get(f"/api/v1/stocks/{symbol}/quote")

            assert response.status_code == 200
            payload = response.json()
            assert payload["stock_code"] == symbol
            assert payload["source"] == "Quote unavailable"
            assert payload["freshness"] == "unavailable"
            assert payload["isUnavailable"] is True
            assert payload["availabilityState"] == "missing"
            assert payload["providerState"] == "provider_missing"
            assert payload["unavailableReason"] == "quote_snapshot_missing"
            assert "current_price" not in payload
            assert "quote_snapshot_missing" in payload["missingRequirements"]
            assert payload["quoteReadiness"]["consumerSafe"] is True
            assert payload["sourceConfidence"]["source"] == "unavailable"


def test_starter_quote_endpoint_reads_real_local_quote_snapshot_with_source_and_freshness(tmp_path, monkeypatch) -> None:
    quote_cache = tmp_path / "quotes.json"
    as_of = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    quote_cache.write_text(
        json.dumps(
            {
                "quotes": [
                    {
                        "symbol": "AAPL",
                        "market": "us",
                        "last": 185.25,
                        "previousClose": 184.0,
                        "volume": 1234567,
                        "asOf": as_of,
                        "currency": "USD",
                        "source": "operator_cache",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LOCAL_US_QUOTE_SNAPSHOT_CACHE_PATH", str(quote_cache))

    with patch("src.services.stock_service.StockServiceProviderAdapter", return_value=_NoQuoteAdapter()):
        response = _client().get("/api/v1/stocks/AAPL/quote")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stock_code"] == "AAPL"
    assert payload["current_price"] == 185.25
    assert payload["source"] == "Operator Cache"
    assert payload["sourceType"] == "local_quote_snapshot_cache"
    assert payload["freshness"] == "cached"
    assert payload["marketTimestamp"] == as_of
    assert payload["availabilityState"] == "available"
    assert payload["providerState"] == "available"
    assert payload["quoteReadiness"]["sourceFamilies"] == ["operator_cache"]
    assert payload["sourceConfidence"]["source"] == "operator_cache"
    assert payload["sourceConfidence"]["freshness"] == "cached"
