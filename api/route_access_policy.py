# -*- coding: utf-8 -*-
"""Shared route access policy helpers for app-level auth and abuse limiting."""

from __future__ import annotations

import re

PUBLIC_BASELINE_PATHS = frozenset(
    {
        # Guest Market Overview secondary reads. These endpoints return only
        # consumer-safe market observations and do not expose user or operator data.
        "/api/v1/market/cn-breadth",
        "/api/v1/market/cn-flows",
        "/api/v1/market/cn-indices",
        "/api/v1/market/cn-short-sentiment",
        "/api/v1/market/crypto",
        "/api/v1/market/crypto/stream",
        "/api/v1/market/daily-intelligence",
        "/api/v1/market/decision-cockpit",
        "/api/v1/market/futures",
        "/api/v1/market/fx-commodities",
        "/api/v1/market/liquidity-monitor",
        "/api/v1/market/market-briefing",
        "/api/v1/market/professional-data-capabilities",
        "/api/v1/market/rates",
        "/api/v1/market/regime-decision",
        "/api/v1/market/regime-evidence-pack",
        "/api/v1/market/regime-read-model",
        "/api/v1/market/rotation-radar",
        "/api/v1/market/sector-rotation",
        "/api/v1/market/sentiment",
        "/api/v1/market/temperature",
        "/api/v1/market/us-breadth",
        "/api/v1/market-overview",
        "/api/v1/market-overview/indices",
        "/api/v1/market-overview/volatility",
        "/api/v1/market-overview/sentiment",
        "/api/v1/market-overview/funds-flow",
        "/api/v1/market-overview/macro",
        "/api/v1/dashboard/market-intelligence-overview",
        "/api/v1/homepage/intelligence",
    }
)

PUBLIC_CONSUMER_SAFE_ROUTES = frozenset(
    {
        ("POST", "/api/v1/analysis/preview"),
    }
)

_PUBLIC_STOCK_READ_RE = re.compile(
    r"^/api/v1/stocks/[^/]+/quote$"
)


def normalize_policy_path(path: str) -> str:
    return str(path or "").rstrip("/") or "/"


def is_public_baseline_read(method: str, path: str) -> bool:
    normalized_method = str(method or "").upper()
    normalized = normalize_policy_path(path)
    if (normalized_method, normalized) in PUBLIC_CONSUMER_SAFE_ROUTES:
        return True
    if normalized_method != "GET":
        return False
    return normalized in PUBLIC_BASELINE_PATHS or _PUBLIC_STOCK_READ_RE.match(normalized) is not None
