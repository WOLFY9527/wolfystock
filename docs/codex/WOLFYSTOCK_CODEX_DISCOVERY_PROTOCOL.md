# WolfyStock Codex Discovery Protocol

Purpose: let future task prompts stay short and cache-friendly while preserving enough repo discovery discipline to make safe edits.

Use this protocol when the prompt gives only:

- `Surface`
- `Change type`
- `Goal`
- `Contract delta`
- `Validation profile`

Do not duplicate global execution or guard rules here. Follow the linked docs for policy details.

Related docs:

- `docs/codex/WOLFYSTOCK_SURFACE_MAP.md`
- `docs/codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md`
- `docs/codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md`
- `docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`
- `docs/codex/NO_ADVICE_REGRESSION_GUARDS.md`

## Compact Prompt Contract

Future prompts can usually stop at:

```text
Surface:
Change type:
Goal:
Contract delta:
Validation profile:
Commit:
```

Optional only when needed:

- `Risk domain`
- `Allowed final diff`
- `Forbidden final diff`
- route/viewport proof for frontend work

## Discovery Order

1. Start from `docs/codex/WOLFYSTOCK_SURFACE_MAP.md`.
2. Resolve the named surface to the likely backend endpoint, schema, service, tests, frontend client, page/component, and frontend tests.
3. Read the task delta and classify it:
   - copy/layout-only
   - frontend client/view-model
   - backend service/endpoint
   - additive contract
   - protected-domain or boundary-adjacent
4. Inspect existing tests before changing fixtures or helpers.
5. Inspect existing endpoint/schema/service/client/page patterns before adding abstractions.
6. Prefer the smallest existing chain that already owns the surface:
   - backend: endpoint -> schema -> service -> focused tests
   - frontend: API client -> page/component -> focused tests
7. Pull validation from `docs/codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md` using the named `Validation profile`.

## Required Inspection Rules

### Tests before fixtures

- Inspect existing tests before editing fixtures, builders, or mocked payloads.
- If the current change looks like “fixture update only,” verify there is no existing higher-level test already locking the intended behavior.

### Pattern before abstraction

Before adding a helper, DTO, hook, adapter, or wrapper:

- inspect the current endpoint pattern
- inspect the current schema pattern
- inspect the current service pattern
- inspect the current frontend client pattern
- inspect the current page/component pattern

If an existing local pattern already solves the task, extend it instead of creating a parallel abstraction.

### Frontend worktree dependency rule

For frontend worktrees only:

- if `apps/dsa-web/node_modules` is missing, symlink it from the main repo copy
- never run with a committed `node_modules`
- never commit the symlink target contents

Preferred local command shape:

```bash
ln -s <main-repo>/apps/dsa-web/node_modules apps/dsa-web/node_modules
```

If the main repo in this environment is `/Users/yehengli/daily_stock_analysis`, that path is the expected source. Only do this when the link is absent and the selected workspace is a frontend-capable worktree.

### Auth route inventory rule

If the task hits auth route inventory, capability inventory, or fixture mismatches around route protection:

- read `tests/test_auth_route_capability_inventory.py` before modifying fixtures
- do not “fix” the inventory by weakening route capability assertions first

## Conflict And Rebase Rules

- Stop on any non-`docs/CHANGELOG.md` rebase conflict.
- Only auto-resolve `docs/CHANGELOG.md` conflicts when it is the sole conflict.
- For that sole changelog conflict, keep both sides.
- Do not auto-resolve application, test, schema, route, or codex-doc conflicts by guesswork.

## Boundary Guards

Do not restate boundary policy from scratch in task prompts or local notes. Route to the durable guard docs instead:

- backend protected domains: `docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`
- no-advice wording and consumer-safe copy: `docs/codex/NO_ADVICE_REGRESSION_GUARDS.md`
- execution/runtime rules: `docs/codex/WOLFYSTOCK_CODEX_EXECUTION_POLICY.md`
- validation sizing and stop conditions: `docs/codex/WOLFYSTOCK_CODEX_VALIDATION_MATRIX.md`

When the surface is consumer-visible, preserve no-advice and consumer/admin boundaries unless the task explicitly says otherwise.

## Surface-Specific Hints

- `Daily Intelligence` and `Market Decision Cockpit` usually move together; inspect both when the prompt mentions briefing, queue preview, or regime framing.
- `Market Overview / Briefing` often spans `market.ts`, `marketOverview.ts`, and the `temperature` plus `market-briefing` backend paths.
- `Scanner Research Overlay` and `Watchlist Research Overlay` are overlay/read-model tasks; inspect overlay endpoints before legacy list/detail routes.
- `Portfolio Structure Review` is not the same as `scenario-risk`; inspect `/structure-review` first for structure tasks.
- `Scenario Lab` currently has a backend contract but a frontend placeholder page in this branch; do not assume the page is already wired to the endpoint.
- `Options / Gamma Observation` must preserve observation-only posture; inspect readiness, no-advice, and gamma observation tests before touching DTOs or UI summaries.

## Output Expectation

After discovery, the task should be able to proceed with a compact prompt because the stable navigation lives in repo docs, not in repeated prompt boilerplate.
