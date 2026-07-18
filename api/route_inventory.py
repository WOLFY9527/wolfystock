"""Read-only inventory for registered FastAPI and mounted application routes."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RouteInventoryEntry:
    """Metadata for one effective runtime HTTP route."""

    route: Any
    path: str
    methods: frozenset[str]
    include_in_schema: bool
    mounted_application_route: bool

    @property
    def registered_runtime_route(self) -> bool:
        return True

    @property
    def public_openapi_route(self) -> bool:
        return self.include_in_schema and not self.mounted_application_route

    @property
    def hidden_runtime_route(self) -> bool:
        return not self.include_in_schema and not self.mounted_application_route


def _join_route_path(prefix: str, path: str) -> str:
    if not prefix:
        return path
    if path == "/":
        return f"{prefix.rstrip('/')}/"
    return f"{prefix.rstrip('/')}/{path.lstrip('/')}"


def iter_route_inventory(
    routes: Iterable[Any],
    *,
    _mount_prefix: str = "",
    _mounted_application: bool = False,
) -> Iterator[RouteInventoryEntry]:
    """Yield effective HTTP routes recursively without executing request code."""
    for route in routes:
        effective_candidates = getattr(route, "effective_candidates", None)
        if callable(effective_candidates):
            yield from iter_route_inventory(
                effective_candidates(),
                _mount_prefix=_mount_prefix,
                _mounted_application=_mounted_application,
            )
            continue

        nested_routes = getattr(route, "routes", None)
        if nested_routes is not None:
            mount_prefix = _join_route_path(
                _mount_prefix,
                str(getattr(route, "path", "")),
            )
            yield from iter_route_inventory(
                nested_routes,
                _mount_prefix=mount_prefix,
                _mounted_application=True,
            )
            continue

        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not isinstance(path, str) or not methods:
            continue
        yield RouteInventoryEntry(
            route=route,
            path=_join_route_path(_mount_prefix, path),
            methods=frozenset(str(method) for method in methods),
            include_in_schema=bool(getattr(route, "include_in_schema", False)),
            mounted_application_route=_mounted_application,
        )
