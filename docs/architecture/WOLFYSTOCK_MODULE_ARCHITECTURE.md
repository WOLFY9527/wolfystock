# WolfyStock Modular Architecture Manual

This manual is the first Codex maintenance guide for WolfyStock modular
architecture. It describes the target shape, the current guard state, and the
next execution lanes. It is an inventory and operating guide, not a completed
refactor plan and not approval to change protected runtime behavior.

## 1. Overview

WolfyStock should behave as a set of bounded-context modules. Each domain owns a
clear responsibility, exposes a narrow public interface, and hides its internal
implementation details from other domains.

The target model is OOP-style package discipline:

- Public interface: facades, service entrypoints, schemas, DTOs, API clients,
  validators, and documented commands that another module may call.
- Private implementation: engines, repositories, provider clients, internal
  mutation helpers, calculation internals, storage layout, local UI material,
  and raw diagnostics that other modules must not import or reinterpret.
- Cross-domain access: call the public interface and consume the contract. Do
  not reach into another domain's internals to save a few lines of glue code.

This matters for AI/Codex maintenance because WolfyStock has high-risk domains
whose semantics must not drift during unrelated work. A backtest task should not
change scanner ranking, portfolio accounting, provider runtime fallback, AI
routing, auth/RBAC, admin observability, or terminal UI primitives unless the
task explicitly scopes that change and adds focused tests.

Current state is partial. Existing tests already freeze some modular seams:
`src.contracts` is limited to inert evidence and data-quality namespaces,
provider primitives must stay lightweight, LLM helper modules have import guards,
and service-to-API upward imports are inventoried. The broader domain import
guard model below is still a roadmap.

## 2. Dependency Direction Rules

Domain consumers must call public facades, schemas, DTO contracts, or API
clients. A caller should know what contract it receives, not which repository,
provider client, cache key, or private engine produced it.

Cross-domain imports into internal engines, repositories, provider clients, or
mutation internals are forbidden as a target rule. Existing exceptions must be
made explicit with owner comments, tests, and a deletion or migration path.

Platform services such as provider runtime, AI routing/cost, auth/RBAC, shared
contracts, and MarketCache must expose narrow public APIs. Domains should depend
on those APIs, not on the concrete clients or internal policy roots behind them.

Frontend pages should orchestrate and render. They may choose layout, state
transitions, and user interaction, but they should not reinterpret backend
internals, rebuild backend report semantics, or derive authoritative financial
state from raw diagnostic fields.

## 3. Domain Map

