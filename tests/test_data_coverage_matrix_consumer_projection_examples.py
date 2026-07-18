# -*- coding: utf-8 -*-
"""Consumer projection fixture examples for Data Coverage Matrix v1."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.services.data_coverage_matrix_contract import project_consumer_data_coverage


_DOC_PATH = Path("docs/AI_PROJECT_MANUAL.md")
_FORBIDDEN_CONSUMER_TERMS = (
    "sourceAuthorityAllowed",
    "scoreContributionAllowed",
    "source_authority_allowed",
    "score_contribution_allowed",
    "observationOnly",
    "reasonCode",
    "reason_code",
    "reasonFamilies",
    "rawDiagnostics",
    "raw_diagnostics",
    "providerId",
    "providerLabel",
    "provider_id",
    "provider_label",
    "sourceType",
    "sourceTier",
    "source_type",
    "source_tier",
    "Polygon",
    "Tushare",
    "authorized_licensed_feed",
    "official_public",
    "fallback_static",
    "synthetic_fixture",
)


def _base_fixture(*, surface_id: str, route_id: str, field_key: str, evidence_family: str) -> dict[str, object]:
    return {
        "surfaceId": surface_id,
        "routeId": route_id,
        "audience": "consumer",
        "fieldKey": field_key,
        "evidenceFamily": evidence_family,
        "providerId": "polygon_primary",
        "providerLabel": "Polygon",
        "sourceId": f"{surface_id}_source",
        "sourceLabel": f"{surface_id} source",
        "sourceType": "authorized_licensed_feed",
        "sourceTier": "official_public",
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": True,
        "authorityGrant": True,
        "decisionGrade": True,
        "rightToDisplay": "granted",
        "reasonCode": "provider_unavailable",
        "reasonFamilies": ["freshness", "display"],
        "rawDiagnostics": {
            "provider_name": "Polygon",
            "backend_reason_code": "provider_unavailable",
            "source_authority_allowed": True,
            "score_contribution_allowed": True,
        },
    }


@pytest.mark.parametrize(
    ("fixture", "expected_status", "expected_headline"),
    [
        (
            {
                **_base_fixture(
                    surface_id="market_overview",
                    route_id="/zh/market-overview",
                    field_key="market_regime",
                    evidence_family="market_regime",
                ),
                "freshnessState": "fresh",
                "asOf": "2026-06-08T09:30:00Z",
            },
            "AVAILABLE",
            None,
        ),
        (
            {
                **_base_fixture(
                    surface_id="liquidity",
                    route_id="/zh/liquidity",
                    field_key="capital_flow",
                    evidence_family="capital_flow",
                ),
                "freshnessState": "partial",
                "isPartial": True,
                "asOf": "2026-06-08T09:35:00Z",
            },
            "PARTIAL",
            "部分数据暂不可用。",
        ),
        (
            {
                **_base_fixture(
                    surface_id="scanner",
                    route_id="/zh/scanner",
                    field_key="candidate_score",
                    evidence_family="scanner_candidate",
                ),
                "freshnessState": "fresh",
                "sourceAuthorityAllowed": False,
                "scoreContributionAllowed": True,
                "authorityGrant": True,
                "decisionGrade": True,
                "source_authority_allowed": False,
                "score_contribution_allowed": True,
                "asOf": "2026-06-08T09:40:00Z",
            },
            "INSUFFICIENT",
            "当前信号置信度较低，仅供观察。",
        ),
        (
            {
                **_base_fixture(
                    surface_id="portfolio",
                    route_id="/zh/portfolio",
                    field_key="pricing_snapshot",
                    evidence_family="portfolio_pricing",
                ),
                "freshnessState": "delayed",
                "asOf": "2026-06-08T09:45:00Z",
            },
            "DELAYED",
            "已使用最近一次可用数据。",
        ),
        (
            {
                **_base_fixture(
                    surface_id="backtest",
                    route_id="/zh/backtest",
                    field_key="run_snapshot",
                    evidence_family="backtest_run",
                ),
                "freshnessState": "unavailable",
                "isUnavailable": True,
                "asOf": "2026-06-08T09:50:00Z",
            },
            "UNAVAILABLE",
            "本模块暂不可用，请稍后重试。",
        ),
    ],
    ids=[
        "market-overview-available",
        "liquidity-partial",
        "scanner-insufficient",
        "portfolio-delayed",
        "backtest-unavailable",
    ],
)
def test_consumer_projection_examples_stay_product_safe(
    fixture: dict[str, object],
    expected_status: str,
    expected_headline: str | None,
) -> None:
    projection = project_consumer_data_coverage(fixture).to_dict()
    serialized = json.dumps(projection, ensure_ascii=False, sort_keys=True)

    assert projection == {
        "status": expected_status,
        "headline": expected_headline,
        "asOf": fixture["asOf"],
    }
    for forbidden in _FORBIDDEN_CONSUMER_TERMS:
        assert forbidden not in serialized


def test_consumer_projection_examples_doc_stays_product_language() -> None:
    manual = _DOC_PATH.read_text(encoding="utf-8")
    heading = "## Data Coverage Consumer Projection"
    start = manual.index(heading)
    end = manual.find("\n## ", start + len(heading))
    content = manual[start:] if end == -1 else manual[start:end]

    for required in (
        "## Data Coverage Consumer Projection",
        "Market Overview",
        "Liquidity",
        "Scanner",
        "Portfolio",
        "Backtest",
        "AVAILABLE",
        "PARTIAL",
        "INSUFFICIENT",
        "DELAYED",
        "UNAVAILABLE",
        "部分数据暂不可用。",
        "当前信号置信度较低，仅供观察。",
        "已使用最近一次可用数据。",
        "本模块暂不可用，请稍后重试。",
    ):
        assert required in content

    for forbidden in _FORBIDDEN_CONSUMER_TERMS:
        assert forbidden not in content
