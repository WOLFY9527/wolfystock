# Phase F Trades-List Bounded Evidence Collection Runbook

## Goal

Define the smallest practical, operator-friendly procedure for collecting real bounded comparison evidence for the trades-list candidate without changing serving behavior or enabling PostgreSQL serving.

This document is docs-only. It does not authorize or implement PostgreSQL serving for `GET /api/v1/portfolio/trades`.

## Audience

This runbook is written for an operator who:

- can start the backend with a small `.env` change
- can use the existing authenticated product flow or a copied API request
- relies primarily on logs, emitted diagnostics, and AI assistance
- is not expected to write code

## Status Of This Document

This runbook builds on:

- [phase-f-trades-list-acceptance-evidence-review-2026-04-20.md](/Users/yehengli/daily_stock_analysis_backend/docs/architecture/phase-f-trades-list-acceptance-evidence-review-2026-04-20.md)
- [phase-f-trades-list-serving-mode-design-acceptance-plan-2026-04-20.md](/Users/yehengli/daily_stock_analysis_backend/docs/architecture/phase-f-trades-list-serving-mode-design-acceptance-plan-2026-04-20.md)
- [phase-f-trades-list-comparison-promotion-readiness-audit-2026-04-20.md](/Users/yehengli/daily_stock_analysis_backend/docs/architecture/phase-f-trades-list-comparison-promotion-readiness-audit-2026-04-20.md)

Code anchors for this runbook:

- [portfolio_service.py](/Users/yehengli/daily_stock_analysis_backend/src/services/portfolio_service.py)
- [config.py](/Users/yehengli/daily_stock_analysis_backend/src/config.py)
- [.env.example](/Users/yehengli/daily_stock_analysis_backend/.env.example)
- [portfolio.py](/Users/yehengli/daily_stock_analysis_backend/api/v1/endpoints/portfolio.py)
- [storage.py](/Users/yehengli/daily_stock_analysis_backend/src/storage.py)
- [postgres_phase_f.py](/Users/yehengli/daily_stock_analysis_backend/src/postgres_phase_f.py)

## 1. Preconditions

### 1.1 What must already exist

Before collecting evidence, all of the following must already be true:

- you are on the intended Phase F branch or an equivalent review branch
- the backend starts successfully with the current Phase F trades-list comparison code
- PostgreSQL Phase F storage is reachable through `POSTGRES_PHASE_A_URL`
- the existing API path `GET /api/v1/portfolio/trades` works normally in legacy mode
- the candidate accounts already exist and already have real trade history to query
- you have a valid authenticated user session for the account owner you are sampling

### 1.2 What branch and runtime state this runbook assumes

This runbook assumes the currently implemented behavior:

- legacy is still the only serving path
- PG is comparison-only
- trades-list comparison remains service-owned in `PortfolioService.list_trade_events(...)`
- comparison diagnostics are emitted through the existing logger
- the in-process collector is bounded and not durable

### 1.3 What not to do

Do not do any of the following while using this runbook:

- do not enable or attempt PG serving
- do not sample cash-ledger or corporate-actions endpoints
- do not include replay-input or snapshot-cache work
- do not allowlist every account
- do not treat this as a production-wide rollout
- do not restart the process mid-run unless you intentionally want to lose in-memory collector state

### 1.4 Important limitation: collector scope

The current comparison report collector is in-process only.

That means:

- reports collected inside a running API process stay inside that process
- a separate fresh Python shell will not see those in-memory reports
- logs are the primary evidence source for operators
- collector-based summary/review is optional and only works when AI assistance can inspect the same live process or when sampling is done inside one controlled Python process

## 2. Exact Bounded Scope

This runbook is limited to:

- endpoint: `GET /api/v1/portfolio/trades`
- comparison-only behavior
- legacy still serving every response
- a tiny allowlisted account set only

This runbook is not for:

- PG serving
- cash-ledger
- corporate-actions
- replay-input
- snapshot-cache
- write-path validation
- generic multi-endpoint observability

## 3. Required Configuration

### 3.1 Required environment variables

The minimum relevant config for bounded evidence collection is:

- `POSTGRES_PHASE_A_URL`
  - required so the Phase F PostgreSQL stores initialize
- `POSTGRES_PHASE_A_APPLY_SCHEMA`
  - keep existing project default unless your environment requires otherwise
- `ENABLE_PHASE_F_TRADES_LIST_COMPARISON=true`
  - required so the comparison-only path actually runs
