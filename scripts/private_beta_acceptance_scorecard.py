#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline private-beta acceptance scorecard.

The scorecard maps T-157 acceptance categories to existing deterministic
UAT/API/service evidence. It reads source and test files only; it does not open
browsers, call local services, call external networks, read credentials, mutate
runtime state, or approve public launch.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


SCHEMA_VERSION = "wolfystock_private_beta_acceptance_scorecard_v1"
TOOL_NAME = "scripts/private_beta_acceptance_scorecard.py"
PASS = "PASS"
FAIL = "FAIL"


@dataclass(frozen=True)
class EvidenceRequirement:
    """A deterministic file/token requirement for one acceptance category."""

    id: str
    path: str
    tokens: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class AcceptanceCategory:
    """Named private-beta acceptance category."""

    id: str
    label: str
    objective: str
    requirements: tuple[EvidenceRequirement, ...]


DEFAULT_CATEGORY_SPECS: tuple[AcceptanceCategory, ...] = (
    AcceptanceCategory(
        id="first_login_home_start",
        label="First-login/home start path",
        objective="Signed-in home shell shows research readiness, evidence coverage, and no blank first viewport.",
        requirements=(
            EvidenceRequirement(
                id="home_readiness_browser_acceptance",
                path="apps/dsa-web/e2e/readiness-browser-acceptance.smoke.spec.ts",
                tokens=(
                    "Home readiness strip is visible and consumer-safe",
                    "home-research-readiness-strip",
                    "expectNoHorizontalOverflow",
                    "unhandledApiRoutes",
                ),
                description="Home readiness strip is covered in desktop/mobile browser acceptance.",
            ),
            EvidenceRequirement(
                id="home_evidence_packet_smoke",
                path="apps/dsa-web/e2e/home-scanner-evidence-browser.smoke.spec.ts",
                tokens=(
                    "Home shows evidence packet strip without raw leakage or trading wording",
                    "home-evidence-packet-strip",
                    "expectSurfaceTextSafe",
                ),
                description="Home evidence packet strip stays visible and consumer-safe.",
            ),
        ),
    ),
    AcceptanceCategory(
        id="stock_research_route",
        label="Stock research route",
        objective="Single-stock research evidence is present, observation-only, and sanitized.",
        requirements=(
            EvidenceRequirement(
                id="stock_evidence_browser_route",
                path="apps/dsa-web/e2e/home-scanner-evidence-browser.smoke.spec.ts",
                tokens=(
                    "**/api/v1/stocks/*/evidence**",
                    "buildHomeEvidencePacketShell",
                    "buildHomeSingleStockEvidencePacketBase",
                    "home-evidence-packet-strip",
                ),
                description="Browser smoke loads stock evidence through the route harness.",
            ),
            EvidenceRequirement(
                id="stock_evidence_contract_redaction",
                path="tests/test_stock_evidence_packet.py",
                tokens=(
                    "rawProviderPayload",
                    "notInvestmentAdvice",
                    "observationOnly",
                ),
                description="Stock evidence packet contract keeps advice and raw payload boundaries explicit.",
            ),
        ),
    ),
    AcceptanceCategory(
        id="market_overview_route",
        label="Market overview route",
        objective="Market Overview has first-viewport research value without proxy/provider leakage.",
        requirements=(
            EvidenceRequirement(
                id="market_overview_smoke",
                path="apps/dsa-web/e2e/market-overview-scanner.smoke.spec.ts",
                tokens=(
                    "market overview keeps top metrics visible",
                    "market-overview-shell",
                    "market-overview-decision-readiness",
                    "expectNoMarketOverviewProxyLabelLeaks",
                ),
                description="Market Overview first viewport and proxy-label safety are covered.",
            ),
            EvidenceRequirement(
                id="market_overview_readiness_acceptance",
                path="apps/dsa-web/e2e/readiness-browser-acceptance.smoke.spec.ts",
                tokens=(
                    "Market Overview readiness strip is visible and consumer-safe",
                    "market-overview-decision-readiness",
                    "market-decision-semantics-advice-boundary",
                ),
                description="Market Overview readiness copy stays consumer-safe.",
            ),
        ),
    ),
    AcceptanceCategory(
        id="scanner_readiness_candidate_path",
        label="Scanner readiness/candidate path",
        objective="Scanner shows readiness, candidate evidence, and research-only candidate handoff.",
        requirements=(
            EvidenceRequirement(
                id="scanner_readiness_browser_acceptance",
                path="apps/dsa-web/e2e/readiness-browser-acceptance.smoke.spec.ts",
                tokens=(
                    "Scanner readiness strip is visible and consumer-safe",
                    "scanner-top-down-context-strip",
                    "scanner-result-row-NVDA",
                    "边界：仅研究观察",
                ),
                description="Scanner readiness strip and candidate row are covered in browser acceptance.",
            ),
            EvidenceRequirement(
                id="scanner_candidate_evidence_smoke",
                path="apps/dsa-web/e2e/home-scanner-evidence-browser.smoke.spec.ts",
                tokens=(
                    "Scanner shows candidate evidence coverage without raw leakage or trading wording",
                    "scanner-inline-candidate-evidence-NVDA",
                    "candidateResearchReadiness",
                    "candidateSourceProvenanceFrame",
                ),
                description="Scanner candidate evidence coverage is visible and sanitized.",
            ),
        ),
    ),
    AcceptanceCategory(
        id="backtest_cached_sample_readiness",
        label="Backtest cached sample/readiness path",
        objective="Backtest result and sample readiness evidence are available without live provider dependency.",
        requirements=(
            EvidenceRequirement(
                id="backtest_result_research_surface",
                path="apps/dsa-web/e2e/research-surfaces-launch.spec.ts",
                tokens=(
                    "Backtest result launch research surface",
                    "/zh/backtest/results/34",
                    "deterministic-result-page-hero",
                    "backtest-report-evidence-details",
                ),
                description="Backtest cached result route keeps KPI and evidence areas visible.",
            ),
            EvidenceRequirement(
                id="research_radar_backtest_sample_reader",
                path="tests/test_research_radar_service.py",
                tokens=(
                    "backtest_sample_reader",
                    "prepared_count",
                    "sample_readiness_state",
                    "backtestSamples",
                ),
                description="Research Radar joins backtest sample readiness without live execution.",
            ),
        ),
    ),
    AcceptanceCategory(
        id="research_radar_evidence_path",
        label="Research Radar evidence path",
        objective="Research Radar exposes scanner, stock, backtest, and data activation evidence safely.",
        requirements=(
            EvidenceRequirement(
                id="research_radar_service_evidence_hub",
                path="tests/test_research_radar_service.py",
                tokens=(
                    "test_research_radar_evidence_hub_surfaces_real_evidence_readiness",
                    "evidenceHub",
                    "scannerCandidates",
                    "stockReadiness",
                    "dataActivation",
                ),
                description="Service evidence hub composes cross-surface readiness.",
            ),
            EvidenceRequirement(
                id="research_radar_endpoint_redaction",
                path="tests/api/test_research_radar_endpoint.py",
                tokens=(
                    "/api/v1/research/radar",
                    "evidenceHub",
                    "ResearchRadarResponse",
                    "provider",
                    "raw",
                ),
                description="API endpoint returns typed, consumer-safe radar evidence.",
            ),
        ),
    ),
    AcceptanceCategory(
        id="portfolio_risk_route",
        label="Portfolio risk route",
        objective="Portfolio risk surface is present when available and stays read-only/user scoped.",
        requirements=(
            EvidenceRequirement(
                id="portfolio_risk_route_canonicalization",
                path="apps/dsa-web/e2e/viewport-route-canonicalization.smoke.spec.ts",
                tokens=(
                    "**/api/v1/portfolio/risk**",
                    "portfolioRiskPayload",
                    "portfolio-bento-page",
                    "no_advice_disclosure",
                ),
                description="Viewport route harness includes portfolio risk data.",
            ),
            EvidenceRequirement(
                id="portfolio_risk_launch_surface",
                path="apps/dsa-web/e2e/critical-route-launch-smoke.spec.ts",
                tokens=(
                    "portfolio route stays clean on desktop and mobile when mocked",
                    "/api/v1/portfolio/risk",
                    "portfolio-workspace-lanes",
                    "startsWith('POST ')",
                ),
                description="Portfolio launch smoke verifies risk route requests and no write calls.",
            ),
        ),
    ),
    AcceptanceCategory(
        id="admin_data_provider_readiness",
        label="Admin data/provider readiness route",
        objective="Admin provider readiness is diagnostic, redacted, read-only, and capability-gated.",
        requirements=(
            EvidenceRequirement(
                id="admin_provider_diagnostics_browser_smoke",
                path="apps/dsa-web/e2e/critical-route-launch-smoke.spec.ts",
                tokens=(
                    "provider diagnostics stays clean on desktop and mobile",
                    "/api/v1/admin/providers/circuits",
                    "expectProviderCircuitSecondaryDisclosure",
                    "assertAdminShell",
                ),
                description="Admin provider diagnostics browser surface stays clean and redacted.",
            ),
            EvidenceRequirement(
                id="admin_surface_readiness_contract",
                path="tests/api/test_admin_surface_readiness.py",
                tokens=(
                    "/api/v1/admin/ops/surface-readiness",
                    "noExternalCalls",
                    "providerCallsAttempted",
                    "readOnly",
                ),
                description="Admin surface readiness endpoint is read-only and does not call providers.",
            ),
        ),
    ),
    AcceptanceCategory(
        id="mobile_shell_header_sanity",
        label="Mobile shell/header sanity",
        objective="Mobile shell keeps route identity, header affordances, and navigation sane.",
        requirements=(
            EvidenceRequirement(
                id="mobile_route_canonicalization",
                path="apps/dsa-web/e2e/viewport-route-canonicalization.smoke.spec.ts",
                tokens=(
                    "mobile",
                    "390",
                    "844",
                    "canonical",
                ),
                description="Product and admin routes are checked at the mobile viewport.",
            ),
            EvidenceRequirement(
                id="mobile_shell_affordance",
                path="apps/dsa-web/e2e/shell-route-admin-affordance.smoke.spec.ts",
                tokens=(
                    "shell-mobile-active-route",
                    "打开导航菜单",
                    "expectNoHorizontalOverflow",
                    "expectNoForbiddenAffordanceText",
                ),
                description="Mobile active route and drawer affordances are checked.",
            ),
        ),
    ),
    AcceptanceCategory(
        id="no_advice_language",
        label="No advice language",
        objective="Visible acceptance evidence rejects advice, broker, order, and execution language.",
        requirements=(
            EvidenceRequirement(
                id="browser_no_advice_copy_guard",
                path="apps/dsa-web/e2e/critical-route-launch-smoke.spec.ts",
                tokens=(
                    "expectForbiddenTradingWordingAbsent",
                    "buy now",
                    "place order",
                    "AI recommends you buy",
                ),
                description="Browser smoke blocks unsafe trading wording.",
            ),
            EvidenceRequirement(
                id="uat_artifact_advice_guard",
                path="scripts/private_beta_uat_evidence_check.py",
                tokens=(
                    "ADVICE_OR_EXECUTION_PATTERN",
                    "advice_order_execution_claim_forbidden",
                    "brokerOrderTradePathEnabled",
                ),
                description="Private-beta evidence validator rejects advice/order claims.",
            ),
            EvidenceRequirement(
                id="research_radar_no_advice_contract",
                path="tests/test_research_radar_service.py",
                tokens=(
                    "FORBIDDEN_PUBLIC_RE",
                    "observationOnly",
                    "decisionGrade",
                    "noAdviceDisclosure",
                ),
                description="Research Radar service keeps no-advice and observation boundaries.",
            ),
        ),
    ),
    AcceptanceCategory(
        id="no_fake_data_claims",
        label="No fake data claims",
        objective="Synthetic, fixture, unavailable, and fallback data cannot masquerade as live/fresh readiness.",
        requirements=(
            EvidenceRequirement(
                id="single_stock_synthetic_boundary",
                path="tests/test_single_stock_evidence_contract.py",
                tokens=(
                    "test_synthetic_or_unavailable_evidence_never_claims_live_or_fresh_reliable",
                    "synthetic_source",
                    "live_or_fresh_reliable",
                    "authorityGrant",
                ),
                description="Single-stock evidence blocks synthetic/unavailable live claims.",
            ),
            EvidenceRequirement(
                id="source_confidence_degraded_boundary",
                path="tests/test_source_confidence_contract.py",
                tokens=(
                    "test_degraded_sources_are_capped_and_cannot_masquerade_as_live_or_fresh",
                    "synthetic_source",
                    "not in {\"live\", \"fresh\"}",
                    "networkCallsEnabled",
                ),
                description="Source confidence contracts cap degraded and synthetic evidence.",
            ),
        ),
    ),
    AcceptanceCategory(
        id="provider_internal_redaction",
        label="Provider/internal leakage",
        objective="Consumer and admin paths redact raw provider, credential, diagnostic, and internal details.",
        requirements=(
            EvidenceRequirement(
                id="consumer_api_redaction",
                path="tests/services/test_consumer_api_diagnostic_redaction.py",
                tokens=(
                    "FORBIDDEN_KEYS",
                    "project_consumer_api_payload",
                    "rawPayload",
                    "provider",
                    "requestId",
                ),
                description="Consumer API diagnostic projection removes provider/internal keys.",
            ),
            EvidenceRequirement(
                id="browser_raw_secret_redaction",
                path="apps/dsa-web/e2e/critical-route-launch-smoke.spec.ts",
                tokens=(
                    "expectNoRawLaunchArtifacts",
                    "expectNoBrokerCredentialOrOrderPayloads",
                    "expectNoRawSecretLikeText",
                    "mock-canary-raw-provider-payload",
                ),
                description="Browser smoke blocks raw launch artifacts, broker payloads, and secret-like text.",
            ),
        ),
    ),
)


