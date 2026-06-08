# -*- coding: utf-8 -*-
"""Integration tests for user-owned scanner watchlist endpoints."""

from __future__ import annotations

import os
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from api.deps import CurrentUser, get_current_user
import src.auth as auth
from src.config import Config
from src.storage import DatabaseManager, MarketScannerCandidate, MarketScannerRun, RuleBacktestRun, UserWatchlistItem


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


def _make_user(user_id: str, username: str, *, is_admin: bool = False, auth_enabled: bool = True) -> CurrentUser:
    return CurrentUser(
        user_id=user_id,
        username=username,
        display_name=username.title(),
        role="admin" if is_admin else "user",
        is_admin=is_admin,
        is_authenticated=True,
        transitional=False,
        auth_enabled=auth_enabled,
    )


class WatchlistApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "watchlist_api_test.db"
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=600519",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=false",
                    f"DATABASE_PATH={self.db_path}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.db_path)
        Config.reset_instance()
        _reset_auth_globals()
        DatabaseManager.reset_instance()
        app = create_app(static_dir=self.data_dir / "empty-static")
        self.app = app
        self.client = TestClient(app)
        self.db = DatabaseManager.get_instance()
        self.db.create_or_update_app_user(
            user_id="user-1",
            username="alice",
            role="user",
            display_name="Alice",
        )
        self.db.create_or_update_app_user(
            user_id="user-2",
            username="bob",
            role="user",
            display_name="Bob",
        )

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        _reset_auth_globals()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def _make_auth_enabled_client(self) -> TestClient:
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=600519",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=true",
                    f"DATABASE_PATH={self.db_path}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.db_path)
        Config.reset_instance()
        _reset_auth_globals()
        app = create_app(static_dir=self.data_dir / "empty-static")
        return TestClient(app)

    def test_watchlist_add_list_is_owner_scoped_and_preserves_scanner_metadata(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        add_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={
                "symbol": "NVDA",
                "market": "us",
                "name": "NVIDIA",
                "source": "scanner",
                "scanner_run_id": 11,
                "scanner_rank": 1,
                "scanner_score": 94,
                "theme_id": "crypto_miners",
                "universe_type": "default",
                "notes": "Backend reason: momentum and liquidity improved.",
            },
        )
        self.assertEqual(add_resp.status_code, 200)
        payload = add_resp.json()
        self.assertEqual(payload["symbol"], "NVDA")
        self.assertEqual(payload["market"], "us")
        self.assertEqual(payload["scanner_run_id"], 11)
        self.assertEqual(payload["scanner_rank"], 1)
        self.assertEqual(payload["scanner_score"], 94.0)
        self.assertEqual(payload["theme_id"], "crypto_miners")
        self.assertEqual(payload["universe_type"], "default")

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.json()["items"]), 1)

        logs, total = self.db.list_execution_log_sessions(task_id="portfolio:watchlist_add", limit=10)
        self.assertEqual(total, 1)
        self.assertEqual(logs[0]["code"], "NVDA")
        self.assertEqual(logs[0]["summary"]["portfolio_event"]["category"], "watchlist")
        self.assertEqual(logs[0]["summary"]["portfolio_event"]["scanner_run_id"], 11)

    def test_watchlist_duplicate_add_is_idempotent_and_delete_is_owner_scoped(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        first_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "MARA", "market": "us", "source": "scanner"},
        )
        self.assertEqual(first_resp.status_code, 200)
        first_item = first_resp.json()

        second_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "MARA", "market": "us", "source": "scanner", "notes": "updated note"},
        )
        self.assertEqual(second_resp.status_code, 200)
        second_item = second_resp.json()
        self.assertEqual(second_item["id"], first_item["id"])
        self.assertEqual(second_item["notes"], "updated note")

        delete_resp = self.client.delete(f"/api/v1/watchlist/items/{first_item['id']}")
        self.assertEqual(delete_resp.status_code, 200)
        self.assertEqual(delete_resp.json()["deleted"], 1)

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(list_resp.json()["items"], [])

    def test_watchlist_items_do_not_leak_between_users(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")
        create_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "AVGO", "market": "us", "source": "scanner"},
        )
        self.assertEqual(create_resp.status_code, 200)
        item_id = create_resp.json()["id"]

        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-2", "bob")
        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(list_resp.json()["items"], [])

        delete_resp = self.client.delete(f"/api/v1/watchlist/items/{item_id}")
        self.assertEqual(delete_resp.status_code, 404)

    def test_watchlist_unauthorized_add_is_rejected_when_auth_is_enabled(self) -> None:
        client = self._make_auth_enabled_client()
        resp = client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "NVDA", "market": "us", "source": "scanner"},
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["error"], "unauthorized")

    def test_watchlist_validation_rejects_invalid_symbol_and_market(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        bad_symbol = self.client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "???", "market": "us", "source": "scanner"},
        )
        self.assertEqual(bad_symbol.status_code, 422)

        bad_market = self.client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "NVDA", "market": "EU", "source": "scanner"},
        )
        self.assertEqual(bad_market.status_code, 422)

    def test_watchlist_refresh_scores_endpoint_updates_scanner_score(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")
        add_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={
                "symbol": "WULF",
                "market": "us",
                "source": "scanner",
                "scanner_run_id": 5,
                "scanner_rank": 8,
                "scanner_score": 60,
                "theme_id": "crypto_miners",
                "universe_type": "theme",
            },
        )
        self.assertEqual(add_resp.status_code, 200)

        now = datetime.now()
        run = MarketScannerRun(
            market="us",
            profile="us_preopen_v1",
            universe_name="us_preopen_watchlist_v1",
            status="completed",
            run_at=now,
            completed_at=now,
            shortlist_size=1,
        )
        candidate = MarketScannerCandidate(
            symbol="WULF",
            name="WULF",
            rank=2,
            score=71.5,
            reason_summary="Scanner score refreshed.",
            created_at=now,
        )
        with self.db.get_session() as session:
            session.add(run)
            session.flush()
            run_id = run.id
            candidate.run_id = run.id
            session.add(candidate)
            session.commit()

        refresh_resp = self.client.post("/api/v1/watchlist/refresh-scores", json={"market": "us"})
        self.assertEqual(refresh_resp.status_code, 200)
        payload = refresh_resp.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["updated_count"], 1)
        self.assertEqual(payload["results"][0]["status"], "fresh")

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        item = list_resp.json()["items"][0]
        self.assertEqual(item["scanner_run_id"], run_id)
        self.assertEqual(item["scanner_score"], 71.5)
        self.assertEqual(item["scanner_rank"], 2)
        self.assertEqual(item["score_source"], "scanner_run")
        self.assertEqual(item["score_profile"], "us_preopen_v1")
        self.assertEqual(item["score_reason"], "Scanner score refreshed.")
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
        self.assertEqual(item["theme_id"], "crypto_miners")
        self.assertEqual(item["universe_type"], "theme")
        self.assertTrue(item["last_scored_at"])

    def test_watchlist_items_project_local_ohlcv_provenance_from_scanner_candidate_diagnostics(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        now = datetime.now()
        run = MarketScannerRun(
            market="us",
            profile="us_preopen_v1",
            universe_name="us_preopen_watchlist_v1",
            status="completed",
            run_at=now,
            completed_at=now,
            shortlist_size=1,
        )
        candidate = MarketScannerCandidate(
            symbol="WULF",
            name="WULF",
            rank=2,
            score=71.5,
            reason_summary="Scanner score refreshed.",
            diagnostics_json=json.dumps(
                {
                    "history": {
                        "source": "local_us_parquet",
                        "latest_trade_date": "2026-05-22",
                    }
                },
                ensure_ascii=False,
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

        add_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={
                "symbol": "WULF",
                "market": "us",
                "source": "scanner",
                "scanner_run_id": run_id,
                "scanner_rank": 2,
                "scanner_score": 71.5,
            },
        )
        self.assertEqual(add_resp.status_code, 200)

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        provenance = list_resp.json()["items"][0]["intelligence"]["scanner"]["ohlcv_provenance"]
        self.assertEqual(provenance["source"], "local_us_parquet")
        self.assertEqual(provenance["source_type"], "cache_snapshot")
        self.assertEqual(provenance["source_label"], "本地 Parquet 历史")

    def test_watchlist_items_project_scanner_confidence_disclosure_metadata(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        now = datetime.now()
        run = MarketScannerRun(
            market="us",
            profile="us_preopen_v1",
            universe_name="us_preopen_watchlist_v1",
            status="completed",
            run_at=now,
            completed_at=now,
            shortlist_size=1,
        )
        candidate = MarketScannerCandidate(
            symbol="WULF",
            name="WULF",
            rank=2,
            score=71.5,
            reason_summary="Scanner score refreshed.",
            diagnostics_json=json.dumps(
                {
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
                ensure_ascii=False,
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

        add_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={
                "symbol": "WULF",
                "market": "us",
                "source": "scanner",
                "scanner_run_id": run_id,
                "scanner_rank": 2,
                "scanner_score": 71.5,
            },
        )
        self.assertEqual(add_resp.status_code, 200)

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        scanner = list_resp.json()["items"][0]["intelligence"]["scanner"]
        self.assertEqual(scanner["score_confidence"], 0.35)
        self.assertEqual(scanner["cap_reason"], "configured_cache_only_diagnostic")
        self.assertEqual(scanner["degradation_reason"], "configured_cache_only_diagnostic")
        self.assertFalse(scanner["score_grade_allowed"])
        self.assertEqual(
            scanner["reason_families"]["cap_reason"],
            {
                "raw_code": "configured_cache_only_diagnostic",
                "family": "unclassified",
                "scope": None,
            },
        )
        self.assertEqual(
            scanner["reason_families"]["degradation_reason"],
            {
                "raw_code": "configured_cache_only_diagnostic",
                "family": "unclassified",
                "scope": None,
            },
        )
        self.assertEqual(
            scanner["reason_families"]["source_confidence"]["cap_reason"],
            {
                "raw_code": "configured_cache_only_diagnostic",
                "family": "unclassified",
                "scope": None,
            },
        )
        self.assertEqual(
            scanner["reason_families"]["source_confidence"]["degradation_reason"],
            {
                "raw_code": "configured_cache_only_diagnostic",
                "family": "unclassified",
                "scope": None,
            },
        )
        self.assertEqual(scanner["source_confidence"]["source"], "local_us_parquet_dir")
        self.assertEqual(scanner["source_confidence"]["source_type"], "cache_snapshot")
        self.assertFalse(scanner["source_confidence"]["score_contribution_allowed"])
        self.assertFalse(scanner["source_confidence"]["source_authority_allowed"])
        self.assertTrue(scanner["source_confidence"]["observation_only"])
        investor_signal = scanner["investor_signal"]
        self.assertEqual(investor_signal["contractVersion"], "investor_signal_contract_v1")
        self.assertFalse(investor_signal["sourceAuthorityAllowed"])
        self.assertEqual(investor_signal["freshness"], "cached")
        self.assertEqual(investor_signal["confidenceLabel"], "blocked")
        self.assertIn("source_authority_missing", investor_signal["reasonCodes"])
        self.assertIn("score_rights_missing", investor_signal["reasonCodes"])

    def test_watchlist_items_project_scanner_lineage_v1_without_raw_diagnostics(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        now = datetime(2026, 5, 4, 9, 30, 0)
        run = MarketScannerRun(
            market="us",
            profile="us_preopen_v1",
            universe_name="us_preopen_watchlist_v1",
            status="completed",
            run_at=now,
            completed_at=now,
            shortlist_size=1,
        )
        candidate = MarketScannerCandidate(
            symbol="WULF",
            name="WULF",
            rank=2,
            score=71.5,
            reason_summary="动量延续，等待补充证据。",
            diagnostics_json=json.dumps(
                {
                    "candidateResearchSummaryFrame": {
                        "primaryResearchReason": "动量延续，等待补充证据。",
                        "researchNextStep": "补充证据后继续观察。",
                    },
                    "consumerDiagnostics": {
                        "userFacingLabels": ["当前信号置信度较低，仅供观察。"],
                    },
                    "score_explainability": {
                        "score_confidence": 0.35,
                        "cap_reason": "configured_cache_only_diagnostic",
                        "degradation_reason": "configured_cache_only_diagnostic",
                        "score_grade_allowed": True,
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
                            "coverage": 1.0,
                            "scoreContributionAllowed": False,
                            "sourceAuthorityAllowed": False,
                            "observationOnly": True,
                        },
                    },
                    "providerObservation": {
                        "entries": [{"providerName": "internal-provider"}],
                    },
                    "reasonCodes": ["sourceAuthorityAllowed=false"],
                    "rawDiagnostics": {"debug": "should not leave backend"},
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

        add_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={
                "symbol": "WULF",
                "market": "us",
                "source": "scanner",
                "scanner_run_id": run_id,
                "scanner_rank": 2,
                "scanner_score": 71.5,
                "theme_id": "crypto_miners",
                "universe_type": "theme",
                "notes": "保存备注不应覆盖 Scanner 安全研究原因。",
            },
        )
        self.assertEqual(add_resp.status_code, 200)

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        scanner = list_resp.json()["items"][0]["intelligence"]["scanner"]
        lineage = scanner["scanner_lineage_v1"]

        self.assertEqual(
            lineage,
            {
                "contract_version": "scanner_watchlist_lineage_v1",
                "source": "scanner",
                "scanner_run_id": run_id,
                "symbol": "WULF",
                "market": "us",
                "rank_at_scan": 2,
                "score_at_scan": 71.5,
                "score_snapshot_kind": "saved_at_add",
                "run_profile": "us_preopen_v1",
                "run_completed_at": "2026-05-04T09:30:00",
                "watchlist_added_at": add_resp.json()["created_at"],
                "theme_id": "crypto_miners",
                "universe_type": "theme",
                "research_reason": "动量延续，等待补充证据。",
                "research_next_step": "补充证据后继续观察。",
                "data_state": "observation_only",
                "freshness_label": "最近可用",
                "no_advice_boundary": True,
                "observation_only": True,
                "score_grade_allowed": False,
            },
        )

        serialized_lineage = json.dumps(lineage, ensure_ascii=False)
        self.assertNotIn("source_confidence", lineage)
        self.assertNotIn("providerObservation", serialized_lineage)
        self.assertNotIn("rawDiagnostics", serialized_lineage)
        self.assertNotIn("reasonCodes", serialized_lineage)
        self.assertNotIn("sourceAuthorityAllowed", serialized_lineage)
        self.assertNotIn("scoreContributionAllowed", serialized_lineage)
        self.assertNotIn("internal-provider", serialized_lineage)

    def test_watchlist_items_attach_catalyst_exposures_from_explicit_saved_evidence(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        now = datetime.now()
        run = MarketScannerRun(
            market="us",
            profile="us_preopen_v1",
            universe_name="us_preopen_watchlist_v1",
            status="completed",
            run_at=now,
            completed_at=now,
            shortlist_size=1,
        )
        candidate = MarketScannerCandidate(
            symbol="NVDA",
            name="NVIDIA",
            rank=1,
            score=94.0,
            reason_summary="Scanner score refreshed.",
            diagnostics_json=json.dumps(
                {
                    "fundamentalSnapshot": {
                        "reportedPeriod": "2026Q2",
                        "summary": "Quarterly revenue and margin snapshot is available.",
                        "asOf": "2026-05-17T20:00:00+00:00",
                        "freshness": "delayed",
                        "providerPayload": {"raw": "must-not-leak"},
                    },
                    "storedNewsItems": [
                        {
                            "headline": "Supplier commentary mentions demand stabilization",
                            "summary": "Stored article summary references a potential demand catalyst.",
                            "publishedAt": "2026-05-17T13:00:00+00:00",
                            "sourceProvider": "must-not-leak",
                            "rawPayload": {"body": "must-not-leak"},
                        }
                    ],
                    "officialMacroStatus": {
                        "status": "cache_hit",
                        "asOf": "2026-05-17",
                        "series": [{"symbol": "CPIAUCSL", "name": "CPI"}],
                        "admin": {"trace": "must-not-leak"},
                        "debug": "must-not-leak",
                    },
                },
                ensure_ascii=False,
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

        add_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={
                "symbol": "NVDA",
                "market": "us",
                "source": "scanner",
                "scanner_run_id": run_id,
                "scanner_rank": 1,
                "scanner_score": 94.0,
            },
        )
        self.assertEqual(add_resp.status_code, 200)

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        exposures = list_resp.json()["items"][0]["intelligence"]["catalyst_exposures"]

        self.assertEqual([item["category"] for item in exposures], [
            "earnings_fundamental_snapshot",
            "stored_news_catalyst_proxy",
            "official_macro_cache_status",
        ])
        self.assertEqual(exposures[0]["timeframe"], "2026Q2")
        self.assertEqual(exposures[1]["publishedAt"], "2026-05-17T13:00:00+00:00")
        self.assertEqual(exposures[2]["evidenceLabels"], ["delayed"])
        for item in exposures:
            self.assertTrue(item["observationOnly"])
            self.assertFalse(item["sourceAuthorityAllowed"])
            self.assertFalse(item["scoreContributionAllowed"])
            self.assertFalse(item["decisionGrade"])
            self.assertFalse(item["calendarClaimAllowed"])
            self.assertIn("observation_only", item["reasonCodes"])

        serialized = json.dumps(exposures, ensure_ascii=False, sort_keys=True)
        for forbidden in (
            "must-not-leak",
            "providerPayload",
            "rawPayload",
            "sourceProvider",
            "admin",
            "debug",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_watchlist_catalyst_exposures_keep_stale_and_proxy_inputs_fail_closed(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        now = datetime.now()
        run = MarketScannerRun(
            market="us",
            profile="us_preopen_v1",
            universe_name="us_preopen_watchlist_v1",
            status="completed",
            run_at=now,
            completed_at=now,
            shortlist_size=1,
        )
        candidate = MarketScannerCandidate(
            symbol="AAPL",
            name="Apple",
            rank=2,
            score=88.0,
            reason_summary="Scanner score refreshed.",
            diagnostics_json=json.dumps(
                {
                    "fundamentalSnapshot": {
                        "summary": "Delayed snapshot only.",
                        "stale": True,
                        "asOf": "2026-04-30T20:00:00+00:00",
                    },
                    "storedNewsItems": [
                        {
                            "headline": "Cached headline",
                            "summary": "Cached summary.",
                            "stale": True,
                            "publishedAt": "2026-04-29T12:00:00+00:00",
                        }
                    ],
                    "officialMacroStatus": {
                        "status": "stale",
                        "asOf": "2026-04-29",
                    },
                },
                ensure_ascii=False,
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

        add_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={
                "symbol": "AAPL",
                "market": "us",
                "source": "scanner",
                "scanner_run_id": run_id,
                "scanner_rank": 2,
                "scanner_score": 88.0,
            },
        )
        self.assertEqual(add_resp.status_code, 200)

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        exposures = list_resp.json()["items"][0]["intelligence"]["catalyst_exposures"]

        self.assertEqual(len(exposures), 3)
        self.assertEqual(exposures[0]["evidenceStatus"], "stale")
        self.assertEqual(exposures[1]["evidenceStatus"], "stale")
        self.assertIn("proxy", exposures[1]["evidenceLabels"])
        self.assertEqual(exposures[2]["evidenceStatus"], "stale")
        for item in exposures:
            self.assertFalse(item["sourceAuthorityAllowed"])
            self.assertFalse(item["scoreContributionAllowed"])
            self.assertFalse(item["decisionGrade"])
            self.assertFalse(item["calendarClaimAllowed"])
            self.assertIn("stale_evidence", item["reasonCodes"])

    def test_watchlist_catalyst_exposures_omit_missing_and_non_eligible_inputs(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        now = datetime.now()
        run = MarketScannerRun(
            market="us",
            profile="us_preopen_v1",
            universe_name="us_preopen_watchlist_v1",
            status="completed",
            run_at=now,
            completed_at=now,
            shortlist_size=1,
        )
        candidate = MarketScannerCandidate(
            symbol="TSM",
            name="TSMC",
            rank=3,
            score=86.0,
            reason_summary="Scanner score refreshed.",
            diagnostics_json=json.dumps(
                {
                    "fundamentalSnapshot": {
                        "providerPayload": {"raw": "provider-only"},
                    },
                    "storedNewsItems": [
                        {
                            "publishedAt": "2026-05-17T13:00:00+00:00",
                            "rawPayload": {"body": "provider-only"},
                        }
                    ],
                    "officialMacroStatus": {
                        "admin": {"trace": "provider-only"},
                        "debug": "provider-only",
                    },
                },
                ensure_ascii=False,
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

        add_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={
                "symbol": "TSM",
                "market": "us",
                "source": "scanner",
                "scanner_run_id": run_id,
                "scanner_rank": 3,
                "scanner_score": 86.0,
            },
        )
        self.assertEqual(add_resp.status_code, 200)

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        intelligence = list_resp.json()["items"][0]["intelligence"]
        self.assertTrue("catalyst_exposures" not in intelligence or intelligence["catalyst_exposures"] in (None, []))

    def test_watchlist_items_include_read_only_intelligence_from_saved_records(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")
        add_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={
                "symbol": "WULF",
                "market": "us",
                "name": "TeraWulf",
                "source": "scanner",
                "scanner_run_id": 11,
                "scanner_rank": 1,
                "scanner_score": 60,
                "theme_id": "crypto_miners",
                "universe_type": "theme",
                "notes": "趋势/动量通过",
            },
        )
        self.assertEqual(add_resp.status_code, 200)

        older = RuleBacktestRun(
            owner_id="user-1",
            code="WULF",
            strategy_text="观察列表单标的回测",
            parsed_strategy_json="{}",
            strategy_hash="old",
            status="completed",
            run_at=datetime(2026, 5, 1, 8, 0, 0),
            completed_at=datetime(2026, 5, 1, 8, 1, 0),
            trade_count=1,
            total_return_pct=4.0,
            max_drawdown_pct=-2.0,
        )
        latest = RuleBacktestRun(
            owner_id="user-1",
            code="WULF",
            strategy_text="观察列表单标的回测",
            parsed_strategy_json="{}",
            strategy_hash="latest",
            status="completed",
            run_at=datetime(2026, 5, 2, 8, 0, 0),
            completed_at=datetime(2026, 5, 2, 8, 1, 0),
            trade_count=6,
            total_return_pct=24.6,
            max_drawdown_pct=-8.2,
            summary_json='{"metrics":{"sharpe_ratio":1.34}}',
        )
        failed = RuleBacktestRun(
            owner_id="user-1",
            code="WULF",
            strategy_text="观察列表单标的回测",
            parsed_strategy_json="{}",
            strategy_hash="failed",
            status="failed",
            run_at=datetime(2026, 5, 3, 8, 0, 0),
            completed_at=datetime(2026, 5, 3, 8, 1, 0),
            trade_count=0,
            total_return_pct=99.0,
        )
        with self.db.get_session() as session:
            session.add_all([older, latest, failed])
            session.commit()
            latest_id = latest.id

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        item = list_resp.json()["items"][0]
        intelligence = item["intelligence"]
        self.assertEqual(intelligence["scanner"]["last_score"], 60.0)
        self.assertEqual(intelligence["scanner"]["last_rank"], 1)
        self.assertEqual(intelligence["scanner"]["status"], "selected")
        self.assertEqual(intelligence["scanner"]["theme"], "crypto_miners")
        self.assertEqual(intelligence["scanner"]["profile"], None)
        self.assertEqual(intelligence["scanner"]["reason"], "趋势/动量通过")
        self.assertEqual(intelligence["strategy_simulation"]["status"], "unknown")
        self.assertEqual(intelligence["backtest"]["last_result_id"], latest_id)
        self.assertEqual(intelligence["backtest"]["total_return_pct"], 24.6)
        self.assertEqual(intelligence["backtest"]["max_drawdown_pct"], -8.2)
        self.assertEqual(intelligence["backtest"]["sharpe"], 1.34)
        self.assertEqual(intelligence["backtest"]["trade_count"], 6)

    def test_watchlist_items_remain_compatible_with_legacy_scalar_only_rows(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        with self.db.get_session() as session:
            session.add(
                UserWatchlistItem(
                    owner_id="user-1",
                    symbol="600001",
                    market="cn",
                    name="平安银行",
                    source="scanner",
                    scanner_run_id=8,
                    scanner_rank=2,
                    scanner_score=77.5,
                    notes="legacy row without provider observation metadata",
                )
            )
            session.commit()

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        item = list_resp.json()["items"][0]
        self.assertEqual(item["symbol"], "600001")
        self.assertEqual(item["scanner_run_id"], 8)
        self.assertEqual(item["scanner_rank"], 2)
        self.assertEqual(item["scanner_score"], 77.5)
        self.assertNotIn("providerObservation", item)
        self.assertNotIn("providerObservation", item["intelligence"]["scanner"])
        self.assertEqual(item["intelligence"]["scanner"]["last_score"], 77.5)
        self.assertEqual(item["intelligence"]["scanner"]["last_rank"], 2)
        self.assertEqual(item["intelligence"]["scanner"]["reason"], "legacy row without provider observation metadata")

    def test_watchlist_items_without_records_return_null_safe_intelligence(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")
        add_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "MARA", "market": "us", "source": "scanner"},
        )
        self.assertEqual(add_resp.status_code, 200)

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        intelligence = list_resp.json()["items"][0]["intelligence"]
        self.assertIsNone(intelligence["scanner"]["last_score"])
        self.assertEqual(intelligence["scanner"]["status"], "unknown")
        self.assertEqual(intelligence["strategy_simulation"]["status"], "unknown")
        self.assertIsNone(intelligence["backtest"]["last_result_id"])
