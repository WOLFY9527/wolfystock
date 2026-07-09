#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Sequence


ROOT = Path(__file__).resolve().parent.parent
MANUAL_PATH = ROOT / "docs" / "AI_PROJECT_MANUAL.md"
MANIFEST_PATH = ROOT / "docs" / "AI_PROJECT_MANUAL_SOURCES.json"
GENERATOR_PATH = "scripts/build_ai_project_manual.py"
GENERATOR_VERSION = 4
SCHEMA_VERSION = 2

PRUNED_DIR_NAMES = {
    ".cache",
    ".codex",
    ".codex-artifacts",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "artifacts",
    "backtest_outputs",
    "blob-report",
    "build",
    "coverage",
    "dist",
    "htmlcov",
    "node_modules",
    "playwright-report",
    "reports",
    "screenshots",
    "static",
    "test-results",
    "venv",
    "worktree_archives",
}

OUTPUT_MARKDOWN_PATHS = {"docs/AI_PROJECT_MANUAL.md"}

EXCLUSION_POLICY = [
    "Keep the manual source set intentionally tiny: AGENTS.md, README.md, and docs/DOCS_INDEX.md.",
    "Do not rediscover archive lanes, task reports, stale audits, old plans, or one-off acceptance snapshots as manual sources.",
    "Keep .github and .claude Markdown files as governance/workflow mirrors when required by scripts/check_ai_assets.py, but do not treat them as handbook sources.",
    "Keep issue and PR templates as GitHub workflow assets, not project handbook chapters.",
    "Exclude generated outputs, local evidence, fixture READMEs, language duplicates, broad legacy guides, and dependency/build/cache folders.",
    "When durable knowledge is needed, merge it into this deterministic generator/manual instead of adding another index or archive file.",
]


@dataclass(frozen=True)
class SourceRef:
    path: str
    purpose: str
    categories: tuple[str, ...]


@dataclass(frozen=True)
class ManualSection:
    key: str
    title: str
    body: str
    source_paths: tuple[str, ...]
    update_trigger: str
    validation: str


@dataclass(frozen=True)
class GeneratedOutputs:
    manual: str
    manifest_text: str
    source_count: int
    discovery: dict[str, object]


SOURCE_REFS = [
    SourceRef("AGENTS.md", "repository AI-agent rules and hard safety boundaries", ("governance", "workflow")),
    SourceRef("README.md", "human product entrypoint and supported run commands", ("product", "onboarding")),
    SourceRef("docs/DOCS_INDEX.md", "tiny canonical documentation pointer", ("governance", "sources")),
]

SOURCE_BY_PATH = {source.path: source for source in SOURCE_REFS}

SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password|authorization|cookie|session[_-]?id|webhook|private[_-]?key)\b\s*[:=]\s*['\"]?([^'\"\s`]+)"
)


def rel_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def is_safe_placeholder(value: str) -> bool:
    normalized = value.strip().strip("\"'").strip()
    lower = normalized.lower()
    if not normalized:
        return True
    if lower in {"none", "null", "nil", "true", "false", "placeholder", "todo", "tbd", "example", "sample", "dummy", "mock", "fake"}:
        return True
    if lower in {"x", "xx", "xxx", "changeme", "change_me", "change-me"}:
        return True
    if "example" in lower or "sample" in lower or "dummy" in lower or "mock" in lower:
        return True
    if "redacted" in lower or "masked" in lower:
        return True
    if "<" in lower and ">" in lower:
        return True
    if normalized.startswith("$") or normalized.startswith("${"):
        return True
    if set(normalized) <= {"*", "x", "X", "_", ".", "/", "-"}:
        return True
    return False


def looks_secret_like(value: str) -> bool:
    normalized = value.strip().strip("\"'").strip()
    if is_safe_placeholder(normalized):
        return False
    if len(normalized) < 16:
        return False
    has_alpha = any(char.isalpha() for char in normalized)
    has_digit_or_symbol = any(char.isdigit() or char in "+/=_-." for char in normalized)
    return has_alpha and has_digit_or_symbol


