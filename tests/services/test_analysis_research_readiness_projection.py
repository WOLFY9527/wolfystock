# -*- coding: utf-8 -*-
"""Research-readiness projection tests for Home AI analysis responses."""

from __future__ import annotations

from typing import Any

from src.analyzer import AnalysisResult
from src.services.analysis_service import AnalysisService


def _result_with_quality(
    *,
    code: str = "AAPL",
    data_quality_report: dict[str, Any] | None = None,
    structured_overrides: dict[str, Any] | None = None,
    runtime_data: dict[str, Any] | None = None,
    score: int | None = 86,
) -> AnalysisResult:
    structured = {
        "technicals": {
            "status": "ok",
            "source": "polygon_us_grouped_daily",
            "sourceType": "authorized_licensed_feed",
            "sourceTier": "score_grade",
            "trustLevel": "score_grade",
            "freshness": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
        },
        "fundamentals": {
            "status": "ok",
            "source": "fmp",
            "sourceType": "official_public",
            "sourceTier": "score_grade",
            "trustLevel": "score_grade",
            "freshness": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
        },
        "sentiment_analysis": {
            "status": "ok",
            "source": "finnhub",
            "sourceType": "official_public",
            "sourceTier": "score_grade",
            "trustLevel": "score_grade",
            "freshness": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
        },
        "catalyst": {
            "status": "ok",
            "source": "gnews",
            "sourceType": "official_public",
            "sourceTier": "score_grade",
            "trustLevel": "score_grade",
            "freshness": "fresh",
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
        },
        "data_quality_report": data_quality_report or {
            "dataQualityTier": "decision_grade",
            "requiredAvailable": True,
            "confidenceCap": 100,
            "missingRequiredDomains": [],
            "importantDomainsMissing": [],
            "scoreSuppressed": False,
            "stanceGuardrail": "none",
        },
    }
    if structured_overrides:
        structured.update(structured_overrides)
    return AnalysisResult(
        code=code,
        name=code,
        sentiment_score=score,
        trend_prediction="震荡",
        operation_advice="观望",
        decision_type="hold",
        confidence_level="中",
        report_language="zh",
        analysis_summary="研究摘要。",
        technical_analysis="技术面摘要。",
        fundamental_analysis="基本面摘要。",
        news_summary="新闻摘要。",
        risk_warning="风险提示。",
        dashboard={
            "structured_analysis": structured,
            "battle_plan": {"sniper_points": {}},
        },
        runtime_execution={
            "data_quality_report": structured["data_quality_report"],
            "data": runtime_data or {},
        },
    )


def _report_for(result: AnalysisResult) -> dict[str, Any]:
    return AnalysisService()._build_analysis_response(result, query_id="query-123")


def test_home_analysis_response_adds_research_readiness_ready_path() -> None:
    response = _report_for(_result_with_quality())

    readiness = response["researchReadiness"]

    assert response["report"]["researchReadiness"] == readiness
    assert response["report"]["meta"]["researchReadiness"] == readiness
    assert response["report"]["details"]["analysis_result"]["researchReadiness"] == readiness
    assert readiness["researchReady"] is True
    assert readiness["readinessState"] == "ready"
    assert readiness["missingEvidence"] == []
    assert readiness["sourceAuthority"] == "scoreGradeAllowed"
    assert readiness["consumerActionBoundary"] == "no_advice"


def test_home_analysis_partial_orcl_like_path_completes_but_is_not_research_ready() -> None:
    result = _result_with_quality(
        code="ORCL",
        data_quality_report={
            "dataQualityTier": "analysis_grade",
            "requiredAvailable": True,
            "confidenceCap": 70,
            "importantDomainsMissing": ["fundamentals"],
            "scoreSuppressed": False,
            "stanceGuardrail": "observe_only",
            "reasonCodes": ["important_data_missing"],
        },
    )

    response = _report_for(result)
    readiness = response["researchReadiness"]

    assert response["stock_code"] == "ORCL"
    assert response["report"]["details"]["analysis_result"]["score_state"] == "capped"
    assert readiness["researchReady"] is False
    assert readiness["readinessState"] == "insufficient"
    assert "fundamentals" in readiness["missingEvidence"]
    assert "score_cap_active" in readiness["blockingReasons"]


def test_home_analysis_missing_fundamentals_news_and_catalyst_blocks_research_ready() -> None:
    result = _result_with_quality(
        data_quality_report={
            "dataQualityTier": "partial",
            "requiredAvailable": True,
            "confidenceCap": 65,
            "importantDomainsMissing": ["fundamentals", "catalyst_news_event"],
            "optionalMissing": ["news", "sentiment", "detailed_fundamentals"],
            "scoreSuppressed": False,
            "stanceGuardrail": "observe_only",
        },
        structured_overrides={
            "fundamentals": {"status": "missing", "source": None},
            "sentiment_analysis": {"status": "missing", "source": None},
            "catalyst": {"status": "missing", "source": None},
        },
    )

    readiness = _report_for(result)["researchReadiness"]

    assert readiness["researchReady"] is False
    assert readiness["readinessState"] == "insufficient"
    assert readiness["missingEvidence"] == ["fundamentals", "news", "catalyst"]
    assert "missing_required_evidence" in readiness["blockingReasons"]


def test_home_analysis_stale_fallback_proxy_inputs_cap_to_observe_only() -> None:
    result = _result_with_quality(
        data_quality_report={
            "dataQualityTier": "analysis_grade",
            "requiredAvailable": True,
            "confidenceCap": 75,
            "staleSources": ["quote"],
            "reasonCodes": ["stale_required_source", "non_live_required_source"],
            "scoreSuppressed": False,
            "stanceGuardrail": "observe_only",
        },
        structured_overrides={
            "technicals": {
                "status": "partial",
                "source": "yfinance_proxy",
                "sourceType": "public_proxy",
                "freshness": "stale",
                "proxyOnly": True,
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
            },
            "fundamentals": {
                "status": "partial",
                "source": "fallback_cache",
                "sourceType": "fallback",
                "freshness": "fallback",
                "isFallback": True,
                "sourceAuthorityAllowed": True,
                "scoreContributionAllowed": True,
            },
        },
    )

    readiness = _report_for(result)["researchReadiness"]

    assert readiness["researchReady"] is False
    assert readiness["readinessState"] == "observe_only"
    assert readiness["freshnessFloor"] == "fallback"
    assert readiness["sourceAuthority"] == "observationOnly"
    assert "public_proxy_evidence" in readiness["blockingReasons"]
    assert "stale_evidence" in readiness["blockingReasons"]
    assert "fallback_evidence" in readiness["blockingReasons"]
