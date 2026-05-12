# -*- coding: utf-8 -*-
"""Inert auth-context contracts shared across non-API layers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdminActorContext:
    user_id: str
    username: str
    display_name: str | None
    role: str
    is_admin: bool
