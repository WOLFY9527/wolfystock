# Operator Evidence Schema Reference Guide

This guide covers `scripts/operator_evidence_schema_reference.py`, an offline
helper that renders a sanitized operator-facing reference from the existing
operator evidence template pack and bundle checker category metadata.

## Purpose

Operators can use the generated reference to see each evidence category,
expected artifact filename, required top-level fields, safe placeholder
examples, redaction notes, validator script, and review posture without reading
internal launch acceptance artifacts.

The reference is not evidence and does not approve a release. It always states
manual review is required and `releaseApproved=false`.

## Generate

Render Markdown:

```bash
python3 scripts/operator_evidence_schema_reference.py render \
  --output /tmp/operator-evidence-schema-reference.md
```

Render Markdown plus JSON:

```bash
python3 scripts/operator_evidence_schema_reference.py render \
  --output /tmp/operator-evidence-schema-reference.md \
  --json-output /tmp/operator-evidence-schema-reference.json
```

## Safety

The renderer is offline only. It derives shape from local template definitions
and validator category metadata. It does not read environment values,
deployment state, credentials, cookies, sessions, databases, provider payloads,
or real evidence artifacts.

Use `docs/audits/operator-evidence-template-pack-guide.md` to generate fillable
templates and `docs/audits/operator-evidence-redaction-checklist.md` before
handoff.
