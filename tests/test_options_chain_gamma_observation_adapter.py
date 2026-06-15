# -*- coding: utf-8 -*-
"""Options chain to gamma observation adapter tests."""

from __future__ import annotations

import json

import pytest

from src.services.options_chain_gamma_observation_adapter import (
    build_options_chain_gamma_observation,
)
from src.services.options_chain_normalizer import normalize_options_chain
from src.services.options_market_structure_observation import (
    GEX_FORMULA,
    SIGN_CONVENTION,
)


def _normalized_chain(*, freshness: str = "fresh", contract_overrides: list[dict] | None = None):
    contracts = [
        {
            "contractSymbol": "TEST260619C00100000",
            "side": "call",
            "expiration": "2026-06-19",
            "strike": 100,
            "multiplier": 100,
            "openInterest": 100,
            "impliedVolatility": 0.25,
            "greeks": {"gamma": 0.02},
            "asOf": "2026-06-15T14:00:00Z",
            "freshness": freshness,
        },
        {
            "contractSymbol": "TEST260619P00100000",
            "side": "put",
            "expiration": "2026-06-19",
            "strike": 100,
            "multiplier": 100,
            "openInterest": 50,
            "impliedVolatility": 0.25,
            "greeks": {"gamma": 0.01},
            "asOf": "2026-06-15T14:00:00Z",
            "freshness": freshness,
        },
    ]
    for index, override in enumerate(contract_overrides or []):
        contracts[index].update(override)
    return normalize_options_chain(
        {
            "symbol": "TEST",
            "market": "us",
            "currency": "USD",
            "underlying": {
                "price": 100,
                "asOf": "2026-06-15T14:00:00Z",
                "source": "approved_research_snapshot",
                "freshness": freshness,
            },
            "chainAsOf": "2026-06-15T14:00:00Z",
            "source": "approved_research_snapshot",
            "freshness": freshness,
            "contracts": contracts,
        },
        provider_profile="generic",
    )


def _approved_adapter(chain):
    return build_options_chain_gamma_observation(
        chain,
        methodology_approved=True,
        coverage_thresholds_defined=True,
        provider_authority_verified=True,
        redistribution_rights_verified=True,
        decision_use_rights_verified=True,
        deliverable_handling_reviewed=True,
    )


def test_complete_normalized_chain_produces_gex_gamma_observation() -> None:
    result = _approved_adapter(_normalized_chain())

    assert result["adapterName"] == "optionsChainGammaObservationAdapter"
    assert result["status"] == "available"
    assert result["observationOnly"] is True
    assert result["decisionGrade"] is False
    assert result["underlying"] == "TEST"
    assert result["spot"] == 100.0
    assert result["chainAsOf"] == "2026-06-15T14:00:00Z"
    assert result["freshness"] == "fresh"
    assert result["missingEvidence"] == []

    observation = result["observation"]
    assert observation["observationState"] == "ready"
    assert observation["gammaRegime"] == "positive"
    assert observation["gexSummary"]["callGamma"] == pytest.approx(20_000.0)
    assert observation["gexSummary"]["putGamma"] == pytest.approx(-5_000.0)
    assert observation["gexSummary"]["netGamma"] == pytest.approx(15_000.0)
    assert result["inputRecords"][0]["openInterest"] == 100
    assert result["inputRecords"][0]["gamma"] == 0.02

    methodology = result["methodology"]
    assert methodology["formula"] == GEX_FORMULA
    assert methodology["signConvention"] == SIGN_CONVENTION
    assert methodology["observationOnly"] is True
    assert methodology["decisionGrade"] is False
    assert methodology["dataRequirements"] == [
        "underlying",
        "spot",
        "expiration",
        "strike",
        "side",
        "openInterest",
        "gamma",
        "multiplier",
        "asOf",
        "freshness",
    ]


def test_missing_gamma_blocks_without_fabricating_greeks() -> None:
    chain = _normalized_chain(contract_overrides=[{"greeks": {}}])

    result = _approved_adapter(chain)

    assert result["status"] == "blocked"
    assert result["observation"]["observationState"] == "blocked"
    assert result["observation"]["gexSummary"]["netGamma"] is None
    assert "missing_gamma" in result["blockedReasonCodes"]
    assert any(item["code"] == "missing_gamma" for item in result["missingEvidence"])


def test_missing_open_interest_blocks_without_fabricating_oi() -> None:
    chain = _normalized_chain(contract_overrides=[{"openInterest": None}])

    result = _approved_adapter(chain)

    assert result["status"] == "blocked"
    assert "missing_open_interest" in result["blockedReasonCodes"]
    assert any(item["field"] == "openInterest" for item in result["missingEvidence"])


def test_missing_multiplier_blocks_without_defaulting_contract_size() -> None:
    chain = _normalized_chain(contract_overrides=[{"multiplier": None}])

    result = _approved_adapter(chain)

    assert result["status"] == "blocked"
    assert "missing_multiplier" in result["blockedReasonCodes"]
    assert any(item["field"] == "multiplier" for item in result["missingEvidence"])


@pytest.mark.parametrize(
    ("freshness", "expected_code"),
    [("unknown", "unknown_freshness"), ("stale", "stale_freshness")],
)
def test_stale_or_unknown_freshness_degrades_but_keeps_zero_values_as_evidence(
    freshness: str,
    expected_code: str,
) -> None:
    chain = _normalized_chain(
        freshness=freshness,
        contract_overrides=[
            {"openInterest": 0, "greeks": {"gamma": 0}},
            {"openInterest": 0, "greeks": {"gamma": 0}},
        ],
    )

    result = _approved_adapter(chain)

    assert result["status"] == "degraded"
    assert result["observation"]["observationState"] == "ready"
    assert result["observation"]["gexSummary"]["netGamma"] == 0.0
    assert "missing_gamma" not in result["blockedReasonCodes"]
    assert "missing_open_interest" not in result["blockedReasonCodes"]
    assert expected_code in result["blockedReasonCodes"]
    assert any(item["code"] == expected_code for item in result["missingEvidence"])


def test_put_call_sign_convention_is_deterministic() -> None:
    chain = _normalized_chain(
        contract_overrides=[
            {"openInterest": 100, "greeks": {"gamma": 0.02}},
            {"openInterest": 100, "greeks": {"gamma": 0.02}},
        ]
    )

    result = _approved_adapter(chain)

    summary = result["observation"]["gexSummary"]
    assert summary["callGamma"] == pytest.approx(20_000.0)
    assert summary["putGamma"] == pytest.approx(-20_000.0)
    assert summary["netGamma"] == pytest.approx(0.0)
    assert result["methodology"]["signConvention"] == SIGN_CONVENTION


def test_adapter_copy_avoids_advice_support_resistance_and_dealer_book_claims() -> None:
    result = build_options_chain_gamma_observation(_normalized_chain())
    serialized = json.dumps(result, ensure_ascii=False).lower()

    for forbidden in (
        "buy now",
        "sell now",
        "best contract",
        "guaranteed",
        "support level",
        "resistance level",
        "confirmed support",
        "confirmed resistance",
        "dealer book",
        "dealer inventory",
        "actual dealer inventory",
        "true dealer",
    ):
        assert forbidden not in serialized
    assert result["observationOnly"] is True
    assert result["decisionGrade"] is False
