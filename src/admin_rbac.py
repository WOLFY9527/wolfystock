# -*- coding: utf-8 -*-
"""Read-only admin RBAC compatibility helpers for Phase R1."""

from __future__ import annotations

import os
from typing import Any

from src.multi_user import ROLE_ADMIN

SUPER_ADMIN_ROLE = "super-admin"
SECURITY_ADMIN_ROLE = "security-admin"
SUPPORT_ADMIN_ROLE = "support-admin"
OPS_ADMIN_ROLE = "ops-admin"

ADMIN_RBAC_ROLES = (
    SUPER_ADMIN_ROLE,
    SECURITY_ADMIN_ROLE,
    SUPPORT_ADMIN_ROLE,
    OPS_ADMIN_ROLE,
)

ADMIN_RBAC_CAPABILITIES = (
    "users:read",
    "users:activity:read",
    "users:portfolio:read",
    "users:security:read",
    "users:security:write",
    "admin_audit:read",
    "ops:logs:read",
    "ops:logs:write",
    "ops:providers:read",
    "ops:providers:write",
    "ops:notifications:read",
    "ops:notifications:write",
    "ops:system_config:read",
    "ops:system_config:write",
    "cost:observability:read",
    "scanner:admin:read",
    "backtest:admin:read",
    "options:admin:read",
    "quant:admin:read",
    "quant:admin:write",
)
ADMIN_ROLE_ASSIGNMENT_REQUIRED_CAPABILITY = "users:security:write"

ADMIN_RBAC_ROLE_CAPABILITIES: dict[str, tuple[str, ...]] = {
    SUPER_ADMIN_ROLE: ADMIN_RBAC_CAPABILITIES,
    SECURITY_ADMIN_ROLE: (
        "users:read",
        "users:activity:read",
        "users:security:read",
        "users:security:write",
        "admin_audit:read",
        "ops:logs:read",
        "ops:notifications:read",
    ),
    SUPPORT_ADMIN_ROLE: (
        "users:read",
        "users:activity:read",
    ),
    OPS_ADMIN_ROLE: (
        "admin_audit:read",
        "ops:logs:read",
        "ops:logs:write",
        "ops:providers:read",
        "ops:providers:write",
        "ops:notifications:read",
        "ops:notifications:write",
        "ops:system_config:read",
        "ops:system_config:write",
        "cost:observability:read",
        "scanner:admin:read",
        "backtest:admin:read",
        "quant:admin:read",
        "quant:admin:write",
    ),
}

_SENSITIVE_AUDIT_KEY_MARKERS = (
    "password",
    "token",
    "session",
    "cookie",
    "secret",
    "totp",
    "mfa_code",
    "recovery_code",
    "api_key",
    "apikey",
    "authorization",
)


def _sanitize_assignment_audit_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            key_text = str(key)
            if any(marker in key_text.lower() for marker in _SENSITIVE_AUDIT_KEY_MARKERS):
                sanitized[key_text] = "[redacted]"
            else:
                sanitized[key_text] = _sanitize_assignment_audit_payload(item)
        return sanitized
    if isinstance(value, (list, tuple)):
        return [_sanitize_assignment_audit_payload(item) for item in value]
    return value


def _explicit_admin_capabilities(user: Any) -> set[str]:
    return {str(capability).strip() for capability in getattr(user, "admin_capabilities", ()) or () if str(capability).strip()}


def build_admin_role_assignment_preflight(
    *,
    actor: Any,
    target_user_id: str,
    role_key: str,
    capabilities: tuple[str, ...] | list[str],
    audit_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a fail-closed readiness decision for future role assignment.

    This helper is intentionally non-mutating: it does not assign roles,
    create endpoints, change seeded defaults, or expand coarse legacy admin
    permissions for assignment decisions.
    """
    actor_id = str(getattr(actor, "user_id", "") or getattr(actor, "id", "") or "").strip()
    normalized_target = str(target_user_id or "").strip()
    normalized_role = str(role_key or "").strip()
    normalized_capabilities = tuple(str(capability or "").strip() for capability in capabilities or ())
    explicit_capabilities = _explicit_admin_capabilities(actor)
    known_capabilities = set(ADMIN_RBAC_CAPABILITIES)
    sanitized_payload = _sanitize_assignment_audit_payload(audit_payload or {})
    base = {
        "allowed": False,
        "error": None,
        "targetUserId": normalized_target,
        "roleKey": normalized_role if normalized_role in ADMIN_RBAC_ROLES else None,
        "capabilityCount": len(set(normalized_capabilities)),
        "coarseFallbackIgnored": bool(getattr(actor, "legacy_admin", False))
        and ADMIN_ROLE_ASSIGNMENT_REQUIRED_CAPABILITY not in explicit_capabilities,
        "auditPayload": sanitized_payload,
    }

    if ADMIN_ROLE_ASSIGNMENT_REQUIRED_CAPABILITY not in explicit_capabilities:
        return {**base, "error": "admin_capability_required"}
    if not normalized_role or normalized_role not in ADMIN_RBAC_ROLES:
        return {**base, "error": "unknown_admin_role"}
    if not normalized_capabilities or any(capability not in known_capabilities for capability in normalized_capabilities):
        return {**base, "error": "invalid_admin_capability"}
    if actor_id and normalized_target and actor_id == normalized_target:
        return {**base, "error": "self_assignment_blocked"}
    return {
        **base,
        "allowed": True,
        "error": None,
        "roleKey": normalized_role,
        "coarseFallbackIgnored": False,
    }


def _is_legacy_admin(user: Any) -> bool:
    return bool(getattr(user, "is_admin", False)) or str(getattr(user, "role", "") or "") == ROLE_ADMIN


def is_coarse_admin_fallback_enabled() -> bool:
    """Return whether legacy admin role expansion is still allowed."""
    raw = os.getenv("WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED")
    if raw is None:
        return True
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def expand_admin_capabilities(user: Any) -> set[str]:
    """Return effective admin capabilities without enforcing them on routes."""
    if user is None or not _is_legacy_admin(user):
        return set()

    from src.storage import DatabaseManager

    db = DatabaseManager.get_instance()
    user_id = str(getattr(user, "user_id", "") or getattr(user, "id", "") or "").strip()
    capabilities = set(db.list_admin_capabilities_for_user(user_id)) if user_id else set()
    if capabilities:
        return capabilities
    if not is_coarse_admin_fallback_enabled():
        return set()
    return set(db.list_admin_role_capabilities(SUPER_ADMIN_ROLE))


def has_admin_capability(user: Any, capability: str) -> bool:
    """Return whether a user has a read-only expanded admin capability."""
    normalized = str(capability or "").strip()
    if not normalized:
        return False
    return normalized in expand_admin_capabilities(user)
