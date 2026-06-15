# -*- coding: utf-8 -*-
"""Contract tests for the Market Decision Cockpit aggregate service."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

from src.services.market_decision_cockpit_service import build_market_decision_cockpit


REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PUBLIC_TERMS = (
    "buy",
    "sell",
    "hold",
    "position",
    "target",
    "stop loss",
    "take profit",
    "guaranteed",
    "support level",
    "resistance level",
    "dealer book",
    "交易建议",
    "投资建议",
    "买入",
    "卖出",
    "仓位",
    "目标价",
    "止损",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "src.providers",
    "src.services.market_scanner_service",
    "src.services.watchlist_service",
    "src.services.portfolio",
    "api.deps",
    "src.auth",
)
FORBIDDEN_PUBLIC_WORD_TERMS = {"buy", "sell", "hold", "position", "target", "stop", "guaranteed"}


def _item(
    symbol: str,
    value: float,
    *,
    change_percent: float = 0.0,
    source_type: str = "official_public",
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "label": symbol,
        "value": value,
        "changePercent": change_percent,
        "source": "official_public",
        "sourceType": source_type,
        "trustLevel": "high",
        "freshness": "live",
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": True,
    }


def _regime_ready_inputs() -> dict[str, Any]:
    return {
        "breadth": {"items": [_item("ADV_RATIO", 66.0, change_percent=3.0)]},
        "rates": {
            "items": [
                _item("VIX", 14.0, change_percent=-6.0),
                _item("US10Y", 4.16, change_percent=-1.0),
                _item("BAMLH0A0HYM2", 3.2, change_percent=-1.5),
            ]
        },
        "fx": {"items": [_item("DXY", 101.8, change_percent=-0.4)]},
        "futures": {"items": [_item("ES", 5400.0, change_percent=0.7, source_type="exchange_public")]},
        "crypto": {"items": [_item("BTC", 68000.0, change_percent=1.4, source_type="exchange_public")]},
        "sectors": {
            "items": [
                {
                    **_item("AI_SOFTWARE", 72.0, change_percent=2.0, source_type="tier_1_configured"),
                    "rotationScore": 72.0,
                    "rankEligible": True,
                    "headlineEligible": True,
                }
            ]
        },
        "capitalFlowSignal": {
            "likelyDestination": "growth_ai_software_semis",
            "score": 72.0,
            "freshness": "live",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
        },
    }


def _candidate(symbol: str = "ALFA") -> dict[str, Any]:
    return {
        "ticker": symbol,
        "relativeStrength": 88,
        "volumeExpansion": 1.8,
        "trendStructure": "confirmed_uptrend",
        "themes": ["AI Infrastructure"],
        "eventCatalyst": {"state": "confirmed", "label": "earnings review"},
        "avgDollarVolume": 120_000_000,
        "evidenceQuality": {"state": "complete", "score": 0.88},
    }


def _complete_option_contracts() -> list[dict[str, Any]]:
    return [
        {
            "contractSymbol": "TEST260619C00100000",
            "side": "call",
            "strike": 100.0,
            "expiration": "2026-06-19",
            "gamma": 0.02,
            "openInterest": 100,
            "impliedVolatility": 0.25,
            "multiplier": 100,
            "dte": 0,
        },
        {
            "contractSymbol": "TEST260619P00100000",
            "side": "put",
            "strike": 100.0,
            "expiration": "2026-06-19",
            "gamma": 0.01,
            "openInterest": 50,
            "impliedVolatility": 0.28,
            "multiplier": 100,
            "dte": 0,
        },
    ]


def _serialized_values(payload: object) -> str:
    values: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, str):
            values.append(value)
            return
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                visit(item)

    visit(payload)
    return json.dumps(values, ensure_ascii=False, sort_keys=True).lower()


def _assert_no_forbidden_public_terms(payload: object) -> None:
    serialized = _serialized_values(payload)
    for forbidden in FORBIDDEN_PUBLIC_TERMS:
        if forbidden in FORBIDDEN_PUBLIC_WORD_TERMS:
            assert re.search(rf"\b{re.escape(forbidden)}\b", serialized) is None
        else:
            assert forbidden not in serialized


def test_cockpit_uses_regime_engine_as_primary_judgment_and_shapes_safe_aggregate() -> None:
    payload = build_market_decision_cockpit(
        market_inputs=_regime_ready_inputs(),
        research_candidates=[_candidate()],
        generated_at="2026-06-15T00:00:00+00:00",
    )

    assert payload["schemaVersion"] == "market_decision_cockpit.v1"
    assert payload["generatedAt"] == "2026-06-15T00:00:00+00:00"
    assert payload["noAdviceDisclosure"]

    decision = payload["marketRegimeDecision"]
    assert decision["regime"] == "riskOn"
    assert decision["confidence"] in {"medium", "high"}
    assert set(decision["driverScores"]) == {
        "dealerGamma",
        "breadthParticipation",
        "volatilityStructure",
        "ratesDollar",
        "liquidityCredit",
        "crossAssetRisk",
        "sectorThemeRotation",
        "eventCatalyst",
    }
    assert decision["explanation"]["whyThisRegime"]
    assert decision["invalidationConditions"] == decision["explanation"]["whatInvalidatesIt"]
    assert decision["researchPriorities"]["watchToday"]

    attribution = payload["driverAttribution"]
    assert attribution["topPositiveDrivers"][0]["driver"] in decision["driverScores"]
    assert attribution["topPositiveDrivers"][0]["score"] > 0
    assert attribution["topPositiveDrivers"][0]["whyItMatters"]
    assert isinstance(attribution["topNegativeDrivers"], list)
    assert isinstance(attribution["conflictingDrivers"], list)
    assert attribution["unavailableDrivers"][0]["driver"] == "dealerGamma"
    assert "live_gex_not_implemented_v1" in attribution["unavailableDrivers"][0]["reasonCodes"]

    diagnostics = payload["confidenceDiagnostics"]
    assert diagnostics["evidenceStrength"]["confidence"] == decision["confidence"]
    assert diagnostics["evidenceStrength"]["confidenceScore"] == decision["confidenceScore"]
    assert diagnostics["evidenceStrength"]["scoringDriverCount"] >= 3
    assert diagnostics["confidencePenalties"]
    assert diagnostics["missingEvidenceImpact"][0]["evidence"] == "dealerGamma:unavailable"

    watch_trigger = payload["watchTriggers"][0]
    assert set(watch_trigger) == {"triggerName", "driver", "condition", "whyItMatters", "currentEvidence"}
    assert watch_trigger["condition"]
    assert watch_trigger["currentEvidence"]

    what_changed = payload["whatChanged"]
    assert what_changed["status"] == "degraded"
    assert what_changed["basis"] == "current_snapshot_only"
    assert "historical_baseline_unavailable" in what_changed["unavailableDrivers"]
    assert any(item["field"] == "generatedAt" for item in what_changed["observations"])

    readiness = payload["cockpitReadiness"]
    assert readiness["status"] == "degraded"
    assert readiness["reasons"] == ["options structure evidence is unavailable"]

    assert payload["scenarioHints"]
    assert all(isinstance(hint, str) and hint for hint in payload["scenarioHints"])
    assert all(not any(char.isdigit() for char in hint) for hint in payload["scenarioHints"])

    queue = payload["researchQueuePreview"]
    assert queue["previewOnly"] is True
    assert queue["topCandidates"][0]["ticker"] == "ALFA"
    assert queue["queueQuality"] in {"strong", "mixed", "thin", "low_evidence"}
    assert isinstance(queue["evidenceGaps"], list)

    options = payload["optionsStructureStatus"]
    assert options["gammaEvidenceStatus"] == "unavailable"
    assert options["observationOnly"] is True
    assert options["decisionGrade"] is False
    assert "option_chain_unavailable" in options["blockedReasonCodes"]
    assert "missing_spot_reference" in options["blockedReasonCodes"]

    assert payload["cockpitSummary"]["whatChanged"]
    assert payload["cockpitSummary"]["whyItMatters"]
    assert payload["cockpitSummary"]["whatToWatch"]
    assert payload["cockpitSummary"]["confidenceLimits"]
    assert payload["dataQuality"]["status"] == "degraded"

    _assert_no_forbidden_public_terms(payload)


def test_missing_inputs_fail_closed_with_empty_research_preview_and_blocked_options() -> None:
    payload = build_market_decision_cockpit(
        market_inputs={},
        research_candidates=None,
        generated_at="2026-06-15T00:00:00+00:00",
    )

    assert payload["marketRegimeDecision"]["regime"] == "lowConfidence"
    assert payload["marketRegimeDecision"]["confidence"] == "low"
    assert payload["researchQueuePreview"]["topCandidates"] == []
    assert payload["researchQueuePreview"]["degradedState"] == {
        "status": "empty",
        "reasonCodes": ["research_candidates_unavailable"],
    }
    assert payload["optionsStructureStatus"]["gammaEvidenceStatus"] == "unavailable"
    assert payload["optionsStructureStatus"]["decisionGrade"] is False
    assert payload["dataQuality"]["status"] == "blocked"
    assert "market_regime_low_confidence" in payload["dataQuality"]["reasonCodes"]
    assert "research_candidates_unavailable" in payload["dataQuality"]["reasonCodes"]
    assert "option_chain_unavailable" in payload["dataQuality"]["reasonCodes"]
    assert payload["cockpitReadiness"] == {
        "status": "insufficient",
        "reasons": [
            "market regime evidence is insufficient",
            "research radar candidates are unavailable",
            "options structure evidence is unavailable",
        ],
    }
    assert payload["confidenceDiagnostics"]["missingEvidenceImpact"]
    assert payload["whatChanged"]["status"] == "degraded"
    assert payload["driverAttribution"]["topPositiveDrivers"] == []
    assert payload["driverAttribution"]["topNegativeDrivers"] == []
    assert payload["driverAttribution"]["unavailableDrivers"]


def test_driver_attribution_surfaces_conflicting_positive_and_negative_drivers() -> None:
    payload = build_market_decision_cockpit(
        market_regime_decision={
            "regime": "mixed",
            "confidence": "low",
            "confidenceScore": 0.42,
            "driverScores": {
                "breadthParticipation": {
                    "score": 68,
                    "evidenceState": "score_grade",
                    "reasons": [],
                    "evidenceCount": 2,
                    "observations": ["breadth participation is broad"],
                },
                "volatilityStructure": {
                    "score": -72,
                    "evidenceState": "score_grade",
                    "reasons": [],
                    "evidenceCount": 2,
                    "observations": ["volatility pressure is elevated"],
                },
                "dealerGamma": {
                    "score": 0,
                    "evidenceState": "unavailable",
                    "reasons": ["live_gex_not_implemented_v1"],
                    "evidenceCount": 0,
                    "observations": [],
                },
            },
            "explanation": {
                "whyThisRegime": ["mixed selected from deterministic driver agreement."],
                "whatConfirmsIt": ["Breadth participation remains supportive with score-grade evidence."],
                "whatInvalidatesIt": ["Driver alignment weakens or evidence quality deteriorates."],
                "keyTriggerLevels": [],
            },
            "researchPriorities": {
                "watchToday": ["Breadth participation"],
                "needsMoreEvidence": ["dealerGamma:unavailable"],
                "investigateNext": ["Resolve conflicting driver evidence."],
            },
            "dataQuality": {
                "evidenceGrade": "limited",
                "availableDriverCount": 2,
                "scoringDriverCount": 2,
                "blockedDriverCount": 0,
                "missingDriverCount": 1,
                "proxyEvidenceCount": 0,
                "confidenceCapReasons": ["mixed_driver_alignment"],
            },
            "missingEvidence": ["dealerGamma:unavailable"],
            "updatedAt": "2026-06-14T21:00:00+00:00",
        },
        research_candidates=[_candidate()],
        generated_at="2026-06-15T00:00:00+00:00",
    )

    attribution = payload["driverAttribution"]

    assert attribution["topPositiveDrivers"][0]["driver"] == "breadthParticipation"
    assert attribution["topNegativeDrivers"][0]["driver"] == "volatilityStructure"
    assert attribution["conflictingDrivers"] == [
        {
            "driver": "volatilityStructure",
            "score": -72,
            "condition": "Negative driver conflicts with positive regime evidence.",
            "currentEvidence": ["volatility pressure is elevated"],
        }
    ]
    assert payload["whatChanged"]["observations"][0] == {
        "field": "marketRegimeDecision.updatedAt",
        "value": "2026-06-14T21:00:00+00:00",
        "interpretation": "Current payload timestamp is available; no historical baseline is inferred.",
    }


def test_options_evidence_remains_observation_only_even_when_contract_inputs_are_complete() -> None:
    payload = build_market_decision_cockpit(
        market_inputs=_regime_ready_inputs(),
        research_candidates=[_candidate()],
        option_contracts=_complete_option_contracts(),
        option_spot=100.0,
        generated_at="2026-06-15T00:00:00+00:00",
    )

    options = payload["optionsStructureStatus"]

    assert options["gammaEvidenceStatus"] == "ready_observation"
    assert options["observationOnly"] is True
    assert options["decisionGrade"] is False
    assert options["blockedReasonCodes"] == ["observation_only_not_decision_grade"]
    assert options["missingEvidence"] == []
    assert payload["cockpitReadiness"] == {
        "status": "ready",
        "reasons": ["core evidence is available for read-only decision support"],
    }

    serialized = _serialized_values(options)
    for forbidden in ("support level", "resistance level", "dealer book", "position"):
        assert forbidden not in serialized


def test_service_does_not_import_protected_runtime_domains() -> None:
    tree = ast.parse((REPO_ROOT / "src/services/market_decision_cockpit_service.py").read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    for module in imports:
        assert not any(module == prefix or module.startswith(f"{prefix}.") for prefix in FORBIDDEN_IMPORT_PREFIXES)
