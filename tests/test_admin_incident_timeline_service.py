# -*- coding: utf-8 -*-
"""Read-only admin incident timeline foundation tests."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from src.services.admin_incident_timeline_service import AdminIncidentTimelineService
from src.services.execution_log_service import ExecutionLogService
from src.storage import DatabaseManager


class AdminIncidentTimelineServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.db = DatabaseManager(db_url="sqlite:///:memory:")

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()

    def _seed_degraded_analysis(self) -> str:
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            service = ExecutionLogService()
            execution_id = service.start_execution(
                category="analysis",
                type="stock_analysis",
                event="AAPL",
                summary="用户分析 AAPL 部分数据源失败",
                subject="AAPL",
                symbol="AAPL",
                request_id="req-aapl",
                user_id="user-1",
                metadata={"safeLabel": "kept", "api_key": "SECRET"},
                actor={
                    "actor_type": "guest",
                    "session_id": "guest-session-1",
                    "request_id": "req-aapl",
                },
            )
            service.start_step(
                execution_id,
                "fetch_quote",
                "获取行情",
                category="data_market",
                provider="fmp",
                endpoint="/api/v1/market/quote?api_key=SECRET",
            )
            service.finish_step_failed(
                execution_id,
                "fetch_quote",
                provider="fmp",
                error_type="TimeoutError",
                error_message="quote timeout token=SECRET",
                reason="timeout",
                metadata={
                    "freshness_state": "stale",
                    "fallback_used": True,
                    "cache_state": "stale",
                    "token": "SECRET",
                },
                endpoint="/api/v1/market/quote?api_key=SECRET",
            )
            service.start_step(
                execution_id,
                "ai_analysis",
                "AI 分析",
                category="ai_model",
                provider="openai",
                model="gpt-4o-mini",
            )
            service.finish_step_success(
                execution_id,
                "ai_analysis",
                provider="openai",
                model="gpt-4o-mini",
            )
            service.start_step(
                execution_id,
                "send_notification",
                "发送通知",
                category="notification",
                provider="email",
            )
            service.skip_step(
                execution_id,
                "send_notification",
                "发送通知",
                provider="email",
                reason="channel_not_configured",
                metadata={"category": "notification"},
            )
            service.finish_execution(execution_id, status="partial")
        return execution_id

    def test_builds_read_only_timeline_from_existing_logs_and_safe_hooks(self) -> None:
        execution_id = self._seed_degraded_analysis()
        before = self.db.get_execution_log_session_detail(execution_id)

        with patch("src.services.admin_incident_timeline_service.get_db", return_value=self.db):
            payload = AdminIncidentTimelineService().build_timeline(
                session_id=execution_id,
                request_id="req-aapl",
                symbol="AAPL",
                since="",
                limit=20,
            )

        after = self.db.get_execution_log_session_detail(execution_id)
        self.assertEqual(after, before)
        self.assertEqual(payload["lookup"]["session_id"], execution_id)
        self.assertEqual(payload["lookup"]["request_id"], "req-aapl")
        self.assertEqual(payload["lookup"]["symbol"], "AAPL")
        self.assertGreaterEqual(payload["total"], 4)
        kinds = {item["kind"] for item in payload["items"]}
        self.assertIn("business_event", kinds)
        self.assertIn("data_quality", kinds)
        self.assertIn("llm_cost", kinds)
        self.assertIn("notification", kinds)

        data_hook = next(hook for hook in payload["hooks"] if hook["kind"] == "data_quality")
        provider_hook = next(hook for hook in payload["hooks"] if hook["kind"] == "provider_cache_circuit")
        llm_hook = next(hook for hook in payload["hooks"] if hook["kind"] == "llm_cost")
        notification_hook = next(hook for hook in payload["hooks"] if hook["kind"] == "notification")
        evidence_hook = next(hook for hook in payload["hooks"] if hook["kind"] == "evidence_posture")
        self.assertEqual(data_hook["status"], "degraded")
        self.assertEqual(provider_hook["provider"], "fmp")
        self.assertEqual(llm_hook["model"], "gpt-4o-mini")
        self.assertEqual(notification_hook["channel"], "email")
        self.assertEqual(evidence_hook["status"], "placeholder")
        self.assertIn(execution_id, data_hook["sample_session_ids"])
        self.assertIn(execution_id, data_hook["sample_business_event_ids"])

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("SECRET", serialized)
        self.assertNotIn("api_key", serialized.lower())
        self.assertNotIn("raw_prompt", serialized.lower())

    def test_returns_empty_state_without_mutation_when_lookup_has_no_matches(self) -> None:
        with patch("src.services.admin_incident_timeline_service.get_db", return_value=self.db):
            payload = AdminIncidentTimelineService().build_timeline(
                session_id="missing-session",
                request_id="missing-request",
                query_id="missing-query",
                symbol="MSFT",
                since="",
            )

        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["empty_state"]["reason"], "no_matching_read_models")
        self.assertTrue(payload["empty_state"]["read_only"])


if __name__ == "__main__":
    unittest.main()
