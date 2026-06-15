# -*- coding: utf-8 -*-
"""Tests for the stock structure decision API service."""

from __future__ import annotations

import json
from typing import Any

from src.services.stock_structure_decision_service import (
    STOCK_STRUCTURE_DECISION_API_SCHEMA_VERSION,
    StockStructureDecisionService,
)


FORBIDDEN_ADVICE_TOKENS = (
    "buy",
    "sell",
    "hold",
    "position",
    "target",
    "stop",
    "entry",
    "exit",
    "recommendation",
    "买入",
    "卖出",
    "持有",
    "仓位",
    "目标",
    "止损",
    "止盈",
    "推荐",
)


class _FakeHistoryService:
    def __init__(self, payload: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self.payload = payload or {}
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def get_history_data(self, stock_code: str, period: str = "daily", days: int = 30) -> dict[str, Any]:
        self.calls.append({"stock_code": stock_code, "period": period, "days": days})
        if self.error is not None:
            raise self.error
        return self.payload


def _bar(index: int, close: float, *, volume: float = 1000.0, width: float = 1.0) -> dict[str, Any]:
    return {
        "date": f"2026-01-{index + 1:02d}",
        "open": round(close - width * 0.2, 4),
        "high": round(close + width * 0.5, 4),
        "low": round(close - width * 0.5, 4),
        "close": round(close, 4),
        "volume": round(volume, 4),
    }


def _trend_breakout_history() -> list[dict[str, Any]]:
    bars = [_bar(index, 100 + index * 0.55, volume=1200.0) for index in range(55)]
    prior_range_high = max(float(bar["high"]) for bar in bars[-21:-1])
    bars[-1] = _bar(54, prior_range_high * 1.025, volume=2600.0)
    return bars


def _assert_required_contract(payload: dict[str, Any]) -> None:
    assert payload["schemaVersion"] == STOCK_STRUCTURE_DECISION_API_SCHEMA_VERSION
    assert payload["ticker"] == "AAPL"
    assert payload["structureState"] in {
        "uptrend",
        "breakout",
        "pullback",
        "consolidation",
        "extended",
        "distribution",
        "breakdown",
        "mixed",
        "lowConfidence",
    }
    assert payload["confidence"] in {"high", "medium", "low"}
    assert set(payload["componentScores"]) == {
        "trend",
        "relativeStrength",
        "volumePressure",
        "volatilityCompression",
        "breakoutQuality",
        "pullbackHealth",
        "riskExtension",
        "evidenceQuality",
    }
    assert set(payload["explanation"]) == {
        "whyThisStructure",
        "whatConfirmsIt",
        "whatInvalidatesIt",
        "keyLevels",
    }
    assert set(payload["researchNotes"]) == {"watchNext", "needsMoreEvidence", "riskFlags"}
    assert "dataQuality" in payload
    assert "missingEvidence" in payload
    assert payload["noAdviceDisclosure"]


def test_service_builds_observation_only_structure_decision_from_daily_ohlcv() -> None:
    fake_history = _FakeHistoryService(
        {
            "stock_code": "AAPL",
            "period": "daily",
            "data": _trend_breakout_history(),
            "source": "local_db",
            "diagnostics": {"status": "ok", "reason": "history_available", "rows": 55},
        }
    )

    payload = StockStructureDecisionService(history_service=fake_history).get_structure_decision("aapl")

    _assert_required_contract(payload)
    assert fake_history.calls == [{"stock_code": "AAPL", "period": "daily", "days": 90}]
    assert payload["ticker"] == "AAPL"
    assert payload["structureState"] == "breakout"
    assert payload["dataQuality"] == {
        "status": "available",
        "source": "local_db",
        "period": "daily",
        "requestedDays": 90,
        "observedBars": 55,
        "usableBars": 55,
        "reason": "history_available",
    }
    assert payload["missingEvidence"] == [
        {
            "kind": "benchmark_ohlcv",
            "message": "Benchmark OHLCV is not included in this endpoint yet, so relative-strength evidence is neutral.",
        }
    ]


def test_service_fails_closed_when_ohlcv_history_is_unavailable() -> None:
    fake_history = _FakeHistoryService(
        {
            "stock_code": "AAPL",
            "period": "daily",
            "data": [],
            "source": "unavailable",
            "diagnostics": {
                "status": "unavailable",
                "reason": "history_unavailable",
                "message": "No real OHLC daily history is currently available.",
            },
        }
    )

    payload = StockStructureDecisionService(history_service=fake_history).get_structure_decision("AAPL")

    _assert_required_contract(payload)
    assert payload["structureState"] == "lowConfidence"
    assert payload["confidence"] == "low"
    assert payload["dataQuality"]["status"] == "unavailable"
    assert payload["dataQuality"]["source"] == "unavailable"
    assert payload["dataQuality"]["observedBars"] == 0
    assert payload["dataQuality"]["usableBars"] == 0
    assert payload["dataQuality"]["reason"] == "history_unavailable"
    assert {
        "kind": "daily_ohlcv",
        "message": "Daily OHLCV history is unavailable, so the structure state is low confidence.",
    } in payload["missingEvidence"]


def test_service_fails_closed_when_history_lookup_raises() -> None:
    fake_history = _FakeHistoryService(error=RuntimeError("provider timeout"))

    payload = StockStructureDecisionService(history_service=fake_history).get_structure_decision("AAPL")

    _assert_required_contract(payload)
    assert payload["structureState"] == "lowConfidence"
    assert payload["confidence"] == "low"
    assert payload["dataQuality"]["status"] == "unavailable"
    assert payload["dataQuality"]["source"] == "unavailable"
    assert payload["dataQuality"]["reason"] == "history_lookup_failed"
    assert payload["missingEvidence"][0]["kind"] == "daily_ohlcv"


def test_service_output_avoids_recommendation_or_trading_instruction_language() -> None:
    fake_history = _FakeHistoryService(
        {
            "stock_code": "AAPL",
            "period": "daily",
            "data": _trend_breakout_history(),
            "source": "local_db",
            "diagnostics": {"status": "ok", "reason": "history_available", "rows": 55},
        }
    )

    payload = StockStructureDecisionService(history_service=fake_history).get_structure_decision("AAPL")
    serialized = json.dumps(payload, ensure_ascii=False).lower()

    for forbidden in FORBIDDEN_ADVICE_TOKENS:
        assert forbidden not in serialized
    assert "not personalized financial advice" in serialized
