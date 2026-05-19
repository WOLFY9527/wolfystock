# -*- coding: utf-8 -*-
"""Pure Coinbase public market data fixture parser.

This module is parser-only. It accepts already-loaded Coinbase public ticker
fixture payloads and returns normalized observation-only records plus
deterministic parse warnings. It must not read env vars, perform network calls,
or affect runtime provider wiring.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping


COINBASE_PUBLIC_PROVIDER_NAME = "Coinbase Public"
COINBASE_PUBLIC_PROVIDER_ID = "coinbase_public"
COINBASE_PUBLIC_SOURCE_TIER = "exchange_public"
COINBASE_PUBLIC_TRUST_LEVEL = "usable_with_caution"
COINBASE_PUBLIC_FRESHNESS_EXPECTATION = "near_real_time_venue_scoped"
COINBASE_PUBLIC_VENUE = "coinbase"


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_payload(payload: Mapping[str, Any] | str | bytes | bytearray | dict[str, Any]) -> Mapping[str, Any] | None:
    if isinstance(payload, Mapping):
        return payload
    if isinstance(payload, (bytes, bytearray)):
        try:
            payload = payload.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if isinstance(payload, str):
        try:
            loaded = json.loads(payload)
        except json.JSONDecodeError:
            return None
        if isinstance(loaded, Mapping):
            return loaded
    return None


def _mapping_get(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _extract_product_id(payload: Mapping[str, Any], ticker_payload: Mapping[str, Any]) -> str | None:
    product_payload = _mapping_get(payload, "product")
    if isinstance(product_payload, Mapping):
        value = _mapping_get(product_payload, "product_id", "productId", "id", "symbol")
        text = _clean_text(value)
        if text:
            return text

    for mapping in (payload, ticker_payload):
        value = _mapping_get(mapping, "product_id", "productId", "symbol")
        text = _clean_text(value)
        if text:
            return text
    return None


def _extract_base_quote(
    payload: Mapping[str, Any],
    ticker_payload: Mapping[str, Any],
    product_id: str | None,
) -> tuple[str | None, str | None]:
    for mapping in (payload, ticker_payload):
        base_currency = _clean_text(_mapping_get(mapping, "base_currency", "baseCurrency", "base"))
        quote_currency = _clean_text(_mapping_get(mapping, "quote_currency", "quoteCurrency", "quote"))
        if base_currency or quote_currency:
            return base_currency, quote_currency

    if not product_id:
        return None, None

    for separator in ("-", "/", "_"):
        if separator in product_id:
            base_currency, quote_currency = product_id.split(separator, 1)
            return _clean_text(base_currency), _clean_text(quote_currency)
    return None, None


def _build_source_ref(payload: Mapping[str, Any], product_id: str | None, source_ref: str | None) -> str:
    explicit = _clean_text(source_ref) or _clean_text(_mapping_get(payload, "sourceRef", "source_ref"))
    if explicit:
        return explicit
    return f"{COINBASE_PUBLIC_PROVIDER_ID}:products:{product_id or 'unknown_product'}:ticker"


@dataclass(frozen=True, slots=True)
class CoinbasePublicParseWarning:
    code: str
    message: str
    field_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "fieldName": self.field_name,
        }


@dataclass(frozen=True, slots=True)
class CoinbasePublicObservationRecord:
    product_id: str | None
    symbol: str | None
    base_currency: str | None
    quote_currency: str | None
    price: float | None
    bid: float | None
    ask: float | None
    volume: float | None
    as_of: str | None
    updated_at: str | None
    source_ref: str
    degradation_reason: str | None
    provider_name: str = COINBASE_PUBLIC_PROVIDER_NAME
    provider_id: str = COINBASE_PUBLIC_PROVIDER_ID
    source: str = COINBASE_PUBLIC_PROVIDER_ID
    source_tier: str = COINBASE_PUBLIC_SOURCE_TIER
    trust_level: str = COINBASE_PUBLIC_TRUST_LEVEL
    freshness_expectation: str = COINBASE_PUBLIC_FRESHNESS_EXPECTATION
    observation_only: bool = True
    score_contribution_allowed: bool = False
    venue: str = COINBASE_PUBLIC_VENUE

    def to_dict(self) -> dict[str, Any]:
        return {
            "providerName": self.provider_name,
            "providerId": self.provider_id,
            "source": self.source,
            "sourceTier": self.source_tier,
            "trustLevel": self.trust_level,
            "freshnessExpectation": self.freshness_expectation,
            "observationOnly": self.observation_only,
            "scoreContributionAllowed": self.score_contribution_allowed,
            "venue": self.venue,
            "productId": self.product_id,
            "symbol": self.symbol,
            "baseCurrency": self.base_currency,
            "quoteCurrency": self.quote_currency,
            "price": self.price,
            "bid": self.bid,
            "ask": self.ask,
            "volume": self.volume,
            "asOf": self.as_of,
            "updatedAt": self.updated_at,
            "sourceRef": self.source_ref,
            "degradationReason": self.degradation_reason,
        }


@dataclass(frozen=True, slots=True)
class CoinbasePublicTickerParseResult:
    records: tuple[CoinbasePublicObservationRecord, ...]
    warnings: tuple[CoinbasePublicParseWarning, ...]
    provider_name: str = COINBASE_PUBLIC_PROVIDER_NAME
    provider_id: str = COINBASE_PUBLIC_PROVIDER_ID
    source_tier: str = COINBASE_PUBLIC_SOURCE_TIER
    trust_level: str = COINBASE_PUBLIC_TRUST_LEVEL
    freshness_expectation: str = COINBASE_PUBLIC_FRESHNESS_EXPECTATION
    observation_only: bool = True
    score_contribution_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "providerName": self.provider_name,
            "providerId": self.provider_id,
            "sourceTier": self.source_tier,
            "trustLevel": self.trust_level,
            "freshnessExpectation": self.freshness_expectation,
            "observationOnly": self.observation_only,
            "scoreContributionAllowed": self.score_contribution_allowed,
            "records": [record.to_dict() for record in self.records],
            "warnings": [warning.to_dict() for warning in self.warnings],
        }


def parse_ticker_payload(
    payload: Mapping[str, Any] | str | bytes | bytearray | dict[str, Any],
    *,
    parser_timestamp: str | None = None,
    source_ref: str | None = None,
) -> CoinbasePublicTickerParseResult:
    """Parse a local Coinbase public ticker fixture into observation-only records."""

    payload_map = _coerce_payload(payload)
    if payload_map is None:
        return CoinbasePublicTickerParseResult(
            records=(),
            warnings=(
                CoinbasePublicParseWarning(
                    code="invalid_payload",
                    message="Coinbase public ticker payload must be a JSON object or mapping.",
                ),
            ),
        )

    ticker_payload_raw = _mapping_get(payload_map, "ticker")
    ticker_payload = ticker_payload_raw if isinstance(ticker_payload_raw, Mapping) else payload_map

    warnings: list[CoinbasePublicParseWarning] = []

    product_id = _extract_product_id(payload_map, ticker_payload)
    if product_id is None:
        warnings.append(
            CoinbasePublicParseWarning(
                code="missing_product_id",
                message="Coinbase public ticker fixture did not include a product identifier.",
                field_name="product_id",
            )
        )

    symbol = _clean_text(_mapping_get(payload_map, "symbol"))
    if symbol is None:
        symbol = product_id

    base_currency, quote_currency = _extract_base_quote(payload_map, ticker_payload, product_id)

    price_raw = _mapping_get(ticker_payload, "price")
    price = _normalize_number(price_raw)
    if price is None:
        warnings.append(
            CoinbasePublicParseWarning(
                code="missing_price",
                message="Coinbase public ticker fixture did not include a usable price.",
                field_name="price",
            )
        )

    numeric_fields = {
        "bid": _mapping_get(ticker_payload, "bid"),
        "ask": _mapping_get(ticker_payload, "ask"),
        "volume": _mapping_get(ticker_payload, "volume"),
    }
    normalized_numeric_fields: dict[str, float | None] = {}
    for field_name, raw_value in numeric_fields.items():
        normalized_value = _normalize_number(raw_value)
        normalized_numeric_fields[field_name] = normalized_value
        if raw_value not in (None, "") and normalized_value is None:
            warnings.append(
                CoinbasePublicParseWarning(
                    code="invalid_numeric_field",
                    message="Coinbase public ticker fixture contained an invalid numeric field.",
                    field_name=field_name,
                )
            )

    timestamp = _clean_text(
        _mapping_get(
            ticker_payload,
            "time",
            "timestamp",
            "updated_at",
            "updatedAt",
            "as_of",
            "asOf",
        )
    ) or _clean_text(_mapping_get(payload_map, "updatedAt", "updated_at", "asOf", "as_of", "timestamp"))
    if timestamp is None:
        warnings.append(
            CoinbasePublicParseWarning(
                code="missing_timestamp",
                message="Coinbase public ticker fixture did not include a timestamp.",
                field_name="time",
            )
        )

    as_of = timestamp or _clean_text(parser_timestamp)
    updated_at = timestamp or _clean_text(parser_timestamp)

    degradation_reason = None
    warning_codes = {warning.code for warning in warnings}
    if "missing_product_id" in warning_codes:
        degradation_reason = "product_id_missing"
    elif "missing_price" in warning_codes:
        degradation_reason = "price_missing"
    elif "missing_timestamp" in warning_codes and timestamp is None and parser_timestamp is None:
        degradation_reason = "timestamp_missing"
    elif warnings:
        degradation_reason = "partial_coverage"

    record = CoinbasePublicObservationRecord(
        product_id=product_id,
        symbol=symbol,
        base_currency=base_currency,
        quote_currency=quote_currency,
        price=price,
        bid=normalized_numeric_fields["bid"],
        ask=normalized_numeric_fields["ask"],
        volume=normalized_numeric_fields["volume"],
        as_of=as_of,
        updated_at=updated_at,
        source_ref=_build_source_ref(payload_map, product_id, source_ref),
        degradation_reason=degradation_reason,
    )
    return CoinbasePublicTickerParseResult(records=(record,), warnings=tuple(warnings))
