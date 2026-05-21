# -*- coding: utf-8 -*-
"""Inert custom source contracts for future panel-specific runtime wiring.

This module is metadata and fixture parsing only. It must not call networks,
read credentials, import runtime panel services, alter Settings behavior, or
enable custom API routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from src.services.provider_unavailable_reason_buckets import (
    CUSTOM_SOURCE_REASON_BUCKET_RULES,
    CUSTOM_SOURCE_REASON_MARKER_KEYS,
    explicit_unavailable_reason_bucket,
    safe_unavailable_reason_bucket,
)


SOURCE_TYPE_CUSTOM = "custom"
GENERIC_SAFE_PANEL_PARSER_ID = "generic_safe_panel_v1"
DEFAULT_CUSTOM_SOURCE_DISABLED_REASON = (
    "Custom source contracts stay disabled until an explicit runtime allowlist and panel binding ship."
)
SAFE_UNAVAILABLE_REASON_BUCKETS = (
    "missing_credentials",
    "permission_denied",
    "empty_payload",
    "malformed_payload",
    "temporarily_unavailable",
)


@dataclass(frozen=True)
class CustomSourceContract:
    custom_source_id: str
    panel_id: str
    parser_id: str
    capability: str
    allowed_symbols: tuple[str, ...]
    series_ids: tuple[str, ...]
    source_type: str
    freshness_window: str
    runtime_eligible: bool
    disabled_reason: str
    credential_ref: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "customSourceId": self.custom_source_id,
            "panelId": self.panel_id,
            "parserId": self.parser_id,
            "capability": self.capability,
            "allowedSymbols": list(self.allowed_symbols),
            "seriesIds": list(self.series_ids),
            "sourceType": self.source_type,
            "freshnessWindow": self.freshness_window,
            "runtimeEligible": self.runtime_eligible,
            "disabledReason": self.disabled_reason,
            "credentialRef": self.credential_ref,
        }


@dataclass(frozen=True)
class CustomSourceParserContract:
    parser_id: str
    target_dto_family: str
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...]
    unavailable_reason_buckets: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "parserId": self.parser_id,
            "targetDtoFamily": self.target_dto_family,
            "requiredFields": list(self.required_fields),
            "optionalFields": list(self.optional_fields),
            "unavailableReasonBuckets": list(self.unavailable_reason_buckets),
        }


_PARSER_CONTRACTS = (
    CustomSourceParserContract(
        parser_id=GENERIC_SAFE_PANEL_PARSER_ID,
        target_dto_family="generic_panel_series_v1",
        required_fields=("symbol", "seriesId", "value", "asOf"),
        optional_fields=("label", "unit"),
        unavailable_reason_buckets=SAFE_UNAVAILABLE_REASON_BUCKETS,
    ),
)
_PARSER_CONTRACTS_BY_ID = MappingProxyType({item.parser_id: item for item in _PARSER_CONTRACTS})


def list_custom_source_parser_contracts() -> tuple[CustomSourceParserContract, ...]:
    """Return deterministic parser contracts for custom-source fixtures."""
    return tuple(_PARSER_CONTRACTS)


def get_custom_source_parser_contract(parser_id: str | None) -> CustomSourceParserContract | None:
    """Look up a parser contract by id."""
    normalized = _text(parser_id)
    if not normalized:
        return None
    return _PARSER_CONTRACTS_BY_ID.get(normalized)


def normalize_custom_source_contract(payload: Any) -> dict[str, Any]:
    """Normalize a stored custom-source entry into a disabled contract record."""
    if not isinstance(payload, Mapping):
        raise ValueError("Custom source contract payload must be an object")

    parser_id = _required_text(payload, "parserId", "parser_id")
    parser_contract = get_custom_source_parser_contract(parser_id)
    if parser_contract is None:
        raise ValueError(f"Unknown parserId: {parser_id}")

    allowed_symbols = _normalized_text_list(payload.get("allowedSymbols", payload.get("allowed_symbols")))
    series_ids = _normalized_text_list(payload.get("seriesIds", payload.get("series_ids")))
    if not allowed_symbols and not series_ids:
        raise ValueError("Missing symbol or series mapping")

    contract = CustomSourceContract(
        custom_source_id=_required_text(payload, "customSourceId", "custom_source_id"),
        panel_id=_required_text(payload, "panelId", "panel_id"),
        parser_id=parser_contract.parser_id,
        capability=_required_text(payload, "capability"),
        allowed_symbols=allowed_symbols,
        series_ids=series_ids,
        source_type=SOURCE_TYPE_CUSTOM,
        freshness_window=_required_text(payload, "freshnessWindow", "freshness_window"),
        runtime_eligible=False,
        disabled_reason=DEFAULT_CUSTOM_SOURCE_DISABLED_REASON,
        credential_ref=_optional_text(payload, "credentialRef", "credential_ref"),
    )
    return contract.to_dict()


def parse_custom_source_fixture_payload(parser_id: str, payload: Any) -> dict[str, Any]:
    """Parse the mocked fixture-only payload for a supported custom parser."""
    parser_contract = get_custom_source_parser_contract(parser_id)
    if parser_contract is None:
        raise ValueError(f"Unknown parserId: {parser_id}")

    unavailable_reason = _explicit_reason_bucket(payload)
    if unavailable_reason is not None:
        return _build_unavailable_parser_result(parser_contract, unavailable_reason)
    if not isinstance(payload, Mapping):
        return _build_unavailable_parser_result(parser_contract, "malformed_payload")

    observations = payload.get("observations")
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
        return _build_unavailable_parser_result(parser_contract, "malformed_payload")
    if not observations:
        return _build_unavailable_parser_result(parser_contract, "empty_payload")

    normalized_observations: list[dict[str, Any]] = []
    for raw_item in observations:
        if not isinstance(raw_item, Mapping):
            return _build_unavailable_parser_result(parser_contract, "malformed_payload")
        observation = {
            "symbol": _required_payload_text(raw_item, "symbol"),
            "seriesId": _required_payload_text(raw_item, "seriesId"),
            "value": _required_number(raw_item.get("value")),
            "asOf": _required_payload_text(raw_item, "asOf"),
        }
        label = _text(raw_item.get("label"))
        unit = _text(raw_item.get("unit"))
        if label:
            observation["label"] = label
        if unit:
            observation["unit"] = unit
        normalized_observations.append(observation)

    return {
        "parserId": parser_contract.parser_id,
        "targetDtoFamily": parser_contract.target_dto_family,
        "isEvidence": True,
        "unavailableReason": None,
        "observations": normalized_observations,
    }


def _build_unavailable_parser_result(
    parser_contract: CustomSourceParserContract,
    reason_bucket: str,
) -> dict[str, Any]:
    return {
        "parserId": parser_contract.parser_id,
        "targetDtoFamily": parser_contract.target_dto_family,
        "isEvidence": False,
        "unavailableReason": _safe_reason_bucket(reason_bucket),
        "observations": [],
    }


def _explicit_reason_bucket(payload: Any) -> str | None:
    return explicit_unavailable_reason_bucket(
        payload,
        marker_keys=CUSTOM_SOURCE_REASON_MARKER_KEYS,
        reason_bucket_rules=CUSTOM_SOURCE_REASON_BUCKET_RULES,
        include_error_markers=False,
    )


def _safe_reason_bucket(value: Any) -> str:
    return safe_unavailable_reason_bucket(value, SAFE_UNAVAILABLE_REASON_BUCKETS)


def _required_payload_text(payload: Mapping[str, Any], key: str) -> str:
    value = _text(payload.get(key))
    if not value:
        raise ValueError(f"Fixture observation field is required: {key}")
    return value


def _required_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Fixture observation value must be numeric") from exc


def _required_text(payload: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = _text(payload.get(key))
        if value:
            return value
    raise ValueError(f"Missing required custom source field: {keys[0]}")


def _optional_text(payload: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = _text(payload.get(key))
        if value:
            return value
    return None


def _normalized_text_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, str)):
        items = list(value)
    else:
        return ()

    normalized: list[str] = []
    for item in items:
        text = _text(item)
        if text and text not in normalized:
            normalized.append(text)
    return tuple(normalized)


def _text(value: Any) -> str:
    return str(value or "").strip()
