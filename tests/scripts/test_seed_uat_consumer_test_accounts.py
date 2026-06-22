from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import src.auth as auth
import scripts.seed_uat_consumer_test_accounts as seed
from src.config import Config
from src.storage import DatabaseManager


def _reset_runtime() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._password_hash_value = None
    auth._rate_limit = {}
    auth._admin_reauth_markers = {}
    Config.reset_instance()
    DatabaseManager.reset_instance()


class UatConsumerSeedTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_runtime()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_dir = self.root / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "uat-seed.db"
        self.env = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": str(self.db_path),
                "ADMIN_AUTH_ENABLED": "true",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        _reset_runtime()
        self.temp_dir.cleanup()

    def test_seed_creates_consumer_only_accounts_without_sensitive_output(self) -> None:
        result = seed.seed_uat_consumer_test_accounts()

        self.assertEqual(result["status"], "seeded")
        self.assertIsNone(result["reasonCode"])
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn(seed.uat_consumer_test_login_value(), serialized)
        self.assertNotIn("passwordHash", serialized)
        self.assertNotIn("wolfystock", serialized.lower())

        db = DatabaseManager.get_instance()
        self.assertEqual(len(result["accounts"]), 2)
        for account in result["accounts"]:
            self.assertIn(account["username"], seed.UAT_CONSUMER_TEST_ACCOUNT_USERNAMES)
            self.assertEqual(account["role"], "user")
            self.assertTrue(account["isActive"])
            self.assertFalse(account["isAdmin"])

            row = db.get_app_user_by_username(account["username"])
            self.assertIsNotNone(row)
            self.assertEqual(row.role, "user")
            self.assertTrue(row.is_active)
            self.assertTrue(
                auth.verify_password_hash_string(
                    seed.uat_consumer_test_login_value(),
                    row.password_hash,
                )
            )

    def test_seed_refuses_production_environment(self) -> None:
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=False):
            result = seed.seed_uat_consumer_test_accounts()

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reasonCode"], "production_environment_blocked")
        self.assertEqual(result["accounts"], [])
        db = DatabaseManager.get_instance()
        for username in seed.UAT_CONSUMER_TEST_ACCOUNT_USERNAMES:
            self.assertIsNone(db.get_app_user_by_username(username))


if __name__ == "__main__":
    unittest.main()
