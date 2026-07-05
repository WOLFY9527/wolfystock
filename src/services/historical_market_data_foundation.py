from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Protocol

from src.core.trading_calendar import MARKET_EXCHANGE, MARKET_TIMEZONE
from src.utils.symbol_classification import is_bse_code, is_us_index_code, is_us_stock_code
from src.utils.symbol_normalization import normalize_stock_code


HISTORICAL_MARKET_DATA_NORMALIZATION_VERSION = "historical_market_data_foundation_v1"
HISTORICAL_MARKET_DATA_CONTRACT_VERSION = "historical_market_data_read_contract_v1"


@dataclass(frozen=True)
class CanonicalHistoricalBar:
    market: str
    venue: str
    canonical_symbol: str
    provider_symbol: str
    interval: str
    session_date: date
    timestamp: datetime | None
    timezone: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    adjustment_status: str = "unknown"
    adjustment_metadata: Mapping[str, Any] = field(default_factory=dict)
    currency: str | None = None
    provider: str = "unknown"
    source: str = "unknown"
    observed_at: datetime | None = None
    as_of: datetime | None = None
    ingestion_id: str = ""
    lineage_id: str = ""
    normalization_version: str = HISTORICAL_MARKET_DATA_NORMALIZATION_VERSION
    quality_state: str = "unchecked"
    quality_reason_codes: tuple[str, ...] = ()
    raw_identity: str = ""

    def natural_key(self) -> tuple[str, str, str, date, str, str]:
        return (
            self.market,
            self.canonical_symbol,
            self.interval,
            self.session_date,
            self.provider,
            self.adjustment_status,
        )

    def value_fingerprint(self) -> str:
        payload = {
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "currency": self.currency,
            "adjustmentMetadata": dict(self.adjustment_metadata or {}),
        }
        return _stable_hash(payload)

    def with_quality(self, outcome: "HistoricalBarQualityOutcome") -> "CanonicalHistoricalBar":
        return CanonicalHistoricalBar(
            market=self.market,
            venue=self.venue,
            canonical_symbol=self.canonical_symbol,
            provider_symbol=self.provider_symbol,
            interval=self.interval,
            session_date=self.session_date,
            timestamp=self.timestamp,
            timezone=self.timezone,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
            adjustment_status=self.adjustment_status,
            adjustment_metadata=dict(self.adjustment_metadata or {}),
            currency=self.currency,
            provider=self.provider,
            source=self.source,
            observed_at=self.observed_at,
            as_of=self.as_of,
            ingestion_id=self.ingestion_id,
            lineage_id=self.lineage_id,
            normalization_version=self.normalization_version,
            quality_state=outcome.state,
            quality_reason_codes=tuple(outcome.reason_codes),
            raw_identity=self.raw_identity,
        )

    def as_read_model(self) -> dict[str, Any]:
        return {
            "contractVersion": HISTORICAL_MARKET_DATA_CONTRACT_VERSION,
            "market": self.market,
            "venue": self.venue,
            "canonicalSymbol": self.canonical_symbol,
            "interval": self.interval,
            "sessionDate": self.session_date.isoformat(),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "timezone": self.timezone,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "adjustmentStatus": self.adjustment_status,
            "adjustmentMetadata": dict(self.adjustment_metadata or {}),
            "currency": self.currency,
            "provider": self.provider,
            "source": self.source,
            "observedAt": self.observed_at.isoformat() if self.observed_at else None,
            "asOf": self.as_of.isoformat() if self.as_of else None,
            "qualityState": self.quality_state,
            "qualityReasonCodes": list(self.quality_reason_codes),
            "normalizationVersion": self.normalization_version,
            "ingestionId": self.ingestion_id,
            "lineageId": self.lineage_id,
        }


