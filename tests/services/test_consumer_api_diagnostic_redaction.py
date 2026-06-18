# -*- coding: utf-8 -*-
"""Tests for consumer API diagnostic redaction projections."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.helpers.packet_redaction_fuzzer import assert_packet_output_redacted


FORBIDDEN_KEYS = {
    "provider",
    "providerTier",
    "providerName",
    "providerObservation",
    "sourceRef",
    "sourceRefs",
    "sourceType",
    "sourceTier",
    "sourceAuthorityDiagnostics",
    "sourceAuthorityRouter",
    "forbiddenProviders",
    "reasonCode",
    "reasonCodes",
    "debug",
    "debugRef",
    "requestId",
    "traceId",
    "trace",
    "raw",
    "rawPayload",
    "rawJson",
    "runtime",
    "cache",
    "schemaVersion",
    "policyVersion",
    "local_db",
    "fallback_source",
    "internalRoute",
    "diagnosticRef",
    "authorityDiagnostics",
}


def _walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key))
            keys.update(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_walk_keys(child))
    return keys


def test_project_consumer_api_payload_recursively_removes_forbidden_diagnostic_keys() -> None:
    from src.services.consumer_api_diagnostic_redaction import project_consumer_api_payload

    payload = {
        "schemaVersion": "consumer_payload_v9",
        "provider": "alpaca",
        "sourceType": "unofficial_proxy",
        "sourceTier": "tier_1_configured",
        "debugRef": "market:temperature",
        "requestId": "REQ-123",
        "trace": {"traceId": "TRACE-123"},
        "nested": [
            {
                "rawPayload": {"providerName": "fallback_source"},
                "reasonCodes": ["benchmark_missing", "provider_timeout"],
                "safeObservation": "Relative strength evidence is still being reviewed.",
            }
        ],
    }

    projected = project_consumer_api_payload(payload, surface="unit-test")
    serialized = json.dumps(projected, ensure_ascii=False)

    assert FORBIDDEN_KEYS.isdisjoint(_walk_keys(projected))
    for forbidden_value in (
        "alpaca",
        "unofficial_proxy",
        "tier_1_configured",
        "market:temperature",
        "REQ-123",
        "TRACE-123",
        "fallback_source",
        "benchmark_missing",
        "provider_timeout",
    ):
        assert forbidden_value not in serialized
    assert projected["consumerSafeSourceLabel"] == "部分数据源暂不可用"
    assert projected["dataQualityState"] == "limited"
    assert projected["freshnessState"] == "limited"
    assert "benchmark evidence" in projected["missingInputs"]
    assert "evidence limited" in projected["evidenceGaps"]
    assert projected["observationBoundary"]
    assert projected["researchNextSteps"]


def test_project_consumer_api_payload_redacts_adversarial_values_without_dropping_safe_context() -> None:
    from src.services.consumer_api_diagnostic_redaction import project_consumer_api_payload

    payload = {
        "headline": "Provider timeout hit requestId=req-1; raw_payload was unavailable.",
        "summary": "Use this as observation context while public evidence is refreshed.",
        "items": [
            {
                "label": "Evidence review",
                "detail": "sourceAuthorityRouter rejected by provider runtime",
            }
        ],
    }

    projected = project_consumer_api_payload(payload, surface="unit-test")

    assert projected["summary"] == "Use this as observation context while public evidence is refreshed."
    assert projected["headline"] == "Evidence is limited for this observation."
    assert projected["items"][0]["detail"] == "Evidence is limited for this observation."
    assert_packet_output_redacted(projected, surface="consumer-api-redaction")


def test_project_consumer_api_payload_caps_high_confidence_when_evidence_is_limited() -> None:
    from src.services.consumer_api_diagnostic_redaction import project_consumer_api_payload

    payload = {
        "confidence": "high",
        "score": 0.94,
        "reasonCodes": ["benchmark_missing"],
        "evidenceGaps": ["Benchmark evidence is unavailable."],
        "decisionGrade": False,
        "observationOnly": True,
    }

    projected = project_consumer_api_payload(payload, surface="unit-test")

    assert projected["confidence"] == "limited"
    assert projected["confidenceCap"] == {
        "value": 60,
        "reason": "Evidence is limited by missing or stale inputs.",
    }
    assert projected["dataQualityState"] == "limited"
    assert projected["observationBoundary"]
    assert "benchmark evidence" in projected["missingInputs"]


@pytest.mark.parametrize(
    "key,value,expected_bucket",
    [
        ("reasonCodes", ["provider_timeout"], "evidenceGaps"),
        ("reasonCodes", ["benchmark_missing"], "missingInputs"),
        ("reasonCodes", ["stale_official_row"], "staleInputs"),
        ("sourceType", "unofficial_proxy", "evidenceGaps"),
    ],
)
def test_project_consumer_api_payload_maps_diagnostics_to_safe_evidence_buckets(
    key: str,
    value: Any,
    expected_bucket: str,
) -> None:
    from src.services.consumer_api_diagnostic_redaction import project_consumer_api_payload

    projected = project_consumer_api_payload({key: value}, surface="unit-test")

    assert projected[expected_bucket]
    assert key not in projected


def test_project_consumer_api_payload_redacts_internal_diagnostic_code_values() -> None:
    from src.services.consumer_api_diagnostic_redaction import project_consumer_api_payload

    payload = {
        "gateIssues": [
            {
                "category": "provider_authority",
                "code": "provider_fixture_not_decision_grade",
                "label": "Evidence is limited.",
            },
            {"code": "missing_iv", "label": "IV evidence is incomplete."},
            {"code": "unknown_freshness_not_decision_grade", "label": "Freshness is incomplete."},
        ],
        "expectedMove": {"expectedMoveSource": "tradier_adapter_contract"},
        "ivGreeks": {"ivRankSource": "synthetic_fixture_proxy"},
        "stock": {"code": "AAPL"},
        "strategyType": "long_call",
    }

    projected = project_consumer_api_payload(payload, surface="unit-test")
    serialized = json.dumps(projected, ensure_ascii=False)

    assert "provider_fixture_not_decision_grade" not in serialized
    assert "provider_authority" not in serialized
    assert "missing_iv" not in serialized
    assert "unknown_freshness_not_decision_grade" not in serialized
    assert "tradier_adapter_contract" not in serialized
    assert "synthetic_fixture_proxy" not in serialized
    assert projected["gateIssues"][0]["category"] == "Evidence is limited for this observation."
    assert projected["gateIssues"][0]["code"] == "Evidence is limited for this observation."
    assert projected["gateIssues"][1]["code"] == "Evidence is limited for this observation."
    assert projected["gateIssues"][2]["code"] == "Evidence is limited for this observation."
    assert projected["expectedMove"]["expectedMoveSource"] == "Evidence is limited for this observation."
    assert projected["ivGreeks"]["ivRankSource"] == "Evidence is limited for this observation."
    assert projected["stock"]["code"] == "AAPL"
    assert projected["strategyType"] == "long_call"
