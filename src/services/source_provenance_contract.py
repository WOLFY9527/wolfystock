# -*- coding: utf-8 -*-
"""Pure helper-only source provenance contract skeleton.

This module is intentionally inert. It does not import provider clients, read
settings, touch caches, call networks, or alter any runtime DTO behavior.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from src.contracts.evidence.source_observation import (
    SourceClass,
    SourceObservationFacts,
)


SOURCE_PROVENANCE_CONTRACT_VERSION = "source_provenance_v1"

_DEFAULT_ENTRY = {
    "contractVersion": SOURCE_PROVENANCE_CONTRACT_VERSION,
    "sourceId": "unknown_source",
    "sourceLabel": "未知来源",
    "evidenceDomain": "general",
    "authorityTier": "unknown",
    "freshnessState": "unknown",
    "sourceTier": "unknown",
    "fallbackOrProxy": True,
    "observationOnly": True,
    "scoreContributionAllowed": False,
    "limitations": ["unknown_source"],
    "nextEvidenceNeeded": ["verified_source_metadata"],
    "debugRef": "source-provenance:unknown",
}

_FRESHNESS_ALIASES = {
    "fresh": "fresh",
    "live": "live",
    "cached": "cached",
    "delayed": "delayed",
    "partial": "partial",
    "stale": "stale",
    "fallback": "fallback",
    "synthetic": "synthetic",
    "fixture": "synthetic",
    "demo": "synthetic",
    "unavailable": "unavailable",
    "missing": "unavailable",
    "unknown": "unknown",
}

_AUTHORITY_ALIASES = {
    "score_grade": "score_grade",
    "scoregrade": "score_grade",
    "score_grade_allowed": "score_grade",
    "authorized": "score_grade",
    "official": "trusted_public",
    "official_public": "trusted_public",
    "trusted_public": "trusted_public",
    "cache_snapshot": "stored_snapshot",
    "stored_snapshot": "stored_snapshot",
    "observation_only": "observation_only",
    "manual_review": "observation_only",
    "fixture": "fixture",
    "demo": "fixture",
    "synthetic": "fixture",
    "unknown": "unknown",
    "unavailable": "unknown",
}

_SOURCE_TIER_ALIASES = {
    "authorized_licensed_feed": "authorized_feed",
    "authorized_feed": "authorized_feed",
    "official_public": "official_public",
    "exchange_public": "official_public",
    "public_proxy": "proxy",
    "unofficial_proxy": "proxy",
    "proxy": "proxy",
    "cache_snapshot": "stored_snapshot",
    "stored_snapshot": "stored_snapshot",
    "fallback_static": "fallback",
    "fallback": "fallback",
    "synthetic_fixture": "fixture",
    "synthetic": "synthetic",
    "first_party": "first_party",
    "third_party": "third_party",
    "delayed_fixture": "fixture",
    "malformed_fixture": "fixture",
    "disabled_live_stub": "fixture",
    "fixture": "fixture",
    "demo": "fixture",
    "missing": "unknown",
    "unknown": "unknown",
}

_DOMAIN_ALIASES = {
    "general": "general",
    "quote": "market_data",
    "quotes": "market_data",
    "market_data": "market_data",
    "technicals": "market_data",
    "fundamentals": "fundamentals",
    "macro": "macro",
    "news": "news",
    "research": "research",
    "scanner": "research",
    "options": "derivatives",
    "derivatives": "derivatives",
    "portfolio": "portfolio",
    "risk": "portfolio",
}

_SANITIZE_VALUE_MARKERS = (
    "token",
    "secret",
    "credential",
    "api_key",
    "apikey",
    "password",
    "cookie",
    "session",
    "env",
    "router",
    "provider",
    "payload",
    "trace",
    "stack",
    "debug",
    "internal",
    "cache",
    "raw",
)

_SANITIZE_LABEL_MARKERS = (
    "token",
    "secret",
    "credential",
    "password",
    "cookie",
    "session",
    "env",
    "payload",
    "trace",
    "stack",
    "debug",
    "internal",
    "raw",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_key(value: Any) -> str:
    text = _text(value).lower()
    return "_".join(part for part in text.replace("-", "_").replace("/", "_").split("_") if part)


def _has_sensitive_marker(text: str, markers: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in markers)


def _sanitize_source_id(value: Any) -> str:
    normalized = _normalize_key(value)
    if not normalized or _has_sensitive_marker(normalized, _SANITIZE_VALUE_MARKERS):
        return "unknown_source"
    return normalized[:64]


def _sanitize_source_label(value: Any) -> str:
    text = " ".join(_text(value).split())
    if not text or _has_sensitive_marker(text, _SANITIZE_LABEL_MARKERS):
        return "未知来源"
    return text[:80]


def _sanitize_debug_ref(value: Any) -> str:
    text = _text(value)
    if text.lower().startswith("source-provenance:"):
        text = text.split(":", 1)[1]
    normalized = _normalize_key(text)
    if not normalized:
        return "source-provenance:unknown"
    parts = [part for part in normalized.split("_") if not _has_sensitive_marker(part, _SANITIZE_VALUE_MARKERS)]
    if not parts:
        return "source-provenance:unknown"
    return f"source-provenance:{'-'.join(parts[:4])}"


def _normalize_choice(value: Any, mapping: Mapping[str, str], *, default: str) -> str:
    return mapping.get(_normalize_key(value), default)


def _normalize_freshness(value: Any) -> str:
    return _normalize_choice(value, _FRESHNESS_ALIASES, default="unknown")


def _normalize_authority(value: Any) -> str:
    return _normalize_choice(value, _AUTHORITY_ALIASES, default="unknown")


def _normalize_source_tier(value: Any) -> str:
    return _normalize_choice(value, _SOURCE_TIER_ALIASES, default="unknown")


def _normalize_domain(value: Any) -> str:
    return _normalize_choice(value, _DOMAIN_ALIASES, default="general")


def _normalize_limitations(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        raw_values = [values]
    elif isinstance(values, Iterable):
        raw_values = list(values)
    else:
        raw_values = []
    cleaned: list[str] = []
    for value in raw_values:
        normalized = _normalize_key(value)
        if not normalized or _has_sensitive_marker(normalized, _SANITIZE_VALUE_MARKERS):
            continue
        cleaned.append(normalized[:64])
    return list(dict.fromkeys(cleaned))


def _normalize_next_evidence(values: Any) -> list[str]:
    if values is None:
        return ["verified_source_metadata"]
    cleaned = _normalize_limitations(values)
    return cleaned or ["verified_source_metadata"]


def _derive_limitations(
    *,
    authority_tier: str,
    freshness_state: str,
    source_tier: str,
    fallback_or_proxy: bool,
    observation_only: bool,
) -> list[str]:
    limitations: list[str] = []
    if authority_tier == "unknown" or source_tier == "unknown":
        limitations.append("unknown_source")
    if freshness_state in {"stale", "fallback", "unavailable", "unknown"}:
        limitations.append(f"{freshness_state}_source")
    if source_tier in {"proxy", "fallback", "fixture"} or fallback_or_proxy:
        limitations.append("fallback_or_proxy_source")
    if observation_only:
        limitations.append("observation_only")
    return list(dict.fromkeys(limitations)) or ["unknown_source"]


def build_source_provenance(
    *,
    source_id: Any = None,
    source_label: Any = None,
    evidence_domain: Any = None,
    authority_tier: Any = None,
    freshness_state: Any = None,
    source_tier: Any = None,
    fallback_or_proxy: Any = None,
    observation_only: Any = None,
    score_contribution_allowed: Any = None,
    limitations: Any = None,
    next_evidence_needed: Any = None,
    debug_ref: Any = None,
    source_observation: SourceObservationFacts | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    facts = _coerce_source_observation(source_observation)
    if facts is not None:
        canonical_source_id = facts.identity.source_id
        canonical_freshness = facts.freshness.value
        canonical_source_tier = _source_tier_from_identity(facts)
        if source_id is not None and _text(source_id) != canonical_source_id:
            raise ValueError("sourceId conflicts with sourceObservation")
        if freshness_state is not None and _normalize_freshness(freshness_state) != canonical_freshness:
            raise ValueError("freshnessState conflicts with sourceObservation")
        if source_tier is not None and _normalize_source_tier(source_tier) != canonical_source_tier:
            raise ValueError("sourceTier conflicts with sourceObservation")
        source_id = canonical_source_id
        freshness_state = canonical_freshness
        source_tier = canonical_source_tier
        fallback_or_proxy = bool(fallback_or_proxy) or facts.identity.is_proxy

    entry = dict(_DEFAULT_ENTRY)
    normalized_source_id = _sanitize_source_id(source_id)
    normalized_source_label = _sanitize_source_label(source_label)
    normalized_domain = _normalize_domain(evidence_domain)
    normalized_authority = _normalize_authority(authority_tier)
    normalized_freshness = _normalize_freshness(freshness_state)
    normalized_source_tier = _normalize_source_tier(source_tier)

    derived_fallback = normalized_source_tier in {"proxy", "fallback", "fixture"} or normalized_freshness == "fallback"
    fallback_flag = bool(fallback_or_proxy) or derived_fallback or normalized_source_id == "unknown_source"
    observation_flag = bool(observation_only) or normalized_authority != "score_grade"
    score_allowed = bool(score_contribution_allowed)

    if normalized_authority != "score_grade":
        score_allowed = False
    if fallback_flag or normalized_freshness not in {"live", "fresh", "cached"}:
        score_allowed = False
    if normalized_source_tier in {"proxy", "fallback", "synthetic", "fixture", "unknown"}:
        score_allowed = False
    if normalized_source_id == "unknown_source":
        normalized_authority = "unknown"
        normalized_freshness = "unknown"
        normalized_source_tier = "unknown"
        fallback_flag = True
        observation_flag = True
        normalized_limitations = ["unknown_source"]
        normalized_next = ["verified_source_metadata"]
        normalized_debug_ref = "source-provenance:unknown"
    else:
        normalized_limitations = (
            _derive_limitations(
                authority_tier=normalized_authority,
                freshness_state=normalized_freshness,
                source_tier=normalized_source_tier,
                fallback_or_proxy=fallback_flag,
                observation_only=observation_flag,
            )
            if limitations is None
            else _normalize_limitations(limitations)
        )
        normalized_next = _normalize_next_evidence(next_evidence_needed)
        normalized_debug_ref = _sanitize_debug_ref(debug_ref or normalized_source_id)

    entry.update(
        {
            "sourceId": normalized_source_id,
            "sourceLabel": normalized_source_label,
            "evidenceDomain": normalized_domain,
            "authorityTier": normalized_authority,
            "freshnessState": normalized_freshness,
            "sourceTier": normalized_source_tier,
            "fallbackOrProxy": fallback_flag,
            "observationOnly": observation_flag,
            "scoreContributionAllowed": score_allowed,
            "limitations": normalized_limitations,
            "nextEvidenceNeeded": normalized_next,
            "debugRef": normalized_debug_ref,
        }
    )
    if facts is not None:
        entry["sourceObservation"] = facts.to_dict()
    return entry


def _coerce_source_observation(
    value: SourceObservationFacts | Mapping[str, Any] | None,
) -> SourceObservationFacts | None:
    if value is None:
        return None
    if isinstance(value, SourceObservationFacts):
        return value
    if isinstance(value, Mapping):
        return SourceObservationFacts.from_dict(value)
    raise TypeError("source_observation must be SourceObservationFacts, a mapping, or None")


def _source_tier_from_identity(facts: SourceObservationFacts) -> str:
    identity = facts.identity
    if identity.is_fixture:
        return "fixture"
    if identity.is_synthetic:
        return "synthetic"
    if identity.is_proxy:
        return "proxy"
    return {
        SourceClass.OFFICIAL: "official_public",
        SourceClass.LICENSED: "authorized_feed",
        SourceClass.FIRST_PARTY: "first_party",
        SourceClass.THIRD_PARTY: "third_party",
        SourceClass.UNKNOWN: "unknown",
    }[identity.source_class]


def build_unknown_source_provenance(*, evidence_domain: Any = "general", debug_ref: Any = None) -> dict[str, Any]:
    return build_source_provenance(evidence_domain=evidence_domain, debug_ref=debug_ref)


def build_stale_source_provenance(
    *,
    source_id: Any,
    source_label: Any,
    evidence_domain: Any = "general",
    authority_tier: Any = "trusted_public",
    source_tier: Any = "official_public",
    debug_ref: Any = None,
) -> dict[str, Any]:
    return build_source_provenance(
        source_id=source_id,
        source_label=source_label,
        evidence_domain=evidence_domain,
        authority_tier=authority_tier,
        freshness_state="stale",
        source_tier=source_tier,
        fallback_or_proxy=False,
        observation_only=True,
        score_contribution_allowed=False,
        limitations=["stale_source"],
        next_evidence_needed=["fresh_authoritative_snapshot"],
        debug_ref=debug_ref,
    )


def build_fallback_proxy_source_provenance(
    *,
    source_id: Any,
    source_label: Any,
    evidence_domain: Any = "general",
    freshness_state: Any = "fallback",
    source_tier: Any = "public_proxy",
    debug_ref: Any = None,
) -> dict[str, Any]:
    return build_source_provenance(
        source_id=source_id,
        source_label=source_label,
        evidence_domain=evidence_domain,
        authority_tier="observation_only",
        freshness_state=freshness_state,
        source_tier=source_tier,
        fallback_or_proxy=True,
        observation_only=True,
        score_contribution_allowed=False,
        limitations=["fallback_or_proxy_source"],
        next_evidence_needed=["authorized_primary_source"],
        debug_ref=debug_ref,
    )


def build_observation_only_source_provenance(
    *,
    source_id: Any,
    source_label: Any,
    evidence_domain: Any = "general",
    freshness_state: Any = "cached",
    source_tier: Any = "cache_snapshot",
    debug_ref: Any = None,
) -> dict[str, Any]:
    return build_source_provenance(
        source_id=source_id,
        source_label=source_label,
        evidence_domain=evidence_domain,
        authority_tier="observation_only",
        freshness_state=freshness_state,
        source_tier=source_tier,
        fallback_or_proxy=False,
        observation_only=True,
        score_contribution_allowed=False,
        limitations=["observation_only"],
        next_evidence_needed=["score_grade_authority_source"],
        debug_ref=debug_ref,
    )


def build_score_grade_source_provenance(
    *,
    source_id: Any,
    source_label: Any,
    evidence_domain: Any = "general",
    freshness_state: Any = "fresh",
    source_tier: Any = "authorized_licensed_feed",
    debug_ref: Any = None,
) -> dict[str, Any]:
    return build_source_provenance(
        source_id=source_id,
        source_label=source_label,
        evidence_domain=evidence_domain,
        authority_tier="score_grade",
        freshness_state=freshness_state,
        source_tier=source_tier,
        fallback_or_proxy=False,
        observation_only=False,
        score_contribution_allowed=True,
        limitations=[],
        next_evidence_needed=[],
        debug_ref=debug_ref,
    )


def build_fixture_demo_source_provenance(
    *,
    source_id: Any = "fixture_demo",
    source_label: Any = "Fixture Demo",
    evidence_domain: Any = "general",
    debug_ref: Any = None,
) -> dict[str, Any]:
    return build_source_provenance(
        source_id=source_id,
        source_label=source_label,
        evidence_domain=evidence_domain,
        authority_tier="fixture",
        freshness_state="synthetic",
        source_tier="synthetic_fixture",
        fallback_or_proxy=True,
        observation_only=True,
        score_contribution_allowed=False,
        limitations=["synthetic_source", "demo_only"],
        next_evidence_needed=["real_world_authoritative_source"],
        debug_ref=debug_ref,
    )


def summarize_source_provenance(entries: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    normalized_entries = [
        build_source_provenance(
            source_id=entry.get("sourceId"),
            source_label=entry.get("sourceLabel"),
            evidence_domain=entry.get("evidenceDomain"),
            authority_tier=entry.get("authorityTier"),
            freshness_state=entry.get("freshnessState"),
            source_tier=entry.get("sourceTier"),
            fallback_or_proxy=entry.get("fallbackOrProxy"),
            observation_only=entry.get("observationOnly"),
            score_contribution_allowed=entry.get("scoreContributionAllowed"),
            limitations=entry.get("limitations"),
            next_evidence_needed=entry.get("nextEvidenceNeeded"),
            debug_ref=entry.get("debugRef"),
        )
        for entry in entries
        if isinstance(entry, Mapping)
    ]
    normalized_entries = sorted(normalized_entries, key=lambda item: (item["sourceId"], item["debugRef"], item["evidenceDomain"]))
    authority_counts: dict[str, int] = {}
    freshness_counts: dict[str, int] = {}
    domain_counts: dict[str, int] = {}
    for entry in normalized_entries:
        authority_counts[entry["authorityTier"]] = authority_counts.get(entry["authorityTier"], 0) + 1
        freshness_counts[entry["freshnessState"]] = freshness_counts.get(entry["freshnessState"], 0) + 1
        domain_counts[entry["evidenceDomain"]] = domain_counts.get(entry["evidenceDomain"], 0) + 1
    return {
        "contractVersion": SOURCE_PROVENANCE_CONTRACT_VERSION,
        "entryCount": len(normalized_entries),
        "authorityTierCounts": dict(sorted(authority_counts.items())),
        "freshnessStateCounts": dict(sorted(freshness_counts.items())),
        "evidenceDomainCounts": dict(sorted(domain_counts.items())),
        "fallbackOrProxyCount": sum(1 for entry in normalized_entries if entry["fallbackOrProxy"]),
        "observationOnlyCount": sum(1 for entry in normalized_entries if entry["observationOnly"]),
        "scoreContributionAllowedCount": sum(1 for entry in normalized_entries if entry["scoreContributionAllowed"]),
        "entries": normalized_entries,
    }


def build_source_provenance_sidecar(
    *,
    contract_version: str,
    entries: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    sidecar_entries = list(entries)
    summary = summarize_source_provenance(sidecar_entries)
    return {
        "contractVersion": contract_version,
        "sourceProvenanceContractVersion": SOURCE_PROVENANCE_CONTRACT_VERSION,
        "entryCount": summary["entryCount"],
        "authorityTierCounts": summary["authorityTierCounts"],
        "freshnessStateCounts": summary["freshnessStateCounts"],
        "evidenceDomainCounts": summary["evidenceDomainCounts"],
        "fallbackOrProxyCount": summary["fallbackOrProxyCount"],
        "observationOnlyCount": summary["observationOnlyCount"],
        "scoreContributionAllowedCount": summary["scoreContributionAllowedCount"],
        "entries": sidecar_entries,
    }


__all__ = [
    "SOURCE_PROVENANCE_CONTRACT_VERSION",
    "build_fixture_demo_source_provenance",
    "build_fallback_proxy_source_provenance",
    "build_observation_only_source_provenance",
    "build_score_grade_source_provenance",
    "build_source_provenance",
    "build_source_provenance_sidecar",
    "build_stale_source_provenance",
    "build_unknown_source_provenance",
    "summarize_source_provenance",
]
