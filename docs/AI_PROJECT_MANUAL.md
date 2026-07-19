# WolfyStock AI Project Manual

> GENERATED FILE. DO NOT EDIT DIRECTLY.
>
> Edit `scripts/build_ai_project_manual.py` or the tiny canonical source files, then run `python scripts/build_ai_project_manual.py`.
> Check freshness with `python scripts/build_ai_project_manual.py --check`.

Status: generated comprehensive project handbook after the DOCS-006 hard Markdown collapse.
Audience: future AI models, Codex workers, review agents, maintainers, and humans assigning AI work.
Authority: operational handbook and source map; `AGENTS.md` remains the repository AI-collaboration rule source.
Do not use as: launch approval, protected-domain authorization, stale audit authority, trading advice, or replacement for current source/test inspection.

## Table Of Contents

- [Project Identity And Product Purpose](#project-identity-and-product-purpose)
- [Architecture Overview](#architecture-overview)
- [Dependency Environment Authority](#dependency-environment-authority)
- [Frontend Surfaces](#frontend-surfaces)
- [Backend API And Service Structure](#backend-api-and-service-structure)
- [Data Providers And Data Reality Boundaries](#data-providers-and-data-reality-boundaries)
- [Market, Options, Macro, Liquidity, Backtest, Scenario, And Portfolio Domains](#market-options-macro-liquidity-backtest-scenario-and-portfolio-domains)
- [Operator Evidence Boundary](#operator-evidence-boundary)
- [Data Coverage Consumer Projection](#data-coverage-consumer-projection)
- [DuckDB Diagnostic Boundary](#duckdb-diagnostic-boundary)
- [Provider Provenance Vocabulary](#provider-provenance-vocabulary)
- [Professional Analytics Roadmap And Readiness](#professional-analytics-roadmap-and-readiness)
- [Production Readiness Documentation Authority](#production-readiness-documentation-authority)
- [Protected Domains And Safety Rules](#protected-domains-and-safety-rules)
- [No-Advice Policy](#no-advice-policy)
- [Validation Matrix](#validation-matrix)
- [Codex Workflow And Landing Changes](#codex-workflow-and-landing-changes)
- [Current Canonical File Map](#current-canonical-file-map)
- [Compressed Project History](#compressed-project-history)
- [AI Onboarding Checklist](#ai-onboarding-checklist)
- [Source Map](#source-map)
- [JSON Manifest](#json-manifest)

## Project Identity And Product Purpose

WolfyStock is a professional financial research terminal for market operators, discretionary research, and portfolio workflows across US, CN, and HK markets. It combines market context, scanner discovery, watchlists, rule backtesting, portfolio tracking, provider diagnostics, admin observability, and AI-assisted research in a Python/FastAPI plus React/TypeScript codebase.

The product solves the problem of fragmented research evidence: market regime, quote/history readiness, portfolio exposure, scenario shocks, options context, and backtest evidence are easy to confuse when they come from different providers and freshness levels. WolfyStock's durable direction is to show the evidence, source authority, lineage, and readiness boundary before any research conclusion.

It is not a broker, order-entry surface, retail trading game, or unconstrained LLM wrapper. All user-visible research must stay analytical and no-advice.

Source provenance: [`README.md`](../README.md), [`AGENTS.md`](../AGENTS.md).

## Architecture Overview

Main runtime entrypoints are `main.py` for analysis/local automation, `server.py` and `api/app.py` for the FastAPI app, `api/v1/router.py` for API grouping, `src/services/` for business services, `src/repositories/` for persistence boundaries, `src/schemas/` for DTO/schema contracts, `data_provider/` for provider adapters and fallback normalization, `bot/` for notification integrations, `apps/dsa-web/` for the web terminal, `apps/dsa-desktop/` for the Electron wrapper, `scripts/` for local and CI utilities, and `.github/workflows/` for CI/release automation. `main.py --serve` and `main.py --serve-only` wait for application import, FastAPI lifespan startup, and socket bind before reporting API startup. Any failure or bounded startup timeout exits the main process with code 1 before bots, analysis, scheduling, or keepalive, giving Desktop, Docker, and UAT one authoritative process-level startup signal. Frontend asset preparation returning `False` remains a warning-only degradation, and readiness 503 after a successful bind remains distinct from startup failure. Normal returns and interactive shutdown explicitly stop and join the managed uvicorn thread.

Maintain bounded contexts. Consumers should call public facades, API clients, schemas, DTOs, validators, and documented commands. Do not reach into private engines, repositories, provider clients, cache keys, ledger internals, or mutation code from another domain just to make a local task easier.

Shared contracts, schema changes, root config, CI, dependency files, auth, provider runtime, broker/accounting, DB migrations, and frontend route-entry behavior are high-risk and require explicit task scope.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`README.md`](../README.md).

## Dependency Environment Authority

`./wolfy` is the repository-owned dependency environment authority. `requirements.txt` and `requirements-dev.txt` preserve direct runtime and development/test intent; they are not install locks. `requirements-lock.json` binds their normalized SHA-256 hashes to a reviewed family of CPython 3.11/3.12 pip locks and target/profile artifact projections. Each selected distribution is exact-pinned; compatible artifact filenames carry SHA-256 coverage, and source distributions record their reviewed build backend and exact locked build requirements. PyArrow is the single reviewed Parquet read/write authority in every supported target projection; no second Parquet engine or fallback authority is accepted.

Run `./wolfy lock python --check` for a no-install freshness, schema, pin, hash, resolver, target-matrix, and normalization check. Only an explicit dependency review may run `./wolfy lock python --update`. The update command uses `uv 0.11.19` only as a universal resolver and reports direct and transitive changes separately; it never runs implicitly. Runtime installation remains pip-based through `./wolfy bootstrap --ensure`, which selects the reviewed target/profile projection and installs with `--no-deps --require-hashes`.

The reviewed targets are CPython 3.11 on Linux x86_64 for runtime/development, Linux aarch64 for runtime, macOS arm64/x86_64 for runtime/development, and Windows AMD64 for runtime/development, plus CPython 3.12 on macOS arm64/x86_64 and Windows AMD64 for runtime/development. Docker `linux/arm64` and Python-detected Linux `aarch64` select the same `manylinux_2_36_aarch64` runtime projection; Linux aarch64 has no development projection. Release containers map BuildKit `amd64` and `arm64` to the reviewed CPython 3.11 Linux x86_64 and aarch64 runtime projections, respectively. Their dependency builder reuses the same locked installer with `--no-deps --require-hashes --no-build-isolation`; requirements intent, development locks, uv, missing architectures, and unsupported architectures cannot enter that install path. Unsupported target/profile combinations fail before installation. Online and offline bootstrap use the same graph and artifact projection; offline mode fails on missing artifacts and neither mode rewrites or resolves the lock. Environment evidence records lock schema/policy, content and input hashes, resolver identity, normalized target/profile/lock/projection, distribution, artifact, source-build and hash counts, and hash-verification status. The same bootstrap authority provisions reviewed `rg` and the exact Playwright-derived Chromium revision 1208 as persistent content-addressed snapshots, verifies the browser executable can launch, and supplies that managed executable to every Playwright project. Offline bootstrap reuses those verified snapshots or fails closed when material is absent; host `PATH`, global `rg`, and system-browser fallback are not authorities. Combined environment evidence binds the Python, Web, browser, and managed-tool input and installed fingerprints and records whether bootstrap used the network. Static marker, wheel-tag, ABI, and source-build validation is not real-platform execution.

Canonical UAT builds the Web artifact at most once, verifies and reuses the immutable artifact, and binds source SHA/tree identity, the combined environment fingerprint, dependency identity, and asset hashes. It does not write below managed `node_modules`. Authenticated smoke establishes real HttpOnly cookie sessions and keeps anonymous, member, limited-admin, logout, and revoked-session behavior explicit; failed session establishment blocks qualification. The `release-real-runtime` Playwright project must use the same managed Chromium executable, real product routes, and zero retries before browser evidence can qualify.

`.github/workflows/release.yml` is the sole publication authority. It builds one source/Web/multi-platform OCI candidate, binds the exact source, nested environment, reviewed lock, Web artifact, OCI index, amd64 and arm64 identities, and produces twelve fail-closed gate records. The qualified manifest binds every gate evidence digest. Promotion copies the already-qualified registry digest and never rebuilds or resolves dependencies. Electron desktop artifacts remain outside this graph while their legacy scripts retain independent install behavior; they must not be published by a parallel workflow.

Source provenance: [`README.md`](../README.md), [`AGENTS.md`](../AGENTS.md).

## Frontend Surfaces

| Surface | Purpose | Primary ownership | Readiness boundary |
| --- | --- | --- | --- |
| Market Overview | Regime, breadth, official risk, and macro first read | `api/v1/endpoints/market_overview.py`, `src/services/market_overview_service.py`, `apps/dsa-web/src/pages/MarketOverviewPage.tsx` | Partial until official risk, quote authority, and target-environment evidence are proven. |
| Scanner | Candidate discovery and watchlist handoff | `api/v1/endpoints/scanner.py`, `src/services/market_scanner_service.py`, `apps/dsa-web/src/pages/UserScannerPage.tsx` | Partial; quote, history, universe, freshness, turnover, and packet readiness must fail closed. |
| Watchlist | Saved symbols and row-level research queue | `api/v1/endpoints/watchlist.py`, `src/services/watchlist_service.py`, `src/services/watchlist_research_overlay_service.py`, `apps/dsa-web/src/pages/WatchlistPage.tsx` | Partial; row packets may lack quote freshness, catalyst age, or scanner lineage and must say so. |
| Stock Detail | Symbol research packet and structure decision | `api/v1/endpoints/stocks.py`, `src/services/stock_service.py`, `src/services/stock_structure_decision_service.py` | Partial; no invented quote, fundamental, event, SEC, peer, or catalyst evidence. |
| Liquidity Monitor | Capital pressure and stress context | `api/v1/endpoints/liquidity_monitor.py`, `src/services/liquidity_monitor_service.py`, `apps/dsa-web/src/pages/LiquidityMonitorPage.tsx` | Partial; macro, flow, and proxy rows remain capped unless official source authority exists. |
| Rotation Radar | ETF/index family rotation context | `api/v1/endpoints/market.py`, rotation services, `apps/dsa-web/src/pages/MarketRotationRadarPage.tsx` | Partial; quote coverage, membership, and official source authority gate headline claims. |
| Options Lab | Read-only options research console | `api/v1/endpoints/options.py`, `src/services/options_lab_service.py`, `apps/dsa-web/src/pages/OptionsLabPage.tsx` | Observation-only unless entitlement, redisplay, chain, Greeks, IV, OI, volume, and methodology proof exist. |
| Scenario Lab | Bounded shock comparison | `api/v1/endpoints/market.py`, `src/services/market_scenario_lab_engine.py`, `apps/dsa-web/src/pages/ScenarioLabPage.tsx` | Partial; sample, request-supplied, fallback, or static baselines are observation-only. |
| Backtest | Deterministic rule backtest and stored readback | `api/v1/endpoints/backtest.py`, `src/core/rule_backtest_engine.py`, `src/services/backtest_service.py`, `apps/dsa-web/src/pages/BacktestPage.tsx` | Research-useful v1 semantics; no optimizer, winner, allocation, or fake performance semantics. |
| Portfolio | Accounts, holdings, cash, FX, ledger, risk, and attribution | `api/v1/endpoints/portfolio.py`, `src/services/portfolio_service.py`, `apps/dsa-web/src/pages/PortfolioPage.tsx` | Accounting authority is protected; price/FX lineage and broker/order implications must stay explicit. |
| Admin/Ops | Operator observability and protected diagnostics | `api/v1/endpoints/admin/*`, `src/services/admin_*`, `apps/dsa-web/src/pages/Admin*` | Manual-review-gated; never leak raw provider, credential, security, or internal payload details. |

Frontend work should preserve the operator-terminal posture: dense but legible, route-first, evidence-first, and calm. Prefer tables, rows, rails, drawers, strips, and explicit disclosure states over generic card sprawl. Each route should make the primary research task visible in the first viewport and should keep raw provider, cache, schema, debug, credential, and fallback internals out of consumer copy.

Source provenance: [`README.md`](../README.md), [`AGENTS.md`](../AGENTS.md).

## Backend API And Service Structure

Backend/API work should keep API routers thin, services authoritative for business semantics, repositories responsible for persistence, schemas/DTOs explicit, and provider adapters isolated behind provider-runtime boundaries. FastAPI endpoints should not embed scanner ranking math, portfolio accounting, provider fallback ordering, auth policy, or report rendering internals.

Core API families include auth, analysis, history, stocks, scanner, watchlist, market overview, market/scenario, liquidity, rotation, options, portfolio, backtest, quant, system, usage, admin, and diagnostics. Additive fields are preferred over breaking response contracts; deleted or renamed fields require client compatibility review.

For Python changes, prefer `./scripts/ci_gate.sh`. At minimum run `python -m py_compile <changed_python_files>` and the closest deterministic tests. Protected semantic changes need focused regression evidence.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`README.md`](../README.md).

## Data Providers And Data Reality Boundaries

Provider runtime owns provider order, fallback, retry/circuit behavior, timeout posture, freshness labels, source authority, display rights, optional enrichment budgets, sanitized diagnostics, and cache/local-first behavior. Do not reorder providers, deepen live fallback, add broad optional fanout, or expose raw provider payloads without explicit scope.

Fallback, cached, proxy, repaired, inferred, fixture, synthetic, dry-run, parser-only, request-supplied, and observation-only data must remain visibly not-live and not-decision-grade. Missing data stays missing; do not fabricate quote, fundamental, event, IV, Greek, bid/ask, OI, volume, FX, benchmark, or source-freshness fields.

| Data family | Readiness | Operational boundary |
| --- | --- | --- |
| Official risk and volatility | Partial | VIX/volatility, rates, Fed liquidity, credit stress, and official macro rows must be source-authorized before score-grade claims. |
| Authorized quote spine | Partial | US/CN/HK quote and daily OHLCV snapshots need durable lineage, freshness, and redisplay/display authority. |
| Index/ETF membership | Partial | Rotation and market claims need official membership and weighting proof, not proxy-only membership. |
| Scanner universe/history | Partial | Universe, local history, quote freshness, turnover, and evidence packets must gate scanner summaries. |
| Fundamentals/filings/events | Partial | Ratios, filings, catalysts, events, and peers are fragmented; missing values remain missing. |
| Options chains/Greeks | Blocked or observation-only | No production-grade claims without provider entitlement, redisplay rights, methodology proof, and chain/Greek completeness. |
| Scenario baselines | Partial | Durable baseline snapshots and target-environment evidence are required before scenario state can be authoritative. |
| Backtest lineage | Partial but research-useful | Adjusted basis, calendar, point-in-time universe, reproducibility, and stored-result authority gate professional claims. |
| Factor research lineage | Diagnostic-only | No PIT universe or long-short factor-return contract yet; do not promote factor helpers as ranking truth. |
| Portfolio price/FX lineage | Partial | Valuation is only as credible as quote, FX, timestamp, source, and account/ledger provenance. |

Source provenance: [`AGENTS.md`](../AGENTS.md), [`README.md`](../README.md).

## Market, Options, Macro, Liquidity, Backtest, Scenario, And Portfolio Domains

Market Overview, Liquidity, and Rotation depend on official risk, macro, ETF/index quote coverage, and membership authority. They may show bounded context, but they must not convert proxy breadth or quote-derived approximations into score-grade institutional claims.

Options Lab is a read-only experiment console. It is not an execution surface, strategy-ranking engine, or order workflow. Fixture/dry-run providers and disabled live stubs must fail closed until entitlement, redisplay rights, chain completeness, Greeks/IV/OI/volume methodology, and display authority are proven.

Scenario Lab compares bounded shocks. Request-supplied, fallback, static, sample, or stale baselines are observation-only and must not imply execution readiness.

Backtest owns deterministic rule evaluation, stored result readback, exports, compare workflows, and research-useful v1 semantics. Do not change fills, costs, metrics, benchmark semantics, parameter/winner meaning, local-only universe execution, or stored-result authority without explicit versioning and focused tests.

Portfolio owns accounts, holdings, cash, transactions, P&L, FX/native currency, cost basis, broker sync/import overlays, ledger mutations, and read projections. UI work must not recalculate accounting authority or imply broker order execution.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`README.md`](../README.md).

## Operator Evidence Boundary

Operator evidence tooling works only with sanitized artifacts and supports manual review; it does not make a release, deployment, or launch decision. Use the repository-owned offline helpers for preflight, workflow smoke, workflow execution, schema reference rendering, archive packaging, gap analysis, bundle comparison, and artifact sanitization. Their script paths are `scripts/operator_evidence_preflight.py`, `scripts/operator_evidence_workflow_smoke.py`, `scripts/operator_evidence_workflow_run.py`, `scripts/operator_evidence_schema_reference.py`, `scripts/operator_evidence_archive_pack.py`, `scripts/operator_evidence_gap_analyzer.py`, `scripts/operator_evidence_bundle_diff.py`, and `scripts/evidence_artifact_sanitize.py`.

Keep raw credentials, cookies, sessions, private URLs, private local paths, provider payloads, database material, request/response bodies, and raw logs out of evidence inputs and reports. The scripts' `--help` output is the command interface authority; their validators define the accepted sanitized artifact shapes.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`README.md`](../README.md).

## Data Coverage Consumer Projection

Consumer coverage communicates only the visible availability state and its short product message. It does not expose internal provider, source, routing, or scoring fields.

| Surface | State | Consumer message |
| --- | --- | --- |
| Market Overview | AVAILABLE | No additional headline. |
| Liquidity | PARTIAL | 部分数据暂不可用。 |
| Scanner | INSUFFICIENT | 当前信号置信度较低，仅供观察。 |
| Portfolio | DELAYED | 已使用最近一次可用数据。 |
| Backtest | UNAVAILABLE | 本模块暂不可用，请稍后重试。 |

Source provenance: [`README.md`](../README.md), [`AGENTS.md`](../AGENTS.md).

## DuckDB Diagnostic Boundary

DuckDB remains an optional diagnostic analytics capability, not a production readiness claim or a replacement for protected runtime semantics. Run only one DuckDB init/ingest/build action at a time during local smoke. Concurrent production operation requires a separately reviewed single-flight ownership design, explicit permissions, bounded inputs, cleanup, and deterministic comparison evidence.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`README.md`](../README.md).

## Provider Provenance Vocabulary

### Provenance vocabulary guard

The following fields are not interchangeable and must not be used as aliases for one another: `diagnosticOnly`, `observationOnly`, `authorityGrant`, `sourceAuthorityAllowed`, `scoreContributionAllowed`, `scoreReliabilityAllowed`, `score_grade_allowed`, `scoreGradeEvidenceAllowed`, `freshness`, `stale`, `partial`, and `fallback`.

A diagnostic or observation field does not grant source authority, score contribution, routing, live-call, or decision authority. Freshness describes evidence condition; stale, partial, and fallback evidence remains visible but cannot be silently promoted.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`README.md`](../README.md).

## Professional Analytics Roadmap And Readiness

The professional roadmap is not a promise that a family is live. It is an ordered readiness map:

1. Official VIX/volatility and macro/rates/Fed-liquidity source authority.
2. Authorized US/CN/HK quote spine with lineage, freshness, and display rights.
3. US index/ETF quote coverage and official membership/weight proofs.
4. Scanner universe, history, turnover, and quote-readiness gates.
5. Watchlist row packet and single-stock research packet completeness.
6. Portfolio price and FX lineage.
7. Options provider entitlement, redisplay rights, and methodology proof.
8. Scenario durable baseline snapshots and target-environment evidence.
9. Backtest dataset lineage, adjusted basis, calendar, PIT universe, and reproducibility gates.
10. Factor research lineage with PIT membership and return contracts.

Each step must expose blocked, partial, missing, unauthorized, stale, or observation-only states rather than hiding them behind positive copy.

Source provenance: [`README.md`](../README.md), [`AGENTS.md`](../AGENTS.md).

## Production Readiness Documentation Authority

Canonical owner: this generated manual, produced by `scripts/build_ai_project_manual.py`. After DOCS-006, the historical `docs/audits/deployment-readiness-checklist.md`, `docs/DEPLOY.md`, and `docs/DEPLOY_EN.md` are deprecated and must not be recreated as compatibility shims. Production-readiness tests should validate this section and the runtime preflight contract, not stale audit paths.

Current public multi-user production posture remains **NO-GO** unless every repository-owned gate below has accepted sanitized target-environment evidence and manual release review. The manual is documentation authority, not launch approval.

| Production concern | Repository-owned authority | Required evidence boundary |
| --- | --- | --- |
| Production environment marker | `APP_ENV=production` must be explicit in the sanitized production config contract. | Use `python3 scripts/production_config_readiness.py --contract <sanitized-production-config-contract.json>`; do not attach raw `.env` values. |
| Authentication enablement | `ADMIN_AUTH_ENABLED=true` is required for public deployment; missing or false is local/dev only. | Auth-disabled public ingress is **NO-GO** and does not change runtime defaults. |
| Fail-closed production posture | Missing required launch config, unsupported MFA scope, public SearXNG discovery, or unsafe CORS posture must fail closed. | Readiness output may include flag names, states, and bounded labels, not secret values or raw service URLs. |
| CORS and CSRF allowlist | `CORS_ALLOW_ALL=false`, explicit `CORS_ORIGINS`, and explicit `CSRF_TRUSTED_ORIGINS` are required for public topology review. | Evidence must prove intended HTTPS origin behavior without echoing raw credential-bearing origins. |
| Secret and config handling | Provider keys, cookies, sessions, DSNs, broker credentials, webhook URLs, raw provider payloads, stack traces, and raw `.env` values stay out of docs, logs, DOM, and release evidence. | Use presence states, redacted summaries, and sanitized validator output only. |
| Docs/OpenAPI production exposure | Root docs/OpenAPI exposure must fail closed when production mode has public ingress but auth is disabled. | T286 behavior is read-only here; documentation must keep auth-disabled production exposure as **NO-GO**. |
| Database and persistence readiness | Repository-owned DB readiness is bounded to local/storage checks, backup/PITR opt-in flags, restore/PITR evidence tooling, and owner-isolation smoke where implemented. | Do not claim Kubernetes, managed database, cloud secret-manager, or external backup infrastructure ownership. |
| Runtime startup verification | `main.py` fails closed with exit code 1 on API import, lifespan, bind, pre-start runner exit, or bounded startup timeout; `scripts/uat_runtime_harness.py` remains the canonical local runtime verifier. | Desktop, Docker, and UAT observe the same process exit. Static preparation `False` is nonfatal, while readiness 503 after bind remains an operational health state. UAT evidence is local runtime proof, not production launch approval. |
| Health and readiness checks | Health/readiness coverage is limited to repository scripts, API/system endpoints, admin diagnostics, and release-summary validators that exist in this tree. | Missing target-environment evidence remains blocked, partial, or **NO-GO** rather than inferred. |
| Rollback and operational validation | Rollback proof requires last-good commit/image, DB restore decision point where applicable, health checks, owner-isolation smoke, and sanitized operator evidence references. | No release, rollback, or live-enforcement approval is implied by docs alone. |

Public deployment env flag matrix:

| Flag / feature | Current behavior | Classification | Required target-env evidence before public launch |
| --- | --- | --- | --- |
| `APP_ENV` | Enables production-mode security semantics only when explicitly set to `production`; missing or non-production values are local/dev only. | **GATED** | Sanitized config contract and target-environment evidence must show explicit production review without raw `.env` values. |
| `VITE_API_URL` | Frontend uses same-origin API by default; explicit value only overrides API base for split-domain/static deployments. | **GATED** | Browser/ingress evidence must show the built frontend reaches the intended HTTPS API origin, CORS/CSRF origins match, and backend `:8000` is not directly public. |
| `PUBLIC_API_ABUSE_LIMIT_*` | Process-local abuse limiter knobs are clamped and sanitized in diagnostics. | **SAFE** | Include sanitized limiter snapshot evidence and keep it labeled process-local; it is not quota, billing, auth, or distributed rate-limit enforcement. |
| `CRYPTO_REALTIME_ENABLED` | Realtime crypto background behavior must be explicitly reviewed for outbound access and degraded behavior. | **AMBIGUOUS** | Target-environment evidence must show whether outbound Binance/WebSocket access is allowed, how failures degrade, and whether realtime is intentionally disabled. |
| `SEARXNG_PUBLIC_INSTANCES_ENABLED` | Public-instance discovery is unsuitable for public launch unless separately accepted or disabled in favor of vetted self-hosted endpoints. | **NO-GO** | Public launch must use vetted self-hosted SearXNG endpoints, explicitly disable public discovery, or attach accepted operator risk evidence. |

Classification rule: **SAFE** still requires target-environment evidence; **GATED** requires explicit config plus accepted evidence; **AMBIGUOUS** requires an operator decision; **NO-GO** applies whenever required target-environment evidence is missing, raw secrets would be needed to prove the claim, or a flag is used to imply provider, quota, auth/RBAC, database, broker, or notification live-enforcement approval.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`README.md`](../README.md), [`docs/DOCS_INDEX.md`](DOCS_INDEX.md).

## Protected Domains And Safety Rules

Stop before editing these domains unless the prompt explicitly authorizes the scope and validation path:

- provider adapters, provider order, fallback, freshness, cache semantics, live-call behavior, credentials, and source authority;
- scanner scoring, selection, thresholds, ranking, sorting, score contribution, and live/fallback labels;
- backtest fills, costs, metrics, benchmarks, parameter/winner semantics, universe execution, and stored readback;
- portfolio accounting, cash, holdings, transactions, P&L, FX/native currency, cost basis, broker sync/import, and ledger semantics;
- auth/RBAC/security, sessions, cookies, CSRF/CORS, password/token handling, MFA, and admin protection;
- DB migrations, root config, package/lock files, CI, dependency updates, env templates, and external network behavior;
- broker/order execution, trading CTAs, target prices, position sizing, and personalized financial advice.

Do not introduce fake data, fallback payloads, placeholder readiness, hidden compatibility layers, raw provider leakage, or one-off Markdown reports as a way to satisfy a task.

Source provenance: [`AGENTS.md`](../AGENTS.md).

## No-Advice Policy

WolfyStock may provide research context, evidence, readiness state, scenario comparison, risk disclosure, and operational diagnostics. It must not provide direct instructions to buy, sell, hold, short, add, reduce, execute, route, or size positions for a user.

Avoid user-facing copy that implies investment recommendation, guaranteed outcome, target price, execution readiness, risk-free action, or personalized suitability. Safer patterns are observation-only labels, evidence boundaries, uncertainty, data-source/freshness/lineage, and explicit no-advice wording. The Chinese no-advice anchor `数据不足，暂不形成结论。` is intentionally retained where product copy needs a compact blocked-state sentence.

No-advice review should classify grep hits. Tests, negative assertions, source-code identifiers, and policy docs may contain forbidden words as guardrails; visible UI and generated reports need stricter review.

Source provenance: [`AGENTS.md`](../AGENTS.md).

## Validation Matrix

Use the smallest validation set that proves the touched behavior:

- Docs/manual/generator: `python -m py_compile scripts/build_ai_project_manual.py`, `python scripts/build_ai_project_manual.py`, `python scripts/build_ai_project_manual.py --check`, `python -m pytest -q tests/scripts/test_build_ai_project_manual.py`, `python scripts/check_ai_assets.py`, `git diff --check`, `bash scripts/release_secret_scan.sh --base-ref origin/main`, inventory counts, and link sanity.
- Backend Python: `./scripts/ci_gate.sh` when feasible; otherwise `python -m py_compile <changed_python_files>` plus closest deterministic pytest. Standard pytest runs deny non-loopback sockets, and the authoritative gate verifies the explicit domain manifest.
- Shadow test topology: `python scripts/domain_test_topology.py verify-all`; run the single-startup backend aggregate with `python scripts/domain_test_topology.py run-backend --output-dir output/domain-test-topology --retry-failures 1`; list ownership with `list-backend --domain <domain>` and audited network tests with `list-network`. These commands add parity evidence and do not replace the existing gates.
- Audited external-network tests: the standard offline/LAND tier always skips them. An explicit run requires marker fields `owner`, `reason`, and `audit`, plus `python -m pytest -m network --allow-test-network --network-audit <audit-id>`.
- API/schema/auth/provider/protected contracts: backend focused tests, compatibility review, redaction/leakage checks, and wider gates when shared contracts are touched.
- Web frontend: after `./wolfy bootstrap --ensure`, run Vitest/lint through managed npm and run non-incremental typecheck/production build through `./wolfy exec --profile test -- python scripts/web_build_artifact.py <typecheck|build>` so validation never writes the immutable dependency snapshot. Use browser/screenshot smoke when layout or visible UX changes.
- Local UAT runtime harness: run `./wolfy exec --profile test -- python scripts/uat_runtime_harness.py --expected-sha "$(git rev-parse HEAD)"`, then use the same managed command with `--preflight --expected-sha "$(git rev-parse HEAD)" --evidence-path <run-evidence> --json` for read-only WorkBuddy qualification and `--stop-from-evidence --evidence-path <run-evidence> --json` for task-owned cleanup.

> Shell note: commands using `./scripts/*.sh` and `$(git rev-parse HEAD)` are
> POSIX-shell (bash/sh) syntax. On Windows run them from Git Bash, WSL, or any
> shell providing a POSIX `sh` (e.g. `bash scripts/ci_gate.sh`). PowerShell uses
> the same `$(...)` subexpression syntax, so the UAT `--expected-sha "$(git rev-parse HEAD)"`
> invocations also work unchanged in PowerShell.
- Desktop: build web first, then desktop build where platform allows.
- Workflow/scripts/Docker: run the closest local deterministic script or syntax check and report unexecuted remote/infra gaps.

Never claim tests passed unless the command actually ran in this workspace and succeeded.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`README.md`](../README.md).

## Codex Workflow And Landing Changes

Start with read-only discovery. Confirm `pwd`, branch, and `git status`; read the current prompt, `AGENTS.md`, `README.md`, this manual, and the smallest code/docs context required. Respect task mode and workspace. In a `WORKTREE-WORKER` task, stay inside the specified worktree and branch.

Do not push unless explicitly authorized. Do not commit unless the task asks for a commit or the current instruction grants auto-commit. Do not rebase, merge, delete branches/worktrees, or rewrite history unless the task explicitly requires it. If a task requires fetch/rebase before final report, run `git fetch origin`, rebase onto `origin/main`, rerun focused validation, and only then commit/report.

Before final delivery: inspect `git diff`, run `git diff --check`, run required tests/checks, confirm no unexpected files or secrets, and report exact commands and results. Final reports should include status, changed files, validation, risk, final base commit, commit hash when created, final `git status`, and rollback command.

### Completion Evidence By Change Risk

本节只规定完成报告必须保留的证据，不改变风险选择、gate 选择、gate 执行、
topology、release policy 或其他验收规则。任务和仓库要求运行的验证仍必须运行；
报告简洁只允许去掉重复叙述，不允许省略必需证据。R0 到 R5 的要求逐级累积，
失败、跳过、不可用、未执行、静态推断或未评估均不得写成通过。

- **R0**：报告结果、相对 accepted base 的精确 changed files、focused/static
  validation 的完整命令与结果、commit hash/subject（未创建时明确说明）、可执行
  rollback、最终 clean/dirty status，以及 upstream 与 push state。
- **R1**：保留全部 R0 字段；另外说明受影响的 test/mechanical owner、节点或生成
  产物范围（如适用），不得用“小改动”省略 focused validation 或未验证项。
- **R2**：保留全部 R0/R1 字段；另外报告 protected owner、adjacent contracts、
  topology delta（未变化也要给出验证）、targeted integration evidence，以及
  residual risk。
- **R3**：保留全部 R2 字段；对 public contract 或 cross-owner integration 给出
  producer/consumer 和 combined-tree 身份、所有受影响 owner 的 targeted integration
  结果、精确 topology delta 与仍未验证的集成风险。
- **R4**：保留全部 R3 字段；另外报告完整 immutable evidence identity，包括
  accepted base/tree/commit、environment、dependency/config、command/selection、artifact
  hash 和适用的 candidate identity；列出全部 required protected gates，并分别保留
  first attempt 与每次 retry 的结果。触发 browser/UAT、release 或 remote 验证时，
  必须给出真实执行证据和精确身份；未触发、未授权或未执行时明确记录，不能推断通过。
- **R5**：保留全部 R4 字段；绑定 frozen candidate 的 source/tree/artifact/digest、
  complete protected gates、browser/UAT/release 与 target-environment 证据、first
  attempt/retry 历史、promotion/rollback identity，以及精确 remote ref/digest 验证和
  push state。任何 identity mismatch 都使相关证据失效，必须如实报告并重新资格化。

无论报告层级，任务触发以下边界时都必须保留对应 evidence 与 rollback boundary：
auth/RBAC/owner isolation、persistence/transaction、provider isolation/source authority、
truth semantics、secrets/private paths、no-live、release identity、migration、browser、
target environment。特别保留 `missing != zero`、`not evaluated != passed`、
`skipped != passed`、`corrupt state != empty state`、`injected transport != live transport`
和 `task accepted != analysis completed`；不得用概括性“已验证”替代边界、命令、
结果、artifact identity 或限制条件。

若任务创建或依赖 temporary audit/evidence artifact，完成报告必须记录 artifact
classification、owner、仍存依赖、最早 retirement 条件和删除动作。只有在 durable
policy 已迁入 canonical authority、所有引用已移除且资格化前置条件满足后才能删除；
不得移动到 archive/historical/completed-report 目录，也不得保留 compatibility copy。

Source provenance: [`AGENTS.md`](../AGENTS.md), [`docs/DOCS_INDEX.md`](DOCS_INDEX.md).

## Current Canonical File Map

After DOCS-006, the repository intentionally avoids a large Markdown corpus. The canonical reading path should be:

1. `README.md` for the human product entrypoint and run commands.
2. `AGENTS.md` for current AI-agent rules and hard safety boundaries.
3. `docs/AI_PROJECT_MANUAL.md` for the comprehensive project handbook.

Retained Markdown categories:

| File or lane | Why retained |
| --- | --- |
| `README.md` | Short human entrypoint and run-command starter. |
| `AGENTS.md` | Repository AI-collaboration source of truth and protected-domain hard rules. |
| `CLAUDE.md` | Required symlink to `AGENTS.md` for Claude compatibility; retained because `scripts/check_ai_assets.py` enforces it. |
| `docs/AI_PROJECT_MANUAL.md` | Generated comprehensive handbook for AI workers and maintainers. |
| `docs/DOCS_INDEX.md` | Tiny pointer to canonical docs; no archive lane or broad index. |
| `docs/CHANGELOG.md` | Short compatibility file retained because release tooling still reads this path. |
| `.github/*.md` | GitHub Copilot/instruction/issue/PR workflow assets. |
| `.claude/skills/*.md` | Required repository skill assets checked by AI governance tooling. |

`docs/AI_PROJECT_MANUAL_SOURCES.json` is not Markdown; it records deterministic source hashes, generator metadata, discovery counts, and section provenance. `docs/DOCS_INDEX.md` should stay tiny and only point to canonical files. Archive and product-recovery Markdown lanes are no longer retained as active project knowledge.

Source provenance: [`README.md`](../README.md), [`AGENTS.md`](../AGENTS.md), [`docs/DOCS_INDEX.md`](DOCS_INDEX.md).

## Compressed Project History

WolfyStock began as a scheduled stock-analysis and notification project, then accumulated web, desktop, provider, backtest, portfolio, admin, and AI-assisted research surfaces. Later work shifted the architecture toward bounded contexts, provider/source readiness, route-level research workbenches, and protected semantics around scanner, portfolio, backtest, auth/RBAC, broker/accounting, and provider runtime.

Product-recovery and DATA-series work established the durable lesson that visible research value depends on real source authority: official risk/macro, authorized quote spine, scanner/watchlist packets, portfolio price/FX lineage, options entitlement, scenario baselines, and backtest dataset lineage must be explicit. Old audits, acceptance reports, launch checklists, design notes, and progress logs were useful for their moment, but their durable content now lives in this manual.

DOCS-006 hard-collapsed the Markdown corpus: keep a short README, a short AGENTS rule entrypoint, this generated manual, the manifest, and required governance/workflow mirrors. Do not recreate old index/archive lanes for routine tasks.

Source provenance: [`README.md`](../README.md), [`docs/DOCS_INDEX.md`](DOCS_INDEX.md).

## AI Onboarding Checklist

For a new task:

1. Confirm CWD, branch, and `git status --short --branch`.
2. Read the user's task contract and protected/forbidden scope.
3. Read `AGENTS.md`, `README.md`, and this manual.
4. Run read-only discovery with `rg`, `rg --files`, source files, tests, and scripts. Do not edit during discovery.
5. Classify the task as docs, backend, frontend, API/schema, provider, auth, portfolio, backtest, workflow, or review.
6. If the task touches a protected domain, stop unless explicit scope and validation are present.
7. Make the smallest relevant change; avoid new docs, indexes, archive lanes, or parallel implementations.
8. Run the focused validation that proves the touched area.
9. Inspect diff/status, secret scan when required, and link/Markdown sanity for docs work.
10. If the prompt requires rebase, fetch/rebase and rerun focused validation before final report or commit.

For docs tasks, the default answer is to update this manual/generator and delete stale Markdown after durable knowledge is absorbed.

Source provenance: [`AGENTS.md`](../AGENTS.md), [`README.md`](../README.md), [`docs/DOCS_INDEX.md`](DOCS_INDEX.md).

## Source Map

This map is generated from the hard-collapse source set. The manual contains absorbed durable knowledge from retired docs, but only these canonical files remain source-tracked.

| Manual section | Tracked sources | Update trigger | Validation |
| --- | --- | --- | --- |
| Project Identity And Product Purpose | `README.md`<br>`AGENTS.md` | Product positioning, target audience, or no-advice posture changes. | Docs-only validation plus no-advice grep when user-visible wording changes. |
| Architecture Overview | `AGENTS.md`<br>`README.md` | Runtime entrypoints, module ownership, public contracts, or high-risk boundary rules change. | Run the focused gate for the touched module plus `python scripts/check_ai_assets.py` for AI-governance edits. |
| Dependency Environment Authority | `README.md`<br>`AGENTS.md` | Python requirement intent, lock schema/family, resolver, supported target matrix, managed browser/tool identity, UAT artifact binding, or bootstrap install authority changes. | Python lock check, focused wolfy lock/component/identity/manager/CLI/browser tests, authenticated UAT, release-real-runtime Playwright, offline ensure, manual freshness, and AI asset checks. |
| Frontend Surfaces | `README.md`<br>`AGENTS.md` | Route map, page ownership, consumer copy, route IA, or visual system changes. | Frontend tests/lint/build plus browser or screenshot evidence when UI source changes. |
| Backend API And Service Structure | `AGENTS.md`<br>`README.md` | API families, service boundaries, schema contracts, report payloads, or validation routing changes. | Backend gate or closest pytest/py_compile evidence; wider gates for protected/shared contracts. |
| Data Providers And Data Reality Boundaries | `AGENTS.md`<br>`README.md` | Provider routing, source authority, data readiness, freshness, lineage, or professional-roadmap changes. | Provider/cache/freshness tests, no-live-call proof when relevant, and raw-provider leakage scans. |
| Market, Options, Macro, Liquidity, Backtest, Scenario, And Portfolio Domains | `AGENTS.md`<br>`README.md` | Any domain readiness, public copy, protected math/accounting, options authority, or macro/liquidity source change. | Domain-focused tests plus no-advice and leakage checks; never use unrelated green tests as proof. |
| Operator Evidence Boundary | `AGENTS.md`<br>`README.md` | Operator evidence script inventory, sanitization boundary, or review-only semantics change. | Focused operator evidence command-doc tests, safe placeholder scan, generator freshness, and AI asset check. |
| Data Coverage Consumer Projection | `README.md`<br>`AGENTS.md` | Consumer data-coverage states or visible availability copy change. | Data-coverage projection tests, consumer leakage checks, generator freshness, and no-advice wording checks. |
| DuckDB Diagnostic Boundary | `AGENTS.md`<br>`README.md` | DuckDB diagnostic scope, concurrency ownership, permissions, or runtime integration changes. | Focused DuckDB service tests, generated-artifact scan, generator freshness, and AI asset check. |
| Provider Provenance Vocabulary | `AGENTS.md`<br>`README.md` | Provider provenance vocabulary, authority semantics, or confidence caps change. | Provider capability/source-confidence tests, generator freshness, and no-advice or leakage checks. |
| Professional Analytics Roadmap And Readiness | `README.md`<br>`AGENTS.md` | Professional data roadmap, readiness labels, or evidence-harness expectations change. | Docs/generator validation for handbook changes; domain validation for implementation changes. |
| Production Readiness Documentation Authority | `AGENTS.md`<br>`README.md`<br>`docs/DOCS_INDEX.md` | Production readiness docs authority, public deployment env flag classifications, or launch evidence policy changes. | Production config readiness tests, manual generator freshness, AI asset check, and link/stale-path scans. |
| Protected Domains And Safety Rules | `AGENTS.md` | Any protected boundary or safety policy changes. | Focused tests for the exact protected semantic plus diff/status/secret/no-advice checks before reporting completion. |
| No-Advice Policy | `AGENTS.md` | User-facing research copy, generated reports, product policy, options/backtest/portfolio wording, or no-advice guards change. | Focused grep/classification plus relevant page/report tests. |
| Validation Matrix | `AGENTS.md`<br>`README.md` | Validation commands, CI gates, protected test expectations, or docs/generator workflow changes. | Run the validation relevant to this manual/generator when edited. |
| Codex Workflow And Landing Changes | `AGENTS.md`<br>`docs/DOCS_INDEX.md` | Task modes, git policy, final-report requirements, or AI workflow rules change. | Docs/generator check and `python scripts/check_ai_assets.py` when governance assets change. |
| Current Canonical File Map | `README.md`<br>`AGENTS.md`<br>`docs/DOCS_INDEX.md` | Canonical docs set, retained Markdown policy, or AI asset governance changes. | Inventory before/after counts, link sanity, generator `--check`, and `python scripts/check_ai_assets.py`. |
| Compressed Project History | `README.md`<br>`docs/DOCS_INDEX.md` | Major project direction, docs-retention policy, or historical context changes. | Docs-only validation and inventory count check. |
| AI Onboarding Checklist | `AGENTS.md`<br>`README.md`<br>`docs/DOCS_INDEX.md` | Onboarding order, docs model, or task execution policy changes. | Generator check plus AI asset check. |

## JSON Manifest

The machine-readable manifest is generated at `docs/AI_PROJECT_MANUAL_SOURCES.json`. It records source paths, source hashes, generator metadata, section provenance, and Markdown discovery statistics.

Current discovery summary:

- Markdown discovered after pruned directory rules, excluding this generated manual: 26
- Candidate Markdown after hard-collapse policy: 3
- Curated sources included in this manual: 3

Exclusion policy:

- Keep the manual source set intentionally tiny: AGENTS.md, README.md, and docs/DOCS_INDEX.md.
- Do not rediscover archive lanes, task reports, stale audits, old plans, or one-off acceptance snapshots as manual sources.
- Keep .github and .claude Markdown files as governance/workflow mirrors when required by scripts/check_ai_assets.py, but do not treat them as handbook sources.
- Keep issue and PR templates as GitHub workflow assets, not project handbook chapters.
- Exclude generated outputs, local evidence, fixture READMEs, language duplicates, broad legacy guides, and dependency/build/cache folders.
- When durable knowledge is needed, merge it into this deterministic generator/manual instead of adding another index or archive file.
