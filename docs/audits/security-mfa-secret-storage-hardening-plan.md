# Security MFA Secret Storage Hardening Plan

Status: Deferred
Owner domain: Production security
Related docs: `docs/audits/security-admin-mfa-backend-foundation.md`, `docs/audits/production-security-hardening-audit.md`

Date: 2026-05-07
Branch checked: `main`
Mode: docs-only security design / rollout plan. No runtime auth or MFA code,
storage/schema, tests, Options, Data Pipeline, Provider Circuit, cost/quota,
scanner, backtest, or portfolio behavior was changed.

## 1. Current scaffold and production gap

Admin MFA has a backend foundation, but login enforcement remains disabled. The
current service can start enrollment, verify enrollment, verify an enabled MFA
code, disable MFA, and manage recovery codes for the current admin session.

Current TOTP secret posture:

- `src/services/admin_mfa_service.py` generates a base32 TOTP secret during
  enrollment start.
- Enrollment start returns the raw TOTP secret and provisioning URI once so the
  admin can add it to an authenticator app.
- Later MFA verify/disable responses do not return the raw TOTP secret.
- Tests use `WOLFYSTOCK_MFA_TEST_SECRET` and a deterministic `test-only:` secret
  reference so verification can run without production encryption.
- Non-test generated secrets are persisted only as `placeholder-sha256:<digest>`
  references, which are intentionally not recoverable for production TOTP
  verification.

Production gap:

- A hash-only TOTP secret reference cannot verify future TOTP codes.
- A recoverable TOTP secret must not be stored as plaintext in application rows,
  logs, audit details, API responses, fixtures, or migration output.
- MFA enforcement cannot be enabled until production storage can recover the
  secret only inside the verification path and recovery codes are integrated
  into the final MFA-required session contract.

## 2. Candidate storage strategies

### Application-level envelope encryption

Store an encrypted secret envelope in `mfa_secret_ref` or a future dedicated
secret column. The application generates a data-encryption key, encrypts the TOTP
secret with authenticated encryption, encrypts the data key with a configured
master key, and stores only ciphertext plus metadata.

Recommended envelope shape:

```text
$wolfystock$mfa-secret=v1$mode=envelope$kid=<key-id>$alg=<aead>$created=<iso8601>$ciphertext=<base64url>
```

Advantages:

- Works with SQLite and PostgreSQL without requiring database-specific crypto.
- Keeps storage portable across local, Docker, and future PostgreSQL modes.
- Allows key rotation through envelope metadata.
- Can be tested deterministically with fake keys without exposing real secrets.

Risks and requirements:

- Master-key loading must be production-grade and must not come from committed
  config or logs.
- Backup/restore must include key escrow or KMS recovery planning.
- The application must fail closed when the key is missing, wrong, disabled, or
  too old for policy.

### OS, keychain, or KMS-backed secret encryption

Use an operating-system keychain, cloud KMS, HSM, or deployment secret provider
to wrap the per-secret data key or directly encrypt/decrypt the TOTP secret.

Advantages:

- Stronger key custody than a static application key.
- Central key rotation, access policy, and audit can be delegated to the
  platform.
- Production compromise blast radius can be reduced if application storage is
  copied without key access.

Risks and requirements:

- Local development, CI, Docker, and production must have explicit provider
  behavior instead of hidden environment-specific branches.
- The service must define startup/readiness behavior when KMS is unavailable.
- KMS latency and rate limits must not make MFA verification brittle.
- Provider failures need sanitized operational logging without secret material.

### External secret manager

Store each TOTP secret as a separate object in a secret manager and persist only
an opaque reference in the user row.

Example reference:

```text
$wolfystock$mfa-secret=v1$mode=external$provider=<provider>$ref=<opaque-id>$version=<secret-version>$kid=<key-id>
```

Advantages:

- Avoids storing recoverable secret ciphertext in the application database.
- Secret manager access control, version history, audit, and rotation can be
  managed centrally.
- Secret retrieval can be scoped to the MFA verification service path.

Risks and requirements:

- External availability becomes part of login and admin access reliability once
  MFA enforcement is enabled.
- Backup/restore must reconcile database references with external secret objects.
- Deleting or rotating a secret object must stay transactionally consistent with
  the user MFA state.
- Local and test modes need a fake provider that never resembles production
  plaintext storage.

### Database encrypted column strategy

