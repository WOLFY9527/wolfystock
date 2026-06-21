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
GENERATOR_VERSION = 3
SCHEMA_VERSION = 1

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

OUTPUT_MARKDOWN_PATHS = {
    "docs/AI_PROJECT_MANUAL.md",
}

EXCLUSION_POLICY = [
    ".git/**",
    "node_modules/**",
    "dist/**",
    "static/**",
    "coverage/**",
    "reports/** unless explicitly high-value",
    "worktree_archives/**",
    "archive folders unless explicitly allowlisted",
    "docs/codex/audits/** task reports unless explicitly promoted by a current source",
    "local/generated evidence such as .codex/**, .claude/reviews/**, artifacts/**, screenshots/**, and test-results/**",
    "AI-governance mirrors such as CLAUDE.md and .github/copilot-instructions.md when AGENTS.md is available",
    "language duplicates and broad translated guides unless generating a language-specific manual",
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
    SourceRef("AGENTS.md", "canonical repository AI-agent rules", ("workflow", "governance")),
    SourceRef("README.md", "product purpose, feature set, stack, entry points", ("product", "architecture")),
    SourceRef("docs/product-recovery/WOLFYSTOCK_PRODUCT_RECOVERY_PLAN.md", "canonical product recovery plan and recovery posture", ("product-recovery", "product")),
    SourceRef("docs/product-recovery/DATA_COVERAGE_MATRIX.md", "repo-grounded data coverage matrix for product recovery", ("product-recovery", "data")),
    SourceRef("docs/product-recovery/DATA011_PACKET_CONSUMPTION_ACCEPTANCE.md", "packet consumption acceptance for first-read recovery", ("product-recovery", "acceptance")),
    SourceRef("docs/product-recovery/DATA016_FOCUSED_ACCEPTANCE.md", "focused first-read recovery acceptance", ("product-recovery", "acceptance")),
    SourceRef("docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md", "real data value acceptance and remaining blockers", ("product-recovery", "acceptance")),
    SourceRef("docs/product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md", "professional data source roadmap", ("product-recovery", "roadmap")),
    SourceRef("docs/product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md", "backtest professional upgrade audit", ("product-recovery", "backtest")),
    SourceRef("docs/product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md", "target-environment evidence harness", ("product-recovery", "evidence")),
    SourceRef("docs/product-recovery/DATA034_OPTIONS_PROVIDER_ENTITLEMENT_DECISION.md", "options provider entitlement decision", ("product-recovery", "options")),
    SourceRef("docs/product-recovery/DATA035_SCENARIO_DURABLE_BASELINE_SNAPSHOT_PLAN.md", "scenario durable baseline snapshot plan", ("product-recovery", "scenario")),
    SourceRef("docs/product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md", "authorized quote spine contract", ("product-recovery", "data")),
    SourceRef("docs/product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md", "backtest dataset lineage gate contract", ("product-recovery", "backtest")),
    SourceRef("docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md", "minimum symbol research packet contract", ("product-recovery", "packet")),
    SourceRef("docs/data/market-source-activation-blueprint.md", "official risk and quote source activation roadmap", ("data", "roadmap")),
    SourceRef("docs/DOCS_INDEX.md", "current documentation navigation and authority map", ("governance", "sources")),
    SourceRef("docs/DEPLOY.md", "deployment modes and boundary notes", ("deployment", "launch")),
    SourceRef("docs/ARCHIVE_INDEX.md", "archive lanes and safe-use rules", ("governance", "sources")),
    SourceRef("docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md", "system overview, routes, API groups, domain guide", ("architecture", "product")),
    SourceRef("docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md", "AI worker modes, stale-doc traps, validation expectations", ("workflow", "governance")),
    SourceRef("docs/architecture/file-governance-taxonomy.md", "active-vs-archive and generated artifact policy", ("governance", "sources")),
    SourceRef("docs/architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md", "bounded-context architecture and dependency rules", ("architecture", "protected-domains")),
    SourceRef("docs/architecture/backend-frontend-modular-maintenance-handbook.md", "module owners, first files, invariants, debug flow", ("architecture", "workflow")),
    SourceRef("docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md", "Codex operating guard, protected domains, validation policy", ("workflow", "protected-domains")),
    SourceRef("docs/codex/WOLFYSTOCK_CODEX_DISCOVERY_PROTOCOL.md", "Codex discovery protocol for compact prompts", ("workflow", "validation")),
    SourceRef("docs/codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md", "Codex execution policy for task modes and prompt compression", ("workflow", "validation")),
    SourceRef("docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md", "execution modes, prompt fields, commit/push rules", ("workflow", "validation")),
    SourceRef("docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md", "final report evidence contract", ("workflow", "validation")),
    SourceRef("docs/codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md", "smallest-safe validation tiers and path routing", ("validation",)),
    SourceRef("docs/codex/NO_ADVICE_REGRESSION_GUARDS.md", "no-advice regression guards and grep policy", ("validation", "product-safety")),
    SourceRef("docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md", "backend protected semantic boundaries", ("protected-domains",)),
    SourceRef("docs/codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md", "provider budget, quota, and routing rules", ("provider", "quota", "cost")),
    SourceRef("docs/codex/WOLFYSTOCK_BACKTEST_UNIVERSE_RULES.md", "backtest universe local-only guardrails", ("backtest", "protected-domains")),
    SourceRef("docs/audits/README.md", "active audit and launch authority index", ("launch", "sources")),
    SourceRef("docs/audits/public-launch-readiness-master.md", "executive public launch NO-GO verdict", ("launch",)),
    SourceRef("docs/audits/public-launch-gap-register.md", "detailed launch blocker register", ("launch",)),
    SourceRef("docs/audits/deployment-readiness-checklist.md", "release-candidate checklist and final gates", ("launch", "validation")),
    SourceRef("docs/audits/launch-acceptance-evidence-pack.md", "sanitized launch evidence contract", ("launch", "validation")),
    SourceRef("docs/audits/private-beta-readiness.md", "private beta boundary and non-approved areas", ("deployment", "launch")),
    SourceRef("docs/audits/auth-rbac-release-security-guide.md", "Auth/RBAC release review scope", ("auth", "security")),
    SourceRef("docs/audits/index-security-rbac-mfa.md", "security, RBAC, role-governance, MFA doc index", ("auth", "security")),
    SourceRef("docs/audits/admin-rbac-r5-coarse-fallback-removal-plan.md", "future coarse fallback removal plan", ("auth", "rbac")),
    SourceRef("docs/audits/security-mfa-secret-storage-hardening-plan.md", "deferred MFA secret and recovery hardening plan", ("auth", "mfa")),
    SourceRef("docs/portfolio/README.md", "portfolio domain entry point and safety rules", ("portfolio",)),
    SourceRef("docs/backtest/README.md", "backtest domain entry point and v1 semantics freeze", ("backtest",)),
    SourceRef("docs/backtest-system.md", "backtest APIs, async behavior, stored-first exports", ("backtest",)),
    SourceRef("docs/audits/backtest-portfolio-public-safety-audit.md", "portfolio/backtest public safety evidence", ("portfolio", "backtest", "launch")),
    SourceRef("docs/market-overview/README.md", "market overview domain entry point and boundary rules", ("market-overview", "product")),
    SourceRef("docs/scanner/README.md", "scanner and watchlist domain entry point and boundary rules", ("scanner", "product")),
    SourceRef("docs/liquidity/README.md", "liquidity domain entry point and boundary rules", ("liquidity", "product")),
    SourceRef("docs/rotation/README.md", "rotation domain entry point and boundary rules", ("rotation", "product")),
    SourceRef("docs/provider-data/README.md", "provider, data, freshness, cache, disclosure rules", ("provider", "data")),
    SourceRef("docs/audits/index-provider-data-options.md", "provider/data/options readiness index", ("provider", "options", "data")),
    SourceRef("docs/audits/index-cost-quota-observability.md", "cost, quota, provider budget, observability index", ("quota", "cost")),
    SourceRef("docs/audits/quota-reserve-release-operator-evidence-checklist.md", "quota reserve/release operator evidence", ("quota", "cost")),
    SourceRef("docs/operations/background-job-queue-boundary.md", "process-local async and first queue boundary", ("ws2", "runtime")),
    SourceRef("docs/operations/queue-ws2-metrics-production-readiness.md", "queue/WS2 metrics production-readiness notes", ("ws2", "runtime")),
    SourceRef("docs/operations/provider-capability-metadata.md", "provider capability metadata and inert source-confidence contract", ("provider", "data")),
    SourceRef("docs/audits/ws2-multi-instance-smoke-test-design.md", "multi-instance smoke design and acceptance criteria", ("ws2", "runtime", "launch")),
    SourceRef("docs/audits/ws2-multi-user-runtime-cost-control-design.md", "multi-user runtime, quota, cost, circuit baseline", ("ws2", "quota", "cost")),
    SourceRef("docs/options/README.md", "Options Lab domain entry point", ("options",)),
    SourceRef("docs/audits/options-provider-adapter-contract.md", "Options provider adapter and fixture/live boundary", ("options", "provider")),
    SourceRef("docs/audits/data-pipeline-r2-progressive-enrichment.md", "progressive enrichment contract and future async merge", ("data-pipeline", "provider")),
    SourceRef("docs/audits/data-quality-user-disclosure-policy.md", "user-facing source, freshness, and data-quality disclosure", ("data", "frontend")),
    SourceRef("docs/audits/trading-no-advice-product-policy.md", "no-advice and no-order product safety policy", ("product", "safety")),
    SourceRef("docs/frontend/README.md", "current frontend route-family and visual authority entry point", ("frontend",)),
    SourceRef("docs/frontend/visual-system.md", "Linear OS route taxonomy, layout, primitives, IA", ("frontend", "ui")),
    SourceRef("docs/frontend/validation-playbook.md", "frontend/browser evidence and visual validation expectations", ("frontend", "validation")),
    SourceRef("docs/frontend/WOLFYSTOCK_FRONTEND_NOISE_BUDGET.md", "frontend noise, density, and disclosure budget", ("frontend", "ui")),
    SourceRef("docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md", "consumer data-quality UX wording and disclosure rules", ("frontend", "data")),
    SourceRef("docs/frontend/WOLFYSTOCK_ADMIN_MAINTENANCE_OS.md", "admin maintenance OS IA and operator UX rules", ("frontend", "admin")),
    SourceRef("docs/quant-duckdb-engine.md", "DuckDB diagnostic-only engine posture", ("experimental", "data")),
    SourceRef("docs/data-reliability/provider-source-confidence-contract.md", "provider source confidence and fail-closed boundary", ("data", "experimental")),
    SourceRef("docs/alerts/README.md", "alerts domain entry point and safety posture", ("experimental", "notifications")),
]

