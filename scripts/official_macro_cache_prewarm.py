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
    OFFICIAL_FED_LIQUIDITY_REQUIRED_SERIES,
    OFFICIAL_USD_PRESSURE_REQUIRED_SERIES,
    OFFICIAL_US_RATES_REQUIRED_SERIES,
)


REFRESH_WAIT_TIMEOUT_SECONDS = 5.0
REQUIRED_SERIES: tuple[str, ...] = (
    *OFFICIAL_US_RATES_REQUIRED_SERIES,
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


def _as_list(values: object) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []
    return [str(value) for value in values if str(value or "").strip()]


def _unique(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value or "").strip()))


def _required_series() -> list[str]:
    return _unique(REQUIRED_SERIES)


def _target_panel_reports(*, write_attempted: bool) -> list[dict[str, object]]:
    return [
        {
            "cacheKey": str(panel["cacheKey"]),
            "panel": str(panel["panel"]),
            "writeAttempted": write_attempted,
            "writeWouldBeAttemptedWithWrite": not write_attempted,
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


def _diagnostic_fulfills_required_series(item: Mapping[str, object], *, required: set[str]) -> bool:
    series_id = _series_id(item)
    if series_id not in required:
        return False
    freshness = str(item.get("freshness") or "").strip().lower()
    if freshness not in {"live", "fresh", "cached", "delayed"}:
        return False
    if item.get("sourceAuthorityAllowed") is not True:
        return False
    if item.get("scoreContributionAllowed") is not True:
        return False
    if item.get("isFallback") or item.get("fallbackUsed") or item.get("isUnavailable") or item.get("isPartial"):
        return False
    source_type = str(item.get("sourceType") or "").strip().lower()
    if source_type != "official_public":
        return False
    return True


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


def _fulfilled_required_series(panels: Sequence[dict[str, object]]) -> list[str]:
    required = set(_required_series())
    fulfilled: list[str] = []
    for panel in panels:
        diagnostics = panel.get("targetDiagnostics")
        if not isinstance(diagnostics, Sequence) or isinstance(diagnostics, (str, bytes, bytearray)):
            continue
        for item in diagnostics:
            if not isinstance(item, Mapping):
                continue
            series_id = _series_id(item)
            if series_id in fulfilled:
                continue
            if _diagnostic_fulfills_required_series(item, required=required):
                fulfilled.append(series_id)
    required_order = _required_series()
    return [series_id for series_id in required_order if series_id in set(fulfilled)]


def _summary_fields(
    *,
    write: bool,
    panels: Sequence[dict[str, object]] | None = None,
    cache_rows_written: int = 0,
    reason: str | None = None,
) -> dict[str, object]:
    required = _required_series()
    fulfilled = _fulfilled_required_series(panels or []) if write else []
    missing = [series_id for series_id in required if series_id not in set(fulfilled)] if write else []
    return {
        "dryRun": not write,
        "writeEnabled": write,
        "writeAttempted": write,
        "requiredSeries": required,
        "fulfilledSeries": fulfilled,
        "missingSeries": missing,
        "cacheRowsWouldWrite": 0 if write else len(TARGET_PANELS),
        "cacheRowsWritten": cache_rows_written if write else 0,
        "reason": reason or ("required_series_missing" if missing else ("write_attempted" if write else "dry_run_no_write")),
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
) -> dict[str, object]:
    target_panels = _target_panel_reports(write_attempted=write)
    if not write:
        return {
            "mode": "dry-run",
            **_summary_fields(write=False),
            "result": "dry_run_no_write",
            "targetPanels": target_panels,
        }

    service = service_factory()
    payloads = service.prewarm_official_macro_cache()
    refreshes_completed = _wait_for_market_cache_refreshes(service)
    panels = [
        _panel_result(panel, payloads.get(str(panel["cacheKey"]), {}))
        for panel in TARGET_PANELS
    ]
    summary = _summary_fields(
        write=True,
        panels=panels,
        cache_rows_written=_count_returned_cache_rows(payloads),
    )
    return {
        "mode": "write",
        **summary,
        "result": "write_attempted",
        "targetPanels": target_panels,
        "panels": panels,
        "marketCacheRefreshesCompleted": refreshes_completed,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prewarm official macro Market Overview cache rows. Defaults to dry-run.",
    )
    parser.set_defaults(write=False)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        dest="write",
        action="store_false",
        help="Report targets without mutating Market Overview cache or snapshots.",
    )
    mode.add_argument(
        "--write",
        dest="write",
        action="store_true",
        help="Invoke the existing Market Overview macro/rates cache refresh path.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_prewarm(write=bool(args.write))
    except Exception as exc:
        print(
            json.dumps(
                {
                    "mode": "write" if args.write else "dry-run",
                    **_summary_fields(
                        write=bool(args.write),
                        reason="error",
                    ),
                    "result": "error",
                    "errorClass": type(exc).__name__,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
