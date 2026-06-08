# T-1247 Docs retention cleanup audit

Task ID: T-1247
Task title: Docs retention cleanup audit
Mode: READ-ONLY-AUDIT with one task-authorized report artifact
Report path: `docs/codex/audits/T-1247-docs-retention-cleanup-audit.md`
Audit date: 2026-06-08

## Scope and method

This audit inspected tracked Markdown files in the current workspace and did not
delete, move, rename, or edit existing documentation.

Evidence commands used:

- `git status --short --branch`
- `git fetch origin`
- `git log --oneline -5`
- `git log --oneline --decorate origin/main..HEAD`
- `git diff --name-only`
- `git diff --cached --name-only`
- `git ls-files "*.md"`
- folder-count PowerShell inventories over tracked Markdown files
- `rg -n "T-[0-9]+|READ-ONLY-AUDIT|Allowed final diff|First safe execution task|provider-source-confidence|data-coverage|protected domains|frontend" docs AGENTS.md README.md`
- targeted `rg --fixed-strings` path-reference checks
- targeted `git log --follow --oneline -- <candidate_file>` checks

Pre-write state:

- cwd: `C:\Users\leeyi\worktrees\t1247-docs-retention-cleanup-audit`
- branch: `codex/t1247-docs-retention-cleanup-audit`
- initial branch status after fetch: `## codex/t1247-docs-retention-cleanup-audit...origin/main [behind 4]`
- local HEAD before report: `ae9c82bf67b5be3544f30a9c59439d97ae31434d`
- latest observed `origin/main`: `7b9e0961`
- staged files before report: none
- tracked dirty files before report: none

Important note: the standard `READ-ONLY-AUDIT` runtime rule normally says not to
create artifacts, commit, or push. This task prompt explicitly authorizes one
report artifact plus commit/push of that report only. This report follows the
more specific task authorization while keeping all existing docs unchanged.

## Executive verdict

WolfyStock does not have random Markdown clutter so much as several different
retention classes sharing active-looking paths. The main risk is deleting files
that are still prompt inputs, protected-domain contracts, or live follow-up task
definitions.

Safe cleanup should therefore happen in three waves:

1. Delete only truly unreferenced temporary Markdown notes first.
2. Move old Codex audit waves into a colder archive after active follow-up tasks
   close.
3. Consolidate overlapping domain design docs into existing indexes before any
   deletion of referenced historical reports.

The smallest safe first deletion batch is one file:

- `apps/dsa-web/src/i18n/canonical-i18n-migration-notes.md`

That file is a tracked, unreferenced, point-in-time migration note under app
source, not a current docs index, guardrail, contract, test fixture, or active
prompt input. It should still be deleted only in a separate execution task after
a final path/basename `rg` check.

No `docs/codex/**` guardrails, `docs/data-reliability/**` contracts,
`docs/frontend/**` current authority docs, launch/readiness runbooks, current
domain indexes, or T-1175/T-1176/T-1212/T-1213/T-1215 evidence should be
deleted in the next execution task.

## Markdown inventory summary by folder

Tracked Markdown count from `git ls-files "*.md"`: 334.

Top-level distribution:

| Area | Count | Primary classification |
| --- | ---: | --- |
| `docs/` | 312 | Mixed: current authority, active evidence, archive candidates, consolidation candidates |
| `.github/` | 7 | KEEP_REQUIRED |
| repo root | 5 | KEEP_REQUIRED except `DESIGN.md` is ARCHIVE_CANDIDATE |
| `.claude/` | 4 | KEEP_REQUIRED |
| `tests/` | 3 | KEEP_REQUIRED |
| `apps/` | 1 | DELETE_CANDIDATE |
| `scripts/` | 1 | KEEP_REQUIRED |
| `strategies/` | 1 | KEEP_REQUIRED |

`docs/` distribution:

| Folder | Count | Primary classification |
| --- | ---: | --- |
| `docs/audits/` | 95 | Mixed: KEEP_REQUIRED, CONSOLIDATE_CANDIDATE, ARCHIVE_CANDIDATE |
| `docs/codex/` | 81 | Mixed: KEEP_REQUIRED process docs, KEEP_ACTIVE_EVIDENCE audits |
| `docs/architecture/` | 32 | Mixed: KEEP_REQUIRED active architecture, ARCHIVE_CANDIDATE archive snapshots |
| `docs` root files | 32 | Mostly KEEP_REQUIRED public/system docs |
| `docs/operations/` | 14 | KEEP_REQUIRED |
| `docs/frontend/` | 12 | KEEP_REQUIRED active docs plus ARCHIVE_CANDIDATE historical evidence |
| `docs/backtest/` | 8 | KEEP_REQUIRED |
| `docs/data-reliability/` | 7 | KEEP_REQUIRED |
| `docs/qa/` | 4 | KEEP_REQUIRED current QA plus ARCHIVE_CANDIDATE point-in-time QA |
| `docs/bot/` | 3 | KEEP_REQUIRED |
| `docs/checks/` | 3 | KEEP_REQUIRED |
| `docs/options/` | 3 | KEEP_REQUIRED |
| `docs/alerts/` | 2 | KEEP_REQUIRED |
| `docs/design/` | 2 | KEEP_REQUIRED |
| `docs/market-overview/` | 2 | KEEP_REQUIRED |
| `docs/portfolio/` | 2 | KEEP_REQUIRED |
| `docs/product/` | 2 | KEEP_REQUIRED |
| `docs/admin-ops/` | 1 | KEEP_REQUIRED |
| `docs/ai-llm/` | 1 | KEEP_REQUIRED |
| `docs/backend/` | 1 | KEEP_REQUIRED |
| `docs/docker/` | 1 | KEEP_REQUIRED |
| `docs/liquidity/` | 1 | KEEP_REQUIRED |
| `docs/provider-data/` | 1 | KEEP_REQUIRED |
| `docs/rotation/` | 1 | KEEP_REQUIRED |
| `docs/scanner/` | 1 | KEEP_REQUIRED |
| `docs/examples/` | 0 | No tracked Markdown |

Primary classification counts, counted once per tracked Markdown file:

| Category | Count | Notes |
| --- | ---: | --- |
| KEEP_REQUIRED | 199 | Current guards, contracts, indexes, runbooks, public docs, repo templates, tracked skills |
| KEEP_ACTIVE_EVIDENCE | 32 | Recent task reports/progress docs that still define upcoming work or active goals |
| ARCHIVE_CANDIDATE | 73 | Already historical archives plus old Codex audit waves that should move to colder archive after closure |
| CONSOLIDATE_CANDIDATE | 22 | Overlapping domain designs, prompt protocols, launch/audit plans |
| REVIEW_MANUALLY | 7 | Unclear ownership or external dependency risk |
| DELETE_CANDIDATE | 1 | Unreferenced temporary Markdown note |
| Total | 334 | Matches tracked Markdown inventory |

## Top clutter sources

1. `docs/audits/` has 95 Markdown files. It contains current launch authority,
   active domain indexes, partially implemented designs, and already archived
   historical evidence in the same broad lane.
2. `docs/codex/audits/` has 62 report files in a flat folder. Recent reports
   define future tasks, while older waves are mostly point-in-time planning
   evidence.
3. `docs/architecture/` has 32 files, including current architecture docs,
   Postgres/storage plans, Phase F docs, and archived implementation snapshots.
4. Frontend history is split between `docs/frontend/archive/` and
   `docs/audits/archive/frontend/`. This is intentional today, but it creates
   two historical UI evidence lanes.
5. Codex process docs overlap across execution policy, compact prompt protocol,
   minimal prompt protocol, task templates, compact task examples, and compact
   final report protocol.
6. Admin, cost/quota, DB/WS2, provider/options, and security docs have multiple
   partial or deferred designs that need status consolidation before deletion.

## KEEP_REQUIRED

These docs are canonical or required operational references. Do not delete
without explicit owner approval and a replacement plan.

### Repository governance and agent assets

