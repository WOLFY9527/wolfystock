# -*- coding: utf-8 -*-
"""Consumer-safe Market Pulse snapshot contract."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


MarketPulseStatus = Literal["ready", "partial", "no_evidence", "unavailable"]
MarketPulseConsumerCopy = Literal[
    "正常",
    "中性",
    "走强",
    "走弱",
    "观察",
    "复核",
    "适合研究观察",
    "暂无证据",
    "暂不可用",
]
MarketPulseMetricLabel = Literal[
    "S&P 500",
    "Nasdaq",
    "Russell 2000",
    "VIX",
    "10Y Treasury yield",
    "Dollar index",
    "Market breadth",
    "Liquidity state",
]
MarketPulseMetricUnit = Literal["pt", "%"]

_FORBIDDEN_TEXT_MARKERS = (
    "buy now",
    "sell now",
    "add position",
    "reduce position",
    "clear position",
    "stop-loss",
    "take-profit",
    "target-price",
    "predicted-return",
    "ai recommends",
    "broker",
    "order",
    "trade execution",
    "provider url",
    "traceback",
    "raw exception",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "token",
    "session",
    "apikey",
    "secret",
    "debug",
    "rawpayload",
)


def _assert_safe_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        compact = value.lower().replace("_", "").replace(" ", "")
        for marker in _FORBIDDEN_TEXT_MARKERS:
            if marker.replace(" ", "") in compact:
                raise ValueError(f"{field_name} contains forbidden text marker: {marker}")
        return
    if isinstance(value, BaseModel):
        _assert_safe_text(value.model_dump(mode="json"), field_name=field_name)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_safe_text(item, field_name=f"{field_name}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_safe_text(item, field_name=f"{field_name}[{index}]")


class MarketPulseDataQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: MarketPulseConsumerCopy
    label: MarketPulseConsumerCopy
    available: bool = False


class MarketPulseMetricItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: MarketPulseMetricLabel
    value: float | None = None
    unit: MarketPulseMetricUnit | None = None
    change: float | None = None
    state: MarketPulseConsumerCopy
    interpretation: MarketPulseConsumerCopy
    dataQuality: MarketPulseDataQuality

    @model_validator(mode="after")
    def _validate_safe_text(self):
        _assert_safe_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


class MarketPulseSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: MarketPulseStatus
    asOf: str | None = None
    indices: list[MarketPulseMetricItem] = Field(default_factory=list)
    volatility: MarketPulseMetricItem
    rates: MarketPulseMetricItem
    dollar: MarketPulseMetricItem
    breadth: MarketPulseMetricItem
    liquidity: MarketPulseMetricItem
    dataQuality: MarketPulseDataQuality
    noAdviceDisclosure: str

    @model_validator(mode="after")
    def _validate_safe_text(self):
        _assert_safe_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self
