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
    "FRED_CPIAUCSL": ("CPIAUCSL",),
    "FRED_DFF": ("DFF",),
    "FRED_VIXCLS": ("VIXCLS",),
    "FRED_DGS2": ("DGS2",),
    "FRED_DGS10": ("DGS10",),
    "FRED_DGS30": ("DGS30",),
    "FRED_DTWEXBGS": ("DTWEXBGS",),
    "FRED_PPIACO": ("PPIACO",),
    "FRED_RRPONTSYD": ("RRPONTSYD",),
    "FRED_SOFR": ("SOFR",),
    "FRED_WALCL": ("WALCL",),
    "FRED_WRESBAL": ("WRESBAL",),
    "FRED_WTREGEN": ("WTREGEN",),
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
        assert contract.requires_api_key_or_config is contract.source_id.startswith("FRED_")
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
    fed_funds_contract = get_official_macro_source_for_transport_source("fred:DFF")
    cpi_contract = get_official_macro_source_for_transport_source("fred:CPIAUCSL")
    ppi_contract = get_official_macro_source_for_transport_source("fred:PPIACO")
    usd_contract = get_official_macro_source_for_transport_source("fred:DTWEXBGS")
    walcl_contract = get_official_macro_source_for_transport_source("fred:WALCL")
    rrp_contract = get_official_macro_source_for_transport_source("fred:RRPONTSYD")
    tga_contract = get_official_macro_source_for_transport_source("fred:WTREGEN")
    reserve_contract = get_official_macro_source_for_transport_source("fred:WRESBAL")

    assert treasury_contract is not None
    assert treasury_contract.source_id == "TREASURY_DAILY_RATES"
    assert vix_contract is not None
    assert vix_contract.source_id == "FRED_VIXCLS"
    assert fed_funds_contract is not None
    assert fed_funds_contract.source_id == "FRED_DFF"
    assert cpi_contract is not None
    assert cpi_contract.source_id == "FRED_CPIAUCSL"
    assert ppi_contract is not None
    assert ppi_contract.source_id == "FRED_PPIACO"
    assert usd_contract is not None
    assert usd_contract.source_id == "FRED_DTWEXBGS"
    assert walcl_contract is not None
    assert walcl_contract.source_id == "FRED_WALCL"
    assert rrp_contract is not None
    assert rrp_contract.source_id == "FRED_RRPONTSYD"
    assert tga_contract is not None
    assert tga_contract.source_id == "FRED_WTREGEN"
    assert reserve_contract is not None
    assert reserve_contract.source_id == "FRED_WRESBAL"


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


def test_new_macro_contracts_cover_daily_policy_rate_and_monthly_inflation_releases() -> None:
    fed_funds = get_official_macro_source("fred_dff")
    cpi = get_official_macro_source("fred_cpiaucsl")
    ppi = get_official_macro_source("fred_ppiaco")

    assert fed_funds is not None
    assert fed_funds.display_name == "FRED Federal Funds Effective Rate"
    assert fed_funds.series_codes == ("DFF",)
    assert fed_funds.cadence == "business_daily"
    assert fed_funds.live_eligible is False
    assert fed_funds.delayed_eligible is True

    assert cpi is not None
    assert cpi.display_name == "FRED CPI All Urban Consumers Headline Index"
    assert cpi.series_codes == ("CPIAUCSL",)
    assert cpi.cadence == "monthly"
    assert cpi.live_eligible is False
    assert cpi.delayed_eligible is True

    assert ppi is not None
    assert ppi.display_name == "FRED PPI All Commodities Index"
    assert ppi.series_codes == ("PPIACO",)
    assert ppi.cadence == "monthly"
    assert ppi.live_eligible is False
    assert ppi.delayed_eligible is True


def test_fed_liquidity_contracts_cover_required_official_fred_series() -> None:
    expected = {
        "FRED_WALCL": ("WALCL", "weekly"),
        "FRED_RRPONTSYD": ("RRPONTSYD", "business_daily"),
        "FRED_WTREGEN": ("WTREGEN", "weekly"),
        "FRED_WRESBAL": ("WRESBAL", "weekly"),
    }

    for source_id, (series_id, cadence) in expected.items():
        contract = get_official_macro_source(source_id)

        assert contract is not None
        assert contract.series_codes == (series_id,)
        assert contract.source_type == "official_public"
        assert contract.cadence == cadence
        assert contract.live_eligible is False
        assert contract.delayed_eligible is True
        assert contract.observation_only is False
        assert any("Fed liquidity" in note for note in contract.notes)


def test_usd_pressure_contract_uses_truthful_trade_weighted_label_not_ice_dxy() -> None:
    contract = get_official_macro_source("fred_dtwexbgs")

    assert contract is not None
    assert contract.display_name == "FRED Nominal Broad U.S. Dollar Index"
    assert contract.series_codes == ("DTWEXBGS",)
    assert contract.source_type == "official_public"
    assert contract.cadence == "h10_weekly_release_daily_observations"
    assert "weekly Federal Reserve H.10 release" in contract.expected_freshness_window
    assert contract.live_eligible is False
    assert contract.delayed_eligible is True
    assert contract.observation_only is False
    assert any("trade-weighted" in note.lower() for note in contract.notes)
    assert "ICE DXY" not in contract.display_name
    assert any("not an ICE DXY" in note for note in contract.notes)


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
