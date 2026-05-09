# WolfyStock Provider Budget and Routing Rules

Purpose: stable rules for free/limited API usage, research modes, provider budgeting, and diagnostics.

## Background

WolfyStock uses multiple free or limited data providers. API quota must be protected. Expensive providers should be used only when the mode and data need justify them.

Existing concepts:
- provider capability metadata
- cache-first plan advisor
- research modes: `quick`, `standard`, `deep`
- provider usage ledger diagnostics
- optional category deadlines
- search/news/social sentiment dedupe

## Core principles

1. Cache/local first.
2. Required data and optional enrichment are separate.
3. Optional providers must be budgeted and deadline-bounded.
4. Free API quota is scarce; do not spend it on broad/low-value scans.
5. Fallback/stale/mock/synthetic data must never be marked live.
6. Provider diagnostics must be sanitized.
7. Do not add new live provider paths without explicit approval.

## Research modes

### quick

Purpose:
- interactive fast analysis
- avoid optional external calls
- preserve quota

Expected behavior:
- cache/local/yfinance first
- shortest optional deadline
- news/social sentiment usually skipped
- fundamentals capped or skipped if optional
- suitable for UI previews and fast decisions

### standard

Purpose:
- balanced default explicit mode
- limited enrichment
- sane timeout/deadline behavior

Expected behavior:
- cache-first
- limited optional supplemental categories
- limited news/sentiment
- deadline aligned with fast decision budget

### deep

Purpose:
- richer research on selected symbols
- still budgeted and bounded

Expected behavior:
- broader optional enrichment
- may allow news/social sentiment
- still has max call budgets
- not unlimited
- generally not for every scanner candidate

## Required vs optional categories

Required examples:
- realtime quote if needed for decision quality
- candles/OHLCV for technical quality
- data needed to avoid invalid analysis

Optional examples:
- news enrichment
- social sentiment
- deep fundamentals
- alternate provider cross-checks
- explanatory context

Rules:
- Required categories must not be skipped by optional budget deadlines.
- Optional categories may be skipped by mode/budget/deadline.
- Optional skip should produce sanitized gap metadata, not raw errors.

## Provider order

Do not change provider global order unless explicitly required.
Do not reorder live provider fallback silently.
Do not add new live call paths in a diagnostics/metadata task.

Allowed:
- advisory-only plan suggestions
- metadata indicating preferred provider classes
- optional budget skip before calls
- deadline-bounded optional fanout preserving call semantics

## Provider capability metadata

Capability metadata should describe:
- provider id/name
- domains
- markets
- quota class
- freshness class
- recommended TTLs
- scanner/backtest eligibility
- quick/standard/deep eligibility
- domain priority hints
- risk/operator notes

It must not import live provider clients or read credentials.

## Usage ledger

Provider usage ledger may record:
- provider/category attempted
- cache hit
- skipped by cache
- skipped by budget
- skipped by mode
- optional deadline exceeded
- provider timeout
- success/failure
- sanitized reason code
- researchMode
- bounded metadata

Must not store:
- raw provider payload
- request body
- response body
- headers
- cookies
- Authorization
- API keys
- tokens
- secrets
- full stack traces

Use bounded ring buffer unless durable storage is explicitly requested.

## News / search / social sentiment

Rules:
- Tavily/GNews/Social Sentiment are not broad scanner defaults.
- Use them for standard/deep or top-N enrichment only.
- Cache empty filtered gaps.
- Deduplicate identical symbol/query/freshness calls.
- Log bounded key/count summaries, not raw payloads.

## Scanner usage

Scanner should not spend scarce providers across the full universe by default.
Allowed:
- local/cache/history preselection
- top-N enrichment if explicitly budgeted
- optional mode-aware context

Forbidden unless explicitly requested:
- changing scanner scoring/selection/thresholds
- adding broad news/social sentiment fanout
- marking fallback data live

## Backtest usage

Backtest should be local-data-only.
Forbidden:
- live provider calls during backtest universe execution
- `_ensure_market_history`
- provider fallback fetches
- changing strategy math

## Diagnostics endpoint

Admin/provider diagnostics may expose:
- counts
- health
- budget skips
- deadline exceeded count
- provider status
- cache hit count
- sanitized reason codes

Do not expose:
- raw payloads
- credentials
- tokens
- headers
- request/response bodies

## Final report must include

For provider tasks:
- whether provider order changed
- whether new live call paths were added
- budget behavior
- required vs optional category handling
- sanitized diagnostics fields
- tests proving no raw payload/secret leakage
- confirmation fallback/mock/synthetic not-live semantics unchanged
