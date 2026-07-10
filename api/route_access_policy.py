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
        "/api/v1/market/cn-short-sentiment",
        "/api/v1/market/crypto",
        "/api/v1/market/crypto/stream",
        "/api/v1/market/futures",
        "/api/v1/market/fx-commodities",
        "/api/v1/market/liquidity-monitor",
        "/api/v1/market/market-briefing",
        "/api/v1/market/rates",
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
    }
)

_PUBLIC_STOCK_READ_RE = re.compile(
    r"^/api/v1/stocks/[^/]+/quote$"
)


def normalize_policy_path(path: str) -> str:
    return str(path or "").rstrip("/") or "/"


def is_public_baseline_read(method: str, path: str) -> bool:
    if str(method or "").upper() != "GET":
        return False
    normalized = normalize_policy_path(path)
    return normalized in PUBLIC_BASELINE_PATHS or _PUBLIC_STOCK_READ_RE.match(normalized) is not None
