# -*- coding: utf-8 -*-
"""Admin activity projection service redaction tests."""

from __future__ import annotations

import json
import unittest
from datetime import datetime
from unittest.mock import patch

from api.v1.schemas.admin_activity import AdminActivityEvent
from src.services.admin_activity_service import AdminActivityService, hash_reference
from src.storage import AnalysisHistory, DatabaseManager
from src.services.execution_log_service import ExecutionLogService


class AdminActivityServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.db = DatabaseManager(db_url="sqlite:///:memory:")
        self.db.create_or_update_app_user(
            user_id="user-1",
            username="alice",
            display_name="Alice",
            role="user",
            password_hash="pbkdf2:secret-hash",
            is_active=True,
        )

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()

    def test_analysis_projection_omits_raw_sensitive_fields(self) -> None:
        with self.db.get_session() as session:
            session.add(
                AnalysisHistory(
                    owner_id="user-1",
                    query_id="raw-query-secret",
                    code="AAPL",
                    name="Apple",
                    report_type="standard",
                    analysis_summary="Safe summary token=raw-token",
                    raw_result="RAW_RESULT_SHOULD_NOT_LEAK",
                    news_content="NEWS_CONTENT_SHOULD_NOT_LEAK",
                    context_snapshot="CONTEXT_SNAPSHOT_SHOULD_NOT_LEAK",
                    created_at=datetime.now(),
                )
            )
            session.commit()

        items, total = AdminActivityService(db_manager=self.db).list_activity(target_user_id="user-1")

        self.assertEqual(total, 1)
        self.assertIsInstance(items[0], dict)
        self.assertEqual(items[0]["target_user"]["id"], "user-1")
        validated = [AdminActivityEvent.model_validate(item) for item in items]
        text = json.dumps([item.to_dict() for item in validated], ensure_ascii=False)
        self.assertIn("AAPL", text)
        self.assertNotIn("raw-query-secret", text)
        self.assertNotIn("raw-token", text)
        self.assertNotIn("RAW_RESULT_SHOULD_NOT_LEAK", text)
        self.assertNotIn("NEWS_CONTENT_SHOULD_NOT_LEAK", text)
        self.assertNotIn("CONTEXT_SNAPSHOT_SHOULD_NOT_LEAK", text)

        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            execution_logs = ExecutionLogService()
            for run_id, evaluated, data_failed in ((201, 5, 0), (202, 0, 3)):
                execution_logs.record_scanner_run(
                    run_detail={
                        "id": run_id,
                        "market": "us",
                        "profile": "us_preopen_v1",
                        "profile_label": "Scanner",
                        "status": "completed",
                        "run_at": datetime.now().isoformat(),
                        "completed_at": datetime.now().isoformat(),
                        "universe_size": max(evaluated, data_failed, 3),
                        "evaluated_size": evaluated,
                        "shortlist_size": 0,
                        "summary": {"data_failed_count": data_failed},
                        "diagnostics": {},
                    },
                    actor={"user_id": "user-1", "actor_type": "user"},
                )

        items, total = AdminActivityService(db_manager=self.db, execution_log_service=execution_logs).list_activity(
            target_user_id="user-1",
            family="scanner",
        )
        self.assertEqual(total, 2)
        self.assertEqual({item["status"] for item in items}, {"empty", "data_failed"})
        for item in items:
            self.assertEqual(AdminActivityEvent.model_validate(item).outcome, "warning")

        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            execution_logs.record_scanner_run(
                run_detail={
                    "id": 203,
                    "market": "us",
                    "profile": "us_preopen_v1",
                    "profile_label": "Cancelled scanner",
                    "status": "cancelled",
                    "run_at": datetime.now().isoformat(),
                    "completed_at": datetime.now().isoformat(),
                    "universe_size": 3,
                    "evaluated_size": 0,
                    "shortlist_size": 0,
                },
                actor={"user_id": "user-1", "actor_type": "user"},
            )
            execution_logs.record_scanner_run(
                run_detail={
                    "id": 204,
                    "market": "us",
                    "profile": "us_preopen_v1",
                    "profile_label": "Unavailable scanner",
                    "status": "unavailable",
                    "run_at": datetime.now().isoformat(),
                    "completed_at": datetime.now().isoformat(),
                    "universe_size": 3,
                    "evaluated_size": 0,
                    "shortlist_size": 0,
                },
                actor={"user_id": "user-1", "actor_type": "user"},
            )
            execution_logs.record_scanner_run(
                run_detail={
                    "id": 205,
                    "market": "us",
                    "profile": "us_preopen_v1",
                    "profile_label": "Skipped scanner",
                    "status": "skipped",
                    "run_at": datetime.now().isoformat(),
                    "completed_at": datetime.now().isoformat(),
                    "universe_size": 0,
                    "evaluated_size": 0,
                    "shortlist_size": 0,
                },
                actor={"user_id": "user-1", "actor_type": "user"},
            )

        items, total = AdminActivityService(db_manager=self.db, execution_log_service=execution_logs).list_activity(
            target_user_id="user-1",
            family="scanner",
        )
        self.assertEqual(total, 5)
        terminal = {item["entity"]["label"]: item for item in items if item["status"] in {"cancelled", "unavailable", "skipped"}}
        self.assertEqual({item["status"] for item in terminal.values()}, {"cancelled", "unavailable", "skipped"})
        self.assertTrue(all(item["outcome"] == "warning" for item in terminal.values()))

    def test_request_correlation_is_hash_projected_for_admin_activity(self) -> None:
        raw_request_id = "b" * 32
        with patch("src.services.execution_log_service.get_db", return_value=self.db):
            execution_logs = ExecutionLogService()
            execution_logs.record_user_write_action(
                event_type="portfolio.account_created",
                message="Portfolio account created",
                actor={
                    "user_id": "user-1",
                    "actor_type": "user",
                    "role": "user",
                    "request_id": raw_request_id,
                },
                domain="portfolio",
                target_type="portfolio_account",
                target_id=7,
            )

        items, total = AdminActivityService(
            db_manager=self.db,
            execution_log_service=execution_logs,
        ).list_activity(target_user_id="user-1", family="user_action")

        self.assertEqual(total, 1)
        self.assertEqual(items[0]["request_id_hash"], hash_reference(raw_request_id))
        self.assertEqual(items[0]["actor"]["request_id_hash"], hash_reference(raw_request_id))
        self.assertNotIn(raw_request_id, json.dumps(items[0], ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
