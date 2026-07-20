# WolfyStock AI Project Manual

> GENERATED FILE. DO NOT EDIT DIRECTLY.
> Canonical registry: [`docs/documentation-manifest.json`](../documentation-manifest.json). Generator: [`scripts/build_ai_project_manual.py`](../../scripts/build_ai_project_manual.py).

This manual is a generated navigation and integrity catalog. It does not copy domain rules, authorize protected changes, approve release, or replace current source/test inspection.

## Mandatory Context

1. Read the current task and [AGENTS.md](../../AGENTS.md).
2. Use [docs/README.md](../README.md) to select only the applicable canonical documents.
3. Read the closest source and tests; they remain the executable truth.

## Task Routing

| Task | Read after the mandatory context | Boundary |
| --- | --- | --- |
| Backend, API, service, repository, or schema work | [docs/architecture/overview.md](../architecture/overview.md)<br>[docs/contracts/data-trust.md](../contracts/data-trust.md) | Add the closest source and tests; shared schemas and public contracts require producer/consumer review. |
| Provider, market, scanner, freshness, or source-authority work | [docs/contracts/data-trust.md](../contracts/data-trust.md)<br>[docs/architecture/overview.md](../architecture/overview.md) | Provider order, fallback, cache, freshness, and scoring are protected. |
| Backtest, portfolio, broker, accounting, auth, RBAC, or security work | [docs/contracts/data-trust.md](../contracts/data-trust.md) | Read the exact owner source/tests and retain all fail-closed distinctions. |
| Web UI, route, content, interaction, accessibility, or visual design work | [docs/design/frontend.md](../design/frontend.md)<br>[docs/contracts/data-trust.md](../contracts/data-trust.md)<br>[docs/architecture/overview.md](../architecture/overview.md) | The design contract does not override runtime, auth, or domain truth. |
| Dependency, lock, environment, bootstrap, local runtime, or configuration work | [docs/development/environment.md](../development/environment.md) | Use ./wolfy; do not create a second install or resolver authority. |
| Tests, topology, validation, browser UAT, or evidence qualification | [docs/development/validation.md](../development/validation.md) | AGENTS.md owns evidence policy; this document routes commands. |
| Database, storage, migration, restore, PostgreSQL, Phase F, or DuckDB work | [docs/operations/database.md](../operations/database.md)<br>[docs/contracts/data-trust.md](../contracts/data-trust.md) | Migration and persistence changes require explicit scope. |
| Operator evidence, production readiness, release, or target-environment work | [docs/operations/operator-evidence.md](../operations/operator-evidence.md)<br>[docs/operations/release.md](../operations/release.md)<br>[docs/development/validation.md](../development/validation.md) | Sanitized evidence supports manual review and does not auto-approve release. |
| Historical OHLCV foundation, cache seed, or readiness work | [docs/contracts/historical-market-data.md](../contracts/historical-market-data.md)<br>[docs/operations/historical-ohlcv-seed.md](../operations/historical-ohlcv-seed.md)<br>[docs/contracts/data-trust.md](../contracts/data-trust.md) | A successful seed does not imply quote, scanner, or backtest readiness. |
| Documentation architecture, AI instructions, generators, or navigation work | [docs/documentation-manifest.json](../documentation-manifest.json)<br>[docs/development/validation.md](../development/validation.md) | Edit canonical sources and regenerate; do not edit generated outputs. |
| Audit follow-up, remediation roadmap, or evidence retirement | [docs/audits/README.md](../audits/README.md) | Read only the specifically applicable temporary report, never the whole audit corpus. |

## Canonical Authority Map

| Authority | Canonical source | Scope |
| --- | --- | --- |
| repository-governance | [AGENTS.md](../../AGENTS.md) | AI collaboration rules, protected domains, completion evidence, Git authorization, and delivery gates |
| human-onboarding | [README.md](../../README.md) | product orientation and quick start |
| documentation-architecture | [docs/documentation-manifest.json](../documentation-manifest.json) | Markdown classification, root placement, task routing, generated outputs, and temporary evidence lifecycle |
| system-architecture | [docs/architecture/overview.md](../architecture/overview.md) | runtime entrypoints, repository map, component ownership, and cross-module boundaries |
| data-trust | [docs/contracts/data-trust.md](../contracts/data-trust.md) | truth vocabulary, source authority, readiness, no-advice, and protected financial-domain distinctions |
| historical-market-data | [docs/contracts/historical-market-data.md](../contracts/historical-market-data.md) | normalized historical OHLCV contract, quality outcomes, persistence, and read interfaces |
| frontend-design | [docs/design/frontend.md](../design/frontend.md) | consumer product experience, information architecture, visual system, accessibility, and frontend implementation |
| development-environment | [docs/development/environment.md](../development/environment.md) | dependency authority, supported targets, bootstrap, snapshots, local runtime, and optional configuration |
| validation-reference | [docs/development/validation.md](../development/validation.md) | validation command routing and evidence execution reference; AGENTS.md owns policy |
| database-operations | [docs/operations/database.md](../operations/database.md) | database diagnostics, baseline artifacts, Phase F configuration, and DuckDB local analytics |
| historical-seed-operations | [docs/operations/historical-ohlcv-seed.md](../operations/historical-ohlcv-seed.md) | explicit local historical OHLCV starter cache seeding and verification |
| operator-evidence | [docs/operations/operator-evidence.md](../operations/operator-evidence.md) | sanitized offline operator-evidence preparation and manual review |
| release-readiness | [docs/operations/release.md](../operations/release.md) | production-readiness documentation, release qualification, and operational review boundaries |
| audit-lifecycle | [docs/audits/README.md](../audits/README.md) | temporary audit evidence classification and retirement policy |

