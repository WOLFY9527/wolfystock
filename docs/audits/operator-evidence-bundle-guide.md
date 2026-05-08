# Operator Evidence Bundle Guide

Date: 2026-05-08
Scope: domain-local, offline review bundle for sanitized operator evidence.

This guide explains how to run the local bundle checker against a directory of
sanitized operator JSON artifacts. The checker is a review aid only. It is not
connected to the shared launch acceptance evidence generator, and it does not
make a final release decision.

## Required Directory Contents

Create a local artifact directory containing these sanitized JSON files:

- `provider_operator_evidence.json`
- `restore_pitr_operator_evidence.json`
- `security_operator_acceptance.json`
- `quota_budget_operator_evidence.json`
- `staging_ingress_operator_evidence.json`
- `ws2_sse_operator_decision_evidence.json`
- `config_snapshot_evidence.json`
- `manual_release_approval_review_record.json`

Each file must already follow its domain-specific evidence guide and validator
contract. Unknown extra `*.json` files are not validated as required evidence;
the bundle checker reports them as advisory items for human review.

## Safe Local Command

Run the bundle checker from the repository root:

```bash
python3 scripts/operator_evidence_bundle_check.py path/to/sanitized-artifact-dir
```

The checker:

- reads only local JSON files in the provided directory;
- reuses the existing standalone validator logic for each required artifact;
- emits only filename labels, artifact categories, validator names, statuses,
  and reason-code summaries;
- never prints raw artifact bodies;
- never calls providers, databases, browsers, deployment tools, notification
  channels, or external networks;
- never reads `.env` files or secret values;
- never changes provider, auth, quota, ingress, storage, scanner, AI,
  portfolio, or backtest runtime behavior.

## Summary Statuses

The top-level `bundleStatus` can be:

- `complete-review-required`: all required files were present and no required
  validator rejected an artifact. Manual review is still required.
- `incomplete-no-go`: one or more required files were missing.
- `rejected-no-go`: one or more required validators rejected an artifact.

Artifact-level `status` can be:

- `accepted`
- `rejected`
- `missing`
- `needs-review`

The bundle checker intentionally does not emit a final approval status. A
`complete-review-required` result means only that the local sanitized bundle is
ready for human review.

## Output Shape

The summary JSON includes:

- `generatedAt`
- `bundleStatus`
- `artifactDirectoryLabel`
- `runtimeBehaviorChanged: false`
- `networkCallsExecutedByValidator: false`
- `rawArtifactBodiesIncluded: false`
- `artifacts[]` with `category`, `pathLabel`, `status`, `validatorName`, and
  `blockingReasonSummaries`
- `advisories[]` for unknown extra JSON files

`pathLabel` is always a filename label, not an absolute path. Reason summaries
are validator reason codes or failed-check labels, not raw values from the
artifact.

## Manual Review Requirement

After a clean bundle run, a human reviewer must still inspect:

- whether each source artifact came from the intended operator process;
- whether evidence collection happened in the correct environment;
- whether timestamps and operator labels are plausible;
- whether domain-specific guide requirements were followed;
- whether any `needs-review` or advisory item blocks acceptance;
- whether a later, explicitly scoped task should wire accepted evidence into
  shared launch acceptance artifacts.

Do not copy bundle output into shared launch acceptance files unless a separate
task explicitly authorizes that integration.

## Related Domain Guides

- `docs/audits/provider-operator-evidence-guide.md`
- `docs/audits/db-real-restore-pitr-operator-evidence-guide.md`
- `docs/audits/security-operator-acceptance-evidence-guide.md`
- `docs/audits/quota-budget-operator-evidence-guide.md`
- `docs/audits/staging-ingress-operator-evidence-guide.md`
- `docs/audits/ws2-sse-operator-decision-evidence-guide.md`
- `docs/audits/config-snapshot-operator-evidence-guide.md`
- `docs/audits/manual-release-approval-evidence-guide.md`
