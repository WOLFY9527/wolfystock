# -*- coding: utf-8 -*-
"""Pure service that emits a deterministic homepage Policy and Regulation Watch contract."""

from __future__ import annotations

from api.v1.schemas.homepage_policy_regulation_watch import (
    HOMEPAGE_POLICY_REGULATION_WATCH_DEFAULT_AS_OF,
    HOMEPAGE_POLICY_REGULATION_WATCH_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_POLICY_REGULATION_WATCH_SCHEMA_VERSION,
    HomepagePolicyRegulationWatchContext,
    HomepagePolicyRegulationWatchEvent,
    HomepagePolicyRegulationWatchQuality,
    HomepagePolicyRegulationWatchSnapshot,
    HomepagePolicyRegulationWatchWindow,
)


_POLICY_EVENTS = (
    HomepagePolicyRegulationWatchEvent(
        category="Fed communication",
        observation=(
            "Sample proxy for central-bank communication sensitivity; needs confirmation from current releases."
        ),
        marketArea="Rates, dollar, equity duration, and risk appetite",
        affectedAssets=["Treasury curve", "US dollar", "growth equities", "gold"],
        affectedSectors=["technology", "real estate", "utilities", "financials"],
        affectedThemes=["central-bank communication", "duration sensitivity", "liquidity expectations"],
        evidenceState="sample_proxy",
    ),
    HomepagePolicyRegulationWatchEvent(
        category="Treasury issuance / auction pressure",
        observation=(
            "Sample proxy for supply pressure around issuance and auctions; not connected to current calendars."
        ),
        marketArea="Yield curve, funding conditions, and rate-sensitive equity groups",
        affectedAssets=["Treasury curve", "money-market rates", "banks", "small caps"],
        affectedSectors=["financials", "real estate", "industrials", "utilities"],
        affectedThemes=["auction pressure", "term premium", "funding liquidity"],
        evidenceState="sample_proxy",
    ),
    HomepagePolicyRegulationWatchEvent(
        category="fiscal spending",
        observation=(
            "Sample proxy for fiscal impulse research context; no current budget release evidence is attached."
        ),
        marketArea="Demand-sensitive sectors, inflation expectations, and credit backdrop",
        affectedAssets=["equity indexes", "Treasuries", "credit indexes", "inflation-linked assets"],
        affectedSectors=["industrials", "materials", "consumer discretionary", "health care"],
        affectedThemes=["fiscal impulse", "public spending mix", "inflation sensitivity"],
        evidenceState="sample_proxy",
    ),
    HomepagePolicyRegulationWatchEvent(
        category="industrial policy",
        observation=(
            "Sample proxy for policy-linked capital allocation themes; needs confirmation from current programs."
        ),
        marketArea="Semiconductors, infrastructure, reshoring, and strategic supply chains",
        affectedAssets=["semiconductors", "industrial equities", "infrastructure baskets", "materials"],
        affectedSectors=["semiconductors", "capital goods", "electric equipment", "materials"],
        affectedThemes=["reshoring", "strategic supply chains", "public-private investment"],
        evidenceState="sample_proxy",
    ),
    HomepagePolicyRegulationWatchEvent(
        category="China policy support",
        observation=(
            "Sample proxy for China support monitoring; no current official announcement evidence is attached."
        ),
        marketArea="China growth proxies, commodities, regional equities, and global cyclicals",
        affectedAssets=["China equities", "industrial metals", "luxury equities", "Asia FX"],
        affectedSectors=["materials", "industrials", "consumer discretionary", "financials"],
        affectedThemes=["China policy support", "growth stabilization", "commodity demand"],
        evidenceState="sample_proxy",
    ),
)

_REGULATION_EVENTS = (
    HomepagePolicyRegulationWatchEvent(
        category="AI regulation",
        observation=(
            "Sample proxy for AI oversight discussion; not connected to current rulemaking records."
        ),
        marketArea="AI infrastructure, software platforms, model governance, and data usage",
        affectedAssets=["AI infrastructure", "software platforms", "semiconductors", "cloud infrastructure"],
        affectedSectors=["software", "semiconductors", "internet platforms", "data-center infrastructure"],
        affectedThemes=["AI governance", "model oversight", "data compliance"],
        evidenceState="sample_proxy",
    ),
    HomepagePolicyRegulationWatchEvent(
        category="energy policy",
        observation=(
            "Sample proxy for energy-policy sensitivity; current permitting or supply actions are not connected."
        ),
        marketArea="Energy supply, power demand, inflation channels, and transition infrastructure",
        affectedAssets=["energy equities", "power equipment", "crude oil", "utilities"],
        affectedSectors=["energy", "utilities", "electric equipment", "transportation"],
        affectedThemes=["energy security", "power demand", "transition infrastructure"],
        evidenceState="sample_proxy",
    ),
    HomepagePolicyRegulationWatchEvent(
        category="market-structure regulation",
        observation=(
            "Sample proxy for market-structure rule sensitivity; current rule text is unavailable in this contract."
        ),
        marketArea="Exchanges, market makers, liquidity, and market quality research",
        affectedAssets=["exchange operators", "capital-markets equities", "market-maker exposure", "equity indexes"],
        affectedSectors=["financials", "capital markets", "fintech", "asset managers"],
        affectedThemes=["market structure", "liquidity formation", "clearing and settlement"],
        evidenceState="sample_proxy",
    ),
)


class HomepagePolicyRegulationWatchService:
    """Build deterministic policy and regulation observations without runtime dependencies."""

    def build_snapshot(self) -> HomepagePolicyRegulationWatchSnapshot:
        return HomepagePolicyRegulationWatchSnapshot(
            schemaVersion=HOMEPAGE_POLICY_REGULATION_WATCH_SCHEMA_VERSION,
            asOf=HOMEPAGE_POLICY_REGULATION_WATCH_DEFAULT_AS_OF,
            policyWindow=HomepagePolicyRegulationWatchWindow(
                label="Static policy watch window",
                scope="Sample proxy only; not connected to current policy releases or real policy/news data.",
                evidenceState="sample_proxy",
            ),
            policyEvents=list(_POLICY_EVENTS),
            regulationEvents=list(_REGULATION_EVENTS),
            monetaryPolicyContext=HomepagePolicyRegulationWatchContext(
                label="Central-bank communication context",
                observation="Observation-only view of how central-bank language could affect market expectations.",
                marketTransmission="Rates, dollar, credit, and equity duration are the affected market areas.",
                evidenceState="sample_proxy",
            ),
            fiscalPolicyContext=HomepagePolicyRegulationWatchContext(
                label="Fiscal policy context",
                observation="Observation-only view of spending mix, issuance needs, and demand-sensitive sectors.",
                marketTransmission="Treasury supply, inflation expectations, credit, and cyclicals need confirmation.",
                evidenceState="sample_proxy",
            ),
            industrialPolicyContext=HomepagePolicyRegulationWatchContext(
                label="Industrial policy context",
                observation="Observation-only view of policy-linked capital allocation and supply-chain themes.",
                marketTransmission="Semiconductors, infrastructure, energy equipment, and materials need confirmation.",
                evidenceState="sample_proxy",
            ),
            affectedAssets=[
                "Treasury curve",
                "US dollar",
                "equity indexes",
                "growth equities",
                "credit indexes",
                "commodities",
                "China equities",
                "energy equities",
            ],
            affectedSectors=[
                "technology",
                "financials",
                "industrials",
                "materials",
                "energy",
                "utilities",
                "consumer discretionary",
                "semiconductors",
            ],
            affectedThemes=[
                "central-bank communication",
                "Treasury supply pressure",
                "fiscal impulse",
                "industrial policy",
                "AI governance",
                "energy security",
                "China policy support",
                "market structure",
            ],
            confidence="low",
            missingEvidence=[
                "Current policy release calendar",
                "Current central-bank remarks",
                "Current auction schedule and demand statistics",
                "Current fiscal budget details",
                "Current regulatory rule text",
                "Current implementation timelines",
            ],
            watchPoints=[
                "Whether central-bank communication changes financial-condition expectations",
                "Whether Treasury supply pressure affects rates and funding conditions",
                "Whether fiscal spending changes sector-level demand sensitivity",
                "Whether AI or energy rulemaking changes compliance-sensitive themes",
                "Whether China support language affects global cyclicals and commodities",
                "Whether market-structure discussion affects liquidity research context",
            ],
            evidenceQuality=HomepagePolicyRegulationWatchQuality(
                state="sample_proxy",
                label="Sample proxy evidence",
                summary="Deterministic research context; not connected to current policy releases.",
            ),
            dataQuality=HomepagePolicyRegulationWatchQuality(
                state="sample_proxy",
                label="Static contract data",
                summary="Fixed sample proxy for contract testing; no current policy/news data is claimed.",
            ),
            noAdviceDisclosure=HOMEPAGE_POLICY_REGULATION_WATCH_NO_ADVICE_DISCLOSURE,
        )


__all__ = [
    "HOMEPAGE_POLICY_REGULATION_WATCH_DEFAULT_AS_OF",
    "HOMEPAGE_POLICY_REGULATION_WATCH_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_POLICY_REGULATION_WATCH_SCHEMA_VERSION",
    "HomepagePolicyRegulationWatchService",
]
