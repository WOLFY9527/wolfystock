# -*- coding: utf-8 -*-
"""Tests for consumer-safe US fundamentals normalization."""

from __future__ import annotations

from src.services.us_fundamentals_service import USFundamentalsService


def test_us_fundamentals_service_normalizes_provider_fields_without_network() -> None:
    service = USFundamentalsService(
        fundamentals_fetcher=lambda symbol: {
            "companyName": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "marketCap": 3_000_000_000_000,
            "totalRevenue": 390_000_000_000,
            "operatingMargins": 0.31,
            "trailingPE": 29.4,
            "_meta": {
                "field_periods": {
                    "marketCap": "latest",
                    "totalRevenue": "ttm",
                    "operatingMargins": "ttm",
                    "trailingPE": "ttm",
                },
                "field_sources": {
                    "companyName": "yfinance",
                    "sector": "yfinance",
                    "industry": "yfinance",
                    "marketCap": "yfinance",
                    "totalRevenue": "yfinance",
                    "operatingMargins": "yfinance",
                    "trailingPE": "yfinance",
                },
            },
        },
        now_fn=lambda: "2026-07-01T00:00:00+00:00",
    )

    payload = service.get_us_fundamentals("aapl")

    assert payload["symbol"] == "AAPL"
    assert payload["state"] == "partial"
    assert payload["companyName"] == "Apple Inc."
    assert payload["sector"] == "Technology"
    assert payload["industry"] == "Consumer Electronics"
    assert payload["marketCap"] == 3_000_000_000_000.0
    assert payload["revenueTtm"] == 390_000_000_000.0
    assert payload["profitabilityMargin"] == 0.31
    assert payload["valuationRatio"] == 29.4
    assert payload["fiscalPeriod"] == "mixed"
    assert payload["asOf"] == "2026-07-01T00:00:00+00:00"
    assert payload["source"] == "yfinance"
    assert payload["freshness"] == "current"
    assert payload["fieldsAvailable"] == [
        "companyName",
        "sector",
        "industry",
        "marketCap",
        "revenueTtm",
        "profitabilityMargin",
        "valuationRatio",
    ]
    assert payload["missingFieldReasons"]["fiscalPeriod"] == "mixed_periods"
    assert payload["missingFieldReasons"]["source"] == ""
    assert "provider" not in payload


def test_us_fundamentals_service_returns_partial_with_missing_reasons() -> None:
    service = USFundamentalsService(
        fundamentals_fetcher=lambda symbol: {
            "companyName": "NVIDIA Corporation",
            "marketCap": 2_900_000_000_000,
            "_meta": {"field_periods": {"marketCap": "latest"}, "field_sources": {"marketCap": "yfinance"}},
        },
        now_fn=lambda: "2026-07-01T00:00:00+00:00",
    )

    payload = service.get_us_fundamentals("NVDA")

    assert payload["state"] == "partial"
    assert payload["companyName"] == "NVIDIA Corporation"
    assert payload["marketCap"] == 2_900_000_000_000.0
    assert payload["revenueTtm"] is None
    assert payload["profitabilityMargin"] is None
    assert payload["valuationRatio"] is None
    assert payload["missingFieldReasons"]["sector"] == "provider_field_missing"
    assert payload["missingFieldReasons"]["industry"] == "provider_field_missing"
    assert payload["missingFieldReasons"]["revenueTtm"] == "provider_field_missing"
    assert payload["missingFieldReasons"]["profitabilityMargin"] == "provider_field_missing"
    assert payload["missingFieldReasons"]["valuationRatio"] == "provider_field_missing"


def test_us_fundamentals_service_fail_closes_provider_exception_without_raw_text() -> None:
    def _raise(_symbol: str) -> dict:
        raise RuntimeError("raw provider timeout with token=secret")

    service = USFundamentalsService(
        fundamentals_fetcher=_raise,
        now_fn=lambda: "2026-07-01T00:00:00+00:00",
    )

    payload = service.get_us_fundamentals("MSFT")
    serialized = str(payload)

    assert payload["state"] == "provider_unavailable"
    assert payload["source"] == "unavailable"
    assert payload["freshness"] == "unknown"
    assert payload["missingFieldReasons"]["companyName"] == "provider_unavailable"
    assert "raw provider timeout" not in serialized
    assert "secret" not in serialized


def test_us_fundamentals_service_marks_non_us_symbol_unsupported() -> None:
    service = USFundamentalsService(
        fundamentals_fetcher=lambda symbol: {"companyName": "Should not be called"},
        now_fn=lambda: "2026-07-01T00:00:00+00:00",
    )

    payload = service.get_us_fundamentals("600519")

    assert payload["state"] == "unsupported"
    assert payload["source"] == "unsupported"
    assert payload["missingFieldReasons"]["companyName"] == "unsupported_market"
