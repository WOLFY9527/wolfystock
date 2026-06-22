# Docs Source-of-Truth Prune Register

Task ID: T-1472
Task title: Docs source-of-truth prune audit
Mode: WORKTREE-WORKER docs-only audit/register
Date: 2026-06-12

Status: prune audit register only. No Markdown files were deleted, moved,
renamed, regenerated, or edited by this register.

## Executive Summary

The safe answer to "why were the old Markdown files not deleted?" is that many
old-looking files still carry one of five roles: current source of truth,
generated navigation output, active launch/protected-domain evidence, historical
provenance, or unresolved owner-decision material. Deletion is unsafe until a
future task proves references, current authority, protected evidence role, and
owner intent for each exact path.

Current survey baselines:

| Count | Source | Meaning |
| ---: | --- | --- |
| 356 | `git ls-files '*.md'` | Tracked Markdown files in this worktree. |
| 241 | coarse lane count | Tracked Markdown in active/current/support lanes after excluding generated, mirrors, archive lanes, and active Codex task reports. |
| 55 | coarse lane count | Tracked Markdown already in archive/provenance lanes. |
| 54 | coarse lane count | Active `docs/codex/audits/*.md` task-evidence reports. |
| 6 | coarse lane count | Generated output plus AI-governance mirrors: `docs/AI_PROJECT_MANUAL.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, and `.github/instructions/*.instructions.md`. |
| 427 | `docs/AI_PROJECT_MANUAL_SOURCES.json` | Manual-generator discovery count after its own pruned-directory rules; this is generator context, not the tracked inventory count. |
| 284 | `docs/AI_PROJECT_MANUAL_SOURCES.json` | Candidate Markdown after generator exclusion policy. |
| 53 | `docs/AI_PROJECT_MANUAL_SOURCES.json` | Curated source files included in the generated AI manual. |

High-signal findings:

- Never delete current authority, current domain entry points, AI governance,
  Codex guard docs, launch/operator evidence, or protected-domain contracts
  without explicit owner approval and replacement proof.
- `docs/AI_PROJECT_MANUAL.md` is generated and do-not-edit; original Markdown
  files remain source material and must not be deleted just because the manual
  summarizes them.
- No high-confidence immediate delete candidate exists in the current tracked
  Markdown inventory. T-1247's prior candidate,
  `apps/dsa-web/src/i18n/canonical-i18n-migration-notes.md`, is absent now.
- Archive and consolidation candidates exist, but the safe default is archive
  after reference updates, not deletion.
- Public launch remains NO-GO. Any file used as launch, operator, RBAC, quota,
  provider, DB, broker, WS2, backtest, portfolio, notification, or no-advice
  evidence requires product-owner decision before removal.

## Reference Proof Method

Future prune tasks should use all of these checks before moving or deleting any
Markdown file:

1. Source-map membership:
   - Check `docs/AI_PROJECT_MANUAL_SOURCES.json` `includedSources[].path`.
   - Check `sections[].sources[]`.
   - If a file is in either set, classify it as `keep as source of truth` for
     the generated manual until the generator allowlist and manual are updated.
2. Static reference checks:
   - Search both full path and basename with `rg`.
   - Include `AGENTS.md`, `README.md`, `docs/DOCS_INDEX.md`,
     `docs/ARCHIVE_INDEX.md`, `docs/audits/README.md`, `.github/**`,
     `scripts/**`, `tests/**`, and source files.
   - If a file is referenced by current code, scripts, tests, active indexes, or
     runtime/admin status data, do not delete it in the same pass.
3. Current authority checks:
   - Prefer `AGENTS.md`, `docs/DOCS_INDEX.md`,
     `docs/architecture/file-governance-taxonomy.md`, current domain indexes,
     current source/tests/scripts, and active runbooks over old reports.
   - Archive docs are provenance only unless an active doc explicitly promotes
     them for a specific question.
4. Protected evidence checks:
   - Treat launch, security/RBAC/MFA, provider/quota/cost, DB/WS2/deployment,
     broker, backtest, portfolio, notification, data-quality, no-advice, and
     Codex protected-domain docs as owner-decision material.
   - If a candidate appears in launch or protected-domain evidence, stop and
     record it as `stale/conflicting doc needing owner decision`.
5. Generated/mirror checks:
   - Generated outputs and mirrors are not source of truth, but may still be
     required compatibility surfaces. Replace by generator or mirroring process,
     not by hand deletion.

Commands used for this audit baseline:

```bash
git ls-files '*.md' | wc -l
git ls-files '*.md' | awk 'BEGIN{tracked=0} {tracked++; if ($0 ~ /(^|\/)archive\//) archive++; else if ($0 ~ /^docs\/codex\/audits\//) codex_audits++; else if ($0 == "docs/AI_PROJECT_MANUAL.md") generated++; else if ($0 == "CLAUDE.md" || $0 == ".github/copilot-instructions.md" || $0 ~ /^\.github\/instructions\//) mirrors++; else active++} END{printf "tracked=%d\nactive_or_current_lane=%d\ngenerated=%d\nmirrors=%d\narchive_lane=%d\ncodex_task_audit_active_lane=%d\n", tracked, active, generated, mirrors, archive, codex_audits}'
jq '{discovery, includedCount: (.includedSources|length), sectionCount: (.sections|length), generator, outputs}' docs/AI_PROJECT_MANUAL_SOURCES.json
rg -n "markdown-inventory\.md|markdown-consolidation-plan\.md|final-pre-push-audit\.md|options-lab-phase0-design\.md|small-private-beta-release-checklist\.md|T-1247-docs-retention-cleanup-audit\.md|WOLFYSTOCK_CODEX_EXECUTION_POLICY\.md|DESIGN\.md" .
```

## Classification Register

### Keep As Source Of Truth

These files or file families are current source-of-truth lanes. They should not
be deleted unless a future owner-approved task first creates a replacement,
updates references, and proves the replacement.

| Area | Keep paths | Why |
| --- | --- | --- |
| AI collaboration governance | `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md`, `.claude/skills/**` | `AGENTS.md` is the repository AI-collaboration source of truth; the others are compatibility or mirrored agent assets. |
| Repository entry points | `README.md`, `docs/DOCS_INDEX.md`, `docs/ARCHIVE_INDEX.md`, `docs/CHANGELOG.md`, `docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`, `docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md`, `docs/architecture/file-governance-taxonomy.md` | Current navigation, archive policy, system overview, AI maintenance, and docs governance. |
| Generated-manual curated sources | The 53 paths in `docs/AI_PROJECT_MANUAL_SOURCES.json` `includedSources[]` | These feed the generated AI manual. Delete only after updating `scripts/build_ai_project_manual.py` and regenerating. |
| Codex process and protected-domain guardrails | `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`, `docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`, `docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`, `docs/codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md`, `docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`, `docs/codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md`, `docs/codex/WOLFYSTOCK_BACKTEST_UNIVERSE_RULES.md`, `docs/codex/NO_ADVICE_REGRESSION_GUARDS.md` | Current task rules, validation, final-report contract, and protected-domain stop rules. |
| Launch and operator evidence | `docs/audits/README.md`, `docs/audits/public-launch-readiness-master.md`, `docs/audits/public-launch-gap-register.md`, `docs/audits/public-launch-blocker-burndown.md`, `docs/audits/deployment-readiness-checklist.md`, `docs/audits/launch-acceptance-evidence-pack.md`, `docs/audits/incident-response-audit-evidence-pack.md`, `docs/audits/known-test-warnings-register.md`, `docs/audits/operator-evidence-*.md`, `docs/audits/evidence-artifact-sanitizer-guide.md`, `docs/audits/release-*.md`, `docs/audits/staging-integration-smoke-guide.md` | Current NO-GO, blocker, checklist, redaction, rollback, and operator evidence roles. These do not approve launch by themselves. |
| Domain indexes | `docs/audits/index-security-rbac-mfa.md`, `docs/audits/index-db-ws2-deployment.md`, `docs/audits/index-cost-quota-observability.md`, `docs/audits/index-provider-data-options.md` | Current index lanes for protected domains and launch blockers. |
| Current frontend/design authority | `docs/frontend/README.md`, `docs/frontend/visual-system.md`, `docs/frontend/validation-playbook.md`, `docs/frontend/WOLFYSTOCK_FRONTEND_NOISE_BUDGET.md`, `docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md`, `docs/frontend/WOLFYSTOCK_ADMIN_MAINTENANCE_OS.md`, `docs/design/README.md`, `docs/design/reference/wolfystock-reflect-linear-home-mockup.png` | Current UI/design source of truth and browser-evidence rules. |
| Provider/data/options | `docs/provider-data/README.md`, `docs/audits/provider-data-freshness-reliability-guide.md`, `docs/audits/provider-data-incident-runbook.md`, `docs/audits/market-data-provider-upgrade-decision-matrix.md`, `docs/audits/options-provider-adapter-contract.md`, `docs/options/README.md`, `docs/data-reliability/**` | Provider order/fallback/freshness, source-confidence, data-quality disclosure, and Options live-vs-fixture boundaries. |
| Security/RBAC/MFA | `docs/audits/index-security-rbac-mfa.md`, `docs/audits/auth-rbac-release-security-guide.md`, `docs/audits/admin-rbac-*.md`, `docs/audits/admin-role-*.md`, `docs/audits/production-security-hardening-audit.md`, `docs/audits/security-*.md` | Auth, RBAC, MFA, role governance, and security evidence. |
| DB/WS2/deployment | `docs/audits/index-db-ws2-deployment.md`, `docs/audits/db-*.md`, `docs/architecture/database-*.md`, `docs/architecture/postgresql-*.md`, `docs/operations/queue-ws2-metrics-production-readiness.md`, `docs/operations/background-job-queue-boundary.md`, `docs/audits/ws2-*.md` | DB source-of-truth, restore/PITR, retention, WS2/process-local limits, and deployment evidence. |
| Broker/backtest/portfolio/notification | `docs/audits/broker-order-trade-redaction-release-evidence-checklist.md`, `docs/backtest/**`, `docs/backtest-system.md`, `docs/codex/WOLFYSTOCK_BACKTEST_UNIVERSE_RULES.md`, `docs/portfolio/**`, `docs/architecture/phase-f/**`, `docs/alerts/**`, `docs/bot-command*.md`, `docs/bot/**` | Broker redaction, backtest v1 semantics, portfolio accounting provenance, alert dry-run/no-send, and bot/operator configuration. |

### Generated Or Do-Not-Edit

| Path | Classification | Handling |
| --- | --- | --- |
| `docs/AI_PROJECT_MANUAL.md` | Generated manual | Do not edit directly. Update source docs or `scripts/build_ai_project_manual.py`, then regenerate if explicitly scoped. |
| `docs/AI_PROJECT_MANUAL_SOURCES.json` | Generated manifest | Do not hand-edit. It records generator outputs, hashes, source metadata, and discovery policy. |
| `CLAUDE.md` | Compatibility shim | Keep as symlink/mirror to `AGENTS.md`; do not treat as independent source of truth. |
| `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md` | AI-governance mirrors/layers | Keep aligned with `AGENTS.md`; conflicts resolve to `AGENTS.md`. |
| Local/generated artifact lanes such as `.codex/**`, `.codex-artifacts/**`, `reports/**`, `test-results/**`, `playwright-report/**`, `artifacts/**` | Local/generated evidence | Not repository authority; do not promote into tracked docs without explicit task scope. |

### Merge Or Consolidate Candidates

These are candidates for future consolidation. None are deletion approvals.

| Cluster | Candidate paths | Preferred target |
| --- | --- | --- |
| Codex prompt authoring | `docs/codex/WOLFYSTOCK_CODEX_COMPACT_PROMPT_PROTOCOL.md`, `docs/codex/WOLFYSTOCK_CODEX_MINIMAL_PROMPT_PROTOCOL.md`, `docs/codex/WOLFYSTOCK_CODEX_TASK_TEMPLATES.md`, `docs/codex/WOLFYSTOCK_CODEX_COMPACT_TASK_EXAMPLES.md` | One prompt-authoring guide linked from `docs/codex/README.md`. |
| Codex final report protocol | `docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`, `docs/codex/WOLFYSTOCK_CODEX_COMPACT_FINAL_REPORT_PROTOCOL.md` | Keep the full template canonical; fold compact guidance into it or link as appendix. |
| Codex execution summary | `docs/codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md`, `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`, `docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md` | Keep standard guard/runtime canonical; execution policy remains a compact summary only. |
| Admin data/governance | `docs/audits/admin-data-*.md`, `docs/audits/admin-user-*.md`, `docs/audits/admin-role-management-ui-design.md` | `docs/admin-ops/README.md` plus security/admin domain indexes. |
| Cost/quota/LLM observability | `docs/audits/cost-*.md`, `docs/audits/duplicate-cost-*.md`, `docs/audits/llm-*.md`, `docs/audits/quota-cost-notification-release-guide.md` | `docs/audits/index-cost-quota-observability.md`. |
| DB/WS2/deployment | `docs/audits/db-*.md`, `docs/audits/ws2-*.md`, deployment readiness docs | `docs/audits/index-db-ws2-deployment.md`, preserving launch master and gap register. |
| Provider/data/options | Provider runbooks, source candidate worksheets, Options phase/design docs | `docs/audits/index-provider-data-options.md`, `docs/provider-data/README.md`, and `docs/options/README.md`. |
| Markdown retention governance | `docs/audits/archive/markdown-inventory.md`, `docs/audits/archive/markdown-consolidation-plan.md`, `docs/codex/audits/archive/2026-06/T-1247-docs-retention-cleanup-audit.md`, this register | This register plus `docs/ARCHIVE_INDEX.md` and domain indexes after references are updated. |
| Language/version duplicates | `docs/*_EN.md`, `docs/*_CHT.md`, `docs/full-guide*.md`, `docs/README_EN.md`, `docs/README_CHT.md`, `docs/INDEX_EN.md` | Bilingual/public-doc policy decision. Do not remove one language without owner decision. |

### Archive Candidates

Archive candidates retain historical value or provenance. They should be moved
only in a future task that updates indexes and references.

| Path or group | Why archive, not delete |
| --- | --- |
| `DESIGN.md` | Legacy/imported design asset. Current UI authority lives under `docs/frontend/` and `docs/design/README.md`, but `DESIGN.md` is still referenced as reference-only material. |
| Older `docs/codex/audits/T-*.md`, `WFE-*`, `WRD-*`, and `wrd-goal-*.md` reports | Point-in-time task evidence. Archive after task chains close and stable docs capture decisions. |
| `docs/audits/archive/**` | Already archive/provenance. Keep indexed; do not use as current authority. |
| `docs/codex/audits/archive/**` | Historical Codex task provenance. Keep indexed until cold-retention policy is approved. |
| `docs/frontend/archive/**`, `docs/audits/archive/frontend/**`, `docs/qa/archive/**` | Historical UI/QA evidence. Current frontend authority lives in `docs/frontend/`. |
| `docs/architecture/archive/**` | Historical architecture, multi-user foundation, and Phase F evidence. Some files still explain protected portfolio/DB decisions. |
| `docs/audits/*goal-progress.md`, `docs/codex/goals/*.md` | Task or goal progress logs. Archive only after goal closure and status capture. |

### Delete Candidate Only After Reference Proof

No current high-confidence immediate delete candidate was found.

| Path or group | Current decision | Why not delete now |
| --- | --- | --- |
| `apps/dsa-web/src/i18n/canonical-i18n-migration-notes.md` | No-op for T-1472 | This was T-1247's only first-batch delete candidate, but it is absent from the current tracked Markdown inventory. |
| `docs/audits/archive/markdown-inventory.md` | Delete candidate only after reference proof | Still referenced by `docs/ARCHIVE_INDEX.md`, active domain indexes, and historical docs. |
| `docs/audits/archive/markdown-consolidation-plan.md` | Delete candidate only after reference proof | Still referenced by active domain indexes and `docs/audits/public-launch-readiness-master.md`. |
| `docs/audits/archive/final-pre-push-audit.md` | Delete candidate only after reference proof | Still referenced by `docs/ARCHIVE_INDEX.md`, launch docs, warnings, and archive notes. |

Pre-delete checklist for any future candidate:

```bash
rg -n '<full path>|<basename>|<title>' .
git ls-files '*.md' | rg '<basename>'
git diff --check -- <changed-doc-files>
PYTHONDONTWRITEBYTECODE=1 PYTHON_BIN="/Users/yehengli/daily_stock_analysis/.venv/bin/python" ./scripts/release_secret_scan.sh --base-ref origin/main
```

If the file appears in active launch/protected-domain evidence, stop and move
it to owner decision instead of deleting.

### Stale Or Conflicting Docs Needing Owner Decision

| Path or group | Decision needed |
| --- | --- |
| `docs/audits/options-lab-phase0-design.md` | Marked superseded by later Options/provider docs, but still referenced from `docs/options/README.md`, `docs/DOCS_INDEX.md`, and `docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`. Owner must decide whether to keep as historical baseline or consolidate references. |
| `docs/release/small-private-beta-release-checklist.md` | Referenced by `src/services/admin_ops_status_service.py`; not safe to archive/delete as unreferenced. Owner must decide whether this remains active release evidence or should move into private-beta readiness docs. |
| Partial/deferred protected-domain plans | Many admin/security/DB/WS2/cost/provider docs are partial or deferred. Owner must decide whether they are active plans, archived designs, or superseded by domain indexes. |
| Options source candidate worksheets | `docs/audits/options-*-source-candidate-evidence.md` may have low static reference counts but can carry external-provider onboarding evidence. Owner decision required. |
| Bilingual/public docs | Public `*_EN.md`, `*_CHT.md`, broad guides, and FAQ/docs indexes need bilingual/public-doc policy before pruning. |
| Bot/external integration docs | Bot config docs and `docs/openclaw-skill-integration.md` may be externally depended on. Static repo references are not enough to prove deletion safety. |

## Source-Map Membership Snapshot

The generated manual currently includes 53 curated source files. These are the
manual source set and should be treated as keep-required until the generator is
explicitly updated:

```text
AGENTS.md
README.md
docs/ARCHIVE_INDEX.md
docs/DEPLOY.md
docs/DOCS_INDEX.md
docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md
docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md
docs/alerts/README.md
docs/architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md
docs/architecture/backend-frontend-modular-maintenance-handbook.md
docs/architecture/file-governance-taxonomy.md
docs/audits/README.md
docs/audits/admin-rbac-r5-coarse-fallback-removal-plan.md
docs/audits/auth-rbac-release-security-guide.md
docs/audits/backtest-portfolio-public-safety-audit.md
docs/audits/data-pipeline-r2-progressive-enrichment.md
docs/audits/data-quality-user-disclosure-policy.md
docs/audits/deployment-readiness-checklist.md
docs/audits/index-cost-quota-observability.md
docs/audits/index-provider-data-options.md
docs/audits/index-security-rbac-mfa.md
docs/audits/launch-acceptance-evidence-pack.md
docs/audits/options-provider-adapter-contract.md
docs/audits/private-beta-readiness.md
docs/audits/public-launch-gap-register.md
docs/audits/public-launch-readiness-master.md
docs/audits/quota-reserve-release-operator-evidence-checklist.md
docs/audits/security-mfa-secret-storage-hardening-plan.md
docs/audits/trading-no-advice-product-policy.md
docs/audits/ws2-multi-instance-smoke-test-design.md
docs/audits/ws2-multi-user-runtime-cost-control-design.md
docs/backtest-system.md
docs/backtest/README.md
docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md
docs/codex/WOLFYSTOCK_BACKTEST_UNIVERSE_RULES.md
docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md
docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md
docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md
docs/codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md
docs/codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md
docs/data-reliability/provider-source-confidence-contract.md
docs/frontend/README.md
docs/frontend/WOLFYSTOCK_ADMIN_MAINTENANCE_OS.md
docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md
docs/frontend/WOLFYSTOCK_FRONTEND_NOISE_BUDGET.md
docs/frontend/validation-playbook.md
docs/frontend/visual-system.md
docs/operations/background-job-queue-boundary.md
docs/operations/queue-ws2-metrics-production-readiness.md
docs/options/README.md
docs/portfolio/README.md
docs/provider-data/README.md
docs/quant-duckdb-engine.md
```

## Future Prune Order

1. Freeze deletion scope to exact paths, not folders.
2. Re-run full-path and basename reference checks.
3. For any generated-manual source, update `scripts/build_ai_project_manual.py`
   and regenerate in a generator-scoped task.
4. For any archive candidate, update `docs/ARCHIVE_INDEX.md` and active indexes
   before moving it.
5. For any protected-domain or launch evidence candidate, get product-owner
   approval and preserve NO-GO / evidence boundaries.
6. Delete only after no active references remain and the file is not current
   source, protected evidence, public docs, tracked fixture/docs, or operator
   runbook material.

## Validation Scope For This Register

Validation profile: `PROFILE_DOCS_POLICY`.

No script was added, so `PROFILE_DOCS_GENERATOR`, `py_compile`, and generator
determinism proof are not required for this task.

No pytest, frontend typecheck/build, or full `ci_gate` is required because this
register is docs-only and does not change runtime, frontend, tests, generator,
configuration, or existing governance assets.
