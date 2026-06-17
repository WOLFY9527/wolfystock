# -*- coding: utf-8 -*-
"""Focused contracts for the stock evidence conflict detector."""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from src.services.stock_evidence_conflict_detector import detect_stock_evidence_conflicts


CONTRACT_KEYS = {
    "contractVersion",
    "symbol",
    "conflictState",
    "conflictFamilies",
    "confirmingEvidence",
    "contradictoryEvidence",
    "staleInputs",
    "missingInputs",
    "confidenceCap",
    "observationBoundary",
    "researchNextSteps",
    "noAdviceDisclosure",
}

ADVICE_RE = re.compile(
    r"\b(buy|sell|hold|recommend(?:ation|ed)?|target(?: price)?|stop(?: loss)?|position[-\s]?sizing)\b"
    r"|买入|卖出|持有|推荐|交易建议|投资建议|目标价|止损|止盈|仓位|下单|立即交易",
    re.IGNORECASE,
)


def _base_input() -> dict[str, Any]:
    return {
        "symbol": "aapl",
        "symbolEvidenceReadiness": {
            "symbolEvidenceReadiness": True,
            "symbol": "AAPL",
            "readinessTier": "sufficient",
            "evidenceUsed": ["quote", "technical", "fundamental", "news"],
            "evidenceMissing": [],
            "staleInputs": [],
            "conflictingEvidence": [],
            "observationOnly": True,
            "noAdviceDisclosure": "Observation-only research readiness; not personalized financial advice or an instruction.",
        },
        "stockEvidencePacket": {
            "schemaVersion": "stock_evidence_packet_v1",
            "symbol": "AAPL",
            "thesisEligibility": {"status": "eligible", "reasonCodes": []},
            "dataGaps": [],
            "confidenceCap": {"value": 90, "policyVersion": "stock_evidence_confidence_cap_v1", "reasonCodes": []},
            "confidenceLabel": "high",
            "notInvestmentAdvice": True,
        },
        "stockStructureDecision": {
            "symbol": "AAPL",
            "structureState": "breakout",
            "confidence": "high",
            "componentScores": {"evidenceQuality": 90, "breakoutQuality": 82, "trend": 74},
            "evidenceNotes": ["Structure evidence is complete enough for a bounded research read."],
            "riskObservations": [],
            "dataQuality": {
                "status": "available",
                "source": "local_db",
                "period": "daily",
                "requestedDays": 90,
                "observedBars": 55,
                "usableBars": 55,
                "reason": "history_available",
            },
            "missingEvidence": [],
            "degradedInputs": [],
            "observationOnly": True,
            "decisionGrade": False,
        },
        "peerCorrelationSnapshot": {
            "symbol": "AAPL",
            "peerGroup": {"status": "available", "label": "local peers", "symbols": ["MSFT", "NVDA"]},
            "correlationState": "aligned",
            "peerEvidence": [{"symbol": "MSFT", "state": "aligned"}, {"symbol": "NVDA", "state": "aligned"}],
            "divergenceEvidence": [],
            "staleInputs": [],
            "missingInputs": [],
            "confidenceCap": "medium",
            "observationBoundary": "Observation-only peer movement context; no personalized action instruction.",
            "researchNextSteps": [],
        },
        "symbolCompareEvidencePacket": {
            "comparedSymbols": ["AAPL", "MSFT"],
            "sharedEvidence": [
                {"kind": "daily_ohlcv", "symbols": ["AAPL", "MSFT"], "status": "available"},
                {"kind": "benchmark_ohlcv", "symbols": ["AAPL", "MSFT"], "status": "available"},
            ],
            "divergentEvidence": [],
            "missingEvidenceBySymbol": {"AAPL": [], "MSFT": []},
            "freshnessBySymbol": {
                "AAPL": {"status": "available", "source": "local_db", "period": "daily", "usableBars": 55},
                "MSFT": {"status": "available", "source": "local_db", "period": "daily", "usableBars": 55},
            },
            "confidenceCap": {"value": 100, "policyVersion": "symbol_compare_evidence_packet_v1", "reasonCodes": []},
            "observationBoundary": {
                "observationOnly": True,
                "decisionGrade": False,
                "rankingAllowed": False,
                "adviceAllowed": False,
            },
            "researchNextSteps": [],
        },
    }


