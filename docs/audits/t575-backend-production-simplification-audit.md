# T575 Backend Production Simplification and Architectural Debt Audit

## Result and status

**AUDIT COMPLETE; IMPLEMENTATION NOT AUTHORIZED BY THIS TASK.** The accepted
base is commit `4220b383cdfd0afa70f51e674c22246262ec0195` (tree
`74b8cae5ba78cd5944f66286ccc9d44ff21a92a3`) on branch
`codex/t575-backend-production-simplification-audit`.

This audit identifies **7,153 backend production LLOC** removable with high
confidence: 38 complete Python modules plus three unused public symbols. That is
`7,153 / 310,993 = 2.3001%` of the scoped backend. The moderate scenario adds a
non-overlapping point estimate of 9,570 LLOC, for a combined point estimate of
16,723 LLOC (`5.3773%`). The aggressive scenario is not the recommendation.

No production code, test, script, workflow, dependency, lockfile, topology,
architecture baseline, or other worktree is changed by T575. The machine-readable
evidence ledger is
`validation/t575_backend_production_simplification_audit.json`.

## Direct conclusions

1. **High-confidence removable code:** 7,153 LLOC, 38 whole modules, and three
   partial symbols. This is a lower bound, not the 22,253-LLOC static-unreachable
   set.
2. **Most duplicated authority:** persistence. `DatabaseManager` is a 9,890-LLOC,
   257-method hub with 51 direct storage consumers, 142 repository delegations,
   29 direct-return repository wrappers, and 106 phase/bridge methods.
3. **Greatest accidental complexity:** `market_overview_service.py` has the
   strongest combined size, fan-out, change, defect, state, and transformation
   evidence. The highest individual conditional scores are in
   `rule_backtest_engine.py` and `pipeline.py`.
4. **Wrappers with no meaningful boundary:** the seven `src/postgres_phase_*.py`
   wildcard shims, the market-provider route aliases and recursive compatibility
   projector, the provider-circuit alias delegate, three orphan public types, and
   the circular `Config` delegate chain.
5. **Compatibility paths that appear obsolete:** ten registered operations in
   the market-provider/admin/scanner/provider-circuit/options/watchlist clusters.
   They are not authorized for immediate deletion because repository tests still
   freeze them and T576 must confirm consumers. `/api/health` and `server.py` are
   demonstrably still required.
6. **Global state blocking safe parallelism:** the unclosed analysis-provider,
   market-cache, optional-enrichment, and yfinance executors; separate
   `TaskService` and `AnalysisTaskQueue` singletons; `Config` and
   `DatabaseManager` singletons; conversation/provider/overview caches.
7. **Files that should be split:** `rule_backtest_service.py`,
   `market_overview_service.py`, `storage.py`, `market_scanner_service.py`, and
   `portfolio_service.py`, each only across an existing domain boundary.
8. **Files to make smaller in place:** `src/runtime/settings.py`, `src/core/pipeline.py`,
   `report_renderer.py`, `api/v1/endpoints/portfolio.py`,
   `rule_backtest_engine.py`, and `data_provider/base.py`. Creating more modules
   before making their states explicit would add indirection.
9. **Unnecessary abstractions:** test-only evidence/schema islands, wildcard phase
   facades, unused `RootResponse`, `NotificationBuilder`, and
   `ErrorHandlerMiddleware`, `Config` compatibility delegates, and alias-only
   payload projectors.
10. **Required apparent duplication:** public/admin/privacy projections, provider
    wire symbol conversions, provider-specific retry/rate/cache policy, explicit
    fixture/production and injected/live identities, fail-closed unavailable
    projections, phase F/G comparison paths, and transaction/recovery boundaries.
11. **Safest first implementation wave:** T612, T613, T614, and T617 in four
    disjoint ownership lanes, followed by T616 as the sole topology/architecture
    integration writer.
12. **Maximum-safe parallel plan:** four lanes in the first wave, at most three in
    later protected waves, and serial ownership for API schema/error integration,
    all `storage.py` work, provider/market-source ownership joins, and final gate
    integration.

## Protected invariants

Every proposal preserves these distinctions:

- unavailable is not zero; missing is not neutral;
- stale is not fresh; delayed is not live;
- proxy is not official; synthetic is not real;
- fixture is not production; not checked is not ready;
- task accepted is not analysis completed;
- injected transport is not live transport;
- corrupt persisted state is not empty persisted state.

No lane may introduce fallback code, a compatibility shim, a parallel authority,
a silent default, or a wrapper that masks failure. Authentication, RBAC,
owner/tenant isolation, no-live, no-advice, source authority, persistence,
transactions, recovery, privacy, runtime identity, and release provenance remain
protected.

## Scope and measurement

The production Python inventory includes tracked code under `api/`, `src/`,
`data_provider/`, `bot/`, and `patch/`, plus root `main.py` and `server.py`.
Frontend code is excluded for T576. Tests and workflow optimization are excluded
for T569, but tests are caller and topology evidence. Scripts are operator/caller
evidence, not production inventory. The Rust backtest shadow CLI is validation
infrastructure. The 11 YAML files under `strategies/` are runtime assets rather
than Python inventory.

Definitions used for reproducibility:

- **LLOC:** a physical source line containing a Python token, excluding blanks,
  pure comments, and module/class/function docstrings.
- **Dependency edge:** one unique statically resolvable scoped-production import
  from one module to another.
- **Public symbol:** non-private module-level declaration/export, de-duplicated
  per module.
- **Endpoint:** a statically decorated handler. Runtime method/path operations
  are enumerated separately from `api.app.app`.
- **Service:** a top-level type under `src/services` ending in `Service`,
  `Engine`, or `Runner`.
- **Repository/store:** a concrete repository/store under `src/repositories`, a
  `PostgresPhase*Store`, or one of the two explicit service-side stores.
- **Provider adapter:** a concrete `BaseFetcher` subclass.
- **Projection helper:** a function/method whose name contains `project`,
  `projection`, or `serialize`, or begins `map_`/`_map_`.
- **Approximate complexity:** `1` plus AST branches (`if`, loops, conditional
  expressions, exception handlers, comprehensions, assertions, match cases, and
  Boolean operands after the first). This ranks hotspots; it is not Radon.

Static reachability starts at `main.py`, `server.py`, `api.app`, and
`bot.handler`, then checks scripts, tests, routes, registries, configuration,
exports, and history. Dynamic imports and external invocation remain residual
uncertainties; a text search alone was never treated as death proof.

## Exact production inventory

