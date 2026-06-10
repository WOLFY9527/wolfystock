from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from api.deps import CurrentUser
from api.v1.endpoints import analysis
from api.v1.schemas.analysis import AnalyzeRequest


PILOT_ENABLED_ENV = "WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_RESERVE_RELEASE_PILOT_ENABLED"
PILOT_OWNER_ALLOWLIST_ENV = "WOLFYSTOCK_QUOTA_ANALYSIS_SYNC_RESERVE_RELEASE_OWNER_IDS"
_DEFAULT_SERVICE_RESULT = object()


class _FakeReport:
    def model_dump(self) -> dict:
        return {"summary": {"operation_advice": "Observe only"}}


class _FakeExecutionLogs:
    instances: list["_FakeExecutionLogs"] = []

    def __init__(self) -> None:
        self.started: list[dict] = []
        self.finished: list[dict] = []
        _FakeExecutionLogs.instances.append(self)

    def start_analysis_execution(self, **kwargs):
        self.started.append(kwargs)
        return "exec-1"

    def add_execution_step(self, **_kwargs):
        return None

    def append_runtime_result(self, **_kwargs):
        return None

    def get_business_event_detail(self, _execution_id):
        return {"recordId": "record-1"}

    def finish_analysis_execution(self, **kwargs):
        self.finished.append(kwargs)


def _pilot_user(
    user_id: str = "pilot-user",
    *,
    is_authenticated: bool = True,
    transitional: bool = False,
    auth_enabled: bool = True,
) -> CurrentUser:
    return CurrentUser(
        user_id=user_id,
        username="pilot",
        display_name="Pilot User",
        role="user",
        is_admin=False,
        is_authenticated=is_authenticated,
        transitional=transitional,
        auth_enabled=auth_enabled,
    )


def _analysis_response(query_id: str = "resolved-query") -> dict:
    return {
        "query_id": query_id,
        "stock_code": "AAPL",
        "stock_name": "Apple",
        "report": {"summary": {"operation_advice": "Observe only"}},
        "runtime_execution": {"status": "success"},
        "notification_result": {"sent": False},
    }


def _install_quota_service(
    monkeypatch: pytest.MonkeyPatch,
    *,
    reserve_decision: SimpleNamespace | None = None,
    reserve_exception: Exception | None = None,
) -> dict[str, list]:
    calls: dict[str, list] = {"init": [], "reserve": [], "release": []}
    decision = reserve_decision or SimpleNamespace(
        allowed=True,
        status="reserved",
        reservation_id="qres_success",
        estimated_units=5,
    )

    class FakeQuotaPolicyService:
        def __init__(self, **kwargs) -> None:
            calls["init"].append(kwargs)

        def reserve_quota(self, **kwargs):
            calls["reserve"].append(kwargs)
            if reserve_exception is not None:
                raise reserve_exception
            return decision

        def release_reservation(self, **kwargs):
            calls["release"].append(kwargs)
            return SimpleNamespace(allowed=True, status="released", reservation_id=kwargs.get("reservation_id"))

    monkeypatch.setattr(analysis, "QuotaPolicyService", FakeQuotaPolicyService, raising=False)
    return calls


def _install_sync_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    service_result=_DEFAULT_SERVICE_RESULT,
    service_exception=None,
) -> None:
    class FakeAnalysisService:
        def analyze_stock(self, **_kwargs):
            if service_exception is not None:
                raise service_exception
            if service_result is _DEFAULT_SERVICE_RESULT:
                return _analysis_response()
            return service_result

    _FakeExecutionLogs.instances = []
    monkeypatch.setattr(analysis, "_load_sync_fundamental_sources", lambda **_kwargs: (None, None))
    monkeypatch.setattr(analysis, "_build_analysis_report", lambda *_args, **_kwargs: _FakeReport())
    monkeypatch.setattr(
        "src.services.execution_log_service.ExecutionLogService",
        _FakeExecutionLogs,
    )
    monkeypatch.setattr(
        "src.services.analysis_service.AnalysisService",
        FakeAnalysisService,
    )


def _enable_pilot(monkeypatch: pytest.MonkeyPatch, *, owners: str = "pilot-user") -> None:
    monkeypatch.setenv(PILOT_ENABLED_ENV, "true")
    monkeypatch.setenv(PILOT_OWNER_ALLOWLIST_ENV, owners)


