# -*- coding: utf-8 -*-
"""Deterministic scanner universe lifecycle contracts.

This module is intentionally local-file based. It validates explicit repository
or operator supplied inputs, activates only accepted universe versions, and
builds read-only readiness projections without provider calls.
"""

from __future__ import annotations

import hashlib
import csv
import json
import os
from datetime import date, datetime, timezone
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
SCANNER_UNIVERSE_DEFAULT_MAX_SHRINK_PERCENTAGE = 80.0
SCANNER_UNIVERSE_SOURCE_CONTRACT_VERSION = "scanner_universe_source_membership_v1"
SCANNER_UNIVERSE_SOURCE_INVENTORY_VERSION = "scanner_universe_source_inventory_v1"
SCANNER_UNIVERSE_SOURCE_DISCOVERY_VERSION = "scanner_universe_source_artifact_discovery_v1"
SCANNER_UNIVERSE_QUALIFICATION_DECISION_VERSION = "scanner_universe_activation_qualification_decision_v1"
SCANNER_UNIVERSE_QUALIFICATION_PACK_VERSION = "scanner_universe_activation_qualification_pack_v1"
SCANNER_UNIVERSE_CURRENT_STATE_MATRIX_VERSION = "scanner_universe_current_state_matrix_v1"
SCANNER_UNIVERSE_COVERAGE_PROOF_VERSION = "scanner_universe_coverage_proof_v1"
SCANNER_UNIVERSE_DOWNSTREAM_READINESS_VERSION = "scanner_universe_downstream_readiness_separation_v1"
SCANNER_UNIVERSE_APPROVED_POLICY_STATES = frozenset({"approved", "operator_supplied"})
SCANNER_UNIVERSE_BLOCKED_PRODUCTS = ("Scanner", "Research Radar", "Backtest", "Market Overview")
SCANNER_UNIVERSE_MARKETS = ("CN", "US", "HK")


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


def build_scanner_universe_source_inventory() -> dict[str, Any]:
    """Return the read-only ownership map for known universe/listing sources.

    This is an inventory, not an approval grant. Network-capable providers stay
    policy-unknown unless repository or operator approval is explicit.
    """

    return {
        "contractVersion": SCANNER_UNIVERSE_SOURCE_INVENTORY_VERSION,
        "readOnly": True,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
        "markets": [
            {
                "market": "CN",
                "currentScannerResolver": "MarketScannerService._resolve_cn_stock_universe",
                "sources": [
                    _source_inventory_record(
                        source_name="local_universe_cache",
                        owner_module="src.services.market_scanner_service",
                        source_class="repository_local_csv",
                        network_or_local="local",
                        authentication_requirement="none",
                        commercial_licensing_uncertainty=False,
                        available_metadata=["code", "name"],
                        normalization_requirement="strip SH/SZ/BJ prefixes and exchange suffixes to six-digit A-share code",
                        freshness_characteristics="file mtime only; not source generated timestamp",
                        current_product_usage="current Scanner CN resolver first input",
                        suitability="operator_supplied",
                    ),
                    _source_inventory_record(
                        source_name="TushareFetcher.stock_basic",
                        owner_module="data_provider.tushare_fetcher",
                        source_class="provider_listing_capability",
                        network_or_local="network",
                        authentication_requirement="tushare token and quota/permission",
                        commercial_licensing_uncertainty=True,
                        available_metadata=["code", "name"],
                        normalization_requirement="strip exchange suffix/prefix to repository CN scanner code",
                        freshness_characteristics="provider response time; controlled by provider and token entitlement",
                        current_product_usage="current Scanner CN resolver provider attempt",
                        suitability="blocked_until_policy_approved",
                    ),
                    _source_inventory_record(
                        source_name="AkshareFetcher.stock_info_a_code_name",
                        owner_module="data_provider.akshare_fetcher / src.services.name_to_code_resolver",
                        source_class="provider_listing_capability",
                        network_or_local="network",
                        authentication_requirement="none, but dependency and upstream page availability required",
                        commercial_licensing_uncertainty=True,
                        available_metadata=["code", "name"],
                        normalization_requirement="strip exchange suffix/prefix to repository CN scanner code",
                        freshness_characteristics="live scrape/library response; no durable source timestamp",
                        current_product_usage="current Scanner CN resolver fallback attempt and name resolver",
                        suitability="blocked_until_policy_approved",
                    ),
                    _source_inventory_record(
                        source_name="db_local_fallback",
                        owner_module="src.repositories.scanner_repo / src.repositories.stock_repo",
                        source_class="database_backed_listing_inventory",
                        network_or_local="local",
                        authentication_requirement="local database access",
                        commercial_licensing_uncertainty=False,
                        available_metadata=["code", "name"],
                        normalization_requirement="normalize to six-digit CN scanner code",
                        freshness_characteristics="derived from local analysis/history rows; not exchange listing authority",
                        current_product_usage="current Scanner CN resolver fallback",
                        suitability="operator_supplied",
                    ),
                    _source_inventory_record(
                        source_name="builtin_stock_mapping",
                        owner_module="src.data.stock_mapping",
                        source_class="repository_local_symbol_mapping",
                        network_or_local="local",
                        authentication_requirement="none",
                        commercial_licensing_uncertainty=False,
                        available_metadata=["code", "name"],
                        normalization_requirement="filter to supported CN common stock prefixes",
                        freshness_characteristics="static repository mapping; freshness unknown",
                        current_product_usage="current Scanner CN resolver last fallback",
                        suitability="unknown_policy",
                    ),
                ],
            },
            {
                "market": "US",
                "currentScannerResolver": "MarketScannerService._resolve_us_stock_universe",
                "sources": [
                    _source_inventory_record(
                        source_name="local_us_parquet_dir",
                        owner_module="src.services.us_history_helper / src.services.market_scanner_service",
                        source_class="local_parquet_symbol_inventory",
                        network_or_local="local",
                        authentication_requirement="none",
                        commercial_licensing_uncertainty=False,
                        available_metadata=["filename ticker", "local OHLCV presence"],
                        normalization_requirement="uppercase US ticker, reject index symbols",
                        freshness_characteristics="filesystem presence/mtime; does not prove listing status",
                        current_product_usage="current Scanner US resolver first source, bounded to starter symbols",
                        suitability="operator_supplied",
                    ),
                    _source_inventory_record(
                        source_name="local_db_us_history",
                        owner_module="src.services.market_scanner_service / stock_daily repository",
                        source_class="database_backed_symbol_inventory",
                        network_or_local="local",
                        authentication_requirement="local database access",
                        commercial_licensing_uncertainty=False,
                        available_metadata=["symbol", "history presence"],
                        normalization_requirement="uppercase US ticker, reject index symbols",
                        freshness_characteristics="derived from local history rows; not exchange listing authority",
                        current_product_usage="current Scanner US resolver fallback, bounded to starter symbols",
                        suitability="operator_supplied",
                    ),
                    _source_inventory_record(
                        source_name="alpaca_assets_metadata",
                        owner_module="data_provider.alpaca_fetcher",
                        source_class="provider_asset_metadata_capability",
                        network_or_local="network",
                        authentication_requirement="Alpaca API key and secret",
                        commercial_licensing_uncertainty=True,
                        available_metadata=["symbol", "exchange", "asset class/status if endpoint is added"],
                        normalization_requirement="uppercase US ticker, reject index symbols and unsupported assets",
                        freshness_characteristics="provider retrieval timestamp; product policy not inferred from access",
                        current_product_usage="not current Scanner universe owner",
                        suitability="blocked_until_policy_approved",
                        related_sources=[
                            {"sourceName": "local_us_parquet_dir", "networkOrLocal": "local"},
                            {"sourceName": "AlpacaFetcher.market_data", "networkOrLocal": "network"},
                        ],
                    ),
                    _source_inventory_record(
                        source_name="exchange_nasdaq_nyse_listing_files",
                        owner_module="not implemented",
                        source_class="exchange_listing_source_support",
                        network_or_local="network",
                        authentication_requirement="operator-supplied approved artifact required",
                        commercial_licensing_uncertainty=True,
                        available_metadata=["symbol", "exchange", "security type", "listing status"],
                        normalization_requirement="uppercase US ticker, reject non-common unsupported forms",
                        freshness_characteristics="source artifact as-of/import timestamp required",
                        current_product_usage="not implemented",
                        suitability="blocked_until_policy_approved",
                    ),
                ],
            },
            {
                "market": "HK",
                "currentScannerResolver": "MarketScannerService._resolve_hk_stock_universe",
                "sources": [
                    _source_inventory_record(
                        source_name="local_db_hk_history",
                        owner_module="src.services.market_scanner_service / stock_daily repository",
                        source_class="database_backed_symbol_inventory",
                        network_or_local="local",
                        authentication_requirement="local database access",
                        commercial_licensing_uncertainty=False,
                        available_metadata=["symbol", "history presence"],
                        normalization_requirement="zero-pad HK numeric forms to HKxxxxx",
                        freshness_characteristics="derived from local history rows; not exchange listing authority",
                        current_product_usage="current Scanner HK resolver first source",
                        suitability="operator_supplied",
                    ),
                    _source_inventory_record(
                        source_name="curated_hk_liquid_seed_symbols",
                        owner_module="src.services.market_scanner_service",
                        source_class="repository_local_symbol_seed",
                        network_or_local="local",
                        authentication_requirement="none",
                        commercial_licensing_uncertainty=False,
                        available_metadata=["symbol only"],
                        normalization_requirement="zero-pad HK numeric forms to HKxxxxx",
                        freshness_characteristics="static repository seed; not listing authority",
                        current_product_usage="current Scanner HK resolver supplement",
                        suitability="unknown_policy",
                    ),
                    _source_inventory_record(
                        source_name="hk_exchange_listing_metadata",
                        owner_module="not implemented",
                        source_class="exchange_listing_metadata_path",
                        network_or_local="network",
                        authentication_requirement="operator-supplied approved artifact required",
                        commercial_licensing_uncertainty=True,
                        available_metadata=["symbol", "exchange", "security type", "listing status"],
                        normalization_requirement="zero-pad HK numeric forms to HKxxxxx",
                        freshness_characteristics="source artifact as-of/import timestamp required",
                        current_product_usage="not implemented",
                        suitability="blocked_until_policy_approved",
                    ),
                ],
            },
        ],
    }


