# -*- coding: utf-8 -*-
"""Disabled-by-default cache adapter for authorized CN/HK connect-flow data.

This adapter only reads an explicitly configured local JSON cache. It never
calls external providers and never exposes credential or path values.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from src.services.cn_hk_flow_contracts import CnHkFlowProviderUnavailable


CN_HK_CONNECT_FLOW_PROVIDER_ENABLED_ENV = "CN_HK_CONNECT_FLOW_PROVIDER_ENABLED"
CN_HK_CONNECT_FLOW_CACHE_PATH_ENV = "CN_HK_CONNECT_FLOW_CACHE_PATH"


class AuthorizedCnHkConnectFlowCacheProvider:
    """Read a pre-authorized CN/HK connect-flow cache payload when enabled."""

    def __init__(
        self,
        *,
        env: Mapping[str, str] | None = None,
        file_loader: Callable[[Path], Any] | None = None,
    ) -> None:
        self._env = env if env is not None else os.environ
        self._file_loader = file_loader or self._load_json

    def __call__(self) -> Any:
        enabled_raw = _text(self._env.get(CN_HK_CONNECT_FLOW_PROVIDER_ENABLED_ENV))
        if not _env_bool(enabled_raw, default=False):
            raise CnHkFlowProviderUnavailable("disabled_provider")
        cache_path = _text(self._env.get(CN_HK_CONNECT_FLOW_CACHE_PATH_ENV))
        if not cache_path:
            raise CnHkFlowProviderUnavailable("missing_credentials")
        try:
            return self._file_loader(Path(cache_path))
        except CnHkFlowProviderUnavailable:
            raise
        except FileNotFoundError as exc:
            raise CnHkFlowProviderUnavailable("empty_payload") from exc
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            raise CnHkFlowProviderUnavailable("malformed_payload") from exc

    @staticmethod
    def _load_json(path: Path) -> Any:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)


def _env_bool(value: str, *, default: bool) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return default
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _text(value: Any) -> str:
    return str(value or "").strip()


__all__ = [
    "AuthorizedCnHkConnectFlowCacheProvider",
    "CN_HK_CONNECT_FLOW_CACHE_PATH_ENV",
    "CN_HK_CONNECT_FLOW_PROVIDER_ENABLED_ENV",
]
