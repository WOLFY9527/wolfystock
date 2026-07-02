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
FORBIDDEN_RAW_NARRATIVE_TOKENS = (
    "riskOn",
    "lowConfidence",
    "market_regime_low_confidence",
    "research_candidates_unavailable",
    "option_chain_unavailable",
    "options_observation_only",
    "historical_baseline_unavailable",
    "dealerGamma:unavailable",
    "live_gex_not_implemented_v1",
    "observation_only_not_decision_grade",
    "missing_spot_reference",
)
FORBIDDEN_CONSUMER_REASON_TOKENS = (
    "_blocked",
    "_gate",
    "freshness_blocked",
    "proxy_or_sample_evidence_blocked",
    "source_authority_or_score_gate_blocked",
    "source_authority_blocked",
    "score_gate",
)
NARRATIVE_KEYS = (
    "marketRegimeSummary",
    "whatChanged",
    "topResearchPriorities",
    "scannerHighlights",
    "watchlistHighlights",
    "portfolioHighlights",
    "scenarioRisks",
    "evidenceGaps",
    "degradedInputs",
    "drilldownTargets",
    "researchWorkflow",
    "crossSurfaceEvidence",
    "topResearchQuestions",
    "priorityDrilldowns",
    "evidenceConflicts",
    "degradedSurfaceSummary",
    "nextObservationSteps",
    "noAdviceDisclosure",
)
ROUTE_RE = re.compile(r"^/[A-Za-z0-9][A-Za-z0-9/_-]*(?:\?[A-Za-z0-9=&._%-]+)?$")
INTERNAL_CODE_RE = re.compile(r"[a-z][a-z0-9]*_[a-z0-9_]+|[a-zA-Z]+:[a-zA-Z0-9_.-]+|=")


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


