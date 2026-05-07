# -*- coding: utf-8 -*-
"""Real auth/session smoke coverage for admin API reachability."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.auth as auth
from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager


EXPECTED_SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
    "x-frame-options": "DENY",
}

FORBIDDEN_AUTH_LEAK_TERMS = (
    "real-smoke-pass",
    "wrong-real-smoke-pass",
    "password_hash",
    "passwordhash",
    "dsa_session",
    "session_id",
    "sessionid",
    "cookie",
    "api_key",
    "apikey",
    "totp",
    "recovery",
    "secret",
    ".env",
)


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

    def _assert_security_headers(self, response) -> None:
        headers = {key.lower(): value for key, value in response.headers.items()}
        for name, value in EXPECTED_SECURITY_HEADERS.items():
            self.assertEqual(headers.get(name), value)
        self.assertIn("permissions-policy", headers)
        self.assertIn("content-security-policy-report-only", headers)

    def _assert_no_auth_leaks(self, response, *, extra_forbidden=()) -> None:
        text = response.text.lower()
        for forbidden in FORBIDDEN_AUTH_LEAK_TERMS + tuple(extra_forbidden):
            self.assertNotIn(str(forbidden).lower(), text)

    def test_real_bootstrap_session_reaches_admin_route_and_logged_out_fails_closed(self) -> None:
        logged_out_admin = self.client.get("/api/v1/admin/users")
        self.assertEqual(logged_out_admin.status_code, 401)
        self._assert_security_headers(logged_out_admin)
        self._assert_no_auth_leaks(logged_out_admin)

        login = self.client.post(
            "/api/v1/auth/login",
            json={"password": "real-smoke-pass", "passwordConfirm": "real-smoke-pass"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn("dsa_session", self.client.cookies)
        self._assert_security_headers(login)
        set_cookie = login.headers.get("set-cookie", "")
        self.assertIn("dsa_session=", set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=lax", set_cookie)
        self.assertIn("Path=/", set_cookie)
        self.assertIn("Max-Age=", set_cookie)
        self.assertNotIn("Secure", set_cookie)

        status = self.client.get("/api/v1/auth/status")
        self.assertEqual(status.status_code, 200)
        self._assert_security_headers(status)
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
        self._assert_security_headers(admin_users)
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
        self._assert_security_headers(logout)
        logout_cookie = logout.headers.get("set-cookie", "")
        self.assertIn("dsa_session=", logout_cookie)
        self.assertIn("Max-Age=0", logout_cookie)
        self.assertIn("HttpOnly", logout_cookie)
        self.assertIn("SameSite=lax", logout_cookie)

        logged_out_status = self.client.get("/api/v1/auth/status")
        self.assertEqual(logged_out_status.status_code, 200)
        self._assert_security_headers(logged_out_status)
        self.assertFalse(logged_out_status.json()["loggedIn"])

        logged_out_again = self.client.get("/api/v1/admin/users")
        self.assertEqual(logged_out_again.status_code, 401)
        self._assert_security_headers(logged_out_again)
        self._assert_no_auth_leaks(logged_out_again)

    def test_real_failed_login_and_unauthenticated_admin_errors_are_sanitized_without_session_cookie(self) -> None:
        bootstrap = self.client.post(
            "/api/v1/auth/login",
            json={"password": "real-smoke-pass", "passwordConfirm": "real-smoke-pass"},
        )
        self.assertEqual(bootstrap.status_code, 200)
        self.client.post("/api/v1/auth/logout")

        failed_login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrong-real-smoke-pass"},
        )
        self.assertEqual(failed_login.status_code, 401)
        self.assertNotIn("set-cookie", {key.lower(): value for key, value in failed_login.headers.items()})
        self._assert_security_headers(failed_login)
        self._assert_no_auth_leaks(failed_login)

        admin_response = self.client.get(
            "/api/v1/admin/users",
            headers={
                "Authorization": "Bearer raw-admin-token",
                "Cookie": "dsa_session=raw-session-id",
            },
        )
        self.assertIn(admin_response.status_code, {401, 403})
        self._assert_security_headers(admin_response)
        self._assert_no_auth_leaks(
            admin_response,
            extra_forbidden=("raw-admin-token", "raw-session-id", "authorization", "bearer"),
        )

    def test_production_https_unauthenticated_admin_error_includes_hsts(self) -> None:
        with patch.dict(os.environ, {"APP_ENV": "production", "TRUST_X_FORWARDED_FOR": "true"}, clear=False):
            response = self.client.get(
                "/api/v1/admin/users",
                headers={"X-Forwarded-Proto": "https"},
            )

        self.assertEqual(response.status_code, 401)
        self._assert_security_headers(response)
        self.assertEqual(response.headers.get("strict-transport-security"), "max-age=31536000; includeSubDomains")
        self._assert_no_auth_leaks(response)

    def test_production_admin_csrf_denial_has_security_headers_and_no_session_leak(self) -> None:
        login = self.client.post(
            "/api/v1/auth/login",
            json={"password": "real-smoke-pass", "passwordConfirm": "real-smoke-pass"},
        )
        self.assertEqual(login.status_code, 200)

        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=False):
            response = self.client.post(
                "/api/v1/admin/users/bootstrap-admin/disable",
                json={"reason": "csrf launch evidence", "confirm": "DISABLE"},
                headers={"Origin": "https://evil.example.test"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "csrf_origin_forbidden")
        self._assert_security_headers(response)
        self._assert_no_auth_leaks(response)


if __name__ == "__main__":
    unittest.main()
