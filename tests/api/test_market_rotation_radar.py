# -*- coding: utf-8 -*-
"""API contract tests for the market rotation radar endpoint."""

from __future__ import annotations

import json
import time
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from api.v1.endpoints import market


def _client(monkeypatch: pytest.MonkeyPatch, provider_factory=None) -> TestClient:
    monkeypatch.setattr(
        market,
        "get_rotation_radar_quote_provider",
        provider_factory or (lambda: None),
    )
    app = FastAPI()
    app.include_router(market.router, prefix="/api/v1/market")
    return TestClient(app)


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
        assert payload["metadata"]["timeWindows"] == ["5m", "15m", "60m", "1d"]
        assert payload["metadata"]["proxyQualityRequired"] is True
        assert payload["metadata"]["alertsAreReadOnlyEvidence"] is True
        assert payload["metadata"]["notificationDeliveryEnabled"] is False
        assert payload["isFallback"] is True
        assert payload["freshness"] == "fallback"
        assert payload["themes"]
        assert all(theme["freshness"] != "live" for theme in payload["themes"])
        assert all(theme["confidence"] <= 0.25 for theme in payload["themes"])
        assert all(set(theme["timeWindows"]) == {"5m", "15m", "60m", "1d"} for theme in payload["themes"])
        assert all(theme["themeDetail"]["watchlistSafe"] is True for theme in payload["themes"])
        assert all("benchmarkProxies" in theme for theme in payload["themes"])
        assert all("proxyQuality" in theme for theme in payload["themes"])
        assert all("rotationStateEvidence" in theme for theme in payload["themes"])
        assert all(theme["rotationStateEvidence"]["schemaVersion"] == "rotation_state_evidence_v1" for theme in payload["themes"])
        assert all(theme["rotationStateEvidence"]["flowLanguageAllowed"] is False for theme in payload["themes"])
        assert all(theme["rotationStateEvidence"]["evidenceSnapshot"]["contractVersion"] == "source_confidence_contract_v1" for theme in payload["themes"])
        assert all(theme["rotationStateEvidence"]["evidenceSnapshot"]["sourceConfidence"]["freshness"] == "fallback" for theme in payload["themes"])
        assert all(theme["rotationStateEvidence"]["evidenceSnapshot"]["sourceConfidence"]["isFallback"] is True for theme in payload["themes"])
        assert all(theme["proxyQuality"]["coveragePercent"] <= 100 for theme in payload["themes"])
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
        assert all(theme["rotationStateEvidence"]["state"] == "insufficient_evidence" for theme in cn_payload["themes"])
        assert all(theme["rotationStateEvidence"]["flowEvidenceType"] == "none" for theme in cn_payload["themes"])
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
    client = _client(monkeypatch)
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
        assert "部分主题行情暂不可用" in payload["warning"]
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
