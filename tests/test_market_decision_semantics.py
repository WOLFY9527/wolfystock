# -*- coding: utf-8 -*-
"""Tests for the pure market decision semantics foundation."""

from __future__ import annotations

import ast
from pathlib import Path

from src.services.liquidity_impulse_synthesis_service import (
    LiquidityImpulseEvidenceItem,
    synthesize_liquidity_impulse,
)
from src.services.market_decision_semantics import (
    MARKET_DECISION_SEMANTICS_VERSION,
    MarketDecisionSemanticsService,
    derive_market_decision_semantics,
)
from src.services.market_regime_synthesis_service import (
    MarketRegimeEvidenceItem,
    synthesize_market_regime,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = REPO_ROOT / "src/services/market_decision_semantics.py"


def _regime_evidence(
    key: str,
    pillar: str,
    direction: str,
    *,
    z_score: float = 1.4,
    source_tier: str = "official_public",
    trust_level: str = "high",
    freshness: str = "live",
    observation_only: bool = False,
    score_contribution_allowed: bool = True,
    degradation_reason: str | None = None,
) -> MarketRegimeEvidenceItem:
    return MarketRegimeEvidenceItem(
        key=key,
        label=key,
        pillar=pillar,
        z_score=z_score,
        direction=direction,
        source="unit_fixture",
        source_tier=source_tier,
        trust_level=trust_level,
        freshness=freshness,
        observation_only=observation_only,
        score_contribution_allowed=score_contribution_allowed,
        as_of="2026-05-21T09:30:00+08:00",
        updated_at="2026-05-21T09:30:00+08:00",
        degradation_reason=degradation_reason,
    )


def _liquidity_evidence(
    key: str,
    pillar: str,
    direction: str,
    *,
    z_score: float = 1.4,
    source_tier: str = "official_public",
    trust_level: str = "high",
    freshness: str = "live",
    observation_only: bool = False,
    score_contribution_allowed: bool = True,
    included_in_score: bool | None = True,
    proxy_only: bool = False,
    degradation_reason: str | None = None,
) -> LiquidityImpulseEvidenceItem:
    return LiquidityImpulseEvidenceItem(
        key=key,
        label=key,
        pillar=pillar,
        z_score=z_score,
        direction=direction,
        source="unit_fixture",
        source_tier=source_tier,
        trust_level=trust_level,
        freshness=freshness,
        observation_only=observation_only,
        score_contribution_allowed=score_contribution_allowed,
        included_in_score=included_in_score,
        proxy_only=proxy_only,
        as_of="2026-05-21T09:30:00+08:00",
        updated_at="2026-05-21T09:30:00+08:00",
        degradation_reason=degradation_reason,
    )


def _risk_on_regime():
    return synthesize_market_regime(
        [
            _regime_evidence("spx", "risk_appetite", "up"),
            _regime_evidence("btc", "crypto_risk_beta", "up"),
            _regime_evidence("dxy", "dollar_pressure", "down"),
            _regime_evidence("vix", "volatility_stress", "down"),
        ]
    )


def _risk_off_regime():
    return synthesize_market_regime(
        [
            _regime_evidence("us10y", "rates_pressure", "up"),
            _regime_evidence("dxy", "dollar_pressure", "up"),
            _regime_evidence("btc", "crypto_risk_beta", "down"),
            _regime_evidence("spx", "risk_appetite", "down"),
        ]
    )


def _expanding_liquidity():
    return synthesize_liquidity_impulse(
        [
            _liquidity_evidence("btc", "crypto_liquidity_beta", "up", source_tier="exchange_public"),
            _liquidity_evidence("eth", "crypto_liquidity_beta", "up", source_tier="exchange_public"),
            _liquidity_evidence("dxy", "dollar_pressure", "down"),
            _liquidity_evidence("vix", "volatility_stress", "down"),
        ]
    )


def _contracting_liquidity():
    return synthesize_liquidity_impulse(
        [
            _liquidity_evidence("us10y", "rates_pressure", "up"),
            _liquidity_evidence("dxy", "dollar_pressure", "up"),
            _liquidity_evidence("btc", "crypto_liquidity_beta", "down"),
            _liquidity_evidence("spy_flow", "equity_flow_proxy", "down"),
        ]
    )


def _rotation_summary(
    *,
    score_contribution_allowed: bool = True,
    source_authority_allowed: bool = True,
    evidence_quality: str = "score_grade",
    rotation_score: float = 79.0,
    confidence: float = 0.62,
    stage: str = "confirmed_rotation",
    change_percent: float = 2.4,
) -> dict[str, object]:
    return {
        "id": "ai_applications",
        "label": "AI Applications",
        "rotationScore": rotation_score,
        "confidence": confidence,
        "stage": stage,
        "changePercent": change_percent,
        "source": "alpaca",
        "sourceTier": "tier_1_configured",
        "trustLevel": "high",
        "freshness": "cached",
        "sourceAuthorityAllowed": source_authority_allowed,
        "scoreContributionAllowed": score_contribution_allowed,
        "flowLanguageAllowed": score_contribution_allowed,
        "evidenceQuality": evidence_quality,
        "dataGaps": [] if score_contribution_allowed else ["proxy_context_only"],
    }


def test_score_grade_alignment_produces_observational_offensive_watch() -> None:
    result = derive_market_decision_semantics(
        _risk_on_regime(),
        _expanding_liquidity(),
        _rotation_summary(),
    )

    assert result.posture == "offensive"
    assert result.exposure_bias == "risk_on_watch"
    assert result.posture_confidence.label in {"medium", "high"}
    assert result.posture_confidence.cap_reasons == ()
    assert any(item["tilt"] == "liquidity_beta_watch" for item in result.style_tilts)
    assert any(item["tilt"] == "rotation_leadership_watch" for item in result.style_tilts)
    assert result.confirmation_signals
    assert result.invalidation_triggers
    assert any(boundary["claim"] == "observational_posture_watch" and boundary["allowed"] for boundary in result.claim_boundaries)
    assert all(boundary["claim"] != "direct_trade_action" or not boundary["allowed"] for boundary in result.claim_boundaries)


def test_low_confidence_alignment_keeps_tentative_watch_and_caps_style_claims() -> None:
    regime = {
        **_risk_on_regime().to_dict(),
        "confidence": 0.43,
        "confidenceLabel": "low",
        "counterEvidence": [{"key": "breadth", "label": "Breadth weakens", "detail": "Breadth confirmation is weak."}],
        "evidenceQuality": {
            **_risk_on_regime().to_dict()["evidenceQuality"],
            "conflictPenalty": 0.34,
        },
    }
    liquidity = {
        **_expanding_liquidity().to_dict(),
        "confidence": 0.46,
        "confidenceLabel": "low",
        "counterEvidence": [{"key": "vix", "label": "Volatility rebound", "detail": "Volatility is not fully confirming."}],
        "evidenceQuality": {
            **_expanding_liquidity().to_dict()["evidenceQuality"],
            "conflictPenalty": 0.3,
        },
    }

    result = MarketDecisionSemanticsService().derive(regime, liquidity, _rotation_summary())
    payload = result.to_dict()

    assert result.posture == "offensive"
    assert result.exposure_bias == "risk_on_watch"
    assert result.posture_confidence.label == "low"
    assert "tentative_bias_only" in result.posture_confidence.cap_reasons
    assert "counter_evidence_present" in result.posture_confidence.cap_reasons
    assert result.style_tilts == ()
    blocked = {item["claim"]: item for item in result.claim_boundaries if not item["allowed"]}
    assert blocked["style_tilt_watch"]["reasonCode"] == "tentative_bias_only"
    assert payload["postureConfidence"]["label"] == "low"
    assert payload["notInvestmentAdvice"] is True


def test_proxy_only_or_non_scoring_inputs_cannot_produce_posture_or_style_conclusions() -> None:
    regime = synthesize_market_regime(
        [
            _regime_evidence(
                "btc_obs",
                "crypto_risk_beta",
                "up",
                source_tier="unofficial_proxy",
                trust_level="usable_with_caution",
                freshness="stale",
                observation_only=True,
                score_contribution_allowed=False,
                degradation_reason="source_authority_router_rejected",
            ),
            _regime_evidence(
                "vix_obs",
                "volatility_stress",
                "down",
                source_tier="unofficial_proxy",
                trust_level="usable_with_caution",
                freshness="stale",
                observation_only=True,
                score_contribution_allowed=False,
                degradation_reason="source_authority_router_rejected",
            ),
            _regime_evidence(
                "dxy_obs",
                "dollar_pressure",
                "down",
                source_tier="unofficial_proxy",
                trust_level="usable_with_caution",
                freshness="stale",
                observation_only=True,
                score_contribution_allowed=False,
                degradation_reason="source_authority_router_rejected",
            ),
        ]
    )
    liquidity = synthesize_liquidity_impulse(
        [
            _liquidity_evidence(
                "btc_proxy",
                "crypto_liquidity_beta",
                "up",
                source_tier="unofficial_proxy",
                trust_level="usable_with_caution",
                freshness="delayed",
                proxy_only=True,
                score_contribution_allowed=True,
            ),
            _liquidity_evidence(
                "dxy_proxy",
                "dollar_pressure",
                "down",
                source_tier="unofficial_proxy",
                trust_level="usable_with_caution",
                freshness="delayed",
                proxy_only=True,
                score_contribution_allowed=True,
            ),
            _liquidity_evidence(
                "vix_proxy",
                "volatility_stress",
                "down",
                source_tier="unofficial_proxy",
                trust_level="usable_with_caution",
                freshness="delayed",
                proxy_only=True,
                score_contribution_allowed=True,
            ),
        ]
    )

    result = derive_market_decision_semantics(
        regime,
        liquidity,
        _rotation_summary(
            score_contribution_allowed=False,
            source_authority_allowed=False,
            evidence_quality="taxonomy_only",
            stage="early_watch",
            change_percent=1.1,
        ),
    )

    assert result.posture == "data_insufficient"
    assert result.exposure_bias == "no_bias_data_insufficient"
    assert result.style_tilts == ()
    assert "proxy_or_observation_only_evidence" in result.posture_confidence.cap_reasons
    blocked = {item["claim"]: item for item in result.claim_boundaries if not item["allowed"]}
    assert blocked["observational_posture_watch"]["reasonCode"] == "insufficient_score_grade_evidence"
    assert blocked["style_tilt_watch"]["reasonCode"] == "insufficient_score_grade_evidence"


def test_conflicting_pillars_reduce_certainty_and_require_confirmation_and_invalidation() -> None:
    regime = _risk_on_regime().to_dict()
    regime["counterEvidence"] = [
        {"key": "rates", "label": "Rates pressure", "detail": "Rates continue to rise against the risk-on read."}
    ]
    regime["evidenceQuality"] = {**regime["evidenceQuality"], "conflictPenalty": 0.28}

    liquidity = _contracting_liquidity().to_dict()
    liquidity["counterEvidence"] = [
        {"key": "crypto", "label": "Crypto weakens", "detail": "Crypto beta weakens against the broader posture."}
    ]
    liquidity["evidenceQuality"] = {**liquidity["evidenceQuality"], "conflictPenalty": 0.31}

    result = derive_market_decision_semantics(regime, liquidity)

    assert result.posture == "neutral"
    assert result.exposure_bias == "balanced_watch"
    assert result.posture_confidence.label in {"low", "medium"}
    assert "conflicting_primary_pillars" in result.posture_confidence.cap_reasons
    assert "counter_evidence_present" in result.posture_confidence.cap_reasons
    assert result.confirmation_signals
    assert result.invalidation_triggers
    assert result.counter_evidence


def test_missing_scoring_pillars_produce_no_posture_and_no_bias() -> None:
    regime = synthesize_market_regime([_regime_evidence("btc", "crypto_risk_beta", "up")])
    liquidity = synthesize_liquidity_impulse([_liquidity_evidence("btc", "crypto_liquidity_beta", "up")])

    result = derive_market_decision_semantics(regime, liquidity)

    assert result.posture == "data_insufficient"
    assert result.exposure_bias == "no_bias_data_insufficient"
    assert result.posture_confidence.label == "insufficient"
    assert "missing_scoring_pillars" in result.posture_confidence.cap_reasons
    assert result.confirmation_signals == ()
    assert result.style_tilts == ()


def test_result_payload_contains_required_fields_and_camel_case_projection() -> None:
    payload = derive_market_decision_semantics(
        _risk_off_regime(),
        _contracting_liquidity(),
    ).to_dict()

    for key in (
        "version",
        "posture",
        "postureConfidence",
        "exposureBias",
        "styleTilts",
        "confirmationSignals",
        "invalidationTriggers",
        "counterEvidence",
        "dataGaps",
        "claimBoundaries",
        "notInvestmentAdvice",
    ):
        assert key in payload
    assert payload["version"] == MARKET_DECISION_SEMANTICS_VERSION
    assert payload["posture"] == "defensive"
    assert payload["notInvestmentAdvice"] is True


def test_service_module_has_no_provider_network_runtime_or_endpoint_imports() -> None:
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")

    forbidden_prefixes = (
        "api",
        "apps",
        "bot",
        "data_provider",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "yfinance",
        "src.services.market_overview_service",
        "src.services.liquidity_monitor_service",
        "src.services.market_rotation_radar_service",
        "src.services.data_fetcher_manager",
    )
    assert not [name for name in imports if name.startswith(forbidden_prefixes)]

    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "DataFetcherManager",
        "MarketOverviewService",
        "LiquidityMonitorService",
        "MarketRotationRadarService",
        "MarketCache",
        "FastAPI",
    ):
        assert forbidden not in source
