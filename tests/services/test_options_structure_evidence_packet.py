# -*- coding: utf-8 -*-
"""Options structure evidence packet service tests."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from src.services.options_structure_evidence_packet import (
    build_options_structure_evidence_packet,
)


FORBIDDEN_VOCABULARY = (
    "buy",
    "sell",
    "hold",
    "recommend",
    "target price",
    "stop loss",
    "position sizing",
    "best contract",
    "guaranteed",
    "trade instruction",
    "dealer book",
    "true gex",
)


def _complete_packet() -> dict:
    return {
        "symbol": "SPY",
        "asOf": "2026-06-17T14:30:00Z",
        "spot": 540.0,
        "contracts": [
            {
                "contractSymbol": "SPY260619C00540000",
                "side": "call",
                "expiration": "2026-06-19",
                "strike": 540.0,
                "openInterest": 1_200,
                "volume": 450,
                "impliedVolatility": 0.22,
                "greeks": {"gamma": 0.012},
                "multiplier": 100,
                "asOf": "2026-06-17T14:30:00Z",
                "freshness": "fresh",
            },
            {
                "contractSymbol": "SPY260619P00535000",
                "side": "put",
                "expiration": "2026-06-19",
                "strike": 535.0,
                "openInterest": 2_400,
                "volume": 700,
                "impliedVolatility": 0.28,
                "gamma": 0.01,
                "multiplier": 100,
                "asOf": "2026-06-17T14:30:00Z",
                "freshness": "fresh",
            },
            {
                "contractSymbol": "SPY260626C00545000",
                "side": "call",
                "expiration": "2026-06-26",
                "strike": 545.0,
                "openInterest": 600,
                "volume": 150,
                "impliedVolatility": 0.2,
                "greeks": {"gamma": 0.006},
                "multiplier": 100,
                "asOf": "2026-06-17T14:30:00Z",
                "freshness": "fresh",
            },
            {
                "contractSymbol": "SPY260626P00530000",
                "side": "put",
                "expiration": "2026-06-26",
                "strike": 530.0,
                "openInterest": 800,
                "volume": 170,
                "impliedVolatility": 0.31,
                "greeks": {"gamma": 0.008},
                "multiplier": 100,
                "asOf": "2026-06-17T14:30:00Z",
                "freshness": "fresh",
            },
        ],
    }


def test_complete_input_produces_bounded_options_structure_evidence() -> None:
    packet = build_options_structure_evidence_packet(_complete_packet())

    assert packet["contractVersion"] == "options-structure-evidence-packet-v1"
    assert packet["symbol"] == "SPY"
    assert packet["asOf"] == "2026-06-17T14:30:00Z"
    assert packet["structureState"] == "skewed"
    assert set(packet) == {
        "contractVersion",
        "symbol",
        "asOf",
        "structureState",
        "expiryConcentrationEvidence",
        "openInterestEvidence",
        "putCallSkewEvidence",
        "gammaRiskEvidence",
        "staleInputs",
        "missingInputs",
        "confidenceCap",
        "observationBoundary",
        "researchNextSteps",
        "noAdviceDisclosure",
    }

    assert packet["expiryConcentrationEvidence"]["state"] == "concentrated"
    assert packet["expiryConcentrationEvidence"]["dominantExpiry"] == "2026-06-19"
    assert packet["expiryConcentrationEvidence"]["dominantOpenInterestShare"] == pytest.approx(0.72)
    assert packet["openInterestEvidence"]["totalOpenInterest"] == 5_000.0
    assert packet["openInterestEvidence"]["topStrikeOpenInterestShare"] == pytest.approx(0.48)
    assert packet["putCallSkewEvidence"]["state"] == "skewed"
    assert packet["putCallSkewEvidence"]["putCallOpenInterestRatio"] == pytest.approx(1.7778)
    assert packet["gammaRiskEvidence"]["state"] == "observed"
    assert packet["gammaRiskEvidence"]["gammaInputsPresent"] is True
    assert packet["gammaRiskEvidence"]["proxyOnly"] is True
    assert packet["gammaRiskEvidence"]["largestStrike"] == 535.0
    assert "gex" not in json.dumps(packet["gammaRiskEvidence"], ensure_ascii=False).lower()
    assert packet["missingInputs"] == []
    assert packet["staleInputs"] == []
    assert packet["confidenceCap"]["level"] == "medium"
    assert packet["observationBoundary"] == {
        "observationOnly": True,
        "decisionGrade": False,
        "noProviderCalls": True,
        "noStorageMutation": True,
        "endpointAttached": False,
    }


def test_missing_gamma_or_greeks_does_not_fabricate_gex() -> None:
    input_packet = _complete_packet()
    for contract in input_packet["contracts"]:
        contract.pop("gamma", None)
        contract.pop("greeks", None)

    packet = build_options_structure_evidence_packet(input_packet)

    assert packet["gammaRiskEvidence"] == {
        "state": "insufficient_evidence",
        "gammaInputsPresent": False,
        "proxyOnly": True,
        "message": (
            "Gamma or greeks input is unavailable, so gamma-risk evidence is not calculated."
        ),
        "largestStrike": None,
        "netSignedGammaProxy": None,
        "grossGammaProxy": None,
    }
    assert {"field": "gammaOrGreeks", "label": "Gamma or greeks input is unavailable."} in packet[
        "missingInputs"
    ]
    assert packet["confidenceCap"]["level"] == "low"
    assert "gex" not in json.dumps(packet, ensure_ascii=False).lower()


def test_concentrated_expiry_and_open_interest_state_is_observation_only() -> None:
    packet = build_options_structure_evidence_packet(_complete_packet())

    assert packet["structureState"] == "skewed"
    assert packet["expiryConcentrationEvidence"]["state"] == "concentrated"
    assert packet["openInterestEvidence"]["state"] == "concentrated"
    assert packet["observationBoundary"]["observationOnly"] is True
    assert packet["observationBoundary"]["decisionGrade"] is False
    assert packet["researchNextSteps"] == [
        "Compare expiry and open-interest concentration across verified snapshots.",
        "Add verified greeks before interpreting gamma-risk evidence.",
        "Review stale or missing inputs before downstream research use.",
    ]


def test_stale_inputs_lower_confidence_and_appear_in_stale_inputs() -> None:
    input_packet = _complete_packet()
    input_packet["contracts"][0]["freshness"] = "stale"
    input_packet["contracts"][0]["asOf"] = "2026-06-12T14:30:00Z"

    packet = build_options_structure_evidence_packet(input_packet)

    assert packet["staleInputs"] == [
        {
            "field": "contractFreshness",
            "label": "A contract row is marked stale.",
            "contractSymbol": "SPY260619C00540000",
        }
    ]
    assert packet["confidenceCap"]["level"] == "low"
    assert "stale input" in packet["confidenceCap"]["reason"].lower()


def test_malformed_raw_provider_debug_request_and_trace_input_is_dropped() -> None:
    input_packet = _complete_packet()
    input_packet.update(
        {
            "rawPayload": {"provider": "secret_vendor", "debug": "trace-id-123"},
            "providerDiagnostics": "provider_route=internal",
            "request": {"headers": {"authorization": "Bearer should-not-render"}},
            "trace": "trace-abc",
            "debug": True,
        }
    )
    input_packet["contracts"].append(
        {
            "contractSymbol": "BROKEN",
            "side": "call",
            "expiration": "2026-06-19",
            "strike": "not-a-number",
            "openInterest": "not-a-number",
            "greeks": {"gamma": "not-a-number"},
            "rawPayload": "leak",
            "providerTrace": "leak",
        }
    )

    packet = build_options_structure_evidence_packet(input_packet)
    serialized = json.dumps(packet, ensure_ascii=False).lower()

    for forbidden in (
        "secret_vendor",
        "provider_route",
        "authorization",
        "bearer",
        "trace-id",
        "trace-abc",
        "rawpayload",
        "providerdiagnostics",
        "providertrace",
        "debug",
        "request",
    ):
        assert forbidden not in serialized
    assert packet["openInterestEvidence"]["contractCount"] == 4


def test_no_advice_vocabulary_in_serialized_output() -> None:
    packet = build_options_structure_evidence_packet(_complete_packet())
    serialized = json.dumps(packet, ensure_ascii=False).lower()

    for forbidden in FORBIDDEN_VOCABULARY:
        assert forbidden not in serialized
    assert "observation-only research context" in serialized
    assert "not personalized financial advice" in serialized


def test_input_packet_immutability() -> None:
    input_packet = _complete_packet()
    before = deepcopy(input_packet)

    build_options_structure_evidence_packet(input_packet)

    assert input_packet == before