SOURCE_BY_PATH = {source.path: source for source in SOURCE_REFS}


SECTIONS = [
    ManualSection(
        key="start-here",
        title="Start Here: Authority And Operating Posture",
        body=(
            "Use this generated manual as the first navigation layer for AI-assisted work. "
            "It is not a new rule source and does not replace current source inspection, tests, "
            "or task-specific prompt boundaries.\n\n"
            "- Current user prompts and explicit allowed/forbidden diffs come first.\n"
            "- `AGENTS.md` remains the repository AI-collaboration source of truth.\n"
            "- Current code, scripts, tests, and active docs beat memory, stale screenshots, old audits, and generated artifacts.\n"
            "- If a task is near protected semantics, stop unless the prompt explicitly scopes that domain and gives a validation path.\n"
            "- Read-only tasks mean no edits, no artifacts, no staging, no commits, and no pushes."
        ),
        source_paths=(
            "AGENTS.md",
            "docs/DOCS_INDEX.md",
            "docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md",
            "docs/architecture/file-governance-taxonomy.md",
        ),
        update_trigger="AI governance, source authority, archive policy, or generated-artifact policy changes.",
        validation="Docs/generator validation plus `python scripts/check_ai_assets.py` when AI governance assets change.",
    ),
    ManualSection(
        key="product-boundary",
        title="Product Purpose And Current Deployment Boundary",
        body=(
            "WolfyStock is a professional financial research terminal. It combines market overview, scanner discovery, "
            "watchlists, rule backtesting, portfolio tracking, AI-assisted analysis, provider diagnostics, and admin observability.\n\n"
            "It is not a broker, order-entry surface, generic retail trading app, or unbounded LLM wrapper. Public launch remains "
            "NO-GO until security, provider/data, WS2, cost/quota, portfolio/backtest safety, and deployment evidence gates are accepted. "
            "Treat private-beta and local tooling as reviewed integration surfaces, not launch approval.\n\n"
            "Current safe posture is analytical and no-advice. Do not add buy/sell/order affordances, broker execution, or personalized "
            "financial advice unless a separate safety-reviewed task explicitly scopes that change."
        ),
        source_paths=(
            "README.md",
            "docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md",
            "docs/DEPLOY.md",
            "docs/audits/private-beta-readiness.md",
            "docs/audits/public-launch-readiness-master.md",
            "docs/audits/trading-no-advice-product-policy.md",
        ),
        update_trigger="Product positioning, deployment mode, private beta, no-advice, or launch verdict changes.",
        validation="Docs-only validation for docs changes; release/UAT evidence for deployment posture changes.",
    ),
    ManualSection(
        key="hard-stops",
        title="Protected Domains And Hard Stops",
        body=(
            "Treat these as hard stops unless the task explicitly scopes them and gives a focused validation path:\n\n"
            "- provider order, credentials, live-call paths, cache/freshness labels, source authority, score contribution, and right-to-display;\n"
            "- scanner scoring, selection, thresholds, ranking, sorting, and live/fallback labels;\n"
            "- backtest math, fills, costs, metrics, benchmarks, stored result semantics, and parameter/winner semantics;\n"
            "- portfolio accounting, cash, holdings, P&L, FX/native currency, cost basis, sync/import/replay, and ledger semantics;\n"
            "- auth/RBAC/security, sessions, CSRF/CORS, password/token handling, MFA, and admin protection;\n"
            "- DB migrations, package/config/env, and external network behavior;\n"
            "- direct trading advice, buy/sell/order CTAs, target prices, position sizing, or synthetic readiness claims.\n\n"
            "No fake data, no fallback promotion, no hidden compatibility layer, and no advice. Changes in these areas need the matching guard docs and "
            "focused validation before anyone should call the result safe."
        ),
        source_paths=(
            "AGENTS.md",
            "docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md",
            "docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md",
            "docs/codex/NO_ADVICE_REGRESSION_GUARDS.md",
            "docs/audits/trading-no-advice-product-policy.md",
            "docs/data-reliability/provider-source-confidence-contract.md",
            "docs/operations/provider-capability-metadata.md",
        ),
        update_trigger="Protected-domain boundaries, no-advice policy, provider/source confidence, or hard-stop validation rules change.",
        validation="Read the guard docs first; then use focused tests and the smallest validation tier that proves the protected semantic stayed intact.",
    ),
    ManualSection(
        key="product-surfaces-data-reality",
        title="Product Surfaces And Data Reality",
        body=(
            "WolfyStock is for professional market and stock research support. It is not generic stock-app filler, a broker surface, or a direct advice engine.\n\n"
            "{{PRODUCT_SURFACE_TABLE}}\n\n"
            "{{PROFESSIONAL_DATA_FAMILY_TABLE}}\n\n"
            "Roadmap order:\n"
            "- Official VIX / volatility.\n"
            "- Macro / rates / Fed liquidity.\n"
            "- US index / ETF quote coverage.\n"
            "- Scanner universe / history / quote readiness.\n"
            "- Watchlist row packet and Stock research packet.\n"
            "- Portfolio price / FX lineage.\n"
            "- Options rights and methodology proof.\n"
            "- Scenario baseline snapshots.\n"
            "- Backtest dataset lineage.\n"
            "- Factor research lineage.\n\n"
            "Missing families stay missing, blocked, partial, or observation-only. Do not turn proxy, cached, synthetic, fallback, or fixture data into "
            "live, fresh, decision-grade evidence. Do not output direct trading advice."
        ),
        source_paths=(
            "README.md",
            "docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md",
            "docs/market-overview/README.md",
            "docs/scanner/README.md",
            "docs/liquidity/README.md",
            "docs/rotation/README.md",
            "docs/options/README.md",
            "docs/portfolio/README.md",
            "docs/backtest/README.md",
            "docs/backtest-system.md",
            "docs/product-recovery/WOLFYSTOCK_PRODUCT_RECOVERY_PLAN.md",
            "docs/product-recovery/DATA_COVERAGE_MATRIX.md",
            "docs/product-recovery/DATA011_PACKET_CONSUMPTION_ACCEPTANCE.md",
            "docs/product-recovery/DATA016_FOCUSED_ACCEPTANCE.md",
            "docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md",
            "docs/product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md",
            "docs/product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md",
            "docs/product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md",
            "docs/product-recovery/DATA034_OPTIONS_PROVIDER_ENTITLEMENT_DECISION.md",
            "docs/product-recovery/DATA035_SCENARIO_DURABLE_BASELINE_SNAPSHOT_PLAN.md",
            "docs/product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md",
            "docs/product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md",
            "docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md",
            "docs/data/market-source-activation-blueprint.md",
            "docs/data-reliability/provider-source-confidence-contract.md",
            "docs/operations/provider-capability-metadata.md",
            "docs/audits/data-quality-user-disclosure-policy.md",
            "docs/audits/options-provider-adapter-contract.md",
            "docs/audits/backtest-portfolio-public-safety-audit.md",
            "docs/audits/trading-no-advice-product-policy.md",
        ),
        update_trigger="Surface maps, data-roadmap boundaries, or any professional data family readiness change.",
        validation="Use the source docs and current code/tests to classify every surface and family as ready, partial, blocked, missing, unauthorized, or observation-only before editing anything else.",
    ),
    ManualSection(
        key="architecture-surfaces",
        title="Architecture And Major Surfaces",
        body=(
            "Maintain WolfyStock as bounded-context modules with narrow public interfaces. Consumers should call facades, schemas, DTOs, "
            "API clients, validators, and documented commands instead of private engines, repositories, provider clients, cache keys, or mutation internals.\n\n"
            "Major runtime surfaces are `main.py`, `server.py`, `api/app.py`, `api/v1/router.py`, `src/services/`, `src/repositories/`, "
            "`data_provider/`, `apps/dsa-web/`, `apps/dsa-desktop/`, `scripts/`, and `.github/workflows/`.\n\n"
            "Main product routes include Home, Scanner, Watchlist, Market Overview, Liquidity Monitor, Rotation Radar, Portfolio, Backtest, "
            "Options Lab, Settings, and Admin/Ops pages. API groups live under `/api/v1` for auth, analysis, history, stocks, backtest, scanner, "
            "system, usage, portfolio, watchlist, market, quant, options, and admin families."
        ),
        source_paths=(
            "docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md",
            "docs/architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md",
            "docs/architecture/backend-frontend-modular-maintenance-handbook.md",
            "README.md",
        ),
        update_trigger="Route map, API group, module ownership, dependency direction, or first-files debug flow changes.",
        validation="Focused validation for touched surface; architecture docs-only validation for handbook-only changes.",
    ),
    ManualSection(
        key="auth-rbac-mfa",
        title="Auth, RBAC, And MFA",
        body=(
            "Auth/RBAC/security is a protected domain. Do not alter dependencies, capabilities, admin route protection, session behavior, "
            "CSRF/CORS/security middleware, password/token handling, or MFA behavior as a side effect.\n\n"
            "Current launch posture remains manual-review-gated. Production MFA secret custody/recovery, staged MFA enforcement, route/capability "
            "inventory, coarse fallback removal, role governance, and rollback evidence are not launch-accepted as broad public controls.\n\n"
            "Security evidence must be sanitized. Never include raw cookies, Authorization headers, session IDs, request bodies, provider payloads, "
            "password hashes, or secret values in docs, logs, screenshots, reports, or release artifacts."
        ),
        source_paths=(
            "docs/audits/index-security-rbac-mfa.md",
            "docs/audits/auth-rbac-release-security-guide.md",
            "docs/audits/admin-rbac-r5-coarse-fallback-removal-plan.md",
            "docs/audits/security-mfa-secret-storage-hardening-plan.md",
            "docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md",
        ),
        update_trigger="Any auth, session, capability, MFA, security evidence, admin route, or role-governance change.",
        validation="Focused auth/RBAC tests, route-capability inventory, redaction checks, and wider gates when enforcement changes.",
    ),
    ManualSection(
        key="portfolio-backtest",
        title="Portfolio And Backtest",
        body=(
            "Portfolio owns accounts, holdings, cash, transactions, P&L, FX/native currency, cost basis, broker sync/import overlays, ledger mutations, "
            "and read projections. UI work must not recalculate accounting authority or imply broker order execution.\n\n"
            "Backtest owns standard historical evaluation, deterministic rule backtests, calculation math, stored-first readback, support exports, compare workflows, "
            "universe diagnostics, and professional-readiness disclosures. The deterministic rule backtest lane is frozen as v1 semantics unless a future task "
            "explicitly versions and tests a new execution model.\n\n"
            "Do not change portfolio accounting, mutation semantics, owner isolation, backtest fills, costs, metrics, benchmark semantics, stored-result authority, "
            "or local-only universe execution without explicit scope and focused regression evidence."
        ),
        source_paths=(
            "docs/portfolio/README.md",
            "docs/backtest/README.md",
            "docs/backtest-system.md",
            "docs/audits/backtest-portfolio-public-safety-audit.md",
            "docs/codex/WOLFYSTOCK_BACKTEST_UNIVERSE_RULES.md",
        ),
        update_trigger="Portfolio accounting/read models, backtest execution/readback/export, public-safety, or owner-isolation changes.",
        validation="Portfolio/backtest focused tests, golden fixtures, mutation guards, no-advice checks, and owner-isolation evidence when applicable.",
    ),
    ManualSection(
        key="provider-quota-cost",
        title="Provider, Quota, And Cost",
        body=(
            "Provider runtime owns provider order, fallback, retry/circuit posture, freshness labels, optional enrichment budgets, source disclosure, sanitized diagnostics, "
            "and cache/local-first behavior. Keep stale, fallback, mock, synthetic, fixture, repaired, or inferred data clearly not-live.\n\n"
            "Quota and cost tooling is mostly advisory, dry-run, or pilot-bound unless a prompt explicitly scopes live route-boundary enforcement. Cost dashboards and ledgers "
            "are useful observability surfaces, but they are not billing-authoritative without accepted provider invoice/export reconciliation.\n\n"
            "Do not reorder providers, deepen live fallback, add broad optional fanout, print raw provider payloads, or expose request URLs, headers, credentials, query strings, "
            "tokens, stack traces, or raw ledger internals."
        ),
        source_paths=(
            "docs/provider-data/README.md",
            "docs/codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md",
            "docs/audits/index-provider-data-options.md",
            "docs/audits/index-cost-quota-observability.md",
            "docs/audits/quota-reserve-release-operator-evidence-checklist.md",
        ),
        update_trigger="Provider routing/fallback/freshness/cache, quota, circuit, budget, cost, or provider diagnostics changes.",
        validation="Provider/cache/freshness tests, quota lifecycle tests, no-live-call proof when scoped, and redaction checks.",
    ),
    ManualSection(
        key="ws2-durable-runtime",
        title="WS2 And Durable Runtime",
        body=(
            "Current async/background behavior remains process-local or route/script-specific. `AnalysisTaskQueue` futures and analysis-task SSE are process-local; durable rows, "
            "progress polling, and synthetic worker prototypes are evidence foundations, not production multi-instance recovery.\n\n"
            "Public multi-instance deployment remains NO-GO until API A/B route switching, worker lease/retry/failure handling, owner isolation, durable polling replay, "
            "SSE limitation handling, and sanitized operator evidence are accepted.\n\n"
            "Do not add Redis, Celery, RQ, Kafka, broker dependencies, worker cutovers, migrations, provider/LLM calls, or runtime queue behavior from docs/generator work."
        ),
        source_paths=(
            "docs/operations/background-job-queue-boundary.md",
            "docs/operations/queue-ws2-metrics-production-readiness.md",
            "docs/audits/ws2-multi-instance-smoke-test-design.md",
            "docs/audits/ws2-multi-user-runtime-cost-control-design.md",
        ),
        update_trigger="Analysis task queue, SSE, durable polling, worker, broker, multi-instance, or WS2 readiness changes.",
        validation="Synthetic/local smoke first; staging/API A-B evidence and operator artifacts only when deployment posture changes.",
    ),
    ManualSection(
        key="options-data-pipeline",
        title="Options And Data Pipeline",
        body=(
            "Options Lab is an ExperimentConsole, not an execution surface. Current providers are fixture/dry-run contracts; live provider stubs are disabled by default and must fail closed. "
            "Do not add broker/order paths, portfolio mutation, live provider calls, global market-provider fallback changes, or tradeable-data claims without explicit safety review.\n\n"
            "Data Pipeline R2 treats optional news, sentiment, and detailed fundamentals as progressive enrichment metadata. Optional enrichment gaps must be sanitized and non-blocking; "
            "late async merge is future work and should update only bounded metadata unless a separate reviewed recalculation path exists.\n\n"
            "Missing provider values must stay missing. Do not fabricate Greeks, IV, bid/ask, volume, open interest, fundamentals, or freshness to make data appear decision-grade."
        ),
        source_paths=(
            "docs/options/README.md",
            "docs/audits/options-provider-adapter-contract.md",
            "docs/audits/data-pipeline-r2-progressive-enrichment.md",
            "docs/audits/data-quality-user-disclosure-policy.md",
            "docs/audits/trading-no-advice-product-policy.md",
        ),
        update_trigger="Options providers, chain/Greeks, scenario copy, optional enrichment, data-quality, or no-advice changes.",
        validation="Options/data-quality focused tests, fixture/mocked-provider tests, no-order scans, and redaction checks.",
    ),
    ManualSection(
        key="frontend-ia-ui",
        title="Frontend IA And UI Conventions",
        body=(
            "WolfyStock frontend follows a Reflect-Linear / Linear OS product language: calm, precise, data-rich, route-first, and workbench-oriented. "
            "Prefer rows, tables, strips, rails, drawers, and disclosures before card-first dashboards.\n\n"
            "Each major route should reveal its primary task in the first viewport. User routes keep raw provider/cache/schema/debug terms collapsed by default; admin/ops pages may be denser "
            "but still start with operator state, impact, recommended action, evidence, then details.\n\n"
            "New user-facing material should prefer `apps/dsa-web/src/components/linear/`. Existing `Terminal*` names are compatibility adapters, not permission to create a parallel terminal UI system."
        ),
        source_paths=(
            "docs/frontend/README.md",
            "docs/frontend/visual-system.md",
            "docs/frontend/validation-playbook.md",
            "docs/frontend/WOLFYSTOCK_FRONTEND_NOISE_BUDGET.md",
            "docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md",
            "docs/frontend/WOLFYSTOCK_ADMIN_MAINTENANCE_OS.md",
        ),
        update_trigger="Frontend route taxonomy, primitives, route IA, visual system, consumer/admin disclosure, or browser-evidence rules change.",
        validation="Frontend focused tests plus lint/build/browser evidence when UI source or visual behavior changes.",
    ),
    ManualSection(
        key="validation-workflow",
        title="Codex Workflow, Validation, And Reporting",
        body=(
            "Pick the smallest validation set that proves the current change. Docs/generator tasks use docs diff-checks plus secret scan; frontend source changes need route-aware tests and browser evidence; "
            "backend/API/auth/provider changes need focused tests and wider gates when protected or shared contracts are near scope.\n\n"
            "Use the task mode and workspace the prompt actually names. `WORKTREE-WORKER` means stay inside the prompt workspace and branch. `SERIAL-MAIN` is only for an explicit shared-main task. "
            "Do not push unless the prompt authorizes it, and keep the branch name exactly aligned with the task contract.\n\n"
            "Before final reporting, fetch the latest `origin/main` when the task contract requires it, rebase onto it, rerun the focused validation, and confirm the branch is clean, ahead of `origin/main`, and not behind.\n\n"
            "Cleanup happens after the final report is captured, not before. Do not create one-off task report markdown when the canonical final report template already exists. "
            "Do not broaden validation just to look thorough, and do not treat green tests on a different surface as proof for this one.\n\n"
            "If docs are changed, change the docs because the source-of-truth moved or the behavior did, not because the task needs a separate story file."
        ),
        source_paths=(
            "AGENTS.md",
            "docs/codex/WOLFYSTOCK_CODEX_DISCOVERY_PROTOCOL.md",
            "docs/codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md",
            "docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md",
            "docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md",
            "docs/codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md",
            "docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md",
            "docs/codex/NO_ADVICE_REGRESSION_GUARDS.md",
            "docs/frontend/validation-playbook.md",
        ),
        update_trigger="Task modes, prompt fields, validation matrix, final report format, or frontend evidence rules change.",
        validation="Run the smallest validation that proves the touched files, then record the command, exit status, and any blocker in the final report.",
    ),
    ManualSection(
        key="launch-no-go",
        title="Public Launch NO-GO Blockers",
        body=(
            "Current public launch status is NO-GO. Existing foundations and offline validators are useful review plumbing, but they do not approve launch and do not replace target-environment operator evidence.\n\n"
            "Main blocker families are security/MFA/RBAC, provider/options/data quality, portfolio/backtest safety, WS2 multi-instance runtime, cost/quota/provider circuit enforcement, deployment/backup/rollback, "
            "and final release-candidate gates.\n\n"
            "Machine-readable launch evidence and operator bundles must remain sanitized and manual-review-only. `releaseApproved=false` remains the safe default unless every hard blocker has accepted external/manual evidence."
        ),
        source_paths=(
            "docs/audits/README.md",
            "docs/audits/public-launch-readiness-master.md",
            "docs/audits/public-launch-gap-register.md",
            "docs/audits/deployment-readiness-checklist.md",
            "docs/audits/launch-acceptance-evidence-pack.md",
        ),
        update_trigger="Launch verdict, blocker register, release checklist, operator evidence contract, or launch acceptance process changes.",
        validation="Docs-only validation for launch docs; release-grade gates and sanitized operator evidence for actual launch posture changes.",
    ),
    ManualSection(
        key="experimental-demo-only",
        title="Known Experimental And Demo-Only Surfaces",
        body=(
            "Treat fixture-only, demo-only, dry-run, no-send, local-only, diagnostic-only, disabled-by-default, synthetic, fallback, cache-only, and advisory-only labels as hard safety signals.\n\n"
            "Current examples include Options fixture/dry-run providers, disabled live options stubs, DuckDB diagnostic/local-only posture, WS2 synthetic worker and process-local SSE limitations, "
            "provider source-confidence helpers, optional enrichment metadata, and alert/notification dry-run surfaces.\n\n"
            "Do not present these as production-grade, launch-approved, live, billing-authoritative, decision-grade, or tradeable capabilities without separate approval and current validation."
        ),
        source_paths=(
            "docs/audits/options-provider-adapter-contract.md",
            "docs/quant-duckdb-engine.md",
            "docs/alerts/README.md",
            "docs/operations/background-job-queue-boundary.md",
            "docs/operations/queue-ws2-metrics-production-readiness.md",
            "docs/data-reliability/provider-source-confidence-contract.md",
            "docs/audits/data-pipeline-r2-progressive-enrichment.md",
        ),
        update_trigger="Any diagnostic/demo/fixture/dry-run surface becomes runtime, production, or user-visible decision authority.",
        validation="Fail-closed tests, no-live-call proof, redaction checks, docs wording review, and task-specific runtime evidence.",
    ),
    ManualSection(
        key="source-truth-index",
        title="Source-Of-Truth Index",
        body=(
            "Use this compact index to jump to the canonical doc for a topic, then read the supporting docs only as needed. If a topic is historical or archive-only, say so explicitly and do not treat it as current authority.\n\n"
            "{{SOURCE_TRUTH_INDEX_TABLE}}\n\n"
            "The canonical doc should be the first stop. Supporting docs are there to narrow scope, validate edge cases, or explain why a path is blocked, partial, or observation-only."
        ),
        source_paths=(
            "AGENTS.md",
            "docs/DOCS_INDEX.md",
            "docs/ARCHIVE_INDEX.md",
            "docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md",
            "docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md",
            "docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md",
            "docs/codex/WOLFYSTOCK_CODEX_DISCOVERY_PROTOCOL.md",
            "docs/codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md",
            "docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md",
            "docs/codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md",
            "docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md",
            "docs/codex/NO_ADVICE_REGRESSION_GUARDS.md",
            "docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md",
            "docs/data-reliability/provider-source-confidence-contract.md",
            "docs/operations/provider-capability-metadata.md",
            "docs/data/market-source-activation-blueprint.md",
            "docs/product-recovery/WOLFYSTOCK_PRODUCT_RECOVERY_PLAN.md",
            "docs/product-recovery/DATA_COVERAGE_MATRIX.md",
            "docs/product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md",
            "docs/product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md",
            "docs/product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md",
            "docs/product-recovery/DATA034_OPTIONS_PROVIDER_ENTITLEMENT_DECISION.md",
            "docs/product-recovery/DATA035_SCENARIO_DURABLE_BASELINE_SNAPSHOT_PLAN.md",
            "docs/product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md",
            "docs/product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md",
            "docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md",
            "docs/market-overview/README.md",
            "docs/scanner/README.md",
            "docs/liquidity/README.md",
            "docs/rotation/README.md",
            "docs/options/README.md",
            "docs/portfolio/README.md",
            "docs/backtest/README.md",
            "docs/backtest-system.md",
            "docs/audits/data-quality-user-disclosure-policy.md",
            "docs/audits/options-provider-adapter-contract.md",
            "docs/audits/backtest-portfolio-public-safety-audit.md",
            "docs/audits/trading-no-advice-product-policy.md",
        ),
        update_trigger="Canonical source maps, source curation, or topic ownership changes.",
        validation="Read the canonical doc first, then supporting docs, and use the class label to decide whether the topic is policy, contract, roadmap, historical, or generated manual source.",
    ),
    ManualSection(
        key="source-policy",
        title="Source Inclusion And Exclusion Policy",
        body=(
            "The generator discovers Markdown files but only includes curated high-signal sources in the manual. This prevents the manual from exceeding practical AI context size and avoids treating old evidence as current truth.\n\n"
            "Default inclusions are current authority docs, domain entry points, launch/blocker indexes, Codex workflow docs, and a few targeted domain contracts. Default exclusions are archive lanes, local/generated evidence, "
            "task audit dumps, language duplicates, fixture-local READMEs, AI-governance mirrors, and broad legacy guides unless a current source explicitly promotes them.\n\n"
            "When source docs conflict, prefer the current prompt, `AGENTS.md`, current code/tests/scripts, and active authority docs. Use archives for provenance only."
        ),
        source_paths=(
            "docs/DOCS_INDEX.md",
            "docs/architecture/file-governance-taxonomy.md",
            "docs/ARCHIVE_INDEX.md",
            "docs/audits/README.md",
        ),
        update_trigger="Docs taxonomy, archive policy, generated artifact policy, or manual source curation changes.",
        validation="Run this generator twice and prove deterministic output; run docs diff-check and secret scan.",
    ),
]


