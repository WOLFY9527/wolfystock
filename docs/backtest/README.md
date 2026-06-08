# WolfyStock Backtest Docs

Status: current backtest domain entry point.

Use this lane before changing deterministic backtest, rule backtest, helper
maintenance, backtest result UI, stored-first result readback, or backtest
public-safety wording.

## Current Authority

- [Backtest System](../backtest-system.md)
- [Backtest Research Manual Validation Checklist](./manual-validation-checklist.md)
- [Backtest Helper Maintenance](../backtest-helper-maintenance.md)
- [Backtest Universe Rules](../codex/WOLFYSTOCK_BACKTEST_UNIVERSE_RULES.md)
- [Rule Backtest Reopen Trustworthiness Status](../architecture/rule-backtest-reopen-trustworthiness-p0-status-index-2026-04-22.md)
- [Backtest Quant Capability Audit](../audits/backtest-quant-capability-audit.md)
- [Backtest / Portfolio Public Safety Audit](../audits/backtest-portfolio-public-safety-audit.md)
- [Backtest Factor Lab Readiness Contract](./factor-lab-readiness-contract.md)
- [Frontend Visual System](../frontend/visual-system.md)

## Helper Contract Index

- [Backtest Factor Lab Readiness Contract](./factor-lab-readiness-contract.md)
  - Observe-only metadata helper; no engine, provider, cache, DB, API, or
    frontend wiring.
- [Backtest Factor Lab Readiness Fixtures](./factor-lab-readiness-fixtures.md)
  - Fixture catalog for caller-supplied readiness states only; not runtime or
    professional-readiness proof.
- [Backtest Helper Maintenance](../backtest-helper-maintenance.md)
  - Maintenance boundary reference for additive helpers; do not widen into
    calculation/runtime changes from this entry.
- `tests/test_backtest_factor_lab_readiness_contract.py`
  - Pure-helper contract coverage.
- `tests/test_backtest_factor_lab_readiness_fixtures.py`
  - Readiness fixture coverage.
- `tests/test_pure_helper_import_boundaries.py`
  - Import-boundary guard for inert helper modules.

## Current Rules

- Standard historical evaluation and deterministic rule backtest are different
  contract lanes. `POST /api/v1/backtest/run` evaluates stored historical
  analysis snapshots against later market bars; `POST /api/v1/backtest/rule/run`
  runs the deterministic single-symbol rule strategy engine.
- Universe jobs are batch research wrappers around the existing single-symbol
  rule engine. They emit sequential per-symbol compact rows, not portfolio
  allocation, cross-symbol capital allocation, or multi-asset ledger backtests.
- Walk-forward and compare heatmap outputs are diagnostic read surfaces. Current
  walk-forward replays the same parsed strategy on rolling windows; current
  heatmap is a stored compare projection derived from persisted compare payloads.
  Neither surface performs optimizer training, OOS model selection, parameter
  sweeps, or grid-search execution.
- Parameter stability helpers are additive scaffolds only. They can plan a
  deterministic parameter grid and aggregate caller-supplied evaluation results
  into a stability surface, but they do not execute rule runs, promote winners,
  select live strategies, change engine math, call providers, or simulate
  portfolio allocation.
- Backtest + Factor Lab readiness packets are observe-only metadata helpers.
  They aggregate caller-supplied readiness/factor/bridge/lineage evidence into
  a fail-closed research-readiness view and do not run engines, call providers,
  touch storage, or change stored semantics.
- Support exports are stored-first contract artifacts. The current export set is
  `support_bundle_manifest_json`,
  `support_bundle_reproducibility_manifest_json`, `execution_trace_json`,
  `execution_trace_csv`, `robustness_evidence_json` when stored robustness
  evidence exists, `regime_attribution_readiness_json` as a stored
  diagnostic/readiness projection rather than validated institutional PnL
  attribution, `execution_model_metadata_json` as a read-only v1 execution
  model metadata projection, and `oos_parameter_readiness_json` as a
  diagnostic-only stored-first OOS/parameter-readiness projection. That
  metadata export documents the current/default rule backtest execution
  assumptions and guardrails only; the OOS/parameter export only re-exposes
  stored walk-forward robustness evidence plus caller-supplied compare/parameter
  evidence when present, and otherwise keeps the missing side explicit as
  partial/unavailable. Neither export implies market impact, spread simulation,
  partial fills, PIT universe guarantees, or decision-grade institutional
  execution realism.