def _read_model(
    *,
    readiness_label: str = "product_ready",
    status: str = "ok",
    regime_label: str = "risk_off",
) -> dict[str, Any]:
    projection = {
        "consumerSafe": True,
        "contractVersion": "market_regime_evidence_projection_v1",
        "sourceContractVersion": "market_regime_evidence_pack_v1",
        "status": "ready" if readiness_label == "product_ready" else status,
        "readiness": "ready" if readiness_label == "product_ready" else readiness_label,
        "label": regime_label,
        "confidence": 0.71 if readiness_label == "product_ready" else 0.0,
        "asOf": "2026-03-02",
        "generatedAt": "2026-03-02T00:00:00+00:00",
        "noAdviceDisclosure": "Observation-only market structure evidence; not investment advice.",
        "dataQuality": {
            "status": "ready" if readiness_label == "product_ready" else status,
            "summary": "Local evidence is available." if readiness_label == "product_ready" else "Local evidence is blocked.",
            "reasonCodes": [] if readiness_label == "product_ready" else ["historical_ohlcv"],
        },
        "evidencePreview": {
            "indexTrend": {"symbol": "SPY", "return20d": -0.08, "closeVsMa20": "below", "state": "available"},
            "breadth": {
                "percentAboveMovingAverage": 0.0,
                "aboveMovingAverageCount": 0,
                "evaluatedCount": 4,
                "skippedCount": 0 if readiness_label == "product_ready" else 1,
                "state": "available" if readiness_label == "product_ready" else "insufficient_data",
            },
            "volatilityRisk": {
                "realizedVolatility20d": 0.2,
                "volatilityState": "normal",
                "state": "available",
            },
            "concentrationLeadership": {
                "state": "leaders_lagging",
                "evaluatedCount": 4,
                "skippedCount": 0,
                "relativeReturn20d": -0.02,
            },
            "dataCoverage": {
                "state": "available" if readiness_label == "product_ready" else "missing",
                "usedSymbolCount": 4 if readiness_label == "product_ready" else 0,
                "skippedSymbolCount": 0 if readiness_label == "product_ready" else 4,
                "usedSymbols": ["SPY", "QQQ", "AAPL", "MSFT"] if readiness_label == "product_ready" else [],
                "skippedSymbols": [],
            },
        },
        "readOnlyBoundary": {
            "localEvidenceOnly": True,
            "externalCallsEnabled": False,
            "networkCallsEnabled": False,
            "mutationEnabled": False,
        },
        "providerCallsEnabled": False,
        "networkCallsEnabled": False,
        "mutationEnabled": False,
    }
    return {
        "consumerSafe": True,
        "noAdvice": True,
        "contractVersion": "market_regime_read_model_v1",
        "sourceEvidenceContractVersion": "market_regime_evidence_pack_v1",
        "status": status,
        "market": "US",
        "symbols": ["SPY", "QQQ", "AAPL", "MSFT"],
        "benchmarkSymbol": "SPY",
        "growthProxySymbol": "QQQ",
        "regime": {"label": regime_label, "status": status, "source": "deterministic_evidence_fields"},
        "regimeLabel": regime_label,
        "regimeStatus": status,
        "productSummary": "Risk-off evidence is currently dominant across the bounded read model.",
        "regimeEvidenceProjection": projection,
        "evidenceCards": [
            {
                "id": "benchmark_trend",
                "title": "Benchmark Trend",
                "status": "negative",
                "severity": "warning",
                "headline": "Benchmark trend evidence is negative.",
                "metrics": [],
                "reasons": ["Benchmark local trend fields are negative."],
                "sourceFields": ["evidence.benchmarkTrend.return20d"],
                "consumerSafe": True,
            },
            {
                "id": "breadth",
                "title": "Breadth",
                "status": "negative",
                "severity": "warning",
                "headline": "Breadth evidence is weak.",
                "metrics": [],
                "reasons": ["Breadth evidence is weak."],
                "sourceFields": ["evidence.breadthProxy.percentAboveMa20"],
                "consumerSafe": True,
            },
            {
                "id": "data_quality",
                "title": "Data Quality",
                "status": "positive" if readiness_label == "product_ready" else "degraded",
                "severity": "info" if readiness_label == "product_ready" else "blocker",
                "headline": "Data quality is product-ready."
                if readiness_label == "product_ready"
                else "Data quality blocks the read model.",
                "metrics": [],
                "reasons": [],
                "sourceFields": ["missingDataFamilies"],
                "consumerSafe": True,
            },
        ],
        "dataQuality": {
            "adjustedCoverageState": "available" if readiness_label == "product_ready" else "missing",
            "missingDataFamilies": [] if readiness_label == "product_ready" else ["historical_ohlcv"],
            "blockedProductSurfaces": [] if readiness_label == "product_ready" else ["Market Overview"],
        },
        "readiness": {
            "label": readiness_label,
            "status": status,
            "missingDataFamilies": [] if readiness_label == "product_ready" else ["historical_ohlcv"],
            "blockedProductSurfaces": [] if readiness_label == "product_ready" else ["Market Overview"],
            "nextOperatorAction": "Market regime read model is available from local evidence inputs."
            if readiness_label == "product_ready"
            else "Provide readable local evidence inputs, then rerun the read model.",
        },
        "missingDataFamilies": [] if readiness_label == "product_ready" else ["historical_ohlcv"],
        "blockedProductSurfaces": [] if readiness_label == "product_ready" else ["Market Overview"],
        "nextOperatorAction": "Market regime read model is available from local evidence inputs.",
        "networkCallsEnabled": False,
        "mutationEnabled": False,
        "providerCallsEnabled": False,
    }


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


def _assert_consumer_safe_cockpit_narrative(payload: dict[str, Any]) -> None:
    for key in NARRATIVE_KEYS:
        assert key in payload
    narrative = {key: payload[key] for key in NARRATIVE_KEYS}
    serialized = _serialized_values(narrative)
    for token in FORBIDDEN_RAW_NARRATIVE_TOKENS:
        assert token not in serialized
    assert re.search(r"\b[a-z]+(?:_[a-z0-9]+)+\b", serialized) is None
    assert re.search(r"\b[a-z][a-z0-9]+:[a-z0-9_]+\b", serialized) is None
    for target in payload["drilldownTargets"]:
        assert ROUTE_RE.fullmatch(target["route"])
        assert not target["route"].startswith("/api/")
    for key in (
        "researchWorkflow",
        "crossSurfaceEvidence",
        "topResearchQuestions",
        "priorityDrilldowns",
        "evidenceConflicts",
        "degradedSurfaceSummary",
    ):
        _assert_routes_safe(payload[key])
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False


def _assert_routes_safe(payload: object) -> None:
    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "route":
                    assert isinstance(item, str)
                    assert ROUTE_RE.fullmatch(item)
                    assert not item.startswith("/api/")
                else:
                    visit(item)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                visit(item)

    visit(payload)


