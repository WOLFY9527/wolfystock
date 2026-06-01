#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Opt-in official macro cache prewarm entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.market_overview_service import MarketOverviewService
from src.services.official_macro_liquidity_cache_contracts import (
    OFFICIAL_FED_LIQUIDITY_FRESHNESS_POLICIES,
    OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES,
    OFFICIAL_FED_LIQUIDITY_SERIES_TO_SYMBOL,
    OFFICIAL_USD_PRESSURE_FRESHNESS_POLICIES,
    OFFICIAL_USD_PRESSURE_REQUIRED_SERIES,
    OFFICIAL_USD_PRESSURE_SYMBOL_TO_SERIES_ID,
    OFFICIAL_US_RATES_REQUIRED_SERIES,
)
from scripts.diagnose_official_macro_activation import (
    _cache_readiness_unexpected_error_summary,
    _run_cache_readiness_smoke,
)


REFRESH_WAIT_TIMEOUT_SECONDS = 5.0
CACHE_READINESS_REQUIRED_SERIES: tuple[str, ...] = (
    *OFFICIAL_USD_PRESSURE_REQUIRED_SERIES,
    *OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES,
)

TARGET_PANELS: tuple[dict[str, object], ...] = (
    {
        "cacheKey": "rates",
        "panel": "Market Overview rates",
        "targetGroups": (
            {
                "name": "us_rates",
                "symbols": ("US2Y", "US10Y", "US30Y", "SOFR", "US10Y2Y", "US10Y3M"),
                "series": (*OFFICIAL_US_RATES_REQUIRED_SERIES, "SOFR", "T10Y2Y", "T10Y3M"),
            },
        ),
    },
    {
        "cacheKey": "macro",
        "panel": "Market Overview macro",
        "targetGroups": (
            {
                "name": "usd_pressure",
                "symbols": ("USD_TWI",),
                "series": OFFICIAL_USD_PRESSURE_REQUIRED_SERIES,
            },
            {
                "name": "us_rates",
                "symbols": ("US2Y", "US10Y", "US30Y", "SOFR", "US10Y2Y", "US10Y3M"),
                "series": (*OFFICIAL_US_RATES_REQUIRED_SERIES, "SOFR", "T10Y2Y", "T10Y3M"),
            },
            {
                "name": "fed_liquidity",
                "symbols": ("FED_ASSETS", "FED_RRP", "TGA", "RESERVES"),
                "series": OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES,
            },
        ),
    },
)
SERIES_READINESS_GROUPS: tuple[dict[str, object], ...] = (
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
WRITE_EVIDENCE_FIELDS: tuple[str, ...] = (
    "writeEnabled",
    "writeAttempted",
    "cacheRowsWouldWrite",
    "cacheRowsWritten",
    "writeEfficacy",
    "scoreGradeUsable",
    "writtenButNotScoreGradeReason",
)


def _as_list(values: object) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    return [str(value) for value in values if str(value or "").strip()]


def _unique(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value or "").strip()))


def _target_panel_reports(*, write_attempted: bool) -> list[dict[str, object]]:
    return [
        {
            "cacheKey": str(panel["cacheKey"]),
            "panel": str(panel["panel"]),
            "writeAttempted": write_attempted,
            "writeWouldBeAttemptedWithWrite": not write_attempted,
            **_efficacy_fields(diagnostics=[], write_attempted=write_attempted),
            "targetGroups": [
                {
                    "name": str(group["name"]),
                    "symbols": _as_list(group.get("symbols")),
                    "series": _as_list(group.get("series")),
                }
                for group in panel.get("targetGroups", ())
                if isinstance(group, Mapping)
            ],
        }
        for panel in TARGET_PANELS
    ]


def _target_symbols(panel: Mapping[str, object]) -> set[str]:
    symbols: set[str] = set()
    for group in panel.get("targetGroups", ()):
        if isinstance(group, Mapping):
            symbols.update(_as_list(group.get("symbols")))
    return symbols


def _target_series(panel: Mapping[str, object]) -> set[str]:
    series: set[str] = set()
    for group in panel.get("targetGroups", ()):
        if isinstance(group, Mapping):
            series.update(_as_list(group.get("series")))
    return series


