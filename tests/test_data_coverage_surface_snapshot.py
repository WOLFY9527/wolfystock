# -*- coding: utf-8 -*-
"""Offline tests for inert Data Coverage surface snapshots."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

from src.services.data_coverage_surface_snapshot import (
    DATA_COVERAGE_SURFACE_SNAPSHOT_VERSION,
    build_data_coverage_surface_snapshot,
)


_ALLOWED_CONSUMER_STATES = {
    "AVAILABLE",
    "UPDATING",
    "DELAYED",
    "PARTIAL",
    "INSUFFICIENT",
    "PAUSED",
    "UNAVAILABLE",
}

_FORBIDDEN_CONSUMER_TERMS = (
    "sourceAuthorityAllowed",
    "scoreContributionAllowed",
    "source_authority_allowed",
    "score_contribution_allowed",
    "observationOnly",
    "reasonCode",
    "reason_code",
    "providerId",
    "providerLabel",
    "sourceType",
    "sourceTier",
    "Polygon",
    "Tushare",
    "authorized_licensed_feed",
    "official_public",
    "fallback_static",
    "synthetic_fixture",
)


def _row(
    *,
    surface_id: str,
    route_id: str,
    field_key: str,
    evidence_family: str,
    freshness_state: str = "fresh",
    audience: str = "consumer",
    as_of: str | None = None,
    last_updated: str | None = None,
    source_authority_allowed: bool = True,
    score_contribution_allowed: bool = True,
    authority_grant: bool = True,
    decision_grade: bool = True,
    right_to_display: str = "granted",
    is_fallback: bool = False,
    is_stale: bool = False,
    is_partial: bool = False,
    is_synthetic: bool = False,
    is_unavailable: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "contractVersion": "data_coverage_matrix_v1",
        "surfaceId": surface_id,
        "routeId": route_id,
        "audience": audience,
        "fieldKey": field_key,
        "evidenceFamily": evidence_family,
        "providerId": "polygon_primary",
        "providerLabel": "Polygon",
        "sourceId": f"{surface_id}_source",
        "sourceLabel": f"{surface_id} source",
        "sourceType": "authorized_licensed_feed",
        "sourceTier": "official_public",
        "freshnessState": freshness_state,
        "isFallback": is_fallback,
        "isStale": is_stale,
        "isPartial": is_partial,
        "isSynthetic": is_synthetic,
        "isUnavailable": is_unavailable,
        "sourceAuthorityAllowed": source_authority_allowed,
        "scoreContributionAllowed": score_contribution_allowed,
        "authorityGrant": authority_grant,
        "decisionGrade": decision_grade,
        "rightToDisplay": right_to_display,
    }
    if as_of is not None:
        payload["asOf"] = as_of
    if last_updated is not None:
        payload["lastUpdated"] = last_updated
    return payload


def test_market_overview_rows_project_available_surface_snapshot() -> None:
    snapshot = build_data_coverage_surface_snapshot(
        [
            _row(
                surface_id="market_overview",
                route_id="/zh/market-overview",
                field_key="market_regime",
                evidence_family="market_regime",
                as_of="2026-06-08T09:30:00Z",
                last_updated="2026-06-08T09:31:00Z",
            )
        ]
    )

    assert snapshot.to_dict() == {
        "snapshotVersion": DATA_COVERAGE_SURFACE_SNAPSHOT_VERSION,
        "surfaceId": "market_overview",
        "routeId": "/zh/market-overview",
        "audience": "consumer",
        "consumerState": "AVAILABLE",
        "confidencePosture": "AVAILABLE",
        "consumerSummary": "AVAILABLE",
        "asOf": "2026-06-08T09:30:00Z",
        "lastUpdated": "2026-06-08T09:31:00Z",
        "rowCount": 1,
        "availableRowCount": 1,
        "limitedRowCount": 0,
        "blockedRowCount": 0,
        "unavailableRowCount": 0,
    }


def test_liquidity_fallback_row_pauses_surface_scoring() -> None:
    snapshot = build_data_coverage_surface_snapshot(
        [
            _row(
                surface_id="liquidity",
                route_id="/zh/market/liquidity-monitor",
                field_key="liquidity_score_status",
                evidence_family="liquidity_monitor",
                freshness_state="fallback",
                is_fallback=True,
                as_of="2026-06-08T09:30:00Z",
            )
        ]
    )

    assert snapshot.to_dict() == {
        "snapshotVersion": DATA_COVERAGE_SURFACE_SNAPSHOT_VERSION,
        "surfaceId": "liquidity",
        "routeId": "/zh/market/liquidity-monitor",
        "audience": "consumer",
        "consumerState": "PAUSED",
        "confidencePosture": "INSUFFICIENT",
        "consumerSummary": "PAUSED",
        "asOf": "2026-06-08T09:30:00Z",
        "rowCount": 1,
        "availableRowCount": 0,
        "limitedRowCount": 0,
        "blockedRowCount": 1,
        "unavailableRowCount": 0,
    }


def test_scanner_insufficient_row_fails_closed_for_surface_snapshot() -> None:
    snapshot = build_data_coverage_surface_snapshot(
        [
            _row(
                surface_id="scanner",
                route_id="/zh/scanner",
                field_key="candidate_score_status",
                evidence_family="scanner_candidate",
                source_authority_allowed=False,
            )
        ]
    )

    assert snapshot.consumer_state.value == "INSUFFICIENT"
    assert snapshot.confidence_posture.value == "INSUFFICIENT"
    assert snapshot.blocked_row_count == 1


def test_portfolio_delayed_row_limits_snapshot_without_blocking_display() -> None:
    snapshot = build_data_coverage_surface_snapshot(
        [
            _row(
                surface_id="portfolio",
                route_id="/zh/portfolio",
                field_key="portfolio_read_model_status",
                evidence_family="portfolio_research",
                freshness_state="stale",
                is_stale=True,
                as_of="2026-06-08T09:40:00Z",
                last_updated="2026-06-08T09:42:00Z",
            )
        ]
    )

    assert snapshot.consumer_state.value == "DELAYED"
    assert snapshot.confidence_posture.value == "PARTIAL"
    assert snapshot.as_of == "2026-06-08T09:40:00Z"
    assert snapshot.last_updated == "2026-06-08T09:42:00Z"
    assert snapshot.limited_row_count == 1


def test_backtest_unavailable_row_makes_surface_unavailable() -> None:
    snapshot = build_data_coverage_surface_snapshot(
        [
            _row(
                surface_id="backtest",
                route_id="/zh/backtest",
                field_key="backtest_result_status",
                evidence_family="backtest_research",
                freshness_state="unavailable",
                is_unavailable=True,
            )
        ]
    )

    assert snapshot.consumer_state.value == "UNAVAILABLE"
    assert snapshot.confidence_posture.value == "UNAVAILABLE"
    assert snapshot.unavailable_row_count == 1


def test_surface_or_audience_disagreement_fails_closed() -> None:
    snapshot = build_data_coverage_surface_snapshot(
        [
            _row(
                surface_id="market_overview",
                route_id="/zh/market-overview",
                field_key="market_regime",
                evidence_family="market_regime",
            ),
            _row(
                surface_id="scanner",
                route_id="/zh/scanner",
                field_key="candidate_score_status",
                evidence_family="scanner_candidate",
                audience="admin",
            ),
        ]
    )

    assert snapshot.surface_id == ""
    assert snapshot.route_id == ""
    assert snapshot.audience == ""
    assert snapshot.consumer_state.value == "UNAVAILABLE"
    assert snapshot.confidence_posture.value == "UNAVAILABLE"
    assert snapshot.row_count == 2
    assert snapshot.available_row_count == 0
    assert snapshot.limited_row_count == 0
    assert snapshot.blocked_row_count == 0
    assert snapshot.unavailable_row_count == 2


def test_invalid_or_empty_rows_fail_closed() -> None:
    invalid_snapshot = build_data_coverage_surface_snapshot([{"surfaceId": "scanner"}])
    empty_snapshot = build_data_coverage_surface_snapshot([])

    assert invalid_snapshot.consumer_state.value == "UNAVAILABLE"
    assert invalid_snapshot.unavailable_row_count == 1
    assert empty_snapshot.consumer_state.value == "UNAVAILABLE"
    assert empty_snapshot.row_count == 0


def test_snapshot_consumer_summary_uses_only_bounded_product_state_vocabulary() -> None:
    snapshots = [
        build_data_coverage_surface_snapshot(
            [
                _row(
                    surface_id="market_overview",
                    route_id="/zh/market-overview",
                    field_key="market_regime",
                    evidence_family="market_regime",
                )
            ]
        ),
        build_data_coverage_surface_snapshot(
            [
                _row(
                    surface_id="scanner",
                    route_id="/zh/scanner",
                    field_key="candidate_score_status",
                    evidence_family="scanner_candidate",
                    source_authority_allowed=False,
                )
            ]
        ),
    ]

    for snapshot in snapshots:
        payload = snapshot.to_dict()
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)

        assert payload["consumerState"] in _ALLOWED_CONSUMER_STATES
        assert payload["confidencePosture"] in _ALLOWED_CONSUMER_STATES
        assert payload["consumerSummary"] in _ALLOWED_CONSUMER_STATES
        for forbidden in _FORBIDDEN_CONSUMER_TERMS:
            assert forbidden not in serialized


def test_snapshot_helper_module_is_pure_and_inert() -> None:
    module_path = Path("src/services/data_coverage_surface_snapshot.py")
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_modules.add(node.module or "")

    assert imported_modules <= {
        "__future__",
        "dataclasses",
        "typing",
        "src.services.data_coverage_matrix_contract",
    }

    script = """
import json
import sys
before = set(sys.modules)
import src.services.data_coverage_surface_snapshot  # noqa: F401
after = set(sys.modules) - before
blocked = sorted(
    name for name in after
    if (
        name.startswith("data_provider")
        or name.startswith("api")
        or name.startswith("apps")
        or name.startswith("requests")
        or name.startswith("sqlalchemy")
        or name.startswith("duckdb")
        or name.startswith("aiohttp")
        or name.startswith("src.storage")
        or (
            name.startswith("src.services.")
            and name
            not in {
                "src.services",
                "src.services.data_coverage_surface_snapshot",
                "src.services.data_coverage_matrix_contract",
            }
        )
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
