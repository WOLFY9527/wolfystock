# -*- coding: utf-8 -*-
"""Tests for the read-only portfolio structure review projection."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from src.services.portfolio_structure_review_service import (
    PORTFOLIO_STRUCTURE_REVIEW_SCHEMA_VERSION,
    PortfolioStructureReviewService,
)


FORBIDDEN_RESEARCH_TOKENS = (
    r"\bbuy\b",
    r"\bsell\b",
    r"\bplace\s+order\b",
    r"\btrade\s+recommendation\b",
    r"\bposition\s+sizing\b",
    r"\brecommendation\b",
    r"\btarget\s+price\b",
    r"\bstop\s+loss\b",
    r"买入",
    r"卖出",
    r"下单",
    r"交易建议",
    r"仓位建议",
    r"目标价",
    r"止损",
)


@dataclass
class _Account:
    id: int
    owner_id: str = "user-1"
    name: str = "Main"
    broker: str | None = None
    market: str = "us"
    base_currency: str = "USD"
    is_active: bool = True


@dataclass
class _Snapshot:
    account_id: int
    snapshot_date: date
    cost_method: str = "fifo"
    base_currency: str = "USD"
    total_cash: float = 100.0
    total_market_value: float = 2000.0
    total_equity: float = 2100.0
    unrealized_pnl: float = 100.0
    realized_pnl: float = 0.0
    fee_total: float = 0.0
    tax_total: float = 0.0
    fx_stale: bool = False
    payload: str | None = None


@dataclass
class _Position:
    account_id: int
    symbol: str
    market_value_base: float
    market: str = "us"
    currency: str = "USD"
    cost_method: str = "fifo"
    quantity: float = 1.0
    avg_cost: float = 100.0
    total_cost: float = 100.0
    last_price: float = 100.0
    unrealized_pnl_base: float = 0.0
    valuation_currency: str = "USD"


class _FakePortfolioRepo:
    def __init__(self, *, accounts: list[_Account], bundles: dict[tuple[int, date, str], dict[str, Any]]) -> None:
        self.accounts = accounts
        self.bundles = bundles
        self.calls: list[dict[str, Any]] = []
        self.write_calls: list[str] = []

    def list_accounts(self, include_inactive: bool = False, *, owner_id: str | None = None, include_all_owners: bool = False):
        self.calls.append(
            {
                "method": "list_accounts",
                "include_inactive": include_inactive,
                "owner_id": owner_id,
                "include_all_owners": include_all_owners,
            }
        )
        return [account for account in self.accounts if include_inactive or account.is_active]

    def get_account(
        self,
        account_id: int,
        include_inactive: bool = False,
        *,
        owner_id: str | None = None,
        include_all_owners: bool = False,
    ):
        self.calls.append(
            {
                "method": "get_account",
                "account_id": account_id,
                "owner_id": owner_id,
                "include_all_owners": include_all_owners,
            }
        )
        for account in self.accounts:
            if int(account.id) == int(account_id) and (include_inactive or account.is_active):
                return account
        return None

    def get_cached_snapshot_bundle(self, *, account_id: int, snapshot_date: date, cost_method: str):
        self.calls.append(
            {
                "method": "get_cached_snapshot_bundle",
                "account_id": account_id,
                "snapshot_date": snapshot_date,
                "cost_method": cost_method,
            }
        )
        return self.bundles.get((int(account_id), snapshot_date, cost_method))

    def get_latest_cached_snapshot_date(self, *, account_id: int, cost_method: str):
        self.calls.append(
            {
                "method": "get_latest_cached_snapshot_date",
                "account_id": account_id,
                "cost_method": cost_method,
            }
        )
        dates = [key[1] for key in self.bundles if key[0] == int(account_id) and key[2] == cost_method]
        return max(dates) if dates else None

    def replace_positions_lots_and_snapshot(self, *args: Any, **kwargs: Any) -> None:
        self.write_calls.append("replace_positions_lots_and_snapshot")
        raise AssertionError("portfolio structure review must not write snapshot cache")


class _FakeStructureService:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def get_structure_decisions_batch(
        self,
        tickers: list[str],
        *,
        benchmark: str | None = None,
        max_items: int | None = None,
    ) -> dict[str, Any]:
        self.calls.append({"tickers": tickers, "benchmark": benchmark, "max_items": max_items})
        return self.payload


def _structure_item(
    ticker: str,
    *,
    state: str = "breakout",
    confidence: str = "high",
    evidence_score: int = 92,
    data_status: str = "available",
    risk_flags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "structureState": state,
        "confidence": confidence,
        "componentScores": {
            "trend": 75,
            "relativeStrength": 60,
            "volumePressure": 65,
            "volatilityCompression": 40,
            "breakoutQuality": 84,
            "pullbackHealth": 42,
            "riskExtension": 50,
            "evidenceQuality": evidence_score,
        },
        "researchNotes": {
            "watchNext": ["Observe whether the structure remains supported by fresh daily bars."],
            "needsMoreEvidence": [],
            "riskFlags": risk_flags or [],
        },
        "dataQuality": {
            "status": data_status,
            "source": "local_db",
            "period": "daily",
            "requestedDays": 90,
            "observedBars": 55,
            "usableBars": 55,
            "reason": "history_available",
        },
        "missingEvidence": [],
    }


def _batch_payload() -> dict[str, Any]:
    items = [
        _structure_item("AAPL", state="breakout", confidence="high", evidence_score=92),
        _structure_item(
            "MSFT",
            state="lowConfidence",
            confidence="low",
            evidence_score=18,
            data_status="unavailable",
            risk_flags=["Low evidence quality limits structure confidence."],
        ),
    ]
    return {
        "items": items,
        "aggregateSummary": {
            "requestedCount": 2,
            "evaluatedCount": 2,
            "maxItems": 25,
            "truncated": False,
            "structureStateCounts": {"breakout": 1, "lowConfidence": 1},
            "strongestStructures": [{"ticker": "AAPL", "structureState": "breakout", "score": 84, "confidence": "high"}],
            "weakestEvidence": [{"ticker": "MSFT", "status": "unavailable", "usableBars": 0, "evidenceQuality": 18}],
            "commonRiskFlags": [
                {"flag": "Low evidence quality limits structure confidence.", "count": 1, "tickers": ["MSFT"]}
            ],
        },
        "missingEvidence": [{"kind": "daily_ohlcv", "message": "At least one symbol has unavailable daily OHLCV evidence."}],
        "dataQuality": {
            "status": "partial",
            "availableCount": 1,
            "partialCount": 0,
            "insufficientCount": 0,
            "unavailableCount": 1,
        },
        "noAdviceDisclosure": "Observation-only research context; not personalized financial advice and not an instruction.",
    }


def test_structure_review_uses_cached_holdings_and_batch_structure_without_portfolio_writes() -> None:
    review_date = date(2026, 6, 15)
    sector_payload = {
        "analytics": {
            "exposure": {
                "by_sector": [
                    {
                        "key": "ai_infrastructure",
                        "label": "AI Infrastructure",
                        "market_value": 1500.0,
                        "percent": 75.0,
                        "holding_count": 2,
                    }
                ],
                "sector_status": "available",
            }
        }
    }
    repo = _FakePortfolioRepo(
        accounts=[_Account(id=1)],
        bundles={
            (1, review_date, "fifo"): {
                "snapshot": _Snapshot(account_id=1, snapshot_date=review_date, payload=json.dumps(sector_payload)),
                "positions": [
                    _Position(account_id=1, symbol="aapl", market_value_base=1200.0),
                    _Position(account_id=1, symbol="MSFT", market_value_base=800.0),
                ],
                "lots": [],
            }
        },
    )
    structure_service = _FakeStructureService(_batch_payload())

    payload = PortfolioStructureReviewService(
        portfolio_repo=repo,
        structure_service=structure_service,
    ).build_review(account_id=None, as_of=review_date, cost_method="fifo", benchmark="SPY", owner_id="user-1")

    assert payload["schemaVersion"] == PORTFOLIO_STRUCTURE_REVIEW_SCHEMA_VERSION
    assert payload["aggregateSummary"]["accountCount"] == 1
    assert payload["aggregateSummary"]["holdingCount"] == 2
    assert payload["aggregateSummary"]["largestHolding"]["ticker"] == "AAPL"
    assert payload["aggregateSummary"]["largestHolding"]["percent"] == 60.0
    assert payload["exposureByThemeOrSector"] == sector_payload["analytics"]["exposure"]["by_sector"]
    assert payload["countsByStructureState"] == {"breakout": 1, "lowConfidence": 1}
    assert [item["ticker"] for item in payload["holdingsStructure"]] == ["AAPL", "MSFT"]
    assert payload["holdingsStructure"][0]["evidenceQuality"] == {"score": 92, "status": "available"}
    assert payload["weakestEvidence"][0]["ticker"] == "MSFT"
    assert payload["readOnly"] is True
    assert payload["failClosed"] is False
    assert payload["consumerState"] == "PARTIAL"
    assert payload["consumerSummary"] == "Structure review partially available"
    assert payload["consumerMessage"] == (
        "Some holdings are missing metadata or structure evidence, so this review remains partial and read-only."
    )
    assert payload["drilldownSymbols"] == ["AAPL", "MSFT"]
    assert payload["dataQuality"]["status"] == "partial"
    assert payload["dataQuality"]["holdingMetadataStatus"] == "available"
    assert payload["dataQuality"]["readOnly"] is True
    assert structure_service.calls == [{"tickers": ["AAPL", "MSFT"], "benchmark": "SPY", "max_items": None}]
    assert repo.write_calls == []


def test_structure_review_fails_closed_when_cached_holdings_are_unavailable() -> None:
    review_date = date(2026, 6, 15)
    repo = _FakePortfolioRepo(accounts=[_Account(id=1)], bundles={})
    structure_service = _FakeStructureService(_batch_payload())

    payload = PortfolioStructureReviewService(
        portfolio_repo=repo,
        structure_service=structure_service,
    ).build_review(account_id=1, as_of=review_date, cost_method="fifo", owner_id="user-1")

    assert payload["schemaVersion"] == PORTFOLIO_STRUCTURE_REVIEW_SCHEMA_VERSION
    assert payload["aggregateSummary"]["holdingCount"] == 0
    assert payload["holdingsStructure"] == []
    assert payload["countsByStructureState"] == {}
    assert payload["readOnly"] is True
    assert payload["failClosed"] is True
    assert payload["consumerState"] == "UNAVAILABLE"
    assert payload["consumerSummary"] == "Structure review unavailable"
    assert payload["consumerMessage"] == (
        "Cached holdings or structure evidence are unavailable, so this panel remains fail-closed."
    )
    assert payload["drilldownSymbols"] == []
    assert payload["dataQuality"]["status"] == "unavailable"
    assert payload["dataQuality"]["holdingMetadataStatus"] == "unavailable"
    assert payload["dataQuality"]["failClosed"] is True
    assert {"kind": "cached_portfolio_holdings", "message": "Cached portfolio holdings are unavailable."} in payload[
        "missingEvidence"
    ]
    assert structure_service.calls == []
    assert repo.write_calls == []


def test_structure_review_fails_closed_for_missing_security_metadata() -> None:
    review_date = date(2026, 6, 15)
    repo = _FakePortfolioRepo(
        accounts=[_Account(id=1)],
        bundles={
            (1, review_date, "fifo"): {
                "snapshot": _Snapshot(account_id=1, snapshot_date=review_date),
                "positions": [_Position(account_id=1, symbol="", market_value_base=1000.0)],
                "lots": [],
            }
        },
    )
    structure_service = _FakeStructureService(_batch_payload())

    payload = PortfolioStructureReviewService(
        portfolio_repo=repo,
        structure_service=structure_service,
    ).build_review(account_id=1, as_of=review_date, cost_method="fifo", owner_id="user-1")

    assert payload["holdingsStructure"] == [
        {
            "ticker": "UNKNOWN",
            "structureState": "lowConfidence",
            "confidence": "low",
            "evidenceQuality": {"score": 0, "status": "unavailable"},
            "riskFlags": ["Security metadata is unavailable for this cached holding."],
            "researchNotes": {
                "watchNext": [],
                "needsMoreEvidence": ["Security metadata is required before structure evidence can be reviewed."],
                "riskFlags": ["Security metadata is unavailable for this cached holding."],
            },
            "missingEvidence": [
                {
                    "kind": "security_metadata",
                    "message": "Ticker, market, or currency metadata is missing for this cached holding.",
                }
            ],
        }
    ]
    assert payload["readOnly"] is True
    assert payload["failClosed"] is True
    assert payload["consumerState"] == "UNAVAILABLE"
    assert payload["consumerSummary"] == "Structure review unavailable"
    assert payload["dataQuality"]["status"] == "unavailable"
    assert payload["dataQuality"]["holdingMetadataStatus"] == "unavailable"
    assert structure_service.calls == []


def test_structure_review_output_avoids_research_instruction_language() -> None:
    review_date = date(2026, 6, 15)
    repo = _FakePortfolioRepo(
        accounts=[_Account(id=1)],
        bundles={
            (1, review_date, "fifo"): {
                "snapshot": _Snapshot(account_id=1, snapshot_date=review_date),
                "positions": [_Position(account_id=1, symbol="AAPL", market_value_base=1000.0)],
                "lots": [],
            }
        },
    )

    payload = PortfolioStructureReviewService(
        portfolio_repo=repo,
        structure_service=_FakeStructureService(
            {
                **_batch_payload(),
                "items": [_structure_item("AAPL", state="mixed", confidence="medium", evidence_score=75)],
                "aggregateSummary": {
                    **_batch_payload()["aggregateSummary"],
                    "structureStateCounts": {"mixed": 1},
                    "strongestStructures": [{"ticker": "AAPL", "structureState": "mixed", "score": 75}],
                    "weakestEvidence": [{"ticker": "AAPL", "status": "available", "usableBars": 55, "evidenceQuality": 75}],
                    "commonRiskFlags": [],
                },
                "missingEvidence": [],
                "dataQuality": {
                    "status": "available",
                    "availableCount": 1,
                    "partialCount": 0,
                    "insufficientCount": 0,
                    "unavailableCount": 0,
                },
            }
        ),
    ).build_review(account_id=1, as_of=review_date, cost_method="fifo", owner_id="user-1")

    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for pattern in FORBIDDEN_RESEARCH_TOKENS:
        assert re.search(pattern, serialized) is None, pattern
    assert "noAdviceDisclosure" in payload
