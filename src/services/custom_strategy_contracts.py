# -*- coding: utf-8 -*-
"""Pure validation helpers for inert custom strategy contracts.

This module only validates schema payloads and computes deterministic digests.
It does not execute user Python, create runners, expose routes, or import
backtest runtime services.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from pydantic import ValidationError

from api.v1.schemas.custom_strategy import (
    MAX_CUSTOM_STRATEGY_BARS,
    MAX_CUSTOM_STRATEGY_PAYLOAD_BYTES,
    MAX_CUSTOM_STRATEGY_REASON_LENGTH,
    MAX_CUSTOM_STRATEGY_SIGNALS,
    CustomStrategyInput,
    CustomStrategyOutput,
)


def validate_custom_strategy_input(
    value: CustomStrategyInput | Mapping[str, Any],
    *,
    max_payload_bytes: int = MAX_CUSTOM_STRATEGY_PAYLOAD_BYTES,
) -> CustomStrategyInput:
    payload = value if isinstance(value, CustomStrategyInput) else CustomStrategyInput.model_validate(value)
    _validate_payload_size(payload, kind="input", max_payload_bytes=max_payload_bytes)
    return payload


def validate_custom_strategy_output(
    value: CustomStrategyOutput | Mapping[str, Any],
    *,
    max_payload_bytes: int = MAX_CUSTOM_STRATEGY_PAYLOAD_BYTES,
) -> CustomStrategyOutput:
    payload = value if isinstance(value, CustomStrategyOutput) else CustomStrategyOutput.model_validate(value)
    _validate_payload_size(payload, kind="output", max_payload_bytes=max_payload_bytes)
    return payload


def compute_custom_strategy_output_digest(value: CustomStrategyOutput | Mapping[str, Any]) -> str:
    payload = value if isinstance(value, CustomStrategyOutput) else CustomStrategyOutput.model_validate(value)
    normalized = payload.model_dump(by_alias=True, exclude_none=False)
    for collection_name in ("errors", "auditEvents"):
        collection = normalized.get(collection_name)
        if not isinstance(collection, list):
            continue
        for item in collection:
            if isinstance(item, dict) and "outputDigest" in item:
                item["outputDigest"] = None
    serialized = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def serialize_custom_strategy_validation_error(
    exc: ValidationError | ValueError,
    *,
    kind: str,
) -> dict[str, Any]:
    normalized_kind = kind.strip().lower()
    if normalized_kind not in {"input", "output"}:
        raise ValueError("kind must be input or output")
    issues = (
        _normalize_pydantic_issues(exc)
        if isinstance(exc, ValidationError)
        else [_normalize_value_error_issue(exc, kind=normalized_kind)]
    )
    return {
        "error": "validation_error",
        "message": f"Custom strategy {normalized_kind} contract validation failed",
        "issues": issues,
    }


def _validate_payload_size(
    payload: CustomStrategyInput | CustomStrategyOutput,
    *,
    kind: str,
    max_payload_bytes: int,
) -> None:
    if max_payload_bytes <= 0:
        raise ValueError("max_payload_bytes must be positive")
    payload_bytes = len(payload.model_dump_json(by_alias=True, exclude_none=False).encode("utf-8"))
    if payload_bytes > max_payload_bytes:
        raise ValueError(
            f"Custom strategy {kind} payload exceeds {max_payload_bytes} bytes: {payload_bytes}",
        )


def _normalize_pydantic_issues(exc: ValidationError) -> list[dict[str, str]]:
    normalized_issues: list[dict[str, str]] = []
    for issue in exc.errors(include_input=False, include_url=False, include_context=False):
        message = str(issue.get("msg") or "").strip()
        normalized_issues.append(
            {
                "field": _stringify_error_location(issue.get("loc")),
                "reasonCode": _normalize_reason_code(str(issue.get("type") or ""), message=message),
                "message": _normalize_issue_message(message),
            }
        )
    return sorted(normalized_issues, key=lambda item: (item["field"], item["reasonCode"], item["message"]))


def _normalize_value_error_issue(exc: ValueError, *, kind: str) -> dict[str, str]:
    message = str(exc).strip()
    if "payload exceeds" in message:
        return {
            "field": "$",
            "reasonCode": "payload_too_large",
            "message": f"Custom strategy {kind} payload exceeds byte limit",
        }
    return {
        "field": "$",
        "reasonCode": "value_error",
        "message": "Custom strategy contract validation failed",
    }


def _stringify_error_location(loc: Any) -> str:
    if not isinstance(loc, (list, tuple)) or not loc:
        return "$"
    return ".".join(str(item) for item in loc)


def _normalize_reason_code(reason_code: str, *, message: str) -> str:
    if reason_code != "value_error":
        return reason_code
    lowered = message.lower()
    if "blocked import content" in lowered:
        return "source_code_import_blocked"
    if "blocked execution content" in lowered:
        return "source_code_exec_blocked"
    if "blocked path traversal content" in lowered:
        return "source_code_path_traversal_blocked"
    if "parameter is too large" in lowered or "parameter magnitude is too large" in lowered:
        return "parameter_value_out_of_bounds"
    return reason_code


def _normalize_issue_message(message: str) -> str:
    lowered = message.lower()
    if lowered.startswith("value error, "):
        lowered = lowered[len("value error, ") :]
    if "blocked import content" in lowered or "blocked execution content" in lowered or "blocked path traversal content" in lowered:
        return "Custom strategy source code contains blocked content"
    if "parameter is too large" in lowered or "parameter magnitude is too large" in lowered:
        return "Custom strategy parameter value exceeds safe limit"
    return message


__all__ = [
    "MAX_CUSTOM_STRATEGY_BARS",
    "MAX_CUSTOM_STRATEGY_PAYLOAD_BYTES",
    "MAX_CUSTOM_STRATEGY_REASON_LENGTH",
    "MAX_CUSTOM_STRATEGY_SIGNALS",
    "compute_custom_strategy_output_digest",
    "serialize_custom_strategy_validation_error",
    "validate_custom_strategy_input",
    "validate_custom_strategy_output",
]
