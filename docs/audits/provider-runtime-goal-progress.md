
## 2026-06-12 Provider Circuit Admin Probe Evidence Surface

Extended the existing admin provider SLA readiness surface with an opt-in,
operator-readable pilot evidence projection:

- surface:
  `/api/v1/admin/providers/sla-readiness?adminProbePilotEvidence=true`;
- evidence contract: `provider_admin_probe_pilot_evidence_v1`;
- evidence shows pilot enabled/disabled, rollback enabled/disabled, selected
  boundary, API route, last decision category, would-block/block state, and
  sanitized no-change markers;
- default SLA readiness responses still omit the evidence field unless the
  operator explicitly requests it;
- evidence appears only for `data_source_validation/admin_provider_probe`.

The evidence is generated from stored circuit state and existing pilot flags. It
does not call providers, store raw payloads, expose provider URLs/query strings,
credentials, cookies, raw session ids, exception text, or stack traces, and does
not change global provider order, fallback, retry, timeout, in-flight,
sufficiency, MarketCache TTL/SWR/cold-start behavior, quota enforcement,
auth/RBAC/session behavior, frontend behavior, broker/order/trade paths, or
notification sending.

This is operator visibility and review plumbing only. It is not public-launch
approval, does not accept target-environment evidence by itself, and does not
approve public/user provider runtime enforcement. Public launch provider
reliability remains **NO-GO** until accepted target-environment provider
entitlement, degraded behavior, broader circuit policy, and operator/staging
evidence exist.

## 2026-06-12 Provider Admin Probe Evidence Acceptance Hardening

Tightened the admin probe pilot evidence acceptance layer without changing
provider runtime behavior:

- `adminProbePilotEvidence` now explicitly marks the evidence as admin-probe
  only, default-off, rollback-available, sanitized-only, not accepted operator
  evidence, not public-launch-ready, and still blocked by remaining public
  provider-circuit **NO-GO** items;
- the evidence separately records that public/member provider runtime blocking,
  provider runtime enforcement, provider order/fallback/cache changes,
  MarketCache changes, quota enforcement changes, auth/RBAC/session changes,
  and notification sends are not part of this surface;
- `scripts/provider_sla_licensing_evidence_check.py` now rejects sanitized
  provider SLA/licensing artifacts that try to promote admin-probe evidence into
  public/member runtime blocking, provider runtime enforcement, provider
  order/fallback/cache changes, accepted operator evidence, or public readiness;
- the checker also treats synthetic provider URLs, request ids, tokens, raw
  payloads, trace markers, credentials, and cache keys as unsafe evidence fields
  and keeps failing output bounded/redacted.
- `scripts/operator_evidence_template_pack.py` now emits
  `provider_sla_licensing_evidence.json`, and
  `scripts/operator_evidence_bundle_check.py` validates it through
  `scripts/provider_sla_licensing_evidence_check.py` so reviewer evidence packs
  expose the same admin-probe-only/default-off/no-enforcement posture.

This hardening is reviewer evidence only. It does not change the existing admin
probe pilot runtime path, public/user provider routes, provider ordering,
fallback, retry, timeout, in-flight behavior, MarketCache TTL/SWR/cold-start
behavior, quota/cost enforcement, auth/RBAC/session behavior, DB schema,
frontend source, broker/order/trade paths, or notification sending.

## 2026-06-12 Provider Circuit Admin Probe Pilot

Implemented a default-off, explicit opt-in provider circuit enforcement pilot
for the admin built-in provider validation probe only:

- boundary: `/config/data-source/test-builtin`, provider category
  `data_source_validation`, route family `admin_provider_probe`;
- enable switch:
  `WOLFYSTOCK_PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ENABLED=true`;
- rollback switch:
  `WOLFYSTOCK_PROVIDER_CIRCUIT_ADMIN_PROBE_PILOT_ROLLBACK_ENABLED=true`;
- when enabled and stored circuit state for the selected provider/boundary
  would block, the admin probe returns a sanitized blocked diagnostic before
  outbound provider validation;
- default-off and rollback paths do not read circuit state or change the
  provider validation call path.

This is not public-launch approval. It does not change global provider order,
fallback, retry, timeout, in-flight, sufficiency, MarketCache TTL/SWR/cold-start
behavior, quota enforcement, auth/RBAC/session behavior, DB schema, frontend
behavior, broker/order/trade paths, or notification sending. Public launch
provider reliability remains **NO-GO** until target-environment provider
entitlement, degraded behavior, broader circuit policy, and operator evidence
are accepted.

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

## 2026-06-11 Provider Dashboard/SLA Doc Reconciliation

Docs-only reconciliation:

- Launch Cockpit and admin provider surfaces now provide advisory operator
  visibility for provider diagnostics.
- These surfaces do not prove provider entitlement, staging degraded behavior,
  live circuit enforcement, provider order/fallback/retry/timeout/cache
  behavior, or public launch readiness.
- Mission Control, Launch Cockpit, and admin provider diagnostics do not approve
  launch.
- Provider runtime enforcement and provider data licensing remain **NO-GO**.
- Provider SLA/degraded target-environment evidence remains missing until
  accepted staging/operator artifacts exist.

Unchanged boundaries:

- No runtime code, frontend/UI/CSS/layout, provider runtime/order/fallback,
  retry, timeout, cache, quota, auth, DB, broker, notification, or production
  config behavior changed.
