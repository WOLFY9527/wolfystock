# -*- coding: utf-8 -*-
"""Scanner diagnostics contract tests."""

import pytest

from api.v1.schemas import scanner as scanner_schema
from src.core.scanner_skip_reason import normalize_scanner_skip_reason
from src.repositories.stock_repo import StockRepository
from src.services import market_scanner_service as scanner_service
from src.services.market_scanner_service import MarketScannerService
from src.storage import DatabaseManager
from tests.test_market_scanner_service import FakeUsScannerDataManager, seed_crypto_miner_local_history


UNSAFE_CONSUMER_DIAGNOSTIC_TERMS = (
    "alpaca",
    "history_only_us_scan",
    "missing price history",
    "not_enough_history",
    "below_score_threshold",
    "provider_payload",
    "raw_payload",
)


SCANNER_SKIP_REASON_CASES = (
    pytest.param("selected", None, [], [], "selected", id="selected-status"),
    pytest.param("data_failed", None, [], [], "history_coverage", id="data-failed-status"),
    pytest.param("skipped", "missing price history", [], [], "history_coverage", id="missing-price-history"),
    pytest.param("skipped", None, ["not_enough_history"], [], "history_coverage", id="not-enough-history"),
    pytest.param("skipped", None, [], ["missing_history"], "history_coverage", id="missing-history-field"),
    pytest.param("rejected", None, ["insufficient_history"], [], "history_coverage", id="insufficient-history"),
    pytest.param("rejected", None, ["below_score_threshold"], [], "score_fit", id="score-threshold"),
    pytest.param("rejected", None, ["below_liquidity_threshold"], [], "liquidity", id="liquidity"),
    pytest.param("rejected", None, ["volume"], [], "liquidity", id="volume"),
    pytest.param("rejected", None, ["amount"], [], "liquidity", id="amount"),
    pytest.param("rejected", None, ["turnover"], [], "liquidity", id="turnover"),
    pytest.param("rejected", "below price threshold", [], [], "price_range", id="price"),
    pytest.param("rejected", None, ["below_trend_threshold"], [], "trend_fit", id="trend"),
    pytest.param("rejected", None, ["ma20"], [], "trend_fit", id="ma20"),
    pytest.param("rejected", None, ["ma60"], [], "trend_fit", id="ma60"),
    pytest.param("rejected", None, ["below_ma20_or_ma60"], [], "trend_fit", id="ma-rules"),
    pytest.param("rejected", None, ["below_momentum_threshold"], [], "momentum_fit", id="momentum"),
    pytest.param("skipped", "unsupported_market", [], [], "universe_scope", id="unsupported-market"),
    pytest.param("skipped", "benchmark_symbol_skipped", [], [], "universe_scope", id="benchmark-symbol"),
    pytest.param("skipped", None, ["duplicate_symbol"], [], "universe_scope", id="duplicate-symbol"),
    pytest.param("error", None, ["invalid_payload"], [], "input_validation", id="invalid-payload"),
    pytest.param("error", "invalid", [], [], "input_validation", id="invalid"),
    pytest.param("error", "payload", [], [], "input_validation", id="payload"),
    pytest.param("skipped", "not_evaluated", [], [], "other", id="not-evaluated"),
    pytest.param("evaluated", "evaluated", [], [], "other", id="evaluated"),
    pytest.param("selected", "missing price history", [], [], "selected", id="ordering-selected-first"),
    pytest.param(
        "data_failed",
        None,
        ["below_score_threshold"],
        [],
        "history_coverage",
        id="ordering-history-before-score",
    ),
    pytest.param(
        "rejected",
        "liquidity",
        ["below_score_threshold"],
        [],
        "score_fit",
        id="ordering-score-before-liquidity",
    ),
    pytest.param("rejected", "price", ["liquidity"], [], "liquidity", id="ordering-liquidity-before-price"),
    pytest.param("rejected", "trend", ["price"], [], "price_range", id="ordering-price-before-trend"),
    pytest.param("rejected", "momentum", ["trend"], [], "trend_fit", id="ordering-trend-before-momentum"),
    pytest.param(
        "rejected",
        "unsupported_market",
        ["momentum"],
        [],
        "momentum_fit",
        id="ordering-momentum-before-universe",
    ),
    pytest.param(
        "skipped",
        "invalid_payload",
        ["duplicate_symbol"],
        [],
        "universe_scope",
        id="ordering-universe-before-input",
    ),
    pytest.param("", "", [], [], "other", id="empty"),
    pytest.param(None, None, [], [], "other", id="null"),
    pytest.param("skipped", {"unexpected": True}, [17, None], [{"bad": True}], "other", id="malformed"),
    pytest.param("skipped", "unknown_reason", ["unknown_rule"], ["unknown.field"], "other", id="unknown"),
    pytest.param("SELECTED", None, [], [], "other", id="status-case-sensitive"),
)


