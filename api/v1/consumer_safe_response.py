# -*- coding: utf-8 -*-
"""Helpers for consumer-safe API response projection."""

from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from src.services.consumer_api_diagnostic_redaction import project_consumer_api_payload


def consumer_safe_json_response(payload: Any, *, surface: str, exclude_none: bool = False) -> JSONResponse:
    return JSONResponse(
        content=jsonable_encoder(
            project_consumer_api_payload(payload, surface=surface),
            exclude_none=exclude_none,
        )
    )


__all__ = ["consumer_safe_json_response"]
