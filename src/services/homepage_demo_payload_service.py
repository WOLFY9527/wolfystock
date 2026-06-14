# -*- coding: utf-8 -*-
"""Deterministic homepage demo payload builder for UI/UAT fixtures only."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from api.v1.schemas.event_radar import EventRadarSourceStatus
from api.v1.schemas.research_queue import ResearchQueueBuildInputs
from src.services.event_radar_service import build_event_radar_snapshot
from src.services.market_pulse_service import MarketPulseService
from src.services.money_flow_service import MoneyFlowService
from src.services.personal_summary_service import PersonalSummaryService
from src.services.research_queue_service import ResearchQueueService


HAPPY_PATH = "happy_path"
DEGRADED_EXAMPLE = "degraded_example"
FIXED_AS_OF = "2026-06-14T09:30:00Z"
_FIXED_AS_OF_DT = datetime(2026, 6, 14, 9, 30, tzinfo=timezone.utc)
DEMO_DISCLOSURE = "首页演示样例，仅用于界面联调与 UAT，不代表真实数据。"
_DEMO_FLAGS = {"sampleData": True, "demoPayload": True}
_DATA_QUALITY_LABELS = {
    "ready": "正常",
    "partial": "部分缺失",
    "delayed": "数据延迟",
    "cached": "使用缓存",
    "no_evidence": "暂无证据",
    "unavailable": "暂不可用",
}


class HomepageDemoPayloadService:
    """Build bounded homepage demo fixtures without runtime/provider coupling."""

    def __init__(self) -> None:
        self._market_pulse_service = MarketPulseService()
        self._money_flow_service = MoneyFlowService()
        self._personal_summary_service = PersonalSummaryService()
        self._research_queue_service = ResearchQueueService()

    def build_payload(self, scenario: str = HAPPY_PATH) -> dict[str, Any]:
        if scenario == HAPPY_PATH:
            return deepcopy(self._build_happy_path())
        if scenario == DEGRADED_EXAMPLE:
            return deepcopy(self._build_degraded_example())
        raise ValueError(f"unsupported homepage demo scenario: {scenario}")

    def build_payloads(self) -> dict[str, dict[str, Any]]:
        return {
            HAPPY_PATH: self.build_payload(HAPPY_PATH),
            DEGRADED_EXAMPLE: self.build_payload(DEGRADED_EXAMPLE),
        }

    def _build_happy_path(self) -> dict[str, Any]:
        market_pulse = self._build_market_pulse_happy()
        money_flow = self._build_money_flow_happy()
        event_radar = self._build_event_radar_happy()
        personal_summary = self._build_personal_summary_happy()
        research_queue = self._build_research_queue_happy()
        section_states = {
            "marketPulse": "ready",
            "moneyFlow": "ready",
            "eventRadar": "ready",
            "personalSummary": "ready",
            "researchQueue": "ready",
        }
        return {
            "status": "ready",
            "scenario": HAPPY_PATH,
            "asOf": FIXED_AS_OF,
            "sampleData": True,
            "demoPayload": True,
            "headline": "首页 happy-path 演示样例",
            "summary": "固定 happy-path 样例，展示正常联调路径。",
            "marketPulse": market_pulse,
            "moneyFlow": money_flow,
            "eventRadar": event_radar,
            "personalSummary": personal_summary,
            "researchQueue": research_queue,
            "dataQuality": self._build_overall_data_quality(
                status="ready",
                summary="固定 happy-path 样例，字段稳定，适合界面联调。",
                sections=section_states,
            ),
            "demoDisclosure": DEMO_DISCLOSURE,
        }

    def _build_degraded_example(self) -> dict[str, Any]:
        market_pulse = self._build_market_pulse_degraded()
        money_flow = self._build_money_flow_degraded()
        event_radar = self._build_event_radar_degraded()
        personal_summary = self._build_personal_summary_degraded()
        research_queue = self._build_research_queue_degraded()
        section_states = {
            "marketPulse": "delayed",
            "moneyFlow": "partial",
            "eventRadar": "delayed",
            "personalSummary": "partial",
            "researchQueue": "partial",
        }
        return {
            "status": "partial",
            "scenario": DEGRADED_EXAMPLE,
            "asOf": FIXED_AS_OF,
            "sampleData": True,
            "demoPayload": True,
            "headline": "首页异常态演示样例",
            "summary": "固定异常样例，刻意保留延迟与缺失状态，供 UAT 展示。",
            "marketPulse": market_pulse,
            "moneyFlow": money_flow,
            "eventRadar": event_radar,
            "personalSummary": personal_summary,
            "researchQueue": research_queue,
            "dataQuality": self._build_overall_data_quality(
                status="delayed",
                summary="固定异常样例，刻意展示延迟与缺失状态，不对应真实运行告警。",
                sections=section_states,
            ),
            "demoDisclosure": DEMO_DISCLOSURE,
        }

    def _build_market_pulse_happy(self) -> dict[str, Any]:
        payload = self._market_pulse_service.build_snapshot(
            {
                "asOf": FIXED_AS_OF,
                "sp500": {"value": 5318.2, "change": 18.4, "state": "正常", "interpretation": "适合研究观察"},
                "nasdaq": {"value": 18942.6, "change": 42.3, "state": "走强", "interpretation": "适合研究观察"},
                "russell2000": {"value": 2116.5, "change": 4.6, "state": "中性", "interpretation": "观察"},
                "vix": {"value": 13.2, "change": -0.4, "state": "中性", "interpretation": "观察"},
                "tenYearYield": {"value": 4.28, "change": -0.02, "state": "中性", "interpretation": "观察"},
                "dollarIndex": {"value": 104.1, "change": -0.1, "state": "中性", "interpretation": "观察"},
                "marketBreadth": {"value": 57.0, "change": 1.8, "state": "正常", "interpretation": "适合研究观察"},
                "liquidityState": {"state": "正常", "interpretation": "适合研究观察"},
            }
        ).model_dump(mode="json")
        payload["noAdviceDisclosure"] = DEMO_DISCLOSURE
        self._mark_market_pulse_payload(payload)
        return payload

    def _build_market_pulse_degraded(self) -> dict[str, Any]:
        payload = self._market_pulse_service.build_snapshot(
            {
                "asOf": FIXED_AS_OF,
                "sp500": {"value": 5301.0, "change": -6.1, "state": "观察", "interpretation": "观察"},
                "nasdaq": {"state": "暂无证据", "interpretation": "暂无证据"},
                "russell2000": {"value": 2104.2, "change": -8.4, "state": "复核", "interpretation": "复核"},
                "vix": {"value": 15.8, "change": 0.9, "state": "观察", "interpretation": "观察", "dataQuality": "观察"},
                "tenYearYield": {"value": 4.36, "change": 0.04, "state": "复核", "interpretation": "复核"},
                "dollarIndex": {"value": 104.5, "change": 0.3, "state": "观察", "interpretation": "观察"},
                "marketBreadth": {"state": "暂无证据", "interpretation": "暂无证据"},
                "liquidityState": {"state": "观察", "interpretation": "观察"},
            }
        ).model_dump(mode="json")
        payload["noAdviceDisclosure"] = DEMO_DISCLOSURE
        self._mark_market_pulse_payload(payload)
        return payload

    def _build_money_flow_happy(self) -> dict[str, Any]:
        payload = self._money_flow_service.build_homepage_money_flow_proxy(
            as_of=FIXED_AS_OF,
            top_inflows=[
                {
                    "name": "半导体链",
                    "category": "theme",
                    "strength": "strong",
                    "breadth": "broadening",
                    "relativeMove": "strengthening",
                    "interpretation": "半导体样例观察线索保持稳定。",
                    "dataQuality": "ready",
                },
                {
                    "name": "高质量龙头",
                    "category": "style",
                    "strength": "moderate",
                    "breadth": "broadening",
                    "relativeMove": "strengthening",
                    "interpretation": "高质量样例线索延续，适合继续观察。",
                    "dataQuality": "ready",
                },
            ],
            top_outflows=[
                {
                    "name": "高波动题材",
                    "category": "theme",
                    "strength": "moderate",
                    "breadth": "converging",
                    "relativeMove": "weakening",
                    "interpretation": "高波动样例线索趋于收敛。",
                    "dataQuality": "ready",
                }
            ],
            style_bias={
                "bias": "growth",
                "interpretation": "成长风格样例观察线索略强。",
                "dataQuality": "ready",
            },
            offensive_defensive_bias={
                "bias": "balanced",
                "interpretation": "进攻与防守样例线索保持均衡。",
                "dataQuality": "ready",
            },
            interpretation="资金流样例线索已整理为固定联调载荷。",
        )
        payload["sourceStatus"] = {
            "status": "ready",
            "summary": "固定 happy-path 演示样例，字段仅用于界面联调。",
        }
        payload["noAdviceDisclosure"] = DEMO_DISCLOSURE
        self._mark_money_flow_payload(payload)
        return payload

    def _build_money_flow_degraded(self) -> dict[str, Any]:
        payload = self._money_flow_service.build_homepage_money_flow_proxy(
            as_of=FIXED_AS_OF,
            top_inflows=[
                {
                    "name": "防御现金流",
                    "category": "sector",
                    "strength": "moderate",
                    "breadth": "mixed",
                    "relativeMove": "flat",
                    "interpretation": "防御样例线索仍可观察，但延续性不足。",
                    "dataQuality": "partial",
                }
            ],
            top_outflows=[],
            style_bias={
                "bias": "value",
                "interpretation": "价值风格样例线索保留观察位。",
                "dataQuality": "partial",
            },
            offensive_defensive_bias=None,
            interpretation="固定异常样例仅展示部分缺失的资金流代理状态。",
        )
        payload["sourceStatus"] = {
            "status": "partial",
            "summary": "固定 demo 异常样例，刻意展示部分缺失状态。",
        }
        payload["noAdviceDisclosure"] = DEMO_DISCLOSURE
        self._mark_money_flow_payload(payload)
        return payload

    def _build_event_radar_happy(self) -> dict[str, Any]:
        payload = build_event_radar_snapshot(
            items=[
                {
                    "id": "evt-demo-macro-001",
                    "title": "CPI 窗口进入样例复核时段",
                    "category": "macro",
                    "impactStatus": "review",
                    "impactDirection": "mixed",
                    "affectedSectors": ["software", "semiconductors"],
                    "affectedThemes": ["rate_sensitivity", "leadership_shift"],
                    "relatedSymbols": ["QQQ", "SMH", "AAPL"],
                    "relatedMarketSignals": ["rates", "sector_rotation", "watchlist"],
                    "reviewModules": ["macro_context", "home_overview"],
                    "sourceStatus": EventRadarSourceStatus.READY,
                    "freshness": "fresh",
                    "summary": "宏观样例事件已整理为固定观察项。",
                    "noAdviceDisclosure": DEMO_DISCLOSURE,
                },
                {
                    "id": "evt-demo-earnings-001",
                    "title": "重点财报周样例进入观察窗口",
                    "category": "earnings",
                    "impactStatus": "high_attention",
                    "impactDirection": "mixed",
                    "affectedSectors": ["internet"],
                    "affectedThemes": ["earnings_cluster"],
                    "relatedSymbols": ["AMZN", "GOOGL"],
                    "relatedMarketSignals": ["earnings", "portfolio"],
                    "reviewModules": ["earnings_calendar", "portfolio_context"],
                    "sourceStatus": EventRadarSourceStatus.READY,
                    "freshness": "fresh",
                    "summary": "财报样例事件用于展示高关注复核路径。",
                    "noAdviceDisclosure": DEMO_DISCLOSURE,
                },
            ],
            as_of=_FIXED_AS_OF_DT,
            source_status=EventRadarSourceStatus.READY,
        ).model_dump(mode="json")
        payload.pop("schemaVersion", None)
        payload["asOf"] = FIXED_AS_OF
        payload["summary"] = "固定事件样例，展示正常联调路径。"
        payload["noAdviceDisclosure"] = DEMO_DISCLOSURE
        for item in payload["items"]:
            item["noAdviceDisclosure"] = DEMO_DISCLOSURE
        self._mark_event_radar_payload(payload)
        return payload

    def _build_event_radar_degraded(self) -> dict[str, Any]:
        payload = build_event_radar_snapshot(
            items=[
                {
                    "id": "evt-demo-watchlist-001",
                    "title": "观察名单样例事件存在延迟复核",
                    "category": "watchlist",
                    "impactStatus": "review",
                    "impactDirection": "negative",
                    "affectedSectors": ["software"],
                    "affectedThemes": ["delivery_delay"],
                    "relatedSymbols": ["TSLA", "MSFT"],
                    "relatedMarketSignals": ["watchlist", "breadth"],
                    "reviewModules": ["watchlist_context", "risk_review"],
                    "sourceStatus": EventRadarSourceStatus.READY,
                    "freshness": "delayed",
                    "summary": "固定异常样例用于展示延迟事件条目。",
                    "noAdviceDisclosure": DEMO_DISCLOSURE,
                }
            ],
            as_of=_FIXED_AS_OF_DT,
            source_status=EventRadarSourceStatus.READY,
        ).model_dump(mode="json")
        payload.pop("schemaVersion", None)
        payload["asOf"] = FIXED_AS_OF
        payload["freshness"] = "delayed"
        payload["summary"] = "固定异常事件样例，刻意展示延迟与待复核状态。"
        payload["noAdviceDisclosure"] = DEMO_DISCLOSURE
        for item in payload["items"]:
            item["noAdviceDisclosure"] = DEMO_DISCLOSURE
        self._mark_event_radar_payload(payload)
        return payload

    def _build_personal_summary_happy(self) -> dict[str, Any]:
        payload = self._personal_summary_service.build_summary(
            portfolio_snapshot={
                "total_equity": 580000.0,
                "daily_change": 2300.0,
                "cash_percent": 18.4,
                "largest_exposure": 16.2,
                "beta": 0.94,
                "risk_score": 38.0,
                "risk_status": "normal",
                "concentration_status": "normal",
                "sampleData": True,
            },
            watchlist_items=[
                {
                    "symbol": "AAPL",
                    "displayName": "Apple",
                    "symbolStatus": "normal",
                    "movementStatus": "normal",
                    "relativeStrengthStatus": "normal",
                    "volumeStatus": "normal",
                    "evidenceStatus": "normal",
                    "researchStatus": "normal",
                },
                {
                    "symbol": "MSFT",
                    "displayName": "Microsoft",
                    "symbolStatus": "normal",
                    "movementStatus": "normal",
                    "relativeStrengthStatus": "normal",
                    "volumeStatus": "normal",
                    "evidenceStatus": "normal",
                    "researchStatus": "normal",
                },
            ],
            portfolio_connected=True,
            sample_data=True,
            portfolio_status="ready",
            watchlist_status="ready",
        ).model_dump(mode="json")
        payload["watchlistExceptions"] = {
            "status": "ready",
            "items": [],
            "staleCount": 0,
            "noEvidenceCount": 0,
        }
        payload["reviewQueue"] = {"status": "ready", "items": []}
        payload["noAdviceDisclosure"] = DEMO_DISCLOSURE
        self._mark_personal_summary_payload(payload)
        return payload

    def _build_personal_summary_degraded(self) -> dict[str, Any]:
        payload = self._personal_summary_service.build_summary(
            portfolio_snapshot={
                "total_equity": 580000.0,
                "daily_change": -3200.0,
                "cash_percent": 27.0,
                "largest_exposure": 24.5,
                "beta": 1.08,
                "risk_score": 52.0,
                "risk_status": "observe",
                "concentration_status": "review",
                "sampleData": True,
            },
            watchlist_items=[
                {
                    "symbol": "TSLA",
                    "displayName": "Tesla",
                    "symbolStatus": "review",
                    "movementStatus": "weaker",
                    "relativeStrengthStatus": "weaker",
                    "volumeStatus": "normal",
                    "evidenceStatus": "stale",
                    "researchStatus": "review",
                    "reviewReason": "样例证据需要二次复核。",
                },
                {
                    "symbol": "NVDA",
                    "displayName": "NVIDIA",
                    "symbolStatus": "normal",
                    "movementStatus": "normal",
                    "relativeStrengthStatus": "normal",
                    "volumeStatus": "normal",
                    "evidenceStatus": "no_evidence",
                    "researchStatus": "no_evidence",
                    "reviewReason": "样例资料仍待补齐。",
                },
            ],
            portfolio_connected=True,
            sample_data=True,
            portfolio_status="partial",
            watchlist_status="partial",
        ).model_dump(mode="json")
        payload["noAdviceDisclosure"] = DEMO_DISCLOSURE
        self._mark_personal_summary_payload(payload)
        return payload

    def _build_research_queue_happy(self) -> dict[str, Any]:
        payload = self._research_queue_service.build_queue(
            ResearchQueueBuildInputs(
                asOf=FIXED_AS_OF,
                market=[
                    {
                        "title": "广度样例复核",
                        "reason": "固定样例用于展示市场广度复核入口。",
                        "status": "review",
                        "evidenceStatus": "available",
                        "relatedSymbols": ["000300.SH"],
                        "relatedThemes": ["宽基"],
                    }
                ],
                moneyFlow=[
                    {
                        "title": "资金流样例观察",
                        "reason": "固定样例用于展示资金流延续性观察。",
                        "status": "observe",
                        "evidenceStatus": "available",
                        "relatedSymbols": ["SMH"],
                        "relatedThemes": ["半导体"],
                    }
                ],
                research=[
                    {
                        "title": "研究样例整理",
                        "reason": "固定样例用于展示后续研究排队。",
                        "status": "observe",
                        "evidenceStatus": "available",
                        "relatedSymbols": ["AAPL"],
                        "relatedThemes": ["质量龙头"],
                    }
                ],
            )
        ).model_dump(mode="json")
        payload["noAdviceDisclosure"] = DEMO_DISCLOSURE
        payload["dataQuality"]["summary"] = "研究队列样例已生成，字段固定且稳定。"
        for item in payload["items"]:
            item["noAdviceDisclosure"] = DEMO_DISCLOSURE
        self._mark_research_queue_payload(payload)
        return payload

    def _build_research_queue_degraded(self) -> dict[str, Any]:
        payload = self._research_queue_service.build_queue(
            ResearchQueueBuildInputs(
                asOf=FIXED_AS_OF,
                event=[
                    {
                        "title": "事件样例资料补齐",
                        "reason": "固定异常样例用于展示资料缺口。",
                        "status": "review",
                        "evidenceStatus": "no_evidence",
                        "relatedSymbols": ["TSLA"],
                        "relatedThemes": ["事件缺口"],
                    }
                ],
                dataQuality=[
                    {
                        "title": "异常态样例复核",
                        "reason": "固定异常样例用于展示延迟与缺失混合状态。",
                        "status": "observe",
                        "evidenceStatus": "partial",
                        "relatedThemes": ["数据质量"],
                    }
                ],
            )
        ).model_dump(mode="json")
        payload["noAdviceDisclosure"] = DEMO_DISCLOSURE
        payload["dataQuality"]["summary"] = "研究队列异常样例已生成，刻意保留部分缺失状态。"
        for item in payload["items"]:
            item["noAdviceDisclosure"] = DEMO_DISCLOSURE
        self._mark_research_queue_payload(payload)
        return payload

    def _build_overall_data_quality(
        self,
        *,
        status: str,
        summary: str,
        sections: dict[str, str],
    ) -> dict[str, Any]:
        return {
            "status": status,
            "label": _DATA_QUALITY_LABELS[status],
            "summary": summary,
            "sections": dict(sections),
            "sampleData": True,
            "demoPayload": True,
        }

    def _mark_demo_mapping(self, payload: dict[str, Any]) -> None:
        payload.update(_DEMO_FLAGS)

    def _mark_demo_sequence(self, items: list[Any]) -> None:
        for item in items:
            if isinstance(item, dict):
                self._mark_demo_mapping(item)

    def _mark_market_pulse_payload(self, payload: dict[str, Any]) -> None:
        self._mark_demo_mapping(payload)
        self._mark_demo_sequence(payload.get("indices", []))
        for item in payload.get("indices", []):
            if isinstance(item, dict) and isinstance(item.get("dataQuality"), dict):
                self._mark_demo_mapping(item["dataQuality"])
        for key in ("volatility", "rates", "dollar", "breadth", "liquidity", "dataQuality"):
            value = payload.get(key)
            if isinstance(value, dict):
                self._mark_demo_mapping(value)
                if isinstance(value.get("dataQuality"), dict):
                    self._mark_demo_mapping(value["dataQuality"])

    def _mark_money_flow_payload(self, payload: dict[str, Any]) -> None:
        self._mark_demo_mapping(payload)
        self._mark_demo_sequence(payload.get("topInflows", []))
        self._mark_demo_sequence(payload.get("topOutflows", []))
        for key in ("styleBias", "offensiveDefensiveBias", "sourceStatus", "dataQuality"):
            value = payload.get(key)
            if isinstance(value, dict):
                self._mark_demo_mapping(value)
                if isinstance(value.get("dataQuality"), dict):
                    self._mark_demo_mapping(value["dataQuality"])

    def _mark_event_radar_payload(self, payload: dict[str, Any]) -> None:
        self._mark_demo_mapping(payload)
        self._mark_demo_sequence(payload.get("items", []))

    def _mark_personal_summary_payload(self, payload: dict[str, Any]) -> None:
        self._mark_demo_mapping(payload)
        for key in (
            "portfolioSnapshot",
            "watchlistExceptions",
            "researchCoverage",
            "reviewQueue",
            "dataQuality",
        ):
            value = payload.get(key)
            if isinstance(value, dict):
                self._mark_demo_mapping(value)
        watchlist_exceptions = payload.get("watchlistExceptions")
        if isinstance(watchlist_exceptions, dict):
            self._mark_demo_sequence(watchlist_exceptions.get("items", []))
        review_queue = payload.get("reviewQueue")
        if isinstance(review_queue, dict):
            self._mark_demo_sequence(review_queue.get("items", []))

    def _mark_research_queue_payload(self, payload: dict[str, Any]) -> None:
        self._mark_demo_mapping(payload)
        self._mark_demo_sequence(payload.get("items", []))
        data_quality = payload.get("dataQuality")
        if isinstance(data_quality, dict):
            self._mark_demo_mapping(data_quality)
