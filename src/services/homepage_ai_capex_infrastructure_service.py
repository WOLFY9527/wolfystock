# -*- coding: utf-8 -*-
"""Pure service that emits a deterministic homepage AI infrastructure monitor."""

from __future__ import annotations

from api.v1.schemas.homepage_ai_capex_infrastructure import (
    HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_DEFAULT_AS_OF,
    HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_NO_ADVICE_DISCLOSURE,
    HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_SCHEMA_VERSION,
    HomepageAICapexInfrastructureQuality,
    HomepageAICapexInfrastructureSection,
    HomepageAICapexInfrastructureSignal,
    HomepageAICapexInfrastructureSnapshot,
    HomepageAICapexInfrastructureWindow,
)


_REQUIRED_THEMES = [
    "AI infrastructure",
    "semiconductors",
    "data centers",
    "power equipment",
    "liquid cooling",
    "grid infrastructure",
    "optical networking",
    "software infrastructure",
    "cybersecurity",
    "cloud / compute capacity",
]

_AFFECTED_SECTORS = [
    "semiconductors",
    "data-center infrastructure",
    "electric equipment",
    "thermal management",
    "network equipment",
    "cloud infrastructure",
    "software infrastructure",
    "cybersecurity",
]

_CAPEX_SIGNAL = HomepageAICapexInfrastructureSignal(
    key="ai_infrastructure_capex_frame",
    label="AI infrastructure capex monitoring frame",
    evidenceState="sample_proxy",
    observation=(
        "This fixed sample organizes AI infrastructure capex demand without claiming actual spend data."
    ),
    researchContext=(
        "The research question is whether compute, facilities, power, and network capacity would need confirmation together."
    ),
    relatedThemes=["AI infrastructure", "data centers", "cloud / compute capacity"],
)

_DEMAND_SIGNALS = (
    HomepageAICapexInfrastructureSignal(
        key="compute_capacity_demand",
        label="Compute capacity demand",
        evidenceState="sample_proxy",
        observation="Fixed sample demand focuses on accelerator capacity and cloud / compute capacity needs.",
        researchContext="This monitoring frame does not claim current utilization or contracted capacity.",
        relatedThemes=["cloud / compute capacity", "semiconductors"],
    ),
    HomepageAICapexInfrastructureSignal(
        key="data_center_pipeline",
        label="Data-center pipeline demand",
        evidenceState="sample_proxy",
        observation="Fixed sample demand highlights facility planning as a research theme.",
        researchContext="Facility demand would need confirmation from permitting, power access, and project milestones.",
        relatedThemes=["data centers", "grid infrastructure"],
    ),
    HomepageAICapexInfrastructureSignal(
        key="software_infrastructure_load",
        label="Software infrastructure load",
        evidenceState="sample_proxy",
        observation="Fixed sample demand includes orchestration, observability, and platform reliability needs.",
        researchContext="Software infrastructure demand would need confirmation from workload growth and resilience signals.",
        relatedThemes=["software infrastructure", "cybersecurity"],
    ),
)

_SUPPLY_CONSTRAINTS = (
    HomepageAICapexInfrastructureSignal(
        key="accelerator_availability",
        label="Accelerator availability",
        evidenceState="sample_proxy",
        observation="Fixed sample constraint tracks whether compute supply availability remains a bottleneck theme.",
        researchContext="The signal is a research placeholder and does not claim shipment or allocation data.",
        relatedThemes=["semiconductors", "cloud / compute capacity"],
    ),
    HomepageAICapexInfrastructureSignal(
        key="power_access_constraint",
        label="Power access constraint",
        evidenceState="sample_proxy",
        observation="Fixed sample constraint highlights power access as a key condition for data-center expansion.",
        researchContext="Power access would need confirmation from interconnect queues and capacity planning evidence.",
        relatedThemes=["power equipment", "grid infrastructure"],
    ),
    HomepageAICapexInfrastructureSignal(
        key="thermal_density_constraint",
        label="Thermal density constraint",
        evidenceState="sample_proxy",
        observation="Fixed sample constraint watches whether higher rack density increases liquid cooling research focus.",
        researchContext="Cooling demand would need confirmation from deployment mix and facility design evidence.",
        relatedThemes=["liquid cooling", "data centers"],
    ),
)

