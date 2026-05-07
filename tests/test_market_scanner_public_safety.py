# -*- coding: utf-8 -*-
"""Public-safety evidence for scanner and scanner signal outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from src.multi_user import OWNERSHIP_SCOPE_USER
from src.repositories.stock_repo import StockRepository
from src.services.market_scanner_ops_service import MarketScannerOperationsService
from src.services.market_scanner_service import MarketScannerService
from src.services.scanner_ai_service import ScannerAiInterpretationService
from src.storage import DatabaseManager
from tests.test_market_scanner_service import (
    FakeScannerAiService,
    FakeScannerDataManager,
    StructuredScannerDataManager,
)


FORBIDDEN_DIRECTIVE_TERMS = (
    "place order",
    "submit order",
    "buy now",
    "sell now",
    "guaranteed",
    "must buy",
    "must sell",
    "ai recommends you buy",
    "稳赚",
    "必买",
    "下单",
    "立即买入",
    "立即卖出",
    "立即交易",
    "保证收益",
)

FORBIDDEN_RAW_OUTPUT_KEYS = (
    "raw_provider_payload",
    "raw_payload",
    "token",
    "api_key",
    "credential",
    "password",
    "secret",
    "stack_trace",
    "traceback",
    "debug_schema",
    "attempt_trace",
)


def _iter_public_strings(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _iter_public_strings(item)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _iter_public_strings(item)
        return
    if isinstance(value, str):
        yield value


def _public_text(value: Any) -> str:
    return "\n".join(_iter_public_strings(value)).lower()


def _assert_no_forbidden_directives(value: Any) -> None:
    public_text = _public_text(value)
    for term in FORBIDDEN_DIRECTIVE_TERMS:
        assert term.lower() not in public_text


def _assert_no_raw_output_keys(value: Any) -> None:
    public_text = _public_text(value)
    for key in FORBIDDEN_RAW_OUTPUT_KEYS:
        assert key.lower() not in public_text


def test_scanner_outputs_use_bounded_observation_language_without_direct_trade_directives() -> None:
    DatabaseManager.reset_instance()
    db = DatabaseManager(db_url="sqlite:///:memory:")
    try:
        service = MarketScannerService(
            db,
            data_manager=FakeScannerDataManager(),
            ai_interpretation_service=FakeScannerAiService(),
        )

        detail = service.run_scan(
            market="cn",
            profile="cn_preopen_v1",
            shortlist_size=3,
            universe_limit=50,
            detail_limit=10,
        )
        notification = MarketScannerOperationsService.build_watchlist_notification(detail)

        _assert_no_forbidden_directives(detail)
        _assert_no_forbidden_directives(notification)
        assert any("不是自动买卖指令" in note for note in detail["scoring_notes"])
        assert detail["shortlist"]
        for candidate in detail["shortlist"]:
            assert candidate["risk_notes"]
            assert candidate["watch_context"]
            bounded_risk_text = " ".join(candidate["risk_notes"])
            assert any(token in bounded_risk_text for token in ("风险", "需", "防", "不宜", "确认", "回落"))
            ai_payload = candidate["ai_interpretation"]
            assert ai_payload["available"] is True
            assert "风险" in ai_payload["risk_interpretation"] or "回落" in ai_payload["risk_interpretation"]
            assert "看" in ai_payload["watch_plan"] or "观察" in ai_payload["watch_plan"]
    finally:
        DatabaseManager.reset_instance()


def test_degraded_market_data_is_disclosed_without_guaranteed_confidence_language() -> None:
    DatabaseManager.reset_instance()
    db = DatabaseManager(db_url="sqlite:///:memory:")
    try:
        stock_repo = StockRepository(db)
        data_manager = FakeScannerDataManager()
        for code, history in data_manager.histories.items():
            stock_repo.save_dataframe(history.copy(), code, data_source="LocalWarmCache")

        degraded_manager = StructuredScannerDataManager(
            snapshot_result={
                "success": False,
                "source": None,
                "data": None,
                "attempts": [
                    {
                        "fetcher": "AkshareFetcher",
                        "status": "failed",
                        "reason_code": "akshare_snapshot_fetch_failed",
                        "summary": "[AkshareFetcher] (DataFetchError) snapshot unavailable",
                    },
                    {
                        "fetcher": "EfinanceFetcher",
                        "status": "failed",
                        "reason_code": "efinance_snapshot_fetch_failed",
                        "summary": "[EfinanceFetcher] (DataFetchError) timeout",
                    },
                ],
                "error_code": "no_realtime_snapshot_available",
                "error_message": "snapshot unavailable",
            }
        )
        service = MarketScannerService(db, data_manager=degraded_manager)

        detail = service.run_scan(
            market="cn",
            profile="cn_preopen_v1",
            shortlist_size=3,
            universe_limit=50,
            detail_limit=10,
        )

        _assert_no_forbidden_directives(detail)
        assert detail["diagnostics"]["scanner_data"]["degraded_mode_used"] is True
        assert "snapshot=local_history_degraded" in detail["source_summary"]
        assert "degraded=yes" in detail["source_summary"]
        assert any("降级快照" in note for note in detail["universe_notes"])
        assert any("不是自动买卖指令" in note for note in detail["scoring_notes"])
    finally:
        DatabaseManager.reset_instance()


def test_scanner_public_ai_payload_redacts_raw_provider_and_debug_fields() -> None:
    raw_diagnostics = {
        "status": "generated",
        "summary": "更像趋势延续中的临界突破观察。",
        "opportunity_type": "临界突破",
        "risk_interpretation": "若竞价过高且量能不跟，容易冲高回落。",
        "watch_plan": "盘前看竞价承接，开盘后看量比是否维持强势。",
        "provider": "fake",
        "model": "fake/scanner-ai",
        "generated_at": "2026-04-13T08:30:00",
        "message": None,
        "attempt_trace": [{"fetcher": "SecretProvider", "token": "secret-token"}],
        "raw_provider_payload": {"credential": "secret", "debug_schema": {"stack_trace": "boom"}},
        "api_key": "secret-api-key",
    }

    public_payload = ScannerAiInterpretationService.public_payload_from_diagnostics(raw_diagnostics)

    _assert_no_raw_output_keys(public_payload)
    assert public_payload == {
        "available": True,
        "status": "generated",
        "summary": "更像趋势延续中的临界突破观察。",
        "opportunity_type": "临界突破",
        "risk_interpretation": "若竞价过高且量能不跟，容易冲高回落。",
        "watch_plan": "盘前看竞价承接，开盘后看量比是否维持强势。",
        "review_commentary": None,
        "provider": "fake",
        "model": "fake/scanner-ai",
        "generated_at": "2026-04-13T08:30:00",
        "message": None,
    }


def test_user_scoped_scanner_results_are_not_visible_to_other_users() -> None:
    DatabaseManager.reset_instance()
    db = DatabaseManager(db_url="sqlite:///:memory:")
    try:
        db.create_or_update_app_user(user_id="scanner-user-a", username="scanner-user-a")
        db.create_or_update_app_user(user_id="scanner-user-b", username="scanner-user-b")
        user_a_service = MarketScannerService(
            db,
            data_manager=FakeScannerDataManager(),
            owner_id="scanner-user-a",
        )
        user_b_service = MarketScannerService(
            db,
            data_manager=FakeScannerDataManager(),
            owner_id="scanner-user-b",
        )

        detail = user_a_service.run_scan(
            market="cn",
            profile="cn_preopen_v1",
            shortlist_size=2,
            universe_limit=50,
            detail_limit=10,
            scope=OWNERSHIP_SCOPE_USER,
        )

        assert user_a_service.get_run_detail(detail["id"], scope=OWNERSHIP_SCOPE_USER) is not None
        assert user_b_service.get_run_detail(detail["id"], scope=OWNERSHIP_SCOPE_USER) is None
        assert user_b_service.list_runs(market="cn", profile="cn_preopen_v1")["total"] == 0
    finally:
        DatabaseManager.reset_instance()


def test_scanner_runtime_modules_do_not_import_broker_order_or_portfolio_mutation_paths() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    scanner_runtime_files = [
        repo_root / "src/services/market_scanner_service.py",
        repo_root / "src/services/market_scanner_ops_service.py",
        repo_root / "src/services/scanner_ai_service.py",
        repo_root / "api/v1/endpoints/scanner.py",
        repo_root / "api/v1/schemas/scanner.py",
    ]
    forbidden_fragments = (
        "broker",
        "place_order",
        "submit_order",
        "execute_order",
        "create_order",
        "portfolio_service",
        "portfolio_repository",
        "PortfolioService",
        "Broker",
    )

    for path in scanner_runtime_files:
        source = path.read_text(encoding="utf-8")
        for fragment in forbidden_fragments:
            assert fragment not in source, f"{fragment!r} unexpectedly appears in {path}"
