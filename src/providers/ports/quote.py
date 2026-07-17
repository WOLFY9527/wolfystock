"""Normalized quote value and acquisition port."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Mapping, Protocol

from src.providers.types import ProviderDataResult


@dataclass(frozen=True, slots=True)
class QuoteRequest:
    symbol: str

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("quote symbol must be a non-empty string")


@dataclass(frozen=True, slots=True)
class QuoteData:
    symbol: str
    name: str | None = None
    price: float | None = None
    change_pct: float | None = None
    change_amount: float | None = None
    volume: int | None = None
    amount: float | None = None
    volume_ratio: float | None = None
    turnover_rate: float | None = None
    amplitude: float | None = None
    open_price: float | None = None
    high: float | None = None
    low: float | None = None
    pre_close: float | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    total_mv: float | None = None
    circ_mv: float | None = None
    change_60d: float | None = None
    high_52w: float | None = None
    low_52w: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("quote symbol must be a non-empty string")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "QuoteData":
        expected = {field.name for field in fields(cls)}
        payload = _strict_mapping(value, expected=expected, context="quote data")
        return cls(**payload)

    def to_dict(self) -> dict[str, Any]:
        return {field.name: getattr(self, field.name) for field in fields(self)}


class QuotePort(Protocol):
    def fetch_quote(self, request: QuoteRequest) -> ProviderDataResult[QuoteData]:
        ...


def _strict_mapping(
    value: Mapping[str, Any],
    *,
    expected: set[str],
    context: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{context} must be a mapping")
    payload = dict(value)
    actual = set(payload)
    if actual != expected:
        raise ValueError(
            f"invalid {context} fields: missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )
    return payload


__all__ = ["QuoteData", "QuotePort", "QuoteRequest"]
