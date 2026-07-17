# -*- coding: utf-8 -*-
"""Production ingress and SPA static containment release contracts."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import src.auth as auth
from api.app import create_app
from api.deps import resolve_current_user
from src.runtime.composition import RuntimeContainer
from src.storage import DatabaseManager


REPO_ROOT = Path(__file__).resolve().parents[2]


class _QueueResource:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def get_runtime_status(self) -> dict[str, object]:
        return {
            "mode": "process_local",
            "single_process_required": True,
            "configured_worker_count": 1,
            "topology_ok": True,
            "shutdown": False,
            "worker_hints": {},
        }

    def shutdown(self, *, wait: bool = False, cancel_futures: bool = True) -> None:
        self._events.append(f"queue:close:{wait}:{cancel_futures}")


def _runtime_container(events: list[str]) -> RuntimeContainer:
    return RuntimeContainer(
        system_config_service_factory=lambda: events.append("system:start") or object(),
        task_queue_factory=lambda: events.append("queue:start") or _QueueResource(events),
        should_start_crypto_realtime=lambda: False,
    )


def _configure_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    profile: str,
    auth_value: str | None,
) -> None:
    env_path = tmp_path / "runtime.env"
    lines = [f"APP_ENV={profile}", "CORS_ORIGINS=https://app.example.invalid"]
    if auth_value is not None:
        lines.append(f"ADMIN_AUTH_ENABLED={auth_value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    monkeypatch.setenv("ENV_FILE", str(env_path))
    monkeypatch.setenv("APP_ENV", profile)
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.invalid")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("DSA_ENV", raising=False)
    if auth_value is None:
        monkeypatch.delenv("ADMIN_AUTH_ENABLED", raising=False)
    else:
        monkeypatch.setenv("ADMIN_AUTH_ENABLED", auth_value)
    auth._auth_enabled = None


def test_production_app_creation_fails_closed_when_auth_is_disabled_before_runtime_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_environment(
        tmp_path,
        monkeypatch,
        profile="production",
        auth_value="false",
    )
    events: list[str] = []
    container = _runtime_container(events)

    with pytest.raises(RuntimeError, match="Production requires ADMIN_AUTH_ENABLED=true"):
        create_app(container, static_dir=tmp_path / "static")

    assert container.is_started is False
    assert events == []


def test_production_auth_snapshot_cannot_be_overridden_by_cached_auth_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_environment(
        tmp_path,
        monkeypatch,
        profile="production",
        auth_value="false",
    )
    auth._auth_enabled = True

    with pytest.raises(RuntimeError, match="Production requires ADMIN_AUTH_ENABLED=true"):
        create_app(static_dir=tmp_path / "static")


def test_production_app_creation_fails_closed_when_auth_configuration_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_environment(
        tmp_path,
        monkeypatch,
        profile="production",
        auth_value=None,
    )

    with pytest.raises(RuntimeError, match="Production requires ADMIN_AUTH_ENABLED=true"):
        create_app(static_dir=tmp_path / "static")


def test_production_app_creation_succeeds_with_explicit_auth_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_environment(
        tmp_path,
        monkeypatch,
        profile="production",
        auth_value="true",
    )
    events: list[str] = []
    container = _runtime_container(events)
    app = create_app(container, static_dir=tmp_path / "missing-static")

    assert container.is_started is False
    assert events == []

    with TestClient(app) as client:
        health_response = client.get("/api/health/live")
        auth_response = client.get("/api/v1/auth/status")
        docs_response = client.get("/docs")

    assert health_response.status_code == 200
    assert auth_response.status_code == 200
    assert auth_response.json()["authEnabled"] is True
    assert docs_response.status_code == 401
    assert events == ["system:start", "queue:start", "queue:close:False:True"]


def test_production_module_import_fails_before_route_import_when_auth_is_missing(
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "production.env"
    env_path.write_text(
        "APP_ENV=production\nCORS_ORIGINS=https://app.example.invalid\n",
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment.update({"APP_ENV": "production", "ENV_FILE": str(env_path)})
    environment.pop("ADMIN_AUTH_ENABLED", None)
    environment.pop("ENVIRONMENT", None)
    environment.pop("DSA_ENV", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import builtins\n"
                "original_import = builtins.__import__\n"
                "def guarded_import(name, *args, **kwargs):\n"
                "    if name == 'litellm':\n"
                "        raise RuntimeError('route import occurred before ingress check')\n"
                "    return original_import(name, *args, **kwargs)\n"
                "builtins.__import__ = guarded_import\n"
                "import api.app\n"
            ),
        ],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "Production requires ADMIN_AUTH_ENABLED=true" in result.stderr
    assert "route import occurred before ingress check" not in result.stderr


def test_explicit_local_development_remains_usable_with_auth_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_environment(
        tmp_path,
        monkeypatch,
        profile="development",
        auth_value="false",
    )
    events: list[str] = []
    app = create_app(_runtime_container(events), static_dir=tmp_path / "missing-static")

    with TestClient(app) as client:
        response = client.get("/api/health/live")

    assert response.status_code == 200
    assert events == ["system:start", "queue:start", "queue:close:False:True"]


def test_production_never_projects_anonymous_transitional_admin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_environment(
        tmp_path,
        monkeypatch,
        profile="production",
        auth_value="false",
    )
    db_path = tmp_path / "production-auth.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    DatabaseManager.reset_instance()
    DatabaseManager(db_url=f"sqlite:///{db_path}")
    request = SimpleNamespace(state=SimpleNamespace(), cookies={})
    try:
        assert resolve_current_user(request) is None
    finally:
        DatabaseManager.reset_instance()


def test_contained_static_file_and_spa_index_are_served(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_environment(
        tmp_path,
        monkeypatch,
        profile="development",
        auth_value="false",
    )
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>contained-index</html>", encoding="utf-8")
    (static_dir / "manifest.json").write_text('{"contained": true}', encoding="utf-8")
    app = create_app(_runtime_container([]), static_dir=static_dir)

    with TestClient(app) as client:
        asset = client.get("/manifest.json")
        fallback = client.get("/dashboard/overview")

    assert asset.status_code == 200
    assert asset.json() == {"contained": True}
    assert fallback.status_code == 200
    assert fallback.text == "<html>contained-index</html>"


def test_canonical_candidate_outside_static_root_is_rejected_with_bounded_404(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_environment(
        tmp_path,
        monkeypatch,
        profile="development",
        auth_value="false",
    )
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>contained-index</html>", encoding="utf-8")
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("outside-root-marker", encoding="utf-8")
    (static_dir / "linked.txt").symlink_to(outside_file)
    app = create_app(_runtime_container([]), static_dir=static_dir)

    with TestClient(app) as client:
        response = client.get("/linked.txt")

    assert response.status_code == 404
    assert response.json() == {
        "error": "not_found",
        "message": "Static asset not found",
    }
    assert "outside-root-marker" not in response.text
    assert str(tmp_path) not in response.text


def test_spa_index_outside_static_root_preserves_missing_asset_degradation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_environment(
        tmp_path,
        monkeypatch,
        profile="development",
        auth_value="false",
    )
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    outside_index = tmp_path / "outside-index.html"
    outside_index.write_text("<html>outside-index-marker</html>", encoding="utf-8")
    (static_dir / "index.html").symlink_to(outside_index)
    app = create_app(_runtime_container([]), static_dir=static_dir)

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert app.state.frontend_static_mode == "unavailable"
    assert "Frontend Not Built" in response.text
    assert "outside-index-marker" not in response.text
