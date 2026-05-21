# -*- coding: utf-8 -*-
"""Market rotation radar scoring and safety tests."""

from __future__ import annotations

import json
import os
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pandas as pd

from data_provider.provider_credentials import ProviderCredentialBundle
from src.config import Config
from src.services.market_data_source_registry import project_source_provenance
from src.services.market_rotation_radar_service import MarketRotationRadarService
from src.services.rotation_radar_quote_provider import (
    load_rotation_radar_quotes,
    run_rotation_radar_alpaca_live_smoke,
)


def _quote(
    symbol: str,
    change: float,
    *,
    volume_ratio: float = 1.0,
    price: float = 100.0,
    freshness: str = "live",
    is_stale: bool = False,
    is_fallback: bool = False,
    time_windows: dict | None = None,
    source: str = "unit_fixture",
    source_type: str | None = None,
    source_tier: str | None = None,
) -> dict:
    payload = {
        "symbol": symbol,
        "name": symbol,
        "price": price,
        "changePercent": change,
        "volume": 1_000_000 * volume_ratio,
        "averageVolume": 1_000_000,
        "vwap": price * 0.99,
        "freshness": freshness,
        "isStale": is_stale,
        "isFallback": is_fallback,
        "source": source,
        "sourceLabel": "Unit Fixture",
        "asOf": "2026-05-07T09:45:00+00:00",
    }
    if time_windows is not None:
        payload["timeWindows"] = time_windows
    if source_type is not None:
        payload["sourceType"] = source_type
    if source_tier is not None:
        payload["sourceTier"] = source_tier
    return payload


def _alpaca_credentials(*, feed: str = "sip") -> ProviderCredentialBundle:
    return ProviderCredentialBundle(
        provider="alpaca",
        auth_mode="key_secret",
        key_id="alpaca-key-id",
        secret_key="alpaca-secret",
        extras={"data_feed": feed},
    )


def _missing_alpaca_credentials() -> ProviderCredentialBundle:
    return ProviderCredentialBundle(
        provider="alpaca",
        auth_mode="key_secret",
        key_id=None,
        secret_key=None,
        extras={"data_feed": "iex"},
    )


def _partial_alpaca_credentials() -> ProviderCredentialBundle:
    return ProviderCredentialBundle(
        provider="alpaca",
        auth_mode="key_secret",
        key_id="alpaca-key-id",
        secret_key=None,
        extras={"data_feed": "sip"},
    )


def _yfinance_frame() -> pd.DataFrame:
    latest_date = datetime.now(timezone.utc).date()
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [101.0, 103.0],
            "Low": [99.0, 100.0],
            "Close": [100.0, 102.0],
            "Volume": [1_000_000.0, 1_250_000.0],
        },
        index=pd.DatetimeIndex([(latest_date - timedelta(days=1)).isoformat(), latest_date.isoformat()]),
    )


def _alpaca_bars(*, start_close: float = 100.0, end_close: float = 102.0, as_of: str | None = None) -> list[dict]:
    timestamp = as_of or (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    return [
        {"t": (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat(), "o": 99.0, "h": 101.0, "l": 98.5, "c": start_close, "v": 1000, "vw": start_close},
        {"t": timestamp, "o": start_close, "h": end_close + 1.0, "l": start_close - 1.0, "c": end_close, "v": 1500, "vw": (start_close + end_close) / 2},
    ]


def _alpaca_time_windows(
    changes: dict[str, float],
    *,
    as_of: str = "2026-05-07T09:45:00+00:00",
) -> dict[str, dict[str, object]]:
    return {
        window: {
            "changePercent": change,
            "relativeVolume": 1.2,
            "freshness": "live" if window != "1d" else "delayed",
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
        time_windows = _alpaca_time_windows(window_changes[symbol])
        quote = _quote(
            symbol,
            window_changes[symbol]["1d"],
            freshness="live",
            time_windows=time_windows,
            source="alpaca",
            source_type="official_public",
            source_tier="broker_authorized",
        )
        quote["sourceLabel"] = "Alpaca SIP"
        quote["providerTier"] = "tier_1_configured"
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


def _runtime_probe_symbols() -> tuple[str, ...]:
    return (
        "QQQ",
        "SPY",
        "IWM",
        "IGV",
        "SMH",
        "APP",
        "PLTR",
        "CRM",
        "SNOW",
        "ADBE",
        "NOW",
        "MSFT",
    )


def _utc_dt(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


class MarketRotationRadarServiceTestCase(unittest.TestCase):
    def test_live_quotes_score_confirmed_rotation_with_breadth_and_newsless_evidence(self) -> None:
        quotes = {
            "QQQ": _quote("QQQ", 0.8),
            "SPY": _quote("SPY", 0.45),
            "IWM": _quote("IWM", 0.15),
            "APP": _quote("APP", 5.1, volume_ratio=2.4, price=310),
            "PLTR": _quote("PLTR", 4.6, volume_ratio=2.0, price=132),
            "CRM": _quote("CRM", 2.8, volume_ratio=1.7, price=285),
            "SNOW": _quote("SNOW", 3.5, volume_ratio=1.8, price=212),
            "ADBE": _quote("ADBE", 2.2, volume_ratio=1.5, price=505),
            "NOW": _quote("NOW", 2.6, volume_ratio=1.6, price=780),
        }
        service = MarketRotationRadarService(
            quote_provider=lambda symbols: {symbol: quotes[symbol] for symbol in symbols if symbol in quotes},
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        payload = service.get_rotation_radar()
        theme = payload["themes"][0]
        provider_meta = payload["metadata"]["quoteProvider"]

        self.assertEqual(theme["id"], "ai_applications")
        self.assertGreaterEqual(theme["rotationScore"], 70)
        self.assertGreaterEqual(theme["confidence"], 0.55)
        self.assertIn(theme["stage"], {"early_watch", "confirmed_rotation"})
        self.assertGreaterEqual(theme["breadth"]["percentUp"], 80)
        self.assertGreaterEqual(theme["breadth"]["percentOutperformingBenchmark"], 80)
        self.assertGreaterEqual(theme["volume"]["averageRelativeVolume"], 1.5)
        self.assertTrue(theme["newslessRotation"])
        self.assertIn("无明显新闻的同步异动", theme["evidence"])
        self.assertTrue(theme["timeWindows"]["1d"]["available"])
        self.assertFalse(theme["timeWindows"]["5m"]["available"])
        self.assertLessEqual(theme["confidence"], 0.6)
        self.assertIn("QQQ", theme["benchmarkProxies"])
        self.assertIn("IGV", theme["benchmarkProxies"])
        self.assertTrue(theme["themeDetail"]["watchlistSafe"])
        self.assertIn("仅观察", theme["themeDetail"]["safeActionLabel"])
        self.assertIn("stale_or_incomplete_windows", theme["riskLabels"])
        self.assertIn("persistenceScore", theme)
        self.assertIn("persistenceEvidence", theme)
        self.assertIn("alertCandidates", theme)
        self.assertGreaterEqual(theme["persistenceScore"], 0)
        self.assertTrue(theme["alertCandidates"])
        self.assertTrue(all(candidate["readOnly"] for candidate in theme["alertCandidates"]))
        self.assertLessEqual(theme["proxyQuality"]["coveragePercent"], 75)
        self.assertLessEqual(theme["confidence"], 0.58)
        self.assertEqual(theme["benchmarkProxies"]["IGV"]["quality"]["missingReason"], "proxy_quote_missing")
        self.assertIn("ETF 代理覆盖", theme["proxyQuality"]["explanation"])
        self.assertIn("sortExplanation", theme["alertCandidates"][0])
        self.assertIn("非买卖建议", theme["alertCandidates"][0]["sortExplanation"])
        self.assertEqual(theme["rotationScore"], 89)
        self.assertEqual(theme["stage"], "early_watch")
        self.assertTrue(provider_meta["present"])
        self.assertEqual(provider_meta["status"], "partial")
        self.assertEqual(provider_meta["quoteMode"], "proxy")
        self.assertEqual(provider_meta["sourceType"], "synthetic_fixture")
        self.assertEqual(provider_meta["sourceLabelCounts"], {"Unit Fixture": len(quotes)})
        self.assertEqual(provider_meta["usableSymbolCount"], len(quotes))
        self.assertFalse(payload["metadata"]["noExternalCalls"])
        self.assertIn("rotationStateEvidence", theme)
        self.assertEqual(theme["signalType"], "relative_strength")
        self.assertEqual(theme["flowEvidenceType"], "proxy_only")
        self.assertFalse(theme["flowLanguageAllowed"])
        self.assertTrue(theme["sourceAuthorityAllowed"])
        self.assertEqual(theme["evidenceQuality"], "degraded_proxy")
        self.assertIn("true_flow_data_missing", theme["dataGaps"])
        self.assertIn("flow_methodology_missing", theme["dataGaps"])
        self.assertIn("benchmark_proxy_missing", theme["dataGaps"])
        self.assertEqual(theme["rotationStateEvidence"]["flowEvidenceType"], "proxy_only")
        self.assertFalse(theme["rotationStateEvidence"]["flowLanguageAllowed"])

    def test_intraday_windows_are_aggregated_only_when_quote_fixture_provides_them(self) -> None:
        windows = {
            "5m": {"changePercent": 0.8, "relativeVolume": 1.3, "freshness": "live", "asOf": "2026-05-07T09:45:00+00:00"},
            "15m": {"changePercent": 1.6, "relativeVolume": 1.5, "freshness": "live", "asOf": "2026-05-07T09:45:00+00:00"},
            "60m": {"changePercent": 2.2, "relativeVolume": 1.7, "freshness": "live", "asOf": "2026-05-07T09:45:00+00:00"},
        }
        quotes = {
            "QQQ": _quote("QQQ", 0.4, time_windows=windows),
            "SPY": _quote("SPY", 0.2),
            "IWM": _quote("IWM", 0.1),
            "IGV": _quote("IGV", 0.6, time_windows=windows),
            "APP": _quote("APP", 3.0, volume_ratio=1.8, time_windows=windows),
            "PLTR": _quote("PLTR", 2.4, volume_ratio=1.5, time_windows=windows),
            "CRM": _quote("CRM", 1.8, volume_ratio=1.3, time_windows=windows),
        }
        service = MarketRotationRadarService(
            quote_provider=lambda symbols: {symbol: quotes[symbol] for symbol in symbols if symbol in quotes},
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        payload = service.get_rotation_radar()
        theme = next(item for item in payload["themes"] if item["id"] == "ai_applications")

        self.assertTrue(theme["timeWindows"]["5m"]["available"])
        self.assertTrue(theme["timeWindows"]["15m"]["available"])
        self.assertTrue(theme["timeWindows"]["60m"]["available"])
        self.assertTrue(theme["timeWindows"]["1d"]["available"])
        self.assertEqual(theme["timeWindows"]["5m"]["observedMemberCount"], 3)
        self.assertEqual(theme["benchmarkProxies"]["IGV"]["role"], "sector_proxy")
        self.assertEqual(theme["benchmarkProxies"]["IGV"]["quality"]["missingReason"], None)
        self.assertEqual(theme["proxyQuality"]["coveragePercent"], 100)
        self.assertEqual(theme["proxyQuality"]["availableProxyCount"], 4)
        self.assertIn("watchlistSignals", payload["summary"])
        self.assertIn("watchlistSortingExplanation", payload["summary"])
        self.assertIn("非买卖建议", payload["summary"]["watchlistSortingExplanation"])
        self.assertEqual(payload["themes"][0]["id"], "ai_applications")
        self.assertEqual(payload["themes"][0]["rotationScore"], 73)
        self.assertEqual(payload["themes"][0]["stage"], "early_watch")
        self.assertEqual(payload["themes"][0]["signalType"], "relative_strength")
        self.assertEqual(payload["themes"][0]["evidenceQuality"], "degraded_proxy")
        dumped = json.dumps(theme, ensure_ascii=False).lower()
        self.assertNotIn("raw_payload", dumped)
        self.assertNotIn("建议买入", dumped)

    def test_fallback_when_no_provider_never_marks_live_and_caps_confidence(self) -> None:
        service = MarketRotationRadarService(now_provider=lambda: datetime(2026, 5, 7, tzinfo=timezone.utc))

        payload = service.get_rotation_radar()

        self.assertTrue(payload["isFallback"])
        self.assertEqual(payload["freshness"], "fallback")
        self.assertNotEqual(payload["freshness"], "live")
        self.assertEqual(payload["metadata"]["noExternalCalls"], True)
        self.assertEqual(payload["metadata"]["quoteProvider"]["present"], False)
        self.assertEqual(payload["metadata"]["quoteProvider"]["status"], "absent")
        self.assertGreaterEqual(len(payload["themes"]), 18)
        self.assertEqual(payload["summary"]["strongestThemes"], [])
        self.assertEqual(payload["summary"]["acceleratingThemes"], [])
        self.assertTrue(payload["summary"]["observationThemes"])
        self.assertEqual(payload["summary"]["eligibleThemeCount"], 0)
        self.assertEqual(payload["summary"]["headlineEligibleThemeCount"], 0)
        self.assertEqual(payload["summary"]["observationThemeCount"], len(payload["themes"]))
        self.assertIn("没有可用于头部排名", payload["summary"]["noHeadlineReason"])
        self.assertIn("fallback/static", payload["summary"]["headlineWarning"])
        self.assertIn("没有可用于头部排名", payload["warning"])
        self.assertTrue(all(item["rankingLane"] == "observation" for item in payload["summary"]["observationThemes"]))
        self.assertEqual(
            [(theme["id"], theme["rotationScore"], theme["stage"]) for theme in payload["themes"][:5]],
            [
                ("ai_applications", 34, "weak_or_no_signal"),
                ("ai_infrastructure", 32, "weak_or_no_signal"),
                ("semiconductors", 30, "weak_or_no_signal"),
                ("cybersecurity", 27, "weak_or_no_signal"),
                ("cloud_software", 26, "weak_or_no_signal"),
            ],
        )
        for theme in payload["themes"]:
            self.assertTrue(theme["isFallback"])
            self.assertEqual(theme["freshness"], "fallback")
            self.assertNotEqual(theme["freshness"], "live")
            self.assertLessEqual(theme["confidence"], 0.25)
            self.assertEqual(theme["stage"], "weak_or_no_signal")
            self.assertIn("rotationStateEvidence", theme)
            self.assertEqual(theme["rotationStateEvidence"]["state"], "insufficient_evidence")
            self.assertEqual(theme["rotationStateEvidence"]["flowEvidenceType"], "none")
            self.assertFalse(theme["rotationStateEvidence"]["flowLanguageAllowed"])
            self.assertFalse(theme["rankEligible"])
            self.assertFalse(theme["headlineEligible"])
            self.assertFalse(theme["scoreContributionAllowed"])
            self.assertFalse(theme["conclusionAllowed"])
            self.assertEqual(theme["signalType"], "insufficient_evidence")
            self.assertEqual(theme["flowEvidenceType"], "none")
            self.assertFalse(theme["flowLanguageAllowed"])
            self.assertFalse(theme["sourceAuthorityAllowed"])
            self.assertEqual(theme["evidenceQuality"], "insufficient")
            self.assertIn("true_flow_data_missing", theme["dataGaps"])
            self.assertIn("flow_methodology_missing", theme["dataGaps"])
            self.assertTrue(theme["observationOnly"])
            self.assertEqual(theme["rankingLane"], "observation")
            self.assertFalse(theme["taxonomyOnly"])
            self.assertEqual(theme["rankExclusionReason"], "fallback_static_source")
            self.assertEqual(theme["sourceTier"], "static_fallback")
            self.assertEqual(theme["trustLevel"], "unavailable")
            self.assertEqual(theme["scoreBreakdown"]["rankEligible"], False)
            self.assertEqual(theme["scoreBreakdown"]["rankingLane"], "observation")
            self.assertEqual(theme["scoreBreakdown"]["scoreContributionAllowed"], False)
            self.assertIn("stale_or_incomplete_windows", theme["riskLabels"])
            self.assertTrue(all(not slot["available"] for slot in theme["timeWindows"].values()))
            self.assertTrue(theme["themeDetail"]["watchlistSafe"])
            self.assertEqual(theme["proxyQuality"]["coveragePercent"], 0)
            self.assertTrue(all(proxy["quality"]["missingReason"] for proxy in theme["benchmarkProxies"].values()))

    def test_provider_backed_usable_themes_can_rank_while_fallback_static_stays_observation_only(self) -> None:
        ai_members = ("APP", "PLTR", "CRM", "SNOW", "ADBE", "NOW", "DUOL", "MDB", "TEAM", "WDAY")
        quotes = {
            "QQQ": _quote("QQQ", 0.4, freshness="cached", source="cache", source_type="cache_snapshot", source_tier="snapshot"),
            "SPY": _quote("SPY", 0.2, freshness="cached", source="cache", source_type="cache_snapshot", source_tier="snapshot"),
            "IWM": _quote("IWM", 0.1, freshness="cached", source="cache", source_type="cache_snapshot", source_tier="snapshot"),
            "IGV": _quote("IGV", 0.8, freshness="cached", source="cache", source_type="cache_snapshot", source_tier="snapshot"),
        }
        for index, symbol in enumerate(ai_members):
            quotes[symbol] = _quote(
                symbol,
                2.0 + index * 0.2,
                volume_ratio=1.35,
                freshness="cached",
                source="cache",
                source_type="cache_snapshot",
                source_tier="snapshot",
            )
        service = MarketRotationRadarService(
            quote_provider=lambda symbols: {
                "quotes": {symbol: quotes[symbol] for symbol in symbols if symbol in quotes},
                "metadata": {
                    "quoteMode": "proxy",
                    "sourceType": "cache_snapshot",
                    "sourceTier": "snapshot",
                    "freshness": "cached",
                    "asOf": "2026-05-07T09:45:00+00:00",
                    "noExternalCalls": False,
                },
            },
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        payload = service.get_rotation_radar()
        ai_theme = next(theme for theme in payload["themes"] if theme["id"] == "ai_applications")
        fallback_theme = next(theme for theme in payload["themes"] if theme["id"] == "crypto_miners")
        strongest_ids = {theme["id"] for theme in payload["summary"]["strongestThemes"]}

        self.assertIn("ai_applications", strongest_ids)
        self.assertTrue(ai_theme["rankEligible"])
        self.assertTrue(ai_theme["headlineEligible"])
        self.assertEqual(ai_theme["rankingLane"], "headline")
        self.assertTrue(ai_theme["scoreContributionAllowed"])
        self.assertTrue(ai_theme["conclusionAllowed"])
        self.assertEqual(ai_theme["rankExclusionReason"], None)
        self.assertEqual(ai_theme["trustLevel"], "usable_with_caution")
        self.assertNotEqual(ai_theme["sourceTier"], "static_fallback")
        self.assertFalse(fallback_theme["rankEligible"])
        self.assertFalse(fallback_theme["headlineEligible"])
        self.assertFalse(fallback_theme["scoreContributionAllowed"])
        self.assertTrue(fallback_theme["observationOnly"])
        self.assertEqual(fallback_theme["rankingLane"], "observation")
        self.assertEqual(fallback_theme["rankExclusionReason"], "fallback_static_source")
        self.assertNotIn(fallback_theme["id"], strongest_ids)
        self.assertEqual(payload["summary"]["eligibleThemeCount"], payload["summary"]["headlineEligibleThemeCount"])
        self.assertGreater(payload["summary"]["eligibleThemeCount"], 0)
        self.assertIsNone(payload["summary"]["noHeadlineReason"])
        self.assertTrue(all(theme["rankEligible"] for theme in payload["summary"]["strongestThemes"]))
        self.assertTrue(all(theme["headlineEligible"] for theme in payload["summary"]["strongestThemes"]))
        self.assertTrue(all(theme["rankingLane"] == "headline" for theme in payload["summary"]["strongestThemes"]))
        self.assertTrue(all(theme["rankEligible"] for theme in payload["summary"]["acceleratingThemes"]))
        self.assertTrue(all(theme["headlineEligible"] for theme in payload["summary"]["acceleratingThemes"]))

    def test_synthetic_theme_scores_remain_visible_but_are_not_headline_eligible(self) -> None:
        ai_members = ("APP", "PLTR", "CRM", "SNOW", "ADBE", "NOW", "DUOL", "MDB", "TEAM", "WDAY")
        quotes = {
            "QQQ": _quote("QQQ", 0.4, freshness="mock", source="synthetic_fixture", source_type="synthetic_fixture", source_tier="synthetic"),
            "IGV": _quote("IGV", 0.8, freshness="mock", source="synthetic_fixture", source_type="synthetic_fixture", source_tier="synthetic"),
        }
        for symbol in ai_members:
            quotes[symbol] = _quote(
                symbol,
                3.0,
                volume_ratio=1.8,
                freshness="mock",
                source="synthetic_fixture",
                source_type="synthetic_fixture",
                source_tier="synthetic",
            )
        service = MarketRotationRadarService(
            quote_provider=lambda symbols: {
                "quotes": {symbol: quotes[symbol] for symbol in symbols if symbol in quotes},
                "metadata": {
                    "quoteMode": "proxy",
                    "sourceType": "synthetic_fixture",
                    "sourceTier": "synthetic",
                    "freshness": "mock",
                    "asOf": "2026-05-07T09:45:00+00:00",
                    "noExternalCalls": True,
                },
            },
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        payload = service.get_rotation_radar()
        theme = next(item for item in payload["themes"] if item["id"] == "ai_applications")

        self.assertGreater(theme["rotationScore"], 0)
        self.assertIn("scoreBreakdown", theme)
        self.assertFalse(theme["rankEligible"])
        self.assertFalse(theme["headlineEligible"])
        self.assertFalse(theme["scoreContributionAllowed"])
        self.assertTrue(theme["observationOnly"])
        self.assertEqual(theme["rankingLane"], "observation")
        self.assertEqual(theme["rankExclusionReason"], "synthetic_source")
        self.assertEqual(theme["sourceTier"], "synthetic")
        self.assertIn(theme["trustLevel"], {"weak", "unavailable"})
        self.assertNotIn(theme["id"], {item["id"] for item in payload["summary"]["strongestThemes"]})
        self.assertTrue(all(item["rankEligible"] for item in payload["summary"]["strongestThemes"]))
        self.assertTrue(all(item["headlineEligible"] for item in payload["summary"]["acceleratingThemes"]))

    def test_registry_v2_metadata_and_proxy_explainability_are_additive(self) -> None:
        service = MarketRotationRadarService(now_provider=lambda: datetime(2026, 5, 7, tzinfo=timezone.utc))

        payload = service.get_rotation_radar()
        neocloud = next(theme for theme in payload["themes"] if theme["id"] == "ai_neocloud")
        ethereum = next(theme for theme in payload["themes"] if theme["id"] == "ethereum_treasury")
        semis = next(theme for theme in payload["themes"] if theme["id"] == "semiconductors")

        self.assertEqual(payload["metadata"]["themeRegistryVersion"], "rotation_theme_registry_v2")
        self.assertEqual(neocloud["themeDefinition"]["themeId"], "ai_neocloud")
        self.assertEqual(neocloud["themeDefinition"]["category"], "AI Compute")
        self.assertIn("ORCL", neocloud["membersConfigured"])
        self.assertIn("ORCL", neocloud["themeDefinition"]["primarySymbols"])
        self.assertIn("ORCL", neocloud["themeDefinition"]["inclusionNotes"])
        self.assertIn("AI cloud", neocloud["themeDefinition"]["inclusionNotes"]["ORCL"])
        self.assertIn("BMNR", ethereum["membersConfigured"])
        self.assertIn("BMNR", ethereum["themeDefinition"]["inclusionNotes"])
        self.assertIn("Ethereum", ethereum["themeDefinition"]["inclusionNotes"]["BMNR"])
        self.assertIn("ETH beta", ethereum["themeDefinition"]["inclusionNotes"]["BMNR"])

        self.assertIn("SOX", semis["themeDefinition"]["proxyIndices"])
        self.assertNotIn("SOX", semis["themeDefinition"]["proxyEtfs"])
        self.assertIn("SMH", semis["themeDefinition"]["proxyEtfs"])
        self.assertIn("SOXX", semis["themeDefinition"]["proxyEtfs"])
        self.assertNotIn("SOX", semis["missingProxySymbols"])
        self.assertTrue(all(row["role"] == "index_concept" for row in semis["proxyEvidence"]["proxyIndices"]))
        self.assertIn("ETF proxy", semis["proxyEvidence"]["claimBoundary"])
        self.assertIn("relative strength proxy", semis["proxyEvidence"]["claimBoundary"])
        self.assertIn("no real fund-flow dollars", semis["proxyEvidence"]["claimBoundary"])

    def test_score_and_weight_breakdown_are_deterministic_without_changing_final_fields(self) -> None:
        quotes = {
            "QQQ": _quote("QQQ", 0.4),
            "SPY": _quote("SPY", 0.2),
            "IWM": _quote("IWM", 0.1),
            "IGV": _quote("IGV", 0.6),
            "APP": _quote("APP", 3.0, volume_ratio=1.8),
            "PLTR": _quote("PLTR", 2.4, volume_ratio=1.5),
            "CRM": _quote("CRM", 1.8, volume_ratio=1.3),
        }

        def provider(symbols):
            return {
                "quotes": {symbol: quotes[symbol] for symbol in symbols if symbol in quotes},
                "metadata": {
                    "quoteMode": "proxy",
                    "sourceType": "cache_snapshot",
                    "freshness": "delayed",
                    "asOf": "2026-05-07T09:45:00+00:00",
                    "noExternalCalls": True,
                },
            }

        service = MarketRotationRadarService(
            quote_provider=provider,
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        first = service.get_rotation_radar()
        second = service.get_rotation_radar()
        first_theme = next(item for item in first["themes"] if item["id"] == "ai_applications")
        second_theme = next(item for item in second["themes"] if item["id"] == "ai_applications")

        self.assertEqual(first_theme["scoreBreakdown"], second_theme["scoreBreakdown"])
        self.assertEqual(first_theme["weightBreakdown"], second_theme["weightBreakdown"])
        self.assertEqual(first_theme["scoreBreakdown"]["finalScore"], first_theme["rotationScore"])
        self.assertEqual(first_theme["scoreBreakdown"]["stage"], first_theme["stage"])
        self.assertEqual(first_theme["weightBreakdown"]["relativeStrength"], 0.28)
        self.assertEqual(first_theme["weightBreakdown"]["breadth"], 0.22)
        self.assertEqual(first_theme["weightBreakdown"]["volume"], 0.18)
        self.assertEqual(first_theme["weightBreakdown"]["synchronization"], 0.14)
        self.assertEqual(first_theme["weightBreakdown"]["vwapParticipation"], 0.10)
        self.assertEqual(first_theme["weightBreakdown"]["persistence"], 0.08)
        self.assertEqual(first_theme["coveragePenalty"], first_theme["scoreBreakdown"]["penalties"]["coverage"])
        self.assertEqual(first_theme["fallbackPenalty"], first_theme["scoreBreakdown"]["penalties"]["fallback"])

    def test_degraded_proxy_evidence_never_appears_live_or_claims_real_flows(self) -> None:
        service = MarketRotationRadarService(now_provider=lambda: datetime(2026, 5, 7, tzinfo=timezone.utc))

        payload = service.get_rotation_radar()
        semis = next(theme for theme in payload["themes"] if theme["id"] == "semiconductors")

        self.assertEqual(semis["proxyEvidence"]["freshness"], "fallback")
        self.assertTrue(semis["proxyEvidence"]["isFallback"])
        self.assertNotIn(semis["proxyEvidence"]["freshness"], {"live", "fresh"})
        self.assertGreaterEqual(len(semis["missingProxySymbols"]), 1)
        self.assertNotIn("SOX", semis["missingProxySymbols"])
        self.assertIn("SMH", semis["missingProxySymbols"])
        self.assertIn("SOXX", semis["missingProxySymbols"])
        dumped = json.dumps(semis["proxyEvidence"], ensure_ascii=False).lower()
        self.assertIn("etf proxy", dumped)
        self.assertIn("participation proxy", dumped)
        self.assertIn("relative strength proxy", dumped)
        self.assertNotIn("real fund-flow dollars", dumped.replace("no real fund-flow dollars", ""))

    def test_quote_provider_success_metadata_can_mark_local_proxy_snapshot_without_external_calls(self) -> None:
        def provider(symbols):
            quotes = {}
            for index, symbol in enumerate(symbols):
                is_benchmark = symbol in {"QQQ", "SPY", "IWM", "IGV", "SMH", "CIBR", "CLOU", "PAVE", "BOTZ"}
                quotes[symbol] = _quote(
                    symbol,
                    0.4 if is_benchmark else 1.2 + (index % 4) * 0.15,
                    volume_ratio=1.0 if is_benchmark else 1.35,
                    freshness="cached",
                )
            return {
                "quotes": quotes,
                "metadata": {
                    "quoteMode": "proxy",
                    "sourceType": "cache_snapshot",
                    "freshness": "cached",
                    "asOf": "2026-05-07T09:45:00+00:00",
                    "noExternalCalls": True,
                },
            }

        service = MarketRotationRadarService(
            quote_provider=provider,
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        payload = service.get_rotation_radar()
        provider_meta = payload["metadata"]["quoteProvider"]

        self.assertFalse(payload["isFallback"])
        self.assertTrue(provider_meta["present"])
        self.assertEqual(provider_meta["status"], "success")
        self.assertEqual(provider_meta["quoteMode"], "proxy")
        self.assertEqual(provider_meta["sourceType"], "cache_snapshot")
        self.assertEqual(provider_meta["freshness"], "cached")
        self.assertEqual(
            provider_meta["coverage"],
            {
                "requestedSymbolCount": provider_meta["requestedSymbolCount"],
                "usableSymbolCount": provider_meta["usableSymbolCount"],
                "coveragePercent": provider_meta["coveragePercent"],
            },
        )
        self.assertEqual(provider_meta["usableSymbolCount"], provider_meta["requestedSymbolCount"])
        self.assertEqual(provider_meta["asOf"], "2026-05-07T09:45:00+00:00")
        self.assertTrue(payload["metadata"]["noExternalCalls"])
        self.assertNotEqual(provider_meta["sourceType"], "unofficial_proxy")

    def test_observed_evidence_snapshot_is_consumed_without_quote_provider_calls(self) -> None:
        provider_calls: list[list[str]] = []
        observed_evidence = {
            "quotes": {
                "QQQ": _quote("QQQ", 0.4, freshness="cached"),
                "SPY": _quote("SPY", 0.2, freshness="cached"),
                "IWM": _quote("IWM", 0.1, freshness="cached"),
                "IGV": _quote("IGV", 0.7, freshness="cached"),
                "APP": _quote("APP", 3.0, volume_ratio=1.8, freshness="cached"),
                "PLTR": _quote("PLTR", 2.4, volume_ratio=1.5, freshness="cached"),
                "CRM": _quote("CRM", 1.8, volume_ratio=1.3, freshness="cached"),
            },
            "metadata": {
                "quoteMode": "proxy",
                "sourceType": "cache_snapshot",
                "freshness": "cached",
                "asOf": "2026-05-07T09:45:00+00:00",
                "noExternalCalls": True,
            },
        }
        service = MarketRotationRadarService(
            quote_provider=lambda symbols: provider_calls.append(list(symbols)) or {},
            observed_evidence=observed_evidence,
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        payload = service.get_rotation_radar()
        provider_meta = payload["metadata"]["quoteProvider"]
        observed_meta = payload["metadata"]["observedEvidence"]

        self.assertEqual(provider_calls, [])
        self.assertFalse(payload["isFallback"])
        self.assertTrue(payload["metadata"]["noExternalCalls"])
        self.assertEqual(provider_meta["present"], False)
        self.assertEqual(provider_meta["status"], "absent")
        self.assertTrue(observed_meta["present"])
        self.assertEqual(observed_meta["status"], "partial")
        self.assertEqual(observed_meta["sourceType"], "cache_snapshot")
        self.assertEqual(observed_meta["freshness"], "cached")
        self.assertEqual(observed_meta["coverage"]["usableSymbolCount"], 7)
        self.assertEqual(observed_meta["asOf"], "2026-05-07T09:45:00+00:00")
        self.assertTrue(
            any(theme["id"] == "ai_applications" and theme["isFallback"] is False for theme in payload["themes"])
        )

    def test_quote_provider_failure_falls_back_and_marks_external_call_boundary_honestly(self) -> None:
        service = MarketRotationRadarService(
            quote_provider=lambda symbols: (_ for _ in ()).throw(RuntimeError("provider down")),
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        payload = service.get_rotation_radar()
        provider_meta = payload["metadata"]["quoteProvider"]

        self.assertTrue(payload["isFallback"])
        self.assertEqual(payload["freshness"], "fallback")
        self.assertIn("quote provider 暂不可用", payload["warning"])
        self.assertTrue(provider_meta["present"])
        self.assertEqual(provider_meta["status"], "fallback")
        self.assertEqual(provider_meta["usableSymbolCount"], 0)
        self.assertEqual(provider_meta["unavailableReason"], "provider_unavailable")
        self.assertEqual(provider_meta["failedSymbols"], [])
        self.assertEqual(provider_meta["failedSymbolCount"], 0)
        self.assertFalse(payload["metadata"]["noExternalCalls"])
        diagnostics = provider_meta["providerDiagnostics"]
        self.assertFalse(diagnostics["providerConstructed"])
        self.assertTrue(diagnostics["fallbackProviderUsed"])
        self.assertTrue(diagnostics["staticBasketFallbackUsed"])
        self.assertEqual(diagnostics["providerFailureReasons"], ["provider_unavailable"])
        self.assertEqual(diagnostics["finalSourceTier"], "fallback_static")
        self.assertEqual(diagnostics["trustLevel"], "unavailable")

    def test_partial_quote_provider_sanitizes_failed_symbols_and_keeps_payload_computed(self) -> None:
        quotes = {
            "QQQ": _quote("QQQ", 0.5),
            "SPY": _quote("SPY", 0.3),
            "IWM": _quote("IWM", 0.1),
            "IGV": _quote("IGV", 0.8),
            "APP": _quote("APP", 3.0, volume_ratio=1.8),
            "PLTR": _quote("PLTR", 2.5, volume_ratio=1.6),
            "CRM": _quote("CRM", 1.7, volume_ratio=1.3),
        }
        service = MarketRotationRadarService(
            quote_provider=lambda symbols: {
                "quotes": {symbol: quotes[symbol] for symbol in symbols if symbol in quotes},
                "metadata": {
                    "quoteMode": "proxy",
                    "sourceType": "unofficial_public_api",
                    "freshness": "delayed",
                    "failedSymbols": ["sq", "X", "IRBT", "bad symbol", "sq", "X  ", "  "],
                    "failedSymbolCount": 9,
                    "unavailableReason": "possibly delisted; no price data found 404 timeout",
                },
            },
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        payload = service.get_rotation_radar()
        provider_meta = payload["metadata"]["quoteProvider"]

        self.assertFalse(payload["isFallback"])
        self.assertEqual(payload["source"], "computed")
        self.assertEqual(provider_meta["status"], "partial")
        self.assertEqual(provider_meta["unavailableReason"], "symbol_unavailable")
        self.assertEqual(provider_meta["failedSymbols"], ["SQ", "X", "IRBT", "BAD SYMBOL"])
        self.assertEqual(provider_meta["failedSymbolCount"], 9)
        self.assertIn("部分主题行情暂不可用", payload["warning"])
        self.assertNotIn("possibly delisted", json.dumps(payload, ensure_ascii=False).lower())

        theme = next(item for item in payload["themes"] if item["id"] == "ai_applications")
        snapshot = theme["rotationStateEvidence"]["evidenceSnapshot"]

        self.assertEqual(snapshot["contractVersion"], "source_confidence_contract_v1")
        self.assertEqual(snapshot["sourceConfidence"]["freshness"], "partial")
        self.assertTrue(snapshot["sourceConfidence"]["isPartial"])
        self.assertFalse(snapshot["sourceConfidence"]["isFallback"])
        self.assertNotIn(snapshot["sourceConfidence"]["freshness"], {"live", "fresh"})
        self.assertEqual(snapshot["signals"]["breadth"]["sourceConfidence"]["freshness"], "partial")
        self.assertEqual(snapshot["signals"]["volume"]["sourceConfidence"]["freshness"], "partial")

    def test_rotation_radar_yfinance_quote_provider_reuses_history_transport(self) -> None:
        latest_date = datetime.now(timezone.utc).date()
        frame = pd.DataFrame(
            {
                "Open": [100.0, 101.0, 103.0],
                "High": [101.0, 104.0, 106.0],
                "Low": [99.0, 100.0, 102.0],
                "Close": [100.0, 103.0, 105.0],
                "Volume": [1_000_000.0, 1_200_000.0, 1_500_000.0],
            },
            index=pd.DatetimeIndex(
                [
                    (latest_date - timedelta(days=2)).isoformat(),
                    (latest_date - timedelta(days=1)).isoformat(),
                    latest_date.isoformat(),
                ]
            ),
        )
        expected_as_of = f"{latest_date.isoformat()}T00:00:00+00:00"

        with patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_missing_alpaca_credentials(),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            return_value=frame,
        ) as mock_fetch:
            payload = load_rotation_radar_quotes(["APP"])

        quote = payload["quotes"]["APP"]
        metadata = payload["metadata"]
        provenance = project_source_provenance(
            source=quote["source"],
            source_type=metadata["sourceType"],
            freshness=metadata["freshness"],
            no_external_calls=metadata["noExternalCalls"],
        )

        mock_fetch.assert_called_once_with("APP")
        self.assertEqual(metadata["quoteMode"], "proxy")
        self.assertEqual(metadata["sourceType"], "unofficial_public_api")
        self.assertFalse(metadata["noExternalCalls"])
        self.assertEqual(metadata["freshness"], "delayed")
        self.assertEqual(metadata["asOf"], expected_as_of)
        self.assertEqual(quote["source"], "yfinance_proxy")
        self.assertEqual(quote["sourceLabel"], "Yahoo Finance")
        self.assertEqual(quote["freshness"], "delayed")
        self.assertEqual(provenance["sourceType"], "unofficial_proxy")
        self.assertEqual(provenance["freshnessLabel"], "延迟")
        self.assertAlmostEqual(quote["changePercent"], 1.942, places=3)
        self.assertAlmostEqual(quote["volumeRatio"], 1.364, places=3)
        self.assertEqual(quote["timeWindows"]["1d"]["changePercent"], quote["changePercent"])
        self.assertEqual(quote["timeWindows"]["1d"]["freshness"], "delayed")

    def test_env_alpaca_credentials_are_reflected_in_configured_provider_diagnostics(self) -> None:
        class FakeAlpacaFetcher:
            def __init__(self, *, api_key_id: str, secret_key: str, data_feed: str, timeout: int = 15, **kwargs) -> None:
                self.data_feed = data_feed

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                return _alpaca_bars(end_close=102.0)

        try:
            with patch.dict(
                os.environ,
                {
                    "ALPACA_API_KEY_ID": "env-alpaca-key-id",
                    "ALPACA_API_SECRET_KEY": "env-alpaca-secret-value",
                    "ALPACA_DATA_FEED": "sip",
                },
                clear=False,
            ), patch(
                "src.services.rotation_radar_quote_provider.AlpacaFetcher",
                FakeAlpacaFetcher,
                create=True,
            ), patch(
                "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
                side_effect=AssertionError("yfinance fallback should not be called when Alpaca covers all symbols"),
            ):
                Config.reset_instance()
                payload = load_rotation_radar_quotes(["APP"])
        finally:
            Config.reset_instance()

        diagnostics = payload["metadata"]["providerDiagnostics"]
        self.assertTrue(diagnostics["credentialsPresent"])
        self.assertTrue(diagnostics["configuredProviderAttempted"])
        self.assertEqual(diagnostics["credentialFieldsMissing"], [])
        self.assertEqual(diagnostics["credentialSource"], "env")
        self.assertEqual(diagnostics["configuredProviderName"], "alpaca")
        self.assertEqual(diagnostics["feed"], "sip")
        self.assertEqual(diagnostics["feedEntitlementStatus"], "unknown")
        dumped = json.dumps(diagnostics, ensure_ascii=False)
        self.assertNotIn("env-alpaca-key-id", dumped)
        self.assertNotIn("env-alpaca-secret-value", dumped)

    def test_configured_alpaca_quote_provider_supplies_intraday_windows_without_yfinance(self) -> None:
        fetch_calls: list[tuple[str, str]] = []

        class FakeAlpacaFetcher:
            def __init__(self, *, api_key_id: str, secret_key: str, data_feed: str, timeout: int = 15, **kwargs) -> None:
                self.data_feed = data_feed

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                fetch_calls.append((symbol, timeframe))
                return _alpaca_bars(
                    start_close=100.0,
                    end_close={
                        "5Min": 101.0,
                        "15Min": 102.0,
                        "1Hour": 103.0,
                        "1Day": 104.0,
                    }[timeframe],
                )

        with patch("src.services.rotation_radar_quote_provider._UNAVAILABLE_SYMBOL_STATE", {}), patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="sip"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            FakeAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            side_effect=AssertionError("yfinance fallback should not be called when Alpaca covers all symbols"),
        ):
            payload = load_rotation_radar_quotes(["APP", "QQQ"])

        metadata = payload["metadata"]
        self.assertEqual(metadata["status"], "success")
        self.assertEqual(metadata["quoteMode"], "configured")
        self.assertEqual(metadata["source"], "alpaca")
        self.assertEqual(metadata["sourceLabel"], "Alpaca SIP")
        self.assertEqual(metadata["sourceTier"], "broker_authorized")
        self.assertEqual(metadata["providerTier"], "tier_1_configured")
        self.assertEqual(metadata["providerOrder"], ["alpaca", "yfinance"])
        self.assertEqual(metadata["coverage"]["coveragePercent"], 100.0)
        self.assertGreaterEqual(metadata["confidenceWeight"], 0.8)
        self.assertEqual(metadata["failedSymbolReasons"], {})
        self.assertTrue(metadata["sourceAuthorityAllowed"])
        self.assertTrue(metadata["scoreContributionAllowed"])
        self.assertFalse(metadata["sourceAuthorityRouteRejected"])
        self.assertIsNone(metadata["sourceAuthorityReason"])
        self.assertEqual(metadata["routeRejectedReasonCodes"], [])
        diagnostics = metadata["providerDiagnostics"]
        self.assertTrue(diagnostics["configuredProviderAttempted"])
        self.assertTrue(diagnostics["providerAttempted"])
        self.assertEqual(diagnostics["configuredProviderName"], "alpaca")
        self.assertTrue(diagnostics["credentialsPresent"])
        self.assertEqual(diagnostics["credentialFieldsMissing"], [])
        self.assertTrue(diagnostics["providerConstructed"])
        self.assertEqual(diagnostics["feedEntitlementStatus"], "unknown")
        self.assertEqual(diagnostics["requestedWindows"], ["5m", "15m", "60m", "1d"])
        self.assertEqual(diagnostics["fulfilledWindows"], ["5m", "15m", "60m", "1d"])
        self.assertEqual(diagnostics["missingWindows"], [])
        self.assertEqual(diagnostics["configuredProviderFulfilledWindows"], ["5m", "15m", "60m", "1d"])
        self.assertEqual(diagnostics["configuredProviderMissingWindows"], [])
        self.assertEqual(diagnostics["liveActivationStatus"], "active")
        self.assertIsNone(diagnostics["activationBlocker"])
        self.assertEqual(diagnostics["recommendedAction"], "none")
        self.assertEqual(
            diagnostics["activationHint"],
            "Alpaca feed active for requested 5m/15m/60m/1d windows.",
        )
        self.assertEqual(diagnostics["minimumActivationSuccessRatio"], 0.75)
        self.assertEqual(diagnostics["minimumActivationSuccessCount"], 1)
        self.assertEqual(diagnostics["activationProbeSymbolCount"], 1)
        self.assertEqual(diagnostics["diagnosticProbeSymbolCount"], 2)
        for window in ("5m", "15m", "60m", "1d"):
            result = diagnostics["requestWindowResults"][window]
            self.assertEqual(result["requestedSymbolCount"], 2)
            self.assertEqual(result["successCount"], 2)
            self.assertEqual(result["failureCount"], 0)
            self.assertEqual(result["failureClasses"], {})
            self.assertIsNone(result["dominantFailureClass"])
            self.assertEqual(result["successRatio"], 1.0)
            self.assertEqual(result["minimumRequiredSuccessRatio"], 0.75)
            self.assertEqual(result["minimumRequiredSuccessCount"], 2)
            self.assertCountEqual(result["successSymbols"], ["APP", "QQQ"])
            self.assertEqual(result["failedSymbols"], [])
            self.assertTrue(result["fulfilled"])
        self.assertEqual(diagnostics["symbolSuccessCount"], 2)
        self.assertEqual(diagnostics["symbolFailureCount"], 0)
        self.assertEqual(diagnostics["symbolFailureSamples"], [])
        self.assertEqual(diagnostics["providerFailureReasons"], [])
        self.assertFalse(diagnostics["fallbackProviderUsed"])
        self.assertFalse(diagnostics["yfinanceFallbackUsed"])
        self.assertFalse(diagnostics["fallbackYfinanceUsed"])
        self.assertFalse(diagnostics["staticBasketFallbackUsed"])
        self.assertEqual(diagnostics["finalSourceTier"], "broker_authorized")
        self.assertEqual(diagnostics["trustLevel"], "active")
        self.assertTrue(diagnostics["sourceAuthorityAllowed"])
        self.assertTrue(diagnostics["scoreContributionAllowed"])
        self.assertFalse(diagnostics["sourceAuthorityRouteRejected"])
        self.assertIsNone(diagnostics["sourceAuthorityReason"])
        self.assertEqual(diagnostics["routeRejectedReasonCodes"], [])
        self.assertEqual(diagnostics["sourceAuthorityRouter"]["request"]["useCase"], "rotation_radar")
        activation = diagnostics["alpacaActivationDiagnostics"]
        self.assertTrue(activation["credentialsPresent"])
        self.assertTrue(activation["providerConstructed"])
        self.assertTrue(activation["probePassed"])
        self.assertTrue(activation["freshnessValid"])
        self.assertTrue(activation["sourceMetadataValid"])
        self.assertTrue(activation["sourceAuthorityAllowed"])
        self.assertTrue(activation["scoreContributionAllowed"])
        self.assertIsNone(activation["reason"])
        self.assertEqual(activation["fulfilledWindows"], ["5m", "15m", "60m", "1d"])
        self.assertEqual(activation["missingWindows"], [])
        self.assertEqual(activation["staleWindows"], [])
        self.assertEqual(activation["sourceMetadataInvalidWindows"], [])
        self.assertEqual(sorted(payload["quotes"]), ["APP", "QQQ"])
        self.assertEqual(fetch_calls.count(("APP", "5Min")), 1)
        quote = payload["quotes"]["APP"]
        self.assertEqual(quote["source"], "alpaca")
        self.assertEqual(quote["sourceTier"], "broker_authorized")
        self.assertEqual(quote["providerTier"], "tier_1_configured")
        self.assertEqual(set(quote["timeWindows"]), {"5m", "15m", "60m", "1d"})
        self.assertTrue(all(window["available"] for window in quote["timeWindows"].values()))
        self.assertTrue(all(not window["isFallback"] for window in quote["timeWindows"].values()))
        self.assertTrue(all(window["source"] == "alpaca" for window in quote["timeWindows"].values()))

    def test_configured_alpaca_activation_probes_large_universe_before_budgeted_expansion(self) -> None:
        symbols = tuple(
            dict.fromkeys(
                (
                    "QQQ",
                    "SPY",
                    "IWM",
                    "IGV",
                    "SMH",
                    "APP",
                    *(f"T{i:03d}" for i in range(197)),
                )
            )
        )
        fetch_calls: list[tuple[str, str]] = []
        probe_symbols = {"QQQ", "SPY", "IWM", "IGV", "SMH", "APP"}

        class ProbeOnlyAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                fetch_calls.append((symbol, timeframe))
                if symbol not in probe_symbols:
                    time.sleep(0.05)
                return _alpaca_bars(end_close=102.0)

        with patch("src.services.rotation_radar_quote_provider._UNAVAILABLE_SYMBOL_STATE", {}), patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="sip"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            ProbeOnlyAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider._ALPACA_MAX_PROBE_SYMBOLS",
            6,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider._ALPACA_MAX_SYMBOLS_PER_WINDOW",
            10,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider._ALPACA_PER_WINDOW_TIMEOUT_SECONDS",
            0.01,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider._ALPACA_TOTAL_PROVIDER_BUDGET_SECONDS",
            0.05,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            return_value=pd.DataFrame(),
        ):
            payload = load_rotation_radar_quotes(symbols)

        diagnostics = payload["metadata"]["providerDiagnostics"]
        self.assertEqual(diagnostics["fullUniverseSymbolCount"], 203)
        self.assertEqual(diagnostics["probeSymbolCount"], 6)
        self.assertEqual(diagnostics["activationScope"], "partial_universe")
        self.assertTrue(diagnostics["providerBudgetExceeded"])
        self.assertGreater(diagnostics["skippedDueToBudgetCount"], 0)
        self.assertGreater(diagnostics["timeoutSymbolCount"], 0)
        self.assertTrue(diagnostics["minimumActivationCoverageMet"])
        self.assertEqual(diagnostics["liveActivationStatus"], "partial")
        self.assertEqual(diagnostics["fulfilledWindows"], ["5m", "15m", "60m", "1d"])
        self.assertNotEqual(diagnostics["liveActivationStatus"], "unavailable")
        activation = diagnostics["alpacaActivationDiagnostics"]
        self.assertTrue(activation["probePassed"])
        self.assertTrue(activation["sourceAuthorityAllowed"])
        self.assertTrue(activation["scoreContributionAllowed"])
        self.assertIsNone(activation["reason"])
        for window in ("5m", "15m", "60m", "1d"):
            self.assertEqual(diagnostics["requestWindowResults"][window]["successCount"], 6)
            self.assertIn("timeout", diagnostics["requestWindowResults"][window]["failureClasses"])
            self.assertTrue(diagnostics["activationWindowResults"][window]["fulfilled"])
        self.assertGreater(len({symbol for symbol, _ in fetch_calls}), 6)

    def test_configured_alpaca_probe_success_with_full_universe_timeout_stays_partial(self) -> None:
        symbols = ("QQQ", "SPY", "IWM", "APP", "PLTR", "CRM", "SNOW", "ADBE")
        probe_symbols = {"QQQ", "SPY", "IWM"}

        class SlowExpansionAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                if symbol in probe_symbols:
                    return _alpaca_bars(end_close=102.0)
                time.sleep(0.05)
                return _alpaca_bars(end_close=103.0)

        with patch("src.services.rotation_radar_quote_provider._UNAVAILABLE_SYMBOL_STATE", {}), patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="sip"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            SlowExpansionAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider._ALPACA_MAX_PROBE_SYMBOLS",
            3,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider._ALPACA_MAX_SYMBOLS_PER_WINDOW",
            8,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider._ALPACA_PER_WINDOW_TIMEOUT_SECONDS",
            0.01,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider._ALPACA_TOTAL_PROVIDER_BUDGET_SECONDS",
            0.03,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            return_value=pd.DataFrame(),
        ):
            payload = load_rotation_radar_quotes(symbols)

        diagnostics = payload["metadata"]["providerDiagnostics"]
        self.assertEqual(diagnostics["activationScope"], "partial_universe")
        self.assertEqual(diagnostics["liveActivationStatus"], "partial")
        self.assertNotEqual(diagnostics["liveActivationStatus"], "unavailable")
        self.assertTrue(diagnostics["minimumActivationCoverageMet"])
        self.assertTrue(diagnostics["providerBudgetExceeded"])
        self.assertGreaterEqual(diagnostics["timeoutSymbolCount"], 1)
        self.assertEqual(diagnostics["activationBlocker"], "timeout")
        self.assertIn("probe", diagnostics["activationHint"].lower())

    def test_configured_alpaca_probe_timeout_reports_unavailable_timeout_blocker(self) -> None:
        class TimeoutAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                time.sleep(0.05)
                return _alpaca_bars(end_close=102.0)

        with patch("src.services.rotation_radar_quote_provider._UNAVAILABLE_SYMBOL_STATE", {}), patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="sip"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            TimeoutAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider._ALPACA_MAX_PROBE_SYMBOLS",
            3,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider._ALPACA_PER_WINDOW_TIMEOUT_SECONDS",
            0.01,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider._ALPACA_TOTAL_PROVIDER_BUDGET_SECONDS",
            0.02,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            return_value=pd.DataFrame(),
        ):
            payload = load_rotation_radar_quotes(["QQQ", "SPY", "IWM", "APP"])

        diagnostics = payload["metadata"]["providerDiagnostics"]
        self.assertEqual(diagnostics["activationScope"], "probe_only")
        self.assertFalse(diagnostics["minimumActivationCoverageMet"])
        self.assertEqual(diagnostics["fulfilledWindows"], [])
        self.assertEqual(diagnostics["missingWindows"], ["5m", "15m", "60m", "1d"])
        self.assertEqual(diagnostics["activationBlocker"], "timeout")
        self.assertEqual(diagnostics["liveActivationStatus"], "unavailable")
        self.assertEqual(diagnostics["timeoutSymbolCount"], 3)

    def test_configured_alpaca_long_window_threshold_coverage_reports_partial_short_blocker(self) -> None:
        symbols = _runtime_probe_symbols()
        failed_symbols = set(symbols[9:])
        regular_session_now = _utc_dt(2026, 5, 8, 17, 30)

        class PartialWindowAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                if symbol in failed_symbols:
                    raise RuntimeError("request timeout")
                if timeframe in {"5Min", "15Min"}:
                    return []
                return _alpaca_bars(end_close=102.0)

        with patch("src.services.rotation_radar_quote_provider._UNAVAILABLE_SYMBOL_STATE", {}), patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="iex"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            PartialWindowAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider._utc_now",
            return_value=regular_session_now,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            return_value=pd.DataFrame(),
        ):
            payload = load_rotation_radar_quotes(symbols)

        metadata = payload["metadata"]
        diagnostics = metadata["providerDiagnostics"]
        self.assertEqual(diagnostics["liveActivationStatus"], "partial")
        self.assertNotEqual(diagnostics["liveActivationStatus"], "active")
        self.assertEqual(diagnostics["fulfilledWindows"], ["60m", "1d"])
        self.assertEqual(diagnostics["missingWindows"], ["5m", "15m"])
        self.assertEqual(diagnostics["configuredProviderFulfilledWindows"], ["60m", "1d"])
        self.assertEqual(diagnostics["configuredProviderMissingWindows"], ["5m", "15m"])
        self.assertEqual(diagnostics["activationBlocker"], "feed_intraday_empty")
        self.assertIn("5m/15m", diagnostics["activationHint"])
        self.assertEqual(diagnostics["minimumActivationCoverageMet"], True)
        self.assertEqual(diagnostics["minimumActivationSuccessRatio"], 0.75)
        self.assertEqual(diagnostics["minimumActivationSuccessCount"], 4)
        self.assertTrue(diagnostics["yfinanceFallbackUsed"])
        self.assertEqual(metadata["windowCoverage"]["5m"]["usableSymbolCount"], 0)
        self.assertEqual(metadata["windowCoverage"]["60m"]["usableSymbolCount"], 9)
        for window in ("5m", "15m"):
            result = diagnostics["requestWindowResults"][window]
            self.assertEqual(result["requestedSymbolCount"], 12)
            self.assertEqual(result["successCount"], 0)
            self.assertEqual(result["failureClasses"], {"empty_response": 9, "timeout": 3})
            self.assertEqual(result["successRatio"], 0.0)
            self.assertEqual(result["minimumRequiredSuccessRatio"], 0.75)
            self.assertEqual(result["minimumRequiredSuccessCount"], 9)
            self.assertFalse(result["fulfilled"])
            self.assertEqual(result["successSymbols"], [])
            self.assertLessEqual(len(result["failedSymbols"]), 8)
            self.assertEqual(len(diagnostics["failedSymbolsByWindow"][window]), 8)
        for window in ("60m", "1d"):
            result = diagnostics["requestWindowResults"][window]
            self.assertEqual(result["requestedSymbolCount"], 12)
            self.assertEqual(result["successCount"], 9)
            self.assertEqual(result["failureClasses"], {"timeout": 3})
            self.assertEqual(result["successRatio"], 0.75)
            self.assertEqual(result["minimumRequiredSuccessRatio"], 0.75)
            self.assertEqual(result["minimumRequiredSuccessCount"], 9)
            self.assertTrue(result["fulfilled"])
            self.assertLessEqual(len(result["successSymbols"]), 8)
            self.assertEqual(len(diagnostics["successSymbolsByWindow"][window]), 8)

    def test_configured_alpaca_all_windows_empty_reports_unavailable_activation(self) -> None:
        class EmptyAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                return []

        with patch("src.services.rotation_radar_quote_provider._UNAVAILABLE_SYMBOL_STATE", {}), patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="iex"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            EmptyAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            return_value=pd.DataFrame(),
        ):
            payload = load_rotation_radar_quotes(_runtime_probe_symbols())

        diagnostics = payload["metadata"]["providerDiagnostics"]
        self.assertEqual(diagnostics["liveActivationStatus"], "unavailable")
        self.assertEqual(diagnostics["fulfilledWindows"], [])
        self.assertEqual(diagnostics["missingWindows"], ["5m", "15m", "60m", "1d"])
        self.assertEqual(diagnostics["minimumActivationSuccessRatio"], 0.75)
        self.assertEqual(diagnostics["minimumActivationSuccessCount"], 4)
        for window in ("5m", "15m", "60m", "1d"):
            result = diagnostics["requestWindowResults"][window]
            self.assertEqual(result["requestedSymbolCount"], 12)
            self.assertEqual(result["successCount"], 0)
            self.assertEqual(result["successRatio"], 0.0)
            self.assertEqual(result["minimumRequiredSuccessCount"], 9)
            self.assertFalse(result["fulfilled"])

    def test_configured_alpaca_observed_data_below_activation_threshold_is_not_coverage_met(self) -> None:
        symbols = ("QQQ", "SPY", "IWM", "SMH", "SOXX", "IGV")
        successful_long_window_symbols = {"QQQ", "SPY"}

        class SparseLongWindowAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                if symbol in successful_long_window_symbols and timeframe in {"1Hour", "1Day"}:
                    return _alpaca_bars(end_close=102.0)
                return []

        with patch("src.services.rotation_radar_quote_provider._UNAVAILABLE_SYMBOL_STATE", {}), patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="iex"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            SparseLongWindowAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            return_value=pd.DataFrame(),
        ):
            payload = load_rotation_radar_quotes(symbols)

        diagnostics = payload["metadata"]["providerDiagnostics"]
        self.assertTrue(diagnostics["anyConfiguredProviderDataAvailable"])
        self.assertFalse(diagnostics["configuredProviderWindowCoverageMet"])
        self.assertFalse(diagnostics["partialActivationEligible"])
        self.assertFalse(diagnostics["minimumActivationCoverageMet"])
        self.assertEqual(diagnostics["configuredProviderFulfilledWindows"], [])
        self.assertEqual(diagnostics["configuredProviderMissingWindows"], ["5m", "15m", "60m", "1d"])
        self.assertEqual(diagnostics["liveActivationStatus"], "unavailable")
        self.assertEqual(diagnostics["activationWindowResults"]["60m"]["successCount"], 2)
        self.assertFalse(diagnostics["activationWindowResults"]["60m"]["fulfilled"])

    def test_configured_alpaca_activation_uses_stable_probe_and_reports_long_tail_failures(self) -> None:
        symbols = (
            "QQQ",
            "SPY",
            "IWM",
            "SMH",
            "SOXX",
            "IGV",
            "CLOU",
            "CIBR",
            "HACK",
            "BLOK",
            "BITQ",
            "BITO",
        )
        stable_symbols = {"QQQ", "SPY", "IWM", "SMH", "SOXX", "IGV"}
        timed_out_symbols = {"CLOU", "CIBR", "HACK"}
        regular_session_now = _utc_dt(2026, 5, 8, 17, 30)

        class MixedCoverageAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                if symbol in stable_symbols and timeframe in {"1Hour", "1Day"}:
                    return _alpaca_bars(end_close=102.0)
                if symbol in timed_out_symbols:
                    raise RuntimeError("request timeout")
                return []

        with patch("src.services.rotation_radar_quote_provider._UNAVAILABLE_SYMBOL_STATE", {}), patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="iex"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            MixedCoverageAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider._utc_now",
            return_value=regular_session_now,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            return_value=pd.DataFrame(),
        ):
            payload = load_rotation_radar_quotes(symbols)

        diagnostics = payload["metadata"]["providerDiagnostics"]
        self.assertEqual(diagnostics["activationProbeSymbolCount"], 6)
        self.assertEqual(diagnostics["diagnosticProbeSymbolCount"], 12)
        self.assertEqual(diagnostics["stableActivationProbeSymbols"], ["SPY", "QQQ", "IWM", "SMH", "SOXX", "IGV"])
        self.assertEqual(diagnostics["longTailProbeSymbols"], ["CLOU", "CIBR", "HACK", "BLOK", "BITQ", "BITO"])
        self.assertTrue(diagnostics["anyConfiguredProviderDataAvailable"])
        self.assertTrue(diagnostics["configuredProviderWindowCoverageMet"])
        self.assertTrue(diagnostics["partialActivationEligible"])
        self.assertTrue(diagnostics["minimumActivationCoverageMet"])
        self.assertEqual(diagnostics["configuredProviderFulfilledWindows"], ["60m", "1d"])
        self.assertEqual(diagnostics["configuredProviderMissingWindows"], ["5m", "15m"])
        self.assertEqual(diagnostics["liveActivationStatus"], "partial")
        self.assertEqual(diagnostics["activationBlocker"], "feed_intraday_empty")
        self.assertEqual(diagnostics["activationWindowResults"]["60m"]["requestedSymbolCount"], 6)
        self.assertEqual(diagnostics["activationWindowResults"]["60m"]["successCount"], 6)
        self.assertTrue(diagnostics["activationWindowResults"]["60m"]["fulfilled"])
        self.assertEqual(diagnostics["requestWindowResults"]["60m"]["requestedSymbolCount"], 12)
        self.assertEqual(diagnostics["requestWindowResults"]["60m"]["successCount"], 6)
        self.assertFalse(diagnostics["requestWindowResults"]["60m"]["fulfilled"])
        self.assertCountEqual(diagnostics["requestWindowResults"]["60m"]["timedOutSymbols"], ["CLOU", "CIBR", "HACK"])
        self.assertCountEqual(diagnostics["requestWindowResults"]["60m"]["emptyResponseSymbols"], ["BLOK", "BITQ", "BITO"])
        self.assertCountEqual(diagnostics["timedOutSymbolsByWindow"]["60m"], ["CLOU", "CIBR", "HACK"])
        self.assertCountEqual(diagnostics["emptyResponseSymbolsByWindow"]["60m"], ["BLOK", "BITQ", "BITO"])

    def test_configured_alpaca_full_window_coverage_reports_active_activation(self) -> None:
        class FullCoverageAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                return _alpaca_bars(end_close=102.0)

        with patch("src.services.rotation_radar_quote_provider._UNAVAILABLE_SYMBOL_STATE", {}), patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="sip"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            FullCoverageAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            side_effect=AssertionError("yfinance fallback should not satisfy configured Alpaca windows"),
        ):
            payload = load_rotation_radar_quotes(_runtime_probe_symbols())

        diagnostics = payload["metadata"]["providerDiagnostics"]
        self.assertEqual(diagnostics["liveActivationStatus"], "active")
        self.assertEqual(diagnostics["fulfilledWindows"], ["5m", "15m", "60m", "1d"])
        self.assertEqual(diagnostics["missingWindows"], [])
        self.assertEqual(diagnostics["minimumActivationSuccessRatio"], 0.75)
        self.assertEqual(diagnostics["minimumActivationSuccessCount"], 4)
        for window in ("5m", "15m", "60m", "1d"):
            result = diagnostics["requestWindowResults"][window]
            self.assertEqual(result["requestedSymbolCount"], 12)
            self.assertEqual(result["successCount"], 12)
            self.assertEqual(result["successRatio"], 1.0)
            self.assertEqual(result["minimumRequiredSuccessCount"], 9)
            self.assertTrue(result["fulfilled"])

    def test_yfinance_fallback_does_not_fulfill_configured_alpaca_windows(self) -> None:
        class EmptyAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                return []

        with patch("src.services.rotation_radar_quote_provider._UNAVAILABLE_SYMBOL_STATE", {}), patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="sip"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            EmptyAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            return_value=_yfinance_frame(),
        ):
            payload = load_rotation_radar_quotes(["APP", "QQQ"])

        diagnostics = payload["metadata"]["providerDiagnostics"]
        self.assertEqual(sorted(payload["quotes"]), ["APP", "QQQ"])
        self.assertEqual(payload["quotes"]["APP"]["source"], "yfinance_proxy")
        self.assertTrue(diagnostics["yfinanceFallbackUsed"])
        self.assertEqual(diagnostics["fulfilledWindows"], [])
        self.assertEqual(diagnostics["configuredProviderFulfilledWindows"], [])
        self.assertEqual(diagnostics["missingWindows"], ["5m", "15m", "60m", "1d"])
        for window in ("5m", "15m", "60m", "1d"):
            self.assertFalse(diagnostics["requestWindowResults"][window]["fulfilled"])

    def test_missing_alpaca_credentials_report_required_env_names(self) -> None:
        with patch.object(
            Config,
            "_instance",
            Config(alpaca_api_key_id=None, alpaca_api_secret_key=None, alpaca_data_feed="iex"),
        ), patch.dict(
            os.environ,
            {"ALPACA_API_KEY_ID": "", "ALPACA_API_SECRET_KEY": "", "ALPACA_DATA_FEED": "iex"},
            clear=False,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            side_effect=AssertionError("Alpaca should not be constructed without credentials"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            return_value=_yfinance_frame(),
        ):
            payload = load_rotation_radar_quotes(["APP"])

        diagnostics = payload["metadata"]["providerDiagnostics"]
        self.assertFalse(diagnostics["credentialsPresent"])
        self.assertEqual(
            diagnostics["credentialFieldsMissing"],
            ["ALPACA_API_KEY_ID", "ALPACA_API_SECRET_KEY"],
        )
        self.assertEqual(diagnostics["credentialSource"], "unavailable")
        self.assertEqual(diagnostics["providerFailureReason"], "credentials_missing")

    def test_partial_alpaca_credentials_report_missing_required_env_name(self) -> None:
        with patch.object(
            Config,
            "_instance",
            Config(alpaca_api_key_id="configured-key-id", alpaca_api_secret_key=None, alpaca_data_feed="iex"),
        ), patch.dict(
            os.environ,
            {"ALPACA_API_KEY_ID": "", "ALPACA_API_SECRET_KEY": "", "ALPACA_DATA_FEED": "iex"},
            clear=False,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            side_effect=AssertionError("Alpaca should not be constructed with partial credentials"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            return_value=_yfinance_frame(),
        ):
            payload = load_rotation_radar_quotes(["APP"])

        diagnostics = payload["metadata"]["providerDiagnostics"]
        self.assertFalse(diagnostics["credentialsPresent"])
        self.assertEqual(diagnostics["credentialFieldsMissing"], ["ALPACA_API_SECRET_KEY"])
        self.assertEqual(diagnostics["credentialSource"], "config")
        self.assertEqual(diagnostics["providerFailureReason"], "credential_fields_missing")

    def test_missing_alpaca_credentials_skips_configured_provider_and_keeps_yfinance_degraded(self) -> None:
        with patch("src.services.rotation_radar_quote_provider._UNAVAILABLE_SYMBOL_STATE", {}), patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_missing_alpaca_credentials(),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            side_effect=AssertionError("Alpaca should not be constructed without credentials"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider._QUOTE_PROVIDER_REQUEST_TIMEOUT_SECONDS",
            0.25,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            return_value=_yfinance_frame(),
        ) as mock_yfinance:
            payload = load_rotation_radar_quotes(["APP"])

        quote = payload["quotes"]["APP"]
        metadata = payload["metadata"]
        mock_yfinance.assert_called_once_with("APP")
        self.assertEqual(metadata["configuredProviderStatus"], "not_configured")
        self.assertEqual(metadata["quoteMode"], "proxy")
        self.assertEqual(metadata["source"], "yfinance_proxy")
        self.assertEqual(metadata["sourceLabel"], "Yahoo Finance")
        self.assertEqual(metadata["sourceTier"], "unofficial_public_api")
        self.assertEqual(metadata["providerTier"], "tier_2_delayed_proxy")
        self.assertEqual(metadata["providerOrder"], ["alpaca", "yfinance"])
        self.assertEqual(metadata["providerTimeoutSeconds"], 0.25)
        self.assertLessEqual(metadata["confidenceWeight"], 0.5)
        diagnostics = metadata["providerDiagnostics"]
        self.assertTrue(diagnostics["configuredProviderAttempted"])
        self.assertEqual(diagnostics["configuredProviderName"], "alpaca")
        self.assertFalse(diagnostics["credentialsPresent"])
        self.assertEqual(diagnostics["credentialFieldsMissing"], ["ALPACA_API_KEY_ID", "ALPACA_API_SECRET_KEY"])
        self.assertFalse(diagnostics["providerConstructed"])
        self.assertEqual(diagnostics["providerFailureReason"], "credentials_missing")
        self.assertEqual(diagnostics["providerFailureReasons"], ["credentials_missing"])
        self.assertTrue(diagnostics["fallbackProviderUsed"])
        self.assertTrue(diagnostics["yfinanceFallbackUsed"])
        self.assertFalse(diagnostics["staticBasketFallbackUsed"])
        self.assertEqual(diagnostics["finalSourceTier"], "unofficial_public_api")
        self.assertEqual(diagnostics["trustLevel"], "degraded")
        activation = diagnostics["alpacaActivationDiagnostics"]
        self.assertFalse(activation["sourceAuthorityAllowed"])
        self.assertFalse(activation["scoreContributionAllowed"])
        self.assertEqual(activation["reason"], "credentials")
        self.assertFalse(metadata["sourceAuthorityAllowed"])
        self.assertFalse(metadata["scoreContributionAllowed"])
        self.assertEqual(metadata["sourceAuthorityReason"], "source_authority_router_rejected")
        self.assertEqual(metadata["routeRejectedReasonCodes"], diagnostics["routeRejectedReasonCodes"])
        self.assertIn("provider_forbidden_for_use_case", metadata["routeRejectedReasonCodes"])
        self.assertIn("score_inputs", metadata["routeRejectedReasonCodes"])
        self.assertIn("provider_not_capable", metadata["routeRejectedReasonCodes"])
        self.assertFalse(diagnostics["sourceAuthorityAllowed"])
        self.assertFalse(diagnostics["scoreContributionAllowed"])
        self.assertEqual(diagnostics["sourceAuthorityReason"], "source_authority_router_rejected")
        self.assertEqual(diagnostics["routeRejectedReasonCodes"], metadata["routeRejectedReasonCodes"])
        assert diagnostics["sourceAuthorityRouter"]["diagnosticOnly"] is True
        assert diagnostics["sourceAuthorityRouter"]["providerRuntimeCalled"] is False
        assert diagnostics["sourceAuthorityRouter"]["networkCallsEnabled"] is False
        assert diagnostics["sourceAuthorityRouter"]["request"] == {
            "market": "US",
            "assetType": "equity",
            "useCase": "rotation_radar",
            "capability": "quote",
            "freshnessNeed": "live",
            "scoringAllowed": True,
            "symbol": None,
            "productId": None,
            "cik": None,
            "asOf": None,
            "allowNetwork": False,
            "reproducibilityRequired": False,
        }
        assert "yfinance_current_baseline" in {
            item["providerId"] for item in diagnostics["sourceAuthorityRouter"]["forbiddenProviders"]
        }
        self.assertEqual(set(quote["timeWindows"]), {"1d"})
        self.assertEqual(quote["freshness"], "delayed")
        self.assertEqual(quote["sourceTier"], "unofficial_public_api")
        self.assertEqual(quote["providerTier"], "tier_2_delayed_proxy")
        self.assertNotIn("5m", quote["timeWindows"])
        self.assertNotIn(metadata["freshness"], {"live", "fresh"})

    def test_partial_alpaca_credentials_report_missing_field_without_constructing_provider(self) -> None:
        with patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_partial_alpaca_credentials(),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            side_effect=AssertionError("Alpaca should not be constructed with partial credentials"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            return_value=_yfinance_frame(),
        ):
            payload = load_rotation_radar_quotes(["APP"])

        diagnostics = payload["metadata"]["providerDiagnostics"]
        self.assertEqual(payload["metadata"]["configuredProviderStatus"], "incomplete_credentials")
        self.assertTrue(diagnostics["configuredProviderAttempted"])
        self.assertEqual(diagnostics["configuredProviderName"], "alpaca")
        self.assertFalse(diagnostics["credentialsPresent"])
        self.assertEqual(diagnostics["credentialFieldsMissing"], ["ALPACA_API_SECRET_KEY"])
        self.assertFalse(diagnostics["providerConstructed"])
        self.assertEqual(diagnostics["providerFailureReason"], "credential_fields_missing")
        self.assertEqual(diagnostics["providerFailureReasons"], ["credential_fields_missing"])
        self.assertTrue(diagnostics["fallbackProviderUsed"])
        self.assertTrue(diagnostics["yfinanceFallbackUsed"])
        self.assertFalse(diagnostics["staticBasketFallbackUsed"])
        self.assertEqual(diagnostics["finalSourceTier"], "unofficial_public_api")
        self.assertEqual(diagnostics["trustLevel"], "degraded")

    def test_configured_provider_constructor_failure_is_diagnosed_without_secret_leak(self) -> None:
        class FailingAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                raise RuntimeError("bad secret value SHOULD_NOT_LEAK")

        with patch("src.services.rotation_radar_quote_provider._UNAVAILABLE_SYMBOL_STATE", {}), patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="sip"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            FailingAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            return_value=_yfinance_frame(),
        ):
            payload = load_rotation_radar_quotes(["APP"])

        diagnostics = payload["metadata"]["providerDiagnostics"]
        self.assertEqual(payload["metadata"]["quoteMode"], "proxy")
        self.assertFalse(diagnostics["providerConstructed"])
        self.assertEqual(diagnostics["providerFailureReason"], "provider_unavailable")
        self.assertEqual(diagnostics["providerFailureReasons"], ["provider_unavailable"])
        self.assertTrue(diagnostics["fallbackProviderUsed"])
        self.assertTrue(diagnostics["yfinanceFallbackUsed"])
        self.assertEqual(diagnostics["finalSourceTier"], "unofficial_public_api")
        self.assertEqual(diagnostics["trustLevel"], "degraded")
        dumped = json.dumps(diagnostics, ensure_ascii=False)
        self.assertNotIn("SHOULD_NOT_LEAK", dumped)
        self.assertNotIn("alpaca-secret", dumped)

    def test_quote_provider_timeout_preserves_sanitized_credential_diagnostics(self) -> None:
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

        service = MarketRotationRadarService(
            quote_provider=provider,
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        with patch("src.services.market_rotation_radar_service._QUOTE_PROVIDER_TIMEOUT_SECONDS", 0.001):
            payload = service.get_rotation_radar()

        diagnostics = payload["metadata"]["quoteProvider"]["providerDiagnostics"]
        self.assertTrue(diagnostics["configuredProviderAttempted"])
        self.assertTrue(diagnostics["credentialsPresent"])
        self.assertEqual(diagnostics["credentialFieldsMissing"], [])
        self.assertEqual(diagnostics["credentialSource"], "env")
        self.assertEqual(diagnostics["feed"], "iex")
        self.assertFalse(diagnostics["providerConstructed"])
        self.assertEqual(diagnostics["providerFailureReason"], "quote_fetch_failed")
        self.assertEqual(diagnostics["providerFailureReasons"], ["quote_fetch_failed"])
        self.assertEqual(diagnostics["finalSourceTier"], "fallback_static")
        self.assertEqual(diagnostics["trustLevel"], "unavailable")

    def test_configured_provider_partial_windows_cap_activation_trust(self) -> None:
        class DailyOnlyAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                if timeframe != "1Day":
                    raise RuntimeError("subscription required")
                return _alpaca_bars(end_close=102.0)

        with patch("src.services.rotation_radar_quote_provider._UNAVAILABLE_SYMBOL_STATE", {}), patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="sip"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            DailyOnlyAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            side_effect=AssertionError("yfinance fallback should not be called when Alpaca returns quotes"),
        ):
            payload = load_rotation_radar_quotes(["APP", "QQQ"])

        metadata = payload["metadata"]
        diagnostics = metadata["providerDiagnostics"]
        self.assertEqual(metadata["quoteMode"], "configured")
        self.assertEqual(metadata["windowCoverage"]["1d"]["coveragePercent"], 100.0)
        self.assertEqual(metadata["windowCoverage"]["5m"]["usableSymbolCount"], 0)
        self.assertEqual(diagnostics["fulfilledWindows"], ["1d"])
        self.assertEqual(diagnostics["missingWindows"], ["5m", "15m", "60m"])
        self.assertEqual(diagnostics["configuredProviderFulfilledWindows"], ["1d"])
        self.assertEqual(diagnostics["configuredProviderMissingWindows"], ["5m", "15m", "60m"])
        self.assertEqual(diagnostics["liveActivationStatus"], "partial")
        self.assertEqual(diagnostics["activationBlocker"], "entitlement")
        self.assertTrue(diagnostics["providerConstructed"])
        self.assertEqual(diagnostics["feedEntitlementStatus"], "entitlement_denied")
        self.assertEqual(diagnostics["recommendedAction"], "enable_feed_entitlement_or_switch_feed")
        self.assertEqual(
            diagnostics["activationHint"],
            "Alpaca provider is active but missing 5m/15m/60m windows: entitlement_denied.",
        )
        self.assertEqual(diagnostics["requestWindowResults"]["5m"]["failureClasses"], {"entitlement_denied": 2})
        self.assertEqual(diagnostics["requestWindowResults"]["15m"]["failureClasses"], {"entitlement_denied": 2})
        self.assertEqual(diagnostics["requestWindowResults"]["60m"]["failureClasses"], {"entitlement_denied": 2})
        self.assertEqual(diagnostics["requestWindowResults"]["1d"]["successCount"], 2)
        self.assertEqual(diagnostics["requestWindowResults"]["1d"]["failureCount"], 0)
        self.assertEqual(diagnostics["symbolSuccessCount"], 2)
        self.assertEqual(diagnostics["symbolFailureCount"], 0)
        self.assertEqual(diagnostics["providerFailureReasons"], ["entitlement_denied"])
        self.assertFalse(diagnostics["fallbackProviderUsed"])
        self.assertFalse(diagnostics["yfinanceFallbackUsed"])
        self.assertFalse(diagnostics["fallbackYfinanceUsed"])
        self.assertEqual(diagnostics["finalSourceTier"], "broker_authorized")
        self.assertEqual(diagnostics["trustLevel"], "partial")
        activation = diagnostics["alpacaActivationDiagnostics"]
        self.assertFalse(activation["probePassed"])
        self.assertTrue(activation["freshnessValid"])
        self.assertTrue(activation["sourceMetadataValid"])
        self.assertFalse(activation["sourceAuthorityAllowed"])
        self.assertFalse(activation["scoreContributionAllowed"])
        self.assertEqual(activation["reason"], "entitlement")

    def test_alpaca_short_intraday_requests_use_recent_completed_regular_session_outside_market_hours(self) -> None:
        request_calls: list[dict[str, str]] = []
        outside_market_now = _utc_dt(2026, 5, 9, 15, 0)

        class RecordingAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                request_calls.append({
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "start": start,
                    "end": end,
                })
                return _alpaca_bars(end_close=102.0)

        with patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="sip"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            RecordingAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider._utc_now",
            return_value=outside_market_now,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            side_effect=AssertionError("yfinance fallback should not be called when Alpaca covers all symbols"),
        ):
            load_rotation_radar_quotes(["SPY"])

        request_by_timeframe = {entry["timeframe"]: entry for entry in request_calls}
        self.assertEqual(
            request_by_timeframe["5Min"],
            {
                "symbol": "SPY",
                "timeframe": "5Min",
                "start": "2026-05-08T18:00:00+00:00",
                "end": "2026-05-08T20:00:00+00:00",
            },
        )
        self.assertEqual(
            request_by_timeframe["15Min"],
            {
                "symbol": "SPY",
                "timeframe": "15Min",
                "start": "2026-05-08T14:00:00+00:00",
                "end": "2026-05-08T20:00:00+00:00",
            },
        )
        self.assertEqual(request_by_timeframe["1Hour"]["end"], outside_market_now.isoformat())
        self.assertEqual(request_by_timeframe["1Day"]["end"], outside_market_now.isoformat())

    def test_configured_provider_auth_failure_reports_actionable_window_diagnostics_without_secret_leak(self) -> None:
        class AuthFailingAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                raise RuntimeError("401 unauthorized invalid alpaca-secret SHOULD_NOT_LEAK")

        with patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="sip"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            AuthFailingAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            return_value=_yfinance_frame(),
        ):
            payload = load_rotation_radar_quotes(["APP"])

        metadata = payload["metadata"]
        diagnostics = metadata["providerDiagnostics"]
        self.assertEqual(metadata["quoteMode"], "proxy")
        self.assertEqual(payload["quotes"]["APP"]["source"], "yfinance_proxy")
        self.assertTrue(diagnostics["credentialsPresent"])
        self.assertTrue(diagnostics["providerConstructed"])
        self.assertEqual(diagnostics["fulfilledWindows"], [])
        self.assertEqual(diagnostics["missingWindows"], ["5m", "15m", "60m", "1d"])
        self.assertEqual(diagnostics["configuredProviderFulfilledWindows"], [])
        self.assertEqual(diagnostics["configuredProviderMissingWindows"], ["5m", "15m", "60m", "1d"])
        self.assertEqual(diagnostics["liveActivationStatus"], "unavailable")
        self.assertEqual(diagnostics["activationBlocker"], "auth")
        self.assertEqual(diagnostics["providerFailureReason"], "auth_failed")
        self.assertEqual(diagnostics["providerFailureReasons"], ["auth_failed"])
        self.assertEqual(diagnostics["feedEntitlementStatus"], "auth_failed")
        self.assertEqual(diagnostics["recommendedAction"], "verify_alpaca_credentials")
        self.assertEqual(
            diagnostics["activationHint"],
            "Alpaca credentials are present and the provider was constructed, but no configured windows were fulfilled: auth_failed.",
        )
        self.assertTrue(diagnostics["fallbackProviderUsed"])
        self.assertTrue(diagnostics["yfinanceFallbackUsed"])
        self.assertTrue(diagnostics["fallbackYfinanceUsed"])
        self.assertEqual(diagnostics["trustLevel"], "degraded")
        for window in ("5m", "15m", "60m", "1d"):
            result = diagnostics["requestWindowResults"][window]
            self.assertEqual(result["requestedSymbolCount"], 1)
            self.assertEqual(result["successCount"], 0)
            self.assertEqual(result["failureCount"], 1)
            self.assertEqual(result["failureClasses"], {"auth_failed": 1})
            self.assertEqual(result["dominantFailureClass"], "auth_failed")
            self.assertEqual(result["successRatio"], 0.0)
            self.assertEqual(result["minimumRequiredSuccessRatio"], 0.75)
            self.assertEqual(result["minimumRequiredSuccessCount"], 1)
            self.assertEqual(result["successSymbols"], [])
            self.assertEqual(result["failedSymbols"], ["APP"])
            self.assertFalse(result["fulfilled"])
        self.assertEqual(len(diagnostics["symbolFailureSamples"]), 4)
        self.assertEqual(diagnostics["symbolFailureSamples"][0]["failureClass"], "auth_failed")
        dumped = json.dumps(diagnostics, ensure_ascii=False)
        self.assertNotIn("SHOULD_NOT_LEAK", dumped)
        self.assertNotIn("alpaca-secret", dumped)
        self.assertNotIn("alpaca-key-id", dumped)

    def test_configured_provider_empty_all_windows_reports_empty_response_and_missing_windows(self) -> None:
        class EmptyAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                return []

        with patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="sip"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            EmptyAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            return_value=_yfinance_frame(),
        ):
            payload = load_rotation_radar_quotes(["APP", "QQQ"])

        metadata = payload["metadata"]
        diagnostics = metadata["providerDiagnostics"]
        self.assertEqual(metadata["quoteMode"], "proxy")
        self.assertEqual(sorted(payload["quotes"]), ["APP", "QQQ"])
        self.assertTrue(diagnostics["credentialsPresent"])
        self.assertTrue(diagnostics["providerConstructed"])
        self.assertEqual(diagnostics["fulfilledWindows"], [])
        self.assertEqual(diagnostics["missingWindows"], ["5m", "15m", "60m", "1d"])
        self.assertEqual(diagnostics["configuredProviderFulfilledWindows"], [])
        self.assertEqual(diagnostics["configuredProviderMissingWindows"], ["5m", "15m", "60m", "1d"])
        self.assertEqual(diagnostics["liveActivationStatus"], "unavailable")
        self.assertEqual(diagnostics["activationBlocker"], "empty_response")
        self.assertEqual(diagnostics["providerFailureReason"], "empty_response")
        self.assertEqual(diagnostics["providerFailureReasons"], ["empty_response"])
        self.assertEqual(diagnostics["recommendedAction"], "verify_symbol_coverage")
        self.assertEqual(
            diagnostics["activationHint"],
            "Alpaca credentials are present and the provider was constructed, but no configured windows were fulfilled: empty_response.",
        )
        activation = diagnostics["alpacaActivationDiagnostics"]
        self.assertFalse(activation["sourceAuthorityAllowed"])
        self.assertFalse(activation["scoreContributionAllowed"])
        self.assertEqual(activation["reason"], "empty_response")
        for window in ("5m", "15m", "60m", "1d"):
            self.assertEqual(diagnostics["requestWindowResults"][window]["requestedSymbolCount"], 2)
            self.assertEqual(diagnostics["requestWindowResults"][window]["successCount"], 0)
            self.assertEqual(diagnostics["requestWindowResults"][window]["failureCount"], 2)
            self.assertEqual(diagnostics["requestWindowResults"][window]["failureClasses"], {"empty_response": 2})
            self.assertFalse(diagnostics["requestWindowResults"][window]["fulfilled"])
        self.assertLessEqual(len(diagnostics["symbolFailureSamples"]), 8)
        self.assertTrue(diagnostics["fallbackYfinanceUsed"])

    def test_configured_provider_interval_mapping_failure_is_first_class_activation_blocker(self) -> None:
        class UnsupportedIntervalAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                raise RuntimeError(f"unsupported timeframe {timeframe}")

        with patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="iex"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            UnsupportedIntervalAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            return_value=_yfinance_frame(),
        ):
            payload = load_rotation_radar_quotes(["APP"])

        diagnostics = payload["metadata"]["providerDiagnostics"]
        self.assertEqual(diagnostics["fulfilledWindows"], [])
        self.assertEqual(diagnostics["configuredProviderFulfilledWindows"], [])
        self.assertEqual(diagnostics["configuredProviderMissingWindows"], ["5m", "15m", "60m", "1d"])
        self.assertEqual(diagnostics["liveActivationStatus"], "unavailable")
        self.assertEqual(diagnostics["activationBlocker"], "interval_mapping")
        self.assertEqual(diagnostics["providerFailureReason"], "interval_mapping")
        self.assertEqual(diagnostics["providerFailureReasons"], ["interval_mapping"])
        self.assertTrue(diagnostics["fallbackYfinanceUsed"])
        for window in ("5m", "15m", "60m", "1d"):
            self.assertEqual(diagnostics["requestWindowResults"][window]["failureClasses"], {"interval_mapping": 1})
            self.assertEqual(diagnostics["requestWindowResults"][window]["dominantFailureClass"], "interval_mapping")

    def test_configured_provider_stale_activation_probe_blocks_diagnostic_authority(self) -> None:
        stale_as_of = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()

        class StaleAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                return _alpaca_bars(end_close=102.0, as_of=stale_as_of)

        with patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="sip"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            StaleAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            side_effect=AssertionError("yfinance fallback should not be called when Alpaca covers all symbols"),
        ):
            payload = load_rotation_radar_quotes(["QQQ", "SPY", "IWM", "SMH", "SOXX", "IGV"])

        diagnostics = payload["metadata"]["providerDiagnostics"]
        activation = diagnostics["alpacaActivationDiagnostics"]
        self.assertEqual(diagnostics["liveActivationStatus"], "active")
        self.assertTrue(activation["probePassed"])
        self.assertFalse(activation["freshnessValid"])
        self.assertTrue(activation["sourceMetadataValid"])
        self.assertFalse(activation["sourceAuthorityAllowed"])
        self.assertFalse(activation["scoreContributionAllowed"])
        self.assertEqual(activation["reason"], "stale_window")
        self.assertEqual(activation["staleWindows"], ["5m", "15m", "60m", "1d"])

    def test_alpaca_live_smoke_short_windows_outside_market_hours_report_market_closed_window_empty(self) -> None:
        outside_market_now = _utc_dt(2026, 5, 9, 15, 0)

        class OutsideHoursShortWindowFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                if timeframe in {"5Min", "15Min"}:
                    return []
                return _alpaca_bars(end_close=102.0)

        with patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="sip"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            OutsideHoursShortWindowFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider._utc_now",
            return_value=outside_market_now,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            side_effect=AssertionError("live smoke must stay on the bounded Alpaca configured path"),
        ):
            summary = run_rotation_radar_alpaca_live_smoke()

        self.assertTrue(summary["credentialsPresent"])
        self.assertTrue(summary["providerConstructed"])
        self.assertFalse(summary["probePassed"])
        self.assertFalse(summary["sourceAuthorityAllowed"])
        self.assertFalse(summary["scoreContributionAllowed"])
        self.assertEqual(summary["fulfilledWindows"], ["60m", "1d"])
        self.assertEqual(summary["missingWindows"], ["5m", "15m"])
        self.assertEqual(summary["staleWindows"], [])
        self.assertEqual(summary["reason"], "market_closed_window_empty")

    def test_alpaca_live_smoke_missing_credentials_exits_cleanly_without_secret_output(self) -> None:
        with patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_missing_alpaca_credentials(),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            side_effect=AssertionError("live smoke must not call yfinance when credentials are missing"),
        ):
            summary = run_rotation_radar_alpaca_live_smoke()

        self.assertEqual(
            summary,
            {
                "credentialsPresent": False,
                "providerConstructed": False,
                "probePassed": False,
                "freshnessValid": True,
                "sourceMetadataValid": True,
                "sourceAuthorityAllowed": False,
                "scoreContributionAllowed": False,
                "fulfilledWindows": [],
                "missingWindows": ["5m", "15m", "60m", "1d"],
                "staleWindows": [],
                "reason": "credentials",
            },
        )
        dumped = json.dumps(summary, ensure_ascii=False)
        self.assertNotIn("alpaca-secret", dumped)
        self.assertNotIn("alpaca-key-id", dumped)
        self.assertNotIn("ALPACA_API_SECRET_KEY", dumped)

    def test_alpaca_live_smoke_probes_only_stable_symbols_with_bounded_summary(self) -> None:
        requested_symbols: list[str] = []

        class StableOnlyAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                requested_symbols.append(symbol)
                return _alpaca_bars(end_close=102.0)

        with patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="sip"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            StableOnlyAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            side_effect=AssertionError("live smoke must stay on the bounded Alpaca configured path"),
        ):
            summary = run_rotation_radar_alpaca_live_smoke()

        self.assertEqual(set(requested_symbols), {"SPY", "QQQ", "IWM", "SMH", "SOXX", "IGV"})
        self.assertTrue(summary["credentialsPresent"])
        self.assertTrue(summary["providerConstructed"])
        self.assertTrue(summary["probePassed"])
        self.assertTrue(summary["freshnessValid"])
        self.assertTrue(summary["sourceMetadataValid"])
        self.assertTrue(summary["sourceAuthorityAllowed"])
        self.assertTrue(summary["scoreContributionAllowed"])
        self.assertEqual(summary["fulfilledWindows"], ["5m", "15m", "60m", "1d"])
        self.assertEqual(summary["missingWindows"], [])
        self.assertEqual(summary["staleWindows"], [])
        self.assertIsNone(summary["reason"])
        self.assertEqual(
            sorted(summary),
            sorted(
                [
                    "credentialsPresent",
                    "providerConstructed",
                    "probePassed",
                    "freshnessValid",
                    "sourceMetadataValid",
                    "sourceAuthorityAllowed",
                    "scoreContributionAllowed",
                    "fulfilledWindows",
                    "missingWindows",
                    "staleWindows",
                    "reason",
                ]
            ),
        )

    def test_configured_provider_calendar_and_market_session_empty_bars_are_activation_blockers(self) -> None:
        cases = (
            ("market_session", {"bars": [], "message": "market is closed for the requested session"}),
            ("calendar", {"bars": [], "message": "calendar has no trading sessions for the requested range"}),
        )
        for expected_blocker, empty_payload in cases:
            class EmptyCalendarAlpacaFetcher:
                def __init__(self, **kwargs) -> None:
                    pass

                def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> dict:
                    return empty_payload

            with self.subTest(expected_blocker=expected_blocker), patch(
                "src.services.rotation_radar_quote_provider.get_provider_credentials",
                return_value=_alpaca_credentials(feed="iex"),
                create=True,
            ), patch(
                "src.services.rotation_radar_quote_provider.AlpacaFetcher",
                EmptyCalendarAlpacaFetcher,
                create=True,
            ), patch(
                "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
                return_value=_yfinance_frame(),
            ):
                payload = load_rotation_radar_quotes(["APP"])

            diagnostics = payload["metadata"]["providerDiagnostics"]
            self.assertEqual(diagnostics["liveActivationStatus"], "unavailable")
            self.assertEqual(diagnostics["activationBlocker"], expected_blocker)
            self.assertEqual(diagnostics["providerFailureReason"], expected_blocker)
            self.assertEqual(diagnostics["providerFailureReasons"], [expected_blocker])
            self.assertEqual(diagnostics["configuredProviderFulfilledWindows"], [])
            self.assertEqual(diagnostics["configuredProviderMissingWindows"], ["5m", "15m", "60m", "1d"])
            for window in ("5m", "15m", "60m", "1d"):
                self.assertEqual(diagnostics["requestWindowResults"][window]["failureClasses"], {expected_blocker: 1})
                self.assertEqual(diagnostics["requestWindowResults"][window]["dominantFailureClass"], expected_blocker)

    def test_configured_provider_symbol_failures_reduce_coverage_and_confidence(self) -> None:
        class FakeAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                if symbol == "SQ":
                    raise RuntimeError("no data")
                return _alpaca_bars(end_close=102.0)

        with patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="sip"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            FakeAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            return_value=pd.DataFrame(),
        ):
            payload = load_rotation_radar_quotes(["APP", "SQ"])

        metadata = payload["metadata"]
        self.assertEqual(sorted(payload["quotes"]), ["APP"])
        self.assertEqual(metadata["status"], "partial")
        self.assertEqual(metadata["coverage"]["requestedSymbolCount"], 2)
        self.assertEqual(metadata["coverage"]["usableSymbolCount"], 1)
        self.assertEqual(metadata["coverage"]["coveragePercent"], 50.0)
        self.assertLess(metadata["confidenceWeight"], 0.8)
        self.assertEqual(metadata["failedSymbols"], ["SQ"])
        self.assertEqual(metadata["failedSymbolReasons"], {"SQ": "symbol_unavailable"})
        self.assertEqual(metadata["configuredProviderFailedSymbols"], ["SQ"])
        self.assertEqual(metadata["configuredProviderFailedSymbolReasons"], {"SQ": "symbol_unavailable"})
        self.assertEqual(metadata["unavailableReason"], "symbol_unavailable")

    def test_rotation_radar_yfinance_quote_provider_bounds_unavailable_symbols_and_skips_retry_within_cooldown(self) -> None:
        frame = pd.DataFrame(
            {
                "Open": [100.0, 101.0, 103.0],
                "High": [101.0, 104.0, 106.0],
                "Low": [99.0, 100.0, 102.0],
                "Close": [100.0, 103.0, 105.0],
                "Volume": [1_000_000.0, 1_200_000.0, 1_500_000.0],
            },
            index=pd.DatetimeIndex(["2026-05-09", "2026-05-12", "2026-05-13"]),
        )

        with patch("src.services.rotation_radar_quote_provider._UNAVAILABLE_SYMBOL_STATE", {}):
            with patch(
                "src.services.rotation_radar_quote_provider.get_provider_credentials",
                return_value=_missing_alpaca_credentials(),
                create=True,
            ), patch(
                "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
                side_effect=[RuntimeError("possibly delisted; no price data found"), frame, frame],
            ) as mock_fetch:
                first_payload = load_rotation_radar_quotes(["SQ", "APP"])
                second_payload = load_rotation_radar_quotes(["SQ", "APP"])

        self.assertEqual(
            [call.args[0] for call in mock_fetch.call_args_list],
            ["SQ", "APP", "APP"],
        )
        self.assertEqual(first_payload["metadata"]["status"], "partial")
        self.assertEqual(first_payload["metadata"]["unavailableReason"], "symbol_unavailable")
        self.assertEqual(first_payload["metadata"]["failedSymbols"], ["SQ"])
        self.assertEqual(first_payload["metadata"]["failedSymbolCount"], 1)
        self.assertEqual(second_payload["metadata"]["status"], "partial")
        self.assertEqual(second_payload["metadata"]["failedSymbols"], ["SQ"])
        self.assertEqual(second_payload["metadata"]["failedSymbolCount"], 1)
        self.assertEqual(second_payload["metadata"]["coverage"]["usableSymbolCount"], 1)

    def test_rotation_radar_yfinance_quote_provider_bounds_slow_symbols_and_keeps_partial_quotes(self) -> None:
        frame = pd.DataFrame(
            {
                "Open": [100.0, 101.0, 103.0],
                "High": [101.0, 104.0, 106.0],
                "Low": [99.0, 100.0, 102.0],
                "Close": [100.0, 103.0, 105.0],
                "Volume": [1_000_000.0, 1_200_000.0, 1_500_000.0],
            },
            index=pd.DatetimeIndex(["2026-05-09", "2026-05-12", "2026-05-13"]),
        )

        def fetch(symbol: str):
            if symbol == "SQ":
                time.sleep(0.05)
                raise RuntimeError("request timeout")
            return frame

        with patch("src.services.rotation_radar_quote_provider._UNAVAILABLE_SYMBOL_STATE", {}):
            with patch(
                "src.services.rotation_radar_quote_provider.get_provider_credentials",
                return_value=_missing_alpaca_credentials(),
                create=True,
            ), patch(
                "src.services.rotation_radar_quote_provider._QUOTE_PROVIDER_REQUEST_TIMEOUT_SECONDS",
                0.01,
                create=True,
            ):
                with patch(
                    "src.services.rotation_radar_quote_provider._QUOTE_PROVIDER_MAX_WORKERS",
                    2,
                    create=True,
                ):
                    with patch(
                        "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
                        side_effect=fetch,
                    ):
                        started = time.monotonic()
                        payload = load_rotation_radar_quotes(["SQ", "APP"])
                        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 0.04)
        self.assertEqual(payload["metadata"]["status"], "partial")
        self.assertEqual(sorted(payload["quotes"]), ["APP"])
        self.assertEqual(payload["metadata"]["failedSymbols"], ["SQ"])
        self.assertEqual(payload["metadata"]["failedSymbolCount"], 1)
        self.assertEqual(payload["metadata"]["unavailableReason"], "quote_fetch_failed")

    def test_slow_quote_provider_is_bounded_and_degrades_to_fallback_payload(self) -> None:
        def provider(symbols):
            time.sleep(0.05)
            return {}

        service = MarketRotationRadarService(
            quote_provider=provider,
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        with patch(
            "src.services.market_rotation_radar_service._QUOTE_PROVIDER_TIMEOUT_SECONDS",
            0.01,
            create=True,
        ):
            started = time.monotonic()
            payload = service.get_rotation_radar()
            elapsed = time.monotonic() - started

        provider_meta = payload["metadata"]["quoteProvider"]

        self.assertLess(elapsed, 0.04)
        self.assertTrue(payload["isFallback"])
        self.assertEqual(payload["source"], "fallback")
        self.assertTrue(provider_meta["present"])
        self.assertEqual(provider_meta["status"], "fallback")
        self.assertEqual(provider_meta["unavailableReason"], "quote_fetch_failed")
        self.assertGreaterEqual(provider_meta["failedSymbolCount"], 1)
        self.assertTrue(provider_meta["failedSymbols"])
        self.assertNotIn("timeout", json.dumps(payload, ensure_ascii=False).lower())

    def test_non_us_market_returns_taxonomy_only_entries_without_quote_provider_calls(self) -> None:
        provider_calls: list[list[str]] = []
        service = MarketRotationRadarService(
            quote_provider=lambda symbols: provider_calls.append(list(symbols)) or {},
            now_provider=lambda: datetime(2026, 5, 7, tzinfo=timezone.utc),
        )

        payload = service.get_rotation_radar(market="CN")

        self.assertEqual(provider_calls, [])
        self.assertEqual(payload["market"], "CN")
        self.assertGreaterEqual(len(payload["themes"]), 25)
        self.assertTrue(all(theme["staticThemeOnly"] for theme in payload["themes"]))
        self.assertTrue(all(theme["dataQuality"] in {"taxonomy_only", "local_only", "proxy_backed"} for theme in payload["themes"]))
        self.assertTrue(all(theme["confidenceLabel"] == "待行情确认" for theme in payload["themes"]))
        self.assertTrue(all(theme["confidence"] <= 0.25 for theme in payload["themes"]))
        self.assertTrue(all("rotationStateEvidence" in theme for theme in payload["themes"]))
        self.assertTrue(all(theme["rotationStateEvidence"]["state"] == "insufficient_evidence" for theme in payload["themes"]))
        self.assertTrue(all(theme["rotationStateEvidence"]["flowEvidenceType"] == "none" for theme in payload["themes"]))
        self.assertTrue(all(theme["rotationStateEvidence"]["flowLanguageAllowed"] is False for theme in payload["themes"]))
        self.assertTrue(all(theme["signalType"] == "taxonomy_fallback" for theme in payload["themes"]))
        self.assertTrue(all(theme["flowEvidenceType"] == "none" for theme in payload["themes"]))
        self.assertTrue(all(theme["flowLanguageAllowed"] is False for theme in payload["themes"]))
        self.assertTrue(all(theme["sourceAuthorityAllowed"] is False for theme in payload["themes"]))
        self.assertTrue(all(theme["evidenceQuality"] == "taxonomy_only" for theme in payload["themes"]))
        self.assertTrue(all("taxonomy_only" in theme["dataGaps"] for theme in payload["themes"]))
        self.assertTrue(all("true_flow_data_missing" in theme["dataGaps"] for theme in payload["themes"]))
        self.assertEqual(payload["summary"]["strongestThemes"], [])
        self.assertEqual(payload["summary"]["acceleratingThemes"], [])
        self.assertEqual(payload["summary"]["eligibleThemeCount"], 0)
        self.assertEqual(payload["summary"]["headlineEligibleThemeCount"], 0)
        self.assertIn("没有可用于头部排名", payload["summary"]["noHeadlineReason"])
        self.assertTrue(all(theme["rankingLane"] == "taxonomy" for theme in payload["summary"]["taxonomyThemes"]))
        self.assertIn("AI算力", [theme["name"] for theme in payload["themes"]])

    def test_stale_and_missing_data_penalizes_confidence_and_blocks_clean_rotation_claims(self) -> None:
        quotes = {
            "QQQ": _quote("QQQ", 0.7),
            "SPY": _quote("SPY", 0.2),
            "IWM": _quote("IWM", -0.2),
            "NVDA": _quote("NVDA", 7.5, volume_ratio=2.8, price=980, freshness="stale", is_stale=True),
            "AVGO": _quote("AVGO", 0.2, volume_ratio=0.9, price=1450),
            "AMD": _quote("AMD", -0.4, volume_ratio=0.8, price=160),
        }
        service = MarketRotationRadarService(
            quote_provider=lambda symbols: {symbol: quotes[symbol] for symbol in symbols if symbol in quotes},
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        payload = service.get_rotation_radar()
        infra = next(theme for theme in payload["themes"] if theme["id"] == "ai_infrastructure")

        self.assertIn("stale_or_incomplete_windows", infra["riskLabels"])
        self.assertIn("thin_breadth", infra["riskLabels"])
        self.assertIn("single_name_driven", infra["riskLabels"])
        self.assertLess(infra["confidence"], 0.55)
        self.assertEqual(infra["stage"], "weak_or_no_signal")
        self.assertEqual(infra["rotationScore"], 36)
        self.assertEqual(infra["rotationStateEvidence"]["state"], "divergence")
        self.assertEqual(infra["rotationStateEvidence"]["evidenceSnapshot"]["sourceConfidence"]["freshness"], "stale")
        self.assertTrue(infra["rotationStateEvidence"]["evidenceSnapshot"]["sourceConfidence"]["isStale"])
        self.assertEqual(infra["signalType"], "relative_strength")
        self.assertEqual(infra["evidenceQuality"], "degraded_proxy")
        self.assertIn("stale_quote_window", infra["dataGaps"])
        self.assertNotIn(
            infra["rotationStateEvidence"]["evidenceSnapshot"]["sourceConfidence"]["freshness"],
            {"live", "fresh"},
        )
        self.assertFalse(infra["newslessRotation"])

    def test_rotation_state_evidence_does_not_trigger_additional_provider_calls(self) -> None:
        provider_calls: list[list[str]] = []
        quotes = {
            "QQQ": _quote("QQQ", 0.8),
            "SPY": _quote("SPY", 0.45),
            "IWM": _quote("IWM", 0.15),
            "APP": _quote("APP", 5.1, volume_ratio=2.4, price=310),
            "PLTR": _quote("PLTR", 4.6, volume_ratio=2.0, price=132),
            "CRM": _quote("CRM", 2.8, volume_ratio=1.7, price=285),
            "SNOW": _quote("SNOW", 3.5, volume_ratio=1.8, price=212),
            "ADBE": _quote("ADBE", 2.2, volume_ratio=1.5, price=505),
            "NOW": _quote("NOW", 2.6, volume_ratio=1.6, price=780),
        }
        service = MarketRotationRadarService(
            quote_provider=lambda symbols: provider_calls.append(list(symbols)) or {
                symbol: quotes[symbol] for symbol in symbols if symbol in quotes
            },
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        payload = service.get_rotation_radar()

        self.assertEqual(len(provider_calls), 1)
        self.assertTrue(payload["themes"][0]["rotationStateEvidence"])

    def test_theme_detail_separates_sorted_leaders_and_laggards_as_observation_evidence(self) -> None:
        windows = {
            "5m": {"changePercent": 0.4, "relativeVolume": 1.2, "freshness": "live", "asOf": "2026-05-07T09:45:00+00:00"},
            "15m": {"changePercent": 0.9, "relativeVolume": 1.4, "freshness": "live", "asOf": "2026-05-07T09:45:00+00:00"},
            "60m": {"changePercent": 1.4, "relativeVolume": 1.6, "freshness": "live", "asOf": "2026-05-07T09:45:00+00:00"},
        }
        quotes = {
            "QQQ": _quote("QQQ", 0.3, time_windows=windows),
            "SPY": _quote("SPY", 0.2, time_windows=windows),
            "IWM": _quote("IWM", -0.1, time_windows=windows),
            "IGV": _quote("IGV", 0.4, time_windows=windows),
            "APP": _quote("APP", 4.2, volume_ratio=1.9, time_windows=windows),
            "PLTR": _quote("PLTR", 3.3, volume_ratio=1.6, time_windows=windows),
            "CRM": _quote("CRM", 0.1, volume_ratio=0.9, time_windows=windows),
            "SNOW": _quote("SNOW", -0.5, volume_ratio=0.8, time_windows=windows),
        }
        service = MarketRotationRadarService(
            quote_provider=lambda symbols: {symbol: quotes[symbol] for symbol in symbols if symbol in quotes},
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        payload = service.get_rotation_radar()
        theme = next(item for item in payload["themes"] if item["id"] == "ai_applications")
        detail = theme["themeDetail"]

        self.assertEqual(detail["leaderSectionLabel"], "领先成员")
        self.assertEqual(detail["laggardSectionLabel"], "落后/待验证成员")
        self.assertIn("观察信号", detail["leaderExplanation"])
        self.assertIn("不是买卖建议", detail["laggardExplanation"])
        self.assertEqual([item["symbol"] for item in detail["leadershipMembers"][:2]], ["APP", "PLTR"])
        self.assertEqual([item["symbol"] for item in detail["laggardMembers"][:2]], ["SNOW", "CRM"])

    def test_payload_uses_safe_no_advice_and_no_exact_fund_flow_wording(self) -> None:
        payload = MarketRotationRadarService().get_rotation_radar()
        dumped = json.dumps(payload, ensure_ascii=False).lower()

        forbidden = (
            "建议买入",
            "必买",
            "稳赚",
            "下单",
            "best contract",
            "guaranteed",
            "buy now",
            "sell now",
            "主力资金流入金额",
            "exact fund flow",
        )
        for marker in forbidden:
            self.assertNotIn(marker.lower(), dumped)
        self.assertIn("资金轮动迹象", dumped)
        self.assertIn("非买卖建议", dumped)

    def test_bounded_etf_authority_spine_is_emitted_when_alpaca_windows_pass(self) -> None:
        stable_etfs = ("SPY", "QQQ", "IWM", "SMH", "SOXX", "IGV")

        class StableEtfAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                return _alpaca_bars(
                    start_close=100.0,
                    end_close={
                        "5Min": 101.0,
                        "15Min": 102.0,
                        "1Hour": 103.0,
                        "1Day": 104.0,
                    }[timeframe],
                )

        with patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="sip"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            StableEtfAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            side_effect=AssertionError("yfinance fallback should not be called when Alpaca covers the bounded ETF spine"),
        ):
            payload = load_rotation_radar_quotes(stable_etfs)

        spine = payload["metadata"]["providerDiagnostics"]["etfAuthoritySpine"]

        self.assertEqual(spine["universe"], list(stable_etfs))
        self.assertEqual(spine["requiredWindows"], ["5m", "15m", "60m", "1d"])
        self.assertEqual(spine["fulfilledWindows"], ["5m", "15m", "60m", "1d"])
        self.assertEqual(spine["missingWindows"], [])
        self.assertTrue(spine["sourceAuthorityAllowed"])
        self.assertTrue(spine["scoreContributionAllowed"])
        self.assertEqual(spine["trustLevel"], "active")
        self.assertEqual(spine["reasonCodes"], [])
        self.assertEqual([row["symbol"] for row in spine["quotes"]], list(stable_etfs))
        self.assertTrue(all(row["windowsFulfilled"] == ["5m", "15m", "60m", "1d"] for row in spine["quotes"]))
        self.assertTrue(all(row["sourceLabel"] == "Alpaca SIP" for row in spine["quotes"]))
        self.assertTrue(all(row["sourceTier"] == "broker_authorized" for row in spine["quotes"]))
        self.assertTrue(all(row["sourceAuthorityAllowed"] for row in spine["quotes"]))
        self.assertTrue(all(row["scoreContributionAllowed"] for row in spine["quotes"]))
        self.assertTrue(all(row["reasonCodes"] == [] for row in spine["quotes"]))

    def test_missing_credentials_keep_bounded_etf_authority_spine_non_scoring(self) -> None:
        stable_etfs = ("SPY", "QQQ", "IWM", "SMH", "SOXX", "IGV")

        with patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_missing_alpaca_credentials(),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            return_value=_yfinance_frame(),
        ):
            payload = load_rotation_radar_quotes(stable_etfs)

        spine = payload["metadata"]["providerDiagnostics"]["etfAuthoritySpine"]

        self.assertFalse(spine["sourceAuthorityAllowed"])
        self.assertFalse(spine["scoreContributionAllowed"])
        self.assertEqual(spine["trustLevel"], "unavailable")
        self.assertIn("credentials", spine["reasonCodes"])
        self.assertEqual([row["symbol"] for row in spine["quotes"]], list(stable_etfs))
        self.assertTrue(all(row["scoreContributionAllowed"] is False for row in spine["quotes"]))
        self.assertTrue(all(row["sourceAuthorityAllowed"] is False for row in spine["quotes"]))
        self.assertTrue(all("credentials" in row["reasonCodes"] for row in spine["quotes"]))

    def test_partial_windows_keep_bounded_etf_authority_spine_non_scoring(self) -> None:
        stable_etfs = ("SPY", "QQQ", "IWM", "SMH", "SOXX", "IGV")

        class DailyOnlyAlpacaFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def get_bars(self, symbol: str, *, timeframe: str, start: str, end: str, limit: int = 100) -> list[dict]:
                if timeframe != "1Day":
                    raise RuntimeError("subscription required")
                return _alpaca_bars(end_close=102.0)

        with patch(
            "src.services.rotation_radar_quote_provider.get_provider_credentials",
            return_value=_alpaca_credentials(feed="sip"),
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.AlpacaFetcher",
            DailyOnlyAlpacaFetcher,
            create=True,
        ), patch(
            "src.services.rotation_radar_quote_provider.fetch_yfinance_quote_history_frame",
            side_effect=AssertionError("yfinance fallback should not be called when Alpaca returns bounded ETF rows"),
        ):
            payload = load_rotation_radar_quotes(stable_etfs)

        spine = payload["metadata"]["providerDiagnostics"]["etfAuthoritySpine"]

        self.assertFalse(spine["sourceAuthorityAllowed"])
        self.assertFalse(spine["scoreContributionAllowed"])
        self.assertEqual(spine["fulfilledWindows"], ["1d"])
        self.assertEqual(spine["missingWindows"], ["5m", "15m", "60m"])
        self.assertEqual(spine["trustLevel"], "partial")
        self.assertIn("entitlement", spine["reasonCodes"])
        self.assertTrue(all(row["scoreContributionAllowed"] is False for row in spine["quotes"]))
        self.assertTrue(all(row["sourceAuthorityAllowed"] is False for row in spine["quotes"]))
        self.assertTrue(all("entitlement" in row["reasonCodes"] for row in spine["quotes"]))

    def test_active_etf_authority_spine_does_not_promote_static_themes_to_headlines(self) -> None:
        stable_etfs = ("SPY", "QQQ", "IWM", "SMH", "SOXX", "IGV")
        time_windows = {
            "5m": {"changePercent": 0.8, "relativeVolume": 1.2, "freshness": "live", "asOf": "2026-05-07T09:45:00+00:00", "available": True, "source": "alpaca", "sourceLabel": "Alpaca SIP", "sourceTier": "broker_authorized", "providerTier": "tier_1_configured"},
            "15m": {"changePercent": 1.1, "relativeVolume": 1.3, "freshness": "live", "asOf": "2026-05-07T09:45:00+00:00", "available": True, "source": "alpaca", "sourceLabel": "Alpaca SIP", "sourceTier": "broker_authorized", "providerTier": "tier_1_configured"},
            "60m": {"changePercent": 1.6, "relativeVolume": 1.4, "freshness": "live", "asOf": "2026-05-07T09:45:00+00:00", "available": True, "source": "alpaca", "sourceLabel": "Alpaca SIP", "sourceTier": "broker_authorized", "providerTier": "tier_1_configured"},
            "1d": {"changePercent": 2.0, "relativeVolume": 1.5, "freshness": "delayed", "asOf": "2026-05-07T09:45:00+00:00", "available": True, "source": "alpaca", "sourceLabel": "Alpaca SIP", "sourceTier": "broker_authorized", "providerTier": "tier_1_configured"},
        }
        quotes = {
            symbol: _quote(
                symbol,
                1.0 + index * 0.1,
                freshness="live",
                time_windows=time_windows,
                source="alpaca",
                source_type="official_public",
                source_tier="broker_authorized",
            )
            for index, symbol in enumerate(stable_etfs)
        }
        etf_authority_spine = {
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
        service = MarketRotationRadarService(
            quote_provider=lambda symbols: {
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
            },
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )
        payload = service.get_rotation_radar()

        provider_meta = payload["metadata"]["quoteProvider"]
        spine = provider_meta["etfAuthoritySpine"]
        ai_theme = next(theme for theme in payload["themes"] if theme["id"] == "ai_applications")
        igv_proxy = ai_theme["benchmarkProxies"]["IGV"]

        self.assertTrue(spine["sourceAuthorityAllowed"])
        self.assertTrue(spine["scoreContributionAllowed"])
        self.assertEqual(provider_meta["status"], "partial")
        self.assertEqual(payload["summary"]["headlineEligibleThemeCount"], 0)
        self.assertEqual(payload["summary"]["eligibleThemeCount"], 0)
        self.assertFalse(ai_theme["headlineEligible"])
        self.assertFalse(ai_theme["scoreContributionAllowed"])
        self.assertTrue(ai_theme["staticThemeOnly"])
        self.assertEqual(ai_theme["rankingLane"], "observation")
        self.assertTrue(igv_proxy["etfAuthorityEvidence"]["sourceAuthorityAllowed"])
        self.assertTrue(igv_proxy["etfAuthorityEvidence"]["scoreContributionAllowed"])
        self.assertEqual(igv_proxy["etfAuthorityEvidence"]["symbol"], "IGV")
        self.assertEqual(igv_proxy["etfAuthorityEvidence"]["reasonCodes"], [])

    def test_active_bounded_etf_authority_spine_produces_leadership_diagnostics(self) -> None:
        stable_etfs, quotes, etf_authority_spine = _bounded_etf_authority_fixture()
        service = MarketRotationRadarService(
            quote_provider=lambda symbols: {
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
            },
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        payload = service.get_rotation_radar()
        diagnostics = payload["etfLeadershipDiagnostics"]

        self.assertTrue(diagnostics["enabled"])
        self.assertEqual(diagnostics["source"], "alpaca_etf_authority_spine")
        self.assertEqual(diagnostics["asOf"], "2026-05-07T09:45:00+00:00")
        self.assertEqual(diagnostics["eligibleSymbols"], list(stable_etfs))
        self.assertEqual(diagnostics["leadingSymbols"], ["SMH", "SOXX", "QQQ"])
        self.assertEqual(diagnostics["laggingSymbols"], ["IWM", "IGV", "SPY"])
        self.assertGreater(diagnostics["leadershipSpread"], 1.0)
        self.assertEqual(diagnostics["confidenceLabel"], "high")
        self.assertEqual(diagnostics["reasonCodes"], ["bounded_etf_authority_active"])
        self.assertEqual([row["symbol"] for row in diagnostics["evidence"]], list(stable_etfs))
        self.assertTrue(all(row["sourceAuthorityAllowed"] for row in diagnostics["evidence"]))
        self.assertTrue(all(row["scoreContributionAllowed"] for row in diagnostics["evidence"]))

    def test_partial_etf_authority_windows_disable_leadership_diagnostics(self) -> None:
        stable_etfs, quotes, etf_authority_spine = _bounded_etf_authority_fixture()
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

        service = MarketRotationRadarService(
            quote_provider=lambda symbols: {
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
            },
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        payload = service.get_rotation_radar()
        diagnostics = payload["etfLeadershipDiagnostics"]

        self.assertFalse(diagnostics["enabled"])
        self.assertEqual(diagnostics["leadingSymbols"], [])
        self.assertEqual(diagnostics["laggingSymbols"], [])
        self.assertIsNone(diagnostics["leadershipSpread"])
        self.assertEqual(diagnostics["confidenceLabel"], "disabled")
        self.assertIn("missing_required_windows", diagnostics["reasonCodes"])
        self.assertIn("ineligible_bounded_etf", diagnostics["reasonCodes"])

    def test_missing_credentials_disable_leadership_diagnostics(self) -> None:
        stable_etfs, quotes, etf_authority_spine = _bounded_etf_authority_fixture()
        etf_authority_spine["sourceAuthorityAllowed"] = False
        etf_authority_spine["scoreContributionAllowed"] = False
        etf_authority_spine["trustLevel"] = "unavailable"
        etf_authority_spine["reasonCodes"] = ["credentials"]
        for row in etf_authority_spine["quotes"]:
            row["sourceAuthorityAllowed"] = False
            row["scoreContributionAllowed"] = False
            row["trustLevel"] = "unavailable"
            row["reasonCodes"] = ["credentials"]

        yfinance_quotes = {
            symbol: _quote(
                symbol,
                quotes[symbol]["changePercent"],
                freshness="delayed",
                is_fallback=True,
                time_windows={"1d": {"changePercent": quotes[symbol]["changePercent"], "freshness": "delayed", "asOf": "2026-05-07T09:45:00+00:00", "available": True}},
                source="yfinance_proxy",
                source_type="unofficial_public_api",
                source_tier="unofficial_public_api",
            )
            for symbol in stable_etfs
        }

        service = MarketRotationRadarService(
            quote_provider=lambda symbols: {
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
                    "providerDiagnostics": {
                        "etfAuthoritySpine": etf_authority_spine,
                    },
                },
            },
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        payload = service.get_rotation_radar()
        diagnostics = payload["etfLeadershipDiagnostics"]

        self.assertFalse(diagnostics["enabled"])
        self.assertEqual(diagnostics["eligibleSymbols"], [])
        self.assertIn("credentials", diagnostics["reasonCodes"])
        self.assertEqual(diagnostics["confidenceLabel"], "disabled")

    def test_static_or_yfinance_fallback_cannot_produce_leadership_diagnostics(self) -> None:
        stable_etfs, quotes, _ = _bounded_etf_authority_fixture()
        yfinance_quotes = {
            symbol: _quote(
                symbol,
                quotes[symbol]["changePercent"],
                freshness="delayed",
                is_fallback=True,
                time_windows={"1d": {"changePercent": quotes[symbol]["changePercent"], "freshness": "delayed", "asOf": "2026-05-07T09:45:00+00:00", "available": True}},
                source="yfinance_proxy",
                source_type="unofficial_public_api",
                source_tier="unofficial_public_api",
            )
            for symbol in stable_etfs
        }
        service = MarketRotationRadarService(
            quote_provider=lambda symbols: {
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
            },
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        payload = service.get_rotation_radar()
        diagnostics = payload["etfLeadershipDiagnostics"]

        self.assertFalse(diagnostics["enabled"])
        self.assertEqual(diagnostics["eligibleSymbols"], [])
        self.assertEqual(diagnostics["leadingSymbols"], [])
        self.assertEqual(diagnostics["laggingSymbols"], [])
        self.assertIn("etf_authority_spine_missing", diagnostics["reasonCodes"])

    def test_leadership_diagnostics_stay_bounded_to_authority_spine_symbols(self) -> None:
        stable_etfs, quotes, etf_authority_spine = _bounded_etf_authority_fixture()
        etf_authority_spine["universe"] = [*stable_etfs, "XLF"]
        etf_authority_spine["quotes"].append(
            {
                "symbol": "XLF",
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
        )
        service = MarketRotationRadarService(
            quote_provider=lambda symbols: {
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
            },
            now_provider=lambda: datetime(2026, 5, 7, 9, 50, tzinfo=timezone.utc),
        )

        payload = service.get_rotation_radar()
        diagnostics = payload["etfLeadershipDiagnostics"]

        self.assertEqual(diagnostics["eligibleSymbols"], list(stable_etfs))
        self.assertNotIn("XLF", diagnostics["eligibleSymbols"])
        self.assertNotIn("XLF", diagnostics["leadingSymbols"])
        self.assertNotIn("XLF", diagnostics["laggingSymbols"])
        self.assertTrue(all(row["symbol"] in stable_etfs for row in diagnostics["evidence"]))


if __name__ == "__main__":
    unittest.main()
