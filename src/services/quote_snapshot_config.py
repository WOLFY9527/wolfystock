"""Configuration helpers for local quote snapshot evidence."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


US_QUOTE_SNAPSHOT_CACHE_ENV_KEYS = (
    "LOCAL_US_QUOTE_SNAPSHOT_CACHE_PATH",
    "US_QUOTE_SNAPSHOT_CACHE_PATH",
    "WOLFYSTOCK_US_QUOTE_SNAPSHOT_CACHE_PATH",
    "QUOTE_SNAPSHOT_CACHE_PATH",
)


def get_configured_us_quote_snapshot_cache_path(
    env: Mapping[str, str] | None = None,
) -> Path | None:
    """Return the explicitly configured US quote snapshot cache path, if any."""

    source = os.environ if env is None else env
    for env_key in US_QUOTE_SNAPSHOT_CACHE_ENV_KEYS:
        configured = str(source.get(env_key, "") or "").strip()
        if configured:
            return Path(configured)
    return None


__all__ = [
    "US_QUOTE_SNAPSHOT_CACHE_ENV_KEYS",
    "get_configured_us_quote_snapshot_cache_path",
]
