# -*- coding: utf-8 -*-
"""Offline contracts for the CN provider health snapshot service."""

from __future__ import annotations

from src.services.cn_provider_health_service import CNProviderHealthService
from src.services.provider_capability_matrix import list_provider_capability_support_contracts


def _entry_by_provider(snapshot: tuple, provider_id: str):
    return next(item for item in snapshot if item.provider_id == provider_id)


def test_cn_provider_health_snapshot_degrades_cleanly_when_both_providers_are_missing() -> None:
    service = CNProviderHealthService(
        pytdx_probe=lambda timeout_seconds: {
            "providerName": "pytdx",
            "providerId": "pytdx",
            "dependencyInstalled": False,
            "providerAvailable": False,
            "supportedCapabilities": [
                "cn_history_daily",
                "cn_name_lookup",
                "cn_quote",
                "cn_realtime_quote",
            ],
            "unsupportedCapabilities": ["hk_history_daily", "us_quote"],
            "degradationReason": "pytdx_not_installed",
            "missingProviderReason": "pytdx_not_installed",
            "attemptedAt": None,
            "timeoutSeconds": timeout_seconds,
            "serverHealth": "missing_dependency",
        },
        akshare_probe=lambda timeout_seconds: {
            "providerName": "akshare",
            "providerId": "akshare",
            "dependencyInstalled": False,
            "providerAvailable": False,
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
            "unsupportedCapabilities": ["us_realtime_quote", "hk_index_quote"],
            "degradationReason": "akshare_not_installed",
            "missingProviderReason": "akshare_not_installed",
            "attemptedAt": None,
            "timeoutSeconds": timeout_seconds,
            "interfaceHealth": "missing_dependency",
        },
    )

    snapshot = service.get_snapshot(timeout_seconds=2.5)

    assert [item.provider_id for item in snapshot] == ["pytdx", "akshare"]

    pytdx = _entry_by_provider(snapshot, "pytdx")
    assert pytdx.trust_level == "usable_with_caution"
    assert pytdx.dependency_installed is False
    assert pytdx.provider_available is False
    assert pytdx.health_status == "missing_dependency"
    assert pytdx.missing_provider_reason == "pytdx_not_installed"
    assert pytdx.observation_only is True
    assert pytdx.score_contribution_allowed is False
    assert pytdx.contract_capabilities == (
        "cn_history_daily",
        "cn_name_lookup",
        "cn_quote",
        "cn_realtime_quote",
    )

    akshare = _entry_by_provider(snapshot, "akshare")
    assert akshare.trust_level == "weak"
    assert akshare.dependency_installed is False
    assert akshare.provider_available is False
    assert akshare.health_status == "missing_dependency"
    assert akshare.missing_provider_reason == "akshare_not_installed"
    assert akshare.observation_only is True
    assert akshare.score_contribution_allowed is False
    assert akshare.contract_capabilities == (
        "chip_distribution",
        "cn_etf_history_daily",
        "cn_etf_realtime_quote",
        "cn_history_daily",
        "cn_index_quote",
        "cn_market_stats",
        "cn_realtime_quote",
        "cn_realtime_snapshot",
        "cn_sector_rankings",
        "cn_stock_list",
        "hk_history_daily",
        "hk_realtime_quote",
    )


def test_cn_provider_health_snapshot_supports_mixed_pytdx_healthy_akshare_missing_state() -> None:
    service = CNProviderHealthService(
        pytdx_probe=lambda timeout_seconds: {
            "providerName": "pytdx",
            "providerId": "pytdx",
            "dependencyInstalled": True,
            "providerAvailable": True,
            "supportedCapabilities": [
                "cn_history_daily",
                "cn_name_lookup",
                "cn_quote",
                "cn_realtime_quote",
            ],
            "unsupportedCapabilities": ["hk_history_daily", "us_quote"],
            "degradationReason": None,
            "missingProviderReason": None,
            "attemptedAt": "2026-05-19T02:03:04+00:00",
            "timeoutSeconds": timeout_seconds,
            "serverHealth": "reachable",
        },
        akshare_probe=lambda timeout_seconds: {
            "providerName": "akshare",
            "providerId": "akshare",
            "dependencyInstalled": False,
            "providerAvailable": False,
            "supportedCapabilities": ["cn_stock_list"],
            "unsupportedCapabilities": ["us_realtime_quote"],
            "degradationReason": "akshare_not_installed",
            "missingProviderReason": "akshare_not_installed",
            "attemptedAt": None,
            "timeoutSeconds": timeout_seconds,
            "interfaceHealth": "missing_dependency",
        },
    )

    snapshot = service.get_snapshot(timeout_seconds=1.25)

    pytdx = _entry_by_provider(snapshot, "pytdx")
    assert pytdx.health_status == "healthy"
    assert pytdx.provider_available is True
    assert pytdx.attempted_at == "2026-05-19T02:03:04+00:00"
    assert pytdx.supported_capabilities == (
        "cn_history_daily",
        "cn_name_lookup",
        "cn_quote",
        "cn_realtime_quote",
    )
    assert pytdx.timeout_seconds == 1.25

    akshare = _entry_by_provider(snapshot, "akshare")
    assert akshare.health_status == "missing_dependency"
    assert akshare.provider_available is False
    assert akshare.attempted_at is None
    assert akshare.score_contribution_allowed is False


