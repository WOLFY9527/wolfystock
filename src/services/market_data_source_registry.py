# -*- coding: utf-8 -*-
"""Pure provenance helpers for market data source classification."""

from __future__ import annotations

from typing import Any, Dict


CANONICAL_SOURCE_TYPES = {
    "exchange_public",
    "official_public",
    "public_proxy",
    "unofficial_proxy",
    "cache_snapshot",
    "fallback_static",
    "synthetic_fixture",
    "missing",
}

SOURCE_TYPE_BY_SOURCE = {
    "alternative": "official_public",
    "alternative_me": "official_public",
    "binance": "exchange_public",
    "binance_ws": "exchange_public",
    "cache": "cache_snapshot",
    "cached": "cache_snapshot",
    "cnn": "official_public",
    "eastmoney": "official_public",
    "fallback": "fallback_static",
    "fixture": "synthetic_fixture",
    "mock": "synthetic_fixture",
    "snapshot": "cache_snapshot",
    "sina": "official_public",
    "synthetic": "synthetic_fixture",
    "synthetic_fixture": "synthetic_fixture",
    "unit_fixture": "synthetic_fixture",
    "unavailable": "missing",
    "yahoo": "unofficial_proxy",
    "yfinance": "unofficial_proxy",
    "yfinance_proxy": "unofficial_proxy",
}

SOURCE_TYPE_ALIASES = {
    "": "missing",
    "cache": "cache_snapshot",
    "cache_snapshot": "cache_snapshot",
    "cached": "cache_snapshot",
    "exchange_public": "exchange_public",
    "fallback": "fallback_static",
    "fallback_static": "fallback_static",
    "missing": "missing",
    "mock": "synthetic_fixture",
    "official_api": "official_public",
    "official_public": "official_public",
    "proxy_public": "public_proxy",
    "public": "public_proxy",
    "public_api": "official_public",
    "public_or_live": "public_proxy",
    "public_proxy": "public_proxy",
    "snapshot": "cache_snapshot",
    "synthetic": "synthetic_fixture",
    "synthetic_fixture": "synthetic_fixture",
    "unavailable": "missing",
    "unofficial_proxy": "unofficial_proxy",
    "unofficial_public_api": "unofficial_proxy",
}

SOURCE_LABEL_BY_SOURCE = {
    "alternative": "Alternative.me",
    "alternative_me": "Alternative.me",
    "binance": "Binance",
    "binance_ws": "Binance",
    "cache": "缓存快照",
    "cached": "缓存快照",
    "cnn": "CNN",
    "eastmoney": "东方财富",
    "fallback": "备用数据",
    "fixture": "Synthetic Fixture",
    "mock": "模拟数据",
    "snapshot": "缓存快照",
    "sina": "新浪财经",
    "synthetic": "Synthetic Fixture",
    "synthetic_fixture": "Synthetic Fixture",
    "unit_fixture": "Unit Fixture",
    "unavailable": "未接入",
    "yahoo": "Yahoo Finance",
    "yfinance": "Yahoo Finance",
    "yfinance_proxy": "Yahoo Finance",
}

SOURCE_LABEL_BY_TYPE = {
    "cache_snapshot": "缓存快照",
    "exchange_public": "公开交易所",
    "fallback_static": "备用数据",
    "missing": "未接入",
    "official_public": "公开数据",
    "public_proxy": "公开代理",
    "synthetic_fixture": "Synthetic Fixture",
    "unofficial_proxy": "Yahoo Finance",
}

