# -*- coding: utf-8 -*-
"""Consumer-safe homepage UAT readiness checklist contract."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator


HomepageUatReadinessStatus = Literal["pass", "review", "blocked", "no_evidence"]
HomepageUatReadinessOwnerArea = Literal["contract", "frontend_ui", "data_quality", "copy", "qa", "integration"]
HomepageUatReadinessModuleState = Literal["ready", "review", "blocked", "no_evidence"]
HomepageUatReadinessDataIntegration = Literal[
    "not_wired_current_data",
    "static_contract_only",
    "proxy_only",
    "no_evidence",
]
HomepageUatReadinessEvidenceBoundary = Literal[
    "static_contract",
    "deterministic_sample",
    "placeholder",
    "proxy_only",
    "proxy_no_evidence_mix",
    "sample_proxy",
]

_FORBIDDEN_TEXT_MARKERS = (
    "买入",
    "卖出",
    "下单",
    "立即交易",
    "交易信号",
    "交易指令",
    "交易建议",
    "交易执行",
    "止损",
    "止盈",
    "目标价",
    "投资建议",
    "收益预测",
    "保证收益",
    "稳赚",
    "buy now",
    "sell now",
    "place order",
    "trading signal",
    "trading advice",
    "trade execution",
    "investment advice",
    "target price",
    "recommendation",
    "guaranteed",
    "best contract",
    "ai recommends you buy",
    "traceback",
    "provider",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "token",
    "sessionid",
    "session id",
    "apikey",
    "secret",
    "cookie",
    "debug",
    "raw",
    "internal.example",
    "/tmp/",
)


def _compact_text(value: str) -> str:
    return value.lower().replace("_", "").replace(" ", "").replace("-", "")


def _assert_safe_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        compact = _compact_text(value)
        for marker in _FORBIDDEN_TEXT_MARKERS:
            normalized_marker = _compact_text(marker)
            if normalized_marker in compact:
                raise ValueError(f"{field_name} contains forbidden text marker: {marker}")
        return
    if isinstance(value, BaseModel):
        _assert_safe_text(value.model_dump(mode="json"), field_name=field_name)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_safe_text(item, field_name=f"{field_name}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_safe_text(item, field_name=f"{field_name}[{index}]")


class _HomepageUatReadinessBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_safe_text(self):
        _assert_safe_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


class HomepageUatReadinessDataQuality(_HomepageUatReadinessBase):
    status: HomepageUatReadinessStatus
    label: str
    publicMessage: str


class HomepageUatReadinessCheck(_HomepageUatReadinessBase):
    key: str
    label: str
    status: HomepageUatReadinessStatus
    publicMessage: str
    ownerArea: HomepageUatReadinessOwnerArea
    required: bool


class HomepageUatReadinessModule(_HomepageUatReadinessBase):
    taskId: str
    key: str
    label: str
    uatReviewable: bool
    reviewScope: list[str]
    evidenceBoundary: HomepageUatReadinessEvidenceBoundary
    evidenceBoundaryLabel: str
    serializationReadiness: HomepageUatReadinessModuleState
    publicDisplayReadiness: HomepageUatReadinessModuleState
    dataIntegrationReadiness: HomepageUatReadinessDataIntegration
    dataIntegrationLabel: str
    missingEvidenceCategories: list[str]
    uatChecklistItems: list[str]


class HomepageUatReadinessModuleSummary(_HomepageUatReadinessBase):
    totalModules: int
    reviewableModules: int
    notWiredDataModules: int
    sampleProxyOrNoEvidenceModules: int
    publicMessage: str


class HomepageUatReadinessResponse(_HomepageUatReadinessBase):
    status: HomepageUatReadinessStatus
    asOf: str
    checks: list[HomepageUatReadinessCheck]
    cockpitModules: list[HomepageUatReadinessModule]
    moduleSummary: HomepageUatReadinessModuleSummary
    summary: str
    noAdviceDisclosure: str
    dataQuality: HomepageUatReadinessDataQuality
