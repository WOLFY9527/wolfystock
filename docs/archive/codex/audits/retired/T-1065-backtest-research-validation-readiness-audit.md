# T-1065 Backtest Research Validation Readiness Audit

Task ID: T-1065-AUDIT

Task title: Backtest research validation readiness audit

Mode: READ-ONLY-AUDIT with one explicitly allowed audit artifact.

Allowed artifact:

`docs/codex/audits/T-1065-backtest-research-validation-readiness-audit.md`

Observed workspace:

- cwd: `/Users/yehengli/worktrees/t1065-backtest-research-validation-readiness-audit`
- branch: `codex/t1065-backtest-research-validation-readiness-audit`
- base commit inspected: `950ec68aa415daa5f8531a78c33c61c4e870cde2`
- `origin/main` after `git fetch origin`: `2937600c5197586ac6cae1103a13123fb20244cc`
- branch relation after fetch: current branch is behind `origin/main` by 1 commit; no local ahead commits before this audit write.

Scope boundary:

- Source, tests, config, package, lockfile, frontend, backend, API, provider,
  cache, runtime, scanner, portfolio, options, and auth files were inspected
  only.
- This audit does not implement backtest features.
- This audit does not change engine math, fills, costs, metrics, stored result
  semantics, UI layout, report behavior, provider/cache behavior, or API
  behavior.
- Final diff is limited to this Markdown report.

## Executive Decision

Current backtest already has multiple research-validation scaffolds and read
surfaces. The important decision is not to build another parallel OOS,
heatmap, robustness, export, or execution-realism abstraction.

No implementation task is recommended from this audit. The safest next task is
one docs-only prerequisite:

**T-1065-D1: add a compact research-validation capability matrix to
`docs/backtest/README.md`.**

This keeps the future roadmap aligned with current code paths before any
protected-domain feature work starts. It must remain documentation-only.

Live trading integration and full event-driven backtesting are explicitly
deferred. Current evidence does not show safe scaffolding for broker routing,
live order placement, portfolio ledger execution, event queues, market-impact
simulation, or institutional fill modeling.

## Capability Matrix

