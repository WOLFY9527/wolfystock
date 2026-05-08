# Operator Evidence Bundle Diff Guide

Date: 2026-05-08
Scope: offline comparison of sanitized operator evidence bundle summaries and
optional checksum manifests.

This guide explains how to compare two already-generated bundle summaries
without exposing raw artifact bodies. The diff reviewer is a manual review aid
only. It does not change launch acceptance plumbing and does not make a release
decision.

## Inputs

Required inputs are two sanitized bundle summary JSON files produced by:

```bash
python3 scripts/operator_evidence_bundle_check.py path/to/sanitized-artifact-dir \
  > bundle-summary.json
```

Optional inputs are two checksum manifest JSON files produced by:

```bash
python3 scripts/operator_evidence_manifest_check.py create \
  --artifact-dir path/to/sanitized-artifact-dir \
  --output operator-evidence-manifest.json
```

Use only summaries and manifests that were generated from sanitized operator
evidence. Do not pass raw logs, provider payloads, database exports, request or
response bodies, cookies, sessions, DSNs, private keys, or artifact body dumps.

## Compare Two Bundle Attempts

Run from the repository root:

```bash
python3 scripts/operator_evidence_bundle_diff.py diff \
  --before path/to/before-bundle-summary.json \
  --after path/to/after-bundle-summary.json
```

To include checksum-manifest comparison:

```bash
python3 scripts/operator_evidence_bundle_diff.py diff \
  --before path/to/before-bundle-summary.json \
  --after path/to/after-bundle-summary.json \
  --before-manifest path/to/before-manifest.json \
  --after-manifest path/to/after-manifest.json
```

To save the Markdown review delta:

```bash
python3 scripts/operator_evidence_bundle_diff.py diff \
  --before path/to/before-bundle-summary.json \
  --after path/to/after-bundle-summary.json \
  --before-manifest path/to/before-manifest.json \
  --after-manifest path/to/after-manifest.json \
  --output path/to/operator-evidence-review-diff.md
```

When `--output` is supplied, the same sanitized Markdown is also printed to
stdout for terminal review.

## Output

The Markdown diff includes:

- before and after bundle status labels;
- categories added or removed between attempts;
- status changes for categories present in both attempts;
- blocking or needs-review count changes;
- after-attempt blocking or needs-review category summaries;
- checksum changes by sanitized manifest file label only when both manifests
  are supplied;
- an explicit manual review required statement;
- an explicit non-approval statement.

Manifest checksum deltas do not include checksum values, byte-level content, or
artifact bodies. They report only whether a sanitized file label was added,
removed, or changed.

## Exit Codes

- `0`: the diff rendered successfully.
- `2`: one or more supplied JSON files could not be read or sanitized rendering
  failed.

The diff reviewer intentionally does not return a release approval status. A
successful render means only that a bounded review delta was produced.

## Safety Boundary

The diff reviewer is offline only. It does not:

- read raw artifact files beyond the summary or manifest paths explicitly
  supplied on the command line;
- print full raw JSON input bodies;
- print raw artifact bodies, provider payloads, request or response bodies,
  raw logs, stack traces, cookies, sessions, DSNs, tokens, private keys,
  credential-bearing URLs, database dumps, or secret values;
- call networks, providers, browsers, deployment tools, databases,
  notification systems, or external services;
- read `.env` files or environment variable values;
- mutate runtime configuration or application behavior;
- update `scripts/launch_acceptance_evidence.py`,
  `scripts/release_gate_summary.sh`, shared launch acceptance fixtures, or
  readiness audit documents.

Sensitive-looking labels and reason summaries are replaced with `[redacted]`.

## Manual Review Requirement

Every rendered diff still requires a human reviewer to decide:

- whether the two summaries came from the intended evidence attempts;
- whether a lower blocking count represents genuinely resolved evidence issues;
- whether newly added categories are expected;
- whether removed categories indicate missing evidence;
- whether checksum changes correspond to an authorized regenerated sanitized
  artifact;
- whether any unresolved blocker or advisory should prevent downstream review
  closure.

Do not copy diff output into shared launch acceptance files unless a separate,
explicitly scoped task authorizes that integration.
