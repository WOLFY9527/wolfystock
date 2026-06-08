# WolfyStock Alerts Docs

Status: helper-contract entry for local-only alert dry-run docs.

Use this lane when a future task needs pure user-alert helper boundaries without
broad repo search.

## Helper Contract Index

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
- Do not infer API availability, frontend availability, outbound notification
  readiness, or professional readiness from their presence.