Use database-native encrypted columns or database crypto functions for the TOTP
secret while preserving application-level metadata.

Advantages:

- May reduce application crypto surface if the production database already
  provides approved encryption primitives and key custody.
- Queries and backups can stay inside database operational boundaries.

Risks and requirements:

- SQLite/local compatibility needs a separate implementation path.
- Database admins or backup operators may still have access depending on key
  custody and deployment policy.
- PostgreSQL-specific crypto can complicate coexistence with current SQLite
  fallback posture.
- Rotation and audit metadata still need explicit application handling.

## 3. Recommended strategy

Recommended first production implementation: application-level envelope
encryption with a KMS/keychain-backed master key where production deployment
supports it, plus a fake in-memory provider for tests.

Why this is the best fit now:

- It preserves the current SQLite and PostgreSQL coexistence posture.
- It does not require moving TOTP secrets into a new external dependency before
  the MFA session contract is finalized.
- It can use `mfa_secret_ref` as a versioned envelope reference first, then move
  to a dedicated encrypted secret column later if schema ownership changes.
- It gives the verifier enough metadata to fail closed, rotate keys, and audit
  sanitized storage state.

External secret manager storage should remain the target for larger production
deployments if the deployment already has managed secrets, operator access
policy, and restore drills. Database encrypted columns should be a
deployment-specific option, not the portable default.

## 4. Required metadata

The production secret envelope or external reference must carry enough metadata
to make verification and rotation auditable without exposing the secret.

Required fields:

- `secret_version`: storage-envelope version, starting at `1`.
- `key_id`: KMS/keychain/master-key identifier used to wrap or encrypt the
  secret.
- `created_at`: when the current secret was enrolled.
- `rotated_at`: when the secret was last replaced or re-encrypted, nullable for
  first enrollment.
- `enabled_at`: when the admin successfully verified enrollment and MFA became
  enabled.
- `last_verified_at`: when TOTP or recovery-code verification last succeeded.

Recommended optional fields:

- `storage_mode`: `envelope`, `external`, `db_encrypted`, or `test_only`.
- `algorithm`: authenticated encryption algorithm and parameter version.
- `external_ref`: opaque secret-manager id when using external storage.
- `status`: `pending_enrollment`, `enabled`, `disabled`, `rotation_pending`, or
  `retired`.
- `previous_key_id`: only for sanitized rotation audit, never for decryption
  fallback unless the key policy explicitly allows it.

Metadata rules:

- Metadata may be logged only after sanitization.
- No metadata field may contain the raw TOTP secret, provisioning URI, recovery
  code, encrypted data key, plaintext key, session id, cookie, token, or
  password hash.
- Unknown or malformed secret references must fail closed with generic MFA
  errors.

## 5. Secret lifecycle

### Enrollment

1. Require an authenticated admin session and recent admin reauth.
2. Generate a new random base32 TOTP secret.
3. Encrypt or externalize the secret before writing user metadata.
4. Store a pending MFA state with `mfa_enabled=false`, secret metadata,
   `created_at`, and no `enabled_at`.
5. Return the raw secret and provisioning URI only in the enrollment-start
   response.
6. Never return the raw secret again, including enrollment status, verify,
   disable, logs, traces, or errors.

### Verification

1. Load the secret reference for the current user.
2. Resolve and decrypt the secret only inside the MFA verification path.
3. Verify the submitted TOTP code with the existing time-window policy.
4. On success, set `enabled_at` and `last_verified_at` during enrollment verify,
   or update only `last_verified_at` for normal verification.
5. On failure, return a generic invalid-code response and do not reveal whether
   decryption, missing key, wrong key, expired key, or code mismatch caused the
   failure.

### Rotation

TOTP rotation should be a first-class lifecycle operation, separate from recovery
code rotation.

1. Require authenticated admin, recent reauth, and current MFA proof unless the
   user is in a documented recovery flow.
2. Create a new pending encrypted/external secret.
3. Display the new secret once.
4. Enable the new secret only after successful verification.
5. Retire the prior secret after the new one is verified.
6. Write sanitized audit metadata with old/new storage versions and key ids, not
   secret values or ciphertext.

Key rotation should be separate from TOTP rotation:

- Rewrap or re-encrypt the existing TOTP secret with a new key id.
- Keep `enabled_at` unchanged.
- Update `rotated_at` or a dedicated key-rotation timestamp.
- Test rollback behavior before retiring the old key.

### Disable

1. Require authenticated admin and recent reauth.
2. Require current MFA proof when enforcement is active, except for a documented
   break-glass support path.
3. Delete or retire the encrypted/external TOTP secret.
4. Clear or mark inactive the recovery-code set.
5. Set `mfa_enabled=false` and clear active secret references.
6. Audit only sanitized status, user id/account hash, actor, and reason code.

### Recovery-code interaction

Recovery codes are already display-once and stored only as salted hashes. The
production TOTP secret plan must preserve that posture.

- Recovery codes may satisfy a future MFA challenge only under the final
  MFA-required session contract.
- Recovery-code verification must consume exactly one active code.
- Recovery-code generation and rotation must keep requiring recent admin reauth.
- TOTP secret rotation should normally rotate recovery codes as part of the same
  operator flow or prompt the admin to regenerate them immediately.
- Disabling MFA must clear or retire active recovery-code hashes.

## 6. Migration path from scaffold to production storage

The existing scaffold has two relevant states:

- `test-only:<secret>`: deterministic test-only secret reference.
- `placeholder-sha256:<digest>`: production-like hash-only placeholder that
  cannot recover a TOTP secret.

Recommended migration:

1. Add a production `MfaSecretStore` abstraction with explicit providers:
   `test_fake`, `envelope`, and optionally `external`.
2. Add a parser for versioned secret references and keep current scaffold
   prefixes recognized only as legacy states.
3. Keep `test-only:` support limited to tests and local deterministic fixtures.
   It must be impossible to enable in production mode.
4. Treat `placeholder-sha256:` rows as migration-incomplete. They cannot be
   auto-upgraded because the raw secret is unavailable.
5. For any admin with a placeholder secret, require re-enrollment into the
   encrypted/external store before enforcement.
6. Write a one-time audit/report command that counts MFA states by sanitized
   storage mode and migration readiness without printing references.
7. Only after all enforced admin accounts have production secret storage and
   recovery codes should login enforcement be piloted.

Compatibility requirements:

- Existing rows must continue to disable cleanly.
- Existing non-enforced login behavior must remain unchanged until explicit MFA
  enforcement rollout.
- Scaffold parsing must never produce a raw secret outside test-only execution.
- Migration logs must not print `mfa_secret_ref` values.

## 7. Audit and logging rules

Hard rules:

- Never log the raw TOTP secret.
- Never log the provisioning URI because it embeds the raw TOTP secret.
- Never expose the raw TOTP secret after enrollment start.
- Never log recovery-code plaintext.
- Never log encrypted payloads, wrapped data keys, KMS responses, session ids,
  cookies, tokens, password hashes, provider credentials, or `.env` values.

Allowed sanitized audit metadata:

- actor user id or stable account hash;
- target user id or stable account hash;
- event type such as `mfa_enrollment_started`, `mfa_enabled`, `mfa_verified`,
  `mfa_totp_rotated`, `mfa_key_rewrapped`, `mfa_recovery_codes_generated`,
  `mfa_recovery_code_used`, and `mfa_disabled`;
- storage mode;
- secret version;
- key id;
- previous/new key id for rotation, if not sensitive in the selected KMS;
- timestamps;
- result code such as `success`, `invalid_code`, `missing_key`,
  `decrypt_failed`, `storage_unavailable`, or `policy_blocked`;
- request/session correlation id after existing sanitization.

Failure logging:

- User/API responses should stay generic.
- Internal logs may use sanitized reason codes but must not include raw exception
  payloads from KMS/secret-manager providers unless reviewed and redacted.
- Alerting should trigger on repeated decrypt failures, missing keys, malformed
  envelopes, unexpected `test-only` references in production mode, and attempts
  to verify placeholder-only secrets under enforcement.

## 8. Test plan

Unit tests:

- Encryption/decryption roundtrip returns the original TOTP secret only inside
  the secret-store API.
- Wrong key id or wrong key material fails closed.
- Malformed envelope fails closed.
- Unsupported storage mode fails closed.
- `test-only:` references are rejected outside test mode.
- `placeholder-sha256:` references cannot verify under production mode.
- Rotation creates a new encrypted/external secret and retires the old reference
  only after verifying the new code.
- Key rewrap changes key metadata without changing the TOTP secret.

API/service tests:

