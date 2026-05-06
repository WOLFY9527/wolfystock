# Security Phase 3C/3D Password KDF Upgrade Plan

Date: 2026-05-06
Branch checked: `main`
Mode: docs-only security design / migration plan. No runtime auth behavior,
schema, migrations, tests, MFA, RBAC, Options Lab, cost ledger, quota, provider,
scanner, backtest, portfolio, notification, DuckDB, or broker/order behavior was
changed.

## 1. Executive summary

Security Phase 3A and 3B established a recent admin reauthentication source and
then required it for the narrow admin user-security write pilot. The remaining
production blockers include MFA and a password KDF upgrade. This document covers
only the password KDF upgrade plan.

Observed current password hashing posture:

- `src/auth.py` persists credentials as an unversioned `salt_b64:hash_b64`
  string.
- `_build_password_hash_entry()` derives the hash with PBKDF2-HMAC-SHA256 using
  `PBKDF2_ITERATIONS = 100_000` and a 32-byte random salt.
- `_verify_password_hash()` recomputes PBKDF2-HMAC-SHA256 and uses
  `hmac.compare_digest()` for comparison.
- `hash_password_for_storage()` is used for app users, normal user bootstrap,
  and password changes.
- The bootstrap admin compatibility path still writes `data/.admin_password_hash`
  and mirrors the same stored value into `app_users.password_hash`.
- `api/v1/endpoints/auth.py` verifies app users with
  `verify_password_hash_string()` and verifies the bootstrap admin through the
  file-backed helper.
- `AppUser.password_hash` is currently `String(255)` in SQLite ORM storage.

Why the KDF upgrade matters:

- The current PBKDF2 iteration count is low for a production public auth
  boundary in 2026.
- The current hash string has no algorithm or parameter marker, so future code
  cannot distinguish legacy and upgraded hashes without format inference.
- Password verification now gates login, admin reauth, settings unlock, and
  password change. A stronger KDF protects those routes if stored hashes are
  ever exposed.

Future implementation scope:

- Introduce versioned password hash strings.
- Verify current legacy hashes without breaking existing users.
- Opportunistically rehash legacy hashes after a successful login or admin
  reauth.
- Use the new format for all new password writes.
- Preserve bootstrap-admin compatibility until the legacy credential file is
  retired by a separate auth migration.

Implementation note, Security Phase 3D:

- KDF support has landed in the auth foundation.
- Argon2id and bcrypt were not available in the current project/runtime and were
  not added as new dependencies in this scoped pass.
- New password writes now use a versioned stronger PBKDF2-HMAC-SHA256 format
  with 600,000 iterations, a 32-byte random salt, and a 32-byte derived hash:
  `$wolfystock$kdf=v1$alg=pbkdf2-sha256$params=iter=600000,digest=sha256$salt=<base64url>$hash=<base64url>`.
- Existing unversioned `salt_b64:hash_b64` PBKDF2 hashes continue to verify as
  legacy hashes.
- Successful login, admin password unlock, auth settings current-password
  verification, and `POST /api/v1/auth/reauth` opportunistically rewrite
  recognized legacy hashes to the versioned format. Wrong passwords,
  unsupported hashes, disabled users, and rate-limited attempts do not upgrade.
- Bootstrap-admin file-backed compatibility is preserved: the legacy
  `data/.admin_password_hash` source remains authoritative during the
  transitional phase and the mirrored `app_users.password_hash` value is updated
  after a successful bootstrap-admin upgrade.
- Remaining work: MFA, password reset governance, optional forced reset for
  unsupported hashes, production calibration of Argon2id/bcrypt if those
  dependencies become approved, and any future password metadata fields such as
  `password_upgraded_at`.

Explicitly not changed in this task:

- No production login, reauth, settings-unlock, or change-password behavior.
- No MFA implementation.
- No RBAC route authorization changes.
- No schema migration, data backfill, or PostgreSQL cutover.
- No Options Lab, cost ledger, quota, admin cost, provider fallback,
  MarketCache, scanner, backtest, portfolio, notification, DuckDB, or
  broker/order behavior.

## 2. Target KDF strategy

Recommended primary strategy: Argon2id when dependency and deployment policy
allow it.

- Library: prefer `argon2-cffi` or the existing approved Python security
  dependency path if one is already present when implementation starts.
- Algorithm id: `argon2id`.
- Suggested starting parameters for production review:
  - memory cost: 64 MiB minimum, tuned against container limits;
  - time cost: 3 iterations;
  - parallelism: 1 or 2, tuned against deployed CPU limits;
  - salt length: 16 bytes or more;
  - hash length: 32 bytes.
- The implementation pass must benchmark the chosen parameters in the target
  deployment envelope before making them defaults.

Fallback strategy if Argon2id is not appropriate: bcrypt with a stronger cost
factor.