SECTION_KEYS = {section.key for section in SECTIONS}
if len(SECTION_KEYS) != len(SECTIONS):
    raise RuntimeError("Manual section keys must be unique")


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
    if "example" in lower or "sample" in lower or "dummy" in lower or "mock" in lower or "fake" in lower:
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
    lines = text.splitlines()
    return {
        "path": source.path,
        "title": first_heading(text, Path(source.path).name),
        "purpose": source.purpose,
        "categories": sorted(source.categories),
        "sha256": sha256_bytes(data),
        "bytes": len(data),
        "lineCount": len(lines),
    }


def should_prune_dir(path: Path) -> bool:
    return path.name in PRUNED_DIR_NAMES


def exclusion_reason(path: str) -> str | None:
    if path in OUTPUT_MARKDOWN_PATHS:
        return "generated_manual_output"
    pure = PurePosixPath(path)
    parts = set(pure.parts)
    if path == "CLAUDE.md" or path.startswith(".github/instructions/") or path == ".github/copilot-instructions.md":
        return "ai_governance_mirror"
    if path in {"DESIGN.md", "SKILL.md", "docs/openclaw-skill-integration.md"}:
        return "legacy_or_external_product_doc"
    if "archive" in parts:
        return "archive_provenance"
    if path.startswith("docs/codex/audits/"):
        return "codex_point_in_time_audit"
    if path.startswith("docs/codex/goals/") or "goal-progress" in path:
        return "task_progress_log"
    if path.startswith("tests/fixtures/") and path.endswith("/README.md"):
        return "fixture_local_doc"
    if path.endswith("_EN.md") or path.endswith("_CHT.md") or PurePosixPath(path).name.startswith("full-guide"):
        return "language_or_broad_duplicate"
    if parts & PRUNED_DIR_NAMES:
        return "generated_or_dependency_path"
    return None