def _assert_consumer_issues_safe(issues: object, raw_codes: tuple[str, ...]) -> None:
    serialized = json.dumps(issues, ensure_ascii=False).lower()
    for raw_code in raw_codes:
        assert raw_code.lower() not in serialized
    assert INTERNAL_CODE_RE.search(serialized) is None
    for forbidden in FORBIDDEN_PUBLIC_TERMS:
        if forbidden in FORBIDDEN_PUBLIC_WORD_TERMS:
            assert re.search(rf"\b{re.escape(forbidden)}\b", serialized) is None
        else:
            assert forbidden not in serialized


def _assert_no_raw_consumer_reason_tokens(payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for token in FORBIDDEN_CONSUMER_REASON_TOKENS:
        assert token not in serialized


def test_cockpit_uses_regime_engine_as_primary_judgment_and_shapes_safe_aggregate() -> None:
    payload = build_market_decision_cockpit(
        market_inputs=_regime_ready_inputs(),
        research_candidates=[_candidate()],
        generated_at="2026-06-15T00:00:00+00:00",
    )

    assert payload["schemaVersion"] == "market_decision_cockpit.v1"
    assert payload["generatedAt"] == "2026-06-15T00:00:00+00:00"
    assert payload["noAdviceDisclosure"]
    assert payload["observationOnly"] is True
    assert payload["decisionGrade"] is False
    assert payload["marketRegimeSummary"]["regime"] == "Risk-on observation"

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
    assert "Options gamma unavailable" in attribution["unavailableDrivers"][0]["reasonCodes"]

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
    assert isinstance(what_changed, list)
    assert what_changed == [
        "Current regime observation is Risk-on observation with moderate confidence.",
        "Research queue quality is mixed.",
        "Options structure evidence is unavailable for this cockpit snapshot.",
    ]

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
    assert "Options chain unavailable" in options["blockedReasonCodes"]
    assert "Spot reference missing" in options["blockedReasonCodes"]
    assert "consumerIssues" in options
    _assert_consumer_issues_safe(
        options["consumerIssues"],
        ("option_chain_unavailable", "missing_spot_reference", "observation_only_not_decision_grade"),
    )

    assert payload["cockpitSummary"]["whatChanged"]
    assert payload["cockpitSummary"]["whyItMatters"]
    assert payload["cockpitSummary"]["whatToWatch"]
    assert payload["cockpitSummary"]["confidenceLimits"]
    assert payload["dataQuality"]["status"] == "degraded"
    assert payload["consumerIssues"]
    assert payload["dataQuality"]["consumerIssues"]
    assert "Options gamma unavailable" in {issue["label"] for issue in payload["consumerIssues"]}
    assert {item["surface"] for item in payload["researchWorkflow"]} >= {
        "Market Overview",
        "Research Radar",
        "Portfolio Structure Review",
        "Scenario Lab",
        "Stock Structure",
        "Options / Gamma Observation",
    }
    assert any(
        set(item["surfaces"]) >= {"Market Overview", "Research Radar"}
        for item in payload["crossSurfaceEvidence"]
    )
    assert any("structure verification" in item["question"].lower() for item in payload["topResearchQuestions"])
    assert any(item["route"] == "/scenario-lab" for item in payload["priorityDrilldowns"])
    assert isinstance(payload["evidenceConflicts"], list)
    assert any(item["surface"] == "Portfolio Structure Review" for item in payload["degradedSurfaceSummary"])
    assert any(item["surface"] == "Options / Gamma Observation" for item in payload["degradedSurfaceSummary"])
    assert payload["nextObservationSteps"]

    _assert_no_forbidden_public_terms(payload)
    _assert_consumer_safe_cockpit_narrative(payload)


def test_product_ready_read_model_becomes_primary_regime_context_without_low_confidence_contradiction() -> None:
    payload = build_market_decision_cockpit(
        market_regime_decision={
            "regime": "lowConfidence",
            "confidence": "low",
            "confidenceScore": 0.18,
            "driverScores": {},
            "explanation": {
                "whyThisRegime": ["lowConfidence selected from deterministic driver agreement."],
                "whatConfirmsIt": [],
                "whatInvalidatesIt": [],
            },
            "researchPriorities": {"watchToday": [], "needsMoreEvidence": [], "investigateNext": []},
            "dataQuality": {
                "evidenceGrade": "limited",
                "availableDriverCount": 0,
                "scoringDriverCount": 0,
                "blockedDriverCount": 0,
                "missingDriverCount": 0,
                "proxyEvidenceCount": 0,
                "confidenceCapReasons": [],
            },
            "missingEvidence": ["market_regime_low_confidence"],
        },
        market_regime_read_model=_read_model(),
        research_candidates=[],
        generated_at="2026-06-15T00:00:00+00:00",
    )

    assert payload["marketRegimeReadModel"]["primaryContext"] is True
    assert payload["marketRegimeReadModel"]["readinessLabel"] == "product_ready"
    assert payload["marketRegimeReadModel"]["regimeLabel"] == "risk_off"
    projection = payload["marketRegimeReadModel"]["regimeEvidenceProjection"]
    assert projection["contractVersion"] == "market_regime_evidence_projection_v1"
    assert projection["sourceContractVersion"] == "market_regime_evidence_pack_v1"
    assert projection["status"] == "ready"
    assert projection["label"] == "risk_off"
    assert projection["confidence"] == 0.71
    assert projection["consumerSafe"] is True
    assert projection["providerCallsEnabled"] is False
    assert projection["networkCallsEnabled"] is False
    assert projection["mutationEnabled"] is False
    assert projection["readOnlyBoundary"]["externalCallsEnabled"] is False
    assert projection["evidencePreview"]["indexTrend"]["closeVsMa20"] == "below"
    assert projection["evidencePreview"]["breadth"]["evaluatedCount"] == 4
    assert payload["marketRegimeDecision"]["regime"] == "risk_off"
    assert payload["marketRegimeDecision"]["readModelPrimaryContext"] is True
    assert payload["marketRegimeDecision"]["missingEvidence"] == []
    assert payload["marketRegimeSummary"]["regime"] == "Risk-off observation"
    assert payload["marketRegimeSummary"]["readinessLabel"] == "product_ready"
    assert payload["whatChanged"][0] == "Market Regime Read Model is product-ready: Risk-off observation."
    assert "Low-confidence observation" not in json.dumps(payload["whatChanged"], ensure_ascii=False)
    assert payload["dataQuality"]["status"] == "ready"
    assert payload["cockpitReadiness"]["status"] == "ready"
    assert payload["advancedDecisionDiagnostics"] == {
        "status": "secondary",
        "primaryOverriddenByReadModel": True,
        "advancedRegime": "lowConfidence",
        "advancedConfidence": "low",
        "readModelReadinessLabel": "product_ready",
        "reason": "Market Regime Read Model is product-ready, so advanced cockpit evidence is secondary.",
    }
    _assert_no_forbidden_public_terms(payload)


def test_product_ready_read_model_keeps_advanced_gaps_visible_as_secondary() -> None:
    payload = build_market_decision_cockpit(
        market_regime_decision={"regime": "lowConfidence", "confidence": "low", "driverScores": {}},
        market_regime_read_model=_read_model(),
        research_candidates=[],
        generated_at="2026-06-15T00:00:00+00:00",
    )

    degraded_reasons = {item["reason"] for item in payload["degradedInputs"]}
    degraded_surfaces = {(item["surface"], item["reason"]) for item in payload["degradedSurfaceSummary"]}

    assert "Market regime evidence is low confidence." not in degraded_reasons
    assert "Secondary Research Radar evidence is unavailable." in degraded_reasons
    assert "Secondary options structure evidence is unavailable." in degraded_reasons
    assert ("Research Radar", "Secondary Research Radar evidence is unavailable.") in degraded_surfaces
    assert (
        "Options / Gamma Observation",
        "Secondary options structure evidence is unavailable.",
    ) in degraded_surfaces
    assert "Secondary Research Radar evidence unavailable" in payload["dataQuality"]["reasonCodes"]
    assert "Secondary options structure evidence unavailable" in payload["dataQuality"]["reasonCodes"]
    assert "Advanced evidence observation-only" in payload["dataQuality"]["reasonCodes"]


def test_unready_read_model_fails_closed_as_primary_market_context() -> None:
    payload = build_market_decision_cockpit(
        market_regime_decision={
            "regime": "riskOn",
            "confidence": "high",
            "confidenceScore": 0.91,
            "driverScores": {},
            "dataQuality": {"availableDriverCount": 4, "scoringDriverCount": 4},
            "missingEvidence": [],
        },
        market_regime_read_model=_read_model(readiness_label="failed_closed", status="failed_closed", regime_label="insufficient_data"),
        research_candidates=[_candidate()],
        generated_at="2026-06-15T00:00:00+00:00",
    )

    assert payload["marketRegimeReadModel"]["primaryContext"] is False
    assert payload["marketRegimeReadModel"]["readinessLabel"] == "failed_closed"
    projection = payload["marketRegimeReadModel"]["regimeEvidenceProjection"]
    assert projection["status"] == "failed_closed"
    assert projection["readiness"] == "failed_closed"
    assert projection["label"] == "insufficient_data"
    assert projection["confidence"] == 0.0
    assert projection["dataQuality"]["reasonCodes"] == ["historical_ohlcv"]
    assert payload["marketRegimeDecision"]["regime"] == "insufficient_data"
    assert payload["marketRegimeDecision"]["confidence"] == "low"
    assert payload["marketRegimeSummary"]["regime"] == "Insufficient market evidence"
    assert payload["dataQuality"]["status"] == "blocked"
    assert payload["cockpitReadiness"]["status"] in {"degraded", "insufficient"}
    assert "Market Regime Read Model failed closed" in payload["dataQuality"]["reasonCodes"]
    assert payload["advancedDecisionDiagnostics"]["status"] == "primary"
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
        "reasonCodes": ["Research candidates unavailable"],
    }
    assert payload["optionsStructureStatus"]["gammaEvidenceStatus"] == "unavailable"
    assert payload["optionsStructureStatus"]["decisionGrade"] is False
    assert payload["dataQuality"]["status"] == "blocked"
    assert "Research candidates unavailable" in payload["dataQuality"]["reasonCodes"]
    assert "Options chain unavailable" in payload["dataQuality"]["reasonCodes"]
    assert "research_candidates_unavailable" not in payload["dataQuality"]["reasonCodes"]
    assert "option_chain_unavailable" not in payload["dataQuality"]["reasonCodes"]
    assert payload["cockpitReadiness"] == {
        "status": "insufficient",
        "reasons": [
            "market regime evidence is insufficient",
            "research radar candidates are unavailable",
            "options structure evidence is unavailable",
        ],
    }
    assert payload["confidenceDiagnostics"]["missingEvidenceImpact"]
    assert payload["whatChanged"] == [
        "Current regime observation is Low-confidence observation with low confidence.",
        "Research queue quality is thin.",
        "Options structure evidence is unavailable for this cockpit snapshot.",
    ]
    assert payload["driverAttribution"]["topPositiveDrivers"] == []
    assert payload["driverAttribution"]["topNegativeDrivers"] == []
    assert payload["driverAttribution"]["unavailableDrivers"]
    assert payload["researchQueuePreview"]["consumerIssues"]
    assert payload["optionsStructureStatus"]["consumerIssues"]
    assert payload["consumerIssues"]
    assert payload["priorityDrilldowns"]
    assert any(item["surface"] == "Research Radar" for item in payload["degradedSurfaceSummary"])
    assert any(item["surface"] == "Stock Structure" for item in payload["degradedSurfaceSummary"])
    assert any(item["surface"] == "Options / Gamma Observation" for item in payload["degradedSurfaceSummary"])
    assert payload["topResearchQuestions"]
    _assert_consumer_issues_safe(
        payload["consumerIssues"],
        ("research_candidates_unavailable", "option_chain_unavailable", "missing_contracts"),
    )


