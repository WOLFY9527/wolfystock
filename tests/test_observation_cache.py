# -*- coding: utf-8 -*-
"""Offline contracts for the backend-only observation cache foundation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.services.observation_cache import (
    OBSERVATION_CACHE_FRESHNESS_VALUES,
    CachedProviderObservationDTO,
    ObservationCache,
)


UTC = timezone.utc


def _iso(minutes: int) -> str:
    base = datetime(2026, 5, 20, 0, 0, tzinfo=UTC)
    return (base + timedelta(minutes=minutes)).isoformat()


def _dto(
    *,
    freshness: str = "fresh",
    stale_at: str | None = None,
    expires_at: str | None = None,
    records: tuple[dict[str, object], ...] = ({"value": 1},),
) -> CachedProviderObservationDTO:
    return CachedProviderObservationDTO(
        provider_id="sec_edgar",
        source="sec_edgar",
        capability="companyfacts",
        cik="0000320193",
        source_tier="official_public",
        trust_level="reliable_for_filings_metadata",
        freshness=freshness,
        freshness_expectation="filing_or_daily",
        as_of=_iso(0),
        updated_at=_iso(1),
        stale_at=stale_at or _iso(10),
        expires_at=expires_at or _iso(20),
        degradation_reason=None,
        missing_provider_reason=None,
        records=records,
        metadata={"projection": "evidence_only"},
    )


def test_observation_cache_dto_enforces_inert_flags_and_defaults() -> None:
    dto = CachedProviderObservationDTO(
        provider_id="coinbase_public",
        source="coinbase_public",
        capability="venue_observation",
        product_id="BTC-USD",
        source_tier="exchange_public",
        trust_level="usable_with_caution",
        freshness="delayed",
        as_of=_iso(0),
        updated_at=_iso(1),
        stale_at=_iso(10),
        expires_at=_iso(20),
        observation_only=False,
        score_contribution_allowed=True,
    )

    assert OBSERVATION_CACHE_FRESHNESS_VALUES == frozenset(
        {"fresh", "delayed", "stale", "unavailable"}
    )
    assert dto.observation_only is True
    assert dto.score_contribution_allowed is False
    assert dto.records == ()
    assert dto.to_dict() == {
        "providerId": "coinbase_public",
        "source": "coinbase_public",
        "capability": "venue_observation",
        "symbol": None,
        "productId": "BTC-USD",
        "cik": None,
        "sourceTier": "exchange_public",
        "trustLevel": "usable_with_caution",
        "freshness": "delayed",
        "freshnessExpectation": None,
        "observationOnly": True,
        "scoreContributionAllowed": False,
        "asOf": _iso(0),
        "updatedAt": _iso(1),
        "staleAt": _iso(10),
        "expiresAt": _iso(20),
        "degradationReason": None,
        "missingProviderReason": None,
        "records": [],
    }


def test_observation_cache_builds_stable_keys_from_provider_capability_and_identifiers() -> None:
    key = ObservationCache.build_key(
        provider_id="coinbase_public",
        capability="venue_observation",
        product_id="BTC-USD",
    )

    assert key == (
        "providerId=coinbase_public|capability=venue_observation|"
        "symbol=|productId=BTC-USD|cik="
    )

    dto = CachedProviderObservationDTO(
        provider_id="coinbase_public",
        source="coinbase_public",
        capability="venue_observation",
        product_id="BTC-USD",
        source_tier="exchange_public",
        trust_level="usable_with_caution",
        freshness="delayed",
        as_of=_iso(0),
        updated_at=_iso(1),
        stale_at=_iso(10),
        expires_at=_iso(20),
    )

    assert dto.cache_key == key


def test_observation_cache_returns_missing_unavailable_metadata_for_absent_keys() -> None:
    cache = ObservationCache(now=lambda: datetime.fromisoformat(_iso(5)))

    missing = cache.get(
        provider_id="baostock",
        capability="cn_history_daily",
        symbol="000001.SZ",
    )

    assert missing.provider_id == "baostock"
    assert missing.capability == "cn_history_daily"
    assert missing.symbol == "000001.SZ"
    assert missing.source == "baostock"
    assert missing.freshness == "unavailable"
    assert missing.trust_level == "unavailable"
    assert missing.degradation_reason == "observation_cache_miss"
    assert missing.missing_provider_reason == "observation_cache_miss"
    assert missing.records == ()
    assert missing.observation_only is True
    assert missing.score_contribution_allowed is False


def test_observation_cache_preserves_available_freshness_before_stale_boundary() -> None:
    cache = ObservationCache(now=lambda: datetime.fromisoformat(_iso(5)))
    dto = _dto(freshness="delayed")

    cache.set(dto)
    cached = cache.get_by_key(dto.cache_key)

    assert cached.freshness == "delayed"
    assert cached.records == ({"value": 1},)
    assert cached.degradation_reason is None


def test_observation_cache_returns_stale_dto_without_throwing_after_stale_boundary() -> None:
    cache = ObservationCache(now=lambda: datetime.fromisoformat(_iso(12)))
    dto = _dto(freshness="fresh")

    cache.set(dto)
    stale = cache.get_by_key(dto.cache_key)

    assert stale.freshness == "stale"
    assert stale.records == ({"value": 1},)
    assert stale.degradation_reason == "observation_cache_stale"
    assert stale.missing_provider_reason is None


def test_observation_cache_returns_unavailable_for_expired_entries_by_default() -> None:
    cache = ObservationCache(now=lambda: datetime.fromisoformat(_iso(25)))
    dto = _dto(freshness="fresh")

    cache.set(dto)
    expired = cache.get_by_key(dto.cache_key)

    assert expired.provider_id == "sec_edgar"
    assert expired.source == "sec_edgar"
    assert expired.freshness == "unavailable"
    assert expired.trust_level == "unavailable"
    assert expired.records == ()
    assert expired.degradation_reason == "observation_cache_expired"
    assert expired.missing_provider_reason == "observation_cache_expired"


def test_observation_cache_can_explicitly_serve_expired_entries_as_stale() -> None:
    cache = ObservationCache(now=lambda: datetime.fromisoformat(_iso(25)))
    dto = _dto(freshness="delayed")

    cache.set(dto)
    stale = cache.get_by_key(dto.cache_key, serve_stale_if_expired=True)

    assert stale.freshness == "stale"
    assert stale.trust_level == "reliable_for_filings_metadata"
    assert stale.records == ({"value": 1},)
    assert stale.degradation_reason == "observation_cache_expired"
    assert stale.missing_provider_reason is None


def test_observation_cache_clear_and_reset_drop_entries_for_tests() -> None:
    cache = ObservationCache(now=lambda: datetime.fromisoformat(_iso(5)))
    dto = _dto()

    cache.set(dto)
    assert cache.get_by_key(dto.cache_key).freshness == "fresh"

    cache.clear()
    assert cache.get_by_key(dto.cache_key).freshness == "unavailable"

    cache.set(dto)
    cache.reset()
    assert cache.get_by_key(dto.cache_key).freshness == "unavailable"
