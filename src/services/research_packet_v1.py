# -*- coding: utf-8 -*-
"""Pure Research Packet v1 projection helper.

This helper only consumes caller-supplied sidecars and metadata. It must stay
inert: no provider runtime, API, cache, storage, config, network, or frontend
imports belong here.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any


RESEARCH_PACKET_V1_VERSION = "research_packet_v1"

RESEARCH_PACKET_V1_LANES = (
    "priceHistory",
    "technicals",
    "fundamentals",
    "earnings",
    "filings",
    "newsCatalysts",
    "sentiment",
    "valuation",
    "sectorTheme",
    "macroLiquidity",
)

_LANE_SOURCE_DOMAINS = {
    "priceHistory": ("priceHistory",),
    "technicals": ("technicals",),
    "fundamentals": ("fundamentals",),
    "earnings": ("earnings",),
    "filings": ("filings",),
    "newsCatalysts": ("news", "catalysts", "newsCatalysts"),
    "sentiment": ("sentiment",),
    "valuation": ("valuation",),
    "sectorTheme": ("sectorTheme",),
    "macroLiquidity": ("macroLiquidity",),
}
_DOMAIN_TO_LANE = {
    domain: lane
    for lane, domains in _LANE_SOURCE_DOMAINS.items()
    for domain in domains
}
_LANE_NEXT_EVIDENCE = {
    "priceHistory": "等待价格历史证据更新。",
    "technicals": "等待技术面证据更新。",
    "fundamentals": "等待基本面证据更新。",
    "earnings": "等待财报证据更新。",
    "filings": "等待披露文件证据更新。",
    "newsCatalysts": "等待新闻与催化剂证据更新。",
    "sentiment": "等待情绪证据更新。",
    "valuation": "等待估值证据更新。",
    "sectorTheme": "等待行业主题证据更新。",
    "macroLiquidity": "等待宏观流动性证据更新。",
}
_CONSUMER_COPY = {
    "AVAILABLE": "数据可用于研究观察。",
    "UPDATING": "数据更新中，稍后将自动刷新。",
    "DELAYED": "已使用最近一次可用数据。",
    "PARTIAL": "部分数据暂不可用，当前评分已暂停。",
    "INSUFFICIENT": "当前信号置信度较低，仅供观察。",
    "PAUSED": "当前信号置信度较低，仅供观察。",
    "UNAVAILABLE": "本模块暂不可用，请稍后重试。",
}
_FRESHNESS_RANK = {
    "fresh": 0,
    "live": 0,
    "cached": 1,
    "delayed": 2,
    "partial": 3,
    "stale": 4,
    "fallback": 5,
    "synthetic": 6,
    "unavailable": 7,
    "unknown": 8,
}
_STATUS_MISSING = {
    "blocked",
    "empty",
    "error",
    "failed",
    "missing",
    "not_configured",
    "not_supported",
    "skipped",
    "timeout",
    "timed_out",
    "unavailable",
    "unsupported",
}
_STATUS_UPDATING = {"loading", "pending", "queued", "scheduled", "updating", "waiting"}
_STATUS_DEGRADED = {"cached", "degraded", "delayed", "fallback", "partial", "stale", "weak"}
_DEGRADED_FRESHNESS = {
    "cached",
    "delayed",
    "fallback",
    "partial",
    "stale",
    "synthetic",
    "unavailable",
    "unknown",
}
_FORBIDDEN_TEXT_MARKERS = (
    "api key",
    "api_key",
    "apikey",
    "authorization",
    "authorized_licensed_feed",
    "bearer",
    "cache",
    "cookie",
    "diagnostic",
    "fallback_static",
    "internal_env",
    "official_public",
    "polygon",
    "provider",
    "public_proxy",
    "raw",
    "reasoncode",
    "reasonfamilies",
    "remediation",
    "runtime",
    "scorecontributionallowed",
    "secret",
    "sourceauthorityallowed",
    "sourcetier",
    "sourcetype",
    "stack trace",
    "synthetic_fixture",
    "token",
    "trace",
    "traceback",
    "tushare",
    "unofficial_proxy",
)
_FORBIDDEN_ACTION_TEXT_RE = re.compile(
    r"\b(?:buy|sell|hold|recommend(?:ation|ed)?|target(?: price)?|stop(?: loss)?|position[-\s]?sizing)\b|"
    r"买入|卖出|持有|推荐|交易建议|投资建议|目标价|止损|止盈|仓位|下单|立即交易|必买|稳赚|保证收益",
    re.IGNORECASE,
)
_SAFE_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-:.#")


def build_research_packet_v1(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Project caller-supplied single-stock sidecars into Research Packet v1."""

    payload = _mapping(value)
    identity = _packet_identity(payload)
    research_readiness = _mapping(payload.get("researchReadiness"))
    evidence_coverage = _mapping(payload.get("evidenceCoverageFrame"))
    single_stock_packet = _mapping(payload.get("singleStockEvidencePacket"))
    citation_frame = _mapping(payload.get("evidenceCitationFrame"))
    source_provenance = _sequence(payload.get("sourceProvenanceFrame"))
    data_rows = _sequence(payload.get("dataCoverageRows"))

    row_refs_by_lane, sanitized_rows = _data_coverage_rows(data_rows)
    citation_index = _citations_by_lane(citation_frame.get("citedEvidence"))
    coverage_index = _coverage_by_lane(evidence_coverage, citation_frame.get("domainCoverage"))
    packet_domains = _mapping(single_stock_packet.get("domains"))
    provenance_index = _provenance_by_lane(source_provenance)
    missing_readiness_lanes = _readiness_missing_lanes(research_readiness)

    lanes: dict[str, dict[str, Any]] = {}
    for lane_name in RESEARCH_PACKET_V1_LANES:
        lane = _build_lane(
            lane_name=lane_name,
            row_ref=row_refs_by_lane.get(lane_name),
            packet_domains=packet_domains,
            coverage_index=coverage_index,
            citation_index=citation_index,
            provenance_index=provenance_index,
            missing_readiness_lanes=missing_readiness_lanes,
        )
        lanes[lane_name] = lane

    evidence_citations = _evidence_citations(citation_index, lanes)
    consumer_projection = _consumer_projection(lanes, identity)

    return {
        "contractVersion": RESEARCH_PACKET_V1_VERSION,
        "packetIdentity": identity,
        "runtimePosture": _runtime_posture(),
        "lanes": lanes,
        "sourceProvenanceSummary": _source_provenance_summary(source_provenance, lanes),
        "evidenceCitations": evidence_citations,
        "dataCoverageRows": sanitized_rows,
        "redactionPosture": _redaction_posture(),
        "noAdviceBoundary": _no_advice_boundary(),
        "consumerProjection": consumer_projection,
    }


