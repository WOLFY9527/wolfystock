# -*- coding: utf-8 -*-
"""Standalone homepage section layout contract service.

This service is intentionally inert. It only exposes a bounded layout/order
contract for frontend UAT and does not wire routes, fetch data, or change
homepage runtime behavior.
"""

from __future__ import annotations

import time
from typing import Any

from api.v1.schemas.homepage_section_layout import (
    HomepageSectionLayoutDataQuality,
    HomepageSectionLayoutItem,
    HomepageSectionLayoutModule,
    HomepageSectionLayoutResponse,
)

NO_ADVICE_DISCLOSURE = "仅用于市场研究编排与证据复核，不作为任何执行依据。"
TOP_LEVEL_DATA_QUALITY_SUMMARY = "当前合同仅描述驾驶舱研究工作流顺序、密度与复核点，不包含实时行情、操作结论或数据质量核查注记。"
ALLOWED_REGIONS = {"top_strip", "main_left", "main_center", "main_right", "secondary", "utility"}
ALLOWED_DENSITIES = {"compact", "standard", "expanded"}

_SECTION_BLUEPRINTS: tuple[dict[str, Any], ...] = (
    {
        "key": "dailyBrief",
        "label": "每日简报",
        "region": "top_strip",
        "density": "compact",
        "required": True,
        "reviewPoint": "复核今日摘要与盘后背景是否先说明研究范围。",
        "modules": (
            {
                "key": "daily_market_brief",
                "label": "每日市场简报",
                "required": True,
                "reviewPoint": "复核主要指数、广度与跨资产线索是否保持研究口径。",
            },
            {
                "key": "after_close_developments",
                "label": "盘后发展",
                "required": True,
                "reviewPoint": "复核盘后宏观、业绩与商品线索是否仅用于背景观察。",
            },
        ),
    },
    {
        "key": "marketPulse",
        "label": "市场脉搏",
        "region": "main_center",
        "density": "standard",
        "required": True,
        "reviewPoint": "复核市场参与度是否作为当前环境的第一层观察。",
        "modules": (
            {
                "key": "market_breadth",
                "label": "市场广度",
                "required": True,
                "reviewPoint": "复核上涨参与率与扩散线索是否保持整体观察口径。",
            },
        ),
    },
    {
        "key": "riskAndPricing",
        "label": "风险与定价",
        "region": "main_left",
        "density": "standard",
        "required": True,
        "reviewPoint": "复核风险、利率与波动线索是否形成一致定价背景。",
        "modules": (
            {
                "key": "risk_regime",
                "label": "风险状态",
                "required": True,
                "reviewPoint": "复核风险语气是否来自公开结构线索。",
            },
            {
                "key": "rates_pricing",
                "label": "利率定价",
                "required": True,
                "reviewPoint": "复核利率路径和估值敏感度是否保持研究表述。",
            },
            {
                "key": "volatility_positioning",
                "label": "波动定位",
                "required": True,
                "reviewPoint": "复核波动与情绪线索是否只表达观察条件。",
            },
        ),
    },
    {
        "key": "crossAsset",
        "label": "跨资产线索",
        "region": "main_center",
        "density": "standard",
        "required": True,
        "reviewPoint": "复核指数、利率、美元与商品线索是否同框比较。",
        "modules": (
            {
                "key": "cross_asset_indicators",
                "label": "跨资产指标",
                "required": True,
                "reviewPoint": "复核跨资产指标是否用于验证宏观背景。",
            },
        ),
    },
    {
        "key": "liquidityAndBreadth",
        "label": "流动性与广度",
        "region": "main_left",
        "density": "standard",
        "required": True,
        "reviewPoint": "复核信用、成交与参与度线索是否共同解释市场质量。",
        "modules": (
            {
                "key": "liquidity_credit",
                "label": "流动性信用",
                "required": True,
                "reviewPoint": "复核流动性和信用环境是否保持证据整理口径。",
            },
        ),
    },
    {
        "key": "eventsAndCatalysts",
        "label": "事件与催化",
        "region": "main_right",
        "density": "expanded",
        "required": True,
        "reviewPoint": "复核事件、业绩与地缘商品线索是否按影响路径排列。",
        "modules": (
            {
                "key": "event_impact_map",
                "label": "事件影响图",
                "required": True,
                "reviewPoint": "复核事件影响是否按资产、行业与时间窗口整理。",
            },
            {
                "key": "earnings_catalysts",
                "label": "业绩催化",
                "required": True,
                "reviewPoint": "复核业绩线索是否聚焦披露质量和行业传导。",
            },
            {
                "key": "geopolitical_commodity_risk",
                "label": "地缘商品风险",
                "required": True,
                "reviewPoint": "复核地缘和商品风险是否保持情景观察。",
            },
        ),
    },
    {
        "key": "themesAndLeadership",
        "label": "主题与领先",
        "region": "secondary",
        "density": "expanded",
        "required": True,
        "reviewPoint": "复核资金主题、风格轮动与AI基建是否按领导力线索排列。",
        "modules": (
            {
                "key": "theme_capital_flow",
                "label": "主题资金流",
                "required": True,
                "reviewPoint": "复核主题资金线索是否用于观察扩散与持续性。",
            },
            {
                "key": "style_leadership_rotation",
                "label": "风格领先轮动",
                "required": True,
                "reviewPoint": "复核风格领先变化是否保持相对强弱研究口径。",
            },
            {
                "key": "ai_capex_infrastructure",
                "label": "AI基建",
                "required": True,
                "reviewPoint": "复核AI资本开支和基础设施线索是否聚焦产业证据。",
            },
        ),
    },
    {
        "key": "policyAndMacro",
        "label": "政策与宏观",
        "region": "secondary",
        "density": "standard",
        "required": True,
        "reviewPoint": "复核政策、监管、宏观驱动链与情景线索是否放在宏观背景中观察。",
        "modules": (
            {
                "key": "policy_regulation_watch",
                "label": "政策监管观察",
                "required": True,
                "reviewPoint": "复核政策和监管事项是否保持中性研究语气。",
            },
            {
                "key": "scenario_watchlist",
                "label": "情景观察表",
                "required": True,
                "reviewPoint": "复核情景清单是否呈现待验证问题。",
            },
            {
                "key": "driver_chain",
                "label": "宏观驱动链",
                "required": True,
                "reviewPoint": "复核宏观驱动链是否保持研究口径。",
            },
        ),
    },
    {
        "key": "researchQueue",
        "label": "研究队列",
        "region": "main_right",
        "density": "standard",
        "required": True,
        "reviewPoint": "复核研究事项是否按开盘前待确认顺序排列。",
        "modules": (
            {
                "key": "research_priorities",
                "label": "研究优先级",
                "required": True,
                "reviewPoint": "复核研究优先级是否帮助安排后续证据复核。",
            },
            {
                "key": "pre_session_research_checklist",
                "label": "盘前研究清单",
                "required": True,
                "reviewPoint": "复核盘前清单是否保持问题驱动的研究流程。",
            },
        ),
    },
    {
        "key": "evidenceAndReadiness",
        "label": "证据与就绪度",
        "region": "utility",
        "density": "compact",
        "required": True,
        "reviewPoint": "复核证据质量是否作为阅读前后的公共校验层。",
        "modules": (
            {
                "key": "evidence_quality",
                "label": "证据质量",
                "required": True,
                "reviewPoint": "复核证据质量是否只展示公开状态和限制说明。",
            },
        ),
    },
)