- `PHASE_F_TRADES_LIST_COMPARISON_ACCOUNT_IDS=<small comma-separated list>`
  - required to keep the sampling set narrow

### 3.2 Safe example configuration

Use a tiny allowlist. Example:

```env
POSTGRES_PHASE_A_URL=postgresql+psycopg://user:password@127.0.0.1:5432/daily_stock_analysis
POSTGRES_PHASE_A_APPLY_SCHEMA=true
ENABLE_PHASE_F_TRADES_LIST_COMPARISON=true
PHASE_F_TRADES_LIST_COMPARISON_ACCOUNT_IDS=101,102
```

Safe characteristics of this example:

- comparison is enabled only for trades-list
- only two accounts are in scope
- legacy still serves
- the rest of the system remains outside the sampling run

### 3.3 Unsafe configuration patterns

Avoid:

```env
ENABLE_PHASE_F_TRADES_LIST_COMPARISON=true
PHASE_F_TRADES_LIST_COMPARISON_ACCOUNT_IDS=
```

Why this is unsafe for evidence collection:

- an empty allowlist means comparison may run for every trades-list request
- that widens sampling scope unnecessarily
- it makes the evidence harder to review as a bounded candidate set

### 3.4 Relevant request shape

The current bounded endpoint supports:

- `account_id`
- `date_from`
- `date_to`
- `symbol`
- `side`
- `page`
- `page_size`

The route is:

- `GET /api/v1/portfolio/trades`

## 4. Safe Sampling Procedure

### 4.1 Choose a tiny allowlisted account set

Choose only `1` to `3` accounts.

Use accounts that:

- belong to the same authenticated operator or test owner you can safely access
- already contain real trade data
- have enough variation to exercise at least a few filters

Prefer accounts that give you:

- at least one account with multiple trade rows
- at least one account where pagination can be exercised
- at least one account with both buy and sell history if available

Do not choose:

- every active account
- accounts you are not authorized to access
- accounts with known broken or incomplete legacy data

### 4.2 Start the backend with bounded comparison enabled

Use the existing backend startup path. For example:

```bash
python main.py --serve
```

or:

```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Use whichever path is already standard in your environment. Do not change runtime code.

### 4.3 Keep one terminal dedicated to logs

Keep the server running in one terminal and preserve its output.

This matters because the log line:

- `Phase F trades-list comparison diagnostic: ...`

is the primary operator-visible evidence source for this run.

### 4.4 Trigger only real trades-list requests

Use one of these safe request paths:

- the existing authenticated web or desktop flow that already loads `GET /api/v1/portfolio/trades`
- a copied authenticated API request from an existing operator session

If using a direct HTTP request, keep it bounded. Example shape only:

```bash
curl -s \
  -H "Cookie: <existing-auth-cookie>" \
  "http://127.0.0.1:8000/api/v1/portfolio/trades?account_id=101&page=1&page_size=20"
