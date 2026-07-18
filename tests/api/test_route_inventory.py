"""Focused contracts for recursive FastAPI runtime route inventory."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI


def test_route_inventory_recurses_without_executing_handlers_or_dependencies() -> None:
    from api.route_inventory import iter_route_inventory

    calls: list[str] = []
    leaf_router = APIRouter()
    nested_router = APIRouter()

    def require_operator() -> None:
        calls.append("dependency")

    @leaf_router.get("/public")
    def public_route() -> dict[str, bool]:
        calls.append("public-handler")
        return {"ok": True}

    @leaf_router.get(
        "/hidden",
        include_in_schema=False,
        dependencies=[Depends(require_operator)],
    )
    def hidden_route() -> dict[str, bool]:
        calls.append("hidden-handler")
        return {"ok": True}

    nested_router.include_router(leaf_router, prefix="/leaf")
    app = FastAPI()
    app.include_router(nested_router, prefix="/api")

    inventory = {entry.path: entry for entry in iter_route_inventory(app.routes)}

    public = inventory["/api/leaf/public"]
    assert public.registered_runtime_route is True
    assert public.public_openapi_route is True
    assert public.hidden_runtime_route is False
    assert public.mounted_application_route is False

    hidden = inventory["/api/leaf/hidden"]
    assert hidden.registered_runtime_route is True
    assert hidden.public_openapi_route is False
    assert hidden.hidden_runtime_route is True
    assert hidden.mounted_application_route is False
    assert hidden.route.dependant.dependencies[0].call is require_operator
    assert "/api/leaf/public" in app.openapi()["paths"]
    assert "/api/leaf/hidden" not in app.openapi()["paths"]
    assert calls == []


def test_route_inventory_distinguishes_mounted_application_routes() -> None:
    from api.route_inventory import iter_route_inventory

    calls: list[str] = []
    child = FastAPI()

    @child.get("/status")
    def child_status() -> dict[str, bool]:
        calls.append("mounted-handler")
        return {"ok": True}

    parent = FastAPI()
    parent.mount("/child", child)

    inventory = {entry.path: entry for entry in iter_route_inventory(parent.routes)}
    mounted = inventory["/child/status"]

    assert mounted.registered_runtime_route is True
    assert mounted.include_in_schema is True
    assert mounted.public_openapi_route is False
    assert mounted.hidden_runtime_route is False
    assert mounted.mounted_application_route is True
    assert "/child/status" not in parent.openapi()["paths"]
    assert calls == []
