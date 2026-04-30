# -*- coding: utf-8 -*-
"""Provider result primitives shared by future provider integrations."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from src.utils.security import sanitize_message, sanitize_metadata


class ProviderStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


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