_COMPUTE_SUPPLY_CHAIN = (
    HomepageAICapexInfrastructureSignal(
        key="semiconductor_capacity",
        label="Semiconductor capacity",
        evidenceState="sample_proxy",
        observation="Fixed sample supply-chain item tracks accelerator, memory, and packaging capacity themes.",
        researchContext="It does not claim current backlog, pricing, or production volume.",
        relatedThemes=["semiconductors"],
    ),
    HomepageAICapexInfrastructureSignal(
        key="optical_networking_capacity",
        label="Optical networking capacity",
        evidenceState="sample_proxy",
        observation="Fixed sample supply-chain item tracks optical networking needs for cluster scale-out.",
        researchContext="Networking demand would need confirmation from architecture mix and capacity planning evidence.",
        relatedThemes=["optical networking", "data centers"],
    ),
    HomepageAICapexInfrastructureSignal(
        key="power_equipment_capacity",
        label="Power equipment capacity",
        evidenceState="sample_proxy",
        observation="Fixed sample supply-chain item tracks transformers, switchgear, and backup power themes.",
        researchContext="Equipment tightness would need confirmation from availability schedules and project timelines.",
        relatedThemes=["power equipment", "grid infrastructure"],
    ),
    HomepageAICapexInfrastructureSignal(
        key="cybersecurity_capacity",
        label="Cybersecurity capacity",
        evidenceState="sample_proxy",
        observation="Fixed sample supply-chain item includes identity, data protection, and workload security themes.",
        researchContext="Cybersecurity needs would need confirmation from deployment architecture and risk controls.",
        relatedThemes=["cybersecurity", "software infrastructure"],
    ),
)

_DATA_CENTER_WATCH_POINTS = (
    HomepageAICapexInfrastructureSignal(
        key="facility_pipeline_timing",
        label="Facility pipeline timing",
        evidenceState="sample_proxy",
        observation="Watch whether facility planning, power access, and compute timing remain aligned.",
        researchContext="Misalignment would be a research question for demand timing, not a direction signal.",
        relatedThemes=["data centers"],
    ),
)

_POWER_WATCH_POINTS = (
    HomepageAICapexInfrastructureSignal(
        key="power_availability_timing",
        label="Power availability timing",
        evidenceState="sample_proxy",
        observation="Watch whether power equipment availability remains visible enough to support planned capacity.",
        researchContext="The monitor treats this as infrastructure availability, not a valuation conclusion.",
        relatedThemes=["power equipment", "grid infrastructure"],
    ),
)

_LIQUID_COOLING_WATCH_POINTS = (
    HomepageAICapexInfrastructureSignal(
        key="cooling_density_mix",
        label="Cooling density mix",
        evidenceState="sample_proxy",
        observation="Watch whether rack-density assumptions increase liquid cooling relevance.",
        researchContext="The theme would need confirmation from facility design and deployment mix.",
        relatedThemes=["liquid cooling", "data centers"],
    ),
)

_GRID_WATCH_POINTS = (
    HomepageAICapexInfrastructureSignal(
        key="grid_interconnect_queue",
        label="Grid interconnect queue",
        evidenceState="sample_proxy",
        observation="Watch whether interconnect timing becomes a limiting condition for compute expansion.",
        researchContext="Grid constraints would need confirmation from capacity planning and power availability evidence.",
        relatedThemes=["grid infrastructure", "power equipment"],
    ),
)

_CONFIRMATION_SIGNALS = (
    HomepageAICapexInfrastructureSignal(
        key="capex_commentary_confirmation",
        label="Capex commentary confirmation",
        evidenceState="sample_proxy",
        observation="Confirmation would require consistent research evidence across capex plans and capacity needs.",
        researchContext="This fixed sample does not claim fresh company commentary or current news.",
        relatedThemes=["AI infrastructure", "cloud / compute capacity"],
    ),
    HomepageAICapexInfrastructureSignal(
        key="supply_chain_alignment",
        label="Supply-chain alignment",
        evidenceState="sample_proxy",
        observation="Confirmation would look for compute, networking, power, and cooling capacity signals together.",
        researchContext="Single-theme movement is treated as incomplete evidence in this monitoring frame.",
        relatedThemes=["semiconductors", "optical networking", "power equipment", "liquid cooling"],
    ),
)

_MISSING_EVIDENCE = (
    HomepageAICapexInfrastructureSignal(
        key="no_actual_spend_data",
        label="Actual capex data unavailable",
        evidenceState="no_evidence",
        observation="The snapshot has no actual capex figures and should be read as a fixed sample.",
        researchContext="Any public use should retain sample_proxy or no_evidence markers until evidence is added.",
        relatedThemes=["AI infrastructure"],
    ),
    HomepageAICapexInfrastructureSignal(
        key="no_current_capacity_data",
        label="Current capacity evidence unavailable",
        evidenceState="no_evidence",
        observation="The snapshot has no current capacity, timing, or utilization evidence.",
        researchContext="Capacity claims would need independent confirmation before becoming a factual statement.",
        relatedThemes=["cloud / compute capacity", "data centers"],
    ),
)

