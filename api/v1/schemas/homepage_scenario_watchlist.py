# -*- coding: utf-8 -*-
"""Standalone scenario watchlist contract for the homepage intelligence cockpit."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


HomepageScenarioWatchlistEvidenceQuality = Literal[
    "scenario_monitoring",
    "needs_confirmation",
    "mixed",
    "limited",
]
HomepageScenarioWatchlistDataQuality = Literal[
    "deterministic",
    "static_sample",
    "partial",
    "unavailable",
]

HOMEPAGE_SCENARIO_WATCHLIST_SCHEMA_VERSION = "homepage_scenario_watchlist_v1"
HOMEPAGE_SCENARIO_WATCHLIST_DEFAULT_AS_OF = "2026-06-15T09:30:00Z"
HOMEPAGE_SCENARIO_WATCHLIST_NO_ADVICE_DISCLOSURE = (
    "For homepage scenario monitoring only; not a personalized decision basis."
)

_FORBIDDEN_TEXT_RE = re.compile(
    r"交易指令|交易执行|交易建议|买入|卖出|加仓|减仓|清仓|止损|止盈|目标价|"
    r"收益预测|AI推荐|智能选股|投资建议|下单|立即交易|"
    r"\b(?:buy|sell|broker|order|trade[\s-]?execution|trading[\s-]?advice|"
    r"investment[\s-]?advice|financial[\s-]?advice|target[\s-]?price|"
    r"stop[\s-]?loss|take[\s-]?profit|place[\s-]?order|submit[\s-]?order)\b|"
    r"provider|fallback|internal|diagnostic|debug|traceback|reasoncode|trustlevel|"
    r"sourcetype|raw|token|secret|cookie|session|api[_-]?key|https?://|/users/|/tmp/",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def contains_forbidden_scenario_watchlist_text(value: Any) -> bool:
    text = str(value or "")
    return bool(text and _FORBIDDEN_TEXT_RE.search(text))


def ensure_scenario_watchlist_text(value: Any, *, field_name: str, max_length: int) -> str:
    text = _WHITESPACE_RE.sub(" ", str(value or "").strip())
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds max_length={max_length}")
    if contains_forbidden_scenario_watchlist_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    return text


def _assert_safe_nested_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        ensure_scenario_watchlist_text(value, field_name=field_name, max_length=240)
        return
    if isinstance(value, BaseModel):
        _assert_safe_nested_text(value.model_dump(mode="json"), field_name=field_name)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_safe_nested_text(item, field_name=f"{field_name}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_safe_nested_text(item, field_name=f"{field_name}[{index}]")


class _HomepageScenarioWatchlistBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepageScenarioWatchlistScenario(_HomepageScenarioWatchlistBase):
    scenarioName: str
    description: str
    affectedAssets: list[str] = Field(..., min_length=1, max_length=8)
    affectedSectors: list[str] = Field(..., min_length=1, max_length=8)
    affectedThemes: list[str] = Field(..., min_length=1, max_length=8)
    triggerConditions: list[str] = Field(..., min_length=1, max_length=5)
    confirmingSignals: list[str] = Field(..., min_length=1, max_length=5)
    invalidatingSignals: list[str] = Field(..., min_length=1, max_length=5)
    evidenceQuality: HomepageScenarioWatchlistEvidenceQuality
    dataQuality: HomepageScenarioWatchlistDataQuality

    @field_validator("scenarioName")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return ensure_scenario_watchlist_text(value, field_name="scenarioName", max_length=80)

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        return ensure_scenario_watchlist_text(value, field_name="description", max_length=200)

    @field_validator(
        "affectedAssets",
        "affectedSectors",
        "affectedThemes",
        "triggerConditions",
        "confirmingSignals",
        "invalidatingSignals",
    )
    @classmethod
    def _validate_text_list(cls, value: list[str]) -> list[str]:
        return [
            ensure_scenario_watchlist_text(item, field_name="scenarioWatchlist.listItem", max_length=120)
            for item in value
        ]


class HomepageScenarioWatchlistSnapshot(_HomepageScenarioWatchlistBase):
    schemaVersion: str = Field(default=HOMEPAGE_SCENARIO_WATCHLIST_SCHEMA_VERSION)
    asOf: str = Field(default=HOMEPAGE_SCENARIO_WATCHLIST_DEFAULT_AS_OF, min_length=1, max_length=40)
    scenarios: list[HomepageScenarioWatchlistScenario] = Field(..., min_length=1, max_length=10)
    evidenceQuality: HomepageScenarioWatchlistEvidenceQuality
    dataQuality: HomepageScenarioWatchlistDataQuality
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=100)

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str) -> str:
        return ensure_scenario_watchlist_text(value, field_name="asOf", max_length=40)

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_scenario_watchlist_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=100,
        )

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "HomepageScenarioWatchlistSnapshot":
        if self.schemaVersion != HOMEPAGE_SCENARIO_WATCHLIST_SCHEMA_VERSION:
            raise ValueError("schemaVersion mismatch")
        _assert_safe_nested_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_SCENARIO_WATCHLIST_DEFAULT_AS_OF",
    "HOMEPAGE_SCENARIO_WATCHLIST_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_SCENARIO_WATCHLIST_SCHEMA_VERSION",
    "HomepageScenarioWatchlistDataQuality",
    "HomepageScenarioWatchlistEvidenceQuality",
    "HomepageScenarioWatchlistScenario",
    "HomepageScenarioWatchlistSnapshot",
    "contains_forbidden_scenario_watchlist_text",
    "ensure_scenario_watchlist_text",
]
