# Backtest Research Manual Validation Checklist

Status: T-217H smoke/checklist coverage for the T-217B-G research scaffolds.

This checklist is for diagnostic research helpers only:

- `backtest_walkforward_oos`
- `backtest_execution_cost_capacity`
- `backtest_parameter_stability`
- `backtest_factor_research_bridge`
- `backtest_reproducibility_manifest`

## What To Run

Run the focused smoke first:

```bash
python3 -m pytest tests/test_backtest_research_scaffold_smoke.py
```

Run the existing focused helper contracts when practical:

```bash
python3 -m pytest \
  tests/test_backtest_walkforward_oos_contract.py \
  tests/test_backtest_execution_cost_capacity.py \
  tests/test_backtest_parameter_stability_contract.py \
  tests/test_backtest_factor_research_bridge_contract.py \
  tests/test_backtest_reproducibility_manifest_contract.py
```

Optional local syntax / hygiene checks for this lane:

```bash
python3 -m py_compile tests/test_backtest_research_scaffold_smoke.py
git diff --check
./scripts/release_secret_scan.sh
```

## Expected Commands And Outcomes

- `tests/test_backtest_research_scaffold_smoke.py` should pass with pure fixture inputs only.
- The smoke is expected to import the five helper modules directly and exercise their public helper functions without provider calls, DB writes, API calls, or backtest engine math changes.
- The contract tests above should keep passing without changing existing backtest outputs.

## Diagnostic-Only Meaning

- Walk-forward output is a diagnostic rolling-window scaffold, not optimizer training or live OOS winner selection.
- Execution cost / capacity output is additive diagnostics only. It does not rewrite the stored rule backtest result or change engine fills by itself.
- Parameter stability output is a caller-supplied result aggregation surface, not a hidden grid-search runner.
- Factor research bridge output is an offline input bridge, not a runtime backtest launcher.
- Reproducibility manifest output is metadata / fingerprint packaging, not a replay engine.

## Not Real Runtime Integration

The following are explicitly out of scope for this checklist:

- live provider hydration
- database persistence or migrations
- API route wiring
- frontend or operator UI behavior
- scanner, portfolio, MarketCache, options, auth, RBAC, or LLM integration
- deterministic backtest engine math changes

## Do Not Manually Test As Live Trading Or Real Backtest Execution

Do not treat this checklist as evidence for:

- live trading readiness
- broker or order-routing execution
- portfolio allocation backtests
- production OOS model selection
- parameter auto-tuning or strategy promotion
- end-to-end rule backtest runtime integration

If you need those behaviors, use the canonical backtest runtime lanes and their dedicated validation paths instead of this scaffold-only checklist.
