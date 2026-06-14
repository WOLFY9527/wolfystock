# -*- coding: utf-8 -*-
"""Consumer-safe homepage dashboard overview scaffold service."""

from __future__ import annotations

from datetime import UTC, datetime

from api.v1.schemas.dashboard_overview import DashboardMarketIntelligenceOverviewResponse


class DashboardOverviewService:
    """Build a bounded overview contract without provider/runtime side effects."""

    def get_market_intelligence_overview(self) -> dict[str, object]:
        payload = DashboardMarketIntelligenceOverviewResponse(
            status="ready",
            asOf=_now_iso(),
            marketPulse={
                "sp500": {"label": "S&P 500", "value": "震荡观察", "change": "+0.2%", "status": "ready"},
                "nasdaq": {"label": "Nasdaq", "value": "成长分化", "change": "+0.1%", "status": "ready"},
                "russell2000": {"label": "Russell 2000", "value": "小盘承压", "change": "-0.1%", "status": "ready"},
                "vix": {"label": "VIX", "value": "波动中性", "change": "-0.3", "status": "ready"},
                "tenYearYield": {"label": "10Y Yield", "value": "利率平稳", "change": "+1bp", "status": "ready"},
                "dollarIndex": {"label": "Dollar Index", "value": "美元偏稳", "change": "+0.1%", "status": "ready"},
                "marketBreadth": {"summary": "广度未形成单边扩散，适合继续观察。", "status": "ready"},
                "liquidityState": "流动性中性观察",
            },
            marketBrief={
                "headline": "市场状态以观察与复核为主",
                "summary": "当前首页概览聚焦市场状态、资金流、风险与研究优先级，不提供交易判断。",
                "status": "ready",
            },
            moneyFlow={
                "topInflows": ["高质量大型股", "防御现金流主题", "低波动宽基"],
                "topOutflows": ["高波动题材", "短线拥挤热点", "高杠杆风险偏好"],
                "styleBias": "均衡偏防御",
                "offensiveDefensiveBias": "中性偏防御",
                "sourceStatus": "ready",
                "status": "ready",
            },
            liquidityRisk={
                "summary": "流动性与风险偏好暂未出现一致性突破，优先跟踪波动与利率共振。",
                "volatilityTone": "平稳",
                "fundingStress": "可控",
                "dollarRatePressure": "中性",
                "status": "ready",
            },
            sectorThemeRotation={
                "leadingThemes": ["防御质量", "现金流稳定", "指数权重"],
                "laggingThemes": ["高波动题材", "拥挤主题追逐", "弱势扩散链条"],
                "diffusion": "分歧",
                "summary": "主题轮动仍处于分歧阶段，更适合做证据跟踪而非方向定性。",
                "status": "ready",
            },
            researchQueue={
                "status": "ready",
                "items": [
                    {
                        "title": "广度扩散复核",
                        "summary": "复核上涨家数与权重指数是否同步扩散。",
                        "action": "复核",
                        "priority": "high",
                    },
                    {
                        "title": "防御风格走强研究",
                        "summary": "研究防御风格走强是否伴随资金持续流入。",
                        "action": "研究",
                        "priority": "medium",
                    },
                    {
                        "title": "流动性分歧观察",
                        "summary": "观察利率、美元与波动率之间是否继续分歧。",
                        "action": "观察",
                        "priority": "medium",
                    },
                    {
                        "title": "题材收敛证据",
                        "summary": "证据不足时保持收敛判断，等待更清晰的扩散线索。",
                        "action": "证据",
                        "priority": "low",
                    },
                ],
            },
            dataQuality={
                "state": "ready",
                "label": "正常",
                "summary": "当前返回消费者安全合同 scaffold，字段稳定且无内部诊断暴露。",
                "sections": {
                    "marketPulse": "ready",
                    "marketBrief": "ready",
                    "moneyFlow": "ready",
                    "liquidityRisk": "ready",
                    "sectorThemeRotation": "ready",
                    "researchQueue": "ready",
                },
            },
            noAdviceDisclosure="本概览仅用于市场研究观察，不构成投资建议或交易指令。",
        )
        return payload.model_dump(mode="json")


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
