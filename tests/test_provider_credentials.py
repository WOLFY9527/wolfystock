# -*- coding: utf-8 -*-
"""Tests for normalized provider credential resolution."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from data_provider.provider_credentials import get_provider_credentials
from src.config import Config


_TWELVE_DATA_ENV_ALIASES = (
    "TWELVE_DATA_API_KEYS",
    "TWELVE_DATA_API_KEY",
    "TWELVEDATA_API_KEYS",
    "TWELVEDATA_API_KEY",
)


class ProviderCredentialsTestCase(unittest.TestCase):
    def tearDown(self) -> None:
        Config.reset_instance()

    def _credentials_from_env(self, provider: str, env: dict[str, str]):
        with patch("src.config.setup_env"), patch.object(
            Config,
            "_parse_litellm_yaml",
            return_value=[],
        ), patch.dict(os.environ, {"STOCK_LIST": "600519", **env}, clear=True):
            Config.reset_instance()
            return get_provider_credentials(provider)

    def test_resolves_and_normalizes_twelve_data_as_single_key_provider(self) -> None:
        credentials = get_provider_credentials(
            "twelve_data",
            config={
                "twelve_data_api_keys": ["td-primary, td-secondary", "  "],
                "twelve_data_api_key": "legacy-td-key",
            },
        )

        self.assertEqual(credentials.provider, "twelve_data")
        self.assertEqual(credentials.auth_mode, "single_key")
        self.assertTrue(credentials.is_configured)
        self.assertFalse(credentials.is_partial)
        self.assertEqual(credentials.primary_api_key, "td-primary")
        self.assertEqual(credentials.api_keys, ("td-primary", "td-secondary", "legacy-td-key"))
        self.assertEqual(credentials.credential_source, "control_plane")

    def test_each_twelve_data_env_alias_is_attributed_to_env(self) -> None:
        credential_value = "twelve-alias-sentinel"
        for env_name in _TWELVE_DATA_ENV_ALIASES:
            with self.subTest(env_name=env_name):
                credentials = self._credentials_from_env(
                    "twelve_data",
                    {env_name: credential_value},
                )

                self.assertTrue(credentials.is_configured)
                self.assertEqual(credentials.api_keys, (credential_value,))
                self.assertEqual(credentials.credential_source, "env")
                self.assertEqual(credentials.missing_fields, ())

    def test_twelve_data_empty_and_whitespace_values_remain_missing(self) -> None:
        credentials = get_provider_credentials(
            "twelve_data",
            config={
                "TWELVE_DATA_API_KEYS": " ,  ",
                "TWELVEDATA_API_KEY": "\t",
            },
        )

        self.assertFalse(credentials.is_configured)
        self.assertFalse(credentials.is_partial)
        self.assertEqual(credentials.api_keys, ())
        self.assertEqual(credentials.missing_fields, ("TWELVE_DATA_API_KEY",))
        self.assertEqual(credentials.credential_source, "unavailable")

    def test_twelve_data_config_object_is_attributed_to_config(self) -> None:
        config_values = ("config-primary", "config-secondary")
        credentials = get_provider_credentials(
            "twelve_data",
            config=Config(twelve_data_api_keys=list(config_values)),
        )

        self.assertTrue(credentials.is_configured)
        self.assertEqual(credentials.api_keys, config_values)
        self.assertEqual(credentials.credential_source, "config")

    def test_resolves_alpaca_as_key_secret_provider(self) -> None:
        credentials = get_provider_credentials(
            "alpaca",
            config={
                "alpaca_api_key_id": "alpaca-key-id",
                "alpaca_api_secret_key": "alpaca-secret",
                "alpaca_data_feed": "sip",
            },
        )

        self.assertEqual(credentials.provider, "alpaca")
        self.assertEqual(credentials.auth_mode, "key_secret")
        self.assertTrue(credentials.is_configured)
        self.assertFalse(credentials.is_partial)
        self.assertEqual(credentials.key_id, "alpaca-key-id")
        self.assertEqual(credentials.secret_key, "alpaca-secret")
        self.assertEqual(credentials.extras["data_feed"], "sip")
        self.assertEqual(credentials.credential_source, "control_plane")

    def test_alpaca_missing_partial_and_complete_env_states(self) -> None:
        cases = (
            ({}, False, False, ("ALPACA_API_KEY_ID", "ALPACA_API_SECRET_KEY"), "unavailable"),
            (
                {"ALPACA_API_KEY_ID": "  ", "ALPACA_API_SECRET_KEY": "\t"},
                False,
                False,
                ("ALPACA_API_KEY_ID", "ALPACA_API_SECRET_KEY"),
                "unavailable",
            ),
            (
                {"ALPACA_API_KEY_ID": "alpaca-key-sentinel"},
                False,
                True,
                ("ALPACA_API_SECRET_KEY",),
                "env",
            ),
            (
                {"ALPACA_API_SECRET_KEY": "alpaca-secret-sentinel"},
                False,
                True,
                ("ALPACA_API_KEY_ID",),
                "env",
            ),
            (
                {
                    "ALPACA_API_KEY_ID": "alpaca-key-sentinel",
                    "ALPACA_API_SECRET_KEY": "alpaca-secret-sentinel",
                },
                True,
                False,
                (),
                "env",
            ),
        )

        for env, configured, partial, missing_fields, source in cases:
            with self.subTest(env_names=tuple(env)):
                credentials = self._credentials_from_env("alpaca", env)

                self.assertEqual(credentials.is_configured, configured)
                self.assertEqual(credentials.is_partial, partial)
                self.assertEqual(credentials.missing_fields, missing_fields)
                self.assertEqual(credentials.credential_source, source)


if __name__ == "__main__":
    unittest.main()
