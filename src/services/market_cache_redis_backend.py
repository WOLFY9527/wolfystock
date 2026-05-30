# -*- coding: utf-8 -*-
"""Disabled-by-default Redis/Valkey mirror backend for MarketCache."""

from __future__ import annotations

import hashlib
import importlib
import json
import logging
from typing import Any

from src.services.market_cache import (
    MarketCacheRemoteMirrorDispatcher,
    NullMarketCacheRemoteBackend,
)


logger = logging.getLogger(__name__)

DEFAULT_KEY_PREFIX = "marketcache:mirror"
DEFAULT_TIMEOUT_SECONDS = 0.2
DEFAULT_QUEUE_SIZE = 256


class RedisMarketCacheRemoteBackend:
    """Persist-only Redis/Valkey backend for JSON-safe MarketCache projections."""

    def __init__(self, client: Any, *, key_prefix: str = DEFAULT_KEY_PREFIX) -> None:
        self._client = client
        self._key_prefix = _normalize_key_prefix(key_prefix)

    @classmethod
    def from_url(cls, redis_url: str, *, timeout_seconds: float) -> "RedisMarketCacheRemoteBackend":
        redis_module = importlib.import_module("redis")
        redis_client_cls = getattr(redis_module, "Redis")
        client = redis_client_cls.from_url(
            redis_url,
            socket_connect_timeout=timeout_seconds,
            socket_timeout=timeout_seconds,
            retry_on_timeout=False,
            decode_responses=True,
        )
        return cls(client)

    def persist(self, key: str, document: dict) -> None:
        try:
            payload = json.dumps(
                document,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            self._client.set(self._storage_key(key), payload)
        except (TypeError, ValueError):
            logger.debug(
                "[RedisMarketCacheRemoteBackend] persist skipped key_hash=%s reason=invalid_json_projection",
                _safe_key_hash(key),
            )
        except Exception:
            logger.debug(
                "[RedisMarketCacheRemoteBackend] persist skipped key_hash=%s reason=client_error",
                _safe_key_hash(key),
            )

    def _storage_key(self, key: str) -> str:
        key_hash = hashlib.sha256(str(key).encode("utf-8")).hexdigest()
        return f"{self._key_prefix}:{key_hash}"


def build_market_cache_remote_backend_from_config(config: Any):
    """Build the disabled-by-default MarketCache remote backend from config."""

    backend_name = str(getattr(config, "market_cache_remote_backend", "disabled") or "disabled").strip().lower()
    if backend_name != "redis":
        return NullMarketCacheRemoteBackend()

    redis_url = str(getattr(config, "market_cache_remote_url", "") or "").strip()
    if not redis_url:
        logger.debug("[RedisMarketCacheRemoteBackend] disabled reason=missing_url")
        return NullMarketCacheRemoteBackend()

    timeout_seconds = _coerce_timeout_seconds(
        getattr(config, "market_cache_remote_timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    )
    queue_size = _coerce_queue_size(getattr(config, "market_cache_remote_queue_size", DEFAULT_QUEUE_SIZE))
    try:
        backend = RedisMarketCacheRemoteBackend.from_url(
            redis_url,
            timeout_seconds=timeout_seconds,
        )
    except (ImportError, ModuleNotFoundError, AttributeError):
        logger.debug("[RedisMarketCacheRemoteBackend] disabled reason=redis_client_unavailable")
        return NullMarketCacheRemoteBackend()
    except Exception:
        logger.debug("[RedisMarketCacheRemoteBackend] disabled reason=client_init_failed")
        return NullMarketCacheRemoteBackend()

    return MarketCacheRemoteMirrorDispatcher(backend, queue_size=queue_size)


def _normalize_key_prefix(key_prefix: str) -> str:
    prefix = str(key_prefix or DEFAULT_KEY_PREFIX).strip().strip(":")
    return prefix or DEFAULT_KEY_PREFIX


def _coerce_timeout_seconds(value: Any) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SECONDS
    if timeout < 0.001:
        return 0.001
    if timeout > 5.0:
        return 5.0
    return timeout


def _coerce_queue_size(value: Any) -> int:
    try:
        queue_size = int(value)
    except (TypeError, ValueError):
        return DEFAULT_QUEUE_SIZE
    return max(1, queue_size)


def _safe_key_hash(key: str) -> str:
    return hashlib.sha256(str(key).encode("utf-8")).hexdigest()[:12]
