# Test Fixture Index

These fixtures are synthetic test inputs and example payloads. They are not
production evidence, not launch approval, and not proof that an operational
step ran in a real environment.

If a fixture says `accepted`, read that as "accepted example shape" unless an
operator separately supplies sanitized real evidence through the documented
review flow.

No fixture under `tests/fixtures/` should contain real secrets, DSNs, tokens,
cookies, API keys, provider credentials, or production data.

## Fixture groups

- `release/`: synthetic release-readiness and launch-evidence examples consumed
  by release/evidence helpers. See `tests/fixtures/release/README.md`.
- `ops/`: synthetic backup/restore/PITR preflight metadata and marker files
  used by ops-readiness checks. See `tests/fixtures/ops/README.md`.
- `options/`: options-lab sample payloads for tests, such as
  `options/tem_chain.json`. These are test fixtures only and have no release or
  production-evidence meaning.
