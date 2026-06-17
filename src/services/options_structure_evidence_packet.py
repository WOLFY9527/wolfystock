# -*- coding: utf-8 -*-
"""Pure options structure evidence packet composer.

The composer is intentionally offline-only. It consumes already-supplied option
structure rows and emits observation evidence without fetching provider data,
mutating storage, or attaching an API endpoint.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any


CONTRACT_VERSION = "options-structure-evidence-packet-v1"
NO_ADVICE_DISCLOSURE = (
    "Observation-only research context; not personalized financial advice and "
    "not an execution instruction."
)
_EXPIRY_CONCENTRATION_SHARE = 0.6
_OPEN_INTEREST_CONCENTRATION_SHARE = 0.4
_PUT_CALL_SKEW_RATIO = 1.35
_CALL_PUT_SKEW_RATIO = 0.75
_STALE_FRESHNESS_VALUES = {"stale", "cached", "delayed", "fallback"}


def build_options_structure_evidence_packet(input_packet: Mapping[str, Any]) -> dict:
    """Build a deterministic options-structure evidence packet.

    ``input_packet`` is treated as immutable and bounded. Unknown, raw,
    diagnostic, request, provider, and trace fields are not projected into the
    returned packet.
    """

    packet = input_packet if isinstance(input_packet, Mapping) else {}
    symbol = _safe_symbol(
        _text(_first_present(packet, ("symbol", "underlying", "underlyingSymbol")))
    )
    as_of = _text(_first_present(packet, ("asOf", "as_of", "chainAsOf", "chain_as_of"))) or None
    spot = _positive_float_or_none(
        _first_present(packet, ("spot", "underlyingSpot", "underlying_spot"))
    )
    contracts = _normalized_contracts(packet)
    total_open_interest = sum(contract["openInterest"] for contract in contracts)

    missing_inputs = _missing_inputs(
        symbol=symbol,
        as_of=as_of,
        contracts=contracts,
        total_open_interest=total_open_interest,
    )
    stale_inputs = _stale_inputs(contracts)
    expiry_evidence = _expiry_concentration_evidence(contracts, total_open_interest)
    open_interest_evidence = _open_interest_evidence(contracts, total_open_interest)
    skew_evidence = _put_call_skew_evidence(contracts)
    gamma_evidence, gamma_missing = _gamma_risk_evidence(contracts, spot)
    missing_inputs = _dedupe_evidence([*missing_inputs, *gamma_missing])
    structure_state = _structure_state(
        expiry_evidence=expiry_evidence,
        open_interest_evidence=open_interest_evidence,
        skew_evidence=skew_evidence,
        missing_inputs=missing_inputs,
    )

    return {
        "contractVersion": CONTRACT_VERSION,
        "symbol": symbol,
        "asOf": as_of,
        "structureState": structure_state,
        "expiryConcentrationEvidence": expiry_evidence,
        "openInterestEvidence": open_interest_evidence,
        "putCallSkewEvidence": skew_evidence,
        "gammaRiskEvidence": gamma_evidence,
        "staleInputs": stale_inputs,
        "missingInputs": missing_inputs,
        "confidenceCap": _confidence_cap(missing_inputs, stale_inputs, gamma_evidence),
        "observationBoundary": {
            "observationOnly": True,
            "decisionGrade": False,
            "noProviderCalls": True,
            "noStorageMutation": True,
            "endpointAttached": False,
        },
        "researchNextSteps": [
            "Compare expiry and open-interest concentration across verified snapshots.",
            "Add verified greeks before interpreting gamma-risk evidence.",
            "Review stale or missing inputs before downstream research use.",
        ],
        "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
    }


def _normalized_contracts(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[tuple[Any, str | None]] = []
    rows.extend(
        (item, None) for item in _sequence(_first_present(packet, ("contracts", "options")))
    )
    rows.extend((item, "call") for item in _sequence(_value(packet, "calls")))
    rows.extend((item, "put") for item in _sequence(_value(packet, "puts")))

    contracts: list[dict[str, Any]] = []
    for row, side_hint in rows:
        normalized = _normalize_contract(row, side_hint=side_hint)
        if normalized is not None:
            contracts.append(normalized)
    return contracts


def _normalize_contract(row: Any, *, side_hint: str | None) -> dict[str, Any] | None:
    side = (_text(_first_present(row, ("side", "type", "contractType"))) or side_hint or "").lower()
    if side not in {"call", "put"}:
        return None
    expiration = _text(_first_present(row, ("expiration", "expirationDate", "expiration_date")))
    strike = _positive_float_or_none(_value(row, "strike"))
    open_interest = _non_negative_float_or_none(
        _first_present(row, ("openInterest", "open_interest", "oi"))
    )
    if not expiration or strike is None or open_interest is None:
        return None

    contract_symbol = (
        _text(_first_present(row, ("contractSymbol", "contract_symbol", "symbol"))) or None
    )
    freshness = (_text(_value(row, "freshness")) or "unknown").lower()
    return {
        "contractSymbol": contract_symbol,
        "side": side,
        "expiration": expiration,
        "strike": strike,
        "openInterest": open_interest,
        "gamma": _gamma(row),
        "multiplier": _positive_float_or_none(_value(row, "multiplier")),
        "asOf": _text(_first_present(row, ("asOf", "as_of"))) or None,
        "freshness": freshness,
    }


def _expiry_concentration_evidence(
    contracts: Sequence[dict[str, Any]],
    total_open_interest: float,
) -> dict[str, Any]:
    if not contracts or total_open_interest <= 0:
        return {
            "state": "insufficient_evidence",
            "dominantExpiry": None,
            "dominantOpenInterestShare": None,
            "expiryCount": 0,
            "topExpiries": [],
        }

    buckets: dict[str, float] = defaultdict(float)
    for contract in contracts:
        buckets[contract["expiration"]] += contract["openInterest"]
    top_expiries = [
        {
            "expiration": expiration,
            "openInterest": _rounded(open_interest),
            "openInterestShare": _ratio(open_interest, total_open_interest),
        }
        for expiration, open_interest in sorted(
            buckets.items(),
            key=lambda item: (-item[1], item[0]),
        )[:3]
    ]
    dominant = top_expiries[0]
    state = (
        "concentrated"
        if float(dominant["openInterestShare"] or 0) >= _EXPIRY_CONCENTRATION_SHARE
        else "balanced"
    )
    return {
        "state": state,
        "dominantExpiry": dominant["expiration"],
        "dominantOpenInterestShare": dominant["openInterestShare"],
        "expiryCount": len(buckets),
        "topExpiries": top_expiries,
    }


def _open_interest_evidence(
    contracts: Sequence[dict[str, Any]],
    total_open_interest: float,
) -> dict[str, Any]:
    if not contracts or total_open_interest <= 0:
        return {
            "state": "insufficient_evidence",
            "totalOpenInterest": _rounded(total_open_interest),
            "contractCount": len(contracts),
            "topStrike": None,
            "topStrikeOpenInterest": None,
            "topStrikeOpenInterestShare": None,
        }

    buckets: dict[float, float] = defaultdict(float)
    for contract in contracts:
        buckets[contract["strike"]] += contract["openInterest"]
    top_strike, top_open_interest = sorted(
        buckets.items(),
        key=lambda item: (-item[1], item[0]),
    )[0]
    share = _ratio(top_open_interest, total_open_interest)
    return {
        "state": "concentrated"
        if float(share or 0) >= _OPEN_INTEREST_CONCENTRATION_SHARE
        else "balanced",
        "totalOpenInterest": _rounded(total_open_interest),
        "contractCount": len(contracts),
        "topStrike": _rounded(top_strike),
        "topStrikeOpenInterest": _rounded(top_open_interest),
        "topStrikeOpenInterestShare": share,
    }


def _put_call_skew_evidence(contracts: Sequence[dict[str, Any]]) -> dict[str, Any]:
    call_open_interest = sum(
        contract["openInterest"] for contract in contracts if contract["side"] == "call"
    )
    put_open_interest = sum(
        contract["openInterest"] for contract in contracts if contract["side"] == "put"
    )
    if call_open_interest <= 0 and put_open_interest <= 0:
        return {
            "state": "insufficient_evidence",
            "putOpenInterest": _rounded(put_open_interest),
            "callOpenInterest": _rounded(call_open_interest),
            "putCallOpenInterestRatio": None,
            "dominantSide": None,
        }

    ratio = None if call_open_interest <= 0 else _ratio(put_open_interest, call_open_interest)
    state = "balanced"
    dominant_side = "put" if put_open_interest > call_open_interest else "call"
    if (
        ratio is None
        or float(ratio) >= _PUT_CALL_SKEW_RATIO
        or float(ratio) <= _CALL_PUT_SKEW_RATIO
    ):
        state = "skewed"
    return {
        "state": state,
        "putOpenInterest": _rounded(put_open_interest),
        "callOpenInterest": _rounded(call_open_interest),
        "putCallOpenInterestRatio": ratio,
        "dominantSide": dominant_side,
    }


def _gamma_risk_evidence(
    contracts: Sequence[dict[str, Any]],
    spot: float | None,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    gamma_ready = [
        contract
        for contract in contracts
        if contract["gamma"] is not None
        and contract["multiplier"] is not None
        and contract["openInterest"] >= 0
    ]
    if not gamma_ready:
        return (
            {
                "state": "insufficient_evidence",
                "gammaInputsPresent": False,
                "proxyOnly": True,
                "message": (
                    "Gamma or greeks input is unavailable, so gamma-risk evidence is not "
                    "calculated."
                ),
                "largestStrike": None,
                "netSignedGammaProxy": None,
                "grossGammaProxy": None,
            },
            [{"field": "gammaOrGreeks", "label": "Gamma or greeks input is unavailable."}],
        )

    exposures = []
    for contract in gamma_ready:
        exposure = (
            float(contract["gamma"])
            * contract["openInterest"]
            * float(contract["multiplier"])
        )
        if spot is not None:
            exposure *= spot * spot * 0.01
        signed_exposure = exposure if contract["side"] == "call" else -exposure
        exposures.append((contract["strike"], signed_exposure, abs(exposure)))

    net_gamma = sum(item[1] for item in exposures)
    gross_gamma = sum(item[2] for item in exposures)
    largest_strike = sorted(exposures, key=lambda item: (-item[2], item[0]))[0][0]
    return (
        {
            "state": "observed",
            "gammaInputsPresent": True,
            "proxyOnly": True,
            "message": "Gamma-risk evidence uses supplied greeks and open interest only.",
            "largestStrike": _rounded(largest_strike),
            "netSignedGammaProxy": _rounded(net_gamma),
            "grossGammaProxy": _rounded(gross_gamma),
        },
        [],
    )


def _structure_state(
    *,
    expiry_evidence: Mapping[str, Any],
    open_interest_evidence: Mapping[str, Any],
    skew_evidence: Mapping[str, Any],
    missing_inputs: Sequence[Mapping[str, str]],
) -> str:
    if _has_missing_core_inputs(missing_inputs):
        return "insufficient_evidence"
    if skew_evidence.get("state") == "skewed":
        return "skewed"
    if (
        expiry_evidence.get("state") == "concentrated"
        or open_interest_evidence.get("state") == "concentrated"
    ):
        return "concentrated"
    return "balanced"


def _missing_inputs(
    *,
    symbol: str | None,
    as_of: str | None,
    contracts: Sequence[dict[str, Any]],
    total_open_interest: float,
) -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    if not symbol:
        missing.append({"field": "symbol", "label": "Underlying symbol is unavailable."})
    if not as_of:
        missing.append({"field": "asOf", "label": "Observation timestamp is unavailable."})
    if not contracts:
        missing.append({"field": "contracts", "label": "Option contract rows are unavailable."})
    if contracts and total_open_interest <= 0:
        missing.append({"field": "openInterest", "label": "Open interest input is unavailable."})
    return missing


def _stale_inputs(contracts: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    stale: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for contract in contracts:
        freshness = str(contract.get("freshness") or "").lower()
        if freshness not in _STALE_FRESHNESS_VALUES:
            continue
        contract_symbol = contract.get("contractSymbol") or ""
        key = ("contractFreshness", contract_symbol)
        if key in seen:
            continue
        seen.add(key)
        item = {
            "field": "contractFreshness",
            "label": f"A contract row is marked {freshness}.",
        }
        if contract_symbol:
            item["contractSymbol"] = str(contract_symbol)
        stale.append(item)
    return stale


def _confidence_cap(
    missing_inputs: Sequence[Mapping[str, str]],
    stale_inputs: Sequence[Mapping[str, str]],
    gamma_evidence: Mapping[str, Any],
) -> dict[str, str]:
    if _has_missing_core_inputs(missing_inputs):
        return {
            "level": "low",
            "reason": "Core options-structure inputs are incomplete.",
        }
    if missing_inputs or gamma_evidence.get("state") == "insufficient_evidence":
        return {
            "level": "low",
            "reason": "Gamma or greeks evidence is incomplete.",
        }
    if stale_inputs:
        return {
            "level": "low",
            "reason": "Stale input rows are present.",
        }
    return {
        "level": "medium",
        "reason": "Supplied evidence is complete for observation research.",
    }


def _has_missing_core_inputs(missing_inputs: Sequence[Mapping[str, str]]) -> bool:
    core_fields = {"symbol", "asOf", "contracts", "openInterest"}
    return any(item.get("field") in core_fields for item in missing_inputs)


def _dedupe_evidence(items: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        field = str(item.get("field") or "")
        label = str(item.get("label") or "")
        if not field or not label:
            continue
        key = (field, label)
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"field": field, "label": label})
    return deduped


def _gamma(row: Any) -> float | None:
    greeks = _value(row, "greeks")
    gamma = _non_negative_float_or_none(_value(greeks, "gamma"))
    if gamma is not None:
        return gamma
    return _non_negative_float_or_none(_value(row, "gamma"))


def _value(source: Any, key: str) -> Any:
    if isinstance(source, Mapping):
        return source.get(key)
    return getattr(source, key, None)


def _first_present(source: Any, keys: Sequence[str]) -> Any:
    for key in keys:
        value = _value(source, key)
        if value is not None:
            return value
    return None


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_symbol(value: str) -> str | None:
    if not value:
        return None
    sanitized = "".join(ch for ch in value.upper() if ch.isalnum() or ch in {".", "_", "-"})
    return sanitized[:24] or None


def _non_negative_float_or_none(value: Any) -> float | None:
    number = _float_or_none(value)
    if number is None or number < 0:
        return None
    return number


def _positive_float_or_none(value: Any) -> float | None:
    number = _float_or_none(value)
    if number is None or number <= 0:
        return None
    return number


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _rounded(value: float | int | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)
