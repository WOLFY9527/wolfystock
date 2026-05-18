# -*- coding: utf-8 -*-
"""Market rotation radar scoring and safety tests."""

from __future__ import annotations

import json
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pandas as pd

from src.services.market_data_source_registry import project_source_provenance
from src.services.market_rotation_radar_service import MarketRotationRadarService
from src.services.rotation_radar_quote_provider import load_rotation_radar_quotes


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
        "source": "unit_fixture",
        "sourceLabel": "Unit Fixture",
        "asOf": "2026-05-07T09:45:00+00:00",
    }
    if time_windows is not None:
        payload["timeWindows"] = time_windows
    return payload


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
            self.assertIn("stale_or_incomplete_windows", theme["riskLabels"])
            self.assertTrue(all(not slot["available"] for slot in theme["timeWindows"].values()))
            self.assertTrue(theme["themeDetail"]["watchlistSafe"])
            self.assertEqual(theme["proxyQuality"]["coveragePercent"], 0)
            self.assertTrue(all(proxy["quality"]["missingReason"] for proxy in theme["benchmarkProxies"].values()))

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


if __name__ == "__main__":
    unittest.main()
