# -*- coding: utf-8 -*-
"""Inert official-public CN money-market rate cache contracts.

This module validates and projects explicitly configured local/cache payloads
only. It must not import provider clients, call networks, read credentials,
mutate MarketCache, change provider ordering, or enable liquidity scoring.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence


OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID = "official_public.cn_money_market_rates"
OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_NAME = "Official CN Money Market Rates"
OFFICIAL_CN_MONEY_MARKET_RATES_SOURCE_TYPE = "official_public"
OFFICIAL_CN_MONEY_MARKET_RATES_SOURCE_TIER = "official_public"
OFFICIAL_CN_MONEY_MARKET_RATES_TRUST_LEVEL = "score_grade_when_configured"
OFFICIAL_CN_MONEY_MARKET_RATES_CACHE_ONLY_MODE = "cache_only"
OFFICIAL_CN_MONEY_MARKET_RATES_CACHE_PATH_ENV = "CN_MONEY_MARKET_RATES_CACHE_PATH"
OFFICIAL_CN_MONEY_MARKET_RATES_REQUIRED_METRICS = ("DR007", "SHIBOR_ON")
OFFICIAL_CN_MONEY_MARKET_RATES_CONTEXT_METRICS = ("SHIBOR_3M", "LPR_1Y", "LPR_5Y", "CN10Y")
OFFICIAL_CN_MONEY_MARKET_RATES_MAX_DELAY_MINUTES = 7 * 24 * 60

SAFE_UNAVAILABLE_REASON_BUCKETS = (
    "missing_cache_config",
    "missing_cache",
    "empty_payload",
    "malformed_payload",
    "missing_required_metric",
    "partial_official_coverage",
    "stale_official_release",
    "missing_publication_or_trading_date",
    "holiday_calendar_unqualified_date_ambiguity",
    "unsupported_unit",
    "unsupported_value_format",
)

_CN_TZ = timezone(timedelta(hours=8))
_SOURCE_CLASS_DISABLED = "disabled_live_stub"
_SUCCESS_REASON_CODE = "official_cn_money_market_rates_cache_valid_diagnostic_only"
_CN10Y_CONTEXT_REASON_CODE = "cn10y_context_only_not_yield_curve_authority"
_EXPECTED_UNIT = "%"


@dataclass(frozen=True)
class CnMoneyMarketRateContract:
    official_series_id: str
    symbol: str
    display_name: str
    expected_unit: str
    expected_cadence: str
    source_class: str
    freshness_window: str
    required_for_future_score_eligibility: bool
    context_only: bool


@dataclass(frozen=True)
class ParsedCnMoneyMarketRateObservation:
    official_series_id: str
    symbol: str
    value: float
    as_of: str
    publication_date: str | None
    trading_date: str | None


class CnMoneyMarketRatesProviderUnavailable(RuntimeError):
    """Sanitized fail-closed unavailable state for CN money-market cache data."""

    def __init__(self, reason_codes: Sequence[str] | str) -> None:
        if isinstance(reason_codes, str):
            raw_values = (reason_codes,)
        else:
            raw_values = tuple(reason_codes)
        sanitized = tuple(dict.fromkeys(_safe_reason_bucket(reason) for reason in raw_values))
        self.reason_codes = sanitized or ("malformed_payload",)
        super().__init__(
            f"{OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID}_unavailable:"
            f"{','.join(self.reason_codes)}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "providerId": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
            "available": False,
            "reasonCodes": list(self.reason_codes),
            "observationOnly": True,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "externalProviderCalls": False,
        }


_CONTRACTS = (
    CnMoneyMarketRateContract(
        official_series_id="DR007",
        symbol="DR007",
        display_name="DR007",
        expected_unit=_EXPECTED_UNIT,
        expected_cadence="session_daily_official_fixing",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Session or daily official fixing from configured local cache only.",
        required_for_future_score_eligibility=True,
        context_only=False,
    ),
    CnMoneyMarketRateContract(
        official_series_id="SHIBOR_ON",
        symbol="SHIBOR",
        display_name="SHIBOR overnight",
        expected_unit=_EXPECTED_UNIT,
        expected_cadence="daily_official_fixing",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Daily official overnight SHIBOR fixing from configured local cache only.",
        required_for_future_score_eligibility=True,
        context_only=False,
    ),
    CnMoneyMarketRateContract(
        official_series_id="SHIBOR_3M",
        symbol="SHIBOR_3M",
        display_name="SHIBOR 3M",
        expected_unit=_EXPECTED_UNIT,
        expected_cadence="daily_official_fixing",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Daily official SHIBOR 3M fixing from configured local cache only.",
        required_for_future_score_eligibility=False,
        context_only=True,
    ),
    CnMoneyMarketRateContract(
        official_series_id="LPR_1Y",
        symbol="LPR_1Y",
        display_name="LPR 1Y",
        expected_unit=_EXPECTED_UNIT,
        expected_cadence="monthly_official_fixing",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Official LPR 1Y fixing from configured local cache only.",
        required_for_future_score_eligibility=False,
        context_only=True,
    ),
    CnMoneyMarketRateContract(
        official_series_id="LPR_5Y",
        symbol="LPR_5Y",
        display_name="LPR 5Y",
        expected_unit=_EXPECTED_UNIT,
        expected_cadence="monthly_official_fixing",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="Official LPR 5Y fixing from configured local cache only.",
        required_for_future_score_eligibility=False,
        context_only=True,
    ),
    CnMoneyMarketRateContract(
        official_series_id="CN10Y",
        symbol="CN10Y",
        display_name="China 10Y government bond yield context",
        expected_unit=_EXPECTED_UNIT,
        expected_cadence="context_only_daily_yield_snapshot",
        source_class=_SOURCE_CLASS_DISABLED,
        freshness_window="CN10Y may be carried as context only; this is not yield-curve authority.",
        required_for_future_score_eligibility=False,
        context_only=True,
    ),
)

_CONTRACTS_BY_SERIES = MappingProxyType({item.official_series_id: item for item in _CONTRACTS})
_CONTRACTS_BY_ALIAS = MappingProxyType(
    {
        "DR007": _CONTRACTS_BY_SERIES["DR007"],
        "SHIBOR": _CONTRACTS_BY_SERIES["SHIBOR_ON"],
        "SHIBOR_ON": _CONTRACTS_BY_SERIES["SHIBOR_ON"],
        "SHIBOR_O/N": _CONTRACTS_BY_SERIES["SHIBOR_ON"],
        "SHIBOR_3M": _CONTRACTS_BY_SERIES["SHIBOR_3M"],
        "LPR_1Y": _CONTRACTS_BY_SERIES["LPR_1Y"],
        "LPR1Y": _CONTRACTS_BY_SERIES["LPR_1Y"],
        "LPR_5Y": _CONTRACTS_BY_SERIES["LPR_5Y"],
        "LPR5Y": _CONTRACTS_BY_SERIES["LPR_5Y"],
        "CN10Y": _CONTRACTS_BY_SERIES["CN10Y"],
    }
)


def list_cn_money_market_rate_contracts() -> tuple[CnMoneyMarketRateContract, ...]:
    """Return deterministic CN money-market contracts for future provider wiring."""
    return tuple(_CONTRACTS)


def get_cn_money_market_rate_contract(symbol: str | None) -> CnMoneyMarketRateContract | None:
    """Look up a CN money-market contract by display symbol or official series id."""
    normalized = _normalize_metric_id(symbol)
    if not normalized:
        return None
    return _CONTRACTS_BY_ALIAS.get(normalized)


def read_official_cn_money_market_rates_cache(
    *,
    env: Mapping[str, str] | None = None,
    file_loader: Callable[[Path], Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Read and normalize an explicitly configured local CN money-market cache."""
    runtime_env = env if env is not None else os.environ
    cache_path = _text(runtime_env.get(OFFICIAL_CN_MONEY_MARKET_RATES_CACHE_PATH_ENV))
    if not cache_path:
        raise CnMoneyMarketRatesProviderUnavailable("missing_cache_config")
    loader = file_loader or _load_json
    try:
        payload = loader(Path(cache_path))
    except CnMoneyMarketRatesProviderUnavailable:
        raise
    except FileNotFoundError as exc:
        raise CnMoneyMarketRatesProviderUnavailable("missing_cache") from exc
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        raise CnMoneyMarketRatesProviderUnavailable("malformed_payload") from exc
    return build_official_cn_money_market_rates_snapshot(payload, now=now)


