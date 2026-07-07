from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from src.repositories.quote_ohlcv_snapshot_repository import QuoteOhlcvSnapshotRepository
from src.services.historical_ohlcv_readiness import HistoricalOhlcvBar
from src.services.provider_capability_matrix import providers_for_domain, ProviderDomain
from src.services.quote_ohlcv_snapshot_lineage import (
    QUOTE_OHLCV_SNAPSHOT_CONTRACT_VERSION,
    QuoteOhlcvSnapshotSpine,
    SnapshotLineageError,
    build_ohlcv_snapshot_from_bar,
    build_quote_snapshot_from_readiness,
)
from src.services.quote_snapshot_readiness import QuoteSnapshot
from src.storage import DatabaseManager, QuoteOhlcvSnapshotRow


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _db(tmp_path: Path) -> DatabaseManager:
    return DatabaseManager(db_url=f"sqlite:///{tmp_path / 'snapshots.db'}")


def _repo(tmp_path: Path) -> QuoteOhlcvSnapshotRepository:
    return QuoteOhlcvSnapshotRepository(_db(tmp_path))


def _quote_snapshot():
    return build_quote_snapshot_from_readiness(
        QuoteSnapshot(
            symbol="aapl",
            market="us",
            last=214.55,
            previous_close=212.2,
            volume=1_000_000,
            currency="usd",
            as_of=_dt("2026-07-06T20:00:00Z"),
            source="local_quote_snapshot_cache",
        ),
        retrieval_time=_dt("2026-07-06T20:01:00Z"),
        authority_state="advisory_only",
        display_state="limited",
        freshness_state="cached",
        coverage_state="available",
        lineage_ref="quote-cache:2026-07-06:AAPL",
    )


@pytest.fixture(autouse=True)
def _reset_database_manager():
    DatabaseManager.reset_instance()
    yield
    DatabaseManager.reset_instance()


def test_quote_snapshot_contract_persists_explicit_lineage_without_provider_order_change(tmp_path) -> None:
    provider_order_before = [item.provider_id for item in providers_for_domain(ProviderDomain.QUOTE)]
    spine = QuoteOhlcvSnapshotSpine(_repo(tmp_path))

    snapshot = _quote_snapshot()

    result = spine.persist_snapshot(snapshot)
    loaded = spine.get_snapshot(result.snapshot_id)

    assert result.inserted is True
    assert loaded is not None
    payload = loaded.as_read_model()
    assert payload["contractVersion"] == QUOTE_OHLCV_SNAPSHOT_CONTRACT_VERSION
    assert payload["snapshotId"] == result.snapshot_id
    assert payload["symbol"] == "AAPL"
    assert payload["market"] == "US"
    assert payload["instrumentIdentity"]["canonicalSymbol"] == "AAPL"
    assert payload["quoteAsOf"] == "2026-07-06T20:00:00+00:00"
    assert payload["retrievalTime"] == "2026-07-06T20:01:00+00:00"
    assert payload["sourceId"] == "local_quote_snapshot_cache"
    assert payload["sourceType"] == "cache_snapshot"
    assert payload["authorityState"] == "advisory_only"
    assert payload["displayState"] == "limited"
    assert payload["freshnessState"] == "cached"
    assert payload["coverageState"] == "available"
    assert payload["missingFieldSummary"] == []
    assert payload["ohlcvBasis"] is None
    assert payload["lineageRef"] == "quote-cache:2026-07-06:AAPL"
    assert [item.provider_id for item in providers_for_domain(ProviderDomain.QUOTE)] == provider_order_before


