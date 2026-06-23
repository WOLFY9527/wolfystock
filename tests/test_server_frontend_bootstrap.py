from __future__ import annotations

import importlib
import sys


def test_server_entrypoint_prepares_frontend_assets_before_import(monkeypatch) -> None:
    calls: list[str] = []

    import src.webui_frontend as webui_frontend

    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(webui_frontend, "prepare_webui_frontend_assets", lambda: calls.append("prepare") or True)
    sys.modules.pop("server", None)

    try:
        importlib.import_module("server")
    finally:
        sys.modules.pop("server", None)

    assert calls == ["prepare"]
