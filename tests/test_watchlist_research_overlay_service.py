# -*- coding: utf-8 -*-
"""Tests for the read-only watchlist research overlay projection."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sqlalchemy import event

from src.config import Config
from src.services.watchlist_research_overlay_service import WatchlistResearchOverlayService
from src.services.watchlist_service import WatchlistService
from src.storage import (
    DatabaseManager,
    MarketScannerCandidate,
    MarketScannerRun,
    UserAlertEvent,
    UserAlertRule,
)


FORBIDDEN_OVERLAY_TEXT = (
    "buy",
    "sell",
    "hold",
    "recommendation",
    "target",
    "stop",
    "position sizing",
    "买入",
    "卖出",
    "持有",
    "目标价",
    "止损",
    "仓位",
)


class WatchlistResearchOverlayServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.db_path = self.data_dir / "watchlist_overlay_test.db"
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
        self.watchlist_service = WatchlistService(db_manager=self.db)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def _save_scanner_candidate(
        self,
        *,
        symbol: str,
        market: str = "us",
        theme: str = "ai_infra",
        diagnostics: dict | None = None,
    ) -> int:
        now = datetime(2026, 5, 4, 9, 30, 0)
        run = MarketScannerRun(
            market=market,
            profile=f"{market}_preopen_v1",
            universe_name=f"{market}_preopen_watchlist_v1",
            status="completed",
            run_at=now,
            completed_at=now,
            shortlist_size=1,
        )
        candidate = MarketScannerCandidate(
            symbol=symbol,
            name=symbol,
            rank=2,
            score=71.5,
            reason_summary="Structure and evidence changed; verify the stored research frame.",
            diagnostics_json=json.dumps(
                diagnostics
                or {
                    "history": {
                        "source": "local_us_parquet_dir",
                        "latest_trade_date": "2026-05-03",
                    },
                    "candidateResearchSummaryFrame": {
                        "primaryResearchReason": "Volume structure improved while evidence remains incomplete.",
                        "researchNextStep": "Verify local OHLCV coverage and latest catalyst evidence.",
                    },
                    "score_explainability": {
                        "score_confidence": 0.35,
                        "score_grade_allowed": False,
                        "cap_reason": "configured_cache_only_diagnostic",
                        "source_confidence": {
                            "source": "local_us_parquet_dir",
                            "sourceType": "cache_snapshot",
                            "freshness": "cached",
                            "coverage": 1.0,
                            "scoreContributionAllowed": False,
                            "sourceAuthorityAllowed": False,
                            "observationOnly": True,
                        },
                    },
                },
                ensure_ascii=False,
            ),
            boards_json=json.dumps([theme], ensure_ascii=False),
            created_at=now,
        )
        with self.db.get_session() as session:
            session.add(run)
            session.flush()
            candidate.run_id = run.id
            session.add(candidate)
            session.commit()
            return int(run.id)

    def _count_alert_rows(self) -> tuple[int, int]:
        with self.db.get_session() as session:
            rule_count = session.query(UserAlertRule).count()
            event_count = session.query(UserAlertEvent).count()
        return int(rule_count), int(event_count)

    def test_overlay_projects_research_attention_without_mutating_or_alerting(self) -> None:
        run_id = self._save_scanner_candidate(symbol="NVDA")
        self.watchlist_service.add_item(
            owner_id="user-1",
            symbol="NVDA",
            market="us",
            scanner_run_id=run_id,
            scanner_rank=2,
            scanner_score=71.5,
            theme_id="ai_infra",
            notes="Track structural change and missing evidence.",
        )
        self.watchlist_service.add_item(owner_id="user-1", symbol="MSFT", market="us")

        mutation_statements: list[str] = []

        def guard_mutation(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
            verb = statement.lstrip().split(None, 1)[0].upper() if statement.strip() else ""
            if verb in {"INSERT", "UPDATE", "DELETE", "REPLACE", "ALTER", "DROP", "CREATE"}:
                mutation_statements.append(statement)

        event.listen(self.db._engine, "before_cursor_execute", guard_mutation)
        try:
            payload = WatchlistResearchOverlayService(
                watchlist_service=self.watchlist_service
            ).build_overlay(owner_id="user-1")
        finally:
            event.remove(self.db._engine, "before_cursor_execute", guard_mutation)

        self.assertEqual(mutation_statements, [])
        self.assertEqual(self._count_alert_rows(), (0, 0))
        self.assertEqual(payload["schemaVersion"], "watchlist_research_overlay_v1")
        self.assertEqual(len(payload["items"]), 2)
        self.assertTrue(payload["noAdviceDisclosure"])
        self.assertEqual(payload["aggregateSummary"]["byThemeOrSector"]["ai_infra"], 1)
        self.assertEqual(payload["aggregateSummary"]["byEvidenceQuality"]["stale_or_cached"], 1)
        self.assertEqual(payload["aggregateSummary"]["byEvidenceQuality"]["no_evidence"], 1)
        self.assertEqual(payload["dataQuality"]["state"], "partial")
        self.assertTrue(payload["dataQuality"]["failClosed"])

        nvda = next(item for item in payload["items"] if item["ticker"] == "NVDA")
        self.assertEqual(nvda["structureState"], "structure_changed")
        self.assertEqual(nvda["researchPriority"], "medium")
        self.assertIn("Volume structure improved", nvda["whyWatching"])
        self.assertTrue(
            any("Verify local OHLCV coverage" in check for check in nvda["whatToVerify"])
        )
        self.assertIn("cached_or_stale_evidence", nvda["riskFlags"])
        self.assertIn("score_grade_not_allowed", nvda["evidenceGaps"])
        self.assertEqual(nvda["freshness"]["state"], "stale_or_cached")

        msft = next(item for item in payload["items"] if item["ticker"] == "MSFT")
        self.assertIsNone(msft["researchPriority"])
        self.assertIn("local_ohlcv_evidence", msft["evidenceGaps"])
        self.assertIn("local_ohlcv_evidence", payload["missingEvidence"])

        serialized = json.dumps(payload, ensure_ascii=False).lower()
        for forbidden in FORBIDDEN_OVERLAY_TEXT:
            self.assertNotIn(forbidden.lower(), serialized)

    def test_overlay_fails_closed_when_watchlist_read_fails(self) -> None:
        class BrokenWatchlistService:
            def list_items(self, owner_id: str) -> list[dict]:  # noqa: ARG002
                raise RuntimeError("database unavailable")

        payload = WatchlistResearchOverlayService(
            watchlist_service=BrokenWatchlistService()
        ).build_overlay(owner_id="user-1")

        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["dataQuality"]["state"], "unavailable")
        self.assertTrue(payload["dataQuality"]["failClosed"])
        self.assertIn("watchlist_unavailable", payload["missingEvidence"])


if __name__ == "__main__":
    unittest.main()
