# -*- coding: utf-8 -*-
"""Import-boundary contracts for the MarketCache module singleton."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MARKET_CACHE_ENV_KEYS = (
    "MARKET_CACHE_REMOTE_BACKEND",
    "MARKET_CACHE_REMOTE_URL",
    "MARKET_CACHE_REMOTE_TIMEOUT_SECONDS",
    "MARKET_CACHE_REMOTE_QUEUE_SIZE",
)


def _run_market_cache_subprocess(script: str, *, env_overrides: dict[str, str | None] | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    python_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(REPO_ROOT) if not python_path else f"{REPO_ROOT}{os.pathsep}{python_path}"
    for key in MARKET_CACHE_ENV_KEYS:
        env.pop(key, None)
    for key, value in (env_overrides or {}).items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value

    completed = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        pytest.fail(
            "MarketCache import-boundary probe failed\n"
            f"exit_code={completed.returncode}\n"
            f"stdout={completed.stdout}\n"
            f"stderr={completed.stderr}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            "MarketCache import-boundary probe returned invalid JSON\n"
            f"stdout={completed.stdout}\n"
            f"stderr={completed.stderr}\n"
            f"error={exc}"
        )


def test_module_import_is_config_free_and_does_not_construct_singleton() -> None:
    result = _run_market_cache_subprocess(
        """
        import builtins
        import json
        import sys

        blocked = []
        real_import = builtins.__import__

        def guarding_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "src.config" or name.startswith("src.config."):
                blocked.append(name)
                raise AssertionError(f"unexpected config import: {name}")
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = guarding_import
        try:
            import src.services.market_cache as market_cache_module
        finally:
            builtins.__import__ = real_import

        print(
            json.dumps(
                {
                    "blocked": blocked,
                    "config_loaded": "src.config" in sys.modules,
                    "singleton_is_none": market_cache_module._market_cache_singleton is None,
                    "proxy_type": type(market_cache_module.market_cache).__name__,
                    "market_cache_is_real_cache": isinstance(
                        market_cache_module.market_cache,
                        market_cache_module.MarketCache,
                    ),
                }
            )
        )
        """,
    )

    assert result["blocked"] == []
    assert result["config_loaded"] is False
    assert result["singleton_is_none"] is True
    assert result["proxy_type"] == "_MarketCacheProxy"
    assert result["market_cache_is_real_cache"] is False


def test_disabled_default_module_import_does_not_import_redis_or_valkey() -> None:
    result = _run_market_cache_subprocess(
        """
        import builtins
        import json
        import sys

        blocked = []
        real_import = builtins.__import__

        def guarding_import(name, globals=None, locals=None, fromlist=(), level=0):
            root = name.split(".", 1)[0]
            if root in {"redis", "valkey"}:
                blocked.append(name)
                raise AssertionError(f"unexpected import: {name}")
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = guarding_import
        try:
            import src.services.market_cache as market_cache_module
        finally:
            builtins.__import__ = real_import

        print(
            json.dumps(
                {
                    "blocked": blocked,
                    "redis_loaded": "redis" in sys.modules,
                    "valkey_loaded": "valkey" in sys.modules,
                    "singleton_is_none": market_cache_module._market_cache_singleton is None,
                }
            )
        )
        """,
        env_overrides={
            "MARKET_CACHE_REMOTE_BACKEND": "disabled",
            "MARKET_CACHE_REMOTE_URL": "",
        },
    )

    assert result["blocked"] == []
    assert result["redis_loaded"] is False
    assert result["valkey_loaded"] is False
    assert result["singleton_is_none"] is True


def test_env_set_before_first_access_deterministically_builds_lazy_singleton() -> None:
    result = _run_market_cache_subprocess(
        """
        import json
        import sys
        import types

        calls = []

        class FakeRedisClient:
            pass

        class FakeRedis:
            @classmethod
            def from_url(cls, url, **kwargs):
                calls.append({"url": url, "kwargs": kwargs})
                return FakeRedisClient()

        redis_module = types.ModuleType("redis")
        redis_module.Redis = FakeRedis
        sys.modules["redis"] = redis_module

        import src.services.market_cache as market_cache_module
        from src.config import get_config

        before_access_singleton_is_none = market_cache_module._market_cache_singleton is None
        cache = market_cache_module.get_market_cache()
        proxy_cache_backend_type = type(market_cache_module.market_cache._remote_backend).__name__
        remote_backend = cache._remote_backend
        print(
            json.dumps(
                {
                    "before_access_singleton_is_none": before_access_singleton_is_none,
                    "config_backend": get_config().market_cache_remote_backend,
                    "config_url": get_config().market_cache_remote_url,
                    "proxy_cache_backend_type": proxy_cache_backend_type,
                    "singleton_backend_type": type(remote_backend).__name__,
                    "inner_backend_type": type(getattr(remote_backend, "_backend", None)).__name__,
                    "redis_calls": calls,
                }
            )
        )
        """,
        env_overrides={
            "MARKET_CACHE_REMOTE_BACKEND": "redis",
            "MARKET_CACHE_REMOTE_URL": "redis://:secret@example.invalid:6379/0",
            "MARKET_CACHE_REMOTE_TIMEOUT_SECONDS": "0.35",
            "MARKET_CACHE_REMOTE_QUEUE_SIZE": "32",
        },
    )

    assert result["before_access_singleton_is_none"] is True
    assert result["config_backend"] == "redis"
    assert result["config_url"] == "redis://:secret@example.invalid:6379/0"
    assert result["proxy_cache_backend_type"] == "MarketCacheRemoteMirrorDispatcher"
    assert result["singleton_backend_type"] == "MarketCacheRemoteMirrorDispatcher"
    assert result["inner_backend_type"] == "RedisMarketCacheRemoteBackend"
    assert result["redis_calls"] == [
        {
            "url": "redis://:secret@example.invalid:6379/0",
            "kwargs": {
                "socket_connect_timeout": 0.35,
                "socket_timeout": 0.35,
                "retry_on_timeout": False,
                "decode_responses": True,
            },
        }
    ]


def test_env_changes_after_import_do_not_silently_rebuild_singleton() -> None:
    result = _run_market_cache_subprocess(
        """
        import json
        import os
        import sys
        import types

        import src.services.market_cache as market_cache_module
        from src.config import get_config

        before_cache = market_cache_module.get_market_cache()
        before_config = get_config()
        redis_calls = []

        class FakeRedisClient:
            pass

        class FakeRedis:
            @classmethod
            def from_url(cls, url, **kwargs):
                redis_calls.append({"url": url, "kwargs": kwargs})
                return FakeRedisClient()

        redis_module = types.ModuleType("redis")
        redis_module.Redis = FakeRedis
        sys.modules["redis"] = redis_module
        os.environ["MARKET_CACHE_REMOTE_BACKEND"] = "redis"
        os.environ["MARKET_CACHE_REMOTE_URL"] = "redis://:secret@example.invalid:6379/0"

        after_cache = market_cache_module.get_market_cache()
        after_config = get_config()

        print(
            json.dumps(
                {
                    "same_cache_object": before_cache is after_cache,
                    "same_config_object": before_config is after_config,
                    "before_backend_type": type(before_cache._remote_backend).__name__,
                    "after_backend_type": type(after_cache._remote_backend).__name__,
                    "config_backend_before": before_config.market_cache_remote_backend,
                    "config_backend_after": after_config.market_cache_remote_backend,
                    "redis_calls": redis_calls,
                }
            )
        )
        """,
        env_overrides={
            "MARKET_CACHE_REMOTE_BACKEND": "disabled",
            "MARKET_CACHE_REMOTE_URL": "",
        },
    )

    assert result["same_cache_object"] is True
    assert result["same_config_object"] is True
    assert result["before_backend_type"] == "NullMarketCacheRemoteBackend"
    assert result["after_backend_type"] == "NullMarketCacheRemoteBackend"
    assert result["config_backend_before"] == "disabled"
    assert result["config_backend_after"] == "disabled"
    assert result["redis_calls"] == []


def test_reset_market_cache_for_tests_resets_lazy_singleton_state() -> None:
    result = _run_market_cache_subprocess(
        """
        import json
        import os
        import sys
        import types

        calls = []

        class FakeRedisClient:
            pass

        class FakeRedis:
            @classmethod
            def from_url(cls, url, **kwargs):
                calls.append({"url": url, "kwargs": kwargs})
                return FakeRedisClient()

        import src.services.market_cache as market_cache_module
        from src.config import Config

        first_cache = market_cache_module.get_market_cache()

        redis_module = types.ModuleType("redis")
        redis_module.Redis = FakeRedis
        sys.modules["redis"] = redis_module
        os.environ["MARKET_CACHE_REMOTE_BACKEND"] = "redis"
        os.environ["MARKET_CACHE_REMOTE_URL"] = "redis://:secret@example.invalid:6379/0"
        Config.reset_instance()
        market_cache_module.reset_market_cache_for_tests()

        second_cache = market_cache_module.get_market_cache()
        print(
            json.dumps(
                {
                    "same_cache_object": first_cache is second_cache,
                    "first_backend_type": type(first_cache._remote_backend).__name__,
                    "second_backend_type": type(second_cache._remote_backend).__name__,
                    "second_inner_backend_type": type(getattr(second_cache._remote_backend, "_backend", None)).__name__,
                    "redis_calls": calls,
                }
            )
        )
        """,
        env_overrides={
            "MARKET_CACHE_REMOTE_BACKEND": "disabled",
            "MARKET_CACHE_REMOTE_URL": "",
        },
    )

    assert result["same_cache_object"] is False
    assert result["first_backend_type"] == "NullMarketCacheRemoteBackend"
    assert result["second_backend_type"] == "MarketCacheRemoteMirrorDispatcher"
    assert result["second_inner_backend_type"] == "RedisMarketCacheRemoteBackend"
    assert result["redis_calls"] == [
        {
            "url": "redis://:secret@example.invalid:6379/0",
            "kwargs": {
                "socket_connect_timeout": 0.2,
                "socket_timeout": 0.2,
                "retry_on_timeout": False,
                "decode_responses": True,
            },
        }
    ]


def test_direct_market_cache_constructor_stays_local_and_skips_config_reads() -> None:
    from src.services.market_cache import MarketCache, NullMarketCacheRemoteBackend

    with patch("src.config.get_config", side_effect=AssertionError("direct MarketCache() must not read config")):
        cache = MarketCache(max_workers=1)

    assert isinstance(cache._remote_backend, NullMarketCacheRemoteBackend)


def test_existing_consumers_keep_default_local_null_singleton_semantics() -> None:
    result = _run_market_cache_subprocess(
        """
        import builtins
        import json
        import sys

        blocked = []
        real_import = builtins.__import__

        def guarding_import(name, globals=None, locals=None, fromlist=(), level=0):
            root = name.split(".", 1)[0]
            if root in {"redis", "valkey"}:
                blocked.append(name)
                raise AssertionError(f"unexpected import: {name}")
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = guarding_import
        try:
            from src.services.market_overview_service import MarketOverviewService
            from src.services.market_cache import market_cache
        finally:
            builtins.__import__ = real_import

        entry = market_cache.set("crypto", {"source": "test", "value": 1}, ttl_seconds=30)
        payload = MarketOverviewService._market_cache.get_or_refresh(
            "crypto",
            30,
            lambda: {"source": "unexpected", "value": 2},
        )
        print(
            json.dumps(
                {
                    "same_cache_object": MarketOverviewService._market_cache is market_cache,
                    "backend_type": type(market_cache._remote_backend).__name__,
                    "entry_value": entry.data["value"],
                    "payload_value": payload["value"],
                    "blocked": blocked,
                    "redis_loaded": "redis" in sys.modules,
                    "valkey_loaded": "valkey" in sys.modules,
                }
            )
        )
        """,
        env_overrides={
            "MARKET_CACHE_REMOTE_BACKEND": "disabled",
            "MARKET_CACHE_REMOTE_URL": "",
        },
    )

    assert result["same_cache_object"] is True
    assert result["backend_type"] == "NullMarketCacheRemoteBackend"
    assert result["entry_value"] == 1
    assert result["payload_value"] == 1
    assert result["blocked"] == []
    assert result["redis_loaded"] is False
    assert result["valkey_loaded"] is False
