# -*- coding: utf-8 -*-
"""Pure service for deterministic homepage geopolitical commodity risk monitoring."""

from __future__ import annotations

from api.v1.schemas.homepage_geopolitical_commodity_risk import (
    HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_DEFAULT_AS_OF,
    HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_SCHEMA_VERSION,
    HomepageGeopoliticalCommodityRiskDataQuality,
    HomepageGeopoliticalCommodityRiskScenario,
    HomepageGeopoliticalCommodityRiskSnapshot,
    HomepageGeopoliticalCommodityRiskVector,
)


_DATA_QUALITY_STATUS = "sample_proxy"
_EVIDENCE_QUALITY = "scenario_monitoring"

_OIL_RISING = HomepageGeopoliticalCommodityRiskScenario(
    scenarioName="Oil/geopolitical risk premium rising",
    researchLanguage=(
        "A research watch item for oil risk premium rising; it would need confirmation from "
        "energy volatility, cross-asset hedging demand, and inflation-sensitive pricing."
    ),
    affectedAssets=["crude oil", "energy equities", "gold", "inflation-linked assets"],
    affectedSectors=["energy", "transportation", "chemicals", "consumer discretionary"],
    affectedThemes=["geopolitical risk premium", "energy inflation sensitivity", "safe-haven demand"],
    evidenceQuality=_EVIDENCE_QUALITY,
    dataQuality=_DATA_QUALITY_STATUS,
)

_OIL_FALLING = HomepageGeopoliticalCommodityRiskScenario(
    scenarioName="Oil/geopolitical risk premium falling",
    researchLanguage=(
        "A research watch item for oil risk premium cooling; it would need confirmation from "
        "lower energy volatility and weaker inflation sensitivity rather than demand weakness."
    ),
    affectedAssets=["crude oil", "airlines", "consumer equities", "inflation-linked assets"],
    affectedSectors=["transportation", "consumer discretionary", "materials", "energy"],
    affectedThemes=["geopolitical risk premium", "commodity input pressure", "disinflation sensitivity"],
    evidenceQuality="needs_confirmation",
    dataQuality=_DATA_QUALITY_STATUS,
)

_SAFE_HAVEN_RISING = HomepageGeopoliticalCommodityRiskScenario(
    scenarioName="Safe-haven demand rising",
    researchLanguage=(
        "A research watch item for safe-haven demand rising; it does not forecast conflict, "
        "shipping, energy, or market outcomes and would need confirmation across assets."
    ),
    affectedAssets=["gold", "US dollar", "Treasury curve", "defensive equities"],
    affectedSectors=["utilities", "consumer staples", "health care", "defense"],
    affectedThemes=["safe-haven demand", "risk appetite cooling", "defensive resilience"],
    evidenceQuality=_EVIDENCE_QUALITY,
    dataQuality=_DATA_QUALITY_STATUS,
)

_SHIPPING_DISRUPTION = HomepageGeopoliticalCommodityRiskScenario(
    scenarioName="Shipping-route disruption risk",
    researchLanguage=(
        "A research watch item for shipping-route disruption risk; it would need confirmation "
        "from freight stress, delivery timing, and goods inflation sensitivity."
    ),
    affectedAssets=["shipping rates", "crude oil", "industrial metals", "global equities"],
    affectedSectors=["transportation", "retail", "industrials", "materials"],
    affectedThemes=["shipping-route disruption", "supply chain sensitivity", "goods inflation"],
    evidenceQuality="needs_confirmation",
    dataQuality=_DATA_QUALITY_STATUS,
)

_ENERGY_INFLATION_PRESSURE = HomepageGeopoliticalCommodityRiskScenario(
    scenarioName="Energy inflation pressure",
    researchLanguage=(
        "A research watch item for energy inflation pressure; it would need confirmation from "
        "oil products, inflation expectations, and cost-sensitive market areas."
    ),
    affectedAssets=["crude oil", "inflation-linked assets", "US dollar", "consumer equities"],
    affectedSectors=["energy", "transportation", "consumer discretionary", "materials"],
    affectedThemes=["energy inflation sensitivity", "commodity input pressure", "margin sensitivity"],
    evidenceQuality="needs_confirmation",
    dataQuality=_DATA_QUALITY_STATUS,
)

