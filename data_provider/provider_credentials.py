# -*- coding: utf-8 -*-
"""Lightweight provider credential helpers for market-data integrations."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional, Sequence, Tuple

from src.config import Config, get_config


def _coerce_non_empty(value: object) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _get_config_raw(config: object, attr_name: str) -> object:
    if isinstance(config, Mapping):
        for candidate in (attr_name, attr_name.upper(), attr_name.lower()):
            if candidate in config:
                return config[candidate]
        return None
    for candidate in (attr_name, attr_name.upper(), attr_name.lower()):
        if hasattr(config, candidate):
            return getattr(config, candidate)
    return None


def _collect_non_empty_strings(config: object, attr_names: Sequence[str]) -> Tuple[str, ...]:
    values: list[str] = []
    for attr_name in attr_names:
        raw_value = _get_config_raw(config, attr_name)
        if isinstance(raw_value, (list, tuple)):
            for item in raw_value:
                token = _coerce_non_empty(item)
                if token:
                    values.append(token)
        else:
            token = _coerce_non_empty(raw_value)
            if token:
                values.append(token)
    deduped: list[str] = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return tuple(deduped)


def _infer_alpaca_credential_source(
    config: object,
    *,
    key_id: Optional[str],
    secret_key: Optional[str],
) -> str:
    env_names = ("ALPACA_API_KEY_ID", "ALPACA_API_SECRET_KEY")
    if isinstance(config, Mapping):
        normalized_keys = {str(key).upper() for key in config.keys()}
        if any(name in normalized_keys for name in env_names):
            return "control_plane"
        return "config" if (key_id or secret_key) else "unknown"
    if any(_coerce_non_empty(os.getenv(name)) for name in env_names):
        return "env"
    if key_id or secret_key:
        return "config"
    return "unavailable"


def _infer_twelve_data_credential_source(
    config: object,
    *,
    api_keys: Tuple[str, ...],
) -> str:
    env_names = ("TWELVE_DATA_API_KEY", "TWELVE_DATA_API_KEYS")
    if isinstance(config, Mapping):
        normalized_keys = {str(key).upper() for key in config.keys()}
        if any(name in normalized_keys for name in env_names):
            return "control_plane"
        return "config" if api_keys else "unknown"
    if any(_coerce_non_empty(os.getenv(name)) for name in env_names):
        return "env"
    if api_keys:
        return "config"
    return "unavailable"


@dataclass(frozen=True)
class ProviderCredentialBundle:
    """Normalized provider credential payload."""

    provider: str
    auth_mode: str
    api_keys: Tuple[str, ...] = ()
    key_id: Optional[str] = None
    secret_key: Optional[str] = None
    extras: Dict[str, str] = field(default_factory=dict)
    credential_source: str = "unknown"

    @property
    def primary_api_key(self) -> Optional[str]:
        return self.api_keys[0] if self.api_keys else None

    @property
    def is_configured(self) -> bool:
        if self.auth_mode == "single_key":
            return bool(self.primary_api_key)
        if self.auth_mode == "key_secret":
            return bool(self.key_id and self.secret_key)
        return False

    @property
    def is_partial(self) -> bool:
        if self.auth_mode != "key_secret":
            return False
        return bool(self.key_id or self.secret_key) and not self.is_configured

    @property
    def missing_fields(self) -> Tuple[str, ...]:
        if self.auth_mode == "single_key":
            return ("api_key",) if not self.primary_api_key else ()
        if self.auth_mode == "key_secret":
            missing: list[str] = []
            if not self.key_id:
                missing.append("key_id")
            if not self.secret_key:
                missing.append("secret_key")
            return tuple(missing)
        return ()


def get_provider_credentials(
    provider: str,
    *,
    config: Optional[Config | Mapping[str, object]] = None,
) -> ProviderCredentialBundle:
    """Resolve provider credentials from the current config."""

    normalized = str(provider or "").strip().lower()
    config_obj: object = config if config is not None else get_config()

    if normalized in {"twelve_data", "twelvedata"}:
        api_keys = _collect_non_empty_strings(
            config_obj,
            (
                "twelve_data_api_keys",
                "twelve_data_api_key",
                "TWELVE_DATA_API_KEYS",
                "TWELVE_DATA_API_KEY",
            ),
        )
        return ProviderCredentialBundle(
            provider="twelve_data",
            auth_mode="single_key",
            api_keys=api_keys,
            credential_source=_infer_twelve_data_credential_source(
                config_obj,
                api_keys=api_keys,
            ),
        )

    if normalized == "alpaca":
        key_id = _coerce_non_empty(_get_config_raw(config_obj, "alpaca_api_key_id"))
        secret_key = _coerce_non_empty(_get_config_raw(config_obj, "alpaca_api_secret_key"))
        data_feed = _coerce_non_empty(_get_config_raw(config_obj, "alpaca_data_feed")) or "iex"
        return ProviderCredentialBundle(
            provider="alpaca",
            auth_mode="key_secret",
            key_id=key_id,
            secret_key=secret_key,
            extras={
                "data_feed": data_feed,
            },
            credential_source=_infer_alpaca_credential_source(
                config_obj,
                key_id=key_id,
                secret_key=secret_key,
            ),
        )

    raise ValueError(f"Unsupported provider credential lookup: {provider}")