def test_cockpit_consumer_payload_redacts_raw_reason_codes_from_reason_fields() -> None:
    payload = build_market_decision_cockpit(
        market_regime_decision={
            "regime": "lowConfidence",
            "confidence": "low",
            "confidenceScore": 0.24,
            "driverScores": {
                "breadthParticipation": {
                    "score": 0,
                    "evidenceState": "blocked",
                    "reasons": [
                        "freshness_blocked:fallback",
                        "proxy_or_sample_evidence_blocked",
                    ],
                    "evidenceCount": 0,
                    "observations": [],
                },
                "sectorThemeRotation": {
                    "score": 0,
                    "evidenceState": "blocked",
                    "reasons": ["source_authority_or_score_gate_blocked"],
                    "evidenceCount": 0,
                    "observations": [],
                },
            },
            "explanation": {
                "whyThisRegime": ["lowConfidence selected from deterministic driver agreement."],
                "whatConfirmsIt": [],
                "whatInvalidatesIt": [],
                "keyTriggerLevels": [],
            },
            "researchPriorities": {
                "watchToday": [],
                "needsMoreEvidence": [
                    "freshness_blocked:fallback",
                    "source_authority_or_score_gate_blocked",
                ],
                "investigateNext": [],
            },
            "dataQuality": {
                "evidenceGrade": "limited",
                "availableDriverCount": 0,
                "scoringDriverCount": 0,
                "blockedDriverCount": 2,
                "missingDriverCount": 0,
                "proxyEvidenceCount": 1,
                "confidenceCapReasons": ["source_authority_or_score_gate_blocked"],
            },
            "missingEvidence": [
                "freshness_blocked:fallback",
                "proxy_or_sample_evidence_blocked",
                "source_authority_or_score_gate_blocked",
            ],
            "updatedAt": "2026-06-14T21:00:00+00:00",
        },
        research_candidates=[],
        generated_at="2026-06-15T00:00:00+00:00",
    )

    consumer_payload = {
        "marketRegimeDecision": payload["marketRegimeDecision"],
        "scenarioRisks": payload["scenarioRisks"],
        "evidenceGaps": payload["evidenceGaps"],
        "dataQuality": payload["dataQuality"],
        "driverAttribution": payload["driverAttribution"],
        "confidenceDiagnostics": payload["confidenceDiagnostics"],
        "consumerIssues": payload["consumerIssues"],
    }

    _assert_no_raw_consumer_reason_tokens(consumer_payload)
    assert "数据新鲜度尚未确认，当前仅显示降级观察结果" in payload["marketRegimeDecision"]["missingEvidence"]
    assert "当前仅有样本或代理证据，暂不足以代表完整市场结构" in payload["marketRegimeDecision"]["missingEvidence"]
    assert "当前数据源权威性或评分级别不足，暂不能形成可靠研究结论" in payload["marketRegimeDecision"]["missingEvidence"]


