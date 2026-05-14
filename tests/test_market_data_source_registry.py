# -*- coding: utf-8 -*-
"""Tests for market data source provenance registry helpers."""

from __future__ import annotations

from src.services.market_data_source_registry import (
    project_source_provenance,
    resolve_freshness_label,
    resolve_source_label,
    resolve_source_type,
)


def test_binance_remains_exchange_public() -> None:
    provenance = project_source_provenance(source="binance", freshness="live")

    assert provenance["sourceType"] == "exchange_public"
    assert provenance["sourceLabel"] == "Binance"
    assert provenance["freshnessLabel"] == "实时"


def test_yfinance_proxy_remains_delayed_unofficial_proxy() -> None:
    provenance = project_source_provenance(
        source="yfinance_proxy",
        source_type="proxy_public",
        freshness="delayed",
    )

    assert provenance["sourceType"] == "unofficial_proxy"
    assert provenance["sourceLabel"] == "Yahoo Finance"
    assert provenance["freshnessLabel"] == "延迟"


def test_fallback_static_never_claims_live_freshness() -> None:
    provenance = project_source_provenance(
        source="fallback",
        freshness="live",
        is_fallback=True,
    )

    assert provenance["sourceType"] == "fallback_static"
    assert provenance["sourceLabel"] == "备用数据"
    assert provenance["freshnessLabel"] == "备用/缺失"


def test_cache_snapshot_is_distinguishable_from_live_provider_data() -> None:
    provenance = project_source_provenance(
        source="yfinance_proxy",
        freshness="cached",
        is_from_snapshot=True,
        no_external_calls=True,
    )

    assert provenance["sourceType"] == "cache_snapshot"
    assert provenance["sourceLabel"] == "缓存快照"
    assert provenance["freshnessLabel"] == "缓存快照"


def test_missing_source_defaults_to_missing_labels() -> None:
    assert resolve_source_type(source=None, source_type=None) == "missing"
    assert resolve_source_label(source=None, source_type=None) == "未接入"
    assert resolve_freshness_label("unavailable") == "不可用"
