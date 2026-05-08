# Operator Evidence Workflow Runner Guide

Date: 2026-05-08
Scope: one-command offline workflow for sanitized operator evidence review.

This guide covers `scripts/operator_evidence_workflow_run.py`. The runner
orchestrates the existing offline template, manifest, bundle, and report helpers
in a safe local sequence. It is a review workflow aid only. It does not approve
launch readiness and does not update shared launch acceptance artifacts.

## Modes

### Initialize Templates

Generate the full sanitized template pack into a local directory:

```bash
python3 scripts/operator_evidence_workflow_run.py init \
  --output-dir path/to/operator-evidence-templates
```

This mode reuses `scripts/operator_evidence_template_pack.py` logic and writes
the full template set:

- `provider_operator_evidence.json`
- `restore_pitr_operator_evidence.json`
- `security_operator_acceptance.json`
- `quota_budget_operator_evidence.json`
- `staging_ingress_operator_evidence.json`
- `ws2_sse_operator_decision_evidence.json`
- `config_snapshot_evidence.json`
- `manual_release_approval_review_record.json`

Generated templates are placeholders for later operator-sanitized evidence.
They are not real launch evidence.

### Check Evidence Bundle

Validate a local sanitized artifact directory and render workflow outputs:

```bash
python3 scripts/operator_evidence_workflow_run.py check \
  --artifact-dir path/to/sanitized-operator-evidence-dir \
  --output-dir path/to/operator-evidence-review-output
```

This mode writes:

- `bundle-summary.json`
- `evidence-manifest.json`
- `release-review-report.md`

The runner creates and verifies a checksum manifest, aggregates the existing
bundle checker summary, and renders a sanitized Markdown review report. The
best possible bundle status remains `complete-review-required`, meaning a human
reviewer must still make any release decision outside the runner.

### Render Report Only

Render a Markdown report from an existing bounded bundle summary:

```bash
python3 scripts/operator_evidence_workflow_run.py report \
  --bundle-summary path/to/bundle-summary.json \
  --output path/to/release-review-report.md
```

This mode does not inspect artifact directories and does not create a manifest.

## Required Artifacts For Check Mode

`check` mode follows the current operator bundle checker contract. The required
sanitized files are:

- `provider_operator_evidence.json`
- `restore_pitr_operator_evidence.json`
- `security_operator_acceptance.json`
- `quota_budget_operator_evidence.json`
- `staging_ingress_operator_evidence.json`

Supplemental template-pack artifacts, such as WS2/SSE, config snapshot, and
manual release approval records, remain outside the current required bundle
checker contract unless a separately scoped task expands that validator.

## Exit Codes

- `0`: workflow outputs were written and the bundle is ready for manual review.
- `2`: CLI, input, or report-rendering error.
- `10`: required artifact missing.
- `11`: validator rejection or non-reviewable bundle status.
- `12`: manifest verification mismatch.
- `13`: unsafe marker detected by existing validator summaries.

Non-zero exit codes still preserve sanitized output files when enough bounded
input exists to render them. Operators should inspect the reason-code summaries,
not raw artifact bodies.

## Safety Boundary

The runner is offline only. It does not:

- make network calls;
- read environment variables, `.env` files, provider credentials, DB URLs,
  cookies, sessions, tokens, or deployment state;
- run database restore commands, provider probes, browser tests, deployment
  commands, or outbound notifications;
- print raw artifact bodies, raw logs, requests, responses, stack traces, or
  real user data;
- mutate runtime configuration or application behavior;
- change launch acceptance plumbing.

The runner is intentionally separate from:

- `scripts/launch_acceptance_evidence.py`
- `scripts/release_gate_summary.sh`
- launch acceptance tests and fixtures
- public launch readiness audit documents

## Manual Review Requirement

`release-review-report.md` is sanitized review evidence, not an approval
record. A reviewer must still confirm the source and quality of each operator
artifact, verify that redaction rules were followed, and make any release
decision through the approved human process.
