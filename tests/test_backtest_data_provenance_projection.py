# -*- coding: utf-8 -*-
"""Tests for the inert backtest data provenance projection helper."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

from src.services.backtest_data_provenance_projection import (
    build_backtest_data_provenance_projection,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = REPO_ROOT / "src/services/backtest_data_provenance_projection.py"
FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "backtest"
    / "rule_backtest_data_provenance_projection_v1.json"
)
EXPECTED_CAPABILITY_STATES = {
    "pointInTimeUniverseMembership": "unavailable",
    "survivorshipBiasSafeUniverseEvidence": "unavailable",
    "delistingInactiveSymbolHandling": "unavailable",
    "splitDividendCorporateActionAdjustedOhlcLineage": "unavailable",
    "adjustmentMethodologyVersion": "unavailable",
    "exchangeCalendarSessionAlignment": "unavailable",
    "symbolIdentifierLineage": "unavailable",
    "vendorSourceProvenance": "unavailable",
    "asOfTimestampPolicy": "unavailable",
    "missingStaleBarPolicy": "unavailable",
    "historicalSnapshotReproducibility": "unavailable",
    "decisionGradeInstitutionalReadiness": "not_ready",
}
FORBIDDEN_IMPORT_PREFIXES = (
    "api",
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib",
    "urllib3",
    "yfinance",
    "src.schemas",
    "src.core",
    "src.services.market_cache",
    "src.services.rule_backtest",
    "src.services.backtest",
    "src.services.provider",
)


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _helper_imports() -> set[str]:
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _assert_guardrails(payload: dict[str, Any]) -> None:
    assert payload["diagnosticOnly"] is True
    assert payload["authorityGrant"] is False
    assert payload["decisionGrade"] is False
    assert payload["institutionalReadinessApproved"] is False
    assert payload["professionalReadinessApproved"] is False
    assert payload["providerCallsExecuted"] is False
    assert payload["dataIngestionExecuted"] is False
    assert payload["engineMathChanged"] is False
    assert payload["runtimeWiringChanged"] is False
    assert payload["apiSchemaChanged"] is False
    assert payload["exportReadbackWiringChanged"] is False


def _assert_capabilities_fail_closed(payload: dict[str, Any]) -> None:
    assert list(payload["capabilities"]) == list(EXPECTED_CAPABILITY_STATES)
    for key, expected_state in EXPECTED_CAPABILITY_STATES.items():
        capability = payload["capabilities"][key]
        assert capability["state"] == expected_state
        assert capability["ready"] is False
        assert capability["available"] is False
        assert isinstance(capability["reasonCode"], str)
        assert capability["reasonCode"]
        assert isinstance(capability["evidenceRequired"], str)
        assert capability["evidenceRequired"]


def _assert_no_forbidden_promotion(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    lowered = serialized.lower()
    for forbidden in (
        '"authorityGrant": true',
        '"decisionGrade": true',
        '"institutionalReadinessApproved": true',
        '"professionalReadinessApproved": true',
        '"providerCallsExecuted": true',
        '"dataIngestionExecuted": true',
        '"engineMathChanged": true',
        '"runtimeWiringChanged": true',
        '"apiSchemaChanged": true',
        '"exportReadbackWiringChanged": true',
        '"pitAdjustedInstitutionalReady": true',
        '"survivorshipBiasSafe": true',
        '"corporateActionAdjustedDataReady": true',
        '"historicalSnapshotReproducible": true',
        '"acceptedAsReadinessEvidence": true',
        '"ready": true',
        '"available": true',
        "institutional proof",
        "professional approval",
        "decision-grade approved",
    ):
        assert forbidden.lower() not in lowered, forbidden


def test_projection_matches_static_fixture_expected_projection() -> None:
    fixture = _load_fixture()
    local_metadata = fixture["input"]["localMetadata"]

    projection = build_backtest_data_provenance_projection(local_metadata)

    assert projection == fixture["expectedProjection"]
    _assert_guardrails(projection)
    _assert_capabilities_fail_closed(projection)
    _assert_no_forbidden_promotion(projection)


def test_projection_is_json_safe_deterministic_and_does_not_mutate_input() -> None:
    local_metadata = _load_fixture()["input"]["localMetadata"]
    original = copy.deepcopy(local_metadata)

    first = build_backtest_data_provenance_projection(local_metadata)
    second = build_backtest_data_provenance_projection(local_metadata)

    assert local_metadata == original
    assert first == second
    assert json.loads(json.dumps(first, ensure_ascii=False, sort_keys=True)) == first


def test_missing_and_unknown_provenance_fields_remain_unavailable_or_not_ready() -> None:
    projection = build_backtest_data_provenance_projection(
        {
            "unknownFutureContract": {"ready": True, "available": True},
            "pointInTimeUniverseMembership": {"state": "available", "ready": True},
            "decisionGrade": True,
            "institutionalReadinessApproved": True,
            "professionalReadinessApproved": True,
        }
    )

    _assert_guardrails(projection)
    _assert_capabilities_fail_closed(projection)
    _assert_no_forbidden_promotion(projection)
    assert projection["metadataObservations"]["acceptedAsReadinessEvidence"] is False
    assert projection["metadataObservations"]["ignoredReadinessClaimKeys"] == [
        "decisionGrade",
        "institutionalReadinessApproved",
        "pointInTimeUniverseMembership",
        "professionalReadinessApproved",
    ]


def test_labels_and_source_names_do_not_grant_authority_or_readiness() -> None:
    projection = build_backtest_data_provenance_projection(
        {
            "source": "local",
            "provider": "yfinance",
            "sourceLabel": "polygon",
            "datasetLabel": "cached fixture",
            "freshness": "cached",
        }
    )

    _assert_guardrails(projection)
    _assert_capabilities_fail_closed(projection)
    assert projection["metadataObservations"]["sourceLabels"] == [
        "cached",
        "cached fixture",
        "local",
        "polygon",
        "yfinance",
    ]
    assert projection["metadataObservations"]["acceptedAsReadinessEvidence"] is False


def test_default_projection_keeps_all_high_risk_capabilities_fail_closed() -> None:
    projection = build_backtest_data_provenance_projection()

    assert projection["metadataObservations"] == {
        "callerSupplied": False,
        "acceptedAsReadinessEvidence": False,
        "recognizedKeys": [],
        "sourceLabels": [],
        "ignoredReadinessClaimKeys": [],
    }
    _assert_guardrails(projection)
    _assert_capabilities_fail_closed(projection)


def test_projection_module_imports_stay_pure_local_and_do_not_touch_runtime_domains() -> None:
    imports = _helper_imports()

    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)
