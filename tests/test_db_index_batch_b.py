# -*- coding: utf-8 -*-
"""Non-destructive smoke coverage for DB Index Batch B foundations."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import inspect, text

from src.storage import DatabaseManager


BASELINE_SQL_PATH = Path(__file__).resolve().parents[1] / "docs" / "architecture" / "postgresql-baseline-v1.sql"


def _sqlite_index_names(engine, table_name: str) -> set[str]:
    return {str(index["name"]) for index in inspect(engine).get_indexes(table_name)}


def _sqlite_index_columns(engine, table_name: str) -> dict[str, tuple[str, ...]]:
    return {
        str(index["name"]): tuple(str(column) for column in index.get("column_names") or ())
        for index in inspect(engine).get_indexes(table_name)
    }


def _all_sqlite_index_names(engine) -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                select name
                from sqlite_master
                where type = 'index'
                  and name not like 'sqlite_autoindex_%'
                """
            )
        ).fetchall()
    return [str(row[0]) for row in rows]


class DbIndexBatchBSmokeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def test_sqlite_clean_database_exposes_batch_b_foundation_indexes(self) -> None:
        db = DatabaseManager(db_url=f"sqlite:///{self.data_dir / 'batch-b.sqlite'}")

        expected_by_table = {
            "execution_log_sessions": {
                "ix_execution_log_sessions_started_at",
                "ix_exec_session_code_started",
                "ix_exec_session_query_started",
            },
            "execution_log_events": {
                "ix_exec_event_session_time",
                "ix_exec_event_phase_status",
                "ix_execution_log_events_target",
            },
            "llm_usage": {
                "ix_llm_usage_called_at",
                "ix_llm_usage_call_type",
            },
            "llm_cost_ledger": {
                "ix_llm_cost_ledger_owner_created",
                "ix_llm_cost_ledger_owner_route_created",
                "ix_llm_cost_ledger_provider_model_created",
                "ix_llm_cost_ledger_route_created",
            },
            "provider_quota_windows": {
                "ix_provider_quota_window_owner_provider",
                "ix_provider_quota_window_provider_route",
                "ix_provider_quota_window_probe",
                "ix_provider_quota_window_burn",
            },
            "provider_circuit_events": {
                "ix_provider_circuit_event_provider_time",
                "ix_provider_circuit_event_to_state_time",
                "ix_provider_circuit_event_owner_time",
                "ix_provider_circuit_event_type_time",
                "ix_provider_circuit_event_reason_time",
            },
            "provider_probe_events": {
                "ix_provider_probe_event_provider_time",
                "ix_provider_probe_event_actor_time",
                "ix_provider_probe_event_result_time",
                "ix_provider_probe_event_state_time",
            },
        }
        for table_name, expected_indexes in expected_by_table.items():
            self.assertTrue(
                expected_indexes.issubset(_sqlite_index_names(db._engine, table_name)),
                msg=f"Missing expected Batch B foundation indexes for {table_name}",
            )

        index_names = _all_sqlite_index_names(db._engine)
        self.assertEqual(len(index_names), len(set(index_names)))

    def test_sqlite_batch_b_foundation_index_columns_stay_portable(self) -> None:
        db = DatabaseManager(db_url=f"sqlite:///{self.data_dir / 'batch-b-columns.sqlite'}")

        session_indexes = _sqlite_index_columns(db._engine, "execution_log_sessions")
        self.assertEqual(session_indexes["ix_exec_session_code_started"], ("code", "started_at"))
        self.assertEqual(session_indexes["ix_exec_session_query_started"], ("query_id", "started_at"))

        event_indexes = _sqlite_index_columns(db._engine, "execution_log_events")
        self.assertEqual(event_indexes["ix_exec_event_session_time"], ("session_id", "event_at"))
        self.assertEqual(event_indexes["ix_exec_event_phase_status"], ("phase", "status"))

        cost_indexes = _sqlite_index_columns(db._engine, "llm_cost_ledger")
        self.assertEqual(cost_indexes["ix_llm_cost_ledger_owner_created"], ("owner_user_id", "created_at"))
        self.assertEqual(
            cost_indexes["ix_llm_cost_ledger_owner_route_created"],
            ("owner_user_id", "route_family", "created_at"),
        )
        self.assertEqual(
            cost_indexes["ix_llm_cost_ledger_provider_model_created"],
            ("provider", "model", "created_at"),
        )

        quota_indexes = _sqlite_index_columns(db._engine, "provider_quota_windows")
        self.assertEqual(
            quota_indexes["ix_provider_quota_window_owner_provider"],
            ("owner_user_id", "provider", "route_family", "window_start", "window_end"),
        )
        self.assertEqual(
            quota_indexes["ix_provider_quota_window_provider_route"],
            ("provider", "provider_category", "route_family", "window_start", "window_end"),
        )

        circuit_indexes = _sqlite_index_columns(db._engine, "provider_circuit_events")
        self.assertEqual(
            circuit_indexes["ix_provider_circuit_event_provider_time"],
            ("provider", "provider_category", "route_family", "created_at"),
        )

        probe_indexes = _sqlite_index_columns(db._engine, "provider_probe_events")
        self.assertEqual(
            probe_indexes["ix_provider_probe_event_provider_time"],
            ("provider", "provider_category", "probe_type", "created_at"),
        )

    def test_postgresql_baseline_exposes_provider_and_admin_batch_b_foundations(self) -> None:
        baseline_sql = BASELINE_SQL_PATH.read_text(encoding="utf-8")

        for index_name in (
            "idx_execution_sessions_started",
            "idx_execution_sessions_owner_started",
            "idx_execution_events_session_time",
            "idx_execution_events_phase_status",
            "idx_admin_logs_occurred",
            "ix_provider_quota_window_owner_provider",
            "ix_provider_quota_window_provider_route",
            "ix_provider_quota_window_probe",
            "ix_provider_quota_window_burn",
            "ix_provider_circuit_event_provider_time",
            "ix_provider_circuit_event_to_state_time",
            "ix_provider_circuit_event_owner_time",
            "ix_provider_circuit_event_type_time",
            "ix_provider_circuit_event_reason_time",
            "ix_provider_probe_event_provider_time",
            "ix_provider_probe_event_actor_time",
            "ix_provider_probe_event_result_time",
            "ix_provider_probe_event_state_time",
        ):
            self.assertIn(index_name, baseline_sql)


if __name__ == "__main__":
    unittest.main()
