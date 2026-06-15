# -*- coding: utf-8 -*-
"""HTTP contract tests for the portfolio structure review overlay."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import CurrentUser, get_current_user
from api.v1.endpoints import portfolio as portfolio_endpoint
from src.services.portfolio_structure_review_service import PORTFOLIO_STRUCTURE_REVIEW_SCHEMA_VERSION


def _make_user() -> CurrentUser:
    return CurrentUser(
        user_id="portfolio-review-user",
        username="portfolio-review-user",
        display_name="Portfolio Review User",
        role="user",
        is_admin=False,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
    )


class _FakePortfolioStructureReviewService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def build_review(
        self,
        *,
        account_id: int | None = None,
        as_of: date | None = None,
        cost_method: str = "fifo",
        benchmark: str | None = None,
        max_items: int | None = None,
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "account_id": account_id,
                "as_of": as_of,
                "cost_method": cost_method,
                "benchmark": benchmark,
                "max_items": max_items,
                "owner_id": owner_id,
            }
        )
        return {
            "schemaVersion": PORTFOLIO_STRUCTURE_REVIEW_SCHEMA_VERSION,
            "aggregateSummary": {
                "asOf": "2026-06-15",
                "accountCount": 1,
                "holdingCount": 1,
                "evaluatedCount": 1,
                "largestHolding": {"ticker": "AAPL", "percent": 100.0},
            },
            "exposureByThemeOrSector": [],
            "countsByStructureState": {"mixed": 1},
            "holdingsStructure": [
                {
                    "ticker": "AAPL",
                    "structureState": "mixed",
                    "confidence": "medium",
                    "evidenceQuality": {"score": 75, "status": "available"},
                    "riskFlags": [],
                    "researchNotes": {"watchNext": [], "needsMoreEvidence": [], "riskFlags": []},
                    "missingEvidence": [],
                }
            ],
            "strongestStructures": [{"ticker": "AAPL", "structureState": "mixed", "score": 75}],
            "weakestEvidence": [{"ticker": "AAPL", "status": "available", "usableBars": 55, "evidenceQuality": 75}],
            "commonRiskFlags": [],
            "missingEvidence": [],
            "dataQuality": {
                "status": "available",
                "holdingMetadataStatus": "available",
                "structureEvidenceStatus": "available",
                "readOnly": True,
                "failClosed": False,
            },
            "noAdviceDisclosure": "Observation-only research context; not personalized financial advice and not an instruction.",
        }


def _client(fake_service: _FakePortfolioStructureReviewService) -> TestClient:
    app = FastAPI()
    app.include_router(portfolio_endpoint.router, prefix="/api/v1/portfolio")
    app.dependency_overrides[get_current_user] = _make_user
    app.dependency_overrides[portfolio_endpoint.get_current_user] = _make_user
    app.dependency_overrides[portfolio_endpoint._get_portfolio_structure_review_service] = lambda: fake_service
    return TestClient(app)


def test_portfolio_structure_review_endpoint_returns_read_only_projection() -> None:
    fake_service = _FakePortfolioStructureReviewService()

    response = _client(fake_service).get(
        "/api/v1/portfolio/structure-review",
        params={"account_id": 7, "as_of": "2026-06-15", "cost_method": "fifo", "benchmark": "SPY", "max_items": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schemaVersion"] == PORTFOLIO_STRUCTURE_REVIEW_SCHEMA_VERSION
    assert payload["aggregateSummary"]["holdingCount"] == 1
    assert payload["holdingsStructure"][0]["ticker"] == "AAPL"
    assert payload["dataQuality"]["readOnly"] is True
    assert fake_service.calls == [
        {
            "account_id": 7,
            "as_of": date(2026, 6, 15),
            "cost_method": "fifo",
            "benchmark": "SPY",
            "max_items": 5,
            "owner_id": "portfolio-review-user",
        }
    ]
