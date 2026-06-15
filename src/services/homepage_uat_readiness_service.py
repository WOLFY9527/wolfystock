# -*- coding: utf-8 -*-
"""Standalone homepage UAT readiness checklist service.

The service builds a bounded public checklist only. It does not call live data,
inspect provider state, or expose runtime diagnostics.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from api.v1.schemas.homepage_uat_readiness import (
    HomepageUatReadinessCheck,
    HomepageUatReadinessDataQuality,
    HomepageUatReadinessModule,
    HomepageUatReadinessModuleSummary,
    HomepageUatReadinessResponse,
)


NO_ADVICE_DISCLOSURE = "本清单仅用于首页模块验收与公开观察边界复核，不作为个性化决策依据。"
SUMMARY_REVIEW = "首页 cockpit 验收可进入人工复核；模块仍需按静态、样本、代理与暂无证据边界展示。"
DATA_QUALITY_MESSAGE = "清单为静态合同，只描述验收边界、缺口类别与数据接入准备度。"
_STATUS_LABELS = {
    "pass": "通过",
    "review": "需人工复核",
    "blocked": "阻塞",
    "no_evidence": "暂无证据",
}
_BOUNDARY_LABELS = {
    "static_contract": "静态合同",
    "deterministic_sample": "确定性样本",
    "placeholder": "占位样本",
    "proxy_only": "仅代理观察",
    "proxy_no_evidence_mix": "代理与暂无证据混合",
    "sample_proxy": "样本代理",
}
_REVIEW_SCOPE = (
    "public_serialization",
    "public_copy_boundary",
    "display_state_labels",
    "missing_evidence_disclosure",
)
_UAT_CHECKLIST_ITEMS = (
    "confirm_public_fields_render",
    "confirm_boundary_labels_visible",
    "confirm_missing_evidence_copy",
    "record_uat_evidence",
)
_COMMON_MISSING_EVIDENCE = ("current_data_feed",)
_CHECK_BLUEPRINTS: tuple[dict[str, object], ...] = (
    {
        "key": "contract_shape",
        "label": "合同形状",
        "status": "pass",
        "publicMessage": "清单字段、状态枚举与模块列表已固定，可供页面验收读取。",
        "ownerArea": "contract",
        "required": True,
    },
    {
        "key": "cockpit_module_coverage",
        "label": "模块覆盖",
        "status": "pass",
        "publicMessage": "覆盖 T-1589 至 T-1608 的 20 个首页 cockpit 模块。",
        "ownerArea": "contract",
        "required": True,
    },
    {
        "key": "sample_proxy_boundary",
        "label": "样本与代理边界",
        "status": "pass",
        "publicMessage": "样本、代理与暂无证据状态在模块级保留，不被提升为当前数据。",
        "ownerArea": "data_quality",
        "required": True,
    },
    {
        "key": "public_copy_boundary",
        "label": "公开文案边界",
        "status": "pass",
        "publicMessage": "公开文案保持观察与验收口径，不作为个性化决策依据。",
        "ownerArea": "copy",
        "required": True,
    },
    {
        "key": "serialization_readiness",
        "label": "序列化准备度",
        "status": "pass",
        "publicMessage": "20 个模块均通过静态序列化合同复核。",
        "ownerArea": "contract",
        "required": True,
    },
    {
        "key": "public_display_readiness",
        "label": "公开展示准备度",
        "status": "review",
        "publicMessage": "UAT 可复核标题、状态、缺口提示与展示顺序；最终界面证据仍待记录。",
        "ownerArea": "frontend_ui",
        "required": True,
    },
    {
        "key": "data_integration_readiness",
        "label": "数据接入准备度",
        "status": "review",
        "publicMessage": "20 个模块均标记为未接入当前数据，只可按静态合同复核。",
        "ownerArea": "integration",
        "required": True,
    },
    {
        "key": "missing_evidence_categories",
        "label": "缺口类别",
        "status": "pass",
        "publicMessage": "每个模块列出缺口类别，便于 UAT 记录后续证据。",
        "ownerArea": "data_quality",
        "required": True,
    },
    {
        "key": "uat_checklist_items",
        "label": "验收清单项",
        "status": "review",
        "publicMessage": "每个模块给出统一验收项：字段展示、边界标签、缺口文案与证据记录。",
        "ownerArea": "qa",
        "required": True,
    },
    {
        "key": "qa_evidence_record",
        "label": "QA 证据记录",
        "status": "no_evidence",
        "publicMessage": "等待 UAT 人员补充页面截图、浏览器信息与验收结论。",
        "ownerArea": "qa",
        "required": True,
    },
)
_MODULE_BLUEPRINTS: tuple[dict[str, object], ...] = (
    {
        "taskId": "T-1589",
        "key": "daily_market_brief",
        "label": "每日市场简报",
        "evidenceBoundary": "static_contract",
        "missingEvidenceCategories": (
            "current_index_inputs",
            "current_breadth_inputs",
            "current_cross_asset_inputs",
        ),
    },
    {
        "taskId": "T-1590",
        "key": "risk_regime",
        "label": "风险状态与市场定价",
        "evidenceBoundary": "deterministic_sample",
        "missingEvidenceCategories": (
            "current_rates_confirmation",
            "current_volatility_confirmation",
            "current_defensive_demand_confirmation",
        ),
    },
    {
        "taskId": "T-1591",
        "key": "cross_asset_indicators",
        "label": "跨资产指标",
        "evidenceBoundary": "proxy_no_evidence_mix",
        "missingEvidenceCategories": (
            "rate_volatility_metric",
            "direct_credit_confirmation",
            "current_cross_asset_prices",
        ),
    },
    {
        "taskId": "T-1592",
        "key": "event_impact_map",
        "label": "事件影响地图",
        "evidenceBoundary": "placeholder",
        "missingEvidenceCategories": (
            "current_event_calendar",
            "verified_event_timing",
            "current_asset_reaction",
        ),
    },
    {
        "taskId": "T-1593",
        "key": "driver_chain",
        "label": "宏观驱动链",
        "evidenceBoundary": "static_contract",
        "missingEvidenceCategories": (
            "sustained_earnings_revision_support",
            "broader_growth_participation",
        ),
    },
    {
        "taskId": "T-1594",
        "key": "theme_capital_flow",
        "label": "主题资金代理",
        "evidenceBoundary": "proxy_only",
        "missingEvidenceCategories": (
            "authoritative_flow_evidence",
            "direct_flow_confirmation",
            "theme_breadth_confirmation",
        ),
    },
    {
        "taskId": "T-1595",
        "key": "research_priorities",
        "label": "研究优先级",
        "evidenceBoundary": "static_contract",
        "missingEvidenceCategories": (
            "confirmed_breadth_extension",
            "confirmed_volatility_context",
        ),
    },
    {
        "taskId": "T-1596",
        "key": "evidence_quality",
        "label": "证据质量投影",
        "evidenceBoundary": "proxy_no_evidence_mix",
        "missingEvidenceCategories": (
            "flow_confirmation_evidence",
            "current_section_freshness",
        ),
    },
    {
        "taskId": "T-1597",
        "key": "rates_pricing",
        "label": "利率定价观察",
        "evidenceBoundary": "proxy_only",
        "missingEvidenceCategories": (
            "fed_futures_curve",
            "ois_curve",
            "meeting_probability_distribution",
        ),
    },
    {
        "taskId": "T-1598",
        "key": "volatility_positioning",
        "label": "波动定位",
        "evidenceBoundary": "proxy_only",
        "missingEvidenceCategories": (
            "authoritative_option_chain",
            "positioning_evidence",
            "intraday_options_flow",
        ),
    },
    {
        "taskId": "T-1599",
        "key": "liquidity_credit",
        "label": "流动性与信用压力",
        "evidenceBoundary": "proxy_no_evidence_mix",
        "missingEvidenceCategories": (
            "direct_credit_spread",
            "funding_pressure_series",
            "treasury_market_depth",
        ),
    },
    {
        "taskId": "T-1600",
        "key": "market_breadth",
        "label": "市场广度参与",
        "evidenceBoundary": "proxy_no_evidence_mix",
        "missingEvidenceCategories": (
            "advance_decline_context",
            "small_cap_participation",
            "sector_participation_map",
        ),
    },
    {
        "taskId": "T-1601",
        "key": "after_close_developments",
        "label": "收盘后发展",
        "evidenceBoundary": "sample_proxy",
        "missingEvidenceCategories": (
            "actual_after_close_news",
            "actual_index_futures",
            "overnight_macro_calendar",
        ),
    },
    {
        "taskId": "T-1602",
        "key": "scenario_watchlist",
        "label": "情景观察清单",
        "evidenceBoundary": "static_contract",
        "missingEvidenceCategories": (
            "scenario_trigger_confirmation",
            "invalidating_signal_review",
        ),
    },
    {
        "taskId": "T-1603",
        "key": "earnings_catalysts",
        "label": "业绩催化",
        "evidenceBoundary": "sample_proxy",
        "missingEvidenceCategories": (
            "verified_company_calendar",
            "reported_figures",
            "transcript_excerpt",
            "market_reaction_measurement",
        ),
    },
    {
        "taskId": "T-1604",
        "key": "geopolitical_commodity_risk",
        "label": "地缘与商品风险",
        "evidenceBoundary": "sample_proxy",
        "missingEvidenceCategories": (
            "current_geopolitical_data",
            "current_commodity_data",
            "shipping_stress_confirmation",
        ),
    },
    {
        "taskId": "T-1605",
        "key": "ai_capex_infrastructure",
        "label": "AI 资本开支基础设施",
        "evidenceBoundary": "sample_proxy",
        "missingEvidenceCategories": (
            "actual_capex_figures",
            "current_capacity_data",
            "facility_timeline_evidence",
        ),
    },
    {
        "taskId": "T-1606",
        "key": "policy_regulation_watch",
        "label": "政策与监管观察",
        "evidenceBoundary": "sample_proxy",
        "missingEvidenceCategories": (
            "current_policy_calendar",
            "current_rule_text",
            "implementation_timeline",
        ),
    },
    {
        "taskId": "T-1607",
        "key": "style_leadership_rotation",
        "label": "风格领导轮动",
        "evidenceBoundary": "proxy_no_evidence_mix",
        "missingEvidenceCategories": (
            "value_style_breadth",
            "small_cap_breadth_series",
            "cyclical_participation",
        ),
    },
    {
        "taskId": "T-1608",
        "key": "pre_session_research_checklist",
        "label": "盘前研究清单",
        "evidenceBoundary": "static_contract",
        "missingEvidenceCategories": (
            "evidence_attachment_for_each_gate",
            "review_window_evidence",
        ),
    },
)


class HomepageUatReadinessService:
    """Build a deterministic, consumer-safe homepage UAT readiness checklist."""

    def build_checklist(self, *, as_of: str | None = None) -> dict[str, Any]:
        checks = [self._build_check(item) for item in _CHECK_BLUEPRINTS]
        modules = [self._build_module(item) for item in _MODULE_BLUEPRINTS]
        status = self._aggregate_status(checks)
        payload = HomepageUatReadinessResponse(
            status=status,
            asOf=self._safe_as_of(as_of),
            checks=checks,
            cockpitModules=modules,
            moduleSummary=self._build_module_summary(modules),
            summary=SUMMARY_REVIEW,
            noAdviceDisclosure=NO_ADVICE_DISCLOSURE,
            dataQuality=HomepageUatReadinessDataQuality(
                status=status,
                label=_STATUS_LABELS[status],
                publicMessage=DATA_QUALITY_MESSAGE,
            ),
        )
        return payload.model_dump(mode="json")

    def _build_check(self, item: dict[str, object]) -> HomepageUatReadinessCheck:
        return HomepageUatReadinessCheck(
            key=str(item["key"]),
            label=str(item["label"]),
            status=str(item["status"]),
            publicMessage=str(item["publicMessage"]),
            ownerArea=str(item["ownerArea"]),
            required=bool(item["required"]),
        )

    def _build_module(self, item: dict[str, object]) -> HomepageUatReadinessModule:
        missing = [*_COMMON_MISSING_EVIDENCE, *tuple(item["missingEvidenceCategories"])]
        evidence_boundary = str(item["evidenceBoundary"])
        return HomepageUatReadinessModule(
            taskId=str(item["taskId"]),
            key=str(item["key"]),
            label=str(item["label"]),
            uatReviewable=True,
            reviewScope=list(_REVIEW_SCOPE),
            evidenceBoundary=evidence_boundary,
            evidenceBoundaryLabel=_BOUNDARY_LABELS[evidence_boundary],
            serializationReadiness="ready",
            publicDisplayReadiness="review",
            dataIntegrationReadiness="not_wired_current_data",
            dataIntegrationLabel="未接入当前数据",
            missingEvidenceCategories=missing,
            uatChecklistItems=list(_UAT_CHECKLIST_ITEMS),
        )

    def _build_module_summary(
        self,
        modules: list[HomepageUatReadinessModule],
    ) -> HomepageUatReadinessModuleSummary:
        return HomepageUatReadinessModuleSummary(
            totalModules=len(modules),
            reviewableModules=sum(1 for module in modules if module.uatReviewable),
            notWiredDataModules=sum(
                1
                for module in modules
                if module.dataIntegrationReadiness == "not_wired_current_data"
            ),
            sampleProxyOrNoEvidenceModules=sum(
                1
                for module in modules
                if module.evidenceBoundary
                in {
                    "static_contract",
                    "deterministic_sample",
                    "placeholder",
                    "proxy_only",
                    "proxy_no_evidence_mix",
                    "sample_proxy",
                }
            ),
            publicMessage=(
                "20 个首页 cockpit 模块可做公开验收复核；所有模块仍停留在静态、样本、代理或暂无证据边界。"
            ),
        )

    def _aggregate_status(self, checks: list[HomepageUatReadinessCheck]) -> str:
        required_statuses = {check.status for check in checks if check.required}
        if "blocked" in required_statuses:
            return "blocked"
        if "review" in required_statuses:
            return "review"
        if "no_evidence" in required_statuses:
            return "review"
        return "pass"

    def _safe_as_of(self, as_of: str | None) -> str:
        text = str(as_of or "").strip()
        if text:
            return text
        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
