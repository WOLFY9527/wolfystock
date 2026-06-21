# DATA-031 Backtest Professional Upgrade Audit

Task ID: DATA-031
Date: 2026-06-21
Scope: WolfyStock backtesting, factor research, DuckDB diagnostics, API/schema surfaces, frontend surfaces, and tests.

## 1. Executive verdict

Current maturity level: research-useful.

WolfyStock cannot replace paid professional backtest websites today. It has a deterministic single-symbol rule engine, stored readback, execution trace exports, local-only universe batches, basic robustness diagnostics, and offline factor research helpers. Those are useful for personal research and implementation validation, but they are not a professional-grade backtesting platform.

Main reason: the runtime still lacks professional data and execution contracts. Current rule backtests use available local bars, close-signal / next-open fills, single long exposure, bps fee/slippage assumptions, and diagnostic-only support projections. The system explicitly reports research-prototype readiness instead of professional quant readiness (`src/services/backtest_professional_readiness.py:41`, `docs/backtest-system.md`, `docs/audits/backtest-quant-capability-audit.md`).

The fastest path is not to relabel current outputs. The fastest path is to productize one bounded research workflow at a time while preserving hard fail-closed language for adjusted data, corporate actions, calendars, point-in-time membership, survivorship control, impact, partial fills, and portfolio allocation.

## 2. Current capability inventory

### Standard historical analysis evaluation

Implemented, but legacy and not a strategy engine. `BacktestService.run_backtest()` evaluates stored `AnalysisHistory` snapshots against later bars (`src/services/backtest_service.py:69`, `src/services/backtest_service.py:203`). Its result payload marks `evaluation_mode: historical_analysis_evaluation` and records the window/source assumptions (`src/services/backtest_service.py:377`). This is useful for checking historical analysis quality, not for deterministic strategy simulation.

### Deterministic single-symbol rule backtest

Implemented and research-useful. `RuleBacktestEngine.run()` executes supported single-symbol rule strategies over daily bars (`src/core/rule_backtest_engine.py:1292`). The engine routes supported strategy families (`src/core/rule_backtest_engine.py:1308`), rejects empty/invalid bars fail-closed (`src/core/rule_backtest_engine.py:1361`), fills pending entries/exits on next bar open with bps fee/slippage assumptions (`src/core/rule_backtest_engine.py:1437`), and forces a terminal close when needed (`src/core/rule_backtest_engine.py:1590`). It builds benchmark and buy-and-hold comparison outputs (`src/core/rule_backtest_engine.py:1667`).

Professional limitation: this is a v1 deterministic single-symbol long-only engine, not a portfolio allocator, optimizer, volume-aware execution simulator, or institutional execution model (`docs/backtest/README.md`, `docs/backtest/execution-model-versioning-contract.md`).

### Universe backtest

Implemented as a local-only research batch. The API can create a local universe job and then run it sequentially without provider calls (`api/v1/endpoints/backtest.py:647`, `api/v1/endpoints/backtest.py:683`). Diagnostics expose compact job-level summaries, reason buckets, performance leaders, and local data coverage (`api/v1/endpoints/backtest.py:733`). Service diagnostics explicitly mark `local_only`, no live provider calls, and no concurrency (`src/services/rule_backtest_service.py:1483`).

Professional limitation: this is not point-in-time universe research and not a portfolio-level allocation backtest. It runs per-symbol rule backtests over available local daily data.

### Stored run readback

Implemented. Rule runs have history, detail, status, compare, and export endpoints (`api/v1/endpoints/backtest.py:800`, `api/v1/endpoints/backtest.py:847`, `api/v1/endpoints/backtest.py:871`, `api/v1/endpoints/backtest.py:824`). Schemas carry metrics, execution assumptions, benchmark curves, audit rows, stored readiness fields, equity curves, trades, and execution trace (`api/v1/schemas/backtest.py:1147`, `api/v1/schemas/backtest.py:1215`).