- `AGENTS.md`: repository AI collaboration source of truth.
- `CLAUDE.md`: compatibility shim that must point to `AGENTS.md`.
- `.github/copilot-instructions.md`
- `.github/instructions/backend.instructions.md`
- `.github/instructions/client.instructions.md`
- `.github/instructions/governance.instructions.md`
- `.github/ISSUE_TEMPLATE/*.md`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.claude/skills/README.md`
- `.claude/skills/analyze-issue/SKILL.md`
- `.claude/skills/analyze-pr/SKILL.md`
- `.claude/skills/fix-issue/SKILL.md`
- `README.md`: public repository entry point.
- `SKILL.md`: product/external skill integration document, not agent governance.

Rationale: `AGENTS.md` and `docs/architecture/file-governance-taxonomy.md`
explicitly define these as current governance or tracked collaboration assets.

### Documentation navigation and system entry points

- `docs/DOCS_INDEX.md`
- `docs/ARCHIVE_INDEX.md`
- `docs/CHANGELOG.md`
- `docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`
- `docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md`
- `docs/CONTRIBUTING.md`
- `docs/CONTRIBUTING_EN.md`
- `docs/DEPLOY.md`
- `docs/DEPLOY_EN.md`
- `docs/README_EN.md`
- `docs/README_CHT.md`
- `docs/INDEX_EN.md`
- `docs/FAQ.md`
- `docs/FAQ_EN.md`
- `docs/full-guide.md`
- `docs/full-guide_EN.md`
- `docs/LLM_CONFIG_GUIDE.md`
- `docs/LLM_CONFIG_GUIDE_EN.md`

Rationale: these are current navigation, onboarding, deployment, support, and
bilingual public docs. Deleting any one of them requires a bilingual-sync and
entrypoint review.

### Codex process and protected-domain docs

- `docs/codex/README.md`
- `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`
- `docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`
- `docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`
- `docs/codex/WOLFYSTOCK_BACKTEST_UNIVERSE_RULES.md`
- `docs/codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md`
- `docs/codex/WOLFYSTOCK_CODEX_MODEL_ROUTING.md`
- `docs/codex/WOLFYSTOCK_PROMPT_CONTEXT_INDEX.md`
- `docs/codex/WOLFYSTOCK_SHARED_MAIN_WORKTREE_PROTOCOL.md`
- `docs/codex/WOLFYSTOCK_FRONTEND_VALIDATION_COMMAND_TEMPLATES.md`
- `docs/codex/WOLFYSTOCK_OPTIONS_AUTHORITY_DIAGNOSTIC_PATTERN.md`
- prompt-authoring docs under `docs/codex/WOLFYSTOCK_CODEX_*PROMPT*`,
  `WOLFYSTOCK_CODEX_TASK_TEMPLATES.md`,
  `WOLFYSTOCK_CODEX_COMPACT_TASK_EXAMPLES.md`, and
  `WOLFYSTOCK_CODEX_COMPACT_FINAL_REPORT_PROTOCOL.md`

Rationale: current task prompts explicitly read the standard guard, runtime
rules, final-report template, and protected-domain docs. The prompt-authoring
docs overlap but are still current process inputs.

### Current frontend authority

- `docs/frontend/README.md`
- `docs/frontend/visual-system.md`
- `docs/frontend/validation-playbook.md`
- `docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md`
- `docs/frontend/WOLFYSTOCK_ADMIN_MAINTENANCE_OS.md`
- `docs/frontend/WOLFYSTOCK_FRONTEND_NOISE_BUDGET.md`
- `docs/design/README.md`
- `docs/design/wolfystock-market-provider-operations-dashboard.md`

Rationale: these define current Reflect-Linear source of truth, validation
rules, consumer data-quality copy, admin surface IA, and future provider
operations planning. Archived frontend evidence must not override them.

### Data, provider, source-confidence, and quality contracts

- `docs/data-reliability/README.md`
- `docs/data-reliability/provider-source-confidence-contract.md`
- `docs/data-reliability/data-coverage-matrix-v1.md`
- `docs/data-reliability/data-coverage-consumer-projection-examples.md`
- `docs/data-reliability/data-coverage-surface-fixtures.md`
- `docs/data-reliability/evidence-readiness-matrix.md`
- `docs/data-reliability/single-stock-actionability-observation-contract.md`
- `docs/provider-data/README.md`
- `docs/audits/provider-data-freshness-reliability-guide.md`
- `docs/audits/provider-data-incident-runbook.md`
- `docs/audits/data-quality-user-disclosure-policy.md`
- `docs/operations/provider-capability-metadata.md`
- `docs/operations/official-macro-cache-prewarm-runbook.md`

Rationale: current and future tasks cite these to preserve source-confidence,
authority, fallback, data coverage, cache-only diagnostics, and user disclosure
semantics.

### Domain authority lanes

- `docs/backend/README.md`
- `docs/architecture/README.md`
- `docs/architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md`
- `docs/architecture/file-governance-taxonomy.md`
- `docs/architecture/backend-frontend-modular-maintenance-handbook.md`
- `docs/architecture/database-component-map.md`
- `docs/architecture/database-maintenance-handbook.md`
- `docs/architecture/database-real-pg-bundle-playbook.md`
- `docs/architecture/database-troubleshooting-playbook.md`
- `docs/architecture/phase-f/decisions.md`
- `docs/architecture/phase-f/status.md`
- `docs/architecture/phase-f/runbook.md`
- `docs/backtest/README.md`
- `docs/backtest-system.md`
- `docs/backtest-system_EN.md`
- `docs/backtest-helper-maintenance.md`
- `docs/backtest-helper-maintenance_EN.md`
- `docs/backtest/*.md`
- `docs/portfolio/README.md`
- `docs/portfolio/portfolio-research-smoke-checklist.md`
- `docs/alerts/README.md`
- `docs/alerts/user-alert-dry-run-fixtures.md`
- `docs/options/README.md`
- `docs/liquidity/README.md`
- `docs/rotation/README.md`
- `docs/scanner/README.md`
- `docs/market-overview/README.md`
- `docs/market-overview/market-intelligence-smoke-checklist.md`
- `docs/admin-ops/README.md`
- `docs/ai-llm/README.md`
- `docs/product/*.md`
- `docs/checks/*.md`
- `docs/operations/*.md`
- `docs/bot/*.md`
- `docs/docker/zeabur-deployment.md`
- `scripts/README.md`
- `strategies/README.md`
- `tests/fixtures/**/*.md`

Rationale: these are current module, runbook, fixture, and domain entrypoint
docs. Some can be shortened later, but they should not be deleted as clutter.

### Current audit authority and runbooks

- `docs/audits/README.md`
- `docs/audits/public-launch-readiness-master.md`
- `docs/audits/public-launch-gap-register.md`
- `docs/audits/public-launch-blocker-burndown.md`
- `docs/audits/deployment-readiness-checklist.md`
- `docs/audits/launch-acceptance-evidence-pack.md`
- `docs/audits/incident-response-audit-evidence-pack.md`
- `docs/audits/known-test-warnings-register.md`
- `docs/audits/index-security-rbac-mfa.md`
- `docs/audits/index-db-ws2-deployment.md`
- `docs/audits/index-cost-quota-observability.md`
- `docs/audits/index-provider-data-options.md`
- `docs/audits/auth-rbac-release-security-guide.md`
- `docs/audits/admin-rbac-capability-model-design.md`
- `docs/audits/admin-rbac-r5-coarse-fallback-removal-plan.md`
- `docs/audits/admin-role-governance-plan.md`
- `docs/audits/production-security-hardening-audit.md`
- `docs/audits/security-mfa-secret-storage-hardening-plan.md`
- `docs/audits/security-password-kdf-upgrade-plan.md`
- `docs/audits/backtest-portfolio-public-safety-audit.md`
- `docs/audits/trading-no-advice-product-policy.md`
- `docs/audits/market-data-provider-upgrade-decision-matrix.md`
- `docs/audits/options-provider-adapter-contract.md`
- `docs/audits/options-lab-phase0-design.md`
- `docs/audits/backtest-quant-capability-audit.md`
- `docs/audits/db-production-readiness-index-retention-audit.md`
- `docs/audits/db-retention-backup-restore-drill-plan.md`
- `docs/audits/ws2-*.md`
- `docs/audits/cost-*.md`
- `docs/audits/llm-*.md`
- `docs/audits/operator-evidence-*.md`
- `docs/audits/release-*.md`
- `docs/audits/ci-*.md`
- `docs/audits/staging-integration-smoke-guide.md`

Rationale: `docs/audits/README.md` names these as current launch, domain,
operator, and safety evidence.

## KEEP_ACTIVE_EVIDENCE

These audit reports remain active because they directly define upcoming tasks,
current protected follow-up boundaries, or the public beta candidate goal.

| File or group | Task references | Why active |
| --- | --- | --- |
| `docs/codex/goals/T-1175_PROGRESS.md` | T-1175 | Active public beta candidate progress ledger; contains current checkpoints, score, validation, and allowed write families. |
| `docs/codex/audits/T-1176-system-wide-consolidation-audit.md` | T-1176, Batch A-E | Defines current system-wide cleanup batches and protected no-touch list. |
| `docs/codex/audits/T-1212-watchlist-research-workflow-audit.md` | T-1212 | Defines no-migration Watchlist workflow strip first slice and forbidden backend/storage domains. |
| `docs/codex/audits/T-1213-portfolio-risk-exposure-summary-audit.md` | T-1213 | Defines frontend-only Portfolio risk exposure summary first slice and protected accounting boundaries. |
| `docs/codex/audits/T-1215-scanner-watchlist-pipeline-audit.md` | T-1215, T-1215-M1 | Defines Scanner-to-Watchlist lineage projection first task and ranking/provider no-touch boundaries. |
| `docs/codex/audits/T-1080-market-liquidity-rotation-consumer-readiness-audit.md` | T-1080 | Still cited by consumer data-quality and market/liquidity/rotation follow-up context. |
| `docs/codex/audits/T-1086-options-gex-market-structure-placement-readiness-audit.md` | T-1086 | Defines Options market-structure placement and no-advice placement boundaries. |
| `docs/codex/audits/T-1087-portfolio-pricing-evidence-consumer-readiness-audit.md` | T-1087 | Still feeds Portfolio evidence/consumer-readiness copy decisions. |
| `docs/codex/audits/T-1077-single-stock-evidence-consumer-metadata-readiness-audit.md` and `T-1078-scanner-explainability-consumer-readiness-audit.md` | T-1077, T-1078 | Still referenced by current evidence/consumer metadata and scanner explainability decisions. |
| `docs/codex/audits/T-1045-*` through `T-1067-*` data-reliability/provider/backtest/options reports | T-1045 to T-1067 | These reports define the provider-source-confidence/data-reliability adoption chain and should stay until contracts are fully represented in stable docs. |
| `docs/codex/audits/T-987-*`, `T-989-*`, `T-990-*`, `T-992-*`, `T-995-*`, `WRD-008-*`, `wrd-goal-react-doctor-100-progress.md` | T-987 to T-995, WRD-008 | React Doctor, smoke, large-page, and bundle task chain. Keep until the frontend cleanup wave is closed and summarized elsewhere. |
| `docs/codex/audits/T-892-*`, `T-913-*`, `T-917-*`, `T-918-*`, `T-925-*`, `T-929-*`, `T-930-*`, `T-935-*`, `T-953-*`, `T-957-*`, `T-981-*` | T-892 to T-981 | Older but still chain-defining Research OS, scanner, options, source-provenance, and platform architecture context. Archive only after the current roadmap/index captures their decisions. |

## ARCHIVE_CANDIDATE

These should be archived or moved to colder historical retention rather than
deleted immediately.

| File or group | Recommended action | Rationale |
| --- | --- | --- |
| `DESIGN.md` | Move to a historical design archive after updating references in `docs/architecture/file-governance-taxonomy.md` and `docs/codex/WOLFYSTOCK_PROMPT_CONTEXT_INDEX.md`. | Root-level legacy imported Linear design asset; current frontend authority lives under `docs/frontend/` and `docs/design/README.md`. |
| Older `docs/codex/audits/T-*.md` waves before T-1176 | Move to `docs/archive/codex-audits/YYYY-MM/` or `docs/codex/audits/archive/YYYY-MM/` after active task chains close. | Useful task provenance but not ideal in the active prompt lane forever. |
| `docs/codex/audits/WFE-001-*`, `WFE-002-*`, `WRD-008-*`, `wrd-goal-react-doctor-100-progress.md` | Archive after Windows/frontend validation and React Doctor work are fully closed. | Tooling evidence remains useful, but should not live as current task evidence indefinitely. |
| `docs/frontend/archive/*.md` | Keep in archive, optionally external-retain later. | Already marked historical frontend evidence. Do not treat as active design authority. |
| `docs/audits/archive/**/*.md` | Keep in archive, optionally external-retain later after `docs/ARCHIVE_INDEX.md` is updated. | Already linked as historical evidence. Current policy says archive when provenance matters. |
| `docs/architecture/archive/**/*.md` | Keep in archive, optionally external-retain later. | Historical architecture and Phase F evidence. Some Phase F docs may still explain portfolio decisions. |
| `docs/qa/archive/*.md` | Keep in archive, optionally external-retain later. | Point-in-time QA evidence. |

## DELETE_CANDIDATE

Delete only after owner approval and a fresh reference check. The first
execution task should include only the high-confidence candidate below.

| File | Risk | Deletion rationale | Required pre-delete checks |
| --- | --- | --- | --- |
| `apps/dsa-web/src/i18n/canonical-i18n-migration-notes.md` | Low to medium | Unreferenced tracked point-in-time frontend i18n migration note; not a current docs index, guardrail, source contract, test fixture, or active task input. | `rg -n "canonical-i18n-migration-notes|Canonical i18n Migration Notes" .`; confirm no active i18n cleanup task needs it; `git diff --check`; secret scan. |

Deferred deletion candidates only after references and indexes are updated:

| File | Risk | Why not in first batch |
| --- | --- | --- |
| `docs/audits/archive/markdown-inventory.md` | Medium | Historical and partly superseded by this report, but it is still referenced by active audit indexes and `docs/ARCHIVE_INDEX.md`. |
| `docs/audits/archive/markdown-consolidation-plan.md` | Medium | Overlaps this report, but active indexes and `public-launch-readiness-master.md` still reference it. |
| `docs/audits/archive/final-pre-push-audit.md` | Medium | Historical launch evidence still referenced by launch and warning docs. |

No `docs/codex/audits/*.md` file should be deleted in the first cleanup batch.
Older reports should be archived first, not deleted, because many define
protected-domain task boundaries that are easier to lose than to reconstruct.

## CONSOLIDATE_CANDIDATE

These docs overlap and should be merged into canonical docs before deletion.

| Group | Candidate files | Canonical target |
| --- | --- | --- |
| Markdown retention governance | `docs/audits/archive/markdown-inventory.md`, `docs/audits/archive/markdown-consolidation-plan.md`, this T-1247 report | Keep T-1247 as current cleanup plan; update `docs/ARCHIVE_INDEX.md` and domain indexes before deleting old referenced notes. |
| Codex prompt authoring | `WOLFYSTOCK_CODEX_COMPACT_PROMPT_PROTOCOL.md`, `WOLFYSTOCK_CODEX_MINIMAL_PROMPT_PROTOCOL.md`, `WOLFYSTOCK_CODEX_TASK_TEMPLATES.md`, `WOLFYSTOCK_CODEX_COMPACT_TASK_EXAMPLES.md` | One prompt-authoring guide plus examples, linked from `docs/codex/README.md`. |
| Codex final report protocol | `WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`, `WOLFYSTOCK_CODEX_COMPACT_FINAL_REPORT_PROTOCOL.md` | Keep full template canonical; fold compact rules into it or link as a short appendix. |
| Codex execution summary | `WOLFYSTOCK_CODEX_EXECUTION_POLICY.md`, `WOLFYSTOCK_CODEX_STANDARD_GUARD.md`, `WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md` | Keep guard/runtime canonical; execution policy remains a summary only or is folded into prompt protocol. |
| Admin data and governance | `admin-data-control-center-design.md`, `admin-data-control-center-frontend-ux-contract.md`, `admin-data-governance-next-phase-design.md`, `admin-data-schema-inventory.md`, `admin-user-directory-api-design.md`, `admin-user-activity-timeline-api-design.md`, `admin-role-management-ui-design.md` | `docs/audits/index-security-rbac-mfa.md` plus `docs/admin-ops/README.md` or a new admin-data index. |
| Cost/quota/LLM observability | `cost-observability-*`, `duplicate-cost-*`, `llm-*`, `quota-cost-notification-release-guide.md` | `docs/audits/index-cost-quota-observability.md`. |
| DB/WS2/deployment | `db-*`, `ws2-*`, deployment/readiness docs | `docs/audits/index-db-ws2-deployment.md`, while preserving launch master/gap register. |
| Provider/data/options | provider runbooks, options source candidate worksheets, options phase0/provider docs | `docs/audits/index-provider-data-options.md`, `docs/provider-data/README.md`, `docs/options/README.md`. |
| Frontend historical evidence | `docs/frontend/archive/*.md`, `docs/audits/archive/frontend/*.md` | Keep both archive lanes indexed from `docs/ARCHIVE_INDEX.md`; consolidate only the navigation, not the evidence, unless owner approves cold archive. |
| Architecture storage/Postgres plans | `postgresql-baseline-*`, storage coordination, DB component/maintenance docs | `docs/architecture/README.md` plus current database handbooks. Do not delete until implementation status is reconciled. |

## REVIEW_MANUALLY

These are unsafe to delete without owner or domain decision.

| File or group | Risk |
| --- | --- |
| `DESIGN.md` | External or prompt-context dependency risk. Archive candidate, not direct delete. |
| Root bilingual public docs (`docs/full-guide*`, `docs/FAQ*`, `docs/README_*`, `docs/INDEX_EN.md`) | Public docs and bilingual sync risk. |
| `docs/audits/*` files marked `Status: Partial` or `Status: Deferred` | May describe partially implemented but still active protected-domain work. |
| Options source candidate worksheets (`options-*-source-candidate-evidence.md`) | External-source onboarding evidence; owner must decide if failed candidates need historical retention. |
| `docs/architecture/postgresql-baseline-*` and storage plans | Storage/source-of-truth cleanup risk. |
| Bot docs and Discord/DingTalk/Feishu config docs | External integration risk; static repo references are not enough to prove no operator dependency. |
| `docs/openclaw-skill-integration.md` | External integration doc referenced by `AGENTS.md` as product/integration material. |

## Audit question answers

### 1. Which docs are canonical and must never be deleted without explicit owner approval?

Canonical docs are:

- `AGENTS.md`, `CLAUDE.md`, `.github/**`, `.claude/skills/**`, `README.md`,
  and `SKILL.md`.
- `docs/DOCS_INDEX.md`, `docs/ARCHIVE_INDEX.md`,
  `docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`,
  `docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md`,
  `docs/CHANGELOG.md`, and `docs/architecture/file-governance-taxonomy.md`.
- Current Codex process and protected-domain docs under `docs/codex/`, especially
  the standard guard, runtime rules, final report template, backend protected
  domains, provider budget/routing, backtest universe rules, prompt context,
  model routing, and shared-main protocol.
- Current frontend authority under `docs/frontend/`.
- Current source-confidence/data-coverage contracts under
  `docs/data-reliability/`.
- Current domain entrypoints and protected-domain contracts under
  `docs/backtest/`, `docs/portfolio/`, `docs/alerts/`, `docs/options/`,
  `docs/provider-data/`, `docs/scanner/`, `docs/market-overview/`,
  `docs/liquidity/`, `docs/rotation/`, `docs/operations/`, and
  `docs/architecture/`.
- Current launch/domain/operator audit indexes and runbooks under
  `docs/audits/`.

### 2. Which audit reports are still active because they directly define upcoming tasks?

Active task-defining reports are:

- `docs/codex/goals/T-1175_PROGRESS.md`
- `docs/codex/audits/T-1176-system-wide-consolidation-audit.md`
- `docs/codex/audits/T-1212-watchlist-research-workflow-audit.md`
- `docs/codex/audits/T-1213-portfolio-risk-exposure-summary-audit.md`
- `docs/codex/audits/T-1215-scanner-watchlist-pipeline-audit.md`
- Recent or still-cited evidence reports in the T-1045 to T-1087 range,
  especially T-1047, T-1062, T-1077, T-1078, T-1080, T-1086, and T-1087.
- React Doctor and frontend cleanup chain reports T-987, T-989, T-990, T-992,
  T-995, WFE-001, WFE-002, WRD-008, and `wrd-goal-react-doctor-100-progress.md`
  until their follow-up wave is closed.
- Product architecture and provenance chain reports T-892, T-913, T-917,
  T-918, T-925, T-929, T-930, T-935, T-953, T-957, and T-981 until decisions
  are captured in current indexes/contracts.

### 3. Which old audit reports can be deleted after their key decisions are captured elsewhere?

Potential delete-after-capture targets are limited to already archived,
referenced historical notes:

- `docs/audits/archive/markdown-inventory.md`
- `docs/audits/archive/markdown-consolidation-plan.md`
- `docs/audits/archive/final-pre-push-audit.md`

They cannot be deleted now because active docs reference them. The safe path is:

1. capture their useful decisions in this T-1247 report, `docs/ARCHIVE_INDEX.md`,
   and relevant domain indexes;
2. remove or update references;
3. run link/reference checks;
4. delete in a separate owner-approved cleanup task.

### 4. Which docs duplicate newer contracts or have been superseded?

Superseded or overlapping docs include:

- `DESIGN.md`, superseded as current UI authority by `docs/frontend/` and
  `docs/design/README.md`.
- `docs/audits/archive/markdown-inventory.md` and
  `docs/audits/archive/markdown-consolidation-plan.md`, superseded for current
  cleanup planning by this audit.
- Codex prompt-authoring docs listed under CONSOLIDATE_CANDIDATE.
- Old frontend archive evidence under `docs/frontend/archive/` and
  `docs/audits/archive/frontend/`, superseded as current UI authority but still
  useful as historical proof.
- `docs/audits/options-lab-phase0-design.md`, marked `Status: Superseded` but
  still listed by current Options docs; consolidate before deletion.
- Partial/deferred admin, security, DB/WS2, cost, and provider plans that now
  overlap current domain indexes.

### 5. Which folders are bloated and should get retention rules?

Folders needing explicit retention rules:

- `docs/codex/audits/`: define active window, closure marker, and archive
  destination for task reports.
- `docs/audits/`: separate current authority, active designs, and historical
  support evidence more visibly.
- `docs/audits/archive/`: add cold-retention policy for files older than an
  owner-approved horizon.
- `docs/frontend/archive/` and `docs/audits/archive/frontend/`: keep a single
  archive index and avoid listing every old UI proof in active docs.
- `docs/architecture/archive/`: retain provenance but avoid active-link drift.

### 6. What is the smallest safe deletion batch for the next execution task?

Delete only:

- `apps/dsa-web/src/i18n/canonical-i18n-migration-notes.md`

Do not delete or move anything under:

- `docs/codex/**`
- `docs/audits/**`
- `docs/frontend/**`
- `docs/data-reliability/**`
- `docs/backtest/**`
- `docs/portfolio/**`
- `docs/alerts/**`
- root governance docs

### 7. Which files should be archived rather than deleted?

Archive rather than delete:

- `DESIGN.md`
- older `docs/codex/audits/T-*.md` reports after their task chains close
- WFE/WRD frontend validation reports after their validation wave closes
- existing historical lanes under `docs/frontend/archive/`,
  `docs/audits/archive/`, `docs/architecture/archive/`, and `docs/qa/archive/`

## Proposed retention policy for future Codex audits

### Codex audit status labels

Every new `docs/codex/audits/*.md` report should include exactly one status:

- `ACTIVE_TASK_DEFINITION`: directly defines an allowed future execution task.
- `ACTIVE_REFERENCE`: still cited by current prompts, domain indexes, or
  protected contracts.
- `SUPERSEDED_CAPTURED`: decisions are captured in a current contract/index.
- `HISTORICAL_PROVENANCE`: useful only for why/history.
- `DELETE_AFTER_APPROVAL`: generated/duplicate and safe to delete after final
  reference checks.

### Default retention windows

- Keep `ACTIVE_TASK_DEFINITION` and `ACTIVE_REFERENCE` in the active folder.
- Move `SUPERSEDED_CAPTURED` to an archive lane after the follow-up task lands
  and indexes are updated.
- Keep `HISTORICAL_PROVENANCE` in archive for at least one release train or
  one owner-approved cleanup cycle.
- Delete only `DELETE_AFTER_APPROVAL` files after path and basename references
  are zero.

### Required archive metadata

Archived audit reports should carry:

- original task ID and title;
- superseding doc or task;
- owner domain;
- active contracts preserved;
- whether deletion is ever allowed.

### Required pre-delete checks

Before deleting tracked Markdown:

```bash
git status --short --branch
rg -n "<full/path>|<basename>" .
git log --follow --oneline -- <candidate_file>
git diff --check
./scripts/release_secret_scan.sh
```

If Git Bash is unavailable on Windows, run the task's targeted secret-pattern
fallback on changed docs and record the limitation.

## First safe execution task

Task title: Delete stale i18n migration note

Goal:

- Remove the one unreferenced temporary Markdown note found in this audit.
- Do not touch docs guardrails, contracts, audits, source code, tests, config,
  package files, lockfiles, CI, scripts, runtime files, or frontend behavior.

Exact allowed file to delete:

- `apps/dsa-web/src/i18n/canonical-i18n-migration-notes.md`

Exact allowed files to move:

- none

Exact forbidden files and folders:

- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `SKILL.md`
- `DESIGN.md`
- `.github/**`
- `.claude/**`
- `docs/**`
- `src/**`
- `api/**`
- `data_provider/**`
- `bot/**`
- `apps/dsa-web/src/**/*.ts`
- `apps/dsa-web/src/**/*.tsx`
- `apps/dsa-web/package.json`
- `apps/dsa-web/package-lock.json`
- `apps/dsa-desktop/**`
- `tests/**`
- `scripts/**`
- `.gitignore`
- package, lock, CI, DB, migration, provider, cache, backend, frontend runtime,
  and protected-domain files

Validation for that future execution task:

```bash
rg -n "canonical-i18n-migration-notes|Canonical i18n Migration Notes" .
git diff --check -- apps/dsa-web/src/i18n/canonical-i18n-migration-notes.md
G:\Git\bin\bash.exe ./scripts/release_secret_scan.sh
git status --short --branch
```

If Git Bash is unavailable, run a targeted changed-file secret scan against the
deleted-file diff metadata and report the limitation.

## First safe archival task after owner approval

Task title: Archive root legacy design reference

Goal:

- Move root `DESIGN.md` out of the repository root so it no longer looks like
  current UI authority.
- Preserve it as historical design provenance.
- Update only references that point to its old root location.

Exact allowed move:

- from `DESIGN.md`
- to `docs/frontend/archive/linear-design-analysis-legacy-reference.md` or an
  owner-approved design archive path

Exact allowed reference updates:

- `docs/architecture/file-governance-taxonomy.md`
- `docs/codex/WOLFYSTOCK_PROMPT_CONTEXT_INDEX.md`
- `docs/ARCHIVE_INDEX.md`
- `docs/frontend/archive/README.md`

Forbidden:

- any current frontend authority text in `docs/frontend/visual-system.md`
  unless the owner explicitly scopes it;
- source, tests, config, package, lockfile, CI, or runtime files.

Risk:

- Medium. This is an archive move, not deletion, because prompt context still
  references `DESIGN.md` as a reference-only asset.

## No-write confirmation for existing docs

This audit report intentionally did not delete, move, rename, or edit any
existing Markdown file. Existing docs remain in place for a later execution task
with explicit owner approval.
