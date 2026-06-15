# -*- coding: utf-8 -*-
"""Pure service that emits a deterministic homepage pre-session research checklist."""

from __future__ import annotations

from collections.abc import Iterable

from api.v1.schemas.homepage_pre_session_research_checklist import (
    HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_DEFAULT_AS_OF,
    HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_SCHEMA_VERSION,
    HomepagePreSessionChecklistItem,
    HomepagePreSessionContext,
    HomepagePreSessionQuality,
    HomepagePreSessionResearchChecklistSnapshot,
)


_CHECKLIST_ITEMS = (
    HomepagePreSessionChecklistItem(
        id="rates_pressure_review",
        title="Rates pressure review",
        reviewPrompt="Confirm whether rates pressure is easing or rising.",
        researchQuestion="Are yields, real-rate proxies, and currency pressure aligned before the next market session?",
        confirmationGates=[
            "Confirm rate direction across short and long tenors",
            "cross-check currency pressure against equity breadth",
            "No conclusion until duration-sensitive groups are reviewed",
        ],
        evidenceNeeded=[
            "yield-curve direction",
            "real-rate sensitivity",
            "currency pressure context",
        ],
        relatedSections=["rates pricing", "cross-asset indicators", "macro driver chain"],
        relatedAssets=["Treasury curve", "US dollar", "growth equities"],
        relatedSectors=["technology", "real estate", "utilities"],
        relatedThemes=["rates pressure", "duration sensitivity", "valuation discount rate"],
        reviewModule="rates_pricing",
        confidence="needs_review",
        evidenceQuality="needs_confirmation",
        dataQuality="static_contract",
    ),
    HomepagePreSessionChecklistItem(
        id="breadth_participation_review",
        title="Breadth participation review",
        reviewPrompt="Confirm whether breadth is broadening or narrowing.",
        researchQuestion="Is participation expanding beyond leading groups before the next market session?",
        confirmationGates=[
            "Confirm sector participation count",
            "cross-check equal-weight behavior against headline indexes",
            "No conclusion until small-cap and sector breadth are reviewed",
        ],
        evidenceNeeded=[
            "advance-decline context",
            "equal-weight confirmation",
            "sector participation map",
        ],
        relatedSections=["market breadth", "theme capital flow", "scenario watchlist"],
        relatedAssets=["equal-weight indexes", "small caps", "sector baskets"],
        relatedSectors=["technology", "industrials", "financials"],
        relatedThemes=["market breadth", "leadership diffusion", "participation quality"],
        reviewModule="market_breadth",
        confidence="needs_review",
        evidenceQuality="needs_confirmation",
        dataQuality="static_contract",
    ),
    HomepagePreSessionChecklistItem(
        id="ai_infrastructure_evidence_review",
        title="AI infrastructure evidence review",
        reviewPrompt="Check whether AI infrastructure leadership is still supported by evidence.",
        researchQuestion="Do infrastructure demand, supply-chain signals, and margins still support leadership review?",
        confirmationGates=[
            "Confirm demand visibility across infrastructure groups",
            "cross-check supplier breadth against large-platform spending commentary",
            "No conclusion until margin and cash-flow quality are reviewed",
        ],
        evidenceNeeded=[
            "infrastructure demand visibility",
            "supplier breadth",
            "margin-quality context",
        ],
        relatedSections=["theme capital flow", "scenario watchlist", "after-close developments"],
        relatedAssets=["semiconductors", "cloud infrastructure", "power equipment"],
        relatedSectors=["semiconductors", "software", "electric equipment"],
        relatedThemes=["AI infrastructure", "compute demand", "capital expenditure cycle"],
        reviewModule="theme_capital_flow",
        confidence="medium",
        evidenceQuality="template_only",
        dataQuality="static_contract",
    ),
    HomepagePreSessionChecklistItem(
        id="oil_geopolitical_premium_review",
        title="Oil and geopolitical premium review",
        reviewPrompt="Review whether oil/geopolitical risk premium is falling or rising.",
        researchQuestion="Are energy, shipping, and safe-haven signals pointing to the same risk-premium backdrop?",
        confirmationGates=[
            "Confirm oil-volatility direction",
            "cross-check energy leadership against inflation-sensitive assets",
            "No conclusion until safe-haven confirmation is reviewed",
        ],
        evidenceNeeded=[
            "oil-volatility direction",
            "shipping-risk context",
            "safe-haven confirmation",
        ],
        relatedSections=["cross-asset indicators", "after-close developments", "event impact map"],
        relatedAssets=["crude oil", "energy equities", "gold"],
        relatedSectors=["energy", "transportation", "chemicals"],
        relatedThemes=["oil risk premium", "geopolitical stress", "inflation sensitivity"],
        reviewModule="cross_asset_indicators",
        confidence="needs_review",
        evidenceQuality="mixed",
        dataQuality="static_contract",
    ),
    HomepagePreSessionChecklistItem(
        id="credit_liquidity_stress_review",
        title="Credit and liquidity stress review",
        reviewPrompt="Check whether credit/liquidity stress is visible.",
        researchQuestion="Do funding, credit, dollar, and small-cap signals show visible stress before the next session?",
        confirmationGates=[
            "Confirm credit-spread direction",
            "cross-check funding pressure against dollar strength",
            "No conclusion until small-cap and financial-sector signals are reviewed",
        ],
        evidenceNeeded=[
            "credit-spread context",
            "funding-pressure proxy",
            "small-cap relative behavior",
        ],
        relatedSections=["liquidity credit", "cross-asset indicators", "market breadth"],
        relatedAssets=["credit indexes", "small caps", "US dollar"],
        relatedSectors=["financials", "real estate", "industrials"],
        relatedThemes=["liquidity conditions", "credit stress", "funding pressure"],
        reviewModule="liquidity_credit",
        confidence="needs_review",
        evidenceQuality="needs_confirmation",
        dataQuality="static_contract",
    ),
    HomepagePreSessionChecklistItem(
        id="after_close_developments_review",
        title="After-close developments review",
        reviewPrompt="Review whether after-close developments change the research queue.",
        researchQuestion="Do after-close macro, earnings, or commodity developments change what needs review first?",
        confirmationGates=[
            "Confirm overnight context before updating review priority",
            "cross-check earnings and macro items against related sections",
            "No conclusion until next-session research questions are ranked",
        ],
        evidenceNeeded=[
            "overnight context",
            "earnings-catalyst notes",
            "macro-event calendar",
        ],
        relatedSections=["after-close developments", "event radar", "research queue"],
        relatedAssets=["equity indexes", "rates", "commodities"],
        relatedSectors=["technology", "energy", "financials"],
        relatedThemes=["after-close context", "event catalyst", "research queue"],
        reviewModule="after_close_developments",
        confidence="needs_review",
        evidenceQuality="template_only",
        dataQuality="static_contract",
    ),
)


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


