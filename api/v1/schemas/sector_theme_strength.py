# -*- coding: utf-8 -*-
"""Standalone sector/theme strength summary contract scaffold."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SectorThemeCategory = Literal["sector", "theme", "style", "industry", "other"]
SectorThemeContractStatus = Literal[
    "stronger",
    "weaker",
    "neutral",
    "concentrated",
    "diffusing",
    "narrowing",
    "no_evidence",
    "unavailable",
    "ready",
]
SectorThemeSummaryStatus = Literal["ready", "no_evidence", "unavailable"]
SectorThemeDataQualityStatus = Literal["ready", "no_evidence", "unavailable"]


class SectorThemeStrengthDataQualityModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SectorThemeDataQualityStatus
    observation: str


class SectorThemeStrengthNarrativeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SectorThemeContractStatus
    observation: str
    dataQuality: SectorThemeStrengthDataQualityModel


class SectorThemeStrengthItemModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    category: SectorThemeCategory
    relativeStrength: float | None = None
    breadth: float | None = None
    diffusionStatus: SectorThemeContractStatus
    leadershipStatus: SectorThemeContractStatus
    observation: str
    dataQuality: SectorThemeStrengthDataQualityModel


class SectorThemeStrengthSummaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SectorThemeSummaryStatus
    asOf: str | None = None
    strongest: list[SectorThemeStrengthItemModel] = Field(default_factory=list)
    weakest: list[SectorThemeStrengthItemModel] = Field(default_factory=list)
    leadership: SectorThemeStrengthNarrativeModel
    diffusion: SectorThemeStrengthNarrativeModel
    concentration: SectorThemeStrengthNarrativeModel
    dataQuality: SectorThemeStrengthDataQualityModel
    noAdviceDisclosure: str
