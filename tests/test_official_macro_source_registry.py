# -*- coding: utf-8 -*-
"""Tests for inert official macro source contracts."""

from __future__ import annotations

import json
import subprocess
import sys

from src.services.market_data_source_registry import CANONICAL_SOURCE_TYPES, project_source_provenance
from src.services.official_macro_source_registry import (
    get_official_macro_source,
    get_official_macro_source_for_transport_source,
    list_official_macro_sources,
)


EXPECTED_SOURCE_SERIES = {
    "FRED_BAMLH0A0HYM2": ("BAMLH0A0HYM2",),
    "FRED_VIXCLS": ("VIXCLS",),
    "FRED_DGS2": ("DGS2",),
    "FRED_DGS10": ("DGS10",),
    "FRED_DGS30": ("DGS30",),
    "FRED_SOFR": ("SOFR",),
    "TREASURY_DAILY_RATES": ("BC_2YEAR", "BC_10YEAR", "BC_30YEAR"),
    "NYFED_SOFR": ("SOFR",),
}


def test_registry_contains_expected_contract_ids_in_deterministic_order() -> None:
    contracts = list_official_macro_sources()

    assert [item.source_id for item in contracts] == sorted(EXPECTED_SOURCE_SERIES)


def test_every_contract_uses_existing_official_public_terminology_and_non_live_boundaries() -> None:
    for contract in list_official_macro_sources():
        assert contract.source_id in EXPECTED_SOURCE_SERIES
        assert contract.display_name
        assert contract.source_type == "official_public"
        assert contract.source_type in CANONICAL_SOURCE_TYPES
        assert contract.cadence
        assert contract.expected_freshness_window
        assert contract.series_codes == EXPECTED_SOURCE_SERIES[contract.source_id]
        assert contract.requires_api_key_or_config is False
        assert contract.live_eligible is False
        assert contract.delayed_eligible or contract.observation_only
        assert contract.notes
        assert any("DXY" in note for note in contract.notes)


def test_lookup_is_case_insensitive_and_exposes_expected_series_codes() -> None:
    contract = get_official_macro_source("fred_dgs10")

    assert contract is not None
    assert contract.source_id == "FRED_DGS10"
    assert contract.display_name == "FRED US Treasury 10Y Constant Maturity"
    assert contract.series_codes == ("DGS10",)


def test_transport_source_lookup_maps_runtime_source_ids_back_to_contracts() -> None:
    treasury_contract = get_official_macro_source_for_transport_source("treasury:daily_treasury_yield_curve")
    vix_contract = get_official_macro_source_for_transport_source("fred:VIXCLS")

    assert treasury_contract is not None
    assert treasury_contract.source_id == "TREASURY_DAILY_RATES"
    assert vix_contract is not None
    assert vix_contract.source_id == "FRED_VIXCLS"


def test_official_macro_contracts_project_to_non_live_daily_observation_provenance() -> None:
    delayed = project_source_provenance(source_type="official_public", freshness="delayed")
    stale = project_source_provenance(source_type="official_public", freshness="stale", is_stale=True)

    assert delayed == {
        "sourceType": "official_public",
        "sourceLabel": "公开数据",
        "freshnessLabel": "延迟",
    }
    assert stale == {
        "sourceType": "official_public",
        "sourceLabel": "公开数据",
        "freshnessLabel": "过期",
    }


def test_credit_stress_contract_uses_single_explicit_high_yield_oas_series() -> None:
    contract = get_official_macro_source("FRED_BAMLH0A0HYM2")

    assert contract is not None
    assert contract.display_name == "FRED ICE BofA US High Yield Index Option-Adjusted Spread"
    assert contract.series_codes == ("BAMLH0A0HYM2",)
    assert contract.live_eligible is False
    assert contract.delayed_eligible is True
    assert contract.observation_only is True
    assert any("high yield" in note.lower() for note in contract.notes)
    assert any("not-live" in note.lower() or "not live" in note.lower() for note in contract.notes)


def test_registry_import_has_no_runtime_or_provider_side_effects() -> None:
    script = """
import json
import src.services.official_macro_source_registry
blocked = [
    "src.services.market_cache",
    "src.services.market_overview_service",
    "src.services.liquidity_monitor_service",
    "data_provider.yfinance_fetcher",
    "data_provider.alpaca_fetcher",
    "api.v1.endpoints.market",
]
print(json.dumps({name: name in __import__("sys").modules for name in blocked}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    imported = json.loads(completed.stdout)
    assert imported == {name: False for name in imported}