```

Only use a direct request if you already have a valid authenticated session. Do not create a new bypass or temporary auth path for this run.

### 4.5 Recommended request sample set per allowlisted account

For each allowlisted account, aim for a tiny but representative request set:

1. Default first page:
   - `account_id=<id>&page=1&page_size=20`
2. Symbol-filtered page:
   - `account_id=<id>&symbol=<known-symbol>&page=1&page_size=20`
3. Side-filtered page:
   - `account_id=<id>&side=buy&page=1&page_size=20`
4. Date-bounded page:
   - `account_id=<id>&date_from=<known-date>&date_to=<known-date-or-window>&page=1&page_size=20`
5. Forced small-page pagination:
   - `account_id=<id>&page=1&page_size=1`
   - `account_id=<id>&page=2&page_size=1`

If the account has enough history, this gives a bounded sample of:

- unfiltered list behavior
- filter behavior
- ordering behavior
- pagination behavior

### 4.6 Target request volume

Keep the run small.

Recommended starting volume:

- `5` to `8` requests per allowlisted account
- `1` to `3` allowlisted accounts total

That yields roughly:

- `5` to `24` total requests

This is enough to move beyond an empty snapshot without widening scope into a large rollout.

### 4.7 How to avoid widening scope

To keep the run bounded:

- only query `GET /api/v1/portfolio/trades`
- only use the explicit allowlisted account ids
- do not browse unrelated portfolio screens during the run
- do not remove the allowlist
- do not raise the sample size because “more data might help”

The goal is first real evidence, not broad coverage.

## 5. What Evidence To Collect

### 5.1 Primary evidence: emitted comparison diagnostics

Capture the emitted log lines from the running backend that contain:

- `Phase F trades-list comparison diagnostic:`

Those diagnostics are the primary evidence for operators because they are emitted by the actual request path.

Capture enough surrounding context to identify:

- timestamp
- request sequence
- account id if present in `request_context`
- `comparison_status`
- `mismatch_class`
- `fallback_decision`
- any `query_failure_detail`

### 5.2 Secondary evidence: collected reports

If AI assistance can inspect the same live process or if sampling is done inside one controlled Python process, also capture:

- `PortfolioService.get_phase_f_trade_list_comparison_reports()`

Important:

- do not rely on a new Python shell to read reports from a different running process
- if the process restarted, assume the in-memory collector state is gone

### 5.3 Evidence summary output

If same-process inspection is available, capture:

```python
service._build_phase_f_trade_list_comparison_evidence_summary_from_collected_reports(
    allowlisted_account_ids=[...],
)
```

Record at minimum:

- `total_reports`
- `total_attempted`
- `total_skipped`
- `total_matched`
- `total_mismatched`
- `total_query_failures`
- `mismatch_counts_by_class`
- `compared_account_ids`
- `uncovered_allowlisted_account_ids`
- `evidence_is_thin`

### 5.4 Promotion-readiness review output

If same-process inspection is available, also capture:

```python
service._build_phase_f_trade_list_promotion_readiness_review_from_collected_reports(
    allowlisted_account_ids=[...],
)
```

Record at minimum:

- `review_status`
- `promotion_discussion_ready`
- `blocking_reasons`
- `hard_blocking_mismatch_observed`
- `hard_blocking_mismatch_classes`
- `query_failures_observed`

### 5.5 Helpful context for later AI review

Preserve:

- the exact allowlisted account ids used
- the exact request shapes exercised
- the approximate request count
- whether any requests were skipped because of allowlist behavior
- whether the backend process was restarted during the run

Without that context, later evidence review will be weaker.

## 6. When To Stop

Stop the sampling run immediately if any of the following happens:

- a hard-blocking mismatch is observed
- repeated `query_failure` diagnostics are observed
- any owner-scope mismatch or suspicious cross-account leakage is observed
- the backend begins emitting diagnostics for accounts outside the intended allowlist
- the run starts touching endpoints outside `GET /api/v1/portfolio/trades`

Stop the run and mark it incomplete if:

- the request count is too low to move beyond thin evidence
- the sampled accounts do not have enough trade history to exercise filters or pagination
- the process restarts and the in-memory collector state is lost before capture

Do not continue sampling after a suspicious owner-scope issue just to “collect more data.”

## 7. Post-Run Review Procedure

After the run:

1. Save the captured log excerpts for the trades-list comparison diagnostics.
2. Record the allowlisted account ids and the exact request shapes exercised.
3. If available, capture same-process:
   - collected reports
   - evidence summary output
   - promotion-readiness review output
4. Create a follow-up acceptance review artifact under `docs/architecture/` that states:
   - what was sampled
   - how many requests ran
   - what statuses were observed
   - what mismatch classes were observed
   - whether evidence is still thin
   - whether allowlisted coverage was complete
   - what blockers remain

The follow-up artifact should stay bounded to the sampled trades-list candidate only.

## 8. Recommended Next Move After Sampling

The single best next step after a real bounded sampling run is:

- produce a new trades-list acceptance-evidence review artifact based on the captured sampled evidence

Why this is the highest-ROI next move:

- the current blocker is lack of real collected evidence
- the existing summary and review helpers already define the acceptance vocabulary
- the next decision should be based on sampled evidence, not on more design expansion

What should still remain out of scope after sampling:

- PG serving
- cash-ledger expansion
- corporate-actions expansion
- replay-input or snapshot work
- generic telemetry infrastructure

## Final Conclusion

The current comparison-only path already has enough plumbing.

The correct next operational step is a tiny, allowlist-scoped evidence collection run that:

- exercises only `GET /api/v1/portfolio/trades`
- preserves legacy serving
- captures emitted diagnostics as the primary evidence source
- optionally captures same-process collector summary and review output

That is the minimum practical path to move from an empty evidence snapshot to a reviewable sampled evidence set.
