# -*- coding: utf-8 -*-
"""Pure Market Intelligence source-tier and trust gate contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence


MARKET_INTELLIGENCE_TRUST_GATE_VERSION = "market_intelligence_trust_gate_v1"


class MarketIntelligenceSourceTier(str, Enum):
    OFFICIAL_PUBLIC = "official_public"
    EXCHANGE_PUBLIC = "exchange_public"
    BROKER_AUTHORIZED = "broker_authorized"
    UNOFFICIAL_PUBLIC_API = "unofficial_public_api"
    PUBLIC_WEB_FALLBACK = "public_web_fallback"
    SNAPSHOT = "snapshot"
    STATIC_FALLBACK = "static_fallback"
    SYNTHETIC = "synthetic"
    UNAVAILABLE = "unavailable"


class MarketIntelligenceTrustLevel(str, Enum):
    RELIABLE = "reliable"
    USABLE_WITH_CAUTION = "usable_with_caution"
    WEAK = "weak"
    UNAVAILABLE = "unavailable"


_RELIABLE_CAPABLE_TIERS = {
    MarketIntelligenceSourceTier.OFFICIAL_PUBLIC,
    MarketIntelligenceSourceTier.EXCHANGE_PUBLIC,
    MarketIntelligenceSourceTier.BROKER_AUTHORIZED,
    MarketIntelligenceSourceTier.UNOFFICIAL_PUBLIC_API,
}
_WEAK_TIERS = {
    MarketIntelligenceSourceTier.PUBLIC_WEB_FALLBACK,
    MarketIntelligenceSourceTier.STATIC_FALLBACK,
    MarketIntelligenceSourceTier.SYNTHETIC,
}
_SOURCE_TYPE_TO_TIER = {
    "official_api": MarketIntelligenceSourceTier.OFFICIAL_PUBLIC,
    "official_public": MarketIntelligenceSourceTier.OFFICIAL_PUBLIC,
    "exchange_public": MarketIntelligenceSourceTier.EXCHANGE_PUBLIC,
    "broker_authorized": MarketIntelligenceSourceTier.BROKER_AUTHORIZED,
    "public": MarketIntelligenceSourceTier.UNOFFICIAL_PUBLIC_API,
    "public_api": MarketIntelligenceSourceTier.UNOFFICIAL_PUBLIC_API,
    "public_proxy": MarketIntelligenceSourceTier.UNOFFICIAL_PUBLIC_API,
    "proxy_public": MarketIntelligenceSourceTier.UNOFFICIAL_PUBLIC_API,
    "unofficial_proxy": MarketIntelligenceSourceTier.UNOFFICIAL_PUBLIC_API,
    "unofficial_public_api": MarketIntelligenceSourceTier.UNOFFICIAL_PUBLIC_API,
    "computed_from_real": MarketIntelligenceSourceTier.UNOFFICIAL_PUBLIC_API,
    "public_web_fallback": MarketIntelligenceSourceTier.PUBLIC_WEB_FALLBACK,
    "cache": MarketIntelligenceSourceTier.SNAPSHOT,
    "cache_snapshot": MarketIntelligenceSourceTier.SNAPSHOT,
    "cached": MarketIntelligenceSourceTier.SNAPSHOT,
    "snapshot": MarketIntelligenceSourceTier.SNAPSHOT,
    "fallback": MarketIntelligenceSourceTier.STATIC_FALLBACK,
    "fallback_static": MarketIntelligenceSourceTier.STATIC_FALLBACK,
    "static_fallback": MarketIntelligenceSourceTier.STATIC_FALLBACK,
    "synthetic": MarketIntelligenceSourceTier.SYNTHETIC,
    "synthetic_fixture": MarketIntelligenceSourceTier.SYNTHETIC,
    "mock": MarketIntelligenceSourceTier.SYNTHETIC,
    "fixture": MarketIntelligenceSourceTier.SYNTHETIC,
    "unit_fixture": MarketIntelligenceSourceTier.SYNTHETIC,
    "delayed_fixture": MarketIntelligenceSourceTier.PUBLIC_WEB_FALLBACK,
    "disabled_live_stub": MarketIntelligenceSourceTier.UNAVAILABLE,
    "malformed_fixture": MarketIntelligenceSourceTier.UNAVAILABLE,
    "missing": MarketIntelligenceSourceTier.UNAVAILABLE,
    "unavailable": MarketIntelligenceSourceTier.UNAVAILABLE,
}
_SOURCE_TO_TIER = {
    "fred": MarketIntelligenceSourceTier.OFFICIAL_PUBLIC,
    "treasury": MarketIntelligenceSourceTier.OFFICIAL_PUBLIC,
    "tusharefetcher": MarketIntelligenceSourceTier.OFFICIAL_PUBLIC,
    "eastmoney": MarketIntelligenceSourceTier.OFFICIAL_PUBLIC,
    "cnn": MarketIntelligenceSourceTier.OFFICIAL_PUBLIC,
    "alternative": MarketIntelligenceSourceTier.OFFICIAL_PUBLIC,
    "alternative_me": MarketIntelligenceSourceTier.OFFICIAL_PUBLIC,
    "alpaca": MarketIntelligenceSourceTier.BROKER_AUTHORIZED,
    "binance": MarketIntelligenceSourceTier.EXCHANGE_PUBLIC,
    "binance_ws": MarketIntelligenceSourceTier.EXCHANGE_PUBLIC,
    "sina": MarketIntelligenceSourceTier.UNOFFICIAL_PUBLIC_API,
    "tickflow": MarketIntelligenceSourceTier.UNOFFICIAL_PUBLIC_API,
    "yahoo": MarketIntelligenceSourceTier.UNOFFICIAL_PUBLIC_API,
    "yfinance": MarketIntelligenceSourceTier.UNOFFICIAL_PUBLIC_API,
    "yfinance_proxy": MarketIntelligenceSourceTier.UNOFFICIAL_PUBLIC_API,
    "computed": MarketIntelligenceSourceTier.UNOFFICIAL_PUBLIC_API,
    "cache": MarketIntelligenceSourceTier.SNAPSHOT,
    "cached": MarketIntelligenceSourceTier.SNAPSHOT,
    "snapshot": MarketIntelligenceSourceTier.SNAPSHOT,
    "local_db": MarketIntelligenceSourceTier.SNAPSHOT,
    "fallback": MarketIntelligenceSourceTier.STATIC_FALLBACK,
    "mock": MarketIntelligenceSourceTier.SYNTHETIC,
    "synthetic": MarketIntelligenceSourceTier.SYNTHETIC,
    "synthetic_fixture": MarketIntelligenceSourceTier.SYNTHETIC,
    "unit_fixture": MarketIntelligenceSourceTier.SYNTHETIC,
    "unavailable": MarketIntelligenceSourceTier.UNAVAILABLE,
    "missing": MarketIntelligenceSourceTier.UNAVAILABLE,
}
_TIER_SCORE_CAP = {
    MarketIntelligenceSourceTier.OFFICIAL_PUBLIC: 1.0,
    MarketIntelligenceSourceTier.EXCHANGE_PUBLIC: 1.0,
    MarketIntelligenceSourceTier.BROKER_AUTHORIZED: 1.0,
    MarketIntelligenceSourceTier.UNOFFICIAL_PUBLIC_API: 0.9,
    MarketIntelligenceSourceTier.SNAPSHOT: 0.7,
    MarketIntelligenceSourceTier.PUBLIC_WEB_FALLBACK: 0.5,
    MarketIntelligenceSourceTier.STATIC_FALLBACK: 0.4,
    MarketIntelligenceSourceTier.SYNTHETIC: 0.2,
    MarketIntelligenceSourceTier.UNAVAILABLE: 0.0,
}
_TIER_RANK = {
    MarketIntelligenceSourceTier.OFFICIAL_PUBLIC: 0,
    MarketIntelligenceSourceTier.EXCHANGE_PUBLIC: 0,
    MarketIntelligenceSourceTier.BROKER_AUTHORIZED: 0,
    MarketIntelligenceSourceTier.UNOFFICIAL_PUBLIC_API: 1,
    MarketIntelligenceSourceTier.SNAPSHOT: 2,
    MarketIntelligenceSourceTier.PUBLIC_WEB_FALLBACK: 3,
    MarketIntelligenceSourceTier.STATIC_FALLBACK: 4,
    MarketIntelligenceSourceTier.SYNTHETIC: 5,
    MarketIntelligenceSourceTier.UNAVAILABLE: 6,
}
_FRESHNESS_RANK = {
    "fresh": 0,
    "live": 0,
    "delayed": 1,
    "cached": 2,
    "partial": 3,
    "stale": 4,
    "fallback": 5,
    "synthetic": 6,
    "mock": 6,
    "error": 7,
    "unavailable": 7,
    "unknown": 8,
}


@dataclass(frozen=True, slots=True)
class MarketIntelligenceTrustResult:
    is_reliable: bool
    trust_level: MarketIntelligenceTrustLevel
    coverage: float
    source_tier: MarketIntelligenceSourceTier
    freshness: str
    degradation_reasons: tuple[str, ...]
    score_cap: float
    conclusion_allowed: bool
    warning: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "isReliable": self.is_reliable,
            "trustLevel": self.trust_level.value,
            "coverage": self.coverage,
            "sourceTier": self.source_tier.value,
            "freshness": self.freshness,
            "degradationReasons": list(self.degradation_reasons),
            "scoreCap": self.score_cap,
            "conclusionAllowed": self.conclusion_allowed,
            "warning": self.warning,
        }


def resolve_market_intelligence_source_tier(
    *,
    source: Any = None,
    source_type: Any = None,
    source_tier: Any = None,
    freshness: Any = None,
    is_fallback: bool = False,
    is_synthetic: bool = False,
    is_unavailable: bool = False,
    is_from_snapshot: bool = False,
) -> MarketIntelligenceSourceTier:
    """Return the source tier used by the Market Intelligence trust gate."""

    if is_unavailable:
        return MarketIntelligenceSourceTier.UNAVAILABLE
    if is_synthetic:
        return MarketIntelligenceSourceTier.SYNTHETIC
    if is_fallback:
        return MarketIntelligenceSourceTier.STATIC_FALLBACK
    if is_from_snapshot:
        return MarketIntelligenceSourceTier.SNAPSHOT

    explicit_tier = _coerce_source_tier(source_tier)
    if explicit_tier is not None:
        return explicit_tier

    normalized_freshness = _text(freshness).lower()
    if normalized_freshness in {"unavailable", "error"}:
        return MarketIntelligenceSourceTier.UNAVAILABLE
    if normalized_freshness in {"synthetic", "mock", "synthetic_delayed"}:
        return MarketIntelligenceSourceTier.SYNTHETIC
    if normalized_freshness == "fallback":
        return MarketIntelligenceSourceTier.STATIC_FALLBACK

    normalized_type = _text(source_type).lower()
    if normalized_type in _SOURCE_TYPE_TO_TIER:
        return _SOURCE_TYPE_TO_TIER[normalized_type]

    normalized_source = _text(source).lower()
    if normalized_source in _SOURCE_TO_TIER:
        return _SOURCE_TO_TIER[normalized_source]
    if "synthetic" in normalized_source or "mock" in normalized_source:
        return MarketIntelligenceSourceTier.SYNTHETIC
    if "fallback" in normalized_source or "static" in normalized_source:
        return MarketIntelligenceSourceTier.STATIC_FALLBACK
    if "snapshot" in normalized_source or "cache" in normalized_source:
        return MarketIntelligenceSourceTier.SNAPSHOT
    if normalized_source or normalized_type:
        return MarketIntelligenceSourceTier.UNOFFICIAL_PUBLIC_API
    return MarketIntelligenceSourceTier.UNAVAILABLE


def evaluate_market_intelligence_trust(
    value: Mapping[str, Any] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    """Evaluate source tier, freshness, coverage, and conclusion eligibility."""

    payload = {**dict(value or {}), **overrides}
    is_unavailable = _bool(_get(payload, "is_unavailable", "isUnavailable"))
    is_synthetic = _bool(_get(payload, "is_synthetic", "isSynthetic"))
    is_fallback = _bool(_get(payload, "is_fallback", "isFallback", "fallbackUsed", "fallback_used"))
    is_stale = _bool(_get(payload, "is_stale", "isStale"))
    is_partial = _bool(_get(payload, "is_partial", "isPartial"))
    source_tier = resolve_market_intelligence_source_tier(
        source=_get(payload, "source"),
        source_type=_get(payload, "source_type", "sourceType"),
        source_tier=_get(payload, "source_tier", "sourceTier"),
        freshness=_get(payload, "freshness"),
        is_fallback=is_fallback,
        is_synthetic=is_synthetic,
        is_unavailable=is_unavailable,
        is_from_snapshot=_bool(_get(payload, "is_from_snapshot", "isFromSnapshot")),
    )
    if source_tier is MarketIntelligenceSourceTier.UNAVAILABLE:
        is_unavailable = True
    if source_tier is MarketIntelligenceSourceTier.SYNTHETIC:
        is_synthetic = True
    if source_tier is MarketIntelligenceSourceTier.STATIC_FALLBACK:
        is_fallback = True

    freshness = _normalized_freshness(
        _get(payload, "freshness"),
        source_tier=source_tier,
        is_fallback=is_fallback,
        is_stale=is_stale,
        is_partial=is_partial,
        is_synthetic=is_synthetic,
        is_unavailable=is_unavailable,
    )
    coverage = 0.0 if is_unavailable else _bounded_float(_get(payload, "coverage"), default=1.0)
    reasons = _ordered_reasons(_reasons_from_payload(payload))
    score_cap = _TIER_SCORE_CAP[source_tier]

    if source_tier is MarketIntelligenceSourceTier.UNAVAILABLE:
        reasons = _append_reason(reasons, "unavailable_source")
    elif source_tier is MarketIntelligenceSourceTier.SYNTHETIC:
        reasons = _append_reason(reasons, "synthetic_source")
    elif source_tier is MarketIntelligenceSourceTier.STATIC_FALLBACK:
        reasons = _append_reason(reasons, "static_fallback_source")
    elif source_tier is MarketIntelligenceSourceTier.PUBLIC_WEB_FALLBACK:
        reasons = _append_reason(reasons, "public_web_fallback_source")
    elif source_tier is MarketIntelligenceSourceTier.SNAPSHOT:
        reasons = _append_reason(reasons, "snapshot_source")

    if is_unavailable or freshness in {"unavailable", "error"}:
        coverage = 0.0
        score_cap = 0.0
        reasons = _append_reason(reasons, "unavailable_source")
    elif is_synthetic or freshness in {"synthetic", "mock"}:
        score_cap = min(score_cap, 0.2)
        reasons = _append_reason(reasons, "synthetic_source")
    elif is_fallback or freshness == "fallback":
        score_cap = min(score_cap, 0.4)
        reasons = _append_reason(reasons, "fallback_source")
    elif is_stale or freshness == "stale":
        score_cap = min(score_cap, 0.6)
        reasons = _append_reason(reasons, "stale_source")
    elif is_partial or freshness == "partial":
        score_cap = min(score_cap, 0.7)
        reasons = _append_reason(reasons, "partial_coverage")

    if coverage <= 0.0:
        score_cap = 0.0
        reasons = _append_reason(reasons, "no_coverage")
    elif coverage < 0.5:
        score_cap = min(score_cap, 0.4)
        reasons = _append_reason(reasons, "low_coverage")
    elif coverage < 0.8:
        score_cap = min(score_cap, 0.7)
        reasons = _append_reason(reasons, "partial_coverage")

    confidence_weight = _optional_bounded_float(_get(payload, "confidence_weight", "confidenceWeight"))
    if confidence_weight is not None:
        score_cap = min(score_cap, confidence_weight)

    score_cap = round(score_cap, 2)
    trust_level = _trust_level(source_tier=source_tier, score_cap=score_cap, reasons=reasons)
    result = MarketIntelligenceTrustResult(
        is_reliable=trust_level is MarketIntelligenceTrustLevel.RELIABLE,
        trust_level=trust_level,
        coverage=round(coverage, 2),
        source_tier=source_tier,
        freshness=freshness,
        degradation_reasons=reasons,
        score_cap=score_cap,
        conclusion_allowed=trust_level
        in {MarketIntelligenceTrustLevel.RELIABLE, MarketIntelligenceTrustLevel.USABLE_WITH_CAUTION},
        warning=_warning_for(trust_level, reasons),
    )
    return result.to_dict()


def evaluate_market_intelligence_trust_from_sources(
    sources: Sequence[Mapping[str, Any]] | Iterable[Mapping[str, Any]],
    *,
    coverage: Any = None,
    degradation_reasons: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Aggregate source tier trust across multiple evidence inputs."""

    materialized = [dict(item) for item in sources if isinstance(item, Mapping)]
    if not materialized:
        return evaluate_market_intelligence_trust(
            {
                "sourceTier": MarketIntelligenceSourceTier.UNAVAILABLE.value,
                "freshness": "unavailable",
                "coverage": 0.0,
                "degradationReasons": list(degradation_reasons or ()),
            }
        )

    item_results = [evaluate_market_intelligence_trust(item) for item in materialized]
    item_tiers = [
        _coerce_source_tier(result["sourceTier"]) or MarketIntelligenceSourceTier.UNAVAILABLE
        for result in item_results
    ]
    aggregate_coverage = (
        _bounded_float(coverage, default=0.0)
        if coverage is not None
        else round(sum(float(result["coverage"]) for result in item_results) / len(item_results), 2)
    )
    freshness = _weakest_freshness(str(result["freshness"]) for result in item_results)
    source_tier = _aggregate_source_tier(item_tiers)
    reasons = _ordered_reasons(degradation_reasons or ())
    for result in item_results:
        for reason in result["degradationReasons"]:
            if reason in {"low_coverage", "no_coverage"}:
                continue
            reasons = _append_reason(reasons, reason)
    if _has_mixed_trust_groups(item_tiers):
        reasons = _append_reason(reasons, "mixed_source_tiers")
        reasons = _append_reason(reasons, "partial_coverage")
    if 0.0 < aggregate_coverage < 0.8:
        reasons = _append_reason(reasons, "partial_coverage" if aggregate_coverage >= 0.5 else "low_coverage")
    elif aggregate_coverage <= 0.0:
        reasons = _append_reason(reasons, "no_coverage")

    return evaluate_market_intelligence_trust(
        {
            "sourceTier": source_tier.value,
            "freshness": freshness,
            "coverage": aggregate_coverage,
            "isStale": freshness == "stale",
            "isFallback": freshness == "fallback",
            "isSynthetic": freshness in {"synthetic", "mock"},
            "isUnavailable": (
                freshness in {"unavailable", "error"}
                or source_tier is MarketIntelligenceSourceTier.UNAVAILABLE
            ),
            "isPartial": "partial_coverage" in reasons or "mixed_source_tiers" in reasons,
            "degradationReasons": reasons,
        }
    )


