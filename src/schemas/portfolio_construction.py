# -*- coding: utf-8 -*-
"""Portfolio construction advisory read-model DTOs."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


PortfolioConstructionSuggestedAction = Literal[
    "increase_exposure",
    "reduce_exposure",
    "no_action",
]


class PortfolioConstructionConstraintViolation(BaseModel):
    code: str
    severity: Literal["info", "warning", "blocker"] = "warning"
    message: str


class PortfolioConstructionPositionEvidence(BaseModel):
    source: str
    accountIds: List[int] = Field(default_factory=list)
    marketValue: float = 0.0


class PortfolioConstructionPositionReadModel(BaseModel):
    symbol: str
    market: Optional[str] = None
    currency: Optional[str] = None
    currentWeight: float
    targetWeight: float
    drift: float
    suggestedAction: PortfolioConstructionSuggestedAction
    currentMarketValue: float = 0.0
    constraintViolations: List[PortfolioConstructionConstraintViolation] = Field(default_factory=list)
    riskBudgetNotes: List[str] = Field(default_factory=list)
    noTradeReasons: List[str] = Field(default_factory=list)
    noActionReasons: List[str] = Field(default_factory=list)
    evidence: PortfolioConstructionPositionEvidence


class PortfolioConstructionEvidenceMetadata(BaseModel):
    snapshotSource: str
    targetSource: str
    asOf: Optional[str] = None
    deterministic: bool = True
    sideEffectFree: bool = True
    advisoryOnly: bool = True
    accountingMutation: bool = False
    brokerIntegration: bool = False


class PortfolioConstructionMetadata(BaseModel):
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    confidenceReasons: List[str] = Field(default_factory=list)
    evidence: PortfolioConstructionEvidenceMetadata


class PortfolioConstructionReadModel(BaseModel):
    readModelType: Literal["portfolio_construction_advisory_v1"] = "portfolio_construction_advisory_v1"
    asOf: Optional[str] = None
    currency: str
    totalMarketValue: float
    targetSource: str
    driftThreshold: float
    advisoryOnly: bool = True
    accountingMutation: bool = False
    brokerIntegration: bool = False
    tradeExecution: bool = False
    executionReadiness: Literal["advisory_only_not_trade_execution"] = "advisory_only_not_trade_execution"
    riskBudgetNotes: List[str] = Field(default_factory=list)
    noTradeReasons: List[str] = Field(default_factory=list)
    positions: List[PortfolioConstructionPositionReadModel] = Field(default_factory=list)
    metadata: PortfolioConstructionMetadata
    extensions: Dict[str, Any] = Field(default_factory=dict)
