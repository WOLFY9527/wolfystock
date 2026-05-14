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

    def test_builtin_data_source_validation_endpoint_preserves_twelve_data_hk_diagnostic_checks(self) -> None:
        service = Mock()
        expected = {
            "provider": "twelve_data",
            "ok": False,
            "status": "partial",
            "checked_at": "2026-05-14T00:00:00+00:00",
            "duration_ms": 88,
            "key_masked": "td-s...-key",
            "checks": [
                {
                    "name": "hk_quote",
                    "endpoint": "/quote",
                    "ok": True,
                    "http_status": 200,
                    "duration_ms": 32,
                    "error_type": None,
                    "message": "quote endpoint 可用。",
                },
                {
                    "name": "hk_history",
                    "endpoint": "/time_series",
                    "ok": False,
                    "http_status": 429,
                    "duration_ms": 56,
                    "error_type": "RateLimited",
                    "message": "history endpoint 返回 429，可能已触发 provider 频率限制或额度耗尽。",
                },
                {
                    "name": "hk_quote_history",
                    "endpoint": "/quote + /time_series",
                    "ok": False,
                    "http_status": 429,
                    "duration_ms": 88,
                    "error_type": "quota_limited",
                    "message": "Twelve Data 已配置，但 HK quote/history 诊断命中额度或频率限制。",
                },
            ],
            "summary": "Twelve Data 已配置，但 HK quote/history 诊断命中额度或频率限制。",
            "suggestion": "请检查 Twelve Data credits/quota/frequency limit，稍后重试或切换可用 key。",
        }
        service.test_builtin_data_source.return_value = expected

        payload = system_config.test_builtin_data_source(
            request=TestBuiltinDataSourceRequest(provider="twelve_data", symbol="HK00700"),
            service=service,
        ).model_dump()

        self.assertEqual(payload, expected)
        service.test_builtin_data_source.assert_called_once_with(
            provider="twelve_data",
            symbol="HK00700",
            credential="",
            secret="",
            timeout_seconds=5.0,
        )

    def test_builtin_data_source_validation_endpoint_preserves_twelve_data_hk_state_vocabulary(self) -> None:
        service = Mock()
        cases = (
            ("missing_key", "missing_key"),
            ("configured_unverified", "partial"),
            ("ok_hk_quote_history", "success"),
            ("quota_limited", "partial"),
            ("hk_entitlement_missing", "partial"),
            ("timeout", "partial"),
            ("malformed_response", "partial"),
            ("provider_error", "partial"),
        )

        for diagnostic_state, status in cases:
            with self.subTest(diagnostic_state=diagnostic_state):
                expected = {
                    "provider": "twelve_data",
                    "ok": status == "success",
                    "status": status,
                    "checked_at": "2026-05-14T00:00:00+00:00",
                    "duration_ms": 88,
                    "key_masked": "td-s...-key",
                    "checks": [
                        {
                            "name": "hk_quote_history",
                            "endpoint": "/quote + /time_series",
                            "ok": diagnostic_state == "ok_hk_quote_history",
                            "http_status": 200 if diagnostic_state == "ok_hk_quote_history" else None,
                            "duration_ms": 88,
                            "error_type": diagnostic_state,
                            "message": f"diagnostic:{diagnostic_state}",
                        }
                    ],
                    "summary": f"summary:{diagnostic_state}",
                    "suggestion": f"suggestion:{diagnostic_state}",
                }
                service.test_builtin_data_source.return_value = expected

                payload = system_config.test_builtin_data_source(
                    request=TestBuiltinDataSourceRequest(provider="twelve_data", symbol="HK00700"),
                    service=service,
                ).model_dump()

                self.assertEqual(payload, expected)
                self.assertEqual(payload["checks"][0]["error_type"], diagnostic_state)

        self.assertEqual(service.test_builtin_data_source.call_count, len(cases))


if __name__ == "__main__":
    unittest.main()
