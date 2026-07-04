# -*- coding: utf-8 -*-
"""Pure symbol evidence readiness projector.

Consumes already-built stock evidence items and emits a bounded research
readiness packet. It performs no provider calls, cache reads, DB access, or LLM
work.
"""

from __future__ import annotations

from typing import Any, Mapping


SYMBOL_EVIDENCE_READINESS_NO_ADVICE_DISCLOSURE = (
    "仅供研究观察，不构成个性化行动指令。"
)

_REQUIRED_FAMILIES = ("quote", "technical", "fundamental", "news")
_OPTIONAL_FAMILIES = ("secFilingEvidence",)
_ALL_FAMILIES = _REQUIRED_FAMILIES + _OPTIONAL_FAMILIES
_AVAILABLE_STATUSES = {"available", "ok", "success"}
_PARTIAL_STATUSES = {"partial"}
_MISSING_STATUSES = {"", "missing", "unknown", "unavailable", "error", "rejected", "placeholder"}
_STALE_FRESHNESS = {"stale", "fallback", "delayed", "partial", "synthetic"}
_STALE_SOURCE_TYPES = {"fallback", "synthetic", "unofficial_proxy"}
_NEWS_PLACEHOLDER_TOKENS = ("placeholder", "unknown", "no recent headlines", "not available")
_CONSUMER_FAMILY_LABELS = {
    "quote": "行情",
    "technical": "技术面",
    "fundamental": "基本面",
    "news": "新闻资讯",
    "secFilingEvidence": "公告文件",
}


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _status(payload: Mapping[str, Any]) -> str:
    return _text(payload.get("status"), "missing").lower() or "missing"


def _is_partial(payload: Mapping[str, Any]) -> bool:
    return _status(payload) in _PARTIAL_STATUSES


def _is_missing(payload: Mapping[str, Any]) -> bool:
    return _status(payload) in _MISSING_STATUSES


def _news_is_placeholder(news: Mapping[str, Any]) -> bool:
    headline = _text(news.get("latestHeadline") or news.get("headline")).lower()
    provider = _text(news.get("provider") or news.get("providerId") or news.get("providerName")).lower()
    if _is_missing(news):
        return True
    return any(token in headline or token in provider for token in _NEWS_PLACEHOLDER_TOKENS)


def _is_used(family: str, payload: Mapping[str, Any]) -> bool:
    if family == "news" and _news_is_placeholder(payload):
        return False
    return _status(payload) in _AVAILABLE_STATUSES or _is_partial(payload)


def _is_stale_input(payload: Mapping[str, Any]) -> bool:
    if not payload:
        return False
    if any(bool(payload.get(key)) for key in ("isStale", "isFallback", "isSynthetic")):
        return True
    freshness = _text(payload.get("freshness") or payload.get("freshnessClass")).lower()
    if freshness in _STALE_FRESHNESS:
        return True
    source_type = _text(payload.get("sourceType") or payload.get("sourceClass") or payload.get("sourceTier")).lower()
    return source_type in _STALE_SOURCE_TYPES


def _explicit_conflicting_families(families: Mapping[str, Mapping[str, Any]]) -> list[str]:
    conflicting: list[str] = []
    for family, payload in families.items():
        status = _status(payload)
        if status in {"conflict", "conflicting"} or payload.get("conflict") is True:
            conflicting.append(family)
    return conflicting


def _consumer_family_labels(families: list[str]) -> str:
    return "、".join(_CONSUMER_FAMILY_LABELS.get(family, family) for family in families)


def _readiness_tier(
    *,
    evidence_used: list[str],
    evidence_missing: list[str],
    stale_inputs: list[str],
    conflicting_evidence: list[str],
) -> str:
    clean_required = [
        family
        for family in _REQUIRED_FAMILIES
        if family in evidence_used
        and family not in evidence_missing
        and family not in stale_inputs
        and family not in conflicting_evidence
    ]
    if len(clean_required) == len(_REQUIRED_FAMILIES):
        return "sufficient"

    required_used_count = len([family for family in _REQUIRED_FAMILIES if family in evidence_used])
    if required_used_count >= 2:
        return "partial"
    return "insufficient"


