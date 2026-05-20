# -*- coding: utf-8 -*-
"""Regression coverage for Liquidity Monitor -> liquidity impulse adapter."""

from __future__ import annotations

import ast
from pathlib import Path

from src.services.liquidity_impulse_synthesis_adapter import (
    build_liquidity_impulse_evidence_items,
    build_liquidity_impulse_synthesis_payload,
    synthesize_liquidity_impulse_from_monitor_indicators,
)
from src.services.liquidity_monitor_service import LiquidityMonitorService


REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = REPO_ROOT / "src/services/liquidity_impulse_synthesis_adapter.py"


def _indicator(
    key: str,
    summary: str,
    *,
    score_contribution: int = 0,
    included_in_score: bool = True,
    source: str = "fixture_source",
    source_tier: str = "official_public",
    trust_level: str = "reliable",
    freshness: str = "live",
    observation_only: bool = False,
    score_contribution_allowed: bool = True,
    proxy_only: bool = False,
    degradation_reason: str | None = None,
    updated_at: str = "2026-05-20T10:00:00+08:00",
) -> dict:
    return {
        "key": key,
        "label": key.replace("_", " ").title(),
        "status": "partial" if freshness in {"delayed", "stale"} else "live",
        "freshness": freshness,
        "includedInScore": included_in_score,
        "scoreContribution": score_contribution,
        "scoreWeight": 6,
        "summary": summary,
        "updatedAt": updated_at,
        "evidence": {
            "source": source,
            "sourceLabel": "Fixture Source",
            "asOf": updated_at,
            "freshness": freshness,
            "isFallback": freshness == "fallback",
            "isStale": freshness == "stale",
            "isPartial": freshness in {"delayed", "stale", "partial"},
            "isUnavailable": freshness == "unavailable",
            "coverage": 1.0 if freshness != "unavailable" else 0.0,
            "confidenceWeight": 1.0,
            "degradationReason": degradation_reason,
            "inputs": [],
        },
        "coverageDiagnostics": {
            "sourceTier": source_tier,
            "trustLevel": trust_level,
            "freshness": freshness,
            "observationOnly": observation_only,
            "scoreContributionAllowed": score_contribution_allowed,
            "proxyOnly": proxy_only,
            "degradationReason": degradation_reason,
        },
    }


def _contracting_indicator_set(*, proxy_usd: bool) -> list[dict]:
    usd_allowed = not proxy_usd
    usd_included = not proxy_usd
    usd_tier = "official_public" if not proxy_usd else "unofficial_proxy"
    usd_trust = "reliable" if not proxy_usd else "usable_with_caution"
    usd_freshness = "live" if not proxy_usd else "delayed"
    usd_reason = None if not proxy_usd else "proxy_only_missing_real_source"
    return [
        _indicator("us_rates_pressure", "US10Y +0.42% | US30Y +0.30%", score_contribution=6),
        _indicator(
            "usd_pressure",
            "DXY +0.35% | USD/CNH +0.20%",
            score_contribution=-6 if usd_allowed else 0,
            included_in_score=usd_included,
            source="fred" if not proxy_usd else "yfinance_proxy",
            source_tier=usd_tier,
            trust_level=usd_trust,
            freshness=usd_freshness,
            score_contribution_allowed=usd_allowed,
            proxy_only=proxy_usd,
            degradation_reason=usd_reason,
        ),
        _indicator("crypto_spot_momentum", "1/3 上涨 | 均值 -2.40%", score_contribution=-6, source="binance", source_tier="exchange_public"),
        _indicator(
            "crypto_funding",
            "BTC +0.0180% | ETH +0.0150% | 均值 +0.0165%",
            included_in_score=False,
            source="binance",
            source_tier="exchange_public",
            observation_only=True,
            score_contribution_allowed=False,
            degradation_reason="observation_only",
        ),
        _indicator(
            "futures_premarket",
            "均值 -0.90%",
            included_in_score=False,
            source="cme",
            source_tier="exchange_public",
            observation_only=True,
            score_contribution_allowed=False,
            degradation_reason="observation_only",
        ),
    ]


