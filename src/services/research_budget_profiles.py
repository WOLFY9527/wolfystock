# -*- coding: utf-8 -*-
"""Research mode budget profiles for quota-aware analysis planning.

This module is metadata only. It must not import provider clients, read
credentials, call networks, mutate runtime config, or affect provider order.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional


class ResearchMode(str, Enum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


@dataclass(frozen=True)
class ResearchBudgetProfile:
    mode: ResearchMode
    optional_deadline_seconds: float
    max_external_provider_calls: int
    max_news_calls: int
    max_sentiment_calls: int
    max_fundamental_calls: int
    allow_deep_news: bool
    allow_social_sentiment: bool
    allow_expensive_fundamentals: bool
    scanner_top_n_enrichment_limit: int
    cache_first_required: bool
    stale_cache_allowed: bool
    operator_description: str
    notes: tuple[str, ...] = ()

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "researchMode": self.mode.value,
            "optionalDeadlineSeconds": self.optional_deadline_seconds,
            "maxExternalProviderCalls": self.max_external_provider_calls,
            "maxNewsCalls": self.max_news_calls,
            "maxSentimentCalls": self.max_sentiment_calls,
            "maxFundamentalCalls": self.max_fundamental_calls,
            "allowDeepNews": self.allow_deep_news,
            "allowSocialSentiment": self.allow_social_sentiment,
            "allowExpensiveFundamentals": self.allow_expensive_fundamentals,
            "scannerTopNEnrichmentLimit": self.scanner_top_n_enrichment_limit,
            "cacheFirstRequired": self.cache_first_required,
            "staleCacheAllowed": self.stale_cache_allowed,
            "operatorDescription": self.operator_description,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class ProviderUsageBudgetEvent:
    """Metadata-only extension point for a future provider usage ledger."""

    category: str
    mode: ResearchMode
    event: str
    provider: Optional[str] = None
    reason: Optional[str] = None
    cache_hit: Optional[bool] = None

    def to_public_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "category": str(self.category or "").strip().lower(),
            "mode": self.mode.value,
            "event": str(self.event or "").strip().lower(),
        }
        if self.provider:
            payload["provider"] = str(self.provider).strip().lower()[:80]
        if self.reason:
            payload["reason"] = str(self.reason).strip().lower()[:80]
        if self.cache_hit is not None:
            payload["cacheHit"] = bool(self.cache_hit)
        return payload


_PROFILES: Mapping[ResearchMode, ResearchBudgetProfile] = MappingProxyType(
    {
        ResearchMode.QUICK: ResearchBudgetProfile(
            mode=ResearchMode.QUICK,
            optional_deadline_seconds=1.0,
            max_external_provider_calls=4,
            max_news_calls=0,
            max_sentiment_calls=0,
            max_fundamental_calls=1,
            allow_deep_news=False,
            allow_social_sentiment=False,
            allow_expensive_fundamentals=False,
            scanner_top_n_enrichment_limit=10,
            cache_first_required=True,
            stale_cache_allowed=True,
            operator_description="Fast interactive analysis; cache/local/yfinance-first and minimal optional enrichment.",
            notes=(
                "Optional news and social sentiment are disabled unless another layer explicitly opts in.",
                "Fundamentals stay optional and are capped to preserve scarce provider quota.",
            ),
        ),
        ResearchMode.STANDARD: ResearchBudgetProfile(
            mode=ResearchMode.STANDARD,
            optional_deadline_seconds=3.0,
            max_external_provider_calls=10,
            max_news_calls=1,
            max_sentiment_calls=1,
            max_fundamental_calls=3,
            allow_deep_news=False,
            allow_social_sentiment=True,
            allow_expensive_fundamentals=False,
            scanner_top_n_enrichment_limit=25,
            cache_first_required=True,
            stale_cache_allowed=True,
            operator_description="Balanced default research budget with limited cache-first supplemental calls.",
            notes=(
                "Designed to match the existing fast-decision supplemental deadline when explicitly selected.",
                "Optional categories remain bounded and should fail open.",
            ),
        ),
        ResearchMode.DEEP: ResearchBudgetProfile(
            mode=ResearchMode.DEEP,
            optional_deadline_seconds=5.0,
            max_external_provider_calls=12,
            max_news_calls=3,
            max_sentiment_calls=2,
            max_fundamental_calls=3,
            allow_deep_news=True,
            allow_social_sentiment=True,
            allow_expensive_fundamentals=True,
            scanner_top_n_enrichment_limit=50,
            cache_first_required=True,
            stale_cache_allowed=True,
            operator_description="Broader research pass that remains deadline-bound and quota-capped.",
            notes=(
                "This profile is not unlimited and should not create new provider call paths by itself.",
                "Use for explicit operator-requested enrichment only.",
            ),
        ),
    }
)


def normalize_research_mode(value: Any, *, strict: bool = False) -> ResearchMode:
    if isinstance(value, ResearchMode):
        return value
    normalized = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "": ResearchMode.STANDARD,
        "fast": ResearchMode.QUICK,
        "fast_decision": ResearchMode.QUICK,
        "balanced": ResearchMode.STANDARD,
        "normal": ResearchMode.STANDARD,
        "research": ResearchMode.DEEP,
        "manual": ResearchMode.DEEP,
    }
    resolved = aliases.get(normalized, normalized)
    try:
        return ResearchMode(resolved)
    except ValueError as exc:
        if strict:
            raise ValueError("unsupported research mode") from exc
        return ResearchMode.STANDARD


def get_research_budget_profile(mode: Any = ResearchMode.STANDARD) -> ResearchBudgetProfile:
    return _PROFILES[normalize_research_mode(mode)]


def describe_research_budget_profiles() -> dict[str, dict[str, Any]]:
    return {mode.value: profile.to_public_dict() for mode, profile in _PROFILES.items()}


def build_provider_usage_budget_event(
    *,
    category: str,
    mode: Any,
    event: str,
    provider: Optional[str] = None,
    reason: Optional[str] = None,
    cache_hit: Optional[bool] = None,
) -> dict[str, Any]:
    return ProviderUsageBudgetEvent(
        category=category,
        mode=normalize_research_mode(mode),
        event=event,
        provider=provider,
        reason=reason,
        cache_hit=cache_hit,
    ).to_public_dict()


__all__ = [
    "ProviderUsageBudgetEvent",
    "ResearchBudgetProfile",
    "ResearchMode",
    "build_provider_usage_budget_event",
    "describe_research_budget_profiles",
    "get_research_budget_profile",
    "normalize_research_mode",
]
