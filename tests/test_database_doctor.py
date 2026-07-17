# -*- coding: utf-8 -*-
"""Focused coverage for the database doctor support bundle flow."""

from __future__ import annotations

import json
import os
import subprocess
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
from src.storage import DatabaseManager


class DatabaseDoctorReportTestCase(unittest.TestCase):
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
        os.environ.pop("ENABLE_PHASE_F_TRADES_LIST_COMPARISON", None)
        os.environ.pop("PHASE_F_TRADES_LIST_COMPARISON_ACCOUNT_IDS", None)
        os.environ.pop("ENABLE_PHASE_F_CASH_LEDGER_COMPARISON", None)
        os.environ.pop("PHASE_F_CASH_LEDGER_COMPARISON_ACCOUNT_IDS", None)
        os.environ.pop("ENABLE_PHASE_F_CORPORATE_ACTIONS_COMPARISON", None)
        os.environ.pop("PHASE_F_CORPORATE_ACTIONS_COMPARISON_ACCOUNT_IDS", None)
        os.environ.pop("POSTGRES_PHASE_A_REAL_DSN", None)
        self.temp_dir.cleanup()

    def _configure_environment(
        self,
        *,
        postgres_url: str | None = None,
        auto_apply_schema: bool = True,
        extra_lines: list[str] | None = None,
    ) -> None:
        lines = [
            "STOCK_LIST=600519",
            "GEMINI_API_KEY=test-key",
            f"DATABASE_PATH={self.sqlite_db_path}",
        ]
        if postgres_url is not None:
            lines.append(f"POSTGRES_PHASE_A_URL={postgres_url}")
            lines.append(
                f"POSTGRES_PHASE_A_APPLY_SCHEMA={'true' if auto_apply_schema else 'false'}"
            )
        if extra_lines:
            lines.extend(extra_lines)

        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.sqlite_db_path)
        os.environ.pop("ENABLE_PHASE_F_TRADES_LIST_COMPARISON", None)
        os.environ.pop("PHASE_F_TRADES_LIST_COMPARISON_ACCOUNT_IDS", None)
        os.environ.pop("ENABLE_PHASE_F_CASH_LEDGER_COMPARISON", None)
        os.environ.pop("PHASE_F_CASH_LEDGER_COMPARISON_ACCOUNT_IDS", None)
        os.environ.pop("ENABLE_PHASE_F_CORPORATE_ACTIONS_COMPARISON", None)
        os.environ.pop("PHASE_F_CORPORATE_ACTIONS_COMPARISON_ACCOUNT_IDS", None)
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

    def test_sqlite_only_report_marks_bridge_disabled_and_includes_ai_handoff(self) -> None:
        from src.database_doctor import build_database_doctor_report, render_database_doctor_markdown

        self._configure_environment(postgres_url=None)

        report = build_database_doctor_report()
        markdown = render_database_doctor_markdown(report)

        self.assertEqual(report["sqlite_primary"]["runtime_role"], "primary_runtime")
        self.assertTrue(report["sqlite_primary"]["path_exists"])
        self.assertTrue(report["sqlite_primary"]["reachable"]["ok"])
        self.assertFalse(report["postgresql_coexistence"]["configured"])
        self.assertFalse(report["postgresql_coexistence"]["bridge_initialized"])
        self.assertIn("Paste the following with your error when asking AI for help", markdown)
        self.assertIn("src/storage.py", report["ai_handoff"]["files_to_read_first"])
        self.assertIn(
            "src/storage_postgres_bridge.py",
            report["ai_handoff"]["files_to_read_first"],
        )
        self.assertIn(
            "src/storage_topology_report.py",
            report["ai_handoff"]["files_to_read_first"],
        )
        self.assertIn(
            "src/storage_phase_g_observability.py",
            report["ai_handoff"]["files_to_read_first"],
        )
        self.assertEqual(
            report["phase_g_control_plane"]["live_source_reminder"],
            ".env remains the live source of truth for control-plane config; PostgreSQL is snapshot/shadow only.",
        )

    def test_pg_enabled_report_reuses_topology_helpers_and_phase_g_status(self) -> None:
        from src.database_doctor import build_database_doctor_report

        self._configure_environment(
            postgres_url=f"sqlite:///{self.phase_db_path}",
            auto_apply_schema=True,
        )

        report = build_database_doctor_report()
        db = DatabaseManager.get_instance()
        topology = db.describe_database_topology(include_connection_probe=True)

        self.assertTrue(report["postgresql_coexistence"]["configured"])
        self.assertTrue(report["postgresql_coexistence"]["bridge_initialized"])
        self.assertEqual(
            report["stores"]["phase_g"]["mode"],
            topology["stores"]["phase_g"]["mode"],
        )
        self.assertEqual(report["stores"]["phase_a"]["status"], "initialized")
        self.assertEqual(report["stores"]["phase_g"]["schema_apply_status"], "applied")
        self.assertEqual(
            report["phase_g_control_plane"]["execution_log_observability"]["shadow_entities"],
            ["execution_sessions", "execution_events"],
        )

    def test_missing_schema_is_classified_as_schema_bootstrap_issue(self) -> None:
        from src.database_doctor import build_database_doctor_report

        self._configure_environment(
            postgres_url=f"sqlite:///{self.phase_db_path}",
            auto_apply_schema=False,
        )

        report = build_database_doctor_report()

        self.assertTrue(report["postgresql_coexistence"]["configured"])
        self.assertTrue(report["postgresql_coexistence"]["bridge_initialized"])
        self.assertEqual(report["stores"]["phase_a"]["schema_apply_status"], "skipped")
        self.assertIn("app_users", report["stores"]["phase_a"]["missing_tables"])
        self.assertEqual(
            report["probable_issue_classification"]["category"],
            "schema_bootstrap_issue",
        )

    def test_support_bundle_output_redacts_pg_secrets_when_bridge_init_fails(self) -> None:
        from src.database_doctor import (
            build_database_doctor_report,
            render_database_doctor_json,
            render_database_doctor_markdown,
        )

        self._configure_environment(
            postgres_url="postgresql://doctor:super-secret@127.0.0.1:1/support_bundle",
            auto_apply_schema=True,
        )

        report = build_database_doctor_report()
        markdown = render_database_doctor_markdown(report)
        payload = render_database_doctor_json(report)

        self.assertFalse(report["postgresql_coexistence"]["bridge_initialized"])
        self.assertEqual(
            report["probable_issue_classification"]["category"],
            "pg_bridge_init_issue",
        )
        self.assertIn("postgresql://doctor:***@127.0.0.1:1/support_bundle", markdown)
        self.assertIn("postgresql://doctor:***@127.0.0.1:1/support_bundle", payload)
        self.assertNotIn("super-secret", markdown)
        self.assertNotIn("super-secret", payload)
        self.assertNotIn("test-key", payload)
        self.assertEqual(json.loads(payload)["postgresql_coexistence"]["configured"], True)

    def test_phase_f_authority_summary_reports_owner_scope_and_feature_specific_allowlists(self) -> None:
        from src.database_doctor import build_database_doctor_report

        self._configure_environment(
            postgres_url=f"sqlite:///{self.phase_db_path}",
            auto_apply_schema=True,
            extra_lines=[
                "ENABLE_PHASE_F_TRADES_LIST_COMPARISON=true",
                "PHASE_F_TRADES_LIST_COMPARISON_ACCOUNT_IDS=101,102",
                "ENABLE_PHASE_F_CASH_LEDGER_COMPARISON=true",
                "PHASE_F_CASH_LEDGER_COMPARISON_ACCOUNT_IDS=",
                "ENABLE_PHASE_F_CORPORATE_ACTIONS_COMPARISON=true",
                "PHASE_F_CORPORATE_ACTIONS_COMPARISON_ACCOUNT_IDS=301",
            ],
        )

        report = build_database_doctor_report()
        summary = report["phase_f_authority_summary"]

        self.assertEqual(summary["summary_model"], "phase_f_authority_permission_summary_v1")
        self.assertEqual(summary["request_actor_scope"]["allowed_roles"], ["admin", "user"])
        self.assertFalse(summary["request_actor_scope"]["comparison_specific_role_gate"])
        self.assertTrue(summary["request_actor_scope"]["owner_scope_enforced_at_api"])
        self.assertEqual(
            summary["features"]["trades_list"]["effective_account_scope"],
            "allowlisted_accounts_only",
        )
        self.assertEqual(
            summary["features"]["trades_list"]["allowlisted_account_ids"],
            [101, 102],
        )
        self.assertEqual(
            summary["features"]["cash_ledger"]["empty_allowlist_behavior"],
            "comparison_skipped",
        )
        self.assertEqual(
            summary["features"]["cash_ledger"]["effective_account_scope"],
            "no_accounts",
        )
        self.assertEqual(
            summary["features"]["corporate_actions"]["allowlisted_account_ids"],
            [301],
        )
        self.assertEqual(
            summary["non_empty_sets"],
            {
                "trades_list.allowlisted_account_ids": [101, 102],
                "corporate_actions.allowlisted_account_ids": [301],
            },
        )

    def test_real_pg_bundle_report_uses_disposable_dsn_and_verifies_phase_g_shadow(self) -> None:
        from src.database_doctor import (
            build_database_real_pg_bundle_report,
            render_database_doctor_markdown,
        )

        self._configure_environment(
            postgres_url=None,
            extra_lines=[
                "ENABLE_PHASE_F_TRADES_LIST_COMPARISON=true",
                "PHASE_F_TRADES_LIST_COMPARISON_ACCOUNT_IDS=501,502",
                "ENABLE_PHASE_F_CASH_LEDGER_COMPARISON=true",
                "PHASE_F_CASH_LEDGER_COMPARISON_ACCOUNT_IDS=501",
            ],
        )

        report = build_database_real_pg_bundle_report(
            real_pg_dsn=f"sqlite:///{self.phase_db_path}",
        )
        markdown = render_database_doctor_markdown(report)

        self.assertEqual(report["report_kind"], "database_real_pg_bundle")
        self.assertEqual(
            report["real_pg_bundle"]["bundle_model"],
            "database_real_pg_support_bundle_v1",
        )
        self.assertFalse(report["real_pg_bundle"]["safety_contract"]["sqlite_primary_truth_changed"])
        self.assertFalse(report["real_pg_bundle"]["safety_contract"]["phase_f_serving_changed"])
        self.assertTrue(
            report["real_pg_bundle"]["verification_checks"]["phase_store_initialization"]["passed"]
        )
        self.assertTrue(
            report["real_pg_bundle"]["verification_checks"]["schema_bootstrap"]["passed"]
        )
        self.assertTrue(
            report["real_pg_bundle"]["verification_checks"]["phase_g_execution_log_shadow"]["passed"]
        )
        self.assertGreaterEqual(
            report["real_pg_bundle"]["verification_checks"]["phase_g_execution_log_shadow"]["pg_session_count_delta"],
            1,
        )
        self.assertEqual(
            report["phase_f_authority_summary"]["features"]["trades_list"]["allowlisted_account_ids"],
            [501, 502],
        )
        self.assertIn("Real-PG Bundle Verification", markdown)
        self.assertIn("Real-PG Bundle AI Handoff", markdown)

    def test_real_pg_bundle_report_normalizes_transient_fields_for_deterministic_comparison(self) -> None:
        from src.database_doctor import build_database_real_pg_bundle_report

        self._configure_environment(postgres_url=None)

        report = build_database_real_pg_bundle_report(
            real_pg_dsn=f"sqlite:///{self.phase_db_path}",
        )

        normalized_sqlite_path = "<temporary>/database-real-pg-bundle.sqlite"
        self.assertEqual(report["real_pg_bundle"]["isolated_sqlite_path"], normalized_sqlite_path)
        self.assertEqual(report["sqlite_primary"]["configured_path"], normalized_sqlite_path)
        self.assertEqual(report["sqlite_primary"]["resolved_path"], normalized_sqlite_path)
        self.assertEqual(
            report["topology_summary"]["config_layer"]["sqlite_database_path"],
            normalized_sqlite_path,
        )
        self.assertEqual(
            report["real_pg_bundle"]["verification_checks"]["phase_g_execution_log_shadow"]["probe_session_id"],
            "<latest_probe_session_id>",
        )
        self.assertTrue(
            all(
                (not store_summary["bootstrap_recorded"]) or store_summary["bootstrap_applied_at"] == "<bootstrap_applied_at>"
                for store_summary in report["stores"].values()
            )
        )
        self.assertIn(
            f"- isolated_sqlite_path={normalized_sqlite_path}",
            report["real_pg_bundle"]["ai_handoff_sample"]["paste_block"],
        )
        self.assertIn(
            f"- sqlite_primary: path={normalized_sqlite_path} exists=yes reachable=yes",
            report["ai_handoff"]["paste_block"],
        )

    def test_real_pg_bundle_smoke_matches_primary_report_after_removing_generated_at(self) -> None:
        from src.database_doctor import build_database_real_pg_bundle_report
        from src.database_doctor_smoke import build_database_real_pg_bundle_smoke_report

        self._configure_environment(postgres_url=None)

        report = build_database_real_pg_bundle_report(
            real_pg_dsn=f"sqlite:///{self.phase_db_path}",
        )
        smoke_report = build_database_real_pg_bundle_smoke_report(
            real_pg_dsn=f"sqlite:///{self.phase_db_path}",
        )

        report.pop("generated_at", None)
        smoke_report.pop("generated_at", None)

        self.assertEqual(report, smoke_report)

    def test_real_pg_bundle_probe_creates_phase_g_bundle_actor_before_logging(self) -> None:
        from src.database_doctor import build_database_real_pg_bundle_report
        from src.services.execution_log_service import ExecutionLogService

        self._configure_environment(
            postgres_url=None,
            extra_lines=[
                "ENABLE_PHASE_F_TRADES_LIST_COMPARISON=true",
                "PHASE_F_TRADES_LIST_COMPARISON_ACCOUNT_IDS=501,502",
            ],
        )

        original_record_admin_action = ExecutionLogService.record_admin_action
        actor_preexisting_states: list[bool] = []

        def _wrapped_record_admin_action(service_self, *args, **kwargs):
            actor = dict(kwargs.get("actor") or {})
            if actor.get("user_id") == "database-real-pg-bundle":
                db = DatabaseManager.get_instance()
                bundle_actor = db.get_app_user("database-real-pg-bundle")
                actor_preexisting_states.append(bundle_actor is not None)
            return original_record_admin_action(service_self, *args, **kwargs)

        with patch.object(ExecutionLogService, "record_admin_action", autospec=True, side_effect=_wrapped_record_admin_action):
            report = build_database_real_pg_bundle_report(
                real_pg_dsn=f"sqlite:///{self.phase_db_path}",
            )

        self.assertEqual(actor_preexisting_states, [True])
        self.assertTrue(
            report["real_pg_bundle"]["verification_checks"]["phase_g_execution_log_shadow"]["passed"]
        )

    def test_real_pg_bundle_output_redacts_secret_dsn_on_failure(self) -> None:
        from src.database_doctor import (
            build_database_real_pg_bundle_report,
            render_database_doctor_json,
            render_database_doctor_markdown,
        )

        self._configure_environment(postgres_url=None)

        report = build_database_real_pg_bundle_report(
            real_pg_dsn="postgresql://bundle:super-secret@127.0.0.1:1/real_pg_bundle",
        )
        markdown = render_database_doctor_markdown(report)
        payload = render_database_doctor_json(report)

        self.assertEqual(report["report_kind"], "database_real_pg_bundle")
        self.assertIn("postgresql://bundle:***@127.0.0.1:1/real_pg_bundle", markdown)
        self.assertIn("postgresql://bundle:***@127.0.0.1:1/real_pg_bundle", payload)
        self.assertNotIn("super-secret", markdown)
        self.assertNotIn("super-secret", payload)
        self.assertFalse(
            report["real_pg_bundle"]["verification_checks"]["phase_store_initialization"]["passed"]
        )

    def test_script_entrypoint_real_pg_bundle_writes_markdown_and_json_outputs(self) -> None:
        markdown_path = self.data_dir / "real-pg-bundle.md"
        json_path = self.data_dir / "real-pg-bundle.json"
        self._configure_environment(postgres_url=None)

        completed = subprocess.run(
            [
                sys.executable,
                "scripts/database_doctor.py",
                "--real-pg-bundle",
                "--real-pg-dsn",
                f"sqlite:///{self.phase_db_path}",
                "--write",
                "--format",
                "json",
                "--markdown-output",
                str(markdown_path),
                "--json-output",
                str(json_path),
            ],
            cwd=str(Path(__file__).resolve().parent.parent),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["report_kind"], "database_real_pg_bundle")
        self.assertTrue(markdown_path.exists())
        self.assertTrue(json_path.exists())
        self.assertIn("Real-PG Bundle Verification", markdown_path.read_text(encoding="utf-8"))
        self.assertEqual(
            json.loads(json_path.read_text(encoding="utf-8"))["real_pg_bundle"]["bundle_model"],
            "database_real_pg_support_bundle_v1",
        )

    def test_script_entrypoint_runs_from_repo_root(self) -> None:
        self._configure_environment(postgres_url=None)

        completed = subprocess.run(
            [sys.executable, "scripts/database_doctor.py", "--format", "json"],
            cwd=str(Path(__file__).resolve().parent.parent),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["doctor_version"], "database_doctor_v1")
        self.assertFalse(payload["postgresql_coexistence"]["configured"])


if __name__ == "__main__":
    unittest.main()
