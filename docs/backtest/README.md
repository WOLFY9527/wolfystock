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
- [Frontend Visual System](../frontend/visual-system.md)

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