| Capability | Current support | Evidence | Readiness conclusion |
| --- | --- | --- | --- |
| Walk-forward / out-of-sample validation | Partially supported as diagnostic replay. The service can build rolling walk-forward windows and rerun the same parsed strategy over test slices, but contract metadata marks the output diagnostic-only and not validated OOS strategy selection. | Runtime robustness is built in `src/services/rule_backtest_service.py:2196` and walk-forward generation starts at `src/services/rule_backtest_service.py:2310`. Guardrails set `parameter_selection_executed=false`, `parameter_sweep_executed=false`, `provider_calls_executed=false`, `portfolio_allocation_backtest_executed=false`, and `walk_forward_validation_claimed=false` at `src/services/rule_backtest_service.py:2280`. Stored OOS readiness export stays `stored_first` and `diagnostic_only` in `src/services/rule_backtest_support_exports.py:684`. | Do not add a second OOS abstraction. Treat current support as research diagnostics, not institutional OOS validation or model selection. |
| Parameter stability / heatmaps | Supported as stored compare/readback projections and pure helper scaffolds. There is no runtime optimizer, automatic grid-search execution, winner promotion, or live strategy selection. | Compare builds `heatmap_projection` and `parameter_stability_evidence` in `src/services/rule_backtest_service.py:956` and `src/services/rule_backtest_service.py:990`; heatmap projection is stored-first at `src/services/rule_backtest_service.py:4476`. Parameter stability evidence adapts stored compare payloads in `src/services/backtest_parameter_stability.py:255`; its metadata says caller-supplied results only, hidden optimizer false, and automatic winner promotion false at `src/services/backtest_parameter_stability.py:351`. API schema exposes the projection at `api/v1/schemas/backtest.py:1016`. Frontend compare renders the heatmap panel at `apps/dsa-web/src/components/backtest/RuleBacktestCompareHeatmapProjectionPanel.tsx:154`. | Do not build another heatmap or parameter-stability namespace. Future work must decide whether it wants a real optimizer; current heatmap is readback, not training. |
| Transaction cost and slippage modeling | Supported only as bounded per-side bps assumptions in the deterministic engine. A richer cost/capacity helper exists but is additive diagnostics and is not wired into default backtest math. | Engine accepts `fee_bps` and `slippage_bps` at `src/core/rule_backtest_engine.py:1302`; applies fee and slippage rates at `src/core/rule_backtest_engine.py:1415`; trade rows carry fee/slippage amounts at `src/core/rule_backtest_engine.py:1481`. The cost/capacity helper marks its scope `additive_diagnostic_helper_only` at `src/services/backtest_execution_cost_capacity.py:55` and says it is not wired into default math at `src/services/backtest_execution_cost_capacity.py:83`. Execution model semantics mark market impact, spread simulation, partial fills, and volume caps as unavailable or not modeled at `src/services/rule_backtest_execution_model_registry.py:91`. | Do not claim institutional execution realism. Any runtime cost-model expansion needs a new versioned execution model and golden fixture plan first. |
| Stress / Monte Carlo testing | Supported as runtime robustness reruns over repriced bars, plus stored-first export/readback. It remains diagnostic, not calibrated institutional stress testing. | Monte Carlo generation starts at `src/services/rule_backtest_service.py:2382`; stress test generation starts at `src/services/rule_backtest_service.py:2457`. The result export endpoint explicitly says robustness export will not rerun walk-forward, Monte Carlo, or stress calculations at `api/v1/endpoints/backtest.py:1013`. Fixture tests keep stress and Monte Carlo projections stored-only and non-promotional in `tests/test_backtest_stress_monte_carlo_readiness_contract.py:1`. | Existing capability is enough for research diagnostics. Do not add provider-backed replay, calibration, liquidity tail models, or regime-tail models without a new contract. |
| Portfolio / multi-asset rebalancing | Not supported. Universe jobs are local-only batch wrappers around single-symbol runs, not portfolio allocation, cross-symbol capital allocation, or multi-asset ledger backtests. | The engine is a deterministic long-only daily rule backtest at `src/core/rule_backtest_engine.py:1292`. Default execution model uses `single_position_full_notional` at `src/core/rule_backtest_engine.py:3277`. Universe job creation is local-data-only preflight at `src/services/rule_backtest_service.py:1058`; sequential execution remains local at `src/services/rule_backtest_service.py:1178`. API schema defaults universe jobs to `local_data_only=true` and `execution_mode=preflight_only` at `api/v1/schemas/backtest.py:472`. `docs/backtest/README.md:25` states universe jobs are not portfolio allocation. | Defer portfolio and multi-asset rebalancing. Do not repurpose universe jobs as a portfolio engine. |
| Performance / regime attribution | Core performance metrics exist. Regime attribution exists only as stored-first readiness/gap projection and drawdown/readback diagnostics, not validated PnL causality. | Metrics include total return, annualized return, Sharpe, benchmark/buy-and-hold comparison, win rate, and drawdown at `src/core/rule_backtest_engine.py:3848`. Regime attribution export sets `diagnosticOnly=true`, `engineReexecuted=false`, `attributionEngineAvailable=false`, and `pnlCausalityAvailable=false` at `src/services/rule_backtest_support_exports.py:493`. The endpoint description says it is not a runtime attribution engine at `api/v1/endpoints/backtest.py:1048`. `docs/backtest/regime-attribution-readiness-contract.md:9` states current regime surfaces are research/readback scaffolds only. | Keep regime attribution diagnostic until a source, as-of, join, benchmark, and daily PnL allocation contract is approved. |
| Test coverage and protected boundaries | Strong coverage exists for compute golden behavior, execution-model versioning, stored-first exports, API contracts, data-source authority, universe local-only behavior, frontend no-trading language, and compare heatmap rendering. | Golden compute tests are in `tests/test_rule_backtest_compute_golden.py:91`. Execution-model fixture and registry tests are in `tests/test_backtest_execution_model_versioning_contract.py:56` and `tests/test_backtest_execution_model_registry.py:51`. API support/export/OOS/parameter tests are in `tests/test_backtest_api_contract.py:1001`, `tests/test_backtest_api_contract.py:2645`, and `tests/test_backtest_api_contract.py:3273`. Data-source routing tests are in `tests/test_backtest_data_source_routing.py:15`. Frontend no-trading and report fail-closed tests are in `apps/dsa-web/src/pages/__tests__/BacktestPage.test.tsx:978`, `apps/dsa-web/src/components/backtest/__tests__/BacktestResultReport.test.tsx:425`, and `apps/dsa-web/e2e/backtest-visual-result.smoke.spec.ts:10`. | The next safe work should not start by expanding implementation. Preserve these boundaries and make the capability map easier to find. |

## Current User-Facing Capability

Backtest is a registered-user surface:

- `/backtest`, `/backtest/compare`, and `/backtest/results/:runId` are wrapped
  in `RegisteredSurfaceRoute` at `apps/dsa-web/src/App.tsx:404`,
  `apps/dsa-web/src/App.tsx:406`, and `apps/dsa-web/src/App.tsx:407`.
- Localized route variants are similarly protected at
  `apps/dsa-web/src/App.tsx:441`, `apps/dsa-web/src/App.tsx:443`, and
  `apps/dsa-web/src/App.tsx:444`.

Visible research controls and reports already include:

- fee/slippage assumptions in the Backtest run request path
  (`apps/dsa-web/src/pages/BacktestPage.tsx:1048`);
- optional Monte Carlo and walk-forward robustness controls in the Pro workflow
  with tests proving defaults are not sent unless enabled
  (`apps/dsa-web/src/pages/__tests__/BacktestPage.test.tsx:1441`,
  `apps/dsa-web/src/pages/__tests__/BacktestPage.test.tsx:1563`,
  `apps/dsa-web/src/pages/__tests__/BacktestPage.test.tsx:1593`);
- parameter, assumptions, robustness, stress, and support export read surfaces
  on result/report pages (`apps/dsa-web/src/pages/DeterministicBacktestResultPage.tsx:426`,
  `apps/dsa-web/src/components/backtest/BacktestSupportExportsDisclosure.tsx:230`);
