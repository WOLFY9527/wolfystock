# -*- coding: utf-8 -*-
"""Provider result primitives shared by future provider integrations."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Generic, Mapping, Optional, TypeVar

from src.contracts.evidence import RawAvailability, SourceObservationFacts
from src.utils.security import sanitize_message, sanitize_metadata


PROVIDER_DATA_RESULT_VERSION = "provider_data_result_v1"

_DataT = TypeVar("_DataT")


class ProviderStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ProviderDataState(str, Enum):
    """Raw provider outcome without consumer interpretation."""

    OBSERVED = "observed"
    EMPTY = "empty"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class ProviderReason(str, Enum):
    MISSING_API_KEY = "missing_api_key"
    NOT_CONFIGURED = "not_configured"
    FORBIDDEN = "forbidden"
    UNAUTHORIZED = "unauthorized"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    INVALID_PAYLOAD = "invalid_payload"
    NO_DATA = "no_data"
    CIRCUIT_OPEN = "circuit_open"
    PROVIDER_UNHEALTHY = "provider_unhealthy"
    UNSUPPORTED_MARKET = "unsupported_market"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    PREVIOUS_PROVIDER_SUCCEEDED = "previous_provider_succeeded"
    PREVIOUS_MODEL_SUCCEEDED = "previous_model_succeeded"
    DISABLED_BY_STRATEGY = "disabled_by_strategy"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN_ERROR = "unknown_error"


class ProviderCapability(str, Enum):
    QUOTE = "quote"
    HISTORY = "history"
    TECHNICAL = "technical"
    FUNDAMENTALS = "fundamentals"
    NEWS = "news"
    MARKET_CONTEXT = "market_context"
    MACRO = "macro"
    CRYPTO_TICKER = "crypto_ticker"
    CRYPTO_KLINE = "crypto_kline"
    LLM_COMPLETION = "llm_completion"
    DATA_SOURCE_VALIDATION = "data_source_validation"
    NOTIFICATION = "notification"
    BROKER_QUOTE = "broker_quote"
    BROKER_ORDER = "broker_order"


class ProviderSourceType(str, Enum):
    OFFICIAL_API = "official_api"
    PUBLIC_API = "public_api"
    UNOFFICIAL_PUBLIC_API = "unofficial_public_api"
    EXCHANGE_PUBLIC = "exchange_public"
    CRAWLER_HTML = "crawler_html"
    COMPUTED = "computed"
    FALLBACK = "fallback"
    MOCK = "mock"
    INTERNAL = "internal"


@dataclass(frozen=True, slots=True)
class ProviderCacheIdentity:
    """Opaque cache entry identity supplied by an existing cache contract."""

    key: str

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("cache identity key must be a non-empty string")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProviderCacheIdentity":
        payload = _strict_mapping(value, expected={"key"}, context="cache identity")
        return cls(key=_strict_string(payload["key"], field="cache identity key"))

    def to_dict(self) -> dict[str, str]:
        return {"key": self.key}


@dataclass(frozen=True, slots=True)
class ProviderDataResult(Generic[_DataT]):
    """Single immutable result authority for normalized provider data."""

    capability: ProviderCapability
    state: ProviderDataState
    data: _DataT | None
    facts: SourceObservationFacts
    reason: ProviderReason | None = None
    error_message: str | None = None
    cache_identity: ProviderCacheIdentity | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.capability, ProviderCapability):
            raise TypeError("capability must be a ProviderCapability")
        if not isinstance(self.state, ProviderDataState):
            raise TypeError("state must be a ProviderDataState")
        if not isinstance(self.facts, SourceObservationFacts):
            raise TypeError("facts must be SourceObservationFacts")
        if self.reason is not None and not isinstance(self.reason, ProviderReason):
            raise TypeError("reason must be a ProviderReason or None")
        if self.cache_identity is not None and not isinstance(self.cache_identity, ProviderCacheIdentity):
            raise TypeError("cache_identity must be a ProviderCacheIdentity or None")
        if self.cache_identity is not None and not self.facts.is_cached:
            raise ValueError("cache identity requires cached facts")

        available_states = {ProviderDataState.OBSERVED, ProviderDataState.EMPTY}
        if self.state in available_states and self.facts.raw_availability is not RawAvailability.AVAILABLE:
            raise ValueError(f"{self.state.value} result requires available facts")
        if self.state is ProviderDataState.MISSING and self.facts.raw_availability is not RawAvailability.MISSING:
            raise ValueError("missing result requires missing facts")
        unavailable_states = {ProviderDataState.UNAVAILABLE, ProviderDataState.ERROR}
        if self.state in unavailable_states and self.facts.raw_availability is not RawAvailability.UNAVAILABLE:
            raise ValueError(f"{self.state.value} result requires unavailable facts")

        if self.state is ProviderDataState.OBSERVED:
            if self.data is None:
                raise ValueError("observed result requires data")
        elif self.data is not None:
            raise ValueError(f"{self.state.value} result cannot contain data")

        if self.state is ProviderDataState.ERROR:
            if self.reason is None:
                raise ValueError("error result requires a classified reason")
            object.__setattr__(
                self,
                "error_message",
                sanitize_message(self.error_message) if self.error_message else None,
            )
        elif self.error_message is not None:
            raise ValueError("only error results may contain an error message")

    @classmethod
    def observed(
        cls,
        capability: ProviderCapability,
        data: _DataT,
        facts: SourceObservationFacts,
        *,
        cache_identity: ProviderCacheIdentity | None = None,
    ) -> "ProviderDataResult[_DataT]":
        return cls(capability, ProviderDataState.OBSERVED, data, facts, cache_identity=cache_identity)

    @classmethod
    def authoritative_empty(
        cls,
        capability: ProviderCapability,
        facts: SourceObservationFacts,
        *,
        cache_identity: ProviderCacheIdentity | None = None,
    ) -> "ProviderDataResult[_DataT]":
        return cls(capability, ProviderDataState.EMPTY, None, facts, cache_identity=cache_identity)

    @classmethod
    def missing(
        cls,
        capability: ProviderCapability,
        facts: SourceObservationFacts,
        *,
        reason: ProviderReason | None = None,
        cache_identity: ProviderCacheIdentity | None = None,
    ) -> "ProviderDataResult[_DataT]":
        return cls(
            capability,
            ProviderDataState.MISSING,
            None,
            facts,
            reason=reason,
            cache_identity=cache_identity,
        )

    @classmethod
    def unavailable(
        cls,
        capability: ProviderCapability,
        facts: SourceObservationFacts,
        *,
        reason: ProviderReason | None = None,
        cache_identity: ProviderCacheIdentity | None = None,
    ) -> "ProviderDataResult[_DataT]":
        return cls(
            capability,
            ProviderDataState.UNAVAILABLE,
            None,
            facts,
            reason=reason,
            cache_identity=cache_identity,
        )

    @classmethod
    def error(
        cls,
        capability: ProviderCapability,
        facts: SourceObservationFacts,
        *,
        reason: ProviderReason,
        error_message: str | None = None,
        cache_identity: ProviderCacheIdentity | None = None,
    ) -> "ProviderDataResult[_DataT]":
        return cls(
            capability,
            ProviderDataState.ERROR,
            None,
            facts,
            reason=reason,
            error_message=error_message,
            cache_identity=cache_identity,
        )

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
        *,
        data_loader: Callable[[Mapping[str, Any]], _DataT],
    ) -> "ProviderDataResult[_DataT]":
        payload = _strict_mapping(
            value,
            expected={
                "contractVersion",
                "capability",
                "state",
                "data",
                "sourceObservation",
                "reason",
                "errorMessage",
                "cacheIdentity",
            },
            context="provider data result",
        )
        if payload["contractVersion"] != PROVIDER_DATA_RESULT_VERSION:
            raise ValueError("unsupported provider data result contractVersion")
        data_payload = payload["data"]
        data = None
        if data_payload is not None:
            if not isinstance(data_payload, Mapping):
                raise TypeError("provider data must be a mapping or null")
            data = data_loader(data_payload)
        facts_payload = payload["sourceObservation"]
        if not isinstance(facts_payload, Mapping):
            raise TypeError("sourceObservation must be a mapping")
        cache_payload = payload["cacheIdentity"]
        if cache_payload is not None and not isinstance(cache_payload, Mapping):
            raise TypeError("cacheIdentity must be a mapping or null")
        reason_value = payload["reason"]
        return cls(
            capability=_strict_enum(ProviderCapability, payload["capability"], field="capability"),
            state=_strict_enum(ProviderDataState, payload["state"], field="state"),
            data=data,
            facts=SourceObservationFacts.from_dict(facts_payload),
            reason=(
                None
                if reason_value is None
                else _strict_enum(ProviderReason, reason_value, field="reason")
            ),
            error_message=_strict_optional_string(payload["errorMessage"], field="errorMessage"),
            cache_identity=(
                None if cache_payload is None else ProviderCacheIdentity.from_dict(cache_payload)
            ),
        )

    def to_dict(self, *, data_serializer: Callable[[_DataT], Mapping[str, Any]]) -> dict[str, Any]:
        return {
            "contractVersion": PROVIDER_DATA_RESULT_VERSION,
            "capability": self.capability.value,
            "state": self.state.value,
            "data": None if self.data is None else dict(data_serializer(self.data)),
            "sourceObservation": self.facts.to_dict(),
            "reason": None if self.reason is None else self.reason.value,
            "errorMessage": self.error_message,
            "cacheIdentity": None if self.cache_identity is None else self.cache_identity.to_dict(),
        }


def _strict_mapping(
    value: Mapping[str, Any],
    *,
    expected: set[str],
    context: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{context} must be a mapping")
    payload = dict(value)
    actual = set(payload)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        details = []
        if missing:
            details.append(f"missing {missing}")
        if unexpected:
            details.append(f"unexpected {context} fields {unexpected}")
        raise ValueError("; ".join(details))
    return payload


def _strict_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    return value


def _strict_optional_string(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    return _strict_string(value, field=field)


def _strict_enum(enum_type: type[Enum], value: Any, *, field: str) -> Any:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise ValueError(f"invalid {field}: {value}") from exc


def _value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


@dataclass
class ProviderResult:
    provider: str
    capability: ProviderCapability | str
    status: ProviderStatus
    ok: bool
    reason: ProviderReason | str | None = None
    data: Any | None = None
    errorMessage: str | None = None
    httpStatus: int | None = None
    durationMs: int | None = None
    sourceType: ProviderSourceType | str | None = None
    freshness: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    startedAt: datetime | None = None
    finishedAt: datetime | None = None

    def __post_init__(self) -> None:
        self.status = ProviderStatus(self.status)
        self.ok = self.status == ProviderStatus.SUCCESS
        self.errorMessage = sanitize_message(self.errorMessage) if self.errorMessage else None
        self.metadata = sanitize_metadata(self.metadata or {})

    @classmethod
    def success(
        cls,
        provider: str,
        capability: ProviderCapability | str,
        data: Any | None = None,
        *,
        sourceType: ProviderSourceType | str | None = None,
        freshness: str | None = None,
        metadata: Optional[dict[str, Any]] = None,
        httpStatus: int | None = None,
        durationMs: int | None = None,
        startedAt: datetime | None = None,
        finishedAt: datetime | None = None,
    ) -> "ProviderResult":
        return cls(
            provider=provider,
            capability=capability,
            status=ProviderStatus.SUCCESS,
            ok=True,
            data=data,
            httpStatus=httpStatus,
            durationMs=durationMs,
            sourceType=sourceType,
            freshness=freshness,
            metadata=metadata or {},
            startedAt=startedAt,
            finishedAt=finishedAt,
        )

    @classmethod
    def failed(
        cls,
        provider: str,
        capability: ProviderCapability | str,
        reason: ProviderReason | str | None = None,
        *,
        errorMessage: str | None = None,
        data: Any | None = None,
        httpStatus: int | None = None,
        durationMs: int | None = None,
        sourceType: ProviderSourceType | str | None = None,
        freshness: str | None = None,
        metadata: Optional[dict[str, Any]] = None,
        startedAt: datetime | None = None,
        finishedAt: datetime | None = None,
    ) -> "ProviderResult":
        return cls(
            provider=provider,
            capability=capability,
            status=ProviderStatus.FAILED,
            ok=False,
            reason=reason or ProviderReason.UNKNOWN_ERROR,
            data=data,
            errorMessage=errorMessage,
            httpStatus=httpStatus,
            durationMs=durationMs,
            sourceType=sourceType,
            freshness=freshness,
            metadata=metadata or {},
            startedAt=startedAt,
            finishedAt=finishedAt,
        )

    @classmethod
    def skipped(
        cls,
        provider: str,
        capability: ProviderCapability | str,
        reason: ProviderReason | str,
        *,
        errorMessage: str | None = None,
        data: Any | None = None,
        durationMs: int | None = None,
        sourceType: ProviderSourceType | str | None = None,
        freshness: str | None = None,
        metadata: Optional[dict[str, Any]] = None,
        startedAt: datetime | None = None,
        finishedAt: datetime | None = None,
    ) -> "ProviderResult":
        return cls(
            provider=provider,
            capability=capability,
            status=ProviderStatus.SKIPPED,
            ok=False,
            reason=reason,
            data=data,
            errorMessage=errorMessage,
            durationMs=durationMs,
            sourceType=sourceType,
            freshness=freshness,
            metadata=metadata or {},
            startedAt=startedAt,
            finishedAt=finishedAt,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "capability": _value(self.capability),
            "status": self.status.value,
            "ok": self.ok,
            "reason": _value(self.reason),
            "data": _json_safe(self.data),
            "errorMessage": self.errorMessage,
            "httpStatus": self.httpStatus,
            "durationMs": self.durationMs,
            "sourceType": _value(self.sourceType),
            "freshness": self.freshness,
            "metadata": _json_safe(self.metadata),
            "startedAt": _json_safe(self.startedAt),
            "finishedAt": _json_safe(self.finishedAt),
        }
