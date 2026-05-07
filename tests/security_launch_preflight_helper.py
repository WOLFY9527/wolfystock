# -*- coding: utf-8 -*-
"""Test-only launch preflight helpers for security readiness coverage."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re
from unittest.mock import patch

from fastapi import HTTPException

from api.deps import CurrentUser
from api.deps import require_admin_capability
from api.v1.endpoints import auth as auth_endpoint
from src.admin_rbac import ADMIN_RBAC_CAPABILITIES, expand_admin_capabilities, is_coarse_admin_fallback_enabled
from src.multi_user import ROLE_ADMIN

PUBLIC_LAUNCH_ADMIN_RBAC_ENDPOINT_FILES = (
    "admin_cost.py",
    "admin_logs.py",
    "admin_notifications.py",
    "admin_portfolio.py",
    "admin_provider_circuits.py",
    "admin_security.py",
    "system_config.py",
)

EXPECTED_PUBLIC_LAUNCH_ADMIN_ROUTE_CAPABILITY_COUNTS: dict[str, dict[str, int]] = {
    "admin_cost.py": {"cost:observability:read": 4},
    "admin_logs.py": {"ops:logs:read": 5, "ops:logs:write": 1},
    "admin_notifications.py": {"ops:notifications:read": 2, "ops:notifications:write": 5},
    "admin_portfolio.py": {"users:portfolio:read": 4},
    "admin_provider_circuits.py": {"ops:providers:read": 5},
    "admin_security.py": {"users:security:write": 1},
    "system_config.py": {
        "ops:system_config:read": 3,
        "ops:system_config:write": 3,
        "ops:providers:write": 3,
    },
}

_CAPABILITY_DEPENDENCY_PATTERN = re.compile(r"require_admin_capability\(\s*[\"']([^\"']+)[\"']\s*\)")
_LEGACY_ADMIN_DEPENDENCY_PATTERN = re.compile(r"Depends\(\s*require_admin_user\s*\)")
_FORBIDDEN_DENIAL_MARKERS = (
    "raw-session-id",
    "password",
    "cookie",
    "token",
    "api_key",
    "secret",
    ".env",
    "super-admin",
    "users:read",
)


@dataclass(frozen=True)
class AdminRouteCapabilityInventory:
    capability_counts: dict[str, dict[str, int]]
    legacy_admin_dependencies: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class SecurityLaunchPreflight:
    mfa_enforcement_enabled_by_default: bool
    mfa_pilot_scope: str
    mfa_unsupported_scope_fails_closed: bool
    break_glass_enabled_by_default: bool
    coarse_admin_fallback_present: bool
    coarse_admin_fallback_status: str
    coarse_admin_fallback_default_enabled: bool
    coarse_admin_fallback_disable_preflight_ready: bool
    coarse_admin_fallback_guarded_disable_switch_available: bool
    coarse_admin_fallback_production_switch_ready: bool
    coarse_admin_fallback_production_switch_status: str
    coarse_admin_fallback_switch_evidence: dict[str, bool]
    explicit_capability_grants_without_fallback: bool
    missing_capability_dependency_fail_closed: bool
    missing_admin_capabilities_fail_closed: bool
    missing_admin_capabilities_payload: dict
    public_launch_dependency_inventory_complete: bool
    public_launch_legacy_admin_route_dependencies: dict[str, tuple[str, ...]]
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


def _denial_is_sanitized(exc: HTTPException) -> bool:
    text = str(exc.detail).lower()
    return all(marker.lower() not in text for marker in _FORBIDDEN_DENIAL_MARKERS)


def inventory_public_launch_admin_route_capabilities() -> AdminRouteCapabilityInventory:
    endpoint_dir = Path(__file__).resolve().parents[1] / "api" / "v1" / "endpoints"
    capability_counts: dict[str, dict[str, int]] = {}
    legacy_admin_dependencies: dict[str, tuple[str, ...]] = {}

    for filename in PUBLIC_LAUNCH_ADMIN_RBAC_ENDPOINT_FILES:
        text = (endpoint_dir / filename).read_text(encoding="utf-8")
        counted = Counter(_CAPABILITY_DEPENDENCY_PATTERN.findall(text))
        if counted:
            capability_counts[filename] = dict(sorted(counted.items()))
        legacy_dependencies = tuple(sorted(set(_LEGACY_ADMIN_DEPENDENCY_PATTERN.findall(text))))
        if legacy_dependencies:
            legacy_admin_dependencies[filename] = legacy_dependencies

    return AdminRouteCapabilityInventory(
        capability_counts=capability_counts,
        legacy_admin_dependencies=legacy_admin_dependencies,
    )


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
    fallback_default_enabled = is_coarse_admin_fallback_enabled()
    explicit_capability_grants_work = require_admin_capability("users:read")(_explicit_capability_admin()) is not None
    legacy_admin_without_payload_denied_without_fallback = False
    missing_payload_without_fallback_fail_closed = False
    sanitized_denials_without_fallback = False
    with patch.dict("os.environ", {"WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED": "false"}, clear=False):
        explicit_capability_grants_without_fallback = (
            require_admin_capability("users:read")(_explicit_capability_admin()) is not None
        )
        fallback_disabled_fail_closed = expand_admin_capabilities(_legacy_admin_user()) == set()
        denial_checks = []
        try:
            require_admin_capability("users:read")(_legacy_admin_user())
        except HTTPException as exc:
            legacy_admin_without_payload_denied_without_fallback = (
                exc.status_code == 403 and exc.detail.get("error") == "admin_capability_required"
            )
            denial_checks.append(_denial_is_sanitized(exc))
        try:
            require_admin_capability("users:read")(_missing_capability_admin())
        except HTTPException as exc:
            missing_payload_without_fallback_fail_closed = (
                exc.status_code == 403 and exc.detail.get("error") == "admin_capability_required"
            )
            denial_checks.append(_denial_is_sanitized(exc))
        sanitized_denials_without_fallback = bool(denial_checks) and all(denial_checks)

    inventory = inventory_public_launch_admin_route_capabilities()
    public_launch_dependency_inventory_complete = (
        inventory.capability_counts == EXPECTED_PUBLIC_LAUNCH_ADMIN_ROUTE_CAPABILITY_COUNTS
        and not inventory.legacy_admin_dependencies
    )
    coarse_fallback_disable_preflight_ready = (
        fallback_disabled_fail_closed
        and explicit_capability_grants_without_fallback
        and legacy_admin_without_payload_denied_without_fallback
        and missing_payload_without_fallback_fail_closed
        and sanitized_denials_without_fallback
    )
    try:
        require_admin_capability("users:read")(_missing_capability_admin())
        missing_capability_dependency_fail_closed = False
    except HTTPException as exc:
        missing_capability_dependency_fail_closed = (
            exc.status_code == 403 and exc.detail.get("error") == "admin_capability_required"
        )
    switch_evidence = {
        "fallback_default_enabled": fallback_default_enabled,
        "fallback_disabled_fail_closed": fallback_disabled_fail_closed,
        "explicit_capability_payloads_without_fallback": explicit_capability_grants_without_fallback,
        "legacy_admin_without_payload_denied_without_fallback": legacy_admin_without_payload_denied_without_fallback,
        "missing_payload_without_fallback_fail_closed": missing_payload_without_fallback_fail_closed,
        "sanitized_denials_without_fallback": sanitized_denials_without_fallback,
        "public_launch_dependency_inventory_complete": public_launch_dependency_inventory_complete,
        "runtime_default_changed": False,
    }
    guarded_disable_switch_available = (
        coarse_fallback_disable_preflight_ready and public_launch_dependency_inventory_complete
    )
    switch_evidence["guarded_disable_switch_available"] = guarded_disable_switch_available
    blockers = []
    if fallback_default_enabled and guarded_disable_switch_available:
        blockers.append("coarse_admin_fallback_default_enabled_until_switch_applied")
    elif coarse_fallback_present:
        blockers.append("coarse_admin_fallback_present")
    if not public_launch_dependency_inventory_complete:
        blockers.append("admin_route_capability_dependency_gap")
    if not payload.get("adminCapabilities") and not all(value is False for value in flag_values):
        blockers.append("missing_admin_capabilities_not_fail_closed")
    if mfa_default:
        blockers.append("mfa_login_enforcement_enabled_by_default")
    if break_glass_default:
        blockers.append("mfa_break_glass_enabled_by_default")
    production_switch_ready = guarded_disable_switch_available
    production_switch_status = "guarded_disable_available" if production_switch_ready else "blocked"

    return SecurityLaunchPreflight(
        mfa_enforcement_enabled_by_default=mfa_default,
        mfa_pilot_scope=mfa_pilot_scope,
        mfa_unsupported_scope_fails_closed=mfa_unsupported_scope_fails_closed,
        break_glass_enabled_by_default=break_glass_default,
        coarse_admin_fallback_present=coarse_fallback_present,
        coarse_admin_fallback_status="transitional" if coarse_fallback_present else "removed",
        coarse_admin_fallback_default_enabled=fallback_default_enabled,
        coarse_admin_fallback_disable_preflight_ready=coarse_fallback_disable_preflight_ready,
        coarse_admin_fallback_guarded_disable_switch_available=guarded_disable_switch_available,
        coarse_admin_fallback_production_switch_ready=production_switch_ready,
        coarse_admin_fallback_production_switch_status=production_switch_status,
        coarse_admin_fallback_switch_evidence=switch_evidence,
        explicit_capability_grants_without_fallback=explicit_capability_grants_work,
        missing_capability_dependency_fail_closed=missing_capability_dependency_fail_closed,
        missing_admin_capabilities_fail_closed=not payload.get("adminCapabilities") and all(
            value is False for value in flag_values
        ),
        missing_admin_capabilities_payload=payload,
        public_launch_dependency_inventory_complete=public_launch_dependency_inventory_complete,
        public_launch_legacy_admin_route_dependencies=inventory.legacy_admin_dependencies,
        launch_blockers=tuple(blockers),
        rollback_safe_next_step="Set WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED=false only for the guarded "
        "production-disable path; do not delete the compatibility code until explicit role assignments, telemetry, "
        "MFA/reauth evidence, fail-closed browser proof, and rollback evidence are complete.",
    )
