# WolfyStock Documentation Index

Status: canonical documentation navigation map.

This file is the active map for AI and human maintainers. It separates current
authority from generated manuals, active references, externally referenced
legacy docs, and historical archive material.

## Start Here

Future AI workers should read no more than these six primary Markdown files
before narrowing into a task-specific domain:

| Order | File | Class | Purpose |
| ---: | --- | --- | --- |
| 1 | [README](../README.md) | canonical entrypoint | Product purpose, stack, run commands, and human orientation. |
| 2 | [AGENTS](../AGENTS.md) | canonical entrypoint | Repository AI collaboration rules and hard safety boundaries. |
| 3 | [AI Project Manual](./AI_PROJECT_MANUAL.md) | generated canonical output | Main AI onboarding manual for purpose, architecture, surfaces, data reality, protected domains, validation, and source map. |
| 4 | [Docs Index](./DOCS_INDEX.md) | canonical entrypoint | Current doc navigation and Markdown classification map. |
| 5 | [Surface Map](./codex/WOLFYSTOCK_SURFACE_MAP.md) | active reference | Stable product surface to endpoint/service/page/test lookup. |
| 6 | [Codex Execution Policy](./codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md) | canonical manual source | Compact task-mode, validation, commit/push, and final-report policy. |

## Agent Rules

| File | Class | Use |
| --- | --- | --- |
| [AGENTS](../AGENTS.md) | canonical entrypoint | Source of truth for repository AI rules. |
| [AI Maintenance Manual](./WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md) | canonical manual source | Worker modes, stale-doc traps, validation expectations, and handoff checklist. |
| [Codex Standard Guard](./codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md) | canonical manual source | Operating guard for bounded Codex work. |
| [Codex Runtime Rules](./codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md) | canonical manual source | Workspace, mode, branch, commit, and push rules. |
| [Codex Final Report Template](./codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md) | canonical manual source | Required final report evidence contract. |
| [Codex Prompt Context Index](./codex/WOLFYSTOCK_PROMPT_CONTEXT_INDEX.md) | active reference | Prompt authoring and context compression guide. |

`CLAUDE.md`, `.github/copilot-instructions.md`,
`.github/instructions/*.instructions.md`, `.claude/skills/**`, and
`.agents/skills/**` are kept because external agent tools reference those paths.
They are mirrors or compatibility assets, not higher authority than
`AGENTS.md`.

## Product Architecture

| File | Class | Use |
| --- | --- | --- |
| [System Handbook](./WOLFYSTOCK_SYSTEM_HANDBOOK.md) | canonical manual source | Product, route, API, provider, validation, and troubleshooting overview. |
| [Surface Map](./codex/WOLFYSTOCK_SURFACE_MAP.md) | active reference | Endpoint/schema/service/page/test lookup by surface. |
| [Module Architecture](./architecture/WOLFYSTOCK_MODULE_ARCHITECTURE.md) | canonical manual source | Bounded contexts, dependency rules, and protected domain ownership. |
| [Backend / Frontend Maintenance Handbook](./architecture/backend-frontend-modular-maintenance-handbook.md) | canonical manual source | Module owners, first files, invariants, and debug flow. |
| [File Governance Taxonomy](./architecture/file-governance-taxonomy.md) | canonical manual source | Active-vs-archive rules and docs asset governance. |

Task-specific product entry points remain active because they route directly to
current surface rules:

- [Market Overview](./market-overview/README.md)
- [Scanner and Watchlist](./scanner/README.md)
- [Liquidity](./liquidity/README.md)
- [Rotation](./rotation/README.md)
- [Portfolio](./portfolio/README.md)
- [Backtest](./backtest/README.md)
- [Options](./options/README.md)
- [Frontend](./frontend/README.md)
- [Operations](./operations/README.md)
- [Provider/Data](./provider-data/README.md)

## Data And Professional Analytics

| File | Class | Use |
| --- | --- | --- |
| [Product Recovery Plan](./product-recovery/WOLFYSTOCK_PRODUCT_RECOVERY_PLAN.md) | canonical manual source | Current recovery posture and product value constraints. |
| [Data Coverage Matrix](./product-recovery/DATA_COVERAGE_MATRIX.md) | canonical manual source | Repo-grounded data-family readiness and gaps. |
| [Professional Data Source Roadmap](./product-recovery/DATA030_PROFESSIONAL_DATA_SOURCE_ROADMAP.md) | canonical manual source | Current professional source roadmap. |
| [Authorized Quote Spine Contract](./product-recovery/DATA038_AUTHORIZED_QUOTE_SPINE_CONTRACT.md) | canonical manual source | Future bounded quote/OHLCV backbone contract. |
| [Backtest Dataset Lineage Gate Contract](./product-recovery/DATA039_BACKTEST_DATASET_LINEAGE_GATE_CONTRACT.md) | canonical manual source | Backtest/factor dataset lineage gate. |
| [Symbol Research Packet Contract](./product-recovery/SYMBOL_RESEARCH_PACKET_CONTRACT.md) | canonical manual source | Watchlist and stock packet readiness contract. |
| [Options Provider Entitlement Decision](./product-recovery/DATA034_OPTIONS_PROVIDER_ENTITLEMENT_DECISION.md) | canonical manual source | Options rights and no-advice boundary. |
| [Scenario Baseline Snapshot Plan](./product-recovery/DATA035_SCENARIO_DURABLE_BASELINE_SNAPSHOT_PLAN.md) | canonical manual source | Scenario durable baseline requirements. |
| [Evidence Harness](./product-recovery/DATA033_TARGET_ENVIRONMENT_EVIDENCE_HARNESS.md) | canonical manual source | Sanitized target-environment evidence harness. |
| [Market Source Activation Blueprint](./data/market-source-activation-blueprint.md) | canonical manual source | Official risk and quote source activation roadmap. |
| [Provider Source-Confidence Contract](./data-reliability/provider-source-confidence-contract.md) | canonical manual source | Provider confidence, freshness, and fail-closed boundary. |
| [Provider Capability Metadata](./operations/provider-capability-metadata.md) | canonical manual source | Inert provider metadata and source-confidence rules. |

