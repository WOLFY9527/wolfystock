# -*- coding: utf-8 -*-
"""Helper-only Market Intelligence provenance sidecar builder."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.services.source_provenance_contract import (
    build_source_provenance,
    build_source_provenance_sidecar,
)


MARKET_INTELLIGENCE_SOURCE_PROVENANCE_VERSION = "market_intelligence_source_provenance_sidecar_v1"

_DOMAIN_SPECS = (
    ("breadth", "market_data", "市场广度"),
    ("liquidity", "market_data", "流动性信号"),
    ("macroLiquidity", "macro", "宏观流动性"),
    ("marketRegime", "macro", "市场状态"),
    ("rotation", "market_data", "轮动信号"),
    ("scannerContext", "research", "扫描器上下文"),
    ("sectorTheme", "market_data", "行业主题"),
    ("sentiment", "market_data", "市场情绪"),
    ("volatility", "market_data", "波动率"),
)
_DEGRADED_FRESHNESS = {"stale", "fallback", "unavailable", "unknown", "synthetic", "fixture", "demo", "mock", "error"}
_DEGRADED_SOURCE_MARKERS = {"proxy", "fallback", "fixture", "demo", "synthetic", "unknown", "missing"}


def build_market_intelligence_source_provenance_sidecar(
    domain_inputs: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = _mapping(domain_inputs)
    entries = sorted(
        [
        _build_domain_entry(domain_key, evidence_domain, fallback_label, payload[domain_key])
        for domain_key, evidence_domain, fallback_label in _DOMAIN_SPECS
        if domain_key in payload
        ],
        key=lambda item: (item["sourceId"], item["debugRef"], item["evidenceDomain"]),
    )
    return build_source_provenance_sidecar(
        contract_version=MARKET_INTELLIGENCE_SOURCE_PROVENANCE_VERSION,
        entries=entries,
    )


def _build_domain_entry(
    domain_key: str,
    evidence_domain: str,
    fallback_label: str,
    raw_value: Any,
) -> dict[str, Any]:
    value = _coerce_domain_value(raw_value)
    source_id = (
        value.get("sourceId")
        or value.get("source")
        or value.get("sourceKey")
        or f"market_{domain_key}"
    )
    source_label = value.get("sourceLabel") or value.get("label") or fallback_label
    freshness = _text(value.get("freshness") or value.get("freshnessState") or value.get("status") or "unknown").lower()
    source_tier = _normalized_source_tier(value.get("sourceTier") or value.get("sourceType") or "unknown")
    authority_tier = _authority_tier(value, freshness, source_tier)
    observation_only = _observation_only(value, freshness, source_tier, authority_tier)
    score_allowed = authority_tier == "score_grade" and not observation_only
    fallback_or_proxy = _fallback_or_proxy(value, freshness, source_tier)
    limitations = _limitations(value, freshness, fallback_or_proxy, observation_only)
    next_evidence_needed = _next_evidence_needed(domain_key, authority_tier, freshness, fallback_or_proxy)

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
        debug_ref=f"market:{domain_key}",
    )


def _coerce_domain_value(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            if isinstance(item, Mapping):
                return item
    return {}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _contains_marker(value: str, markers: set[str]) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in markers)


def _normalized_source_tier(value: Any) -> str:
    text = _text(value).lower()
    if "proxy" in text:
        return "public_proxy"
    if "fallback" in text:
        return "fallback_static"
    if any(marker in text for marker in ("fixture", "demo", "synthetic")):
        return "synthetic_fixture"
    return text or "unknown"


def _authority_tier(value: Mapping[str, Any], freshness: str, source_tier: Any) -> str:
    if (
        bool(value.get("sourceAuthorityAllowed"))
        and bool(value.get("scoreContributionAllowed"))
        and freshness in {"fresh", "cached"}
        and not _contains_marker(_text(source_tier), _DEGRADED_SOURCE_MARKERS)
    ):
        return "score_grade"
    if _contains_marker(freshness, {"demo", "fixture", "synthetic"}) or _contains_marker(_text(source_tier), {"demo", "fixture", "synthetic"}):
        return "fixture"
    if freshness in _DEGRADED_FRESHNESS or _contains_marker(_text(source_tier), _DEGRADED_SOURCE_MARKERS):
        return "observation_only"
    if bool(value.get("observationOnly")) or not bool(value.get("sourceAuthorityAllowed")):
        return "observation_only"
    return "unknown"


def _observation_only(value: Mapping[str, Any], freshness: str, source_tier: Any, authority_tier: str) -> bool:
    if authority_tier != "score_grade":
        return True
    if bool(value.get("observationOnly")):
        return True
    if freshness not in {"fresh", "cached"}:
        return True
    return _contains_marker(_text(source_tier), _DEGRADED_SOURCE_MARKERS)


def _fallback_or_proxy(value: Mapping[str, Any], freshness: str, source_tier: Any) -> bool:
    if bool(value.get("fallbackUsed") or value.get("isFallback") or value.get("isProxy")):
        return True
    if freshness in {"fallback", "synthetic", "fixture", "demo", "unknown", "unavailable"}:
        return True
    return _contains_marker(_text(source_tier), _DEGRADED_SOURCE_MARKERS)


def _limitations(
    value: Mapping[str, Any],
    freshness: str,
    fallback_or_proxy: bool,
    observation_only: bool,
) -> list[str] | None:
    raw = value.get("limitations") or value.get("missingEvidence") or value.get("blockingReasons")
    cleaned = []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        for item in raw:
            text = _text(item).lower().replace("-", "_").replace(" ", "_")
            if text:
                cleaned.append(text)
    if freshness in _DEGRADED_FRESHNESS:
        cleaned.append(f"{freshness}_source")
    if fallback_or_proxy:
        cleaned.append("fallback_or_proxy_source")
    if observation_only:
        cleaned.append("observation_only")
    return list(dict.fromkeys(cleaned)) or None


def _next_evidence_needed(
    domain_key: str,
    authority_tier: str,
    freshness: str,
    fallback_or_proxy: bool,
) -> list[str]:
    if authority_tier == "score_grade":
        return []
    if fallback_or_proxy:
        return [f"{domain_key}_authorized_primary_source"]
    if freshness in _DEGRADED_FRESHNESS:
        return [f"{domain_key}_fresh_authoritative_snapshot"]
    return [f"{domain_key}_verified_source_metadata"]


__all__ = [
    "MARKET_INTELLIGENCE_SOURCE_PROVENANCE_VERSION",
    "build_market_intelligence_source_provenance_sidecar",
]
