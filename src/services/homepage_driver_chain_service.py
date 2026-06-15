# -*- coding: utf-8 -*-
"""Pure service that emits a bounded homepage macro driver-chain contract."""

from __future__ import annotations

from api.v1.schemas.homepage_driver_chain import (
    HOMEPAGE_DRIVER_CHAIN_DEFAULT_AS_OF,
    HOMEPAGE_DRIVER_CHAIN_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_DRIVER_CHAIN_SCHEMA_VERSION,
    HomepageDriverChain,
    HomepageDriverChainSnapshot,
)


_DRIVER_CHAINS = (
    HomepageDriverChain(
        key="lower_yields_growth_duration",
        macroDriver="Lower yields",
        marketMechanism="Lower discount-rate pressure creates less pressure on growth valuation.",
        riskRegimeImplication="Nasdaq and growth assets improve when duration pressure eases.",
        affectedAssets=["Nasdaq", "growth assets", "long-duration equities"],
        affectedSectors=["semiconductors", "software"],
        affectedThemes=["AI infrastructure", "duration sensitivity", "quality growth"],
        researchImplication="Semiconductors, software, and AI infrastructure research priority rises.",
        confirmingEvidence=[
            "Ten-year yields continue moving lower",
            "Growth breadth improves beyond mega-cap leadership",
            "Credit spreads remain contained",
        ],
        missingEvidence=[
            "Sustained earnings revision support",
            "Broader participation across growth groups",
        ],
        contradiction="Sticky inflation or a yield rebound would weaken the growth-valuation link.",
        evidenceQuality="needs_confirmation",
        dataQuality="deterministic",
    ),
    HomepageDriverChain(
        key="oil_risk_premium_falls",
        macroDriver="Oil-risk premium falls",
        marketMechanism="Lower oil-risk premium means inflation pressure eases as policy concern cools.",
        riskRegimeImplication="Risk appetite improves when inflation pressure and energy stress cool.",
        affectedAssets=["gold", "energy-linked assets", "broad equities"],
        affectedSectors=["energy", "industrials", "consumer discretionary"],
        affectedThemes=["inflation sensitivity", "safe-haven demand", "cyclical demand"],
        researchImplication=(
            "When gold and energy safe-haven demand cools, cyclical research context improves."
        ),
        confirmingEvidence=[
            "Oil volatility cools after risk-premium compression",
            "Inflation expectations stop rising",
            "Defensive demand moderates across cross-asset signals",
        ],
        missingEvidence=[
            "Confirmation from realized inflation data",
            "Evidence that demand weakness is not the primary oil driver",
        ],
        contradiction="Oil weakness caused by growth concern would not support a cleaner risk-on reading.",
        evidenceQuality="mixed",
        dataQuality="deterministic",
    ),
    HomepageDriverChain(
        key="stronger_dollar_liquidity_pressure",
        macroDriver="Dollar strengthens",
        marketMechanism="A stronger dollar can tighten global liquidity conditions.",
        riskRegimeImplication=(
            "When liquidity pressure rises, small caps and emerging assets weaken."
        ),
        affectedAssets=["small caps", "emerging assets", "non-US equities"],
        affectedSectors=["financials", "materials", "consumer discretionary"],
        affectedThemes=["liquidity pressure", "domestic defensiveness", "global demand"],
        researchImplication="Defensive review priority rises until dollar pressure stabilizes.",
        confirmingEvidence=[
            "Dollar strength appears with higher real yields",
            "Small-cap relative strength weakens",
            "Emerging asset breadth deteriorates",
        ],
        missingEvidence=[
            "Funding stress confirmation",
            "Regional breadth data across emerging markets",
        ],
        contradiction="Dollar strength led by better growth can soften the liquidity-pressure reading.",
        evidenceQuality="needs_confirmation",
        dataQuality="deterministic",
    ),
    HomepageDriverChain(
        key="vix_rises_defensive_review",
        macroDriver="VIX rises",
        marketMechanism="Higher implied volatility signals weaker risk appetite.",
        riskRegimeImplication="When risk appetite weakens, defensive sectors outperform.",
        affectedAssets=["equity indexes", "volatility-linked assets", "growth assets"],
        affectedSectors=["utilities", "consumer staples", "health care"],
        affectedThemes=["defensive leadership", "risk premium", "growth confirmation"],
        researchImplication="Defensive review continues while growth exposure requires confirmation.",
        confirmingEvidence=[
            "Volatility rise is paired with weaker market breadth",
            "Defensive sectors show relative resilience",
            "Growth leadership narrows",
        ],
        missingEvidence=[
            "Whether volatility remains elevated",
            "Whether defensive leadership persists over time",
        ],
        contradiction="A brief volatility spike without breadth damage may be only a short-lived reset.",
        evidenceQuality="needs_confirmation",
        dataQuality="deterministic",
    ),
)


class HomepageDriverChainService:
    """Build deterministic macro-to-research causal chains without runtime dependencies."""

    def build_snapshot(self) -> HomepageDriverChainSnapshot:
        return HomepageDriverChainSnapshot(
            schemaVersion=HOMEPAGE_DRIVER_CHAIN_SCHEMA_VERSION,
            asOf=HOMEPAGE_DRIVER_CHAIN_DEFAULT_AS_OF,
            driverChains=list(_DRIVER_CHAINS),
            evidenceQuality="needs_confirmation",
            dataQuality="deterministic",
            noAdviceDisclosure=HOMEPAGE_DRIVER_CHAIN_NO_ADVICE_DISCLOSURE,
        )


__all__ = [
    "HOMEPAGE_DRIVER_CHAIN_DEFAULT_AS_OF",
    "HOMEPAGE_DRIVER_CHAIN_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_DRIVER_CHAIN_SCHEMA_VERSION",
    "HomepageDriverChainService",
]
