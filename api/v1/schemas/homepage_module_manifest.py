# -*- coding: utf-8 -*-
"""Consumer-safe homepage module manifest contract."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator


HomepageModuleManifestStatus = Literal["ready", "partial", "no_evidence", "unavailable"]
HomepageModuleAvailability = Literal["ready", "scaffold", "no_evidence", "unavailable"]
HomepageModuleIntegrationStatus = Literal["standalone", "wired", "pending", "unavailable"]
HomepageModulePublicStatus = Literal["public", "gated", "private_beta", "internal_only"]
HomepageModuleCategory = Literal["overview", "flow", "rotation", "events", "personal", "research", "quality"]

_FORBIDDEN_TEXT_MARKERS = (
    "买入",
    "卖出",
    "下单",
    "交易信号",
    "止损",
    "止盈",
    "目标价",
    "buy now",
    "sell now",
    "trading signal",
    "target price",
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
    "launch",
    "launcher",
    "navigate",
    "open module",
    "打开",
    "进入",
    "跳转",
    "导航",
    "入口",
)


def _assert_safe_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        compact = value.lower().replace("_", "").replace(" ", "")
        for marker in _FORBIDDEN_TEXT_MARKERS:
            if marker.lower().replace(" ", "") in compact:
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


class _HomepageManifestBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_safe_text(self):
        _assert_safe_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


class HomepageModuleDataQuality(_HomepageManifestBase):
    state: HomepageModuleManifestStatus
    label: str
    summary: str


class HomepageModuleManifestItem(_HomepageManifestBase):
    key: str
    label: str
    category: HomepageModuleCategory
    availability: HomepageModuleAvailability
    integrationStatus: HomepageModuleIntegrationStatus
    publicStatus: HomepageModulePublicStatus
    reviewPoint: str
    dataQuality: HomepageModuleDataQuality


class HomepageModuleManifestResponse(_HomepageManifestBase):
    status: HomepageModuleManifestStatus
    asOf: str
    modules: list[HomepageModuleManifestItem]
    dataQuality: HomepageModuleDataQuality
    noAdviceDisclosure: str