_GOLD_OIL_DIVERGENCE = HomepageGeopoliticalCommodityRiskScenario(
    scenarioName="Gold/oil divergence",
    researchLanguage=(
        "A research watch item for gold/oil divergence; it would need confirmation to separate "
        "safe-haven demand from energy-specific supply or demand signals."
    ),
    affectedAssets=["gold", "crude oil", "US dollar", "real-rate sensitive assets"],
    affectedSectors=["materials", "energy", "financials", "consumer discretionary"],
    affectedThemes=["safe-haven demand", "geopolitical risk premium", "cross-asset divergence"],
    evidenceQuality=_EVIDENCE_QUALITY,
    dataQuality=_DATA_QUALITY_STATUS,
)

_GEOPOLITICAL_RISK_PREMIUM = HomepageGeopoliticalCommodityRiskVector(
    key="geopolitical_risk_premium",
    label="Geopolitical risk premium",
    state="mixed",
    summary=(
        "Scenario monitoring frame for whether cross-asset pricing reflects a higher or lower "
        "geopolitical risk premium; sample proxy only."
    ),
    monitoringScenarios=[_OIL_RISING, _OIL_FALLING],
    confirmingSignals=[
        "Energy volatility moves with stronger safe-haven demand",
        "Cost-sensitive sectors react to energy and freight pressure",
        "Gold, dollar, and oil signals align with risk-premium stress",
    ],
    invalidatingSignals=[
        "Oil moves mainly reflect demand softness",
        "Safe-haven assets stay muted during energy moves",
        "Commodity pressure fades without cross-asset confirmation",
    ],
    evidenceQuality=_EVIDENCE_QUALITY,
    dataQuality=_DATA_QUALITY_STATUS,
)

_OIL_RISK_PREMIUM = HomepageGeopoliticalCommodityRiskVector(
    key="oil_risk_premium",
    label="Oil risk premium",
    state="monitoring",
    summary=(
        "Scenario monitoring for oil risk premium without asserting live energy or geopolitical "
        "conditions; sample proxy only."
    ),
    monitoringScenarios=[_OIL_RISING, _OIL_FALLING, _ENERGY_INFLATION_PRESSURE],
    confirmingSignals=[
        "Oil volatility and energy equities move together",
        "Inflation-linked assets react to energy pressure",
        "Transportation and consumer groups show cost sensitivity",
    ],
    invalidatingSignals=[
        "Energy moves reverse without inflation-sensitive follow-through",
        "Oil weakness appears tied to broad demand concerns",
        "Cost-sensitive groups do not respond to energy movement",
    ],
    evidenceQuality=_EVIDENCE_QUALITY,
    dataQuality=_DATA_QUALITY_STATUS,
)

_SAFE_HAVEN_DEMAND = HomepageGeopoliticalCommodityRiskVector(
    key="safe_haven_demand",
    label="Safe-haven demand",
    state="rising",
    summary=(
        "Scenario monitoring for defensive cross-asset demand; it does not assert live "
        "geopolitical or commodity data."
    ),
    monitoringScenarios=[_SAFE_HAVEN_RISING, _GOLD_OIL_DIVERGENCE],
    confirmingSignals=[
        "Gold demand strengthens while risk appetite cools",
        "Dollar and defensive sectors show resilience",
        "Treasury curve sensitivity appears alongside equity caution",
    ],
    invalidatingSignals=[
        "Gold strength reverses with stable risk appetite",
        "Defensive sectors lag while cyclicals broaden",
        "Cross-asset hedging demand does not broaden",
    ],
    evidenceQuality=_EVIDENCE_QUALITY,
    dataQuality=_DATA_QUALITY_STATUS,
)

_SHIPPING_RISK = HomepageGeopoliticalCommodityRiskVector(
    key="shipping_risk",
    label="Shipping risk",
    state="elevated",
    summary=(
        "Scenario monitoring for shipping-route disruption and freight sensitivity; sample "
        "proxy only and not a live logistics claim."
    ),
    monitoringScenarios=[_SHIPPING_DISRUPTION],
    confirmingSignals=[
        "Shipping rates and delivery timing indicators point to stress",
        "Import-sensitive groups show margin sensitivity",
        "Goods inflation watch items rise with freight pressure",
    ],
    invalidatingSignals=[
        "Freight stress fades without goods-price follow-through",
        "Retail and transportation groups stabilize",
        "Commodity pressure stays isolated from shipping-sensitive areas",
    ],
    evidenceQuality="needs_confirmation",
    dataQuality=_DATA_QUALITY_STATUS,
)