@pytest.mark.parametrize(
    ("status", "reason", "failed_rules", "missing_fields", "expected"),
    SCANNER_SKIP_REASON_CASES,
)
def test_scanner_skip_reason_normalizer_golden_parity(
    status: object,
    reason: object,
    failed_rules: list[object],
    missing_fields: list[object],
    expected: str,
) -> None:
    assert normalize_scanner_skip_reason(
        status=status,
        reason=reason,
        failed_rules=failed_rules,
        missing_fields=missing_fields,
    ) == expected


def test_scanner_schema_and_service_share_authoritative_skip_reason_normalizer() -> None:
    assert scanner_schema.normalize_scanner_skip_reason is normalize_scanner_skip_reason
    assert scanner_service.normalize_scanner_skip_reason is normalize_scanner_skip_reason


@pytest.mark.parametrize(
    ("status", "reason", "failed_rules", "missing_fields", "expected"),
    tuple(
        case
        for case in SCANNER_SKIP_REASON_CASES
        if case.values[0] in {"selected", "rejected", "data_failed", "skipped", "error", "evaluated"}
        and case.id != "malformed"
    ),
)
def test_scanner_schema_and_service_skip_reason_projections_are_equal(
    status: str,
    reason: object,
    failed_rules: list[object],
    missing_fields: list[object],
    expected: str,
) -> None:
    schema_payload = scanner_schema.ScannerCandidateDiagnosticsResponse(
        symbol="TEST",
        status=status,
        score=None if status == "data_failed" else 50.0,
        reason=reason,
        failed_rules=failed_rules,
        missing_fields=missing_fields,
        factorEvidence={
            "contractVersion": "scanner_factor_evidence_v1",
            "overallState": "blocked",
            "rankingEligible": False,
            "blockers": ["momentum:unavailable"],
            "factors": [],
        },
    ).model_dump()
    service = object.__new__(MarketScannerService)
    service_payload = service._build_candidate_consumer_projection(
        {
            "status": status,
            "score": None if status == "data_failed" else 50.0,
            "reason": reason,
            "failed_rules": failed_rules,
            "missing_fields": missing_fields,
        }
    )

    assert schema_payload["consumerReasonBucket"] == expected
    assert service_payload["consumerReasonBucket"] == expected
    assert (
        schema_payload["consumerDiagnostics"]["reasonBucket"]
        == service_payload["consumerDiagnostics"]["reasonBucket"]
    )


def _assert_consumer_rejection_projection_is_safe(candidate: dict) -> None:
    assert candidate["consumerReasonBucket"]
    assert candidate["consumerReasonLabel"]
    assert candidate["consumerNextEvidence"]
    assert candidate["consumerDiagnostics"]["reasonBucket"] == candidate["consumerReasonBucket"]
    assert candidate["consumerDiagnostics"]["reasonLabel"] == candidate["consumerReasonLabel"]
    assert candidate["consumerDiagnostics"]["nextEvidence"] == candidate["consumerNextEvidence"]
    assert candidate["consumerDiagnostics"]["sourceConfidenceBucket"]
    assert candidate["consumerDiagnostics"]["freshnessCategory"]
    public_text = str(
        {
            "consumerReasonBucket": candidate["consumerReasonBucket"],
            "consumerReasonLabel": candidate["consumerReasonLabel"],
            "consumerNextEvidence": candidate["consumerNextEvidence"],
            "consumerDiagnostics": candidate["consumerDiagnostics"],
        }
    ).lower()
    for term in UNSAFE_CONSUMER_DIAGNOSTIC_TERMS:
        assert term not in public_text