def read_scanner_universe_source_file(source_path: str | Path, *, market: str) -> dict[str, Any]:
    """Read an explicit local source artifact and project normalized memberships."""

    normalized_market = _normalize_market(market)
    source = Path(str(source_path)).expanduser()
    payload = _read_json_payload(source)
    if isinstance(payload, list):
        return _read_frontend_stock_index_source(
            payload=payload,
            source_path=source,
            market=normalized_market,
        )
    if not isinstance(payload, dict):
        return _source_projection_blocked(
            market=normalized_market,
            source_path=source,
            reasons=["source_missing_or_malformed"],
        )
    if not isinstance(payload.get("symbols"), list):
        return _source_projection_blocked(
            market=normalized_market,
            source_path=source,
            payload=payload,
            reasons=["metadata_malformed"],
        )

    source_market = _normalize_market(payload.get("market") or normalized_market)
    reasons: list[str] = []
    if source_market != normalized_market:
        reasons.append("market_mismatch")

    memberships: list[dict[str, Any]] = []
    seen: set[str] = set()
    active_symbols: list[str] = []
    duplicate_count = 0
    normalized_change_count = 0
    for item in payload.get("symbols") or []:
        raw_symbol, exchange, security_type, listing_status = _extract_source_symbol_record(item)
        normalized = normalize_scanner_universe_symbol(raw_symbol, market=normalized_market)
        if normalized is None:
            memberships.append(
                _membership_record(
                    raw_symbol=raw_symbol,
                    normalized_symbol=None,
                    result="unsupported_symbol",
                    status="rejected",
                    exchange=exchange,
                    security_type=security_type,
                    listing_status=listing_status,
                    policy_state=_source_policy_state(payload.get("sourcePolicyState")),
                )
            )
            continue
        changed = str(raw_symbol or "").strip() != normalized
        if changed:
            normalized_change_count += 1
        if normalized in seen:
            duplicate_count += 1
            memberships.append(
                _membership_record(
                    raw_symbol=raw_symbol,
                    normalized_symbol=normalized,
                    result="duplicate_normalized",
                    status="duplicate",
                    exchange=exchange,
                    security_type=security_type,
                    listing_status=listing_status,
                    policy_state=_source_policy_state(payload.get("sourcePolicyState")),
                )
            )
            continue
        seen.add(normalized)
        active_symbols.append(normalized)
        memberships.append(
            _membership_record(
                raw_symbol=raw_symbol,
                normalized_symbol=normalized,
                result="normalized" if changed else "unchanged",
                status="active",
                exchange=exchange,
                security_type=security_type,
                listing_status=listing_status,
                policy_state=_source_policy_state(payload.get("sourcePolicyState")),
            )
        )

    policy_state = _source_policy_state(payload.get("sourcePolicyState"))
    source_as_of = _safe_text(payload.get("sourceAsOf") or payload.get("asOf"))
    retrieved_at = _safe_text(payload.get("retrievedAt") or payload.get("importedAt") or payload.get("generatedAt"))
    source_id = _safe_text(payload.get("sourceId")) or f"{normalized_market.lower()}:{_source_path_label(source)}"
    source_class = _safe_source_class(payload.get("sourceClass"))
    artifact_identity = _safe_text(payload.get("sourceArtifactIdentity")) or _artifact_identity(source, payload)
    if not source_as_of:
        reasons.append("source_as_of_missing")
    if not retrieved_at:
        reasons.append("retrieved_at_missing")
    if not artifact_identity:
        reasons.append("source_artifact_identity_missing")

    return {
        "contractVersion": SCANNER_UNIVERSE_SOURCE_CONTRACT_VERSION,
        "market": normalized_market,
        "sourceId": source_id,
        "sourceClass": source_class,
        "sourceAsOf": source_as_of,
        "retrievedAt": retrieved_at,
        "importedAt": _safe_text(payload.get("importedAt")) or retrieved_at,
        "sourceArtifactIdentity": artifact_identity,
        "sourcePath": _source_path_label(source),
        "symbolCount": len(active_symbols),
        "rawSymbolCount": len(payload.get("symbols") or []),
        "normalizedSymbols": active_symbols,
        "memberships": memberships,
        "rejectedSymbols": [item for item in memberships if item["membershipStatus"] == "rejected"],
        "duplicateSymbolCount": duplicate_count,
        "normalizedChangeCount": normalized_change_count,
        "sourcePolicyState": policy_state,
        "blockingReasons": list(dict.fromkeys(reasons)),
        "readOnly": True,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
    }


def _read_frontend_stock_index_source(
    *,
    payload: list[Any],
    source_path: Path,
    market: str,
) -> dict[str, Any]:
    memberships: list[dict[str, Any]] = []
    seen: set[str] = set()
    active_symbols: list[str] = []
    duplicate_count = 0
    normalized_change_count = 0
    relevant_raw_count = 0
    for row in payload:
        record = _extract_frontend_stock_index_record(row)
        if not record:
            continue
        if record["market"] != market:
            continue
        relevant_raw_count += 1
        raw_symbol = record["displayCode"] or record["canonicalCode"]
        normalized = normalize_scanner_universe_symbol(raw_symbol, market=market)
        if normalized is None:
            memberships.append(
                _membership_record(
                    raw_symbol=raw_symbol,
                    normalized_symbol=None,
                    result="unsupported_symbol",
                    status="rejected",
                    exchange=record["exchange"],
                    security_type=record["assetType"],
                    listing_status="active" if record["active"] else "unknown",
                    policy_state="unknown_policy",
                )
            )
            continue
        if str(raw_symbol or "").strip().upper() != normalized:
            normalized_change_count += 1
        if normalized in seen:
            duplicate_count += 1
            memberships.append(
                _membership_record(
                    raw_symbol=raw_symbol,
                    normalized_symbol=normalized,
                    result="duplicate_normalized",
                    status="duplicate",
                    exchange=record["exchange"],
                    security_type=record["assetType"],
                    listing_status="active" if record["active"] else "unknown",
                    policy_state="unknown_policy",
                )
            )
            continue
        seen.add(normalized)
        active_symbols.append(normalized)
        memberships.append(
            _membership_record(
                raw_symbol=raw_symbol,
                normalized_symbol=normalized,
                result="normalized",
                status="active",
                exchange=record["exchange"],
                security_type=record["assetType"],
                listing_status="active" if record["active"] else "unknown",
                policy_state="unknown_policy",
            )
        )
    return {
        "contractVersion": SCANNER_UNIVERSE_SOURCE_CONTRACT_VERSION,
        "market": market,
        "sourceId": f"repo:frontend_stock_index:{market}",
        "sourceClass": "repository_local_frontend_stock_index",
        "sourceAsOf": "",
        "retrievedAt": "",
        "importedAt": "",
        "sourceArtifactIdentity": _artifact_identity(source_path, {"market": market, "rows": payload}),
        "sourcePath": _source_path_label(source_path),
        "symbolCount": len(active_symbols),
        "rawSymbolCount": relevant_raw_count,
        "normalizedSymbols": active_symbols,
        "memberships": memberships,
        "rejectedSymbols": [item for item in memberships if item["membershipStatus"] == "rejected"],
        "duplicateSymbolCount": duplicate_count,
        "normalizedChangeCount": normalized_change_count,
        "sourcePolicyState": "unknown_policy",
        "blockingReasons": ["source_as_of_missing", "retrieved_at_missing"],
        "readOnly": True,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
    }


