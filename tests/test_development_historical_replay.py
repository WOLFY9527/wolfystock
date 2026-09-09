from __future__ import annotations

import hashlib
import json
import os
from decimal import Decimal
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from src.core.scanner_profile import get_scanner_profile
from src.services.backtest_service import BacktestService
from src.services.backtest_data_source_guard import assess_backtest_data_source_eligibility
from src.services.development_historical_replay import (
    DEVELOPMENT_HISTORICAL_REPLAY_MANIFEST_ENV,
    DEVELOPMENT_HISTORICAL_REPLAY_MANIFEST_VERSION,
    DevelopmentHistoricalReplayProvider,
)
from src.services.historical_ohlcv_readiness import (
    HistoricalOhlcvProviderResult,
    HistoricalOhlcvReadinessRequest,
)
from src.services.market_scanner_service import MarketScannerService
from src.services.research_radar_service import ResearchRadarService, _scanner_lineage_from_run
from src.services.rule_backtest_service import RuleBacktestService
from src.storage import DatabaseManager


def _daily_rows(*, count: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    session_date = date(2023, 1, 2)
    while len(rows) < count:
        if session_date.weekday() < 5:
            close = round(10.5 + len(rows) * 0.02, 4)
            rows.append(
                {
                    "sessionDate": session_date.isoformat(),
                    "open": round(close - 0.2, 4),
                    "high": round(close + 0.3, 4),
                    "low": round(close - 0.4, 4),
                    "close": close,
                    "volume": 1000 + len(rows),
                    "adjustedClose": close,
                }
            )
        session_date += timedelta(days=1)
    return rows


def _payload(
    *,
    market: str,
    symbol: str,
    canonical_symbol: str,
    provider: str,
    source: str,
    rows: list[dict[str, object]] | None = None,
) -> dict:
    return {
        "market": market,
        "symbol": symbol,
        "canonicalSymbol": canonical_symbol,
        "provider": provider,
        "source": source,
        "observedAt": "2026-09-01T12:00:00Z",
        "asOf": "2024-01-03T08:00:00Z",
        "asOfState": "known",
        "interval": "1d",
        "delivery": "local_replay",
        "historical": True,
        "replay": True,
        "development": True,
        "authority": False,
        "fallback": False,
        "productionEligible": False,
        "observationOnly": True,
        "adjusted": True,
        "rows": rows
        if rows is not None
        else [
            {
                "sessionDate": "2024-01-02",
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 1000,
                "adjustedClose": 10.5,
            },
            {
                "sessionDate": "2024-01-03",
                "open": 10.5,
                "high": 12.0,
                "low": 10.0,
                "close": 11.5,
                "volume": 1200,
                "adjustedClose": 11.5,
            },
        ],
    }


def _write_manifest(tmp_path, payload: dict, *, payload_name: str = "observation.json"):
    payload_path = tmp_path / payload_name
    payload_bytes = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    payload_path.write_bytes(payload_bytes)
    entry = {
        key: payload[key]
        for key in (
            "market",
            "symbol",
            "canonicalSymbol",
            "provider",
            "source",
            "observedAt",
            "asOf",
            "asOfState",
            "interval",
            "delivery",
            "historical",
            "replay",
            "development",
            "authority",
            "fallback",
            "productionEligible",
            "observationOnly",
        )
    }
    entry.update({"path": payload_name, "sha256": hashlib.sha256(payload_bytes).hexdigest()})
    manifest = {
        "schemaVersion": DEVELOPMENT_HISTORICAL_REPLAY_MANIFEST_VERSION,
        "delivery": "local_replay",
        "historical": True,
        "replay": True,
        "development": True,
        "authority": False,
        "fallback": False,
        "productionEligible": False,
        "observationOnly": True,
        "observations": [entry],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path, payload_path, manifest


def _write_manifest_observations(tmp_path, payloads: list[dict]) -> tuple[object, list[object], dict]:
    entries = []
    payload_paths = []
    for index, payload in enumerate(payloads):
        payload_name = f"observation-{index}.json"
        payload_path = tmp_path / payload_name
        payload_bytes = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
        payload_path.write_bytes(payload_bytes)
        entry = {
            key: payload[key]
            for key in (
                "market",
                "symbol",
                "canonicalSymbol",
                "provider",
                "source",
                "observedAt",
                "asOf",
                "asOfState",
                "interval",
                "delivery",
                "historical",
                "replay",
                "development",
                "authority",
                "fallback",
                "productionEligible",
                "observationOnly",
            )
        }
        entry.update({"path": payload_name, "sha256": hashlib.sha256(payload_bytes).hexdigest()})
        entries.append(entry)
        payload_paths.append(payload_path)
    manifest = {
        "schemaVersion": DEVELOPMENT_HISTORICAL_REPLAY_MANIFEST_VERSION,
        "delivery": "local_replay",
        "historical": True,
        "replay": True,
        "development": True,
        "authority": False,
        "fallback": False,
        "productionEligible": False,
        "observationOnly": True,
        "observations": entries,
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path, payload_paths, manifest


@pytest.mark.parametrize(
    ("market", "symbol", "request_symbol", "canonical_symbol", "provider", "source"),
    [
        ("CN", "SH600519", "600519.SH", "600519", "akshare_archive", "eastmoney_historical"),
        ("CN", "SZ000001", "000001.SZ", "000001", "akshare_archive", "eastmoney_historical"),
        ("HK", "00700", "HK00700", "HK00700", "stooq_archive", "stooq_historical"),
        ("US", "AAPL", "AAPL.US", "AAPL", "stooq_archive", "stooq_historical"),
    ],
)
def test_replays_verified_cn_hk_us_observations_through_canonical_identity(
    tmp_path,
    market,
    symbol,
    request_symbol,
    canonical_symbol,
    provider,
    source,
) -> None:
    manifest_path, _, _ = _write_manifest(
        tmp_path,
        _payload(
            market=market,
            symbol=symbol,
            canonical_symbol=canonical_symbol,
            provider=provider,
            source=source,
        ),
    )

    result = DevelopmentHistoricalReplayProvider(manifest_path).fetch_ohlcv_history(
        HistoricalOhlcvReadinessRequest(symbol=request_symbol, market=market, require_adjusted=True)
    )

    assert result.unavailable_reason is None
    assert [bar.date.isoformat() for bar in result.bars] == ["2024-01-02", "2024-01-03"]
    assert result.bars[-1].close == 11.5
    assert result.bars[-1].adjusted_close == 11.5
    assert result.adjustments_available is True
    assert result.freshness_state == "stale"
    assert result.metadata == {
        "runtimeStatus": "available",
        "development": True,
        "historical": True,
        "replay": True,
        "delivery": "local_replay",
        "authority": False,
        "fallback": False,
        "productionEligible": False,
        "observationOnly": True,
        "provider": provider,
        "source": source,
        "market": market,
        "canonicalSymbol": canonical_symbol,
        "observedAt": "2026-09-01T12:00:00Z",
        "asOf": "2024-01-03T08:00:00Z",
        "asOfState": "known",
        "manifestVersion": DEVELOPMENT_HISTORICAL_REPLAY_MANIFEST_VERSION,
    }


def test_content_hash_tampering_fails_closed_before_replay(tmp_path) -> None:
    manifest_path, payload_path, _ = _write_manifest(
        tmp_path,
        _payload(
            market="US",
            symbol="AAPL",
            canonical_symbol="AAPL",
            provider="stooq_archive",
            source="stooq_historical",
        ),
    )
    payload_path.write_text('{"tampered":true}', encoding="utf-8")

    result = DevelopmentHistoricalReplayProvider(manifest_path).fetch_ohlcv_history(
        HistoricalOhlcvReadinessRequest(symbol="AAPL", market="US")
    )

    assert result.bars == ()
    assert result.unavailable_reason == "provider_unavailable"
    assert result.metadata["developmentReplayReason"] == "observation_sha256_mismatch"
    assert result.metadata["authority"] is False
    assert result.metadata["productionEligible"] is False


def test_replay_preserves_explicitly_unknown_as_of_without_inventing_a_cutoff(tmp_path) -> None:
    payload = _payload(
        market="US",
        symbol="AAPL",
        canonical_symbol="AAPL",
        provider="yfinance",
        source="yahoo",
    )
    payload["asOf"] = None
    payload["asOfState"] = "unknown"
    manifest_path, _, _ = _write_manifest(tmp_path, payload)

    result = DevelopmentHistoricalReplayProvider(manifest_path).fetch_ohlcv_history(
        HistoricalOhlcvReadinessRequest(symbol="AAPL", market="US")
    )

    assert result.bars
    assert result.metadata["asOf"] is None
    assert result.metadata["asOfState"] == "unknown"
    assert result.metadata["observedAt"] == "2026-09-01T12:00:00Z"


@pytest.mark.parametrize(
    ("as_of", "as_of_state", "reason"),
    [
        (None, "known", "payload_as_of_invalid"),
        ("2024-01-03T08:00:00Z", "unknown", "payload_as_of_unknown_invalid"),
        (None, "unavailable", "payload_as_of_state_invalid"),
    ],
)
def test_replay_rejects_inconsistent_as_of_state(tmp_path, as_of, as_of_state, reason) -> None:
    payload = _payload(
        market="US",
        symbol="AAPL",
        canonical_symbol="AAPL",
        provider="yfinance",
        source="yahoo",
    )
    payload["asOf"] = as_of
    payload["asOfState"] = as_of_state
    manifest_path, _, _ = _write_manifest(tmp_path, payload)

    result = DevelopmentHistoricalReplayProvider(manifest_path).fetch_ohlcv_history(
        HistoricalOhlcvReadinessRequest(symbol="AAPL", market="US")
    )

    assert result.bars == ()
    assert result.metadata["developmentReplayReason"] == reason.replace("payload_", "entry_", 1)


def test_production_authority_claim_fails_closed_even_with_a_valid_hash(tmp_path) -> None:
    payload = _payload(
        market="US",
        symbol="AAPL",
        canonical_symbol="AAPL",
        provider="stooq_archive",
        source="stooq_historical",
    )
    payload["productionEligible"] = True
    manifest_path, _, _ = _write_manifest(tmp_path, payload)

    result = DevelopmentHistoricalReplayProvider(manifest_path).fetch_ohlcv_history(
        HistoricalOhlcvReadinessRequest(symbol="AAPL", market="US")
    )

    assert result.bars == ()
    assert result.unavailable_reason == "provider_unavailable"
    assert result.metadata["developmentReplayReason"] == "observation_production_eligibility_invalid"
    assert result.metadata["observationOnly"] is True


@pytest.mark.parametrize(
    ("target", "field_name", "value", "reason"),
    [
        ("manifest", "replay", False, "manifest_replay_invalid"),
        ("entry", "development", False, "observation_development_invalid"),
        ("payload", "authority", True, "payload_authority_invalid"),
        ("payload", "fallback", True, "payload_fallback_invalid"),
        ("payload", "source", "fallback", "payload_fallback_source_invalid"),
        ("payload", "source", "fallback_static", "payload_fallback_source_invalid"),
        ("payload", "source", "missing", "payload_missing_source_invalid"),
        ("payload", "source", "unavailable", "payload_missing_source_invalid"),
        ("payload", "source", "synthetic_fixture", "payload_synthetic_source_invalid"),
        ("payload", "provider", "unit_fixture", "payload_synthetic_source_invalid"),
        ("payload", "source", "delayed_fixture", "payload_source_type_invalid"),
        ("payload", "source", "malformed_fixture", "payload_source_type_invalid"),
        ("payload", "source", "disabled_live_stub", "payload_source_type_invalid"),
    ],
)
def test_replay_metadata_and_synthetic_source_claims_fail_closed(
    tmp_path,
    target,
    field_name,
    value,
    reason,
) -> None:
    payload = _payload(
        market="US",
        symbol="AAPL",
        canonical_symbol="AAPL",
        provider="stooq_archive",
        source="stooq_historical",
    )
    manifest_path, _, manifest = _write_manifest(tmp_path, payload)
    if target == "manifest":
        manifest[field_name] = value
    elif target == "entry":
        manifest["observations"][0][field_name] = value
    if target in {"manifest", "entry"}:
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif target == "payload":
        payload[field_name] = value
        payload_bytes = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
        (tmp_path / "observation.json").write_bytes(payload_bytes)
        manifest["observations"][0]["sha256"] = hashlib.sha256(payload_bytes).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = DevelopmentHistoricalReplayProvider(manifest_path).fetch_ohlcv_history(
        HistoricalOhlcvReadinessRequest(symbol="AAPL", market="US")
    )

    assert result.bars == ()
    assert result.unavailable_reason == "provider_unavailable"
    assert result.metadata["developmentReplayReason"] == reason


def test_non_finite_ohlcv_fails_closed_as_replay_unavailable(tmp_path) -> None:
    payload = _payload(
        market="US",
        symbol="AAPL",
        canonical_symbol="AAPL",
        provider="stooq_archive",
        source="stooq_historical",
    )
    payload["rows"][0]["close"] = "bad"
    manifest_path, _, _ = _write_manifest(tmp_path, payload)

    result = DevelopmentHistoricalReplayProvider(manifest_path).fetch_ohlcv_history(
        HistoricalOhlcvReadinessRequest(symbol="AAPL", market="US")
    )

    assert result.bars == ()
    assert result.unavailable_reason == "provider_unavailable"
    assert result.metadata["developmentReplayReason"] == "observation_rejected"


@pytest.mark.parametrize(
    ("field_name", "value"),
    [("close", True), ("adjustedClose", "bad"), ("adjustedClose", True)],
    ids=("boolean-close", "text-adjusted-close", "boolean-adjusted-close"),
)
def test_invalid_canonical_numeric_replay_rows_fail_closed(tmp_path, field_name, value) -> None:
    payload = _payload(
        market="US",
        symbol="AAPL",
        canonical_symbol="AAPL",
        provider="stooq_archive",
        source="stooq_historical",
    )
    payload["rows"][0][field_name] = value
    manifest_path, _, _ = _write_manifest(tmp_path, payload)

    result = DevelopmentHistoricalReplayProvider(manifest_path).fetch_ohlcv_history(
        HistoricalOhlcvReadinessRequest(symbol="AAPL", market="US")
    )

    assert result.bars == ()
    assert result.unavailable_reason == "provider_unavailable"
    assert result.metadata["developmentReplayReason"] == "observation_rejected"


class _LocalUsOnlyProvider:
    def __init__(self) -> None:
        self.requests: list[HistoricalOhlcvReadinessRequest] = []

    def fetch_ohlcv_history(self, request: HistoricalOhlcvReadinessRequest) -> HistoricalOhlcvProviderResult:
        self.requests.append(request)
        if str(request.market).upper() != "US":
            return HistoricalOhlcvProviderResult.unavailable("provider_missing")
        return HistoricalOhlcvProviderResult.available(
            [
                {
                    "date": "2024-01-02",
                    "open": 20.0,
                    "high": 21.0,
                    "low": 19.0,
                    "close": 20.5,
                    "volume": 2000,
                    "adjustedClose": 20.5,
                }
            ],
            adjustments_available=True,
            metadata={"runtimeStatus": "available"},
        )


def test_scanner_combines_local_us_cache_with_cn_manifest_replay(tmp_path) -> None:
    manifest_path, _, _ = _write_manifest_observations(
        tmp_path,
        [
            _payload(
                market="CN",
                symbol="600519",
                canonical_symbol="600519",
                provider="akshare_archive",
                source="eastmoney_historical",
                rows=_daily_rows(count=260),
            ),
            _payload(
                market="US",
                symbol="AAPL",
                canonical_symbol="AAPL",
                provider="stooq_archive",
                source="stooq_historical",
                rows=_daily_rows(count=260),
            ),
        ],
    )
    local_provider = _LocalUsOnlyProvider()
    db = DatabaseManager(db_url="sqlite:///:memory:")
    with (
        patch.dict(
            os.environ,
            {
                DEVELOPMENT_HISTORICAL_REPLAY_MANIFEST_ENV: str(manifest_path),
                "WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED": "",
            },
            clear=False,
        ),
        patch(
            "src.services.market_scanner_service.build_readonly_local_us_ohlcv_cache_provider_from_env",
            return_value=local_provider,
        ),
        patch(
            "src.services.market_scanner_service.get_config",
            return_value=SimpleNamespace(scanner_local_universe_path=str(tmp_path / "scanner-universe.csv")),
        ),
        patch.object(MarketScannerService, "_load_local_us_universe_from_parquet", return_value=["AAPL"]),
        patch.object(MarketScannerService, "_load_local_us_universe_from_db", return_value=[]),
    ):
        service = MarketScannerService(db, data_manager=object())
        history, diagnostics = service._load_history_from_ohlcv_provider(
            code="600519",
            profile=get_scanner_profile(market="cn"),
        )
        us_result = service.historical_ohlcv_provider.fetch_ohlcv_history(
            HistoricalOhlcvReadinessRequest(symbol="AAPL", market="US")
        )
        universe = service._resolve_us_stock_universe(
            profile=get_scanner_profile(market="us"),
            allow_development_replay=True,
        )

    assert not history.empty, diagnostics
    assert diagnostics["source"] == "development_historical_replay"
    assert diagnostics["network_used"] is False
    assert diagnostics["observationOnly"] is True
    assert [(request.symbol, request.market) for request in local_provider.requests] == [("AAPL", "US")]
    assert us_result.metadata == {"runtimeStatus": "available"}
    assert universe["resolvedStarterSymbols"] == ["AAPL"]
    assert universe["source"] == "local_us_parquet_dir"
    assert [attempt["fetcher"] for attempt in universe["attempts"]] == [
        "local_us_parquet_dir",
        "local_db_us_history",
    ]


def test_backtest_uses_cn_manifest_replay_without_runtime_fallback_when_local_us_cache_exists(tmp_path) -> None:
    manifest_path, _, _ = _write_manifest(
        tmp_path,
        _payload(
            market="CN",
            symbol="600519",
            canonical_symbol="600519",
            provider="akshare_archive",
            source="eastmoney_historical",
        ),
    )
    local_provider = _LocalUsOnlyProvider()
    db = DatabaseManager(db_url="sqlite:///:memory:")
    with (
        patch.dict(
            os.environ,
            {DEVELOPMENT_HISTORICAL_REPLAY_MANIFEST_ENV: str(manifest_path)},
            clear=False,
        ),
        patch(
            "src.services.backtest_service.build_readonly_local_us_ohlcv_cache_provider_from_env",
            return_value=local_provider,
        ),
        patch("src.services.backtest_service.fetch_daily_history_with_local_us_fallback") as runtime_fallback,
    ):
        service = BacktestService(db)
        metadata = service._try_fill_daily_data(
            code="600519",
            analysis_date=date(2024, 1, 2),
            eval_window_days=1,
        )

    assert metadata is not None
    assert metadata.resolved_source == "DevelopmentHistoricalReplay"
    assert runtime_fallback.call_count == 0
    assert local_provider.requests == []
    assert [row.data_source for row in service._load_stock_daily_rows("600519")] == [
        "development_historical_replay",
        "development_historical_replay",
    ]


def test_from_env_requires_an_existing_manifest_without_creating_a_fallback(tmp_path) -> None:
    missing_manifest = tmp_path / "missing.json"
    with patch.dict(
        os.environ,
        {DEVELOPMENT_HISTORICAL_REPLAY_MANIFEST_ENV: str(missing_manifest)},
        clear=False,
    ), patch(
        "src.services.backtest_service.get_config",
        return_value=SimpleNamespace(backtest_enabled=True),
    ):
        assert DevelopmentHistoricalReplayProvider.from_env({}) is None
        provider = DevelopmentHistoricalReplayProvider.from_env()
    assert isinstance(provider, DevelopmentHistoricalReplayProvider)
    result = provider.fetch_ohlcv_history(HistoricalOhlcvReadinessRequest(symbol="AAPL", market="US"))
    assert result.bars == ()
    assert result.unavailable_reason == "provider_unavailable"
    assert result.metadata["developmentReplayReason"] == "manifest_unavailable"


def test_scanner_explicit_missing_manifest_stays_unavailable_without_runtime_provider(tmp_path) -> None:
    missing_manifest = tmp_path / "missing.json"
    with patch.dict(
        os.environ,
        {
            DEVELOPMENT_HISTORICAL_REPLAY_MANIFEST_ENV: str(missing_manifest),
            "WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED": "1",
            "LOCAL_US_PARQUET_DIR": "",
            "US_STOCK_PARQUET_DIR": "",
        },
        clear=False,
    ), patch("src.services.market_scanner_service.HistoricalOhlcvRuntimeAdapter") as runtime_adapter:
        service = MarketScannerService(
            DatabaseManager(db_url="sqlite:///:memory:"),
            data_manager=object(),
        )

    assert isinstance(service.historical_ohlcv_provider, DevelopmentHistoricalReplayProvider)
    runtime_adapter.assert_not_called()


def test_backtest_explicit_missing_manifest_blocks_runtime_fallback(tmp_path) -> None:
    missing_manifest = tmp_path / "missing.json"
    with (
        patch.dict(
            os.environ,
            {DEVELOPMENT_HISTORICAL_REPLAY_MANIFEST_ENV: str(missing_manifest)},
            clear=False,
        ),
        patch("src.services.backtest_service.fetch_daily_history_with_local_us_fallback") as runtime_fallback,
    ):
        service = BacktestService(DatabaseManager(db_url="sqlite:///:memory:"))
        metadata = service._try_fill_daily_data(
            code="AAPL",
            analysis_date=date(2024, 1, 2),
            eval_window_days=1,
        )

    assert metadata is None
    runtime_fallback.assert_not_called()


def test_backtest_sample_status_with_missing_manifest_skips_runtime_readiness_probe(tmp_path) -> None:
    missing_manifest = tmp_path / "missing.json"
    with patch.dict(
        os.environ,
        {DEVELOPMENT_HISTORICAL_REPLAY_MANIFEST_ENV: str(missing_manifest)},
        clear=False,
    ), patch(
        "src.services.backtest_service.get_config",
        return_value=SimpleNamespace(backtest_enabled=True),
    ):
        service = BacktestService(DatabaseManager(db_url="sqlite:///:memory:"))
        with patch.object(service, "_probe_runtime_historical_ohlcv_readiness") as runtime_probe:
            status = service.get_sample_status(code="AAPL")

    runtime_probe.assert_not_called()
    readiness = status["historicalOhlcvReadiness"]
    assert readiness["providerState"] == "provider_unavailable"
    assert readiness["runtimeStatus"] == "unavailable"
    assert readiness["reason"] == "provider_unavailable"
    assert status["resolved_source"] == "DevelopmentHistoricalReplay"


def test_backtest_persists_verified_replay_without_provider_fallback(tmp_path) -> None:
    manifest_path, _, _ = _write_manifest(
        tmp_path,
        _payload(
            market="US",
            symbol="AAPL",
            canonical_symbol="AAPL",
            provider="stooq_archive",
            source="stooq_historical",
        ),
    )
    db = DatabaseManager(db_url="sqlite:///:memory:")
    service = BacktestService(
        db,
        historical_ohlcv_provider=DevelopmentHistoricalReplayProvider(manifest_path),
    )

    metadata = service._try_fill_daily_data(
        code="AAPL",
        analysis_date=date(2024, 1, 2),
        eval_window_days=1,
    )

    assert metadata is not None
    assert metadata.resolved_source == "DevelopmentHistoricalReplay"
    assert metadata.fallback_used is False
    authority = assess_backtest_data_source_eligibility(code="AAPL", source="development_historical_replay")
    assert authority.authority_status == "degraded_fill_only"
    assert authority.authority_allowed is False
    assert authority.degraded_fill_only is True
    assert authority.reason_codes == ("development_replay_not_production_authoritative",)
    rows = service._load_stock_daily_rows("AAPL")
    assert [row.data_source for row in rows] == ["development_historical_replay"] * 2
    assert [row.close for row in rows] == [Decimal("10.5000"), Decimal("11.5000")]
    mixed_sources = ["database_cache", "development_historical_replay"]
    mixed_quality = service._standard_result_data_quality(
        code="AAPL",
        analysis_date=date(2024, 1, 2),
        eval_window_days=1,
        market_data_sources=mixed_sources,
    )
    assert mixed_quality["source"] == "mixed"
    assert mixed_quality["sources"] == mixed_sources
    assert mixed_quality["authority_status"] == "degraded_fill_only"
    assert mixed_quality["authority_reason_codes"] == ["development_replay_not_production_authoritative"]
    data_basis = service._standard_result_data_basis(
        code="AAPL",
        rows=rows,
        analysis_date=date(2024, 1, 2),
        eval_window_days=1,
    )
    mixed_manifest = service._standard_result_reproducibility_manifest(
        code="AAPL",
        rows=rows,
        data_basis=data_basis,
        market_data_sources=mixed_sources,
        evaluated_at=None,
    )
    assert mixed_manifest["dataset_lineage"]["source_lineage"]["source"] == "mixed"
    assert mixed_manifest["dataset_lineage"]["source_lineage"]["sources"] == mixed_sources
    assert mixed_manifest["dataset_lineage"]["source_lineage"]["authority_status"] == "degraded_fill_only"
    empty_quality = service._standard_result_data_quality(
        code="AAPL",
        analysis_date=date(2024, 1, 2),
        eval_window_days=1,
        market_data_sources=[],
    )
    assert empty_quality["source"] == "database_cache"
    assert empty_quality["sources"] == []
    assert empty_quality["authority_status"] == "allowed"
    readiness = service._build_historical_ohlcv_readiness(
        code="AAPL",
        rows=rows,
        required_bars=1,
        allow_runtime_probe=False,
    )
    assert readiness["freshnessState"] == "stale"
    assert "stale_data" in readiness["missingRequirements"]


def test_scanner_loads_explicit_replay_after_local_us_cache_selection(tmp_path) -> None:
    manifest_path, _, _ = _write_manifest(
        tmp_path,
        _payload(
            market="US",
            symbol="AAPL",
            canonical_symbol="AAPL",
            provider="stooq_archive",
            source="stooq_historical",
            rows=_daily_rows(count=260),
        ),
    )
    db = DatabaseManager(db_url="sqlite:///:memory:")
    with (
        patch.dict(
            os.environ,
            {
                DEVELOPMENT_HISTORICAL_REPLAY_MANIFEST_ENV: str(manifest_path),
                "LOCAL_US_PARQUET_DIR": "",
                "US_STOCK_PARQUET_DIR": "",
                "WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED": "",
            },
            clear=False,
        ),
        patch(
            "src.services.market_scanner_service.get_config",
            return_value=SimpleNamespace(scanner_local_universe_path=str(tmp_path / "scanner-universe.csv")),
        ),
    ):
        service = MarketScannerService(db, data_manager=object())
        history, diagnostics = service._load_history_from_ohlcv_provider(
            code="AAPL",
            profile=get_scanner_profile(market="us"),
        )

    assert not history.empty, diagnostics
    assert diagnostics["source"] == "development_historical_replay"
    assert diagnostics["network_used"] is False
    assert diagnostics["stale"] is True
    assert diagnostics["observationOnly"] is True
    assert diagnostics["historicalOhlcvReadiness"]["freshnessState"] == "stale"

    candidate = {
        "symbol": "AAPL",
        "score": 83.6,
        "ret_5d": 4.1,
        "ret_20d": 12.7,
        "avg_amount_20": 1.2e10,
        "amount": 1.1e10,
        "atr20_pct": 3.7,
        "_relative_strength_pct": 0.81,
        "_component_scores": {"trend": 18.0},
        "_diagnostics": {
            "history": diagnostics,
            "quote_context": {"available": True, "source": "polygon_us_grouped_daily"},
            "factorEvidence": {"rankingEligible": True, "blockers": []},
        },
    }
    service._apply_score_caps_and_explainability(candidate)
    score_confidence = candidate["_diagnostics"]["score_explainability"]["source_confidence"]
    assert candidate["score"] == 60.0
    assert score_confidence["isStale"] is True
    assert score_confidence["sourceAuthorityAllowed"] is False
    assert score_confidence["scoreContributionAllowed"] is False
    assert score_confidence["observationOnly"] is True


def test_scanner_default_us_universe_uses_verified_replay_only_without_local_coverage(tmp_path, request) -> None:
    expected_symbols = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"]
    replay_rows = _daily_rows(count=540)
    for row in replay_rows:
        row["volume"] = 2_000_000
    manifest_path, _, _ = _write_manifest_observations(
        tmp_path,
        [
            _payload(
                market="US",
                symbol=symbol,
                canonical_symbol=symbol,
                provider="stooq_archive",
                source="stooq_historical",
                rows=replay_rows,
            )
            for symbol in expected_symbols
        ],
    )
    DatabaseManager.reset_instance()
    request.addfinalizer(DatabaseManager.reset_instance)
    db = DatabaseManager(db_url=f"sqlite:///{tmp_path / 'scanner-backtest.sqlite'}")
    data_manager = Mock()
    cutoff = date(2024, 12, 31)

    with (
        patch.dict(
            os.environ,
            {
                DEVELOPMENT_HISTORICAL_REPLAY_MANIFEST_ENV: str(manifest_path),
                "LOCAL_US_PARQUET_DIR": "",
                "US_STOCK_PARQUET_DIR": "",
                "WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED": "",
            },
            clear=False,
        ),
        patch(
            "src.services.market_scanner_service.get_config",
            return_value=SimpleNamespace(scanner_local_universe_path=str(tmp_path / "scanner-universe.csv")),
        ),
        patch.object(MarketScannerService, "_load_local_us_universe_from_parquet", return_value=[]),
        patch(
            "src.services.rule_backtest_service.fetch_daily_history_with_local_us_fallback",
            return_value=(pd.DataFrame(), "unavailable"),
        ) as local_history_fetch,
    ):
        first_scan = MarketScannerService(db, data_manager=data_manager).run_scan(
            market="us",
            profile="us_historical_research_v1",
            scope="system",
            evaluation_mode="historical_development",
            evaluation_cutoff=cutoff,
        )

        backtest = RuleBacktestService(db).run_backtest(
            code="SPY",
            strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            start_date="2024-01-02",
            end_date=cutoff,
            lookback_bars=180,
            benchmark_mode="auto",
            confirmed=True,
        )
        cached_symbols = sorted(RuleBacktestService(db).stock_repo.list_distinct_codes())

        second_scan = MarketScannerService(db, data_manager=data_manager).run_scan(
            market="us",
            profile="us_historical_research_v1",
            scope="system",
            evaluation_mode="historical_development",
            evaluation_cutoff=cutoff,
        )
        current_resolution = MarketScannerService(db, data_manager=data_manager)._resolve_us_stock_universe(
            profile=get_scanner_profile(market="us"),
            allow_development_replay=False,
        )

    first_resolution = first_scan["diagnostics"]["scanner_data"]["universe_resolution"]
    second_resolution = second_scan["diagnostics"]["scanner_data"]["universe_resolution"]
    assert first_resolution["resolvedStarterSymbols"] == expected_symbols
    assert first_scan["scannerLineage"]["universeSymbols"] == expected_symbols
    assert first_resolution["local_symbol_count"] == 0
    assert first_resolution["development_replay_symbol_count"] == 5
    assert backtest["status"] == "completed"
    assert backtest["benchmark_summary"]["code"] == "QQQ"
    assert backtest["benchmark_summary"]["resolved_mode"] == "etf_qqq"
    assert cached_symbols == ["QQQ", "SPY"]
    assert second_resolution["resolvedStarterSymbols"] == expected_symbols
    assert second_scan["scannerLineage"]["universeSymbols"] == expected_symbols
    assert second_resolution["source"] == "local_db_us_history+development_historical_replay_manifest"
    assert second_resolution["local_symbol_count"] == 2
    assert second_resolution["development_replay_symbol_count"] == 3
    assert second_resolution["universeSource"] == "development_historical_replay"
    assert second_resolution["noExternalCalls"] is True
    assert second_resolution["providerCallsEnabled"] is False
    replay_attempt = second_resolution["attempts"][-1]
    assert replay_attempt == {
        "fetcher": "development_historical_replay_manifest",
        "status": "success",
        "rows": 5,
        "added_rows": 3,
        "historical": True,
        "replay": True,
        "development": True,
        "authority": False,
        "productionEligible": False,
        "observationOnly": True,
        "noExternalCalls": True,
    }
    assert {
        symbol: second_scan["diagnostics"]["candidate_diagnostics"][symbol]["status"]
        for symbol in ("AAPL", "MSFT", "NVDA")
    } == {"AAPL": "evaluated", "MSFT": "evaluated", "NVDA": "evaluated"}
    assert second_scan["diagnostics"]["candidate_diagnostics"]["SPY"]["status"] == "skipped"
    assert second_scan["diagnostics"]["candidate_diagnostics"]["SPY"]["reason"] == "benchmark_symbol_skipped"
    assert data_manager.get_realtime_quote.call_count == 0
    assert [call.args[0] for call in local_history_fetch.call_args_list] == ["SPY", "QQQ"]
    assert all(call.kwargs["allow_provider_fallback"] is False for call in local_history_fetch.call_args_list)
    assert current_resolution["resolvedStarterSymbols"] == ["SPY", "QQQ"]
    assert current_resolution["universeSource"] == "bounded_starter_market_data_spine"
    assert all(
        attempt["fetcher"] != "development_historical_replay_manifest"
        for attempt in current_resolution["attempts"]
    )


def test_rule_backtest_persists_verified_replay_for_instrument_and_benchmark_without_provider_fallback(tmp_path) -> None:
    manifest_path, _, _ = _write_manifest_observations(
        tmp_path,
        [
            _payload(
                market="US",
                symbol="AAPL",
                canonical_symbol="AAPL",
                provider="stooq_archive",
                source="stooq_historical",
                rows=_daily_rows(count=540),
            ),
            _payload(
                market="US",
                symbol="SPY",
                canonical_symbol="SPY",
                provider="stooq_archive",
                source="stooq_historical",
                rows=_daily_rows(count=540),
            ),
        ],
    )
    db = DatabaseManager(db_url="sqlite:///:memory:")
    service = RuleBacktestService(db)

    with patch.dict(os.environ, {DEVELOPMENT_HISTORICAL_REPLAY_MANIFEST_ENV: str(manifest_path)}, clear=False):
        response = service.run_backtest(
            code="AAPL",
            strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            start_date="2024-01-02",
            end_date=date(2024, 12, 31),
            lookback_bars=180,
            benchmark_mode="custom_code",
            benchmark_code="SPY",
            confirmed=True,
        )

    aapl_stored = service.stock_repo.get_range("AAPL", date(2023, 9, 1), date(2024, 12, 31))
    spy_stored = service.stock_repo.get_range("SPY", date(2023, 9, 1), date(2024, 12, 31))
    assert response["status"] == "completed"
    assert response["data_quality"]["source"] == "development_historical_replay"
    assert response["data_quality"]["expected_bar_count"] == 252
    assert response["data_quality"]["missing_bar_count"] == 0
    assert response["professionalReadiness"]["provider_calls"] is False
    assert aapl_stored and spy_stored
    assert {row.data_source for row in aapl_stored} == {"development_historical_replay"}
    assert {row.data_source for row in spy_stored} == {"development_historical_replay"}


def test_historical_mode_cannot_reuse_preopen_profile() -> None:
    service = MarketScannerService(DatabaseManager(db_url="sqlite:///:memory:"), data_manager=object())
    with pytest.raises(ValueError, match="us_preopen_v1 requires evaluation_mode=current"):
        service.run_scan(
            market="us",
            profile="us_preopen_v1",
            evaluation_mode="historical_development",
            evaluation_cutoff=date(2024, 12, 31),
        )


def test_historical_profile_requires_historical_mode_and_cutoff() -> None:
    service = MarketScannerService(DatabaseManager(db_url="sqlite:///:memory:"), data_manager=object())
    with pytest.raises(ValueError, match="us_historical_research_v1 requires evaluation_mode=historical_development"):
        service.run_scan(
            market="us",
            profile="us_historical_research_v1",
            evaluation_mode="current",
        )


def test_research_radar_preserves_historical_scanner_lineage_and_temporal_boundary() -> None:
    run = SimpleNamespace(
        id=7,
        market="us",
        profile="us_historical_research_v1",
        diagnostics_json=json.dumps(
            {
                "evaluationMode": "historical_development",
                "evaluationCutoff": "2024-12-31",
                "scannerLineage": {
                    "source": "development_historical_replay",
                    "universeMode": "bounded_starter_local",
                    "universeSymbols": ["AAPL"],
                    "generatedAt": "2026-09-01T00:00:00",
                    "symbolsEvaluated": ["AAPL"],
                    "symbolsSkipped": [],
                },
            }
        ),
    )
    lineage = _scanner_lineage_from_run(run, market="us")
    assert lineage["profile"] == "us_historical_research_v1"
    assert lineage["evaluationMode"] == "historical_development"
    assert lineage["evaluationCutoff"] == "2024-12-31"
