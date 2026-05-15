# -*- coding: utf-8 -*-
"""Regression tests for analysis API/report-type contracts."""

import asyncio
from concurrent.futures import Future
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

try:
    from api.app import create_app
    from api.v1.schemas.analysis import AnalyzeRequest
    from api.v1.endpoints.analysis import (
        get_task_progress,
        trigger_analysis,
        _handle_sync_analysis,
        _build_llm_model_unavailable_detail,
        _build_analysis_report,
        _load_sync_fundamental_sources,
        _format_sse_event,
    )
except Exception:  # pragma: no cover - optional dependency environments
    create_app = None
    AnalyzeRequest = None
    get_task_progress = None
    trigger_analysis = None
    _handle_sync_analysis = None
    _build_llm_model_unavailable_detail = None
    _build_analysis_report = None
    _load_sync_fundamental_sources = None
    _format_sse_event = None

from src.config import Config
from src.enums import ReportType
from src.services.analysis_service import AnalysisService
from src.services.image_stock_extractor import _call_litellm_vision
from src.services.task_queue import AnalysisTaskQueue
from data_provider.realtime_types import RealtimeSource


class AnalysisApiContractTestCase(unittest.TestCase):
    def test_report_type_full_maps_to_full_pipeline_mode(self) -> None:
        service = object.__new__(AnalysisService)
        pipeline_instance = MagicMock()
        pipeline_instance.process_single_stock.return_value = object()

        with patch("src.config.get_config", return_value=SimpleNamespace()), \
             patch("src.core.pipeline.StockAnalysisPipeline", return_value=pipeline_instance), \
             patch.object(AnalysisService, "_build_analysis_response", return_value={"stock_code": "600519"}):
            result = AnalysisService.analyze_stock(service, "600519", report_type="full", query_id="q1")

        self.assertEqual(result, {"stock_code": "600519"})
        self.assertEqual(
            pipeline_instance.process_single_stock.call_args.kwargs["report_type"],
            ReportType.FULL,
        )

    def test_analyze_stock_forwards_progress_callback_to_pipeline(self) -> None:
        service = object.__new__(AnalysisService)
        pipeline_instance = MagicMock()
        pipeline_instance.process_single_stock.return_value = None
        progress_callback = MagicMock()

        with patch("src.config.get_config", return_value=SimpleNamespace()), \
             patch("src.core.pipeline.StockAnalysisPipeline", return_value=pipeline_instance):
            AnalysisService.analyze_stock(
                service,
                "600519",
                report_type="detailed",
                query_id="q-progress",
                send_notification=False,
                progress_callback=progress_callback,
            )

        self.assertIs(
            pipeline_instance.process_single_stock.call_args.kwargs["progress_callback"],
            progress_callback,
        )

    def test_analyze_stock_forwards_force_refresh_to_pipeline(self) -> None:
        service = object.__new__(AnalysisService)
        pipeline_instance = MagicMock()
        pipeline_instance.process_single_stock.return_value = None

        with patch("src.config.get_config", return_value=SimpleNamespace()), \
             patch("src.core.pipeline.StockAnalysisPipeline", return_value=pipeline_instance):
            AnalysisService.analyze_stock(
                service,
                "600519",
                report_type="detailed",
                force_refresh=True,
                query_id="q-force-refresh",
                send_notification=False,
            )

        self.assertTrue(
            pipeline_instance.process_single_stock.call_args.kwargs["force_refresh"]
        )

    def test_analyze_stock_forwards_explicit_research_mode_to_pipeline(self) -> None:
        service = object.__new__(AnalysisService)
        pipeline_instance = MagicMock()
        pipeline_instance.process_single_stock.return_value = None

        with patch("src.config.get_config", return_value=SimpleNamespace()), \
             patch("src.core.pipeline.StockAnalysisPipeline", return_value=pipeline_instance):
            AnalysisService.analyze_stock(
                service,
                "AAPL",
                report_type="detailed",
                query_id="q-research-mode",
                send_notification=False,
                research_mode="quick",
            )

        self.assertEqual(
            pipeline_instance.process_single_stock.call_args.kwargs["research_mode"],
            "quick",
        )

    def test_trigger_analysis_rejects_unusable_llm_model_with_actionable_detail(self) -> None:
        if trigger_analysis is None or AnalyzeRequest is None:
            self.skipTest("analysis endpoint import unavailable")

        config = Config(
            stock_list=["AAPL"],
            llm_model_list=[
                {
                    "model_name": "openai/gpt-4.1-free",
                    "litellm_params": {"model": "openai/gpt-4.1-free", "api_key": "sk-test"},
                },
                {
                    "model_name": "openai/gpt-4o-free",
                    "litellm_params": {"model": "openai/gpt-4o-free", "api_key": "sk-test"},
                },
            ],
            litellm_model="openai/gpt-5-ghost",
            wechat_webhook_url="https://example.com/webhook",
            bocha_api_keys=["test"],
        )

        with self.assertRaises(Exception) as ctx:
            trigger_analysis(
                AnalyzeRequest(stock_code="AAPL", async_mode=True),
                config=config,
                current_user=SimpleNamespace(user_id="user-1"),
            )

        exc = ctx.exception
        self.assertEqual(getattr(exc, "status_code", None), 500)
        self.assertEqual(exc.detail["error"], "llm_model_unavailable")
        self.assertIn("配置的模型不可用", exc.detail["message"])
        self.assertEqual(exc.detail["available_models"], ["openai/gpt-4.1-free", "openai/gpt-4o-free"])

    def test_model_unavailable_detail_is_sanitized_and_actionable(self) -> None:
        if _build_llm_model_unavailable_detail is None:
            self.skipTest("analysis endpoint import unavailable")

        config = Config(
            stock_list=["AAPL"],
            llm_model_list=[
                {
                    "model_name": "openai/gpt-4o-free",
                    "litellm_params": {
                        "model": "openai/gpt-4o-free",
                        "api_key": "sk-secret-123",
                        "api_base": "https://example.com/v1?api_key=sk-secret-123",
                    },
                },
            ],
            litellm_model="openai/gpt-5-ghost",
            wechat_webhook_url="https://example.com/webhook",
            bocha_api_keys=["test"],
        )

        detail = _build_llm_model_unavailable_detail(config)

        self.assertEqual(detail["error"], "llm_model_unavailable")
        self.assertIn("配置的模型不可用", detail["message"])
        self.assertIn("openai/gpt-4o-free", detail["message"])
        self.assertNotIn("api_key", detail["message"].lower())
        self.assertNotIn("sk-secret-123", detail["message"])

    def test_get_task_progress_returns_module_payload(self) -> None:
        if get_task_progress is None:
            self.skipTest("analysis endpoint import unavailable")

        service = MagicMock()
        service.get_task_progress.return_value = {
            "task_id": "task-1",
            "stock_code": "TSLA",
            "stock_name": "Tesla",
            "status": "processing",
            "progress": 62,
            "message": "正在分析价格信号、基本面与新闻证据...",
            "updated_at": "2026-04-29T09:02:00Z",
            "execution_session_id": "session-1",
            "modules": [
                {"key": "llm", "name": "LLM", "status": "running"},
                {"key": "news", "name": "新闻", "status": "failed"},
            ],
            "final_result": None,
        }
        current_user = SimpleNamespace(user_id="user-1")

        payload = get_task_progress("task-1", service=service, current_user=current_user).model_dump()

        self.assertEqual(payload["task_id"], "task-1")
        self.assertNotIn("model", payload["modules"][0])
        self.assertNotIn("error", payload["modules"][1])
        service.get_task_progress.assert_called_once_with("task-1", owner_id="user-1")

    def test_report_type_full_is_preserved_in_response_metadata(self) -> None:
        service = AnalysisService()
        pipeline_instance = MagicMock()
        pipeline_instance.process_single_stock.return_value = SimpleNamespace(
            code="600519",
            name="贵州茅台",
            current_price=1234.56,
            change_pct=1.23,
            model_used="test-model",
            analysis_summary="summary",
            operation_advice="hold",
            trend_prediction="up",
            sentiment_score=80,
            news_summary="news",
            technical_analysis="tech",
            fundamental_analysis="fundamental",
            risk_warning="risk",
            get_sniper_points=lambda: {},
        )

        with patch("src.config.get_config", return_value=SimpleNamespace()), \
             patch("src.core.pipeline.StockAnalysisPipeline", return_value=pipeline_instance):
            result = service.analyze_stock("600519", report_type="full", query_id="q1", send_notification=False)

        self.assertEqual(result["report"]["meta"]["report_type"], "full")

    def test_build_analysis_response_localizes_placeholder_stock_name_for_english(self) -> None:
        service = AnalysisService()
        result = service._build_analysis_response(
            SimpleNamespace(
                code="AAPL",
                name="股票AAPL",
                current_price=180.35,
                change_pct=1.04,
                model_used="test-model",
                analysis_summary="Momentum remains constructive.",
                operation_advice="Buy",
                trend_prediction="Bullish",
                sentiment_score=78,
                news_summary="news",
                technical_analysis="tech",
                fundamental_analysis="fundamental",
                risk_warning="risk",
                report_language="en",
                get_sniper_points=lambda: {},
            ),
            "q1",
            report_type="full",
        )

        self.assertEqual(result["stock_name"], "Unnamed Stock")
        self.assertEqual(result["report"]["meta"]["stock_name"], "Unnamed Stock")

    def test_build_analysis_response_includes_standard_report(self) -> None:
        service = AnalysisService()
        response = service._build_analysis_response(
            SimpleNamespace(
                code="NVDA",
                name="NVIDIA",
                current_price=125.3,
                change_pct=1.87,
                model_used="test-model",
                analysis_summary="等待确认",
                operation_advice="持有",
                trend_prediction="看多",
                sentiment_score=78,
                news_summary="news",
                technical_analysis="tech",
                fundamental_analysis="fundamental",
                risk_warning="risk",
                report_language="zh",
                market_snapshot={
                    "price": 125.3,
                    "close": 124.0,
                    "prev_close": 123.0,
                    "session_type": "intraday_snapshot",
                },
                dashboard={
                    "core_conclusion": {"one_sentence": "等待确认"},
                    "battle_plan": {},
                    "intelligence": {},
                },
                get_sniper_points=lambda: {},
            ),
            "q-standard-report",
            report_type="full",
        )

        self.assertIn("standard_report", response["report"]["details"])
        self.assertEqual(
            response["report"]["details"]["standard_report"]["summary_panel"]["ticker"],
            "NVDA",
        )

    def test_build_analysis_response_promotes_query_and_notification_artifacts(self) -> None:
        service = AnalysisService()
        notification_result = {"attempted": True, "status": "ok", "success": True}
        response = service._build_analysis_response(
            SimpleNamespace(
                code="NVDA",
                name="NVIDIA",
                query_id="q-top-level",
                current_price=125.3,
                change_pct=1.87,
                model_used="test-model",
                analysis_summary="等待确认",
                operation_advice="持有",
                trend_prediction="看多",
                sentiment_score=78,
                news_summary="news",
                technical_analysis="tech",
                fundamental_analysis="fundamental",
                risk_warning="risk",
                report_language="zh",
                runtime_execution={"steps": []},
                notification_result=notification_result,
                get_sniper_points=lambda: {},
            ),
            "q-fallback",
            report_type="full",
        )

        self.assertEqual(response["query_id"], "q-top-level")
        self.assertIs(response["notification_result"], notification_result)

    def test_build_analysis_response_marks_standard_report_delivery_in_runtime_execution(self) -> None:
        service = AnalysisService()
        response = service._build_analysis_response(
            SimpleNamespace(
                code="NVDA",
                name="NVIDIA",
                query_id="q-runtime-report",
                current_price=125.3,
                change_pct=1.87,
                model_used="deepseek/deepseek-chat",
                analysis_summary="等待确认",
                operation_advice="持有",
                trend_prediction="看多",
                sentiment_score=78,
                news_summary="news",
                technical_analysis="tech",
                fundamental_analysis="fundamental",
                risk_warning="risk",
                report_language="zh",
                market_snapshot={},
                dashboard={
                    "core_conclusion": {"one_sentence": "NVIDIA remains in a valid trend."},
                    "intelligence": {"risk_alerts": []},
                },
                runtime_execution={"steps": [{"key": "ai_analysis", "status": "ok"}]},
                notification_result={"attempted": False, "status": "not_configured", "success": None},
                get_sniper_points=lambda: {},
            ),
            "q-runtime-report",
            report_type="full",
        )

        runtime_execution = response["runtime_execution"]
        self.assertIsInstance(runtime_execution, dict)
        self.assertEqual(runtime_execution["report"]["standard_report"]["status"], "ok")
        self.assertTrue(runtime_execution["report"]["standard_report"]["present"])
        self.assertEqual(
            runtime_execution["report"]["standard_report"]["path"],
            "task.result.report.details.standard_report",
        )
        self.assertIn(
            {"key": "standard_report", "status": "ok"},
            runtime_execution["steps"],
        )

    def test_analyze_stock_attaches_persisted_report_after_successful_completion(self) -> None:
        service = AnalysisService()
        pipeline_instance = MagicMock()
        pipeline_instance.process_single_stock.return_value = SimpleNamespace(
            code="NVDA",
            name="NVIDIA",
            query_id="q-persisted-report",
            current_price=125.3,
            change_pct=1.87,
            model_used="test-model",
            analysis_summary="等待确认",
            operation_advice="持有",
            trend_prediction="看多",
            sentiment_score=78,
            news_summary="news",
            technical_analysis="tech",
            fundamental_analysis="fundamental",
            risk_warning="risk",
            report_language="zh",
            decision_type="buy",
            runtime_execution={"steps": []},
            notification_result={"status": "ok"},
            get_sniper_points=lambda: {},
        )

        with patch("src.config.get_config", return_value=SimpleNamespace()), \
             patch("src.core.pipeline.StockAnalysisPipeline", return_value=pipeline_instance), \
             patch("src.repositories.analysis_repo.AnalysisRepository.attach_persisted_report") as attach_report:
            attach_report.return_value = 1
            response = service.analyze_stock(
                "NVDA",
                report_type="detailed",
                query_id="q-persisted-report",
                send_notification=False,
                owner_id="user-1",
            )

        self.assertIsNotNone(response)
        attach_report.assert_called_once_with(
            "q-persisted-report",
            response["report"],
        )
        self.assertEqual(response["report"]["meta"]["generated_at"], response["report"]["meta"]["report_generated_at"])
        self.assertTrue(str(response["report"]["meta"]["generated_at"]).endswith("+08:00"))
        self.assertEqual(response["report"]["meta"]["company_name"], "NVIDIA")
        self.assertFalse(response["report"]["meta"]["is_test"])
        self.assertEqual(response["report"]["meta"]["strategy_type"], "buy")
        self.assertEqual(response["report"]["summary"]["strategy_summary"], "等待确认")

    def test_build_report_payload_includes_structured_analysis_detail_aliases(self) -> None:
        service = AnalysisService()
        result = SimpleNamespace(
            code="TSLA",
            name="Tesla",
            query_id="q-detail-aliases",
            current_price=171.22,
            change_pct=2.41,
            model_used="deepseek/deepseek-chat",
            analysis_summary="等待回踩确认后再加仓。",
            operation_advice="持有",
            trend_prediction="震荡偏强",
            sentiment_score=64,
            news_summary="news",
            technical_analysis="MACD 金叉后放大。",
            fundamental_analysis="盈利能力保持稳定。",
            risk_warning="波动率仍高。",
            report_language="zh",
            decision_type="buy",
            confidence_level="高",
            ma_analysis="MA20 上拐，MA60 走平。",
            volume_analysis="回踩缩量，反弹放量。",
            raw_response={"provider": "llm", "content": "raw ai response"},
            dashboard={
                "battle_plan": {
                    "sniper_points": {
                        "ideal_buy": "168.40 - 170.20",
                        "stop_loss": "162.80",
                        "take_profit": "184.20",
                    }
                },
                "data_perspective": {
                    "trend_status": {"ma_alignment": "多头修复"},
                    "technical_indicators": {"rsi_14": "58.3", "macd": "金叉后放大"},
                    "volume_analysis": {"volume_meaning": "回踩缩量，反弹放量"},
                },
            },
            runtime_execution={"steps": []},
            notification_result={"status": "ok"},
            get_sniper_points=lambda: {
                "ideal_buy": "168.40 - 170.20",
                "stop_loss": "162.80",
                "take_profit": "184.20",
            },
        )

        payload = service._build_report_payload(
            result,
            query_id="q-detail-aliases",
            report_type="detailed",
        )

        analysis_result = payload["details"]["analysis_result"]
        self.assertEqual(analysis_result["decision"], "buy")
        self.assertEqual(analysis_result["action"], "持有")
        self.assertEqual(analysis_result["score"], 64)
        self.assertEqual(analysis_result["confidence"], "高")
        self.assertEqual(analysis_result["entry_price"], "168.40 - 170.20")
        self.assertEqual(analysis_result["stop_loss"], "162.80")
        self.assertEqual(analysis_result["take_profit"], "184.20")
        self.assertEqual(analysis_result["technical_analysis"], "MACD 金叉后放大。")
        self.assertEqual(analysis_result["ma_alignment"], "多头修复")
        self.assertEqual(analysis_result["rsi"], "58.3")
        self.assertEqual(analysis_result["macd"], "金叉后放大")
        self.assertEqual(analysis_result["volume_dynamics"], "回踩缩量，反弹放量")
        self.assertEqual(analysis_result["full_reasoning"], "等待回踩确认后再加仓。")
        self.assertEqual(payload["details"]["raw_ai_response"], {"provider": "llm", "content": "raw ai response"})

    def test_build_report_payload_redacts_sensitive_raw_ai_response_fields(self) -> None:
        service = AnalysisService()
        result = SimpleNamespace(
            code="TSLA",
            name="Tesla",
            query_id="q-redaction",
            current_price=171.22,
            change_pct=2.41,
            model_used="openai/gpt-4.1-mini",
            analysis_summary="等待回踩确认。",
            operation_advice="持有",
            trend_prediction="震荡偏强",
            sentiment_score=64,
            news_summary="news",
            technical_analysis="tech",
            fundamental_analysis="fundamental",
            risk_warning="risk",
            report_language="zh",
            dashboard={"battle_plan": {}, "decision_context": {}, "structured_analysis": {}},
            raw_response={
                "provider": "openai",
                "raw_provider_payload": {
                    "api_key": "sk-test-public",
                    "cookie": "guest-cookie",
                    "trace_id": "trace-123",
                },
                "raw_prompt": "hidden system prompt",
                "debug_schema": {"stack_trace": "hidden"},
                "hidden_reasoning": "covert reasoning",
                "content": "visible content",
            },
            runtime_execution={"steps": []},
            notification_result={"status": "ok"},
            get_sniper_points=lambda: {},
        )

        payload = service._build_report_payload(
            result,
            query_id="q-redaction",
            report_type="detailed",
        )

        raw_ai_response = payload["details"]["raw_ai_response"]
        self.assertEqual(raw_ai_response["provider"], "openai")
        self.assertEqual(raw_ai_response["content"], "visible content")
        self.assertEqual(raw_ai_response["raw_provider_payload"], "[redacted]")
        self.assertEqual(raw_ai_response["raw_prompt"], "[redacted]")
        self.assertEqual(raw_ai_response["debug_schema"], "[redacted]")
        self.assertEqual(raw_ai_response["hidden_reasoning"], "[redacted]")
        serialized = json.dumps(raw_ai_response, ensure_ascii=False)
        self.assertNotIn("sk-test-public", serialized)
        self.assertNotIn("guest-cookie", serialized)
        self.assertNotIn("trace-123", serialized)
        self.assertNotIn("hidden system prompt", serialized)

    def test_build_report_payload_includes_decision_trace_metadata(self) -> None:
        service = AnalysisService()
        result = SimpleNamespace(
            code="WULF",
            name="WULF",
            query_id="q-decision-trace",
            current_price=21.06,
            change_pct=-1.2,
            model_used="openai/gpt-4.1-mini",
            analysis_summary="短线承压。",
            operation_advice="卖出",
            trend_prediction="看空",
            sentiment_score=38,
            news_summary="news",
            technical_analysis="price below MA20",
            fundamental_analysis="fundamental",
            risk_warning="risk",
            report_language="zh",
            decision_type="sell",
            confidence_level="高",
            llm_structured_output=True,
            llm_schema_validated=True,
            dashboard={
                "battle_plan": {
                    "sniper_points": {
                        "ideal_buy": "21.06",
                        "stop_loss": "19.50",
                        "take_profit": "22.60-22.62",
                    },
                    "position_strategy": {"entry_plan": "分批建仓策略"},
                },
                "decision_context": {
                    "score_breakdown": [
                        {"label": "技术分", "score": 32, "note": "价格位于 MA20 下方"},
                    ],
                },
                "structured_analysis": {
                    "data_quality": {"missing_fields": ["fundamentals.revenue"]},
                    "technicals": {"ma20": {"value": 22.1, "source": "technical_rule"}},
                    "fundamentals": {"status": "partial"},
                    "sentiment_analysis": {"status": "ok"},
                    "realtime_context": {"source": "yfinance", "market": "US"},
                },
            },
            runtime_execution={
                "ai": {"provider": "openai", "model": "openai/gpt-4.1-mini"},
                "data": {
                    "market": {"source": "Yahoo Finance", "status": "ok"},
                    "fundamentals": {"source": "fmp", "status": "partial", "fallback_occurred": True},
                    "news": {"source": "brave", "status": "ok"},
                },
                "steps": [],
            },
            notification_result={"status": "ok"},
            get_sniper_points=lambda: {
                "ideal_buy": "21.06",
                "stop_loss": "19.50",
                "take_profit": "22.60-22.62",
            },
        )

        payload = service._build_report_payload(
            result,
            query_id="q-decision-trace",
            report_type="detailed",
        )

        trace = payload["decision_trace"]
        self.assertEqual(trace["engine_version"], "analysis_decision_trace_v1")
        self.assertEqual(trace["endpoint"], "/api/v1/analysis/analyze")
        self.assertEqual(trace["decision_fields"]["action"]["source"], "rule")
        self.assertEqual(trace["decision_fields"]["score"]["source"], "rule")
        self.assertEqual(trace["decision_fields"]["confidence"]["source"], "llm")
        self.assertEqual(trace["decision_fields"]["entry"]["source"], "llm")
        self.assertEqual(trace["llm"]["provider"], "openai")
        self.assertEqual(trace["llm"]["template"], "decision_dashboard_v2")
        self.assertTrue(trace["llm"]["structured_output"])
        self.assertTrue(trace["llm"]["schema_validated"])
        self.assertFalse(trace["llm"]["prompt_exposed"])
        self.assertIn("data_sources", trace)
        self.assertNotIn("sk-", json.dumps(trace))
        self.assertNotIn("SYSTEM_PROMPT", json.dumps(trace))

    def test_decision_trace_flags_action_plan_and_quality_conflicts(self) -> None:
        service = AnalysisService()
        trace = service._build_decision_trace(
            SimpleNamespace(
                code="WULF",
                query_id="q-conflict",
                model_used="openai/gpt-4.1-mini",
                operation_advice="卖出",
                sentiment_score=92,
                confidence_level="高",
                decision_type="sell",
                report_language="zh",
                dashboard={
                    "battle_plan": {
                        "sniper_points": {"ideal_buy": "21.06", "stop_loss": "19.50"},
                        "position_strategy": {"entry_plan": "分批建仓策略，继续加仓"},
                    },
                    "decision_context": {"score_breakdown": [{"label": "技术分", "score": 30}]},
                    "structured_analysis": {
                        "data_quality": {
                            "missing_fields": [
                                "fundamentals.revenue",
                                "fundamentals.netIncome",
                                "news.latest",
                                "technicals.ma20",
                            ]
                        },
                        "fundamentals": {"status": "missing"},
                    },
                    "intelligence": {"risk_alerts": ["基本面数据缺失"]},
                },
                runtime_execution={"ai": {"provider": "openai", "model": "openai/gpt-4.1-mini"}, "data": {}},
                get_sniper_points=lambda: {"ideal_buy": "21.06", "stop_loss": "19.50"},
            ),
            query_id="q-conflict",
            report_type="detailed",
        )

        conflict_types = {item["type"] for item in trace["conflicts"]}
        self.assertIn("action_plan_mismatch", conflict_types)
        self.assertIn("low_data_quality_high_confidence", conflict_types)

    def test_build_analysis_report_extracts_fundamental_fields_from_snapshot(self) -> None:
        if _build_analysis_report is None:
            self.skipTest("analysis endpoint helpers unavailable in this environment")

        report = _build_analysis_report(
            report_data={
                "meta": {},
                "summary": {},
                "strategy": {},
                "details": {"news_summary": "news"},
            },
            query_id="q1",
            stock_code="600519",
            stock_name="贵州茅台",
            context_snapshot={
                "enhanced_context": {
                    "fundamental_context": {
                        "earnings": {
                            "data": {
                                "financial_report": {"report_date": "2025-12-31", "revenue": 1000},
                                "dividend": {"ttm_dividend_yield_pct": 2.5},
                            }
                        }
                    }
                }
            },
            fallback_fundamental_payload=None,
        )

        self.assertEqual(report.details.financial_report["report_date"], "2025-12-31")
        self.assertEqual(report.details.dividend_metrics["ttm_dividend_yield_pct"], 2.5)

    def test_build_analysis_report_extracts_time_contract_from_snapshot(self) -> None:
        if _build_analysis_report is None:
            self.skipTest("analysis endpoint helpers unavailable in this environment")

        report = _build_analysis_report(
            report_data={"meta": {}, "summary": {}, "strategy": {}, "details": {}},
            query_id="q1",
            stock_code="MSTR",
            stock_name="MicroStrategy",
            context_snapshot={
                "enhanced_context": {
                    "market_timestamp": "2026-03-24T16:00:00-04:00",
                    "market_session_date": "2026-03-24",
                    "news_published_at": "2026-03-24T15:10:00-04:00",
                    "report_generated_at": "2026-03-25T01:10:00+00:00",
                }
            },
            fallback_fundamental_payload=None,
        )

        self.assertEqual(report.meta.market_timestamp, "2026-03-24T16:00:00-04:00")
        self.assertEqual(report.meta.market_session_date, "2026-03-24")
        self.assertEqual(report.meta.news_published_at, "2026-03-24T15:10:00-04:00")
        self.assertEqual(report.meta.report_generated_at, "2026-03-25T01:10:00+00:00")

    def test_build_analysis_report_preserves_report_language(self) -> None:
        if _build_analysis_report is None:
            self.skipTest("analysis endpoint helpers unavailable in this environment")

        report = _build_analysis_report(
            report_data={
                "meta": {"report_language": "en"},
                "summary": {"analysis_summary": "English output"},
                "strategy": {},
                "details": {},
            },
            query_id="q1",
            stock_code="AAPL",
            stock_name="Apple",
            context_snapshot={"report_language": "zh"},
            fallback_fundamental_payload=None,
        )

        self.assertEqual(report.meta.report_language, "en")

    def test_load_sync_fundamental_sources_uses_query_and_code_for_fallback(self) -> None:
        if _load_sync_fundamental_sources is None:
            self.skipTest("analysis endpoint helpers unavailable in this environment")

        mock_db = MagicMock()
        mock_db.get_analysis_history.return_value = [SimpleNamespace(context_snapshot=None)]
        fallback_payload = {
            "earnings": {
                "data": {
                    "financial_report": {"report_date": "2025-12-31"},
                    "dividend": {"ttm_dividend_yield_pct": 2.1},
                }
            }
        }
        mock_db.get_latest_fundamental_snapshot.return_value = fallback_payload

        with patch("src.storage.DatabaseManager.get_instance", return_value=mock_db):
            context_snapshot, fundamental_snapshot = _load_sync_fundamental_sources(
                query_id="q_sync_001",
                stock_code="600519",
            )

        self.assertIsNone(context_snapshot)
        self.assertEqual(fundamental_snapshot, fallback_payload)
        mock_db.get_analysis_history.assert_called_once_with(
            query_id="q_sync_001",
            code="600519",
            limit=1,
        )
        mock_db.get_latest_fundamental_snapshot.assert_called_once_with(
            query_id="q_sync_001",
            code="600519",
        )

    def test_load_sync_fundamental_sources_uses_analysis_repository_boundary(self) -> None:
        if _load_sync_fundamental_sources is None:
            self.skipTest("analysis endpoint helpers unavailable in this environment")

        repo = MagicMock()
        repo.get_latest_record.return_value = SimpleNamespace(context_snapshot=None)
        repo.get_latest_fundamental_snapshot.return_value = {"ok": True}

        with patch("api.v1.endpoints.analysis.AnalysisRepository", create=True) as repo_cls:
            repo_cls.return_value = repo
            context_snapshot, fundamental_snapshot = _load_sync_fundamental_sources(
                query_id="q_sync_001",
                stock_code="600519",
                owner_id="user-1",
            )

        repo_cls.assert_called_once_with(owner_id="user-1")
        repo.get_latest_record.assert_called_once_with(query_id="q_sync_001", code="600519")
        repo.get_latest_fundamental_snapshot.assert_called_once_with(
            query_id="q_sync_001",
            code="600519",
        )
        self.assertIsNone(context_snapshot)
        self.assertEqual(fundamental_snapshot, {"ok": True})

    def test_handle_sync_analysis_prefers_top_level_query_id_from_service_result(self) -> None:
        if _handle_sync_analysis is None:
            self.skipTest("analysis endpoint helpers unavailable in this environment")

        fake_report = SimpleNamespace(model_dump=lambda: {"meta": {"query_id": "service-query-id"}})
        service_result = {
            "query_id": "service-query-id",
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "report": {"meta": {"query_id": "nested-query-id"}},
        }

        with patch("src.services.analysis_service.AnalysisService") as service_cls, \
             patch("api.v1.endpoints.analysis._load_sync_fundamental_sources", return_value=(None, None)) as load_sources, \
             patch("api.v1.endpoints.analysis._build_analysis_report", return_value=fake_report):
            service_cls.return_value.analyze_stock.return_value = service_result
            response = _handle_sync_analysis(
                "600519",
                SimpleNamespace(report_type="detailed", force_refresh=False),
            )

        self.assertEqual(response.query_id, "service-query-id")
        load_sources.assert_called_once_with(
            query_id="service-query-id",
            stock_code="600519",
        )

    def test_openapi_declares_single_and_batch_async_202_payloads(self) -> None:
        if create_app is None:
            self.skipTest("fastapi is not installed in this test environment")

        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(static_dir=Path(temp_dir))
            schema = app.openapi()["paths"]["/api/v1/analysis/analyze"]["post"]["responses"]["202"][
                "content"
            ]["application/json"]["schema"]

        refs = {item["$ref"] for item in schema["anyOf"]}
        self.assertEqual(
            refs,
            {
                "#/components/schemas/TaskAccepted",
                "#/components/schemas/BatchTaskAcceptedResponse",
            },
        )

    def test_format_sse_event_accepts_enum_payload(self) -> None:
        if _format_sse_event is None:
            self.skipTest("analysis endpoint helpers unavailable in this environment")
        payload = {"provider_notes": {"market_data": RealtimeSource.YFINANCE}}
        event = _format_sse_event("status", payload)
        self.assertIn('"market_data": "yfinance"', event)

    def test_trigger_analysis_rejects_blank_only_stock_inputs(self) -> None:
        if trigger_analysis is None:
            self.skipTest("fastapi is not installed in this test environment")

        with self.assertRaises(Exception) as ctx:
            trigger_analysis(
                request=SimpleNamespace(
                    stock_code="   ",
                    stock_codes=None,
                    report_type="detailed",
                    force_refresh=False,
                    async_mode=False,
                ),
                config=SimpleNamespace(),
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(
            ctx.exception.detail["message"],
            "股票代码不能为空或仅包含空白字符",
        )

    def test_trigger_analysis_rejects_obviously_invalid_mixed_input_before_resolution(self) -> None:
        if trigger_analysis is None:
            self.skipTest("fastapi is not installed in this test environment")

        with patch("api.v1.endpoints.analysis.resolve_name_to_code") as resolve_mock:
            with self.assertRaises(Exception) as ctx:
                trigger_analysis(
                    request=SimpleNamespace(
                        stock_code="00AAAAA",
                        stock_codes=None,
                        report_type="detailed",
                        force_refresh=False,
                        async_mode=True,
                    ),
                    config=SimpleNamespace(),
                )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail["message"], "请输入有效的股票代码或股票名称")
        resolve_mock.assert_not_called()

    def test_trigger_analysis_rejects_unresolvable_alpha_garbage(self) -> None:
        if trigger_analysis is None:
            self.skipTest("fastapi is not installed in this test environment")

        with patch("api.v1.endpoints.analysis.resolve_name_to_code", return_value=None), \
             patch("api.v1.endpoints.analysis.get_task_queue") as queue_mock:
            with self.assertRaises(Exception) as ctx:
                trigger_analysis(
                    request=SimpleNamespace(
                        stock_code="aaaaaaa",
                        stock_codes=None,
                        report_type="detailed",
                        force_refresh=False,
                        async_mode=True,
                    ),
                    config=SimpleNamespace(),
                )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail["message"], "请输入有效的股票代码或股票名称")
        queue_mock.assert_not_called()

    def test_trigger_analysis_accepts_us_suffix_code(self) -> None:
        if trigger_analysis is None:
            self.skipTest("fastapi is not installed in this test environment")

        queue = MagicMock()
        queue.submit_tasks_batch.return_value = ([], [])

        with patch("api.v1.endpoints.analysis.get_task_queue", return_value=queue), \
             patch("api.v1.endpoints.analysis.resolve_name_to_code") as resolve_mock:
            response = trigger_analysis(
                request=SimpleNamespace(
                    stock_code="AAPL.US",
                    stock_codes=None,
                    stock_name=None,
                    original_query="AAPL.US",
                    selection_source="manual",
                    report_type="detailed",
                    force_refresh=False,
                    async_mode=True,
                ),
                config=SimpleNamespace(),
            )

        self.assertEqual(response.status_code, 202)
        resolve_mock.assert_not_called()
        queue.submit_tasks_batch.assert_called_once_with(
            stock_codes=["AAPL.US"],
            stock_name=None,
            original_query="AAPL.US",
            selection_source="manual",
            report_type="detailed",
            force_refresh=False,
        )

    def test_trigger_analysis_allows_stock_names_with_star_and_hyphen(self) -> None:
        if trigger_analysis is None:
            self.skipTest("fastapi is not installed in this test environment")

        queue = MagicMock()
        queue.submit_tasks_batch.return_value = ([], [])

        with patch("api.v1.endpoints.analysis.resolve_name_to_code", return_value="688783"), \
             patch("api.v1.endpoints.analysis.get_task_queue", return_value=queue):
            response = trigger_analysis(
                request=SimpleNamespace(
                    stock_code="西安奕材-U",
                    stock_codes=None,
                    stock_name=None,
                    original_query="西安奕材-U",
                    selection_source="manual",
                    report_type="detailed",
                    force_refresh=False,
                    async_mode=True,
                ),
                config=SimpleNamespace(),
            )

        self.assertEqual(response.status_code, 202)
        queue.submit_tasks_batch.assert_called_once_with(
            stock_codes=["688783"],
            stock_name=None,
            original_query="西安奕材-U",
            selection_source="manual",
            report_type="detailed",
            force_refresh=False,
        )

    def test_trigger_analysis_accepts_resolvable_free_text_input(self) -> None:
        if trigger_analysis is None:
            self.skipTest("fastapi is not installed in this test environment")

        queue = MagicMock()
        queue.submit_tasks_batch.return_value = ([], [])

        with patch("api.v1.endpoints.analysis.resolve_name_to_code", return_value="600519"), \
             patch("api.v1.endpoints.analysis.get_task_queue", return_value=queue):
            response = trigger_analysis(
                request=SimpleNamespace(
                    stock_code="贵州茅台",
                    stock_codes=None,
                    stock_name=None,
                    original_query="贵州茅台",
                    selection_source="manual",
                    report_type="detailed",
                    force_refresh=False,
                    async_mode=True,
                ),
                config=SimpleNamespace(),
            )

        self.assertEqual(response.status_code, 202)
        queue.submit_tasks_batch.assert_called_once_with(
            stock_codes=["600519"],
            stock_name=None,
            original_query="贵州茅台",
            selection_source="manual",
            report_type="detailed",
            force_refresh=False,
        )

    def test_trigger_analysis_passes_explicit_research_mode_to_async_queue(self) -> None:
        if trigger_analysis is None:
            self.skipTest("fastapi is not installed in this test environment")

        queue = MagicMock()
        queue.submit_tasks_batch.return_value = ([], [])

        with patch("api.v1.endpoints.analysis.get_task_queue", return_value=queue):
            response = trigger_analysis(
                request=SimpleNamespace(
                    stock_code="AAPL",
                    stock_codes=None,
                    stock_name=None,
                    original_query="AAPL",
                    selection_source="manual",
                    report_type="detailed",
                    force_refresh=False,
                    async_mode=True,
                    research_mode="quick",
                ),
                config=SimpleNamespace(),
            )

        self.assertEqual(response.status_code, 202)
        queue.submit_tasks_batch.assert_called_once_with(
            stock_codes=["AAPL"],
            stock_name=None,
            original_query="AAPL",
            selection_source="manual",
            report_type="detailed",
            force_refresh=False,
            research_mode="quick",
        )

    def test_trigger_analysis_preserves_batch_metadata(self) -> None:
        if trigger_analysis is None:
            self.skipTest("fastapi is not installed in this test environment")

        queue = MagicMock()
        queue.submit_tasks_batch.return_value = ([], [])

        with patch("api.v1.endpoints.analysis.get_task_queue", return_value=queue):
            response = trigger_analysis(
                request=SimpleNamespace(
                    stock_code=None,
                    stock_codes=["600519", "000001"],
                    stock_name=None,
                    original_query="uploaded.csv",
                    selection_source="import",
                    report_type="detailed",
                    force_refresh=False,
                    async_mode=True,
                ),
                config=SimpleNamespace(),
            )

        self.assertEqual(response.status_code, 202)
        queue.submit_tasks_batch.assert_called_once_with(
            stock_codes=["600519", "000001"],
            stock_name=None,
            original_query="uploaded.csv",
            selection_source="import",
            report_type="detailed",
            force_refresh=False,
        )

    def test_trigger_analysis_rejects_cross_request_duplicate_for_equivalent_code_shapes(self) -> None:
        if trigger_analysis is None:
            self.skipTest("fastapi is not installed in this test environment")

        original_instance = AnalysisTaskQueue._instance
        AnalysisTaskQueue._instance = None
        try:
            queue = AnalysisTaskQueue(max_workers=1)
            queue._executor = type("ExecutorStub", (), {"submit": lambda self, *args, **kwargs: Future()})()

            with patch("api.v1.endpoints.analysis.get_task_queue", return_value=queue):
                first = trigger_analysis(
                    request=SimpleNamespace(
                        stock_code="600519",
                        stock_codes=None,
                        stock_name=None,
                        original_query=None,
                        selection_source=None,
                        report_type="detailed",
                        force_refresh=False,
                        async_mode=True,
                    ),
                    config=SimpleNamespace(),
                )
                second = trigger_analysis(
                    request=SimpleNamespace(
                        stock_code="600519.SH",
                        stock_codes=None,
                        stock_name=None,
                        original_query=None,
                        selection_source=None,
                        report_type="detailed",
                        force_refresh=False,
                        async_mode=True,
                    ),
                    config=SimpleNamespace(),
                )

            self.assertEqual(first.status_code, 202)
            self.assertEqual(second.status_code, 409)
            self.assertEqual(json.loads(second.body)["error"], "duplicate_task")
            self.assertEqual(json.loads(second.body)["stock_code"], "600519.SH")
            self.assertEqual(
                json.loads(second.body)["existing_task_id"],
                json.loads(first.body)["task_id"],
            )
        finally:
            queue = AnalysisTaskQueue._instance
            if queue is not None and queue is not original_instance:
                executor = getattr(queue, "_executor", None)
                if executor is not None and hasattr(executor, "shutdown"):
                    executor.shutdown(wait=False, cancel_futures=True)
            AnalysisTaskQueue._instance = original_instance

    def test_trigger_analysis_batch_does_not_apply_single_stock_name_to_all_tasks(self) -> None:
        if trigger_analysis is None:
            self.skipTest("fastapi is not installed in this test environment")

        queue = MagicMock()
        queue.submit_tasks_batch.return_value = ([], [])

        with patch("api.v1.endpoints.analysis.get_task_queue", return_value=queue):
            response = trigger_analysis(
                request=SimpleNamespace(
                    stock_code=None,
                    stock_codes=["600519", "000001"],
                    stock_name="贵州茅台",
                    original_query="茅台,平安银行",
                    selection_source="import",
                    report_type="detailed",
                    force_refresh=False,
                    async_mode=True,
                ),
                config=SimpleNamespace(),
            )

        self.assertEqual(response.status_code, 202)
        queue.submit_tasks_batch.assert_called_once_with(
            stock_codes=["600519", "000001"],
            stock_name=None,
            original_query="茅台,平安银行",
            selection_source="import",
            report_type="detailed",
            force_refresh=False,
        )

    def test_spa_fallback_returns_json_404_for_bare_api_path(self) -> None:
        if create_app is None:
            self.skipTest("fastapi is not installed in this test environment")

        with tempfile.TemporaryDirectory() as temp_dir:
            static_dir = Path(temp_dir)
            (static_dir / "index.html").write_text("<html>spa</html>", encoding="utf-8")
            app = create_app(static_dir=static_dir)

            serve_spa = next(
                route.endpoint for route in app.routes
                if getattr(route, "path", None) == "/{full_path:path}"
            )

            response = asyncio.run(serve_spa(None, "api"))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            json.loads(response.body),
            {"error": "not_found", "message": "API endpoint /api not found"},
        )


class BatchTaskQueueContractTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._original_instance = AnalysisTaskQueue._instance
        AnalysisTaskQueue._instance = None

    def tearDown(self) -> None:
        queue = AnalysisTaskQueue._instance
        if queue is not None and queue is not self._original_instance:
            executor = getattr(queue, "_executor", None)
            if executor is not None and hasattr(executor, "shutdown"):
                executor.shutdown(wait=False, cancel_futures=True)
        AnalysisTaskQueue._instance = self._original_instance

    def test_batch_submit_rolls_back_when_executor_submit_fails(self) -> None:
        class FailingExecutor:
            def __init__(self) -> None:
                self.submit_count = 0

            def submit(self, *args, **kwargs):
                self.submit_count += 1
                if self.submit_count == 2:
                    raise RuntimeError("executor down")
                return Future()

        queue = AnalysisTaskQueue(max_workers=1)
        queue._executor = FailingExecutor()

        with self.assertRaisesRegex(RuntimeError, "executor down"):
            queue.submit_tasks_batch(["600519", "000858"], report_type="detailed")

        self.assertEqual(queue._tasks, {})
        self.assertEqual(queue._analyzing_stocks, {})
        self.assertEqual(queue._futures, {})

    def test_batch_submit_ignores_blank_stock_codes(self) -> None:
        queue = AnalysisTaskQueue(max_workers=1)
        queue._executor = type("ExecutorStub", (), {"submit": lambda self, *args, **kwargs: Future()})()

        accepted, duplicates = queue.submit_tasks_batch(["600519", "   "], report_type="detailed")

        self.assertEqual([task.stock_code for task in accepted], ["600519"])
        self.assertEqual(duplicates, [])
        self.assertEqual(sorted(task.stock_code for task in queue._tasks.values()), ["600519"])

    def test_batch_submit_deduplicates_equivalent_stock_code_shapes(self) -> None:
        queue = AnalysisTaskQueue(max_workers=1)
        queue._executor = type("ExecutorStub", (), {"submit": lambda self, *args, **kwargs: Future()})()

        accepted, duplicates = queue.submit_tasks_batch(["600519"], report_type="detailed")

        self.assertEqual(len(accepted), 1)
        self.assertEqual(duplicates, [])
        self.assertTrue(queue.is_analyzing("600519.SH"))
        self.assertEqual(queue.get_analyzing_task_id("600519.SH"), accepted[0].task_id)

        accepted_again, duplicates_again = queue.submit_tasks_batch(["600519.SH"], report_type="detailed")

        self.assertEqual(accepted_again, [])
        self.assertEqual(len(duplicates_again), 1)
        self.assertEqual(duplicates_again[0].stock_code, "600519.SH")
        self.assertEqual(duplicates_again[0].existing_task_id, accepted[0].task_id)

    def test_submit_task_rejects_blank_stock_code(self) -> None:
        queue = AnalysisTaskQueue(max_workers=1)
        queue._executor = type("ExecutorStub", (), {"submit": lambda self, *args, **kwargs: Future()})()

        with self.assertRaisesRegex(ValueError, "股票代码不能为空或仅包含空白字符"):
            queue.submit_task("   ", report_type="detailed")

        self.assertEqual(queue._tasks, {})
        self.assertEqual(queue._analyzing_stocks, {})
        self.assertEqual(queue._futures, {})

    def test_batch_submit_broadcasts_task_created_while_queue_lock_is_held(self) -> None:
        queue = AnalysisTaskQueue(max_workers=1)
        queue._executor = type("ExecutorStub", (), {"submit": lambda self, *args, **kwargs: Future()})()
        lock_states = []

        def record_broadcast(event_type, data):
            if event_type == "task_created":
                lock_states.append(queue._data_lock._is_owned())

        queue._broadcast_event = record_broadcast

        accepted, duplicates = queue.submit_tasks_batch(["600519", "000858"], report_type="detailed")

        self.assertEqual(len(accepted), 2)
        self.assertEqual(duplicates, [])
        self.assertEqual(lock_states, [True, True])


class ImageStockExtractorContractTestCase(unittest.TestCase):
    def test_litellm_completion_patch_target_remains_available(self) -> None:
        cfg = SimpleNamespace(
            vision_model="",
            openai_vision_model=None,
            litellm_model="",
            gemini_api_keys=["sk-gemini-testkey-1234"],
            gemini_model="gemini-2.0-flash",
            anthropic_api_keys=[],
            anthropic_model="claude-3-5-sonnet-20241022",
            openai_api_keys=[],
            openai_model="gpt-4o-mini",
            openai_base_url=None,
        )
        msg = MagicMock()
        msg.content = '["600519"]'
        choice = MagicMock()
        choice.message = msg
        response = MagicMock()
        response.choices = [choice]

        with patch("src.services.image_stock_extractor.get_config", return_value=cfg), \
             patch("src.services.image_stock_extractor.litellm.completion", return_value=response) as mock_completion:
            result = _call_litellm_vision("base64data", "image/jpeg")

        self.assertEqual(result, '["600519"]')
        mock_completion.assert_called_once()


if __name__ == "__main__":
    unittest.main()
