# Security Phase 3E Admin MFA Backend Foundation

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

Recovery code hashing is represented by the storage placeholder
`mfa_recovery_codes_hash`, but recovery code issuance and verification are not
implemented in this phase.

## Explicitly Not Changed

- No login MFA enforcement.
- No RBAC route migration.
- No Options, Data Pipeline, cost ledger, quota, provider runtime, MarketCache,
  scanner, backtest, portfolio, notification, DuckDB, or broker behavior.
- No real secrets, tokens, raw session IDs, or provider credentials are logged or
  returned by the new MFA verification/disable responses.

## Remaining Blockers

- Approve and implement production secret encryption/storage for TOTP secrets.
- Add recovery code generation, hashing, display-once behavior, and verification.
- Decide the future login/session contract for MFA-required state.
- Enable admin MFA enforcement only after the storage/encryption model and
  rollout/rollback plan are production-ready.
