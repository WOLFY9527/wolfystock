# -*- coding: utf-8 -*-
"""Test-only launch preflight helpers for security readiness coverage."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

from api.deps import CurrentUser
from api.v1.endpoints import auth as auth_endpoint
from src.admin_rbac import ADMIN_RBAC_CAPABILITIES, expand_admin_capabilities
from src.multi_user import ROLE_ADMIN


@dataclass(frozen=True)
class SecurityLaunchPreflight:
    mfa_enforcement_enabled_by_default: bool
    break_glass_enabled_by_default: bool
    coarse_admin_fallback_present: bool
    missing_admin_capabilities_fail_closed: bool
    missing_admin_capabilities_payload: dict
    launch_blockers: tuple[str, ...]
    rollback_safe_next_step: str


def _legacy_admin_user() -> CurrentUser:
    return CurrentUser(
        user_id="launch-preflight-admin",
        username="launch-preflight-admin",
        display_name="Launch Preflight Admin",
        role=ROLE_ADMIN,
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="raw-session-id",
    )


def _missing_capabilities_payload() -> dict:
    return auth_endpoint._current_user_response(
        id="launch-preflight-admin",
        username="launch-preflight-admin",
        displayName="Launch Preflight Admin",
        role=ROLE_ADMIN,
        isAdmin=True,
        isAuthenticated=True,
        transitional=False,
        authEnabled=True,
        legacyAdmin=False,
        adminCapabilities=[],
    ).model_dump(by_alias=True)


def build_security_launch_preflight() -> SecurityLaunchPreflight:
    """Return a test-only security launch readiness snapshot.

    This helper deliberately reports the current compatibility posture; it does
    not remove fallback or enable MFA.
    """
    with patch.dict(
        "os.environ",
        {
            "WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED": "",
            "WOLFYSTOCK_MFA_LOGIN_BREAK_GLASS_ENABLED": "",
        },
        clear=False,
    ):
        mfa_default = auth_endpoint._is_mfa_login_enforcement_enabled()
        break_glass_default = auth_endpoint._is_mfa_login_break_glass_enabled()

    payload = _missing_capabilities_payload()
    flag_values = [value for key, value in payload.items() if key.startswith("can")]
    coarse_fallback_present = set(expand_admin_capabilities(_legacy_admin_user())) == set(ADMIN_RBAC_CAPABILITIES)
    blockers = []
    if coarse_fallback_present:
        blockers.append("coarse_admin_fallback_present")
    if not payload.get("adminCapabilities") and not all(value is False for value in flag_values):
        blockers.append("missing_admin_capabilities_not_fail_closed")
    if mfa_default:
        blockers.append("mfa_login_enforcement_enabled_by_default")
    if break_glass_default:
        blockers.append("mfa_break_glass_enabled_by_default")

    return SecurityLaunchPreflight(
        mfa_enforcement_enabled_by_default=mfa_default,
        break_glass_enabled_by_default=break_glass_default,
        coarse_admin_fallback_present=coarse_fallback_present,
        missing_admin_capabilities_fail_closed=not payload.get("adminCapabilities") and all(
            value is False for value in flag_values
        ),
        missing_admin_capabilities_payload=payload,
        launch_blockers=tuple(blockers),
        rollback_safe_next_step="Do not remove coarse admin fallback until R5 inventory, observe-mode telemetry, "
        "explicit role assignments, MFA/reauth evidence, fail-closed browser proof, and rollback evidence are complete.",
    )
