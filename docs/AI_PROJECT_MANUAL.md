# WolfyStock AI Project Manual

> GENERATED FILE. DO NOT EDIT DIRECTLY.
>
> Edit `scripts/build_ai_project_manual.py` or its tiny canonical sources, then run:
>
> ```bash
> python scripts/build_ai_project_manual.py
> python scripts/build_ai_project_manual.py --check
> ```

Status: generated cross-domain project handbook
Audience: Codex workers, reviewers, maintainers, and humans assigning AI work
Authority: operational handbook and source map; `AGENTS.md` remains the repository AI hard-rule source
Do not use as: launch approval, protected-domain authorization, stale audit authority, trading advice, or a replacement for current code/test inspection

---

## Task reading matrix

Read only the sections required by the task unless the work is cross-domain.

| Task family | Required sections | Additional canonical source |
| --- | --- | --- |
| Bounded frontend repair | Project Identity, Frontend Surfaces, Protected Domains, Validation Matrix, Codex Workflow | relevant `DESIGN.md` section |
| Frontend page/product migration | Project Identity, Frontend Surfaces, Data Reality, Protected Domains, Validation Matrix, Codex Workflow | full relevant page contract in `DESIGN.md` and visual reference |
| Backend service/API | Architecture, Backend API, relevant domain, Protected Domains, Validation Matrix | current schemas, service tests, API tests |
| Provider/data-truth work | Data Providers, relevant domain, Readiness Roadmap, Protected Domains, Validation Matrix | provider/runtime source and canonical gate |
| Historical market-data work | Data Providers, relevant domain, Protected Domains, Validation Matrix | `docs/contracts/historical_market_data_foundation.md` and relevant runbook |
| Dependency/runtime/CI | Architecture, Protected Domains, Validation Matrix, Codex Workflow | package/lockfile or canonical gate scripts |
| Auth/Admin/Security | Architecture, Frontend Surfaces, Production Readiness, Protected Domains, Validation Matrix | current auth/RBAC/security tests |
| Portfolio/Backtest | relevant domain, Data Reality, Protected Domains, Validation Matrix | accounting/backtest contracts and focused tests |
| Deployment/readiness | Production Readiness, Protected Domains, Validation Matrix, Canonical File Map | target-environment sanitized evidence |
| Documentation governance | Canonical File Map, Source Map, Codex Workflow | `AGENTS.md`, `DOCS_INDEX.md`, generator and asset checks |

Read the full manual for cross-domain architecture, production-readiness, milestone integration, or documentation-generation changes.

---

## Project identity and product purpose

WolfyStock is a professional financial research workbench for market context, candidate discovery, stock research, watchlists, deterministic validation, portfolio exposure, provider diagnostics, admin observability, and AI-assisted research across US, CN, and HK markets.

The durable product hierarchy is:

```text
结论
→ 证据
→ 数据质量
→ 风险边界
→ 下一步研究动作
```

Core user journey:

```text
看市场
→ 找候选
→ 看个股
→ 加入持续观察
→ 用扫描 / 回测 / 情景分析做验证
→ 检视真实持仓暴露
```

WolfyStock is not a broker, order-entry surface, retail trading game, buy/sell signal engine, investment-advice application, or unconstrained LLM wrapper.

Every user-visible conclusion must preserve evidence, source authority, lineage, freshness, readiness, and no-advice boundaries.

Source: `README.md`, `AGENTS.md`, `DESIGN.md`.

---

## Architecture overview

Primary entrypoints and boundaries:

| Area | Ownership |
| --- | --- |
| Analysis and local automation | `main.py` |
| FastAPI runtime | `server.py`, `api/app.py`, `api/v1/router.py` |
| Business services | `src/services/` |
| Persistence | `src/repositories/` |
| Schemas and DTOs | `src/schemas/` |
| Provider adapters/runtime | `data_provider/` and owned provider services |
| Notifications | `bot/` |
| Web terminal | `apps/dsa-web/` |
| Desktop wrapper | `apps/dsa-desktop/` |
| Scripts and CI | `scripts/`, `.github/workflows/`, `docker/` |