def _build_lane(
    *,
    lane_name: str,
    row_ref: Mapping[str, Any] | None,
    packet_domains: Mapping[str, Any],
    coverage_index: Mapping[str, Sequence[Mapping[str, Any]]],
    citation_index: Mapping[str, Sequence[Mapping[str, Any]]],
    provenance_index: Mapping[str, Sequence[Mapping[str, Any]]],
    missing_readiness_lanes: set[str],
) -> dict[str, Any]:
    packet_blocks = [_mapping(packet_domains.get(domain)) for domain in _LANE_SOURCE_DOMAINS[lane_name]]
    coverage_blocks = list(coverage_index.get(lane_name, ()))
    citation_blocks = list(citation_index.get(lane_name, ()))
    provenance_blocks = list(provenance_index.get(lane_name, ()))
    blocks = [*packet_blocks, *coverage_blocks, *citation_blocks, *provenance_blocks]

    row = _mapping(row_ref)
    row_ref_id = _optional_text(row.get("rowRef"))
    freshness = _lane_freshness(blocks, row)
    coverage = _lane_coverage(blocks, lane_name in missing_readiness_lanes)
    evidence_refs = _lane_evidence_refs(packet_blocks, coverage_blocks, citation_blocks)
    degraded = _lane_is_degraded(blocks, row=row, freshness=freshness, coverage=coverage)
    right_to_display = _lane_right_to_display(row=row, degraded=degraded, has_evidence=bool(evidence_refs))
    status, consumer_state = _lane_status(
        blocks=blocks,
        coverage=coverage,
        freshness=freshness,
        right_to_display=right_to_display,
        has_evidence=bool(evidence_refs),
    )
    limitations = _lane_limitations(
        status=status,
        consumer_state=consumer_state,
        freshness=freshness,
        coverage=coverage,
        right_to_display=right_to_display,
        degraded=degraded,
    )
    next_evidence_needed = _next_evidence_needed(lane_name, blocks, limitations)

    return {
        "status": status,
        "freshness": freshness,
        "coverage": coverage,
        "evidenceRefs": evidence_refs,
        "dataCoverageRowRef": row_ref_id,
        "rightToDisplay": right_to_display,
        "limitations": limitations,
        "nextEvidenceNeeded": next_evidence_needed,
        "consumerState": consumer_state,
    }


