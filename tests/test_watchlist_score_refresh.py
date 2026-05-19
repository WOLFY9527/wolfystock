# -*- coding: utf-8 -*-
"""Tests for lightweight user watchlist score refresh."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from src.config import Config
from src.storage import DatabaseManager, MarketScannerCandidate, MarketScannerRun, UserWatchlistItem
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
            run_id = run.id
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
            scanner_run_id=5,
            theme_id="crypto_miners",
            universe_type="theme",
        )
        self._save_scanner_candidate(symbol="WULF", market="us", score=72.5, rank=3)

        result = self.service.refresh_scores(owner_id="user-1", market="us")

        self.assertEqual(result["updated_count"], 1)
        self.assertEqual(result["results"][0]["status"], "fresh")
        item = self.service.list_items(owner_id="user-1")[0]
        self.assertIsNotNone(item["scanner_run_id"])
        self.assertEqual(item["scanner_score"], 72.5)
        self.assertEqual(item["scanner_rank"], 3)
        self.assertEqual(item["score_profile"], "us_preopen_v1")
        self.assertEqual(item["score_reason"], "Latest scanner score.")
        self.assertEqual(item["score_status"], "fresh")
        self.assertEqual(item["score_source"], "scanner_run")
        self.assertEqual(item["theme_id"], "crypto_miners")
        self.assertEqual(item["universe_type"], "theme")
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

    def test_refresh_is_owner_scoped_when_other_users_hold_same_symbol(self) -> None:
        self.db.create_or_update_app_user(
            user_id="user-2",
            username="bob",
            role="user",
            display_name="Bob",
        )
        self.service.add_item(owner_id="user-1", symbol="WULF", market="us", scanner_score=60, scanner_rank=8)
        self.service.add_item(owner_id="user-2", symbol="WULF", market="us", scanner_score=55, scanner_rank=9)
        self._save_scanner_candidate(symbol="WULF", market="us", score=72.5, rank=3)

        result = self.service.refresh_scores(owner_id="user-1", market="us")

        self.assertEqual(result["updated_count"], 1)
        user_one_item = self.service.list_items(owner_id="user-1")[0]
        user_two_item = self.service.list_items(owner_id="user-2")[0]
        self.assertEqual(user_one_item["scanner_score"], 72.5)
        self.assertEqual(user_one_item["scanner_rank"], 3)
        self.assertEqual(user_one_item["score_status"], "fresh")
        self.assertEqual(user_two_item["scanner_score"], 55.0)
        self.assertEqual(user_two_item["scanner_rank"], 9)
        self.assertIsNone(user_two_item["score_source"])
        self.assertIsNone(user_two_item["last_scored_at"])

    def test_refresh_legacy_rows_reuses_persisted_scores_without_provider_fanout(self) -> None:
        with self.db.get_session() as session:
            session.add(
                UserWatchlistItem(
                    owner_id="user-1",
                    symbol="600001",
                    market="cn",
                    source="scanner",
                    scanner_run_id=5,
                    scanner_rank=7,
                    scanner_score=61.0,
                    notes="legacy row",
                )
            )
            session.commit()

        now = datetime.now()
        run = MarketScannerRun(
            market="cn",
            profile="cn_preopen_v1",
            universe_name="cn_watchlist",
            status="completed",
            run_at=now - timedelta(minutes=5),
            completed_at=now - timedelta(minutes=4),
            shortlist_size=1,
            universe_size=1,
            preselected_size=1,
            evaluated_size=1,
        )
        candidate = MarketScannerCandidate(
            symbol="600001",
            name="平安银行",
            rank=2,
            score=78.4,
            reason_summary="Persisted scanner score only.",
            diagnostics_json=(
                '{"cn_provider_observation":{"observationOnly":true,"scoreContributionAllowed":false,'
                '"entries":[{"providerName":"akshare"},{"providerName":"pytdx"}]}}'
            ),
            created_at=now,
        )
        with self.db.get_session() as session:
            session.add(run)
            session.flush()
            run_id = int(run.id)
            candidate.run_id = run.id
            session.add(candidate)
            session.commit()

        with (
            patch("data_provider.base.DataFetcherManager.get_daily_data", side_effect=AssertionError("watchlist refresh should not fetch provider history")) as get_daily_data,
            patch("data_provider.base.DataFetcherManager.get_realtime_quote", side_effect=AssertionError("watchlist refresh should not fetch provider quotes")) as get_realtime_quote,
        ):
            result = self.service.refresh_scores(owner_id="user-1", market="cn")

        self.assertEqual(result["updated_count"], 1)
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(result["results"][0]["status"], "fresh")
        get_daily_data.assert_not_called()
        get_realtime_quote.assert_not_called()

        item = self.service.list_items(owner_id="user-1")[0]
        self.assertEqual(item["scanner_run_id"], run_id)
        self.assertEqual(item["scanner_score"], 78.4)
        self.assertEqual(item["scanner_rank"], 2)
        self.assertEqual(item["score_source"], "scanner_run")
        self.assertEqual(item["score_profile"], "cn_preopen_v1")
        self.assertEqual(item["score_reason"], "Persisted scanner score only.")
        self.assertEqual(item["score_status"], "fresh")
        self.assertNotIn("providerObservation", item)
        self.assertNotIn("providerObservation", item["intelligence"]["scanner"])

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