def test_quote_snapshot_contract_preserves_missing_field_summary_and_latest_read(tmp_path) -> None:
    repo = _repo(tmp_path)
    spine = QuoteOhlcvSnapshotSpine(repo)

    snapshot = build_quote_snapshot_from_readiness(
        QuoteSnapshot(
            symbol="AAPL",
            market="US",
            last=214.55,
            as_of=_dt("2026-07-06T20:00:00Z"),
            source="local_quote_snapshot_cache",
        ),
        retrieval_time=_dt("2026-07-06T20:01:00Z"),
        authority_state="advisory_only",
        display_state="limited",
        freshness_state="cached",
        coverage_state="partial",
        missing_field_summary=("previous_close", "volume", "currency"),
        lineage_ref="quote-cache:2026-07-06:AAPL",
    )

    spine.persist_snapshot(snapshot)
    latest = spine.latest_for_symbol(symbol="AAPL", market="US", snapshot_kind="quote")

    assert latest is not None
    assert latest.snapshot_id == snapshot.snapshot_id
    payload = latest.as_read_model()
    assert payload["coverageState"] == "partial"
    assert payload["missingFieldSummary"] == ["previous_close", "volume", "currency"]


def test_latest_for_symbol_orders_by_retrieval_time(tmp_path) -> None:
    repo = _repo(tmp_path)
    early = _quote_snapshot()
    later = build_quote_snapshot_from_readiness(
        QuoteSnapshot(
            symbol="AAPL",
            market="US",
            last=215.25,
            as_of=_dt("2026-07-06T20:00:00Z"),
            source="local_quote_snapshot_cache",
        ),
        retrieval_time=_dt("2026-07-06T20:05:00Z"),
        authority_state="advisory_only",
        display_state="limited",
        freshness_state="cached",
        coverage_state="partial",
        lineage_ref="quote-cache:2026-07-06:AAPL:late",
    )

    repo.upsert_snapshot(later)
    repo.upsert_snapshot(early)

    latest = repo.latest_for_symbol(symbol="AAPL", market="US", snapshot_kind="quote")

    assert latest is not None
    assert latest.snapshot_id == later.snapshot_id
    assert latest.retrieval_time == _dt("2026-07-06T20:05:00Z")


def test_restart_persistence_reads_database_manager_owned_snapshot(tmp_path) -> None:
    db_path = tmp_path / "snapshots.db"
    db = DatabaseManager(db_url=f"sqlite:///{db_path}")
    repo = QuoteOhlcvSnapshotRepository(db)
    snapshot = _quote_snapshot()

    repo.upsert_snapshot(snapshot)
    DatabaseManager.reset_instance()

    restarted_db = DatabaseManager(db_url=f"sqlite:///{db_path}")
    restarted_repo = QuoteOhlcvSnapshotRepository(restarted_db)
    loaded = restarted_repo.get_snapshot(snapshot.snapshot_id)

    assert loaded is not None
    assert loaded.snapshot_id == snapshot.snapshot_id
    assert loaded.lineage_ref == "quote-cache:2026-07-06:AAPL"


@pytest.mark.parametrize(
    ("symbol", "market", "expected_symbol", "expected_market", "expected_venue"),
    [
        ("AAPL", "US", "AAPL", "US", "XNYS"),
        ("SH600519", "CN", "600519", "CN", "XSHG"),
        ("hk00700", "HK", "00700", "HK", "XHKG"),
    ],
)
def test_ohlcv_snapshot_contract_normalizes_cross_market_identity(
    tmp_path,
    symbol: str,
    market: str,
    expected_symbol: str,
    expected_market: str,
    expected_venue: str,
) -> None:
    spine = QuoteOhlcvSnapshotSpine(_repo(tmp_path))
    bar = HistoricalOhlcvBar(
        date=date(2026, 7, 6),
        open=10.0,
        high=11.0,
        low=9.5,
        close=10.5,
        volume=1000.0,
        adjusted_close=10.4,
    )

    snapshot = build_ohlcv_snapshot_from_bar(
        symbol=symbol,
        market=market,
        bar=bar,
        retrieval_time=_dt("2026-07-06T21:00:00Z"),
        source_id="local_ohlcv",
        authority_state="advisory_only",
        display_state="limited",
        freshness_state="fresh",
        coverage_state="available",
        lineage_ref=f"local-ohlcv:{expected_market}:{expected_symbol}:2026-07-06",
    )

    persisted = spine.persist_snapshot(snapshot)
    loaded = spine.get_snapshot(persisted.snapshot_id)

    assert loaded is not None
    payload = loaded.as_read_model()
    assert payload["symbol"] == expected_symbol
    assert payload["market"] == expected_market
    assert payload["instrumentIdentity"] == {
        "canonicalSymbol": expected_symbol,
        "market": expected_market,
        "venue": expected_venue,
    }
    assert payload["barTradeDateTime"] == "2026-07-06"
    assert payload["retrievalTime"] == "2026-07-06T21:00:00+00:00"
    assert payload["sourceId"] == "local_ohlcv"
    assert payload["sourceType"] == "cache_snapshot"
    assert payload["ohlcvBasis"] == "adjusted"
    assert payload["missingFieldSummary"] == []


