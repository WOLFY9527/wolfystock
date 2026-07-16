# -*- coding: utf-8 -*-
"""Append-only persistence evidence snapshot contract and pure reader helpers.

This module is deliberately inert. It defines a backend-only DTO, in-memory
append-only reader, de-duplication, window selection, and conversion into the
T-224H persistence evidence classifier without provider, cache, DB, API, or
frontend wiring.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable, Mapping

from src.services.market_persistence_evidence_service import MarketPersistenceEvidenceSnapshot


MARKET_PERSISTENCE_SNAPSHOT_SCHEMA_VERSION = "market_persistence_snapshot_v1"
MARKET_PERSISTENCE_SNAPSHOT_ALGORITHM_VERSION = "snapshot_window_v1"
PERSISTENCE_SNAPSHOT_WINDOWS: tuple[str, ...] = ("latest", "1d", "5d", "20d")

_WINDOW_TARGET_DAYS = {
    "latest": 0.0,
    "1d": 1.0,
    "5d": 5.0,
    "20d": 20.0,
}

_EXCLUDED_MARKERS = (
    "fallback",
    "mock",
    "static",
    "synthetic",
    "taxonomy",
    "unavailable",
    "missing",
)

_SECRET_OR_RAW_KEYS = (
    "rawpayload",
    "rawproviderpayload",
    "providerpayload",
    "secret",
    "token",
    "password",
    "credential",
    "apikey",
    "api_key",
)


@dataclass(frozen=True, slots=True)
class MarketPersistenceSnapshotDTO:
    snapshot_id: str
    surface: str
    metric_key: str
    value: float | str | None
    score: float | None
    state_label: str | None
    regime_label: str | None
    signal_label: str | None
    source: str
    source_type: str
    source_tier: str
    trust_level: str
    freshness: str
    observation_only: bool
    score_contribution_allowed: bool
    as_of: str | None
    updated_at: str | None
    snapshot_created_at: str
    degradation_reason: str | None
    missing_provider_reason: str | None
    is_fallback: bool
    is_stale: bool
    is_partial: bool
    is_unavailable: bool
    provider_id: str | None
    capability: str | None
    payload_hash: str
    input_hash: str
    schema_version: str
    algorithm_version: str
    taxonomy_only: bool = False

    @staticmethod
    def evidence_snapshot_type() -> type[MarketPersistenceEvidenceSnapshot]:
        return MarketPersistenceEvidenceSnapshot

    @property
    def effective_timestamp(self) -> datetime | None:
        return _parse_datetime(self.as_of)

    @property
    def created_timestamp(self) -> datetime | None:
        return _parse_datetime(self.snapshot_created_at)

    @property
    def is_excluded_from_trend_authority(self) -> bool:
        if self.effective_timestamp is None:
            return True
        if self.observation_only or not self.score_contribution_allowed:
            return True
        if self.is_fallback or self.is_unavailable or self.taxonomy_only:
            return True
        text = " ".join(
            _text(value).lower()
            for value in (
                self.source,
                self.source_type,
                self.source_tier,
                self.freshness,
                self.capability,
                self.degradation_reason,
                self.missing_provider_reason,
            )
        )
        return any(marker in text for marker in _EXCLUDED_MARKERS)

    @property
    def is_degraded_context(self) -> bool:
        if self.is_excluded_from_trend_authority:
            return False
        text = " ".join(
            _text(value).lower()
            for value in (
                self.freshness,
                self.trust_level,
                self.degradation_reason,
                self.missing_provider_reason,
            )
        )
        return self.is_stale or self.is_partial or "stale" in text or "degraded" in text or "partial" in text

    @property
    def score_grade_eligible(self) -> bool:
        return not self.is_excluded_from_trend_authority and not self.is_degraded_context

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshotId": self.snapshot_id,
            "surface": self.surface,
            "metricKey": self.metric_key,
            "value": self.value,
            "score": self.score,
            "stateLabel": self.state_label,
            "regimeLabel": self.regime_label,
            "signalLabel": self.signal_label,
            "source": self.source,
            "sourceType": self.source_type,
            "sourceTier": self.source_tier,
            "trustLevel": self.trust_level,
            "freshness": self.freshness,
            "observationOnly": self.observation_only,
            "scoreContributionAllowed": self.score_contribution_allowed,
            "asOf": self.as_of,
            "updatedAt": self.updated_at,
            "snapshotCreatedAt": self.snapshot_created_at,
            "degradationReason": self.degradation_reason,
            "missingProviderReason": self.missing_provider_reason,
            "isFallback": self.is_fallback,
            "isStale": self.is_stale,
            "isPartial": self.is_partial,
            "isUnavailable": self.is_unavailable,
            "providerId": self.provider_id,
            "capability": self.capability,
            "payloadHash": self.payload_hash,
            "inputHash": self.input_hash,
            "schemaVersion": self.schema_version,
            "algorithmVersion": self.algorithm_version,
            "taxonomyOnly": self.taxonomy_only,
        }

    def to_persistence_evidence_snapshot(self) -> MarketPersistenceEvidenceSnapshot:
        return MarketPersistenceEvidenceSnapshot(
            key=f"{self.surface}:{self.metric_key}",
            surface=self.surface,
            metric=self.metric_key,
            value=self.value,
            score=self.score,
            regime_label=self.regime_label,
            state_label=self.state_label,
            signal_label=self.signal_label,
            as_of=self.as_of,
            updated_at=self.updated_at,
            source=self.source,
            source_tier=self.source_tier,
            trust_level=self.trust_level,
            freshness=self.freshness,
            observation_only=self.observation_only,
            score_contribution_allowed=self.score_contribution_allowed,
            degradation_reason=self.degradation_reason,
        )


@dataclass(frozen=True, slots=True)
class MarketPersistenceSnapshotWindow:
    window: str
    snapshot: MarketPersistenceSnapshotDTO
    bucket_key: str
    authority_level: str


class InMemoryMarketPersistenceSnapshotStore:
    """Pure append-only in-memory reader for normalized persistence snapshots."""

    def __init__(self, snapshots: Iterable[MarketPersistenceSnapshotDTO | Mapping[str, Any]] | None = None) -> None:
        self._snapshots: list[MarketPersistenceSnapshotDTO] = []
        self._by_payload_hash: dict[str, MarketPersistenceSnapshotDTO] = {}
        self.deduplicated_count = 0
        if snapshots:
            self.append_many(snapshots)

    def append(self, snapshot: MarketPersistenceSnapshotDTO | Mapping[str, Any]) -> MarketPersistenceSnapshotDTO:
        normalized = normalize_persistence_snapshot(snapshot)
        existing = self._by_payload_hash.get(normalized.payload_hash)
        if existing is not None:
            self.deduplicated_count += 1
            return existing
        self._snapshots.append(normalized)
        self._by_payload_hash[normalized.payload_hash] = normalized
        return normalized

    def append_many(
        self,
        snapshots: Iterable[MarketPersistenceSnapshotDTO | Mapping[str, Any]],
    ) -> tuple[MarketPersistenceSnapshotDTO, ...]:
        return tuple(self.append(snapshot) for snapshot in snapshots)

    def all_snapshots(self) -> tuple[MarketPersistenceSnapshotDTO, ...]:
        return tuple(self._snapshots)

    def select_windows(self, *, include_degraded_context: bool = True) -> tuple[MarketPersistenceSnapshotWindow, ...]:
        return select_persistence_snapshot_windows(
            self._snapshots,
            include_degraded_context=include_degraded_context,
        )


def normalize_persistence_snapshot(
    value: MarketPersistenceSnapshotDTO | Mapping[str, Any],
) -> MarketPersistenceSnapshotDTO:
    if isinstance(value, MarketPersistenceSnapshotDTO):
        return value
    sanitized = _sanitize_mapping(value)
    snapshot_created_at = _optional_text(_get(sanitized, "snapshot_created_at", "snapshotCreatedAt"))
    updated_at = _optional_text(_get(sanitized, "updated_at", "updatedAt"))
    as_of = _optional_text(_get(sanitized, "as_of", "asOf"))
    snapshot_created_at = snapshot_created_at or updated_at or as_of or _EPOCH
    source = _text(_get(sanitized, "source"))
    provider_id = _optional_text(_get(sanitized, "provider_id", "providerId"))
    safe_fields = {
        "surface": _text(_get(sanitized, "surface")) or "generic",
        "metricKey": _text(_get(sanitized, "metric_key", "metricKey", "metric")) or "metric",
        "value": _get(sanitized, "value"),
        "score": _optional_float(_get(sanitized, "score")),
        "stateLabel": _optional_text(_get(sanitized, "state_label", "stateLabel", "state")),
        "regimeLabel": _optional_text(_get(sanitized, "regime_label", "regimeLabel", "regime")),
        "signalLabel": _optional_text(_get(sanitized, "signal_label", "signalLabel", "signal")),
        "source": source,
        "sourceType": _text(_get(sanitized, "source_type", "sourceType")),
        "sourceTier": _text(_get(sanitized, "source_tier", "sourceTier")),
        "trustLevel": _text(_get(sanitized, "trust_level", "trustLevel")) or "unknown",
        "freshness": _text(_get(sanitized, "freshness")) or "unknown",
        "observationOnly": _bool(_get(sanitized, "observation_only", "observationOnly")),
        "scoreContributionAllowed": _bool(
            _get(sanitized, "score_contribution_allowed", "scoreContributionAllowed", default=True)
        ),
        "asOf": as_of,
        "updatedAt": updated_at,
        "snapshotCreatedAt": snapshot_created_at,
        "degradationReason": _optional_text(_get(sanitized, "degradation_reason", "degradationReason")),
        "missingProviderReason": _optional_text(_get(sanitized, "missing_provider_reason", "missingProviderReason")),
        "isFallback": _bool(_get(sanitized, "is_fallback", "isFallback")),
        "isStale": _bool(_get(sanitized, "is_stale", "isStale")),
        "isPartial": _bool(_get(sanitized, "is_partial", "isPartial")),
        "isUnavailable": _bool(_get(sanitized, "is_unavailable", "isUnavailable")),
        "providerId": provider_id,
        "capability": _optional_text(_get(sanitized, "capability")),
        "schemaVersion": _text(_get(sanitized, "schema_version", "schemaVersion"))
        or MARKET_PERSISTENCE_SNAPSHOT_SCHEMA_VERSION,
        "algorithmVersion": _text(_get(sanitized, "algorithm_version", "algorithmVersion"))
        or MARKET_PERSISTENCE_SNAPSHOT_ALGORITHM_VERSION,
        "taxonomyOnly": _bool(_get(sanitized, "taxonomy_only", "taxonomyOnly")),
    }
    payload_hash = _stable_hash(safe_fields)
    snapshot_id = _optional_text(_get(sanitized, "snapshot_id", "snapshotId")) or f"mps_{payload_hash[:24]}"
    return MarketPersistenceSnapshotDTO(
        snapshot_id=snapshot_id,
        surface=str(safe_fields["surface"]),
        metric_key=str(safe_fields["metricKey"]),
        value=safe_fields["value"],
        score=_optional_float(safe_fields["score"]),
        state_label=_optional_text(safe_fields["stateLabel"]),
        regime_label=_optional_text(safe_fields["regimeLabel"]),
        signal_label=_optional_text(safe_fields["signalLabel"]),
        source=str(safe_fields["source"]),
        source_type=str(safe_fields["sourceType"]),
        source_tier=str(safe_fields["sourceTier"]),
        trust_level=str(safe_fields["trustLevel"]),
        freshness=str(safe_fields["freshness"]),
        observation_only=bool(safe_fields["observationOnly"]),
        score_contribution_allowed=bool(safe_fields["scoreContributionAllowed"]),
        as_of=as_of,
        updated_at=updated_at,
        snapshot_created_at=snapshot_created_at,
        degradation_reason=_optional_text(safe_fields["degradationReason"]),
        missing_provider_reason=_optional_text(safe_fields["missingProviderReason"]),
        is_fallback=bool(safe_fields["isFallback"]),
        is_stale=bool(safe_fields["isStale"]),
        is_partial=bool(safe_fields["isPartial"]),
        is_unavailable=bool(safe_fields["isUnavailable"]),
        provider_id=provider_id,
        capability=_optional_text(safe_fields["capability"]),
        payload_hash=payload_hash,
        input_hash=_stable_hash({"sanitizedInput": safe_fields}),
        schema_version=str(safe_fields["schemaVersion"]),
        algorithm_version=str(safe_fields["algorithmVersion"]),
        taxonomy_only=bool(safe_fields["taxonomyOnly"]),
    )


def select_persistence_snapshot_windows(
    snapshots: Iterable[MarketPersistenceSnapshotDTO | Mapping[str, Any]],
    *,
    include_degraded_context: bool = True,
) -> tuple[MarketPersistenceSnapshotWindow, ...]:
    normalized = tuple(normalize_persistence_snapshot(snapshot) for snapshot in snapshots)
    candidates = tuple(
        snapshot
        for snapshot in normalized
        if snapshot.score_grade_eligible or (include_degraded_context and snapshot.is_degraded_context)
    )
    latest_timestamp = max((snapshot.effective_timestamp for snapshot in candidates if snapshot.effective_timestamp), default=None)
    if latest_timestamp is None:
        return ()

    chosen: dict[str, MarketPersistenceSnapshotWindow] = {}
    seen_buckets: set[str] = set()
    for snapshot in sorted(candidates, key=_selection_sort_key, reverse=True):
        bucket_key = _bucket_key(snapshot)
        if bucket_key in seen_buckets:
            continue
        seen_buckets.add(bucket_key)
        window = _window_name(snapshot.effective_timestamp, latest_timestamp)
        if window is None:
            continue
        window_snapshot = MarketPersistenceSnapshotWindow(
            window=window,
            snapshot=snapshot,
            bucket_key=bucket_key,
            authority_level="score_grade" if snapshot.score_grade_eligible else "degraded_context",
        )
        existing = chosen.get(window)
        if existing is None or _is_better_window_candidate(window_snapshot, existing, latest_timestamp):
            chosen[window] = window_snapshot

    return tuple(chosen[window] for window in PERSISTENCE_SNAPSHOT_WINDOWS if window in chosen)


def snapshots_to_persistence_evidence(
    snapshots: Iterable[MarketPersistenceSnapshotDTO | Mapping[str, Any]],
    *,
    include_degraded_context: bool = True,
) -> tuple[MarketPersistenceEvidenceSnapshot, ...]:
    windows = select_persistence_snapshot_windows(
        snapshots,
        include_degraded_context=include_degraded_context,
    )
    return tuple(window.snapshot.to_persistence_evidence_snapshot() for window in windows)


def _sanitize_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, item in value.items():
        normalized_key = str(key).replace("-", "_")
        if _is_secret_or_raw_key(normalized_key):
            continue
        sanitized[normalized_key] = item
    return sanitized


def _is_secret_or_raw_key(key: str) -> bool:
    normalized = key.replace("_", "").lower()
    return any(marker in normalized for marker in _SECRET_OR_RAW_KEYS)


def _selection_sort_key(snapshot: MarketPersistenceSnapshotDTO) -> tuple[datetime, datetime, str]:
    return (
        snapshot.effective_timestamp or _MIN_DATETIME,
        snapshot.created_timestamp or _MIN_DATETIME,
        snapshot.snapshot_id,
    )


def _is_better_window_candidate(
    candidate: MarketPersistenceSnapshotWindow,
    existing: MarketPersistenceSnapshotWindow,
    latest_timestamp: datetime,
) -> bool:
    candidate_distance = _window_distance(candidate.snapshot.effective_timestamp, latest_timestamp, candidate.window)
    existing_distance = _window_distance(existing.snapshot.effective_timestamp, latest_timestamp, existing.window)
    if candidate_distance != existing_distance:
        return candidate_distance < existing_distance
    candidate_created = candidate.snapshot.created_timestamp or _MIN_DATETIME
    existing_created = existing.snapshot.created_timestamp or _MIN_DATETIME
    return candidate_created > existing_created


def _bucket_key(snapshot: MarketPersistenceSnapshotDTO) -> str:
    timestamp = snapshot.as_of or "missing-observation"
    return f"{snapshot.surface}|{snapshot.metric_key}|{timestamp}"


def _window_name(timestamp: datetime | None, latest_timestamp: datetime | None) -> str | None:
    if timestamp is None or latest_timestamp is None:
        return None
    age_days = abs((latest_timestamp - timestamp).total_seconds()) / 86400.0
    closest = min(PERSISTENCE_SNAPSHOT_WINDOWS, key=lambda name: abs(age_days - _WINDOW_TARGET_DAYS[name]))
    tolerance = 0.35 if closest in {"latest", "1d"} else 1.25
    if abs(age_days - _WINDOW_TARGET_DAYS[closest]) <= tolerance:
        return closest
    return None


def _window_distance(timestamp: datetime | None, latest_timestamp: datetime, window: str) -> float:
    if timestamp is None:
        return float("inf")
    age_days = abs((latest_timestamp - timestamp).total_seconds()) / 86400.0
    return abs(age_days - _WINDOW_TARGET_DAYS[window])


def _stable_hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _get(value: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in value:
            return value[name]
    return default


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _optional_text(value: Any) -> str | None:
    text = _text(value)
    return text or None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_EPOCH = "1970-01-01T00:00:00+00:00"
_MIN_DATETIME = datetime.min.replace(tzinfo=timezone.utc)
