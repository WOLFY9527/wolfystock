# -*- coding: utf-8 -*-
"""Local backup/restore drill smoke coverage with disposable SQLite state."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import text

from src.storage import DatabaseManager


def _sqlite_backup(source: Path, destination: Path) -> None:
    """Create a SQLite backup artifact without mutating the source database."""
    if not source.is_file():
        raise AssertionError(f"source database does not exist: {source}")
    if source.resolve() == destination.resolve():
        raise AssertionError("backup source and destination must be different files")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()

    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as source_conn:
        with sqlite3.connect(destination) as destination_conn:
            source_conn.backup(destination_conn)


def _table_count(db: DatabaseManager, table_name: str) -> int:
    safe_table_names = {
        "app_users",
        "app_user_sessions",
        "durable_task_states",
        "durable_task_progress_events",
        "execution_log_sessions",
        "execution_log_events",
    }
    if table_name not in safe_table_names:
        raise AssertionError(f"unexpected table name: {table_name}")
    with db.get_session() as session:
        return int(session.execute(text(f"select count(*) from {table_name}")).scalar() or 0)


class BackupRestoreDrillSmokeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.source_db_path = self.data_dir / "source.sqlite"
        self.backup_path = self.data_dir / "backup-artifact.sqlite"
        self.restore_db_path = self.data_dir / "restored.sqlite"

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def _seed_source_database(self) -> None:
        db = DatabaseManager(db_url=f"sqlite:///{self.source_db_path}")
        expires_at = datetime.now() + timedelta(hours=1)

        for user_id, username in (("owner-alpha", "restore-alpha"), ("owner-beta", "restore-beta")):
            db.create_or_update_app_user(
                user_id=user_id,
                username=username,
                display_name=username.title(),
                role="user",
                password_hash=None,
                is_active=True,
            )
            db.create_app_user_session(
                session_id=f"session-{user_id}",
                user_id=user_id,
                expires_at=expires_at,
            )
            db.create_durable_task_state(
                task_id=f"task-{user_id}",
                owner_user_id=user_id,
                task_type="analysis",
                route_family="analysis",
                status="completed",
                progress=100,
                current_step="Synthetic restore drill complete",
                metadata={"drill": "backup_restore", "owner": user_id},
            )
            db.append_durable_task_progress_event(
                task_id=f"task-{user_id}",
                owner_user_id=user_id,
                event_type="completed",
                stage="restore_drill",
                progress=100,
                message="Synthetic restore drill completed",
                metadata={"sequence_label": user_id},
            )
            db.create_execution_log_session(
                session_id=f"log-{user_id}",
                task_id=f"task-{user_id}",
                code="AAPL",
                name="Synthetic AAPL",
                overall_status="running",
                truth_level="confirmed",
                summary={"meta": {"owner_user_id": user_id, "drill": "backup_restore"}},
            )
            db.append_execution_log_event(
                session_id=f"log-{user_id}",
                phase="restore_drill",
                step="seed",
                target=user_id,
                status="success",
                truth_level="confirmed",
                message="Synthetic log event",
                detail={"log": {"category": "system", "level": "NOTICE", "event_name": "RestoreDrillSeeded"}},
            )
            db.finalize_execution_log_session(
                session_id=f"log-{user_id}",
                overall_status="success",
                truth_level="confirmed",
                summary={"meta": {"owner_user_id": user_id, "drill": "backup_restore"}},
            )

        DatabaseManager.reset_instance()

    def test_disposable_sqlite_backup_restores_users_tasks_and_logs(self) -> None:
        self._seed_source_database()

        _sqlite_backup(self.source_db_path, self.backup_path)
        self.assertTrue(self.backup_path.is_file())

        _sqlite_backup(self.backup_path, self.restore_db_path)
        restored_db = DatabaseManager(db_url=f"sqlite:///{self.restore_db_path}")

        expected_counts = {
            "app_users": 2,
            "app_user_sessions": 2,
            "durable_task_states": 2,
            "durable_task_progress_events": 2,
            "execution_log_sessions": 2,
            "execution_log_events": 2,
        }
        observed_counts = {
            table_name: _table_count(restored_db, table_name)
            for table_name in expected_counts
        }
        self.assertEqual(observed_counts, expected_counts)
        self.assertIsNone(restored_db.get_app_user("bootstrap-admin"))

        alpha_user = restored_db.get_app_user("owner-alpha")
        beta_session = restored_db.get_app_user_session("session-owner-beta")
        self.assertIsNotNone(alpha_user)
        self.assertIsNotNone(beta_session)
        self.assertEqual(alpha_user.username, "restore-alpha")
        self.assertEqual(beta_session.user_id, "owner-beta")

        alpha_task = restored_db.get_durable_task_state(
            task_id="task-owner-alpha",
            owner_user_id="owner-alpha",
        )
        self.assertIsNotNone(alpha_task)
        self.assertEqual(alpha_task["status"], "completed")
        self.assertEqual(alpha_task["progress"], 100)
        self.assertIsNone(
            restored_db.get_durable_task_state(
                task_id="task-owner-alpha",
                owner_user_id="owner-beta",
            )
        )

        alpha_events = restored_db.list_durable_task_progress_events(
            task_id="task-owner-alpha",
            owner_user_id="owner-alpha",
        )
        beta_events_for_alpha_task = restored_db.list_durable_task_progress_events(
            task_id="task-owner-alpha",
            owner_user_id="owner-beta",
        )
        self.assertEqual([event["sequence"] for event in alpha_events], [1])
        self.assertEqual(beta_events_for_alpha_task, [])

        log_detail = restored_db.get_execution_log_session_detail("log-owner-alpha")
        self.assertIsNotNone(log_detail)
        self.assertEqual(log_detail["overall_status"], "success")
        self.assertEqual(log_detail["events"][0]["phase"], "restore_drill")


if __name__ == "__main__":
    unittest.main()