def _serialized(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _assert_contract_shape(payload: dict[str, Any]) -> None:
    assert set(payload) == CONTRACT_KEYS
    assert payload["contractVersion"] == "stock_evidence_conflict_detector_v1"
    assert payload["conflictState"] in {"aligned", "conflicting", "insufficient_evidence"}
    assert isinstance(payload["conflictFamilies"], list)
    assert isinstance(payload["confirmingEvidence"], list)
    assert isinstance(payload["contradictoryEvidence"], list)
    assert isinstance(payload["staleInputs"], list)
    assert isinstance(payload["missingInputs"], list)
    assert payload["observationBoundary"] == {
        "observationOnly": True,
        "decisionGrade": False,
        "scoringImpact": "none",
        "rankingImpact": "none",
    }
    assert payload["noAdviceDisclosure"] == (
        "Observation-only research conflict context; not personalized action instruction."
    )


def test_aligned_inputs_return_aligned() -> None:
    result = detect_stock_evidence_conflicts(_base_input())

    _assert_contract_shape(result)
    assert result["symbol"] == "AAPL"
    assert result["conflictState"] == "aligned"
    assert result["conflictFamilies"] == []
    assert result["contradictoryEvidence"] == []
    assert result["staleInputs"] == []
    assert result["missingInputs"] == []
    assert result["confidenceCap"] == {"value": 90, "label": "high"}
    assert {item["family"] for item in result["confirmingEvidence"]} >= {
        "symbol_evidence",
        "structure",
        "peer",
        "compare",
    }


def test_peer_diverging_while_symbol_evidence_is_strong_returns_peer_conflict() -> None:
    packet = _base_input()
    packet["peerCorrelationSnapshot"]["correlationState"] = "diverging"
    packet["peerCorrelationSnapshot"]["peerEvidence"] = [{"symbol": "MSFT", "state": "diverging"}]
    packet["peerCorrelationSnapshot"]["divergenceEvidence"] = [
        {
            "symbol": "MSFT",
            "state": "diverging",
            "summary": "peer provider trace requestId must-not-emit",
        }
    ]

    result = detect_stock_evidence_conflicts(packet)

    assert result["conflictState"] == "conflicting"
    assert result["conflictFamilies"] == ["peer_vs_symbol"]
    assert result["confidenceCap"]["value"] == 65
    assert result["contradictoryEvidence"] == [
        {
            "family": "peer_vs_symbol",
            "observation": "Peer movement diverges from otherwise supportive symbol evidence.",
        }
    ]
    assert "must-not-emit" not in _serialized(result)


def test_readiness_weak_with_structure_evidence_returns_readiness_conflict() -> None:
    packet = _base_input()
    packet["symbolEvidenceReadiness"].update(
        {
            "readinessTier": "partial",
            "evidenceUsed": ["quote", "technical"],
            "evidenceMissing": ["fundamental", "news"],
            "staleInputs": ["quote"],
        }
    )

    result = detect_stock_evidence_conflicts(packet)

    assert result["conflictState"] == "conflicting"
    assert result["conflictFamilies"] == [
        "readiness_vs_structure",
        "freshness_gap",
        "missing_fundamental_context",
        "data_quality_gap",
    ]
    assert result["confidenceCap"] == {"value": 45, "label": "low"}
    assert {"family": "symbol_evidence", "input": "fundamental"} in result["missingInputs"]
    assert {"family": "symbol_evidence", "input": "news"} in result["missingInputs"]
    assert {"family": "symbol_evidence", "input": "quote"} in result["staleInputs"]


def test_missing_peer_and_compare_inputs_return_insufficient_evidence() -> None:
    packet = _base_input()
    packet.pop("peerCorrelationSnapshot")
    packet.pop("symbolCompareEvidencePacket")

    result = detect_stock_evidence_conflicts(packet)

    assert result["conflictState"] == "insufficient_evidence"
    assert result["conflictFamilies"] == ["compare_vs_symbol", "missing_peer_context"]
    assert result["confidenceCap"] == {"value": 40, "label": "low"}
    assert {"family": "peer", "input": "peerCorrelationSnapshot"} in result["missingInputs"]
    assert {"family": "compare", "input": "symbolCompareEvidencePacket"} in result["missingInputs"]


def test_stale_inputs_are_represented() -> None:
    packet = _base_input()
    packet["symbolEvidenceReadiness"]["staleInputs"] = ["quote"]
    packet["peerCorrelationSnapshot"]["staleInputs"] = ["AAPL latest date lags verified peers"]
    packet["symbolCompareEvidencePacket"]["freshnessBySymbol"]["MSFT"]["status"] = "unavailable"

    result = detect_stock_evidence_conflicts(packet)

    assert result["conflictState"] == "conflicting"
    assert "freshness_gap" in result["conflictFamilies"]
    assert {"family": "symbol_evidence", "input": "quote"} in result["staleInputs"]
    assert {"family": "peer", "input": "peer_context"} in result["staleInputs"]
    assert {"family": "compare", "input": "MSFT"} in result["staleInputs"]
    assert result["confidenceCap"]["value"] <= 65


def test_raw_diagnostics_and_adversarial_values_are_dropped() -> None:
    packet = _base_input()
    packet["providerDiagnostics"] = {
        "providerTrace": "provider runtime debug trace sourceRef=raw requestId=REQ-1",
        "rawJson": {"cache": "must-not-emit"},
    }
    packet["stockEvidencePacket"]["sourceRefs"] = [
        {"sourceRefId": "raw-provider", "provider": "debug-provider", "requestId": "REQ-2"}
    ]
    packet["stockEvidencePacket"]["dataGaps"] = [
        {
            "evidenceClass": "fundamental",
            "reasonCode": "provider_timeout",
            "detail": "raw provider debug trace must-not-emit",
        }
    ]
    packet["symbolEvidenceReadiness"]["dataQualityNotes"] = [
        "provider cache runtime trace sourceRef requestId must-not-emit"
    ]

    result = detect_stock_evidence_conflicts(packet)
    serialized = _serialized(result).lower()

    for forbidden in ("provider", "debug", "runtime", "cache", "sourceref", "reasoncode", "requestid", "trace", "raw"):
        assert forbidden not in serialized
    assert "must-not-emit" not in serialized


def test_input_packet_is_not_mutated() -> None:
    packet = _base_input()
    original = copy.deepcopy(packet)

    detect_stock_evidence_conflicts(packet)

    assert packet == original


def test_serialized_output_contains_no_advice_vocabulary() -> None:
    result = detect_stock_evidence_conflicts(_base_input())

    assert ADVICE_RE.search(_serialized(result)) is None
