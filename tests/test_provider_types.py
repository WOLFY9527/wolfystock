# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import socket
import ssl
import unittest
from dataclasses import asdict
from datetime import datetime, timezone
from types import SimpleNamespace

import src.providers.errors as provider_errors

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


class _StatusCodeError(RuntimeError):
    def __init__(self, status_code: int) -> None:
        super().__init__("request failed token=SECRET")
        self.status_code = status_code


class _HttpStatusError(RuntimeError):
    def __init__(self, http_status: int) -> None:
        super().__init__("request failed token=SECRET")
        self.http_status = http_status


class _ResponseStatusError(RuntimeError):
    def __init__(self, status_code: int) -> None:
        super().__init__("request failed token=SECRET")
        self.response = SimpleNamespace(status_code=status_code)


def test_retry_disposition_retries_timeout_connection_and_5xx_same_target() -> None:
    cases = [
        (TimeoutError("timed out token=SECRET"), None),
        (ConnectionError("connection reset token=SECRET"), None),
        (_StatusCodeError(503), 503),
        (_HttpStatusError(502), 502),
        (_ResponseStatusError(504), 504),
        (provider_errors.ProviderError("provider failed", http_status=503), 503),
    ]
    for failure, expected_status in cases:
        disposition = provider_errors.classify_provider_retry_disposition(failure)

        assert disposition.retry_same_target is True
        assert disposition.fallback_allowed is True
        assert disposition.counts_toward_transport_circuit is True
        assert set(asdict(disposition)) == {
            "retry_same_target",
            "fallback_allowed",
            "counts_toward_transport_circuit",
        }
        assert "SECRET" not in repr(disposition)
        if expected_status is not None:
            assert provider_errors._http_status_from_exception(failure) == expected_status


def test_retry_disposition_stops_401_403_429_same_target() -> None:
    for failure in (_StatusCodeError(401), _HttpStatusError(403), _ResponseStatusError(429)):
        disposition = provider_errors.classify_provider_retry_disposition(failure)

        assert disposition.retry_same_target is False
        assert disposition.fallback_allowed is True
        assert disposition.counts_toward_transport_circuit is False


def test_retry_disposition_stops_invalid_input_unsupported_payload_and_contract_failures() -> None:
    certificate_failure = RuntimeError("transport failed")
    certificate_failure.reason = "transport_error"  # type: ignore[attr-defined]
    certificate_failure.__cause__ = ssl.SSLCertVerificationError(1, "certificate verify failed")
    failures = [
        provider_errors.ProviderInvalidPayload("invalid request"),
        _StatusCodeError(415),
        ValueError("deterministic contract failure"),
        TypeError("deterministic contract failure"),
        KeyError("deterministic contract failure"),
        certificate_failure,
    ]
    for failure in failures:
        disposition = provider_errors.classify_provider_retry_disposition(failure)

        assert disposition.retry_same_target is False
        assert disposition.counts_toward_transport_circuit is False


def test_retry_disposition_separates_fallback_permission_from_same_target_retry() -> None:
    auth = provider_errors.classify_provider_retry_disposition(_StatusCodeError(401))
    invalid = provider_errors.classify_provider_retry_disposition(_StatusCodeError(400))
    timeout = provider_errors.classify_provider_retry_disposition(TimeoutError("timed out"))

    assert (auth.retry_same_target, auth.fallback_allowed) == (False, True)
    assert (invalid.retry_same_target, invalid.fallback_allowed) == (False, False)
    assert (timeout.retry_same_target, timeout.fallback_allowed) == (True, True)


def test_retry_disposition_counts_only_transport_availability_failures_toward_circuit() -> None:
    cases = [
        (socket.timeout("timed out"), True),
        (ConnectionResetError("connection reset"), True),
        (_StatusCodeError(500), True),
        (_StatusCodeError(401), False),
        (_StatusCodeError(429), False),
        (provider_errors.ProviderInvalidPayload("invalid payload"), False),
        (provider_errors.ProviderUnsupported("unsupported payload"), False),
    ]
    for failure, expected in cases:
        disposition = provider_errors.classify_provider_retry_disposition(failure)

        assert disposition.counts_toward_transport_circuit is expected
