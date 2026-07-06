# -*- coding: utf-8 -*-
"""Real scanner universe source lifecycle qualification tests."""

from __future__ import annotations

import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.scanner_universe_lifecycle_import import main as scanner_universe_import_main
from src.services.scanner_universe_lifecycle import (
    ScannerUniverseLifecycleStore,
    activate_scanner_universe_from_source,
    build_scanner_universe_lifecycle_readiness,
    build_scanner_universe_source_inventory,
    dry_run_scanner_universe_source,
    read_scanner_universe_source_file,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _source(
    *,
    market: str = "us",
    source_policy_state: str = "approved",
    source_id: str = "operator/us-approved",
    source_class: str = "operator_file",
    symbols: list[object] | None = None,
    source_as_of: str = "2026-07-05",
    retrieved_at: str = "2026-07-05T01:02:03+00:00",
) -> dict:
    return {
        "market": market,
        "sourceId": source_id,
        "sourceClass": source_class,
        "sourceAsOf": source_as_of,
        "retrievedAt": retrieved_at,
        "sourceArtifactIdentity": f"{source_id}@{source_as_of}",
        "sourcePolicyState": source_policy_state,
        "symbols": symbols if symbols is not None else ["AAPL", "MSFT", "BRK.B"],
    }


def test_inventory_maps_actual_supported_market_sources_without_approval_inference() -> None:
    inventory = build_scanner_universe_source_inventory()

    assert inventory["contractVersion"] == "scanner_universe_source_inventory_v1"
    by_market = {item["market"]: item for item in inventory["markets"]}
    assert set(by_market) == {"CN", "US", "HK"}
    assert "TushareFetcher.stock_basic" in {source["sourceName"] for source in by_market["CN"]["sources"]}
    assert "AkshareFetcher.stock_info_a_code_name" in {source["sourceName"] for source in by_market["CN"]["sources"]}
    assert "local_us_parquet_dir" in {source["sourceName"] for source in by_market["US"]["sources"]}
    assert "alpaca_assets_metadata" in {source["sourceName"] for source in by_market["US"]["sources"]}
    assert "local_db_hk_history" in {source["sourceName"] for source in by_market["HK"]["sources"]}
    alpaca = next(source for source in by_market["US"]["sources"] if source["sourceName"] == "alpaca_assets_metadata")
    assert alpaca["sourcePolicyState"] == "unknown_policy"
    assert alpaca["suitabilityForUniverseMembership"] == "blocked_until_policy_approved"
    assert alpaca["commercialLicensingUncertainty"] is True
    assert all(source["networkOrLocal"] in {"network", "local"} for source in alpaca["relatedSources"])


def test_read_source_file_projects_symbol_membership_and_normalization(tmp_path: Path) -> None:
    source_path = _write_json(
        tmp_path / "us-source.json",
        _source(symbols=["aapl", {"symbol": "MSFT", "exchange": "NASDAQ", "securityType": "Common Stock"}, "SPX"]),
    )

    projection = read_scanner_universe_source_file(source_path, market="us")

    assert projection["contractVersion"] == "scanner_universe_source_membership_v1"
    assert projection["market"] == "US"
    assert projection["sourceId"] == "operator/us-approved"
    assert projection["sourceClass"] == "operator_file"
    assert projection["sourceAsOf"] == "2026-07-05"
    assert projection["retrievedAt"] == "2026-07-05T01:02:03+00:00"
    assert projection["sourceArtifactIdentity"] == "operator/us-approved@2026-07-05"
    assert projection["sourcePolicyState"] == "approved"
    assert projection["symbolCount"] == 2
    assert projection["memberships"][0]["rawSymbol"] == "aapl"
    assert projection["memberships"][0]["normalizedSymbol"] == "AAPL"
    assert projection["memberships"][0]["normalizationResult"] == "normalized"
    assert projection["memberships"][1]["exchange"] == "NASDAQ"
    assert projection["memberships"][1]["securityType"] == "Common Stock"
    assert projection["memberships"][2]["rawSymbol"] == "SPX"
    assert projection["memberships"][2]["membershipStatus"] == "rejected"
    assert projection["memberships"][2]["normalizationResult"] == "unsupported_symbol"


def test_unknown_policy_source_dry_run_stays_unqualified_and_no_activation(tmp_path: Path) -> None:
    store = ScannerUniverseLifecycleStore(root=tmp_path / "store")
    source_path = _write_json(tmp_path / "source.json", _source(source_policy_state="unknown_policy"))

    result = dry_run_scanner_universe_source(
        source_path=source_path,
        store=store,
        market="us",
        minimum_coverage_threshold=2,
        now=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )
    readiness = build_scanner_universe_lifecycle_readiness(store=store, market="us")

    assert result["status"] == "rejected"
    assert "source_policy_unknown" in result["rejectedReasons"]
    assert result["activationReady"] is False
    assert result["dryRun"] is True
    assert readiness["usable"] is False
    assert readiness["universeVersion"] is None


def test_dry_run_diff_does_not_activate_and_explicit_activation_preserves_provenance(tmp_path: Path) -> None:
    store = ScannerUniverseLifecycleStore(root=tmp_path / "store")
    source_path = _write_json(tmp_path / "source.json", _source(symbols=["AAPL", "MSFT", "NVDA"]))

    dry_run = dry_run_scanner_universe_source(
        source_path=source_path,
        store=store,
        market="us",
        minimum_coverage_threshold=3,
        now=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )
    before = build_scanner_universe_lifecycle_readiness(store=store, market="us")
    activated = activate_scanner_universe_from_source(
        source_path=source_path,
        store=store,
        market="us",
        minimum_coverage_threshold=3,
        activated_at=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )
    after = build_scanner_universe_lifecycle_readiness(
        store=store,
        market="us",
        now=datetime(2026, 7, 6, tzinfo=timezone.utc),
    )

    assert dry_run["status"] == "accepted"
    assert dry_run["dryRun"] is True
    assert dry_run["diff"]["addedCount"] == 3
    assert dry_run["diff"]["removedCount"] == 0
    assert before["universeVersion"] is None
    assert activated["status"] == "activated"
    assert after["sourceId"] == "operator/us-approved"
    assert after["sourceArtifactIdentity"] == "operator/us-approved@2026-07-05"
    assert after["sourcePolicyState"] == "approved"
    assert after["symbols"] == ["AAPL", "MSFT", "NVDA"]
    assert after["membershipReadiness"]["usable"] is True
    assert after["marketDataReadiness"]["status"] == "not_evaluated"
    assert after["candidateGenerationReadiness"]["status"] == "blocked"
    assert after["downstreamImpact"]["blockedProducts"] == []


def test_suspicious_shrink_is_blocked_but_bounded_diff_is_accepted(tmp_path: Path) -> None:
    store = ScannerUniverseLifecycleStore(root=tmp_path / "store")
    first = _write_json(tmp_path / "first.json", _source(symbols=["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META"]))
    activate_scanner_universe_from_source(
        source_path=first,
        store=store,
        market="us",
        minimum_coverage_threshold=2,
        activated_at=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )

    tiny = _write_json(tmp_path / "tiny.json", _source(symbols=["AAPL"], source_id="operator/us-tiny"))
    tiny_result = activate_scanner_universe_from_source(
        source_path=tiny,
        store=store,
        market="us",
        minimum_coverage_threshold=1,
        max_shrink_percentage=50.0,
        activated_at=datetime(2026, 7, 6, tzinfo=timezone.utc),
    )
    bounded = _write_json(tmp_path / "bounded.json", _source(symbols=["AAPL", "MSFT", "NVDA", "TSLA", "AMD"], source_id="operator/us-bounded"))
    bounded_result = activate_scanner_universe_from_source(
        source_path=bounded,
        store=store,
        market="us",
        minimum_coverage_threshold=2,
        max_shrink_percentage=50.0,
        activated_at=datetime(2026, 7, 7, tzinfo=timezone.utc),
    )
    readiness = build_scanner_universe_lifecycle_readiness(store=store, market="us")

    assert tiny_result["status"] == "rejected"
    assert "suspicious_universe_shrink" in tiny_result["rejectedReasons"]
    assert tiny_result["diff"]["shrinkPercentage"] == pytest.approx(83.3333, rel=1e-3)
    assert bounded_result["status"] == "activated"
    assert bounded_result["diff"]["removedCount"] == 2
    assert bounded_result["diff"]["addedCount"] == 1
    assert readiness["sourceId"] == "operator/us-bounded"
    assert readiness["symbols"] == ["AAPL", "MSFT", "NVDA", "TSLA", "AMD"]


def test_malformed_empty_duplicate_and_freshness_fail_closed(tmp_path: Path) -> None:
    store = ScannerUniverseLifecycleStore(root=tmp_path / "store")
    malformed = _write_json(tmp_path / "malformed.json", {"market": "us", "sourcePolicyState": "approved", "symbols": "AAPL"})
    empty = _write_json(tmp_path / "empty.json", _source(symbols=[]))
    duplicate = _write_json(tmp_path / "duplicate.json", _source(symbols=["AAPL", "aapl", "MSFT"]))
    stale = _write_json(tmp_path / "stale.json", _source(symbols=["AAPL", "MSFT"], source_as_of="2026-06-01"))

    malformed_result = dry_run_scanner_universe_source(source_path=malformed, store=store, market="us")
    empty_result = dry_run_scanner_universe_source(source_path=empty, store=store, market="us")
    duplicate_result = dry_run_scanner_universe_source(
        source_path=duplicate,
        store=store,
        market="us",
        minimum_coverage_threshold=2,
        now=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )
    stale_result = dry_run_scanner_universe_source(
        source_path=stale,
        store=store,
        market="us",
        minimum_coverage_threshold=2,
        max_age_days=3,
        now=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )

    assert "metadata_malformed" in malformed_result["rejectedReasons"]
    assert "empty_universe" in empty_result["rejectedReasons"]
    assert duplicate_result["status"] == "accepted"
    assert duplicate_result["symbolCount"] == 2
    assert duplicate_result["diff"]["normalizedChangeCount"] == 1
    assert "stale_source" in stale_result["rejectedReasons"]


def test_cn_us_hk_normalization_qualification_for_supported_forms(tmp_path: Path) -> None:
    cn = read_scanner_universe_source_file(
        _write_json(tmp_path / "cn.json", _source(market="cn", symbols=["SH600001", "600001.SS", "SZ300123"])),
        market="cn",
    )
    us = read_scanner_universe_source_file(
        _write_json(tmp_path / "us.json", _source(market="us", symbols=["brk.b", "AAPL", "SPX"])),
        market="us",
    )
    hk = read_scanner_universe_source_file(
        _write_json(tmp_path / "hk.json", _source(market="hk", symbols=["700.HK", "hk5", "00700"])),
        market="hk",
    )

    assert [item["normalizedSymbol"] for item in cn["memberships"] if item["membershipStatus"] == "active"] == [
        "600001",
        "300123",
    ]
    assert [item["normalizedSymbol"] for item in us["memberships"] if item["membershipStatus"] == "active"] == [
        "BRK.B",
        "AAPL",
    ]
    assert [item["normalizedSymbol"] for item in hk["memberships"] if item["membershipStatus"] == "active"] == [
        "HK00700",
        "HK00005",
    ]


def test_cli_supports_inspect_dry_run_and_explicit_activate_without_network(tmp_path: Path, capsys) -> None:
    source = _write_json(tmp_path / "source.json", _source(symbols=["AAPL", "MSFT", "NVDA"]))
    store_root = tmp_path / "store"

    with patch.object(socket.socket, "connect", side_effect=AssertionError("network must not be used")):
        inspect_code = scanner_universe_import_main(
            ["--source", str(source), "--market", "us", "--root", str(store_root), "--minimum-coverage-threshold", "3", "--inspect"]
        )
        inspect_payload = json.loads(capsys.readouterr().out)
        dry_run_code = scanner_universe_import_main(
            ["--source", str(source), "--market", "us", "--root", str(store_root), "--minimum-coverage-threshold", "3", "--dry-run"]
        )
        dry_run_payload = json.loads(capsys.readouterr().out)
        activate_code = scanner_universe_import_main(
            ["--source", str(source), "--market", "us", "--root", str(store_root), "--minimum-coverage-threshold", "3", "--activate"]
        )
        activate_payload = json.loads(capsys.readouterr().out)
        active_code = scanner_universe_import_main(["--market", "us", "--root", str(store_root), "--inspect-active"])
        active_payload = json.loads(capsys.readouterr().out)

    assert inspect_code == 0
    assert inspect_payload["action"]["status"] == "inspected"
    assert dry_run_code == 0
    assert dry_run_payload["action"]["dryRun"] is True
    assert dry_run_payload["readiness"]["universeVersion"] is None
    assert activate_code == 0
    assert activate_payload["action"]["status"] == "activated"
    assert active_code == 0
    assert active_payload["readiness"]["usable"] is True
    assert active_payload["scannerRefreshExecuted"] is False
    assert active_payload["providerCallsEnabled"] is False
