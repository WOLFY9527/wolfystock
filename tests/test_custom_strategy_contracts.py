# -*- coding: utf-8 -*-
"""Tests for inert custom strategy contracts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.v1.schemas.custom_strategy import (
    CustomStrategyAuditEvent,
    CustomStrategyBar,
    CustomStrategyContext,
    CustomStrategyError,
    CustomStrategyInput,
    CustomStrategyOutput,
    CustomStrategyParameters,
    CustomStrategySignal,
)
from src.services.custom_strategy_contracts import (
    MAX_CUSTOM_STRATEGY_BARS,
    MAX_CUSTOM_STRATEGY_PAYLOAD_BYTES,
    MAX_CUSTOM_STRATEGY_REASON_LENGTH,
    MAX_CUSTOM_STRATEGY_SIGNALS,
    compute_custom_strategy_output_digest,
    serialize_custom_strategy_validation_error,
    validate_custom_strategy_input,
    validate_custom_strategy_output,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_IMPORTS = (
    "api.v1.endpoints.backtest",
    "src.services.backtest_service",
    "src.services.rule_backtest_service",
    "src.services.market_cache",
    "data_provider",
)


def _build_bar(index: int) -> dict[str, object]:
    return {
        "timestamp": f"2026-05-{(index % 28) + 1:02d}T09:30:00Z",
        "open": 100.0 + index,
        "high": 101.0 + index,
        "low": 99.0 + index,
        "close": 100.5 + index,
        "volume": 1000.0 + index,
    }


def _build_input(*, bars: int = 3) -> dict[str, object]:
    return {
        "strategyId": "custom-demo",
        "language": "restricted_python",
        "sourceCode": "def evaluate(ctx):\n    return []\n",
        "context": {
            "symbol": "AAPL",
            "market": "us",
            "timeframe": "1d",
            "timezone": "UTC",
            "currency": "USD",
        },
        "parameters": {
            "ints": {"fast_window": 5, "slow_window": 20},
            "floats": {"threshold": 0.25},
            "bools": {"allow_short": False},
            "strings": {"mode": "close_only"},
        },
        "bars": [_build_bar(index) for index in range(bars)],
    }


def _build_output(*, signals: int = 1, reason: str = "trend_confirmed") -> dict[str, object]:
    payload = {
        "signals": [
            {
                "timestamp": f"2026-05-{(index % 28) + 1:02d}T15:00:00Z",
                "signalType": "entry",
                "side": "long",
                "confidence": 0.75,
                "targetWeight": 0.2,
                "reason": reason,
                "reasonCodes": ["trend_confirmed", "volume_supported"],
            }
            for index in range(signals)
        ],
        "diagnostics": ["bars_loaded", "rules_checked"],
        "errors": [],
        "auditEvents": [
            {
                "eventType": "completed",
                "timestamp": "2026-05-18T08:00:00Z",
                "strategyHash": "a" * 64,
                "timeoutMs": 2500,
                "memoryLimitMb": 128,
                "exitReason": "completed",
                "outputDigest": "b" * 64,
                "reason": "completed cleanly",
            }
        ],
    }
    return payload


def test_input_contract_accepts_explicit_read_only_payload() -> None:
    contract = validate_custom_strategy_input(_build_input())

    assert isinstance(contract, CustomStrategyInput)
    assert isinstance(contract.context, CustomStrategyContext)
    assert isinstance(contract.parameters, CustomStrategyParameters)
    assert all(isinstance(item, CustomStrategyBar) for item in contract.bars)
    assert isinstance(contract.bars, tuple)
    assert contract.model_dump(by_alias=True)["language"] == "restricted_python"


def test_input_contract_exposes_no_runtime_or_secret_handle_fields() -> None:
    field_names = set(CustomStrategyInput.model_fields)

    assert {"strategy_id", "language", "source_code", "context", "parameters", "bars"} <= field_names
    for forbidden in {"db", "session", "service", "client", "filesystem", "network", "env"}:
        assert forbidden not in field_names


def test_input_contract_rejects_unknown_runtime_like_fields() -> None:
    payload = _build_input()
    payload["sessionHandle"] = "danger"

    with pytest.raises(ValidationError):
        validate_custom_strategy_input(payload)


def test_input_contract_rejects_nested_parameter_objects() -> None:
    payload = _build_input()
    payload["parameters"] = {
        "ints": {"fast_window": {"value": 5}},
        "floats": {},
        "bools": {},
        "strings": {},
    }

    with pytest.raises(ValidationError):
        validate_custom_strategy_input(payload)


def test_input_contract_enforces_max_bars() -> None:
    with pytest.raises(ValidationError):
        validate_custom_strategy_input(_build_input(bars=MAX_CUSTOM_STRATEGY_BARS + 1))


@pytest.mark.parametrize(
    ("source_code", "reason_code"),
    [
        ('import os\nos.system("echo owned")\n', "source_code_import_blocked"),
        ('result = eval("1 + 1")\n', "source_code_exec_blocked"),
        ('path = "../../etc/passwd"\n', "source_code_path_traversal_blocked"),
    ],
)
def test_input_contract_rejects_malicious_source_code_markers(source_code: str, reason_code: str) -> None:
    payload = _build_input()
    payload["sourceCode"] = source_code

    with pytest.raises(ValidationError) as exc_info:
        validate_custom_strategy_input(payload)

    serialized = serialize_custom_strategy_validation_error(exc_info.value, kind="input")
    assert serialized["issues"] == [
        {
            "field": "sourceCode",
            "reasonCode": reason_code,
            "message": "Custom strategy source code contains blocked content",
        }
    ]


def test_input_contract_rejects_unknown_nested_context_and_bar_fields() -> None:
    payload = _build_input()
    payload["context"]["sessionHandle"] = "danger"
    payload["bars"][0]["filesystemPath"] = "../../secrets.txt"

    with pytest.raises(ValidationError) as exc_info:
        validate_custom_strategy_input(payload)

    serialized = serialize_custom_strategy_validation_error(exc_info.value, kind="input")
    assert serialized["issues"] == [
        {
            "field": "bars.0.filesystemPath",
            "reasonCode": "extra_forbidden",
            "message": "Extra inputs are not permitted",
        },
        {
            "field": "context.sessionHandle",
            "reasonCode": "extra_forbidden",
            "message": "Extra inputs are not permitted",
        },
    ]


def test_input_contract_rejects_resource_abuse_like_parameter_values() -> None:
    payload = _build_input()
    payload["parameters"]["ints"]["max_iterations"] = 10**12
    payload["parameters"]["floats"]["leverage"] = 10**12

    with pytest.raises(ValidationError):
        validate_custom_strategy_input(payload)


def test_output_contract_accepts_bounded_signals_and_audit_fields() -> None:
    contract = validate_custom_strategy_output(_build_output())

    assert isinstance(contract, CustomStrategyOutput)
    assert all(isinstance(item, CustomStrategySignal) for item in contract.signals)
    assert isinstance(contract.audit_events[0], CustomStrategyAuditEvent)
    assert contract.audit_events[0].strategy_hash == "a" * 64
    assert contract.audit_events[0].timeout_ms == 2500
    assert contract.audit_events[0].memory_limit_mb == 128
    assert contract.audit_events[0].exit_reason == "completed"
    assert contract.audit_events[0].output_digest == "b" * 64


def test_output_contract_rejects_invalid_signal_side() -> None:
    payload = _build_output()
    payload["signals"][0]["side"] = "buy"

    with pytest.raises(ValidationError):
        validate_custom_strategy_output(payload)


def test_output_contract_rejects_confidence_out_of_bounds() -> None:
    payload = _build_output()
    payload["signals"][0]["confidence"] = 1.2

    with pytest.raises(ValidationError):
        validate_custom_strategy_output(payload)


def test_output_contract_rejects_reason_text_that_is_too_long() -> None:
    payload = _build_output(reason="x" * (MAX_CUSTOM_STRATEGY_REASON_LENGTH + 1))

    with pytest.raises(ValidationError):
        validate_custom_strategy_output(payload)


def test_output_contract_enforces_max_signals() -> None:
    with pytest.raises(ValidationError):
        validate_custom_strategy_output(_build_output(signals=MAX_CUSTOM_STRATEGY_SIGNALS + 1))


def test_output_contract_rejects_malformed_signal_and_audit_shapes() -> None:
    payload = _build_output()
    payload["signals"] = {"timestamp": "2026-05-18T15:00:00Z"}
    payload["auditEvents"][0]["stderrPath"] = "/tmp/strategy.stderr"

    with pytest.raises(ValidationError) as exc_info:
        validate_custom_strategy_output(payload)

    serialized = serialize_custom_strategy_validation_error(exc_info.value, kind="output")
    assert serialized["issues"] == [
        {
            "field": "auditEvents.0.stderrPath",
            "reasonCode": "extra_forbidden",
            "message": "Extra inputs are not permitted",
        },
        {
            "field": "signals",
            "reasonCode": "tuple_type",
            "message": "Input should be a valid tuple",
        },
    ]


def test_output_contract_exposes_typed_error_records() -> None:
    payload = _build_output()
    payload["errors"] = [
        {
            "code": "sandbox_timeout",
            "message": "timed out safely",
            "strategyHash": "c" * 64,
            "timeoutMs": 2500,
            "memoryLimitMb": 128,
            "exitReason": "timeout",
            "outputDigest": None,
        }
    ]

    contract = validate_custom_strategy_output(payload)

    assert isinstance(contract.errors[0], CustomStrategyError)
    assert contract.errors[0].exit_reason == "timeout"


def test_payload_size_guard_rejects_oversized_input_and_output() -> None:
    with pytest.raises(ValueError, match="payload exceeds"):
        validate_custom_strategy_input(_build_input(), max_payload_bytes=64)

    with pytest.raises(ValueError, match="payload exceeds"):
        validate_custom_strategy_output(_build_output(), max_payload_bytes=64)


def test_payload_size_error_serialization_is_structured_and_deterministic() -> None:
    with pytest.raises(ValueError) as exc_info:
        validate_custom_strategy_input(_build_input(), max_payload_bytes=64)

    serialized = serialize_custom_strategy_validation_error(exc_info.value, kind="input")
    assert serialized == {
        "error": "validation_error",
        "message": "Custom strategy input contract validation failed",
        "issues": [
            {
                "field": "$",
                "reasonCode": "payload_too_large",
                "message": "Custom strategy input payload exceeds byte limit",
            }
        ],
    }


def test_output_digest_is_stable_sha256_hex() -> None:
    first = compute_custom_strategy_output_digest(_build_output())
    second = compute_custom_strategy_output_digest(_build_output())

    assert first == second
    assert len(first) == 64
    assert set(first) <= set("0123456789abcdef")


def test_contract_modules_are_inert_and_do_not_import_runtime_domains() -> None:
    script = f"""