Professional limitation: stored readback is strong for reproducibility and support, but it only preserves the current v1 assumptions unless richer data/execution contracts are added.

### Execution trace

Implemented. Stored rule runs can export execution trace JSON and CSV (`api/v1/endpoints/backtest.py:980`, `api/v1/endpoints/backtest.py:1139`). The response schema includes trace rows, assumptions, execution model, benchmark summary, and fallback metadata (`api/v1/schemas/backtest.py:1311`). The frontend renders a key-checkpoint trace preview and full trace/export controls (`apps/dsa-web/src/components/backtest/ExecutionTracePanel.tsx:55`, `apps/dsa-web/src/components/backtest/ExecutionTracePanel.tsx:103`).

Professional limitation: the trace explains v1 decisions; it does not imply volume-aware fills, market-impact modeling, or exchange-session realism.

### Robustness evidence

Implemented as stored diagnostic evidence. Rule runs can export stored robustness evidence without re-executing calculations (`api/v1/endpoints/backtest.py:1016`). The service builds walk-forward, Monte Carlo, and stress diagnostics and records contract metadata that keeps the output diagnostic-only (`src/services/rule_backtest_service.py:2236`). Monte Carlo uses synthetic repriced paths for robustness probing and must not be presented as real historical bars (`src/services/rule_backtest_service.py:2422`).

Professional limitation: robustness evidence is not a professional validation suite. It is not a training loop, parameter-selection engine, or investable evidence package.

### Walk-forward / OOS diagnostics

Implemented as scaffolds and stored adapters. The service's walk-forward analysis replays the same parsed strategy over rolling windows (`src/services/rule_backtest_service.py:2350`). The standalone OOS helper states that it is diagnostic-only, not an optimizer, not a parameter sweep, and does not change engine/provider behavior (`src/services/backtest_walkforward_oos.py:52`, `src/services/backtest_walkforward_oos.py:252`).

Professional limitation: there is no training stage, no OOS winner selection, no nested cross-validation, and no promotion path from OOS diagnostics to executable strategy configuration.

### Parameter stability / grid helpers

Implemented as diagnostic helpers, not as a product-grade parameter sweep surface. The parameter-stability module can build deterministic plans and aggregate caller-supplied results (`src/services/backtest_parameter_stability.py:71`, `src/services/backtest_parameter_stability.py:177`). Its metadata explicitly says diagnostic only, no optimizer, no winner promotion, no live strategy selection, and no provider/runtime/portfolio changes (`src/services/backtest_parameter_stability.py:375`). The bounded grid runner can execute a small caller-supplied bar bundle through the v1 engine and returns runner-local evidence only (`src/services/backtest_bounded_grid_runner.py:23`, `src/services/backtest_bounded_grid_runner.py:96`).

Professional limitation: no public stored parameter-sweep workflow exists for users; current compare heatmaps are stored-run projections and not an execution grid (`api/v1/schemas/backtest.py:1028`, `api/v1/schemas/backtest.py:1044`).

### Factor metrics

Implemented as offline deterministic helpers. `build_factor_metrics_report()` computes IC, Rank IC, decay, turnover, and peer correlations from in-memory observations and forward returns (`src/services/factor_metrics.py:31`, `src/services/factor_metrics.py:48`). Contract tests cover IC/Rank IC/decay/turnover/correlation behavior and insufficient-data states (`tests/test_factor_metrics_contract.py:82`).

Professional limitation: these helpers require caller-supplied factor observations and forward returns. They do not yet provide a production factor panel, factor backtest, or long-short return series from point-in-time datasets.

### Factor exposure

Implemented as offline exposure helpers. Weighted portfolio exposure and long-short basket exposure reports are built from supplied observations and weights (`src/services/factor_exposure.py:86`, `src/services/factor_exposure.py:155`). Tests cover weighted exposure, missing observations, invalid weights, long-short basket exposure, neutralized values, deterministic order, and no runtime side effects (`tests/test_factor_exposure_contract.py:57`).

