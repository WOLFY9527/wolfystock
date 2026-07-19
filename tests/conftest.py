# -*- coding: utf-8 -*-
"""Shared pytest setup and process-state isolation."""

from __future__ import annotations

import copy
import os
import sys
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from tests.litellm_stub import ensure_litellm_stub


ensure_litellm_stub()


_AUTH_STATE_ATTRIBUTES = (
    "_auth_enabled",
    "_session_secret",
    "_password_hash_salt",
    "_password_hash_stored",
    "_password_hash_value",
    "_rate_limit",
    "_admin_reauth_markers",
    "_rate_limit_lock",
)


def _snapshot_attributes(module: Any, names: Iterable[str]) -> dict[str, tuple[Any, Any]] | None:
    if module is None:
        return None
    snapshot: dict[str, tuple[Any, Any]] = {}
    for name in names:
        value = getattr(module, name)
        snapshot[name] = (value, copy.deepcopy(value) if isinstance(value, dict) else value)
    return snapshot


def _restore_attributes(module: Any, snapshot: Mapping[str, tuple[Any, Any]]) -> None:
    for name, (original, saved_value) in snapshot.items():
        if isinstance(original, dict):
            original.clear()
            original.update(saved_value)
        setattr(module, name, original)


def _loaded_apps(extra_apps: Iterable[Any]) -> list[Any]:
    apps = list(extra_apps)
    app_module = sys.modules.get("api.app")
    canonical_app = getattr(app_module, "app", None) if app_module is not None else None
    if canonical_app is not None:
        apps.append(canonical_app)

    unique_apps: list[Any] = []
    seen: set[int] = set()
    for app in apps:
        if id(app) not in seen:
            seen.add(id(app))
            unique_apps.append(app)
    return unique_apps


def _snapshot_app_state(app: Any) -> tuple[dict[Any, Any], dict[str, Any]]:
    return dict(app.dependency_overrides), dict(app.state._state)


def _restore_app_state(app: Any, snapshot: tuple[dict[Any, Any], dict[str, Any]]) -> None:
    dependency_overrides, state = snapshot
    app.dependency_overrides.clear()
    app.dependency_overrides.update(dependency_overrides)
    app.state._state.clear()
    app.state._state.update(state)


@contextmanager
def preserve_runtime_test_state(*, apps: Iterable[Any] = ()) -> Iterator[None]:
    """Restore only the process-scoped owners exercised by canonical runtime tests."""

    environment = dict(os.environ)
    auth_module = sys.modules.get("src.auth")
    auth_state = _snapshot_attributes(auth_module, _AUTH_STATE_ATTRIBUTES)
    provider_module = sys.modules.get("src.services.rotation_radar_quote_provider")
    provider_state = _snapshot_attributes(provider_module, ("_UNAVAILABLE_SYMBOL_STATE",))
    config_module = sys.modules.get("src.config")
    config_class = getattr(config_module, "Config", None) if config_module is not None else None
    config_instance = getattr(config_class, "_instance", None) if config_class is not None else None
    app_states = [(app, _snapshot_app_state(app)) for app in _loaded_apps(apps)]

    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(environment)

        loaded_auth = sys.modules.get("src.auth")
        if auth_state is not None and loaded_auth is not None:
            _restore_attributes(loaded_auth, auth_state)
        elif loaded_auth is not None:
            for name in _AUTH_STATE_ATTRIBUTES:
                setattr(loaded_auth, name, {} if name in {"_rate_limit", "_admin_reauth_markers"} else None)

        loaded_provider = sys.modules.get("src.services.rotation_radar_quote_provider")
        if provider_state is not None and loaded_provider is not None:
            _restore_attributes(loaded_provider, provider_state)
        elif loaded_provider is not None:
            loaded_provider._UNAVAILABLE_SYMBOL_STATE.clear()

        loaded_config = sys.modules.get("src.config")
        loaded_config_class = getattr(loaded_config, "Config", None) if loaded_config is not None else None
        if loaded_config_class is not None:
            loaded_config_class._instance = config_instance

        for app, app_state in app_states:
            _restore_app_state(app, app_state)
