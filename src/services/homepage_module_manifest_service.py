# -*- coding: utf-8 -*-
"""Standalone homepage module manifest service.

This service is intentionally inert. It only exposes a bounded manifest for
homepage intelligence modules and does not launch modules, fetch providers, or
change existing dashboard/runtime behavior.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from api.v1.schemas.homepage_module_manifest import (
    HomepageModuleDataQuality,
    HomepageModuleManifestItem,
    HomepageModuleManifestResponse,
)


NO_ADVICE_DISCLOSURE = "仅供模块可用性与接入准备度观察，不构成个性化投资建议。"
TOP_LEVEL_DATA_QUALITY_SUMMARY = "当前模块 manifest 仅描述公开状态、接入状态与复核点，不包含操作性结论。"
_DATA_QUALITY_LABELS = {
    "ready": "正常",
    "partial": "部分缺失",
    "no_evidence": "暂无证据",
    "unavailable": "暂不可用",
}
_MODULE_BLUEPRINTS: tuple[dict[str, str], ...] = (
    {
        "key": "market_pulse",
        "label": "市场脉搏",
        "category": "overview",
        "availability": "ready",
        "integrationStatus": "standalone",
        "publicStatus": "public",
        "reviewPoint": "复核市场广度、波动与流动性是否仍保持观察口径。",
    },
    {
        "key": "money_flow",
        "label": "资金流向代理",
        "category": "flow",
        "availability": "ready",
        "integrationStatus": "standalone",
        "publicStatus": "public",
        "reviewPoint": "复核资金流向代理文案是否仍明确为观察型代理。",
    },
    {
        "key": "sector_theme_strength",
        "label": "板块主题强弱",
        "category": "rotation",
        "availability": "ready",
        "integrationStatus": "standalone",
        "publicStatus": "public",
        "reviewPoint": "复核主题强弱表述是否仍以扩散与收敛观察为主。",
    },
    {
        "key": "event_radar",
        "label": "事件雷达",
        "category": "events",
        "availability": "ready",
        "integrationStatus": "standalone",
        "publicStatus": "public",
        "reviewPoint": "复核事件分组与观察标签是否仍保持消费者安全表述。",
    },
    {
        "key": "personal_summary",
        "label": "个人摘要",
        "category": "personal",
        "availability": "ready",
        "integrationStatus": "standalone",
        "publicStatus": "gated",
        "reviewPoint": "复核个性化摘要仍保持账户隔离与非建议表达。",
    },
    {
        "key": "research_queue",
        "label": "研究队列",
        "category": "research",
        "availability": "ready",
        "integrationStatus": "standalone",
        "publicStatus": "public",
        "reviewPoint": "复核研究优先级条目仍聚焦复核与观察，不延伸为操作动作。",
    },
    {
        "key": "public_data_quality",
        "label": "公开数据质量",
        "category": "quality",
        "availability": "ready",
        "integrationStatus": "standalone",
        "publicStatus": "public",
        "reviewPoint": "复核公开数据质量摘要仍只暴露有限状态与简洁说明。",
    },
    {
        "key": "dashboard_overview",
        "label": "总览看板",
        "category": "overview",
        "availability": "ready",
        "integrationStatus": "wired",
        "publicStatus": "public",
        "reviewPoint": "复核总览聚合层仍只消费安全字段，并保持聚合展示边界。",
    },
)


class HomepageModuleManifestService:
    """Build a bounded manifest for homepage intelligence modules."""

    def build_manifest(self, *, as_of: str | None = None) -> dict[str, Any]:
        modules = [self._build_module(item) for item in _MODULE_BLUEPRINTS]
        status = self._aggregate_status(modules)
        payload = HomepageModuleManifestResponse(
            status=status,
            asOf=self._safe_as_of(as_of),
            modules=modules,
            dataQuality=self._data_quality(
                state=status,
                summary=TOP_LEVEL_DATA_QUALITY_SUMMARY,
            ),
            noAdviceDisclosure=NO_ADVICE_DISCLOSURE,
        )
        return payload.model_dump(mode="json")

    def _build_module(self, item: dict[str, str]) -> HomepageModuleManifestItem:
        availability = str(item["availability"])
        quality_state = "ready" if availability == "ready" else "partial" if availability == "scaffold" else availability
        return HomepageModuleManifestItem(
            key=item["key"],
            label=item["label"],
            category=item["category"],
            availability=availability,
            integrationStatus=item["integrationStatus"],
            publicStatus=item["publicStatus"],
            reviewPoint=item["reviewPoint"],
            dataQuality=self._data_quality(
                state=quality_state,
                summary=self._module_quality_summary(item["label"], availability=availability),
            ),
        )

    def _aggregate_status(self, modules: list[HomepageModuleManifestItem]) -> str:
        availability = {module.availability for module in modules}
        if availability == {"ready"}:
            return "ready"
        if availability <= {"no_evidence", "unavailable"}:
            return "unavailable" if availability == {"unavailable"} else "no_evidence"
        return "partial"

    def _data_quality(self, *, state: str, summary: str) -> HomepageModuleDataQuality:
        return HomepageModuleDataQuality(
            state=state,
            label=_DATA_QUALITY_LABELS[state],
            summary=summary,
        )

    def _module_quality_summary(self, label: str, *, availability: str) -> str:
        if availability == "ready":
            return f"{label}合同字段已整理为消费者安全描述，可用于公开状态与接入状态观察。"
        if availability == "scaffold":
            return f"{label}当前仅保留合同骨架，接入前仍需补足公开字段复核。"
        if availability == "no_evidence":
            return f"{label}当前暂无足够公开证据，仅保留模块占位。"
        return f"{label}当前暂不可用，仅保留受限状态说明。"

    def _safe_as_of(self, as_of: str | None) -> str:
        text = str(as_of or "").strip()
        if text:
            return text
        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
