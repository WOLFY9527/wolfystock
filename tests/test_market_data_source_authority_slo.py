# -*- coding: utf-8 -*-
"""Offline tests for the inert market-data source-authority SLO matrix."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.services.market_data_source_authority_slo import (
    EXPECTED_SOURCE_AUTHORITY_FIELDS,
    MARKET_DATA_SOURCE_AUTHORITY_SLO_MATRIX,
    MARKET_DATA_SOURCE_AUTHORITY_SLO_VERSION,
    ConsumerProductStatus,
    FreshnessState,
    MarketDataSourceAuthorityFeature,
    SourceAuthoritySloReadiness,
    SourceAuthoritySloRiskLevel,
    evaluate_market_data_source_authority_slo,
    get_market_data_source_authority_slo_expectation,
    get_market_data_source_authority_slo_matrix,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = REPO_ROOT / "src/services/market_data_source_authority_slo.py"

FORBIDDEN_IMPORT_PREFIXES = (
    "api",
    "apps",
    "data_provider",
    "fastapi",
    "httpx",
    "requests",
    "sqlalchemy",
    "urllib",
    "urllib3",
    "yfinance",
    "src.config",
    "src.repositories",
    "src.storage",
    "src.services.analysis_service",
    "src.services.data_source_router",
    "src.services.liquidity_monitor_service",
    "src.services.market_cache",
    "src.services.market_overview_service",
    "src.services.market_rotation_radar_service",
    "src.services.market_scanner_service",
    "src.services.provider_circuit_observer",
    "src.services.rotation_radar_quote_provider",
    "src.services.scanner_ai_service",
    "src.services.watchlist_service",
)


def _base_ready_fixture(feature_id: str) -> dict[str, object]:
    return {
        "featureId": feature_id,
        "freshness": "fresh",
        "sourceStates": ["fresh"],
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": True,
        "authorityGrant": True,
        "decisionGrade": True,
        "rightToDisplay": "granted",
        "observationOnly": False,
        "consumerSafeProjection": True,
        "confidenceWeight": 0.95,
    }


def _collect_imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def test_matrix_is_complete_stable_and_inert() -> None:
    matrix = get_market_data_source_authority_slo_matrix()

    assert matrix == MARKET_DATA_SOURCE_AUTHORITY_SLO_MATRIX
    assert len(matrix) == 5
    assert [entry.feature_id for entry in matrix] == [
        MarketDataSourceAuthorityFeature.MARKET_OVERVIEW,
        MarketDataSourceAuthorityFeature.LIQUIDITY,
        MarketDataSourceAuthorityFeature.ROTATION,
        MarketDataSourceAuthorityFeature.SCANNER,
        MarketDataSourceAuthorityFeature.WATCHLIST,
    ]
    assert len({entry.feature_id for entry in matrix}) == len(matrix)

    for entry in matrix:
        assert entry.contract_version == MARKET_DATA_SOURCE_AUTHORITY_SLO_VERSION
        assert entry.endpoint_ids
        assert entry.expected_fields == EXPECTED_SOURCE_AUTHORITY_FIELDS
        assert set(entry.expected_fields) == {
            "freshnessState",
            "isFallback",
            "isStale",
            "sourceAuthorityAllowed",
            "scoreContributionAllowed",
            "authorityGrant",
            "observationOnly",
            "rightToDisplay",
            "consumerSafeProjection",
        }
        assert entry.consumer_safe_projection_required is True
        assert entry.consumer_safe_projection_expectations
        assert entry.diagnostic_only is True
        assert entry.provider_runtime_called is False
        assert entry.api_called is False
        assert entry.network_calls_enabled is False
        assert entry.market_cache_mutation is False


def test_market_overview_is_marked_higher_risk_partial_until_contract_is_uniform() -> None:
    expectation = get_market_data_source_authority_slo_expectation("market_overview")
    evaluation = evaluate_market_data_source_authority_slo(_base_ready_fixture("market_overview"))

    assert expectation.feature_label == "Market Overview"
    assert expectation.current_contract_uniform is False
    assert expectation.risk_level is SourceAuthoritySloRiskLevel.HIGHER_RISK_PARTIAL
    assert "market_overview_contract_not_uniform" in expectation.partial_reason_codes

    assert evaluation.readiness is SourceAuthoritySloReadiness.PARTIAL
    assert evaluation.consumer_status is ConsumerProductStatus.PARTIAL
    assert evaluation.source_authority_allowed is False
    assert evaluation.score_contribution_allowed is False
    assert evaluation.observation_only is True
    assert evaluation.data_coverage_row["contractVersion"] == MARKET_DATA_SOURCE_AUTHORITY_SLO_VERSION
    assert evaluation.data_coverage_row["rightToDisplay"] == "limited"
    assert "market_overview_contract_not_uniform" in evaluation.reason_codes


def test_ready_fixture_is_allowed_only_when_all_reviews_and_projection_are_present() -> None:
    evaluation = evaluate_market_data_source_authority_slo(_base_ready_fixture("liquidity"))

    payload = evaluation.to_dict()

    assert payload["contractVersion"] == MARKET_DATA_SOURCE_AUTHORITY_SLO_VERSION
    assert payload["featureId"] == "liquidity"
    assert payload["readiness"] == "ready"
    assert payload["consumerStatus"] == "AVAILABLE"
    assert payload["reasonCodes"] == []
    assert payload["validationIssueCodes"] == []
    assert payload["sourceAuthorityAllowed"] is True
    assert payload["scoreContributionAllowed"] is True
    assert payload["observationOnly"] is False
    assert payload["rightToDisplay"] == "granted"
    assert payload["expectationRiskLevel"] == "standard"
    assert payload["currentContractUniform"] is True
    assert payload["diagnosticOnly"] is True
    assert payload["providerRuntimeCalled"] is False
    assert payload["apiCalled"] is False
    assert payload["networkCallsEnabled"] is False
    assert payload["marketCacheMutation"] is False
    assert payload["dataCoverageRow"]["contractVersion"] == MARKET_DATA_SOURCE_AUTHORITY_SLO_VERSION
    assert payload["dataCoverageRow"]["authorityGrant"] is True
    assert payload["dataCoverageRow"]["decisionGrade"] is True


@pytest.mark.parametrize(
    (
        "payload_overrides",
        "expected_reason",
        "expected_readiness",
        "expected_consumer_status",
    ),
    [
        (
            {"freshness": "stale", "isStale": True},
            "stale_source_state",
            SourceAuthoritySloReadiness.BLOCKED,
            ConsumerProductStatus.DELAYED,
        ),
        (
            {"freshness": "live", "isFallback": True},
            "fallback_source_state",
            SourceAuthoritySloReadiness.BLOCKED,
            ConsumerProductStatus.PAUSED,
        ),
        (
            {"freshness": "fresh", "sourceStates": ["fresh", "fallback"]},
            "mixed_source_state",
            SourceAuthoritySloReadiness.BLOCKED,
            ConsumerProductStatus.PARTIAL,
        ),
        (
            {"freshness": "fresh", "confidenceWeight": 0.2},
            "low_confidence",
            SourceAuthoritySloReadiness.BLOCKED,
            ConsumerProductStatus.INSUFFICIENT,
        ),
        (
            {"freshness": "partial", "isPartial": True},
            "partial_source_state",
            SourceAuthoritySloReadiness.PARTIAL,
            ConsumerProductStatus.PARTIAL,
        ),
        (
            {"freshness": "synthetic", "isSynthetic": True},
            "synthetic_source_state",
            SourceAuthoritySloReadiness.BLOCKED,
            ConsumerProductStatus.UNAVAILABLE,
        ),
        (
            {"freshness": "unavailable", "isUnavailable": True},
            "unavailable_source_state",
            SourceAuthoritySloReadiness.BLOCKED,
            ConsumerProductStatus.UNAVAILABLE,
        ),
    ],
)
def test_degraded_fixtures_fail_closed_even_when_raw_input_claims_authority(
    payload_overrides: dict[str, object],
    expected_reason: str,
    expected_readiness: SourceAuthoritySloReadiness,
    expected_consumer_status: ConsumerProductStatus,
) -> None:
    payload = _base_ready_fixture("scanner")
    payload.update(payload_overrides)

    evaluation = evaluate_market_data_source_authority_slo(payload)

    assert expected_reason in evaluation.reason_codes
    assert evaluation.readiness is expected_readiness
    assert evaluation.consumer_status is expected_consumer_status
    assert evaluation.source_authority_allowed is False
    assert evaluation.score_contribution_allowed is False
    assert evaluation.observation_only is True
    assert evaluation.data_coverage_row["sourceAuthorityAllowed"] is False
    assert evaluation.data_coverage_row["scoreContributionAllowed"] is False
    assert evaluation.data_coverage_row["authorityGrant"] is False
    assert evaluation.data_coverage_row["decisionGrade"] is False
    assert evaluation.provider_runtime_called is False
    assert evaluation.api_called is False
    assert evaluation.market_cache_mutation is False


@pytest.mark.parametrize(
    ("payload_overrides", "expected_reason"),
    [
        ({"freshness": "fresh", "sourceAuthorityAllowed": False}, "missing_source_authority"),
        ({"freshness": "fresh", "scoreContributionAllowed": False}, "missing_score_contribution"),
        ({"freshness": "fresh", "consumerSafeProjection": False}, "missing_consumer_safe_projection"),
        ({"freshness": "unknown"}, "unknown_freshness"),
        ({"freshness": "fresh", "confidenceWeight": None}, "missing_confidence_weight"),
    ],
)
def test_missing_required_slo_fields_fail_closed(
    payload_overrides: dict[str, object],
    expected_reason: str,
) -> None:
    payload = _base_ready_fixture("rotation")
    payload.update(payload_overrides)

    evaluation = evaluate_market_data_source_authority_slo(payload)

    assert expected_reason in evaluation.reason_codes
    assert evaluation.source_authority_allowed is False
    assert evaluation.score_contribution_allowed is False
    assert evaluation.observation_only is True


def test_raw_provider_debug_source_state_is_normalized_to_fail_closed_reason_codes() -> None:
    evaluation = evaluate_market_data_source_authority_slo(
        {
            **_base_ready_fixture("watchlist"),
            "sourceStates": [
                "provider_payload_session_cookie",
                "cache_stale",
                "fallback_source",
                "route_runtime_debug",
            ],
        }
    )
    serialized = json.dumps(evaluation.to_dict(), ensure_ascii=False, sort_keys=True)

    assert "unknown_source_state" in evaluation.reason_codes
    assert "mixed_source_state" in evaluation.reason_codes
    assert evaluation.source_authority_allowed is False
    assert evaluation.score_contribution_allowed is False
    assert evaluation.observation_only is True

    for raw_fragment in ("provider_payload", "session_cookie", "cache_stale", "fallback_source", "runtime_debug"):
        assert raw_fragment not in serialized


def test_feature_lookup_unknown_key_fails_closed_by_exception() -> None:
    with pytest.raises(LookupError):
        get_market_data_source_authority_slo_expectation("portfolio")

    with pytest.raises(LookupError):
        evaluate_market_data_source_authority_slo({"featureId": "portfolio"})


def test_helper_imports_stay_pure_and_inert() -> None:
    imports = _collect_imported_modules(HELPER_PATH)
    violations = {
        module
        for module in imports
        for prefix in FORBIDDEN_IMPORT_PREFIXES
        if module == prefix or module.startswith(f"{prefix}.")
    }

    assert imports <= {
        "__future__",
        "dataclasses",
        "enum",
        "typing",
        "src.services.data_coverage_matrix_builder",
        "src.services.data_coverage_matrix_contract",
    }
    assert not violations

    script = """
import json
import sys
before = set(sys.modules)
import src.services.market_data_source_authority_slo  # noqa: F401
after = set(sys.modules) - before
blocked = sorted(
    name for name in after
    if (
        name.startswith("api")
        or name.startswith("apps")
        or name.startswith("data_provider")
        or name.startswith("fastapi")
        or name.startswith("requests")
        or name.startswith("sqlalchemy")
        or name.startswith("src.storage")
        or name.startswith("src.services.market_cache")
        or name.startswith("src.services.market_overview_service")
        or name.startswith("src.services.liquidity_monitor_service")
        or name.startswith("src.services.market_rotation_radar_service")
        or name.startswith("src.services.market_scanner_service")
        or name.startswith("src.services.watchlist_service")
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


def test_observation_mapping_accepts_enum_inputs_without_runtime_dependencies() -> None:
    evaluation = evaluate_market_data_source_authority_slo(
        {
            **_base_ready_fixture(MarketDataSourceAuthorityFeature.LIQUIDITY.value),
            "freshness": FreshnessState.FRESH,
        }
    )

    assert evaluation.feature_id is MarketDataSourceAuthorityFeature.LIQUIDITY
    assert evaluation.readiness is SourceAuthoritySloReadiness.READY