def _series_id(item: Mapping[str, object]) -> str:
    raw = (
        item.get("officialSeriesId")
        or item.get("series")
        or item.get("seriesId")
        or item.get("sourceId")
        or item.get("symbol")
        or ""
    )
    text = str(raw)
    return text.rsplit(":", 1)[-1].upper() if ":" in text else text.upper()


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _diagnostic_reason(item: Mapping[str, object]) -> str | None:
    for key in (
        "sourceAuthorityReason",
        "degradationReason",
        "officialOverlayFailureReason",
    ):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    route_codes = item.get("routeRejectedReasonCodes")
    if isinstance(route_codes, Sequence) and not isinstance(route_codes, (str, bytes, bytearray)):
        for value in route_codes:
            text = str(value or "").strip()
            if text:
                return text
    return None


def _target_diagnostics(panel: Mapping[str, object], payload: Mapping[str, object]) -> list[dict[str, object]]:
    symbols = _target_symbols(panel)
    series_ids = _target_series(panel)
    diagnostics: list[dict[str, object]] = []
    items = payload.get("items")
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
        return diagnostics
    for item in items:
        if not isinstance(item, Mapping):
            continue
        symbol = str(item.get("symbol") or "").strip()
        series_id = _series_id(item)
        if symbol not in symbols and series_id not in series_ids:
            continue
        route_codes = item.get("routeRejectedReasonCodes")
        diagnostics.append(
            {
                "symbol": symbol,
                "series": series_id,
                "freshness": item.get("freshness"),
                "source": item.get("source"),
                "sourceType": item.get("sourceType"),
                "isFallback": item.get("isFallback") is True,
                "isUnavailable": item.get("isUnavailable") is True,
                "sourceAuthorityAllowed": _optional_bool(item.get("sourceAuthorityAllowed")),
                "scoreContributionAllowed": _optional_bool(item.get("scoreContributionAllowed")),
                "sourceAuthorityReason": item.get("sourceAuthorityReason"),
                "degradationReason": item.get("degradationReason"),
                "officialOverlayFailureReason": item.get("officialOverlayFailureReason"),
                "routeRejectedReasonCodes": _as_list(route_codes),
                "reason": _diagnostic_reason(item),
            }
        )
    return diagnostics


def _normalized_reason(reason: object) -> str | None:
    text = str(reason or "").strip().lower()
    if not text:
        return None
    if "budget" in text:
        return "budget_exhausted"
    if "timeout" in text:
        return "timeout"
    return text


def _degraded_target_reasons(diagnostic: Mapping[str, object]) -> list[str]:
    reasons: list[str] = []
    normalized_reason = _normalized_reason(diagnostic.get("reason"))
    freshness = str(diagnostic.get("freshness") or "").strip().lower()

    if diagnostic.get("isFallback") is True or freshness == "fallback":
        reasons.append("fallback")
    if normalized_reason:
        reasons.append(normalized_reason)
    elif diagnostic.get("isUnavailable") is True or freshness == "unavailable":
        reasons.append("unavailable")
    elif freshness == "stale":
        reasons.append("stale")

    if diagnostic.get("sourceAuthorityAllowed") is False and not normalized_reason:
        reasons.append("source_authority_blocked")
    if (
        diagnostic.get("scoreContributionAllowed") is False
        and not normalized_reason
        and diagnostic.get("sourceAuthorityAllowed") is not False
    ):
        reasons.append("score_contribution_blocked")
    return _unique(reasons)


def _degraded_target_symbol(diagnostic: Mapping[str, object]) -> str | None:
    symbol = str(diagnostic.get("symbol") or "").strip()
    if symbol:
        return symbol
    series = str(diagnostic.get("series") or "").strip()
    return series or None


def _efficacy_fields(
    *,
    diagnostics: Sequence[Mapping[str, object]],
    write_attempted: bool,
) -> dict[str, object]:
    if not write_attempted:
        return {
            "writeEfficacy": "not_written",
            "scoreGradeUsable": False,
            "degradedTargetCount": 0,
            "degradedTargetSymbols": [],
            "degradedTargetReasons": [],
            "writtenButNotScoreGradeReason": "write_not_attempted",
        }

    degraded_symbols: list[str] = []
    degraded_reasons: list[str] = []
    seen_symbols: set[str] = set()
    degraded_count = 0

    for diagnostic in diagnostics:
        reasons = _degraded_target_reasons(diagnostic)
        if not reasons:
            continue
        degraded_count += 1
        symbol = _degraded_target_symbol(diagnostic)
        if symbol and symbol not in seen_symbols:
            seen_symbols.add(symbol)
            degraded_symbols.append(symbol)
        degraded_reasons.extend(reasons)

    degraded_reasons = _unique(degraded_reasons)
    score_grade_usable = degraded_count == 0
    return {
        "writeEfficacy": (
            "written_score_grade_usable"
            if score_grade_usable
            else "written_not_score_grade_usable"
        ),
        "scoreGradeUsable": score_grade_usable,
        "degradedTargetCount": degraded_count,
        "degradedTargetSymbols": degraded_symbols,
        "degradedTargetReasons": degraded_reasons,
        "writtenButNotScoreGradeReason": None if score_grade_usable else "degraded_target_diagnostics",
    }


def _safe_cache_readiness_summary(readiness_probe: Callable[[], Mapping[str, object]]) -> Mapping[str, object]:
    try:
        summary = readiness_probe()
    except Exception:
        return _cache_readiness_unexpected_error_summary()
    return summary if isinstance(summary, Mapping) else _cache_readiness_unexpected_error_summary()


def _readiness_required_series(summary: Mapping[str, object]) -> list[str]:
    status_by_series = summary.get("requiredSeriesStatus")
    if isinstance(status_by_series, Mapping):
        return _unique([str(series_id) for series_id in status_by_series.keys()])
    explicit = _as_list(summary.get("requiredSeries"))
    if explicit:
        return _unique(explicit)
    return _unique(CACHE_READINESS_REQUIRED_SERIES)


def _series_status(summary: Mapping[str, object], series_id: str) -> str:
    status_by_series = summary.get("requiredSeriesStatus")
    if isinstance(status_by_series, Mapping):
        return str(status_by_series.get(series_id) or "missing").strip().lower()
    if series_id in set(_as_list(summary.get("staleSeries"))):
        return "stale"
    if series_id in set(_as_list(summary.get("fulfilledSeries"))):
        return "fulfilled"
    if series_id in set(_as_list(summary.get("missingSeries"))):
        return "missing"
    return "missing"


def _readiness_summary_fields(summary: Mapping[str, object]) -> dict[str, object]:
    required = _readiness_required_series(summary)
    fulfilled = [series_id for series_id in required if _series_status(summary, series_id) == "fulfilled"]
    stale = [series_id for series_id in required if _series_status(summary, series_id) == "stale"]
    missing = [
        series_id
        for series_id in required
        if _series_status(summary, series_id) not in {"fulfilled", "stale"}
    ]
    source_authority_allowed = summary.get("sourceAuthorityAllowed") is True
    score_contribution_allowed = summary.get("scoreContributionAllowed") is True
    readiness = str(summary.get("readiness") or "").strip().lower()
    if readiness not in {"ready", "blocked"}:
        readiness = (
            "ready"
            if required and not missing and not stale and source_authority_allowed and score_contribution_allowed
            else "blocked"
        )
    reason = str(summary.get("reason") or "").strip() or None
    if readiness == "blocked" and reason is None:
        if stale:
            reason = "stale_series"
        elif missing:
            reason = "series_coverage"
        elif not source_authority_allowed:
            reason = "source_authority_blocked"
        elif not score_contribution_allowed:
            reason = "score_contribution_blocked"
        else:
            reason = "readiness_blocked"
    return {
        "readiness": readiness,
        "reason": reason,
        "requiredSeries": required,
        "fulfilledSeries": fulfilled,
        "missingSeries": missing,
        "staleSeries": stale,
        "sourceAuthorityAllowed": source_authority_allowed,
        "scoreContributionAllowed": score_contribution_allowed,
    }


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
    for group in SERIES_READINESS_GROUPS:
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


def _operator_evidence(summary: Mapping[str, object]) -> dict[str, object]:
    return {
        "writeEvidence": {
            field: summary.get(field)
            for field in WRITE_EVIDENCE_FIELDS
        },
        "seriesReadiness": _series_readiness(summary),
    }


def _summary_fields(
    *,
    write_enabled: bool,
    write_attempted: bool,
    readiness_summary: Mapping[str, object],
    cache_rows_written: int = 0,
) -> dict[str, object]:
    readiness_fields = _readiness_summary_fields(readiness_summary)
    return {
        "dryRun": not write_enabled,
        "writeEnabled": write_enabled,
        "writeAttempted": write_attempted,
        **readiness_fields,
        "cacheRowsWouldWrite": 0 if write_enabled else len(TARGET_PANELS),
        "cacheRowsWritten": cache_rows_written if write_attempted else 0,
    }


