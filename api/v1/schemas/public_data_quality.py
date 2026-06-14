# -*- coding: utf-8 -*-
"""Public-facing data quality summary contract for homepage and consumer surfaces."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


PublicDataQualityStatus = Literal["ready", "partial", "delayed", "cached", "no_evidence", "unavailable"]

PUBLIC_DATA_QUALITY_LABELS: dict[PublicDataQualityStatus, str] = {
    "ready": "正常",
    "partial": "部分缺失",
    "delayed": "数据延迟",
    "cached": "使用缓存",
    "no_evidence": "暂无证据",
    "unavailable": "暂不可用",
}
PUBLIC_DATA_QUALITY_MESSAGES: dict[PublicDataQualityStatus, str] = {
    "ready": "核心模块已更新，适合研究观察",
    "partial": "部分模块数据暂不完整，请结合更新时间观察",
    "delayed": "数据存在延迟，请结合更新时间观察",
    "cached": "当前使用最近一次可用数据，请结合更新时间观察",
    "no_evidence": "暂无足够证据生成公开摘要",
    "unavailable": "当前公开摘要暂不可用，请稍后查看",
}
PUBLIC_DATA_QUALITY_NO_ADVICE_DISCLOSURE = "仅供研究观察，不构成投资建议"

_SAFE_PUBLIC_MODULES = {
    "home": "首页",
    "homepage": "首页",
    "首页": "首页",
    "marketoverview": "市场总览",
    "marketoverviewpage": "市场总览",
    "market_overview": "市场总览",
    "market overview": "市场总览",
    "市场总览": "市场总览",
    "liquidity": "流动性观察",
    "liquiditymonitor": "流动性观察",
    "liquidity_monitor": "流动性观察",
    "流动性观察": "流动性观察",
    "rotation": "轮动观察",
    "rotationradar": "轮动观察",
    "rotation_radar": "轮动观察",
    "轮动观察": "轮动观察",
    "scanner": "扫描观察",
    "扫描观察": "扫描观察",
    "watchlist": "自选观察",
    "自选观察": "自选观察",
    "research": "研究观察",
    "researchobservation": "研究观察",
    "研究观察": "研究观察",
    "options": "期权观察",
    "期权观察": "期权观察",
}
_FORBIDDEN_PUBLIC_TEXT_RE = re.compile(
    r"traceback|provider|reasoncode|trustlevel|sourcetype|fallback|exception|"
    r"https?://|api[_-]?key|secret|cookie|session|token|path|/"
    ,
    re.IGNORECASE,
)


def _normalize_public_module_key(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value or "").strip().lower())


def sanitize_public_module_names(values: list[object] | tuple[object, ...] | set[object] | None) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []

    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = str(item or "").strip()
        if not text or _FORBIDDEN_PUBLIC_TEXT_RE.search(text):
            continue
        label = _SAFE_PUBLIC_MODULES.get(_normalize_public_module_key(text))
        if not label or label in seen:
            continue
        seen.add(label)
        result.append(label)
    return result


class PublicDataQualitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    status: PublicDataQualityStatus
    label: str
    suitable_for_research_observation: bool = Field(alias="suitableForResearchObservation")
    as_of: str | None = Field(default=None, alias="asOf")
    updated_modules: list[str] = Field(default_factory=list, alias="updatedModules")
    affected_modules: list[str] = Field(default_factory=list, alias="affectedModules")
    message: str
    no_advice_disclosure: str = Field(
        default=PUBLIC_DATA_QUALITY_NO_ADVICE_DISCLOSURE,
        alias="noAdviceDisclosure",
    )

    @field_validator("updated_modules", "affected_modules", mode="before")
    @classmethod
    def _sanitize_modules(cls, value: object) -> list[str]:
        if isinstance(value, list):
            return sanitize_public_module_names(value)
        if isinstance(value, tuple):
            return sanitize_public_module_names(list(value))
        if isinstance(value, set):
            return sanitize_public_module_names(list(value))
        return []
