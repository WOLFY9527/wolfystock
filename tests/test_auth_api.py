# -*- coding: utf-8 -*-
"""Integration tests for auth API endpoints (login, logout, change-password, API protection)."""

import asyncio
import base64
import hashlib
import json
import os
import secrets
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock, patch

from dotenv import dotenv_values
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import Response
from sqlalchemy import func, select
from starlette.requests import Request

# Keep this test runnable when optional LLM runtime deps are not installed.
try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.deps import CurrentUser
from api.middlewares.auth import AuthMiddleware
from api.v1.endpoints import auth as auth_endpoint
from src.admin_rbac import ADMIN_RBAC_ROLE_CAPABILITIES, SUPER_ADMIN_ROLE
from src.config import Config
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID, ROLE_ADMIN
from src.storage import AdminUserRole, DatabaseManager


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._password_hash_value = None
    auth._rate_limit = {}
    auth._admin_reauth_markers = {}


CAPABILITY_FLAG_MAP = {
    "canReadUsers": "users:read",
    "canReadUserActivity": "users:activity:read",
    "canReadUserPortfolio": "users:portfolio:read",
    "canWriteUserSecurity": "users:security:write",
    "canReadCostObservability": "cost:observability:read",
    "canReadOpsLogs": "ops:logs:read",
    "canReadProviders": "ops:providers:read",
    "canReadNotifications": "ops:notifications:read",
    "canReadSystemConfig": "ops:system_config:read",
}


