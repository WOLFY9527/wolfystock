# T-1048 Backend Provider Cache Validation Gate Readiness Audit

## Metadata

- Task ID: T-1048-AUDIT
- Task title: Backend provider cache validation gate readiness audit
- Mode: READ-ONLY-AUDIT report artifact
- Date: 2026-06-06
- Workspace: `/Users/yehengli/worktrees/t1048-backend-validation-provider-cache-audit`
- Branch: `codex/t1048-backend-validation-provider-cache-audit`
- Base commit inspected: `e4bff2a9`
- Allowed diff: this audit document only

## Scope

This audit inspected backend validation scripts, CI references, provider/cache/runtime-focused tests,
source/provenance tests, provider diagnostics tests, and secret-scan/release helpers enough to define a
minimal validation gate for future protected provider/cache/runtime writes.

No source code, tests, config, fixtures, scripts, provider behavior, cache behavior, runtime routing, API
behavior, frontend behavior, or CI behavior was changed.

## Executive Verdict

WolfyStock has enough focused offline coverage to require a small provider/cache/runtime gate before future
protected writes. The default gate should not be the full backend gate for every small change. Instead, future
Codex prompts should require:

1. preflight and exact diff allowlist checks;
2. `py_compile` for changed Python files plus directly coupled provider/cache/runtime modules;
3. a focused pytest slice from the matrix below;
4. `git diff --check`;
5. `./scripts/release_secret_scan.sh`.

Use `./scripts/ci_gate.sh` for broad provider/cache/runtime changes, release/landing confidence, shared
planner/fallback changes, API response-shape changes, or when focused tests do not cover the touched semantics.
Do not require network smoke or live-provider diagnostics for every task.

## Current Validation Entrypoints

| Entrypoint | Current behavior | Gate classification |
| --- | --- | --- |
| `./scripts/ci_gate.sh` | Runs `scripts/task_preflight.sh`, critical flake8 if available, core/storage/search/market/provider `py_compile`, deterministic `./test.sh code`, deterministic `./test.sh yfinance` conversion checks, and `python -m pytest -m "not network"`. CI runs this in `backend-gate`. | Required broad landing gate for high-risk or wide backend changes; too broad for every small provider/cache edit loop. |
| `./scripts/ci_gate_fast.sh` | Detects branch/local changed files, compiles changed Python, tries filename-matched focused tests, runs frontend/docs checks when relevant, and explicitly says it does not replace `ci_gate.sh`. | Useful iteration helper only. Not enough as the protected provider/cache gate because filename matching misses semantic coupling. |
| `scripts/ci_gate_profile.sh backend` | Runs offline pytest with durations using `-p no:cacheprovider`; explicitly profiling only. | Runtime profiling evidence only, never pass/fail release evidence. |
| `./scripts/release_secret_scan.sh` | Scans committed branch diff, staged files, working-tree diffs, and untracked text files for high-confidence credential patterns; skips binary/build/cache paths. | Required for docs and protected backend tasks before commit/push. Not a full repository DLP scan. |
| `python3 scripts/provider_reliability_audit.py --offline` | Emits bounded JSON for freshness/fallback posture and declares `networkCallsExecuted=false`; it does not call providers, read credentials, inspect `.env`, or modify routing. | Optional focused evidence when changing provider freshness/fallback/cache posture. Not a replacement for focused pytest. |
| `./scripts/market_data_readiness_preflight.sh` | Local-only diagnostic for market-data readiness; the script states no providers are called, no external network calls are made, no env vars are modified, and no packages are installed. | Optional operator/readiness diagnostic for market-data readiness tasks. Not CI-critical and not a default protected-write gate. |
| `.github/workflows/network-smoke.yml` | Scheduled/manual non-blocking workflow for `python -m pytest -m network` and `./test.sh quick --no-notify`. | Observation-only, not a default task gate. Current tests define a `network` marker in `setup.cfg`, but no `@pytest.mark.network` usage was found. |
| `./test.sh quick`, `./test.sh all`, stock scenario modes | Execute app/provider paths and may depend on network/provider availability. `ci_gate.sh` only uses deterministic `code` and `yfinance` modes. | Manual smoke only unless a prompt explicitly scopes live provider/operator evidence. |

## Minimal Backend Provider/Cache Runtime Gate

Use this command template for future protected provider/cache/provenance writes. Replace placeholders with the
actual changed files and the smallest relevant test slice from the next section.

```bash
pwd
git fetch origin
git status --short --branch
git diff --name-only
git diff --cached --name-only

PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile <changed_python_files> <directly_coupled_provider_cache_runtime_files>
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider <focused_test_files>
git diff --check
./scripts/release_secret_scan.sh
git status --short --branch
```

Escalate to `./scripts/ci_gate.sh` before commit/push when any of these are true:

- provider runtime order, fallback, first-good-wins behavior, circuit behavior, or deadline behavior changed;
- MarketCache TTL, SWR, cold-start fallback, background refresh, cache key, or payload meaning changed;
- `analysis_provider_planner`, `data_source_router`, research-budget profiles, or shared provider result
  contracts changed;
