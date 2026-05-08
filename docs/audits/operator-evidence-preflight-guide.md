# Operator Evidence Preflight Guide

Date: 2026-05-08
Scope: offline local preflight for sanitized operator evidence review.

This guide covers `scripts/operator_evidence_preflight.py`. The command runs
existing safe operator evidence checks in one local sequence and emits a bounded
JSON summary for human review. It is local tooling only and does not update
launch acceptance plumbing.

## Modes

### Synthetic Fixture Preflight

Run the default synthetic-only preflight:

```bash
python3 scripts/operator_evidence_preflight.py --synthetic
```

This mode runs:

- `scripts/operator_evidence_workflow_smoke.py` against repository synthetic
  fixtures
- `tests/test_operator_evidence_docs_safety.py`
- `tests/test_evidence_cli_contracts.py`
- `tests/test_operator_evidence_fixture_pack.py`

The command captures child process output and prints only a bounded JSON
summary. It does not print raw artifact bodies or raw fixture contents.

### Local Sanitized Artifact Preflight

Optionally add one local sanitized artifact workflow check:

```bash
python3 scripts/operator_evidence_preflight.py \
  --synthetic \
  --artifact-dir path/to/sanitized-operator-evidence-dir
```

The default checks still use synthetic fixtures. The extra artifact-directory
check runs the existing workflow runner against the supplied local directory and
reports only the check label, pass/fail status, exit code, and bounded failure
reason.

## Output Contract

The command writes JSON to stdout with:

- `preflightStatus`: `preflight-pass-review-required` or
  `preflight-fail-review-required`
- `manualReviewRequired: true`
- `releaseApproved: false`
- `launchApproved: false`
- `runtimeBehaviorChanged: false`
- `networkCallsExecuted: false`
- `rawArtifactBodiesIncluded: false`
- `checks`: bounded check labels, statuses, exit codes, and failure summaries

The best possible status is still review-required. The preflight cannot approve
launch, deployment, or production operation.

## Safety Boundary

The preflight is offline and local. It does not:

- read environment values, `.env` files, provider credentials, DB URLs, cookies,
  sessions, tokens, or deployment state
- call networks
- run provider probes, database commands, browser checks, deployment commands,
  or outbound notifications
- print raw artifact bodies, raw logs, request or response bodies, stack traces,
  or real user data
- mutate runtime configuration or application behavior
- change `scripts/launch_acceptance_evidence.py`,
  `scripts/release_gate_summary.sh`, launch acceptance tests, launch fixtures,
  or shared launch documentation

## Operator Review Notes

Use this command before assembling an offline review packet when you want one
bounded local summary of the current safe checks. A passing preflight means the
synthetic checks and any supplied sanitized local workflow check completed
without local validator failures. It does not replace manual evidence review,
source validation, redaction review, or the approved release decision process.