@dataclass(frozen=True)
class HistoricalBarQualityOutcome:
    state: str
    reason_codes: list[str]
    product_readable: bool
    severity_by_reason: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def evaluate(cls, bars: Sequence[CanonicalHistoricalBar]) -> "HistoricalBarQualityOutcome":
        reasons: list[str] = []
        severities: dict[str, str] = {}

        def add(reason: str, severity: str) -> None:
            if reason not in reasons:
                reasons.append(reason)
            severities[reason] = severity

        if not bars:
            add("empty_bar_set", "reject")
        seen: dict[tuple[str, str, str, date, str, str], CanonicalHistoricalBar] = {}
        previous_date: date | None = None
        identity_fields = ("market", "canonical_symbol", "interval", "session_date", "timezone", "provider")
        for bar in bars:
            if any(not getattr(bar, field_name) for field_name in identity_fields):
                add("missing_required_identity", "reject")
            if bar.session_date == date.min:
                add("malformed_timestamp", "reject")
            if any(value < 0 for value in (bar.open, bar.high, bar.low, bar.close)):
                add("negative_price", "reject")
            if bar.volume < 0:
                add("negative_volume", "reject")
            if bar.high < max(bar.open, bar.low, bar.close) or bar.low > min(bar.open, bar.high, bar.close):
                add("invalid_ohlc_relationship", "reject")
            if bar.observed_at is None or bar.as_of is None:
                add("source_metadata_gap", "degrade")
            natural_key = bar.natural_key()
            if natural_key in seen:
                previous = seen[natural_key]
                if previous.value_fingerprint() != bar.value_fingerprint():
                    add("conflicting_duplicate_bar", "reject")
                else:
                    add("duplicate_bar", "degrade")
            else:
                seen[natural_key] = bar
            if previous_date is not None:
                if bar.session_date < previous_date:
                    add("non_monotonic_ordering", "reject")
                elif bar.interval == "1d" and _has_business_day_gap(previous_date, bar.session_date):
                    add("missing_session_gap", "degrade")
            previous_date = bar.session_date

        if any(severity == "reject" for severity in severities.values()):
            return cls(state="rejected", reason_codes=reasons, product_readable=False, severity_by_reason=severities)
        if reasons:
            return cls(state="degraded", reason_codes=reasons, product_readable=True, severity_by_reason=severities)
        return cls(state="usable", reason_codes=[], product_readable=True, severity_by_reason={})


@dataclass(frozen=True)
class HistoricalPersistenceResult:
    inserted: int = 0
    updated: int = 0
    duplicates: int = 0
    conflicts: int = 0
    rejected: int = 0


@dataclass(frozen=True)
class HistoricalIngestionResult:
    bars: tuple[CanonicalHistoricalBar, ...]
    quality: HistoricalBarQualityOutcome
    persisted: HistoricalPersistenceResult


class HistoricalMarketDataRepositoryProtocol(Protocol):
    def upsert_bars(
        self,
        bars: Sequence[CanonicalHistoricalBar],
        quality: HistoricalBarQualityOutcome,
    ) -> HistoricalPersistenceResult:
        ...

    def query_bars(
        self,
        *,
        symbol: str,
        market: str,
        interval: str,
        start: date,
        end: date,
    ) -> list[CanonicalHistoricalBar]:
        ...

    def latest_bar(self, *, symbol: str, market: str, interval: str) -> CanonicalHistoricalBar | None:
        ...


