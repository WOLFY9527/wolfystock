# -*- coding: utf-8 -*-
"""Admin user directory API contract tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID
from src.storage import AppUser, AppUserSession, DatabaseManager


def _admin_user() -> CurrentUser:
    return CurrentUser(
        user_id=BOOTSTRAP_ADMIN_USER_ID,
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
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
    )


class AdminUsersApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "admin_users.db"
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")

        from api.v1.endpoints import admin_users

        self.app = FastAPI()
        self.app.include_router(admin_users.router, prefix="/api/v1/admin")
        self.client = TestClient(self.app)
        self.now = datetime.now()
        self._seed_users()

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        DatabaseManager.reset_instance()
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

    @staticmethod
    def _json_text(response) -> str:
        return json.dumps(response.json(), ensure_ascii=False)

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

        inactive = self.client.get("/api/v1/admin/users/user-2")
        self.assertEqual(inactive.status_code, 200)
        self.assertFalse(inactive.json()["user"]["isActive"])
        self.assertEqual(inactive.json()["user"]["passwordState"], "unset")

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


if __name__ == "__main__":
    unittest.main()
