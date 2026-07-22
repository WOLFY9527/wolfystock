from __future__ import annotations

import json
import math
from datetime import date, timedelta
from typing import Any

import pytest

from api.v1.schemas.stocks import StockTechnicalIndicatorsResponse
from src.services.stock_technical_indicators_service import (
    INDICATOR_MINIMUM_BARS,
    StockTechnicalIndicatorsService,
)


class _HistoryService:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def get_history_data(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(dict(kwargs))
        return self.payload


def _bars(count: int) -> list[dict[str, Any]]:
    start = date(2025, 1, 1)
    rows: list[dict[str, Any]] = []
    for index in range(count):
        close = 100.0 + index + ((index % 5) * 0.1)
        rows.append(
            {
                "date": (start + timedelta(days=index)).isoformat(),
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "adjustedClose": close,
                "volume": 1_000.0 + index,
            }
        )
    return rows


def _history(
    rows: list[dict[str, Any]],
    *,
    status: str = "ok",
    reason: str = "history_available",
    source: str = "fixture_adjusted_history",
    freshness: str = "fresh",
    provider_state: str = "available",
) -> dict[str, Any]:
    as_of = rows[-1]["date"] if rows else None
    return {
        "stock_code": "AAPL",
        "period": "daily",
        "source": source,
        "diagnostics": {"status": status, "reason": reason, "rows": len(rows)},
        "historicalOhlcvReadiness": {
            "providerState": provider_state,
            "overallState": "ready" if rows else "blocked",
            "freshnessState": freshness,
            "adjustmentState": "available" if rows else "missing",
        },
        "sourceConfidence": {
            "source": source,
            "provider": "fixture-provider",
            "sourceLabel": "Deterministic adjusted history fixture",
            "asOf": as_of,
            "freshness": freshness,
            "isStale": freshness == "stale",
            "isUnavailable": source == "unavailable",
        },
        "data": rows,
    }


def _calculate(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], _HistoryService]:
    history = _HistoryService(_history(rows))
    payload = StockTechnicalIndicatorsService(history_service=history).get_technical_indicators("aapl")
    return payload, history


def _values(payload: dict[str, Any]) -> list[Any]:
    return [item["value"] for item in payload["indicators"].values()]


def test_sufficient_adjusted_history_preserves_lineage_and_finite_values() -> None:
    payload, history = _calculate(_bars(max(INDICATOR_MINIMUM_BARS.values()) + 5))

    assert history.calls == [{"stock_code": "AAPL", "period": "daily", "days": 260}]
    assert payload["status"] == "available"
    assert payload["validBars"] == max(INDICATOR_MINIMUM_BARS.values()) + 5
    assert payload["source"] == "fixture_adjusted_history"
    assert payload["provider"] == "fixture-provider"
    assert payload["sourceLabel"] == "Deterministic adjusted history fixture"
    assert payload["asOf"] == payload["dataQuality"]["usableRange"]["end"]
    assert payload["adjustmentStatus"] == "adjusted"
    values = _values(payload)
    assert all(isinstance(value, float) and math.isfinite(value) for value in values)
    assert any(value != 0.0 for value in values)


def test_partial_history_exposes_only_qualified_indicators() -> None:
    payload, _ = _calculate(_bars(20))

    assert payload["status"] == "partial"
    assert payload["indicators"]["sma20"]["value"] is not None
    assert payload["indicators"]["bollingerUpper"]["value"] is not None
    assert payload["indicators"]["sma50"] == {
        "status": "unavailable",
        "value": None,
        "requiredBars": INDICATOR_MINIMUM_BARS["sma50"],
        "availableBars": 20,
        "reason": "insufficient_history",
        "asOf": payload["asOf"],
    }
    assert payload["dataQuality"]["reason"] == "partial_indicator_coverage"


def test_insufficient_history_never_emits_values_or_trend_classification() -> None:
    shortest_window = min(INDICATOR_MINIMUM_BARS.values())
    payload, _ = _calculate(_bars(shortest_window - 1))

    assert payload["status"] == "insufficient_history"
    assert all(value is None for value in _values(payload))
    assert payload["dataQuality"]["reason"] == "insufficient_history"
    serialized = json.dumps(payload, sort_keys=True).lower()
    for forbidden in ("trend", "neutral", "bullish", "bearish", "oversold", "overbought"):
        assert forbidden not in serialized


def test_empty_history_is_explicitly_unavailable_without_zero_payload() -> None:
    service = StockTechnicalIndicatorsService(history_service=_HistoryService(_history([], reason="history_unavailable")))
    payload = service.get_technical_indicators("AAPL")

    assert payload["status"] == "unavailable"
    assert payload["reason"] == "history_unavailable"
    assert payload["validBars"] == 0
    assert all(value is None for value in _values(payload))
    assert 0 not in _values(payload)


