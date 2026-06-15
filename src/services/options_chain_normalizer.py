# -*- coding: utf-8 -*-
"""Provider-neutral options chain normalizer.

This module is intentionally pure and offline-only. It maps provider-like
fixtures into a small internal contract shape that future observation-only
market-structure code can consume without granting decision authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
import re
from typing import Any, Literal


ProviderProfile = Literal["generic", "polygon_snapshot_like", "tradier_like"]
NORMALIZER_VERSION = "options_chain_normalizer_v1"
_SUPPORTED_PROVIDER_PROFILES = {"generic", "polygon_snapshot_like", "tradier_like"}
_OBSERVATION_BLOCKERS = [
    "observation_only_not_decision_grade",
    "provider_authority_unverified",
    "redistribution_rights_unverified",
    "decision_use_rights_unverified",
]


@dataclass(frozen=True)
class NormalizedOptionGreeks:
    delta: float | None = None
    gamma: float | None = None
    vega: float | None = None
    theta: float | None = None
    rho: float | None = None


@dataclass(frozen=True)
class NormalizedOptionContract:
    symbol: str
    contract_symbol: str
    side: str | None
    expiration: str | None
    strike: float | None
    multiplier: int | None = None
    bid: float | None = None
    ask: float | None = None
    mid: float | None = None
    last: float | None = None
    volume: int | None = None
    open_interest: int | None = None
    implied_volatility: float | None = None
    greeks: NormalizedOptionGreeks | None = None
    dte: int | None = None
    moneyness: str = "unknown"
    spread_pct: float | None = None
    liquidity_bucket: str = "unknown"
    as_of: str = ""
    source: str = ""
    freshness: str = "unknown"
    provider_quality: str | None = None
    data_quality: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NormalizedOptionsChain:
    underlying_symbol: str
    market: str
    currency: str
    underlying_spot: float | None
    spot_reference: dict[str, Any]
    contracts: list[NormalizedOptionContract]
    provider_profile: ProviderProfile
    source: str
    chain_as_of: str
    freshness: str
    provider_quality: str
    data_quality_labels: list[str]
    coverage: dict[str, Any]
    missing_evidence: list[dict[str, Any]]
    metadata: dict[str, Any]
    observation_only: bool = True
    decision_grade: bool = False
    warnings: list[str] = field(default_factory=list)


def normalize_options_chain(
    raw_chain: Mapping[str, Any],
    *,
    provider_profile: ProviderProfile = "generic",
    underlying_symbol: str | None = None,
    source: str | None = None,
    as_of: str | None = None,
    freshness: str | None = None,
) -> NormalizedOptionsChain:
    """Normalize provider-like raw option chain records.

    The normalizer does not fetch data, read credentials, or promote any row to
    decision grade. Missing GEX prerequisites are reported in
    ``missing_evidence`` instead of being filled with guessed values.
    """

    if not isinstance(raw_chain, Mapping):
        raise TypeError("raw_chain must be a mapping")
    profile = _normalize_provider_profile(provider_profile)
    data = dict(raw_chain)
    underlying = _underlying_mapping(data, profile)
    symbol = _normalize_symbol(
        _coalesce_present(
            underlying_symbol,
            _first_present(data, ("symbol", "ticker", "underlyingSymbol", "underlying_symbol")),
            _first_present(underlying, ("symbol", "ticker")),
        )
    )
    market = _text(_first_present(data, ("market",)) or "us").lower() or "us"
    currency = _text(_first_present(data, ("currency",)) or "USD").upper() or "USD"
    spot = _positive_float_or_none(
        _coalesce_present(
            _first_present(
                underlying,
                ("price", "last", "last_price", "close", "underlyingPrice", "underlying_price"),
            ),
            _first_present(data, ("underlyingPrice", "underlying_price", "spot", "spotPrice")),
        )
    )
    chain_as_of = _text(
        _coalesce_present(
            as_of,
            _first_present(data, ("chainAsOf", "chain_as_of", "asOf", "as_of", "timestamp")),
            _first_present(underlying, ("asOf", "as_of", "trade_date", "last_updated", "timestamp")),
        )
    )
    source_text = _text(
        _coalesce_present(
            source,
            _first_present(data, ("source", "providerName", "provider_name")),
            _first_present(underlying, ("source",)),
            profile,
        )
    )
    freshness_text = _text(
        _coalesce_present(
            freshness,
            _first_present(data, ("freshness", "chainFreshness", "chain_freshness")),
            _first_present(underlying, ("freshness",)),
            "unknown",
        )
    )
    provider_quality = _text(
        _first_present(data, ("providerQuality", "provider_quality"))
        or "observation_only_not_decision_grade"
    )

    contracts = [
        _normalize_contract(
            row,
            index=index,
            profile=profile,
            symbol=symbol,
            chain_as_of=chain_as_of,
            chain_source=source_text,
            chain_freshness=freshness_text,
            provider_quality=provider_quality,
            spot=spot,
        )
        for index, row in enumerate(_contract_rows(data, profile))
    ]
    data_quality_labels = _data_quality_labels(freshness_text)
    missing_evidence = _missing_evidence(contracts, spot)
    coverage = _coverage(contracts, spot)
    metadata = {
        "normalizerVersion": NORMALIZER_VERSION,
        "providerProfile": profile,
        "source": source_text,
        "asOf": chain_as_of,
        "freshness": freshness_text,
        "providerQuality": provider_quality,
        "observationOnly": True,
        "decisionGrade": False,
        "decisionGradeBlocked": True,
        "notDecisionGradeReasonCodes": list(_OBSERVATION_BLOCKERS),
        "liveProviderEnabled": False,
        "providerAuthorityVerified": False,
        "noExternalCalls": True,
        "noProviderCredentials": True,
    }
    warnings = _dedupe(
        [
            *list(data.get("warnings") or []),
            "observation_only_not_decision_grade",
            *(["freshness_unknown"] if freshness_text == "unknown" else []),
        ]
    )

    return NormalizedOptionsChain(
        underlying_symbol=symbol,
        market=market,
        currency=currency,
        underlying_spot=spot,
        spot_reference={
            "symbol": symbol,
            "spot": spot,
            "asOf": chain_as_of,
            "source": source_text,
            "freshness": freshness_text,
        },
        contracts=contracts,
        provider_profile=profile,
        source=source_text,
        chain_as_of=chain_as_of,
        freshness=freshness_text,
        provider_quality=provider_quality,
        data_quality_labels=data_quality_labels,
        coverage=coverage,
        missing_evidence=missing_evidence,
        metadata=metadata,
        warnings=warnings,
    )


def _normalize_provider_profile(value: str) -> ProviderProfile:
    normalized = _text(value).lower()
    if normalized not in _SUPPORTED_PROVIDER_PROFILES:
        raise ValueError(f"Unsupported options provider profile: {value}")
    return normalized  # type: ignore[return-value]


def _underlying_mapping(data: Mapping[str, Any], profile: ProviderProfile) -> Mapping[str, Any]:
    if profile == "polygon_snapshot_like":
        return _mapping_or_empty(data.get("underlying_asset") or data.get("underlyingAsset"))
    return _mapping_or_empty(data.get("underlying"))


def _contract_rows(data: Mapping[str, Any], profile: ProviderProfile) -> list[Mapping[str, Any]]:
    if profile == "polygon_snapshot_like":
        return _mapping_rows(data.get("results") or data.get("snapshots"))
    if profile == "tradier_like":
        options = data.get("options")
        if isinstance(options, Mapping):
            return _mapping_rows(options.get("option"))
        return _mapping_rows(data.get("option") or options)
    return _mapping_rows(data.get("contracts") or data.get("options"))


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [item for item in value if isinstance(item, Mapping)]
    return []


def _normalize_contract(
    row: Mapping[str, Any],
    *,
    index: int,
    profile: ProviderProfile,
    symbol: str,
    chain_as_of: str,
    chain_source: str,
    chain_freshness: str,
    provider_quality: str,
    spot: float | None,
) -> NormalizedOptionContract:
    if profile == "polygon_snapshot_like":
        return _normalize_polygon_snapshot_contract(
            row,
            index=index,
            symbol=symbol,
            chain_as_of=chain_as_of,
            chain_source=chain_source,
            chain_freshness=chain_freshness,
            provider_quality=provider_quality,
            spot=spot,
        )
    return _normalize_flat_contract(
        row,
        index=index,
        profile=profile,
        symbol=symbol,
        chain_as_of=chain_as_of,
        chain_source=chain_source,
        chain_freshness=chain_freshness,
        provider_quality=provider_quality,
        spot=spot,
    )


def _normalize_polygon_snapshot_contract(
    row: Mapping[str, Any],
    *,
    index: int,
    symbol: str,
    chain_as_of: str,
    chain_source: str,
    chain_freshness: str,
    provider_quality: str,
    spot: float | None,
) -> NormalizedOptionContract:
    details = _mapping_or_empty(row.get("details"))
    quote = _mapping_or_empty(row.get("last_quote") or row.get("lastQuote"))
    trade = _mapping_or_empty(row.get("last_trade") or row.get("lastTrade"))
    day = _mapping_or_empty(row.get("day"))
    contract_symbol = _text(
        _coalesce_present(
            _first_present(details, ("ticker", "contractSymbol", "contract_symbol")),
            _first_present(row, ("ticker", "contractSymbol", "contract_symbol", "symbol")),
        )
    )
    side = _normalize_side(
        _coalesce_present(
            _first_present(details, ("contract_type", "contractType", "side")),
            _first_present(row, ("contract_type", "contractType", "side")),
        ),
        contract_symbol=contract_symbol,
    )
    expiration = _optional_text(
        _coalesce_present(
            _first_present(details, ("expiration_date", "expirationDate", "expiration")),
            _first_present(row, ("expiration_date", "expirationDate", "expiration")),
        )
    )
    bid = _float_or_none(_first_present(quote, ("bid", "bid_price", "bidPrice")))
    ask = _float_or_none(_first_present(quote, ("ask", "ask_price", "askPrice")))
    return _contract(
        symbol=symbol,
        contract_symbol=contract_symbol,
        side=side,
        expiration=expiration,
        strike=_float_or_none(
            _coalesce_present(
                _first_present(details, ("strike_price", "strikePrice", "strike")),
                _first_present(row, ("strike_price", "strikePrice", "strike")),
            )
        ),
        multiplier=_positive_int_or_none(
            _coalesce_present(
                _first_present(details, ("shares_per_contract", "sharesPerContract", "multiplier")),
                _first_present(row, ("shares_per_contract", "sharesPerContract", "multiplier")),
            )
        ),
        bid=bid,
        ask=ask,
        last=_float_or_none(
            _coalesce_present(
                _first_present(trade, ("price", "last", "last_price", "lastPrice")),
                _first_present(row, ("last", "last_price", "lastPrice")),
                _first_present(day, ("close", "last", "price")),
            )
        ),
        volume=_non_negative_int_or_none(
            _coalesce_present(
                _first_present(day, ("volume",)),
                _first_present(row, ("volume", "day_volume", "dayVolume")),
            )
        ),
        open_interest=_non_negative_int_or_none(
            _first_present(row, ("open_interest", "openInterest"))
        ),
        implied_volatility=_float_or_none(
            _first_present(row, ("implied_volatility", "impliedVolatility"))
        ),
        greeks=_normalize_greeks(_mapping_or_empty(row.get("greeks"))),
        as_of=_text(
            _coalesce_present(
                _first_present(quote, ("last_updated", "lastUpdated", "asOf", "as_of")),
                _first_present(trade, ("sip_timestamp", "timestamp", "asOf", "as_of")),
                _first_present(row, ("asOf", "as_of")),
                chain_as_of,
            )
        ),
        source=_text(_first_present(row, ("source",)) or chain_source),
        freshness=_text(_first_present(row, ("freshness",)) or chain_freshness),
        provider_quality=provider_quality,
        data_quality=_contract_data_quality(row),
        warnings=list(row.get("warnings") or []),
        spot=spot,
    )


def _normalize_flat_contract(
    row: Mapping[str, Any],
    *,
    index: int,
    profile: ProviderProfile,
    symbol: str,
    chain_as_of: str,
    chain_source: str,
    chain_freshness: str,
    provider_quality: str,
    spot: float | None,
) -> NormalizedOptionContract:
    del index
    contract_symbol = _text(
        _first_present(row, ("contractSymbol", "contract_symbol", "symbol", "ticker"))
    )
    side = _normalize_side(
        _first_present(row, ("side", "option_type", "optionType", "type", "contract_type")),
        contract_symbol=contract_symbol,
    )
    expiration = _optional_text(
        _first_present(row, ("expiration", "expiration_date", "expirationDate"))
    )
    greeks_payload = _mapping_or_empty(row.get("greeks"))
    implied_volatility = _float_or_none(
        _coalesce_present(
            _first_present(row, ("impliedVolatility", "implied_volatility", "iv")),
            _first_present(greeks_payload, ("mid_iv", "midIv", "smv_vol", "smvVol")),
        )
    )
    return _contract(
        symbol=symbol,
        contract_symbol=contract_symbol,
        side=side,
        expiration=expiration,
        strike=_float_or_none(_first_present(row, ("strike", "strike_price", "strikePrice"))),
        multiplier=_positive_int_or_none(
            _first_present(row, ("multiplier", "shares_per_contract", "sharesPerContract"))
        ),
        bid=_float_or_none(_first_present(row, ("bid", "bid_price", "bidPrice"))),
        ask=_float_or_none(_first_present(row, ("ask", "ask_price", "askPrice"))),
        last=_float_or_none(_first_present(row, ("last", "last_price", "lastPrice", "close"))),
        volume=_non_negative_int_or_none(_first_present(row, ("volume",))),
        open_interest=_non_negative_int_or_none(
            _first_present(row, ("openInterest", "open_interest"))
        ),
        implied_volatility=implied_volatility,
        greeks=_normalize_greeks(greeks_payload, fallback=row),
        as_of=_text(
            _first_present(row, ("asOf", "as_of", "trade_date", "timestamp", "last_updated"))
            or chain_as_of
        ),
        source=_text(_first_present(row, ("source",)) or chain_source),
        freshness=_text(_first_present(row, ("freshness",)) or chain_freshness),
        provider_quality=_text(_first_present(row, ("providerQuality", "provider_quality")) or provider_quality),
        data_quality=_contract_data_quality(row),
        warnings=_dedupe(
            [
                *list(row.get("warnings") or []),
                *(["tradier_like_shape"] if profile == "tradier_like" else []),
            ]
        ),
        spot=spot,
    )


def _contract(
    *,
    symbol: str,
    contract_symbol: str,
    side: str | None,
    expiration: str | None,
    strike: float | None,
    multiplier: int | None,
    bid: float | None,
    ask: float | None,
    last: float | None,
    volume: int | None,
    open_interest: int | None,
    implied_volatility: float | None,
    greeks: NormalizedOptionGreeks | None,
    as_of: str,
    source: str,
    freshness: str,
    provider_quality: str,
    data_quality: dict[str, Any],
    warnings: list[str],
    spot: float | None,
) -> NormalizedOptionContract:
    mid = _mid(bid, ask)
    spread_pct = _spread_pct(bid, ask, mid)
    return NormalizedOptionContract(
        symbol=symbol,
        contract_symbol=contract_symbol,
        side=side,
        expiration=expiration,
        strike=strike,
        multiplier=multiplier,
        bid=bid,
        ask=ask,
        mid=mid,
        last=last,
        volume=volume,
        open_interest=open_interest,
        implied_volatility=implied_volatility,
        greeks=greeks,
        dte=_dte(expiration, as_of),
        moneyness=_moneyness(side, strike, spot),
        spread_pct=spread_pct,
        liquidity_bucket=_liquidity_bucket(spread_pct, open_interest),
        as_of=as_of,
        source=source,
        freshness=freshness or "unknown",
        provider_quality=provider_quality,
        data_quality=data_quality,
        warnings=_dedupe(
            [
                *warnings,
                "observation_only_not_decision_grade",
                *(["freshness_unknown"] if (freshness or "unknown") == "unknown" else []),
            ]
        ),
    )


def _normalize_greeks(
    greeks: Mapping[str, Any],
    fallback: Mapping[str, Any] | None = None,
) -> NormalizedOptionGreeks | None:
    fallback = fallback or {}
    values = {
        "delta": _float_or_none(_coalesce_present(_first_present(greeks, ("delta",)), fallback.get("delta"))),
        "gamma": _non_negative_float_or_none(
            _coalesce_present(_first_present(greeks, ("gamma",)), fallback.get("gamma"))
        ),
        "vega": _float_or_none(_coalesce_present(_first_present(greeks, ("vega",)), fallback.get("vega"))),
        "theta": _float_or_none(_coalesce_present(_first_present(greeks, ("theta",)), fallback.get("theta"))),
        "rho": _float_or_none(_coalesce_present(_first_present(greeks, ("rho",)), fallback.get("rho"))),
    }
    if all(value is None for value in values.values()):
        return None
    return NormalizedOptionGreeks(**values)


def _missing_evidence(
    contracts: Sequence[NormalizedOptionContract],
    spot: float | None,
) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    if spot is None:
        missing.append(_missing("missing_spot_reference", "underlying_spot"))
    if not contracts:
        missing.append(_missing("missing_contracts", "contracts"))
        return missing
    for index, contract in enumerate(contracts):
        contract_symbol = contract.contract_symbol or f"contract_{index}"
        if contract.side not in {"call", "put"}:
            missing.append(_missing("missing_side", "side", contract_symbol, index))
        if contract.strike is None:
            missing.append(_missing("missing_strike", "strike", contract_symbol, index))
        if not contract.expiration:
            missing.append(_missing("missing_expiration", "expiration", contract_symbol, index))
        if contract.open_interest is None:
            missing.append(_missing("missing_open_interest", "open_interest", contract_symbol, index))
        if contract.greeks is None or contract.greeks.gamma is None:
            missing.append(_missing("missing_gamma", "greeks.gamma", contract_symbol, index))
        if contract.multiplier is None:
            missing.append(_missing("missing_multiplier", "multiplier", contract_symbol, index))
    return missing


def _missing(
    code: str,
    field_name: str,
    contract_symbol: str | None = None,
    index: int | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "field": field_name,
        "contractSymbol": contract_symbol,
        "contractIndex": index,
    }


def _coverage(
    contracts: Sequence[NormalizedOptionContract],
    spot: float | None,
) -> dict[str, Any]:
    total = len(contracts)
    return {
        "totalContracts": total,
        "spotReferenceCoveragePct": 100.0 if spot is not None else 0.0,
        "sideCoveragePct": _pct(sum(1 for item in contracts if item.side in {"call", "put"}), total),
        "strikeCoveragePct": _pct(sum(1 for item in contracts if item.strike is not None), total),
        "expirationCoveragePct": _pct(sum(1 for item in contracts if item.expiration), total),
        "bidAskCoveragePct": _pct(sum(1 for item in contracts if item.bid is not None and item.ask is not None), total),
        "volumeCoveragePct": _pct(sum(1 for item in contracts if item.volume is not None), total),
        "openInterestCoveragePct": _pct(sum(1 for item in contracts if item.open_interest is not None), total),
        "ivCoveragePct": _pct(sum(1 for item in contracts if item.implied_volatility is not None), total),
        "gammaCoveragePct": _pct(
            sum(1 for item in contracts if item.greeks is not None and item.greeks.gamma is not None),
            total,
        ),
        "multiplierCoveragePct": _pct(sum(1 for item in contracts if item.multiplier is not None), total),
    }


def _data_quality_labels(freshness: str) -> list[str]:
    text = freshness.strip().lower()
    if text in {"fresh", "live", "realtime", "real_time", "real-time"}:
        return ["live"]
    if any(marker in text for marker in ("delayed", "stale", "cached", "dry_run", "dry-run")):
        return ["delayed"]
    if any(marker in text for marker in ("fixture", "synthetic", "mock", "proxy", "fallback")):
        return ["proxy"]
    return ["unavailable"]


def _contract_data_quality(row: Mapping[str, Any]) -> dict[str, Any]:
    data_quality = row.get("dataQuality") or row.get("data_quality")
    if isinstance(data_quality, Mapping):
        return dict(data_quality)
    return {
        "tradeable": False,
        "normalizer": NORMALIZER_VERSION,
    }


def _normalize_side(value: Any, *, contract_symbol: str) -> str | None:
    text = _text(value).lower()
    if text in {"call", "calls", "c"}:
        return "call"
    if text in {"put", "puts", "p"}:
        return "put"
    match = re.search(r"\d{6}([CP])\d{8}$", contract_symbol)
    if match:
        return "call" if match.group(1) == "C" else "put"
    return None


def _normalize_symbol(value: Any) -> str:
    return re.sub(r"\s+", "", _text(value)).upper()


def _first_present(payload: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in payload and payload.get(key) not in (None, ""):
            return payload.get(key)
    return None


def _coalesce_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _positive_float_or_none(value: Any) -> float | None:
    parsed = _float_or_none(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def _non_negative_float_or_none(value: Any) -> float | None:
    parsed = _float_or_none(value)
    if parsed is None or parsed < 0:
        return None
    return parsed


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _positive_int_or_none(value: Any) -> int | None:
    parsed = _int_or_none(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def _non_negative_int_or_none(value: Any) -> int | None:
    parsed = _int_or_none(value)
    if parsed is None or parsed < 0:
        return None
    return parsed


def _optional_text(value: Any) -> str | None:
    text = _text(value)
    return text or None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mid(bid: float | None, ask: float | None) -> float | None:
    if bid is None or ask is None:
        return None
    return round((bid + ask) / 2, 4)


def _spread_pct(bid: float | None, ask: float | None, mid: float | None) -> float | None:
    if bid is None or ask is None or mid in (None, 0):
        return None
    return round(((ask - bid) / mid) * 100, 2)


def _moneyness(side: str | None, strike: float | None, spot: float | None) -> str:
    if not side or strike is None or spot is None:
        return "unknown"
    if abs(strike - spot) / spot <= 0.03:
        return "atm"
    if side == "call":
        return "itm" if strike < spot else "otm"
    if side == "put":
        return "itm" if strike > spot else "otm"
    return "unknown"


def _liquidity_bucket(spread_pct: float | None, open_interest: int | None) -> str:
    if spread_pct is None or open_interest is None:
        return "unknown"
    if spread_pct <= 10 and open_interest >= 500:
        return "tight"
    if spread_pct <= 25 and open_interest >= 100:
        return "moderate"
    return "thin"


def _dte(expiration: str | None, as_of: str) -> int | None:
    if not expiration or not as_of:
        return None
    try:
        expiration_date = date.fromisoformat(expiration[:10])
        as_of_date = datetime.fromisoformat(as_of.replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return None
    return max((expiration_date - as_of_date).days, 0)


def _pct(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((count / total) * 100.0, 2)


def _dedupe(values: Sequence[Any]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered
