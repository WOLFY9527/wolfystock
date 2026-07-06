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
from src.services import watchlist_service as watchlist_service_module
from src.config import Config
from src.multi_user import OWNERSHIP_SCOPE_USER
from src.storage import DatabaseManager, MarketScannerCandidate, MarketScannerRun, RuleBacktestRun, UserWatchlistItem


FORBIDDEN_CONSUMER_RESPONSE_FIELDS = (
    "fallback",
    "trustLevel",
    "reasonCode",
    "sourceType",
    "launchVerdict",
    "consumerVisible",
    "advisoryOnly",
    "liveEnforcement",
    "isFallback",
    "isStale",
    "isPartial",
    "source_type",
    "scoreContributionAllowed",
    "score_contribution_allowed",
    "observation_only",
    "raw provider error",
    "providerName",
    "providerClass",
    "providerAttempted",
    "apiKey",
    "credential",
    "env",
    "requestId",
    "traceId",
    "cacheKey",
    "rawPayload",
    "exceptionClass",
    "stack",
    "Traceback",
    "https://",
    "api_key",
    "secret",
    "cookie",
    "session_id",
    "token",
    "target price",
    "predicted return",
)


def _assert_no_forbidden_consumer_response_fields(payload: dict) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    normalized = serialized.lower()
    for forbidden in FORBIDDEN_CONSUMER_RESPONSE_FIELDS:
        assert forbidden not in serialized
        assert forbidden.lower() not in normalized