def build_official_cn_money_market_rates_snapshot(
    payload: Any,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Project a cache-only official CN money-market payload into diagnostics."""
    now_dt = _normalize_datetime(now) or datetime.now(_CN_TZ)
    if not isinstance(payload, Mapping):
        raise CnMoneyMarketRatesProviderUnavailable("malformed_payload")

    _validate_source_metadata(payload)
    observations = payload.get("observations")
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
        raise CnMoneyMarketRatesProviderUnavailable("malformed_payload")
    if not observations:
        raise CnMoneyMarketRatesProviderUnavailable("empty_payload")

    if _boolean(payload.get("holidayCalendarQualified") or payload.get("holiday_calendar_qualified")) is not True:
        raise CnMoneyMarketRatesProviderUnavailable("holiday_calendar_unqualified_date_ambiguity")

    as_of_text = _extract_as_of(payload)
    as_of_dt = _parse_datetime(as_of_text)
    if as_of_dt is None:
        raise CnMoneyMarketRatesProviderUnavailable("malformed_payload")

    publication_date = _text(payload.get("publicationDate") or payload.get("publication_date"))
    trading_date = _text(payload.get("tradingDate") or payload.get("trading_date"))
    if not publication_date and not trading_date:
        raise CnMoneyMarketRatesProviderUnavailable("missing_publication_or_trading_date")

    delay_minutes = _delay_minutes(as_of_dt, now_dt)
    if delay_minutes > OFFICIAL_CN_MONEY_MARKET_RATES_MAX_DELAY_MINUTES:
        raise CnMoneyMarketRatesProviderUnavailable("stale_official_release")

    freshness = _official_freshness(payload)
    parsed = _parse_observations(
        observations,
        as_of_text=as_of_text or now_dt.isoformat(timespec="seconds"),
        publication_date=publication_date or None,
        trading_date=trading_date or None,
    )
    fulfilled_metrics = [
        metric
        for metric in OFFICIAL_CN_MONEY_MARKET_RATES_REQUIRED_METRICS
        if metric in parsed
    ]
    missing_metrics = [
        metric
        for metric in OFFICIAL_CN_MONEY_MARKET_RATES_REQUIRED_METRICS
        if metric not in parsed
    ]
    coverage_ratio = round(
        len(fulfilled_metrics) / len(OFFICIAL_CN_MONEY_MARKET_RATES_REQUIRED_METRICS),
        2,
    )
    if missing_metrics:
        raise CnMoneyMarketRatesProviderUnavailable(
            ("missing_required_metric", "partial_official_coverage")
        )

    source_freshness_evidence = {
        "providerId": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
        "source": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
        "freshness": freshness,
        "asOf": as_of_text,
        "publicationDate": publication_date or None,
        "tradingDate": trading_date or None,
        "delayMinutes": delay_minutes,
        "cacheOnly": True,
        "externalProviderCalls": False,
        "isFallback": False,
        "isStale": False,
        "isPartial": False,
        "isUnavailable": False,
        "fulfilledMetrics": fulfilled_metrics,
        "missingMetrics": missing_metrics,
        "requiredSeries": list(OFFICIAL_CN_MONEY_MARKET_RATES_REQUIRED_METRICS),
        "fulfilledSeries": fulfilled_metrics,
        "missingSeries": missing_metrics,
        "contextSeries": list(OFFICIAL_CN_MONEY_MARKET_RATES_CONTEXT_METRICS),
        "coverageRatio": coverage_ratio,
    }
    cache_bundle_diagnostics = {
        "providerId": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
        "providerName": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_NAME,
        "source": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
        "sourceLabel": f"{OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_NAME} diagnostic cache",
        "sourceType": OFFICIAL_CN_MONEY_MARKET_RATES_SOURCE_TYPE,
        "sourceTier": OFFICIAL_CN_MONEY_MARKET_RATES_SOURCE_TIER,
        "trustLevel": OFFICIAL_CN_MONEY_MARKET_RATES_TRUST_LEVEL,
        "retrievalMode": OFFICIAL_CN_MONEY_MARKET_RATES_CACHE_ONLY_MODE,
        "cacheOnly": True,
        "externalProviderCalls": False,
        "freshness": freshness,
        "requiredSeries": list(OFFICIAL_CN_MONEY_MARKET_RATES_REQUIRED_METRICS),
        "fulfilledSeries": fulfilled_metrics,
        "missingSeries": missing_metrics,
        "requiredMetrics": list(OFFICIAL_CN_MONEY_MARKET_RATES_REQUIRED_METRICS),
        "fulfilledMetrics": fulfilled_metrics,
        "missingMetrics": missing_metrics,
        "contextSeries": list(OFFICIAL_CN_MONEY_MARKET_RATES_CONTEXT_METRICS),
        "contextOnlySeries": list(OFFICIAL_CN_MONEY_MARKET_RATES_CONTEXT_METRICS),
        "coverageRatio": coverage_ratio,
        "coverage": coverage_ratio,
        "isPartial": False,
        "isStale": False,
        "isUnavailable": False,
        "isFallback": False,
        "fallbackUsed": False,
        "observationOnly": True,
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": False,
        "reasonCodes": [_SUCCESS_REASON_CODE],
        "sourceFreshnessEvidence": dict(source_freshness_evidence),
    }
    ordered_series = (
        *OFFICIAL_CN_MONEY_MARKET_RATES_REQUIRED_METRICS,
        *OFFICIAL_CN_MONEY_MARKET_RATES_CONTEXT_METRICS,
    )
    items = [
        _rate_item(
            parsed[series_id],
            freshness=freshness,
            source_freshness_evidence=source_freshness_evidence,
        )
        for series_id in ordered_series
        if series_id in parsed
    ]
    return {
        "providerId": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
        "providerName": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_NAME,
        "source": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
        "sourceLabel": f"{OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_NAME} diagnostic cache",
        "sourceType": OFFICIAL_CN_MONEY_MARKET_RATES_SOURCE_TYPE,
        "sourceTier": OFFICIAL_CN_MONEY_MARKET_RATES_SOURCE_TIER,
        "trustLevel": OFFICIAL_CN_MONEY_MARKET_RATES_TRUST_LEVEL,
        "retrievalMode": OFFICIAL_CN_MONEY_MARKET_RATES_CACHE_ONLY_MODE,
        "cacheOnly": True,
        "externalProviderCalls": False,
        "updatedAt": _text(payload.get("updatedAt") or payload.get("updated_at") or as_of_text),
        "asOf": as_of_text,
        "publicationDate": publication_date or None,
        "tradingDate": trading_date or None,
        "freshness": freshness,
        "sourceFreshnessEvidence": source_freshness_evidence,
        "cacheBundleDiagnostics": cache_bundle_diagnostics,
        "items": items,
        "requiredSeries": list(OFFICIAL_CN_MONEY_MARKET_RATES_REQUIRED_METRICS),
        "fulfilledSeries": fulfilled_metrics,
        "missingSeries": missing_metrics,
        "contextSeries": list(OFFICIAL_CN_MONEY_MARKET_RATES_CONTEXT_METRICS),
        "contextOnlySeries": list(OFFICIAL_CN_MONEY_MARKET_RATES_CONTEXT_METRICS),
        "fulfilledMetrics": fulfilled_metrics,
        "missingMetrics": missing_metrics,
        "coverageRatio": coverage_ratio,
        "coverage": coverage_ratio,
        "isPartial": False,
        "fallbackUsed": False,
        "isFallback": False,
        "isUnavailable": False,
        "observationOnly": True,
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": False,
        "reasonCodes": [_SUCCESS_REASON_CODE],
        "warning": "Official CN money-market diagnostic cache; scoring remains disabled.",
    }


def _parse_observations(
    observations: Sequence[Any],
    *,
    as_of_text: str,
    publication_date: str | None,
    trading_date: str | None,
) -> dict[str, ParsedCnMoneyMarketRateObservation]:
    parsed: dict[str, ParsedCnMoneyMarketRateObservation] = {}
    for raw_item in observations:
        if not isinstance(raw_item, Mapping):
            raise CnMoneyMarketRatesProviderUnavailable("malformed_payload")
        contract = get_cn_money_market_rate_contract(
            raw_item.get("officialSeriesId")
            or raw_item.get("official_series_id")
            or raw_item.get("seriesId")
            or raw_item.get("series_id")
            or raw_item.get("symbol")
        )
        if contract is None:
            continue
        unit = _text(raw_item.get("unit"))
        if unit != contract.expected_unit:
            raise CnMoneyMarketRatesProviderUnavailable("unsupported_unit")
        value = _parse_number(raw_item.get("value"))
        if value is None:
            raise CnMoneyMarketRatesProviderUnavailable("unsupported_value_format")
        row_publication_date = _text(raw_item.get("publicationDate") or raw_item.get("publication_date")) or publication_date
        row_trading_date = _text(raw_item.get("tradingDate") or raw_item.get("trading_date")) or trading_date
        if not row_publication_date and not row_trading_date:
            raise CnMoneyMarketRatesProviderUnavailable("missing_publication_or_trading_date")
        parsed[contract.official_series_id] = ParsedCnMoneyMarketRateObservation(
            official_series_id=contract.official_series_id,
            symbol=contract.symbol,
            value=value,
            as_of=_extract_as_of(raw_item) or as_of_text,
            publication_date=row_publication_date or None,
            trading_date=row_trading_date or None,
        )
    if not parsed:
        raise CnMoneyMarketRatesProviderUnavailable("empty_payload")
    return parsed


def _rate_item(
    observation: ParsedCnMoneyMarketRateObservation,
    *,
    freshness: str,
    source_freshness_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    contract = _CONTRACTS_BY_SERIES[observation.official_series_id]
    reason_codes = [_SUCCESS_REASON_CODE]
    source_authority_allowed = True
    source_authority_reason = None
    if observation.official_series_id == "CN10Y":
        source_authority_allowed = False
        source_authority_reason = _CN10Y_CONTEXT_REASON_CODE
        reason_codes.append(_CN10Y_CONTEXT_REASON_CODE)
    return {
        "name": contract.display_name,
        "label": contract.display_name,
        "symbol": observation.symbol,
        "officialSeriesId": observation.official_series_id,
        "value": observation.value,
        "price": observation.value,
        "change": None,
        "changePercent": None,
        "change_text": None,
        "sparkline": [],
        "trend": [],
        "unit": contract.expected_unit,
        "currency": None,
        "source": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
        "sourceId": observation.official_series_id,
        "sourceLabel": f"{OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_NAME} diagnostic cache",
        "sourceType": OFFICIAL_CN_MONEY_MARKET_RATES_SOURCE_TYPE,
        "sourceTier": OFFICIAL_CN_MONEY_MARKET_RATES_SOURCE_TIER,
        "trustLevel": OFFICIAL_CN_MONEY_MARKET_RATES_TRUST_LEVEL,
        "providerId": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
        "providerClass": OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID,
        "activationHint": "official_cn_money_market_rates_cache_diagnostic",
        "asOf": observation.as_of,
        "updatedAt": observation.as_of,
        "publicationDate": observation.publication_date,
        "tradingDate": observation.trading_date,
        "freshness": freshness,
        "isFallback": False,
        "fallbackUsed": False,
        "isUnavailable": False,
        "observationOnly": True,
        "sourceAuthorityAllowed": source_authority_allowed,
        "sourceAuthorityReason": source_authority_reason,
        "scoreContributionAllowed": False,
        "includedInScore": False,
        "reasonCodes": reason_codes,
        "sourceFreshnessEvidence": dict(source_freshness_evidence),
        "risk_direction": "neutral",
        "hover_details": ["Official-public diagnostic cache; score contribution disabled."],
    }


def _validate_source_metadata(payload: Mapping[str, Any]) -> None:
    provider_id = _text(payload.get("providerId") or payload.get("provider_id") or payload.get("source")).lower()
    source = _text(payload.get("source") or payload.get("providerId") or payload.get("provider_id")).lower()
    source_type = _text(payload.get("sourceType") or payload.get("source_type")).lower()
    source_tier = _text(payload.get("sourceTier") or payload.get("source_tier")).lower()
    if provider_id != OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID:
        raise CnMoneyMarketRatesProviderUnavailable("malformed_payload")
    if source != OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID:
        raise CnMoneyMarketRatesProviderUnavailable("malformed_payload")
    if source_type != OFFICIAL_CN_MONEY_MARKET_RATES_SOURCE_TYPE:
        raise CnMoneyMarketRatesProviderUnavailable("malformed_payload")
    if source_tier != OFFICIAL_CN_MONEY_MARKET_RATES_SOURCE_TIER:
        raise CnMoneyMarketRatesProviderUnavailable("malformed_payload")


def _official_freshness(payload: Mapping[str, Any]) -> str:
    freshness = _text(payload.get("freshness") or payload.get("sourceFreshness")).lower()
    if freshness in {"live", "realtime"}:
        raise CnMoneyMarketRatesProviderUnavailable("malformed_payload")
    if freshness in {"fresh", "delayed", "cached"}:
        return "delayed" if freshness == "fresh" else freshness
    if freshness == "stale":
        raise CnMoneyMarketRatesProviderUnavailable("stale_official_release")
    return "delayed"


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _parse_datetime(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _normalize_datetime(parsed)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=_CN_TZ)
    return value.astimezone(_CN_TZ)


def _delay_minutes(as_of: datetime, now: datetime) -> int:
    delay = int((now - as_of).total_seconds() // 60)
    return max(0, delay)


def _extract_as_of(payload: Any) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    for key in ("as_of", "asOf", "updated_at", "updatedAt"):
        value = _text(payload.get(key))
        if value:
            return value
    return None


def _parse_number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    normalized = _text(value).lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _normalize_metric_id(value: Any) -> str:
    return _text(value).upper().replace("-", "_").replace(" ", "_")


def _safe_reason_bucket(value: Any) -> str:
    normalized = _text(value).lower()
    if normalized in SAFE_UNAVAILABLE_REASON_BUCKETS:
        return normalized
    return "malformed_payload"


def _text(value: Any) -> str:
    return str(value or "").strip()


__all__ = [
    "OFFICIAL_CN_MONEY_MARKET_RATES_CACHE_PATH_ENV",
    "OFFICIAL_CN_MONEY_MARKET_RATES_CONTEXT_METRICS",
    "OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_ID",
    "OFFICIAL_CN_MONEY_MARKET_RATES_PROVIDER_NAME",
    "OFFICIAL_CN_MONEY_MARKET_RATES_REQUIRED_METRICS",
    "CnMoneyMarketRateContract",
    "CnMoneyMarketRatesProviderUnavailable",
    "build_official_cn_money_market_rates_snapshot",
    "get_cn_money_market_rate_contract",
    "list_cn_money_market_rate_contracts",
    "read_official_cn_money_market_rates_cache",
]
