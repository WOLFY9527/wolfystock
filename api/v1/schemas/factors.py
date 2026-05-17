# -*- coding: utf-8 -*-
"""Stable factor registry and observation contracts."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.services.market_data_source_registry import CANONICAL_SOURCE_TYPES


FACTOR_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[._][a-z0-9]+)*$")
FACTOR_VALUE_LIMIT = 1_000_000.0
FACTOR_Z_SCORE_LIMIT = 10.0

FactorFamily = Literal[
    "trend",
    "momentum",
    "relative_strength",
    "volatility_quality",
    "liquidity",
    "activity",
    "sector_context",
]
FactorDirection = Literal["higher_is_better", "lower_is_better", "context_only"]
FactorFreshnessStatus = Literal["live", "fresh", "cached", "delayed", "stale", "fallback", "partial", "unavailable"]
FactorEvidenceType = Literal["metric", "snapshot", "regime", "peer_compare", "note"]
FactorDisposition = Literal["positive", "negative", "neutral", "observe_only", "blocked"]
FactorSignalSide = Literal["long", "short", "neutral"]
FactorNeutralizationAxis = Literal["sector", "industry", "market_cap_bucket", "beta_bucket", "country", "market"]
FactorNeutralizationMethod = Literal["none", "cross_sectional_rank", "zscore_demean", "sector_residual"]


def normalize_factor_id(value: Any) -> str:
    """Normalize ids to lowercase dotted/snake format."""
    text = str(value or "").strip().lower()
    text = re.sub(r"[\s\-]+", "_", text)
    text = re.sub(r"[^a-z0-9._]+", "_", text)
    text = re.sub(r"_+", "_", text)
    text = re.sub(r"\.+", ".", text)
    text = text.replace("_.", ".").replace("._", ".")
    text = text.strip("._")
    if not text or not FACTOR_ID_PATTERN.match(text):
        raise ValueError("factor_id must normalize to lowercase snake/dot format")
    return text


def _required_text(value: Any, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def _validate_iso_like(value: Any, field_name: str) -> str:
    normalized = _required_text(value, field_name)
    iso_text = normalized.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(iso_text)
    except ValueError:
        try:
            date.fromisoformat(iso_text)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an ISO date or datetime string") from exc
    return normalized


class _FactorModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class FactorNeutralizationSpec(_FactorModel):
    method: FactorNeutralizationMethod = "cross_sectional_rank"
    axes: list[FactorNeutralizationAxis] = Field(default_factory=list)
    exposure_limit: Optional[float] = Field(default=None, ge=0, le=1)
    notes: list[str] = Field(default_factory=list)

    @field_validator("axes", mode="before")
    @classmethod
    def _normalize_axes(cls, value: Any) -> list[str]:
        if value is None:
            return []
        raw_items = value if isinstance(value, list) else [value]
        result: list[str] = []
        seen: set[str] = set()
        for item in raw_items:
            normalized = str(item or "").strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result


class FactorDefinition(_FactorModel):
    factor_id: str
    family: FactorFamily
    label: str
    description: str
    direction: FactorDirection
    unit: str = "score"
    default_lookback_days: Optional[int] = Field(default=None, ge=1, le=756)
    expected_range_min: Optional[float] = Field(default=None, ge=-FACTOR_VALUE_LIMIT, le=FACTOR_VALUE_LIMIT)
    expected_range_max: Optional[float] = Field(default=None, ge=-FACTOR_VALUE_LIMIT, le=FACTOR_VALUE_LIMIT)
    neutralization: Optional[FactorNeutralizationSpec] = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("factor_id")
    @classmethod
    def _normalize_factor_id(cls, value: Any) -> str:
        return normalize_factor_id(value)

    @field_validator("label", "description", "unit")
    @classmethod
    def _validate_text_fields(cls, value: Any, info: Any) -> str:
        return _required_text(value, info.field_name)

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tags(cls, value: Any) -> list[str]:
        if value is None:
            return []
        raw_items = value if isinstance(value, list) else [value]
        result: list[str] = []
        seen: set[str] = set()
        for item in raw_items:
            normalized = str(item or "").strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    @model_validator(mode="after")
    def _validate_ranges_and_family(self) -> "FactorDefinition":
        if self.expected_range_min is not None and self.expected_range_max is not None:
            if self.expected_range_min > self.expected_range_max:
                raise ValueError("expected_range_min must be <= expected_range_max")
        family_prefix = self.factor_id.split(".", 1)[0]
        if family_prefix != self.family:
            raise ValueError("factor_id prefix must match factor family")
        return self


class _FactorProvenanceModel(_FactorModel):
    source_name: str
    source_type: str
    as_of: str
    observed_at: str
    freshness_status: FactorFreshnessStatus
    confidence: float = Field(ge=0, le=1)
    is_fallback: bool = False
    is_stale: bool = False
    is_partial: bool = False

    @field_validator("source_name")
    @classmethod
    def _validate_source_name(cls, value: Any) -> str:
        return _required_text(value, "source_name")

    @field_validator("source_type")
    @classmethod
    def _validate_source_type(cls, value: Any) -> str:
        normalized = _required_text(value, "source_type").lower()
        if normalized not in CANONICAL_SOURCE_TYPES:
            raise ValueError(f"source_type must be one of {sorted(CANONICAL_SOURCE_TYPES)}")
        return normalized

    @field_validator("as_of")
    @classmethod
    def _validate_as_of(cls, value: Any) -> str:
        return _validate_iso_like(value, "as_of")

    @field_validator("observed_at")
    @classmethod
    def _validate_observed_at(cls, value: Any) -> str:
        return _validate_iso_like(value, "observed_at")

    @model_validator(mode="after")
    def _validate_freshness_constraints(self) -> "_FactorProvenanceModel":
        fallback_like = self.is_fallback or self.source_type == "fallback_static"
        if fallback_like and self.freshness_status in {"live", "fresh"}:
            raise ValueError("fallback data cannot claim live/fresh freshness_status")
        if self.is_stale and self.freshness_status in {"live", "fresh"}:
            raise ValueError("stale data cannot claim live/fresh freshness_status")
        return self


class FactorEvidence(_FactorProvenanceModel):
    factor_id: str
    evidence_type: FactorEvidenceType
    title: str
    summary: Optional[str] = None
    metric_name: Optional[str] = None
    numeric_value: Optional[float] = Field(default=None, ge=-FACTOR_VALUE_LIMIT, le=FACTOR_VALUE_LIMIT)
    raw_value: Optional[str] = None

    @field_validator("factor_id")
    @classmethod
    def _normalize_factor_id(cls, value: Any) -> str:
        return normalize_factor_id(value)

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: Any) -> str:
        return _required_text(value, "title")


class FactorObservation(_FactorProvenanceModel):
    factor_id: str
    symbol: str
    value: float = Field(ge=-FACTOR_VALUE_LIMIT, le=FACTOR_VALUE_LIMIT)
    percentile: Optional[float] = Field(default=None, ge=0, le=1)
    z_score: Optional[float] = Field(default=None, ge=-FACTOR_Z_SCORE_LIMIT, le=FACTOR_Z_SCORE_LIMIT)
    basis: Optional[str] = None
    evidences: list[FactorEvidence] = Field(default_factory=list)

    @field_validator("factor_id")
    @classmethod
    def _normalize_factor_id(cls, value: Any) -> str:
        return normalize_factor_id(value)

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: Any) -> str:
        return _required_text(value, "symbol").upper()

    @model_validator(mode="after")
    def _validate_evidence_factor_ids(self) -> "FactorObservation":
        for item in self.evidences:
            if item.factor_id != self.factor_id:
                raise ValueError("all evidences must match the observation factor_id")
        return self


class FactorEvaluation(_FactorProvenanceModel):
    factor_id: str
    symbol: str
    score: float = Field(ge=-1, le=1)
    disposition: FactorDisposition = "neutral"
    observation: FactorObservation
    evidences: list[FactorEvidence] = Field(default_factory=list)
    neutralization: Optional[FactorNeutralizationSpec] = None
    notes: list[str] = Field(default_factory=list)

    @field_validator("factor_id")
    @classmethod
    def _normalize_factor_id(cls, value: Any) -> str:
        return normalize_factor_id(value)

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: Any) -> str:
        return _required_text(value, "symbol").upper()

    @model_validator(mode="after")
    def _validate_nested_contracts(self) -> "FactorEvaluation":
        if self.observation.factor_id != self.factor_id:
            raise ValueError("observation.factor_id must match evaluation.factor_id")
        if self.observation.symbol != self.symbol:
            raise ValueError("observation.symbol must match evaluation.symbol")
        for item in self.evidences:
            if item.factor_id != self.factor_id:
                raise ValueError("all evidences must match the evaluation factor_id")
        return self


class FactorPortfolioSignal(_FactorProvenanceModel):
    factor_id: str
    symbol: str
    side: FactorSignalSide
    signal_weight: float = Field(ge=-1, le=1)
    conviction: float = Field(ge=0, le=1)
    evaluation_score: float = Field(ge=-1, le=1)
    neutralization: Optional[FactorNeutralizationSpec] = None
    notes: list[str] = Field(default_factory=list)

    @field_validator("factor_id")
    @classmethod
    def _normalize_factor_id(cls, value: Any) -> str:
        return normalize_factor_id(value)

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: Any) -> str:
        return _required_text(value, "symbol").upper()


__all__ = [
    "FactorDefinition",
    "FactorDirection",
    "FactorDisposition",
    "FactorEvidence",
    "FactorEvaluation",
    "FactorEvidenceType",
    "FactorFamily",
    "FactorFreshnessStatus",
    "FactorNeutralizationAxis",
    "FactorNeutralizationMethod",
    "FactorNeutralizationSpec",
    "FactorObservation",
    "FactorPortfolioSignal",
    "FactorSignalSide",
    "normalize_factor_id",
]
