# -*- coding: utf-8 -*-
"""Focused tests for admin MFA backend foundation."""

from __future__ import annotations

import base64
import hmac
import os
import struct
import tempfile
import time
import unittest
from hashlib import sha1
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.auth as auth
from api.middlewares.auth import add_auth_middleware
from src.storage import DatabaseManager


TEST_MFA_SECRET = "JBSWY3DPEHPK3PXP"


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._password_hash_value = None
    auth._rate_limit = {}
    auth._admin_reauth_markers = {}


def _totp_code(secret: str, *, at_time: int | None = None) -> str:
    key = base64.b32decode(secret.upper())
    counter = int((at_time or time.time()) // 30)
    digest = hmac.new(key, struct.pack(">Q", counter), sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset: offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


class AuthMfaFoundationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_dir = self.root / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "mfa.db"
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")

        from api.v1.endpoints import auth as auth_endpoint

        self.app = FastAPI()
        self.app.include_router(auth_endpoint.router, prefix="/api/v1/auth")
        add_auth_middleware(self.app)
        self.client = TestClient(self.app)

        self.env = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": str(self.db_path),
                "ADMIN_AUTH_ENABLED": "true",
                "WOLFYSTOCK_MFA_TEST_SECRET": TEST_MFA_SECRET,
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

    def tearDown(self) -> None:
        self.client.close()
        DatabaseManager.reset_instance()
        _reset_auth_globals()
        self.temp_dir.cleanup()

    def _login_admin(self):
        response = self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "adminpass123"})
        self.assertEqual(response.status_code, 200)
        return response

    def _reauth_admin(self):
        response = self.client.post("/api/v1/auth/reauth", json={"password": "adminpass123"})
        self.assertEqual(response.status_code, 200)
        return response

    def test_mfa_enrollment_start_returns_secret_once_and_stores_pending_metadata(self) -> None:
        self._login_admin()

        response = self.client.post("/api/v1/auth/mfa/enroll/start")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "pending")
        self.assertEqual(payload["secret"], TEST_MFA_SECRET)
        self.assertIn("otpauth://totp/", payload["provisioningUri"])
        self.assertFalse(payload["mfaRequiredForLogin"])

        user = self.db.get_app_user("bootstrap-admin")
        self.assertFalse(getattr(user, "mfa_enabled"))
        self.assertIsNotNone(getattr(user, "mfa_created_at"))
        self.assertIsNone(getattr(user, "mfa_enabled_at"))
        self.assertNotEqual(getattr(user, "mfa_secret_ref"), TEST_MFA_SECRET)
        self.assertTrue(str(getattr(user, "mfa_secret_ref")).startswith("test-only:"))

    def test_mfa_enrollment_verify_requires_recent_reauth_and_does_not_block_login(self) -> None:
        self._login_admin()
        self.client.post("/api/v1/auth/mfa/enroll/start")
        code = _totp_code(TEST_MFA_SECRET)

        blocked = self.client.post("/api/v1/auth/mfa/enroll/verify", json={"code": code})
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()["detail"]["error"], "admin_reauth_required")

        self._reauth_admin()
        enabled = self.client.post("/api/v1/auth/mfa/enroll/verify", json={"code": code})
        self.assertEqual(enabled.status_code, 200)
        self.assertTrue(enabled.json()["ok"])
        self.assertEqual(enabled.json()["status"], "enabled")
        self.assertFalse(enabled.json()["mfaRequiredForLogin"])
        self.assertNotIn(TEST_MFA_SECRET, enabled.text)

        user = self.db.get_app_user("bootstrap-admin")
        self.assertTrue(getattr(user, "mfa_enabled"))
        self.assertIsNotNone(getattr(user, "mfa_enabled_at"))
        self.assertIsNotNone(getattr(user, "mfa_last_verified_at"))

        login = self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "adminpass123"})
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.json()["ok"])

    def test_mfa_verify_is_sanitized_and_updates_last_verified_at(self) -> None:
        self._login_admin()
        self.client.post("/api/v1/auth/mfa/enroll/start")
        self._reauth_admin()
        code = _totp_code(TEST_MFA_SECRET)
        self.client.post("/api/v1/auth/mfa/enroll/verify", json={"code": code})

        rejected = self.client.post("/api/v1/auth/mfa/verify", json={"code": "000000"})
        self.assertEqual(rejected.status_code, 401)
        self.assertEqual(rejected.json()["error"], "invalid_mfa_code")
        self.assertNotIn(TEST_MFA_SECRET, rejected.text)

        accepted = self.client.post("/api/v1/auth/mfa/verify", json={"code": _totp_code(TEST_MFA_SECRET)})
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json()["verified"])
        self.assertNotIn(TEST_MFA_SECRET, accepted.text)

    def test_mfa_disable_requires_recent_reauth(self) -> None:
        self._login_admin()
        self.client.post("/api/v1/auth/mfa/enroll/start")
        self._reauth_admin()
        self.client.post("/api/v1/auth/mfa/enroll/verify", json={"code": _totp_code(TEST_MFA_SECRET)})
        auth._admin_reauth_markers = {}

        blocked = self.client.post("/api/v1/auth/mfa/disable")
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()["detail"]["error"], "admin_reauth_required")

        self._reauth_admin()
        disabled = self.client.post("/api/v1/auth/mfa/disable")
        self.assertEqual(disabled.status_code, 200)
        self.assertTrue(disabled.json()["ok"])
        self.assertEqual(disabled.json()["status"], "disabled")
        user = self.db.get_app_user("bootstrap-admin")
        self.assertFalse(getattr(user, "mfa_enabled"))
        self.assertIsNone(getattr(user, "mfa_secret_ref"))


if __name__ == "__main__":
    unittest.main()
