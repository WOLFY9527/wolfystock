from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol


HISTORICAL_OHLCV_READINESS_CONTRACT_VERSION = "historical_ohlcv_readiness_v1"
HISTORICAL_OHLCV_DEFAULT_TIMEFRAME = "1d"
_PROVIDER_MISSING = "provider_missing"
_PROVIDER_UNAVAILABLE = "provider_unavailable"
_ENTITLEMENT_REQUIRED = "entitlement_required"
_INSUFFICIENT_HISTORY = "insufficient_history"
_STALE_DATA = "stale_data"
_MISSING_ADJUSTMENTS = "missing_adjustments"
_MISSING_BENCHMARK = "missing_benchmark"
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
    def unavailable(cls, reason: str) -> "HistoricalOhlcvProviderResult":
        normalized = _safe_code(reason) or _PROVIDER_UNAVAILABLE
        return cls(unavailable_reason=normalized)


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

        benchmark_state = self._benchmark_state(request)
        return self._result_from_provider_result(request, provider_result, benchmark_state=benchmark_state)

    def assess_supplied_history(
        self,
        request: HistoricalOhlcvReadinessRequest,
        bars: Sequence[HistoricalOhlcvBar | Mapping[str, Any]],
        *,
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
        benchmark_state = "missing" if request.benchmark_required else "not_requested"
        return self._result_from_provider_result(request, provider_result, benchmark_state=benchmark_state)

    def _benchmark_state(self, request: HistoricalOhlcvReadinessRequest) -> str:
        if not request.benchmark_required:
            return "not_requested"
        if self.provider is None or not request.benchmark_symbol:
            return "missing"
        try:
            benchmark_result = self.provider.fetch_ohlcv_history(request.benchmark_request())
        except Exception:
            return "missing"
        usable_bars = _count_usable_bars(benchmark_result.bars)
        if benchmark_result.unavailable_reason or usable_bars < max(0, int(request.required_bars or 0)):
            return "missing"
        return "available"

    def _result_from_provider_result(
        self,
        request: HistoricalOhlcvReadinessRequest,
        provider_result: HistoricalOhlcvProviderResult,
        *,
        benchmark_state: str,
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
            "freshnessState": freshness_state,
            "adjustmentState": adjustment_state,
            "benchmarkState": benchmark_state,
            "providerState": provider_state,
            "overallState": _overall_state(missing_requirements),
            "missingRequirements": missing_requirements,
            "consumerSafe": True,
        }
        return HistoricalOhlcvAcquisitionResult(
            bars=bars,
            readiness=readiness,
            unavailable_reason=provider_result.unavailable_reason,
        )


def _normalize_bars(values: Sequence[HistoricalOhlcvBar | Mapping[str, Any]]) -> list[HistoricalOhlcvBar]:
    bars: list[HistoricalOhlcvBar] = []
    for value in values or []:
        bar = _normalize_bar(value)
        if bar is not None:
            bars.append(bar)
    return sorted(bars, key=lambda item: item.date)


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
    adjusted_close = _finite_float(value.get("adjustedClose") or value.get("adjusted_close") or value.get("adj_close"))
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
) -> list[str]:
    values: list[str] = []
    for candidate in (_PROVIDER_MISSING, _PROVIDER_UNAVAILABLE, _ENTITLEMENT_REQUIRED):
        if provider_state == candidate:
            values.append(candidate)
    if missing_bars > 0:
        values.append(_INSUFFICIENT_HISTORY)
    if freshness_state == "stale":
        values.append(_STALE_DATA)
    if adjustment_state == "missing":
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
