# -*- coding: utf-8 -*-
"""Consumer-safe homepage section layout contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


HomepageSectionLayoutStatus = Literal["ready", "partial", "no_evidence", "unavailable"]
HomepageSectionGroup = Literal[
    "dailyBrief",
    "marketPulse",
    "riskAndPricing",
    "crossAsset",
    "liquidityAndBreadth",
    "eventsAndCatalysts",
    "themesAndLeadership",
    "policyAndMacro",
    "researchQueue",
    "evidenceAndReadiness",
]
HomepageSectionModuleKey = Literal[
    "daily_market_brief",
    "after_close_developments",
    "market_breadth",
    "risk_regime",
    "rates_pricing",
    "volatility_positioning",
    "cross_asset_indicators",
    "liquidity_credit",
    "event_impact_map",
    "earnings_catalysts",
    "geopolitical_commodity_risk",
    "theme_capital_flow",
    "style_leadership_rotation",
    "ai_capex_infrastructure",
    "policy_regulation_watch",
    "scenario_watchlist",
    "research_priorities",
    "pre_session_research_checklist",
    "evidence_quality",
]
HomepageSectionRegion = Literal["top_strip", "main_left", "main_center", "main_right", "secondary", "utility"]
HomepageSectionDensity = Literal["compact", "standard", "expanded"]

ALLOWED_HOMEPAGE_SECTION_LAYOUT_STATUSES: frozenset[str] = frozenset(
    {"ready", "partial", "no_evidence", "unavailable"}
)
ALLOWED_HOMEPAGE_SECTION_GROUPS: frozenset[str] = frozenset(
    {
        "dailyBrief",
        "marketPulse",
        "riskAndPricing",
        "crossAsset",
        "liquidityAndBreadth",
        "eventsAndCatalysts",
        "themesAndLeadership",
        "policyAndMacro",
        "researchQueue",
        "evidenceAndReadiness",
    }
)
ALLOWED_HOMEPAGE_SECTION_MODULES: frozenset[str] = frozenset(
    {
        "daily_market_brief",
        "after_close_developments",
        "market_breadth",
        "risk_regime",
        "rates_pricing",
        "volatility_positioning",
        "cross_asset_indicators",
        "liquidity_credit",
        "event_impact_map",
        "earnings_catalysts",
        "geopolitical_commodity_risk",
        "theme_capital_flow",
        "style_leadership_rotation",
        "ai_capex_infrastructure",
        "policy_regulation_watch",
        "scenario_watchlist",
        "research_priorities",
        "pre_session_research_checklist",
        "evidence_quality",
    }
)
ALLOWED_HOMEPAGE_SECTION_REGIONS: frozenset[str] = frozenset(
    {"top_strip", "main_left", "main_center", "main_right", "secondary", "utility"}
)
ALLOWED_HOMEPAGE_SECTION_DENSITIES: frozenset[str] = frozenset({"compact", "standard", "expanded"})

_FORBIDDEN_TEXT_MARKERS = (
    "买入",
    "卖出",
    "下单",
    "交易信号",
    "交易指令",
    "交易建议",
    "止损",
    "止盈",
    "目标价",
    "加仓",
    "减仓",
    "清仓",
    "收益预测",
    "buy now",
    "sell now",
    "trading signal",
    "trading instruction",
    "target price",
    "ai recommends",
    "traceback",
    "provider",
    "cache",
    "fallback",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "token",
    "sessionid",
    "session token",
    "apikey",
    "secret",
    "cookie",
    "debug",
    "raw",
    "internal.example",
    "/tmp/",
    "launch",
    "launcher",
    "navigate",
    "open module",
    "打开",
    "进入",
    "跳转",
    "导航",
    "入口",
)


def _assert_safe_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        compact = value.lower().replace("_", "").replace(" ", "")
        for marker in _FORBIDDEN_TEXT_MARKERS:
            if marker.lower().replace(" ", "") in compact:
                raise ValueError(f"{field_name} contains forbidden text marker: {marker}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_safe_text(item, field_name=f"{field_name}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_safe_text(item, field_name=f"{field_name}[{index}]")


def _assert_choice(value: str, allowed: frozenset[str], *, field_name: str) -> None:
    if value not in allowed:
        raise ValueError(f"{field_name} must be one of {sorted(allowed)}")


def _assert_text(value: str, *, field_name: str, max_length: int) -> None:
    if not value or len(value) > max_length:
        raise ValueError(f"{field_name} must be 1-{max_length} characters")
    _assert_safe_text(value, field_name=field_name)


@dataclass(frozen=True)
class HomepageSectionLayoutDataQuality:
    state: HomepageSectionLayoutStatus
    label: str
    summary: str

    def __post_init__(self) -> None:
        _assert_choice(self.state, ALLOWED_HOMEPAGE_SECTION_LAYOUT_STATUSES, field_name="dataQuality.state")
        _assert_text(self.label, field_name="dataQuality.label", max_length=40)
        _assert_text(self.summary, field_name="dataQuality.summary", max_length=160)

    def to_dict(self) -> dict[str, str]:
        return {
            "state": self.state,
            "label": self.label,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class HomepageSectionLayoutModule:
    key: HomepageSectionModuleKey
    label: str
    priority: int
    required: bool
    reviewPoint: str

    def __post_init__(self) -> None:
        _assert_choice(self.key, ALLOWED_HOMEPAGE_SECTION_MODULES, field_name="module.key")
        _assert_text(self.label, field_name=f"{self.key}.label", max_length=40)
        if self.priority < 1 or self.priority > 100:
            raise ValueError("module.priority must be between 1 and 100")
        _assert_text(self.reviewPoint, field_name=f"{self.key}.reviewPoint", max_length=160)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "priority": self.priority,
            "required": self.required,
            "reviewPoint": self.reviewPoint,
        }


@dataclass(frozen=True)
class HomepageSectionLayoutItem:
    key: HomepageSectionGroup
    label: str
    priority: int
    region: HomepageSectionRegion
    density: HomepageSectionDensity
    required: bool
    reviewPoint: str
    modules: list[HomepageSectionLayoutModule]

    def __post_init__(self) -> None:
        _assert_choice(self.key, ALLOWED_HOMEPAGE_SECTION_GROUPS, field_name="section.key")
        _assert_text(self.label, field_name=f"{self.key}.label", max_length=40)
        if self.priority < 1 or self.priority > 100:
            raise ValueError("section.priority must be between 1 and 100")
        _assert_choice(self.region, ALLOWED_HOMEPAGE_SECTION_REGIONS, field_name=f"{self.key}.region")
        _assert_choice(self.density, ALLOWED_HOMEPAGE_SECTION_DENSITIES, field_name=f"{self.key}.density")
        _assert_text(self.reviewPoint, field_name=f"{self.key}.reviewPoint", max_length=160)
        if not self.modules:
            raise ValueError("section.modules must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "priority": self.priority,
            "region": self.region,
            "density": self.density,
            "required": self.required,
            "reviewPoint": self.reviewPoint,
            "modules": [module.to_dict() for module in self.modules],
        }


@dataclass(frozen=True)
class HomepageSectionLayoutResponse:
    status: HomepageSectionLayoutStatus
    asOf: str
    sections: list[HomepageSectionLayoutItem]
    noAdviceDisclosure: str
    dataQuality: HomepageSectionLayoutDataQuality

    def __post_init__(self) -> None:
        _assert_choice(self.status, ALLOWED_HOMEPAGE_SECTION_LAYOUT_STATUSES, field_name="status")
        _assert_text(self.asOf, field_name="asOf", max_length=40)
        if not self.sections:
            raise ValueError("sections must not be empty")
        _assert_text(self.noAdviceDisclosure, field_name="noAdviceDisclosure", max_length=120)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "asOf": self.asOf,
            "sections": [section.to_dict() for section in self.sections],
            "noAdviceDisclosure": self.noAdviceDisclosure,
            "dataQuality": self.dataQuality.to_dict(),
        }