## Registered Markdown Inventory

| Path | Kind | Status | Direct edit | Purpose | SHA-256 |
| --- | --- | --- | --- | --- | --- |
| [.claude/skills/README.md](../../.claude/skills/README.md) | tool_workflow | active | yes | Claude-compatible repository skill index; defers to AGENTS.md | 12c76fe1a644 |
| [.claude/skills/analyze-issue/SKILL.md](../../.claude/skills/analyze-issue/SKILL.md) | tool_workflow | active | yes | Claude issue-analysis workflow; defers to AGENTS.md | 7087b69f11dc |
| [.claude/skills/analyze-pr/SKILL.md](../../.claude/skills/analyze-pr/SKILL.md) | tool_workflow | active | yes | Claude pull-request analysis workflow; defers to AGENTS.md | 4f1459bd4114 |
| [.claude/skills/fix-issue/SKILL.md](../../.claude/skills/fix-issue/SKILL.md) | tool_workflow | active | yes | Claude issue-fix workflow; defers to AGENTS.md | b8cb440145f8 |
| [.github/copilot-instructions.md](../../.github/copilot-instructions.md) | tool_mirror | mirror | yes | GitHub Copilot compatibility entry | cd70c0093d9c |
| [.github/instructions/backend.instructions.md](../../.github/instructions/backend.instructions.md) | tool_mirror | mirror | yes | Path-scoped backend instruction mirror | 08f91f8d32b6 |
| [.github/instructions/client.instructions.md](../../.github/instructions/client.instructions.md) | tool_mirror | mirror | yes | Path-scoped client instruction mirror | 3aa1faea8fe0 |
| [.github/instructions/governance.instructions.md](../../.github/instructions/governance.instructions.md) | tool_mirror | mirror | yes | Path-scoped governance instruction mirror | c7d9ab20e71c |
| [.github/ISSUE_TEMPLATE/bug_report.md](../../.github/ISSUE_TEMPLATE/bug_report.md) | platform_template | active | yes | GitHub bug-report form body | 608e6c365e37 |
| [.github/ISSUE_TEMPLATE/feature_request.md](../../.github/ISSUE_TEMPLATE/feature_request.md) | platform_template | active | yes | GitHub feature-request form body | 3940adddc1e1 |
| [.github/PULL_REQUEST_TEMPLATE.md](../../.github/PULL_REQUEST_TEMPLATE.md) | platform_template | active | yes | GitHub pull-request template | 0dea45ebf511 |
| [AGENTS.md](../../AGENTS.md) | canonical | active | yes | Repository AI rules and protected-domain boundaries | 35ab8fec9728 |
| [CLAUDE.md](../../CLAUDE.md) | tool_entry | mirror | no | Claude automatic-discovery symlink | 35ab8fec9728 |
| [README.md](../../README.md) | canonical | active | yes | Human product orientation and quick start | 0b22ed2ef427 |
| [docs/README.md](../README.md) | generated | generated | no | Generated platform-discoverable documentation entry and task router | generated |
| [docs/architecture/overview.md](../architecture/overview.md) | canonical | active | yes | System map, runtime entrypoints, and component ownership | cfe458a5a97c |
| [docs/audits/README.md](../audits/README.md) | canonical | active | yes | Temporary audit evidence lifecycle policy | 4e9350acf50f |
| [docs/audits/t563-latest-residual-failure-census.md](../audits/t563-latest-residual-failure-census.md) | temporary_evidence | temporary | yes | Residual failure census and T564-T568 remediation map | 9a8bc53ec55a |
| [docs/audits/t569-test-redundancy-performance-audit.md](../audits/t569-test-redundancy-performance-audit.md) | temporary_evidence | temporary | yes | Test redundancy, runtime cost, and T630-T643 roadmap evidence | 8678ae14915a |
| [docs/audits/t570-official-macro-provider-order-decision.md](../audits/t570-official-macro-provider-order-decision.md) | temporary_evidence | temporary | yes | Official macro provider-order decision evidence | 0e6766d8d36b |
| [docs/audits/t575-backend-production-simplification-audit.md](../audits/t575-backend-production-simplification-audit.md) | temporary_evidence | temporary | yes | Backend simplification evidence and T612-T629 roadmap | cd1f8bc827a8 |
| [docs/audits/t576-frontend-production-simplification-audit.md](../audits/t576-frontend-production-simplification-audit.md) | temporary_evidence | temporary | yes | Frontend simplification evidence and T600-T611 roadmap | 9081512345ee |
| [docs/contracts/data-trust.md](../contracts/data-trust.md) | canonical | active | yes | Cross-domain truth, source, readiness, no-advice, and protected semantics | 976c004be4f6 |
| [docs/contracts/historical-market-data.md](../contracts/historical-market-data.md) | canonical | active | yes | Historical OHLCV foundation contract | be8438c651f5 |
| [docs/design/frontend.md](../design/frontend.md) | canonical | active | yes | Consumer frontend design and implementation contract | 4a74cd9c85dc |
| [docs/development/environment.md](../development/environment.md) | canonical | active | yes | Dependency, bootstrap, target, snapshot, runtime, and configuration authority | dafd93e3635e |
| [docs/development/validation.md](../development/validation.md) | canonical | active | yes | Validation command routing and evidence reference | f1f4f1d6949d |
| [docs/generated/AI_PROJECT_MANUAL.md](AI_PROJECT_MANUAL.md) | generated | generated | no | Generated complete documentation catalog | generated |
| [docs/operations/database.md](../operations/database.md) | canonical | active | yes | Database diagnostics, baseline artifacts, Phase F, and DuckDB runbook | 96c9087a86be |
| [docs/operations/historical-ohlcv-seed.md](../operations/historical-ohlcv-seed.md) | canonical | active | yes | Local historical OHLCV seed and verification runbook | d4d4706d3d51 |
| [docs/operations/operator-evidence.md](../operations/operator-evidence.md) | canonical | active | yes | Sanitized offline operator-evidence runbook | a819a54cae32 |
| [docs/operations/release.md](../operations/release.md) | canonical | active | yes | Production-readiness and release qualification authority | c0dcd939b2ad |

