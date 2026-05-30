# Queue / WS2 / Metrics Production Readiness

Status: topology contract only. Repo-local foundations exist, but production
runtime, deployment enablement, and launch approval remain deferred.

## Purpose

This note consolidates the current Queue / WS2 / metrics topology so readers do
not mistake repo-local foundations for production readiness.

This document does not:

- change runtime behavior
- change queue mode
- enable deployment, broker, worker, Redis, or SSE cutover
- add a metrics exporter, endpoint, or internal consumer
- satisfy release approval or accepted launch evidence

## Current classification

- Queue execution remains process-local. `AnalysisTaskQueue` still reports
  `mode=process_local` and `single_process_required=True`.
- Durable task state and durable polling foundations exist and are the current
  reliability baseline for cross-instance reads.
- SSE remains process-local. Cross-instance replay/broadcast is not enabled;
  polling fallback remains the safe multi-instance posture.
- WS2 repo-local foundations exist: durable state, durable polling, synthetic
  worker prototype, owner isolation, lease recovery, and progress replay.
- `BackendMetricsSnapshotService` exists as an internal helper-only contract. No
  production caller, endpoint, exporter, or deployment path exists.
- Redis/Valkey in current repo scope is MarketCache mirror-only, disabled by
  default, persist-only, and non-authoritative. It does not grant remote reads,
  queue authority, locking authority, or metrics-stack readiness.

## Topology crosswalk

| Surface | Current repo-local state | Production-ready? | Explicit boundary |
| --- | --- | --- | --- |
| `AnalysisTaskQueue` | In-process queue, in-process executor, in-process SSE subscriber state | No | Keep single-process requirement; no broker or worker cutover implied |
| Durable task state / durable polling | Durable task/progress rows and owner-scoped polling reads exist | Partial foundation only | Safe read/replay foundation; not a production worker topology by itself |
| SSE / WS2 replay | SSE stays process-local; durable polling can replay progress by owner/task | No | No external broadcast, no cross-instance SSE guarantee, no cutover |
| Synthetic worker prototype | Fixture-backed lease/claim/retry/recovery prototype exists | No | Prototype only; not an accepted deployment model |
| Owner isolation / lease recovery / progress replay | Repo-local foundations and tests exist | Partial foundation only | Keep as readiness building blocks, not launch evidence |
| `BackendMetricsSnapshotService` | Pure helper contract for sanitized count snapshots | No | Helper-only; no endpoint, exporter, internal consumer, or runtime authority |
| MarketCache Redis mirror boundary | Disabled-by-default Redis/Valkey mirror for JSON-safe persist-only projection | No | Mirror-only, no remote reads, no distributed lock/SWR/cold-start authority |
| Production metrics/exporter stack | No OpenTelemetry, Prometheus, Grafana, Sentry, or exporter deployment | No | Current posture is helper/log/diagnostic only, not production metrics |

## Deferred items

The following are still deferred and must not be inferred from this document:

- production queue/broker/worker deployment model
- external SSE replay, broadcast, or cutover
- staging API A/B + worker + PostgreSQL smoke evidence
- Redis/Valkey deployment smoke
- any Redis remote read authority
- OpenTelemetry / Prometheus / Grafana / Sentry / exporter deployment
- any `BackendMetricsSnapshotService` endpoint, exporter, or internal consumer
- release approval or accepted launch evidence

## Release and launch boundary

This note is a topology crosswalk, not release evidence.

- It does not convert repo-local foundations into accepted staging or production
  evidence.
- It does not satisfy launch approval, go/no-go review, or operator acceptance.
- Use the deployment and launch audit docs for actual readiness gates and
  evidence requirements.

## Related docs

- `docs/audits/deployment-readiness-checklist.md`
- `docs/audits/public-launch-readiness-master.md`
- `docs/audits/public-launch-gap-register.md`
- `docs/audits/index-db-ws2-deployment.md`
- `docs/operations/provider-observability-metrics-readiness.md`
