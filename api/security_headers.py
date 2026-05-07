# -*- coding: utf-8 -*-
"""Shared security header helpers for API responses."""

from __future__ import annotations

import os
from typing import Dict

from fastapi import Request
from starlette.responses import Response

from src.auth import is_production_mode


SECURITY_HEADERS: Dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=(), "
        "fullscreen=(self), clipboard-read=(), clipboard-write=(self)"
    ),
    "Content-Security-Policy-Report-Only": (
        "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'"
    ),
}
HSTS_HEADER_VALUE = "max-age=31536000; includeSubDomains"


def request_is_https(request: Request) -> bool:
    if os.getenv("TRUST_X_FORWARDED_FOR", "false").lower() == "true":
        return request.headers.get("X-Forwarded-Proto", "").lower() == "https"
    return request.url.scheme == "https"


def apply_security_headers(response: Response, request: Request | None = None) -> Response:
    for name, value in SECURITY_HEADERS.items():
        if name not in response.headers:
            response.headers[name] = value
    if request is not None and is_production_mode() and request_is_https(request):
        response.headers["Strict-Transport-Security"] = HSTS_HEADER_VALUE
    return response
