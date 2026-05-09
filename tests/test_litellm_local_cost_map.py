# -*- coding: utf-8 -*-
"""Local-soak guards for LiteLLM model cost-map loading."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_litellm_import_uses_local_cost_map_without_remote_fetch_in_local_mode() -> None:
    code = textwrap.dedent(
        """
        import os
        import httpx

        calls = []

        def forbidden_get(*args, **kwargs):
            calls.append((args, kwargs))
            raise RuntimeError("remote fetch should not be attempted")

        httpx.get = forbidden_get
        os.environ.pop("APP_ENV", None)
        os.environ.pop("ENVIRONMENT", None)
        os.environ.pop("DSA_ENV", None)
        os.environ.pop("LITELLM_LOCAL_MODEL_COST_MAP", None)
        os.environ["LITELLM_MODEL_COST_MAP_URL"] = "https://example.invalid/model_cost_map?api_key=must-not-leak"

        import src.agent.llm_adapter  # noqa: F401
        import litellm
        from litellm.litellm_core_utils.get_model_cost_map import get_model_cost_map_source_info

        info = get_model_cost_map_source_info()
        print(f"calls={len(calls)}")
        print(f"flag={os.environ.get('LITELLM_LOCAL_MODEL_COST_MAP')}")
        print(f"source={info.get('source')}")
        print(f"forced={info.get('is_env_forced')}")
        print(f"models={len(getattr(litellm, 'model_cost', {}) or {})}")
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    combined_output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined_output
    assert "calls=0" in result.stdout
    assert "flag=True" in result.stdout
    assert "source=local" in result.stdout
    assert "forced=True" in result.stdout
    assert "models=0" not in result.stdout
    assert "Failed to fetch remote model cost map" not in combined_output
    assert "must-not-leak" not in combined_output


def test_litellm_local_cost_map_setting_respects_production_env() -> None:
    from src.services.litellm_runtime import configure_litellm_cost_map_for_runtime

    env = {
        "APP_ENV": "production",
    }

    result = configure_litellm_cost_map_for_runtime(env=env)

    assert result["mode"] == "remote_allowed"
    assert "LITELLM_LOCAL_MODEL_COST_MAP" not in env


def test_litellm_local_cost_map_setting_preserves_explicit_litellm_flag() -> None:
    from src.services.litellm_runtime import configure_litellm_cost_map_for_runtime

    env = {
        "LITELLM_LOCAL_MODEL_COST_MAP": "false",
    }

    result = configure_litellm_cost_map_for_runtime(env=env)

    assert result["mode"] == "explicit"
    assert env["LITELLM_LOCAL_MODEL_COST_MAP"] == "false"
