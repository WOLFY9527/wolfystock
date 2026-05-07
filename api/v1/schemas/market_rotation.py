# -*- coding: utf-8 -*-
"""Schemas for the read-only market rotation radar endpoint."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


FreshnessLabel = Literal["live", "delayed", "cached", "stale", "fallback", "mock", "error"]
RotationStage = Literal[
    "early_rotation",
    "confirmed_rotation",
    "crowded_or_extended",
    "cooling",
    "weak_or_no_signal",
]
RotationRiskLabel = Literal[
    "gap_fade_risk",
    "thin_breadth",
    "single_name_driven",
    "stale_data",
    "fallback_data",
]


class RotationRadarTimeWindowModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    window: Literal["5m", "15m", "60m", "1d"]
    label: str
    available: bool = False
    changePercent: Optional[float] = None
    relativeVolume: Optional[float] = None
    freshness: FreshnessLabel = "fallback"
    isFallback: bool = False
    isStale: bool = False
    source: Optional[str] = None
    sourceLabel: Optional[str] = None
    asOf: Optional[str] = None
    reason: Optional[str] = None


class RotationRadarBenchmarkModel(BaseModel):
    symbol: str
    changePercent: Optional[float] = None
    timeWindows: Dict[str, RotationRadarTimeWindowModel] = Field(default_factory=dict)
    freshness: FreshnessLabel = "fallback"
    isFallback: bool = False
    isStale: bool = False
    source: Optional[str] = None
    sourceLabel: Optional[str] = None
    asOf: Optional[str] = None


class RotationRadarMemberModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: str
    name: str
    observed: bool = False
    price: Optional[float] = None
    changePercent: Optional[float] = None
    relativeStrengthVsBenchmark: Optional[float] = None
    volumeRatio: Optional[float] = None
    timeWindows: Dict[str, RotationRadarTimeWindowModel] = Field(default_factory=dict)
    priceAboveVwap: Optional[bool] = None
    persistenceScore: Optional[float] = None
    leadershipLabel: Optional[str] = None
    freshnessLabel: Optional[str] = None
    freshness: FreshnessLabel = "fallback"
    isFallback: bool = False
    isStale: bool = False
    source: Optional[str] = None
    sourceLabel: Optional[str] = None
    asOf: Optional[str] = None
    notes: List[str] = Field(default_factory=list)


class RotationRadarThemeModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    englishName: str
    focus: str
    benchmark: str
    sectorBenchmark: Optional[str] = None
    membersConfigured: List[str] = Field(default_factory=list)
    rotationScore: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    stage: RotationStage
    stageExplanation: Optional[str] = None
    riskLabels: List[RotationRiskLabel] = Field(default_factory=list)
    riskExplanations: List[str] = Field(default_factory=list)
    newslessRotation: bool = False
    newslessRotationEvidence: Optional[str] = None
    relativeStrength: Dict[str, Any] = Field(default_factory=dict)
    benchmarkProxies: Dict[str, Any] = Field(default_factory=dict)
    timeWindows: Dict[str, RotationRadarTimeWindowModel] = Field(default_factory=dict)
    volume: Dict[str, Any] = Field(default_factory=dict)
    breadth: Dict[str, Any] = Field(default_factory=dict)
    synchronization: Dict[str, Any] = Field(default_factory=dict)
    leadership: Dict[str, Any] = Field(default_factory=dict)
    themeDetail: Dict[str, Any] = Field(default_factory=dict)
    freshness: FreshnessLabel = "fallback"
    isFallback: bool = False
    isStale: bool = False
    source: str = "fallback"
    sourceLabel: Optional[str] = None
    asOf: Optional[str] = None
    updatedAt: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)
    members: List[RotationRadarMemberModel] = Field(default_factory=list)
    noAdviceDisclosure: str


class RotationRadarSummaryItemModel(BaseModel):
    id: str
    name: str
    rotationScore: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    stage: RotationStage
    freshness: FreshnessLabel
    isFallback: bool
    riskLabels: List[RotationRiskLabel] = Field(default_factory=list)


class RotationRadarSummaryModel(BaseModel):
    strongestThemes: List[RotationRadarSummaryItemModel] = Field(default_factory=list)
    acceleratingThemes: List[RotationRadarSummaryItemModel] = Field(default_factory=list)
    fadingThemes: List[RotationRadarSummaryItemModel] = Field(default_factory=list)
    safeWording: List[str] = Field(default_factory=list)


class MarketRotationRadarResponse(BaseModel):
    endpoint: str
    generatedAt: str
    source: str
    sourceLabel: Optional[str] = None
    freshness: FreshnessLabel
    isFallback: bool = False
    isStale: bool = False
    warning: Optional[str] = None
    noAdviceDisclosure: str
    benchmarks: Dict[str, RotationRadarBenchmarkModel] = Field(default_factory=dict)
    summary: RotationRadarSummaryModel
    themes: List[RotationRadarThemeModel] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