def dry_run_scanner_universe_source(
    *,
    source_path: str | Path,
    store: ScannerUniverseLifecycleStore | None = None,
    market: str,
    minimum_coverage_threshold: int | None = None,
    max_age_days: int = SCANNER_UNIVERSE_DEFAULT_MAX_AGE_DAYS,
    max_shrink_percentage: float = SCANNER_UNIVERSE_DEFAULT_MAX_SHRINK_PERCENTAGE,
    now: datetime | None = None,
) -> dict[str, Any]:
    lifecycle_store = store or ScannerUniverseLifecycleStore()
    normalized_market = _normalize_market(market)
    current_time = _normalize_datetime(now)
    source_projection = read_scanner_universe_source_file(source_path, market=normalized_market)
    previous = lifecycle_store.load_active(normalized_market)
    previous_symbols = _active_symbols(previous)
    threshold = _coverage_threshold(normalized_market, minimum_coverage_threshold)
    candidate_symbols = list(source_projection.get("normalizedSymbols") or [])
    diff = _build_universe_diff(
        previous_symbols=previous_symbols,
        candidate_symbols=candidate_symbols,
        normalized_change_count=int(source_projection.get("normalizedChangeCount") or 0),
        rejected_count=len(source_projection.get("rejectedSymbols") or []),
    )
    reasons = _qualification_reasons(
        projection=source_projection,
        symbol_count=len(candidate_symbols),
        threshold=threshold,
        now=current_time,
        max_age_days=max_age_days,
        max_shrink_percentage=max_shrink_percentage,
        diff=diff,
        previous_symbols=previous_symbols,
    )
    status = "accepted" if not reasons else "rejected"
    version = _candidate_universe_version(normalized_market, source_projection, candidate_symbols)
    raw_count = int(source_projection.get("rawSymbolCount") or 0)
    rejected_count = len(source_projection.get("rejectedSymbols") or [])
    freshness_state = (
        "stale"
        if "stale_source" in reasons
        else "missing"
        if "source_metadata_missing" in reasons or "source_as_of_missing" in reasons
        else "fresh"
    )
    coverage_state = "sufficient" if len(candidate_symbols) >= threshold and len(candidate_symbols) > 0 else "insufficient"
    return {
        "contractVersion": "scanner_universe_source_dry_run_v1",
        "status": status,
        "activationReady": status == "accepted",
        "dryRun": True,
        "market": normalized_market,
        "universeVersion": version if status == "accepted" else None,
        "candidateUniverseVersion": version,
        "rawSymbolCount": raw_count,
        "symbolCount": len(candidate_symbols),
        "normalizedSymbolCount": len(candidate_symbols),
        "duplicateSymbolCount": int(source_projection.get("duplicateSymbolCount") or 0),
        "rejectedSymbolCount": rejected_count,
        "normalizationRejectionRate": _rejection_rate(rejected_count, raw_count),
        "minimumCoverageThreshold": threshold,
        "freshnessState": freshness_state,
        "coverageState": coverage_state,
        "source": source_projection,
        "diff": diff,
        "rejectedReasons": reasons,
        "blockingReasons": reasons,
        "readOnly": True,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
        "mutationEnabled": False,
    }


def activate_scanner_universe_from_source(
    *,
    source_path: str | Path,
    store: ScannerUniverseLifecycleStore | None = None,
    market: str,
    minimum_coverage_threshold: int | None = None,
    max_age_days: int = SCANNER_UNIVERSE_DEFAULT_MAX_AGE_DAYS,
    max_shrink_percentage: float = SCANNER_UNIVERSE_DEFAULT_MAX_SHRINK_PERCENTAGE,
    activated_at: datetime | None = None,
) -> dict[str, Any]:
    lifecycle_store = store or ScannerUniverseLifecycleStore()
    normalized_market = _normalize_market(market)
    now = _normalize_datetime(activated_at)
    dry_run = dry_run_scanner_universe_source(
        source_path=source_path,
        store=lifecycle_store,
        market=normalized_market,
        minimum_coverage_threshold=minimum_coverage_threshold,
        max_age_days=max_age_days,
        max_shrink_percentage=max_shrink_percentage,
        now=now,
    )
    previous = lifecycle_store.load_active(normalized_market)
    previous_version = previous.get("universeVersion") if isinstance(previous, dict) else None
    if dry_run.get("status") != "accepted":
        rejected = _reject_import(
            store=lifecycle_store,
            market=normalized_market,
            source_path=Path(str(source_path)).expanduser(),
            previous_version=previous_version,
            reasons=list(dry_run.get("rejectedReasons") or ["rejected"]),
            now=now,
            normalized_symbols=list(dry_run.get("source", {}).get("normalizedSymbols") or []),
            rejected_symbols=[str(item.get("rawSymbol")) for item in dry_run.get("source", {}).get("rejectedSymbols") or []],
        )
        rejected["diff"] = dry_run.get("diff")
        rejected["source"] = dry_run.get("source")
        return rejected

    source_projection = dict(dry_run.get("source") or {})
    symbols = list(source_projection.get("normalizedSymbols") or [])
    generated_at = _iso_datetime(source_projection.get("retrievedAt") or now.isoformat())
    as_of = str(source_projection.get("sourceAsOf") or generated_at[:10]).strip()
    universe_version = str(dry_run.get("candidateUniverseVersion") or _candidate_universe_version(normalized_market, source_projection, symbols))
    metadata = {
        "contractVersion": SCANNER_UNIVERSE_LIFECYCLE_CONTRACT_VERSION,
        "market": normalized_market,
        "universeVersion": universe_version,
        "generatedAt": generated_at,
        "asOf": as_of,
        "sourceId": source_projection.get("sourceId"),
        "sourceClass": _safe_source_class(source_projection.get("sourceClass")),
        "sourcePolicyState": _source_policy_state(source_projection.get("sourcePolicyState")),
        "sourceArtifactIdentity": source_projection.get("sourceArtifactIdentity"),
        "sourcePath": source_projection.get("sourcePath") or _source_path_label(Path(str(source_path)).expanduser()),
        "symbols": symbols,
        "sourceMemberships": list(source_projection.get("memberships") or []),
        "symbolCount": len(symbols),
        "minimumCoverageThreshold": _coverage_threshold(normalized_market, minimum_coverage_threshold),
        "freshnessState": "fresh",
        "coverageState": "sufficient",
        "blockingReasons": [],
        "diff": dry_run.get("diff"),
        "activatedAt": now.isoformat(),
        "previousUniverseVersion": previous_version,
        "lastSuccessfulActivation": now.isoformat(),
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
        "symbolCount": len(symbols),
        "previousUniverseVersion": previous_version,
        "diff": dry_run.get("diff"),
        "rejectedReasons": [],
        "readOnly": False,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
    }


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
    membership_readiness = {
        "contractVersion": "scanner_universe_membership_readiness_v1",
        "status": "ready" if usable else "blocked",
        "usable": usable,
        "blockingReasons": blocking_reasons,
        "symbolCount": symbol_count,
        "freshnessState": freshness_state,
        "coverageState": coverage_state,
    }
    market_data_readiness = {
        "contractVersion": "scanner_universe_market_data_readiness_v1",
        "status": "not_evaluated",
        "usable": False,
        "blockingReasons": ["market_data_readiness_not_evaluated"],
    }
    candidate_generation_readiness = {
        "contractVersion": "scanner_universe_candidate_generation_readiness_v1",
        "status": "blocked",
        "usable": False,
        "blockingReasons": ["candidate_generation_requires_market_data_readiness"],
    }
    downstream_readiness = build_scanner_universe_downstream_readiness(
        market=normalized_market,
        membership_readiness=membership_readiness,
        market_data_readiness=market_data_readiness,
        candidate_generation_readiness=candidate_generation_readiness,
    )
    payload = {
        "contractVersion": SCANNER_UNIVERSE_LIFECYCLE_CONTRACT_VERSION,
        "market": normalized_market,
        "universeVersion": str(active.get("universeVersion") or ""),
        "generatedAt": active.get("generatedAt"),
        "asOf": active.get("asOf"),
        "sourceId": active.get("sourceId"),
        "sourceClass": _safe_source_class(active.get("sourceClass")),
        "sourcePolicyState": _source_policy_state(active.get("sourcePolicyState")),
        "sourceArtifactIdentity": active.get("sourceArtifactIdentity"),
        "sourcePath": str(active.get("sourcePath") or ""),
        "symbols": list(symbols),
        "sourceMemberships": list(active.get("sourceMemberships") or []),
        "symbolCount": symbol_count,
        "freshnessState": freshness_state,
        "age": {"days": age_days, "maxAgeDays": int(max_age_days)},
        "minimumCoverageThreshold": threshold,
        "coverageState": coverage_state,
        "usable": usable,
        "blockingReasons": blocking_reasons,
        "membershipReadiness": membership_readiness,
        "marketDataReadiness": market_data_readiness,
        "candidateGenerationReadiness": candidate_generation_readiness,
        "versionDiff": active.get("diff"),
        "downstreamReadiness": downstream_readiness,
        "downstreamImpact": downstream_readiness["downstreamImpact"],
        "lastSuccessfulActivation": active.get("activatedAt"),
        "lastRejectedImportReason": _last_rejected_reason(rejected),
        "lastRejectedImport": _public_rejected(rejected),
        "readOnly": True,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
        "consumerSafe": True,
    }
    return payload