- Backtest pages lead with result, risk metrics, assumptions, and evidence
  quality before export, rerun, trace, ledger, or raw controls.
- Execution assumptions and data quality can be professional evidence when
  summarized; raw trace/ledger details stay collapsed.
- Backtest UI and docs must not imply broker/order execution.
- Backtest calculations and stored result semantics are protected runtime
  behavior.

## Research Validation Capability Matrix

Use this matrix before opening any backtest research-validation task. It is a
boundary map for existing scaffolds, not a feature roadmap.

| Lane | Current status | Existing boundary | Future-work instruction |
| --- | --- | --- | --- |
| Walk-forward / out-of-sample validation | Diagnostic/readback-only | Runtime walk-forward replays the same parsed strategy across rolling windows; stored OOS/parameter readiness exports are diagnostic and do not claim validated model selection. | Do not add a parallel OOS adapter. Reuse current robustness/OOS readiness surfaces unless a later contract explicitly approves real optimizer training and OOS selection. |
| Parameter stability / heatmaps | Diagnostic/readback-only | Compare payloads expose `heatmap_projection` and `parameter_stability_evidence`; helper logic can aggregate caller-supplied results but does not execute grid searches or promote winners. | Do not add a parallel heatmap or parameter-stability namespace. Treat current heatmaps as stored compare projections, not training output. |
| Transaction cost and slippage modeling | Implemented with bounded assumptions; richer modeling deferred | The deterministic rule engine supports bounded per-side `fee_bps` and `slippage_bps`; cost/capacity helpers are additive diagnostics and are not default runtime math. | Do not add a duplicate execution-cost model. Any execution-realism expansion needs a versioned execution model and fixture plan first. |
| Stress / Monte Carlo | Diagnostic/readback-only | Robustness reruns and stored-first support exports cover stress and Monte Carlo evidence when available; exports do not rerun calculations. | Do not add duplicate robustness exports. Keep provider-backed replay, calibration, liquidity tails, and regime-tail modeling deferred. |
| Portfolio / multi-asset rebalancing | Not supported | Universe jobs are sequential single-symbol research wrappers over the existing rule engine. They are not portfolio allocation, rebalancing, or multi-asset ledger backtests. | Do not treat universe jobs as portfolio rebalancing. Portfolio and multi-asset allocation remain deferred. |
| Performance / regime attribution | Implemented core metrics; regime attribution diagnostic/readback-only | Core return/risk metrics exist. Regime attribution surfaces are stored-first readiness/gap projections and do not prove daily PnL causality. | Keep attribution diagnostic until a source, as-of join, benchmark, and PnL allocation contract is approved. |
| Current test/protected-boundary status | Protected | Existing tests cover golden compute behavior, execution-model metadata, stored-first exports, API/readback contracts, universe local-only behavior, and no-trading language. | Future prompts must preserve backtest calculations, fills, costs, metrics, stored result semantics, no-advice copy, and protected readback authority. |

## Duplicate-Feature Warnings

- Do not add parallel OOS, walk-forward, or OOS-readiness abstractions.
- Do not add parallel heatmap or parameter-stability abstractions.
- Do not add duplicate robustness, support-export, or readback export surfaces.
- Do not add a duplicate execution-cost model beside the existing bounded
  fee/slippage assumptions and diagnostic cost/capacity helper.
- Do not treat universe jobs as portfolio allocation or rebalancing.
- Do not merge legacy historical evaluation and deterministic rule backtest
  abstractions; they remain separate contract lanes.
- Defer live trading integration, broker connectivity, order placement, and
  full event-driven backtesting until a later approved contract scopes them.
