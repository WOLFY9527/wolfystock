# -*- coding: utf-8 -*-
"""Tests for FastAPI app CORS configuration."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from api.app import create_app


class AppCorsConfigTestCase(unittest.TestCase):
    """CORS configuration should stay browser-compatible."""

    def _build_app(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return create_app(static_dir=Path(temp_dir.name))

    def test_allow_all_disables_credentials(self):
        with patch.dict(os.environ, {"CORS_ALLOW_ALL": "true"}, clear=False):
            app = self._build_app()

        cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
        self.assertEqual(cors.kwargs["allow_origins"], ["*"])
        self.assertFalse(cors.kwargs["allow_credentials"])

    def test_explicit_origin_list_keeps_credentials_enabled(self):
        with patch.dict(os.environ, {"CORS_ALLOW_ALL": "false"}, clear=False):
            app = self._build_app()

        cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
        self.assertIn("http://localhost:5173", cors.kwargs["allow_origins"])
        self.assertTrue(cors.kwargs["allow_credentials"])

    def test_security_headers_are_present_without_hsts_in_local_dev(self):
        with patch.dict(os.environ, {"CORS_ALLOW_ALL": "false", "APP_ENV": ""}, clear=False):
            app = self._build_app()

        with TestClient(app) as client:
            response = client.get("/api/health/live")

        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["referrer-policy"], "strict-origin-when-cross-origin")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("geolocation=()", response.headers["permissions-policy"])
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy-report-only"])
        self.assertNotIn("strict-transport-security", response.headers)

    def test_hsts_is_only_set_for_production_https_context(self):
        production_env = {
            "APP_ENV": "production",
            "CORS_ALLOW_ALL": "false",
            "CORS_ORIGINS": "https://app.example.test",
            "TRUST_X_FORWARDED_FOR": "true",
        }
        with patch.dict(os.environ, production_env, clear=False):
            app = self._build_app()

            with TestClient(app) as client:
                http_response = client.get("/api/health/live")
                https_response = client.get(
                    "/api/health/live",
                    headers={"X-Forwarded-Proto": "https"},
                )

        self.assertNotIn("strict-transport-security", http_response.headers)
        self.assertEqual(
            https_response.headers["strict-transport-security"],
            "max-age=31536000; includeSubDomains",
        )


if __name__ == "__main__":
    unittest.main()
