# Backend Final Audit Report

- Generated at: `2026-04-23T23:10:49+08:00`
- Branch: `main`
- Commit: `b196a68b42c690004090b3ceaa42f40dcb8a1221`
- Verdict: `ready_to_deploy`

## Scope

Backend closure audit covered:

- `src/database_doctor.py`
- `src/storage.py`
- `src/storage_postgres_bridge.py`
- `src/postgres_*_store.py` formal runtime modules touched by the shim-closure slice
- `docs/CHANGELOG.md`
- `docs/architecture/database-maintenance-handbook.md`
- database doctor / cleanup / Phase F / Phase G / real-PG regression suites
- support-bundle / reopen acceptance suites
- `./scripts/ci_gate.sh`

## Executive Summary

This slice closes the three blocking backend findings without changing runtime truth semantics:

1. Shim cleanup wording is now truthful. The repo keeps `src/postgres_phase_{a..g}.py` compatibility shims intentionally, while default runtime imports now point at the formal `src/postgres_*_store.py` modules.
2. Disposable Real-PG bundle output is now deterministic under the intended acceptance rule. Direct vs smoke bundle JSON is identical after removing only `generated_at`.
3. Phase F authority-backed metadata/sync reads now batch shadow materialization and legacy comparison inputs per request instead of looping through repeated per-account authority fetches.

SQLite remains the primary runtime truth. Phase F remains comparison-only shadow. Phase G `.env` live-source semantics remain unchanged.

## Blocking Findings Closure

### 1. Shim handling

Chosen path: `B` (`document accurately and retain compatibility shims for now`)

What changed:

- `docs/CHANGELOG.md` no longer claims the compatibility shims are gone.
- The changelog now states that formal modules are the default runtime path and the shim files remain intentionally for compatibility.
- Cleanup test wording was narrowed so it only claims removal of legacy experimental paths, not full shim deletion.
- Runtime bridge/storage imports now use formal modules directly:
  - `src/storage.py`
  - `src/storage_postgres_bridge.py`
  - touched `src/postgres_*_store.py` cross-module imports

Result:

- Documentation matches the checked-in repository state.
- Default runtime paths no longer depend on the compatibility shim modules.
- Compatibility shims remain available for existing tests and external legacy imports.

### 2. Real-PG bundle determinism

Normalized deterministic surfaces:

- `real_pg_bundle.isolated_sqlite_path`
- `sqlite_primary.configured_path`
- `sqlite_primary.resolved_path`
- `topology_summary.config_layer.sqlite_database_path`
- `real_pg_bundle.verification_checks.phase_g_execution_log_shadow.probe_session_id`
- AI handoff paste blocks that embed the isolated SQLite path

Stable placeholders now used:

- isolated SQLite path: `<temporary>/database-real-pg-bundle.sqlite`
- probe session id: `<latest_probe_session_id>`

Fresh verification:

- default doctor vs smoke, removing only `generated_at`: `passed`
- real-PG bundle vs smoke real-PG bundle, removing only `generated_at`: `passed`
- Real-PG verification checks:
  - `phase_store_initialization`: `passed`
  - `schema_bootstrap`: `passed`
  - `phase_g_execution_log_shadow`: `passed`
  - `phase_f_comparison_flags`: `passed`

### 3. Phase F authority read-path performance

What changed:

- Added batched Phase F shadow bundle materialization in `src/postgres_portfolio_coexistence_store.py`.
- Refactored `src/storage.py` authority evaluation so one request can reuse:
  - batched shadow bundles
  - batched legacy account rows
  - batched legacy broker connection rows
  - batched latest sync-state candidates
  - batched legacy sync positions / cash balances grouped by broker connection
- Applied the batched authority path to:
  - account metadata list
  - broker connection metadata list
  - latest broker sync bundle lookup

Result:

- The previous Phase F N+1 authority pattern on the audited metadata/sync paths is removed.
- Read semantics remain unchanged: SQLite is still serving truth, and Phase F remains comparison-only.

## Validation Summary

### Targeted database audit suites

Command:

```bash
python3 -m pytest \
  tests/test_database_doctor.py \
  tests/test_database_doctor_cleanup.py \
  tests/test_postgres_phase_f.py \
  tests/test_postgres_phase_g.py \
  tests/test_postgres_phase_f_real_pg.py \
  tests/test_postgres_phase_g_real_pg.py -q
```

Result:

- Passed: `113`
- Failed: `0`
- Skipped: `0`

### Support bundle / reopen regression suites

Command:

```bash
python3 -m pytest \
  tests/test_rule_backtest_support_bundle_e2e.py \
  tests/test_rule_backtest_reopen_acceptance.py -q
```

Result:

- Passed: `7`
- Failed: `0`

### Fresh determinism audit

Command shape:

```bash
python3 - <<'PY'
# build doctor / smoke / real-PG / real-PG smoke reports
# compare after removing generated_at
PY
```

Result:

- `doctor_smoke_equal_without_generated_at`: `true`
- `real_pg_bundle_equal_to_smoke_without_generated_at`: `true`
- `real_pg_bundle_isolated_sqlite_path`: `<temporary>/database-real-pg-bundle.sqlite`
- `real_pg_bundle_probe_session_id`: `<latest_probe_session_id>`
- `real_pg_bundle_ai_handoff_has_placeholder`: `true`

### Empty-diff-safe py_compile audit

Command:

```bash
changed_py_files=$(git diff --name-only origin/main...HEAD -- '*.py')
if [ -n "$changed_py_files" ]; then
  python3 -m py_compile $changed_py_files
else
  echo no_changed_python_files
fi
```

Result:

- Status: `passed`
- Mode: `no_changed_python_files`

### Broader backend gate

Command:

```bash
./scripts/ci_gate.sh
```

Result:

- Passed: `yes`
- Pytest summary: `1644 passed, 2 skipped, 1 warning, 113 subtests passed`

Observed non-blocking warnings:

- `flake8` not installed in the local environment, so the script emitted a warning instead of running it
- `akshare` not installed; the local script printed a non-blocking warning during deterministic smoke checks
- one existing Pydantic serializer warning in `tests/test_backtest_api_contract.py`

### Web build

- Not run
- Reason: no frontend files were touched in this slice

## Compatibility Checks

- Phase E support bundle contract: `passed`
- Phase E reopen contract: `passed`
- Phase F snapshot / attribution / comparison surfaces: `passed`
- Phase G execution-log shadow observability: `passed`
- Changelog shim wording accuracy: `passed`

## Deployment Verdict

Verdict: `ready_to_deploy`

Reason:

- The three blocking findings from the prior audit are closed.
- Fresh targeted validation and the broader backend gate both passed.
- No runtime truth semantics were changed.

## Remaining Caveats

- Compatibility shims under `src/postgres_phase_{a..g}.py` still exist intentionally. This is now documented truthfully; they are no longer treated as removed.
- Local `ci_gate` still warns when `flake8` is absent. This is environmental, not a blocker for this slice.
- The existing Pydantic serializer warning remains outside the scope of this audit closure.

## Rollback

- Revert the touched runtime/docs/tests files from this slice.
- Re-run:
  - `python3 -m pytest tests/test_database_doctor.py tests/test_database_doctor_cleanup.py tests/test_postgres_phase_f.py tests/test_postgres_phase_g.py tests/test_postgres_phase_f_real_pg.py tests/test_postgres_phase_g_real_pg.py -q`
  - `./scripts/ci_gate.sh`
