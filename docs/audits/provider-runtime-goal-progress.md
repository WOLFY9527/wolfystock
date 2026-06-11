
## 2026-06-11 Salvage Rebase And Baseline Gate Evidence

The clean salvage branch was synced to current `origin/main` before commit.
Final changed files are limited to the admin provider SLA readiness endpoint,
schema, focused diagnostics tests, changelog, and this progress note.

Implemented posture:

- default SLA readiness items omit `runtimePilot`;
- `runtimePilot` appears only when `runtimePilotEnabled=true` or
  `runtimePilotFallbackEvaluationEnabled=true`;
- the projection is admin-only, read-only, advisory, sanitized, and explicit
  that live enforcement is false;
- provider order, fallback, cache behavior, MarketCache behavior, quota
  enforcement, auth/RBAC/session behavior, DB migration/cleanup/restore,
  broker/order/trade behavior, external notification sending, and frontend
  behavior are unchanged.

Focused validation after syncing current main:

- `PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python -m pytest -p no:cacheprovider tests/api/test_admin_provider_circuit_diagnostics.py tests/test_provider_circuit_observer.py -q`
  passed with 50 tests.
- `PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python -m py_compile src/services/provider_circuit_observer.py api/v1/schemas/admin_provider_circuits.py api/v1/endpoints/admin_provider_circuits.py`
  passed.
- `git diff --check` passed.
- `PYTHON_BIN=/Users/yehengli/daily_stock_analysis/.venv/bin/python ./scripts/release_secret_scan.sh --base-ref origin/main`
  passed.

Baseline gate note:

- `tests/test_provider_runtime_boundary.py` fails on current `origin/main` with
  existing fixture mismatches unrelated to this salvage.
- `src/services/provider_reliability_runtime.py` does not exist on current
  `origin/main`, so older py_compile commands naming that module are stale.
- `PYTHON_BIN=/Users/yehengli/daily_stock_analysis/.venv/bin/python ./scripts/ci_gate.sh`
  fails on current `origin/main` because `tests/test_market_data_availability_contracts.py`
  has existing F821 undefined-name errors for `service` and `now`.
- This salvage branch does not modify those baseline failure files.
