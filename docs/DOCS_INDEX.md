# WolfyStock Documentation Index

This is the starting navigation map for maintainers. It points to the current
source-of-truth documents and separates active authority from historical
evidence, local artifacts, and older inherited guides.

## Start Here

- [WolfyStock System Handbook](./WOLFYSTOCK_SYSTEM_HANDBOOK.md): product,
  module, route, API, provider, validation, troubleshooting, and safe-change
  overview.
- [WolfyStock AI Maintenance Manual](./WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md):
  Codex worker rules, protected domains, validation expectations, stale-doc
  traps, and AI-assisted maintenance workflow.
- [Archive Index](./ARCHIVE_INDEX.md): retained historical evidence and audit
  provenance that must not be treated as current authority unless another
  current doc says so.
- [File Governance Taxonomy](./architecture/file-governance-taxonomy.md):
  active-vs-archive rules, docs lanes, asset/fixture policy, and AI navigation
  rules.
- [Operations Runbook](./operations/WOLFYSTOCK_RUNBOOK.md): operator runbook
  skeleton and links to current operational guides.
- [README](../README.md): repository overview, local run commands, and product
  orientation.
- [Changelog](./CHANGELOG.md): user-visible, operational, and documentation
  navigation changes.

## Directory Guides

- [Audit Index](./audits/README.md): current audit, launch, and operator
  evidence navigation.
- [Architecture Docs](./architecture/README.md): current backend, storage, and
  portfolio architecture navigation.
- [Codex Docs](./codex/README.md): current Codex workflow, prompt, and frontend
  validation navigation.
- [Design Docs](./design/README.md): current Reflect-Linear design navigation.
- [Operations Docs](./operations/README.md): current operator runbook and
  artifact-handling navigation.

## Current Authority

Use these documents before changing code, tests, routes, API contracts, or
operator workflows.

| Area | Current source |
| --- | --- |
| System overview | [System Handbook](./WOLFYSTOCK_SYSTEM_HANDBOOK.md) |
| AI-assisted maintenance | [AI Maintenance Manual](./WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md) |
| Module boundaries | [Modular Architecture Manual](./architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md) |
| Backend/frontend maintenance map | [Backend / Frontend Modular Maintenance Handbook](./architecture/backend-frontend-modular-maintenance-handbook.md) |
| Protected backend domains | [Backend Protected Domains](./codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md) |
| Codex task guard | [Codex Standard Guard](./codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md) |
| Codex runtime modes | [Codex Task Runtime Rules](./codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md) |
| Codex final reports | [Codex Final Report Template](./codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md) |
| Prompt compression and task examples | [Compact Prompt Protocol](./codex/WOLFYSTOCK_CODEX_COMPACT_PROMPT_PROTOCOL.md) and [Compact Task Examples](./codex/WOLFYSTOCK_CODEX_COMPACT_TASK_EXAMPLES.md) |
| Model routing | [Model Routing](./codex/WOLFYSTOCK_CODEX_MODEL_ROUTING.md) |
| Prompt context lookup | [Prompt Context Index](./codex/WOLFYSTOCK_PROMPT_CONTEXT_INDEX.md) |
| File/docs governance | [File Governance Taxonomy](./architecture/file-governance-taxonomy.md) |
| Frontend design authority | [Linear OS Design Language](./codex/WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md) |
| Frontend route taxonomy | [Frontend Surface Usage](./codex/WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md) and [Route Templates](./codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md) |
| Frontend primitive policy | [Terminal Primitives Usage](./codex/WOLFYSTOCK_TERMINAL_PRIMITIVES_USAGE.md), [Design Docs](./design/README.md), and [Canonical UI Primitives](./design/wolfystock-canonical-ui-primitives.md) |
| Frontend validation | [Frontend Validation Playbook](./codex/WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md) and [Visual Evidence Protocol](./codex/WOLFYSTOCK_CODEX_VISUAL_EVIDENCE_PROTOCOL.md) |
| Launch readiness | [Audit Index](./audits/README.md), [Public Launch Readiness Master](./audits/public-launch-readiness-master.md), and [Public Launch Gap Register](./audits/public-launch-gap-register.md) |

## Module References

