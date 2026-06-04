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
from src.analyzer import AnalysisResult
from src.config import Config
from src.services.analysis_service import AnalysisService
from src.storage import AnalysisHistory, DatabaseManager


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


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class PublicPreviewSafetyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "ai_public_safety.db"
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=AAPL",
                    "GEMINI_API_KEY=test",
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
        self.app = create_app(static_dir=self.data_dir / "empty-static")
        self.client = TestClient(self.app)
        self.db = DatabaseManager.get_instance()

    def tearDown(self) -> None:
        self.client.close()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

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
        self.assertIsNone(payload["report"]["meta"]["model_used"])
        self.assertIsNone(payload["report"]["decision_trace"])
        self.assertIsNone(payload["report"]["details"])
        self.assertEqual(payload["report"]["data_quality_report"]["confidenceCap"], 75)
        _assert_no_forbidden_directives(payload["report"])
        _assert_no_raw_output_terms(payload["report"])
        self.assertNotIn("public-safety-fixture", json.dumps(payload["report"], ensure_ascii=False))

        with self.db.get_session() as session:
            self.assertEqual(session.query(AnalysisHistory).count(), 0)


if __name__ == "__main__":
    unittest.main()
