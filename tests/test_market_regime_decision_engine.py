# -*- coding: utf-8 -*-
"""Tests for the deterministic market regime decision engine."""

from __future__ import annotations

import json

from src.services.market_regime_decision_engine import MarketRegimeDecisionEngine


def _item(
    symbol: str,
    value: float,
    *,
    change_percent: float = 0.0,
    source: str = "official_public",
    source_type: str = "official_public",
    trust_level: str = "high",
    freshness: str = "live",
    source_authority_allowed: bool = True,
    score_contribution_allowed: bool = True,
    observation_only: bool = False,
) -> dict:
    return {
        "symbol": symbol,
        "label": symbol,
        "value": value,
        "changePercent": change_percent,
        "source": source,
        "sourceType": source_type,
        "trustLevel": trust_level,
        "freshness": freshness,
        "sourceAuthorityAllowed": source_authority_allowed,
        "scoreContributionAllowed": score_contribution_allowed,
        "observationOnly": observation_only,
    }


def _base_score_grade_inputs() -> dict:
    return {
        "breadth": {"items": [_item("ADV_RATIO", 68.0, change_percent=4.0)]},
        "rates": {
            "items": [
                _item("VIX", 13.5, change_percent=-8.0),
                _item("US10Y", 4.18, change_percent=-1.2),
                _item("BAMLH0A0HYM2", 3.1, change_percent=-2.0),
            ]
        },
        "fx": {"items": [_item("DXY", 101.4, change_percent=-0.5)]},
        "futures": {
            "items": [
                _item("ES", 5400.0, change_percent=0.8, source_type="exchange_public"),
                _item("NQ", 19300.0, change_percent=1.1, source_type="exchange_public"),
            ]
        },
        "crypto": {"items": [_item("BTC", 68000.0, change_percent=1.9, source_type="exchange_public")]},
        "sectors": {
            "items": [
                {
                    **_item("AI_SOFTWARE", 72.0, change_percent=2.2, source_type="tier_1_configured"),
                    "rotationScore": 72.0,
                    "rankEligible": True,
                    "headlineEligible": True,
                }
            ]
        },
        "capitalFlowSignal": {
            "likelyDestination": "growth_ai_software_semis",
            "score": 74.0,
            "freshness": "live",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "observationOnly": False,
        },
    }


def test_risk_on_decision_uses_score_grade_inputs_and_research_language() -> None:
    decision = MarketRegimeDecisionEngine().decide(_base_score_grade_inputs())

    assert decision["schemaVersion"] == "market_regime_decision_engine.v1"
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
    for driver in decision["driverScores"].values():
        assert -100 <= driver["score"] <= 100

    assert decision["driverScores"]["dealerGamma"]["evidenceState"] == "unavailable"
    assert "live_gex_not_implemented_v1" in decision["driverScores"]["dealerGamma"]["reasons"]
    assert decision["explanation"]["whyThisRegime"]
    assert decision["explanation"]["whatConfirmsIt"]
    assert decision["explanation"]["whatInvalidatesIt"]
    assert decision["explanation"]["keyTriggerLevels"]
    assert decision["researchPriorities"]["watchToday"]
    assert decision["researchPriorities"]["needsMoreEvidence"]
    assert decision["researchPriorities"]["investigateNext"]
    assert decision["noAdviceDisclosure"] == "Research support only; not personalized financial advice."

    serialized = json.dumps(decision, ensure_ascii=False).lower()
    for forbidden in ("buy", "sell", "position sizing", "target price", "stop loss"):
        assert forbidden not in serialized


def test_proxy_and_observation_only_inputs_cap_confidence_and_do_not_drive_strong_regime() -> None:
    inputs = _base_score_grade_inputs()
    for panel in ("breadth", "rates", "fx", "futures", "crypto", "sectors"):
        for item in inputs[panel]["items"]:
            item["source"] = "homepage_sample_proxy"
            item["sourceType"] = "unofficial_proxy"
            item["freshness"] = "fallback"
            item["sourceAuthorityAllowed"] = False
            item["scoreContributionAllowed"] = False
            item["observationOnly"] = True
    inputs["capitalFlowSignal"].update(
        {
            "source": "homepage_sample_proxy",
            "sourceType": "unofficial_proxy",
            "freshness": "fallback",
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "observationOnly": True,
        }
    )

    decision = MarketRegimeDecisionEngine().decide(inputs)

    assert decision["regime"] == "lowConfidence"
    assert decision["confidence"] == "low"
    assert decision["dataQuality"]["proxyEvidenceCount"] > 0
    assert decision["dataQuality"]["confidenceCapReasons"]
    assert "source_authority_or_score_gate_blocked" in decision["missingEvidence"]


