# Provider Data Freshness Reliability Guide

Date: 2026-05-09
Mode: tests/scripts/docs first. Runtime provider routing, provider ordering,
fallback depth, MarketCache TTL/SWR/cold-start behavior, frontend UI, scanner,
portfolio, backtest, AI logic, notification routing, DuckDB runtime, launch
acceptance files, and release secret scan were not changed.

## Purpose

This guide defines the offline contract for provider reliability, data
freshness labels, fallback boundaries, stale handling, and no-mock-as-live
guarantees.

The offline audit is advisory. It does not approve launch, does not call live
providers, does not read credentials or `.env`, and does not change runtime
behavior.

## Offline Audit CLI

Run:

```bash
python3 scripts/provider_reliability_audit.py --offline
```

`--offline` is the default posture. The CLI emits bounded JSON with these
top-level fields only:

- `providersChecked`
- `freshnessPosture`
- `fallbackPosture`
- `networkCallsExecuted`
- `manualReviewRequired`

`networkCallsExecuted` must remain `false` for this command. The current CLI
does not implement `--allow-network`; any future network-enabled mode must be
explicitly opt-in, documented here first, and must never print credentials,
raw provider payloads, URLs with query strings, headers, stack traces, or `.env`
values.

## Contract Coverage

Automated offline contracts cover:

- fallback, mock, and synthetic data cannot be labeled `live`;
- freshness semantics for `live`, `stale`, and `fallback`;
- mixed real/fallback payload classification;
- unavailable and refreshing provider-health states;
- timeout, `403`/unauthorized, empty payload, missing field, malformed payload,
  and fallback provider paths;
- MarketCache cold-start timeout fallback returning quickly;
- stale snapshots served with source/freshness/refreshing metadata;
- refresh failure preserving the old safe snapshot.

## Manual Live-Credential Review Before Launch

Before any launch decision that relies on live provider credentials, operators
must manually verify and attach sanitized evidence for each provider/category:

| Check | Required evidence | Must not include |
| --- | --- | --- |
| Credentials and entitlement | Provider name, environment, credential presence state, entitlement class, and operator timestamp. | API keys, secrets, tokens, cookies, session ids, headers, or `.env` values. |
| Latency and timeout posture | Bounded latency bucket, timeout bucket count, and route/category label. | Raw URLs, query strings, request bodies, response bodies, or stack traces. |
| `403`/unauthorized handling | Safe reason bucket such as `provider_403` or `auth_error`, plus affected category. | Provider error body, account identifiers, or credential values. |
| Empty/missing/malformed payloads | Bounded schema or field-family bucket and whether fallback/stale cache was used. | Raw provider payload excerpts or debug payloads. |
| Freshness disclosure | As-of/generated-at timestamps, cache state, delay class, fallback/stale labels, and source label. | Claims that fallback, mock, fixture, or synthetic data is live. |
| Cache/SWR behavior | Cold-start timeout result, stale snapshot serving, background refresh result, and refresh-failure preservation. | Changes to TTL, provider ordering, or fallback policy unless separately approved. |
| License and redistribution | Provider/license review status and whether data can be cached/displayed for the intended environment. | Legal conclusions without owner review or launch approval claims. |

Manual evidence should follow the sanitized provider/operator evidence pattern
in `docs/audits/provider-operator-evidence-guide.md`. Passing the offline CLI
or attaching sanitized evidence is not launch approval; shared launch
acceptance wiring remains a separate serial review.
