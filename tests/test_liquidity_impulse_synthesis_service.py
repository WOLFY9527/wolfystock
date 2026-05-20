# -*- coding: utf-8 -*-
"""Tests for the pure liquidity impulse synthesis algorithm foundation."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from src.services.liquidity_impulse_synthesis_service import (
    LIQUIDITY_IMPULSE_CLASSIFICATIONS,
    PILLARS,
    LiquidityImpulseEvidenceItem,
    LiquidityImpulseSynthesisService,
    synthesize_liquidity_impulse,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = REPO_ROOT / "src/services/liquidity_impulse_synthesis_service.py"


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
    included_in_score: bool | None = True,
    proxy_only: bool = False,
    degradation_reason: str | None = None,
) -> LiquidityImpulseEvidenceItem:
    return LiquidityImpulseEvidenceItem(
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
        included_in_score=included_in_score,
        proxy_only=proxy_only,
        as_of="2026-05-20T10:00:00+08:00",
        updated_at="2026-05-20T10:00:00+08:00",
        degradation_reason=degradation_reason,
    )


def _crypto_expansion_inputs(**quality: Any) -> list[LiquidityImpulseEvidenceItem]:
    return [
        _evidence("btc", "crypto_liquidity_beta", "up", label="BTC", **quality),
        _evidence("eth", "crypto_liquidity_beta", "up", label="ETH", **quality),
        _evidence("dxy", "dollar_pressure", "down", label="DXY", **quality),
        _evidence("vix", "volatility_stress", "down", label="VIX", **quality),
    ]


def test_rates_up_dxy_up_btc_down_classifies_rates_driven_tightening() -> None:
    result = synthesize_liquidity_impulse(
        [
            _evidence("us10y", "rates_pressure", "up", label="US 10Y yield"),
            _evidence("dxy", "dollar_pressure", "up", label="DXY"),
            _evidence("btc", "crypto_liquidity_beta", "down", label="BTC"),
            _evidence("spy_flow", "equity_flow_proxy", "down", label="SPY flow proxy"),
        ]
    )

    assert result.liquidity_impulse == "contracting_liquidity"
    assert result.subtype == "rates_driven_tightening"
    assert result.direction_score < 0
    assert result.pillar_scores["rates_pressure"] > 0
    assert result.pillar_scores["dollar_pressure"] > 0
    assert result.pillar_scores["crypto_liquidity_beta"] < 0
    assert any(driver["key"] == "us10y" for driver in result.dominant_drivers)


def test_vix_up_crypto_and_equities_down_classifies_risk_deleveraging() -> None:
    result = LiquidityImpulseSynthesisService().synthesize(
        [
            _evidence("vix", "volatility_stress", "up", label="VIX"),
            _evidence("btc", "crypto_liquidity_beta", "down", label="BTC"),
            _evidence("spx", "risk_asset_demand", "down", label="S&P 500"),
            _evidence("breadth", "breadth_confirmation", "down", label="Breadth"),
        ]
    )

    assert result.liquidity_impulse == "contracting_liquidity"
    assert result.subtype == "risk_deleveraging"
    assert result.pillar_scores["volatility_stress"] > 0
    assert result.pillar_scores["risk_asset_demand"] < 0
    assert result.counter_evidence == ()


def test_crypto_up_dxy_down_vix_down_classifies_crypto_beta_expansion() -> None:
    result = synthesize_liquidity_impulse(_crypto_expansion_inputs())

    assert result.liquidity_impulse == "expanding_liquidity"
    assert result.subtype == "crypto_beta_expansion"
    assert result.direction_score > 0
    assert result.pillar_scores["crypto_liquidity_beta"] > 0
    assert result.pillar_scores["dollar_pressure"] < 0
    assert result.pillar_scores["volatility_stress"] < 0
    assert result.confidence_label in {"medium", "high"}


def test_low_coverage_returns_data_insufficient_with_explicit_gaps() -> None:
    result = synthesize_liquidity_impulse([_evidence("btc", "crypto_liquidity_beta", "up", label="BTC")])

    assert result.liquidity_impulse == "data_insufficient"
    assert result.subtype == "data_insufficient"
    assert result.confidence_label == "insufficient"
    assert result.evidence_quality["scoringPillarCount"] == 1
    assert result.data_gaps
    assert any(gap["reason"] == "missing_scoring_evidence" for gap in result.data_gaps)


def test_stale_proxy_and_observation_only_inputs_lower_confidence() -> None:
    fresh = synthesize_liquidity_impulse(
        [
            _evidence("btc", "crypto_liquidity_beta", "up", label="BTC", source_tier="exchange_public"),
            _evidence(
                "eth_obs",
                "crypto_liquidity_beta",
                "up",
                label="ETH observation",
                source_tier="unofficial_proxy",
                trust_level="usable_with_caution",
                freshness="stale",
                observation_only=True,
                proxy_only=True,
                source="proxy_fixture",
            ),
            _evidence(
                "dxy_obs",
                "dollar_pressure",
                "down",
                label="DXY observation",
                source_tier="unofficial_proxy",
                trust_level="usable_with_caution",
                freshness="stale",
                observation_only=True,
                proxy_only=True,
                source="proxy_fixture",
            ),
            _evidence(
                "vix_obs",
                "volatility_stress",
                "down",
                label="VIX observation",
                source_tier="unofficial_proxy",
                trust_level="usable_with_caution",
                freshness="stale",
                observation_only=True,
                proxy_only=True,
                source="proxy_fixture",
            ),
        ]
    )
    cleaner = synthesize_liquidity_impulse(
        [
            _evidence("btc", "crypto_liquidity_beta", "up", label="BTC", source_tier="exchange_public"),
            _evidence("eth", "crypto_liquidity_beta", "up", label="ETH", source_tier="exchange_public"),
            _evidence("dxy", "dollar_pressure", "down", label="DXY"),
            _evidence("vix", "volatility_stress", "down", label="VIX"),
        ]
    )

    assert cleaner.liquidity_impulse == "expanding_liquidity"
    assert fresh.liquidity_impulse == "expanding_liquidity"
    assert fresh.confidence < cleaner.confidence
    assert fresh.evidence_quality["discountedEvidenceCount"] > cleaner.evidence_quality["discountedEvidenceCount"]
    assert fresh.evidence_quality["proxyOnlyScoringCount"] > 0


def test_proxy_only_scoring_evidence_cannot_claim_true_expansion_or_contraction() -> None:
    result = synthesize_liquidity_impulse(
        _crypto_expansion_inputs(
            source_tier="unofficial_proxy",
            trust_level="usable_with_caution",
            freshness="delayed",
            proxy_only=True,
            source="proxy_fixture",
        )
    )

    assert result.liquidity_impulse == "data_insufficient"
    assert result.subtype == "data_insufficient"
    assert result.evidence_quality["realScoringEvidenceCount"] == 0
    assert result.evidence_quality["allScoringEvidenceProxyOnly"] is True


def test_non_score_eligible_evidence_cannot_dominate_conclusion() -> None:
    result = synthesize_liquidity_impulse(
        [
            _evidence("us10y", "rates_pressure", "up", label="US 10Y yield"),
            _evidence("dxy", "dollar_pressure", "up", label="DXY"),
            _evidence("btc", "crypto_liquidity_beta", "down", label="BTC"),
            _evidence(
                "eth_blocked",
                "crypto_liquidity_beta",
                "up",
                label="ETH blocked",
                source_tier="exchange_public",
                score_contribution_allowed=False,
                included_in_score=False,
            ),
            _evidence(
                "vix_blocked",
                "volatility_stress",
                "down",
                label="VIX blocked",
                score_contribution_allowed=False,
                included_in_score=False,
            ),
        ]
    )

    assert result.liquidity_impulse == "contracting_liquidity"
    assert result.subtype == "rates_driven_tightening"
    assert result.evidence_quality["scoreBlockedEvidenceCount"] == 2
    assert all(driver["key"] not in {"eth_blocked", "vix_blocked"} for driver in result.dominant_drivers)
    assert any(gap["reason"] == "score_contribution_not_allowed" for gap in result.data_gaps)


def test_unavailable_china_context_becomes_data_gap_not_fake_confidence() -> None:
    result = synthesize_liquidity_impulse(
        [
            _evidence("us10y", "rates_pressure", "up", label="US 10Y yield"),
            _evidence("dxy", "dollar_pressure", "up", label="DXY"),
            _evidence("btc", "crypto_liquidity_beta", "down", label="BTC"),
            _evidence(
                "dr007",
                "china_liquidity_context",
                "up",
                label="DR007",
                freshness="unavailable",
                trust_level="unavailable",
                degradation_reason="provider_unavailable",
            ),
        ]
    )

    assert result.liquidity_impulse == "contracting_liquidity"
    assert any(gap["key"] == "dr007" for gap in result.data_gaps)
    assert result.evidence_quality["dataGapCount"] >= 1


def test_conflicting_signals_produce_counter_evidence_and_mixed_transition() -> None:
    result = synthesize_liquidity_impulse(
        [
            _evidence("btc", "crypto_liquidity_beta", "up", label="BTC"),
            _evidence("dxy", "dollar_pressure", "up", label="DXY"),
            _evidence("vix", "volatility_stress", "up", label="VIX"),
            _evidence("spx", "risk_asset_demand", "up", label="S&P 500"),
        ]
    )

    assert result.liquidity_impulse == "mixed_or_transition"
    assert result.counter_evidence
    assert result.confidence_label in {"insufficient", "low", "medium"}


def test_output_dto_contains_required_fields_and_camel_case_projection() -> None:
    result = synthesize_liquidity_impulse(_crypto_expansion_inputs())
    payload = result.to_dict()

    for key in (
        "liquidityImpulse",
        "impulseLabel",
        "subtype",
        "confidence",
        "confidenceLabel",
        "pillarScores",
        "directionScore",
        "dominantDrivers",
        "counterEvidence",
        "dataGaps",
        "narrativeBullets",
        "evidenceQuality",
        "notInvestmentAdvice",
    ):
        assert key in payload
    assert payload["notInvestmentAdvice"] is True
    assert payload["dominantDrivers"]
    assert isinstance(payload["counterEvidence"], list)
    assert payload["dataGaps"]
    assert payload["narrativeBullets"]
    assert set(payload["pillarScores"]) == set(PILLARS)
    assert result.liquidity_impulse in LIQUIDITY_IMPULSE_CLASSIFICATIONS


def test_input_dto_accepts_camel_case_mapping_without_provider_calls() -> None:
    result = synthesize_liquidity_impulse(
        [
            {
                "key": "btc",
                "label": "BTC",
                "pillar": "crypto_liquidity_beta",
                "zScore": 1.2,
                "direction": "up",
                "source": "exchange_fixture",
                "sourceTier": "exchange_public",
                "trustLevel": "high",
                "freshness": "live",
                "observationOnly": False,
                "scoreContributionAllowed": True,
                "includedInScore": True,
                "proxyOnly": False,
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
                "includedInScore": True,
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
                "includedInScore": True,
            },
        ]
    )

    assert result.liquidity_impulse == "expanding_liquidity"
    assert result.subtype == "crypto_beta_expansion"


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
