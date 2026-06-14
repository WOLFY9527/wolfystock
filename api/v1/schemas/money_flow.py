# -*- coding: utf-8 -*-
"""Schemas for the homepage money flow proxy scaffold."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.services.market_data_quality import build_consumer_data_quality_state


MoneyFlowProxyStatus = Literal["ready", "no_evidence", "partial", "unavailable"]
MoneyFlowCategory = Literal["sector", "theme", "style", "asset_class", "other"]
MoneyFlowDirection = Literal["inflow", "outflow", "neutral"]
MoneyFlowStrength = Literal["strong", "moderate", "weak", "mixed", "unknown"]
MoneyFlowBreadth = Literal["broadening", "converging", "mixed", "unknown"]
MoneyFlowRelativeMove = Literal["strengthening", "weakening", "flat", "unknown"]
DataQualityState = Literal["ready", "delayed", "cached", "partial", "no_evidence", "unavailable"]


class ConsumerDataQualityModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: DataQualityState
    label: str
    available: bool = False


class MoneyFlowItemModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    category: MoneyFlowCategory
    direction: MoneyFlowDirection
    strength: MoneyFlowStrength = "unknown"
    breadth: MoneyFlowBreadth = "unknown"
    relativeMove: MoneyFlowRelativeMove = "unknown"
    interpretation: str
    dataQuality: DataQualityState = "no_evidence"


class MoneyFlowBiasModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bias: str
    interpretation: str
    dataQuality: ConsumerDataQualityModel


class MoneyFlowSourceStatusModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    providerWired: bool = False
    proxyMode: Literal["observed_flow_proxy"] = "observed_flow_proxy"
    observationOnly: bool = True
    summary: str


class HomeMoneyFlowProxyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: MoneyFlowProxyStatus
    asOf: str | None = None
    topInflows: list[MoneyFlowItemModel] = Field(default_factory=list)
    topOutflows: list[MoneyFlowItemModel] = Field(default_factory=list)
    styleBias: MoneyFlowBiasModel
    offensiveDefensiveBias: MoneyFlowBiasModel
    interpretation: str
    sourceStatus: MoneyFlowSourceStatusModel
    dataQuality: ConsumerDataQualityModel
    noAdviceDisclosure: str

    @model_validator(mode="before")
    @classmethod
    def _populate_data_quality(cls, value: Any) -> Any:
        if not isinstance(value, dict) or "dataQuality" in value:
            return value
        payload = dict(value)
        payload["dataQuality"] = build_consumer_data_quality_state(
            _quality_seed(str(payload.get("status") or "").strip().lower())
        )
        return payload


def _quality_seed(status: str) -> dict[str, Any]:
    if status == "ready":
        return {"status": "ready"}
    if status == "partial":
        return {"status": "partial", "isPartial": True}
    if status == "unavailable":
        return {"isUnavailable": True}
    return {}
