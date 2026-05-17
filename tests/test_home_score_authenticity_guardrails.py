# -*- coding: utf-8 -*-
"""Home analysis score authenticity guardrail regressions."""

from __future__ import annotations

import inspect
from types import SimpleNamespace

from src.analyzer import AnalysisResult
from src.core.pipeline import StockAnalysisPipeline
from src.services.analysis_service import AnalysisService


def _analysis_result(
    *,
    score: int | None = 88,
    operation_advice: str = "买入",
    decision_type: str = "buy",
    confidence_level: str = "高",
) -> AnalysisResult:
    return AnalysisResult(
        code="AAPL",
        name="Apple",
        sentiment_score=score,
        trend_prediction="看多",
        operation_advice=operation_advice,
        decision_type=decision_type,
        confidence_level=confidence_level,
        report_language="zh",
        analysis_summary="LLM 给出积极结论。",
        risk_warning="风险可控。",
        dashboard={
            "battle_plan": {
                "sniper_points": {
                    "ideal_buy": "180-182",
                    "secondary_buy": "176",
                    "stop_loss": "170",
                    "take_profit": "196",
                },
                "position_strategy": {"entry_plan": "突破后分批建仓"},
            },
            "core_conclusion": {
                "one_sentence": "技术突破后可以积极关注。",
                "position_advice": {"no_position": "分批建仓", "has_position": "继续持有"},
            },
            "decision_context": {"score_breakdown": [{"label": "技术分", "score": 78}]},
            "structured_analysis": {
                "data_quality": {"missing_fields": []},
                "data_quality_report": {},
            },
        },
    )


def _insufficient_report() -> dict:
    return {
        "dataQualityTier": "insufficient",
        "requiredAvailable": False,
        "confidenceCap": 40,
        "reasonCodes": ["required_data_missing", "required_technical_history_missing"],
        "missingRequiredDomains": ["price_ohlcv", "technical_history"],
        "scoreSuppressed": True,
        "scoreSuppressedReason": "required_evidence_missing",
        "stanceGuardrail": "no_score",
        "keyLevelGuardrail": "ungrounded",
    }


def test_process_single_stock_applies_quality_caps_after_stabilization() -> None:
    source = inspect.getsource(StockAnalysisPipeline.analyze_stock)

    assert source.index("_stabilize_analysis_result(") < source.rindex("_apply_data_quality_caps(")


def test_required_evidence_missing_suppresses_score_stance_and_levels() -> None:
    result = _analysis_result(score=91)

    StockAnalysisPipeline._apply_data_quality_caps(result, _insufficient_report())

    assert result.sentiment_score is None
    assert result.operation_advice == "数据不足，禁止判断"
    assert result.trend_prediction == "数据不足，禁止判断"
    assert result.decision_type == "data_insufficient"
    assert result.confidence_level == "低"
    assert result.dashboard["battle_plan"]["sniper_points"] == {
        "ideal_buy": "待补充",
        "secondary_buy": "待补充",
        "stop_loss": "待补充",
        "take_profit": "待补充",
    }
    structured = result.dashboard["structured_analysis"]
    assert structured["score_authenticity"]["scoreSuppressed"] is True
    assert structured["score_authenticity"]["missingRequiredDomains"] == ["price_ohlcv", "technical_history"]


def test_partial_evidence_caps_score_confidence_and_forces_watch() -> None:
    result = _analysis_result(score=86, operation_advice="买入", decision_type="buy", confidence_level="高")
    report = {
        "dataQualityTier": "analysis_grade",
        "requiredAvailable": True,
        "confidenceCap": 70,
        "reasonCodes": ["important_data_missing"],
        "importantMissing": ["fundamentals.revenue", "fundamentals.eps"],
        "scoreSuppressed": False,
        "stanceGuardrail": "observe_only",
        "keyLevelGuardrail": "grounded",
    }

    StockAnalysisPipeline._apply_data_quality_caps(result, report)

    assert result.sentiment_score == 70
    assert result.operation_advice == "观望"
    assert result.decision_type == "hold"
    assert result.confidence_level == "低"
    assert result.dashboard["structured_analysis"]["score_authenticity"]["scoreCapped"] is True


def test_weak_technical_evidence_marks_llm_levels_ungrounded() -> None:
    result = _analysis_result(score=64, operation_advice="持有", decision_type="hold", confidence_level="中")
    report = {
        "dataQualityTier": "analysis_grade",
        "requiredAvailable": True,
        "confidenceCap": 75,
        "reasonCodes": ["stale_required_source"],
        "scoreSuppressed": False,
        "stanceGuardrail": "observe_only",
        "keyLevelGuardrail": "ungrounded",
        "keyLevelGuardrailReason": "technical_evidence_weak_or_stale",
    }

    StockAnalysisPipeline._apply_data_quality_caps(result, report)

    sniper_points = result.dashboard["battle_plan"]["sniper_points"]
    assert sniper_points["ideal_buy"] == "待补充"
    assert sniper_points["stop_loss"] == "待补充"
    assert result.dashboard["battle_plan"]["sniper_points_meta"]["grounding"] == "ungrounded"


def test_decision_grade_data_keeps_normal_score_stance_and_levels() -> None:
    result = _analysis_result(score=73, operation_advice="持有", decision_type="hold", confidence_level="中")
    report = {
        "dataQualityTier": "decision_grade",
        "requiredAvailable": True,
        "confidenceCap": 100,
        "reasonCodes": [],
        "scoreSuppressed": False,
        "stanceGuardrail": "none",
        "keyLevelGuardrail": "grounded",
    }

    StockAnalysisPipeline._apply_data_quality_caps(result, report)

    assert result.sentiment_score == 73
    assert result.operation_advice == "持有"
    assert result.decision_type == "hold"
    assert result.confidence_level == "中"
    assert result.dashboard["battle_plan"]["sniper_points"]["stop_loss"] == "170"


def test_report_payload_represents_no_score_without_midpoint_score() -> None:
    service = AnalysisService()
    quality_report = _insufficient_report()
    result = SimpleNamespace(
        code="AAPL",
        name="Apple",
        query_id="q-no-score",
        current_price=None,
        change_pct=None,
        model_used="openai/gpt-4.1-mini",
        analysis_summary="数据不足，禁止判断",
        operation_advice="数据不足，禁止判断",
        trend_prediction="数据不足，禁止判断",
        sentiment_score=None,
        news_summary="",
        technical_analysis="",
        fundamental_analysis="",
        risk_warning="缺少必需价格与技术证据。",
        report_language="zh",
        decision_type="data_insufficient",
        confidence_level="低",
        dashboard={
            "battle_plan": {"sniper_points": {"ideal_buy": "待补充", "stop_loss": "待补充"}},
            "decision_context": {},
            "structured_analysis": {
                "data_quality_report": quality_report,
                "score_authenticity": {"scoreSuppressed": True},
            },
        },
        runtime_execution={"data_quality_report": quality_report, "steps": []},
        notification_result=None,
        get_sniper_points=lambda: {"ideal_buy": "待补充", "stop_loss": "待补充"},
    )

    payload = service._build_report_payload(result, query_id="q-no-score", report_type="detailed")

    assert payload["summary"]["sentiment_score"] is None
    assert payload["summary"]["sentiment_label"] == "数据不足"
    assert payload["details"]["analysis_result"]["score"] is None
    assert payload["details"]["analysis_result"]["dataQualityReport"]["scoreSuppressed"] is True
    assert payload["strategy"]["ideal_buy"] == "待补充"
