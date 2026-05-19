# -*- coding: utf-8 -*-
"""Offline contracts for the Coinbase public venue fixture parser."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from data_provider.coinbase_public_provider import parse_ticker_payload


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "coinbase_public" / "ticker_sample.json"


def test_parse_ticker_fixture_extracts_venue_scoped_observation_record() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    result = parse_ticker_payload(payload)

    assert result.provider_name == "Coinbase Public"
    assert result.provider_id == "coinbase_public"
    assert result.source_tier == "exchange_public"
    assert result.trust_level == "usable_with_caution"
    assert result.freshness_expectation == "near_real_time_venue_scoped"
    assert result.observation_only is True
    assert result.score_contribution_allowed is False
    assert result.warnings == ()

    assert len(result.records) == 1
    record = result.records[0]
    assert record.provider_name == "Coinbase Public"
    assert record.provider_id == "coinbase_public"
    assert record.source == "coinbase_public"
    assert record.source_tier == "exchange_public"
    assert record.trust_level == "usable_with_caution"
    assert record.freshness_expectation == "near_real_time_venue_scoped"
    assert record.observation_only is True
    assert record.score_contribution_allowed is False
    assert record.venue == "coinbase"
    assert record.product_id == "BTC-USD"
    assert record.symbol == "BTC-USD"
    assert record.base_currency == "BTC"
    assert record.quote_currency == "USD"
    assert record.price == 65001.42
    assert record.bid == 65001.41
    assert record.ask == 65001.43
    assert record.volume == 125.55
    assert record.as_of == "2026-05-19T10:15:30.123456Z"
    assert record.updated_at == "2026-05-19T10:15:30.123456Z"
    assert record.source_ref == "tests/fixtures/coinbase_public/ticker_sample.json"
    assert record.degradation_reason is None

    serialized = record.to_dict()
    assert serialized["providerName"] == "Coinbase Public"
    assert serialized["venue"] == "coinbase"
    assert "ticker" not in serialized
    assert "rawPayload" not in serialized
    assert "providerPayload" not in serialized


def test_parse_ticker_payload_accepts_json_text_and_is_deterministic() -> None:
    raw_text = FIXTURE_PATH.read_text(encoding="utf-8")

    text_result = parse_ticker_payload(raw_text)
    mapping_result = parse_ticker_payload(json.loads(raw_text))

    assert text_result.to_dict() == mapping_result.to_dict()


def test_parse_ticker_payload_degrades_safely_for_incomplete_fixture_payloads() -> None:
    result = parse_ticker_payload(
        {
            "sourceRef": "tests/fixtures/coinbase_public/incomplete_ticker.json",
            "ticker": {
                "bid": "bad-numeric",
                "ask": "2500.10",
                "volume": "",
            },
        },
        parser_timestamp="2026-05-20T01:02:03Z",
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record.product_id is None
    assert record.symbol is None
    assert record.base_currency is None
    assert record.quote_currency is None
    assert record.price is None
    assert record.bid is None
    assert record.ask == 2500.10
    assert record.volume is None
    assert record.as_of == "2026-05-20T01:02:03Z"
    assert record.updated_at == "2026-05-20T01:02:03Z"
    assert record.degradation_reason == "product_id_missing"
    assert [warning.code for warning in result.warnings] == [
        "missing_product_id",
        "missing_price",
        "invalid_numeric_field",
        "missing_timestamp",
    ]


def test_parse_ticker_payload_rejects_non_object_payloads_without_crashing() -> None:
    result = parse_ticker_payload(["not", "a", "mapping"])

    assert result.records == ()
    assert [warning.code for warning in result.warnings] == ["invalid_payload"]


def test_coinbase_public_parser_does_not_emit_env_or_secret_values() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    result = parse_ticker_payload(payload, parser_timestamp="2026-05-20T05:06:07Z")

    serialized = json.dumps(result.to_dict(), sort_keys=True)
    assert "super-secret-token" not in serialized
    assert "apiKey" not in serialized
    assert "secret" not in serialized.lower()


def test_coinbase_public_parser_import_is_metadata_only() -> None:
    script = """
import json
import importlib.util
from pathlib import Path
import sys

module_path = Path.cwd() / "data_provider" / "coinbase_public_provider.py"
spec = importlib.util.spec_from_file_location("coinbase_public_provider_standalone", module_path)
assert spec is not None
assert spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

blocked = [
    "requests",
    "httpx",
    "urllib.request",
    "urllib3",
]
print(json.dumps({name: name in sys.modules for name in blocked}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    imported = json.loads(completed.stdout)
    assert imported == {name: False for name in imported}
