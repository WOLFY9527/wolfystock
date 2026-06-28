from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from scripts.quote_snapshot_operator_verifier import build_operator_verifier_payload, main
from src.services.quote_snapshot_readiness import (
    QuoteSnapshot,
    QuoteSnapshotProviderResult,
    QuoteSnapshotReadinessRequest,
)


class _FakeQuoteSnapshotProvider:
    def __init__(self, snapshots: dict[str, QuoteSnapshot] | None = None) -> None:
        self.snapshots = dict(snapshots or {})
        self.calls: list[QuoteSnapshotReadinessRequest] = []
        self.write_calls: list[dict] = []

    def fetch_quote_snapshots(
        self,
        request: QuoteSnapshotReadinessRequest,
    ) -> QuoteSnapshotProviderResult:
        self.calls.append(request)
        rows = [self.snapshots[symbol] for symbol in request.symbols if symbol in self.snapshots]
        if rows:
            return QuoteSnapshotProviderResult.available(rows)
        return QuoteSnapshotProviderResult.unavailable("provider_missing")


def _snapshots(*symbols: str, as_of: datetime | None = None) -> dict[str, QuoteSnapshot]:
    return {
        symbol: QuoteSnapshot(
            symbol=symbol,
            market="us",
            last=100.0 + index,
            previous_close=99.0 + index,
            volume=1_000_000 + index,
            as_of=as_of or datetime.now(timezone.utc),
            currency="USD",
            source="local_quote_snapshot_cache",
        )
        for index, symbol in enumerate(symbols)
    }


def test_inspect_mode_reports_gates_and_dependency_without_values() -> None:
    payload = build_operator_verifier_payload(mode="inspect", env={}, symbols=["SPY", "QQQ"])

    assert payload["status"] == "ok"
    assert payload["mode"] == "inspect"
    assert {gate["name"] for gate in payload["envGates"]} == {
        "WOLFYSTOCK_US_QUOTE_SNAPSHOT_LIVE_ENABLED",
        "WOLFYSTOCK_US_QUOTE_SNAPSHOT_CACHE_WRITE_ENABLED",
    }
    assert all(gate["valueRedacted"] is True for gate in payload["envGates"])
    assert payload["dependencyState"]["yfinance"]["detailsExposed"] is False
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    assert "apikey" not in serialized
    assert "requestid" not in serialized


def test_dry_run_does_not_call_provider_or_mutate_cache() -> None:
    provider = _FakeQuoteSnapshotProvider(_snapshots("SPY"))

    payload = build_operator_verifier_payload(
        mode="dry-run",
        env={},
        symbols=["SPY"],
        quote_provider=provider,
    )

    assert payload["status"] == "ok"
    assert payload["dryRun"] is True
    assert payload["networkCallsEnabled"] is False
    assert payload["mutationEnabled"] is False
    assert provider.calls == []
    assert provider.write_calls == []


def test_execute_refuses_without_explicit_flag_and_required_gates() -> None:
    no_flag = build_operator_verifier_payload(
        mode="execute",
        env={},
        symbols=["AAPL"],
        execute=False,
    )
    no_gates = build_operator_verifier_payload(
        mode="execute",
        env={},
        symbols=["AAPL"],
        execute=True,
    )

    assert no_flag["status"] == "failed_closed"
    assert no_flag["reason"] == "missing_explicit_execute_flag"
    assert no_gates["status"] == "failed_closed"
    assert no_gates["reason"] == "required_env_gates_disabled"
    assert no_gates["missingRequiredGates"] == [
        "WOLFYSTOCK_US_QUOTE_SNAPSHOT_LIVE_ENABLED",
        "WOLFYSTOCK_US_QUOTE_SNAPSHOT_CACHE_WRITE_ENABLED",
    ]


def test_verify_snapshot_reports_available_missing_and_stale_symbols() -> None:
    provider = _FakeQuoteSnapshotProvider(
        {
            **_snapshots("SPY", "AAPL"),
            **_snapshots("QQQ", as_of=datetime.now(timezone.utc) - timedelta(days=2)),
        }
    )

    payload = build_operator_verifier_payload(
        mode="verify-snapshot",
        env={},
        symbols=["SPY", "QQQ", "AAPL", "MSFT"],
        quote_provider=provider,
        max_age_seconds=60 * 60,
    )

    assert payload["status"] == "partial"
    readiness = payload["quoteSnapshotReadiness"]
    assert readiness["availableSymbols"] == ["SPY", "AAPL"]
    assert readiness["staleSymbols"] == ["QQQ"]
    assert readiness["missingSymbols"] == ["MSFT"]
    assert payload["networkCallsEnabled"] is False
    assert payload["mutationEnabled"] is False


def test_verify_scanner_marks_quote_snapshot_available_only_when_rows_exist() -> None:
    provider = _FakeQuoteSnapshotProvider(_snapshots("SPY", "QQQ", "AAPL", "MSFT"))

    payload = build_operator_verifier_payload(
        mode="verify-scanner",
        env={},
        symbols=["SPY", "QQQ", "AAPL", "MSFT"],
        quote_provider=provider,
    )

    assert payload["status"] == "ok"
    scanner = payload["scannerReadiness"]["scannerUniverseReadiness"]
    assert scanner["availableDataClasses"] == ["universe", "quote_snapshot"]
    assert "quote_snapshot" not in scanner["missingDataFamilies"]
    assert scanner["eligibleSymbols"] == ["SPY", "QQQ", "AAPL", "MSFT"]
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in ("rawpayload", "traceback", "requestid", "traceid", "cachekey", "token=secret"):
        assert forbidden not in serialized


def test_cli_execute_without_execute_flag_exits_failed_closed(capsys) -> None:
    exit_code = main(["--mode", "execute", "--us-symbols", "AAPL"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 2
    assert payload["status"] == "failed_closed"
    assert payload["reason"] == "missing_explicit_execute_flag"


def test_cli_verify_snapshot_reads_explicit_cache_path_without_mutation(tmp_path, capsys) -> None:
    cache_path = tmp_path / "quote_snapshot.json"
    cache_path.write_text(
        json.dumps(
            {
                "quotes": [
                    {
                        "symbol": "SPY",
                        "market": "us",
                        "last": 500.0,
                        "previousClose": 499.0,
                        "volume": 1000,
                        "asOf": datetime.now(timezone.utc).isoformat(),
                        "currency": "USD",
                        "source": "operator_cache",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--mode",
            "verify-snapshot",
            "--us-symbols",
            "SPY",
            "--cache-path",
            str(cache_path),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["quoteSnapshotReadiness"]["availableSymbols"] == ["SPY"]
    assert payload["mutationEnabled"] is False