| Domain | Files | LLOC | Classes | Functions | Public symbols | Imports | Dependency edges | Endpoints |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Agents, workers, bots | 48 | 7,926 | 58 | 409 | 228 | 376 | 174 | 0 |
| API endpoints | 34 | 14,794 | 29 | 636 | 381 | 418 | 266 | 275 |
| API runtime/policy | 15 | 1,631 | 5 | 107 | 66 | 101 | 70 | 0 |
| API schemas | 80 | 19,300 | 991 | 625 | 1,377 | 292 | 16 | 0 |
| Core/domain contracts | 28 | 11,175 | 47 | 256 | 206 | 121 | 51 | 0 |
| Other backend | 42 | 22,467 | 110 | 814 | 310 | 343 | 106 | 0 |
| Persistence | 29 | 11,771 | 55 | 444 | 108 | 210 | 54 | 0 |
| Providers/transports | 32 | 12,350 | 58 | 482 | 198 | 335 | 100 | 0 |
| Runtime/config/entry points | 7 | 6,585 | 17 | 143 | 77 | 115 | 31 | 0 |
| Services | 311 | 202,994 | 578 | 7,841 | 2,304 | 2,116 | 705 | 0 |
| **Total** | **626** | **310,993** | **1,948** | **11,757** | **5,255** | **4,427** | **1,573** | **275** |

Physical source lines total 357,889. The services domain alone owns 202,994 LLOC
(`65.2729%`) and 7,841 functions, but exposes only 113 name-matched service,
engine, or runner types. It has the strongest size-to-contract imbalance.

### Contract and implementation counts

| Contract/implementation kind | Exact count | Qualification |
| --- | ---: | --- |
| Service modules excluding `__init__.py` | 309 | `src/services` only |
| Service/engine/runner types | 113 | Name-matched public types |
| Repository modules excluding `__init__.py` | 10 | `src/repositories` |
| Concrete repositories/stores | 19 | 10 repositories + 7 Postgres phase stores + 2 service-side stores |
| Concrete `BaseFetcher` adapters | 9 | All have selection/availability evidence |
| Dedicated transport modules | 5 | Functional `*transport.py` modules |
| Concrete transport/client types | 7 | Excludes 2 `Protocol` declarations |
| Schema modules excluding `__init__.py` | 81 | API plus domain schemas |
| Schema Python files including initializers | 83 | API plus domain schemas |
| Top-level schema/support classes | 1,010 | 991 are in the API-schema domain |
| Named projection helpers | 166 | Exact naming heuristic above |
| Object conversion calls | 1,742 | `dict`, `asdict`, model dump/validate, `to_dict`, JSON conversions |

### Runtime routes

Runtime import under a test-safe environment found 278 method/path operations:
267 public OpenAPI operations and 11 hidden runtime operations. Method counts are
175 GET, 87 POST, 9 DELETE, 4 PUT, and 3 PATCH. All 34 modules included by
`api/v1/router.py` are registered, and no duplicate method/path pair exists.
The 275 static handler functions differ because stacked decorators expose aliases
and root operations. No endpoint was classified as dead merely because it was
absent from OpenAPI.

## Native architecture evidence

The repository-native boundary inventory reports:

| Family | Exact baseline |
| --- | ---: |
| Direct storage consumers | 51 |
| Provider-heavy construction points | 21 |
| Service-to-API-schema edges | 53 |

The 53 schema edges originate in 52 files and reach 43 schema modules;
`api.v1.schemas.factors` is the largest single target with seven edges. The
native `boundary_debt.py --check` result is green at the accepted base. These
counters are architecture debt, not permission to lower a baseline before the
corresponding code and tests prove the reduction.

## Dead and unreachable code

The static root graph identifies 89 unreachable modules in 63 components,
totalling 22,253 LLOC. That number is deliberately not reported as removable.
The graph also contains script-owned database doctors, P2/P3 operators, recent
options and market-persistence evidence owners, dynamic registries, validation
adapters, and package initializers.

After call-site, route, registry, configuration, test, history, and protected
semantic checks, the high-confidence lower bound is:

| Candidate | Whole files | Partial symbols | LLOC | Evidence summary |
| --- | ---: | ---: | ---: | --- |
| C001 data-coverage/research island | 14 | 0 | 4,156 | No runtime path; 16 test-file callers only |
| C002 unregistered schema/service island | 12 | 0 | 1,694 | No route/registry path; 11 test-file callers only |
| C003 other task scaffolds | 5 | 0 | 1,223 | No runtime path; 6 test-file callers only |
| C004 Postgres phase wildcard shims | 7 | 0 | 7 | One wildcard line each; tests only |
| C005 orphan public abstractions | 0 | 3 | 73 | No caller; one stale re-export |
| **Total** | **38** | **3** | **7,153** | **2.3001% of backend LLOC** |

The three C005 symbols are `api/v1/schemas/common.py::RootResponse` (19 LLOC),
`src/notification.py::NotificationBuilder` (30), and
`api/middlewares/error_handler.py::ErrorHandlerMiddleware` (24). The middleware
is only re-exported from `api/middlewares/__init__.py`; `api.app` uses
`add_error_handlers` instead.

### Exact C001 files (4,156 LLOC)

- `src/services/data_coverage_matrix_batch.py` (125)
- `src/services/data_coverage_matrix_builder.py` (77)
- `src/services/data_coverage_matrix_contract.py` (563)
- `src/services/data_coverage_quality_matrix.py` (526)
- `src/services/data_coverage_surface_registry.py` (157)
- `src/services/data_coverage_surface_snapshot.py` (174)
- `src/services/research_narrative_composer.py` (439)
- `src/services/research_narrative_scanner_adapter.py` (182)
- `src/services/research_gap_prioritizer.py` (373)
- `src/services/research_checklist_composer.py` (199)
- `src/services/research_queue_evidence_provenance_adapter.py` (180)
- `src/services/cross_surface_research_synthesis_engine.py` (513)
- `src/services/stock_evidence_conflict_detector.py` (332)
- `src/services/market_regime_divergence_detector.py` (316)

### Exact C002 files (1,694 LLOC)

- `api/v1/schemas/custom_strategy.py` (264)
- `api/v1/schemas/event_intelligence.py` (55)
- `api/v1/schemas/event_window.py` (57)
- `api/v1/schemas/homepage_explanation.py` (178)
- `api/v1/schemas/homepage_empty_state.py` (143)
- `src/services/custom_strategy_contracts.py` (133)
- `src/services/event_intelligence_contracts.py` (81)
- `src/services/event_intelligence_provider_contract.py` (15)
- `src/services/event_intelligence_timeline.py` (208)
- `src/services/event_window_service.py` (266)
- `src/services/homepage_explanation_service.py` (208)
- `src/services/homepage_empty_state_service.py` (86)

