# -*- coding: utf-8 -*-
"""Standalone homepage section layout contract service.

This service is intentionally inert. It only exposes a bounded layout/order
contract for frontend UAT and does not wire routes, fetch data, or change
homepage runtime behavior.
"""

from __future__ import annotations

import time
from typing import Any


NO_ADVICE_DISCLOSURE = "仅用于首页区块布局验收参考，不构成投资建议或交易指令。"
TOP_LEVEL_DATA_QUALITY_SUMMARY = "当前合同仅描述首页区块顺序、密度与复核点，不包含实时行情、交易建议或内部诊断。"
ALLOWED_REGIONS = {"top_strip", "main_left", "main_center", "main_right", "secondary", "utility"}
ALLOWED_DENSITIES = {"compact", "standard", "expanded"}

_SECTION_BLUEPRINTS: tuple[dict[str, Any], ...] = (
    {
        "key": "market_pulse",
        "label": "市场脉搏",
        "region": "top_strip",
        "density": "compact",
        "required": True,
        "reviewPoint": "复核市场总览区块是否保持页面顶部的快速观察定位。",
    },
    {
        "key": "market_brief",
        "label": "市场简报",
        "region": "main_center",
        "density": "standard",
        "required": True,
        "reviewPoint": "复核简报区块是否承接主要阅读流，并保持研究观察口径。",
    },
    {
        "key": "money_flow",
        "label": "资金流向",
        "region": "main_left",
        "density": "standard",
        "required": True,
        "reviewPoint": "复核资金流向区块是否用于强弱观察，不延伸为操作动作。",
    },
    {
        "key": "research_queue",
        "label": "研究队列",
        "region": "main_right",
        "density": "standard",
        "required": True,
        "reviewPoint": "复核研究队列是否保持待复核事项列表，不表达交易指令。",
    },
    {
        "key": "event_radar",
        "label": "事件雷达",
        "region": "secondary",
        "density": "standard",
        "required": True,
        "reviewPoint": "复核事件雷达是否用于时间窗口观察，并保持公共标签。",
    },
    {
        "key": "sector_theme_strength",
        "label": "板块主题强弱",
        "region": "secondary",
        "density": "expanded",
        "required": True,
        "reviewPoint": "复核主题强弱区块是否呈现扩散与收敛，不输出方向性指令。",
    },
    {
        "key": "portfolio_watchlist",
        "label": "组合关注清单",
        "region": "secondary",
        "density": "standard",
        "required": False,
        "reviewPoint": "复核关注清单是否保持观察与复盘语义，并兼容未登录状态。",
    },
    {
        "key": "data_quality",
        "label": "数据质量",
        "region": "utility",
        "density": "compact",
        "required": True,
        "reviewPoint": "复核数据质量区块是否只展示公开状态与简洁说明。",
    },
    {
        "key": "homepage_intelligence",
        "label": "首页智能摘要",
        "region": "utility",
        "density": "compact",
        "required": False,
        "reviewPoint": "复核智能摘要是否仅作为辅助观察内容，不替代人工判断。",
    },
)


class HomepageSectionLayoutService:
    """Build a bounded layout/order contract for homepage frontend UAT."""

    def build_layout(self, *, as_of: str | None = None) -> dict[str, Any]:
        sections = [self._build_section(index, item) for index, item in enumerate(_SECTION_BLUEPRINTS, start=1)]
        return {
            "status": "ready",
            "asOf": self._safe_as_of(as_of),
            "sections": sections,
            "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
            "dataQuality": {
                "state": "ready",
                "label": "布局合同已就绪",
                "summary": TOP_LEVEL_DATA_QUALITY_SUMMARY,
            },
        }

    def _build_section(self, priority: int, item: dict[str, Any]) -> dict[str, Any]:
        region = str(item["region"])
        density = str(item["density"])
        if region not in ALLOWED_REGIONS:
            raise ValueError(f"Unsupported homepage section region: {region}")
        if density not in ALLOWED_DENSITIES:
            raise ValueError(f"Unsupported homepage section density: {density}")
        return {
            "key": str(item["key"]),
            "label": str(item["label"]),
            "priority": priority,
            "region": region,
            "density": density,
            "required": bool(item["required"]),
            "reviewPoint": str(item["reviewPoint"]),
        }

    def _safe_as_of(self, as_of: str | None) -> str:
        text = str(as_of or "").strip()
        if text:
            return text
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
