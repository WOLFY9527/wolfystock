# WolfyStock Archive And Historical Evidence Index

Status: canonical archive navigation map.

Archived docs preserve provenance only. They are not current launch, frontend,
provider, security, portfolio, backtest, API, product-readiness, or Codex
workflow authority unless a current active doc explicitly re-promotes a specific
archived item for a specific question.

Start current work from:

- [Docs Index](./DOCS_INDEX.md)
- [AI Project Manual](./AI_PROJECT_MANUAL.md)
- [System Handbook](./WOLFYSTOCK_SYSTEM_HANDBOOK.md)
- [AI Maintenance Manual](./WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md)
- [File Governance Taxonomy](./architecture/file-governance-taxonomy.md)

## Central Archive Locations

| Location | Contents | Use |
| --- | --- | --- |
| `docs/archive/audits/` | Retired audit notes, consolidation plans, old launch/security/admin findings, and goal-progress notes | Historical audit provenance only |
| `docs/archive/audits/frontend/` | Retired frontend DOM, CSS, bundle, scroll, and launch UX reports | Historical UI evidence only |
| `docs/archive/architecture/` | Older backend/frontend audits, multi-user foundation notes, Phase F evidence, and archived implementation plans | Historical architecture provenance only |
| `docs/archive/codex/audits/` | Retired Codex task reports, readiness audits, and old Codex audit archive contents | Historical Codex task provenance only |
| `docs/archive/codex/goals/` | Retired Codex goal-progress notes | Historical planning provenance only |
| `docs/archive/design/` | Legacy imported design assets that are no longer current UI authority | Historical design reference only |
| `docs/archive/frontend/` | Retired frontend route, CSS, visual constitution, and UI replacement evidence | Historical frontend provenance only |
| `docs/archive/product-audit/` | Retired product QA and wording sweep reports | Historical product-audit provenance only |
| `docs/archive/product-recovery/` | Superseded root-cause and recovery notes | Historical product-recovery provenance only |
| `docs/archive/product-recovery/acceptance/` | DATA-011, DATA-016, and DATA-021 point-in-time acceptance snapshots | Historical acceptance evidence only |
| `docs/archive/qa/` | Point-in-time QA reports | Historical QA provenance only |

## Important Archive Notes

- `docs/archive/codex/audits/retired/` contains formerly active Codex task
  reports that DOCS-005 moved out of `docs/codex/` so that directory now holds
  durable workflow, prompt, validation, and protected-domain references only.
- `docs/archive/product-recovery/acceptance/` contains acceptance snapshots
  whose durable conclusions are now represented by the generated AI manual and
  active product-recovery contracts.
- `docs/archive/design/DESIGN.md` is the legacy imported design asset. Current
  frontend authority is `docs/frontend/README.md`,
  `docs/frontend/visual-system.md`, `docs/frontend/validation-playbook.md`, and
  `docs/design/reference/wolfystock-reflect-linear-home-mockup.png`.
- Bilingual public docs, root `SKILL.md`, GitHub templates, and agent mirror
  files are not archive material merely because they are duplicate-ish; keep
  them active when external tools or public links still depend on their paths.

## How To Use Historical Evidence

Use archive docs to answer:

- why a decision was made;
- which risks were already found;
- which paths were consolidated before;
- which validation commands existed at that time;
- what not to repeat in future cleanup tasks.

Do not use archive docs to claim:

- current launch readiness;
- current route acceptance;
- current API shape;
- current provider entitlement or freshness;
- current security/RBAC behavior;
- current portfolio/backtest accounting safety;
- current browser/UI acceptance.

For current claims, inspect current code, tests, active docs, and fresh
validation output.

## Local Artifacts Are Not Archive Authority

The following local or ignored paths are not repository archive authority:

- `.claude/reviews/`
- `.codex/`
- `.codex-artifacts/`
- `reports/`
- `test-results/`
- `playwright-report/`
- `coverage/`
- `repo_archive/`
- `repo_trash/`

Do not cite them as current truth in PRs or final reports unless a task
explicitly asks for a local report artifact and the artifact is clearly labeled
as local evidence.

## Archive Or Delete Rule

Before moving or deleting tracked docs:

1. confirm the current source-of-truth replacement;
2. search current references by full path and basename;
3. update active indexes and current docs;
4. run docs validation;
5. report what moved and why;
6. keep launch and protected-domain authority unchanged unless explicitly
   scoped.

Archive when a document has historical value, prior evidence, risk context, or
review provenance but is no longer current authority. Delete only when the file
is generated, duplicate, unreferenced, and has no historical value.
