# Quota Reserve/Release Operator Evidence Checklist

Date: 2026-06-10
Scope: internal/private-beta evidence checklist for the default-off quota
reserve/release advisory pilot on authenticated sync single-stock analysis.

This checklist is for evidence-gathering only. It does not approve public
launch, does not approve live quota enforcement, and does not approve
reservation consume wiring. Public launch remains **NO-GO**. Consume and live
enforcement remain **NO-GO**.

## Pilot Boundaries That Must Already Be True

Collect evidence only if all of the following are true:

- The pilot flag is default-off and remains disabled by default.
- Owner access is controlled by an explicit allowlist.
- Eligibility is limited to auth-enabled, authenticated, non-transitional,
  sync, single-stock analysis only.
- The pilot is reserve-only with guaranteed release on every path.
- Reserve and release remain fail-open advisory semantics.
- API response shape does not change.
- Execution metadata does not expose raw reservation IDs.

Reject the run if any prerequisite is false or cannot be proven with sanitized
evidence.

## Evidence Packet Rules

- Evidence is internal/private-beta only.
- Use sanitized excerpts only.
- Prefer booleans, bounded labels, counts, timestamps, route labels, and reason
  codes.
- Do not treat this checklist as public-launch evidence or live-enforcement
  approval.

## Offline Validator

Operators can run the offline checker against a sanitized JSON artifact, or a
directory of sanitized JSON artifacts:

```bash
python3 scripts/quota_reserve_release_operator_evidence_check.py \
  <sanitized-quota-reserve-release-evidence.json-or-directory>
```

The checker validates sanitized local evidence against the categories in this
checklist. It must not be pointed at live systems and does not call runtime
APIs, route handlers, storage, quota services, providers, auth, or live
credentials. A passing result means the evidence packet is ready for manual
internal/private-beta review only. It does not approve public launch, live
quota enforcement, reservation consume wiring, route blocking, or runtime
behavior changes.

## Required Evidence Sections

### 1. Config Snapshot

Provide a sanitized config snapshot proving:

- the pilot is disabled by default;
- owner access requires an explicit allowlist;
- no public/global enablement exists.

Allowed proof examples:

- feature flag name plus `enabledByDefault=false`;
- allowlist presence as `ownerAllowlistConfigured=true`;
- route scope label such as `sync_single_stock_only`.

### 2. Synthetic Or Private-Beta Success Case

Provide one sanitized sync single-stock success case proving:

- an eligible authenticated request entered advisory reserve/release handling;
- the analysis still completed successfully;
- response shape stayed unchanged;
- the evidence is from synthetic or private-beta usage only.

### 3. Reserve Failure Fail-Open Case

Provide a sanitized case where reserve fails and prove:

- the analysis request still proceeded;
- no blocking/consume behavior occurred;
- user-visible response behavior remained unchanged except for internal
  advisory evidence.

### 4. Analysis Failure With Finally Release

Provide a sanitized case where analysis fails after reserve and prove:

- release ran from the `finally` path;
- the response or error behavior matched the pre-pilot behavior;
- no quota fields were exposed in the response shape.

### 5. Release Failure Fail-Open Warning

Provide a sanitized case where release fails and prove:

- the failure is recorded as advisory warning/evidence only;
- the user response is not mutated to include quota internals;
- no blocking or consume behavior is introduced.

### 6. Execution-Log Metadata Safety Proof

Provide a sanitized execution-log metadata excerpt proving the metadata is
bounded and does not leak raw identifiers or sensitive context.

The proof must show only bounded booleans or bounded labels and must show the
absence of:

- raw reservation IDs;
- idempotency keys or hashes;
- owner allowlist values;
- raw owner, user, request, session, provider, or exception data.

### 7. Quota Window Before/After Proof

Provide sanitized before/after proof that:

- advisory reserve increments are released correctly;
- no reserved units remain leaked after completion or failure;
- the observed window returns to the expected post-release state.

### 8. Rollback Proof

Provide sanitized rollback proof by either:

- disabling the pilot flag; or
- removing the owner from the explicit allowlist.

The proof must show the route returns to fully out-of-scope behavior without
changing API response shape.

## Do Not Capture

Do not capture or attach any of the following:

- raw `reservation_id`
- idempotency key or idempotency hash
- owner allowlist values
- raw owner, user, session, cookie, token, header, or body data
- `stock_name`, `original_query`, or raw user text
- provider or model payloads
- raw exception text or stack traces
- credentials or secrets

## Stop / Reject Evidence

Stop collection and reject the evidence packet if any of the following occurs:

- reserve or release appears outside sync analysis;
- any consume or blocking behavior appears;
- response shape exposes quota fields;
- raw identifiers or secrets appear in logs or evidence;
- auth-disabled, transitional, guest, async, scanner, agent, or options paths
  become eligible;
- protected code, config, or deployment changes are required.

## Future Live-Enforcement Blockers

This checklist does not close live-enforcement readiness. Future live
enforcement remains blocked until all of the following are accepted:

- stable client retry and request identity;
- reservation ID propagation into the quota ledger;
- exact-once consume tied to actual cost result;
- crash and timeout reconciliation;
- admin read-only pilot status;
- rollback and staging evidence;
- explicit block contract and tests.

## Operator Wording Requirements

Use precise wording throughout the packet:

- `advisory`
- `default-off`
- `internal/private-beta`
- `evidence-gathering only`

Do not use wording that implies:

- public launch approval;
- live quota enforcement approval;
- consume approval;
- route-blocking approval.

## Expected Outcome

If every section above is satisfied with sanitized excerpts only, the result is
an internal/private-beta evidence packet for manual review. The result is still
not public launch approval, still not consume approval, and still not live
quota enforcement approval.
