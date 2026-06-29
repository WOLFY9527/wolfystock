from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol


HISTORICAL_OHLCV_READINESS_CONTRACT_VERSION = "historical_ohlcv_readiness_v1"
BACKTEST_HISTORICAL_OHLCV_READINESS_CONTRACT_VERSION = "backtest_historical_ohlcv_readiness_v1"
HISTORICAL_OHLCV_DEFAULT_TIMEFRAME = "1d"
_PROVIDER_MISSING = "provider_missing"
_PROVIDER_UNAVAILABLE = "provider_unavailable"
_ENTITLEMENT_REQUIRED = "entitlement_required"
_INSUFFICIENT_HISTORY = "insufficient_history"
_STALE_DATA = "stale_data"
_MISSING_ADJUSTMENTS = "missing_adjustments"
_MISSING_BENCHMARK = "missing_benchmark"
_SAFE_RUNTIME_STATUSES = {
    "available",
    "missing",
    "stale",
    "not_configured",
    "insufficient_coverage",
    "unavailable",
}
_BLOCKING_REQUIREMENTS = {
    _PROVIDER_MISSING,
    _PROVIDER_UNAVAILABLE,
    _ENTITLEMENT_REQUIRED,
    _INSUFFICIENT_HISTORY,
}


@dataclass(frozen=True)
class HistoricalOhlcvReadinessRequest:
    symbol: str
    market: str = "unknown"
    timeframe: str = HISTORICAL_OHLCV_DEFAULT_TIMEFRAME
    start: date | None = None
    end: date | None = None
    lookback_bars: int | None = None
    required_bars: int = 0
    require_adjusted: bool = False
    benchmark_symbol: str | None = None
    benchmark_required: bool = False

    def benchmark_request(self) -> "HistoricalOhlcvReadinessRequest":
        return HistoricalOhlcvReadinessRequest(
            symbol=str(self.benchmark_symbol or "").strip().upper(),
            market=self.market,
            timeframe=self.timeframe,
            start=self.start,
            end=self.end,
            lookback_bars=self.lookback_bars,
            required_bars=self.required_bars,
            require_adjusted=self.require_adjusted,
        )


@dataclass(frozen=True)
class HistoricalOhlcvBar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    adjusted_close: float | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "date": self.date.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }
        if self.adjusted_close is not None:
            payload["adjustedClose"] = self.adjusted_close
        return payload