def build_scanner_universe_downstream_readiness(
    *,
    market: str,
    membership_readiness: Mapping[str, Any],
    market_data_readiness: Mapping[str, Any],
    candidate_generation_readiness: Mapping[str, Any],
    historical_coverage_state: str = "not_evaluated",
) -> dict[str, Any]:
    normalized_market = _normalize_market(market)
    membership_state = "ready" if bool(membership_readiness.get("usable")) else "blocked"
    market_data_state = str(market_data_readiness.get("status") or "not_evaluated")
    candidate_state = str(candidate_generation_readiness.get("status") or "blocked")
    historical_state = str(historical_coverage_state or "not_evaluated")

    def _base_reasons() -> list[str]:
        if membership_state != "ready":
            return list(membership_readiness.get("blockingReasons") or ["membership_readiness_blocked"])
        return []

    def _consumer(
        *,
        product: str,
        extra_reasons: list[str],
        final_ready: bool = False,
    ) -> dict[str, Any]:
        reasons = _dedupe_texts([*_base_reasons(), *extra_reasons])
        final_state = "ready" if final_ready and not reasons else "blocked"
        return {
            "product": product,
            "membershipState": membership_state,
            "marketDataState": market_data_state,
            "historicalCoverageState": historical_state,
            "candidateGenerationState": candidate_state,
            "finalProductState": final_state,
            "blockingReasons": reasons,
            "readOnly": True,
            "consumerSafe": True,
        }

    market_data_reasons = [] if membership_state != "ready" else _state_reasons(
        market_data_state,
        fallback="market_data_readiness_not_evaluated",
        ready_states={"ready", "available"},
    )
    candidate_reasons = [] if membership_state != "ready" else _state_reasons(
        candidate_state,
        fallback="candidate_generation_requires_market_data_readiness",
        ready_states={"ready", "available"},
    )
    historical_reasons = [] if membership_state != "ready" else _state_reasons(
        historical_state,
        fallback="historical_coverage_not_evaluated",
        ready_states={"ready", "available", "sufficient"},
    )
    consumers = {
        "Scanner": _consumer(
            product="Scanner",
            extra_reasons=[*market_data_reasons, *candidate_reasons],
            final_ready=membership_state == "ready" and not market_data_reasons and not candidate_reasons,
        ),
        "Research Radar": _consumer(
            product="Research Radar",
            extra_reasons=[
                *candidate_reasons,
                *(["scanner_candidates_unavailable"] if membership_state == "ready" else []),
            ],
            final_ready=membership_state == "ready" and not candidate_reasons,
        ),
        "Backtest preparation": _consumer(
            product="Backtest preparation",
            extra_reasons=historical_reasons,
            final_ready=membership_state == "ready" and not historical_reasons,
        ),
        "Market Overview": _consumer(
            product="Market Overview",
            extra_reasons=market_data_reasons,
            final_ready=membership_state == "ready" and not market_data_reasons,
        ),
    }
    blocked_products = [
        product
        for product in SCANNER_UNIVERSE_BLOCKED_PRODUCTS
        if consumers["Backtest preparation" if product == "Backtest" else product]["finalProductState"] != "ready"
    ]
    blocking_reasons: list[str] = []
    for product in blocked_products:
        key = "Backtest preparation" if product == "Backtest" else product
        blocking_reasons.extend(consumers[key]["blockingReasons"])
    return {
        "contractVersion": SCANNER_UNIVERSE_DOWNSTREAM_READINESS_VERSION,
        "market": normalized_market,
        "consumers": consumers,
        "downstreamImpact": {
            "contractVersion": "scanner_universe_downstream_impact_v1",
            "blockedProducts": blocked_products,
            "blockingReasons": _dedupe_texts(blocking_reasons),
            "readOnly": True,
            "consumerSafe": True,
        },
        "readOnly": True,
        "consumerSafe": True,
    }


