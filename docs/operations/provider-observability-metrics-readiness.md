# Provider Observability And Metrics Readiness

Status: readiness note only. No production metrics stack is implemented or enabled today.

## Current status

- T-649 conclusion: WolfyStock already exposes useful operator-facing observability through admin logs, execution logs, runtime diagnostics, provider/source/freshness sidecars, evidence snapshots, and MarketCache process-local counters.
- No production metrics stack is implemented.
- No OpenTelemetry, Prometheus, Grafana, or Sentry integration is active.
- Current observability is mostly log-centric, diagnostic, metadata-centric, and process-local rather than a durable time-series or tracing system.

## Existing observable surfaces

- Admin Logs and `ExecutionLogService` provide sanitized admin/action/business-event visibility.
- Market Provider Operations provides a read-only admin projection of provider/cache status.
- Provider Usage Ledger provides sanitized provider usage diagnostics.
- Provider capability, source-confidence, and registry metadata document provider/source/freshness posture without granting runtime authority.
- `scripts/diagnose_market_intelligence_runtime.py` emits sanitized runtime diagnostic JSON.
- MarketCache exposes status and process-local event counters used for operational observation, including the current `marketCacheEventSummary` payload returned by `MarketProviderOperationsService`.
- Market Overview, Scanner, Liquidity, Rotation, and Stocks already expose additive freshness/evidence/provider sidecars or snapshots for operator and user disclosure.
- Prewarm, smoke, and diagnose scripts exist for bounded operational checks; they are not a metrics backend.

## Ranked gaps from T-649

1. API p95/p99 latency
2. Provider latency, error, fallback, and stale rates
3. Cache hit/miss/SWR rates
4. Budget skips
5. SWR refresh success/failure
6. Authority/freshness distribution
7. Degraded score count
8. Trace/error correlation

## Guardrails

Diagnostic and provider metadata must remain observational only. They must not affect:

- provider routing
- provider budgets
- scoring
- gates
- `decisionGrade`
- provider authority
- cache behavior

This note does not implement or imply any exporter, tracing SDK, metrics middleware, or external monitoring sink.

## Known follow-up to inspect later

- `MarketProviderOperationsService` already returns `marketCacheEventSummary`.
- The response schema may not yet declare that field.
- A future sanitized admin payload contract task can inspect `api/v1/schemas/market_provider_operations.py` and `tests/api/test_market_provider_operations.py`.

## Safest future implementation order

1. Keep docs/readiness mapping current first.
2. If needed, add a test-only sanitized metrics payload contract next.
3. Then tighten the internal diagnostic/admin payload contract.
4. Only later consider Prometheus text exposition behind disabled config or OpenTelemetry tracing.

Until those later tasks land, treat the current system as logs + diagnostics + sidecars + process-local counters, not as a production metrics stack.