@pytest.mark.parametrize(
    "missing_kwargs",
    [
        {"lineage_ref": ""},
        {"source_id": ""},
        {"authority_state": ""},
        {"freshness_state": ""},
        {"coverage_state": ""},
    ],
)
def test_snapshot_contract_fails_closed_when_required_provenance_is_missing(missing_kwargs) -> None:
    kwargs = {
        "symbol": "AAPL",
        "market": "US",
        "bar": HistoricalOhlcvBar(
            date=date(2026, 7, 6),
            open=10.0,
            high=11.0,
            low=9.5,
            close=10.5,
            volume=1000.0,
        ),
        "retrieval_time": _dt("2026-07-06T21:00:00Z"),
        "source_id": "local_ohlcv",
        "authority_state": "advisory_only",
        "display_state": "unavailable",
        "freshness_state": "fresh",
        "coverage_state": "available",
        "lineage_ref": "local-ohlcv:US:AAPL:2026-07-06",
    }
    kwargs.update(missing_kwargs)

    with pytest.raises(SnapshotLineageError):
        build_ohlcv_snapshot_from_bar(**kwargs)


def test_repository_constructor_requires_canonical_database_manager_without_creating_files(tmp_path) -> None:
    unmanaged_path = tmp_path / "unmanaged.sqlite"

    with pytest.raises(TypeError):
        QuoteOhlcvSnapshotRepository()  # type: ignore[call-arg]

    assert not unmanaged_path.exists()


def test_passive_reads_do_not_create_files_when_storage_is_unavailable(tmp_path) -> None:
    blocked_path = tmp_path / "blocked.sqlite"

    class _UnavailableDb:
        def get_session(self):
            raise RuntimeError("canonical storage unavailable")

    repo = QuoteOhlcvSnapshotRepository(_UnavailableDb())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="canonical storage unavailable"):
        repo.get_snapshot("missing")
    with pytest.raises(RuntimeError, match="canonical storage unavailable"):
        repo.latest_for_symbol(symbol="AAPL", market="US", snapshot_kind="quote")
    assert not blocked_path.exists()


