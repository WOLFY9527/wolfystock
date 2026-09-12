# -*- coding: utf-8 -*-
"""Inert auth-context contracts shared across non-API layers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from src.services.admin_user_service import AdminUserService


@dataclass(frozen=True)
class AdminActorContext:
    user_id: str
    username: str
    display_name: str | None
    role: str
    is_admin: bool


def resolve_ordinary_user_actor_references(
    user_ids: Iterable[Any],
    *,
    repo: Any | None = None,
) -> dict[str, dict[str, str]]:
    """Return safe ordinary-user references through the public auth context.

    Admin observability may project only current ordinary-user identities.  This
    deliberately exposes that narrow lookup without exposing the broader admin
    user read-model implementation to other owners.
    """

    return AdminUserService(repo=repo).resolve_user_actor_references(user_ids)