def _panel_result(panel: Mapping[str, object], payload: Mapping[str, object]) -> dict[str, object]:
    diagnostics = _target_diagnostics(panel, payload)
    return {
        "cacheKey": str(panel["cacheKey"]),
        "panel": str(panel["panel"]),
        "source": payload.get("source"),
        "freshness": payload.get("freshness"),
        "itemCount": len(payload.get("items") or []) if isinstance(payload.get("items"), list) else 0,
        "targetSymbolsFound": [item["symbol"] for item in diagnostics if item.get("symbol")],
        "targetDiagnostics": diagnostics,
        **_efficacy_fields(diagnostics=diagnostics, write_attempted=True),
    }


def _wait_for_market_cache_refreshes(service: object) -> bool | None:
    cache = getattr(service, "_market_cache", None)
    wait_for_refreshes = getattr(cache, "wait_for_refreshes", None)
    if not callable(wait_for_refreshes):
        return None
    return bool(wait_for_refreshes(timeout=REFRESH_WAIT_TIMEOUT_SECONDS))


def _count_returned_cache_rows(payloads: Mapping[str, object]) -> int:
    count = 0
    for panel in TARGET_PANELS:
        payload = payloads.get(str(panel["cacheKey"]))
        if isinstance(payload, Mapping) and payload:
            count += 1
    return count


def run_prewarm(
    *,
    write: bool,
    service_factory: Callable[[], MarketOverviewService] = MarketOverviewService,
    readiness_probe: Callable[[], Mapping[str, object]] | None = None,
) -> dict[str, object]:
    target_panels = _target_panel_reports(write_attempted=write)
    readiness_summary = _safe_cache_readiness_summary(readiness_probe or _run_cache_readiness_smoke)
    if not write:
        result = {
            "mode": "dry-run",
            **_summary_fields(
                write_enabled=False,
                write_attempted=False,
                readiness_summary=readiness_summary,
            ),
            **_efficacy_fields(diagnostics=[], write_attempted=False),
            "result": "dry_run_no_write",
            "targetPanels": target_panels,
        }
        result.update(_operator_evidence(result))
        return result

    blocked_summary = _summary_fields(
        write_enabled=True,
        write_attempted=False,
        readiness_summary=readiness_summary,
    )
    if blocked_summary["readiness"] != "ready":
        result = {
            "mode": "write",
            **blocked_summary,
            **_efficacy_fields(diagnostics=[], write_attempted=False),
            "result": "readiness_blocked",
            "targetPanels": target_panels,
        }
        result.update(_operator_evidence(result))
        return result

    service = service_factory()
    payloads = service.prewarm_official_macro_cache()
    refreshes_completed = _wait_for_market_cache_refreshes(service)
    panels = [
        _panel_result(panel, payloads.get(str(panel["cacheKey"]), {}))
        for panel in TARGET_PANELS
    ]
    summary = _summary_fields(
        write_enabled=True,
        write_attempted=True,
        readiness_summary=readiness_summary,
        cache_rows_written=_count_returned_cache_rows(payloads),
    )
    result = {
        "mode": "write",
        **summary,
        **_efficacy_fields(
            diagnostics=[
                diagnostic
                for panel in panels
                for diagnostic in panel.get("targetDiagnostics", ())
                if isinstance(diagnostic, Mapping)
            ],
            write_attempted=True,
        ),
        "result": "write_attempted",
        "targetPanels": target_panels,
        "panels": panels,
        "marketCacheRefreshesCompleted": refreshes_completed,
    }
    result.update(_operator_evidence(result))
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Report official macro cache readiness and optionally prewarm existing "
            "Market Overview rates/macro cache rows. Defaults to dry-run."
        ),
    )
    parser.set_defaults(write=False)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        dest="write",
        action="store_false",
        help="Report required series readiness and write evidence without mutating cache or snapshots.",
    )
    mode.add_argument(
        "--write",
        dest="write",
        action="store_true",
        help="Attempt the existing Market Overview macro/rates cache refresh path after readiness passes.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_prewarm(write=bool(args.write))
    except Exception as exc:
        error_payload = {
            "mode": "write" if args.write else "dry-run",
            **_summary_fields(
                write_enabled=bool(args.write),
                write_attempted=False,
                readiness_summary=_cache_readiness_unexpected_error_summary(),
            ),
            **_efficacy_fields(diagnostics=[], write_attempted=False),
            "result": "error",
            "errorClass": type(exc).__name__,
        }
        error_payload.update(_operator_evidence(error_payload))
        print(json.dumps(error_payload, ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if bool(args.write) and result.get("result") == "readiness_blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