- API response shapes or stored/public contract versions changed;
- the focused test slice is empty, ambiguous, or only indirectly covers the changed behavior;
- the prompt explicitly requires a broad backend gate.

Add `python3 scripts/provider_reliability_audit.py --offline` when the change touches freshness/fallback/cache
posture and the prompt wants an extra local posture check. Add `./scripts/market_data_readiness_preflight.sh`
only for readiness/operator-diagnostic tasks, not as a normal code gate.

## Focused Test Matrix

Choose the smallest matching row, then add adjacent rows if the write crosses boundaries.

| Write area | Focused tests that are narrow enough for small writes | What they protect |
| --- | --- | --- |
| Provider execution cache, fallback order, duplicate suppression, optional deadlines | `tests/api/test_provider_cache.py`, `tests/api/test_provider_fallback.py`, `tests/test_research_budget_profiles.py`, `tests/test_provider_usage_ledger.py`, `tests/api/test_provider_usage_ledger.py` | Provider coalescing, cache-hit call avoidance, fallback order, quota/timeout counters, optional-vs-required category behavior, sanitized usage ledger. |
| MarketCache local/remote/fallback semantics | `tests/api/test_market_cache.py`, `tests/api/test_market_cache_import_boundary.py`, `tests/test_market_cache_fallback_contracts.py`, `tests/test_observation_cache.py`; optional posture check: `python3 scripts/provider_reliability_audit.py --offline` | Fresh/stale/fallback projection, no live relabeling, background refresh, local-authoritative remote mirroring, lazy singleton/import boundaries, observation cache freshness, offline freshness/fallback posture. |
| Provider runtime and freshness contracts | `tests/test_provider_runtime_contracts.py`, `tests/test_provider_runtime_boundary.py`, `tests/test_provider_freshness_contracts.py`, `tests/test_provider_contract_boundary.py` | Runtime quote/history fallback shape, first-success behavior, unavailable-without-fake-data behavior, provider/freshness namespace inertness, fixture boundaries, fallback/mock/synthetic not-live semantics. |
| Routing, source authority, provenance, provider metadata | `tests/test_data_source_router.py`, `tests/test_source_confidence_contract.py`, `tests/test_provider_capability_matrix.py`, `tests/test_provider_plan_advisor.py`, `tests/test_provider_fit_advisor_service.py`, `tests/api/test_provider_fit_advisor.py`, `tests/test_provider_evidence_snapshot.py` | Cache-required route degradation, non-scoring provider rejection, score-grade authority gates, provider capability metadata, advisory-only plan snapshots, provider-fit diagnostics, bounded evidence snapshots. |
| Admin/provider operations diagnostics | `tests/test_market_provider_operations_boundary.py`, `tests/api/test_market_provider_operations.py`, `tests/api/test_provider_operations_matrix.py`, `tests/test_provider_circuit_observer.py`, `tests/test_provider_circuit_storage.py`, `tests/api/test_admin_provider_circuit_diagnostics.py` | Read-only diagnostics, no provider/cache refresh from admin surfaces, sanitized secret-free output, circuit/quota dry-run rows, capability-gated provider diagnostics. |
| Provider adapter primitives and credentials | `tests/test_provider_http.py`, `tests/test_provider_types.py`, `tests/test_provider_validation.py`, `tests/test_provider_credentials.py` plus touched adapter tests such as `tests/test_alpaca_fetcher.py`, `tests/test_alphavantage_provider.py`, `tests/test_coinbase_public_provider.py`, `tests/test_twelve_data_fetcher.py`, `tests/test_tickflow_fetcher.py`, `tests/test_us_fundamentals_provider.py`, `tests/test_polygon_us_breadth_provider.py`, `tests/test_sec_edgar_evidence_service.py` | HTTP status normalization, timeout/error bucket mapping, credential-state sanitization, adapter payload normalization, provider-specific fail-closed behavior. |
| Public source/provenance sidecars | `tests/services/test_source_provenance_contract.py`, `tests/services/test_home_source_provenance_sidecar.py`, `tests/services/test_single_stock_evidence_packet.py`, `tests/services/test_market_intelligence_source_provenance_sidecar.py`, `tests/services/test_liquidity_source_provenance_sidecar.py`, `tests/services/test_rotation_source_provenance_sidecar.py`, `tests/services/test_options_source_provenance_sidecar.py`, `tests/services/test_market_scanner_source_provenance_sidecar.py` | Inert helper imports, bounded consumer-safe provenance fields, degraded/fallback/fixture fail-closed states, raw/provider/admin detail redaction. |

## Required Prompt Template

Future Codex prompts touching provider/cache/runtime should include this compact validation block:

```text
Validation:
- PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile <changed_python_files> <directly_coupled_provider_cache_runtime_files>
- PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider <focused_test_files_from_T-1048_matrix>
- git diff --check
- ./scripts/release_secret_scan.sh
- git status --short --branch

Escalate:
- Run ./scripts/ci_gate.sh if the write changes provider order/fallback/deadline behavior,
  MarketCache TTL/SWR/cold-start/background refresh semantics, shared routing/planner policy,
  API response shape, or if focused coverage is missing.
```

