# -*- coding: utf-8 -*-
"""Admin account security API contract tests."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.auth as auth
from api.deps import CurrentUser, get_current_user
from src.auth import hash_password_for_storage
from src.admin_rbac import SUPPORT_ADMIN_ROLE
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID
from src.storage import AdminUserRole, AppUserSession, DatabaseManager, ExecutionLogSession


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


def _admin_user(user_id: str = BOOTSTRAP_ADMIN_USER_ID) -> CurrentUser:
    return CurrentUser(
        user_id=user_id,
        username="admin" if user_id == BOOTSTRAP_ADMIN_USER_ID else user_id,
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="admin-session-raw",
    )


def _regular_user() -> CurrentUser:
    return CurrentUser(
        user_id="user-1",
        username="alice",
        display_name="Alice",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="user-session-raw",
    )


class AdminSecurityApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "admin_security.db"
        self.data_dir = Path(self.temp_dir.name) / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")

        from api.v1.endpoints import admin_security, auth as auth_endpoint

        self.app = FastAPI()
        self.app.include_router(admin_security.router, prefix="/api/v1/admin")
        self.app.include_router(auth_endpoint.router, prefix="/api/v1/auth")
        self.client = TestClient(self.app)
        self.now = datetime.now()
        self._seed_users()

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        DatabaseManager.reset_instance()
        _reset_auth_globals()
        self.temp_dir.cleanup()

    def _seed_users(self) -> None:
        self.user_password_hash = hash_password_for_storage("userpass123")
        self.db.create_or_update_app_user(
            user_id=BOOTSTRAP_ADMIN_USER_ID,
            username="admin",
            display_name="Admin",
            role="admin",
            password_hash="pbkdf2:admin-secret-hash",
            is_active=True,
        )
        self.db.create_or_update_app_user(
            user_id="admin-2",
            username="admin2",
            display_name="Admin Two",
            role="admin",
            password_hash="pbkdf2:admin2-secret-hash",
            is_active=True,
        )
        self.db.create_or_update_app_user(
            user_id="support-admin-1",
            username="support-admin",
            display_name="Support Admin",
            role="admin",
            password_hash="pbkdf2:support-secret-hash",
            is_active=True,
        )
        self.db.create_or_update_app_user(
            user_id="user-1",
            username="alice",
            display_name="Alice Analyst",
            role="user",
            password_hash=self.user_password_hash,
            is_active=True,
        )
        with self.db.get_session() as session:
            session.add(AdminUserRole(user_id="support-admin-1", role_key=SUPPORT_ADMIN_ROLE))
            session.add_all(
                [
                    AppUserSession(
                        session_id="raw-active-session-token",
                        user_id="user-1",
                        created_at=self.now - timedelta(hours=2),
                        last_seen_at=self.now - timedelta(minutes=5),
                        expires_at=self.now + timedelta(hours=3),
                        revoked_at=None,
                    ),
                    AppUserSession(
                        session_id="raw-active-session-token-2",
                        user_id="user-1",
                        created_at=self.now - timedelta(hours=1),
                        last_seen_at=self.now - timedelta(minutes=3),
                        expires_at=self.now + timedelta(hours=4),
                        revoked_at=None,
                    ),
                    AppUserSession(
                        session_id="raw-revoked-session-token",
                        user_id="user-1",
                        created_at=self.now - timedelta(days=3),
                        last_seen_at=self.now - timedelta(days=2),
                        expires_at=self.now + timedelta(hours=1),
                        revoked_at=self.now - timedelta(days=1),
                    ),
                ]
            )
            session.commit()

    def _as_admin(self, user_id: str = BOOTSTRAP_ADMIN_USER_ID) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: _admin_user(user_id)

    def _as_user(self) -> None:
        self.app.dependency_overrides[get_current_user] = _regular_user

    @staticmethod
    def _json_text(response) -> str:
        return json.dumps(response.json(), ensure_ascii=False)

    def _user_is_active(self, user_id: str) -> bool:
        row = self.db.get_app_user(user_id)
        return bool(getattr(row, "is_active", False))

    def _active_session_count(self, user_id: str) -> int:
        return sum(1 for row in self.db.list_app_user_sessions(user_id) if getattr(row, "revoked_at", None) is None)

    def _audit_rows(self, action: str) -> list[ExecutionLogSession]:
        with self.db.get_session() as session:
            return (
                session.query(ExecutionLogSession)
                .filter(ExecutionLogSession.task_id == action)
                .order_by(ExecutionLogSession.started_at.asc())
                .all()
            )

    def _assert_safe_payload(self, response) -> None:
        text = self._json_text(response)
        forbidden = [
            "password_hash",
            "pbkdf2:admin-secret-hash",
            "pbkdf2:admin2-secret-hash",
            "pbkdf2:support-secret-hash",
            self.user_password_hash,
            "raw-active-session-token",
            "raw-active-session-token-2",
            "raw-revoked-session-token",
            "admin-session-raw",
            "user-session-raw",
            "cookie",
            "token",
            "api_key",
            "secret",
            "reset",
        ]
        for needle in forbidden:
            self.assertNotIn(str(needle), text)

    def _assert_safe_audit(self, action: str, *, expected_status: str) -> None:
        rows = self._audit_rows(action)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].overall_status, expected_status)
        text = json.dumps(rows[0].summary_json, ensure_ascii=False)
        text += json.dumps(self.db.get_execution_log_session_detail(rows[0].session_id), ensure_ascii=False)
        self.assertIn("user-1", text)
        self.assertIn("admin", text)
        self.assertNotIn("raw-active-session-token", text)
        self.assertNotIn("raw-active-session-token-2", text)
        self.assertNotIn("admin-session-raw", text)
        self.assertNotIn("password_hash", text)
        self.assertNotIn("pbkdf2", text)
        self.assertNotIn("cookie", text.lower())
        self.assertNotIn("token", text.lower())
        self.assertNotIn("api_key", text.lower())
        self.assertNotIn("secret", text.lower())
        self.assertNotIn("request_body", text.lower())

    def test_admin_required_for_security_actions(self) -> None:
        unauthenticated = self.client.post(
            "/api/v1/admin/users/user-1/disable",
            json={"reason": "support request", "confirm": "DISABLE"},
        )
        self.assertEqual(unauthenticated.status_code, 401)

        self._as_user()
        forbidden = self.client.post(
            "/api/v1/admin/users/user-1/disable",
            json={"reason": "support request", "confirm": "DISABLE"},
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_admin_without_security_write_capability_is_denied_safely(self) -> None:
        self._as_admin("support-admin-1")

        response = self.client.post(
            "/api/v1/admin/users/user-1/disable",
            json={"reason": "support request", "confirm": "DISABLE"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["error"], "admin_capability_required")
        self.assertTrue(self._user_is_active("user-1"))
        self.assertEqual(self._active_session_count("user-1"), 2)
        self._assert_safe_payload(response)

    def test_admin_can_disable_target_and_optionally_revoke_sessions(self) -> None:
        self._as_admin()
        response = self.client.post(
            "/api/v1/admin/users/user-1/disable",
            json={"reason": "confirmed compromise report", "confirm": "DISABLE", "revokeSessions": True},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["targetUserId"], "user-1")
        self.assertEqual(payload["action"], "disable")
        self.assertEqual(payload["status"], "completed")
        self.assertTrue(payload["changed"])
        self.assertEqual(payload["sessionsRevoked"], 2)
        self.assertFalse(self._user_is_active("user-1"))
        self.assertEqual(self._active_session_count("user-1"), 0)
        self._assert_safe_payload(response)
        self._assert_safe_audit("admin_security.account_disabled", expected_status="completed")

    def test_admin_can_enable_disabled_user(self) -> None:
        self.db.create_or_update_app_user(
            user_id="user-1",
            username="alice",
            display_name="Alice Analyst",
            role="user",
            password_hash=self.user_password_hash,
            is_active=False,
        )
        self._as_admin()

        response = self.client.post(
            "/api/v1/admin/users/user-1/enable",
            json={"reason": "support review complete", "confirm": "ENABLE"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["changed"])
        self.assertTrue(self._user_is_active("user-1"))
        self.assertEqual(response.json()["sessionsRevoked"], 0)
        self._assert_safe_payload(response)
        self._assert_safe_audit("admin_security.account_enabled", expected_status="completed")

    def test_admin_can_revoke_target_sessions_without_raw_session_ids(self) -> None:
        self._as_admin()
        response = self.client.post(
            "/api/v1/admin/users/user-1/revoke-sessions",
            json={"reason": "device reported lost", "confirm": "REVOKE_SESSIONS", "scope": "all"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sessionsRevoked"], 2)
        self.assertEqual(self._active_session_count("user-1"), 0)
        self._assert_safe_payload(response)
        self._assert_safe_audit("admin_security.sessions_revoked", expected_status="completed")

    def test_self_disable_and_last_admin_disable_are_blocked_and_audited(self) -> None:
        self._as_admin()
        self_disable = self.client.post(
            f"/api/v1/admin/users/{BOOTSTRAP_ADMIN_USER_ID}/disable",
            json={"reason": "mistake", "confirm": "DISABLE"},
        )
        self.assertEqual(self_disable.status_code, 403)
        self.assertIn("self", self_disable.json()["detail"]["error"])

        self.db.create_or_update_app_user(
            user_id="admin-2",
            username="admin2",
            display_name="Admin Two",
            role="admin",
            password_hash="pbkdf2:admin2-secret-hash",
            is_active=False,
        )
        self.db.create_or_update_app_user(
            user_id="support-admin-1",
            username="support-admin",
            display_name="Support Admin",
            role="admin",
            password_hash="pbkdf2:support-secret-hash",
            is_active=False,
        )
        self._as_admin(user_id="admin-2")
        last_admin = self.client.post(
            f"/api/v1/admin/users/{BOOTSTRAP_ADMIN_USER_ID}/disable",
            json={"reason": "bad request", "confirm": "DISABLE"},
        )
        self.assertEqual(last_admin.status_code, 409)
        self.assertIn("last_admin", last_admin.json()["detail"]["error"])

        rows = self._audit_rows("admin_security.account_disabled")
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row.overall_status == "failed" for row in rows))

    def test_confirmation_reason_and_target_validation(self) -> None:
        self._as_admin()
        missing_reason = self.client.post(
            "/api/v1/admin/users/user-1/disable",
            json={"confirm": "DISABLE"},
        )
        self.assertEqual(missing_reason.status_code, 422)

        wrong_confirm = self.client.post(
            "/api/v1/admin/users/user-1/disable",
            json={"reason": "support request", "confirm": "WRONG"},
        )
        self.assertEqual(wrong_confirm.status_code, 400)

        missing_user = self.client.post(
            "/api/v1/admin/users/no-such-user/enable",
            json={"reason": "support request", "confirm": "ENABLE"},
        )
        self.assertEqual(missing_user.status_code, 404)

        bad_scope = self.client.post(
            "/api/v1/admin/users/user-1/revoke-sessions",
            json={"reason": "support request", "confirm": "REVOKE_SESSIONS", "scope": "one"},
        )
        self.assertEqual(bad_scope.status_code, 400)

    def test_disabled_user_cannot_login(self) -> None:
        self.db.create_or_update_app_user(
            user_id="user-1",
            username="alice",
            display_name="Alice Analyst",
            role="user",
            password_hash=self.user_password_hash,
            is_active=False,
        )

        with patch.dict(os.environ, {"DATABASE_PATH": str(self.db_path)}, clear=False), patch.object(
            auth, "_get_data_dir", return_value=self.data_dir
        ), patch.object(auth, "_is_auth_enabled_from_env", return_value=True):
            auth._auth_enabled = True
            response = self.client.post(
                "/api/v1/auth/login",
                json={"username": "alice", "password": "userpass123"},
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "invalid_login")
        self.assertEqual(self._active_session_count("user-1"), 2)


if __name__ == "__main__":
    unittest.main()
