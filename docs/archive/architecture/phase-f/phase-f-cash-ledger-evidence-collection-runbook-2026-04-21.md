# Phase F Cash-Ledger Bounded Evidence Collection Runbook

## Goal

Define the smallest practical, reviewer-friendly procedure for collecting real bounded comparison-only evidence for the cash-ledger candidate without changing serving behavior or enabling PostgreSQL serving.

This document is docs-only. It does not authorize or implement PostgreSQL serving for `GET /api/v1/portfolio/cash-ledger`.

## Audience

This runbook is written for a reviewer or operator who:

- can start the backend with a small `.env` change
- can trigger the existing authenticated cash-ledger read flow
- relies primarily on logs, structured diagnostics, and AI assistance
- is not expected to write or modify backend code

## Status Of This Document

This runbook is grounded in the current cash-ledger comparison-only implementation and the active Phase F status/runbook pages.

The detailed boundary and acceptance snapshots that used to sit beside this runbook were consolidated into the active source-of-truth docs.

Code anchors for this runbook:

- [portfolio_service.py](/Users/yehengli/daily_stock_analysis_backend/src/services/portfolio_service.py)
- [storage.py](/Users/yehengli/daily_stock_analysis_backend/src/storage.py)
- [postgres_phase_f.py](/Users/yehengli/daily_stock_analysis_backend/src/postgres_phase_f.py)
- [config.py](/Users/yehengli/daily_stock_analysis_backend/src/config.py)
- [.env.example](/Users/yehengli/daily_stock_analysis_backend/.env.example)
- [test_postgres_phase_f.py](/Users/yehengli/daily_stock_analysis_backend/tests/test_postgres_phase_f.py)

## 1. Preconditions

### 1.1 What must already be true

Before collecting evidence, all of the following should already be true:

- the backend starts successfully with the current Phase F cash-ledger comparison code
- `POSTGRES_PHASE_A_URL` points to a reachable Phase F store
- the legacy endpoint `GET /api/v1/portfolio/cash-ledger` already works normally in legacy mode
- the candidate accounts already exist
- at least one tiny allowlisted account set is known ahead of time
- if non-empty evidence is desired, the sampled account already has cash-ledger rows

### 1.2 What branch/runtime posture this runbook assumes

This runbook assumes the current implemented posture:

- legacy remains the only serving path
- PG is comparison-only
- cash-ledger comparison is owned by `PortfolioService.list_cash_ledger_events(...)`
- the comparison source is `DatabaseManager.get_phase_f_cash_ledger_comparison_candidate(...)`
- the PG-side query is `PostgresPhaseFStore.query_cash_ledger_comparison_candidate(...)`
- per-request diagnostics are emitted through the existing logger
- the collector is bounded and in-process only
- the current compact summary helper is evidence-only, not serving approval

### 1.3 What not to do

Do not do any of the following while using this runbook:

- do not enable or attempt PG serving
- do not broaden into replay-style `list_cash_ledger(..., as_of=...)`
- do not include snapshot-cache or replay-input work
- do not sample write paths as part of this runbook unless those rows already exist through normal product use
- do not allowlist every account
- do not treat this as a rollout or cutover exercise
- do not restart the process mid-run unless you intentionally want to lose in-memory collector state

### 1.4 Important limitation: collector scope

The current collector is in-process only through:

- `PortfolioService.clear_phase_f_cash_ledger_comparison_reports()`
- `PortfolioService.get_phase_f_cash_ledger_comparison_reports()`
- `PortfolioService._build_phase_f_cash_ledger_comparison_evidence_summary_from_collected_reports(...)`

That means:

- logs are the primary reviewer-visible evidence source
- collected reports are only available inside the same running Python process
- a fresh shell or restarted server will not see earlier in-memory reports
- the summary helper is useful for a controlled same-process review, but it is not durable evidence storage

## 2. Exact Bounded Scope

This runbook is limited to:

- endpoint: `GET /api/v1/portfolio/cash-ledger`
- service path: `PortfolioService.list_cash_ledger_events(...)`
- comparison-only behavior
- legacy still serving every response
- a tiny allowlisted account set only

This runbook is not for:

- PG serving
- `record_cash_ledger(...)`
- `delete_cash_ledger_event(...)`
- replay-style `list_cash_ledger(account_id, as_of=...)`
- `_replay_account(...)`
- snapshot-cache semantics
- generic event-history evidence infrastructure

## 3. Required Configuration

### 3.1 Required environment variables

The minimum relevant configuration for bounded evidence collection is:

- `POSTGRES_PHASE_A_URL`
  - required so the Phase F store initializes
- `POSTGRES_PHASE_A_APPLY_SCHEMA`
  - keep the existing project default unless your environment requires otherwise
- `ENABLE_PHASE_F_CASH_LEDGER_COMPARISON=true`
  - required so the comparison-only path actually runs
- `PHASE_F_CASH_LEDGER_COMPARISON_ACCOUNT_IDS=<small comma-separated list>`
  - required to keep the sampling set narrow and reviewable