Also require final reports to state:

- provider order changed: yes/no;
- new live provider call paths added: yes/no;
- MarketCache TTL/SWR/cold-start/cache-key semantics changed: yes/no;
- fallback/mock/synthetic live-labeling changed: yes/no;
- raw provider payloads, credentials, headers, cookies, request/response bodies exposed: yes/no;
- required vs optional category handling changed: yes/no.

## Coverage Gaps And Weak Spots

1. Network-smoke lane is not ready as a required gate.
   - `setup.cfg` defines `network`, and `.github/workflows/network-smoke.yml` checks that the selection is not
     empty, but no `@pytest.mark.network` usage was found under `tests/`.
   - Treat network smoke as scheduled/manual observation only until a dedicated task restores meaningful
     network-marked tests.

2. Several legacy provider adapters have thin or indirect direct coverage.
   - No obvious direct filename-matched test was found for `data_provider/akshare_fetcher.py`,
     `data_provider/baostock_fetcher.py`, `data_provider/efinance_fetcher.py`,
     `data_provider/pytdx_fetcher.py`, `data_provider/sec_edgar_provider.py`,
     `data_provider/yfinance_fetcher.py`, or `data_provider/realtime_types.py`.
   - Some behavior is covered indirectly through `test.sh`, `tests/test_data_source_router.py`, service tests,
     or evidence services, but direct adapter normalization/fail-closed suites are uneven.

3. Remote cache coverage is strong with fake backends, but not an external Redis/Valkey integration gate.
   - `tests/api/test_market_cache.py` covers remote projection, local-authoritative behavior, Redis factory
     wiring, sanitized failure logging, and slow/failing remote behavior with fakes.
   - This is appropriate for default CI. Real Redis/Valkey connectivity should stay operator/staging evidence,
     not a per-task gate.

4. Some diagnostic helpers are behavior-tested through broader suites rather than direct unit files.
   - Examples include `data_source_router_diagnostics.py`, `provider_operations_matrix_service.py`,
     `market_provider_operations_service.py`, `provider_unavailable_reason_buckets.py`, and
     `rotation_radar_quote_provider.py`.
   - This is acceptable for current small writes when the adjacent behavior tests are selected, but future
     helper extraction should add direct tests if semantics become reusable policy.

5. `release_secret_scan.sh` is scoped to changed text files.
   - It is the right pre-push/pre-release smoke for this workflow, but it does not prove unchanged historical
     files are secret-free.

## Commands Too Broad Or Flaky For Every Task

- `./scripts/ci_gate.sh`: correct broad backend gate, but it runs full offline pytest plus `test.sh` smoke
  checks and depends on local optional tooling/package state. Its `./test.sh yfinance` phase is a deterministic
  conversion check, not a live provider smoke, but the overall gate is still too broad for every focused
  iteration. Use for broad/high-risk changes and final landing.
- `python3 -m pytest -m "not network"`: strong regression signal, but too broad for small provider metadata or
  projection-only writes unless the focused slice is inadequate.
- `python3 -m pytest -m network`: not suitable as a required gate today because network tests are not currently
  marked and the workflow is non-blocking/scheduled/manual.
- `./test.sh quick`, `./test.sh all`, stock scenario modes, and live provider activation diagnostics: can call
  app/provider paths and depend on network, credentials, provider quotas, or local environment. Use only when
  explicitly scoped as operator evidence.
- `./scripts/market_data_readiness_preflight.sh`: useful local readiness/operator diagnostic, but it can depend
  on local venv/parquet/backend readiness state and is not CI-critical.
- `scripts/ci_gate_profile.sh`: profiling only; it must not be used to waive the real gate.
- Docker build/import smoke: useful CI/release coverage, but too expensive and environment-dependent for every
  narrow provider/cache task.

## Exactly One Future Docs/Test Write

Recommended future write: add the `Required Prompt Template` above to
`docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md` as a docs-only backend provider/cache/runtime validation
template.

Do not combine that docs write with test changes. Defer network-marker restoration, legacy adapter direct-test
fill-ins, and Redis/Valkey operator evidence to separate scoped tasks.

## Future Deferrals

- Restore or add meaningful `@pytest.mark.network` tests only if the team wants the scheduled network smoke lane
  to be actionable.
- Add direct fail-closed adapter tests for the legacy providers listed above when those adapters are next touched.
- Add direct unit tests for diagnostic helper modules if they become shared policy rather than local projection
  details.
- Keep real Redis/Valkey connectivity and live provider activation checks out of default Codex gates unless a
  prompt explicitly requests controlled operator/staging evidence.

## Final Audit Boundary

Confirmed unchanged by this audit:

- provider runtime order/live-call paths/fallback semantics;
- MarketCache TTL/SWR/cold-start/background refresh/cache-key semantics;
- provider budget/routing behavior;
- source authority and score contribution behavior;
- API response shapes and stored contract versions;
- scripts, CI, tests, fixtures, package files, lockfiles, source code, backend/frontend behavior.
