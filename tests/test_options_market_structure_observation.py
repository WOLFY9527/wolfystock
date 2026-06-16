# -*- coding: utf-8 -*-
"""Pure options market-structure observation helper tests."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import pytest

from api.v1.schemas.options import OptionContract, OptionGreeks
from src.services.options_market_structure_observation import (
    GEX_FORMULA_ID,
    GEX_UNIT_CONVENTION,
    POSITIONING_ASSUMPTION,
    SIGN_CONVENTION,
    build_options_market_structure_observation,
)


INTERNAL_LOOKING_TOKEN = re.compile(r"\b[a-z]+(?:_[a-z0-9]+){1,}\b")


@dataclass
class _GreekFixture:
    gamma: float | None = None
    delta: float | None = None


@dataclass
class _ContractFixture:
    contract_symbol: str
    side: str
    strike: float | None
    expiration: str | None
    gamma: float | None
    open_interest: int | None
    implied_volatility: float | None = 0.32
    multiplier: int | None = 100
    dte: int | None = 0
    freshness: str = "fresh"
    source: str = "approved_live_research_snapshot"

    @property
    def greeks(self) -> _GreekFixture | None:
        if self.gamma is None:
            return None
        return _GreekFixture(gamma=self.gamma)


def _complete_contracts() -> list[_ContractFixture]:
    return [
        _ContractFixture("TEST260619C00095000", "call", 95.0, "2026-06-19", 0.01, 100),
        _ContractFixture("TEST260619P00095000", "put", 95.0, "2026-06-19", 0.02, 100),
        _ContractFixture("TEST260619C00100000", "call", 100.0, "2026-06-19", 0.03, 200),
        _ContractFixture("TEST260619P00100000", "put", 100.0, "2026-06-19", 0.01, 100),
        _ContractFixture("TEST260626C00105000", "call", 105.0, "2026-06-26", 0.02, 300, dte=7),
        _ContractFixture("TEST260626P00105000", "put", 105.0, "2026-06-26", 0.01, 50, dte=7),
    ]


def test_complete_normalized_contracts_emit_observation_only_gex_walls_flip_and_coverage() -> None:
    observation = build_options_market_structure_observation(
        _complete_contracts(),
        spot=100.0,
        as_of="2026-06-15T13:45:00Z",
        data_quality_label="live",
        methodology_approved=True,
        coverage_thresholds_defined=True,
        provider_authority_verified=True,
        redistribution_rights_verified=True,
        decision_use_rights_verified=True,
        deliverable_handling_reviewed=True,
    )

    assert observation["observationOnly"] is True
    assert observation["decisionGrade"] is False
    assert observation["decisionGradeBlocked"] is True
    assert observation["blockedReasonCodes"] == ["observation_only_not_decision_grade"]
    assert observation["observationState"] == "ready"
    assert observation.get("schemaVersion") == "options_gamma_observation_contract_v1"
    assert observation.get("observationSourceClass") == "live"
    assert observation["gammaRegime"] == "positive"
    assert observation["methodology"]["formulaId"] == GEX_FORMULA_ID
    assert observation["methodology"]["unitConvention"] == GEX_UNIT_CONVENTION
    assert observation["methodology"]["signConvention"] == SIGN_CONVENTION
    assert observation["methodology"]["positioningAssumption"] == POSITIONING_ASSUMPTION

    assert observation["gexSummary"]["netGamma"] == pytest.approx(95_000.0)
    assert observation["gexSummary"]["callGamma"] == pytest.approx(130_000.0)
    assert observation["gexSummary"]["putGamma"] == pytest.approx(-35_000.0)
    assert observation["gexSummary"]["grossGamma"] == pytest.approx(165_000.0)
    assert observation["callWall"]["strike"] == 105.0
    assert observation["callWall"]["label"] == "call_gamma_concentration"
    assert observation["putWall"]["strike"] == 95.0
    assert observation["putWall"]["label"] == "put_gamma_concentration"
    assert observation["gammaFlipLevel"] is None
    assert observation["gammaFlipInterval"] == {
        "lowerStrike": 95.0,
        "upperStrike": 100.0,
        "method": "adjacent_strike_bucket_sign_change",
        "confidence": "low",
    }
    assert observation["topGammaStrikes"][0]["strike"] == 105.0
    assert observation["topGammaStrikes"][0]["netGamma"] == pytest.approx(55_000.0)
    assert observation["zeroDTEGammaShare"]["available"] is True
    assert observation["zeroDTEGammaShare"]["share"] == pytest.approx(100_000.0 / 165_000.0)
    assert observation["coverage"]["usableContracts"] == 6
    assert observation["coverage"]["calculationCoveragePct"] == 100.0
    assert observation["missingEvidence"] == []
    assert observation["dataQualityLabels"] == ["live"]
    assert observation.get("dataQuality", {}).get("status") == "ready"
    assert observation.get("dataQuality", {}).get("observationSourceClass") == "live"
    assert observation.get("dataQuality", {}).get("observationOnly") is True
    assert observation.get("dataQuality", {}).get("decisionGrade") is False


def test_missing_core_prerequisites_fail_closed_without_gex_guessing() -> None:
    observation = build_options_market_structure_observation(
        [
            _ContractFixture(
                "BROKEN",
                "call",
                strike=None,
                expiration=None,
                gamma=None,
                open_interest=None,
                implied_volatility=None,
                multiplier=None,
                dte=None,
                freshness="unknown",
                source="fixture_snapshot",
            )
        ],
        spot=None,
    )

    assert observation["observationState"] == "blocked"
    assert observation["gammaRegime"] == "blocked"
    assert observation["gexSummary"]["netGamma"] is None
    assert observation["callWall"] is None
    assert observation["putWall"] is None
    assert observation["topGammaStrikes"] == []
    assert observation["zeroDTEGammaShare"] == {
        "available": False,
        "reason": "expiry_data_unavailable",
    }
    assert {
        "missing_spot_reference",
        "missing_gamma",
        "missing_open_interest",
        "missing_multiplier",
        "missing_strike",
        "missing_expiration",
        "missing_iv",
    }.issubset(set(observation["blockedReasonCodes"]))
    assert "unavailable" in observation["dataQualityLabels"]
    assert observation["consumerIssues"]
    assert observation.get("dataQuality", {}).get("status") == "blocked"
    assert observation.get("blockedReasonDetails")
    assert observation.get("evidenceLimits")
    serialized_issues = json.dumps(observation["consumerIssues"], ensure_ascii=False).lower()
    serialized_details = json.dumps(observation.get("blockedReasonDetails"), ensure_ascii=False).lower()
    serialized_limits = json.dumps(observation.get("evidenceLimits"), ensure_ascii=False).lower()
    for raw_code in ("missing_spot_reference", "insufficient_usable_contracts", "methodology_approval_missing"):
        assert raw_code not in serialized_issues
        assert raw_code not in serialized_details
        assert raw_code not in serialized_limits
    assert all(not INTERNAL_LOOKING_TOKEN.search(item) for item in observation["evidenceLimits"])


def test_partial_contract_coverage_degrades_and_excludes_missing_inputs() -> None:
    observation = build_options_market_structure_observation(
        [
            _ContractFixture("VALID", "call", 100.0, "2026-06-19", 0.02, 10, dte=2),
            _ContractFixture("MISSING_IV", "put", 100.0, "2026-06-19", 0.02, 10, implied_volatility=None, dte=2),
        ],
        spot=50.0,
        data_quality_label="delayed",
    )

    assert observation["observationState"] == "degraded"
    assert observation["gammaRegime"] == "positive"
    assert observation["gexSummary"]["netGamma"] == pytest.approx(500.0)
    assert observation["coverage"]["totalContracts"] == 2
    assert observation["coverage"]["usableContracts"] == 1
    assert observation["coverage"]["excludedContracts"] == 1
    assert observation["coverage"]["ivCoveragePct"] == 50.0
    assert "missing_iv" in observation["blockedReasonCodes"]
    assert observation["missingEvidence"][0]["contractSymbol"] == "MISSING_IV"
    assert observation["dataQualityLabels"] == ["delayed"]
    assert observation["consumerIssues"]
    assert observation.get("dataQuality", {}).get("status") == "degraded"
    assert observation.get("degradedReasonDetails")
    assert observation.get("evidenceLimits")


def test_fixture_source_class_is_explicit_and_keeps_observation_non_live() -> None:
    contracts = [
        _ContractFixture(
            "FIXTURE260619C00100000",
            "call",
            100.0,
            "2026-06-19",
            0.02,
            100,
            freshness="synthetic_fixture",
            source="synthetic_options_lab_fixture",
        )
    ]

    observation = build_options_market_structure_observation(contracts, spot=100.0)

    assert observation.get("observationSourceClass") == "fixture"
    assert observation.get("dataQuality", {}).get("observationSourceClass") == "fixture"
    assert observation["observationOnly"] is True
    assert observation["decisionGrade"] is False


def test_existing_option_contract_schema_is_accepted_without_provider_runtime_coupling() -> None:
    contract = OptionContract(
        symbol="TEST",
        contractSymbol="TEST260619C00100000",
        side="call",
        expiration="2026-06-19",
        strike=100.0,
        multiplier=100,
        bid=1.0,
        ask=1.1,
        mid=1.05,
        volume=20,
        openInterest=10,
        impliedVolatility=0.25,
        greeks=OptionGreeks(gamma=0.02),
        dte=0,
        asOf="2026-06-15T13:45:00Z",
        source="approved_live_research_snapshot",
        freshness="fresh",
    )

    observation = build_options_market_structure_observation([contract], spot=50.0, data_quality_label="live")

    assert observation["coverage"]["usableContracts"] == 1
    assert observation["gexSummary"]["netGamma"] == pytest.approx(500.0)
    assert observation["zeroDTEGammaShare"]["share"] == 1.0


def test_observation_copy_avoids_advice_support_resistance_and_inventory_claims() -> None:
    observation = build_options_market_structure_observation(_complete_contracts(), spot=100.0)
    serialized = json.dumps(observation, ensure_ascii=False).lower()

    for forbidden in (
        "buy now",
        "sell now",
        "must buy",
        "must sell",
        "best contract",
        "guaranteed",
        "support level",
        "resistance level",
        "confirmed support",
        "confirmed resistance",
        "true dealer book",
        "market-maker inventory",
    ):
        assert forbidden not in serialized
    assert "observation-only research context" in serialized
    assert "not personalized financial advice" in serialized