- Enrollment start returns raw secret once and stores only encrypted/external
  reference metadata.
- Enrollment verify enables MFA and records `enabled_at` and
  `last_verified_at`.
- Normal verify updates `last_verified_at` and does not expose the secret.
- Disable clears active secret and recovery-code state.
- Recovery-code generation/rotation/verification still returns plaintext only
  once and stores only salted hashes.
- Login remains non-enforcing until the rollout flag/session contract changes.

Leakage tests:

- Response bodies for verify, disable, recovery-code verify, errors, and audit
  reads never contain raw TOTP secret, provisioning URI, recovery-code plaintext,
  encrypted payload, data key, session id, token, cookie, password hash, or
  secret-manager reference payload.
- Log capture for success and failure paths contains only sanitized reason
  codes.
- `git diff`, fixtures, snapshots, and test output do not include real secrets.

Backup/restore tests:

- Restored database plus restored key material can verify an enrolled TOTP code.
- Restored database without key material fails closed with sanitized operational
  errors.
- External secret-manager references survive restore or are reported as
  migration-incomplete.
- Key rotation backup windows are documented so a backup taken before key
  retirement remains restorable.

## 9. Enforcement blockers and rollout sequence

Current enforcement blockers:

- No approved production TOTP secret encryption or external secret storage.
- No final MFA-required login/session contract.
- No recovery-code fallback integration into enforced login.
- No break-glass/admin recovery procedure for lost device plus lost recovery
  codes.
- No production key custody, rotation, restore, and missing-key runbook.
- No audit policy for decrypt failures, rotation, disable, and recovery-code
  usage under enforcement.

Recommended rollout:

1. Land secret-store abstraction behind the existing non-enforcing MFA endpoints.
2. Implement envelope encryption with fake test provider and production key
   loader/KMS integration.
3. Add sanitized audit events and leakage tests.
4. Add re-enrollment flow for placeholder rows and production-mode rejection of
   `test-only:` references.
5. Run a migration-readiness report and re-enroll all admin accounts that will
   be subject to enforcement.
6. Finalize MFA-required login/session states, including recovery-code fallback
   and rollback behavior.
7. Pilot enforcement for one admin/security role in staging or local production
   simulation.
8. Enable enforcement for production admin roles with explicit rollback: disable
   enforcement flag first, do not delete encrypted secrets, and keep
   recovery-code verification available.

Go/no-go rule:

- MFA enforcement is NO-GO until encrypted/external TOTP secret storage,
  recovery-code fallback, key restore drill, leakage tests, and rollback plan all
  pass.

## 10. Recommended implementation prompt

```text
Task: Implement production MFA TOTP secret storage foundation

Repo:
cd /Users/yehengli/daily_stock_analysis
Branch: main

Read first:
- docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md
- docs/audits/security-admin-mfa-backend-foundation.md
- docs/audits/security-password-kdf-upgrade-plan.md
- docs/audits/security-mfa-secret-storage-hardening-plan.md
- src/services/admin_mfa_service.py
- api/v1/endpoints/auth.py
- src/repositories/auth_repo.py
- src/storage.py
- src/postgres_identity_store.py
- tests/api/test_auth_mfa_foundation.py

Goal:
Add a production-ready MFA secret-store foundation while keeping login MFA
enforcement disabled.

Scope:
- Add a small MFA secret-store abstraction.
- Support test fake storage and application-level encrypted envelope storage.
- Preserve current recovery-code hashing behavior.
- Reject test-only secret references outside test mode.
- Treat placeholder-sha256 references as migration-incomplete.
- Add sanitized audit/log reason codes where existing audit plumbing supports
  them.
- Add focused tests for roundtrip, wrong key, malformed envelope, rotation, and
  no secret leakage.

Do not touch:
- login MFA enforcement
- unrelated auth/RBAC behavior
- Options
- Data Pipeline
- Provider Circuit
- cost/quota/admin cost
- scanner/backtest/portfolio
- provider ordering/fallback, MarketCache, LLM routing/prompts, broker/order
  paths

Validation:
- python3 -m py_compile <changed_python_files>
- pytest tests/api/test_auth_mfa_foundation.py -q
- git diff --check -- <changed_files>

Final report additions:
- storage mode implemented
- migration behavior for test-only and placeholder rows
- leakage test evidence
- confirmation login enforcement remains disabled
```