def test_adapter_maps_liquidity_monitor_indicators_into_impulse_evidence_items() -> None:
    evidence = build_liquidity_impulse_evidence_items(
        [
            _indicator("usd_pressure", "DXY +0.35% | USD/CNH +0.20%", score_contribution=0, included_in_score=False, source="yfinance_proxy", source_tier="unofficial_proxy", trust_level="usable_with_caution", freshness="delayed", score_contribution_allowed=False, proxy_only=True, degradation_reason="proxy_only_missing_real_source"),
            _indicator("us_rates_pressure", "US10Y +0.42% | US30Y +0.30%", score_contribution=6),
            _indicator("crypto_spot_momentum", "2/3 上涨 | 均值 +1.40%", score_contribution=6, source="binance", source_tier="exchange_public"),
            _indicator("us_breadth_proxy", "8/3 | RSP/SPY +1.20% | IWM/SPY +0.80%", score_contribution=0, included_in_score=False, source="yfinance_proxy", source_tier="unofficial_proxy", trust_level="usable_with_caution", freshness="delayed", score_contribution_allowed=False, proxy_only=True, degradation_reason="proxy_only_missing_real_source"),
            _indicator("cn_money_market_rates", "均值 +0.18%", included_in_score=False, observation_only=True, score_contribution_allowed=False, degradation_reason="observation_only"),
        ]
    )
    evidence_by_key = {item.key: item for item in evidence}

    assert set(evidence_by_key) == {
        "liquidity_monitor:usd_pressure",
        "liquidity_monitor:us_rates_pressure",
        "liquidity_monitor:crypto_spot_momentum",
        "liquidity_monitor:us_breadth_proxy",
        "liquidity_monitor:cn_money_market_rates",
    }

    assert evidence_by_key["liquidity_monitor:usd_pressure"].pillar == "dollar_pressure"
    assert evidence_by_key["liquidity_monitor:usd_pressure"].direction == "up"
    assert evidence_by_key["liquidity_monitor:usd_pressure"].source == "yfinance_proxy"
    assert evidence_by_key["liquidity_monitor:usd_pressure"].source_tier == "unofficial_proxy"
    assert evidence_by_key["liquidity_monitor:usd_pressure"].trust_level == "usable_with_caution"
    assert evidence_by_key["liquidity_monitor:usd_pressure"].freshness == "delayed"
    assert evidence_by_key["liquidity_monitor:usd_pressure"].score_contribution_allowed is False
    assert evidence_by_key["liquidity_monitor:usd_pressure"].included_in_score is False
    assert evidence_by_key["liquidity_monitor:usd_pressure"].proxy_only is True
    assert evidence_by_key["liquidity_monitor:usd_pressure"].degradation_reason == "proxy_only_missing_real_source"

    assert evidence_by_key["liquidity_monitor:us_rates_pressure"].pillar == "rates_pressure"
    assert evidence_by_key["liquidity_monitor:us_rates_pressure"].direction == "up"
    assert evidence_by_key["liquidity_monitor:crypto_spot_momentum"].pillar == "crypto_liquidity_beta"
    assert evidence_by_key["liquidity_monitor:crypto_spot_momentum"].direction == "up"
    assert evidence_by_key["liquidity_monitor:us_breadth_proxy"].pillar == "breadth_confirmation"
    assert evidence_by_key["liquidity_monitor:us_breadth_proxy"].direction == "up"
    assert evidence_by_key["liquidity_monitor:cn_money_market_rates"].pillar == "china_liquidity_context"
    assert evidence_by_key["liquidity_monitor:cn_money_market_rates"].direction == "down"


def test_adapter_synthesis_discounts_proxy_and_preserves_non_scoring_gaps() -> None:
    official = synthesize_liquidity_impulse_from_monitor_indicators(_contracting_indicator_set(proxy_usd=False))
    proxy = synthesize_liquidity_impulse_from_monitor_indicators(_contracting_indicator_set(proxy_usd=True))

    assert official.liquidity_impulse == "contracting_liquidity"
    assert proxy.liquidity_impulse == "data_insufficient"
    assert proxy.confidence < official.confidence
    assert proxy.evidence_quality["scoreBlockedEvidenceCount"] > official.evidence_quality["scoreBlockedEvidenceCount"]
    assert any(gap["key"] == "liquidity_monitor:usd_pressure" for gap in proxy.data_gaps)
    assert any(gap["key"] == "liquidity_monitor:crypto_funding" for gap in proxy.data_gaps)
    assert any(gap["key"] == "liquidity_monitor:futures_premarket" for gap in proxy.data_gaps)


def test_liquidity_monitor_service_helper_returns_additive_synthesis_payload() -> None:
    payload = LiquidityMonitorService()._build_liquidity_impulse_synthesis_payload(_contracting_indicator_set(proxy_usd=True))

    assert payload["liquidityImpulse"] == "data_insufficient"
    assert payload["subtype"] == "data_insufficient"
    assert "dominantDrivers" in payload
    assert "counterEvidence" in payload
    assert "dataGaps" in payload
    assert "evidenceQuality" in payload
    assert payload["notInvestmentAdvice"] is True


def test_adapter_build_payload_projects_camel_case_result() -> None:
    payload = build_liquidity_impulse_synthesis_payload(_contracting_indicator_set(proxy_usd=True))

    assert payload["liquidityImpulse"] == "data_insufficient"
    assert "directionScore" in payload
    assert "pillarScores" in payload


def test_adapter_module_has_no_provider_network_or_endpoint_imports() -> None:
    tree = ast.parse(ADAPTER_PATH.read_text(encoding="utf-8"))
    imports: list[str] = []
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
    )
    assert not [name for name in imports if name.startswith(forbidden_prefixes)]