def _packet_identity(payload: Mapping[str, Any]) -> dict[str, Any]:
    identity = {
        "symbol": _safe_symbol(payload.get("symbol")),
        "market": _safe_market(payload.get("market")),
    }
    for output_key, input_keys in (
        ("generatedAt", ("generatedAt", "generated_at")),
        ("asOf", ("asOf", "as_of")),
        ("reportLanguage", ("reportLanguage", "report_language")),
    ):
        value = _first_present(*(payload.get(key) for key in input_keys))
        text = _optional_text(value)
        if text:
            identity[output_key] = text
    return identity


def _runtime_posture() -> dict[str, bool]:
    return {
        "diagnosticOnly": True,
        "observationOnly": True,
        "providerRuntimeCalled": False,
        "networkCallsEnabled": False,
        "marketCacheMutation": False,
        "authorityGrant": False,
    }


def _data_coverage_rows(value: Sequence[Any]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    by_lane: dict[str, dict[str, Any]] = {}
    sanitized: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        row = _mapping(raw)
        lane = _lane_from_row(row)
        if lane not in RESEARCH_PACKET_V1_LANES:
            continue
        field_key = _safe_ref(_first_present(row.get("fieldKey"), row.get("field_key"))) or f"row-{index + 1}"
        field_ref = field_key.replace("_", "-")
        row_ref = f"dataCoverage:{lane}:{field_ref}"
        freshness = _normalize_freshness(_first_present(row.get("freshnessState"), row.get("freshness_state")))
        degraded = _row_is_degraded(row, freshness=freshness)
        right_to_display = _normalize_right_to_display(
            _first_present(row.get("rightToDisplay"), row.get("right_to_display"))
        )
        if right_to_display == "granted" and degraded:
            right_to_display = "limited"
        item = {
            "rowRef": row_ref,
            "lane": lane,
            "freshness": freshness,
            "rightToDisplay": right_to_display,
            "observationOnly": True,
            "consumerState": _consumer_state_from_row(right_to_display, degraded, freshness),
        }
        sanitized.append(item)
        by_lane.setdefault(lane, {**row, "rowRef": row_ref})
    sanitized.sort(key=lambda item: (_lane_index(str(item["lane"])), str(item["rowRef"])))
    return by_lane, sanitized


def _citations_by_lane(value: Any) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for raw in _sequence(value):
        citation = _mapping(raw)
        lane = _lane_from_domain(citation.get("domain"))
        if lane not in RESEARCH_PACKET_V1_LANES:
            continue
        result.setdefault(lane, []).append(citation)
    return result


def _coverage_by_lane(
    evidence_coverage: Mapping[str, Any],
    citation_coverage: Any,
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for domain, raw in evidence_coverage.items():
        lane = _lane_from_domain(domain)
        if lane in RESEARCH_PACKET_V1_LANES:
            result.setdefault(lane, []).append(_mapping(raw))
    for raw in _sequence(citation_coverage):
        coverage = _mapping(raw)
        lane = _lane_from_domain(coverage.get("domain"))
        if lane in RESEARCH_PACKET_V1_LANES:
            result.setdefault(lane, []).append(coverage)
    return result


def _provenance_by_lane(value: Sequence[Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for raw in value:
        item = _mapping(raw)
        lane = _lane_from_domain(
            _first_present(
                item.get("evidenceDomain"),
                item.get("evidence_domain"),
                item.get("domain"),
            )
        )
        if lane in RESEARCH_PACKET_V1_LANES:
            result.setdefault(lane, []).append(item)
    return result


def _readiness_missing_lanes(readiness: Mapping[str, Any]) -> set[str]:
    lanes: set[str] = set()
    for raw in _sequence(readiness.get("missingEvidence")) + _sequence(readiness.get("missing_evidence")):
        lane = _lane_from_domain(raw)
        if lane in RESEARCH_PACKET_V1_LANES:
            lanes.add(lane)
    return lanes


def _lane_freshness(blocks: Sequence[Mapping[str, Any]], row: Mapping[str, Any]) -> str:
    values: list[str] = []
    for block in blocks:
        value = _first_present(
            block.get("freshness"),
            block.get("freshnessState"),
            block.get("freshness_state"),
            block.get("freshnessLabel"),
        )
        if value is not None:
            values.append(_normalize_freshness(value))
    row_value = _first_present(row.get("freshnessState"), row.get("freshness_state"), row.get("freshness"))
    if row_value is not None:
        values.append(_normalize_freshness(row_value))
    if not values:
        return "unknown"
    return max(values, key=lambda item: _FRESHNESS_RANK.get(item, _FRESHNESS_RANK["unknown"]))


def _lane_coverage(blocks: Sequence[Mapping[str, Any]], readiness_missing: bool) -> str:
    statuses = [_normalize_status(block.get("status")) for block in blocks if _has_key(block, "status")]
    evidence_count = sum(_safe_int(block.get("evidenceCount")) for block in blocks)
    if readiness_missing:
        return "missing"
    if any(status in _STATUS_MISSING for status in statuses):
        return "missing" if evidence_count <= 0 else "partial"
    if any(status in _STATUS_UPDATING for status in statuses):
        return "partial"
    if any(status in _STATUS_DEGRADED for status in statuses):
        return "partial"
    if evidence_count > 0:
        return "available"
    if any(_sequence(block.get("evidenceRefIds")) or _sequence(block.get("topEvidenceRefs")) for block in blocks):
        return "available"
    if any(_safe_ref(block.get("id")) for block in blocks):
        return "available"
    return "missing"


def _lane_evidence_refs(
    packet_blocks: Sequence[Mapping[str, Any]],
    coverage_blocks: Sequence[Mapping[str, Any]],
    citation_blocks: Sequence[Mapping[str, Any]],
) -> list[str]:
    refs: list[str] = []
    for block in packet_blocks:
        for raw in _sequence(block.get("topEvidenceRefs")):
            _append_unique(refs, _safe_ref(raw))
    for block in coverage_blocks:
        for raw in _sequence(block.get("evidenceRefIds")):
            _append_unique(refs, _safe_ref(raw))
    for block in citation_blocks:
        _append_unique(refs, _safe_ref(block.get("id")))
    return refs[:5]


def _lane_is_degraded(
    blocks: Sequence[Mapping[str, Any]],
    *,
    row: Mapping[str, Any],
    freshness: str,
    coverage: str,
) -> bool:
    if coverage != "available":
        return True
    if freshness in _DEGRADED_FRESHNESS:
        return True
    if _row_is_degraded(row, freshness=freshness):
        return True
    for block in blocks:
        if _bool(_first_present(block.get("fallbackOrProxy"), block.get("fallback_or_proxy"))):
            return True
        if _bool(_first_present(block.get("isFallback"), block.get("is_fallback"), block.get("proxyOnly"))):
            return True
        if _sequence(block.get("missingReasons")) or _sequence(block.get("limitations")):
            return True
    return False


def _row_is_degraded(row: Mapping[str, Any], *, freshness: str) -> bool:
    if not row:
        return False
    if freshness in _DEGRADED_FRESHNESS:
        return True
    for key in (
        "isFallback",
        "isStale",
        "isPartial",
        "isSynthetic",
        "isUnavailable",
        "is_fallback",
        "is_stale",
        "is_partial",
        "is_synthetic",
        "is_unavailable",
    ):
        if _bool(row.get(key)):
            return True
    return False


def _lane_right_to_display(row: Mapping[str, Any], *, degraded: bool, has_evidence: bool) -> str:
    if not row:
        return "unavailable"
    right = _normalize_right_to_display(_first_present(row.get("rightToDisplay"), row.get("right_to_display")))
    if right == "granted" and degraded:
        return "limited" if has_evidence else "unavailable"
    return right


def _lane_status(
    *,
    blocks: Sequence[Mapping[str, Any]],
    coverage: str,
    freshness: str,
    right_to_display: str,
    has_evidence: bool,
) -> tuple[str, str]:
    statuses = [_normalize_status(block.get("status")) for block in blocks if _has_key(block, "status")]
    if any(status in _STATUS_UPDATING for status in statuses):
        return "updating", "UPDATING"
    if not has_evidence and coverage == "missing":
        return "unavailable", "UNAVAILABLE"
    if right_to_display == "unavailable":
        return "insufficient", "INSUFFICIENT"
    if coverage == "missing":
        return "unavailable", "UNAVAILABLE"
    if coverage == "partial":
        return "partial", "PARTIAL"
    if freshness in {"stale", "fallback", "synthetic", "unavailable", "unknown"}:
        return "insufficient", "INSUFFICIENT"
    if freshness in {"cached", "delayed", "partial"}:
        return "delayed", "DELAYED"
    if right_to_display == "limited":
        return "partial", "PARTIAL"
    return "available", "AVAILABLE"


def _lane_limitations(
    *,
    status: str,
    consumer_state: str,
    freshness: str,
    coverage: str,
    right_to_display: str,
    degraded: bool,
) -> list[str]:
    limitations: list[str] = []
    if status == "available":
        return limitations
    if consumer_state == "UPDATING":
        _append_unique(limitations, _CONSUMER_COPY["UPDATING"])
    if freshness in {"cached", "delayed", "stale", "fallback"}:
        _append_unique(limitations, _CONSUMER_COPY["DELAYED"])
    if coverage == "partial" or degraded:
        _append_unique(limitations, _CONSUMER_COPY["INSUFFICIENT"])
    if right_to_display == "unavailable" or coverage == "missing":
        _append_unique(limitations, _CONSUMER_COPY["UNAVAILABLE"])
    return limitations or [_CONSUMER_COPY.get(consumer_state, _CONSUMER_COPY["INSUFFICIENT"])]


def _next_evidence_needed(
    lane_name: str,
    blocks: Sequence[Mapping[str, Any]],
    limitations: Sequence[str],
) -> list[str]:
    if not limitations:
        return []
    items: list[str] = []
    for block in blocks:
        for raw in _sequence(block.get("nextEvidenceNeeded")) + _sequence(block.get("next_evidence_needed")):
            _append_unique(items, _safe_consumer_text(raw, limit=48))
    if not items:
        items.append(_LANE_NEXT_EVIDENCE[lane_name])
    return items[:3]


def _evidence_citations(
    citation_index: Mapping[str, Sequence[Mapping[str, Any]]],
    lanes: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for lane_name in RESEARCH_PACKET_V1_LANES:
        lane = lanes[lane_name]
        if lane.get("rightToDisplay") == "unavailable":
            continue
        for raw in citation_index.get(lane_name, ()):
            citation = _mapping(raw)
            citation_id = _safe_ref(citation.get("id"))
            label = _safe_consumer_text(citation.get("label"), limit=72)
            summary = _safe_consumer_text(citation.get("summary"), limit=160)
            if not (citation_id and (label or summary)):
                continue
            item = {
                "id": citation_id,
                "lane": lane_name,
                "label": label or summary,
                "summary": summary or label,
            }
            as_of = _optional_text(_first_present(citation.get("asOf"), citation.get("publishedAt")))
            if as_of:
                item["asOf"] = as_of
            citations.append(item)
    citations.sort(key=lambda item: (_lane_index(str(item["lane"])), str(item["id"])))
    return citations


def _source_provenance_summary(
    source_provenance: Sequence[Any],
    lanes: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    entries = [_mapping(item) for item in source_provenance]
    limited_lane_count = sum(
        1
        for lane in lanes.values()
        if lane.get("consumerState") in {"DELAYED", "PARTIAL", "INSUFFICIENT", "UNAVAILABLE"}
    )
    displayable_lane_count = sum(1 for lane in lanes.values() if lane.get("rightToDisplay") in {"granted", "limited"})
    return {
        "entriesObserved": len(entries),
        "observationOnly": True,
        "authorityGrant": False,
        "displayableLaneCount": displayable_lane_count,
        "limitedLaneCount": limited_lane_count,
        "unknownLaneCount": sum(1 for lane in lanes.values() if lane.get("freshness") == "unknown"),
    }


def _redaction_posture() -> dict[str, bool]:
    return {
        "providerIdentifiersRedacted": True,
        "sourceDescriptorsRedacted": True,
        "rawDiagnosticsRedacted": True,
        "backendReasonCodesRedacted": True,
        "maintainerInstructionsRedacted": True,
        "consumerProjectionBounded": True,
    }


def _no_advice_boundary() -> dict[str, Any]:
    return {
        "analysisOnly": True,
        "personalizedAdviceAllowed": False,
        "actionableInstructionAllowed": False,
        "summary": "仅供研究观察，不构成投资建议。",
    }


def _consumer_projection(
    lanes: Mapping[str, Mapping[str, Any]],
    identity: Mapping[str, Any],
) -> dict[str, Any]:
    lane_items = []
    for lane_name in RESEARCH_PACKET_V1_LANES:
        lane = lanes[lane_name]
        state = str(lane.get("consumerState") or "UNAVAILABLE")
        item = {
            "lane": lane_name,
            "state": state,
            "headline": _CONSUMER_COPY.get(state, _CONSUMER_COPY["INSUFFICIENT"]),
        }
        as_of = _optional_text(identity.get("asOf"))
        if as_of and state != "UNAVAILABLE":
            item["lastUpdated"] = as_of
        lane_items.append(item)

    status = _aggregate_consumer_status(item["state"] for item in lane_items)
    result = {
        "status": status,
        "headline": _CONSUMER_COPY.get(status, _CONSUMER_COPY["INSUFFICIENT"]),
        "lanes": lane_items,
    }
    as_of = _optional_text(identity.get("asOf"))
    if as_of:
        result["lastUpdated"] = as_of
    return result


def _aggregate_consumer_status(states: Sequence[str]) -> str:
    states = tuple(states)
    if not states or all(state == "UNAVAILABLE" for state in states):
        return "UNAVAILABLE"
    if any(state == "INSUFFICIENT" for state in states):
        return "INSUFFICIENT"
    if any(state == "PAUSED" for state in states):
        return "PAUSED"
    if any(state == "PARTIAL" for state in states):
        return "PARTIAL"
    if any(state == "UPDATING" for state in states):
        return "UPDATING"
    if any(state == "DELAYED" for state in states):
        return "DELAYED"
    return "AVAILABLE"


def _consumer_state_from_row(right_to_display: str, degraded: bool, freshness: str) -> str:
    if right_to_display == "unavailable":
        return "INSUFFICIENT"
    if degraded:
        return "PARTIAL"
    if freshness in {"cached", "delayed"}:
        return "DELAYED"
    return "AVAILABLE" if right_to_display == "granted" else "PARTIAL"


def _lane_from_row(row: Mapping[str, Any]) -> str:
    for key in ("lane", "evidenceFamily", "evidence_family", "fieldKey", "field_key"):
        lane = _lane_from_domain(row.get(key))
        if lane in RESEARCH_PACKET_V1_LANES:
            return lane
    joined = " ".join(str(row.get(key) or "") for key in ("fieldKey", "field_key", "surfaceId", "surface_id"))
    return _lane_from_domain(joined)


def _lane_from_domain(value: Any) -> str:
    text = str(value or "").strip()
    if text in RESEARCH_PACKET_V1_LANES:
        return text
    if text in _DOMAIN_TO_LANE:
        return _DOMAIN_TO_LANE[text]
    normalized = text.lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "catalyst": "catalysts",
        "news": "news",
        "news_catalysts": "newsCatalysts",
        "newscatalysts": "newsCatalysts",
        "price_history": "priceHistory",
        "pricehistory": "priceHistory",
        "technical": "technicals",
        "sector_theme": "sectorTheme",
        "sectortheme": "sectorTheme",
        "macro_liquidity": "macroLiquidity",
        "macroliquidity": "macroLiquidity",
        "macro": "macroLiquidity",
        "liquidity": "macroLiquidity",
    }
    if normalized in aliases:
        return _DOMAIN_TO_LANE.get(aliases[normalized], aliases[normalized])
    for lane_name in RESEARCH_PACKET_V1_LANES:
        lane_normalized = lane_name.lower()
        if lane_normalized in normalized.replace("_", ""):
            return lane_name
    return ""


def _normalize_freshness(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    mapping = {
        "cache": "cached",
        "fixture": "synthetic",
        "late": "delayed",
        "local": "cached",
        "mock": "synthetic",
        "ok": "fresh",
        "pending": "unknown",
        "realtime": "live",
        "snapshot": "cached",
    }
    text = mapping.get(text, text)
    return text if text in _FRESHNESS_RANK else "unknown"


def _normalize_status(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"ok", "ready"}:
        return "available"
    return text


def _normalize_right_to_display(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"granted", "allowed", "true", "yes"}:
        return "granted"
    if text in {"limited", "partial", "delayed"}:
        return "limited"
    return "unavailable"


def _safe_symbol(value: Any) -> str:
    text = str(value or "").strip().upper()
    safe = "".join(char for char in text if char.isalnum() or char in ".-_")
    return safe[:24] or "UNKNOWN"


def _safe_market(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"cn", "hk", "us"} else "unknown"


def _safe_ref(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if _has_forbidden_consumer_text(text):
        return ""
    compact = "".join(char for char in text if char in _SAFE_ID_CHARS)
    return compact[:64]


def _safe_consumer_text(value: Any, *, limit: int) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).strip().split())
    if not text:
        return ""
    if _has_forbidden_consumer_text(text):
        return ""
    if "{" in text or "}" in text or "[" in text or "]" in text:
        return ""
    return text[:limit].rstrip()


def _has_forbidden_consumer_text(text: str) -> bool:
    lowered = text.lower()
    squashed = lowered.replace("_", "")
    if any(marker in lowered or marker.replace("_", "") in squashed for marker in _FORBIDDEN_TEXT_MARKERS):
        return True
    return _FORBIDDEN_ACTION_TEXT_RE.search(text) is not None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return max(0, value)
    try:
        return max(0, int(str(value)))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y"}


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


def _has_key(mapping: Mapping[str, Any], key: str) -> bool:
    return key in mapping


def _append_unique(values: list[str], value: str | None) -> None:
    text = str(value or "").strip()
    if text and text not in values:
        values.append(text)


def _lane_index(lane_name: str) -> int:
    try:
        return RESEARCH_PACKET_V1_LANES.index(lane_name)
    except ValueError:
        return len(RESEARCH_PACKET_V1_LANES)


__all__ = [
    "RESEARCH_PACKET_V1_LANES",
    "RESEARCH_PACKET_V1_VERSION",
    "build_research_packet_v1",
]
