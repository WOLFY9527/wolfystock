# -*- coding: utf-8 -*-
"""Offline contracts for the optional BaoStock capability probe."""

from __future__ import annotations

from data_provider.baostock_fetcher import BaostockFetcher
from src.services.market_data_source_registry import project_source_provenance


class _ProbeResult:
    def __init__(self, error_code: str = "0", error_msg: str = "") -> None:
        self.error_code = error_code
        self.error_msg = error_msg


class _ProbeBaostockModule:
    def __init__(self) -> None:
        self.login_calls = 0
        self.logout_calls = 0

    def login(self) -> _ProbeResult:
        self.login_calls += 1
        return _ProbeResult()

    def logout(self) -> _ProbeResult:
        self.logout_calls += 1
        return _ProbeResult()


def test_baostock_capability_probe_degrades_cleanly_when_dependency_is_missing() -> None:
    fetcher = BaostockFetcher()
    fetcher._get_baostock = lambda: None

    probe = fetcher.probe_capabilities(timeout_seconds=2.5)

    assert probe == {
        "providerName": "baostock",
        "providerId": "baostock",
        "source": "baostock",
        "sourceType": "public_proxy",
        "sourceTier": "third_party_free_api",
        "sourceLabel": "BaoStock",
        "dependencyInstalled": False,
        "providerAvailable": False,
        "interfaceHealth": "missing_dependency",
        "serverHealth": "missing_dependency",
        "healthStatus": "missing_dependency",
        "supportedCapabilities": [
            "cn_history_daily",
            "cn_adjust_factor",
            "cn_basic_financials",
            "cn_index_history_daily",
        ],
        "unsupportedCapabilities": [
            "cn_realtime_quote",
            "cn_quote",
            "hk_history_daily",
            "hk_quote",
            "us_history_daily",
            "us_quote",
        ],
        "trustLevel": "unavailable",
        "freshness": "unavailable",
        "freshnessExpectation": "t_plus_1_or_delayed",
        "observationOnly": True,
        "scoreContributionAllowed": False,
        "paidDataLikelyRequired": False,
        "keyRequired": False,
        "cacheRequired": True,
        "backgroundRefreshRecommended": True,
        "degradationReason": "baostock_not_installed",
        "missingProviderReason": "baostock_not_installed",
        "attemptedAt": None,
        "timeoutSeconds": 2.5,
    }


def test_baostock_capability_probe_degrades_cleanly_when_live_probe_is_disabled() -> None:
    fetcher = BaostockFetcher()
    module = _ProbeBaostockModule()
    fetcher._get_baostock = lambda: module

    probe = fetcher.probe_capabilities(timeout_seconds=1.25, live_probe_enabled=False)

    assert probe["providerName"] == "baostock"
    assert probe["providerId"] == "baostock"
    assert probe["source"] == "baostock"
    assert probe["sourceType"] == "public_proxy"
    assert probe["sourceTier"] == "third_party_free_api"
    assert probe["sourceLabel"] == "BaoStock"
    assert probe["dependencyInstalled"] is True
    assert probe["providerAvailable"] is False
    assert probe["interfaceHealth"] == "ready"
    assert probe["serverHealth"] == "probe_disabled"
    assert probe["healthStatus"] == "probe_disabled"
    assert probe["trustLevel"] == "unavailable"
    assert probe["freshness"] == "unavailable"
    assert probe["freshnessExpectation"] == "t_plus_1_or_delayed"
    assert probe["observationOnly"] is True
    assert probe["scoreContributionAllowed"] is False
    assert probe["paidDataLikelyRequired"] is False
    assert probe["keyRequired"] is False
    assert probe["cacheRequired"] is True
    assert probe["backgroundRefreshRecommended"] is True
    assert probe["degradationReason"] == "baostock_live_probe_disabled"
    assert probe["missingProviderReason"] == "baostock_live_probe_disabled"
    assert probe["attemptedAt"] is None
    assert probe["timeoutSeconds"] == 1.25
    assert module.login_calls == 0
    assert module.logout_calls == 0


def test_baostock_capability_probe_reports_reachable_server_without_promoting_trust() -> None:
    fetcher = BaostockFetcher()
    module = _ProbeBaostockModule()
    fetcher._get_baostock = lambda: module

    probe = fetcher.probe_capabilities(timeout_seconds=3, live_probe_enabled=True)

    assert probe["providerName"] == "baostock"
    assert probe["providerId"] == "baostock"
    assert probe["source"] == "baostock"
    assert probe["sourceType"] == "public_proxy"
    assert probe["sourceTier"] == "third_party_free_api"
    assert probe["sourceLabel"] == "BaoStock"
    assert probe["dependencyInstalled"] is True
    assert probe["providerAvailable"] is True
    assert probe["interfaceHealth"] == "ok"
    assert probe["serverHealth"] == "reachable"
    assert probe["healthStatus"] == "healthy"
    assert probe["trustLevel"] == "usable_with_caution"
    assert probe["freshness"] == "delayed"
    assert probe["freshnessExpectation"] == "t_plus_1_or_delayed"
    assert probe["observationOnly"] is True
    assert probe["scoreContributionAllowed"] is False
    assert probe["paidDataLikelyRequired"] is False
    assert probe["keyRequired"] is False
    assert probe["cacheRequired"] is True
    assert probe["backgroundRefreshRecommended"] is True
    assert probe["degradationReason"] is None
    assert probe["missingProviderReason"] is None
    assert probe["attemptedAt"] is not None
    assert probe["timeoutSeconds"] == 3
    assert probe["supportedCapabilities"] == [
        "cn_history_daily",
        "cn_adjust_factor",
        "cn_basic_financials",
        "cn_index_history_daily",
    ]
    assert probe["unsupportedCapabilities"] == [
        "cn_realtime_quote",
        "cn_quote",
        "hk_history_daily",
        "hk_quote",
        "us_history_daily",
        "us_quote",
    ]
    assert module.login_calls == 1
    assert module.logout_calls == 1


def test_baostock_source_provenance_stays_non_official() -> None:
    provenance = project_source_provenance(
        source="baostock",
        source_type="official_public",
        freshness="delayed",
    )

    assert provenance["sourceType"] == "public_proxy"
    assert provenance["sourceLabel"] == "BaoStock"
    assert provenance["freshnessLabel"] == "延迟"
