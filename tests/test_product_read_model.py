from __future__ import annotations

from datetime import date

from src.repositories.historical_market_data_repo import HistoricalMarketDataRepository
from src.services.historical_market_data_foundation import HistoricalMarketDataFoundation


def test_product_read_state_aggregation_blocks_ready_parent_when_child_is_missing() -> None:
    from src.services.product_read_model import aggregate_product_readiness

    aggregate = aggregate_product_readiness(
        surface="Stock Research",
        children=[
            {"name": "quote", "state": "available", "critical": True},
            {"name": "history", "state": "no_evidence", "critical": True},
            {"name": "fundamentals", "state": "partial", "critical": False},
        ],
    )

    assert aggregate["state"] == "no_evidence"
    assert aggregate["ready"] is False
    assert aggregate["blockingChildren"] == ["history"]
    assert aggregate["criticalChildStates"]["history"] == "no_evidence"
    assert aggregate["contractVersion"] == "product_read_model_v1"


def test_historical_foundation_projects_canonical_coverage_freshness_and_provenance(tmp_path) -> None:
    from src.services.product_read_model import (
        product_read_model_from_historical_foundation,
    )

    foundation = HistoricalMarketDataFoundation(
        repository=HistoricalMarketDataRepository.sqlite(tmp_path / "history.db")
    )
    foundation.ingest_provider_payload(
        {
            "provider": "unit_fixture",
            "source": "unit_fixture",
            "market": "US",
            "symbol": "AAPL",
            "interval": "1d",
            "observedAt": "2026-01-07T21:05:00Z",
            "asOf": "2026-01-07T21:05:00Z",
            "adjusted": True,
            "rows": [
                {"Date": "2026-01-05", "Open": 10, "High": 11, "Low": 9, "Close": 10, "Volume": 1},
                {"Date": "2026-01-07", "Open": 11, "High": 12, "Low": 10, "Close": 11, "Volume": 2},
            ],
        }
    )

    read_model = product_read_model_from_historical_foundation(
        foundation,
        symbol="AAPL",
        market="US",
        interval="1d",
        required_bars=3,
        stale_after_days=5,
        as_of=date(2026, 1, 9),
    )

    assert read_model["state"] == "partial"
    assert read_model["ready"] is False
    assert read_model["coverage"]["state"] == "insufficient"
    assert read_model["coverage"]["barCount"] == 2
    assert read_model["freshness"]["state"] == "available"
    assert read_model["quality"]["state"] == "degraded"
    assert read_model["provenance"]["sourceClass"] == "historical_market_data"
    assert read_model["provenance"]["quality"] == "degraded"
    assert "provider" not in read_model["provenance"]
    assert "lineageId" not in read_model["provenance"]


def test_structure_confidence_boundary_hides_strong_classification_when_evidence_blocks() -> None:
    from src.services.product_read_model import build_structure_decision_product_read_model

    read_model = build_structure_decision_product_read_model(
        {
            "structureState": "breakout",
            "confidence": "high",
            "confidenceState": {
                "label": "low",
                "status": "evidence incomplete",
                "reasons": ["critical_evidence_missing"],
                "freshnessConstrained": False,
                "sourceQualityLimited": True,
                "thesisBlocked": True,
            },
            "missingEvidence": [
                {"kind": "daily_ohlcv", "message": "Daily price-history evidence is unavailable."},
            ],
            "historicalOhlcvReadiness": {
                "overallState": "blocked",
                "missingRequirements": ["insufficient_history"],
                "consumerSafe": True,
            },
            "dataQuality": {
                "status": "unavailable",
                "usableBars": 0,
                "requestedDays": 90,
                "reason": "history_unavailable",
            },
            "observationOnly": True,
            "decisionGrade": False,
        }
    )

    assert read_model["state"] == "no_evidence"
    assert read_model["ready"] is False
    assert read_model["classification"]["displayState"] == "withheld"
    assert read_model["classification"]["observedState"] == "breakout"
    assert read_model["confidence"]["label"] == "low"
    assert read_model["confidence"]["strongConclusionAllowed"] is False
    assert read_model["observationOnly"] is True
    assert read_model["decisionGrade"] is False


def test_backtest_readiness_projection_is_read_only_and_fail_closed() -> None:
    from src.services.product_read_model import build_backtest_readiness_read_model

    read_model = build_backtest_readiness_read_model(
        {
            "status": "stale",
            "executable": False,
            "freshness": "stale",
            "asOf": "2026-01-01",
            "requiredBarCount": 90,
            "availableBarCount": 90,
            "missingDataClasses": ["freshness"],
            "consumerSafe": True,
            "sourceReadiness": {"providerName": "must-not-leak", "consumerSafe": True},
        }
    )

    assert read_model["state"] == "stale"
    assert read_model["ready"] is False
    assert read_model["readOnly"] is True
    assert read_model["backtestExecuted"] is False
    assert read_model["coverage"]["state"] == "available"
    assert read_model["freshness"]["state"] == "stale"
    assert read_model["quality"]["state"] == "degraded"
    assert read_model["provenance"]["sourceClass"] == "historical_market_data"
    assert "providerName" not in str(read_model)
