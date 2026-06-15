# -*- coding: utf-8 -*-
"""Pure service that emits a deterministic homepage earnings catalysts contract."""

from __future__ import annotations

from api.v1.schemas.homepage_earnings_catalysts import (
    HOMEPAGE_EARNINGS_CATALYSTS_DEFAULT_AS_OF,
    HOMEPAGE_EARNINGS_CATALYSTS_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_EARNINGS_CATALYSTS_SCHEMA_VERSION,
    HomepageEarningsCatalystObservation,
    HomepageEarningsCatalystWindow,
    HomepageEarningsCatalystsQuality,
    HomepageEarningsCatalystsSection,
    HomepageEarningsCatalystsSnapshot,
)


_COMMON_MISSING_EVIDENCE = [
    "No verified company calendar is attached",
    "No reported figures are attached",
    "No transcript excerpt is attached",
    "No market reaction measurement is attached",
]

_EARNINGS_CATALYSTS = (
    HomepageEarningsCatalystObservation(
        key="large_platform_results_proxy",
        label="Large platform results sample",
        category="earnings_observation",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="Fixed sample frame for watching whether large platform reports reshape index-level research questions.",
        researchContext="The observation stays conditional until verified filings, call notes, and market reaction evidence are attached.",
        affectedAssets=["mega-cap equities", "index baskets", "cloud suppliers", "semiconductor basket"],
        affectedSectors=["technology", "communication services", "semiconductors"],
        affectedThemes=["platform margins", "AI infrastructure spend", "index concentration"],
        confirmationSignals=[
            "Verified revenue quality evidence",
            "Margin bridge evidence",
            "Cash-flow commentary evidence",
            "Observed index breadth response",
        ],
        missingEvidence=list(_COMMON_MISSING_EVIDENCE),
        watchPoints=["Margin durability", "Capex commentary", "Supplier demand visibility"],
    ),
    HomepageEarningsCatalystObservation(
        key="industrial_guidance_proxy",
        label="Industrial outlook sample",
        category="guidance_sensitivity",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="Fixed sample frame for watching whether outlook language changes cyclicals research questions.",
        researchContext="The contract does not include live management commentary or verified backlog data.",
        affectedAssets=["industrial equities", "transportation basket", "credit indexes"],
        affectedSectors=["industrials", "materials", "transportation"],
        affectedThemes=["cyclical demand", "operating leverage", "backlog visibility"],
        confirmationSignals=[
            "Verified backlog commentary",
            "Observed margin commentary",
            "Demand sensitivity evidence",
        ],
        missingEvidence=list(_COMMON_MISSING_EVIDENCE),
        watchPoints=["Backlog tone", "Input cost language", "Credit sensitivity"],
    ),
    HomepageEarningsCatalystObservation(
        key="consumer_read_through_proxy",
        label="Consumer demand sample",
        category="sector_read_through",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="Fixed sample frame for watching whether consumer reports affect broader demand research.",
        researchContext="The sample is a research placeholder and carries no live retail, payment, or survey evidence.",
        affectedAssets=["consumer equities", "retail basket", "payment networks"],
        affectedSectors=["consumer discretionary", "consumer staples", "financial services"],
        affectedThemes=["consumer resilience", "pricing power", "spending mix"],
        confirmationSignals=[
            "Verified same-store sales evidence",
            "Margin and inventory evidence",
            "Observed breadth response across consumer groups",
        ],
        missingEvidence=list(_COMMON_MISSING_EVIDENCE),
        watchPoints=["Demand quality", "Inventory language", "Pricing power context"],
    ),
    HomepageEarningsCatalystObservation(
        key="ai_supply_chain_proxy",
        label="AI supply-chain sample",
        category="theme_read_through",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="Fixed sample frame for watching whether compute demand evidence broadens across suppliers.",
        researchContext="The observation requires verified demand, capacity, and margin evidence before research confidence can rise.",
        affectedAssets=["semiconductors", "power equipment", "data-center infrastructure"],
        affectedSectors=["semiconductors", "electric equipment", "software"],
        affectedThemes=["compute demand", "power constraints", "AI infrastructure spend"],
        confirmationSignals=[
            "Verified supplier demand evidence",
            "Capacity constraint evidence",
            "Observed theme participation beyond a few leaders",
        ],
        missingEvidence=list(_COMMON_MISSING_EVIDENCE),
        watchPoints=["Demand breadth", "Capacity constraints", "Theme participation"],
    ),
)

