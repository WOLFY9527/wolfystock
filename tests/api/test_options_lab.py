# -*- coding: utf-8 -*-
"""Options Lab API contract tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import options
from api.v1.schemas.options import OptionChainResponse, OptionContract, OptionGreeks, OptionsMetadata
from src.services.consumer_api_diagnostic_redaction import project_consumer_api_payload
from src.services.options_lab_domain_models import (
    AnalyzeCandidateModel,
    AnalyzeResultModel,
    AnalyzeSubScoresModel,
    BreakevenAssessment,
    DecisionAlternativeModel,
    DecisionDataQualityAssessment,
    DecisionEvaluationResult,
    DecisionFreshnessModel,
    ExpectedMoveEstimate,
    IvGreeksAssessment,
    LiquidityAssessment,
    OptionChainResultModel,
    OptionExpirationModel,
    OptionExpirationsResultModel,
    OptionsLabMetadataModel,
    OptionUnderlyingSummaryResultModel,
    OptimizerCandidate,
    OptimizerResult,
    RiskRewardAssessment,
    ScenarioPayoffRowModel,
    ScenarioResultModel,
    ScenarioRiskModel,
    StrategyCompareResultModel,
    StrategyComparisonModel,
    StrategyLegModel,
)
from src.services.options_lab_service import OptionsLabService


SAFETY_BLOCKED_MARKERS = [
    "rawproviderpayload",
    "raw_provider_payload",
    "raw provider payload",
    "debugschema",
    "debug_schema",
    "rawschema",
    "raw_schema",
    "traceback",
    "stack trace",
    "api_key",
    "apikey",
    "api key",
    "token=",
    "password",
    "session=",
    "cookie",
    "authorization",
    "bearer",
    "provider.example",
    "provider credential",
    "credential payload",
    "必买",
    "稳赚",
    "保证收益",
    "下单",
    "立即买入",
    "立即卖出",
    "guaranteed",
    "guaranteed profit",
    "best contract",
    "ai recommends you buy",
    "must buy",
    "must sell",
    "buy now",
    "sell now",
    "trade-ready",
    "trade ready",
    "trade quality",
    "you should buy",
    "you should sell",
    "决策实验室",
    "可成交性",
    "有条件可交易",
]


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(options.router, prefix="/api/v1/options")
    return TestClient(app)


def _json_text(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _assert_no_safety_leaks(payload) -> None:
    text = _json_text(payload).lower()
    for value in SAFETY_BLOCKED_MARKERS:
        assert value not in text


def _assert_no_consumer_diagnostic_leaks(payload) -> None:
    text = _json_text(payload)
    lowered = text.lower()
    for marker in (
        "debugRef",
        "failClosedReasonCodes",
        "providerAuthority",
        "providerName",
        "providerDecisionAuthority",
        "recommendationAuthority",
        "sourceType",
        "sourceTier",
        "sourceRef",
        "rawPayload",
        "schemaVersion",
        "policyVersion",
        "requestId",
        "traceId",
        "provider_adapter_contract_not_decision_grade",
        "provider_authority_tier_observation_only",
        "provider_fixture_not_decision_grade",
        "provider_live_disabled",
        "provider_tradeable_data_false",
        "tradier_adapter_contract",
        "delayed_fixture",
        "synthetic_fixture",
    ):
        assert marker not in text
        assert marker.lower() not in lowered


OPTIONS_CONSUMER_FORBIDDEN_MARKERS = (
    "providerName",
    "providerClass",
    "providerAttempted",
    "requiredProviderClass",
    "sourceAuthorityRouter",
    "endpointHost",
    "apiKeyPresent",
    "exceptionClass",
    "exceptionChain",
    "requestId",
    "traceId",
    "cacheKey",
    "rawPayload",
    "raw_provider_payload",
    "credential",
    "token",
    "env",
    "API_KEY",
    "PASSWORD",
    "SECRET",
    "PRIVATE_KEY",
    "Traceback",
    "providerCapabilities",
    "providerAuthority",
    "providerQuality",
    "sourceType",
    "sourceTier",
    "sourceRef",
    "synthetic_fixture",
    "delayed_fixture",
)


def _assert_no_options_consumer_redaction_leaks(payload) -> None:
    text = _json_text(payload)
    lowered = text.lower()
    for marker in OPTIONS_CONSUMER_FORBIDDEN_MARKERS:
        assert marker not in text
        assert marker.lower() not in lowered


def _assert_consumer_safe_sandbox_metadata(payload: dict) -> None:
    metadata = payload["metadata"]
    assert metadata["mode"] in {"sandbox", "educational"}
    assert metadata["dataStatus"] in {"example_data", "sandbox_data", "unavailable", "ready"}
    assert metadata["label"] in {"教学沙盒", "示例数据", "教学沙盒 · 示例数据"}
    assert metadata["noAdvice"] is True
    assert metadata["executionSupported"] is False
    assert metadata["noOrderPlacement"] is True
    assert metadata["noBrokerConnection"] is True
    assert metadata["noTradingRecommendation"] is True
    if metadata["fixtureBacked"] or metadata["syntheticData"]:
        assert metadata["dataStatus"] == "example_data"
        assert metadata["label"] == "教学沙盒 · 示例数据"


def _assert_no_execution_implication_fields(payload: dict) -> None:
    forbidden_truthy_keys = {
        "brokerExecutionSupported",
        "orderPlacementSupported",
        "personalizedRecommendation",
        "guaranteedPricing",
        "targetProfit",
        "targetLoss",
    }
    stack = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                assert not (key in forbidden_truthy_keys and value)
                stack.append(value)
        elif isinstance(item, list):
            stack.extend(item)


def _assert_consumer_scenario_frame_contract(frame: dict) -> None:
    assert set(frame.keys()) == {
        "contractVersion",
        "frameState",
        "underlying",
        "strategyType",
        "expiration",
        "scenarioCoverage",
        "chainQuality",
        "liquidityGate",
        "ivGreeksGate",
        "spreadGate",
        "payoffEvidence",
        "riskEvidence",
        "assumptions",
        "missingEvidence",
        "blockingReasons",
        "nextEvidenceNeeded",
        "noTradingBoundary",
    }
    assert frame["contractVersion"] == "options-consumer-scenario-frame-v1"
    assert frame["underlying"]
    assert frame["strategyType"]
    assert frame["scenarioCoverage"] in {"missing_chain_data", "single_contract", "strategy_compare_ready"}
    assert frame["liquidityGate"] in {"clear", "blocked", "observe_only", "manual_review"}
    assert frame["ivGreeksGate"] in {"clear", "blocked", "observe_only", "manual_review"}
    assert frame["spreadGate"] in {"clear", "blocked", "observe_only", "manual_review"}
    assert frame["payoffEvidence"]
    assert frame["riskEvidence"]
    assert frame["assumptions"] is not None
    assert isinstance(frame["missingEvidence"], list)
    assert isinstance(frame["blockingReasons"], list)
    assert isinstance(frame["nextEvidenceNeeded"], list)
    assert frame["noTradingBoundary"] == {
        "analyticalOnly": True,
        "noBrokerExecution": True,
        "noOrderPlacement": True,
        "noPortfolioMutation": True,
        "noTradingRecommendation": True,
    }


class _MockTradierHttpResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


def _tradier_runtime_env(credential: str) -> dict[str, str]:
    return {
        "OPTIONS_LIVE_PROVIDERS_ENABLED": "1",
        "OPTIONS_LIVE_PROVIDER_KEYS": "tradier",
        "TRADIER_API_TOKEN": credential,
    }


def _tradier_quote_payload() -> dict:
    return {
        "quotes": {
            "quote": {
                "symbol": "TEM",
                "last": "52.40",
                "change_percentage": "1.15",
                "trade_date": "2026-05-06T13:45:00Z",
            }
        }
    }


def _tradier_expirations_payload() -> dict:
    return {"expirations": {"date": ["2026-06-19", "2026-08-21"]}}


def _tradier_chain_payload() -> dict:
    return {
        "options": {
            "option": [
                {
                    "symbol": "TEM260619C00050000",
                    "option_type": "call",
                    "expiration_date": "2026-06-19",
                    "strike": "50.0",
                    "bid": "4.80",
                    "ask": "5.20",
                    "last": "5.00",
                    "volume": "320",
                    "open_interest": "1480",
                    "greeks": {
                        "mid_iv": "0.62",
                        "delta": "0.61",
                        "gamma": "0.044",
                        "theta": "-0.072",
                        "vega": "0.118",
                        "rho": "0.031",
                    },
                }
            ]
        }
    }


def test_summary_endpoint_returns_safe_normalized_fixture_response() -> None:
    client = _client()
    try:
        response = client.get("/api/v1/options/underlyings/tem/summary", params={"forceRefresh": "true"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["symbol"] == "TEM"
        assert payload["market"] == "us"
        assert payload["metadata"]["fixtureBacked"] is True
        assert payload["metadata"]["noExternalCalls"] is True
        assert payload["metadata"]["noOrderPlacement"] is True
        assert payload["limitations"]["optionsAreHighRisk"] is True
        assert payload["limitations"]["dataMayBeDelayedOrStale"] is True
    finally:
        client.close()


def test_options_consumer_underlying_endpoints_recursively_redact_provider_diagnostics() -> None:
    client = _client()
    try:
        responses = [
            client.get("/api/v1/options/underlyings/NVDA/summary", params={"forceRefresh": "true"}),
            client.get(
                "/api/v1/options/underlyings/NVDA/chain",
                params={"expiration": "2026-06-19", "includeGreeks": "true"},
            ),
            client.get("/api/v1/options/underlyings/NVDA/structure"),
        ]
        assert all(response.status_code == 200 for response in responses)
        for response in responses:
            payload = response.json()
            _assert_no_options_consumer_redaction_leaks(payload)
            assert payload["consumerSafeSourceLabel"] == "部分数据源暂不可用"
    finally:
        client.close()


def test_openapi_decision_summary_uses_no_decision_grade_copy() -> None:
    client = _client()
    try:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        payload = response.json()
        operation = payload["paths"]["/api/v1/options/decision/evaluate"]["post"]
        summary = operation["summary"]

        assert "trade quality" not in summary.lower()
        assert "decision" not in summary.lower()
        assert "read-only" in summary.lower()
        assert "analytical" in summary.lower()
    finally:
        client.close()


def test_expirations_endpoint_returns_fixture_expirations() -> None:
    client = _client()
    try:
        response = client.get("/api/v1/options/underlyings/TEM/expirations")
        assert response.status_code == 200
        payload = response.json()
        assert [item["date"] for item in payload["expirations"]] == ["2026-06-19", "2026-08-21"]
        assert payload["expirations"][0]["chainAvailable"] is True
    finally:
        client.close()


def test_summary_and_expirations_endpoint_mappers_preserve_alias_contracts() -> None:
    summary_result = OptionUnderlyingSummaryResultModel(
        symbol="TEM",
        market="us",
        currency="USD",
        underlying={"symbol": "TEM", "price": 52.4},
        options_availability={
            "supported": True,
            "provider": "synthetic_fixture",
            "providerCapabilities": {"expirations": True, "chain": True},
            "limitations": ["fixture_only", "provider_validation_required_later"],
        },
        as_of="2026-05-06T14:30:00Z",
        source="synthetic_fixture",
        warnings=["synthetic_fixture_data", "options_are_high_risk"],
        metadata=OptionsLabMetadataModel(provider_name="synthetic_fixture"),
    )
    summary_payload = options._map_underlying_summary_response(summary_result).model_dump(by_alias=True)
    assert summary_payload["optionsReadiness"] == summary_payload["optionsResearchReadiness"]
    assert summary_payload["optionsReadiness"]["optionsResearchReady"] is False
    assert summary_payload["optionsReadiness"]["readinessState"] == "blocked"
    assert summary_payload["optionsReadiness"]["dataQualityTier"] == "synthetic_demo_only"
    summary_contract_only = dict(summary_payload)
    summary_contract_only.pop("optionsReadiness")
    summary_contract_only.pop("optionsResearchReadiness")
    assert summary_contract_only == {
        "symbol": "TEM",
        "market": "us",
        "currency": "USD",
        "observationOnly": True,
        "decisionGrade": False,
        "underlying": {"symbol": "TEM", "price": 52.4},
        "optionsAvailability": {
            "supported": True,
            "provider": "synthetic_fixture",
            "providerCapabilities": {"expirations": True, "chain": True},
            "limitations": ["fixture_only", "provider_validation_required_later"],
        },
        "asOf": "2026-05-06T14:30:00Z",
        "source": "synthetic_fixture",
        "warnings": ["synthetic_fixture_data", "options_are_high_risk"],
        "limitations": {
            "optionsAreHighRisk": True,
            "longOptionsCanLose100PercentPremium": True,
            "dataMayBeDelayedOrStale": True,
            "analyticalOnlyNotInvestmentAdvice": True,
            "noOrderPlacement": True,
            "noBrokerExecution": True,
        },
        "metadata": options._map_options_metadata(summary_result.metadata).model_dump(by_alias=True),
    }

    expirations_result = OptionExpirationsResultModel(
        symbol="TEM",
        market="us",
        expirations=[
            OptionExpirationModel(
                date="2026-06-19",
                dte=44,
                type="monthly",
                chain_available=True,
                as_of="2026-05-06T14:30:00Z",
                source="synthetic_fixture",
                warnings=["synthetic_fixture_data"],
            ),
            OptionExpirationModel(
                date="2026-08-21",
                dte=107,
                type="monthly",
                chain_available=True,
                as_of="2026-05-06T14:30:00Z",
                source="synthetic_fixture",
                warnings=[],
            ),
        ],
        as_of="2026-05-06T14:30:00Z",
        source="synthetic_fixture",
        warnings=["synthetic_fixture_data", "options_are_high_risk"],
        metadata=OptionsLabMetadataModel(provider_name="synthetic_fixture"),
    )
    expirations_payload = options._map_expirations_response(expirations_result).model_dump(by_alias=True)
    assert expirations_payload["optionsReadiness"] == expirations_payload["optionsResearchReadiness"]
    assert expirations_payload["optionsReadiness"]["optionsResearchReady"] is False
    assert expirations_payload["optionsReadiness"]["readinessState"] == "blocked"
    expirations_contract_only = dict(expirations_payload)
    expirations_contract_only.pop("optionsReadiness")
    expirations_contract_only.pop("optionsResearchReadiness")
    assert expirations_contract_only == {
        "symbol": "TEM",
        "market": "us",
        "observationOnly": True,
        "decisionGrade": False,
        "expirations": [
            {
                "date": "2026-06-19",
                "dte": 44,
                "type": "monthly",
                "chainAvailable": True,
                "asOf": "2026-05-06T14:30:00Z",
                "source": "synthetic_fixture",
                "warnings": ["synthetic_fixture_data"],
            },
            {
                "date": "2026-08-21",
                "dte": 107,
                "type": "monthly",
                "chainAvailable": True,
                "asOf": "2026-05-06T14:30:00Z",
                "source": "synthetic_fixture",
                "warnings": [],
            },
        ],
        "asOf": "2026-05-06T14:30:00Z",
        "source": "synthetic_fixture",
        "warnings": ["synthetic_fixture_data", "options_are_high_risk"],
        "limitations": {
            "optionsAreHighRisk": True,
            "longOptionsCanLose100PercentPremium": True,
            "dataMayBeDelayedOrStale": True,
            "analyticalOnlyNotInvestmentAdvice": True,
            "noOrderPlacement": True,
            "noBrokerExecution": True,
        },
        "metadata": options._map_options_metadata(expirations_result.metadata).model_dump(by_alias=True),
    }


def test_chain_endpoint_filters_side_expiration_liquidity_and_spread() -> None:
    client = _client()
    try:
        response = client.get(
            "/api/v1/options/underlyings/TEM/chain",
            params={
                "expiration": "2026-06-19",
                "side": "call",
                "minOpenInterest": 100,
                "maxSpreadPct": 20,
                "includeGreeks": "false",
                "forceRefresh": "true",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert [item["contractSymbol"] for item in payload["calls"]] == [
            "TEM260619C00050000",
            "TEM260619C00055000",
        ]
        assert payload["puts"] == []
        assert all(item["greeks"] is None for item in payload["calls"])
        assert payload["calls"][0]["multiplier"] == 100
        assert payload["calls"][0]["freshness"] == "synthetic_delayed"
        assert payload["calls"][0]["dataQuality"]["tradeable"] is False
        assert payload["filtersApplied"]["forceRefresh"] is True
        assert payload["metadata"]["forceRefreshIgnored"] is True
        assert payload["metadata"]["liveProviderEnabled"] is False
        assert payload["consumerSafeSourceLabel"] == "部分数据源暂不可用"
        _assert_no_options_consumer_redaction_leaks(payload)
    finally:
        client.close()


def test_chain_endpoint_includes_observation_only_structure_signal_packet() -> None:
    client = _client()
    try:
        response = client.get(
            "/api/v1/options/underlyings/TEM/chain",
            params={"expiration": "2026-06-19", "includeGreeks": "true", "forceRefresh": "true"},
        )
        assert response.status_code == 200
        payload = response.json()

        packet = payload["optionsStructureSignalPacket"]
        assert set(packet.keys()) == {
            "gammaCoverageState",
            "ivCoverageState",
            "skewObservation",
            "liquidityObservation",
            "expirationCoverage",
            "missingGreeks",
            "staleOrDemoBoundary",
            "observationBoundary",
            "researchNextSteps",
        }
        assert packet["gammaCoverageState"] == "covered"
        assert packet["ivCoverageState"] == "covered"
        assert packet["skewObservation"] == {
            "state": "observed",
            "callAverageIv": 0.6867,
            "putAverageIv": 0.655,
            "callPutIvSpread": 0.0317,
            "contractCount": 5,
        }
        assert packet["liquidityObservation"] == {
            "state": "partial",
            "contractCount": 5,
            "contractsWithBidAsk": 5,
            "wideSpreadCount": 1,
            "thinLiquidityCount": 1,
            "minimumOpenInterest": 40,
            "minimumVolume": 8,
        }
        assert packet["expirationCoverage"] == {
            "state": "single_expiration",
            "expirationCount": 1,
            "nearestDte": 44,
            "contractsByExpiration": [{"expiration": "2026-06-19", "contractCount": 5}],
        }
        assert packet["missingGreeks"] == []
        assert packet["staleOrDemoBoundary"] == {
            "state": "demo_or_stale",
            "sourceFreshness": "synthetic_delayed",
            "fixtureBacked": True,
            "syntheticData": True,
            "forceRefreshIgnored": True,
        }
        assert packet["observationBoundary"] == {
            "researchOnly": True,
            "decisionGrade": False,
            "executionSupported": False,
            "orderPlacement": False,
            "brokerExecution": False,
            "portfolioMutation": False,
        }
        assert packet["researchNextSteps"] == [
            "Confirm non-demo chain freshness before elevating confidence.",
            "Review thin-liquidity rows before comparing structures.",
        ]
        _assert_no_execution_implication_fields(payload)
        _assert_no_safety_leaks(payload)
    finally:
        client.close()


def test_structure_signal_packet_respects_fixture_metadata_over_live_text_hints() -> None:
    payload = OptionChainResponse(
        symbol="TEM",
        market="US",
        underlying={"price": 52.4, "freshness": "live"},
        expiration="2026-06-19",
        calls=[
            OptionContract(
                symbol="TEM",
                contractSymbol="TEM260619C00055000",
                side="call",
                expiration="2026-06-19",
                strike=55,
                bid=4.1,
                ask=4.3,
                volume=100,
                openInterest=500,
                impliedVolatility=0.62,
                greeks=OptionGreeks(delta=0.51, gamma=0.03, theta=-0.02, vega=0.12),
                dte=44,
                asOf="2026-05-06T13:45:00Z",
                source="authorized_live_feed",
                freshness="live",
            ),
        ],
        puts=[
            OptionContract(
                symbol="TEM",
                contractSymbol="TEM260619P00050000",
                side="put",
                expiration="2026-06-19",
                strike=50,
                bid=3.2,
                ask=3.4,
                volume=120,
                openInterest=600,
                impliedVolatility=0.66,
                greeks=OptionGreeks(delta=-0.42, gamma=0.03, theta=-0.02, vega=0.11),
                dte=44,
                asOf="2026-05-06T13:45:00Z",
                source="authorized_live_feed",
                freshness="live",
            ),
        ],
        filtersApplied={},
        chainAsOf="2026-05-06T13:45:00Z",
        source="authorized_live_feed",
        metadata=OptionsMetadata(
            fixtureBacked=True,
            syntheticData=True,
            forceRefreshIgnored=True,
            providerName="authorized_live_feed",
        ),
    ).model_dump(by_alias=True)

    boundary = payload["optionsStructureSignalPacket"]["staleOrDemoBoundary"]
    assert boundary == {
        "state": "demo_or_stale",
        "sourceFreshness": "synthetic_delayed",
        "fixtureBacked": True,
        "syntheticData": True,
        "forceRefreshIgnored": True,
    }


def test_structure_signal_packet_marks_missing_bid_ask_liquidity_partial() -> None:
    payload = OptionChainResponse(
        symbol="TEM",
        market="US",
        underlying={"price": 52.4, "freshness": "synthetic_delayed"},
        expiration="2026-06-19",
        calls=[
            OptionContract(
                symbol="TEM",
                contractSymbol="TEM260619C00055000",
                side="call",
                expiration="2026-06-19",
                strike=55,
                volume=500,
                openInterest=500,
                impliedVolatility=0.62,
                greeks=OptionGreeks(delta=0.51, gamma=0.03, theta=-0.02, vega=0.12),
                dte=44,
                asOf="2026-05-06T13:45:00Z",
                source="synthetic_fixture",
                freshness="synthetic_delayed",
            ),
        ],
        puts=[
            OptionContract(
                symbol="TEM",
                contractSymbol="TEM260619P00050000",
                side="put",
                expiration="2026-06-19",
                strike=50,
                volume=520,
                openInterest=530,
                impliedVolatility=0.66,
                greeks=OptionGreeks(delta=-0.42, gamma=0.03, theta=-0.02, vega=0.11),
                dte=44,
                asOf="2026-05-06T13:45:00Z",
                source="synthetic_fixture",
                freshness="synthetic_delayed",
            ),
        ],
        filtersApplied={},
        chainAsOf="2026-05-06T13:45:00Z",
        source="synthetic_fixture",
        metadata=OptionsMetadata(),
    ).model_dump(by_alias=True)

    liquidity = payload["optionsStructureSignalPacket"]["liquidityObservation"]
    assert liquidity["contractsWithBidAsk"] == 0
    assert liquidity["thinLiquidityCount"] == 0
    assert liquidity["wideSpreadCount"] == 0
    assert liquidity["state"] == "partial"


def _readiness_contract(
    *,
    contract_symbol: str,
    side: str,
    expiration: str = "2026-06-19",
    strike: float = 55.0,
    bid: float | None = 4.1,
    ask: float | None = 4.3,
    last: float | None = 4.2,
    volume: int | None = 240,
    open_interest: int | None = 920,
    implied_volatility: float | None = 0.62,
    greeks: OptionGreeks | None = None,
    greeks_missing: bool = False,
) -> OptionContract:
    return OptionContract(
        symbol="TEM",
        contractSymbol=contract_symbol,
        side=side,
        expiration=expiration,
        strike=strike,
        bid=bid,
        ask=ask,
        last=last,
        volume=volume,
        openInterest=open_interest,
        impliedVolatility=implied_volatility,
        greeks=None
        if greeks_missing
        else (
            greeks
            if greeks is not None
            else OptionGreeks(
                delta=0.51 if side == "call" else -0.42,
                gamma=0.03,
                theta=-0.02,
                vega=0.12,
                rho=0.01,
            )
        ),
        dte=44,
        asOf="2026-05-06T13:45:00Z",
        source="review_live_snapshot",
        freshness="live",
        spreadPct=4.8,
    )


def _authorized_chain_payload(
    *,
    calls: list[OptionContract] | None = None,
    puts: list[OptionContract] | None = None,
    metadata: OptionsMetadata | None = None,
    source: str = "review_live_snapshot",
    freshness: str = "live",
) -> dict:
    return OptionChainResponse(
        symbol="TEM",
        market="US",
        underlying={"price": 52.4, "freshness": freshness},
        expiration=None,
        calls=calls
        if calls is not None
        else [
            _readiness_contract(contract_symbol="TEM260619C00050000", side="call", strike=50.0),
            _readiness_contract(contract_symbol="TEM260619C00055000", side="call", strike=55.0),
            _readiness_contract(contract_symbol="TEM260821C00060000", side="call", expiration="2026-08-21", strike=60.0),
        ],
        puts=puts
        if puts is not None
        else [
            _readiness_contract(contract_symbol="TEM260619P00050000", side="put", strike=50.0),
            _readiness_contract(contract_symbol="TEM260619P00045000", side="put", strike=45.0),
            _readiness_contract(contract_symbol="TEM260821P00045000", side="put", expiration="2026-08-21", strike=45.0),
        ],
        filtersApplied={},
        chainAsOf="2026-05-06T13:45:00Z",
        source=source,
        metadata=metadata
        or OptionsMetadata(
            fixtureBacked=False,
            syntheticData=False,
            providerName="review_live_snapshot",
            liveProviderEnabled=True,
            providerCapabilities={
                "sourceType": "live",
                "fixtureOnly": False,
                "liveEnabled": True,
                "tradeableData": True,
                "authorityTier": "decision_grade",
                "supportsExpirations": True,
                "supportsChain": True,
                "supportsBidAsk": True,
                "supportsIv": True,
                "supportsGreeks": True,
                "supportsOpenInterest": True,
                "supportsVolume": True,
            },
        ),
    ).model_dump(by_alias=True)


def test_chain_readiness_marks_complete_authorized_chain_ready() -> None:
    payload = _authorized_chain_payload()

    readiness = payload["optionsChainReadiness"]
    assert readiness["contractVersion"] == "options-chain-readiness-v1"
    assert readiness["overallState"] == "ready"
    assert readiness["chainState"] == "available"
    assert readiness["configurationState"] == "available"
    assert readiness["dataBoundary"] == "provider_backed"
    assert readiness["authorityState"] == "authoritative"
    assert readiness["scoreAuthority"] == "authoritative"
    assert readiness["expirationCoverage"] == {
        "state": "available",
        "expirationCount": 2,
        "missingCount": 0,
        "coveredExpirations": ["2026-06-19", "2026-08-21"],
    }
    assert readiness["strikeCoverage"] == {
        "state": "available",
        "strikeCount": 4,
        "sparseCount": 0,
    }
    for key in ("iv", "greeks", "openInterest", "volume", "quote"):
        assert readiness["fieldCompleteness"][key]["state"] == "available"
    assert readiness["blockingReasons"] == []
    assert readiness["nextEvidenceNeeded"] == []


def test_chain_readiness_missing_configuration_blocks_and_observes_only() -> None:
    payload = _authorized_chain_payload(
        metadata=OptionsMetadata(
            fixtureBacked=False,
            syntheticData=False,
            providerName="review_snapshot",
            liveProviderEnabled=False,
            providerCapabilities={},
        )
    )

    readiness = payload["optionsChainReadiness"]
    assert readiness["overallState"] == "blocked"
    assert readiness["configurationState"] == "missing"
    assert readiness["authorityState"] == "observation_only"
    assert readiness["scoreAuthority"] == "observation_only"
    assert "missing_provider_configuration" in readiness["blockingReasons"]
    assert "provider_not_authoritative" in readiness["blockingReasons"]


def test_chain_readiness_demo_sample_chain_is_observation_only() -> None:
    client = _client()
    try:
        response = client.get(
            "/api/v1/options/underlyings/TEM/chain",
            params={"expiration": "2026-06-19", "includeGreeks": "true"},
        )
        assert response.status_code == 200
        payload = response.json()

        readiness = payload["optionsChainReadiness"]
        assert readiness["chainState"] == "available"
        assert readiness["dataBoundary"] == "demo_sample"
        assert readiness["authorityState"] == "observation_only"
        assert readiness["overallState"] == "blocked"
        assert readiness["blockingReasons"]
        assert all("provider" not in reason.lower() for reason in readiness["blockingReasons"])
        assert readiness["fieldCompleteness"]["iv"]["state"] == "available"
        assert readiness["fieldCompleteness"]["greeks"]["state"] == "available"
    finally:
        client.close()


def test_chain_readiness_marks_missing_iv_greeks_oi_volume_and_quotes_partial() -> None:
    payload = _authorized_chain_payload(
        calls=[
            _readiness_contract(contract_symbol="TEM260619C00050000", side="call", strike=50.0),
            _readiness_contract(
                contract_symbol="TEM260619C00055000",
                side="call",
                strike=55.0,
                bid=None,
                ask=None,
                last=None,
                volume=None,
                open_interest=None,
                implied_volatility=None,
                greeks_missing=True,
            ),
        ],
        puts=[],
    )

    readiness = payload["optionsChainReadiness"]
    assert readiness["overallState"] == "partial"
    assert readiness["chainState"] == "partial"
    assert readiness["fieldCompleteness"]["iv"]["state"] == "partial"
    assert readiness["fieldCompleteness"]["greeks"]["state"] == "partial"
    assert readiness["fieldCompleteness"]["openInterest"]["state"] == "partial"
    assert readiness["fieldCompleteness"]["volume"]["state"] == "partial"
    assert readiness["fieldCompleteness"]["quote"]["state"] == "partial"
    assert set(readiness["blockingReasons"]) >= {
        "partial_iv",
        "partial_greeks",
        "partial_open_interest",
        "partial_volume",
        "partial_quote",
    }


def test_chain_readiness_marks_sparse_expiration_and_strike_coverage_limited() -> None:
    payload = _authorized_chain_payload(
        calls=[_readiness_contract(contract_symbol="TEM260619C00055000", side="call", strike=55.0)],
        puts=[],
    )

    readiness = payload["optionsChainReadiness"]
    assert readiness["overallState"] == "partial"
    assert readiness["expirationCoverage"] == {
        "state": "limited",
        "expirationCount": 1,
        "missingCount": 1,
        "coveredExpirations": ["2026-06-19"],
    }
    assert readiness["strikeCoverage"] == {
        "state": "limited",
        "strikeCount": 1,
        "sparseCount": 1,
    }
    assert "limited_expiration_coverage" in readiness["blockingReasons"]
    assert "limited_strike_coverage" in readiness["blockingReasons"]


def test_nvda_fixture_underlying_summary_expirations_and_chain_are_observation_only() -> None:
    client = _client()
    try:
        summary = client.get("/api/v1/options/underlyings/NVDA/summary", params={"forceRefresh": "true"})
        expirations = client.get("/api/v1/options/underlyings/nvda/expirations")
        chain = client.get(
            "/api/v1/options/underlyings/NVDA/chain",
            params={"expiration": "2026-06-19", "includeGreeks": "true"},
        )

        assert summary.status_code == 200
        assert expirations.status_code == 200
        assert chain.status_code == 200

        summary_payload = summary.json()
        expirations_payload = expirations.json()
        chain_payload = chain.json()
        assert summary_payload["symbol"] == "NVDA"
        assert summary_payload["observationOnly"] is True
        assert summary_payload["decisionGrade"] is False
        assert summary_payload["metadata"]["fixtureBacked"] is True
        assert summary_payload["metadata"]["syntheticData"] is True
        assert summary_payload["metadata"]["liveProviderEnabled"] is False
        assert summary_payload["metadata"]["noExternalCalls"] is True
        assert summary_payload["optionsReadiness"]["decisionGrade"] is False
        assert summary_payload["optionsReadiness"]["noTradingBoundary"] == {
            "analyticalOnly": True,
            "noBrokerExecution": True,
            "noOrderPlacement": True,
            "noPortfolioMutation": True,
            "noTradingRecommendation": True,
        }
        assert expirations_payload["symbol"] == "NVDA"
        assert expirations_payload["observationOnly"] is True
        assert expirations_payload["decisionGrade"] is False
        assert [item["date"] for item in expirations_payload["expirations"]] == [
            "2026-06-19",
            "2026-08-21",
        ]
        assert expirations_payload["optionsReadiness"]["decisionGrade"] is False
        assert chain_payload["symbol"] == "NVDA"
        assert chain_payload["observationOnly"] is True
        assert chain_payload["decisionGrade"] is False
        assert chain_payload["calls"]
        assert chain_payload["puts"]
        assert chain_payload["calls"][0]["contractSymbol"].startswith("NVDA")
        assert chain_payload["puts"][0]["contractSymbol"].startswith("NVDA")
        assert chain_payload["optionsReadiness"]["decisionGrade"] is False
        assert chain_payload["metadata"]["liveProviderEnabled"] is False
        for payload in (summary_payload, expirations_payload, chain_payload):
            _assert_consumer_safe_sandbox_metadata(payload)
            _assert_no_execution_implication_fields(payload)
            _assert_no_safety_leaks(payload)
            _assert_no_options_consumer_redaction_leaks(payload)
    finally:
        client.close()


def test_chain_endpoint_can_return_puts_only() -> None:
    client = _client()
    try:
        response = client.get(
            "/api/v1/options/underlyings/TEM/chain",
            params={"expiration": "2026-06-19", "side": "put"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["calls"] == []
        assert [item["side"] for item in payload["puts"]] == ["put", "put"]
    finally:
        client.close()


def test_chain_endpoint_matches_service_alias_contract() -> None:
    request_params = {
        "expiration": "2026-06-19",
        "side": "call",
        "minOpenInterest": 100,
        "maxSpreadPct": 20,
        "includeGreeks": "false",
        "forceRefresh": "true",
    }

    client = _client()
    try:
        response = client.get("/api/v1/options/underlyings/TEM/chain", params=request_params)
        assert response.status_code == 200

        expected_payload = OptionsLabService(
            fixture_path=Path("tests/fixtures/options/tem_chain.json")
        ).get_chain(
            "TEM",
            expiration="2026-06-19",
            side="call",
            min_open_interest=100,
            max_spread_pct=20,
            include_greeks=False,
            force_refresh=True,
        )
        assert isinstance(expected_payload, OptionChainResultModel)
        assert response.json() == project_consumer_api_payload(
            options._map_chain_response(expected_payload),
            surface="options-chain",
        )
    finally:
        client.close()


def test_unsupported_symbol_returns_sanitized_error() -> None:
    client = _client()
    try:
        response = client.get("/api/v1/options/underlyings/hk00700/chain")
        assert response.status_code == 404
        assert response.json()["detail"] == {
            "error": "unsupported_symbol_or_market",
            "message": "Options Lab Phase 1 supports fixture-backed US listed equity options only.",
        }
    finally:
        client.close()


def test_chain_endpoint_rejects_live_provider_selection_without_live_calls() -> None:
    client = _client()
    try:
        with patch.dict(os.environ, {}, clear=True):
            response = client.get(
                "/api/v1/options/underlyings/TEM/chain",
                params={"marketDataProvider": "tradier"},
            )
        assert response.status_code == 400
        assert response.json()["detail"] == {
            "error": "options_provider_disabled",
            "message": "Requested Options Lab provider is fixture-only, disabled, or not implemented.",
        }
    finally:
        client.close()


def test_live_provider_stub_selection_does_not_call_external_paths_or_expose_secrets() -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("forbidden runtime path was called")

    client = _client()
    try:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("data_provider.base.DataFetcherManager.get_realtime_quote", side_effect=forbidden),
            patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
            patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
            patch("src.services.portfolio_service.PortfolioService.add_lot", side_effect=forbidden, create=True),
        ):
            response = client.get(
                "/api/v1/options/underlyings/TEM/chain",
                params={"marketDataProvider": "polygon"},
            )

        assert response.status_code == 400
        text = _json_text(response.json()).lower()
        assert "options_provider_disabled" in text
        for value in ("api_key", "apikey", "token=", "secret", "requesturl", "env"):
            assert value not in text
    finally:
        client.close()


def test_options_launch_surfaces_reject_live_provider_selection_safely_without_mutations() -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("forbidden runtime path was called")

    requests = [
        ("get", "/api/v1/options/underlyings/TEM/summary", None, {"marketDataProvider": "tradier"}),
        ("get", "/api/v1/options/underlyings/TEM/expirations", None, {"marketDataProvider": "tradier"}),
        ("get", "/api/v1/options/underlyings/TEM/chain", None, {"marketDataProvider": "tradier"}),
        (
            "post",
            "/api/v1/options/analyze",
            {
                "symbol": "TEM",
                "marketDataProvider": "tradier",
                "direction": "bullish",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
            },
            None,
        ),
        (
            "post",
            "/api/v1/options/scenario",
            {
                "symbol": "TEM",
                "marketDataProvider": "tradier",
                "strategy": "long_call",
                "contractSymbol": "TEM260619C00055000",
                "targetPrice": 65,
            },
            None,
        ),
        (
            "post",
            "/api/v1/options/strategies/compare",
            {
                "symbol": "TEM",
                "marketDataProvider": "tradier",
                "direction": "bullish",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
                "riskProfile": "balanced",
            },
            None,
        ),
        (
            "post",
            "/api/v1/options/decision/evaluate",
            {
                "symbol": "TEM",
                "marketDataProvider": "tradier",
                "strategy": "bull_call_spread",
                "expiration": "2026-06-19",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
            },
            None,
        ),
    ]

    client = _client()
    try:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("data_provider.base.DataFetcherManager.get_realtime_quote", side_effect=forbidden),
            patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
            patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
            patch("src.services.portfolio_service.PortfolioService.add_lot", side_effect=forbidden, create=True),
        ):
            for method, path, json_payload, params in requests:
                response = (
                    client.get(path, params=params)
                    if method == "get"
                    else client.post(path, json=json_payload)
                )
                assert response.status_code == 400
                assert response.json()["detail"] == {
                    "error": "options_provider_disabled",
                    "message": "Requested Options Lab provider is fixture-only, disabled, or not implemented.",
                }
                _assert_no_safety_leaks(response.json())
    finally:
        client.close()


def test_endpoint_does_not_call_live_provider_llm_market_cache_or_mutation_paths() -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("forbidden runtime path was called")

    client = _client()
    try:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("data_provider.base.DataFetcherManager.get_realtime_quote", side_effect=forbidden),
            patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
            patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
            patch("src.services.portfolio_service.PortfolioService.add_lot", side_effect=forbidden, create=True),
        ):
            response = client.get(
                "/api/v1/options/underlyings/TEM/chain",
                params={"forceRefresh": "true"},
            )

        assert response.status_code == 200
        assert response.json()["metadata"]["noExternalCalls"] is True
    finally:
        client.close()


def test_endpoint_response_excludes_raw_provider_and_recommendation_language() -> None:
    client = _client()
    try:
        responses = [
            client.get("/api/v1/options/underlyings/TEM/summary"),
            client.get("/api/v1/options/underlyings/TEM/expirations"),
            client.get("/api/v1/options/underlyings/TEM/chain"),
            client.post(
                "/api/v1/options/analyze",
                json={
                    "symbol": "TEM",
                    "direction": "bullish",
                    "targetPrice": 65,
                    "targetDate": "2026-08-21",
                    "maxPremium": 600,
                    "riskProfile": "balanced",
                    "strategies": ["long_call"],
                    "forceRefresh": True,
                },
            ),
            client.post(
                "/api/v1/options/scenario",
                json={
                    "symbol": "TEM",
                    "strategy": "long_call",
                    "contractSymbol": "TEM260619C00055000",
                    "targetPrice": 65,
                    "forceRefresh": True,
                },
            ),
        ]
        assert all(response.status_code == 200 for response in responses)
        text = "\n".join(_json_text(response.json()) for response in responses).lower()
        for value in SAFETY_BLOCKED_MARKERS:
            assert value not in text
    finally:
        client.close()


def test_options_lab_success_responses_expose_consumer_safe_sandbox_metadata() -> None:
    client = _client()
    try:
        responses = [
            client.get("/api/v1/options/underlyings/TEM/summary"),
            client.get("/api/v1/options/underlyings/TEM/expirations"),
            client.get("/api/v1/options/underlyings/TEM/chain"),
            client.post(
                "/api/v1/options/analyze",
                json={
                    "symbol": "TEM",
                    "direction": "bullish",
                    "targetPrice": 65,
                    "targetDate": "2026-08-21",
                    "maxPremium": 600,
                    "riskProfile": "balanced",
                    "strategies": ["long_call"],
                },
            ),
            client.post(
                "/api/v1/options/scenario",
                json={
                    "symbol": "TEM",
                    "strategy": "long_call",
                    "contractSymbol": "TEM260619C00055000",
                    "targetPrice": 65,
                },
            ),
            client.post(
                "/api/v1/options/strategies/compare",
                json={
                    "symbol": "TEM",
                    "direction": "bullish",
                    "targetPrice": 65,
                    "targetDate": "2026-06-19",
                    "riskProfile": "balanced",
                    "strategies": ["long_call", "bull_call_spread"],
                },
            ),
            client.post(
                "/api/v1/options/decision/evaluate",
                json={
                    "symbol": "TEM",
                    "strategy": "bull_call_spread",
                    "expiration": "2026-06-19",
                    "targetPrice": 65,
                    "targetDate": "2026-06-19",
                    "riskBudget": 600,
                },
            ),
        ]
        assert all(response.status_code == 200 for response in responses)
        for response in responses:
            payload = response.json()
            _assert_consumer_safe_sandbox_metadata(payload)
            _assert_no_execution_implication_fields(payload)
    finally:
        client.close()


def test_analyze_endpoint_returns_ranked_call_candidates() -> None:
    client = _client()
    try:
        response = client.post(
            "/api/v1/options/analyze",
            json={
                "symbol": "TEM",
                "direction": "bullish",
                "targetPrice": 65,
                "targetDate": "2026-08-21",
                "riskProfile": "balanced",
                "strategies": ["long_call"],
                "forceRefresh": True,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["underlying"]["price"] == 52.4
        assert [item["contract"]["side"] for item in payload["candidateContracts"]] == ["call", "call", "call", "call"]
        assert payload["candidateContracts"][0]["score"] >= payload["candidateContracts"][-1]["score"]
        assert payload["metadata"]["forceRefreshIgnored"] is True
        assert payload["metadata"]["noExternalCalls"] is True
        assert payload["metadata"]["scoringEngine"] == "deterministic_fixture_scoring_v1"
    finally:
        client.close()


def test_analyze_endpoint_matches_service_alias_contract() -> None:
    request_payload = {
        "symbol": "TEM",
        "direction": "bullish",
        "targetPrice": 65,
        "targetDate": "2026-08-21",
        "riskProfile": "balanced",
        "strategies": ["long_call"],
        "forceRefresh": True,
    }

    client = _client()
    try:
        response = client.post("/api/v1/options/analyze", json=request_payload)
        assert response.status_code == 200

        expected_payload = options._map_analyze_response(
            OptionsLabService(fixture_path=Path("tests/fixtures/options/tem_chain.json")).analyze(request_payload)
        )
        expected_payload = project_consumer_api_payload(expected_payload, surface="options-analyze")
        assert response.json() == expected_payload
    finally:
        client.close()


def test_analyze_endpoint_filters_max_premium_and_does_not_call_external_paths() -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("forbidden runtime path was called")

    client = _client()
    try:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("data_provider.base.DataFetcherManager.get_realtime_quote", side_effect=forbidden),
            patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
            patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
            patch("src.services.portfolio_service.PortfolioService.add_lot", side_effect=forbidden, create=True),
        ):
            response = client.post(
                "/api/v1/options/analyze",
                json={
                    "symbol": "TEM",
                    "direction": "bullish",
                    "targetPrice": 65,
                    "targetDate": "2026-06-19",
                    "maxPremium": 300,
                    "riskProfile": "balanced",
                    "strategies": ["long_call"],
                    "forceRefresh": True,
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert [item["contract"]["contractSymbol"] for item in payload["candidateContracts"]] == [
            "TEM260619C00055000",
            "TEM260619C00065000",
        ]
        assert all(item["premiumAtRisk"] <= 300 for item in payload["candidateContracts"])
    finally:
        client.close()


def test_scenario_endpoint_returns_expiration_payoff_grid() -> None:
    client = _client()
    try:
        response = client.post(
            "/api/v1/options/scenario",
            json={
                "symbol": "TEM",
                "strategy": "long_put",
                "contractSymbol": "TEM260619P00050000",
                "targetPrice": 45,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["contract"]["contractSymbol"] == "TEM260619P00050000"
        assert payload["risk"]["premiumAtRisk"] == 250
        assert payload["risk"]["breakeven"] == 47.5
        target = next(row for row in payload["expirationPayoffGrid"] if row["label"] == "custom_target")
        assert target["grossPayoff"] == 500
        assert target["netPayoff"] == 250
        assert payload["preExpirationTheoreticalPricing"]["available"] is False
        assert payload["metadata"]["noOrderPlacement"] is True
    finally:
        client.close()


def test_scenario_endpoint_matches_service_alias_contract() -> None:
    request_payload = {
        "symbol": "TEM",
        "strategy": "long_put",
        "contractSymbol": "TEM260619P00050000",
        "targetPrice": 45,
    }

    client = _client()
    try:
        response = client.post("/api/v1/options/scenario", json=request_payload)
        assert response.status_code == 200

        expected_payload = options._map_scenario_response(
            OptionsLabService(fixture_path=Path("tests/fixtures/options/tem_chain.json")).scenario(request_payload)
        )
        expected_payload = project_consumer_api_payload(expected_payload, surface="options-scenario")
        assert response.json() == expected_payload
    finally:
        client.close()


def test_analyze_unsupported_symbol_returns_sanitized_error() -> None:
    client = _client()
    try:
        response = client.post(
            "/api/v1/options/analyze",
            json={"symbol": "HK00700", "direction": "bullish", "targetPrice": 65, "targetDate": "2026-08-21"},
        )
        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "unsupported_symbol_or_market"
        assert "HK00700" not in _json_text(response.json())
    finally:
        client.close()


def test_strategy_compare_endpoint_returns_defined_risk_structures() -> None:
    client = _client()
    try:
        response = client.post(
            "/api/v1/options/strategies/compare",
            json={
                "symbol": "TEM",
                "direction": "bullish",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
                "riskProfile": "balanced",
                "strategies": ["long_call", "long_put", "bull_call_spread", "bear_put_spread"],
                "forceRefresh": True,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert [strategy["strategyType"] for strategy in payload["strategies"]] == [
            "long_call",
            "long_put",
            "bull_call_spread",
            "bear_put_spread",
        ]
        bull = next(strategy for strategy in payload["strategies"] if strategy["strategyType"] == "bull_call_spread")
        assert all(strategy["maxLoss"] is not None for strategy in payload["strategies"])
        assert all(strategy["breakeven"] is not None for strategy in payload["strategies"])
        assert all(strategy["noAdviceDisclosure"] for strategy in payload["strategies"])
        assert all(strategy["liquidityWarnings"] or strategy["ivThetaNotes"] or strategy["limitations"] for strategy in payload["strategies"])
        assert bull["netDebit"] == 230
        assert bull["maxLoss"] == 230
        assert bull["maxGain"] == 270
        assert bull["breakeven"] == 52.3
        assert bull["payoffAtTarget"] == 270
        assert payload["metadata"]["forceRefreshIgnored"] is True
        assert payload["metadata"]["noBrokerConnection"] is True
        assert payload["metadata"]["noPortfolioMutation"] is True
    finally:
        client.close()


def test_strategy_analyzer_endpoint_returns_payoff_probability_and_readiness_contract() -> None:
    client = _client()
    try:
        response = client.post(
            "/api/v1/options/strategies/analyze",
            json={
                "symbol": "TEM",
                "expiration": "2026-06-19",
                "strategies": ["long_straddle", "long_strangle", "bull_call_spread", "iron_condor"],
                "scenarioPrices": [40, 52.4, 70],
                "forceRefresh": True,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["observationOnly"] is True
        assert payload["decisionGrade"] is False
        assert payload["strategyReadiness"]["strategyStructureState"] == "available"
        assert payload["strategyReadiness"]["observationOnly"] is True
        assert payload["strategyReadiness"]["decisionGrade"] is False
        assert [item["strategyType"] for item in payload["analyses"]] == [
            "long_straddle",
            "long_strangle",
            "bull_call_spread",
            "iron_condor",
        ]

        straddle = payload["analyses"][0]
        assert straddle["netDebit"] == 750
        assert straddle["maxLoss"] == 750
        assert straddle["maxProfit"] is None
        assert straddle["breakevens"] == [42.5, 57.5]
        assert straddle["payoffTable"][0] == {
            "underlyingPrice": 40.0,
            "grossPayoff": 1000.0,
            "netPayoff": 250.0,
        }
        assert straddle["aggregateGreeks"] == {
            "delta": 0.22,
            "gamma": 0.091,
            "theta": -0.133,
            "vega": 0.234,
            "rho": 0.012,
        }
        assert straddle["modelImpliedProbability"]["state"] == "available"
        assert 0 <= straddle["modelImpliedProbability"]["modelImpliedProbabilityOfProfit"] <= 1
        assert straddle["modelImpliedProbability"]["inputs"]["riskFreeRate"] == 0.04
        assert straddle["historicalWinRate"] == {
            "state": "unavailable",
            "value": None,
            "blockers": ["historical_options_chain_data_unavailable"],
        }

        condor = next(item for item in payload["analyses"] if item["strategyType"] == "iron_condor")
        assert condor["netCredit"] == 345
        assert condor["maxProfit"] == 345
        assert condor["maxLoss"] == 655
        assert condor["breakevens"] == [46.55, 58.45]
        assert condor["modelImpliedProbability"]["state"] == "available"
        _assert_no_safety_leaks(payload)
    finally:
        client.close()


def test_strategy_compare_endpoint_matches_service_alias_contract() -> None:
    request_payload = {
        "symbol": "TEM",
        "direction": "bullish",
        "targetPrice": 65,
        "targetDate": "2026-06-19",
        "riskProfile": "balanced",
        "strategies": ["long_call", "long_put", "bull_call_spread", "bear_put_spread"],
        "forceRefresh": True,
    }

    client = _client()
    try:
        response = client.post("/api/v1/options/strategies/compare", json=request_payload)
        assert response.status_code == 200

        expected_payload = options._map_strategy_compare_response(
            OptionsLabService(fixture_path=Path("tests/fixtures/options/tem_chain.json")).compare_strategies(
                request_payload
            )
        )
        expected_payload = project_consumer_api_payload(
            expected_payload,
            surface="options-strategies-compare",
        )
        assert response.json() == expected_payload
    finally:
        client.close()


def test_analyze_scenario_and_compare_endpoint_mappers_preserve_alias_contracts() -> None:
    service = OptionsLabService(fixture_path=Path("tests/fixtures/options/tem_chain.json"))
    contract = service.get_chain("TEM", expiration="2026-06-19", side="call").calls[1]

    analyze_result = AnalyzeResultModel(
        symbol="TEM",
        underlying={"symbol": "TEM", "price": 52.4},
        assumptions={
            "direction": "bullish",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "riskProfile": "balanced",
            "contractMultiplier": 100,
        },
        option_chain_summary={
            "source": "synthetic_fixture",
            "chainAsOf": "2026-05-06T14:30:00Z",
            "expirationCount": 2,
            "callCount": 3,
            "putCount": 2,
            "candidateCount": 1,
        },
        candidate_contracts=[
            AnalyzeCandidateModel(
                strategy="long_call",
                contract=contract,
                score=78.25,
                grade_label="B",
                premium_at_risk=270.0,
                breakeven=57.7,
                required_move_pct=10.11,
                target_payoff=730.0,
                sub_scores=AnalyzeSubScoresModel(
                    directional_fit=100.0,
                    delta_fit=88.5,
                    breakeven_difficulty=84.2,
                    premium_efficiency=92.0,
                    liquidity_score=76.5,
                    spread_penalty=82.0,
                    iv_risk=64.0,
                    theta_risk=58.0,
                    dte_fit=90.0,
                    target_scenario_payoff=95.0,
                    max_loss_budget_fit=100.0,
                    oi_volume_confidence=72.5,
                    data_freshness_confidence=100.0,
                ),
                top_positive_drivers=["directional_fit", "target_scenario_payoff", "premium_efficiency"],
                top_risk_drivers=["theta_risk", "iv_risk", "oi_volume_confidence"],
                assumptions_used={
                    "direction": "bullish",
                    "targetPrice": 65,
                    "targetDate": "2026-06-19",
                    "riskProfile": "balanced",
                    "contractMultiplier": 100,
                    "pricingMode": "expiration_intrinsic_minus_mid_premium",
                },
                data_confidence="high",
                not_advice_disclosure=(
                    "Analytical ranking under explicit assumptions only; not investment advice or an instruction."
                ),
            )
        ],
        risks=["options_are_high_risk"],
        limitations=["synthetic_fixture_data_only"],
        metadata=OptionsLabMetadataModel(scoring_engine="deterministic_fixture_scoring_v1"),
    )
    analyze_payload = options._map_analyze_response(analyze_result).model_dump(by_alias=True)
    assert analyze_payload["optionsReadiness"] == analyze_payload["optionsResearchReadiness"]
    assert analyze_payload["optionsReadiness"]["optionsResearchReady"] is False
    assert analyze_payload["optionsReadiness"]["readinessState"] == "blocked"
    analyze_contract_only = dict(analyze_payload)
    analyze_contract_only.pop("optionsReadiness")
    analyze_contract_only.pop("optionsResearchReadiness")
    assert analyze_contract_only == {
        "symbol": "TEM",
        "underlying": {"symbol": "TEM", "price": 52.4},
        "assumptions": {
            "direction": "bullish",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "riskProfile": "balanced",
            "contractMultiplier": 100,
        },
        "optionChainSummary": {
            "source": "synthetic_fixture",
            "chainAsOf": "2026-05-06T14:30:00Z",
            "expirationCount": 2,
            "callCount": 3,
            "putCount": 2,
            "candidateCount": 1,
        },
        "candidateContracts": [
            {
                "strategy": "long_call",
                "contract": contract.model_dump(by_alias=True),
                "score": 78.25,
                "gradeLabel": "B",
                "premiumAtRisk": 270.0,
                "breakeven": 57.7,
                "requiredMovePct": 10.11,
                "targetPayoff": 730.0,
                "scoring": {
                    "subScores": {
                        "directionalFit": 100.0,
                        "deltaFit": 88.5,
                        "breakevenDifficulty": 84.2,
                        "premiumEfficiency": 92.0,
                        "liquidityScore": 76.5,
                        "spreadPenalty": 82.0,
                        "ivRisk": 64.0,
                        "thetaRisk": 58.0,
                        "dteFit": 90.0,
                        "targetScenarioPayoff": 95.0,
                        "maxLossBudgetFit": 100.0,
                        "oiVolumeConfidence": 72.5,
                        "dataFreshnessConfidence": 100.0,
                    },
                    "gradeLabel": "B",
                    "topPositiveDrivers": ["directional_fit", "target_scenario_payoff", "premium_efficiency"],
                    "topRiskDrivers": ["theta_risk", "iv_risk", "oi_volume_confidence"],
                    "assumptionsUsed": {
                        "direction": "bullish",
                        "targetPrice": 65,
                        "targetDate": "2026-06-19",
                        "riskProfile": "balanced",
                        "contractMultiplier": 100,
                        "pricingMode": "expiration_intrinsic_minus_mid_premium",
                    },
                    "dataConfidence": "high",
                    "notAdviceDisclosure": (
                        "Analytical ranking under explicit assumptions only; "
                        "not investment advice or an instruction."
                    ),
                },
            }
        ],
        "risks": ["options_are_high_risk"],
        "limitations": ["synthetic_fixture_data_only"],
        "metadata": options._map_options_metadata(analyze_result.metadata).model_dump(by_alias=True),
    }

    scenario_result = ScenarioResultModel(
        symbol="TEM",
        underlying={"symbol": "TEM", "price": 52.4},
        strategy="long_put",
        contract=contract.model_copy(update={"side": "put", "contractSymbol": "TEM260619P00050000"}),
        expiration_payoff_grid=[
            ScenarioPayoffRowModel(
                label="custom_target",
                underlying_price=65.0,
                gross_payoff=1000.0,
                net_payoff=730.0,
                return_on_premium_pct=270.37,
            )
        ],
        risk=ScenarioRiskModel(
            premium_at_risk=270.0,
            breakeven=57.7,
            required_move_pct=10.11,
            max_loss=270.0,
        ),
        pre_expiration_theoretical_pricing={
            "available": False,
            "reason": "phase3_expiration_payoff_only",
        },
        limitations=["synthetic_fixture_data_only"],
        metadata=OptionsLabMetadataModel(strategy_engine="expiration_payoff_v1"),
    )
    scenario_payload = options._map_scenario_response(scenario_result).model_dump(by_alias=True)
    assert scenario_payload["optionsReadiness"] == scenario_payload["optionsResearchReadiness"]
    assert scenario_payload["optionsReadiness"]["optionsResearchReady"] is False
    assert scenario_payload["optionsReadiness"]["readinessState"] == "blocked"
    scenario_frame = scenario_payload["optionsConsumerScenarioFrame"]
    _assert_consumer_scenario_frame_contract(scenario_frame)
    assert scenario_frame["frameState"] == "blocked"
    assert scenario_frame["underlying"] == {"symbol": "TEM", "price": 52.4}
    assert scenario_frame["strategyType"] == "long_put"
    assert scenario_frame["expiration"] == "2026-06-19"
    assert scenario_frame["scenarioCoverage"] == "single_contract"
    assert scenario_frame["chainQuality"] == {
        "hasChain": True,
        "contractCount": 1,
        "callCount": 0,
        "putCount": 1,
        "freshness": "synthetic_delayed",
        "sourceType": "synthetic_options_lab_fixture",
        "coverageState": "single_contract",
    }
    assert scenario_frame["liquidityGate"] == "clear"
    assert scenario_frame["ivGreeksGate"] == "clear"
    assert scenario_frame["spreadGate"] == "clear"
    assert scenario_frame["payoffEvidence"] == {
        "targetPrice": 65.0,
        "payoffAtTarget": 730.0,
        "payoffAtTargetLabel": "custom_target",
        "scenarioPoints": 1,
        "theoreticalPricingAvailable": False,
    }
    assert scenario_frame["riskEvidence"] == {
        "premiumAtRisk": 270.0,
        "maxLoss": 270.0,
        "maxGain": None,
        "breakeven": 57.7,
        "requiredMovePct": 10.11,
    }
    assert scenario_frame["assumptions"] == {
        "inputMode": "scenario",
        "targetPrice": 65.0,
        "customPriceCount": 0,
        "preExpirationTheoreticalPricing": "phase3_expiration_payoff_only",
    }
    assert scenario_frame["missingEvidence"] == [
        "provider authority",
        "live chain",
    ]
    assert scenario_frame["blockingReasons"] == scenario_payload["optionsReadiness"]["blockingReasons"]
    assert scenario_frame["nextEvidenceNeeded"] == scenario_payload["optionsReadiness"]["nextEvidenceNeeded"]
    scenario_contract_only = dict(scenario_payload)
    scenario_contract_only.pop("optionsConsumerScenarioFrame")
    scenario_contract_only.pop("optionsReadiness")
    scenario_contract_only.pop("optionsResearchReadiness")
    assert scenario_contract_only == {
        "symbol": "TEM",
        "underlying": {"symbol": "TEM", "price": 52.4},
        "strategy": "long_put",
        "contract": scenario_result.contract.model_dump(by_alias=True),
        "expirationPayoffGrid": [
            {
                "label": "custom_target",
                "underlyingPrice": 65.0,
                "grossPayoff": 1000.0,
                "netPayoff": 730.0,
                "returnOnPremiumPct": 270.37,
            }
        ],
        "risk": {
            "premiumAtRisk": 270.0,
            "breakeven": 57.7,
            "requiredMovePct": 10.11,
            "maxLoss": 270.0,
        },
        "preExpirationTheoreticalPricing": {
            "available": False,
            "reason": "phase3_expiration_payoff_only",
        },
        "limitations": ["synthetic_fixture_data_only"],
        "metadata": options._map_options_metadata(scenario_result.metadata).model_dump(by_alias=True),
    }

    compare_result = StrategyCompareResultModel(
        symbol="TEM",
        underlying={"symbol": "TEM", "price": 52.4},
        assumptions={
            "direction": "bullish",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "riskProfile": "balanced",
        },
        strategies=[
            StrategyComparisonModel(
                strategy_type="bull_call_spread",
                legs=[
                    StrategyLegModel(
                        action="buy",
                        side="call",
                        contract_symbol="TEM260619C00050000",
                        expiration="2026-06-19",
                        strike=50.0,
                        mid=5.0,
                    ),
                    StrategyLegModel(
                        action="sell",
                        side="call",
                        contract_symbol="TEM260619C00055000",
                        expiration="2026-06-19",
                        strike=55.0,
                        mid=2.7,
                    ),
                ],
                net_debit=230.0,
                max_loss=230.0,
                max_gain=270.0,
                breakeven=52.3,
                required_move_pct=-0.19,
                payoff_at_target=270.0,
                risk_reward_ratio=1.17,
                liquidity_warnings=[],
                iv_theta_notes=["iv_and_theta_can_change_strategy_value_before_expiration"],
                suitability_notes=[
                    "comparison_uses_user_assumptions_and_fixture_mid_prices",
                    "defined_risk_debit_spread_caps_loss_and_gain",
                ],
                limitations=["synthetic_fixture_data_only"],
                no_advice_disclosure=(
                    "Analytical comparison under explicit assumptions only; not investment advice or an instruction."
                ),
            )
        ],
        limitations=["synthetic_fixture_data_only"],
        metadata=OptionsLabMetadataModel(strategy_engine="defined_risk_strategy_compare_v1"),
    )
    compare_payload = options._map_strategy_compare_response(compare_result).model_dump(by_alias=True)
    assert compare_payload["optionsReadiness"] == compare_payload["optionsResearchReadiness"]
    assert compare_payload["optionsReadiness"]["optionsResearchReady"] is False
    assert compare_payload["optionsReadiness"]["readinessState"] == "blocked"
    compare_frame = compare_payload["optionsConsumerScenarioFrame"]
    _assert_consumer_scenario_frame_contract(compare_frame)
    assert compare_frame["frameState"] == "blocked"
    assert compare_frame["underlying"] == {"symbol": "TEM", "price": 52.4}
    assert compare_frame["strategyType"] == "bull_call_spread"
    assert compare_frame["expiration"] == "2026-06-19"
    assert compare_frame["scenarioCoverage"] == "strategy_compare_ready"
    assert compare_frame["chainQuality"] == {
        "hasChain": True,
        "contractCount": 2,
        "callCount": 2,
        "putCount": 0,
        "freshness": "unknown",
        "sourceType": "unknown",
        "coverageState": "strategy_compare_ready",
    }
    assert compare_frame["liquidityGate"] == "manual_review"
    assert compare_frame["ivGreeksGate"] == "manual_review"
    assert compare_frame["spreadGate"] == "manual_review"
    assert compare_frame["payoffEvidence"] == {
        "targetPrice": 65.0,
        "payoffAtTarget": 270.0,
        "candidateCount": 1,
        "topStrategyType": "bull_call_spread",
        "comparisonState": "strategy_compare_ready",
    }
    assert compare_frame["riskEvidence"] == {
        "premiumAtRisk": 230.0,
        "maxLoss": 230.0,
        "maxGain": 270.0,
        "breakeven": 52.3,
        "requiredMovePct": -0.19,
    }
    assert compare_frame["assumptions"] == {
        "inputMode": "strategy_compare",
        "direction": "bullish",
        "targetPrice": 65.0,
        "targetDate": "2026-06-19",
        "riskProfile": "balanced",
    }
    assert compare_frame["missingEvidence"] == [
        "provider authority",
        "live chain",
        "bid ask",
        "iv greeks",
    ]
    assert compare_frame["blockingReasons"] == compare_payload["optionsReadiness"]["blockingReasons"]
    assert compare_frame["nextEvidenceNeeded"] == compare_payload["optionsReadiness"]["nextEvidenceNeeded"]
    compare_contract_only = dict(compare_payload)
    compare_contract_only.pop("optionsConsumerScenarioFrame")
    compare_contract_only.pop("optionsReadiness")
    compare_contract_only.pop("optionsResearchReadiness")
    assert compare_contract_only == {
        "symbol": "TEM",
        "underlying": {"symbol": "TEM", "price": 52.4},
        "assumptions": {
            "direction": "bullish",
            "targetPrice": 65,
            "targetDate": "2026-06-19",
            "riskProfile": "balanced",
        },
        "strategies": [
            {
                "strategyType": "bull_call_spread",
                "legs": [
                    {
                        "action": "buy",
                        "side": "call",
                        "contractSymbol": "TEM260619C00050000",
                        "expiration": "2026-06-19",
                        "strike": 50.0,
                        "mid": 5.0,
                        "quantity": 1,
                    },
                    {
                        "action": "sell",
                        "side": "call",
                        "contractSymbol": "TEM260619C00055000",
                        "expiration": "2026-06-19",
                        "strike": 55.0,
                        "mid": 2.7,
                        "quantity": 1,
                    },
                ],
                "netDebit": 230.0,
                "maxLoss": 230.0,
                "maxGain": 270.0,
                "breakeven": 52.3,
                "requiredMovePct": -0.19,
                "payoffAtTarget": 270.0,
                "riskRewardRatio": 1.17,
                "liquidityWarnings": [],
                "ivThetaNotes": ["iv_and_theta_can_change_strategy_value_before_expiration"],
                "suitabilityNotes": [
                    "comparison_uses_user_assumptions_and_fixture_mid_prices",
                    "defined_risk_debit_spread_caps_loss_and_gain",
                ],
                "limitations": ["synthetic_fixture_data_only"],
                "noAdviceDisclosure": (
                    "Analytical comparison under explicit assumptions only; "
                    "not investment advice or an instruction."
                ),
            }
        ],
        "limitations": ["synthetic_fixture_data_only"],
        "metadata": options._map_options_metadata(compare_result.metadata).model_dump(by_alias=True),
    }


def test_strategy_compare_endpoint_filters_max_premium_and_rejects_unsupported_strategy() -> None:
    client = _client()
    try:
        filtered = client.post(
            "/api/v1/options/strategies/compare",
            json={
                "symbol": "TEM",
                "direction": "neutral",
                "targetPrice": 52.4,
                "targetDate": "2026-06-19",
                "maxPremium": 150,
                "riskProfile": "conservative",
                "strategies": ["long_call", "long_put", "bull_call_spread", "bear_put_spread"],
            },
        )
        assert filtered.status_code == 200
        filtered_strategies = filtered.json()["strategies"]
        assert [strategy["strategyType"] for strategy in filtered_strategies] == [
            "long_call",
            "long_put",
            "bear_put_spread",
        ]
        assert all(strategy["netDebit"] <= 150 for strategy in filtered_strategies)

        unsupported = client.post(
            "/api/v1/options/strategies/compare",
            json={
                "symbol": "TEM",
                "direction": "bullish",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
                "riskProfile": "balanced",
                "strategies": ["short_call"],
            },
        )
        assert unsupported.status_code == 400
        assert unsupported.json()["detail"] == {
            "error": "validation_error",
            "message": "Unsupported strategy requested for Options Lab Phase 4.",
        }
    finally:
        client.close()


def test_strategy_compare_endpoint_does_not_call_external_or_mutating_paths() -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("forbidden runtime path was called")

    client = _client()
    try:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("data_provider.base.DataFetcherManager.get_realtime_quote", side_effect=forbidden),
            patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
            patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
            patch("src.services.portfolio_service.PortfolioService.add_lot", side_effect=forbidden, create=True),
        ):
            response = client.post(
                "/api/v1/options/strategies/compare",
                json={
                    "symbol": "TEM",
                    "direction": "bullish",
                    "targetPrice": 65,
                    "targetDate": "2026-06-19",
                    "forceRefresh": True,
                },
            )

        assert response.status_code == 200
        text = _json_text(response.json()).lower()
        for value in SAFETY_BLOCKED_MARKERS + ["trade ticket"]:
            assert value not in text
    finally:
        client.close()


def test_decision_endpoint_returns_safe_demo_only_contract_quality() -> None:
    client = _client()
    try:
        response = client.post(
            "/api/v1/options/decision/evaluate",
            json={
                "symbol": "TEM",
                "strategy": "long_call",
                "expiration": "2026-06-19",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
                "riskBudget": 600,
                "forceRefresh": True,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["dataQuality"]["dataQualityTier"] == "synthetic_demo_only"
        assert payload["decisionLabel"] == "数据不足，禁止判断"
        assert payload["tradeQualityScore"] <= 35
        assert payload["ivRankStatus"] == "available"
        assert payload["ivRank"] == 68.89
        assert payload["ivPercentile"] == 71.43
        assert payload["expectedMove"]["expectedMoveSource"] == "straddle_mid"
        assert payload["expectedMove"]["expectedMoveAbs"] == 7.5
        assert payload["optimizer"]["optimizerLabel"] == "数据不足，禁止判断"
        assert payload["optimizer"]["preferredStrategyKey"] is None
        assert payload["rankedAlternatives"]
        assert payload["gateDecision"] == "数据不足，禁止判断"
        assert payload["decisionGrade"] is False
        assert payload["dataQualityGates"]["status"] == "blocked"
        assert payload["liquidityGates"]["status"] in {"blocked", "manual_review"}
        assert payload["gateIssues"]
        assert "failClosedReasonCodes" not in payload
        assert payload["evidenceGaps"]
        assert payload["researchNextSteps"]
        assert payload["optionsResearchReadiness"] == payload["optionsReadiness"]
        readiness = payload["optionsReadiness"]
        assert readiness["optionsResearchReady"] is False
        assert readiness["readinessState"] == "blocked"
        assert readiness["dataQualityTier"] == "synthetic_demo_only"
        assert readiness["decisionGrade"] is False
        assert "providerAuthority" not in readiness
        assert readiness["liquidityGate"] in {"blocked", "manual_review"}
        assert readiness["ivGreeksGate"] == "blocked"
        assert readiness["spreadGate"] in {"blocked", "manual_review"}
        assert readiness["scenarioCoverage"] == "single_contract"
        assert readiness["noTradingBoundary"] == {
            "analyticalOnly": True,
            "noBrokerExecution": True,
            "noOrderPlacement": True,
            "noPortfolioMutation": True,
            "noTradingRecommendation": True,
        }
        assert "provider_fixture_not_decision_grade" not in readiness["blockingReasons"]
        assert "Evidence is limited for this observation." in readiness["blockingReasons"]
        assert "Evidence is limited for this observation." in readiness["nextEvidenceNeeded"]
        assert payload["metadata"]["noExternalCalls"] is True
        assert payload["metadata"]["readOnly"] is True
        assert payload["metadata"]["mode"] == "sandbox"
        assert payload["metadata"]["dataStatus"] == "example_data"
        assert payload["metadata"]["label"] == "教学沙盒 · 示例数据"
        assert payload["metadata"]["noAdvice"] is True
        assert payload["metadata"]["executionSupported"] is False
        assert payload["metadata"]["noOrderPlacement"] is True
        assert payload["metadata"]["noBrokerConnection"] is True
        assert payload["metadata"]["noPortfolioMutation"] is True
        assert payload["metadata"]["noTradingRecommendation"] is True
        assert "not personalized financial advice" in payload["noAdviceDisclosure"]
    finally:
        client.close()


def test_decision_endpoint_excludes_raw_payloads_and_live_provider_paths() -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("forbidden runtime path was called")

    client = _client()
    try:
        with (
            patch("data_provider.base.DataFetcherManager.get_realtime_quote", side_effect=forbidden),
            patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
            patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
            patch("src.services.portfolio_service.PortfolioService.add_lot", side_effect=forbidden, create=True),
        ):
            response = client.post(
                "/api/v1/options/decision/evaluate",
                json={
                    "symbol": "TEM",
                    "strategy": "bull_call_spread",
                    "expiration": "2026-06-19",
                    "targetPrice": 65,
                    "targetDate": "2026-06-19",
                    "forceRefresh": True,
                },
            )

        assert response.status_code == 200
        text = _json_text(response.json()).lower()
        for value in SAFETY_BLOCKED_MARKERS + ["trade ticket"]:
            assert value not in text
    finally:
        client.close()


def test_decision_endpoint_live_provider_unavailable_fails_closed_without_secret_leakage() -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("forbidden runtime path was called")

    client = _client()
    try:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("data_provider.base.DataFetcherManager.get_realtime_quote", side_effect=forbidden),
            patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
            patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
            patch("src.services.portfolio_service.PortfolioService.add_lot", side_effect=forbidden, create=True),
        ):
            response = client.post(
                "/api/v1/options/decision/evaluate",
                json={
                    "symbol": "TEM",
                    "marketDataProvider": "tradier",
                    "strategy": "bull_call_spread",
                    "expiration": "2026-06-19",
                    "targetPrice": 65,
                    "targetDate": "2026-06-19",
                    "riskBudget": 600,
                },
            )

        assert response.status_code == 400
        payload = response.json()
        assert payload["detail"]["error"] == "options_provider_disabled"
        text = _json_text(payload).lower()
        assert "live confidence" not in text
        for value in ("api_key", "apikey", "token=", "secret", "requesturl", "traceback", "stack trace"):
            assert value not in text
    finally:
        client.close()


def test_decision_endpoint_tradier_live_provider_opt_in_uses_mocked_http_and_fails_authority_gate() -> None:
    credential = "synthetic_api_tradier_runtime_credential_1234567890"

    def forbidden(*_args, **_kwargs):
        raise AssertionError("forbidden mutation or analysis path was called")

    client = _client()
    try:
        with (
            patch.dict(os.environ, _tradier_runtime_env(credential), clear=True),
            patch(
                "requests.sessions.Session.request",
                side_effect=[
                    _MockTradierHttpResponse(_tradier_quote_payload()),
                    _MockTradierHttpResponse(_tradier_expirations_payload()),
                    _MockTradierHttpResponse(_tradier_chain_payload()),
                ],
            ) as request_mock,
            patch("data_provider.base.DataFetcherManager.get_realtime_quote", side_effect=forbidden),
            patch("src.services.market_cache.MarketCache.get_or_refresh", side_effect=forbidden),
            patch("src.analyzer.GeminiAnalyzer.analyze", side_effect=forbidden),
            patch("src.services.portfolio_service.PortfolioService.add_lot", side_effect=forbidden, create=True),
        ):
            response = client.post(
                "/api/v1/options/decision/evaluate",
                json={
                    "symbol": "TEM",
                    "marketDataProvider": "tradier",
                    "strategy": "long_call",
                    "expiration": "2026-06-19",
                    "targetPrice": 65,
                    "targetDate": "2026-06-19",
                    "riskBudget": 600,
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert request_mock.call_count == 3
        _assert_no_consumer_diagnostic_leaks(payload)
        assert "providerName" not in payload["metadata"]
        assert "providerCapabilities" not in payload["metadata"]
        assert payload["metadata"]["liveProviderEnabled"] is True
        assert payload["metadata"]["fixtureBacked"] is False
        assert payload["metadata"]["noExternalCalls"] is False
        assert payload["decisionGrade"] is False
        assert payload["decisionLabel"] == "数据不足，禁止判断"
        assert "failClosedReasonCodes" not in payload
        assert payload["consumerSafeSourceLabel"] == "部分数据源暂不可用"
        assert payload["evidenceGaps"] == ["evidence incomplete"]
        assert payload["researchNextSteps"]
        readiness = payload["optionsReadiness"]
        assert payload["optionsResearchReadiness"] == readiness
        assert readiness["optionsResearchReady"] is False
        assert readiness["readinessState"] == "blocked"
        assert readiness["dataQualityTier"] == "insufficient"
        assert "providerAuthority" not in readiness
        assert readiness["decisionGrade"] is False
        assert readiness["consumerSafeSourceLabel"] == "部分数据源暂不可用"
        assert readiness["evidenceGaps"] == ["evidence incomplete"]
        assert set(readiness["blockingReasons"]) == {"Evidence is limited for this observation."}
        assert readiness["nextEvidenceNeeded"] == ["Evidence is limited for this observation."]
        assert payload["metadata"]["readOnly"] is True
        assert payload["metadata"]["mode"] == "educational"
        assert payload["metadata"]["dataStatus"] == "unavailable"
        assert payload["metadata"]["label"] == "教学沙盒"
        assert payload["metadata"]["noAdvice"] is True
        assert payload["metadata"]["executionSupported"] is False
        assert payload["metadata"]["noOrderPlacement"] is True
        assert payload["metadata"]["noBrokerConnection"] is True
        assert payload["metadata"]["noPortfolioMutation"] is True
        assert payload["metadata"]["noTradingRecommendation"] is True
        assert all(item["decisionLabel"] != "有条件可交易" for item in payload["rankedAlternatives"])
        assert credential.lower() not in _json_text(payload).lower()
        _assert_no_safety_leaks(payload)
    finally:
        client.close()


def test_decision_endpoint_delayed_fixture_keeps_tradeability_cap() -> None:
    client = _client()
    try:
        response = client.post(
            "/api/v1/options/decision/evaluate",
            json={
                "symbol": "TEM",
                "marketDataProvider": "delayed_fixture",
                "strategy": "bull_call_spread",
                "expiration": "2026-06-19",
                "targetPrice": 65,
                "targetDate": "2026-06-19",
                "riskBudget": 600,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        _assert_no_consumer_diagnostic_leaks(payload)
        assert "providerName" not in payload["metadata"]
        assert "providerCapabilities" not in payload["metadata"]
        assert payload["dataQuality"]["dataQualityTier"] == "delayed_usable"
        assert payload["freshness"]["freshness"] == "delayed"
        assert payload["decisionLabel"] != "有条件可交易"
        assert payload["decisionGrade"] is False
        assert "failClosedReasonCodes" not in payload
        assert payload["consumerSafeSourceLabel"] == "部分数据源暂不可用"
        assert payload["evidenceGaps"] == ["evidence incomplete"]
        assert payload["staleInputs"] == ["freshness constrained"]
        assert payload["gateDecision"] in {"数据不足，禁止判断", "仅观察", "需人工复核"}
        assert payload["metadata"]["readOnly"] is True
        assert payload["metadata"]["noOrderPlacement"] is True
        assert payload["metadata"]["noBrokerConnection"] is True
        assert payload["metadata"]["noPortfolioMutation"] is True
        assert payload["metadata"]["noTradingRecommendation"] is True
        assert all(item["decisionLabel"] != "有条件可交易" for item in payload["rankedAlternatives"])
    finally:
        client.close()


def test_decision_endpoint_matches_service_alias_contract() -> None:
    request_payload = {
        "symbol": "TEM",
        "strategy": "bull_call_spread",
        "expiration": "2026-06-19",
        "targetPrice": 65,
        "targetDate": "2026-06-19",
        "riskBudget": 600,
    }

    client = _client()
    try:
        response = client.post("/api/v1/options/decision/evaluate", json=request_payload)
        assert response.status_code == 200

        expected_result = OptionsLabService(
            fixture_path=Path("tests/fixtures/options/tem_chain.json")
        ).evaluate_decision(request_payload)
        expected_payload = project_consumer_api_payload(
            options._map_decision_response(expected_result),
            surface="options-decision-evaluate",
        )
        actual_payload = response.json()

        assert actual_payload == expected_payload
        _assert_no_consumer_diagnostic_leaks(actual_payload)
        assert actual_payload["rankedAlternatives"] == actual_payload["optimizer"]["alternatives"]
    finally:
        client.close()


def test_decision_endpoint_no_trade_payload_matches_service_alias_contract(tmp_path: Path) -> None:
    fixture = json.loads(Path("tests/fixtures/options/tem_chain.json").read_text(encoding="utf-8"))
    for contract in fixture["contracts"]:
        contract["volume"] = 0
        contract["openInterest"] = 0
        contract["bid"] = 0.1
        contract["ask"] = 2.5
        contract["impliedVolatility"] = 1.4
    path = tmp_path / "tem_weak_candidates.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    weak_service = OptionsLabService(fixture_path=path)
    request_payload = {
        "symbol": "TEM",
        "strategy": "long_call",
        "expiration": "2026-06-19",
        "targetPrice": 52.5,
        "targetDate": "2026-06-19",
    }

    client = _client()
    try:
        with patch.object(options, "_service", return_value=weak_service):
            response = client.post("/api/v1/options/decision/evaluate", json=request_payload)

        assert response.status_code == 200
        expected_payload = options._map_decision_response(
            weak_service.evaluate_decision(request_payload)
        )
        expected_payload = project_consumer_api_payload(
            expected_payload,
            surface="options-decision-evaluate",
        )
        actual_payload = response.json()

        assert actual_payload == expected_payload
        _assert_no_consumer_diagnostic_leaks(actual_payload)
        assert {
            "preferredStrategyKey",
            "optimizerLabel",
            "alternatives",
            "noTradeReason",
        }.issubset(actual_payload["optimizer"])
        assert actual_payload["optimizer"]["preferredStrategyKey"] is None
        assert actual_payload["optimizer"]["noTradeReason"] is not None
        assert actual_payload["rankedAlternatives"] == actual_payload["optimizer"]["alternatives"]
    finally:
        client.close()


def test_decision_endpoint_mapper_preserves_existing_alias_shape() -> None:
    result = DecisionEvaluationResult(
        symbol="TEM",
        strategy="bull_call_spread",
        data_quality=DecisionDataQualityAssessment(
            data_quality_score=82.5,
            data_quality_tier="delayed_usable",
            source_type="delayed",
            as_of_age_minutes=18.5,
            blocking_reasons=["synthetic_or_fixture_data_not_decision_grade"],
            warnings=["missing_iv"],
        ),
        liquidity=LiquidityAssessment(
            liquidity_score=71.25,
            spread_pct=9.5,
            liquidity_warnings=["low_or_missing_volume"],
        ),
        iv_greeks=IvGreeksAssessment(
            iv_readiness=68.0,
            iv_rank_status="available",
            iv_rank=64.44,
            iv_percentile=71.43,
            iv_rank_source="synthetic_fixture_proxy",
            iv_rank_confidence="test_only_low_confidence",
            warnings=["missing_greeks"],
            dte_bucket="standard",
        ),
        expected_move=ExpectedMoveEstimate(
            expected_move_abs=7.5,
            expected_move_pct=14.31,
            expected_move_source="straddle_mid",
            expected_move_warnings=["expected_move_uses_fixture_mid_prices"],
        ),
        optimizer=OptimizerResult(
            preferred_strategy_key=None,
            optimizer_label="数据不足，禁止判断",
            alternatives=[
                OptimizerCandidate(
                    strategy_key="bull_call_spread",
                    data_quality_tier="delayed_usable",
                    liquidity_score=71.25,
                    breakeven_pressure=10.11,
                    max_loss=230,
                    max_gain=270,
                    risk_reward_ratio=1.17,
                    expected_move_alignment=58.0,
                    iv_readiness=68.0,
                    trade_quality_score=61.25,
                    decision_label="仅观察",
                    primary_reasons=["数据质量、流动性与风险回报需同时复核"],
                    risk_warnings=["expected_move_does_not_cover_breakeven_pressure"],
                )
            ],
            no_trade_reason="data_quality_not_decision_grade",
        ),
        breakeven=BreakevenAssessment(
            breakeven=57.7,
            required_move_pct=10.11,
            target_price_status="target_above_breakeven",
            score=74.0,
        ),
        risk_reward=RiskRewardAssessment(
            max_loss=230,
            max_gain=270,
            risk_reward_ratio=1.17,
            score=66.5,
            warnings=["max_gain_not_defined_for_long_option"],
        ),
        trade_quality_score=61.25,
        decision_label="仅观察",
        primary_reasons=["数据质量、流动性与风险回报需同时复核"],
        risk_warnings=["expected_move_does_not_cover_breakeven_pressure"],
        data_quality_gates={
            "status": "blocked",
            "issueCodes": ["synthetic_or_fixture_data_not_decision_grade"],
            "decisionGrade": False,
            "legDiagnostics": [],
        },
        liquidity_gates={
            "status": "manual_review",
            "issueCodes": ["low_or_missing_volume"],
            "decisionGrade": False,
            "legDiagnostics": [],
        },
        gate_decision="数据不足，禁止判断",
        gate_issues=[
            {
                "code": "synthetic_or_fixture_data_not_decision_grade",
                "category": "data_quality",
                "status": "blocked",
                "label": "Synthetic data is not decision grade",
                "decisionGrade": False,
                "legIndex": None,
                "contractSymbol": None,
            }
        ],
        decision_grade=False,
        fail_closed_reason_codes=["synthetic_or_fixture_data_not_decision_grade"],
        better_alternative=DecisionAlternativeModel(
            strategy_type="bull_call_spread",
            reason="定义风险结构或更低权利金暴露可能降低单合约风险",
            max_loss=230,
            risk_reward_ratio=1.17,
        ),
        no_advice_disclosure=(
            "Analytical output under explicit assumptions only; not personalized financial advice "
            "and not an instruction to trade."
        ),
        freshness=DecisionFreshnessModel(
            source="synthetic_fixture",
            freshness="synthetic_delayed",
            as_of="2026-05-06T16:00:00Z",
        ),
        metadata=OptionsLabMetadataModel(
            force_refresh_ignored=True,
            scoring_engine="options_decision_engine_r2",
            strategy_engine="options_decision_engine_r2",
            provider_name="synthetic_fixture",
            provider_capabilities={"liveEnabled": False},
            live_provider_enabled=False,
        ),
    )

    payload = options._map_decision_response(result).model_dump(by_alias=True)

    assert payload["dataQuality"] == {
        "dataQualityScore": 82.5,
        "dataQualityTier": "delayed_usable",
        "sourceType": "delayed",
        "asOfAgeMinutes": 18.5,
        "blockingReasons": ["synthetic_or_fixture_data_not_decision_grade"],
        "warnings": ["missing_iv"],
    }
    assert payload["liquidity"] == {
        "liquidityScore": 71.25,
        "spreadPct": 9.5,
        "liquidityWarnings": ["low_or_missing_volume"],
    }
    assert payload["ivGreeks"] == {
        "ivReadiness": 68.0,
        "ivRankStatus": "available",
        "ivRank": 64.44,
        "ivPercentile": 71.43,
        "ivRankSource": "synthetic_fixture_proxy",
        "ivRankConfidence": "test_only_low_confidence",
        "warnings": ["missing_greeks"],
        "dteBucket": "standard",
    }
    assert payload["breakeven"] == {
        "breakeven": 57.7,
        "requiredMovePct": 10.11,
        "targetPriceStatus": "target_above_breakeven",
        "score": 74.0,
    }
    assert payload["riskReward"] == {
        "maxLoss": 230.0,
        "maxGain": 270.0,
        "riskRewardRatio": 1.17,
        "score": 66.5,
        "warnings": ["max_gain_not_defined_for_long_option"],
    }
    assert payload["expectedMove"] == {
        "expectedMoveAbs": 7.5,
        "expectedMovePct": 14.31,
        "expectedMoveSource": "straddle_mid",
        "expectedMoveWarnings": ["expected_move_uses_fixture_mid_prices"],
    }
    assert payload["betterAlternative"] == {
        "strategyType": "bull_call_spread",
        "reason": "定义风险结构或更低权利金暴露可能降低单合约风险",
        "maxLoss": 230.0,
        "riskRewardRatio": 1.17,
    }
    assert payload["optionsReadiness"] == payload["optionsResearchReadiness"]
    assert payload["optionsReadiness"] == {
        "optionsResearchReady": False,
        "readinessState": "blocked",
        "dataQualityTier": "delayed_usable",
        "decisionGrade": False,
        "providerAuthority": "observationOnly",
        "liquidityGate": "manual_review",
        "ivGreeksGate": "blocked",
        "spreadGate": "clear",
        "scenarioCoverage": "strategy_compare_ready",
        "noTradingBoundary": {
            "analyticalOnly": True,
            "noBrokerExecution": True,
            "noOrderPlacement": True,
            "noPortfolioMutation": True,
            "noTradingRecommendation": True,
        },
        "blockingReasons": [
            "provider_fixture_not_decision_grade",
            "provider_live_disabled",
            "provider_tradeable_data_false",
            "provider_authority_tier_observation_only",
            "synthetic_or_fixture_data_not_decision_grade",
            "missing_iv",
            "missing_greeks",
            "low_or_missing_volume",
        ],
        "nextEvidenceNeeded": [
            "补充 provider authority 与 live chain 证据",
            "补充 Greeks 与 IV 证据",
            "补充 OI/成交量与更紧价差证据",
        ],
    }
    frame = payload["optionsConsumerScenarioFrame"]
    _assert_consumer_scenario_frame_contract(frame)
    assert frame["frameState"] == "blocked"
    assert frame["underlying"] == {"symbol": "TEM"}
    assert frame["strategyType"] == "bull_call_spread"
    assert frame["expiration"] is None
    assert frame["scenarioCoverage"] == "strategy_compare_ready"
    assert frame["chainQuality"] == {
        "hasChain": True,
        "contractCount": 1,
        "callCount": 0,
        "putCount": 0,
        "freshness": "synthetic_delayed",
        "sourceType": "synthetic_fixture",
        "coverageState": "strategy_compare_ready",
    }
    assert frame["liquidityGate"] == "manual_review"
    assert frame["ivGreeksGate"] == "blocked"
    assert frame["spreadGate"] == "clear"
    assert frame["payoffEvidence"] == {
        "targetPrice": None,
        "payoffAtTarget": None,
        "expectedMoveAbs": 7.5,
        "expectedMovePct": 14.31,
        "expectedMoveSource": "straddle_mid",
    }
    assert frame["riskEvidence"] == {
        "premiumAtRisk": None,
        "maxLoss": 230.0,
        "maxGain": 270.0,
        "breakeven": 57.7,
        "requiredMovePct": 10.11,
    }
    assert frame["assumptions"] == {
        "inputMode": "decision",
        "decisionLabel": "仅观察",
        "targetPriceStatus": "target_above_breakeven",
        "optimizerLabel": "数据不足，禁止判断",
    }
    assert frame["missingEvidence"] == ["provider authority", "live chain", "iv greeks", "volume"]
    assert frame["blockingReasons"] == payload["optionsReadiness"]["blockingReasons"]
    assert frame["nextEvidenceNeeded"] == payload["optionsReadiness"]["nextEvidenceNeeded"]
    assert payload["optimizer"] == {
        "preferredStrategyKey": None,
        "optimizerLabel": "数据不足，禁止判断",
        "alternatives": [
            {
                "strategyKey": "bull_call_spread",
                "dataQualityTier": "delayed_usable",
                "liquidityScore": 71.25,
                "breakevenPressure": 10.11,
                "maxLoss": 230.0,
                "maxGain": 270.0,
                "riskRewardRatio": 1.17,
                "expectedMoveAlignment": 58.0,
                "ivReadiness": 68.0,
                "tradeQualityScore": 61.25,
                "decisionLabel": "仅观察",
                "primaryReasons": ["数据质量、流动性与风险回报需同时复核"],
                "riskWarnings": ["expected_move_does_not_cover_breakeven_pressure"],
            }
        ],
        "noTradeReason": "data_quality_not_decision_grade",
    }
    assert payload["rankedAlternatives"] == payload["optimizer"]["alternatives"]


def test_decision_endpoint_options_readiness_detects_missing_chain_fields_and_wide_spread() -> None:
    result = DecisionEvaluationResult(
        symbol="TEM",
        strategy="long_call",
        data_quality=DecisionDataQualityAssessment(
            data_quality_score=34.0,
            data_quality_tier="insufficient",
            source_type="delayed",
            as_of_age_minutes=12.0,
            blocking_reasons=["missing_bid_ask", "missing_contract_legs"],
            warnings=["missing_iv", "missing_greeks", "missing_volume", "missing_open_interest"],
        ),
        liquidity=LiquidityAssessment(
            liquidity_score=28.0,
            spread_pct=41.2,
            liquidity_warnings=["wide_bid_ask_spread", "low_or_missing_volume", "low_or_missing_open_interest"],
        ),
        iv_greeks=IvGreeksAssessment(
            iv_readiness=24.0,
            iv_rank_status="unavailable",
            iv_rank=None,
            iv_percentile=None,
            iv_rank_source=None,
            iv_rank_confidence=None,
            warnings=["missing_iv", "missing_greeks"],
            dte_bucket="short",
        ),
        expected_move=ExpectedMoveEstimate(
            expected_move_abs=None,
            expected_move_pct=None,
            expected_move_source="unavailable",
            expected_move_warnings=["expected_move_unavailable"],
        ),
        optimizer=OptimizerResult(
            preferred_strategy_key=None,
            optimizer_label="数据不足，禁止判断",
            alternatives=[],
            no_trade_reason="data_quality_not_decision_grade",
        ),
        breakeven=BreakevenAssessment(
            breakeven=None,
            required_move_pct=None,
            target_price_status="not_supplied",
            score=20.0,
        ),
        risk_reward=RiskRewardAssessment(
            max_loss=None,
            max_gain=None,
            risk_reward_ratio=None,
            score=18.0,
            warnings=[],
        ),
        trade_quality_score=18.0,
        decision_label="数据不足，禁止判断",
        primary_reasons=["missing_contract_legs"],
        risk_warnings=["wide_bid_ask_spread"],
        data_quality_gates={
            "status": "blocked",
            "issueCodes": ["missing_bid_ask", "missing_contract_legs"],
            "decisionGrade": False,
            "legDiagnostics": [],
        },
        liquidity_gates={
            "status": "blocked",
            "issueCodes": ["wide_bid_ask_spread", "low_or_missing_volume", "low_or_missing_open_interest"],
            "decisionGrade": False,
            "legDiagnostics": [],
        },
        gate_decision="数据不足，禁止判断",
        gate_issues=[
            {
                "code": "missing_bid_ask",
                "category": "data_quality",
                "status": "blocked",
                "label": "Missing bid ask",
                "decisionGrade": False,
                "legIndex": None,
                "contractSymbol": None,
            }
        ],
        decision_grade=False,
        fail_closed_reason_codes=["missing_bid_ask", "missing_contract_legs"],
        better_alternative=None,
        no_advice_disclosure=(
            "Analytical output under explicit assumptions only; not personalized financial advice "
            "and not an instruction to trade."
        ),
        freshness=DecisionFreshnessModel(
            source="delayed_feed",
            freshness="delayed",
            as_of="2026-05-06T16:00:00Z",
        ),
        metadata=OptionsLabMetadataModel(
            fixture_backed=False,
            synthetic_data=False,
            no_external_calls=False,
            provider_name="delayed_authorized_feed",
            provider_capabilities={
                "liveEnabled": True,
                "tradeableData": True,
                "authorityPolicySource": "wolfystock_options_provider_authority_policy_v1",
                "authorityTier": "decision_grade",
                "sourceType": "authorized_licensed_feed",
            },
            live_provider_enabled=True,
        ),
    )

    payload = options._map_decision_response(result).model_dump(by_alias=True)
    readiness = payload["optionsReadiness"]
    assert readiness["optionsResearchReady"] is False
    assert readiness["readinessState"] == "blocked"
    assert readiness["dataQualityTier"] == "insufficient"
    assert readiness["providerAuthority"] == "scoreGradeAllowed"
    assert readiness["liquidityGate"] == "blocked"
    assert readiness["ivGreeksGate"] == "blocked"
    assert readiness["spreadGate"] == "blocked"
    assert readiness["scenarioCoverage"] == "missing_chain_data"
    assert "missing_bid_ask" in readiness["blockingReasons"]
    assert "missing_contract_legs" in readiness["blockingReasons"]
    assert "wide_bid_ask_spread" in readiness["blockingReasons"]
    assert "missing_iv" in readiness["blockingReasons"]
    assert "missing_greeks" in readiness["blockingReasons"]
    assert "missing_volume" in readiness["blockingReasons"]
    assert "missing_open_interest" in readiness["blockingReasons"]
    assert readiness["nextEvidenceNeeded"] == [
        "补充完整期权链路与 bid/ask",
        "补充 Greeks 与 IV 证据",
        "补充 OI/成交量与更紧价差证据",
    ]
    frame = payload["optionsConsumerScenarioFrame"]
    _assert_consumer_scenario_frame_contract(frame)
    assert frame["frameState"] == "blocked"
    assert frame["scenarioCoverage"] == "missing_chain_data"
    assert frame["liquidityGate"] == "blocked"
    assert frame["ivGreeksGate"] == "blocked"
    assert frame["spreadGate"] == "blocked"
    assert frame["payoffEvidence"]["expectedMoveSource"] == "unavailable"
    assert frame["riskEvidence"]["breakeven"] is None
    assert frame["missingEvidence"] == ["bid ask", "iv greeks", "volume", "open interest"]
    assert frame["blockingReasons"] == readiness["blockingReasons"]


def test_decision_endpoint_options_readiness_distinguishes_delayed_and_live_usable_states() -> None:
    delayed_result = DecisionEvaluationResult(
        symbol="TEM",
        strategy="long_call",
        data_quality=DecisionDataQualityAssessment(
            data_quality_score=78.0,
            data_quality_tier="delayed_usable",
            source_type="delayed",
            as_of_age_minutes=15.0,
            blocking_reasons=[],
            warnings=[],
        ),
        liquidity=LiquidityAssessment(liquidity_score=81.0, spread_pct=7.5, liquidity_warnings=[]),
        iv_greeks=IvGreeksAssessment(
            iv_readiness=76.0,
            iv_rank_status="available",
            iv_rank=58.0,
            iv_percentile=62.0,
            iv_rank_source="licensed_delayed_iv",
            iv_rank_confidence="medium",
            warnings=[],
            dte_bucket="standard",
        ),
        expected_move=ExpectedMoveEstimate(
            expected_move_abs=5.5,
            expected_move_pct=10.2,
            expected_move_source="iv_dte",
            expected_move_warnings=[],
        ),
        optimizer=OptimizerResult(
            preferred_strategy_key=None,
            optimizer_label="仅观察",
            alternatives=[],
            no_trade_reason="delayed_evidence_manual_review",
        ),
        breakeven=BreakevenAssessment(
            breakeven=57.0,
            required_move_pct=8.3,
            target_price_status="target_above_breakeven",
            score=77.0,
        ),
        risk_reward=RiskRewardAssessment(
            max_loss=180.0,
            max_gain=None,
            risk_reward_ratio=None,
            score=55.0,
            warnings=[],
        ),
        trade_quality_score=59.0,
        decision_label="仅观察",
        primary_reasons=["delayed chain usable with manual review"],
        risk_warnings=[],
        data_quality_gates={
            "status": "manual_review",
            "issueCodes": [],
            "decisionGrade": False,
            "legDiagnostics": [
                {
                    "legIndex": 0,
                    "contractSymbol": "TEM260619C00050000",
                    "dataQualityStatus": "manual_review",
                    "liquidityStatus": "clear",
                    "issueCodes": [],
                    "decisionGrade": False,
                }
            ],
        },
        liquidity_gates={
            "status": "clear",
            "issueCodes": [],
            "decisionGrade": True,
            "legDiagnostics": [
                {
                    "legIndex": 0,
                    "contractSymbol": "TEM260619C00050000",
                    "dataQualityStatus": "manual_review",
                    "liquidityStatus": "clear",
                    "issueCodes": [],
                    "decisionGrade": False,
                }
            ],
        },
        gate_decision="仅观察",
        gate_issues=[],
        decision_grade=False,
        fail_closed_reason_codes=[],
        better_alternative=None,
        no_advice_disclosure=(
            "Analytical output under explicit assumptions only; not personalized financial advice "
            "and not an instruction to trade."
        ),
        freshness=DecisionFreshnessModel(
            source="licensed_delayed_feed",
            freshness="delayed",
            as_of="2026-05-06T16:00:00Z",
        ),
        metadata=OptionsLabMetadataModel(
            fixture_backed=False,
            synthetic_data=False,
            no_external_calls=False,
            provider_name="licensed_delayed_feed",
            provider_capabilities={
                "liveEnabled": True,
                "tradeableData": True,
                "authorityPolicySource": "wolfystock_options_provider_authority_policy_v1",
                "authorityTier": "decision_grade",
                "sourceType": "authorized_licensed_feed",
            },
            live_provider_enabled=True,
        ),
    )
    live_result = DecisionEvaluationResult(
        symbol="TEM",
        strategy=delayed_result.strategy,
        data_quality=DecisionDataQualityAssessment(
            data_quality_score=92.0,
            data_quality_tier="live_usable",
            source_type="live",
            as_of_age_minutes=1.0,
            blocking_reasons=[],
            warnings=[],
        ),
        liquidity=delayed_result.liquidity,
        iv_greeks=IvGreeksAssessment(
            iv_readiness=82.0,
            iv_rank_status="available",
            iv_rank=61.0,
            iv_percentile=66.0,
            iv_rank_source="licensed_live_iv",
            iv_rank_confidence="high",
            warnings=[],
            dte_bucket="standard",
        ),
        expected_move=delayed_result.expected_move,
        optimizer=OptimizerResult(
            preferred_strategy_key=None,
            optimizer_label="仅观察",
            alternatives=[],
            no_trade_reason="research_only_boundary",
        ),
        breakeven=delayed_result.breakeven,
        risk_reward=delayed_result.risk_reward,
        trade_quality_score=72.0,
        decision_label="仅观察",
        primary_reasons=list(delayed_result.primary_reasons),
        risk_warnings=[],
        data_quality_gates={
            "status": "clear",
            "issueCodes": [],
            "decisionGrade": True,
            "legDiagnostics": [
                {
                    "legIndex": 0,
                    "contractSymbol": "TEM260619C00050000",
                    "dataQualityStatus": "clear",
                    "liquidityStatus": "clear",
                    "issueCodes": [],
                    "decisionGrade": True,
                }
            ],
        },
        liquidity_gates=delayed_result.liquidity_gates,
        gate_decision="仅观察",
        gate_issues=[],
        decision_grade=True,
        fail_closed_reason_codes=[],
        better_alternative=None,
        no_advice_disclosure=delayed_result.no_advice_disclosure,
        freshness=DecisionFreshnessModel(
            source="authorized_live_feed",
            freshness="fresh",
            as_of="2026-05-06T16:14:00Z",
        ),
        metadata=OptionsLabMetadataModel(
            fixture_backed=False,
            synthetic_data=False,
            no_external_calls=False,
            provider_name="authorized_live_feed",
            provider_capabilities={
                "liveEnabled": True,
                "tradeableData": True,
                "authorityPolicySource": "wolfystock_options_provider_authority_policy_v1",
                "authorityTier": "decision_grade",
                "sourceType": "authorized_licensed_feed",
            },
            live_provider_enabled=True,
        ),
    )

    delayed_payload = options._map_decision_response(delayed_result).model_dump(by_alias=True)
    live_payload = options._map_decision_response(live_result).model_dump(by_alias=True)
    delayed_readiness = delayed_payload["optionsReadiness"]
    live_readiness = live_payload["optionsReadiness"]

    assert delayed_payload["metadata"]["mode"] == "educational"
    assert delayed_payload["metadata"]["dataStatus"] == "ready"
    assert delayed_payload["metadata"]["label"] == "教学沙盒"
    assert delayed_payload["metadata"]["noAdvice"] is True
    assert delayed_payload["metadata"]["executionSupported"] is False

    assert live_payload["metadata"]["mode"] == "educational"
    assert live_payload["metadata"]["dataStatus"] == "ready"
    assert live_payload["metadata"]["label"] == "教学沙盒"
    assert live_payload["metadata"]["noAdvice"] is True
    assert live_payload["metadata"]["executionSupported"] is False

    assert delayed_readiness["optionsResearchReady"] is True
    assert delayed_readiness["readinessState"] == "delayed_usable"
    assert delayed_readiness["dataQualityTier"] == "delayed_usable"
    assert delayed_readiness["providerAuthority"] == "scoreGradeAllowed"
    assert delayed_readiness["liquidityGate"] == "clear"
    assert delayed_readiness["ivGreeksGate"] == "manual_review"
    assert delayed_readiness["spreadGate"] == "clear"
    assert delayed_readiness["scenarioCoverage"] == "single_contract"
    assert delayed_readiness["blockingReasons"] == []
    assert delayed_readiness["nextEvidenceNeeded"] == ["等待更高新鲜度链路"]

    assert live_readiness["optionsResearchReady"] is True
    assert live_readiness["readinessState"] == "live_usable"
    assert live_readiness["dataQualityTier"] == "live_usable"
    assert live_readiness["providerAuthority"] == "scoreGradeAllowed"
    assert live_readiness["liquidityGate"] == "clear"
    assert live_readiness["ivGreeksGate"] == "clear"
    assert live_readiness["spreadGate"] == "clear"
    assert live_readiness["scenarioCoverage"] == "single_contract"
    assert live_readiness["blockingReasons"] == []
    assert live_readiness["nextEvidenceNeeded"] == []
    delayed_frame = delayed_payload["optionsConsumerScenarioFrame"]
    live_frame = live_payload["optionsConsumerScenarioFrame"]
    _assert_consumer_scenario_frame_contract(delayed_frame)
    _assert_consumer_scenario_frame_contract(live_frame)
    assert delayed_frame["frameState"] == "observe_only"
    assert live_frame["frameState"] == "ready"
    assert delayed_frame["missingEvidence"] == ["freshness"]
    assert live_frame["missingEvidence"] == []
    assert delayed_frame["nextEvidenceNeeded"] == ["等待更高新鲜度链路"]
    assert live_frame["nextEvidenceNeeded"] == []


def test_options_launch_source_does_not_import_broker_order_or_portfolio_mutation_paths() -> None:
    source_paths = [
        "api/v1/endpoints/options.py",
        "src/services/options_lab_service.py",
        "src/services/options_market_data_provider.py",
    ]
    forbidden_imports = [
        "from src.services.portfolio_service",
        "import portfolio_service",
        "from src.services.broker",
        "import broker",
        "from src.services.order",
        "import order_service",
    ]
    forbidden_calls = [
        ".add_lot(",
        ".place_order(",
        ".submit_order(",
        ".create_order(",
        ".execute_order(",
        ".mutate_portfolio(",
        ".create_broker_connection(",
        ".update_broker_connection(",
        ".mark_broker_connection_imported(",
        ".mark_broker_connection_synced(",
        ".replace_broker_sync_state(",
        ".sync_broker(",
    ]

    for path in source_paths:
        source = Path(path).read_text(encoding="utf-8")
        for marker in forbidden_imports + forbidden_calls:
            assert marker not in source
