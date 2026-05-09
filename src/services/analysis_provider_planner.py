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
from src.services.llm_instrumentation import emit_provider_event, hash_label_value
from src.services.research_budget_profiles import (
    ResearchBudgetProfile,
    get_research_budget_profile,
)

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


@dataclass
class _ProviderHealth:
    provider: str
    category: DataCategory
    timeout_count: int = 0
    rate_limited_count: int = 0
    auth_error_count: int = 0
    missing_required_fields_count: int = 0
    last_failure_at: Optional[float] = None
    cooldown_until: Optional[float] = None


FAST_DECISION_TIMEOUT_SECONDS = {
    DataCategory.QUOTE: 1.2,
    DataCategory.HISTORICAL_PRICES: 2.5,
    DataCategory.TECHNICAL_INDICATORS: 2.5,
    DataCategory.FUNDAMENTALS: 2.5,
    DataCategory.EARNINGS: 2.5,
    DataCategory.NEWS: 1.5,
    DataCategory.SENTIMENT: 1.5,
}
FAST_DECISION_PLAN_DEADLINE_SECONDS = 3.0


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


def build_fast_decision_provider_plan(
    symbol: str,
    *,
    market: Optional[str] = None,
    categories: Optional[Iterable[DataCategory | str]] = None,
) -> AnalysisProviderPlan:
    plan = build_analysis_provider_plan(symbol, market=market, categories=categories)
    categories_with_fast_budget = {
        category: CategoryProviderPlan(
            category=category_plan.category,
            providers=list(category_plan.providers),
            timeout_seconds=FAST_DECISION_TIMEOUT_SECONDS.get(category, category_plan.timeout_seconds),
            cache_ttl_seconds=category_plan.cache_ttl_seconds,
            max_attempts=category_plan.max_attempts,
            required_fields=category_plan.required_fields,
        )
        for category, category_plan in plan.categories.items()
    }
    return AnalysisProviderPlan(symbol=plan.symbol, market=plan.market, categories=categories_with_fast_budget)


_FUNDAMENTAL_BUDGET_CATEGORIES = {
    DataCategory.FUNDAMENTALS,
    DataCategory.EARNINGS,
}


def _category_budget_limit(category: DataCategory, profile: ResearchBudgetProfile, current_limit: int) -> int:
    if category is DataCategory.NEWS:
        return min(current_limit, profile.max_news_calls)
    if category is DataCategory.SENTIMENT:
        return min(current_limit, profile.max_sentiment_calls)
    if category in _FUNDAMENTAL_BUDGET_CATEGORIES:
        return min(current_limit, profile.max_fundamental_calls)
    return current_limit


def _skip_reason_for_budget(category: DataCategory, profile: ResearchBudgetProfile) -> Optional[str]:
    if category is DataCategory.NEWS and profile.max_news_calls <= 0:
        return "skipped_by_budget"
    if category is DataCategory.SENTIMENT and (
        profile.max_sentiment_calls <= 0 or not profile.allow_social_sentiment
    ):
        return "skipped_by_mode"
    return None


