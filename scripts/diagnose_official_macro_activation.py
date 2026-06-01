#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run a bounded official macro live smoke diagnostic."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.official_macro_liquidity_cache_contracts import (
    OFFICIAL_FED_LIQUIDITY_FRESHNESS_POLICIES,
    OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES,
    OFFICIAL_FED_LIQUIDITY_SERIES_TO_SYMBOL,
    OFFICIAL_USD_PRESSURE_FRESHNESS_POLICIES,
    OFFICIAL_USD_PRESSURE_REQUIRED_SERIES,
    OFFICIAL_USD_PRESSURE_SYMBOL_TO_SERIES_ID,
)
from src.services.official_macro_transport import (
    run_fed_liquidity_live_smoke,
    run_official_macro_live_smoke,
    run_usd_pressure_live_smoke,
)

EXIT_OK = 0
EXIT_FAILED = 1
_CACHE_READINESS_GROUPS = {
    "usdPressure": OFFICIAL_USD_PRESSURE_REQUIRED_SERIES,
    "fedLiquidity": OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES,
}
_SERIES_READINESS_GROUPS: tuple[dict[str, object], ...] = (
    {
        "group": "usd_pressure",
        "series": OFFICIAL_USD_PRESSURE_REQUIRED_SERIES,
        "seriesToSymbol": {
            series_id: symbol for symbol, series_id in OFFICIAL_USD_PRESSURE_SYMBOL_TO_SERIES_ID.items()
        },
        "freshnessPolicies": OFFICIAL_USD_PRESSURE_FRESHNESS_POLICIES,
    },
    {
        "group": "fed_liquidity",
        "series": OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES,
        "seriesToSymbol": OFFICIAL_FED_LIQUIDITY_SERIES_TO_SYMBOL,
        "freshnessPolicies": OFFICIAL_FED_LIQUIDITY_FRESHNESS_POLICIES,
    },
)
_GROUP_FIELD_ALLOWLIST = (
    "credentialsPresent",
    "providerConstructed",
    "probePassed",
    "freshnessValid",
    "sourceMetadataValid",
    "sourceAuthorityAllowed",
    "scoreContributionAllowed",
    "fulfilledSeries",
    "missingSeries",
    "staleSeries",
    "reason",
    "attempts",
    "maxAttempts",
    "transientMissingSeries",
    "finalAttemptMissingSeries",
    "latestObservationDate",
    "latestAsOf",
    "freshnessPolicy",
    "maxAcceptedLagDays",
    "maxAcceptedBusinessLagDays",
    "seriesLagDays",
)


def _unexpected_error_summary() -> dict[str, object]:
    return {
        "credentialsPresent": False,
        "providerConstructed": False,
        "probePassed": False,
        "freshnessValid": False,
        "sourceMetadataValid": False,
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "fulfilledSeries": [],
        "missingSeries": [
            "VIXCLS",
            "SOFR",
            "DFF",
            "DGS2",
            "DGS10",
            "DGS30",
            "BAMLH0A0HYM2",
        ],
        "staleSeries": [],
        "reason": "unexpected_error",
    }


def _cache_readiness_unexpected_error_summary() -> dict[str, object]:
    required_series = [series for group in _CACHE_READINESS_GROUPS.values() for series in group]
    return _decorate_cache_readiness_summary(
        {
        "credentialsPresent": False,
        "keyPresent": False,
        "providerConstructed": False,
        "probePassed": False,
        "readiness": "blocked",
        "freshnessValid": False,
        "sourceMetadataValid": False,
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "requiredSeriesStatus": {series: "missing" for series in required_series},
        "missingSeries": required_series,
        "staleSeries": [],
        "reason": "unexpected_error",
        "groups": {},
        }
    )


def _as_list(values: object) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    return [str(value) for value in values if str(value or "").strip()]


def _required_series_status(summary: Mapping[str, object], required_series: Sequence[str]) -> dict[str, str]:
    fulfilled = set(_as_list(summary.get("fulfilledSeries")))
    missing = set(_as_list(summary.get("missingSeries")))
    stale = set(_as_list(summary.get("staleSeries")))
    return {
        series: "stale" if series in stale else ("fulfilled" if series in fulfilled else ("missing" if series in missing else "missing"))
        for series in required_series
    }


def _sanitize_group_summary(summary: Mapping[str, object], required_series: Sequence[str]) -> dict[str, object]:
    sanitized = {field: summary[field] for field in _GROUP_FIELD_ALLOWLIST if field in summary}
    sanitized["requiredSeriesStatus"] = _required_series_status(summary, required_series)
    return sanitized


def _aggregate_reason(groups: Mapping[str, Mapping[str, object]]) -> str | None:
    summaries = list(groups.values())
    if any(summary.get("reason") == "unexpected_error" for summary in summaries):
        return "unexpected_error"
    if not all(bool(summary.get("credentialsPresent")) for summary in summaries):
        return "credentials"
    if not all(bool(summary.get("freshnessValid")) for summary in summaries):
        return "stale_series"
    if not all(bool(summary.get("sourceMetadataValid")) for summary in summaries):
        return "source_metadata_invalid"
    if any(_as_list(summary.get("missingSeries")) for summary in summaries):
        return "series_coverage"
    return None


def _required_series() -> list[str]:
    return [series for group in _CACHE_READINESS_GROUPS.values() for series in group]


def _series_status(summary: Mapping[str, object], series_id: str) -> str:
    required_series_status = summary.get("requiredSeriesStatus")
    if isinstance(required_series_status, Mapping):
        return str(required_series_status.get(series_id) or "missing").strip().lower()
    if series_id in set(_as_list(summary.get("staleSeries"))):
        return "stale"
    if series_id in set(_as_list(summary.get("fulfilledSeries"))):
        return "fulfilled"
    if series_id in set(_as_list(summary.get("missingSeries"))):
        return "missing"
    return "missing"