Keep bounded contexts intact. Consumers should use public facades, API clients, schemas, DTOs, validators, and documented commands.

Do not reach into private engines, repositories, provider clients, cache keys, ledger internals, auth internals, or mutation code merely to simplify a local task.

Shared contracts, schema, dependency files, root config, CI, auth, provider runtime, portfolio accounting, database migration, and frontend route-entry behavior are high-risk and require explicit ownership and validation.

---

## Frontend surfaces

| Surface | Product purpose | Primary authority | Readiness boundary |
| --- | --- | --- | --- |
| Home | Bounded first read and research starting point | existing home read paths and `HomePage` family | Guest/auth, quote, market, and chart states remain honest. |
| Market Overview | Regime, breadth, official risk, macro first read | market-overview endpoint/service and consumer page | Partial until official risk, quote authority, and target-environment evidence are proven. |
| Scanner | Candidate discovery and watchlist handoff | scanner endpoint/service and `UserScannerPage` | Universe, history, quote, freshness, turnover, and packet readiness fail closed. |
| Research Radar | Research-priority queue and explanation | existing research/radar owners | Candidate is observation priority, not recommendation. |
| Watchlist | Recurring research-task ledger | watchlist endpoint/services and page | Row packets may be partial; owner and symbol identity remain authoritative. |
| Stock Research / Structure | Symbol packet, chart, evidence, structure observation | stock endpoints/services and stock pages | No invented quote, history, fundamentals, event, filing, peer, or catalyst evidence. |
| Liquidity / Rotation | Market pressure, flow, and rotation context | owned market/liquidity services and pages | Proxy/delayed rows remain capped unless official authority exists. |
| Options Lab | Read-only options research console | options endpoint/service and page | Observation-only until entitlement, redisplay, chain, Greeks, IV, OI, volume, and methodology are proven. |
| Scenario Lab | Bounded shock comparison | scenario engine and page | Request-supplied, fallback, sample, static, proxy, or stale baseline is observation-only. |
| Backtest / Compare | Deterministic rule validation and stored readback | backtest endpoint/engine/service and pages | No optimizer, winner, allocation, or fake performance semantics. |
| Portfolio | Accounts, holdings, cash, FX, ledger, risk, attribution | portfolio endpoint/service and page | Accounting authority is protected; quote/FX lineage and owner isolation remain explicit. |
| Settings | User-owned configuration | auth/settings API and pages | Saved secrets do not enter DOM; unchanged secret fields are omitted. |
| Admin/Ops | Role-gated diagnostics and controls | admin endpoints/services and pages | Capability gates fail closed; raw secrets/provider payloads stay redacted. |
| Report Preview | Bounded research report and export | report/render owners and preview page | Observation time, generated time, provenance, unavailable, and no-advice remain distinct. |

Frontend posture: dense but legible, route-first, evidence-first, calm, and consumer-safe. Prefer tables, rows, rails, drawers, disclosures, and dominant analytical surfaces over generic card sprawl.

See `DESIGN.md` for information architecture, visual system, page contracts, responsive behavior, and browser-validation expectations.

---

## Backend API and service structure

- API routers remain thin.
- Services own domain semantics.
- Repositories own persistence boundaries.
- Schemas/DTOs remain explicit.
- Provider adapters remain behind provider/runtime boundaries.
- Public projections redact provider, security, credential, and admin internals.

FastAPI endpoints must not embed scanner ranking math, portfolio accounting, provider fallback order, auth policy, or report-rendering internals.

Prefer additive response changes. Deleted or renamed fields require client compatibility review and versioning where appropriate.

For Python changes, prefer the canonical gate. At minimum run syntax/compile checks and closest deterministic tests; protected semantic changes require focused and canonical evidence.

---