def _run_sync(monkeypatch: pytest.MonkeyPatch, current_user: CurrentUser | None = None, **request_overrides):
    _install_sync_dependencies(
        monkeypatch,
        service_result=request_overrides.pop("service_result", _DEFAULT_SERVICE_RESULT),
    )
    request = AnalyzeRequest(
        stock_code=request_overrides.pop("stock_code", "AAPL"),
        stock_name=request_overrides.pop("stock_name", "Apple"),
        async_mode=request_overrides.pop("async_mode", False),
        original_query=request_overrides.pop("original_query", None),
        report_type=request_overrides.pop("report_type", "detailed"),
        force_refresh=request_overrides.pop("force_refresh", False),
        **request_overrides,
    )
    return analysis._handle_sync_analysis("AAPL", request, current_user or _pilot_user())


def test_out_of_scope_owner_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot(monkeypatch, owners="other-user")
    calls = _install_quota_service(monkeypatch)

    response = _run_sync(monkeypatch, _pilot_user("pilot-user"))

    assert response.stock_code == "AAPL"
    assert calls["reserve"] == []
    assert calls["release"] == []


@pytest.mark.parametrize(
    "current_user",
    [
        _pilot_user(is_authenticated=False),
        _pilot_user(transitional=True),
        _pilot_user(is_authenticated=False, transitional=True, auth_enabled=False),
    ],
)
def test_unauthenticated_transitional_and_auth_disabled_users_are_noop(
    monkeypatch: pytest.MonkeyPatch,
    current_user: CurrentUser,
) -> None:
    _enable_pilot(monkeypatch)
    calls = _install_quota_service(monkeypatch)

    response = _run_sync(monkeypatch, current_user)

    assert response.stock_code == "AAPL"
    assert calls["reserve"] == []
    assert calls["release"] == []


def test_async_request_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot(monkeypatch)
    calls = _install_quota_service(monkeypatch)

    class FakeTaskQueue:
        def submit_tasks_batch(self, **_kwargs):
            return [SimpleNamespace(task_id="task-1", stock_code="AAPL")], []

    monkeypatch.setattr(analysis, "_raise_if_llm_model_unavailable", lambda _config: None)
    monkeypatch.setattr(analysis, "get_task_queue", lambda: FakeTaskQueue())

    response = analysis.trigger_analysis(
        AnalyzeRequest(stock_code="AAPL", async_mode=True),
        config=SimpleNamespace(),
        current_user=_pilot_user(),
    )

    assert response.status_code == 202
    assert calls["reserve"] == []
    assert calls["release"] == []


def test_reservation_success_releases_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot(monkeypatch)
    calls = _install_quota_service(monkeypatch)

    response = _run_sync(monkeypatch)

    assert response.stock_code == "AAPL"
    assert calls["reserve"][0]["owner_user_id"] == "pilot-user"
    assert calls["reserve"][0]["route_family"] == "analysis"
    assert calls["release"] == [{"reservation_id": "qres_success"}]
    assert _FakeExecutionLogs.instances[0].started[0]["metadata"] == {
        "quota_route_pilot": {"reservation_id": "qres_success"}
    }


def test_reservation_success_releases_on_http_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot(monkeypatch)
    calls = _install_quota_service(monkeypatch)
    _install_sync_dependencies(monkeypatch, service_result=None)

    request = AnalyzeRequest(stock_code="AAPL", async_mode=False)
    with pytest.raises(HTTPException) as exc_info:
        analysis._handle_sync_analysis("AAPL", request, _pilot_user())

    assert exc_info.value.status_code == 500
    assert calls["release"] == [{"reservation_id": "qres_success"}]


def test_reservation_success_releases_on_generic_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot(monkeypatch)
    calls = _install_quota_service(monkeypatch)
    _install_sync_dependencies(monkeypatch, service_exception=RuntimeError("boom"))

    request = AnalyzeRequest(stock_code="AAPL", async_mode=False)
    with pytest.raises(HTTPException) as exc_info:
        analysis._handle_sync_analysis("AAPL", request, _pilot_user())

    assert exc_info.value.status_code == 500
    assert calls["release"] == [{"reservation_id": "qres_success"}]