### Exact C003 and C004 files (1,230 LLOC)

- `src/services/backend_metrics_snapshot_service.py` (374)
- `src/services/user_alert_dry_run_summary.py` (224)
- `src/agent/agents/portfolio_agent.py` (99)
- `src/services/ai_evidence_dry_run_explanation.py` (305)
- `src/services/factor_experiment_manifest.py` (221)
- `src/postgres_phase_a.py` through `src/postgres_phase_g.py` (1 each)

The 38 whole modules contain 63 classes, 434 functions/methods, 94 public
top-level symbols, and 114 explicit `__all__` entries.

### Topology impact qualification

Topology counts below include every node in a directly importing test file, so
they are upper bounds and overlap where a shared test imports multiple groups.
They must not be summed or treated as automatic topology deletion counts.

| Candidate | Direct test files | Affected-file topology upper bound |
| --- | ---: | --- |
| C001 | 16 | 118: provider 24, residual 65, market 15, scanner 3, API 11 |
| C002 | 11 | 142: residual 50, API 79, auth 13 |
| C003 | 6 | 151: residual 145, API 6 |
| C004 | 14 | 142: database 142 |
| C005 | 0 | 0 directly importing nodes found |

Implementation tasks must first run focused tests with topology bootstrap. T616
is the sole task allowed to reconcile `validation/domain_test_topology.json`
after determining exactly which shared-file tests survive.

### Retained or insufficient-evidence static components

- The six-module options-authority component (2,629 LLOC) has operator/tests and
  recent protected fixes. It is not deletion evidence.
- Durable-runtime and durable-worker components have recent atomicity/lifecycle
  work and operational callers.
- Market-persistence evidence components preserve source/persistence truth.
- Historical/repository doctors and P2/P3 runners are script-owned operators.
- Postgres phase F/G stores retain live coexistence, comparison, transaction,
  and recovery responsibilities.

## Parallel authorities

| Cluster | Authoritative owner | Shadow owners | Evidence | Disposition |
| --- | --- | --- | --- | --- |
| Persistence | Domain repositories and reviewed Postgres stores | `DatabaseManager`, 51 direct consumers, 106 phase/bridge methods | 9,890 LLOC; 142 repo delegations | Move serial domain slices into repositories |
| Runtime/provider construction | `RuntimeContainer` + `DataFetcherManager` | 21 service construction points, module globals, endpoint-local construction | Native debt manifest | Move construction; retain provider policy |
| Configuration | `RuntimeSettings` | `Config`, 41 outside environment readers, app reads | 376 env reads; circular parse chain | Flatten, fail closed |
| Analysis tasks | `AnalysisTaskQueue` | Bot `TaskService` | Separate pools/state vocabularies; durable vs in-memory | Consolidate after actor/no-advice contract |
| Source/freshness | Provider ports/types + `market_observation_time.py` | Overview/endpoint/cache/provider projections | 83 helpers across 52 modules | Consolidate facts, retain truth distinctions |
| Symbol identity | Canonical domain classification | 71 helpers across 51 modules | Repeated casing/market inference/conversion | Consolidate identity, retain provider wire formats |
| API projection/errors | API schema/error boundary | Endpoint dicts, service API-schema imports, hand-built errors | 53 reverse edges, 166 helpers, 21 bypass handlers | One-way projection and one redaction owner |

Persistence is the direct answer to “most duplicated authority.” Market source
and freshness is the most semantically dangerous shadow-authority cluster, but
it has fewer structural duplicate paths than persistence.

## Wrapper and delegation chains

| Representative chain | Static depth | Layer classification | Decision |
| --- | ---: | --- | --- |
| `Config` instance -> load -> `RuntimeSettings.load(Config)` -> environment parser -> `Config._parse_*` | 6 | Redundant delegation/circular compatibility | Flatten to `RuntimeSettings` |
| Endpoint -> service -> repository -> `DatabaseManager` -> phase/legacy bridge | 5 | Service/repository useful; storage forwarding mixed | Move domain logic to repository; retain reviewed bridge semantics |
| Market-provider alias -> recursive legacy projector -> canonical service | 3 | Compatibility-only | Delete only after T576/product approval |
| Options endpoint -> 33 mappers -> domain/service models -> safe `Response` | 3 | Consumer boundary required; mapper ownership fragmented | One validated projector |
| Watchlist root alias -> service -> identity exception -> empty list | 3 | Compatibility-only and failure masking | Replace with canonical fail-closed endpoint |

The options endpoint alone has 33 `_map_`/`_project_` helpers spanning 385 source
lines. The problem is not that a consumer projection exists; it is that the
same payload is renamed/defaulted through many helpers and then emitted via a
`Response` path that bypasses FastAPI response-model enforcement.

## Conditional complexity and maintenance hotspots

| Path | LLOC | Max score | Fan-in/out | 2026 touches/fixes | Test import files | Assessment |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `src/services/rule_backtest_service.py` | 11,814 | 89 | 2 / 20 | 98 / 11 | 12 | Split by stable backtest owner |
| `src/services/market_overview_service.py` | 11,038 | 107 | 4 / 44 | 122 / 36 | 33 | Highest combined accidental complexity |
| `src/storage.py` | 9,890 | 52 | 60 / 20 | 84 / 24 | 134 | Split serially by repository domain |
| `src/services/market_scanner_service.py` | 8,846 | 84 | 3 / 37 | 60 / 21 | 12 | Split readiness/persistence/execution |
| `src/services/portfolio_service.py` | 5,832 | 59 | 5 / 8 | 33 / 12 | 10 | Split only across ledger/read model |
| `src/core/pipeline.py` | 4,506 | 262 | 2 / 29 | 59 / 13 | 11 | State table first; shrink in place |
| `src/core/rule_backtest_engine.py` | 4,252 | 263 | 3 / 1 | 14 / 4 | 5 | Cohesive compute owner; table-drive dispatch |
| `src/services/report_renderer.py` | 3,828 | 182 | 3 / 4 | 21 / 6 | 1 | Presentation-state table; no new module first |
| `src/services/execution_log_service.py` | 4,205 | 78 | 16 / 3 | 24 / 8 | 8 | Large but cohesive audit boundary; retain |
| `data_provider/base.py` | 3,001 | 91 | 23 / 18 | 45 / 15 | 16 | Cohesive provider router; simplify conditions only |
| `src/runtime/settings.py` | 1,859 | 129 | 4 / 4 | 2 / 1 | 2 | Declarative parsers; shrink in place |
| `api/v1/endpoints/portfolio.py` | 2,446 | 37 | 1 / 18 | 28 / 12 | 0 direct | Shrink in place; privacy projection stays |

