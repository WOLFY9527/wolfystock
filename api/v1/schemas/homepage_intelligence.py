# -*- coding: utf-8 -*-
"""Bounded homepage intelligence metadata contract for UI discovery and UAT."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


HomepageIntelligenceStatus = Literal["ready", "partial", "no_evidence", "unavailable"]
HomepageIntelligenceScope = Literal["homepage_ui_uat_metadata"]

HOMEPAGE_INTELLIGENCE_SCHEMA_VERSION = "homepage_intelligence_v1"
HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF = "2026-06-14T09:30:00Z"
HOMEPAGE_INTELLIGENCE_NO_ADVICE_DISCLOSURE = (
    "仅供首页元数据与固定样例联调，不构成投资建议。"
)
HOMEPAGE_INTELLIGENCE_DEFAULT_SCENARIO = "happy_path"
HOMEPAGE_INTELLIGENCE_ALLOWED_SCENARIOS = frozenset({"happy_path", "degraded_example"})

_FORBIDDEN_TEXT_MARKERS = (
    "买入",
    "卖出",
    "下单",
    "立即交易",
    "交易信号",
    "交易指令",
    "目标价",
    "止损",
    "止盈",
    "recommendation",
    "buynow",
    "sellnow",
    "placeorder",
    "targetprice",
    "buy now",
    "sell now",
    "place order",
    "target price",
    "traceback",
    "provider",
    "fallback",
    "diagnostic",
    "debug",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "rawpayload",
    "raw provider",
    "raw_provider",
    "token",
    "secret",
    "cookie",
    "sessionid",
    "apikey",
    "api key",
    "http://",
    "https://",
    "livedata",
    "实时数据",
    "realtime",
    "real-time",
)
_FORBIDDEN_KEY_MARKERS = (
    "fallback",
    "trustlevel",
    "sourcetype",
    "reasoncode",
    "raw",
    "provider",
    "traceback",
    "scaffold",
)
_DEMO_MARKER_KEYS = frozenset({"sampleData", "demoPayload"})


def _compact(value: str) -> str:
    return value.lower().replace("_", "").replace(" ", "").replace("-", "")


def _assert_safe_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        compact = _compact(value)
        for marker in _FORBIDDEN_TEXT_MARKERS:
            if _compact(marker) in compact:
                raise ValueError(f"{field_name} contains forbidden text marker: {marker}")
        return
    if isinstance(value, BaseModel):
        _assert_safe_text(value.model_dump(mode="json"), field_name=field_name)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            key_compact = _compact(str(key))
            for marker in _FORBIDDEN_KEY_MARKERS:
                if marker in key_compact:
                    raise ValueError(f"{field_name}.{key} contains forbidden key marker: {marker}")
            _assert_safe_text(item, field_name=f"{field_name}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_safe_text(item, field_name=f"{field_name}[{index}]")


def _assert_demo_marker_scope(value: Any, *, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, BaseModel):
        _assert_demo_marker_scope(value.model_dump(mode="json"), path=path)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = (*path, str(key))
            if key in _DEMO_MARKER_KEYS and not _is_demo_fixture_path(path):
                raise ValueError(f"{'.'.join(child_path)} must stay inside demo fixture subtree")
            _assert_demo_marker_scope(item, path=child_path)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_demo_marker_scope(item, path=(*path, str(index)))


def _is_demo_fixture_path(path: tuple[str, ...]) -> bool:
    return len(path) >= 3 and path[0] == "demo" and path[1] == "scenarios"


class HomepageIntelligenceDemoBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    defaultScenario: Literal["happy_path"]
    scenarios: dict[str, dict[str, Any]]

    @model_validator(mode="after")
    def _validate_demo_bundle(self) -> "HomepageIntelligenceDemoBundle":
        if set(self.scenarios) != set(HOMEPAGE_INTELLIGENCE_ALLOWED_SCENARIOS):
            raise ValueError("demo scenarios mismatch")
        for scenario_name, payload in self.scenarios.items():
            if payload.get("scenario") != scenario_name:
                raise ValueError(f"demo scenario payload mismatch: {scenario_name}")
            if payload.get("asOf") != HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF:
                raise ValueError(f"demo scenario asOf mismatch: {scenario_name}")
            if payload.get("sampleData") is not True or payload.get("demoPayload") is not True:
                raise ValueError(f"demo scenario must remain sample-only: {scenario_name}")
        _assert_safe_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


class HomepageIntelligenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: str = Field(default=HOMEPAGE_INTELLIGENCE_SCHEMA_VERSION)
    status: HomepageIntelligenceStatus
    scope: HomepageIntelligenceScope
    asOf: str = Field(..., min_length=1, max_length=40)
    sampleOnly: bool
    capabilities: dict[str, Any]
    moduleManifest: dict[str, Any]
    sessionStatus: dict[str, Any]
    sourceFreshness: dict[str, Any]
    demo: HomepageIntelligenceDemoBundle
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=120)

    @model_validator(mode="after")
    def _validate_contract(self) -> "HomepageIntelligenceResponse":
        if self.schemaVersion != HOMEPAGE_INTELLIGENCE_SCHEMA_VERSION:
            raise ValueError("schemaVersion mismatch")
        if self.asOf != HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF:
            raise ValueError("asOf must remain deterministic for metadata/UAT payloads")
        if self.sampleOnly is not True:
            raise ValueError("sampleOnly must remain true")
        dumped = self.model_dump(mode="json")
        _assert_demo_marker_scope(dumped)
        _assert_safe_text(dumped, field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_INTELLIGENCE_ALLOWED_SCENARIOS",
    "HOMEPAGE_INTELLIGENCE_DEFAULT_AS_OF",
    "HOMEPAGE_INTELLIGENCE_DEFAULT_SCENARIO",
    "HOMEPAGE_INTELLIGENCE_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_INTELLIGENCE_SCHEMA_VERSION",
    "HomepageIntelligenceDemoBundle",
    "HomepageIntelligenceResponse",
    "HomepageIntelligenceScope",
    "HomepageIntelligenceStatus",
]
