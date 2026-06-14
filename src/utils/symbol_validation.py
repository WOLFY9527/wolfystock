# -*- coding: utf-8 -*-
"""Consumer-facing symbol validation helpers without provider runtime access."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from src.utils.symbol_classification import is_us_index_code, is_us_stock_code
from src.utils.symbol_normalization import canonical_stock_code, normalize_stock_code


SymbolValidationStatus = Literal[
    "valid",
    "invalid_format",
    "unsupported_market",
    "ambiguous",
    "not_found",
    "unavailable",
    "unknown",
]

SUPPORTED_SYMBOL_MARKETS = frozenset({"cn", "hk", "us"})

_SAFE_SYMBOL_RE = re.compile(r"^[A-Za-z0-9.^-]+$")


@dataclass(frozen=True)
class ConsumerSymbolPrecheck:
    raw_symbol: str
    normalized_symbol: str
    market: str | None
    status: SymbolValidationStatus
    message: str

    @property
    def can_lookup(self) -> bool:
        return self.status == "unknown"


def validate_consumer_symbol_precheck(
    symbol: str | None,
    *,
    market: str | None = None,
) -> ConsumerSymbolPrecheck:
    """Normalize and classify a consumer symbol before any lookup dependency runs."""
    raw = str(symbol or "").strip()
    requested_market = _normalize_requested_market(market)
    normalized = canonical_stock_code(normalize_stock_code(raw))

    if requested_market == "unsupported":
        return _result(
            raw,
            normalized,
            None,
            "unsupported_market",
            "Supported markets are cn, hk, and us.",
        )
    if not raw:
        return _result(raw, normalized, requested_market, "invalid_format", "Enter a symbol.")
    if len(raw) > 16 or not _SAFE_SYMBOL_RE.fullmatch(raw):
        return _result(
            raw,
            normalized,
            requested_market,
            "invalid_format",
            "Enter a supported stock symbol format.",
        )

    if requested_market is None and raw.isdigit() and 1 <= len(raw) <= 5:
        return _result(
            raw,
            canonical_stock_code(raw),
            None,
            "ambiguous",
            "Add a market to validate this symbol.",
        )

    if requested_market == "cn":
        return _validate_cn_symbol(raw, normalized)
    if requested_market == "hk":
        return _validate_hk_symbol(raw, normalized)
    if requested_market == "us":
        return _validate_us_symbol(raw)

    inferred_market = _infer_market(raw, normalized)
    if inferred_market is None:
        return _result(
            raw,
            normalized,
            None,
            "invalid_format",
            "Enter a supported stock symbol format.",
        )
    if inferred_market == "hk":
        normalized = _normalize_hk_symbol(raw, normalized)
    return _result(
        raw,
        normalized,
        inferred_market,
        "unknown",
        "Symbol format is supported, but verification is not confirmed yet.",
    )


def _normalize_requested_market(market: str | None) -> str | None:
    if market is None:
        return None
    normalized = str(market or "").strip().lower()
    if not normalized:
        return None
    if normalized not in SUPPORTED_SYMBOL_MARKETS:
        return "unsupported"
    return normalized


def _validate_cn_symbol(raw: str, normalized: str) -> ConsumerSymbolPrecheck:
    if _looks_like_hk_symbol(raw, normalized) or _looks_like_us_symbol(raw):
        return _result(
            raw,
            normalized,
            "cn",
            "unsupported_market",
            "Symbol format does not match the requested market.",
        )
    if _looks_like_cn_symbol(raw, normalized):
        return _result(
            raw,
            normalized,
            "cn",
            "unknown",
            "Symbol format is supported, but verification is not confirmed yet.",
        )
    return _result(raw, normalized, "cn", "invalid_format", "Enter a supported CN stock symbol.")


def _validate_hk_symbol(raw: str, normalized: str) -> ConsumerSymbolPrecheck:
    if _looks_like_cn_symbol(raw, normalized) or _looks_like_us_symbol(raw):
        return _result(
            raw,
            normalized,
            "hk",
            "unsupported_market",
            "Symbol format does not match the requested market.",
        )
    hk_symbol = _normalize_hk_symbol(raw, normalized)
    if _is_hk_canonical(hk_symbol):
        return _result(
            raw,
            hk_symbol,
            "hk",
            "unknown",
            "Symbol format is supported, but verification is not confirmed yet.",
        )
    return _result(raw, normalized, "hk", "invalid_format", "Enter a supported HK stock symbol.")


def _validate_us_symbol(raw: str) -> ConsumerSymbolPrecheck:
    normalized = canonical_stock_code(raw)
    normalized_stock = canonical_stock_code(normalize_stock_code(raw))
    if _looks_like_cn_symbol(raw, normalized_stock) or _looks_like_hk_symbol(raw, normalized_stock):
        return _result(
            raw,
            normalized_stock,
            "us",
            "unsupported_market",
            "Symbol format does not match the requested market.",
        )
    if _looks_like_us_symbol(raw):
        return _result(
            raw,
            normalized,
            "us",
            "unknown",
            "Symbol format is supported, but verification is not confirmed yet.",
        )
    return _result(raw, normalized, "us", "invalid_format", "Enter a supported US ticker.")


def _infer_market(raw: str, normalized: str) -> str | None:
    if _looks_like_hk_symbol(raw, normalized):
        return "hk"
    if _looks_like_cn_symbol(raw, normalized):
        return "cn"
    if _looks_like_us_symbol(raw):
        return "us"
    return None


def _looks_like_us_symbol(raw: str) -> bool:
    normalized = canonical_stock_code(raw)
    return is_us_stock_code(normalized) or is_us_index_code(normalized)


def _looks_like_cn_symbol(raw: str, normalized: str) -> bool:
    del raw
    return normalized.isdigit() and len(normalized) == 6 and not normalized.startswith("900")


def _looks_like_hk_symbol(raw: str, normalized: str) -> bool:
    upper = canonical_stock_code(raw)
    return (
        _is_hk_canonical(normalized)
        or (upper.endswith(".HK") and upper[:-3].isdigit() and 1 <= len(upper[:-3]) <= 5)
        or (upper.startswith("HK") and upper[2:].isdigit() and 1 <= len(upper[2:]) <= 5)
    )


def _normalize_hk_symbol(raw: str, normalized: str) -> str:
    if _is_hk_canonical(normalized):
        return normalized
    upper = canonical_stock_code(raw)
    if upper.endswith(".HK") and upper[:-3].isdigit():
        return f"HK{upper[:-3].zfill(5)}"
    if upper.startswith("HK") and upper[2:].isdigit():
        return f"HK{upper[2:].zfill(5)}"
    if upper.isdigit() and 1 <= len(upper) <= 5:
        return f"HK{upper.zfill(5)}"
    return normalized


def _is_hk_canonical(symbol: str) -> bool:
    return symbol.startswith("HK") and symbol[2:].isdigit() and len(symbol[2:]) == 5


def _result(
    raw_symbol: str,
    normalized_symbol: str,
    market: str | None,
    status: SymbolValidationStatus,
    message: str,
) -> ConsumerSymbolPrecheck:
    return ConsumerSymbolPrecheck(
        raw_symbol=raw_symbol,
        normalized_symbol=normalized_symbol,
        market=market,
        status=status,
        message=message,
    )