- Algorithm id: `bcrypt`.
- Suggested cost: start at 12 and tune upward only if local, CI, and production
  latency remain acceptable.
- Bcrypt should be a second choice because password length and library
  semantics need careful handling.

Compatibility-only strategy: current PBKDF2-HMAC-SHA256.

- Algorithm id for explicit legacy handling: `pbkdf2-sha256`.
- Existing unversioned strings should be parsed as `legacy-pbkdf2-sha256` only
  when they match the current `salt_b64:hash_b64` format.
- PBKDF2 should remain verify-only for existing rows unless a deployment cannot
  add Argon2id or bcrypt yet. If PBKDF2 must be used temporarily, increase the
  iteration count in a new versioned format and keep the current 100,000-count
  strings as legacy.

Target hash format:

```text
$wolfystock$kdf=v1$alg=<algorithm>$params=<parameter-string>$salt=<base64url>$hash=<base64url>
```

Notes:

- The `$wolfystock$kdf=v1` prefix gives the verifier a stable marker.
- `alg` identifies `argon2id`, `bcrypt`, or `pbkdf2-sha256`.
- `params` stores algorithm-specific metadata such as Argon2id
  `m=<memory>,t=<time>,p=<parallelism>`, bcrypt `cost=<cost>`, or PBKDF2
  `iter=<iterations>,digest=sha256`.
- `salt` and `hash` should use base64url without padding for formats that need
  explicit salt/hash fields.
- If the selected library already returns a safe PHC string, the stored value
  may instead be a wrapped PHC string, for example
  `$wolfystock$kdf=v1$phc=<base64url-encoded-phc>`. The implementation prompt
  below should choose the simpler parser with the fewest sharp edges.

Timestamp considerations:

- Existing `app_users.created_at` and `updated_at` can record that a row changed,
  but they cannot distinguish password creation from KDF upgrade.
- A future migration may add `password_created_at` and `password_upgraded_at`
  for auditability. Those fields are useful but not required for the first
  opportunistic rehash pass if the version marker is sufficient.
- The legacy `data/.admin_password_hash` file has no timestamp metadata.
  Bootstrap-admin upgrade audit should therefore come from the auth event log,
  not file metadata.

Compatibility requirements:

- Existing unversioned `salt_b64:hash_b64` strings must continue to verify.
- New writes must use the target versioned format.
- Unknown prefixes and malformed values must fail closed with the existing
  generic auth error surfaces.
- No API response, audit detail, or log line may include the stored hash string
  or submitted password.

## 3. Migration strategy

Recommended future login flow:

1. Resolve the account exactly as today.
2. Parse `password_hash` into one of:
   - current target format;
   - recognized legacy PBKDF2 format;
   - unsupported or malformed format.
3. Verify the submitted password using the parsed algorithm.
4. If verification fails, record the same generic failed-login path as today and
   do not write anything.
5. If verification succeeds and the hash is legacy or below current policy,
   compute a new target-format hash and update only that user's credential.
6. Continue session creation only after verification and any best-effort rehash
   decision has completed.

Unsupported hash fallback:

- Unsupported or malformed hashes should fail safely with the current generic
  invalid-login response.
- The user-facing recovery path should be a forced password reset or an
  administrator-operated reset workflow once that exists.
- Do not attempt to guess formats beyond the explicit legacy parser.

Bootstrap-admin handling:

- Bootstrap admin currently has dual storage:
  - legacy file: `data/.admin_password_hash`;
  - mirrored database row: `app_users.password_hash`.
- During coexistence, the bootstrap-admin password source of truth remains the
  file-backed helper.
- A future implementation should upgrade both locations together after a
  successful bootstrap-admin login, settings unlock, reauth, or password change.
- If the file write succeeds but the mirror write fails, preserve login
  compatibility and emit a sanitized warning/audit event without the hash value.
- If the mirror write succeeds but the file write fails, keep the legacy file as
  authoritative and report a sanitized operational error. Do not silently switch
  bootstrap-admin authority in this phase.

Auth-disabled / transitional local admin handling:

- When auth is disabled, `verify_password()` intentionally returns true for the
  transitional local path. The KDF upgrade must not turn auth-disabled local dev
  into mandatory password auth.
- Transitional users without an authenticated session should not receive
  opportunistic rehash behavior because there is no verified password event.
- The Phase 3B explicit bypass for unauthenticated transitional local admin
  should remain limited to that dev compatibility path.

Recent reauth interaction:

- `POST /api/v1/auth/reauth` verifies the current admin password and records a
  short-lived session-bound marker.
- After the KDF upgrade, reauth should call the same verifier as login.
- Successful reauth may opportunistically upgrade a legacy admin hash because it
  proves the current password. The response shape should remain unchanged except
  for any future non-sensitive audit correlation if explicitly added.
