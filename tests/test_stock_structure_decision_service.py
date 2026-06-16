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


class _FakeMultiHistoryService:
    def __init__(self, payloads: dict[str, dict[str, Any]]) -> None:
        self.payloads = payloads
        self.calls: list[dict[str, Any]] = []

    def get_history_data(self, stock_code: str, period: str = "daily", days: int = 30) -> dict[str, Any]:
        self.calls.append({"stock_code": stock_code, "period": period, "days": days})
        return self.payloads.get(
            stock_code,
            {
                "stock_code": stock_code,
                "period": "daily",
                "data": [],
                "source": "unavailable",
                "diagnostics": {"status": "unavailable", "reason": "history_unavailable"},
            },
        )


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


def _flat_history() -> list[dict[str, Any]]:
    return [_bar(index, 100 + (index % 3) * 0.05, volume=900.0, width=0.4) for index in range(55)]


def _weak_history() -> list[dict[str, Any]]:
    return [_bar(index, 80 - index * 0.35, volume=1000.0 + index * 12, width=0.8) for index in range(55)]


def _assert_required_contract(payload: dict[str, Any]) -> None:
    assert payload["schemaVersion"] == STOCK_STRUCTURE_DECISION_API_SCHEMA_VERSION
    assert payload["ticker"] == "AAPL"
    assert payload["symbol"] == "AAPL"
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
    assert isinstance(payload["keyLevels"], list)
    assert isinstance(payload["evidenceNotes"], list)
    assert isinstance(payload["riskObservations"], list)
    assert isinstance(payload["evidenceGaps"], list)
    assert "dataQuality" in payload
    assert "missingEvidence" in payload
    assert "degradedInputs" in payload
    assert "consumerIssues" in payload
    assert payload["noAdviceDisclosure"]
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False
    assert "drilldownLinks" in payload


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
    assert "Breakout quality is supported by a close above the recent range and stronger volume." in payload["evidenceNotes"]
    assert payload["riskObservations"]
    assert "Benchmark OHLCV is not included in this endpoint yet, so relative-strength evidence is neutral." in payload["evidenceGaps"]
    assert "Benchmark OHLCV would improve relative-strength evidence." in payload["evidenceGaps"]
    assert payload["degradedInputs"] == [
        {
            "section": "comparativeContext",
            "status": "degraded",
            "reason": "benchmark_ohlcv_unavailable",
        }
    ]
    assert payload["drilldownLinks"] == []


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
    assert payload["consumerIssues"][0]["label"] == "Structure evidence unavailable"
    consumer_copy = json.dumps(
        {
            "consumerIssues": payload["consumerIssues"],
            "evidenceGaps": payload["evidenceGaps"],
            "drilldownLinks": payload["drilldownLinks"],
        },
        ensure_ascii=False,
    ).lower()
    assert "history_unavailable" not in consumer_copy
    assert "daily_ohlcv" not in consumer_copy


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
    assert payload["consumerIssues"][0]["label"] == "Structure evidence unavailable"


def test_service_fails_closed_before_history_lookup_for_invalid_symbol_format() -> None:
    fake_history = _FakeHistoryService(
        {
            "stock_code": "AAPL",
            "period": "daily",
            "data": _trend_breakout_history(),
            "source": "local_db",
            "diagnostics": {"status": "ok", "reason": "history_available", "rows": 55},
        }
    )

    payload = StockStructureDecisionService(history_service=fake_history).get_structure_decision("AAPL<script>")

    assert fake_history.calls == []
    assert payload["structureState"] == "lowConfidence"
    assert payload["dataQuality"]["reason"] == "invalid_format"
    assert payload["consumerIssues"][0]["label"] == "Symbol needs review"
    assert payload["consumerIssues"][0]["message"] == "Enter a supported stock symbol format."
    assert payload["degradedInputs"][0]["section"] == "symbol"


def test_service_adds_safe_drilldown_context_when_requested() -> None:
    fake_history = _FakeHistoryService(
        {
            "stock_code": "AAPL",
            "period": "daily",
            "data": _trend_breakout_history(),
            "source": "local_db",
            "diagnostics": {"status": "ok", "reason": "history_available", "rows": 55},
        }
    )

    payload = StockStructureDecisionService(history_service=fake_history).get_structure_decision(
        "AAPL",
        context_source="researchRadar",
        context_section="scannerHighlights",
        context_reason="scanner_candidates_origin",
    )

    assert payload["sourceContext"] == {
        "source": "researchRadar",
        "label": "Research Radar",
        "route": "/research/radar",
        "section": "scannerHighlights",
        "reason": "Scanner candidate context.",
    }
    assert payload["drilldownLinks"] == [payload["sourceContext"]]
    assert payload["consumerIssues"][0]["label"] != "Research context unavailable"


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


