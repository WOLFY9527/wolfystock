# -*- coding: utf-8 -*-
"""Tests for backward-compatible config env aliases and TickFlow loading."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.config import Config, setup_env
from src.runtime.settings import parse_report_language


class ConfigEnvCompatibilityTestCase(unittest.TestCase):
    def tearDown(self):
        Config.reset_instance()

    @patch("src.config.setup_env")
    @patch("src.runtime.settings.parse_litellm_yaml", return_value=[])
    def test_load_from_env_reads_tickflow_api_key(
        self, _mock_parse_litellm_yaml, _mock_setup_env
    ):
        with patch.dict(
            os.environ,
            {
                "STOCK_LIST": "600519",
                "TICKFLOW_API_KEY": "tf-secret",
            },
            clear=True,
        ):
            config = Config._load_from_env()

        self.assertEqual(config.tickflow_api_key, "tf-secret")

    @patch("src.config.setup_env")
    @patch("src.runtime.settings.parse_litellm_yaml", return_value=[])
    def test_load_from_env_keeps_default_behavior_without_tickflow_api_key(
        self, _mock_parse_litellm_yaml, _mock_setup_env
    ):
        with patch.dict(
            os.environ,
            {
                "STOCK_LIST": "600519",
            },
            clear=True,
        ):
            config = Config._load_from_env()

        self.assertIsNone(config.tickflow_api_key)
        self.assertEqual(
            config.realtime_source_priority,
            "tencent,akshare_sina,efinance,akshare_em",
        )

    @patch("src.config.setup_env")
    @patch("src.runtime.settings.parse_litellm_yaml", return_value=[])
    def test_load_from_env_reads_twelve_data_alias_and_alpaca_pair(
        self,
        _mock_parse_litellm_yaml,
        _mock_setup_env,
    ) -> None:
        with patch.dict(
            os.environ,
            {
                "STOCK_LIST": "600519",
                "TWELVEDATA_API_KEY": "td-legacy-key",
                "ALPACA_API_KEY_ID": "alpaca-id",
                "ALPACA_API_SECRET_KEY": "alpaca-secret",
                "ALPACA_DATA_FEED": "sip",
            },
            clear=True,
        ):
            config = Config._load_from_env()

        self.assertEqual(config.twelve_data_api_keys, ["td-legacy-key"])
        self.assertEqual(config.twelve_data_api_key, "td-legacy-key")
        self.assertEqual(config.alpaca_api_key_id, "alpaca-id")
        self.assertEqual(config.alpaca_api_secret_key, "alpaca-secret")
        self.assertEqual(config.alpaca_data_feed, "sip")

    @patch("src.config.setup_env")
    @patch("src.runtime.settings.parse_litellm_yaml", return_value=[])
    def test_load_from_env_accepts_each_twelve_data_alias(
        self,
        _mock_parse_litellm_yaml,
        _mock_setup_env,
    ) -> None:
        aliases = (
            "TWELVE_DATA_API_KEYS",
            "TWELVE_DATA_API_KEY",
            "TWELVEDATA_API_KEYS",
            "TWELVEDATA_API_KEY",
        )
        credential_value = "td-alias-sentinel"

        for env_name in aliases:
            with self.subTest(env_name=env_name), patch.dict(
                os.environ,
                {"STOCK_LIST": "600519", env_name: credential_value},
                clear=True,
            ):
                config = Config._load_from_env()

                self.assertEqual(config.twelve_data_api_keys, [credential_value])
                self.assertEqual(config.twelve_data_api_key, credential_value)

    @patch("src.config.setup_env")
    @patch("src.runtime.settings.parse_litellm_yaml", return_value=[])
    def test_schedule_run_immediately_falls_back_to_legacy_run_immediately(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        env = {
            "RUN_IMMEDIATELY": "false",
        }

        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()

        self.assertFalse(config.schedule_run_immediately)
        self.assertFalse(config.run_immediately)

    @patch("src.config.setup_env")
    @patch("src.runtime.settings.parse_litellm_yaml", return_value=[])
    def test_schedule_run_immediately_prefers_schedule_specific_setting(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        env = {
            "RUN_IMMEDIATELY": "false",
            "SCHEDULE_RUN_IMMEDIATELY": "true",
        }

        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()

        self.assertTrue(config.schedule_run_immediately)
        self.assertFalse(config.run_immediately)

    @patch("src.config.setup_env")
    @patch("src.runtime.settings.parse_litellm_yaml", return_value=[])
    def test_empty_legacy_run_immediately_stays_false_when_schedule_alias_is_unset(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        env = {
            "RUN_IMMEDIATELY": "",
        }

        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()

        self.assertFalse(config.schedule_run_immediately)
        self.assertFalse(config.run_immediately)

    @patch("src.config.setup_env")
    @patch("src.runtime.settings.parse_litellm_yaml", return_value=[])
    def test_empty_schedule_run_immediately_stays_false_without_falling_back(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        env = {
            "RUN_IMMEDIATELY": "true",
            "SCHEDULE_RUN_IMMEDIATELY": "",
        }

        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()

        self.assertFalse(config.schedule_run_immediately)
        self.assertTrue(config.run_immediately)

    @patch("src.config.setup_env")
    @patch("src.runtime.settings.parse_litellm_yaml", return_value=[])
    def test_report_language_prefers_preexisting_process_env_over_env_file(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("REPORT_LANGUAGE=zh\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "ENV_FILE": str(env_path),
                    "REPORT_LANGUAGE": "en",
                },
                clear=True,
            ):
                config = Config._load_from_env()

        self.assertEqual(config.report_language, "en")

    @patch("src.config.setup_env")
    @patch("src.runtime.settings.parse_litellm_yaml", return_value=[])
    def test_report_language_uses_env_file_when_process_env_is_absent(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("REPORT_LANGUAGE=en\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "ENV_FILE": str(env_path),
                },
                clear=True,
            ):
                config = Config._load_from_env()

        self.assertEqual(config.report_language, "en")

    def test_parse_report_language_accepts_known_alias_without_warning(self) -> None:
        with self.assertNoLogs("src.config", level="WARNING"):
            parsed = parse_report_language(Config, "zh-cn")

        self.assertEqual(parsed, "zh")

    @patch("src.config.setup_env")
    @patch("src.runtime.settings.parse_litellm_yaml", return_value=[])
    def test_invalid_numeric_env_values_fall_back_to_defaults(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        invalid_values = {
            "AGENT_ORCHESTRATOR_TIMEOUT_S": "oops",
            "NEWS_MAX_AGE_DAYS": "bad",
            "MAX_WORKERS": "",
            "WEBUI_PORT": "invalid",
        }

        for name, value in invalid_values.items():
            with self.subTest(name=name), patch.dict(
                os.environ,
                {name: value},
                clear=True,
            ):
                with self.assertRaisesRegex(ValueError, name):
                    Config._load_from_env()

    @patch("src.config.setup_env")
    @patch("src.runtime.settings.parse_litellm_yaml", return_value=[])
    def test_home_quick_analysis_generation_overrides_are_loaded(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        env = {
            "HOME_QUICK_ANALYSIS_MAX_OUTPUT_TOKENS": "3072",
            "HOME_QUICK_ANALYSIS_TEMPERATURE": "0.15",
        }

        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()

        self.assertEqual(config.home_quick_analysis_max_output_tokens, 3072)
        self.assertEqual(config.home_quick_analysis_temperature, 0.15)

    @patch("src.config.setup_env")
    @patch("src.runtime.settings.parse_litellm_yaml", return_value=[])
    def test_invalid_home_quick_analysis_generation_overrides_fall_back_to_defaults(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        invalid_values = {
            "HOME_QUICK_ANALYSIS_MAX_OUTPUT_TOKENS": "bad",
            "HOME_QUICK_ANALYSIS_TEMPERATURE": "oops",
        }

        for name, value in invalid_values.items():
            with self.subTest(name=name), patch.dict(
                os.environ,
                {name: value},
                clear=True,
            ):
                with self.assertRaisesRegex(ValueError, name):
                    Config._load_from_env()

    def test_setup_env_maps_legacy_local_proxy_to_standard_proxy_variables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "USE_PROXY=true",
                        "PROXY_HOST=127.0.0.1",
                        "PROXY_PORT=18080",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "ENV_FILE": str(env_path),
                },
                clear=True,
            ):
                setup_env(override=True)

                self.assertEqual(os.environ.get("HTTP_PROXY"), "http://127.0.0.1:18080")
                self.assertEqual(os.environ.get("HTTPS_PROXY"), "http://127.0.0.1:18080")
                self.assertIn("eastmoney.com", os.environ.get("NO_PROXY", ""))
                self.assertIn("tushare.pro", os.environ.get("NO_PROXY", ""))

    def test_setup_env_keeps_explicit_http_proxy_as_authoritative(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "USE_PROXY=true",
                        "PROXY_HOST=127.0.0.1",
                        "PROXY_PORT=18080",
                        "HTTP_PROXY=http://proxy.example:9000",
                        "HTTPS_PROXY=http://secure-proxy.example:9443",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "ENV_FILE": str(env_path),
                },
                clear=True,
            ):
                setup_env(override=True)

                self.assertEqual(os.environ.get("HTTP_PROXY"), "http://proxy.example:9000")
                self.assertEqual(os.environ.get("HTTPS_PROXY"), "http://secure-proxy.example:9443")


if __name__ == "__main__":
    unittest.main()
