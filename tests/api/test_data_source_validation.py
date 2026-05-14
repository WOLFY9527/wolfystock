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

    def _write_twelve_data_key(self, value: str = "td-secret-key") -> None:
        self.env_path.write_text(f"TWELVE_DATA_API_KEY={value}\n", encoding="utf-8")

    @staticmethod
    def _hk_state_check(payload):
        return next(check for check in payload["checks"] if check["name"] == "hk_quote_history")

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

    @patch("src.services.system_config_service.requests.request")
    def test_twelve_data_hk_quote_and_history_success_returns_hk_entitlement_success(self, mock_request) -> None:
        self._write_twelve_data_key()
        mock_request.side_effect = [
            _Response(200, {"status": "ok", "price": "503.5", "close": "503.5"}),
            _Response(
                200,
                {
                    "meta": {"symbol": "0700", "exchange": "HKEX", "interval": "1day"},
                    "values": [{"datetime": "2026-05-14", "close": "503.5", "volume": "12345000"}],
                },
            ),
        ]

        payload = self.service.test_builtin_data_source(provider="twelve_data", symbol="HK00700")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "success")
        self.assertEqual([check["name"] for check in payload["checks"]], ["hk_quote", "hk_history", "hk_quote_history"])
        self.assertEqual(self._hk_state_check(payload)["error_type"], "ok_hk_quote_history")
        self.assertIn("HK quote/history entitlement 可用", payload["summary"])
        serialized = str(payload)
        self.assertNotIn("td-secret-key", serialized)
        self.assertNotIn("apikey=", serialized)

    @patch("src.services.system_config_service.requests.request")
    def test_twelve_data_non_hk_symbol_returns_configured_unverified_without_remote_probe(self, mock_request) -> None:
        self._write_twelve_data_key()

        payload = self.service.test_builtin_data_source(provider="twelve_data", symbol="MSFT")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(payload["checks"], [self._hk_state_check(payload)])
        self.assertEqual(self._hk_state_check(payload)["error_type"], "configured_unverified")
        self.assertIn("未使用港股代码", payload["summary"])
        mock_request.assert_not_called()

    @patch("src.services.system_config_service.requests.request")
    def test_twelve_data_hk_quota_limited_is_sanitized_and_distinguished(self, mock_request) -> None:
        self._write_twelve_data_key()
        mock_request.side_effect = [
            _Response(200, {"status": "ok", "price": "503.5"}),
            _Response(429, {"status": "error", "message": "quota exceeded for td-secret-key"}),
        ]

        payload = self.service.test_builtin_data_source(provider="twelve_data", symbol="HK00700")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(self._hk_state_check(payload)["error_type"], "quota_limited")
        self.assertIn("额度", payload["summary"])
        serialized = str(payload)
        self.assertNotIn("td-secret-key", serialized)
        self.assertNotIn("apikey=", serialized)


if __name__ == "__main__":
    unittest.main()
