# -*- coding: utf-8 -*-
"""Focused tests for public auth/session security hardening."""

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
from api.middlewares.auth import add_auth_middleware
from src.auth import hash_password_for_storage
from src.storage import AppUserSession, DatabaseManager, ExecutionLogSession


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._password_hash_value = None
    auth._rate_limit = {}
    auth._admin_reauth_markers = {}
    try:
        from api.middlewares.public_abuse_limiter import reset_public_api_abuse_limiter_state
    except ModuleNotFoundError:
        return
    reset_public_api_abuse_limiter_state()


class AuthSecurityHardeningTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_dir = self.root / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "security.db"
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")

        from api.v1.endpoints import admin_security, analysis as analysis_endpoint, auth as auth_endpoint

        self.app = FastAPI()
        self.app.include_router(auth_endpoint.router, prefix="/api/v1/auth")
        self.app.include_router(admin_security.router, prefix="/api/v1/admin")
        self.app.include_router(analysis_endpoint.router, prefix="/api/v1/analysis")
        add_auth_middleware(self.app)
        self.client = TestClient(self.app)

        self.env = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": str(self.db_path),
                "ADMIN_AUTH_ENABLED": "true",
                "AUTH_RATE_LIMIT_MAX_FAILURES": "2",
                "AUTH_RATE_LIMIT_WINDOW_SECONDS": "300",
                "AUTH_ACCOUNT_RATE_LIMIT_MAX_FAILURES": "2",
                "AUTH_ADMIN_RATE_LIMIT_MAX_FAILURES": "2",
                "ADMIN_SESSION_IDLE_TIMEOUT_MINUTES": "15",
                "CORS_ORIGINS": "https://app.example.test",
                "CSRF_TRUSTED_ORIGINS": "https://app.example.test",
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.auth_enabled = patch.object(auth, "_is_auth_enabled_from_env", return_value=True)
        self.data_dir_patch = patch.object(auth, "_get_data_dir", return_value=self.data_dir)
        self.auth_enabled.start()
        self.data_dir_patch.start()
        self.addCleanup(self.auth_enabled.stop)
        self.addCleanup(self.data_dir_patch.stop)
        auth._auth_enabled = True
        auth.set_initial_password("adminpass123")
        self.user_hash = hash_password_for_storage("userpass123")
        self.db.create_or_update_app_user(
            user_id="user-1",
            username="alice",
            display_name="Alice",
            role="user",
            password_hash=self.user_hash,
            is_active=True,
        )

    def tearDown(self) -> None:
        self.client.close()
        DatabaseManager.reset_instance()
        _reset_auth_globals()
        self.temp_dir.cleanup()

    def _audit_rows(self, task_id: str) -> list[ExecutionLogSession]:
        with self.db.get_session() as session:
            return (
                session.query(ExecutionLogSession)
                .filter(ExecutionLogSession.task_id == task_id)
                .order_by(ExecutionLogSession.started_at.asc())
                .all()
            )

    def _login(self, username: str, password: str, *, origin: str | None = None, client: TestClient | None = None):
        active_client = client or self.client
        headers = {"X-Forwarded-For": "198.51.100.10"}
        if origin:
            headers["Origin"] = origin
        return active_client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
            headers=headers,
        )

    def _reauth_admin(self, *, origin: str | None = None, client: TestClient | None = None):
        active_client = client or self.client
        headers = {"X-Forwarded-For": "198.51.100.10"}
        if origin:
            headers["Origin"] = origin
        return active_client.post(
            "/api/v1/auth/reauth",
            json={"password": "adminpass123"},
            headers=headers,
        )

    def _new_client(self, base_url: str) -> TestClient:
        return TestClient(self.app, base_url=base_url)

    def test_rate_limit_tracks_ip_and_account_buckets_durably(self) -> None:
        self.assertTrue(auth.check_rate_limit("198.51.100.1", "alice", admin=False))
        auth.record_login_failure("198.51.100.1", "alice", reason="invalid_password", admin=False)
        auth.record_login_failure("198.51.100.2", "alice", reason="invalid_password", admin=False)

        self.assertFalse(auth.check_rate_limit("198.51.100.3", "alice", admin=False))
        self.assertTrue(auth.check_rate_limit("198.51.100.3", "bob", admin=False))

        DatabaseManager.reset_instance()
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")
        self.assertFalse(auth.check_rate_limit("198.51.100.3", "alice", admin=False))

    def test_login_failures_are_generic_and_audited_without_secrets(self) -> None:
        response = self._login("alice", "wrongpass")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "invalid_login")
        self.assertNotIn("wrongpass", json.dumps(response.json(), ensure_ascii=False))

        rows = self._audit_rows("security.login_failed")
        self.assertEqual(len(rows), 1)
        detail = self.db.get_execution_log_session_detail(rows[0].session_id)
        text = json.dumps(detail, ensure_ascii=False)
        self.assertIn("invalid_password", text)
        self.assertIn("account_hash", text)
        self.assertNotIn("wrongpass", text)
        self.assertNotIn("Authorization", text)

    def test_disabled_user_login_attempt_is_generic_and_sanitized(self) -> None:
        self.db.create_or_update_app_user(
            user_id="user-1",
            username="alice",
            display_name="Alice",
            role="user",
            password_hash=self.user_hash,
            is_active=False,
        )

        response = self._login("alice", "userpass123")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "invalid_login")
        detail = self.db.get_execution_log_session_detail(self._audit_rows("security.login_failed")[0].session_id)
        text = json.dumps(detail, ensure_ascii=False)
        self.assertIn("disabled_user", text)
        self.assertNotIn("userpass123", text)
        self.assertNotIn(self.user_hash, text)

    def test_production_https_cookie_flags_are_hardened(self) -> None:
        with patch.dict(os.environ, {"APP_ENV": "production", "TRUST_X_FORWARDED_FOR": "true"}, clear=False):
            response = self.client.post(
                "/api/v1/auth/login",
                json={"username": "alice", "password": "userpass123"},
                headers={"Origin": "https://app.example.test", "X-Forwarded-Proto": "https"},
            )

        self.assertEqual(response.status_code, 200)
        set_cookie = response.headers.get("set-cookie", "")
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=lax", set_cookie)
        self.assertIn("Secure", set_cookie)
        self.assertIn("Max-Age=", set_cookie)

    def test_admin_idle_timeout_expires_and_revokes_inactive_session(self) -> None:
        login = self._login("admin", "adminpass123", origin="https://app.example.test")
        self.assertEqual(login.status_code, 200)
        session_cookie = login.cookies.get(auth.COOKIE_NAME)
        self.assertTrue(session_cookie)
        identity = auth.get_session_identity(session_cookie)
        self.assertIsNotNone(identity)
        self.assertTrue(identity.is_admin)
        self.assertTrue(identity.session_id)

        with self.db.get_session() as db_session:
            row = db_session.query(AppUserSession).filter_by(session_id=identity.session_id).one()
            row.last_seen_at = datetime.now() - timedelta(minutes=16)
            db_session.commit()

        response = self.client.get("/api/v1/auth/me")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "unauthorized")
        self.assertIsNone(auth.get_session_identity(session_cookie))
        with self.db.get_session() as db_session:
            row = db_session.query(AppUserSession).filter_by(session_id=identity.session_id).one()
            self.assertIsNotNone(row.revoked_at)

    def test_csrf_origin_rejects_cross_site_admin_post_and_allows_trusted_origin(self) -> None:
        login = self._login("admin", "adminpass123", origin="https://app.example.test")
        self.assertEqual(login.status_code, 200)
        reauth = self._reauth_admin(origin="https://app.example.test")
        self.assertEqual(reauth.status_code, 200)

        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=False):
            rejected = self.client.post(
                "/api/v1/admin/users/user-1/disable",
                json={"reason": "security test", "confirm": "DISABLE"},
                headers={"Origin": "https://evil.example.test"},
            )
            missing = self.client.post(
                "/api/v1/admin/users/user-1/disable",
                json={"reason": "security test", "confirm": "DISABLE"},
            )
            allowed = self.client.post(
                "/api/v1/admin/users/user-1/disable",
                json={"reason": "security test", "confirm": "DISABLE"},
                headers={"Origin": "https://app.example.test"},
            )

        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(rejected.json()["error"], "csrf_origin_forbidden")
        self.assertEqual(missing.status_code, 403)
        self.assertEqual(allowed.status_code, 200)

    def test_analysis_post_same_origin_127001_reaches_validation_error_not_csrf(self) -> None:
        with self._new_client("http://127.0.0.1:8000") as client:
            login = self._login("alice", "userpass123", origin="http://127.0.0.1:8000", client=client)
            self.assertEqual(login.status_code, 200)

            response = client.post(
                "/api/v1/analysis/analyze",
                json={},
                headers={"Origin": "http://127.0.0.1:8000"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["error"], "validation_error")

    def test_analysis_post_same_origin_localhost_reaches_validation_error_not_csrf(self) -> None:
        with self._new_client("http://localhost:8000") as client:
            login = self._login("alice", "userpass123", origin="http://localhost:8000", client=client)
            self.assertEqual(login.status_code, 200)

            response = client.post(
                "/api/v1/analysis/analyze",
                json={},
                headers={"Origin": "http://localhost:8000"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["error"], "validation_error")

    def test_analysis_post_same_origin_uses_request_host_dynamically(self) -> None:
        with self._new_client("http://127.0.0.1:8899") as client:
            login = self._login("alice", "userpass123", origin="http://127.0.0.1:8899", client=client)
            self.assertEqual(login.status_code, 200)

            response = client.post(
                "/api/v1/analysis/analyze",
                json={},
                headers={"Origin": "http://127.0.0.1:8899"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["error"], "validation_error")

    def test_analysis_post_rejects_evil_origin_for_authenticated_cookie(self) -> None:
        with self._new_client("http://127.0.0.1:8000") as client:
            login = self._login("alice", "userpass123", origin="http://127.0.0.1:8000", client=client)
            self.assertEqual(login.status_code, 200)

            response = client.post(
                "/api/v1/analysis/analyze",
                json={},
                headers={"Origin": "https://evil.example.test"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "csrf_origin_forbidden")

    def test_analysis_post_keeps_trusted_dev_origin_for_regular_user(self) -> None:
        with self._new_client("http://127.0.0.1:8000") as client:
            login = self._login("alice", "userpass123", origin="http://localhost:5173", client=client)
            self.assertEqual(login.status_code, 200)

            response = client.post(
                "/api/v1/analysis/analyze",
                json={},
                headers={"Origin": "http://localhost:5173"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["error"], "validation_error")

    def test_analysis_post_without_auth_stays_401(self) -> None:
        response = self.client.post(
            "/api/v1/analysis/analyze",
            json={},
            headers={"Origin": "http://localhost:5173"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "unauthorized")

    def test_local_dev_allows_missing_origin_for_cookie_write(self) -> None:
        login = self._login("admin", "adminpass123", origin="http://localhost:5173")
        self.assertEqual(login.status_code, 200)
        reauth = self._reauth_admin(origin="http://localhost:5173")
        self.assertEqual(reauth.status_code, 200)

        response = self.client.post(
            "/api/v1/admin/users/user-1/disable",
            json={"reason": "local dev test", "confirm": "DISABLE"},
        )

        self.assertEqual(response.status_code, 200)

    def test_public_abuse_limiter_does_not_change_login_limiter_or_authenticated_admin_flow(self) -> None:
        from api.middlewares.public_abuse_limiter import reset_public_api_abuse_limiter_state

        reset_public_api_abuse_limiter_state()
        with patch.dict(
            os.environ,
            {
                "PUBLIC_API_ABUSE_LIMIT_MAX_FAILURES": "1",
                "PUBLIC_API_ABUSE_LIMIT_WINDOW_SECONDS": "300",
            },
            clear=False,
        ):
            unauthenticated = self.client.post(
                "/api/v1/admin/users/user-1/disable",
                json={"reason": "public abuse limiter rehearsal", "confirm": "DISABLE"},
                headers={"X-Forwarded-For": "198.51.100.10"},
            )
            limited = self.client.post(
                "/api/v1/admin/users/user-1/disable",
                json={"reason": "public abuse limiter rehearsal", "confirm": "DISABLE"},
                headers={"X-Forwarded-For": "198.51.100.10"},
            )

            login = self._login("admin", "adminpass123", origin="https://app.example.test")
            reauth = self._reauth_admin(origin="https://app.example.test")
            authenticated = self.client.post(
                "/api/v1/admin/users/user-1/disable",
                json={"reason": "authenticated smoke", "confirm": "DISABLE"},
                headers={
                    "Origin": "https://app.example.test",
                    "X-Forwarded-For": "198.51.100.10",
                },
            )

        self.assertEqual([unauthenticated.status_code, limited.status_code], [401, 429])
        self.assertEqual(login.status_code, 200)
        self.assertEqual(reauth.status_code, 200)
        self.assertEqual(authenticated.status_code, 200)


class CorsProductionGuardrailTestCase(unittest.TestCase):
    def test_production_rejects_wildcard_cors(self) -> None:
        from api.app import create_app

        with patch.dict(os.environ, {"APP_ENV": "production", "CORS_ALLOW_ALL": "true"}, clear=False):
            with self.assertRaises(RuntimeError):
                create_app()

    def test_production_requires_explicit_cors_origins(self) -> None:
        from api.app import create_app

        with patch.dict(os.environ, {"APP_ENV": "production", "CORS_ALLOW_ALL": "false", "CORS_ORIGINS": ""}, clear=False):
            with self.assertRaises(RuntimeError):
                create_app()
