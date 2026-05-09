# -*- coding: utf-8 -*-
"""Runtime defaults for LiteLLM imports."""

from __future__ import annotations

import os
from typing import MutableMapping


_PRODUCTION_ENV_VALUES = {"prod", "production"}
_REMOTE_ENV_VALUES = _PRODUCTION_ENV_VALUES | {"staging", "stage"}
_ENV_KEYS = ("APP_ENV", "ENVIRONMENT", "DSA_ENV")


def configure_litellm_cost_map_for_runtime(
    *,
    env: MutableMapping[str, str] | None = None,
) -> dict[str, str]:
    """Prefer LiteLLM's bundled cost map for local/test/offline imports.

    LiteLLM fetches its model cost map from GitHub during import unless
    ``LITELLM_LOCAL_MODEL_COST_MAP=True`` is already set. WolfyStock keeps its
    own cost ledger on local pricing policies, so local/test runs should avoid
    that best-effort network fetch noise while preserving LiteLLM metadata.
    """
    target_env = env if env is not None else os.environ

    explicit = str(target_env.get("LITELLM_LOCAL_MODEL_COST_MAP") or "").strip()
    if explicit:
        return {"mode": "explicit"}

    environment = _resolve_environment(target_env)
    if environment in _REMOTE_ENV_VALUES:
        return {"mode": "remote_allowed", "environment": environment}

    target_env["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    return {"mode": "local_forced", "environment": environment or "local"}


def _resolve_environment(env: MutableMapping[str, str]) -> str:
    for key in _ENV_KEYS:
        value = str(env.get(key) or "").strip().lower()
        if value:
            return value
    return ""
