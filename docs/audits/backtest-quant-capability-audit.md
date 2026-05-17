# Backtest Quant Capability Audit

Date: 2026-05-18
Branch checked: `codex/t214a-backtest-quant-capability-audit`
Mode: docs-only capability audit. No runtime code, API behavior, schemas,
frontend behavior, provider integration, DuckDB wiring, database migrations, or
tests were changed by this audit.

## Verdict

Current backtest capability is suitable for deterministic research prototypes,
stored-first result inspection, compact support diagnostics, and local-only
universe experiments. It is not ready to be described as professional quant
infrastructure.

| Capability claim | Current verdict | Basis |
| --- | --- | --- |
| Single-symbol deterministic rule backtest | Research prototype OK | Existing status/detail contracts expose stored artifacts and additive professional-readiness diagnostics. |
| Stored compare and robustness readback | Research prototype OK | Compare/readback paths are stored-first and tests keep robustness evidence in `research_prototype` state. |
| Universe backtest | Limited research prototype | Universe jobs are local-data-only, sequential, compact, and explicitly not point-in-time universe proof. |
| DuckDB quant engine | Diagnostic/admin accelerator only | DuckDB validates factor coverage and benchmark scans through explicit admin APIs; it does not replace the Python backtest engine or production scoring. |
| Professional quant readiness | NO-GO | Adjusted OHLC, corporate action lineage, market calendar policy, partial fill/liquidity modeling, tax/impact models, dataset lineage, and point-in-time universe membership remain blockers. |
| Production trading or signal routing | NO-GO | No broker execution, no portfolio mutation, no scanner ranking replacement, no AI decision replacement, and no notification routing changes are in scope. |

## Evidence Read

- `src/services/backtest_professional_readiness.py` fixes
  `overall_state="research_prototype"` and
  `professional_quant_ready=False`, then enumerates blockers for adjusted data,
  corporate actions, trading calendar, fill model, costs, anti-leakage,
  reproducibility, universe bias, and local-data coverage.
- `src/services/rule_backtest_service.py` builds single-symbol and universe
  readiness payloads from the same diagnostic helper. Universe readiness is
  constructed with `universe_mode=True`, `point_in_time_universe=False`, and
  `provider_calls=False`.
- `api/v1/endpoints/backtest.py` describes universe job creation as a stored
  local-only preflight and universe job execution as synchronous sequential
  local-data execution with no provider pull and no worker concurrency.
- `tests/test_backtest_api_contract.py` asserts compact universe API contracts:
  `local_data_only=True`, `professionalReadiness.overall_state` stays
  `research_prototype`, `professional_quant_ready=False`,
  `pointInTimeUniverse=False`, `survivorshipBiasState="uncontrolled"`, and
  `providerCalls=False`.
- `src/services/quant_analytics/duckdb_service.py` implements optional DuckDB
  health, ingest, factor build, benchmark, snapshot, validation, runtime-context
  diagnostics, and candidate query helpers. The runtime-context comparison sets
  `productionRuntimeChanged=False` and `diagnosticOnly=True`.
- `api/v1/endpoints/quant.py` exposes DuckDB only through admin-protected
  explicit endpoints. Factor snapshot, factor path validation, runtime-context
  comparison, coverage, and benchmark endpoints are diagnostic/admin surfaces.
- `tests/test_quant_duckdb_service.py` verifies disabled ingest does not create
  a DB file, factor builds are deterministic, factor coverage can be
  insufficient, and runtime-context comparison returns diagnostics rather than
  decisions.
- `docs/quant-duckdb-engine.md` states DuckDB is optional, disabled by default,
  standalone, and does not replace PostgreSQL, the Python backtest engine,
  scanner selection, backtest calculations, portfolio accounting, AI decisions,
  provider logic, or notification routing.

## Current Strengths

- The system already avoids overclaiming by returning explicit
  `professionalReadiness` metadata on backtest read surfaces.
- Stored-first readback, artifact availability, readback integrity, support
  manifests, execution-trace exports, and compare projections give a useful
  audit trail for research runs.
- Universe jobs have a bounded contract: compact per-symbol rows, deterministic
  sequence order, local data coverage diagnostics, explicit skipped/failed
  reasons, and no live provider calls.
- DuckDB is well-contained as an optional factor validation store with lazy
  dependency import, disabled-by-default behavior, bounded payload ingest, and
  read-only diagnostic calls for benchmark/snapshot/coverage paths.

## Capability Gaps

These gaps block any professional quant-readiness claim:

| Domain | Current state | Gap |
| --- | --- | --- |
| Price adjustment | `adjusted_data_state=unknown_or_mixed` | No authoritative adjusted OHLC basis or return-basis contract. |
| Corporate actions | `corporate_action_state=not_ready` | Split/dividend policy and lineage are not explicit enough. |
| Calendar | `available_bars_only` | No exchange-calendar, holiday, half-day, suspension, or trading-session contract. |
| Fill model | `next_open_baseline` with close fallback | No partial fills, no-fill support, liquidity caps, or volume participation model. |
| Costs | `baseline_bps_only` | Tax, stamp duty, spread, impact, and minimum-fee models are absent. |
| Anti-leakage | `basic_bar_close_to_next_open` | Dataset lineage and leakage controls are not broad enough for professional claims. |
| Reproducibility | `partial_without_dataset_lineage` | Dataset/calendar versions and full replay lineage are missing. |
| Universe bias | `survivorship_bias_state=uncontrolled` | No point-in-time universe membership history. |
| Runtime integration | DuckDB diagnostic-only | No accepted path for DuckDB factors to drive scanner ranking, backtest execution, portfolio decisions, AI decisions, or notifications. |

## Recommended Next Steps

1. Keep product wording at "research prototype" until the readiness helper can
   truthfully flip each blocking domain with tests and evidence.
2. Add a golden fixture suite for professional-readiness payloads before
   changing any readiness semantics.
3. If DuckDB factors are promoted beyond diagnostics, introduce a separate
   RFC/task for one explicit consumer path, with rollback and tests proving no
   silent ranking/backtest mutation.
4. For universe backtests, prioritize point-in-time membership and adjusted data
   lineage before concurrency or larger-scale execution.
5. For execution realism, define market-specific fill/cost contracts before
   exposing stronger performance claims.

## Non-Goals Confirmed

- No live provider integration changed.
- No DuckDB runtime promotion changed.
- No scanner ranking changed.
- No backtest calculation changed.
- No portfolio accounting changed.
- No AI prompt/routing/decision behavior changed.
- No broker execution or order placement changed.
- No notification behavior changed.
- No launch approval or public-readiness status changed.

## Rollback

This audit is docs-only. Revert this report and its audit-index entry if the
documentation needs to be removed. No runtime rollback is required.
