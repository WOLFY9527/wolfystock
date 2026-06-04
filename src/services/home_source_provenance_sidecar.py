# -*- coding: utf-8 -*-
"""Helper-only Home provenance sidecar builder."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.services.source_provenance_contract import build_source_provenance


HOME_SOURCE_PROVENANCE_DOMAIN_ORDER = (
    "priceHistory",
    "technicals",
    "fundamentals",
    "earnings",
    "filings",
    "news",
    "catalysts",
    "sentiment",
    "valuation",
    "sectorTheme",
    "macroLiquidity",
)

_STATUS_BLOCKED = {"blocked", "pending"}
_STATUS_DEGRADED = {"degraded", "partial"}
_FORBIDDEN_TEXT_MARKERS = (
    "authorization",
    "api_key",
    "apikey",
    "bearer",
    "broker",
    "cache_key",
    "cookie",
    "internal_env",
    "order",
    "payload",
    "prompt",
    "raw",
    "router_debug",
    "secret",
    "session",
    "stack trace",
    "submit order",
    "token",
    "traceback",
    "trade",
)
_FIXTURE_MARKERS = ("fixture", "demo", "synthetic", "mock", "stub")
_PROXY_MARKERS = ("proxy", "fallback", "cache", "snapshot", "delayed")


def build_home_source_provenance_sidecar_v1(value: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    payload = _mapping(value)
    packet = _mapping(payload.get("singleStockEvidencePacket"))
    packet_domains = _mapping(packet.get("domains"))
    citation = _mapping(
        _first_present(
            payload.get("evidenceCitationFrame"),
            payload.get("homeReportEvidenceCitationFrame"),
            payload.get("home_report_evidence_citation_frame"),
        )
    )
    citation_coverage = _index_by_domain(citation.get("domainCoverage"))
    cited_evidence = _index_first_citation(citation.get("citedEvidence"))
    source_metadata = _mapping(payload.get("sourceMetadataByDomain"))
    payload_debug_ref = _safe_text(_first_present(payload.get("debugRef"), packet.get("debugRef")), limit=64)

    entries: list[dict[str, Any]] = []
    for domain in HOME_SOURCE_PROVENANCE_DOMAIN_ORDER:
        domain_packet = _mapping(packet_domains.get(domain))
        domain_source = _mapping(source_metadata.get(domain))
        domain_coverage = _mapping(citation_coverage.get(domain))
        domain_citation = _mapping(cited_evidence.get(domain))
        domain_status = _status(domain_packet.get("status"))
        fail_closed_unknown = domain_status in _STATUS_BLOCKED or _has_unknown_source_reason(
            domain_packet.get("missingReasons")
        )

        source_id = None if fail_closed_unknown else _safe_source_id(
            _first_present(
                domain_source.get("sourceId"),
                domain_source.get("source_id"),
                domain_source.get("source"),
                domain_packet.get("sourceId"),
                domain_packet.get("source"),
                domain_citation.get("sourceId"),
            )
        )
        source_label = None if fail_closed_unknown else _safe_label(
            _first_present(
                domain_source.get("sourceLabel"),
                domain_source.get("source_label"),
                domain_source.get("label"),
                domain_packet.get("sourceLabel"),
                domain_packet.get("source"),
                domain_citation.get("sourceLabel"),
                domain_citation.get("sourceId"),
            )
        )
        authority_tier = _authority_tier(
            _first_present(
                domain_source.get("authorityTier"),
                domain_source.get("providerAuthority"),
                domain_source.get("sourceAuthority"),
                domain_packet.get("providerAuthority"),
                domain_coverage.get("authorityLabel"),
            ),
            domain_packet=domain_packet,
        )
        freshness_state = _freshness_state(
            _first_present(
                domain_source.get("freshnessState"),
                domain_source.get("freshness"),
                domain_packet.get("freshness"),
                domain_coverage.get("freshness"),
                domain_coverage.get("freshnessLabel"),
                domain_citation.get("freshness"),
            )
        )
        source_tier = _source_tier(
            _first_present(
                domain_source.get("sourceTier"),
                domain_source.get("source_type"),
                domain_source.get("sourceType"),
                domain_packet.get("sourceTier"),
            ),
            source_id=source_id,
            source_label=source_label,
        )
        limitations = _limit_list(
            [
                *(_sequence(domain_source.get("limitations"))),
                *(_sequence(domain_packet.get("missingReasons"))),
                *(_sequence(domain_coverage.get("missingReasons"))),
                *(_sequence(domain_coverage.get("notes"))),
                domain_citation.get("limitation"),
            ]
        )
        next_evidence_needed = _limit_list(
            [
                *(_sequence(domain_source.get("nextEvidenceNeeded"))),
                *(_sequence(domain_packet.get("nextEvidenceNeeded"))),
            ]
        )
        fallback_or_proxy = _fallback_or_proxy(
            source_id=source_id,
            source_label=source_label,
            source_tier=source_tier,
            freshness_state=freshness_state,
            status=domain_status,
            values=(
                domain_source.get("fallbackOrProxy"),
                domain_source.get("isFallback"),
                domain_source.get("proxyOnly"),
                domain_packet.get("fallbackOrProxy"),
            ),
            limitations=limitations,
        )
        observation_only = _bool(
            _first_present(
                domain_source.get("observationOnly"),
                domain_packet.get("observationOnly"),
            )
        )
        score_allowed = _bool(
            _first_present(
                domain_source.get("scoreContributionAllowed"),
                domain_packet.get("scoreContributionAllowed"),
            )
        )
        if fail_closed_unknown or fallback_or_proxy or freshness_state in {"stale", "fallback", "synthetic", "unavailable", "unknown"}:
            observation_only = True
            score_allowed = False
        debug_ref = _first_present(
            domain_source.get("debugRef"),
            domain_citation.get("id"),
            f"{payload_debug_ref or 'home'}-{domain}",
        )

        entry = build_source_provenance(
            source_id=source_id,
            source_label=source_label,
            evidence_domain="research",
            authority_tier=authority_tier,
            freshness_state=freshness_state,
            source_tier=source_tier,
            fallback_or_proxy=fallback_or_proxy,
            observation_only=observation_only,
            score_contribution_allowed=score_allowed,
            limitations=limitations or None,
            next_evidence_needed=next_evidence_needed or None,
            debug_ref=debug_ref,
        )
        entry["evidenceDomain"] = domain
        if fail_closed_unknown:
            entry["limitations"] = limitations or ["unknown_source"]
            entry["nextEvidenceNeeded"] = next_evidence_needed or ["verified_source_metadata"]
        entries.append(entry)

    return entries


def _index_by_domain(value: Any) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in _sequence(value):
        mapping = _mapping(item)
        domain = _domain(mapping.get("domain"))
        if domain:
            indexed[domain] = mapping
    return indexed


def _index_first_citation(value: Any) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in _sequence(value):
        mapping = _mapping(item)
        domain = _domain(mapping.get("domain"))
        if domain and domain not in indexed:
            indexed[domain] = mapping
    return indexed


def _authority_tier(value: Any, *, domain_packet: Mapping[str, Any]) -> str:
    normalized = _normalize_key(value)
    if normalized in {"scoregradeallowed", "score_grade_allowed", "scoregrade", "score_grade"}:
        return "score_grade"
    if normalized in {"observationonly", "observation_only", "observe_only"}:
        return "observation_only"
    if normalized in {"trustedpublic", "trusted_public", "official", "official_public"}:
        return "trusted_public"
    if normalized in {"storedsnapshot", "stored_snapshot", "cache_snapshot"}:
        return "stored_snapshot"
    if any(marker in normalized for marker in _FIXTURE_MARKERS):
        return "fixture"
    if _status(domain_packet.get("status")) in _STATUS_BLOCKED | _STATUS_DEGRADED:
        return "observation_only"
    return "unknown"


def _freshness_state(value: Any) -> str:
    normalized = _normalize_key(value)
    if normalized in {"fresh", "live", "realtime"}:
        return "fresh"
    if normalized in {"cached", "cache"}:
        return "cached"
    if normalized in {"delayed", "late"}:
        return "delayed"
    if normalized in {"partial"}:
        return "partial"
    if normalized in {"stale"}:
        return "stale"
    if normalized in {"fallback"}:
        return "fallback"
    if normalized in {"fixture", "demo", "synthetic"}:
        return "synthetic"
    if normalized in {"missing", "unavailable"}:
        return "unavailable"
    return "unknown"


def _source_tier(value: Any, *, source_id: str, source_label: str) -> str:
    normalized = _normalize_key(value)
    joined = f"{source_id} {source_label}".lower()
    if normalized in {"authorizedlicensedfeed", "authorized_licensed_feed", "authorizedfeed", "authorized_feed"}:
        return "authorized_licensed_feed"
    if normalized in {"scoregrade", "score_grade"}:
        return "authorized_licensed_feed"
    if normalized in {"officialpublic", "official_public", "exchangepublic", "exchange_public"}:
        return "official_public"
    if normalized in {"publicproxy", "public_proxy", "unofficialproxy", "unofficial_proxy"}:
        return "public_proxy"
    if normalized in {"unofficialpublicapi", "unofficial_public_api", "unofficialpublic", "proxy"}:
        return "public_proxy"
    if normalized in {"fallbackstatic", "fallback_static", "fallback"}:
        return "fallback_static"
    if normalized in {"cachesnapshot", "cache_snapshot", "storedsnapshot", "stored_snapshot"}:
        return "cache_snapshot"
    if normalized in {"syntheticfixture", "synthetic_fixture", "fixture", "demo"}:
        return "synthetic_fixture"
    if any(marker in joined for marker in _FIXTURE_MARKERS):
        return "synthetic_fixture"
    if any(marker in joined for marker in _PROXY_MARKERS):
        return "public_proxy"
    return "unknown"


def _fallback_or_proxy(
    *,
    source_id: str,
    source_label: str,
    source_tier: str,
    freshness_state: str,
    status: str,
    values: Sequence[Any],
    limitations: Sequence[str],
) -> bool:
    if any(_bool(value) for value in values):
        return True
    joined = f"{source_id} {source_label} {' '.join(limitations)}".lower()
    if any(marker in joined for marker in _FIXTURE_MARKERS + _PROXY_MARKERS):
        return True
    if source_tier in {"public_proxy", "fallback_static", "cache_snapshot", "synthetic_fixture"}:
        return True
    if freshness_state in {"fallback", "synthetic"}:
        return True
    if status in _STATUS_BLOCKED:
        return True
    return False


def _limit_list(values: Sequence[Any]) -> list[str]:
    items: list[str] = []
    for value in values:
        text = _safe_text(value, limit=64).lower().replace(" ", "_")
        if text and text not in items:
            items.append(text)
    return items


def _has_unknown_source_reason(values: Any) -> bool:
    normalized = _limit_list(_sequence(values))
    return any(
        reason in {"fundamental_context_unavailable", "provider_timeout", "unsupported_market"}
        for reason in normalized
    )


def _safe_source_id(value: Any) -> str | None:
    text = _safe_text(value, limit=64)
    return text or None


def _safe_label(value: Any) -> str | None:
    text = _safe_text(value, limit=80)
    return text or None


def _domain(value: Any) -> str:
    text = _safe_text(value, limit=32)
    return text if text in HOME_SOURCE_PROVENANCE_DOMAIN_ORDER else ""


def _status(value: Any) -> str:
    text = _safe_text(value, limit=24).lower()
    if text in {"ok", "ready", "available"}:
        return "available"
    if text in {"partial", "degraded", "stale", "delayed"}:
        return "degraded"
    if text in {"blocked", "timeout", "failed", "error"}:
        return "blocked"
    if text in {"pending", "waiting"}:
        return "pending"
    if text in {"missing", "unsupported", "not_supported", "unavailable"}:
        return "missing"
    return ""


def _safe_text(value: Any, *, limit: int) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).strip().split())
    lowered = text.lower()
    if not text or any(marker in lowered for marker in _FORBIDDEN_TEXT_MARKERS):
        return ""
    return text[:limit]


def _normalize_key(value: Any) -> str:
    return "".join(ch for ch in _safe_text(value, limit=80).lower() if ch.isalnum() or ch == "_")


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


__all__ = [
    "HOME_SOURCE_PROVENANCE_DOMAIN_ORDER",
    "build_home_source_provenance_sidecar_v1",
]