## Data providers and data-reality boundaries

Provider runtime owns:

- provider order and fallback;
- retry, circuit, timeout, and quota posture;
- cache and freshness;
- source authority and display rights;
- optional enrichment budgets;
- sanitized diagnostics;
- local-first and fail-closed behavior.

Do not reorder providers, deepen live fallback, add uncontrolled fanout, activate providers from passive UI, or expose raw provider payloads without explicit scope.

```text
fallback != live
cached != fresh
proxy != official
request supplied != authoritative
fixture != production
synthetic != observed
missing != zero
rejected != neutral
```

| Data family | Current posture | Operational boundary |
| --- | --- | --- |
| Official risk and volatility | Partial | VIX/rates/Fed-liquidity/credit rows require source authority before score-grade claims. |
| Quote spine | Partial | US/CN/HK quote snapshots require lineage, freshness, redisplay/display authority. |
| Index/ETF membership | Partial | Rotation claims require official membership/weight proof. |
| Scanner universe/history | Partial | Universe, local history, quote, turnover, freshness, and packet readiness gate candidate claims. |
| Fundamentals/filings/events | Partial | Missing ratios, filings, catalysts, events, and peers remain missing. |
| Options | Blocked or observation-only | No production-grade claim without entitlement, redisplay, chain, Greek/IV/OI/volume and methodology proof. |
| Scenario baseline | Partial | Durable baseline snapshots and target-environment evidence gate authority. |
| Backtest lineage | Research-useful but partial | Adjustment, calendar, PIT universe, reproducibility, and stored-result authority gate professional claims. |
| Factor research | Diagnostic-only | No PIT membership/long-short return contract; helpers are not ranking truth. |
| Portfolio quote/FX | Partial | Valuation credibility depends on source, timestamp, quote, FX, account, and ledger provenance. |
| Historical market data | Foundation available, integration incremental | Canonical bars, quality, persistence, coverage, freshness, and provenance must be preserved per the historical contract. |

---

## Domain boundaries

### Market, liquidity, and rotation

May present bounded context but must not promote proxy breadth, partial quotes, or delayed rows into official score-grade claims.

### Scanner

Candidate is a research-priority signal, not advice. Universe, quote, history, freshness, turnover, and packet readiness remain backend-owned and fail closed.

### Watchlist and Stock Research

Watchlist is a research ledger. Stock pages explain identity, evidence, limitations, and next checks. Missing data remains missing and consumer withholding is respected.

### Options

Read-only research. No order flow, strategy ranking, or execution posture. Fixture, dry-run, disabled, or unauthorized provider state remains observation-only.

### Scenario

Compares bounded shocks. Static, request-supplied, sample, fallback, proxy, or stale baseline cannot support authoritative allocation or action claims.

### Backtest

Owns deterministic rule execution, stored readback, export, and comparison. Do not change fills, costs, metrics, benchmark, calendar, universe, result ownership, or winner semantics without explicit scope and tests.

### Portfolio

Owns accounts, cash, holdings, transactions, P&L, FX/native currency, cost basis, broker sync/import overlays, owner isolation, ledger mutation, and read projections. UI does not recalculate accounting authority or imply broker execution.

### Historical market data

Canonical foundation:

```text
provider observation
→ normalization
→ canonical bar
→ quality outcome
→ repository
→ foundation reads
→ product seam
```

See `docs/contracts/historical_market_data_foundation.md`.

---

## Professional analytics roadmap and readiness

The roadmap is an ordered readiness map, not a promise that each family is live:

1. official volatility and macro/rates/Fed-liquidity authority;
2. authorized US/CN/HK quote spine;
3. index/ETF quotes and official membership/weights;
4. Scanner universe/history/turnover/quote readiness;
5. Watchlist and single-stock evidence-packet completeness;
6. Portfolio quote and FX lineage;
7. Options entitlement, redisplay, and methodology;
8. durable Scenario baseline snapshots;
9. Backtest dataset lineage, adjustment, calendar, PIT universe, reproducibility;
10. factor research PIT membership and return contracts.

