# -*- coding: utf-8 -*-
"""RBAC compatibility-layer tests for admin capability metadata."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import inspect, select

import src.auth as auth
from api.deps import CurrentUser, require_admin_user
from src.admin_rbac import (
    ADMIN_RBAC_CAPABILITIES,
    ADMIN_RBAC_ROLES,
    SUPER_ADMIN_ROLE,
    SUPPORT_ADMIN_ROLE,
    expand_admin_capabilities,
    has_admin_capability,
)
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID, ROLE_ADMIN, ROLE_USER
from src.storage import AdminRole, AdminRoleCapability, AdminUserRole, DatabaseManager


def _current_user(
    *,
    role: str,
    is_admin: bool,
    admin_capabilities: tuple[str, ...] = (),
    legacy_admin: bool = False,
) -> CurrentUser:
    return CurrentUser(
        user_id="user-1",
        username="alice",
        display_name="Alice",
        role=role,
        is_admin=is_admin,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="raw-session-id",
        legacy_admin=legacy_admin,
        admin_capabilities=admin_capabilities,
    )


class AdminRbacCompatibilityTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "rbac.db"
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")

    def tearDown(self) -> None:
        auth._admin_reauth_markers = {}
        auth._session_secret = None
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def test_storage_initialization_seeds_admin_rbac_roles_and_capabilities(self) -> None:
        inspector = inspect(self.db._engine)
        self.assertIn("admin_roles", inspector.get_table_names())
        self.assertIn("admin_role_capabilities", inspector.get_table_names())
        self.assertIn("admin_user_roles", inspector.get_table_names())

        with self.db.get_session() as session:
            roles = {row.role_key for row in session.execute(select(AdminRole)).scalars().all()}
            self.assertEqual(set(ADMIN_RBAC_ROLES), roles)

            capability_rows = session.execute(
                select(AdminRoleCapability).where(AdminRoleCapability.role_key == SUPER_ADMIN_ROLE)
            ).scalars().all()
            self.assertEqual(set(ADMIN_RBAC_CAPABILITIES), {row.capability for row in capability_rows})

    def test_super_admin_capabilities_expand_from_seeded_role(self) -> None:
        capabilities = self.db.list_admin_role_capabilities(SUPER_ADMIN_ROLE)
        self.assertEqual(set(ADMIN_RBAC_CAPABILITIES), set(capabilities))

    def test_legacy_admin_expands_to_super_admin_equivalent_capabilities(self) -> None:
        user = _current_user(role=ROLE_ADMIN, is_admin=True)

        capabilities = expand_admin_capabilities(user)

        self.assertEqual(set(ADMIN_RBAC_CAPABILITIES), capabilities)
        self.assertTrue(has_admin_capability(user, "users:read"))
        self.assertTrue(has_admin_capability(user, "quant:admin:write"))

    def test_non_admin_has_no_admin_capabilities(self) -> None:
        user = _current_user(role=ROLE_USER, is_admin=False)

        self.assertEqual(set(), expand_admin_capabilities(user))
        self.assertFalse(has_admin_capability(user, "users:read"))

    def test_unknown_capability_is_false(self) -> None:
        user = _current_user(role=ROLE_ADMIN, is_admin=True)

        self.assertFalse(has_admin_capability(user, "secrets:read"))

    def test_require_admin_user_behavior_is_unchanged(self) -> None:
        admin = _current_user(role=ROLE_ADMIN, is_admin=True)
        regular = _current_user(role=ROLE_USER, is_admin=False)

        self.assertIs(require_admin_user(admin), admin)
        with self.assertRaises(HTTPException) as exc:
            require_admin_user(regular)
        self.assertEqual(exc.exception.status_code, 403)
        self.assertEqual(exc.exception.detail["error"], "admin_required")

    def test_explicit_capability_grant_passes_required_dependency_without_coarse_fallback(self) -> None:
        from api.deps import require_admin_capability

        admin = _current_user(role=ROLE_ADMIN, is_admin=True, admin_capabilities=("users:read",))
        dependency = require_admin_capability("users:read")

        self.assertIs(dependency(admin), admin)

    def test_missing_capability_cache_fails_closed_for_capability_dependency(self) -> None:
        from api.deps import require_admin_capability

        admin = _current_user(role=ROLE_ADMIN, is_admin=True)
        dependency = require_admin_capability("users:read")

        with self.assertRaises(HTTPException) as exc:
            dependency(admin)
        self.assertEqual(exc.exception.status_code, 403)
        self.assertEqual(exc.exception.detail["error"], "admin_capability_required")
        detail_text = str(exc.exception.detail).lower()
        self.assertNotIn("raw-session-id", detail_text)
        self.assertNotIn("users:read", detail_text)

    def test_transitional_legacy_admin_still_passes_required_capability_dependency(self) -> None:
        from api.deps import require_admin_capability

        admin = _current_user(role=ROLE_ADMIN, is_admin=True, legacy_admin=True)
        dependency = require_admin_capability("users:read")

        self.assertTrue(admin.legacy_admin)
        self.assertIs(dependency(admin), admin)

    def test_required_capability_dependency_rejects_non_admin(self) -> None:
        from api.deps import require_admin_capability

        regular = _current_user(role=ROLE_USER, is_admin=False)
        dependency = require_admin_capability("users:read")

        with self.assertRaises(HTTPException) as exc:
            dependency(regular)
        self.assertEqual(exc.exception.status_code, 403)
        self.assertEqual(exc.exception.detail["error"], "admin_required")

    def test_required_capability_dependency_rejects_scoped_admin_without_capability(self) -> None:
        from api.deps import require_admin_capability

        self.db.create_or_update_app_user(
            user_id="support-admin-1",
            username="support",
            display_name="Support",
            role=ROLE_ADMIN,
            password_hash=None,
            is_active=True,
        )
        with self.db.get_session() as session:
            session.add(AdminUserRole(user_id="support-admin-1", role_key=SUPPORT_ADMIN_ROLE))
            session.commit()
        admin = CurrentUser(
            user_id="support-admin-1",
            username="support",
            display_name="Support",
            role=ROLE_ADMIN,
            is_admin=True,
            is_authenticated=True,
            transitional=False,
            auth_enabled=True,
        )
        dependency = require_admin_capability("users:security:write")

        with self.assertRaises(HTTPException) as exc:
            dependency(admin)
        self.assertEqual(exc.exception.status_code, 403)
        self.assertEqual(exc.exception.detail["error"], "admin_capability_required")
        self.assertNotIn("support-admin", str(exc.exception.detail))
        self.assertNotIn("users:read", str(exc.exception.detail))

    def test_any_capability_dependency_accepts_any_matching_capability(self) -> None:
        from api.deps import require_any_admin_capability

        admin = _current_user(role=ROLE_ADMIN, is_admin=True, admin_capabilities=("users:read",))
        dependency = require_any_admin_capability(["secrets:read", "users:read"])

        self.assertIs(dependency(admin), admin)

    def test_unknown_capability_dependency_fails_without_inventory_leakage(self) -> None:
        from api.deps import require_admin_capability

        admin = _current_user(role=ROLE_ADMIN, is_admin=True)
        dependency = require_admin_capability("secrets:read")

        with self.assertRaises(HTTPException) as exc:
            dependency(admin)
        detail_text = str(exc.exception.detail).lower()
        self.assertEqual(exc.exception.status_code, 403)
        self.assertNotIn("users:read", detail_text)
        self.assertNotIn("super-admin", detail_text)
        self.assertNotIn("raw-session-id", detail_text)

    def test_sensitive_reason_helper_accepts_bounded_reason(self) -> None:
        from api.deps import require_sensitive_reason

        self.assertEqual("support verified request", require_sensitive_reason(" support verified request "))

    def test_sensitive_reason_helper_rejects_missing_or_overlong_reason(self) -> None:
        from api.deps import require_sensitive_reason

        for reason in ("", "   ", "x" * 501):
            with self.assertRaises(HTTPException) as exc:
                require_sensitive_reason(reason)
            self.assertEqual(exc.exception.status_code, 400)
            self.assertIn(exc.exception.detail["error"], {"reason_required", "validation_error"})

    def test_self_destructive_helper_blocks_self_action(self) -> None:
        from api.deps import assert_not_self_destructive_action

        admin = _current_user(role=ROLE_ADMIN, is_admin=True)

        with self.assertRaises(HTTPException) as exc:
            assert_not_self_destructive_action(admin, "user-1")
        self.assertEqual(exc.exception.status_code, 403)
        self.assertEqual(exc.exception.detail["error"], "self_action_blocked")

    def test_last_super_admin_helper_blocks_removing_last_super_admin(self) -> None:
        from api.deps import assert_not_last_super_admin

        self.db.create_or_update_app_user(
            user_id="admin-only",
            username="admin-only",
            display_name="Only Admin",
            role=ROLE_ADMIN,
            password_hash=None,
            is_active=True,
        )
        self.db.create_or_update_app_user(
            user_id=BOOTSTRAP_ADMIN_USER_ID,
            username="admin",
            display_name="Bootstrap Admin",
            role=ROLE_ADMIN,
            password_hash=None,
            is_active=False,
        )

        with self.assertRaises(HTTPException) as exc:
            assert_not_last_super_admin("admin-only")
        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(exc.exception.detail["error"], "last_super_admin_blocked")

    def test_last_super_admin_helper_allows_when_another_super_admin_remains(self) -> None:
        from api.deps import assert_not_last_super_admin

        self.db.create_or_update_app_user(
            user_id="admin-1",
            username="admin1",
            display_name="Admin One",
            role=ROLE_ADMIN,
            password_hash=None,
            is_active=True,
        )
        self.db.create_or_update_app_user(
            user_id="admin-2",
            username="admin2",
            display_name="Admin Two",
            role=ROLE_ADMIN,
            password_hash=None,
            is_active=True,
        )

        self.assertIsNone(assert_not_last_super_admin("admin-1"))

    def test_recent_admin_reauth_helper_is_safe_unsupported_without_metadata(self) -> None:
        from api.deps import require_recent_admin_reauth

        admin = _current_user(role=ROLE_ADMIN, is_admin=True)

        with self.assertRaises(HTTPException) as exc:
            require_recent_admin_reauth(admin)
        self.assertEqual(exc.exception.status_code, 403)
        self.assertEqual(exc.exception.detail["error"], "admin_reauth_required")

    def test_recent_admin_reauth_helper_accepts_recent_explicit_metadata(self) -> None:
        from api.deps import require_recent_admin_reauth

        admin = _current_user(role=ROLE_ADMIN, is_admin=True)
        reauthenticated_at = datetime.now() - timedelta(minutes=3)

        self.assertIs(require_recent_admin_reauth(admin, reauthenticated_at=reauthenticated_at), admin)

    def test_recent_admin_reauth_helper_accepts_session_bound_marker(self) -> None:
        from api.deps import require_recent_admin_reauth

        auth._session_secret = b"1" * 32
        admin = _current_user(role=ROLE_ADMIN, is_admin=True)
        session_id = "session-bound-marker"
        object.__setattr__(admin, "session_id", session_id)
        self.db.create_or_update_app_user(
            user_id=admin.user_id,
            username=admin.username,
            display_name=admin.display_name or admin.username,
            role=ROLE_ADMIN,
            password_hash=None,
            is_active=True,
        )
        self.db.create_app_user_session(
            session_id=session_id,
            user_id=admin.user_id,
            expires_at=datetime.now() + timedelta(hours=1),
        )
        auth.mark_admin_session_reauthenticated(user_id=admin.user_id, session_id=session_id)

        self.assertIs(require_recent_admin_reauth(admin), admin)

    def test_recent_admin_reauth_helper_rejects_expired_session_marker(self) -> None:
        from api.deps import require_recent_admin_reauth

        auth._session_secret = b"2" * 32
        admin = _current_user(role=ROLE_ADMIN, is_admin=True)
        session_id = "expired-marker-session"
        object.__setattr__(admin, "session_id", session_id)
        self.db.create_or_update_app_user(
            user_id=admin.user_id,
            username=admin.username,
            display_name=admin.display_name or admin.username,
            role=ROLE_ADMIN,
            password_hash=None,
            is_active=True,
        )
        self.db.create_app_user_session(
            session_id=session_id,
            user_id=admin.user_id,
            expires_at=datetime.now() + timedelta(hours=1),
        )
        auth.mark_admin_session_reauthenticated(
            user_id=admin.user_id,
            session_id=session_id,
            reauthenticated_at=datetime.now() - timedelta(minutes=20),
        )

        with self.assertRaises(HTTPException) as exc:
            require_recent_admin_reauth(admin, max_age_minutes=15)
        self.assertEqual(exc.exception.status_code, 403)
        self.assertEqual(exc.exception.detail["error"], "admin_reauth_required")

    def test_recent_admin_reauth_helper_rejects_revoked_session_marker(self) -> None:
        from api.deps import require_recent_admin_reauth

        auth._session_secret = b"3" * 32
        admin = _current_user(role=ROLE_ADMIN, is_admin=True)
        session_id = "revoked-marker-session"
        object.__setattr__(admin, "session_id", session_id)
        self.db.create_or_update_app_user(
            user_id=admin.user_id,
            username=admin.username,
            display_name=admin.display_name or admin.username,
            role=ROLE_ADMIN,
            password_hash=None,
            is_active=True,
        )
        self.db.create_app_user_session(
            session_id=session_id,
            user_id=admin.user_id,
            expires_at=datetime.now() + timedelta(hours=1),
        )
        auth.mark_admin_session_reauthenticated(user_id=admin.user_id, session_id=session_id)
        self.db.revoke_app_user_session(session_id)

        with self.assertRaises(HTTPException) as exc:
            require_recent_admin_reauth(admin)
        self.assertEqual(exc.exception.status_code, 403)
        self.assertEqual(exc.exception.detail["error"], "admin_reauth_required")

    def test_capability_output_contains_no_secret_like_fields(self) -> None:
        user = _current_user(role=ROLE_ADMIN, is_admin=True)

        text = " ".join(sorted(expand_admin_capabilities(user))).lower()

        for forbidden in (
            "password",
            "hash",
            "session",
            "cookie",
            "token",
            "api_key",
            "secret",
            "broker",
            ".env",
        ):
            self.assertNotIn(forbidden, text)

    def test_only_r3_pilot_and_r3b_admin_routes_use_capability_dependencies(self) -> None:
        endpoint_dir = Path(__file__).resolve().parents[1] / "api" / "v1" / "endpoints"
        usages: dict[str, int] = {}
        for path in endpoint_dir.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            count = text.count("require_admin_capability(") + text.count("require_any_admin_capability(")
            if count:
                usages[path.name] = count

        self.assertEqual(
            {
                "admin_cost.py": 3,
                "admin_logs.py": 6,
                "admin_notifications.py": 7,
                "admin_portfolio.py": 4,
                "admin_provider_circuits.py": 5,
                "admin_security.py": 1,
                "system_config.py": 9,
            },
            usages,
        )


if __name__ == "__main__":
    unittest.main()
