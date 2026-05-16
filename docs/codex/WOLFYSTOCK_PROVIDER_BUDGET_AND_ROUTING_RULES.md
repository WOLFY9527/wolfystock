# WolfyStock Provider Budget and Routing Rules

Purpose: stable rules for free/limited API usage, research modes, provider budgeting, and diagnostics.

---

## Core Principles

1. Cache/local first.
2. Required data and optional enrichment are separate.
3. Optional providers must be budgeted and deadline-bounded.
4. Free API quota is scarce; do not spend it on broad/low-value scans.
5. Fallback/stale/mock/synthetic data must never be marked live.
6. Provider diagnostics must be sanitized.
7. Do not add new live provider paths without explicit approval.

---

## Research Modes

### quick

Purpose: interactive fast analysis and UI previews.

Expected behavior:

- cache/local/yfinance first;
- avoid optional external calls;
- shortest optional deadline;
- news/social sentiment usually skipped;
- fundamentals capped or skipped if optional.

### standard

Purpose: balanced default explicit mode.

Expected behavior:

- cache-first;
- limited optional supplemental categories;
- limited news/sentiment;
- deadline aligned with fast decision budget.

### deep

Purpose: richer research on selected symbols.

Expected behavior:

- broader optional enrichment;
- may allow news/social sentiment;
- max call budgets still apply;
- not for every scanner candidate.

---

## Required vs Optional Categories

Required examples:

- realtime quote if needed for decision quality;
- candles/OHLCV for technical quality;
- data needed to avoid invalid analysis.

Optional examples:

- news enrichment;
- social sentiment;
- deep fundamentals;
- alternate provider cross-checks;
- explanatory context.

Rules:

- Required categories must not be skipped by optional budget deadlines.
- Optional categories may be skipped by mode/budget/deadline.
- Optional skips produce sanitized gap metadata, not raw errors.

---

## Provider Order

Do not change provider global order unless explicitly required.

Do not reorder live provider fallback silently.

Allowed:

- advisory-only plan suggestions;
- metadata indicating preferred provider classes;
- optional budget skip before calls;
- deadline-bounded optional fanout preserving call semantics.

---

## Provider Capability Metadata

Capability metadata may describe:

- provider id/name;
- domains;
- markets;
- quota class;
- freshness class;
- recommended TTLs;
- scanner/backtest eligibility;
- quick/standard/deep eligibility;
- priority hints;
- risk/operator notes.

It must not import live provider clients or read credentials.

---

## Usage Ledger

May record:

- provider/category attempted;
- cache hit;
- skipped by cache/budget/mode;
- optional deadline exceeded;
- timeout;
- success/failure;
- sanitized reason code;
- research mode;
- bounded metadata.

Must not store:

- raw provider payload;
- request/response body;
- headers;
- cookies;
- Authorization;
- API keys;
- tokens;
- secrets;
- full stack traces.

---

## Scanner Usage

Scanner should not spend scarce providers across the full universe by default.

Allowed:

- local/cache/history preselection;
- top-N enrichment if explicitly budgeted;
- optional mode-aware context.

Forbidden unless explicitly requested:

- live calls across full universe;
- broad news/social sentiment for all candidates;
- provider-order changes;
- hiding fallback/stale gaps.
