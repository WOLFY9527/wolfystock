# -*- coding: utf-8 -*-
"""Tests for shared research packet redaction fuzzer helpers."""

from __future__ import annotations

import pytest

from tests.helpers.packet_redaction_fuzzer import (
    REQUIRED_REDACTION_CATEGORIES,
    assert_packet_output_redacted,
    collect_packet_redaction_leaks,
    redaction_fuzzer_payload,
    redaction_fuzzer_strings,
)


def test_redaction_fuzzer_payload_exercises_required_boundary_categories() -> None:
    leaks = collect_packet_redaction_leaks(
        redaction_fuzzer_payload(),
        surface="fuzzer-payload",
    )

    observed = {leak.category for leak in leaks}
    assert REQUIRED_REDACTION_CATEGORIES <= observed


def test_redaction_fuzzer_strings_cover_task_boundary_terms() -> None:
    corpus = " ".join(redaction_fuzzer_strings()).lower()

    for expected in (
        "provider",
        "cache",
        "runtime",
        "debug",
        "raw_payload",
        "schemaversion",
        "traceid",
        "sourceref",
        "requestid",
        "buy",
        "sell",
        "hold",
        "recommend",
        "target price",
        "stop loss",
        "position sizing",
        "provider_timeout",
        "admindiagnostics",
    ):
        assert expected in corpus


def test_assert_packet_output_redacted_accepts_bounded_product_copy() -> None:
    payload = {
        "consumerProjection": {
            "status": "PARTIAL",
            "headline": "Some evidence is still being reviewed.",
            "lanes": [
                {
                    "lane": "fundamentals",
                    "state": "PARTIAL",
                    "headline": "Some quality checks are not fully cleared yet.",
                }
            ],
        },
        "researchSummary": "Use this as observation context while public evidence is refreshed.",
    }

    assert_packet_output_redacted(payload, surface="bounded-copy")


def test_assert_packet_output_redacted_reports_category_and_path() -> None:
    payload = {
        "consumerProjection": {
            "headline": "Buy now after provider_timeout",
        }
    }

    with pytest.raises(AssertionError) as exc_info:
        assert_packet_output_redacted(payload, surface="unsafe-packet")

    message = str(exc_info.value)
    assert "unsafe-packet" in message
    assert "advice_wording" in message
    assert "internal_reason_code" in message
    assert "consumerProjection.headline" in message
