# Phase F Status

## Scope

This is the long-lived Phase F status entry point for the current PostgreSQL/SQLite coexistence posture.

Phase F remains:

- backend-only
- comparison-only
- legacy-served
- portfolio-read-path focused

This page is the current source of truth; archive docs are provenance only.

## Current Overall Posture

The accepted current posture is:

- legacy remains the only serving source
- PostgreSQL remains comparison-only on the validated lines
- PostgreSQL is still being validated primarily as a comparison source
- this is not PG serving readiness
- this is not broader cutover readiness
- this is not migration completion

## Validated Comparison-Only Lines

### Trades-list

Accepted status:

- non-empty bounded clean match

What to carry forward:

- the old PG source-unavailable blocker is no longer active
- the old empty-only framing is no longer accurate
- bounded non-empty evidence exists
- legacy still serves every response

### Cash-ledger

Accepted status:

- bounded non-empty real-PG evidence checkpoint complete

What to carry forward:

- real comparison wiring exists
- bounded mismatch classification exists
- request-local diagnostics exist
- bounded non-empty real-PG evidence exists
- legacy still serves every response

### Corporate-actions

Accepted status:

- bounded non-empty real-PG evidence checkpoint complete

What to carry forward:

- real comparison wiring exists
- bounded request-local diagnostics exist
- bounded non-empty real-PG evidence exists
- legacy still serves every response

## Separate-Track Surface

The most important excluded surface is:

- `GET /api/v1/portfolio/accounts`

Current boundary:

- remains on the metadata-authority / drift-fallback track
- should not proceed into new Phase F comparison implementation work

## Plateau And Next-Step Boundary

Current accepted plateau boundary:

- there is currently no fourth true bounded comparison-only candidate worth selecting next inside the present portfolio surface

This means:

- do not force a weak next candidate
- do not treat current evidence as serving approval
- do not broaden into replay, snapshot, or write-path migration by default

## Explicitly Not Done

The following are still not complete:

- PG serving for trades-list
- PG serving for cash-ledger
- PG serving for corporate-actions
- broader Phase F cutover
- replay or snapshot expansion
- write-path migration
- generic repo-wide comparison infrastructure
- overall migration completion

## Decision Documents

Use [decisions.md](./decisions.md) for the durable boundary set:

- serving boundary
- promotion-readiness framing
- cutover prerequisite framing
- accounts-list exclusion
- plateau conclusions
