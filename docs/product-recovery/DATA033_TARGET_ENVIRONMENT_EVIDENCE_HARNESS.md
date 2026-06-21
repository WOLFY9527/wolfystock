# DATA-033 Target Environment Evidence Harness

## Purpose

DATA-033 adds a local operator evidence harness for collecting sanitized
target-environment readiness evidence after DATA-021.

DATA-021 accepted DATA-017 through DATA-020 as source/test evidence only. This
harness helps an operator collect bounded evidence from a locally running
WolfyStock API for:

- Rotation Radar quote readiness.
- Portfolio price, FX, valuation snapshot, and analytics lineage.
- Options chain readiness.
- Scenario Lab baseline readiness.

The harness does not prove private-beta acceptance by itself. It records what a
target environment returned, keeps unavailable endpoints separate from blocked
readiness, and avoids exposing credentials or raw provider payloads.

## Script

```bash
/Users/yehengli/daily_stock_analysis/.venv/bin/python scripts/target_environment_evidence_harness.py \
  --base-url http://127.0.0.1:8000 \
  --output-dir artifacts/target-environment-evidence
```

The script writes a timestamped JSON artifact:

```text
target_environment_evidence_<YYYYMMDDTHHMMSSZ>.json
```

Use `--output <path>` when the artifact path must be controlled by an operator
workflow.

## Default Local API Paths

The harness uses configurable local API paths. These are the default path-only
patterns discovered in this branch:

| Surface | Default request | Extracted readiness fields |
| --- | --- | --- |
| Rotation Radar quote readiness | `GET /api/v1/market/rotation-radar?market=US` | `alpacaQuoteAuthorityReadiness` |
| Portfolio lineage | `GET /api/v1/portfolio/snapshot` | `price_lineage`, `fx_lineage`, `valuation_snapshot_lineage`, `analytics_readiness` |
| Options chain readiness | `GET /api/v1/options/underlyings/TEM/chain?includeGreeks=true` | `optionsChainReadiness` |
| Scenario baseline readiness | `POST /api/v1/market/scenario-lab` | `baselineReadiness` |

If an operator environment uses a different local route, override the path:

```bash
/Users/yehengli/daily_stock_analysis/.venv/bin/python scripts/target_environment_evidence_harness.py \
  --base-url http://127.0.0.1:8000 \
  --surface-url 'options_chain_readiness=GET:/api/v1/options/underlyings/AAPL/chain?includeGreeks=true&marketDataProvider=review_snapshot' \
  --output-dir artifacts/target-environment-evidence
```

Known surface ids:

- `rotation_quote_readiness`
- `portfolio_lineage`
- `options_chain_readiness`
- `scenario_baseline_readiness`

Use `--list-surfaces` to print the current defaults.

## Scenario Body

Scenario Lab is a `POST` endpoint. The default body is `{}` so the endpoint can
fail closed or return its default bounded contract. Operators can pass a local
JSON object when they need to probe a specific baseline contract:

```bash
/Users/yehengli/daily_stock_analysis/.venv/bin/python scripts/target_environment_evidence_harness.py \
  --base-url http://127.0.0.1:8000 \
  --scenario-body-file ./local_scenario_probe.json \
  --output-dir artifacts/target-environment-evidence
```

Do not put secrets, account identifiers, raw provider payloads, or broker
payloads in the scenario body.

## Artifact Semantics

Each surface records:

- endpoint availability: local HTTP status and unavailable/access-blocked/error
  classification.
- readiness status: readiness field state when the endpoint returns a usable
  response.
- collected fields: only the readiness fields needed to prove available,
  partial, blocked, stale, missing, observation-only, or authoritative states.
- missing evidence: unavailable endpoint, missing readiness fields, or
  readiness blockers.
- operator next steps: review-only recovery guidance for collecting more
  evidence.

`endpoint_unavailable` means the local endpoint was absent or not mapped. It is
not the same as `readiness_blocked`, which means the endpoint returned a
readiness contract and the contract itself blocked readiness.

## Redaction And Boundaries

The harness redacts sensitive keys and values before writing artifacts. It is
intended to remove authorization headers, cookies, credentials, account
identifiers, raw request/response markers, and credential-bearing URLs from
collected output.

The artifact also records:

- `readOnly: true`
- `noDataMutation: true`
- `noOrderPlacement: true`
- `providerRoutingChanged: false`
- `credentialsWritten: false`
- `liveProviderSuccessClaimed: false`

The harness must not be used to claim live provider success unless the returned
readiness fields actually prove that state. Demo, fallback, static, synthetic,
stale, missing, partial, and observation-only evidence remains bounded evidence.

## Validation

Focused script tests:

```bash
/Users/yehengli/daily_stock_analysis/.venv/bin/python -m pytest -q tests/scripts/test_target_environment_evidence_harness.py
```

Changed-file syntax check:

```bash
/Users/yehengli/daily_stock_analysis/.venv/bin/python -m py_compile \
  scripts/target_environment_evidence_harness.py \
  tests/scripts/test_target_environment_evidence_harness.py
```

Standard delivery checks:

```bash
git diff --check
bash scripts/release_secret_scan.sh --base-ref origin/main
```