def discover_markdown_files() -> dict[str, object]:
    discovered: list[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(dirnames)
        filenames = sorted(filenames)
        kept_dirs: list[str] = []
        for dirname in dirnames:
            child = Path(dirpath) / dirname
            if should_prune_dir(child):
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs
        for filename in filenames:
            if not filename.endswith(".md"):
                continue
            path = Path(dirpath) / filename
            discovered_path = rel_path(path)
            if discovered_path in OUTPUT_MARKDOWN_PATHS:
                continue
            discovered.append(discovered_path)

    discovered = sorted(discovered)
    excluded = Counter()
    candidates: list[str] = []
    for path in discovered:
        reason = exclusion_reason(path)
        if reason:
            excluded[reason] += 1
        else:
            candidates.append(path)
    included_paths = sorted(SOURCE_BY_PATH)
    return {
        "markdownDiscovered": len(discovered),
        "candidateMarkdownAfterPolicy": len(candidates),
        "includedSourceCount": len(included_paths),
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


PRODUCT_SURFACE_ROWS = [
    (
        "Market Overview",
        "Regime, breadth, and risk first read",
        "`api/v1/endpoints/market_overview.py`; `src/services/market_overview_service.py`; `apps/dsa-web/src/pages/MarketOverviewPage.tsx`",
        "partial; official risk bundle and quote authority still gate the first screen",
        "fallback/static, stale, proxy-only, missing official risk rows -> `mixed_no_clear_edge` or unavailable",
        source_list(
            (
                "docs/market-overview/README.md",
                "docs/data/market-source-activation-blueprint.md",
                "docs/provider-data/README.md",
                "docs/audits/data-quality-user-disclosure-policy.md",
            )
        ),
    ),
    (
        "Scanner",
        "Candidate discovery and watchlist handoff",
        "`api/v1/endpoints/scanner.py`; `src/services/market_scanner_service.py`; `src/repositories/scanner_repo.py`; `apps/dsa-web/src/pages/UserScannerPage.tsx`",
        "partial; useful only when universe, quote, history, turnover, and evidence packet inputs exist",
        "empty runs from missing local data, blocked input readiness, stale/fallback quote/history",
        source_list(
            (
                "docs/scanner/README.md",
                "docs/product-recovery/DATA_COVERAGE_MATRIX.md",
                "docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md",
            )
        ),
    ),
    (
        "Watchlist",
        "Saved symbols and research queue",
        "`api/v1/endpoints/watchlist.py`; `src/services/watchlist_service.py`; `src/services/watchlist_research_overlay_service.py`; `apps/dsa-web/src/pages/WatchlistPage.tsx`",
        "partial; row packet still missing quote/freshness/catalyst refs in many cases",
        "missing quote freshness, missing research packet, missing catalyst age, stale scanner lineage",
        source_list(
            (
                "docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md",
                "docs/product-recovery/DATA_COVERAGE_MATRIX.md",
                "docs/scanner/README.md",
            )
        ),
    ),
    (
        "Stock Detail",
        "Symbol research packet and structure decision",
        "`api/v1/endpoints/stocks.py`; `src/services/stock_service.py`; `src/services/stock_structure_decision_service.py`",
        "partial; stock packet assembly is not yet fully durable",
        "missing quote/history/fundamentals/events/peer, parser-only SEC facts, observation-only structure",
        source_list(
            (
                "docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md",
                "docs/product-recovery/DATA_COVERAGE_MATRIX.md",
                "docs/audits/data-quality-user-disclosure-policy.md",
            )
        ),
    ),
    (
        "Options Lab",
        "Read-only experiment console",
        "`api/v1/endpoints/options.py`; `src/services/options_lab_service.py`; `apps/dsa-web/src/pages/OptionsLabPage.tsx`",
        "observation-only / partial; fixture and dry-run default, no live provider authority proven",
        "missing chain/IV/Greeks/OI/volume, missing entitlement/redisplay, no strategy ranking or trade workflow",
        source_list(
            (
                "docs/options/README.md",
                "docs/product-recovery/DATA034_OPTIONS_PROVIDER_ENTITLEMENT_DECISION.md",
                "docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md",
                "docs/audits/options-provider-adapter-contract.md",
            )
        ),
    ),
    (
        "Liquidity Monitor",
        "Capital pressure and market stress",
        "`api/v1/endpoints/liquidity_monitor.py`; `src/services/liquidity_monitor_service.py`; `apps/dsa-web/src/pages/LiquidityMonitorPage.tsx`",
        "partial; official risk bundle and coverage contract still gate score-grade",
        "proxy-only flow, stale or missing official macro rows, observation-only CN/HK flow",
        source_list(
            (
                "docs/liquidity/README.md",
                "docs/data/market-source-activation-blueprint.md",
                "docs/provider-data/README.md",
            )
        ),
    ),
    (
        "Backtest / Parameter Sweep",
        "Deterministic rule backtest and stored readback",
        "`api/v1/endpoints/backtest.py`; `src/core/rule_backtest_engine.py`; `src/services/backtest_service.py`; `apps/dsa-web/src/pages/BacktestPage.tsx`",
        "research-useful; v1 deterministic engine is live, parameter sweep remains diagnostic for professional claims",
        "no optimizer/winner semantics, no portfolio allocation, no live provider hydration, no fake performance",
        source_list(
            (
                "docs/backtest/README.md",
                "docs/backtest-system.md",
                "docs/product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md",
                "docs/product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md",
            )
        ),
    ),
    (
        "Factor Research",
        "Offline factor helpers and backtest bridge",
        "`src/services/factor_metrics.py`; `src/services/factor_exposure.py`; `src/services/backtest_factor_research_bridge.py`",
        "diagnostic-only; no public factor panel, no long-short return backtest, no PIT universe",
        "missing forward returns, no PIT membership, no survivorship control, no winner promotion",
        source_list(
            (
                "docs/product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md",
                "docs/product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md",
                "docs/backtest/README.md",
            )
        ),
    ),
    (
        "Scenario Lab",
        "Bounded shock comparison",
        "`api/v1/endpoints/market.py`; `src/services/market_scenario_lab_engine.py`; `apps/dsa-web/src/pages/ScenarioLabPage.tsx`",
        "partial; request/snapshot driven, authoritative only when real cached baseline inputs exist",
        "sample/demo/fallback/static/request-supplied-only state stays observation-only, no execution-readiness implication",
        source_list(
            (
                "docs/product-recovery/DATA035_SCENARIO_DURABLE_BASELINE_SNAPSHOT_PLAN.md",
                "docs/product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md",
                "docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md",
            )
        ),
    ),
    (
        "Portfolio",
        "Holdings, P&L, FX, ledger, risk",
        "`api/v1/endpoints/portfolio.py`; `src/services/portfolio_service.py`; `apps/dsa-web/src/pages/PortfolioPage.tsx`",
        "partial; accounting is real, valuation lineage and FX freshness still gate credibility",
        "stale or missing FX, missing price lineage, no order/broker semantics, manual forms are ledger records only",
        source_list(
            (
                "docs/portfolio/README.md",
                "docs/product-recovery/DATA_COVERAGE_MATRIX.md",
                "docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md",
                "docs/audits/backtest-portfolio-public-safety-audit.md",
            )
        ),
    ),
    (
        "Evidence Harness / target env artifacts",
        "Sanitized operator evidence for readiness",
        "`scripts/target_environment_evidence_harness.py`; `scripts/ws2_target_environment_evidence_check.py`",
        "read-only / observation-only; captures evidence, does not prove acceptance",
        "secrets, raw payloads, unavailable endpoints, readiness blocked vs endpoint unavailable conflation",
        source_list(
            (
                "docs/product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md",
                "docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md",
            )
        ),
    ),
    (
        "Admin / diagnostics",
        "Operator-facing observability",
        "`api/v1/endpoints/admin/*`; `src/services/admin_*`; `apps/dsa-web/src/pages/Admin*`",
        "manual-review-gated; operational only",
        "raw provider/internal leakage, security evidence, cross-domain semantic changes",
        source_list(
            (
                "docs/frontend/WOLFYSTOCK_ADMIN_MAINTENANCE_OS.md",
                "docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md",
                "docs/audits/README.md",
            )
        ),
    ),
]

PROFESSIONAL_DATA_FAMILY_ROWS = [
    (
        "Official risk bundle",
        "partial",
        "VIX, rates, Fed liquidity, and credit stress are the first credibility layer, but target-environment activation still needs proof.",
        "Do not relabel proxy rows as official or live.",
        source_list(
            (
                "docs/data/market-source-activation-blueprint.md",
                "docs/provider-data/README.md",
                "docs/data-reliability/provider-source-confidence-contract.md",
            )
        ),
    ),
    (
        "ETF / index quote and membership coverage",
        "partial",
        "US index / ETF quote coverage and official membership / weight proofs are still incomplete for broad market and rotation claims.",
        "No headline Rotation or Market Overview claim from proxy membership alone.",
        source_list(
            (
                "docs/data/market-source-activation-blueprint.md",
                "docs/product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md",
                "docs/product-recovery/DATA_COVERAGE_MATRIX.md",
            )
        ),
    ),
    (
        "Authorized quote spine",
        "partial",
        "Durable US/CN/HK quote and daily OHLCV snapshots still need a unified store and explicit display rights.",
        "No fake live quotes or fallback promotion.",
        source_list(
            (
                "docs/product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md",
                "docs/product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md",
                "docs/product-recovery/DATA_COVERAGE_MATRIX.md",
            )
        ),
    ),
    (
        "Breadth, flows, and positioning",
        "partial / observation-only",
        "Real flow and positioning remain unproven; proxy breadth and quote-derived flow stay bounded and explicitly capped.",
        "No score-grade flow or positioning claim from proxy data.",
        source_list(
            (
                "docs/data/market-source-activation-blueprint.md",
                "docs/liquidity/README.md",
                "docs/provider-data/README.md",
            )
        ),
    ),
    (
        "Fundamentals, filings, and events",
        "partial",
        "Fundamental fields, filings, catalysts, and normalized events are fragmented and still need a durable research packet.",
        "No invented catalysts, ratios, or event freshness.",
        source_list(
            (
                "docs/product-recovery/DATA_COVERAGE_MATRIX.md",
                "docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md",
                "docs/product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md",
            )
        ),
    ),
    (
        "Options chains and Greeks",
        "blocked / observation-only",
        "No authorized live provider or rights proof exists for production use, and methodology approval is still missing for gamma-family outputs.",
        "No strategy ranking, GEX, vanna, charm, or order CTA.",
        source_list(
            (
                "docs/product-recovery/DATA034_OPTIONS_PROVIDER_ENTITLEMENT_DECISION.md",
                "docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md",
                "docs/audits/options-provider-adapter-contract.md",
            )
        ),
    ),
    (
        "Scenario baselines",
        "partial",
        "Scenario Lab is still request/snapshot driven until durable baseline snapshots and target-environment proof exist.",
        "No execution-readiness implication from scenario comparisons.",
        source_list(
            (
                "docs/product-recovery/DATA035_SCENARIO_DURABLE_BASELINE_SNAPSHOT_PLAN.md",
                "docs/product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md",
                "docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md",
            )
        ),
    ),
    (
        "Backtest dataset lineage",
        "partial / research-useful",
        "v1 backtests exist, but the professional lineage gate is incomplete and still needs adjusted basis, calendar, PIT, and reproducibility proof.",
        "No optimizer/winner semantics or fake performance.",
        source_list(
            (
                "docs/product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md",
                "docs/product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md",
                "docs/backtest/README.md",
            )
        ),
    ),
    (
        "Factor research lineage",
        "diagnostic-only",
        "Offline factor helpers exist, but there is no PIT universe or long-short return backtest contract yet.",
        "No lookahead or winner promotion.",
        source_list(
            (
                "docs/product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md",
                "docs/product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md",
                "docs/backtest/README.md",
            )
        ),
    ),
]

SOURCE_TRUTH_INDEX_ROWS = [
    (
        "AI onboarding and navigation",
        manual_link("docs/AI_PROJECT_MANUAL.md"),
        source_list(("AGENTS.md", "docs/DOCS_INDEX.md", "scripts/build_ai_project_manual.py")),
        "repo-wide AI maintenance",
        "first five minutes of any task",
        "generated manual source",
    ),
    (
        "Repository AI rules",
        manual_link("AGENTS.md"),
        source_list(("docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md", "docs/DOCS_INDEX.md")),
        "repo-wide",
        "before any edit, commit, or validation",
        "policy",
    ),
    (
        "Codex workflow and reporting",
        manual_link("docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md"),
        source_list(
            (
                "docs/codex/WOLFYSTOCK_CODEX_DISCOVERY_PROTOCOL.md",
                "docs/codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md",
                "docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md",
                "docs/codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md",
                "docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md",
                "docs/codex/NO_ADVICE_REGRESSION_GUARDS.md",
            )
        ),
        "Codex workers",
        "before any execution-class task",
        "policy",
    ),
    (
        "Protected backend domains",
        manual_link("docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md"),
        source_list(("docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md", "docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md")),
        "scanner / backtest / portfolio / provider / auth / options",
        "before touching protected runtime semantics",
        "policy",
    ),
    (
        "Provider source confidence",
        manual_link("docs/data-reliability/provider-source-confidence-contract.md"),
        source_list(("docs/provider-data/README.md", "docs/operations/provider-capability-metadata.md", "docs/audits/data-quality-user-disclosure-policy.md")),
        "provider / data",
        "before reasoning about freshness, coverage, or authority",
        "contract",
    ),
    (
        "Official risk and quote activation",
        manual_link("docs/data/market-source-activation-blueprint.md"),
        source_list(("docs/product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md", "docs/product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md")),
        "market overview / liquidity / rotation",
        "before activating official VIX, rates, or quote coverage",
        "roadmap",
    ),
    (
        "Symbol research packet",
        manual_link("docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md"),
        source_list(("docs/product-recovery/DATA_COVERAGE_MATRIX.md", "docs/product-recovery/DATA011_PACKET_CONSUMPTION_ACCEPTANCE.md")),
        "watchlist / stock detail",
        "before assembling row-level research packets",
        "contract",
    ),
    (
        "Quote spine and target env evidence",
        manual_link("docs/product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md"),
        source_list(("docs/product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md", "docs/product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md")),
        "scanner / watchlist / stock / portfolio / market / rotation",
        "before quote or history lineage changes",
        "contract",
    ),
    (
        "Backtest dataset lineage",
        manual_link("docs/product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md"),
        source_list(("docs/backtest/README.md", "docs/backtest-system.md", "docs/product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md")),
        "backtest / factor research",
        "before adjusting backtest lineage or sweep storage",
        "contract",
    ),
    (
        "Options entitlement and no-advice",
        manual_link("docs/product-recovery/DATA034_OPTIONS_PROVIDER_ENTITLEMENT_DECISION.md"),
        source_list(("docs/options/README.md", "docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md", "docs/audits/options-provider-adapter-contract.md", "docs/audits/trading-no-advice-product-policy.md")),
        "options lab",
        "before touching options chain, Greeks, or strategy copy",
        "decision record",
    ),
    (
        "Scenario baseline evidence",
        manual_link("docs/product-recovery/DATA035_SCENARIO_DURABLE_BASELINE_SNAPSHOT_PLAN.md"),
        source_list(("docs/product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md", "docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md")),
        "scenario lab / target-env evidence",
        "before scenario baseline or operator evidence work",
        "plan",
    ),
    (
        "Market data recovery summary",
        manual_link("docs/product-recovery/WOLFYSTOCK_PRODUCT_RECOVERY_PLAN.md"),
        source_list(("docs/product-recovery/DATA_COVERAGE_MATRIX.md", "docs/product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md")),
        "recovery program",
        "before any product-recovery task",
        "roadmap",
    ),
    (
        "Surface entry docs",
        manual_link("docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md"),
        source_list(("docs/market-overview/README.md", "docs/scanner/README.md", "docs/liquidity/README.md", "docs/rotation/README.md", "docs/portfolio/README.md", "docs/backtest/README.md", "docs/options/README.md")),
        "route families",
        "before touching a user-facing route",
        "entry point",
    ),
    (
        "Historical / archive only",
        manual_link("docs/ARCHIVE_INDEX.md"),
        source_list(("docs/audits/README.md", "docs/architecture/file-governance-taxonomy.md")),
        "provenance only",
        "only to trace prior decisions or retired evidence",
        "historical",
    ),
    (
        "Current documentation navigation",
        manual_link("docs/DOCS_INDEX.md"),
        source_list(("docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md", "docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md")),
        "maintainers",
        "when you need the current doc tree",
        "index",
    ),
]


def markdown_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> list[str]:
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        output.append("| " + " | ".join(cell.replace("\n", " ").replace("|", "\\|") for cell in row) + " |")
    return output


def render_section_body(body: str) -> str:
    table_replacements = {
        "{{PRODUCT_SURFACE_TABLE}}": markdown_table(
            (
                "Surface",
                "User-visible purpose",
                "Main ownership",
                "Current data readiness boundary",
                "Major fail-closed states",
                "Deeper source docs",
            ),
            PRODUCT_SURFACE_ROWS,
        ),
        "{{PROFESSIONAL_DATA_FAMILY_TABLE}}": markdown_table(
            ("Family", "Readiness", "Current reality", "Fail-closed rule", "Deeper source docs"),
            PROFESSIONAL_DATA_FAMILY_ROWS,
        ),
        "{{SOURCE_TRUTH_INDEX_TABLE}}": markdown_table(
            (
                "Topic",
                "Canonical doc",
                "Supporting docs",
                "Owner / surface",
                "When an AI should read it",
                "Type",
            ),
            SOURCE_TRUTH_INDEX_ROWS,
        ),
    }
    rendered = body
    for placeholder, table_lines in table_replacements.items():
        rendered = rendered.replace(placeholder, "\n".join(table_lines))
    if "{{" in rendered or "}}" in rendered:
        raise RuntimeError("unresolved manual placeholder detected")
    return rendered


def section_anchor(title: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", title.lower().replace("/", " "))
    return re.sub(r"\s+", "-", cleaned.strip())


def build_manual(source_meta: dict[str, dict[str, object]], discovery: dict[str, object]) -> str:
    lines: list[str] = [
        "# WolfyStock AI Project Manual",
        "",
        "> GENERATED FILE. DO NOT EDIT DIRECTLY.",
        ">",
        f"> Edit source docs or `{GENERATOR_PATH}`, then run `python {GENERATOR_PATH}`.",
        f"> Check freshness with `python {GENERATOR_PATH} --check`.",
        "",
        "Status: generated AI maintenance onboarding manual.",
        "Audience: Codex workers, review agents, integrators, and humans assigning AI work.",
        "Authority: navigation and operating guide only; `AGENTS.md` remains the repository AI-collaboration source of truth.",
        "Do not use as: launch approval, protected-domain authorization, stale audit authority, or replacement for current source/test inspection.",
        "",
        "## Table Of Contents",
        "",
    ]
    for section in SECTIONS:
        lines.append(f"- [{section.title}](#{section_anchor(section.title)})")
    lines.extend(
        [
            "- [Source Map](#source-map)",
            "- [JSON Manifest](#json-manifest)",
            "",
        ]
    )

    for section in SECTIONS:
        missing_sources = [path for path in section.source_paths if path not in source_meta]
        if missing_sources:
            raise RuntimeError(f"section {section.key} references missing sources: {missing_sources}")
        lines.extend(
            [
                f"## {section.title}",
                "",
                render_section_body(section.body.strip()),
                "",
                f"Source provenance: {source_list(section.source_paths)}.",
                "",
            ]
        )

    source_rows: list[tuple[str, ...]] = []
    for section in SECTIONS:
        source_rows.append(
            (
                section.title,
                "<br>".join(f"`{path}`" for path in section.source_paths),
                section.update_trigger,
                section.validation,
            )
        )

    lines.extend(
        [
            "## Source Map",
            "",
            "This map is generated from the curated source allowlist. It is a lookup aid, not a replacement for reading the linked sources before editing a domain.",
            "",
        ]
    )
    lines.extend(markdown_table(("Manual section", "Primary sources", "Update trigger", "Validation"), source_rows))
    lines.extend(
        [
            "",
            "## JSON Manifest",
            "",
            f"The machine-readable manifest is generated at `{MANIFEST_PATH.relative_to(ROOT).as_posix()}`. It records source paths, titles, purposes, categories, SHA-256 hashes, byte counts, line counts, manual sections, and discovery/exclusion statistics.",
            "",
            "Current discovery summary:",
            "",
            f"- Markdown discovered after pruned directory rules: {discovery['markdownDiscovered']}",
            f"- Candidate Markdown after exclusion policy: {discovery['candidateMarkdownAfterPolicy']}",
            f"- Curated sources included in this manual: {discovery['includedSourceCount']}",
            "",
            "Exclusion policy:",
            "",
        ]
    )
    lines.extend(f"- `{rule}`" for rule in EXCLUSION_POLICY)
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
