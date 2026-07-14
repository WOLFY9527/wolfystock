# -*- coding: utf-8 -*-
"""Focused credential-owner tests for provider operations diagnostics."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from data_provider.provider_credentials import get_provider_credentials
from src.services.provider_operations_matrix_service import ProviderOperationsMatrixService


class ProviderOperationsMatrixCredentialOwnerTestCase(unittest.TestCase):
    @staticmethod
    def _rows(env: dict[str, str]) -> dict[str, dict[str, object]]:
        payload = ProviderOperationsMatrixService(
            env=env,
            spec_finder=lambda _: None,
        ).build_matrix()
        return {row["providerId"]: row for row in payload["rows"]}

    def test_alpaca_state_projects_runtime_resolver_eligibility(self) -> None:
        cases = (
            {},
            {"ALPACA_API_KEY_ID": "alpaca-key-sentinel"},
            {"ALPACA_API_SECRET_KEY": "alpaca-secret-sentinel"},
            {
                "ALPACA_API_KEY_ID": "alpaca-key-sentinel",
                "ALPACA_API_SECRET_KEY": "alpaca-secret-sentinel",
            },
        )

        for env in cases:
            with self.subTest(env_names=tuple(env)):
                credentials = get_provider_credentials("alpaca", config=env)
                alpaca = self._rows(env)["alpaca"]
                expected_state = "present" if credentials.is_configured else "missing"

                self.assertEqual(alpaca["credentialState"], expected_state)
                self.assertEqual(alpaca["runtimeState"], "runtime_metadata")

    def test_each_twelve_alias_projects_runtime_resolver_eligibility(self) -> None:
        aliases = (
            "TWELVE_DATA_API_KEYS",
            "TWELVE_DATA_API_KEY",
            "TWELVEDATA_API_KEYS",
            "TWELVEDATA_API_KEY",
        )

        for env_name in aliases:
            env = {env_name: "twelve-matrix-sentinel"}
            with self.subTest(env_name=env_name):
                credentials = get_provider_credentials("twelve_data", config=env)
                twelve_data = self._rows(env)["twelve_data"]

                self.assertTrue(credentials.is_configured)
                self.assertEqual(twelve_data["credentialState"], "present")
                self.assertEqual(twelve_data["runtimeState"], "runtime_metadata")

    def test_matrix_calls_runtime_owner_for_alpaca_and_twelve_data(self) -> None:
        with patch(
            "src.services.provider_operations_matrix_service.get_provider_credentials",
            wraps=get_provider_credentials,
            create=True,
        ) as resolver:
            ProviderOperationsMatrixService(env={}, spec_finder=lambda _: None).build_matrix()

        resolved_providers = [call.args[0] for call in resolver.call_args_list]
        self.assertEqual(resolved_providers.count("alpaca"), 1)
        self.assertEqual(resolved_providers.count("twelve_data"), 1)

    def test_matrix_never_serializes_credential_values(self) -> None:
        secret_values = ("alpaca-key-sentinel", "alpaca-secret-sentinel", "twelve-matrix-sentinel")
        payload = ProviderOperationsMatrixService(
            env={
                "ALPACA_API_KEY_ID": secret_values[0],
                "ALPACA_API_SECRET_KEY": secret_values[1],
                "TWELVEDATA_API_KEY": secret_values[2],
            },
            spec_finder=lambda _: None,
        ).build_matrix()
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)

        for secret in secret_values:
            self.assertNotIn(secret, serialized)
        self.assertFalse(payload["metadata"]["secretValuesIncluded"])


if __name__ == "__main__":
    unittest.main()