Specific conditional targets are
`rule_backtest_engine._signal_family_triggered` (score 263),
`pipeline._stabilize_analysis_result` (262), and
`report_renderer._build_trade_setup` (182). They encode dispatch or state as
large condition sets. Tables, named guard clauses, and explicit state
transitions are appropriate. Recursion is not.

## Compatibility and fallback debt

Ten registered compatibility operations appear obsolete but remain test-frozen:

- canonical `/market-providers/operations`; aliases
  `/market-provider-operations`, `/provider-operations`, `/market-providers`;
- canonical `/ops/status`; aliases `/ops-status`, `/launch-cockpit`;
- canonical `/ops/scanner-universe-readiness`; alias
  `/scanner/universe-readiness`;
- canonical `/providers/circuits`; alias `/provider-circuits`;
- options `/lab` and `/gamma` compatibility states;
- canonical `/watchlist/items`; compatibility root `/watchlist/`.

The frontend production API paths inspected by this audit use the canonical
market-provider, ops, scanner-readiness, circuit, and watchlist paths. Tests and
auth inventories explicitly assert aliases, so frontend absence alone is not an
authorized deprecation. T576 and a product decision are dependencies.

The watchlist root is particularly unsafe: it catches `Unknown app user` and
returns an empty list, turning identity failure into successful empty account
state. `MarketDecisionCockpitService._market_overview_decision` catches broad
exceptions and builds a newly timestamped decision from `{}`, making unchecked
data look current. Both should become explicit unavailable/error states, not new
fallbacks.

`/api/health` is retained because desktop/scripts consume it. `server.py` is
retained because it is a documented Uvicorn entry point. The deprecated
`strategies/` directory is retained until its 11 YAML assets move atomically;
only then can `load_builtin_strategies`, `select_strategies`, and
`StrategyRouter` aliases be removed without adding another lookup fallback.

## Exception and transformation debt

The scoped backend contains 1,705 exception handlers: 890 catch
`Exception`/`BaseException`, zero are bare, 60 are pass-only, and 237 use
`raise ... from`. Broad-handler hotspots are `data_provider/base.py` (35), the
portfolio endpoint (35), `akshare_fetcher.py` (35), `storage.py` (32),
`pipeline.py` (29), `market_overview_service.py` (29), `search_service.py` (26),
and `market_scanner_service.py` (21).

This does not justify blanket narrowing. Many catches deliberately sanitize a
provider or parsing boundary. Concrete targets are programming errors entering
fallback paths, successful payloads created from failures, and duplicate error
envelopes. The market-overview endpoint's explicit unavailable projection is a
counterexample that should remain fail closed. Pipeline notification
classification can remain best-effort, but should preserve a bounded reason.

There are 1,742 object conversion calls and 166 named projection helpers. Twenty
one handlers declare a response model but emit a `Response`/consumer-safe JSON
path: options 10, stocks 4, analysis 2, research 2, market 2, and portfolio 1.
The safe projection is a real privacy boundary; the simplification is to validate
before emission and make the transformation one-way, not to return raw service or
provider objects.

Exact schema-field comparison found 31 duplicated field-set groups spanning 101
classes. Examples include 15 homepage classes with `state/label/summary`, six
with `state/label/available/summary`, six drilldown route models, and five
pagination families. Equal fields are only a candidate signal: public/admin,
privacy, source, and unavailable semantics can make identical structures
intentionally distinct.

## Configuration, cache, and lifecycle ownership

There are 376 AST environment reads: 285 in `src/runtime/settings.py` and 91 across
41 other modules. `Config` exposes 15 delegate methods spanning 81 source lines,
and its load path calls `RuntimeSettings`, which calls back into `Config` parsers.
Invalid agent/cache values can silently default. Five reserved fields describe
unavailable features; frontend hides four while runtime still parses four.

The intended owner is `RuntimeSettings`, with one parse pass and explicit invalid
configuration failures. This does not require a dependency-injection framework.
`RuntimeContainer` should own resource construction and close order, but today it
owns only `SystemConfigService`, `AnalysisTaskQueue`, and optional
`CryptoRealtimeService`.

Unowned or split lifecycle state includes:

- `analysis_provider_planner._DEFAULT_EXECUTOR` and its executor, with no close;
- `MarketCache` singleton/proxy and local executor; reset closes only the remote
  backend;
- `_OPTIONAL_ENRICHMENT_POOL` and `_YFINANCE_HISTORY_EXECUTOR`;
- bot `TaskService` versus API `AnalysisTaskQueue`;
- conversation manager, `Config`, and `DatabaseManager` singletons;
- provider circuit/cache and market overview/search caches.

The answer is not one undifferentiated cache. Provider cooldown/rate-limit state,
market observation state, and response cache state have different truth and TTL
contracts. Their resource lifecycle and TTL policy owners can be explicit while
their semantic scopes remain separate.

The shared market cache defines 12 reviewed panel TTLs: crypto 15 seconds;
futures, equity index, CN indices, temperature, and market briefing 30; FX/
commodity and breadth 60; flows and sector rotation 180; rates 600; sentiment
1,800. `MarketOverviewService` also maintains class `_cache`, class
`_market_data_cache`, a 15-second official-macro micro-cache, and the shared
`MarketCache`. `DataFetcherManager` separately owns a 60-second CN stock-list
cache, 15-second realtime snapshot cache, configured fundamental cache, and a
process-lifetime stock-name cache. These are overlapping lifecycle owners, not
automatically equivalent caches.

`MarketCache.get_or_refresh` can launch a background refresh and `_payload` can
best-effort persist a remote cache entry, so a nominal read has controlled side
effects. Those paths should be named and lifecycle-owned rather than treated as
pure reads. Provider-circuit cooldown remains a separate enforcement/observation
authority and must not be folded into response-cache TTL logic.

## Database and persistence structure

`DatabaseManager` spans 9,890 LLOC and 257 methods. Within it are 29 methods with
transaction behavior, 106 phase/bridge methods, and 24 methods containing broad
exception handlers. Ten repository modules and two service-side stores provide
useful domain boundaries, but 142 repository methods delegate back into the
manager and 29 simply return that delegation.