| Domain | Responsibility | Not responsible for | Public interface candidates | Internal/private candidates | Current external consumers | Protected semantics | Existing tests | Missing tests / guards | First safe execution task | Parallelization safety |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| provider-runtime / MarketCache | Provider ordering, fallback, cache/freshness semantics, TTL/SWR, circuit state, sanitized diagnostics, cache/local-first data access. | Scanner ranking, backtest math, portfolio accounting, AI model choice, UI copy. | `DataFetcherManager` capability methods, `src.providers.*` primitives, provider capability metadata, MarketCache service APIs, provider diagnostics DTOs. | Concrete fetchers in `data_provider/*`, raw provider payloads, credentials, cache keys, retry internals, circuit mutation internals. | Analysis pipeline, scanner, market overview, portfolio FX/risk, admin provider ops, backtest single-symbol fallback paths. | Provider order, first-good-wins fallback, live-call paths, TTL/SWR, circuit semantics, fallback/stale/mock/synthetic not-live labeling. | `tests/test_backend_modular_import_boundaries.py` provider primitive guard; provider protected-domain docs. | Guard concrete provider imports outside facades; golden TTL/SWR/fallback/circuit fixtures; MarketCache public/private boundary inventory. | Document facade contract and add an import guard for provider client imports. | Platform-level. Usually serial with scanner, backtest, portfolio, and AI routing work. |
| scanner | Bounded universe construction, deterministic filtering/scoring/ranking, candidate diagnostics, shortlist persistence, watchlist handoff, optional AI interpretation. | Automatic trading, backtest execution, portfolio mutation, provider policy root ownership, primary AI ranking. | `POST /api/v1/scanner/run`, scanner run/read/status APIs, scanner schemas, persisted run/candidate DTOs, watchlist handoff fields. | Profile engines, scoring weights, candidate filtering, internal evidence packets, persistence helpers, provider call details. | `/scanner`, admin logs, watchlist, backtest prefill links, analysis/chat links, notification summary. | Deterministic score/order, thresholds, profile separation, fallback/live labeling, AI as additive only. | Scanner docs; existing backend guards indirectly track `src.services.market_scanner_service` as runtime-heavy. | Golden candidate/rejection/handoff fixtures; forbid cross-domain imports into scanner internals; provider budget guard for full-universe scans. | Add scanner candidate DTO golden fixtures without changing scoring. | Can parallel with backtest only when handoff schemas are frozen and provider runtime is untouched. |
| backtest | Standard and rule backtest execution, calculation engine, result/readback schema, stored-first reports, support bundles, execution trace exports, universe job diagnostics. | Live market discovery, scanner ranking, portfolio accounting, AI provider policy, provider runtime fallback during universe execution. | `/api/v1/backtest/*` APIs, `src.services.backtest_service`, `src.services.rule_backtest_service`, backtest schemas, support-bundle/export-index contracts. | Calculation internals, trade/equity/audit row generation, local data loaders, execution assumptions, stored artifact repair logic. | `/backtest`, `/backtest/results/:runId`, `/backtest/compare`, scanner prefill, admin/operator diagnostics. | Calculation math, fills, costs, metrics, persisted result semantics, stored-first readback, local-only universe execution. | Backtest docs; import-boundary tests classify `rule_backtest_service` as runtime-heavy. | Golden result/trace/export fixtures; guard no provider fallback in universe execution; frontend no semantic reconstruction guard. | Add golden fixtures for stored-first result/readback/export DTOs. | Can parallel with scanner only if scanner-to-backtest handoff is frozen. Universe/local-data work should not overlap provider runtime work. |
| portfolio | Holdings, cash, transactions, P&L, FX/native currency display, cost basis, broker sync, ledger mutations, read projections. | Scanner selection, backtest math, provider runtime policy, auth capability design, UI-only accounting authority. | `/api/v1/portfolio/*`, portfolio service read models, mutation commands, admin portfolio projection DTOs, frontend portfolio API client. | Ledger mutation helpers, broker import/sync adapters, accounting formulas, risk internals, FX direct calls. | `/portfolio`, admin portfolio, risk diagnostics, broker sync/import workflows, settings/display currency. | Accounting, cash ledger, P&L, FX, holdings, transaction/corporate-action behavior, mutation semantics. | Protected-domain docs; import-boundary tests track portfolio services as runtime-heavy. | Ledger/cash/FX/cost-basis fixtures; mutation/read-model separation tests; guard UI from authoritative recalculation. | Add portfolio golden accounting DTO fixtures around current read models. | Accounting mutation work should remain serial until golden fixtures exist. UI read-only projection work can run separately. |
| AI routing / cost / LLM provider selection | Model/provider selection, prompt assembly boundaries, LiteLLM runtime, usage/cost ledger, budget modes, optional enrichment limits. | Scanner primary ranking, backtest math, portfolio accounting, provider market-data fallback, auth decisions. | `src.services.litellm_runtime`, `src.services.llm_instrumentation`, cost ledger services, research budget profiles, AI evidence contracts. | Raw prompts, raw LLM responses, provider credentials, model fallback internals, prompt assembly internals, cost ledger storage internals. | Analysis pipeline, scanner AI interpretation, rule parse/summarization, options lab, admin cost diagnostics. | Prompts, model routing, recommendation semantics, evidence weighting, quota/cost accounting, raw data secrecy. | LLM helper import guard; `src.contracts.evidence` inert contract tests. | Forbid bypassing AI routing/cost facade; prompt/routing boundary inventory; golden model selection and cost ledger fixtures. | Add AI routing/cost facade guard with explicit allowed call sites. | Platform-level. Usually serial with scanner/backtest/analysis tasks that use LLMs. |
| auth / RBAC | Session/auth dependencies, capability names, admin permissions, protected backend endpoints, protected frontend routes. | Domain math, provider policy, portfolio accounting, scanner ranking, UI visual primitives. | `api.deps` auth dependencies, auth endpoints, route guards, capability constants/inventory, frontend auth API/client. | Token/password/session internals, CSRF/CORS/security middleware, admin-only dependency internals, user storage mutations. | All protected API routes, `/admin/*`, `/settings/system`, premium routes, frontend route wrappers. | Capabilities, admin route protection, session behavior, endpoint-to-capability mapping, security middleware. | Existing service-to-API inventory lists legacy `api.deps` imports in admin services. | Route-capability inventory tests; explicit allowlist comments for service imports from `api.deps`; frontend protected-route contract tests. | Add auth route-capability inventory tests without changing enforcement. | Platform-level and often serial. Do not overlap with endpoint/schema migrations. |
| admin observability | Logs, activity, cost, provider circuits, provider ops, users/security, portfolio projections, read-only diagnostics, controlled admin actions. | Hidden domain ownership, scanner/backtest/portfolio semantic changes, raw secret exposure, normal user UI. | Admin endpoints under `/api/v1/admin/*`, admin schemas, admin services, frontend admin API clients and pages. | Raw logs/payloads, security mutation internals, provider circuit mutation internals, portfolio projection internals. | Admin pages, `/admin/logs`, provider ops, cost/security/users panels, operator validation flows. | Read-only diagnostics vs mutation/admin actions, sanitized fields, actor/session/symbol attribution, no secrets. | Service-to-API schema import inventory for admin services; protected-domain docs. | Admin DTO golden fixtures; explicit read-only vs mutation capability tests; raw payload/secret rendering guards. | Add admin diagnostic DTO fixtures and ownership comments for schema exceptions. | Read-only diagnostics can run in parallel with UI docs. Mutation/admin-control work should be serial with auth/provider work. |
| frontend terminal primitives / UI shell | Shared UI public interface for page shells, panels, grids, buttons, chips, notices, empty states, disclosures, dense lists/tables, and migrated page material. | Backend semantics, API contract reinterpretation, page-specific business calculations, raw provider/schema/debug leakage. | `apps/dsa-web/src/components/terminal/*`, page-level API clients, route shells, design guard scripts/tests. | Page-local card/chip/button/disclosure material, legacy common visual components, raw debug terminology, retired styling helpers. | Scanner, backtest, portfolio, admin/provider ops, market overview, home/report pages. | Terminal primitives as canonical visual surface, no retired primitives after migration, Chinese-first user states, collapsed raw diagnostics. | Terminal primitive tests; frontend constitution; terminal usage docs; route/page tests where present. | Guard migrated route families against retired common visual primitives; API-client schema compatibility tests; no raw/internal term guard per route. | Add a route-family primitive usage guard for one migrated page group. | UI shell work can parallel with backend docs only if files do not overlap. Large page migrations should avoid shared shell collisions. |
| shared contracts / schemas / API clients | DTOs, API schemas, validators, frontend API clients, inert contract namespace, compatibility contracts between backend and clients. | Runtime provider calls, DB connections, domain service orchestration, UI material, hidden behavior changes. | `api.v1.schemas.*`, `src.contracts.evidence`, `src.contracts.data_quality`, frontend `apps/dsa-web/src/api/*`, contract validators. | Endpoint implementations, service internals, provider runtime, adapters, raw payloads, persistence details. | API endpoints, frontend API clients, AI evidence consumers, data quality consumers, admin DTOs. | Additive compatibility, inert contracts, no runtime side effects, no wildcard schema imports from services. | `tests/test_contracts_namespace.py`; `tests/test_backend_modular_import_boundaries.py` service-to-API import inventory. | Frontend API client compatibility fixtures; DTO golden snapshots; explicit schema ownership comments for allowed upward imports. | Add frontend/backend DTO fixture tests for one stable read path. | Safe in parallel only when schema shape is frozen and no runtime code changes are required. |

