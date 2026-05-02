# -*- coding: utf-8 -*-
"""Quota-aware provider planning for analysis data categories.

Categories are deliberately broader than provider APIs: stock_name/profile,
quote/latest_price, historical_prices, technical_indicators, fundamentals,
earnings/financial_statements, news, sentiment, and macro/market_context.
Provider order is market-aware and lazy: one provider is attempted first, and
fallbacks are tried only after timeout, circuit-open, error, or insufficient
payload. Independent categories may run concurrently, but duplicate providers
for the same provider/category/symbol key are coalesced.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

from data_provider.us_index_mapping import is_us_index_code, is_us_stock_code

logger = logging.getLogger(__name__)


class DataCategory(str, Enum):
    STOCK_NAME = "stock_name"
    PROFILE = "profile"
    QUOTE = "quote"
    HISTORICAL_PRICES = "historical_prices"
    TECHNICAL_INDICATORS = "technical_indicators"
    FUNDAMENTALS = "fundamentals"
    EARNINGS = "earnings"
    NEWS = "news"
    SENTIMENT = "sentiment"
    MACRO = "macro"


class ProviderTimeout(TimeoutError):
    """Raised when a provider exceeds its category timeout."""


class ProviderQuotaExceeded(RuntimeError):
    """Raised for 403/429/quota responses that should not be retried."""


class ProviderInvalidPayload(RuntimeError):
    """Raised when a provider returns a payload that is not sufficient."""


@dataclass(frozen=True)
class CategoryProviderPlan:
    category: DataCategory
    providers: list[str]
    timeout_seconds: float
    cache_ttl_seconds: int
    max_attempts: int = 3
    required_fields: tuple[str, ...] = ()

    @property
    def primary(self) -> Optional[str]:
        return self.providers[0] if self.providers else None

    @property
    def fallback(self) -> list[str]:
        return self.providers[1:]


@dataclass(frozen=True)
class AnalysisProviderPlan:
    symbol: str
    market: str
    categories: dict[DataCategory, CategoryProviderPlan]


@dataclass
class ProviderCategoryResult:
    category: DataCategory
    source_provider: Optional[str]
    data: Any = None
    source_category: Optional[str] = None
    is_fallback: bool = False
    cache_hit: bool = False
    warnings: list[str] = field(default_factory=list)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    partial: bool = False

    def metadata(self) -> dict[str, Any]:
        return {
            "source_provider": self.source_provider,
            "source_category": self.source_category or self.category.value,
            "is_fallback": self.is_fallback,
            "cache_hit": self.cache_hit,
            "partial": self.partial,
            "warnings": list(self.warnings),
            "attempts": copy.deepcopy(self.attempts),
        }


@dataclass
class _CacheEntry:
    expires_at: float
    data: Any


@dataclass
class _CircuitState:
    failures: list[float] = field(default_factory=list)
    opened_at: Optional[float] = None
    half_open: bool = False


def _normalize_market(symbol: str, market: Optional[str]) -> str:
    if market:
        normalized = str(market).strip().lower()
        if normalized in {"us", "cn", "hk"}:
            return normalized
    code = str(symbol or "").strip().upper()
    if is_us_stock_code(code) or is_us_index_code(code):
        return "us"
    if code.startswith("HK") or code.endswith(".HK") or (code.isdigit() and len(code) == 5):
        return "hk"
    if code.isdigit() and len(code) == 6:
        return "cn"
    return "us" if code.isalpha() else "cn"


def _category_defaults(market: str) -> dict[DataCategory, CategoryProviderPlan]:
    us = {
        DataCategory.STOCK_NAME: ["fmp", "yfinance", "finnhub"],
        DataCategory.PROFILE: ["fmp", "yfinance", "finnhub", "alpha_vantage"],
        DataCategory.QUOTE: ["alpaca", "finnhub", "fmp", "yfinance"],
        DataCategory.HISTORICAL_PRICES: ["fmp", "yfinance", "alpha_vantage"],
        DataCategory.TECHNICAL_INDICATORS: ["fmp", "alpha_vantage", "local_history"],
        DataCategory.FUNDAMENTALS: ["fmp", "finnhub", "yfinance", "alpha_vantage"],
        DataCategory.EARNINGS: ["fmp", "yfinance", "alpha_vantage"],
        DataCategory.NEWS: ["gnews", "finnhub", "tavily"],
        DataCategory.SENTIMENT: ["social_sentiment_service", "tavily", "local_inference"],
        DataCategory.MACRO: ["local_market_context"],
    }
    cn = {
        DataCategory.STOCK_NAME: ["akshare", "tushare", "pytdx", "baostock", "static_mapping"],
        DataCategory.PROFILE: ["akshare", "tushare"],
        DataCategory.QUOTE: ["efinance", "akshare", "tushare"],
        DataCategory.HISTORICAL_PRICES: ["akshare", "tushare", "baostock"],
        DataCategory.TECHNICAL_INDICATORS: ["local_history", "akshare"],
        DataCategory.FUNDAMENTALS: ["akshare", "tushare"],
        DataCategory.EARNINGS: ["akshare", "tushare"],
        DataCategory.NEWS: ["gnews", "tavily"],
        DataCategory.SENTIMENT: ["tavily", "local_inference"],
        DataCategory.MACRO: ["local_market_context"],
    }
    base = us if market == "us" else cn
    timeouts = {
        DataCategory.STOCK_NAME: 3,
        DataCategory.PROFILE: 3,
        DataCategory.QUOTE: 3,
        DataCategory.HISTORICAL_PRICES: 5,
        DataCategory.TECHNICAL_INDICATORS: 5,
        DataCategory.FUNDAMENTALS: 5,
        DataCategory.EARNINGS: 5,
        DataCategory.NEWS: 6,
        DataCategory.SENTIMENT: 6,
        DataCategory.MACRO: 5,
    }
    ttls = {
        DataCategory.STOCK_NAME: 60 * 60 * 24,
        DataCategory.PROFILE: 60 * 60 * 12,
        DataCategory.QUOTE: 60,
        DataCategory.HISTORICAL_PRICES: 60 * 15,
        DataCategory.TECHNICAL_INDICATORS: 60 * 5,
        DataCategory.FUNDAMENTALS: 60 * 60 * 12,
        DataCategory.EARNINGS: 60 * 60 * 12,
        DataCategory.NEWS: 60 * 10,
        DataCategory.SENTIMENT: 60 * 10,
        DataCategory.MACRO: 60 * 10,
    }
    return {
        category: CategoryProviderPlan(
            category=category,
            providers=list(providers),
            timeout_seconds=timeouts[category],
            cache_ttl_seconds=ttls[category],
            max_attempts=min(3, len(providers)),
        )
        for category, providers in base.items()
    }


def build_analysis_provider_plan(
    symbol: str,
    *,
    market: Optional[str] = None,
    categories: Optional[Iterable[DataCategory | str]] = None,
) -> AnalysisProviderPlan:
    resolved_market = _normalize_market(symbol, market)
    defaults = _category_defaults(resolved_market)
    selected = [DataCategory(item) for item in (categories or defaults.keys())]
    return AnalysisProviderPlan(
        symbol=str(symbol or "").strip().upper(),
        market=resolved_market,
        categories={category: defaults[category] for category in selected if category in defaults},
    )


class AnalysisProviderExecutor:
    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        failure_window_seconds: int = 300,
        cooldown_seconds: int = 120,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.failure_window_seconds = failure_window_seconds
        self.cooldown_seconds = cooldown_seconds
        self._cache: dict[str, _CacheEntry] = {}
        self._inflight: dict[str, Future] = {}
        self._circuits: dict[str, _CircuitState] = {}
        self._lock = threading.RLock()
        self._call_pool = ThreadPoolExecutor(max_workers=16, thread_name_prefix="provider_call_")

    def execute_plan(
        self,
        plan: AnalysisProviderPlan,
        *,
        symbol: str,
        providers_by_category: Mapping[DataCategory, Mapping[str, Callable[[], Any]]],
        max_workers: int = 4,
    ) -> dict[DataCategory, ProviderCategoryResult]:
        results: dict[DataCategory, ProviderCategoryResult] = {}
        with ThreadPoolExecutor(max_workers=max(1, max_workers), thread_name_prefix="provider_category_") as pool:
            future_map = {
                pool.submit(
                    self.execute_category,
                    category_plan,
                    symbol=symbol,
                    providers=providers_by_category.get(category, {}),
                ): category
                for category, category_plan in plan.categories.items()
                if category in providers_by_category
            }
            for future in as_completed(future_map):
                category = future_map[future]
                results[category] = future.result()
        return results

    def execute_category(
        self,
        category_plan: CategoryProviderPlan,
        *,
        symbol: str,
        providers: Mapping[str, Callable[[], Any]],
        params: Optional[Mapping[str, Any]] = None,
        sufficient: Optional[Callable[[Any], bool]] = None,
    ) -> ProviderCategoryResult:
        sufficient = sufficient or self._has_sufficient_data
        warnings: list[str] = []
        attempts: list[dict[str, Any]] = []
        available = [provider for provider in category_plan.providers if provider in providers]
        for index, provider in enumerate(available[: category_plan.max_attempts]):
            if self._is_circuit_open(provider, category_plan.category):
                attempts.append({"provider": provider, "status": "skipped", "reason": "circuit_open"})
                warnings.append(f"{provider}: circuit_open")
                logger.warning(
                    "ProviderCircuitOpened category=%s provider=%s circuit_state=open",
                    category_plan.category.value,
                    provider,
                )
                continue
            started = time.monotonic()
            try:
                data, cache_hit = self._get_or_call(
                    provider=provider,
                    category_plan=category_plan,
                    symbol=symbol,
                    params=params or {},
                    call=providers[provider],
                )
                duration_ms = int((time.monotonic() - started) * 1000)
                if not sufficient(data):
                    self._record_failure(provider, category_plan.category)
                    attempts.append(
                        {
                            "provider": provider,
                            "status": "failed",
                            "reason": "invalid_payload",
                            "duration_ms": duration_ms,
                            "cache_hit": cache_hit,
                        }
                    )
                    logger.error(
                        "ProviderInvalidPayload category=%s provider=%s duration_ms=%s cache_hit=%s",
                        category_plan.category.value,
                        provider,
                        duration_ms,
                        cache_hit,
                    )
                    continue
                self._record_success(provider, category_plan.category)
                attempts.append(
                    {
                        "provider": provider,
                        "status": "success",
                        "duration_ms": duration_ms,
                        "cache_hit": cache_hit,
                        "is_fallback": index > 0,
                    }
                )
                if index > 0:
                    logger.warning(
                        "ProviderFallbackUsed category=%s provider=%s symbol=%s duration_ms=%s",
                        category_plan.category.value,
                        provider,
                        symbol,
                        duration_ms,
                    )
                else:
                    logger.debug(
                        "ProviderCallSucceeded category=%s provider=%s symbol=%s duration_ms=%s cache_hit=%s",
                        category_plan.category.value,
                        provider,
                        symbol,
                        duration_ms,
                        cache_hit,
                    )
                return ProviderCategoryResult(
                    category=category_plan.category,
                    source_provider=provider,
                    data=data,
                    source_category=category_plan.category.value,
                    is_fallback=index > 0,
                    cache_hit=cache_hit,
                    warnings=warnings,
                    attempts=attempts,
                )
            except Exception as exc:
                duration_ms = int((time.monotonic() - started) * 1000)
                reason = self._classify_exception(exc)
                self._record_failure(provider, category_plan.category)
                attempts.append(
                    {
                        "provider": provider,
                        "status": "failed",
                        "reason": reason,
                        "duration_ms": duration_ms,
                    }
                )
                warnings.append(f"{provider}: {reason}")
                if reason == "timeout":
                    logger.warning(
                        "ProviderCallTimeout category=%s provider=%s symbol=%s duration_ms=%s",
                        category_plan.category.value,
                        provider,
                        symbol,
                        duration_ms,
                    )
                elif reason == "rate_limited":
                    logger.warning(
                        "ProviderQuotaExceeded category=%s provider=%s symbol=%s duration_ms=%s",
                        category_plan.category.value,
                        provider,
                        symbol,
                        duration_ms,
                    )
                else:
                    logger.debug(
                        "ProviderCallFailed category=%s provider=%s symbol=%s reason=%s duration_ms=%s",
                        category_plan.category.value,
                        provider,
                        symbol,
                        reason,
                        duration_ms,
                    )
                continue
        return ProviderCategoryResult(
            category=category_plan.category,
            source_provider=None,
            data=None,
            source_category=category_plan.category.value,
            warnings=warnings,
            attempts=attempts,
            partial=True,
        )

    def _get_or_call(
        self,
        *,
        provider: str,
        category_plan: CategoryProviderPlan,
        symbol: str,
        params: Mapping[str, Any],
        call: Callable[[], Any],
    ) -> tuple[Any, bool]:
        key = self._cache_key(provider, category_plan.category, symbol, params)
        now = time.time()
        with self._lock:
            cached = self._cache.get(key)
            if cached and cached.expires_at > now:
                return copy.deepcopy(cached.data), True
            future = self._inflight.get(key)
            if future is None:
                logger.debug(
                    "ProviderCallStarted category=%s provider=%s symbol=%s cache_hit=false",
                    category_plan.category.value,
                    provider,
                    symbol,
                )
                future = self._call_pool.submit(call)
                self._inflight[key] = future
                future.add_done_callback(lambda _future, cache_key=key: self._clear_inflight(cache_key))
        try:
            data = future.result(timeout=category_plan.timeout_seconds)
        except TimeoutError as exc:
            raise ProviderTimeout(f"{provider}:{category_plan.category.value} timed out") from exc
        if self._has_sufficient_data(data):
            with self._lock:
                self._cache[key] = _CacheEntry(
                    expires_at=time.time() + category_plan.cache_ttl_seconds,
                    data=copy.deepcopy(data),
                )
        return copy.deepcopy(data), False

    def _clear_inflight(self, key: str) -> None:
        with self._lock:
            self._inflight.pop(key, None)

    def _is_circuit_open(self, provider: str, category: DataCategory) -> bool:
        key = f"{provider}:{category.value}"
        now = time.time()
        with self._lock:
            state = self._circuits.get(key)
            if not state or state.opened_at is None:
                return False
            if now - state.opened_at >= self.cooldown_seconds:
                state.opened_at = None
                state.half_open = True
                return False
            return True

    def _record_failure(self, provider: str, category: DataCategory) -> None:
        key = f"{provider}:{category.value}"
        now = time.time()
        with self._lock:
            state = self._circuits.setdefault(key, _CircuitState())
            state.failures = [ts for ts in state.failures if now - ts <= self.failure_window_seconds]
            state.failures.append(now)
            if len(state.failures) >= self.failure_threshold:
                state.opened_at = now
                state.half_open = False

    def _record_success(self, provider: str, category: DataCategory) -> None:
        key = f"{provider}:{category.value}"
        with self._lock:
            self._circuits.pop(key, None)

    @staticmethod
    def _classify_exception(exc: Exception) -> str:
        if isinstance(exc, ProviderTimeout) or isinstance(exc, TimeoutError):
            return "timeout"
        if isinstance(exc, ProviderQuotaExceeded):
            return "rate_limited"
        status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
        text = str(exc).lower()
        if status in {403, 429} or "429" in text or "quota" in text or "rate limit" in text:
            return "rate_limited"
        if status and int(status) >= 500:
            return "provider_unavailable"
        if isinstance(exc, ProviderInvalidPayload):
            return "invalid_payload"
        return "unknown_error"

    @staticmethod
    def _has_sufficient_data(data: Any) -> bool:
        if data is None:
            return False
        if isinstance(data, dict):
            return any(value not in (None, "", [], {}, "N/A", "None") for value in data.values())
        if isinstance(data, (list, tuple, set)):
            return len(data) > 0
        if isinstance(data, str):
            return bool(data.strip())
        return True

    @staticmethod
    def _cache_key(provider: str, category: DataCategory, symbol: str, params: Mapping[str, Any]) -> str:
        normalized_params = "&".join(f"{key}={params[key]}" for key in sorted(params))
        return f"{provider}:{category.value}:{str(symbol or '').strip().upper()}:{normalized_params}"


_DEFAULT_EXECUTOR: Optional[AnalysisProviderExecutor] = None
_DEFAULT_EXECUTOR_LOCK = threading.Lock()


def get_analysis_provider_executor() -> AnalysisProviderExecutor:
    global _DEFAULT_EXECUTOR
    with _DEFAULT_EXECUTOR_LOCK:
        if _DEFAULT_EXECUTOR is None:
            _DEFAULT_EXECUTOR = AnalysisProviderExecutor()
        return _DEFAULT_EXECUTOR


__all__ = [
    "AnalysisProviderExecutor",
    "AnalysisProviderPlan",
    "CategoryProviderPlan",
    "DataCategory",
    "ProviderCategoryResult",
    "ProviderInvalidPayload",
    "ProviderQuotaExceeded",
    "ProviderTimeout",
    "build_analysis_provider_plan",
    "get_analysis_provider_executor",
]
