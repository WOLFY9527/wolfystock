# -*- coding: utf-8 -*-
"""RBAC compatibility-layer tests for admin capability metadata."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import inspect, select

from api.deps import CurrentUser, require_admin_user
from src.admin_rbac import (
    ADMIN_RBAC_CAPABILITIES,
    ADMIN_RBAC_ROLES,
    SUPER_ADMIN_ROLE,
    expand_admin_capabilities,
    has_admin_capability,
)
from src.multi_user import ROLE_ADMIN, ROLE_USER
from src.storage import AdminRole, AdminRoleCapability, DatabaseManager


def _current_user(*, role: str, is_admin: bool) -> CurrentUser:
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
    )


class AdminRbacCompatibilityTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "rbac.db"
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")

    def tearDown(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