Professional limitation: exposure reports are analysis artifacts, not attribution or portfolio-rebalance backtests.

### Factor registry

Implemented as a deterministic static seed registry. It contains built-in factor definitions and explicitly avoids importing scanner/backtest/portfolio/provider services or storage (`src/services/factor_registry.py:2`, `src/services/factor_registry.py:15`, `src/services/factor_registry.py:119`). Tests lock expected families and no runtime side effects (`tests/test_factor_registry_contract.py:25`).

Professional limitation: the registry is metadata only. It is not a governed factor library with versioned production formulas, panel lineage, or runtime factor materialization.

### Factor neutralization

Implemented as offline residual helpers. The service builds sector-neutral and market-cap-bucket-neutral residual reports from fixture or in-memory rows (`src/services/factor_neutralization.py:75`, `src/services/factor_neutralization.py:90`). Tests cover residuals, deterministic buckets, missing metadata, insufficient group size, and side-effect-free imports (`tests/test_factor_neutralization_contract.py:26`).

Professional limitation: neutralization exists for supplied rows only. It is not integrated into a factor portfolio construction or live panel-generation workflow.

### DuckDB factor diagnostics

Implemented as optional admin-invoked diagnostics. `QuantDuckDBService` is disabled by default and explicitly optional (`src/services/quant_analytics/duckdb_service.py:19`, `src/services/quant_analytics/duckdb_service.py:62`). It can initialize `ohlcv_daily` and `factor_daily`, ingest bounded OHLCV rows, build basic daily factors, return coverage, snapshots, runtime-context comparison, and benchmark diagnostics (`src/services/quant_analytics/duckdb_service.py:102`, `src/services/quant_analytics/duckdb_service.py:170`, `src/services/quant_analytics/duckdb_service.py:305`, `api/v1/endpoints/quant.py:41`, `api/v1/endpoints/quant.py:98`, `api/v1/endpoints/quant.py:139`).

Professional limitation: docs state this optional engine does not replace PostgreSQL, the scanner, the backtest engine, the provider layer, or production decision paths (`docs/quant-duckdb-engine.md`). It is currently diagnostics and acceleration scaffolding, not a backtest source of truth.

### Frontend backtest surfaces

Implemented surfaces include:

- Backtest page with historical and rule modules plus normal/professional control modes (`apps/dsa-web/src/pages/BacktestPage.tsx:54`, `apps/dsa-web/src/pages/BacktestPage.tsx:1480`, `apps/dsa-web/src/pages/BacktestPage.tsx:1540`, `apps/dsa-web/src/pages/BacktestPage.tsx:1566`).
- Normal backtest workspace for quick single-symbol rule research setup (`apps/dsa-web/src/components/backtest/NormalBacktestWorkspace.tsx:51`).
- Professional workspace with symbol, strategy, orders, costs, and advanced diagnostics steps (`apps/dsa-web/src/components/backtest/ProBacktestWorkspace.tsx:325`).
- Explicit planned labels for portfolio shell and rebalance cadence; current runs still execute one parsed strategy per symbol (`apps/dsa-web/src/components/backtest/ProBacktestWorkspace.tsx:564`).
- Execution trace, support exports, drawdown diagnostics, and run comparison panels (`apps/dsa-web/src/components/backtest/BacktestAuditTables.tsx:333`, `apps/dsa-web/src/components/backtest/BacktestAuditTables.tsx:753`, `apps/dsa-web/src/components/backtest/BacktestAuditTables.tsx:807`).

Professional limitation: the UI exposes useful controls and readback, but it does not yet provide public factor-combination backtests, parameter-sweep execution, point-in-time universe construction, portfolio allocation, or attribution workflows.

## 3. Professional quant gap matrix