def _read_text(repo_root: Path, relative_path: str) -> tuple[str, str | None]:
    path = repo_root / relative_path
    try:
        return path.read_text(encoding="utf-8"), None
    except OSError as exc:
        return "", f"{type(exc).__name__}: file_unavailable"


def _evaluate_requirement(
    repo_root: Path,
    requirement: EvidenceRequirement,
    source_cache: dict[str, tuple[str, str | None]],
) -> dict[str, Any]:
    if requirement.path not in source_cache:
        source_cache[requirement.path] = _read_text(repo_root, requirement.path)
    source, read_error = source_cache[requirement.path]
    missing_tokens = [token for token in requirement.tokens if token not in source]
    status = PASS if read_error is None and not missing_tokens else FAIL
    result: dict[str, Any] = {
        "id": requirement.id,
        "status": status,
        "path": requirement.path,
        "description": requirement.description,
        "requiredTokenCount": len(requirement.tokens),
        "matchedTokenCount": len(requirement.tokens) - len(missing_tokens),
    }
    if read_error is not None:
        result["reasonCode"] = "evidence_file_unavailable"
        result["readError"] = read_error
    elif missing_tokens:
        result["reasonCode"] = "evidence_anchor_missing"
        result["missingTokens"] = missing_tokens
    return result


