# T-1514 MFA Recovery-Code Login/Session Contract Audit

Task ID: T-1514
Task title: MFA recovery-code login/session contract audit
Validation profile: PROFILE_MFA_RECOVERY_CONTRACT_AUDIT_SCOPED
Status: audit-only, not production MFA recovery acceptance

## Scope

Audited the current backend MFA recovery-code and session contract without changing auth runtime behavior.

Primary source surfaces:

- `api/v1/endpoints/auth.py`
- `src/services/admin_mfa_service.py`
- `src/auth.py`
- `src/postgres_identity_store.py`
- `tests/api/test_auth_mfa_foundation.py`
- `tests/test_auth_api.py`
- `tests/test_auth.py`
- `docs/audits/index-security-rbac-mfa.md`
- `docs/audits/auth-rbac-release-security-guide.md`
- `docs/audits/security-mfa-secret-storage-hardening-plan.md`
- `docs/audits/production-security-hardening-audit.md`

Forbidden central launch docs and operator registry files were not edited.

## Current Contract Summary

MFA login enforcement is disabled by default behind `WOLFYSTOCK_MFA_LOGIN_ENFORCEMENT_ENABLED`. The only supported enforcement scope is admin-only; unsupported scope or non-admin-only rollout mode fails closed with `mfa_required`. See `api/v1/endpoints/auth.py:414`, `api/v1/endpoints/auth.py:424`, and `api/v1/endpoints/auth.py:561`.

Recovery codes are generated only for an MFA-enabled user, returned in plaintext only in the generation/rotation response, and persisted as salted password-hash entries in a versioned JSON envelope. Rotating codes marks prior active sets as replaced. See `api/v1/endpoints/auth.py:1208` and `src/services/admin_mfa_service.py:392`.

Recovery-code verification normalizes the submitted code, compares against the active unused hashes, marks the matching entry with `used_at`, updates `mfa_last_verified_at`, and returns only a boolean plus remaining count. Replay is denied because used entries are skipped. See `src/services/admin_mfa_service.py:437`.

Login enforcement first requires a complete admin MFA state: `mfa_enabled`, a secret ref, `mfa_enabled_at`, and at least one active unused recovery code. TOTP success, recovery-code success, and break-glass success each let login continue to normal session creation. See `api/v1/endpoints/auth.py:604`, `api/v1/endpoints/auth.py:626`, `api/v1/endpoints/auth.py:642`, and `api/v1/endpoints/auth.py:668`.

Successful recovery-code login issues the same signed app-user session cookie path as password/TOTP login. The response `currentUser` does not include recovery-code material, session id, MFA method, or MFA verification timestamp. See `api/v1/endpoints/auth.py:1807` and `api/v1/endpoints/auth.py:1828`.

Session validation checks signed-token integrity, token expiration, backing `app_user_sessions` row ownership, row revocation, row expiration, admin idle timeout, and then touches `last_seen_at`. See `src/auth.py:640`.

Audit events for MFA login decisions and recovery-code/break-glass events use hashed account/user/IP/user-agent identifiers and boolean/reason-code metadata, not raw submitted codes, passwords, TOTP secrets, or raw break-glass reason text. See `api/v1/endpoints/auth.py:449` and `api/v1/endpoints/auth.py:491`.

## Confirmed Safe Behaviors

- Default-off posture: MFA login enforcement and break-glass login are both disabled unless explicit env switches are set.
- Scope fail-closed: unsupported MFA login scope and non-admin-only pilot mode deny admin login instead of silently widening enforcement.
- Recovery generation/display: plaintext codes are returned only on generate/rotate responses and are not stored as plaintext in `mfa_recovery_codes_hash`.
- Hash storage: persisted recovery entries use the existing versioned password KDF hash format.
- Consume once: a successful recovery-code verification marks one active code used and replay is denied.
- Rotation/revocation: rotating codes replaces prior active sets; disabling MFA clears the secret ref and recovery-code envelope.
- Login replay denial: after one recovery-code login consumes a code, a second login with the same code receives `mfa_required` and no session cookie.
- Stale/revoked session denial: a session created via recovery-code login is rejected after the backing session row is revoked.
- Audit redaction: response and mocked audit payload tests assert no raw recovery code, TOTP secret, password, provisioning URI, or break-glass reason appears in responses/audit calls.

