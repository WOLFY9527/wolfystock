# -*- coding: utf-8 -*-
"""Consumer-safe Market Pulse snapshot contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


class MarketPulseDataQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: MarketPulseConsumerCopy
    label: MarketPulseConsumerCopy
    available: bool = False


class MarketPulseMetricItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    value: float | None = None
    unit: str | None = None
    change: float | None = None
    state: MarketPulseConsumerCopy
    interpretation: MarketPulseConsumerCopy
    dataQuality: MarketPulseDataQuality


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
