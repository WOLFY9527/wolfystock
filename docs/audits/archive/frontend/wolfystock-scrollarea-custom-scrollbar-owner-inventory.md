# WolfyStock ScrollArea / `custom-scrollbar` Owner Inventory

Date: 2026-05-05 Asia/Shanghai  
Repository: `/Users/yehengli/daily_stock_analysis`  
Branch: `main`  
Mode: read-only owner inventory plus one docs artifact; no product code, tests, CSS, backend/API, package/config, script, runtime, generated artifact, or `docs/CHANGELOG.md` edits by this task

## 1. Executive summary

Owner verdict: **shared-component scoped owner**.

`custom-scrollbar` is defined in `apps/dsa-web/src/index.css` and source-owned by `apps/dsa-web/src/components/common/ScrollArea.tsx`. The shared `ScrollArea` viewport applies `overflow-y-auto overscroll-contain custom-scrollbar no-scrollbar [-webkit-overflow-scrolling:touch]`.

Direct production `custom-scrollbar` usage is limited to `ScrollArea.tsx`; no route/page/component production consumer currently imports or renders `ScrollArea` outside the component itself. The only `<ScrollArea>` render found in source is `apps/dsa-web/src/components/common/__tests__/ScrollArea.test.tsx`.

Rendered route evidence was **not collected** for this inventory because static investigation found no production route consumers worth proving. Prior route matrices reported `.custom-scrollbar=0` in default and corrected target route states, but this report treats those as supporting context, not fresh rendered proof.

Deletion/change recommendation: **do not delete or change `custom-scrollbar` now**. It is not an orphan while `ScrollArea` remains exported and tested. Any future change requires a deliberate `ScrollArea` owner migration, consumer search through direct and barrel imports, and route/component proof that default scrollbars remain hidden.

## 2. Methodology

