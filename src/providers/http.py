# -*- coding: utf-8 -*-
"""Shared HTTP helpers for bounded provider validation probes."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import requests

from src.providers.errors import reason_from_http_status
from src.providers.types import ProviderCapability, ProviderReason, ProviderResult
from src.utils.security import sanitize_message, sanitize_metadata, sanitize_url

_DEFAULT_USER_AGENT = "WolfyStock-Provider-Validation/1.0"
_DEFAULT_ACCEPT = "application/json, text/plain;q=0.9, */*;q=0.8"
_SENSITIVE_PARAM_KEYS = {"apikey", "api_key", "token", "access_token", "secret", "api_secret", "password", "credential"}


def map_http_status_to_provider_reason(status_code: int | None) -> ProviderReason:
    status_reason = reason_from_http_status(status_code)
    if status_reason is not None:
        return status_reason
    if status_code and status_code >= 500:
        return ProviderReason.PROVIDER_UNHEALTHY
    return ProviderReason.UNKNOWN_ERROR


def sanitize_provider_request_metadata(
    *,
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    method: str = "GET",
) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "method": str(method or "GET").upper(),
            "url": _url_with_params(url, params),
            "params": params or {},
            "headers": headers or {},
        }
    )


def provider_get_json(
    *,
    provider: str,
    capability: str | ProviderCapability,
    url: str,
    timeout_seconds: float = 5.0,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
) -> ProviderResult:
    return provider_request_json(
        provider=provider,
        capability=capability,
        url=url,
        timeout_seconds=timeout_seconds,
        headers=headers,
        params=params,
        method="GET",
    )


def provider_request_json(
    *,
    provider: str,
    capability: str | ProviderCapability,
    url: str,
    timeout_seconds: float = 5.0,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    method: str = "GET",
    json_payload: dict[str, Any] | None = None,
) -> ProviderResult:
    started_at = datetime.now(timezone.utc)
    started_perf = time.perf_counter()
    method_name = str(method or "GET").upper()
    request_headers = {
        "User-Agent": _DEFAULT_USER_AGENT,
        "Accept": _DEFAULT_ACCEPT,
        **(headers or {}),
    }
    metadata = sanitize_provider_request_metadata(
        url=url,
        params=params,
        headers=request_headers,
        method=method_name,
    )
    if json_payload is not None:
        metadata["json"] = sanitize_metadata(json_payload)

    response = None
    try:
        response = requests.request(
            method_name,
            url,
            params=params,
            json=json_payload,
            headers=request_headers,
            timeout=timeout_seconds,
        )
        duration_ms = int((time.perf_counter() - started_perf) * 1000)
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code != 200:
            reason = map_http_status_to_provider_reason(status_code)
            return ProviderResult.failed(
                provider=provider,
                capability=capability,
                reason=reason,
                errorMessage=_http_status_message(status_code),
                httpStatus=status_code,
                durationMs=duration_ms,
                metadata=metadata,
                startedAt=started_at,
                finishedAt=datetime.now(timezone.utc),
            )

        try:
            data = response.json()
        except ValueError:
            return ProviderResult.failed(
                provider=provider,
                capability=capability,
                reason=ProviderReason.INVALID_PAYLOAD,
                errorMessage="Provider returned a non-JSON response.",
                httpStatus=status_code,
                durationMs=duration_ms,
                metadata=metadata,
                startedAt=started_at,
                finishedAt=datetime.now(timezone.utc),
            )

        if data in (None, "", [], {}):
            return ProviderResult.failed(
                provider=provider,
                capability=capability,
                reason=ProviderReason.NO_DATA,
                errorMessage="Provider returned an empty payload.",
                httpStatus=status_code,
                durationMs=duration_ms,
                metadata=metadata,
                startedAt=started_at,
                finishedAt=datetime.now(timezone.utc),
            )

        return ProviderResult.success(
            provider=provider,
            capability=capability,
            data=_sanitize_payload(data, params=params, headers=request_headers, json_payload=json_payload),
            httpStatus=status_code,
            durationMs=duration_ms,
            metadata=metadata,
            startedAt=started_at,
            finishedAt=datetime.now(timezone.utc),
        )
    except requests.exceptions.Timeout:
        return ProviderResult.failed(
            provider=provider,
            capability=capability,
            reason=ProviderReason.TIMEOUT,
            errorMessage=f"Provider request timed out after {int(timeout_seconds)} seconds.",
            durationMs=int((time.perf_counter() - started_perf) * 1000),
            metadata=metadata,
            startedAt=started_at,
            finishedAt=datetime.now(timezone.utc),
        )
    except requests.exceptions.RequestException as exc:
        return ProviderResult.failed(
            provider=provider,
            capability=capability,
            reason=map_http_status_to_provider_reason(_http_status_from_exception(exc)),
            errorMessage=sanitize_message(str(exc) or exc.__class__.__name__),
            httpStatus=_http_status_from_exception(exc),
            durationMs=int((time.perf_counter() - started_perf) * 1000),
            metadata=metadata,
            startedAt=started_at,
            finishedAt=datetime.now(timezone.utc),
        )
    finally:
        if response is not None and callable(getattr(response, "close", None)):
            response.close()


def build_provider_check(
    *,
    result: ProviderResult,
    name: str,
    endpoint: str,
    success_message: str,
    failure_message: str | None = None,
) -> dict[str, Any]:
    ok = bool(result.ok)
    reason = result.reason.value if hasattr(result.reason, "value") else result.reason
    return {
        "name": name,
        "endpoint": endpoint,
        "ok": ok,
        "http_status": result.httpStatus,
        "duration_ms": result.durationMs,
        "error_type": None if ok else _reason_to_error_type(result.reason, result.httpStatus),
        "reason": None if ok else reason,
        "message": success_message if ok else (failure_message or result.errorMessage or "Provider validation failed."),
    }


def _url_with_params(url: str, params: dict[str, Any] | None) -> str:
    base = sanitize_url(str(url or ""))
    if not params:
        return base
    safe_params: dict[str, Any] = {}
    for key, value in params.items():
        key_text = str(key)
        safe_params[key_text] = "***" if key_text.lower() in _SENSITIVE_PARAM_KEYS else value
    separator = "&" if "?" in base else "?"
    return sanitize_url(f"{base}{separator}{urlencode(safe_params, doseq=True)}")


def _http_status_from_exception(exc: BaseException) -> int | None:
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None


def _http_status_message(status_code: int) -> str:
    if status_code == 401:
        return "Provider returned HTTP 401 unauthorized."
    if status_code == 403:
        return "Provider returned HTTP 403 forbidden."
    if status_code == 429:
        return "Provider returned HTTP 429 rate limited."
    return f"Provider returned HTTP {status_code}."


def _reason_to_error_type(reason: ProviderReason | str | None, http_status: int | None) -> str:
    if reason == ProviderReason.UNAUTHORIZED:
        return "Unauthorized"
    if reason == ProviderReason.FORBIDDEN:
        return "Forbidden"
    if reason == ProviderReason.RATE_LIMITED:
        return "RateLimited"
    if reason == ProviderReason.TIMEOUT:
        return "Timeout"
    if reason == ProviderReason.NO_DATA:
        return "NoData"
    if reason == ProviderReason.INVALID_PAYLOAD:
        return "InvalidPayload"
    if reason == ProviderReason.PROVIDER_UNHEALTHY or (http_status and http_status >= 500):
        return "ProviderServerError"
    if http_status:
        return "HttpError"
    return "UnknownError"


def _sanitize_payload(
    data: Any,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    json_payload: dict[str, Any] | None = None,
) -> Any:
    sanitized = sanitize_metadata(data)
    for secret in _request_secret_values(params=params, headers=headers, json_payload=json_payload):
        sanitized = _replace_secret(sanitized, secret)
    return sanitized


def _request_secret_values(
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    json_payload: dict[str, Any] | None = None,
) -> list[str]:
    secrets: list[str] = []
    for payload in (params or {}, headers or {}, json_payload or {}):
        if not isinstance(payload, dict):
            continue
        for key, value in payload.items():
            if str(key).lower() in _SENSITIVE_PARAM_KEYS or str(key).lower() == "authorization":
                raw_value = str(value or "").strip()
                if raw_value:
                    secrets.append(raw_value)
                    if raw_value.lower().startswith("bearer "):
                        secrets.append(raw_value[7:].strip())
    return [secret for secret in secrets if secret]


def _replace_secret(value: Any, secret: str) -> Any:
    if isinstance(value, dict):
        return {key: _replace_secret(item, secret) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_secret(item, secret) for item in value]
    if isinstance(value, tuple):
        return tuple(_replace_secret(item, secret) for item in value)
    if isinstance(value, str) and len(secret) >= 4:
        return value.replace(secret, "***")
    return value
