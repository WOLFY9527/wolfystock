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


__all__ = [
    "MAX_CUSTOM_STRATEGY_BARS",
    "MAX_CUSTOM_STRATEGY_PAYLOAD_BYTES",
    "MAX_CUSTOM_STRATEGY_REASON_LENGTH",
    "MAX_CUSTOM_STRATEGY_SIGNALS",
    "compute_custom_strategy_output_digest",
    "validate_custom_strategy_input",
    "validate_custom_strategy_output",
]
