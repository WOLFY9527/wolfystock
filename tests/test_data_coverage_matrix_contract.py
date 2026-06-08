# -*- coding: utf-8 -*-
"""Offline tests for the inert Data Coverage Matrix v1 contract."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.services.data_coverage_matrix_contract import (
    DATA_COVERAGE_MATRIX_CONTRACT_VERSION,
    ConsumerDataCoverageProjection,
    ConsumerProductStatus,
    DataCoverageMatrixContract,
    FreshnessState,
    RightToDisplay,
    coerce_data_coverage_matrix_contract,
    project_consumer_data_coverage,
    validate_data_coverage_matrix_contract,
)


def _base_payload() -> dict[str, object]:
    return {
        "surfaceId": "market_overview",
        "routeId": "/zh/market-overview",
        "audience": "consumer",
        "fieldKey": "market_regime",
        "evidenceFamily": "market_regime",
        "providerId": "polygon_primary",
        "providerLabel": "Polygon",
        "sourceId": "us_equities_feed",
        "sourceLabel": "US Equities Feed",
        "sourceType": "authorized_licensed_feed",
        "sourceTier": "official_public",
    }


def test_contract_projects_required_fields_and_fail_closed_defaults() -> None:
    contract = coerce_data_coverage_matrix_contract(_base_payload())
    payload = contract.to_dict()
    issues = {issue.code for issue in validate_data_coverage_matrix_contract(contract).issues}

    assert payload == {
        "contractVersion": DATA_COVERAGE_MATRIX_CONTRACT_VERSION,
        "surfaceId": "market_overview",
        "routeId": "/zh/market-overview",
        "audience": "consumer",
        "fieldKey": "market_regime",
        "evidenceFamily": "market_regime",
        "providerId": "polygon_primary",
        "providerLabel": "Polygon",
        "sourceId": "us_equities_feed",
        "sourceLabel": "US Equities Feed",
        "sourceType": "authorized_licensed_feed",
        "sourceTier": "official_public",
        "freshnessState": "unknown",
        "isFallback": False,
        "isStale": False,
        "isPartial": False,
        "isSynthetic": False,
        "isUnavailable": False,
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "authorityGrant": False,
        "decisionGrade": False,
        "observationOnly": True,
        "rightToDisplay": "unavailable",
        "diagnosticOnly": True,
        "providerRuntimeCalled": False,
        "networkCallsEnabled": False,
        "marketCacheMutation": False,
    }
    assert issues >= {
        "missing_source_authority",
        "missing_score_contribution",
        "missing_right_to_display",
        "unknown_freshness",
    }


@pytest.mark.parametrize(
    ("payload", "expected_right_to_display", "expected_status"),
    [
        ({"freshnessState": "fallback", "isFallback": True}, RightToDisplay.LIMITED, ConsumerProductStatus.PAUSED),
        ({"freshnessState": "stale", "isStale": True}, RightToDisplay.LIMITED, ConsumerProductStatus.DELAYED),
        ({"freshnessState": "partial", "isPartial": True}, RightToDisplay.LIMITED, ConsumerProductStatus.PARTIAL),
        ({"freshnessState": "synthetic", "isSynthetic": True}, RightToDisplay.UNAVAILABLE, ConsumerProductStatus.INSUFFICIENT),
        ({"freshnessState": "unavailable", "isUnavailable": True}, RightToDisplay.UNAVAILABLE, ConsumerProductStatus.UNAVAILABLE),
        ({"freshnessState": "unknown"}, RightToDisplay.LIMITED, ConsumerProductStatus.UPDATING),
    ],
)
def test_degraded_or_unknown_states_fail_closed_even_when_raw_payload_claims_full_grants(
    payload: dict[str, object],
    expected_right_to_display: RightToDisplay,
    expected_status: ConsumerProductStatus,
) -> None:
    contract = coerce_data_coverage_matrix_contract(
        {
            **_base_payload(),
            **payload,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "authorityGrant": True,
            "decisionGrade": True,
            "rightToDisplay": "granted",
        }
    )

    assert contract.source_authority_allowed is True
    assert contract.score_contribution_allowed is False
    assert contract.authority_grant is False
    assert contract.decision_grade is False
    assert contract.observation_only is True
    assert contract.right_to_display is expected_right_to_display

    projection = project_consumer_data_coverage(contract)
    assert projection.status is expected_status


def test_explicit_fresh_reviewed_grants_can_project_available_without_inference() -> None:
    contract = coerce_data_coverage_matrix_contract(
        {
            **_base_payload(),
            "freshnessState": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "authorityGrant": True,
            "decisionGrade": True,
            "rightToDisplay": "granted",
        }
    )
    projection = project_consumer_data_coverage(contract)

    assert contract.source_authority_allowed is True
    assert contract.score_contribution_allowed is True
    assert contract.authority_grant is True
    assert contract.decision_grade is True
    assert contract.observation_only is False
    assert contract.right_to_display is RightToDisplay.GRANTED
    assert projection == ConsumerDataCoverageProjection(
        status=ConsumerProductStatus.AVAILABLE,
        headline=None,
        as_of=None,
        observation_only=False,
    )


def test_consumer_projection_uses_only_bounded_product_states_and_safe_copy() -> None:
    contract = coerce_data_coverage_matrix_contract(
        {
            **_base_payload(),
            "freshnessState": "fallback",
            "isFallback": True,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "authorityGrant": True,
            "decisionGrade": True,
            "rightToDisplay": "granted",
        }
    )

    projection = project_consumer_data_coverage(contract).to_dict()
    serialized = json.dumps(projection, ensure_ascii=False, sort_keys=True)

    assert projection["status"] in {
        "AVAILABLE",
        "UPDATING",
        "DELAYED",
        "PARTIAL",
        "INSUFFICIENT",
        "PAUSED",
        "UNAVAILABLE",
    }
    assert projection["headline"] == "部分数据暂不可用，当前评分已暂停。"
    for forbidden in (
        "sourceAuthorityAllowed",
        "scoreContributionAllowed",
        "observationOnly",
        "official_public",
        "authorized_licensed_feed",
        "Polygon",
        "reasonCode",
        "fallback_static",
        "synthetic_fixture",
        "providerId",
        "sourceType",
    ):
        assert forbidden not in serialized


def test_validator_flags_separation_violations() -> None:
    contract = DataCoverageMatrixContract(
        surface_id="scanner",
        route_id="/zh/scanner",
        audience="consumer",
        field_key="candidate_score",
        evidence_family="scanner_candidate",
        provider_id="manual_provider",
        provider_label="Manual Provider",
        source_id="manual_source",
        source_label="Manual Source",
        source_type="official_public",
        source_tier="official_public",
        freshness_state=FreshnessState.FRESH,
        source_authority_allowed=False,
        source_authority_specified=False,
        score_contribution_allowed=True,
        score_contribution_specified=True,
        authority_grant=True,
        authority_grant_specified=True,
        decision_grade=True,
        decision_grade_specified=True,
        right_to_display=RightToDisplay.GRANTED,
        right_to_display_specified=True,
        observation_only=False,
    )

    issues = {issue.code for issue in validate_data_coverage_matrix_contract(contract).issues}

    assert issues >= {
        "missing_source_authority",
        "score_contribution_without_source_authority",
        "authority_grant_without_prerequisites",
        "decision_grade_without_prerequisites",
    }


def test_module_is_pure_and_inert() -> None:
    module_path = Path("src/services/data_coverage_matrix_contract.py")
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_modules.add(node.module or "")

    assert imported_modules <= {"__future__", "dataclasses", "enum", "typing"}

    script = """
import json
import sys
before = set(sys.modules)
import src.services.data_coverage_matrix_contract  # noqa: F401
after = set(sys.modules) - before
blocked = sorted(
    name for name in after
    if (
        name.startswith("data_provider")
        or name.startswith("api")
        or name.startswith("requests")
        or name.startswith("sqlalchemy")
        or name.startswith("duckdb")
        or name.startswith("aiohttp")
        or name.startswith("src.storage")
        or name.startswith("src.services.market_")
        or name.startswith("src.services.liquidity_")
        or name.startswith("src.services.market_rotation_")
        or name.startswith("src.services.market_scanner_")
    )
)
print(json.dumps(blocked))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == []
