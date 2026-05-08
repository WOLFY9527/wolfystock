# Operator Evidence Gap Analyzer Guide

Date: 2026-05-09
Scope: local checklist generation for sanitized operator evidence review.

This guide covers `scripts/operator_evidence_gap_analyzer.py`. The analyzer
reads a local directory of already-sanitized operator evidence artifacts and
writes a bounded JSON checklist of remaining human inputs. It is a review aid
only. It cannot make a launch or release decision.

## Command

Run from the repository root before the real operator review:

```bash
python3 scripts/operator_evidence_gap_analyzer.py \
  --artifact-dir path/to/sanitized-operator-evidence-dir \
  --output path/to/operator-evidence-gap-summary.json
```

The command exits `0` only when all required category artifacts are present and
the local analyzer found no missing inputs or unsafe placeholder findings. A
`0` exit still means manual review is required.

## Categories Covered

The analyzer covers the same eight operator evidence categories as the local
bundle checker:

- `provider`
- `restore-pitr`
- `security`
- `quota-budget`
- `staging-ingress`
- `ws2-sse`
- `config-snapshot`
- `manual-release-approval`

For each category, the output includes:

- `status`
- `missingRequiredHumanInputs`
- `unsafePlaceholderHits`
- `outcomePosture`
- `nextOperatorAction`

The checklist contains field labels and reason codes only. It does not include
raw artifact bodies, raw logs, request bodies, response bodies, stack traces, or
secret values.

## Output Posture

The top-level JSON always includes:

- `manualReviewRequired: true`
- `releaseApproved: false`
- `launchApproved: false`
- `networkCallsExecuted: false`
- `rawArtifactBodiesIncluded: false`
- `runtimeBehaviorChanged: false`

The best possible `gapStatus` is `review-required`. That status means the local
checklist is ready for a human reviewer to inspect. It does not replace the
reviewer, the release meeting or ticket, rollback ownership checks, or any
separately authorized launch acceptance process.

## How It Differs From Nearby Tools

`scripts/operator_evidence_preflight.py` runs a fixed set of repository checks
and can optionally invoke the workflow runner against a local artifact
directory. It summarizes whether those checks passed; it does not produce a
per-category human-input checklist.

`scripts/operator_evidence_workflow_run.py` creates a manifest, bundle summary,
and Markdown review report from sanitized artifacts. It is the broader offline
workflow. The gap analyzer is narrower: it reads the artifact directory and
writes only the remaining-input checklist.

`scripts/operator_evidence_archive_pack.py` packages workflow outputs for
manual review. It expects workflow output files, not source artifacts. The gap
analyzer expects the sanitized source artifact directory and does not package
files.

## Safety Boundary

The analyzer is local and offline. It does not:

- read environment values or `.env` files;
- inspect deployment state;
- call networks, providers, browsers, deployment tools, notification channels,
  or databases;
- run restore commands, probes, or release commands;
- mutate runtime configuration or application behavior;
- modify shared launch acceptance files;
- print or write raw artifact bodies.

If the analyzer reports missing inputs, unsafe placeholder findings, or
validator review reasons, operators should regenerate the sanitized artifact
that owns the category and rerun the analyzer before handing the bundle to a
human reviewer.
