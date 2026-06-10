# -*- coding: utf-8 -*-
"""Durable Runtime v1 prototype contract tests."""

from __future__ import annotations

import unittest

from src.services.durable_runtime_contracts import (
    DURABLE_RUNTIME_PRODUCTION_CUTOVER_ENABLED,
    DURABLE_RUNTIME_V1_SCHEMA,
    DURABLE_RUNTIME_V1_SYNTHETIC_TASK_TYPE,
    build_durable_runtime_envelope,
    normalize_durable_runtime_status,
)


class DurableRuntimeContractsTestCase(unittest.TestCase):
    def test_status_mapping_projects_stored_states_to_api_safe_statuses(self) -> None:
        expected = {
            "queued": "pending",
            "pending": "pending",
            "waiting_retry": "pending",
            "leased": "processing",
            "processing": "processing",
            "running": "processing",
            "completed": "completed",
            "failed": "failed",
            "cancelled": "failed",
            "canceled": "failed",
            "unexpected": "processing",
            "": "pending",
            None: "pending",
        }

        for stored_status, api_status in expected.items():
            with self.subTest(stored_status=stored_status):
                self.assertEqual(normalize_durable_runtime_status(stored_status), api_status)

    def test_synthetic_envelope_is_guarded_and_cutover_disabled(self) -> None:
        envelope = build_durable_runtime_envelope(
            job_kind="analysis_fixture",
            fixture_name="synthetic_success",
            symbol="AAPL",
            extra_metadata={"selection_source": "manual"},
        )

        self.assertEqual(envelope["runtime_schema"], DURABLE_RUNTIME_V1_SCHEMA)
        self.assertEqual(envelope["task_type"], DURABLE_RUNTIME_V1_SYNTHETIC_TASK_TYPE)
        self.assertEqual(envelope["job_kind"], "analysis_fixture")
        self.assertEqual(envelope["fixture_name"], "synthetic_success")
        self.assertEqual(envelope["source"], "synthetic_fixture")
        self.assertEqual(envelope["symbol"], "AAPL")
        self.assertFalse(envelope["production_cutover_enabled"])
        self.assertFalse(DURABLE_RUNTIME_PRODUCTION_CUTOVER_ENABLED)
        self.assertNotEqual(DURABLE_RUNTIME_V1_SYNTHETIC_TASK_TYPE, "analysis")

    def test_envelope_rejects_live_or_unknown_job_kinds(self) -> None:
        for job_kind in ("analysis", "backtest", "provider_live", "unknown"):
            with self.subTest(job_kind=job_kind):
                with self.assertRaises(ValueError):
                    build_durable_runtime_envelope(
                        job_kind=job_kind,
                        fixture_name="synthetic_success",
                    )

    def test_envelope_rejects_empty_fixture_name(self) -> None:
        with self.assertRaises(ValueError):
            build_durable_runtime_envelope(
                job_kind="analysis_fixture",
                fixture_name="",
            )

    def test_extra_metadata_cannot_override_synthetic_guards(self) -> None:
        envelope = build_durable_runtime_envelope(
            job_kind="backtest_fixture",
            fixture_name="synthetic_backtest",
            extra_metadata={
                "runtime_schema": "production_runtime",
                "task_type": "analysis",
                "source": "live_provider",
                "production_cutover_enabled": True,
            },
        )

        self.assertEqual(envelope["runtime_schema"], DURABLE_RUNTIME_V1_SCHEMA)
        self.assertEqual(envelope["task_type"], DURABLE_RUNTIME_V1_SYNTHETIC_TASK_TYPE)
        self.assertEqual(envelope["source"], "synthetic_fixture")
        self.assertFalse(envelope["production_cutover_enabled"])


if __name__ == "__main__":
    unittest.main()
