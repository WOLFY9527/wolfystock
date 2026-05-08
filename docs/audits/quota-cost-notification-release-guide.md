# Quota, Cost, and Notification Release Safety Guide

Date: 2026-05-09
Scope: offline release safety coverage for quota, LLM/provider cost, and notification delivery.

This guide is advisory and domain-local. It does not approve launch, change
quota enforcement, change provider or AI routing, change notification routing,
or integrate with the shared launch acceptance matrix.

## Offline Audit

Run:

```bash
python3 scripts/quota_cost_notification_release_audit.py --offline
```

The command uses in-memory fixtures only and emits bounded JSON with:

- `quotaPosture`
- `costPosture`
- `notificationPosture`
- `liveCallsExecuted=false`
- `notificationsSent=false`
- `manualReviewRequired=true`

The default CLI mode is also offline. There is no live mode in this script.

## What The Audit Covers

- Quota dry-run posture does not create reservations or usage windows.
- Invalid quota route/config inputs fall back or reject safely using existing behavior.
- Missing pricing policy/provider credentials do not create cost ledger spend.
- Notification no-channel and dry-run paths do not send outbound messages.
- Sanitized notification event payloads do not expose webhook, token, password,
  session, cookie, API key, or email-payload values.

## What Operators Must Verify Separately

With real credentials and a separately approved runbook, operators still need to verify:

- real provider quota limits, billing terms, and API-key presence outside this offline audit;
- paid provider and AI gateway budgets, retry ceilings, and account-level spend alerts;
- notification channel ownership, webhook/email target correctness, and opt-in delivery rehearsals;
- provider invoice reconciliation against actual billing exports;
- rollback switches for quota pilot enforcement and notification delivery wiring.

Real-credential verification must stay outside this script. Do not paste raw
provider payloads, tokens, webhook URLs, email addresses, invoices, prompts,
LLM responses, or stack traces into audit artifacts.

## Runtime Boundary

This pass adds release tests, an offline CLI, and operator documentation. It
does not:

- enable live quota enforcement;
- change provider routing, AI decisions, model fallback, scanner scoring,
  portfolio/backtest calculations, or MarketCache behavior;
- send notifications from the audit command;
- modify launch acceptance shared files.