class HistoricalMarketDataFoundation:
    def __init__(self, repository: HistoricalMarketDataRepositoryProtocol) -> None:
        self.repository = repository

    def ingest_provider_payload(self, payload: Mapping[str, Any]) -> HistoricalIngestionResult:
        bars = normalize_provider_historical_bars(payload, preserve_provider_order=True)
        quality = HistoricalBarQualityOutcome.evaluate(bars)
        if quality.state == "rejected":
            persisted = self.repository.upsert_bars([], quality)
            if "conflicting_duplicate_bar" not in quality.reason_codes:
                conflicts = self.repository.upsert_bars(bars, quality).conflicts
                if conflicts:
                    persisted = HistoricalPersistenceResult(conflicts=conflicts)
            return HistoricalIngestionResult(bars=tuple(bar.with_quality(quality) for bar in bars), quality=quality, persisted=persisted)
        qualified = [bar.with_quality(quality) for bar in bars]
        persisted = self.repository.upsert_bars(qualified, quality)
        if persisted.conflicts:
            quality = HistoricalBarQualityOutcome(
                state="rejected",
                reason_codes=["repository_conflict"],
                product_readable=False,
                severity_by_reason={"repository_conflict": "reject"},
            )
        return HistoricalIngestionResult(bars=tuple(qualified), quality=quality, persisted=persisted)

    def query_bars(
        self,
        *,
        symbol: str,
        market: str,
        interval: str,
        start: date,
        end: date,
    ) -> list[CanonicalHistoricalBar]:
        identity = resolve_historical_symbol_identity(symbol=symbol, market=market)
        return self.repository.query_bars(
            symbol=identity["canonical_symbol"],
            market=identity["market"],
            interval=_normalize_interval(interval),
            start=start,
            end=end,
        )

    def latest_bar(self, *, symbol: str, market: str, interval: str) -> CanonicalHistoricalBar | None:
        identity = resolve_historical_symbol_identity(symbol=symbol, market=market)
        return self.repository.latest_bar(
            symbol=identity["canonical_symbol"],
            market=identity["market"],
            interval=_normalize_interval(interval),
        )

    def coverage_range(self, *, symbol: str, market: str, interval: str) -> dict[str, Any]:
        latest = self.latest_bar(symbol=symbol, market=market, interval=interval)
        if latest is None:
            return {"start": None, "end": None, "barCount": 0}
        rows = self.repository.query_bars(
            symbol=latest.canonical_symbol,
            market=latest.market,
            interval=latest.interval,
            start=date(1900, 1, 1),
            end=date(2999, 12, 31),
        )
        if not rows:
            return {"start": None, "end": None, "barCount": 0}
        return {
            "start": rows[0].session_date.isoformat(),
            "end": rows[-1].session_date.isoformat(),
            "barCount": len(rows),
        }

    def freshness_summary(self, *, symbol: str, market: str, interval: str) -> dict[str, Any]:
        rows = self._all_rows(symbol=symbol, market=market, interval=interval)
        if not rows:
            return {
                "contractVersion": HISTORICAL_MARKET_DATA_CONTRACT_VERSION,
                "freshnessState": "unavailable",
                "qualityState": "rejected",
                "asOf": None,
                "coveredDateRange": {"start": None, "end": None},
            }
        latest = rows[-1]
        return {
            "contractVersion": HISTORICAL_MARKET_DATA_CONTRACT_VERSION,
            "freshnessState": _freshness_state(latest),
            "qualityState": _rollup_quality(rows),
            "asOf": latest.as_of.isoformat() if latest.as_of else None,
            "coveredDateRange": {
                "start": rows[0].session_date.isoformat(),
                "end": rows[-1].session_date.isoformat(),
            },
            "barCount": len(rows),
            "provider": latest.provider,
            "normalizationVersion": latest.normalization_version,
        }

    def provenance_summary(self, *, symbol: str, market: str, interval: str) -> dict[str, Any]:
        rows = self._all_rows(symbol=symbol, market=market, interval=interval)
        if not rows:
            identity = resolve_historical_symbol_identity(symbol=symbol, market=market)
            return {
                "contractVersion": HISTORICAL_MARKET_DATA_CONTRACT_VERSION,
                "market": identity["market"],
                "canonicalSymbol": identity["canonical_symbol"],
                "qualityState": "rejected",
                "sourceObservationRange": {"start": None, "end": None},
            }
        latest = rows[-1]
        return {
            "contractVersion": HISTORICAL_MARKET_DATA_CONTRACT_VERSION,
            "market": latest.market,
            "venue": latest.venue,
            "canonicalSymbol": latest.canonical_symbol,
            "interval": latest.interval,
            "provider": latest.provider,
            "source": latest.source,
            "asOf": latest.as_of.isoformat() if latest.as_of else None,
            "observedAt": latest.observed_at.isoformat() if latest.observed_at else None,
            "freshnessState": _freshness_state(latest),
            "qualityState": _rollup_quality(rows),
            "normalizationVersion": latest.normalization_version,
            "lineageId": latest.lineage_id,
            "sourceObservationRange": {
                "start": rows[0].session_date.isoformat(),
                "end": rows[-1].session_date.isoformat(),
            },
        }

    def _all_rows(self, *, symbol: str, market: str, interval: str) -> list[CanonicalHistoricalBar]:
        identity = resolve_historical_symbol_identity(symbol=symbol, market=market)
        return self.repository.query_bars(
            symbol=identity["canonical_symbol"],
            market=identity["market"],
            interval=_normalize_interval(interval),
            start=date(1900, 1, 1),
            end=date(2999, 12, 31),
        )


