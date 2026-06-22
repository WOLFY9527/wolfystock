# Phase F Cash-Ledger Non-Empty Evidence Collection Plan

## Goal

Define the smallest reviewer-friendly procedure for collecting bounded non-empty comparison-only evidence for cash-ledger on a real local PostgreSQL store without changing serving behavior.

This document is docs-only. It does not authorize or implement PostgreSQL serving for `GET /api/v1/portfolio/cash-ledger`.

## Status Of This Document

This plan complements the active Phase F runbook and status pages.

The older boundary and acceptance snapshots were consolidated into the active source-of-truth docs, so this file now stands as a historical plan record only.

Code anchors used for this plan:

- [tests/test_postgres_phase_f_real_pg.py](/Users/yehengli/daily_stock_analysis_backend/tests/test_postgres_phase_f_real_pg.py)
- [portfolio_service.py](/Users/yehengli/daily_stock_analysis_backend/src/services/portfolio_service.py)
- [postgres_phase_f.py](/Users/yehengli/daily_stock_analysis_backend/src/postgres_phase_f.py)
- [storage.py](/Users/yehengli/daily_stock_analysis_backend/src/storage.py)
- [portfolio_repo.py](/Users/yehengli/daily_stock_analysis_backend/src/repositories/portfolio_repo.py)

## 1. Exact Bounded Evidence Harness

The most conservative non-empty evidence harness for this pass is:

- isolated local SQLite legacy store
- real local PostgreSQL Phase F store
- existing `PortfolioService.list_cash_ledger_events(...)` comparison path
- existing in-process collector
- existing evidence summary helper

This harness is intentionally narrow because it proves the current comparison-only implementation against a real PG candidate source without introducing:

- PG serving
- endpoint schema changes
- replay or snapshot work
- broad runtime harnesses

## 2. Exact Seed Dataset

Use one allowlisted account only.

Use exactly three cash-ledger rows:

1. `2026-04-01`, `direction=in`, `amount=100.0`, `currency=USD`, `note=phase_f_cash_non_empty_seed_1`
2. `2026-04-02`, `direction=out`, `amount=25.0`, `currency=USD`, `note=phase_f_cash_non_empty_seed_2`
3. `2026-04-03`, `direction=in`, `amount=50.0`, `currency=USD`, `note=phase_f_cash_non_empty_seed_3`

Why this exact seed set is sufficient:

- default list becomes non-empty
- `page_size=1` becomes non-empty
- `page=2&page_size=1` becomes non-empty
- `direction=in` becomes a simple supported non-empty filter shape

It intentionally avoids:

- wider account coverage
- date-window explosion
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
   - `account_id=<allowlisted_id>&direction=in&page=1&page_size=20`

This request set is intentionally small and maps directly to the current public contract.

## 4. Exact Collection Procedure

Use the existing focused real-PG unittest entrypoint:

```bash
POSTGRES_PHASE_A_REAL_DSN=<local_pg_dsn> \
python -m pytest tests/test_postgres_phase_f_real_pg.py -k cash_ledger_comparison_collects_bounded_non_empty_evidence -q
```

What this test does:

1. creates an isolated legacy SQLite database
2. points Phase F storage at a real local PostgreSQL DSN
3. seeds one account with three cash-ledger rows through the normal write path
4. enables cash-ledger comparison-only mode with a one-account allowlist
5. executes the four bounded request shapes
6. captures emitted in-process comparison reports
7. derives the compact evidence summary from collected reports

## 5. Expected Evidence Surface

The expected reviewer-visible evidence from this plan is:

- exact request contexts for all sampled requests
- per-request `comparison_status`
- per-request ordered id parity
- per-request legacy-vs-PG summary parity
- one compact evidence summary

The expected summary quality target for this pass is:

- `evidence_strength = "non_empty_sampled"`
- `matched_non_empty_reports > 0`
- `total_query_failures = 0`
- `total_mismatched = 0`
- `uncovered_allowlisted_account_ids = []`

## 6. Bounded Blocker Rule

If `POSTGRES_PHASE_A_REAL_DSN` is unavailable or no local PostgreSQL instance is reachable, stop at that point.

Do not respond to that blocker by:

- enabling PG serving
- broadening into generic comparison infrastructure
- expanding into replay or snapshot work
- broadening request coverage

The correct response to that blocker is to leave the runtime unchanged and record the evidence gap explicitly.