The simplification direction is therefore **not** “delete repositories.” It is
to make repositories own domain queries and transactions, leaving connection and
lifecycle ownership behind. Auth/identity, market/scanner, and
portfolio/backtest must be three serial tasks because they share `storage.py` and
protected transaction state. Phase F/G shadow/comparison paths stay until their
authority cutover is separately proven. No read fallback, dual write, silent
recovery, or weakened factory-reset behavior is proposed.

## Provider and transport structure

There are nine concrete `BaseFetcher` adapters, and all nine have selection or
availability evidence; none is a high-confidence deletion candidate. There are
five dedicated functional transport modules, seven concrete class-based
transport/client implementations, and two protocol declarations.

`DataFetcherManager`, provider result/port types, and source-observation facts are
the correct common boundaries. The native architecture guard still finds 21
provider-heavy construction points. A name inventory finds 71 symbol
normalization/classification/conversion helpers across 51 modules and 83
source/freshness/observation helpers across 52. Canonical domain identity can be
shared; provider wire symbols, rate limits, retry disposition, malformed/empty
handling, and official/proxy source identity cannot be collapsed.

## Historical residue

Recent history already removed unused eager package facades, provider policy and
cache layers, an options test-only evidence island, and isolated backtest and
portfolio research scaffolds. The remaining C001-C005 modules match that residue
pattern: task-generated public-looking contracts outlived runtime adoption.

History also prevents over-deletion. Options authority, durable runtime, and
market-persistence components received recent protected fixes. Market overview
has 122 touches and 36 fix commits in 2026; that is evidence for controlled owner
extraction, not a rewrite. `storage.py` has 84 touches/24 fixes, and scanner has
60/21. Any broad redesign would erase the distinctions those fixes established.

## Simplification scenarios

### Conservative - recommended first

- Exact reduction: **7,153 LLOC** (`2.3001%`).
- Scope: C001-C005, after focused caller/test migration and topology join.
- Arithmetic: `4,156 + 1,694 + 1,223 + 7 + 73 = 7,153`.
- C006 can move 418 LLOC of inline diagnostics out of production, but it is not
  counted as repository-wide deletion because equivalent script/test logic may
  remain.

### Moderate - recommended after the conservative join

- Additional point estimate: **9,570 LLOC**.
- Additional plausible range: **6,800-12,500 LLOC**
  (`2.1865%-4.0194%` of backend).
- Combined point estimate: **16,723 LLOC** (`5.3773%`).

The non-overlapping point arithmetic is:

| Component | LLOC |
| --- | ---: |
| Task authority | 190 |
| Config ownership including reserved fields | 140 |
| Lifecycle ownership | 220 |
| Persistence ownership | 3,200 |
| Provider construction | 650 |
| Symbol normalization | 240 |
| API schema/projection | 900 |
| Compatibility routes | 160 |
| Error translation including cockpit fallback | 350 |
| One-way transformations | 550 |
| Backtest condition tables | 260 |
| Pipeline state table | 240 |
| Report-renderer state table | 300 |
| Market overview including source/freshness owner | 1,200 |
| Scanner ownership | 850 |
| Strategy compatibility | 120 |
| **Total** | **9,570** |

C013 is included in C021, C023 in C008, and C025 in C016; they are not counted
twice. C006 is a move and is excluded from net reduction arithmetic.

### Aggressive - not recommended

An additional 12,000-22,000 LLOC might be reduced through a broad service,
schema, repository, and provider redesign. Confidence is low, and the range is
`3.8586%-7.0741%` of current backend LLOC. No evidence supports choosing this
over the staged moderate roadmap. It would combine protected domains, create a
large rollback boundary, and obscure whether behavior was preserved.

## Exact candidate ledger

The JSON artifact is the canonical field-complete ledger. The two tables below
repeat every required field in readable form; file arrays are exact in the JSON
and C001-C005 are expanded above.

### Ownership, evidence, disposition, and estimate

