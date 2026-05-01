# -*- coding: utf-8 -*-
"""Admin log center filtering and noise-reduction tests."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from api.deps import CurrentUser
from api.v1.endpoints import admin_logs
from src.services.execution_log_service import ExecutionLogService
from src.storage import DatabaseManager


def _admin_user() -> CurrentUser:
    return CurrentUser(
        user_id="bootstrap-admin",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )


class AdminLogsApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.db = DatabaseManager(db_url="sqlite:///:memory:")

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()

    def _record_event(
        self,
        *,
        session_id: str,
        event_name: str,
        level: str,
        category: str,
        message: str,
        status: str = "completed",
        target: str | None = None,
        detail: dict | None = None,
        event_at: datetime | None = None,
    ) -> None:
        event_at = event_at or datetime.now()
        self.db.create_execution_log_session(
            session_id=session_id,
            task_id=event_name,
            code=target,
            name=event_name,
            overall_status=status,
            truth_level="actual",
            summary={"meta": {"subsystem": category}, "log": {"level": level, "category": category, "event_name": event_name}},
            started_at=event_at,
        )
        self.db.append_execution_log_event(
            session_id=session_id,
            phase=category,
            step=event_name,
            target=target or category,
            status=status,
            truth_level="actual",
            message=message,
            detail={
                "level": level,
                "category": category,
                "event_name": event_name,
                **(detail or {}),
            },
            event_at=event_at,
        )
        self.db.finalize_execution_log_session(
            session_id=session_id,
            overall_status=status,
            truth_level="actual",
            summary={"meta": {"subsystem": category}, "log": {"level": level, "category": category, "event_name": event_name}},
            ended_at=event_at,
        )

    def test_default_query_returns_warning_and_above_only(self) -> None:
        now = datetime.now()
        self._record_event(session_id="debug-cache", event_name="MarketCacheHit", level="DEBUG", category="cache", message="cache hit", event_at=now)
        self._record_event(session_id="info-prewarm", event_name="MarketPrewarmCompleted", level="INFO", category="cache", message="prewarm done", event_at=now)
        self._record_event(session_id="warning-timeout", event_name="ExternalSourceTimeout", level="WARNING", category="data_source", message="source timeout", status="timed_out", event_at=now)
        self._record_event(session_id="error-analysis", event_name="AnalysisFailed", level="ERROR", category="analysis", message="analysis failed", status="failed", event_at=now)

        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            payload = admin_logs.list_execution_log_sessions(_=_admin_user())

        session_ids = [item.session_id for item in payload.items]
        self.assertEqual(session_ids, ["error-analysis", "warning-timeout"])
        self.assertEqual(payload.summary.error_count, 1)
        self.assertEqual(payload.summary.warning_count, 1)
        self.assertEqual(payload.summary.data_source_failure_count, 1)

    def test_min_level_info_category_query_and_limit_are_honored(self) -> None:
        self._record_event(session_id="notice-stale", event_name="MarketDataStaleServed", level="NOTICE", category="market", message="served stale SPX", target="SPX")
        self._record_event(session_id="info-refresh", event_name="MarketRefreshCompleted", level="INFO", category="market", message="SPX refresh done", target="SPX")
        self._record_event(session_id="warning-auth", event_name="AdminLoginFailed", level="WARNING", category="security", message="admin login failed", status="failed", target="admin")

        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            payload = admin_logs.list_execution_log_sessions(
                min_level="INFO",
                category="market",
                query="spx",
                limit=1,
                _=_admin_user(),
            )

        self.assertEqual(payload.total, 2)
        self.assertEqual(len(payload.items), 1)
        self.assertEqual(payload.items[0].readable_summary["log_category"], "market")
        self.assertIn(payload.items[0].readable_summary["log_level"], {"NOTICE", "INFO"})

    def test_camel_case_query_aliases_and_page_are_honored(self) -> None:
        self._record_event(session_id="notice-stale", event_name="MarketDataStaleServed", level="NOTICE", category="market", message="served stale SPX", target="SPX")
        self._record_event(session_id="warning-timeout", event_name="ExternalSourceTimeout", level="WARNING", category="data_source", message="source timeout", status="failed")

        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            payload = admin_logs.list_execution_log_sessions(
                min_level_alias="NOTICE",
                task_id_alias="MarketDataStaleServed",
                limit=1,
                page=1,
                _=_admin_user(),
            )

        self.assertEqual(payload.total, 1)
        self.assertEqual(payload.items[0].session_id, "notice-stale")

    def test_exact_level_overrides_default_min_level(self) -> None:
        self._record_event(session_id="info-routine", event_name="RoutineInfoEvent", level="INFO", category="system", message="routine info")
        self._record_event(session_id="warning-timeout", event_name="ExternalSourceTimeout", level="WARNING", category="data_source", message="source timeout", status="failed")

        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            payload = admin_logs.list_execution_log_sessions(
                level="INFO",
                _=_admin_user(),
            )

        self.assertEqual([item.session_id for item in payload.items], ["info-routine"])

    def test_since_defaults_to_recent_window(self) -> None:
        self._record_event(
            session_id="old-error",
            event_name="AnalysisFailed",
            level="ERROR",
            category="analysis",
            message="old failure",
            status="failed",
            event_at=datetime.now() - timedelta(days=8),
        )
        self._record_event(
            session_id="recent-error",
            event_name="AnalysisFailed",
            level="ERROR",
            category="analysis",
            message="recent failure",
            status="failed",
            event_at=datetime.now() - timedelta(hours=1),
        )

        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            payload = admin_logs.list_execution_log_sessions(_=_admin_user())

        self.assertEqual([item.session_id for item in payload.items], ["recent-error"])

    def test_root_lists_business_events_with_pagination_and_filters(self) -> None:
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
            service.finish_analysis_execution(execution_id=execution_id, record_id="record-tsla")

            payload = admin_logs.list_execution_logs_root(
                category="analysis",
                symbol="TSLA",
                status="partial",
                query="TSLA",
                limit=1,
                offset=0,
                _=_admin_user(),
            )

        self.assertEqual(payload.total, 1)
        self.assertFalse(payload.hasMore)
        self.assertEqual(payload.items[0].id, execution_id)
        self.assertEqual(payload.items[0].event, "TSLA")
        self.assertEqual(payload.items[0].category, "analysis")
        self.assertEqual(payload.items[0].status, "partial")
        self.assertEqual(payload.items[0].failedStepCount, 1)
        self.assertEqual(payload.items[0].recordId, "record-tsla")

    def test_root_detail_returns_business_event_steps(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_analysis_execution(symbol="TSLA", market="US")
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
            service.finish_analysis_execution(execution_id=execution_id, record_id="record-tsla")
            detail = admin_logs.get_business_event_detail(execution_id, _=_admin_user())

        self.assertEqual(detail.id, execution_id)
        self.assertEqual(detail.event, "TSLA")
        self.assertEqual(detail.steps[0].name, "fetch_news")
        self.assertEqual(detail.steps[0].errorMessage, "News API timeout after 3000ms")

    def test_root_exposes_market_overview_triage_fields_without_steps(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            session_id = service.record_market_overview_fetch(
                panel_name="MarketSentimentCard",
                endpoint_url="/api/v1/market-overview/sentiment?api_key=SECRET",
                status="failure",
                fetch_timestamp="2026-04-30T10:00:00",
                error_message="provider timeout token=SECRET",
                raw_response={
                    "provider": "finnhub",
                    "source": "market_overview",
                    "request_id": "req-sentiment",
                    "trace_id": "trace-sentiment",
                    "error": "upstream provider timeout token=SECRET",
                },
                actor={"actor_type": "anonymous", "request_id": "req-sentiment"},
            )

            payload = admin_logs.list_execution_logs_root(
                category="data_source",
                query="MarketSentimentCard",
                limit=10,
                _=_admin_user(),
            )
            detail = admin_logs.get_business_event_detail(session_id, _=_admin_user())

        self.assertEqual(payload.total, 1)
        item = payload.items[0]
        self.assertEqual(item.actorType, "anonymous")
        self.assertEqual(item.contextLabel, "MarketSentimentCard")
        self.assertEqual(item.component, "MarketSentimentCard")
        self.assertEqual(item.endpoint, "/api/v1/market-overview/sentiment?api_key=***")
        self.assertEqual(item.provider, "finnhub")
        self.assertEqual(item.source, "market_overview")
        self.assertEqual(item.reason, "timeout")
        self.assertEqual(item.requestId, "req-sentiment")
        self.assertEqual(item.traceId, "trace-sentiment")
        self.assertFalse(item.stepTraceAvailable)
        self.assertEqual(item.failedStepCount, 0)
        self.assertEqual(item.status, "failed")
        self.assertIn("provider timeout", item.errorSummary or "")
        self.assertNotIn("SECRET", str(item.model_dump()))
        self.assertEqual(detail.contextLabel, "MarketSentimentCard")
        self.assertEqual(detail.steps, [])

    def test_root_lists_guest_analysis_by_symbol(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            service.start_analysis_execution(
                symbol="ORCL",
                market="US",
                request_id="guest:session-1:req-1",
                actor={"actor_type": "guest", "role": "guest", "session_id": "session-1"},
            )
            payload = admin_logs.list_execution_logs_root(
                query="ORCL",
                limit=10,
                _=_admin_user(),
            )

        self.assertEqual(payload.total, 1)
        self.assertEqual(payload.items[0].symbol, "ORCL")
        self.assertEqual(payload.items[0].requestId, "guest:session-1:req-1")

    def test_root_detail_returns_split_step_counts_and_skipped_reasons(self) -> None:
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
            service.skip_step(
                execution_id,
                "ai_analysis",
                "AI 分析",
                reason="previous_model_succeeded",
                provider="deepseek",
                model="deepseek-v4-pro",
            )
            service.start_step(execution_id, "fetch_quote", "获取行情", category="data_market", provider="fmp")
            service.finish_step_failed(
                execution_id,
                "fetch_quote",
                provider="fmp",
                error_type="HTTPError",
                error_message="GET https://api.example.test/v1/quote?apikey=SECRET returned 403",
                reason="forbidden",
                metadata={"httpStatus": 403, "authorization": "Bearer SECRET"},
            )
            service.start_step(execution_id, "save_record", "保存分析记录", category="database")
            service.finish_execution(execution_id, status="partial")

            detail = admin_logs.get_business_event_detail(execution_id, _=_admin_user())

        self.assertEqual(detail.successStepCount, 1)
        self.assertEqual(detail.skippedStepCount, 1)
        self.assertEqual(detail.failedStepCount, 1)
        self.assertEqual(detail.unknownStepCount, 1)
        skipped = next(step for step in detail.steps if step.provider == "deepseek")
        failed = next(step for step in detail.steps if step.provider == "fmp")
        orphan = next(step for step in detail.steps if step.name == "save_record")
        self.assertEqual(skipped.status, "skipped")
        self.assertEqual(skipped.reason, "previous_model_succeeded")
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.reason, "forbidden")
        self.assertIn("apikey=***", failed.message or "")
        self.assertEqual(orphan.status, "unknown")

    def test_sessions_endpoint_still_exposes_raw_logs(self) -> None:
        self._record_event(
            session_id="warning-timeout",
            event_name="ExternalSourceTimeout",
            level="WARNING",
            category="data_source",
            message="source timeout",
            status="timed_out",
        )

        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            payload = admin_logs.list_execution_log_sessions(
                min_level="WARNING",
                _=_admin_user(),
            )

        self.assertEqual(payload.total, 1)
        self.assertEqual(payload.items[0].session_id, "warning-timeout")

    def test_session_detail_read_time_sanitizes_legacy_raw_secrets(self) -> None:
        self._record_event(
            session_id="legacy-secret",
            event_name="ExternalSourceTimeout",
            level="WARNING",
            category="data_source",
            message="failed url https://x.com?apikey=LEGACYSECRET&token=OLDTOKEN",
            status="failed",
            detail={
                "reason": "Authorization: Bearer OLDBEARER",
                "metadata": {"api_key": "LEGACYSECRET", "nested": {"token": "OLDTOKEN"}},
                "raw_response": {"password": "OLDPASSWORD"},
            },
        )

        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            payload = admin_logs.get_execution_log_session_detail("legacy-secret", _=_admin_user())

        dumped = payload.model_dump()
        self.assertNotIn("LEGACYSECRET", str(dumped))
        self.assertNotIn("OLDTOKEN", str(dumped))
        self.assertNotIn("OLDBEARER", str(dumped))
        self.assertNotIn("OLDPASSWORD", str(dumped))
        event_detail = dumped["events"][0]["detail"]
        self.assertEqual(event_detail["metadata"]["api_key"], "***")
        self.assertEqual(event_detail["raw_response"]["password"], "***")

    def test_root_filters_generic_business_execution_fields(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_execution(
                category="scanner",
                type="scan_run",
                event="Scanner: 大盘单机游戏",
                summary="扫描器运行：大盘单机游戏",
                subject="大盘单机游戏",
                scanner_id="scanner-mainland",
                request_id="req-scan",
                user_id="user-1",
            )
            service.start_step(execution_id, "run_screen", "执行扫描", category="compute", critical=True)
            service.finish_step_success(execution_id, "run_screen")
            service.finish_execution(execution_id, metadata={"matchedCount": 18})

            payload = admin_logs.list_execution_logs_root(
                category="scanner",
                type="scan_run",
                subject="大盘",
                scanner_id="scanner-mainland",
                request_id="req-scan",
                user_id="user-1",
                limit=10,
                _=_admin_user(),
            )

        self.assertEqual(payload.total, 1)
        self.assertEqual(payload.items[0].id, execution_id)
        self.assertEqual(payload.items[0].type, "scan_run")
        self.assertEqual(payload.items[0].scannerId, "scanner-mainland")
        self.assertEqual(payload.items[0].skippedStepCount, 0)


if __name__ == "__main__":
    unittest.main()