def _series_blocked_reason(summary: Mapping[str, object], series_id: str, status: str) -> str | None:
    if status == "fulfilled":
        return None
    if status == "stale":
        return "stale_series"
    top_level_reason = str(summary.get("reason") or "").strip()
    if top_level_reason:
        return top_level_reason
    if summary.get("sourceAuthorityAllowed") is False:
        return "source_authority_blocked"
    if summary.get("scoreContributionAllowed") is False:
        return "score_contribution_blocked"
    return "series_coverage" if series_id in set(_as_list(summary.get("missingSeries"))) else "readiness_blocked"


def _series_readiness(summary: Mapping[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for group in _SERIES_READINESS_GROUPS:
        group_name = str(group["group"])
        series_to_symbol = group.get("seriesToSymbol")
        freshness_policies = group.get("freshnessPolicies")
        for series_id in _as_list(group.get("series")):
            status = _series_status(summary, series_id)
            symbol = (
                str(series_to_symbol.get(series_id) or "").strip()
                if isinstance(series_to_symbol, Mapping)
                else ""
            )
            freshness_policy = (
                str(freshness_policies.get(series_id) or "").strip()
                if isinstance(freshness_policies, Mapping)
                else ""
            )
            blocked_reason = _series_blocked_reason(summary, series_id, status)
            rows.append(
                {
                    "group": group_name,
                    "series": series_id,
                    "symbol": symbol or None,
                    "freshnessPolicy": freshness_policy or None,
                    "status": status,
                    "blocked": blocked_reason is not None,
                    "blockedReason": blocked_reason,
                }
            )
    return rows


def _operator_next_gate(summary: Mapping[str, object]) -> str:
    readiness = str(summary.get("readiness") or "").strip().lower()
    return "run_official_macro_cache_prewarm" if readiness == "ready" else "remediate_required_series_before_prewarm"


def _decorate_cache_readiness_summary(summary: Mapping[str, object]) -> dict[str, object]:
    required_series = _as_list(summary.get("requiredSeries")) or _required_series()
    decorated = dict(summary)
    decorated["requiredSeries"] = required_series
    if "requiredSeriesStatus" not in decorated:
        decorated["requiredSeriesStatus"] = _required_series_status(summary, required_series)
    decorated["seriesReadiness"] = _series_readiness(decorated)
    decorated["operatorNextGate"] = _operator_next_gate(decorated)
    return decorated


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a bounded official macro activation diagnostic.",
    )
    parser.add_argument(
        "--cache-readiness",
        action="store_true",
        help=(
            "Emit diagnostic-only official macro cache readiness evidence with "
            "requiredSeries, seriesReadiness, and operatorNextGate fields."
        ),
    )
    return parser


def _run_cache_readiness_smoke() -> dict[str, object]:
    usd_pressure = run_usd_pressure_live_smoke()
    fed_liquidity = run_fed_liquidity_live_smoke()
    raw_groups = {
        "usdPressure": usd_pressure,
        "fedLiquidity": fed_liquidity,
    }
    groups = {
        name: _sanitize_group_summary(raw_groups[name], _CACHE_READINESS_GROUPS[name])
        for name in _CACHE_READINESS_GROUPS
    }
    required_series_status: dict[str, str] = {}
    missing_series: list[str] = []
    stale_series: list[str] = []
    for name, series_ids in _CACHE_READINESS_GROUPS.items():
        status_by_series = groups[name]["requiredSeriesStatus"]
        if not isinstance(status_by_series, Mapping):
            continue
        for series_id in series_ids:
            status = str(status_by_series.get(series_id) or "missing")
            required_series_status[series_id] = status
            if status == "missing":
                missing_series.append(series_id)
            elif status == "stale":
                stale_series.append(series_id)

    credentials_present = all(bool(summary.get("credentialsPresent")) for summary in groups.values())
    provider_constructed = all(bool(summary.get("providerConstructed")) for summary in groups.values())
    freshness_valid = all(bool(summary.get("freshnessValid")) for summary in groups.values())
    source_metadata_valid = all(bool(summary.get("sourceMetadataValid")) for summary in groups.values())
    probe_passed = all(bool(summary.get("probePassed")) for summary in groups.values())
    source_authority_allowed = all(bool(summary.get("sourceAuthorityAllowed")) for summary in groups.values())
    score_contribution_allowed = all(bool(summary.get("scoreContributionAllowed")) for summary in groups.values())

    return _decorate_cache_readiness_summary(
        {
        "credentialsPresent": credentials_present,
        "keyPresent": credentials_present,
        "providerConstructed": provider_constructed,
        "probePassed": probe_passed,
        "readiness": "ready" if probe_passed and source_authority_allowed and score_contribution_allowed else "blocked",
        "freshnessValid": freshness_valid,
        "sourceMetadataValid": source_metadata_valid,
        "sourceAuthorityAllowed": source_authority_allowed,
        "scoreContributionAllowed": score_contribution_allowed,
        "requiredSeriesStatus": required_series_status,
        "missingSeries": missing_series,
        "staleSeries": stale_series,
        "reason": _aggregate_reason(groups),
        "groups": groups,
        }
    )


def main(argv: Sequence[str] | None = None) -> int:
    parsed = _build_parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    cache_readiness = parsed.cache_readiness
    try:
        summary = _run_cache_readiness_smoke() if cache_readiness else run_official_macro_live_smoke()
    except Exception:
        fallback = _cache_readiness_unexpected_error_summary() if cache_readiness else _unexpected_error_summary()
        print(json.dumps(fallback, ensure_ascii=False, sort_keys=True))
        return EXIT_FAILED
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