| Module or workflow | Start with | Supporting docs |
| --- | --- | --- |
| Analysis and reports | [Full Guide](./full-guide.md), [AI Decision Engine](./ai-decision-engine.md) | [LLM Config Guide](./LLM_CONFIG_GUIDE.md), [Image Extract Prompt](./image-extract-prompt.md) |
| Scanner and watchlist | [Market Scanner](./market-scanner.md) | [Scanner export label policy](./product/wolfystock-scanner-export-label-policy.md) |
| Backtest | [Backtest System](./backtest-system.md) | [Backtest helper maintenance](./backtest-helper-maintenance.md), [Rule backtest reopen trust status](./architecture/rule-backtest-reopen-trustworthiness-p0-status-index-2026-04-22.md) |
| Bot notifications | [Discord bot config](./bot/discord-bot-config.md) | [DingTalk bot config](./bot/dingding-bot-config.md), [Feishu bot config](./bot/feishu-bot-config.md) |
| Portfolio | [Modular Architecture Manual](./architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md) | [Phase F decisions](./architecture/phase-f/decisions.md), [Phase F status](./architecture/phase-f/status.md), [Phase F runbook](./architecture/phase-f/runbook.md) |
| Provider and freshness | [Provider Data Freshness Reliability Guide](./audits/provider-data-freshness-reliability-guide.md) | [Provider Capability Metadata](./operations/provider-capability-metadata.md), [Market Data Provider Upgrade Matrix](./audits/market-data-provider-upgrade-decision-matrix.md), [Provider Incident Runbook](./audits/provider-data-incident-runbook.md) |
| Provider operations dashboard | [Market Provider Operations Dashboard](./design/wolfystock-market-provider-operations-dashboard.md) | [Provider Capability Metadata](./operations/provider-capability-metadata.md), [Provider Budget And Routing Rules](./codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md) |
| Options Lab | [Options provider adapter contract](./audits/options-provider-adapter-contract.md) | [Options Lab phase 0 design](./audits/options-lab-phase0-design.md), [Trading no-advice policy](./audits/trading-no-advice-product-policy.md) |
| Admin, security, RBAC | [Auth/RBAC release security guide](./audits/auth-rbac-release-security-guide.md) | [Admin RBAC capability model](./audits/admin-rbac-capability-model-design.md), [Admin role governance plan](./audits/admin-role-governance-plan.md), [Production security hardening audit](./audits/production-security-hardening-audit.md) |
| Cost, quota, observability | [Cost observability design index](./audits/cost-observability-design-index.md) | [Cost observability roadmap](./audits/cost-observability-implementation-roadmap.md), [Quota/cost notification release guide](./audits/quota-cost-notification-release-guide.md) |
| DuckDB quant diagnostics | [Quant DuckDB Engine](./quant-duckdb-engine.md) | [DuckDB Operator Smoke Guide](./operations/duckdb-operator-smoke-guide.md), [DuckDB Production Readiness Checklist](./operations/duckdb-production-readiness-checklist.md) |
| Deployment | [Deploy Guide](./DEPLOY.md) | [Deployment readiness checklist](./audits/deployment-readiness-checklist.md), [Release rollback runbook](./audits/release-rollback-runbook.md), [Zeabur deployment](./docker/zeabur-deployment.md) |
| Desktop package | [Desktop package guide](./desktop-package.md) | [Deploy Guide](./DEPLOY.md) |

## Operations And Runbooks

- [WolfyStock Operations Runbook](./operations/WOLFYSTOCK_RUNBOOK.md):
  high-level operator flow and triage skeleton.
- [Artifact Cleanup Policy](./operations/ARTIFACT_CLEANUP_POLICY.md):
  tracked-vs-generated artifact ownership and cleanup timing rules.
- [Parallel Codex Operator Playbook](./operations/parallel-codex-playbook.md):
  same-repo and parallel worker safety.
- [Provider Data Incident Runbook](./audits/provider-data-incident-runbook.md):
  provider outage and freshness incident response.
- [Operator Evidence Real Runbook](./audits/operator-evidence-real-runbook.md):
  sanitized real-operator evidence collection.
- [Operator Evidence Dry-Run Handoff](./audits/operator-evidence-dry-run-handoff.md):
  synthetic rehearsal flow for evidence workflow.
- [Operator Evidence Redaction Checklist](./audits/operator-evidence-redaction-checklist.md):
  redaction before handoff.
- [Release Rollback Runbook](./audits/release-rollback-runbook.md):
  release rollback decisioning.
- [CI Gate Usage](./audits/ci-gate-usage.md): when to use fast worker gates
  versus full release gates.
- [CI PostgreSQL Gate Triage](./audits/ci-postgres-gate-triage-guide.md):
  PostgreSQL CI triage.
- [DuckDB Operator Smoke Guide](./operations/duckdb-operator-smoke-guide.md):
  local DuckDB diagnostics only.

## Historical Evidence

Historical docs are useful for provenance and prior decisions, but they are not
current authority unless a current index or handbook points to them for that
specific question.

- [Archive Index](./ARCHIVE_INDEX.md): consolidated historical evidence map.
- [Audit Index](./audits/README.md): current audit navigation, launch posture,
  and archived audit warnings.
- `docs/audits/archive/`: archived audit and consolidation notes.
- `docs/audits/archive/backtest/`: archived backtest maintenance evidence and
  machine-readable audit bundles.
- `docs/audits/archive/frontend/`: archived frontend DOM/CSS/bundle/old launch
  UX evidence.
- `docs/architecture/archive/`: archived architecture and Phase F evidence.
- `docs/qa/archive/`: archived point-in-time QA reports.
- `docs/design/archive/old-ui/`: archived transitional UI replacement notes.

## Local Or Ignored Docs Excluded From Authority

These paths can be useful during local work, but they are not repository
authority and should not be cited as current system truth without a tracked
source document:

- `.claude/reviews/`: local analysis/review outputs.
- `.codex/` and `.codex-artifacts/`: local Codex runtime artifacts.
- `reports/`: generated local reports.
- `test-results/`, `playwright-report/`, `blob-report/`, and `screenshots/`:
  generated test/browser/visual artifacts.
- `coverage/`, `.coverage`, and generated coverage output.
- `repo_archive/`, `repo_trash/`, and packaged/exported archives unless a
  current tracked doc explicitly references the artifact.

`AGENTS.md` remains the repository AI-collaboration source of truth. `.claude`
skills may be tracked collaboration assets, but local review outputs under
`.claude/reviews/` are intentionally not authority.
