# -*- coding: utf-8 -*-
"""Admin log center filtering and noise-reduction tests."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import admin_logs
from src.services.execution_log_service import ExecutionLogService
from src.storage import DatabaseManager
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _admin_logs_config(**overrides):
    values = {
        "admin_logs_retention_days": 90,
        "admin_logs_min_retention_days": 7,
        "admin_logs_storage_soft_limit_mb": 512,
        "admin_logs_storage_hard_limit_mb": 1024,
        "admin_logs_cleanup_batch_size": 1000,
        "admin_logs_auto_cleanup_enabled": False,
        "admin_logs_warning_threshold_count": 50000,
        "admin_logs_critical_threshold_count": 100000,
        "admin_logs_warning_threshold_storage_bytes": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _storage_measurement(size: int):
    return {
        "size_bytes": size,
        "measurement_scope": "postgres_tables",
        "measurement_status": "available",
        "measurement_reason": None,
    }


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


def _regular_user() -> CurrentUser:
    return CurrentUser(
        user_id="user-1",
        username="alice",
        display_name="Alice",
        role="user",
        is_admin=False,
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

    def test_session_detail_redacts_password_token_and_secret_like_metadata_keys(self) -> None:
        self._record_event(
            session_id="legacy-secret-key-shapes",
            event_name="ExternalSourceTimeout",
            level="WARNING",
            category="data_source",
            message="Authorization: Bearer RAWTOKEN",
            status="failed",
            detail={
                "metadata": {
                    "clientSecret": "CLIENTSECRET",
                    "passwordHash": "PASSWORDHASH",
                    "accessToken": "ACCESSTOKEN",
                    "nested": [{"refresh_token": "REFRESHTOKEN"}],
                    "safeLabel": "visible",
                },
            },
        )

        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            payload = admin_logs.get_execution_log_session_detail("legacy-secret-key-shapes", _=_admin_user())

        dumped = payload.model_dump()
        self.assertNotIn("CLIENTSECRET", str(dumped))
        self.assertNotIn("PASSWORDHASH", str(dumped))
        self.assertNotIn("ACCESSTOKEN", str(dumped))
        self.assertNotIn("REFRESHTOKEN", str(dumped))
        self.assertNotIn("RAWTOKEN", str(dumped))
        metadata = dumped["events"][0]["detail"]["metadata"]
        self.assertEqual(metadata["clientSecret"], "***")
        self.assertEqual(metadata["passwordHash"], "***")
        self.assertEqual(metadata["accessToken"], "***")
        self.assertEqual(metadata["nested"][0]["refresh_token"], "***")
        self.assertEqual(metadata["safeLabel"], "visible")

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

    def test_scanner_run_records_started_and_completed_lifecycle_events(self) -> None:
        run_started = datetime.now() - timedelta(seconds=3)
        run_completed = datetime.now()
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            session_id = service.record_scanner_run(
                run_detail={
                    "id": 42,
                    "market": "us",
                    "profile": "us_preopen_v1",
                    "profile_label": "US Pre-open Scanner v1",
                    "status": "completed",
                    "run_at": run_started.isoformat(),
                    "completed_at": run_completed.isoformat(),
                    "universe_size": 120,
                    "evaluated_size": 30,
                    "shortlist_size": 5,
                    "source_summary": "scanner=local_db",
                    "selected": [{"symbol": "NVDA"}],
                    "diagnostics": {
                        "coverage_summary": {
                            "input_universe_size": 120,
                            "ranked_candidate_count": 30,
                            "shortlisted_count": 5,
                            "excluded_total": 90,
                        },
                        "provider_diagnostics": {
                            "providers_used": ["local_db", "yfinance"],
                            "provider_failure_count": 0,
                            "missing_data_symbol_count": 2,
                        },
                    },
                },
                actor={"actor_type": "admin", "user_id": "bootstrap-admin"},
            )
            detail = admin_logs.get_execution_log_session_detail(session_id, _=_admin_user())
            scanner_tab = admin_logs.list_execution_log_sessions(category="scanner", min_level="INFO", since="", _=_admin_user())
            global_default = admin_logs.list_execution_log_sessions(since="", _=_admin_user())

        event_names = [event.event_name for event in detail.events]
        self.assertIn("ScannerRunStarted", event_names)
        self.assertIn("ScannerRunCompleted", event_names)
        completed = next(event for event in detail.events if event.event_name == "ScannerRunCompleted")
        self.assertEqual(completed.level, "INFO")
        self.assertEqual(completed.category, "scanner")
        self.assertEqual(completed.detail["market"], "us")
        self.assertEqual(completed.detail["configName"], "US Pre-open Scanner v1")
        self.assertEqual(completed.detail["evaluatedCount"], 30)
        self.assertEqual(completed.detail["selectedCount"], 5)
        self.assertGreaterEqual(completed.detail["durationMs"], 0)
        self.assertEqual(completed.detail["topSymbol"], "NVDA")
        self.assertEqual(scanner_tab.total, 1)
        self.assertEqual(global_default.total, 0)

    def test_failed_scanner_run_records_failed_lifecycle_event(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            session_id = service.record_scanner_run(
                run_detail={
                    "id": 43,
                    "market": "cn",
                    "profile": "cn_preopen_v1",
                    "profile_label": "A 股盘前 Scanner v1",
                    "status": "failed",
                    "run_at": datetime.now().isoformat(),
                    "completed_at": datetime.now().isoformat(),
                    "universe_size": 0,
                    "evaluated_size": 0,
                    "shortlist_size": 0,
                    "source_summary": "scanner=failed",
                    "diagnostics": {
                        "failure": {"message": "snapshot provider timeout token=SECRET"},
                        "provider_diagnostics": {"provider_failure_count": 1, "providers_used": ["akshare"]},
                    },
                },
                actor={"actor_type": "admin", "user_id": "bootstrap-admin"},
            )
            detail = admin_logs.get_execution_log_session_detail(session_id, _=_admin_user())
            scanner_tab = admin_logs.list_execution_log_sessions(category="scanner", min_level="INFO", since="", _=_admin_user())

        failed = next(event for event in detail.events if event.event_name == "ScannerRunFailed")
        self.assertEqual(failed.level, "ERROR")
        self.assertEqual(failed.category, "scanner")
        self.assertIn("snapshot provider timeout", failed.detail["errorMessage"])
        self.assertNotIn("SECRET", str(failed.model_dump()))
        self.assertEqual(scanner_tab.total, 1)

    def test_root_health_summary_groups_failures_and_sanitizes_top_errors(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            analysis_id = service.start_execution(
                category="data_source",
                type="market_overview_fetch",
                event="MarketSentimentCard",
                summary="MarketSentimentCard failed",
                subject="MarketSentimentCard",
                metadata={"provider": "newsapi"},
                actor={"username": "alice", "role": "user"},
            )
            service.start_step(analysis_id, "fetch_news", "获取新闻", category="data_source", provider="newsapi")
            service.finish_step_failed(
                analysis_id,
                "fetch_news",
                provider="newsapi",
                error_type="TimeoutError",
                error_message="News API timeout token=SECRET",
                reason="timeout",
                metadata={"api_key": "SECRET"},
            )
            service.finish_execution(analysis_id, status="failed")

            scanner_id = service.start_execution(
                category="scanner",
                type="scan_run",
                event="Scanner Run",
                summary="Scanner provider failed",
                metadata={"provider": "finnhub", "reason": "rate_limited"},
                actor={"actor_type": "system"},
            )
            service.start_step(scanner_id, "load_market_data", "加载行情", category="data_source", provider="finnhub")
            service.finish_step_failed(
                scanner_id,
                "load_market_data",
                provider="finnhub",
                error_type="HTTPError",
                error_message="provider rate limited api_key=SECRET",
                reason="rate_limited",
            )
            service.finish_execution(scanner_id, status="partial")

            payload = admin_logs.list_execution_logs_root(limit=10, _=_admin_user())

        self.assertIsNotNone(payload.health_summary)
        summary = payload.health_summary
        self.assertEqual(summary.total_events, 2)
        self.assertEqual(summary.failed_events, 1)
        self.assertEqual(summary.warning_events, 1)
        self.assertEqual(summary.status, "failing")
        self.assertAlmostEqual(summary.failure_rate, 0.5)
        self.assertEqual(summary.failures_by_category[0].key, "data_source")
        self.assertTrue(any(item.key == "newsapi" for item in summary.failures_by_provider))
        self.assertTrue(any(item.key == "timeout" for item in summary.failures_by_reason))
        self.assertTrue(any(item.key == "user" for item in summary.actor_breakdown))
        self.assertTrue(summary.top_recent_errors)
        self.assertNotIn("SECRET", str(summary.model_dump()))

    def test_root_health_summary_handles_empty_result(self) -> None:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            payload = admin_logs.list_execution_logs_root(limit=10, _=_admin_user())

        self.assertIsNotNone(payload.health_summary)
        self.assertEqual(payload.health_summary.total_events, 0)
        self.assertEqual(payload.health_summary.failed_events, 0)
        self.assertEqual(payload.health_summary.status, "healthy")
        self.assertEqual(payload.health_summary.failures_by_category, [])

    def test_storage_summary_returns_retention_and_volume_counts(self) -> None:
        now = datetime.now()
        self._record_event(
            session_id="old-error",
            event_name="AnalysisFailed",
            level="ERROR",
            category="analysis",
            message="old failure",
            status="failed",
            event_at=now - timedelta(days=120),
        )
        self._record_event(
            session_id="recent-success",
            event_name="AnalysisCompleted",
            level="INFO",
            category="analysis",
            message="recent success",
            status="completed",
            event_at=now - timedelta(days=1),
        )

        with patch("src.services.admin_logs_service.get_db", return_value=self.db):
            payload = admin_logs.get_log_storage_summary(_=_admin_user())

        self.assertEqual(payload.total_log_count, 2)
        self.assertEqual(payload.total_event_count, 2)
        self.assertEqual(payload.retention_days, 90)
        self.assertEqual(payload.minimum_retention_days, 7)
        self.assertEqual(payload.logs_older_than_retention_count, 1)
        self.assertFalse(payload.storage_size_available)
        self.assertEqual(payload.measurement_status, "unavailable")
        self.assertIsNotNone(payload.measurement_reason)
        self.assertEqual(payload.storage_soft_limit_bytes, 512 * 1024 * 1024)
        self.assertEqual(payload.storage_hard_limit_bytes, 1024 * 1024 * 1024)
        self.assertIsNotNone(payload.oldest_log_timestamp)
        self.assertIsNotNone(payload.newest_log_timestamp)
        self.assertEqual(payload.status, "warning")
        self.assertIn("cleanup", payload.recommended_cleanup_action)

    def test_storage_summary_exposes_explicit_admin_log_retention_tiers(self) -> None:
        with (
            patch("src.services.admin_logs_service.get_db", return_value=self.db),
            patch("src.services.admin_logs_service.get_config", return_value=_admin_logs_config(admin_logs_retention_days=45, admin_logs_min_retention_days=10)),
        ):
            payload = admin_logs.get_log_storage_summary(_=_admin_user())

        tiers = payload.model_dump()["retention_tiers"]
        self.assertEqual(tiers["admin_logs_standard"]["retention_days"], 45)
        self.assertEqual(tiers["admin_logs_standard"]["cleanup_mode"], "preview_first_retention_cleanup")
        self.assertEqual(tiers["admin_logs_minimum_protected"]["retention_days"], 10)
        self.assertEqual(tiers["admin_logs_minimum_protected"]["cleanup_mode"], "capacity_cleanup_floor")
        self.assertTrue(tiers["admin_logs_minimum_protected"]["preview_required"])
        self.assertTrue(tiers["admin_logs_storage_pressure"]["preview_required"])

    def test_storage_summary_uses_sqlite_database_file_size_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "logs.db"
            DatabaseManager.reset_instance()
            file_db = DatabaseManager(db_url=f"sqlite:///{db_path}")
            file_db.create_execution_log_session(
                session_id="sqlite-size",
                task_id="AnalysisCompleted",
                code="AAPL",
                name="AnalysisCompleted",
                overall_status="completed",
                truth_level="actual",
                summary={},
                started_at=datetime.now(),
            )
            file_db.append_execution_log_event(
                session_id="sqlite-size",
                phase="analysis",
                step="AnalysisCompleted",
                target="AAPL",
                status="completed",
                truth_level="actual",
                message="ok",
                detail={"level": "INFO", "category": "analysis", "event_name": "AnalysisCompleted"},
                event_at=datetime.now(),
            )
            with patch("src.services.admin_logs_service.get_db", return_value=file_db):
                payload = admin_logs.get_log_storage_summary(_=_admin_user())

            self.assertTrue(payload.storage_size_available)
            self.assertEqual(payload.measurement_scope, "sqlite_database_file")
            self.assertEqual(payload.measurement_status, "available")
            self.assertEqual(payload.storage_size_bytes, db_path.stat().st_size)
            DatabaseManager.reset_instance()

    def test_storage_summary_marks_ok_warning_and_critical_by_quota(self) -> None:
        self._record_event(
            session_id="recent-success",
            event_name="AnalysisCompleted",
            level="INFO",
            category="analysis",
            message="recent success",
            status="completed",
            event_at=datetime.now() - timedelta(days=1),
        )

        with (
            patch("src.services.admin_logs_service.get_db", return_value=self.db),
            patch("src.services.admin_logs_service.get_config", return_value=_admin_logs_config()),
            patch("src.services.admin_logs_service.AdminLogsRetentionService._storage_measurement", return_value=_storage_measurement(128 * 1024 * 1024)),
        ):
            ok_payload = admin_logs.get_log_storage_summary(_=_admin_user())
        with (
            patch("src.services.admin_logs_service.get_db", return_value=self.db),
            patch("src.services.admin_logs_service.get_config", return_value=_admin_logs_config()),
            patch("src.services.admin_logs_service.AdminLogsRetentionService._storage_measurement", return_value=_storage_measurement(690 * 1024 * 1024)),
        ):
            warning_payload = admin_logs.get_log_storage_summary(_=_admin_user())
        with (
            patch("src.services.admin_logs_service.get_db", return_value=self.db),
            patch("src.services.admin_logs_service.get_config", return_value=_admin_logs_config()),
            patch("src.services.admin_logs_service.AdminLogsRetentionService._storage_measurement", return_value=_storage_measurement(1200 * 1024 * 1024)),
        ):
            critical_payload = admin_logs.get_log_storage_summary(_=_admin_user())

        self.assertTrue(ok_payload.storage_size_available)
        self.assertEqual(ok_payload.status, "ok")
        self.assertEqual(warning_payload.status, "warning")
        self.assertTrue(warning_payload.capacity_cleanup_recommended)
        self.assertEqual(critical_payload.status, "critical")
        self.assertIn("storage_hard_limit_exceeded", critical_payload.status_reasons)

    def test_storage_summary_capacity_plan_is_preview_only_without_auto_cleanup(self) -> None:
        now = datetime.now()
        self._record_event(
            session_id="old-error",
            event_name="AnalysisFailed",
            level="ERROR",
            category="analysis",
            message="old failure",
            status="failed",
            event_at=now - timedelta(days=120),
        )

        with (
            patch("src.services.admin_logs_service.get_db", return_value=self.db),
            patch("src.services.admin_logs_service.get_config", return_value=_admin_logs_config(admin_logs_storage_soft_limit_mb=1, admin_logs_storage_hard_limit_mb=2, admin_logs_auto_cleanup_enabled=False)),
            patch("src.services.admin_logs_service.AdminLogsRetentionService._storage_measurement", return_value=_storage_measurement(3 * 1024 * 1024)),
        ):
            payload = admin_logs.get_log_storage_summary(_=_admin_user())
            remaining = admin_logs.get_log_storage_summary(_=_admin_user())

        self.assertTrue(payload.capacity_cleanup_recommended)
        self.assertFalse(payload.auto_cleanup_enabled)
        self.assertFalse(payload.auto_cleanup_performed)
        self.assertEqual(payload.capacity_cleanup_plan["mode"], "capacity")
        self.assertTrue(payload.capacity_cleanup_plan["cleanup_safe"])
        self.assertEqual(payload.capacity_cleanup_plan["estimated_candidate_sessions"], 1)
        self.assertEqual(remaining.total_log_count, 1)

    def test_storage_summary_handles_empty_logs_table(self) -> None:
        with patch("src.services.admin_logs_service.get_db", return_value=self.db):
            payload = admin_logs.get_log_storage_summary(_=_admin_user())

        self.assertEqual(payload.total_log_count, 0)
        self.assertEqual(payload.total_event_count, 0)
        self.assertIsNone(payload.oldest_log_timestamp)
        self.assertIsNone(payload.newest_log_timestamp)
        self.assertEqual(payload.logs_older_than_retention_count, 0)
        self.assertEqual(payload.status, "ok")
        self.assertFalse(payload.storage_size_available)

    def test_cleanup_dry_run_does_not_delete_logs(self) -> None:
        old_at = datetime.now() - timedelta(days=120)
        self._record_event(
            session_id="old-error",
            event_name="AnalysisFailed",
            level="ERROR",
            category="analysis",
            message="old failure",
            status="failed",
            event_at=old_at,
        )

        with patch("src.services.admin_logs_service.get_db", return_value=self.db):
            payload = admin_logs.cleanup_admin_logs(
                admin_logs.AdminLogCleanupRequest(use_retention=True, dry_run=True),
                _=_admin_user(),
            )
            remaining = admin_logs.get_log_storage_summary(_=_admin_user())

        self.assertTrue(payload.dry_run)
        self.assertEqual(payload.mode, "retention")
        self.assertEqual(payload.matched_log_count, 1)
        self.assertEqual(payload.deleted_log_count, 0)
        self.assertEqual(remaining.total_log_count, 1)

    def test_cleanup_actual_run_deletes_only_logs_older_than_cutoff(self) -> None:
        now = datetime.now()
        self._record_event(
            session_id="old-error",
            event_name="AnalysisFailed",
            level="ERROR",
            category="analysis",
            message="old failure",
            status="failed",
            event_at=now - timedelta(days=120),
        )
        self._record_event(
            session_id="recent-success",
            event_name="AnalysisCompleted",
            level="INFO",
            category="analysis",
            message="recent success",
            status="completed",
            event_at=now - timedelta(days=2),
        )

        with patch("src.services.admin_logs_service.get_db", return_value=self.db):
            payload = admin_logs.cleanup_admin_logs(
                admin_logs.AdminLogCleanupRequest(older_than=(now - timedelta(days=30)).isoformat(), dry_run=False),
                _=_admin_user(),
            )
            remaining = admin_logs.get_log_storage_summary(_=_admin_user())
            list_payload = admin_logs.list_execution_log_sessions(min_level="INFO", since="", _=_admin_user())

        self.assertFalse(payload.dry_run)
        self.assertEqual(payload.deleted_log_count, 1)
        self.assertEqual(remaining.total_log_count, 1)
        self.assertEqual([item.session_id for item in list_payload.items], ["recent-success"])

    def test_capacity_cleanup_dry_run_does_not_delete_logs(self) -> None:
        now = datetime.now()
        self._record_event(
            session_id="old-error",
            event_name="AnalysisFailed",
            level="ERROR",
            category="analysis",
            message="old failure",
            status="failed",
            event_at=now - timedelta(days=120),
        )

        with (
            patch("src.services.admin_logs_service.get_db", return_value=self.db),
            patch("src.services.admin_logs_service.get_config", return_value=_admin_logs_config(admin_logs_storage_soft_limit_mb=1, admin_logs_storage_hard_limit_mb=2)),
            patch("src.services.admin_logs_service.AdminLogsRetentionService._storage_measurement", return_value=_storage_measurement(3 * 1024 * 1024)),
        ):
            payload = admin_logs.cleanup_admin_logs(
                admin_logs.AdminLogCleanupRequest(mode="capacity", dry_run=True),
                _=_admin_user(),
            )
            remaining = admin_logs.get_log_storage_summary(_=_admin_user())

        self.assertTrue(payload.dry_run)
        self.assertEqual(payload.mode, "capacity")
        self.assertEqual(payload.matched_log_count, 1)
        self.assertEqual(payload.deleted_log_count, 0)
        self.assertEqual(remaining.total_log_count, 1)

    def test_capacity_cleanup_actual_run_preserves_min_retention(self) -> None:
        now = datetime.now()
        self._record_event(
            session_id="old-error",
            event_name="AnalysisFailed",
            level="ERROR",
            category="analysis",
            message="old failure",
            status="failed",
            event_at=now - timedelta(days=120),
        )
        self._record_event(
            session_id="recent-error",
            event_name="RecentFailure",
            level="ERROR",
            category="analysis",
            message="recent failure",
            status="failed",
            event_at=now - timedelta(days=2),
        )

        with (
            patch("src.services.admin_logs_service.get_db", return_value=self.db),
            patch("src.services.admin_logs_service.get_config", return_value=_admin_logs_config(admin_logs_storage_soft_limit_mb=1, admin_logs_storage_hard_limit_mb=2, admin_logs_min_retention_days=7)),
            patch("src.services.admin_logs_service.AdminLogsRetentionService._storage_measurement", return_value=_storage_measurement(3 * 1024 * 1024)),
        ):
            payload = admin_logs.cleanup_admin_logs(
                admin_logs.AdminLogCleanupRequest(mode="capacity", dry_run=False),
                _=_admin_user(),
            )
            list_payload = admin_logs.list_execution_log_sessions(min_level="INFO", since="", _=_admin_user())

        self.assertFalse(payload.dry_run)
        self.assertEqual(payload.mode, "capacity")
        self.assertEqual(payload.deleted_log_count, 1)
        self.assertEqual([item.session_id for item in list_payload.items], ["recent-error"])

    def test_capacity_cleanup_actual_run_emits_sanitized_audit_event(self) -> None:
        self._record_event(
            session_id="old-secret-error",
            event_name="AnalysisFailed",
            level="ERROR",
            category="analysis",
            message="old failure token=SECRET",
            status="failed",
            event_at=datetime.now() - timedelta(days=120),
            detail={
                "metadata": {
                    "api_key": "SECRET",
                    "password": "SECRET",
                    "nested": {"sessionToken": "SECRET"},
                },
            },
        )

        with (
            patch("src.services.admin_logs_service.get_db", return_value=self.db),
            patch("src.services.admin_logs_service.get_config", return_value=_admin_logs_config(admin_logs_storage_soft_limit_mb=1, admin_logs_storage_hard_limit_mb=2, admin_logs_min_retention_days=7)),
            patch("src.services.admin_logs_service.AdminLogsRetentionService._storage_measurement", return_value=_storage_measurement(3 * 1024 * 1024)),
            patch("src.services.admin_logs_service.AdminLogsRetentionService._emit_notification_event") as emit_event,
        ):
            payload = admin_logs.cleanup_admin_logs(
                admin_logs.AdminLogCleanupRequest(mode="capacity", dry_run=False),
                _=_admin_user(),
            )

        self.assertEqual(payload.deleted_log_count, 1)
        emit_event.assert_called_once()
        _, kwargs = emit_event.call_args
        self.assertEqual(kwargs["event_type"], "admin_logs.cleanup")
        self.assertEqual(kwargs["severity"], "warning")
        self.assertEqual(kwargs["payload"]["mode"], "capacity")
        self.assertEqual(kwargs["payload"]["deleted_log_count"], 1)
        self.assertNotIn("SECRET", str(kwargs))

    def test_capacity_cleanup_refuses_when_storage_size_unavailable(self) -> None:
        with patch("src.services.admin_logs_service.get_db", return_value=self.db):
            with self.assertRaises(Exception) as raised:
                admin_logs.cleanup_admin_logs(
                    admin_logs.AdminLogCleanupRequest(mode="capacity", dry_run=True),
                    _=_admin_user(),
                )

        self.assertEqual(getattr(raised.exception, "status_code", None), 400)
        self.assertIn("storage size is unavailable", str(getattr(raised.exception, "detail", {})))

    def test_invalid_config_is_safely_adjusted(self) -> None:
        with (
            patch("src.services.admin_logs_service.get_db", return_value=self.db),
            patch(
                "src.services.admin_logs_service.get_config",
                return_value=_admin_logs_config(
                    admin_logs_retention_days=5,
                    admin_logs_min_retention_days=9,
                    admin_logs_storage_soft_limit_mb=10,
                    admin_logs_storage_hard_limit_mb=5,
                ),
            ),
        ):
            payload = admin_logs.get_log_storage_summary(_=_admin_user())

        self.assertEqual(payload.minimum_retention_days, 5)
        self.assertGreater(payload.storage_hard_limit_bytes, payload.storage_soft_limit_bytes)
        self.assertIn("min_retention_days_clamped_to_retention_days", payload.status_reasons)
        self.assertIn("hard_limit_adjusted_above_soft_limit", payload.status_reasons)

    def test_cleanup_refuses_unsafe_request_without_cutoff_or_retention(self) -> None:
        with patch("src.services.admin_logs_service.get_db", return_value=self.db):
            with self.assertRaises(Exception) as raised:
                admin_logs.cleanup_admin_logs(
                    admin_logs.AdminLogCleanupRequest(dry_run=False),
                    _=_admin_user(),
                )

        self.assertEqual(getattr(raised.exception, "status_code", None), 400)

    def test_cleanup_requires_admin_authorization(self) -> None:
        app = FastAPI()
        app.include_router(admin_logs.router, prefix="/api/v1/admin/logs")
        app.dependency_overrides[get_current_user] = lambda: _regular_user()
        client = TestClient(app)

        response = client.post("/api/v1/admin/logs/cleanup", json={"use_retention": True, "dry_run": True})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["error"], "admin_required")


if __name__ == "__main__":
    unittest.main()
