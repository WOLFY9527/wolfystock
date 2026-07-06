# -*- coding: utf-8 -*-
"""Lightweight UAT no-live-provider isolation boundary.

This module intentionally imports only stdlib so harness control-plane paths
can reuse the same contract without pulling provider/runtime dependencies.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


UAT_NO_LIVE_PROVIDERS_ENV = "WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS"
UAT_LIVE_PROVIDER_ALLOWLIST_ENV = "WOLFYSTOCK_UAT_LIVE_PROVIDER_ALLOWLIST"
_TRUTHY = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class UatProviderDispatch:
    provider: str
    capability: str
    route: str
    allowed: bool
    reason_code: str

    def to_trace(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "capability": self.capability,
            "route": self.route,
            "action": "allowed" if self.allowed else "blocked",
            "outcome": "ok" if self.allowed else "blocked",
            "status": "ok" if self.allowed else "blocked",
            "reason": self.reason_code,
            "message": (
                "UAT contract explicitly allowed provider dispatch."
                if self.allowed
                else "UAT no-live-provider mode blocked external provider dispatch."
            ),
        }


class UatProviderIsolationError(RuntimeError):
    """Raised when UAT no-live-provider mode blocks an external dispatch."""

    def __init__(self, dispatch: UatProviderDispatch) -> None:
        self.dispatch = dispatch
        super().__init__(
            f"UAT no-live-provider mode blocked {dispatch.provider}:{dispatch.capability}"
        )


def uat_no_live_providers_enabled(env: dict[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return str(source.get(UAT_NO_LIVE_PROVIDERS_ENV) or "").strip().lower() in _TRUTHY


def uat_live_provider_allowlist(env: dict[str, str] | None = None) -> set[str]:
    source = os.environ if env is None else env
    raw_value = str(source.get(UAT_LIVE_PROVIDER_ALLOWLIST_ENV) or "")
    return {
        token.strip().lower()
        for token in raw_value.split(",")
        if token.strip()
    }


def check_uat_provider_dispatch(
    *,
    provider: str,
    capability: str,
    route: str,
    env: dict[str, str] | None = None,
) -> UatProviderDispatch:
    normalized_provider = _safe_token(provider)
    normalized_capability = _safe_token(capability)
    normalized_route = _safe_token(route)
    if not uat_no_live_providers_enabled(env):
        return UatProviderDispatch(
            provider=normalized_provider,
            capability=normalized_capability,
            route=normalized_route,
            allowed=True,
            reason_code="uat_no_live_providers_disabled",
        )

    allowlist = uat_live_provider_allowlist(env)
    candidates = {
        normalized_provider,
        f"{normalized_provider}:{normalized_capability}",
        f"{normalized_provider}:{normalized_capability}:{normalized_route}",
    }
    if candidates & allowlist:
        return UatProviderDispatch(
            provider=normalized_provider,
            capability=normalized_capability,
            route=normalized_route,
            allowed=True,
            reason_code="uat_contract_allowlisted",
        )

    return UatProviderDispatch(
        provider=normalized_provider,
        capability=normalized_capability,
        route=normalized_route,
        allowed=False,
        reason_code="uat_no_live_providers",
    )


def require_uat_provider_dispatch_allowed(
    *,
    provider: str,
    capability: str,
    route: str,
    env: dict[str, str] | None = None,
) -> UatProviderDispatch:
    dispatch = check_uat_provider_dispatch(
        provider=provider,
        capability=capability,
        route=route,
        env=env,
    )
    if not dispatch.allowed:
        raise UatProviderIsolationError(dispatch)
    return dispatch


def _safe_token(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text or "unknown"
