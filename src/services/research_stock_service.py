# -*- coding: utf-8 -*-
"""Inert AI Stock Research contract service.

The scaffold intentionally avoids provider, cache, storage, or LLM execution.
It returns a fail-closed evidence-missing response until a separate task wires
approved evidence inputs into this contract.
"""

from __future__ import annotations

from datetime import datetime, timezone

from api.v1.schemas.research_stock import (
    AIStockResearchResponse,
    ResearchDataQuality,
    ResearchFactor,
    ResearchFreshness,
    ResearchSource,
    ResearchSummary,
    ResearchUnavailableState,
)


class AIStockResearchService:
    """Build consumer-safe structured research responses from approved evidence."""

    _MISSING_EVIDENCE = (
        "summary",
        "positive_factors",
        "risk_factors",
        "uncertain_factors",
        "technical_state",
        "sources",
        "freshness",
    )

    def build_unavailable_response(
        self,
        *,
        ticker: str,
        market: str | None = None,
        research_window: str | None = None,
    ) -> AIStockResearchResponse:
        generated_at = datetime.now(timezone.utc).isoformat()
        normalized_ticker = ticker.strip().upper()
        normalized_market = (market or "UNKNOWN").strip().upper() or "UNKNOWN"
        normalized_window = (research_window or "latest_available").strip() or "latest_available"

        return AIStockResearchResponse(
            ticker=normalized_ticker,
            market=normalized_market,
            research_window=normalized_window,
            generated_at=generated_at,
            as_of=generated_at,
            data_quality=ResearchDataQuality(
                status="unavailable",
                evidence_status="unavailable",
                missing_evidence=list(self._MISSING_EVIDENCE),
                external_calls_executed=False,
                llm_execution=False,
            ),
            evidence_status="unavailable",
            summary=ResearchSummary(
                status="unavailable",
                text="Structured research evidence is unavailable because no approved evidence input is attached.",
                evidence_count=0,
            ),
            bullish_factors=[],
            bearish_factors=[],
            neutral_or_uncertain_factors=[
                ResearchFactor(
                    label="Evidence missing",
                    evidence=["No approved structured evidence input is attached to this scaffold."],
                    status="unavailable",
                )
            ],
            technical_state=None,
            portfolio_watchlist_relevance=None,
            sources=[
                ResearchSource(
                    name="No approved evidence input",
                    category="research_evidence",
                    status="no_evidence",
                    as_of=None,
                )
            ],
            freshness=ResearchFreshness(
                status="unavailable",
                as_of=None,
                source_count=0,
            ),
            risk_disclosure=(
                "Evidence may be incomplete, delayed, or missing; use this response only as "
                "bounded research context."
            ),
            no_advice_disclosure=(
                "This endpoint provides structured research evidence only and does not provide "
                "personalized trading guidance."
            ),
            unavailable=ResearchUnavailableState(
                state="unavailable",
                reason="evidence_missing",
                message="No approved evidence input is available for this research request.",
            ),
        )
