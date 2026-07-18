# -*- coding: utf-8 -*-
"""Contracts for rule-backtest execution-model registry gating."""

from __future__ import annotations

import json

import pytest

from src.services.rule_backtest_execution_model_registry import (
    CURRENT_RULE_BACKTEST_EXECUTION_MODEL_ID,
    DEFAULT_RULE_BACKTEST_EXECUTION_MODEL_VERSION,
    FUTURE_RULE_BACKTEST_EXECUTION_MODEL_ID,
    PERIODIC_RULE_BACKTEST_EXECUTION_MODEL_ID,
    RuleBacktestExecutionModelUnsupportedError,
    build_rule_backtest_execution_model_registry_metadata,
    resolve_rule_backtest_execution_model_request,
)


def _assert_no_forbidden_promotion(payload: dict) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    for forbidden in (
        '"decision_grade": true',
        '"institutional_execution_realism": true',
        '"provider_calls_required": true',
        '"live_provider_calls_required": true',
        '"executable": true',
        '"supported": true',
        '"silent_runtime_semantic_change_allowed": true',
    ):
        if '"version": "v1"' in serialized and forbidden in {'"executable": true', '"supported": true'}:
            continue
        assert forbidden not in serialized, forbidden


def test_registry_exposes_each_v1_engine_identity_as_an_executable_model() -> None:
    registry = build_rule_backtest_execution_model_registry_metadata()

    assert registry["registry_version"] == "v2"
    assert registry["current_version"] == "v1"
    assert registry["default_version"] == DEFAULT_RULE_BACKTEST_EXECUTION_MODEL_VERSION
    assert registry["supported_versions"] == ["v1"]
    assert registry["default_model"]["model_id"] == "rule_backtest_default_execution_model_v1"
    assert registry["default_model"]["version"] == "v1"
    assert set(registry["models"]) == {
        CURRENT_RULE_BACKTEST_EXECUTION_MODEL_ID,
        PERIODIC_RULE_BACKTEST_EXECUTION_MODEL_ID,
        FUTURE_RULE_BACKTEST_EXECUTION_MODEL_ID,
    }
    for model_id in (
        CURRENT_RULE_BACKTEST_EXECUTION_MODEL_ID,
        PERIODIC_RULE_BACKTEST_EXECUTION_MODEL_ID,
    ):
        assert registry["models"][model_id]["supported"] is True
        assert registry["models"][model_id]["executable"] is True
        assert registry["models"][model_id]["diagnostic_only"] is True
        assert registry["models"][model_id]["decision_grade"] is False
        assert registry["models"][model_id]["provider_calls_required"] is False
        assert registry["models"][model_id]["live_provider_calls_required"] is False


def test_registry_marks_v2_as_future_unsupported_fail_closed_model() -> None:
    registry = build_rule_backtest_execution_model_registry_metadata()
    v2 = registry["models"][FUTURE_RULE_BACKTEST_EXECUTION_MODEL_ID]

    assert v2["version"] == "v2"
    assert v2["supported"] is False
    assert v2["executable"] is False
    assert v2["availability"] == "unavailable"
    assert v2["failure_policy"] == "fail_closed_before_execution"
    assert v2["provider_calls_required"] is False
    assert v2["live_provider_calls_required"] is False
    assert v2["decision_grade"] is False

    _assert_no_forbidden_promotion({"v2": v2})


@pytest.mark.parametrize(
    "request_payload",
    [
        None,
        {},
        {"version": "v1"},
        {"model_id": "rule_backtest_default_execution_model_v1"},
        "v1",
    ],
)
def test_resolver_accepts_omitted_or_explicit_v1_request_metadata(request_payload: object) -> None:
    resolved = resolve_rule_backtest_execution_model_request(request_payload)

    assert resolved["requested_version"] in {None, "v1"}
    assert resolved["resolved_version"] == "v1"
    assert resolved["supported"] is True
    assert resolved["executable"] is True
    assert resolved["execution_model"]["version"] == "v1"
    assert resolved["execution_model"]["model_id"] == "rule_backtest_default_execution_model_v1"


@pytest.mark.parametrize(
    "request_payload, requested_version",
    [
        ({"version": "v2"}, "v2"),
        ({"model_id": "rule_backtest_default_execution_model_v2"}, "v2"),
        ("v2", "v2"),
        ({"version": "quant-v9"}, "quant-v9"),
        ({"model_id": "custom_secret_token_model"}, "unknown"),
    ],
)
def test_resolver_rejects_v2_or_unknown_model_fail_closed(
    request_payload: object,
    requested_version: str,
) -> None:
    with pytest.raises(RuleBacktestExecutionModelUnsupportedError) as exc_info:
        resolve_rule_backtest_execution_model_request(request_payload)

    detail = exc_info.value.to_error_detail()
    assert detail["error"] == "unsupported_execution_model"
    assert detail["message"] == "Unsupported rule backtest execution model. Current supported execution model is v1."
    assert detail["requested_version"] == requested_version
    assert detail["supported_versions"] == ["v1"]


def test_registry_metadata_is_json_safe_and_does_not_imply_institutional_realism() -> None:
    registry = build_rule_backtest_execution_model_registry_metadata()

    json.dumps(registry, ensure_ascii=False, sort_keys=True)
    assert registry["guardrails"]["unsupported_versions_fail_closed"] is True
    assert registry["guardrails"]["unsupported_versions_silently_downgraded"] is False
    assert registry["guardrails"]["engine_math_changed"] is True
    assert registry["guardrails"]["fill_state_model_changed"] is True
    assert registry["guardrails"]["stored_result_semantics_changed"] is True
    assert registry["guardrails"]["provider_calls_executed"] is False
    assert registry["guardrails"]["decision_grade"] is False
    _assert_no_forbidden_promotion(
        {
            "v2": registry["models"][FUTURE_RULE_BACKTEST_EXECUTION_MODEL_ID],
            "guardrails": registry["guardrails"],
        }
    )
