#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run a bounded official macro live smoke diagnostic."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.official_macro_transport import (
    FED_LIQUIDITY_FRED_SERIES_IDS,
    USD_PRESSURE_FRED_SERIES_IDS,
    run_fed_liquidity_live_smoke,
    run_official_macro_live_smoke,
    run_usd_pressure_live_smoke,
)

EXIT_OK = 0
EXIT_FAILED = 1
_CACHE_READINESS_GROUPS = {
    "usdPressure": USD_PRESSURE_FRED_SERIES_IDS,
    "fedLiquidity": FED_LIQUIDITY_FRED_SERIES_IDS,
}
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
    return {
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

    return {
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


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cache_readiness = "--cache-readiness" in set(args)
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
