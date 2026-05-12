# -*- coding: utf-8 -*-
"""Pure symbol classification helpers shared outside provider runtime."""

from __future__ import annotations

import re


_US_STOCK_PATTERN = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")
_US_INDEX_CODES = frozenset(
    {
        "SPX",
        "^GSPC",
        "GSPC",
        "DJI",
        "^DJI",
        "DJIA",
        "IXIC",
        "^IXIC",
        "NASDAQ",
        "NDX",
        "^NDX",
        "VIX",
        "^VIX",
        "RUT",
        "^RUT",
    }
)


def is_us_index_code(code: str | None) -> bool:
    """Return True when a symbol matches the provider-runtime US index rules."""
    return (code or "").strip().upper() in _US_INDEX_CODES


def is_us_stock_code(code: str | None) -> bool:
    """Return True when a symbol matches the provider-runtime US stock rules."""
    normalized = (code or "").strip().upper()
    if is_us_index_code(normalized):
        return False
    return bool(_US_STOCK_PATTERN.match(normalized))


def is_bse_code(code: str | None) -> bool:
    """Return True when a code matches the provider-runtime BSE rules."""
    candidate = (code or "").strip().split(".")[0]
    if len(candidate) != 6 or not candidate.isdigit():
        return False
    if candidate.startswith("900"):
        return False
    return candidate.startswith(("92", "43", "81", "82", "83", "87", "88"))


def is_st_stock(name: str | None) -> bool:
    """Return True when a stock name matches the provider-runtime ST rule."""
    return "ST" in (name or "").upper()


def is_kc_cy_stock(code: str | None) -> bool:
    """Return True when a code matches the provider-runtime STAR/ChiNext rule."""
    candidate = (code or "").strip().split(".")[0]
    return candidate.startswith("688") or candidate.startswith("30")
