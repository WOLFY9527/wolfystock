# -*- coding: utf-8 -*-
"""Offline contracts for CN provider source-confidence capability metadata."""

from __future__ import annotations

import pytest

from src.contracts.source_confidence import ProviderCapabilitySupportContract
from src.services.provider_capability_matrix import (
    get_provider_capability_support_contract,
    list_provider_capability_support_contracts,
)


@pytest.mark.parametrize(
    ("provider_id", "capability", "expected_trust", "expected_missing_reason", "expected_source_tier"),
    [
        ("pytdx", "cn_realtime_quote", "usable_with_caution", "pytdx_not_installed", "unofficial_public_api"),
        ("pytdx", "cn_history_daily", "usable_with_caution", "pytdx_not_installed", "unofficial_public_api"),
        ("akshare", "cn_realtime_snapshot", "weak", "akshare_not_installed", "unofficial_public_api"),
        ("akshare", "hk_history_daily", "weak", "akshare_not_installed", "unofficial_public_api"),
        ("baostock", "cn_history_daily", "usable_with_caution", "baostock_not_installed", "third_party_free_api"),
        ("baostock", "cn_basic_financials", "usable_with_caution", "baostock_not_installed", "third_party_free_api"),
    ],
)
def test_cn_provider_capability_contract_resolves_supported_entries(
    provider_id: str,
    capability: str,
    expected_trust: str,
    expected_missing_reason: str,
    expected_source_tier: str,
) -> None:
    contract = get_provider_capability_support_contract(provider_id, capability)

    assert isinstance(contract, ProviderCapabilitySupportContract)
    assert contract.provider_id == provider_id
    assert contract.provider_name == provider_id
    assert contract.capability == capability
    assert contract.source_type == "public_proxy"
    assert contract.source_tier == expected_source_tier
    assert contract.trust_level == expected_trust
    assert contract.observation_only is True
    assert contract.score_contribution_allowed is False
    assert contract.paid_data_likely_required is False
    assert contract.key_required is False
    assert contract.cache_required is True
    assert contract.background_refresh_recommended is True
    assert contract.degradation_reason is not None
    assert contract.missing_provider_reason == expected_missing_reason


def test_cn_provider_capability_contracts_cover_current_probe_declared_capabilities() -> None:
    pytdx_contracts = list_provider_capability_support_contracts("pytdx")
    akshare_contracts = list_provider_capability_support_contracts("akshare")
    baostock_contracts = list_provider_capability_support_contracts("baostock")

    assert {item.capability for item in pytdx_contracts} == {
        "cn_history_daily",
        "cn_name_lookup",
        "cn_quote",
        "cn_realtime_quote",
    }
    assert {item.capability for item in akshare_contracts} == {
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
    }
    assert {item.capability for item in baostock_contracts} == {
        "cn_adjust_factor",
        "cn_basic_financials",
        "cn_history_daily",
        "cn_index_history_daily",
    }


@pytest.mark.parametrize(
    ("provider_id", "capability"),
    [
        ("pytdx", "hk_history_daily"),
        ("pytdx", "chip_distribution"),
        ("akshare", "cn_quote"),
        ("akshare", "hk_index_quote"),
        ("baostock", "cn_realtime_quote"),
        ("baostock", "hk_history_daily"),
        ("missing", "cn_quote"),
    ],
)
def test_cn_provider_capability_contract_does_not_advertise_unsupported_entries(
    provider_id: str,
    capability: str,
) -> None:
    assert get_provider_capability_support_contract(provider_id, capability) is None


def test_cn_provider_capability_contract_projects_required_camel_case_fields() -> None:
    contract = get_provider_capability_support_contract("akshare", "cn_market_stats")

    assert contract is not None
    assert contract.to_dict() == {
        "providerName": "akshare",
        "providerId": "akshare",
        "capability": "cn_market_stats",
        "sourceType": "public_proxy",
        "sourceTier": "unofficial_public_api",
        "trustLevel": "weak",
        "freshnessExpectation": "best_effort_public_web_quote_snapshot_and_daily_history",
        "observationOnly": True,
        "scoreContributionAllowed": False,
        "paidDataLikelyRequired": False,
        "keyRequired": False,
        "cacheRequired": True,
        "backgroundRefreshRecommended": True,
        "degradationReason": "akshare_provider_unavailable",
        "missingProviderReason": "akshare_not_installed",
    }
