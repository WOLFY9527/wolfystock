# -*- coding: utf-8 -*-
"""Admin activity projection service redaction tests."""

from __future__ import annotations

import json
import unittest
from datetime import datetime

from src.storage import AnalysisHistory, DatabaseManager


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

        from src.services.admin_activity_service import AdminActivityService

        items, total = AdminActivityService(db_manager=self.db).list_activity(target_user_id="user-1")

        self.assertEqual(total, 1)
        text = json.dumps([item.to_dict() for item in items], ensure_ascii=False)
        self.assertIn("AAPL", text)
        self.assertNotIn("raw-query-secret", text)
        self.assertNotIn("raw-token", text)
        self.assertNotIn("RAW_RESULT_SHOULD_NOT_LEAK", text)
        self.assertNotIn("NEWS_CONTENT_SHOULD_NOT_LEAK", text)
        self.assertNotIn("CONTEXT_SNAPSHOT_SHOULD_NOT_LEAK", text)


if __name__ == "__main__":
    unittest.main()
