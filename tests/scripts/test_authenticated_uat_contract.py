from __future__ import annotations

import json
from pathlib import Path

from scripts import release_runtime_fixture as fixture
from scripts import uat_runtime_harness as harness


class _Response:
    def __init__(self, status_code: int, payload: dict[str, object] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = json.dumps(self._payload)
        self.content = self.text.encode("utf-8")

    def json(self) -> dict[str, object]:
        return self._payload


class _SessionClient:
    def __init__(self, identity: str, *, fail_login: bool = False) -> None:
        self.identity = identity
        self.fail_login = fail_login
        self.logged_in = False

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        json_body: dict[str, object] | None = None,
    ) -> _Response:
        assert not headers or "Authorization" not in headers
        path = url.split("http://uat.local", 1)[-1]
        if path == "/api/v1/auth/login":
            if self.fail_login:
                return _Response(401, {"error": "invalid_login"})
            self.logged_in = True
            if self.identity == "member":
                return _Response(
                    200,
                    {
                        "ok": True,
                        "currentUser": {
                            "username": fixture.AUTHENTICATED_UAT_MEMBER_USERNAME,
                            "role": "user",
                            "isAdmin": False,
                            "adminCapabilities": [],
                        },
                    },
                )
            return _Response(
                200,
                {
                    "ok": True,
                    "currentUser": {
                        "username": fixture.AUTHENTICATED_UAT_ADMIN_USERNAME,
                        "role": "admin",
                        "isAdmin": True,
                        "adminCapabilities": ["ops:logs:read"],
                    },
                },
            )
        if path == "/api/v1/auth/status":
            return _Response(200, {"authEnabled": True, "loggedIn": self.logged_in})
        if path == "/api/v1/auth/logout":
            self.logged_in = False
            return _Response(204)
        if path in {"/api/v1/research/radar", "/api/v1/scanner/themes"}:
            return _Response(200 if self.logged_in else 401)
        if path in {"/api/v1/admin/ops/status", "/api/v1/admin/ops/surface-readiness"}:
            if not self.logged_in:
                return _Response(401)
            if self.identity != "admin":
                return _Response(403)
            if path.endswith("surface-readiness"):
                return _Response(200, {"surface": "ready"})
            return _Response(200, {"buildProvenance": {"contract": "admin_build_provenance_v1"}})
        if path == "/api/v1/admin/users":
            return _Response(403 if self.logged_in else 401)
        raise AssertionError(f"unexpected request: {method} {path}")

    def session_cookie_contract(self, name: str) -> dict[str, object]:
        return {
            "name": name,
            "present": self.logged_in,
            "httpOnly": self.logged_in,
            "transport": "cookie_jar",
        }