def normalize_provider_historical_bars(
    payload: Mapping[str, Any],
    *,
    preserve_provider_order: bool = False,
) -> list[CanonicalHistoricalBar]:
    provider = _safe_text(payload.get("provider") or payload.get("source") or "unknown").lower()
    symbol = _safe_text(payload.get("symbol") or payload.get("stock_code") or payload.get("code"))
    identity = resolve_historical_symbol_identity(symbol=symbol, market=_safe_text(payload.get("market")))
    interval = _normalize_interval(_safe_text(payload.get("interval") or payload.get("timeframe") or payload.get("period")))
    observed_at = _parse_datetime(payload.get("observedAt") or payload.get("observed_at") or payload.get("timestamp"))
    as_of = _parse_datetime(payload.get("asOf") or payload.get("as_of")) or observed_at
    rows = payload.get("rows")
    if rows is None:
        rows = payload.get("data")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        rows = []
    bars: list[CanonicalHistoricalBar] = []
    ingestion_id = _stable_hash(
        {
            "provider": provider,
            "market": identity["market"],
            "symbol": identity["canonical_symbol"],
            "interval": interval,
            "observedAt": observed_at.isoformat() if observed_at else None,
            "rows": rows,
        }
    )
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            continue
        bar = _normalize_row(
            row,
            provider=provider,
            source=_safe_text(payload.get("source") or provider).lower(),
            identity=identity,
            interval=interval,
            observed_at=observed_at,
            as_of=as_of,
            ingestion_id=ingestion_id,
            currency=_safe_text(row.get("currency") or payload.get("currency")) or None,
            adjusted=payload.get("adjusted"),
            row_index=index,
        )
        bars.append(bar)
    if preserve_provider_order:
        return bars
    return sorted(bars, key=lambda item: (item.session_date, item.timestamp or datetime.min.replace(tzinfo=timezone.utc)))


def resolve_historical_symbol_identity(*, symbol: str, market: str | None = None) -> dict[str, str]:
    provider_symbol = _safe_text(symbol).upper()
    normalized = normalize_stock_code(provider_symbol).upper()
    requested_market = _normalize_market(market)
    if requested_market == "UNKNOWN":
        if is_us_index_code(normalized) or is_us_stock_code(normalized):
            requested_market = "US"
        elif normalized.startswith("HK") and normalized[2:].isdigit():
            requested_market = "HK"
        elif normalized.isdigit() and len(normalized) == 6:
            requested_market = "CN"
    if requested_market == "HK" and not normalized.startswith("HK") and normalized.isdigit():
        normalized = f"HK{normalized.zfill(5)}"
    venue = _venue_for_market_symbol(requested_market, normalized)
    return {
        "market": requested_market,
        "venue": venue,
        "canonical_symbol": normalized,
        "provider_symbol": provider_symbol,
        "timezone": _timezone_for_market(requested_market),
    }


def _normalize_row(
    row: Mapping[str, Any],
    *,
    provider: str,
    source: str,
    identity: Mapping[str, str],
    interval: str,
    observed_at: datetime | None,
    as_of: datetime | None,
    ingestion_id: str,
    currency: str | None,
    adjusted: Any,
    row_index: int,
) -> CanonicalHistoricalBar:
    session_value = _first_value(row, "sessionDate", "session_date", "date", "Date", "trade_date", "日期")
    timestamp_value = _first_value(row, "timestamp", "Timestamp", "datetime", "time")
    session_date, timestamp = _parse_session_and_timestamp(session_value=session_value, timestamp_value=timestamp_value)
    open_value = _float_or_sentinel(_first_value(row, "open", "Open", "开盘"))
    high_value = _float_or_sentinel(_first_value(row, "high", "High", "最高"))
    low_value = _float_or_sentinel(_first_value(row, "low", "Low", "最低"))
    close_value = _float_or_sentinel(_first_value(row, "close", "Close", "收盘"))
    volume_value = _float_or_sentinel(_first_value(row, "volume", "Volume", "成交量"))
    adjustment_metadata = _adjustment_metadata(row)
    adjustment_status = _adjustment_status(adjusted=adjusted, metadata=adjustment_metadata)
    raw_identity = _safe_text(_first_value(row, "id", "rawId", "raw_identity")) or _stable_hash({"row": row, "index": row_index})
    lineage_id = _stable_hash(
        {
            "provider": provider,
            "market": identity["market"],
            "symbol": identity["canonical_symbol"],
            "interval": interval,
            "sessionDate": session_date.isoformat(),
            "rawIdentity": raw_identity,
            "normalizationVersion": HISTORICAL_MARKET_DATA_NORMALIZATION_VERSION,
        }
    )
    return CanonicalHistoricalBar(
        market=identity["market"],
        venue=identity["venue"],
        canonical_symbol=identity["canonical_symbol"],
        provider_symbol=identity["provider_symbol"],
        interval=interval,
        session_date=session_date,
        timestamp=timestamp,
        timezone=identity["timezone"],
        open=open_value,
        high=high_value,
        low=low_value,
        close=close_value,
        volume=volume_value,
        adjustment_status=adjustment_status,
        adjustment_metadata=adjustment_metadata,
        currency=currency,
        provider=provider,
        source=source,
        observed_at=observed_at,
        as_of=as_of,
        ingestion_id=ingestion_id,
        lineage_id=lineage_id,
        normalization_version=HISTORICAL_MARKET_DATA_NORMALIZATION_VERSION,
        raw_identity=raw_identity,
    )


