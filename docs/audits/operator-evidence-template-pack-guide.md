# Operator Evidence Template Pack Guide

This guide covers `scripts/operator_evidence_template_pack.py`, an offline helper
that creates sanitized JSON templates for operator and release-review evidence
collection.

## Purpose

The template pack gives operators a consistent starting point for artifacts
validated by the existing offline evidence checkers:

- provider operator evidence
- restore/PITR operator evidence
- security MFA/RBAC operator acceptance
- quota/budget operator evidence
- staging ingress operator evidence
- WS2/SSE topology operator decision evidence
- config snapshot evidence
- manual release approval review record

Generated templates are not real evidence. They intentionally use
`needs-review` outcomes or review-only placeholders and must be replaced with
operator-sanitized summaries before any release review.

## Safe Use

Generate every template into a local directory:

```bash
python3 scripts/operator_evidence_template_pack.py /tmp/wolfystock-operator-evidence-templates
```

Generate one category:

```bash
python3 scripts/operator_evidence_template_pack.py --category provider /tmp/wolfystock-operator-evidence-templates
```

Print templates without writing files:

```bash
python3 scripts/operator_evidence_template_pack.py --stdout --category config-snapshot
```

The generator refuses to overwrite existing files unless `--force` is passed:

```bash
python3 scripts/operator_evidence_template_pack.py --force /tmp/wolfystock-operator-evidence-templates
```

## Redaction Expectations

Before attaching any completed artifact to a review, replace placeholders only
with sanitized labels, bounded summaries, enum values, counts, booleans, and
review references. Keep all real operational material outside the evidence
bundle.

Do not include:

- real service locations or credential-bearing locations
- personal contact details
- credential values or credential-like strings
- browser or API session material
- database connection strings
- raw logs
- request or response bodies
- stack traces
- provider payloads
- meeting transcripts, screenshots, or chat exports

Use labels such as `<sanitized-operator-label>`,
`<staging-environment-label>`, `<redacted-or-configured>`,
`<review-ticket-label>`, and `<release-candidate-sha>` until an operator has
prepared sanitized values.

## Validation

After operators fill the templates with sanitized summaries, run the matching
offline validators. The template generator itself does not call these validators
and is not wired into launch acceptance.

Useful checks:

```bash
python3 scripts/operator_evidence_bundle_check.py <sanitized-operator-evidence-dir>
python3 scripts/ws2_sse_operator_decision_check.py <sanitized-ws2-sse-operator-decision.json>
python3 scripts/config_snapshot_evidence_check.py <sanitized-config-snapshot-evidence.json>
python3 scripts/manual_release_approval_evidence_check.py --artifact <sanitized-manual-release-review-record.json>
```

The validator outputs remain advisory review evidence. They do not approve a
launch and do not change runtime behavior.
