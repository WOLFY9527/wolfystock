# -*- coding: utf-8 -*-
"""Backend-only observation cache DTOs and deterministic in-process cache."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import threading
from typing import Any, Callable, Mapping


OBSERVATION_CACHE_FRESHNESS_VALUES = frozenset({"fresh", "delayed", "stale", "unavailable"})
OBSERVATION_CACHE_SOURCE_TIER = "cached_observation"
OBSERVATION_CACHE_MISS_REASON = "observation_cache_miss"
OBSERVATION_CACHE_STALE_REASON = "observation_cache_stale"
OBSERVATION_CACHE_EXPIRED_REASON = "observation_cache_expired"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _required_text(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_iso8601(value: str | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include timezone information")
    return parsed


def _normalize_records(records: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]] | None) -> tuple[dict[str, Any], ...]:
    if not records:
        return ()
    return tuple(dict(record) for record in records)


def _normalize_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if metadata is None:
        return None
    return dict(metadata)


@dataclass(frozen=True, slots=True)
class CachedProviderObservationDTO:
    provider_id: str
    source: str
    capability: str
    source_tier: str
    trust_level: str
    freshness: str
    as_of: str | None
    updated_at: str
    stale_at: str
    expires_at: str
    observation_only: bool = True
    score_contribution_allowed: bool = False
    symbol: str | None = None
    product_id: str | None = None
    cik: str | None = None
    freshness_expectation: str | None = None
    degradation_reason: str | None = None
    missing_provider_reason: str | None = None
    records: tuple[Mapping[str, Any], ...] = ()
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _required_text(self.provider_id, "provider_id"))
        object.__setattr__(self, "source", _required_text(self.source, "source"))
        object.__setattr__(self, "capability", _required_text(self.capability, "capability"))
        object.__setattr__(self, "source_tier", _required_text(self.source_tier, "source_tier"))
        object.__setattr__(self, "trust_level", _required_text(self.trust_level, "trust_level"))
        object.__setattr__(self, "freshness", self._coerce_freshness(self.freshness))
        object.__setattr__(self, "as_of", _optional_text(self.as_of))
        object.__setattr__(self, "updated_at", _required_text(self.updated_at, "updated_at"))
        object.__setattr__(self, "stale_at", _required_text(self.stale_at, "stale_at"))
        object.__setattr__(self, "expires_at", _required_text(self.expires_at, "expires_at"))
        object.__setattr__(self, "symbol", _optional_text(self.symbol))
        object.__setattr__(self, "product_id", _optional_text(self.product_id))
        object.__setattr__(self, "cik", _optional_text(self.cik))
        object.__setattr__(self, "freshness_expectation", _optional_text(self.freshness_expectation))
        object.__setattr__(self, "degradation_reason", _optional_text(self.degradation_reason))
        object.__setattr__(self, "missing_provider_reason", _optional_text(self.missing_provider_reason))
        object.__setattr__(self, "records", _normalize_records(self.records))
        object.__setattr__(self, "metadata", _normalize_metadata(self.metadata))
        object.__setattr__(self, "observation_only", True)
        object.__setattr__(self, "score_contribution_allowed", False)

        updated_at = _parse_iso8601(self.updated_at, "updated_at")
        stale_at = _parse_iso8601(self.stale_at, "stale_at")
        expires_at = _parse_iso8601(self.expires_at, "expires_at")
        as_of = _parse_iso8601(self.as_of, "as_of")
        if as_of is not None and updated_at is not None and as_of > updated_at:
            raise ValueError("as_of cannot be after updated_at")
        if updated_at is not None and stale_at is not None and updated_at > stale_at:
            raise ValueError("updated_at cannot be after stale_at")
        if stale_at is not None and expires_at is not None and stale_at > expires_at:
            raise ValueError("stale_at cannot be after expires_at")

    @staticmethod
    def _coerce_freshness(value: str) -> str:
        freshness = _required_text(value, "freshness")
        if freshness not in OBSERVATION_CACHE_FRESHNESS_VALUES:
            raise ValueError(
                f"freshness must be one of {sorted(OBSERVATION_CACHE_FRESHNESS_VALUES)}"
            )
        return freshness

    @property
    def cache_key(self) -> str:
        return ObservationCache.build_key(
            provider_id=self.provider_id,
            capability=self.capability,
            symbol=self.symbol,
            product_id=self.product_id,
            cik=self.cik,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "providerId": self.provider_id,
            "source": self.source,
            "capability": self.capability,
            "symbol": self.symbol,
            "productId": self.product_id,
            "cik": self.cik,
            "sourceTier": self.source_tier,
            "trustLevel": self.trust_level,
            "freshness": self.freshness,
            "freshnessExpectation": self.freshness_expectation,
            "observationOnly": True,
            "scoreContributionAllowed": False,
            "asOf": self.as_of,
            "updatedAt": self.updated_at,
            "staleAt": self.stale_at,
            "expiresAt": self.expires_at,
            "degradationReason": self.degradation_reason,
            "missingProviderReason": self.missing_provider_reason,
            "records": [dict(record) for record in self.records],
        }
        if self.metadata is not None:
            payload["metadata"] = dict(self.metadata)
        return payload

    @classmethod
    def unavailable(
        cls,
        *,
        provider_id: str,
        source: str | None = None,
        capability: str,
        source_tier: str = OBSERVATION_CACHE_SOURCE_TIER,
        trust_level: str = "unavailable",
        symbol: str | None = None,
        product_id: str | None = None,
        cik: str | None = None,
        freshness_expectation: str | None = None,
        as_of: str | None = None,
        updated_at: str | None = None,
        stale_at: str | None = None,
        expires_at: str | None = None,
        degradation_reason: str | None = None,
        missing_provider_reason: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "CachedProviderObservationDTO":
        now = _utcnow().isoformat()
        return cls(
            provider_id=provider_id,
            source=source or provider_id,
            capability=capability,
            symbol=symbol,
            product_id=product_id,
            cik=cik,
            source_tier=source_tier,
            trust_level=trust_level,
            freshness="unavailable",
            freshness_expectation=freshness_expectation,
            as_of=as_of,
            updated_at=updated_at or now,
            stale_at=stale_at or now,
            expires_at=expires_at or now,
            degradation_reason=degradation_reason,
            missing_provider_reason=missing_provider_reason,
            records=(),
            metadata=metadata,
        )

    def as_stale(self, *, degradation_reason: str) -> "CachedProviderObservationDTO":
        if self.freshness == "unavailable":
            return self
        return replace(
            self,
            freshness="stale",
            degradation_reason=degradation_reason,
            missing_provider_reason=None,
        )

    def as_unavailable(
        self,
        *,
        degradation_reason: str,
        missing_provider_reason: str,
        now: datetime,
    ) -> "CachedProviderObservationDTO":
        now_iso = now.isoformat()
        return replace(
            self,
            trust_level="unavailable",
            freshness="unavailable",
            updated_at=now_iso,
            stale_at=now_iso,
            expires_at=now_iso,
            degradation_reason=degradation_reason,
            missing_provider_reason=missing_provider_reason,
            records=(),
        )


class ObservationCache:
    """Small deterministic in-process cache for provider observation DTOs."""

    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._entries: dict[str, CachedProviderObservationDTO] = {}
        self._lock = threading.RLock()
        self._now = now or _utcnow

    @staticmethod
    def build_key(
        *,
        provider_id: str,
        capability: str,
        symbol: str | None = None,
        product_id: str | None = None,
        cik: str | None = None,
    ) -> str:
        return (
            f"providerId={_required_text(provider_id, 'provider_id')}|"
            f"capability={_required_text(capability, 'capability')}|"
            f"symbol={_optional_text(symbol) or ''}|"
            f"productId={_optional_text(product_id) or ''}|"
            f"cik={_optional_text(cik) or ''}"
        )

    def set(self, observation: CachedProviderObservationDTO) -> CachedProviderObservationDTO:
        with self._lock:
            self._entries[observation.cache_key] = observation
        return observation

    def get(
        self,
        *,
        provider_id: str,
        capability: str,
        symbol: str | None = None,
        product_id: str | None = None,
        cik: str | None = None,
        serve_stale_if_expired: bool = False,
    ) -> CachedProviderObservationDTO:
        return self.get_by_key(
            self.build_key(
                provider_id=provider_id,
                capability=capability,
                symbol=symbol,
                product_id=product_id,
                cik=cik,
            ),
            serve_stale_if_expired=serve_stale_if_expired,
        )

    def get_by_key(
        self,
        key: str,
        *,
        serve_stale_if_expired: bool = False,
    ) -> CachedProviderObservationDTO:
        with self._lock:
            cached = self._entries.get(key)

        now = self._now()
        if cached is None:
            return self._missing_from_key(key, now=now, reason=OBSERVATION_CACHE_MISS_REASON)

        stale_at = _parse_iso8601(cached.stale_at, "stale_at")
        expires_at = _parse_iso8601(cached.expires_at, "expires_at")
        if expires_at is not None and now >= expires_at:
            if serve_stale_if_expired:
                return cached.as_stale(degradation_reason=OBSERVATION_CACHE_EXPIRED_REASON)
            return cached.as_unavailable(
                degradation_reason=OBSERVATION_CACHE_EXPIRED_REASON,
                missing_provider_reason=OBSERVATION_CACHE_EXPIRED_REASON,
                now=now,
            )
        if stale_at is not None and now >= stale_at:
            return cached.as_stale(degradation_reason=OBSERVATION_CACHE_STALE_REASON)
        return cached

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def reset(self) -> None:
        self.clear()

    @staticmethod
    def _missing_from_key(
        key: str,
        *,
        now: datetime,
        reason: str,
    ) -> CachedProviderObservationDTO:
        parsed = ObservationCache._parse_key(key)
        now_iso = now.isoformat()
        return CachedProviderObservationDTO.unavailable(
            provider_id=parsed["provider_id"],
            source=parsed["provider_id"],
            capability=parsed["capability"],
            symbol=parsed["symbol"],
            product_id=parsed["product_id"],
            cik=parsed["cik"],
            source_tier=OBSERVATION_CACHE_SOURCE_TIER,
            trust_level="unavailable",
            updated_at=now_iso,
            stale_at=now_iso,
            expires_at=now_iso,
            degradation_reason=reason,
            missing_provider_reason=reason,
        )

    @staticmethod
    def _parse_key(key: str) -> dict[str, str | None]:
        values: dict[str, str | None] = {
            "provider_id": None,
            "capability": None,
            "symbol": None,
            "product_id": None,
            "cik": None,
        }
        for part in key.split("|"):
            name, _, value = part.partition("=")
            if name == "providerId":
                values["provider_id"] = value or None
            elif name == "capability":
                values["capability"] = value or None
            elif name == "symbol":
                values["symbol"] = value or None
            elif name == "productId":
                values["product_id"] = value or None
            elif name == "cik":
                values["cik"] = value or None
        values["provider_id"] = _required_text(values["provider_id"] or "", "provider_id")
        values["capability"] = _required_text(values["capability"] or "", "capability")
        return values