- Failed reauth must not upgrade and must keep generic error responses.

Password change and session revocation:

- New passwords should always be written in the target KDF format.
- Existing normal-user password changes already revoke all sessions for that
  user. The bootstrap-admin file-backed path currently changes the password but
  does not use the same app-user session revocation path in this endpoint.
- Future implementation should explicitly define and test session revocation
  after any password change:
  - normal users: revoke all app-user sessions as today;
  - bootstrap admin: revoke all bootstrap-admin app-user sessions and clear
    recent reauth markers, while preserving any required local recovery path.
- Opportunistic rehash after login or reauth should not revoke sessions because
  the password did not change.

Rollback caveats:

- Once a password is upgraded to a new KDF format, older application builds that
  know only `salt_b64:hash_b64` cannot verify it.
- A rollback that may run old code therefore needs one of:
  - deploy the parser before enabling writes to the new format;
  - keep a feature flag that can stop new-format writes while leaving
    verification support active;
  - require password reset for affected accounts after rollback.
- Do not store both old and new hashes for rollback. Dual hashes increase
  credential exposure blast radius.

## 4. Storage / schema considerations

Current storage:

- SQLite ORM: `AppUser.password_hash = Column(String(255))`.
- Legacy bootstrap file: `data/.admin_password_hash`.
- PostgreSQL Phase A design treats `app_users` as the durable identity table and
  keeps the bootstrap file as transitional compatibility.

Can the current field store versioned KDF strings?

- The current unversioned PBKDF2 string is short enough for `String(255)`.
- Bcrypt strings are also generally short enough for 255 characters.
- Argon2 PHC strings often fit under 255 characters with common parameters, but
  the margin is not generous once wrapped with custom metadata.
- Recommendation: before writing Argon2id hashes, either confirm the exact
  target encoded length is comfortably below 255 or widen `password_hash` to
  `Text` / an equivalent unbounded string in both SQLite and PostgreSQL.

Extra fields:

- The first implementation can rely on the versioned string alone.
- Future auditability can add:
  - `password_created_at`;
  - `password_upgraded_at`;
  - `password_kdf_algorithm`;
  - `password_reset_required`.
- Those fields are not required for compatibility if the hash string is
  self-describing.

SQLite and PostgreSQL compatibility:

- The verifier must be store-agnostic: it should accept the stored string from
  either SQLite or PostgreSQL without knowing the storage backend.
- Any column-width migration must be additive and compatible with the Phase A
  PostgreSQL baseline.
- No migration is implemented in this pass because the target algorithm and
  encoded length still need dependency and deployment confirmation.

## 5. Security controls

Verification controls:

- Continue constant-time comparison for PBKDF2 and any manual hash comparison.
- For Argon2id or bcrypt, use the library verifier rather than reimplementing
  comparison logic.
- Keep generic error messages for unknown users, wrong passwords, disabled
  users, unsupported hashes, and reauth failures.
- Preserve existing rate limiting for login, settings unlock, and reauth. The
  KDF upgrade must not bypass throttle buckets.

Exposure controls:

- Do not return `password_hash` or any KDF metadata in API responses.
- Do not log submitted passwords, stored hashes, session cookie values, raw
  session ids, tokens, API keys, provider credentials, broker credentials,
  private keys, webhook URLs, or `.env` values.
- Audit events may record event types such as `password_kdf_upgraded` or
  `password_reset_required`, but details must use account/user hashes and safe
  algorithm labels only. Never include salt, hash, or password length.
- Tests should use synthetic fixtures only and must assert that response and
  audit payloads do not expose password/hash/session/token/cookie material.

Operational controls:

- Rehash should be best-effort only after successful verification. If the
  rehash write fails, prefer a sanitized audit/operational warning and continue
  or fail according to the route's existing write guarantees. Do not leak the
  hash or password in the error.
- For admin accounts, consider an audit event on successful KDF upgrade because
  it changes credential storage posture.
- For normal users, a low-noise audit event can be recorded without exposing
  account existence to callers.

## 6. Future implementation test plan

Focused helper tests:

- legacy unversioned PBKDF2 hash verifies successfully.
- target-format Argon2id or bcrypt hash verifies successfully.
- malformed hash returns a safe failure.
- unknown version marker returns a safe failure.
- wrong password fails without upgrade.
- `needs_rehash()` returns true for legacy PBKDF2 and false for current target
  parameters.
- generated target-format hash never embeds plaintext password material.

Login and migration tests:

- successful login with legacy hash upgrades that account to the target format.
- successful login with current target hash does not rewrite the row.
- wrong password does not upgrade the row.
- unsupported hash fails with the generic invalid-login response and no row
  write.
- disabled-user login remains generic and does not upgrade.
- rate-limited login does not verify or upgrade.

