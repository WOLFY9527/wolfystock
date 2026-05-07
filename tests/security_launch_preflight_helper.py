# -*- coding: utf-8 -*-
"""Test-only launch preflight helpers for security readiness coverage."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

from fastapi import HTTPException

from api.deps import CurrentUser
from api.deps import require_admin_capability
from api.v1.endpoints import auth as auth_endpoint
from src.admin_rbac import ADMIN_RBAC_CAPABILITIES, expand_admin_capabilities
from src.multi_user import ROLE_ADMIN


@dataclass(frozen=True)
class SecurityLaunchPreflight:
    mfa_enforcement_enabled_by_default: bool
    mfa_pilot_scope: str
    mfa_unsupported_scope_fails_closed: bool
    break_glass_enabled_by_default: bool
    coarse_admin_fallback_present: bool
    coarse_admin_fallback_status: str
    coarse_admin_fallback_disable_preflight_ready: bool
    explicit_capability_grants_without_fallback: bool
    missing_capability_dependency_fail_closed: bool
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
        legacy_admin=True,
    )


def _explicit_capability_admin() -> CurrentUser:
    return CurrentUser(
        user_id="launch-preflight-explicit-admin",
        username="launch-preflight-explicit-admin",
        display_name="Launch Preflight Explicit Admin",
        role=ROLE_ADMIN,
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="raw-session-id",
        legacy_admin=False,
        admin_capabilities=("users:read",),
    )


def _missing_capability_admin() -> CurrentUser:
    return CurrentUser(
        user_id="launch-preflight-missing-capabilities-admin",
        username="launch-preflight-missing-capabilities-admin",
        display_name="Launch Preflight Missing Capabilities Admin",
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
        mfa_pilot_scope = auth_endpoint._mfa_login_enforcement_policy_scope()

    with patch.dict(
        "os.environ",
        {
            "WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED": "true",
            "WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_SCOPE": "global",
        },
        clear=False,
    ):
        mfa_unsupported_scope_fails_closed = auth_endpoint._mfa_login_enforcement_policy_scope() == "unsupported"

    payload = _missing_capabilities_payload()
    flag_values = [value for key, value in payload.items() if key.startswith("can")]
    coarse_fallback_present = set(expand_admin_capabilities(_legacy_admin_user())) == set(ADMIN_RBAC_CAPABILITIES)
    explicit_capability_grants_work = require_admin_capability("users:read")(_explicit_capability_admin()) is not None
    with patch.dict("os.environ", {"WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED": "false"}, clear=False):
        coarse_fallback_disable_preflight_ready = (
            expand_admin_capabilities(_legacy_admin_user()) == set()
            and require_admin_capability("users:read")(_explicit_capability_admin()) is not None
        )
    try:
        require_admin_capability("users:read")(_missing_capability_admin())
        missing_capability_dependency_fail_closed = False
    except HTTPException as exc:
        missing_capability_dependency_fail_closed = (
            exc.status_code == 403 and exc.detail.get("error") == "admin_capability_required"
        )
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
        mfa_pilot_scope=mfa_pilot_scope,
        mfa_unsupported_scope_fails_closed=mfa_unsupported_scope_fails_closed,
        break_glass_enabled_by_default=break_glass_default,
        coarse_admin_fallback_present=coarse_fallback_present,
        coarse_admin_fallback_status="transitional" if coarse_fallback_present else "removed",
        coarse_admin_fallback_disable_preflight_ready=coarse_fallback_disable_preflight_ready,
        explicit_capability_grants_without_fallback=explicit_capability_grants_work,
        missing_capability_dependency_fail_closed=missing_capability_dependency_fail_closed,
        missing_admin_capabilities_fail_closed=not payload.get("adminCapabilities") and all(
            value is False for value in flag_values
        ),
        missing_admin_capabilities_payload=payload,
        launch_blockers=tuple(blockers),
        rollback_safe_next_step="Do not remove coarse admin fallback until R5 inventory, observe-mode telemetry, "
        "explicit role assignments, MFA/reauth evidence, fail-closed browser proof, and rollback evidence are complete.",
    )
