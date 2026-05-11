# -*- coding: utf-8 -*-
"""Pure symbol normalization helpers shared outside provider runtime."""

from __future__ import annotations


def normalize_stock_code(stock_code: str) -> str:
    """Normalize stock code by stripping exchange prefixes and suffixes."""
    code = stock_code.strip()
    upper = code.upper()

    if upper.startswith("HK") and not upper.startswith("HK."):
        candidate = upper[2:]
        if candidate.isdigit() and 1 <= len(candidate) <= 5:
            return f"HK{candidate.zfill(5)}"

    if upper.startswith(("SH", "SZ")) and not upper.startswith(("SH.", "SZ.")):
        candidate = code[2:]
        if candidate.isdigit() and len(candidate) in (5, 6):
            return candidate

    if upper.startswith("BJ") and not upper.startswith("BJ."):
        candidate = code[2:]
        if candidate.isdigit() and len(candidate) == 6:
            return candidate

    if "." in code:
        base, suffix = code.rsplit(".", 1)
        if suffix.upper() == "HK" and base.isdigit() and 1 <= len(base) <= 5:
            return f"HK{base.zfill(5)}"
        if suffix.upper() in ("SH", "SZ", "SS", "BJ") and base.isdigit():
            return base

    return code


def canonical_stock_code(code: str | None) -> str:
    """Return the canonical uppercase form of a stock code."""
    return (code or "").strip().upper()
