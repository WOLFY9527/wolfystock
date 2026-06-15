# -*- coding: utf-8 -*-
"""Pure adapter from normalized option chains to gamma observations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.services.options_market_structure_observation import (
    GEX_FORMULA,
    GEX_FORMULA_ID,
    GEX_UNIT_CONVENTION,
    SIGN_CONVENTION,
    build_options_market_structure_observation,
)


ADAPTER_NAME = "optionsChainGammaObservationAdapter"
ADAPTER_VERSION = "options-chain-gamma-observation-adapter-v1"
DATA_REQUIREMENTS = [
    "underlying",
    "spot",
    "expiration",
    "strike",
    "side",
    "openInterest",
    "gamma",
    "multiplier",
    "asOf",
    "freshness",
]
_CORE_BLOCKING_CODES = {
    "missing_underlying",
    "missing_spot_reference",
    "missing_contracts",
    "missing_side",
    "missing_strike",
    "missing_expiration",
    "missing_gamma",
    "missing_open_interest",
    "missing_multiplier",
}
_UNKNOWN_FRESHNESS = {"", "unknown", "unavailable"}
_DEGRADED_FRESHNESS_MARKERS = ("stale", "delayed", "cached", "fallback", "fixture", "synthetic", "mock")


def build_options_chain_gamma_observation(
    normalized_chain: Any,
    *,
    methodology_approved: bool | None = None,
    coverage_thresholds_defined: bool | None = None,
    provider_authority_verified: bool | None = None,
    redistribution_rights_verified: bool | None = None,
    decision_use_rights_verified: bool | None = None,
    deliverable_handling_reviewed: bool | None = None,
) -> dict[str, Any]:
    """Build an observation-only gamma/GEX payload from a normalized chain.

    The adapter is side-effect free. It does not fetch live data, read provider
    credentials, fill missing fields, or promote the result to decision grade.
    """

    metadata = _mapping(_value(normalized_chain, "metadata"))
    contracts = _contracts(normalized_chain)
    underlying = _text(_value(normalized_chain, "underlying_symbol", "underlyingSymbol", "symbol"))
    spot = _float(_value(normalized_chain, "underlying_spot", "underlyingSpot", "spot"))
    if spot is None:
        spot_reference = _mapping(_value(normalized_chain, "spot_reference", "spotReference"))
        spot = _float(_value(spot_reference, "spot", "price", "value"))
    chain_as_of = _text(
        _coalesce(
            _value(normalized_chain, "chain_as_of", "chainAsOf", "as_of", "asOf"),
            _value(metadata, "asOf", "as_of"),
        )
    )
    freshness = _text(
        _coalesce(
            _value(normalized_chain, "freshness"),
            _value(metadata, "freshness"),
        )
    )
    source = _text(_coalesce(_value(normalized_chain, "source"), _value(metadata, "source")))
    data_quality_labels = _data_quality_labels(normalized_chain, freshness)

    adapter_missing = _adapter_missing_evidence(
        underlying=underlying,
        spot=spot,
        chain_as_of=chain_as_of,
        chain_freshness=freshness,
        contracts=contracts,
    )
    flags = {
        "methodology_approved": _bool_or_metadata(
            methodology_approved,
            metadata,
            "methodologyApproved",
            "methodology_approved",
        ),
        "coverage_thresholds_defined": _bool_or_metadata(
            coverage_thresholds_defined,
            metadata,
            "coverageThresholdsDefined",
            "coverage_thresholds_defined",
        ),
        "provider_authority_verified": _bool_or_metadata(
            provider_authority_verified,
            metadata,
            "providerAuthorityVerified",
            "provider_authority_verified",
        ),
        "redistribution_rights_verified": _bool_or_metadata(
            redistribution_rights_verified,
            metadata,
            "redistributionRightsVerified",
            "redistribution_rights_verified",
        ),
        "decision_use_rights_verified": _bool_or_metadata(
            decision_use_rights_verified,
            metadata,
            "decisionUseRightsVerified",
            "decision_use_rights_verified",
        ),
        "deliverable_handling_reviewed": _bool_or_metadata(
            deliverable_handling_reviewed,
            metadata,
            "deliverableHandlingReviewed",
            "deliverable_handling_reviewed",
        ),
    }

    observation = build_options_market_structure_observation(
        contracts,
        spot=spot,
        as_of=chain_as_of or None,
        data_quality_label=data_quality_labels,
        **flags,
    )
    missing_evidence = _merge_missing(adapter_missing, observation.get("missingEvidence"))
    blocked_reason_codes = _dedupe(
        [
            *list(observation.get("blockedReasonCodes") or []),
            *(item["code"] for item in missing_evidence if item.get("code")),
        ]
    )
    status = _status(
        observation_state=str(observation.get("observationState") or ""),
        missing_evidence=missing_evidence,
        blocked_reason_codes=blocked_reason_codes,
    )
    if status == "blocked":
        observation = _blocked_observation(observation, blocked_reason_codes, missing_evidence)

    methodology = dict(observation.get("methodology") or {})
    methodology.update(
        {
            "formula": methodology.get("formula") or GEX_FORMULA,
            "formulaId": methodology.get("formulaId") or GEX_FORMULA_ID,
            "unitConvention": methodology.get("unitConvention") or GEX_UNIT_CONVENTION,
            "signConvention": methodology.get("signConvention") or SIGN_CONVENTION,
            "observationOnly": True,
            "decisionGrade": False,
            "dataRequirements": list(DATA_REQUIREMENTS),
        }
    )
    observation["methodology"] = methodology

    return {
        "adapterName": ADAPTER_NAME,
        "adapterVersion": ADAPTER_VERSION,
        "status": status,
        "underlying": underlying or None,
        "spot": spot,
        "chainAsOf": chain_as_of or None,
        "freshness": freshness or "unknown",
        "source": source or None,
        "observationOnly": True,
        "decisionGrade": False,
        "decisionGradeBlocked": True,
        "inputRecords": [_input_record(contract, underlying=underlying, spot=spot) for contract in contracts],
        "missingEvidence": missing_evidence,
        "blockedReasonCodes": blocked_reason_codes,
        "dataQualityLabels": data_quality_labels,
        "methodology": methodology,
        "rights": {
            "providerAuthorityVerified": flags["provider_authority_verified"],
            "redistributionRightsVerified": flags["redistribution_rights_verified"],
            "decisionUseRightsVerified": flags["decision_use_rights_verified"],
        },
        "observation": observation,
    }


def _adapter_missing_evidence(
    *,
    underlying: str,
    spot: float | None,
    chain_as_of: str,
    chain_freshness: str,
    contracts: Sequence[Any],
) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    if not underlying:
        missing.append(_missing("missing_underlying", "underlying"))
    if spot is None or spot <= 0:
        missing.append(_missing("missing_spot_reference", "spot"))
    if not chain_as_of:
        missing.append(_missing("missing_as_of", "asOf"))
    missing.extend(_freshness_evidence(chain_freshness))
    if not contracts:
        missing.append(_missing("missing_contracts", "contracts"))
        return missing

    for index, contract in enumerate(contracts):
        contract_symbol = _contract_symbol(contract, index)
        side = _text(_value(contract, "side")).lower()
        if side not in {"call", "put"}:
            missing.append(_missing("missing_side", "side", contract_symbol, index))
        if _float(_value(contract, "strike")) is None:
            missing.append(_missing("missing_strike", "strike", contract_symbol, index))
        if not _text(_value(contract, "expiration", "expiration_date", "expirationDate")):
            missing.append(_missing("missing_expiration", "expiration", contract_symbol, index))
        if _gamma(contract) is None:
            missing.append(_missing("missing_gamma", "gamma", contract_symbol, index))
        if _open_interest(contract) is None:
            missing.append(_missing("missing_open_interest", "openInterest", contract_symbol, index))
        if _multiplier(contract) is None:
            missing.append(_missing("missing_multiplier", "multiplier", contract_symbol, index))
        if not _text(_value(contract, "as_of", "asOf")):
            missing.append(_missing("missing_as_of", "asOf", contract_symbol, index))
        missing.extend(
            _freshness_evidence(
                _text(_value(contract, "freshness")),
                contract_symbol=contract_symbol,
                contract_index=index,
            )
        )
    return _merge_missing(missing, [])


def _status(
    *,
    observation_state: str,
    missing_evidence: Sequence[Mapping[str, Any]],
    blocked_reason_codes: Sequence[str],
) -> str:
    codes = {str(item.get("code")) for item in missing_evidence if item.get("code")}
    if observation_state == "blocked" or codes & _CORE_BLOCKING_CODES:
        return "blocked"
    degraded_codes = codes | {str(code) for code in blocked_reason_codes}
    if observation_state == "degraded" or degraded_codes - {"observation_only_not_decision_grade"}:
        return "degraded"
    return "available"


def _blocked_observation(
    observation: Mapping[str, Any],
    blocked_reason_codes: Sequence[str],
    missing_evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    blocked = dict(observation)
    summary = dict(blocked.get("gexSummary") or {})
    summary.update(
        {
            "netGamma": None,
            "callGamma": None,
            "putGamma": None,
            "grossGamma": None,
            "unit": summary.get("unit") or GEX_UNIT_CONVENTION,
            "formulaId": summary.get("formulaId") or GEX_FORMULA_ID,
        }
    )
    blocked.update(
        {
            "observationState": "blocked",
            "gammaRegime": "blocked",
            "gammaFlipLevel": None,
            "gammaFlipInterval": None,
            "gexSummary": summary,
            "callWall": None,
            "putWall": None,
            "topGammaStrikes": [],
            "zeroDTEGammaShare": {
                "available": False,
                "reason": "insufficient_gamma_observation_evidence",
            },
            "missingEvidence": [dict(item) for item in missing_evidence],
            "blockedReasonCodes": list(blocked_reason_codes),
        }
    )
    return blocked


def _input_record(contract: Any, *, underlying: str, spot: float | None) -> dict[str, Any]:
    return {
        "underlying": underlying or None,
        "spot": spot,
        "contractSymbol": _text(_value(contract, "contract_symbol", "contractSymbol", "symbol")) or None,
        "expiration": _text(_value(contract, "expiration", "expiration_date", "expirationDate")) or None,
        "strike": _float(_value(contract, "strike")),
        "side": _text(_value(contract, "side")).lower() or None,
        "openInterest": _open_interest(contract),
        "gamma": _gamma(contract),
        "multiplier": _multiplier(contract),
        "asOf": _text(_value(contract, "as_of", "asOf")) or None,
        "freshness": _text(_value(contract, "freshness")) or "unknown",
    }


def _freshness_evidence(
    freshness: str,
    *,
    contract_symbol: str | None = None,
    contract_index: int | None = None,
) -> list[dict[str, Any]]:
    text = freshness.strip().lower()
    if text in _UNKNOWN_FRESHNESS:
        return [_missing("unknown_freshness", "freshness", contract_symbol, contract_index)]
    if any(marker in text for marker in _DEGRADED_FRESHNESS_MARKERS):
        return [_missing("stale_freshness", "freshness", contract_symbol, contract_index)]
    return []


def _data_quality_labels(chain: Any, freshness: str) -> list[str]:
    labels = _value(chain, "data_quality_labels", "dataQualityLabels")
    if isinstance(labels, Sequence) and not isinstance(labels, (str, bytes, bytearray)):
        cleaned = [_text(label) for label in labels if _text(label)]
        if cleaned:
            return cleaned
    return [freshness or "unknown"]


def _contracts(chain: Any) -> list[Any]:
    contracts = _value(chain, "contracts")
    if contracts is None:
        contracts = [*_sequence(_value(chain, "calls")), *_sequence(_value(chain, "puts"))]
    return _sequence(contracts)


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _value(source: Any, *names: str) -> Any:
    if source is None:
        return None
    for name in names:
        if isinstance(source, Mapping) and name in source:
            return source.get(name)
        if hasattr(source, name):
            return getattr(source, name)
    return None


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _gamma(contract: Any) -> float | None:
    greeks = _value(contract, "greeks")
    gamma = _float(_value(greeks, "gamma"))
    if gamma is None:
        gamma = _float(_value(contract, "gamma"))
    if gamma is None or gamma < 0:
        return None
    return gamma


def _open_interest(contract: Any) -> int | None:
    value = _float(_value(contract, "open_interest", "openInterest"))
    if value is None or value < 0:
        return None
    return int(value)


def _multiplier(contract: Any) -> int | None:
    value = _float(_value(contract, "multiplier"))
    if value is None or value <= 0:
        return None
    return int(value)


def _contract_symbol(contract: Any, index: int) -> str:
    return _text(_value(contract, "contract_symbol", "contractSymbol", "symbol")) or f"contract_{index}"


def _missing(
    code: str,
    field_name: str,
    contract_symbol: str | None = None,
    contract_index: int | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "field": field_name,
        "contractSymbol": contract_symbol,
        "contractIndex": contract_index,
    }


def _merge_missing(*groups: Any) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any, Any]] = set()
    for group in groups:
        if not isinstance(group, Sequence) or isinstance(group, (str, bytes, bytearray)):
            continue
        for item in group:
            if not isinstance(item, Mapping):
                continue
            normalized = dict(item)
            key = (
                normalized.get("code"),
                normalized.get("field"),
                normalized.get("contractSymbol"),
                normalized.get("contractIndex"),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(normalized)
    return merged


def _bool_or_metadata(explicit: bool | None, metadata: Mapping[str, Any], *keys: str) -> bool:
    if explicit is not None:
        return bool(explicit)
    for key in keys:
        if key in metadata:
            return bool(metadata.get(key))
    return False


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
