# Staging Integration Smoke Guide

This guide covers the post-gate staging integration smoke for WolfyStock API
surfaces. The smoke is intentionally advisory: it does not approve a release,
does not replace operator evidence, and is not wired into the launch acceptance
matrix.

## Purpose

Run this after `./scripts/ci_gate.sh` and before release review to confirm that
the backend route/config surface is present for the production-like workflow:

- auth/session
- public health
- market overview
- scanner
- AI research when locally configured
- portfolio
- backtest
- admin logs, cost observability, provider circuits, market-provider operations

## Safe Default

Default local mode performs route/config inspection only:

```bash
python3 scripts/staging_integration_smoke.py --mode local
```

Default mode does not:

- make provider calls
- call AI/LLM providers
- send notifications
- mutate portfolio/backtest/scanner/admin state
- execute destructive writes
- open network sockets

The JSON summary always includes:

- `smokeStatus`
- `checkedSurfaces`
- `skippedSurfaces`
- `networkCallsExecuted`
- `destructiveWritesExecuted`
- `authRequiredSurfaces`
- `manualReviewRequired`
- `timingSummary`

Each item in `checkedSurfaces` includes a sanitized `elapsedMs` measurement for
the local route/config check or explicitly enabled live probe. `timingSummary`
aggregates those measurements with `count`, `minElapsedMs`, `maxElapsedMs`,
`p50ElapsedMs`, and `p95ElapsedMs`.

`authRequiredSurfaces` are expected to need a real authenticated staging session
for deeper operator validation.

## Optional Live Probe

Use live probing only when the target backend is explicitly approved for
read-only staging checks:

```bash
python3 scripts/staging_integration_smoke.py \
  --mode local \
  --base-url http://127.0.0.1:8000 \
  --allow-network \
  --json-output reports/staging-integration-smoke.json
```

The live probe uses bounded read-only `GET` requests against selected API
surfaces. It does not send request bodies, credentials, cookies, write calls, or
notification requests.

Do not put credentials, tokens, query strings, or secret-bearing URLs in
`--base-url`. The CLI rejects URLs with embedded credentials and strips query
strings from the base URL before probing. Timing evidence does not include the
base URL, query strings, response bodies, provider payloads, cookies, or
credentials.

## Classification

Each checked surface reports a stable `status` and `reasonCode`:

| Condition | Meaning |
| --- | --- |
| `route_missing` | The route is absent locally or returned HTTP 404 in live mode. |
| `auth_required` | The surface is protected and needs an authenticated staging session. |
| `config_missing` | Optional local capability, such as AI research provider readiness, is not configured. |
| `dependency_unavailable` | A live read-only probe could not reach a required dependency or returned an unavailable response. |
| `unexpected_server_error` | A live read-only probe returned an unexpected 5xx response. |

`smokeStatus=pass` means all checked surfaces were directly verified without
auth, optional-config, or dependency follow-up. `manual_review_required` means
protected or optional surfaces need operator follow-up. `fail` means at least
one required route is missing or a live probe hit an unexpected server error.

## Recommended Post-Gate Sequence

```bash
./scripts/ci_gate.sh
python3 scripts/staging_integration_smoke.py --mode local --json-output reports/staging-integration-smoke.json
git diff --check
```

If the worktree is clean enough for release scanning:

```bash
./scripts/release_secret_scan.sh
```

Attach the generated JSON summary to release review notes as advisory smoke
evidence. Keep real operator acceptance, launch approval, and manual GO/NO-GO
decisions in the existing release evidence workflow.

## Boundaries

This smoke does not change runtime behavior and does not touch:

- frontend UI files
- provider routing
- scanner scoring or thresholds
- portfolio accounting
- backtest calculations
- AI decision logic
- notification routing
- launch acceptance shared files
