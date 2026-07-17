# -*- coding: utf-8 -*-
"""Non-destructive real PostgreSQL runtime audit for Phase A-G coexistence stores."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from src.config import Config
from src.postgres_schema_bootstrap import list_bootstrap_records
from src.storage import DatabaseManager
from tests.destructive_postgres import current_target

pytestmark = pytest.mark.destructive_postgres
_EXPECTED_SCHEMA_KEYS = ("phase_a", "phase_b", "phase_c", "phase_d", "phase_e", "phase_f", "phase_g")


class PostgresRuntimeRealPgAuditTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.sqlite_db_path = self.data_dir / "legacy.sqlite"
        self.real_pg_dsn = current_target().scoped_dsn
        self.pg_engine = create_engine(self.real_pg_dsn, echo=False, pool_pre_ping=True)
        self._configure_environment(auto_apply_schema=True)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        os.environ.pop("POSTGRES_PHASE_A_URL", None)
        os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)
        self.pg_engine.dispose()
        self.temp_dir.cleanup()

    def _configure_environment(self, *, auto_apply_schema: bool) -> None:
        lines = [
            "STOCK_LIST=600519",
            "GEMINI_API_KEY=test",
            f"DATABASE_PATH={self.sqlite_db_path}",
            f"POSTGRES_PHASE_A_URL={self.real_pg_dsn}",
            f"POSTGRES_PHASE_A_APPLY_SCHEMA={'true' if auto_apply_schema else 'false'}",
        ]
        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.sqlite_db_path)
        os.environ["POSTGRES_PHASE_A_URL"] = self.real_pg_dsn
        os.environ["POSTGRES_PHASE_A_APPLY_SCHEMA"] = "true" if auto_apply_schema else "false"
        Config.reset_instance()
        DatabaseManager.reset_instance()

    def _db(self) -> DatabaseManager:
        return DatabaseManager.get_instance()

    def _phase_report_message(self, phase_key: str, report: dict) -> str:
        return f"{phase_key}: {json.dumps(report, ensure_ascii=False, sort_keys=True)}"

    def test_real_postgres_runtime_audit_reports_all_phase_slices_as_applied(self) -> None:
        db = self._db()
        topology = db.describe_database_topology(include_connection_probe=True)
        bootstrap_records = list_bootstrap_records(self.pg_engine)

        self.assertTrue(topology["postgres_bridge"]["configured"])
        self.assertTrue(topology["postgres_bridge"]["enabled"])
        self.assertEqual(topology["primary_runtime"], "sqlite")
        self.assertEqual(topology["serving_semantics"]["phase_f"], "legacy_serving_pg_comparison_only")
        self.assertEqual(topology["serving_semantics"]["phase_g"], "env_live_source_pg_snapshot_shadow")
        self.assertTrue(set(_EXPECTED_SCHEMA_KEYS).issubset(set(topology["bootstrap_registry"]["recorded_schema_keys"])))
        self.assertTrue(set(_EXPECTED_SCHEMA_KEYS).issubset({row["schema_key"] for row in bootstrap_records}))

        for phase_key in _EXPECTED_SCHEMA_KEYS:
            report = topology["stores"][phase_key]
            self.assertTrue(report["enabled"], self._phase_report_message(phase_key, report))
            self.assertTrue(report["connection"]["ok"], self._phase_report_message(phase_key, report))
            self.assertEqual(report["schema"]["last_apply_status"], "applied", self._phase_report_message(phase_key, report))
            self.assertTrue(report["schema"]["bootstrap_recorded"], self._phase_report_message(phase_key, report))
            self.assertEqual(report["schema"]["missing_tables"], [], self._phase_report_message(phase_key, report))
            self.assertEqual(report["schema"]["missing_indexes"], [], self._phase_report_message(phase_key, report))
            self.assertEqual(report["schema"]["bootstrap"]["schema_key"], phase_key, self._phase_report_message(phase_key, report))

    def test_real_postgres_runtime_audit_reports_skip_mode_without_losing_schema_visibility(self) -> None:
        self._db()
        self._configure_environment(auto_apply_schema=False)

        db = self._db()
        topology = db.describe_database_topology(include_connection_probe=True)
        phase_g_status = db.describe_phase_g_execution_log_status(include_connection_probe=True)

        self.assertTrue(phase_g_status["bridge_enabled"])
        self.assertTrue(phase_g_status["shadow_enabled"])
        self.assertTrue(phase_g_status["serving_flags"]["sqlite_primary"])
        self.assertFalse(phase_g_status["serving_flags"]["pg_execution_logs_are_serving_truth"])

        for phase_key in _EXPECTED_SCHEMA_KEYS:
            report = topology["stores"][phase_key]
            self.assertTrue(report["enabled"], self._phase_report_message(phase_key, report))
            self.assertTrue(report["connection"]["ok"], self._phase_report_message(phase_key, report))
            self.assertEqual(report["schema"]["last_apply_status"], "skipped", self._phase_report_message(phase_key, report))
            self.assertEqual(report["schema"]["skip_reason"], "auto_apply_schema_disabled", self._phase_report_message(phase_key, report))
            self.assertTrue(report["schema"]["bootstrap_recorded"], self._phase_report_message(phase_key, report))
            self.assertEqual(report["schema"]["missing_tables"], [], self._phase_report_message(phase_key, report))
            self.assertEqual(report["schema"]["missing_indexes"], [], self._phase_report_message(phase_key, report))


if __name__ == "__main__":
    unittest.main()
