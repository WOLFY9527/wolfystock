# -*- coding: utf-8 -*-
"""Tests for bounded, best-effort LLM instrumentation helpers."""

from __future__ import annotations

import unittest

from src.services.llm_instrumentation import (
    bucket_duration_ms,
    bucket_retry_reason,
    bucket_token_count,
    emit_llm_event,
    reset_llm_event_counters,
    set_llm_event_sink,
    snapshot_llm_event_counters,
)


class TestLlmInstrumentationHelpers(unittest.TestCase):
    def setUp(self) -> None:
        reset_llm_event_counters()
        set_llm_event_sink(None)

    def tearDown(self) -> None:
        set_llm_event_sink(None)
        reset_llm_event_counters()

    def test_buckets_are_bounded(self) -> None:
        self.assertEqual(bucket_duration_ms(42), "lt_100ms")
        self.assertEqual(bucket_duration_ms(4_200), "1s-5s")
        self.assertEqual(bucket_token_count(999), "1-999")
        self.assertEqual(bucket_token_count(12_500), "10k-50k")
        self.assertEqual(bucket_retry_reason("Timed out waiting for provider"), "timeout")
        self.assertEqual(bucket_retry_reason("JSON parse failed"), "parse_error")

    def test_emit_sanitizes_and_counts_event(self) -> None:
        emit_llm_event(
            "llm_call_completed",
            call_type="analysis",
            provider="gemini",
            model_family="gemini/gemini-2.5-flash",
            attempt_index=2,
            fallback_depth=1,
            duration_bucket=3_200,
            token_bucket=12_500,
            retry_reason="Timed out waiting for provider",
            outcome="success",
            raw_prompt="should not leak",
        )

        snapshot = snapshot_llm_event_counters()
        self.assertEqual(len(snapshot), 1)
        entry = snapshot[0]
        self.assertEqual(entry["event"], "llm_call_completed")
        self.assertEqual(entry["count"], 1)
        self.assertEqual(entry["labels"]["call_type"], "analysis")
        self.assertEqual(entry["labels"]["provider"], "gemini")
        self.assertEqual(entry["labels"]["model_family"], "gemini/gemini-2.5")
        self.assertEqual(entry["labels"]["attempt_index"], "2")
        self.assertEqual(entry["labels"]["fallback_depth"], "1")
        self.assertEqual(entry["labels"]["duration_bucket"], "1s-5s")
        self.assertEqual(entry["labels"]["token_bucket"], "10k-50k")
        self.assertEqual(entry["labels"]["retry_reason"], "timeout")
        self.assertEqual(entry["labels"]["outcome"], "success")
        self.assertNotIn("raw_prompt", entry["labels"])

    def test_emit_swallow_sink_errors(self) -> None:
        calls: list[dict[str, str]] = []

        def failing_sink(event_name: str, labels: dict[str, str]) -> None:
            calls.append({"event": event_name, **labels})
            raise RuntimeError("sink failed")

        set_llm_event_sink(failing_sink)

        emit_llm_event("llm_call_started", call_type="analysis", provider="gemini")
        self.assertEqual(len(calls), 1)
        self.assertEqual(snapshot_llm_event_counters()[0]["count"], 1)