Required preflight was run first:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -150
./scripts/task_preflight.sh || true
```

Preflight result:

- `pwd`: `/Users/yehengli/daily_stock_analysis`
- branch: `main`
- upstream: `origin/main`, ahead 0 / behind 0
- initial dirty files: 0
- `task_preflight.sh`: PASS; dirty files 0

Mandatory reading completed:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `docs/audits/archive/frontend/wolfystock-scrollbar-dom-verification.md`
- `docs/audits/archive/frontend/wolfystock-corrected-scroll-proof.md`
- `docs/design/wolfystock-canonical-ui-primitives.md`
- `docs/checks/css-visual-regression-checklist.md`
- `docs/operations/parallel-codex-playbook.md`

Static investigation:

```bash
cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
rg -n "custom-scrollbar|ScrollArea|<ScrollArea|from ['\"].*ScrollArea|no-scrollbar|overflow-y-auto|overflow-auto|scrollbar" src/index.css src/pages src/components src/hooks src/utils src/__tests__ | head -1000
```

Additional focused inspections:

- `apps/dsa-web/src/components/common/ScrollArea.tsx`
- `apps/dsa-web/src/components/common/__tests__/ScrollArea.test.tsx`
- `apps/dsa-web/src/components/common/index.ts`
- `apps/dsa-web/src/index.css`
- package scripts in `apps/dsa-web/package.json`
- direct source searches for `ScrollArea`, `<ScrollArea>`, direct `custom-scrollbar`, and common barrel imports

Limitations:

- This is a source owner inventory, not a fresh route-level browser matrix.
- Optional Playwright was not used because no production route `ScrollArea` consumer was found.
- After preflight and before writing, `apps/dsa-web/src/index.css` became dirty from a parallel CSS deletion task. The diff removes `stealth-scrollbar` selector prefixes from the scrollbar block and leaves `custom-scrollbar` intact. This task did not edit, stage, or revert that CSS.
- Current CSS line numbers in this report reflect the inspected working tree after the unrelated parallel CSS diff. Historical prior reports should be consulted for pre-deletion `stealth-scrollbar` pairing context.

## 3. Static baseline

| Check | Result | Key output |
| --- | --- | --- |
| `pwd` | PASS | `/Users/yehengli/daily_stock_analysis` |
| Branch | PASS | `main` |
| Initial preflight | PASS | clean worktree; `origin/main` ahead 0 / behind 0 |
| Required source search | PASS | `custom-scrollbar` found in `src/index.css`, `ScrollArea.tsx`, `ScrollArea.test.tsx`; no production route consumer found |
| `npm run check:design` | PASS | 216 files scanned; 0 blocking violations; 0 warnings |
| `npm run lint` | PASS | `eslint .` exited 0 |
| `npm run build` | PASS with warning | 3160 modules transformed; Vite chunk-size warning for `DeterministicBacktestChartWorkspace-CZBkWH9y.js` at 532.42 kB |
| `npm run test -- ScrollArea` | PASS | 1 test file passed; 1 test passed |
| `python3 -m compileall -q src api` | PASS | exited 0 with no output |
| Markdown lint | Not run | no markdown lint script found in `apps/dsa-web/package.json`; only app `lint` is `eslint .` |
| `./scripts/ci_gate.sh` | Not run | docs-only report task; frontend gates, focused component test, and Python compile baseline passed |

## 4. CSS definition evidence

Exact selector locations in the inspected working tree:

| Selector | File location | Behavior |
| --- | --- | --- |
| `.no-scrollbar::-webkit-scrollbar` | `apps/dsa-web/src/index.css:5` | hides WebKit scrollbar with `display: none`, zero width/height, transparent background |
| `.no-scrollbar` | `apps/dsa-web/src/index.css:12` | hides IE/Edge legacy scrollbar style and Firefox scrollbar width |
| global `*` scrollbar rule | `apps/dsa-web/src/index.css:5875` | sets transparent scrollbar color and `scrollbar-width: none` globally |
| `.custom-scrollbar` | `apps/dsa-web/src/index.css:5880` | hides Firefox scrollbar and sets transparent scrollbar color |
| `.custom-scrollbar::-webkit-scrollbar` | `apps/dsa-web/src/index.css:5885` | hides WebKit scrollbar with `display: none`, zero width/height, transparent background |
| `.custom-scrollbar::-webkit-scrollbar-thumb` | `apps/dsa-web/src/index.css:5892` | defines a muted rounded thumb style, currently not visible because the WebKit scrollbar is hidden |
| `.custom-scrollbar::-webkit-scrollbar-track` | `apps/dsa-web/src/index.css:5899` | transparent track |

Relationship between `custom-scrollbar` and `no-scrollbar`:

- `no-scrollbar` is a broad utility with active route/local usage across pages and components.
- `custom-scrollbar` is a shared component utility currently paired with `no-scrollbar` inside `ScrollArea`.
- `ScrollArea` relies on both classes on the same viewport. `no-scrollbar` provides canonical hidden-scrollbar behavior; `custom-scrollbar` provides the component-scoped selector hook and legacy/custom scrollbar styling block.
- The current inspected CSS has a parallel dirty diff that removes `stealth-scrollbar` from the same block, but it does not remove `custom-scrollbar`.

Theme/visual behavior:

- The active behavior is hidden scrollbars, not visible custom scrollbar chrome.
- `custom-scrollbar` and `no-scrollbar` both preserve scrollability while hiding native scrollbar affordances.
- Future visible scrollbar styling would need explicit design approval because the frontend constitution requires scrollable containers to avoid native scrollbar exposure.

## 5. Source owner evidence

| File | Usage type | Route/surface | Risk | Notes |
| --- | --- | --- | --- | --- |
| `apps/dsa-web/src/index.css` | definition | global CSS utilities | High | Defines `custom-scrollbar` selectors and broad scrollbar behavior. Shared CSS cascade must not be changed from static search alone. |
| `apps/dsa-web/src/index.css` | definition | global CSS utilities | High | Defines `no-scrollbar`, which is actively used across routes/components and paired with `custom-scrollbar` in `ScrollArea`. |
| `apps/dsa-web/src/components/common/ScrollArea.tsx` | direct class / shared component owner | common component | High | The viewport class includes `overflow-y-auto overscroll-contain custom-scrollbar no-scrollbar [-webkit-overflow-scrolling:touch]`. This is the direct source owner. |
| `apps/dsa-web/src/components/common/index.ts` | export | common component barrel | Medium | Re-exports `ScrollArea`, so future searches must include direct imports from `../components/common`, `../common`, and the barrel. |
| `apps/dsa-web/src/components/common/__tests__/ScrollArea.test.tsx` | test | common component | Medium | Renders `<ScrollArea>` and verifies custom outer/viewport classes, but does not currently assert `custom-scrollbar` or `no-scrollbar`. |
| `apps/dsa-web/src/pages/*` | no direct usage found | routes | Medium | Required source search found no production route `custom-scrollbar` usage and no route `ScrollArea` consumer. |
| `apps/dsa-web/src/components/*` | no direct usage found outside `ScrollArea` | shared/domain components | Medium | Required source search found no production component `ScrollArea` consumer outside the owner component itself. |

Direct `custom-scrollbar` source files:

- `apps/dsa-web/src/index.css`
- `apps/dsa-web/src/components/common/ScrollArea.tsx`

Direct `ScrollArea` source files:

- `apps/dsa-web/src/components/common/ScrollArea.tsx`
- `apps/dsa-web/src/components/common/index.ts`
- `apps/dsa-web/src/components/common/__tests__/ScrollArea.test.tsx`

No direct production route/component `<ScrollArea>` consumers were found in `apps/dsa-web/src/pages`, `apps/dsa-web/src/components`, `apps/dsa-web/src/hooks`, or `apps/dsa-web/src/utils`.

## 6. Rendered evidence

Fresh rendered route evidence was not collected in this task.

| Route | Viewport | `.custom-scrollbar` | `.no-scrollbar` | Scroll container notes |
| --- | --- | ---: | ---: | --- |
| Not collected | Not collected | Not collected | Not collected | Static source search found no production route `ScrollArea` consumer, so optional Playwright route proof was not run. |

Supporting prior-report context:

- `docs/audits/archive/frontend/wolfystock-scrollbar-dom-verification.md` reported `.custom-scrollbar=0` across its default route matrix.
- `docs/audits/archive/frontend/wolfystock-corrected-scroll-proof.md` reported `.custom-scrollbar=0` for corrected Scanner, Portfolio, and Market Overview states.
- Those reports are useful context, but this inventory does not rely on them as fresh evidence for a new route matrix.

## 7. Ownership verdict

Classification: **shared-component scoped owner**.

Reasoning:

- Not an active route owner: no production route emits `custom-scrollbar` through source usage found in this audit.
- Not an unused orphan: `custom-scrollbar` is directly referenced by the exported `ScrollArea` common component, and `ScrollArea` has a unit test.
- Not fully active in rendered route states based on available evidence: prior rendered matrices saw zero hits, and this task found no route consumer.
- Therefore, `custom-scrollbar` is best classified as a **shared-component scoped owner with currently unproven route emission**.

Deletion status: **not safe now**.

The selector must remain protected in future CSS prompts because deleting it would silently alter an exported shared component before proving whether the component is intentionally unused, deprecated, or waiting for future reuse.

## 8. Future action

Before any future `custom-scrollbar` change or deletion:

1. Decide whether `ScrollArea` remains a supported common primitive.
2. If keeping `ScrollArea`, preserve `custom-scrollbar` or migrate the viewport to a named replacement utility with equivalent hidden-scrollbar behavior.
3. If removing `ScrollArea`, first prove no production imports exist through direct paths or the common barrel, then remove or update the unit test in the same scoped task.
4. Run source searches for `custom-scrollbar`, `ScrollArea`, `<ScrollArea`, and common barrel imports.
5. Run a rendered route matrix only if production consumers exist, using desktop `1440x1000` and mobile `390x844`.
6. Verify default scrollbars are not exposed and local scrolling still works.
7. Run `npm run check:design`, relevant component/page tests, `npm run lint`, `npm run build`, and `git diff --check`.

Required tests/routes before any change:

- `apps/dsa-web/src/components/common/__tests__/ScrollArea.test.tsx`
- Any route/page/component tests for newly discovered `ScrollArea` consumers
- Route-level Playwright/browser proof for every discovered production consumer state
- At minimum, inspect the canonical route matrix from `docs/checks/css-visual-regression-checklist.md` if the change touches global CSS

Protection recommendation:

- Keep `custom-scrollbar` protected in future CSS deletion prompts.
- Treat it as coupled to `ScrollArea` ownership, not as an independent dead selector.
- Do not combine a `custom-scrollbar` change with unrelated `stealth-scrollbar`, `no-scrollbar`, shell, card, or route redesign work.

## 9. Non-goals

- No CSS changed.
- No product code changed.
- No tests changed.
- No backend/API changed.
- No package/config changed.
- No scripts changed.
- No `docs/CHANGELOG.md` changed.
- No generated artifacts committed.
- No route/browser proof claimed.
- No deletion or migration performed.

## 10. Appendix

Command output summary:

```text
pwd
/Users/yehengli/daily_stock_analysis

git branch --show-current
main

git status --short
<no output at preflight>

git status --branch --short
## main...origin/main

./scripts/task_preflight.sh || true
PASS; branch main; upstream origin/main ahead 0 / behind 0; dirty files 0

Required rg search
Found custom-scrollbar definitions in src/index.css and ScrollArea.tsx.
Found ScrollArea export and ScrollArea unit test.
Found no production route/component ScrollArea consumer outside the owner component.

npm run check:design
PASS; 216 files scanned; no blocking violations or warnings.

npm run lint
PASS; eslint exited 0.

npm run build
PASS with Vite chunk-size warning; DeterministicBacktestChartWorkspace-CZBkWH9y.js is 532.42 kB.

npm run test -- ScrollArea
PASS; 1 test file passed; 1 test passed.

python3 -m compileall -q src api
PASS; no output.

Markdown lint
Not run; no markdown lint script found in apps/dsa-web/package.json.

./scripts/ci_gate.sh
Not run; docs-only report task and targeted required checks passed.
```

Parallel dirty state observed after preflight:

```text
 M apps/dsa-web/src/index.css
```

Observed unrelated CSS diff:

```text
apps/dsa-web/src/index.css | 4 ----
```

The dirty CSS removes `stealth-scrollbar` selector prefixes from the scrollbar block and leaves `custom-scrollbar` intact. This task did not edit, stage, or commit that CSS.

Rollback for this report:

```bash
git revert <commit>
```
