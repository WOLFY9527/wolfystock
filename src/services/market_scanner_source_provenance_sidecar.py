# -*- coding: utf-8 -*-
"""Helper-only Scanner provenance sidecar builder.

This module derives bounded SourceProvenanceV1 entries from existing scanner
candidate/readiness/summary/context mappings. It does not import runtime
services, call providers, read caches, or change scanner behavior.
"""

from __future__ import annotations

from typing import Any, Mapping

from src.services.source_provenance_contract import (
    build_fixture_demo_source_provenance,
    build_source_provenance,
    summarize_source_provenance,
)


SCANNER_SOURCE_PROVENANCE_DOMAIN_ORDER = (
    "priceHistory",
    "liquidity",
    "technicals",
    "fundamentals",
    "news",
    "catalysts",
    "sectorTheme",
    "macroLiquidity",
    "topDownContext",
)

_FIXTURE_MARKERS = ("fixture", "demo", "mock", "synthetic", "sample")
_PROXY_TIERS = {"public_proxy", "unofficial_proxy", "fallback_static", "fallback", "proxy"}
_BLOCKED_STATES = {"blocked", "unavailable", "failed"}
_UNSAFE_FRESHNESS = {"stale", "fallback", "unknown", "unavailable", "synthetic"}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _normalize_key(value: Any) -> str:
    text = _text(value).lower().replace("-", "_").replace("/", "_")
    return "_".join(part for part in text.split("_") if part)


def _first_mapping(*values: Any) -> dict[str, Any]:
    for value in values:
        mapped = _mapping(value)
        if mapped:
            return mapped
    return {}


def _merge_mappings(*values: Any) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for value in values:
        mapped = _mapping(value)
        if mapped:
            merged.update(mapped)
    return merged


def _first_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return []


def _domain_contract_name(domain: str) -> str:
    if domain in {"priceHistory", "liquidity", "technicals"}:
        return "technicals"
    if domain == "fundamentals":
        return "fundamentals"
    if domain in {"news", "catalysts"}:
        return "news"
    if domain == "macroLiquidity":
        return "macro"
    return "research"


def _domain_state(
    domain: str,
    *,
    candidate_evidence_frame: Mapping[str, Any],
    scanner_context_frame: Mapping[str, Any],
    candidate_research_summary_frame: Mapping[str, Any],
) -> str:
    domains = _mapping(candidate_evidence_frame.get("domains"))
    if domain == "news":
        return _text(_mapping(domains.get("newsCatalyst")).get("state")).lower() or "missing"
    if domain == "catalysts":
        return _text(_mapping(domains.get("newsCatalyst")).get("state")).lower() or "missing"
    if domain == "sectorTheme":
        return _text(_mapping(domains.get("theme")).get("state")).lower() or "missing"
    if domain == "macroLiquidity":
        liquidity_frame = _mapping(scanner_context_frame.get("liquidityFrame"))
        return _text(liquidity_frame.get("readinessState") or liquidity_frame.get("state")).lower() or "unknown"
    if domain == "topDownContext":
        market_readiness = _mapping(scanner_context_frame.get("marketReadiness"))
        if market_readiness:
            return _text(market_readiness.get("readinessState") or market_readiness.get("state")).lower() or "unknown"
        refs = _list(candidate_research_summary_frame.get("topDownContextRefs"))
        return "available" if refs else "unknown"
    return _text(_mapping(domains.get(domain)).get("state")).lower() or "missing"


def _extract_domain_input(
    domain: str,
    *,
    candidate: Mapping[str, Any],
    candidate_research_readiness: Mapping[str, Any],
    scanner_context_frame: Mapping[str, Any],
) -> dict[str, Any]:
    diagnostics = _mapping(candidate.get("diagnostics") or candidate.get("_diagnostics"))
    history = _mapping(diagnostics.get("history"))
    quote_context = _mapping(diagnostics.get("quote_context"))
    explainability = _mapping(diagnostics.get("score_explainability"))
    source_confidence = _mapping(explainability.get("source_confidence"))
    provider_observation = _mapping(diagnostics.get("cn_provider_observation"))
    evidence_packet = _mapping(diagnostics.get("evidence_packet"))
    fundamentals_context = _first_mapping(
        candidate.get("fundamentals"),
        diagnostics.get("fundamentals"),
        diagnostics.get("fundamentals_context"),
    )
    news_context = _first_mapping(
        candidate.get("news"),
        diagnostics.get("news"),
        diagnostics.get("news_context"),
        diagnostics.get("news_catalyst"),
    )
    catalyst_context = _first_mapping(
        candidate.get("catalyst"),
        diagnostics.get("catalyst"),
        diagnostics.get("events"),
        diagnostics.get("news_catalyst"),
    )
    theme_context = _first_mapping(
        diagnostics.get("theme_context"),
        _mapping(evidence_packet.get("sectorThemeContext")),
    )
    market_readiness = _mapping(scanner_context_frame.get("marketReadiness"))
    liquidity_frame = _mapping(scanner_context_frame.get("liquidityFrame"))

    if domain == "priceHistory":
        return _merge_mappings(history, quote_context, source_confidence)
    if domain == "liquidity":
        return _merge_mappings(history, quote_context, source_confidence)
    if domain == "technicals":
        return _merge_mappings(history, quote_context, source_confidence)
    if domain == "fundamentals":
        return fundamentals_context
    if domain == "news":
        return news_context
    if domain == "catalysts":
        return catalyst_context
    if domain == "sectorTheme":
        return theme_context
    if domain == "macroLiquidity":
        return liquidity_frame
    if domain == "topDownContext":
        return _first_mapping(market_readiness, candidate_research_readiness)
    return {}