def _coerce_source_tier(value: Any) -> MarketIntelligenceSourceTier | None:
    if isinstance(value, MarketIntelligenceSourceTier):
        return value
    normalized = _text(value).lower()
    if not normalized:
        return None
    normalized = normalized.replace("-", "_")
    for item in MarketIntelligenceSourceTier:
        if item.value == normalized:
            return item
    return _SOURCE_TYPE_TO_TIER.get(normalized)


def _aggregate_source_tier(tiers: Sequence[MarketIntelligenceSourceTier]) -> MarketIntelligenceSourceTier:
    reliable_tiers = [tier for tier in tiers if tier in _RELIABLE_CAPABLE_TIERS]
    non_reliable_tiers = [tier for tier in tiers if tier not in _RELIABLE_CAPABLE_TIERS]
    candidates = non_reliable_tiers or reliable_tiers or [MarketIntelligenceSourceTier.UNAVAILABLE]
    return max(candidates, key=lambda tier: _TIER_RANK[tier])


def _has_mixed_trust_groups(tiers: Sequence[MarketIntelligenceSourceTier]) -> bool:
    groups = {_tier_group(tier) for tier in tiers}
    return len(groups) > 1 and groups != {"reliable"}


def _tier_group(tier: MarketIntelligenceSourceTier) -> str:
    if tier in _RELIABLE_CAPABLE_TIERS:
        return "reliable"
    if tier is MarketIntelligenceSourceTier.SNAPSHOT:
        return "snapshot"
    if tier in _WEAK_TIERS:
        return "weak"
    return "unavailable"


