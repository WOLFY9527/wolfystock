# -*- coding: utf-8 -*-
"""Integration evidence for durable observation through real circuit owners."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from data_provider.realtime_types import CircuitBreaker
from src.services.analysis_provider_planner import (
    AnalysisProviderExecutor,
    CategoryProviderPlan,
    DataCategory,
    ProviderTimeout,
)
from src.services.provider_circuit_observer import ProviderCircuitObserver
from src.storage import (
    DatabaseManager,
    ProviderCircuitEvent,
    ProviderProbeEvent,
    ProviderQuotaWindow,
)


@pytest.fixture
def circuit_db():
    DatabaseManager.reset_instance()
    with tempfile.TemporaryDirectory() as temp_dir:
        db = DatabaseManager(db_url=f"sqlite:///{Path(temp_dir) / 'runtime-circuit.db'}")
        yield db
    DatabaseManager.reset_instance()


def _quote_plan(*providers: str) -> CategoryProviderPlan:
    return CategoryProviderPlan(
        category=DataCategory.QUOTE,
        providers=list(providers),
        timeout_seconds=0.1,
        cache_ttl_seconds=60,
        max_attempts=len(providers),
    )


def _counts(db: DatabaseManager) -> tuple[int, int, int]:
    with db.get_session() as session:
        return (
            session.query(ProviderCircuitEvent).count(),
            session.query(ProviderProbeEvent).count(),
            session.query(ProviderQuotaWindow).count(),
        )


def test_planner_runtime_open_half_open_recovery_and_probe_truth(circuit_db: DatabaseManager) -> None:
    observer = ProviderCircuitObserver(db=circuit_db)
    executor = AnalysisProviderExecutor(
        failure_threshold=1,
        cooldown_seconds=60,
        circuit_observer=observer.record_runtime_observation,
    )
    plan = _quote_plan("primary")

    failed = executor.execute_category(
        plan,
        symbol="ORCL",
        providers={"primary": lambda: (_ for _ in ()).throw(ProviderTimeout("bounded fixture"))},
    )

    assert failed.source_provider is None
    state = circuit_db.get_provider_circuit_state(
        provider="primary",
        provider_category="quote",
        route_family="analysis_provider_executor",
    )
    assert state is not None
    assert state["state"] == "open"
    assert state["reason_bucket"] == "timeout"
    assert _counts(circuit_db) == (1, 0, 1)

    executor._circuits["primary:quote"].opened_at -= 61
    assert executor._is_circuit_open("primary", DataCategory.QUOTE) is False
    assert executor._circuits["primary:quote"].half_open is True
    assert _counts(circuit_db) == (2, 0, 1)

    recovered = executor.execute_category(
        plan,
        symbol="ORCL",
        providers={"primary": lambda: {"price": 101}},
    )

    assert recovered.source_provider == "primary"
    state = circuit_db.get_provider_circuit_state(
        provider="primary",
        provider_category="quote",
        route_family="analysis_provider_executor",
    )
    assert state is not None
    assert state["state"] == "closed"
    assert state["reason_bucket"] == "recovered"
    assert _counts(circuit_db) == (3, 1, 1)
    with circuit_db.get_session() as session:
        probe = session.query(ProviderProbeEvent).one()
        assert probe.probe_type == "half_open_request"
        assert probe.probe_source == "analysis_provider_planner"
        assert probe.result_bucket == "success"


def test_planner_success_without_transition_and_observer_failure_preserve_decisions(
    circuit_db: DatabaseManager,
) -> None:
    observer = ProviderCircuitObserver(db=circuit_db)
    successful = AnalysisProviderExecutor(circuit_observer=observer.record_runtime_observation)
    calls: list[str] = []

    result = successful.execute_category(
        _quote_plan("primary", "fallback"),
        symbol="ORCL",
        providers={
            "primary": lambda: calls.append("primary") or {"price": 100},
            "fallback": lambda: calls.append("fallback") or {"price": 101},
        },
    )

    assert result.source_provider == "primary"
    assert result.is_fallback is False
    assert calls == ["primary"]
    assert _counts(circuit_db) == (0, 0, 1)

    def unavailable_observer(**_facts):
        raise RuntimeError("deterministic observation outage")

    fail_open = AnalysisProviderExecutor(
        failure_threshold=1,
        cooldown_seconds=60,
        circuit_observer=unavailable_observer,
    )
    calls.clear()
    result = fail_open.execute_category(
        _quote_plan("primary", "fallback"),
        symbol="ORCL",
        providers={
            "primary": lambda: calls.append("primary") or (_ for _ in ()).throw(ProviderTimeout("slow")),
            "fallback": lambda: calls.append("fallback") or {"price": 101},
        },
    )

    assert result.source_provider == "fallback"
    assert result.is_fallback is True
    assert calls == ["primary", "fallback"]
    assert fail_open._is_circuit_open("primary", DataCategory.QUOTE) is True


def test_realtime_breaker_runtime_transition_dedup_and_probe_truth(circuit_db: DatabaseManager) -> None:
    observer = ProviderCircuitObserver(db=circuit_db)
    breaker = CircuitBreaker(
        failure_threshold=2,
        cooldown_seconds=10,
        half_open_max_calls=1,
        provider_category="realtime_quote",
        route_family="data_provider_realtime",
        circuit_observer=observer.record_runtime_observation,
    )

    with patch("data_provider.realtime_types.time.time", return_value=1000.0):
        breaker.record_failure("akshare_sina", "HTTP 503")
        assert _counts(circuit_db) == (0, 0, 1)
        breaker.record_failure("akshare_sina", "HTTP 503")
        assert breaker.get_status()["akshare_sina"] == "open"
        assert _counts(circuit_db) == (1, 0, 1)
        breaker.record_failure("akshare_sina", "HTTP 503")
        assert _counts(circuit_db) == (1, 0, 1)
        assert breaker.is_available("akshare_sina") is False

    with patch("data_provider.realtime_types.time.time", return_value=1011.0):
        assert breaker.is_available("akshare_sina") is True
        assert breaker.get_status()["akshare_sina"] == "half_open"
        assert _counts(circuit_db) == (2, 0, 1)
        breaker.record_success("akshare_sina")

    assert breaker.get_status()["akshare_sina"] == "closed"
    assert _counts(circuit_db) == (3, 1, 1)
    with circuit_db.get_session() as session:
        window = session.query(ProviderQuotaWindow).one()
        assert window.request_count == 4
        assert window.failure_count == 3
        assert window.success_count == 1
        assert window.probe_count == 1
        assert session.query(ProviderCircuitEvent).filter_by(from_state="open", to_state="open").count() == 0


def test_realtime_observer_failure_cannot_change_breaker_outcome() -> None:
    def unavailable_observer(**_facts):
        raise RuntimeError("deterministic observation outage")

    breaker = CircuitBreaker(
        failure_threshold=1,
        cooldown_seconds=60,
        circuit_observer=unavailable_observer,
    )

    breaker.record_failure("akshare_sina", "timeout")

    assert breaker.get_status()["akshare_sina"] == "open"
    assert breaker.is_available("akshare_sina") is False
