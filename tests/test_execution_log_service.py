# -*- coding: utf-8 -*-
"""Focused tests for global admin observability metadata."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from src.storage import DatabaseManager
from src.services.execution_log_service import ExecutionLogService
from src.utils.security import sanitize_metadata, sanitize_url


class ExecutionLogServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.db = DatabaseManager(db_url="sqlite:///:memory:")

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()

    def test_sanitize_url_masks_query_secrets(self) -> None:
        sanitized = sanitize_url("https://x.com?a=1&apikey=SECRET&token=ABC")

        self.assertNotIn("SECRET", sanitized)
        self.assertNotIn("ABC", sanitized)
        self.assertIn("apikey=***", sanitized)
        self.assertIn("token=***", sanitized)

    def test_sanitize_metadata_masks_nested_secrets(self) -> None:
        payload = sanitize_metadata(
            {
                "safe": "value",
                "api_key": "SECRET",
                "nested": [{"token": "ABC", "note": "keep"}],
                "message": "Authorization: Bearer raw-token",
            }
        )

        self.assertEqual(payload["safe"], "value")
        self.assertEqual(payload["api_key"], "***")
        self.assertEqual(payload["nested"][0]["token"], "***")
        self.assertEqual(payload["nested"][0]["note"], "keep")
        self.assertNotIn("raw-token", str(payload))

    def test_execution_log_write_sanitizes_metadata(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_execution(
                category="analysis",
                type="stock_analysis",
                event="TSLA",
                summary="analyze TSLA",
                metadata={
                    "apikey": "SECRET-KEY",
                    "nested": {"token": "TOKEN-ABC"},
                    "url": "https://x.com?api_key=SECRET-KEY&token=TOKEN-ABC",
                },
            )
            detail = service.get_business_event_detail(execution_id)

        self.assertIsNotNone(detail)
        self.assertNotIn("SECRET-KEY", str(detail))
        self.assertNotIn("TOKEN-ABC", str(detail))
        self.assertEqual(detail["metadata"]["apikey"], "***")
        self.assertEqual(detail["metadata"]["nested"]["token"], "***")

    def test_start_session_persists_actor_scope_metadata_for_user_activity(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            session_id = service.start_session(
                task_id="task-1",
                stock_code="600519",
                stock_name="贵州茅台",
                configured_execution={"request_source": "web"},
                actor={
                    "user_id": "user-1",
                    "username": "alice",
                    "display_name": "Alice",
                    "role": "user",
                },
                subsystem="analysis",
            )
            detail = service.get_session_detail(session_id)

        self.assertIsNotNone(detail)
        readable = detail["readable_summary"]
        self.assertEqual(readable["actor_display"], "Alice")
        self.assertEqual(readable["actor_role"], "user")
        self.assertEqual(readable["session_kind"], "user_activity")
        self.assertEqual(readable["subsystem"], "analysis")

    def test_start_analysis_execution_persists_guest_actor_and_symbol_search(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_analysis_execution(
                symbol="ORCL",
                request_id="guest:session-1:req-1",
                actor={
                    "actor_type": "guest",
                    "role": "guest",
                    "session_id": "session-1",
                    "request_id": "guest:session-1:req-1",
                },
            )
            service.finish_analysis_execution(execution_id=execution_id, status="success")
            sessions, total = service.list_sessions(query="orcl", limit=10, min_level="DEBUG")
            detail = service.get_session_detail(execution_id)

        self.assertEqual(total, 1)
        self.assertEqual(sessions[0]["code"], "ORCL")
        self.assertEqual(detail["readable_summary"]["actor_role"], "guest")
        self.assertEqual(detail["readable_summary"]["actor_type"], "guest")
        self.assertEqual(detail["readable_summary"]["actor_session_id"], "session-1")

    def test_record_admin_action_persists_global_admin_observability_fields(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            session_id = service.record_admin_action(
                action="factory_reset_system",
                message="Factory reset completed",
                actor={
                    "user_id": "bootstrap-admin",
                    "username": "admin",
                    "display_name": "Bootstrap Admin",
                    "role": "admin",
                },
                subsystem="system_control",
                destructive=True,
                detail={"counts": {"users": 2}},
            )
            sessions, total = service.list_sessions(limit=10)
            detail = service.get_session_detail(session_id)

        self.assertEqual(total, 1)
        self.assertEqual(sessions[0]["readable_summary"]["session_kind"], "admin_action")
        self.assertEqual(sessions[0]["readable_summary"]["actor_role"], "admin")
        self.assertEqual(sessions[0]["readable_summary"]["action_name"], "factory_reset_system")
        self.assertTrue(sessions[0]["readable_summary"]["destructive"])
        self.assertEqual(detail["events"][0]["detail"]["action"], "factory_reset_system")

    def test_record_market_overview_fetch_persists_panel_audit_fields(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            session_id = service.record_market_overview_fetch(
                panel_name="VolatilityCard",
                endpoint_url="/api/v1/market-overview/volatility",
                status="failure",
                fetch_timestamp="2026-04-29T10:00:00",
                error_message="provider timeout api_key=SECRET",
                raw_response={
                    "cache": "stale_or_fallback",
                    "error": "provider timeout token=SECRET",
                    "provider": "finnhub",
                    "trace_id": "trace-volatility",
                    "request_id": "req-volatility",
                },
                actor={"user_id": "user-1", "username": "alice", "role": "user", "request_id": "req-volatility"},
            )
            detail = service.get_session_detail(session_id)
            business = service.get_business_event_detail(session_id)

        self.assertIsNotNone(detail)
        self.assertEqual(detail["readable_summary"]["subsystem"], "data_source")
        self.assertEqual(detail["events"][0]["phase"], "data_source")
        self.assertEqual(detail["events"][0]["level"], "WARNING")
        self.assertEqual(detail["events"][0]["category"], "data_source")
        self.assertEqual(detail["events"][0]["detail"]["panel_name"], "VolatilityCard")
        self.assertEqual(detail["events"][0]["detail"]["endpoint_url"], "/api/v1/market-overview/volatility")
        self.assertNotIn("SECRET", str(detail))
        self.assertEqual(detail["events"][0]["detail"]["raw_response"]["provider"], "finnhub")
        self.assertEqual(business["actorType"], "user")
        self.assertEqual(business["actorLabel"], "alice")
        self.assertEqual(business["contextLabel"], "VolatilityCard")
        self.assertEqual(business["component"], "VolatilityCard")
        self.assertEqual(business["endpoint"], "/api/v1/market-overview/volatility")
        self.assertEqual(business["provider"], "finnhub")
        self.assertEqual(business["reason"], "timeout")
        self.assertIn("provider timeout", business["errorSummary"])
        self.assertIn("api_key=***", business["errorSummary"])
        self.assertEqual(business["traceId"], "trace-volatility")
        self.assertEqual(business["requestId"], "req-volatility")
        self.assertFalse(business["stepTraceAvailable"])
        self.assertEqual(business["failedStepCount"], 0)
        self.assertEqual(business["status"], "failed")

    def test_record_scanner_run_persists_actor_attribution(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            session_id = service.record_scanner_run(
                run_detail={
                    "id": 99,
                    "market": "us",
                    "profile": "us_preopen_v1",
                    "profile_label": "US Preopen",
                    "trigger_mode": "manual",
                    "status": "completed",
                    "shortlist_size": 3,
                    "diagnostics": {"coverage_summary": {"input_universe_size": 120, "shortlisted_count": 3}},
                },
                actor={"user_id": "user-1", "username": "alice", "role": "user"},
            )
            detail = service.get_session_detail(session_id)

        self.assertEqual(detail["readable_summary"]["subsystem"], "scanner")
        self.assertEqual(detail["readable_summary"]["actor_role"], "user")
        self.assertEqual(detail["events"][0]["detail"]["market"], "us")

    def test_record_portfolio_event_persists_business_audit_fields(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            session_id = service.record_portfolio_event(
                action="buy_trade",
                message="Portfolio buy trade recorded for AAPL",
                actor={"user_id": "user-1", "username": "alice", "role": "user"},
                account_id=7,
                symbol="AAPL",
                currency="USD",
                record_id=42,
                detail={"quantity": 3, "price": 188.2, "market": "us"},
            )
            sessions, total = service.list_sessions(query="AAPL", limit=10, min_level="DEBUG")
            detail = service.get_session_detail(session_id)

        self.assertEqual(total, 1)
        self.assertEqual(sessions[0]["code"], "AAPL")
        self.assertEqual(detail["readable_summary"]["subsystem"], "portfolio")
        self.assertEqual(detail["readable_summary"]["actor_role"], "user")
        self.assertEqual(detail["events"][0]["detail"]["action"], "buy_trade")
        self.assertEqual(detail["events"][0]["detail"]["account_id"], 7)

    def test_summarize_business_events_groups_and_sanitizes_failures(self) -> None:
        service = ExecutionLogService()
        summary = service.summarize_business_events([
            {
                "id": "evt-1",
                "event": "TSLA",
                "category": "analysis",
                "status": "failed",
                "provider": "newsapi",
                "source": "newsapi",
                "reason": "timeout",
                "errorSummary": "upstream timeout token=SECRET",
                "actorType": "user",
                "startedAt": "2026-05-01T10:00:00",
                "durationMs": 6200,
            },
            {
                "id": "evt-2",
                "event": "Scanner",
                "category": "scanner",
                "status": "partial",
                "provider": "finnhub",
                "reason": "rate_limited",
                "actorType": "system",
                "startedAt": "2026-05-01T10:05:00",
            },
            {
                "id": "evt-3",
                "event": "AAPL",
                "category": "analysis",
                "status": "success",
                "provider": "fmp",
                "actorType": "user",
                "startedAt": "2026-05-01T10:10:00",
            },
        ])

        self.assertEqual(summary["total_events"], 3)
        self.assertEqual(summary["failed_events"], 1)
        self.assertEqual(summary["warning_events"], 1)
        self.assertEqual(summary["slow_events"], 1)
        self.assertEqual(summary["status"], "degraded")
        self.assertEqual(summary["failures_by_category"][0]["key"], "analysis")
        self.assertEqual(summary["failures_by_provider"][0]["key"], "newsapi")
        self.assertEqual(summary["failures_by_reason"][0]["key"], "timeout")
        self.assertEqual(summary["actor_breakdown"][0]["key"], "user")
        self.assertNotIn("SECRET", str(summary))

    def test_summarize_business_events_handles_empty_input(self) -> None:
        service = ExecutionLogService()
        summary = service.summarize_business_events([])

        self.assertEqual(summary["total_events"], 0)
        self.assertEqual(summary["failed_events"], 0)
        self.assertEqual(summary["failure_rate"], 0)
        self.assertEqual(summary["status"], "healthy")
        self.assertEqual(summary["top_recent_errors"], [])

    def test_list_sessions_filters_by_task_id(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            service.start_session(
                task_id="task-a",
                stock_code="TSLA",
                stock_name="Tesla",
                configured_execution={},
                actor={"user_id": "user-1", "role": "user"},
                subsystem="analysis",
            )
            service.start_session(
                task_id="task-b",
                stock_code="NVDA",
                stock_name="NVIDIA",
                configured_execution={},
                actor={"user_id": "user-1", "role": "user"},
                subsystem="analysis",
            )

            items, total = service.list_sessions(task_id="task-b", limit=10)

        self.assertEqual(total, 1)
        self.assertEqual(items[0]["task_id"], "task-b")

    def test_analysis_detail_exposes_operation_log_contract_with_fallback_diagnostics(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            session_id = service.start_session(
                task_id="task-tsla",
                stock_code="TSLA",
                stock_name="Tesla",
                configured_execution={},
                actor={"user_id": "user-1", "role": "user"},
                subsystem="analysis",
            )
            service.append_runtime_result(
                session_id=session_id,
                runtime_execution={
                    "score": 5.2,
                    "ai": {
                        "model": "alpaca",
                        "gateway": "deepseek",
                        "fallback_occurred": True,
                        "attempt_chain": [
                            {
                                "model": "gemini-2.5-flash",
                                "version": "2.5-flash",
                                "status": "failed",
                                "reason": "Service unavailable, code 503",
                            },
                            {
                                "model": "alpaca",
                                "version": "fallback",
                                "status": "succeeded",
                                "message": "Fallback after primary failed",
                            },
                        ],
                    },
                    "data": {
                        "market": {
                            "source": "Finnhub",
                            "status": "succeeded",
                            "source_chain": [
                                {
                                    "source": "Yahoo Finance",
                                    "status": "failed",
                                    "reason": "Timeout error",
                                    "response": {"status_code": 504},
                                    "stack_trace": "TimeoutError: Yahoo Finance",
                                },
                                {
                                    "source": "Finnhub",
                                    "status": "succeeded",
                                    "message": "Data fetched",
                                },
                            ],
                        },
                    },
                },
                notification_result={"status": "not_configured"},
                query_id="query-tsla",
                overall_status="partial_success",
            )
            items, _ = service.list_sessions(limit=10)
            detail = service.get_session_detail(session_id)

        self.assertEqual(items[0]["readable_summary"]["operation_category"], "single_stock_analysis")
        self.assertEqual(items[0]["readable_summary"]["operation_type"], "Single Stock Analysis")
        self.assertEqual(items[0]["readable_summary"]["operation_target"], "TSLA")
        self.assertEqual(items[0]["readable_summary"]["operation_status"], "partial fail")
        self.assertEqual(items[0]["readable_summary"]["key_metric"], "Score 5.2")

        operation_detail = detail["operation_detail"]
        self.assertEqual(operation_detail["operation_category"], "single_stock_analysis")
        self.assertEqual(operation_detail["target"], "TSLA")
        self.assertTrue(any(call["model"] == "gemini-2.5-flash" and call["status"] == "fail" for call in operation_detail["ai_calls"]))
        self.assertTrue(any(call["source"] == "Yahoo Finance" and call["status"] == "fail" for call in operation_detail["data_source_calls"]))
        self.assertTrue(any("Fallback" in item["label"] for item in operation_detail["timeline"]))
        self.assertTrue(any("Timeout error" in item["message"] for item in operation_detail["diagnostics"]))

    def test_runtime_trace_primary_success_backup_skipped_merges_to_final_provider_steps(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            session_id = service.start_session(
                task_id="task-msft",
                stock_code="MSFT",
                stock_name="Microsoft",
                configured_execution={},
                actor={"user_id": "user-1", "role": "user"},
                subsystem="analysis",
            )
            service.append_runtime_result(
                session_id=session_id,
                runtime_execution={
                    "ai": {
                        "gateway": "gemini",
                        "model": "gemini-2.5-flash",
                        "attempt_chain": [
                            {"model": "gemini-2.5-flash", "status": "succeeded", "message": "ok"},
                            {"model": "deepseek-v4-pro", "status": "skipped_because_previous_succeeded", "reason": "previous_model_succeeded"},
                        ],
                    },
                    "data": {
                        "market": {
                            "source": "Yahoo",
                            "status": "succeeded",
                            "source_chain": [
                                {"source": "Yahoo", "status": "succeeded", "message": "Quote fetched"},
                                {"source": "FMP", "status": "skipped_because_previous_succeeded", "reason": "previous_provider_succeeded"},
                            ],
                        }
                    },
                },
                notification_result={"status": "not_configured"},
                query_id="query-msft",
                overall_status="success",
            )
            detail = service.get_business_event_detail(session_id)

        ai_steps = [step for step in detail["steps"] if step["name"] == "ai_analysis"]
        quote_steps = [step for step in detail["steps"] if step["name"] == "fetch_quote"]
        self.assertEqual(len(ai_steps), 2)
        self.assertEqual(len(quote_steps), 2)
        self.assertEqual(detail["successStepCount"], 2)
        self.assertEqual(detail["skippedStepCount"], 2)
        self.assertEqual({step["status"] for step in ai_steps}, {"success", "skipped"})
        self.assertEqual({step["status"] for step in quote_steps}, {"success", "skipped"})
        self.assertEqual(sum(1 for step in ai_steps if step["status"] == "success"), 1)

    def test_analysis_execution_groups_steps_and_finishes_partial(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_analysis_execution(
                symbol="TSLA",
                market="US",
                analysis_type="recent",
                user_id="user-1",
                request_id="req-tsla",
            )
            service.add_execution_step(
                execution_id=execution_id,
                name="fetch_quote",
                label="获取行情",
                provider="yahoo",
                status="success",
                duration_ms=320,
            )
            service.add_execution_step(
                execution_id=execution_id,
                name="fetch_news",
                label="获取新闻",
                provider="newsapi",
                status="failed",
                duration_ms=3000,
                error_type="TimeoutError",
                error_message="News API timeout after 3000ms",
                critical=False,
            )
            service.add_execution_step(
                execution_id=execution_id,
                name="ai_analysis",
                label="AI 分析",
                provider="deepseek",
                status="success",
                duration_ms=8600,
            )
            service.add_execution_step(
                execution_id=execution_id,
                name="save_record",
                label="保存分析记录",
                status="success",
                record_id="history-1",
            )
            event = service.finish_analysis_execution(
                execution_id=execution_id,
                record_id="history-1",
            )
            items, total = service.list_business_events(category="analysis", symbol="TSLA", status="partial", query="TSLA")
            detail = service.get_business_event_detail(execution_id)

        self.assertEqual(event["status"], "partial")
        self.assertEqual(event["event"], "TSLA")
        self.assertEqual(event["category"], "analysis")
        self.assertEqual(event["summary"], "用户分析 TSLA，部分数据源失败")
        self.assertEqual(event["stepCount"], 4)
        self.assertEqual(event["failedStepCount"], 1)
        self.assertEqual(event["recordId"], "history-1")
        self.assertEqual(total, 1)
        self.assertEqual(items[0]["id"], execution_id)
        self.assertEqual(detail["steps"][1]["name"], "fetch_news")
        self.assertEqual(detail["steps"][1]["errorMessage"], "News API timeout after 3000ms")

    def test_analysis_execution_finishes_failed_when_ai_fails(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_analysis_execution(symbol="NVDA", market="US")
            service.add_execution_step(
                execution_id=execution_id,
                name="fetch_quote",
                label="获取行情",
                status="success",
            )
            service.add_execution_step(
                execution_id=execution_id,
                name="ai_analysis",
                label="AI 分析",
                status="failed",
                error_type="RuntimeError",
                error_message="LLM unavailable",
                critical=True,
            )
            event = service.finish_analysis_execution(execution_id=execution_id)
            items, total = service.list_business_events(category="analysis", symbol="NVDA", status="failed")

        self.assertEqual(event["status"], "failed")
        self.assertEqual(total, 1)
        self.assertEqual(items[0]["failedStepCount"], 1)

    def test_generic_execution_lifecycle_supports_scanner(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_execution(
                category="scanner",
                type="scan_run",
                event="Scanner: 大盘单机游戏",
                summary="扫描器运行：大盘单机游戏",
                subject="大盘单机游戏",
                scanner_id="scanner-a",
                metadata={"universeSize": 4200},
            )
            service.start_step(execution_id, "load_universe", "加载股票池", category="compute", critical=True)
            service.finish_step_success(execution_id, "load_universe", metadata={"loaded": 4200})
            service.finish_execution(execution_id, metadata={"matchedCount": 18})
            items, total = service.list_business_events(category="scanner", type="scan_run", subject="大盘")
            detail = service.get_business_event_detail(execution_id)

        self.assertEqual(total, 1)
        self.assertEqual(items[0]["category"], "scanner")
        self.assertEqual(items[0]["type"], "scan_run")
        self.assertEqual(items[0]["scannerId"], "scanner-a")
        self.assertEqual(items[0]["successStepCount"], 1)
        self.assertEqual(items[0]["skippedStepCount"], 0)
        self.assertEqual(detail["steps"][0]["status"], "success")

    def test_backtest_execution_supported(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_execution(
                category="backtest",
                type="backtest_run",
                event="Backtest: MA20 Breakout",
                summary="回测策略 MA20 Breakout",
                subject="MA20 Breakout",
                strategy_id="strategy-ma20",
                backtest_id="bt-1",
            )
            for name, label in [
                ("load_price_data", "加载价格数据"),
                ("generate_signals", "生成信号"),
                ("calculate_metrics", "计算指标"),
            ]:
                service.start_step(execution_id, name, label, category="compute", critical=True)
                service.finish_step_success(execution_id, name)
            event = service.finish_execution(execution_id)
            items, total = service.list_business_events(category="backtest", strategy_id="strategy-ma20")

        self.assertEqual(event["status"], "success")
        self.assertEqual(total, 1)
        self.assertEqual(items[0]["backtestId"], "bt-1")
        self.assertEqual(items[0]["stepCount"], 3)

    def test_skipped_backup_provider_not_success(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_execution(
                category="data_source",
                type="provider_validation",
                event="Provider validation",
                summary="数据源校验",
            )
            service.start_step(execution_id, "test_quote_endpoint", "测试行情接口", provider="fmp", critical=True)
            service.finish_step_success(execution_id, "test_quote_endpoint", provider="fmp")
            service.skip_step(
                execution_id,
                "test_quote_endpoint",
                "测试行情接口",
                reason="previous_provider_succeeded",
                provider="yahoo",
            )
            event = service.finish_execution(execution_id)
            detail = service.get_business_event_detail(execution_id)

        self.assertEqual(event["successStepCount"], 1)
        self.assertEqual(event["skippedStepCount"], 1)
        self.assertEqual(event["failedStepCount"], 0)
        self.assertTrue(any(step["provider"] == "yahoo" and step["status"] == "skipped" for step in detail["steps"]))

    def test_llm_primary_success_backup_skipped(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_execution(
                category="analysis",
                type="stock_analysis",
                event="MSFT",
                summary="用户分析 MSFT",
                subject="MSFT",
                symbol="MSFT",
            )
            service.start_step(execution_id, "ai_analysis", "AI 分析", category="ai_model", provider="gemini", model="gemini-2.5", critical=True)
            service.finish_step_success(execution_id, "ai_analysis", provider="gemini", model="gemini-2.5")
            service.skip_step(execution_id, "ai_analysis", "AI 分析", reason="previous_model_succeeded", provider="deepseek", model="deepseek-chat")
            event = service.finish_execution(execution_id, status="success")
            detail = service.get_business_event_detail(execution_id)

        gemini = next(step for step in detail["steps"] if step["provider"] == "gemini")
        deepseek = next(step for step in detail["steps"] if step["provider"] == "deepseek")
        self.assertEqual(event["status"], "success")
        self.assertEqual(event["successStepCount"], 1)
        self.assertEqual(event["skippedStepCount"], 1)
        self.assertEqual(event["failedStepCount"], 0)
        self.assertEqual(gemini["status"], "success")
        self.assertEqual(deepseek["status"], "skipped")
        self.assertEqual(deepseek["reason"], "previous_model_succeeded")

    def test_provider_primary_success_backup_skipped(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_execution(
                category="analysis",
                type="stock_analysis",
                event="MSFT",
                summary="用户分析 MSFT",
                subject="MSFT",
                symbol="MSFT",
            )
            service.start_step(execution_id, "fetch_quote", "获取行情", category="data_market", provider="yahoo", endpoint="/quote", critical=True)
            service.finish_step_success(execution_id, "fetch_quote", provider="yahoo", endpoint="/quote")
            service.skip_step(
                execution_id,
                "fetch_quote",
                "获取行情",
                reason="previous_provider_succeeded",
                provider="fmp",
                endpoint="/quote",
            )
            event = service.finish_execution(execution_id, status="success")
            detail = service.get_business_event_detail(execution_id)

        yahoo = next(step for step in detail["steps"] if step["provider"] == "yahoo")
        fmp = next(step for step in detail["steps"] if step["provider"] == "fmp")
        self.assertEqual(event["successStepCount"], 1)
        self.assertEqual(event["skippedStepCount"], 1)
        self.assertEqual(event["failedStepCount"], 0)
        self.assertEqual(yahoo["status"], "success")
        self.assertEqual(fmp["status"], "skipped")
        self.assertEqual(fmp["reason"], "previous_provider_succeeded")
        self.assertNotEqual(fmp["status"], "success")

    def test_primary_failed_backup_success(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_execution(
                category="analysis",
                type="stock_analysis",
                event="MSFT",
                summary="用户分析 MSFT",
                subject="MSFT",
                symbol="MSFT",
            )
            service.start_step(execution_id, "ai_analysis", "AI 分析", category="ai_model", provider="gemini", model="gemini-2.5", critical=False)
            service.finish_step_failed(
                execution_id,
                "ai_analysis",
                provider="gemini",
                model="gemini-2.5",
                error_type="HTTPError",
                error_message="Gemini returned 429 rate limited",
                reason="rate_limited",
            )
            service.start_step(execution_id, "ai_analysis", "AI 分析", category="ai_model", provider="deepseek", model="deepseek-v4-pro", critical=True)
            service.finish_step_success(execution_id, "ai_analysis", provider="deepseek", model="deepseek-v4-pro")
            event = service.finish_execution(execution_id, status="partial")
            detail = service.get_business_event_detail(execution_id)

        gemini = next(step for step in detail["steps"] if step["provider"] == "gemini")
        deepseek = next(step for step in detail["steps"] if step["provider"] == "deepseek")
        self.assertEqual(event["failedStepCount"], 1)
        self.assertEqual(event["successStepCount"], 1)
        self.assertEqual(gemini["status"], "failed")
        self.assertEqual(deepseek["status"], "success")

    def test_missing_key_maps_to_skipped(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_execution(
                category="analysis",
                type="stock_analysis",
                event="MSFT",
                summary="用户分析 MSFT",
                subject="MSFT",
                symbol="MSFT",
            )
            service.skip_step(execution_id, "fetch_news", "获取新闻", reason="missing_api_key", provider="finnhub")
            event = service.finish_execution(execution_id, status="success")
            detail = service.get_business_event_detail(execution_id)

        skipped = detail["steps"][0]
        self.assertEqual(skipped["status"], "skipped")
        self.assertEqual(skipped["reason"], "missing_api_key")
        self.assertEqual(event["successStepCount"], 0)
        self.assertEqual(event["failedStepCount"], 0)
        self.assertEqual(event["skippedStepCount"], 1)

    def test_circuit_open_maps_to_skipped(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_execution(
                category="analysis",
                type="stock_analysis",
                event="MSFT",
                summary="用户分析 MSFT",
                subject="MSFT",
                symbol="MSFT",
            )
            service.skip_step(execution_id, "fetch_quote", "获取行情", reason="circuit_open", provider="fmp")
            event = service.finish_execution(execution_id, status="success")
            detail = service.get_business_event_detail(execution_id)

        skipped = detail["steps"][0]
        self.assertEqual(skipped["status"], "skipped")
        self.assertEqual(skipped["reason"], "circuit_open")
        self.assertEqual(event["skippedStepCount"], 1)

    def test_forbidden_provider_call_maps_to_failed(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_execution(
                category="analysis",
                type="stock_analysis",
                event="MSFT",
                summary="用户分析 MSFT",
                subject="MSFT",
                symbol="MSFT",
            )
            service.start_step(execution_id, "fetch_quote", "获取行情", category="data_market", provider="alpaca")
            service.finish_step_failed(
                execution_id,
                "fetch_quote",
                provider="alpaca",
                error_type="HTTPError",
                error_message="GET https://api.example.test/v1/quote?apikey=secret-token returned 403",
                reason="forbidden",
                metadata={"httpStatus": 403, "authorization": "Bearer secret", "nested": {"api_key": "secret"}},
            )
            event = service.finish_execution(execution_id, status="failed")
            detail = service.get_business_event_detail(execution_id)

        self.assertEqual(event["successStepCount"], 0)
        self.assertEqual(event["skippedStepCount"], 0)
        self.assertEqual(event["failedStepCount"], 1)
        failed = next(step for step in detail["steps"] if step["status"] == "failed")
        self.assertEqual(failed["reason"], "forbidden")
        self.assertIn("apikey=***", failed["message"])
        self.assertIn("403", failed["errorMessage"])
        self.assertEqual(failed["metadata"]["authorization"], "***")
        self.assertEqual(failed["metadata"]["nested"]["api_key"], "***")

    def test_attempting_then_success_merges_single_step(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_execution(
                category="analysis",
                type="stock_analysis",
                event="MSFT",
                summary="用户分析 MSFT",
                subject="MSFT",
                symbol="MSFT",
            )
            service.start_step(execution_id, "ai_analysis", "AI 分析", category="ai_model", provider="gemini", model="gemini-2.5")
            service.finish_step_success(execution_id, "ai_analysis", provider="gemini", model="gemini-2.5")
            event = service.finish_execution(execution_id, status="success")
            detail = service.get_business_event_detail(execution_id)

        self.assertEqual(len(detail["steps"]), 1)
        self.assertEqual(detail["steps"][0]["status"], "success")
        self.assertFalse(any(step["status"] == "running" for step in detail["steps"]))
        self.assertEqual(event["successStepCount"], 1)

    def test_attempting_then_failed_merges_single_step(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_execution(
                category="analysis",
                type="stock_analysis",
                event="MSFT",
                summary="用户分析 MSFT",
                subject="MSFT",
                symbol="MSFT",
            )
            service.start_step(execution_id, "fetch_quote", "获取行情", category="data_market", provider="fmp", endpoint="/quote")
            service.finish_step_failed(
                execution_id,
                "fetch_quote",
                provider="fmp",
                endpoint="/quote",
                error_type="TimeoutError",
                error_message="provider timeout",
                reason="timeout",
            )
            event = service.finish_execution(execution_id, status="failed")
            detail = service.get_business_event_detail(execution_id)

        self.assertEqual(len(detail["steps"]), 1)
        self.assertEqual(detail["steps"][0]["status"], "failed")
        self.assertFalse(any(step["status"] == "running" for step in detail["steps"]))
        self.assertEqual(event["failedStepCount"], 1)

    def test_execution_finished_closes_orphan_running_steps(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_execution(
                category="scheduler",
                type="scheduled_job",
                event="Daily job",
                summary="定时任务",
            )
            service.start_step(execution_id, "notify_user", "通知用户", category="notification")
            event = service.finish_execution(execution_id, status="success")
            detail = service.get_business_event_detail(execution_id)

        self.assertEqual(event["unknownStepCount"], 1)
        self.assertFalse(any(step["status"] == "running" for step in detail["steps"]))
        self.assertEqual(detail["steps"][0]["status"], "unknown")

    def test_skipped_steps_do_not_count_as_success(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_execution(
                category="analysis",
                type="stock_analysis",
                event="MSFT",
                summary="用户分析 MSFT",
                subject="MSFT",
                symbol="MSFT",
            )
            service.skip_step(execution_id, "fetch_news", "获取新闻", reason="previous_provider_succeeded", provider="gnews")
            event = service.finish_execution(execution_id, status="success")

        self.assertEqual(event["successStepCount"], 0)
        self.assertEqual(event["failedStepCount"], 0)
        self.assertEqual(event["skippedStepCount"], 1)

    def test_raw_system_logs_do_not_pollute_analysis_business_events(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            service.record_api_request(
                route="/api/v1/market-overview/indices",
                method="GET",
                status_code=200,
                duration_ms=2400,
                request_id="req-slow",
            )
            service.start_analysis_execution(symbol="AAPL", market="US")
            items, total = service.list_business_events(category="analysis", query="AAPL")

        self.assertEqual(total, 1)
        self.assertEqual(items[0]["event"], "AAPL")


if __name__ == "__main__":
    unittest.main()
