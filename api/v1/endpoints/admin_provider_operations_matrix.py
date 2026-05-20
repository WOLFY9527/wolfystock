# -*- coding: utf-8 -*-
"""Admin-only read API for the provider operations matrix."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import CurrentUser, require_admin_capability
from src.services.provider_operations_matrix_service import ProviderOperationsMatrixService

router = APIRouter()


@router.get(
    "/providers/operations-matrix",
    summary="Get read-only provider operations matrix",
)
def get_provider_operations_matrix(
    _: CurrentUser = Depends(require_admin_capability("ops:providers:read")),
):
    return ProviderOperationsMatrixService().build_matrix()
