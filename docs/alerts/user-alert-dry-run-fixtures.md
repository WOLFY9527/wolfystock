# User Alert Dry-Run Fixtures

Status: fixture catalog for local-only user alert dry-run helpers
Test coverage: `tests/test_user_alert_dry_run_fixtures.py`

## Scope

These fixtures exercise only the existing pure helpers:

- `src/services/user_alert_evaluation.py`
- `src/services/user_alert_event_packet.py`

The catalog is review coverage only. It does not add runtime wiring, delivery
paths, storage writes, API handlers, or frontend behavior.

## What Dry-Run Means Here

For every fixture state, dry-run means:

- the caller supplies the rule, price, freshness, and suppression inputs;
- the helper returns a bounded evaluation payload and a bounded local packet;
- no external notification is sent;
- no provider runtime path runs;
- no cache or storage mutation happens.

The fixtures therefore lock the helper output shape and copy only. They do not
prove any live reminder flow.

## No-Send Meaning

`no-send` means the helper result stays inside local review flow:

- `outboundAttempted: false`
- `liveOutbound: false`

This is true for observed, not observed, blocked, and suppressed states.

## Local-Only Meaning

`local-only` applies to the event packet projection:

- `dryRun: true`
- `localOnly: true`

The packet is a local summary of the caller-supplied dry-run result. It is not
treated as a live outbound reminder record.

## Fixture Catalog

| Fixture | Input shape | Expected state | Bounded meaning |
| --- | --- | --- | --- |
| `condition_observed` | Fresh observed price reaches the threshold. | `condition_observed` | Condition is observed and recorded as dry-run only. |
| `condition_not_observed` | Fresh observed price stays below the threshold. | `condition_not_observed` | Condition is not observed; the helper keeps a local check result only. |
| `blocked_insufficient_data` | Observed price is missing. | `blocked_insufficient_data` | Data is insufficient, so the helper does not treat the result as current. |
| `suppressed_muted` | Observed condition with `muted: true`. | `suppressed_muted` | Condition is observed, but the result stays muted and no-send. |
| `suppressed_snoozed` | Observed condition with a future `snoozedUntil`. | `suppressed_snoozed` | Condition is observed, but the result stays postponed and no-send. |
| `suppressed_cooldown` | Observed condition with `cooldownActive: true`. | `suppressed_cooldown` | Condition is observed, but the result stays inside the cooldown boundary. |
| `suppressed_duplicate` | Observed condition with `duplicateActive: true`. | `suppressed_duplicate` | Condition is observed, but the result stays folded into a duplicate dry-run record. |

## Review Notes

- `condition_not_observed` and `blocked_insufficient_data` must remain
  non-suppressed states.
- All `suppressed_*` fixtures must remain `conditionObserved: true` while still
  keeping `outboundAttempted: false`.
- The packet copy must stay aligned with the evaluation copy for every fixture.
- The catalog must stay free of runtime claims such as live send, live routing,
  or account-level reminder execution.
