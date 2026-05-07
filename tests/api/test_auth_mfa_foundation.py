# -*- coding: utf-8 -*-
"""Focused tests for admin MFA backend foundation."""

from __future__ import annotations

import base64
from datetime import datetime
import hmac
import json
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
from src.repositories.auth_repo import AuthRepository
from src.services.admin_mfa_service import (
    MFA_SECRET_REF_ENCRYPTED_PREFIX,
    create_enrollment_challenge,
    verify_totp_code,
)
from src.storage import DatabaseManager


TEST_MFA_SECRET = "JBSWY3DPEHPK3PXP"
TEST_MFA_ENCRYPTION_KEY = "test-mfa-secret-storage-key-32-bytes-minimum"


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
                "WOLFYSTOCK_MFA_SECRET_ENCRYPTION_KEY": TEST_MFA_ENCRYPTION_KEY,
                "WOLFYSTOCK_MFA_SECRET_KEY_ID": "unit-test-key",
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

    def _enable_admin_mfa_and_recovery_codes(self):
        self._login_admin()
        with patch.dict(os.environ, {"WOLFYSTOCK_MFA_TEST_SECRET": TEST_MFA_SECRET}, clear=False):
            self.client.post("/api/v1/auth/mfa/enroll/start")
            self._reauth_admin()
            self.client.post("/api/v1/auth/mfa/enroll/verify", json={"code": _totp_code(TEST_MFA_SECRET)})
        generated = self.client.post("/api/v1/auth/mfa/recovery-codes/generate")
        self.assertEqual(generated.status_code, 200)
        return generated.json()["recoveryCodes"]

    def _reauth_admin(self):
        response = self.client.post("/api/v1/auth/reauth", json={"password": "adminpass123"})
        self.assertEqual(response.status_code, 200)
        return response

    def test_mfa_enrollment_start_returns_secret_once_and_stores_pending_metadata(self) -> None:
        self._login_admin()

        with patch.dict(os.environ, {"WOLFYSTOCK_MFA_TEST_SECRET": TEST_MFA_SECRET}, clear=False):
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
        with patch.dict(os.environ, {"WOLFYSTOCK_MFA_TEST_SECRET": TEST_MFA_SECRET}, clear=False):
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
        with patch.dict(os.environ, {"WOLFYSTOCK_MFA_TEST_SECRET": TEST_MFA_SECRET}, clear=False):
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
        with patch.dict(os.environ, {"WOLFYSTOCK_MFA_TEST_SECRET": TEST_MFA_SECRET}, clear=False):
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

    def test_recovery_code_generation_returns_plaintext_once_and_stores_hashes(self) -> None:
        self._login_admin()
        with patch.dict(os.environ, {"WOLFYSTOCK_MFA_TEST_SECRET": TEST_MFA_SECRET}, clear=False):
            self.client.post("/api/v1/auth/mfa/enroll/start")
            self._reauth_admin()
            self.client.post("/api/v1/auth/mfa/enroll/verify", json={"code": _totp_code(TEST_MFA_SECRET)})

        generated = self.client.post("/api/v1/auth/mfa/recovery-codes/generate")

        self.assertEqual(generated.status_code, 200)
        payload = generated.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "generated")
        self.assertEqual(payload["count"], 10)
        codes = payload["recoveryCodes"]
        self.assertEqual(len(codes), 10)
        self.assertTrue(all("-" in code for code in codes))
        self.assertFalse(payload["mfaRequiredForLogin"])

        user = self.db.get_app_user("bootstrap-admin")
        stored = getattr(user, "mfa_recovery_codes_hash")
        self.assertIsNotNone(stored)
        self.assertNotIn(codes[0], stored)
        envelope = json.loads(stored)
        active_set = envelope["sets"][0]
        self.assertIsNotNone(active_set["generated_at"])
        self.assertIsNone(active_set["replaced_at"])
        self.assertEqual(len(active_set["codes"]), 10)
        self.assertTrue(all(entry["hash"].startswith("$wolfystock$kdf=v1$") for entry in active_set["codes"]))

    def test_recovery_code_verify_marks_used_once_and_does_not_block_login(self) -> None:
        self._login_admin()
        with patch.dict(os.environ, {"WOLFYSTOCK_MFA_TEST_SECRET": TEST_MFA_SECRET}, clear=False):
            self.client.post("/api/v1/auth/mfa/enroll/start")
            self._reauth_admin()
            self.client.post("/api/v1/auth/mfa/enroll/verify", json={"code": _totp_code(TEST_MFA_SECRET)})
        generated = self.client.post("/api/v1/auth/mfa/recovery-codes/generate")
        code = generated.json()["recoveryCodes"][0]

        verified = self.client.post("/api/v1/auth/mfa/recovery-codes/verify", json={"code": code})
        self.assertEqual(verified.status_code, 200)
        self.assertTrue(verified.json()["verified"])
        self.assertEqual(verified.json()["remainingCount"], 9)
        self.assertNotIn(code, verified.text)

        user = self.db.get_app_user("bootstrap-admin")
        envelope = json.loads(getattr(user, "mfa_recovery_codes_hash"))
        used_entries = [entry for entry in envelope["sets"][0]["codes"] if entry["used_at"]]
        self.assertEqual(len(used_entries), 1)

        replay = self.client.post("/api/v1/auth/mfa/recovery-codes/verify", json={"code": code})
        self.assertEqual(replay.status_code, 401)
        self.assertEqual(replay.json()["error"], "invalid_recovery_code")

        login = self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "adminpass123"})
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.json()["ok"])

    def test_recovery_code_rotation_requires_recent_reauth_and_replaces_active_set(self) -> None:
        self._login_admin()
        with patch.dict(os.environ, {"WOLFYSTOCK_MFA_TEST_SECRET": TEST_MFA_SECRET}, clear=False):
            self.client.post("/api/v1/auth/mfa/enroll/start")
            self._reauth_admin()
            self.client.post("/api/v1/auth/mfa/enroll/verify", json={"code": _totp_code(TEST_MFA_SECRET)})
        first = self.client.post("/api/v1/auth/mfa/recovery-codes/generate").json()["recoveryCodes"][0]
        auth._admin_reauth_markers = {}

        blocked = self.client.post("/api/v1/auth/mfa/recovery-codes/rotate")
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()["detail"]["error"], "admin_reauth_required")

        self._reauth_admin()
        rotated = self.client.post("/api/v1/auth/mfa/recovery-codes/rotate")
        self.assertEqual(rotated.status_code, 200)
        payload = rotated.json()
        self.assertEqual(payload["status"], "rotated")
        self.assertEqual(payload["count"], 10)
        second = payload["recoveryCodes"][0]
        self.assertNotEqual(first, second)

        old_rejected = self.client.post("/api/v1/auth/mfa/recovery-codes/verify", json={"code": first})
        self.assertEqual(old_rejected.status_code, 401)

        new_accepted = self.client.post("/api/v1/auth/mfa/recovery-codes/verify", json={"code": second})
        self.assertEqual(new_accepted.status_code, 200)
        self.assertTrue(new_accepted.json()["verified"])

        user = self.db.get_app_user("bootstrap-admin")
        envelope = json.loads(getattr(user, "mfa_recovery_codes_hash"))
        self.assertIsNotNone(envelope["sets"][0]["replaced_at"])
        self.assertIsNone(envelope["sets"][1]["replaced_at"])

    def test_mfa_secret_is_encrypted_for_storage_and_readable_for_verification(self) -> None:
        self._login_admin()

        response = self.client.post("/api/v1/auth/mfa/enroll/start")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["storageMode"], "encrypted_v1")
        secret = payload["secret"]
        user = self.db.get_app_user("bootstrap-admin")
        secret_ref = str(getattr(user, "mfa_secret_ref"))
        self.assertTrue(secret_ref.startswith(MFA_SECRET_REF_ENCRYPTED_PREFIX))
        self.assertNotIn(secret, secret_ref)

        self._reauth_admin()
        verified = self.client.post("/api/v1/auth/mfa/enroll/verify", json={"code": _totp_code(secret)})
        self.assertEqual(verified.status_code, 200)
        self.assertTrue(verified.json()["ok"])
        self.assertNotIn(secret, verified.text)

    def test_mfa_secret_legacy_refs_remain_read_compatible(self) -> None:
        self.assertTrue(verify_totp_code(secret_ref=TEST_MFA_SECRET, code=_totp_code(TEST_MFA_SECRET)))
        self.assertTrue(
            verify_totp_code(
                secret_ref=f"test-only:{TEST_MFA_SECRET}",
                code=_totp_code(TEST_MFA_SECRET),
            )
        )
        self.assertFalse(
            verify_totp_code(
                secret_ref="placeholder-sha256:" + "0" * 64,
                code=_totp_code(TEST_MFA_SECRET),
            )
        )

    def test_mfa_enrollment_fails_safely_when_encryption_key_is_missing(self) -> None:
        self._login_admin()

        with patch.dict(
            os.environ,
            {
                "WOLFYSTOCK_MFA_SECRET_ENCRYPTION_KEY": "",
                "WOLFYSTOCK_MFA_SECRET_KEY_ID": "",
            },
            clear=False,
        ):
            response = self.client.post("/api/v1/auth/mfa/enroll/start")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], "mfa_secret_storage_unavailable")
        self.assertNotIn(TEST_MFA_SECRET, response.text)
        self.assertNotIn("provisioningUri", response.text)
        user = self.db.get_app_user("bootstrap-admin")
        self.assertIsNone(getattr(user, "mfa_secret_ref"))

    def test_mfa_enrollment_challenge_repr_does_not_leak_plaintext_secret(self) -> None:
        repo = AuthRepository(self.db)
        challenge = create_enrollment_challenge(
            user_id="bootstrap-admin",
            username="admin",
            repo=repo,
        )

        rendered = repr(challenge)
        self.assertNotIn(challenge.secret, rendered)
        self.assertNotIn(challenge.provisioning_uri, rendered)
        self.assertNotIn(challenge.secret_ref, rendered)

    def test_mfa_login_enforcement_disabled_keeps_current_login_behavior(self) -> None:
        self._enable_admin_mfa_and_recovery_codes()

        response = self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "adminpass123"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertNotIn("mfaRequired", payload)

    def test_mfa_login_enforcement_denies_admin_without_complete_mfa_state_and_no_session_cookie(self) -> None:
        with patch("api.v1.endpoints.auth.ExecutionLogService") as service_cls:
            recorder = service_cls.return_value
            with patch.dict(os.environ, {"WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED": "true"}, clear=False):
                response = self.client.post(
                    "/api/v1/auth/login",
                    json={"username": "admin", "password": "adminpass123"},
                )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "mfa_required")
        self.assertNotIn("set-cookie", {key.lower(): value for key, value in response.headers.items()})
        audit_text = repr(recorder.record_admin_action.call_args_list)
        self.assertIn("mfa_state_incomplete", audit_text)
        self.assertNotIn("adminpass123", response.text + audit_text)

    def test_mfa_login_enforcement_admin_only_pilot_skips_user_accounts_with_audit(self) -> None:
        self.db.create_or_update_app_user(
            user_id="user-1",
            username="alice",
            display_name="Alice",
            role="user",
            password_hash=auth.hash_password_for_storage("userpass123"),
            is_active=True,
        )

        with patch("api.v1.endpoints.auth.ExecutionLogService") as service_cls:
            recorder = service_cls.return_value
            with patch.dict(
                os.environ,
                {
                    "WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED": "true",
                    "WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ADMIN_ONLY": "true",
                },
                clear=False,
            ):
                response = self.client.post(
                    "/api/v1/auth/login",
                    json={"username": "alice", "password": "userpass123"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        actions = [call.kwargs.get("action") for call in recorder.record_admin_action.call_args_list]
        self.assertIn("security.mfa_login_enforcement_decision", actions)
        audit_text = repr(recorder.record_admin_action.call_args_list)
        self.assertIn("not_eligible_admin_only", audit_text)
        self.assertIn("admin_only", audit_text)
        self.assertNotIn("userpass123", audit_text)

    def test_mfa_login_enforcement_admin_only_pilot_accepts_verified_admin_totp_and_issues_session(self) -> None:
        self._enable_admin_mfa_and_recovery_codes()

        with patch("api.v1.endpoints.auth.ExecutionLogService") as service_cls:
            recorder = service_cls.return_value
            with patch.dict(
                os.environ,
                {
                    "WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED": "true",
                    "WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ADMIN_ONLY": "true",
                },
                clear=False,
            ):
                blocked = self.client.post(
                    "/api/v1/auth/login",
                    json={"username": "admin", "password": "adminpass123"},
                )
                accepted = self.client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": "admin",
                        "password": "adminpass123",
                        "mfaCode": _totp_code(TEST_MFA_SECRET),
                    },
                )

        self.assertEqual(blocked.status_code, 401)
        self.assertEqual(blocked.json()["error"], "mfa_required")
        self.assertNotIn("set-cookie", {key.lower(): value for key, value in blocked.headers.items()})
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json()["ok"])
        self.assertIn("set-cookie", {key.lower(): value for key, value in accepted.headers.items()})
        actions = [call.kwargs.get("action") for call in recorder.record_admin_action.call_args_list]
        self.assertIn("security.mfa_login_enforcement_decision", actions)
        audit_text = repr(recorder.record_admin_action.call_args_list)
        self.assertIn("admin_only", audit_text)
        self.assertIn("totp_success", audit_text)
        self.assertNotIn(TEST_MFA_SECRET, blocked.text + accepted.text + audit_text)

    def test_mfa_login_enforcement_unsupported_scope_fails_closed(self) -> None:
        self._enable_admin_mfa_and_recovery_codes()

        with patch("api.v1.endpoints.auth.ExecutionLogService") as service_cls:
            recorder = service_cls.return_value
            with patch.dict(
                os.environ,
                {
                    "WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED": "true",
                    "WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_SCOPE": "global",
                },
                clear=False,
            ):
                response = self.client.post(
                    "/api/v1/auth/login",
                    json={"username": "admin", "password": "adminpass123"},
                )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "mfa_required")
        audit_text = repr(recorder.record_admin_action.call_args_list)
        self.assertIn("unsupported_scope", audit_text)
        self.assertNotIn("global", audit_text)
        self.assertNotIn("adminpass123", audit_text)

    def test_mfa_login_enforcement_non_admin_only_rollout_mode_fails_closed(self) -> None:
        self._enable_admin_mfa_and_recovery_codes()

        with patch("api.v1.endpoints.auth.ExecutionLogService") as service_cls:
            recorder = service_cls.return_value
            with patch.dict(
                os.environ,
                {
                    "WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED": "true",
                    "WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ADMIN_ONLY": "false",
                },
                clear=False,
            ):
                response = self.client.post(
                    "/api/v1/auth/login",
                    json={"username": "admin", "password": "adminpass123", "mfaCode": _totp_code(TEST_MFA_SECRET)},
                )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "mfa_required")
        self.assertNotIn("set-cookie", {key.lower(): value for key, value in response.headers.items()})
        audit_text = repr(recorder.record_admin_action.call_args_list)
        self.assertIn("unsupported_scope", audit_text)
        self.assertNotIn(TEST_MFA_SECRET, response.text + audit_text)
        self.assertNotIn("adminpass123", response.text + audit_text)

    def test_mfa_login_enforcement_enabled_accepts_verified_totp(self) -> None:
        self._enable_admin_mfa_and_recovery_codes()

        with patch("api.v1.endpoints.auth.ExecutionLogService") as service_cls:
            recorder = service_cls.return_value
            with patch.dict(os.environ, {"WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED": "true"}, clear=False):
                missing = self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "adminpass123"})
                accepted = self.client.post(
                    "/api/v1/auth/login",
                    json={"username": "admin", "password": "adminpass123", "mfaCode": _totp_code(TEST_MFA_SECRET)},
                )

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(missing.json()["error"], "mfa_required")
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json()["ok"])
        self.assertNotIn(TEST_MFA_SECRET, missing.text + accepted.text)
        audit_text = repr(recorder.record_admin_action.call_args_list)
        self.assertIn("security.mfa_login_enforcement_decision", audit_text)
        self.assertIn("totp_success", audit_text)
        self.assertNotIn(TEST_MFA_SECRET, audit_text)

    def test_mfa_login_enforcement_fails_safely_when_recovery_state_is_missing(self) -> None:
        self._enable_admin_mfa_and_recovery_codes()
        repo = AuthRepository(self.db)
        repo.update_app_user_mfa(
            user_id="bootstrap-admin",
            mfa_enabled=True,
            mfa_secret_ref=f"test-only:{TEST_MFA_SECRET}",
            mfa_recovery_codes_hash=None,
            mfa_created_at=datetime.now(),
            mfa_enabled_at=datetime.now(),
            mfa_last_verified_at=None,
        )

        with patch("api.v1.endpoints.auth.ExecutionLogService") as service_cls:
            recorder = service_cls.return_value
            with patch.dict(os.environ, {"WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED": "true"}, clear=False):
                response = self.client.post(
                    "/api/v1/auth/login",
                    json={"username": "admin", "password": "adminpass123", "mfaCode": _totp_code(TEST_MFA_SECRET)},
                )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "mfa_required")
        audit_text = repr(recorder.record_admin_action.call_args_list)
        self.assertIn("mfa_state_incomplete", audit_text)
        self.assertNotIn(TEST_MFA_SECRET, response.text + audit_text)

    def test_mfa_login_enforcement_enabled_accepts_recovery_code_once(self) -> None:
        recovery_code = self._enable_admin_mfa_and_recovery_codes()[0]

        with patch("api.v1.endpoints.auth.ExecutionLogService") as service_cls:
            recorder = service_cls.return_value
            with patch.dict(os.environ, {"WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED": "true"}, clear=False):
                accepted = self.client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": "admin",
                        "password": "adminpass123",
                        "mfaRecoveryCode": recovery_code,
                    },
                )
                replay = self.client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": "admin",
                        "password": "adminpass123",
                        "mfaRecoveryCode": recovery_code,
                    },
                )

        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json()["ok"])
        self.assertIn("set-cookie", {key.lower(): value for key, value in accepted.headers.items()})
        self.assertEqual(replay.status_code, 401)
        self.assertEqual(replay.json()["error"], "mfa_required")
        self.assertNotIn("set-cookie", {key.lower(): value for key, value in replay.headers.items()})
        self.assertNotIn(recovery_code, accepted.text + replay.text)
        actions = [call.kwargs.get("action") for call in recorder.record_admin_action.call_args_list]
        self.assertIn("security.mfa_recovery_code_login", actions)
        self.assertIn("security.mfa_login_required", actions)
        audit_text = repr(recorder.record_admin_action.call_args_list)
        self.assertIn("recovery_code_success", audit_text)
        self.assertIn("mfa_required", audit_text)
        self.assertNotIn(recovery_code, audit_text)
        self.assertNotIn(TEST_MFA_SECRET, audit_text)

    def test_mfa_login_enforcement_invalid_recovery_code_fails_closed_and_is_sanitized(self) -> None:
        self._enable_admin_mfa_and_recovery_codes()

        with patch("api.v1.endpoints.auth.ExecutionLogService") as service_cls:
            recorder = service_cls.return_value
            with patch.dict(os.environ, {"WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED": "true"}, clear=False):
                response = self.client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": "admin",
                        "password": "adminpass123",
                        "mfaRecoveryCode": "BAD-CODE-0000",
                    },
                )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "mfa_required")
        self.assertNotIn("set-cookie", {key.lower(): value for key, value in response.headers.items()})
        actions = [call.kwargs.get("action") for call in recorder.record_admin_action.call_args_list]
        self.assertIn("security.mfa_login_required", actions)
        audit_text = repr(recorder.record_admin_action.call_args_list)
        self.assertIn("mfa_required", audit_text)
        self.assertNotIn("BAD-CODE-0000", response.text + audit_text)
        self.assertNotIn(TEST_MFA_SECRET, response.text + audit_text)

    def test_mfa_login_enforcement_fails_safely_for_missing_or_invalid_state(self) -> None:
        self._enable_admin_mfa_and_recovery_codes()
        repo = AuthRepository(self.db)
        repo.update_app_user_mfa(
            user_id="bootstrap-admin",
            mfa_enabled=True,
            mfa_secret_ref=None,
            mfa_recovery_codes_hash=None,
            mfa_created_at=None,
            mfa_enabled_at=None,
            mfa_last_verified_at=None,
        )

        with patch("api.v1.endpoints.auth.ExecutionLogService") as service_cls:
            recorder = service_cls.return_value
            with patch.dict(os.environ, {"WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED": "true"}, clear=False):
                response = self.client.post(
                    "/api/v1/auth/login",
                    json={"username": "admin", "password": "adminpass123", "mfaCode": _totp_code(TEST_MFA_SECRET)},
                )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "mfa_required")
        self.assertNotIn("set-cookie", {key.lower(): value for key, value in response.headers.items()})
        audit_text = repr(recorder.record_admin_action.call_args_list)
        self.assertIn("mfa_state_incomplete", audit_text)
        self.assertNotIn(TEST_MFA_SECRET, response.text)
        self.assertNotIn("adminpass123", response.text + audit_text)

    def test_mfa_break_glass_login_requires_explicit_flag_reason_and_audit(self) -> None:
        self._enable_admin_mfa_and_recovery_codes()

        with patch("api.v1.endpoints.auth.ExecutionLogService") as service_cls:
            recorder = service_cls.return_value
            with patch.dict(os.environ, {"WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED": "true"}, clear=False):
                blocked = self.client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": "admin",
                        "password": "adminpass123",
                        "breakGlassReason": "lost-device-support-ticket",
                    },
                )
            with patch.dict(
                os.environ,
                {
                    "WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED": "true",
                    "WOLFYSTOCK_MFA_LOGIN_BREAK_GLASS_ENABLED": "true",
                },
                clear=False,
            ):
                accepted = self.client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": "admin",
                        "password": "adminpass123",
                        "breakGlassReason": "lost-device-support-ticket",
                    },
                )

        self.assertEqual(blocked.status_code, 401)
        self.assertEqual(blocked.json()["error"], "mfa_required")
        self.assertEqual(accepted.status_code, 200)
        recorder.record_admin_action.assert_called()
        actions = [call.kwargs.get("action") for call in recorder.record_admin_action.call_args_list]
        self.assertIn("security.mfa_break_glass_login", actions)
        rendered_calls = repr(recorder.record_admin_action.call_args_list)
        self.assertNotIn(TEST_MFA_SECRET, rendered_calls)
        self.assertNotIn("adminpass123", rendered_calls)
        self.assertNotIn("lost-device-support-ticket", rendered_calls)

    def test_mfa_login_enforcement_responses_and_audit_do_not_leak_secrets(self) -> None:
        recovery_code = self._enable_admin_mfa_and_recovery_codes()[0]

        with patch("api.v1.endpoints.auth.ExecutionLogService") as service_cls:
            recorder = service_cls.return_value
            with patch.dict(os.environ, {"WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED": "true"}, clear=False):
                rejected = self.client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": "admin",
                        "password": "adminpass123",
                        "mfaCode": "000000",
                        "mfaRecoveryCode": "BAD-CODE-0000",
                    },
                )

        self.assertEqual(rejected.status_code, 401)
        response_text = rejected.text
        audit_text = repr(recorder.record_admin_action.call_args_list)
        self.assertNotIn(TEST_MFA_SECRET, response_text + audit_text)
        self.assertNotIn(recovery_code, response_text + audit_text)
        self.assertNotIn("otpauth://", response_text + audit_text)


if __name__ == "__main__":
    unittest.main()
