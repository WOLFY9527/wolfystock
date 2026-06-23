# -*- coding: utf-8 -*-
"""Advisory-only liquidity monitor endpoint."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter

from api.v1.schemas.liquidity_monitor import LiquidityMonitorResponse
from src.services.liquidity_monitor_service import LiquidityMonitorService


router = APIRouter()

_LIQUIDITY_FORBIDDEN_CONSUMER_KEYS = frozenset(
    {
        "apikeypresent",
        "cachekey",
        "credential",
        "credentials",
        "credentialfieldsmissing",
        "credentialsource",
        "credentialspresent",
        "endpointhost",
        "exceptionchain",
        "exceptionclass",
        "rawpayload",
        "rawproviderpayload",
        "rawproviderpayloadstored",
        "requestid",
        "requiredproviderclass",
        "traceid",
    }
)
_LIQUIDITY_UNSAFE_CONSUMER_TEXT_RE = re.compile(
    r"\b(?:missing[_-]?api[_-]?key|api[_-]?key|credentials?|token|password|secret|private[_-]?key|traceback|env)\b",
    re.IGNORECASE,
)


def _normalize_key(key: object) -> str:
    return "".join(ch for ch in str(key).lower() if ch.isalnum())


def _consumer_safe_liquidity_payload(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, child in value.items():
            normalized = _normalize_key(key)
            if normalized in _LIQUIDITY_FORBIDDEN_CONSUMER_KEYS:
                continue
            if any(token in normalized for token in ("credential", "apikey", "password", "privatekey")):
                continue
            redacted[str(key)] = _consumer_safe_liquidity_payload(child)
        return redacted
    if isinstance(value, list):
        return [_consumer_safe_liquidity_payload(item) for item in value]
    if isinstance(value, str) and _LIQUIDITY_UNSAFE_CONSUMER_TEXT_RE.search(value):
        return "configuration_required"
    return value


@router.get(
    "/liquidity-monitor",
    response_model=LiquidityMonitorResponse,
    response_model_exclude_none=True,
    summary="Get advisory liquidity monitor",
)
def get_liquidity_monitor() -> LiquidityMonitorResponse:
    return _consumer_safe_liquidity_payload(LiquidityMonitorService().get_liquidity_monitor())