| Professional capability | Current status | Blocks professional claim | Evidence |
| --- | --- | --- | --- |
| Adjusted OHLC / total return data | Not implemented as a trusted runtime contract. DuckDB schema has `adj_close`, but readiness still fails closed without explicit adjusted basis. | Yes | `src/services/backtest_professional_readiness.py:201`, `src/services/quant_analytics/duckdb_service.py:113` |
| Corporate action lineage | Not ready. Readiness requires dividend/split policy and blocks professional claims when missing. | Yes | `src/services/backtest_professional_readiness.py:247` |
| Exchange calendar / holidays / half-days / suspensions | Not ready. Current v1 uses available bars; readiness requires calendar, holiday, and half-day evidence. | Yes | `src/services/backtest_professional_readiness.py:281`, `docs/backtest/README.md` |
| A-share T+1, price-limit rules, stamp duty | Not implemented in runtime execution model. Future v2 execution model is required for market-specific realism. | Yes | `docs/backtest/execution-model-versioning-contract.md`, `docs/backtest/transaction-cost-slippage-readiness.md` |
| US equity cost/slippage model | Baseline fee/slippage bps only. No NBBO/spread regime/venue model. | Yes | `src/core/rule_backtest_engine.py:1437`, `src/services/backtest_professional_readiness.py:366` |
| Partial fills / volume participation / liquidity cap | Diagnostic helper exists, default engine does not enforce it. | Yes | `src/services/backtest_execution_cost_capacity.py:74`, `src/services/backtest_professional_readiness.py:319` |
| Market impact / spread model | Spread helper exists in diagnostic cost helper; impact is not runtime-modeled. | Yes | `src/services/backtest_execution_cost_capacity.py:11`, `src/services/backtest_professional_readiness.py:366` |
| Benchmark alignment | Basic benchmark and buy-and-hold comparisons exist. Professional alignment by calendar, rebalance convention, and total-return benchmark is incomplete. | Partial blocker | `src/core/rule_backtest_engine.py:1667`, `api/v1/schemas/backtest.py:1182` |
| Point-in-time universe membership | Not available. Current universe jobs are local-only per-symbol batches, not point-in-time membership panels. | Yes | `docs/backtest/pit-universe-adjusted-data-readiness.md`, `api/v1/endpoints/backtest.py:647` |
| Survivorship bias control | Not available as a runtime guarantee. Readiness and provenance helpers keep it blocked. | Yes | `src/services/backtest_data_provenance_projection.py:19`, `tests/test_backtest_pit_universe_adjusted_data_readiness_contract.py:138` |
| Anti-leakage controls | Basic date-window guards and diagnostic OOS scaffolds exist; no full dataset as-of contract or factor-panel leak checks. | Yes | `src/services/backtest_professional_readiness.py:41`, `src/services/backtest_walkforward_oos.py:52` |
| Dataset lineage / reproducibility | Stored support manifests exist, but dataset version/source authority remains partial and not enough for professional claims. | Yes | `api/v1/schemas/backtest.py:1268`, `src/services/backtest_professional_readiness.py:418` |
| Parameter sweep | Internal bounded runner and stability helpers exist, but no public stored sweep workflow. | Yes for paid-site replacement | `src/services/backtest_bounded_grid_runner.py:23`, `src/services/backtest_parameter_stability.py:71` |
| Walk-forward training and OOS selection | Diagnostic windows exist; no training, optimizer, or OOS selection. | Yes | `src/services/backtest_walkforward_oos.py:52`, `src/services/rule_backtest_service.py:2350` |
| Factor IC / Rank IC / IR | IC and Rank IC exist offline. IR is not a first-class product output. | Partial blocker | `src/services/factor_metrics.py:48`, `tests/test_factor_metrics_contract.py:82` |
| Factor bucket returns | Factor research bridge can build score buckets, but not realized bucket return portfolios from a point-in-time panel. | Yes | `src/services/backtest_factor_research_bridge.py:291` |
| Factor long-short portfolio | Exposure helper can summarize long/short baskets; no long-short return portfolio backtest. | Yes | `src/services/factor_exposure.py:155` |
| Factor neutralization | Offline helper exists; not integrated into factor backtest construction. | Partial blocker | `src/services/factor_neutralization.py:75` |
| Portfolio-level allocation backtest | Not implemented. UI labels portfolio shell and rebalance cadence as planned. | Yes | `apps/dsa-web/src/components/backtest/ProBacktestWorkspace.tsx:564` |
| Attribution and exposure decomposition | Exposure helper and drawdown readiness panels exist; no causal PnL attribution or exposure decomposition engine. | Yes | `src/services/factor_exposure.py:86`, `docs/backtest/regime-attribution-readiness-contract.md` |