FRESHNESS_LABELS = {
    "cached": "缓存",
    "delayed": "延迟",
    "error": "不可用",
    "fallback": "备用/缺失",
    "live": "实时",
    "mock": "模拟",
    "stale": "过期",
    "unavailable": "不可用",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def resolve_source_type(
    source: Any = None,
    *,
    source_type: Any = None,
    freshness: Any = None,
    is_fallback: bool = False,
    is_from_snapshot: bool = False,
    no_external_calls: bool = False,
) -> str:
    """Return the canonical provenance class for a market data source."""
    normalized_source = _text(source).lower()
    normalized_type = _text(source_type).lower()
    normalized_freshness = _text(freshness).lower()

    if is_from_snapshot or (no_external_calls and normalized_freshness == "cached"):
        return "cache_snapshot"
    if is_fallback or normalized_freshness in {"fallback", "mock"} or normalized_source == "fallback":
        return "fallback_static"
    if normalized_source in SOURCE_TYPE_BY_SOURCE:
        return SOURCE_TYPE_BY_SOURCE[normalized_source]
    if normalized_type in SOURCE_TYPE_ALIASES:
        return SOURCE_TYPE_ALIASES[normalized_type]
    if normalized_source or normalized_type:
        return "public_proxy"
    return "missing"


def resolve_source_label(
    source: Any = None,
    *,
    source_type: Any = None,
    source_label: Any = None,
    freshness: Any = None,
    is_fallback: bool = False,
    is_from_snapshot: bool = False,
    no_external_calls: bool = False,
) -> str:
    """Return a human-readable provenance label while preserving explicit labels."""
    explicit_label = _text(source_label)
    if explicit_label:
        return explicit_label

    normalized_source = _text(source).lower()
    resolved_type = resolve_source_type(
        source,
        source_type=source_type,
        freshness=freshness,
        is_fallback=is_fallback,
        is_from_snapshot=is_from_snapshot,
        no_external_calls=no_external_calls,
    )
    if resolved_type in {"cache_snapshot", "fallback_static", "missing"}:
        return SOURCE_LABEL_BY_TYPE.get(resolved_type, "公开数据")
    if normalized_source in SOURCE_LABEL_BY_SOURCE:
        return SOURCE_LABEL_BY_SOURCE[normalized_source]
    return SOURCE_LABEL_BY_TYPE.get(resolved_type, "公开数据")


def resolve_freshness_label(
    freshness: Any,
    *,
    is_fallback: bool = False,
    is_stale: bool = False,
    source_type: Any = None,
    is_from_snapshot: bool = False,
) -> str:
    """Return a standardized freshness label for display-only provenance."""
    normalized_freshness = _text(freshness).lower()
    resolved_type = _text(source_type).lower()
    if is_fallback or normalized_freshness == "fallback" or resolved_type == "fallback_static":
        return "备用/缺失"
    if is_stale or normalized_freshness == "stale":
        return "过期"
    if is_from_snapshot or resolved_type == "cache_snapshot":
        return "缓存快照" if normalized_freshness in {"cached", "live", ""} else FRESHNESS_LABELS.get(normalized_freshness, "缓存快照")
    return FRESHNESS_LABELS.get(normalized_freshness or "unavailable", "不可用")


def project_source_provenance(
    *,
    source: Any = None,
    source_type: Any = None,
    source_label: Any = None,
    freshness: Any = None,
    is_fallback: bool = False,
    is_stale: bool = False,
    is_from_snapshot: bool = False,
    no_external_calls: bool = False,
) -> Dict[str, str]:
    """Project canonical sourceType/sourceLabel/freshnessLabel without side effects."""
    resolved_type = resolve_source_type(
        source,
        source_type=source_type,
        freshness=freshness,
        is_fallback=is_fallback,
        is_from_snapshot=is_from_snapshot,
        no_external_calls=no_external_calls,
    )
    return {
        "sourceType": resolved_type,
        "sourceLabel": resolve_source_label(
            source,
            source_type=resolved_type,
            source_label=source_label,
            freshness=freshness,
            is_fallback=is_fallback,
            is_from_snapshot=is_from_snapshot,
            no_external_calls=no_external_calls,
        ),
        "freshnessLabel": resolve_freshness_label(
            freshness,
            is_fallback=is_fallback,
            is_stale=is_stale,
            source_type=resolved_type,
            is_from_snapshot=is_from_snapshot,
        ),
    }