def test_crypto_mining_scan_returns_full_candidate_diagnostics() -> None:
    DatabaseManager.reset_instance()
    db = DatabaseManager(db_url="sqlite:///:memory:")
    try:
        stock_repo = StockRepository(db)
        seed_crypto_miner_local_history(stock_repo)
        data_manager = FakeUsScannerDataManager()
        service = MarketScannerService(db, data_manager=data_manager)

        result = service.run_scan(
            market="us",
            profile="us_preopen_v1",
            shortlist_size=1,
            universe_limit=50,
            detail_limit=10,
            universe_type="theme",
            theme_id="crypto_miners",
        )

        assert result["summary"]["universe_count"] == 11
        assert result["summary"]["selected_count"] == 1
        assert result["summary"]["rejected_count"] == 7
        assert result["summary"]["data_failed_count"] == 3
        assert result["summary"]["limited_by_result_cap"] is False
        assert len(result["candidates"]) == 11
        assert result["selected"] == result["shortlist"]
        hive = next(item for item in result["candidates"] if item["symbol"] == "HIVE")
        assert hive["status"] == "data_failed"
        assert hive["rank"] == 0
        assert hive["reason"] == "factor_evidence_blocked"
        assert hive["factorEvidence"]["blockers"] == ["gap_context:unavailable"]
        assert hive["metrics"]["price"] > 0
        assert {
            "coverage_summary",
            "provider_diagnostics",
            "scanner_data",
            "universe_selection",
        } <= set(result["diagnostics"])
        candidate_by_status = {item["status"]: item for item in result["candidates"]}
        for status in ("selected", "rejected", "data_failed"):
            assert {
                "rank",
                "status",
                "score",
                "provider",
                "reason",
                "failed_rules",
                "missing_fields",
                "metrics",
            } <= set(candidate_by_status[status]), f"{status} candidate diagnostics must keep bounded scanner fields"
            assert isinstance(candidate_by_status[status]["rank"], int)
            if status == "data_failed":
                assert candidate_by_status[status]["rank"] == 0
            else:
                assert candidate_by_status[status]["provider"]
                assert candidate_by_status[status]["rank"] > 0
        assert all(item["reason"] or item["failed_rules"] for item in result["candidates"] if item["status"] == "rejected")
        assert any(item["status"] == "data_failed" and item["missing_fields"] for item in result["candidates"])
        assert candidate_by_status["selected"]["score"] is not None
        assert candidate_by_status["selected"]["failed_rules"] == []
        assert candidate_by_status["selected"]["missing_fields"] == []
        assert candidate_by_status["rejected"]["score"] is not None
        assert candidate_by_status["rejected"]["failed_rules"]
        assert candidate_by_status["data_failed"]["score"] is None
        assert candidate_by_status["data_failed"]["missing_fields"]
        assert isinstance(candidate_by_status["data_failed"]["metrics"], dict)
        rejected = [item for item in result["candidates"] if item["status"] == "rejected"]
        data_failed = [item for item in result["candidates"] if item["status"] == "data_failed"]
        assert rejected
        assert data_failed
        assert {item["consumerReasonBucket"] for item in rejected} == {"score_fit"}
        assert {item["consumerReasonBucket"] for item in data_failed} == {"history_coverage"}
        for item in rejected + data_failed:
            _assert_consumer_rejection_projection_is_safe(item)
        assert len(data_manager.realtime_quote_calls) == 9
    finally:
        DatabaseManager.reset_instance()
