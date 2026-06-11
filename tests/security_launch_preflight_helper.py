# -*- coding: utf-8 -*-
"""Test-only launch preflight helpers for security readiness coverage."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re
from unittest.mock import patch

from fastapi import HTTPException

from api.deps import CurrentUser
from api.deps import require_admin_capability
from api.v1.endpoints import auth as auth_endpoint
from src.admin_rbac import (
    ADMIN_RBAC_CAPABILITIES,
    ADMIN_RBAC_ROLE_CAPABILITIES,
    ADMIN_ROLE_ASSIGNMENT_REQUIRED_CAPABILITY,
    SUPPORT_ADMIN_ROLE,
    build_admin_role_assignment_preflight,
    expand_admin_capabilities,
    is_coarse_admin_fallback_enabled,
)
from src.multi_user import ROLE_ADMIN

PUBLIC_LAUNCH_ADMIN_RBAC_ENDPOINT_FILES = (
    "agent.py",
    "admin_cost.py",
    "admin_logs.py",
    "admin_notifications.py",
    "admin_portfolio.py",
    "admin_provider_circuits.py",
    "admin_security.py",
    "scanner.py",
    "system_config.py",
    "usage.py",
)
FRONTEND_ROUTE_CAPABILITY_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "auth" / "frontend_route_capability_inventory.json"
)
FRONTEND_ADMIN_CAPABILITIES_SOURCE = (
    Path(__file__).resolve().parents[1] / "apps" / "dsa-web" / "src" / "utils" / "adminCapabilities.ts"
)

EXPECTED_PUBLIC_LAUNCH_ADMIN_ROUTE_CAPABILITY_COUNTS: dict[str, dict[str, int]] = {
    "agent.py": {"ops:notifications:write": 1},
    "admin_cost.py": {"cost:observability:read": 4},
    "admin_logs.py": {"ops:logs:read": 8, "ops:logs:write": 1},
    "admin_notifications.py": {"ops:notifications:read": 2, "ops:notifications:write": 5},
    "admin_portfolio.py": {"users:portfolio:read": 4},
    "admin_provider_circuits.py": {"ops:providers:read": 5},
    "admin_security.py": {"users:security:write": 1},
    "scanner.py": {"scanner:admin:read": 3},
    "system_config.py": {
        "ops:system_config:read": 3,
        "ops:system_config:write": 3,
        "ops:providers:write": 3,
    },
    "usage.py": {"cost:observability:read": 1},
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
_FORBIDDEN_OPERATOR_EVIDENCE_VALUES = (
    "raw-password",
    "raw-session-id",
    "raw-cookie",
    "raw-token",
    "totp-secret",
    "recovery-code",
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
    mfa_operator_acceptance_ready: bool
    mfa_operator_acceptance_evidence: dict[str, bool]
    break_glass_enabled_by_default: bool
    coarse_admin_fallback_present: bool
    coarse_admin_fallback_status: str
    coarse_admin_fallback_default_enabled: bool
    coarse_admin_fallback_disable_preflight_ready: bool
    coarse_admin_fallback_guarded_disable_switch_available: bool
    coarse_admin_fallback_production_switch_ready: bool
    coarse_admin_fallback_production_switch_status: str
    coarse_admin_fallback_switch_evidence: dict[str, bool]
    coarse_admin_fallback_staging_rehearsal_ready: bool
    coarse_admin_fallback_staging_rehearsal_evidence: dict[str, object]
    explicit_capability_grants_without_fallback: bool
    missing_capability_dependency_fail_closed: bool
    missing_admin_capabilities_fail_closed: bool
    missing_admin_capabilities_payload: dict
    public_launch_dependency_inventory_complete: bool
    public_launch_legacy_admin_route_dependencies: dict[str, tuple[str, ...]]
    role_management_runtime_api_present: bool
    role_management_ui_api_pending: bool
    role_assignment_requires_explicit_capability: bool
    role_assignment_invalid_inputs_fail_closed: bool
    role_assignment_self_escalation_blocked: bool
    role_assignment_audit_payload_sanitized: bool
    role_assignment_least_privilege_preserved: bool
    role_assignment_missing_payload_fail_closed: bool
    role_assignment_runtime_behavior_changed: bool
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


def _role_assignment_actor(*, capabilities: tuple[str, ...] = (), legacy_admin: bool = False) -> CurrentUser:
    return CurrentUser(
        user_id="launch-role-actor",
        username="launch-role-actor",
        display_name="Launch Role Actor",
        role=ROLE_ADMIN,
        is_admin=True,
        is_authenticated=True,
        transitional=False,
        auth_enabled=True,
        session_id="raw-session-id",
        legacy_admin=legacy_admin,
        admin_capabilities=capabilities,
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


def _frontend_admin_capability_gate_evidence() -> dict[str, bool]:
    fixture = json.loads(FRONTEND_ROUTE_CAPABILITY_FIXTURE.read_text(encoding="utf-8"))
    capability_source = FRONTEND_ADMIN_CAPABILITIES_SOURCE.read_text(encoding="utf-8")
    admin_routes = fixture.get("admin_surface_routes", [])
    capability_flags = {
        str(entry.get("capability_flag"))
        for entry in admin_routes
        if str(entry.get("capability_flag") or "").strip()
    }
    capability_labels = {
        str(entry.get("capability_label"))
        for entry in admin_routes
        if str(entry.get("capability_label") or "").strip()
    }
    route_prefixes = {
        str(entry.get("path") or "").split("/:")[0]
        for entry in admin_routes
    }

    return {
        "admin_gates_capability_based": bool(admin_routes)
        and all(flag in capability_source for flag in capability_flags)
        and all(label in capability_source for label in capability_labels)
        and all(prefix in capability_source for prefix in route_prefixes if prefix),
        "missing_capabilities_fail_closed": bool(capability_flags)
        and all(f"{flag}: false" in capability_source for flag in capability_flags)
        and "if (!currentUser?.isAdmin)" in capability_source
        and "return emptyFlags" in capability_source
        and "return false;" in capability_source,
    }


def _role_management_runtime_api_present() -> bool:
    endpoint_dir = Path(__file__).resolve().parents[1] / "api" / "v1" / "endpoints"
    route_text = "\n".join(path.read_text(encoding="utf-8") for path in endpoint_dir.glob("admin*.py"))
    forbidden_markers = (
        "assign_admin_role",
        "assign_role",
        "admin_user_roles",
        "role-capabilities",
        "role_assignments",
    )
    return any(marker in route_text for marker in forbidden_markers)


def _role_assignment_denial_is_sanitized(result: dict) -> bool:
    payload = result.get("auditPayload", {})

    def _check(value) -> bool:
        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key).lower()
                if any(marker in key_text for marker in ("password", "token", "session", "cookie", "secret", "api_key", "apikey", "authorization")):
                    if item != "[redacted]":
                        return False
                elif not _check(item):
                    return False
            return True
        if isinstance(value, list):
            return all(_check(item) for item in value)
        return True

    control_text = str({key: value for key, value in result.items() if key != "auditPayload"}).lower()
    return _check(payload) and all(marker.lower() not in control_text for marker in _FORBIDDEN_DENIAL_MARKERS)


def _operator_evidence_is_sanitized(value: object) -> bool:
    text = str(value).lower()
    return all(marker.lower() not in text for marker in _FORBIDDEN_OPERATOR_EVIDENCE_VALUES)


def build_coarse_admin_fallback_disable_rehearsal_evidence() -> dict[str, object]:
    inventory = inventory_public_launch_admin_route_capabilities()
    frontend_gate_evidence = _frontend_admin_capability_gate_evidence()
    inventoried_capabilities = tuple(
        sorted({capability for counts in inventory.capability_counts.values() for capability in counts})
    )
    explicit_payloads_passed: list[str] = []
    legacy_payload_denials: list[bool] = []
    missing_payload_denials: list[bool] = []

    with patch.dict("os.environ", {"WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED": "false"}, clear=False):
        fallback_disabled_fail_closed = expand_admin_capabilities(_legacy_admin_user()) == set()
        for capability in inventoried_capabilities:
            explicit_user = CurrentUser(
                user_id=f"explicit-{capability}",
                username="explicit-admin",
                display_name="Explicit Admin",
                role=ROLE_ADMIN,
                is_admin=True,
                is_authenticated=True,
                transitional=False,
                auth_enabled=True,
                session_id="raw-session-id",
                legacy_admin=False,
                admin_capabilities=(capability,),
            )
            if require_admin_capability(capability)(explicit_user) is explicit_user:
                explicit_payloads_passed.append(capability)
            for user, results in (
                (_legacy_admin_user(), legacy_payload_denials),
                (_missing_capability_admin(), missing_payload_denials),
            ):
                try:
                    require_admin_capability(capability)(user)
                    results.append(False)
                except HTTPException as exc:
                    results.append(
                        exc.status_code == 403
                        and exc.detail.get("error") == "admin_capability_required"
                        and _denial_is_sanitized(exc)
                    )

        role_assignment_audit_payload = build_admin_role_assignment_preflight(
            actor=_role_assignment_actor(capabilities=(ADMIN_ROLE_ASSIGNMENT_REQUIRED_CAPABILITY,)),
            target_user_id="target-admin",
            role_key=SUPPORT_ADMIN_ROLE,
            capabilities=ADMIN_RBAC_ROLE_CAPABILITIES[SUPPORT_ADMIN_ROLE],
            audit_payload={
                "reason": "staging-rehearsal-ticket",
                "password": "raw-password",
                "session_id": "raw-session-id",
                "cookie": "raw-cookie",
                "api_token": "raw-token",
            },
        )

    with patch.dict("os.environ", {}, clear=True):
        default_enabled_without_explicit_config = is_coarse_admin_fallback_enabled()

    return {
        "fallback_disabled_fail_closed": fallback_disabled_fail_closed,
        "explicit_capability_payloads_passed": tuple(explicit_payloads_passed),
        "legacy_payloads_fail_closed": bool(legacy_payload_denials) and all(legacy_payload_denials),
        "missing_payloads_fail_closed": bool(missing_payload_denials) and all(missing_payload_denials),
        "denial_details_sanitized": all(legacy_payload_denials + missing_payload_denials),
        "audit_payload_sanitized": _role_assignment_denial_is_sanitized(role_assignment_audit_payload),
        "public_launch_inventory_complete": inventory.capability_counts
        == EXPECTED_PUBLIC_LAUNCH_ADMIN_ROUTE_CAPABILITY_COUNTS,
        "public_launch_routes_without_legacy_admin_dependencies": not inventory.legacy_admin_dependencies,
        "backend_admin_routes_explicit_capability_classified": inventory.capability_counts
        == EXPECTED_PUBLIC_LAUNCH_ADMIN_ROUTE_CAPABILITY_COUNTS
        and not inventory.legacy_admin_dependencies,
        "frontend_admin_gates_capability_based": frontend_gate_evidence["admin_gates_capability_based"],
        "frontend_admin_missing_capabilities_fail_closed": frontend_gate_evidence["missing_capabilities_fail_closed"],
        "operator_pilot_evidence_path": "security_operator_acceptance",
        "public_launch_approved": False,
        "default_enabled_without_explicit_config": default_enabled_without_explicit_config,
        "runtime_default_changed": False,
    }


def _expected_public_launch_rehearsal_capabilities() -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                capability
                for counts in EXPECTED_PUBLIC_LAUNCH_ADMIN_ROUTE_CAPABILITY_COUNTS.values()
                for capability in counts
            }
        )
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
    mfa_operator_acceptance_evidence = {
        "admin_only_scope_recorded": mfa_pilot_scope == "admin_only",
        "unsupported_global_rollout_no_go": mfa_unsupported_scope_fails_closed,
        "break_glass_disabled_by_default": not break_glass_default,
        "runtime_default_changed": False,
        "secret_evidence_redacted": _operator_evidence_is_sanitized(
            {
                "password": "[redacted]",
                "session_id": "[redacted]",
                "totp_secret": "[redacted]",
                "recovery_code": "[redacted]",
                "token": "[redacted]",
                "cookie": "[redacted]",
            }
        ),
    }
    mfa_operator_acceptance_ready = (
        mfa_operator_acceptance_evidence["admin_only_scope_recorded"]
        and mfa_operator_acceptance_evidence["unsupported_global_rollout_no_go"]
        and mfa_operator_acceptance_evidence["break_glass_disabled_by_default"]
        and not mfa_operator_acceptance_evidence["runtime_default_changed"]
        and mfa_operator_acceptance_evidence["secret_evidence_redacted"]
    )

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
    staging_rehearsal_evidence = build_coarse_admin_fallback_disable_rehearsal_evidence()
    staging_rehearsal_ready = bool(
        staging_rehearsal_evidence["fallback_disabled_fail_closed"]
        and tuple(staging_rehearsal_evidence["explicit_capability_payloads_passed"])
        == _expected_public_launch_rehearsal_capabilities()
        and staging_rehearsal_evidence["legacy_payloads_fail_closed"]
        and staging_rehearsal_evidence["missing_payloads_fail_closed"]
        and staging_rehearsal_evidence["denial_details_sanitized"]
        and staging_rehearsal_evidence["audit_payload_sanitized"]
        and staging_rehearsal_evidence["public_launch_inventory_complete"]
        and staging_rehearsal_evidence["public_launch_routes_without_legacy_admin_dependencies"]
        and staging_rehearsal_evidence["backend_admin_routes_explicit_capability_classified"]
        and staging_rehearsal_evidence["frontend_admin_gates_capability_based"]
        and staging_rehearsal_evidence["frontend_admin_missing_capabilities_fail_closed"]
        and not staging_rehearsal_evidence["public_launch_approved"]
        and staging_rehearsal_evidence["default_enabled_without_explicit_config"]
        and not staging_rehearsal_evidence["runtime_default_changed"]
    )
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
    role_api_present = _role_management_runtime_api_present()
    role_assignment_legacy_denied = build_admin_role_assignment_preflight(
        actor=_role_assignment_actor(legacy_admin=True),
        target_user_id="target-admin",
        role_key=SUPPORT_ADMIN_ROLE,
        capabilities=ADMIN_RBAC_ROLE_CAPABILITIES[SUPPORT_ADMIN_ROLE],
    )
    role_assignment_explicit_allowed = build_admin_role_assignment_preflight(
        actor=_role_assignment_actor(capabilities=(ADMIN_ROLE_ASSIGNMENT_REQUIRED_CAPABILITY,)),
        target_user_id="target-admin",
        role_key=SUPPORT_ADMIN_ROLE,
        capabilities=ADMIN_RBAC_ROLE_CAPABILITIES[SUPPORT_ADMIN_ROLE],
    )
    role_assignment_unknown_role = build_admin_role_assignment_preflight(
        actor=_role_assignment_actor(capabilities=(ADMIN_ROLE_ASSIGNMENT_REQUIRED_CAPABILITY,)),
        target_user_id="target-admin",
        role_key="owner-admin",
        capabilities=("users:read",),
    )
    role_assignment_bad_capability = build_admin_role_assignment_preflight(
        actor=_role_assignment_actor(capabilities=(ADMIN_ROLE_ASSIGNMENT_REQUIRED_CAPABILITY,)),
        target_user_id="target-admin",
        role_key=SUPPORT_ADMIN_ROLE,
        capabilities=("users:read", "secrets:read"),
    )
    role_assignment_self = build_admin_role_assignment_preflight(
        actor=_role_assignment_actor(capabilities=(ADMIN_ROLE_ASSIGNMENT_REQUIRED_CAPABILITY,)),
        target_user_id="launch-role-actor",
        role_key=SUPPORT_ADMIN_ROLE,
        capabilities=ADMIN_RBAC_ROLE_CAPABILITIES[SUPPORT_ADMIN_ROLE],
    )
    role_assignment_least_privilege = build_admin_role_assignment_preflight(
        actor=_role_assignment_actor(capabilities=("users:read",)),
        target_user_id="target-admin",
        role_key=SUPPORT_ADMIN_ROLE,
        capabilities=ADMIN_RBAC_ROLE_CAPABILITIES[SUPPORT_ADMIN_ROLE],
    )
    role_assignment_missing_payload = build_admin_role_assignment_preflight(
        actor=_role_assignment_actor(),
        target_user_id="target-admin",
        role_key=SUPPORT_ADMIN_ROLE,
        capabilities=ADMIN_RBAC_ROLE_CAPABILITIES[SUPPORT_ADMIN_ROLE],
    )
    role_assignment_audit_payload = build_admin_role_assignment_preflight(
        actor=_role_assignment_actor(capabilities=(ADMIN_ROLE_ASSIGNMENT_REQUIRED_CAPABILITY,)),
        target_user_id="target-admin",
        role_key=SUPPORT_ADMIN_ROLE,
        capabilities=ADMIN_RBAC_ROLE_CAPABILITIES[SUPPORT_ADMIN_ROLE],
        audit_payload={
            "reason": "launch-readiness-ticket",
            "password": "raw-password",
            "session_id": "raw-session-id",
            "cookie": "raw-cookie",
            "api_token": "raw-token",
        },
    )

    return SecurityLaunchPreflight(
        mfa_enforcement_enabled_by_default=mfa_default,
        mfa_pilot_scope=mfa_pilot_scope,
        mfa_unsupported_scope_fails_closed=mfa_unsupported_scope_fails_closed,
        mfa_operator_acceptance_ready=mfa_operator_acceptance_ready,
        mfa_operator_acceptance_evidence=mfa_operator_acceptance_evidence,
        break_glass_enabled_by_default=break_glass_default,
        coarse_admin_fallback_present=coarse_fallback_present,
        coarse_admin_fallback_status="transitional" if coarse_fallback_present else "removed",
        coarse_admin_fallback_default_enabled=fallback_default_enabled,
        coarse_admin_fallback_disable_preflight_ready=coarse_fallback_disable_preflight_ready,
        coarse_admin_fallback_guarded_disable_switch_available=guarded_disable_switch_available,
        coarse_admin_fallback_production_switch_ready=production_switch_ready,
        coarse_admin_fallback_production_switch_status=production_switch_status,
        coarse_admin_fallback_switch_evidence=switch_evidence,
        coarse_admin_fallback_staging_rehearsal_ready=staging_rehearsal_ready,
        coarse_admin_fallback_staging_rehearsal_evidence=staging_rehearsal_evidence,
        explicit_capability_grants_without_fallback=explicit_capability_grants_work,
        missing_capability_dependency_fail_closed=missing_capability_dependency_fail_closed,
        missing_admin_capabilities_fail_closed=not payload.get("adminCapabilities") and all(
            value is False for value in flag_values
        ),
        missing_admin_capabilities_payload=payload,
        public_launch_dependency_inventory_complete=public_launch_dependency_inventory_complete,
        public_launch_legacy_admin_route_dependencies=inventory.legacy_admin_dependencies,
        role_management_runtime_api_present=role_api_present,
        role_management_ui_api_pending=not role_api_present,
        role_assignment_requires_explicit_capability=(
            not role_assignment_legacy_denied["allowed"]
            and role_assignment_legacy_denied["error"] == "admin_capability_required"
            and role_assignment_explicit_allowed["allowed"]
        ),
        role_assignment_invalid_inputs_fail_closed=(
            not role_assignment_unknown_role["allowed"]
            and role_assignment_unknown_role["error"] == "unknown_admin_role"
            and not role_assignment_bad_capability["allowed"]
            and role_assignment_bad_capability["error"] == "invalid_admin_capability"
        ),
        role_assignment_self_escalation_blocked=(
            not role_assignment_self["allowed"] and role_assignment_self["error"] == "self_assignment_blocked"
        ),
        role_assignment_audit_payload_sanitized=_role_assignment_denial_is_sanitized(role_assignment_audit_payload),
        role_assignment_least_privilege_preserved=(
            not role_assignment_least_privilege["allowed"]
            and role_assignment_least_privilege["error"] == "admin_capability_required"
        ),
        role_assignment_missing_payload_fail_closed=(
            not role_assignment_missing_payload["allowed"]
            and role_assignment_missing_payload["error"] == "admin_capability_required"
            and _role_assignment_denial_is_sanitized(role_assignment_missing_payload)
        ),
        role_assignment_runtime_behavior_changed=False,
        launch_blockers=tuple(blockers),
        rollback_safe_next_step="Set WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED=false only for the guarded "
        "production-disable path; do not delete the compatibility code until explicit role assignments, telemetry, "
        "MFA/reauth evidence, fail-closed browser proof, and rollback evidence are complete.",
    )
