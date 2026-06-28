from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "historical_ohlcv_cache_preflight.py"


def test_cli_defaults_to_dry_run_and_emits_safe_summary() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["dryRun"] is True
    assert payload["networkCallsEnabled"] is False
    assert payload["mutationEnabled"] is False
    assert payload["representativeSymbols"]["cn"] == ["600519", "000001", "601398"]
    assert payload["representativeSymbols"]["us"] == ["SPY", "QQQ", "AAPL", "MSFT"]
    assert "AkshareFetcher" not in json.dumps(payload, ensure_ascii=False)


def test_cli_seed_us_symbols_keeps_cn_out_unless_explicitly_requested() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--seed",
            "--us-symbols",
            "SPY",
            "--required-bars",
            "5",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["dryRun"] is True
    assert payload["networkCallsEnabled"] is False
    assert payload["mutationEnabled"] is False
    assert payload["representativeSymbols"]["cn"] == []
    assert payload["markets"]["cn"]["symbols"] == []
    assert [item["symbol"] for item in payload["markets"]["us"]["symbols"]] == ["SPY"]
