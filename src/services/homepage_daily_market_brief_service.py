# -*- coding: utf-8 -*-
"""Deterministic homepage daily market brief service.

The service is intentionally standalone: it does not call live providers,
network resources, auth/session state, dashboards, caches, or environment
secrets. It only emits a bounded public contract for homepage display wiring.
"""

from __future__ import annotations

from typing import Any

from api.v1.schemas.homepage_daily_market_brief import (
    DAILY_MARKET_BRIEF_SCHEMA_VERSION,
    DailyMarketBriefIndexSummary,
    HomepageDailyMarketBriefResponse,
)


DEFAULT_AS_OF = "2026-06-15T00:00:00Z"
NO_ADVICE_DISCLOSURE = "仅用于市场观察、证据整理与研究支持，不作为任何个性化决策或执行依据。"

_KEY_DRIVERS: tuple[str, ...] = (
    "指数线索需要结合市场广度与量能变化复核。",
    "流动性观察聚焦成交活跃度与资金参与连续性。",
    "波动线索提示短线情绪仍需用公开证据增强。",
    "跨资产线索关注利率、美元与风险偏好的同步变化。",
)
_INDEX_SUMMARY: tuple[dict[str, str], ...] = (
    {
        "label": "A股主要指数",
        "summary": "关注权重指数与成长方向是否同步改善，避免只看单一指数。",
    },
    {
        "label": "港股主要指数",
        "summary": "观察外部流动性、互联网权重与本地情绪是否形成一致线索。",
    },
    {
        "label": "美股主要指数",
        "summary": "观察科技权重、广度扩散与波动变化是否支撑风险偏好。",
    },
)
_WATCH_POINTS: tuple[str, ...] = (
    "今日重点观察指数表现与市场广度是否背离。",
    "今日重点观察成交活跃度是否支持持续研究。",
    "今日重点观察波动变化是否需要复核风险语气。",
    "今日重点观察跨资产线索是否出现新的证据增强。",
)


class HomepageDailyMarketBriefService:
    """Build a plain-language daily market brief for homepage consumers."""

    def build_daily_market_brief(self, *, as_of: str | None = None) -> dict[str, Any]:
        payload = HomepageDailyMarketBriefResponse(
            schemaVersion=DAILY_MARKET_BRIEF_SCHEMA_VERSION,
            asOf=self._safe_as_of(as_of),
            sessionLabel="今日重点观察",
            headline="市场观察聚焦广度、流动性与跨资产线索",
            marketNarrative=(
                "当前摘要以公开线索做证据整理，帮助投资者先理解市场结构，再决定是否继续研究。"
            ),
            keyDrivers=list(_KEY_DRIVERS),
            riskTone="市场观察",
            indexSummary=[DailyMarketBriefIndexSummary(**item) for item in _INDEX_SUMMARY],
            breadthSummary="广度摘要关注上涨参与率、主题扩散与分化程度，结论需要复核。",
            liquiditySummary="流动性摘要关注成交活跃度与资金参与连续性，当前用于研究支持。",
            volatilitySummary="波动摘要关注情绪变化与风险偏好切换，证据不足时保持克制表述。",
            ratesSummary="利率摘要关注期限变化对估值敏感资产的影响，需要结合公开证据复核。",
            dollarSummary="美元摘要关注汇率线索与跨境风险偏好变化，避免单一变量解释市场。",
            crossAssetSummary="跨资产摘要把指数、利率、美元与波动放在同一观察框架中做证据整理。",
            todayWatchPoints=list(_WATCH_POINTS),
            evidenceQuality="证据整理",
            dataQuality="研究支持",
            noAdviceDisclosure=NO_ADVICE_DISCLOSURE,
        )
        return payload.model_dump(mode="json")

    def _safe_as_of(self, as_of: str | None) -> str:
        text = str(as_of or "").strip()
        return text or DEFAULT_AS_OF


__all__ = [
    "DAILY_MARKET_BRIEF_SCHEMA_VERSION",
    "DEFAULT_AS_OF",
    "HomepageDailyMarketBriefService",
    "NO_ADVICE_DISCLOSURE",
]