Inventory summary: registered=32, discovered=32; canonical=13, generated=2, platform_template=3, temporary_evidence=5, tool_entry=1, tool_mirror=4, tool_workflow=4.

## Temporary Evidence Lifecycle

| Report | Owner | Machine evidence | Retire when | Action |
| --- | --- | --- | --- | --- |
| [docs/audits/t563-latest-residual-failure-census.md](../audits/t563-latest-residual-failure-census.md) | residual-failure remediation owners T564-T568 | none | T564 through T568 are completed, superseded, or explicitly rejected; durable decisions and current failure identity are owned by source, tests, or canonical validation policy; and no current reference depends on this report | delete |
| [docs/audits/t569-test-redundancy-performance-audit.md](../audits/t569-test-redundancy-performance-audit.md) | test-performance roadmap owners T630-T643 | [validation/t569_test_redundancy_performance_audit.json](../../validation/t569_test_redundancy_performance_audit.json) | T643 has landed after T630 through T642 resolve, durable risk-tier and validation-selection policy has moved to canonical owners, and no current reference depends on the report or JSON | delete report and JSON when its executable dependencies have migrated |
| [docs/audits/t570-official-macro-provider-order-decision.md](../audits/t570-official-macro-provider-order-decision.md) | official macro provider-order owner | [validation/t570_official_macro_provider_order_decision.json](../../validation/t570_official_macro_provider_order_decision.json) | the approved decision is encoded in canonical source and focused tests, residual disagreement is resolved, and no current reference depends on the dossier or JSON | delete report and JSON |
| [docs/audits/t575-backend-production-simplification-audit.md](../audits/t575-backend-production-simplification-audit.md) | backend simplification roadmap owners T612-T629 | [validation/t575_backend_production_simplification_audit.json](../../validation/t575_backend_production_simplification_audit.json) | T612 through T629 are completed, superseded, or explicitly rejected; durable architecture decisions are encoded in current source, tests, and canonical manifests; and no current reference depends on the report or JSON | delete report and JSON |
| [docs/audits/t576-frontend-production-simplification-audit.md](../audits/t576-frontend-production-simplification-audit.md) | frontend simplification roadmap owners T600-T611 | [validation/t576_frontend_production_simplification_audit.json](../../validation/t576_frontend_production_simplification_audit.json) | T600 through T611 are completed, superseded, or explicitly rejected; durable frontend decisions are encoded in current source, tests, and the frontend design authority; and no current reference depends on the report or JSON | delete report and JSON |

Temporary reports are deleted when their registered condition is met. They are not moved to archive, history, completed-report, mirror, or compatibility paths.

## Generated Model

The generator reads the structured registry and registered source metadata. It renders navigation, classifications, lifecycle conditions, and hashes; domain prose remains in its canonical owner. The source identity file is [`docs/generated/AI_PROJECT_MANUAL_SOURCES.json`](AI_PROJECT_MANUAL_SOURCES.json).

Run `python scripts/build_ai_project_manual.py --check` for freshness and `python scripts/check_documentation.py` for structure, links, paths, and lifecycle checks.