def _normalized_freshness(
    value: Any,
    *,
    source_tier: MarketIntelligenceSourceTier,
    is_fallback: bool,
    is_stale: bool,
    is_partial: bool,
    is_synthetic: bool,
    is_unavailable: bool,
) -> str:
    normalized = _text(value).lower()
    if normalized == "synthetic_delayed":
        normalized = "synthetic"
    if normalized == "error":
        normalized = "unavailable"
    if is_unavailable or source_tier is MarketIntelligenceSourceTier.UNAVAILABLE:
        return "unavailable"
    if is_synthetic or source_tier is MarketIntelligenceSourceTier.SYNTHETIC:
        return "synthetic"
    if is_fallback or source_tier in {
        MarketIntelligenceSourceTier.PUBLIC_WEB_FALLBACK,
        MarketIntelligenceSourceTier.STATIC_FALLBACK,
    }:
        return "fallback"
    if is_stale:
        return "stale"
    if is_partial and normalized in {"", "fresh", "live", "delayed", "cached"}:
        return "partial"
    if source_tier is MarketIntelligenceSourceTier.SNAPSHOT and normalized in {"", "fresh", "live"}:
        return "cached"
    return normalized if normalized in _FRESHNESS_RANK else "unknown"


def _weakest_freshness(values: Iterable[str]) -> str:
    normalized_values = [value if value in _FRESHNESS_RANK else "unknown" for value in values]
    if not normalized_values:
        return "unavailable"
    return max(normalized_values, key=lambda value: _FRESHNESS_RANK[value])


