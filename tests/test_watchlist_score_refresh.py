# -*- coding: utf-8 -*-
"""Tests for lightweight user watchlist score refresh."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from src.config import Config
from src.storage import DatabaseManager, MarketScannerCandidate, MarketScannerRun
from src.services.watchlist_service import WatchlistService


class WatchlistScoreRefreshTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.db_path = self.data_dir / "watchlist_refresh_test.db"
        os.environ["DATABASE_PATH"] = str(self.db_path)
        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        self.db.create_or_update_app_user(
            user_id="user-1",
            username="alice",
            role="user",
            display_name="Alice",
        )
        self.service = WatchlistService(db_manager=self.db)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def _save_scanner_candidate(self, *, symbol: str, market: str, score: float, rank: int) -> None:
        now = datetime.now()
        run = MarketScannerRun(
            market=market,
            profile=f"{market}_preopen_v1",
            universe_name=f"{market}_watchlist",
            status="completed",
            run_at=now - timedelta(minutes=5),
            completed_at=now - timedelta(minutes=4),
            shortlist_size=1,
            universe_size=1,
            preselected_size=1,
            evaluated_size=1,
        )
        candidate = MarketScannerCandidate(
            symbol=symbol,
            name=symbol,
            rank=rank,
            score=score,
            reason_summary="Latest scanner score.",
            created_at=now,
        )
        with self.db.get_session() as session:
            session.add(run)
            session.flush()
            candidate.run_id = run.id
            session.add(candidate)
            session.commit()

    def test_manual_refresh_updates_score_and_last_scored_at(self) -> None:
        self.service.add_item(
            owner_id="user-1",
            symbol="WULF",
            market="us",
            scanner_score=60,
            scanner_rank=8,
        )
        self._save_scanner_candidate(symbol="WULF", market="us", score=72.5, rank=3)

        result = self.service.refresh_scores(owner_id="user-1", market="us")

        self.assertEqual(result["updated_count"], 1)
        item = self.service.list_items(owner_id="user-1")[0]
        self.assertEqual(item["scanner_score"], 72.5)
        self.assertEqual(item["scanner_rank"], 3)
        self.assertEqual(item["score_status"], "fresh")
        self.assertEqual(item["score_source"], "scanner_run")
        self.assertTrue(item["last_scored_at"])

    def test_refresh_preserves_candidate_when_scanner_data_is_missing(self) -> None:
        self.service.add_item(
            owner_id="user-1",
            symbol="MARA",
            market="us",
            scanner_score=61,
            scanner_rank=7,
        )

        result = self.service.refresh_scores(owner_id="user-1", market="us")

        self.assertEqual(result["updated_count"], 0)
        self.assertEqual(result["skipped_count"], 1)
        item = self.service.list_items(owner_id="user-1")[0]
        self.assertEqual(item["scanner_score"], 61.0)
        self.assertEqual(item["scanner_rank"], 7)
        self.assertEqual(item["score_status"], "stale")
        self.assertIn("No scanner candidate", item["score_error"])

    def test_refresh_groups_candidates_by_market(self) -> None:
        self.service.add_item(owner_id="user-1", symbol="WULF", market="us", scanner_score=60)
        self.service.add_item(owner_id="user-1", symbol="00700", market="hk", scanner_score=70)
        self._save_scanner_candidate(symbol="WULF", market="us", score=73, rank=2)
        self._save_scanner_candidate(symbol="00700", market="hk", score=81, rank=1)

        result = self.service.refresh_scores(owner_id="user-1")

        self.assertEqual(result["updated_count"], 2)
        self.assertEqual(sorted(result["markets"]), ["hk", "us"])

    def test_refresh_does_not_overlap_existing_refresh(self) -> None:
        locked = WatchlistService._refresh_lock.acquire(blocking=False)
        self.assertTrue(locked)
        try:
            WatchlistService._refresh_running = True
            result = self.service.refresh_scores(owner_id="user-1", market="us")
        finally:
            WatchlistService._refresh_running = False
            WatchlistService._refresh_lock.release()

        self.assertFalse(result["ok"])
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(result["results"][0]["status"], "running")


if __name__ == "__main__":
    unittest.main()