def _data_quality_notes(
    *,
    readiness_tier: str,
    evidence_missing: list[str],
    stale_inputs: list[str],
    conflicting_evidence: list[str],
    evidence_used: list[str],
) -> list[str]:
    notes: list[str] = []
    if readiness_tier == "sufficient":
        notes.append("核心行情、技术面、基本面与新闻资讯证据已返回，未见过期标记。")
    elif readiness_tier == "partial":
        notes.append("已返回部分标的证据，但仍有关键缺口，暂不形成完整研究交接。")
    else:
        notes.append("标的证据仍然不足，暂不形成完整研究交接。")

    if evidence_missing:
        notes.append(f"待补证据类别：{_consumer_family_labels(evidence_missing)}。")
    if stale_inputs:
        notes.append(f"存在过期或延迟输入：{_consumer_family_labels(stale_inputs)}。")
    if conflicting_evidence:
        notes.append(f"存在需要复核的冲突标记：{_consumer_family_labels(conflicting_evidence)}。")
    if "secFilingEvidence" in evidence_used:
        notes.append("SEC filing evidence is treated as observation-only context.")
    return notes


def _suggested_research_path(
    *,
    readiness_tier: str,
    evidence_missing: list[str],
    stale_inputs: list[str],
) -> list[str]:
    if readiness_tier == "sufficient":
        return [
            "继续一起复核行情、技术面、基本面与新闻资讯证据。",
            "后续研究假设继续与交易指令保持分离。",
        ]

    path: list[str] = []
    if readiness_tier == "insufficient":
        path.append("先补齐标的核心证据，再开展个股研究假设。")
    if "quote" in evidence_missing:
        path.append("补齐实时报价与时效信息。")
    if "technical" in evidence_missing:
        path.append("补充近期 K 线或技术面上下文。")
    if "fundamental" in evidence_missing:
        path.append("补充基本面证据后再复核研究主线。")
    if "news" in evidence_missing:
        path.append("补充近期新闻或公告语境后再复核催化因素。")
    if stale_inputs:
        path.append("刷新过期或延迟输入后再比较研究场景。")
    if not path:
        path.append("先复核已有证据，并优先补齐最薄弱的证据类别。")
    return path


def build_symbol_evidence_readiness(stock_evidence_item: Mapping[str, Any]) -> dict[str, Any]:
    """Build the bounded symbol-level evidence readiness packet."""

    item = _as_mapping(stock_evidence_item)
    symbol = _text(item.get("symbol"), "unknown").upper() or "unknown"
    families = {family: _as_mapping(item.get(family)) for family in _ALL_FAMILIES}

    evidence_used = [
        family
        for family in _ALL_FAMILIES
        if _is_used(family, families[family])
    ]
    evidence_missing = [
        family
        for family in _REQUIRED_FAMILIES
        if _is_missing(families[family]) or _is_partial(families[family])
    ]
    stale_inputs = [
        family
        for family in _ALL_FAMILIES
        if family in evidence_used and _is_stale_input(families[family])
    ]
    conflicting_evidence = _explicit_conflicting_families(families)
    readiness_tier = _readiness_tier(
        evidence_used=evidence_used,
        evidence_missing=evidence_missing,
        stale_inputs=stale_inputs,
        conflicting_evidence=conflicting_evidence,
    )

    return {
        "symbolEvidenceReadiness": True,
        "symbol": symbol,
        "readinessTier": readiness_tier,
        "evidenceUsed": evidence_used,
        "evidenceMissing": evidence_missing,
        "staleInputs": stale_inputs,
        "conflictingEvidence": conflicting_evidence,
        "dataQualityNotes": _data_quality_notes(
            readiness_tier=readiness_tier,
            evidence_missing=evidence_missing,
            stale_inputs=stale_inputs,
            conflicting_evidence=conflicting_evidence,
            evidence_used=evidence_used,
        ),
        "suggestedResearchPath": _suggested_research_path(
            readiness_tier=readiness_tier,
            evidence_missing=evidence_missing,
            stale_inputs=stale_inputs,
        ),
        "observationOnly": True,
        "noAdviceDisclosure": SYMBOL_EVIDENCE_READINESS_NO_ADVICE_DISCLOSURE,
    }


__all__ = [
    "SYMBOL_EVIDENCE_READINESS_NO_ADVICE_DISCLOSURE",
    "build_symbol_evidence_readiness",
]