def test_repository_construction_and_passive_reads_do_not_apply_schema(tmp_path) -> None:
    db_path = tmp_path / "passive.sqlite"
    engine = create_engine(f"sqlite:///{db_path}", pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = object.__new__(DatabaseManager)
    db._engine = engine
    db._SessionLocal = session_factory
    db._initialized = True

    repo = QuoteOhlcvSnapshotRepository(db)

    assert "quote_ohlcv_snapshots" not in inspect(engine).get_table_names()
    with pytest.raises(Exception):
        repo.get_snapshot("missing")
    assert "quote_ohlcv_snapshots" not in inspect(engine).get_table_names()

    engine.dispose()


def test_database_manager_lifecycle_owns_snapshot_schema(tmp_path) -> None:
    db = _db(tmp_path)

    assert "quote_ohlcv_snapshots" in inspect(db._engine).get_table_names()
    repo = QuoteOhlcvSnapshotRepository(db)
    report = repo.migration_report()
    assert report["storageOwner"] == "DatabaseManager"
    assert report["schemaLifecycle"] == "SQLAlchemy Base.metadata.create_all"


def test_repository_rejects_direct_invalid_persistence_record(tmp_path) -> None:
    repo = _repo(tmp_path)
    snapshot = _quote_snapshot()
    invalid = type(snapshot)(
        snapshot_id=snapshot.snapshot_id,
        snapshot_kind=snapshot.snapshot_kind,
        symbol=snapshot.symbol,
        market=snapshot.market,
        instrument_identity=dict(snapshot.instrument_identity),
        quote_as_of=snapshot.quote_as_of,
        bar_trade_date_time=snapshot.bar_trade_date_time,
        retrieval_time=snapshot.retrieval_time,
        source_id="",
        source_type=snapshot.source_type,
        authority_state=snapshot.authority_state,
        display_state=snapshot.display_state,
        freshness_state=snapshot.freshness_state,
        coverage_state=snapshot.coverage_state,
        missing_field_summary=snapshot.missing_field_summary,
        ohlcv_basis=snapshot.ohlcv_basis,
        lineage_ref=snapshot.lineage_ref,
        values=dict(snapshot.values),
        contract_version=snapshot.contract_version,
    )

    with pytest.raises(SnapshotLineageError):
        repo.upsert_snapshot(invalid)


def test_repository_detects_snapshot_identity_content_conflict(tmp_path) -> None:
    repo = _repo(tmp_path)
    snapshot = _quote_snapshot()

    assert repo.upsert_snapshot(snapshot).inserted is True
    assert repo.upsert_snapshot(snapshot).inserted is False

    conflicting = type(snapshot)(
        snapshot_id=snapshot.snapshot_id,
        snapshot_kind=snapshot.snapshot_kind,
        symbol=snapshot.symbol,
        market=snapshot.market,
        instrument_identity=dict(snapshot.instrument_identity),
        quote_as_of=snapshot.quote_as_of,
        bar_trade_date_time=snapshot.bar_trade_date_time,
        retrieval_time=snapshot.retrieval_time,
        source_id=snapshot.source_id,
        source_type=snapshot.source_type,
        authority_state=snapshot.authority_state,
        display_state=snapshot.display_state,
        freshness_state="stale",
        coverage_state=snapshot.coverage_state,
        missing_field_summary=snapshot.missing_field_summary,
        ohlcv_basis=snapshot.ohlcv_basis,
        lineage_ref=snapshot.lineage_ref,
        values=dict(snapshot.values),
        contract_version=snapshot.contract_version,
    )

    with pytest.raises(SnapshotLineageError, match="identity conflict"):
        repo.upsert_snapshot(conflicting)


@pytest.mark.parametrize(
    "payload_patch",
    [
        {"payload_json": "not-json"},
        {"payload_json": json.dumps({"snapshotId": "bad"}, sort_keys=True)},
    ],
)
def test_repository_fails_closed_for_corrupt_persisted_rows(tmp_path, payload_patch) -> None:
    db = _db(tmp_path)
    repo = QuoteOhlcvSnapshotRepository(db)
    snapshot = _quote_snapshot()
    repo.upsert_snapshot(snapshot)

    with db.session_scope() as session:
        row = session.get(QuoteOhlcvSnapshotRow, snapshot.snapshot_id)
        for key, value in payload_patch.items():
            setattr(row, key, value)

    with pytest.raises(SnapshotLineageError):
        repo.get_snapshot(snapshot.snapshot_id)


def test_failed_write_rolls_back_without_partial_row(tmp_path) -> None:
    db = _db(tmp_path)
    repo = QuoteOhlcvSnapshotRepository(db)
    snapshot = _quote_snapshot()
    original_session_scope = db.session_scope

    def failing_session_scope():
        context = original_session_scope()
        session = context.__enter__()
        def fail_commit():
            raise RuntimeError("forced commit failure")

        session.commit = fail_commit

        class _FailingContext:
            def __enter__(self):
                return session

            def __exit__(self, exc_type, exc, tb):
                return context.__exit__(exc_type, exc, tb)

        return _FailingContext()

    db.session_scope = failing_session_scope
    with pytest.raises(RuntimeError):
        repo.upsert_snapshot(snapshot)

    db.session_scope = original_session_scope
    assert repo.get_snapshot(snapshot.snapshot_id) is None
