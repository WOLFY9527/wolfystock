# Portfolio Research Smoke Checklist

Status: advisory-only manual validation for read-only Portfolio Research helpers.

Scope:
- portfolio construction advisory read model
- current rebalance advisory read surface via `PortfolioConstructionReadModelService`
- portfolio factor exposure
- portfolio risk attribution
- portfolio stress / VaR

Run:

```bash
python3 -m pytest tests/test_portfolio_research_smoke_checklist.py -q
python3 -m pytest \
  tests/test_portfolio_construction_read_model.py \
  tests/test_portfolio_factor_exposure_read_model.py \
  tests/test_portfolio_risk_attribution_read_model.py \
  tests/test_portfolio_stress_risk_read_model.py -q
python3 -m py_compile \
  src/services/portfolio_construction_service.py \
  src/services/portfolio_factor_exposure.py \
  src/services/portfolio_risk_attribution.py \
  src/services/portfolio_stress_risk.py \
  tests/test_portfolio_research_smoke_checklist.py
git diff --check
./scripts/release_secret_scan.sh
```

Expected commands:
- Run the smoke test first to verify the fixture-style composition path stays read-only.
- Run the existing portfolio read-model contract tests next.
- Run `python3 -m py_compile` only for changed Python files.
- Run `git diff --check` before completion to catch whitespace or patch formatting regressions.
- Run `./scripts/release_secret_scan.sh` before commit/push.

Advisory-only:
- These helpers are advisory-only research projections.
- They are not trade execution.
- They are not broker sync/import.
- They are not accounting mutation.
- They are not provider-backed live calculations.
- They are safe only when composed from caller-supplied fixture or snapshot-style inputs.

Must not be manually tested:
- Do not create, edit, delete, or replay portfolio accounting records.
- Do not trigger broker/account import or sync.
- Do not place orders, submit trades, or simulate execution readiness.
- Do not run provider fetches, API routes, DB migrations, or frontend flows as part of this checklist.
- These helpers must not be manually tested as broker/accounting mutation.

Manual acceptance:
- Smoke output stays within the advisory read-model payloads only.
- No helper requires DB writes, broker wiring, provider calls, API calls, or frontend dependencies.
- Rebalance guidance remains read-only target-weight drift and delta advice, not execution intent.
