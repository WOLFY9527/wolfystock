"""Focused offline contracts for normalized Quote, History and Macro ports."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from data_provider.base import DataFetcherManager
from data_provider.realtime_types import RealtimeSource, UnifiedRealtimeQuote
from src.contracts.evidence import (
    ObservationFreshness,
    RawAvailability,
    SourceClass,
    SourceIdentity,
    SourceObservationFacts,
)
from src.providers import (
    ProviderCacheIdentity,
    ProviderCapability,
    ProviderDataResult,
    ProviderDataState,
    ProviderReason,
)
from src.providers.ports import (
    HistoryBar,
    HistoryData,
    HistoryPort,
    HistoryRequest,
    MacroData,
    MacroPort,
    MacroRequest,
    QuoteData,
    QuotePort,
    QuoteRequest,
    provider_error_result_from_exception,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _facts(
    *,
    availability: RawAvailability = RawAvailability.AVAILABLE,
    freshness: ObservationFreshness = ObservationFreshness.LIVE,
    source_id: str = "licensed_quotes",
    source_class: SourceClass = SourceClass.LICENSED,
    is_proxy: bool = False,
    is_synthetic: bool = False,
    is_fixture: bool = False,
    is_cached: bool = False,
) -> SourceObservationFacts:
    return SourceObservationFacts(
        identity=SourceIdentity(
            source_id=source_id,
            source_class=source_class,
            is_proxy=is_proxy,
            is_synthetic=is_synthetic,
            is_fixture=is_fixture,
        ),
        observed_at=datetime(2026, 7, 17, 1, 2, 3, tzinfo=timezone.utc),
        as_of=datetime(2026, 7, 17, 1, 0, 0, tzinfo=timezone.utc),
        raw_availability=availability,
        freshness=freshness,
        is_cached=is_cached,
    )


def test_quote_port_preserves_success_empty_zero_missing_and_unavailable() -> None:
    facts = _facts()
    quote = QuoteData(symbol="AAPL", price=0.0, volume=0)

    observed = ProviderDataResult.observed(ProviderCapability.QUOTE, quote, facts)
    empty = ProviderDataResult.authoritative_empty(ProviderCapability.QUOTE, facts)
    missing = ProviderDataResult.missing(
        ProviderCapability.QUOTE,
        _facts(availability=RawAvailability.MISSING, freshness=ObservationFreshness.UNKNOWN),
    )
    unavailable = ProviderDataResult.unavailable(
        ProviderCapability.QUOTE,
        _facts(availability=RawAvailability.UNAVAILABLE, freshness=ObservationFreshness.UNKNOWN),
        reason=ProviderReason.NOT_CONFIGURED,
    )

    assert observed.state is ProviderDataState.OBSERVED
    assert observed.data is quote
    assert observed.data.price == 0.0
    assert observed.data.volume == 0
    assert empty.state is ProviderDataState.EMPTY and empty.data is None
    assert missing.state is ProviderDataState.MISSING and missing.data is None
    assert unavailable.state is ProviderDataState.UNAVAILABLE and unavailable.data is None
    assert unavailable.reason is ProviderReason.NOT_CONFIGURED
    assert len({item.state for item in (observed, empty, missing, unavailable)}) == 4


def test_quote_transport_adapter_returns_immutable_data_without_reclassifying_facts() -> None:
    facts = _facts(freshness=ObservationFreshness.DELAYED)
    transport = UnifiedRealtimeQuote(
        code="AAPL",
        name="Apple",
        source=RealtimeSource.YFINANCE,
        price=187.25,
        change_pct=0.0,
        volume=0,
        market_timestamp="2026-07-17T01:00:00Z",
    )

    result = transport.to_provider_data_result(facts)

    assert result.facts is facts
    assert result.data == QuoteData(
        symbol="AAPL",
        name="Apple",
        price=187.25,
        change_pct=0.0,
        volume=0,
    )
    assert not hasattr(result.data, "source")
    assert not hasattr(result.data, "observed_at")
    with pytest.raises(FrozenInstanceError):
        result.data.price = 200.0  # type: ignore[misc]


def test_history_port_preserves_success_sparse_empty_stale_and_unavailable() -> None:
    sparse = HistoryData(
        symbol="AAPL",
        bars=(
            HistoryBar(period="2026-07-15", open=210.0, high=None, low=208.0, close=209.0, volume=None),
            HistoryBar(period="2026-07-16", open=209.0, high=212.0, low=None, close=211.0, volume=0),
        ),
    )
    success = ProviderDataResult.observed(ProviderCapability.HISTORY, sparse, _facts())
    stale = ProviderDataResult.observed(
        ProviderCapability.HISTORY,
        sparse,
        _facts(freshness=ObservationFreshness.STALE),
    )
    empty = ProviderDataResult.authoritative_empty(ProviderCapability.HISTORY, _facts())
    unavailable = ProviderDataResult.unavailable(
        ProviderCapability.HISTORY,
        _facts(availability=RawAvailability.UNAVAILABLE, freshness=ObservationFreshness.UNKNOWN),
        reason=ProviderReason.PROVIDER_UNHEALTHY,
    )

    assert success.data.bars[0].high is None
    assert success.data.bars[1].low is None
    assert success.data.bars[1].volume == 0
    assert stale.facts.freshness is ObservationFreshness.STALE
    assert empty.state is ProviderDataState.EMPTY and empty.data is None
    assert unavailable.state is ProviderDataState.UNAVAILABLE


def test_macro_port_preserves_delayed_proxy_cached_and_unavailable_facts() -> None:
    proxy_facts = _facts(
        freshness=ObservationFreshness.DELAYED,
        source_id="public_macro_proxy",
        source_class=SourceClass.THIRD_PARTY,
        is_proxy=True,
    )
    cached_facts = proxy_facts.as_cached(freshness=ObservationFreshness.STALE)
    cache_identity = ProviderCacheIdentity("macro:fred:DGS10")
    macro = MacroData(series_id="DGS10", value=0.0, unit="percent")

    delayed = ProviderDataResult.observed(ProviderCapability.MACRO, macro, proxy_facts)
    cached = ProviderDataResult.observed(
        ProviderCapability.MACRO,
        macro,
        cached_facts,
        cache_identity=cache_identity,
    )
    unavailable = ProviderDataResult.unavailable(
        ProviderCapability.MACRO,
        _facts(availability=RawAvailability.UNAVAILABLE, freshness=ObservationFreshness.UNKNOWN),
        reason=ProviderReason.TIMEOUT,
    )

    assert delayed.data.value == 0.0
    assert delayed.facts.identity.is_proxy is True
    assert delayed.facts.freshness is ObservationFreshness.DELAYED
    assert cached.facts.identity == proxy_facts.identity
    assert cached.facts.is_cached is True
    assert cached.cache_identity is cache_identity
    assert unavailable.state is ProviderDataState.UNAVAILABLE


def test_transport_error_is_classified_and_distinct_from_authoritative_empty() -> None:
    unavailable_facts = _facts(
        availability=RawAvailability.UNAVAILABLE,
        freshness=ObservationFreshness.UNKNOWN,
    )

    failed = provider_error_result_from_exception(
        TimeoutError("request timed out token=SECRET"),
        capability=ProviderCapability.MACRO,
        facts=unavailable_facts,
    )
    empty = ProviderDataResult.authoritative_empty(ProviderCapability.MACRO, _facts())

    assert failed.state is ProviderDataState.ERROR
    assert failed.reason is ProviderReason.TIMEOUT
    assert failed.data is None
    assert "SECRET" not in (failed.error_message or "")
    assert empty.state is ProviderDataState.EMPTY
    assert empty.reason is None and empty.error_message is None


def test_result_rejects_fact_upgrades_and_cache_identity_without_cached_fact() -> None:
    with pytest.raises(ValueError, match="observed result requires available facts"):
        ProviderDataResult.observed(
            ProviderCapability.QUOTE,
            QuoteData(symbol="AAPL", price=1.0),
            _facts(availability=RawAvailability.MISSING),
        )
    with pytest.raises(ValueError, match="missing result requires missing facts"):
        ProviderDataResult.missing(ProviderCapability.QUOTE, _facts())
    with pytest.raises(ValueError, match="cache identity requires cached facts"):
        ProviderDataResult.observed(
            ProviderCapability.MACRO,
            MacroData(series_id="DGS10", value=4.2),
            _facts(),
            cache_identity=ProviderCacheIdentity("macro:fred:DGS10"),
        )


@pytest.mark.parametrize(
    ("data", "loader"),
    [
        (QuoteData(symbol="AAPL", price=0.0, volume=0), QuoteData.from_dict),
        (
            HistoryData(symbol="AAPL", bars=(HistoryBar(period="2026-07-17", close=0.0),)),
            HistoryData.from_dict,
        ),
        (MacroData(series_id="DGS10", value=0.0, unit="percent"), MacroData.from_dict),
    ],
    ids=("quote", "history", "macro"),
)
def test_source_facts_survive_json_transport_to_port_round_trip(data: object, loader: object) -> None:
    facts = _facts(
        freshness=ObservationFreshness.STALE,
        source_id="port_fixture",
        source_class=SourceClass.UNKNOWN,
        is_synthetic=True,
        is_fixture=True,
        is_cached=True,
    )
    capability = {
        QuoteData: ProviderCapability.QUOTE,
        HistoryData: ProviderCapability.HISTORY,
        MacroData: ProviderCapability.MACRO,
    }[type(data)]
    result = ProviderDataResult.observed(
        capability,
        data,
        facts,
        cache_identity=ProviderCacheIdentity(f"fixture:{capability.value}"),
    )

    payload = json.loads(json.dumps(result.to_dict(data_serializer=lambda item: item.to_dict())))
    restored = ProviderDataResult.from_dict(payload, data_loader=loader)

    assert restored == result
    assert restored.facts == facts
    assert restored.facts.identity.is_fixture is True
    assert restored.facts.identity.is_synthetic is True
    assert restored.facts.observed_at == facts.observed_at
    assert restored.facts.as_of == facts.as_of


def test_port_protocols_are_narrow_and_request_values_are_immutable() -> None:
    quote_request = QuoteRequest(symbol="AAPL")
    history_request = HistoryRequest(symbol="AAPL", start="2026-07-01", end="2026-07-17", interval="1d")
    macro_request = MacroRequest(series_id="DGS10")

    assert set(QuotePort.__dict__) & {"fetch_quote"} == {"fetch_quote"}
    assert set(HistoryPort.__dict__) & {"fetch_history"} == {"fetch_history"}
    assert set(MacroPort.__dict__) & {"fetch_macro"} == {"fetch_macro"}
    for request in (quote_request, history_request, macro_request):
        field_name = next(iter(request.__dataclass_fields__))
        with pytest.raises(FrozenInstanceError):
            setattr(request, field_name, "changed")


def test_port_layer_has_one_result_authority_and_no_domain_policy() -> None:
    provider_files = sorted((REPO_ROOT / "src" / "providers").rglob("*.py"))
    result_definitions: list[Path] = []
    forbidden_imports = (
        "data_provider",
        "src.services.market_cache",
        "src.services.market_scanner_service",
        "src.services.rule_backtest_service",
        "src.services.portfolio",
        "pandas",
        "requests",
        "httpx",
    )
    for path in provider_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(isinstance(node, ast.ClassDef) and node.name == "ProviderDataResult" for node in ast.walk(tree)):
            result_definitions.append(path.relative_to(REPO_ROOT))
        if path.parent.name == "ports":
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
            assert not any(
                name == prefix or name.startswith(f"{prefix}.")
                for name in imported
                for prefix in forbidden_imports
            )

    assert result_definitions == [Path("src/providers/types.py")]
    port_text = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in sorted((REPO_ROOT / "src" / "providers" / "ports").rglob("*.py"))
    )
    for forbidden_term in ("readiness", "threshold", "score_contribution", "provider_order"):
        assert forbidden_term not in port_text


def test_existing_provider_manager_close_remains_idempotent() -> None:
    class CloseProbe:
        def __init__(self) -> None:
            self.calls = 0

        def close(self) -> None:
            self.calls += 1

    tickflow = CloseProbe()
    alpaca = CloseProbe()
    twelve_data = CloseProbe()
    manager = DataFetcherManager(fetchers=[])
    manager._tickflow_fetcher = tickflow
    manager._alpaca_fetcher = alpaca
    manager._twelve_data_fetcher = twelve_data

    manager.close()
    manager.close()

    assert (tickflow.calls, alpaca.calls, twelve_data.calls) == (1, 1, 1)