def _trust_level(
    *,
    source_tier: MarketIntelligenceSourceTier,
    score_cap: float,
    reasons: Sequence[str],
) -> MarketIntelligenceTrustLevel:
    if score_cap <= 0.0 or source_tier is MarketIntelligenceSourceTier.UNAVAILABLE:
        return MarketIntelligenceTrustLevel.UNAVAILABLE
    if source_tier in _WEAK_TIERS or score_cap < 0.5:
        return MarketIntelligenceTrustLevel.WEAK
    if score_cap >= 0.8 and not reasons:
        return MarketIntelligenceTrustLevel.RELIABLE
    return MarketIntelligenceTrustLevel.USABLE_WITH_CAUTION


def _warning_for(trust_level: MarketIntelligenceTrustLevel, reasons: Sequence[str]) -> str | None:
    if trust_level is MarketIntelligenceTrustLevel.RELIABLE:
        return None
    if trust_level is MarketIntelligenceTrustLevel.UNAVAILABLE:
        return "Market intelligence data is unavailable; strong conclusions are blocked."
    if trust_level is MarketIntelligenceTrustLevel.WEAK:
        return "Market intelligence data is weak; strong conclusions are blocked."
    if "mixed_source_tiers" in reasons:
        return "Market intelligence sources are mixed; conclusions require caution."
    if "stale_source" in reasons:
        return "Market intelligence data is stale; conclusions require caution."
    if "partial_coverage" in reasons:
        return "Market intelligence coverage is partial; conclusions require caution."
    return "Market intelligence trust is capped; conclusions require caution."


