"""Normalized macro value and acquisition port."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from src.providers.types import ProviderDataResult


@dataclass(frozen=True, slots=True)
class MacroRequest:
    series_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.series_id, str) or not self.series_id.strip():
            raise ValueError("macro series_id must be a non-empty string")


@dataclass(frozen=True, slots=True)
class MacroData:
    series_id: str
    value: float | int
    unit: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.series_id, str) or not self.series_id.strip():
            raise ValueError("macro series_id must be a non-empty string")
        if isinstance(self.value, bool) or not isinstance(self.value, (float, int)):
            raise TypeError("macro value must be numeric")
        if self.unit is not None and not isinstance(self.unit, str):
            raise TypeError("macro unit must be a string or None")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MacroData":
        if not isinstance(value, Mapping):
            raise TypeError("macro data must be a mapping")
        payload = dict(value)
        expected = {"seriesId", "value", "unit"}
        if set(payload) != expected:
            raise ValueError(
                f"invalid macro data fields: missing={sorted(expected - set(payload))}, "
                f"unexpected={sorted(set(payload) - expected)}"
            )
        series_id = payload["seriesId"]
        if not isinstance(series_id, str):
            raise TypeError("macro seriesId must be a string")
        return cls(series_id=series_id, value=payload["value"], unit=payload["unit"])

    def to_dict(self) -> dict[str, Any]:
        return {"seriesId": self.series_id, "value": self.value, "unit": self.unit}


class MacroPort(Protocol):
    def fetch_macro(self, request: MacroRequest) -> ProviderDataResult[MacroData]:
        ...


__all__ = ["MacroData", "MacroPort", "MacroRequest"]