## 4. Domain-Specific Rules

### Provider Runtime / MarketCache

Provider runtime owns provider order, fallback behavior, live-call boundaries,
freshness classification, TTL/SWR, circuit state, cache/local-first posture, and
sanitized provider diagnostics.

Rules:

- Do not change global provider order or live fallback order silently.
- Required data and optional enrichment must remain separate.
- Cache/local-first behavior is the default posture.
- Optional providers must be budgeted, deadline-bounded, and recorded with
  sanitized reason codes when skipped.
- MarketCache TTL, SWR, cold-start fallback, cache keys, stale labels, and
  payload meaning are protected semantics.
- Fallback, stale, mock, synthetic, fixture, or locally repaired data must never
  be marked live.
- New live provider paths require explicit approval.
- Capability metadata may describe provider domains, markets, quota class,
  freshness class, scanner/backtest eligibility, TTL hints, and operator notes.
  It must not import live clients or read credentials.

### Scanner

Scanner owns deterministic candidate discovery, profile-specific filtering,
ranking, candidate schema, rejection reasons, diagnostics, and scanner-to-
backtest handoff.

Rules:

- Deterministic scoring/ranking is primary. AI is additive interpretation only.
- AI must not replace `rank`, `score`, selection thresholds, or ordering.
- `cn_preopen_v1`, `us_preopen_v1`, and `hk_preopen_v1` must stay separated by
  profile and market assumptions.
