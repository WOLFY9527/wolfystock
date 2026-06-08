from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from tests.api.test_analysis import (
    _assert_no_forbidden_keys,
    _service_response_for_api_contract,
)


@pytest.fixture(autouse=True)
def disable_auth():
    auth._auth_enabled = None
    with patch("api.middlewares.auth.is_auth_enabled", return_value=False), patch(
        "api.deps.is_auth_enabled", return_value=False
    ), patch("src.auth.is_auth_enabled", return_value=False):
        yield
    auth._auth_enabled = None


@pytest.fixture
def client(tmp_path):
    app = create_app(static_dir=tmp_path)
    with TestClient(app) as test_client:
        yield test_client


def test_public_preview_uses_consumer_safe_projection_without_advice_or_diagnostics(client) -> None:
    service_response = _service_response_for_api_contract()
    service_response["report"]["summary"]["operation_advice"] = "Buy on pullback"
    service_response["report"]["summary"]["decision_type"] = "buy"
    service_response["report"]["summary"]["signal_type"] = "buy"
    service_response["report"]["strategy"] = {
        "ideal_buy": "184-186",
        "secondary_buy": "181",
        "stop_loss": "179",
        "take_profit": "195-198",
        "battle_plan": {"sniper_points": {"ideal_buy": "184-186"}},
        "position_strategy": "half position",
        "position_advice": "scale in",
        "has_trading_plan": True,
    }
    service_response["report"]["dataQualityReport"] = {
        "confidenceCap": 100,
        "sourceAuthorityAllowed": True,
        "scoreContributionAllowed": True,
        "providerAuthority": "scoreGradeAllowed",
        "rawProviderPayload": {"sentinel": "raw-provider-preview-leak"},
    }
    service_response["report"]["details"]["analysis_result"]["backendDiagnostics"] = {
        "providerRoute": "polygon",
        "cacheKey": "preview-cache-key",
        "reasonCode": "source_authority_allowed",
    }

    execution_log = MagicMock()
    execution_log.start_analysis_execution.return_value = "preview-execution-001"

    with patch("api.v1.endpoints.analysis._raise_if_llm_model_unavailable", return_value=None), patch(
        "src.services.analysis_service.AnalysisService.analyze_stock",
        return_value=service_response,
    ), patch(
        "src.services.execution_log_service.ExecutionLogService",
        return_value=execution_log,
    ):
        response = client.post(
            "/api/v1/analysis/preview",
            json={"stock_code": "AAPL", "stock_name": "Apple", "report_type": "brief"},
        )

    assert response.status_code == 200
    payload = response.json()
    report = payload["report"]
    serialized_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    assert report["summary"]["observation_scope"] == "仅观察"
    assert "研究摘要" in report["summary"]["analysis_summary"]
    assert "关键价位参考" in report["summary"]["key_price_reference"]
    assert "证据边界" in report["summary"]["evidence_boundary"]
    assert "strategy" not in report
    assert "details" not in report
    assert "dataQualityReport" not in report
    assert "data_quality_report" not in report
    assert "model_used" not in serialized_payload
    assert "modelUsed" not in serialized_payload

    for forbidden_value in (
        "Buy on pullback",
        '"buy"',
        "184-186",
        "181",
        "179",
        "195-198",
        "half position",
        "scale in",
        "raw-provider-preview-leak",
        "source_authority_allowed",
        "preview-cache-key",
        "scoreGradeAllowed",
    ):
        assert forbidden_value not in serialized_payload

    _assert_no_forbidden_keys(
        payload,
        (
            "operation_advice",
            "operationAdvice",
            "decision_type",
            "decisionType",
            "signal_type",
            "signalType",
            "battle_plan",
            "battlePlan",
            "sniper_points",
            "sniperPoints",
            "ideal_buy",
            "idealBuy",
            "secondary_buy",
            "secondaryBuy",
            "stop_loss",
            "stopLoss",
            "take_profit",
            "takeProfit",
            "position_strategy",
            "positionStrategy",
            "position_advice",
            "positionAdvice",
            "has_trading_plan",
            "hasTradingPlan",
            "raw_result",
            "rawResult",
            "context_snapshot",
            "contextSnapshot",
            "rawProviderPayload",
            "rawSourcePayload",
            "rawCachePayload",
            "providerRoute",
            "providerAuthority",
            "sourceAuthorityAllowed",
            "scoreContributionAllowed",
            "sourceTier",
            "field_sources",
            "fieldSources",
            "field_periods",
            "fieldPeriods",
            "topEvidenceRefs",
            "backendDiagnostics",
            "reasonCode",
            "cacheKey",
        ),
    )
