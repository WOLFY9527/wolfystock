# -*- coding: utf-8 -*-
"""Custom strategy schemas for future sandboxed strategy execution.

This module defines inert contracts only. It does not execute user code, load
runtime services, expose routes, or add notebook/runner behavior.
"""

from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_CUSTOM_STRATEGY_BARS = 5000
MAX_CUSTOM_STRATEGY_SIGNALS = 128
MAX_CUSTOM_STRATEGY_REASON_LENGTH = 240
MAX_CUSTOM_STRATEGY_PAYLOAD_BYTES = 256 * 1024
MAX_CUSTOM_STRATEGY_REASON_CODES = 8
MAX_CUSTOM_STRATEGY_DIAGNOSTICS = 32
MAX_CUSTOM_STRATEGY_PARAMETER_KEYS = 32
MAX_CUSTOM_STRATEGY_PARAMETER_STRING_LENGTH = 128
MAX_CUSTOM_STRATEGY_SOURCE_CODE_LENGTH = 16000

_SAFE_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9_:-]{0,63}$")
_SAFE_KEY_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$")
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


class _CustomStrategySchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


def _validate_safe_code(value: str, *, field_name: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    if not _SAFE_CODE_RE.fullmatch(normalized):
        raise ValueError(f"{field_name} must use lowercase safe code format")
    return normalized


def _validate_string_tuple(value: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    normalized: list[str] = []
    for item in value:
        code = _validate_safe_code(item, field_name=field_name)
        normalized.append(code)
    return tuple(normalized)


def _validate_parameter_mapping(
    mapping: dict[str, int] | dict[str, float] | dict[str, bool] | dict[str, str],
    *,
    field_name: str,
) -> dict[str, int] | dict[str, float] | dict[str, bool] | dict[str, str]:
    if len(mapping) > MAX_CUSTOM_STRATEGY_PARAMETER_KEYS:
        raise ValueError(f"{field_name} exceeds max parameter keys")
    for key, value in mapping.items():
        if not _SAFE_KEY_RE.fullmatch(key):
            raise ValueError(f"{field_name} has invalid parameter key: {key}")
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError(f"{field_name} has empty string parameter value: {key}")
            if len(stripped) > MAX_CUSTOM_STRATEGY_PARAMETER_STRING_LENGTH:
                raise ValueError(f"{field_name} string parameter is too long: {key}")
            mapping[key] = stripped
        elif isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError(f"{field_name} has non-finite float parameter: {key}")
    return mapping


class CustomStrategyBar(_CustomStrategySchema):
    timestamp: str = Field(..., min_length=1, max_length=64)
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None

    @field_validator("open", "high", "low", "close", "volume")
    @classmethod
    def _validate_finite_numbers(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if not math.isfinite(value):
            raise ValueError("bar values must be finite")
        return value


class CustomStrategyContext(_CustomStrategySchema):
    symbol: str = Field(..., min_length=1, max_length=32)
    market: Literal["cn", "hk", "us", "global"]
    timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
    timezone: str = Field(..., min_length=1, max_length=64)
    currency: str = Field(..., min_length=1, max_length=16)


class CustomStrategyParameters(_CustomStrategySchema):
    ints: dict[str, int] = Field(default_factory=dict)
    floats: dict[str, float] = Field(default_factory=dict)
    bools: dict[str, bool] = Field(default_factory=dict)
    strings: dict[str, str] = Field(default_factory=dict)

    @field_validator("ints")
    @classmethod
    def _validate_ints(cls, value: dict[str, int]) -> dict[str, int]:
        return _validate_parameter_mapping(value, field_name="ints")

    @field_validator("floats")
    @classmethod
    def _validate_floats(cls, value: dict[str, float]) -> dict[str, float]:
        return _validate_parameter_mapping(value, field_name="floats")

    @field_validator("bools")
    @classmethod
    def _validate_bools(cls, value: dict[str, bool]) -> dict[str, bool]:
        return _validate_parameter_mapping(value, field_name="bools")

    @field_validator("strings")
    @classmethod
    def _validate_strings(cls, value: dict[str, str]) -> dict[str, str]:
        return _validate_parameter_mapping(value, field_name="strings")


class CustomStrategyInput(_CustomStrategySchema):
    strategy_id: str = Field(..., alias="strategyId", min_length=1, max_length=64)
    language: Literal["dsl", "restricted_python"]
    source_code: str = Field(..., alias="sourceCode", min_length=1, max_length=MAX_CUSTOM_STRATEGY_SOURCE_CODE_LENGTH)
    context: CustomStrategyContext
    parameters: CustomStrategyParameters = Field(default_factory=CustomStrategyParameters)
    bars: tuple[CustomStrategyBar, ...] = Field(..., min_length=1, max_length=MAX_CUSTOM_STRATEGY_BARS)

    @field_validator("strategy_id")
    @classmethod
    def _validate_strategy_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("source_code")
    @classmethod
    def _validate_source_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("sourceCode must not be empty")
        return normalized


class CustomStrategySignal(_CustomStrategySchema):
    timestamp: str = Field(..., min_length=1, max_length=64)
    signal_type: Literal["entry", "exit", "rebalance", "hold"] = Field(..., alias="signalType")
    side: Literal["long", "short", "flat"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    target_weight: float | None = Field(None, alias="targetWeight", ge=-1.0, le=1.0)
    reason: str | None = Field(None, min_length=1, max_length=MAX_CUSTOM_STRATEGY_REASON_LENGTH)
    reason_codes: tuple[str, ...] = Field(
        default_factory=tuple,
        alias="reasonCodes",
        max_length=MAX_CUSTOM_STRATEGY_REASON_CODES,
    )

    @field_validator("confidence", "target_weight")
    @classmethod
    def _validate_signal_numbers(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if not math.isfinite(value):
            raise ValueError("signal numeric values must be finite")
        return value

    @field_validator("reason")
    @classmethod
    def _validate_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("reason must not be empty when provided")
        return normalized

    @field_validator("reason_codes")
    @classmethod
    def _validate_reason_codes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_string_tuple(value, field_name="reasonCodes")


class CustomStrategyError(_CustomStrategySchema):
    code: str = Field(..., min_length=1, max_length=64)
    message: str = Field(..., min_length=1, max_length=MAX_CUSTOM_STRATEGY_REASON_LENGTH)
    strategy_hash: str = Field(..., alias="strategyHash", min_length=64, max_length=64)
    timeout_ms: int = Field(..., alias="timeoutMs", ge=1, le=60000)
    memory_limit_mb: int = Field(..., alias="memoryLimitMb", ge=1, le=4096)
    exit_reason: str = Field(..., alias="exitReason", min_length=1, max_length=64)
    output_digest: str | None = Field(None, alias="outputDigest", min_length=64, max_length=64)

    @field_validator("code", "exit_reason")
    @classmethod
    def _validate_error_codes(cls, value: str) -> str:
        return _validate_safe_code(value, field_name="error field")

    @field_validator("strategy_hash", "output_digest")
    @classmethod
    def _validate_hashes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not _SHA256_HEX_RE.fullmatch(normalized):
            raise ValueError("hash fields must be 64 lowercase hex chars")
        return normalized

    @field_validator("message")
    @classmethod
    def _validate_error_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("message must not be empty")
        return normalized


class CustomStrategyAuditEvent(_CustomStrategySchema):
    event_type: Literal["queued", "started", "completed", "failed", "timeout", "killed"] = Field(
        ...,
        alias="eventType",
    )
    timestamp: str = Field(..., min_length=1, max_length=64)
    strategy_hash: str = Field(..., alias="strategyHash", min_length=64, max_length=64)
    timeout_ms: int = Field(..., alias="timeoutMs", ge=1, le=60000)
    memory_limit_mb: int = Field(..., alias="memoryLimitMb", ge=1, le=4096)
    exit_reason: str = Field(..., alias="exitReason", min_length=1, max_length=64)
    output_digest: str | None = Field(None, alias="outputDigest", min_length=64, max_length=64)
    reason: str | None = Field(None, min_length=1, max_length=MAX_CUSTOM_STRATEGY_REASON_LENGTH)

    @field_validator("strategy_hash", "output_digest")
    @classmethod
    def _validate_hashes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not _SHA256_HEX_RE.fullmatch(normalized):
            raise ValueError("hash fields must be 64 lowercase hex chars")
        return normalized

    @field_validator("exit_reason")
    @classmethod
    def _validate_exit_reason(cls, value: str) -> str:
        return _validate_safe_code(value, field_name="exitReason")

    @field_validator("reason")
    @classmethod
    def _validate_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("reason must not be empty when provided")
        return normalized


class CustomStrategyOutput(_CustomStrategySchema):
    signals: tuple[CustomStrategySignal, ...] = Field(default_factory=tuple, max_length=MAX_CUSTOM_STRATEGY_SIGNALS)
    diagnostics: tuple[str, ...] = Field(default_factory=tuple, max_length=MAX_CUSTOM_STRATEGY_DIAGNOSTICS)
    errors: tuple[CustomStrategyError, ...] = Field(default_factory=tuple)
    audit_events: tuple[CustomStrategyAuditEvent, ...] = Field(default_factory=tuple, alias="auditEvents")

    @field_validator("diagnostics")
    @classmethod
    def _validate_diagnostics(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized: list[str] = []
        for item in value:
            text = item.strip().lower()
            if not text:
                raise ValueError("diagnostics entries must not be empty")
            if len(text) > 64:
                raise ValueError("diagnostics entries must be bounded")
            normalized.append(text)
        return tuple(normalized)


__all__ = [
    "MAX_CUSTOM_STRATEGY_BARS",
    "MAX_CUSTOM_STRATEGY_DIAGNOSTICS",
    "MAX_CUSTOM_STRATEGY_PARAMETER_KEYS",
    "MAX_CUSTOM_STRATEGY_PARAMETER_STRING_LENGTH",
    "MAX_CUSTOM_STRATEGY_PAYLOAD_BYTES",
    "MAX_CUSTOM_STRATEGY_REASON_CODES",
    "MAX_CUSTOM_STRATEGY_REASON_LENGTH",
    "MAX_CUSTOM_STRATEGY_SIGNALS",
    "MAX_CUSTOM_STRATEGY_SOURCE_CODE_LENGTH",
    "CustomStrategyAuditEvent",
    "CustomStrategyBar",
    "CustomStrategyContext",
    "CustomStrategyError",
    "CustomStrategyInput",
    "CustomStrategyOutput",
    "CustomStrategyParameters",
    "CustomStrategySignal",
]