def test_batch_structure_decisions_are_bounded_and_stably_ordered() -> None:
    fake_history = _FakeMultiHistoryService(
        {
            "AAPL": {
                "stock_code": "AAPL",
                "period": "daily",
                "data": _trend_breakout_history(),
                "source": "local_db",
                "diagnostics": {"status": "ok", "reason": "history_available"},
            },
            "MSFT": {
                "stock_code": "MSFT",
                "period": "daily",
                "data": _flat_history(),
                "source": "local_db",
                "diagnostics": {"status": "ok", "reason": "history_available"},
            },
            "SPY": {
                "stock_code": "SPY",
                "period": "daily",
                "data": _flat_history(),
                "source": "local_db",
                "diagnostics": {"status": "ok", "reason": "history_available"},
            },
        }
    )

    payload = StockStructureDecisionService(history_service=fake_history).get_structure_decisions_batch(
        ["msft", "aapl", "msft", "goog"],
        benchmark="spy",
        max_items=2,
    )

    assert payload["schemaVersion"] == STOCK_STRUCTURE_DECISION_API_SCHEMA_VERSION
    assert [item["ticker"] for item in payload["items"]] == ["MSFT", "AAPL"]
    assert [call["stock_code"] for call in fake_history.calls] == ["SPY", "MSFT", "AAPL"]
    assert payload["aggregateSummary"]["requestedCount"] == 4
    assert payload["aggregateSummary"]["evaluatedCount"] == 2
    assert payload["aggregateSummary"]["maxItems"] == 2
    assert payload["aggregateSummary"]["truncated"] is True
    assert payload["aggregateSummary"]["structureStateCounts"]
    relative_strength = payload["aggregateSummary"]["relativeStrength"]
    assert relative_strength["status"] == "available"
    assert relative_strength["benchmark"] == "SPY"
    assert [entry["ticker"] for entry in relative_strength["ranking"]] == ["AAPL", "MSFT"]
    assert [entry["rank"] for entry in relative_strength["ranking"]] == [1, 2]
    assert payload["missingEvidence"] == []
    assert payload["dataQuality"]["status"] == "available"
    assert all(item["observationOnly"] is True for item in payload["items"])
    assert all(item["decisionGrade"] is False for item in payload["items"])


def test_batch_structure_decisions_mark_comparative_context_unavailable_without_benchmark() -> None:
    fake_history = _FakeMultiHistoryService(
        {
            "AAPL": {
                "stock_code": "AAPL",
                "period": "daily",
                "data": _trend_breakout_history(),
                "source": "local_db",
                "diagnostics": {"status": "ok", "reason": "history_available"},
            },
            "MSFT": {
                "stock_code": "MSFT",
                "period": "daily",
                "data": [],
                "source": "unavailable",
                "diagnostics": {"status": "unavailable", "reason": "history_unavailable"},
            },
        }
    )

    payload = StockStructureDecisionService(history_service=fake_history).get_structure_decisions_batch(
        ["aapl", "msft"],
    )

    assert [item["comparativeContext"]["status"] for item in payload["items"]] == [
        "unavailable",
        "unavailable",
    ]
    assert payload["items"][1]["structureState"] == "lowConfidence"
    assert payload["aggregateSummary"]["relativeStrength"] == {
        "status": "unavailable",
        "benchmark": None,
        "ranking": [],
        "reason": "benchmark_ohlcv_unavailable",
    }
    assert payload["missingEvidence"] == [
        {
            "kind": "benchmark_ohlcv",
            "message": "Benchmark OHLCV is unavailable, so relative-strength ranking is unavailable.",
        },
        {
            "kind": "daily_ohlcv",
            "message": "At least one symbol has unavailable daily OHLCV evidence.",
        },
    ]
    assert payload["dataQuality"]["status"] == "partial"


def test_batch_structure_decision_output_avoids_recommendation_or_trading_instruction_language() -> None:
    fake_history = _FakeMultiHistoryService(
        {
            "AAPL": {
                "stock_code": "AAPL",
                "period": "daily",
                "data": _trend_breakout_history(),
                "source": "local_db",
                "diagnostics": {"status": "ok", "reason": "history_available"},
            },
            "MSFT": {
                "stock_code": "MSFT",
                "period": "daily",
                "data": _weak_history(),
                "source": "local_db",
                "diagnostics": {"status": "ok", "reason": "history_available"},
            },
        }
    )

    payload = StockStructureDecisionService(history_service=fake_history).get_structure_decisions_batch(
        ["AAPL", "MSFT"],
    )
    serialized = json.dumps(payload, ensure_ascii=False).lower()

    for forbidden in FORBIDDEN_ADVICE_TOKENS:
        assert forbidden not in serialized
    assert "not personalized financial advice" in serialized
