# -*- coding: utf-8 -*-
"""Helpers for inspecting FastAPI route tables in tests."""

from __future__ import annotations

from typing import Any, Iterable

from fastapi.routing import APIRoute


def iter_effective_api_routes(routes: Iterable[Any]):
    """Yield concrete APIRoute objects, including FastAPI included-router candidates."""
    for route in routes:
        if isinstance(route, APIRoute) or (
            hasattr(route, "path") and hasattr(route, "methods") and hasattr(route, "endpoint")
        ):
            yield route
            continue
        effective_candidates = getattr(route, "effective_candidates", None)
        if callable(effective_candidates):
            yield from iter_effective_api_routes(effective_candidates())