These flags are parsed in [config.py](/Users/yehengli/daily_stock_analysis_backend/src/config.py) and documented in [.env.example](/Users/yehengli/daily_stock_analysis_backend/.env.example).

### 3.2 Safe example configuration

Use a tiny allowlist. Example:

```env
POSTGRES_PHASE_A_URL=postgresql+psycopg://user:password@127.0.0.1:5432/daily_stock_analysis
POSTGRES_PHASE_A_APPLY_SCHEMA=true
ENABLE_PHASE_F_CASH_LEDGER_COMPARISON=true
PHASE_F_CASH_LEDGER_COMPARISON_ACCOUNT_IDS=101,102
```

Safe characteristics of this example:

- comparison is enabled only for cash-ledger
- only two accounts are in scope
- legacy still serves
- the rest of the system remains outside the sampling run

### 3.3 Allowlist behavior reviewers should expect

The current rollout decision is intentionally strict:

- if the allowlist is empty, comparison does not run
- if `account_id` is missing, comparison does not run
- if the request `account_id` is not allowlisted, comparison does not run
- all of those cases resolve to `comparison_status = "skipped"` with `comparison_skip_reason = "account_not_allowlisted"`

This is conservative by design. It prevents accidental wide-scope comparison.

### 3.4 Unsafe configuration pattern

Avoid:

```env
ENABLE_PHASE_F_CASH_LEDGER_COMPARISON=true
PHASE_F_CASH_LEDGER_COMPARISON_ACCOUNT_IDS=
```

Why this is unsafe or unhelpful for evidence collection:

- the comparison flag is on, but the empty allowlist makes every request fast-skip
- you collect skip evidence instead of compare evidence
- that is useful only for confirming guardrails, not for a bounded acceptance checkpoint

## 4. Legacy Vs PG Role Separation

The current code keeps the roles separate:

- legacy source:
  - `PortfolioRepository.query_cash_ledger(...)`
  - remains the only serving source
- PG comparison source:
  - `DatabaseManager.get_phase_f_cash_ledger_comparison_candidate(...)`
  - delegates to `PostgresPhaseFStore.query_cash_ledger_comparison_candidate(...)`
  - is diagnostic-only for the current phase

The current service behavior is:

1. validate and normalize request shape
2. query legacy rows
3. build the public response from legacy rows
4. optionally compare the legacy result against the PG candidate
5. emit a structured comparison report
6. still return the legacy response

This is comparison-only. It is not a latent PG serving path.

## 5. Safe Sampling Procedure

### 5.1 Choose a tiny allowlisted account set

Choose only `1` to `3` accounts.

Prefer accounts that:

- belong to the authenticated reviewer or test owner you can safely access
- already contain cash-ledger history
- exercise at least one non-empty list page if you want acceptance-strength evidence

Do not choose:

- every active account
- accounts you are not authorized to access
- replay-only accounts when the list route is not representative

### 5.2 Start the backend with bounded comparison enabled

Use the existing backend startup path already standard in your environment. For example:

```bash
python main.py --serve
```

or:

```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Do not change runtime code. Do not create a cash-ledger-specific dev harness for this runbook.

### 5.3 Keep one terminal dedicated to logs

Keep the server running in one terminal and preserve its output.

This matters because the line:

- `Phase F cash-ledger comparison diagnostic: ...`

is the primary reviewer-visible evidence source for this phase.

### 5.4 Trigger only real cash-ledger requests

Use one of these safe request paths:

- the existing authenticated web or desktop flow that already loads `GET /api/v1/portfolio/cash-ledger`
- a copied authenticated API request from an existing operator session

If using a direct HTTP request, keep it bounded. Example shape only:

```bash
curl -s \
  -H "Cookie: <existing-auth-cookie>" \
  "http://127.0.0.1:8000/api/v1/portfolio/cash-ledger?account_id=101&page=1&page_size=20"
