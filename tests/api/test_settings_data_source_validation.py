# -*- coding: utf-8 -*-
"""System settings API tests for built-in provider validation."""

import unittest
from unittest.mock import Mock

from api.v1.endpoints import system_config
from api.v1.schemas.system_config import (
    TestBuiltinDataSourceRequest,
    TestCustomDataSourceRequest as CustomDataSourceRequestSchema,
)


class SettingsDataSourceValidationApiTestCase(unittest.TestCase):
    def test_custom_data_source_validation_endpoint_returns_service_payload_and_preserves_shape(self) -> None:
        service = Mock()
        expected = {
            "success": False,
            "message": "Endpoint reachable, but the server rejected the supplied credentials",
            "error": "Connectivity is working, but authentication/authorization failed.",
            "status_code": 401,
            "checked_url": "https://demo.example.com/v1",
            "latency_ms": 89,
        }
        service.test_custom_data_source.return_value = expected

        payload = system_config.test_custom_data_source(
            request=CustomDataSourceRequestSchema(
                name="Demo API",
                base_url="https://demo.example.com/v1",
                credential_schema="key_secret",
                credential="demo-key",
                secret="demo-secret",
                timeout_seconds=7.5,
            ),
            service=service,
        ).model_dump()

        self.assertEqual(payload, expected)
        service.test_custom_data_source.assert_called_once_with(
            name="Demo API",
            base_url="https://demo.example.com/v1",
            credential_schema="key_secret",
            credential="demo-key",
            secret="demo-secret",
            timeout_seconds=7.5,
        )

    def test_builtin_data_source_validation_endpoint_returns_service_payload(self) -> None:
        service = Mock()
        expected = {
            "provider": "fmp",
            "ok": False,
            "status": "failed",
            "checked_at": "2026-04-30T00:00:00+00:00",
            "duration_ms": 123,
            "key_masked": "abcd...wxyz",
            "checks": [
                {
                    "name": "quote",
                    "endpoint": "/api/v3/quote/MSFT",
                    "ok": False,
                    "http_status": 403,
                    "duration_ms": 60,
                    "error_type": "Forbidden",
                    "message": "quote endpoint 返回 403。",
                }
            ],
            "summary": "FMP 连接失败。",
            "suggestion": "检查套餐权限。",
        }
        service.test_builtin_data_source.return_value = expected

        payload = system_config.test_builtin_data_source(
            request=TestBuiltinDataSourceRequest(provider="fmp", symbol="MSFT"),
            service=service,
        ).model_dump()

        self.assertEqual(payload, expected)
        service.test_builtin_data_source.assert_called_once_with(
            provider="fmp",
            symbol="MSFT",
            credential="",
            secret="",
            timeout_seconds=5.0,
        )


if __name__ == "__main__":
    unittest.main()
