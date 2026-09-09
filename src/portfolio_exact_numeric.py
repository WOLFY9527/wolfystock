# -*- coding: utf-8 -*-
"""Central exact-decimal policy for authoritative Portfolio values.

Public callers must use the context-aware parse/normalize/serialize helpers below.
The two generic aliases at the end of this module exist only while legacy storage
and migration owners are being moved to the context-aware boundary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional

import pandas as pd
from sqlalchemy import Numeric, Text
from sqlalchemy.types import TypeDecorator, TypeEngine


PORTFOLIO_STORAGE_PRECISION = 24
PORTFOLIO_STORAGE_SCALE = 8
PORTFOLIO_STORAGE_QUANTUM = Decimal("0.00000001")
PORTFOLIO_ROUNDING = ROUND_HALF_EVEN
STOCK_DAILY_CLOSE_PROVENANCE_ATTR = "wolfystock.stock_daily.close_tokens.v1"


def attach_stock_daily_close_tokens(
    frame: pd.DataFrame,
    raw_close_tokens: list[Any],
) -> pd.DataFrame:
    """Attach verified textual/Decimal daily-close provenance for strict storage."""

    result = frame.copy()
    result.attrs.pop(STOCK_DAILY_CLOSE_PROVENANCE_ATTR, None)
    if "date" not in result.columns or len(result) != len(raw_close_tokens):
        return result

    token_by_date: dict[str, Any] = {}
    for row_date, token in zip(result["date"].tolist(), raw_close_tokens):
        if not isinstance(token, (Decimal, str)):
            return result
        parsed_date = pd.to_datetime(row_date, errors="coerce")
        if pd.isna(parsed_date):
            return result
        date_key = parsed_date.date().isoformat()
        if date_key in token_by_date:
            return result
        token_by_date[date_key] = token

    result.attrs[STOCK_DAILY_CLOSE_PROVENANCE_ATTR] = token_by_date
    return result

# These aliases preserve the existing storage decorator contract while callers
# are migrated to the explicit policy functions below.
PORTFOLIO_EXACT_NUMERIC_PRECISION = PORTFOLIO_STORAGE_PRECISION
PORTFOLIO_EXACT_NUMERIC_SCALE = PORTFOLIO_STORAGE_SCALE
PORTFOLIO_EXACT_NUMERIC_QUANTUM = PORTFOLIO_STORAGE_QUANTUM
PORTFOLIO_EXACT_NUMERIC_ROUNDING = PORTFOLIO_ROUNDING

PORTFOLIO_CURRENCY_MINOR_SCALES: Mapping[str, int] = MappingProxyType(
    {
        "AUD": 2,
        "CAD": 2,
        "CHF": 2,
        "CNY": 2,
        "EUR": 2,
        "GBP": 2,
        "HKD": 2,
        "INR": 2,
        "JPY": 0,
        "KRW": 0,
        "NZD": 2,
        "SEK": 2,
        "SGD": 2,
        "TWD": 2,
        "USD": 2,
    }
)
PORTFOLIO_ASSET_MARKET_SCALES: Mapping[str, int] = MappingProxyType(
    {
        "cn": 8,
        "global": 8,
        "hk": 8,
        "us": 8,
    }
)


class PortfolioNumericKind(str, Enum):
    """Stable field categories accepted by the context-aware public API."""

    MONEY = "money"
    QUANTITY = "quantity"
    PRICE = "price"
    FX_RATE = "fx_rate"
    RATE = "rate"
    RATIO = "ratio"
    STORAGE = "storage"


PORTFOLIO_PRECISION_KINDS = frozenset(kind.value for kind in PortfolioNumericKind)

_PORTFOLIO_STORAGE_MAX_ABSOLUTE = Decimal(10) ** (
    PORTFOLIO_STORAGE_PRECISION - PORTFOLIO_STORAGE_SCALE
)
_PUBLIC_DECIMAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")


class PortfolioPrecisionError(ValueError):
    """Raised when a Portfolio precision context is missing or unsupported."""


class PortfolioExactNumericError(PortfolioPrecisionError):
    """Raised when a Portfolio value cannot be represented by its policy."""


@dataclass(frozen=True)
class PortfolioPrecision:
    """Resolved exact-value contract for one Portfolio field category."""

    kind: str
    scale: int
    rounding: str
    currency: Optional[str] = None
    market: Optional[str] = None
    from_currency: Optional[str] = None
    to_currency: Optional[str] = None

    @property
    def quantum(self) -> Decimal:
        return Decimal(1).scaleb(-self.scale)


def _normalize_kind(kind: str) -> str:
    if not isinstance(kind, str):
        raise PortfolioPrecisionError("portfolio precision kind must be a string")
    normalized = kind.strip().lower()
    if normalized not in PORTFOLIO_PRECISION_KINDS:
        raise PortfolioPrecisionError(f"unsupported portfolio precision kind: {kind!r}")
    return normalized


def _normalize_currency(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise PortfolioPrecisionError(f"{field_name} must be a supported currency code")
    normalized = value.strip().upper()
    if normalized not in PORTFOLIO_CURRENCY_MINOR_SCALES:
        raise PortfolioPrecisionError(f"unsupported portfolio currency: {value!r}")
    return normalized


def _normalize_market(value: object) -> str:
    if not isinstance(value, str):
        raise PortfolioPrecisionError("market must be a supported asset market")
    normalized = value.strip().lower()
    if normalized not in PORTFOLIO_ASSET_MARKET_SCALES:
        raise PortfolioPrecisionError(f"unsupported portfolio market: {value!r}")
    return normalized


def resolve_portfolio_precision(
    *,
    kind: str,
    currency: Optional[str] = None,
    market: Optional[str] = None,
    from_currency: Optional[str] = None,
    to_currency: Optional[str] = None,
) -> PortfolioPrecision:
    """Resolve one reviewed context to an immutable precision contract.

    Money requires a supported currency, price and quantity require a supported
    asset market, and FX rates require both sides of a supported currency pair.
    Generic storage is intentionally context-free and internal-only.
    """

    normalized_kind = _normalize_kind(kind)
    normalized_currency = (
        _normalize_currency(currency, field_name="currency") if currency is not None else None
    )
    normalized_market = _normalize_market(market) if market is not None else None
    normalized_from_currency = (
        _normalize_currency(from_currency, field_name="from_currency")
        if from_currency is not None
        else None
    )
    normalized_to_currency = (
        _normalize_currency(to_currency, field_name="to_currency")
        if to_currency is not None
        else None
    )

    if normalized_kind == "money":
        if normalized_currency is None:
            raise PortfolioPrecisionError("money precision requires currency")
        if normalized_from_currency is not None or normalized_to_currency is not None:
            raise PortfolioPrecisionError("money precision does not accept an FX currency pair")
        return PortfolioPrecision(
            kind=normalized_kind,
            scale=PORTFOLIO_CURRENCY_MINOR_SCALES[normalized_currency],
            rounding=PORTFOLIO_ROUNDING,
            currency=normalized_currency,
            market=normalized_market,
        )

    if normalized_kind in {"quantity", "price"}:
        if normalized_market is None:
            raise PortfolioPrecisionError(f"{normalized_kind} precision requires market")
        if normalized_from_currency is not None or normalized_to_currency is not None:
            raise PortfolioPrecisionError(
                f"{normalized_kind} precision does not accept an FX currency pair"
            )
        return PortfolioPrecision(
            kind=normalized_kind,
            scale=PORTFOLIO_ASSET_MARKET_SCALES[normalized_market],
            rounding=PORTFOLIO_ROUNDING,
            currency=normalized_currency,
            market=normalized_market,
        )

    if normalized_kind == "fx_rate":
        if (normalized_from_currency is None) != (normalized_to_currency is None):
            raise PortfolioPrecisionError(
                "fx_rate precision requires both from_currency and to_currency when either is supplied"
            )
        return PortfolioPrecision(
            kind=normalized_kind,
            scale=PORTFOLIO_STORAGE_SCALE,
            rounding=PORTFOLIO_ROUNDING,
            currency=normalized_currency,
            market=normalized_market,
            from_currency=normalized_from_currency,
            to_currency=normalized_to_currency,
        )

    if normalized_kind in {"rate", "ratio"}:
        if normalized_from_currency is not None or normalized_to_currency is not None:
            raise PortfolioPrecisionError(
                f"{normalized_kind} precision does not accept an FX currency pair"
            )
        return PortfolioPrecision(
            kind=normalized_kind,
            scale=PORTFOLIO_STORAGE_SCALE,
            rounding=PORTFOLIO_ROUNDING,
            currency=normalized_currency,
            market=normalized_market,
        )

    if any(
        value is not None
        for value in (
            normalized_currency,
            normalized_market,
            normalized_from_currency,
            normalized_to_currency,
        )
    ):
        raise PortfolioPrecisionError("storage precision does not accept public context")
    return PortfolioPrecision(
        kind="storage",
        scale=PORTFOLIO_STORAGE_SCALE,
        rounding=PORTFOLIO_ROUNDING,
    )


def _parse_decimal(value: Any, *, allow_legacy_float: bool) -> Decimal:
    if isinstance(value, bool):
        raise PortfolioExactNumericError("portfolio numeric value must not be boolean")
    if isinstance(value, float) and not allow_legacy_float:
        raise PortfolioExactNumericError("portfolio public numeric values must not be binary floats")

    if isinstance(value, Decimal):
        decimal_value = value
    elif isinstance(value, int):
        decimal_value = Decimal(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise PortfolioExactNumericError("portfolio numeric value is empty")
        if not allow_legacy_float and _PUBLIC_DECIMAL_RE.fullmatch(text) is None:
            raise PortfolioExactNumericError("portfolio public numeric value is malformed")
        try:
            decimal_value = Decimal(text)
        except (InvalidOperation, ValueError) as exc:
            raise PortfolioExactNumericError("portfolio numeric value is invalid") from exc
    elif isinstance(value, float):
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise PortfolioExactNumericError("portfolio numeric value is invalid") from exc
    else:
        raise PortfolioExactNumericError("portfolio numeric value must be Decimal, int, or string")

    if not decimal_value.is_finite():
        raise PortfolioExactNumericError("portfolio numeric value must be finite")
    return decimal_value


def _round_decimal(value: Decimal, precision: PortfolioPrecision) -> Decimal:
    try:
        with localcontext() as context:
            context.prec = max(
                PORTFOLIO_STORAGE_PRECISION,
                len(value.as_tuple().digits) + precision.scale + 1,
            )
            normalized = value.quantize(precision.quantum, rounding=precision.rounding)
    except InvalidOperation as exc:
        raise PortfolioExactNumericError(
            "portfolio numeric value cannot be rounded to the resolved precision"
        ) from exc

    if normalized.copy_abs() >= _PORTFOLIO_STORAGE_MAX_ABSOLUTE:
        raise PortfolioExactNumericError("portfolio numeric value exceeds storage precision")
    if normalized.is_zero():
        return Decimal(0).quantize(precision.quantum)
    return normalized


def parse_portfolio_decimal(
    value: Any,
    *,
    kind: str,
    currency: Optional[str] = None,
    market: Optional[str] = None,
    from_currency: Optional[str] = None,
    to_currency: Optional[str] = None,
) -> Decimal:
    """Parse normal ingress exactly and reject values requiring implicit rounding."""

    precision = resolve_portfolio_precision(
        kind=kind,
        currency=currency,
        market=market,
        from_currency=from_currency,
        to_currency=to_currency,
    )
    parsed = _parse_decimal(value, allow_legacy_float=False)
    normalized = _round_decimal(parsed, precision)
    if parsed != normalized:
        raise PortfolioExactNumericError(
            "portfolio numeric value exceeds the resolved fractional precision"
        )
    return normalized


def parse_portfolio_decimal_transport(value: Any) -> Decimal:
    """Parse a public decimal token before its owning context is available.

    This transport boundary deliberately chooses no precision. The caller must
    resolve the value as money, quantity, price, or another reviewed kind before
    using it for storage or arithmetic.
    """

    return _parse_decimal(value, allow_legacy_float=False)


def round_portfolio_decimal_value(
    value: Any,
    *,
    kind: str,
    currency: Optional[str] = None,
    market: Optional[str] = None,
    from_currency: Optional[str] = None,
    to_currency: Optional[str] = None,
) -> Decimal:
    """Round derived exact arithmetic to its resolved policy boundary."""

    precision = resolve_portfolio_precision(
        kind=kind,
        currency=currency,
        market=market,
        from_currency=from_currency,
        to_currency=to_currency,
    )
    return _round_decimal(_parse_decimal(value, allow_legacy_float=False), precision)


def normalize_portfolio_decimal_value(
    value: Any,
    *,
    kind: str,
    currency: Optional[str] = None,
    market: Optional[str] = None,
    from_currency: Optional[str] = None,
    to_currency: Optional[str] = None,
) -> Decimal:
    """Normalize normal ingress without permitting an implicit precision loss."""

    return parse_portfolio_decimal(
        value,
        kind=kind,
        currency=currency,
        market=market,
        from_currency=from_currency,
        to_currency=to_currency,
    )


def serialize_portfolio_decimal_value(
    value: Any,
    *,
    kind: str,
    currency: Optional[str] = None,
    market: Optional[str] = None,
    from_currency: Optional[str] = None,
    to_currency: Optional[str] = None,
) -> str:
    """Serialize normal ingress values as canonical, exact decimal text."""

    return format(
        parse_portfolio_decimal(
            value,
            kind=kind,
            currency=currency,
            market=market,
            from_currency=from_currency,
            to_currency=to_currency,
        ),
        "f",
    )


def portfolio_decimal_equal(
    left: Any,
    right: Any,
    *,
    kind: str,
    currency: Optional[str] = None,
    market: Optional[str] = None,
    from_currency: Optional[str] = None,
    to_currency: Optional[str] = None,
) -> bool:
    """Compare two normal-ingress values after exact policy resolution."""

    context = {
        "kind": kind,
        "currency": currency,
        "market": market,
        "from_currency": from_currency,
        "to_currency": to_currency,
    }
    return parse_portfolio_decimal(left, **context) == parse_portfolio_decimal(right, **context)


def normalize_portfolio_value(
    value: Any,
    *,
    kind: str,
    currency: Optional[str] = None,
    market: Optional[str] = None,
) -> Decimal:
    """Stable public API for derived exact values at a reviewed policy boundary."""

    return normalize_portfolio_decimal_value(
        value,
        kind=kind,
        currency=currency,
        market=market,
    )


def serialize_portfolio_value(
    value: Any,
    *,
    kind: str,
    currency: Optional[str] = None,
    market: Optional[str] = None,
) -> str:
    """Stable public API for canonical, exact Portfolio wire values."""

    return serialize_portfolio_decimal_value(
        value,
        kind=kind,
        currency=currency,
        market=market,
    )


def portfolio_values_equal(
    left: Any,
    right: Any,
    *,
    kind: str,
    currency: Optional[str] = None,
    market: Optional[str] = None,
) -> bool:
    """Stable public API for exact equality at the resolved policy quantum."""

    return portfolio_decimal_equal(
        left,
        right,
        kind=kind,
        currency=currency,
        market=market,
    )


def normalize_legacy_portfolio_decimal(
    value: Any,
    *,
    kind: str = "storage",
    currency: Optional[str] = None,
    market: Optional[str] = None,
    from_currency: Optional[str] = None,
    to_currency: Optional[str] = None,
) -> Decimal:
    """Convert legacy storage/migration input through this same policy registry.

    This is intentionally the only float-accepting entry point. It is for
    historical storage conversion, never API, import, or interactive ingress.
    """

    precision = resolve_portfolio_precision(
        kind=kind,
        currency=currency,
        market=market,
        from_currency=from_currency,
        to_currency=to_currency,
    )
    return _round_decimal(_parse_decimal(value, allow_legacy_float=True), precision)


def serialize_legacy_portfolio_decimal(
    value: Any,
    *,
    kind: str = "storage",
    currency: Optional[str] = None,
    market: Optional[str] = None,
    from_currency: Optional[str] = None,
    to_currency: Optional[str] = None,
) -> str:
    """Serialize legacy storage/migration input using the shared registry."""

    return format(
        normalize_legacy_portfolio_decimal(
            value,
            kind=kind,
            currency=currency,
            market=market,
            from_currency=from_currency,
            to_currency=to_currency,
        ),
        "f",
    )


def normalize_portfolio_decimal(value: Any) -> Decimal:
    """Legacy generic storage alias; do not use for normal public ingress."""

    return normalize_legacy_portfolio_decimal(value)


def serialize_portfolio_decimal(value: Any) -> str:
    """Legacy generic storage alias; do not use for API serialization."""

    return serialize_legacy_portfolio_decimal(value)


class PortfolioExactNumeric(TypeDecorator):
    """Persist exact Portfolio storage numerics as SQLite TEXT or SQL NUMERIC."""

    impl = Numeric(
        PORTFOLIO_STORAGE_PRECISION,
        PORTFOLIO_STORAGE_SCALE,
        asdecimal=True,
    )
    cache_ok = True

    def load_dialect_impl(self, dialect) -> TypeEngine[Any]:
        if dialect.name == "sqlite":
            return dialect.type_descriptor(Text())
        return dialect.type_descriptor(
            Numeric(
                PORTFOLIO_STORAGE_PRECISION,
                PORTFOLIO_STORAGE_SCALE,
                asdecimal=True,
            )
        )

    def process_bind_param(self, value: Any, dialect) -> Any:
        if value is None:
            return None
        normalized = parse_portfolio_decimal(value, kind="storage")
        if dialect.name == "sqlite":
            return format(normalized, "f")
        return normalized

    def process_result_value(self, value: Any, dialect) -> Any:
        if value is None:
            return None
        return normalize_legacy_portfolio_decimal(value)

    @property
    def python_type(self) -> type[Decimal]:
        return Decimal
