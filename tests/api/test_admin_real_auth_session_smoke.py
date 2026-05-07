# -*- coding: utf-8 -*-
"""Real auth/session smoke coverage for admin API reachability."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import src.auth as auth
from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._password_hash_value = None
    auth._rate_limit = {}
    auth._admin_reauth_markers = {}


class AdminRealAuthSessionSmokeTestCase(unittest.TestCase):
    """Narrow smoke for real login/session/admin-route behavior."""

    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.env_path.write_text(
            "STOCK_LIST=AAPL\nGEMINI_API_KEY=test\nADMIN_AUTH_ENABLED=true\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.data_dir / "real_auth_smoke.db")
        Config.reset_instance()
        DatabaseManager.reset_instance()

        static_dir = self.data_dir / "empty-static"
        static_dir.mkdir()
        self.client = TestClient(create_app(static_dir=static_dir))

    def tearDown(self) -> None:
        self.client.close()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        _reset_auth_globals()
        self.temp_dir.cleanup()

    def test_real_bootstrap_session_reaches_admin_route_and_logged_out_fails_closed(self) -> None:
        logged_out_admin = self.client.get("/api/v1/admin/users")
        self.assertEqual(logged_out_admin.status_code, 401)

        login = self.client.post(
            "/api/v1/auth/login",
            json={"password": "real-smoke-pass", "passwordConfirm": "real-smoke-pass"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn("dsa_session", self.client.cookies)

        status = self.client.get("/api/v1/auth/status")
        self.assertEqual(status.status_code, 200)
        status_payload = status.json()
        self.assertTrue(status_payload["authEnabled"])
        self.assertTrue(status_payload["loggedIn"])
        current_user = status_payload["currentUser"]
        self.assertEqual(current_user["username"], "admin")
        self.assertTrue(current_user["isAdmin"])
        self.assertTrue(current_user["isAuthenticated"])
        self.assertIsInstance(current_user["adminCapabilities"], list)
        self.assertGreater(len(current_user["adminCapabilities"]), 0)
        self.assertIn("users:read", current_user["adminCapabilities"])
        self.assertTrue(current_user["canReadUsers"])
        self.assertTrue(current_user["canReadSystemConfig"])
        capability_text = json.dumps(current_user["adminCapabilities"], sort_keys=True).lower()
        for forbidden in ("password", "session", "cookie", "token", "api_key", "apikey", "secret"):
            self.assertNotIn(forbidden, capability_text)

        admin_users = self.client.get("/api/v1/admin/users")
        self.assertEqual(admin_users.status_code, 200)
        self.assertGreaterEqual(admin_users.json()["total"], 1)

        serialized = json.dumps(
            {"status": status_payload, "adminUsers": admin_users.json()},
            ensure_ascii=False,
            sort_keys=True,
        ).lower()
        for forbidden in (
            "real-smoke-pass",
            "password_hash",
            "passwordhash",
            "dsa_session",
            "session_id",
            "sessionid",
            "api_key",
            "apikey",
            "secret",
            ".env",
        ):
            self.assertNotIn(forbidden, serialized)

        logout = self.client.post("/api/v1/auth/logout")
        self.assertEqual(logout.status_code, 204)

        logged_out_status = self.client.get("/api/v1/auth/status")
        self.assertEqual(logged_out_status.status_code, 200)
        self.assertFalse(logged_out_status.json()["loggedIn"])

        logged_out_again = self.client.get("/api/v1/admin/users")
        self.assertEqual(logged_out_again.status_code, 401)


if __name__ == "__main__":
    unittest.main()
