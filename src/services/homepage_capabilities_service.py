# -*- coding: utf-8 -*-
"""Pure service that emits a bounded homepage capabilities contract."""

from __future__ import annotations

from api.v1.schemas.homepage_capabilities import (
    HOMEPAGE_CAPABILITIES_CONTRACT_VERSION,
    HomepageCapabilitiesDataQuality,
    HomepageCapabilitiesSnapshot,
    HomepageCapabilitySection,
)


HOMEPAGE_CAPABILITIES_NO_ADVICE_DISCLOSURE = "首页能力信息仅供研究观察，不构成个性化建议。"
HOMEPAGE_EXISTING_CAPABILITY_FLAGS: tuple[str, ...] = (
    "marketPulse",
    "moneyFlowProxy",
    "eventRadar",
    "personalSummary",
    "researchQueue",
    "publicDataQuality",
    "sessionStatus",
    "eventWindows",
    "noAdviceBoundary",
)
HOMEPAGE_COCKPIT_MODULES: tuple[dict[str, str], ...] = (
    {
        "key": "dailyMarketBrief",
        "label": "每日市场简报",
        "category": "overview",
        "availability": "sample",
        "description": "展示每日市场简报样本，帮助观察盘面线索和研究背景。",
        "reviewPoint": "复核简报样本是否仍清楚标记为观察材料。",
    },
    {
        "key": "riskRegime",
        "label": "风险状态",
        "category": "overview",
        "availability": "proxy",
        "description": "展示风险偏好代理观察，提示仍需结合更多证据复核。",
        "reviewPoint": "复核风险状态仍以代理观察和证据边界表达。",
    },
    {
        "key": "crossAssetIndicators",
        "label": "跨资产指标",
        "category": "overview",
        "availability": "proxy",
        "description": "展示跨资产指标代理观察，用于研究支持和关系复核。",
        "reviewPoint": "复核跨资产关系仍作为研究支持，而非操作结论。",
    },
    {
        "key": "eventImpactMap",
        "label": "事件影响图",
        "category": "events",
        "availability": "sample",
        "description": "展示事件影响样本分组，用于观察可能影响路径。",
        "reviewPoint": "复核事件影响仍保留样本和情景边界。",
    },
    {
        "key": "driverChain",
        "label": "驱动链",
        "category": "research",
        "availability": "proxy",
        "description": "展示驱动链代理观察，帮助复核宏观到资产的研究假设。",
        "reviewPoint": "复核驱动链仍以研究假设和证据复核为主。",
    },
    {
        "key": "themeCapitalFlow",
        "label": "主题资金流",
        "category": "flow",
        "availability": "proxy",
        "description": "展示主题资金流代理观察，帮助复核扩散和收敛线索。",
        "reviewPoint": "复核主题资金流仍明确为代理观察。",
    },
    {
        "key": "researchPriorities",
        "label": "研究优先级",
        "category": "research",
        "availability": "no_evidence",
        "description": "展示研究优先级占位，当前缺少足够公开证据支撑排序。",
        "reviewPoint": "复核研究优先级仍标明暂无证据边界。",
    },
    {
        "key": "evidenceQuality",
        "label": "证据质量",
        "category": "quality",
        "availability": "sample",
        "description": "展示证据质量样本摘要，帮助复核各模块证据边界。",
        "reviewPoint": "复核证据质量摘要仍不暴露内部诊断。",
    },
    {
        "key": "ratesPricing",
        "label": "利率定价",
        "category": "overview",
        "availability": "proxy",
        "description": "展示利率定价代理观察，用于研究利率敏感性。",
        "reviewPoint": "复核利率定价仍以代理观察表达。",
    },
    {
        "key": "volatilityPositioning",
        "label": "波动定位",
        "category": "overview",
        "availability": "proxy",
        "description": "展示波动定位代理观察，用于复核风险偏好背景。",
        "reviewPoint": "复核波动定位仍避免操作性暗示。",
    },
    {
        "key": "liquidityCredit",
        "label": "流动性与信用",
        "category": "overview",
        "availability": "proxy",
        "description": "展示流动性信用代理观察，用于研究支持和复核。",
        "reviewPoint": "复核流动性信用仍标记为代理观察。",
    },
    {
        "key": "marketBreadth",
        "label": "市场广度",
        "category": "overview",
        "availability": "proxy",
        "description": "展示市场广度代理观察，用于复核扩散和集中度。",
        "reviewPoint": "复核市场广度仍以扩散观察为主。",
    },
    {
        "key": "afterCloseDevelopments",
        "label": "收盘后发展",
        "category": "events",
        "availability": "sample",
        "description": "展示收盘后发展样本清单，用于观察后续研究线索。",
        "reviewPoint": "复核收盘后发展仍清楚标记样本边界。",
    },
    {
        "key": "scenarioWatchlist",
        "label": "情景观察清单",
        "category": "research",
        "availability": "sample",
        "description": "展示情景观察样本清单，用于复核关键触发条件。",
        "reviewPoint": "复核情景观察仍作为研究清单表达。",
    },
    {
        "key": "earningsCatalysts",
        "label": "财报催化",
        "category": "events",
        "availability": "sample",
        "description": "展示财报催化样本清单，用于复核事件研究线索。",
        "reviewPoint": "复核财报催化仍以事件研究支持为主。",
    },
    {
        "key": "geopoliticalCommodityRisk",
        "label": "地缘与商品风险",
        "category": "events",
        "availability": "sample",
        "description": "展示地缘和商品风险样本清单，用于观察外部扰动。",
        "reviewPoint": "复核地缘和商品风险仍保留样本边界。",
    },
    {
        "key": "aiCapexInfrastructure",
        "label": "AI 资本开支基础设施",
        "category": "research",
        "availability": "sample",
        "description": "展示 AI 资本开支基础设施样本，用于复核主题研究线索。",
        "reviewPoint": "复核 AI 资本开支线索仍作为主题研究支持。",
    },
    {
        "key": "policyRegulationWatch",
        "label": "政策监管观察",
        "category": "events",
        "availability": "sample",
        "description": "展示政策监管观察样本，用于复核规则变化研究线索。",
        "reviewPoint": "复核政策监管观察仍聚焦研究复核。",
    },
    {
        "key": "styleLeadershipRotation",
        "label": "风格领先轮动",
        "category": "rotation",
        "availability": "sample",
        "description": "展示风格轮动样本观察，用于复核领先与滞后关系。",
        "reviewPoint": "复核风格轮动仍保留观察和样本边界。",
    },
    {
        "key": "preSessionResearchChecklist",
        "label": "盘前研究清单",
        "category": "research",
        "availability": "sample",
        "description": "展示开盘前研究清单样本，用于支持研究准备。",
        "reviewPoint": "复核盘前研究清单仍只提供研究准备支持。",
    },
)
_CAPABILITY_STATUS_BY_AVAILABILITY = {
    "sample": "partial",
    "proxy": "partial",
    "no_evidence": "no_evidence",
}
_DEFAULT_DATA_QUALITY = HomepageCapabilitiesDataQuality(
    status="partial",
    label="部分缺失",
    available=False,
    description="首页能力信息已整理，样本、代理观察与暂无证据边界已标记。",
)


