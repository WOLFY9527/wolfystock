from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


QUOTE_SNAPSHOT_READINESS_CONTRACT_VERSION = "quote_snapshot_readiness_v1"
DEFAULT_QUOTE_SNAPSHOT_MAX_AGE_SECONDS = 60 * 60 * 24
_PROVIDER_MISSING = "provider_missing"
_PROVIDER_UNAVAILABLE = "provider_unavailable"
_STALE_DATA = "stale_data"


@dataclass(frozen=True)
class QuoteSnapshot:
    symbol: str
    market: str
    last: float
    as_of: datetime
    previous_close: float | None = None
    volume: float | None = None
    currency: str | None = None
    source: str = "unknown"

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "symbol": _safe_symbol(self.symbol),
            "market": _safe_market(self.market),
            "last": float(self.last),
            "asOf": _iso_datetime(self.as_of),
            "source": _safe_source(self.source),
        }
        if self.previous_close is not None:
            payload["previousClose"] = float(self.previous_close)
        if self.volume is not None:
            payload["volume"] = float(self.volume)
        if self.currency:
            payload["currency"] = str(self.currency).strip().upper()[:8]
        return payload


@dataclass(frozen=True)
class QuoteSnapshotProviderResult:
    snapshots: tuple[QuoteSnapshot, ...] = ()
    unavailable_reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def available(
        cls,
        snapshots: Sequence[QuoteSnapshot],
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> "QuoteSnapshotProviderResult":
        return cls(snapshots=tuple(snapshots), metadata=dict(metadata or {}))

    @classmethod
    def unavailable(cls, reason: str) -> "QuoteSnapshotProviderResult":
        return cls(unavailable_reason=_safe_code(reason) or _PROVIDER_UNAVAILABLE)


@dataclass(frozen=True)
class QuoteSnapshotReadinessRequest:
    symbols: tuple[str, ...]
    market: str = "unknown"
    max_age_seconds: int = DEFAULT_QUOTE_SNAPSHOT_MAX_AGE_SECONDS


class QuoteSnapshotProvider(Protocol):
    def fetch_quote_snapshots(
        self,
        request: QuoteSnapshotReadinessRequest,
    ) -> QuoteSnapshotProviderResult:
        ...


@dataclass(frozen=True)
class QuoteSnapshotAcquisitionResult:
    snapshots: list[QuoteSnapshot]
    readiness: dict[str, Any]
    unavailable_reason: str | None = None


class QuoteSnapshotReadinessService:
    """Provider-neutral quote snapshot readiness seam.

    The service does not know how to fetch live data. It only asks an injected
    provider/cache reader and returns a sanitized readiness contract.
    """

    def __init__(self, provider: QuoteSnapshotProvider | None = None) -> None:
        self.provider = provider

    def fetch(self, request: QuoteSnapshotReadinessRequest) -> QuoteSnapshotAcquisitionResult:
        normalized_request = _normalize_request(request)
        if self.provider is None:
            return self._from_provider_result(
                normalized_request,
                QuoteSnapshotProviderResult.unavailable(_PROVIDER_MISSING),
            )

        try:
            provider_result = self.provider.fetch_quote_snapshots(normalized_request)
        except Exception:
            provider_result = QuoteSnapshotProviderResult.unavailable(_PROVIDER_UNAVAILABLE)
        return self._from_provider_result(normalized_request, provider_result)

    def _from_provider_result(
        self,
        request: QuoteSnapshotReadinessRequest,
        provider_result: QuoteSnapshotProviderResult,
    ) -> QuoteSnapshotAcquisitionResult:
        requested_symbols = list(request.symbols)
        by_symbol = {_safe_symbol(snapshot.symbol): snapshot for snapshot in provider_result.snapshots}
        now = datetime.now(timezone.utc)
        available_symbols: list[str] = []
        stale_symbols: list[str] = []
        snapshots: list[QuoteSnapshot] = []
        source_families: list[str] = []

        for symbol in requested_symbols:
            snapshot = by_symbol.get(symbol)
            if snapshot is None:
                continue
            if not _snapshot_has_real_price(snapshot):
                continue
            source = _safe_source(snapshot.source)
            if source and source not in source_families:
                source_families.append(source)
            if _is_stale(snapshot.as_of, now=now, max_age_seconds=request.max_age_seconds):
                stale_symbols.append(symbol)
                continue
            available_symbols.append(symbol)
            snapshots.append(snapshot)

        missing_symbols = [
            symbol
            for symbol in requested_symbols
            if symbol not in available_symbols and symbol not in stale_symbols
        ]
        if provider_result.unavailable_reason and not available_symbols and not stale_symbols:
            provider_state = _safe_code(provider_result.unavailable_reason) or _PROVIDER_UNAVAILABLE
        elif available_symbols or stale_symbols:
            provider_state = "available"
        else:
            provider_state = _PROVIDER_MISSING

        if stale_symbols and not available_symbols and not missing_symbols:
            availability = "stale"
            freshness = "stale"
            missing_requirements = [_STALE_DATA]
        elif available_symbols and not missing_symbols and not stale_symbols:
            availability = "available"
            freshness = "available"
            missing_requirements = []
        elif available_symbols or stale_symbols:
            availability = "partial"
            freshness = "partial" if available_symbols else "stale"
            missing_requirements = ["quote_snapshot"]
            if stale_symbols:
                missing_requirements.append(_STALE_DATA)
        else:
            availability = "missing"
            freshness = "missing"
            missing_requirements = ["quote_snapshot"]

        readiness = {
            "contractVersion": QUOTE_SNAPSHOT_READINESS_CONTRACT_VERSION,
            "market": _safe_market(request.market),
            "requestedSymbols": requested_symbols,
            "availableSymbols": available_symbols,
            "missingSymbols": missing_symbols,
            "staleSymbols": stale_symbols,
            "sourceFamilies": source_families,
            "availabilityState": availability,
            "freshnessState": freshness,
            "providerState": provider_state,
            "missingRequirements": missing_requirements,
            "consumerSafe": True,
        }
        return QuoteSnapshotAcquisitionResult(
            snapshots=snapshots,
            readiness=readiness,
            unavailable_reason=provider_result.unavailable_reason,
        )


def _normalize_request(request: QuoteSnapshotReadinessRequest) -> QuoteSnapshotReadinessRequest:
    symbols: list[str] = []
    for symbol in request.symbols:
        normalized = _safe_symbol(symbol)
        if normalized and normalized not in symbols:
            symbols.append(normalized)
    return QuoteSnapshotReadinessRequest(
        symbols=tuple(symbols),
        market=_safe_market(request.market),
        max_age_seconds=max(1, int(request.max_age_seconds or DEFAULT_QUOTE_SNAPSHOT_MAX_AGE_SECONDS)),
    )


def _safe_symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def _safe_market(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in {"us", "cn", "hk"} else "unknown"


def _safe_code(value: Any) -> str:
    text = str(value or "").strip().lower()
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in text)[:64]


def _safe_source(value: Any) -> str:
    text = str(value or "").strip().lower()
    sanitized = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in text)
    return sanitized[:64] or "unknown"


def _iso_datetime(value: datetime) -> str:
    dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _snapshot_has_real_price(snapshot: QuoteSnapshot) -> bool:
    try:
        return float(snapshot.last) > 0
    except Exception:
        return False


def _is_stale(value: datetime, *, now: datetime, max_age_seconds: int) -> bool:
    dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return (now - dt.astimezone(timezone.utc)).total_seconds() > max_age_seconds


__all__ = [
    "DEFAULT_QUOTE_SNAPSHOT_MAX_AGE_SECONDS",
    "QUOTE_SNAPSHOT_READINESS_CONTRACT_VERSION",
    "QuoteSnapshot",
    "QuoteSnapshotAcquisitionResult",
    "QuoteSnapshotProvider",
    "QuoteSnapshotProviderResult",
    "QuoteSnapshotReadinessRequest",
    "QuoteSnapshotReadinessService",
]
