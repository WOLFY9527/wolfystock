from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo


NEAR_LIVE_MARKET_OBSERVATION_CONTRACT_VERSION = "near_live_market_observation_v1"
NEAR_LIVE_COVERAGE_CONTRACT_VERSION = "near_live_coverage_qualification_v1"

_SUPPORTED_MARKETS = {"US", "CN", "HK"}
_SOURCE_CLASS_ALIASES = {
    "local_historical_data": "local_historical_data",
    "historical_market_data": "local_historical_data",
    "local_quote_snapshot_cache": "near_live_market_data",
    "near_live_market_data": "near_live_market_data",
    "delayed_market_data": "delayed_market_data",
    "official_macro_source": "official_macro_source",
    "unavailable": "unavailable",
    "mixed": "mixed",
    "partial": "partial",
}
_OBSERVATION_FAMILY = {
    "quote": "quote",
    "intraday_price": "quote",
    "daily_ohlcv": "technical_data",
    "technical_indicator": "technical_data",
    "index_data": "index_data",
    "benchmark_data": "benchmark_data",
    "fx_rate": "fx",
}
_SURFACE_POLICIES: dict[str, dict[str, Any]] = {
    "stock_evidence_quote": {
        "required": ("quote",),
        "critical": ("quote",),
        "quote_max_age_open_seconds": 15 * 60,
        "quote_max_age_closed_seconds": 2 * 60 * 60,
        "intraday_max_age_closed_seconds": 2 * 60 * 60,
        "allow_readable_stale": True,
        "session_required": True,
    },
    "stock_evidence_technical_data": {
        "required": ("technical_data",),
        "critical": ("technical_data",),
        "daily_max_trading_day_lag": 1,
        "allow_readable_stale": True,
        "session_required": False,
    },
    "structure_decision": {
        "required": ("technical_data",),
        "critical": ("technical_data",),
        "daily_max_trading_day_lag": 1,
        "allow_readable_stale": False,
        "session_required": False,
    },
    "market_overview": {
        "required": ("index_data", "benchmark_data"),
        "critical": ("index_data",),
        "quote_max_age_open_seconds": 30 * 60,
        "allow_partial": True,
        "allow_readable_stale": True,
        "session_required": False,
    },
    "watchlist_research_state": {
        "required": ("quote", "technical_data"),
        "critical": ("technical_data",),
        "quote_max_age_open_seconds": 30 * 60,
        "daily_max_trading_day_lag": 1,
        "allow_partial": True,
        "allow_readable_stale": True,
        "session_required": False,
    },
    "portfolio_valuation_context": {
        "required": ("quote", "fx"),
        "critical": ("quote", "fx"),
        "quote_max_age_open_seconds": 30 * 60,
        "allow_readable_stale": True,
        "session_required": False,
    },
}
_MARKET_TZ = {
    "US": "America/New_York",
    "CN": "Asia/Shanghai",
    "HK": "Asia/Hong_Kong",
}
_REGULAR_HOURS = {
    "US": (time(9, 30), time(16, 0)),
    "CN": (time(9, 30), time(15, 0)),
    "HK": (time(9, 30), time(16, 0)),
}
_PRE_MARKET_START = {
    "US": time(4, 0),
    "CN": time(9, 0),
    "HK": time(9, 0),
}
_POST_MARKET_END = {
    "US": time(20, 0),
    "CN": time(15, 30),
    "HK": time(16, 30),
}
_ALLOWED_OUTPUT_KEYS = {
    "market",
    "symbol",
    "observationType",
    "value",
    "boundedPayloadRef",
    "currency",
    "asOf",
    "receivedAt",
    "sourceClass",
    "sourceQuality",
    "marketSessionState",
    "freshnessState",
    "ageSeconds",
    "usable",
    "blockingReasons",
}