## Remaining Gaps Before Production MFA Recovery Acceptance

1. No production acceptance yet. The current code is a disabled-by-default pilot path; this audit does not approve broad MFA enforcement, public launch, or production recovery rollout.

2. No MFA method/session marker. A successful recovery-code login becomes a normal app-user session with no stored or response-level `mfa_method`, `mfa_verified_at`, or `recovery_code_used` session attribute. Production acceptance should decide whether downstream admin actions need method-aware session state or step-up evidence.

3. No pending-MFA login session contract. Missing MFA or invalid MFA during login returns `401 mfa_required` and no cookie. That is safe, but there is no intermediate pending session/challenge contract for multi-step login UX. Production acceptance should explicitly choose one-step credential+MFA login or design a pending-session flow.

4. Recovery-code consume is not proven concurrent-safe. The current helper performs read/verify/mutate/write through the repository without an explicit row lock or compare-and-set contract in this audit. Production acceptance needs a race test or storage-level atomic consume guarantee before relying on recovery codes under concurrent login attempts.

5. Production secret custody remains unaccepted. TOTP secret storage supports encrypted refs via env-provided key material, but the helper still documents this phase as a scaffold until a production encryption service is approved.

6. Recovery-code login audit is sanitized but not target-environment accepted. Existing tests use synthetic users and mocked audit recording. Production acceptance still needs sanitized operator evidence from the target environment with raw-value redaction proof.

7. Session policy after MFA changes is not recovery-specific. Disable/rotation clears or replaces MFA recovery state, but active sessions are not explicitly method-scoped or recovery-method-revoked because sessions do not record MFA method. Production acceptance should define whether recovery-code login sessions must be invalidated on MFA disable, rotation, or incident rollback.

## Test Evidence Added

Added focused contract-audit assertions to `tests/api/test_auth_mfa_foundation.py`:

- `test_mfa_recovery_code_login_session_contract_has_no_method_state`
- `test_mfa_recovery_code_login_session_rejects_after_row_revoked`

These tests assert current behavior and gaps only. They do not require runtime changes.

## Validation Results

- `PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python -m pytest -p no:cacheprovider tests/api/test_auth_mfa_foundation.py -q` - passed, 26 tests.
- `PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python -m pytest -p no:cacheprovider tests/test_auth.py::AuthSessionTestCase tests/test_auth_api.py::AuthApiTestCase::test_logout_invalidates_existing_session tests/test_auth_api.py::AuthApiTestCase::test_admin_current_user_exposes_safe_sorted_capability_summary -q` - passed, 8 tests.
- `PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python -m pytest -p no:cacheprovider tests/test_security_operator_acceptance_check.py -q` - passed, 14 tests.
- `PYTHONDONTWRITEBYTECODE=1 /Users/yehengli/daily_stock_analysis/.venv/bin/python -m py_compile tests/api/test_auth_mfa_foundation.py` - passed.
- `git diff --check` - passed.
- `./scripts/release_secret_scan.sh --base-ref origin/main` - passed, no high-confidence secret patterns in changed text files.

## No Runtime Change Proof

Runtime source files were inspected but not modified:

- `api/v1/endpoints/auth.py`
- `src/services/admin_mfa_service.py`
- `src/auth.py`
- `src/postgres_identity_store.py`
- `api/deps.py`

Changed files are limited to this task-specific audit report and focused MFA tests.

## Production Acceptance Posture

NO-GO for production MFA recovery acceptance until the remaining gaps above are resolved and reviewed with sanitized target-environment operator evidence. This audit is not public launch approval and does not enable broad MFA enforcement.

## Rollback

After commit, revert with:

```bash
git revert <commit>
```
