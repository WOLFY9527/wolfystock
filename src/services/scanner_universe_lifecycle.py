# -*- coding: utf-8 -*-
"""Deterministic scanner universe lifecycle contracts.

This module is intentionally local-file based. It validates explicit repository
or operator supplied inputs, activates only accepted universe versions, and
builds read-only readiness projections without provider calls.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.utils.symbol_classification import is_bse_code, is_us_stock_code
from src.utils.symbol_normalization import normalize_stock_code


SCANNER_UNIVERSE_LIFECYCLE_CONTRACT_VERSION = "scanner_universe_lifecycle_v1"
SCANNER_UNIVERSE_DEFAULT_ROOT = "./data/scanner_universe_lifecycle"
SCANNER_UNIVERSE_DEFAULT_MAX_AGE_DAYS = 3
SCANNER_UNIVERSE_DEFAULT_MINIMUM_COVERAGE = {
    "CN": 300,
    "US": 6,
    "HK": 30,
}
SCANNER_UNIVERSE_BLOCKED_PRODUCTS = ("Scanner", "Research Radar", "Backtest", "Market Overview")


class ScannerUniverseLifecycleStore:
    """Filesystem-backed active/rejected universe metadata store."""

    def __init__(self, root: str | Path | None = None) -> None:
        configured_root = root or os.getenv("SCANNER_UNIVERSE_LIFECYCLE_ROOT") or SCANNER_UNIVERSE_DEFAULT_ROOT
        self.root = Path(str(configured_root)).expanduser()

    def market_dir(self, market: str) -> Path:
        return self.root / _normalize_market(market).lower()

    def active_path(self, market: str) -> Path:
        return self.market_dir(market) / "active.json"

    def rejected_path(self, market: str) -> Path:
        return self.market_dir(market) / "last_rejected.json"

    def version_path(self, market: str, universe_version: str) -> Path:
        return self.market_dir(market) / "versions" / f"{universe_version}.json"

    def load_active(self, market: str) -> dict[str, Any] | None:
        return _read_json_file(self.active_path(market))

    def load_rejected(self, market: str) -> dict[str, Any] | None:
        return _read_json_file(self.rejected_path(market))

    def activate(self, market: str, metadata: Mapping[str, Any]) -> None:
        market_dir = self.market_dir(market)
        market_dir.mkdir(parents=True, exist_ok=True)
        version = str(metadata["universeVersion"])
        version_path = self.version_path(market, version)
        version_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(version_path, dict(metadata))
        _atomic_write_json(self.active_path(market), dict(metadata))

    def record_rejected(self, market: str, payload: Mapping[str, Any]) -> None:
        market_dir = self.market_dir(market)
        market_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(self.rejected_path(market), dict(payload))


def normalize_scanner_universe_symbol(value: Any, *, market: str) -> str | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    normalized_market = _normalize_market(market)
    if normalized_market == "US":
        symbol = raw.upper()
        return symbol if is_us_stock_code(symbol) else None
    symbol = normalize_stock_code(raw).upper()
    if normalized_market == "HK":
        return symbol if _is_hk_symbol(symbol) else None
    if normalized_market == "CN":
        return symbol if _is_cn_common_symbol(symbol) else None
    return None


def activate_scanner_universe_from_file(
    *,
    source_path: str | Path,
    store: ScannerUniverseLifecycleStore | None = None,
    market: str,
    minimum_coverage_threshold: int | None = None,
    activated_at: datetime | None = None,
) -> dict[str, Any]:
    lifecycle_store = store or ScannerUniverseLifecycleStore()
    normalized_market = _normalize_market(market)
    threshold = _coverage_threshold(normalized_market, minimum_coverage_threshold)
    previous = lifecycle_store.load_active(normalized_market)
    previous_version = previous.get("universeVersion") if isinstance(previous, dict) else None
    source = Path(str(source_path)).expanduser()
    now = _normalize_datetime(activated_at)

    payload = _read_json_file(source)
    if payload is None:
        return _reject_import(
            store=lifecycle_store,
            market=normalized_market,
            source_path=source,
            previous_version=previous_version,
            reasons=["source_missing"],
            now=now,
        )
    if not isinstance(payload, dict):
        return _reject_import(
            store=lifecycle_store,
            market=normalized_market,
            source_path=source,
            previous_version=previous_version,
            reasons=["metadata_malformed"],
            now=now,
        )

    source_market = _normalize_market(payload.get("market") or normalized_market)
    if source_market != normalized_market:
        return _reject_import(
            store=lifecycle_store,
            market=normalized_market,
            source_path=source,
            previous_version=previous_version,
            reasons=["market_mismatch"],
            now=now,
        )

    raw_symbols = payload.get("symbols")
    if not isinstance(raw_symbols, list):
        return _reject_import(
            store=lifecycle_store,
            market=normalized_market,
            source_path=source,
            previous_version=previous_version,
            reasons=["metadata_malformed"],
            now=now,
        )

    normalized_symbols, rejected_symbols = _normalize_symbols(raw_symbols, market=normalized_market)
    reasons: list[str] = []
    if rejected_symbols:
        reasons.append("normalization_rejected")
    if not normalized_symbols:
        reasons.append("empty_universe")
    if normalized_symbols and len(normalized_symbols) < threshold:
        reasons.append("below_minimum_coverage")
    if reasons:
        return _reject_import(
            store=lifecycle_store,
            market=normalized_market,
            source_path=source,
            previous_version=previous_version,
            reasons=reasons,
            now=now,
            normalized_symbols=normalized_symbols,
            rejected_symbols=rejected_symbols,
        )

    generated_at = _iso_datetime(payload.get("generatedAt") or now.isoformat())
    as_of = str(payload.get("asOf") or generated_at[:10]).strip()
    source_class = _safe_source_class(payload.get("sourceClass"))
    source_identity = f"{normalized_market}|{generated_at}|{as_of}|{source_class}|{','.join(normalized_symbols)}"
    digest = hashlib.sha256(source_identity.encode("utf-8")).hexdigest()[:16]
    universe_version = f"scanner-universe-{normalized_market.lower()}-{digest}"
    metadata = {
        "contractVersion": SCANNER_UNIVERSE_LIFECYCLE_CONTRACT_VERSION,
        "market": normalized_market,
        "universeVersion": universe_version,
        "generatedAt": generated_at,
        "asOf": as_of,
        "sourceClass": source_class,
        "sourcePath": _source_path_label(source),
        "symbols": normalized_symbols,
        "symbolCount": len(normalized_symbols),
        "minimumCoverageThreshold": threshold,
        "activatedAt": now.isoformat(),
        "previousUniverseVersion": previous_version,
        "readOnly": True,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
    }
    lifecycle_store.activate(normalized_market, metadata)
    return {
        "contractVersion": "scanner_universe_import_action_v1",
        "status": "activated",
        "market": normalized_market,
        "universeVersion": universe_version,
        "symbolCount": len(normalized_symbols),
        "previousUniverseVersion": previous_version,
        "rejectedReasons": [],
        "readOnly": False,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
    }


def build_scanner_universe_lifecycle_readiness(
    *,
    store: ScannerUniverseLifecycleStore | None = None,
    market: str,
    minimum_coverage_threshold: int | None = None,
    max_age_days: int = SCANNER_UNIVERSE_DEFAULT_MAX_AGE_DAYS,
    now: datetime | None = None,
) -> dict[str, Any]:
    lifecycle_store = store or ScannerUniverseLifecycleStore()
    normalized_market = _normalize_market(market)
    current_time = _normalize_datetime(now)
    active_path = lifecycle_store.active_path(normalized_market)
    rejected = lifecycle_store.load_rejected(normalized_market) or {}
    active = lifecycle_store.load_active(normalized_market)
    threshold = _coverage_threshold(
        normalized_market,
        minimum_coverage_threshold
        if minimum_coverage_threshold is not None
        else active.get("minimumCoverageThreshold")
        if isinstance(active, dict)
        else None,
    )

    if active is None:
        if active_path.exists():
            return _readiness_blocked(
                market=normalized_market,
                threshold=threshold,
                reasons=["metadata_malformed"],
                last_rejected=rejected,
            )
        return _readiness_blocked(
            market=normalized_market,
            threshold=threshold,
            reasons=["source_missing"],
            last_rejected=rejected,
        )

    symbols = active.get("symbols")
    generated_at = _parse_datetime(active.get("generatedAt"))
    blocking_reasons: list[str] = []
    if not isinstance(symbols, list) or not all(isinstance(item, str) and item for item in symbols):
        blocking_reasons.append("metadata_malformed")
        symbols = []
    if generated_at is None:
        blocking_reasons.append("metadata_malformed")

    symbol_count = len(symbols)
    age_days: int | None = None
    if generated_at is not None:
        age_seconds = max(0.0, (current_time - generated_at).total_seconds())
        age_days = int(age_seconds // 86400)
        if age_days > int(max_age_days):
            blocking_reasons.append("stale_universe")
    if symbol_count <= 0:
        blocking_reasons.append("empty_universe")
    if symbol_count < threshold:
        blocking_reasons.append("below_minimum_coverage")

    blocking_reasons = list(dict.fromkeys(blocking_reasons))
    freshness_state = "malformed" if "metadata_malformed" in blocking_reasons else "stale" if "stale_universe" in blocking_reasons else "fresh"
    coverage_state = "sufficient" if symbol_count >= threshold and symbol_count > 0 else "insufficient"
    usable = not blocking_reasons
    blocked_products = [] if usable else list(SCANNER_UNIVERSE_BLOCKED_PRODUCTS)
    return {
        "contractVersion": SCANNER_UNIVERSE_LIFECYCLE_CONTRACT_VERSION,
        "market": normalized_market,
        "universeVersion": str(active.get("universeVersion") or ""),
        "generatedAt": active.get("generatedAt"),
        "asOf": active.get("asOf"),
        "sourceClass": _safe_source_class(active.get("sourceClass")),
        "sourcePath": str(active.get("sourcePath") or ""),
        "symbols": list(symbols),
        "symbolCount": symbol_count,
        "freshnessState": freshness_state,
        "age": {"days": age_days, "maxAgeDays": int(max_age_days)},
        "minimumCoverageThreshold": threshold,
        "coverageState": coverage_state,
        "usable": usable,
        "blockingReasons": blocking_reasons,
        "downstreamImpact": {
            "contractVersion": "scanner_universe_downstream_impact_v1",
            "blockedProducts": blocked_products,
            "blockingReasons": blocking_reasons,
            "readOnly": True,
            "consumerSafe": True,
        },
        "lastSuccessfulActivation": active.get("activatedAt"),
        "lastRejectedImportReason": _last_rejected_reason(rejected),
        "lastRejectedImport": _public_rejected(rejected),
        "readOnly": True,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
        "consumerSafe": True,
    }


def _reject_import(
    *,
    store: ScannerUniverseLifecycleStore,
    market: str,
    source_path: Path,
    previous_version: Any,
    reasons: list[str],
    now: datetime,
    normalized_symbols: list[str] | None = None,
    rejected_symbols: list[str] | None = None,
) -> dict[str, Any]:
    primary_reason = reasons[0] if reasons else "rejected"
    rejected = {
        "contractVersion": "scanner_universe_import_rejection_v1",
        "status": "rejected",
        "market": market,
        "sourcePath": _source_path_label(source_path),
        "rejectedAt": now.isoformat(),
        "rejectedReasons": reasons,
        "primaryReason": primary_reason,
        "normalizedSymbolCount": len(normalized_symbols or []),
        "rejectedSymbolCount": len(rejected_symbols or []),
        "previousUniverseVersion": previous_version,
        "readOnly": True,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
    }
    store.record_rejected(market, rejected)
    return rejected


def _normalize_symbols(values: Iterable[Any], *, market: str) -> tuple[list[str], list[str]]:
    symbols: list[str] = []
    rejected: list[str] = []
    for value in values:
        normalized = normalize_scanner_universe_symbol(value, market=market)
        if normalized is None:
            rejected.append(str(value))
            continue
        if normalized not in symbols:
            symbols.append(normalized)
    return symbols, rejected


def _readiness_blocked(
    *,
    market: str,
    threshold: int,
    reasons: list[str],
    last_rejected: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "contractVersion": SCANNER_UNIVERSE_LIFECYCLE_CONTRACT_VERSION,
        "market": market,
        "universeVersion": None,
        "generatedAt": None,
        "asOf": None,
        "sourceClass": None,
        "sourcePath": None,
        "symbols": [],
        "symbolCount": 0,
        "freshnessState": "missing" if "source_missing" in reasons else "malformed",
        "age": {"days": None, "maxAgeDays": SCANNER_UNIVERSE_DEFAULT_MAX_AGE_DAYS},
        "minimumCoverageThreshold": threshold,
        "coverageState": "insufficient",
        "usable": False,
        "blockingReasons": reasons,
        "downstreamImpact": {
            "contractVersion": "scanner_universe_downstream_impact_v1",
            "blockedProducts": list(SCANNER_UNIVERSE_BLOCKED_PRODUCTS),
            "blockingReasons": reasons,
            "readOnly": True,
            "consumerSafe": True,
        },
        "lastSuccessfulActivation": None,
        "lastRejectedImportReason": _last_rejected_reason(last_rejected),
        "lastRejectedImport": _public_rejected(last_rejected),
        "readOnly": True,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
        "consumerSafe": True,
    }


def _normalize_market(value: Any) -> str:
    normalized = str(value or "").strip().upper()
    return normalized if normalized in {"CN", "US", "HK"} else "CN"


def _coverage_threshold(market: str, value: int | None) -> int:
    if value is not None:
        return max(1, int(value))
    return SCANNER_UNIVERSE_DEFAULT_MINIMUM_COVERAGE.get(_normalize_market(market), 1)


def _is_cn_common_symbol(value: str) -> bool:
    normalized = normalize_stock_code(value)
    if not normalized.isdigit() or len(normalized) != 6:
        return False
    if is_bse_code(normalized):
        return False
    return normalized.startswith(("000", "001", "002", "003", "300", "301", "600", "601", "603", "605", "688", "689"))


def _is_hk_symbol(value: str) -> bool:
    normalized = normalize_stock_code(value).upper()
    return normalized.startswith("HK") and normalized[2:].isdigit() and len(normalized) == 7


def _safe_source_class(value: Any) -> str:
    text = str(value or "explicit_local_source").strip()
    return text if text else "explicit_local_source"


def _source_path_label(path: Path) -> str:
    return path.name if path.name else "local_source"


def _normalize_datetime(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc).replace(microsecond=0)


def _parse_datetime(value: Any) -> datetime | None:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _iso_datetime(value: Any) -> str:
    parsed = _parse_datetime(value)
    if parsed is None:
        parsed = datetime.now(timezone.utc)
    return parsed.replace(microsecond=0).isoformat()


def _read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def _last_rejected_reason(payload: Mapping[str, Any]) -> str | None:
    reason = str(payload.get("primaryReason") or "").strip()
    if reason:
        return reason
    reasons = payload.get("rejectedReasons")
    if isinstance(reasons, list) and reasons:
        return str(reasons[0])
    return None


def _public_rejected(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    if not payload:
        return None
    return {
        "status": payload.get("status"),
        "market": payload.get("market"),
        "rejectedAt": payload.get("rejectedAt"),
        "rejectedReasons": list(payload.get("rejectedReasons") or []),
        "primaryReason": _last_rejected_reason(payload),
        "previousUniverseVersion": payload.get("previousUniverseVersion"),
        "readOnly": True,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
    }


__all__ = [
    "SCANNER_UNIVERSE_LIFECYCLE_CONTRACT_VERSION",
    "ScannerUniverseLifecycleStore",
    "activate_scanner_universe_from_file",
    "build_scanner_universe_lifecycle_readiness",
    "normalize_scanner_universe_symbol",
]