_COMMODITY_PRESSURE = HomepageGeopoliticalCommodityRiskVector(
    key="commodity_pressure",
    label="Commodity pressure",
    state="divergent",
    summary=(
        "Scenario monitoring for energy and materials input pressure, including gold/oil "
        "divergence and inflation sensitivity."
    ),
    monitoringScenarios=[_ENERGY_INFLATION_PRESSURE, _GOLD_OIL_DIVERGENCE],
    confirmingSignals=[
        "Energy and materials signals pressure cost-sensitive sectors",
        "Gold/oil divergence appears with a defensive market tone",
        "Inflation-sensitive pricing reacts to commodity pressure",
    ],
    invalidatingSignals=[
        "Commodity moves narrow to one market area",
        "Inflation-sensitive assets ignore energy pressure",
        "Gold and oil both fade without broader market stress",
    ],
    evidenceQuality=_EVIDENCE_QUALITY,
    dataQuality=_DATA_QUALITY_STATUS,
)


class HomepageGeopoliticalCommodityRiskService:
    """Build a static geopolitical commodity risk snapshot without runtime dependencies."""

    def build_snapshot(self) -> HomepageGeopoliticalCommodityRiskSnapshot:
        return HomepageGeopoliticalCommodityRiskSnapshot(
            schemaVersion=HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_SCHEMA_VERSION,
            asOf=HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_DEFAULT_AS_OF,
            riskWindow="next_1_to_4_weeks_scenario_monitoring",
            geopoliticalRiskPremium=_GEOPOLITICAL_RISK_PREMIUM,
            oilRiskPremium=_OIL_RISK_PREMIUM,
            safeHavenDemand=_SAFE_HAVEN_DEMAND,
            shippingRisk=_SHIPPING_RISK,
            commodityPressure=_COMMODITY_PRESSURE,
            affectedAssets=[
                "crude oil",
                "gold",
                "US dollar",
                "shipping rates",
                "inflation-linked assets",
                "Treasury curve",
                "energy equities",
                "consumer equities",
            ],
            affectedSectors=[
                "energy",
                "transportation",
                "materials",
                "consumer discretionary",
                "defense",
                "utilities",
                "consumer staples",
                "industrials",
            ],
            affectedThemes=[
                "geopolitical risk premium",
                "safe-haven demand",
                "commodity input pressure",
                "shipping-route disruption",
                "energy inflation sensitivity",
                "cross-asset divergence",
            ],
            confirmingSignals=[
                "Oil volatility aligns with safe-haven demand",
                "Shipping stress appears with goods inflation sensitivity",
                "Energy pressure reaches cost-sensitive sectors",
                "Gold and dollar resilience appear during risk appetite cooling",
            ],
            invalidatingSignals=[
                "Commodity moves stay isolated without cross-asset confirmation",
                "Shipping sensitivity fades without goods-price pressure",
                "Safe-haven demand cools while market breadth improves",
                "Oil movement looks more demand-led than risk-premium-led",
            ],
            watchPoints=[
                "Research watch item: compare oil, gold, and dollar direction",
                "Research watch item: separate energy pressure from broad demand weakness",
                "Research watch item: watch shipping-route disruption sensitivity",
                "Research watch item: monitor cost-sensitive sector reactions",
                "Research watch item: treat all observations as sample proxy monitoring",
            ],
            evidenceQuality=_EVIDENCE_QUALITY,
            dataQuality=HomepageGeopoliticalCommodityRiskDataQuality(
                status=_DATA_QUALITY_STATUS,
                label="sample proxy",
                summary=(
                    "Deterministic sample proxy; does not assert live geopolitical or commodity data."
                ),
            ),
            noAdviceDisclosure=HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_NO_ADVICE_DISCLOSURE,
        )


__all__ = [
    "HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_DEFAULT_AS_OF",
    "HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_GEOPOLITICAL_COMMODITY_RISK_SCHEMA_VERSION",
    "HomepageGeopoliticalCommodityRiskService",
]
