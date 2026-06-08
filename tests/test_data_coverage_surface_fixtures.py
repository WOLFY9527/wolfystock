# -*- coding: utf-8 -*-
"""Fixture catalog tests for Data Coverage Matrix v1 surface coverage."""

from __future__ import annotations

from pathlib import Path

from src.services.data_coverage_matrix_contract import (
    ConsumerProductStatus,
    RightToDisplay,
    coerce_data_coverage_matrix_contract,
    project_consumer_data_coverage,
    validate_data_coverage_matrix_contract,
)
from src.services.data_coverage_surface_registry import (
    DATA_COVERAGE_SURFACE_REGISTRY,
    DATA_COVERAGE_SURFACE_REGISTRY_BY_SURFACE_FIELD,
)


_DOC_PATH = Path("docs/data-reliability/data-coverage-surface-fixtures.md")
_FORBIDDEN_DOC_TERMS = (
    "providerId",
    "providerLabel",
    "sourceId",
    "sourceLabel",
    "sourceType",
    "sourceTier",
    "sourceAuthorityAllowed",
    "scoreContributionAllowed",
    "authorityGrant",
    "decisionGrade",
    "rightToDisplay",
    "observationOnly",
    "reasonCode",
    "reason_code",
    "rawDiagnostics",
    "raw_diagnostics",
    "provider_name",
    "backend_reason_code",
    "fieldKey",
    "field_key",
    "Polygon",
    "Tushare",
    "authorized_licensed_feed",
    "official_public",
)