def _assert_safe_watchlist_research_context(item: dict) -> None:
    research_fields = {
        "symbol_status": item.get("symbol_status"),
        "research_status": item.get("research_status"),
        "data_quality": item.get("data_quality"),
        "last_reviewed_at": item.get("last_reviewed_at"),
        "evidence_status": item.get("evidence_status"),
        "notes_available": item.get("notes_available"),
        "user_note_present": item.get("user_note_present"),
        "no_advice_disclosure": item.get("no_advice_disclosure"),
    }
    self_contained = {key: value for key, value in research_fields.items() if value is not None}
    serialized = json.dumps(self_contained, ensure_ascii=False)
    normalized = serialized.lower()
    for forbidden in FORBIDDEN_CONSUMER_RESPONSE_FIELDS:
        assert forbidden not in serialized
        assert forbidden.lower() not in normalized
    assert "buy" not in normalized
    assert "sell" not in normalized
    assert "add position" not in normalized
    assert "reduce" not in normalized
    assert "买入" not in serialized
    assert "卖出" not in serialized
    assert "加仓" not in serialized
    assert "减仓" not in serialized


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
        self.previous_admin_auth_enabled = os.environ.get("ADMIN_AUTH_ENABLED")
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
        os.environ["ADMIN_AUTH_ENABLED"] = "false"
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
        if self.previous_admin_auth_enabled is None:
            os.environ.pop("ADMIN_AUTH_ENABLED", None)
        else:
            os.environ["ADMIN_AUTH_ENABLED"] = self.previous_admin_auth_enabled
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
        os.environ["ADMIN_AUTH_ENABLED"] = "true"
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
        self.assertEqual(payload["symbol_status"], "ready")
        self.assertEqual(payload["research_status"], "ready")
        self.assertEqual(payload["data_quality"], "ready")
        self.assertEqual(payload["evidence_status"], "ready")
        self.assertTrue(payload["notes_available"])
        self.assertTrue(payload["user_note_present"])
        self.assertIn("research", payload["no_advice_disclosure"].lower())
        _assert_safe_watchlist_research_context(payload)

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

    def test_watchlist_item_projects_canonical_identity_and_six_state_readiness(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        def fake_packet(stock_code: str, *, market: str | None = None) -> dict:
            self.assertEqual(stock_code, "AAPL")
            self.assertEqual(market, "us")
            return {
                "symbol": "AAPL",
                "market": "us",
                "identity": {
                    "name": "Apple Inc.",
                    "exchange": "NASDAQ",
                    "sector": "Technology",
                    "industry": "Consumer Electronics",
                },
                "quote": {"state": "stale", "price": 190.25, "changePercent": -0.42, "asOf": "2026-05-01T11:00:00Z"},
                "missingData": ["fundamentals", "filing_event_catalyst"],
                "researchStatus": "partial",
                "nextDataAction": "Add fundamentals and event evidence before marking the packet ready.",
                "observationOnly": True,
                "decisionGrade": False,
                "noAdviceDisclosure": "Observation-only research packet; no personalized action instruction.",
            }

        self.addCleanup(
            setattr,
            watchlist_service_module,
            "build_symbol_research_packet",
            watchlist_service_module.build_symbol_research_packet,
        )
        watchlist_service_module.build_symbol_research_packet = fake_packet

        add_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={
                "symbol": "aapl",
                "market": "us",
                "name": "Apple Inc.",
                "source": "scanner",
                "scanner_score": 88,
                "score_status": "partial",
            },
        )

        self.assertEqual(add_resp.status_code, 200, add_resp.text)
        payload = add_resp.json()
        self.assertEqual(
            payload["identity"],
            {
                "canonical_symbol": "AAPL",
                "display_symbol": "AAPL",
                "market": "us",
                "exchange": "NASDAQ",
                "display_name": "Apple Inc.",
                "identity_state": "resolved",
            },
        )
        self.assertEqual(payload["research_readiness"]["state"], "partial")
        self.assertEqual(payload["research_readiness"]["freshness_state"], "stale")
        self.assertEqual(payload["research_readiness"]["identity_state"], "resolved")
        self.assertEqual(payload["research_readiness"]["contract_version"], "product_read_model_v1")
        self.assertEqual(payload["rowResearchPacket"]["identity"]["canonicalSymbol"], "AAPL")
        self.assertEqual(payload["rowResearchPacket"]["identity"]["displaySymbol"], "AAPL")
        self.assertEqual(payload["rowResearchPacket"]["identity"]["identityState"], "resolved")

    def test_watchlist_add_rejects_unsupported_market_identity_without_provider_lookup(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        resp = self.client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "600519", "market": "us", "source": "scanner"},
        )

        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertEqual(body["error"], "validation_error")
        self.assertIn("unsupported", body["message"].lower())
        self.assertIn("market", body["message"].lower())

    def test_watchlist_duplicate_add_reports_existing_identity_without_creating_ambiguous_rows(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        first_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "AAPL", "market": "us", "source": "scanner", "notes": "first"},
        )
        self.assertEqual(first_resp.status_code, 200, first_resp.text)
        first_payload = first_resp.json()
        self.assertTrue(first_payload["created_new"])
        self.assertIsNone(first_payload["duplicate_of_id"])

        second_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "aapl", "market": "us", "source": "scanner", "notes": "second"},
        )
        self.assertEqual(second_resp.status_code, 200, second_resp.text)
        second_payload = second_resp.json()
        self.assertEqual(second_payload["id"], first_payload["id"])
        self.assertFalse(second_payload["created_new"])
        self.assertEqual(second_payload["duplicate_of_id"], first_payload["id"])

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual([item["id"] for item in list_resp.json()["items"]], [first_payload["id"]])

    def test_watchlist_create_from_scanner_candidate_preserves_research_queue_evidence(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        now = datetime(2026, 6, 25, 9, 30, 0)
        run = MarketScannerRun(
            owner_id="user-1",
            scope=OWNERSHIP_SCOPE_USER,
            market="us",
            profile="us_preopen_v1",
            universe_name="us_cached_ohlcv",
            status="completed",
            run_at=now,
            completed_at=now,
            shortlist_size=1,
        )
        candidate = MarketScannerCandidate(
            symbol="WULF",
            name="TeraWulf",
            rank=2,
            score=71.5,
            quality_hint="cached",
            reason_summary="趋势结构和成交活跃度触发研究观察。",
            reasons_json=json.dumps(["momentum_structure", "volume_expansion"], ensure_ascii=False),
            diagnostics_json=json.dumps(
                {
                    "history": {"source": "local_us_parquet", "latest_trade_date": "2026-06-24"},
                    "candidateResearchSummaryFrame": {
                        "primaryResearchReason": "趋势结构和成交活跃度触发研究观察。",
                        "researchNextStep": "补充报价与基本面证据后继续观察。",
                    },
                    "candidateResearchReadiness": {
                        "readinessState": "partial",
                        "missingEvidence": ["quote", "fundamentals"],
                    },
                    "score_explainability": {
                        "score_confidence": 0.35,
                        "score_grade_allowed": False,
                        "cap_reason": "configured_cache_only_diagnostic",
                        "source_confidence": {
                            "freshness": "cached",
                            "scoreContributionAllowed": False,
                            "sourceAuthorityAllowed": False,
                            "observationOnly": True,
                        },
                    },
                    "reasonCodes": ["sourceAuthorityAllowed=false"],
                    "providerName": "must-not-leak",
                    "providerClass": "must-not-leak",
                    "providerAttempted": True,
                    "apiKey": "must-not-leak",
                    "credential": "must-not-leak",
                    "env": "must-not-leak",
                    "requestId": "must-not-leak",
                    "traceId": "must-not-leak",
                    "cacheKey": "must-not-leak",
                    "rawPayload": {"secret": "must-not-leak"},
                    "exceptionClass": "ProviderError",
                    "stack": "Traceback...",
                },
                ensure_ascii=False,
            ),
            created_at=now,
        )
        with self.db.get_session() as session:
            session.add(run)
            session.flush()
            run_id = int(run.id)
            candidate.run_id = run_id
            session.add(candidate)
            session.commit()

        resp = self.client.post(
            "/api/v1/watchlist/items/from-scanner-candidate",
            json={"scanner_run_id": run_id, "symbol": "WULF"},
        )

        self.assertEqual(resp.status_code, 200, resp.text)
        item = resp.json()
        self.assertEqual(item["symbol"], "WULF")
        self.assertEqual(item["market"], "us")
        self.assertEqual(item["name"], "TeraWulf")
        self.assertEqual(item["scanner_run_id"], run_id)
        self.assertEqual(item["scanner_rank"], 2)
        self.assertEqual(item["scanner_score"], 71.5)
        self.assertEqual(item["score_profile"], "us_preopen_v1")
        self.assertEqual(item["score_source"], "scanner_candidate")
        self.assertEqual(item["score_status"], "partial")
        self.assertEqual(item["score_reason"], "趋势结构和成交活跃度触发研究观察。")
        self.assertEqual(item["rowResearchPacket"]["scannerLineage"]["runId"], run_id)

        lineage = item["intelligence"]["scanner"]["scanner_lineage_v1"]
        self.assertEqual(lineage["scanner_run_id"], run_id)
        self.assertEqual(lineage["run_profile"], "us_preopen_v1")
        self.assertEqual(lineage["research_reason"], "趋势结构和成交活跃度触发研究观察。")
        self.assertEqual(lineage["research_next_step"], "补充报价与基本面证据后继续观察。")
        self.assertEqual(lineage["observationReasons"], ["momentum_structure", "volume_expansion"])
        self.assertTrue(lineage["no_advice_boundary"])
        _assert_no_forbidden_consumer_response_fields(item)

    def test_watchlist_create_from_scanner_candidate_returns_safe_not_found_for_missing_run_or_candidate(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        missing_run_resp = self.client.post(
            "/api/v1/watchlist/items/from-scanner-candidate",
            json={"scanner_run_id": 9999, "symbol": "WULF"},
        )
        self.assertEqual(missing_run_resp.status_code, 404)
        self.assertEqual(missing_run_resp.json()["error"], "not_found")
        self.assertIn("unavailable", missing_run_resp.json()["message"].lower())

        now = datetime(2026, 6, 25, 9, 30, 0)
        run = MarketScannerRun(
            owner_id="user-1",
            scope=OWNERSHIP_SCOPE_USER,
            market="us",
            profile="us_preopen_v1",
            universe_name="us_cached_ohlcv",
            status="completed",
            run_at=now,
            completed_at=now,
            shortlist_size=1,
        )
        with self.db.get_session() as session:
            session.add(run)
            session.flush()
            run_id = int(run.id)
            session.add(
                MarketScannerCandidate(
                    run_id=run_id,
                    symbol="AAPL",
                    name="Apple",
                    rank=1,
                    score=80.0,
                    reason_summary="已有候选。",
                    created_at=now,
                )
            )
            session.commit()

        missing_candidate_resp = self.client.post(
            "/api/v1/watchlist/items/from-scanner-candidate",
            json={"scanner_run_id": run_id, "symbol": "WULF"},
        )
        self.assertEqual(missing_candidate_resp.status_code, 404)
        self.assertEqual(missing_candidate_resp.json()["error"], "not_found")

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(list_resp.json()["items"], [])

        serialized = json.dumps(missing_candidate_resp.json(), ensure_ascii=False)
        for forbidden in (
            "providerName",
            "providerClass",
            "providerAttempted",
            "apiKey",
            "credential",
            "env",
            "requestId",
            "traceId",
            "cacheKey",
            "rawPayload",
            "exceptionClass",
            "stack",
            "Traceback",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_watchlist_create_from_scanner_candidate_deduplicates_existing_symbol_entry(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        first_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "WULF", "market": "us", "source": "scanner", "notes": "existing note"},
        )
        self.assertEqual(first_resp.status_code, 200)
        first_id = first_resp.json()["id"]

        now = datetime(2026, 6, 25, 9, 30, 0)
        run = MarketScannerRun(
            owner_id="user-1",
            scope=OWNERSHIP_SCOPE_USER,
            market="us",
            profile="us_preopen_v1",
            universe_name="us_cached_ohlcv",
            status="completed",
            run_at=now,
            completed_at=now,
            shortlist_size=1,
        )
        candidate = MarketScannerCandidate(
            symbol="WULF",
            name="TeraWulf",
            rank=3,
            score=68.0,
            reason_summary="缓存历史证据进入研究队列。",
            reasons_json=json.dumps(["cached_observation"], ensure_ascii=False),
            diagnostics_json=json.dumps({"history": {"source": "local_us_parquet"}}, ensure_ascii=False),
            created_at=now,
        )
        with self.db.get_session() as session:
            session.add(run)
            session.flush()
            run_id = int(run.id)
            candidate.run_id = run_id
            session.add(candidate)
            session.commit()

        bridge_resp = self.client.post(
            "/api/v1/watchlist/items/from-scanner-candidate",
            json={"scanner_run_id": run_id, "symbol": "wulf"},
        )

        self.assertEqual(bridge_resp.status_code, 200, bridge_resp.text)
        self.assertEqual(bridge_resp.json()["id"], first_id)
        self.assertEqual(bridge_resp.json()["scanner_run_id"], run_id)
        self.assertEqual(bridge_resp.json()["scanner_rank"], 3)
        self.assertEqual(bridge_resp.json()["score_profile"], "us_preopen_v1")

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.json()["items"]), 1)

    def test_watchlist_create_from_scanner_candidate_redacts_unsafe_reason_and_advice_copy(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        now = datetime(2026, 6, 25, 9, 30, 0)
        run = MarketScannerRun(
            owner_id="user-1",
            scope=OWNERSHIP_SCOPE_USER,
            market="us",
            profile="us_preopen_v1",
            universe_name="us_cached_ohlcv",
            status="completed",
            run_at=now,
            completed_at=now,
            shortlist_size=1,
        )
        candidate = MarketScannerCandidate(
            symbol="MARA",
            name="MARA",
            rank=1,
            score=90.0,
            reason_summary="providerName=internal credential=abc requestId=abc buy now target price",
            reasons_json=json.dumps(["buy_signal", "safe_observation"], ensure_ascii=False),
            diagnostics_json=json.dumps(
                {
                    "candidateResearchSummaryFrame": {
                        "primaryResearchReason": "providerAttempted apiKey rawPayload buy now",
                        "researchNextStep": "env cacheKey traceId target price stop loss position sizing",
                    },
                    "consumerDiagnostics": {"userFacingLabels": ["safe observation label"]},
                    "history": {"source": "local_us_parquet"},
                    "providerClass": "InternalProvider",
                    "rawPayload": {"token": "secret"},
                    "exceptionClass": "ProviderError",
                    "stack": "Traceback...",
                },
                ensure_ascii=False,
            ),
            created_at=now,
        )
        with self.db.get_session() as session:
            session.add(run)
            session.flush()
            run_id = int(run.id)
            candidate.run_id = run_id
            session.add(candidate)
            session.commit()

        resp = self.client.post(
            "/api/v1/watchlist/items/from-scanner-candidate",
            json={"scanner_run_id": run_id, "symbol": "MARA"},
        )

        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assertEqual(payload["score_reason"], "Scanner candidate moved to research queue.")
        self.assertEqual(
            payload["intelligence"]["scanner"]["scanner_lineage_v1"]["research_reason"],
            "safe observation label",
        )
        self.assertEqual(
            payload["intelligence"]["scanner"]["scanner_lineage_v1"]["research_next_step"],
            "补充证据后继续观察。",
        )
        self.assertEqual(
            payload["intelligence"]["scanner"]["scanner_lineage_v1"]["observationReasons"],
            ["safe_observation"],
        )
        serialized = json.dumps(payload, ensure_ascii=False)
        for forbidden in (
            "providerName",
            "providerClass",
            "providerAttempted",
            "apiKey",
            "credential",
            "env",
            "requestId",
            "traceId",
            "cacheKey",
            "rawPayload",
            "exceptionClass",
            "stack",
            "Traceback",
            "buy",
            "sell",
            "hold",
            "target price",
            "stop loss",
            "position sizing",
            "买入",
            "卖出",
            "持有",
            "目标价",
            "止损",
            "仓位",
        ):
            self.assertNotIn(forbidden, serialized)
        _assert_no_forbidden_consumer_response_fields(payload)

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

    def test_watchlist_item_exposes_row_research_packet_for_saved_symbol_without_name_or_price(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        def fake_packet(stock_code: str, *, market: str | None = None) -> dict:
            self.assertEqual(stock_code, "600519")
            self.assertEqual(market, "cn")
            return {
                "symbol": "600519",
                "market": "cn",
                "identity": {"name": None, "exchange": None, "sector": None, "industry": None},
                "quote": {"state": "missing", "price": None, "changePercent": None, "asOf": None},
                "history": {"state": "missing", "bars": 0, "period": "daily", "asOf": None},
                "structure": {"state": "missing", "label": None, "confidence": None, "asOf": None},
                "fundamentals": {"state": "not_integrated", "fieldsAvailable": []},
                "events": {"state": "not_integrated", "latest": []},
                "peer": {"state": "missing", "benchmark": None},
                "missingData": [
                    "quote",
                    "price_history",
                    "structure_analysis",
                    "fundamentals",
                    "filing_event_catalyst",
                    "peer_benchmark",
                ],
                "researchStatus": "blocked",
                "nextDataAction": "Add quote and daily price history evidence before marking the packet ready.",
                "observationOnly": True,
                "decisionGrade": False,
                "noAdviceDisclosure": "Observation-only research packet; no personalized action instruction.",
            }

        self.addCleanup(
            setattr,
            watchlist_service_module,
            "build_symbol_research_packet",
            watchlist_service_module.build_symbol_research_packet,
        )
        watchlist_service_module.build_symbol_research_packet = fake_packet

        add_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "600519", "market": "cn", "source": "scanner"},
        )
        self.assertEqual(add_resp.status_code, 200)
        self.assertEqual(add_resp.json()["rowResearchPacket"]["symbol"], "600519")
        self.assertEqual(add_resp.json()["rowResearchPacket"]["quote"]["state"], "missing")

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        item = list_resp.json()["items"][0]
        packet = item["rowResearchPacket"]
        self.assertEqual(packet["symbol"], "600519")
        self.assertEqual(packet["market"], "cn")
        self.assertEqual(
            {key: packet["identity"].get(key) for key in ("name", "exchange", "sector", "industry")},
            {"name": None, "exchange": None, "sector": None, "industry": None},
        )
        self.assertEqual(packet["identity"]["canonicalSymbol"], "600519")
        self.assertEqual(packet["identity"]["displaySymbol"], "600519")
        self.assertEqual(packet["identity"]["identityState"], "unresolved")
        self.assertEqual(packet["savedItemSource"], "scanner")
        self.assertEqual(packet["quote"]["state"], "missing")
        self.assertEqual(packet["researchStatus"], "blocked")
        self.assertIn("quote", packet["missingData"])
        self.assertIn("price_history", packet["missingData"])
        self.assertEqual(packet["nextDataAction"], "Add quote and daily price history evidence before marking the packet ready.")
        self.assertTrue(packet["observationOnly"])
        self.assertEqual(packet["noAdviceDisclosure"], "Observation-only research packet; no personalized action instruction.")
        self.assertEqual(
            packet["scannerLineage"],
            {
                "runId": None,
                "rank": None,
                "score": None,
                "status": None,
                "lastScoredAt": None,
            },
        )
        serialized = json.dumps(packet, ensure_ascii=False)
        for forbidden in (
            "sourceAuthorityAllowed",
            "scoreContributionAllowed",
            "provider",
            "cache",
            "runtime",
            "requestId",
            "traceId",
            "buy",
            "sell",
            "hold",
            "target price",
            "stop-loss",
            "position sizing",
            "买入",
            "卖出",
            "持有",
            "目标价",
            "止损",
            "仓位",
        ):
            self.assertNotIn(forbidden, serialized)

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

    def test_watchlist_refresh_without_stored_score_does_not_invent_freshness_timestamp(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        add_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "MSFT", "market": "us", "source": "scanner"},
        )
        self.assertEqual(add_resp.status_code, 200, add_resp.text)
        self.assertIsNone(add_resp.json()["last_scored_at"])

        refresh_resp = self.client.post("/api/v1/watchlist/refresh-scores", json={"market": "us"})

        self.assertEqual(refresh_resp.status_code, 200, refresh_resp.text)
        result = refresh_resp.json()["results"][0]
        self.assertEqual(result["status"], "unavailable")
        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        item = list_resp.json()["items"][0]
        self.assertIsNone(item["last_scored_at"])
        self.assertEqual(item["score_status"], "unavailable")
        self.assertEqual(item["research_readiness"]["state"], "unavailable")

    def test_watchlist_row_research_packet_includes_scanner_lineage_without_raw_diagnostics(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        def fake_packet(stock_code: str, *, market: str | None = None) -> dict:
            self.assertEqual(stock_code, "WULF")
            self.assertEqual(market, "us")
            return {
                "symbol": "WULF",
                "market": "us",
                "identity": {"name": None, "exchange": None, "sector": None, "industry": None},
                "quote": {"state": "missing", "price": None, "changePercent": None, "asOf": None},
                "history": {"state": "missing", "bars": 0, "period": "daily", "asOf": None},
                "structure": {"state": "missing", "label": None, "confidence": None, "asOf": None},
                "fundamentals": {"state": "not_integrated", "fieldsAvailable": []},
                "events": {"state": "not_integrated", "latest": []},
                "peer": {"state": "missing", "benchmark": None},
                "missingData": ["quote", "price_history", "fundamentals", "filing_event_catalyst"],
                "researchStatus": "blocked",
                "nextDataAction": "Add quote and daily price history evidence before marking the packet ready.",
                "observationOnly": True,
                "decisionGrade": False,
                "noAdviceDisclosure": "Observation-only research packet; no personalized action instruction.",
            }

        self.addCleanup(
            setattr,
            watchlist_service_module,
            "build_symbol_research_packet",
            watchlist_service_module.build_symbol_research_packet,
        )
        watchlist_service_module.build_symbol_research_packet = fake_packet

        add_resp = self.client.post(
            "/api/v1/watchlist/items",
            json={
                "symbol": "WULF",
                "market": "us",
                "source": "scanner",
                "scanner_run_id": 5,
                "scanner_rank": 8,
                "scanner_score": 60,
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

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        packet = list_resp.json()["items"][0]["rowResearchPacket"]
        self.assertEqual(
            packet["scannerLineage"],
            {
                "runId": run_id,
                "rank": 2,
                "score": 71.5,
                "status": "fresh",
                "lastScoredAt": list_resp.json()["items"][0]["last_scored_at"],
            },
        )
        self.assertEqual(packet["researchStatus"], "blocked")
        self.assertEqual(packet["quote"]["state"], "missing")
        serialized = json.dumps(packet, ensure_ascii=False)
        for forbidden in (
            "sourceAuthorityAllowed",
            "scoreContributionAllowed",
            "source_confidence",
            "provider",
            "rawDiagnostics",
            "trace",
            "target price",
            "predicted return",
            "买入",
            "卖出",
            "目标价",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_watchlist_items_project_safe_local_ohlcv_quality_from_scanner_candidate_diagnostics(self) -> None:
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
        payload = list_resp.json()
        scanner = payload["items"][0]["intelligence"]["scanner"]
        provenance = scanner["ohlcv_provenance"]
        self.assertEqual(provenance["data_quality"], "cached")
        self.assertEqual(provenance["label"], "最近可用")
        self.assertEqual(scanner["data_quality"], "cached")
        item = payload["items"][0]
        self.assertEqual(item["symbol_status"], "ready")
        self.assertEqual(item["research_status"], "stale_or_cached")
        self.assertEqual(item["data_quality"], "stale_or_cached")
        self.assertEqual(item["evidence_status"], "stale_or_cached")
        self.assertTrue(item["last_reviewed_at"])
        _assert_safe_watchlist_research_context(item)
        _assert_no_forbidden_consumer_response_fields(payload)

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
        self.assertEqual(scanner["data_quality"], "cached")
        self.assertNotIn("cap_reason", scanner)
        self.assertNotIn("degradation_reason", scanner)
        self.assertNotIn("score_grade_allowed", scanner)
        self.assertNotIn("reason_families", scanner)
        self.assertNotIn("source_confidence", scanner)
        investor_signal = scanner["investor_signal"]
        self.assertEqual(investor_signal["contractVersion"], "investor_signal_contract_v1")
        self.assertEqual(investor_signal["freshness"], "cached")
        self.assertEqual(investor_signal["confidenceLabel"], "blocked")
        self.assertNotIn("sourceAuthorityAllowed", investor_signal)
        self.assertNotIn("reasonCodes", investor_signal)
        _assert_no_forbidden_consumer_response_fields(list_resp.json())

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
                "observationReasons": [],
                "data_state": "cached",
                "freshness_label": "最近可用",
                "no_advice_boundary": True,
            },
        )

        serialized_lineage = json.dumps(lineage, ensure_ascii=False)
        self.assertNotIn("source_confidence", lineage)
        self.assertNotIn("observation_only", lineage)
        self.assertNotIn("score_grade_allowed", lineage)
        self.assertNotIn("providerObservation", serialized_lineage)
        self.assertNotIn("rawDiagnostics", serialized_lineage)
        self.assertNotIn("reasonCodes", serialized_lineage)
        self.assertNotIn("sourceAuthorityAllowed", serialized_lineage)
        self.assertNotIn("scoreContributionAllowed", serialized_lineage)
        self.assertNotIn("internal-provider", serialized_lineage)
        _assert_no_forbidden_consumer_response_fields(list_resp.json())

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
        item = list_resp.json()["items"][0]
        self.assertEqual(item["symbol_status"], "symbol_unknown")
        self.assertEqual(item["research_status"], "symbol_unknown")
        self.assertEqual(item["data_quality"], "no_evidence")
        self.assertEqual(item["evidence_status"], "no_evidence")
        self.assertFalse(item["notes_available"])
        self.assertFalse(item["user_note_present"])
        _assert_safe_watchlist_research_context(item)

    def test_watchlist_research_context_reports_unsupported_market_without_rejecting_legacy_rows(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        with self.db.get_session() as session:
            session.add(
                UserWatchlistItem(
                    owner_id="user-1",
                    symbol="AAPL",
                    market="cn",
                    source="scanner",
                    notes="kept as user note",
                )
            )
            session.commit()

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        item = list_resp.json()["items"][0]
        self.assertEqual(item["symbol_status"], "unsupported_market")
        self.assertEqual(item["research_status"], "unsupported_market")
        self.assertEqual(item["data_quality"], "no_evidence")
        self.assertEqual(item["evidence_status"], "no_evidence")
        self.assertTrue(item["notes_available"])
        self.assertTrue(item["user_note_present"])
        _assert_safe_watchlist_research_context(item)

    def test_watchlist_research_context_sanitizes_raw_failure_details(self) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _make_user("user-1", "alice")

        with self.db.get_session() as session:
            session.add(
                UserWatchlistItem(
                    owner_id="user-1",
                    symbol="NVDA",
                    market="us",
                    source="scanner",
                    score_status="data_failed",
                    score_error=(
                        "Traceback from https://provider.example/query?token=secret "
                        "sourceType=provider_runtime trustLevel=internal reasonCode=raw_provider_error "
                        "target price and predicted return unavailable"
                    ),
                )
            )
            session.commit()

        list_resp = self.client.get("/api/v1/watchlist/items")
        self.assertEqual(list_resp.status_code, 200)
        payload = list_resp.json()
        item = payload["items"][0]
        self.assertEqual(item["symbol_status"], "symbol_unknown")
        self.assertEqual(item["research_status"], "unavailable")
        self.assertEqual(item["data_quality"], "unavailable")
        self.assertEqual(item["evidence_status"], "unavailable")
        self.assertEqual(item["score_error"], "Watchlist research context is temporarily unavailable.")
        _assert_safe_watchlist_research_context(item)
        _assert_no_forbidden_consumer_response_fields(payload)
