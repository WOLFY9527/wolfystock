# Phase F Corporate-Actions Non-Empty Evidence Collection Plan

## Goal

Define the smallest reviewer-friendly procedure for collecting bounded non-empty comparison-only evidence for corporate-actions on a real local PostgreSQL store without changing serving behavior.

This document is docs-only. It does not authorize or implement PostgreSQL serving for `GET /api/v1/portfolio/corporate-actions`.

## Status Of This Document

This plan complements the active Phase F runbook and status pages.

The older boundary and status-index snapshots were consolidated into the active source-of-truth docs, so this file now stands as a historical plan record only.

Code anchors used for this plan:

- [tests/test_postgres_phase_f_real_pg.py](/Users/yehengli/daily_stock_analysis/tests/test_postgres_phase_f_real_pg.py)
- [portfolio_service.py](/Users/yehengli/daily_stock_analysis/src/services/portfolio_service.py)
- [postgres_phase_f.py](/Users/yehengli/daily_stock_analysis/src/postgres_phase_f.py)
- [storage.py](/Users/yehengli/daily_stock_analysis/src/storage.py)
- [portfolio_repo.py](/Users/yehengli/daily_stock_analysis/src/repositories/portfolio_repo.py)

## 1. Exact Bounded Evidence Harness

The most conservative non-empty evidence harness for this pass is:

- isolated local SQLite legacy store
- real local PostgreSQL Phase F store
- existing `PortfolioService.list_corporate_action_events(...)` comparison path
- existing request-local comparison diagnostics
- existing in-process corporate-actions comparison report collector

This harness is intentionally narrow because it proves the current comparison-only implementation against a real PG candidate source without introducing:

- PG serving
- endpoint schema changes
- replay or snapshot work
- repo-wide evidence infrastructure

## 2. Exact Seed Dataset

Use one allowlisted account only.

Use exactly three corporate-action rows:

1. `2026-04-01`, `symbol=AAPL`, `action_type=cash_dividend`, `cash_dividend_per_share=0.25`, `note=phase_f_corp_actions_non_empty_seed_1`
2. `2026-04-02`, `symbol=AAPL`, `action_type=split_adjustment`, `split_ratio=2.0`, `note=phase_f_corp_actions_non_empty_seed_2`
3. `2026-04-03`, `symbol=MSFT`, `action_type=cash_dividend`, `cash_dividend_per_share=0.4`, `note=phase_f_corp_actions_non_empty_seed_3`

Why this exact seed set is sufficient:

- default list becomes non-empty
- `page_size=1` becomes non-empty
- `page=2&page_size=1` becomes non-empty
- `action_type=cash_dividend` becomes a simple supported non-empty filter shape

It intentionally avoids:

- broader account coverage
- date-window expansion
- mixed-owner scope
- replay-style `as_of` semantics

## 3. Exact Request Shapes

The bounded request set for this pass is exactly:

1. default non-empty list
   - `account_id=<allowlisted_id>&page=1&page_size=20`
2. forced small page
   - `account_id=<allowlisted_id>&page=1&page_size=1`
3. second page
   - `account_id=<allowlisted_id>&page=2&page_size=1`
4. one simple supported filter shape
   - `account_id=<allowlisted_id>&action_type=cash_dividend&page=1&page_size=20`

This request set is intentionally small and maps directly to the current public contract.

## 4. Exact Collection Procedure

Use the existing focused real-PG unittest entrypoint:

```bash
POSTGRES_PHASE_A_REAL_DSN=<local_pg_dsn> \
python3 -m pytest tests/test_postgres_phase_f_real_pg.py -k corporate_actions_comparison_collects_bounded_non_empty_evidence -q -p no:cacheprovider
```

What this test does:

1. creates an isolated legacy SQLite database
2. points Phase F storage at a real local PostgreSQL DSN
3. seeds one account with three corporate-action rows through the normal write path
4. enables corporate-actions comparison-only mode with a one-account allowlist
5. executes the four bounded request shapes
6. captures the emitted in-process comparison reports

## 5. Expected Evidence Surface

The expected reviewer-visible evidence from this plan is:

- exact request contexts for all sampled requests
- per-request `comparison_status`
- per-request non-empty ordered id parity
- per-request legacy-vs-PG summary parity
- explicit absence or presence of `mismatch` and `query_failure`

The current corporate-actions line does not yet expose a separate compact evidence summary helper like cash-ledger. For this pass, the collected request-local reports are the authoritative bounded evidence surface.

The expected quality target for this pass is:

- every sampled request is non-empty
- `comparison_attempted = true`
- `comparison_status = "matched"`
- no `mismatch`
- no `query_failure`

## 6. Bounded Blocker Rule

If `POSTGRES_PHASE_A_REAL_DSN` is unavailable or no local PostgreSQL instance is reachable, stop at that point.

Do not respond to that blocker by:

- enabling PG serving
- broadening into generic comparison infrastructure
- expanding into replay or snapshot work
- broadening request coverage

The correct response to that blocker is to leave the runtime unchanged and record the evidence gap explicitly.
