from __future__ import annotations

import os
import platform
from pathlib import Path

from .errors import EnvironmentFailure


def environment_cache_root(source: dict[str, str] | None = None) -> Path:
    environment = os.environ if source is None else source
    override = environment.get("WOLFYSTOCK_ENV_CACHE")
    if override:
        candidate = Path(override).expanduser()
        if not candidate.is_absolute():
            raise EnvironmentFailure("cache_override_not_absolute", "WOLFYSTOCK_ENV_CACHE must be absolute")
        return candidate.resolve(strict=False)
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Caches" / "WolfyStock" / "environment-v1"
    if system == "Windows":
        base = environment.get("LOCALAPPDATA")
        if not base:
            raise EnvironmentFailure("local_app_data_missing", "LOCALAPPDATA is required on Windows")
        return Path(base) / "WolfyStock" / "environment-v1"
    base = Path(environment.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return base / "wolfystock" / "environment-v1"