def _freshness_for_domain(
    domain_input: Mapping[str, Any],
    *,
    candidate_research_readiness: Mapping[str, Any],
    state: str,
) -> str:
    freshness = _first_text(
        domain_input.get("freshnessState"),
        domain_input.get("freshness"),
        candidate_research_readiness.get("freshness"),
        candidate_research_readiness.get("freshnessFloor"),
    ).lower()
    if freshness in {"live", "fresh"}:
        return "fresh"
    if freshness in {"cached", "cache"}:
        return "cached"
    if freshness in {"delayed", "partial"}:
        return "delayed"
    if freshness in {"stale", "fallback", "synthetic", "unavailable", "unknown"}:
        return freshness
    if _bool(domain_input.get("isStale")):
        return "stale"
    if _bool(domain_input.get("isFallback")) or _bool(domain_input.get("fallbackOrProxy")):
        return "fallback"
    if state in _BLOCKED_STATES:
        return "unavailable"
    return "unknown"


def _source_tier_for_domain(
    domain_input: Mapping[str, Any],
    *,
    market: str,
    observation_only: bool,
) -> str:
    source_tier = _first_text(
        domain_input.get("sourceTier"),
        domain_input.get("sourceType"),
        domain_input.get("source_type"),
    )
    normalized = _normalize_key(source_tier)
    if normalized:
        return normalized
    if market == "cn" and observation_only:
        return "public_proxy"
    return "unknown"


def _authority_for_domain(
    domain: str,
    domain_input: Mapping[str, Any],
    *,
    candidate_research_readiness: Mapping[str, Any],
    observation_only: bool,
    score_allowed: bool,
    state: str,
    blocked_context: bool,
) -> str:
    explicit = _first_text(
        domain_input.get("sourceAuthority"),
        domain_input.get("providerAuthority"),
    )
    normalized = _normalize_key(explicit)
    if score_allowed and state not in _BLOCKED_STATES:
        return "score_grade"
    if domain in {"macroLiquidity", "topDownContext"}:
        return "observation_only" if not blocked_context else "unknown"
    if normalized in {"scoregradeallowed", "score_grade_allowed", "score_grade"}:
        return "score_grade"
    if observation_only or normalized in {"observationonly", "observation_only"}:
        return "observation_only"
    if normalized in {"unavailable", "unknown"}:
        return "unknown"
    return "unknown"


def _next_evidence(candidate_research_readiness: Mapping[str, Any], domain: str) -> list[str]:
    raw = [
        _text(item)
        for item in _list(candidate_research_readiness.get("nextEvidenceNeeded"))
        if _text(item)
    ]
    if raw:
        return raw
    return [f"scanner_{domain}_evidence_needed"]


def _limitations(
    *,
    domain_input: Mapping[str, Any],
    market: str,
    state: str,
    freshness: str,
    source_tier: str,
    observation_only: bool,
    blocked_context: bool,
    missing_state: bool,
) -> list[str]:
    limitations: list[str] = []
    if market == "cn":
        limitations.append("cn_observation_only")
    if blocked_context:
        limitations.append("blocked_runtime_context")
    if missing_state:
        limitations.append("missing_candidate_evidence")
    if freshness in _UNSAFE_FRESHNESS:
        limitations.append(f"{freshness}_evidence")
    if source_tier in _PROXY_TIERS:
        limitations.append("fallback_or_proxy_source")
    if observation_only:
        limitations.append("observation_only")
    for key in ("sourceAuthorityReason", "reason", "status"):
        reason = _normalize_key(domain_input.get(key))
        if reason and reason not in {"ok", "available"}:
            limitations.append(reason[:64])
    ordered: list[str] = []
    for item in limitations:
        if item and item not in ordered:
            ordered.append(item)
    return ordered


def _is_fixture_demo(*values: Any) -> bool:
    haystack = " ".join(_text(value).lower() for value in values if _text(value))
    return any(marker in haystack for marker in _FIXTURE_MARKERS)


