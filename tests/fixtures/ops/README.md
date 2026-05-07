# Ops Fixtures

Files in this directory are synthetic ops-readiness fixtures for dry-run
validation. They do not prove that a real backup, restore, or PITR execution
occurred.

Marker files here only stand in for artifact presence during tests or local
preflight. Accepted real restore evidence must come from separate operator
evidence, not from these fixtures.

No file here should contain real secrets, DSNs, tokens, cookies, API keys,
provider credentials, or production data.

## Files

- `backup_restore_preflight_metadata.json`: synthetic metadata contract for
  `scripts/backup_restore_drill_check.sh`.
- `backup_restore_preflight_artifact.marker`: placeholder artifact-presence
  marker referenced by the synthetic metadata.
- `backup_restore_preflight_wal_archive.marker`: placeholder WAL-archive
  marker referenced by the synthetic metadata.
