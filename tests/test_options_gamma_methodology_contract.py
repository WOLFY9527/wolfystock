# -*- coding: utf-8 -*-
"""Options gamma methodology readiness contract tests."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from src.services.options_gamma_methodology_contract import (
    OPTIONS_GAMMA_METHODOLOGY_SCHEMA_VERSION,
    OPTIONS_GAMMA_NO_ADVICE_DISCLOSURE,
    assess_options_gamma_methodology_readiness,
)
from src.services.options_market_structure_observation import (
    GEX_FORMULA_ID,
    SIGN_CONVENTION,
)


def _complete_payload(**overrides):
    payload = {
        "symbol": "TEST",
        "spot": 100,
        "asOf": "2026-06-15T14:00:00Z",
        "freshness": "fresh",
        "formulaVersion": GEX_FORMULA_ID,
        "signConvention": SIGN_CONVENTION,
        "coverageThreshold": 90,
        "coverage": 100,
        "providerRights": {
            "providerAuthorityVerified": True,
            "redistributionRightsVerified": True,
            "decisionUseRightsVerified": True,
        },
        "contracts": [
            {
                "contractSymbol": "TEST260619C00100000",
                "side": "call",
                "expiration": "2026-06-19",
                "strike": 100,
                "openInterest": 0,
                "gamma": 0,
                "multiplier": 100,
                "asOf": "2026-06-15T14:00:00Z",
                "freshness": "fresh",
            }
        ],
    }
    payload.update(overrides)
    return payload


def _requirement_states(result):
    return {item["key"]: item["state"] for item in result["dataRequirements"]}


def test_complete_methodology_evidence_is_approved_and_observation_only() -> None:
    result = assess_options_gamma_methodology_readiness(_complete_payload())

    assert result["schemaVersion"] == OPTIONS_GAMMA_METHODOLOGY_SCHEMA_VERSION
    assert result["readiness"] == "approved"
    assert result.get("observationSourceClass") == "live"
    assert result["observationOnly"] is True
    assert result["decisionGrade"] is False
    assert result["formulaVersion"] == GEX_FORMULA_ID
    assert result["signConvention"] == SIGN_CONVENTION
    assert result["missingRequirements"] == []
    assert result["degradedReasons"] == []
    assert result["blockedReasons"] == []
    assert result["noAdviceDisclosure"] == OPTIONS_GAMMA_NO_ADVICE_DISCLOSURE
    assert result.get("dataQuality", {}).get("status") == "approved"
    assert result.get("dataQuality", {}).get("observationSourceClass") == "live"
    assert result.get("dataQuality", {}).get("observationOnly") is True
    assert result.get("dataQuality", {}).get("decisionGrade") is False
    assert result["structureDrilldowns"] == [
        {
            "label": "Stock Structure",
            "route": "/stocks/TEST/structure-decision",
            "section": "optionsGammaObservation",
            "reason": "Open stock structure context for the same underlying.",
        }
    ]
    assert result["scenarioDrilldowns"] == [
        {
            "label": "Scenario Lab",
            "route": "/market/scenario-lab",
            "section": "gammaObservation",
            "reason": "Open scenario context with the current gamma evidence constraints.",
        }
    ]
    assert result["methodologyLinks"] == [
        {
            "label": "Gamma readiness",
            "route": "/options-lab",
            "section": "gammaReadiness",
            "reason": "Review why gamma evidence remains observation-only.",
        },
        {
            "label": "Gamma methodology",
            "route": "/options-lab",
            "section": "gammaMethodology",
            "reason": "Review the methodology limits behind this gamma observation.",
        },
    ]
    assert result["evidenceLinkage"] == {
        "status": "available",
        "structureAvailable": True,
        "scenarioAvailable": True,
        "methodologyAvailable": True,
        "message": "Linked structure, scenario, and methodology context is available for observation-only follow-up.",
    }

    states = _requirement_states(result)
    assert states["openInterest"] == "satisfied"
    assert states["gamma"] == "satisfied"
    assert states["freshness"] == "satisfied"
    assert states["providerRights"] == "satisfied"


def test_zero_gamma_and_open_interest_remain_valid_evidence() -> None:
    result = assess_options_gamma_methodology_readiness(_complete_payload())

    assert result["readiness"] == "approved"
    assert "gamma" not in result["missingRequirements"]
    assert "openInterest" not in result["missingRequirements"]


def test_unknown_freshness_degrades_without_blocking_calculable_evidence() -> None:
    payload = _complete_payload(
        freshness="unknown",
        contracts=[
            {
                **_complete_payload()["contracts"][0],
                "freshness": "unknown",
            }
        ],
    )

    result = assess_options_gamma_methodology_readiness(payload)

    assert result["readiness"] == "degraded"
    assert result["missingRequirements"] == []
    assert "freshness_unknown" in result["degradedReasons"]
    assert result["blockedReasons"] == []
    assert _requirement_states(result)["freshness"] == "degraded"


def test_missing_gamma_open_interest_or_multiplier_blocks_methodology_approval() -> None:
    contract = {
        **_complete_payload()["contracts"][0],
        "gamma": None,
        "openInterest": None,
        "multiplier": None,
    }

    result = assess_options_gamma_methodology_readiness(_complete_payload(contracts=[contract]))

    assert result["readiness"] == "blocked"
    assert {"gamma", "openInterest", "multiplier"}.issubset(result["missingRequirements"])
    assert {
        "missing_gamma",
        "missing_open_interest",
        "missing_multiplier",
    }.issubset(result["blockedReasons"])
    assert _requirement_states(result)["gamma"] == "blocked"


def test_missing_provider_rights_formula_sign_or_threshold_blocks_approval() -> None:
    result = assess_options_gamma_methodology_readiness(
        _complete_payload(
            providerRights={"providerAuthorityVerified": True},
            formulaVersion=None,
            signConvention="unsupported",
            coverageThreshold=None,
        )
    )

    assert result["readiness"] == "blocked"
    assert {
        "providerRights",
        "formulaVersion",
        "signConvention",
        "coverageThreshold",
    }.issubset(result["missingRequirements"])
    assert {
        "provider_rights_incomplete",
        "formula_version_missing",
        "sign_convention_unsupported",
        "coverage_threshold_missing",
    }.issubset(result["blockedReasons"])


def test_missing_option_records_are_unavailable_not_decision_grade() -> None:
    result = assess_options_gamma_methodology_readiness(
        {
            "spot": None,
            "contracts": [],
            "freshness": "unavailable",
        }
    )

    assert result["readiness"] == "unavailable"
    assert result["observationOnly"] is True
    assert result["decisionGrade"] is False
    assert {"strike", "expiration", "side", "openInterest", "gamma", "multiplier"}.issubset(
        result["missingRequirements"]
    )
    assert "options_gamma_evidence_unavailable" in result["blockedReasons"]
    assert result.get("dataQuality", {}).get("status") == "unavailable"
    assert result.get("consumerIssues")
    assert result.get("blockedReasonDetails")
    assert result.get("evidenceLimits")
    assert result["structureDrilldowns"] == []
    assert result["scenarioDrilldowns"] == [
        {
            "label": "Scenario Lab",
            "route": "/market/scenario-lab",
            "section": "gammaObservation",
            "reason": "Open scenario context with the current gamma evidence constraints.",
        }
    ]
    assert result["methodologyLinks"] == [
        {
            "label": "Gamma readiness",
            "route": "/options-lab",
            "section": "gammaReadiness",
            "reason": "Review why gamma evidence remains observation-only.",
        },
        {
            "label": "Gamma methodology",
            "route": "/options-lab",
            "section": "gammaMethodology",
            "reason": "Review the methodology limits behind this gamma observation.",
        },
    ]
    assert result["evidenceLinkage"] == {
        "status": "partial",
        "structureAvailable": False,
        "scenarioAvailable": True,
        "methodologyAvailable": True,
        "message": "Linked scenario and methodology context is available, but ticker-specific structure context is unavailable.",
    }
    serialized_details = json.dumps(result.get("blockedReasonDetails"), ensure_ascii=False).lower()
    serialized_limits = json.dumps(result.get("evidenceLimits"), ensure_ascii=False).lower()
    assert "options_gamma_evidence_unavailable" not in serialized_details
    assert "options_gamma_evidence_unavailable" not in serialized_limits


def test_fixture_source_class_is_explicit_without_promoting_decision_grade() -> None:
    payload = _complete_payload(
        source="synthetic_options_lab_fixture",
        freshness="synthetic_delayed",
        contracts=[
            {
                **_complete_payload()["contracts"][0],
                "source": "synthetic_options_lab_fixture",
                "freshness": "synthetic_delayed",
            }
        ],
    )

    result = assess_options_gamma_methodology_readiness(payload)

    assert result.get("observationSourceClass") == "fixture"
    assert result.get("dataQuality", {}).get("observationSourceClass") == "fixture"
    assert result["observationOnly"] is True
    assert result["decisionGrade"] is False


def test_coverage_below_threshold_degrades_when_core_evidence_is_calculable() -> None:
    result = assess_options_gamma_methodology_readiness(
        _complete_payload(coverage=75, coverageThreshold=90)
    )

    assert result["readiness"] == "degraded"
    assert "coverage_below_threshold" in result["degradedReasons"]
    assert result["blockedReasons"] == []
    assert _requirement_states(result)["coverageThreshold"] == "degraded"


def test_contract_copy_avoids_advice_and_real_inventory_claims() -> None:
    result = assess_options_gamma_methodology_readiness(_complete_payload())
    serialized = json.dumps(result, ensure_ascii=False).lower()

    forbidden_patterns = (
        r"\b" + "b" + r"uy\b",
        r"\b" + "s" + r"ell\b",
        r"\b" + "h" + r"old\b",
        r"\breco" + r"mmendation\b",
        r"\btar" + r"get\b",
        r"\bst" + r"op\b",
        r"\bposition" + r" sizing\b",
        r"\bdealer " + r"book\b",
        r"\bactual dealer " + r"inventory\b",
        r"\btrading " + r"signal\b",
    )
    assert all(re.search(pattern, serialized) is None for pattern in forbidden_patterns)
    assert "observation-only" in serialized


def test_methodology_linkage_routes_are_allowlisted_and_consumer_safe() -> None:
    result = assess_options_gamma_methodology_readiness(_complete_payload())

    routes = {
        *[item["route"] for item in result["structureDrilldowns"]],
        *[item["route"] for item in result["scenarioDrilldowns"]],
        *[item["route"] for item in result["methodologyLinks"]],
    }
    assert routes == {
        "/stocks/TEST/structure-decision",
        "/market/scenario-lab",
        "/options-lab",
    }
    for route in routes:
        assert route.startswith("/")
        assert "://" not in route
        assert "?" not in route
        assert "#" not in route
        assert ".." not in route

    consumer_fields = json.dumps(
        {
            "structureDrilldowns": result["structureDrilldowns"],
            "scenarioDrilldowns": result["scenarioDrilldowns"],
            "methodologyLinks": result["methodologyLinks"],
            "evidenceLinkage": result["evidenceLinkage"],
        },
        ensure_ascii=False,
    ).lower()
    assert "provider_rights_incomplete" not in consumer_fields
    assert "formula_version_missing" not in consumer_fields
    for forbidden in ("buy", "sell", "hold", "target", "stop", "recommendation", "position sizing"):
        assert forbidden not in consumer_fields


def test_contract_is_json_stable_and_deterministic() -> None:
    first = assess_options_gamma_methodology_readiness(_complete_payload())
    second = assess_options_gamma_methodology_readiness(_complete_payload())

    assert first == second
    assert json.loads(json.dumps(first, sort_keys=True)) == first


def test_contract_has_no_provider_runtime_cache_or_endpoint_imports() -> None:
    module_path = Path("src/services/options_gamma_methodology_contract.py")
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    forbidden_modules = (
        "api.",
        "data_provider",
        "requests",
        "src.services.market_cache",
        "src.services.options_market_data_provider",
        "src.services.options_lab_service",
        "src.services.portfolio",
        "src.services.rule_backtest",
        "src.services.market_scanner",
    )
    assert all(
        not imported.startswith(forbidden)
        for imported in imports
        for forbidden in forbidden_modules
    )