def test_reservation_failure_does_not_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot(monkeypatch)
    calls = _install_quota_service(
        monkeypatch,
        reserve_decision=SimpleNamespace(
            allowed=False,
            status="budget_exceeded",
            reservation_id=None,
            estimated_units=5,
        ),
    )

    response = _run_sync(monkeypatch)

    assert response.stock_code == "AAPL"
    assert calls["reserve"]
    assert calls["release"] == []


def test_reservation_exception_does_not_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot(monkeypatch)
    calls = _install_quota_service(monkeypatch, reserve_exception=RuntimeError("quota down"))

    response = _run_sync(monkeypatch)

    assert response.stock_code == "AAPL"
    assert calls["reserve"]
    assert calls["release"] == []


def test_response_shape_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot(monkeypatch)
    _install_quota_service(monkeypatch)

    response = _run_sync(monkeypatch)
    payload = response.model_dump()
    serialized = json.dumps(payload, sort_keys=True)

    assert set(payload) == {
        "query_id",
        "stock_code",
        "stock_name",
        "report",
        "created_at",
        "market_timestamp",
        "market_session_date",
        "news_published_at",
        "report_generated_at",
    }
    assert "quota" not in serialized.lower()
    assert "qres_success" not in serialized


def test_idempotency_key_uses_only_sanitized_route_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_pilot(monkeypatch)
    calls = _install_quota_service(monkeypatch)

    class FakeUuid:
        hex = "route-query-001"

    with patch("uuid.uuid4", return_value=FakeUuid()):
        _run_sync(
            monkeypatch,
            stock_name="Apple SECRET_STOCK_NAME",
            original_query="raw user text SECRET_ORIGINAL_QUERY",
            report_type="brief",
            force_refresh=True,
            researchMode="deep",
        )

    idempotency_key = calls["reserve"][0]["idempotency_key"]
    assert "quota:analysis_sync_single_stock:v1" in idempotency_key
    assert "route_family:analysis" in idempotency_key
    assert "route_key:api.v1.analysis.analyze" in idempotency_key
    assert "mode:sync" in idempotency_key
    assert "owner:pilot-user" in idempotency_key
    assert "stock:AAPL" in idempotency_key
    assert "report_type:brief" in idempotency_key
    assert "force_refresh:1" in idempotency_key
    assert "research_mode:deep" in idempotency_key
    assert "query_id:route-query-001" in idempotency_key
    assert "SECRET_STOCK_NAME" not in idempotency_key
    assert "SECRET_ORIGINAL_QUERY" not in idempotency_key
    assert "cookie" not in idempotency_key.lower()
    assert "token" not in idempotency_key.lower()
    assert "prompt" not in idempotency_key.lower()


def test_quota_reserve_release_static_boundary_is_sync_analysis_only() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    analysis_source = (repo_root / "api/v1/endpoints/analysis.py").read_text(encoding="utf-8")
    sync_section = analysis_source.split("def _handle_sync_analysis", 1)[1].split("# ============================================================", 1)[0]
    preview_section = analysis_source.split("def preview_analysis", 1)[1].split("@router.post(\n    \"/analyze\"", 1)[0]
    async_section = analysis_source.split("def _handle_async_analysis_batch", 1)[1].split("def _handle_sync_analysis", 1)[0]

    assert "reserve_quota" in analysis_source
    assert "release_reservation" in analysis_source
    assert "_try_reserve_analysis_sync_quota_pilot" in sync_section
    assert "_release_analysis_sync_quota_pilot_reservation" in sync_section
    assert "reserve_quota" not in preview_section
    assert "release_reservation" not in preview_section
    assert "reserve_quota" not in async_section
    assert "release_reservation" not in async_section

    for relative in (
        "api/v1/endpoints/scanner.py",
        "api/v1/endpoints/agent.py",
        "api/v1/endpoints/options.py",
        "api/v1/endpoints/market_provider_operations.py",
        "api/v1/endpoints/admin_provider_operations_matrix.py",
        "api/v1/endpoints/provider_usage_ledger.py",
        "api/v1/endpoints/admin_provider_circuits.py",
    ):
        source = (repo_root / relative).read_text(encoding="utf-8")
        assert "reserve_quota" not in source
        assert "release_reservation" not in source
