# -*- coding: utf-8 -*-
"""Focused credential-owner tests for Rotation Radar diagnostics."""

from __future__ import annotations

import json
import logging
import unittest
from unittest.mock import patch

from data_provider.provider_credentials import get_provider_credentials
from src.services.rotation_radar_quote_provider import get_rotation_radar_provider_diagnostics


class _MessageCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


class RotationRadarCredentialOwnerTestCase(unittest.TestCase):
    def test_diagnostics_project_each_alpaca_bundle_without_second_field_map(self) -> None:
        cases = (
            ({}, "not_configured"),
            ({"ALPACA_API_KEY_ID": "alpaca-key-sentinel"}, "incomplete_credentials"),
            ({"ALPACA_API_SECRET_KEY": "alpaca-secret-sentinel"}, "incomplete_credentials"),
            (
                {
                    "ALPACA_API_KEY_ID": "alpaca-key-sentinel",
                    "ALPACA_API_SECRET_KEY": "alpaca-secret-sentinel",
                },
                "configured",
            ),
        )

        for config, expected_status in cases:
            with self.subTest(config_names=tuple(config)):
                credentials = get_provider_credentials("alpaca", config=config)
                with patch(
                    "src.services.rotation_radar_quote_provider.get_provider_credentials",
                    return_value=credentials,
                ) as resolver:
                    diagnostics = get_rotation_radar_provider_diagnostics()

                resolver.assert_called_once_with("alpaca")
                self.assertEqual(diagnostics["credentialsPresent"], credentials.is_configured)
                self.assertEqual(diagnostics["credentialFieldsMissing"], list(credentials.missing_fields))
                self.assertEqual(diagnostics["missingCredentialFields"], list(credentials.missing_fields))
                self.assertEqual(diagnostics["credentialSource"], credentials.credential_source)
                self.assertEqual(diagnostics["configuredProviderStatus"], expected_status)
                self.assertFalse(diagnostics["providerConstructed"])

    def test_diagnostics_and_logs_never_expose_alpaca_credential_values(self) -> None:
        secret_values = ("alpaca-key-sentinel", "alpaca-secret-sentinel")
        credentials = get_provider_credentials(
            "alpaca",
            config={
                "ALPACA_API_KEY_ID": secret_values[0],
                "ALPACA_API_SECRET_KEY": secret_values[1],
            },
        )
        capture = _MessageCapture()
        root_logger = logging.getLogger()
        root_logger.addHandler(capture)
        try:
            with patch(
                "src.services.rotation_radar_quote_provider.get_provider_credentials",
                return_value=credentials,
            ):
                diagnostics = get_rotation_radar_provider_diagnostics()
        finally:
            root_logger.removeHandler(capture)

        serialized = json.dumps(diagnostics, ensure_ascii=False, sort_keys=True)
        logged = "\n".join(capture.messages)
        for secret in secret_values:
            self.assertNotIn(secret, serialized)
            self.assertNotIn(secret, logged)


if __name__ == "__main__":
    unittest.main()