def evaluate_acceptance_scorecard(
    *,
    repo_root: Path,
    category_specs: Sequence[AcceptanceCategory] = DEFAULT_CATEGORY_SPECS,
) -> dict[str, Any]:
    source_cache: dict[str, tuple[str, str | None]] = {}
    categories: list[dict[str, Any]] = []

    for category in category_specs:
        requirement_results = [
            _evaluate_requirement(repo_root, requirement, source_cache)
            for requirement in category.requirements
        ]
        failed_requirements = [
            requirement["id"] for requirement in requirement_results if requirement["status"] != PASS
        ]
        status = PASS if not failed_requirements else FAIL
        categories.append(
            {
                "id": category.id,
                "label": category.label,
                "objective": category.objective,
                "status": status,
                "requirements": requirement_results,
                "failedRequirements": failed_requirements,
            }
        )

    failed_categories = [category["id"] for category in categories if category["status"] != PASS]
    passed_count = len(categories) - len(failed_categories)
    final_status = "READY_FOR_REAL_MACHINE_UAT" if not failed_categories else "NOT_READY_FOR_REAL_MACHINE_UAT"

    return {
        "schemaVersion": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "status": "pass" if not failed_categories else "fail",
        "finalStatus": final_status,
        "privateBetaOnly": True,
        "publicLaunchApproved": False,
        "publicLaunchReady": False,
        "deterministic": True,
        "networkFree": True,
        "externalNetworkRequired": False,
        "browserOpenedByScorecard": False,
        "runtimeBehaviorChanged": False,
        "providerRuntimeCalled": False,
        "secretsRequired": False,
        "productionBehaviorChanged": False,
        "summary": {
            "categoryCount": len(categories),
            "passedCategoryCount": passed_count,
            "failedCategoryCount": len(failed_categories),
            "failedCategories": failed_categories,
        },
        "categories": categories,
    }


def _print_human_summary(report: dict[str, Any]) -> None:
    print(f"Private beta acceptance scorecard: {report['status'].upper()}")
    print(f"Final status: {report['finalStatus']}")
    summary = report["summary"]
    print(
        "Categories: "
        f"{summary['passedCategoryCount']}/{summary['categoryCount']} passed"
    )
    for category in report["categories"]:
        total = len(category["requirements"])
        passed = total - len(category["failedRequirements"])
        print(f"- {category['id']}: {category['status']} ({passed}/{total} evidence)")
        for requirement in category["requirements"]:
            if requirement["status"] == PASS:
                continue
            reason = requirement.get("reasonCode", "unknown")
            print(f"  - {requirement['id']}: {reason} [{requirement['path']}]")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the offline private-beta acceptance scorecard.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root. Defaults to the script parent repository.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = evaluate_acceptance_scorecard(repo_root=args.repo_root.resolve())
    if args.json:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        _print_human_summary(report)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
