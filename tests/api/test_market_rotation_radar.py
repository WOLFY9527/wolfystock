# -*- coding: utf-8 -*-
"""API contract tests for the market rotation radar endpoint."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from api.v1.endpoints import market
from src.services import market_rotation_radar_service as radar_service_module
from src.services import rotation_radar_quote_provider
from src.services.market_overview_service import MarketOverviewService


@pytest.fixture(autouse=True)
def _clear_rotation_radar_shared_state():
    MarketOverviewService._market_cache.clear()
    MarketOverviewService._market_data_cache.clear()
    clear_shared_cache = getattr(
        radar_service_module,
        "_clear_shared_rotation_radar_snapshot_cache",
        None,
    )
    if clear_shared_cache:
        clear_shared_cache()
    yield
    MarketOverviewService._market_cache.clear()
    MarketOverviewService._market_data_cache.clear()
    if clear_shared_cache:
        clear_shared_cache()


def _client(monkeypatch: pytest.MonkeyPatch, provider_factory=None) -> TestClient:
    monkeypatch.setattr(
        market,
        "get_rotation_radar_quote_provider",
        provider_factory or (lambda: None),
    )
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    return TestClient(app)


def _shared_cache_quote(symbol: str, index: int, *, freshness: str = "delayed") -> dict:
    change = round(0.4 + (index % 7) * 0.17, 3)
    as_of = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "symbol": symbol,
        "name": symbol,
        "price": 100.0 + index,
        "changePercent": change,
        "volume": 1_000_000 + index,
        "averageVolume": 900_000,
        "volumeRatio": 1.25,
        "vwap": 99.0 + index,
        "freshness": freshness,
        "isStale": freshness == "stale",
        "isFallback": False,
        "source": "unit_fixture",
        "sourceLabel": "Unit Fixture",
        "sourceType": "unofficial_public_api",
        "asOf": as_of,
        "timeWindows": {
            "1d": {
                "changePercent": change,
                "relativeVolume": 1.25,
                "freshness": freshness,
                "asOf": as_of,
            }
        },
    }


def _headline_quote(
    symbol: str,
    index: int,
    *,
    change: float | None = None,
    volume_ratio: float = 1.35,
    freshness: str = "cached",
) -> dict:
    quote = _shared_cache_quote(symbol, index, freshness=freshness)
    if change is not None:
        quote["changePercent"] = change
        quote["volumeRatio"] = volume_ratio
        quote["volume"] = 1_000_000 * volume_ratio
        quote["timeWindows"]["1d"]["changePercent"] = change
        quote["timeWindows"]["1d"]["relativeVolume"] = volume_ratio
    quote["source"] = "cache"
    quote["sourceLabel"] = "Cache Snapshot"
    quote["sourceType"] = "cache_snapshot"
    quote["sourceTier"] = "snapshot"
    return quote


def _etf_authority_time_windows(
    changes: dict[str, float],
    *,
    as_of: str = "2026-05-07T09:45:00+00:00",
    freshness: str = "live",
) -> dict[str, dict[str, object]]:
    return {
        window: {
            "changePercent": change,
            "relativeVolume": 1.2,
            "freshness": freshness,
            "asOf": as_of,
            "available": True,
            "source": "alpaca",
            "sourceLabel": "Alpaca SIP",
            "sourceTier": "broker_authorized",
            "providerTier": "tier_1_configured",
        }
        for window, change in changes.items()
    }


def _bounded_etf_authority_fixture() -> tuple[tuple[str, ...], dict[str, dict], dict[str, object]]:
    stable_etfs = ("SPY", "QQQ", "IWM", "SMH", "SOXX", "IGV")
    window_changes = {
        "SPY": {"5m": 0.2, "15m": 0.4, "60m": 0.6, "1d": 0.9},
        "QQQ": {"5m": 0.5, "15m": 0.7, "60m": 1.1, "1d": 1.6},
        "IWM": {"5m": -0.2, "15m": 0.1, "60m": 0.3, "1d": 0.4},
        "SMH": {"5m": 0.8, "15m": 1.2, "60m": 1.8, "1d": 2.4},
        "SOXX": {"5m": 0.7, "15m": 1.0, "60m": 1.5, "1d": 2.1},
        "IGV": {"5m": 0.1, "15m": 0.3, "60m": 0.6, "1d": 0.8},
    }
    quotes: dict[str, dict] = {}
    for symbol in stable_etfs:
        quote = _shared_cache_quote(symbol, len(quotes), freshness="live")
        quote["changePercent"] = window_changes[symbol]["1d"]
        quote["timeWindows"] = _etf_authority_time_windows(window_changes[symbol])
        quote["source"] = "alpaca"
        quote["sourceLabel"] = "Alpaca SIP"
        quote["sourceType"] = "official_public"
        quote["sourceTier"] = "broker_authorized"
        quote["providerTier"] = "tier_1_configured"
        quote["freshness"] = "live"
        quote["isStale"] = False
        quote["isFallback"] = False
        quote["confidenceWeight"] = 0.9
        quotes[symbol] = quote
    spine = {
        "universe": list(stable_etfs),
        "requiredWindows": ["5m", "15m", "60m", "1d"],
        "fulfilledWindows": ["5m", "15m", "60m", "1d"],
        "missingWindows": [],
        "staleWindows": [],
        "freshness": "live",
        "asOf": "2026-05-07T09:45:00+00:00",
        "sourceLabel": "Alpaca SIP",
        "sourceTier": "broker_authorized",
        "trustLevel": "active",
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": True,
        "reasonCodes": [],
        "quotes": [
            {
                "symbol": symbol,
                "windowsFulfilled": ["5m", "15m", "60m", "1d"],
                "freshness": "live",
                "asOf": "2026-05-07T09:45:00+00:00",
                "sourceLabel": "Alpaca SIP",
                "sourceTier": "broker_authorized",
                "trustLevel": "active",
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
                "reasonCodes": [],
            }
            for symbol in stable_etfs
        ],
    }
    return stable_etfs, quotes, spine


def _assert_consumer_snapshot_excludes_admin_fields(snapshot: dict) -> None:
    dumped = json.dumps(snapshot, ensure_ascii=False)
    for marker in (
        "credentialFieldsMissing",
        "ALPACA_API_KEY",
        "requestWindowResults",
        "symbolFailureSamples",
        "rawFailureSamples",
        "providerPayload",
        "rawProviderPayload",
        "perWindowTimeout",
        "totalProviderBudget",
        "providerDeadlineSeconds",
        "sourceAuthorityRouter",
        "activationHint",
        "recommendedAction",
        "proxyEnvironment",
        "adminDiagnostics",
        "signals",
        "scoreBreakdown",
        "weightBreakdown",
        "rankingTrust",
        "etfAuthoritySpine",
    ):
        assert marker not in dumped


def _install_counting_default_provider(
    monkeypatch: pytest.MonkeyPatch,
    *,
    freshness: str = "delayed",
) -> list[tuple[str, ...]]:
    provider_calls: list[tuple[str, ...]] = []

    def provider(symbols):
        requested = tuple(symbols)
        provider_calls.append(requested)
        return {
            "quotes": {
                symbol: _shared_cache_quote(symbol, index, freshness=freshness)
                for index, symbol in enumerate(requested)
            },
            "metadata": {
                "quoteMode": "proxy",
                "sourceType": "unofficial_public_api",
                "freshness": freshness,
                "asOf": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "noExternalCalls": False,
            },
        }

    monkeypatch.setattr(
        rotation_radar_quote_provider,
        "load_rotation_radar_quotes",
        provider,
    )
    return provider_calls


def test_market_rotation_radar_route_is_exposed(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    routes = {
        (method, route.path)
        for route in app.routes
        if hasattr(route, "methods")
        for method in (route.methods or set())
        if method not in {"HEAD", "OPTIONS"}
    }

    assert ("GET", "/api/v1/market/rotation-radar") in routes


def test_market_rotation_radar_response_is_safe_and_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    try:
        response = client.get("/api/v1/market/rotation-radar")

        assert response.status_code == 200
        payload = response.json()
        assert payload["endpoint"] == "/api/v1/market/rotation-radar"
        assert payload["metadata"]["noExternalCalls"] is True
        assert payload["metadata"]["quoteProvider"]["present"] is False
        assert payload["metadata"]["quoteProvider"]["status"] == "absent"
        assert payload["metadata"]["observedEvidence"]["present"] is False
        assert payload["metadata"]["observedEvidence"]["status"] == "absent"
        assert payload["metadata"]["schemaVersion"] == "market_rotation_radar_phase4_v1"
        assert payload["metadata"]["themeRegistryVersion"] == "rotation_theme_registry_v2"
        assert payload["metadata"]["timeWindows"] == ["5m", "15m", "60m", "1d"]
        assert payload["metadata"]["proxyQualityRequired"] is True
        assert payload["metadata"]["alertsAreReadOnlyEvidence"] is True
        assert payload["metadata"]["notificationDeliveryEnabled"] is False
        consumer_snapshot = payload["consumerEvidenceSnapshot"]
        assert consumer_snapshot["market"] == "US"
        assert consumer_snapshot["generatedAt"] == payload["generatedAt"]
        assert consumer_snapshot["asOf"] == payload["generatedAt"]
        assert consumer_snapshot["freshness"] == "fallback"
        assert consumer_snapshot["isFallback"] is True
        assert consumer_snapshot["isStale"] is False
        assert consumer_snapshot["isPartial"] is False
        assert consumer_snapshot["headlineEligibleThemeCount"] == 0
        assert consumer_snapshot["observationThemeCount"] == len(payload["themes"])
        assert consumer_snapshot["taxonomyThemeCount"] == 0
        assert consumer_snapshot["scoreContributionAllowed"] is False
        assert consumer_snapshot["authorityGrant"] is False
        assert consumer_snapshot["providerState"]["present"] is False
        assert consumer_snapshot["providerState"]["status"] == "absent"
        assert consumer_snapshot["providerState"]["sourceType"] == "fallback_static"
        assert consumer_snapshot["providerState"]["sourceAuthorityAllowed"] is False
        assert consumer_snapshot["providerState"]["scoreContributionAllowed"] is False
        assert consumer_snapshot["providerState"]["noExternalCalls"] is True
        assert len(consumer_snapshot["themes"]) == len(payload["themes"])
        assert set(consumer_snapshot["themes"][0]) == {
            "id",
            "name",
            "rankEligible",
            "headlineEligible",
            "rankingLane",
            "observationOnly",
            "taxonomyOnly",
            "scoreContributionAllowed",
            "freshness",
            "isFallback",
            "isStale",
            "isPartial",
            "evidenceQuality",
            "dataGaps",
        }
        assert all(theme["scoreContributionAllowed"] is False for theme in consumer_snapshot["themes"])
        _assert_consumer_snapshot_excludes_admin_fields(consumer_snapshot)
        assert payload["isFallback"] is True
        assert payload["freshness"] == "fallback"
        assert payload["themes"]
        assert all(theme["freshness"] != "live" for theme in payload["themes"])
        assert all(theme["confidence"] <= 0.25 for theme in payload["themes"])
        assert all(set(theme["timeWindows"]) == {"5m", "15m", "60m", "1d"} for theme in payload["themes"])
        assert all(theme["themeDetail"]["watchlistSafe"] is True for theme in payload["themes"])
        assert all("benchmarkProxies" in theme for theme in payload["themes"])
        assert all("proxyQuality" in theme for theme in payload["themes"])
        assert all("themeDefinition" in theme for theme in payload["themes"])
        assert all("proxyEvidence" in theme for theme in payload["themes"])
        assert all("constituentCoverage" in theme for theme in payload["themes"])
        assert all("scoreBreakdown" in theme for theme in payload["themes"])
        assert all("weightBreakdown" in theme for theme in payload["themes"])
        assert all("coveragePenalty" in theme for theme in payload["themes"])
        assert all("fallbackPenalty" in theme for theme in payload["themes"])
        assert all("rankEligible" in theme for theme in payload["themes"])
        assert all("headlineEligible" in theme for theme in payload["themes"])
        assert all("rankExclusionReason" in theme for theme in payload["themes"])
        assert all("scoreContributionAllowed" in theme for theme in payload["themes"])
        assert all(theme["rankEligible"] is False for theme in payload["themes"])
        assert all(theme["headlineEligible"] is False for theme in payload["themes"])
        assert all(theme["scoreContributionAllowed"] is False for theme in payload["themes"])
        assert payload["summary"]["strongestThemes"] == []
        assert payload["summary"]["acceleratingThemes"] == []
        assert payload["summary"]["observationThemes"]
        assert payload["summary"]["eligibleThemeCount"] == 0
        assert payload["summary"]["headlineEligibleThemeCount"] == 0
        assert payload["summary"]["observationThemeCount"] == len(payload["themes"])
        assert payload["summary"]["noHeadlineReason"]
        assert "fallback/static" in payload["summary"]["headlineWarning"]
        assert all("missingProxySymbols" in theme for theme in payload["themes"])
        assert all("missingConstituentSymbols" in theme for theme in payload["themes"])
        assert all("rotationStateEvidence" in theme for theme in payload["themes"])
        assert all(theme["rotationStateEvidence"]["schemaVersion"] == "rotation_state_evidence_v1" for theme in payload["themes"])
        assert all(theme["rotationStateEvidence"]["flowLanguageAllowed"] is False for theme in payload["themes"])
        assert all("signalType" in theme for theme in payload["themes"])
        assert all("flowEvidenceType" in theme for theme in payload["themes"])
        assert all("flowLanguageAllowed" in theme for theme in payload["themes"])
        assert all("sourceAuthorityAllowed" in theme for theme in payload["themes"])
        assert all("evidenceQuality" in theme for theme in payload["themes"])
        assert all("dataGaps" in theme for theme in payload["themes"])
        assert all(theme["signalType"] == "insufficient_evidence" for theme in payload["themes"])
        assert all(theme["flowEvidenceType"] == "none" for theme in payload["themes"])
        assert all(theme["flowLanguageAllowed"] is False for theme in payload["themes"])
        assert all(theme["sourceAuthorityAllowed"] is False for theme in payload["themes"])
        assert all(theme["evidenceQuality"] == "insufficient" for theme in payload["themes"])
        assert all("true_flow_data_missing" in theme["dataGaps"] for theme in payload["themes"])
        assert all(theme["rotationStateEvidence"]["evidenceSnapshot"]["contractVersion"] == "source_confidence_contract_v1" for theme in payload["themes"])
        assert all(theme["rotationStateEvidence"]["evidenceSnapshot"]["sourceConfidence"]["freshness"] == "fallback" for theme in payload["themes"])
        assert all(theme["rotationStateEvidence"]["evidenceSnapshot"]["sourceConfidence"]["isFallback"] is True for theme in payload["themes"])
        assert all(theme["proxyQuality"]["coveragePercent"] <= 100 for theme in payload["themes"])
        assert all(theme["rankingLane"] == "observation" for theme in payload["themes"])
        semis = next(theme for theme in payload["themes"] if theme["id"] == "semiconductors")
        assert "SOX" in semis["themeDefinition"]["proxyIndices"]
        assert "SOX" not in semis["themeDefinition"]["proxyEtfs"]
        assert "SOX" not in semis["missingProxySymbols"]
        assert {"SMH", "SOXX"}.issubset(set(semis["themeDefinition"]["proxyEtfs"]))
        neocloud = next(theme for theme in payload["themes"] if theme["id"] == "ai_neocloud")
        eth_treasury = next(theme for theme in payload["themes"] if theme["id"] == "ethereum_treasury")
        assert "ORCL" in neocloud["membersConfigured"]
        assert "ORCL" in neocloud["themeDefinition"]["inclusionNotes"]
        assert "BMNR" in eth_treasury["membersConfigured"]
        assert "BMNR" in eth_treasury["themeDefinition"]["inclusionNotes"]
        assert all("persistenceEvidence" in theme for theme in payload["themes"])
        assert "watchlistSortingExplanation" in payload["summary"]
        assert "非买卖建议" in payload["summary"]["watchlistSortingExplanation"]
        assert all(theme["alertCandidates"] == [] for theme in payload["themes"])

        text = json.dumps(payload, ensure_ascii=False).lower()
        for marker in (
            "raw_payload",
            "provider_payload",
            "api_key",
            "password",
            "session_id",
            "cookie",
            "secret",
            "token=",
            "buy now",
            "sell now",
            "建议买入",
            "下单",
        ):
            assert marker not in text
    finally:
        client.close()


def test_market_rotation_radar_market_query_switches_theme_universe(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    try:
        cn_response = client.get("/api/v1/market/rotation-radar?market=CN")
        hk_response = client.get("/api/v1/market/rotation-radar?market=HK")
        us_response = client.get("/api/v1/market/rotation-radar")

        assert cn_response.status_code == 200
        assert hk_response.status_code == 200
        assert us_response.status_code == 200

        cn_payload = cn_response.json()
        hk_payload = hk_response.json()
        us_payload = us_response.json()

        assert cn_payload["market"] == "CN"
        assert hk_payload["market"] == "HK"
        assert us_payload["market"] == "US"
        assert len(cn_payload["themes"]) >= 25
        assert len(hk_payload["themes"]) >= 8
        assert len(us_payload["themes"]) >= 18
        assert any(theme["name"] == "AI算力" for theme in cn_payload["themes"])
        assert any(theme["name"] == "港股科技" for theme in hk_payload["themes"])
        assert any(theme["englishName"] == "AI Applications" for theme in us_payload["themes"])
        assert all(theme["market"] == "CN" for theme in cn_payload["themes"])
        assert all(theme["staticThemeOnly"] is True for theme in cn_payload["themes"])
        assert all(theme["dataQuality"] in {"taxonomy_only", "local_only", "proxy_backed"} for theme in cn_payload["themes"])
        assert all(theme["confidenceLabel"] == "待行情确认" for theme in cn_payload["themes"])
        assert all(theme["taxonomyOnly"] is True for theme in cn_payload["themes"])
        assert all(theme["observationOnly"] is True for theme in cn_payload["themes"])
        assert all(theme["rankEligible"] is False for theme in cn_payload["themes"])
        assert all(theme["headlineEligible"] is False for theme in cn_payload["themes"])
        assert all(theme["rankingLane"] == "taxonomy" for theme in cn_payload["themes"])
        assert cn_payload["summary"]["strongestThemes"] == []
        assert cn_payload["summary"]["taxonomyThemes"]
        assert cn_payload["summary"]["eligibleThemeCount"] == 0
        assert cn_payload["summary"]["headlineEligibleThemeCount"] == 0
        assert cn_payload["summary"]["noHeadlineReason"]
        assert all(theme["rotationStateEvidence"]["state"] == "insufficient_evidence" for theme in cn_payload["themes"])
        assert all(theme["rotationStateEvidence"]["flowEvidenceType"] == "none" for theme in cn_payload["themes"])
        assert all(theme["signalType"] == "taxonomy_fallback" for theme in cn_payload["themes"])
        assert all(theme["flowEvidenceType"] == "none" for theme in cn_payload["themes"])
        assert all(theme["flowLanguageAllowed"] is False for theme in cn_payload["themes"])
        assert all(theme["sourceAuthorityAllowed"] is False for theme in cn_payload["themes"])
        assert all(theme["evidenceQuality"] == "taxonomy_only" for theme in cn_payload["themes"])
        assert all("taxonomy_only" in theme["dataGaps"] for theme in cn_payload["themes"])
        assert all("true_flow_data_missing" in theme["dataGaps"] for theme in cn_payload["themes"])
        assert cn_payload["metadata"]["observedEvidence"]["present"] is False
        assert "静态主题库" in cn_payload["warning"]
    finally:
        client.close()


def test_market_rotation_radar_crypto_market_is_available_when_tab_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch)
    try:
        response = client.get("/api/v1/market/rotation-radar?market=CRYPTO")

        assert response.status_code == 200
        payload = response.json()
        assert payload["market"] == "CRYPTO"
        assert len(payload["themes"]) >= 8
        assert any(theme["name"] == "Layer 1" for theme in payload["themes"])
        assert all(theme["staticThemeOnly"] is True for theme in payload["themes"])
        assert all(theme["source"] == "local_taxonomy" for theme in payload["themes"])
        assert all(theme["freshness"] == "fallback" for theme in payload["themes"])
        assert all(theme["isFallback"] is True for theme in payload["themes"])
    finally:
        client.close()


def test_market_rotation_radar_non_us_tabs_stay_local_taxonomy_and_non_live(monkeypatch: pytest.MonkeyPatch) -> None:
    def provider_factory():
        def provider(symbols):
            raise AssertionError(f"non-US radar should not call quote provider: {tuple(symbols)}")

        return provider

    client = _client(monkeypatch, provider_factory=provider_factory)
    try:
        for market_name in ("CN", "HK", "CRYPTO"):
            response = client.get(f"/api/v1/market/rotation-radar?market={market_name}")

            assert response.status_code == 200
            payload = response.json()
            assert payload["source"] == "local_taxonomy"
            assert payload["sourceLabel"] == "静态主题库"
            assert payload["freshness"] == "fallback"
            assert payload["isFallback"] is True
            assert all(theme["source"] == "local_taxonomy" for theme in payload["themes"])
            assert all(theme["sourceClass"] == "local_taxonomy" for theme in payload["themes"])
            assert all(theme["sourceClass"] not in {"exchange_public", "official_public", "live"} for theme in payload["themes"])
            assert all(theme["freshness"] == "fallback" for theme in payload["themes"])
            assert all(theme["isFallback"] is True for theme in payload["themes"])
            assert all(theme["confidenceLabel"] == "待行情确认" for theme in payload["themes"])
    finally:
        client.close()


def test_market_rotation_radar_default_us_route_uses_injected_quote_provider_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quotes = {
        "QQQ": {
            "price": 500.0,
            "changePercent": 0.8,
            "volumeRatio": 1.2,
            "vwap": 495.0,
            "freshness": "cached",
            "source": "unit_fixture",
            "sourceLabel": "Unit Fixture",
            "asOf": "2026-05-13T09:30:00+00:00",
            "timeWindows": {
                "1d": {
                    "changePercent": 0.8,
                    "relativeVolume": 1.2,
                    "freshness": "cached",
                    "asOf": "2026-05-13T09:30:00+00:00",
                }
            },
        },
        "SPY": {
            "price": 450.0,
            "changePercent": 0.4,
            "volumeRatio": 1.0,
            "vwap": 448.0,
            "freshness": "cached",
            "source": "unit_fixture",
            "sourceLabel": "Unit Fixture",
            "asOf": "2026-05-13T09:30:00+00:00",
            "timeWindows": {
                "1d": {
                    "changePercent": 0.4,
                    "relativeVolume": 1.0,
                    "freshness": "cached",
                    "asOf": "2026-05-13T09:30:00+00:00",
                }
            },
        },
        "IWM": {
            "price": 200.0,
            "changePercent": 0.2,
            "volumeRatio": 0.9,
            "vwap": 199.0,
            "freshness": "cached",
            "source": "unit_fixture",
            "sourceLabel": "Unit Fixture",
            "asOf": "2026-05-13T09:30:00+00:00",
            "timeWindows": {
                "1d": {
                    "changePercent": 0.2,
                    "relativeVolume": 0.9,
                    "freshness": "cached",
                    "asOf": "2026-05-13T09:30:00+00:00",
                }
            },
        },
        "IGV": {
            "price": 100.0,
            "changePercent": 1.0,
            "volumeRatio": 1.4,
            "vwap": 99.0,
            "freshness": "cached",
            "source": "unit_fixture",
            "sourceLabel": "Unit Fixture",
            "asOf": "2026-05-13T09:30:00+00:00",
            "timeWindows": {
                "1d": {
                    "changePercent": 1.0,
                    "relativeVolume": 1.4,
                    "freshness": "cached",
                    "asOf": "2026-05-13T09:30:00+00:00",
                }
            },
        },
        "APP": {
            "price": 300.0,
            "changePercent": 5.0,
            "volumeRatio": 2.0,
            "vwap": 295.0,
            "freshness": "cached",
            "source": "unit_fixture",
            "sourceLabel": "Unit Fixture",
            "asOf": "2026-05-13T09:30:00+00:00",
            "timeWindows": {
                "1d": {
                    "changePercent": 5.0,
                    "relativeVolume": 2.0,
                    "freshness": "cached",
                    "asOf": "2026-05-13T09:30:00+00:00",
                }
            },
        },
        "PLTR": {
            "price": 130.0,
            "changePercent": 4.5,
            "volumeRatio": 1.8,
            "vwap": 127.0,
            "freshness": "cached",
            "source": "unit_fixture",
            "sourceLabel": "Unit Fixture",
            "asOf": "2026-05-13T09:30:00+00:00",
            "timeWindows": {
                "1d": {
                    "changePercent": 4.5,
                    "relativeVolume": 1.8,
                    "freshness": "cached",
                    "asOf": "2026-05-13T09:30:00+00:00",
                }
            },
        },
        "CRM": {
            "price": 280.0,
            "changePercent": 2.5,
            "volumeRatio": 1.3,
            "vwap": 278.0,
            "freshness": "cached",
            "source": "unit_fixture",
            "sourceLabel": "Unit Fixture",
            "asOf": "2026-05-13T09:30:00+00:00",
            "timeWindows": {
                "1d": {
                    "changePercent": 2.5,
                    "relativeVolume": 1.3,
                    "freshness": "cached",
                    "asOf": "2026-05-13T09:30:00+00:00",
                }
            },
        },
    }

    def provider_factory():
        def provider(symbols):
            return {
                "quotes": {symbol: quotes[symbol] for symbol in symbols if symbol in quotes},
                "metadata": {
                    "quoteMode": "proxy",
                    "sourceType": "unofficial_public_api",
                    "freshness": "delayed",
                    "asOf": "2026-05-13T09:30:00+00:00",
                    "noExternalCalls": False,
                },
            }

        return provider

    client = _client(monkeypatch, provider_factory=provider_factory)
    try:
        response = client.get("/api/v1/market/rotation-radar")

        assert response.status_code == 200
        payload = response.json()
        assert payload["market"] == "US"
        assert payload["isFallback"] is False
        assert payload["metadata"]["quoteProvider"]["present"] is True
        assert payload["metadata"]["quoteProvider"]["status"] in {"partial", "success"}
        assert payload["metadata"]["quoteProvider"]["quoteMode"] == "proxy"
        assert payload["metadata"]["quoteProvider"]["sourceType"] == "unofficial_proxy"
        assert payload["metadata"]["quoteProvider"]["freshness"] == "delayed"
        assert payload["metadata"]["quoteProvider"]["noExternalCalls"] is False
        assert payload["metadata"]["observedEvidence"]["present"] is False
        assert payload["metadata"]["observedEvidence"]["status"] == "absent"
        assert payload["metadata"]["quoteProvider"]["coverage"]["usableSymbolCount"] > 0
        assert payload["source"] == "computed"
        assert any(theme["id"] == "ai_applications" and theme["source"] != "fallback" for theme in payload["themes"])
    finally:
        client.close()


def test_market_rotation_radar_route_separates_headline_and_observation_lanes_when_headline_data_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quotes = {
        "QQQ": _headline_quote("QQQ", 0, change=0.4, volume_ratio=1.0),
        "SPY": _headline_quote("SPY", 1, change=0.2, volume_ratio=1.0),
        "IWM": _headline_quote("IWM", 2, change=0.1, volume_ratio=1.0),
        "IGV": _headline_quote("IGV", 3, change=0.8, volume_ratio=1.3),
        "APP": _headline_quote("APP", 4, change=4.2, volume_ratio=1.8),
        "PLTR": _headline_quote("PLTR", 5, change=3.8, volume_ratio=1.7),
        "CRM": _headline_quote("CRM", 6, change=3.2, volume_ratio=1.6),
        "SNOW": _headline_quote("SNOW", 7, change=2.8, volume_ratio=1.5),
        "ADBE": _headline_quote("ADBE", 8, change=2.6, volume_ratio=1.45),
        "NOW": _headline_quote("NOW", 9, change=2.4, volume_ratio=1.4),
        "DUOL": _headline_quote("DUOL", 10, change=2.2, volume_ratio=1.35),
        "MDB": _headline_quote("MDB", 11, change=2.0, volume_ratio=1.35),
        "TEAM": _headline_quote("TEAM", 12, change=1.8, volume_ratio=1.3),
        "WDAY": _headline_quote("WDAY", 13, change=1.6, volume_ratio=1.3),
    }

    def provider_factory():
        def provider(symbols):
            return {
                "quotes": {symbol: quotes[symbol] for symbol in symbols if symbol in quotes},
                "metadata": {
                    "quoteMode": "proxy",
                    "sourceType": "cache_snapshot",
                    "freshness": "cached",
                    "asOf": "2026-05-13T09:30:00+00:00",
                    "noExternalCalls": True,
                },
            }

        return provider

    client = _client(monkeypatch, provider_factory=provider_factory)
    try:
        response = client.get("/api/v1/market/rotation-radar")

        assert response.status_code == 200
        payload = response.json()
        assert payload["summary"]["eligibleThemeCount"] == payload["summary"]["headlineEligibleThemeCount"]
        assert payload["summary"]["eligibleThemeCount"] > 0
        assert payload["summary"]["noHeadlineReason"] is None
        assert payload["summary"]["strongestThemes"]
        assert payload["summary"]["acceleratingThemes"]
        headline_items = payload["summary"]["strongestThemes"] + payload["summary"]["acceleratingThemes"]
        headline_ids = {theme["id"] for theme in headline_items}
        observation_ids = {theme["id"] for theme in payload["summary"]["observationThemes"]}
        taxonomy_ids = {theme["id"] for theme in payload["summary"]["taxonomyThemes"]}
        assert headline_ids.isdisjoint(observation_ids)
        assert headline_ids.isdisjoint(taxonomy_ids)
        assert all(theme["rankEligible"] is True for theme in headline_items)
        assert all(theme["headlineEligible"] is True for theme in headline_items)
        assert all(theme["rankingLane"] == "headline" for theme in headline_items)
        assert all(theme["observationOnly"] is False for theme in headline_items)
        assert all(theme["taxonomyOnly"] is False for theme in headline_items)
        assert all(theme["rankEligible"] is False for theme in payload["summary"]["observationThemes"])
        assert all(theme["headlineEligible"] is False for theme in payload["summary"]["observationThemes"])
        assert all(theme["rankingLane"] == "observation" for theme in payload["summary"]["observationThemes"])
        assert any(theme["id"] == "ai_applications" for theme in payload["summary"]["strongestThemes"])
        assert payload["metadata"]["quoteProvider"]["sourceType"] == "cache_snapshot"
        assert payload["metadata"]["quoteProvider"]["freshness"] == "cached"
    finally:
        client.close()


def test_market_rotation_radar_api_preserves_enabled_etf_leadership_contract_without_broadening_headlines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stable_etfs, quotes, etf_authority_spine = _bounded_etf_authority_fixture()

    def provider_factory():
        def provider(symbols):
            return {
                "quotes": {symbol: quotes[symbol] for symbol in symbols if symbol in quotes},
                "metadata": {
                    "quoteMode": "configured",
                    "source": "alpaca",
                    "sourceLabel": "Alpaca SIP",
                    "sourceType": "official_public",
                    "sourceTier": "broker_authorized",
                    "providerTier": "tier_1_configured",
                    "freshness": "live",
                    "asOf": "2026-05-07T09:45:00+00:00",
                    "noExternalCalls": False,
                    "providerDiagnostics": {
                        "etfAuthoritySpine": etf_authority_spine,
                    },
                },
            }

        return provider

    client = _client(monkeypatch, provider_factory=provider_factory)
    try:
        response = client.get("/api/v1/market/rotation-radar")

        assert response.status_code == 200
        payload = response.json()
        diagnostics = payload["etfLeadershipDiagnostics"]
        assert diagnostics["enabled"] is True
        assert diagnostics["source"] == "alpaca_etf_authority_spine"
        assert diagnostics["asOf"] == "2026-05-07T09:45:00+00:00"
        assert diagnostics["eligibleSymbols"] == list(stable_etfs)
        assert diagnostics["leadingSymbols"] == ["SMH", "SOXX", "QQQ"]
        assert diagnostics["laggingSymbols"] == ["IWM", "IGV", "SPY"]
        assert diagnostics["leadershipSpread"] > 1.0
        assert diagnostics["confidenceLabel"] == "high"
        assert diagnostics["reasonCodes"] == ["bounded_etf_authority_active"]
        assert [row["symbol"] for row in diagnostics["evidence"]] == list(stable_etfs)
        assert all(row["symbol"] in stable_etfs for row in diagnostics["evidence"])
        assert all(row["sourceAuthorityAllowed"] is True for row in diagnostics["evidence"])
        assert all(row["scoreContributionAllowed"] is True for row in diagnostics["evidence"])
        consumer_snapshot = payload["consumerEvidenceSnapshot"]
        assert consumer_snapshot["scoreContributionAllowed"] is False
        assert consumer_snapshot["authorityGrant"] is False
        assert consumer_snapshot["providerState"]["sourceType"] == "official_public"
        assert consumer_snapshot["providerState"]["scoreContributionAllowed"] is False
        assert consumer_snapshot["etfProxySummary"]["present"] is True
        assert consumer_snapshot["etfProxySummary"]["proxyOnly"] is True
        assert consumer_snapshot["etfProxySummary"]["fundFlowAuthorityAllowed"] is False
        assert consumer_snapshot["etfProxySummary"]["enabled"] is True
        assert consumer_snapshot["etfProxySummary"]["source"] == "alpaca_etf_authority_spine"
        assert consumer_snapshot["etfProxySummary"]["eligibleSymbolCount"] == len(stable_etfs)
        assert consumer_snapshot["etfProxySummary"]["leadingSymbols"] == ["SMH", "SOXX", "QQQ"]
        assert "proxy-only" in consumer_snapshot["etfProxySummary"]["label"]
        assert "evidence" not in consumer_snapshot["etfProxySummary"]
        assert "quotes" not in consumer_snapshot["etfProxySummary"]
        _assert_consumer_snapshot_excludes_admin_fields(consumer_snapshot)
        assert payload["metadata"]["quoteProvider"]["etfAuthoritySpine"]["sourceAuthorityAllowed"] is True
        assert payload["metadata"]["quoteProvider"]["etfAuthoritySpine"]["scoreContributionAllowed"] is True
        ai_theme = next(theme for theme in payload["themes"] if theme["id"] == "ai_applications")
        igv_proxy = ai_theme["benchmarkProxies"]["IGV"]
        assert igv_proxy["etfAuthorityEvidence"]["symbol"] == "IGV"
        assert igv_proxy["etfAuthorityEvidence"]["sourceAuthorityAllowed"] is True
        assert igv_proxy["etfAuthorityEvidence"]["scoreContributionAllowed"] is True
        assert igv_proxy["etfAuthorityEvidence"]["reasonCodes"] == []
        assert payload["summary"]["headlineEligibleThemeCount"] == 0
        assert payload["summary"]["eligibleThemeCount"] == 0
        assert payload["summary"]["strongestThemes"] == []
        assert payload["summary"]["acceleratingThemes"] == []
        assert ai_theme["headlineEligible"] is False
        assert ai_theme["scoreContributionAllowed"] is False
        assert ai_theme["rankingLane"] == "observation"
    finally:
        client.close()


def test_market_rotation_radar_api_preserves_disabled_etf_leadership_reason_codes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, quotes, etf_authority_spine = _bounded_etf_authority_fixture()
    quotes["SMH"]["timeWindows"].pop("15m")
    etf_authority_spine["fulfilledWindows"] = ["5m", "60m", "1d"]
    etf_authority_spine["missingWindows"] = ["15m"]
    etf_authority_spine["trustLevel"] = "partial"
    etf_authority_spine["sourceAuthorityAllowed"] = False
    etf_authority_spine["scoreContributionAllowed"] = False
    etf_authority_spine["reasonCodes"] = ["missing_required_windows", "entitlement"]
    for row in etf_authority_spine["quotes"]:
        if row["symbol"] == "SMH":
            row["windowsFulfilled"] = ["5m", "60m", "1d"]
            row["trustLevel"] = "partial"
            row["sourceAuthorityAllowed"] = False
            row["scoreContributionAllowed"] = False
            row["reasonCodes"] = ["missing_required_windows", "entitlement"]

    def provider_factory():
        def provider(symbols):
            return {
                "quotes": {symbol: quotes[symbol] for symbol in symbols if symbol in quotes},
                "metadata": {
                    "quoteMode": "configured",
                    "source": "alpaca",
                    "sourceLabel": "Alpaca SIP",
                    "sourceType": "official_public",
                    "sourceTier": "broker_authorized",
                    "providerTier": "tier_1_configured",
                    "freshness": "live",
                    "asOf": "2026-05-07T09:45:00+00:00",
                    "noExternalCalls": False,
                    "providerDiagnostics": {
                        "etfAuthoritySpine": etf_authority_spine,
                    },
                },
            }

        return provider

    client = _client(monkeypatch, provider_factory=provider_factory)
    try:
        response = client.get("/api/v1/market/rotation-radar")

        assert response.status_code == 200
        payload = response.json()
        diagnostics = payload["etfLeadershipDiagnostics"]
        assert diagnostics["enabled"] is False
        assert diagnostics["leadingSymbols"] == []
        assert diagnostics["laggingSymbols"] == []
        assert diagnostics["leadershipSpread"] is None
        assert diagnostics["confidenceLabel"] == "disabled"
        assert "missing_required_windows" in diagnostics["reasonCodes"]
        assert "ineligible_bounded_etf" in diagnostics["reasonCodes"]
        smh_row = next(row for row in diagnostics["evidence"] if row["symbol"] == "SMH")
        assert smh_row["sourceAuthorityAllowed"] is False
        assert smh_row["scoreContributionAllowed"] is False
        assert "missing_required_windows" in smh_row["reasonCodes"]
        assert "entitlement" in smh_row["reasonCodes"]
    finally:
        client.close()


def test_market_rotation_radar_api_yfinance_fallback_cannot_enable_etf_leadership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stable_etfs, quotes, _ = _bounded_etf_authority_fixture()
    yfinance_quotes = {
        symbol: {
            **_shared_cache_quote(symbol, index, freshness="delayed"),
            "changePercent": quotes[symbol]["changePercent"],
            "timeWindows": {
                "1d": {
                    "changePercent": quotes[symbol]["changePercent"],
                    "freshness": "delayed",
                    "asOf": "2026-05-07T09:45:00+00:00",
                    "available": True,
                }
            },
            "source": "yfinance_proxy",
            "sourceLabel": "Yahoo Finance",
            "sourceType": "unofficial_public_api",
            "sourceTier": "unofficial_public_api",
            "isFallback": True,
        }
        for index, symbol in enumerate(stable_etfs)
    }

    def provider_factory():
        def provider(symbols):
            return {
                "quotes": {symbol: yfinance_quotes[symbol] for symbol in symbols if symbol in yfinance_quotes},
                "metadata": {
                    "quoteMode": "proxy",
                    "source": "yfinance_proxy",
                    "sourceLabel": "Yahoo Finance",
                    "sourceType": "unofficial_public_api",
                    "sourceTier": "unofficial_public_api",
                    "providerTier": "tier_2_delayed_proxy",
                    "freshness": "delayed",
                    "asOf": "2026-05-07T09:45:00+00:00",
                    "noExternalCalls": False,
                },
            }

        return provider

    client = _client(monkeypatch, provider_factory=provider_factory)
    try:
        response = client.get("/api/v1/market/rotation-radar")

        assert response.status_code == 200
        payload = response.json()
        diagnostics = payload["etfLeadershipDiagnostics"]
        assert diagnostics["enabled"] is False
        assert diagnostics["eligibleSymbols"] == []
        assert diagnostics["leadingSymbols"] == []
        assert diagnostics["laggingSymbols"] == []
        assert "etf_authority_spine_missing" in diagnostics["reasonCodes"]
    finally:
        client.close()


def test_market_rotation_radar_timeout_preserves_configured_provider_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def provider_factory():
        def provider(symbols):
            time.sleep(0.05)
            return {}

        provider.rotation_radar_provider_diagnostics = lambda: {
            "configuredProviderAttempted": True,
            "configuredProviderName": "alpaca",
            "credentialsPresent": True,
            "credentialFieldsMissing": [],
            "credentialSource": "env",
            "providerConstructed": False,
            "feed": "iex",
            "feedEntitlementStatus": "not_checked",
        }
        return provider

    monkeypatch.setattr(radar_service_module, "_QUOTE_PROVIDER_TIMEOUT_SECONDS", 0.001)
    client = _client(monkeypatch, provider_factory=provider_factory)
    try:
        response = client.get("/api/v1/market/rotation-radar?market=US")

        assert response.status_code == 200
        payload = response.json()
        diagnostics = payload["metadata"]["quoteProvider"]["providerDiagnostics"]
        assert diagnostics["configuredProviderAttempted"] is True
        assert diagnostics["configuredProviderName"] == "alpaca"
        assert diagnostics["credentialsPresent"] is True
        assert diagnostics["credentialFieldsMissing"] == []
        assert diagnostics["credentialSource"] == "env"
        assert diagnostics["providerConstructed"] is False
        assert diagnostics["feed"] == "iex"
        assert diagnostics["feedEntitlementStatus"] == "not_checked"
        assert diagnostics["providerFailureReason"] == "quote_fetch_failed"
        assert diagnostics["providerFailureReasons"] == ["quote_fetch_failed"]
        assert diagnostics["finalSourceTier"] == "fallback_static"
        assert diagnostics["trustLevel"] == "unavailable"
        assert "raw-secret-value" not in json.dumps(diagnostics, ensure_ascii=False)
    finally:
        client.close()


def test_market_rotation_radar_then_sector_rotation_reuses_provider_backed_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_calls = _install_counting_default_provider(monkeypatch)
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    client = TestClient(app)
    try:
        radar_response = client.get("/api/v1/market/rotation-radar")
        sector_response = client.get("/api/v1/market/sector-rotation")

        assert radar_response.status_code == 200
        assert sector_response.status_code == 200
        radar_payload = radar_response.json()
        sector_payload = sector_response.json()
        assert len(provider_calls) == 1
        assert radar_payload["endpoint"] == "/api/v1/market/rotation-radar"
        assert radar_payload["market"] == "US"
        assert radar_payload["metadata"]["schemaVersion"] == "market_rotation_radar_phase4_v1"
        assert {"benchmarks", "summary", "themes", "metadata"}.issubset(radar_payload)
        assert "endpoint" not in sector_payload
        assert {"source", "sourceLabel", "updatedAt", "items", "providerHealth", "evidenceSnapshot"}.issubset(sector_payload)
        assert sector_payload["items"]
        assert sector_payload["source"] == radar_payload["source"]
        assert sector_payload["freshness"] == radar_payload["freshness"]
        assert sector_payload["radarSnapshot"]["source"] == radar_payload["source"]
        assert sector_payload["radarSnapshot"]["sourceLabel"] == radar_payload["sourceLabel"]
        assert sector_payload["radarSnapshot"]["asOf"] == radar_payload["metadata"]["quoteProvider"]["asOf"]
        assert sector_payload["radarSnapshot"]["freshness"] == radar_payload["freshness"]
        assert sector_payload["sourceFreshnessEvidence"]["freshness"] == radar_payload["freshness"]
        assert sector_payload["sourceFreshnessEvidence"]["freshness"] not in {"live", "fresh"}
        assert sector_payload["items"][0]["rotationStateEvidence"]
        assert sector_payload["items"][0]["rotationStateEvidence"]["source"] == radar_payload["themes"][0]["rotationStateEvidence"]["source"]
        assert sector_payload["items"][0]["rotationStateEvidence"]["sourceConfidence"]["freshness"] == radar_payload["themes"][0]["rotationStateEvidence"]["sourceConfidence"]["freshness"]
        assert sector_payload["items"][0]["sourceFreshnessEvidence"]["freshness"] == radar_payload["themes"][0]["freshness"]
        assert sector_payload["items"][0]["freshness"] == radar_payload["themes"][0]["freshness"]
    finally:
        client.close()


def test_sector_rotation_then_market_rotation_radar_reuses_provider_backed_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_calls = _install_counting_default_provider(monkeypatch)
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    client = TestClient(app)
    try:
        sector_response = client.get("/api/v1/market/sector-rotation")
        radar_response = client.get("/api/v1/market/rotation-radar")

        assert sector_response.status_code == 200
        assert radar_response.status_code == 200
        sector_payload = sector_response.json()
        radar_payload = radar_response.json()
        assert len(provider_calls) == 1
        assert sector_payload["items"]
        assert {"relativeStrength", "rank"}.issubset(sector_payload["items"][0])
        assert sector_payload["radarSnapshot"]["freshness"] == "delayed"
        assert sector_payload["sourceFreshnessEvidence"]["freshness"] == "delayed"
        assert sector_payload["items"][0]["rotationStateEvidence"]["sourceConfidence"]["freshness"] == sector_payload["items"][0]["rotationStateEvidence"]["evidenceSnapshot"]["sourceConfidence"]["freshness"]
        assert sector_payload["items"][0]["freshness"] == "delayed"
        assert radar_payload["endpoint"] == "/api/v1/market/rotation-radar"
        assert radar_payload["metadata"]["quoteProvider"]["present"] is True
        assert radar_payload["metadata"]["quoteProvider"]["status"] == "success"
        assert radar_payload["metadata"]["quoteProvider"]["freshness"] == "delayed"
        assert radar_payload["metadata"]["observedEvidence"]["present"] is False
        assert radar_payload["themes"]
    finally:
        client.close()


def test_market_rotation_radar_partial_quote_failures_are_sanitized_in_api_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quotes = {
        "QQQ": {
            "price": 500.0,
            "changePercent": 0.8,
            "volumeRatio": 1.2,
            "vwap": 495.0,
            "freshness": "delayed",
            "source": "unit_fixture",
            "sourceLabel": "Unit Fixture",
            "asOf": "2026-05-13T09:30:00+00:00",
        },
        "SPY": {
            "price": 450.0,
            "changePercent": 0.4,
            "volumeRatio": 1.0,
            "vwap": 448.0,
            "freshness": "delayed",
            "source": "unit_fixture",
            "sourceLabel": "Unit Fixture",
            "asOf": "2026-05-13T09:30:00+00:00",
        },
        "IWM": {
            "price": 200.0,
            "changePercent": 0.2,
            "volumeRatio": 0.9,
            "vwap": 199.0,
            "freshness": "delayed",
            "source": "unit_fixture",
            "sourceLabel": "Unit Fixture",
            "asOf": "2026-05-13T09:30:00+00:00",
        },
        "IGV": {
            "price": 100.0,
            "changePercent": 1.0,
            "volumeRatio": 1.4,
            "vwap": 99.0,
            "freshness": "delayed",
            "source": "unit_fixture",
            "sourceLabel": "Unit Fixture",
            "asOf": "2026-05-13T09:30:00+00:00",
        },
        "APP": {
            "price": 300.0,
            "changePercent": 5.0,
            "volumeRatio": 2.0,
            "vwap": 295.0,
            "freshness": "delayed",
            "source": "unit_fixture",
            "sourceLabel": "Unit Fixture",
            "asOf": "2026-05-13T09:30:00+00:00",
        },
        "PLTR": {
            "price": 130.0,
            "changePercent": 4.5,
            "volumeRatio": 1.8,
            "vwap": 127.0,
            "freshness": "delayed",
            "source": "unit_fixture",
            "sourceLabel": "Unit Fixture",
            "asOf": "2026-05-13T09:30:00+00:00",
        },
        "CRM": {
            "price": 280.0,
            "changePercent": 2.5,
            "volumeRatio": 1.3,
            "vwap": 278.0,
            "freshness": "delayed",
            "source": "unit_fixture",
            "sourceLabel": "Unit Fixture",
            "asOf": "2026-05-13T09:30:00+00:00",
        },
    }

    def provider_factory():
        def provider(symbols):
            return {
                "quotes": {symbol: quotes[symbol] for symbol in symbols if symbol in quotes},
                "metadata": {
                    "quoteMode": "proxy",
                    "sourceType": "unofficial_public_api",
                    "freshness": "delayed",
                    "failedSymbols": ["sq", "IRBT", "X", "  "],
                    "failedSymbolCount": 5,
                    "unavailableReason": "possibly delisted / no price data",
                    "noExternalCalls": False,
                    "providerDiagnostics": {
                        "configuredProviderAttempted": True,
                        "providerAttempted": True,
                        "credentialsPresent": False,
                        "credentialFieldsMissing": ["ALPACA_API_KEY"],
                        "requestWindowResults": {"5m": {"failureClasses": {"timeout": 1}}},
                        "symbolFailureSamples": [{"symbol": "SQ", "error": "timeout"}],
                        "perWindowTimeout": 2.5,
                        "totalProviderBudget": 8.0,
                        "sourceAuthorityRouter": {"route": "operator_only"},
                        "activationHint": "set secrets",
                        "recommendedAction": "operator action",
                        "proxyEnvironment": {"httpsProxyConfigured": True},
                        "adminDiagnostics": {"raw": True},
                    },
                },
            }

        return provider

    client = _client(monkeypatch, provider_factory=provider_factory)
    try:
        response = client.get("/api/v1/market/rotation-radar")

        assert response.status_code == 200
        payload = response.json()
        assert payload["isFallback"] is False
        assert payload["metadata"]["quoteProvider"]["status"] == "partial"
        assert payload["metadata"]["quoteProvider"]["failedSymbols"] == ["SQ", "IRBT", "X"]
        assert payload["metadata"]["quoteProvider"]["failedSymbolCount"] == 5
        assert payload["metadata"]["quoteProvider"]["unavailableReason"] == "symbol_unavailable"
        assert payload["metadata"]["quoteProvider"]["providerDiagnostics"]["credentialFieldsMissing"] == ["ALPACA_API_KEY"]
        assert "requestWindowResults" in payload["metadata"]["quoteProvider"]["providerDiagnostics"]
        assert "部分主题行情暂不可用" in payload["warning"]
        consumer_snapshot = payload["consumerEvidenceSnapshot"]
        assert consumer_snapshot["isPartial"] is True
        assert consumer_snapshot["freshness"] == "partial"
        assert consumer_snapshot["providerState"]["status"] == "partial"
        assert consumer_snapshot["providerState"]["sourceType"] in {"synthetic_fixture", "unofficial_proxy"}
        assert consumer_snapshot["providerState"]["coverage"]["usableSymbolCount"] > 0
        assert consumer_snapshot["scoreContributionAllowed"] is False
        assert "partial_coverage" in consumer_snapshot["reasonCodes"]
        assert "live" not in {consumer_snapshot["freshness"], consumer_snapshot["providerState"]["freshness"]}
        _assert_consumer_snapshot_excludes_admin_fields(consumer_snapshot)
        ai_apps = next(theme for theme in payload["themes"] if theme["id"] == "ai_applications")
        assert ai_apps["rotationStateEvidence"]["evidenceSnapshot"]["sourceConfidence"]["freshness"] == "partial"
        assert ai_apps["rotationStateEvidence"]["evidenceSnapshot"]["sourceConfidence"]["isPartial"] is True
        assert ai_apps["rotationStateEvidence"]["evidenceSnapshot"]["sourceConfidence"]["freshness"] not in {"live", "fresh"}
        assert "possibly delisted" not in json.dumps(payload, ensure_ascii=False).lower()
    finally:
        client.close()


def test_market_rotation_radar_timeout_degrades_to_fallback_payload_in_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def provider_factory():
        def provider(symbols):
            time.sleep(0.2)
            return {}

        return provider

    monkeypatch.setattr(
        "src.services.market_rotation_radar_service._QUOTE_PROVIDER_TIMEOUT_SECONDS",
        0.01,
        raising=False,
    )
    client = _client(monkeypatch, provider_factory=provider_factory)
    try:
        started = time.monotonic()
        response = client.get("/api/v1/market/rotation-radar?market=US")
        elapsed = time.monotonic() - started

        assert elapsed < 0.15
        assert response.status_code == 200
        payload = response.json()
        assert payload["market"] == "US"
        assert payload["isFallback"] is True
        assert payload["source"] == "fallback"
        assert payload["metadata"]["quoteProvider"]["present"] is True
        assert payload["metadata"]["quoteProvider"]["status"] == "fallback"
        assert payload["metadata"]["quoteProvider"]["unavailableReason"] == "quote_fetch_failed"
        assert payload["metadata"]["quoteProvider"]["failedSymbolCount"] >= 1
        assert payload["metadata"]["quoteProvider"]["failedSymbols"]
        assert "timeout" not in json.dumps(payload, ensure_ascii=False).lower()
    finally:
        client.close()