def _build_domain_entry(
    domain: str,
    *,
    candidate: Mapping[str, Any],
    candidate_evidence_frame: Mapping[str, Any],
    candidate_research_readiness: Mapping[str, Any],
    candidate_research_summary_frame: Mapping[str, Any],
    scanner_context_frame: Mapping[str, Any],
) -> dict[str, Any]:
    market_readiness = _mapping(scanner_context_frame.get("marketReadiness"))
    market = _first_text(
        candidate.get("market"),
        candidate_research_readiness.get("market"),
        market_readiness.get("market"),
    ).lower()
    state = _domain_state(
        domain,
        candidate_evidence_frame=candidate_evidence_frame,
        scanner_context_frame=scanner_context_frame,
        candidate_research_summary_frame=candidate_research_summary_frame,
    )
    domain_input = _extract_domain_input(
        domain,
        candidate=candidate,
        candidate_research_readiness=candidate_research_readiness,
        scanner_context_frame=scanner_context_frame,
    )
    blocked_context = state in _BLOCKED_STATES
    missing_state = state in {"missing", "unknown", ""}
    freshness = _freshness_for_domain(
        domain_input,
        candidate_research_readiness=candidate_research_readiness,
        state=state,
    )
    observation_only = (
        _bool(domain_input.get("observationOnly"))
        or market == "cn"
        or blocked_context
        or freshness in _UNSAFE_FRESHNESS
        or domain in {"macroLiquidity", "topDownContext"}
    )
    source_tier = _source_tier_for_domain(
        domain_input,
        market=market,
        observation_only=observation_only,
    )
    score_allowed = (
        _bool(domain_input.get("sourceAuthorityAllowed"))
        and _bool(domain_input.get("scoreContributionAllowed"))
        and not observation_only
        and source_tier not in _PROXY_TIERS
        and freshness in {"fresh", "cached"}
    )
    authority = _authority_for_domain(
        domain,
        domain_input,
        candidate_research_readiness=candidate_research_readiness,
        observation_only=observation_only,
        score_allowed=score_allowed,
        state=state,
        blocked_context=blocked_context,
    )
    source_id = _first_text(
        domain_input.get("sourceId"),
        domain_input.get("source"),
        domain_input.get("provider"),
        domain_input.get("providerName"),
    )
    source_label = _first_text(
        domain_input.get("sourceLabel"),
        domain_input.get("providerLabel"),
        domain_input.get("source"),
        domain_input.get("providerName"),
    )
    debug_ref = f"scanner:{domain}:{source_id or 'unknown'}"

    if _is_fixture_demo(source_id, source_label, source_tier, debug_ref):
        return build_fixture_demo_source_provenance(
            source_id=source_id or f"scanner_{domain}_fixture",
            source_label=source_label or "Scanner Fixture",
            evidence_domain=_domain_contract_name(domain),
            debug_ref=debug_ref,
        )

    return build_source_provenance(
        source_id=source_id,
        source_label=source_label,
        evidence_domain=_domain_contract_name(domain),
        authority_tier=authority,
        freshness_state=freshness,
        source_tier=source_tier,
        fallback_or_proxy=source_tier in _PROXY_TIERS or _bool(domain_input.get("isFallback")),
        observation_only=observation_only,
        score_contribution_allowed=score_allowed,
        limitations=_limitations(
            domain_input=domain_input,
            market=market,
            state=state,
            freshness=freshness,
            source_tier=source_tier,
            observation_only=observation_only,
            blocked_context=blocked_context,
            missing_state=missing_state,
        ),
        next_evidence_needed=_next_evidence(candidate_research_readiness, domain),
        debug_ref=debug_ref,
    )


def build_market_scanner_source_provenance_sidecar(
    candidate: Mapping[str, Any] | None,
    *,
    candidate_evidence_frame: Mapping[str, Any] | None = None,
    candidate_research_readiness: Mapping[str, Any] | None = None,
    candidate_research_summary_frame: Mapping[str, Any] | None = None,
    scanner_context_frame: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(candidate or {})
    evidence_frame = _mapping(candidate_evidence_frame or payload.get("candidateEvidenceFrame"))
    readiness = _mapping(candidate_research_readiness or payload.get("candidateResearchReadiness"))
    summary_frame = _mapping(candidate_research_summary_frame or payload.get("candidateResearchSummaryFrame"))
    context_frame = _mapping(scanner_context_frame or payload.get("scannerContextFrame"))

    entries = [
        _build_domain_entry(
            domain,
            candidate=payload,
            candidate_evidence_frame=evidence_frame,
            candidate_research_readiness=readiness,
            candidate_research_summary_frame=summary_frame,
            scanner_context_frame=context_frame,
        )
        for domain in SCANNER_SOURCE_PROVENANCE_DOMAIN_ORDER
    ]
    return summarize_source_provenance(entries)


__all__ = [
    "SCANNER_SOURCE_PROVENANCE_DOMAIN_ORDER",
    "build_market_scanner_source_provenance_sidecar",
]