def test_high_regime_confidence_is_limited_when_critical_evidence_is_blocked() -> None:
    payload = build_market_decision_cockpit(
        market_regime_decision={
            "regime": "riskOn",
            "confidence": "high",
            "confidenceScore": 0.91,
            "driverScores": {
                "breadthParticipation": {
                    "score": 82,
                    "evidenceState": "score_grade",
                    "reasons": [],
                    "evidenceCount": 3,
                    "observations": ["Breadth evidence is supportive."],
                },
                "dealerGamma": {
                    "score": 0,
                    "evidenceState": "unavailable",
                    "reasons": ["dealerGamma:unavailable"],
                    "evidenceCount": 0,
                    "observations": [],
                },
            },
            "explanation": {
                "whyThisRegime": ["riskOn selected from deterministic driver agreement."],
                "whatConfirmsIt": ["Breadth participation is supportive."],
                "whatInvalidatesIt": ["Options structure evidence remains unavailable."],
                "keyTriggerLevels": [],
            },
            "researchPriorities": {
                "watchToday": ["Breadth participation"],
                "needsMoreEvidence": ["dealerGamma:unavailable"],
                "investigateNext": [],
            },
            "dataQuality": {
                "evidenceGrade": "limited",
                "availableDriverCount": 3,
                "scoringDriverCount": 3,
                "blockedDriverCount": 0,
                "missingDriverCount": 1,
                "proxyEvidenceCount": 0,
                "confidenceCapReasons": ["dealerGamma:unavailable"],
            },
            "missingEvidence": ["dealerGamma:unavailable"],
            "updatedAt": "2026-06-14T21:00:00+00:00",
        },
        research_candidates=[_candidate()],
        generated_at="2026-06-15T00:00:00+00:00",
    )

    assert payload["marketRegimeDecision"]["confidence"] == "high"
    assert payload["marketRegimeSummary"]["rawConfidence"] == "high"
    assert payload["marketRegimeSummary"]["confidence"] == "moderate"
    assert payload["marketRegimeSummary"]["confidenceCap"] == {
        "value": 60,
        "label": "medium",
        "reasons": ["critical evidence missing"],
    }
    assert payload["marketRegimeSummary"]["confidenceState"]["status"] == "evidence limited"
    assert payload["confidenceDiagnostics"]["evidenceStrength"]["consumerConfidence"] == "medium"
    assert payload["confidenceDiagnostics"]["evidenceStrength"]["rawConfidence"] == "high"
    assert payload["whatChanged"][0] == "Current regime observation is Risk-on observation with moderate confidence."


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
    assert payload["whatChanged"][0] == "Current regime observation is Mixed-regime observation with low confidence."


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
    assert options["blockedReasonCodes"] == ["Observation-only context"]
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
