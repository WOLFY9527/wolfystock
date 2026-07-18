# -*- coding: utf-8 -*-
"""Offline private-beta acceptance scorecard tests."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

from scripts.private_beta_acceptance_scorecard import (
    AcceptanceCategory,
    EvidenceRequirement,
    evaluate_acceptance_scorecard,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "private_beta_acceptance_scorecard.py"


def _tiny_spec() -> tuple[AcceptanceCategory, ...]:
    return (
        AcceptanceCategory(
            id="alpha",
            label="Alpha category",
            objective="Alpha objective.",
            requirements=(
                EvidenceRequirement(
                    id="alpha_evidence",
                    path="evidence/alpha.txt",
                    tokens=("home", "scanner"),
                    description="Alpha evidence exists.",
                ),
            ),
        ),
        AcceptanceCategory(
            id="beta",
            label="Beta category",
            objective="Beta objective.",
            requirements=(
                EvidenceRequirement(
                    id="beta_evidence",
                    path="evidence/beta.txt",
                    tokens=("redacted",),
                    description="Beta evidence exists.",
                ),
            ),
        ),
    )


def test_scorecard_accepts_repository_default_evidence_map() -> None:
    report = evaluate_acceptance_scorecard(repo_root=REPO_ROOT)

    assert report["status"] == "pass"
    assert report["finalStatus"] == "READY_FOR_REAL_MACHINE_UAT"
    assert report["privateBetaOnly"] is True
    assert report["publicLaunchApproved"] is False
    assert report["publicLaunchReady"] is False
    assert report["deterministic"] is True
    assert report["networkFree"] is True
    assert report["externalNetworkRequired"] is False
    assert report["providerRuntimeCalled"] is False
    assert report["secretsRequired"] is False
    assert report["summary"]["failedCategories"] == []

    category_ids = [category["id"] for category in report["categories"]]
    assert category_ids == [
        "first_login_home_start",
        "stock_research_route",
        "market_overview_route",
        "scanner_readiness_candidate_path",
        "backtest_cached_sample_readiness",
        "research_radar_evidence_path",
        "portfolio_risk_route",
        "admin_data_provider_readiness",
        "mobile_shell_header_sanity",
        "no_advice_language",
        "no_fake_data_claims",
        "provider_internal_redaction",
    ]
    assert all(category["status"] == "PASS" for category in report["categories"])


def test_scorecard_reports_missing_anchor_without_echoing_source_text(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "alpha.txt").write_text("home only", encoding="utf-8")
    (evidence_dir / "beta.txt").write_text("redacted", encoding="utf-8")

    report = evaluate_acceptance_scorecard(repo_root=tmp_path, category_specs=_tiny_spec())

    assert report["status"] == "fail"
    assert report["finalStatus"] == "NOT_READY_FOR_REAL_MACHINE_UAT"
    assert report["summary"] == {
        "categoryCount": 2,
        "passedCategoryCount": 1,
        "failedCategoryCount": 1,
        "failedCategories": ["alpha"],
    }
    alpha = report["categories"][0]
    assert alpha["status"] == "FAIL"
    assert alpha["failedRequirements"] == ["alpha_evidence"]
    alpha_requirement = alpha["requirements"][0]
    assert alpha_requirement["reasonCode"] == "evidence_anchor_missing"
    assert alpha_requirement["missingTokens"] == ["scanner"]
    assert "home only" not in json.dumps(report, ensure_ascii=False)


def test_scorecard_reports_missing_evidence_file(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "beta.txt").write_text("redacted", encoding="utf-8")

    report = evaluate_acceptance_scorecard(repo_root=tmp_path, category_specs=_tiny_spec())

    alpha_requirement = report["categories"][0]["requirements"][0]
    assert report["status"] == "fail"
    assert alpha_requirement["status"] == "FAIL"
    assert alpha_requirement["reasonCode"] == "evidence_file_unavailable"
    assert alpha_requirement["path"] == "evidence/alpha.txt"


def test_cli_json_and_human_summary_are_compact_and_deterministic() -> None:
    json_result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert json_result.returncode == 0, json_result.stderr
    payload = json.loads(json_result.stdout)
    assert payload["schemaVersion"] == "wolfystock_private_beta_acceptance_scorecard_v1"
    assert payload["status"] == "pass"
    assert payload["networkFree"] is True

    repeated_json_result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert repeated_json_result.returncode == 0, repeated_json_result.stderr
    assert repeated_json_result.stdout == json_result.stdout

    text_result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert text_result.returncode == 0, text_result.stderr
    assert "Private beta acceptance scorecard: PASS" in text_result.stdout
    assert "first_login_home_start: PASS" in text_result.stdout
    assert "provider_internal_redaction: PASS" in text_result.stdout


def test_scorecard_script_stays_offline_and_does_not_import_runtime_or_network_modules() -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert not imported.intersection(
        {
            "api",
            "src",
            "data_provider",
            "requests",
            "httpx",
            "socket",
            "urllib",
            "webbrowser",
            "playwright",
            "selenium",
        }
    )
