"""Normalized historical series values and acquisition port."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Mapping, Protocol

from src.providers.types import ProviderDataResult


@dataclass(frozen=True, slots=True)
class HistoryRequest:
    symbol: str
    start: str
    end: str
    interval: str

    def __post_init__(self) -> None:
        for name in ("symbol", "start", "end", "interval"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"history {name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class HistoryBar:
    period: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    adjusted_close: float | None = None
    volume: float | int | None = None
    amount: float | None = None
    change_pct: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.period, str) or not self.period.strip():
            raise ValueError("history period must be a non-empty string")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HistoryBar":
        payload = _strict_mapping(
            value,
            expected={field.name for field in fields(cls)},
            context="history bar",
        )
        return cls(**payload)

    def to_dict(self) -> dict[str, Any]:
        return {field.name: getattr(self, field.name) for field in fields(self)}


@dataclass(frozen=True, slots=True)
class HistoryData:
    symbol: str
    bars: tuple[HistoryBar, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("history symbol must be a non-empty string")
        if not isinstance(self.bars, tuple) or not self.bars:
            raise ValueError("observed history data requires at least one bar")
        if any(not isinstance(item, HistoryBar) for item in self.bars):
            raise TypeError("history bars must contain only HistoryBar values")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HistoryData":
        payload = _strict_mapping(value, expected={"symbol", "bars"}, context="history data")
        bars = payload["bars"]
        if not isinstance(bars, list):
            raise TypeError("history bars must be a list")
        return cls(
            symbol=_strict_string(payload["symbol"], field="history symbol"),
            bars=tuple(HistoryBar.from_dict(item) for item in bars),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"symbol": self.symbol, "bars": [item.to_dict() for item in self.bars]}


class HistoryPort(Protocol):
    def fetch_history(self, request: HistoryRequest) -> ProviderDataResult[HistoryData]:
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


def _strict_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    return value


__all__ = ["HistoryBar", "HistoryData", "HistoryPort", "HistoryRequest"]
