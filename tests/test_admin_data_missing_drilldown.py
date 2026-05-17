# -*- coding: utf-8 -*-
"""Focused tests for the admin data-missing drilldown read model."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from src.services.admin_logs_service import AdminDataMissingDrilldownService
from src.storage import DatabaseManager


class AdminDataMissingDrilldownServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.db = DatabaseManager(db_url="sqlite:///:memory:")

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()

    def _record_event(
        self,
        *,
        session_id: str,
        event_at: datetime,
        phase: str,
        step: str,
        status: str,
        detail: dict,
        summary: dict,
        message: str = "",
        target: str | None = None,
        overall_status: str = "partial",
        error_code: str | None = None,
    ) -> int:
        self.db.create_execution_log_session(
            session_id=session_id,
            task_id=f"{phase}:{step}",
            code=summary.get("business_event", {}).get("symbol"),
            name=summary.get("business_event", {}).get("event"),
            overall_status=overall_status,
            truth_level="actual",
            summary=summary,
            started_at=event_at,
        )
        self.db.append_execution_log_event(
            session_id=session_id,
            phase=phase,
            step=step,
            target=target,
            status=status,
            truth_level="actual",
            message=message,
            error_code=error_code,
            detail=detail,
            event_at=event_at,
        )
        self.db.finalize_execution_log_session(
            session_id=session_id,
            overall_status=overall_status,
            truth_level="actual",
            summary=summary,
            ended_at=event_at + timedelta(seconds=1),
        )
        detail_row = self.db.get_execution_log_session_detail(session_id)
        events = detail_row.get("events") if isinstance(detail_row, dict) else []
        self.assertEqual(len(events), 1)
        return int(events[0]["id"])

    @staticmethod
    def _analysis_summary(*, symbol: str, market: str = "US", feature: str = "analysis") -> dict:
        return {
            "business_event": {
                "id": f"evt-{symbol.lower()}",
                "event": symbol,
                "category": "analysis",
                "type": "stock_analysis",
                "summary": f"{symbol} analysis degraded",
                "symbol": symbol,
                "market": market,
                "feature": feature,
            },
            "meta": {
                "subsystem": "analysis",
            },
        }

    def test_returns_empty_summary_when_no_relevant_events(self) -> None:
        now = datetime(2026, 5, 18, 9, 0, 0)
        self._record_event(
            session_id="auth-only",
            event_at=now,
            phase="security",
            step="admin_login",
            status="failed",
            target="admin",
            message="admin login failed",
            detail={
                "category": "security",
                "event_name": "AdminLoginFailed",
                "reason": "invalid_password",
            },
            summary={
                "meta": {"subsystem": "security"},
            },
            overall_status="failed",
        )

        with patch("src.services.admin_logs_service.get_db", return_value=self.db):
            payload = AdminDataMissingDrilldownService().list_items(since="")

        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["items"], [])

    def test_aggregates_missing_data_events_by_surface_domain_provider(self) -> None:
        older = datetime(2026, 5, 18, 9, 0, 0)
        newer = older + timedelta(minutes=4)
        news_time = newer + timedelta(minutes=2)

        first_id = self._record_event(
            session_id="analysis-aapl",
            event_at=older,
            phase="data_market",
            step="fetch_quote",
            status="partial",
            target="AAPL",
            message="served stale quote",
            error_code="stale_quote_served",
            detail={
                "category": "data_source",
                "event_name": "quote.stale_served",
                "provider": "fixture_market_cache",
                "source": "quote_cache",
                "freshness_state": "stale",
                "reason": "stale_quote_served",
                "stale": True,
            },
            summary=self._analysis_summary(symbol="AAPL"),
        )
        second_id = self._record_event(
            session_id="analysis-tsla",
            event_at=newer,
            phase="data_market",
            step="fetch_quote",
            status="partial",
            target="TSLA",
            message="served stale quote",
            error_code="stale_quote_served",
            detail={
                "category": "data_source",
                "event_name": "quote.stale_served",
                "provider": "fixture_market_cache",
                "source": "quote_cache",
                "freshness_state": "stale",
                "reason": "stale_quote_served",
                "stale": True,
            },
            summary=self._analysis_summary(symbol="TSLA"),
        )
        self._record_event(
            session_id="analysis-nvda",
            event_at=news_time,
            phase="data_news",
            step="fetch_news",
            status="failed",
            target="NVDA",
            message="news provider returned no rows",
            error_code="empty_result",
            detail={
                "category": "data_source",
                "event_name": "news.empty_result",
                "provider": "newsapi",
                "source": "news_feed",
                "freshness_state": "missing",
                "reason": "empty_result",
            },
            summary=self._analysis_summary(symbol="NVDA"),
            overall_status="failed",
        )

        with patch("src.services.admin_logs_service.get_db", return_value=self.db):
            payload = AdminDataMissingDrilldownService().list_items(since="")

        self.assertEqual(payload["total"], 2)
        quote_bucket = next(item for item in payload["items"] if item["missing_domain"] == "quote")
        self.assertEqual(quote_bucket["affected_surface"], "analysis")
        self.assertIsNone(quote_bucket["symbol"])
        self.assertEqual(quote_bucket["market"], "US")
        self.assertEqual(quote_bucket["provider"], "fixture_market_cache")
        self.assertEqual(quote_bucket["source"], "quote_cache")
        self.assertEqual(quote_bucket["freshness_status"], "stale")
        self.assertTrue(quote_bucket["stale"])
        self.assertTrue(quote_bucket["partial"])
        self.assertFalse(quote_bucket["fallback_used"])
        self.assertEqual(quote_bucket["reason_code"], "stale_quote_served")
        self.assertEqual(quote_bucket["latest_seen_at"], newer.isoformat())
        self.assertEqual(quote_bucket["count"], 2)
        self.assertEqual(quote_bucket["sample_event_ids"], [str(first_id), str(second_id)])

        news_bucket = next(item for item in payload["items"] if item["missing_domain"] == "news")
        self.assertEqual(news_bucket["provider"], "newsapi")
        self.assertEqual(news_bucket["freshness_status"], "missing")
        self.assertEqual(news_bucket["count"], 1)
        self.assertEqual(news_bucket["symbol"], "NVDA")

    def test_sanitizes_details_and_does_not_expose_secrets_or_tokens(self) -> None:
        now = datetime(2026, 5, 18, 10, 0, 0)
        self._record_event(
            session_id="secret-ish",
            event_at=now,
            phase="data_market",
            step="fetch_quote",
            status="failed",
            target="MSFT",
            message="upstream timeout token=SECRET",
            error_code="missing_api_key",
            detail={
                "category": "data_source",
                "event_name": "quote.missing",
                "provider": "fixture_cache?token=SECRET",
                "source": "https://upstream.example.com/data?api_key=SECRET",
                "freshness_state": "missing",
                "reason": "missing_api_key token=SECRET",
            },
            summary=self._analysis_summary(symbol="MSFT"),
            overall_status="failed",
        )

        with patch("src.services.admin_logs_service.get_db", return_value=self.db):
            payload = AdminDataMissingDrilldownService().list_items(since="")

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("SECRET", serialized)
        self.assertEqual(payload["items"][0]["reason_code"], "missing_api_key")


if __name__ == "__main__":
    unittest.main()
