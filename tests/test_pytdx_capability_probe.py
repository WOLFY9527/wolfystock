# -*- coding: utf-8 -*-
"""Offline contracts for the optional pytdx capability probe."""

from __future__ import annotations

from data_provider.pytdx_fetcher import PytdxFetcher
from src.services.market_data_source_registry import project_source_provenance


class _ReachableApi:
    instances: list["_ReachableApi"] = []

    def __init__(self) -> None:
        self.disconnected = False
        self.connect_calls: list[tuple[str, int, float]] = []
        _ReachableApi.instances.append(self)

    def connect(self, host: str, port: int, time_out: float = 5) -> bool:
        self.connect_calls.append((host, port, time_out))
        return True

    def disconnect(self) -> None:
        self.disconnected = True


class _UnreachableApi:
    instances: list["_UnreachableApi"] = []

    def __init__(self) -> None:
        self.disconnected = False
        self.connect_calls: list[tuple[str, int, float]] = []
        _UnreachableApi.instances.append(self)

    def connect(self, host: str, port: int, time_out: float = 5) -> bool:
        self.connect_calls.append((host, port, time_out))
        raise RuntimeError("tdx socket timeout")

    def disconnect(self) -> None:
        self.disconnected = True


def test_pytdx_capability_probe_degrades_cleanly_when_dependency_is_missing() -> None:
    fetcher = PytdxFetcher(hosts=[("1.2.3.4", 7709)])
    probe = fetcher.probe_capabilities(timeout_seconds=2.5)

    assert probe == {
        "providerName": "pytdx",
        "providerId": "pytdx",
        "source": "pytdx",
        "sourceType": "public_proxy",
        "sourceLabel": "pytdx / 通达信",
        "dependencyInstalled": False,
        "providerAvailable": False,
        "serverReachable": None,
        "serverHealth": "missing_dependency",
        "supportedCapabilities": [
            "cn_history_daily",
            "cn_name_lookup",
            "cn_quote",
            "cn_realtime_quote",
        ],
        "unsupportedCapabilities": [
            "hk_history_daily",
            "hk_quote",
            "us_history_daily",
            "us_quote",
        ],
        "sourceTier": "unofficial_public_api",
        "trustLevel": "unavailable",
        "freshness": "unavailable",
        "freshnessExpectation": "best_effort_realtime_quote_and_daily_history",
        "observationOnly": True,
        "scoreContributionAllowed": False,
        "degradationReason": "pytdx_not_installed",
        "missingProviderReason": "pytdx_not_installed",
        "timeoutSeconds": 2.5,
        "attemptedAt": None,
    }


def test_pytdx_capability_probe_reports_reachable_server_without_promoting_trust() -> None:
    _ReachableApi.instances.clear()
    fetcher = PytdxFetcher(hosts=[("119.147.212.81", 7709)])
    fetcher._get_pytdx = lambda: _ReachableApi

    probe = fetcher.probe_capabilities(timeout_seconds=1.25)

    assert probe["providerName"] == "pytdx"
    assert probe["dependencyInstalled"] is True
    assert probe["providerAvailable"] is True
    assert probe["serverReachable"] is True
    assert probe["serverHealth"] == "reachable"
    assert probe["sourceType"] == "public_proxy"
    assert probe["sourceTier"] == "unofficial_public_api"
    assert probe["trustLevel"] == "usable_with_caution"
    assert probe["freshness"] == "delayed"
    assert probe["freshnessExpectation"] == "best_effort_realtime_quote_and_daily_history"
    assert probe["observationOnly"] is True
    assert probe["scoreContributionAllowed"] is False
    assert probe["degradationReason"] is None
    assert probe["missingProviderReason"] is None
    assert probe["supportedCapabilities"] == [
        "cn_history_daily",
        "cn_name_lookup",
        "cn_quote",
        "cn_realtime_quote",
    ]
    assert probe["unsupportedCapabilities"] == [
        "hk_history_daily",
        "hk_quote",
        "us_history_daily",
        "us_quote",
    ]
    assert probe["timeoutSeconds"] == 1.25
    assert isinstance(probe["attemptedAt"], str)
    assert len(_ReachableApi.instances) == 1
    assert _ReachableApi.instances[0].connect_calls == [("119.147.212.81", 7709, 1.25)]
    assert _ReachableApi.instances[0].disconnected is True


def test_pytdx_capability_probe_degrades_cleanly_when_server_is_unreachable() -> None:
    _UnreachableApi.instances.clear()
    fetcher = PytdxFetcher(hosts=[("112.74.214.43", 7727)])
    fetcher._get_pytdx = lambda: _UnreachableApi

    probe = fetcher.probe_capabilities(timeout_seconds=3)

    assert probe["dependencyInstalled"] is True
    assert probe["providerAvailable"] is False
    assert probe["serverReachable"] is False
    assert probe["serverHealth"] == "unreachable"
    assert probe["sourceType"] == "public_proxy"
    assert probe["sourceTier"] == "unofficial_public_api"
    assert probe["trustLevel"] == "unavailable"
    assert probe["freshness"] == "unavailable"
    assert probe["observationOnly"] is True
    assert probe["scoreContributionAllowed"] is False
    assert probe["degradationReason"] == "tdx_server_unreachable"
    assert probe["missingProviderReason"] == "tdx_server_unreachable"
    assert probe["timeoutSeconds"] == 3
    assert isinstance(probe["attemptedAt"], str)
    assert len(_UnreachableApi.instances) == 1
    assert _UnreachableApi.instances[0].connect_calls == [("112.74.214.43", 7727, 3)]
    assert _UnreachableApi.instances[0].disconnected is True


def test_pytdx_source_provenance_stays_non_official() -> None:
    provenance = project_source_provenance(
        source="pytdx",
        source_type="official_public",
        freshness="delayed",
    )

    assert provenance["sourceType"] == "public_proxy"
    assert provenance["sourceLabel"] == "pytdx / 通达信"
    assert provenance["freshnessLabel"] == "延迟"
