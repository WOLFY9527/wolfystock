# -*- coding: utf-8 -*-
"""Tests for the stock structure decision API service."""

from __future__ import annotations

import json
import threading
import time
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


class _BlockingHistoryService:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls: list[dict[str, Any]] = []

    def get_history_data(self, stock_code: str, period: str = "daily", days: int = 30) -> dict[str, Any]:
        self.calls.append({"stock_code": stock_code, "period": period, "days": days})
        self.started.set()
        self.release.wait(timeout=2.0)
        return {
            "stock_code": stock_code,
            "period": "daily",
            "data": _trend_breakout_history(),
            "source": "local_db",
            "diagnostics": {"status": "ok", "reason": "history_available", "rows": 55},
        }


class _FakePeerRepository:
    def __init__(
        self,
        *,
        peer_groups: dict[str, dict[str, Any]] | None = None,
        rows: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self.peer_groups = peer_groups or {}
        self.rows = rows or {}
        self.peer_group_calls: list[str] = []
        self.daily_row_calls: list[dict[str, Any]] = []

    def get_local_peer_group(self, symbol: str) -> dict[str, Any] | None:
        self.peer_group_calls.append(symbol)
        return self.peer_groups.get(symbol)

    def get_recent_daily_rows(self, *, code: str, limit: int) -> list[dict[str, Any]]:
        self.daily_row_calls.append({"code": code, "limit": limit})
        return list(self.rows.get(code, []))[:limit]


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


def _peer_rows(closes: list[float]) -> list[dict[str, Any]]:
    return [
        {"date": f"2026-02-{index + 1:02d}", "close": close}
        for index, close in enumerate(closes)
    ]


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
    assert "peerCorrelationSnapshot" in payload
    peer_snapshot = payload["peerCorrelationSnapshot"]
    assert peer_snapshot["symbol"] == payload["symbol"]
    assert peer_snapshot["correlationState"] in {"aligned", "diverging", "insufficient_evidence"}
    assert "peerGroup" in peer_snapshot
    assert isinstance(peer_snapshot["peerEvidence"], list)
    assert isinstance(peer_snapshot["divergenceEvidence"], list)
    assert isinstance(peer_snapshot["staleInputs"], list)
    assert isinstance(peer_snapshot["missingInputs"], list)
    assert peer_snapshot["confidenceCap"] in {"low", "medium", "high"}
    assert peer_snapshot["observationBoundary"]
    assert isinstance(peer_snapshot["researchNextSteps"], list)
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
    assert payload["peerCorrelationSnapshot"]["correlationState"] == "insufficient_evidence"
    assert payload["peerCorrelationSnapshot"]["missingInputs"] == [
        "No verified local peer group metadata is available for AAPL."
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


def test_service_caps_high_structure_confidence_when_critical_evidence_is_missing() -> None:
    fake_history = _FakeMultiHistoryService(
        {
            "AAPL": {
                "stock_code": "AAPL",
                "period": "daily",
                "data": _trend_breakout_history(),
                "source": "local_db",
                "diagnostics": {"status": "ok", "reason": "history_available", "rows": 55},
            },
            "SPY": {
                "stock_code": "SPY",
                "period": "daily",
                "data": _flat_history(),
                "source": "local_db",
                "diagnostics": {"status": "ok", "reason": "history_available", "rows": 55},
            },
        }
    )

    batch = StockStructureDecisionService(history_service=fake_history).get_structure_decisions_batch(
        ["AAPL"],
        benchmark="SPY",
    )
    payload = batch["items"][0]

    assert payload["structureState"] == "breakout"
    assert payload["rawConfidence"] == "high"
    assert payload["confidence"] == "medium"
    assert payload["confidenceCap"] == {
        "value": 60,
        "label": "medium",
        "reasons": ["critical evidence missing"],
        "policyVersion": "confidence_evidence_consistency_v1",
    }
    assert payload["confidenceState"] == {
        "status": "evidence limited",
        "label": "medium",
        "reasons": ["critical evidence missing"],
        "freshnessConstrained": False,
        "sourceQualityLimited": False,
        "thesisBlocked": False,
    }


def test_peer_correlation_snapshot_marks_aligned_when_local_peer_group_and_prices_match() -> None:
    fake_history = _FakeHistoryService(
        {
            "stock_code": "AAPL",
            "period": "daily",
            "data": _trend_breakout_history(),
            "source": "local_db",
            "diagnostics": {"status": "ok", "reason": "history_available", "rows": 55},
        }
    )
    target = [100, 101, 102, 104, 107, 111, 116, 122]
    fake_peer_repo = _FakePeerRepository(
        peer_groups={"AAPL": {"label": "local verified software peers", "symbols": ["MSFT", "NVDA"]}},
        rows={
            "AAPL": _peer_rows(target),
            "MSFT": _peer_rows([value * 1.5 for value in target]),
            "NVDA": _peer_rows([value * 0.8 for value in target]),
        },
    )

    payload = StockStructureDecisionService(
        history_service=fake_history,
        stock_repo=fake_peer_repo,
    ).get_structure_decision("AAPL")

    snapshot = payload["peerCorrelationSnapshot"]
    assert snapshot["correlationState"] == "aligned"
    assert snapshot["peerGroup"] == {
        "status": "available",
        "label": "local verified software peers",
        "symbols": ["MSFT", "NVDA"],
    }
    assert [item["symbol"] for item in snapshot["peerEvidence"]] == ["MSFT", "NVDA"]
    assert all(item["state"] == "aligned" for item in snapshot["peerEvidence"])
    assert snapshot["divergenceEvidence"] == []
    assert snapshot["missingInputs"] == []
    assert snapshot["confidenceCap"] == "medium"
    assert fake_history.calls == [{"stock_code": "AAPL", "period": "daily", "days": 90}]
    assert fake_peer_repo.peer_group_calls == ["AAPL"]
    assert [call["code"] for call in fake_peer_repo.daily_row_calls] == ["AAPL", "MSFT", "NVDA"]


def test_peer_correlation_snapshot_marks_diverging_when_local_peers_move_away() -> None:
    fake_history = _FakeHistoryService(
        {
            "stock_code": "AAPL",
            "period": "daily",
            "data": _trend_breakout_history(),
            "source": "local_db",
            "diagnostics": {"status": "ok", "reason": "history_available", "rows": 55},
        }
    )
    fake_peer_repo = _FakePeerRepository(
        peer_groups={"AAPL": {"label": "local verified software peers", "symbols": ["MSFT", "NVDA"]}},
        rows={
            "AAPL": _peer_rows([100, 101, 102, 104, 107, 111, 116, 122]),
            "MSFT": _peer_rows([200, 198, 196, 193, 190, 186, 181, 175]),
            "NVDA": _peer_rows([70, 69, 68, 66, 64, 62, 59, 56]),
        },
    )

    payload = StockStructureDecisionService(
        history_service=fake_history,
        stock_repo=fake_peer_repo,
    ).get_structure_decision("AAPL")

    snapshot = payload["peerCorrelationSnapshot"]
    assert snapshot["correlationState"] == "diverging"
    assert [item["symbol"] for item in snapshot["divergenceEvidence"]] == ["MSFT", "NVDA"]
    assert all(item["state"] == "diverging" for item in snapshot["peerEvidence"])
    assert snapshot["missingInputs"] == []
    assert snapshot["confidenceCap"] == "medium"


def test_peer_correlation_snapshot_fails_gracefully_when_peer_prices_are_missing() -> None:
    fake_history = _FakeHistoryService(
        {
            "stock_code": "AAPL",
            "period": "daily",
            "data": _trend_breakout_history(),
            "source": "local_db",
            "diagnostics": {"status": "ok", "reason": "history_available", "rows": 55},
        }
    )
    fake_peer_repo = _FakePeerRepository(
        peer_groups={"AAPL": {"label": "local verified software peers", "symbols": ["MSFT", "NVDA"]}},
        rows={"AAPL": _peer_rows([100, 101, 102, 104, 107, 111, 116, 122])},
    )

    payload = StockStructureDecisionService(
        history_service=fake_history,
        stock_repo=fake_peer_repo,
    ).get_structure_decision("AAPL")

    snapshot = payload["peerCorrelationSnapshot"]
    assert snapshot["correlationState"] == "insufficient_evidence"
    assert snapshot["peerEvidence"] == []
    assert snapshot["divergenceEvidence"] == []
    assert "Recent local daily OHLCV is incomplete for MSFT." in snapshot["missingInputs"]
    assert "Recent local daily OHLCV is incomplete for NVDA." in snapshot["missingInputs"]
    assert (
        "Enough overlapping local peer OHLCV was not available for a bounded comparison."
        in snapshot["missingInputs"]
    )
    assert snapshot["confidenceCap"] == "low"


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


def test_service_returns_unavailable_when_structure_decision_dependency_exceeds_latency_boundary() -> None:
    blocking_history = _BlockingHistoryService()
    service = StockStructureDecisionService(
        history_service=blocking_history,
        timeout_seconds=0.01,
    )

    started_at = time.monotonic()
    try:
        payload = service.get_structure_decision("AAPL")
    finally:
        blocking_history.release.set()
    elapsed = time.monotonic() - started_at

    assert blocking_history.started.is_set()
    assert elapsed < 0.5
    _assert_required_contract(payload)
    assert payload["structureState"] == "lowConfidence"
    assert payload["confidence"] == "low"
    assert payload["dataQuality"] == {
        "status": "unavailable",
        "source": "unavailable",
        "period": "daily",
        "requestedDays": 90,
        "observedBars": 0,
        "usableBars": 0,
        "reason": "structure_decision_timeout",
    }
    assert payload["missingEvidence"][0] == {
        "kind": "daily_ohlcv",
        "message": "Structure decision inputs did not return within the latency boundary.",
    }
    assert payload["degradedInputs"][0] == {
        "section": "structureEvidence",
        "status": "unavailable",
        "reason": "structure_decision_timeout",
    }
    assert payload["consumerIssues"][0]["label"] == "Structure evidence unavailable"
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    assert "traceback" not in serialized
    assert "exception" not in serialized
    for forbidden in FORBIDDEN_ADVICE_TOKENS:
        assert forbidden not in serialized


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
    compare_packet = payload["symbolCompareEvidencePacket"]
    assert compare_packet["comparedSymbols"] == ["MSFT", "AAPL"]
    assert compare_packet["sharedEvidence"] == [
        {
            "kind": "daily_ohlcv",
            "symbols": ["MSFT", "AAPL"],
            "status": "available",
            "period": "daily",
            "source": "local_db",
            "usableBarsMin": 55,
            "usableBarsMax": 55,
        },
        {
            "kind": "benchmark_ohlcv",
            "symbols": ["MSFT", "AAPL"],
            "status": "available",
            "benchmark": "SPY",
        },
    ]
    assert compare_packet["divergentEvidence"]
    assert {
        "kind": "structure_state",
        "symbols": ["MSFT", "AAPL"],
        "values": {"MSFT": "mixed", "AAPL": "breakout"},
    } in compare_packet["divergentEvidence"]
    assert compare_packet["missingEvidenceBySymbol"] == {"MSFT": [], "AAPL": []}
    assert compare_packet["freshnessBySymbol"] == {
        "MSFT": {"status": "available", "source": "local_db", "period": "daily", "usableBars": 55},
        "AAPL": {"status": "available", "source": "local_db", "period": "daily", "usableBars": 55},
    }
    assert compare_packet["confidenceCap"] == {
        "value": 100,
        "reasonCodes": [],
        "policyVersion": "symbol_compare_evidence_packet_v1",
    }
    assert compare_packet["observationBoundary"] == {
        "observationOnly": True,
        "decisionGrade": False,
        "rankingAllowed": False,
        "adviceAllowed": False,
    }
    assert compare_packet["researchNextSteps"] == []
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
    compare_packet = payload["symbolCompareEvidencePacket"]
    assert compare_packet["comparedSymbols"] == ["AAPL", "MSFT"]
    assert compare_packet["sharedEvidence"] == []
    assert compare_packet["missingEvidenceBySymbol"] == {
        "AAPL": [
            {
                "kind": "benchmark_ohlcv",
                "message": "Benchmark OHLCV is unavailable, so cross-symbol relative evidence is not available.",
            }
        ],
        "MSFT": [
            {
                "kind": "daily_ohlcv",
                "message": "Daily OHLCV history is unavailable, so this symbol cannot contribute complete comparison evidence.",
            },
            {
                "kind": "benchmark_ohlcv",
                "message": "Benchmark OHLCV is unavailable, so cross-symbol relative evidence is not available.",
            },
        ],
    }
    assert compare_packet["freshnessBySymbol"]["MSFT"] == {
        "status": "unavailable",
        "source": "unavailable",
        "period": "daily",
        "usableBars": 0,
    }
    assert compare_packet["confidenceCap"]["value"] == 35
    assert compare_packet["confidenceCap"]["reasonCodes"] == [
        "symbol_evidence_unavailable",
        "benchmark_ohlcv_unavailable",
    ]
    assert compare_packet["researchNextSteps"] == [
        "Add daily OHLCV evidence for MSFT before using divergence observations.",
        "Add benchmark OHLCV evidence to enable cross-symbol relative context.",
    ]


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
    assert "winner" not in serialized
    assert "loser" not in serialized
    assert "best" not in serialized
    compare_serialized = json.dumps(payload["symbolCompareEvidencePacket"], ensure_ascii=False).lower()
    assert '"rank":' not in compare_serialized
    assert "relativestrength" not in compare_serialized