_WATCH_POINTS = (
    HomepageAICapexInfrastructureSignal(
        key="capex_to_power_alignment",
        label="Capex and power alignment",
        evidenceState="sample_proxy",
        observation="Watch whether infrastructure demand is matched by power and grid availability.",
        researchContext="The monitor frames a research question and avoids investment conclusions.",
        relatedThemes=["AI infrastructure", "power equipment", "grid infrastructure"],
    ),
    HomepageAICapexInfrastructureSignal(
        key="compute_to_network_alignment",
        label="Compute and network alignment",
        evidenceState="sample_proxy",
        observation="Watch whether compute expansion needs are matched by optical networking and software capacity.",
        researchContext="The theme would need confirmation across multiple infrastructure layers.",
        relatedThemes=["semiconductors", "optical networking", "software infrastructure"],
    ),
    HomepageAICapexInfrastructureSignal(
        key="security_and_resilience",
        label="Security and resilience",
        evidenceState="sample_proxy",
        observation="Watch whether larger AI infrastructure footprints raise cybersecurity and resilience requirements.",
        researchContext="Security relevance is a monitoring theme, not a product or company claim.",
        relatedThemes=["cybersecurity", "software infrastructure"],
    ),
)


class HomepageAICapexInfrastructureService:
    """Build a static AI infrastructure monitor snapshot without runtime dependencies."""

    def build_snapshot(self) -> HomepageAICapexInfrastructureSnapshot:
        return HomepageAICapexInfrastructureSnapshot(
            schemaVersion=HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_SCHEMA_VERSION,
            asOf=HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_DEFAULT_AS_OF,
            monitorWindow=HomepageAICapexInfrastructureWindow(
                label="AI infrastructure monitor window",
                startsAt="2026-06-15T00:00:00Z",
                endsAt="2026-06-15T23:59:59Z",
                basis="sample_proxy",
                summary="Fixed sample window for organizing AI infrastructure research themes.",
            ),
            capexSignal=_CAPEX_SIGNAL,
            demandSignals=list(_DEMAND_SIGNALS),
            supplyConstraints=list(_SUPPLY_CONSTRAINTS),
            computeSupplyChain=list(_COMPUTE_SUPPLY_CHAIN),
            dataCenterDemand=HomepageAICapexInfrastructureSection(
                state="sample_proxy",
                label="Data-center demand",
                evidenceState="sample_proxy",
                observation="Fixed sample section tracks data-center demand as a monitoring frame.",
                researchContext="Demand interpretation would need confirmation from facilities, power, and compute evidence.",
                watchPoints=list(_DATA_CENTER_WATCH_POINTS),
            ),
            powerConstraint=HomepageAICapexInfrastructureSection(
                state="sample_proxy",
                label="Power constraint",
                evidenceState="sample_proxy",
                observation="Fixed sample section tracks power availability as an infrastructure constraint.",
                researchContext="Power availability would need confirmation from equipment and capacity planning evidence.",
                watchPoints=list(_POWER_WATCH_POINTS),
            ),
            liquidCoolingConstraint=HomepageAICapexInfrastructureSection(
                state="sample_proxy",
                label="Liquid cooling constraint",
                evidenceState="sample_proxy",
                observation="Fixed sample section tracks cooling density as a constraint for compute deployment.",
                researchContext="Cooling relevance would need confirmation from rack-density and facility design evidence.",
                watchPoints=list(_LIQUID_COOLING_WATCH_POINTS),
            ),
            gridConstraint=HomepageAICapexInfrastructureSection(
                state="sample_proxy",
                label="Grid constraint",
                evidenceState="sample_proxy",
                observation="Fixed sample section tracks grid access and interconnect timing as constraints.",
                researchContext="Grid relevance would need confirmation from capacity planning and power availability evidence.",
                watchPoints=list(_GRID_WATCH_POINTS),
            ),
            affectedSectors=list(_AFFECTED_SECTORS),
            affectedThemes=list(_REQUIRED_THEMES),
            confirmationSignals=list(_CONFIRMATION_SIGNALS),
            missingEvidence=list(_MISSING_EVIDENCE),
            watchPoints=list(_WATCH_POINTS),
            evidenceQuality=HomepageAICapexInfrastructureQuality(
                state="sample_proxy",
                label="Fixed sample evidence",
                summary="Public output is a deterministic sample and does not claim current capex or news evidence.",
            ),
            dataQuality=HomepageAICapexInfrastructureQuality(
                state="sample_proxy",
                label="Static sample data",
                summary="All fields are deterministic placeholders marked sample_proxy, no_evidence, or unavailable.",
            ),
            noAdviceDisclosure=HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_NO_ADVICE_DISCLOSURE,
        )


__all__ = [
    "HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_DEFAULT_AS_OF",
    "HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_NO_ADVICE_DISCLOSURE",
    "HOMEPAGE_AI_CAPEX_INFRASTRUCTURE_SCHEMA_VERSION",
    "HomepageAICapexInfrastructureService",
]
