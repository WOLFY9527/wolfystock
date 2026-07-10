# -*- coding: utf-8 -*-
"""Scanner universe lifecycle contract tests."""

from __future__ import annotations

import json
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from src.services.scanner_universe_lifecycle import (
    SCANNER_UNIVERSE_LIFECYCLE_CONTRACT_VERSION,
    ScannerUniverseLifecycleStore,
    activate_scanner_universe_from_file,
    build_scanner_universe_lifecycle_readiness,
    normalize_scanner_universe_symbol,
)
from scripts.scanner_universe_lifecycle_import import main as scanner_universe_import_main


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _source_payload(*, market: str = "cn", symbols: list[object] | None = None, generated_at: str | None = None) -> dict:
    return {
        "market": market,
        "sourceClass": "repo_fixture",
        "generatedAt": generated_at or "2026-07-05T00:00:00+00:00",
        "asOf": "2026-07-05",
        "symbols": symbols if symbols is not None else ["600001", "SH600001", "300123", "bad-symbol"],
    }


def test_valid_universe_activation_normalizes_deduplicates_and_versions(tmp_path: Path) -> None:
    store = ScannerUniverseLifecycleStore(root=tmp_path / "universe")
    source = _write_json(
        tmp_path / "input" / "cn.json",
        _source_payload(symbols=["600001", "SH600001", "SZ300123", "000005"]),
    )

    result = activate_scanner_universe_from_file(
        source_path=source,
        store=store,
        market="cn",
        minimum_coverage_threshold=3,
    )

    assert result["status"] == "activated"
    assert result["previousUniverseVersion"] is None
    readiness = build_scanner_universe_lifecycle_readiness(
        store=store,
        market="cn",
        now=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )
    assert readiness["contractVersion"] == SCANNER_UNIVERSE_LIFECYCLE_CONTRACT_VERSION
    assert readiness["market"] == "CN"
    assert readiness["symbols"] == ["600001", "300123", "000005"]
    assert readiness["symbolCount"] == 3
    assert readiness["sourceClass"] == "repo_fixture"
    assert readiness["universeVersion"].startswith("scanner-universe-cn-")
    assert readiness["freshnessState"] == "fresh"
    assert readiness["coverageState"] == "sufficient"
    assert readiness["usable"] is True
    assert readiness["blockingReasons"] == []
    assert readiness["downstreamImpact"]["blockedProducts"] == ["Scanner", "Research Radar", "Backtest", "Market Overview"]
    assert readiness["downstreamReadiness"]["consumers"]["Scanner"]["membershipState"] == "ready"
    assert readiness["downstreamReadiness"]["consumers"]["Scanner"]["finalProductState"] == "blocked"
    assert readiness["readOnly"] is True
    assert readiness["noExternalCalls"] is True
    assert readiness["providerCallsEnabled"] is False


def test_import_rejects_malformed_empty_and_below_threshold_without_replacing_last_good(tmp_path: Path) -> None:
    store = ScannerUniverseLifecycleStore(root=tmp_path / "universe")
    good_source = _write_json(
        tmp_path / "input" / "good.json",
        _source_payload(symbols=["AAPL", "MSFT", "NVDA"], market="us"),
    )
    activate_scanner_universe_from_file(
        source_path=good_source,
        store=store,
        market="us",
        minimum_coverage_threshold=3,
    )
    before = build_scanner_universe_lifecycle_readiness(store=store, market="us")

    malformed = _write_json(tmp_path / "input" / "malformed.json", {"market": "us", "symbols": ["AAPL", 123, "MSFT"]})
    malformed_result = activate_scanner_universe_from_file(
        source_path=malformed,
        store=store,
        market="us",
        minimum_coverage_threshold=3,
    )

    empty = _write_json(tmp_path / "input" / "empty.json", _source_payload(market="us", symbols=[]))
    empty_result = activate_scanner_universe_from_file(
        source_path=empty,
        store=store,
        market="us",
        minimum_coverage_threshold=3,
    )

    narrow = _write_json(tmp_path / "input" / "narrow.json", _source_payload(market="us", symbols=["AAPL", "MSFT"]))
    narrow_result = activate_scanner_universe_from_file(
        source_path=narrow,
        store=store,
        market="us",
        minimum_coverage_threshold=3,
    )

    after = build_scanner_universe_lifecycle_readiness(store=store, market="us")
    assert malformed_result["status"] == "rejected"
    assert "normalization_rejected" in malformed_result["rejectedReasons"]
    assert empty_result["status"] == "rejected"
    assert "empty_universe" in empty_result["rejectedReasons"]
    assert narrow_result["status"] == "rejected"
    assert "below_minimum_coverage" in narrow_result["rejectedReasons"]
    assert after["universeVersion"] == before["universeVersion"]
    assert after["symbols"] == before["symbols"]
    assert after["lastRejectedImportReason"] == "below_minimum_coverage"


def test_stale_and_below_threshold_readiness_fail_closed(tmp_path: Path) -> None:
    store = ScannerUniverseLifecycleStore(root=tmp_path / "universe")
    source = _write_json(
        tmp_path / "input" / "hk.json",
        _source_payload(market="hk", symbols=["700.HK", "HK00005"], generated_at="2026-06-20T00:00:00+00:00"),
    )
    activate_scanner_universe_from_file(
        source_path=source,
        store=store,
        market="hk",
        minimum_coverage_threshold=2,
    )

    stale = build_scanner_universe_lifecycle_readiness(
        store=store,
        market="hk",
        minimum_coverage_threshold=3,
        max_age_days=3,
        now=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )

    assert stale["symbols"] == ["HK00700", "HK00005"]
    assert stale["freshnessState"] == "stale"
    assert stale["coverageState"] == "insufficient"
    assert stale["usable"] is False
    assert "stale_universe" in stale["blockingReasons"]
    assert "below_minimum_coverage" in stale["blockingReasons"]
    assert stale["downstreamImpact"]["blockedProducts"] == ["Scanner", "Research Radar", "Backtest", "Market Overview"]


def test_missing_metadata_and_missing_source_fail_closed(tmp_path: Path) -> None:
    store = ScannerUniverseLifecycleStore(root=tmp_path / "universe")

    missing = build_scanner_universe_lifecycle_readiness(store=store, market="cn")
    assert missing["usable"] is False
    assert "source_missing" in missing["blockingReasons"]

    active_dir = store.market_dir("cn")
    active_dir.mkdir(parents=True, exist_ok=True)
    (active_dir / "active.json").write_text("{not-json", encoding="utf-8")

    malformed = build_scanner_universe_lifecycle_readiness(store=store, market="cn")
    assert malformed["usable"] is False
    assert "metadata_malformed" in malformed["blockingReasons"]


def test_market_specific_symbol_normalization() -> None:
    assert normalize_scanner_universe_symbol("SH600001", market="cn") == "600001"
    assert normalize_scanner_universe_symbol("600001.SS", market="cn") == "600001"
    assert normalize_scanner_universe_symbol("AAPL", market="us") == "AAPL"
    assert normalize_scanner_universe_symbol("brk.b", market="us") == "BRK.B"
    assert normalize_scanner_universe_symbol("700.HK", market="hk") == "HK00700"
    assert normalize_scanner_universe_symbol("hk5", market="hk") == "HK00005"
    assert normalize_scanner_universe_symbol("SPY", market="cn") is None
    assert normalize_scanner_universe_symbol("HK00700", market="us") is None


def test_lifecycle_import_and_readiness_do_not_open_network_sockets(tmp_path: Path) -> None:
    store = ScannerUniverseLifecycleStore(root=tmp_path / "universe")
    activated_at = datetime.now(timezone.utc).replace(microsecond=0)
    source = _write_json(
        tmp_path / "input" / "us.json",
        _source_payload(
            market="us",
            symbols=["SPY", "QQQ", "AAPL"],
            generated_at=activated_at.isoformat(),
        ),
    )

    with patch.object(socket.socket, "connect", side_effect=AssertionError("network must not be used")):
        activate_scanner_universe_from_file(
            source_path=source,
            store=store,
            market="us",
            minimum_coverage_threshold=3,
            activated_at=activated_at,
        )
        readiness = build_scanner_universe_lifecycle_readiness(
            store=store,
            market="us",
            now=activated_at + timedelta(minutes=1),
        )

    assert readiness["usable"] is True


def test_import_cli_activates_local_input_without_refreshing_runtime(tmp_path: Path, capsys) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0)
    source = _write_json(
        tmp_path / "input" / "cn.json",
        _source_payload(
            market="cn",
            symbols=["600001", "SH600001", "300123"],
            generated_at=generated_at.isoformat(),
        ),
    )

    exit_code = scanner_universe_import_main(
        [
            "--source",
            str(source),
            "--market",
            "cn",
            "--root",
            str(tmp_path / "store"),
            "--minimum-coverage-threshold",
            "2",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["action"]["status"] == "activated"
    assert payload["readiness"]["symbols"] == ["600001", "300123"]
    assert payload["readiness"]["usable"] is True
    assert payload["scannerRefreshExecuted"] is False
    assert payload["runtimeBehaviorChanged"] is False
    assert payload["noExternalCalls"] is True
    assert payload["providerCallsEnabled"] is False