def test_cn_provider_health_snapshot_degrades_cleanly_when_akshare_probe_fails() -> None:
    service = CNProviderHealthService(
        pytdx_probe=lambda timeout_seconds: {
            "providerName": "pytdx",
            "providerId": "pytdx",
            "dependencyInstalled": True,
            "providerAvailable": True,
            "supportedCapabilities": [
                "cn_history_daily",
                "cn_name_lookup",
                "cn_quote",
                "cn_realtime_quote",
            ],
            "unsupportedCapabilities": [],
            "degradationReason": None,
            "missingProviderReason": None,
            "attemptedAt": "2026-05-19T00:00:00+00:00",
            "timeoutSeconds": timeout_seconds,
            "serverHealth": "reachable",
        },
        akshare_probe=lambda timeout_seconds: (_ for _ in ()).throw(RuntimeError("upstream page changed")),
    )

    snapshot = service.get_snapshot(timeout_seconds=3.0)

    akshare = _entry_by_provider(snapshot, "akshare")
    assert akshare.health_status == "probe_failure"
    assert akshare.provider_available is False
    assert akshare.dependency_installed is True
    assert akshare.degradation_reason == "akshare_probe_failed"
    assert akshare.missing_provider_reason == "akshare_probe_failed"
    assert akshare.score_contribution_allowed is False
    assert akshare.contract_capabilities == (
        "chip_distribution",
        "cn_etf_history_daily",
        "cn_etf_realtime_quote",
        "cn_history_daily",
        "cn_index_quote",
        "cn_market_stats",
        "cn_realtime_quote",
        "cn_realtime_snapshot",
        "cn_sector_rankings",
        "cn_stock_list",
        "hk_history_daily",
        "hk_realtime_quote",
    )


def test_cn_provider_health_snapshot_reports_both_providers_healthy_without_promoting_scoring() -> None:
    service = CNProviderHealthService(
        pytdx_probe=lambda timeout_seconds: {
            "providerName": "pytdx",
            "providerId": "pytdx",
            "dependencyInstalled": True,
            "providerAvailable": True,
            "supportedCapabilities": [
                "cn_history_daily",
                "cn_name_lookup",
                "cn_quote",
                "cn_realtime_quote",
            ],
            "unsupportedCapabilities": ["us_history_daily"],
            "degradationReason": None,
            "missingProviderReason": None,
            "attemptedAt": "2026-05-19T00:00:00+00:00",
            "timeoutSeconds": timeout_seconds,
            "serverHealth": "reachable",
        },
        akshare_probe=lambda timeout_seconds: {
            "providerName": "akshare",
            "providerId": "akshare",
            "dependencyInstalled": True,
            "providerAvailable": True,
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
            "unsupportedCapabilities": ["hk_index_quote"],
            "degradationReason": None,
            "missingProviderReason": None,
            "attemptedAt": "2026-05-19T00:00:01+00:00",
            "timeoutSeconds": timeout_seconds,
            "interfaceHealth": "ok",
        },
    )

    snapshot = service.get_snapshot(timeout_seconds=4.0)

    assert all(item.health_status == "healthy" for item in snapshot)
    assert all(item.observation_only is True for item in snapshot)
    assert all(item.score_contribution_allowed is False for item in snapshot)
    assert {item.trust_level for item in snapshot} == {"usable_with_caution", "weak"}


