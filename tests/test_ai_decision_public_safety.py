# -*- coding: utf-8 -*-
"""Public-safety evidence for AI decision and explanation outputs."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Iterable
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from src.analyzer import AnalysisResult, GeminiAnalyzer
from src.config import Config
from src.services.analysis_service import AnalysisService
from src.storage import AnalysisHistory, DatabaseManager
from tests.conftest import preserve_runtime_test_state


FORBIDDEN_DIRECTIVE_TERMS = (
    "place order",
    "submit order",
    "buy now",
    "sell now",
    "guaranteed",
    "must buy",
    "must sell",
    "best contract",
    "ai recommends you buy",
    "稳赚",
    "必买",
    "下单",
    "立即买入",
    "立即卖出",
    "立即交易",
    "保证收益",
)

FORBIDDEN_RAW_OUTPUT_TERMS = (
    "raw_provider_payload",
    "raw_payload",
    "raw_prompt",
    "chain_of_thought",
    "internal_reasoning",
    "api_key",
    "credential",
    "password",
    "stack_trace",
    "traceback",
    "trace_id",
    "traceparent",
    "request_id",
    "session_id",
    "debug_schema",
    "attempt_trace",
    "hidden_reasoning",
    "internal_reasoning",
)

FORBIDDEN_GENERATED_TRADING_TERMS_ZH = (
    "买入",
    "卖出",
    "下单",
    "立即交易",
    "交易建议",
    "投资建议",
    "止损",
    "止盈",
    "目标价",
    "目标位",
    "目标区间",
    "仓位建议",
    "狙击点位",
    "作战计划",
    "建仓策略",
)


def _iter_public_strings(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _iter_public_strings(item)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _iter_public_strings(item)
        return
    if isinstance(value, str):
        yield value


def _public_text(value: Any) -> str:
    return "\n".join(_iter_public_strings(value)).lower()


def _assert_no_forbidden_directives(value: Any) -> None:
    public_text = _public_text(value)
    for term in FORBIDDEN_DIRECTIVE_TERMS:
        assert term.lower() not in public_text, term


def _assert_no_raw_output_terms(value: Any) -> None:
    public_text = _public_text(value)
    for term in FORBIDDEN_RAW_OUTPUT_TERMS:
        assert term.lower() not in public_text, term


def _safe_result(**overrides: Any) -> AnalysisResult:
    dashboard = {
        "core_conclusion": {
            "one_sentence": "Only observe the setup until data quality and risk/reward improve.",
            "position_advice": {
                "no_position": "Keep this on a watchlist and wait for confirmation.",
                "has_position": "Review risk exposure and avoid adding size without confirmation.",
            },
        },
        "battle_plan": {
            "sniper_points": {
                "ideal_buy": "Observe 184-186 as a potential support area.",
                "stop_loss": "Risk invalidates below 179.",
                "take_profit": "Resistance zone near 195-198.",
            },
            "position_strategy": {
                "entry_plan": "Observation only; no order guidance is implied.",
                "risk_control": "Risk remains elevated if required data becomes stale.",
            },
        },
        "decision_context": {
            "score_breakdown": [
                {"label": "Risk", "score": 42, "tone": "negative"},
            ],
        },
        "structured_analysis": {
            "data_quality": {"missing_fields": []},
            "technicals": {"status": "used", "source": "fixture_technicals"},
            "fundamentals": {"status": "used", "source": "fixture_fundamentals"},
            "sentiment_analysis": {"status": "used", "source": "fixture_sentiment"},
            "realtime_context": {"status": "used", "source": "fixture_quote"},
        },
    }
    base: dict[str, Any] = {
        "code": "AAPL",
        "name": "Apple",
        "sentiment_score": 52,
        "trend_prediction": "Observation bias with elevated risk",
        "operation_advice": "Watch only",
        "decision_type": "hold",
        "confidence_level": "中",
        "report_language": "en",
        "dashboard": dashboard,
        "analysis_summary": "Observation only; risk needs review before any user action.",
        "news_summary": "No high-confidence new catalyst in the fixture.",
        "technical_analysis": "Price is near support but confirmation is incomplete.",
        "fundamental_analysis": "Fundamental inputs are adequate for observation.",
        "risk_warning": "Risk remains elevated when quote freshness degrades.",
        "current_price": 188.2,
        "change_pct": 1.8,
        "model_used": "openai/gpt-4o-mini",
        "runtime_execution": {
            "ai": {"provider": "openai", "model": "openai/gpt-4o-mini"},
            "data": {
                "quote": {"status": "ok", "source": "fixture_quote"},
                "fundamentals": {"status": "ok", "source": "fixture_fundamentals"},
            },
            "steps": [],
        },
    }
    base.update(overrides)
    return AnalysisResult(**base)


def test_ai_decision_report_uses_observation_language_without_direct_trade_directives() -> None:
    payload = AnalysisService()._build_report_payload(
        _safe_result(),
        query_id="q-public-safety",
        report_type="detailed",
    )

    public_surface = {
        "summary": payload["summary"],
        "decision_trace": payload["decision_trace"],
    }
    _assert_no_forbidden_directives(public_surface)
    public_text = _public_text(public_surface)
    assert "observe" in public_text or "observation" in public_text
    assert "risk" in public_text
    assert payload["decision_trace"]["decision_fields"]["action"]["value"] == "hold"
    assert payload["decision_trace"]["llm"]["prompt_exposed"] is False


def test_analyzer_generation_prompt_is_observation_only_contract() -> None:
    with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
        analyzer = GeminiAnalyzer()

    system_prompt = analyzer._get_analysis_system_prompt("zh")
    user_prompt = analyzer._format_prompt(
        {
            "code": "600519",
            "stock_name": "贵州茅台",
            "date": "2026-06-09",
            "today": {"close": 1680, "ma5": 1675, "ma10": 1660, "ma20": 1640},
            "ma_status": "均线多头",
        },
        "贵州茅台",
        report_language="zh",
    )
    prompt = f"{system_prompt}\n{user_prompt}"

    self_forbidden = (
        "买入/加仓",
        "减仓/卖出",
        "买入信号",
        "卖出信号",
        "具体操作指引",
        "理想买入点",
        "次优买入点",
        "止损位",
        "目标位",
        "建议仓位",
        "分批建仓",
        "强烈买入",
        "该买该卖",
        "必须给出具体价格",
        "买入价、止损价、目标价",
    )
    for forbidden in self_forbidden:
        assert forbidden not in prompt, forbidden
    assert '"operation_advice"' in prompt
    assert '"decision_type"' in prompt
    assert '"ideal_buy"' in prompt
    assert "仅供观察" in prompt


def test_generated_report_payload_keeps_legacy_shape_without_trading_plan_copy() -> None:
    dashboard = {
        "core_conclusion": {
            "one_sentence": "仅供观察，等待证据补齐。",
            "position_advice": {
                "no_position": "仅跟踪关键价格区间，不提供操作指令。",
                "has_position": "复核风险边界，不扩大风险暴露。",
            },
        },
        "battle_plan": {
            "sniper_points": {
                "ideal_buy": "关键价格区间 184-186。",
                "secondary_buy": "参考区间 180-182。",
                "stop_loss": "风险边界 179 下方。",
                "take_profit": "上方观察区 195-198。",
            },
            "position_strategy": {
                "entry_plan": "继续跟踪证据变化。",
                "risk_control": "若证据走弱，仅记录风险边界。",
            },
        },
        "intelligence": {"risk_alerts": []},
    }
    payload = AnalysisService()._build_report_payload(
        _safe_result(
            report_language="zh",
            operation_advice="观望",
            trend_prediction="震荡",
            analysis_summary="仅供观察，等待证据补齐。",
            dashboard=dashboard,
        ),
        query_id="q-generation-contract",
        report_type="detailed",
    )

    assert set(payload["strategy"]) >= {"ideal_buy", "secondary_buy", "stop_loss", "take_profit"}
    assert set(payload["details"]["analysis_result"]) >= {"decision", "action", "entry_price", "stop_loss", "take_profit"}
    assert payload["details"]["analysis_result"]["decision"] in {"buy", "hold", "sell"}
    public_text = _public_text(
        {
            "summary": payload["summary"],
            "strategy": payload["strategy"],
            "standard_report": payload["details"]["standard_report"],
        }
    )
    for forbidden in FORBIDDEN_GENERATED_TRADING_TERMS_ZH:
        assert forbidden not in public_text, forbidden
    assert "仅供观察" in public_text
    assert "风险边界" in public_text


def test_degraded_data_quality_caps_are_preserved_in_ai_decision_output() -> None:
    dashboard = _safe_result().dashboard
    assert isinstance(dashboard, dict)
    dashboard["structured_analysis"] = {
        "data_quality": {
            "missing_fields": [
                "quote.price",
                "fundamentals.revenue",
                "fundamentals.eps",
                "news.latest",
            ]
        },
        "fundamentals": {"status": "missing"},
        "realtime_context": {"status": "stale"},
    }
    data_quality_report = {
        "dataQualityTier": "insufficient",
        "dataQualityScore": 35,
        "requiredAvailable": False,
        "importantMissing": ["fundamentals.revenue", "fundamentals.eps"],
        "optionalMissing": ["news"],
        "staleSources": ["quote"],
        "confidenceCap": 40,
        "reasonCodes": ["required_data_missing", "stale_required_source"],
    }
    result = _safe_result(
        confidence_level="高",
        sentiment_score=88,
        dashboard=dashboard,
        runtime_execution={
            "ai": {"provider": "openai", "model": "openai/gpt-4o-mini"},
            "data": {
                "quote": {"status": "stale", "source": "fixture_quote"},
                "fundamentals": {"status": "missing", "source": "fixture_fundamentals"},
            },
            "data_quality_report": data_quality_report,
            "steps": [],
        },
    )

    payload = AnalysisService()._build_report_payload(
        result,
        query_id="q-degraded-quality",
        report_type="detailed",
    )

    assert payload["dataQualityReport"]["requiredAvailable"] is False
    assert payload["dataQualityReport"]["confidenceCap"] <= 40
    assert payload["dataQualityReport"]["dataQualityTier"] == "insufficient"
    assert "quote data stale" in payload["decision_trace"]["limitations"]
    assert "fundamental data missing" in payload["decision_trace"]["limitations"]
    conflict_types = {item["type"] for item in payload["decision_trace"]["conflicts"]}
    assert "low_data_quality_high_confidence" in conflict_types
    _assert_no_forbidden_directives(
        {
            "summary": payload["summary"],
            "dataQualityReport": payload["dataQualityReport"],
            "decision_trace": payload["decision_trace"],
        }
    )


def test_single_stock_evidence_packet_redacts_internal_metadata_and_trade_language() -> None:
    result = _safe_result(
        dashboard={
            "battle_plan": {
                "sniper_points": {
                    "ideal_buy": "Observe support",
                    "stop_loss": "Risk invalidates below 179",
                    "take_profit": "Resistance near 195-198",
                }
            },
            "structured_analysis": {
                "fundamentals": {
                    "status": "missing",
                    "source": None,
                    "freshness": "unknown",
                    "normalized": {},
                },
                "earnings_analysis": {
                    "status": "missing",
                    "source": None,
                    "freshness": "unknown",
                    "quarterly_series": [],
                    "summary_flags": ["earnings_data_unavailable"],
                },
                "fundamental_context": {
                    "status": "market not supported",
                    "market": "us",
                    "reason": "fundamental_context unavailable",
                },
                "technicals": {
                    "status": "ok",
                    "source": "polygon_us_grouped_daily",
                    "sourceTier": "score_grade",
                    "freshness": "fresh",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                },
                "realtime_context": {
                    "price": 188.2,
                    "source": "polygon_us_grouped_daily",
                    "freshness": "fresh",
                },
                "sentiment_analysis": {
                    "status": "partial",
                    "source": "tavily",
                    "sourceTier": "observation_only",
                    "providerAuthority": "observationOnly",
                    "freshness": "delayed",
                    "top_positive_items": [],
                    "top_negative_items": [],
                    "classified_items": [],
                    "raw_payload": {"authorization": "Bearer hidden"},
                    "article_body": "Full article body should stay private.",
                    "prompt": "submit order on breakout",
                },
                "catalyst": {
                    "status": "missing",
                    "source": None,
                    "classified_items": [],
                    "summary_text": "trade now on momentum",
                },
                "data_quality_report": {
                    "dataQualityTier": "analysis_grade",
                    "requiredAvailable": True,
                    "confidenceCap": 68,
                    "missingRequiredDomains": ["fundamentals", "earnings", "news"],
                    "importantDomainsMissing": ["valuation", "catalyst_news_event"],
                    "reasonCodes": ["fundamental_context_unavailable", "provider_timeout"],
                    "stanceGuardrail": "observe_only",
                },
            },
        },
        runtime_execution={
            "ai": {"provider": "openai", "model": "openai/gpt-4o-mini"},
            "data": {
                "market": {"status": "ok", "source": "polygon_us_grouped_daily", "freshness": "fresh"},
                "fundamentals": {"status": "missing", "source": None, "freshness": "unknown"},
                "news": {
                    "status": "timeout",
                    "source": None,
                    "freshness": "unknown",
                    "error": "provider_timeout after 8s Authorization: Bearer hidden",
                    "final_reason": "cache_router token=hidden",
                    "router_debug": "news_router>provider_a",
                },
                "sentiment": {
                    "status": "fallback",
                    "source": "fallback_cache",
                    "freshness": "fallback",
                    "final_reason": "traceback token=hidden",
                },
            },
            "data_quality_report": {
                "dataQualityTier": "analysis_grade",
                "requiredAvailable": True,
                "confidenceCap": 68,
                "missingRequiredDomains": ["fundamentals", "earnings", "news"],
                "importantDomainsMissing": ["valuation", "catalyst_news_event"],
                "reasonCodes": ["fundamental_context_unavailable", "provider_timeout"],
                "stanceGuardrail": "observe_only",
            },
            "steps": [],
        },
    )

    response = AnalysisService()._build_analysis_response(
        result,
        query_id="q-evidence-safety",
        report_type="detailed",
    )
    packet = response["singleStockEvidencePacket"]
    serialized = json.dumps(packet, ensure_ascii=False).lower()

    assert response["report"]["singleStockEvidencePacket"] == packet
    assert response["report"]["meta"]["singleStockEvidencePacket"] == packet
    assert response["report"]["details"]["analysis_result"]["singleStockEvidencePacket"] == packet
    _assert_no_forbidden_directives(packet)
    _assert_no_raw_output_terms(packet)
    assert "authorization" not in serialized
    assert "bearer" not in serialized
    assert "cache_router" not in serialized
    assert "traceback" not in serialized
    assert "article body" not in serialized
    assert "submit order" not in serialized
    assert "trade now" not in serialized


def test_evidence_citation_frame_redacts_internal_metadata_and_trade_language() -> None:
    result = _safe_result(
        dashboard={
            "battle_plan": {
                "sniper_points": {
                    "ideal_buy": "Observe support",
                    "stop_loss": "Risk invalidates below 179",
                    "take_profit": "Resistance near 195-198",
                }
            },
            "structured_analysis": {
                "fundamentals": {
                    "status": "missing",
                    "source": None,
                    "freshness": "unknown",
                    "normalized": {},
                },
                "earnings_analysis": {
                    "status": "missing",
                    "source": None,
                    "freshness": "unknown",
                    "quarterly_series": [],
                    "summary_flags": ["earnings_data_unavailable"],
                },
                "fundamental_context": {
                    "status": "market not supported",
                    "market": "us",
                    "reason": "fundamental_context unavailable",
                },
                "technicals": {
                    "status": "ok",
                    "source": "polygon_us_grouped_daily",
                    "sourceTier": "score_grade",
                    "freshness": "fresh",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                },
                "realtime_context": {
                    "price": 188.2,
                    "source": "polygon_us_grouped_daily",
                    "freshness": "fresh",
                },
                "sentiment_analysis": {
                    "status": "partial",
                    "source": "tavily",
                    "sourceTier": "observation_only",
                    "providerAuthority": "observationOnly",
                    "freshness": "delayed",
                    "top_positive_items": [],
                    "top_negative_items": [],
                    "classified_items": [],
                    "raw_payload": {"authorization": "Bearer hidden"},
                    "article_body": "Full article body should stay private.",
                    "prompt": "submit order on breakout",
                },
                "catalyst": {
                    "status": "missing",
                    "source": None,
                    "classified_items": [],
                    "summary_text": "trade now on momentum",
                },
                "data_quality_report": {
                    "dataQualityTier": "analysis_grade",
                    "requiredAvailable": True,
                    "confidenceCap": 68,
                    "missingRequiredDomains": ["fundamentals", "earnings", "news"],
                    "importantDomainsMissing": ["valuation", "catalyst_news_event"],
                    "reasonCodes": ["fundamental_context_unavailable", "provider_timeout"],
                    "stanceGuardrail": "observe_only",
                },
            },
        },
        runtime_execution={
            "ai": {"provider": "openai", "model": "openai/gpt-4o-mini"},
            "data": {
                "market": {"status": "ok", "source": "polygon_us_grouped_daily", "freshness": "fresh"},
                "fundamentals": {"status": "missing", "source": None, "freshness": "unknown"},
                "news": {
                    "status": "timeout",
                    "source": None,
                    "freshness": "unknown",
                    "error": "provider_timeout after 8s Authorization: Bearer hidden",
                    "final_reason": "cache_router token=hidden",
                    "router_debug": "news_router>provider_a",
                },
                "sentiment": {
                    "status": "fallback",
                    "source": "fallback_cache",
                    "freshness": "fallback",
                    "final_reason": "traceback token=hidden",
                },
            },
            "data_quality_report": {
                "dataQualityTier": "analysis_grade",
                "requiredAvailable": True,
                "confidenceCap": 68,
                "missingRequiredDomains": ["fundamentals", "earnings", "news"],
                "importantDomainsMissing": ["valuation", "catalyst_news_event"],
                "reasonCodes": ["fundamental_context_unavailable", "provider_timeout"],
                "stanceGuardrail": "observe_only",
            },
            "steps": [],
        },
    )

    response = AnalysisService()._build_analysis_response(
        result,
        query_id="q-citation-safety",
        report_type="detailed",
    )
    frame = response["evidenceCitationFrame"]
    serialized = json.dumps(frame, ensure_ascii=False).lower()

    assert response["report"]["evidenceCitationFrame"] == frame
    assert response["report"]["meta"]["evidenceCitationFrame"] == frame
    assert response["report"]["details"]["analysis_result"]["evidenceCitationFrame"] == frame
    _assert_no_forbidden_directives(frame)
    _assert_no_raw_output_terms(frame)
    assert "authorization" not in serialized
    assert "bearer" not in serialized
    assert "cache_router" not in serialized
    assert "traceback" not in serialized
    assert "article body" not in serialized
    assert "submit order" not in serialized
    assert "trade now" not in serialized


def test_source_provenance_frame_redacts_internal_metadata_and_trade_language() -> None:
    result = _safe_result(
        dashboard={
            "battle_plan": {
                "sniper_points": {
                    "ideal_buy": "Observe support",
                    "stop_loss": "Risk invalidates below 179",
                    "take_profit": "Resistance near 195-198",
                }
            },
            "structured_analysis": {
                "fundamentals": {
                    "status": "missing",
                    "source": None,
                    "freshness": "unknown",
                    "normalized": {},
                },
                "earnings_analysis": {
                    "status": "missing",
                    "source": None,
                    "freshness": "unknown",
                    "quarterly_series": [],
                    "summary_flags": ["earnings_data_unavailable"],
                },
                "technicals": {
                    "status": "ok",
                    "source": "polygon_us_grouped_daily",
                    "sourceTier": "score_grade",
                    "freshness": "fresh",
                    "sourceAuthorityAllowed": True,
                    "scoreContributionAllowed": True,
                },
                "realtime_context": {
                    "price": 188.2,
                    "source": "polygon_us_grouped_daily",
                    "freshness": "fresh",
                },
                "sentiment_analysis": {
                    "status": "partial",
                    "source": "tavily",
                    "sourceTier": "observation_only",
                    "providerAuthority": "observationOnly",
                    "freshness": "delayed",
                    "classified_items": [],
                    "raw_payload": {"authorization": "Bearer hidden"},
                    "article_body": "Full article body should stay private.",
                    "prompt": "submit order on breakout",
                },
                "catalyst": {
                    "status": "missing",
                    "source": None,
                    "classified_items": [],
                    "summary_text": "trade now on momentum",
                },
                "data_quality_report": {
                    "dataQualityTier": "analysis_grade",
                    "requiredAvailable": True,
                    "confidenceCap": 68,
                    "missingRequiredDomains": ["fundamentals", "earnings", "news"],
                    "importantDomainsMissing": ["valuation", "catalyst_news_event"],
                    "reasonCodes": ["fundamental_context_unavailable", "provider_timeout"],
                    "stanceGuardrail": "observe_only",
                },
            },
        },
        runtime_execution={
            "ai": {"provider": "openai", "model": "openai/gpt-4o-mini"},
            "data": {
                "market": {"status": "ok", "source": "polygon_us_grouped_daily", "freshness": "fresh"},
                "fundamentals": {"status": "missing", "source": None, "freshness": "unknown"},
                "news": {
                    "status": "timeout",
                    "source": None,
                    "freshness": "unknown",
                    "error": "provider_timeout after 8s Authorization: Bearer hidden",
                    "final_reason": "cache_router token=hidden",
                    "router_debug": "news_router>provider_a",
                },
                "sentiment": {
                    "status": "fallback",
                    "source": "fallback_cache",
                    "freshness": "fallback",
                    "final_reason": "traceback token=hidden",
                },
            },
            "data_quality_report": {
                "dataQualityTier": "analysis_grade",
                "requiredAvailable": True,
                "confidenceCap": 68,
                "missingRequiredDomains": ["fundamentals", "earnings", "news"],
                "importantDomainsMissing": ["valuation", "catalyst_news_event"],
                "reasonCodes": ["fundamental_context_unavailable", "provider_timeout"],
                "stanceGuardrail": "observe_only",
            },
            "steps": [],
        },
    )

    response = AnalysisService()._build_analysis_response(
        result,
        query_id="q-source-provenance-safety",
        report_type="detailed",
    )
    frame = response["sourceProvenanceFrame"]
    serialized = json.dumps(frame, ensure_ascii=False).lower()

    assert response["report"]["sourceProvenanceFrame"] == frame
    assert response["report"]["meta"]["sourceProvenanceFrame"] == frame
    assert response["report"]["details"]["analysis_result"]["sourceProvenanceFrame"] == frame
    _assert_no_forbidden_directives(frame)
    _assert_no_raw_output_terms(frame)
    assert "authorization" not in serialized
    assert "bearer" not in serialized
    assert "cache_router" not in serialized
    assert "traceback" not in serialized
    assert "article body" not in serialized
    assert "submit order" not in serialized
    assert "trade now" not in serialized


def test_decision_trace_redacts_sensitive_provider_metadata_and_debug_text() -> None:
    result = _safe_result(
        dashboard={
            "decision_context": {"score_breakdown": [{"label": "Risk", "score": 42}]},
            "structured_analysis": {
                "data_quality": {
                    "missing_fields": [
                        "raw_prompt: hidden system instruction",
                        "session_cookie: should not appear",
                    ]
                },
                "realtime_context": {"status": "failed", "source": "token=public-safety-fixture"},
            },
            "battle_plan": {"position_strategy": {"risk_control": "Risk review only."}},
        },
        runtime_execution={
            "ai": {
                "provider": "openai api_key=public-safety-fixture",
                "model": "openai/gpt-4o-mini",
            },
            "data": {
                "quote": {
                    "status": "failed",
                    "source": "token=public-safety-fixture",
                    "final_reason": "Traceback includes cookie=public-safety-fixture",
                }
            },
            "steps": [],
        },
    )

    trace = AnalysisService()._build_decision_trace(
        result,
        query_id="q-redaction",
        report_type="detailed",
    )

    assert trace["llm"]["prompt_exposed"] is False
    serialized = json.dumps(trace, ensure_ascii=False).lower()
    for forbidden in (
        "public-safety-fixture",
        "api_key",
        "raw_prompt",
        "hidden system instruction",
        "session_cookie",
        "traceback",
        "cookie=",
        "token=",
    ):
        assert forbidden not in serialized
    assert "[redacted]" in serialized


def test_analysis_runtime_files_do_not_import_broker_order_or_portfolio_mutation_paths() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    analysis_runtime_files = [
        repo_root / "api/v1/endpoints/analysis.py",
        repo_root / "src/services/analysis_service.py",
    ]
    forbidden_fragments = (
        "place_order",
        "submit_order",
        "execute_order",
        "create_order",
        "broker_execution",
        "order_placement",
        "portfolio_mutation",
        "portfolio_service",
        "portfolio_repository",
        "PortfolioService",
        "litellm.",
        "_call_litellm(",
        "GeminiAnalyzer(",
    )

    for path in analysis_runtime_files:
        source = path.read_text(encoding="utf-8")
        for fragment in forbidden_fragments:
            assert fragment not in source, f"{fragment!r} unexpectedly appears in {path}"


def test_agent_executor_prompts_use_observation_contract_language() -> None:
    from src.agent.executor import AGENT_SYSTEM_PROMPT, CHAT_SYSTEM_PROMPT

    prompt = f"{AGENT_SYSTEM_PROMPT}\n{CHAT_SYSTEM_PROMPT}"
    forbidden_fragments = (
        "专注于趋势交易",
        "交易技能",
        "决策仪表盘",
        "买入/加仓",
        "减仓/卖出",
        "买入信号",
        "卖出信号",
        "立即行动",
        "空仓者建议",
        "持仓者建议",
        "强烈买入",
        "该买该卖",
        "分持仓建议",
        "精确狙击点",
        "理想买入点",
        "止损位",
        "目标位",
        "建议仓位",
        "分批建仓",
    )

    for fragment in forbidden_fragments:
        assert fragment not in prompt, fragment
    assert '"operation_advice": "观望/仅供观察/继续跟踪/风险收缩/数据不足"' in prompt
    assert "仅供研究观察，不构成投资建议" in prompt


def test_agent_orchestrator_default_copy_is_observation_only() -> None:
    from src.agent.orchestrator import (
        _adjust_operation_advice,
        _default_position_advice,
        _default_position_size,
        _signal_to_operation,
        _signal_to_signal_type,
    )

    public_values = [
        _signal_to_operation("buy"),
        _signal_to_operation("sell"),
        _signal_to_signal_type("buy"),
        _signal_to_signal_type("sell"),
        _adjust_operation_advice("legacy", "buy"),
        _adjust_operation_advice("legacy", "sell"),
        _default_position_size("buy"),
        _default_position_size("sell"),
        *_default_position_advice("buy").values(),
        *_default_position_advice("hold").values(),
        *_default_position_advice("sell").values(),
    ]
    public_text = "\n".join(public_values)
    forbidden_fragments = (
        "买入",
        "卖出",
        "加仓",
        "减仓",
        "建仓",
        "试仓",
        "止损",
        "入场",
        "开仓",
        "仓位",
        "建议",
    )

    for fragment in forbidden_fragments:
        assert fragment not in public_text, fragment
    assert "继续跟踪" in public_text
    assert "风险边界" in public_text


def test_history_schema_public_descriptions_are_observation_only() -> None:
    source = (Path(__file__).resolve().parents[1] / "api/v1/schemas/history.py").read_text(encoding="utf-8")
    forbidden_fragments = (
        'description="操作建议"',
        'description="理想买入价"',
        'description="第二买入价"',
        'description="止损价"',
        'description="止盈价"',
        '"operation_advice": "持有"',
        "技术面向好，建议持有",
    )

    for fragment in forbidden_fragments:
        assert fragment not in source, fragment
    assert "研究状态" in source
    assert "关键价位参考" in source
    assert "风险边界" in source


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._password_hash_value = None
    auth._rate_limit = {}
    auth._admin_reauth_markers = {}
    auth._rate_limit_lock = None


class PublicPreviewSafetyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime_state = preserve_runtime_test_state()
        self.runtime_state.__enter__()
        self.addCleanup(self.runtime_state.__exit__, None, None, None)
        _reset_auth_globals()
        for key in ("STOCK_LIST", "GEMINI_API_KEY", "ADMIN_AUTH_ENABLED"):
            os.environ.pop(key, None)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "ai_public_safety.db"
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=AAPL",
                    "GEMINI_API_KEY=deterministic-fixture-key",
                    "ADMIN_AUTH_ENABLED=true",
                    f"DATABASE_PATH={self.db_path}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.db_path)
        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.addCleanup(Config.reset_instance)
        self.addCleanup(DatabaseManager.reset_instance)
        self.app = create_app(static_dir=self.data_dir / "empty-static")
        self.client_context = TestClient(self.app)
        self.client = self.client_context.__enter__()
        self.addCleanup(self.client_context.__exit__, None, None, None)
        self.db = DatabaseManager.get_instance()

    def test_guest_preview_strips_raw_ai_details_and_uses_mocked_analysis(self) -> None:
        def _mock_analyze_stock(*args: Any, **kwargs: Any) -> dict[str, Any]:
            query_id = str(kwargs["query_id"])
            return {
                "query_id": query_id,
                "stock_code": "AAPL",
                "stock_name": "Apple",
                "report": {
                    "meta": {
                        "query_id": query_id,
                        "stock_code": "AAPL",
                        "stock_name": "Apple",
                        "report_type": "brief",
                        "report_language": "en",
                        "created_at": "2026-05-07T09:00:00+08:00",
                        "model_used": "openai/gpt-4o-mini",
                    },
                    "summary": {
                        "analysis_summary": "Observation only; risk remains elevated.",
                        "operation_advice": "Watch only",
                        "trend_prediction": "Needs confirmation",
                        "sentiment_score": 52,
                        "sentiment_label": "Neutral",
                    },
                    "strategy": {
                        "ideal_buy": "Observe support near 184-186",
                        "stop_loss": "Risk invalidates below 179",
                        "take_profit": "Resistance near 195-198",
                    },
                    "details": {
                        "raw_ai_response": {
                            "raw_provider_payload": {"api_key": "public-safety-fixture"},
                            "debug_schema": {"stack_trace": "hidden"},
                            "attempt_trace": [{"token": "public-safety-fixture"}],
                            "trace_id": "trace-public-safety-fixture",
                            "hidden_reasoning": "hidden chain should not appear",
                        },
                        "standard_report": {"internal": "hidden"},
                    },
                    "decision_trace": {
                        "llm": {
                            "provider": "openai",
                            "model": "openai/gpt-4o-mini",
                            "prompt_exposed": False,
                        },
                        "trace_id": "trace-public-safety-fixture",
                        "hidden_reasoning": "hidden chain should not appear",
                    },
                    "dataQualityReport": {
                        "dataQualityTier": "analysis_grade",
                        "requiredAvailable": True,
                        "confidenceCap": 75,
                        "staleSources": ["quote"],
                    },
                },
            }

        with patch(
            "src.services.analysis_service.AnalysisService.analyze_stock",
            side_effect=_mock_analyze_stock,
        ) as analyze_stock:
            response = self.client.post(
                "/api/v1/analysis/preview",
                json={"stock_code": "AAPL", "stock_name": "Apple"},
            )

        self.assertEqual(response.status_code, 200)
        analyze_stock.assert_called_once()
        _, kwargs = analyze_stock.call_args
        self.assertFalse(kwargs["send_notification"])
        self.assertFalse(kwargs["persist_history"])
        self.assertIsNotNone(kwargs["guest_bucket_hash"])

        payload = response.json()
        self.assertEqual(payload["preview_scope"], "guest")
        self.assertNotIn("model_used", payload["report"]["meta"])
        self.assertNotIn("decision_trace", payload["report"])
        self.assertNotIn("details", payload["report"])
        self.assertNotIn("data_quality_report", payload["report"])
        _assert_no_forbidden_directives(payload["report"])
        _assert_no_raw_output_terms(payload["report"])
        self.assertNotIn("public-safety-fixture", json.dumps(payload["report"], ensure_ascii=False))

        with self.db.get_session() as session:
            self.assertEqual(session.query(AnalysisHistory).count(), 0)


if __name__ == "__main__":
    unittest.main()
