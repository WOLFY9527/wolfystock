# -*- coding: utf-8 -*-
"""Lightweight provider policy defaults for future provider integrations."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProviderPolicy:
    timeoutSeconds: int = 15
    retryCount: int = 0
    cacheTtlSeconds: int | None = None
    circuitBreakerEnabled: bool = False
    fallbackOrder: list[str] = field(default_factory=list)
    isCritical: bool = False
