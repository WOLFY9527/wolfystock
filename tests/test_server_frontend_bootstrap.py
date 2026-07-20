from __future__ import annotations

import importlib
import inspect
import sys


def test_server_entrypoint_prepares_frontend_assets_before_import(monkeypatch) -> None:
    calls: list[str] = []

    import api as api_package
    import src.webui_frontend as webui_frontend

    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(webui_frontend, "prepare_webui_frontend_assets", lambda: calls.append("prepare") or True)
    previous_api_app = sys.modules.pop("api.app", None)
    previous_package_app = getattr(api_package, "app", None)
    sys.modules.pop("server", None)

    try:
        server_module = importlib.import_module("server")
        container = server_module.app.state.runtime_container
        assert server_module.config.runtime_settings is container.runtime_settings
        assert container.config is server_module.config
        snapshot = server_module.config.runtime_settings
        server_source = inspect.getsource(server_module)
        assert "host=config.webui_host" in server_source
        assert "port=config.webui_port" in server_source
        monkeypatch.setenv("MAX_WORKERS", "99")
        importlib.reload(server_module)
        assert server_module.config.runtime_settings is snapshot
    finally:
        sys.modules.pop("server", None)
        if previous_api_app is not None:
            sys.modules["api.app"] = previous_api_app
        if previous_package_app is None and hasattr(api_package, "app"):
            delattr(api_package, "app")
        elif previous_package_app is not None:
            api_package.app = previous_package_app

    assert calls == ["prepare", "prepare"]
