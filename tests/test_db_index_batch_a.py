# -*- coding: utf-8 -*-
"""Smoke coverage for DB Index Migration Batch A."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import inspect, text

from src.postgres_phase_a import PostgresPhaseAStore, load_phase_a_sql_statements
from src.storage import DatabaseManager


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


class DbIndexBatchATestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def test_sqlite_clean_database_initializes_batch_a_indexes(self) -> None:
        db = DatabaseManager(db_url=f"sqlite:///{self.data_dir / 'batch-a.sqlite'}")

        expected_by_table = {
            "app_users": {
                "ix_app_user_role_active",
            },
            "app_user_sessions": {
                "ix_app_user_session_user_expiry",
                "ix_app_user_session_user_revoked_expiry",
                "ix_app_user_sessions_last_seen_at",
            },
            "auth_rate_limit_buckets": {
                "ix_auth_rate_limit_type_expiry",
            },
            "durable_task_states": {
                "ix_durable_task_owner_created",
                "ix_durable_task_owner_status_created",
                "ix_durable_task_status_updated",
                "ix_durable_task_status_lease",
                "ix_durable_task_states_idempotency_key_hash",
                "ix_durable_task_states_dedupe_key_hash",
                "ux_durable_task_active_dedupe",
            },
            "durable_task_progress_events": {
                "ix_durable_task_progress_task_sequence",
                "ix_durable_task_progress_task_created",
                "ix_durable_task_progress_owner_created",
            },
        }
        for table_name, expected_indexes in expected_by_table.items():
            self.assertTrue(
                expected_indexes.issubset(_sqlite_index_names(db._engine, table_name)),
                msg=f"Missing expected indexes for {table_name}",
            )

        index_names = _all_sqlite_index_names(db._engine)
        self.assertEqual(len(index_names), len(set(index_names)))

    def test_sqlite_batch_a_index_columns_stay_portable(self) -> None:
        db = DatabaseManager(db_url=f"sqlite:///{self.data_dir / 'batch-a-columns.sqlite'}")

        session_indexes = _sqlite_index_columns(db._engine, "app_user_sessions")
        self.assertEqual(
            session_indexes["ix_app_user_session_user_revoked_expiry"],
            ("user_id", "revoked_at", "expires_at"),
        )

        durable_indexes = _sqlite_index_columns(db._engine, "durable_task_states")
        self.assertEqual(
            durable_indexes["ix_durable_task_owner_status_created"],
            ("owner_user_id", "status", "created_at"),
        )
        self.assertEqual(
            durable_indexes["ix_durable_task_states_dedupe_key_hash"],
            ("dedupe_key_hash",),
        )
        self.assertEqual(
            durable_indexes["ux_durable_task_active_dedupe"],
            ("owner_user_id", "task_type", "active_dedupe_key_hash"),
        )

        progress_indexes = _sqlite_index_columns(db._engine, "durable_task_progress_events")
        self.assertEqual(
            progress_indexes["ix_durable_task_progress_task_sequence"],
            ("task_id", "sequence"),
        )

    def test_phase_a_sqlite_schema_exposes_auth_guest_indexes(self) -> None:
        store = PostgresPhaseAStore(
            f"sqlite:///{self.data_dir / 'phase-a.sqlite'}",
            auto_apply_schema=True,
        )
        try:
            self.assertTrue(
                {
                    "idx_app_users_role_active",
                    "idx_app_user_sessions_user_expiry",
                    "idx_app_user_sessions_user_revoked_expiry",
                    "ix_app_user_sessions_last_seen_at",
                }.issubset(_sqlite_index_names(store._engine, "app_user_sessions") | _sqlite_index_names(store._engine, "app_users"))
            )
            self.assertTrue(
                {
                    "idx_guest_sessions_expires",
                    "idx_guest_sessions_started",
                }.issubset(_sqlite_index_names(store._engine, "guest_sessions"))
            )

            index_names = _all_sqlite_index_names(store._engine)
            self.assertEqual(len(index_names), len(set(index_names)))
        finally:
            store.dispose()

    def test_phase_a_baseline_sql_selects_batch_a_indexes(self) -> None:
        statements = "\n".join(load_phase_a_sql_statements())

        for index_name in (
            "idx_app_users_role_active",
            "idx_app_user_sessions_user_expiry",
            "idx_app_user_sessions_user_revoked_expiry",
            "ix_app_user_sessions_last_seen_at",
            "idx_guest_sessions_expires",
            "idx_guest_sessions_started",
        ):
            self.assertIn(index_name, statements)


if __name__ == "__main__":
    unittest.main()
