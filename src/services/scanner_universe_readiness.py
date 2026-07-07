# -*- coding: utf-8 -*-
"""Scanner universe readiness contract.

This module is intentionally local and read-only: it inspects configured local
universe/cache signals and combines them with scanner quote/history coverage
without touching provider runtime behavior.
"""

from __future__ import annotations

import csv
from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.services.scanner_universe_lifecycle import (
    SCANNER_UNIVERSE_DEFAULT_MAX_AGE_DAYS,
    SCANNER_UNIVERSE_DEFAULT_MINIMUM_COVERAGE,
    SCANNER_UNIVERSE_LIFECYCLE_CONTRACT_VERSION,
)


SCANNER_UNIVERSE_READINESS_CONTRACT_VERSION = "scanner_universe_readiness_v1"
SCANNER_UNIVERSE_SUPPORTED_STATUSES = (
    "available",
    "ready",
    "missing",
    "stale",
    "invalid",
    "blocked",
    "not_configured",
    "insufficient_coverage",
    "unavailable",
    "deferred",
    "manual_action_required",
    "local_universe_available",
    "local_universe_seeded",
    "quote_snapshot_stale",
    "provider_not_configured",
)
SCANNER_UNIVERSE_REQUIRED_DATA_CLASSES = (
    "universe",
    "historical_ohlcv",
    "quote_snapshot",
)
SCANNER_UNIVERSE_BLOCKED_SURFACES = ("Scanner", "Research Radar", "Backtest", "Market Overview")
SCANNER_UNIVERSE_MAX_AGE_DAYS = 3
SCANNER_UNIVERSE_SAFE_DATA_FAMILIES = (
    "universe",
    "historical_ohlcv",
    "quote_snapshot",
    "benchmark_ohlcv",
    "date_coverage",
    "freshness",
    "adjusted_prices",
)

FileMtimeReader = Callable[[Path], float | None]


def _safe_market(value: Any) -> str:
    normalized = str(value or "").strip().upper()
    return normalized if normalized in {"CN", "US", "HK"} else "CN"


def _date_from_mtime(value: float | None) -> date | None:
    if value is None:
        return None
    try:
        if 1 <= value <= 4_000_000:
            return date.fromordinal(int(value))
        return datetime.fromtimestamp(float(value), tz=timezone.utc).date()
    except (OSError, OverflowError, ValueError):
        return None


def _iso_from_mtime(value: float | None) -> str | None:
    if value is None:
        return None
    try:
        if 1 <= value <= 4_000_000:
            return datetime.combine(date.fromordinal(int(value)), datetime.min.time(), tzinfo=timezone.utc).isoformat()
        return datetime.fromtimestamp(float(value), tz=timezone.utc).replace(microsecond=0).isoformat()
    except (OSError, OverflowError, ValueError):
        return None