def test_seed_authenticated_uat_accounts_assigns_only_required_admin_capability(
    monkeypatch,
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "authenticated-uat.sqlite"
    env_path = tmp_path / "uat.env"
    env_path.write_text("APP_ENV=uat\nADMIN_AUTH_ENABLED=true\n", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "uat")
    monkeypatch.setenv("ADMIN_AUTH_ENABLED", "true")
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.setenv("ENV_FILE", str(env_path))
    monkeypatch.delenv("POSTGRES_PHASE_A_URL", raising=False)

    from src.config import Config
    from src.repositories.auth_repo import AuthRepository
    from src.storage import AdminUserRole, DatabaseManager

    Config.reset_instance()
    DatabaseManager.reset_instance()
    try:
        first = fixture.seed_authenticated_uat_accounts(
            member_password="member-session-password",
            admin_password="admin-session-password",
        )
        with DatabaseManager().session_scope() as session:
            session.add(
                AdminUserRole(
                    user_id=fixture.AUTHENTICATED_UAT_MEMBER_USER_ID,
                    role_key=fixture.AUTHENTICATED_UAT_ADMIN_ROLE,
                    assigned_by=fixture.AUTHENTICATED_UAT_ADMIN_USER_ID,
                )
            )
        second = fixture.seed_authenticated_uat_accounts(
            member_password="member-session-password",
            admin_password="admin-session-password",
        )
        repo = AuthRepository()

        assert first["status"] == second["status"] == "seeded"
        assert first["accountCount"] == 2
        assert repo.list_admin_user_roles(fixture.AUTHENTICATED_UAT_ADMIN_USER_ID) == [
            fixture.AUTHENTICATED_UAT_ADMIN_ROLE,
        ]
        assert repo.list_admin_capabilities_for_user(fixture.AUTHENTICATED_UAT_ADMIN_USER_ID) == [
            "ops:logs:read",
        ]
        assert repo.list_admin_user_roles(fixture.AUTHENTICATED_UAT_MEMBER_USER_ID) == []
        assert repo.list_admin_capabilities_for_user(fixture.AUTHENTICATED_UAT_MEMBER_USER_ID) == []
        serialized = json.dumps(first, sort_keys=True)
        assert "member-session-password" not in serialized
        assert "admin-session-password" not in serialized
        assert "super-admin" not in serialized
        assert str(tmp_path) not in serialized
    finally:
        DatabaseManager.reset_instance()
        Config.reset_instance()


def test_authenticated_uat_smoke_uses_real_cookie_sessions_and_exact_capability_matrix() -> None:
    clients = iter((_SessionClient("anonymous"), _SessionClient("member"), _SessionClient("admin")))
    member = harness.UatSmokeAccount(
        username=fixture.AUTHENTICATED_UAT_MEMBER_USERNAME,
        password="member-session-password",
        role="user",
        capabilities=(),
    )
    admin = harness.UatSmokeAccount(
        username=fixture.AUTHENTICATED_UAT_ADMIN_USERNAME,
        password="admin-session-password",
        role="admin",
        capabilities=("ops:logs:read",),
    )

    report = harness.run_authenticated_uat_smoke(
        base_url="http://uat.local",
        member=member,
        admin=admin,
        client_factory=lambda: next(clients),
    )

    assert report["status"] == "PASS"
    assert report["sessionTransport"] == "http_only_cookie_jar"
    assert report["sessionEstablishment"] == {
        "boundary": "POST /api/v1/auth/login",
        "transport": "HttpOnly CookieJar",
        "authorizationHeaderInjected": False,
        "dependencyUserInjected": False,
    }
    assert report["capabilityMatrix"] == {
        "member": [],
        "adminAllowed": ["ops:logs:read"],
        "adminDenied": ["users:read"],
    }
    assert all(check["status"] == "PASS" for check in report["checks"].values())
    assert report["checks"]["anonymousAccess"]["memberHttpStatus"] == 401
    assert report["checks"]["adminDenied"]["httpStatus"] == 403
    assert report["checks"]["sessionRevocation"]["httpStatus"] == 401
    assert report["adminPayloads"]["surfaceReadiness"] == {"surface": "ready"}
    serialized = json.dumps(report, sort_keys=True)
    assert "member-session-password" not in serialized
    assert "admin-session-password" not in serialized
    assert "Authorization" not in serialized


def test_authenticated_uat_smoke_fails_closed_when_session_establishment_fails() -> None:
    clients = iter((_SessionClient("anonymous"), _SessionClient("member", fail_login=True), _SessionClient("admin")))

    report = harness.run_authenticated_uat_smoke(
        base_url="http://uat.local",
        member=harness.UatSmokeAccount("member", "bad", "user", ()),
        admin=harness.UatSmokeAccount("admin", "unused", "admin", ("ops:logs:read",)),
        client_factory=lambda: next(clients),
    )

    assert report["status"] == "FAIL"
    assert report["checks"]["memberSession"]["status"] == "FAIL"
    assert "session_establishment_failed" in report["checks"]["memberSession"]["reasonCodes"]