`DATA011`, `DATA016`, and `DATA021` acceptance snapshots are archived under
`docs/archive/product-recovery/acceptance/`; their durable conclusions are
absorbed into the generated AI manual and the active product-recovery contracts
above.

## Validation And Protected Domains

| File | Class | Use |
| --- | --- | --- |
| [Backend Protected Domains](./codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md) | canonical manual source | Scanner, backtest, portfolio, provider, AI, auth, notification, cache, API, and stored-contract hard stops. |
| [Validation Matrix](./codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md) | canonical manual source | Smallest-safe validation selection by changed surface. |
| [No-Advice Regression Guards](./codex/NO_ADVICE_REGRESSION_GUARDS.md) | canonical manual source | No-advice, no-order, raw-provider, and consumer copy guards. |
| [Provider Budget And Routing Rules](./codex/WOLFYSTOCK_PROVIDER_BUDGET_AND_ROUTING_RULES.md) | canonical manual source | Provider budget, quota, and routing guardrails. |
| [Backtest Universe Rules](./codex/WOLFYSTOCK_BACKTEST_UNIVERSE_RULES.md) | canonical manual source | Backtest universe local-only and professional-readiness guardrails. |
| [Frontend Validation Playbook](./frontend/validation-playbook.md) | canonical manual source | Browser and frontend evidence expectations. |
| [Audit Index](./audits/README.md) | active reference | Current launch, safety, domain, and operator-evidence navigation. |

## Active Reference Lanes

| Lane | Class | Purpose |
| --- | --- | --- |
| `docs/architecture/` | active reference | Current architecture, database, and module docs. Historical architecture reports live in `docs/archive/architecture/`. |
| `docs/audits/` | active reference | Current launch, safety, operator, security, provider, cost, and deployment references. Point-in-time reports live in `docs/archive/audits/`. |
| `docs/frontend/` | active reference | Current frontend visual system, validation, IA, and UX policy. Historical frontend audits live in `docs/archive/frontend/` and `docs/archive/audits/frontend/`. |
| `docs/operations/` | active reference | Current runbooks, artifact cleanup, queue/WS2 notes, provider metadata, and operator procedures. |
| `docs/product-recovery/` | canonical manual source | Durable current recovery contracts and roadmaps only. Historical snapshots live in `docs/archive/product-recovery/`. |
| `docs/codex/` | canonical manual source | Durable Codex workflow, validation, prompt, protected-domain, and report docs only. Task reports live in `docs/archive/codex/`. |
| `docs/backtest/`, `docs/options/`, `docs/portfolio/`, `docs/scanner/`, `docs/rotation/`, `docs/liquidity/`, `docs/market-overview/` | active reference | Current surface-specific rules and entry docs. |

Legacy or externally referenced docs such as `docs/full-guide*.md`,
`docs/README_EN.md`, `docs/README_CHT.md`, `docs/INDEX_EN.md`, `SKILL.md`, and
`docs/openclaw-skill-integration.md` are kept because public links, bilingual
docs, or external skill consumers may reference them. Prefer the six-file start
path for AI onboarding.

## Markdown Classification Rules

Classify Markdown files by the first matching rule:

| Class | Rule |
| --- | --- |
| canonical entrypoint | `README.md`, `AGENTS.md`, `docs/DOCS_INDEX.md` |
| generated canonical output | `docs/AI_PROJECT_MANUAL.md` |
| canonical manual source | Files curated by `scripts/build_ai_project_manual.py` and listed in `docs/AI_PROJECT_MANUAL_SOURCES.json` |
| active reference | Current surface, architecture, audit index, operations, frontend, product, and provider docs linked from this index |
| historical task report | Point-in-time audits, QA passes, goal-progress notes, acceptance snapshots, and retired Codex task reports under `docs/archive/` |
| outdated recovery note | Superseded recovery or root-cause snapshots under `docs/archive/product-recovery/` |
| duplicate/covered by manual | Legacy broad guides or translated duplicates when the AI manual already covers the maintenance path |
| archive-only | Any file under `docs/archive/` |
| keep because externally referenced | Agent mirrors, public bilingual docs, root `SKILL.md`, OpenClaw skill integration, issue/PR templates |
| candidate for deletion only if safe | Generated, duplicate, or superseded docs with no active references and no historical value |

## Historical Archive

Use [Archive Index](./ARCHIVE_INDEX.md) for archive lanes and safe-use rules.
All historical Markdown moved by DOCS-005 now lives under:

- `docs/archive/audits/`
- `docs/archive/architecture/`
- `docs/archive/codex/`
- `docs/archive/design/`
- `docs/archive/frontend/`
- `docs/archive/product-audit/`
- `docs/archive/product-recovery/`
- `docs/archive/qa/`

Archive docs preserve provenance only. They are not current launch, provider,
security, portfolio, backtest, API, frontend, or product-readiness authority
unless an active doc explicitly re-promotes them for a specific question.
