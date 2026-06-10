# WolfyStock Alerts Docs

Status: local-only user alert dry-run API and helper contract docs.

Use this lane when a future task needs pure user-alert helper boundaries without
broad repo search.

## Helper Contract Index

- `POST /api/v1/user-alerts/rules/{rule_id}/dry-run`
  - Owner-scoped API path for current-user local alert review. The request must
    provide caller-supplied `observedPrice`, `observedAt`, and `freshness`; it
    may provide `suppression`.
  - The endpoint loads the rule by current owner and `rule_id`, calls the pure
    dry-run pipeline, and returns `dryRun=true`, `noSend=true`,
    `outboundAttempted=false`, `liveOutbound=false`, and `localOnly=true`.
  - The endpoint does not fetch quotes, call provider runtime, send
    notifications, wire scheduling, mutate MarketCache, or persist default
    events.
- `src/services/user_alert_evaluation.py`
  - Pure dry-run evaluation helper; local intent only, no outbound delivery,
    provider runtime, cache mutation, or API/frontend wiring claim.
- `src/services/user_alert_event_packet.py`
  - Local-only event-packet projection from caller-supplied dry-run results; no
    live notification path.
- `src/services/user_alert_suppression_policy.py`
  - Pure suppression decision helper; bounded state output only.
- `tests/test_user_alert_evaluation.py`
  - Focused dry-run coverage/examples for alert result states.
- `tests/test_pure_helper_import_boundaries.py`
  - Import-boundary guard for optional alert helper modules.

## Boundary Reminder

- These helpers are inert/pure helper lanes, not runtime wiring.
- The API dry-run route is backend-only and local-only; do not infer frontend
  availability, outbound notification readiness, scheduled evaluation
  readiness, or professional readiness from its presence.
