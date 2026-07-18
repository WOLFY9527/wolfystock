# -*- coding: utf-8 -*-
"""Standalone safe contract for homepage capabilities metadata."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


HomepageCapabilitiesStatus = Literal["ready", "partial", "no_evidence", "unavailable"]
HomepageCapabilityId = Literal[
    "dailyMarketBrief",
    "riskRegime",
    "crossAssetIndicators",
    "eventImpactMap",
    "driverChain",
    "themeCapitalFlow",
    "researchPriorities",
    "evidenceQuality",
    "ratesPricing",
    "volatilityPositioning",
    "liquidityCredit",
    "marketBreadth",
    "afterCloseDevelopments",
    "scenarioWatchlist",
    "earningsCatalysts",
    "geopoliticalCommodityRisk",
    "aiCapexInfrastructure",
    "policyRegulationWatch",
    "styleLeadershipRotation",
    "preSessionResearchChecklist",
    "marketPulse",
    "moneyFlowProxy",
    "eventRadar",
    "personalSummary",
    "researchQueue",
    "publicDataQuality",
    "sessionStatus",
    "eventWindows",
    "noAdviceBoundary",
]

HOMEPAGE_CAPABILITIES_CONTRACT_VERSION = "homepage_capabilities_v1"
_FORBIDDEN_TEXT_MARKERS = (
    "route",
    "router",
    "endpoint",
    "admin",
    "diagnostic",
    "debug",
    "provider",
    "traceback",
    "reasoncode",
    "trustlevel",
    "sourcetype",
    "rawpayload",
    "sessionid",
    "apikey",
    "secret",
    "buy",
    "sell",
    "placeorder",
    "tradeexecution",
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "交易建议",
    "投资建议",
)


def _assert_safe_text(value: Any, *, field_name: str) -> None:
    if isinstance(value, str):
        compact = value.lower().replace("_", "").replace(" ", "").replace("-", "")
        for marker in _FORBIDDEN_TEXT_MARKERS:
            if marker in compact:
                raise ValueError(f"{field_name} contains forbidden text marker: {marker}")
        return
    if isinstance(value, BaseModel):
        _assert_safe_text(value.model_dump(mode="json"), field_name=field_name)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_safe_text(item, field_name=f"{field_name}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_safe_text(item, field_name=f"{field_name}[{index}]")


class HomepageCapabilitySection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., min_length=1, max_length=40)
    label: str = Field(..., min_length=1, max_length=80)
    supported: bool
    status: HomepageCapabilitiesStatus
    description: str = Field(..., min_length=1, max_length=200)


class HomepageCapabilitiesDataQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: HomepageCapabilitiesStatus
    label: str = Field(..., min_length=1, max_length=40)
    available: bool
    description: str = Field(..., min_length=1, max_length=200)


class HomepageCapabilitiesSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: str = Field(default=HOMEPAGE_CAPABILITIES_CONTRACT_VERSION)
    status: HomepageCapabilitiesStatus
    sections: list[HomepageCapabilitySection] = Field(default_factory=list)
    capabilities: dict[HomepageCapabilityId, bool]
    dataQuality: HomepageCapabilitiesDataQuality
    noAdviceDisclosure: str = Field(..., min_length=1, max_length=120)

    @model_validator(mode="after")
    def _validate_snapshot(self) -> "HomepageCapabilitiesSnapshot":
        if self.schemaVersion != HOMEPAGE_CAPABILITIES_CONTRACT_VERSION:
            raise ValueError("schemaVersion mismatch")
        _assert_safe_text(self.model_dump(mode="json"), field_name=self.__class__.__name__)
        return self


__all__ = [
    "HOMEPAGE_CAPABILITIES_CONTRACT_VERSION",
    "HomepageCapabilitiesDataQuality",
    "HomepageCapabilitiesSnapshot",
    "HomepageCapabilitiesStatus",
    "HomepageCapabilityId",
    "HomepageCapabilitySection",
]
