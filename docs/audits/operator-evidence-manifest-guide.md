# Operator Evidence Manifest Guide

Date: 2026-05-08
Scope: offline checksum manifest for sanitized local operator evidence bundles.

This guide explains how an operator can create and verify a local evidence
manifest before manual review. The manifest is a checksum aid only. It does not
approve launch readiness, does not update shared launch acceptance artifacts,
and does not replace domain-specific validator review.

## Inputs

Use a local directory that already contains sanitized operator evidence JSON
artifacts for the bundle checker:

- `provider_operator_evidence.json`
- `restore_pitr_operator_evidence.json`
- `security_operator_acceptance.json`
- `quota_budget_operator_evidence.json`
- `staging_ingress_operator_evidence.json`

The manifest checker recognizes these filenames and records their category,
filename label, validator name, checksum, byte size, generation timestamp, and
redaction version when a sanitized artifact exposes one as metadata.

## Create A Manifest

Run from the repository root:

```bash
python3 scripts/operator_evidence_manifest_check.py create \
  --artifact-dir path/to/sanitized-artifact-dir \
  --output path/to/operator-evidence-manifest.json
```

The generated manifest does not include raw artifact bodies. It contains only
bounded file labels and checksum metadata for recognized required artifacts.

## Verify A Manifest

Run from the repository root:

```bash
python3 scripts/operator_evidence_manifest_check.py verify \
  --artifact-dir path/to/sanitized-artifact-dir \
  --manifest path/to/operator-evidence-manifest.json
```

Verification returns `0` only when the manifest shape is safe and every
recognized required artifact still matches its recorded checksum and byte size.
It returns non-zero for findings such as:

- missing file;
- changed checksum;
- changed byte size;
- unknown required artifact in the manifest;
- unsafe manifest fields;
- path traversal attempts in file labels.

The verification output is a sanitized status summary. It does not echo raw
artifact values, request or response bodies, logs, stack traces, cookies,
tokens, private keys, DSNs, credential-bearing URLs, sessions, or deployment
state.

## Pair With Bundle Validation

Use the manifest checker with the existing bundle checker in this order:

1. Run each domain-specific artifact collection and redaction workflow.
2. Run `operator_evidence_bundle_check.py` against the sanitized directory:

```bash
python3 scripts/operator_evidence_bundle_check.py path/to/sanitized-artifact-dir
```

3. If the bundle checker reports `complete-review-required`, create a manifest
   for the exact directory.
4. Preserve the manifest with the local review packet.
5. Before manual review or handoff, verify the same directory against the
   manifest to detect missing or changed artifacts.

The manifest confirms file integrity only. Manual reviewers still need to check
whether each artifact came from the intended operator process, whether the
environment labels are correct, whether timestamps are plausible, and whether
domain-specific guide requirements were followed.

## Boundaries

The manifest checker is offline only. It does not:

- call networks, providers, browsers, deployment tools, databases, notification
  systems, or external services;
- read `.env` files, environment variables, deployment state, cookies, tokens,
  DSNs, private keys, or session values;
- print artifact bodies or raw logs;
- mutate runtime configuration or application behavior;
- change launch acceptance plumbing or shared launch acceptance evidence files.

Do not copy manifest output into shared launch acceptance files unless a
separate task explicitly authorizes that integration.
