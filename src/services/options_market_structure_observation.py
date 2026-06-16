# -*- coding: utf-8 -*-
"""Pure options market-structure observation helpers.

This module is intentionally provider-neutral and side-effect free. It consumes
already-normalized option contract objects or mappings and emits observation
metadata only; it does not authorize API exposure, ranking, recommendations, or
execution workflows.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from src.services.consumer_issue_labels import build_consumer_issues


OBSERVATION_CONTRACT_NAME = "optionsMarketStructureObservation"
OBSERVATION_CONTRACT_VERSION = "options-market-structure-observation-v1"
GEX_FORMULA_ID = "gex_open_interest_spot_squared_one_percent_v1"
GEX_FORMULA = "gamma * open_interest * multiplier * spot * spot * 0.01"
GEX_UNIT_CONVENTION = "estimated_underlying_currency_delta_per_1pct_spot_move"
SIGN_CONVENTION = "calls_positive_puts_negative_open_interest_proxy"
POSITIONING_ASSUMPTION = (
    "Open-interest proxy: call OI contributes positive signed gamma and put OI "
    "contributes negative signed gamma; this is not an estimate of actual dealer positioning."
)
NO_ADVICE_DISCLOSURE = (
    "Observation-only research context; not personalized financial advice and "
    "not an execution instruction."
)
NEUTRAL_NET_GEX_SHARE = 0.05
MIXED_SIDE_GEX_SHARE = 0.25
MIXED_NET_GEX_SHARE = 0.35
DEFAULT_MIN_CALCULATION_COVERAGE_PCT = 90.0
ALLOWED_DATA_QUALITY_LABELS = ("live", "delayed", "estimated", "proxy", "unavailable")
_CALCULATION_PREREQUISITES = (
    "side",
    "strike",
    "expiration",
    "gamma",
    "open_interest",
    "multiplier",
    "iv",
)


def build_options_market_structure_observation(
    contracts: Sequence[Any],
    *,
    spot: float | int | str | None,
    as_of: str | None = None,
    data_quality_label: str | Sequence[str] | None = None,
    methodology_approved: bool = False,
    coverage_thresholds_defined: bool = False,
    provider_authority_verified: bool = False,
    redistribution_rights_verified: bool = False,
    decision_use_rights_verified: bool = False,
    deliverable_handling_reviewed: bool = False,
    min_calculation_coverage_pct: float = DEFAULT_MIN_CALCULATION_COVERAGE_PCT,
    top_n: int = 5,
) -> dict[str, Any]:
    """Build an observation-only GEX and strike-concentration summary.

    The helper deliberately fail-closes for missing formula inputs. Partial
    usable evidence can still produce a degraded observation, but missing rows
    are excluded rather than filled or guessed.
    """

    normalized = [_normalize_contract(contract, index) for index, contract in enumerate(contracts or [])]
    spot_value = _coerce_float(spot)
    missing_evidence = _missing_evidence(normalized, spot_value)
    field_coverage = _coverage_by_field(normalized)
    usable = [item for item in normalized if _is_usable_contract(item, spot_value)]
    total_contracts = len(normalized)
    calculation_coverage_pct = _pct(len(usable), total_contracts)
    data_quality_labels = _data_quality_labels(data_quality_label, normalized)
    observation_state = _observation_state(
        total_contracts=total_contracts,
        usable_contracts=len(usable),
        calculation_coverage_pct=calculation_coverage_pct,
        min_calculation_coverage_pct=min_calculation_coverage_pct,
    )

    blocked_reason_codes = _blocked_reason_codes(
        missing_evidence=missing_evidence,
        observation_state=observation_state,
        methodology_approved=methodology_approved,
        coverage_thresholds_defined=coverage_thresholds_defined,
        provider_authority_verified=provider_authority_verified,
        redistribution_rights_verified=redistribution_rights_verified,
        decision_use_rights_verified=decision_use_rights_verified,
        deliverable_handling_reviewed=deliverable_handling_reviewed,
    )

    gex_summary: dict[str, Any]
    buckets: dict[float, dict[str, Any]]
    if observation_state == "blocked" or spot_value is None:
        gex_summary = _empty_gex_summary()
        buckets = {}
    else:
        exposures = [_contract_exposure(item, spot_value) for item in usable]
        buckets = _strike_buckets(exposures)
        gex_summary = _gex_summary(exposures)

    gamma_regime = _gamma_regime(observation_state, gex_summary)
    gamma_flip_level, gamma_flip_interval = _gamma_flip(buckets, spot_value)

    coverage = {
        "totalContracts": total_contracts,
        "usableContracts": len(usable),
        "excludedContracts": total_contracts - len(usable),
        "calculationCoveragePct": calculation_coverage_pct,
        "minimumCalculationCoveragePct": float(min_calculation_coverage_pct),
        "expirationCount": len({item["expiration"] for item in normalized if item["expiration"]}),
        "zeroDTEContractCount": sum(1 for item in usable if item["dte"] == 0),
        **field_coverage,
    }

    consumer_issues = build_consumer_issues(blocked_reason_codes, missing_evidence, data_quality_labels)
    return {
        "contractName": OBSERVATION_CONTRACT_NAME,
        "contractVersion": OBSERVATION_CONTRACT_VERSION,
        "observationOnly": True,
        "decisionGrade": False,
        "decisionGradeBlocked": True,
        "generatedAt": as_of,
        "observationState": observation_state,
        "gammaRegime": gamma_regime,
        "gammaFlipLevel": gamma_flip_level,
        "gammaFlipInterval": gamma_flip_interval,
        "gexSummary": gex_summary,
        "callWall": _wall(buckets, "call"),
        "putWall": _wall(buckets, "put"),
        "topGammaStrikes": _top_gamma_strikes(buckets, top_n=top_n),
        "zeroDTEGammaShare": _zero_dte_gamma_share(usable, spot_value, observation_state),
        "coverage": coverage,
        "missingEvidence": missing_evidence,
        "blockedReasonCodes": blocked_reason_codes,
        "dataQualityLabels": data_quality_labels,
        "consumerIssues": consumer_issues,
        "methodology": {
            "formulaId": GEX_FORMULA_ID,
            "formula": GEX_FORMULA,
            "unitConvention": GEX_UNIT_CONVENTION,
            "signConvention": SIGN_CONVENTION,
            "positioningAssumption": POSITIONING_ASSUMPTION,
            "aggregation": "strike_bucket_side_and_expiry_sums",
            "gammaFlipMethod": "adjacent_strike_bucket_sign_change",
            "confidencePolicy": "low_confidence_observation_until_rights_coverage_and_methodology_are_reviewed",
        },
        "noAdviceDisclosure": NO_ADVICE_DISCLOSURE,
        "forbiddenUses": [
            "broker_execution",
            "portfolio_mutation",
            "scanner_ranking",
            "backtest_input",
            "recommendation",
        ],
    }


def _normalize_contract(contract: Any, index: int) -> dict[str, Any]:
    greeks = _value(contract, "greeks")
    gamma = _coerce_float(_value(greeks, "gamma"))
    if gamma is None:
        gamma = _coerce_float(_value(contract, "gamma"))
    open_interest = _coerce_float(_value(contract, "open_interest", "openInterest"))
    multiplier = _coerce_float(_value(contract, "multiplier"))
    return {
        "index": index,
        "contract_symbol": _text(_value(contract, "contract_symbol", "contractSymbol", "symbol")),
        "side": _text(_value(contract, "side")).lower(),
        "strike": _coerce_float(_value(contract, "strike")),
        "expiration": _text(_value(contract, "expiration", "expiration_date", "expirationDate")),
        "gamma": gamma if gamma is None or gamma >= 0 else None,
        "open_interest": open_interest if open_interest is None or open_interest >= 0 else None,
        "multiplier": multiplier if multiplier is None or multiplier > 0 else None,
        "iv": _coerce_float(_value(contract, "implied_volatility", "impliedVolatility", "mid_iv", "midIv")),
        "dte": _coerce_int(_value(contract, "dte", "days_to_expiration", "daysToExpiration")),
        "freshness": _text(_value(contract, "freshness")),
        "source": _text(_value(contract, "source")),
    }


def _contract_exposure(contract: dict[str, Any], spot: float) -> dict[str, Any]:
    raw_gex = (
        float(contract["gamma"])
        * float(contract["open_interest"])
        * float(contract["multiplier"])
        * spot
        * spot
        * 0.01
    )
    side = contract["side"]
    signed_gex = raw_gex if side == "call" else -raw_gex
    return {
        **contract,
        "rawGammaExposure": raw_gex,
        "signedGammaExposure": signed_gex,
    }


def _strike_buckets(exposures: Sequence[dict[str, Any]]) -> dict[float, dict[str, Any]]:
    buckets: dict[float, dict[str, Any]] = defaultdict(
        lambda: {
            "strike": 0.0,
            "netGamma": 0.0,
            "callGamma": 0.0,
            "putGamma": 0.0,
            "grossGamma": 0.0,
            "openInterest": 0.0,
            "callOpenInterest": 0.0,
            "putOpenInterest": 0.0,
            "contractCount": 0,
        }
    )
    for item in exposures:
        strike = float(item["strike"])
        bucket = buckets[strike]
        bucket["strike"] = strike
        signed_gex = float(item["signedGammaExposure"])
        bucket["netGamma"] += signed_gex
        bucket["grossGamma"] += abs(signed_gex)
        bucket["openInterest"] += float(item["open_interest"])
        bucket["contractCount"] += 1
        if item["side"] == "call":
            bucket["callGamma"] += abs(signed_gex)
            bucket["callOpenInterest"] += float(item["open_interest"])
        elif item["side"] == "put":
            bucket["putGamma"] -= abs(signed_gex)
            bucket["putOpenInterest"] += float(item["open_interest"])
    return buckets


def _gex_summary(exposures: Sequence[dict[str, Any]]) -> dict[str, Any]:
    call_gamma = sum(float(item["signedGammaExposure"]) for item in exposures if item["side"] == "call")
    put_gamma = sum(float(item["signedGammaExposure"]) for item in exposures if item["side"] == "put")
    net_gamma = call_gamma + put_gamma
    gross_gamma = sum(abs(float(item["signedGammaExposure"])) for item in exposures)
    return {
        "netGamma": _round(net_gamma),
        "callGamma": _round(call_gamma),
        "putGamma": _round(put_gamma),
        "grossGamma": _round(gross_gamma),
        "unit": GEX_UNIT_CONVENTION,
        "formulaId": GEX_FORMULA_ID,
    }


def _empty_gex_summary() -> dict[str, Any]:
    return {
        "netGamma": None,
        "callGamma": None,
        "putGamma": None,
        "grossGamma": None,
        "unit": GEX_UNIT_CONVENTION,
        "formulaId": GEX_FORMULA_ID,
    }


def _gamma_regime(observation_state: str, gex_summary: Mapping[str, Any]) -> str:
    if observation_state == "blocked":
        return "blocked"
    gross_gamma = _coerce_float(gex_summary.get("grossGamma")) or 0.0
    net_gamma = _coerce_float(gex_summary.get("netGamma")) or 0.0
    call_gamma = abs(_coerce_float(gex_summary.get("callGamma")) or 0.0)
    put_gamma = abs(_coerce_float(gex_summary.get("putGamma")) or 0.0)
    if gross_gamma <= 0:
        return "unknown"
    net_share = net_gamma / gross_gamma
    if abs(net_share) <= NEUTRAL_NET_GEX_SHARE:
        return "neutral"
    if (
        call_gamma / gross_gamma >= MIXED_SIDE_GEX_SHARE
        and put_gamma / gross_gamma >= MIXED_SIDE_GEX_SHARE
        and abs(net_share) <= MIXED_NET_GEX_SHARE
    ):
        return "mixed"
    return "positive" if net_gamma > 0 else "negative"


def _gamma_flip(
    buckets: Mapping[float, Mapping[str, Any]],
    spot: float | None,
) -> tuple[float | None, dict[str, Any] | None]:
    signed_buckets = [
        (float(strike), float(bucket["netGamma"]))
        for strike, bucket in sorted(buckets.items())
        if float(bucket["netGamma"]) != 0
    ]
    if not signed_buckets:
        return None, None
    for strike, net_gamma in sorted(buckets.items()):
        if float(net_gamma["netGamma"]) == 0:
            return float(strike), None

    intervals: list[tuple[float, float]] = []
    for (lower_strike, lower_gamma), (upper_strike, upper_gamma) in zip(signed_buckets, signed_buckets[1:]):
        if (lower_gamma < 0 < upper_gamma) or (lower_gamma > 0 > upper_gamma):
            intervals.append((lower_strike, upper_strike))
    if not intervals:
        return None, None

    if spot is None:
        lower, upper = intervals[0]
    else:
        lower, upper = min(intervals, key=lambda item: abs(((item[0] + item[1]) / 2) - spot))
    return None, {
        "lowerStrike": _round(lower),
        "upperStrike": _round(upper),
        "method": "adjacent_strike_bucket_sign_change",
        "confidence": "low",
    }


def _wall(buckets: Mapping[float, Mapping[str, Any]], side: str) -> dict[str, Any] | None:
    if not buckets:
        return None
    gamma_key = "callGamma" if side == "call" else "putGamma"
    oi_key = "callOpenInterest" if side == "call" else "putOpenInterest"
    candidates = [bucket for bucket in buckets.values() if abs(float(bucket[gamma_key])) > 0]
    if not candidates:
        return None
    selected = max(
        candidates,
        key=lambda bucket: (abs(float(bucket[gamma_key])), float(bucket[oi_key]), float(bucket["strike"])),
    )
    return {
        "strike": _round(selected["strike"]),
        "side": side,
        "gammaExposure": _round(selected[gamma_key]),
        "openInterest": int(selected[oi_key]),
        "label": f"{side}_gamma_concentration",
    }


def _top_gamma_strikes(buckets: Mapping[float, Mapping[str, Any]], *, top_n: int) -> list[dict[str, Any]]:
    rows = []
    for bucket in buckets.values():
        call_gamma = abs(float(bucket["callGamma"]))
        put_gamma = abs(float(bucket["putGamma"]))
        if call_gamma > put_gamma:
            dominant_side = "call"
        elif put_gamma > call_gamma:
            dominant_side = "put"
        else:
            dominant_side = "balanced"
        rows.append(
            {
                "strike": _round(bucket["strike"]),
                "netGamma": _round(bucket["netGamma"]),
                "absGamma": _round(abs(float(bucket["netGamma"]))),
                "grossGamma": _round(bucket["grossGamma"]),
                "callGamma": _round(bucket["callGamma"]),
                "putGamma": _round(bucket["putGamma"]),
                "openInterest": int(bucket["openInterest"]),
                "contractCount": int(bucket["contractCount"]),
                "dominantSide": dominant_side,
            }
        )
    return sorted(rows, key=lambda row: (-float(row["absGamma"]), float(row["strike"])))[: max(top_n, 0)]


def _zero_dte_gamma_share(
    usable_contracts: Sequence[dict[str, Any]],
    spot: float | None,
    observation_state: str,
) -> dict[str, Any]:
    if observation_state == "blocked" or spot is None or not usable_contracts:
        return {"available": False, "reason": "expiry_data_unavailable"}
    if not any(item["dte"] is not None for item in usable_contracts):
        return {"available": False, "reason": "expiry_data_unavailable"}
    exposures = [_contract_exposure(item, spot) for item in usable_contracts]
    gross_gamma = sum(abs(float(item["signedGammaExposure"])) for item in exposures)
    zero_dte_gamma = sum(abs(float(item["signedGammaExposure"])) for item in exposures if item["dte"] == 0)
    return {
        "available": True,
        "share": _round(zero_dte_gamma / gross_gamma) if gross_gamma > 0 else 0.0,
        "zeroDTEGamma": _round(zero_dte_gamma),
        "grossGamma": _round(gross_gamma),
    }


def _missing_evidence(normalized: Sequence[dict[str, Any]], spot: float | None) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    if spot is None or spot <= 0:
        missing.append({"code": "missing_spot_reference", "field": "spot", "contractSymbol": None})
    if not normalized:
        missing.append({"code": "missing_contracts", "field": "contracts", "contractSymbol": None})
        return missing
    for item in normalized:
        for code, field in _missing_contract_codes(item):
            missing.append(
                {
                    "code": code,
                    "field": field,
                    "contractSymbol": item["contract_symbol"] or f"contract_{item['index']}",
                }
            )
    return missing


def _missing_contract_codes(item: Mapping[str, Any]) -> list[tuple[str, str]]:
    missing: list[tuple[str, str]] = []
    if item["side"] not in {"call", "put"}:
        missing.append(("missing_side", "side"))
    if item["strike"] is None:
        missing.append(("missing_strike", "strike"))
    if not item["expiration"]:
        missing.append(("missing_expiration", "expiration"))
    if item["gamma"] is None:
        missing.append(("missing_gamma", "greeks.gamma"))
    if item["open_interest"] is None:
        missing.append(("missing_open_interest", "open_interest"))
    if item["multiplier"] is None:
        missing.append(("missing_multiplier", "multiplier"))
    if item["iv"] is None:
        missing.append(("missing_iv", "implied_volatility"))
    return missing


def _coverage_by_field(normalized: Sequence[dict[str, Any]]) -> dict[str, float]:
    total = len(normalized)
    return {
        "sideCoveragePct": _pct(sum(1 for item in normalized if item["side"] in {"call", "put"}), total),
        "strikeCoveragePct": _pct(sum(1 for item in normalized if item["strike"] is not None), total),
        "expirationCoveragePct": _pct(sum(1 for item in normalized if item["expiration"]), total),
        "gammaCoveragePct": _pct(sum(1 for item in normalized if item["gamma"] is not None), total),
        "openInterestCoveragePct": _pct(
            sum(1 for item in normalized if item["open_interest"] is not None),
            total,
        ),
        "multiplierCoveragePct": _pct(sum(1 for item in normalized if item["multiplier"] is not None), total),
        "ivCoveragePct": _pct(sum(1 for item in normalized if item["iv"] is not None), total),
    }


def _is_usable_contract(item: Mapping[str, Any], spot: float | None) -> bool:
    if spot is None or spot <= 0:
        return False
    return not _missing_contract_codes(item)


def _observation_state(
    *,
    total_contracts: int,
    usable_contracts: int,
    calculation_coverage_pct: float,
    min_calculation_coverage_pct: float,
) -> str:
    if total_contracts <= 0 or usable_contracts <= 0:
        return "blocked"
    if usable_contracts < total_contracts or calculation_coverage_pct < min_calculation_coverage_pct:
        return "degraded"
    return "ready"


def _blocked_reason_codes(
    *,
    missing_evidence: Sequence[Mapping[str, Any]],
    observation_state: str,
    methodology_approved: bool,
    coverage_thresholds_defined: bool,
    provider_authority_verified: bool,
    redistribution_rights_verified: bool,
    decision_use_rights_verified: bool,
    deliverable_handling_reviewed: bool,
) -> list[str]:
    codes = ["observation_only_not_decision_grade"]
    codes.extend(str(item.get("code")) for item in missing_evidence if item.get("code"))
    if observation_state == "blocked":
        codes.append("insufficient_usable_contracts")
    elif observation_state == "degraded":
        codes.append("partial_calculation_coverage")
    if not methodology_approved:
        codes.append("methodology_approval_missing")
    if not coverage_thresholds_defined:
        codes.append("coverage_thresholds_missing")
    if not provider_authority_verified:
        codes.append("provider_authority_missing")
    if not redistribution_rights_verified:
        codes.append("redistribution_rights_missing")
    if not decision_use_rights_verified:
        codes.append("decision_use_rights_missing")
    if not deliverable_handling_reviewed:
        codes.append("deliverable_handling_missing")
    return _dedupe(codes)


def _data_quality_labels(
    explicit_label: str | Sequence[str] | None,
    normalized: Sequence[Mapping[str, Any]],
) -> list[str]:
    labels: list[str] = []
    if explicit_label:
        raw_labels = [explicit_label] if isinstance(explicit_label, str) else list(explicit_label)
        labels.extend(_normalize_quality_label(label) for label in raw_labels)
    else:
        for item in normalized:
            labels.append(_normalize_quality_label(item.get("freshness")))
            labels.append(_normalize_quality_label(item.get("source")))
    labels = [label for label in _dedupe(labels) if label in ALLOWED_DATA_QUALITY_LABELS]
    return labels or ["unavailable"]


def _normalize_quality_label(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in ALLOWED_DATA_QUALITY_LABELS:
        return text
    if text in {"fresh", "realtime", "real_time", "real-time"} or "live" in text:
        return "live"
    if any(marker in text for marker in ("delayed", "stale", "cached", "dry_run")):
        return "delayed"
    if "estimated" in text or "estimate" in text:
        return "estimated"
    if any(marker in text for marker in ("proxy", "fixture", "synthetic", "mock", "fallback")):
        return "proxy"
    return "unavailable"


def _value(source: Any, *names: str) -> Any:
    if source is None:
        return None
    for name in names:
        if isinstance(source, Mapping) and name in source:
            return source.get(name)
        if hasattr(source, name):
            return getattr(source, name)
    return None


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _pct(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return _round((count / total) * 100.0)


def _round(value: Any) -> float:
    return round(float(value), 6)


def _dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            ordered.append(text)
    return ordered
