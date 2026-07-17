#!/usr/bin/env python3
"""Seed disposable release-browser users without printing synthetic credentials."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.admin_rbac import SUPER_ADMIN_ROLE
from src.auth import hash_password_for_storage, is_production_mode
from src.config import setup_env
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID, BOOTSTRAP_ADMIN_USERNAME, ROLE_ADMIN, ROLE_USER
from src.repositories.auth_repo import AuthRepository
from src.storage import AdminUserRole


def _required_env(name: str) -> str:
    value = str(os.environ.get(name) or "").strip()
    if not value:
        raise ValueError(f"{name}_required")
    return value


def _ensure_release_admin_role(repo: AuthRepository) -> None:
    if SUPER_ADMIN_ROLE in repo.list_admin_user_roles(BOOTSTRAP_ADMIN_USER_ID):
        return
    with repo.db.session_scope() as session:
        session.add(
            AdminUserRole(
                user_id=BOOTSTRAP_ADMIN_USER_ID,
                role_key=SUPER_ADMIN_ROLE,
                assigned_by=BOOTSTRAP_ADMIN_USER_ID,
            )
        )


def main() -> int:
    setup_env()
    if is_production_mode():
        print(json.dumps({"status": "blocked", "reasonCode": "production_environment_blocked"}))
        return 1
    admin_username = _required_env("WOLFYSTOCK_RELEASE_ADMIN_USERNAME")
    admin_password = _required_env("WOLFYSTOCK_RELEASE_ADMIN_PASSWORD")
    member_username = _required_env("WOLFYSTOCK_RELEASE_MEMBER_USERNAME")
    member_password = _required_env("WOLFYSTOCK_RELEASE_MEMBER_PASSWORD")
    if admin_username != BOOTSTRAP_ADMIN_USERNAME:
        raise ValueError("release_admin_must_use_bootstrap_identity")
    repo = AuthRepository()
    admin_hash = hash_password_for_storage(admin_password)
    database_path = Path(_required_env("DATABASE_PATH")).resolve()
    credential_path = database_path.parent / ".admin_password_hash"
    credential_path.parent.mkdir(parents=True, exist_ok=True)
    credential_path.write_text(admin_hash, encoding="utf-8")
    credential_path.chmod(0o600)
    accounts = (
        (BOOTSTRAP_ADMIN_USER_ID, admin_username, "Release Browser Admin", ROLE_ADMIN, admin_password),
        ("release-browser-member", member_username, "Release Browser Member", ROLE_USER, member_password),
    )
    for user_id, username, display_name, role, password in accounts:
        repo.create_or_update_app_user(
            user_id=user_id,
            username=username,
            display_name=display_name,
            role=role,
            password_hash=admin_hash if role == ROLE_ADMIN else hash_password_for_storage(password),
            is_active=True,
        )
    _ensure_release_admin_role(repo)
    print(
        json.dumps(
            {
                "schemaVersion": "wolfystock_release_runtime_fixture_v1",
                "status": "seeded",
                "accountCount": len(accounts),
                "roles": [ROLE_ADMIN, ROLE_USER],
                "secretsIncluded": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "reasonCode": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
