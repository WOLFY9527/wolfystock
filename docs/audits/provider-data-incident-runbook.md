# Provider and Data Incident Runbook

Date: 2026-05-07
Mode: docs-only operations runbook. No runtime code, provider ordering,
fallback behavior, MarketCache behavior, provider circuit enforcement, schema,
tests, frontend code, deployment scripts, live providers, or git history was
changed.

## 1. Purpose

Use this runbook when staging or post-merge validation shows provider or market
data degradation. The current release posture treats provider circuit storage,
diagnostics, and dry-run counters as observational unless a separate approved
enforcement pilot exists.

This runbook does not authorize changing provider order, enabling provider
enforcement, hiding fallback labels, changing cache TTLs, or calling live
providers from incident evidence without approval.

## 2. Symptoms

| Symptom | Likely category | First check |
| --- | --- | --- |
| API `429` | Provider rate limit or quota depletion. | Provider diagnostics by provider, route family, quota window, and safe reason bucket. |
| API `403` | Entitlement, credential, key, or licensing problem. | Credential/key status through approved admin diagnostics; do not print secret values. |
| Timeout spike | Provider latency, network issue, cache stampede, or route fan-out pressure. | Timeout buckets, fallback depth, MarketCache hit/stale/miss counters, and task latency. |
| Missing fundamentals | Provider payload gap, entitlement gap, fallback insufficiency, or optional enrichment failure. | `dataQualityReport`, required/important field coverage, and confidence cap. |
| Stale quote | Cache-only/stale serving, delayed source, provider outage, or failed background refresh. | Freshness metadata, as-of/generated-at timestamps, stale/cache-only disclosure, and MarketCache events. |
| Options Greeks unavailable | Fixture/demo limitation, live options provider gap, OPRA entitlement issue, or malformed chain payload. | Options data-quality labels, provider adapter diagnostics, entitlement/licensing status, and fixture/synthetic markers. |
| Provider malformed payload | Provider response shape changed, parser mismatch, partial response, or upstream outage. | Safe `malformed_payload` / `insufficient_payload` buckets and sanitized parser diagnostics. |

Do not treat one symptom as proof of a root cause. Confirm the affected route,
provider, data category, owner/guest bucket, cache state, and whether the
affected data was required or optional.

## 3. Immediate Actions

1. Confirm scope.
   - Identify route family: analysis, async analysis, guest preview, provider
     market data, scanner, admin provider probe, Options Lab, or system.
   - Check whether the issue is one user, one symbol, one provider, one market,
     one data category, or global.
   - Record safe labels only. Do not capture raw provider payloads, URLs,
     query strings, `.env` values, tokens, cookies, raw session ids, prompts, or
     stack traces containing private data.

2. Check provider diagnostics API/UI.
   - Review provider circuit state, dry-run events, quota windows, probe
     events, route family, reason buckets, and redaction status.
   - Distinguish process-local counters from durable provider circuit state.
   - Confirm whether a state is observational/dry-run or approved enforcement.

3. Inspect `dataQualityReport`.
   - Confirm `requiredAvailable`, `dataQualityTier`, `confidenceCap`, missing
     required fields, missing important fields, and optional enrichment status.
   - For fast decisions, do not override data-quality caps to force a stronger
     answer.
   - For optional enrichment, confirm failures use sanitized reason codes and
     remain non-blocking where designed.

4. Verify fallback, synthetic, fixture, delayed, and cache labels.
   - Confirm UI/API output still discloses fallback or synthetic data.
   - Confirm stale/cache-only responses include freshness metadata and
     as-of/generated-at timestamps where available.
   - Confirm Options Lab does not present fixture/synthetic or missing-Greeks
     data as production-grade live options decisioning.

5. Avoid changing provider ordering blindly.
   - Do not reorder providers to chase a symptom without reproducible evidence.
   - Do not increase retry depth during a rate-limit or outage event.
   - Do not change MarketCache TTL, stale-while-revalidate behavior, background
     refresh, fallback factory behavior, or cold-start fallback as a first
     response.

## 4. Mitigation

Choose the smallest mitigation that preserves disclosure and limits shared
provider pressure.

