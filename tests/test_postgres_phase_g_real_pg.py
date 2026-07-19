# -*- coding: utf-8 -*-
"""Real PostgreSQL validation for the Phase G control-plane baseline."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from src.config import Config
from src.core.config_manager import ConfigManager
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID
from src.postgres_control_plane_store import (
    PhaseGAdminLog,
    PhaseGProviderConfig,
    PhaseGExecutionEvent,
    PhaseGExecutionSession,
    PhaseGSystemAction,
    PhaseGSystemConfig,
)
from src.services.execution_log_service import ExecutionLogService
from src.services.system_config_service import SystemConfigService
from src.storage import DatabaseManager
from tests.destructive_postgres import current_target

pytestmark = pytest.mark.destructive_postgres


class PostgresPhaseGRealPgTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.sqlite_db_path = self.data_dir / "legacy.sqlite"
        self.real_pg_dsn = current_target().scoped_dsn
        self.pg_engine = create_engine(self.real_pg_dsn, echo=False, pool_pre_ping=True)
        self._drop_phase_g_tables()
        self._configure_environment()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        os.environ.pop("POSTGRES_PHASE_A_URL", None)
        os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)
        self._drop_phase_g_tables()
        self.pg_engine.dispose()
        self.temp_dir.cleanup()

    def _configure_environment(self) -> None:
        lines = [
            "STOCK_LIST=600519,000001",
            "GEMINI_API_KEY=real-secret",
            "GEMINI_MODEL=gemini-2.5-pro",
            "SCHEDULE_TIME=18:00",
            f"DATABASE_PATH={self.sqlite_db_path}",
            f"POSTGRES_PHASE_A_URL={self.real_pg_dsn}",
            "POSTGRES_PHASE_A_APPLY_SCHEMA=true",
        ]
        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.sqlite_db_path)
        os.environ["POSTGRES_PHASE_A_URL"] = self.real_pg_dsn
        os.environ["POSTGRES_PHASE_A_APPLY_SCHEMA"] = "true"
        Config.reset_instance()
        DatabaseManager.reset_instance()

    def _db(self) -> DatabaseManager:
        return DatabaseManager.get_instance()

    def _service(self) -> SystemConfigService:
        return SystemConfigService(manager=ConfigManager(env_path=self.env_path))

    def _drop_phase_g_tables(self) -> None:
        with self.pg_engine.begin() as conn:
            conn.execute(text("drop table if exists execution_events cascade"))
            conn.execute(text("drop table if exists execution_sessions cascade"))
            conn.execute(text("drop table if exists system_actions cascade"))
            conn.execute(text("drop table if exists admin_logs cascade"))
            conn.execute(text("drop table if exists system_configs cascade"))
            conn.execute(text("drop table if exists provider_configs cascade"))

    def _pg_scalar(self, sql: str, **params):
        with self.pg_engine.begin() as conn:
            return conn.execute(text(sql), params).scalar()

    def test_real_postgres_phase_g_control_plane_round_trip(self) -> None:
        db = self._db()
        db.ensure_bootstrap_admin_user()
        service = self._service()

        service.get_config(include_schema=False)
        service.factory_reset_system(
            confirmation_phrase="FACTORY RESET",
            actor_user_id=BOOTSTRAP_ADMIN_USER_ID,
            actor_display_name="Bootstrap Admin",
        )

        self.assertEqual(self._pg_scalar("select count(*) from provider_configs"), 1)
        self.assertGreaterEqual(self._pg_scalar("select count(*) from system_configs"), 2)
        self.assertEqual(self._pg_scalar("select count(*) from admin_logs"), 1)
        self.assertEqual(self._pg_scalar("select count(*) from system_actions"), 1)

        with db._phase_g_store.session_scope() as session:
            self.assertEqual(session.query(PhaseGProviderConfig).count(), 1)
            self.assertGreaterEqual(session.query(PhaseGSystemConfig).count(), 2)
            self.assertEqual(session.query(PhaseGAdminLog).count(), 1)
            self.assertEqual(session.query(PhaseGSystemAction).count(), 1)

    def test_real_postgres_phase_g_factory_reset_nulls_deleted_user_refs(self) -> None:
        db = self._db()
        db.ensure_bootstrap_admin_user()
        db.create_or_update_app_user(user_id="admin-2", username="admin-2", role="admin")
        service = self._service()

        service.get_config(include_schema=False)
        service.update(
            config_version=service._manager.get_config_version(),
            items=[{"key": "SCHEDULE_TIME", "value": "19:45"}],
            reload_now=False,
            actor_user_id="admin-2",
        )

        result = db.factory_reset_non_bootstrap_state()

        self.assertIn("app_users", result["cleared"])
        with db._phase_g_store.session_scope() as session:
            schedule_time = (
                session.query(PhaseGSystemConfig)
                .filter(PhaseGSystemConfig.config_key == "SCHEDULE_TIME")
                .one()
            )
        self.assertIsNone(schedule_time.updated_by_user_id)

    def test_real_postgres_phase_g_execution_log_shadow_observability_round_trip(self) -> None:
        db = self._db()
        db.ensure_bootstrap_admin_user()
        db.create_or_update_app_user(user_id="real-pg-user", username="real-pg-user", role="user")
        service = ExecutionLogService()

        analysis_session_id = service.start_session(
            task_id="task-real-pg",
            stock_code="600519",
            stock_name="贵州茅台",
            configured_execution={
                "ai": {
                    "configured_primary_gateway": "openai",
                    "configured_primary_model": "gpt-4o-mini",
                    "model": "gpt-4o-mini",
                },
                "data": {
                    "market": {
                        "source": "akshare",
                        "status": "succeeded",
                    }
                },
                "notification": {"channels": ["feishu"]},
            },
            owner_id="real-pg-user",
            actor={
                "user_id": "real-pg-user",
                "username": "real-pg-user",
                "display_name": "Real PG User",
                "role": "user",
            },
            subsystem="analysis",
        )
        admin_session_id = service.record_admin_action(
            action="factory_reset_system",
            message="Factory reset completed",
            actor={
                "user_id": BOOTSTRAP_ADMIN_USER_ID,
                "username": "admin",
                "display_name": "Bootstrap Admin",
                "role": "admin",
            },
            subsystem="system_control",
            destructive=True,
            detail={"counts": {"users": 1}},
        )

        status = db.describe_phase_g_execution_log_status(include_connection_probe=True)
        analysis_detail = db.get_phase_g_execution_session_detail(analysis_session_id)
        admin_detail = db.get_phase_g_execution_session_detail(admin_session_id)

        self.assertTrue(status["bridge_enabled"])
        self.assertTrue(status["shadow_enabled"])
        self.assertTrue(status["connection"]["ok"])
        self.assertEqual(status["schema"]["last_apply_status"], "applied")
        self.assertEqual(self._pg_scalar("select count(*) from execution_sessions"), 2)
        self.assertGreaterEqual(self._pg_scalar("select count(*) from execution_events"), 3)
        self.assertIsNotNone(analysis_detail)
        self.assertEqual(analysis_detail["ownership"]["domain_store"], "phase_b")
        self.assertIsNotNone(admin_detail)
        self.assertEqual(admin_detail["ownership"]["domain_store"], "phase_g")
        self.assertEqual(admin_detail["related_phase_g_admin_log_count"], 1)
        self.assertEqual(admin_detail["related_phase_g_system_action_count"], 1)

        with db._phase_g_store.session_scope() as session:
            self.assertEqual(session.query(PhaseGExecutionSession).count(), 2)
            self.assertGreaterEqual(session.query(PhaseGExecutionEvent).count(), 3)


if __name__ == "__main__":
    unittest.main()
