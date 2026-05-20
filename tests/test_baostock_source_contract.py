# -*- coding: utf-8 -*-
"""Drift guards for BaoStock source-confidence capability contracts."""

from __future__ import annotations

from data_provider.baostock_fetcher import BaostockFetcher
from src.services.provider_capability_matrix import list_provider_capability_support_contracts


def test_baostock_contract_capabilities_match_supported_probe_capabilities() -> None:
    contracts = list_provider_capability_support_contracts("baostock")
    contract_capabilities = tuple(sorted(item.capability for item in contracts))

    assert contract_capabilities == tuple(sorted(BaostockFetcher.SUPPORTED_CAPABILITIES))


def test_baostock_contract_capabilities_exclude_unsupported_probe_capabilities() -> None:
    contract_capabilities = {
        item.capability for item in list_provider_capability_support_contracts("baostock")
    }

    assert contract_capabilities.isdisjoint(BaostockFetcher.UNSUPPORTED_CAPABILITIES)


def test_baostock_contracts_remain_cautious_observation_only_metadata() -> None:
    contracts = list_provider_capability_support_contracts("baostock")

    assert contracts
    assert {item.provider_name for item in contracts} == {"baostock"}
    assert {item.provider_id for item in contracts} == {"baostock"}
    assert {item.source_type for item in contracts} == {"public_proxy"}
    assert {item.source_tier for item in contracts} == {"third_party_free_api"}
    assert {item.trust_level for item in contracts} == {"usable_with_caution"}
    assert {item.freshness_expectation for item in contracts} == {"t_plus_1_or_delayed"}
    assert {item.observation_only for item in contracts} == {True}
    assert {item.score_contribution_allowed for item in contracts} == {False}
    assert {item.paid_data_likely_required for item in contracts} == {False}
    assert {item.key_required for item in contracts} == {False}
    assert {item.cache_required for item in contracts} == {True}
    assert {item.background_refresh_recommended for item in contracts} == {True}
    assert {item.degradation_reason for item in contracts} == {"baostock_provider_unavailable"}
    assert {item.missing_provider_reason for item in contracts} == {"baostock_not_installed"}
    assert "official_public" not in {item.source_type for item in contracts}
    assert "exchange_authorized" not in {item.source_tier for item in contracts}
    assert "reliable" not in {item.trust_level for item in contracts}
    assert "live" not in {item.freshness_expectation for item in contracts}
    assert "fresh" not in {item.freshness_expectation for item in contracts}
