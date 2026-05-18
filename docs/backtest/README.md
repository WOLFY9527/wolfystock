# WolfyStock Backtest Docs

Status: current backtest domain entry point.

Use this lane before changing deterministic backtest, rule backtest, helper
maintenance, backtest result UI, stored-first result readback, or backtest
public-safety wording.

## Current Authority

- [Backtest System](../backtest-system.md)
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
- Support exports are stored-first contract artifacts. The current export set is
  `support_bundle_manifest_json`,
  `support_bundle_reproducibility_manifest_json`, `execution_trace_json`,
  `execution_trace_csv`, and `robustness_evidence_json` when stored robustness
  evidence exists.
- Backtest pages lead with result, risk metrics, assumptions, and evidence
  quality before export, rerun, trace, ledger, or raw controls.
- Execution assumptions and data quality can be professional evidence when
  summarized; raw trace/ledger details stay collapsed.
- Backtest UI and docs must not imply broker/order execution.
- Backtest calculations and stored result semantics are protected runtime
  behavior.