class AuthApiTestCase(unittest.TestCase):
    """Integration tests for /api/v1/auth/* and API protection."""

    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.env_path.write_text(
            "STOCK_LIST=600519\nGEMINI_API_KEY=test\nADMIN_AUTH_ENABLED=true\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.data_dir / "test.db")
        self.coarse_fallback_patcher = patch.dict(
            os.environ,
            {"WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED": "false"},
            clear=False,
        )
        self.coarse_fallback_patcher.start()
        Config.reset_instance()
        DatabaseManager.reset_instance()

        self.auth_patcher = patch.object(auth, "_is_auth_enabled_from_env", return_value=True)
        self.data_dir_patcher = patch.object(auth, "_get_data_dir", return_value=self.data_dir)
        self.auth_patcher.start()
        self.data_dir_patcher.start()

        self.db = DatabaseManager.get_instance()

    def tearDown(self) -> None:
        self.auth_patcher.stop()
        self.data_dir_patcher.stop()
        self.coarse_fallback_patcher.stop()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def _read_auth_enabled_from_env(self) -> bool:
        values = dotenv_values(self.env_path)
        return (values.get("ADMIN_AUTH_ENABLED") or "").strip().lower() in ("true", "1", "yes")

    @staticmethod
    def _build_request(cookies=None, headers=None):
        return SimpleNamespace(
            headers=headers or {},
            url=SimpleNamespace(scheme="http"),
            cookies=cookies or {},
            client=SimpleNamespace(host="127.0.0.1"),
            state=SimpleNamespace(),
            app=SimpleNamespace(state=SimpleNamespace()),
        )

    @staticmethod
    def _extract_session_cookie(response) -> str:
        cookie_header = response.headers["set-cookie"]
        return cookie_header.split(f"{auth.COOKIE_NAME}=", 1)[1].split(";", 1)[0]

    @staticmethod
    def _json_response_body(response) -> dict:
        return json.loads(response.body.decode("utf-8"))

    def _assert_canonical_super_admin_capabilities(self, payload: dict) -> None:
        expected = set(ADMIN_RBAC_ROLE_CAPABILITIES[SUPER_ADMIN_ROLE])
        self.assertEqual(payload["adminCapabilities"], sorted(expected))
        for flag, capability in CAPABILITY_FLAG_MAP.items():
            self.assertEqual(payload[flag], capability in expected)

    @staticmethod
    def _legacy_hash(password: str) -> str:
        salt = secrets.token_bytes(32)
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt=salt,
            iterations=auth.PBKDF2_ITERATIONS,
        )
        return (
            f"{base64.standard_b64encode(salt).decode('ascii')}:"
            f"{base64.standard_b64encode(derived).decode('ascii')}"
        )

    def _login_admin(self, password: str = "passwd6"):
        return asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(),
                auth_endpoint.LoginRequest(password=password, passwordConfirm=password),
            )
        )

    def _login_user(self, username: str = "alice", password: str = "passwd6"):
        return asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(),
                auth_endpoint.LoginRequest(
                    username=username,
                    displayName="Alice",
                    createUser=True,
                    password=password,
                    passwordConfirm=password,
                ),
            )
        )

    def test_auth_status_when_password_not_set(self) -> None:
        data = asyncio.run(auth_endpoint.auth_status(self._build_request()))
        self.assertTrue(data["authEnabled"])
        self.assertFalse(data["passwordSet"])
        self.assertFalse(data["loggedIn"])
        self.assertEqual(data["setupState"], "no_password")
        self.assertEqual(self.db.list_admin_user_roles(BOOTSTRAP_ADMIN_USER_ID), [])
        me_response = asyncio.run(auth_endpoint.auth_me(self._build_request()))
        self.assertEqual(me_response.status_code, 401)
        self.assertEqual(self.db.list_admin_user_roles(BOOTSTRAP_ADMIN_USER_ID), [])

    def test_login_first_time_set_initial_password(self) -> None:
        self.assertEqual(self.db.list_admin_user_roles(BOOTSTRAP_ADMIN_USER_ID), [])
        response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(),
                auth_endpoint.LoginRequest(password="newpass123", passwordConfirm="newpass123"),
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("dsa_session=", response.headers["set-cookie"])
        self.assertIn(b'"ok":true', response.body)
        login_payload = self._json_response_body(response)
        expected_capabilities = sorted(ADMIN_RBAC_ROLE_CAPABILITIES[SUPER_ADMIN_ROLE])
        self.assertEqual(self.db.list_admin_role_capabilities(SUPER_ADMIN_ROLE), expected_capabilities)
        self.assertEqual(self.db.list_admin_user_roles(BOOTSTRAP_ADMIN_USER_ID), [SUPER_ADMIN_ROLE])
        self._assert_canonical_super_admin_capabilities(login_payload["currentUser"])

        session_cookie = self._extract_session_cookie(response)
        status_payload = asyncio.run(
            auth_endpoint.auth_status(self._build_request(cookies={auth.COOKIE_NAME: session_cookie}))
        )
        me_payload = asyncio.run(
            auth_endpoint.auth_me(self._build_request(cookies={auth.COOKIE_NAME: session_cookie}))
        )
        self._assert_canonical_super_admin_capabilities(status_payload["currentUser"])
        self._assert_canonical_super_admin_capabilities(me_payload)

        DatabaseManager.reset_instance()
        Config.reset_instance()
        _reset_auth_globals()
        self.db = DatabaseManager.get_instance()
        self.assertEqual(self.db.list_admin_user_roles(BOOTSTRAP_ADMIN_USER_ID), [SUPER_ADMIN_ROLE])

        repeated_response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(),
                auth_endpoint.LoginRequest(password="newpass123"),
            )
        )
        self.assertEqual(repeated_response.status_code, 200)
        repeated_payload = self._json_response_body(repeated_response)
        self._assert_canonical_super_admin_capabilities(repeated_payload["currentUser"])
        self.assertEqual(self.db.list_admin_user_roles(BOOTSTRAP_ADMIN_USER_ID), [SUPER_ADMIN_ROLE])
        repeated_cookie = self._extract_session_cookie(repeated_response)
        restarted_status = asyncio.run(
            auth_endpoint.auth_status(self._build_request(cookies={auth.COOKIE_NAME: repeated_cookie}))
        )
        restarted_me = asyncio.run(
            auth_endpoint.auth_me(self._build_request(cookies={auth.COOKIE_NAME: repeated_cookie}))
        )
        self._assert_canonical_super_admin_capabilities(restarted_status["currentUser"])
        self._assert_canonical_super_admin_capabilities(restarted_me)
        with self.db.get_session() as session:
            assignment_count = session.execute(
                select(func.count(AdminUserRole.id)).where(
                    AdminUserRole.user_id == BOOTSTRAP_ADMIN_USER_ID,
                    AdminUserRole.role_key == SUPER_ADMIN_ROLE,
                )
            ).scalar_one()
        self.assertEqual(assignment_count, 1)

    def test_login_first_time_mismatch_rejected(self) -> None:
        response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(),
                auth_endpoint.LoginRequest(password="pass1", passwordConfirm="pass2"),
            )
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'"error":"password_mismatch"', response.body)

    def test_login_after_set_normal_login(self) -> None:
        first_response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(),
                auth_endpoint.LoginRequest(password="mypass456", passwordConfirm="mypass456"),
            )
        )
        self.assertEqual(first_response.status_code, 200)

        response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(),
                auth_endpoint.LoginRequest(password="mypass456"),
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"ok":true', response.body)

        with self.db.session_scope() as session:
            session.query(AdminUserRole).filter(
                AdminUserRole.user_id == BOOTSTRAP_ADMIN_USER_ID,
                AdminUserRole.role_key == SUPER_ADMIN_ROLE,
            ).delete()
        session_count = len(self.db.list_app_user_sessions(BOOTSTRAP_ADMIN_USER_ID))
        with patch.object(
            auth_endpoint.AuthRepository,
            "ensure_bootstrap_admin_role_assignment",
            side_effect=RuntimeError("simulated assignment persistence failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "assignment persistence failure"):
                asyncio.run(
                    auth_endpoint.auth_login(
                        self._build_request(),
                        auth_endpoint.LoginRequest(password="mypass456"),
                    )
                )
        self.assertEqual(len(self.db.list_app_user_sessions(BOOTSTRAP_ADMIN_USER_ID)), session_count)
        self.assertEqual(self.db.list_admin_user_roles(BOOTSTRAP_ADMIN_USER_ID), [])

    def test_login_create_normal_user_and_auth_me(self) -> None:
        response = self._login_user(username="normal-user", password="secret123")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"createdUser":true', response.body)
        self.assertIn(b'"role":"user"', response.body)

        session_cookie = self._extract_session_cookie(response)
        me_response = asyncio.run(
            auth_endpoint.auth_me(
                self._build_request(cookies={auth.COOKIE_NAME: session_cookie})
            )
        )

        self.assertEqual(me_response["username"], "normal-user")
        self.assertEqual(me_response["role"], "user")
        self.assertFalse(me_response["isAdmin"])
        self.assertTrue(me_response["isAuthenticated"])

    def test_cookie_max_age_uses_the_server_session_ttl_floor(self) -> None:
        request = self._build_request()

        for configured_hours in ("0", "-1"):
            with patch.dict(os.environ, {"ADMIN_SESSION_MAX_AGE_HOURS": configured_hours}, clear=False):
                self.assertEqual(
                    auth_endpoint._cookie_params(request)["max_age"],
                    auth._get_session_max_age_seconds(),
                )
                self.assertEqual(auth_endpoint._cookie_params(request)["max_age"], 300)

    def test_server_side_expiry_invalidates_a_signed_session_without_waiting(self) -> None:
        login_response = self._login_user(username="expiry-user", password="secret123")
        session_cookie = self._extract_session_cookie(login_response)
        identity = auth.get_session_identity(session_cookie)
        self.assertIsNotNone(identity)
        self.assertIsNotNone(identity.session_id)

        DatabaseManager.get_instance().create_app_user_session(
            session_id=identity.session_id,
            user_id=identity.user_id,
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )

        response = asyncio.run(
            auth_endpoint.auth_me(self._build_request(cookies={auth.COOKIE_NAME: session_cookie}))
        )
        self.assertEqual(response.status_code, 401)

    def test_uat_consumer_fixture_accounts_login_as_non_admin_users(self) -> None:
        from scripts.seed_uat_consumer_test_accounts import (
            UAT_CONSUMER_TEST_ACCOUNT_USERNAMES,
            seed_uat_consumer_test_accounts,
            uat_consumer_test_login_value,
        )

        missing_response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(),
                auth_endpoint.LoginRequest(
                    username=UAT_CONSUMER_TEST_ACCOUNT_USERNAMES[0],
                    password=uat_consumer_test_login_value(),
                ),
            )
        )
        self.assertEqual(missing_response.status_code, 401)

        seed_result = seed_uat_consumer_test_accounts()

        self.assertEqual(seed_result["status"], "seeded")
        self.assertEqual(
            [item["username"] for item in seed_result["accounts"]],
            list(UAT_CONSUMER_TEST_ACCOUNT_USERNAMES),
        )

        for username in UAT_CONSUMER_TEST_ACCOUNT_USERNAMES:
            response = asyncio.run(
                auth_endpoint.auth_login(
                    self._build_request(),
                    auth_endpoint.LoginRequest(
                        username=username,
                        password=uat_consumer_test_login_value(),
                    ),
                )
            )
            self.assertEqual(response.status_code, 200)
            payload = self._json_response_body(response)
            current_user = payload["currentUser"]
            self.assertTrue(payload["ok"])
            self.assertFalse(payload["createdUser"])
            self.assertEqual(current_user["username"], username)
            self.assertEqual(current_user["role"], "user")
            self.assertFalse(current_user["isAdmin"])
            self.assertEqual(current_user["adminCapabilities"], [])
            self.assertFalse(current_user["canReadUsers"])
            self.assertFalse(current_user["canWriteUserSecurity"])

        for username in UAT_CONSUMER_TEST_ACCOUNT_USERNAMES:
            wrong_password_response = asyncio.run(
                auth_endpoint.auth_login(
                    self._build_request(),
                    auth_endpoint.LoginRequest(
                        username=username,
                        password="852259",
                    ),
                )
            )
            self.assertEqual(wrong_password_response.status_code, 401)
            self.assertEqual(self._json_response_body(wrong_password_response)["error"], "invalid_login")

        admin_response = self._login_admin(password="adminpass123")
        self.assertEqual(admin_response.status_code, 200)
        admin_user = self._json_response_body(admin_response)["currentUser"]
        self.assertEqual(admin_user["username"], "admin")
        self.assertEqual(admin_user["role"], "admin")
        self.assertTrue(admin_user["isAdmin"])

    def test_uat_consumer_fixture_login_reconciles_stale_phase_a_runtime_store(self) -> None:
        from api.middlewares.auth import add_auth_middleware
        from scripts.seed_uat_consumer_test_accounts import (
            UAT_CONSUMER_TEST_ACCOUNT_USERNAMES,
            seed_uat_consumer_test_accounts,
            uat_consumer_test_login_value,
        )
        from src.multi_user import ROLE_USER

        seed_result = seed_uat_consumer_test_accounts()
        self.assertEqual(seed_result["status"], "seeded")

        phase_a_path = self.data_dir / "phase-a-identity.db"
        os.environ["POSTGRES_PHASE_A_URL"] = f"sqlite:///{phase_a_path}"
        self.addCleanup(lambda: os.environ.pop("POSTGRES_PHASE_A_URL", None))
        Config.reset_instance()
        DatabaseManager.reset_instance()

        runtime_db = DatabaseManager.get_instance()
        for username in UAT_CONSUMER_TEST_ACCOUNT_USERNAMES:
            runtime_db.create_or_update_app_user(
                user_id=f"phase-a-stale-{username}",
                username=username,
                display_name=f"Stale {username}",
                role=ROLE_USER,
                password_hash=auth.hash_password_for_storage("stale-password"),
                is_active=True,
            )

        app = FastAPI()
        app.include_router(auth_endpoint.router, prefix="/api/v1/auth")
        add_auth_middleware(app)
        with TestClient(app) as client:
            for username in UAT_CONSUMER_TEST_ACCOUNT_USERNAMES:
                response = client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": username,
                        "password": uat_consumer_test_login_value(),
                    },
                )
                self.assertEqual(response.status_code, 200)
                current_user = response.json()["currentUser"]
                self.assertEqual(current_user["username"], username)
                self.assertEqual(current_user["role"], "user")
                self.assertFalse(current_user["isAdmin"])
                self.assertEqual(current_user["adminCapabilities"], [])

    def test_admin_current_user_exposes_safe_sorted_capability_summary(self) -> None:
        response = self._login_admin(password="secret123")
        self.assertEqual(response.status_code, 200)
        session_cookie = self._extract_session_cookie(response)

        status_response = asyncio.run(
            auth_endpoint.auth_status(
                self._build_request(cookies={auth.COOKIE_NAME: session_cookie})
            )
        )
        me_response = asyncio.run(
            auth_endpoint.auth_me(
                self._build_request(cookies={auth.COOKIE_NAME: session_cookie})
            )
        )

        for payload in (status_response["currentUser"], me_response):
            self.assertEqual(payload["id"], BOOTSTRAP_ADMIN_USER_ID)
            self.assertEqual(payload["username"], "admin")
            self.assertTrue(payload["isAdmin"])
            self.assertTrue(payload["isAuthenticated"])
            capabilities = payload["adminCapabilities"]
            self.assertEqual(capabilities, sorted(ADMIN_RBAC_ROLE_CAPABILITIES[SUPER_ADMIN_ROLE]))
            self.assertTrue(payload["canReadUsers"])
            self.assertTrue(payload["canReadUserActivity"])
            self.assertTrue(payload["canReadUserPortfolio"])
            self.assertTrue(payload["canWriteUserSecurity"])
            self.assertTrue(payload["canReadCostObservability"])
            self.assertTrue(payload["canReadOpsLogs"])
            self.assertTrue(payload["canReadProviders"])
            self.assertTrue(payload["canReadNotifications"])
            self.assertTrue(payload["canReadSystemConfig"])
            self.assertNotIn("passwordHash", payload)
            self.assertNotIn("sessionId", payload)
            self.assertNotIn("roles", payload)
            self.assertNotIn("roleMappings", payload)

    def test_login_response_includes_compatible_current_user_capability_contract(self) -> None:
        response = self._login_admin(password="secret123")
        payload = self._json_response_body(response)
        current_user = payload["currentUser"]

        self.assertTrue(payload["ok"])
        self.assertEqual(current_user["id"], BOOTSTRAP_ADMIN_USER_ID)
        self.assertEqual(current_user["username"], "admin")
        self.assertEqual(current_user["role"], "admin")
        self.assertTrue(current_user["isAdmin"])
        self.assertTrue(current_user["isAuthenticated"])
        self.assertEqual(
            current_user["adminCapabilities"],
            sorted(ADMIN_RBAC_ROLE_CAPABILITIES[SUPER_ADMIN_ROLE]),
        )
        self.assertTrue(current_user["canWriteUserSecurity"])
        self.assertTrue(current_user["canReadUserPortfolio"])

    def test_non_admin_current_user_has_no_admin_capability_summary(self) -> None:
        response = self._login_user(username="normal-user", password="secret123")
        self.assertEqual(response.status_code, 200)
        session_cookie = self._extract_session_cookie(response)

        status_response = asyncio.run(
            auth_endpoint.auth_status(
                self._build_request(cookies={auth.COOKIE_NAME: session_cookie})
            )
        )
        me_response = asyncio.run(
            auth_endpoint.auth_me(
                self._build_request(cookies={auth.COOKIE_NAME: session_cookie})
            )
        )

        for payload in (status_response["currentUser"], me_response):
            self.assertEqual(payload["username"], "normal-user")
            self.assertEqual(payload["role"], "user")
            self.assertFalse(payload["isAdmin"])
            self.assertEqual(payload["adminCapabilities"], [])
            for key in (
                "canReadUsers",
                "canReadUserActivity",
                "canReadUserPortfolio",
                "canWriteUserSecurity",
                "canReadCostObservability",
                "canReadOpsLogs",
                "canReadProviders",
                "canReadNotifications",
                "canReadSystemConfig",
            ):
                self.assertFalse(payload[key])

        self.db.create_or_update_app_user(
            user_id="non-bootstrap-admin",
            username="non-bootstrap-admin",
            display_name="Non-Bootstrap Admin",
            role=ROLE_ADMIN,
            password_hash=auth.hash_password_for_storage("scoped-admin-pass"),
            is_active=True,
        )
        admin_login = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(),
                auth_endpoint.LoginRequest(
                    username="non-bootstrap-admin",
                    password="scoped-admin-pass",
                ),
            )
        )
        self.assertEqual(admin_login.status_code, 200)
        admin_cookie = self._extract_session_cookie(admin_login)
        admin_status = asyncio.run(
            auth_endpoint.auth_status(self._build_request(cookies={auth.COOKIE_NAME: admin_cookie}))
        )
        admin_me = asyncio.run(
            auth_endpoint.auth_me(self._build_request(cookies={auth.COOKIE_NAME: admin_cookie}))
        )
        for payload in (
            self._json_response_body(admin_login)["currentUser"],
            admin_status["currentUser"],
            admin_me,
        ):
            self.assertTrue(payload["isAdmin"])
            self.assertEqual(payload["adminCapabilities"], [])
            for flag in CAPABILITY_FLAG_MAP:
                self.assertFalse(payload[flag])
        self.assertEqual(self.db.list_admin_user_roles("non-bootstrap-admin"), [])

    def test_unauthenticated_auth_status_reports_first_run_when_password_missing(self) -> None:
        data = asyncio.run(auth_endpoint.auth_status(self._build_request()))

        self.assertTrue(data["authEnabled"])
        self.assertFalse(data["loggedIn"])
        self.assertFalse(data["passwordSet"])
        self.assertEqual(data["setupState"], "no_password")
        self.assertIsNone(data["currentUser"])

    def test_current_user_capability_summary_exposes_no_sensitive_fields(self) -> None:
        response = self._login_admin(password="secret123")
        session_cookie = self._extract_session_cookie(response)
        payload = asyncio.run(
            auth_endpoint.auth_me(
                self._build_request(cookies={auth.COOKIE_NAME: session_cookie})
            )
        )
        text = json.dumps(payload, sort_keys=True).lower()

        for forbidden in (
            "password_hash",
            "passwordhash",
            "raw session",
            "sessionid",
            "cookie",
            "token",
            "api_key",
            "apikey",
            "secret",
            "broker credential",
            "brokercredential",
            "provider credential",
            "providercredential",
            ".env",
            "granted_by",
            "reason",
            "expiry",
            "rolemappings",
        ):
            self.assertNotIn(forbidden, text)

    def test_login_wrong_password_returns_401(self) -> None:
        first_response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(),
                auth_endpoint.LoginRequest(password="correct", passwordConfirm="correct"),
            )
        )
        self.assertEqual(first_response.status_code, 200)

        response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(),
                auth_endpoint.LoginRequest(password="wrong"),
            )
        )
        self.assertEqual(response.status_code, 401)

    def test_verify_password_bootstrap_sets_initial_password_and_returns_unlock_token(self) -> None:
        login_response = self._login_admin(password="bootstrap-pass")
        self.assertEqual(login_response.status_code, 200)
        session_cookie = self._extract_session_cookie(login_response)

        response = asyncio.run(
            auth_endpoint.auth_verify_password(
                self._build_request(cookies={auth.COOKIE_NAME: session_cookie}),
                auth_endpoint.VerifyPasswordRequest(
                    password="bootstrap-pass",
                ),
            )
        )

        self.assertEqual(response["ok"], True)
        self.assertTrue(response["unlockToken"])
        self.assertGreater(response["expiresInSeconds"], 0)
        self.assertTrue(auth.has_stored_password())

    def test_verify_password_rejects_wrong_password(self) -> None:
        first_response = self._login_admin(password="passwd6")
        self.assertEqual(first_response.status_code, 200)
        session_cookie = self._extract_session_cookie(first_response)

        response = asyncio.run(
            auth_endpoint.auth_verify_password(
                self._build_request(cookies={auth.COOKIE_NAME: session_cookie}),
                auth_endpoint.VerifyPasswordRequest(password="wrong-pass"),
            )
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn(b'"error":"invalid_login"', response.body)

    def test_reauth_succeeds_for_valid_current_admin_password(self) -> None:
        login_response = self._login_admin(password="passwd6")
        self.assertEqual(login_response.status_code, 200)
        session_cookie = self._extract_session_cookie(login_response)

        response = asyncio.run(
            auth_endpoint.auth_reauth(
                self._build_request(cookies={auth.COOKIE_NAME: session_cookie}),
                auth_endpoint.ReauthRequest(password="passwd6"),
            )
        )

        self.assertEqual(response["ok"], True)
        self.assertGreaterEqual(response["ttlSeconds"], 60)
        self.assertIn("reauthExpiresAt", response)
        text = json.dumps(response, ensure_ascii=False).lower()
        for forbidden in (
            "password_hash",
            "passwd6",
            "dsa_session",
            "cookie",
            "token",
            "api_key",
            "secret",
            ".env",
            "traceback",
        ):
            self.assertNotIn(forbidden, text)

    def test_reauth_rejects_wrong_password_safely(self) -> None:
        login_response = self._login_admin(password="passwd6")
        self.assertEqual(login_response.status_code, 200)
        session_cookie = self._extract_session_cookie(login_response)

        response = asyncio.run(
            auth_endpoint.auth_reauth(
                self._build_request(cookies={auth.COOKIE_NAME: session_cookie}),
                auth_endpoint.ReauthRequest(password="wrong-pass"),
            )
        )

        self.assertEqual(response.status_code, 401)
        body = self._json_response_body(response)
        self.assertEqual(body["error"], "invalid_login")
        text = json.dumps(body, ensure_ascii=False).lower()
        for forbidden in ("password_hash", "wrong-pass", "dsa_session", "cookie", "token", "secret", "traceback"):
            self.assertNotIn(forbidden, text)
        self.assertNotIn(b"wrong-pass", response.body)

    def test_legacy_bootstrap_hash_upgrades_on_successful_login(self) -> None:
        legacy_hash = self._legacy_hash("legacy-pass")
        (self.data_dir / ".admin_password_hash").write_text(legacy_hash, encoding="utf-8")
        auth.refresh_auth_state()

        response = self._login_admin(password="legacy-pass")

        self.assertEqual(response.status_code, 200)
        upgraded_file_hash = (self.data_dir / ".admin_password_hash").read_text(encoding="utf-8").strip()
        self.assertNotEqual(upgraded_file_hash, legacy_hash)
        self.assertTrue(upgraded_file_hash.startswith(auth.PASSWORD_KDF_PREFIX))
        self.assertTrue(auth.verify_password_hash_string("legacy-pass", upgraded_file_hash))
        mirrored_user = DatabaseManager.get_instance().get_app_user(BOOTSTRAP_ADMIN_USER_ID)
        self.assertIsNotNone(mirrored_user)
        self.assertEqual(getattr(mirrored_user, "password_hash", None), upgraded_file_hash)

    def test_wrong_bootstrap_password_does_not_upgrade_legacy_hash(self) -> None:
        legacy_hash = self._legacy_hash("legacy-pass")
        (self.data_dir / ".admin_password_hash").write_text(legacy_hash, encoding="utf-8")
        auth.refresh_auth_state()

        response = self._login_admin(password="wrong-pass")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            (self.data_dir / ".admin_password_hash").read_text(encoding="utf-8").strip(),
            legacy_hash,
        )

    def test_legacy_app_user_hash_upgrades_on_successful_login(self) -> None:
        legacy_hash = self._legacy_hash("legacy-pass")
        db = DatabaseManager.get_instance()
        db.create_or_update_app_user(
            user_id="user-legacy",
            username="legacy-user",
            display_name="Legacy User",
            role="user",
            password_hash=legacy_hash,
            is_active=True,
        )

        response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(),
                auth_endpoint.LoginRequest(username="legacy-user", password="legacy-pass"),
            )
        )

        self.assertEqual(response.status_code, 200)
        row = db.get_app_user("user-legacy")
        upgraded_hash = getattr(row, "password_hash", "")
        self.assertTrue(upgraded_hash.startswith(auth.PASSWORD_KDF_PREFIX))
        self.assertTrue(auth.verify_password_hash_string("legacy-pass", upgraded_hash))

    def test_wrong_app_user_password_does_not_upgrade_legacy_hash(self) -> None:
        legacy_hash = self._legacy_hash("legacy-pass")
        db = DatabaseManager.get_instance()
        db.create_or_update_app_user(
            user_id="user-legacy",
            username="legacy-user",
            display_name="Legacy User",
            role="user",
            password_hash=legacy_hash,
            is_active=True,
        )

        response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(),
                auth_endpoint.LoginRequest(username="legacy-user", password="wrong-pass"),
            )
        )

        self.assertEqual(response.status_code, 401)
        row = db.get_app_user("user-legacy")
        self.assertEqual(getattr(row, "password_hash", ""), legacy_hash)

    def test_reauth_succeeds_after_legacy_bootstrap_hash_upgrade(self) -> None:
        legacy_hash = self._legacy_hash("legacy-pass")
        (self.data_dir / ".admin_password_hash").write_text(legacy_hash, encoding="utf-8")
        auth.refresh_auth_state()
        login_response = self._login_admin(password="legacy-pass")
        self.assertEqual(login_response.status_code, 200)
        session_cookie = self._extract_session_cookie(login_response)
        upgraded_file_hash = (self.data_dir / ".admin_password_hash").read_text(encoding="utf-8").strip()
        self.assertTrue(upgraded_file_hash.startswith(auth.PASSWORD_KDF_PREFIX))

        response = asyncio.run(
            auth_endpoint.auth_reauth(
                self._build_request(cookies={auth.COOKIE_NAME: session_cookie}),
                auth_endpoint.ReauthRequest(password="legacy-pass"),
            )
        )

        self.assertEqual(response["ok"], True)
        text = json.dumps(response, ensure_ascii=False).lower()
        for forbidden in (
            "password_hash",
            "legacy-pass",
            "pbkdf2-sha256",
            "wolfystock",
            "cookie",
            "token",
            "secret",
        ):
            self.assertNotIn(forbidden, text)

    def test_unsupported_app_user_hash_fails_safely_without_exposure(self) -> None:
        unsupported_hash = "$wolfystock$kdf=v9$alg=future$params=x$salt=y$hash=z"
        db = DatabaseManager.get_instance()
        db.create_or_update_app_user(
            user_id="user-unsupported",
            username="unsupported-user",
            display_name="Unsupported User",
            role="user",
            password_hash=unsupported_hash,
            is_active=True,
        )

        response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(),
                auth_endpoint.LoginRequest(username="unsupported-user", password="user-pass"),
            )
        )

        self.assertEqual(response.status_code, 401)
        body = self._json_response_body(response)
        self.assertEqual(body["error"], "invalid_login")
        text = json.dumps(body, ensure_ascii=False)
        self.assertNotIn("user-pass", text)
        self.assertNotIn("wolfystock", text)
        self.assertEqual(
            getattr(db.get_app_user("user-unsupported"), "password_hash", None),
            unsupported_hash,
        )

    def test_reauth_rejects_unauthenticated_user(self) -> None:
        response = asyncio.run(
            auth_endpoint.auth_reauth(
                self._build_request(),
                auth_endpoint.ReauthRequest(password="passwd6"),
            )
        )

        self.assertEqual(response.status_code, 401)
        body = self._json_response_body(response)
        self.assertEqual(body["error"], "unauthorized")

    def test_logout_clears_cookie(self) -> None:
        response = asyncio.run(auth_endpoint.auth_logout(self._build_request()))
        self.assertEqual(response.status_code, 204)
        self.assertIn("dsa_session=", response.headers["set-cookie"])
        self.assertIn("Max-Age=0", response.headers["set-cookie"])
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("SameSite=lax", response.headers["set-cookie"])

    def test_logout_invalidates_existing_session(self) -> None:
        login_response = self._login_admin(password="passwd6")
        self.assertEqual(login_response.status_code, 200)
        session_cookie = self._extract_session_cookie(login_response)
        identity = auth.get_session_identity(session_cookie)
        self.assertIsNotNone(identity)
        self.assertIsNotNone(identity.session_id)
        self.assertTrue(auth.verify_session(session_cookie))

        logout_response = asyncio.run(
            auth_endpoint.auth_logout(
                self._build_request(cookies={auth.COOKIE_NAME: session_cookie})
            )
        )

        self.assertEqual(logout_response.status_code, 204)
        self.assertFalse(auth.verify_session(session_cookie))
        session_row = DatabaseManager.get_instance().get_app_user_session(identity.session_id)
        self.assertIsNotNone(session_row)
        self.assertIsNotNone(session_row.revoked_at)

    def test_logout_invalidates_signed_compatibility_session_without_sid(self) -> None:
        login_response = self._login_admin(password="passwd6")
        authoritative_session = self._extract_session_cookie(login_response)
        compatibility_session = auth.create_session()
        compatibility_identity = auth.get_session_identity(compatibility_session)
        self.assertIsNotNone(compatibility_identity)
        compatibility_revocation_id = auth.get_session_revocation_id(
            compatibility_session,
            compatibility_identity,
        )
        self.assertTrue(auth.verify_session(authoritative_session))
        self.assertTrue(auth.verify_session(compatibility_session))

        logout_response = asyncio.run(
            auth_endpoint.auth_logout(
                self._build_request(cookies={auth.COOKIE_NAME: compatibility_session})
            )
        )

        self.assertEqual(logout_response.status_code, 204)
        self.assertIn("Max-Age=0", logout_response.headers["set-cookie"])
        self.assertFalse(auth.verify_session(compatibility_session))
        self.assertTrue(auth.verify_session(authoritative_session))
        compatibility_row = DatabaseManager.get_instance().get_app_user_session(
            compatibility_revocation_id
        )
        self.assertIsNotNone(compatibility_row)
        self.assertIsNotNone(compatibility_row.revoked_at)
        rejected = asyncio.run(
            auth_endpoint.auth_me(
                self._build_request(cookies={auth.COOKIE_NAME: compatibility_session})
            )
        )
        self.assertEqual(rejected.status_code, 401)

    def test_logout_terminates_legacy_identity_without_constructing_legacy_cookie(self) -> None:
        login_response = self._login_admin(password="passwd6")
        authoritative_session = self._extract_session_cookie(login_response)
        compatibility_session = auth.create_session()
        now = int(datetime.now(timezone.utc).timestamp())
        legacy_identity = auth.SessionIdentity(
            user_id=BOOTSTRAP_ADMIN_USER_ID,
            username="admin",
            role="admin",
            session_id=None,
            issued_at=now,
            expires_at=now + auth._get_session_max_age_seconds(),
            legacy_admin=True,
        )

        with patch.object(auth, "_resolve_v2_identity", return_value=None), patch.object(
            auth,
            "_resolve_legacy_admin_session",
            return_value=legacy_identity,
        ):
            logout_response = asyncio.run(
                auth_endpoint.auth_logout(
                    self._build_request(cookies={auth.COOKIE_NAME: compatibility_session})
                )
            )

        self.assertEqual(logout_response.status_code, 204)
        self.assertIn("Max-Age=0", logout_response.headers["set-cookie"])
        self.assertFalse(auth.verify_session(compatibility_session))
        self.assertTrue(auth.verify_session(authoritative_session))

    def test_logout_without_session_still_clears_cookie(self) -> None:
        response = asyncio.run(auth_endpoint.auth_logout(self._build_request()))
        self.assertEqual(response.status_code, 204)
        self.assertIn("dsa_session=", response.headers["set-cookie"])
        self.assertIn("Max-Age=0", response.headers["set-cookie"])

    def test_logout_cookie_expiration_preserves_https_security_attributes(self) -> None:
        request = self._build_request()
        request.url.scheme = "https"

        response = asyncio.run(auth_endpoint.auth_logout(request))

        self.assertEqual(response.status_code, 204)
        set_cookie = response.headers["set-cookie"]
        self.assertIn("Max-Age=0", set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=lax", set_cookie)
        self.assertIn("Path=/", set_cookie)
        self.assertIn("Secure", set_cookie)

    def test_reset_password_request_requires_identifier(self) -> None:
        response = asyncio.run(
            auth_endpoint.auth_request_password_reset(
                auth_endpoint.PasswordResetRequest(identifier=""),
            )
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'"error":"identifier_required"', response.body)

    def test_reset_password_request_returns_generic_success_for_unknown_identifier(self) -> None:
        response = asyncio.run(
            auth_endpoint.auth_request_password_reset(
                auth_endpoint.PasswordResetRequest(identifier="missing-user"),
            )
        )

        self.assertEqual(response.status_code, 202)
        self.assertIn(b'"ok":true', response.body)

    def test_reset_password_request_logs_only_hashed_identifier_without_match_bit(self) -> None:
        raw_identifier = "Sensitive.User+Reset@example.com"
        expected_hash = auth.safe_identifier_hash(raw_identifier, prefix="acct")

        with self.assertLogs("api.v1.endpoints.auth", level="INFO") as captured:
            response = asyncio.run(
                auth_endpoint.auth_request_password_reset(
                    auth_endpoint.PasswordResetRequest(identifier=raw_identifier),
                )
            )

        self.assertEqual(response.status_code, 202)
        log_output = "\n".join(captured.output)
        self.assertIn(str(expected_hash), log_output)
        self.assertNotIn(raw_identifier, log_output)
        self.assertNotIn(raw_identifier.lower(), log_output.lower())
        self.assertNotRegex(log_output, r"\bmatched\s*=")
        self.assertNotRegex(log_output, r"\bmatched_(?:user|account)\b")
        self.assertNotIn("True", log_output)
        self.assertNotIn("False", log_output)

    def test_serialize_user_notification_preferences_uses_auth_repository_boundary(self) -> None:
        repo = MagicMock()
        repo.get_user_notification_preferences.return_value = {
            "channel": "email",
            "enabled": True,
            "email": "user@example.com",
            "email_enabled": True,
            "discord_enabled": False,
            "discord_webhook": None,
            "updated_at": "2026-04-17T08:00:00+08:00",
        }

        with patch("api.v1.endpoints.auth.AuthRepository", create=True) as repo_cls:
            repo_cls.return_value = repo
            payload = auth_endpoint._serialize_user_notification_preferences("user-1")

        repo.get_user_notification_preferences.assert_called_once_with("user-1")
        self.assertEqual(payload["email"], "user@example.com")
        self.assertTrue(payload["enabled"])

    def test_persist_session_for_user_uses_auth_repository_boundary(self) -> None:
        repo = MagicMock()
        expires_at = datetime(2026, 4, 17, 8, 0, 0)

        with patch("api.v1.endpoints.auth.AuthRepository", create=True) as repo_cls, \
             patch("api.v1.endpoints.auth.get_session_expiry_datetime", return_value=expires_at), \
             patch("api.v1.endpoints.auth.create_session", return_value="signed-session"):
            repo_cls.return_value = repo
            session_value = auth_endpoint._persist_session_for_user(
                request=self._build_request(),
                user_id="user-1",
                username="alice",
                role="user",
            )

        repo.create_app_user_session.assert_called_once_with(
            session_id=ANY,
            user_id="user-1",
            expires_at=expires_at,
        )
        self.assertEqual(session_value, "signed-session")

    def test_change_password_requires_session(self) -> None:
        first_response = self._login_admin(password="oldpass6")
        self.assertEqual(first_response.status_code, 200)
        session_cookie = self._extract_session_cookie(first_response)

        response = asyncio.run(
            auth_endpoint.auth_change_password(
                self._build_request(cookies={auth.COOKIE_NAME: session_cookie}),
                auth_endpoint.ChangePasswordRequest(
                    currentPassword="oldpass6",
                    newPassword="newpass6",
                    newPasswordConfirm="newpass6",
                )
            )
        )
        self.assertEqual(response.status_code, 204)

    def test_bootstrap_change_password_revokes_existing_admin_session(self) -> None:
        first_response = self._login_admin(password="oldpass6")
        self.assertEqual(first_response.status_code, 200)
        session_cookie = self._extract_session_cookie(first_response)
        old_identity = auth.get_session_identity(session_cookie)
        self.assertIsNotNone(old_identity)
        self.assertIsNotNone(old_identity.session_id)

        auth.mark_admin_session_reauthenticated(
            user_id=old_identity.user_id,
            session_id=old_identity.session_id,
        )
        self.assertIsNotNone(
            auth.get_admin_session_reauthenticated_at(
                user_id=old_identity.user_id,
                session_id=old_identity.session_id,
            )
        )

        response = asyncio.run(
            auth_endpoint.auth_change_password(
                self._build_request(cookies={auth.COOKIE_NAME: session_cookie}),
                auth_endpoint.ChangePasswordRequest(
                    currentPassword="oldpass6",
                    newPassword="newpass6",
                    newPasswordConfirm="newpass6",
                )
            )
        )

        self.assertEqual(response.status_code, 204)
        row = DatabaseManager.get_instance().get_app_user_session(old_identity.session_id)
        self.assertIsNotNone(row)
        self.assertIsNotNone(row.revoked_at)
        self.assertFalse(auth.verify_session(session_cookie))
        self.assertIsNone(
            auth.get_admin_session_reauthenticated_at(
                user_id=old_identity.user_id,
                session_id=old_identity.session_id,
            )
        )

        rejected = asyncio.run(
            auth_endpoint.auth_me(self._build_request(cookies={auth.COOKIE_NAME: session_cookie}))
        )
        self.assertEqual(rejected.status_code, 401)

    def test_change_password_wrong_current_rejected(self) -> None:
        first_response = self._login_admin(password="actual6")
        self.assertEqual(first_response.status_code, 200)
        session_cookie = self._extract_session_cookie(first_response)

        response = asyncio.run(
            auth_endpoint.auth_change_password(
                self._build_request(cookies={auth.COOKIE_NAME: session_cookie}),
                auth_endpoint.ChangePasswordRequest(
                    currentPassword="wrong",
                    newPassword="new123",
                    newPasswordConfirm="new123",
                )
            )
        )
        self.assertEqual(response.status_code, 400)

    def test_protected_api_returns_401_without_session(self) -> None:
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/system/config",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "root_path": "",
        }
        request = Request(scope)
        middleware = AuthMiddleware(app=MagicMock())

        with patch("api.middlewares.auth.is_auth_enabled", return_value=True):
            response = asyncio.run(middleware.dispatch(request, AsyncMock(return_value=Response(status_code=200))))

        self.assertEqual(response.status_code, 401)
        body = self._json_response_body(response)
        self.assertEqual(body["error"], "unauthorized")
        self.assertEqual(body["code"], "unauthorized")
        self.assertEqual(body["reason"], "unauthorized")
        self.assertEqual(body["status"], 401)
        self.assertEqual(body["consumerSafeMessage"], "Login required")

    def test_protected_api_options_preflight_reaches_cors_without_session(self) -> None:
        scope = {
            "type": "http",
            "method": "OPTIONS",
            "path": "/api/v1/admin/notification-channels",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "root_path": "",
        }
        request = Request(scope)
        middleware = AuthMiddleware(app=MagicMock())
        call_next = AsyncMock(return_value=Response(status_code=204))

        with patch("api.middlewares.auth.is_auth_enabled", return_value=True):
            response = asyncio.run(middleware.dispatch(request, call_next))

        self.assertEqual(response.status_code, 204)
        call_next.assert_awaited_once()

    def test_logout_cleanup_reaches_endpoint_without_valid_session_when_auth_enabled(self) -> None:
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/logout",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "root_path": "",
        }
        request = Request(scope)
        middleware = AuthMiddleware(app=MagicMock())
        call_next = AsyncMock(return_value=Response(status_code=204))

        with patch("api.middlewares.auth.is_auth_enabled", return_value=True):
            response = asyncio.run(middleware.dispatch(request, call_next))

        self.assertEqual(response.status_code, 204)
        call_next.assert_awaited_once()

    def test_reset_password_request_is_exempt_from_auth_middleware(self) -> None:
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/reset-password/request",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "root_path": "",
        }
        request = Request(scope)
        middleware = AuthMiddleware(app=MagicMock())
        call_next = AsyncMock(return_value=Response(status_code=202))

        with patch("api.middlewares.auth.is_auth_enabled", return_value=True):
            response = asyncio.run(middleware.dispatch(request, call_next))

        self.assertEqual(response.status_code, 202)
        call_next.assert_awaited_once()

    def test_protected_api_accessible_with_session(self) -> None:
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/system/config",
            "headers": [(b"cookie", b"dsa_session=test-session")],
            "query_string": b"",
            "scheme": "http",
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "root_path": "",
        }
        request = Request(scope)
        middleware = AuthMiddleware(app=MagicMock())
        next_response = Response(status_code=200)
        call_next = AsyncMock(return_value=next_response)

        with patch("api.middlewares.auth.is_auth_enabled", return_value=True):
            with patch(
                "api.middlewares.auth.resolve_current_user",
                return_value=CurrentUser(
                    user_id="user-1",
                    username="alice",
                    display_name="Alice",
                    role="user",
                    is_admin=False,
                    is_authenticated=True,
                    transitional=False,
                    auth_enabled=True,
                    session_id="session-1",
                ),
            ):
                response = asyncio.run(middleware.dispatch(request, call_next))

        self.assertEqual(response.status_code, 200)
        call_next.assert_awaited_once()

    def test_auth_settings_requires_session_when_auth_enabled(self) -> None:
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/settings",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "root_path": "",
        }
        request = Request(scope)
        middleware = AuthMiddleware(app=MagicMock())

        with patch("api.middlewares.auth.is_auth_enabled", return_value=True):
            response = asyncio.run(middleware.dispatch(request, AsyncMock(return_value=Response(status_code=200))))

        self.assertEqual(response.status_code, 401)

    def test_auth_settings_is_reachable_when_auth_disabled(self) -> None:
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/settings",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "root_path": "",
        }
        request = Request(scope)
        middleware = AuthMiddleware(app=MagicMock())
        next_response = Response(status_code=200)
        call_next = AsyncMock(return_value=next_response)

        with patch("api.middlewares.auth.is_auth_enabled", return_value=False):
            response = asyncio.run(middleware.dispatch(request, call_next))

        self.assertEqual(response.status_code, 200)
        call_next.assert_awaited_once()

    def test_verify_password_endpoint_is_exempt_when_auth_enabled(self) -> None:
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/verify-password",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "root_path": "",
        }
        request = Request(scope)
        middleware = AuthMiddleware(app=MagicMock())
        next_response = Response(status_code=200)
        call_next = AsyncMock(return_value=next_response)

        with patch("api.middlewares.auth.is_auth_enabled", return_value=True):
            response = asyncio.run(middleware.dispatch(request, call_next))

        self.assertEqual(response.status_code, 200)
        call_next.assert_awaited_once()

    def test_auth_settings_enable_sets_initial_password_and_logs_in(self) -> None:
        self.env_path.write_text(
            "STOCK_LIST=600519\nGEMINI_API_KEY=test\nADMIN_AUTH_ENABLED=false\n",
            encoding="utf-8",
        )
        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            auth.refresh_auth_state()

            response = asyncio.run(
                auth_endpoint.auth_update_settings(
                    self._build_request(),
                    auth_endpoint.AuthSettingsRequest(
                        authEnabled=True,
                        password="initpass123",
                        passwordConfirm="initpass123",
                    ),
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"authEnabled":true', response.body)
        self.assertIn(b'"loggedIn":true', response.body)
        self.assertIn(b'"passwordSet":true', response.body)
        self.assertIn("dsa_session=", response.headers["set-cookie"])
        self.assertIn("ADMIN_AUTH_ENABLED=true", self.env_path.read_text(encoding="utf-8"))

    def test_auth_settings_enable_requires_password_when_missing(self) -> None:
        self.env_path.write_text(
            "STOCK_LIST=600519\nGEMINI_API_KEY=test\nADMIN_AUTH_ENABLED=false\n",
            encoding="utf-8",
        )
        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            auth.refresh_auth_state()

            response = asyncio.run(
                auth_endpoint.auth_update_settings(
                    self._build_request(),
                    auth_endpoint.AuthSettingsRequest(authEnabled=True),
                )
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'"error":"password_required"', response.body)

    def test_auth_settings_rechecks_password_before_initial_write(self) -> None:
        self.env_path.write_text(
            "STOCK_LIST=600519\nGEMINI_API_KEY=test\nADMIN_AUTH_ENABLED=false\n",
            encoding="utf-8",
        )
        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            auth.refresh_auth_state()

            with patch.object(
                auth_endpoint,
                "has_stored_password",
                side_effect=[False, True],
            ) as has_password_mock:
                with patch.object(auth_endpoint, "set_initial_password") as set_password_mock:
                    response = asyncio.run(
                        auth_endpoint.auth_update_settings(
                            self._build_request(),
                            auth_endpoint.AuthSettingsRequest(
                                authEnabled=True,
                                password="initpass123",
                                passwordConfirm="initpass123",
                            ),
                        )
                    )

        self.assertEqual(has_password_mock.call_count, 2)
        set_password_mock.assert_not_called()
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'"error":"password_already_set"', response.body)

    def test_auth_settings_disable_clears_cookie_and_hides_password_state(self) -> None:
        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            login_response = self._login_admin(password="passwd6")
            self.assertEqual(login_response.status_code, 200)
            session_cookie = self._extract_session_cookie(login_response)
            identity = auth.get_session_identity(session_cookie)
            self.assertIsNotNone(identity)
            auth.mark_admin_session_reauthenticated(user_id=identity.user_id, session_id=identity.session_id)
            response = asyncio.run(
                auth_endpoint.auth_update_settings(
                    self._build_request(cookies={auth.COOKIE_NAME: session_cookie}),
                    auth_endpoint.AuthSettingsRequest(authEnabled=False, currentPassword="passwd6"),
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"authEnabled":false', response.body)
        self.assertIn(b'"loggedIn":false', response.body)
        self.assertIn(b'"passwordSet":false', response.body)
        self.assertIn("ADMIN_AUTH_ENABLED=false", self.env_path.read_text(encoding="utf-8"))
        self.assertIn("dsa_session=", response.headers["set-cookie"])

        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            status_response = asyncio.run(auth_endpoint.auth_status(self._build_request()))
        self.assertFalse(status_response["authEnabled"])
        self.assertFalse(status_response["passwordSet"])

    def test_auth_settings_disable_requires_authenticated_admin_when_auth_enabled(self) -> None:
        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            auth.set_initial_password("passwd6")
            response = asyncio.run(
                auth_endpoint.auth_update_settings(
                    self._build_request(),
                    auth_endpoint.AuthSettingsRequest(authEnabled=False),
                )
            )

        self.assertEqual(response.status_code, 401)
        self.assertIn(b'"error":"unauthorized"', response.body)
        self.assertIn("ADMIN_AUTH_ENABLED=true", self.env_path.read_text(encoding="utf-8"))

    def test_auth_settings_requires_system_config_write_capability(self) -> None:
        current_user = CurrentUser(
            user_id="admin-no-system-write",
            username="admin-no-system-write",
            display_name="Admin",
            role="admin",
            is_admin=True,
            is_authenticated=True,
            transitional=False,
            auth_enabled=True,
            session_id="session-no-system-write",
            admin_capabilities=(),
        )

        with patch.object(auth_endpoint, "resolve_current_user", return_value=current_user):
            with patch.object(auth_endpoint, "_apply_auth_enabled", return_value=True) as apply_mock:
                response = asyncio.run(
                    auth_endpoint.auth_update_settings(
                        self._build_request(cookies={auth.COOKIE_NAME: "signed-session"}),
                        auth_endpoint.AuthSettingsRequest(authEnabled=False),
                    )
                )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._json_response_body(response)["detail"]["error"], "admin_capability_required")
        apply_mock.assert_not_called()

    def test_auth_settings_requires_unlock_or_recent_reauth_for_system_config_write(self) -> None:
        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            login_response = self._login_admin(password="passwd6")
            self.assertEqual(login_response.status_code, 200)
            session_cookie = self._extract_session_cookie(login_response)

            with patch.object(auth_endpoint, "_apply_auth_enabled", return_value=True) as apply_mock:
                response = asyncio.run(
                    auth_endpoint.auth_update_settings(
                        self._build_request(cookies={auth.COOKIE_NAME: session_cookie}),
                        auth_endpoint.AuthSettingsRequest(authEnabled=False),
                    )
                )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._json_response_body(response)["detail"]["error"], "admin_unlock_required")
        apply_mock.assert_not_called()

    def test_auth_settings_allows_system_config_write_after_recent_reauth(self) -> None:
        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            login_response = self._login_admin(password="passwd6")
            self.assertEqual(login_response.status_code, 200)
            session_cookie = self._extract_session_cookie(login_response)
            identity = auth.get_session_identity(session_cookie)
            self.assertIsNotNone(identity)
            auth.mark_admin_session_reauthenticated(user_id=identity.user_id, session_id=identity.session_id)

            response = asyncio.run(
                auth_endpoint.auth_update_settings(
                    self._build_request(cookies={auth.COOKIE_NAME: session_cookie}),
                    auth_endpoint.AuthSettingsRequest(authEnabled=False),
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"authEnabled":false', response.body)
        self.assertIn("ADMIN_AUTH_ENABLED=false", self.env_path.read_text(encoding="utf-8"))

    def test_auth_settings_allows_system_config_write_with_unlock_token(self) -> None:
        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            login_response = self._login_admin(password="passwd6")
            self.assertEqual(login_response.status_code, 200)
            session_cookie = self._extract_session_cookie(login_response)
            identity = auth.get_session_identity(session_cookie)
            self.assertIsNotNone(identity)
            unlock_token = auth.create_admin_unlock_token(
                user_id=identity.user_id,
                username=identity.username,
                role=identity.role,
            )
            self.assertTrue(unlock_token)

            response = asyncio.run(
                auth_endpoint.auth_update_settings(
                    self._build_request(
                        cookies={auth.COOKIE_NAME: session_cookie},
                        headers={"X-Admin-Unlock-Token": unlock_token},
                    ),
                    auth_endpoint.AuthSettingsRequest(authEnabled=False),
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"authEnabled":false', response.body)
        self.assertIn("ADMIN_AUTH_ENABLED=false", self.env_path.read_text(encoding="utf-8"))

    def test_auth_settings_toggle_fails_when_secret_rotation_fails(self) -> None:
        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            login_response = self._login_admin(password="passwd6")
            self.assertEqual(login_response.status_code, 200)
            session_cookie = self._extract_session_cookie(login_response)
            identity = auth.get_session_identity(session_cookie)
            self.assertIsNotNone(identity)
            auth.mark_admin_session_reauthenticated(user_id=identity.user_id, session_id=identity.session_id)
            with patch.object(auth_endpoint, "rotate_session_secret", return_value=False):
                response = asyncio.run(
                    auth_endpoint.auth_update_settings(
                        self._build_request(cookies={auth.COOKIE_NAME: session_cookie}),
                        auth_endpoint.AuthSettingsRequest(authEnabled=False, currentPassword="passwd6"),
                    )
                )

        self.assertEqual(response.status_code, 500)
        self.assertIn(b'"error":"internal_error"', response.body)
        self.assertIn("ADMIN_AUTH_ENABLED=true", self.env_path.read_text(encoding="utf-8"))

    def test_auth_settings_enable_with_existing_password_reuses_stored_password(self) -> None:
        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            login_response = self._login_admin(password="passwd6")
            self.assertEqual(login_response.status_code, 200)
            session_cookie = self._extract_session_cookie(login_response)
            identity = auth.get_session_identity(session_cookie)
            self.assertIsNotNone(identity)
            auth.mark_admin_session_reauthenticated(user_id=identity.user_id, session_id=identity.session_id)
            disable_response = asyncio.run(
                auth_endpoint.auth_update_settings(
                    self._build_request(cookies={auth.COOKIE_NAME: session_cookie}),
                    auth_endpoint.AuthSettingsRequest(authEnabled=False, currentPassword="passwd6"),
                )
            )
        self.assertEqual(disable_response.status_code, 200)

        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            enable_response = asyncio.run(
                auth_endpoint.auth_update_settings(
                    self._build_request(),
                    auth_endpoint.AuthSettingsRequest(authEnabled=True, currentPassword="passwd6"),
                )
            )

        self.assertEqual(enable_response.status_code, 200)
        self.assertIn(b'"authEnabled":true', enable_response.body)
        self.assertIn(b'"passwordSet":true', enable_response.body)
        self.assertIn(b'"loggedIn":true', enable_response.body)
        self.assertIn("dsa_session=", enable_response.headers["set-cookie"])

    def test_auth_settings_enable_with_existing_password_requires_current_password(self) -> None:
        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            login_response = self._login_admin(password="passwd6")
            self.assertEqual(login_response.status_code, 200)
            session_cookie = self._extract_session_cookie(login_response)
            identity = auth.get_session_identity(session_cookie)
            self.assertIsNotNone(identity)
            auth.mark_admin_session_reauthenticated(user_id=identity.user_id, session_id=identity.session_id)
            disable_response = asyncio.run(
                auth_endpoint.auth_update_settings(
                    self._build_request(cookies={auth.COOKIE_NAME: session_cookie}),
                    auth_endpoint.AuthSettingsRequest(authEnabled=False, currentPassword="passwd6"),
                )
            )
        self.assertEqual(disable_response.status_code, 200)

        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            response = asyncio.run(
                auth_endpoint.auth_update_settings(
                    self._build_request(),
                    auth_endpoint.AuthSettingsRequest(authEnabled=True),
                )
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'"error":"current_required"', response.body)
        self.assertIn("ADMIN_AUTH_ENABLED=false", self.env_path.read_text(encoding="utf-8"))

    def test_auth_settings_enable_with_existing_password_rejects_wrong_current_password(self) -> None:
        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            login_response = self._login_admin(password="passwd6")
            self.assertEqual(login_response.status_code, 200)
            session_cookie = self._extract_session_cookie(login_response)
            identity = auth.get_session_identity(session_cookie)
            self.assertIsNotNone(identity)
            auth.mark_admin_session_reauthenticated(user_id=identity.user_id, session_id=identity.session_id)
            disable_response = asyncio.run(
                auth_endpoint.auth_update_settings(
                    self._build_request(cookies={auth.COOKIE_NAME: session_cookie}),
                    auth_endpoint.AuthSettingsRequest(authEnabled=False, currentPassword="passwd6"),
                )
            )
        self.assertEqual(disable_response.status_code, 200)

        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            response = asyncio.run(
                auth_endpoint.auth_update_settings(
                    self._build_request(),
                    auth_endpoint.AuthSettingsRequest(authEnabled=True, currentPassword="wrongpass"),
                )
            )

        self.assertEqual(response.status_code, 401)
        self.assertIn(b'"error":"invalid_password"', response.body)
        self.assertIn("ADMIN_AUTH_ENABLED=false", self.env_path.read_text(encoding="utf-8"))

    def test_auth_settings_enable_rolls_back_when_session_creation_fails(self) -> None:
        self.env_path.write_text(
            "STOCK_LIST=600519\nGEMINI_API_KEY=test\nADMIN_AUTH_ENABLED=false\n",
            encoding="utf-8",
        )
        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            auth.refresh_auth_state()
            with patch.object(auth_endpoint, "create_session", return_value=""):
                response = asyncio.run(
                    auth_endpoint.auth_update_settings(
                        self._build_request(),
                        auth_endpoint.AuthSettingsRequest(
                            authEnabled=True,
                            password="initpass123",
                            passwordConfirm="initpass123",
                        ),
                    )
                )

        self.assertEqual(response.status_code, 500)
        self.assertIn(b'"error":"internal_error"', response.body)
        self.assertIn("ADMIN_AUTH_ENABLED=false", self.env_path.read_text(encoding="utf-8"))

    def test_auth_settings_rejects_overwriting_existing_password(self) -> None:
        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            login_response = self._login_admin(password="passwd6")
            self.assertEqual(login_response.status_code, 200)
            session_cookie = self._extract_session_cookie(login_response)
            identity = auth.get_session_identity(session_cookie)
            self.assertIsNotNone(identity)
            auth.mark_admin_session_reauthenticated(user_id=identity.user_id, session_id=identity.session_id)
            disable_response = asyncio.run(
                auth_endpoint.auth_update_settings(
                    self._build_request(cookies={auth.COOKIE_NAME: session_cookie}),
                    auth_endpoint.AuthSettingsRequest(authEnabled=False, currentPassword="passwd6"),
                )
            )
            self.assertEqual(disable_response.status_code, 200)

        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            response = asyncio.run(
                auth_endpoint.auth_update_settings(
                    self._build_request(),
                    auth_endpoint.AuthSettingsRequest(
                        authEnabled=True,
                        password="newpass123",
                        passwordConfirm="newpass123",
                    ),
                )
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'"error":"password_already_set"', response.body)

    def test_auth_settings_enable_requires_valid_session_cookie_against_toctou(self) -> None:
        """Verify fix for P1 vulnerability: passing authEnabled=True without currentPassword
        must be rejected if the caller lacks a cryptographically valid session, even if
        is_auth_enabled() evaluates to True during handler execution (TOCTOU race condition).
        """
        self.env_path.write_text(
            "STOCK_LIST=600519\nGEMINI_API_KEY=test\nADMIN_AUTH_ENABLED=false\n",
            encoding="utf-8",
        )
        with patch.object(auth, "_is_auth_enabled_from_env", side_effect=self._read_auth_enabled_from_env):
            # 1. Setup an existing password, auth is currently disabled
            auth.set_initial_password("passwd6")

            # 2. Simulate the race condition:
            # The middleware let the request through because auth was supposedly False.
            # But just before the handler runs, another thread enables auth.
            self.env_path.write_text(
                "STOCK_LIST=600519\nGEMINI_API_KEY=test\nADMIN_AUTH_ENABLED=true\n",
                encoding="utf-8",
            )
            auth.refresh_auth_state()  # simulate the flip to True

            # 3. The attacker tries to re-enable auth without a password or valid cookie
            response = asyncio.run(
                auth_endpoint.auth_update_settings(
                    self._build_request(cookies={"dsa_session": "invalid"}),
                    auth_endpoint.AuthSettingsRequest(authEnabled=True),
                )
            )

        # 4. Must be rejected because auth is enabled and they do not resolve to an admin identity.
        self.assertEqual(response.status_code, 401)
        self.assertIn(b'"error":"unauthorized"', response.body)


if __name__ == "__main__":
    unittest.main()
