# -*- coding: utf-8 -*-
"""Immutable facts describing a source observation and its origin."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Iterable, Mapping


SOURCE_OBSERVATION_FACTS_VERSION = "source_observation_facts_v1"

_SOURCE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")


class SourceClass(str, Enum):
    OFFICIAL = "official"
    LICENSED = "licensed"
    FIRST_PARTY = "first_party"
    THIRD_PARTY = "third_party"
    UNKNOWN = "unknown"


class RawAvailability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    MISSING = "missing"
    UNKNOWN = "unknown"


class ObservationFreshness(str, Enum):
    LIVE = "live"
    FRESH = "fresh"
    DELAYED = "delayed"
    STALE = "stale"
    UNKNOWN = "unknown"


_AVAILABILITY_DEGRADATION = {
    RawAvailability.AVAILABLE: 0,
    RawAvailability.UNAVAILABLE: 1,
    RawAvailability.MISSING: 2,
    RawAvailability.UNKNOWN: 3,
}

_FRESHNESS_DEGRADATION = {
    ObservationFreshness.LIVE: 0,
    ObservationFreshness.FRESH: 1,
    ObservationFreshness.DELAYED: 2,
    ObservationFreshness.STALE: 3,
    ObservationFreshness.UNKNOWN: 4,
}


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    source_id: str
    source_class: SourceClass
    is_proxy: bool = False
    is_synthetic: bool = False
    is_fixture: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.source_class, SourceClass):
            raise TypeError("source_class must be a SourceClass")
        if not _SOURCE_ID_PATTERN.fullmatch(self.source_id):
            raise ValueError("source_id must be a stable lowercase source identifier")
        for name in ("is_proxy", "is_synthetic", "is_fixture"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")
        if self.is_fixture and not self.is_synthetic:
            raise ValueError("fixture source must also be synthetic")
        if self.source_class is SourceClass.OFFICIAL and self.is_proxy:
            raise ValueError("official source cannot be proxy")
        if self.source_class in {SourceClass.OFFICIAL, SourceClass.LICENSED} and self.is_synthetic:
            raise ValueError("official or licensed source cannot be synthetic")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SourceIdentity":
        payload = _strict_mapping(
            value,
            expected={"sourceId", "sourceClass", "isProxy", "isSynthetic", "isFixture"},
            context="source identity",
        )
        return cls(
            source_id=_strict_string(payload["sourceId"], field="sourceId"),
            source_class=_strict_enum(SourceClass, payload["sourceClass"], field="sourceClass"),
            is_proxy=_strict_bool(payload["isProxy"], field="isProxy"),
            is_synthetic=_strict_bool(payload["isSynthetic"], field="isSynthetic"),
            is_fixture=_strict_bool(payload["isFixture"], field="isFixture"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sourceId": self.source_id,
            "sourceClass": self.source_class.value,
            "isProxy": self.is_proxy,
            "isSynthetic": self.is_synthetic,
            "isFixture": self.is_fixture,
        }


@dataclass(frozen=True, slots=True)
class SourceObservationFacts:
    identity: SourceIdentity
    observed_at: datetime | None
    as_of: datetime | None
    raw_availability: RawAvailability
    freshness: ObservationFreshness
    is_cached: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.identity, SourceIdentity):
            raise TypeError("identity must be a SourceIdentity")
        _require_aware_datetime(self.observed_at, field="observed_at")
        _require_aware_datetime(self.as_of, field="as_of")
        if not isinstance(self.raw_availability, RawAvailability):
            raise TypeError("raw_availability must be a RawAvailability")
        if not isinstance(self.freshness, ObservationFreshness):
            raise TypeError("freshness must be an ObservationFreshness")
        if not isinstance(self.is_cached, bool):
            raise TypeError("is_cached must be a bool")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SourceObservationFacts":
        payload = _strict_mapping(
            value,
            expected={
                "contractVersion",
                "sourceIdentity",
                "observedAt",
                "asOf",
                "rawAvailability",
                "freshness",
                "isCached",
            },
            context="source observation",
        )
        if payload["contractVersion"] != SOURCE_OBSERVATION_FACTS_VERSION:
            raise ValueError("unsupported source observation contractVersion")
        identity_payload = payload["sourceIdentity"]
        if not isinstance(identity_payload, Mapping):
            raise TypeError("sourceIdentity must be a mapping")
        return cls(
            identity=SourceIdentity.from_dict(identity_payload),
            observed_at=_parse_optional_datetime(payload["observedAt"], field="observedAt"),
            as_of=_parse_optional_datetime(payload["asOf"], field="asOf"),
            raw_availability=_strict_enum(
                RawAvailability,
                payload["rawAvailability"],
                field="rawAvailability",
            ),
            freshness=_strict_enum(
                ObservationFreshness,
                payload["freshness"],
                field="freshness",
            ),
            is_cached=_strict_bool(payload["isCached"], field="isCached"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contractVersion": SOURCE_OBSERVATION_FACTS_VERSION,
            "sourceIdentity": self.identity.to_dict(),
            "observedAt": _format_optional_datetime(self.observed_at),
            "asOf": _format_optional_datetime(self.as_of),
            "rawAvailability": self.raw_availability.value,
            "freshness": self.freshness.value,
            "isCached": self.is_cached,
        }

    def degrade(
        self,
        *,
        raw_availability: RawAvailability | None = None,
        freshness: ObservationFreshness | None = None,
        drop_observed_at: bool = False,
        drop_as_of: bool = False,
        mark_cached: bool = False,
    ) -> "SourceObservationFacts":
        if raw_availability is not None and not isinstance(raw_availability, RawAvailability):
            raise TypeError("raw_availability must be a RawAvailability")
        if freshness is not None and not isinstance(freshness, ObservationFreshness):
            raise TypeError("freshness must be an ObservationFreshness")
        for name, value in (
            ("drop_observed_at", drop_observed_at),
            ("drop_as_of", drop_as_of),
            ("mark_cached", mark_cached),
        ):
            if not isinstance(value, bool):
                raise TypeError(f"{name} must be a bool")
        availability = raw_availability or self.raw_availability
        next_freshness = freshness or self.freshness
        if _AVAILABILITY_DEGRADATION[availability] < _AVAILABILITY_DEGRADATION[self.raw_availability]:
            raise ValueError("cannot upgrade raw availability")
        if _FRESHNESS_DEGRADATION[next_freshness] < _FRESHNESS_DEGRADATION[self.freshness]:
            raise ValueError("cannot upgrade freshness")
        return replace(
            self,
            observed_at=None if drop_observed_at else self.observed_at,
            as_of=None if drop_as_of else self.as_of,
            raw_availability=availability,
            freshness=next_freshness,
            is_cached=self.is_cached or mark_cached,
        )

    def as_cached(
        self,
        *,
        freshness: ObservationFreshness | None = None,
    ) -> "SourceObservationFacts":
        return self.degrade(freshness=freshness, mark_cached=True)


def merge_source_observations(
    observations: Iterable[SourceObservationFacts],
) -> SourceObservationFacts:
    items = tuple(observations)
    if not items:
        raise ValueError("at least one source observation is required")
    identity = items[0].identity
    if any(item.identity != identity for item in items[1:]):
        raise ValueError("cannot merge different source identities")
    return SourceObservationFacts(
        identity=identity,
        observed_at=_oldest_known_time(item.observed_at for item in items),
        as_of=_oldest_known_time(item.as_of for item in items),
        raw_availability=max(
            (item.raw_availability for item in items),
            key=_AVAILABILITY_DEGRADATION.__getitem__,
        ),
        freshness=max(
            (item.freshness for item in items),
            key=_FRESHNESS_DEGRADATION.__getitem__,
        ),
        is_cached=any(item.is_cached for item in items),
    )


def _strict_mapping(
    value: Mapping[str, Any],
    *,
    expected: set[str],
    context: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{context} must be a mapping")
    payload = dict(value)
    actual = set(payload)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        detail = []
        if missing:
            detail.append(f"missing {missing}")
        if unexpected:
            detail.append(f"unexpected {context} fields {unexpected}")
        raise ValueError("; ".join(detail))
    return payload


def _strict_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    return value


def _strict_bool(value: Any, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{field} must be a bool")
    return value


def _strict_enum(enum_type: type[Enum], value: Any, *, field: str) -> Any:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise ValueError(f"invalid {field}: {value}") from exc


def _require_aware_datetime(value: datetime | None, *, field: str) -> None:
    if value is None:
        return
    if not isinstance(value, datetime):
        raise TypeError(f"{field} must be a datetime or None")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")


def _parse_optional_datetime(value: Any, *, field: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field} must be an ISO-8601 string or null")
    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"invalid {field}: {value}") from exc
    _require_aware_datetime(parsed, field=field)
    return parsed


def _format_optional_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    utc_value = value.astimezone(timezone.utc)
    rendered = utc_value.isoformat()
    return f"{rendered[:-6]}Z" if rendered.endswith("+00:00") else rendered


def _oldest_known_time(values: Iterable[datetime | None]) -> datetime | None:
    items = tuple(values)
    if any(value is None for value in items):
        return None
    return min(value for value in items if value is not None)


__all__ = [
    "SOURCE_OBSERVATION_FACTS_VERSION",
    "ObservationFreshness",
    "RawAvailability",
    "SourceClass",
    "SourceIdentity",
    "SourceObservationFacts",
    "merge_source_observations",
]
