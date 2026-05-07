# -*- coding: utf-8 -*-
"""Launch preflight tests for MFA and admin RBAC readiness."""

from __future__ import annotations

import base64
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
from api.deps import CurrentUser
from api.middlewares.auth import add_auth_middleware
from src.admin_rbac import ADMIN_RBAC_CAPABILITIES, expand_admin_capabilities
from src.multi_user import ROLE_ADMIN
from src.storage import DatabaseManager
from tests.security_launch_preflight_helper import build_security_launch_preflight


TEST_MFA_SECRET = "JBSWY3DPEHPK3PXP"
TEST_MFA_ENCRYPTION_KEY = "launch-preflight-mfa-key-32-bytes-minimum"


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


def _legacy_admin_user(*, admin_capabilities=()) -> CurrentUser:
    return CurrentUser(
        user_id="launch-preflight-admin",
        username="launch-preflight-admin",
        display_name="Launch Preflight Admin",
        role=ROLE_ADMIN,
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="raw-session-id",
        admin_capabilities=tuple(admin_capabilities),
    )


class SecurityLaunchPreflightTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_dir = self.root / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "launch_preflight.db"
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
                "WOLFYSTOCK_MFA_SECRET_KEY_ID": "launch-preflight-key",
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

    def _login_admin(self, **extra_json):
        payload = {"username": "admin", "password": "adminpass123"}
        payload.update(extra_json)
        return self.client.post("/api/v1/auth/login", json=payload)

    def _reauth_admin(self) -> None:
        response = self.client.post("/api/v1/auth/reauth", json={"password": "adminpass123"})
        self.assertEqual(response.status_code, 200)

    def _enable_admin_mfa_and_recovery_codes(self) -> list[str]:
        login = self._login_admin()
        self.assertEqual(login.status_code, 200)
        with patch.dict(os.environ, {"WOLFYSTOCK_MFA_TEST_SECRET": TEST_MFA_SECRET}, clear=False):
            started = self.client.post("/api/v1/auth/mfa/enroll/start")
            self.assertEqual(started.status_code, 200)
            self._reauth_admin()
            verified = self.client.post("/api/v1/auth/mfa/enroll/verify", json={"code": _totp_code(TEST_MFA_SECRET)})
            self.assertEqual(verified.status_code, 200)
        generated = self.client.post("/api/v1/auth/mfa/recovery-codes/generate")
        self.assertEqual(generated.status_code, 200)
        return generated.json()["recoveryCodes"]

    def test_preflight_report_marks_mfa_and_rbac_launch_posture(self) -> None:
        report = build_security_launch_preflight()

        self.assertFalse(report.mfa_enforcement_enabled_by_default)
        self.assertEqual(report.mfa_pilot_scope, "admin_only")
        self.assertTrue(report.mfa_unsupported_scope_fails_closed)
        self.assertFalse(report.break_glass_enabled_by_default)
        self.assertTrue(report.coarse_admin_fallback_present)
        self.assertEqual(report.coarse_admin_fallback_status, "transitional")
        self.assertTrue(report.coarse_admin_fallback_default_enabled)
        self.assertTrue(report.coarse_admin_fallback_disable_preflight_ready)
        self.assertTrue(report.coarse_admin_fallback_guarded_disable_switch_available)
        self.assertEqual(report.coarse_admin_fallback_production_switch_status, "guarded_disable_available")
        self.assertTrue(report.coarse_admin_fallback_production_switch_ready)
        self.assertTrue(report.public_launch_dependency_inventory_complete)
        self.assertNotIn("admin_route_capability_dependency_gap", report.launch_blockers)
        self.assertTrue(report.explicit_capability_grants_without_fallback)
        self.assertTrue(report.missing_capability_dependency_fail_closed)
        self.assertIn("coarse_admin_fallback_default_enabled_until_switch_applied", report.launch_blockers)
        self.assertTrue(report.missing_admin_capabilities_fail_closed)

    def test_mfa_default_remains_non_enforcing_even_after_enrollment(self) -> None:
        self._enable_admin_mfa_and_recovery_codes()

        response = self._login_admin()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertNotIn("mfaRequired", payload)

    def test_mfa_enforcement_pilot_accepts_totp_and_recovery_code_fallback(self) -> None:
        recovery_code = self._enable_admin_mfa_and_recovery_codes()[0]

        with patch.dict(os.environ, {"WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED": "true"}, clear=False):
            missing = self._login_admin()
            totp = self._login_admin(mfaCode=_totp_code(TEST_MFA_SECRET))
            recovery = self._login_admin(mfaRecoveryCode=recovery_code)
            replay = self._login_admin(mfaRecoveryCode=recovery_code)

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(missing.json()["error"], "mfa_required")
        self.assertEqual(totp.status_code, 200)
        self.assertTrue(totp.json()["ok"])
        self.assertEqual(recovery.status_code, 200)
        self.assertTrue(recovery.json()["ok"])
        self.assertEqual(replay.status_code, 401)
        self.assertEqual(replay.json()["error"], "mfa_required")
        rendered = missing.text + totp.text + recovery.text + replay.text
        self.assertNotIn(TEST_MFA_SECRET, rendered)
        self.assertNotIn(recovery_code, rendered)

    def test_break_glass_default_is_disabled_and_enabled_path_is_audited(self) -> None:
        self._enable_admin_mfa_and_recovery_codes()

        with patch("api.v1.endpoints.auth.ExecutionLogService") as service_cls:
            recorder = service_cls.return_value
            with patch.dict(os.environ, {"WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED": "true"}, clear=False):
                blocked = self._login_admin(breakGlassReason="lost-device-ticket-42")
            with patch.dict(
                os.environ,
                {
                    "WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED": "true",
                    "WOLFYSTOCK_MFA_LOGIN_BREAK_GLASS_ENABLED": "true",
                },
                clear=False,
            ):
                accepted = self._login_admin(breakGlassReason="lost-device-ticket-42")

        self.assertEqual(blocked.status_code, 401)
        self.assertEqual(blocked.json()["error"], "mfa_required")
        self.assertEqual(accepted.status_code, 200)
        actions = [call.kwargs.get("action") for call in recorder.record_admin_action.call_args_list]
        self.assertIn("security.mfa_login_required", actions)
        self.assertIn("security.mfa_break_glass_login", actions)
        audit_text = repr(recorder.record_admin_action.call_args_list)
        self.assertIn("break_glass_reason_hash", audit_text)
        self.assertNotIn("lost-device-ticket-42", audit_text)
        self.assertNotIn(TEST_MFA_SECRET, audit_text)

    def test_break_glass_enabled_still_fails_closed_for_unsupported_scope(self) -> None:
        self._enable_admin_mfa_and_recovery_codes()

        with patch("api.v1.endpoints.auth.ExecutionLogService") as service_cls:
            recorder = service_cls.return_value
            with patch.dict(
                os.environ,
                {
                    "WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED": "true",
                    "WOLFYSTOCK_MFA_LOGIN_BREAK_GLASS_ENABLED": "true",
                    "WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_SCOPE": "global",
                },
                clear=False,
            ):
                response = self._login_admin(breakGlassReason="lost-device-ticket-42")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "mfa_required")
        self.assertNotIn("set-cookie", {key.lower(): value for key, value in response.headers.items()})
        actions = [call.kwargs.get("action") for call in recorder.record_admin_action.call_args_list]
        self.assertIn("security.mfa_login_enforcement_decision", actions)
        self.assertNotIn("security.mfa_break_glass_login", actions)
        audit_text = repr(recorder.record_admin_action.call_args_list)
        self.assertIn("unsupported_scope", audit_text)
        self.assertNotIn("lost-device-ticket-42", audit_text)
        self.assertNotIn(TEST_MFA_SECRET, audit_text)

    def test_missing_admin_capabilities_payload_fails_closed_without_leaks(self) -> None:
        report = build_security_launch_preflight()
        payload = report.missing_admin_capabilities_payload

        self.assertEqual(payload["adminCapabilities"], [])
        for key, value in payload.items():
            if key.startswith("can"):
                self.assertFalse(value, key)
        text = json.dumps(payload, sort_keys=True).lower()
        for forbidden in ("raw-session-id", "sessionid", "password", "cookie", "token", "api_key", "secret"):
            self.assertNotIn(forbidden, text)

    def test_coarse_admin_fallback_remains_present_and_marked_launch_blocker(self) -> None:
        capabilities = expand_admin_capabilities(_legacy_admin_user())
        report = build_security_launch_preflight()

        self.assertEqual(set(ADMIN_RBAC_CAPABILITIES), capabilities)
        self.assertTrue(report.coarse_admin_fallback_present)
        self.assertEqual(report.coarse_admin_fallback_status, "transitional")
        self.assertTrue(report.coarse_admin_fallback_default_enabled)
        self.assertTrue(report.coarse_admin_fallback_guarded_disable_switch_available)
        self.assertIn("coarse_admin_fallback_default_enabled_until_switch_applied", report.launch_blockers)
        self.assertIn("WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED=false", report.rollback_safe_next_step)

    def test_coarse_fallback_production_switch_status_reports_no_route_gap(self) -> None:
        report = build_security_launch_preflight()

        self.assertEqual(report.coarse_admin_fallback_production_switch_status, "guarded_disable_available")
        self.assertTrue(report.coarse_admin_fallback_production_switch_ready)
        self.assertEqual(
            {
                "fallback_default_enabled": True,
                "fallback_disabled_fail_closed": True,
                "explicit_capability_payloads_without_fallback": True,
                "legacy_admin_without_payload_denied_without_fallback": True,
                "missing_payload_without_fallback_fail_closed": True,
                "sanitized_denials_without_fallback": True,
                "public_launch_dependency_inventory_complete": True,
                "runtime_default_changed": False,
                "guarded_disable_switch_available": True,
            },
            report.coarse_admin_fallback_switch_evidence,
        )
        self.assertEqual({}, report.public_launch_legacy_admin_route_dependencies)
        self.assertNotIn("admin_route_capability_dependency_gap", report.launch_blockers)
        self.assertTrue(report.public_launch_dependency_inventory_complete)

    def test_role_capability_payloads_do_not_leak_secrets_or_session_data(self) -> None:
        login = self._login_admin()
        self.assertEqual(login.status_code, 200)
        current_user = login.json()["currentUser"]

        self.assertIn("adminCapabilities", current_user)
        self.assertNotIn("sessionId", current_user)
        self.assertNotIn("passwordHash", current_user)
        text = json.dumps(current_user, sort_keys=True).lower()
        for forbidden in (
            "raw-session-id",
            "password",
            "cookie",
            "token",
            "api_key",
            "apikey",
            "secret",
            ".env",
            "rolemappings",
            "recovery",
        ):
            self.assertNotIn(forbidden, text)

    def test_admin_role_management_assignment_preflight_is_launch_ready_but_runtime_pending(self) -> None:
        report = build_security_launch_preflight()

        self.assertFalse(report.role_management_runtime_api_present)
        self.assertTrue(report.role_management_ui_api_pending)
        self.assertTrue(report.role_assignment_requires_explicit_capability)
        self.assertTrue(report.role_assignment_invalid_inputs_fail_closed)
        self.assertTrue(report.role_assignment_self_escalation_blocked)
        self.assertTrue(report.role_assignment_audit_payload_sanitized)
        self.assertTrue(report.role_assignment_least_privilege_preserved)
        self.assertTrue(report.role_assignment_missing_payload_fail_closed)
        self.assertFalse(report.role_assignment_runtime_behavior_changed)


if __name__ == "__main__":
    unittest.main()