def _adjustment_metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    adjusted_close = _first_value(row, "adjusted_close", "adjustedClose", "Adj Close", "Adjusted Close")
    if adjusted_close is None:
        return {}
    return {"adjustedClose": _float_or_sentinel(adjusted_close)}


def _adjustment_status(*, adjusted: Any, metadata: Mapping[str, Any]) -> str:
    if adjusted is True or metadata:
        return "adjusted"
    if adjusted is False:
        return "unadjusted"
    return "unknown"


def _first_value(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def _parse_session_and_timestamp(*, session_value: Any, timestamp_value: Any) -> tuple[date, datetime | None]:
    parsed_timestamp = _parse_datetime(timestamp_value)
    if parsed_timestamp is not None:
        parsed_date = _parse_date(session_value) or parsed_timestamp.date()
        return parsed_date, parsed_timestamp
    parsed_date = _parse_date(session_value)
    if parsed_date is None:
        return date.min, None
    return parsed_date, None


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _safe_text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = _safe_text(value)
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _float_or_sentinel(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return parsed


def _normalize_market(value: str | None) -> str:
    normalized = _safe_text(value).upper()
    aliases = {
        "CN": "CN",
        "A": "CN",
        "A_SHARE": "CN",
        "ASHARE": "CN",
        "SH": "CN",
        "SZ": "CN",
        "HK": "HK",
        "HKEX": "HK",
        "US": "US",
        "USA": "US",
        "NYSE": "US",
        "NASDAQ": "US",
    }
    return aliases.get(normalized, "UNKNOWN")


def _normalize_interval(value: str | None) -> str:
    normalized = _safe_text(value).lower()
    if normalized in {"", "daily", "day", "1day", "d"}:
        return "1d"
    if normalized in {"1d", "1wk", "1w", "weekly", "1mo", "1m", "monthly"}:
        return {"1w": "1wk", "weekly": "1wk", "1m": "1mo", "monthly": "1mo"}.get(normalized, normalized)
    return normalized


def _timezone_for_market(market: str) -> str:
    return MARKET_TIMEZONE.get(market.lower(), "UTC")


def _venue_for_market_symbol(market: str, symbol: str) -> str:
    if market == "US":
        return MARKET_EXCHANGE.get("us", "XNYS")
    if market == "HK":
        return MARKET_EXCHANGE.get("hk", "XHKG")
    if market == "CN":
        if is_bse_code(symbol):
            return "XBSE"
        if symbol.startswith(("000", "001", "002", "003", "300", "301")):
            return "XSHE"
        return MARKET_EXCHANGE.get("cn", "XSHG")
    return "UNKNOWN"


def _safe_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, ensure_ascii=True).encode("utf-8")).hexdigest()


def _has_business_day_gap(previous: date, current: date) -> bool:
    day = previous + timedelta(days=1)
    while day < current:
        if day.weekday() < 5:
            return True
        day += timedelta(days=1)
    return False


def _freshness_state(bar: CanonicalHistoricalBar) -> str:
    if bar.as_of is None:
        return "unknown"
    return "fresh"


def _rollup_quality(rows: Sequence[CanonicalHistoricalBar]) -> str:
    states = {row.quality_state for row in rows}
    if "rejected" in states:
        return "rejected"
    if "degraded" in states:
        return "degraded"
    if "usable" in states:
        return "usable"
    return "unknown"


__all__ = [
    "CanonicalHistoricalBar",
    "HISTORICAL_MARKET_DATA_CONTRACT_VERSION",
    "HISTORICAL_MARKET_DATA_NORMALIZATION_VERSION",
    "HistoricalBarQualityOutcome",
    "HistoricalIngestionResult",
    "HistoricalMarketDataFoundation",
    "HistoricalPersistenceResult",
    "normalize_provider_historical_bars",
    "resolve_historical_symbol_identity",
]
