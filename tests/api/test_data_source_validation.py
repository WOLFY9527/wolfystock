# -*- coding: utf-8 -*-
"""Remote provider validation tests for system settings data sources."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from src.config import Config
from src.core.config_manager import ConfigManager
from src.services.system_config_provider_projection import mask_provider_secret
from src.services.system_config_service import SystemConfigService


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def close(self):
        return None


class DataSourceValidationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_path = Path(self.temp_dir.name) / ".env"
        self.env_path.write_text("FMP_API_KEY=full-secret-fmp-key\n", encoding="utf-8")
        os.environ["ENV_FILE"] = str(self.env_path)
        Config.reset_instance()
        self.service = SystemConfigService(manager=ConfigManager(env_path=self.env_path))

    def tearDown(self) -> None:
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        self.temp_dir.cleanup()

    def test_fmp_quote_and_historical_200_returns_success(self) -> None:
        responses = [
            _Response(200, [{"symbol": "MSFT", "price": 400.12}]),
            _Response(200, {"symbol": "MSFT", "historical": [{"close": 399.1}]}),
        ]
        with patch("src.providers.http.requests.request", side_effect=responses):
            payload = self.service.test_builtin_data_source(provider="fmp", symbol="MSFT")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "success")
        self.assertTrue(all(check["ok"] for check in payload["checks"]))
        self.assertEqual(payload["key_masked"], "full...-key")
        self.assertEqual(payload["summary"], "FMP 连接成功：quote 和 historical endpoint 均可用。")
        self.assertEqual(payload["suggestion"], "请检查 FMP key 是否有效、套餐是否支持 quote/historical endpoint、额度是否用尽。")

    def test_fmp_quote_200_historical_403_returns_partial(self) -> None:
        responses = [
            _Response(200, [{"symbol": "MSFT", "price": 400.12}]),
            _Response(403, {"Error Message": "Forbidden"}),
        ]
        with patch("src.providers.http.requests.request", side_effect=responses):
            payload = self.service.test_builtin_data_source(provider="fmp", symbol="MSFT")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(payload["checks"][1]["http_status"], 403)
        self.assertEqual(payload["checks"][1]["error_type"], "Forbidden")
        self.assertEqual(payload["summary"], "FMP 部分可用：部分 endpoint 失败。 失败 endpoint：historical。")
        self.assertEqual(payload["suggestion"], "请检查 FMP key 是否有效、套餐是否支持 quote/historical endpoint、额度是否用尽。")

    def test_fmp_quote_403_historical_403_returns_failed(self) -> None:
        responses = [
            _Response(403, {"Error Message": "Forbidden"}),
            _Response(403, {"Error Message": "Forbidden"}),
        ]
        with patch("src.providers.http.requests.request", side_effect=responses):
            payload = self.service.test_builtin_data_source(provider="fmp", symbol="MSFT")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "failed")
        self.assertTrue(all(check["error_type"] == "Forbidden" for check in payload["checks"]))

    def test_fmp_timeout_returns_failed_timeout(self) -> None:
        with patch("src.providers.http.requests.request", side_effect=requests.exceptions.Timeout):
            payload = self.service.test_builtin_data_source(provider="fmp", symbol="MSFT")

        self.assertEqual(payload["status"], "failed")
        self.assertTrue(all(check["error_type"] == "Timeout" for check in payload["checks"]))

    def test_missing_key_returns_missing_key(self) -> None:
        self.env_path.write_text("", encoding="utf-8")
        payload = self.service.test_builtin_data_source(provider="fmp", symbol="MSFT")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "missing_key")
        self.assertEqual(payload["checks"], [])

    def test_response_does_not_include_full_api_key(self) -> None:
        responses = [
            _Response(200, {"Error Message": "full-secret-fmp-key is invalid"}),
            _Response(403, {"Error Message": "Forbidden"}),
        ]
        with patch("src.providers.http.requests.request", side_effect=responses):
            payload = self.service.test_builtin_data_source(provider="fmp", symbol="MSFT")

        serialized = str(payload)
        self.assertNotIn("full-secret-fmp-key", serialized)
        self.assertIn("full...-key", serialized)
        self.assertIn("*** is invalid", serialized)

    def test_sanitize_url_masks_api_key_and_token(self) -> None:
        sanitized = SystemConfigService.sanitize_url(
            "https://example.test/quote?symbol=MSFT&apikey=full-secret&token=another-secret"
        )

        self.assertIn("apikey=***", sanitized)
        self.assertIn("token=***", sanitized)
        self.assertNotIn("full-secret", sanitized)
        self.assertNotIn("another-secret", sanitized)

    def test_mask_provider_secret_keeps_first_key_and_count_for_multiple_values(self) -> None:
        masked = mask_provider_secret("first-secret-key, second-secret-key, third-secret-key")

        self.assertEqual(masked, "firs...-key (+2)")

    def test_unsupported_provider_returns_unsupported(self) -> None:
        payload = self.service.test_builtin_data_source(provider="unknown_provider", symbol="MSFT")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "unsupported")
        self.assertIn("暂未实现远程校验", payload["summary"])
        self.assertNotIn("本地校验通过", payload["summary"])


if __name__ == "__main__":
    unittest.main()