def build_canonical_market_observation(
    payload: Mapping[str, Any],
    *,
    surface: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    reference = _as_utc(now) or datetime.now(timezone.utc)
    market = _normalize_market(payload.get("market"))
    symbol = _safe_symbol(payload.get("symbol"))
    observation_type = _safe_code(payload.get("observationType") or payload.get("observation_type"))
    as_of_raw = payload.get("asOf") or payload.get("as_of") or payload.get("timestamp")
    received_at_raw = payload.get("receivedAt") or payload.get("received_at")
    as_of = _parse_datetime(as_of_raw)
    received_at = _parse_datetime(received_at_raw) or as_of
    source_class = _source_class(payload.get("sourceClass") or payload.get("source_class") or payload.get("source"))
    source_quality = _safe_code(payload.get("sourceQuality") or payload.get("source_quality") or "unknown")
    session_state = market_session_state(market=market, at=reference)
    blocking_reasons: list[str] = []

    if market == "UNKNOWN":
        blocking_reasons.append("market_session_unknown")
    if not symbol:
        blocking_reasons.append("symbol_missing")
    if observation_type not in _OBSERVATION_FAMILY:
        blocking_reasons.append("observation_type_unknown")
    if as_of is None:
        blocking_reasons.append(f"{observation_type or 'observation'}_malformed_timestamp")

    age_seconds = None
    if as_of is not None:
        age_seconds = max(0, int((reference - as_of).total_seconds()))

    freshness_state = _freshness_state(
        market=market,
        observation_type=observation_type,
        as_of=as_of,
        reference=reference,
        session_state=session_state,
        surface=surface,
    )
    if freshness_state == "stale":
        blocking_reasons.append("outside_freshness_tolerance")
    if freshness_state in {"unknown", "unavailable"} and _policy(surface).get("session_required"):
        if "market_session_unknown" not in blocking_reasons:
            blocking_reasons.append("market_session_unknown")
    if source_class == "unavailable":
        blocking_reasons.append("source_unavailable")
    if _value_missing(payload) and not payload.get("boundedPayloadRef"):
        blocking_reasons.append(f"{observation_type or 'observation'}_missing")

    usable = not blocking_reasons and freshness_state == "fresh"
    result = {
        "contractVersion": NEAR_LIVE_MARKET_OBSERVATION_CONTRACT_VERSION,
        "market": market,
        "symbol": symbol,
        "observationType": observation_type,
        "currency": _safe_currency(payload.get("currency")),
        "asOf": _iso(as_of),
        "receivedAt": _iso(received_at),
        "sourceClass": source_class,
        "sourceQuality": source_quality,
        "marketSessionState": session_state,
        "freshnessState": freshness_state,
        "ageSeconds": age_seconds,
        "usable": usable,
        "blockingReasons": _dedupe(blocking_reasons),
    }
    if "value" in payload and payload.get("value") is not None:
        result["value"] = payload.get("value")
    if payload.get("boundedPayloadRef"):
        result["boundedPayloadRef"] = str(payload.get("boundedPayloadRef"))[:160]
    return {key: value for key, value in result.items() if key in _ALLOWED_OUTPUT_KEYS or key == "contractVersion"}


def qualify_near_live_coverage(
    *,
    surface: str,
    market: str,
    symbol: str,
    observations: Sequence[Mapping[str, Any]] | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    policy = _policy(surface)
    required = list(policy.get("required") or ())
    critical = set(policy.get("critical") or required)
    canonical = [
        build_canonical_market_observation(observation, surface=surface, now=now)
        for observation in observations or []
        if isinstance(observation, Mapping)
    ]
    available: list[str] = []
    stale: list[str] = []
    rejected: list[str] = []
    blocking_reasons: list[str] = []
    freshness_states: list[str] = []
    as_of_values: list[str] = []
    source_classes: list[str] = []

    for observation in canonical:
        family = _OBSERVATION_FAMILY.get(str(observation.get("observationType") or ""), "unknown")
        if family == "unknown":
            continue
        if observation.get("asOf"):
            as_of_values.append(str(observation.get("asOf")))
        source_class = str(observation.get("sourceClass") or "unavailable")
        if source_class not in source_classes:
            source_classes.append(source_class)
        state = str(observation.get("freshnessState") or "unknown")
        freshness_states.append(state)
        reasons = [str(item) for item in observation.get("blockingReasons") or []]
        malformed = any("malformed_timestamp" in reason for reason in reasons)
        if malformed:
            rejected.append(family)
            blocking_reasons.extend(
                reason if reason.startswith(f"{family}_") else reason
                for reason in reasons
            )
            continue
        if observation.get("usable"):
            _append_unique(available, family)
        elif state == "stale" and policy.get("allow_readable_stale"):
            _append_unique(stale, family)
            blocking_reasons.extend(f"{family}_stale" for _ in [None])
        else:
            blocking_reasons.extend(reasons or [f"{family}_unavailable"])

    missing = [family for family in required if family not in available and family not in stale and family not in rejected]
    for family in missing:
        blocking_reasons.append(f"{family}_missing")

    critical_missing = any(family in critical for family in missing)
    critical_rejected = any(family in critical for family in rejected)
    critical_stale = any(family in critical for family in stale)
    allow_partial = bool(policy.get("allow_partial"))
    if critical_rejected:
        coverage_state = "rejected"
        usable_state = "blocked"
    elif missing and not available and not stale:
        coverage_state = "missing"
        usable_state = "blocked"
    elif critical_missing:
        coverage_state = "missing"
        usable_state = "blocked"
    elif missing:
        coverage_state = "partial" if allow_partial else "missing"
        usable_state = "usable" if allow_partial and available else "blocked"
    elif critical_stale:
        coverage_state = "stale"
        usable_state = "readable_stale" if policy.get("allow_readable_stale") else "blocked"
    elif stale:
        coverage_state = "partial"
        usable_state = "usable"
    else:
        coverage_state = "available"
        usable_state = "usable"

    freshness_state = _rollup_freshness(freshness_states, coverage_state)
    if usable_state == "readable_stale":
        freshness_state = "stale"
    return {
        "contractVersion": NEAR_LIVE_COVERAGE_CONTRACT_VERSION,
        "surface": surface,
        "market": _normalize_market(market),
        "symbol": _safe_symbol(symbol),
        "requiredEvidenceFamilies": required,
        "availableEvidenceFamilies": available,
        "freshness": {
            "state": freshness_state,
            "asOf": min(as_of_values) if as_of_values else None,
        },
        "coverageState": coverage_state,
        "usableState": usable_state,
        "ready": coverage_state == "available" and usable_state == "usable",
        "blockingReasons": _dedupe(blocking_reasons),
        "observations": canonical,
        "provenance": {
            "sourceClass": _bounded_source_class(source_classes, coverage_state=coverage_state),
            "sourceQuality": _bounded_source_quality(canonical),
        },
        "consumerSafe": True,
        "noProductionWrites": True,
    }


def market_session_state(*, market: str, at: datetime) -> str:
    normalized = _normalize_market(market)
    if normalized not in _SUPPORTED_MARKETS:
        return "unknown"
    tz = ZoneInfo(_MARKET_TZ[normalized])
    local = _as_utc(at).astimezone(tz)
    if local.weekday() >= 5:
        return "non_trading_day"
    current = local.time()
    regular_start, regular_end = _REGULAR_HOURS[normalized]
    if regular_start <= current < regular_end:
        return "open"
    if _PRE_MARKET_START[normalized] <= current < regular_start:
        return "pre_market"
    if regular_end <= current < _POST_MARKET_END[normalized]:
        return "post_market"
    return "closed"


def freshness_policy(surface: str) -> dict[str, Any]:
    policy = _policy(surface)
    return {
        "surface": surface,
        "requiredEvidenceFamilies": list(policy.get("required") or ()),
        "criticalEvidenceFamilies": list(policy.get("critical") or ()),
        "allowReadableStale": bool(policy.get("allow_readable_stale")),
        "sessionRequired": bool(policy.get("session_required")),
    }


def _freshness_state(
    *,
    market: str,
    observation_type: str,
    as_of: datetime | None,
    reference: datetime,
    session_state: str,
    surface: str,
) -> str:
    if as_of is None:
        return "unknown"
    if market == "UNKNOWN" or session_state == "unknown":
        return "unknown"
    policy = _policy(surface)
    family = _OBSERVATION_FAMILY.get(observation_type, "unknown")
    if family == "technical_data":
        max_lag = int(policy.get("daily_max_trading_day_lag", 1))
        return "fresh" if _trading_day_lag(market=market, as_of=as_of, reference=reference) <= max_lag else "stale"
    max_age = int(policy.get("quote_max_age_open_seconds", 15 * 60))
    if session_state != "open":
        if observation_type == "intraday_price":
            max_age = int(policy.get("intraday_max_age_closed_seconds", max_age))
        else:
            max_age = int(policy.get("quote_max_age_closed_seconds", max_age))
    return "fresh" if (reference - as_of).total_seconds() <= max_age else "stale"


def _trading_day_lag(*, market: str, as_of: datetime, reference: datetime) -> int:
    tz = ZoneInfo(_MARKET_TZ.get(market, "UTC"))
    start = as_of.astimezone(tz).date()
    end = reference.astimezone(tz).date()
    if end <= start:
        return 0
    lag = 0
    cursor = start + timedelta(days=1)
    while cursor <= end:
        if cursor.weekday() < 5:
            lag += 1
        cursor += timedelta(days=1)
    if reference.astimezone(tz).weekday() >= 5:
        return max(0, lag - 1)
    return lag


def _policy(surface: str) -> dict[str, Any]:
    return dict(_SURFACE_POLICIES.get(surface, _SURFACE_POLICIES["stock_evidence_quote"]))


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return _as_utc(value)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _as_utc(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_market(value: Any) -> str:
    token = str(value or "").strip().upper()
    aliases = {
        "USA": "US",
        "NYSE": "US",
        "NASDAQ": "US",
        "A": "CN",
        "ASHARE": "CN",
        "A_SHARE": "CN",
        "HKEX": "HK",
    }
    return aliases.get(token, token if token in _SUPPORTED_MARKETS else "UNKNOWN")


def _safe_symbol(value: Any) -> str:
    return str(value or "").strip().upper()[:32]


def _safe_code(value: Any) -> str:
    text = str(value or "").strip().lower()
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in text)[:64]


def _safe_currency(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    return text[:8] if text else None


def _source_class(value: Any) -> str:
    token = _safe_code(value)
    return _SOURCE_CLASS_ALIASES.get(token, "unavailable" if not token else "near_live_market_data")


def _value_missing(payload: Mapping[str, Any]) -> bool:
    observation_type = _safe_code(payload.get("observationType") or payload.get("observation_type"))
    if observation_type in {"daily_ohlcv", "technical_indicator"} and payload.get("boundedPayloadRef"):
        return False
    if "value" not in payload:
        return observation_type in {"quote", "intraday_price", "index_data", "benchmark_data", "fx_rate"}
    value = payload.get("value")
    if value is None:
        return True
    try:
        return float(value) <= 0
    except (TypeError, ValueError):
        return False


def _rollup_freshness(states: Sequence[str], coverage_state: str) -> str:
    if coverage_state in {"missing", "rejected"}:
        return "unavailable" if coverage_state == "missing" else "unknown"
    if any(state == "stale" for state in states):
        return "stale"
    if any(state == "fresh" for state in states):
        return "fresh"
    return "unknown"


def _bounded_source_class(source_classes: Sequence[str], *, coverage_state: str) -> str:
    classes = [item for item in source_classes if item]
    if not classes:
        return "unavailable"
    if coverage_state == "partial" or len(set(classes)) > 1:
        return "partial"
    return classes[0] if classes[0] in set(_SOURCE_CLASS_ALIASES.values()) else "near_live_market_data"


def _bounded_source_quality(observations: Sequence[Mapping[str, Any]]) -> str:
    qualities = {str(item.get("sourceQuality") or "unknown") for item in observations}
    if not qualities:
        return "unknown"
    if "usable" in qualities or "reported" in qualities:
        return "usable"
    if "delayed" in qualities:
        return "delayed"
    return "unknown"


def _dedupe(values: Sequence[str] | list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        _append_unique(result, value)
    return result


def _append_unique(values: list[str], value: str) -> None:
    text = str(value or "").strip()
    if text and text not in values:
        values.append(text)


__all__ = [
    "NEAR_LIVE_COVERAGE_CONTRACT_VERSION",
    "NEAR_LIVE_MARKET_OBSERVATION_CONTRACT_VERSION",
    "build_canonical_market_observation",
    "freshness_policy",
    "market_session_state",
    "qualify_near_live_coverage",
]
