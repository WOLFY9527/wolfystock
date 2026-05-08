# Manual Release Approval Evidence Guide

Date: 2026-05-08
Scope: offline manual release review-record validation only.

This guide defines the sanitized human approval artifact expected after
`GO-REVIEW-REQUIRED`. The validator in
`scripts/manual_release_approval_evidence_check.py` checks that a manual review
record is complete, redacted, and free of launch-approval claims that would
change release gate semantics.

The validator is not an automatic launch approval mechanism. A passing result
means only that the review record is shaped correctly for manual release
review. The validator always emits `releaseApproved: false`, makes no network
calls, changes no runtime behavior, and is not integrated with
`scripts/launch_acceptance_evidence.py`.

## Safe Review Record Checklist

Record only sanitized labels and bounded acknowledgements:

- `artifactVersion`
- `releaseCandidateSha`
- `reviewerRoleLabels`
- `approvalMeetingOrTicketRef`
- `approvalTimestamp`
- `evidenceBundleRef`
- `knownResidualRisks`
- `rollbackOwnerLabel`
- `goNoGoDecision`
- `evidenceRedactionVersion`

Use role labels such as `release-manager` or `security-reviewer`, not real
names, emails, account handles, meeting participant lists, or personal
identifiers. Use ticket or meeting labels only, not URLs with credentials or
private chat links.

Do not include raw meeting transcripts, chat logs, screenshots, tracebacks,
stack traces, debug payloads, tokens, cookies, session IDs, private keys,
passwords, API keys, or other secret-bearing values.

Do not include `releaseApproved: true`, `launchApproved: true`,
`launch-approved`, `production-ready`, `automatic-GO`, `GO for launch`, or
similar wording. The only accepted positive manual-review decision label is
`approved-for-manual-release-review`, and even that does not approve release.

## Accepted Example

```json
{
  "artifactVersion": "wolfystock_manual_release_approval_review_record_v1",
  "releaseCandidateSha": "5a72431e4baf7fa87d43ecae73a10d831451bafb",
  "reviewerRoleLabels": ["release-manager", "security-reviewer"],
  "approvalMeetingOrTicketRef": "release-review-ticket-2026-05-08",
  "approvalTimestamp": "2026-05-08T10:45:00Z",
  "evidenceBundleRef": "launch-acceptance-evidence-pack-v1",
  "knownResidualRisks": [
    "async-enrichment-risk-acknowledged",
    "manual-rollback-risk-acknowledged"
  ],
  "rollbackOwnerLabel": "release-rollback-owner",
  "goNoGoDecision": "approved-for-manual-release-review",
  "evidenceRedactionVersion": "manual-release-review-redaction-v1"
}
```

Run the validator:

```bash
python3 scripts/manual_release_approval_evidence_check.py \
  --artifact <sanitized-manual-release-review-record.json>
```

A valid review record returns `manualReviewStatus: review-record-valid` and
`releaseApproved: false`.

## Rejected Snippets

These snippets are intentionally rejected:

```json
{
  "releaseApproved": true
}
```

```json
{
  "reviewerRoleLabels": ["person@example.invalid"]
}
```

```json
{
  "rawMeetingTranscript": "<raw transcript omitted>"
}
```

```json
{
  "knownResidualRisks": []
}
```

```json
{
  "notes": "Production-ready automatic-GO approved for launch."
}
```

## Scope Boundary

This checker is a standalone review-record validator. It does not modify:

- `scripts/launch_acceptance_evidence.py`
- `scripts/release_gate_summary.sh`
- release acceptance fixtures
- public launch readiness documents
- runtime release gate behavior

Launch acceptance remains manual-review gated, and `releaseApproved` must not
be auto-derived or trusted from arbitrary input.