## 4. What to build next

| Task id | Product-visible outcome | Allowed edit scope | Conflict risk | Validation profile | Parallelizable | Protected backtest domain |
| --- | --- | --- | --- | --- | --- | --- |
| BTP-001 | Public, stored single-symbol parameter sweep pilot that runs bounded parameter grids, stores sweep identity, and shows diagnostic heatmaps without winner promotion. | `src/services/*backtest*`, `src/repositories/*backtest*`, `api/v1/endpoints/backtest.py`, `api/v1/schemas/backtest.py`, `apps/dsa-web/src/api/backtest.ts`, `apps/dsa-web/src/types/backtest.ts`, focused backtest tests/docs. | Medium: API/schema plus run storage. | Backend contract tests, golden fixture update, frontend API/unit tests, no-advice grep. | Can run mostly serial; UI read-only display can follow after API contract lands. | Yes, but should avoid changing v1 engine math. |
| BTP-002 | Dataset lineage gate visible on every rule run: adjusted basis, corporate action status, calendar status, source authority, dataset version, and explicit blocker chips. | `src/services/backtest_*readiness*`, `src/services/backtest_data_provenance_projection.py`, schemas/endpoints/readback UI/tests/docs. | Medium: shared readback contract. | Contract tests for fail-closed states, golden support manifest tests, UI tests for product-safe copy. | Parallel with BTP-004 after schema shape freezes. | Yes, metadata/readback only. |
| BTP-003 | Exchange-calendar readiness foundation: per-market session calendar evidence, half-day/holiday/suspension blockers, and run-window alignment diagnostics. | New or existing calendar service, backtest readiness projection, rule run data quality/readback tests/docs. | High: market data semantics and future runtime dependency. | Calendar fixture tests, readiness tests, no runtime math change tests, docs update. | Not parallel with execution-model work until contract is stable. | Yes. |
| BTP-004 | Cost/capacity diagnostic product surface: volume participation, partial/no-fill diagnostics, spread/cost summary, and explicit "not default engine math" copy. | Existing cost-capacity helper, support export/readback/UI/tests. | Low-medium: additive diagnostic surface. | Helper tests, readback tests, UI disclosure tests, golden no-math-change fixture. | Yes, after BTP-002 or independent if no schema conflict. | Yes, diagnostic only. |
| BTP-005 | Factor research report surface: IC, Rank IC, turnover, decay, exposure, neutralization, missing-data states, and reproducibility manifest for supplied factor panels. | `src/services/factor_*`, `api/v1/schemas/factors.py`, factor endpoints if present/new, frontend factor report UI, factor tests/docs. | Medium: new user-facing factor contract. | Factor contract tests, API schema tests, UI tests, no-advice grep. | Parallel with BTP-001 if API ownership is separated. | No direct engine math, but factor-backtest boundary must stay observe-only. |
| BTP-006 | Factor bucket and long-short return prototype using explicit caller-supplied forward returns and no provider fallback. | Factor research services/schemas/API/tests/docs; no rule engine mutation. | Medium: easy to overclaim. | Golden fixtures for bucket/long-short calculations, leak guard tests, fail-closed missing forward return tests. | Parallel with BTP-003 if endpoint ownership is separate. | Adjacent protected factor/backtest domain. |
| BTP-007 | Point-in-time universe dataset contract and local fixture runner: membership snapshots, delisting markers, as-of dates, survivorship blocker evidence. | New dataset contract docs/fixtures/services/tests; later API readback. | High: foundational data contract. | PIT fixture tests, survivorship fail-closed tests, provenance tests, no provider fallback tests. | Should be serial until contract stabilizes. | Yes. |
| BTP-008 | Portfolio allocation backtest v0 contract: rebalance schedule, weights, cash accounting, position ledger, benchmark alignment, and explicit exclusions. | New portfolio backtest design doc first; later isolated services/schemas/tests. | High: touches portfolio ledger semantics if implemented naively. | Design review, ledger invariant tests, golden fixtures, no-advice grep. | Not parallel with BTP-001 unless strictly doc-only/design-only. | Yes, protected domain and portfolio ledger boundary. |
| BTP-009 | Execution model v2 design and fail-closed registry: spread, impact, partial fills, market-specific fees, session rules, and versioned response metadata. | Execution model registry/contracts/docs/tests before runtime math. | High: future math contract. | Registry resolver tests, unsupported-v2 fail-closed tests, docs, no engine default change. | Serial. | Yes. |

