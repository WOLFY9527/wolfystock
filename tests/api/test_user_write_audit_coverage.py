# -*- coding: utf-8 -*-
"""Default INFO audit coverage for consumer user write actions."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

import src.auth as auth
from api.app import create_app
from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import admin_logs
from api.v1.endpoints import agent as agent_endpoint
from api.v1.endpoints import portfolio as portfolio_endpoint
from api.v1.endpoints import user_alerts as user_alerts_endpoint
from api.v1.endpoints import watchlist as watchlist_endpoint
from src.config import Config
from src.storage import DatabaseManager


FORBIDDEN_AUDIT_MARKERS = (
    "password",
    "initialPassword",
    "password_hash",
    "pbkdf2",
    "bcrypt",
    "argon2",
    "cookie",
    "session_token",
    "api_key",
    "RAW_TOKEN",
    "token=RAW_TOKEN",
    "secret",
    "alice@example.com",
    "raw request body",
    "request_body",
    "Traceback",
    "https://provider.example.invalid",
    "alice",
    "Alice",
    "raw-agent-question-must-not-leak",
    "raw-alert-note-must-not-leak",
    "raw-account-name-must-not-leak",
)


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


def _user(user_id: str = "user-1", username: str = "alice") -> CurrentUser:
    return CurrentUser(
        user_id=user_id,
        username=username,
        display_name=username.title(),
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id=f"session-{user_id}",
    )


def _admin() -> CurrentUser:
    return CurrentUser(
        user_id="admin-1",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=("ops:logs:read",),
    )


class UserWriteAuditCoverageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "user_write_audit.db"
        self._previous_admin_auth_enabled = os.environ.get("ADMIN_AUTH_ENABLED")
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
        DatabaseManager.reset_instance()
        self.app = create_app(static_dir=self.data_dir / "empty-static")
        self.client = TestClient(self.app)
        self.db = DatabaseManager.get_instance()
        self.db.create_or_update_app_user(user_id="user-1", username="alice", role="user")
        self._override_current_user(_user())

    def _override_current_user(self, current_user: CurrentUser) -> None:
        for dependency in (
            get_current_user,
            portfolio_endpoint.get_current_user,
            user_alerts_endpoint.get_current_user,
            agent_endpoint.get_current_user,
            watchlist_endpoint.get_current_user,
        ):
            self.app.dependency_overrides[dependency] = lambda current_user=current_user: current_user

    def _override_missing_current_user(self) -> None:
        def missing_current_user() -> None:
            raise HTTPException(
                status_code=401,
                detail={"error": "unauthorized", "message": "Login required"},
            )

        for dependency in (
            get_current_user,
            portfolio_endpoint.get_current_user,
            user_alerts_endpoint.get_current_user,
            agent_endpoint.get_current_user,
            watchlist_endpoint.get_current_user,
        ):
            self.app.dependency_overrides[dependency] = missing_current_user

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()
        self.client.close()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        _reset_auth_globals()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        if self._previous_admin_auth_enabled is None:
            os.environ.pop("ADMIN_AUTH_ENABLED", None)
        else:
            os.environ["ADMIN_AUTH_ENABLED"] = self._previous_admin_auth_enabled
        self.temp_dir.cleanup()

    def _admin_business_events(self, event_type: str):
        payload = admin_logs.list_execution_logs_root(
            category="user_action",
            query=event_type,
            since="",
            _=_admin(),
        )
        return [item for item in payload.items if item.eventType == event_type]

    def _admin_sessions(self, event_type: str):
        payload = admin_logs.list_execution_log_sessions(
            min_level="INFO",
            category="user_action",
            task_id=event_type,
            since="",
            _=_admin(),
        )
        return payload.items

    def _assert_audit_safe(self, event_type: str) -> None:
        text = json.dumps(
            {
                "business_events": [item.model_dump() for item in self._admin_business_events(event_type)],
                "sessions": [item.model_dump() for item in self._admin_sessions(event_type)],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        for marker in FORBIDDEN_AUDIT_MARKERS:
            self.assertNotIn(marker, text)
        return text

    def _assert_audit_actor_identity(
        self,
        task_id: str,
        *,
        username_retained: bool = False,
    ) -> None:
        rows, total = self.db.list_execution_log_sessions(task_id=task_id, limit=10)
        self.assertEqual(total, 1)
        meta = rows[0]["summary"]["meta"]
        self.assertEqual(meta["actor_user_id"], "user-1")
        self.assertEqual(meta["actor_role"], "user")
        self.assertEqual(meta["actor_type"], "user")
        if username_retained:
            self.assertEqual(meta["actor_username"], "alice")
            self.assertEqual(meta["actor_display"], "Alice")
            self.assertEqual(meta["actor_session_id"], "session-user-1")
        else:
            self.assertIsNone(meta["actor_username"])
            self.assertIsNone(meta["actor_display"])
            self.assertIsNone(meta["actor_session_id"])

    def test_portfolio_account_write_is_visible_in_default_info_user_action_audit(self) -> None:
        response = self.client.post(
            "/api/v1/portfolio/accounts",
            json={
                "name": "raw-account-name-must-not-leak",
                "broker": "Demo",
                "market": "us",
                "base_currency": "USD",
            },
        )
        self.assertEqual(response.status_code, 200)

        events = self._admin_business_events("portfolio.account_created")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].category, "user_action")
        self.assertEqual(events[0].eventType, "portfolio.account_created")
        self.assertEqual(events[0].status, "success")
        self.assertEqual(events[0].metadata["target_type"], "portfolio_account")
        self.assertEqual(events[0].metadata["market"], "US")

        sessions = self._admin_sessions("portfolio.account_created")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].readable_summary["log_level"], "INFO")
        self.assertEqual(sessions[0].readable_summary["log_category"], "user_action")
        self._assert_audit_safe("portfolio.account_created")
        self._assert_audit_actor_identity("portfolio.account_created")

    def test_alert_rule_write_is_visible_in_default_info_user_action_audit(self) -> None:
        response = self.client.post(
            "/api/v1/user-alerts/rules",
            json={
                "symbol": "nvda",
                "direction": "above",
                "thresholdPrice": 125.5,
                "enabled": True,
                "note": "raw-alert-note-must-not-leak",
            },
        )
        self.assertEqual(response.status_code, 200)

        events = self._admin_business_events("alert.rule_created")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].category, "user_action")
        self.assertEqual(events[0].eventType, "alert.rule_created")
        self.assertEqual(events[0].metadata["symbol"], "NVDA")
        self.assertEqual(events[0].metadata["target_type"], "alert_rule")

        sessions = self._admin_sessions("alert.rule_created")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].readable_summary["log_level"], "INFO")
        self._assert_audit_safe("alert.rule_created")
        self._assert_audit_actor_identity("alert.rule_created")

    def test_agent_chat_write_is_visible_in_default_info_user_action_audit(self) -> None:
        def _chat(*, message, session_id, context, owner_id):
            self.db.save_conversation_message(session_id, "user", message, owner_id=owner_id)
            return SimpleNamespace(success=True, content="ok", error=None)

        executor = SimpleNamespace(chat=_chat)
        request = agent_endpoint.ChatRequest(
            message="raw-agent-question-must-not-leak token=RAW_TOKEN",
            skills=["bull_trend"],
            context={"providerUrl": "https://provider.example.invalid/path"},
        )

        with patch("api.v1.endpoints.agent.get_config", return_value=SimpleNamespace(is_agent_available=lambda: True)), patch(
            "api.v1.endpoints.agent._build_executor",
            return_value=executor,
        ):
            payload = asyncio.run(agent_endpoint.agent_chat(request, current_user=_user())).model_dump()

        self.assertTrue(payload["success"])
        raw_agent_session_id = payload["session_id"]
        events = self._admin_business_events("agent.request_created")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].category, "user_action")
        self.assertEqual(events[0].eventType, "agent.request_created")
        self.assertEqual(events[0].metadata["target_type"], "agent_session")
        self.assertEqual(events[0].metadata["skill_count"], 1)
        self.assertTrue(events[0].metadata["new_session"])

        sessions = self._admin_sessions("agent.request_created")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].readable_summary["log_level"], "INFO")
        audit_text = self._assert_audit_safe("agent.request_created")
        self.assertNotIn(raw_agent_session_id, audit_text)
        self._assert_audit_actor_identity("agent.request_created")

    def test_watchlist_write_preserves_route_response_and_audit_actor_identity(self) -> None:
        response = self.client.post(
            "/api/v1/watchlist/items",
            json={"symbol": "AAPL", "market": "us", "source": "scanner"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["symbol"], "AAPL")
        self._assert_audit_actor_identity("portfolio:watchlist_add", username_retained=True)

    def test_missing_current_user_cannot_reach_authenticated_actor_route(self) -> None:
        self._override_missing_current_user()

        response = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Denied", "broker": "Demo", "market": "us", "base_currency": "USD"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "unauthorized")
        _, total = self.db.list_execution_log_sessions(task_id="portfolio.account_created", limit=10)
        self.assertEqual(total, 0)

    def test_ordinary_user_cannot_read_admin_audit_route(self) -> None:
        response = self.client.get("/api/v1/admin/logs", params={"since": ""})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "admin_required")

    def test_existing_ownership_and_auth_boundaries_remain_unchanged(self) -> None:
        self._override_current_user(
            CurrentUser(
                user_id="anonymous",
                username="anonymous",
                display_name=None,
                role="anonymous",
                is_admin=False,
                is_authenticated=False,
                transitional=False,
                auth_enabled=True,
            )
        )
        anonymous = self.client.post(
            "/api/v1/user-alerts/rules",
            json={"symbol": "AAPL", "direction": "above", "thresholdPrice": 100},
        )
        self.assertEqual(anonymous.status_code, 401)

        self._override_current_user(_user("user-1", "alice"))
        created = self.client.post(
            "/api/v1/user-alerts/rules",
            json={"symbol": "AAPL", "direction": "above", "thresholdPrice": 100},
        ).json()

        self._override_current_user(_user("user-2", "bob"))
        self.db.create_or_update_app_user(user_id="user-2", username="bob", role="user")
        unrelated = self.client.patch(f"/api/v1/user-alerts/rules/{created['id']}", json={"enabled": False})
        self.assertEqual(unrelated.status_code, 404)


if __name__ == "__main__":
    unittest.main()