| ID | Current files/symbols | Surviving owner | Evidence | Confidence | Disposition | LLOC | Expected complexity reduction |
| --- | --- | --- | --- | --- | --- | ---: | --- |
| C001 | 14 data-coverage/research files above | Existing registered research/market/scanner/provider contracts | No runtime path; 16 test files only | High | delete | 4,156 | Remove 14 modules |
| C002 | 12 unregistered schemas/services above | Registered homepage/event/strategy contracts | No route/registry path; 11 test files only | High | delete | 1,694 | Remove 12 modules |
| C003 | 5 scaffold files above | Existing admin/alert/portfolio/AI/factor owners | No runtime path; 6 test files only | High | delete | 1,223 | Remove 5 modules |
| C004 | `src/postgres_phase_a.py` ... `_g.py` | Canonical Postgres store modules | One wildcard line each; tests only | High | delete | 7 | Remove 7 import authorities |
| C005 | `RootResponse`; `NotificationBuilder`; `ErrorHandlerMiddleware` | Concrete schemas/functions/app handlers | No caller; stale middleware re-export | High | delete | 73 | Remove 3 public abstractions |
| C006 | 15 inline `__main__` diagnostics | `scripts/` diagnostics or tests | 418 production LLOC; operator paths excluded | Medium | move to authoritative owner | 418 | Remove import-time CLI branches |
| C007 | `TaskService`; `AnalysisTaskQueue`; bot analyze | Composed `AnalysisTaskQueue` | Two pools and state authorities | Medium | consolidate | 190 | One task state/lifecycle owner |
| C008 | `Config`; `get_config`; `RuntimeSettings`; parser | `RuntimeSettings` | Circular depth 6; 376 env reads | High | flatten | 140 | One parse pass; lower score 129 |
| C009 | Runtime container, cache/executor globals | `RuntimeContainer` lifespan | Pools lack close owners | High | move to authoritative owner | 220 | One startup/shutdown graph |
| C010 | `DatabaseManager` and 10 repositories | Domain repositories/Postgres stores | 51 consumers, 142 delegates, 106 bridges | High direction/medium estimate | move to authoritative owner | 3,200 | Shrink fan-in-60 hub in serial slices |
| C011 | `DataFetcherManager`; 21 construction points | Provider composition | Native debt manifest count 21 | High | move to authoritative owner | 650 | Remove duplicate construction policy |
| C012 | 71 symbol helpers/51 modules | Canonical domain classifier | AST/name inventory | Medium | consolidate | 240 | Remove duplicate market/casing inference |
| C013 | 83 source/freshness helpers/52 modules | Provider facts + observation-time owner | Helper inventory; overview fan-out 44 | Medium | consolidate | 600 | Remove duplicate observation projection |
| C014 | 53 reverse schema edges; 31 duplicate groups | Domain types + API schemas | Native guard; 101 field-equal classes | Medium | move to authoritative owner | 900 | Remove reverse edges/model mirrors |
| C015 | 10 compatibility operations | Canonical routes | Frontend uses canonical; tests retain aliases | Medium | replace compatibility path | 160 | Remove alias/projection branches |
| C016 | Error helpers/handlers/cockpit catch | API error owner + domain exceptions | 890 broad catches; duplicate envelopes | Medium | consolidate | 350 | One taxonomy/redaction boundary |
| C017 | 166 helpers; 1,742 conversions; 21 bypasses | One-way validated consumer projector | Exact AST inventories | Medium | flatten | 550 | Reduce rename/default/validation hops |
| C018 | Backtest signal/heatmap functions | Existing engine/service with tables | Scores 263/89; symbol 5,917 lines | Medium | simplify conditional structure | 260 | Table-drive indicator dispatch |
| C019 | `pipeline._stabilize_analysis_result` | Pipeline state table | Score 262; 1,977 lines | High hotspot/medium estimate | simplify conditional structure | 240 | Named guarded transitions |
| C020 | `report_renderer._build_trade_setup` | Renderer state table | Score 182; 3,408 lines | Medium | simplify conditional structure | 300 | Table-drive presentation states |
| C021 | Overview service and market endpoints | Typed collection/evidence/cache/projection owners | 11,038 LLOC; 122 touches/36 fixes | High hotspot/medium boundary | move to authoritative owner | 1,200 | Split 359-function hub; includes C013 |
| C022 | Scanner service/readiness/repo/endpoint | Existing separate owners | 8,846 LLOC; fan-out 37; 21 fixes | High hotspot/medium estimate | move to authoritative owner | 850 | Separate readiness/persistence/execution |
| C023 | 5 reserved unavailable config fields | No replacement | Unavailable/read-only; runtime still parses | Medium | delete | 70 | Remove parsing/default branches; included C008 |
| C024 | Strategy method/type aliases and asset path | `SkillManager`/`SkillRouter` + final asset owner | Aliases test-only; 11 assets still legacy | Medium | replace compatibility path | 120 | Remove dual naming after atomic move |
| C025 | Cockpit fallback; watchlist empty fallback | Explicit unavailable/auth error owner | Failure becomes current-looking/success payload | High | replace compatibility path | 80 | Remove fallback-success branches; included C016 |
| C026 | Health/server/privacy/provider/audit boundaries | Existing owners | Live consumers/security/truth evidence | High | retain | 0 | None without equivalence proof |
| C027 | Options/durable/market persistence/operator/phase F-G | Existing protected owners | Static-only signal contradicted by history/callers | Low | insufficient evidence | 0 | No roadmap reduction |

### Risk, tests, topology, migration, rollback, and dependencies

| ID | Semantic risk | Operational risk | Test impact | Topology impact | Migration and rollback boundary | Dependencies/conflicts |
| --- | --- | --- | --- | --- | --- | --- |
| C001 | Medium evidence-label risk | Low | 16 direct files | Upper bound 118 | Migrate/delete shared tests; one 14-module commit | T569 test/topology |
| C002 | Medium live-schema similarity | Low | 11 direct files | Upper bound 142 | Compare registered models; one 12-module commit | T576, T569 |
| C003 | Low-medium no-advice/redaction | Low | 6 direct files | Upper bound 151 | Check dynamic agent registry; one task commit | T569 |
| C004 | High if canonical stores confused | Low | 14 phase files | Upper bound 142 database | Migrate test imports only; restore seven shims | T569 |
| C005 | Low; active redaction retained | Low | Import-boundary assertion | 0 direct | Remove re-export; restore 3 symbols/re-export | None |
| C006 | Medium provider/auth diagnostics | Medium undocumented invocation | Script smoke/import | Move only | Inventory operator paths; per-domain rollback | T569 |
| C007 | High no-advice/state identity | High recovery/in-flight work | Queue + bot tests | Runtime/API/bot | Define actor and states; one owner commit | C008/C009 |
| C008 | High auth/credentials/provider identity | Medium startup/env timing | Config/runtime/API readiness | Config fan-in 80 | Caller slices; one no-facade commit | None |
| C009 | High sessions/tasks | High shutdown | Lifespan/cache/provider/task | Runtime/provider | Add idempotent close first; one lifecycle commit | C008; avoid T566 |
| C010 | Critical persistence semantics | Critical coexistence/reset | Repository/storage/real PG | Database | Three serial commits; never dual-write | C004; T569/T566 |
| C011 | Critical provider/no-live | High sessions/rate limits | Provider/cache/injected transport | Provider guard | Per construction family; no lazy fallback | C008/C009; T566 |
| C012 | High symbol/persistence identity | Medium | Symbol/provider/domain tests | Cross-domain | Separate domain identity from wire format | C011 |
| C013 | Critical all truth distinctions | High cache/freshness | Market/provider consumers | Market/provider | Per projection family; no timestamp substitution | C011/C012; T566 |
| C014 | Critical privacy/truth | Medium serialization | Schema/public safety | API/residual | Prove semantics, not field equality; per family | C001-C003; T576/T569 |
| C015 | High external/auth contract | Medium route removal | Compatibility/auth/frontend | API | T576/product approval; direct deletion, no redirect | T576/T569 |
| C016 | Critical redaction/fail closed | High status/retry/observability | Runtime/public/provider | API/security/market | Narrow family commits; explicit unavailable | C005/C014 |
| C017 | Critical allowlist/source truth | Medium shape/performance | Consumer/schema endpoints | API/residual | Preserve safe boundary; per endpoint family | C014/C015; T576 |
| C018 | Critical backtest truth | High | Golden/shadow/backtest | Backtest | Freeze exact fixtures; one dispatch commit | C010 |
| C019 | High accepted/completed/no-advice | Medium | Pipeline suite | Analysis/residual | Characterize states; one table commit | C007 |
| C020 | Critical no-advice language | Low-medium | Renderer/public safety | Report/residual | Freeze output; one renderer commit | None |
| C021 | Critical market truth | Critical providers/cache | 33 import files/families | Market/provider/API | One evidence family per commit; no old/new owner | C011-C013/C017; T566 |
| C022 | Critical score/persistence/source | High scan/dedupe | Scanner suite | Scanner/market/provider/DB | Freeze score/order/labels; staged commits | C010-C012 |
| C023 | Medium external env unknown | Medium | Config/readiness | Runtime/config | Inventory deployments; same rollback as C008 | C008/T576 |
| C024 | High strategy/no-advice | Medium assets | Agent registry/pipeline | Agent/residual | Atomic asset/API move; no directory fallback | T569 |
| C025 | High, direction is fail closed | Medium caller-visible status | Cockpit/watchlist/auth | Market/API/auth | Product approval; per fallback commit | C015/C016/T576 |
| C026 | Critical if removed | Critical | Retain contracts | None | No migration | None |
| C027 | Critical | Critical | No deletion tests | None | Obtain operator/runtime proof first | T566/T569 |