## 5. Recommended first implementation task

Recommended next code task: BTP-001, public stored single-symbol parameter sweep pilot.

Why this first:

- It is the fastest high-value product step because bounded grid execution and parameter stability helpers already exist (`src/services/backtest_bounded_grid_runner.py:23`, `src/services/backtest_parameter_stability.py:71`).
- It directly addresses one paid-site replacement expectation: parameter sweeps.
- It can preserve the current v1 rule-engine math and avoid adjusted-data or execution-realism overclaims.
- It creates a reusable storage/API/UI pattern for later walk-forward selection and factor-combination experiments.

Acceptance boundary for BTP-001:

- User can launch a bounded parameter grid for one symbol and one supported strategy family.
- The response and readback clearly say diagnostic parameter sweep, not optimizer and not professional-ready evidence.
- Grid overflow, unsafe parameter paths, missing local bars, unsupported strategies, and missing metrics fail closed.
- Stored sweep readback includes parameter set identity, result metrics, skipped cases, engine version, dataset metadata, and warnings.
- No row promotes a best configuration as an instruction to act in markets.

## 6. Safety constraints

Future backtest upgrades must keep these constraints hard:

- Fake performance: never fill missing results, benchmark values, factor returns, run metrics, or attribution values with placeholders that look real.
- Synthetic historical bars: stress or Monte Carlo paths must be labeled synthetic diagnostic paths and must never be presented as historical market bars.
- Hidden provider fallback: professional-readiness, universe, parameter sweep, and factor workflows must record whether data came from local approved datasets and must not silently hydrate missing bars from live providers.
- Lookahead bias: every factor observation, universe membership row, benchmark value, corporate-action adjustment, and forward-return label needs an explicit as-of boundary.
- Survivorship bias: universe tests and factor panels must not claim professional readiness without delisted members, membership history, and unavailable-member accounting.
- Unsupported professional-ready claims: UI/API/docs must continue to say research, diagnostic, or prototype when any required data, calendar, execution, or reproducibility contract is missing.
- Trading advice: backtest outputs must stay research observations. They must not contain personalized trade-action copy, price-objective copy, risk-order instructions, or position-sizing instructions.

## Evidence note

Read-only subagent dispatch was attempted for the requested mapping lanes, but the upstream agent service disconnected before completing. The audit above was completed by the main agent using direct read-only repository inspection across docs, services, schemas, endpoints, frontend surfaces, and tests.
