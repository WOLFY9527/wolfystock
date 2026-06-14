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
    HomepageUatReadinessResponse,
)


NO_ADVICE_DISCLOSURE = "本清单仅用于首页视觉验收准备度复核，不构成投资建议或交易指令。"
SUMMARY_REVIEW = "首页视觉验收可进入人工复核，但仍需前端界面与 QA 执行结果确认。"
DATA_QUALITY_MESSAGE = "清单为静态合同，不执行实时行情或数据源检查。"
_STATUS_LABELS = {
    "pass": "通过",
    "review": "需人工复核",
    "blocked": "阻塞",
    "no_evidence": "暂无证据",
}
_CHECK_BLUEPRINTS: tuple[dict[str, object], ...] = (
    {
        "key": "backend_contract",
        "label": "后端合同形状",
        "status": "pass",
        "publicMessage": "清单字段、状态枚举与安全披露已固定，可供页面验收读取。",
        "ownerArea": "backend_contract",
        "required": True,
    },
    {
        "key": "frontend_visual_review",
        "label": "前端视觉复核",
        "status": "review",
        "publicMessage": "需要在目标页面完成桌面与窄屏视觉复核后再标记通过。",
        "ownerArea": "frontend_ui",
        "required": True,
    },
    {
        "key": "public_copy_safety",
        "label": "公开文案安全",
        "status": "pass",
        "publicMessage": "默认文案保持观察与复核口径，不包含操作号召。",
        "ownerArea": "copy",
        "required": True,
    },
    {
        "key": "data_quality_boundary",
        "label": "数据质量边界",
        "status": "review",
        "publicMessage": "本清单只说明验收准备度，不执行实时行情校验。",
        "ownerArea": "data_quality",
        "required": True,
    },
    {
        "key": "qa_execution",
        "label": "QA 执行记录",
        "status": "no_evidence",
        "publicMessage": "等待 UAT 人员补充页面截图、浏览器与验收结论。",
        "ownerArea": "qa",
        "required": True,
    },
)


class HomepageUatReadinessService:
    """Build a deterministic, consumer-safe homepage UAT readiness checklist."""

    def build_checklist(self, *, as_of: str | None = None) -> dict[str, Any]:
        checks = [self._build_check(item) for item in _CHECK_BLUEPRINTS]
        status = self._aggregate_status(checks)
        payload = HomepageUatReadinessResponse(
            status=status,
            asOf=self._safe_as_of(as_of),
            checks=checks,
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
