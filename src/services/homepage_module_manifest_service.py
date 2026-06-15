# -*- coding: utf-8 -*-
"""Standalone homepage module manifest service.

This service is intentionally inert. It only exposes a bounded manifest for
homepage intelligence modules and does not launch modules, fetch providers, or
change existing dashboard/runtime behavior.
"""

from __future__ import annotations

from typing import Any

from api.v1.schemas.homepage_module_manifest import (
    HomepageModuleDataQuality,
    HomepageModuleManifestItem,
    HomepageModuleManifestResponse,
)
from src.services.homepage_capabilities_service import HOMEPAGE_COCKPIT_MODULES


NO_ADVICE_DISCLOSURE = "仅供模块观察范围、证据边界与研究支持识别，不构成个性化投资建议。"
TOP_LEVEL_DATA_QUALITY_SUMMARY = "当前模块 manifest 仅描述公开观察范围、研究支持状态与复核点，不包含操作性结论。"
DEFAULT_MANIFEST_AS_OF = "2026-06-15T00:00:00Z"
_DATA_QUALITY_LABELS = {
    "ready": "正常",
    "partial": "部分缺失",
    "no_evidence": "暂无证据",
    "unavailable": "暂不可用",
}
_QUALITY_STATE_BY_AVAILABILITY = {
    "ready": "ready",
    "sample": "partial",
    "proxy": "partial",
    "scaffold": "partial",
    "no_evidence": "no_evidence",
    "unavailable": "unavailable",
}


class HomepageModuleManifestService:
    """Build a bounded manifest for homepage intelligence modules."""

    def build_manifest(self, *, as_of: str | None = None) -> dict[str, Any]:
        modules = [self._build_module(item) for item in HOMEPAGE_COCKPIT_MODULES]
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
        quality_state = _QUALITY_STATE_BY_AVAILABILITY[availability]
        return HomepageModuleManifestItem(
            key=item["key"],
            label=item["label"],
            category=item["category"],
            availability=availability,
            integrationStatus="standalone",
            publicStatus="public",
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
        if availability == "sample":
            return f"{label}当前展示样本化观察内容，仍需复核证据边界。"
        if availability == "proxy":
            return f"{label}当前展示代理观察内容，不能代表完整证据。"
        if availability == "scaffold":
            return f"{label}当前仅保留合同骨架，接入前仍需补足公开字段复核。"
        if availability == "no_evidence":
            return f"{label}当前暂无足够公开证据，仅保留模块占位。"
        return f"{label}当前暂不可用，仅保留受限状态说明。"

    def _safe_as_of(self, as_of: str | None) -> str:
        text = str(as_of or "").strip()
        if text:
            return text
        return DEFAULT_MANIFEST_AS_OF