_GUIDANCE_SENSITIVITY = (
    HomepageEarningsCatalystObservation(
        key="margin_outlook_proxy",
        label="Margin outlook sample",
        category="guidance_sensitivity",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="Fixed sample frame for watching whether outlook language changes margin sensitivity research.",
        researchContext="No verified company outlook statement is attached to this standalone service.",
        affectedAssets=["growth equities", "quality factor basket"],
        affectedSectors=["technology", "industrials", "consumer discretionary"],
        affectedThemes=["margin durability", "operating leverage", "input cost sensitivity"],
        confirmationSignals=["Verified outlook statement", "Margin bridge evidence", "Observed sector breadth response"],
        missingEvidence=list(_COMMON_MISSING_EVIDENCE),
        watchPoints=["Margin bridge", "Cost language", "Demand elasticity"],
    ),
    HomepageEarningsCatalystObservation(
        key="capex_outlook_proxy",
        label="Capex outlook sample",
        category="guidance_sensitivity",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="Fixed sample frame for watching whether capital spending plans affect supplier research.",
        researchContext="No live spending plan or supplier demand evidence is attached to this contract.",
        affectedAssets=["cloud infrastructure", "semiconductor equipment", "power equipment"],
        affectedSectors=["semiconductors", "electric equipment", "software"],
        affectedThemes=["capital spending cycle", "AI infrastructure spend", "supply constraints"],
        confirmationSignals=["Verified capex language", "Supplier demand evidence", "Capacity timeline evidence"],
        missingEvidence=list(_COMMON_MISSING_EVIDENCE),
        watchPoints=["Spending cadence", "Supplier visibility", "Capacity timing"],
    ),
)

_MEGA_CAP_IMPACT = (
    HomepageEarningsCatalystObservation(
        key="index_weight_proxy",
        label="Index weight sample",
        category="mega_cap_report",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="Fixed sample frame for watching whether mega-cap reports affect index concentration research.",
        researchContext="The contract does not include actual index contribution or post-report performance measurement.",
        affectedAssets=["capitalization-weighted indexes", "equal-weight indexes", "mega-cap equities"],
        affectedSectors=["technology", "communication services", "consumer discretionary"],
        affectedThemes=["index concentration", "leadership breadth", "earnings quality"],
        confirmationSignals=["Observed index contribution", "Equal-weight confirmation", "Verified report quality evidence"],
        missingEvidence=list(_COMMON_MISSING_EVIDENCE),
        watchPoints=["Index concentration", "Breadth confirmation", "Quality evidence"],
    ),
)

_SECTOR_READ_THROUGH = (
    HomepageEarningsCatalystObservation(
        key="semiconductor_read_through_proxy",
        label="Semiconductor read-through sample",
        category="sector_read_through",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="Fixed sample frame for watching whether component reports affect broader semiconductor research.",
        researchContext="The section requires verified demand, inventory, and pricing evidence before raising confidence.",
        affectedAssets=["semiconductor basket", "equipment makers", "cloud infrastructure"],
        affectedSectors=["semiconductors", "technology hardware", "electric equipment"],
        affectedThemes=["inventory cycle", "compute demand", "supplier visibility"],
        confirmationSignals=["Verified inventory evidence", "Demand visibility evidence", "Observed supplier breadth response"],
        missingEvidence=list(_COMMON_MISSING_EVIDENCE),
        watchPoints=["Inventory posture", "Demand breadth", "Supplier reaction"],
    ),
    HomepageEarningsCatalystObservation(
        key="financials_read_through_proxy",
        label="Financials read-through sample",
        category="sector_read_through",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="Fixed sample frame for watching whether lender reports affect credit and rate sensitivity research.",
        researchContext="No verified net-interest, credit-cost, or deposit evidence is attached to this contract.",
        affectedAssets=["bank equities", "credit indexes", "yield curve"],
        affectedSectors=["financials", "real estate", "small caps"],
        affectedThemes=["credit conditions", "deposit sensitivity", "rate transmission"],
        confirmationSignals=["Verified credit-cost evidence", "Deposit trend evidence", "Observed credit spread response"],
        missingEvidence=list(_COMMON_MISSING_EVIDENCE),
        watchPoints=["Credit quality", "Deposit stability", "Rate sensitivity"],
    ),
)

