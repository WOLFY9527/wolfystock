# Provider Reliability Runtime v1 Progress

Date: 2026-06-11
Mode: guarded backend pilot architecture. Default provider order, fallback, cache, and runtime behavior must remain unchanged.

## Scope Boundary

This goal adds a runtime policy model and a read-only guarded pilot evaluator. It does not enable production enforcement, does not block provider calls, does not change provider order, does not alter fallback behavior, and does not change MarketCache semantics by default.

Pilot scope is intentionally narrow:

- Provider category: `options`
- Route family: `options_lab`
- Pilot behavior: evaluate would-block and would-fallback decisions from stored circuit state and advisory evidence only
- Enforcement behavior: always advisory-only in this iteration

## Runtime Policy Model

| Policy concept | v1 model | Runtime action in this goal |
| --- | --- | --- |
| Health | `healthy`, `cooldown_active`, `half_open_sampling`, `half_open_sample_limited`, `degraded`, `quota_depleted`, `operator_disabled` | Projection only |
| Cooldown | Uses stored `cooldown_until` to distinguish active cooldown from half-open-ready state | Projection only |
| Half-open sampling | Uses stored `half_open_sample_limit` and `half_open_sample_count` | Projection only |
| Fallback | Computes `wouldFallbackIfEnforced` and pilot `pilotWouldFallback` when explicit pilot flags and scope match | Projection only |
| Sufficiency | Maps closed state to `sufficient`, blocking/degraded states to `insufficient`, half-open recovery to `recovery_sampling` | Projection only |
| Degraded status | `none`, `fallback_advised`, `cache_only_advised`, `quota_depleted`, `operator_disabled`, `recovery_sampling` | Projection only |
| Rollback | Disable pilot flag; decision returns default-off status and no pilot block/fallback action | No state rollback needed |

## Advisory, Dry-Run, Pilot, Production

| Mode | Meaning | Enabled in this goal |
| --- | --- | --- |
| Advisory | Read stored provider circuit/quota/probe evidence and report posture fields such as `wouldBlockIfEnforced`. | Yes |
| Dry-run | Record or read synthetic observations and counters without using them to gate provider calls. | Existing support remains unchanged |
| Pilot | Explicitly evaluate `pilotWouldBlock` / `pilotWouldFallback` for the staged `options/options_lab` scope through admin-only diagnostics. | Yes, default off |
| Production enforcement | Use provider circuit policy to skip, block, reorder, retry, or fallback provider calls at runtime. | No |

Pilot flags:

- `runtimePilotEnabled`: defaults to `false`.
- `runtimePilotFallbackEvaluationEnabled`: defaults to `false`.

Both flags only affect `GET /api/v1/admin/providers/sla-readiness` read-only posture output. They do not change provider runtime execution.

## Test Matrix

| Requirement | Test target | Expected assertion |
| --- | --- | --- |
| Timeout bucket | `tests/test_provider_circuit_observer.py` | active cooldown projects block/fallback evidence but does not block calls |
| 429 bucket | `tests/test_provider_circuit_observer.py` | quota depleted maps to degraded quota posture and fallback advice |
| 403 bucket | `tests/test_provider_circuit_observer.py` | operator-disabled/auth posture is sanitized and non-enforcing |
| 5xx bucket | `tests/test_provider_circuit_observer.py` | open state maps to cooldown/open candidate posture |
| Cooldown | `tests/test_provider_circuit_observer.py` | unexpired cooldown is blocking evidence; expired cooldown allows half-open sampling evidence |
| Half-open | `tests/test_provider_circuit_observer.py` | sample limit reached projects would-block evidence; available sample stays evaluation-only |
| Scope matching | `tests/test_provider_circuit_observer.py` | pilot flags only apply to `options/options_lab` |
| Rollback | `tests/test_provider_circuit_observer.py` | disabling pilot flag suppresses pilot block/fallback decisions without mutating stored state |
| Sanitized diagnostics | `tests/api/test_admin_provider_circuit_diagnostics.py` | `runtimePilot` contains bounded labels only |
| No leakage | `tests/api/test_admin_provider_circuit_diagnostics.py` | response omits credentials, raw payloads, URLs, tokens, headers, and exception text |
| Admin posture | `tests/api/test_admin_provider_circuit_diagnostics.py` | SLA readiness exposes `runtimePilot` as read-only posture |

## Checkpoints

- [x] `checkpoint(provider): design runtime policy`
- [x] `checkpoint(provider): add circuit policy tests`
- [x] `checkpoint(provider): add guarded pilot path`
- [x] `checkpoint(provider): add diagnostics evidence`
- [x] final `feat(provider): add reliability runtime v1 pilot`

## Validation Plan

- Focused pytest:
  - `python -m pytest tests/test_provider_circuit_observer.py tests/api/test_admin_provider_circuit_diagnostics.py`
  - Add options/provider tests only if options runtime files are touched.
- Compile:
  - `python -m py_compile src/services/provider_reliability_runtime.py src/services/provider_circuit_observer.py api/v1/schemas/admin_provider_circuits.py api/v1/endpoints/admin_provider_circuits.py`
- Diff and secret checks:
  - `git diff --check`
  - `./scripts/release_secret_scan.sh`

## Rollout Blockers

- Production enforcement remains blocked until a separate task authorizes live provider call gating.
- Provider order and fallback behavior remain blocked from change in this goal.
- MarketCache TTL, stale-while-revalidate, cold-start fallback, payload shape, and cache mutation semantics remain blocked from change in this goal.
- Public launch approval is not granted by this goal.
