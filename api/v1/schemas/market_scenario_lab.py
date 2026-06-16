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
        scenario.update(self.scenario_overrides)
        return scenario or None


class MarketScenarioLabRegime(_MarketScenarioLabModel):
    model_config = ConfigDict(extra="allow")

    regime: str
    confidence: str
    confidenceScore: float
    status: str | None = None


class MarketScenarioLabResponse(_MarketScenarioLabModel):
    schemaVersion: str
    baseRegime: MarketScenarioLabRegime
    scenarioRegime: MarketScenarioLabRegime
    confidenceDelta: float
    driverDeltas: Dict[str, int]
    changedDrivers: List[str]
    scenarioSummary: List[str]
    whatWouldConfirm: List[str]
    whatWouldInvalidate: List[str]
    evidenceLimits: List[str]
    noAdviceDisclosure: str


def _scenario_name_from_input(scenario: Any) -> str | None:
    if isinstance(scenario, str):
        return scenario
    if isinstance(scenario, dict):
        raw_name = scenario.get("name") or scenario.get("scenarioName")
        if raw_name is not None:
            return str(raw_name)
    return None


__all__ = [
    "MarketScenarioLabRequest",
    "MarketScenarioLabResponse",
    "MarketScenarioLabScenarioName",
]
