# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import requests

from src.providers.types import ProviderReason, ProviderStatus
from src.providers.validation import validate_provider_connection


class _Response:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def close(self):
        return None


class TestProviderValidation(unittest.TestCase):
    def test_fmp_all_success_returns_provider_success(self) -> None:
        responses = [
            _Response(200, [{"symbol": "MSFT", "price": 400.12}]),
            _Response(200, {"symbol": "MSFT", "historical": [{"close": 399.1}]}),
        ]

        with patch("src.providers.validation.requests.request", side_effect=responses):
            result = validate_provider_connection("fmp", "MSFT", credential="full-secret-fmp-key")

        self.assertEqual(result.status, ProviderStatus.SUCCESS)
        self.assertEqual(result.metadata["status"], "success")
        self.assertTrue(all(check["ok"] for check in result.metadata["checks"]))

    def test_fmp_partial_keeps_partial_metadata(self) -> None:
        responses = [
            _Response(200, [{"symbol": "MSFT", "price": 400.12}]),
            _Response(403, {"Error Message": "Forbidden apikey=full-secret-fmp-key"}),
        ]

        with patch("src.providers.validation.requests.request", side_effect=responses):
            result = validate_provider_connection("fmp", "MSFT", credential="full-secret-fmp-key")

        self.assertEqual(result.status, ProviderStatus.SUCCESS)
        self.assertEqual(result.metadata["status"], "partial")
        self.assertEqual(result.metadata["checks"][1]["http_status"], 403)
        self.assertEqual(result.metadata["checks"][1]["reason"], ProviderReason.FORBIDDEN.value)
        self.assertNotIn("full-secret-fmp-key", json.dumps(result.to_dict()))

    def test_fmp_all_403_failed(self) -> None:
        responses = [
            _Response(403, {"Error Message": "Forbidden"}),
            _Response(403, {"Error Message": "Forbidden"}),
        ]

        with patch("src.providers.validation.requests.request", side_effect=responses):
            result = validate_provider_connection("fmp", "MSFT", credential="full-secret-fmp-key")

        self.assertEqual(result.status, ProviderStatus.FAILED)
        self.assertEqual(result.reason, ProviderReason.FORBIDDEN)

    def test_missing_key_skipped(self) -> None:
        result = validate_provider_connection("tushare", "MSFT", credential="")

        self.assertEqual(result.status, ProviderStatus.SKIPPED)
        self.assertEqual(result.reason, ProviderReason.MISSING_API_KEY)

    def test_timeout_failed(self) -> None:
        with patch("src.providers.validation.requests.request", side_effect=requests.exceptions.Timeout):
            result = validate_provider_connection("fmp", "MSFT", credential="full-secret-fmp-key")

        self.assertEqual(result.status, ProviderStatus.FAILED)
        self.assertEqual(result.reason, ProviderReason.TIMEOUT)

    def test_unsupported_provider_skipped(self) -> None:
        result = validate_provider_connection("unknown_provider", "MSFT")

        self.assertEqual(result.status, ProviderStatus.SKIPPED)
        self.assertEqual(result.reason, ProviderReason.UNSUPPORTED_CAPABILITY)

    def test_no_secret_leak(self) -> None:
        responses = [
            _Response(200, {"Error Message": "token=full-secret-fmp-key is invalid"}),
            _Response(403, {"Error Message": "Forbidden"}),
        ]

        with patch("src.providers.validation.requests.request", side_effect=responses):
            result = validate_provider_connection("fmp", "MSFT", credential="full-secret-fmp-key")

        serialized = json.dumps(result.to_dict())
        self.assertNotIn("full-secret-fmp-key", serialized)
        self.assertIn("token=***", serialized)


if __name__ == "__main__":
    unittest.main()
