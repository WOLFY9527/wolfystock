# -*- coding: utf-8 -*-
"""Shared VIX metadata normalization helpers."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


_VIX_SYMBOLS = {"VIX", "VIXCLS"}
_PROXY_SOURCE_VALUES = {"yahoo", "yfinance", "yfinance_proxy"}
_PROXY_SOURCE_TYPES = {"unofficial_proxy", "public_proxy", "proxy_public"}
_OFFICIAL_SOURCE_VALUES = {"fred"}
_OFFICIAL_SOURCE_TYPES = {"official_public"}


def is_vix_symbol(value: Any) -> bool:
    text = str(value or "").strip().upper()
    if not text:
        return False
    return text in _VIX_SYMBOLS or text.lstrip("^") in _VIX_SYMBOLS or text.endswith(":VIXCLS")


def normalize_vix_quote_metadata(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Return VIX quote metadata with delayed/unofficial semantics preserved."""

    normalized = dict(payload)
    if not is_vix_symbol(
        normalized.get("symbol")
        or normalized.get("key")
        or normalized.get("label")
        or normalized.get("sourceId")
    ):
        return normalized

    source = str(normalized.get("source") or "").strip().lower()
    source_type = str(normalized.get("sourceType") or "").strip().lower()
    source_id = str(normalized.get("sourceId") or "").strip().lower()
    freshness = str(normalized.get("freshness") or "").strip().lower()

    original_freshness = freshness
    if source in _PROXY_SOURCE_VALUES or source_type in _PROXY_SOURCE_TYPES:
        normalized["sourceType"] = "unofficial_proxy"
        normalized["sourceLabel"] = normalized.get("sourceLabel") or "Yahoo Finance"
        normalized["freshness"] = _normalize_proxy_freshness(freshness)
    elif source in _OFFICIAL_SOURCE_VALUES or source_type in _OFFICIAL_SOURCE_TYPES or source_id == "fred:vixcls":
        normalized["sourceType"] = "official_public"
        normalized["freshness"] = _normalize_official_freshness(freshness)

    freshness = str(normalized.get("freshness") or "").strip().lower()
    if (
        freshness in {"delayed", "stale", "cached"}
        and freshness != original_freshness
        and not normalized.get("degradationReason")
    ):
        normalized["degradationReason"] = "delayed_source"
    if freshness == "delayed":
        normalized["isStale"] = False
    return normalized


def normalize_vix_panel_metadata(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a VIX-sensitive panel payload with explicit freshness metadata."""

    normalized = dict(payload)
    raw_items = normalized.get("items")
    if not isinstance(raw_items, list):
        return normalized

    items = [normalize_vix_quote_metadata(item) if isinstance(item, dict) else item for item in raw_items]
    normalized["items"] = items
    vix_item = _first_vix_item(items)
    if not isinstance(vix_item, dict):
        return normalized

    panel_source = str(normalized.get("source") or "").strip().lower()
    if vix_item.get("sourceType") and not normalized.get("sourceType") and panel_source != "mixed":
        normalized["sourceType"] = vix_item["sourceType"]
    if vix_item.get("asOf"):
        normalized["asOf"] = vix_item["asOf"]
    if vix_item.get("updatedAt"):
        normalized["updatedAt"] = vix_item["updatedAt"]

    freshness = str(vix_item.get("freshness") or "").strip().lower()
    if freshness:
        normalized["sourceFreshnessEvidence"] = {
            "freshness": freshness,
            "isFallback": bool(vix_item.get("isFallback")),
            "isStale": bool(vix_item.get("isStale") or freshness == "stale"),
            "isPartial": bool(vix_item.get("isPartial")),
            "isUnavailable": bool(vix_item.get("isUnavailable")),
            "warning": vix_item.get("warning"),
        }
    return normalized


def _first_vix_item(items: list[Any]) -> Optional[Dict[str, Any]]:
    for item in items:
        if isinstance(item, dict) and is_vix_symbol(item.get("symbol")):
            return item
    return None


def _normalize_proxy_freshness(freshness: str) -> str:
    if freshness in {"stale", "fallback", "mock", "unavailable", "error", "partial", "synthetic", "cached", "delayed"}:
        return freshness
    return "delayed"


def _normalize_official_freshness(freshness: str) -> str:
    if freshness in {"stale", "fallback", "mock", "unavailable", "error", "partial", "synthetic", "cached", "delayed"}:
        return freshness
    return "delayed"
