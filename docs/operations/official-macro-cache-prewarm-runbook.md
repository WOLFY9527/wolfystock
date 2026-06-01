# Official Macro Cache Prewarm Runbook

Status: operator-facing readiness and dry-run guide for official macro cache
prewarm.

Scope:

- `scripts/diagnose_official_macro_activation.py --cache-readiness`
- `scripts/official_macro_cache_prewarm.py`
- existing Market Overview cache refresh path only
- readiness/dry-run evidence for official USD TWI and Fed liquidity cache rows

This runbook is diagnostics-only. It does not authorize provider promotion,
source-confidence promotion, score contribution, provider rerouting, MarketCache
semantic changes, or live-call path changes.

## What This Supports

When cache readiness is healthy, the existing Market Overview cache refresh path
can prewarm the following panels:

- `rates`: US rates and curve context used by Market Overview
- `macro`: USD TWI, US rates/curve, and Fed liquidity context used by Market
  Overview

Operationally, a ready cache also improves downstream evidence availability for:

- Market Overview
- Liquidity Monitor

This remains observation/evidence readiness only. It does not grant runtime
promotion or scoring authority on its own.

## Required Official Series

Readiness is fail-closed on the required official cache series below.

| Group | Symbol | Series | Freshness policy |
| --- | --- | --- | --- |
| USD pressure | `USD_TWI` | `DTWEXBGS` | `official_h10_weekly_batch_t_plus_7` |
| Fed liquidity | `FED_ASSETS` | `WALCL` | `official_weekly_fed_liquidity_t_plus_7` |
| Fed liquidity | `FED_RRP` | `RRPONTSYD` | `official_daily_us_weekday_t_plus_1` |
| Fed liquidity | `TGA` | `WTREGEN` | `official_weekly_fed_liquidity_t_plus_7` |
| Fed liquidity | `RESERVES` | `WRESBAL` | `official_weekly_fed_liquidity_t_plus_7` |

The write path also refreshes existing US rates/curve rows in Market Overview:

- `US2Y` / `DGS2`
- `US10Y` / `DGS10`
- `US30Y` / `DGS30`
- `SOFR` / `SOFR`
- `US10Y2Y` / `T10Y2Y`
- `US10Y3M` / `T10Y3M`

Those rates/curve rows benefit from the existing prewarm path, but this script's
readiness gate remains an official macro cache-readiness diagnostic. It does
not redefine provider routing or add a new live-readiness contract.

## Readiness States

- `ready`: all required official cache series are fulfilled, fresh enough, and
  still marked `sourceAuthorityAllowed=true` plus
  `scoreContributionAllowed=true` in the bounded readiness probe.
- `blocked`: at least one required series is missing or stale, or the bounded
  readiness probe reports an authority/score block.

Common blocked reasons:

- `series_coverage`: one or more required series are missing.
- `stale_series`: one or more required series are stale.
- `source_authority_blocked`: the readiness probe rejected source authority.
- `score_contribution_blocked`: the readiness probe rejected score use.
- `unexpected_error`: the bounded readiness probe failed and the script fell
  back to a safe blocked summary.

## Dry-Run vs Write

Dry-run is the default:

```bash
python3 scripts/official_macro_cache_prewarm.py
```

Behavior:

- does not construct the write service path when `--write` is absent
- does not mutate Market Overview snapshots or cache rows
- emits required-series readiness evidence plus write-plan evidence

Write mode is explicit:

```bash
python3 scripts/official_macro_cache_prewarm.py --write
```

Behavior:

- uses the existing Market Overview prewarm path only after readiness is `ready`
- writes the same `rates` and `macro` cache rows the current service already
  knows how to refresh
- does not change cache write semantics, live provider behavior, or provider
  order

Validation for this task must not execute `--write`.

## Cache-Readiness Parity Diagnostic

Use the bounded activation diagnostic when operators only need the official
macro readiness gate without write-plan evidence:

```bash
python3 scripts/diagnose_official_macro_activation.py --cache-readiness
```

This diagnostic-only mode shares the same readiness vocabulary as the prewarm
dry-run:

- `requiredSeries`: the bounded official series gate
- `requiredSeriesStatus`: compact per-series status map
- `seriesReadiness`: per-series evidence with `group`, `symbol`,
  `freshnessPolicy`, `status`, and `blockedReason`
- `readiness` / `reason`: top-level ready vs blocked summary
- `operatorNextGate`: what to do before entering the prewarm workflow

This mode does not emit `writeEvidence` and does not attempt cache writes. Use
`scripts/official_macro_cache_prewarm.py` when operators need write-plan
diagnostics or the separately authorized write workflow.

## JSON Evidence To Read

The prewarm script emits compact JSON. The main operator fields are:

- `readiness` / `reason`: top-level gate result
- `requiredSeries`, `fulfilledSeries`, `missingSeries`, `staleSeries`
- `seriesReadiness`: per-series evidence with `group`, `symbol`,
  `freshnessPolicy`, `status`, and `blockedReason`
- `writeEvidence`: grouped write-plan evidence
- `cacheRowsWouldWrite` / `cacheRowsWritten`
- `writeEfficacy`
- `writtenButNotScoreGradeReason`
- `targetPanels`: which Market Overview cache keys would be refreshed

The separate `diagnose_official_macro_activation.py --cache-readiness`
diagnostic uses the same `requiredSeries` and `seriesReadiness` vocabulary, and
adds `operatorNextGate` to point operators back into this prewarm workflow.

Expected dry-run evidence:

- `writeAttempted=false`
- `cacheRowsWouldWrite=2`
- `cacheRowsWritten=0`
- `writeEfficacy=not_written`
- `writtenButNotScoreGradeReason=write_not_attempted`

Expected blocked write evidence:

- `result=readiness_blocked`
- `writeAttempted=false`
- no new cache writes attempted

Expected successful write evidence:

- `result=write_attempted`
- `cacheRowsWritten=2`
- `panels[*].targetDiagnostics` explains whether returned targets remained
  score-grade usable after the existing write path finished

## No-Promotion Semantics

This workflow must remain fail-closed and observation-first:

- no provider-order change
- no new live provider path
- no MarketCache TTL/SWR/cold-start semantic change
- no source-confidence promotion
- no score-gate change
- no automatic upgrade from cached readiness to trading/scoring authority

Even when `readiness=ready`, the result only means the official macro cache is
ready for the existing prewarm path. It does not mean:

- the provider is globally enabled
- degraded/fallback data became live
- Liquidity Monitor scoring rules changed
- Market Overview authority semantics changed

## Recommended Operator Flow

1. Run `python3 scripts/diagnose_official_macro_activation.py --help`.
2. Run `python3 scripts/diagnose_official_macro_activation.py --cache-readiness`
   and inspect `requiredSeries`, `seriesReadiness`, and `operatorNextGate`.
3. Run `python3 scripts/official_macro_cache_prewarm.py --help`.
4. Run the default dry-run and inspect `readiness`, `reason`,
   `seriesReadiness`, and `writeEvidence`.
5. If blocked, remediate the missing/stale official cache inputs first.
6. Only after the cache is ready, use the separately authorized write workflow.
