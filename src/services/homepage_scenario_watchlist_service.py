# -*- coding: utf-8 -*-
"""Pure service that emits a deterministic homepage scenario watchlist."""

from __future__ import annotations

from api.v1.schemas.homepage_scenario_watchlist import (
    HOMEPAGE_SCENARIO_WATCHLIST_DEFAULT_AS_OF,
    HOMEPAGE_SCENARIO_WATCHLIST_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_SCENARIO_WATCHLIST_SCHEMA_VERSION,
    HomepageScenarioWatchlistScenario,
    HomepageScenarioWatchlistSnapshot,
)


_SCENARIOS = (
    HomepageScenarioWatchlistScenario(
        scenarioName="Rates repricing pressure",
        description=(
            "A monitoring frame for whether rates repricing is adding pressure to duration-sensitive assets."
        ),
        affectedAssets=["Treasury curve", "US dollar", "growth equities", "gold"],
        affectedSectors=["technology", "real estate", "utilities", "financials"],
        affectedThemes=["rates repricing", "duration sensitivity", "valuation discount rate"],
        triggerConditions=[
            "Policy-rate expectations move higher",
            "Long-end yields rise with real-rate pressure",
            "Dollar strength appears alongside tighter financial conditions",
        ],
        confirmingSignals=[
            "Growth leadership narrows as yields rise",
            "Rate-sensitive groups lag broader equities",
            "Credit spreads stay sensitive to yield shocks",
        ],
        invalidatingSignals=[
            "Yields stabilize without breadth damage",
            "Growth breadth improves despite rate pressure",
            "Dollar strength fades, which would weaken this monitoring case",
        ],
        evidenceQuality="needs_confirmation",
        dataQuality="deterministic",
    ),
    HomepageScenarioWatchlistScenario(
        scenarioName="AI capex continuation",
        description=(
            "A monitoring frame for whether AI infrastructure spend remains visible across the supply chain."
        ),
        affectedAssets=["mega-cap technology", "semiconductors", "cloud infrastructure", "power equipment"],
        affectedSectors=["semiconductors", "software", "electric equipment", "data-center infrastructure"],
        affectedThemes=["AI infrastructure spend", "compute demand", "capital expenditure cycle"],
        triggerConditions=[
            "Large-platform capex commentary remains firm",
            "Compute demand indicators stay broad",
            "Power and data-center constraints remain visible",
        ],
        confirmingSignals=[
            "Supplier demand visibility holds",
            "Semiconductor breadth extends beyond a few leaders",
            "Cloud and infrastructure commentary would need confirmation from margins",
        ],
        invalidatingSignals=[
            "Capex commentary turns more cautious",
            "Demand visibility weakens across infrastructure suppliers",
            "Margin pressure offsets revenue visibility",
        ],
        evidenceQuality="scenario_monitoring",
        dataQuality="deterministic",
    ),
    HomepageScenarioWatchlistScenario(
        scenarioName="Oil/geopolitical risk premium falling or rising",
        description=(
            "A monitoring frame for whether oil risk premium is cooling or rising with geopolitical stress."
        ),
        affectedAssets=["crude oil", "energy equities", "airlines", "gold", "inflation-linked assets"],
        affectedSectors=["energy", "transportation", "chemicals", "consumer discretionary"],
        affectedThemes=["oil risk premium", "geopolitical stress", "inflation sensitivity"],
        triggerConditions=[
            "Shipping or supply disruption risk changes",
            "Oil volatility moves with geopolitical headlines",
            "Inflation-expectation proxies react to energy moves",
        ],
        confirmingSignals=[
            "Energy leadership follows oil risk premium direction",
            "Cost-sensitive sectors react in the opposite direction",
            "Safe-haven demand would need confirmation from cross-asset signals",
        ],
        invalidatingSignals=[
            "Oil moves mainly reflect demand weakness",
            "Energy volatility fades without inflation follow-through",
            "Cross-asset safe-haven signals stay muted",
        ],
        evidenceQuality="mixed",
        dataQuality="deterministic",
    ),
    HomepageScenarioWatchlistScenario(
        scenarioName="Defensive rotation",
        description=(
            "A monitoring frame for whether defensive sectors are gaining relative resilience as risk appetite cools."
        ),
        affectedAssets=["equity indexes", "low-volatility equities", "Treasuries", "gold"],
        affectedSectors=["utilities", "consumer staples", "health care", "telecom"],
        affectedThemes=["defensive sectors", "risk appetite", "quality balance sheets"],
        triggerConditions=[
            "Volatility rises with weaker equity breadth",
            "Cyclical groups lag defensive groups",
            "Earnings sensitivity becomes a larger market focus",
        ],
        confirmingSignals=[
            "Defensive sectors outperform while index breadth narrows",
            "Low-volatility factors remain resilient",
            "Credit spreads stop tightening",
        ],
        invalidatingSignals=[
            "Cyclical breadth expands again",
            "Volatility fades without defensive leadership",
            "Equal-weight indexes recover relative strength",
        ],
        evidenceQuality="needs_confirmation",
        dataQuality="deterministic",
    ),
    HomepageScenarioWatchlistScenario(
        scenarioName="Liquidity or credit stress",
        description=(
            "A monitoring frame for whether liquidity or credit stress is tightening the market backdrop."
        ),
        affectedAssets=["credit indexes", "small caps", "regional banks", "high-beta equities", "US dollar"],
        affectedSectors=["financials", "real estate", "industrials", "materials"],
        affectedThemes=["liquidity conditions", "credit spreads", "funding pressure"],
        triggerConditions=[
            "Credit spreads widen with weaker small-cap breadth",
            "Funding-sensitive groups underperform",
            "Dollar strength appears with tighter liquidity signals",
        ],
        confirmingSignals=[
            "Market breadth weakens alongside credit spreads",
            "Financials lag while volatility rises",
            "Liquidity proxies would need confirmation from multiple assets",
        ],
        invalidatingSignals=[
            "Credit spreads normalize quickly",
            "Small caps recover relative strength",
            "Funding-sensitive groups stabilize",
        ],
        evidenceQuality="needs_confirmation",
        dataQuality="deterministic",
    ),
    HomepageScenarioWatchlistScenario(
        scenarioName="Breadth expansion or narrowing",
        description=(
            "A monitoring frame to watch whether market breadth expands beyond leaders or narrows again."
        ),
        affectedAssets=["equal-weight indexes", "small caps", "sector baskets", "thematic equities"],
        affectedSectors=["technology", "industrials", "consumer discretionary", "financials"],
        affectedThemes=["market breadth", "leadership diffusion", "theme participation"],
        triggerConditions=[
            "Equal-weight indexes diverge from capitalization-weighted indexes",
            "Sector participation changes across cyclical and defensive groups",
            "Theme participation broadens or contracts across market segments",
        ],
        confirmingSignals=[
            "More sectors participate in index moves",
            "Small caps confirm broader participation",
            "Theme breadth would need confirmation beyond mega-cap leadership",
        ],
        invalidatingSignals=[
            "Leadership stays concentrated in a few large components",
            "Equal-weight indexes fail to confirm index strength",
            "Sector participation fades after short-lived rotation",
        ],
        evidenceQuality="scenario_monitoring",
        dataQuality="deterministic",
    ),
)


class HomepageScenarioWatchlistService:
    """Build a static scenario watchlist without runtime dependencies."""

    def build_snapshot(self) -> HomepageScenarioWatchlistSnapshot:
        return HomepageScenarioWatchlistSnapshot(
            schemaVersion=HOMEPAGE_SCENARIO_WATCHLIST_SCHEMA_VERSION,
            asOf=HOMEPAGE_SCENARIO_WATCHLIST_DEFAULT_AS_OF,
            scenarios=list(_SCENARIOS),
            evidenceQuality="scenario_monitoring",
            dataQuality="deterministic",
            noAdviceDisclosure=HOMEPAGE_SCENARIO_WATCHLIST_NO_ADVICE_DISCLOSURE,
        )


__all__ = [
    "HOMEPAGE_SCENARIO_WATCHLIST_DEFAULT_AS_OF",
    "HOMEPAGE_SCENARIO_WATCHLIST_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_SCENARIO_WATCHLIST_SCHEMA_VERSION",
    "HomepageScenarioWatchlistService",
]