```

Only use a direct request if you already have a valid authenticated session.

### 5.5 Recommended bounded request set per allowlisted account

For each allowlisted account, use a tiny but representative request set:

1. Default page:
   - `account_id=<id>&page=1&page_size=20`
2. Direction-filtered page:
   - `account_id=<id>&direction=in&page=1&page_size=20`
3. Opposite direction if data exists:
   - `account_id=<id>&direction=out&page=1&page_size=20`
4. Date-bounded page:
   - `account_id=<id>&date_from=<known-date>&date_to=<known-date-or-window>&page=1&page_size=20`
5. Forced small-page pagination if the account has enough rows:
   - `account_id=<id>&page=1&page_size=1`
   - `account_id=<id>&page=2&page_size=1`

This keeps the sampling boundary aligned with the current code-owned parity dimensions:

- `account_id`
- `date_from`
- `date_to`
- normalized `direction`
- `page`
- `page_size`

### 5.6 Target request volume

Keep the run small.

Recommended starting volume:

- `4` to `6` requests per allowlisted account
- `1` to `3` allowlisted accounts total

That is enough to inspect:

- default list behavior
- direction filter behavior
- date-window behavior
- pagination behavior

without broadening the candidate.

## 6. What Reports And Summaries A Reviewer Should Expect

### 6.1 Per-request diagnostic report

Each comparison attempt or skip should emit a structured report with:

- `report_model = "phase_f_cash_ledger_comparison_diagnostic_v1"`
- `candidate = "portfolio_cash_ledger_list"`
- `comparison_status`
- `comparison_attempted`
- `comparison_decision`
- `comparison_source = "phase_f_pg_cash_ledger_candidate"`
- `comparison_skip_reason`
- `mismatch_class`
- `blocking_level`
- `request_context`
- `owner_context`
- `legacy_summary`
- `pg_summary`
- `first_mismatch_*` fields when relevant
- `query_failure_detail` when relevant
- `fallback_decision`

### 6.2 Legacy and PG summaries inside the report

For matched, mismatch, and query-failure review, the summary objects describe:

- `total`
- `page`
- `page_size`
- `page_item_count`
- `ordered_ids`

These fields are the current compact evidence surface for count, pagination, and ordering review.

### 6.3 Optional in-process evidence summary

If the reviewer or AI assistant can inspect the same running process, the current summary helper can aggregate collected reports into:

- `summary_model = "phase_f_cash_ledger_comparison_evidence_summary_v1"`
- `candidate = "portfolio_cash_ledger_list"`
- `total_reports`
- `total_attempted`
- `total_skipped`
- `total_matched`
- `total_mismatched`
- `total_query_failures`
- `mismatch_counts_by_class`
- `query_failure_count`
- `compared_account_ids`
- `skipped_account_ids`
- `allowlisted_account_ids`
- `uncovered_allowlisted_account_ids`
- `matched_empty_reports`
- `matched_non_empty_reports`
- `non_empty_match_observed`
- `hard_blocking_issue_observed`
- `hard_blocking_issue_classes`
- `evidence_strength`
- `evidence_is_thin`

The summary helper is useful for acceptance review, but it is still bounded and in-process only.

## 7. How To Interpret Current Statuses

### 7.1 `skipped`

Interpretation:

- comparison did not run
- the usual current reason is `account_not_allowlisted`
- legacy still served the response

Reviewer meaning:

- good for confirming rollout discipline
- not useful as acceptance-strength parity evidence by itself

### 7.2 `matched`

Interpretation:

- comparison ran
- the current request context matched
- `total`, page-local membership, ordered ids, and contract-visible fields matched after normalization
- legacy still served the response

Reviewer meaning:

- this is the positive parity signal for the current request shape
- non-empty matches matter more than empty-only matches

### 7.3 `mismatch`

Interpretation:

- comparison ran
- at least one bounded parity check failed
- the report should identify the first mismatch field and mismatch class
- legacy still served the response

Reviewer meaning:

- treat as a hard blocker for this bounded evidence window until explained
- current mismatch classes include:
  - `count_mismatch`
  - `pagination_mismatch`
  - `ordering_mismatch`
  - `filter_mismatch`
  - `owner_scope_mismatch`
  - `payload_field_mismatch`

### 7.4 `query_failure`

Interpretation:

- comparison was attempted
- the PG comparison source could not be loaded or queried
- legacy still served the response

Reviewer meaning:

- this is not serving impact today
- it is still a hard blocker for acceptance-strength comparison evidence in the sampled window
- the current code-grounded detail to watch is `phase_f_cash_ledger_pg_source_unavailable`

## 8. How To Interpret `evidence_strength`

The current summary helper uses three values:

- `thin`
  - no meaningful attempted comparison evidence yet
  - this usually means only skips, zero attempted comparisons, or otherwise insufficient review coverage
- `empty_only`
  - matched reports exist, but only over empty result sets
  - useful as a structural checkpoint, not a strong acceptance checkpoint
- `non_empty_sampled`
  - at least one matched non-empty request exists
  - this is the strongest current comparison-only evidence class

## 9. What Counts As Acceptance-Strength Evidence For This Phase

This section is a reviewer-facing interpretation of the current evidence fields. It is grounded in the current summary helper and tests, but the acceptance rule itself is a review conclusion rather than a runtime-enforced gate.

Treat the evidence as acceptance-strength for the current bounded comparison-only checkpoint only when all of the following are true:

- the sampled requests are inside the current cash-ledger list boundary
- at least one allowlisted account produced a real non-empty `matched` report
- the summary shows `evidence_strength = "non_empty_sampled"`
- the summary shows `hard_blocking_issue_observed = false`
- the summary shows no uncovered allowlisted accounts for the intended review set
- the observed results remain comparison-only with legacy still serving

Do not treat any of the following as acceptance-strength by themselves:

- skips only
- query failures mixed into the sampled window
- mismatches that still need explanation
- matched empty results only
- runs where the intended allowlisted accounts were not actually sampled

## 10. Final Boundary Statement

This runbook is for bounded comparison-only evidence collection.

It is explicitly not:

- PG serving readiness
- PG serving approval
- replay or snapshot expansion
- write-path validation
- a generic evidence platform

The correct output of this runbook is a narrow, reviewer-readable evidence set for `GET /api/v1/portfolio/cash-ledger` while legacy remains the only serving authority.