- Scanner output is a pre-open watchlist, not automated trading advice.
- Scanner should not directly spend scarce providers across the full universe by
  default.
- Candidate diagnostics should reuse data already collected during the same
  scanner run. Do not make extra provider calls just to beautify rejected rows.
- Handoff to backtest should be through stable symbols/profile/context fields,
  not by importing backtest internals.

### Backtest

Backtest owns the calculation engine, result schema, report contract, audit
trail, trade/equity interpretation, stored-first readback, and support-bundle
exports.

Rules:

- Do not change calculation math, fills, costs, metrics, benchmark semantics, or
  persisted result meaning unless explicitly scoped.
- Universe execution must be local-data-only.
- Backtest universe execution must not call live providers, `_ensure_market_history`,
  provider fallback fetches, or DuckDB as runtime truth.
- Stored-first compare/readback/export contracts should remain authoritative.
- Frontend must not reconstruct backend report semantics from raw internals. It
  should consume backend summaries, authority diagnostics, and export contracts.
- Heavy details such as trades, equity curve, audit rows, and execution trace
  should stay behind detail/export surfaces, not compact manifests by default.

### Portfolio

Portfolio owns accounting, cash, holdings, P&L, FX/native currency behavior,
cost basis, broker sync, imports, ledger mutations, and read projections.

Rules:

- UI must not independently calculate authoritative accounting.
- Mutation commands and read models should be separated.
- Read projections may optimize or summarize current state, but must not change
  accounting semantics.
- Broker sync/import paths must preserve ledger mutation boundaries and actor or
  account attribution.
- Native currency visibility must remain clear when FX conversion fails.
- Direct provider/FX calls from accounting internals are coupling hotspots until
  a public provider/FX facade and golden fixtures exist.

### AI Routing / Cost

AI routing/cost owns model/provider selection, prompt assembly boundaries,
quota/cost ledger, provider budget boundaries, model fallback behavior, and
sanitized AI diagnostics.

Rules:

- Domains should not bypass the AI routing/cost facade.
- Optional enrichment must be budgeted and bounded by mode, deadline, and top-N
  constraints.
- Raw prompts, raw provider payloads, raw LLM responses, API keys, headers, and
  tokens must not be exposed in normal logs or UI.
- Metadata pass-through is allowed when it does not alter prompts, routing, or
  final decision semantics.
- AI evidence contracts should stay inert and should not import runtime-heavy
  scanner, provider, LLM, or API endpoint modules.

### Auth / RBAC

Auth/RBAC owns capability names, admin permissions, protected route contracts,
backend endpoint dependencies, session behavior, and security middleware.

Rules:

- Endpoint-to-capability mapping should become a contract.
- Backend endpoints should declare required capabilities through a stable auth
  dependency surface.
- Frontend route guards should mirror backend protection without inventing
  weaker local authority.
- Service imports from `api.deps` are current explicit exceptions and should
  stay inventoried until moved behind a lower layer.
- Do not change sessions, CSRF/CORS/security middleware, password handling, token
  handling, or admin protection as a side effect of domain work.

### Admin Observability

Admin observability owns execution logs, activity logs, cost views, provider
circuits, provider operations, users/security surfaces, and portfolio
projections as operator control and diagnostic surfaces.