def apply_research_budget_profile(
    plan: AnalysisProviderPlan,
    *,
    research_mode: Any = None,
    required_categories: Optional[Iterable[DataCategory | str]] = None,
) -> tuple[AnalysisProviderPlan, dict[str, Any]]:
    """Apply an explicit research-mode budget to optional categories.

    ``research_mode=None`` is intentionally a no-op to preserve legacy
    analysis behavior. Required categories are excluded from optional budgets.
    """

    if research_mode is None:
        return plan, {}

    profile = get_research_budget_profile(research_mode)
    required = {DataCategory(category) for category in (required_categories or [])}
    budgeted_categories: dict[DataCategory, CategoryProviderPlan] = {}
    skipped: list[dict[str, Any]] = []
    usage_events: list[dict[str, Any]] = []
    remaining_external_calls = max(0, int(profile.max_external_provider_calls))

    for category, category_plan in plan.categories.items():
        if category in required:
            budgeted_categories[category] = category_plan
            continue

        skip_reason = _skip_reason_for_budget(category, profile)
        if skip_reason:
            skipped.append({"category": category.value, "reason": skip_reason})
            usage_events.append(
                {
                    "category": category.value,
                    "mode": profile.mode.value,
                    "event": skip_reason,
                    "reason": skip_reason,
                }
            )
            continue

        category_limit = _category_budget_limit(category, profile, category_plan.max_attempts)
        allowed_attempts = min(category_limit, remaining_external_calls)
        if allowed_attempts <= 0:
            skipped.append({"category": category.value, "reason": "external_call_budget_exhausted"})
            usage_events.append(
                {
                    "category": category.value,
                    "mode": profile.mode.value,
                    "event": "skipped_by_budget",
                    "reason": "external_call_budget_exhausted",
                }
            )
            continue

        remaining_external_calls -= allowed_attempts
        budgeted_categories[category] = CategoryProviderPlan(
            category=category_plan.category,
            providers=list(category_plan.providers),
            timeout_seconds=min(category_plan.timeout_seconds, profile.optional_deadline_seconds),
            cache_ttl_seconds=category_plan.cache_ttl_seconds,
            max_attempts=allowed_attempts,
            required_fields=category_plan.required_fields,
        )

    metadata = {
        "researchMode": profile.mode.value,
        "optionalDeadlineSeconds": profile.optional_deadline_seconds,
        "cacheFirstRequired": profile.cache_first_required,
        "staleCacheAllowed": profile.stale_cache_allowed,
        "skippedByBudget": skipped,
        "budgetSkippedCategories": [item["category"] for item in skipped],
        "externalCallBudget": {
            "max": profile.max_external_provider_calls,
            "remainingAfterPlan": remaining_external_calls,
            "requiredCategoriesExcluded": sorted(category.value for category in required),
        },
        "usageLedgerHints": usage_events,
    }
    return AnalysisProviderPlan(symbol=plan.symbol, market=plan.market, categories=budgeted_categories), metadata


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
        self._health: dict[str, _ProviderHealth] = {}
        self._lock = threading.RLock()
        self._call_pool = ThreadPoolExecutor(max_workers=16, thread_name_prefix="provider_call_")

    def execute_plan(
        self,
        plan: AnalysisProviderPlan,
        *,
        symbol: str,
        providers_by_category: Mapping[DataCategory, Mapping[str, Callable[[], Any]]],
        max_workers: int = 4,
        deadline_seconds: Optional[float] = None,
        required_categories: Optional[Iterable[DataCategory | str]] = None,
    ) -> dict[DataCategory, ProviderCategoryResult]:
        results: dict[DataCategory, ProviderCategoryResult] = {}
        required = {DataCategory(category) for category in (required_categories or [])}
        deadline_at = time.monotonic() + deadline_seconds if deadline_seconds and deadline_seconds > 0 else None
        with ThreadPoolExecutor(max_workers=max(1, max_workers), thread_name_prefix="provider_category_") as pool:
            future_map = {
                pool.submit(
                    self.execute_category,
                    category_plan,
                    symbol=symbol,
                    providers=providers_by_category.get(category, {}),
                    deadline_at=None if category in required else deadline_at,
                ): category
                for category, category_plan in plan.categories.items()
                if category in providers_by_category
            }
            for future in as_completed(future_map):
                category = future_map[future]
                results[category] = future.result()
        return results

    @staticmethod
    def _deadline_exceeded_result(category_plan: CategoryProviderPlan) -> ProviderCategoryResult:
        return ProviderCategoryResult(
            category=category_plan.category,
            source_provider=None,
            data=None,
            source_category=category_plan.category.value,
            warnings=["analysis_deadline_exceeded"],
            attempts=[
                {
                    "provider": category_plan.primary,
                    "status": "failed",
                    "reason": "analysis_deadline_exceeded",
                }
            ],
            partial=True,
        )

    def execute_category(
        self,
        category_plan: CategoryProviderPlan,
        *,
        symbol: str,
        providers: Mapping[str, Callable[[], Any]],
        params: Optional[Mapping[str, Any]] = None,
        sufficient: Optional[Callable[[Any], bool]] = None,
        deadline_at: Optional[float] = None,
    ) -> ProviderCategoryResult:
        sufficient = sufficient or self._has_sufficient_data
        warnings: list[str] = []
        attempts: list[dict[str, Any]] = []
        available = [provider for provider in category_plan.providers if provider in providers]
        attempted_providers = available[: category_plan.max_attempts]
        for index, provider in enumerate(attempted_providers):
            provider_timeout = category_plan.timeout_seconds
            if deadline_at is not None:
                remaining = deadline_at - time.monotonic()
                if remaining <= 0:
                    return self._deadline_exceeded_result(category_plan)
                provider_timeout = min(provider_timeout, remaining)
            if self._is_circuit_open(provider, category_plan.category):
                attempts.append({"provider": provider, "status": "skipped", "reason": "circuit_open"})
                warnings.append(f"{provider}: circuit_open")
                logger.warning(
                    "ProviderCircuitOpened category=%s provider=%s circuit_state=open",
                    category_plan.category.value,
                    provider,
                )
                self._emit_provider_fallback_attempt(
                    provider=provider,
                    category_plan=category_plan,
                    symbol=symbol,
                    attempt_index=index,
                    retry_reason="circuit_open",
                    has_next=index + 1 < len(attempted_providers),
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
                    timeout_seconds=provider_timeout,
                )
                duration_ms = int((time.monotonic() - started) * 1000)
                if not sufficient(data):
                    self._record_failure(provider, category_plan.category, "missing_required_fields")
                    self._emit_provider_event(
                        "provider_insufficient_payload",
                        provider=provider,
                        category_plan=category_plan,
                        symbol=symbol,
                        attempt_index=index,
                        fallback_depth=index,
                        duration_ms=duration_ms,
                        outcome="failed",
                        error_bucket="insufficient_payload",
                    )
                    self._emit_provider_event(
                        "provider_call_failed",
                        provider=provider,
                        category_plan=category_plan,
                        symbol=symbol,
                        attempt_index=index,
                        fallback_depth=index,
                        duration_ms=duration_ms,
                        outcome="failed",
                        error_bucket="insufficient_payload",
                    )
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
                    self._emit_provider_fallback_attempt(
                        provider=provider,
                        category_plan=category_plan,
                        symbol=symbol,
                        attempt_index=index,
                        retry_reason="insufficient_payload",
                        has_next=index + 1 < len(attempted_providers),
                    )
                    continue
                self._record_success(provider, category_plan.category)
                if not cache_hit:
                    self._emit_provider_event(
                        "provider_call_completed",
                        provider=provider,
                        category_plan=category_plan,
                        symbol=symbol,
                        attempt_index=index,
                        fallback_depth=index,
                        duration_ms=duration_ms,
                        outcome="success",
                    )
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
                if reason == "timeout" and deadline_at is not None and time.monotonic() >= deadline_at:
                    reason = "analysis_deadline_exceeded"
                if reason != "analysis_deadline_exceeded":
                    self._record_failure(provider, category_plan.category, reason)
                self._emit_provider_event(
                    "provider_call_failed",
                    provider=provider,
                    category_plan=category_plan,
                    symbol=symbol,
                    attempt_index=index,
                    fallback_depth=index,
                    duration_ms=duration_ms,
                    outcome="failed",
                    error_bucket=reason,
                )
                if reason == "timeout":
                    self._emit_provider_event(
                        "provider_timeout",
                        provider=provider,
                        category_plan=category_plan,
                        symbol=symbol,
                        attempt_index=index,
                        fallback_depth=index,
                        duration_ms=duration_ms,
                        outcome="failed",
                        error_bucket=reason,
                    )
                if reason == "rate_limited":
                    self._emit_provider_event(
                        "provider_quota_risk_observed",
                        provider=provider,
                        category_plan=category_plan,
                        symbol=symbol,
                        attempt_index=index,
                        fallback_depth=index,
                        duration_ms=duration_ms,
                        outcome="failed",
                        error_bucket=reason,
                    )
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
                if reason == "analysis_deadline_exceeded":
                    break
                self._emit_provider_fallback_attempt(
                    provider=provider,
                    category_plan=category_plan,
                    symbol=symbol,
                    attempt_index=index,
                    retry_reason=reason,
                    has_next=index + 1 < len(attempted_providers),
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
        timeout_seconds: Optional[float] = None,
    ) -> tuple[Any, bool]:
        key = self._cache_key(provider, category_plan.category, symbol, params)
        cache_key_hash = hash_label_value(key)
        now = time.time()
        cache_hit_data: Optional[Any] = None
        emit_cache_hit = False
        emit_cache_miss = False
        emit_duplicate_candidate = False
        emit_inflight_join = False
        emit_call_started = False
        with self._lock:
            cached = self._cache.get(key)
            if cached and cached.expires_at > now:
                cache_hit_data = copy.deepcopy(cached.data)
                emit_cache_hit = True
            else:
                emit_cache_miss = True
                emit_duplicate_candidate = True
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
                    emit_call_started = True
                else:
                    emit_inflight_join = True
        if emit_cache_hit and cache_hit_data is not None:
            self._emit_provider_event(
                "provider_cache_hit",
                provider=provider,
                category_plan=category_plan,
                symbol=symbol,
                cache_key_hash=cache_key_hash,
                outcome="cache_hit",
            )
            return cache_hit_data, True
        if emit_cache_miss:
            self._emit_provider_event(
                "provider_cache_miss",
                provider=provider,
                category_plan=category_plan,
                symbol=symbol,
                cache_key_hash=cache_key_hash,
                outcome="cache_miss",
            )
        if emit_duplicate_candidate:
            self._emit_provider_event(
                "provider_duplicate_candidate_observed",
                provider=provider,
                category_plan=category_plan,
                symbol=symbol,
                cache_key_hash=cache_key_hash,
                outcome="observed",
            )
        if emit_inflight_join:
            self._emit_provider_event(
                "provider_inflight_join",
                provider=provider,
                category_plan=category_plan,
                symbol=symbol,
                cache_key_hash=cache_key_hash,
                outcome="inflight_join",
            )
        if emit_call_started:
            self._emit_provider_event(
                "provider_call_started",
                provider=provider,
                category_plan=category_plan,
                symbol=symbol,
                cache_key_hash=cache_key_hash,
                outcome="started",
            )
        try:
            data = future.result(timeout=timeout_seconds or category_plan.timeout_seconds)
        except TimeoutError as exc:
            raise ProviderTimeout(f"{provider}:{category_plan.category.value} timed out") from exc
        if self._has_sufficient_data(data):
            with self._lock:
                self._cache[key] = _CacheEntry(
                    expires_at=time.time() + category_plan.cache_ttl_seconds,
                    data=copy.deepcopy(data),
                )
        return copy.deepcopy(data), False

    def _emit_provider_event(
        self,
        event_name: str,
        *,
        provider: str,
        category_plan: CategoryProviderPlan,
        symbol: str,
        attempt_index: Optional[int] = None,
        fallback_depth: Optional[int] = None,
        duration_ms: Optional[int] = None,
        outcome: Optional[str] = None,
        error_bucket: Optional[str] = None,
        retry_reason: Optional[str] = None,
        cache_key_hash: Optional[str] = None,
    ) -> None:
        emit_provider_event(
            event_name,
            provider=provider,
            provider_category=category_plan.category.value,
            market=_normalize_market(symbol, None),
            endpoint_family="analysis_provider_executor",
            attempt_index=attempt_index,
            fallback_depth=fallback_depth,
            duration_bucket=duration_ms,
            outcome=outcome,
            error_bucket=error_bucket,
            retry_reason_bucket=retry_reason,
            cache_key_hash=cache_key_hash,
        )

    def _emit_provider_fallback_attempt(
        self,
        *,
        provider: str,
        category_plan: CategoryProviderPlan,
        symbol: str,
        attempt_index: int,
        retry_reason: str,
        has_next: bool,
    ) -> None:
        if not has_next:
            return
        self._emit_provider_event(
            "provider_fallback_attempt",
            provider=provider,
            category_plan=category_plan,
            symbol=symbol,
            attempt_index=attempt_index,
            fallback_depth=attempt_index + 1,
            outcome="fallback",
            retry_reason=retry_reason,
        )

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

    def _record_failure(self, provider: str, category: DataCategory, reason: str = "unknown_error") -> None:
        key = f"{provider}:{category.value}"
        now = time.time()
        with self._lock:
            state = self._circuits.setdefault(key, _CircuitState())
            state.failures = [ts for ts in state.failures if now - ts <= self.failure_window_seconds]
            state.failures.append(now)
            health = self._health.setdefault(key, _ProviderHealth(provider=provider, category=category))
            health.last_failure_at = now
            if reason == "timeout":
                health.timeout_count += 1
            elif reason == "rate_limited":
                health.rate_limited_count += 1
            elif reason == "auth_error":
                health.auth_error_count += 1
            elif reason in {"missing_required_fields", "invalid_payload", "insufficient_payload"}:
                health.missing_required_fields_count += 1
            if len(state.failures) >= self.failure_threshold:
                state.opened_at = now
                state.half_open = False
                health.cooldown_until = now + self.cooldown_seconds

    def _record_success(self, provider: str, category: DataCategory) -> None:
        key = f"{provider}:{category.value}"
        with self._lock:
            self._circuits.pop(key, None)
            self._health.pop(key, None)

    @staticmethod
    def _classify_exception(exc: Exception) -> str:
        if isinstance(exc, ProviderTimeout) or isinstance(exc, TimeoutError):
            return "timeout"
        if isinstance(exc, ProviderQuotaExceeded):
            return "rate_limited"
        status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
        text = str(exc).lower()
        if status == 403 or "forbidden" in text or "unauthorized" in text or "auth" in text:
            return "auth_error"
        if status == 429 or "429" in text or "quota" in text or "rate limit" in text:
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

    def hot_path_health_snapshot(self) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            provider_timeouts: list[str] = []
            provider_cooldowns: list[str] = []
            counters: dict[str, dict[str, Any]] = {}
            for key, health in self._health.items():
                label = f"{health.provider}:{health.category.value}"
                if health.timeout_count:
                    provider_timeouts.append(label)
                if health.cooldown_until and health.cooldown_until > now:
                    provider_cooldowns.append(label)
                counters[key] = {
                    "provider": health.provider,
                    "category": health.category.value,
                    "timeout_count": health.timeout_count,
                    "rate_limited_count": health.rate_limited_count,
                    "auth_error_count": health.auth_error_count,
                    "missing_required_fields_count": health.missing_required_fields_count,
                    "last_failure_at": health.last_failure_at,
                    "cooldown_until": health.cooldown_until,
                }
            return {
                "provider_timeouts": provider_timeouts,
                "provider_cooldowns": provider_cooldowns,
                "counters": counters,
            }


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
    "apply_research_budget_profile",
    "build_analysis_provider_plan",
    "build_fast_decision_provider_plan",
    "get_analysis_provider_executor",
]
