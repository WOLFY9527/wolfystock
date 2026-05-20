# -*- coding: utf-8 -*-
"""Regression coverage for Market Overview -> regime synthesis adapter."""

from __future__ import annotations

import ast
from pathlib import Path

from src.services.market_overview_service import MarketOverviewService
from src.services.market_regime_synthesis_adapter import (
    build_market_regime_evidence_items,
    synthesize_market_regime_from_temperature_inputs,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = REPO_ROOT / "src/services/market_regime_synthesis_adapter.py"


def _temperature_inputs(*, proxy_dxy: bool = True) -> dict:
    dxy_source_tier = "unofficial_proxy" if proxy_dxy else "official_public"
    dxy_trust_level = "usable_with_caution" if proxy_dxy else "high"
    dxy_freshness = "stale" if proxy_dxy else "live"
    dxy_source = "yfinance_proxy" if proxy_dxy else "fred"
    dxy_reason = "proxy_context_only" if proxy_dxy else None

    return {
        "indices": {
            "items": [
                {
                    "symbol": "HSI",
                    "label": "Hang Seng",
                    "value": 17820.0,
                    "changePercent": -1.2,
                    "source": "sina",
                    "sourceTier": "official_public",
                    "trustLevel": "high",
                    "freshness": "live",
                    "scoreContributionAllowed": True,
                    "asOf": "2026-05-20T10:00:00+08:00",
                    "updatedAt": "2026-05-20T10:00:00+08:00",
                }
            ]
        },
        "breadth": {
            "items": [
                {
                    "symbol": "ADV_RATIO",
                    "label": "Advance Ratio",
                    "value": 38.0,
                    "source": "tickflow",
                    "sourceTier": "official_public",
                    "trustLevel": "high",
                    "freshness": "live",
                    "scoreContributionAllowed": True,
                    "asOf": "2026-05-20T10:00:00+08:00",
                    "updatedAt": "2026-05-20T10:00:00+08:00",
                }
            ]
        },
        "rates": {
            "items": [
                {
                    "symbol": "US10Y",
                    "label": "US 10Y",
                    "value": 4.42,
                    "changePercent": 0.8,
                    "source": "treasury",
                    "sourceTier": "official_public",
                    "trustLevel": "high",
                    "freshness": "cached",
                    "scoreContributionAllowed": True,
                    "asOf": "2026-05-20T10:00:00+08:00",
                    "updatedAt": "2026-05-20T10:00:00+08:00",
                },
                {
                    "symbol": "VIX",
                    "label": "VIX",
                    "value": 21.3,
                    "changePercent": 5.2,
                    "source": "fred",
                    "sourceTier": "official_public",
                    "trustLevel": "high",
                    "freshness": "cached",
                    "scoreContributionAllowed": True,
                    "asOf": "2026-05-20T10:00:00+08:00",
                    "updatedAt": "2026-05-20T10:00:00+08:00",
                },
            ]
        },
        "fx": {
            "items": [
                {
                    "symbol": "DXY",
                    "label": "DXY",
                    "value": 105.4,
                    "changePercent": 0.6,
                    "source": dxy_source,
                    "sourceTier": dxy_source_tier,
                    "trustLevel": dxy_trust_level,
                    "freshness": dxy_freshness,
                    "scoreContributionAllowed": True,
                    "degradationReason": dxy_reason,
                    "asOf": "2026-05-20T10:00:00+08:00",
                    "updatedAt": "2026-05-20T10:00:00+08:00",
                }
            ]
        },
        "futures": {
            "items": [
                {
                    "symbol": "ES",
                    "label": "E-mini S&P",
                    "value": 5250.0,
                    "changePercent": -0.9,
                    "source": "cme",
                    "sourceTier": "exchange_public",
                    "trustLevel": "high",
                    "freshness": "live",
                    "scoreContributionAllowed": True,
                    "asOf": "2026-05-20T10:00:00+08:00",
                    "updatedAt": "2026-05-20T10:00:00+08:00",
                },
                {
                    "symbol": "NQ",
                    "label": "Nasdaq Futures",
                    "value": 18250.0,
                    "changePercent": -1.2,
                    "source": "cme",
                    "sourceTier": "exchange_public",
                    "trustLevel": "high",
                    "freshness": "live",
                    "scoreContributionAllowed": True,
                    "asOf": "2026-05-20T10:00:00+08:00",
                    "updatedAt": "2026-05-20T10:00:00+08:00",
                },
                {
                    "symbol": "RTY",
                    "label": "Russell Futures",
                    "value": 2060.0,
                    "changePercent": -1.5,
                    "source": "cme",
                    "sourceTier": "exchange_public",
                    "trustLevel": "high",
                    "freshness": "live",
                    "scoreContributionAllowed": True,
                    "asOf": "2026-05-20T10:00:00+08:00",
                    "updatedAt": "2026-05-20T10:00:00+08:00",
                },
            ]
        },
        "crypto": {
            "items": [
                {
                    "symbol": "BTC",
                    "label": "Bitcoin",
                    "value": 64000.0,
                    "changePercent": -3.1,
                    "source": "coinbase_public",
                    "sourceTier": "exchange_public",
                    "trustLevel": "high",
                    "freshness": "live",
                    "scoreContributionAllowed": False,
                    "degradationReason": "source_authority_router_rejected",
                    "asOf": "2026-05-20T10:00:00+08:00",
                    "updatedAt": "2026-05-20T10:00:00+08:00",
                },
                {
                    "symbol": "ETH",
                    "label": "Ethereum",
                    "value": 3150.0,
                    "changePercent": -2.6,
                    "source": "binance",
                    "sourceTier": "exchange_public",
                    "trustLevel": "high",
                    "freshness": "live",
                    "scoreContributionAllowed": True,
                    "asOf": "2026-05-20T10:00:00+08:00",
                    "updatedAt": "2026-05-20T10:00:00+08:00",
                },
            ]
        },
    }


def test_adapter_maps_temperature_inputs_into_regime_evidence_items() -> None:
    evidence = build_market_regime_evidence_items(_temperature_inputs(proxy_dxy=True))
    evidence_by_key = {item.key: item for item in evidence}

    assert set(evidence_by_key) == {
        "indices:HSI",
        "breadth:ADV_RATIO",
        "rates:US10Y",
        "rates:VIX",
        "fx:DXY",
        "futures:ES",
        "futures:NQ",
        "futures:RTY",
        "crypto:BTC",
        "crypto:ETH",
    }

    assert evidence_by_key["futures:ES"].pillar == "risk_appetite"
    assert evidence_by_key["futures:ES"].direction == "down"
    assert evidence_by_key["futures:ES"].change == -0.9

    assert evidence_by_key["breadth:ADV_RATIO"].pillar == "breadth_health"
    assert evidence_by_key["breadth:ADV_RATIO"].percentile == 38.0
    assert evidence_by_key["breadth:ADV_RATIO"].direction == "down"

    assert evidence_by_key["rates:VIX"].pillar == "volatility_stress"
    assert evidence_by_key["rates:US10Y"].pillar == "rates_pressure"
    assert evidence_by_key["fx:DXY"].pillar == "dollar_pressure"
    assert evidence_by_key["indices:HSI"].pillar == "china_risk_appetite"
    assert evidence_by_key["crypto:ETH"].pillar == "crypto_risk_beta"

    dxy_item = evidence_by_key["fx:DXY"]
    assert dxy_item.source_tier == "unofficial_proxy"
    assert dxy_item.trust_level == "usable_with_caution"
    assert dxy_item.freshness == "stale"
    assert dxy_item.degradation_reason == "proxy_context_only"

    btc_item = evidence_by_key["crypto:BTC"]
    assert btc_item.score_contribution_allowed is False
    assert btc_item.degradation_reason == "source_authority_router_rejected"


def test_adapter_synthesis_discounts_proxy_inputs_and_turns_rejected_inputs_into_gaps() -> None:
    official = synthesize_market_regime_from_temperature_inputs(_temperature_inputs(proxy_dxy=False))
    proxy = synthesize_market_regime_from_temperature_inputs(_temperature_inputs(proxy_dxy=True))

    assert official.primary_regime == proxy.primary_regime == "rates_shock_duration_pressure"
    assert proxy.confidence < official.confidence
    assert proxy.evidence_quality["discountedEvidenceCount"] > official.evidence_quality["discountedEvidenceCount"]
    assert any(gap["key"] == "crypto:BTC" for gap in proxy.data_gaps)
    assert proxy.rates_pressure > 0
    assert proxy.dollar_pressure > 0
    assert proxy.crypto_risk_beta < 0
    assert proxy.risk_appetite < 0
    assert proxy.breadth_health < 0
    assert proxy.china_risk_appetite < 0


def test_market_overview_service_helper_returns_payload_without_fetching_providers() -> None:
    payload = MarketOverviewService()._build_market_regime_synthesis_payload(_temperature_inputs(proxy_dxy=True))

    assert payload["primaryRegime"] == "rates_shock_duration_pressure"
    assert "topDrivers" in payload
    assert "counterEvidence" in payload
    assert "dataGaps" in payload
    assert "evidenceQuality" in payload


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