class HomepageCapabilitiesService:
    """Emit static homepage capability metadata without route or provider details."""

    def build_snapshot(self) -> HomepageCapabilitiesSnapshot:
        return HomepageCapabilitiesSnapshot(
            schemaVersion=HOMEPAGE_CAPABILITIES_CONTRACT_VERSION,
            status="partial",
            sections=self._build_sections(),
            capabilities=self._build_capability_flags(),
            dataQuality=_DEFAULT_DATA_QUALITY,
            noAdviceDisclosure=HOMEPAGE_CAPABILITIES_NO_ADVICE_DISCLOSURE,
        )

    def _build_sections(self) -> list[HomepageCapabilitySection]:
        return [
            HomepageCapabilitySection(
                key=item["key"],
                label=item["label"],
                supported=True,
                status=_CAPABILITY_STATUS_BY_AVAILABILITY[item["availability"]],
                description=item["description"],
            )
            for item in HOMEPAGE_COCKPIT_MODULES
        ]

    def _build_capability_flags(self) -> dict[str, bool]:
        return {
            **{item["key"]: True for item in HOMEPAGE_COCKPIT_MODULES},
            **{key: True for key in HOMEPAGE_EXISTING_CAPABILITY_FLAGS},
        }


__all__ = [
    "HOMEPAGE_CAPABILITIES_CONTRACT_VERSION",
    "HOMEPAGE_CAPABILITIES_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_COCKPIT_MODULES",
    "HOMEPAGE_EXISTING_CAPABILITY_FLAGS",
    "HomepageCapabilitiesService",
]
