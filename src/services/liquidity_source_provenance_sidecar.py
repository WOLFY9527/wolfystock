# -*- coding: utf-8 -*-
"""Helper-only Liquidity provenance sidecar builder.

This module is intentionally inert. It consumes only passed-in mappings/lists
and converts Liquidity readiness/evidence-like inputs into bounded
`SourceProvenanceV1` entries. It does not call providers, caches, env/settings,
runtime DTOs, storage, or network APIs.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from src.services.source_provenance_contract import (
    build_source_provenance,
    build_source_provenance_sidecar,
)


LIQUIDITY_SOURCE_PROVENANCE_VERSION = "liquidity_source_provenance_sidecar_v1"

_DOMAIN_SPECS = (
    ("liquidity", "market_data", "流动性主信号"),
    ("macroLiquidity", "macro", "宏观流动性"),
    ("fundingStress", "macro", "资金压力"),
    ("creditStress", "macro", "信用压力"),
    ("volatility", "market_data", "波动率"),
    ("breadth", "market_data", "市场广度"),
    ("capitalFlow", "market_data", "资金流向"),
    ("policyLiquidity", "macro", "政策流动性"),
    ("signalCoverage", "research", "信号覆盖"),
)

_DEGRADED_FRESHNESS = {"stale", "fallback", "unavailable", "unknown", "synthetic", "demo", "fixture", "mock"}
_DEGRADED_SOURCE_MARKERS = {"proxy", "fallback", "fixture", "demo", "synthetic", "unknown", "missing"}
_FAIL_CLOSED_MARKERS = {
    "stale",
    "fallback",
    "proxy",
    "observation_only",
    "observe_only",
    "unavailable",
    "unknown",
    "demo",
    "fixture",
    "synthetic",
    "missing",
    "partial",
}
_INDICATOR_TO_DOMAIN = {
    "crypto_spot_momentum": "liquidity",
    "crypto_funding": "fundingStress",
    "vix_pressure": "volatility",
    "us_breadth_proxy": "breadth",
}
_ASSET_TO_DOMAIN = {
    "rates": "creditStress",
    "usd": "policyLiquidity",
    "volatility": "volatility",
    "growth_ai_software_semis": "capitalFlow",
}


def build_liquidity_source_provenance_sidecar(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized_payload = _mapping(payload)
    entries = [
        _build_domain_entry(
            domain_key=domain_key,
            evidence_domain=evidence_domain,
            fallback_label=fallback_label,
            payload=normalized_payload,
        )
        for domain_key, evidence_domain, fallback_label in _DOMAIN_SPECS
    ]
    entries = sorted(entries, key=lambda item: (item["sourceId"], item["debugRef"], item["evidenceDomain"]))
    return build_source_provenance_sidecar(
        contract_version=LIQUIDITY_SOURCE_PROVENANCE_VERSION,
        entries=entries,
    )


def _build_domain_entry(
    *,
    domain_key: str,
    evidence_domain: str,
    fallback_label: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    value = _domain_value(domain_key, payload)
    source_id = value.get("sourceId") or value.get("source") or f"liquidity_{domain_key}"
    source_label = value.get("sourceLabel") or value.get("label") or fallback_label
    freshness = _freshness(value)
    source_tier = _normalized_source_tier(value.get("sourceTier") or value.get("sourceType") or value.get("source"))
    authority_tier = _authority_tier(domain_key=domain_key, value=value, freshness=freshness, source_tier=source_tier)
    observation_only = _observation_only(value=value, freshness=freshness, source_tier=source_tier, authority_tier=authority_tier)
    score_allowed = authority_tier == "score_grade" and not observation_only
    fallback_or_proxy = _fallback_or_proxy(value=value, freshness=freshness, source_tier=source_tier)
    limitations = _limitations(
        domain_key=domain_key,
        value=value,
        freshness=freshness,
        fallback_or_proxy=fallback_or_proxy,
        observation_only=observation_only,
    )
    next_evidence_needed = _next_evidence_needed(
        domain_key=domain_key,
        authority_tier=authority_tier,
        freshness=freshness,
        fallback_or_proxy=fallback_or_proxy,
    )
    return build_source_provenance(
        source_id=source_id,
        source_label=source_label,
        evidence_domain=evidence_domain,
        authority_tier=authority_tier,
        freshness_state=freshness,
        source_tier=source_tier,
        fallback_or_proxy=fallback_or_proxy,
        observation_only=observation_only,
        score_contribution_allowed=score_allowed,
        limitations=limitations,
        next_evidence_needed=next_evidence_needed,
        debug_ref=f"liquidity-{domain_key}",
    )


def _domain_value(domain_key: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    readiness = _mapping(payload.get("readiness"))
    observation_evidence = _mapping(payload.get("observationEvidence"))
    capital_flow_signal = _mapping(payload.get("capitalFlowSignal"))
    time_series_status = _mapping(payload.get("timeSeriesStatus"))
    signal_coverage = _mapping(payload.get("signalCoverage"))

    if domain_key == "signalCoverage":
        return dict(signal_coverage)

    if domain_key in {"macroLiquidity", "fundingStress", "creditStress", "policyLiquidity"}:
        time_series_value = _mapping(time_series_status.get(domain_key))
        merged = dict(readiness)
        merged.update(time_series_value)
        return merged

    if domain_key == "capitalFlow":
        merged = dict(readiness)
        merged.update(capital_flow_signal)
        for item in _sequence(capital_flow_signal.get("sourceAssetPressure")):
            mapped = _mapping(item)
            if _ASSET_TO_DOMAIN.get(_text(mapped.get("asset"))) == "capitalFlow":
                merged.update(mapped)
                break
        return merged

    if domain_key in {"liquidity", "volatility", "breadth"}:
        merged = dict(readiness)
        for item in _sequence(observation_evidence.get("indicatorEvidence")):
            mapped = _mapping(item)
            if _INDICATOR_TO_DOMAIN.get(_text(mapped.get("key"))) == domain_key:
                merged.update(mapped)
                break
        if domain_key == "volatility":
            for item in _sequence(capital_flow_signal.get("sourceAssetPressure")):
                mapped = _mapping(item)
                if _ASSET_TO_DOMAIN.get(_text(mapped.get("asset"))) == "volatility":
                    merged.setdefault("source", mapped.get("source"))
                    merged.setdefault("sourceLabel", mapped.get("sourceLabel"))
                    merged.setdefault("sourceType", mapped.get("sourceType"))
                    merged.setdefault("freshness", mapped.get("freshness"))
                    break
        return merged

    return dict(readiness)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    if isinstance(value, Iterable):
        return list(value)
    return []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _lower_text(value: Any) -> str:
    return _text(value).lower()


def _contains_marker(value: str, markers: set[str]) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in markers)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    return bool(value)


def _freshness(value: Mapping[str, Any]) -> str:
    freshness = _lower_text(value.get("freshness") or value.get("freshnessState") or value.get("status") or "unknown")
    if freshness == "live":
        return "fresh"
    if freshness == "partial":
        return "partial"
    return freshness or "unknown"


def _normalized_source_tier(value: Any) -> str:
    text = _lower_text(value)
    if "proxy" in text:
        return "public_proxy"
    if "fallback" in text:
        return "fallback_static"
    if any(marker in text for marker in ("fixture", "demo", "synthetic")):
        return "synthetic_fixture"
    if "cache" in text or "snapshot" in text:
        return "cache_snapshot"
    if any(marker in text for marker in ("official", "exchange_public")):
        return "official_public"
    if any(marker in text for marker in ("authorized", "licensed", "binance")):
        return "authorized_licensed_feed"
    return text or "unknown"


def _authority_tier(*, domain_key: str, value: Mapping[str, Any], freshness: str, source_tier: str) -> str:
    texts = _all_texts(value)
    available = value.get("available")
    if available is False:
        return "observation_only"
    if _contains_any(texts, {"demo", "fixture", "synthetic"}):
        return "fixture"
    if freshness in _DEGRADED_FRESHNESS or _contains_marker(source_tier, _DEGRADED_SOURCE_MARKERS):
        return "observation_only"
    if domain_key == "liquidity" and _bool(value.get("scoreContributionAllowed")) and not _bool(value.get("coverageObservationOnly")):
        return "score_grade"
    return "observation_only"


def _observation_only(*, value: Mapping[str, Any], freshness: str, source_tier: str, authority_tier: str) -> bool:
    if authority_tier != "score_grade":
        return True
    if "coverageObservationOnly" in value:
        return _bool(value.get("coverageObservationOnly"))
    if _bool(value.get("observationOnly")):
        return True
    if freshness not in {"fresh", "cached"}:
        return True
    return _contains_marker(source_tier, _DEGRADED_SOURCE_MARKERS)


def _fallback_or_proxy(*, value: Mapping[str, Any], freshness: str, source_tier: str) -> bool:
    if _bool(value.get("isFallback")) or _bool(value.get("fallbackUsed")) or _bool(value.get("isProxy")):
        return True
    if _bool(value.get("isPartial")) and freshness in {"delayed", "fallback", "unavailable", "unknown"}:
        return True
    if freshness in {"fallback", "unavailable", "unknown", "synthetic", "demo"}:
        return True
    return _contains_marker(source_tier, _DEGRADED_SOURCE_MARKERS)


def _limitations(
    *,
    domain_key: str,
    value: Mapping[str, Any],
    freshness: str,
    fallback_or_proxy: bool,
    observation_only: bool,
) -> list[str] | None:
    cleaned: list[str] = []
    for item in _sequence(value.get("warnings")) + _sequence(value.get("reasonCodes")) + _sequence(value.get("blockingReasons")):
        text = _lower_text(item).replace("-", "_").replace(" ", "_")
        if text:
            cleaned.append(text)
    if value.get("available") is False:
        cleaned.append("time_series_unavailable")
    if freshness in _DEGRADED_FRESHNESS:
        cleaned.append(f"{freshness}_source")
    if fallback_or_proxy:
        cleaned.append("fallback_or_proxy_source")
    if observation_only:
        cleaned.append("observation_only")
    if _contains_any(_all_texts(value), _FAIL_CLOSED_MARKERS):
        cleaned.append("fail_closed_input")
    if domain_key == "signalCoverage" and _numeric(value.get("missingIndicatorCount")):
        cleaned.append("missing_indicator_coverage")
    return list(dict.fromkeys(cleaned)) or None


def _next_evidence_needed(
    *,
    domain_key: str,
    authority_tier: str,
    freshness: str,
    fallback_or_proxy: bool,
) -> list[str]:
    if authority_tier == "score_grade":
        return []
    if domain_key in {"macroLiquidity", "policyLiquidity"} and freshness == "unavailable":
        return [f"{domain_key.lower()}_authoritative_time_series"]
    if fallback_or_proxy:
        return [f"{domain_key.lower()}_authorized_primary_source"]
    if freshness in _DEGRADED_FRESHNESS:
        return [f"{domain_key.lower()}_fresh_authoritative_snapshot"]
    return [f"{domain_key.lower()}_verified_source_metadata"]


def _all_texts(value: Mapping[str, Any]) -> list[str]:
    texts: list[str] = []
    for raw in value.values():
        if isinstance(raw, Mapping):
            texts.extend(_all_texts(raw))
        elif isinstance(raw, (list, tuple, set, frozenset)):
            for item in raw:
                if isinstance(item, Mapping):
                    texts.extend(_all_texts(item))
                else:
                    text = _text(item)
                    if text:
                        texts.append(text)
        else:
            text = _text(raw)
            if text:
                texts.append(text)
    return texts


def _contains_any(values: Iterable[Any], markers: set[str]) -> bool:
    lowered = " ".join(_lower_text(value) for value in values if value is not None)
    return any(marker in lowered for marker in markers)


def _numeric(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "LIQUIDITY_SOURCE_PROVENANCE_VERSION",
    "build_liquidity_source_provenance_sidecar",
]
