# -*- coding: utf-8 -*-
"""Read-only admin RBAC compatibility helpers for Phase R1."""

from __future__ import annotations

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


def _is_legacy_admin(user: Any) -> bool:
    return bool(getattr(user, "is_admin", False)) or str(getattr(user, "role", "") or "") == ROLE_ADMIN


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
    return set(db.list_admin_role_capabilities(SUPER_ADMIN_ROLE))


def has_admin_capability(user: Any, capability: str) -> bool:
    """Return whether a user has a read-only expanded admin capability."""
    normalized = str(capability or "").strip()
    if not normalized:
        return False
    return normalized in expand_admin_capabilities(user)
