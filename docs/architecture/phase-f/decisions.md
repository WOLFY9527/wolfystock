# Phase F Decisions

## Scope

This is the long-lived decision register for the current Phase F coexistence boundary.

It records the decisions that future AI or human reviewers should treat as already settled unless newer accepted evidence supersedes them.

This page is the current source of truth; archive docs are provenance only.

## Core Boundary

The current accepted Phase F boundary is:

- legacy remains the only serving source on the validated lines
- PostgreSQL remains comparison-only on those lines
- current evidence does not equal serving approval
- current evidence does not equal cutover approval
- current evidence does not equal migration completion

## Validated Line Decisions

The currently accepted comparison-only checkpoints are:

- trades-list = non-empty bounded clean match
- cash-ledger = bounded non-empty real-PG evidence checkpoint complete
- corporate-actions = bounded non-empty real-PG evidence checkpoint complete

These are meaningful checkpoints, but they are not:

- serving approvals
- cutover approvals
- migration-complete signals

## Accounts-List Decision

The most important excluded surface is:

- `GET /api/v1/portfolio/accounts`

Accepted decision:

- keep it on the metadata-authority / drift-fallback track
- do not reopen it as a new Phase F comparison implementation line by default

## Plateau Decision

Accepted decision:

- there is currently no fourth true bounded comparison-only candidate worth selecting next inside the present portfolio surface

Implication:

- do not force weak candidate selection
- do not broaden into replay, snapshot, or generic infrastructure by default

## Serving Boundary Decision

Accepted decision:

- Phase F current evidence should not be described as PG serving readiness
- partial PG schema fallback behavior is a safety behavior, not serving approval
- comparison-only evidence must not be restated as serving approval

## Promotion-Readiness Decision

Accepted decision:

- promotion-readiness at the current stage means reviewer-facing bounded evidence quality only
- it does not mean readiness for PG serving or broad operational rollout

## Cutover Decision

Accepted decision:

- broader Phase F cutover requires additional prerequisites beyond the validated comparison-only lines
- current validated lines are useful input to future cutover thinking, not sufficient approval

## Settled Statements To Reuse

Future work should continue to treat the following as settled unless contradicted by newer accepted evidence:

- legacy remains the serving source
- PostgreSQL remains comparison-only on the validated lines
- accounts-list stays on the metadata-authority / drift-fallback track
- current comparison-only expansion has reached a plateau
- no fourth true bounded candidate is currently worth selecting next
- serving, cutover, replay, and migration-complete claims remain out of bounds