class HomepagePreSessionResearchChecklistService:
    """Build a static checklist snapshot without runtime dependencies."""

    def build_snapshot(self) -> HomepagePreSessionResearchChecklistSnapshot:
        checklist_items = list(_CHECKLIST_ITEMS)
        return HomepagePreSessionResearchChecklistSnapshot(
            schemaVersion=HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_SCHEMA_VERSION,
            asOf=HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_DEFAULT_AS_OF,
            sessionContext=HomepagePreSessionContext(
                label="Next market session research review",
                reviewWindow="Before the next regular session",
                purpose=(
                    "Organize research question, confirmation gate, and evidence review items for the homepage cockpit."
                ),
            ),
            checklistItems=checklist_items,
            researchQuestions=[item.researchQuestion for item in checklist_items],
            confirmationGates=_unique(
                gate for item in checklist_items for gate in item.confirmationGates
            ),
            evidenceNeeded=_unique(
                evidence for item in checklist_items for evidence in item.evidenceNeeded
            ),
            relatedSections=_unique(
                section for item in checklist_items for section in item.relatedSections
            ),
            relatedAssets=_unique(asset for item in checklist_items for asset in item.relatedAssets),
            relatedSectors=_unique(
                sector for item in checklist_items for sector in item.relatedSectors
            ),
            relatedThemes=_unique(theme for item in checklist_items for theme in item.relatedThemes),
            reviewModules=_unique([item.reviewModule for item in checklist_items]),
            confidence=HomepagePreSessionQuality(
                state="needs_review",
                label="Requires pre-session review",
                summary="Confidence stays gated until each checklist item has matching evidence.",
            ),
            evidenceQuality=HomepagePreSessionQuality(
                state="needs_confirmation",
                label="Evidence gathering required",
                summary="The contract defines questions and gates without claiming current evidence is complete.",
            ),
            dataQuality=HomepagePreSessionQuality(
                state="static_contract",
                label="Static research contract",
                summary="Output is deterministic structure for review planning, not current market data.",
            ),
            noAdviceDisclosure=HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_NO_ADVICE_DISCLOSURE,
        )


__all__ = [
    "HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_DEFAULT_AS_OF",
    "HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_PRE_SESSION_RESEARCH_CHECKLIST_SCHEMA_VERSION",
    "HomepagePreSessionResearchChecklistService",
]
