# -*- coding: utf-8 -*-
"""Options chain normalizer contract tests."""

from __future__ import annotations

import pytest

from src.services.options_chain_normalizer import normalize_options_chain
from src.services.options_market_structure_observation import (
    build_options_market_structure_observation,
)


def test_generic_fixture_like_chain_normalizes_contracts_for_observation_contract() -> None:
    chain = normalize_options_chain(
        {
            "symbol": "AAPL",
            "market": "us",
            "currency": "USD",
            "underlying": {
                "price": "190.25",
                "asOf": "2026-06-15T14:00:00Z",
                "source": "delayed_fixture",
                "freshness": "delayed",
            },
            "chainAsOf": "2026-06-15T14:01:00Z",
            "source": "delayed_fixture",
            "freshness": "delayed",
            "contracts": [
                {
                    "contractSymbol": "AAPL260619C00190000",
                    "side": "call",
                    "expiration": "2026-06-19",
                    "strike": "190",
                    "multiplier": "100",
                    "bid": "5.20",
                    "ask": "5.60",
                    "last": "5.35",
                    "volume": "120",
                    "openInterest": "880",
                    "impliedVolatility": "0.31",
                    "greeks": {
                        "delta": "0.52",
                        "gamma": "0.024",
                        "vega": "0.18",
                        "theta": "-0.04",
                    },
                },
                {
                    "contractSymbol": "AAPL260619P00190000",
                    "side": "put",
                    "expiration": "2026-06-19",
                    "strike": 190,
                    "multiplier": 100,
                    "bid": 4.9,
                    "ask": 5.1,
                    "last": 5.0,
                    "volume": 95,
                    "open_interest": 640,
                    "implied_volatility": 0.33,
                    "gamma": 0.026,
                },
            ],
        },
        provider_profile="generic",
    )

    assert chain.underlying_symbol == "AAPL"
    assert chain.observation_only is True
    assert chain.decision_grade is False
    assert chain.underlying_spot == 190.25
    assert chain.chain_as_of == "2026-06-15T14:01:00Z"
    assert chain.source == "delayed_fixture"
    assert chain.freshness == "delayed"
    assert chain.data_quality_labels == ["delayed"]
    assert chain.missing_evidence == []
    assert chain.coverage["gammaCoveragePct"] == 100.0

    call = chain.contracts[0]
    assert call.symbol == "AAPL"
    assert call.contract_symbol == "AAPL260619C00190000"
    assert call.mid == 5.4
    assert call.spread_pct == pytest.approx(7.41)
    assert call.liquidity_bucket == "tight"
    assert call.greeks is not None
    assert call.greeks.gamma == 0.024
    assert call.dte == 4

    observation = build_options_market_structure_observation(
        chain.contracts,
        spot=chain.underlying_spot,
        data_quality_label=chain.data_quality_labels,
    )

    assert observation["coverage"]["usableContracts"] == 2
    assert observation["missingEvidence"] == []
    assert observation["gexSummary"]["grossGamma"] is not None
    assert observation["decisionGrade"] is False


def test_missing_prerequisites_are_tracked_without_fabricating_greeks_or_multiplier() -> None:
    chain = normalize_options_chain(
        {
            "symbol": "BROKEN",
            "underlying": {"asOf": "2026-06-15T14:00:00Z"},
            "chainAsOf": "2026-06-15T14:00:00Z",
            "contracts": [
                {
                    "contractSymbol": "BROKEN_UNKNOWN",
                    "bid": 1.0,
                    "ask": 1.2,
                    "freshness": "unknown",
                }
            ],
        },
        provider_profile="generic",
    )

    contract = chain.contracts[0]
    assert contract.greeks is None
    assert contract.multiplier is None
    assert contract.freshness == "unknown"
    assert chain.data_quality_labels == ["unavailable"]

    missing_codes = {item["code"] for item in chain.missing_evidence}
    assert {
        "missing_spot_reference",
        "missing_side",
        "missing_strike",
        "missing_expiration",
        "missing_open_interest",
        "missing_gamma",
        "missing_multiplier",
    }.issubset(missing_codes)

    observation = build_options_market_structure_observation(
        chain.contracts,
        spot=chain.underlying_spot,
        data_quality_label=chain.data_quality_labels,
    )

    assert observation["observationState"] == "blocked"
    assert observation["gexSummary"]["netGamma"] is None
    assert "missing_gamma" in observation["blockedReasonCodes"]
    assert "missing_multiplier" in observation["blockedReasonCodes"]