def _reasons_from_payload(payload: Mapping[str, Any]) -> tuple[str, ...]:
    value = _get(payload, "degradation_reasons", "degradationReasons")
    reasons: list[str] = []
    if isinstance(value, str):
        reasons.extend(part.strip() for part in value.split(",") if part.strip())
    elif isinstance(value, Iterable):
        reasons.extend(_text(item) for item in value if _text(item))
    explicit_reason = _text(_get(payload, "degradation_reason", "degradationReason", "cap_reason", "capReason"))
    if explicit_reason:
        reasons.append(explicit_reason)
    return tuple(reasons)


def _ordered_reasons(values: Iterable[Any]) -> tuple[str, ...]:
    reasons: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in reasons:
            reasons.append(text)
    return tuple(reasons)


def _append_reason(reasons: Sequence[str], reason: str) -> tuple[str, ...]:
    if reason in reasons:
        return tuple(reasons)
    return (*tuple(reasons), reason)


def _get(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _bounded_float(value: Any, *, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(0.0, min(1.0, number))


def _optional_bounded_float(value: Any) -> float | None:
    if value is None:
        return None
    return _bounded_float(value, default=0.0)


__all__ = [
    "MARKET_INTELLIGENCE_TRUST_GATE_VERSION",
    "MarketIntelligenceSourceTier",
    "MarketIntelligenceTrustLevel",
    "MarketIntelligenceTrustResult",
    "evaluate_market_intelligence_trust",
    "evaluate_market_intelligence_trust_from_sources",
    "resolve_market_intelligence_source_tier",
]
