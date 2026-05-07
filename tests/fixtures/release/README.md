# Release Fixtures

Files in this directory are synthetic examples for release/evidence tooling.
They are not production evidence by themselves.

If a file name says `accepted` or `ready`, treat it as an example of an
accepted/ready payload shape unless an operator supplies corresponding
sanitized evidence from a real review or run.

No file here should contain real secrets, DSNs, tokens, cookies, API keys,
provider credentials, or production data.

## Files

- `launch_acceptance_evidence.accepted.json`: synthetic all-categories-accepted
  example for `scripts/launch_acceptance_evidence.py`.
- `launch_acceptance_evidence.missing.json`: synthetic missing-evidence example
  for `scripts/launch_acceptance_evidence.py`.
- `production_config_readiness.ready.json`: synthetic ready-state config
  contract for `scripts/production_config_readiness.py`.
- `production_config_readiness.missing.json`: synthetic missing-config contract
  for `scripts/production_config_readiness.py`.
