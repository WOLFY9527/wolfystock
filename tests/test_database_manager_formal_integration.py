# -*- coding: utf-8 -*-
"""Focused delegation coverage for formal database manager integration seams."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from src.config import Config
from src.storage_postgres_bridge import BridgeInitResult
from src.storage import DatabaseManager


class DatabaseManagerFormalIntegrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.sqlite_db_path = self.data_dir / "legacy.sqlite"
        self.phase_db_path = self.data_dir / "phase.sqlite"

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        os.environ.pop("POSTGRES_PHASE_A_URL", None)
        os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)
        self.temp_dir.cleanup()

    def _configure_environment(
        self,
        *,
        postgres_url: str | None = None,
        auto_apply_schema: bool = True,
    ) -> None:
        lines = [
            "STOCK_LIST=600519,000001",
            "GEMINI_API_KEY=test-key",
            f"DATABASE_PATH={self.sqlite_db_path}",
        ]
        if postgres_url is not None:
            lines.append(f"POSTGRES_PHASE_A_URL={postgres_url}")
            lines.append(
                f"POSTGRES_PHASE_A_APPLY_SCHEMA={'true' if auto_apply_schema else 'false'}"
            )

        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.sqlite_db_path)
        if postgres_url is None:
            os.environ.pop("POSTGRES_PHASE_A_URL", None)
            os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)
        else:
            os.environ["POSTGRES_PHASE_A_URL"] = postgres_url
            os.environ["POSTGRES_PHASE_A_APPLY_SCHEMA"] = (
                "true" if auto_apply_schema else "false"
            )
        Config.reset_instance()
        DatabaseManager.reset_instance()

    @staticmethod
    def _topology(enabled: bool = False) -> dict:
        phase_state = {
            "enabled": enabled,
            "mode": "env_live_source_with_pg_snapshot",
            "schema": {
                "last_apply_status": "not_initialized",
                "bootstrap_recorded": False,
            },
        }
        return {
            "primary_runtime": "sqlite",
            "postgres_bridge": {"enabled": enabled},
            "stores": {
                "phase_a": {"enabled": enabled, "mode": "bridge_shadow", "schema": phase_state["schema"]},
                "phase_b": {"enabled": enabled, "mode": "bridge_shadow", "schema": phase_state["schema"]},
                "phase_c": {"enabled": enabled, "mode": "bridge_shadow", "schema": phase_state["schema"]},
                "phase_d": {"enabled": enabled, "mode": "bridge_shadow", "schema": phase_state["schema"]},
                "phase_e": {"enabled": enabled, "mode": "bridge_shadow", "schema": phase_state["schema"]},
                "phase_f": {"enabled": enabled, "mode": "comparison_only_shadow", "schema": phase_state["schema"]},
                "phase_g": {"enabled": enabled, "mode": "env_live_source_with_pg_snapshot", "schema": phase_state["schema"]},
            },
        }

    def test_database_manager_init_delegates_pg_bridge_initialization(self) -> None:
        self._configure_environment(
            postgres_url=f"sqlite:///{self.phase_db_path}",
            auto_apply_schema=True,
        )

        with patch(
            "src.storage.storage_postgres_bridge.initialize_postgres_phase_stores",
            return_value=BridgeInitResult(initialized_phases=("phase_a", "phase_g"), failed_phase=None),
        ) as init_bridge, patch(
            "src.storage.storage_topology_report.build_database_topology_report",
            return_value=self._topology(enabled=False),
        ):
            db = DatabaseManager.get_instance()

        init_bridge.assert_called_once_with(
            db,
            bridge_url=f"sqlite:///{self.phase_db_path}",
            auto_apply_schema=True,
        )

    def test_database_manager_initialization_bootstraps_phase_flags_before_migrations(self) -> None:
        self._configure_environment(postgres_url=None)

        observed: dict[str, object] = {}

        def _boom(manager: DatabaseManager) -> None:
            observed["phase_a_enabled"] = manager._phase_a_enabled
            observed["phase_a_store"] = manager._phase_a_store
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            with patch.object(
                DatabaseManager,
                "_run_multi_user_migrations",
                autospec=True,
                side_effect=_boom,
            ):
                DatabaseManager(db_url="sqlite:///:memory:")

        self.assertIsNone(DatabaseManager._instance)
        self.assertEqual(observed["phase_a_enabled"], False)
        self.assertIsNone(observed["phase_a_store"])

        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")
        self.assertTrue(db._initialized)
        self.assertFalse(db._phase_a_enabled)
        self.assertIsNone(db._phase_a_store)

    def test_database_manager_dispose_delegates_pg_bridge_cleanup(self) -> None:
        self._configure_environment(postgres_url=None)
        db = DatabaseManager.get_instance()

        with patch("src.storage.storage_postgres_bridge.dispose_postgres_phase_stores") as dispose_bridge:
            db._dispose_postgres_phase_stores()

        dispose_bridge.assert_called_once_with(db)

    def test_database_manager_topology_and_phase_g_status_delegate_to_integrated_modules(self) -> None:
        self._configure_environment(postgres_url=None)
        db = DatabaseManager.get_instance()
        topology = self._topology(enabled=False)
        phase_g_status = {
            "bridge_enabled": False,
            "shadow_enabled": False,
            "mode": "env_live_source_with_pg_snapshot",
            "shadow_store": "phase_g",
            "shadow_entities": ["execution_sessions", "execution_events"],
            "primary_runtime": {
                "store": "sqlite",
                "session_entity": "execution_log_sessions",
                "event_entity": "execution_log_events",
            },
            "serving_flags": {
                "sqlite_primary": True,
                "pg_execution_logs_shadow": False,
                "pg_execution_logs_are_serving_truth": False,
            },
            "serving_semantics": "env_live_source_pg_snapshot_shadow",
            "schema": {"last_apply_status": "bridge_not_configured", "bootstrap_recorded": False},
            "connection": {"requested": False, "ok": None, "error": None},
        }

        with patch(
            "src.storage.storage_topology_report.build_database_topology_report",
            return_value=topology,
        ) as build_topology:
            observed_topology = db.describe_database_topology(include_connection_probe=True)

        self.assertEqual(observed_topology, topology)
        build_topology.assert_called_once_with(
            db,
            config=Config.get_instance(),
            include_connection_probe=True,
        )

        with patch.object(db, "describe_database_topology", return_value=topology) as describe_topology, patch(
            "src.storage.storage_phase_g_observability.build_phase_g_execution_log_status",
            return_value=phase_g_status,
        ) as build_phase_g:
            observed_phase_g_status = db.describe_phase_g_execution_log_status(include_connection_probe=True)

        self.assertEqual(observed_phase_g_status, phase_g_status)
        describe_topology.assert_called_once_with(include_connection_probe=True)
        build_phase_g.assert_called_once_with(
            db,
            topology=topology,
            include_connection_probe=True,
        )

    def test_database_manager_failure_isolated_by_reset_allows_followup_auth_flow(self) -> None:
        self._configure_environment(postgres_url=None)

        with self.assertRaises(RuntimeError):
            with patch.object(
                DatabaseManager,
                "_run_multi_user_migrations",
                autospec=True,
                side_effect=RuntimeError("boom"),
            ):
                DatabaseManager(db_url="sqlite:///:memory:")

        self.assertIsNone(DatabaseManager._instance)

        db = DatabaseManager(db_url="sqlite:///:memory:")
        self.assertTrue(db._initialized)
        self.assertFalse(db._phase_a_enabled)


if __name__ == "__main__":
    unittest.main()