def assert_no_obvious_secret_values(path: str, text: str) -> None:
    findings: list[str] = []
    for index, line in enumerate(text.splitlines(), start=1):
        match = SECRET_ASSIGNMENT_RE.search(line)
        if not match:
            continue
        if looks_secret_like(match.group(2)):
            findings.append(f"{path}:{index}")
    if findings:
        print("[manual-generator] possible sensitive source value found; refusing to generate", file=sys.stderr)
        for finding in findings:
            print(f"[manual-generator] inspect locally: {finding}", file=sys.stderr)
        raise SystemExit(2)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def first_heading(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def source_metadata(source: SourceRef) -> dict[str, object]:
    path = ROOT / source.path
    if not path.exists():
        raise FileNotFoundError(f"manual source does not exist: {source.path}")
    if not path.is_file():
        raise IsADirectoryError(f"manual source is not a file: {source.path}")
    data = path.read_bytes()
    text = data.decode("utf-8")
    assert_no_obvious_secret_values(source.path, text)
    return {
        "path": source.path,
        "title": first_heading(text, Path(source.path).name),
        "purpose": source.purpose,
        "categories": sorted(source.categories),
        "sha256": sha256_bytes(data),
        "bytes": len(data),
        "lineCount": len(text.splitlines()),
    }


def should_prune_dir(path: Path) -> bool:
    return path.name in PRUNED_DIR_NAMES


def exclusion_reason(path: str) -> str | None:
    if path in OUTPUT_MARKDOWN_PATHS:
        return "generated_manual_output"
    pure = PurePosixPath(path)
    parts = set(pure.parts)
    if path in SOURCE_BY_PATH:
        return None
    if path == "CLAUDE.md":
        return "required_ai_governance_symlink"
    if path.startswith(".github/"):
        return "required_github_workflow_markdown"
    if path.startswith(".claude/skills/"):
        return "required_repository_skill_asset"
    if path.startswith(".agents/skills/"):
        return "legacy_untracked_agent_mirror"
    if path.startswith("tests/fixtures/") and path.endswith("/README.md"):
        return "fixture_local_doc"
    if path in {"SKILL.md", "DESIGN.md"}:
        return "legacy_external_product_doc"
    if "archive" in parts:
        return "archive_or_stale_provenance"
    if path.endswith("_EN.md") or path.endswith("_CHT.md"):
        return "language_duplicate"
    if PurePosixPath(path).name.startswith("full-guide"):
        return "broad_legacy_guide"
    if parts & PRUNED_DIR_NAMES:
        return "generated_or_dependency_path"
    return "not_in_hard_collapse_source_set"


def discover_markdown_files() -> dict[str, object]:
    discovered: list[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(dirname for dirname in dirnames if not should_prune_dir(Path(dirpath) / dirname))
        for filename in sorted(filenames):
            if not filename.endswith(".md"):
                continue
            path = rel_path(Path(dirpath) / filename)
            if path in OUTPUT_MARKDOWN_PATHS:
                continue
            discovered.append(path)

    excluded = Counter()
    candidates: list[str] = []
    for path in sorted(discovered):
        reason = exclusion_reason(path)
        if reason:
            excluded[reason] += 1
        else:
            candidates.append(path)

    return {
        "markdownDiscovered": len(discovered),
        "candidateMarkdownAfterPolicy": len(candidates),
        "includedSourceCount": len(SOURCE_REFS),
        "excludedByReason": dict(sorted(excluded.items())),
        "prunedDirectoryNames": sorted(PRUNED_DIR_NAMES),
    }


def manual_link(path: str) -> str:
    if path.startswith("docs/"):
        target = path[len("docs/") :]
    else:
        target = f"../{path}"
    return f"[`{path}`]({target})"


def source_list(paths: tuple[str, ...]) -> str:
    return ", ".join(manual_link(path) for path in paths)


def markdown_table(headers: tuple[str, ...], rows: Sequence[tuple[str, ...]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


SURFACE_ROWS = [
    ("Market Overview", "Regime, breadth, official risk, and macro first read", "`api/v1/endpoints/market_overview.py`, `src/services/market_overview_service.py`, `apps/dsa-web/src/pages/MarketOverviewPage.tsx`", "Partial until official risk, quote authority, and target-environment evidence are proven."),
    ("Scanner", "Candidate discovery and watchlist handoff", "`api/v1/endpoints/scanner.py`, `src/services/market_scanner_service.py`, `apps/dsa-web/src/pages/UserScannerPage.tsx`", "Partial; quote, history, universe, freshness, turnover, and packet readiness must fail closed."),
    ("Watchlist", "Saved symbols and row-level research queue", "`api/v1/endpoints/watchlist.py`, `src/services/watchlist_service.py`, `src/services/watchlist_research_overlay_service.py`, `apps/dsa-web/src/pages/WatchlistPage.tsx`", "Partial; row packets may lack quote freshness, catalyst age, or scanner lineage and must say so."),
    ("Stock Detail", "Symbol research packet and structure decision", "`api/v1/endpoints/stocks.py`, `src/services/stock_service.py`, `src/services/stock_structure_decision_service.py`", "Partial; no invented quote, fundamental, event, SEC, peer, or catalyst evidence."),
    ("Liquidity Monitor", "Capital pressure and stress context", "`api/v1/endpoints/liquidity_monitor.py`, `src/services/liquidity_monitor_service.py`, `apps/dsa-web/src/pages/LiquidityMonitorPage.tsx`", "Partial; macro, flow, and proxy rows remain capped unless official source authority exists."),
    ("Rotation Radar", "ETF/index family rotation context", "`api/v1/endpoints/market.py`, rotation services, `apps/dsa-web/src/pages/MarketRotationRadarPage.tsx`", "Partial; quote coverage, membership, and official source authority gate headline claims."),
    ("Options Lab", "Read-only options research console", "`api/v1/endpoints/options.py`, `src/services/options_lab_service.py`, `apps/dsa-web/src/pages/OptionsLabPage.tsx`", "Observation-only unless entitlement, redisplay, chain, Greeks, IV, OI, volume, and methodology proof exist."),
    ("Scenario Lab", "Bounded shock comparison", "`api/v1/endpoints/market.py`, `src/services/market_scenario_lab_engine.py`, `apps/dsa-web/src/pages/ScenarioLabPage.tsx`", "Partial; sample, request-supplied, fallback, or static baselines are observation-only."),
    ("Backtest", "Deterministic rule backtest and stored readback", "`api/v1/endpoints/backtest.py`, `src/core/rule_backtest_engine.py`, `src/services/backtest_service.py`, `apps/dsa-web/src/pages/BacktestPage.tsx`", "Research-useful v1 semantics; no optimizer, winner, allocation, or fake performance semantics."),
    ("Portfolio", "Accounts, holdings, cash, FX, ledger, risk, and attribution", "`api/v1/endpoints/portfolio.py`, `src/services/portfolio_service.py`, `apps/dsa-web/src/pages/PortfolioPage.tsx`", "Accounting authority is protected; price/FX lineage and broker/order implications must stay explicit."),
    ("Admin/Ops", "Operator observability and protected diagnostics", "`api/v1/endpoints/admin/*`, `src/services/admin_*`, `apps/dsa-web/src/pages/Admin*`", "Manual-review-gated; never leak raw provider, credential, security, or internal payload details."),
]

DATA_FAMILY_ROWS = [
    ("Official risk and volatility", "Partial", "VIX/volatility, rates, Fed liquidity, credit stress, and official macro rows must be source-authorized before score-grade claims."),
    ("Authorized quote spine", "Partial", "US/CN/HK quote and daily OHLCV snapshots need durable lineage, freshness, and redisplay/display authority."),
    ("Index/ETF membership", "Partial", "Rotation and market claims need official membership and weighting proof, not proxy-only membership."),
    ("Scanner universe/history", "Partial", "Universe, local history, quote freshness, turnover, and evidence packets must gate scanner summaries."),
    ("Fundamentals/filings/events", "Partial", "Ratios, filings, catalysts, events, and peers are fragmented; missing values remain missing."),
    ("Options chains/Greeks", "Blocked or observation-only", "No production-grade claims without provider entitlement, redisplay rights, methodology proof, and chain/Greek completeness."),
    ("Scenario baselines", "Partial", "Durable baseline snapshots and target-environment evidence are required before scenario state can be authoritative."),
    ("Backtest lineage", "Partial but research-useful", "Adjusted basis, calendar, point-in-time universe, reproducibility, and stored-result authority gate professional claims."),
    ("Factor research lineage", "Diagnostic-only", "No PIT universe or long-short factor-return contract yet; do not promote factor helpers as ranking truth."),
    ("Portfolio price/FX lineage", "Partial", "Valuation is only as credible as quote, FX, timestamp, source, and account/ledger provenance."),
]

RETAINED_MARKDOWN_ROWS = [
    ("`README.md`", "Short human entrypoint and run-command starter."),
    ("`AGENTS.md`", "Repository AI-collaboration source of truth and protected-domain hard rules."),
    ("`CLAUDE.md`", "Required symlink to `AGENTS.md` for Claude compatibility; retained because `scripts/check_ai_assets.py` enforces it."),
    ("`docs/AI_PROJECT_MANUAL.md`", "Generated comprehensive handbook for AI workers and maintainers."),
    ("`docs/DOCS_INDEX.md`", "Tiny pointer to canonical docs; no archive lane or broad index."),
    ("`docs/CHANGELOG.md`", "Short compatibility file retained because release tooling still reads this path."),
    ("`.github/*.md`", "GitHub Copilot/instruction/issue/PR workflow assets."),
    ("`.claude/skills/*.md`", "Required repository skill assets checked by AI governance tooling."),
]


def render_table(headers: tuple[str, ...], rows: Sequence[tuple[str, ...]]) -> str:
    return "\n".join(markdown_table(headers, rows))


SECTIONS = [
    ManualSection(
        key="project-identity",
        title="Project Identity And Product Purpose",
        body=(
            "WolfyStock is a professional financial research terminal for market operators, discretionary research, "
            "and portfolio workflows across US, CN, and HK markets. It combines market context, scanner discovery, "
            "watchlists, rule backtesting, portfolio tracking, provider diagnostics, admin observability, and AI-assisted "
            "research in a Python/FastAPI plus React/TypeScript codebase.\n\n"
            "The product solves the problem of fragmented research evidence: market regime, quote/history readiness, "
            "portfolio exposure, scenario shocks, options context, and backtest evidence are easy to confuse when they "
            "come from different providers and freshness levels. WolfyStock's durable direction is to show the evidence, "
            "source authority, lineage, and readiness boundary before any research conclusion.\n\n"
            "It is not a broker, order-entry surface, retail trading game, or unconstrained LLM wrapper. All user-visible "
            "research must stay analytical and no-advice."
        ),
        source_paths=("README.md", "AGENTS.md"),
        update_trigger="Product positioning, target audience, or no-advice posture changes.",
        validation="Docs-only validation plus no-advice grep when user-visible wording changes.",
    ),
    ManualSection(
        key="architecture-overview",
        title="Architecture Overview",
        body=(
            "Main runtime entrypoints are `main.py` for analysis/local automation, `server.py` and `api/app.py` for the "
            "FastAPI app, `api/v1/router.py` for API grouping, `src/services/` for business services, `src/repositories/` "
            "for persistence boundaries, `src/schemas/` for DTO/schema contracts, `data_provider/` for provider adapters "
            "and fallback normalization, `bot/` for notification integrations, `apps/dsa-web/` for the web terminal, "
            "`apps/dsa-desktop/` for the Electron wrapper, `scripts/` for local and CI utilities, and `.github/workflows/` "
            "for CI/release automation.\n\n"
            "Maintain bounded contexts. Consumers should call public facades, API clients, schemas, DTOs, validators, and "
            "documented commands. Do not reach into private engines, repositories, provider clients, cache keys, ledger "
            "internals, or mutation code from another domain just to make a local task easier.\n\n"
            "Shared contracts, schema changes, root config, CI, dependency files, auth, provider runtime, broker/accounting, "
            "DB migrations, and frontend route-entry behavior are high-risk and require explicit task scope."
        ),
        source_paths=("AGENTS.md", "README.md"),
        update_trigger="Runtime entrypoints, module ownership, public contracts, or high-risk boundary rules change.",
        validation="Run the focused gate for the touched module plus `python scripts/check_ai_assets.py` for AI-governance edits.",
    ),
    ManualSection(
        key="frontend-surfaces",
        title="Frontend Surfaces",
        body=(
            render_table(
                ("Surface", "Purpose", "Primary ownership", "Readiness boundary"),
                SURFACE_ROWS,
            )
            + "\n\n"
            "Frontend work should preserve the operator-terminal posture: dense but legible, route-first, evidence-first, "
            "and calm. Prefer tables, rows, rails, drawers, strips, and explicit disclosure states over generic card sprawl. "
            "Each route should make the primary research task visible in the first viewport and should keep raw provider, "
            "cache, schema, debug, credential, and fallback internals out of consumer copy."
        ),
        source_paths=("README.md", "AGENTS.md"),
        update_trigger="Route map, page ownership, consumer copy, route IA, or visual system changes.",
        validation="Frontend tests/lint/build plus browser or screenshot evidence when UI source changes.",
    ),
    ManualSection(
        key="backend-api-service-structure",
        title="Backend API And Service Structure",
        body=(
            "Backend/API work should keep API routers thin, services authoritative for business semantics, repositories "
            "responsible for persistence, schemas/DTOs explicit, and provider adapters isolated behind provider-runtime "
            "boundaries. FastAPI endpoints should not embed scanner ranking math, portfolio accounting, provider fallback "
            "ordering, auth policy, or report rendering internals.\n\n"
            "Core API families include auth, analysis, history, stocks, scanner, watchlist, market overview, market/scenario, "
            "liquidity, rotation, options, portfolio, backtest, quant, system, usage, admin, and diagnostics. Additive fields "
            "are preferred over breaking response contracts; deleted or renamed fields require client compatibility review.\n\n"
            "For Python changes, prefer `./scripts/ci_gate.sh`. At minimum run `python -m py_compile <changed_python_files>` "
            "and the closest deterministic tests. Protected semantic changes need focused regression evidence."
        ),
        source_paths=("AGENTS.md", "README.md"),
        update_trigger="API families, service boundaries, schema contracts, report payloads, or validation routing changes.",
        validation="Backend gate or closest pytest/py_compile evidence; wider gates for protected/shared contracts.",
    ),
    ManualSection(
        key="data-reality",
        title="Data Providers And Data Reality Boundaries",
        body=(
            "Provider runtime owns provider order, fallback, retry/circuit behavior, timeout posture, freshness labels, "
            "source authority, display rights, optional enrichment budgets, sanitized diagnostics, and cache/local-first "
            "behavior. Do not reorder providers, deepen live fallback, add broad optional fanout, or expose raw provider "
            "payloads without explicit scope.\n\n"
            "Fallback, cached, proxy, repaired, inferred, fixture, synthetic, dry-run, parser-only, request-supplied, and "
            "observation-only data must remain visibly not-live and not-decision-grade. Missing data stays missing; do not "
            "fabricate quote, fundamental, event, IV, Greek, bid/ask, OI, volume, FX, benchmark, or source-freshness fields.\n\n"
            + render_table(("Data family", "Readiness", "Operational boundary"), DATA_FAMILY_ROWS)
        ),
        source_paths=("AGENTS.md", "README.md"),
        update_trigger="Provider routing, source authority, data readiness, freshness, lineage, or professional-roadmap changes.",
        validation="Provider/cache/freshness tests, no-live-call proof when relevant, and raw-provider leakage scans.",
    ),
    ManualSection(
        key="domain-boundaries",
        title="Market, Options, Macro, Liquidity, Backtest, Scenario, And Portfolio Domains",
        body=(
            "Market Overview, Liquidity, and Rotation depend on official risk, macro, ETF/index quote coverage, and membership "
            "authority. They may show bounded context, but they must not convert proxy breadth or quote-derived approximations "
            "into score-grade institutional claims.\n\n"
            "Options Lab is a read-only experiment console. It is not an execution surface, strategy-ranking engine, or order "
            "workflow. Fixture/dry-run providers and disabled live stubs must fail closed until entitlement, redisplay rights, "
            "chain completeness, Greeks/IV/OI/volume methodology, and display authority are proven.\n\n"
            "Scenario Lab compares bounded shocks. Request-supplied, fallback, static, sample, or stale baselines are observation-only "
            "and must not imply execution readiness.\n\n"
            "Backtest owns deterministic rule evaluation, stored result readback, exports, compare workflows, and research-useful "
            "v1 semantics. Do not change fills, costs, metrics, benchmark semantics, parameter/winner meaning, local-only universe "
            "execution, or stored-result authority without explicit versioning and focused tests.\n\n"
            "Portfolio owns accounts, holdings, cash, transactions, P&L, FX/native currency, cost basis, broker sync/import overlays, "
            "ledger mutations, and read projections. UI work must not recalculate accounting authority or imply broker order execution."
        ),
        source_paths=("AGENTS.md", "README.md"),
        update_trigger="Any domain readiness, public copy, protected math/accounting, options authority, or macro/liquidity source change.",
        validation="Domain-focused tests plus no-advice and leakage checks; never use unrelated green tests as proof.",
    ),
    ManualSection(
        key="professional-roadmap",
        title="Professional Analytics Roadmap And Readiness",
        body=(
            "The professional roadmap is not a promise that a family is live. It is an ordered readiness map:\n\n"
            "1. Official VIX/volatility and macro/rates/Fed-liquidity source authority.\n"
            "2. Authorized US/CN/HK quote spine with lineage, freshness, and display rights.\n"
            "3. US index/ETF quote coverage and official membership/weight proofs.\n"
            "4. Scanner universe, history, turnover, and quote-readiness gates.\n"
            "5. Watchlist row packet and single-stock research packet completeness.\n"
            "6. Portfolio price and FX lineage.\n"
            "7. Options provider entitlement, redisplay rights, and methodology proof.\n"
            "8. Scenario durable baseline snapshots and target-environment evidence.\n"
            "9. Backtest dataset lineage, adjusted basis, calendar, PIT universe, and reproducibility gates.\n"
            "10. Factor research lineage with PIT membership and return contracts.\n\n"
            "Each step must expose blocked, partial, missing, unauthorized, stale, or observation-only states rather than hiding them behind positive copy."
        ),
        source_paths=("README.md", "AGENTS.md"),
        update_trigger="Professional data roadmap, readiness labels, or evidence-harness expectations change.",
        validation="Docs/generator validation for handbook changes; domain validation for implementation changes.",
    ),
    ManualSection(
        key="production-readiness-authority",
        title="Production Readiness Documentation Authority",
        body=(
            "Canonical owner: this generated manual, produced by `scripts/build_ai_project_manual.py`. After DOCS-006, "
            "the historical `docs/audits/deployment-readiness-checklist.md`, `docs/DEPLOY.md`, and `docs/DEPLOY_EN.md` "
            "are deprecated and must not be recreated as compatibility shims. Production-readiness tests should validate "
            "this section and the runtime preflight contract, not stale audit paths.\n\n"
            "Current public multi-user production posture remains **NO-GO** unless every repository-owned gate below has "
            "accepted sanitized target-environment evidence and manual release review. The manual is documentation authority, "
            "not launch approval.\n\n"
            + render_table(
                (
                    "Production concern",
                    "Repository-owned authority",
                    "Required evidence boundary",
                ),
                (
                    (
                        "Production environment marker",
                        "`APP_ENV=production` must be explicit in the sanitized production config contract.",
                        "Use `python3 scripts/production_config_readiness.py --contract <sanitized-production-config-contract.json>`; do not attach raw `.env` values.",
                    ),
                    (
                        "Authentication enablement",
                        "`ADMIN_AUTH_ENABLED=true` is required for public deployment; missing or false is local/dev only.",
                        "Auth-disabled public ingress is **NO-GO** and does not change runtime defaults.",
                    ),
                    (
                        "Fail-closed production posture",
                        "Missing required launch config, unsupported MFA scope, public SearXNG discovery, or unsafe CORS posture must fail closed.",
                        "Readiness output may include flag names, states, and bounded labels, not secret values or raw service URLs.",
                    ),
                    (
                        "CORS and CSRF allowlist",
                        "`CORS_ALLOW_ALL=false`, explicit `CORS_ORIGINS`, and explicit `CSRF_TRUSTED_ORIGINS` are required for public topology review.",
                        "Evidence must prove intended HTTPS origin behavior without echoing raw credential-bearing origins.",
                    ),
                    (
                        "Secret and config handling",
                        "Provider keys, cookies, sessions, DSNs, broker credentials, webhook URLs, raw provider payloads, stack traces, and raw `.env` values stay out of docs, logs, DOM, and release evidence.",
                        "Use presence states, redacted summaries, and sanitized validator output only.",
                    ),
                    (
                        "Docs/OpenAPI production exposure",
                        "Root docs/OpenAPI exposure must fail closed when production mode has public ingress but auth is disabled.",
                        "T286 behavior is read-only here; documentation must keep auth-disabled production exposure as **NO-GO**.",
                    ),
                    (
                        "Database and persistence readiness",
                        "Repository-owned DB readiness is bounded to local/storage checks, backup/PITR opt-in flags, restore/PITR evidence tooling, and owner-isolation smoke where implemented.",
                        "Do not claim Kubernetes, managed database, cloud secret-manager, or external backup infrastructure ownership.",
                    ),
                    (
                        "Runtime startup verification",
                        "`scripts/uat_runtime_harness.py` is the canonical local runtime verifier for clean tree, expected SHA, build, no-proxy localhost checks, asset identity, and evidence-bound stop.",
                        "UAT harness evidence is local runtime proof, not production launch approval.",
                    ),
                    (
                        "Health and readiness checks",
                        "Health/readiness coverage is limited to repository scripts, API/system endpoints, admin diagnostics, and release-summary validators that exist in this tree.",
                        "Missing target-environment evidence remains blocked, partial, or **NO-GO** rather than inferred.",
                    ),
                    (
                        "Rollback and operational validation",
                        "Rollback proof requires last-good commit/image, DB restore decision point where applicable, health checks, owner-isolation smoke, and sanitized operator evidence references.",
                        "No release, rollback, or live-enforcement approval is implied by docs alone.",
                    ),
                ),
            )
            + "\n\n"
            "Public deployment env flag matrix:\n\n"
            + render_table(
                (
                    "Flag / feature",
                    "Current behavior",
                    "Classification",
                    "Required target-env evidence before public launch",
                ),
                (
                    (
                        "`APP_ENV`",
                        "Enables production-mode security semantics only when explicitly set to `production`; missing or non-production values are local/dev only.",
                        "**GATED**",
                        "Sanitized config contract and target-environment evidence must show explicit production review without raw `.env` values.",
                    ),
                    (
                        "`VITE_API_URL`",
                        "Frontend uses same-origin API by default; explicit value only overrides API base for split-domain/static deployments.",
                        "**GATED**",
                        "Browser/ingress evidence must show the built frontend reaches the intended HTTPS API origin, CORS/CSRF origins match, and backend `:8000` is not directly public.",
                    ),
                    (
                        "`PUBLIC_API_ABUSE_LIMIT_*`",
                        "Process-local abuse limiter knobs are clamped and sanitized in diagnostics.",
                        "**SAFE**",
                        "Include sanitized limiter snapshot evidence and keep it labeled process-local; it is not quota, billing, auth, or distributed rate-limit enforcement.",
                    ),
                    (
                        "`CRYPTO_REALTIME_ENABLED`",
                        "Realtime crypto background behavior must be explicitly reviewed for outbound access and degraded behavior.",
                        "**AMBIGUOUS**",
                        "Target-environment evidence must show whether outbound Binance/WebSocket access is allowed, how failures degrade, and whether realtime is intentionally disabled.",
                    ),
                    (
                        "`SEARXNG_PUBLIC_INSTANCES_ENABLED`",
                        "Public-instance discovery is unsuitable for public launch unless separately accepted or disabled in favor of vetted self-hosted endpoints.",
                        "**NO-GO**",
                        "Public launch must use vetted self-hosted SearXNG endpoints, explicitly disable public discovery, or attach accepted operator risk evidence.",
                    ),
                ),
            )
            + "\n\n"
            "Classification rule: **SAFE** still requires target-environment evidence; **GATED** requires explicit config plus accepted evidence; "
            "**AMBIGUOUS** requires an operator decision; **NO-GO** applies whenever required target-environment evidence is missing, "
            "raw secrets would be needed to prove the claim, or a flag is used to imply provider, quota, auth/RBAC, database, broker, "
            "or notification live-enforcement approval."
        ),
        source_paths=("AGENTS.md", "README.md", "docs/DOCS_INDEX.md"),
        update_trigger="Production readiness docs authority, public deployment env flag classifications, or launch evidence policy changes.",
        validation="Production config readiness tests, manual generator freshness, AI asset check, and link/stale-path scans.",
    ),
    ManualSection(
        key="protected-domains",
        title="Protected Domains And Safety Rules",
        body=(
            "Stop before editing these domains unless the prompt explicitly authorizes the scope and validation path:\n\n"
            "- provider adapters, provider order, fallback, freshness, cache semantics, live-call behavior, credentials, and source authority;\n"
            "- scanner scoring, selection, thresholds, ranking, sorting, score contribution, and live/fallback labels;\n"
            "- backtest fills, costs, metrics, benchmarks, parameter/winner semantics, universe execution, and stored readback;\n"
            "- portfolio accounting, cash, holdings, transactions, P&L, FX/native currency, cost basis, broker sync/import, and ledger semantics;\n"
            "- auth/RBAC/security, sessions, cookies, CSRF/CORS, password/token handling, MFA, and admin protection;\n"
            "- DB migrations, root config, package/lock files, CI, dependency updates, env templates, and external network behavior;\n"
            "- broker/order execution, trading CTAs, target prices, position sizing, and personalized financial advice.\n\n"
            "Do not introduce fake data, fallback payloads, placeholder readiness, hidden compatibility layers, raw provider leakage, "
            "or one-off Markdown reports as a way to satisfy a task."
        ),
        source_paths=("AGENTS.md",),
        update_trigger="Any protected boundary or safety policy changes.",
        validation="Focused tests for the exact protected semantic plus diff/status/secret/no-advice checks before reporting completion.",
    ),
    ManualSection(
        key="no-advice",
        title="No-Advice Policy",
        body=(
            "WolfyStock may provide research context, evidence, readiness state, scenario comparison, risk disclosure, and operational diagnostics. "
            "It must not provide direct instructions to buy, sell, hold, short, add, reduce, execute, route, or size positions for a user.\n\n"
            "Avoid user-facing copy that implies investment recommendation, guaranteed outcome, target price, execution readiness, risk-free action, "
            "or personalized suitability. Safer patterns are observation-only labels, evidence boundaries, uncertainty, data-source/freshness/lineage, "
            "and explicit no-advice wording. The Chinese no-advice anchor `数据不足，暂不形成结论。` is intentionally retained where product copy needs a compact blocked-state sentence.\n\n"
            "No-advice review should classify grep hits. Tests, negative assertions, source-code identifiers, and policy docs may contain forbidden words as guardrails; visible UI and generated reports need stricter review."
        ),
        source_paths=("AGENTS.md",),
        update_trigger="User-facing research copy, generated reports, product policy, options/backtest/portfolio wording, or no-advice guards change.",
        validation="Focused grep/classification plus relevant page/report tests.",
    ),
    ManualSection(
        key="validation-matrix",
        title="Validation Matrix",
        body=(
            "Use the smallest validation set that proves the touched behavior:\n\n"
            "- Docs/manual/generator: `python -m py_compile scripts/build_ai_project_manual.py`, `python scripts/build_ai_project_manual.py`, `python scripts/build_ai_project_manual.py --check`, `python -m pytest -q tests/scripts/test_build_ai_project_manual.py`, `python scripts/check_ai_assets.py`, `git diff --check`, `bash scripts/release_secret_scan.sh --base-ref origin/main`, inventory counts, and link sanity.\n"
            "- Backend Python: `./scripts/ci_gate.sh` when feasible; otherwise `python -m py_compile <changed_python_files>` plus closest deterministic pytest.\n"
            "- API/schema/auth/provider/protected contracts: backend focused tests, compatibility review, redaction/leakage checks, and wider gates when shared contracts are touched.\n"
            "- Web frontend: from `apps/dsa-web`, run dependency install only when needed, then `npm run lint`, `npm run build`, and concrete Vitest paths. Use browser/screenshot smoke when layout or visible UX changes.\n"
            "- Local UAT runtime harness: `python scripts/uat_runtime_harness.py --expected-sha \"$(git rev-parse HEAD)\"`, then use `python scripts/uat_runtime_harness.py --preflight --expected-sha \"$(git rev-parse HEAD)\" --evidence-path <run-evidence> --json` for read-only WorkBuddy qualification and `--stop-from-evidence --evidence-path <run-evidence> --json` for task-owned cleanup.\n\n"
            "> Shell note: commands using `./scripts/*.sh` and `$(git rev-parse HEAD)` are\n"
            "> POSIX-shell (bash/sh) syntax. On Windows run them from Git Bash, WSL, or any\n"
            "> shell providing a POSIX `sh` (e.g. `bash scripts/ci_gate.sh`). PowerShell uses\n"
            "> the same `$(...)` subexpression syntax, so the UAT `--expected-sha \"$(git rev-parse HEAD)\"`\n"
            "> invocations also work unchanged in PowerShell.\n"
            "- Desktop: build web first, then desktop build where platform allows.\n"
            "- Workflow/scripts/Docker: run the closest local deterministic script or syntax check and report unexecuted remote/infra gaps.\n\n"
            "Never claim tests passed unless the command actually ran in this workspace and succeeded."
        ),
        source_paths=("AGENTS.md", "README.md"),
        update_trigger="Validation commands, CI gates, protected test expectations, or docs/generator workflow changes.",
        validation="Run the validation relevant to this manual/generator when edited.",
    ),
    ManualSection(
        key="codex-workflow",
        title="Codex Workflow And Landing Changes",
        body=(
            "Start with read-only discovery. Confirm `pwd`, branch, and `git status`; read the current prompt, `AGENTS.md`, "
            "`README.md`, this manual, and the smallest code/docs context required. Respect task mode and workspace. In a "
            "`WORKTREE-WORKER` task, stay inside the specified worktree and branch.\n\n"
            "Do not push unless explicitly authorized. Do not commit unless the task asks for a commit or the current instruction "
            "grants auto-commit. Do not rebase, merge, delete branches/worktrees, or rewrite history unless the task explicitly "
            "requires it. If a task requires fetch/rebase before final report, run `git fetch origin`, rebase onto `origin/main`, "
            "rerun focused validation, and only then commit/report.\n\n"
            "Before final delivery: inspect `git diff`, run `git diff --check`, run required tests/checks, confirm no unexpected files "
            "or secrets, and report exact commands and results. Final reports should include status, changed files, validation, "
            "risk, final base commit, commit hash when created, final `git status`, and rollback command."
        ),
        source_paths=("AGENTS.md", "docs/DOCS_INDEX.md"),
        update_trigger="Task modes, git policy, final-report requirements, or AI workflow rules change.",
        validation="Docs/generator check and `python scripts/check_ai_assets.py` when governance assets change.",
    ),
    ManualSection(
        key="canonical-file-map",
        title="Current Canonical File Map",
        body=(
            "After DOCS-006, the repository intentionally avoids a large Markdown corpus. The canonical reading path should be:\n\n"
            "1. `README.md` for the human product entrypoint and run commands.\n"
            "2. `AGENTS.md` for current AI-agent rules and hard safety boundaries.\n"
            "3. `docs/AI_PROJECT_MANUAL.md` for the comprehensive project handbook.\n\n"
            "Retained Markdown categories:\n\n"
            + render_table(("File or lane", "Why retained"), RETAINED_MARKDOWN_ROWS)
            + "\n\n"
            "`docs/AI_PROJECT_MANUAL_SOURCES.json` is not Markdown; it records deterministic source hashes, generator metadata, "
            "discovery counts, and section provenance. `docs/DOCS_INDEX.md` should stay tiny and only point to canonical files. "
            "Archive and product-recovery Markdown lanes are no longer retained as active project knowledge."
        ),
        source_paths=("README.md", "AGENTS.md", "docs/DOCS_INDEX.md"),
        update_trigger="Canonical docs set, retained Markdown policy, or AI asset governance changes.",
        validation="Inventory before/after counts, link sanity, generator `--check`, and `python scripts/check_ai_assets.py`.",
    ),
    ManualSection(
        key="compressed-history",
        title="Compressed Project History",
        body=(
            "WolfyStock began as a scheduled stock-analysis and notification project, then accumulated web, desktop, provider, "
            "backtest, portfolio, admin, and AI-assisted research surfaces. Later work shifted the architecture toward bounded "
            "contexts, provider/source readiness, route-level research workbenches, and protected semantics around scanner, "
            "portfolio, backtest, auth/RBAC, broker/accounting, and provider runtime.\n\n"
            "Product-recovery and DATA-series work established the durable lesson that visible research value depends on real "
            "source authority: official risk/macro, authorized quote spine, scanner/watchlist packets, portfolio price/FX lineage, "
            "options entitlement, scenario baselines, and backtest dataset lineage must be explicit. Old audits, acceptance reports, "
            "launch checklists, design notes, and progress logs were useful for their moment, but their durable content now lives "
            "in this manual.\n\n"
            "DOCS-006 hard-collapsed the Markdown corpus: keep a short README, a short AGENTS rule entrypoint, this generated manual, "
            "the manifest, and required governance/workflow mirrors. Do not recreate old index/archive lanes for routine tasks."
        ),
        source_paths=("README.md", "docs/DOCS_INDEX.md"),
        update_trigger="Major project direction, docs-retention policy, or historical context changes.",
        validation="Docs-only validation and inventory count check.",
    ),
    ManualSection(
        key="ai-onboarding",
        title="AI Onboarding Checklist",
        body=(
            "For a new task:\n\n"
            "1. Confirm CWD, branch, and `git status --short --branch`.\n"
            "2. Read the user's task contract and protected/forbidden scope.\n"
            "3. Read `AGENTS.md`, `README.md`, and this manual.\n"
            "4. Run read-only discovery with `rg`, `rg --files`, source files, tests, and scripts. Do not edit during discovery.\n"
            "5. Classify the task as docs, backend, frontend, API/schema, provider, auth, portfolio, backtest, workflow, or review.\n"
            "6. If the task touches a protected domain, stop unless explicit scope and validation are present.\n"
            "7. Make the smallest relevant change; avoid new docs, indexes, archive lanes, or parallel implementations.\n"
            "8. Run the focused validation that proves the touched area.\n"
            "9. Inspect diff/status, secret scan when required, and link/Markdown sanity for docs work.\n"
            "10. If the prompt requires rebase, fetch/rebase and rerun focused validation before final report or commit.\n\n"
            "For docs tasks, the default answer is to update this manual/generator and delete stale Markdown after durable knowledge is absorbed."
        ),
        source_paths=("AGENTS.md", "README.md", "docs/DOCS_INDEX.md"),
        update_trigger="Onboarding order, docs model, or task execution policy changes.",
        validation="Generator check plus AI asset check.",
    ),
]

SECTION_KEYS = {section.key for section in SECTIONS}
if len(SECTION_KEYS) != len(SECTIONS):
    raise RuntimeError("Manual section keys must be unique")


def section_anchor(title: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", title.lower().replace("/", " "))
    return re.sub(r"\s+", "-", cleaned.strip())


def build_manual(source_meta: dict[str, dict[str, object]], discovery: dict[str, object]) -> str:
    lines: list[str] = [
        "# WolfyStock AI Project Manual",
        "",
        "> GENERATED FILE. DO NOT EDIT DIRECTLY.",
        ">",
        f"> Edit `{GENERATOR_PATH}` or the tiny canonical source files, then run `python {GENERATOR_PATH}`.",
        f"> Check freshness with `python {GENERATOR_PATH} --check`.",
        "",
        "Status: generated comprehensive project handbook after the DOCS-006 hard Markdown collapse.",
        "Audience: future AI models, Codex workers, review agents, maintainers, and humans assigning AI work.",
        "Authority: operational handbook and source map; `AGENTS.md` remains the repository AI-collaboration rule source.",
        "Do not use as: launch approval, protected-domain authorization, stale audit authority, trading advice, or replacement for current source/test inspection.",
        "",
        "## Table Of Contents",
        "",
    ]
    for section in SECTIONS:
        lines.append(f"- [{section.title}](#{section_anchor(section.title)})")
    lines.extend(["- [Source Map](#source-map)", "- [JSON Manifest](#json-manifest)", ""])

    for section in SECTIONS:
        missing_sources = [path for path in section.source_paths if path not in source_meta]
        if missing_sources:
            raise RuntimeError(f"section {section.key} references missing sources: {missing_sources}")
        lines.extend(
            [
                f"## {section.title}",
                "",
                section.body.strip(),
                "",
                f"Source provenance: {source_list(section.source_paths)}.",
                "",
            ]
        )

    source_rows = [
        (
            section.title,
            "<br>".join(f"`{path}`" for path in section.source_paths),
            section.update_trigger,
            section.validation,
        )
        for section in SECTIONS
    ]
    lines.extend(
        [
            "## Source Map",
            "",
            "This map is generated from the hard-collapse source set. The manual contains absorbed durable knowledge from retired docs, but only these canonical files remain source-tracked.",
            "",
        ]
    )
    lines.extend(markdown_table(("Manual section", "Tracked sources", "Update trigger", "Validation"), source_rows))
    lines.extend(
        [
            "",
            "## JSON Manifest",
            "",
            f"The machine-readable manifest is generated at `{MANIFEST_PATH.relative_to(ROOT).as_posix()}`. It records source paths, source hashes, generator metadata, section provenance, and Markdown discovery statistics.",
            "",
            "Current discovery summary:",
            "",
            f"- Markdown discovered after pruned directory rules, excluding this generated manual: {discovery['markdownDiscovered']}",
            f"- Candidate Markdown after hard-collapse policy: {discovery['candidateMarkdownAfterPolicy']}",
            f"- Curated sources included in this manual: {discovery['includedSourceCount']}",
            "",
            "Exclusion policy:",
            "",
        ]
    )
    lines.extend(f"- {rule}" for rule in EXCLUSION_POLICY)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def build_manifest(source_meta: dict[str, dict[str, object]], discovery: dict[str, object], manual_sha256: str) -> dict[str, object]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generator": {
            "path": GENERATOR_PATH,
            "version": GENERATOR_VERSION,
            "sha256": sha256_bytes((ROOT / GENERATOR_PATH).read_bytes()),
            "deterministic": True,
            "callsExternalServices": False,
            "requiresApiKeys": False,
            "readsProductionDataPaths": False,
        },
        "outputs": {
            "manual": MANUAL_PATH.relative_to(ROOT).as_posix(),
            "manifest": MANIFEST_PATH.relative_to(ROOT).as_posix(),
            "manualSha256": manual_sha256,
        },
        "discovery": discovery,
        "exclusionPolicy": EXCLUSION_POLICY,
        "includedSources": [source_meta[path] for path in sorted(source_meta)],
        "absorbedContentFamilies": [
            "architecture handbooks and module maps",
            "Codex execution, validation, prompt, report, model-routing, and protected-domain policies",
            "product-recovery DATA-series readiness contracts and acceptance snapshots",
            "market overview, scanner, watchlist, liquidity, rotation, options, scenario, backtest, portfolio, and admin domain docs",
            "provider/data reliability, source confidence, quota/cost, WS2/runtime, launch, security/RBAC/MFA, and frontend IA docs",
            "archive reports, task audits, old plans, historical progress logs, and stale acceptance notes",
        ],
        "sections": [
            {
                "key": section.key,
                "title": section.title,
                "sources": list(section.source_paths),
                "updateTrigger": section.update_trigger,
                "validation": section.validation,
            }
            for section in SECTIONS
        ],
    }


def write_text_if_changed(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def build_generated_outputs() -> GeneratedOutputs:
    source_meta = {source.path: source_metadata(source) for source in SOURCE_REFS}
    discovery = discover_markdown_files()
    manual = build_manual(source_meta, discovery) + "\n"
    manual_sha256 = hashlib.sha256(manual.encode("utf-8")).hexdigest()
    manifest = build_manifest(source_meta, discovery, manual_sha256)
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return GeneratedOutputs(
        manual=manual,
        manifest_text=manifest_text,
        source_count=len(source_meta),
        discovery=discovery,
    )


def check_generated_outputs(outputs: GeneratedOutputs) -> int:
    expected = {
        MANUAL_PATH: outputs.manual,
        MANIFEST_PATH: outputs.manifest_text,
    }
    stale_paths: list[str] = []
    for path, content in expected.items():
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            stale_paths.append(display_path(path))

    if stale_paths:
        print("[manual-generator] generated AI project manual is stale", file=sys.stderr)
        for path in stale_paths:
            print(f"[manual-generator] stale output: {path}", file=sys.stderr)
        print(f"[manual-generator] run: python {GENERATOR_PATH}", file=sys.stderr)
        return 1

    print("[manual-generator] generated AI project manual is fresh")
    print(f"included_sources={outputs.source_count} markdown_discovered={outputs.discovery['markdownDiscovered']}")
    return 0


def write_generated_outputs(outputs: GeneratedOutputs) -> None:
    write_text_if_changed(MANUAL_PATH, outputs.manual)
    write_text_if_changed(MANIFEST_PATH, outputs.manifest_text)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or check the generated WolfyStock AI project manual.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify generated manual and source manifest are current without writing files",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    outputs = build_generated_outputs()
    if args.check:
        return check_generated_outputs(outputs)

    write_generated_outputs(outputs)

    print(f"generated {MANUAL_PATH.relative_to(ROOT).as_posix()}")
    print(f"generated {MANIFEST_PATH.relative_to(ROOT).as_posix()}")
    print(f"included_sources={outputs.source_count} markdown_discovered={outputs.discovery['markdownDiscovered']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