def test_conflicting_drivers_return_mixed_low_confidence() -> None:
    inputs = _base_score_grade_inputs()
    inputs["breadth"]["items"] = [_item("ADV_RATIO", 31.0, change_percent=-6.0)]
    inputs["rates"]["items"] = [
        _item("VIX", 24.0, change_percent=11.0),
        _item("US10Y", 4.85, change_percent=3.0),
    ]
    inputs["fx"]["items"] = [_item("DXY", 106.2, change_percent=0.8)]
    inputs["futures"]["items"] = [_item("ES", 5400.0, change_percent=1.0, source_type="exchange_public")]
    inputs["crypto"]["items"] = [_item("BTC", 68000.0, change_percent=2.0, source_type="exchange_public")]
    inputs["capitalFlowSignal"]["score"] = 68.0

    decision = MarketRegimeDecisionEngine().decide(inputs)

    assert decision["regime"] in {"mixed", "lowConfidence"}
    assert decision["confidence"] == "low"
    assert decision["driverScores"]["breadthParticipation"]["score"] < 0
    assert decision["driverScores"]["crossAssetRisk"]["score"] > 0


def test_downside_acceleration_risk_requires_deterioration_cluster() -> None:
    inputs = _base_score_grade_inputs()
    inputs["breadth"]["items"] = [_item("ADV_RATIO", 24.0, change_percent=-9.0)]
    inputs["rates"]["items"] = [
        _item("VIX", 31.0, change_percent=18.0),
        _item("US10Y", 4.92, change_percent=3.8),
        _item("BAMLH0A0HYM2", 4.9, change_percent=8.0),
    ]
    inputs["fx"]["items"] = [_item("DXY", 107.0, change_percent=1.2)]
    inputs["futures"]["items"] = [_item("ES", 5200.0, change_percent=-1.9, source_type="exchange_public")]
    inputs["crypto"]["items"] = [_item("BTC", 62000.0, change_percent=-4.5, source_type="exchange_public")]
    inputs["capitalFlowSignal"]["score"] = -72.0

    decision = MarketRegimeDecisionEngine().decide(inputs)

    assert decision["regime"] == "downsideAccelerationRisk"
    assert decision["confidence"] in {"medium", "high"}
    assert decision["driverScores"]["volatilityStructure"]["score"] <= -50
    assert decision["driverScores"]["liquidityCredit"]["score"] <= -50


def test_event_risk_requires_live_event_evidence() -> None:
    sample_only = _base_score_grade_inputs()
    sample_only["events"] = {
        "items": [
            _item(
                "FOMC_SAMPLE",
                95.0,
                source="homepage_sample_proxy",
                source_type="unofficial_proxy",
                freshness="fallback",
                source_authority_allowed=False,
                score_contribution_allowed=False,
                observation_only=True,
            )
        ]
    }
    live_event = _base_score_grade_inputs()
    live_event["events"] = {
        "items": [
            _item(
                "FOMC_LIVE",
                92.0,
                source="official_calendar",
                source_type="official_public",
                freshness="live",
                source_authority_allowed=True,
                score_contribution_allowed=True,
            )
        ]
    }

    sample_decision = MarketRegimeDecisionEngine().decide(sample_only)
    live_decision = MarketRegimeDecisionEngine().decide(live_event)

    assert sample_decision["regime"] != "eventRisk"
    assert sample_decision["driverScores"]["eventCatalyst"]["evidenceState"] != "score_grade"
    assert live_decision["regime"] == "eventRisk"
    assert live_decision["confidence"] == "medium"


def test_volatility_compression_confidence_is_capped_without_gamma_evidence() -> None:
    inputs = _base_score_grade_inputs()
    inputs["breadth"]["items"] = [_item("ADV_RATIO", 51.0, change_percent=0.2)]
    inputs["rates"]["items"] = [_item("VIX", 11.8, change_percent=-9.0), _item("US10Y", 4.2, change_percent=-0.1)]
    inputs["fx"]["items"] = [_item("DXY", 102.0, change_percent=0.0)]
    inputs["futures"]["items"] = [_item("ES", 5400.0, change_percent=0.1, source_type="exchange_public")]
    inputs["crypto"]["items"] = [_item("BTC", 68000.0, change_percent=0.1, source_type="exchange_public")]
    inputs["capitalFlowSignal"]["score"] = 4.0

    decision = MarketRegimeDecisionEngine().decide(inputs)

    assert decision["regime"] == "volatilityCompression"
    assert decision["confidence"] != "high"
    assert "dealer_gamma_unavailable_caps_volatility_compression" in decision["dataQuality"]["confidenceCapReasons"]
