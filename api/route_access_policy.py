# -*- coding: utf-8 -*-
"""Shared route access policy helpers for app-level auth and abuse limiting."""

from __future__ import annotations

import re

PUBLIC_BASELINE_PATHS = frozenset(
    {
        "/api/v1/market/market-briefing",
        "/api/v1/market-overview/indices",
        "/api/v1/market-overview/volatility",
        "/api/v1/market-overview/sentiment",
        "/api/v1/market-overview/funds-flow",
        "/api/v1/market-overview/macro",
    }
)

_PUBLIC_STOCK_READ_RE = re.compile(
    r"^/api/v1/stocks/[^/]+/(?:quote|evidence|structure-decision)$"
)


def normalize_policy_path(path: str) -> str:
    return str(path or "").rstrip("/") or "/"


def is_public_baseline_read(method: str, path: str) -> bool:
    if str(method or "").upper() != "GET":
        return False
    normalized = normalize_policy_path(path)
    return normalized in PUBLIC_BASELINE_PATHS or _PUBLIC_STOCK_READ_RE.match(normalized) is not None
