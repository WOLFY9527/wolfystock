# -*- coding: utf-8 -*-
"""Lightweight provider validation wrappers for Settings remote probes."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

import requests

from src.providers.errors import provider_failed_result_from_exception, reason_from_http_status
from src.providers.types import (
    ProviderCapability,
    ProviderReason,
    ProviderResult,
    ProviderSourceType,
)
from src.utils.security import sanitize_message

_REMOTE_VALIDATION_TIMEOUT_SECONDS = 5.0
_REMOTE_VALIDATION_USER_AGENT = "WolfyStock-Provider-Validation/1.0"
_VALIDATION_CAPABILITY = ProviderCapability.DATA_SOURCE_VALIDATION


def normalize_provider_name(provider: str) -> str:
    normalized = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(provider or "").strip().lower()).strip("_")
    aliases = {
        "alphavantage": "alpha_vantage",
        "alpha": "alpha_vantage",
        "twelvedata": "twelve_data",
        "twelve": "twelve_data",
        "yfinance": "yahoo",
    }
    return aliases.get(normalized, normalized or "unknown")


def validate_provider_connection(
    provider: str,
    symbol: str = "MSFT",
    *,
    credential: str = "",
    timeout_seconds: float = _REMOTE_VALIDATION_TIMEOUT_SECONDS,
) -> ProviderResult:
    normalized_provider = normalize_provider_name(provider)
    normalized_symbol = (symbol or "MSFT").strip().upper() or "MSFT"
    timeout = min(_REMOTE_VALIDATION_TIMEOUT_SECONDS, max(1.0, float(timeout_seconds or _REMOTE_VALIDATION_TIMEOUT_SECONDS)))

    if normalized_provider == "fmp":
        return validate_fmp(symbol=normalized_symbol, credential=credential, timeout_seconds=timeout)
    if normalized_provider == "finnhub":
        return validate_finnhub(symbol=normalized_symbol, credential=credential, timeout_seconds=timeout)
    if normalized_provider == "alpha_vantage":
        return validate_alpha_vantage(symbol=normalized_symbol, credential=credential, timeout_seconds=timeout)
    if normalized_provider == "twelve_data":
        return validate_twelve_data(symbol=normalized_symbol, credential=credential, timeout_seconds=timeout)
    if normalized_provider == "tushare":
        return validate_tushare(symbol=normalized_symbol, credential=credential, timeout_seconds=timeout)
    if normalized_provider == "yahoo":
        return validate_yahoo(symbol=normalized_symbol, timeout_seconds=timeout)

    return ProviderResult.skipped(
        provider=normalized_provider,
        capability=_VALIDATION_CAPABILITY,
        reason=ProviderReason.UNSUPPORTED_CAPABILITY,
        errorMessage="Unsupported provider validation capability, skipped.",
        metadata={"checks": [], "status": "unsupported"},
        finishedAt=datetime.now(timezone.utc),
    )


def validate_fmp(symbol: str = "MSFT", *, credential: str = "", timeout_seconds: float = _REMOTE_VALIDATION_TIMEOUT_SECONDS) -> ProviderResult:
    return _validate_with_checks(
        provider="fmp",
        symbol=symbol,
        credential=credential,
        timeout_seconds=timeout_seconds,
        source_type=ProviderSourceType.OFFICIAL_API,
        checks=[
            lambda timeout: _run_remote_json_check(
                name="quote",
                endpoint=f"/api/v3/quote/{symbol}",
                url=f"https://financialmodelingprep.com/api/v3/quote/{symbol}",
                params={"apikey": credential},
                timeout=timeout,
                validator=lambda data: (
                    isinstance(data, list)
                    and bool(data)
                    and isinstance(data[0], dict)
                    and str(data[0].get("symbol") or "").upper() == symbol
                    and data[0].get("price") is not None
                ),
                success_message="quote endpoint 可用。",
                failure_message="quote endpoint 返回的数据结构不可用。",
            ),
            lambda timeout: _run_remote_json_check(
                name="historical",
                endpoint=f"/api/v3/historical-price-full/{symbol}",
                url=f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol}",
                params={"timeseries": "5", "apikey": credential},
                timeout=timeout,
                validator=lambda data: isinstance(data, dict) and isinstance(data.get("historical"), list),
                success_message="historical endpoint 可用。",
                failure_message="historical endpoint 不可用。",
            ),
        ],
    )


def validate_finnhub(symbol: str = "MSFT", *, credential: str = "", timeout_seconds: float = _REMOTE_VALIDATION_TIMEOUT_SECONDS) -> ProviderResult:
    return _validate_with_checks(
        provider="finnhub",
        symbol=symbol,
        credential=credential,
        timeout_seconds=timeout_seconds,
        source_type=ProviderSourceType.OFFICIAL_API,
        checks=[
            lambda timeout: _run_remote_json_check(
                name="quote",
                endpoint="/api/v1/quote",
                url="https://finnhub.io/api/v1/quote",
                params={"symbol": symbol, "token": credential},
                timeout=timeout,
                validator=lambda data: isinstance(data, dict) and data.get("c") not in (None, 0, 0.0),
                success_message="quote endpoint 可用。",
                failure_message="quote endpoint 返回的数据结构不可用。",
            )
        ],
    )


def validate_alpha_vantage(symbol: str = "MSFT", *, credential: str = "", timeout_seconds: float = _REMOTE_VALIDATION_TIMEOUT_SECONDS) -> ProviderResult:
    return _validate_with_checks(
        provider="alpha_vantage",
        symbol=symbol,
        credential=credential,
        timeout_seconds=timeout_seconds,
        source_type=ProviderSourceType.OFFICIAL_API,
        checks=[
            lambda timeout: _run_remote_json_check(
                name="global_quote",
                endpoint="/query?function=GLOBAL_QUOTE",
                url="https://www.alphavantage.co/query",
                params={"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": credential},
                timeout=timeout,
                validator=lambda data: (
                    isinstance(data, dict)
                    and not any(field in data for field in ("Note", "Information", "Error Message"))
                    and isinstance(data.get("Global Quote"), dict)
                    and bool(data.get("Global Quote", {}).get("05. price"))
                ),
                success_message="GLOBAL_QUOTE endpoint 可用。",
                failure_message="GLOBAL_QUOTE endpoint 返回限流、错误或不可用数据。",
            )
        ],
    )


def validate_twelve_data(symbol: str = "MSFT", *, credential: str = "", timeout_seconds: float = _REMOTE_VALIDATION_TIMEOUT_SECONDS) -> ProviderResult:
    return _validate_with_checks(
        provider="twelve_data",
        symbol=symbol,
        credential=credential,
        timeout_seconds=timeout_seconds,
        source_type=ProviderSourceType.OFFICIAL_API,
        checks=[
            lambda timeout: _run_remote_json_check(
                name="quote",
                endpoint="/quote",
                url="https://api.twelvedata.com/quote",
                params={"symbol": symbol, "apikey": credential},
                timeout=timeout,
                validator=lambda data: (
                    isinstance(data, dict)
                    and str(data.get("status") or "").lower() != "error"
                    and bool(data.get("price"))
                ),
                success_message="quote endpoint 可用。",
                failure_message="quote endpoint 返回错误或缺少 price。",
            )
        ],
    )


def validate_tushare(symbol: str = "MSFT", *, credential: str = "", timeout_seconds: float = _REMOTE_VALIDATION_TIMEOUT_SECONDS) -> ProviderResult:
    _ = symbol
    return _validate_with_checks(
        provider="tushare",
        symbol="000001.SZ",
        credential=credential,
        timeout_seconds=timeout_seconds,
        source_type=ProviderSourceType.OFFICIAL_API,
        checks=[
            lambda timeout: _run_remote_json_check(
                name="daily",
                endpoint="/",
                url="http://api.tushare.pro",
                method="POST",
                json_payload={
                    "api_name": "daily",
                    "token": credential,
                    "params": {"ts_code": "000001.SZ", "start_date": "20240101", "end_date": "20240105"},
                    "fields": "ts_code,trade_date,close",
                },
                timeout=timeout,
                validator=lambda data: isinstance(data, dict) and data.get("code") == 0 and isinstance(data.get("data"), dict),
                success_message="daily endpoint 可用。",
                failure_message="daily endpoint 返回错误或 token 不可用。",
            )
        ],
    )


def validate_yahoo(symbol: str = "MSFT", *, timeout_seconds: float = _REMOTE_VALIDATION_TIMEOUT_SECONDS) -> ProviderResult:
    started_at = datetime.now(timezone.utc)
    started_perf = time.perf_counter()
    checks = [
        _run_remote_json_check(
            name="chart",
            endpoint=f"/v8/finance/chart/{symbol}",
            url=f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"range": "1d", "interval": "1d"},
            timeout=timeout_seconds,
            validator=lambda data: (
                isinstance(data, dict)
                and isinstance(data.get("chart"), dict)
                and not data.get("chart", {}).get("error")
                and bool(data.get("chart", {}).get("result"))
            ),
            success_message="Yahoo public chart endpoint 可用。",
            failure_message="Yahoo public chart endpoint 不可用。",
        )
    ]
    return _build_result_from_checks(
        provider="yahoo",
        symbol=symbol,
        started_at=started_at,
        started_perf=started_perf,
        checks=checks,
        source_type=ProviderSourceType.UNOFFICIAL_PUBLIC_API,
    )


def _validate_with_checks(
    *,
    provider: str,
    symbol: str,
    credential: str,
    timeout_seconds: float,
    source_type: ProviderSourceType,
    checks: list[Callable[[float], Dict[str, Any]]],
) -> ProviderResult:
    started_at = datetime.now(timezone.utc)
    started_perf = time.perf_counter()
    if not str(credential or "").strip():
        return ProviderResult.skipped(
            provider=provider,
            capability=_VALIDATION_CAPABILITY,
            reason=ProviderReason.MISSING_API_KEY,
            errorMessage="API key is not configured, skipped.",
            durationMs=int((time.perf_counter() - started_perf) * 1000),
            sourceType=source_type,
            metadata={"checks": [], "status": "missing_key"},
            startedAt=started_at,
            finishedAt=datetime.now(timezone.utc),
        )

    results = [run_check(timeout_seconds) for run_check in checks]
    return _build_result_from_checks(
        provider=provider,
        symbol=symbol,
        started_at=started_at,
        started_perf=started_perf,
        checks=results,
        source_type=source_type,
    )


def _build_result_from_checks(
    *,
    provider: str,
    symbol: str,
    started_at: datetime,
    started_perf: float,
    checks: list[Dict[str, Any]],
    source_type: ProviderSourceType,
) -> ProviderResult:
    ok_count = sum(1 for check in checks if check.get("ok"))
    finished_at = datetime.now(timezone.utc)
    duration_ms = int((time.perf_counter() - started_perf) * 1000)
    metadata = {
        "checks": checks,
        "status": "success" if ok_count == len(checks) and checks else "partial" if ok_count > 0 else "failed",
        "okCount": ok_count,
        "checkCount": len(checks),
    }
    if ok_count == len(checks) and checks:
        return ProviderResult.success(
            provider=provider,
            capability=_VALIDATION_CAPABILITY,
            data={"symbol": symbol},
            durationMs=duration_ms,
            sourceType=source_type,
            metadata=metadata,
            startedAt=started_at,
            finishedAt=finished_at,
        )
    if ok_count > 0:
        return ProviderResult.success(
            provider=provider,
            capability=_VALIDATION_CAPABILITY,
            data={"symbol": symbol},
            durationMs=duration_ms,
            sourceType=source_type,
            metadata=metadata,
            startedAt=started_at,
            finishedAt=finished_at,
        )

    failed_checks = [check for check in checks if not check.get("ok")]
    first_failure = failed_checks[0] if failed_checks else {}
    return ProviderResult.failed(
        provider=provider,
        capability=_VALIDATION_CAPABILITY,
        reason=first_failure.get("reason") or ProviderReason.UNKNOWN_ERROR,
        errorMessage=first_failure.get("message") or "Provider validation failed.",
        httpStatus=first_failure.get("http_status"),
        durationMs=duration_ms,
        sourceType=source_type,
        metadata=metadata,
        startedAt=started_at,
        finishedAt=finished_at,
    )


def _run_remote_json_check(
    *,
    name: str,
    endpoint: str,
    url: str,
    timeout: float,
    validator: Callable[[Any], bool],
    success_message: str,
    failure_message: str,
    params: Optional[Dict[str, Any]] = None,
    method: str = "GET",
    json_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    response = None
    try:
        response = requests.request(
            method,
            url,
            params=params,
            json=json_payload,
            headers={
                "User-Agent": _REMOTE_VALIDATION_USER_AGENT,
                "Accept": "application/json, text/plain;q=0.9, */*;q=0.8",
            },
            timeout=timeout,
        )
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code != 200:
            reason = reason_from_http_status(status_code) or ProviderReason.UNKNOWN_ERROR
            return {
                "name": name,
                "endpoint": endpoint,
                "ok": False,
                "http_status": status_code,
                "duration_ms": duration_ms,
                "error_type": _reason_to_error_type(reason, status_code),
                "reason": reason.value,
                "message": _http_status_message(status_code, name),
            }

        try:
            data = response.json()
        except ValueError:
            return {
                "name": name,
                "endpoint": endpoint,
                "ok": False,
                "http_status": status_code,
                "duration_ms": duration_ms,
                "error_type": "InvalidPayload",
                "reason": ProviderReason.INVALID_PAYLOAD.value,
                "message": f"{name} endpoint 返回非 JSON 响应。",
            }

        if validator(data):
            return {
                "name": name,
                "endpoint": endpoint,
                "ok": True,
                "http_status": status_code,
                "duration_ms": duration_ms,
                "error_type": None,
                "reason": None,
                "message": success_message,
            }

        reason, message = _reason_from_payload(
            data,
            secrets=_request_secret_values(params=params, json_payload=json_payload),
        )
        return {
            "name": name,
            "endpoint": endpoint,
            "ok": False,
            "http_status": status_code,
            "duration_ms": duration_ms,
            "error_type": _reason_to_error_type(reason, status_code),
            "reason": reason.value,
            "message": message or failure_message,
        }
    except requests.exceptions.Timeout as exc:
        result = provider_failed_result_from_exception(
            exc,
            provider="validation",
            capability=_VALIDATION_CAPABILITY,
            durationMs=int((time.perf_counter() - started_at) * 1000),
        )
        return {
            "name": name,
            "endpoint": endpoint,
            "ok": False,
            "http_status": result.httpStatus,
            "duration_ms": result.durationMs,
            "error_type": "Timeout",
            "reason": ProviderReason.TIMEOUT.value,
            "message": f"{name} endpoint 在 {int(timeout)} 秒内未响应。",
        }
    except requests.exceptions.RequestException as exc:
        result = provider_failed_result_from_exception(
            exc,
            provider="validation",
            capability=_VALIDATION_CAPABILITY,
            durationMs=int((time.perf_counter() - started_at) * 1000),
        )
        return {
            "name": name,
            "endpoint": endpoint,
            "ok": False,
            "http_status": result.httpStatus,
            "duration_ms": result.durationMs,
            "error_type": "NetworkError",
            "reason": result.reason.value if hasattr(result.reason, "value") else str(result.reason),
            "message": "endpoint 请求失败，请检查网络、代理或 provider 服务状态。",
        }
    finally:
        if response is not None and callable(getattr(response, "close", None)):
            response.close()


def _reason_from_payload(data: Any, *, secrets: list[str] | None = None) -> tuple[ProviderReason, str]:
    if isinstance(data, dict):
        payload_error = _extract_payload_error_message(data)
        if payload_error:
            reason = _classify_payload_reason(payload_error)
            return reason, _sanitize_secret_text(payload_error[:240], secrets or [])
        if not data:
            return ProviderReason.NO_DATA, "provider 返回空响应。"
        return ProviderReason.INVALID_PAYLOAD, "provider 返回的数据结构不可用。"
    if isinstance(data, list) and not data:
        return ProviderReason.NO_DATA, "provider 未返回数据。"
    return ProviderReason.INVALID_PAYLOAD, "provider 返回的数据结构不可用。"


def _extract_payload_error_message(data: Dict[str, Any]) -> str:
    for key in ("Error Message", "Note", "Information", "message", "error", "msg"):
        value = data.get(key)
        if value:
            return str(value)
    if str(data.get("status") or "").lower() == "error":
        return str(data.get("message") or data.get("code") or "Provider returned error")
    if data.get("code") not in (None, 0, "0"):
        return str(data.get("msg") or data.get("message") or data.get("code"))
    return ""


def _request_secret_values(
    *,
    params: Optional[Dict[str, Any]] = None,
    json_payload: Optional[Dict[str, Any]] = None,
) -> list[str]:
    secrets: list[str] = []
    for payload in (params or {}, json_payload or {}):
        if not isinstance(payload, dict):
            continue
        for key, value in payload.items():
            if str(key).lower() in {"apikey", "api_key", "token", "access_token", "secret", "api_secret"}:
                raw_value = str(value or "").strip()
                if raw_value:
                    secrets.append(raw_value)
    return secrets


def _sanitize_secret_text(message: str, secrets: list[str]) -> str:
    sanitized = sanitize_message(str(message or ""))
    for secret in secrets:
        if len(secret) >= 4:
            sanitized = sanitized.replace(secret, "***")
    return sanitized


def _classify_payload_reason(message: str) -> ProviderReason:
    text = str(message or "").lower()
    if any(token in text for token in ("rate limit", "too many", "frequency", "quota", "call frequency")):
        return ProviderReason.RATE_LIMITED
    if any(token in text for token in ("403", "forbidden", "permission", "plan", "premium", "subscription", "insufficient")):
        return ProviderReason.FORBIDDEN
    if any(token in text for token in ("401", "unauthorized", "invalid api key", "invalid token", "api key", "token invalid", "authentication")):
        return ProviderReason.UNAUTHORIZED
    if any(token in text for token in ("no data", "empty", "not found")):
        return ProviderReason.NO_DATA
    return ProviderReason.INVALID_PAYLOAD


def _reason_to_error_type(reason: ProviderReason, http_status: int | None) -> str:
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
    if http_status and http_status >= 500:
        return "ProviderServerError"
    if http_status:
        return "HttpError"
    return "UnknownError"


def _http_status_message(status_code: int, endpoint_name: str) -> str:
    if status_code == 401:
        return f"{endpoint_name} endpoint 返回 401，可能是 API key 无效或缺失。"
    if status_code == 403:
        return f"{endpoint_name} endpoint 返回 403，可能是 API key 无效、额度不足或当前套餐不支持该 endpoint。"
    if status_code == 429:
        return f"{endpoint_name} endpoint 返回 429，可能已触发 provider 频率限制或额度耗尽。"
    return f"{endpoint_name} endpoint 返回 HTTP {status_code}，远程校验失败。"
