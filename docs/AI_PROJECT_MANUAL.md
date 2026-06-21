# WolfyStock AI Project Manual

> GENERATED FILE. DO NOT EDIT DIRECTLY.
>
> Edit source docs or `scripts/build_ai_project_manual.py`, then run `python scripts/build_ai_project_manual.py`.
> Check freshness with `python scripts/build_ai_project_manual.py --check`.

Status: generated AI maintenance onboarding manual.
Audience: Codex workers, review agents, integrators, and humans assigning AI work.
Authority: navigation and operating guide only; `AGENTS.md` remains the repository AI-collaboration source of truth.
Do not use as: launch approval, protected-domain authorization, stale audit authority, or replacement for current source/test inspection.

## Table Of Contents

- [Start Here: Authority And Operating Posture](#start-here-authority-and-operating-posture)
- [Product Purpose And Current Deployment Boundary](#product-purpose-and-current-deployment-boundary)
- [Protected Domains And Hard Stops](#protected-domains-and-hard-stops)
- [Product Surfaces And Data Reality](#product-surfaces-and-data-reality)
- [Architecture And Major Surfaces](#architecture-and-major-surfaces)
- [Auth, RBAC, And MFA](#auth-rbac-and-mfa)
- [Portfolio And Backtest](#portfolio-and-backtest)
- [Provider, Quota, And Cost](#provider-quota-and-cost)
- [WS2 And Durable Runtime](#ws2-and-durable-runtime)
- [Options And Data Pipeline](#options-and-data-pipeline)
- [Frontend IA And UI Conventions](#frontend-ia-and-ui-conventions)
- [Codex Workflow, Validation, And Reporting](#codex-workflow-validation-and-reporting)
- [Public Launch NO-GO Blockers](#public-launch-no-go-blockers)
- [Known Experimental And Demo-Only Surfaces](#known-experimental-and-demo-only-surfaces)
- [Source-Of-Truth Index](#source-of-truth-index)
- [Source Inclusion And Exclusion Policy](#source-inclusion-and-exclusion-policy)
- [Source Map](#source-map)
- [JSON Manifest](#json-manifest)

## Start Here: Authority And Operating Posture

Use this generated manual as the first navigation layer for AI-assisted work. It is not a new rule source and does not replace current source inspection, tests, or task-specific prompt boundaries.

- Current user prompts and explicit allowed/forbidden diffs come first.
- `AGENTS.md` remains the repository AI-collaboration source of truth.
- Current code, scripts, tests, and active docs beat memory, stale screenshots, old audits, and generated artifacts.
- If a task is near protected semantics, stop unless the prompt explicitly scopes that domain and gives a validation path.
- Read-only tasks mean no edits, no artifacts, no staging, no commits, and no pushes.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`docs/DOCS_INDEX.md`](DOCS_INDEX.md), [`docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md`](WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md), [`docs/architecture/file-governance-taxonomy.md`](architecture/file-governance-taxonomy.md).

## Product Purpose And Current Deployment Boundary

WolfyStock is a professional financial research terminal. It combines market overview, scanner discovery, watchlists, rule backtesting, portfolio tracking, AI-assisted analysis, provider diagnostics, and admin observability.

It is not a broker, order-entry surface, generic retail trading app, or unbounded LLM wrapper. Public launch remains NO-GO until security, provider/data, WS2, cost/quota, portfolio/backtest safety, and deployment evidence gates are accepted. Treat private-beta and local tooling as reviewed integration surfaces, not launch approval.

Current safe posture is analytical and no-advice. Do not add buy/sell/order affordances, broker execution, or personalized financial advice unless a separate safety-reviewed task explicitly scopes that change.

Source provenance: [`README.md`](../README.md), [`docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`](WOLFYSTOCK_SYSTEM_HANDBOOK.md), [`docs/DEPLOY.md`](DEPLOY.md), [`docs/audits/private-beta-readiness.md`](audits/private-beta-readiness.md), [`docs/audits/public-launch-readiness-master.md`](audits/public-launch-readiness-master.md), [`docs/audits/trading-no-advice-product-policy.md`](audits/trading-no-advice-product-policy.md).

## Protected Domains And Hard Stops

Treat these as hard stops unless the task explicitly scopes them and gives a focused validation path:

- provider order, credentials, live-call paths, cache/freshness labels, source authority, score contribution, and right-to-display;
- scanner scoring, selection, thresholds, ranking, sorting, and live/fallback labels;
- backtest math, fills, costs, metrics, benchmarks, stored result semantics, and parameter/winner semantics;
- portfolio accounting, cash, holdings, P&L, FX/native currency, cost basis, sync/import/replay, and ledger semantics;
- auth/RBAC/security, sessions, CSRF/CORS, password/token handling, MFA, and admin protection;
- DB migrations, package/config/env, and external network behavior;
- direct trading advice, buy/sell/order CTAs, target prices, position sizing, or synthetic readiness claims.

No fake data, no fallback promotion, no hidden compatibility layer, and no advice. Changes in these areas need the matching guard docs and focused validation before anyone should call the result safe.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`](codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md), [`docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`](codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md), [`docs/codex/NO_ADVICE_REGRESSION_GUARDS.md`](codex/NO_ADVICE_REGRESSION_GUARDS.md), [`docs/audits/trading-no-advice-product-policy.md`](audits/trading-no-advice-product-policy.md), [`docs/data-reliability/provider-source-confidence-contract.md`](data-reliability/provider-source-confidence-contract.md), [`docs/operations/provider-capability-metadata.md`](operations/provider-capability-metadata.md).

## Product Surfaces And Data Reality

WolfyStock is for professional market and stock research support. It is not generic stock-app filler, a broker surface, or a direct advice engine.

| Surface | User-visible purpose | Main ownership | Current data readiness boundary | Major fail-closed states | Deeper source docs |
| --- | --- | --- | --- | --- | --- |
| Market Overview | Regime, breadth, and risk first read | `api/v1/endpoints/market_overview.py`; `src/services/market_overview_service.py`; `apps/dsa-web/src/pages/MarketOverviewPage.tsx` | partial; official risk bundle and quote authority still gate the first screen | fallback/static, stale, proxy-only, missing official risk rows -> `mixed_no_clear_edge` or unavailable | [`docs/market-overview/README.md`](market-overview/README.md), [`docs/data/market-source-activation-blueprint.md`](data/market-source-activation-blueprint.md), [`docs/provider-data/README.md`](provider-data/README.md), [`docs/audits/data-quality-user-disclosure-policy.md`](audits/data-quality-user-disclosure-policy.md) |
| Scanner | Candidate discovery and watchlist handoff | `api/v1/endpoints/scanner.py`; `src/services/market_scanner_service.py`; `src/repositories/scanner_repo.py`; `apps/dsa-web/src/pages/UserScannerPage.tsx` | partial; useful only when universe, quote, history, turnover, and evidence packet inputs exist | empty runs from missing local data, blocked input readiness, stale/fallback quote/history | [`docs/scanner/README.md`](scanner/README.md), [`docs/product-recovery/DATA_COVERAGE_MATRIX.md`](product-recovery/DATA_COVERAGE_MATRIX.md), [`docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md`](product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md) |
| Watchlist | Saved symbols and research queue | `api/v1/endpoints/watchlist.py`; `src/services/watchlist_service.py`; `src/services/watchlist_research_overlay_service.py`; `apps/dsa-web/src/pages/WatchlistPage.tsx` | partial; row packet still missing quote/freshness/catalyst refs in many cases | missing quote freshness, missing research packet, missing catalyst age, stale scanner lineage | [`docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md`](product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md), [`docs/product-recovery/DATA_COVERAGE_MATRIX.md`](product-recovery/DATA_COVERAGE_MATRIX.md), [`docs/scanner/README.md`](scanner/README.md) |
| Stock Detail | Symbol research packet and structure decision | `api/v1/endpoints/stocks.py`; `src/services/stock_service.py`; `src/services/stock_structure_decision_service.py` | partial; stock packet assembly is not yet fully durable | missing quote/history/fundamentals/events/peer, parser-only SEC facts, observation-only structure | [`docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md`](product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md), [`docs/product-recovery/DATA_COVERAGE_MATRIX.md`](product-recovery/DATA_COVERAGE_MATRIX.md), [`docs/audits/data-quality-user-disclosure-policy.md`](audits/data-quality-user-disclosure-policy.md) |
| Options Lab | Read-only experiment console | `api/v1/endpoints/options.py`; `src/services/options_lab_service.py`; `apps/dsa-web/src/pages/OptionsLabPage.tsx` | observation-only / partial; fixture and dry-run default, no live provider authority proven | missing chain/IV/Greeks/OI/volume, missing entitlement/redisplay, no strategy ranking or trade workflow | [`docs/options/README.md`](options/README.md), [`docs/product-recovery/DATA034_OPTIONS_PROVIDER_ENTITLEMENT_DECISION.md`](product-recovery/DATA034_OPTIONS_PROVIDER_ENTITLEMENT_DECISION.md), [`docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md`](product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md), [`docs/audits/options-provider-adapter-contract.md`](audits/options-provider-adapter-contract.md) |
| Liquidity Monitor | Capital pressure and market stress | `api/v1/endpoints/liquidity_monitor.py`; `src/services/liquidity_monitor_service.py`; `apps/dsa-web/src/pages/LiquidityMonitorPage.tsx` | partial; official risk bundle and coverage contract still gate score-grade | proxy-only flow, stale or missing official macro rows, observation-only CN/HK flow | [`docs/liquidity/README.md`](liquidity/README.md), [`docs/data/market-source-activation-blueprint.md`](data/market-source-activation-blueprint.md), [`docs/provider-data/README.md`](provider-data/README.md) |
| Backtest / Parameter Sweep | Deterministic rule backtest and stored readback | `api/v1/endpoints/backtest.py`; `src/core/rule_backtest_engine.py`; `src/services/backtest_service.py`; `apps/dsa-web/src/pages/BacktestPage.tsx` | research-useful; v1 deterministic engine is live, parameter sweep remains diagnostic for professional claims | no optimizer/winner semantics, no portfolio allocation, no live provider hydration, no fake performance | [`docs/backtest/README.md`](backtest/README.md), [`docs/backtest-system.md`](backtest-system.md), [`docs/product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md`](product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md), [`docs/product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md`](product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md) |
| Factor Research | Offline factor helpers and backtest bridge | `src/services/factor_metrics.py`; `src/services/factor_exposure.py`; `src/services/backtest_factor_research_bridge.py` | diagnostic-only; no public factor panel, no long-short return backtest, no PIT universe | missing forward returns, no PIT membership, no survivorship control, no winner promotion | [`docs/product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md`](product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md), [`docs/product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md`](product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md), [`docs/backtest/README.md`](backtest/README.md) |
| Scenario Lab | Bounded shock comparison | `api/v1/endpoints/market.py`; `src/services/market_scenario_lab_engine.py`; `apps/dsa-web/src/pages/ScenarioLabPage.tsx` | partial; request/snapshot driven, authoritative only when real cached baseline inputs exist | sample/demo/fallback/static/request-supplied-only state stays observation-only, no execution-readiness implication | [`docs/product-recovery/DATA035_SCENARIO_DURABLE_BASELINE_SNAPSHOT_PLAN.md`](product-recovery/DATA035_SCENARIO_DURABLE_BASELINE_SNAPSHOT_PLAN.md), [`docs/product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md`](product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md), [`docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md`](product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md) |
| Portfolio | Holdings, P&L, FX, ledger, risk | `api/v1/endpoints/portfolio.py`; `src/services/portfolio_service.py`; `apps/dsa-web/src/pages/PortfolioPage.tsx` | partial; accounting is real, valuation lineage and FX freshness still gate credibility | stale or missing FX, missing price lineage, no order/broker semantics, manual forms are ledger records only | [`docs/portfolio/README.md`](portfolio/README.md), [`docs/product-recovery/DATA_COVERAGE_MATRIX.md`](product-recovery/DATA_COVERAGE_MATRIX.md), [`docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md`](product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md), [`docs/audits/backtest-portfolio-public-safety-audit.md`](audits/backtest-portfolio-public-safety-audit.md) |
| Evidence Harness / target env artifacts | Sanitized operator evidence for readiness | `scripts/target_environment_evidence_harness.py`; `scripts/ws2_target_environment_evidence_check.py` | read-only / observation-only; captures evidence, does not prove acceptance | secrets, raw payloads, unavailable endpoints, readiness blocked vs endpoint unavailable conflation | [`docs/product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md`](product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md), [`docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md`](product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md) |
| Admin / diagnostics | Operator-facing observability | `api/v1/endpoints/admin/*`; `src/services/admin_*`; `apps/dsa-web/src/pages/Admin*` | manual-review-gated; operational only | raw provider/internal leakage, security evidence, cross-domain semantic changes | [`docs/frontend/WOLFYSTOCK_ADMIN_MAINTENANCE_OS.md`](frontend/WOLFYSTOCK_ADMIN_MAINTENANCE_OS.md), [`docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`](codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md), [`docs/audits/README.md`](audits/README.md) |

| Family | Readiness | Current reality | Fail-closed rule | Deeper source docs |
| --- | --- | --- | --- | --- |
| Official risk bundle | partial | VIX, rates, Fed liquidity, and credit stress are the first credibility layer, but target-environment activation still needs proof. | Do not relabel proxy rows as official or live. | [`docs/data/market-source-activation-blueprint.md`](data/market-source-activation-blueprint.md), [`docs/provider-data/README.md`](provider-data/README.md), [`docs/data-reliability/provider-source-confidence-contract.md`](data-reliability/provider-source-confidence-contract.md) |
| ETF / index quote and membership coverage | partial | US index / ETF quote coverage and official membership / weight proofs are still incomplete for broad market and rotation claims. | No headline Rotation or Market Overview claim from proxy membership alone. | [`docs/data/market-source-activation-blueprint.md`](data/market-source-activation-blueprint.md), [`docs/product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md`](product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md), [`docs/product-recovery/DATA_COVERAGE_MATRIX.md`](product-recovery/DATA_COVERAGE_MATRIX.md) |
| Authorized quote spine | partial | Durable US/CN/HK quote and daily OHLCV snapshots still need a unified store and explicit display rights. | No fake live quotes or fallback promotion. | [`docs/product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md`](product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md), [`docs/product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md`](product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md), [`docs/product-recovery/DATA_COVERAGE_MATRIX.md`](product-recovery/DATA_COVERAGE_MATRIX.md) |
| Breadth, flows, and positioning | partial / observation-only | Real flow and positioning remain unproven; proxy breadth and quote-derived flow stay bounded and explicitly capped. | No score-grade flow or positioning claim from proxy data. | [`docs/data/market-source-activation-blueprint.md`](data/market-source-activation-blueprint.md), [`docs/liquidity/README.md`](liquidity/README.md), [`docs/provider-data/README.md`](provider-data/README.md) |
| Fundamentals, filings, and events | partial | Fundamental fields, filings, catalysts, and normalized events are fragmented and still need a durable research packet. | No invented catalysts, ratios, or event freshness. | [`docs/product-recovery/DATA_COVERAGE_MATRIX.md`](product-recovery/DATA_COVERAGE_MATRIX.md), [`docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md`](product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md), [`docs/product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md`](product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md) |
| Options chains and Greeks | blocked / observation-only | No authorized live provider or rights proof exists for production use, and methodology approval is still missing for gamma-family outputs. | No strategy ranking, GEX, vanna, charm, or order CTA. | [`docs/product-recovery/DATA034_OPTIONS_PROVIDER_ENTITLEMENT_DECISION.md`](product-recovery/DATA034_OPTIONS_PROVIDER_ENTITLEMENT_DECISION.md), [`docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md`](product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md), [`docs/audits/options-provider-adapter-contract.md`](audits/options-provider-adapter-contract.md) |
| Scenario baselines | partial | Scenario Lab is still request/snapshot driven until durable baseline snapshots and target-environment proof exist. | No execution-readiness implication from scenario comparisons. | [`docs/product-recovery/DATA035_SCENARIO_DURABLE_BASELINE_SNAPSHOT_PLAN.md`](product-recovery/DATA035_SCENARIO_DURABLE_BASELINE_SNAPSHOT_PLAN.md), [`docs/product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md`](product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md), [`docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md`](product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md) |
| Backtest dataset lineage | partial / research-useful | v1 backtests exist, but the professional lineage gate is incomplete and still needs adjusted basis, calendar, PIT, and reproducibility proof. | No optimizer/winner semantics or fake performance. | [`docs/product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md`](product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md), [`docs/product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md`](product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md), [`docs/backtest/README.md`](backtest/README.md) |
| Factor research lineage | diagnostic-only | Offline factor helpers exist, but there is no PIT universe or long-short return backtest contract yet. | No lookahead or winner promotion. | [`docs/product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md`](product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md), [`docs/product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md`](product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md), [`docs/backtest/README.md`](backtest/README.md) |

Roadmap order:
- Official VIX / volatility.
- Macro / rates / Fed liquidity.
- US index / ETF quote coverage.
- Scanner universe / history / quote readiness.
- Watchlist row packet and Stock research packet.
- Portfolio price / FX lineage.
- Options rights and methodology proof.
- Scenario baseline snapshots.
- Backtest dataset lineage.
- Factor research lineage.

Missing families stay missing, blocked, partial, or observation-only. Do not turn proxy, cached, synthetic, fallback, or fixture data into live, fresh, decision-grade evidence. Do not output direct trading advice.

Source provenance: [`README.md`](../README.md), [`docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`](WOLFYSTOCK_SYSTEM_HANDBOOK.md), [`docs/market-overview/README.md`](market-overview/README.md), [`docs/scanner/README.md`](scanner/README.md), [`docs/liquidity/README.md`](liquidity/README.md), [`docs/rotation/README.md`](rotation/README.md), [`docs/options/README.md`](options/README.md), [`docs/portfolio/README.md`](portfolio/README.md), [`docs/backtest/README.md`](backtest/README.md), [`docs/backtest-system.md`](backtest-system.md), [`docs/product-recovery/WOLFYSTOCK_PRODUCT_RECOVERY_PLAN.md`](product-recovery/WOLFYSTOCK_PRODUCT_RECOVERY_PLAN.md), [`docs/product-recovery/DATA_COVERAGE_MATRIX.md`](product-recovery/DATA_COVERAGE_MATRIX.md), [`docs/product-recovery/DATA011_PACKET_CONSUMPTION_ACCEPTANCE.md`](product-recovery/DATA011_PACKET_CONSUMPTION_ACCEPTANCE.md), [`docs/product-recovery/DATA016_FOCUSED_ACCEPTANCE.md`](product-recovery/DATA016_FOCUSED_ACCEPTANCE.md), [`docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md`](product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md), [`docs/product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md`](product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md), [`docs/product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md`](product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md), [`docs/product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md`](product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md), [`docs/product-recovery/DATA034_OPTIONS_PROVIDER_ENTITLEMENT_DECISION.md`](product-recovery/DATA034_OPTIONS_PROVIDER_ENTITLEMENT_DECISION.md), [`docs/product-recovery/DATA035_SCENARIO_DURABLE_BASELINE_SNAPSHOT_PLAN.md`](product-recovery/DATA035_SCENARIO_DURABLE_BASELINE_SNAPSHOT_PLAN.md), [`docs/product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md`](product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md), [`docs/product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md`](product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md), [`docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md`](product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md), [`docs/data/market-source-activation-blueprint.md`](data/market-source-activation-blueprint.md), [`docs/data-reliability/provider-source-confidence-contract.md`](data-reliability/provider-source-confidence-contract.md), [`docs/operations/provider-capability-metadata.md`](operations/provider-capability-metadata.md), [`docs/audits/data-quality-user-disclosure-policy.md`](audits/data-quality-user-disclosure-policy.md), [`docs/audits/options-provider-adapter-contract.md`](audits/options-provider-adapter-contract.md), [`docs/audits/backtest-portfolio-public-safety-audit.md`](audits/backtest-portfolio-public-safety-audit.md), [`docs/audits/trading-no-advice-product-policy.md`](audits/trading-no-advice-product-policy.md).

## Architecture And Major Surfaces

Maintain WolfyStock as bounded-context modules with narrow public interfaces. Consumers should call facades, schemas, DTOs, API clients, validators, and documented commands instead of private engines, repositories, provider clients, cache keys, or mutation internals.

Major runtime surfaces are `main.py`, `server.py`, `api/app.py`, `api/v1/router.py`, `src/services/`, `src/repositories/`, `data_provider/`, `apps/dsa-web/`, `apps/dsa-desktop/`, `scripts/`, and `.github/workflows/`.

Main product routes include Home, Scanner, Watchlist, Market Overview, Liquidity Monitor, Rotation Radar, Portfolio, Backtest, Options Lab, Settings, and Admin/Ops pages. API groups live under `/api/v1` for auth, analysis, history, stocks, backtest, scanner, system, usage, portfolio, watchlist, market, quant, options, and admin families.

Source provenance: [`docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`](WOLFYSTOCK_SYSTEM_HANDBOOK.md), [`docs/architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md`](architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md), [`docs/architecture/backend-frontend-modular-maintenance-handbook.md`](architecture/backend-frontend-modular-maintenance-handbook.md), [`README.md`](../README.md).

## Auth, RBAC, And MFA

Auth/RBAC/security is a protected domain. Do not alter dependencies, capabilities, admin route protection, session behavior, CSRF/CORS/security middleware, password/token handling, or MFA behavior as a side effect.

Current launch posture remains manual-review-gated. Production MFA secret custody/recovery, staged MFA enforcement, route/capability inventory, coarse fallback removal, role governance, and rollback evidence are not launch-accepted as broad public controls.

Security evidence must be sanitized. Never include raw cookies, Authorization headers, session IDs, request bodies, provider payloads, password hashes, or secret values in docs, logs, screenshots, reports, or release artifacts.

Source provenance: [`docs/audits/index-security-rbac-mfa.md`](audits/index-security-rbac-mfa.md), [`docs/audits/auth-rbac-release-security-guide.md`](audits/auth-rbac-release-security-guide.md), [`docs/audits/admin-rbac-r5-coarse-fallback-removal-plan.md`](audits/admin-rbac-r5-coarse-fallback-removal-plan.md), [`docs/audits/security-mfa-secret-storage-hardening-plan.md`](audits/security-mfa-secret-storage-hardening-plan.md), [`docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`](codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md).

## Portfolio And Backtest

Portfolio owns accounts, holdings, cash, transactions, P&L, FX/native currency, cost basis, broker sync/import overlays, ledger mutations, and read projections. UI work must not recalculate accounting authority or imply broker order execution.

Backtest owns standard historical evaluation, deterministic rule backtests, calculation math, stored-first readback, support exports, compare workflows, universe diagnostics, and professional-readiness disclosures. The deterministic rule backtest lane is frozen as v1 semantics unless a future task explicitly versions and tests a new execution model.

Do not change portfolio accounting, mutation semantics, owner isolation, backtest fills, costs, metrics, benchmark semantics, stored-result authority, or local-only universe execution without explicit scope and focused regression evidence.

Source provenance: [`docs/portfolio/README.md`](portfolio/README.md), [`docs/backtest/README.md`](backtest/README.md), [`docs/backtest-system.md`](backtest-system.md), [`docs/audits/backtest-portfolio-public-safety-audit.md`](audits/backtest-portfolio-public-safety-audit.md), [`docs/codex/WOLFYSTOCK_BACKTEST_UNIVERSE_RULES.md`](codex/WOLFYSTOCK_BACKTEST_UNIVERSE_RULES.md).

## Provider, Quota, And Cost

Provider runtime owns provider order, fallback, retry/circuit posture, freshness labels, optional enrichment budgets, source disclosure, sanitized diagnostics, and cache/local-first behavior. Keep stale, fallback, mock, synthetic, fixture, repaired, or inferred data clearly not-live.

Quota and cost tooling is mostly advisory, dry-run, or pilot-bound unless a prompt explicitly scopes live route-boundary enforcement. Cost dashboards and ledgers are useful observability surfaces, but they are not billing-authoritative without accepted provider invoice/export reconciliation.

Do not reorder providers, deepen live fallback, add broad optional fanout, print raw provider payloads, or expose request URLs, headers, credentials, query strings, tokens, stack traces, or raw ledger internals.

Source provenance: [`docs/provider-data/README.md`](provider-data/README.md), [`docs/codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md`](codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md), [`docs/audits/index-provider-data-options.md`](audits/index-provider-data-options.md), [`docs/audits/index-cost-quota-observability.md`](audits/index-cost-quota-observability.md), [`docs/audits/quota-reserve-release-operator-evidence-checklist.md`](audits/quota-reserve-release-operator-evidence-checklist.md).

## WS2 And Durable Runtime

Current async/background behavior remains process-local or route/script-specific. `AnalysisTaskQueue` futures and analysis-task SSE are process-local; durable rows, progress polling, and synthetic worker prototypes are evidence foundations, not production multi-instance recovery.

Public multi-instance deployment remains NO-GO until API A/B route switching, worker lease/retry/failure handling, owner isolation, durable polling replay, SSE limitation handling, and sanitized operator evidence are accepted.

Do not add Redis, Celery, RQ, Kafka, broker dependencies, worker cutovers, migrations, provider/LLM calls, or runtime queue behavior from docs/generator work.

Source provenance: [`docs/operations/background-job-queue-boundary.md`](operations/background-job-queue-boundary.md), [`docs/operations/queue-ws2-metrics-production-readiness.md`](operations/queue-ws2-metrics-production-readiness.md), [`docs/audits/ws2-multi-instance-smoke-test-design.md`](audits/ws2-multi-instance-smoke-test-design.md), [`docs/audits/ws2-multi-user-runtime-cost-control-design.md`](audits/ws2-multi-user-runtime-cost-control-design.md).

## Options And Data Pipeline

Options Lab is an ExperimentConsole, not an execution surface. Current providers are fixture/dry-run contracts; live provider stubs are disabled by default and must fail closed. Do not add broker/order paths, portfolio mutation, live provider calls, global market-provider fallback changes, or tradeable-data claims without explicit safety review.

Data Pipeline R2 treats optional news, sentiment, and detailed fundamentals as progressive enrichment metadata. Optional enrichment gaps must be sanitized and non-blocking; late async merge is future work and should update only bounded metadata unless a separate reviewed recalculation path exists.

Missing provider values must stay missing. Do not fabricate Greeks, IV, bid/ask, volume, open interest, fundamentals, or freshness to make data appear decision-grade.

Source provenance: [`docs/options/README.md`](options/README.md), [`docs/audits/options-provider-adapter-contract.md`](audits/options-provider-adapter-contract.md), [`docs/audits/data-pipeline-r2-progressive-enrichment.md`](audits/data-pipeline-r2-progressive-enrichment.md), [`docs/audits/data-quality-user-disclosure-policy.md`](audits/data-quality-user-disclosure-policy.md), [`docs/audits/trading-no-advice-product-policy.md`](audits/trading-no-advice-product-policy.md).

## Frontend IA And UI Conventions

WolfyStock frontend follows a Reflect-Linear / Linear OS product language: calm, precise, data-rich, route-first, and workbench-oriented. Prefer rows, tables, strips, rails, drawers, and disclosures before card-first dashboards.

Each major route should reveal its primary task in the first viewport. User routes keep raw provider/cache/schema/debug terms collapsed by default; admin/ops pages may be denser but still start with operator state, impact, recommended action, evidence, then details.

New user-facing material should prefer `apps/dsa-web/src/components/linear/`. Existing `Terminal*` names are compatibility adapters, not permission to create a parallel terminal UI system.

Source provenance: [`docs/frontend/README.md`](frontend/README.md), [`docs/frontend/visual-system.md`](frontend/visual-system.md), [`docs/frontend/validation-playbook.md`](frontend/validation-playbook.md), [`docs/frontend/WOLFYSTOCK_FRONTEND_NOISE_BUDGET.md`](frontend/WOLFYSTOCK_FRONTEND_NOISE_BUDGET.md), [`docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md`](frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md), [`docs/frontend/WOLFYSTOCK_ADMIN_MAINTENANCE_OS.md`](frontend/WOLFYSTOCK_ADMIN_MAINTENANCE_OS.md).

## Codex Workflow, Validation, And Reporting

Pick the smallest validation set that proves the current change. Docs/generator tasks use docs diff-checks plus secret scan; frontend source changes need route-aware tests and browser evidence; backend/API/auth/provider changes need focused tests and wider gates when protected or shared contracts are near scope.

Use the task mode and workspace the prompt actually names. `WORKTREE-WORKER` means stay inside the prompt workspace and branch. `SERIAL-MAIN` is only for an explicit shared-main task. Do not push unless the prompt authorizes it, and keep the branch name exactly aligned with the task contract.

Before final reporting, fetch the latest `origin/main` when the task contract requires it, rebase onto it, rerun the focused validation, and confirm the branch is clean, ahead of `origin/main`, and not behind.

Cleanup happens after the final report is captured, not before. Do not create one-off task report markdown when the canonical final report template already exists. Do not broaden validation just to look thorough, and do not treat green tests on a different surface as proof for this one.

If docs are changed, change the docs because the source-of-truth moved or the behavior did, not because the task needs a separate story file.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`docs/codex/WOLFYSTOCK_CODEX_DISCOVERY_PROTOCOL.md`](codex/WOLFYSTOCK_CODEX_DISCOVERY_PROTOCOL.md), [`docs/codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md`](codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md), [`docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`](codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md), [`docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`](codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md), [`docs/codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md`](codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md), [`docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`](codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md), [`docs/codex/NO_ADVICE_REGRESSION_GUARDS.md`](codex/NO_ADVICE_REGRESSION_GUARDS.md), [`docs/frontend/validation-playbook.md`](frontend/validation-playbook.md).

## Public Launch NO-GO Blockers

Current public launch status is NO-GO. Existing foundations and offline validators are useful review plumbing, but they do not approve launch and do not replace target-environment operator evidence.

Main blocker families are security/MFA/RBAC, provider/options/data quality, portfolio/backtest safety, WS2 multi-instance runtime, cost/quota/provider circuit enforcement, deployment/backup/rollback, and final release-candidate gates.

Machine-readable launch evidence and operator bundles must remain sanitized and manual-review-only. `releaseApproved=false` remains the safe default unless every hard blocker has accepted external/manual evidence.

Source provenance: [`docs/audits/README.md`](audits/README.md), [`docs/audits/public-launch-readiness-master.md`](audits/public-launch-readiness-master.md), [`docs/audits/public-launch-gap-register.md`](audits/public-launch-gap-register.md), [`docs/audits/deployment-readiness-checklist.md`](audits/deployment-readiness-checklist.md), [`docs/audits/launch-acceptance-evidence-pack.md`](audits/launch-acceptance-evidence-pack.md).

## Known Experimental And Demo-Only Surfaces

Treat fixture-only, demo-only, dry-run, no-send, local-only, diagnostic-only, disabled-by-default, synthetic, fallback, cache-only, and advisory-only labels as hard safety signals.

Current examples include Options fixture/dry-run providers, disabled live options stubs, DuckDB diagnostic/local-only posture, WS2 synthetic worker and process-local SSE limitations, provider source-confidence helpers, optional enrichment metadata, and alert/notification dry-run surfaces.

Do not present these as production-grade, launch-approved, live, billing-authoritative, decision-grade, or tradeable capabilities without separate approval and current validation.

Source provenance: [`docs/audits/options-provider-adapter-contract.md`](audits/options-provider-adapter-contract.md), [`docs/quant-duckdb-engine.md`](quant-duckdb-engine.md), [`docs/alerts/README.md`](alerts/README.md), [`docs/operations/background-job-queue-boundary.md`](operations/background-job-queue-boundary.md), [`docs/operations/queue-ws2-metrics-production-readiness.md`](operations/queue-ws2-metrics-production-readiness.md), [`docs/data-reliability/provider-source-confidence-contract.md`](data-reliability/provider-source-confidence-contract.md), [`docs/audits/data-pipeline-r2-progressive-enrichment.md`](audits/data-pipeline-r2-progressive-enrichment.md).

## Source-Of-Truth Index

Use this compact index to jump to the canonical doc for a topic, then read the supporting docs only as needed. If a topic is historical or archive-only, say so explicitly and do not treat it as current authority.

| Topic | Canonical doc | Supporting docs | Owner / surface | When an AI should read it | Type |
| --- | --- | --- | --- | --- | --- |
| AI onboarding and navigation | [`docs/AI_PROJECT_MANUAL.md`](AI_PROJECT_MANUAL.md) | [`AGENTS.md`](../AGENTS.md), [`docs/DOCS_INDEX.md`](DOCS_INDEX.md), [`scripts/build_ai_project_manual.py`](../scripts/build_ai_project_manual.py) | repo-wide AI maintenance | first five minutes of any task | generated manual source |
| Repository AI rules | [`AGENTS.md`](../AGENTS.md) | [`docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md`](WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md), [`docs/DOCS_INDEX.md`](DOCS_INDEX.md) | repo-wide | before any edit, commit, or validation | policy |
| Codex workflow and reporting | [`docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`](codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md) | [`docs/codex/WOLFYSTOCK_CODEX_DISCOVERY_PROTOCOL.md`](codex/WOLFYSTOCK_CODEX_DISCOVERY_PROTOCOL.md), [`docs/codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md`](codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md), [`docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`](codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md), [`docs/codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md`](codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md), [`docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`](codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md), [`docs/codex/NO_ADVICE_REGRESSION_GUARDS.md`](codex/NO_ADVICE_REGRESSION_GUARDS.md) | Codex workers | before any execution-class task | policy |
| Protected backend domains | [`docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`](codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md) | [`docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`](WOLFYSTOCK_SYSTEM_HANDBOOK.md), [`docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`](codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md) | scanner / backtest / portfolio / provider / auth / options | before touching protected runtime semantics | policy |
| Provider source confidence | [`docs/data-reliability/provider-source-confidence-contract.md`](data-reliability/provider-source-confidence-contract.md) | [`docs/provider-data/README.md`](provider-data/README.md), [`docs/operations/provider-capability-metadata.md`](operations/provider-capability-metadata.md), [`docs/audits/data-quality-user-disclosure-policy.md`](audits/data-quality-user-disclosure-policy.md) | provider / data | before reasoning about freshness, coverage, or authority | contract |
| Official risk and quote activation | [`docs/data/market-source-activation-blueprint.md`](data/market-source-activation-blueprint.md) | [`docs/product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md`](product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md), [`docs/product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md`](product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md) | market overview / liquidity / rotation | before activating official VIX, rates, or quote coverage | roadmap |
| Symbol research packet | [`docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md`](product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md) | [`docs/product-recovery/DATA_COVERAGE_MATRIX.md`](product-recovery/DATA_COVERAGE_MATRIX.md), [`docs/product-recovery/DATA011_PACKET_CONSUMPTION_ACCEPTANCE.md`](product-recovery/DATA011_PACKET_CONSUMPTION_ACCEPTANCE.md) | watchlist / stock detail | before assembling row-level research packets | contract |
| Quote spine and target env evidence | [`docs/product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md`](product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md) | [`docs/product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md`](product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md), [`docs/product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md`](product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md) | scanner / watchlist / stock / portfolio / market / rotation | before quote or history lineage changes | contract |
| Backtest dataset lineage | [`docs/product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md`](product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md) | [`docs/backtest/README.md`](backtest/README.md), [`docs/backtest-system.md`](backtest-system.md), [`docs/product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md`](product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md) | backtest / factor research | before adjusting backtest lineage or sweep storage | contract |
| Options entitlement and no-advice | [`docs/product-recovery/DATA034_OPTIONS_PROVIDER_ENTITLEMENT_DECISION.md`](product-recovery/DATA034_OPTIONS_PROVIDER_ENTITLEMENT_DECISION.md) | [`docs/options/README.md`](options/README.md), [`docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md`](product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md), [`docs/audits/options-provider-adapter-contract.md`](audits/options-provider-adapter-contract.md), [`docs/audits/trading-no-advice-product-policy.md`](audits/trading-no-advice-product-policy.md) | options lab | before touching options chain, Greeks, or strategy copy | decision record |
| Scenario baseline evidence | [`docs/product-recovery/DATA035_SCENARIO_DURABLE_BASELINE_SNAPSHOT_PLAN.md`](product-recovery/DATA035_SCENARIO_DURABLE_BASELINE_SNAPSHOT_PLAN.md) | [`docs/product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md`](product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md), [`docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md`](product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md) | scenario lab / target-env evidence | before scenario baseline or operator evidence work | plan |
| Market data recovery summary | [`docs/product-recovery/WOLFYSTOCK_PRODUCT_RECOVERY_PLAN.md`](product-recovery/WOLFYSTOCK_PRODUCT_RECOVERY_PLAN.md) | [`docs/product-recovery/DATA_COVERAGE_MATRIX.md`](product-recovery/DATA_COVERAGE_MATRIX.md), [`docs/product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md`](product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md) | recovery program | before any product-recovery task | roadmap |
| Surface entry docs | [`docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`](WOLFYSTOCK_SYSTEM_HANDBOOK.md) | [`docs/market-overview/README.md`](market-overview/README.md), [`docs/scanner/README.md`](scanner/README.md), [`docs/liquidity/README.md`](liquidity/README.md), [`docs/rotation/README.md`](rotation/README.md), [`docs/portfolio/README.md`](portfolio/README.md), [`docs/backtest/README.md`](backtest/README.md), [`docs/options/README.md`](options/README.md) | route families | before touching a user-facing route | entry point |
| Historical / archive only | [`docs/ARCHIVE_INDEX.md`](ARCHIVE_INDEX.md) | [`docs/audits/README.md`](audits/README.md), [`docs/architecture/file-governance-taxonomy.md`](architecture/file-governance-taxonomy.md) | provenance only | only to trace prior decisions or retired evidence | historical |
| Current documentation navigation | [`docs/DOCS_INDEX.md`](DOCS_INDEX.md) | [`docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md`](WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md), [`docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`](WOLFYSTOCK_SYSTEM_HANDBOOK.md) | maintainers | when you need the current doc tree | index |

The canonical doc should be the first stop. Supporting docs are there to narrow scope, validate edge cases, or explain why a path is blocked, partial, or observation-only.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`docs/DOCS_INDEX.md`](DOCS_INDEX.md), [`docs/ARCHIVE_INDEX.md`](ARCHIVE_INDEX.md), [`docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md`](WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md), [`docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`](WOLFYSTOCK_SYSTEM_HANDBOOK.md), [`docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`](codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md), [`docs/codex/WOLFYSTOCK_CODEX_DISCOVERY_PROTOCOL.md`](codex/WOLFYSTOCK_CODEX_DISCOVERY_PROTOCOL.md), [`docs/codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md`](codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md), [`docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`](codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md), [`docs/codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md`](codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md), [`docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`](codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md), [`docs/codex/NO_ADVICE_REGRESSION_GUARDS.md`](codex/NO_ADVICE_REGRESSION_GUARDS.md), [`docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`](codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md), [`docs/data-reliability/provider-source-confidence-contract.md`](data-reliability/provider-source-confidence-contract.md), [`docs/operations/provider-capability-metadata.md`](operations/provider-capability-metadata.md), [`docs/data/market-source-activation-blueprint.md`](data/market-source-activation-blueprint.md), [`docs/product-recovery/WOLFYSTOCK_PRODUCT_RECOVERY_PLAN.md`](product-recovery/WOLFYSTOCK_PRODUCT_RECOVERY_PLAN.md), [`docs/product-recovery/DATA_COVERAGE_MATRIX.md`](product-recovery/DATA_COVERAGE_MATRIX.md), [`docs/product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md`](product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md), [`docs/product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md`](product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md), [`docs/product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md`](product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md), [`docs/product-recovery/DATA034_OPTIONS_PROVIDER_ENTITLEMENT_DECISION.md`](product-recovery/DATA034_OPTIONS_PROVIDER_ENTITLEMENT_DECISION.md), [`docs/product-recovery/DATA035_SCENARIO_DURABLE_BASELINE_SNAPSHOT_PLAN.md`](product-recovery/DATA035_SCENARIO_DURABLE_BASELINE_SNAPSHOT_PLAN.md), [`docs/product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md`](product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md), [`docs/product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md`](product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md), [`docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md`](product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md), [`docs/market-overview/README.md`](market-overview/README.md), [`docs/scanner/README.md`](scanner/README.md), [`docs/liquidity/README.md`](liquidity/README.md), [`docs/rotation/README.md`](rotation/README.md), [`docs/options/README.md`](options/README.md), [`docs/portfolio/README.md`](portfolio/README.md), [`docs/backtest/README.md`](backtest/README.md), [`docs/backtest-system.md`](backtest-system.md), [`docs/audits/data-quality-user-disclosure-policy.md`](audits/data-quality-user-disclosure-policy.md), [`docs/audits/options-provider-adapter-contract.md`](audits/options-provider-adapter-contract.md), [`docs/audits/backtest-portfolio-public-safety-audit.md`](audits/backtest-portfolio-public-safety-audit.md), [`docs/audits/trading-no-advice-product-policy.md`](audits/trading-no-advice-product-policy.md).

## Source Inclusion And Exclusion Policy

The generator discovers Markdown files but only includes curated high-signal sources in the manual. This prevents the manual from exceeding practical AI context size and avoids treating old evidence as current truth.

Default inclusions are current authority docs, domain entry points, launch/blocker indexes, Codex workflow docs, and a few targeted domain contracts. Default exclusions are archive lanes, local/generated evidence, task audit dumps, language duplicates, fixture-local READMEs, AI-governance mirrors, and broad legacy guides unless a current source explicitly promotes them.

When source docs conflict, prefer the current prompt, `AGENTS.md`, current code/tests/scripts, and active authority docs. Use archives for provenance only.

Source provenance: [`docs/DOCS_INDEX.md`](DOCS_INDEX.md), [`docs/architecture/file-governance-taxonomy.md`](architecture/file-governance-taxonomy.md), [`docs/ARCHIVE_INDEX.md`](ARCHIVE_INDEX.md), [`docs/audits/README.md`](audits/README.md).

## Source Map

This map is generated from the curated source allowlist. It is a lookup aid, not a replacement for reading the linked sources before editing a domain.

| Manual section | Primary sources | Update trigger | Validation |
| --- | --- | --- | --- |
| Start Here: Authority And Operating Posture | `AGENTS.md`<br>`docs/DOCS_INDEX.md`<br>`docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md`<br>`docs/architecture/file-governance-taxonomy.md` | AI governance, source authority, archive policy, or generated-artifact policy changes. | Docs/generator validation plus `python scripts/check_ai_assets.py` when AI governance assets change. |
| Product Purpose And Current Deployment Boundary | `README.md`<br>`docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`<br>`docs/DEPLOY.md`<br>`docs/audits/private-beta-readiness.md`<br>`docs/audits/public-launch-readiness-master.md`<br>`docs/audits/trading-no-advice-product-policy.md` | Product positioning, deployment mode, private beta, no-advice, or launch verdict changes. | Docs-only validation for docs changes; release/UAT evidence for deployment posture changes. |
| Protected Domains And Hard Stops | `AGENTS.md`<br>`docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`<br>`docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`<br>`docs/codex/NO_ADVICE_REGRESSION_GUARDS.md`<br>`docs/audits/trading-no-advice-product-policy.md`<br>`docs/data-reliability/provider-source-confidence-contract.md`<br>`docs/operations/provider-capability-metadata.md` | Protected-domain boundaries, no-advice policy, provider/source confidence, or hard-stop validation rules change. | Read the guard docs first; then use focused tests and the smallest validation tier that proves the protected semantic stayed intact. |
| Product Surfaces And Data Reality | `README.md`<br>`docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`<br>`docs/market-overview/README.md`<br>`docs/scanner/README.md`<br>`docs/liquidity/README.md`<br>`docs/rotation/README.md`<br>`docs/options/README.md`<br>`docs/portfolio/README.md`<br>`docs/backtest/README.md`<br>`docs/backtest-system.md`<br>`docs/product-recovery/WOLFYSTOCK_PRODUCT_RECOVERY_PLAN.md`<br>`docs/product-recovery/DATA_COVERAGE_MATRIX.md`<br>`docs/product-recovery/DATA011_PACKET_CONSUMPTION_ACCEPTANCE.md`<br>`docs/product-recovery/DATA016_FOCUSED_ACCEPTANCE.md`<br>`docs/product-recovery/DATA021_REAL_DATA_VALUE_ACCEPTANCE.md`<br>`docs/product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md`<br>`docs/product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md`<br>`docs/product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md`<br>`docs/product-recovery/DATA034_OPTIONS_PROVIDER_ENTITLEMENT_DECISION.md`<br>`docs/product-recovery/DATA035_SCENARIO_DURABLE_BASELINE_SNAPSHOT_PLAN.md`<br>`docs/product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md`<br>`docs/product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md`<br>`docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md`<br>`docs/data/market-source-activation-blueprint.md`<br>`docs/data-reliability/provider-source-confidence-contract.md`<br>`docs/operations/provider-capability-metadata.md`<br>`docs/audits/data-quality-user-disclosure-policy.md`<br>`docs/audits/options-provider-adapter-contract.md`<br>`docs/audits/backtest-portfolio-public-safety-audit.md`<br>`docs/audits/trading-no-advice-product-policy.md` | Surface maps, data-roadmap boundaries, or any professional data family readiness change. | Use the source docs and current code/tests to classify every surface and family as ready, partial, blocked, missing, unauthorized, or observation-only before editing anything else. |
| Architecture And Major Surfaces | `docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`<br>`docs/architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md`<br>`docs/architecture/backend-frontend-modular-maintenance-handbook.md`<br>`README.md` | Route map, API group, module ownership, dependency direction, or first-files debug flow changes. | Focused validation for touched surface; architecture docs-only validation for handbook-only changes. |
| Auth, RBAC, And MFA | `docs/audits/index-security-rbac-mfa.md`<br>`docs/audits/auth-rbac-release-security-guide.md`<br>`docs/audits/admin-rbac-r5-coarse-fallback-removal-plan.md`<br>`docs/audits/security-mfa-secret-storage-hardening-plan.md`<br>`docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md` | Any auth, session, capability, MFA, security evidence, admin route, or role-governance change. | Focused auth/RBAC tests, route-capability inventory, redaction checks, and wider gates when enforcement changes. |
| Portfolio And Backtest | `docs/portfolio/README.md`<br>`docs/backtest/README.md`<br>`docs/backtest-system.md`<br>`docs/audits/backtest-portfolio-public-safety-audit.md`<br>`docs/codex/WOLFYSTOCK_BACKTEST_UNIVERSE_RULES.md` | Portfolio accounting/read models, backtest execution/readback/export, public-safety, or owner-isolation changes. | Portfolio/backtest focused tests, golden fixtures, mutation guards, no-advice checks, and owner-isolation evidence when applicable. |
| Provider, Quota, And Cost | `docs/provider-data/README.md`<br>`docs/codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md`<br>`docs/audits/index-provider-data-options.md`<br>`docs/audits/index-cost-quota-observability.md`<br>`docs/audits/quota-reserve-release-operator-evidence-checklist.md` | Provider routing/fallback/freshness/cache, quota, circuit, budget, cost, or provider diagnostics changes. | Provider/cache/freshness tests, quota lifecycle tests, no-live-call proof when scoped, and redaction checks. |
| WS2 And Durable Runtime | `docs/operations/background-job-queue-boundary.md`<br>`docs/operations/queue-ws2-metrics-production-readiness.md`<br>`docs/audits/ws2-multi-instance-smoke-test-design.md`<br>`docs/audits/ws2-multi-user-runtime-cost-control-design.md` | Analysis task queue, SSE, durable polling, worker, broker, multi-instance, or WS2 readiness changes. | Synthetic/local smoke first; staging/API A-B evidence and operator artifacts only when deployment posture changes. |
| Options And Data Pipeline | `docs/options/README.md`<br>`docs/audits/options-provider-adapter-contract.md`<br>`docs/audits/data-pipeline-r2-progressive-enrichment.md`<br>`docs/audits/data-quality-user-disclosure-policy.md`<br>`docs/audits/trading-no-advice-product-policy.md` | Options providers, chain/Greeks, scenario copy, optional enrichment, data-quality, or no-advice changes. | Options/data-quality focused tests, fixture/mocked-provider tests, no-order scans, and redaction checks. |
| Frontend IA And UI Conventions | `docs/frontend/README.md`<br>`docs/frontend/visual-system.md`<br>`docs/frontend/validation-playbook.md`<br>`docs/frontend/WOLFYSTOCK_FRONTEND_NOISE_BUDGET.md`<br>`docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md`<br>`docs/frontend/WOLFYSTOCK_ADMIN_MAINTENANCE_OS.md` | Frontend route taxonomy, primitives, route IA, visual system, consumer/admin disclosure, or browser-evidence rules change. | Frontend focused tests plus lint/build/browser evidence when UI source or visual behavior changes. |
| Codex Workflow, Validation, And Reporting | `AGENTS.md`<br>`docs/codex/WOLFYSTOCK_CODEX_DISCOVERY_PROTOCOL.md`<br>`docs/codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md`<br>`docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`<br>`docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`<br>`docs/codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md`<br>`docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`<br>`docs/codex/NO_ADVICE_REGRESSION_GUARDS.md`<br>`docs/frontend/validation-playbook.md` | Task modes, prompt fields, validation matrix, final report format, or frontend evidence rules change. | Run the smallest validation that proves the touched files, then record the command, exit status, and any blocker in the final report. |
| Public Launch NO-GO Blockers | `docs/audits/README.md`<br>`docs/audits/public-launch-readiness-master.md`<br>`docs/audits/public-launch-gap-register.md`<br>`docs/audits/deployment-readiness-checklist.md`<br>`docs/audits/launch-acceptance-evidence-pack.md` | Launch verdict, blocker register, release checklist, operator evidence contract, or launch acceptance process changes. | Docs-only validation for launch docs; release-grade gates and sanitized operator evidence for actual launch posture changes. |
| Known Experimental And Demo-Only Surfaces | `docs/audits/options-provider-adapter-contract.md`<br>`docs/quant-duckdb-engine.md`<br>`docs/alerts/README.md`<br>`docs/operations/background-job-queue-boundary.md`<br>`docs/operations/queue-ws2-metrics-production-readiness.md`<br>`docs/data-reliability/provider-source-confidence-contract.md`<br>`docs/audits/data-pipeline-r2-progressive-enrichment.md` | Any diagnostic/demo/fixture/dry-run surface becomes runtime, production, or user-visible decision authority. | Fail-closed tests, no-live-call proof, redaction checks, docs wording review, and task-specific runtime evidence. |
| Source-Of-Truth Index | `AGENTS.md`<br>`docs/DOCS_INDEX.md`<br>`docs/ARCHIVE_INDEX.md`<br>`docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md`<br>`docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`<br>`docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`<br>`docs/codex/WOLFYSTOCK_CODEX_DISCOVERY_PROTOCOL.md`<br>`docs/codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md`<br>`docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`<br>`docs/codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md`<br>`docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`<br>`docs/codex/NO_ADVICE_REGRESSION_GUARDS.md`<br>`docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`<br>`docs/data-reliability/provider-source-confidence-contract.md`<br>`docs/operations/provider-capability-metadata.md`<br>`docs/data/market-source-activation-blueprint.md`<br>`docs/product-recovery/WOLFYSTOCK_PRODUCT_RECOVERY_PLAN.md`<br>`docs/product-recovery/DATA_COVERAGE_MATRIX.md`<br>`docs/product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md`<br>`docs/product-recovery/DATA031_BACKTEST_PROFESSIONAL_UPGRADE_AUDIT.md`<br>`docs/product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md`<br>`docs/product-recovery/DATA034_OPTIONS_PROVIDER_ENTITLEMENT_DECISION.md`<br>`docs/product-recovery/DATA035_SCENARIO_DURABLE_BASELINE_SNAPSHOT_PLAN.md`<br>`docs/product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md`<br>`docs/product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md`<br>`docs/product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md`<br>`docs/market-overview/README.md`<br>`docs/scanner/README.md`<br>`docs/liquidity/README.md`<br>`docs/rotation/README.md`<br>`docs/options/README.md`<br>`docs/portfolio/README.md`<br>`docs/backtest/README.md`<br>`docs/backtest-system.md`<br>`docs/audits/data-quality-user-disclosure-policy.md`<br>`docs/audits/options-provider-adapter-contract.md`<br>`docs/audits/backtest-portfolio-public-safety-audit.md`<br>`docs/audits/trading-no-advice-product-policy.md` | Canonical source maps, source curation, or topic ownership changes. | Read the canonical doc first, then supporting docs, and use the class label to decide whether the topic is policy, contract, roadmap, historical, or generated manual source. |
| Source Inclusion And Exclusion Policy | `docs/DOCS_INDEX.md`<br>`docs/architecture/file-governance-taxonomy.md`<br>`docs/ARCHIVE_INDEX.md`<br>`docs/audits/README.md` | Docs taxonomy, archive policy, generated artifact policy, or manual source curation changes. | Run this generator twice and prove deterministic output; run docs diff-check and secret scan. |

## JSON Manifest

The machine-readable manifest is generated at `docs/AI_PROJECT_MANUAL_SOURCES.json`. It records source paths, titles, purposes, categories, SHA-256 hashes, byte counts, line counts, manual sections, and discovery/exclusion statistics.

Current discovery summary:

- Markdown discovered after pruned directory rules: 383
- Candidate Markdown after exclusion policy: 236
- Curated sources included in this manual: 75

Exclusion policy:

- `.git/**`
- `node_modules/**`
- `dist/**`
- `static/**`
- `coverage/**`
- `reports/** unless explicitly high-value`
- `worktree_archives/**`
- `archive folders unless explicitly allowlisted`
- `docs/codex/audits/** task reports unless explicitly promoted by a current source`
- `local/generated evidence such as .codex/**, .claude/reviews/**, artifacts/**, screenshots/**, and test-results/**`
- `AI-governance mirrors such as CLAUDE.md and .github/copilot-instructions.md when AGENTS.md is available`
- `language duplicates and broad translated guides unless generating a language-specific manual`
