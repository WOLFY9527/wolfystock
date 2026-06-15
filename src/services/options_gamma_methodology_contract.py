# -*- coding: utf-8 -*-
"""Pure methodology readiness contract for options gamma observations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from src.services.options_market_structure_observation import GEX_FORMULA_ID, SIGN_CONVENTION


OPTIONS_GAMMA_METHODOLOGY_SCHEMA_VERSION = "options_gamma_methodology_contract_v1"
OPTIONS_GAMMA_NO_ADVICE_DISCLOSURE = (
    "Observation-only options gamma methodology context; not personalized "
    "financial advice and not an execution instruction."
)
OPTIONS_GAMMA_FORMULA_VERSION = GEX_FORMULA_ID
OPTIONS_GAMMA_SIGN_CONVENTION = SIGN_CONVENTION

_UNSET = object()
_FIELD_REQUIREMENTS = (
    ("spot", "underlying spot"),
    ("strike", "contract strike"),
    ("expiration", "contract expiration"),
    ("side", "contract side"),
    ("openInterest", "open interest"),
    ("gamma", "gamma"),
    ("multiplier", "contract multiplier"),
    ("asOf", "as-of timestamp"),
    ("freshness", "freshness"),
    ("providerRights", "provider rights"),
    ("formulaVersion", "formula version"),
    ("signConvention", "sign convention"),
    ("coverageThreshold", "coverage threshold"),
)
_CONTRACT_FIELDS = ("strike", "expiration", "side", "openInterest", "gamma", "multiplier")
_PROVIDER_RIGHT_KEYS = (
    "providerAuthorityVerified",
    "redistributionRightsVerified",
    "decisionUseRightsVerified",
)
_UNKNOWN_FRESHNESS = {"", "unknown"}
_UNAVAILABLE_FRESHNESS = {"unavailable", "not_available", "none"}
_DEGRADED_FRESHNESS_MARKERS = ("stale", "delayed", "cached", "fallback", "fixture", "synthetic", "mock")


def assess_options_gamma_methodology_readiness(
    evidence: Mapping[str, Any] | None = None,
    *,
    contracts: Sequence[Any] | object = _UNSET,
    spot: Any = _UNSET,
    as_of: Any = _UNSET,
    freshness: Any = _UNSET,
    provider_rights: Any = _UNSET,
    formula_version: Any = _UNSET,
    sign_convention: Any = _UNSET,
    coverage_threshold: Any = _UNSET,
    coverage: Any = _UNSET,
) -> dict[str, Any]:
    """Assess supplied gamma evidence without fetching or mutating runtime state."""

    payload = dict(evidence or {})
    overrides = {
        "contracts": contracts,
        "spot": spot,
        "asOf": as_of,
        "freshness": freshness,
        "providerRights": provider_rights,
        "formulaVersion": formula_version,
        "signConvention": sign_convention,
        "coverageThreshold": coverage_threshold,
        "coverage": coverage,
    }
    for key, value in overrides.items():
        if value is not _UNSET:
            payload[key] = value

    contracts_value = _sequence(_coalesce(_get(payload, "contracts"), _get(payload, "inputRecords", "input_records")))
    requirements = _initial_requirements()
    missing: list[str] = []
    degraded: list[str] = []
    blocked: list[str] = []

    spot_value = _number(_get(payload, "spot", "underlyingSpot", "underlying_spot"))
    as_of_value = _text(
        _coalesce(
            _get(payload, "asOf", "as_of", "chainAsOf", "chain_as_of"),
            _first_contract_value(contracts_value, "asOf", "as_of"),
        )
    )
    freshness_values = _freshness_values(payload, contracts_value)
    formula = _text(
        _coalesce(
            _get(payload, "formulaVersion", "formula_version"),
            _get(_mapping(_get(payload, "methodology")), "formulaVersion", "formulaId", "formula_id"),
        )
    )
    sign_convention = _text(
        _coalesce(
            _get(payload, "signConvention", "sign_convention"),
            _get(_mapping(_get(payload, "methodology")), "signConvention", "sign_convention"),
        )
    )
    threshold = _number(
        _coalesce(
            _get(payload, "coverageThreshold", "coverage_threshold", "minimumCalculationCoveragePct"),
            _get(_mapping(_get(payload, "coverage")), "minimumCalculationCoveragePct"),
        )
    )
    coverage_value = _number(_coalesce(_coverage_value(payload), _derived_coverage(contracts_value)))

    if spot_value is None or spot_value <= 0:
        _mark(requirements, "spot", "blocked", "missing_spot", missing, blocked)
    if not as_of_value:
        _mark(requirements, "asOf", "blocked", "missing_as_of", missing, blocked)

    _evaluate_contract_fields(contracts_value, requirements, missing, blocked)
    _evaluate_freshness(freshness_values, requirements, missing, degraded, blocked)
    _evaluate_provider_rights(payload, requirements, missing, blocked)
    _evaluate_formula(formula, requirements, missing, blocked)
    _evaluate_sign_convention(sign_convention, requirements, missing, blocked)
    _evaluate_coverage(threshold, coverage_value, requirements, missing, degraded, blocked)

    unavailable_reasons: list[str] = []
    if not contracts_value:
        unavailable_reasons.append("options_gamma_evidence_unavailable")
    if any(_normalize(value) in _UNAVAILABLE_FRESHNESS for value in freshness_values):
        unavailable_reasons.append("freshness_unavailable")
    for reason in unavailable_reasons:
        _append_unique(blocked, reason)

    readiness = "approved"
    if unavailable_reasons:
        readiness = "unavailable"
    elif blocked:
        readiness = "blocked"
    elif degraded:
        readiness = "degraded"

    return {
        "schemaVersion": OPTIONS_GAMMA_METHODOLOGY_SCHEMA_VERSION,
        "readiness": readiness,
        "observationOnly": True,
        "decisionGrade": False,
        "formulaVersion": formula or None,
        "signConvention": sign_convention or None,
        "dataRequirements": list(requirements.values()),
        "missingRequirements": missing,
        "degradedReasons": degraded,
        "blockedReasons": blocked,
        "noAdviceDisclosure": OPTIONS_GAMMA_NO_ADVICE_DISCLOSURE,
    }


def _evaluate_contract_fields(
    contracts: Sequence[Any],
    requirements: dict[str, dict[str, Any]],
    missing: list[str],
    blocked: list[str],
) -> None:
    if not contracts:
        for key in _CONTRACT_FIELDS:
            _mark(requirements, key, "unavailable", "missing_contracts", missing)
        return

    checks = {
        "strike": lambda row: (_number(_get(row, "strike")) or 0) > 0,
        "expiration": lambda row: bool(_text(_get(row, "expiration", "expirationDate", "expiration_date"))),
        "side": lambda row: _text(_get(row, "side")).lower() in {"call", "put"},
        "openInterest": lambda row: _non_negative(_get(row, "openInterest", "open_interest")),
        "gamma": lambda row: _non_negative(_coalesce(_get(_mapping(_get(row, "greeks")), "gamma"), _get(row, "gamma"))),
        "multiplier": lambda row: (_number(_get(row, "multiplier")) or 0) > 0,
    }
    reason = {
        "strike": "missing_strike",
        "expiration": "missing_expiration",
        "side": "missing_side",
        "openInterest": "missing_open_interest",
        "gamma": "missing_gamma",
        "multiplier": "missing_multiplier",
    }
    for key, check in checks.items():
        if not all(check(row) for row in contracts):
            _mark(requirements, key, "blocked", reason[key], missing, blocked)


def _evaluate_freshness(
    values: Sequence[str],
    requirements: dict[str, dict[str, Any]],
    missing: list[str],
    degraded: list[str],
    blocked: list[str],
) -> None:
    normalized = [_normalize(value) for value in values]
    if not normalized:
        _mark(requirements, "freshness", "blocked", "missing_freshness", missing, blocked)
    elif any(value in _UNAVAILABLE_FRESHNESS for value in normalized):
        _mark(requirements, "freshness", "unavailable", "freshness_unavailable")
    elif any(value in _UNKNOWN_FRESHNESS for value in normalized):
        _mark(requirements, "freshness", "degraded", "freshness_unknown")
        _append_unique(degraded, "freshness_unknown")
    elif any(any(marker in value for marker in _DEGRADED_FRESHNESS_MARKERS) for value in normalized):
        _mark(requirements, "freshness", "degraded", "freshness_degraded")
        _append_unique(degraded, "freshness_degraded")


def _evaluate_provider_rights(
    payload: Mapping[str, Any],
    requirements: dict[str, dict[str, Any]],
    missing: list[str],
    blocked: list[str],
) -> None:
    rights = _mapping(_coalesce(_get(payload, "providerRights", "rights"), {}))
    complete = all(bool(rights.get(key)) for key in _PROVIDER_RIGHT_KEYS)
    complete = complete or bool(_get(payload, "providerRightsVerified", "provider_rights_verified"))
    if not complete:
        _mark(requirements, "providerRights", "blocked", "provider_rights_incomplete", missing, blocked)


def _evaluate_formula(
    value: str,
    requirements: dict[str, dict[str, Any]],
    missing: list[str],
    blocked: list[str],
) -> None:
    if not value:
        _mark(requirements, "formulaVersion", "blocked", "formula_version_missing", missing, blocked)
    elif value != OPTIONS_GAMMA_FORMULA_VERSION:
        _mark(requirements, "formulaVersion", "blocked", "formula_version_unsupported", missing, blocked)


def _evaluate_sign_convention(
    value: str,
    requirements: dict[str, dict[str, Any]],
    missing: list[str],
    blocked: list[str],
) -> None:
    if not value:
        _mark(requirements, "signConvention", "blocked", "sign_convention_missing", missing, blocked)
    elif value != OPTIONS_GAMMA_SIGN_CONVENTION:
        _mark(requirements, "signConvention", "blocked", "sign_convention_unsupported", missing, blocked)


def _evaluate_coverage(
    threshold: float | None,
    coverage: float | None,
    requirements: dict[str, dict[str, Any]],
    missing: list[str],
    degraded: list[str],
    blocked: list[str],
) -> None:
    if threshold is None or threshold <= 0:
        _mark(requirements, "coverageThreshold", "blocked", "coverage_threshold_missing", missing, blocked)
    elif coverage is None:
        _mark(requirements, "coverageThreshold", "blocked", "coverage_missing", missing, blocked)
    elif coverage < threshold:
        _mark(requirements, "coverageThreshold", "degraded", "coverage_below_threshold")
        _append_unique(degraded, "coverage_below_threshold")


def _initial_requirements() -> dict[str, dict[str, Any]]:
    return {
        key: {"key": key, "label": label, "required": True, "state": "satisfied", "reasonCodes": []}
        for key, label in _FIELD_REQUIREMENTS
    }


def _mark(
    requirements: dict[str, dict[str, Any]],
    key: str,
    state: str,
    reason: str,
    missing: list[str] | None = None,
    blocked: list[str] | None = None,
) -> None:
    current = requirements[key]
    if _state_rank(state) > _state_rank(str(current["state"])):
        current["state"] = state
    _append_unique(current["reasonCodes"], reason)
    if missing is not None:
        _append_unique(missing, key)
    if blocked is not None:
        _append_unique(blocked, reason)


def _derived_coverage(contracts: Sequence[Any]) -> float | None:
    if not contracts:
        return None
    usable = 0
    for row in contracts:
        if (
            (_number(_get(row, "strike")) or 0) > 0
            and _text(_get(row, "expiration", "expirationDate", "expiration_date"))
            and _text(_get(row, "side")).lower() in {"call", "put"}
            and _non_negative(_get(row, "openInterest", "open_interest"))
            and _non_negative(_coalesce(_get(_mapping(_get(row, "greeks")), "gamma"), _get(row, "gamma")))
            and (_number(_get(row, "multiplier")) or 0) > 0
        ):
            usable += 1
    return round((usable / len(contracts)) * 100.0, 6)


def _freshness_values(payload: Mapping[str, Any], contracts: Sequence[Any]) -> list[str]:
    values = [_text(_get(payload, "freshness"))]
    values.extend(_text(_get(row, "freshness")) for row in contracts)
    return [value for value in values if value]


def _coverage_value(payload: Mapping[str, Any]) -> Any:
    raw = _get(payload, "coverage")
    if isinstance(raw, Mapping):
        return _coalesce(_get(raw, "calculationCoveragePct", "coveragePct", "coverage"))
    return _coalesce(raw, _get(payload, "calculationCoveragePct", "coveragePct"))


def _first_contract_value(contracts: Sequence[Any], *names: str) -> Any:
    for row in contracts:
        value = _get(row, *names)
        if value not in (None, ""):
            return value
    return None


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _get(source: Any, *names: str) -> Any:
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


def _normalize(value: Any) -> str:
    return _text(value).lower()


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _non_negative(value: Any) -> bool:
    number = _number(value)
    return number is not None and number >= 0


def _state_rank(state: str) -> int:
    return {"satisfied": 0, "degraded": 1, "blocked": 2, "unavailable": 3}.get(state, 0)


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


__all__ = [
    "OPTIONS_GAMMA_FORMULA_VERSION",
    "OPTIONS_GAMMA_METHODOLOGY_SCHEMA_VERSION",
    "OPTIONS_GAMMA_NO_ADVICE_DISCLOSURE",
    "OPTIONS_GAMMA_SIGN_CONVENTION",
    "assess_options_gamma_methodology_readiness",
]
