# -*- coding: utf-8 -*-
"""Durable Runtime v1 prototype contract tests."""

from __future__ import annotations

import json
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
        self.assertEqual(envelope["selection_source"], "manual")

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
            symbol="AAPL",
            extra_metadata={
                "runtime_schema": "production_runtime",
                "runtimeSchema": "production_runtime_camel",
                "task_type": "analysis",
                "job_kind": "analysis",
                "fixture_name": "live_backtest",
                "source": "live_provider",
                "production_cutover_enabled": True,
                "symbol": "MSFT",
            },
        )

        self.assertEqual(envelope["runtime_schema"], DURABLE_RUNTIME_V1_SCHEMA)
        self.assertEqual(envelope["task_type"], DURABLE_RUNTIME_V1_SYNTHETIC_TASK_TYPE)
        self.assertEqual(envelope["job_kind"], "backtest_fixture")
        self.assertEqual(envelope["fixture_name"], "synthetic_backtest")
        self.assertEqual(envelope["source"], "synthetic_fixture")
        self.assertEqual(envelope["symbol"], "AAPL")
        self.assertFalse(envelope["production_cutover_enabled"])
        self.assertNotIn("runtimeSchema", envelope)

    def test_extra_metadata_drops_unsafe_internal_and_secret_keys(self) -> None:
        envelope = build_durable_runtime_envelope(
            job_kind="analysis_fixture",
            fixture_name="synthetic_success",
            symbol="AAPL",
            extra_metadata={
                "selection_source": "manual",
                "api_key": "leak-api-key",
                "accessToken": "leak-token",
                "client_secret": "leak-secret",
                "prompt_override": "leak-prompt",
                "raw_payload": "leak-raw",
                "session_id": "leak-session",
                "webhookUrl": "leak-webhook-url",
                "providerPayload": {"safe": "nope"},
                "stackTrace": "leak-stack-trace",
                "debug_info": "leak-debug",
                "authorization_header": "leak-auth",
                "cookie": "leak-cookie",
                "safe_context": {
                    "display_name": "fixture display",
                    "trace_id": "leak-nested-trace",
                    "nested": {
                        "note": "keep nested note",
                        "raw_response": "leak-nested-raw",
                    },
                },
                "events": [
                    {"name": "prepare", "provider_payload": "leak-list-provider"},
                    {"name": "execute", "detail": "keep list detail"},
                ],
            },
        )

        self.assertEqual(envelope["selection_source"], "manual")
        self.assertEqual(envelope["safe_context"]["display_name"], "fixture display")
        self.assertEqual(envelope["safe_context"]["nested"]["note"], "keep nested note")
        self.assertEqual(envelope["events"], [{"name": "prepare"}, {"name": "execute", "detail": "keep list detail"}])

        serialized = json.dumps(envelope, sort_keys=True)
        for blocked_key in (
            "api_key",
            "accessToken",
            "client_secret",
            "prompt_override",
            "raw_payload",
            "session_id",
            "webhookUrl",
            "providerPayload",
            "stackTrace",
            "debug_info",
            "authorization_header",
            "cookie",
            "trace_id",
            "raw_response",
            "provider_payload",
        ):
            with self.subTest(blocked_key=blocked_key):
                self.assertNotIn(blocked_key, serialized)
        for blocked_value in (
            "leak-api-key",
            "leak-token",
            "leak-secret",
            "leak-prompt",
            "leak-raw",
            "leak-session",
            "leak-webhook-url",
            "leak-stack-trace",
            "leak-debug",
            "leak-auth",
            "leak-cookie",
            "leak-nested-trace",
            "leak-nested-raw",
            "leak-list-provider",
        ):
            with self.subTest(blocked_value=blocked_value):
                self.assertNotIn(blocked_value, serialized)

    def test_extra_metadata_drops_secret_key_variants_recursively(self) -> None:
        envelope = build_durable_runtime_envelope(
            job_kind="analysis_fixture",
            fixture_name="synthetic_success",
            symbol="AAPL",
            extra_metadata={
                "selection_source": "manual",
                "client_api_key": "leak-client-api-key",
                "xApiKey": "leak-x-api-key",
                "privateKey": "leak-private-key",
                "password": "leak-password",
                "credentials": {"username": "leak-credential-user"},
                "safe_context": {
                    "display_name": "fixture display",
                    "clientApiKey": "leak-nested-client-api-key",
                    "credential": "leak-nested-credential",
                    "private_key": "leak-nested-private-key",
                    "children": [
                        {
                            "name": "keep list child",
                            "accessKey": "leak-list-access-key",
                        },
                        (
                            {
                                "note": "keep tuple note",
                                "secretKey": "leak-tuple-secret-key",
                            },
                        ),
                    ],
                },
            },
        )

        self.assertEqual(envelope["selection_source"], "manual")
        self.assertEqual(envelope["safe_context"]["display_name"], "fixture display")
        self.assertEqual(envelope["safe_context"]["children"][0], {"name": "keep list child"})
        self.assertEqual(envelope["safe_context"]["children"][1], [{"note": "keep tuple note"}])

        serialized = json.dumps(envelope, sort_keys=True)
        for blocked_key in (
            "client_api_key",
            "xApiKey",
            "clientApiKey",
            "privateKey",
            "password",
            "credentials",
            "credential",
            "private_key",
            "accessKey",
            "secretKey",
        ):
            with self.subTest(blocked_key=blocked_key):
                self.assertNotIn(blocked_key, serialized)
        for blocked_value in (
            "leak-client-api-key",
            "leak-x-api-key",
            "leak-private-key",
            "leak-password",
            "leak-credential-user",
            "leak-nested-client-api-key",
            "leak-nested-credential",
            "leak-nested-private-key",
            "leak-list-access-key",
            "leak-tuple-secret-key",
        ):
            with self.subTest(blocked_value=blocked_value):
                self.assertNotIn(blocked_value, serialized)


if __name__ == "__main__":
    unittest.main()
