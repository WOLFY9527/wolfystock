# -*- coding: utf-8 -*-
"""Consumer-safe homepage UAT readiness checklist contract."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator


HomepageUatReadinessStatus = Literal["pass", "review", "blocked", "no_evidence"]
HomepageUatReadinessOwnerArea = Literal["backend_contract", "frontend_ui", "data_quality", "copy", "qa"]

_FORBIDDEN_TEXT_MARKERS = (
    "买入",
    "卖出",
    "下单",
    "交易信号",
    "止损",
    "止盈",
    "目标价",
    "保证收益",
    "稳赚",
    "buy now",
    "sell now",
    "trading signal",
    "target price",
    "guaranteed",
    "best contract",
    "ai recommends you buy",
    "traceback",
    "provider",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "token",
    "session",
    "apikey",
    "secret",
    "cookie",
    "debug",
    "raw",
    "internal.example",
    "/tmp/",
)


def _assert_safe_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        compact = value.lower().replace("_", "").replace(" ", "")
        for marker in _FORBIDDEN_TEXT_MARKERS:
            normalized_marker = marker.lower().replace("_", "").replace(" ", "")
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


class HomepageUatReadinessResponse(_HomepageUatReadinessBase):
    status: HomepageUatReadinessStatus
    asOf: str
    checks: list[HomepageUatReadinessCheck]
    summary: str
    noAdviceDisclosure: str
    dataQuality: HomepageUatReadinessDataQuality
