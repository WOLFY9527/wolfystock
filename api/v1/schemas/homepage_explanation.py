# -*- coding: utf-8 -*-
"""Standalone homepage why-it-matters explanation contract."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


HomepageExplanationTopLevelStatus = Literal["ready", "no_evidence", "unavailable"]
HomepageExplanationItemStatus = Literal["ready", "review", "no_evidence", "unavailable"]
HomepageExplanationDataQualityState = Literal["ready", "delayed", "cached", "partial", "no_evidence", "unavailable"]

MAX_EXPLANATIONS = 6
MAX_RELATED_SIGNALS = 4
MAX_ID_LENGTH = 40
MAX_MODULE_LENGTH = 32
MAX_TITLE_LENGTH = 32
MAX_WHY_IT_MATTERS_LENGTH = 80
MAX_REVIEW_POINT_LENGTH = 48
FORBIDDEN_ADVICE_RE = re.compile(
    r"\b(buy|sell|add(?: position)?|reduce(?: position)?|target[\s-]?price|stop[\s-]?loss|"
    r"take[\s-]?profit|predicted[\s-]?return|ai recommendation|place order|submit order)\b|"
    r"买入|卖出|加仓|减仓|目标价|止损|止盈|投资建议|交易建议|下单",
    re.IGNORECASE,
)
FORBIDDEN_LEAK_RE = re.compile(
    r"traceback|token|session|api[_-]?key|secret|reasoncode|trustlevel|sourcetype|fallback|"
    r"providerroute|rawpayload|providerpayload|debug|internal diagnostics|https?://|/users/",
    re.IGNORECASE,
)
UNSAFE_TOKEN_RE = re.compile(
    r"buy|sell|add|reduce|target|stop|take|predict|recommend|order|trade|"
    r"traceback|token|session|apikey|api_key|secret|reasoncode|trustlevel|sourcetype|fallback|http|users",
    re.IGNORECASE,
)


def contains_unsafe_text(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return bool(FORBIDDEN_ADVICE_RE.search(text) or FORBIDDEN_LEAK_RE.search(text))


def normalize_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def normalize_identifier(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")


def contains_unsafe_token(value: Any) -> bool:
    token = str(value or "").strip()
    if not token:
        return False
    return bool(UNSAFE_TOKEN_RE.search(token))


def ensure_safe_text(value: Any, *, field_name: str, max_length: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if contains_unsafe_text(text):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds max_length={max_length}")
    return text


def ensure_safe_token(value: Any, *, field_name: str, max_length: int) -> str:
    token = normalize_token(value)
    if not token:
        raise ValueError(f"{field_name} must not be empty")
    if len(token) > max_length:
        raise ValueError(f"{field_name} exceeds max_length={max_length}")
    if contains_unsafe_text(token) or contains_unsafe_token(token):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    return token


def ensure_safe_identifier(value: Any, *, field_name: str, max_length: int) -> str:
    token = normalize_identifier(value)
    if not token:
        raise ValueError(f"{field_name} must not be empty")
    if len(token) > max_length:
        raise ValueError(f"{field_name} exceeds max_length={max_length}")
    if contains_unsafe_text(token) or contains_unsafe_token(token):
        raise ValueError(f"{field_name} contains forbidden advice or diagnostics content")
    return token


class _HomepageExplanationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomepageExplanationDataQualityModel(_HomepageExplanationModel):
    state: HomepageExplanationDataQualityState
    label: str
    available: bool = False

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return ensure_safe_text(
            value,
            field_name="dataQuality.label",
            max_length=16,
        )


class HomepageExplanationItemModel(_HomepageExplanationModel):
    id: str
    sourceModule: str
    title: str
    whyItMatters: str
    relatedSignals: list[str] = Field(default_factory=list, max_length=MAX_RELATED_SIGNALS)
    reviewPoint: str
    status: HomepageExplanationItemStatus

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        return ensure_safe_identifier(value, field_name="id", max_length=MAX_ID_LENGTH)

    @field_validator("sourceModule")
    @classmethod
    def _validate_source_module(cls, value: str) -> str:
        return ensure_safe_token(
            value,
            field_name="sourceModule",
            max_length=MAX_MODULE_LENGTH,
        )

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        return ensure_safe_text(value, field_name="title", max_length=MAX_TITLE_LENGTH)

    @field_validator("whyItMatters")
    @classmethod
    def _validate_why_it_matters(cls, value: str) -> str:
        return ensure_safe_text(
            value,
            field_name="whyItMatters",
            max_length=MAX_WHY_IT_MATTERS_LENGTH,
        )

    @field_validator("reviewPoint")
    @classmethod
    def _validate_review_point(cls, value: str) -> str:
        return ensure_safe_text(
            value,
            field_name="reviewPoint",
            max_length=MAX_REVIEW_POINT_LENGTH,
        )

    @field_validator("relatedSignals")
    @classmethod
    def _validate_related_signals(cls, value: list[str]) -> list[str]:
        return [
            ensure_safe_token(
                item,
                field_name="relatedSignals",
                max_length=MAX_MODULE_LENGTH,
            )
            for item in value
        ]


class HomepageExplanationResponseModel(_HomepageExplanationModel):
    status: HomepageExplanationTopLevelStatus
    asOf: str | None = None
    explanations: list[HomepageExplanationItemModel] = Field(
        default_factory=list,
        max_length=MAX_EXPLANATIONS,
    )
    noAdviceDisclosure: str
    dataQuality: HomepageExplanationDataQualityModel

    @field_validator("noAdviceDisclosure")
    @classmethod
    def _validate_no_advice_disclosure(cls, value: str) -> str:
        return ensure_safe_text(
            value,
            field_name="noAdviceDisclosure",
            max_length=MAX_WHY_IT_MATTERS_LENGTH,
        )

    @field_validator("asOf")
    @classmethod
    def _validate_as_of(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if len(text) > 40 or contains_unsafe_text(text):
            raise ValueError("asOf contains forbidden content")
        return text


__all__ = [
    "FORBIDDEN_ADVICE_RE",
    "FORBIDDEN_LEAK_RE",
    "HomepageExplanationDataQualityModel",
    "HomepageExplanationItemModel",
    "HomepageExplanationResponseModel",
    "contains_unsafe_text",
    "contains_unsafe_token",
    "ensure_safe_identifier",
    "ensure_safe_text",
    "ensure_safe_token",
    "normalize_identifier",
    "normalize_token",
]
