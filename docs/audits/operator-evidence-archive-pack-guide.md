# Operator Evidence Archive Pack Guide

This guide covers `scripts/operator_evidence_archive_pack.py`, an offline helper
for packaging sanitized operator evidence workflow outputs into a bounded review
directory.

The packager is review support only. It copies selected sanitized workflow
outputs and creates `archive-index.json` with file labels, byte sizes, SHA-256
checksums, `manualReviewRequired=true`, and `releaseApproved=false`.

## Inputs

Run the packager only against the output directory from
`scripts/operator_evidence_workflow_run.py check`, not against the source
artifact directory.

Known workflow outputs:

- `bundle-summary.json`
- `evidence-manifest.json`
- `release-review-report.md`
- `review-diff.md`

`bundle-summary.json` is always included. `evidence-manifest.json` and
`release-review-report.md` are included only when explicitly requested.
`review-diff.md` is included automatically when present.

## Commands

Minimal archive:

```bash
python3 scripts/operator_evidence_archive_pack.py pack \
  --workflow-output-dir <workflow-output-dir> \
  --output-dir <archive-output-dir>
```

Archive with checksum manifest and rendered review report:

```bash
python3 scripts/operator_evidence_archive_pack.py pack \
  --workflow-output-dir <workflow-output-dir> \
  --output-dir <archive-output-dir> \
  --label <sanitized-archive-label> \
  --include-manifest \
  --include-report
```

## Output

`archive-index.json` has schema
`wolfystock_operator_evidence_archive_index_v1` and includes:

- `archiveLabel`
- `generatedAt`
- `includedFiles[].fileLabel`
- `includedFiles[].byteSize`
- `includedFiles[].sha256`
- `reviewStatus` when discoverable from `bundle-summary.json`
- `manualReviewRequired: true`
- `releaseApproved: false`

The index intentionally does not include copied file bodies or source artifact
payload fields.

## Safety Rejections

The packager fails before writing `archive-index.json` when it detects:

- unsafe archive labels, including path traversal or sensitive marker strings;
- raw source artifact filenames in the workflow output directory;
- unknown extra JSON files in the workflow output directory;
- missing requested workflow outputs;
- identical input and output directories.

The command does not read environment variables, call networks, inspect
deployment state, read databases, send notifications, mutate runtime behavior,
or interact with launch acceptance plumbing.

## Review Boundary

The archive is only evidence packaging support. A generated archive still
requires manual operator review, and `releaseApproved` remains `false`.
