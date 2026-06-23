# -*- coding: utf-8 -*-
"""Provider-neutral options structure contract tests."""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import options
from api.v1.schemas.options import OptionChainSnapshot, OptionContractStructureRow
from src.services.options_structure_service import (
    OptionsStructureService,
    aggregate_options_structure_snapshot,
)


FORBIDDEN_PUBLIC_MARKERS = (
    "rawPayload",
    "raw_provider_payload",
    "credential",
    "api_key",
    "apikey",
    "token",
    "secret",
    "env",
    "requestId",
    "request_id",
    "traceId",
    "cacheKey",
    "cache_key",
    "provider.example",
    "OPTIONS_LIVE",
    "TRADIER_API",
)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(options.router, prefix="/api/v1/options")
    return TestClient(app)


def _json_text(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _assert_no_public_leaks(payload: object) -> None:
    text = _json_text(payload)
    lowered = text.lower()
    for marker in FORBIDDEN_PUBLIC_MARKERS:
        assert marker not in text
        if marker.islower():
            assert marker not in lowered


def _complete_snapshot() -> OptionChainSnapshot:
    return OptionChainSnapshot(
        symbol="TEM",
        spotPrice=50.0,
        asOf="2026-06-19T14:30:00Z",
        freshness="fresh",
        contracts=[
            OptionContractStructureRow(
                contractSymbol="TEM260619C00050000",
                side="call",
                expiration="2026-06-19",
                strike=50.0,
                multiplier=100,
                openInterest=10,
                volume=4,
                impliedVolatility=0.45,
                delta=0.52,
                gamma=0.02,
                vega=0.11,
                theta=-0.04,
                charm=-0.01,
                vanna=0.03,
                asOf="2026-06-19T14:30:00Z",
                freshness="fresh",
            ),
            OptionContractStructureRow(
                contractSymbol="TEM260619P00050000",
                side="put",
                expiration="2026-06-19",
                strike=50.0,
                multiplier=100,
                openInterest=5,
                volume=3,
                impliedVolatility=0.47,
                delta=-0.48,
                gamma=0.03,
                vega=0.10,
                theta=-0.05,
                charm=0.02,
                vanna=-0.02,
                asOf="2026-06-19T14:30:00Z",
                freshness="fresh",
            ),
            OptionContractStructureRow(
                contractSymbol="TEM260620C00055000",
                side="call",
                expiration="2026-06-20",
                strike=55.0,
                multiplier=100,
                openInterest=8,
                volume=2,
                impliedVolatility=0.5,
                delta=0.31,
                gamma=0.01,
                vega=0.12,
                theta=-0.03,
                asOf="2026-06-19T14:30:00Z",
                freshness="fresh",
            ),
        ],
    )


def test_option_structure_snapshot_schema_serializes_provider_neutral_fields() -> None:
    payload = _complete_snapshot().model_dump(by_alias=True)

    assert payload["contractVersion"] == "option-chain-snapshot-v1"
    assert payload["symbol"] == "TEM"
    assert payload["spotPrice"] == 50.0
    first_contract = payload["contracts"][0]
    assert first_contract["contractSymbol"] == "TEM260619C00050000"
    assert first_contract["openInterest"] == 10
    assert first_contract["impliedVolatility"] == 0.45
    assert first_contract["charm"] == -0.01
    assert first_contract["vanna"] == 0.03
    assert first_contract["dealerGammaExposure"] is None
    _assert_no_public_leaks(payload)


def test_aggregation_helper_handles_complete_data() -> None:
    summary = aggregate_options_structure_snapshot(_complete_snapshot())
    payload = summary.model_dump(by_alias=True)

    assert payload["status"] == "available"
    assert payload["calculationState"] == "available"
    assert payload["totalDealerGammaExposure"] == 325.0
    assert payload["gammaFlipLevel"]["state"] == "not_available"
    strike_50 = next(item for item in payload["strikeSummaries"] if item["strike"] == 50.0)
    assert strike_50["callOpenInterest"] == 10
    assert strike_50["putOpenInterest"] == 5
    assert strike_50["callVolume"] == 4
    assert strike_50["putVolume"] == 3
    assert strike_50["callDealerGammaExposure"] == 500.0
    assert strike_50["putDealerGammaExposure"] == -375.0
    assert strike_50["netDealerGammaExposure"] == 125.0
    assert payload["nearestExpirations"][0]["expiration"] == "2026-06-19"
    assert payload["zeroDte"]["state"] == "available"
    assert payload["zeroDte"]["expiration"] == "2026-06-19"


def test_aggregation_helper_degrades_when_greeks_or_oi_are_missing() -> None:
    snapshot = OptionChainSnapshot(
        symbol="TEM",
        spotPrice=50.0,
        asOf="2026-06-19T14:30:00Z",
        freshness="fresh",
        contracts=[
            OptionContractStructureRow(
                contractSymbol="TEM260619C00050000",
                side="call",
                expiration="2026-06-19",
                strike=50.0,
                multiplier=100,
                openInterest=None,
                volume=4,
                gamma=0.02,
            ),
            OptionContractStructureRow(
                contractSymbol="TEM260619P00050000",
                side="put",
                expiration="2026-06-19",
                strike=50.0,
                multiplier=100,
                openInterest=5,
                volume=3,
                gamma=None,
            ),
        ],
    )

    payload = aggregate_options_structure_snapshot(snapshot).model_dump(by_alias=True)

    assert payload["status"] == "degraded"
    assert payload["calculationState"] == "not_available"
    assert payload["totalDealerGammaExposure"] is None
    assert "missing_open_interest" in payload["blockingReasons"]
    assert "missing_gamma" in payload["blockingReasons"]
    strike = payload["strikeSummaries"][0]
    assert strike["callOpenInterest"] == 0
    assert strike["putOpenInterest"] == 5
    assert strike["netDealerGammaExposure"] is None


def test_zero_dte_bucket_detection_uses_snapshot_date_and_expiration_dates() -> None:
    payload = aggregate_options_structure_snapshot(_complete_snapshot()).model_dump(by_alias=True)

    zero_dte = payload["zeroDte"]
    assert zero_dte["state"] == "available"
    assert zero_dte["dte"] == 0
    assert zero_dte["callOpenInterest"] == 10
    assert zero_dte["putOpenInterest"] == 5
    assert zero_dte["callVolume"] == 4
    assert zero_dte["putVolume"] == 3


def test_not_available_service_response_is_consumer_safe() -> None:
    payload = OptionsStructureService().get_structure("AAPL").model_dump(by_alias=True)

    assert payload["status"] == "not_available"
    assert payload["providerConfigured"] is False
    assert payload["decisionGrade"] is False
    assert payload["observationOnly"] is True
    assert payload["snapshot"]["contracts"] == []
    assert payload["strikeSummaries"] == []
    assert payload["expirationSummaries"] == []
    assert "options_structure_provider_missing" in payload["blockingReasons"]
    _assert_no_public_leaks(payload)


def test_options_structure_api_returns_not_available_contract_without_leaks() -> None:
    response = _client().get("/api/v1/options/underlyings/AAPL/structure")
    assert response.status_code == 200

    payload = response.json()
    assert payload["contractVersion"] == "options-structure-summary-v1"
    assert payload["symbol"] == "AAPL"
    assert payload["status"] == "not_available"
    assert payload["providerConfigured"] is False
    assert payload["snapshot"]["contracts"] == []
    _assert_no_public_leaks(payload)