_SURFACE_FIXTURE_CASES = (
    {
        "surface_id": "market_overview",
        "field_key": "market_regime",
        "doc_surface": "Market Overview",
        "doc_route": "/zh/market-overview",
        "fixture_state": "更新审查待完成",
        "payload_overrides": {
            "freshnessState": "unknown",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "authorityGrant": True,
            "decisionGrade": True,
            "rightToDisplay": "granted",
        },
        "expected_status": ConsumerProductStatus.UPDATING,
        "expected_headline": "数据更新中，稍后将自动刷新。",
        "expected_right_to_display": RightToDisplay.LIMITED,
        "expected_issue_codes": {"unknown_freshness"},
        "doc_reason": "正在等待更新完成后再恢复完整展示。",
        "doc_copy": "数据更新中，稍后将自动刷新。",
    },
    {
        "surface_id": "liquidity",
        "field_key": "liquidity_score_status",
        "doc_surface": "Liquidity",
        "doc_route": "/zh/market/liquidity-monitor",
        "fixture_state": "降级后暂停评分",
        "payload_overrides": {
            "freshnessState": "fallback",
            "isFallback": True,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "authorityGrant": True,
            "decisionGrade": True,
            "rightToDisplay": "granted",
        },
        "expected_status": ConsumerProductStatus.PAUSED,
        "expected_headline": "部分数据暂不可用，当前评分已暂停。",
        "expected_right_to_display": RightToDisplay.LIMITED,
        "expected_issue_codes": {"degraded_fallback_source"},
        "doc_reason": "部分关键覆盖暂缺，当前评分暂停。",
        "doc_copy": "部分数据暂不可用，当前评分已暂停。",
    },
    {
        "surface_id": "rotation",
        "field_key": "rotation_score_status",
        "doc_surface": "Rotation",
        "doc_route": "/zh/market/rotation-radar",
        "fixture_state": "部分覆盖缺口",
        "payload_overrides": {
            "freshnessState": "partial",
            "isPartial": True,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "authorityGrant": True,
            "decisionGrade": True,
            "rightToDisplay": "granted",
        },
        "expected_status": ConsumerProductStatus.PARTIAL,
        "expected_headline": "部分数据暂不可用。",
        "expected_right_to_display": RightToDisplay.LIMITED,
        "expected_issue_codes": {"degraded_partial_source"},
        "doc_reason": "部分轮动证据缺口仍在，当前结论降级。",
        "doc_copy": "部分数据暂不可用。",
    },
    {
        "surface_id": "scanner",
        "field_key": "candidate_score_status",
        "doc_surface": "Scanner",
        "doc_route": "/zh/scanner",
        "fixture_state": "授权复核未通过",
        "payload_overrides": {
            "freshnessState": "fresh",
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": True,
            "authorityGrant": True,
            "decisionGrade": True,
            "rightToDisplay": "granted",
        },
        "expected_status": ConsumerProductStatus.INSUFFICIENT,
        "expected_headline": "当前信号置信度较低，仅供观察。",
        "expected_right_to_display": RightToDisplay.GRANTED,
        "expected_issue_codes": {
            "score_contribution_without_source_authority",
            "authority_grant_without_prerequisites",
            "decision_grade_without_prerequisites",
        },
        "doc_reason": "独立授权复核尚未完成，候选仅供观察。",
        "doc_copy": "当前信号置信度较低，仅供观察。",
    },
    {
        "surface_id": "single_stock",
        "field_key": "single_stock_summary_status",
        "doc_surface": "Single-stock",
        "doc_route": "/zh",
        "fixture_state": "最近一次可用快照",
        "payload_overrides": {
            "freshnessState": "stale",
            "isStale": True,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "authorityGrant": True,
            "decisionGrade": True,
            "rightToDisplay": "granted",
        },
        "expected_status": ConsumerProductStatus.DELAYED,
        "expected_headline": "已使用最近一次可用数据。",
        "expected_right_to_display": RightToDisplay.LIMITED,
        "expected_issue_codes": {"degraded_stale_source"},
        "doc_reason": "仅保留最近一次可用快照，避免误读为实时结论。",
        "doc_copy": "已使用最近一次可用数据。",
    },
    {
        "surface_id": "watchlist",
        "field_key": "watchlist_readiness_status",
        "doc_surface": "Watchlist",
        "doc_route": "/zh/watchlist",
        "fixture_state": "覆盖暂不可用",
        "payload_overrides": {
            "freshnessState": "unavailable",
            "isUnavailable": True,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "authorityGrant": True,
            "decisionGrade": True,
            "rightToDisplay": "granted",
        },
        "expected_status": ConsumerProductStatus.UNAVAILABLE,
        "expected_headline": "本模块暂不可用，请稍后重试。",
        "expected_right_to_display": RightToDisplay.UNAVAILABLE,
        "expected_issue_codes": {"degraded_unavailable_source"},
        "doc_reason": "当前条目覆盖不可用，先停止展示可行动信号。",
        "doc_copy": "本模块暂不可用，请稍后重试。",
    },
    {
        "surface_id": "portfolio",
        "field_key": "portfolio_read_model_status",
        "doc_surface": "Portfolio",
        "doc_route": "/zh/portfolio",
        "fixture_state": "仅剩代理覆盖",
        "payload_overrides": {
            "freshnessState": "synthetic",
            "isSynthetic": True,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "authorityGrant": True,
            "decisionGrade": True,
            "rightToDisplay": "granted",
        },
        "expected_status": ConsumerProductStatus.INSUFFICIENT,
        "expected_headline": "当前信号置信度较低，仅供观察。",
        "expected_right_to_display": RightToDisplay.UNAVAILABLE,
        "expected_issue_codes": {"degraded_synthetic_source"},
        "doc_reason": "当前仅有代理覆盖，不能作为完整研究结论。",
        "doc_copy": "当前信号置信度较低，仅供观察。",
    },
    {
        "surface_id": "backtest",
        "field_key": "backtest_result_status",
        "doc_surface": "Backtest",
        "doc_route": "/zh/backtest",
        "fixture_state": "展示复核未完成",
        "payload_overrides": {
            "freshnessState": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "authorityGrant": True,
            "decisionGrade": True,
        },
        "expected_status": ConsumerProductStatus.UNAVAILABLE,
        "expected_headline": "本模块暂不可用，请稍后重试。",
        "expected_right_to_display": RightToDisplay.UNAVAILABLE,
        "expected_issue_codes": {
            "missing_right_to_display",
            "authority_grant_without_prerequisites",
            "decision_grade_without_prerequisites",
        },
        "doc_reason": "展示复核尚未完成，结果先保持关闭。",
        "doc_copy": "本模块暂不可用，请稍后重试。",
    },
    {
        "surface_id": "options",
        "field_key": "options_setup_status",
        "doc_surface": "Options",
        "doc_route": "/zh/options-lab",
        "fixture_state": "策略仅供观察",
        "payload_overrides": {
            "freshnessState": "fresh",
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": True,
            "authorityGrant": True,
            "decisionGrade": True,
            "rightToDisplay": "granted",
        },
        "expected_status": ConsumerProductStatus.INSUFFICIENT,
        "expected_headline": "当前信号置信度较低，仅供观察。",
        "expected_right_to_display": RightToDisplay.GRANTED,
        "expected_issue_codes": {
            "score_contribution_without_source_authority",
            "authority_grant_without_prerequisites",
            "decision_grade_without_prerequisites",
        },
        "doc_reason": "缺少独立授权复核，策略结论只能作为观察提示。",
        "doc_copy": "当前信号置信度较低，仅供观察。",
    },
)


