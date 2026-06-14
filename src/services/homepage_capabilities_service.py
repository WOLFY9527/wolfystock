# -*- coding: utf-8 -*-
"""Pure service that emits a bounded homepage capabilities contract."""

from __future__ import annotations

from api.v1.schemas.homepage_capabilities import (
    HOMEPAGE_CAPABILITIES_CONTRACT_VERSION,
    HOMEPAGE_CAPABILITIES_NO_ADVICE_DISCLOSURE,
    HomepageCapabilitiesDataQuality,
    HomepageCapabilitiesSnapshot,
    HomepageCapabilityFlags,
    HomepageCapabilitySection,
)


_DEFAULT_SECTIONS = (
    HomepageCapabilitySection(
        key="marketPulse",
        label="Market Pulse",
        supported=True,
        status="ready",
        description="Broad market context section is available for homepage rendering.",
    ),
    HomepageCapabilitySection(
        key="moneyFlowProxy",
        label="Money Flow Proxy",
        supported=True,
        status="ready",
        description="Money flow proxy section is available for homepage rendering.",
    ),
    HomepageCapabilitySection(
        key="eventRadar",
        label="Event Radar",
        supported=True,
        status="ready",
        description="Event radar section is available for homepage rendering.",
    ),
    HomepageCapabilitySection(
        key="personalSummary",
        label="Personal Summary",
        supported=True,
        status="ready",
        description="Personal summary section is available for homepage rendering.",
    ),
    HomepageCapabilitySection(
        key="researchQueue",
        label="Research Queue",
        supported=True,
        status="ready",
        description="Research queue section is available for homepage rendering.",
    ),
)
_DEFAULT_CAPABILITIES = HomepageCapabilityFlags()
_DEFAULT_DATA_QUALITY = HomepageCapabilitiesDataQuality(
    status="ready",
    label="stable",
    available=True,
    description="Static metadata only; no live homepage data is included.",
)


class HomepageCapabilitiesService:
    """Emit static homepage capability metadata without route or provider details."""

    def build_snapshot(self) -> HomepageCapabilitiesSnapshot:
        return HomepageCapabilitiesSnapshot(
            schemaVersion=HOMEPAGE_CAPABILITIES_CONTRACT_VERSION,
            status="ready",
            sections=list(_DEFAULT_SECTIONS),
            capabilities=_DEFAULT_CAPABILITIES,
            dataQuality=_DEFAULT_DATA_QUALITY,
            noAdviceDisclosure=HOMEPAGE_CAPABILITIES_NO_ADVICE_DISCLOSURE,
        )


__all__ = [
    "HOMEPAGE_CAPABILITIES_CONTRACT_VERSION",
    "HOMEPAGE_CAPABILITIES_NO_ADVICE_DISCLOSURE",
    "HomepageCapabilitiesService",
]
