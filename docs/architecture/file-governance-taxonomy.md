# WolfyStock File Governance Taxonomy

Status: active governance reference.

This taxonomy defines how repository files should be classified before humans
or AI agents edit, archive, delete, cite, or create new documents. It is a
navigation and maintenance contract only; executable code and CI workflows
remain the final authority when docs disagree with reality.

## Root File Ownership

| Root item | Owner lane | Rule |
| --- | --- | --- |
| `README.md` | Public entry point | High-level product, local run, validation, deployment, and current docs links only. Do not turn it into a deep module manual. |
| `AGENTS.md` | AI collaboration source of truth | Canonical repository rules for Codex, Claude compatibility, Copilot mirrors, and skill governance. |
| `CLAUDE.md` | Compatibility shim | Must remain a symlink to `AGENTS.md`. |
| `SKILL.md` | Product/external integration | Describes the stock analyzer skill behavior, not repository collaboration governance. |
| `DESIGN.md` | Legacy/imported design asset | Not current WolfyStock UI authority unless a current design index explicitly says so. |
| `.github/copilot-instructions.md` and `.github/instructions/*.instructions.md` | Agent mirrors | May summarize or layer `AGENTS.md`; conflicts resolve to `AGENTS.md`. |
| `.claude/skills/` | Tracked repository skills | Versioned collaboration assets aligned with `AGENTS.md`. |

## Documentation Authority Lanes

| Lane | Path | Current use |
| --- | --- | --- |
| Navigation | `docs/DOCS_INDEX.md`, `docs/ARCHIVE_INDEX.md` | Start here for current authority and historical evidence. |
| System operations | `docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md`, `docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md` | Human and AI maintenance entry layer. |
| Architecture | `docs/architecture/` | Current module, storage, source-of-truth, provider/scoring, and database design. |
| Current audits | `docs/audits/` | Current launch posture, domain indexes, safety policies, accepted support audits, and active runbooks. |
| Archived audits | `docs/audits/archive/`, `docs/architecture/archive/`, `docs/qa/archive/` | Provenance only. Do not treat archived reports as current authority. |
| Frontend design | `docs/codex/`, `docs/design/` | Current Reflect-Linear source of truth, route taxonomy, validation, and UI primitives. |
| Operations | `docs/operations/` | Runbooks, artifact cleanup policy, provider metadata, and operator procedures. |
| Product policy | `docs/product/` | Product-specific labels, export semantics, and user-facing policy. |
| Local/generated evidence | `.claude/reviews/`, `.codex/`, `.codex-artifacts/`, `reports/`, `artifacts/`, `test-results/`, `playwright-report/`, `backtest_outputs/` | Not repository authority; keep ignored unless a task explicitly asks for tracked summary docs. |

## Active Docs Versus Archive Docs

Active docs must state current operating authority, current source-of-truth
links, or current accepted runbook behavior. They should be short enough to
route readers to the right owner instead of restating every historical audit.

Archive docs preserve why a decision was made, which evidence existed at a
point in time, and which cleanup or launch risks were previously found. They
must not be used to claim current route acceptance, current launch readiness,
current provider behavior, current security posture, or current API shape
unless an active doc explicitly re-promotes that evidence.

## Audit Retention Rules

- Keep current launch-control docs active: `public-launch-readiness-master.md`,
  `public-launch-gap-register.md`, deployment readiness, blocker burn-down,
  and accepted operator evidence runbooks.
- Keep active domain indexes that route to current security/RBAC, DB/WS2,
  cost/quota/observability, and provider/data/options docs.
- Move point-in-time UI, DOM, CSS, bundle, QA, and route proof reports to an
  archive lane after a current handbook/index supersedes them.
- Keep historical audit archives linked from `docs/ARCHIVE_INDEX.md`; avoid
  listing every archived detail in `docs/audits/README.md`.
- If a stale report is still cited by an active checklist, keep it active only
  as narrowly labeled support evidence, not visual or launch authority.

## Frontend Design Source Of Truth

Current frontend visual authority is:

- `docs/codex/WOLFYSTOCK_LINEAR_OS_DESIGN_LANGUAGE.md`
- `docs/codex/WOLFYSTOCK_FRONTEND_SURFACE_USAGE.md`
- `docs/codex/WOLFYSTOCK_FRONTEND_ROUTE_TEMPLATES.md`
- `docs/codex/CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `docs/codex/WOLFYSTOCK_FRONTEND_VALIDATION_PLAYBOOK.md`
- `docs/design/WOLFYSTOCK_REFLECT_LINEAR_VISUAL_SPEC.md`
- `docs/design/wolfystock-canonical-ui-primitives.md`
- `docs/design/reference/wolfystock-reflect-linear-home-mockup.png`

Older deep-space, ghost-glass, OLED terminal, bento-first, card-first, or
generic Linear-only wording is historical unless one of the current docs above
keeps it intentionally. Future frontend tasks should start from the current
Reflect-Linear docs and inspect the live route/source before citing archived
screenshots or old DOM reports.

## Backend Architecture And Provider Lanes

Backend architecture docs belong in `docs/architecture/`. Keep source
confidence, provider capability, scoring, storage, and source-of-truth decisions
there or in a clearly linked current audit/runbook when the document is
operator-facing.

Provider and market-data runtime docs must keep these concepts separate:
provider order, live-call path, fallback behavior, freshness labels, source
confidence, circuit/quota state, scanner eligibility, backtest local-only
boundaries, and cache/SWR behavior. Do not move provider runtime truth into a
frontend design note or historical audit.

## Operations, Runbooks, Logs, And Cleanup

Operations docs live in `docs/operations/` unless a current launch or incident
audit must remain under `docs/audits/`. Logs, screenshots, browser traces,
Playwright reports, generated audit bundles, and local validator outputs are
generated artifacts, not active docs. Summarize durable findings in a tracked
runbook or audit only when the task explicitly asks for that.

Cleanup rules are governed by `docs/operations/ARTIFACT_CLEANUP_POLICY.md`.
Do not delete generated artifacts, source assets, fixtures, databases, caches,
or local reports during a docs-governance task unless the task explicitly names
the exact path and reason.

## Codex Workflow Docs Lane

Codex process docs live in `docs/codex/`. They describe task modes, branch and
worktree rules, final reports, compact prompts, protected domains, validation,
frontend visual evidence, and model routing. Do not add one-off worker reports
there. If a task needs a reusable Codex rule, update the smallest existing
process doc and link it from `docs/DOCS_INDEX.md` only when it becomes a
current starting point.

## Tracked Fixtures Versus Generated Artifacts

Tracked fixtures should be small, deterministic, and intentionally placed under
existing fixture or example paths. Generated artifacts belong in ignored paths:
`reports/`, `artifacts/`, `backtest_outputs/`, `test-results/`,
`playwright-report/`, `.codex/`, `.codex-artifacts/`, and local review output.
Do not reclassify generated evidence as a fixture to make it commit-friendly.

## Sources And Assets Governance

Do not move or delete `sources/` assets, design reference images, screenshots,
or binary files unless they are clearly stale tracked documentation assets and
the task explicitly scopes that cleanup. The Reflect-Linear mockup image is a
current design source and must remain at
`docs/design/reference/wolfystock-reflect-linear-home-mockup.png` unless a
future task updates every current reference.

## `.claude/skills` Versus `.agents` Policy

`AGENTS.md` is the single truth for repository AI collaboration. `.claude/skills/`
contains tracked repository skills aligned to that truth. `.agents/` is not a
tracked repository authority lane today. If a future task adds `.agents/skills/`
or another agent mirror, it must first define the single source of truth and
use scriptable mirroring or validation instead of hand-maintaining duplicate
instructions.

## Archive Versus Delete

Archive when a document has historical value, prior evidence, risk context, or
review provenance but is no longer current authority.

Delete only when all are true:

- the file is clearly generated, duplicate, or superseded;
- no active docs, scripts, tests, or indexes reference it;
- it is not a current design, product, architecture, runbook, or governance
  source;
- the final report lists the exact path and reason.

When unsure, archive instead of delete.

## How AI Agents Should Find The Right Current Document

1. Start with `docs/DOCS_INDEX.md`.
2. Read `docs/WOLFYSTOCK_SYSTEM_HANDBOOK.md` for ownership and protected
   domains.
3. Read `docs/WOLFYSTOCK_AI_MAINTENANCE_MANUAL.md` for worker rules and stale
   doc traps.
4. For frontend work, use the Reflect-Linear docs listed above before any
   archived UI reports.
5. For backend/API/provider/storage work, inspect current source/tests and the
   current architecture or audit index for the domain.
6. Use `docs/ARCHIVE_INDEX.md` only for provenance, not acceptance.
7. Before moving or deleting tracked docs, search both the full path and the
   basename, update active references, and run docs validation.