def _build_payload(surface_id: str, field_key: str, overrides: dict[str, object]) -> dict[str, object]:
    entry = DATA_COVERAGE_SURFACE_REGISTRY_BY_SURFACE_FIELD[(surface_id, field_key)]
    return {
        "surfaceId": entry.surface_id,
        "routeId": entry.route_id,
        "audience": entry.audience.value,
        "fieldKey": entry.field_key,
        "evidenceFamily": entry.evidence_family,
        "providerId": "fixture_provider",
        "providerLabel": "Fixture Provider",
        "sourceId": f"{entry.surface_id}_fixture_source",
        "sourceLabel": f"{entry.surface_id} fixture source",
        "sourceType": "fixture_source",
        "sourceTier": "fixture_only",
        **overrides,
    }


def test_surface_fixture_catalog_covers_every_registered_surface_once() -> None:
    registry_keys = {(entry.surface_id, entry.field_key) for entry in DATA_COVERAGE_SURFACE_REGISTRY}
    fixture_keys = {(case["surface_id"], case["field_key"]) for case in _SURFACE_FIXTURE_CASES}

    assert len(_SURFACE_FIXTURE_CASES) == 9
    assert fixture_keys == registry_keys


def test_surface_fixture_catalog_projects_consumer_safe_fail_closed_states() -> None:
    for case in _SURFACE_FIXTURE_CASES:
        payload = _build_payload(case["surface_id"], case["field_key"], case["payload_overrides"])
        contract = coerce_data_coverage_matrix_contract(payload)
        issues = {
            issue.code for issue in validate_data_coverage_matrix_contract(payload).issues
        }
        projection = project_consumer_data_coverage(payload)

        assert contract.surface_id == case["surface_id"]
        assert contract.field_key == case["field_key"]
        assert contract.observation_only is True
        assert contract.right_to_display is case["expected_right_to_display"]
        assert projection.status is case["expected_status"]
        assert projection.headline == case["expected_headline"]
        assert case["expected_issue_codes"] <= issues


def test_surface_fixture_doc_matches_catalog_and_stays_consumer_safe() -> None:
    content = _DOC_PATH.read_text(encoding="utf-8")

    for required in (
        "# Data Coverage Surface Fixtures",
        "## Registry Coverage",
        "## Row-State Fixture Catalog",
        "## Consumer Copy Guardrails",
        "UPDATING",
        "PAUSED",
        "PARTIAL",
        "INSUFFICIENT",
        "DELAYED",
        "UNAVAILABLE",
    ):
        assert required in content

    for case in _SURFACE_FIXTURE_CASES:
        row = (
            f"| {case['doc_surface']} | `{case['doc_route']}` | {case['fixture_state']} | "
            f"`{case['expected_status'].value}` | {case['doc_reason']} | `{case['doc_copy']}` |"
        )
        assert row in content

    for forbidden in _FORBIDDEN_DOC_TERMS:
        assert forbidden not in content
