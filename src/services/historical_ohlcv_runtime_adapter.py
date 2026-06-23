from __future__ import annotations

import inspect
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from src.services.historical_ohlcv_readiness import (
    HISTORICAL_OHLCV_DEFAULT_TIMEFRAME,
    HistoricalOhlcvProviderResult,
    HistoricalOhlcvReadinessRequest,
)


class HistoricalOhlcvRuntimeAdapter:
    """Consumer-safe adapter for explicitly supplied OHLCV history runtimes."""

    def __init__(self, history_runtime: Any | None = None) -> None:
        self.history_runtime = history_runtime

    def fetch_ohlcv_history(
        self,
        request: HistoricalOhlcvReadinessRequest,
    ) -> HistoricalOhlcvProviderResult:
        if self.history_runtime is None:
            return HistoricalOhlcvProviderResult.unavailable("provider_missing")

        try:
            payload = self._fetch_from_runtime(request)
        except Exception:
            return HistoricalOhlcvProviderResult.unavailable("provider_unavailable")

        return _result_from_payload(payload)

    def _fetch_from_runtime(self, request: HistoricalOhlcvReadinessRequest) -> Any:
        runtime = self.history_runtime
        get_history_data = getattr(runtime, "get_history_data", None)
        if callable(get_history_data):
            return _call_with_supported_kwargs(
                get_history_data,
                {
                    "stock_code": request.symbol,
                    "period": _history_period(request.timeframe),
                    "days": _requested_days(request),
                    "start_date": _date_arg(request.start),
                    "end_date": _date_arg(request.end),
                },
            )

        get_daily_data = getattr(runtime, "get_daily_data", None)
        if callable(get_daily_data):
            return _call_with_supported_kwargs(
                get_daily_data,
                {
                    "stock_code": request.symbol,
                    "days": _requested_days(request),
                    "start_date": _date_arg(request.start),
                    "end_date": _date_arg(request.end),
                },
            )

        return HistoricalOhlcvProviderResult.unavailable("provider_missing")


def _result_from_payload(payload: Any) -> HistoricalOhlcvProviderResult:
    if isinstance(payload, HistoricalOhlcvProviderResult):
        return payload

    source = "unknown"
    diagnostics: Mapping[str, Any] = {}
    source_confidence: Mapping[str, Any] = {}
    rows: Any = payload
    if isinstance(payload, tuple) and payload:
        rows = payload[0]
        source = str(payload[1] or "unknown") if len(payload) > 1 else "unknown"
    if isinstance(payload, Mapping):
        source = str(payload.get("source") or "unknown")
        diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), Mapping) else {}
        source_confidence = (
            payload.get("sourceConfidence")
            if isinstance(payload.get("sourceConfidence"), Mapping)
            else {}
        )
        rows = payload.get("data")

    bars = _rows_as_bar_dicts(rows)
    if not bars:
        return HistoricalOhlcvProviderResult.unavailable(_safe_unavailable_reason(source, diagnostics))

    return HistoricalOhlcvProviderResult.available(
        bars,
        adjustments_available=_adjustments_available(source_confidence),
        freshness_state=_freshness_state(source_confidence),
    )


def _rows_as_bar_dicts(rows: Any) -> list[Mapping[str, Any]]:
    if rows is None:
        return []
    to_dict = getattr(rows, "to_dict", None)
    if callable(to_dict):
        try:
            rows = to_dict("records")
        except Exception:
            return []
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        return []
    result: list[Mapping[str, Any]] = []
    for row in rows:
        if isinstance(row, Mapping):
            result.append(row)
    return result


def _call_with_supported_kwargs(func: Any, kwargs: Mapping[str, Any]) -> Any:
    clean_kwargs = {key: value for key, value in kwargs.items() if value is not None}
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return func(**clean_kwargs)
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
        return func(**clean_kwargs)
    supported = {
        key: value
        for key, value in clean_kwargs.items()
        if key in signature.parameters
    }
    return func(**supported)


def _requested_days(request: HistoricalOhlcvReadinessRequest) -> int:
    for value in (request.lookback_bars, request.required_bars):
        try:
            parsed = int(value or 0)
        except (TypeError, ValueError):
            parsed = 0
        if parsed > 0:
            return parsed
    return 90


def _history_period(timeframe: str) -> str:
    normalized = str(timeframe or HISTORICAL_OHLCV_DEFAULT_TIMEFRAME).strip().lower()
    if normalized in {"1wk", "1w", "weekly"}:
        return "weekly"
    if normalized in {"1mo", "1m", "monthly"}:
        return "monthly"
    return "daily"


def _date_arg(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _safe_unavailable_reason(source: str, diagnostics: Mapping[str, Any]) -> str:
    reason = str(diagnostics.get("reason") or "").strip().lower()
    if reason == "entitlement_required":
        return "entitlement_required"
    if reason == "provider_missing":
        return "provider_missing"
    if str(source or "").strip().lower() in {"", "unavailable", "none"}:
        return "provider_missing"
    return "provider_unavailable"


def _freshness_state(source_confidence: Mapping[str, Any]) -> str | None:
    freshness = str(source_confidence.get("freshness") or "").strip().lower()
    if freshness == "stale" or source_confidence.get("isStale") is True:
        return "stale"
    return None


def _adjustments_available(source_confidence: Mapping[str, Any]) -> bool | None:
    for key in ("adjustmentsAvailable", "adjusted", "isAdjusted"):
        if key in source_confidence:
            return bool(source_confidence.get(key))
    return None
