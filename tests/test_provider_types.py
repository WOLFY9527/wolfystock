# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from src.providers import (
    ProviderCapability,
    ProviderMissingCredentials,
    ProviderReason,
    ProviderResult,
    ProviderStatus,
    normalize_provider_exception,
    provider_failed_result_from_exception,
    reason_from_http_status,
)


class TestProviderTypes(unittest.TestCase):
    def test_success_result_sets_ok_true(self) -> None:
        result = ProviderResult.success("alpha", ProviderCapability.QUOTE, data={"price": 1})

        self.assertTrue(result.ok)
        self.assertEqual(result.status, ProviderStatus.SUCCESS)

    def test_failed_result_sets_ok_false(self) -> None:
        result = ProviderResult.failed("alpha", "quote", ProviderReason.UNKNOWN_ERROR)

        self.assertFalse(result.ok)
        self.assertEqual(result.status, ProviderStatus.FAILED)

    def test_skipped_result_sets_ok_false(self) -> None:
        result = ProviderResult.skipped("alpha", "quote", ProviderReason.MISSING_API_KEY)

        self.assertFalse(result.ok)
        self.assertEqual(result.status, ProviderStatus.SKIPPED)

    def test_failed_and_skipped_reasons_are_distinct(self) -> None:
        failed = ProviderResult.failed("alpha", "quote", ProviderReason.TIMEOUT)
        skipped = ProviderResult.skipped("alpha", "quote", ProviderReason.PREVIOUS_PROVIDER_SUCCEEDED)

        self.assertEqual(failed.reason, ProviderReason.TIMEOUT)
        self.assertEqual(skipped.reason, ProviderReason.PREVIOUS_PROVIDER_SUCCEEDED)
        self.assertNotEqual(failed.status, skipped.status)

    def test_error_message_is_sanitized(self) -> None:
        result = ProviderResult.failed(
            "alpha",
            "quote",
            ProviderReason.UNAUTHORIZED,
            errorMessage="request failed apikey=SECRET token=TOKEN password=PW",
        )

        self.assertNotIn("SECRET", result.errorMessage or "")
        self.assertNotIn("TOKEN", result.errorMessage or "")
        self.assertNotIn("PW", result.errorMessage or "")
        self.assertIn("apikey=***", result.errorMessage or "")

    def test_metadata_is_sanitized_recursively(self) -> None:
        result = ProviderResult.failed(
            "alpha",
            "quote",
            ProviderReason.UNKNOWN_ERROR,
            metadata={
                "api_key": "SECRET",
                "nested": {"token": "TOKEN", "safe": "ok"},
                "items": [{"password": "PW"}],
            },
        )

        self.assertEqual(result.metadata["api_key"], "***")
        self.assertEqual(result.metadata["nested"]["token"], "***")
        self.assertEqual(result.metadata["nested"]["safe"], "ok")
        self.assertEqual(result.metadata["items"][0]["password"], "***")

    def test_http_403_maps_to_forbidden(self) -> None:
        self.assertEqual(reason_from_http_status(403), ProviderReason.FORBIDDEN)

    def test_http_429_maps_to_rate_limited(self) -> None:
        self.assertEqual(reason_from_http_status(429), ProviderReason.RATE_LIMITED)

    def test_timeout_exception_maps_to_timeout(self) -> None:
        self.assertEqual(normalize_provider_exception(TimeoutError("timed out")), ProviderReason.TIMEOUT)

    def test_missing_credentials_exception_maps_to_missing_api_key(self) -> None:
        self.assertEqual(
            normalize_provider_exception(ProviderMissingCredentials("missing")),
            ProviderReason.MISSING_API_KEY,
        )

    def test_failed_result_from_http_exception_uses_status_mapping(self) -> None:
        class HTTPError(Exception):
            status_code = 403

        result = provider_failed_result_from_exception(
            HTTPError("forbidden token=SECRET"),
            provider="alpha",
            capability="quote",
        )

        self.assertEqual(result.reason, ProviderReason.FORBIDDEN)
        self.assertEqual(result.httpStatus, 403)
        self.assertNotIn("SECRET", result.errorMessage or "")

    def test_to_dict_is_json_serializable(self) -> None:
        result = ProviderResult.success(
            "alpha",
            ProviderCapability.QUOTE,
            data={"at": datetime(2026, 4, 30, 1, 2, 3, tzinfo=timezone.utc)},
            metadata={"safe": "ok"},
        )

        json.dumps(result.to_dict())

    def test_datetime_fields_serialize_as_iso_strings(self) -> None:
        started = datetime(2026, 4, 30, 1, 2, 3, tzinfo=timezone.utc)
        finished = datetime(2026, 4, 30, 1, 2, 4, tzinfo=timezone.utc)
        result = ProviderResult.success(
            "alpha",
            "quote",
            startedAt=started,
            finishedAt=finished,
        ).to_dict()

        self.assertEqual(result["startedAt"], started.isoformat())
        self.assertEqual(result["finishedAt"], finished.isoformat())

if __name__ == "__main__":
    unittest.main()
