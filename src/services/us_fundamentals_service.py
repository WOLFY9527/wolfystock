# -*- coding: utf-8 -*-
"""Consumer-safe normalized fundamentals for US stock detail surfaces."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional

from src.utils.symbol_classification import is_us_stock_code

logger = logging.getLogger(__name__)

US_FUNDAMENTALS_FIELDS = (
    "companyName",
    "sector",
    "industry",
    "marketCap",
    "revenueTtm",
    "profitabilityMargin",
    "valuationRatio",
    "fiscalPeriod",
    "asOf",
    "source",
    "freshness",
)


class USFundamentalsService:
    """Normalize existing US fundamentals provider output for consumer APIs."""

    def __init__(
        self,
        *,
        fundamentals_fetcher: Optional[Callable[[str], Mapping[str, Any]]] = None,
        now_fn: Optional[Callable[[], str]] = None,
    ) -> None:
        self._fundamentals_fetcher = fundamentals_fetcher
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat())

    def get_us_fundamentals(self, symbol: str) -> dict[str, Any]:
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol or not is_us_stock_code(normalized_symbol):
            return self._empty_payload(
                normalized_symbol,
                state="unsupported",
                source="unsupported",
                freshness="unknown",
                reason="unsupported_market",
            )

        try:
            raw = dict(self._fetcher()(normalized_symbol) or {})
        except Exception:
            logger.warning("US fundamentals provider unavailable for %s", normalized_symbol, exc_info=True)
            return self._empty_payload(
                normalized_symbol,
                state="provider_unavailable",
                source="unavailable",
                freshness="unknown",
                reason="provider_unavailable",
            )

        meta = _mapping(raw.get("_meta"))
        field_periods = _mapping(meta.get("field_periods"))
        field_sources = _mapping(meta.get("field_sources"))
        mapped = {
            "companyName": _safe_text(_first_defined(raw.get("companyName"), raw.get("longName"), raw.get("shortName"))),
            "sector": _safe_text(raw.get("sector")),
            "industry": _safe_text(raw.get("industry")),
            "marketCap": _safe_number(raw.get("marketCap")),
            "revenueTtm": _safe_number(_first_defined(raw.get("revenueTtm"), raw.get("totalRevenue"), raw.get("revenue"))),
            "profitabilityMargin": _safe_number(
                _first_defined(raw.get("profitabilityMargin"), raw.get("operatingMargins"), raw.get("grossMargins"))
            ),
            "valuationRatio": _safe_number(
                _first_defined(raw.get("valuationRatio"), raw.get("trailingPE"), raw.get("forwardPE"), raw.get("priceToBook"))
            ),
        }
        fields_available = [field for field in mapped if mapped[field] not in (None, "")]
        if not fields_available:
            return self._empty_payload(
                normalized_symbol,
                state="provider_unavailable",
                source="unavailable",
                freshness="unknown",
                reason="provider_unavailable",
            )

        fiscal_period, fiscal_reason = _fiscal_period(field_periods)
        as_of = _safe_text(_first_defined(raw.get("asOf"), raw.get("as_of"), meta.get("asOf"), meta.get("as_of"))) or self._now_fn()
        freshness = "stale" if _is_stale(as_of) else "current"
        source = _source_label(field_sources) or _safe_text(raw.get("source")) or "yfinance"
        state = "stale" if freshness == "stale" else ("available" if len(fields_available) == len(mapped) and not fiscal_reason else "partial")

        missing_reasons = {
            field: "" if mapped.get(field) not in (None, "") else "provider_field_missing"
            for field in mapped
        }
        missing_reasons.update(
            {
                "fiscalPeriod": fiscal_reason,
                "asOf": "" if as_of else "provider_field_missing",
                "source": "" if source else "provider_field_missing",
                "freshness": "" if freshness else "provider_field_missing",
            }
        )
        return {
            "symbol": normalized_symbol,
            "state": state,
            **mapped,
            "fiscalPeriod": fiscal_period,
            "asOf": as_of,
            "source": source,
            "freshness": freshness,
            "fieldsAvailable": fields_available,
            "missingFieldReasons": missing_reasons,
        }

    def _fetcher(self) -> Callable[[str], Mapping[str, Any]]:
        if self._fundamentals_fetcher is not None:
            return self._fundamentals_fetcher
        from data_provider.us_fundamentals_provider import get_yfinance_fundamentals

        return get_yfinance_fundamentals

    @staticmethod
    def _empty_payload(
        symbol: str,
        *,
        state: str,
        source: str,
        freshness: str,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "state": state,
            "companyName": None,
            "sector": None,
            "industry": None,
            "marketCap": None,
            "revenueTtm": None,
            "profitabilityMargin": None,
            "valuationRatio": None,
            "fiscalPeriod": None,
            "asOf": None,
            "source": source,
            "freshness": freshness,
            "fieldsAvailable": [],
            "missingFieldReasons": {field: reason for field in US_FUNDAMENTALS_FIELDS},
        }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _first_defined(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", "N/A", "None"):
            return value
    return None


def _safe_text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _safe_number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fiscal_period(field_periods: Mapping[str, Any]) -> tuple[Optional[str], str]:
    periods = {
        str(value).strip()
        for value in field_periods.values()
        if str(value or "").strip()
    }
    if not periods:
        return None, "provider_field_missing"
    if len(periods) == 1:
        return next(iter(periods)), ""
    return "mixed", "mixed_periods"


def _source_label(field_sources: Mapping[str, Any]) -> Optional[str]:
    sources = {
        str(value).strip()
        for value in field_sources.values()
        if str(value or "").strip()
    }
    if not sources:
        return None
    if len(sources) == 1:
        return next(iter(sources))
    return "mixed"


def _is_stale(as_of: str | None) -> bool:
    if not as_of:
        return False
    try:
        parsed = datetime.fromisoformat(str(as_of).replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).days > 45