Every step must expose blocked, partial, missing, unauthorized, stale, delayed, proxy, degraded, or observation-only states rather than hiding them behind success copy.

---

## Production-readiness documentation authority

Canonical documentation owner: this generated manual and its generator.

Historical broad deployment/checklist Markdown paths must not be recreated as compatibility shims unless the current repository explicitly restores them as canonical sources.

Public multi-user production posture remains **NO-GO** until every required repository-owned gate has accepted sanitized target-environment evidence and manual release review.

| Concern | Repository-owned authority | Evidence boundary |
| --- | --- | --- |
| Production marker | explicit production config contract | Sanitized state; no raw `.env`. |
| Authentication | production requires enabled auth | Auth-disabled public ingress is NO-GO. |
| Fail-closed posture | startup/readiness validation | Missing launch config, unsafe CORS/CSRF, or unsupported scope fails closed. |
| CORS/CSRF | explicit origins and production posture | Prove intended HTTPS behavior without exposing secrets. |
| Secret/config handling | redaction and config validators | Presence/state only; no token, cookie, DSN, webhook, raw provider payload, or stack trace. |
| Docs/OpenAPI exposure | production runtime contract | Public exposure with disabled auth is NO-GO. |
| Persistence | repository-owned DB readiness and restore evidence | Do not claim external infrastructure ownership. |
| Runtime verification | canonical local runtime/UAT harness | Local evidence is not launch approval. |
| Health/readiness | existing endpoints and validators | Missing target evidence remains blocked/partial. |
| Rollback | last-good artifact, DB decision, health and isolation smoke | Documentation alone does not approve release or rollback. |

---

## Protected domains and safety rules

`AGENTS.md` is authoritative. High-level protected domains include:

- provider order, fallback, cache, activation, authority, quota, credentials, external network;
- Scanner universe, scoring, ranking, threshold, candidate generation;
- Backtest fills, costs, metrics, benchmark, universe, execution, stored-result semantics;
- Portfolio accounting, owner isolation, FX, cost basis, broker sync/import, ledger;
- auth/RBAC/security/session/cookie/CSRF/CORS/MFA/admin;
- schema, migrations, root config, dependencies, lockfiles, CI, release;
- broker/order execution and advice language.

Passive page load must not activate providers, execute Scanner/Backtest, mutate Portfolio/Watchlist/Auth/account state, or deliver external notifications.

Never use destructive Git or cleanup commands as automated recovery.

---

## No-advice policy

Consumer language must remain analytical and research-oriented.

Do not generate or imply:

```text
buy / sell / hold
target price
stop loss
add / reduce position
allocation or cash-weight advice
order execution
```

Permitted bounded language includes current observation, evidence strength, risk sensitivity, invalidation conditions, freshness, limitations, and next research checks.

No-advice is a semantic contract, not merely a disclaimer.

---

## Validation matrix

Use Validation Economy:

```text
focused reproduction
→ owned tests
→ impacted shared validation
→ typecheck / design / diff
→ broad validation when a shared boundary changed
```

| Change | Minimum evidence | Broad gate trigger |
| --- | --- | --- |
| Python bounded repair | closest tests, compile/syntax, diff | shared service/schema/runtime behavior |
| Provider/truth | focused provider/runtime tests, redaction, fail-closed | canonical backend gate |
| Frontend page | owned tests, direct route, refresh/history, target viewport, console/pageerror, read-only boundary | shared primitive/state mapper or milestone |
| App/router/auth | focused auth/route tests, browser journey, typecheck/build | full frontend suite |
| Dependency/lockfile | audit before/after, reachability, npm ci, full tests, lint/typecheck/design/build | always |
| Runtime/smoke harness | success/failure, args, artifacts, cleanup, port/process ownership, platform compatibility | full relevant runtime gate |
| Backtest/Portfolio | deterministic focused contract tests | canonical domain/backend gate when semantics change |
| Docs generator | generated output, `--check`, AI asset check, links/diff | documentation governance task |

