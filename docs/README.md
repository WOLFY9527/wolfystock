# WolfyStock Documentation

> GENERATED NAVIGATION. DO NOT EDIT DIRECTLY.
> Source: [`docs/documentation-manifest.json`](documentation-manifest.json). Generator: [`scripts/build_ai_project_manual.py`](../scripts/build_ai_project_manual.py).

This is the model-independent documentation entrypoint. It keeps the mandatory context small, routes tasks to canonical owners, and separates generated, mirrored, historical, and temporary material.

## Mandatory Context

1. Read the current task and [AGENTS.md](../AGENTS.md).
2. Use this task router to select only the applicable canonical documents.
3. Read the closest source and tests; they remain the executable truth.

The root [`README.md`](../README.md) is the human/product entrypoint. The generated [`AI project manual`](generated/AI_PROJECT_MANUAL.md) is a complete catalog, not a second policy or domain authority.

## Task Routing

| Task | Read after the mandatory context | Boundary |
| --- | --- | --- |
| Backend, API, service, repository, or schema work | [docs/architecture/overview.md](architecture/overview.md)<br>[docs/contracts/data-trust.md](contracts/data-trust.md) | Add the closest source and tests; shared schemas and public contracts require producer/consumer review. |
| Provider, market, scanner, freshness, or source-authority work | [docs/contracts/data-trust.md](contracts/data-trust.md)<br>[docs/architecture/overview.md](architecture/overview.md) | Provider order, fallback, cache, freshness, and scoring are protected. |
| Backtest, portfolio, broker, accounting, auth, RBAC, or security work | [docs/contracts/data-trust.md](contracts/data-trust.md) | Read the exact owner source/tests and retain all fail-closed distinctions. |
| Web UI, route, content, interaction, accessibility, or visual design work | [docs/design/frontend.md](design/frontend.md)<br>[docs/contracts/data-trust.md](contracts/data-trust.md)<br>[docs/architecture/overview.md](architecture/overview.md) | The design contract does not override runtime, auth, or domain truth. |
| Dependency, lock, environment, bootstrap, local runtime, or configuration work | [docs/development/environment.md](development/environment.md) | Use ./wolfy; do not create a second install or resolver authority. |
| Tests, topology, validation, browser UAT, or evidence qualification | [docs/development/validation.md](development/validation.md) | AGENTS.md owns evidence policy; this document routes commands. |
| Database, storage, migration, restore, PostgreSQL, Phase F, or DuckDB work | [docs/operations/database.md](operations/database.md)<br>[docs/contracts/data-trust.md](contracts/data-trust.md) | Migration and persistence changes require explicit scope. |
| Operator evidence, production readiness, release, or target-environment work | [docs/operations/operator-evidence.md](operations/operator-evidence.md)<br>[docs/operations/release.md](operations/release.md)<br>[docs/development/validation.md](development/validation.md) | Sanitized evidence supports manual review and does not auto-approve release. |
| Historical OHLCV foundation, cache seed, or readiness work | [docs/contracts/historical-market-data.md](contracts/historical-market-data.md)<br>[docs/operations/historical-ohlcv-seed.md](operations/historical-ohlcv-seed.md)<br>[docs/contracts/data-trust.md](contracts/data-trust.md) | A successful seed does not imply quote, scanner, or backtest readiness. |
| Documentation architecture, AI instructions, generators, or navigation work | [docs/documentation-manifest.json](documentation-manifest.json)<br>[docs/development/validation.md](development/validation.md) | Edit canonical sources and regenerate; do not edit generated outputs. |
| Audit follow-up, remediation roadmap, or evidence retirement | [docs/audits/README.md](audits/README.md) | Read only the specifically applicable temporary report, never the whole audit corpus. |

## Canonical Authority Map

| Authority | Canonical source | Scope |
| --- | --- | --- |
| repository-governance | [AGENTS.md](../AGENTS.md) | AI collaboration rules, protected domains, completion evidence, Git authorization, and delivery gates |
| human-onboarding | [README.md](../README.md) | product orientation and quick start |
| documentation-architecture | [docs/documentation-manifest.json](documentation-manifest.json) | Markdown classification, root placement, task routing, generated outputs, and temporary evidence lifecycle |
| system-architecture | [docs/architecture/overview.md](architecture/overview.md) | runtime entrypoints, repository map, component ownership, and cross-module boundaries |
| data-trust | [docs/contracts/data-trust.md](contracts/data-trust.md) | truth vocabulary, source authority, readiness, no-advice, and protected financial-domain distinctions |
| historical-market-data | [docs/contracts/historical-market-data.md](contracts/historical-market-data.md) | normalized historical OHLCV contract, quality outcomes, persistence, and read interfaces |
| frontend-design | [docs/design/frontend.md](design/frontend.md) | consumer product experience, information architecture, visual system, accessibility, and frontend implementation |
| development-environment | [docs/development/environment.md](development/environment.md) | dependency authority, supported targets, bootstrap, snapshots, local runtime, and optional configuration |
| validation-reference | [docs/development/validation.md](development/validation.md) | validation command routing and evidence execution reference; AGENTS.md owns policy |
| database-operations | [docs/operations/database.md](operations/database.md) | database diagnostics, baseline artifacts, Phase F configuration, and DuckDB local analytics |
| historical-seed-operations | [docs/operations/historical-ohlcv-seed.md](operations/historical-ohlcv-seed.md) | explicit local historical OHLCV starter cache seeding and verification |
| operator-evidence | [docs/operations/operator-evidence.md](operations/operator-evidence.md) | sanitized offline operator-evidence preparation and manual review |
| release-readiness | [docs/operations/release.md](operations/release.md) | production-readiness documentation, release qualification, and operational review boundaries |
| audit-lifecycle | [docs/audits/README.md](audits/README.md) | temporary audit evidence classification and retirement policy |

## Document Classes

- `canonical`: directly editable owner for the stated scope.
- `generated`: output of the registered generator; edit its source instead.
- `tool_entry` / `tool_mirror`: required platform or AI compatibility surface that defers to a canonical owner.
- `tool_workflow` / `platform_template`: local tool or repository-platform workflow asset, not project policy.
- `temporary_evidence`: bounded audit evidence with an owner, retirement condition, and deletion action; never current policy.

## Editing And Validation

Edit canonical sources and [`docs/documentation-manifest.json`](documentation-manifest.json), then run:

```bash
python scripts/build_ai_project_manual.py
python scripts/check_documentation.py
python scripts/build_ai_project_manual.py --check
python scripts/check_ai_assets.py
```

Generated output is not canonical source. Temporary evidence is not durable documentation. Document presence is not authority.