class HomepageSectionLayoutService:
    """Build a bounded layout/order contract for homepage frontend UAT."""

    def build_layout(self, *, as_of: str | None = None) -> dict[str, Any]:
        sections = [self._build_section(index, item) for index, item in enumerate(_SECTION_BLUEPRINTS, start=1)]
        payload = HomepageSectionLayoutResponse(
            status="ready",
            asOf=self._safe_as_of(as_of),
            sections=sections,
            noAdviceDisclosure=NO_ADVICE_DISCLOSURE,
            dataQuality=HomepageSectionLayoutDataQuality(
                state="ready",
                label="布局合同已就绪",
                summary=TOP_LEVEL_DATA_QUALITY_SUMMARY,
            ),
        )
        return payload.to_dict()

    def _build_section(self, priority: int, item: dict[str, Any]) -> HomepageSectionLayoutItem:
        region = str(item["region"])
        density = str(item["density"])
        if region not in ALLOWED_REGIONS:
            raise ValueError(f"Unsupported homepage section region: {region}")
        if density not in ALLOWED_DENSITIES:
            raise ValueError(f"Unsupported homepage section density: {density}")
        modules = [self._build_module(index, module) for index, module in enumerate(item["modules"], start=1)]
        return HomepageSectionLayoutItem(
            key=str(item["key"]),
            label=str(item["label"]),
            priority=priority,
            region=region,
            density=density,
            required=bool(item["required"]),
            reviewPoint=str(item["reviewPoint"]),
            modules=modules,
        )

    def _build_module(self, priority: int, item: dict[str, Any]) -> HomepageSectionLayoutModule:
        return HomepageSectionLayoutModule(
            key=str(item["key"]),
            label=str(item["label"]),
            priority=priority,
            required=bool(item["required"]),
            reviewPoint=str(item["reviewPoint"]),
        )

    def _safe_as_of(self, as_of: str | None) -> str:
        text = str(as_of or "").strip()
        if text:
            return text
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