Baseline-red failures must be classified as product regression, test debt/race, environment, orchestration, or unrelated baseline. Do not repair unrelated failures inside a bounded task.

---

## Codex workflow and landing changes

Default task lifecycle:

```text
inspect
→ classify
→ execute
→ validate
→ report
→ centralized integration gate when authorized
```

Task workers:

- use the assigned worktree and ownership;
- do not create nested worktrees;
- do not use subagents unless explicitly authorized;
- do not push unless explicitly authorized;
- normally produce one local task commit;
- report HEAD, origin/main, ahead/behind, tree, changed files, validation, blocker, and verdict.

Central landing gate should:

1. fetch and verify remote main;
2. rebase the task;
3. require exactly the authorized commit shape;
4. verify subject and changed-file ownership;
5. run focused and required broad validation;
6. run lint/typecheck/design/build/diff as applicable;
7. merge without destructive rollback;
8. push only when authorized;
9. verify local main equals origin/main.

A failed gate stops the landing. Do not hard-land around required red validation.

Milestone browser/UAT should run after substantial independent workstreams converge, not after every tiny task and not only at the very end.

---

## Current canonical file map

| File | Role |
| --- | --- |
| `README.md` | short human entrypoint and run commands |
| `AGENTS.md` | AI hard rules, truth invariants, protected domains, workflow and delivery gates |
| `DESIGN.md` | consumer frontend product/design/page contract |
| `docs/DOCS_INDEX.md` | tiny canonical document router |
| `docs/AI_PROJECT_MANUAL.md` | generated cross-domain handbook |
| `docs/AI_PROJECT_MANUAL_SOURCES.json` | machine-readable source manifest |
| `docs/contracts/historical_market_data_foundation.md` | historical market-data living contract |
| `docs/runbooks/historical_ohlcv_seed_runbook.md` | local OHLCV seed operator procedure |
| `docs/design/reference/wolfystock-impeccable-polish-final.html` | visual and interaction reference only |
| `scripts/build_ai_project_manual.py` | manual generator authority |
| `scripts/check_ai_assets.py` | AI governance asset validation |

Do not recreate broad archive, audits index, per-task report folders, copied terminal logs, or deprecated documentation shims.

---

## AI onboarding checklist

1. Read the current task and `AGENTS.md`.
2. Confirm repository, worktree, branch, `origin/main`, and `git status`.
3. Read `README.md` and task-routed manual sections.
4. For frontend work, read relevant `DESIGN.md` sections and inspect real route/component ownership.
5. Identify protected domains, write ownership, read-only scope, and validation.
6. Inspect the smallest relevant source and tests.
7. Preserve truth, freshness, provenance, fail-closed, mutation, and no-advice boundaries.
8. Execute and validate in one continuous run.
9. Inspect exact diff/status and secret/private-path exposure.
10. Report evidence, changed files, risks, Git state, and a precise verdict.

---

## Source map

This generated handbook should be reproducible from a small canonical set rather than copied from broad historical reports.

Recommended generator inputs:

```text
README.md
AGENTS.md
DESIGN.md
docs/DOCS_INDEX.md
docs/contracts/historical_market_data_foundation.md
docs/runbooks/historical_ohlcv_seed_runbook.md
selected repository-owned readiness metadata in scripts/build_ai_project_manual.py
```

The source manifest should record path, role, existence, digest, and generation time without embedding secrets or local absolute paths.

---

## JSON manifest

`docs/AI_PROJECT_MANUAL_SOURCES.json` is machine-readable generation evidence.

It should include:

- generator version;
- generated file path;
- canonical source paths;
- source role/classification;
- content digest;
- missing/deprecated-path state where relevant.

It must not include raw environment values, credentials, private URLs, personal paths, provider payloads, or target-environment secrets.
