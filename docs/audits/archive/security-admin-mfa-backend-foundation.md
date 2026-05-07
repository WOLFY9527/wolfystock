# Security Phase 3E Admin MFA Backend Foundation

Status: Superseded
Owner domain: Production security
Replacement or related docs: `docs/audits/security-mfa-secret-storage-hardening-plan.md`, `docs/audits/production-security-hardening-audit.md`

Date: 2026-05-07
Branch checked: `main`

## Summary

Security Phase 3E adds a backend foundation for admin MFA without enforcing MFA
on login. The implementation is intentionally narrow: it adds storage metadata,
service helpers, and admin-only MFA endpoints that can enroll, verify, and
disable an MFA scaffold while preserving existing password login behavior.

## Added Backend Contract

- MFA metadata is stored on `app_users`:
  - `mfa_enabled`
  - `mfa_secret_ref`
  - `mfa_recovery_codes_hash`
  - `mfa_created_at`
  - `mfa_enabled_at`
  - `mfa_last_verified_at`
- Admin-only endpoints:
  - `POST /api/v1/auth/mfa/enroll/start`
  - `POST /api/v1/auth/mfa/enroll/verify`
  - `POST /api/v1/auth/mfa/verify`
  - `POST /api/v1/auth/mfa/disable`
- Enrollment verification and disable require the existing recent admin reauth
  marker.
- `POST /api/v1/auth/login` does not require MFA in this phase.

## Secret Handling Model

No production encryption service exists in the current auth stack. Therefore the
Phase 3E TOTP path is a scaffold:

- Enrollment start returns the TOTP secret once, in the start response.
- Later responses never return the raw TOTP secret.
- Tests use `WOLFYSTOCK_MFA_TEST_SECRET` and a `test-only:` storage reference so
  deterministic TOTP verification can be covered without real credentials.
- Without the test-only secret path, generated secrets are stored as
  `placeholder-sha256:` references and are not recoverable for production TOTP
  verification.
- Production-ready MFA still requires an approved secret encryption or external
  secret storage design before login enforcement can be enabled.

Implementation note, Security Phase 3F:

- Recovery-code issuance and verification now use `mfa_recovery_codes_hash` as a
  versioned JSON envelope.
- The envelope stores only salted password-hash entries plus `generated_at`,
  per-code `used_at`, and per-set `replaced_at` metadata.
- Plaintext recovery codes are returned only by generation/rotation responses
  and are never persisted.
- Recovery-code verification consumes one active code exactly once and then
  returns only status plus remaining count.
- Recovery-code generation and rotation require the existing recent admin reauth
  marker. Login MFA enforcement remains disabled.

## Explicitly Not Changed

- No login MFA enforcement.
- No RBAC route migration.
- No Options, Data Pipeline, cost ledger, quota, provider runtime, MarketCache,
  scanner, backtest, portfolio, notification, DuckDB, or broker behavior.
- No real secrets, tokens, raw session IDs, or provider credentials are logged or
  returned by the new MFA verification/disable responses.

## Remaining Blockers

- Approve and implement production secret encryption/storage for TOTP secrets.
- Decide the future login/session contract for MFA-required and recovery-code
  fallback flows.
- Enable admin MFA enforcement only after the storage/encryption model and
  rollout/rollback plan are production-ready.
