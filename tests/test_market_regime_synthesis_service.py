# -*- coding: utf-8 -*-
"""Tests for the pure market regime synthesis algorithm foundation."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from src.services.market_regime_synthesis_service import (
    PILLARS,
    REGIME_CANDIDATES,
    MarketRegimeEvidenceItem,
    MarketRegimeSynthesisService,
    synthesize_market_regime,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = REPO_ROOT / "src/services/market_regime_synthesis_service.py"


def _evidence(
    key: str,
    pillar: str,
    direction: str,
    *,
    label: str | None = None,
    z_score: float = 1.4,
    source_tier: str = "official_public",
    trust_level: str = "high",
    freshness: str = "live",
    source: str = "unit_fixture",
    observation_only: bool = False,
    score_contribution_allowed: bool = True,
    degradation_reason: str | None = None,
) -> MarketRegimeEvidenceItem:
    return MarketRegimeEvidenceItem(
        key=key,
        label=label or key,
        pillar=pillar,
        z_score=z_score,
        direction=direction,
        source=source,
        source_tier=source_tier,
        trust_level=trust_level,
        freshness=freshness,
        observation_only=observation_only,
        score_contribution_allowed=score_contribution_allowed,
        as_of="2026-05-20T10:00:00+08:00",
        updated_at="2026-05-20T10:00:00+08:00",
        degradation_reason=degradation_reason,
    )


def _risk_on_inputs(**quality: Any) -> list[MarketRegimeEvidenceItem]:
    return [
        _evidence("btc", "crypto_risk_beta", "up", label="BTC", **quality),
        _evidence("eth", "crypto_risk_beta", "up", label="ETH", **quality),
        _evidence("vix", "volatility_stress", "down", label="VIX", **quality),
        _evidence("dxy", "dollar_pressure", "down", label="DXY", **quality),
    ]


def test_rates_up_crypto_down_dxy_up_classifies_rates_dollar_pressure() -> None:
    result = synthesize_market_regime(
        [
            _evidence("us10y", "rates_pressure", "up", label="US 10Y yield"),
            _evidence("dxy", "dollar_pressure", "up", label="DXY"),
            _evidence("btc", "crypto_risk_beta", "down", label="BTC"),
        ]
    )

    assert result.primary_regime == "rates_shock_duration_pressure"
    assert result.secondary_regimes[0] == "dollar_squeeze"
    assert result.rates_pressure > 0
    assert result.dollar_pressure > 0
    assert result.crypto_risk_beta < 0
    assert result.regime_scores["rates_shock_duration_pressure"] > result.regime_scores["dollar_squeeze"]
    assert any(driver["key"] == "us10y" for driver in result.top_drivers)


def test_crypto_up_vix_down_dxy_down_classifies_risk_on_liquidity_beta() -> None:
    result = MarketRegimeSynthesisService().synthesize(_risk_on_inputs())

    assert result.primary_regime == "risk_on_liquidity_expansion"
    assert result.crypto_risk_beta > 0
    assert result.volatility_stress < 0
    assert result.dollar_pressure < 0
    assert result.confidence_label in {"medium", "high"}


def test_spx_up_breadth_weak_small_caps_weak_classifies_nacho_rotation() -> None:
    result = synthesize_market_regime(
        [
            _evidence("spx", "risk_appetite", "up", label="S&P 500"),
            _evidence("advance_decline", "breadth_health", "down", label="Advance decline breadth"),
            _evidence("iwm_spy", "rotation_leadership", "down", label="IWM/SPY relative strength"),
        ]
    )

    assert result.primary_regime == "nacho_mega_cap_defensive_rotation"
    assert result.risk_appetite > 0
    assert result.breadth_health < 0
    assert result.rotation_quality < 0
    narrative = " ".join(result.narrative_bullets).lower()
    assert "fund flow" not in narrative
    assert "breadth" in narrative


def test_china_up_while_us_risk_weak_classifies_china_policy_divergence() -> None:
    result = synthesize_market_regime(
        [
            _evidence("csi300", "china_risk_appetite", "up", label="CSI 300"),
            _evidence("spx", "risk_appetite", "down", label="S&P 500"),
            _evidence("vix", "volatility_stress", "up", label="VIX"),
        ]
    )

    assert result.primary_regime == "china_policy_divergence"
    assert result.china_risk_appetite > 0
    assert result.risk_appetite < 0
    assert result.volatility_stress > 0


def test_low_coverage_returns_data_insufficient_with_explicit_gaps() -> None:
    result = synthesize_market_regime([_evidence("btc", "crypto_risk_beta", "up", label="BTC")])

    assert result.primary_regime == "data_insufficient"
    assert result.confidence_label == "insufficient"
    assert result.evidence_quality["scoringPillarCount"] == 1
    assert result.data_gaps
    assert any(gap["reason"] == "missing_scoring_evidence" for gap in result.data_gaps)


def test_stale_proxy_data_lowers_confidence_without_changing_deterministic_shape() -> None:
    fresh = synthesize_market_regime(_risk_on_inputs())
    stale_proxy = synthesize_market_regime(
        _risk_on_inputs(
            source_tier="unofficial_proxy",
            trust_level="usable_with_caution",
            freshness="stale",
            source="proxy_fixture",
        )
    )

    assert fresh.primary_regime == "risk_on_liquidity_expansion"
    assert stale_proxy.primary_regime == "risk_on_liquidity_expansion"
    assert stale_proxy.confidence < fresh.confidence
    assert stale_proxy.evidence_quality["discountedEvidenceCount"] > fresh.evidence_quality["discountedEvidenceCount"]
    assert all(driver["weight"] < 0.3 for driver in stale_proxy.top_drivers)


def test_observation_only_score_blocked_evidence_cannot_dominate_conclusion() -> None:
    result = synthesize_market_regime(
        [
            _evidence(
                "btc_obs",
                "crypto_risk_beta",
                "up",
                label="BTC observation",
                source_tier="exchange_public",
                observation_only=True,
                score_contribution_allowed=False,
            ),
            _evidence(
                "vix_obs",
                "volatility_stress",
                "down",
                label="VIX observation",
                observation_only=True,
                score_contribution_allowed=False,
            ),
            _evidence(
                "dxy_obs",
                "dollar_pressure",
                "down",
                label="DXY observation",
                observation_only=True,
                score_contribution_allowed=False,
            ),
        ]
    )

    assert result.primary_regime == "data_insufficient"
    assert result.evidence_quality["observationOnlyEvidenceCount"] == 3
    assert result.evidence_quality["scoreBlockedEvidenceCount"] == 3
    assert not result.top_drivers
    assert all(gap["reason"] == "score_contribution_not_allowed" for gap in result.data_gaps[:3])


def test_unavailable_or_rejected_authority_is_data_gap_not_strong_evidence() -> None:
    result = synthesize_market_regime(
        [
            _evidence(
                "dxy_rejected",
                "dollar_pressure",
                "up",
                label="DXY rejected",
                freshness="unavailable",
                degradation_reason="source_authority_router_rejected",
            ),
            _evidence("us10y", "rates_pressure", "up", label="US 10Y yield"),
            _evidence("btc", "crypto_risk_beta", "down", label="BTC"),
        ]
    )

    assert result.primary_regime == "data_insufficient"
    assert any(gap["key"] == "dxy_rejected" for gap in result.data_gaps)
    assert all(driver["key"] != "dxy_rejected" for driver in result.top_drivers)


def test_conflicting_signal_produces_counter_evidence_and_lower_confidence() -> None:
    clean = synthesize_market_regime(
        [
            _evidence("us10y", "rates_pressure", "up"),
            _evidence("spx", "risk_appetite", "down"),
            _evidence("vix", "volatility_stress", "up"),
        ]
    )
    conflicted = synthesize_market_regime(
        [
            _evidence("us10y", "rates_pressure", "up"),
            _evidence("spx", "risk_appetite", "up"),
            _evidence("vix", "volatility_stress", "up"),
            _evidence("btc", "crypto_risk_beta", "up"),
        ]
    )

    assert clean.primary_regime == "rates_shock_duration_pressure"
    assert conflicted.primary_regime == "term_premium_or_inflation_scare"
    assert conflicted.counter_evidence
    assert conflicted.confidence < clean.confidence


def test_output_dto_contains_required_fields_and_camel_case_projection() -> None:
    result = synthesize_market_regime(_risk_on_inputs())
    payload = result.to_dict()

    for key in (
        "primaryRegime",
        "secondaryRegimes",
        "regimeScores",
        "confidence",
        "confidenceLabel",
        "liquidityImpulse",
        "riskAppetite",
        "ratesPressure",
        "dollarPressure",
        "volatilityStress",
        "cryptoRiskBeta",
        "breadthHealth",
        "chinaRiskAppetite",
        "rotationQuality",
        "topDrivers",
        "counterEvidence",
        "dataGaps",
        "narrativeBullets",
        "evidenceQuality",
        "notInvestmentAdvice",
    ):
        assert key in payload
    assert set(payload["regimeScores"]) == set(REGIME_CANDIDATES)
    assert payload["notInvestmentAdvice"] is True
    assert payload["topDrivers"]
    assert isinstance(payload["counterEvidence"], list)
    assert payload["dataGaps"]
    assert payload["narrativeBullets"]
    assert set(PILLARS).issuperset(payload["evidenceQuality"]["coveredPillars"])


def test_input_dto_accepts_camel_case_mapping_without_provider_calls() -> None:
    result = synthesize_market_regime(
        [
            {
                "key": "btc",
                "label": "BTC",
                "pillar": "crypto_risk_beta",
                "zScore": 1.2,
                "direction": "up",
                "source": "exchange_fixture",
                "sourceTier": "exchange_public",
                "trustLevel": "high",
                "freshness": "live",
                "observationOnly": False,
                "scoreContributionAllowed": True,
                "asOf": "2026-05-20T10:00:00+08:00",
                "updatedAt": "2026-05-20T10:00:00+08:00",
            },
            {
                "key": "vix",
                "label": "VIX",
                "pillar": "volatility_stress",
                "zScore": 1.2,
                "direction": "down",
                "sourceTier": "official_public",
                "trustLevel": "high",
                "freshness": "live",
            },
            {
                "key": "dxy",
                "label": "DXY",
                "pillar": "dollar_pressure",
                "zScore": 1.2,
                "direction": "down",
                "sourceTier": "official_public",
                "trustLevel": "high",
                "freshness": "live",
            },
        ]
    )

    assert result.primary_regime == "risk_on_liquidity_expansion"


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
