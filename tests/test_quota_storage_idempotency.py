# -*- coding: utf-8 -*-
"""Storage-level quota idempotency foundation tests."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.storage import DatabaseManager, QuotaUsageWindow


def _fresh_db() -> DatabaseManager:
    DatabaseManager.reset_instance()
    return DatabaseManager(db_url="sqlite:///:memory:")


class QuotaStorageIdempotencyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _fresh_db()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()

    def test_null_equivalent_quota_window_identity_is_unique(self) -> None:
        window_start = datetime(2026, 6, 10)
        window_end = window_start + timedelta(days=1)
        identity = DatabaseManager.quota_window_identity_values(
            owner_user_id=None,
            route_family="analysis",
            provider=None,
            model_tier=None,
        )

        with self.assertRaises(IntegrityError):
            with self.db.session_scope() as session:
                session.add(
                    QuotaUsageWindow(
                        owner_user_id=None,
                        route_family="analysis",
                        provider=None,
                        model_tier=None,
                        window_type="daily",
                        window_start=window_start,
                        window_end=window_end,
                        **identity,
                    )
                )
                session.flush()
                session.add(
                    QuotaUsageWindow(
                        owner_user_id="",
                        route_family="analysis",
                        provider="",
                        model_tier="",
                        window_type="daily",
                        window_start=window_start,
                        window_end=window_end,
                        **identity,
                    )
                )
                session.flush()


if __name__ == "__main__":
    unittest.main()