def build_scanner_universe_current_state_matrix(
    *,
    store: ScannerUniverseLifecycleStore | None = None,
    markets: Iterable[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    lifecycle_store = store or ScannerUniverseLifecycleStore()
    rows: list[dict[str, Any]] = []
    for market in markets or SCANNER_UNIVERSE_MARKETS:
        readiness = build_scanner_universe_lifecycle_readiness(
            store=lifecycle_store,
            market=str(market),
            now=now,
        )
        rows.append(
            {
                "market": readiness["market"],
                "activeLifecycleVersion": readiness.get("universeVersion"),
                "activeSourceIdentity": readiness.get("sourceArtifactIdentity") or readiness.get("sourceId"),
                "policyState": readiness.get("sourcePolicyState"),
                "symbolCount": readiness.get("symbolCount"),
                "freshness": readiness.get("freshnessState"),
                "coverage": readiness.get("coverageState"),
                "usable": readiness.get("usable"),
                "blockers": list(readiness.get("blockingReasons") or []),
                "membershipReadiness": readiness.get("membershipReadiness"),
                "marketDataReadiness": readiness.get("marketDataReadiness"),
                "candidateGenerationReadiness": readiness.get("candidateGenerationReadiness"),
                "downstreamReadiness": readiness.get("downstreamReadiness"),
                "readOnly": True,
            }
        )
    return {
        "contractVersion": SCANNER_UNIVERSE_CURRENT_STATE_MATRIX_VERSION,
        "rows": rows,
        "readOnly": True,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
    }


def discover_scanner_universe_source_artifacts(
    *,
    repo_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    markets: Iterable[str] | None = None,
) -> dict[str, Any]:
    root = _repo_root(repo_root)
    source_env = os.environ if env is None else env
    requested_markets = {_normalize_market(market) for market in (markets or SCANNER_UNIVERSE_MARKETS)}
    candidates: list[dict[str, Any]] = []

    stock_index = root / "apps" / "dsa-web" / "public" / "stocks.index.json"
    if "CN" in requested_markets:
        projection = read_scanner_universe_source_file(stock_index, market="CN")
        candidates.append(
            _source_candidate_from_projection(
                projection=projection,
                artifact_path=_relative_path(stock_index, root),
                source_class="repository_local_frontend_stock_index",
                source_usage="frontend autocomplete/search stock index",
                licensing_uncertainty=True,
                network_required=False,
                credentials_required=False,
                extra_blocking_reasons=["source_policy_unknown"],
            )
        )

    for market in requested_markets:
        candidates.append(_stock_mapping_candidate(market=market, repo_root=root))

    scanner_cache = Path(str(source_env.get("SCANNER_LOCAL_UNIVERSE_PATH") or "./data/scanner_cn_universe_cache.csv")).expanduser()
    if not scanner_cache.is_absolute():
        scanner_cache = root / scanner_cache
    if "CN" in requested_markets:
        candidates.append(
            _path_inventory_candidate(
                market="CN",
                source_id="operator:scanner_local_universe_cache",
                artifact_path=_relative_path(scanner_cache, root),
                interface="SCANNER_LOCAL_UNIVERSE_PATH",
                source_class="repository_local_csv",
                policy_state="operator_supplied",
                source_as_of=_path_date(scanner_cache),
                symbol_count=_count_csv_symbols(scanner_cache),
                network_required=False,
                credentials_required=False,
                licensing_uncertainty=False,
                current_product_usage="current Scanner CN resolver first input",
                source_exists=scanner_cache.exists(),
                missing_reason="source_missing",
            )
        )

    parquet_dir = _configured_path(source_env, ("LOCAL_US_PARQUET_DIR", "US_STOCK_PARQUET_DIR"), root=root)
    if "US" in requested_markets:
        candidates.append(
            _path_inventory_candidate(
                market="US",
                source_id="operator:local_us_parquet_dir",
                artifact_path=_relative_path(parquet_dir, root) if parquet_dir else "LOCAL_US_PARQUET_DIR",
                interface="LOCAL_US_PARQUET_DIR or US_STOCK_PARQUET_DIR",
                source_class="local_parquet_symbol_inventory",
                policy_state="operator_supplied",
                source_as_of=_path_date(parquet_dir) if parquet_dir else None,
                symbol_count=_count_parquet_symbols(parquet_dir) if parquet_dir else 0,
                network_required=False,
                credentials_required=False,
                licensing_uncertainty=False,
                current_product_usage="current Scanner US resolver local history inventory",
                source_exists=bool(parquet_dir and parquet_dir.exists()),
                missing_reason="not_configured" if parquet_dir is None else "source_missing",
            )
        )

    db_path = _configured_path(source_env, ("DATABASE_PATH",), root=root) or (root / "data" / "stock_analysis.db")
    for market in requested_markets:
        candidates.append(
            _path_inventory_candidate(
                market=market,
                source_id=f"operator:local_db_history:{market}",
                artifact_path=_relative_path(db_path, root),
                interface="DATABASE_PATH stock_daily/analysis rows",
                source_class="database_backed_symbol_inventory",
                policy_state="operator_supplied",
                source_as_of=_path_date(db_path),
                symbol_count=0,
                network_required=False,
                credentials_required=False,
                licensing_uncertainty=False,
                current_product_usage="current Scanner fallback historical symbol inventory",
                source_exists=db_path.exists(),
                missing_reason="source_missing",
                extra_blocking_reasons=["database_symbol_count_not_evaluated"],
            )
        )
        candidates.append(
            {
                "market": market,
                "sourceId": f"operator:explicit_source_contract:{market}",
                "artifactPath": "operator-supplied JSON path",
                "interface": "scripts/scanner_universe_lifecycle_import.py --source <json>",
                "sourceClass": "operator_supplied_source_contract",
                "sourcePolicyState": "unknown_policy",
                "sourceAsOf": None,
                "symbolCount": 0,
                "rawSymbolCount": 0,
                "networkRequired": False,
                "credentialsRequired": False,
                "licensingUncertainty": False,
                "currentProductUsage": "explicit operator qualification/import workflow",
                "eligibleForActivation": False,
                "reason": "operator_artifact_required",
                "blockingReasons": ["source_missing"],
                "sourceExists": False,
                "readOnly": True,
                "noExternalCalls": True,
                "providerCallsEnabled": False,
            }
        )

    return {
        "contractVersion": SCANNER_UNIVERSE_SOURCE_DISCOVERY_VERSION,
        "candidates": candidates,
        "readOnly": True,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
    }


def build_scanner_universe_activation_qualification_pack(
    *,
    market: str,
    source_path: str | Path | None = None,
    store: ScannerUniverseLifecycleStore | None = None,
    repo_root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    minimum_coverage_threshold: int | None = None,
    max_age_days: int = SCANNER_UNIVERSE_DEFAULT_MAX_AGE_DAYS,
    max_shrink_percentage: float = SCANNER_UNIVERSE_DEFAULT_MAX_SHRINK_PERCENTAGE,
    now: datetime | None = None,
    attempt_activation: bool = False,
) -> dict[str, Any]:
    lifecycle_store = store or ScannerUniverseLifecycleStore()
    normalized_market = _normalize_market(market)
    current_time = _normalize_datetime(now)
    root = _repo_root(repo_root)
    current_state = build_scanner_universe_current_state_matrix(
        store=lifecycle_store,
        markets=SCANNER_UNIVERSE_MARKETS,
        now=current_time,
    )
    discovery = discover_scanner_universe_source_artifacts(
        repo_root=root,
        env=env,
        markets=SCANNER_UNIVERSE_MARKETS,
    )
    selected_path: Path | None = Path(str(source_path)).expanduser() if source_path is not None else None
    selected_projection: dict[str, Any] | None = None
    selected_candidate: dict[str, Any] | None = None
    if selected_path is not None:
        selected_projection = read_scanner_universe_source_file(selected_path, market=normalized_market)
        selected_candidate = _source_candidate_from_projection(
            projection=selected_projection,
            artifact_path=_source_path_label(selected_path),
            source_class=str(selected_projection.get("sourceClass") or "explicit_local_source"),
            source_usage="explicit operator supplied source artifact",
            licensing_uncertainty=False,
            network_required=False,
            credentials_required=False,
        )
    else:
        selected_candidate = _select_activation_candidate(discovery["candidates"], market=normalized_market)
        if selected_candidate and selected_candidate.get("artifactPath") == "apps/dsa-web/public/stocks.index.json":
            selected_path = root / "apps" / "dsa-web" / "public" / "stocks.index.json"
            selected_projection = read_scanner_universe_source_file(selected_path, market=normalized_market)

    decision = _build_activation_decision(
        market=normalized_market,
        candidate=selected_candidate,
        projection=selected_projection,
        minimum_coverage_threshold=minimum_coverage_threshold,
        now=current_time,
        max_age_days=max_age_days,
    )
    before_active = lifecycle_store.load_active(normalized_market)
    before_version = before_active.get("universeVersion") if isinstance(before_active, dict) else None
    dry_run: dict[str, Any] | None = None
    dry_run_proof = _empty_dry_run_proof(market=normalized_market, before_version=before_version)
    if selected_path is not None:
        dry_run = dry_run_scanner_universe_source(
            source_path=selected_path,
            store=lifecycle_store,
            market=normalized_market,
            minimum_coverage_threshold=minimum_coverage_threshold,
            max_age_days=max_age_days,
            max_shrink_percentage=max_shrink_percentage,
            now=current_time,
        )
        after_dry_run = lifecycle_store.load_active(normalized_market)
        after_dry_version = after_dry_run.get("universeVersion") if isinstance(after_dry_run, dict) else None
        dry_run_proof = _dry_run_proof(
            dry_run=dry_run,
            before_version=before_version,
            after_version=after_dry_version,
        )

    activation_proof = _activation_not_requested(market=normalized_market, before_version=before_version)
    if attempt_activation and selected_path is not None:
        activation_result = activate_scanner_universe_from_source(
            source_path=selected_path,
            store=lifecycle_store,
            market=normalized_market,
            minimum_coverage_threshold=minimum_coverage_threshold,
            max_age_days=max_age_days,
            max_shrink_percentage=max_shrink_percentage,
            activated_at=current_time,
        )
        activation_proof = _activation_proof(
            store=lifecycle_store,
            market=normalized_market,
            before_version=before_version,
            activation_result=activation_result,
            dry_run=dry_run,
            source_path=selected_path,
            minimum_coverage_threshold=minimum_coverage_threshold,
            max_age_days=max_age_days,
            max_shrink_percentage=max_shrink_percentage,
            now=current_time,
        )

    active_readiness = build_scanner_universe_lifecycle_readiness(
        store=lifecycle_store,
        market=normalized_market,
        minimum_coverage_threshold=minimum_coverage_threshold,
        now=current_time,
    )
    coverage = _build_coverage_proof(
        market=normalized_market,
        dry_run=dry_run,
        discovery=discovery,
        decision=decision,
        readiness=active_readiness,
        minimum_coverage_threshold=minimum_coverage_threshold,
    )
    operator_pack = _operator_activation_pack(
        market=normalized_market,
        source_path=selected_path,
        decision=decision,
        minimum_coverage_threshold=minimum_coverage_threshold,
    )
    safety = _production_safety_proof(
        dry_run_proof=dry_run_proof,
        attempt_activation=attempt_activation,
        decision=decision,
    )
    return {
        "contractVersion": SCANNER_UNIVERSE_QUALIFICATION_PACK_VERSION,
        "status": decision["status"],
        "generatedAt": current_time.isoformat(),
        "market": normalized_market,
        "currentUniverseStateMatrix": current_state,
        "sourceArtifactDiscoveryMatrix": discovery,
        "activationQualificationDecision": decision,
        "realDryRunProof": dry_run_proof,
        "realActivationProof": activation_proof,
        "coverageProof": coverage,
        "downstreamReadinessSeparation": active_readiness.get("downstreamReadiness"),
        "operatorActivationPack": operator_pack,
        "productionSafetyProof": safety,
        "readOnly": not bool(attempt_activation),
        "noExternalCalls": True,
        "providerCallsEnabled": False,
        "scannerRefreshExecuted": False,
        "runtimeBehaviorChanged": False,
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


def _source_candidate_from_projection(
    *,
    projection: Mapping[str, Any],
    artifact_path: str,
    source_class: str,
    source_usage: str,
    licensing_uncertainty: bool,
    network_required: bool,
    credentials_required: bool,
    extra_blocking_reasons: list[str] | None = None,
) -> dict[str, Any]:
    policy_state = _source_policy_state(projection.get("sourcePolicyState"))
    blockers = _dedupe_texts(
        [
            *list(projection.get("blockingReasons") or []),
            *(extra_blocking_reasons or []),
        ]
    )
    if policy_state == "unknown_policy":
        blockers.append("source_policy_unknown")
    elif policy_state == "rejected":
        blockers.append("source_policy_rejected")
    if int(projection.get("symbolCount") or 0) <= 0:
        blockers.append("empty_universe")
    if not _safe_text(projection.get("sourceAsOf")):
        blockers.append("source_as_of_missing")
    if not _safe_text(projection.get("sourceArtifactIdentity")):
        blockers.append("source_artifact_identity_missing")
    blockers = _dedupe_texts(blockers)
    eligible = not blockers and policy_state in SCANNER_UNIVERSE_APPROVED_POLICY_STATES
    return {
        "market": _normalize_market(projection.get("market")),
        "sourceId": projection.get("sourceId"),
        "artifactPath": artifact_path,
        "interface": "read_scanner_universe_source_file",
        "sourceClass": source_class,
        "sourcePolicyState": policy_state,
        "sourceAsOf": projection.get("sourceAsOf") or None,
        "sourceArtifactIdentity": projection.get("sourceArtifactIdentity"),
        "symbolCount": int(projection.get("symbolCount") or 0),
        "rawSymbolCount": int(projection.get("rawSymbolCount") or 0),
        "networkRequired": bool(network_required),
        "credentialsRequired": bool(credentials_required),
        "licensingUncertainty": bool(licensing_uncertainty),
        "currentProductUsage": source_usage,
        "eligibleForActivation": eligible,
        "reason": "eligible" if eligible else blockers[0] if blockers else "not_eligible",
        "blockingReasons": blockers,
        "sourceExists": int(projection.get("rawSymbolCount") or projection.get("symbolCount") or 0) > 0,
        "dryRunEligible": int(projection.get("symbolCount") or 0) > 0,
        "readOnly": True,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
    }


def _path_inventory_candidate(
    *,
    market: str,
    source_id: str,
    artifact_path: str,
    interface: str,
    source_class: str,
    policy_state: str,
    source_as_of: str | None,
    symbol_count: int,
    network_required: bool,
    credentials_required: bool,
    licensing_uncertainty: bool,
    current_product_usage: str,
    source_exists: bool,
    missing_reason: str,
    extra_blocking_reasons: list[str] | None = None,
) -> dict[str, Any]:
    blockers = list(extra_blocking_reasons or [])
    if not source_exists:
        blockers.append(missing_reason)
    if int(symbol_count or 0) <= 0:
        blockers.append("empty_universe")
    if not source_as_of:
        blockers.append("source_as_of_missing")
    blockers.append("operator_source_contract_required")
    blockers = _dedupe_texts(blockers)
    return {
        "market": _normalize_market(market),
        "sourceId": source_id,
        "artifactPath": artifact_path,
        "interface": interface,
        "sourceClass": source_class,
        "sourcePolicyState": _source_policy_state(policy_state),
        "sourceAsOf": source_as_of,
        "symbolCount": max(0, int(symbol_count or 0)),
        "rawSymbolCount": max(0, int(symbol_count or 0)),
        "networkRequired": bool(network_required),
        "credentialsRequired": bool(credentials_required),
        "licensingUncertainty": bool(licensing_uncertainty),
        "currentProductUsage": current_product_usage,
        "eligibleForActivation": False,
        "reason": blockers[0] if blockers else "operator_source_contract_required",
        "blockingReasons": blockers,
        "sourceExists": bool(source_exists),
        "dryRunEligible": False,
        "readOnly": True,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
    }


def _stock_mapping_candidate(*, market: str, repo_root: Path) -> dict[str, Any]:
    from src.data.stock_mapping import STOCK_NAME_MAP

    normalized_market = _normalize_market(market)
    symbols, rejected = _normalize_symbols(STOCK_NAME_MAP.keys(), market=normalized_market)
    blockers = ["source_policy_unknown", "source_as_of_missing"]
    if not symbols:
        blockers.append("empty_universe")
    return {
        "market": normalized_market,
        "sourceId": f"repo:stock_mapping:{normalized_market}",
        "artifactPath": _relative_path(repo_root / "src" / "data" / "stock_mapping.py", repo_root),
        "interface": "src.data.stock_mapping.STOCK_NAME_MAP",
        "sourceClass": "repository_local_symbol_mapping",
        "sourcePolicyState": "unknown_policy",
        "sourceAsOf": None,
        "symbolCount": len(symbols),
        "rawSymbolCount": len(STOCK_NAME_MAP),
        "networkRequired": False,
        "credentialsRequired": False,
        "licensingUncertainty": True,
        "currentProductUsage": "name lookup and legacy Scanner fallback mapping",
        "eligibleForActivation": False,
        "reason": blockers[0],
        "blockingReasons": blockers,
        "sourceExists": True,
        "dryRunEligible": False,
        "rejectedSymbolCount": len(rejected),
        "readOnly": True,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
    }


def _select_activation_candidate(candidates: list[dict[str, Any]], *, market: str) -> dict[str, Any] | None:
    market_candidates = [item for item in candidates if _normalize_market(item.get("market")) == market]
    if not market_candidates:
        return None
    return sorted(
        market_candidates,
        key=lambda item: (
            bool(item.get("eligibleForActivation")),
            bool(item.get("dryRunEligible")),
            bool(item.get("sourceExists")),
            int(item.get("symbolCount") or 0),
            not bool(item.get("networkRequired")),
        ),
        reverse=True,
    )[0]


def _build_activation_decision(
    *,
    market: str,
    candidate: Mapping[str, Any] | None,
    projection: Mapping[str, Any] | None,
    minimum_coverage_threshold: int | None,
    now: datetime,
    max_age_days: int,
) -> dict[str, Any]:
    threshold = _coverage_threshold(market, minimum_coverage_threshold)
    if not candidate:
        return {
            "contractVersion": SCANNER_UNIVERSE_QUALIFICATION_DECISION_VERSION,
            "market": market,
            "status": "blocked_source_missing",
            "activationEligible": False,
            "dryRunEligible": False,
            "selectedSourceId": None,
            "sourceClass": None,
            "sourcePolicyState": None,
            "symbolCount": 0,
            "minimumCoverageThreshold": threshold,
            "blockingReasons": ["source_missing"],
            "operatorRequiredArtifact": "scanner_universe_source_membership_v1 JSON with sourcePolicyState and sourceAsOf",
            "readOnly": True,
        }
    reasons = _dedupe_texts(list(candidate.get("blockingReasons") or []))
    symbol_count = int(candidate.get("symbolCount") or 0)
    if symbol_count and symbol_count < threshold:
        reasons.append("below_minimum_coverage")
    if projection:
        diff = _build_universe_diff(
            previous_symbols=[],
            candidate_symbols=list(projection.get("normalizedSymbols") or []),
            normalized_change_count=int(projection.get("normalizedChangeCount") or 0),
            rejected_count=len(projection.get("rejectedSymbols") or []),
        )
        reasons = _dedupe_texts(
            [
                *reasons,
                *_qualification_reasons(
                    projection=projection,
                    symbol_count=int(projection.get("symbolCount") or 0),
                    threshold=threshold,
                    now=now,
                    max_age_days=max_age_days,
                    max_shrink_percentage=SCANNER_UNIVERSE_DEFAULT_MAX_SHRINK_PERCENTAGE,
                    diff=diff,
                    previous_symbols=[],
                ),
            ]
        )
    policy_state = _source_policy_state(candidate.get("sourcePolicyState"))
    activation_eligible = not reasons and policy_state in SCANNER_UNIVERSE_APPROVED_POLICY_STATES
    if activation_eligible:
        status = "qualified_for_activation"
    elif "source_policy_unknown" in reasons:
        status = "blocked_policy_unknown"
    elif "stale_source" in reasons:
        status = "blocked_stale"
    elif "below_minimum_coverage" in reasons:
        status = "blocked_coverage"
    elif "metadata_malformed" in reasons or "source_missing_or_malformed" in reasons:
        status = "blocked_malformed"
    elif not bool(candidate.get("sourceExists")):
        status = "blocked_source_missing"
    else:
        status = "qualified_for_dry_run_only" if bool(candidate.get("dryRunEligible")) else "blocked_source_missing"
    return {
        "contractVersion": SCANNER_UNIVERSE_QUALIFICATION_DECISION_VERSION,
        "market": market,
        "status": status,
        "activationEligible": activation_eligible,
        "dryRunEligible": bool(candidate.get("dryRunEligible")) or bool(projection),
        "selectedSourceId": candidate.get("sourceId"),
        "sourceClass": candidate.get("sourceClass"),
        "sourcePolicyState": policy_state,
        "symbolCount": symbol_count,
        "minimumCoverageThreshold": threshold,
        "blockingReasons": reasons,
        "operatorRequiredArtifact": None if activation_eligible else "explicit approved/operator_supplied source artifact with sourceAsOf and sufficient coverage",
        "readOnly": True,
    }


def _empty_dry_run_proof(*, market: str, before_version: Any) -> dict[str, Any]:
    return {
        "contractVersion": "scanner_universe_real_dry_run_proof_v1",
        "status": "not_available",
        "market": market,
        "beforeActiveVersion": before_version,
        "afterActiveVersion": before_version,
        "activeVersionChanged": False,
        "blockingReasons": ["source_missing"],
        "readOnly": True,
    }


def _dry_run_proof(*, dry_run: Mapping[str, Any], before_version: Any, after_version: Any) -> dict[str, Any]:
    source = dry_run.get("source") if isinstance(dry_run.get("source"), Mapping) else {}
    diff = dry_run.get("diff") if isinstance(dry_run.get("diff"), Mapping) else {}
    return {
        "contractVersion": "scanner_universe_real_dry_run_proof_v1",
        "status": dry_run.get("status"),
        "market": dry_run.get("market"),
        "sourceArtifactIdentity": source.get("sourceArtifactIdentity"),
        "sourcePolicyState": source.get("sourcePolicyState"),
        "sourceAsOf": source.get("sourceAsOf"),
        "rawCount": int(dry_run.get("rawSymbolCount") or 0),
        "normalizedCount": int(dry_run.get("normalizedSymbolCount") or dry_run.get("symbolCount") or 0),
        "duplicateCount": int(dry_run.get("duplicateSymbolCount") or 0),
        "rejectedCount": int(dry_run.get("rejectedSymbolCount") or 0),
        "normalizationRejectionRate": float(dry_run.get("normalizationRejectionRate") or 0.0),
        "addedCount": int(diff.get("addedCount") or 0),
        "removedCount": int(diff.get("removedCount") or 0),
        "unchangedCount": int(diff.get("unchangedCount") or 0),
        "coverageDelta": int(diff.get("coverageDelta") or 0),
        "shrinkPercentage": float(diff.get("shrinkPercentage") or 0.0),
        "growthPercentage": float(diff.get("growthPercentage") or 0.0),
        "freshnessState": dry_run.get("freshnessState"),
        "coverageState": dry_run.get("coverageState"),
        "activationEligibility": bool(dry_run.get("activationReady")),
        "candidateUniverseVersion": dry_run.get("candidateUniverseVersion"),
        "blockingReasons": list(dry_run.get("blockingReasons") or []),
        "beforeActiveVersion": before_version,
        "afterActiveVersion": after_version,
        "activeVersionChanged": before_version != after_version,
        "readOnly": True,
        "mutationEnabled": False,
    }


def _activation_not_requested(*, market: str, before_version: Any) -> dict[str, Any]:
    return {
        "contractVersion": "scanner_universe_real_activation_proof_v1",
        "status": "not_requested",
        "market": market,
        "beforeActiveVersion": before_version,
        "afterActiveVersion": before_version,
        "blockingReasons": ["explicit_activation_not_requested"],
        "mutationEnabled": False,
    }


def _activation_proof(
    *,
    store: ScannerUniverseLifecycleStore,
    market: str,
    before_version: Any,
    activation_result: Mapping[str, Any],
    dry_run: Mapping[str, Any] | None,
    source_path: Path,
    minimum_coverage_threshold: int | None,
    max_age_days: int,
    max_shrink_percentage: float,
    now: datetime,
) -> dict[str, Any]:
    after = build_scanner_universe_lifecycle_readiness(
        store=store,
        market=market,
        minimum_coverage_threshold=minimum_coverage_threshold,
        now=now,
    )
    after_version = after.get("universeVersion")
    determinism = dry_run_scanner_universe_source(
        source_path=source_path,
        store=store,
        market=market,
        minimum_coverage_threshold=minimum_coverage_threshold,
        max_age_days=max_age_days,
        max_shrink_percentage=max_shrink_percentage,
        now=now,
    )
    return {
        "contractVersion": "scanner_universe_real_activation_proof_v1",
        "status": activation_result.get("status"),
        "market": market,
        "beforeActiveVersion": before_version,
        "candidateVersion": (dry_run or {}).get("candidateUniverseVersion"),
        "activatedVersion": activation_result.get("universeVersion") if activation_result.get("status") == "activated" else None,
        "afterActiveVersion": after_version,
        "activeSourceIdentity": after.get("sourceArtifactIdentity"),
        "activePolicyState": after.get("sourcePolicyState"),
        "activeSymbolCount": after.get("symbolCount"),
        "freshness": after.get("freshnessState"),
        "coverage": after.get("coverageState"),
        "membershipUsable": bool(after.get("membershipReadiness", {}).get("usable")),
        "lastSuccessfulActivation": after.get("lastSuccessfulActivation"),
        "blockingReasons": list(activation_result.get("rejectedReasons") or after.get("blockingReasons") or []),
        "versionDeterminism": {
            "sameSourceSameVersion": determinism.get("candidateUniverseVersion") == (dry_run or {}).get("candidateUniverseVersion"),
            "requalifiedCandidateUniverseVersion": determinism.get("candidateUniverseVersion"),
        },
        "lastGoodPreserved": activation_result.get("status") != "activated" and before_version == after_version,
        "mutationEnabled": activation_result.get("status") == "activated",
        "noExternalCalls": True,
        "providerCallsEnabled": False,
    }


def _build_coverage_proof(
    *,
    market: str,
    dry_run: Mapping[str, Any] | None,
    discovery: Mapping[str, Any],
    decision: Mapping[str, Any],
    readiness: Mapping[str, Any],
    minimum_coverage_threshold: int | None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    candidates = list(discovery.get("candidates") or [])
    for row_market in SCANNER_UNIVERSE_MARKETS:
        threshold = _coverage_threshold(row_market, minimum_coverage_threshold if row_market == market else None)
        candidate = _select_activation_candidate(candidates, market=row_market)
        is_selected = row_market == market and dry_run is not None
        candidate_count = int((dry_run or {}).get("symbolCount") or 0) if is_selected else int((candidate or {}).get("symbolCount") or 0)
        rejected_count = int((dry_run or {}).get("rejectedSymbolCount") or 0) if is_selected else int((candidate or {}).get("rejectedSymbolCount") or 0)
        raw_count = int((dry_run or {}).get("rawSymbolCount") or 0) if is_selected else int((candidate or {}).get("rawSymbolCount") or 0)
        policy = str(decision.get("status")) if is_selected else (
            "blocked_policy_unknown"
            if candidate and "source_policy_unknown" in list(candidate.get("blockingReasons") or [])
            else "blocked_source_missing"
            if not candidate or not candidate.get("sourceExists")
            else "qualified_for_dry_run_only"
        )
        rows.append(
            {
                "market": row_market,
                "candidateSymbolCount": candidate_count,
                "minimumThreshold": threshold,
                "thresholdSource": "operator_override" if row_market == market and minimum_coverage_threshold is not None else "default_contract",
                "coverageState": "sufficient" if candidate_count >= threshold and candidate_count > 0 else "insufficient",
                "freshnessState": str((dry_run or {}).get("freshnessState") or ("missing" if not (candidate or {}).get("sourceAsOf") else "unknown")),
                "normalizationRejectionRate": _rejection_rate(rejected_count, raw_count),
                "policyQualification": policy,
                "membershipUsability": (
                    "ready"
                    if row_market == market and bool(readiness.get("membershipReadiness", {}).get("usable"))
                    else "blocked"
                ),
                "readOnly": True,
            }
        )
    return {
        "contractVersion": SCANNER_UNIVERSE_COVERAGE_PROOF_VERSION,
        "rows": rows,
        "readOnly": True,
        "thresholdsAreContractDefaults": minimum_coverage_threshold is None,
    }


def _operator_activation_pack(
    *,
    market: str,
    source_path: Path | None,
    decision: Mapping[str, Any],
    minimum_coverage_threshold: int | None,
) -> dict[str, Any]:
    source_label = _source_path_label(source_path) if source_path is not None else "<operator-source.json>"
    threshold_arg = (
        f" --minimum-coverage-threshold {int(minimum_coverage_threshold)}"
        if minimum_coverage_threshold is not None
        else ""
    )
    base = f"python scripts/scanner_universe_lifecycle_import.py --source {source_label} --market {market.lower()} --root <isolated-or-approved-lifecycle-root>{threshold_arg}"
    return {
        "contractVersion": "scanner_universe_operator_activation_pack_v1",
        "sourceId": decision.get("selectedSourceId"),
        "sourcePolicyState": decision.get("sourcePolicyState"),
        "sourceClass": decision.get("sourceClass"),
        "status": decision.get("status"),
        "humanSummary": (
            "Source qualifies for explicit isolated activation."
            if decision.get("status") == "qualified_for_activation"
            else "Source is not activation-qualified; use dry-run output to resolve policy/source blockers."
        ),
        "explicitDryRunCommand": f"{base} --dry-run",
        "explicitActivationCommand": f"{base} --activate",
        "implicitStartupActivation": False,
        "secretsExposed": False,
        "readOnly": True,
    }


def _production_safety_proof(
    *,
    dry_run_proof: Mapping[str, Any],
    attempt_activation: bool,
    decision: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "contractVersion": "scanner_universe_production_safety_proof_v1",
        "pageReadsActivateUniverse": False,
        "scannerPageLoadMutatesUniverse": False,
        "startupAutoActivationEnabled": False,
        "failedImportPreservesLastGood": True,
        "policyUnknownCannotSilentlyActivate": decision.get("status") != "qualified_for_activation" or not attempt_activation,
        "suspiciousShrinkCannotSilentlyActivate": True,
        "dryRunNeverWritesActiveState": not bool(dry_run_proof.get("activeVersionChanged")),
        "explicitActivationRequired": True,
        "providerDispatchChanged": False,
        "uatProviderIsolationPreserved": True,
        "readOnly": not bool(attempt_activation),
    }


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
    freshness_state = "missing" if "source_missing" in reasons else "malformed"
    membership_readiness = {
        "contractVersion": "scanner_universe_membership_readiness_v1",
        "status": "blocked",
        "usable": False,
        "blockingReasons": reasons,
        "symbolCount": 0,
        "freshnessState": freshness_state,
        "coverageState": "insufficient",
    }
    market_data_readiness = {
        "contractVersion": "scanner_universe_market_data_readiness_v1",
        "status": "not_evaluated",
        "usable": False,
        "blockingReasons": ["membership_readiness_blocked"],
    }
    candidate_generation_readiness = {
        "contractVersion": "scanner_universe_candidate_generation_readiness_v1",
        "status": "blocked",
        "usable": False,
        "blockingReasons": ["membership_readiness_blocked"],
    }
    downstream_readiness = build_scanner_universe_downstream_readiness(
        market=market,
        membership_readiness=membership_readiness,
        market_data_readiness=market_data_readiness,
        candidate_generation_readiness=candidate_generation_readiness,
    )
    return {
        "contractVersion": SCANNER_UNIVERSE_LIFECYCLE_CONTRACT_VERSION,
        "market": market,
        "universeVersion": None,
        "generatedAt": None,
        "asOf": None,
        "sourceClass": None,
        "sourceId": None,
        "sourcePolicyState": None,
        "sourceArtifactIdentity": None,
        "sourcePath": None,
        "symbols": [],
        "sourceMemberships": [],
        "symbolCount": 0,
        "freshnessState": freshness_state,
        "age": {"days": None, "maxAgeDays": SCANNER_UNIVERSE_DEFAULT_MAX_AGE_DAYS},
        "minimumCoverageThreshold": threshold,
        "coverageState": "insufficient",
        "usable": False,
        "blockingReasons": reasons,
        "membershipReadiness": membership_readiness,
        "marketDataReadiness": market_data_readiness,
        "candidateGenerationReadiness": candidate_generation_readiness,
        "versionDiff": None,
        "downstreamReadiness": downstream_readiness,
        "downstreamImpact": downstream_readiness["downstreamImpact"],
        "lastSuccessfulActivation": None,
        "lastRejectedImportReason": _last_rejected_reason(last_rejected),
        "lastRejectedImport": _public_rejected(last_rejected),
        "readOnly": True,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
        "consumerSafe": True,
    }


def _source_inventory_record(
    *,
    source_name: str,
    owner_module: str,
    source_class: str,
    network_or_local: str,
    authentication_requirement: str,
    commercial_licensing_uncertainty: bool,
    available_metadata: list[str],
    normalization_requirement: str,
    freshness_characteristics: str,
    current_product_usage: str,
    suitability: str,
    related_sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    policy_state = suitability if suitability in {"approved", "operator_supplied", "rejected"} else "unknown_policy"
    if suitability == "blocked_until_policy_approved":
        policy_state = "unknown_policy"
    return {
        "sourceName": source_name,
        "ownerModule": owner_module,
        "sourceClass": source_class,
        "networkOrLocal": network_or_local,
        "authenticationRequirement": authentication_requirement,
        "commercialLicensingUncertainty": bool(commercial_licensing_uncertainty),
        "availableMetadata": list(available_metadata),
        "normalizationRequirement": normalization_requirement,
        "freshnessCharacteristics": freshness_characteristics,
        "currentProductUsage": current_product_usage,
        "sourcePolicyState": policy_state,
        "suitabilityForUniverseMembership": suitability,
        "relatedSources": list(related_sources or []),
    }


def _source_projection_blocked(
    *,
    market: str,
    source_path: Path,
    reasons: list[str],
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source_id = _safe_text((payload or {}).get("sourceId")) or f"{market.lower()}:{_source_path_label(source_path)}"
    return {
        "contractVersion": SCANNER_UNIVERSE_SOURCE_CONTRACT_VERSION,
        "market": market,
        "sourceId": source_id,
        "sourceClass": _safe_source_class((payload or {}).get("sourceClass")),
        "sourceAsOf": _safe_text((payload or {}).get("sourceAsOf") or (payload or {}).get("asOf")),
        "retrievedAt": _safe_text((payload or {}).get("retrievedAt") or (payload or {}).get("importedAt") or (payload or {}).get("generatedAt")),
        "importedAt": _safe_text((payload or {}).get("importedAt")),
        "sourceArtifactIdentity": _safe_text((payload or {}).get("sourceArtifactIdentity")) or _artifact_identity(source_path, payload or {}),
        "sourcePath": _source_path_label(source_path),
        "symbolCount": 0,
        "rawSymbolCount": 0,
        "normalizedSymbols": [],
        "memberships": [],
        "rejectedSymbols": [],
        "duplicateSymbolCount": 0,
        "normalizedChangeCount": 0,
        "sourcePolicyState": _source_policy_state((payload or {}).get("sourcePolicyState")),
        "blockingReasons": list(dict.fromkeys(reasons)),
        "readOnly": True,
        "noExternalCalls": True,
        "providerCallsEnabled": False,
    }


def _extract_source_symbol_record(item: Any) -> tuple[str, str | None, str | None, str | None]:
    if isinstance(item, Mapping):
        raw = _safe_text(
            item.get("rawSymbol")
            or item.get("symbol")
            or item.get("ticker")
            or item.get("code")
        )
        return (
            raw,
            _safe_text(item.get("exchange")) or None,
            _safe_text(item.get("securityType") or item.get("security_type")) or None,
            _safe_text(item.get("listingStatus") or item.get("listing_status")) or None,
        )
    return _safe_text(item), None, None, None


def _extract_frontend_stock_index_record(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, list) or len(row) < 8:
        return None
    canonical = _safe_text(row[0])
    display = _safe_text(row[1])
    market = _safe_text(row[6]).upper()
    asset_type = _safe_text(row[7]).lower()
    if not canonical and not display:
        return None
    if market not in set(SCANNER_UNIVERSE_MARKETS):
        return None
    if asset_type != "stock":
        return None
    exchange = canonical.split(".")[-1].upper() if "." in canonical else None
    return {
        "canonicalCode": canonical,
        "displayCode": display,
        "market": market,
        "assetType": asset_type,
        "active": bool(row[8]) if len(row) > 8 else True,
        "exchange": exchange,
    }


def _membership_record(
    *,
    raw_symbol: Any,
    normalized_symbol: str | None,
    result: str,
    status: str,
    exchange: str | None,
    security_type: str | None,
    listing_status: str | None,
    policy_state: str,
) -> dict[str, Any]:
    return {
        "rawSymbol": _safe_text(raw_symbol),
        "normalizedSymbol": normalized_symbol,
        "normalizationResult": result,
        "membershipStatus": status,
        "exchange": exchange,
        "securityType": security_type,
        "listingStatus": listing_status,
        "sourcePolicyState": policy_state,
    }


def _source_policy_state(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"approved", "operator_supplied", "unknown_policy", "rejected"}:
        return normalized
    return "unknown_policy"


def _active_symbols(payload: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(payload, Mapping):
        return []
    symbols = payload.get("symbols")
    if not isinstance(symbols, list):
        return []
    result: list[str] = []
    for item in symbols:
        symbol = str(item or "").strip().upper()
        if symbol and symbol not in result:
            result.append(symbol)
    return result


def _build_universe_diff(
    *,
    previous_symbols: list[str],
    candidate_symbols: list[str],
    normalized_change_count: int,
    rejected_count: int,
) -> dict[str, Any]:
    previous_set = set(previous_symbols)
    candidate_set = set(candidate_symbols)
    added = [symbol for symbol in candidate_symbols if symbol not in previous_set]
    removed = [symbol for symbol in previous_symbols if symbol not in candidate_set]
    unchanged = [symbol for symbol in candidate_symbols if symbol in previous_set]
    previous_count = len(previous_symbols)
    candidate_count = len(candidate_symbols)
    shrink_percentage = ((previous_count - candidate_count) / previous_count * 100.0) if previous_count and candidate_count < previous_count else 0.0
    growth_percentage = ((candidate_count - previous_count) / previous_count * 100.0) if previous_count and candidate_count > previous_count else (100.0 if candidate_count and not previous_count else 0.0)
    coverage_delta = candidate_count - previous_count
    return {
        "contractVersion": "scanner_universe_version_diff_v1",
        "previousSymbolCount": previous_count,
        "candidateSymbolCount": candidate_count,
        "addedCount": len(added),
        "removedCount": len(removed),
        "unchangedCount": len(unchanged),
        "normalizedChangeCount": int(normalized_change_count),
        "rejectedSymbolCount": int(rejected_count),
        "coverageDelta": coverage_delta,
        "shrinkPercentage": round(shrink_percentage, 4),
        "growthPercentage": round(growth_percentage, 4),
        "addedSymbols": added[:50],
        "removedSymbols": removed[:50],
        "unchangedSymbols": unchanged[:50],
        "readOnly": True,
    }


def _qualification_reasons(
    *,
    projection: Mapping[str, Any],
    symbol_count: int,
    threshold: int,
    now: datetime,
    max_age_days: int,
    max_shrink_percentage: float,
    diff: Mapping[str, Any],
    previous_symbols: list[str],
) -> list[str]:
    reasons = list(projection.get("blockingReasons") or [])
    policy_state = _source_policy_state(projection.get("sourcePolicyState"))
    if policy_state == "unknown_policy":
        reasons.append("source_policy_unknown")
    elif policy_state == "rejected":
        reasons.append("source_policy_rejected")
    if symbol_count <= 0:
        reasons.append("empty_universe")
    if symbol_count and symbol_count < threshold:
        reasons.append("below_minimum_coverage")
    if projection.get("rejectedSymbols"):
        reasons.append("normalization_rejected")
    source_as_of = _parse_date(projection.get("sourceAsOf"))
    if source_as_of is None:
        reasons.append("source_metadata_missing")
    else:
        age_days = max(0, (now.date() - source_as_of).days)
        if age_days > int(max_age_days):
            reasons.append("stale_source")
    if not _safe_text(projection.get("sourceArtifactIdentity")):
        reasons.append("source_metadata_missing")
    if previous_symbols and float(diff.get("shrinkPercentage") or 0.0) > float(max_shrink_percentage):
        reasons.append("suspicious_universe_shrink")
    return list(dict.fromkeys(reasons))


def _candidate_universe_version(market: str, projection: Mapping[str, Any], symbols: list[str]) -> str:
    identity = {
        "market": market,
        "sourceId": projection.get("sourceId"),
        "sourceClass": projection.get("sourceClass"),
        "sourceAsOf": projection.get("sourceAsOf"),
        "sourceArtifactIdentity": projection.get("sourceArtifactIdentity"),
        "symbols": symbols,
    }
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"scanner-universe-{market.lower()}-{digest}"


def _artifact_identity(source_path: Path, payload: Mapping[str, Any]) -> str:
    if payload:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    else:
        body = _source_path_label(source_path)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    return f"{_source_path_label(source_path)}#{digest}"


def _repo_root(value: str | Path | None = None) -> Path:
    if value is not None and str(value).strip():
        return Path(str(value)).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def _relative_path(path: Path | None, root: Path) -> str:
    if path is None:
        return ""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return _source_path_label(path)


def _configured_path(env: Mapping[str, str], keys: Iterable[str], *, root: Path) -> Path | None:
    for key in keys:
        value = str(env.get(key, "") or "").strip()
        if not value:
            continue
        path = Path(value).expanduser()
        return path if path.is_absolute() else root / path
    return None


def _path_date(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date().isoformat()
    except OSError:
        return None


def _count_csv_symbols(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return 0
            return sum(1 for row in reader if any(str(value or "").strip() for value in row.values()))
    except Exception:
        return 0


def _count_parquet_symbols(path: Path | None) -> int:
    if path is None:
        return 0
    try:
        if not path.exists() or not path.is_dir():
            return 0
        return sum(1 for item in path.iterdir() if item.is_file() and item.suffix.lower() == ".parquet")
    except OSError:
        return 0


def _state_reasons(value: str, *, fallback: str, ready_states: set[str]) -> list[str]:
    normalized = str(value or "").strip().lower()
    if normalized in ready_states:
        return []
    if normalized in {"", "unknown", "not_evaluated"}:
        return [fallback]
    return [normalized]


def _dedupe_texts(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _rejection_rate(rejected_count: int, raw_count: int) -> float:
    raw = int(raw_count or 0)
    if raw <= 0:
        return 0.0
    return round(float(rejected_count or 0) / raw * 100.0, 4)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _parse_date(value: Any) -> date | None:
    text = _safe_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        parsed = _parse_datetime(text)
        return parsed.date() if parsed is not None else None


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


def _read_json_payload(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_json_file(path: Path) -> dict[str, Any] | None:
    payload = _read_json_payload(path)
    return payload if isinstance(payload, dict) else None


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
    "SCANNER_UNIVERSE_SOURCE_CONTRACT_VERSION",
    "SCANNER_UNIVERSE_SOURCE_INVENTORY_VERSION",
    "ScannerUniverseLifecycleStore",
    "activate_scanner_universe_from_file",
    "activate_scanner_universe_from_source",
    "build_scanner_universe_activation_qualification_pack",
    "build_scanner_universe_current_state_matrix",
    "build_scanner_universe_downstream_readiness",
    "build_scanner_universe_source_inventory",
    "build_scanner_universe_lifecycle_readiness",
    "discover_scanner_universe_source_artifacts",
    "dry_run_scanner_universe_source",
    "normalize_scanner_universe_symbol",
    "read_scanner_universe_source_file",
]