def _default_file_mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _count_csv_rows(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return 0
            return sum(1 for row in reader if any(str(value or "").strip() for value in row.values()))
    except Exception:
        return 0


def _safe_symbol_list(values: list[str] | None, *, limit: int = 50) -> list[str]:
    result: list[str] = []
    for value in values or []:
        symbol = str(value or "").strip().upper()
        if not symbol:
            continue
        if not all(ch.isalnum() or ch in {".", "-", "_"} for ch in symbol):
            continue
        if symbol not in result:
            result.append(symbol)
        if len(result) >= limit:
            break
    return result


def _safe_data_family_list(values: list[str] | None) -> list[str]:
    result: list[str] = []
    allowed = set(SCANNER_UNIVERSE_SAFE_DATA_FAMILIES)
    for value in values or []:
        family = str(value or "").strip().lower()
        if family in allowed and family not in result:
            result.append(family)
    return result


def build_scanner_universe_readiness_contract(
    *,
    market: str,
    status: str,
    universe_size: int = 0,
    last_updated_at: str | None = None,
    freshness_state: str = "unknown",
    required_data_classes: list[str] | None = None,
    available_data_classes: list[str] | None = None,
    blocked_product_surfaces: list[str] | None = None,
    operator_next_action: str | None = None,
    consumer_safe_message: str | None = None,
    seeded_symbols: list[str] | None = None,
    eligible_symbols: list[str] | None = None,
    blocked_symbols: list[str] | None = None,
    missing_data_families: list[str] | None = None,
    source_class: str | None = None,
    source_path: str | None = None,
    symbols: list[str] | None = None,
    generated_from: str | None = None,
    no_external_calls: bool = True,
    provider_calls_enabled: bool = False,
    read_only: bool = True,
    activation_state: str | None = None,
    lifecycle_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_status = str(status or "").strip().lower()
    if normalized_status == "ready":
        normalized_status = "available"
    if normalized_status not in SCANNER_UNIVERSE_SUPPORTED_STATUSES:
        normalized_status = "unavailable"
    required = list(required_data_classes or SCANNER_UNIVERSE_REQUIRED_DATA_CLASSES)
    available = [
        str(item)
        for item in (available_data_classes or [])
        if str(item or "").strip() and str(item) in required
    ]
    missing = [item for item in required if item not in set(available)]
    missing_families = _safe_data_family_list(missing_data_families or missing)
    effectively_available = normalized_status in {
        "available",
        "local_universe_available",
        "local_universe_seeded",
    }
    surfaces = list(blocked_product_surfaces or (() if effectively_available else SCANNER_UNIVERSE_BLOCKED_SURFACES))
    next_action = operator_next_action or _operator_next_action(normalized_status)
    reason = _reason_code(normalized_status)
    lifecycle = dict(lifecycle_readiness or {})
    symbol_count = int(lifecycle.get("symbolCount") or universe_size or 0)
    minimum_coverage_threshold = int(
        lifecycle.get("minimumCoverageThreshold")
        or SCANNER_UNIVERSE_DEFAULT_MINIMUM_COVERAGE.get(_safe_market(market), 1)
    )
    has_lifecycle_contract = bool(lifecycle)
    blocking_reasons = _safe_reason_list(lifecycle.get("blockingReasons"))
    if not blocking_reasons:
        if normalized_status in {"missing", "not_configured"}:
            blocking_reasons.append("source_missing")
        elif normalized_status == "stale":
            blocking_reasons.append("stale_universe")
        elif normalized_status == "invalid":
            blocking_reasons.append("metadata_malformed")
        elif normalized_status == "blocked" and lifecycle.get("usable") is not True:
            blocking_reasons.append("candidate_generation_blocked")
        elif normalized_status == "unavailable":
            blocking_reasons.append("metadata_malformed")
        elif normalized_status == "insufficient_coverage" and not has_lifecycle_contract:
            blocking_reasons.append("below_minimum_coverage")
    coverage_state = str(
        lifecycle.get("coverageState")
        or ("sufficient" if symbol_count >= minimum_coverage_threshold and symbol_count > 0 else "insufficient")
    )
    usable = bool(lifecycle.get("usable")) if "usable" in lifecycle else bool(effectively_available and not blocking_reasons)
    downstream_impact = (
        dict(lifecycle.get("downstreamImpact"))
        if isinstance(lifecycle.get("downstreamImpact"), dict)
        else {
            "contractVersion": "scanner_universe_downstream_impact_v1",
            "blockedProducts": [] if usable else surfaces,
            "blockingReasons": blocking_reasons,
            "readOnly": True,
            "consumerSafe": True,
        }
    )
    return {
        "contractVersion": SCANNER_UNIVERSE_READINESS_CONTRACT_VERSION,
        "lifecycleContractVersion": str(
            lifecycle.get("contractVersion") or SCANNER_UNIVERSE_LIFECYCLE_CONTRACT_VERSION
        ),
        "status": normalized_status,
        "reason": reason,
        "market": _safe_market(market),
        "universeVersion": lifecycle.get("universeVersion"),
        "generatedAt": lifecycle.get("generatedAt") or last_updated_at,
        "universeSize": max(0, int(universe_size or 0)),
        "symbolCount": symbol_count,
        "lastUpdatedAt": last_updated_at,
        "asOf": lifecycle.get("asOf") or last_updated_at,
        "freshnessState": str(lifecycle.get("freshnessState") or freshness_state or "unknown"),
        "freshness": str(freshness_state or "unknown"),
        "age": lifecycle.get("age") or {"days": None, "maxAgeDays": SCANNER_UNIVERSE_DEFAULT_MAX_AGE_DAYS},
        "coverageState": coverage_state,
        "usable": usable,
        "blockingReasons": blocking_reasons,
        "downstreamImpact": downstream_impact,
        "lastSuccessfulActivation": lifecycle.get("lastSuccessfulActivation"),
        "lastRejectedImportReason": lifecycle.get("lastRejectedImportReason"),
        "requiredDataClasses": required,
        "availableDataClasses": available,
        "missingDataClasses": missing,
        "missingDataFamilies": missing_families,
        "seededSymbols": _safe_symbol_list(seeded_symbols),
        "eligibleSymbols": _safe_symbol_list(eligible_symbols),
        "blockedSymbols": _safe_symbol_list(blocked_symbols),
        "sourceClass": str(source_class or "").strip() or None,
        "sourcePath": str(source_path or "").strip() or None,
        "symbols": _safe_symbol_list(symbols),
        "generatedFrom": str(generated_from or "").strip() or None,
        "noExternalCalls": bool(no_external_calls),
        "providerCallsEnabled": bool(provider_calls_enabled),
        "readOnly": bool(read_only),
        "activationState": str(activation_state or normalized_status).strip() or normalized_status,
        "blockedProductSurfaces": surfaces,
        "affectedProductSurfaces": surfaces,
        "blockingModules": surfaces,
        "operatorAction": next_action,
        "operatorNextAction": next_action,
        "nextOperatorAction": next_action,
        "consumerSafeMessage": consumer_safe_message or _consumer_safe_message(normalized_status),
        "consumerSafe": True,
    }


def build_scanner_universe_readiness_from_cache(
    *,
    market: str,
    cache_path: str | Path | None,
    today: date | None = None,
    file_mtime: FileMtimeReader | None = None,
) -> dict[str, Any]:
    if cache_path is None or not str(cache_path).strip():
        return build_scanner_universe_readiness_contract(
            market=market,
            status="not_configured",
            freshness_state="not_configured",
            operator_next_action="Configure the scanner universe path, then refresh the local universe before running Scanner.",
            consumer_safe_message="扫描标的池尚未配置，暂时无法生成候选。",
        )

    path = Path(str(cache_path)).expanduser()
    mtime_reader = file_mtime or _default_file_mtime
    mtime = mtime_reader(path)
    if mtime is None:
        return build_scanner_universe_readiness_contract(
            market=market,
            status="missing",
            freshness_state="missing_universe",
            operator_next_action="Create or refresh the scanner local universe before expecting Scanner candidates.",
            consumer_safe_message="扫描标的池缺失，暂时无法生成候选。",
        )

    current_day = today or date.today()
    modified_date = _date_from_mtime(mtime)
    row_count = _count_csv_rows(path)
    if modified_date is None:
        return build_scanner_universe_readiness_contract(
            market=market,
            status="unavailable",
            universe_size=row_count,
            last_updated_at=_iso_from_mtime(mtime),
            freshness_state="universe_modified:unknown",
            operator_next_action="Refresh the scanner local universe and rerun scanner readiness checks.",
            consumer_safe_message="扫描标的池状态无法确认，暂时无法生成候选。",
        )
    if row_count <= 0:
        return build_scanner_universe_readiness_contract(
            market=market,
            status="missing",
            universe_size=0,
            last_updated_at=_iso_from_mtime(mtime),
            freshness_state=f"universe_modified:{modified_date.isoformat()}",
            operator_next_action="Refresh the scanner local universe with valid symbols before running Scanner.",
            consumer_safe_message="扫描标的池为空，暂时无法生成候选。",
        )
    if (current_day - modified_date).days > SCANNER_UNIVERSE_MAX_AGE_DAYS:
        return build_scanner_universe_readiness_contract(
            market=market,
            status="stale",
            universe_size=row_count,
            last_updated_at=_iso_from_mtime(mtime),
            freshness_state=f"universe_modified:{modified_date.isoformat()}",
            available_data_classes=["universe"],
            operator_next_action="Refresh the scanner local universe and rerun scanner readiness checks before candidate generation.",
            consumer_safe_message="扫描标的池已过期，需要更新后再扫描。",
        )

    return build_scanner_universe_readiness_contract(
        market=market,
        status="insufficient_coverage",
        universe_size=row_count,
        last_updated_at=_iso_from_mtime(mtime),
        freshness_state=f"universe_modified:{modified_date.isoformat()}",
        available_data_classes=["universe"],
        operator_next_action="Use the refreshed local universe only after seeded historical OHLCV and quote coverage are confirmed.",
        consumer_safe_message="扫描标的池已更新，但仍需确认历史行情与报价覆盖。",
    )


def build_scanner_universe_readiness_from_coverage(
    *,
    market: str,
    universe_status: str,
    universe_size: int,
    last_updated_at: str | None,
    freshness_state: str,
    quote_coverage: str,
    history_coverage: str,
    blocked: bool,
    historical_requirements: list[str] | None = None,
    seeded_symbols: list[str] | None = None,
    eligible_symbols: list[str] | None = None,
    blocked_symbols: list[str] | None = None,
    missing_data_families: list[str] | None = None,
    operator_next_action: str | None = None,
    source_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_universe_status = str(universe_status or "").strip().lower()
    available_classes: list[str] = []
    if normalized_universe_status in {"available", "local_universe_available", "local_universe_seeded"} and int(universe_size or 0) > 0:
        available_classes.append("universe")
    if str(history_coverage or "").strip().lower() == "available":
        available_classes.append("historical_ohlcv")
    if str(quote_coverage or "").strip().lower() == "available":
        available_classes.append("quote_snapshot")

    requirements = {str(item or "").strip().lower() for item in historical_requirements or []}
    local_universe_statuses = {"local_universe_available", "local_universe_seeded"}
    metadata = dict(source_metadata or {})
    lifecycle_readiness = (
        dict(metadata.get("lifecycleReadiness"))
        if isinstance(metadata.get("lifecycleReadiness"), dict)
        else None
    )
    lifecycle_reasons = {
        str(item or "").strip().lower()
        for item in (lifecycle_readiness or {}).get("blockingReasons", [])
        if str(item or "").strip()
    }
    lifecycle_invalid_reasons = {
        "metadata_malformed",
        "normalization_rejected",
        "empty_universe",
        "source_as_of_missing",
    }
    lifecycle_blocked_reasons = {
        "source_policy_unknown",
        "suspicious_universe_shrink",
        "market_data_readiness_not_evaluated",
        "scanner_candidates_unavailable",
    }
    if normalized_universe_status in local_universe_statuses:
        status = normalized_universe_status
    elif normalized_universe_status in {"missing", "stale", "not_configured"}:
        status = normalized_universe_status
    elif lifecycle_reasons.intersection(lifecycle_invalid_reasons):
        status = "invalid"
    elif lifecycle_reasons.intersection({"source_missing"}):
        status = "missing"
    elif lifecycle_reasons.intersection({"stale_source", "stale_universe"}):
        status = "stale"
    elif lifecycle_reasons.intersection(lifecycle_blocked_reasons):
        status = "blocked"
    elif normalized_universe_status == "unavailable":
        status = normalized_universe_status
    elif "provider_missing" in requirements:
        status = "not_configured"
    elif requirements.intersection({"provider_unavailable", "entitlement_required"}):
        status = "unavailable"
    elif "stale_data" in requirements:
        status = "stale"
    elif blocked or set(available_classes) != set(SCANNER_UNIVERSE_REQUIRED_DATA_CLASSES):
        status = "blocked" if lifecycle_readiness else "insufficient_coverage"
    else:
        status = "available"

    return build_scanner_universe_readiness_contract(
        market=market,
        status=status,
        universe_size=universe_size,
        last_updated_at=last_updated_at,
        freshness_state=freshness_state,
        available_data_classes=available_classes,
        seeded_symbols=seeded_symbols,
        eligible_symbols=eligible_symbols,
        blocked_symbols=blocked_symbols,
        missing_data_families=missing_data_families,
        operator_next_action=operator_next_action,
        source_class=metadata.get("sourceClass"),
        source_path=metadata.get("sourcePath"),
        symbols=metadata.get("symbols") if isinstance(metadata.get("symbols"), list) else None,
        generated_from=metadata.get("generatedFrom"),
        no_external_calls=bool(metadata.get("noExternalCalls", True)),
        provider_calls_enabled=bool(metadata.get("providerCallsEnabled", False)),
        read_only=bool(metadata.get("readOnly", True)),
        activation_state=str(metadata.get("activationState") or status),
        lifecycle_readiness=lifecycle_readiness,
    )


def _safe_reason_list(values: Any) -> list[str]:
    result: list[str] = []
    if not isinstance(values, list):
        return result
    for value in values:
        reason = str(value or "").strip()
        if reason and reason not in result:
            result.append(reason)
    return result


def _operator_next_action(status: str) -> str:
    if status == "not_configured":
        return "Configure the scanner universe path, then refresh the local universe."
    if status == "provider_not_configured":
        return "Configure the local scanner universe source before running Scanner."
    if status == "missing":
        return "Create or refresh the scanner local universe before running Scanner."
    if status == "stale":
        return "Refresh the scanner local universe and rerun scanner readiness checks."
    if status == "quote_snapshot_stale":
        return "Refresh quote snapshot coverage before candidate generation."
    if status == "invalid":
        return "Inspect the rejected scanner universe import and repair the configured source before activation."
    if status == "blocked":
        return "Resolve scanner universe blocking reasons before candidate generation."
    if status == "insufficient_coverage":
        return "Refresh or seed historical OHLCV and quote coverage for the current universe."
    if status in {"available", "local_universe_available", "local_universe_seeded"}:
        return "Run Scanner with bounded candidate generation from the current universe."
    return "Inspect scanner data readiness and refresh the current universe path."


def _reason_code(status: str) -> str:
    if status in {"available", "local_universe_available", "local_universe_seeded"}:
        return "ready"
    return f"scanner_universe_{status or 'unavailable'}"


def _consumer_safe_message(status: str) -> str:
    if status == "not_configured":
        return "扫描标的池尚未配置，暂时无法生成候选。"
    if status == "provider_not_configured":
        return "本地扫描标的池来源尚未配置，暂时无法生成候选。"
    if status == "missing":
        return "扫描标的池缺失，暂时无法生成候选。"
    if status == "stale":
        return "扫描标的池已过期，需要更新后再扫描。"
    if status == "quote_snapshot_stale":
        return "行情快照已过期，需要刷新后再生成候选。"
    if status == "invalid":
        return "扫描标的池导入无效，需要修复来源后再激活。"
    if status == "blocked":
        return "扫描标的池尚有阻塞项，暂不生成候选。"
    if status == "insufficient_coverage":
        return "标的池可用，但行情或历史覆盖不足，暂不生成候选。"
    if status in {"available", "local_universe_available", "local_universe_seeded"}:
        return "标的池与必要行情覆盖已满足本轮扫描。"
    return "扫描标的池状态无法确认，暂时无法生成候选。"


__all__ = [
    "SCANNER_UNIVERSE_BLOCKED_SURFACES",
    "SCANNER_UNIVERSE_READINESS_CONTRACT_VERSION",
    "SCANNER_UNIVERSE_SUPPORTED_STATUSES",
    "build_scanner_universe_readiness_contract",
    "build_scanner_universe_readiness_from_cache",
    "build_scanner_universe_readiness_from_coverage",
]