| Mitigation | Use when | Required guardrail |
| --- | --- | --- |
| Hot-path cooldown | A provider/category/route has repeated timeout, `429`, `5xx`, malformed, or insufficient-payload buckets. | Keep cooldown bounded, jittered where implemented, and visible in diagnostics. |
| Optional enrichment degrade | News, sentiment, detailed fundamentals, or other non-required enrichment fails or times out. | Preserve required/important data gates and disclose optional enrichment status. |
| Disable non-critical provider probes | Admin/manual probe loops are contributing to quota or timeout pressure. | Keep runtime user routes unchanged unless separately approved. |
| Cache/freshness disclosure | Stale/cache-only data is still acceptable for the route. | Show stale/cache-only labels, freshness timestamps, and degraded reason bucket; do not hide uncertainty. |
| Route-level pause or UI withdrawal | A staging route is unsafe to expose while diagnosis continues. | Stop using the route or hide entry points without deleting user data or changing provider storage. |

Mitigations should prefer reducing outbound pressure over deeper fallback
chains. During broad provider incidents, stale/cache-only mode with explicit
freshness disclosure is safer than walking every provider in the chain.

## 5. Escalation

Escalate when the incident cannot be safely handled through observation,
cooldown, optional-degrade, probe-disablement, or route withdrawal.

| Escalation trigger | Owner / path | Notes |
| --- | --- | --- |
| Paid provider outage or sustained `429` / `5xx` | Provider account owner or vendor support. | Include provider name, account tier, time window, safe route/category labels, and bounded counts. Do not include raw payloads or credentials. |
| Credential/key invalid or repeated `403` | Secrets owner / deployment operator. | Rotate or fix credentials through approved secret management. Do not print current values. |
| OPRA/options provider licensing gap | Product/operator plus vendor support. | Treat missing Greeks, entitlement failures, delayed chains, and symbology gaps as production blockers for live Options decisioning. |
| Malformed provider payload after upstream change | Provider integration owner. | Capture sanitized schema mismatch labels and parser category, not raw provider body. |
| User-visible data correctness risk | Incident lead and release owner. | Prefer feature flag disablement, route withdrawal, or rollback decision over hiding data-quality labels. |

## 6. Non-actions

Do not:

- hide synthetic, fixture, fallback, delayed, stale, cache-only, or degraded
  labels;
- turn on provider circuit enforcement without explicit approval;
- change provider ordering, fallback depth, retry caps, timeout envelopes,
  MarketCache TTLs, stale-while-revalidate, background refresh, or payload
  shape as an unreviewed incident response;
- suppress `dataQualityReport` or confidence caps to make output look healthy;
- treat provider diagnostics as billing truth unless that contract has been
  separately implemented and accepted;
- use live provider probes for repeated diagnosis when non-critical probes can
  be disabled;
- print secrets, `.env` values, API keys, provider credentials, raw session
  ids, raw prompts, raw provider payloads, raw stack traces, or production DB
  contents in incident evidence.

## 7. Recovery Validation

After mitigation or vendor recovery, validate with focused checks:

- provider diagnostics show no unexpected open/depleted/disabled state for the
  affected provider/category/route;
- `dataQualityReport` returns expected required/important coverage and
  confidence caps;
- stale/cache-only and fallback labels remain visible where applicable;
- optional enrichment failures recover or remain clearly degraded without
  blocking required data;
- Options Lab still blocks or caps decisions when Greeks, freshness,
  entitlement, or provider coverage are insufficient;
- admin/provider diagnostics remain redacted;
- no provider enforcement, ordering, cache, schema, frontend, or deployment
  behavior changed outside an approved incident action.

## 8. Evidence Template

```text
Incident window:
Route family:
Provider/category:
Affected market/symbol scope:
Primary symptom:
Safe reason bucket:
Required data affected: yes/no
Optional enrichment affected: yes/no
Synthetic/fallback/stale labels preserved: yes/no
Immediate action taken:
Mitigation:
Escalation:
Validation:
Rollback decision needed: yes/no
Secrets or raw payloads printed: no
```