- compare workbench heatmap and cost/slippage panels
  (`apps/dsa-web/src/pages/__tests__/RuleBacktestComparePage.test.tsx:450`).

The UI safety lane is also already protected:

- Backtest page copy says historical buy/sell labels do not place orders,
  connect to a broker, or change portfolio holdings
  (`apps/dsa-web/src/pages/BacktestPage.tsx:1351`).
- Result views label outputs as research simulation
  (`apps/dsa-web/src/components/backtest/DeterministicBacktestResultView.tsx:153`).
- Smoke/tests reject live trading, broker, and recommendation wording
  (`apps/dsa-web/e2e/backtest-visual-result.smoke.spec.ts:10`,
  `apps/dsa-web/src/components/backtest/__tests__/BacktestResultReport.test.tsx:440`).

## Duplicate-Feature Warnings

Do not add these as new abstractions without first proving the existing path is
insufficient:

- A second OOS or walk-forward adapter. Runtime robustness, pure OOS helper,
  stored robustness evidence, and OOS/parameter readiness export already exist.
- A second parameter stability or heatmap contract. Compare already returns
  `heatmap_projection` and `parameter_stability_evidence`, and the helper
  already supports caller-supplied stability surfaces.
- A second robustness report/export surface. `support_export_index`,
  `robustness_evidence_json`, `regime_attribution_readiness_json`,
  `execution_model_metadata_json`, and `oos_parameter_readiness_json` already
  exist.
- A second execution-cost helper. `backtest_execution_cost_capacity.py` already
  models richer diagnostic cost/capacity assumptions, but it is intentionally
  not default runtime math.
- A portfolio abstraction based on universe jobs. Current universe jobs are
  sequential single-symbol wrappers, not allocation or rebalancing engines.
- A merged abstraction across legacy historical evaluation and deterministic
  rule backtest. They remain different run and persistence lanes.

## Protected-Domain Warnings

The following areas are protected and must not change in the next task:

- backtest calculations, strategy math, fills, exposure formulas, costs,
  metrics, benchmarks, and persisted result semantics;
- execution model v1 semantics and unsupported future version fail-closed
  behavior;
- stored-first result authority, support exports, execution trace, comparison,
  and readback repair semantics;
- provider order, live-call paths, fallback behavior, freshness labels,
  MarketCache TTL/SWR/cold-start behavior, and cache payload meaning;
- scanner scoring/ranking, portfolio accounting, options ranking/gates, auth,
  notification routing, and API response shapes;
- consumer-facing no-advice and no-live-trading wording.

## Recommended Next Task

Exactly one next task is safe:

**T-1065-D1: add a canonical backtest research-validation capability matrix to
`docs/backtest/README.md`.**

Goal:

- Add a short matrix under the existing `Current Rules` section that summarizes
  the seven capability lanes from this audit.
- Link or name the existing implementation/test paths that already provide OOS,
  parameter stability, cost/slippage, robustness, support exports, universe
  jobs, execution-model metadata, and regime-attribution readiness.
- Add one duplicate-feature warning section that says future work must reuse
  existing scaffolds before adding new abstractions.
- Keep the README as a navigation/prerequisite document, not a feature spec.

Allowed future write files:

- `docs/backtest/README.md`

Forbidden future write files for T-1065-D1:

- source files under `src/`, `api/`, `data_provider/`, `bot/`, or scripts;
- tests under `tests/` or `apps/dsa-web/`;
- frontend files under `apps/dsa-web/` or `apps/dsa-desktop/`;
- config, dependency, package, lockfile, CI, Docker, provider/cache/runtime,
  scanner, portfolio, options, auth, and notification files.

Validation plan for T-1065-D1:

```bash
git diff --check -- docs/backtest/README.md
./scripts/release_secret_scan.sh
git status --short --branch
```

No full backend, frontend, or browser validation is required for that
docs-only task.

## Explicit Deferrals

Defer all of the following until a later task has an approved contract,
allowed files, and focused tests:

- live trading integration;
- broker connectivity or order placement;
- full event-driven backtesting;
- portfolio or multi-asset allocation/rebalancing;
- optimizer training, winner promotion, or automatic parameter selection;
- versioned execution-realism runtime changes;
- market impact, spread regimes, partial fills, taxes, halts, limit-up/down,
  exchange session, and volume participation runtime modeling;
- validated regime PnL attribution or benchmark-relative regime decomposition;
- provider-backed replay or live provider calls from research-validation tests.

## Final Audit Decision

Proceed only with the docs-only T-1065-D1 prerequisite. Do not open a backtest
feature implementation from this audit. Do not add another OOS, heatmap,
robustness, execution-cost, support export, portfolio, live trading, or
event-driven abstraction.

## Final Diff Confirmation For This Audit

- This T-1065 task is report-only.
- No source code changed.
- No tests changed.
- No config/package/lockfile changes.
- No frontend/backend/API/provider/cache/runtime/scanner/portfolio/options/auth
  behavior changed.
- No backtest engine, math, fills, costs, metrics, stored result semantics, UI
  layout, or report behavior changed.