import json
import sys

import api.v1.schemas.custom_strategy
import src.services.custom_strategy_contracts

blocked = {list(FORBIDDEN_IMPORTS)!r}
print(json.dumps({{name: name in sys.modules for name in blocked}}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    imported = json.loads(completed.stdout)
    assert imported == {name: False for name in imported}


def test_schema_models_can_be_constructed_directly() -> None:
    signal = CustomStrategySignal(
        timestamp="2026-05-18T15:00:00Z",
        signalType="rebalance",
        side="flat",
        confidence=0.5,
        targetWeight=0.0,
        reason="rebalance_only",
        reasonCodes=["rebalance_only"],
    )
    audit = CustomStrategyAuditEvent(
        eventType="failed",
        timestamp="2026-05-18T15:00:00Z",
        strategyHash="d" * 64,
        timeoutMs=3000,
        memoryLimitMb=64,
        exitReason="validation_failed",
        outputDigest=None,
    )

    output = CustomStrategyOutput(
        signals=(signal,),
        diagnostics=("validated",),
        errors=(),
        auditEvents=(audit,),
    )

    assert isinstance(output, CustomStrategyOutput)
    assert output.audit_events[0].exit_reason == "validation_failed"


def test_validation_error_serialization_does_not_echo_malicious_source() -> None:
    payload = _build_input()
    payload["sourceCode"] = '__import__("os").system("touch /tmp/owned")'

    with pytest.raises(ValidationError) as exc_info:
        validate_custom_strategy_input(payload)

    serialized = serialize_custom_strategy_validation_error(exc_info.value, kind="input")
    dumped = json.dumps(serialized, ensure_ascii=False, sort_keys=True)

    assert "__import__" not in dumped
    assert "/tmp/owned" not in dumped
    assert "errors.pydantic.dev" not in dumped
    assert '"input"' not in dumped
