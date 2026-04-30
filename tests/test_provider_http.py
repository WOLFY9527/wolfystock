# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import requests

from src.providers.http import provider_get_json
from src.providers.types import ProviderCapability, ProviderReason, ProviderStatus


class _Response:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if isinstance(self._payload, BaseException):
            raise self._payload
        return self._payload

    def close(self):
        return None


class TestProviderHttp(unittest.TestCase):
    def test_200_json_success_returns_provider_success(self) -> None:
        with patch("src.providers.http.requests.request", return_value=_Response(200, {"price": 1})):
            result = provider_get_json(
                provider="fmp",
                capability=ProviderCapability.DATA_SOURCE_VALIDATION,
                url="https://example.test/quote",
            )

        self.assertEqual(result.status, ProviderStatus.SUCCESS)
        self.assertTrue(result.ok)
        self.assertEqual(result.httpStatus, 200)
        self.assertEqual(result.data, {"price": 1})
        self.assertIsInstance(result.durationMs, int)

    def test_401_maps_to_unauthorized(self) -> None:
        with patch("src.providers.http.requests.request", return_value=_Response(401, {"error": "unauthorized"})):
            result = provider_get_json(provider="fmp", capability="data_source_validation", url="https://example.test")

        self.assertEqual(result.status, ProviderStatus.FAILED)
        self.assertEqual(result.reason, ProviderReason.UNAUTHORIZED)

    def test_403_maps_to_forbidden(self) -> None:
        with patch("src.providers.http.requests.request", return_value=_Response(403, {"error": "forbidden"})):
            result = provider_get_json(provider="fmp", capability="data_source_validation", url="https://example.test")

        self.assertEqual(result.reason, ProviderReason.FORBIDDEN)

    def test_429_maps_to_rate_limited(self) -> None:
        with patch("src.providers.http.requests.request", return_value=_Response(429, {"error": "limited"})):
            result = provider_get_json(provider="fmp", capability="data_source_validation", url="https://example.test")

        self.assertEqual(result.reason, ProviderReason.RATE_LIMITED)

    def test_500_maps_to_failed(self) -> None:
        with patch("src.providers.http.requests.request", return_value=_Response(500, {"error": "server"})):
            result = provider_get_json(provider="fmp", capability="data_source_validation", url="https://example.test")

        self.assertEqual(result.status, ProviderStatus.FAILED)
        self.assertEqual(result.reason, ProviderReason.PROVIDER_UNHEALTHY)
        self.assertEqual(result.httpStatus, 500)

    def test_timeout_maps_to_timeout(self) -> None:
        with patch("src.providers.http.requests.request", side_effect=requests.exceptions.Timeout):
            result = provider_get_json(provider="fmp", capability="data_source_validation", url="https://example.test")

        self.assertEqual(result.status, ProviderStatus.FAILED)
        self.assertEqual(result.reason, ProviderReason.TIMEOUT)

    def test_invalid_json_maps_to_invalid_payload(self) -> None:
        with patch("src.providers.http.requests.request", return_value=_Response(200, ValueError("invalid json"))):
            result = provider_get_json(provider="fmp", capability="data_source_validation", url="https://example.test")

        self.assertEqual(result.status, ProviderStatus.FAILED)
        self.assertEqual(result.reason, ProviderReason.INVALID_PAYLOAD)

    def test_empty_payload_maps_to_no_data(self) -> None:
        with patch("src.providers.http.requests.request", return_value=_Response(200, {})):
            result = provider_get_json(provider="fmp", capability="data_source_validation", url="https://example.test")

        self.assertEqual(result.status, ProviderStatus.FAILED)
        self.assertEqual(result.reason, ProviderReason.NO_DATA)

    def test_url_params_with_apikey_token_are_sanitized(self) -> None:
        with patch("src.providers.http.requests.request", return_value=_Response(200, {"ok": True})):
            result = provider_get_json(
                provider="fmp",
                capability="data_source_validation",
                url="https://example.test/quote",
                params={"symbol": "MSFT", "apikey": "raw-api-key", "token": "raw-token"},
            )

        serialized = json.dumps(result.to_dict())
        self.assertIn("apikey=***", serialized)
        self.assertIn("token=***", serialized)
        self.assertNotIn("raw-api-key", serialized)
        self.assertNotIn("raw-token", serialized)

    def test_headers_with_authorization_token_are_sanitized(self) -> None:
        with patch("src.providers.http.requests.request", return_value=_Response(200, {"ok": True})):
            result = provider_get_json(
                provider="fmp",
                capability="data_source_validation",
                url="https://example.test/quote",
                headers={"Authorization": "Bearer raw-header-token", "X-Token": "raw-token"},
            )

        serialized = json.dumps(result.to_dict())
        self.assertNotIn("raw-header-token", serialized)
        self.assertNotIn("raw-token", serialized)
        self.assertIn('"Authorization": "***"', serialized)
        self.assertIn('"X-Token": "***"', serialized)

    def test_to_dict_output_does_not_contain_raw_secrets(self) -> None:
        with patch("src.providers.http.requests.request", return_value=_Response(200, {"message": "raw-secret-token accepted"})):
            result = provider_get_json(
                provider="fmp",
                capability="data_source_validation",
                url="https://example.test/quote?apikey=raw-url-key",
                params={"token": "raw-secret-token"},
                headers={"Authorization": "Bearer raw-auth-token"},
            )

        serialized = json.dumps(result.to_dict())
        self.assertNotIn("raw-url-key", serialized)
        self.assertNotIn("raw-secret-token", serialized)
        self.assertNotIn("raw-auth-token", serialized)


if __name__ == "__main__":
    unittest.main()