## T612+ implementation roadmap

The machine ledger gives every lane's exact `expected_files`, protected owners,
tests, and commit subject. References such as “C001 files” resolve to the exact
arrays in the same JSON and the expanded lists above; the schema-edge set is the
accepted-base `debt-manifest.json` entry set after deleting T612-T614 sources.

```text
Wave 1 (max 4): T612   T613   T614   T617
                    \    |    /       |
                     T616 join         |
                       |               |
Wave 2 (max 3):       T615   T618   T620 <- T576 decision
                              |      /
                              T619  /
                                \  /
                                 T621

Persistence serial: T622 -> T623 -> T624

Protected max 3 after dependencies:
  T625 market overview    T627 backtest    T628 pipeline/report
       |
      T626 scanner

Final serial join: T629
```

### Ownership and dependency lanes

| Task | Exact ownership / primary expected files | Protected adjacent owners | Dependencies | Parallel safety | LOC | Complexity/maintenance benefit |
| --- | --- | --- | --- | --- | ---: | --- |
| T612 | C001 14 files + 16 named direct test files | Provider/source, scanner, market truth | None | Parallel T613/T614/T617; no topology edit | 4,156 | Delete largest inactive island |
| T613 | C002 12 files + 11 named direct test files | Registered homepage/event/options/auth schemas | None | Parallel T612/T614/T617 | 1,694 | Remove unregistered public-looking contracts |
| T614 | C003 five files, C004 seven shims, C005 three symbols/re-export, direct tests | Portfolio no-advice, redaction, phase F/G stores | None | Parallel T612/T613/T617 | 1,303 | Delete 12 modules and 3 orphan symbols |
| T615 | C006 15 modules; `src/agent/skills/base.py`, `src/agent/skills/router.py`, `strategies/` | Provider no-live, auth diagnostics, strategy no-advice | T616/T617/operator inventory | Parallel T618/T620 after paths frozen | 538 production LLOC | Move diagnostics; retire aliases/assets atomically |
| T616 | `domain_test_topology.json`, architecture manifest only if counters change, shared integration tests | All topology/baselines | T612-T614 | Sole manifest/topology writer | 0 | Exact integration and baseline proof |
| T617 | `src/config.py`, `src/runtime/settings.py`, composition/app/deps, env example, 7 named config tests | Auth, credentials, provider/runtime identity | None | Parallel deletion lanes; sole settings writer | 140 | One parser/owner; explicit invalid values |
| T618 | Composition/app/deps, task queue/service, bot analyze, planner executor, market cache, 5 named tests | Tenant/task persistence, sessions, no-advice | T617 | Parallel T615/T620; sole lifecycle writer | 410 | One task state and shutdown graph |
| T619 | `data_provider/base.py`, composition, classifier, all 21 exact manifest construction files, guard and 5 named tests | Provider order/no-live/credentials/source/wire symbols | T617/T618 | Serial provider composition; before T625/T626 | 890 | One construction graph/domain identity owner |
| T620 | Five named endpoint modules and four route/auth/watchlist test files | Auth, watchlist identity, options unavailable; retain health/server | T576 decision/T616 | Parallel T615/T618; sole route writer | 160 | Remove 10 approved compatibility operations |
| T621 | Ten named API/error endpoint files, six named schemas, cockpit service, accepted-base schema-edge file set | Public/admin privacy, auth, source truth, secrets | T612-T614/T619/T620 | Serial shared API boundary | 1,800 | One-way validation/error projection |
| T622 | `storage.py`, auth/analysis repos, phase A/B stores, named tests | Auth/RBAC/tenant/session/audit | T614/T618 | Serial with T623/T624 | 900 | Identity repository transaction owner |
| T623 | `storage.py`, stock/history/scanner repos, phase C/D stores, named tests | Scanner persistence/source/watchlist owner | T622 | Serial with T622/T624 | 1,200 | Market/scanner repository ownership |
| T624 | `storage.py`, portfolio/backtest/rule repos, phase E-G stores, named tests | Ledger/fills/metrics/transaction/recovery | T623 | Serial persistence join | 1,100 | Finish domain repository ownership |
| T625 | Overview service, observation time, provider ports/types, market endpoints, 8 named test files | All market truth/cache/provider distinctions | T619/T621/T623 | Parallel T627/T628; before T626 | 1,200 | Split 359-function evidence hub |
| T626 | Scanner service/readiness/repo/endpoint and 5 named tests | Score/order/threshold/source/persistence | T623/T625 | Serial scanner/provider writer | 850 | Existing owners gain readiness/persistence |
| T627 | Backtest engine/service and 6 named golden/truth tests | All backtest truth/persistence | T624 | Parallel T625/T628 | 260 | Table-drive score-263 dispatch |
| T628 | Pipeline/renderer and 7 named tests | Accepted/completed, evidence, no-advice | T618 | Parallel T625/T627 | 540 | Explicit score-262/182 state tables |
| T629 | Topology, architecture manifest, integration-only tests/docs | All protected semantics/release provenance | T615/T621/T624/T626-T628 | Serial final join | 0 | Canonical integration proof |

### Delivery requirements per lane