@pytest.mark.parametrize(
    "malformation",
    ["missing_close", "missing_adjusted_close", "non_finite_close", "duplicate_date", "unordered"],
)
def test_malformed_history_cannot_produce_usable_values(malformation: str) -> None:
    rows = _bars(max(INDICATOR_MINIMUM_BARS.values()) + 1)
    if malformation == "missing_close":
        rows[8].pop("close")
    elif malformation == "missing_adjusted_close":
        rows[8].pop("adjustedClose")
    elif malformation == "non_finite_close":
        rows[8]["close"] = float("inf")
        rows[8]["adjustedClose"] = float("inf")
    elif malformation == "duplicate_date":
        rows[8]["date"] = rows[7]["date"]
    else:
        rows[7], rows[8] = rows[8], rows[7]

    payload = StockTechnicalIndicatorsService(history_service=_HistoryService(_history(rows))).get_technical_indicators("AAPL")

    assert payload["status"] == "invalid_history"
    assert payload["validBars"] == 0
    assert payload["reason"] in {
        "missing_required_bar_field",
        "missing_adjusted_close",
        "non_finite_bar_value",
        "duplicate_bar",
        "non_monotonic_ordering",
    }
    assert all(value is None for value in _values(payload))


def test_provider_unavailable_state_overrides_contradictory_rows() -> None:
    rows = _bars(max(INDICATOR_MINIMUM_BARS.values()) + 1)
    history = _history(
        rows,
        status="unavailable",
        reason="provider_unavailable",
        source="unavailable",
        freshness="unknown",
        provider_state="provider_unavailable",
    )
    payload = StockTechnicalIndicatorsService(history_service=_HistoryService(history)).get_technical_indicators("AAPL")

    assert payload["status"] == "provider_unavailable"
    assert payload["reason"] == "provider_unavailable"
    assert payload["validBars"] == 0
    assert payload["dataQuality"]["observedBars"] == len(rows)
    assert all(value is None for value in _values(payload))


def test_provider_failure_diagnostics_override_rows_even_when_lineage_looks_available() -> None:
    rows = _bars(max(INDICATOR_MINIMUM_BARS.values()) + 1)
    history = _history(
        rows,
        status="unavailable",
        reason="history_failed",
        source="fixture_adjusted_history",
        provider_state="available",
    )
    payload = StockTechnicalIndicatorsService(history_service=_HistoryService(history)).get_technical_indicators("AAPL")

    assert payload["status"] == "provider_unavailable"
    assert payload["reason"] == "history_failed"
    assert payload["validBars"] == 0
    assert payload["dataQuality"]["observedBars"] == len(rows)
    assert all(value is None for value in _values(payload))


def test_stale_history_is_unavailable_even_when_rows_are_sufficient() -> None:
    rows = _bars(max(INDICATOR_MINIMUM_BARS.values()) + 1)
    history = _history(rows, freshness="stale")
    payload = StockTechnicalIndicatorsService(history_service=_HistoryService(history)).get_technical_indicators("AAPL")

    assert payload["status"] == "unavailable"
    assert payload["reason"] == "stale_history"
    assert payload["adjustmentStatus"] == "adjusted"
    assert payload["dataQuality"]["observedBars"] == len(rows)
    assert all(value is None for value in _values(payload))


@pytest.mark.parametrize("indicator", sorted(INDICATOR_MINIMUM_BARS))
def test_each_indicator_boundary_uses_canonical_minimum_window(indicator: str) -> None:
    required = INDICATOR_MINIMUM_BARS[indicator]

    below, _ = _calculate(_bars(required - 1))
    exact, _ = _calculate(_bars(required))
    above, _ = _calculate(_bars(required + 1))

    assert below["indicators"][indicator]["value"] is None
    assert below["indicators"][indicator]["requiredBars"] == required
    assert exact["indicators"][indicator]["status"] == "available"
    assert math.isfinite(exact["indicators"][indicator]["value"])
    assert above["indicators"][indicator]["status"] == "available"
    assert math.isfinite(above["indicators"][indicator]["value"])


def test_schema_serialization_keeps_unavailable_values_null_without_defaults() -> None:
    payload, _ = _calculate([])
    serialized = StockTechnicalIndicatorsResponse.model_validate(payload).model_dump(
        by_alias=True,
        exclude_none=False,
    )

    assert serialized["status"] == "unavailable"
    assert set(serialized["indicators"]) == set(INDICATOR_MINIMUM_BARS)
    assert all(item["value"] is None for item in serialized["indicators"].values())
    assert all(item["status"] == "unavailable" for item in serialized["indicators"].values())