def test_cn_provider_health_snapshot_aligns_probe_supported_capabilities_with_contract_capabilities() -> None:
    service = CNProviderHealthService(
        pytdx_probe=lambda timeout_seconds: {
            "providerName": "pytdx",
            "providerId": "pytdx",
            "dependencyInstalled": True,
            "providerAvailable": True,
            "supportedCapabilities": [
                "cn_history_daily",
                "cn_name_lookup",
                "cn_quote",
                "cn_realtime_quote",
                "hk_realtime_quote",
            ],
            "unsupportedCapabilities": ["us_history_daily"],
            "degradationReason": None,
            "missingProviderReason": None,
            "attemptedAt": "2026-05-19T00:00:00+00:00",
            "timeoutSeconds": timeout_seconds,
            "serverHealth": "reachable",
        },
        akshare_probe=lambda timeout_seconds: {
            "providerName": "akshare",
            "providerId": "akshare",
            "dependencyInstalled": True,
            "providerAvailable": True,
            "supportedCapabilities": ["cn_stock_list", "unknown_capability"],
            "unsupportedCapabilities": ["hk_index_quote"],
            "degradationReason": None,
            "missingProviderReason": None,
            "attemptedAt": "2026-05-19T00:00:01+00:00",
            "timeoutSeconds": timeout_seconds,
            "interfaceHealth": "ok",
        },
    )

    snapshot = service.get_snapshot(timeout_seconds=2.0)

    pytdx = _entry_by_provider(snapshot, "pytdx")
    akshare = _entry_by_provider(snapshot, "akshare")

    assert pytdx.supported_capabilities == (
        "cn_history_daily",
        "cn_name_lookup",
        "cn_quote",
        "cn_realtime_quote",
    )
    assert akshare.supported_capabilities == ("cn_stock_list",)
    assert all(item in entry.contract_capabilities for entry in snapshot for item in entry.supported_capabilities)


def test_cn_provider_health_snapshot_does_not_promote_unsupported_capabilities_into_contract_capabilities() -> None:
    service = CNProviderHealthService(
        pytdx_probe=lambda timeout_seconds: {
            "providerName": "pytdx",
            "providerId": "pytdx",
            "dependencyInstalled": True,
            "providerAvailable": True,
            "supportedCapabilities": ["cn_quote"],
            "unsupportedCapabilities": ["cn_sector_rankings", "hk_history_daily"],
            "degradationReason": None,
            "missingProviderReason": None,
            "attemptedAt": "2026-05-19T00:00:00+00:00",
            "timeoutSeconds": timeout_seconds,
            "serverHealth": "reachable",
        },
        akshare_probe=lambda timeout_seconds: {
            "providerName": "akshare",
            "providerId": "akshare",
            "dependencyInstalled": True,
            "providerAvailable": True,
            "supportedCapabilities": ["cn_market_stats"],
            "unsupportedCapabilities": ["us_history_daily", "us_realtime_quote"],
            "degradationReason": None,
            "missingProviderReason": None,
            "attemptedAt": "2026-05-19T00:00:01+00:00",
            "timeoutSeconds": timeout_seconds,
            "interfaceHealth": "ok",
        },
    )

    snapshot = service.get_snapshot(timeout_seconds=2.0)

    pytdx = _entry_by_provider(snapshot, "pytdx")
    akshare = _entry_by_provider(snapshot, "akshare")

    assert "cn_sector_rankings" not in pytdx.contract_capabilities
    assert "us_history_daily" not in akshare.contract_capabilities
    assert pytdx.to_dict()["healthStatus"] == "healthy"
    assert akshare.to_dict()["scoreContributionAllowed"] is False


def test_cn_provider_health_snapshot_contract_capabilities_remain_contract_backed_only() -> None:
    service = CNProviderHealthService(
        pytdx_probe=lambda timeout_seconds: {
            "providerName": "pytdx",
            "providerId": "pytdx",
            "dependencyInstalled": True,
            "providerAvailable": True,
            "supportedCapabilities": [
                "cn_history_daily",
                "cn_name_lookup",
                "cn_quote",
                "cn_realtime_quote",
                "hk_realtime_quote",
            ],
            "unsupportedCapabilities": ["hk_history_daily", "us_history_daily"],
            "degradationReason": None,
            "missingProviderReason": None,
            "attemptedAt": "2026-05-19T00:00:00+00:00",
            "timeoutSeconds": timeout_seconds,
            "serverHealth": "reachable",
        },
        akshare_probe=lambda timeout_seconds: {
            "providerName": "akshare",
            "providerId": "akshare",
            "dependencyInstalled": True,
            "providerAvailable": True,
            "supportedCapabilities": [
                "cn_stock_list",
                "cn_market_stats",
                "unknown_capability",
            ],
            "unsupportedCapabilities": ["hk_index_quote", "us_realtime_quote"],
            "degradationReason": None,
            "missingProviderReason": None,
            "attemptedAt": "2026-05-19T00:00:01+00:00",
            "timeoutSeconds": timeout_seconds,
            "interfaceHealth": "ok",
        },
    )

    snapshot = service.get_snapshot(timeout_seconds=2.0)

    for entry in snapshot:
        expected_contract_capabilities = tuple(
            item.capability for item in list_provider_capability_support_contracts(entry.provider_id)
        )
        assert entry.contract_capabilities == expected_contract_capabilities
        assert set(entry.supported_capabilities).issubset(set(entry.contract_capabilities))
        assert set(entry.unsupported_capabilities).isdisjoint(set(entry.contract_capabilities))
