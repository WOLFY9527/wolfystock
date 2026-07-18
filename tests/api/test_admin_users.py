# -*- coding: utf-8 -*-
"""Admin user directory API contract tests."""

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
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID
from src.storage import AppUser, AppUserSession, DatabaseManager
from tests.api.route_table_helpers import iter_effective_api_routes

FORBIDDEN_PRIVACY_EXPORT_MARKERS = (
    "password",
    "passwordHash",
    "password_hash",
    "initialPassword",
    "passwordDelivery",
    "sessionToken",
    "session_token",
    "pbkdf2:admin-secret-hash",
    "pbkdf2:user-secret-hash",
    "raw-active-session-token",
    "raw-expired-session-token",
    "raw-revoked-session-token",
    "session_id",
    "sessionid",
    "cookie",
    "api_key",
    "apikey",
    "api-key",
    "totp-secret-ref",
    "mfaSecret",
    "mfa_secret",
    "rawMfaSecret",
    "raw_mfa_secret",
    "recoverySecret",
    "recovery_secret",
    "rawRecoverySecret",
    "raw_recovery_secret",
    "recovery-code-hash",
    "provider credential",
    "provider_credential",
    "broker credential",
    "dsn",
    "traceback",
    "stack trace",
)

FORBIDDEN_RESPONSE_KEYS = {
    "password",
    "passwordHash",
    "password_hash",
    "initialPassword",
    "sessionToken",
    "session_token",
    "cookie",
    "rawRecoverySecret",
    "raw_recovery_secret",
    "rawMfaSecret",
    "raw_mfa_secret",
    "mfaSecret",
    "mfa_secret",
}


def _admin_user(*, admin_capabilities: tuple[str, ...] = ("users:read",)) -> CurrentUser:
    return CurrentUser(
        user_id=BOOTSTRAP_ADMIN_USER_ID,
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        admin_capabilities=admin_capabilities,
    )


def _admin_without_users_read() -> CurrentUser:
    return _admin_user(admin_capabilities=("users:activity:read",))


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
    )


class AdminUsersApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._prior_admin_auth_enabled = os.environ.get("ADMIN_AUTH_ENABLED")
        os.environ["ADMIN_AUTH_ENABLED"] = "true"
        auth.refresh_auth_state()
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "admin_users.db"
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")

        from api.v1.endpoints import admin_users

        self.app = FastAPI()
        self.app.include_router(admin_users.router, prefix="/api/v1/admin")
        self.client_context = TestClient(self.app)
        self.client = self.client_context.__enter__()
        self.now = datetime.now()
        self._seed_users()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.app.dependency_overrides.clear()
        DatabaseManager.reset_instance()
        if self._prior_admin_auth_enabled is None:
            os.environ.pop("ADMIN_AUTH_ENABLED", None)
        else:
            os.environ["ADMIN_AUTH_ENABLED"] = self._prior_admin_auth_enabled
        auth.refresh_auth_state()
        self.temp_dir.cleanup()

    def _seed_users(self) -> None:
        self.db.create_or_update_app_user(
            user_id=BOOTSTRAP_ADMIN_USER_ID,
            username="admin",
            display_name="Admin",
            role="admin",
            password_hash="pbkdf2:admin-secret-hash",
            is_active=True,
        )
        self.db.create_or_update_app_user(
            user_id="user-1",
            username="alice",
            display_name="Alice Analyst",
            role="user",
            password_hash="pbkdf2:user-secret-hash",
            mfa_secret_ref="totp-secret-ref",
            mfa_recovery_codes_hash="recovery-code-hash",
            is_active=True,
        )
        self.db.create_or_update_app_user(
            user_id="user-2",
            username="bob",
            display_name="Bob Disabled",
            role="user",
            password_hash=None,
            is_active=False,
        )
        with self.db.get_session() as session:
            from src.storage import AppUserSession

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
                        session_id="raw-expired-session-token",
                        user_id="user-1",
                        created_at=self.now - timedelta(days=2),
                        last_seen_at=self.now - timedelta(days=1),
                        expires_at=self.now - timedelta(hours=1),
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

    def _as_admin(self) -> None:
        self.app.dependency_overrides[get_current_user] = _admin_user

    def _as_user(self) -> None:
        self.app.dependency_overrides[get_current_user] = _regular_user

    def _as_admin_without_users_read(self) -> None:
        self.app.dependency_overrides[get_current_user] = _admin_without_users_read

    @staticmethod
    def _json_text(response) -> str:
        return json.dumps(response.json(), ensure_ascii=False)

    def _assert_no_privacy_export_leaks(self, response) -> None:
        self._assert_no_forbidden_response_keys(response.json())
        text = self._json_text(response).lower()
        for marker in FORBIDDEN_PRIVACY_EXPORT_MARKERS:
            if marker == "password":
                continue
            self.assertNotIn(marker.lower(), text)

    def _assert_no_forbidden_response_keys(self, value) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                self.assertNotIn(key, FORBIDDEN_RESPONSE_KEYS)
                self._assert_no_forbidden_response_keys(child)
        elif isinstance(value, list):
            for child in value:
                self._assert_no_forbidden_response_keys(child)

    def _count(self, model) -> int:
        from sqlalchemy import func, select

        with self.db.get_session() as session:
            return int(session.execute(select(func.count()).select_from(model)).scalar() or 0)

    def test_admin_required_for_user_directory(self) -> None:
        unauthenticated = self.client.get("/api/v1/admin/users")
        self.assertEqual(unauthenticated.status_code, 401)

        self._as_user()
        forbidden = self.client.get("/api/v1/admin/users")
        self.assertEqual(forbidden.status_code, 403)

    def test_user_directory_requires_users_read_capability(self) -> None:
        self._as_admin_without_users_read()
        list_forbidden = self.client.get("/api/v1/admin/users")
        detail_forbidden = self.client.get("/api/v1/admin/users/user-1")

        self.assertEqual(list_forbidden.status_code, 403)
        self.assertEqual(detail_forbidden.status_code, 403)
        self.assertEqual(list_forbidden.json()["detail"]["error"], "admin_capability_required")
        self.assertEqual(detail_forbidden.json()["detail"]["error"], "admin_capability_required")
        self.assertNotIn("users:read", list_forbidden.text)
        self.assertNotIn("users:read", detail_forbidden.text)

        self._as_admin()
        list_allowed = self.client.get("/api/v1/admin/users")
        detail_allowed = self.client.get("/api/v1/admin/users/user-1")

        self.assertEqual(list_allowed.status_code, 200)
        self.assertEqual(detail_allowed.status_code, 200)

    def test_admin_can_list_users_with_filters_pagination_and_safe_projection(self) -> None:
        self._as_admin()
        response = self.client.get(
            "/api/v1/admin/users",
            params={"q": "ali", "role": "user", "active": "true", "limit": 1, "offset": 0},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["limit"], 1)
        self.assertFalse(payload["hasMore"])
        item = payload["items"][0]
        self.assertEqual(item["id"], "user-1")
        self.assertEqual(item["username"], "alice")
        self.assertEqual(item["passwordState"], "set")
        self.assertEqual(item["sessionSummary"]["activeCount"], 1)
        self.assertEqual(item["sessionSummary"]["expiredCount"], 1)
        self.assertEqual(item["sessionSummary"]["revokedCount"], 1)

        text = self._json_text(response)
        self.assertNotIn("password_hash", text)
        self.assertNotIn("pbkdf2:user-secret-hash", text)
        self.assertNotIn("raw-active-session-token", text)
        self.assertNotIn("cookie", text.lower())
        self.assertNotIn("api_key", text.lower())
        self.assertNotIn("secret", text.lower())

    def test_admin_user_lifecycle_fields_are_explicit_and_redacted(self) -> None:
        self._as_admin()

        list_response = self.client.get("/api/v1/admin/users", params={"sort": "username_asc"})
        detail_response = self.client.get("/api/v1/admin/users/user-1")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)

        items = {item["id"]: item for item in list_response.json()["items"]}
        active_user = items["user-1"]
        inactive_user = items["user-2"]
        for item in (active_user, inactive_user, detail_response.json()["user"]):
            self.assertIn("status", item)
            self.assertIn("role", item)
            self.assertIn("createdAt", item)
            self.assertIn("updatedAt", item)
            self.assertIn("lastSeenAt", item)
            self.assertIn("lifecycleState", item)
            self.assertNotIn("lastLoginAt", item)

        self.assertEqual(active_user["status"], "active")
        self.assertEqual(active_user["lifecycleState"], "active")
        self.assertEqual(inactive_user["status"], "inactive")
        self.assertEqual(inactive_user["lifecycleState"], "inactive")
        self.assertEqual(detail_response.json()["user"]["status"], "active")
        self.assertEqual(detail_response.json()["user"]["lifecycleState"], "active")

        self._assert_no_privacy_export_leaks(list_response)
        self._assert_no_privacy_export_leaks(detail_response)

    def test_endpoint_validates_neutral_service_dicts_into_existing_public_schema(self) -> None:
        self._as_admin()

        projected_user = {
            "id": "user-1",
            "username": "alice",
            "display_name": "Alice Analyst",
            "role": "user",
            "is_active": True,
            "created_at": "2026-05-10T10:00:00",
            "updated_at": "2026-05-11T10:00:00",
            "password_state": "set",
            "last_seen_at": "2026-05-12T09:30:00",
            "session_summary": {
                "active_count": 1,
                "expired_count": 1,
                "revoked_count": 1,
                "last_seen_at": "2026-05-12T09:30:00",
                "next_expires_at": "2026-05-12T12:30:00",
            },
            "risk_badges": [
                {
                    "code": "revoked_sessions_present",
                    "label": "Revoked sessions present",
                    "severity": "info",
                    "source": "session",
                }
            ],
            "links": {
                "self": "/api/v1/admin/users/user-1",
                "admin_logs": "/api/v1/admin/logs?user_id=user-1",
                "activity": "/api/v1/admin/users/user-1/activity",
                "portfolio": None,
                "analysis": None,
                "scanner": None,
                "backtest": None,
            },
        }
        projected_sessions = [
            {
                "session_handle": "sess_123456789abc",
                "status": "active",
                "created_at": "2026-05-12T07:30:00",
                "last_seen_at": "2026-05-12T09:30:00",
                "expires_at": "2026-05-12T12:30:00",
                "revoked_at": None,
            }
        ]

        from api.v1.endpoints import admin_users

        with patch.object(admin_users.AdminUserService, "list_users", return_value=([projected_user], 1)):
            list_response = self.client.get("/api/v1/admin/users")
        with patch.object(admin_users.AdminUserService, "get_user_detail", return_value=(projected_user, projected_sessions)):
            detail_response = self.client.get("/api/v1/admin/users/user-1")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)

        list_item = list_response.json()["items"][0]
        self.assertEqual(list_item["displayName"], "Alice Analyst")
        self.assertEqual(list_item["status"], "active")
        self.assertEqual(list_item["lifecycleState"], "active")
        self.assertEqual(list_item["isActive"], True)
        self.assertEqual(list_item["passwordState"], "set")
        self.assertEqual(list_item["sessionSummary"]["activeCount"], 1)
        self.assertEqual(list_item["sessionSummary"]["expiredCount"], 1)
        self.assertEqual(list_item["sessionSummary"]["revokedCount"], 1)
        self.assertEqual(list_item["riskBadges"][0]["code"], "revoked_sessions_present")
        self.assertEqual(list_item["links"]["adminLogs"], "/api/v1/admin/logs?user_id=user-1")

        detail_payload = detail_response.json()
        self.assertEqual(detail_payload["user"]["displayName"], "Alice Analyst")
        self.assertEqual(detail_payload["user"]["status"], "active")
        self.assertEqual(detail_payload["user"]["lifecycleState"], "active")
        self.assertEqual(detail_payload["sessions"][0]["sessionHandle"], "sess_123456789abc")
        self.assertEqual(detail_payload["sessions"][0]["status"], "active")
        self.assertEqual(detail_payload["dataLinks"]["activity"], "/api/v1/admin/users/user-1/activity")

    def test_user_detail_hides_raw_sessions_and_marks_inactive_unset_password(self) -> None:
        self._as_admin()
        response = self.client.get("/api/v1/admin/users/user-1")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["user"]["id"], "user-1")
        self.assertEqual(len(payload["sessions"]), 3)
        handles = [row["sessionHandle"] for row in payload["sessions"]]
        self.assertTrue(all(handle.startswith("sess_") for handle in handles))
        self.assertNotIn("raw-active-session-token", handles)

        text = self._json_text(response)
        self.assertNotIn("raw-active-session-token", text)
        self.assertNotIn("pbkdf2:user-secret-hash", text)
        self.assertNotIn("password_hash", text)
        self._assert_no_privacy_export_leaks(response)

        inactive = self.client.get("/api/v1/admin/users/user-2")
        self.assertEqual(inactive.status_code, 200)
        self.assertFalse(inactive.json()["user"]["isActive"])
        self.assertEqual(inactive.json()["user"]["passwordState"], "unset")

    def test_user_directory_privacy_export_projection_is_read_only_and_sanitized(self) -> None:
        self._as_admin()
        before_users = self._count(AppUser)
        before_sessions = self._count(AppUserSession)

        list_response = self.client.get("/api/v1/admin/users", params={"limit": 50})
        detail_response = self.client.get("/api/v1/admin/users/user-1", params={"include_sessions": "true"})
        active_sessions = self.client.get(
            "/api/v1/admin/users/user-1",
            params={"session_status": "active"},
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(active_sessions.status_code, 200)
        self.assertEqual(self._count(AppUser), before_users)
        self.assertEqual(self._count(AppUserSession), before_sessions)

        for response in (list_response, detail_response, active_sessions):
            self._assert_no_privacy_export_leaks(response)

        detail_payload = detail_response.json()
        self.assertEqual(detail_payload["user"]["links"]["portfolio"], None)
        self.assertEqual(detail_payload["user"]["links"]["analysis"], None)
        self.assertEqual(detail_payload["user"]["links"]["scanner"], None)
        self.assertEqual(detail_payload["user"]["links"]["backtest"], None)
        self.assertEqual(detail_payload["dataLinks"]["portfolio"], None)
        self.assertEqual(detail_payload["dataLinks"]["analysis"], None)
        self.assertEqual(detail_payload["dataLinks"]["scanner"], None)
        self.assertEqual(detail_payload["dataLinks"]["backtest"], None)

        user_routes = [
            route
            for route in iter_effective_api_routes(self.app.routes)
            if getattr(route, "path", "").startswith("/api/v1/admin/users")
        ]
        self.assertGreaterEqual(len(user_routes), 3)
        for route in user_routes:
            if getattr(route, "path", "") == "/api/v1/admin/users/onboard":
                self.assertTrue(set(getattr(route, "methods", set())) <= {"POST"})
            else:
                self.assertTrue(set(getattr(route, "methods", set())) <= {"GET"})

    def test_cross_user_admin_detail_attempt_is_denied_with_sanitized_error(self) -> None:
        self._as_user()

        response = self.client.get("/api/v1/admin/users/user-2")

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("user-2", self._json_text(response))
        self._assert_no_privacy_export_leaks(response)

    def test_destructive_user_delete_route_remains_unsupported_and_read_only(self) -> None:
        self._as_admin()
        before_users = self._count(AppUser)
        before_sessions = self._count(AppUserSession)

        response = self.client.delete("/api/v1/admin/users/user-1")

        self.assertEqual(response.status_code, 405)
        self.assertEqual(self._count(AppUser), before_users)
        self.assertEqual(self._count(AppUserSession), before_sessions)
        self._assert_no_privacy_export_leaks(response)

    def test_unknown_user_and_limit_validation(self) -> None:
        self._as_admin()
        missing = self.client.get("/api/v1/admin/users/no-such-user")
        self.assertEqual(missing.status_code, 404)

        over_limit = self.client.get("/api/v1/admin/users", params={"limit": 201})
        self.assertEqual(over_limit.status_code, 422)

    def test_list_sorting_is_stable_and_read_only(self) -> None:
        self._as_admin()
        before_users = self._count(AppUser)
        before_sessions = self._count(AppUserSession)

        response = self.client.get("/api/v1/admin/users", params={"sort": "username_asc"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["username"] for item in response.json()["items"]], ["admin", "alice", "bob"])
        self.assertEqual(self._count(AppUser), before_users)
        self.assertEqual(self._count(AppUserSession), before_sessions)

    def test_user_directory_does_not_expose_onboarding_secret_in_safe_projections(self) -> None:
        self.db.create_or_update_app_user(
            user_id="user-3",
            username="beta-user",
            display_name="Beta User",
            role="user",
            password_hash="pbkdf2:beta-secret-hash",
            is_active=True,
        )
        self._as_admin()

        list_response = self.client.get("/api/v1/admin/users", params={"q": "beta-user"})
        detail_response = self.client.get("/api/v1/admin/users/user-3")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        for response in (list_response, detail_response):
            self._assert_no_privacy_export_leaks(response)
            text = self._json_text(response)
            self.assertNotIn("beta-secret-hash", text)


if __name__ == "__main__":
    unittest.main()
