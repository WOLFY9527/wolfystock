#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Seed explicit local/UAT consumer login accounts.

This helper is a manual development/UAT fixture path. It is not imported by the
API server and refuses to run when the runtime is marked as production.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.auth import hash_password_for_storage, is_production_mode, verify_password_hash_string
from src.multi_user import ROLE_USER
from src.storage import DatabaseManager

UAT_CONSUMER_TEST_ACCOUNT_USERNAMES: tuple[str, ...] = (
    "uat_consumer_test",
    "webuat_consumer",
)
_UAT_CONSUMER_TEST_LOGIN_VALUE = "852258"

EXIT_OK = 0
EXIT_FAILED = 1


def uat_consumer_test_login_value() -> str:
    """Return the fixed local/UAT fixture login value."""
    return _UAT_CONSUMER_TEST_LOGIN_VALUE


def _display_name(username: str) -> str:
    if username == "uat_consumer_test":
        return "UAT Consumer Test"
    if username == "webuat_consumer":
        return "Web UAT Consumer"
    return username.replace("_", " ").title()


def _account_id(username: str) -> str:
    return f"uat-consumer-{username.replace('_', '-')}"


def _seed_account(*, db: DatabaseManager, username: str, login_value: str) -> dict[str, Any]:
    existing = db.get_app_user_by_username(username)
    existing_hash = getattr(existing, "password_hash", None) if existing is not None else None
    password_hash = (
        str(existing_hash)
        if existing_hash and verify_password_hash_string(login_value, existing_hash)
        else hash_password_for_storage(login_value)
    )
    row = db.create_or_update_app_user(
        user_id=str(getattr(existing, "id", "") or _account_id(username)),
        username=username,
        display_name=_display_name(username),
        role=ROLE_USER,
        password_hash=password_hash,
        is_active=True,
    )
    return {
        "username": str(row.username),
        "userId": str(row.id),
        "role": str(row.role),
        "isActive": bool(row.is_active),
        "isAdmin": str(row.role) != ROLE_USER,
        "credentialState": "unchanged" if existing_hash and existing_hash == password_hash else "updated",
    }


def seed_uat_consumer_test_accounts() -> dict[str, Any]:
    """Create or repair the local/UAT consumer accounts without admin grants."""
    if is_production_mode():
        return {
            "status": "blocked",
            "reasonCode": "production_environment_blocked",
            "accounts": [],
        }

    db = DatabaseManager.get_instance()
    accounts = [
        _seed_account(
            db=db,
            username=username,
            login_value=uat_consumer_test_login_value(),
        )
        for username in UAT_CONSUMER_TEST_ACCOUNT_USERNAMES
    ]
    return {
        "status": "seeded",
        "reasonCode": None,
        "accounts": accounts,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed local/UAT consumer test accounts as non-admin users.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = seed_uat_consumer_test_accounts()
    if args.json:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"UAT consumer test account seed: {result['status']}")
        if result.get("reasonCode"):
            print(f"Reason: {result['reasonCode']}")
        for account in result.get("accounts", []):
            print(f"- {account['username']}: role={account['role']} active={account['isActive']}")
    return EXIT_OK if result["status"] == "seeded" else EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
