from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_pytest_discovers_only_authoritative_test_root() -> None:
    setup_cfg = (ROOT / "setup.cfg").read_text(encoding="utf-8")

    assert "testpaths = tests" in setup_cfg
    assert not (ROOT / "test_env.py").exists()


def test_environment_diagnostic_import_has_no_setup_side_effect(monkeypatch) -> None:
    import src.config

    calls: list[bool] = []
    monkeypatch.setattr(src.config, "setup_env", lambda *args, **kwargs: calls.append(True))
    script = ROOT / "scripts" / "diagnose_environment.py"
    spec = importlib.util.spec_from_file_location("diagnose_environment", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert calls == []
