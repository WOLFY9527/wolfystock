# -*- coding: utf-8 -*-
"""Consumer-safe homepage dashboard overview contract."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


DashboardOverviewStatus = Literal["ready", "partial", "no_evidence", "unavailable"]
DashboardPublicState = Literal["ready", "delayed", "cached", "partial", "no_evidence", "unavailable"]
ResearchQueueAction = Literal[
    "观察",
    "复核",
    "研究",
    "证据",
    "走强",
    "走弱",
    "扩散",
    "收敛",
    "分歧",
    "暂无证据",
    "适合研究观察",
]
ResearchQueuePriority = Literal["high", "medium", "low"]

_FORBIDDEN_TEXT_MARKERS = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "清仓",
    "止损",
    "止盈",
    "目标价",
    "收益预测",
    "AI推荐",
    "智能选股",
    "交易执行",
    "broker execution",
    "provider url",
    "traceback",
    "raw exception",
    "reasoncode",
    "trustlevel",
    "sourcetype",
)


def _assert_safe_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        compact = value.lower().replace("_", "").replace(" ", "")
        for marker in _FORBIDDEN_TEXT_MARKERS:
            if marker.lower().replace(" ", "") in compact:
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


class _DashboardOverviewBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_safe_text(self):
        _assert_safe_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


class DashboardMetric(_DashboardOverviewBase):
    label: str
    value: str
    change: str
    status: DashboardPublicState


class DashboardSummaryItem(_DashboardOverviewBase):
    summary: str
    status: DashboardPublicState


class DashboardMarketPulse(_DashboardOverviewBase):
    sp500: DashboardMetric
    nasdaq: DashboardMetric
    russell2000: DashboardMetric
    vix: DashboardMetric
    tenYearYield: DashboardMetric
    dollarIndex: DashboardMetric
    marketBreadth: DashboardSummaryItem
    liquidityState: str


class DashboardMarketBrief(_DashboardOverviewBase):
    headline: str
    summary: str
    status: DashboardOverviewStatus


class DashboardMoneyFlow(_DashboardOverviewBase):
    topInflows: list[str] = Field(default_factory=list)
    topOutflows: list[str] = Field(default_factory=list)
    styleBias: str
    offensiveDefensiveBias: str
    sourceStatus: DashboardPublicState
    status: DashboardOverviewStatus


class DashboardLiquidityRisk(_DashboardOverviewBase):
    summary: str
    volatilityTone: str
    fundingStress: str
    dollarRatePressure: str
    status: DashboardOverviewStatus


class DashboardSectorThemeRotation(_DashboardOverviewBase):
    leadingThemes: list[str] = Field(default_factory=list)
    laggingThemes: list[str] = Field(default_factory=list)
    diffusion: str
    summary: str
    status: DashboardOverviewStatus


class DashboardResearchQueueItem(_DashboardOverviewBase):
    title: str
    summary: str
    action: ResearchQueueAction
    priority: ResearchQueuePriority


class DashboardResearchQueue(_DashboardOverviewBase):
    status: DashboardOverviewStatus
    items: list[DashboardResearchQueueItem] = Field(default_factory=list)


class DashboardDataQuality(_DashboardOverviewBase):
    state: DashboardPublicState
    label: str
    summary: str
    sections: dict[str, DashboardPublicState]


class DashboardMarketIntelligenceOverviewResponse(_DashboardOverviewBase):
    status: DashboardOverviewStatus
    asOf: str
    marketPulse: DashboardMarketPulse
    marketBrief: DashboardMarketBrief
    moneyFlow: DashboardMoneyFlow
    liquidityRisk: DashboardLiquidityRisk
    sectorThemeRotation: DashboardSectorThemeRotation
    researchQueue: DashboardResearchQueue
    dataQuality: DashboardDataQuality
    productReadModel: dict[str, Any] = Field(default_factory=dict)
    noAdviceDisclosure: str