Admin and bootstrap tests:

- bootstrap-admin legacy file verifies and upgrades both the file and mirrored
  app-user row when safe.
- bootstrap-admin mismatch between file and mirror preserves the file-backed
  authority and emits only sanitized diagnostics.
- auth-disabled transitional local admin behavior remains compatible and does
  not require a password.
- `POST /api/v1/auth/reauth` succeeds after an upgraded admin hash.
- failed reauth does not upgrade and does not reveal secrets.
- recent reauth markers remain session-bound and are cleared when sessions are
  revoked.

Password change / revocation tests:

- password change writes only target-format hashes.
- normal-user password change revokes all sessions and clears recent reauth
  markers.
- bootstrap-admin password change revokes bootstrap-admin sessions if that
  behavior is implemented in the same phase.
- old password fails after change; new password succeeds.

Exposure tests:

- no `password_hash`, stored hash string, submitted password, raw session id,
  `dsa_session`, cookie value, token, API key, secret, provider credential,
  broker credential, private key, webhook URL, or `.env` value appears in API
  responses, audit details, or logs.
- test fixtures use synthetic passwords and synthetic hashes only.

Suggested focused commands for the implementation pass:

```bash
python3 -m py_compile src/auth.py src/repositories/auth_repo.py api/v1/endpoints/auth.py
pytest tests/test_auth.py tests/test_auth_api.py tests/api/test_auth_security_hardening.py -q
```

## 7. Next Codex implementation prompt

```text
You are working on the WolfyStock project in
/Users/yehengli/daily_stock_analysis on branch main.

Goal:
Implement Security Phase 3C Password KDF Upgrade as the smallest compatible
auth-only pass.

Start with:
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -40
./scripts/task_preflight.sh || true
lsof -i :8000 -i :8001 -i :5173 -i :4173 -i :5174 -i :5175 -i :5176 -i :4177 || true

Safety:
- Stop if not on /Users/yehengli/daily_stock_analysis or not on main.
- Stop if target auth/security/docs/test files are dirty before your changes.
- Do not touch Options, cost ledger, quota, provider, scanner, backtest,
  portfolio, notification, DuckDB, broker/order, or WS2 runtime files.
- Do not implement MFA.
- Do not print, log, copy, or commit real passwords, password hashes, session
  ids, cookies, tokens, API keys, .env values, provider credentials, broker
  credentials, private keys, webhook URLs, or secrets.
- Do not use git add . or stage unrelated files.

Read first:
- docs/audits/security-password-kdf-upgrade-plan.md
- docs/audits/admin-rbac-final-qa-report.md
- docs/audits/admin-rbac-capability-model-design.md
- src/auth.py
- src/repositories/auth_repo.py
- api/v1/endpoints/auth.py
- tests/test_auth.py
- tests/test_auth_api.py
- tests/api/test_auth_security_hardening.py

Implement:
1. Add a small versioned password hash helper layer in src/auth.py.
2. Preserve verification of current unversioned PBKDF2-HMAC-SHA256
   salt_b64:hash_b64 strings.
3. Add target-format hashing using Argon2id if the dependency is already
   acceptable in the project; otherwise use bcrypt or a versioned stronger
   PBKDF2 fallback as documented, with explicit algorithm metadata.
4. Use target-format hashes for new password writes.
5. After successful login or admin reauth, opportunistically rehash recognized
   legacy hashes without changing response shape.
6. Never upgrade on wrong password, disabled user, unsupported hash, or
   rate-limited request.
7. Preserve bootstrap-admin file-backed compatibility and mirror behavior.
8. Preserve auth-disabled transitional local admin behavior.
9. Preserve generic auth errors, throttle interaction, no hash exposure, and
   session revocation behavior. If password-change revocation is widened for
   bootstrap-admin, add explicit tests.

Tests:
- Add focused helper tests for format detection, legacy verify, target verify,
  wrong password, unsupported hash, and needs-rehash behavior.
- Add focused API tests for successful legacy login upgrade, wrong password no
  upgrade, reauth after upgrade, and no sensitive exposure.
- Run:
  python3 -m py_compile src/auth.py src/repositories/auth_repo.py api/v1/endpoints/auth.py
  pytest tests/test_auth.py tests/test_auth_api.py tests/api/test_auth_security_hardening.py -q

Docs:
- Update docs/CHANGELOG.md only if clean and consistent with existing style.
- Update docs/audits/security-password-kdf-upgrade-plan.md with an
  implementation note only after tests pass.

Final report:
- commit hash/message if committed;
- changed files;
- KDF chosen and why;
- compatibility behavior;
- checks and results;
- ci_gate result or explanation if not run;
- ports inspected/used;
- confirmation no real secrets were printed or committed;
- final git status;
- rollback command.
```
