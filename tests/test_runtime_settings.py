"""Focused contract tests for the immutable runtime settings snapshot."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import Config, setup_env
from src.runtime.settings import (
    RECOGNIZED_SETTING_NAMES,
    REDACTED_VALUE,
    RuntimeSettings,
    SettingSource,
)


EXPECTED_INVENTORY_SHA256 = (
    "5109b01b1b9f3e5ec1dfdf19f0d57ff12b1177ed2a630a9b1775d0cc5a98402e"
)
EXPECTED_DEFAULT_CONFIG_SHA256 = (
    "c63b4317e4170b08964626c37a87f098a9a33063fb7b555a45b572994c50777d"
)


def _load_snapshot() -> RuntimeSettings:
    with patch.object(Config, "_parse_litellm_yaml", return_value=[]):
        return RuntimeSettings.load(config_type=Config)


def _normalize(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _normalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def _config_contract_digest(config: Config) -> str:
    contract = []
    for config_field in fields(Config):
        if config_field.name == "_instance":
            continue
        value = getattr(config, config_field.name)
        contract.append([config_field.name, type(value).__name__, _normalize(value)])
    payload = json.dumps(
        contract,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_runtime_settings_inventory_preserves_all_344_names() -> None:
    inventory = "\n".join(sorted(RECOGNIZED_SETTING_NAMES)) + "\n"

    assert len(RECOGNIZED_SETTING_NAMES) == 344
    assert hashlib.sha256(inventory.encode("utf-8")).hexdigest() == (
        EXPECTED_INVENTORY_SHA256
    )


def test_runtime_settings_preserves_complete_default_value_and_type_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.config.setup_env", lambda override=False: None)
    with patch.dict(os.environ, {}, clear=True):
        snapshot = _load_snapshot()
        config = snapshot.to_config(Config)

    assert len(snapshot.config_values) == 229
    assert _config_contract_digest(config) == EXPECTED_DEFAULT_CONFIG_SHA256


def test_runtime_settings_preserves_process_over_file_over_default_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_path = tmp_path / "runtime.env"
    env_path.write_text(
        "MAX_WORKERS=4\nREPORT_LANGUAGE=zh\nNEWS_STRATEGY_PROFILE=medium\n"
        "ENVIRONMENT=uat\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    with patch.dict(
        os.environ,
        {
            "ENV_FILE": "runtime.env",
            "MAX_WORKERS": "7",
            "REPORT_LANGUAGE": "en",
        },
        clear=True,
    ):
        snapshot = _load_snapshot()
        config = snapshot.to_config(Config)

    assert config.max_workers == 7
    assert config.report_language == "en"
    assert config.news_strategy_profile == "medium"
    assert config.webui_port == 8000
    assert snapshot.profile == "uat"
    assert snapshot.provenance["MAX_WORKERS"].source is SettingSource.PROCESS_ENV
    assert snapshot.provenance["NEWS_STRATEGY_PROFILE"].source is SettingSource.ENV_FILE
    assert snapshot.provenance["APP_ENV"].source_name == "ENVIRONMENT"
    assert snapshot.provenance["APP_ENV"].is_alias is True
    assert snapshot.provenance["WEBUI_PORT"].source is SettingSource.DEFAULT


def test_runtime_settings_preserves_profile_matrix_and_environment_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.config.setup_env", lambda override=False: None)

    for profile, expected_days in {
        "ultra_short": 1,
        "short": 3,
        "medium": 7,
        "long": 30,
    }.items():
        with patch.dict(
            os.environ,
            {
                "NEWS_STRATEGY_PROFILE": profile,
                "NEWS_MAX_AGE_DAYS": "30",
                "MARKET_REVIEW_REGION": "both",
                "SCANNER_PROFILE": "us_liquid_v1",
            },
            clear=True,
        ):
            config = _load_snapshot().to_config(Config)

        assert config.news_strategy_profile == profile
        assert config.get_effective_news_window_days() == expected_days
        assert config.market_review_region == "both"
        assert config.scanner_profile == "us_liquid_v1"


def test_runtime_settings_records_absolute_env_file_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_path = tmp_path / "nested" / "runtime.env"
    env_path.parent.mkdir()
    env_path.write_text("MAX_WORKERS=5\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with patch.dict(
        os.environ,
        {"ENV_FILE": "nested/runtime.env"},
        clear=True,
    ):
        snapshot = _load_snapshot()

    assert snapshot.env_file == env_path.resolve()
    assert snapshot.env_file.is_absolute()
    assert snapshot.provenance["MAX_WORKERS"].env_file == env_path.resolve()


def test_runtime_settings_preserves_env_file_provenance_after_startup_preload(
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "runtime.env"
    env_path.write_text("MAX_WORKERS=6\n", encoding="utf-8")

    with patch.dict(
        os.environ,
        {"ENV_FILE": str(env_path)},
        clear=True,
    ):
        setup_env()
        snapshot = _load_snapshot()

    source = snapshot.provenance["MAX_WORKERS"]
    assert snapshot.to_config(Config).max_workers == 6
    assert source.source is SettingSource.ENV_FILE
    assert source.env_file == env_path.resolve()


def test_runtime_settings_records_alias_origin_when_values_agree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.config.setup_env", lambda override=False: None)
    with patch.dict(
        os.environ,
        {
            "TWELVEDATA_API_KEYS": "same-secret",
            "TWELVEDATA_API_KEY": "same-secret",
            "VISION_MODEL": "openai/agreed",
            "OPENAI_VISION_MODEL": "openai/agreed",
        },
        clear=True,
    ):
        snapshot = _load_snapshot()
        config = snapshot.to_config(Config)

    source = snapshot.provenance["TWELVE_DATA_API_KEYS"]
    assert config.twelve_data_api_keys == ["same-secret"]
    assert source.source_name == "TWELVEDATA_API_KEYS"
    assert source.is_alias is True
    assert config.vision_model == "openai/agreed"
    assert snapshot.conflicts == ()


def test_runtime_settings_reports_bounded_alias_conflicts_without_changing_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.config.setup_env", lambda override=False: None)
    with patch.dict(
        os.environ,
        {
            "APP_ENV": "production",
            "ENVIRONMENT": "uat",
            "TWELVE_DATA_API_KEYS": "canonical-secret",
            "TWELVEDATA_API_KEYS": "alias-secret",
            "VISION_MODEL": "openai/canonical",
            "OPENAI_VISION_MODEL": "openai/legacy",
            "UNRELATED_VALUE": "ignored",
        },
        clear=True,
    ):
        snapshot = _load_snapshot()
        config = snapshot.to_config(Config)

    assert config.twelve_data_api_keys == ["canonical-secret"]
    assert config.vision_model == "openai/canonical"
    assert [conflict.canonical_name for conflict in snapshot.conflicts] == [
        "APP_ENV",
        "TWELVE_DATA_API_KEYS",
        "VISION_MODEL",
    ]
    assert all(len(conflict.conflicting_names) <= 3 for conflict in snapshot.conflicts)


def test_runtime_settings_is_deeply_immutable_and_diagnostics_are_secret_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.config.setup_env", lambda override=False: None)
    secrets = {
        "OPENAI_API_KEY": "runtime-secret-sentinel",
        "WECHAT_WEBHOOK_URL": "https://example.invalid/private-hook",
        "STOCK_LIST": "600519,AAPL",
    }
    with patch.dict(os.environ, secrets, clear=True):
        snapshot = _load_snapshot()

    with pytest.raises(FrozenInstanceError):
        snapshot.profile = "production"  # type: ignore[misc]
    with pytest.raises(TypeError):
        snapshot.config_values["max_workers"] = 9  # type: ignore[index]
    assert snapshot.config_values["stock_list"] == ("600519", "AAPL")

    rendered = json.dumps(snapshot.diagnostics(), sort_keys=True)
    assert REDACTED_VALUE in rendered
    assert "runtime-secret-sentinel" not in rendered
    assert "private-hook" not in rendered
    assert "600519,AAPL" in rendered
    assert "runtime-secret-sentinel" not in repr(snapshot)