_THEME_READ_THROUGH = (
    HomepageEarningsCatalystObservation(
        key="ai_infrastructure_theme_proxy",
        label="AI infrastructure theme sample",
        category="theme_read_through",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="Fixed sample frame for watching whether reports support or weaken AI infrastructure research breadth.",
        researchContext="Theme confidence stays limited until multiple verified reports and observed breadth evidence align.",
        affectedAssets=["AI infrastructure basket", "power equipment", "cloud platforms"],
        affectedSectors=["semiconductors", "software", "electric equipment"],
        affectedThemes=["AI infrastructure spend", "compute demand", "power constraints"],
        confirmationSignals=["Verified multi-company evidence", "Observed supplier breadth", "Capacity evidence"],
        missingEvidence=list(_COMMON_MISSING_EVIDENCE),
        watchPoints=["Breadth beyond leaders", "Power constraints", "Capacity cadence"],
    ),
    HomepageEarningsCatalystObservation(
        key="consumer_resilience_theme_proxy",
        label="Consumer resilience theme sample",
        category="theme_read_through",
        basis="sample_proxy",
        evidenceState="sample_proxy",
        observation="Fixed sample frame for watching whether reports clarify consumer demand resilience.",
        researchContext="The section is a sample proxy and contains no verified transaction or survey evidence.",
        affectedAssets=["consumer basket", "payment networks", "retail equities"],
        affectedSectors=["consumer discretionary", "consumer staples", "financial services"],
        affectedThemes=["consumer resilience", "pricing power", "spending mix"],
        confirmationSignals=["Verified demand evidence", "Margin evidence", "Observed sector participation"],
        missingEvidence=list(_COMMON_MISSING_EVIDENCE),
        watchPoints=["Demand mix", "Pricing power", "Participation breadth"],
    ),
)


class HomepageEarningsCatalystsService:
    """Build a static earnings catalysts snapshot without runtime dependencies."""

    def build_snapshot(self) -> HomepageEarningsCatalystsSnapshot:
        return HomepageEarningsCatalystsSnapshot(
            schemaVersion=HOMEPAGE_EARNINGS_CATALYSTS_SCHEMA_VERSION,
            asOf=HOMEPAGE_EARNINGS_CATALYSTS_DEFAULT_AS_OF,
            catalystWindow=HomepageEarningsCatalystWindow(
                label="Upcoming earnings research window sample",
                startsAt="2026-06-15T00:00:00Z",
                endsAt="2026-06-22T00:00:00Z",
                basis="sample_proxy",
                summary="Fixed sample window for organizing research observations; it is not a live earnings calendar.",
            ),
            earningsCatalysts=list(_EARNINGS_CATALYSTS),
            guidanceSensitivity=HomepageEarningsCatalystsSection(
                state="sample_proxy",
                summary="Fixed sample section for observing how outlook language could affect research sensitivity.",
                observations=list(_GUIDANCE_SENSITIVITY),
            ),
            megaCapImpact=HomepageEarningsCatalystsSection(
                state="sample_proxy",
                summary="Fixed sample section for observing how mega-cap reports could affect index-level research.",
                observations=list(_MEGA_CAP_IMPACT),
            ),
            sectorReadThrough=HomepageEarningsCatalystsSection(
                state="sample_proxy",
                summary="Fixed sample section for observing sector read-through paths from company reports.",
                observations=list(_SECTOR_READ_THROUGH),
            ),
            themeReadThrough=HomepageEarningsCatalystsSection(
                state="sample_proxy",
                summary="Fixed sample section for observing whether themes gain broader research support.",
                observations=list(_THEME_READ_THROUGH),
            ),
            affectedAssets=[
                "mega-cap equities",
                "capitalization-weighted indexes",
                "equal-weight indexes",
                "semiconductor basket",
                "credit indexes",
                "consumer basket",
            ],
            affectedSectors=[
                "technology",
                "communication services",
                "semiconductors",
                "industrials",
                "financials",
                "consumer discretionary",
            ],
            affectedThemes=[
                "AI infrastructure spend",
                "index concentration",
                "margin durability",
                "consumer resilience",
                "credit conditions",
                "leadership breadth",
            ],
            confirmationSignals=[
                "Verified reported figures",
                "Verified management commentary",
                "Observed index breadth response",
                "Observed sector participation",
                "Multiple-company evidence alignment",
            ],
            missingEvidence=[
                "No verified company calendar is attached",
                "No reported figures are attached",
                "No transcript excerpt is attached",
                "No live news evidence is attached",
                "No market reaction measurement is attached",
            ],
            watchPoints=[
                "Margin durability",
                "Outlook language",
                "Mega-cap index concentration",
                "Sector breadth response",
                "Theme participation breadth",
            ],
            evidenceQuality=HomepageEarningsCatalystsQuality(
                state="sample_proxy",
                label="Sample proxy evidence",
                summary="This standalone contract uses fixed research observations and does not claim live earnings or news data.",
            ),
            dataQuality=HomepageEarningsCatalystsQuality(
                state="sample_proxy",
                label="Deterministic sample data",
                summary="All catalyst observations are deterministic placeholders until verified evidence is attached.",
            ),
            noAdviceDisclosure=HOMEPAGE_EARNINGS_CATALYSTS_NO_ADVICE_DISCLOSURE,
        )


__all__ = [
    "HOMEPAGE_EARNINGS_CATALYSTS_DEFAULT_AS_OF",
    "HOMEPAGE_EARNINGS_CATALYSTS_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_EARNINGS_CATALYSTS_SCHEMA_VERSION",
    "HomepageEarningsCatalystsService",
]
