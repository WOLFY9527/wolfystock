# Phase F Runbook

## Scope

This is the long-lived bounded evidence runbook for the current Phase F comparison-only portfolio lines:

- trades-list
- cash-ledger
- corporate-actions

Current operating boundary:

- legacy remains the only serving source
- PostgreSQL remains comparison-only
- no step in this runbook authorizes PG serving

## Required Runtime Entry

Use the existing coexistence entrypoint only:

- `POSTGRES_PHASE_A_URL`
- `POSTGRES_PHASE_A_APPLY_SCHEMA`

The variable name is legacy-compatible and intentionally retained for now.

## Required Feature Flags

### Trades-list

- `ENABLE_PHASE_F_TRADES_LIST_COMPARISON=true`
- `PHASE_F_TRADES_LIST_COMPARISON_ACCOUNT_IDS=<small comma-separated allowlist>`

Allowlist behavior:

- if the allowlist is empty, comparison may still run broadly
- use a tiny explicit allowlist for bounded collection

### Cash-ledger

- `ENABLE_PHASE_F_CASH_LEDGER_COMPARISON=true`
- `PHASE_F_CASH_LEDGER_COMPARISON_ACCOUNT_IDS=<small comma-separated allowlist>`

Allowlist behavior:

- if the allowlist is empty, comparison does not run
- bounded evidence collection requires explicit allowlisted account ids

### Corporate-actions

- `ENABLE_PHASE_F_CORPORATE_ACTIONS_COMPARISON=true`
- `PHASE_F_CORPORATE_ACTIONS_COMPARISON_ACCOUNT_IDS=<small comma-separated allowlist>`

Allowlist behavior:

- if the allowlist is empty, comparison does not run
- bounded evidence collection requires explicit allowlisted account ids

## Shared Preconditions

Before collecting evidence, all of the following should already be true:

- the backend starts successfully
- `POSTGRES_PHASE_A_URL` points to a reachable PostgreSQL store
- the legacy endpoint already works normally
- sampled accounts already exist
- the request owner is authorized for the sampled accounts
- the run remains bounded to `1` to `3` allowlisted accounts

Do not:

- enable PG serving
- broaden into replay or snapshot work
- sample write paths unless the data already exists through normal product use
- allowlist every account

## Exact Collection Pattern

For each validated comparison-only line, keep the request set intentionally small.

### Trades-list

Recommended bounded request set per allowlisted account:

1. `account_id=<id>&page=1&page_size=20`
2. `account_id=<id>&symbol=<known-symbol>&page=1&page_size=20`
3. `account_id=<id>&side=buy&page=1&page_size=20`
4. `account_id=<id>&date_from=<known-date>&date_to=<known-date-or-window>&page=1&page_size=20`
5. `account_id=<id>&page=1&page_size=1`
6. `account_id=<id>&page=2&page_size=1`

### Cash-ledger

Recommended bounded request set per allowlisted account:

1. `account_id=<id>&page=1&page_size=20`
2. `account_id=<id>&direction=in&page=1&page_size=20`
3. `account_id=<id>&page=1&page_size=1`
4. `account_id=<id>&page=2&page_size=1`

### Corporate-actions

Recommended bounded request set per allowlisted account:

1. `account_id=<id>&page=1&page_size=20`
2. `account_id=<id>&page=1&page_size=1`
3. `account_id=<id>&page=2&page_size=1`
4. `account_id=<id>&action_type=cash_dividend&page=1&page_size=20`

## Evidence Expectations

For bounded acceptance-strength collection, the target evidence shape is:

- `comparison_attempted = true`
- `comparison_status = "matched"` on sampled requests
- bounded non-empty request-local evidence
- no serving behavior change
- no public contract change

This runbook is for:

- request-local diagnostics
- bounded reviewer/operator collection
- coexistence-era evidence

This runbook is not for:

- PG serving rollout
- cutover approval
- write-path migration
- replay or snapshot expansion

## Related Long-Lived Docs

- [database maintenance handbook](../database-maintenance-handbook.md)
- [database troubleshooting playbook](../database-troubleshooting-playbook.md)
- [database component map](../database-component-map.md)
- [status.md](./status.md)
- [decisions.md](./decisions.md)
