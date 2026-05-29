# Release Evidence Operator Handoff Checklist

Date: 2026-05-29
Scope: release/operator handoff after T-658 through T-665.

This checklist is a release-readiness handoff only. It does not approve launch,
does not change any release gate, and does not replace manual review.

## Current Launch Posture

- `completedFoundationEvidence` means repo-local/offline foundation evidence
  only.
- Foundation-complete blockers remain hard blockers until accepted sanitized
  launch evidence is attached for the target release candidate.
- `releaseApproved=false` remains required.
- Hard blockers stay blocking until accepted launch evidence and manual release
  approval requirements are both satisfied.
- Do not describe the current state as GO, launch-approved, or production-ready.

## Draft Evidence Clarification

- Draft evidence may only be used as manual-review-required support for the four
  foundation-complete blockers below.
- Draft output must never set `status: accepted`.
- Draft output must never auto-fill `acceptedBy`.
- Draft output must never auto-fill accepted `capturedAt` or accepted
  `evidenceRef`.
- Draft output must never mark required checks true solely from repo-local
  foundation evidence.
- Draft output must never set `releaseApproved=true`, `launchApproved=true`, GO,
  or production-ready wording.
- Frontend evidence, operator evidence, live-provider evidence, staging
  evidence, and other manual evidence must not be fabricated.
- The draft-support-only boundary applies to:
  `api_abuse_request_safety`,
  `admin_log_retention_capacity_rehearsal`,
  `market_data_freshness_fallback_evidence`, and
  `user_data_privacy_export_deletion_rehearsal`.
- Those four blockers remain blocking until accepted sanitized launch evidence
  and manual review are attached through the existing workflow.

## Foundation-Complete Internal Validation Blockers

### `api_abuse_request_safety`

- Repo-local/offline foundation now locked:
  request-safety regression anchors for limiter posture, malformed-request
  handling, oversized-payload fail-closed behavior, sanitized denial/audit
  output, and no traceback/request-body leakage.
- Accepted launch evidence still required:
  a sanitized operator artifact for the release candidate proving the accepted
  request-safety checks were reviewed and attached through the launch evidence
  workflow.
- Must not be claimed or fabricated:
  no accepted launch artifact, no live abuse rehearsal, no approval semantics,
  and no claim that current foundation evidence unblocks release by itself.

### `admin_log_retention_capacity_rehearsal`

- Repo-local/offline foundation now locked:
  preview-first cleanup anchors, explicit retention tiers, minimum-retention
  guard coverage, storage-pressure rehearsal coverage, and sanitized cleanup
  audit evidence with unchanged runtime defaults.
- Accepted launch evidence still required:
  a sanitized operator artifact for the release candidate showing the accepted
  retention/capacity rehearsal checks were captured and reviewed.
- Must not be claimed or fabricated:
  no completed launch rehearsal, no automatic cleanup approval, no release
  approval, and no suggestion that offline anchors are a substitute for accepted
  launch evidence.

### `market_data_freshness_fallback_evidence`

- Repo-local/offline foundation now locked:
  provider/as-of labeling anchors, stale/fallback disclosure anchors,
  confidence-cap behavior coverage, raw-provider-payload redaction, and
  unchanged runtime-default evidence.
- Accepted launch evidence still required:
  a sanitized operator artifact for the release candidate showing the accepted
  freshness/fallback evidence was reviewed and attached.
- Must not be claimed or fabricated:
  no live provider proof, no launch acceptance, no routing/fallback approval,
  and no claim that the repo-local disclosure anchors are sufficient for
  release.

### `user_data_privacy_export_deletion_rehearsal`

- Repo-local/offline foundation now locked:
  sanitized privacy-export projection anchors, deletion-preview rehearsal
  anchors, owner-isolation evidence, privacy-audit sanitization, and no raw
  user/session/provider data exposure in the covered repo-local paths.
- Accepted launch evidence still required:
  a sanitized operator artifact for the release candidate showing the accepted
  privacy export/deletion rehearsal checks were reviewed and attached.
- Must not be claimed or fabricated:
  no destructive delete completion, no unsupported runtime behavior change, no
  release approval, and no claim that future runtime design changes were
  completed here.

## Remaining Internal Validation Blockers

### `supply_chain_dependency_build_artifact_safety`

- Still blocking.
- Build/frontend dependent.
- Do not claim complete while frontend build evidence, frontend warning review,
  React Doctor follow-up, or related build-artifact evidence is unresolved.

### `final_clean_full_ci_gate`

- Still blocking.
- Final release-candidate gate only.
- Run last on the clean release candidate after the other required evidence is
  accepted.
- Do not claim partial completion from docs-only or foundation-only work.

## Non-Codex Or Non-Operator-Owned Blockers

### External/manual evidence blockers

- Accepted sanitized target-environment artifacts are still required for the
  launch evidence matrix.
- Manual release review remains required.
- Manual release approval remains external/manual even after all evidence is
  accepted.

### Frontend-owned blockers

- Frontend/build evidence remains outside this handoff.
- React Doctor ownership is elsewhere and out of scope for this document.
- Any blocker that depends on frontend build warnings, browser-proof evidence,
  or frontend no-secret/build validation must stay blocking until the owning
  lane closes it.

### Intentional policy blockers

- `releaseApproved=false` must remain unchanged in evidence outputs.
- `completedFoundationEvidence` must not be treated as accepted launch evidence.
- Manual approval requirements must not be weakened.
- Missing, pending, rejected, unsafe, or incomplete evidence remains NO-GO.

## Operator Handoff Checklist

1. Treat this document as a status handoff, not as approval evidence.
2. Use `completedFoundationEvidence` only as proof that repo-local/offline
   foundations are locked for the four blockers above.
3. Collect accepted sanitized launch artifacts for those four blockers through
   the existing launch evidence workflow; do not attach raw secrets, raw
   payloads, request bodies, or production data paths.
4. Keep `supply_chain_dependency_build_artifact_safety` open until the
   frontend/build owner closes the dependent evidence.
5. Run `final_clean_full_ci_gate` only on the final clean release candidate and
   only after the remaining required evidence is accepted.
6. Preserve the current approval posture: hard blockers remain blocking and
   `releaseApproved=false` until manual approval is complete.
