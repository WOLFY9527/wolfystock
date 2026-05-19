# -*- coding: utf-8 -*-
"""Offline contracts for the optional AKShare capability probe."""

from __future__ import annotations

from data_provider.akshare_fetcher import AkshareFetcher
from src.services.market_data_source_registry import project_source_provenance
from src.services.provider_capability_matrix import (
    FreshnessClass,
    ProviderDomain,
    ProviderMarket,
    get_provider_capability,
)


class _ProbeAkshareModule:
    def stock_info_a_code_name(self) -> list[dict[str, str]]:
        return [{"code": "600519", "name": "贵州茅台"}]


class _FailingProbeAkshareModule:
    def stock_info_a_code_name(self) -> list[dict[str, str]]:
        raise RuntimeError("upstream page changed")


def test_akshare_capability_probe_degrades_cleanly_when_dependency_is_missing() -> None:
    fetcher = AkshareFetcher(sleep_min=0.0, sleep_max=0.0)
    fetcher._get_akshare = lambda: None

    probe = fetcher.probe_capabilities(timeout_seconds=2.5)

    assert probe == {
        "providerName": "akshare",
        "providerId": "akshare",
        "source": "akshare",
        "sourceType": "public_proxy",
        "sourceLabel": "AkShare",
        "dependencyInstalled": False,
        "providerAvailable": False,
        "interfaceHealth": "missing_dependency",
        "supportedCapabilities": [
            "cn_stock_list",
            "cn_realtime_snapshot",
            "cn_realtime_quote",
            "cn_history_daily",
            "cn_index_quote",
            "cn_market_stats",
            "cn_sector_rankings",
            "cn_etf_realtime_quote",
            "cn_etf_history_daily",
            "hk_realtime_quote",
            "hk_history_daily",
            "chip_distribution",
        ],
        "unsupportedCapabilities": [
            "us_realtime_quote",
            "us_history_daily",
            "hk_index_quote",
        ],
        "sourceTier": "unofficial_public_api",
        "trustLevel": "unavailable",
        "freshness": "unavailable",
        "freshnessExpectation": "best_effort_public_web_quote_snapshot_and_daily_history",
        "observationOnly": True,
        "scoreContributionAllowed": False,
        "degradationReason": "akshare_not_installed",
        "missingProviderReason": "akshare_not_installed",
        "timeoutSeconds": 2.5,
        "attemptedAt": None,
    }


def test_akshare_capability_probe_reports_available_interface_without_promoting_trust() -> None:
    fetcher = AkshareFetcher(sleep_min=0.0, sleep_max=0.0)
    fetcher._get_akshare = lambda: _ProbeAkshareModule()

    probe = fetcher.probe_capabilities(timeout_seconds=1.25)

    assert probe["providerName"] == "akshare"
    assert probe["providerId"] == "akshare"
    assert probe["source"] == "akshare"
    assert probe["sourceType"] == "public_proxy"
    assert probe["sourceLabel"] == "AkShare"
    assert probe["dependencyInstalled"] is True
    assert probe["providerAvailable"] is True
    assert probe["interfaceHealth"] == "ok"
    assert probe["sourceTier"] == "unofficial_public_api"
    assert probe["trustLevel"] == "weak"
    assert probe["freshness"] == "delayed"
    assert probe["freshnessExpectation"] == "best_effort_public_web_quote_snapshot_and_daily_history"
    assert probe["observationOnly"] is True
    assert probe["scoreContributionAllowed"] is False
    assert probe["degradationReason"] is None
    assert probe["missingProviderReason"] is None
    assert probe["supportedCapabilities"] == [
        "cn_stock_list",
        "cn_realtime_snapshot",
        "cn_realtime_quote",
        "cn_history_daily",
        "cn_index_quote",
        "cn_market_stats",
        "cn_sector_rankings",
        "cn_etf_realtime_quote",
        "cn_etf_history_daily",
        "hk_realtime_quote",
        "hk_history_daily",
        "chip_distribution",
    ]
    assert probe["unsupportedCapabilities"] == [
        "us_realtime_quote",
        "us_history_daily",
        "hk_index_quote",
    ]
    assert probe["timeoutSeconds"] == 1.25
    assert isinstance(probe["attemptedAt"], str)


def test_akshare_capability_probe_degrades_cleanly_when_interface_probe_fails() -> None:
    fetcher = AkshareFetcher(sleep_min=0.0, sleep_max=0.0)
    fetcher._get_akshare = lambda: _FailingProbeAkshareModule()

    probe = fetcher.probe_capabilities(timeout_seconds=3)

    assert probe["dependencyInstalled"] is True
    assert probe["providerAvailable"] is False
    assert probe["interfaceHealth"] == "error"
    assert probe["sourceType"] == "public_proxy"
    assert probe["sourceTier"] == "unofficial_public_api"
    assert probe["trustLevel"] == "unavailable"
    assert probe["freshness"] == "unavailable"
    assert probe["observationOnly"] is True
    assert probe["scoreContributionAllowed"] is False
    assert probe["degradationReason"] == "akshare_probe_failed"
    assert probe["missingProviderReason"] == "akshare_probe_failed"
    assert probe["timeoutSeconds"] == 3
    assert isinstance(probe["attemptedAt"], str)


def test_akshare_source_provenance_stays_non_official() -> None:
    provenance = project_source_provenance(
        source="akshare",
        source_type="official_public",
        freshness="delayed",
    )

    assert provenance["sourceType"] == "public_proxy"
    assert provenance["sourceLabel"] == "AkShare"
    assert provenance["freshnessLabel"] == "延迟"


def test_provider_capability_matrix_marks_akshare_as_cautionary_cn_hk_provider() -> None:
    capability = get_provider_capability("akshare")

    assert capability is not None
    assert capability.provider_id == "akshare"
    assert capability.display_name == "AkShare"
    assert capability.domains == (
        ProviderDomain.QUOTE,
        ProviderDomain.OHLCV,
        ProviderDomain.TECHNICALS,
    )
    assert capability.markets == (ProviderMarket.CN, ProviderMarket.HK)
    assert capability.freshness_class is FreshnessClass.DELAYED
    assert capability.scanner_allowed is True
    assert capability.backtest_allowed is False
    assert "public web" in capability.risk_notes[0].lower()

