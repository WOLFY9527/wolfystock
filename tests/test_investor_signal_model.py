# -*- coding: utf-8 -*-
"""Tests for the inert investor signal contract helper."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

from src.services.investor_signal_model import (
    CAPITAL_FLOW_REGIME_LABEL_VALUES,
    CONFIDENCE_LABEL_VALUES,
    CONTRADICTION_CODE_VALUES,
    FORBIDDEN_CONSUMER_SAFE_FIELDS,
    INVESTOR_SIGNAL_CONTRACT_VERSION,
    MARKET_REGIME_LABEL_VALUES,
    REASON_CODE_VALUES,
    THEME_FLOW_STATE_VALUES,
    build_consumer_safe_investor_signal,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = REPO_ROOT / "src/services/investor_signal_model.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "data_provider",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "yfinance",
    "src.services.market_cache",
    "src.services.data_source_router",
)


def _helper_imports() -> set[str]:
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    return imported_modules


def _authoritative_signal(**overrides: Any) -> dict[str, Any]:
    payload = {
        "marketRegime": "risk_on",
        "capitalFlowRegime": "inflow",
        "themeFlowState": "leading",
        "confidenceLabel": "high",
        "source": "fred",
        "sourceLabel": "FRED",
        "sourceType": "official_public",
        "freshness": "live",
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": True,
        "reasonCodes": [],
        "contradictionCodes": [],
        "providerId": "fred_provider",
        "providerName": "FRED",
        "adminDiagnostics": {"route": "internal-only"},
        "providerRouting": {"target": "fred"},
    }
    payload.update(overrides)
    return payload


def test_investor_signal_helper_is_pure_deterministic_and_json_safe() -> None:
    imports = _helper_imports()
    assert all(not module.startswith(FORBIDDEN_IMPORT_PREFIXES) for module in imports)

    payload = _authoritative_signal()
    original = copy.deepcopy(payload)

    first = build_consumer_safe_investor_signal(payload)
    second = build_consumer_safe_investor_signal(payload)

    assert payload == original
    assert first == second
    assert json.loads(json.dumps(first, ensure_ascii=False)) == first


def test_fallback_stale_and_partial_inputs_stay_observation_only_and_never_become_live_or_score_grade() -> None:
    signal = build_consumer_safe_investor_signal(
        _authoritative_signal(
            source="yfinance_proxy",
            sourceType="public_proxy",
            freshness="stale",
            isStale=True,
            isFallback=True,
            isPartial=True,
            reasonCodes=["fallback_source", "stale_source", "partial_source"],
        )
    )

    assert signal["observationOnly"] is True
    assert signal["authorityGrant"] is False
    assert signal["decisionGrade"] is False
    assert signal["sourceAuthorityAllowed"] is False
    assert signal["scoreContributionAllowed"] is False
    assert signal["freshness"] in {"fallback", "stale", "partial"}
    assert signal["freshness"] != "live"
    assert signal["confidenceLabel"] == "low"
    assert "fallback_source" in signal["reasonCodes"]
    assert "stale_source" in signal["reasonCodes"]
    assert "partial_source" in signal["reasonCodes"]
    assert "confidence_capped" in signal["reasonCodes"]


def test_missing_or_ambiguous_authority_fails_closed() -> None:
    missing_authority = build_consumer_safe_investor_signal(
        _authoritative_signal(sourceAuthorityAllowed=None)
    )
    ambiguous_source = build_consumer_safe_investor_signal(
        _authoritative_signal(source="mixed", sourceAuthorityAllowed=True, scoreContributionAllowed=True)
    )

    for signal in (missing_authority, ambiguous_source):
        assert signal["observationOnly"] is True
        assert signal["sourceAuthorityAllowed"] is False
        assert signal["scoreContributionAllowed"] is False
        assert signal["confidenceLabel"] == "blocked"
    assert "source_authority_missing" in missing_authority["reasonCodes"]
    assert "source_identity_ambiguous" in ambiguous_source["reasonCodes"]


def test_mixed_signals_cap_confidence_and_preserve_contradictions_in_consumer_safe_form() -> None:
    signal = build_consumer_safe_investor_signal(
        _authoritative_signal(
            capitalFlowRegime="outflow",
            contradictionCodes=["capital_flow_signal_mismatch", "market_regime_signal_mismatch"],
            confidenceLabel="high",
        )
    )

    assert signal["sourceAuthorityAllowed"] is False
    assert signal["scoreContributionAllowed"] is False
    assert signal["confidenceLabel"] == "low"
    assert signal["contradictionCodes"] == [
        "capital_flow_signal_mismatch",
        "market_regime_signal_mismatch",
    ]
    assert "conflicting_signal_inputs" in signal["reasonCodes"]
    assert "confidence_capped" in signal["reasonCodes"]


def test_consumer_safe_output_excludes_raw_provider_and_admin_fields() -> None:
    signal = build_consumer_safe_investor_signal(
        _authoritative_signal(
            internalReasonCodes=["polygon_unauthorized"],
            routeDecision={"winner": "polygon"},
            providerBudget={"remaining": 1},
            adminNotes="debug-only",
        )
    )

    for field in FORBIDDEN_CONSUMER_SAFE_FIELDS:
        assert field not in signal


def test_unknown_labels_fail_closed_into_controlled_vocabulary_only() -> None:
    signal = build_consumer_safe_investor_signal(
        _authoritative_signal(
            marketRegime="panic_buy",
            capitalFlowRegime="sideways_but_maybe_up",
            themeFlowState="rocketship",
            confidenceLabel="max",
            reasonCodes=["polygon_unauthorized", "internal_admin_debug"],
        )
    )

    assert signal["contractVersion"] == INVESTOR_SIGNAL_CONTRACT_VERSION
    assert signal["marketRegime"] in MARKET_REGIME_LABEL_VALUES
    assert signal["capitalFlowRegime"] in CAPITAL_FLOW_REGIME_LABEL_VALUES
    assert signal["themeFlowState"] in THEME_FLOW_STATE_VALUES
    assert signal["confidenceLabel"] in CONFIDENCE_LABEL_VALUES
    assert set(signal["reasonCodes"]) <= REASON_CODE_VALUES
    assert set(signal["contradictionCodes"]) <= CONTRADICTION_CODE_VALUES
    assert signal["marketRegime"] == "insufficient_evidence"
    assert signal["capitalFlowRegime"] == "insufficient_evidence"
    assert signal["themeFlowState"] == "insufficient_evidence"
    assert signal["confidenceLabel"] == "blocked"
    assert "unsupported_signal_label" in signal["reasonCodes"]
    assert "internal_detail_redacted" in signal["reasonCodes"]