| Task | Required tests | Canonical gate | QoderWork | GPT-5.6 / reasoning | Exact commit subject |
| --- | --- | --- | --- | --- | --- |
| T612 | 16 direct tests, import/registry, topology bootstrap | At T616 | No | `gpt-5.6-sol` / high | `refactor(research): remove inactive coverage island` |
| T613 | 11 direct tests, route/schema inventory, topology bootstrap | At T616 | No | `gpt-5.6-sol` / high | `refactor(api): remove unregistered contract islands` |
| T614 | Scaffold/middleware/notification/phase tests, topology bootstrap | At T616 | No | `gpt-5.6-sol` / high | `refactor(backend): remove inactive compatibility residue` |
| T615 | Operator smoke, no-live, agent registry/assets | Yes | Yes | `gpt-5.6-sol` / xhigh | `refactor(runtime): retire inline diagnostic paths` |
| T616 | All wave tests, topology, native guards | Yes, outside T566 | No | `gpt-5.6-sol` / high | `test(topology): integrate backend residue cleanup` |
| T617 | Config/runtime/system API/readiness | Yes before downstream | No | `gpt-5.6-sol` / xhigh | `refactor(config): make runtime settings authoritative` |
| T618 | Task/bot/lifespan/cache/provider isolation | Yes | Yes | `gpt-5.6-sol` / xhigh | `refactor(runtime): unify task and resource lifecycle` |
| T619 | Provider/no-live/injected/symbol/native guard | Yes | Yes | `gpt-5.6-sol` / xhigh | `refactor(provider): centralize construction and symbols` |
| T620 | Route/auth/canonical endpoint; T576 consumer proof | Yes | No | `gpt-5.6-sol` / high | `refactor(api): retire approved compatibility routes` |
| T621 | Public/admin/schema/response/error/secret/native guard | Yes | Yes | `gpt-5.6-sol` / xhigh | `refactor(api): unify projection and error boundaries` |
| T622 | Auth/RBAC/multi-user/storage/phase A-B | Yes | Yes | `gpt-5.6-sol` / xhigh | `refactor(storage): move identity persistence to repositories` |
| T623 | Storage/scanner/watchlist/history/phase C-D | Yes | Yes | `gpt-5.6-sol` / xhigh | `refactor(storage): move market persistence to repositories` |
| T624 | Portfolio/backtest/rule/phase E-G/real PG as required | Yes | Yes | `gpt-5.6-sol` / xhigh | `refactor(storage): finish domain repository ownership` |
| T625 | Market overview/freshness/provider/deadline/evidence | Yes | Yes | `gpt-5.6-sol` / xhigh | `refactor(market): separate overview evidence owners` |
| T626 | Scanner service/ops/API/source/persistence | Yes | Yes | `gpt-5.6-sol` / xhigh | `refactor(scanner): separate execution and readiness owners` |
| T627 | Golden/execution/reopen/universe/shadow parity | Yes | Yes | `gpt-5.6-sol` / xhigh | `refactor(backtest): table-drive signal dispatch` |
| T628 | Pipeline/report/no-advice/public safety | Yes | Yes | `gpt-5.6-sol` / xhigh | `refactor(analysis): make result states explicit` |
| T629 | Canonical gate, topology, architecture, approved external qualifications | Yes, sole final run | Yes | `gpt-5.6-sol` / xhigh | `test(backend): integrate simplification architecture gates` |

T612-T614 deliberately do not write topology. T616 joins them once, preventing
parallel edits to a protected authority. T622-T624 are serial because all write
`storage.py`. T619, T625, and T626 are ordered because their provider/source
owners overlap. T621 is serial because schemas and error projection are shared.
This is the maximum-safe plan, not merely the maximum number of processes.

## Validation evidence

Validation is intentionally audit-only. Full canonical gate, full backend
pytest, browser qualification, UAT, QoderWork, release-real-runtime, and any work
that could compete with T566 were not run.

The final validation ledger is recorded in the JSON artifact.

| Check | Result | Exact evidence |
| --- | --- | --- |
| JSON/schema/arithmetic assertion | PASS | 27 candidates, 18 lanes, all fields/enums; inventory 626/310,993; scenario totals 7,153/9,570/16,723; routes 278 |
| Native architecture debt check | PASS | All three families report `status: ok` |
| Runtime route/registry assertion | PASS | 278 operations: 267 public, 11 hidden, 0 mounted; method counts 9/175/3/87/4; no duplicate method/path |
| Direct topology `verify-all` | ENVIRONMENT RETRY REQUIRED, exit 2 | Direct process lacked the managed Chromium executable and explicitly required `./wolfy exec --profile test` |
| Managed topology `verify-all` | PASS | Backend 8,142, network 0, Vitest 176, Playwright 64 specs/718 cases |
| Roadmap/candidate literal-path assertion | PASS | Zero missing literal paths after nine draft corrections |
| `git diff --check` | PASS | Exit 0 with no whitespace errors after final artifact content |
| Changed-file allowlist | PASS | Exactly the two T575-authorized report paths |
| Repository changed-file secret scan | PASS | Two text files scanned; no high-confidence secret pattern |
| Focused private-path/key-pattern scan | PASS | No private absolute path or credential-shaped match |

Managed topology hashes are backend
`383fd5b6f7cab1c9a343fb92a50e887ee512f17edc76b7e758fad6f533247745`
and Vitest
`9330504ca244199783332967bb8a62e8a29425a98d30a4086b70452a54d37608`.
Playwright project cases are 357 Chromium, 357 Chromium mobile, and four
release-real-runtime inventory cases; tests were listed, not executed.

The route inventory import emitted LiteLLM debug messages indicating creation of
Aiohttp transport sessions. The inventory assertion passed, but T575 neither
sent network requests nor qualified that third-party lifecycle.

## Residual uncertainties and risk

- Static reachability cannot prove absence of external Python importers or
  undocumented `python -m module` operator calls. C006/C023/C024 remain medium
  confidence for this reason.
- The runtime route import emitted third-party LiteLLM/aiohttp diagnostics during
  inventory. The route result was available, but this audit did not attribute or
  repair third-party session lifecycle; no runtime qualification was attempted.
- Frontend absence is not product deprecation. T576 and an explicit product
  decision gate C015/C025.
- Exact topology deletion is unknown until shared test files are edited. Reported
  values are affected-file upper bounds and intentionally non-additive.
- Approximate complexity is an AST ranking heuristic. It identifies where to
  inspect; it does not prove semantic equivalence or an exact post-refactor score.
- The moderate and aggressive estimates are planning ranges, not promised net
  deletion. Only 7,153 LLOC is backed by exact high-confidence file/symbol
  arithmetic.
- Real PostgreSQL, real provider, browser, UAT, release, and QoderWork behavior is
  unverified by design in this audit.

## Rollback and push boundary

This audit's rollback boundary is the single documentation commit requested by
T575. After commit, the exact rollback command is `git revert <T575-commit-sha>`.
No push, merge, rebase, main-branch modification, or worktree cleanup is
authorized.
