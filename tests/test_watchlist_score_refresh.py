# -*- coding: utf-8 -*-
"""Tests for lightweight user watchlist score refresh."""

from __future__ import annotations

import os
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import event

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

    def _save_scanner_candidate(
        self,
        *,
        symbol: str,
        market: str,
        score: float,
        rank: int,
        diagnostics_source: str | None = None,
        diagnostics_payload: dict | None = None,
        run_at: datetime | None = None,
        completed_at: datetime | None = None,
        status: str = "completed",
        reason_summary: str = "Latest scanner score.",
    ) -> None:
        now = datetime.now()
        run = MarketScannerRun(
            market=market,
            profile=f"{market}_preopen_v1",
            universe_name=f"{market}_watchlist",
            status=status,
            run_at=run_at or now - timedelta(minutes=5),
            completed_at=completed_at or now - timedelta(minutes=4),
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
            reason_summary=reason_summary,
            diagnostics_json=(
                json.dumps(diagnostics_payload, ensure_ascii=False)
                if diagnostics_payload is not None
                else json.dumps(
                    {
                        "history": {
                            "source": diagnostics_source,
                            "latest_trade_date": "2026-05-22",
                        }
                    },
                    ensure_ascii=False,
                )
                if diagnostics_source
                else None
            ),
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
        self.assertEqual(
            item["score_status_context"],
            {
                "scope": "score_refresh_recency",
                "fresh_means": "persisted_scanner_score_refreshed",
                "source_freshness_implied": False,
                "source_authority_implied": False,
            },
        )
        self.assertEqual(item["score_source"], "scanner_run")
        self.assertEqual(item["theme_id"], "crypto_miners")
        self.assertEqual(item["universe_type"], "theme")
        self.assertTrue(item["last_scored_at"])

    def test_refresh_attaches_post_add_scanner_lineage_without_provider_fanout(self) -> None:
        added_at = datetime(2026, 5, 1, 9, 0, 0)
        with self.db.get_session() as session:
            session.add(
                UserWatchlistItem(
                    owner_id="user-1",
                    symbol="WULF",
                    market="us",
                    source="scanner",
                    scanner_run_id=5,
                    scanner_rank=8,
                    scanner_score=60,
                    theme_id="crypto_miners",
                    universe_type="theme",
                    created_at=added_at,
                    updated_at=added_at,
                )
            )
            session.commit()

        now = datetime(2026, 5, 4, 10, 0, 0)
        run = MarketScannerRun(
            market="us",
            profile="us_preopen_v1",
            universe_name="us_watchlist",
            status="completed",
            run_at=now - timedelta(minutes=5),
            completed_at=now,
            shortlist_size=1,
            universe_size=1,
            preselected_size=1,
            evaluated_size=1,
        )
        candidate = MarketScannerCandidate(
            symbol="WULF",
            name="WULF",
            rank=3,
            score=72.5,
            reason_summary="Latest scanner score.",
            diagnostics_json=json.dumps(
                {
                    "candidateResearchSummaryFrame": {
                        "primaryResearchReason": "评分刷新后继续观察。",
                        "researchNextStep": "补充证据后继续观察。",
                    },
                    "score_explainability": {
                        "score_grade_allowed": False,
                        "source_confidence": {
                            "source": "yfinance_proxy",
                            "sourceType": "proxy",
                            "freshness": "fallback",
                            "isFallback": True,
                            "isStale": True,
                            "isPartial": True,
                            "scoreContributionAllowed": False,
                            "sourceAuthorityAllowed": False,
                            "observationOnly": True,
                        },
                    },
                    "providerObservation": {
                        "entries": [{"providerName": "internal-provider"}],
                    },
                },
                ensure_ascii=False,
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
            patch("data_provider.base.DataFetcherManager.get_daily_data", side_effect=AssertionError("watchlist lineage should not fetch provider history")) as get_daily_data,
            patch("data_provider.base.DataFetcherManager.get_realtime_quote", side_effect=AssertionError("watchlist lineage should not fetch provider quotes")) as get_realtime_quote,
        ):
            result = self.service.refresh_scores(owner_id="user-1", market="us")

        self.assertEqual(result["updated_count"], 1)
        get_daily_data.assert_not_called()
        get_realtime_quote.assert_not_called()

        item = self.service.list_items(owner_id="user-1")[0]
        lineage = item["intelligence"]["scanner"]["scanner_lineage_v1"]
        self.assertEqual(lineage["scanner_run_id"], run_id)
        self.assertEqual(lineage["score_snapshot_kind"], "post_add_refresh")
        self.assertEqual(lineage["run_profile"], "us_preopen_v1")
        self.assertEqual(lineage["rank_at_scan"], 3)
        self.assertEqual(lineage["score_at_scan"], 72.5)
        self.assertEqual(lineage["research_reason"], "评分刷新后继续观察。")
        self.assertEqual(lineage["research_next_step"], "补充证据后继续观察。")
        self.assertEqual(lineage["data_state"], "observation_only")
        self.assertFalse(lineage["score_grade_allowed"])
        serialized_lineage = json.dumps(lineage, ensure_ascii=False)
        self.assertNotIn("providerObservation", serialized_lineage)
        self.assertNotIn("internal-provider", serialized_lineage)
        self.assertNotIn("sourceAuthorityAllowed", serialized_lineage)
        self.assertNotIn("scoreContributionAllowed", serialized_lineage)

    def test_refresh_projects_local_us_parquet_dir_provenance_without_runtime_fetches(self) -> None:
        self.service.add_item(
            owner_id="user-1",
            symbol="WULF",
            market="us",
            scanner_score=60,
            scanner_rank=8,
        )
        self._save_scanner_candidate(
            symbol="WULF",
            market="us",
            score=72.5,
            rank=3,
            diagnostics_source="local_us_parquet_dir",
        )

        with (
            patch("data_provider.base.DataFetcherManager.get_daily_data", side_effect=AssertionError("watchlist provenance should not fetch provider history")) as get_daily_data,
            patch("data_provider.base.DataFetcherManager.get_realtime_quote", side_effect=AssertionError("watchlist provenance should not fetch provider quotes")) as get_realtime_quote,
            patch("src.services.us_history_helper.fetch_daily_history_with_local_us_fallback", side_effect=AssertionError("watchlist provenance should not fetch local/cache history")) as fetch_local_history,
            patch("src.services.backtest_service.BacktestService.run_backtest", side_effect=AssertionError("watchlist provenance should not run backtests")) as run_backtest,
        ):
            result = self.service.refresh_scores(owner_id="user-1", market="us")
            item = self.service.list_items(owner_id="user-1")[0]

        self.assertEqual(result["updated_count"], 1)
        self.assertEqual(item["score_source"], "scanner_run")
        provenance = item["intelligence"]["scanner"]["ohlcv_provenance"]
        self.assertEqual(provenance["source"], "local_us_parquet_dir")
        self.assertEqual(provenance["source_type"], "cache_snapshot")
        self.assertEqual(provenance["source_label"], "本地 Parquet 历史")
        get_daily_data.assert_not_called()
        get_realtime_quote.assert_not_called()
        fetch_local_history.assert_not_called()
        run_backtest.assert_not_called()

    def test_refresh_missing_diagnostics_preserves_scanner_run_without_provenance(self) -> None:
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
        self.assertEqual(item["score_source"], "scanner_run")
        self.assertEqual(item["scanner_score"], 72.5)
        self.assertEqual(item["scanner_rank"], 3)
        self.assertNotIn("ohlcv_provenance", item["intelligence"]["scanner"])
        self.assertNotIn("investor_signal", item["intelligence"]["scanner"])
        self.assertIsNone(item["intelligence"]["scanner"].get("score_confidence"))
        self.assertIsNone(item["intelligence"]["scanner"].get("cap_reason"))
        self.assertIsNone(item["intelligence"]["scanner"].get("degradation_reason"))
        self.assertIsNone(item["intelligence"]["scanner"].get("score_grade_allowed"))
        self.assertIsNone(item["intelligence"]["scanner"].get("source_confidence"))
        self.assertIsNone(item["intelligence"]["scanner"].get("reason_families"))

    def test_refresh_projects_scanner_score_explainability_disclosure_metadata(self) -> None:
        self.service.add_item(
            owner_id="user-1",
            symbol="WULF",
            market="us",
            scanner_score=60,
            scanner_rank=8,
        )
        self._save_scanner_candidate(
            symbol="WULF",
            market="us",
            score=72.5,
            rank=3,
            diagnostics_payload={
                "history": {
                    "source": "yfinance_proxy",
                    "latest_trade_date": "2026-05-22",
                    "stale": True,
                },
                "score_explainability": {
                    "score_confidence": 0.4,
                    "cap_reason": "public_proxy_not_score_grade",
                    "degradation_reason": "fallback_source",
                    "score_grade_allowed": False,
                    "source_confidence": {
                        "source": "yfinance_proxy",
                        "sourceLabel": "Yahoo Finance Proxy",
                        "sourceType": "proxy",
                        "freshness": "fallback",
                        "isFallback": True,
                        "isStale": True,
                        "isPartial": True,
                        "isSynthetic": False,
                        "isUnavailable": False,
                        "confidenceWeight": 0.4,
                        "coverage": 0.58,
                        "degradationReason": "fallback_source",
                        "capReason": "public_proxy_not_score_grade",
                        "scoreContributionAllowed": False,
                        "sourceAuthorityAllowed": False,
                        "observationOnly": True,
                    },
                },
            },
        )

        result = self.service.refresh_scores(owner_id="user-1", market="us")

        self.assertEqual(result["updated_count"], 1)
        item = self.service.list_items(owner_id="user-1")[0]
        self.assertEqual(item["score_status"], "fresh")
        self.assertEqual(item["score_status_context"]["scope"], "score_refresh_recency")
        self.assertFalse(item["score_status_context"]["source_freshness_implied"])
        self.assertFalse(item["score_status_context"]["source_authority_implied"])
        disclosure = item["intelligence"]["scanner"]
        self.assertEqual(disclosure["score_confidence"], 0.4)
        self.assertEqual(disclosure["cap_reason"], "public_proxy_not_score_grade")
        self.assertEqual(disclosure["degradation_reason"], "fallback_source")
        self.assertFalse(disclosure["score_grade_allowed"])
        self.assertEqual(
            disclosure["reason_families"]["cap_reason"],
            {
                "raw_code": "public_proxy_not_score_grade",
                "family": "source_confidence_cap",
                "scope": "scanner_evidence_packet",
            },
        )
        self.assertEqual(
            disclosure["reason_families"]["degradation_reason"],
            {
                "raw_code": "fallback_source",
                "family": "fallback",
                "scope": "source_confidence",
            },
        )
        self.assertEqual(
            disclosure["reason_families"]["source_confidence"]["cap_reason"],
            {
                "raw_code": "public_proxy_not_score_grade",
                "family": "source_confidence_cap",
                "scope": "scanner_evidence_packet",
            },
        )
        self.assertEqual(
            disclosure["reason_families"]["source_confidence"]["degradation_reason"],
            {
                "raw_code": "fallback_source",
                "family": "fallback",
                "scope": "source_confidence",
            },
        )
        self.assertEqual(disclosure["source_confidence"]["source"], "yfinance_proxy")
        self.assertEqual(disclosure["source_confidence"]["source_type"], "proxy")
        self.assertEqual(disclosure["source_confidence"]["freshness"], "fallback")
        self.assertTrue(disclosure["source_confidence"]["is_fallback"])
        self.assertTrue(disclosure["source_confidence"]["is_stale"])
        self.assertTrue(disclosure["source_confidence"]["is_partial"])
        self.assertFalse(disclosure["source_confidence"]["score_contribution_allowed"])
        self.assertFalse(disclosure["source_confidence"]["source_authority_allowed"])
        self.assertTrue(disclosure["source_confidence"]["observation_only"])
        investor_signal = disclosure["investor_signal"]
        self.assertEqual(investor_signal["contractVersion"], "investor_signal_contract_v1")
        self.assertFalse(investor_signal["sourceAuthorityAllowed"])
        self.assertEqual(investor_signal["freshness"], "fallback")
        self.assertEqual(investor_signal["confidenceLabel"], "blocked")
        self.assertIn("fallback_source", investor_signal["reasonCodes"])
        self.assertIn("source_authority_missing", investor_signal["reasonCodes"])

    def test_refresh_projects_local_cache_score_disclosure_without_provider_calls(self) -> None:
        self.service.add_item(
            owner_id="user-1",
            symbol="WULF",
            market="us",
            scanner_score=60,
            scanner_rank=8,
        )
        self._save_scanner_candidate(
            symbol="WULF",
            market="us",
            score=72.5,
            rank=3,
            diagnostics_payload={
                "history": {
                    "source": "local_us_parquet_dir",
                    "latest_trade_date": "2026-05-22",
                },
                "score_explainability": {
                    "score_confidence": 0.35,
                    "cap_reason": "configured_cache_only_diagnostic",
                    "degradation_reason": "configured_cache_only_diagnostic",
                    "score_grade_allowed": False,
                    "source_confidence": {
                        "source": "local_us_parquet_dir",
                        "sourceLabel": "本地 Parquet 历史",
                        "sourceType": "cache_snapshot",
                        "freshness": "cached",
                        "isFallback": False,
                        "isStale": False,
                        "isPartial": False,
                        "isSynthetic": False,
                        "isUnavailable": False,
                        "confidenceWeight": 0.35,
                        "coverage": 1.0,
                        "degradationReason": "configured_cache_only_diagnostic",
                        "capReason": "configured_cache_only_diagnostic",
                        "scoreContributionAllowed": False,
                        "sourceAuthorityAllowed": False,
                        "observationOnly": True,
                    },
                },
            },
        )

        with (
            patch("data_provider.base.DataFetcherManager.get_daily_data", side_effect=AssertionError("watchlist disclosure should not fetch provider history")) as get_daily_data,
            patch("data_provider.base.DataFetcherManager.get_realtime_quote", side_effect=AssertionError("watchlist disclosure should not fetch provider quotes")) as get_realtime_quote,
        ):
            result = self.service.refresh_scores(owner_id="user-1", market="us")
            item = self.service.list_items(owner_id="user-1")[0]

        self.assertEqual(result["updated_count"], 1)
        disclosure = item["intelligence"]["scanner"]
        self.assertEqual(disclosure["score_confidence"], 0.35)
        self.assertFalse(disclosure["score_grade_allowed"])
        self.assertEqual(
            disclosure["reason_families"]["cap_reason"],
            {
                "raw_code": "configured_cache_only_diagnostic",
                "family": "unclassified",
                "scope": None,
            },
        )
        self.assertEqual(
            disclosure["reason_families"]["degradation_reason"],
            {
                "raw_code": "configured_cache_only_diagnostic",
                "family": "unclassified",
                "scope": None,
            },
        )
        self.assertEqual(disclosure["source_confidence"]["source"], "local_us_parquet_dir")
        self.assertEqual(disclosure["source_confidence"]["source_type"], "cache_snapshot")
        self.assertEqual(disclosure["source_confidence"]["freshness"], "cached")
        self.assertTrue(disclosure["source_confidence"]["observation_only"])
        self.assertFalse(disclosure["source_confidence"]["score_contribution_allowed"])
        get_daily_data.assert_not_called()
        get_realtime_quote.assert_not_called()

    def test_refresh_projects_unknown_reason_family_sidecar_without_provider_calls(self) -> None:
        self.service.add_item(
            owner_id="user-1",
            symbol="WULF",
            market="us",
            scanner_score=60,
            scanner_rank=8,
        )
        self._save_scanner_candidate(
            symbol="WULF",
            market="us",
            score=72.5,
            rank=3,
            diagnostics_payload={
                "score_explainability": {
                    "score_confidence": 0.61,
                    "cap_reason": "mystery_reason_code",
                    "degradation_reason": "fallback_source",
                    "score_grade_allowed": False,
                },
            },
        )

        with (
            patch("data_provider.base.DataFetcherManager.get_daily_data", side_effect=AssertionError("watchlist reason families should not fetch provider history")) as get_daily_data,
            patch("data_provider.base.DataFetcherManager.get_realtime_quote", side_effect=AssertionError("watchlist reason families should not fetch provider quotes")) as get_realtime_quote,
        ):
            result = self.service.refresh_scores(owner_id="user-1", market="us")
            item = self.service.list_items(owner_id="user-1")[0]

        self.assertEqual(result["updated_count"], 1)
        self.assertEqual(item["scanner_score"], 72.5)
        disclosure = item["intelligence"]["scanner"]
        self.assertEqual(disclosure["cap_reason"], "mystery_reason_code")
        self.assertEqual(disclosure["degradation_reason"], "fallback_source")
        self.assertEqual(
            disclosure["reason_families"]["cap_reason"],
            {
                "raw_code": "mystery_reason_code",
                "family": "unclassified",
                "scope": None,
            },
        )
        self.assertEqual(
            disclosure["reason_families"]["degradation_reason"],
            {
                "raw_code": "fallback_source",
                "family": "fallback",
                "scope": "source_confidence",
            },
        )
        get_daily_data.assert_not_called()
        get_realtime_quote.assert_not_called()

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
        self.assertEqual(item["score_status_context"]["scope"], "score_refresh_recency")
        self.assertFalse(item["score_status_context"]["source_freshness_implied"])
        self.assertFalse(item["score_status_context"]["source_authority_implied"])
        self.assertIn("No scanner candidate", item["score_error"])

    def test_refresh_groups_candidates_by_market(self) -> None:
        self.service.add_item(owner_id="user-1", symbol="WULF", market="us", scanner_score=60)
        self.service.add_item(owner_id="user-1", symbol="00700", market="hk", scanner_score=70)
        self._save_scanner_candidate(symbol="WULF", market="us", score=73, rank=2)
        self._save_scanner_candidate(symbol="00700", market="hk", score=81, rank=1)

        result = self.service.refresh_scores(owner_id="user-1")

        self.assertEqual(result["updated_count"], 2)
        self.assertEqual(sorted(result["markets"]), ["hk", "us"])

    def test_refresh_uses_bounded_bulk_lookup_for_large_watchlist(self) -> None:
        self.db.create_or_update_app_user(
            user_id="user-2",
            username="bob",
            role="user",
            display_name="Bob",
        )
        expected_scores: dict[tuple[str, str], float] = {}
        stale_keys: set[tuple[str, str]] = set()

        for index in range(24):
            market = "us" if index % 2 == 0 else "hk"
            symbol = f"B{index:04d}"
            self.service.add_item(
                owner_id="user-1",
                symbol=symbol,
                market=market,
                scanner_score=10 + index,
                scanner_rank=90 + index,
            )
            key = (market, symbol)
            if index < 18:
                score = 70.0 + index
                expected_scores[key] = score
                self._save_scanner_candidate(symbol=symbol, market=market, score=score, rank=index + 1)
            else:
                stale_keys.add(key)

        self.service.add_item(owner_id="user-1", symbol="DUAL", market="us", scanner_score=10, scanner_rank=90)
        self.service.add_item(owner_id="user-1", symbol="DUAL", market="hk", scanner_score=20, scanner_rank=91)
        self.service.add_item(owner_id="user-2", symbol="B0000", market="us", scanner_score=5, scanner_rank=88)

        baseline_time = datetime(2026, 5, 12, 9, 0, 0)
        self._save_scanner_candidate(
            symbol="DUAL",
            market="us",
            score=55.0,
            rank=8,
            run_at=baseline_time,
            completed_at=baseline_time,
            reason_summary="Older US scanner score.",
        )
        self._save_scanner_candidate(
            symbol="DUAL",
            market="us",
            score=91.0,
            rank=1,
            run_at=baseline_time + timedelta(minutes=10),
            completed_at=baseline_time + timedelta(minutes=10),
            reason_summary="Latest US scanner score.",
        )
        self._save_scanner_candidate(
            symbol="DUAL",
            market="us",
            score=99.0,
            rank=1,
            run_at=baseline_time + timedelta(minutes=20),
            completed_at=baseline_time + timedelta(minutes=20),
            status="running",
            reason_summary="Running scanner score should be ignored.",
        )
        self._save_scanner_candidate(
            symbol="DUAL",
            market="hk",
            score=82.0,
            rank=2,
            run_at=baseline_time + timedelta(minutes=5),
            completed_at=baseline_time + timedelta(minutes=5),
            reason_summary="Latest HK scanner score.",
        )
        expected_scores[("us", "DUAL")] = 91.0
        expected_scores[("hk", "DUAL")] = 82.0

        scanner_join_queries: list[str] = []

        def count_scanner_join(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
            normalized = " ".join(str(statement).lower().split())
            if "from market_scanner_candidates" in normalized and "join market_scanner_runs" in normalized:
                scanner_join_queries.append(str(statement))

        event.listen(self.db._engine, "before_cursor_execute", count_scanner_join)
        try:
            result = self.service.refresh_scores(owner_id="user-1")
        finally:
            event.remove(self.db._engine, "before_cursor_execute", count_scanner_join)

        self.assertEqual(result["updated_count"], len(expected_scores))
        self.assertEqual(result["skipped_count"], len(stale_keys))
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(len(scanner_join_queries), 1)

        user_one_items = {
            (item["market"], item["symbol"]): item
            for item in self.service.list_items(owner_id="user-1")
        }
        for key, expected_score in expected_scores.items():
            self.assertEqual(user_one_items[key]["score_status"], "fresh")
            self.assertEqual(user_one_items[key]["scanner_score"], expected_score)
        for key in stale_keys:
            self.assertEqual(user_one_items[key]["score_status"], "stale")
            self.assertIn("No scanner candidate", user_one_items[key]["score_error"])

        self.assertEqual(user_one_items[("us", "DUAL")]["score_reason"], "Latest US scanner score.")
        self.assertEqual(user_one_items[("hk", "DUAL")]["score_reason"], "Latest HK scanner score.")
        user_two_item = self.service.list_items(owner_id="user-2")[0]
        self.assertEqual(user_two_item["scanner_score"], 5.0)
        self.assertEqual(user_two_item["scanner_rank"], 88)
        self.assertIsNone(user_two_item["score_source"])
        self.assertIsNone(user_two_item["last_scored_at"])

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
