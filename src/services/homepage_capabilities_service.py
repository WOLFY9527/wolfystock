# -*- coding: utf-8 -*-
"""Pure service that emits a bounded homepage capabilities contract."""

from __future__ import annotations

from api.v1.schemas.homepage_capabilities import (
    HOMEPAGE_CAPABILITIES_CONTRACT_VERSION,
    HomepageCapabilitiesDataQuality,
    HomepageCapabilitiesSnapshot,
    HomepageCapabilityFlags,
    HomepageCapabilitySection,
)


HOMEPAGE_CAPABILITIES_NO_ADVICE_DISCLOSURE = "首页能力信息仅供研究观察，不构成个性化建议或交易指令。"
_DEFAULT_SECTIONS = (
    HomepageCapabilitySection(
        key="marketPulse",
        label="市场脉冲",
        supported=True,
        status="ready",
        description="提供市场状态观察入口，适合研究观察。",
    ),
    HomepageCapabilitySection(
        key="moneyFlowProxy",
        label="资金流代理",
        supported=True,
        status="ready",
        description="提供资金流线索观察入口，证据需要复核。",
    ),
    HomepageCapabilitySection(
        key="eventRadar",
        label="事件雷达",
        supported=True,
        status="ready",
        description="提供事件观察入口，适合研究观察。",
    ),
    HomepageCapabilitySection(
        key="personalSummary",
        label="个人摘要",
        supported=True,
        status="ready",
        description="提供个人研究摘要入口，证据需要复核。",
    ),
    HomepageCapabilitySection(
        key="researchQueue",
        label="研究队列",
        supported=True,
        status="ready",
        description="提供后续研究排队入口，不包含交易指令。",
    ),
)
_DEFAULT_CAPABILITIES = HomepageCapabilityFlags()
_DEFAULT_DATA_QUALITY = HomepageCapabilitiesDataQuality(
    status="ready",
    label="正常",
    available=True,
    description="首页能力信息已就绪，仅用于研究观察。",
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