@dataclass(frozen=True)
class HistoricalOhlcvProviderResult:
    bars: tuple[HistoricalOhlcvBar, ...] = ()
    unavailable_reason: str | None = None
    adjustments_available: bool | None = None
    freshness_state: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def available(
        cls,
        bars: Sequence[HistoricalOhlcvBar | Mapping[str, Any]],
        *,
        adjustments_available: bool | None = None,
        freshness_state: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "HistoricalOhlcvProviderResult":
        return cls(
            bars=tuple(_normalize_bars(bars)),
            unavailable_reason=None,
            adjustments_available=adjustments_available,
            freshness_state=freshness_state,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def unavailable(
        cls,
        reason: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> "HistoricalOhlcvProviderResult":
        normalized = _safe_code(reason) or _PROVIDER_UNAVAILABLE
        return cls(unavailable_reason=normalized, metadata=dict(metadata or {}))


class HistoricalOhlcvProvider(Protocol):
    def fetch_ohlcv_history(
        self,
        request: HistoricalOhlcvReadinessRequest,
    ) -> HistoricalOhlcvProviderResult:
        ...


@dataclass(frozen=True)
class HistoricalOhlcvAcquisitionResult:
    bars: list[HistoricalOhlcvBar]
    readiness: dict[str, Any]
    unavailable_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "bars": [bar.as_dict() for bar in self.bars],
            "readiness": dict(self.readiness),
            "unavailableReason": self.unavailable_reason,
        }


class HistoricalOhlcvReadinessService:
    """Provider-neutral OHLCV readiness and acquisition seam."""

    def __init__(self, provider: HistoricalOhlcvProvider | None = None) -> None:
        self.provider = provider

    def fetch(self, request: HistoricalOhlcvReadinessRequest) -> HistoricalOhlcvAcquisitionResult:
        if self.provider is None:
            return self._result_from_provider_result(
                request,
                HistoricalOhlcvProviderResult.unavailable(_PROVIDER_MISSING),
                benchmark_state="missing" if request.benchmark_required else "not_requested",
            )

        try:
            provider_result = self.provider.fetch_ohlcv_history(request)
        except Exception:
            provider_result = HistoricalOhlcvProviderResult.unavailable(_PROVIDER_UNAVAILABLE)

        benchmark_result = self._benchmark_result(request)
        return self._result_from_provider_result(
            request,
            provider_result,
            benchmark_state=benchmark_result["state"],
            benchmark_usable_bars=benchmark_result["usable_bars"],
            benchmark_missing_bars=benchmark_result["missing_bars"],
            benchmark_range=benchmark_result["usable_range"],
            benchmark_adjustment_state=benchmark_result["adjustment_state"],
        )

    def assess_supplied_history(
        self,
        request: HistoricalOhlcvReadinessRequest,
        bars: Sequence[HistoricalOhlcvBar | Mapping[str, Any]],
        *,
        benchmark_bars: Sequence[HistoricalOhlcvBar | Mapping[str, Any]] | None = None,
        benchmark_source_available: bool | None = None,
        source_available: bool,
        adjustments_available: bool | None = None,
        freshness_state: str | None = None,
        unavailable_reason: str | None = None,
    ) -> HistoricalOhlcvAcquisitionResult:
        if source_available:
            provider_result = HistoricalOhlcvProviderResult.available(
                bars,
                adjustments_available=adjustments_available,
                freshness_state=freshness_state,
            )
        else:
            provider_result = HistoricalOhlcvProviderResult.unavailable(
                unavailable_reason or _PROVIDER_MISSING
            )
        benchmark_result = _assess_supplied_benchmark(
            request,
            benchmark_bars,
            benchmark_source_available=benchmark_source_available,
        )
        return self._result_from_provider_result(
            request,
            provider_result,
            benchmark_state=benchmark_result["state"],
            benchmark_usable_bars=benchmark_result["usable_bars"],
            benchmark_missing_bars=benchmark_result["missing_bars"],
            benchmark_range=benchmark_result["usable_range"],
            benchmark_adjustment_state=benchmark_result["adjustment_state"],
        )

    def _benchmark_result(self, request: HistoricalOhlcvReadinessRequest) -> dict[str, Any]:
        if not request.benchmark_required:
            return {
                "state": "not_requested",
                "usable_bars": 0,
                "missing_bars": 0,
                "usable_range": {},
                "adjustment_state": "not_required",
            }
        if self.provider is None or not request.benchmark_symbol:
            return {
                "state": "missing",
                "usable_bars": 0,
                "missing_bars": max(0, int(request.required_bars or 0)),
                "usable_range": {},
                "adjustment_state": "missing" if request.require_adjusted else "not_required",
            }
        try:
            benchmark_result = self.provider.fetch_ohlcv_history(request.benchmark_request())
        except Exception:
            return {
                "state": "missing",
                "usable_bars": 0,
                "missing_bars": max(0, int(request.required_bars or 0)),
                "usable_range": {},
                "adjustment_state": "missing" if request.require_adjusted else "not_required",
            }
        usable_bars = _count_usable_bars(benchmark_result.bars)
        required_bars = max(0, int(request.required_bars or 0))
        if benchmark_result.unavailable_reason:
            return {
                "state": "missing",
                "usable_bars": 0,
                "missing_bars": required_bars,
                "usable_range": {},
                "adjustment_state": "missing" if request.require_adjusted else "not_required",
            }
        missing_bars = max(0, required_bars - usable_bars)
        return {
            "state": "insufficient_coverage" if missing_bars > 0 else "available",
            "usable_bars": usable_bars,
            "missing_bars": missing_bars,
            "usable_range": _usable_range(benchmark_result.bars),
            "adjustment_state": _adjustment_state(
                request,
                list(benchmark_result.bars),
                benchmark_result.adjustments_available,
            ),
        }

    def _result_from_provider_result(
        self,
        request: HistoricalOhlcvReadinessRequest,
        provider_result: HistoricalOhlcvProviderResult,
        *,
        benchmark_state: str,
        benchmark_usable_bars: int | None = None,
        benchmark_missing_bars: int | None = None,
        benchmark_range: Mapping[str, Any] | None = None,
        benchmark_adjustment_state: str | None = None,
    ) -> HistoricalOhlcvAcquisitionResult:
        bars = list(provider_result.bars) if not provider_result.unavailable_reason else []
        usable_bars = _count_usable_bars(bars)
        required_bars = max(0, int(request.required_bars or 0))
        missing_bars = max(0, required_bars - usable_bars)
        provider_state = _provider_state(provider_result.unavailable_reason)
        freshness_state = _freshness_state(request, bars, provider_result.freshness_state)
        adjustment_state = _adjustment_state(request, bars, provider_result.adjustments_available)
        missing_requirements = _missing_requirements(
            provider_state=provider_state,
            missing_bars=missing_bars,
            freshness_state=freshness_state,
            adjustment_state=adjustment_state,
            benchmark_state=benchmark_state,
            benchmark_adjustment_state=benchmark_adjustment_state,
        )
        readiness = {
            "contractVersion": HISTORICAL_OHLCV_READINESS_CONTRACT_VERSION,
            "symbol": _normalize_symbol(request.symbol),
            "market": _safe_code(request.market) or "unknown",
            "timeframe": _safe_code(request.timeframe) or HISTORICAL_OHLCV_DEFAULT_TIMEFRAME,
            "requestedRange": {
                "start": request.start.isoformat() if request.start else None,
                "end": request.end.isoformat() if request.end else None,
            },
            "lookbackBars": request.lookback_bars,
            "requiredBars": required_bars,
            "usableBars": usable_bars,
            "missingBars": missing_bars,
            "usableRange": _usable_range(bars),
            "freshnessState": freshness_state,
            "adjustmentState": adjustment_state,
            "benchmarkState": benchmark_state,
            "benchmarkSymbol": _normalize_symbol(str(request.benchmark_symbol or "")) or None,
            "benchmarkUsableBars": benchmark_usable_bars,
            "benchmarkMissingBars": benchmark_missing_bars,
            "benchmarkUsableRange": dict(benchmark_range or {}),
            "benchmarkAdjustmentState": benchmark_adjustment_state or "not_required",
            "providerState": provider_state,
            "runtimeStatus": _runtime_status(provider_result.metadata),
            "overallState": _overall_state(missing_requirements),
            "missingRequirements": missing_requirements,
            "consumerSafe": True,
        }
        return HistoricalOhlcvAcquisitionResult(
            bars=bars,
            readiness=readiness,
            unavailable_reason=provider_result.unavailable_reason,
        )


def build_backtest_historical_ohlcv_readiness(
    readiness: Mapping[str, Any] | None,
    *,
    runtime_status: str | None = None,
    operator_next_action: str | None = None,
) -> dict[str, Any]:
    """Project generic OHLCV readiness into a consumer-safe Backtest contract."""

    source = dict(readiness or {})
    missing_requirements = _safe_text_list(source.get("missingRequirements"))
    requested_range = _safe_mapping(source.get("requestedRange"))
    required_bars = _safe_int(source.get("requiredBars"))
    available_bars = _safe_int(source.get("usableBars"))
    missing_bars = _safe_int(source.get("missingBars"))
    provider_state = _safe_code(source.get("providerState"))
    freshness_state = _safe_code(source.get("freshnessState"))
    adjustment_state = _safe_code(source.get("adjustmentState"))
    benchmark_state = _safe_code(source.get("benchmarkState")) or "not_requested"
    benchmark_adjustment_state = _safe_code(source.get("benchmarkAdjustmentState"))
    benchmark_usable_bars = _safe_int(source.get("benchmarkUsableBars"))
    benchmark_missing_bars = _safe_int(source.get("benchmarkMissingBars"))
    benchmark_range = _safe_mapping(source.get("benchmarkUsableRange"))
    normalized_runtime = _normalize_backtest_runtime_status(runtime_status, source, missing_requirements)
    adjusted_requirement_state = _adjusted_requirement_state(
        adjustment_state=adjustment_state,
        benchmark_adjustment_state=benchmark_adjustment_state,
        benchmark_state=benchmark_state,
    )
    status = _backtest_readiness_status(
        runtime_status=normalized_runtime,
        provider_state=provider_state,
        freshness_state=freshness_state,
        adjustment_state=adjusted_requirement_state,
        benchmark_state=benchmark_state,
        missing_bars=missing_bars,
        missing_requirements=missing_requirements,
    )
    missing_classes = _backtest_missing_data_classes(
        status=status,
        provider_state=provider_state,
        adjustment_state=adjusted_requirement_state,
        benchmark_state=benchmark_state,
        missing_requirements=missing_requirements,
    )
    blocked_reason = _backtest_blocked_execution_reason(
        status=status,
        missing_classes=missing_classes,
    )
    next_action = _clean_public_text(operator_next_action) or _default_backtest_operator_action(
        status,
        missing_classes=missing_classes,
    )
    return {
        "contractVersion": BACKTEST_HISTORICAL_OHLCV_READINESS_CONTRACT_VERSION,
        "status": status,
        "executable": status == "available",
        "requestedSymbol": _normalize_symbol(str(source.get("symbol") or "")),
        "requestedMarket": _safe_code(source.get("market")) or "unknown",
        "requestedDateRange": {
            "start": _clean_public_text(requested_range.get("start")),
            "end": _clean_public_text(requested_range.get("end")),
        },
        "requestedRange": {
            "start": _clean_public_text(requested_range.get("start")),
            "end": _clean_public_text(requested_range.get("end")),
        },
        "usableRange": _sanitize_range(source.get("usableRange")),
        "requiredBarCount": required_bars,
        "availableBarCount": available_bars,
        "symbolBarsAvailable": available_bars,
        "benchmarkBarsAvailable": benchmark_usable_bars,
        "missingDateCoverage": {
            "missingBarCount": missing_bars,
            "state": "covered" if missing_bars <= 0 else "missing",
        },
        "adjustedDataRequirement": {
            "required": adjusted_requirement_state != "not_required",
            "state": adjusted_requirement_state or "unknown",
        },
        "benchmarkReadiness": {
            "required": benchmark_state != "not_requested",
            "symbol": _clean_public_text(source.get("benchmarkSymbol")),
            "status": benchmark_state,
            "requiredBarCount": required_bars if benchmark_state != "not_requested" else 0,
            "availableBarCount": benchmark_usable_bars,
            "missingBarCount": benchmark_missing_bars,
            "adjustmentState": benchmark_adjustment_state or "not_required",
            "usableRange": _sanitize_range(benchmark_range),
        },
        "historicalOhlcvRuntimeStatus": normalized_runtime,
        "operatorNextAction": next_action,
        "nextOperatorAction": next_action,
        "consumerSafeMessage": _backtest_consumer_message(status, missing_classes=missing_classes),
        "blockedExecutionReason": blocked_reason,
        "missingDataClasses": missing_classes,
        "missingDataFamilies": list(missing_classes),
        "sourceReadiness": _sanitize_source_readiness(source),
        "consumerSafe": True,
    }


def _normalize_bars(values: Sequence[HistoricalOhlcvBar | Mapping[str, Any]]) -> list[HistoricalOhlcvBar]:
    bars: list[HistoricalOhlcvBar] = []
    for value in values or []:
        bar = _normalize_bar(value)
        if bar is not None:
            bars.append(bar)
    return sorted(bars, key=lambda item: item.date)


def _safe_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _adjusted_requirement_state(
    *,
    adjustment_state: str,
    benchmark_adjustment_state: str,
    benchmark_state: str,
) -> str:
    if adjustment_state == "not_required":
        return "not_required"
    if adjustment_state == "missing":
        return "missing"
    if benchmark_state != "not_requested" and benchmark_adjustment_state == "missing":
        return "missing"
    if adjustment_state == "available":
        return "available"
    return adjustment_state or "unknown"


def _safe_text_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    result: list[str] = []
    for item in value:
        normalized = _safe_code(item)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _clean_public_text(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    lower = text.lower()
    forbidden = ("apikey", "api_key", "token", "credential", "traceid", "trace_id", "requestid", "request_id", "cachekey", "cache_key", "traceback")
    if any(item in lower for item in forbidden):
        return None
    return text[:240]


def _normalize_backtest_runtime_status(
    runtime_status: str | None,
    source: Mapping[str, Any],
    missing_requirements: Sequence[str],
) -> str:
    normalized = _safe_code(runtime_status)
    if normalized in _SAFE_RUNTIME_STATUSES:
        return normalized
    source_runtime = _safe_code(source.get("runtimeStatus"))
    if source_runtime in _SAFE_RUNTIME_STATUSES:
        return source_runtime
    provider_state = _safe_code(source.get("providerState"))
    freshness_state = _safe_code(source.get("freshnessState"))
    if provider_state == _PROVIDER_MISSING:
        return "not_configured"
    if provider_state in {_PROVIDER_UNAVAILABLE, _ENTITLEMENT_REQUIRED}:
        return "unavailable"
    if freshness_state == "stale" or _STALE_DATA in missing_requirements:
        return "stale"
    if _INSUFFICIENT_HISTORY in missing_requirements:
        return "insufficient_coverage"
    if provider_state == "available":
        return "available"
    return "unavailable"


def _backtest_readiness_status(
    *,
    runtime_status: str,
    provider_state: str,
    freshness_state: str,
    adjustment_state: str,
    benchmark_state: str,
    missing_bars: int,
    missing_requirements: Sequence[str],
) -> str:
    if runtime_status == "not_configured":
        return "not_configured"
    if runtime_status == "missing":
        return "missing"
    if runtime_status == "unavailable" or provider_state in {_PROVIDER_UNAVAILABLE, _ENTITLEMENT_REQUIRED}:
        return "unavailable"
    if provider_state == _PROVIDER_MISSING:
        return "not_configured"
    if (
        missing_bars > 0
        or _INSUFFICIENT_HISTORY in missing_requirements
        or runtime_status == "insufficient_coverage"
        or benchmark_state == "insufficient_coverage"
    ):
        return "insufficient_coverage"
    if adjustment_state == "missing" or benchmark_state == "missing" or any(
        item in missing_requirements for item in (_MISSING_ADJUSTMENTS, _MISSING_BENCHMARK)
    ):
        return "missing"
    if freshness_state == "stale" or _STALE_DATA in missing_requirements or runtime_status == "stale":
        return "stale"
    return "available"


def _backtest_missing_data_classes(
    *,
    status: str,
    provider_state: str,
    adjustment_state: str,
    benchmark_state: str,
    missing_requirements: Sequence[str],
) -> list[str]:
    values: list[str] = []

    def add(value: str) -> None:
        if value not in values:
            values.append(value)

    if status in {"not_configured", "unavailable"} or provider_state != "available":
        add("historical_ohlcv")
        add("symbol_ohlcv")
    if status == "insufficient_coverage" or _INSUFFICIENT_HISTORY in missing_requirements:
        add("date_coverage")
        if benchmark_state != "insufficient_coverage":
            add("symbol_ohlcv")
    if status == "stale" or _STALE_DATA in missing_requirements:
        add("freshness")
    if adjustment_state == "missing" or _MISSING_ADJUSTMENTS in missing_requirements:
        add("adjusted_prices")
    if benchmark_state in {"missing", "insufficient_coverage"} or _MISSING_BENCHMARK in missing_requirements:
        add("benchmark_ohlcv")
    return values


def _backtest_blocked_execution_reason(*, status: str, missing_classes: Sequence[str]) -> str | None:
    if status == "available":
        return None
    missing = set(missing_classes or [])
    if "adjusted_prices" in missing and "historical_ohlcv" not in missing and "symbol_ohlcv" not in missing:
        return "adjusted_prices_missing"
    if "benchmark_ohlcv" in missing and "historical_ohlcv" not in missing and "symbol_ohlcv" not in missing:
        return "benchmark_ohlcv_missing"
    return f"historical_ohlcv_{status}"


def _default_backtest_operator_action(status: str, *, missing_classes: Sequence[str] | None = None) -> str:
    missing = set(missing_classes or [])
    if status == "available":
        return "Historical OHLCV requirements are met for this Backtest request."
    if status == "not_configured":
        return "Enable the historical OHLCV runtime and run the existing cache preflight before retrying Backtest."
    if status == "insufficient_coverage":
        return "Seed or refresh the local historical OHLCV cache for the requested symbol and date range."
    if status == "stale":
        return "Refresh the local historical OHLCV cache until the requested end date is covered."
    if status == "missing":
        if "adjusted_prices" in missing and "benchmark_ohlcv" in missing:
            return "Provide adjusted historical prices or adjustment metadata and benchmark OHLCV coverage before retrying Backtest."
        if "adjusted_prices" in missing:
            return "Provide adjusted historical prices or real adjustment metadata before retrying Backtest."
        if "benchmark_ohlcv" in missing:
            return "Provide benchmark OHLCV coverage before retrying Backtest."
        return "Provide the missing historical OHLCV, adjusted price, or benchmark coverage through the existing cache workflow."
    return "Review historical OHLCV runtime availability and rerun the existing cache preflight."


def _backtest_consumer_message(status: str, *, missing_classes: Sequence[str] | None = None) -> str:
    missing = set(missing_classes or [])
    if status == "available":
        return "Historical OHLCV coverage is available for this Backtest request."
    if status == "not_configured":
        return "Backtest cannot run because historical OHLCV runtime readiness is not configured."
    if status == "insufficient_coverage":
        return "Backtest cannot run because the requested date range does not have enough historical OHLCV bars."
    if status == "stale":
        return "Backtest cannot run because the historical OHLCV cache is stale for the requested range."
    if status == "missing":
        if "adjusted_prices" in missing and "historical_ohlcv" not in missing and "symbol_ohlcv" not in missing:
            return "Backtest cannot run because adjusted historical prices or adjustment metadata are missing."
        return "Backtest cannot run because required historical OHLCV inputs are missing."
    return "Backtest cannot run because historical OHLCV runtime is unavailable."


def _sanitize_source_readiness(source: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "contractVersion",
        "symbol",
        "market",
        "timeframe",
        "requestedRange",
        "lookbackBars",
        "requiredBars",
        "usableBars",
        "missingBars",
        "usableRange",
        "freshnessState",
        "adjustmentState",
        "benchmarkState",
        "benchmarkAdjustmentState",
        "providerState",
        "runtimeStatus",
        "overallState",
        "missingRequirements",
        "consumerSafe",
    }
    sanitized = {key: value for key, value in dict(source or {}).items() if key in allowed}
    sanitized["consumerSafe"] = True
    return sanitized


def _assess_supplied_benchmark(
    request: HistoricalOhlcvReadinessRequest,
    bars: Sequence[HistoricalOhlcvBar | Mapping[str, Any]] | None,
    *,
    benchmark_source_available: bool | None,
) -> dict[str, Any]:
    if not request.benchmark_required:
        return {
            "state": "not_requested",
            "usable_bars": 0,
            "missing_bars": 0,
            "usable_range": {},
            "adjustment_state": "not_required",
        }
    if benchmark_source_available is False:
        return {
            "state": "missing",
            "usable_bars": 0,
            "missing_bars": max(0, int(request.required_bars or 0)),
            "usable_range": {},
            "adjustment_state": "missing" if request.require_adjusted else "not_required",
        }
    normalized_bars = _normalize_bars(list(bars or []))
    usable_bars = _count_usable_bars(normalized_bars)
    required_bars = max(0, int(request.required_bars or 0))
    missing_bars = max(0, required_bars - usable_bars)
    if benchmark_source_available is None and not normalized_bars:
        state = "missing"
    elif missing_bars > 0:
        state = "insufficient_coverage"
    else:
        state = "available"
    return {
        "state": state,
        "usable_bars": usable_bars,
        "missing_bars": missing_bars,
        "usable_range": _usable_range(normalized_bars),
        "adjustment_state": _adjustment_state(request, normalized_bars, None),
    }


def _usable_range(bars: Sequence[HistoricalOhlcvBar]) -> dict[str, str | None]:
    dates = [bar.date for bar in bars if isinstance(bar.date, date)]
    if not dates:
        return {"start": None, "end": None}
    return {"start": min(dates).isoformat(), "end": max(dates).isoformat()}


def _sanitize_range(value: Any) -> dict[str, str | None]:
    source = _safe_mapping(value)
    return {
        "start": _clean_public_text(source.get("start")),
        "end": _clean_public_text(source.get("end")),
    }


def _normalize_bar(value: HistoricalOhlcvBar | Mapping[str, Any]) -> HistoricalOhlcvBar | None:
    if isinstance(value, HistoricalOhlcvBar):
        return value
    if not isinstance(value, Mapping):
        return None
    bar_date = _coerce_date(value.get("date") or value.get("trade_date") or value.get("tradeDate"))
    open_value = _finite_float(value.get("open"))
    high_value = _finite_float(value.get("high"))
    low_value = _finite_float(value.get("low"))
    close_value = _finite_float(value.get("close"))
    volume_value = _finite_float(value.get("volume"))
    if (
        bar_date is None
        or open_value is None
        or high_value is None
        or low_value is None
        or close_value is None
        or volume_value is None
    ):
        return None
    adjusted_close = _finite_float(
        value.get("adjustedClose")
        or value.get("adjusted_close")
        or value.get("adj_close")
        or value.get("Adj Close")
        or value.get("Adjusted Close")
    )
    return HistoricalOhlcvBar(
        date=bar_date,
        open=open_value,
        high=high_value,
        low=low_value,
        close=close_value,
        volume=volume_value,
        adjusted_close=adjusted_close,
    )


def _count_usable_bars(bars: Sequence[HistoricalOhlcvBar]) -> int:
    return sum(1 for bar in bars if _is_usable_bar(bar))


def _is_usable_bar(bar: HistoricalOhlcvBar) -> bool:
    return (
        bar.open > 0
        and bar.high > 0
        and bar.low > 0
        and bar.close > 0
        and bar.high >= bar.low
        and bar.volume >= 0
    )


def _provider_state(unavailable_reason: str | None) -> str:
    reason = _safe_code(unavailable_reason)
    if not reason:
        return "available"
    if reason == _PROVIDER_MISSING:
        return _PROVIDER_MISSING
    if reason == _ENTITLEMENT_REQUIRED:
        return _ENTITLEMENT_REQUIRED
    return _PROVIDER_UNAVAILABLE


def _runtime_status(metadata: Mapping[str, Any]) -> str | None:
    status = _safe_code(metadata.get("runtimeStatus") or metadata.get("runtime_status"))
    return status if status in _SAFE_RUNTIME_STATUSES else None


def _freshness_state(
    request: HistoricalOhlcvReadinessRequest,
    bars: Sequence[HistoricalOhlcvBar],
    provider_freshness_state: str | None,
) -> str:
    normalized = _safe_code(provider_freshness_state)
    if normalized == "stale":
        return "stale"
    if not bars:
        return "unknown"
    if request.end is not None:
        latest = max(bar.date for bar in bars)
        if latest < request.end:
            return "stale"
        return "current"
    return "unknown"


def _adjustment_state(
    request: HistoricalOhlcvReadinessRequest,
    bars: Sequence[HistoricalOhlcvBar],
    adjustments_available: bool | None,
) -> str:
    if not request.require_adjusted:
        return "not_required"
    if adjustments_available is False:
        return "missing"
    if bars and all(bar.adjusted_close is not None for bar in bars):
        return "available"
    return "missing"


def _missing_requirements(
    *,
    provider_state: str,
    missing_bars: int,
    freshness_state: str,
    adjustment_state: str,
    benchmark_state: str,
    benchmark_adjustment_state: str | None = None,
) -> list[str]:
    values: list[str] = []
    for candidate in (_PROVIDER_MISSING, _PROVIDER_UNAVAILABLE, _ENTITLEMENT_REQUIRED):
        if provider_state == candidate:
            values.append(candidate)
    if missing_bars > 0:
        values.append(_INSUFFICIENT_HISTORY)
    if freshness_state == "stale":
        values.append(_STALE_DATA)
    if adjustment_state == "missing" or benchmark_adjustment_state == "missing":
        values.append(_MISSING_ADJUSTMENTS)
    if benchmark_state == "missing":
        values.append(_MISSING_BENCHMARK)
    return values


def _overall_state(missing_requirements: Sequence[str]) -> str:
    if not missing_requirements:
        return "ready"
    if any(item in _BLOCKING_REQUIREMENTS for item in missing_requirements):
        return "blocked"
    return "degraded"


def _normalize_symbol(value: str) -> str:
    return str(value or "").strip().upper()


def _safe_code(value: Any) -> str:
    return str(value or "").strip().lower()


def _coerce_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _finite_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed
