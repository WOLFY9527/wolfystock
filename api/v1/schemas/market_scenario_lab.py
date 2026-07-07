# -*- coding: utf-8 -*-
"""Safe schemas for the Market Scenario Lab API."""

from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


MarketScenarioLabScenarioName = Literal[
    "volatilitySpike",
    "breadthBreakdown",
    "ratesUpDollarUp",
    "liquidityStress",
    "riskOnConfirmation",
    "gammaUnavailable",
]

_SUPPORTED_SCENARIO_NAMES = set(MarketScenarioLabScenarioName.__args__)


class _MarketScenarioLabModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class MarketScenarioLabRequest(_MarketScenarioLabModel):
    base_regime: Dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("baseRegime", "baseDecision", "base_regime", "base_decision"),
    )
    driver_scores: Dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("driverScores", "driver_scores"),
    )
    scenario_name: MarketScenarioLabScenarioName | None = Field(
        default=None,
        validation_alias=AliasChoices("scenarioName", "scenario_name"),
    )
    preset_id: MarketScenarioLabScenarioName | None = Field(
        default=None,
        validation_alias=AliasChoices("presetId", "preset_id"),
    )
    scenario: Dict[str, Any] | MarketScenarioLabScenarioName | None = None
    scenario_overrides: Dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("scenarioOverrides", "scenario_overrides"),
    )

    @model_validator(mode="after")
    def _validate_scenario_name(self) -> "MarketScenarioLabRequest":
        scenario_name = _scenario_name_from_input(self.scenario)
        if scenario_name and scenario_name not in _SUPPORTED_SCENARIO_NAMES:
            raise ValueError("Unsupported market scenario lab scenario name.")
        return self

    def to_engine_scenario(self) -> Dict[str, Any] | str | None:
        scenario: Dict[str, Any] = {}
        if isinstance(self.scenario, dict):
            scenario.update(self.scenario)
        elif isinstance(self.scenario, str):
            scenario["name"] = self.scenario
        if self.scenario_name:
            scenario["name"] = self.scenario_name
        if self.preset_id:
            scenario["presetId"] = self.preset_id
            scenario["name"] = self.preset_id
        scenario.update(self.scenario_overrides)
        return scenario or None


class MarketScenarioLabRegime(_MarketScenarioLabModel):
    model_config = ConfigDict(extra="allow")

    regime: str
    confidence: str
    confidenceScore: float
    status: str | None = None


class MarketScenarioLabContractStatus(_MarketScenarioLabModel):
    state: Literal["available", "degraded", "unavailable"]
    label: str
    message: str
    observationOnly: bool
    decisionGrade: bool


class MarketScenarioLabBaseContext(_MarketScenarioLabModel):
    source: str
    label: str
    message: str
    evidenceState: Literal["ready", "degraded", "unavailable"]
    scoringDriverCount: int


class MarketScenarioLabReadinessComponent(_MarketScenarioLabModel):
    state: str
    available: bool
    lastUpdated: str | None = None
    affectedComponents: List[str] = Field(default_factory=list)


class MarketScenarioLabDriverInputsReadiness(_MarketScenarioLabModel):
    state: Literal["available", "partial", "missing"]
    availableDriverKeys: List[str] = Field(default_factory=list)
    partialDriverKeys: List[str] = Field(default_factory=list)
    missingDriverKeys: List[str] = Field(default_factory=list)
    affectedDriverKeys: List[str] = Field(default_factory=list)


class MarketScenarioLabEvidenceCompleteness(_MarketScenarioLabModel):
    state: Literal["ready", "partial", "blocked"]
    gaps: List[str] = Field(default_factory=list)


class MarketScenarioLabBaselineReadiness(_MarketScenarioLabModel):
    status: Literal["ready", "partial", "blocked"]
    baselineSnapshot: MarketScenarioLabReadinessComponent
    marketFrame: MarketScenarioLabReadinessComponent
    driverInputs: MarketScenarioLabDriverInputsReadiness
    evidenceCompleteness: MarketScenarioLabEvidenceCompleteness
    dataState: Literal["real_cached", "demo_static_sample", "request_supplied", "unavailable"]
    sampleState: Literal["none", "fixture", "demo", "sample", "static", "fallback"]
    scoreAuthority: Literal["authoritative", "observation_only"]
    sourceAuthorityAllowed: bool
    authoritative: bool
    observationOnly: bool
    ready: bool
    partial: bool
    blocked: bool
    affectedBaselineComponents: List[str] = Field(default_factory=list)
    affectedDriverKeys: List[str] = Field(default_factory=list)
    evidenceGaps: List[str] = Field(default_factory=list)
    lastUpdated: str | None = None


class MarketScenarioLabBaselineSnapshotScope(_MarketScenarioLabModel):
    type: Literal["symbol", "market"]
    value: str


class MarketScenarioLabBaselineSnapshotSource(_MarketScenarioLabModel):
    dataState: Literal["real_cached", "request_supplied", "demo_static_sample", "unavailable"]
    freshness: Literal["fresh", "recent", "stale", "unavailable", "unknown", "no_evidence"]
    asOf: str | None = None
    sourceAuthorityAllowed: bool
    observationOnly: bool


class MarketScenarioLabBaselineSnapshot(_MarketScenarioLabModel):
    schemaVersion: str
    status: Literal["available", "partial", "not_available"]
    reasonCode: Literal["baseline_available", "baseline_partial", "baseline_missing"]
    snapshotId: str | None = None
    ownerScope: Dict[str, str] | None = None
    scope: MarketScenarioLabBaselineSnapshotScope
    createdAt: str | None = None
    asOf: str | None = None
    source: MarketScenarioLabBaselineSnapshotSource
    availableDataCategories: List[str] = Field(default_factory=list)
    missingDataCategories: List[str] = Field(default_factory=list)
    degradedDataCategories: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    notes: str
    inputSnapshotRefs: List[str] = Field(default_factory=list)
    sourceAuthoritySummary: Dict[str, Any] | None = None
    freshnessSummary: Dict[str, Any] | None = None
    missingInputList: List[str] = Field(default_factory=list)
    readinessState: str | None = None
    targetEnvironmentEvidence: Dict[str, Any] | None = None
    contentHash: str | None = None
    contentVersionRef: str | None = None
    observationOnly: bool
    comparisonReady: bool
    noAdviceDisclosure: str


class MarketScenarioLabBaselineSnapshotCreateRequest(_MarketScenarioLabModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class MarketScenarioLabBaselineSnapshotReadResponse(MarketScenarioLabBaselineSnapshot):
    pass


class MarketScenarioLabScenarioOutput(_MarketScenarioLabModel):
    scenarioRegime: MarketScenarioLabRegime
    confidenceDelta: float
    driverDeltas: Dict[str, int]
    changedDrivers: List[str]
    summary: List[str]


class MarketScenarioLabConfirmInvalidateContext(_MarketScenarioLabModel):
    status: Literal["available", "unavailable"]
    message: str
    confirm: List[str]
    invalidate: List[str]


class MarketScenarioLabExpectedDriverImpact(_MarketScenarioLabModel):
    driver: str
    direction: Literal["pressure", "supportive", "unchanged"]
    magnitude: Literal["low", "medium", "high"]


class MarketScenarioLabLinkedSurface(_MarketScenarioLabModel):
    label: str
    route: str
    section: str
    reason: str


class MarketScenarioLabScenarioPreset(_MarketScenarioLabModel):
    presetId: str
    name: str
    label: str
    category: str
    description: str
    inputAssumptions: List[str]
    expectedDriverImpacts: List[MarketScenarioLabExpectedDriverImpact]
    evidenceLimits: List[str]
    confirmInvalidateContext: MarketScenarioLabConfirmInvalidateContext
    linkedSurfaces: List[MarketScenarioLabLinkedSurface]
    consumerIssues: List[Dict[str, str]]
    noAdviceDisclosure: str
    observationOnly: bool
    decisionGrade: bool


class MarketScenarioLabResponse(_MarketScenarioLabModel):
    schemaVersion: str
    contractStatus: MarketScenarioLabContractStatus
    observationOnly: bool
    decisionGrade: bool
    selectedScenario: MarketScenarioLabScenarioPreset
    scenarioPresets: List[MarketScenarioLabScenarioPreset]
    baseMarketContext: MarketScenarioLabBaseContext
    baselineReadiness: MarketScenarioLabBaselineReadiness
    scenarioBaselineSnapshot: MarketScenarioLabBaselineSnapshot
    baseRegime: MarketScenarioLabRegime
    scenarioRegime: MarketScenarioLabRegime
    scenarioOutput: MarketScenarioLabScenarioOutput
    confidenceDelta: float
    driverDeltas: Dict[str, int]
    changedDrivers: List[str]
    scenarioSummary: List[str]
    confirmInvalidateContext: MarketScenarioLabConfirmInvalidateContext
    whatWouldConfirm: List[str]
    whatWouldInvalidate: List[str]
    evidenceLimits: List[str]
    consumerIssues: List[Dict[str, str]] = Field(default_factory=list)
    noAdviceDisclosure: str
    sourceClass: str | None = None
    dataSourceClass: str | None = None


def _scenario_name_from_input(scenario: Any) -> str | None:
    if isinstance(scenario, str):
        return scenario
    if isinstance(scenario, dict):
        raw_name = scenario.get("presetId") or scenario.get("name") or scenario.get("scenarioName")
        if raw_name is not None:
            return str(raw_name)
    return None


__all__ = [
    "MarketScenarioLabBaselineSnapshotCreateRequest",
    "MarketScenarioLabBaselineSnapshotReadResponse",
    "MarketScenarioLabRequest",
    "MarketScenarioLabResponse",
    "MarketScenarioLabScenarioName",
]