Rules:

- Distinguish read-only diagnostics from mutation/admin actions.
- Diagnostics should expose bounded counts, health, reason codes, attribution,
  and summaries, not raw provider payloads or secrets.
- Mutating admin actions need explicit capability ownership and isolated danger
  zones in the UI.
- Normal user pages should not expose raw admin/operator terms. Admin pages may
  show technical diagnostics, but raw details should stay collapsed.

### Frontend Terminal Primitives

Terminal primitives are the frontend UI public interface for page material.
Pages own layout and product hierarchy. Shared primitives own visual material,
panel borders, radius, chips, buttons, empty states, dense lists/tables, and
disclosures.

Rules:

- Prefer `TerminalPageShell`, `TerminalGrid`, `TerminalPanel`,
  `TerminalNestedBlock`, `TerminalSectionHeader`, `TerminalMetric`,
  `TerminalButton`, `TerminalChip`, `TerminalEmptyState`, `TerminalNotice`,
  `TerminalDenseList`, `TerminalDenseTable`, and `TerminalDisclosure`.
- Page-local card/chip/button/disclosure material is discouraged.
- Migrated pages must not reintroduce retired local visual primitives or legacy
  common components blocked by guards/tests.
- Raw diagnostics, provider/schema/debug terms, and developer details should be
  collapsed by default on user pages.
- Frontend pages should consume API clients and DTOs, not backend implementation
  internals or raw storage semantics.

### Shared Contracts

Shared contracts include API schemas, frontend API clients, DTOs, inert contract
namespaces, validators, and compatibility fixtures.

Rules:

- `src.contracts` should remain inert: types, enums, validators, constants, and
  policy helpers only.
- Contracts must not import provider runtime, LLM/runtime modules, API endpoints,
  domain services, MarketCache, DB connections, or live-call clients.
- Frontend/backend consumers should import shared DTO/API-client contracts, not
  implementation internals.
- Additive schema fields require compatibility review. Shape-breaking changes
  require explicit scope, tests, and migration guidance.
- Service imports from `api.v1.schemas.*` are current explicit inventory items,
  not a pattern to expand without architecture review.

## 5. Cross-Domain Coupling Hotspots

Ranked current hotspots from the modular audit:

1. `src.agent.*` reaching into provider, backtest, portfolio, and storage
   concerns. Target: agents should orchestrate through service/facade contracts
   and AI routing/cost, not concrete internals.
2. `data_provider/base.py` and `analysis_provider_planner` both acting as
   provider policy roots. Target: one documented provider-runtime facade and one
   budget/routing policy seam.
3. `rule_backtest_service` mixing LLM adapter/provider runtime concerns with
   calculation and report concerns. Target: keep calculation/report contracts
   separate from parsing/summarization adapters and provider access.
4. `market_scanner_service` mixing provider access, scoring, AI suggestions,
   evidence, and persistence. Target: expose scanner public DTOs while isolating
   scoring, evidence, provider access, and persistence internals.
5. Portfolio accounting/risk services calling provider/FX services directly.
   Target: accounting consumes a narrow FX/provider facade and golden fixtures
   define authoritative accounting output.
6. Admin services importing `api.v1.schemas` / `api.deps` as explicit
   exceptions. Target: owner comments, allowlists, and eventual lower-layer DTO
   contracts.
7. Frontend large pages mixing Terminal primitives with legacy common
   components. Target: migrated route families use terminal primitives as the
   visual public interface and avoid retired material helpers.

## 6. Import Guard Roadmap

Proposed future guards:

- Forbid service modules importing `api.v1.endpoints`.
- Forbid concrete provider imports outside provider-runtime facades.
- Forbid cross-domain imports into scanner, backtest, and portfolio internals.
- Forbid bypassing the AI routing/cost facade.
- Make `api.v1.schemas` or `api.deps` imports from services explicit allowlists
  with ownership comments.
- Keep `src.contracts` limited to inert namespaces unless a reviewed boundary
  plan lands first.
- Frontend route families should avoid retired common visual primitives after
  migration.
- Frontend API clients should remain the UI boundary for backend schemas; pages
  should not import backend implementation details or duplicate server DTO
  semantics by hand.

