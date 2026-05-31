# WolfyStock Operations Runbook

This is a lightweight operator runbook skeleton. It links to existing runbooks
and checklists instead of duplicating detailed command sequences.

## Scope

Use this for local/operator triage, release review preparation, provider/data
incidents, evidence collection, and safe rollback planning.

This runbook does not approve public launch, live provider wiring, broker/order
paths, DuckDB productionization, or protected-domain semantic changes.

## Operator Start Points

- [Docs Index](../DOCS_INDEX.md)
- [System Handbook](../WOLFYSTOCK_SYSTEM_HANDBOOK.md)
- [Audit Index](../audits/README.md)
- [Public Launch Readiness Master](../audits/public-launch-readiness-master.md)
- [Public Launch Gap Register](../audits/public-launch-gap-register.md)
- [Deployment readiness checklist](../audits/deployment-readiness-checklist.md)

## Local Runtime Checks

Backend:

```bash
source .venv/bin/activate
python3 -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Detailed local backend steps:

- [Backend Local Runbook](./backend-local-runbook.md)

Frontend:

```bash
cd apps/dsa-web
npm run lint
npm run build
```

Docs-only validation:

```bash
git diff --check -- <changed-doc-files>
bash scripts/release_secret_scan.sh
git status --short --branch
```

Full local backend gate when appropriate:

```bash
./scripts/ci_gate.sh
```

## Incident Triage

| Incident type | Start with | Do not do first |
| --- | --- | --- |
| Provider timeout, stale data, missing fields | [Provider Data Incident Runbook](../audits/provider-data-incident-runbook.md) | Do not reorder providers, hide stale labels, or change MarketCache TTL/SWR |
| Launch/release readiness | [Audit Index](../audits/README.md), [Deployment readiness checklist](../audits/deployment-readiness-checklist.md) | Do not infer GO from a single passing local check |
| Rollback decision | [Release Rollback Runbook](../audits/release-rollback-runbook.md) | Do not run destructive DB or git commands without explicit approval |
| Operator evidence | [Operator Evidence Real Runbook](../audits/operator-evidence-real-runbook.md) | Do not paste raw secrets, raw payloads, or private production data into repo docs |
| Admin/security/RBAC | [Auth/RBAC release security guide](../audits/auth-rbac-release-security-guide.md) | Do not weaken auth/session/capability behavior as a workaround |
| DuckDB diagnostics | [DuckDB Operator Smoke Guide](./duckdb-operator-smoke-guide.md) | Do not commit generated DuckDB/WAL/Parquet artifacts |
| Parallel AI work | [Parallel Codex Operator Playbook](./parallel-codex-playbook.md) | Do not stage, reset, clean, or format unrelated work |

## Provider/Data Incident Skeleton

1. Identify route, provider category, market, and affected user/operator
   surface.
2. Check whether output is live, stale, fallback, cache-only, fixture,
   synthetic, or unavailable.
3. Confirm freshness/as-of/source labels remain visible.
4. Capture sanitized reason buckets, not raw payloads or URLs.
5. Prefer cache-only or reduced outbound pressure when allowed by the route.
6. Escalate only with an explicit task before changing provider order,
   fallback depth, retry caps, timeouts, MarketCache TTL/SWR, or data labels.

## Release Review Skeleton

1. Read [Public Launch Readiness Master](../audits/public-launch-readiness-master.md).
2. Read [Public Launch Gap Register](../audits/public-launch-gap-register.md).
3. Confirm current launch verdict and blocker list.
4. Run only the validation appropriate to the release candidate and task scope.
5. Attach sanitized operator evidence where required.
6. Confirm `scripts/release_secret_scan.sh` and final git status.
7. Use [Release Rollback Runbook](../audits/release-rollback-runbook.md) before
   tagging/deploying.

## Evidence Handling

Use:

- [Operator Evidence Real Runbook](../audits/operator-evidence-real-runbook.md)
- [Operator Evidence Dry-Run Handoff](../audits/operator-evidence-dry-run-handoff.md)
- [Operator Evidence Redaction Checklist](../audits/operator-evidence-redaction-checklist.md)
- [Evidence artifact sanitizer guide](../audits/evidence-artifact-sanitizer-guide.md)
- [Artifact Cleanup Policy](./ARTIFACT_CLEANUP_POLICY.md)

Never include:

- API keys, tokens, cookies, webhook URLs, passwords, password hashes, private
  keys, session IDs, raw `.env` values, raw provider payloads, raw prompts, raw
  LLM responses, production DB contents, or stack traces containing sensitive
  data.

Artifact handling rules:

- treat Playwright outputs, screenshot captures, audit bundles, `reports/`,
  `artifacts/`, and `backtest_outputs/` as generated local artifacts unless the
  task explicitly asks for a tracked doc;
- keep tracked fixtures/examples separate from generated evidence;
- do not run broad `rm -rf` cleanup on storage paths;
- clean generated artifacts only after the related final report is accepted;
- never delete active worktree artifacts while Codex is still running.

## Rollback Skeleton

For code/docs commits:

```bash
git revert <commit>
```

For runtime/deployment rollback, follow the current release rollback runbook and
operator-approved deployment procedure. Do not invent ad hoc rollback commands
for databases, production storage, or remote infrastructure inside a docs task.

## Open Runbook Gaps

These areas need fuller future runbooks before production-scale operation:

- multi-instance WS2/API-worker deployment and SSE/polling decision evidence;
- live provider entitlement/freshness acceptance by route;
- quota and provider circuit enforcement pilots;
- real PostgreSQL restore/PITR drill;
- portfolio/backtest owner-isolation and export acceptance;
- Options live provider staged evidence;
- role-management and RBAC coarse-fallback removal operations.
