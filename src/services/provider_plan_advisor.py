# -*- coding: utf-8 -*-
"""Inert cache-first provider planning helpers.

This module is advisory metadata only. It does not import provider clients,
read credentials, call networks, or mutate runtime planner/executor behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.services.provider_capability_matrix import (
    BacktestUsage,
    FreshnessClass,
    ProviderCapability,
    ProviderDomain,
    ProviderMarket,
    ProviderQuotaClass,
    ScannerUsage,
    list_provider_capabilities,
)


class ProviderPlanMode(str):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"
    SCANNER = "scanner"
    BACKTEST = "backtest"


_VALID_MODES = {
    ProviderPlanMode.QUICK,
    ProviderPlanMode.STANDARD,
    ProviderPlanMode.DEEP,
    ProviderPlanMode.SCANNER,
    ProviderPlanMode.BACKTEST,
}


@dataclass(frozen=True)
class AdvisoryProviderCandidate:
    provider_id: str
    display_name: str
    domain: str
    market: str
    mode: str
    priority: int
    quota_class: str
    freshness_class: str
    scanner_usage: str
    backtest_usage: str
    live_provider: bool
    advisory_only: bool = True
    manual_review_required: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "providerId": self.provider_id,
            "displayName": self.display_name,
            "domain": self.domain,
            "market": self.market,
            "mode": self.mode,
            "priority": self.priority,
            "quotaClass": self.quota_class,
            "freshnessClass": self.freshness_class,
            "scannerUsage": self.scanner_usage,
            "backtestUsage": self.backtest_usage,
            "liveProvider": self.live_provider,
            "advisoryOnly": self.advisory_only,
            "manualReviewRequired": self.manual_review_required,
        }


def _normalize_domain(domain: ProviderDomain | str) -> ProviderDomain:
    if isinstance(domain, ProviderDomain):
        return domain
    return ProviderDomain(str(domain or "").strip().lower())


def _normalize_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower().replace("-", "_")
    aliases = {
        "fast": ProviderPlanMode.QUICK,
        "fast_decision": ProviderPlanMode.QUICK,
        "manual": ProviderPlanMode.DEEP,
        "research": ProviderPlanMode.DEEP,
    }
    resolved = aliases.get(normalized, normalized)
    if resolved not in _VALID_MODES:
        raise ValueError(f"unsupported provider plan mode: {mode}")
    return resolved


def _normalize_market(market: ProviderMarket | str) -> ProviderMarket:
    if isinstance(market, ProviderMarket):
        return market
    normalized = str(market or "").strip()
    upper = normalized.upper()
    if upper in {"US", "CN", "HK"}:
        return ProviderMarket(upper)
    lower = normalized.lower()
    if lower in {"crypto", "forex", "global", "unknown"}:
        return ProviderMarket(lower)
    return ProviderMarket.UNKNOWN


def _market_matches(capability: ProviderCapability, market: ProviderMarket) -> bool:
    if ProviderMarket.GLOBAL in capability.markets:
        return True
    return market in capability.markets


def _mode_allows(capability: ProviderCapability, mode: str) -> bool:
    if mode == ProviderPlanMode.SCANNER:
        return capability.scanner_allowed and capability.scanner_usage is ScannerUsage.LOCAL_ONLY
    if mode == ProviderPlanMode.BACKTEST:
        return capability.backtest_allowed and capability.backtest_usage is BacktestUsage.LOCAL_ONLY
    if mode == ProviderPlanMode.QUICK:
        return capability.quick_analysis_allowed
    if mode == ProviderPlanMode.STANDARD:
        return capability.standard_analysis_allowed
    return capability.deep_research_allowed


def _candidate_for(
    capability: ProviderCapability,
    *,
    domain: ProviderDomain,
    market: ProviderMarket,
    mode: str,
) -> AdvisoryProviderCandidate:
    quota_class = capability.quota_class.value
    freshness_class = capability.freshness_class.value
    return AdvisoryProviderCandidate(
        provider_id=capability.provider_id,
        display_name=capability.display_name,
        domain=domain.value,
        market=market.value,
        mode=mode,
        priority=capability.default_priority_by_domain.get(domain.value, 999),
        quota_class=quota_class,
        freshness_class=freshness_class,
        scanner_usage=capability.scanner_usage.value,
        backtest_usage=capability.backtest_usage.value,
        live_provider=quota_class != ProviderQuotaClass.LOCAL.value,
        manual_review_required=freshness_class == FreshnessClass.MANUAL_REVIEW.value,
    )


def plan_provider_candidates(
    domain: ProviderDomain | str,
    *,
    market: ProviderMarket | str = ProviderMarket.US,
    mode: str = ProviderPlanMode.STANDARD,
) -> tuple[AdvisoryProviderCandidate, ...]:
    """Return advisory provider candidates for a domain/market/mode.

    The returned order is metadata-only and must not be used as runtime
    provider execution order without a separate Phase 3 approval.
    """

    resolved_domain = _normalize_domain(domain)
    resolved_market = _normalize_market(market)
    resolved_mode = _normalize_mode(mode)
    candidates = [
        _candidate_for(capability, domain=resolved_domain, market=resolved_market, mode=resolved_mode)
        for capability in list_provider_capabilities()
        if resolved_domain in capability.domains
        and _market_matches(capability, resolved_market)
        and _mode_allows(capability, resolved_mode)
    ]
    return tuple(sorted(candidates, key=lambda item: (item.priority, item.quota_class != "local", item.provider_id)))


def plan_cache_first_candidates(
    domain: ProviderDomain | str,
    *,
    market: ProviderMarket | str = ProviderMarket.US,
    mode: str = ProviderPlanMode.STANDARD,
) -> tuple[AdvisoryProviderCandidate, ...]:
    """Alias for advisory cache-first provider candidates."""

    return plan_provider_candidates(domain, market=market, mode=mode)


def describe_provider_plan(
    domain: ProviderDomain | str,
    *,
    market: ProviderMarket | str = ProviderMarket.US,
    mode: str = ProviderPlanMode.STANDARD,
) -> dict[str, Any]:
    """Return a JSON-serializable advisory plan description."""

    candidates = plan_provider_candidates(domain, market=market, mode=mode)
    resolved_domain = _normalize_domain(domain)
    resolved_market = _normalize_market(market)
    resolved_mode = _normalize_mode(mode)
    return {
        "domain": resolved_domain.value,
        "market": resolved_market.value,
        "mode": resolved_mode,
        "advisoryOnly": True,
        "runtimeBehaviorChanged": False,
        "networkCallsEnabled": False,
        "candidates": [candidate.as_dict() for candidate in candidates],
    }


__all__ = [
    "AdvisoryProviderCandidate",
    "ProviderPlanMode",
    "describe_provider_plan",
    "plan_cache_first_candidates",
    "plan_provider_candidates",
]