## 7. Contract / Golden Fixture Roadmap

Needed fixtures and contract tests:

- Provider TTL/SWR/fallback/circuit fixtures.
- Scanner candidate, rejection reason, run metadata, and handoff fixtures.
- Backtest result, readback authority, execution trace, support bundle, export
  index, compare, and universe diagnostics fixtures.
- Portfolio ledger, cash, FX, holdings, cost-basis, broker import/sync, and read
  projection fixtures.
- AI model selection, prompt/routing boundary, budget skip, and cost ledger
  fixtures.
- Auth route-capability inventory fixtures.
- Admin diagnostic DTO fixtures for logs, cost, provider circuits, provider ops,
  users/security, and portfolio projections.
- Terminal primitive usage guards for migrated route families.
- Frontend API client schema compatibility fixtures.

## 8. AI Maintenance Playbook

When maintaining backtest, touch only backtest services, schemas, API client,
pages, fixtures, and docs unless explicitly scoped. Do not alter scanner
ranking, provider runtime order, portfolio accounting, AI routing, auth/RBAC, or
admin mutation behavior.

When maintaining scanner, touch only scanner services, scanner schemas, scanner
API client, scanner UI, watchlist handoff fields, fixtures, and docs unless
explicitly scoped. Do not alter backtest math, portfolio accounting, broad live
provider spend, AI primary ranking, or profile separation.

When maintaining portfolio, touch only portfolio services, portfolio schemas,
portfolio API client, portfolio UI, broker sync/import boundaries, fixtures, and
docs unless explicitly scoped. Do not move accounting authority into UI, scanner,
backtest, or admin projections.

When maintaining provider runtime, touch only provider-runtime facades,
capability metadata, MarketCache, circuit/freshness diagnostics, provider
clients, fixtures, and docs unless explicitly scoped. Report whether provider
order, new live paths, fallback semantics, TTL/SWR, and not-live labels changed.

When maintaining AI routing/cost, touch only routing/cost facades, LiteLLM
runtime, instrumentation, budget profiles, cost ledgers, evidence contracts,
fixtures, and docs unless explicitly scoped. Do not change prompts, recommendation
semantics, or model selection from another domain task.

When maintaining auth/RBAC, touch only auth dependencies, capability inventory,
protected route wrappers, endpoint authorization tests, fixtures, and docs unless
explicitly scoped. Do not weaken backend enforcement based on frontend behavior.

When maintaining terminal UI, touch only terminal primitives, page layout,
frontend API rendering, route-level tests, design guards, and docs unless
explicitly scoped. Do not reinterpret backend internals or change API contracts
from a visual task.

When maintaining admin observability, touch only admin endpoints, admin services,
admin schemas, admin API clients, admin pages, fixtures, and docs unless
explicitly scoped. Keep read-only diagnostics separate from mutation/admin
actions and do not expose raw secrets or payloads.

## 9. Parallelization Rules

The shared repository allows only one active task at a time.

Isolated task workspaces may run in parallel only if domains and files do not
overlap, the public contracts between them are frozen, and the tasks do not
share platform-level dependencies.

Provider runtime, AI routing/cost, and auth/RBAC changes are platform-level and
often serial. They affect multiple domains and should not be mixed with scanner,
backtest, portfolio, or admin feature work unless the task explicitly owns that
integration.

Scanner and backtest can run in parallel only if scanner-to-backtest handoff
schemas are frozen and neither task changes provider runtime, AI routing, or
shared schemas.

Portfolio accounting mutation work should remain serial unless golden fixtures
exist for ledger, cash, FX, holdings, and cost basis. Read-only UI projection
work is safer, but must still avoid changing accounting authority.

Frontend terminal primitive work can run in parallel with backend docs or tests
only when no shared frontend shell/primitives files overlap. Large route-family
migrations should be treated as shared UI-shell work.

## 10. Next Architecture Execution Lanes

1. Expand backend modular import boundary classifications and allowlists.
2. Add scanner/backtest/portfolio golden DTO fixtures.
3. Add auth route-capability inventory tests.
4. Add provider runtime facade/contract documentation and guard.
5. Add AI routing/cost facade guard and prompt/routing boundary classification.