def test_zero_gamma_and_open_interest_are_preserved_as_present_evidence() -> None:
    chain = normalize_options_chain(
        {
            "symbol": "ZERO",
            "underlying": {
                "price": 10,
                "asOf": "2026-06-15T14:00:00Z",
                "freshness": "fresh",
            },
            "contracts": [
                {
                    "contractSymbol": "ZERO260619C00010000",
                    "side": "call",
                    "expiration": "2026-06-19",
                    "strike": 10,
                    "multiplier": 100,
                    "bid": 0,
                    "ask": 0.05,
                    "volume": 0,
                    "openInterest": 0,
                    "impliedVolatility": 0,
                    "greeks": {"gamma": 0, "delta": 0, "theta": 0, "vega": 0},
                }
            ],
        }
    )

    contract = chain.contracts[0]
    assert contract.bid == 0
    assert contract.volume == 0
    assert contract.open_interest == 0
    assert contract.implied_volatility == 0
    assert contract.greeks is not None
    assert contract.greeks.gamma == 0
    assert contract.greeks.delta == 0
    assert {item["code"] for item in chain.missing_evidence} == set()


def test_polygon_snapshot_like_profile_maps_nested_snapshot_without_live_authority() -> None:
    chain = normalize_options_chain(
        {
            "ticker": "MSFT",
            "underlying_asset": {
                "ticker": "MSFT",
                "price": 412.5,
                "last_updated": "2026-06-15T14:02:00Z",
            },
            "results": [
                {
                    "details": {
                        "ticker": "O:MSFT260619C00410000",
                        "expiration_date": "2026-06-19",
                        "strike_price": 410,
                        "contract_type": "call",
                        "shares_per_contract": 100,
                    },
                    "last_quote": {
                        "bid": 8.1,
                        "ask": 8.7,
                        "last_updated": "2026-06-15T14:02:00Z",
                    },
                    "last_trade": {"price": 8.35},
                    "day": {"volume": 315},
                    "open_interest": 2200,
                    "implied_volatility": 0.28,
                    "greeks": {
                        "delta": 0.57,
                        "gamma": 0.018,
                        "theta": -0.05,
                        "vega": 0.21,
                    },
                }
            ],
        },
        provider_profile="polygon_snapshot_like",
        source="polygon_snapshot_fixture",
        freshness="delayed",
        as_of="2026-06-15T14:02:00Z",
    )

    assert chain.provider_profile == "polygon_snapshot_like"
    assert chain.provider_quality == "observation_only_not_decision_grade"
    assert chain.metadata["liveProviderEnabled"] is False
    assert chain.metadata["providerAuthorityVerified"] is False
    assert chain.missing_evidence == []

    contract = chain.contracts[0]
    assert contract.contract_symbol == "O:MSFT260619C00410000"
    assert contract.side == "call"
    assert contract.expiration == "2026-06-19"
    assert contract.strike == 410.0
    assert contract.multiplier == 100
    assert contract.bid == 8.1
    assert contract.ask == 8.7
    assert contract.mid == 8.4
    assert contract.last == 8.35
    assert contract.volume == 315
    assert contract.open_interest == 2200
    assert contract.implied_volatility == 0.28
    assert contract.greeks is not None
    assert contract.greeks.gamma == 0.018


def test_tradier_like_profile_maps_option_list_and_preserves_unknown_freshness() -> None:
    chain = normalize_options_chain(
        {
            "underlying": {
                "symbol": "TEM",
                "last": 52.4,
                "trade_date": "2026-05-06T13:45:00Z",
            },
            "options": {
                "option": [
                    {
                        "symbol": "TEM260619P00050000",
                        "option_type": "put",
                        "expiration_date": "2026-06-19",
                        "strike": "50.0",
                        "multiplier": "100",
                        "bid": "2.35",
                        "ask": "2.65",
                        "last": "2.50",
                        "volume": "155",
                        "open_interest": "710",
                        "greeks": {
                            "mid_iv": "0.64",
                            "delta": "-0.39",
                            "gamma": "0.047",
                            "theta": "-0.061",
                            "vega": "0.116",
                        },
                    }
                ]
            },
        },
        provider_profile="tradier_like",
        source="tradier_fixture",
    )

    assert chain.underlying_symbol == "TEM"
    assert chain.underlying_spot == 52.4
    assert chain.chain_as_of == "2026-05-06T13:45:00Z"
    assert chain.source == "tradier_fixture"
    assert chain.freshness == "unknown"
    assert chain.data_quality_labels == ["unavailable"]
    assert chain.metadata["decisionGrade"] is False

    contract = chain.contracts[0]
    assert contract.contract_symbol == "TEM260619P00050000"
    assert contract.side == "put"
    assert contract.expiration == "2026-06-19"
    assert contract.strike == 50.0
    assert contract.mid == 2.5
    assert contract.open_interest == 710
    assert contract.implied_volatility == 0.64
    assert contract.greeks is not None
    assert contract.greeks.delta == -0.39
    assert contract.greeks.gamma == 0.047
    assert chain.missing_evidence == []
