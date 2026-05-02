# -*- coding: utf-8 -*-
"""Real PostgreSQL validation for Admin Logs storage quota behavior."""

from __future__ import annotations

import os
import secrets
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
import sys
from unittest.mock import MagicMock

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from api.deps import CurrentUser
from api.v1.endpoints import admin_logs
from api.v1.schemas.admin_logs import AdminLogCleanupRequest
from src.config import Config
from src.storage import DatabaseManager

REAL_PG_DSN = str(
    os.getenv("POSTGRES_PHASE_A_REAL_DSN") or ""
).strip()


def _real_pg_dsn_available(dsn: str) -> bool:
    if not dsn:
        return False
    try:
        parsed = make_url(dsn)
        if str(parsed.host or "") not in {"127.0.0.1", "localhost"}:
            return False
        if int(parsed.port or 0) != 55432:
            return False
        probe_engine = create_engine(dsn, echo=False, pool_pre_ping=True)
        with probe_engine.connect() as conn:
            conn.execute(text("select 1"))
        probe_engine.dispose()
        return True
    except Exception:
        return False


def _admin_user() -> CurrentUser:
    return CurrentUser(
        user_id="bootstrap-admin",
        username="admin",
        display_name="Admin",
        role="admin",
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )


@unittest.skipUnless(
    _real_pg_dsn_available(REAL_PG_DSN),
    "A reachable POSTGRES_PHASE_A_REAL_DSN is required for real PostgreSQL validation",
)
class AdminLogsRealPgQuotaTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.sqlite_db_path = self.data_dir / "legacy.sqlite"

        self.base_url = make_url(REAL_PG_DSN)
        self.pg_test_dsn = str(self.base_url)
        self.pg_engine = create_engine(
            self.pg_test_dsn,
            echo=False,
            pool_pre_ping=True,
        )
        self._drop_phase_g_tables()

        self._configure_environment(
            admin_log_storage_soft_limit_mb=1,
            admin_log_storage_hard_limit_mb=10,
            admin_log_auto_cleanup_enabled=False,
        )

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        os.environ.pop("POSTGRES_PHASE_A_URL", None)
        os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)
        os.environ.pop("ADMIN_LOG_RETENTION_DAYS", None)
        os.environ.pop("ADMIN_LOG_MIN_RETENTION_DAYS", None)
        os.environ.pop("ADMIN_LOG_STORAGE_SOFT_LIMIT_MB", None)
        os.environ.pop("ADMIN_LOG_STORAGE_HARD_LIMIT_MB", None)
        os.environ.pop("ADMIN_LOG_AUTO_CLEANUP_ENABLED", None)
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("STOCK_LIST", None)
        try:
            self._drop_phase_g_tables()
        finally:
            self.pg_engine.dispose()
            self.temp_dir.cleanup()

    def _drop_phase_g_tables(self) -> None:
        with self.pg_engine.begin() as conn:
            conn.execute(text("drop table if exists execution_events cascade"))
            conn.execute(text("drop table if exists execution_sessions cascade"))
            conn.execute(text("drop table if exists admin_logs cascade"))
            conn.execute(text("drop table if exists system_actions cascade"))
            conn.execute(text("drop table if exists system_configs cascade"))
            conn.execute(text("drop table if exists provider_configs cascade"))

    def _configure_environment(
        self,
        *,
        admin_log_storage_soft_limit_mb: int,
        admin_log_storage_hard_limit_mb: int,
        admin_log_auto_cleanup_enabled: bool,
    ) -> None:
        lines = [
            "STOCK_LIST=600519",
            "GEMINI_API_KEY=test",
            f"DATABASE_PATH={self.sqlite_db_path}",
            f"POSTGRES_PHASE_A_URL={self.pg_test_dsn}",
            "POSTGRES_PHASE_A_APPLY_SCHEMA=true",
            "ADMIN_LOG_RETENTION_DAYS=90",
            "ADMIN_LOG_MIN_RETENTION_DAYS=7",
            f"ADMIN_LOG_STORAGE_SOFT_LIMIT_MB={admin_log_storage_soft_limit_mb}",
            f"ADMIN_LOG_STORAGE_HARD_LIMIT_MB={admin_log_storage_hard_limit_mb}",
            f"ADMIN_LOG_AUTO_CLEANUP_ENABLED={'true' if admin_log_auto_cleanup_enabled else 'false'}",
        ]
        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.sqlite_db_path)
        os.environ["POSTGRES_PHASE_A_URL"] = self.pg_test_dsn
        os.environ["POSTGRES_PHASE_A_APPLY_SCHEMA"] = "true"
        os.environ["ADMIN_LOG_RETENTION_DAYS"] = "90"
        os.environ["ADMIN_LOG_MIN_RETENTION_DAYS"] = "7"
        os.environ["ADMIN_LOG_STORAGE_SOFT_LIMIT_MB"] = str(admin_log_storage_soft_limit_mb)
        os.environ["ADMIN_LOG_STORAGE_HARD_LIMIT_MB"] = str(admin_log_storage_hard_limit_mb)
        os.environ["ADMIN_LOG_AUTO_CLEANUP_ENABLED"] = "true" if admin_log_auto_cleanup_enabled else "false"
        os.environ["GEMINI_API_KEY"] = "test"
        os.environ["STOCK_LIST"] = "600519"
        Config.reset_instance()
        DatabaseManager.reset_instance()

    def _db(self) -> DatabaseManager:
        return DatabaseManager.get_instance()

    def _seed_execution_logs(self, *, total: int, old_count: int) -> None:
        db = self._db()
        now = datetime.now()
        for index in range(total):
            session_id = f"quota-{index}"
            timestamp = now - timedelta(days=120 if index < old_count else 1)
            blob = secrets.token_hex(2048)
            payload = {
                "blob": blob,
                "index": index,
                "session_id": session_id,
            }
            db.create_execution_log_session(
                session_id=session_id,
                task_id=f"task-{index}",
                code="600519",
                name="quota-seed",
                overall_status="completed",
                truth_level="actual",
                summary=payload,
                started_at=timestamp,
            )
            db.append_execution_log_event(
                session_id=session_id,
                phase="analysis",
                step="seed",
                target="600519",
                status="completed",
                truth_level="actual",
                message=blob,
                detail=payload,
                event_at=timestamp,
            )
            db.finalize_execution_log_session(
                session_id=session_id,
                overall_status="completed",
                truth_level="actual",
                summary=payload,
                ended_at=timestamp,
            )

    def test_storage_quota_warns_criticalizes_and_cleans_up_against_real_postgresql(self) -> None:
        self._seed_execution_logs(total=250, old_count=125)

        self._configure_environment(
            admin_log_storage_soft_limit_mb=1,
            admin_log_storage_hard_limit_mb=10,
            admin_log_auto_cleanup_enabled=False,
        )
        warning_payload = admin_logs.get_log_storage_summary(_=_admin_user())
        self.assertTrue(warning_payload.storage_size_available)
        self.assertIsNotNone(warning_payload.storage_size_bytes)
        self.assertGreater(warning_payload.storage_size_bytes or 0, 0)
        self.assertGreater(warning_payload.used_percentage_of_soft_limit or 0, 0)
        self.assertGreater(warning_payload.used_percentage_of_hard_limit or 0, 0)
        self.assertEqual(warning_payload.status, "warning")
        self.assertTrue(warning_payload.capacity_cleanup_recommended)

        self._configure_environment(
            admin_log_storage_soft_limit_mb=1,
            admin_log_storage_hard_limit_mb=2,
            admin_log_auto_cleanup_enabled=False,
        )
        critical_payload = admin_logs.get_log_storage_summary(_=_admin_user())
        self.assertTrue(critical_payload.storage_size_available)
        self.assertIsNotNone(critical_payload.storage_size_bytes)
        self.assertGreater(critical_payload.storage_size_bytes or 0, 0)
        self.assertEqual(critical_payload.status, "critical")
        self.assertIn("storage_hard_limit_exceeded", critical_payload.status_reasons)

        dry_run_payload = admin_logs.cleanup_admin_logs(
            AdminLogCleanupRequest(mode="capacity", dry_run=True),
            _=_admin_user(),
        )
        dry_run_remaining = admin_logs.get_log_storage_summary(_=_admin_user())
        self.assertTrue(dry_run_payload.dry_run)
        self.assertEqual(dry_run_payload.mode, "capacity")
        self.assertEqual(dry_run_payload.matched_log_count, 125)
        self.assertEqual(dry_run_payload.matched_event_count, 125)
        self.assertEqual(dry_run_payload.deleted_log_count, 0)
        self.assertEqual(dry_run_remaining.total_log_count, 250)

        actual_payload = admin_logs.cleanup_admin_logs(
            AdminLogCleanupRequest(mode="capacity", dry_run=False),
            _=_admin_user(),
        )
        remaining_after_capacity = admin_logs.get_log_storage_summary(_=_admin_user())
        self.assertFalse(actual_payload.dry_run)
        self.assertEqual(actual_payload.mode, "capacity")
        self.assertEqual(actual_payload.deleted_log_count, 125)
        self.assertEqual(actual_payload.deleted_event_count, 125)
        self.assertEqual(remaining_after_capacity.total_log_count, 125)
        self.assertEqual(remaining_after_capacity.logs_older_than_retention_count, 0)
        self.assertFalse(actual_payload.additional_cleanup_needed)

        self._seed_execution_logs(total=2, old_count=1)
        retention_dry_run = admin_logs.cleanup_admin_logs(
            AdminLogCleanupRequest(use_retention=True, dry_run=True),
            _=_admin_user(),
        )
        self.assertTrue(retention_dry_run.dry_run)
        self.assertEqual(retention_dry_run.mode, "retention")
        self.assertEqual(retention_dry_run.matched_log_count, 1)
        self.assertEqual(retention_dry_run.deleted_log_count, 0)

        retention_actual = admin_logs.cleanup_admin_logs(
            AdminLogCleanupRequest(use_retention=True, dry_run=False),
            _=_admin_user(),
        )
        remaining_after_retention = admin_logs.get_log_storage_summary(_=_admin_user())
        self.assertFalse(retention_actual.dry_run)
        self.assertEqual(retention_actual.mode, "retention")
        self.assertEqual(retention_actual.deleted_log_count, 1)
        self.assertEqual(remaining_after_retention.total_log_count, 126)
        self.assertTrue(remaining_after_retention.storage_size_available)


if __name__ == "__main__":
    unittest.main()
