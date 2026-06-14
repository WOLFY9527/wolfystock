# -*- coding: utf-8 -*-
"""Consumer-safe homepage dashboard overview composition service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping

from api.v1.schemas.dashboard_overview import DashboardMarketIntelligenceOverviewResponse
from src.services.market_pulse_service import MarketPulseService
from src.services.money_flow_service import MoneyFlowService
from src.services.public_data_quality_service import build_public_data_quality_summary
from src.services.research_queue_service import ResearchQueueService
from src.services.sector_theme_strength_service import SectorThemeStrengthService


_DASHBOARD_STATES = {"ready", "delayed", "cached", "partial", "no_evidence", "unavailable"}
_OVERVIEW_STATUSES = {"ready", "partial", "no_evidence", "unavailable"}
_STATE_TO_PUBLIC = {
    "正常": "ready",
    "中性": "ready",
    "走强": "ready",
    "走弱": "ready",
    "观察": "partial",
    "复核": "partial",
    "适合研究观察": "ready",
    "暂无证据": "no_evidence",
    "暂不可用": "unavailable",
}
_RESEARCH_ACTION_BY_STATUS = {
    "high_attention": "复核",
    "review": "复核",
    "observe": "观察",
    "no_evidence": "暂无证据",
    "unavailable": "暂无证据",
}


class DashboardOverviewService:
    """Build the overview contract from inert standalone scaffold services."""

    def get_market_intelligence_overview(self) -> dict[str, object]:
        as_of = _now_iso()

        market_pulse = _as_dict(MarketPulseService().build_snapshot())
        money_flow = _as_dict(MoneyFlowService().build_homepage_money_flow_proxy())
        sector_theme = _as_dict(SectorThemeStrengthService().build_summary())
        research_queue = _as_dict(ResearchQueueService().build_queue())

        section_states = {
            "marketPulse": _overview_status(market_pulse.get("status")),
            "marketBrief": "ready",
            "moneyFlow": _overview_status(money_flow.get("status")),
            "liquidityRisk": "ready",
            "sectorThemeRotation": _overview_status(sector_theme.get("status")),
            "researchQueue": _overview_status(research_queue.get("status")),
        }
        public_quality = _as_dict(
            build_public_data_quality_summary(
                {
                    "status": "ready",
                    "updatedModules": ["home"],
                    "modules": section_states,
                }
            )
        )

        payload = DashboardMarketIntelligenceOverviewResponse(
            status=_combine_overview_status(section_states.values()),
            asOf=as_of,
            marketPulse=_project_market_pulse(market_pulse),
            marketBrief=_market_brief(),
            moneyFlow=_project_money_flow(money_flow),
            liquidityRisk=_liquidity_risk(market_pulse),
            sectorThemeRotation=_project_sector_theme_rotation(sector_theme),
            researchQueue=_project_research_queue(research_queue),
            dataQuality=_project_data_quality(public_quality, section_states),
            noAdviceDisclosure="本概览仅用于市场研究观察，不构成投资建议或交易指令。",
        )
        return payload.model_dump(mode="json")


def _project_market_pulse(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    indices = _list(snapshot.get("indices"))
    sp500 = _metric(indices[0] if len(indices) > 0 else None, fallback_label="S&P 500")
    nasdaq = _metric(indices[1] if len(indices) > 1 else None, fallback_label="Nasdaq")
    russell = _metric(indices[2] if len(indices) > 2 else None, fallback_label="Russell 2000")
    breadth = _metric(snapshot.get("breadth"), fallback_label="Market breadth")
    liquidity = _metric(snapshot.get("liquidity"), fallback_label="Liquidity state")

    return {
        "sp500": sp500,
        "nasdaq": nasdaq,
        "russell2000": russell,
        "vix": _metric(snapshot.get("volatility"), fallback_label="VIX"),
        "tenYearYield": _metric(snapshot.get("rates"), fallback_label="10Y Yield"),
        "dollarIndex": _metric(snapshot.get("dollar"), fallback_label="Dollar Index"),
        "marketBreadth": {
            "summary": _summary_from_metric(breadth, prefix="市场广度"),
            "status": breadth["status"],
        },
        "liquidityState": _metric_tone(liquidity, fallback="流动性暂无证据"),
    }


def _project_money_flow(proxy: Mapping[str, Any]) -> dict[str, Any]:
    data_quality = _as_dict(proxy.get("dataQuality"))
    top_inflows = [_text(item.get("name")) for item in _mapping_list(proxy.get("topInflows"))]
    top_outflows = [_text(item.get("name")) for item in _mapping_list(proxy.get("topOutflows"))]
    style_bias = _as_dict(proxy.get("styleBias"))
    offensive_defensive = _as_dict(proxy.get("offensiveDefensiveBias"))
    status = _overview_status(proxy.get("status"))

    return {
        "topInflows": [item for item in top_inflows if item],
        "topOutflows": [item for item in top_outflows if item],
        "styleBias": _text(style_bias.get("bias")) or "unknown",
        "offensiveDefensiveBias": _text(offensive_defensive.get("bias")) or "unknown",
        "sourceStatus": _dashboard_state(data_quality.get("state") or status),
        "status": status,
    }


def _project_sector_theme_rotation(summary: Mapping[str, Any]) -> dict[str, Any]:
    strongest = [_text(item.get("name")) for item in _mapping_list(summary.get("strongest"))]
    weakest = [_text(item.get("name")) for item in _mapping_list(summary.get("weakest"))]
    diffusion = _as_dict(summary.get("diffusion"))
    status = _overview_status(summary.get("status"))

    return {
        "leadingThemes": [item for item in strongest if item],
        "laggingThemes": [item for item in weakest if item],
        "diffusion": _text(diffusion.get("status")) or status,
        "summary": _text(diffusion.get("observation")) or "主题轮动暂无可复用证据，当前仅保留观察口径。",
        "status": status,
    }


def _project_research_queue(queue: Mapping[str, Any]) -> dict[str, Any]:
    items = []
    for item in _mapping_list(queue.get("items"))[:4]:
        items.append(
            {
                "title": _text(item.get("title")) or "研究观察",
                "summary": _text(item.get("reason")) or "当前仅保留研究观察，等待更多证据。",
                "action": _RESEARCH_ACTION_BY_STATUS.get(_text(item.get("status")), "观察"),
                "priority": _priority_label(item.get("priority")),
            }
        )
    return {
        "status": _overview_status(queue.get("status")),
        "items": items,
    }


def _project_data_quality(
    public_quality: Mapping[str, Any],
    section_states: Mapping[str, str],
) -> dict[str, Any]:
    state = _dashboard_state(public_quality.get("status"))
    return {
        "state": state,
        "label": _text(public_quality.get("label")) or "正常",
        "summary": _text(public_quality.get("message")) or "核心模块已更新，适合研究观察",
        "sections": {key: _dashboard_state(value) for key, value in section_states.items()},
    }


def _market_brief() -> dict[str, Any]:
    return {
        "headline": "市场状态以观察与复核为主",
        "summary": "当前首页概览组合市场脉冲、资金流代理、主题强弱、研究队列与公开数据质量合同，不提供交易判断。",
        "status": "ready",
    }


def _liquidity_risk(market_pulse: Mapping[str, Any]) -> dict[str, Any]:
    volatility = _metric(market_pulse.get("volatility"), fallback_label="VIX")
    rates = _metric(market_pulse.get("rates"), fallback_label="10Y Yield")
    dollar = _metric(market_pulse.get("dollar"), fallback_label="Dollar Index")
    return {
        "summary": "流动性与风险偏好以市场脉冲 scaffold 为观察依据，证据不足时保持收敛表述。",
        "volatilityTone": _metric_tone(volatility, fallback="暂无证据"),
        "fundingStress": _metric_tone(rates, fallback="暂无证据"),
        "dollarRatePressure": _metric_tone(dollar, fallback="暂无证据"),
        "status": _combine_overview_status([volatility["status"], rates["status"], dollar["status"]]),
    }


def _metric(value: Any, *, fallback_label: str) -> dict[str, str]:
    item = _as_dict(value)
    return {
        "label": _text(item.get("label")) or fallback_label,
        "value": _metric_value(item),
        "change": _metric_change(item.get("change")),
        "status": _metric_status(item),
    }


def _metric_value(item: Mapping[str, Any]) -> str:
    state = _text(item.get("state"))
    value = item.get("value")
    unit = _text(item.get("unit"))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:g} {unit}".strip()
    return state or "暂无证据"


def _metric_change(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value > 0:
            return f"+{value:g}"
        return f"{value:g}"
    return "暂无证据"


def _metric_status(item: Mapping[str, Any]) -> str:
    quality = _as_dict(item.get("dataQuality"))
    return _dashboard_state(quality.get("state") or item.get("state"))


def _summary_from_metric(metric: Mapping[str, str], *, prefix: str) -> str:
    if metric["status"] == "no_evidence":
        return f"{prefix}暂无证据，适合继续观察。"
    return f"{prefix}{metric['value']}，变化 {metric['change']}，适合研究观察。"


def _metric_tone(metric: Mapping[str, str], *, fallback: str) -> str:
    if metric["status"] == "no_evidence":
        return fallback
    return metric["value"]


def _combine_overview_status(statuses: Any) -> str:
    normalized = [_overview_status(value) for value in statuses]
    if not normalized:
        return "ready"
    if all(value == "ready" for value in normalized):
        return "ready"
    if all(value == "no_evidence" for value in normalized):
        return "no_evidence"
    if all(value == "unavailable" for value in normalized):
        return "unavailable"
    return "partial"


def _overview_status(value: Any) -> str:
    text = _text(value)
    if text in _OVERVIEW_STATUSES:
        return text
    if text == "delayed" or text == "cached":
        return "partial"
    return _STATE_TO_PUBLIC.get(text, "no_evidence")


def _dashboard_state(value: Any) -> str:
    text = _text(value)
    if text in _DASHBOARD_STATES:
        return text
    return _STATE_TO_PUBLIC.get(text, "no_evidence")


def _priority_label(value: Any) -> str:
    if isinstance(value, int):
        if value <= 1:
            return "high"
        if value <= 3:
            return "medium"
        return "low"
    return "medium"


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    return [item for item in _list(value) if isinstance(item, Mapping)]


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
