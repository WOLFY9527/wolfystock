# Home / Research Workspace — Visual System Pass (Pass 2)

**Date**: 2026-06-11
**Branch**: `claude/ui-redesign-v1`
**Scope**: Authenticated Home / research-workspace surface (`/`), desktop 1440 + mobile 390.
**Status**: Uncommitted. Frontend-only. No backend / behavior changes.

---

## 1. Key finding that shaped this pass

The authenticated home (`/`) is rendered by `HomeBentoDashboardPage.tsx`. Its layout is
**contract-frozen** by `src/pages/__tests__/HomeSurfacePage.test.tsx` (4,691 lines, 82 tests):
data-testids, layout zones, exact radii (`rounded-[10px]/[12px]/[14px]`), card counts
(≤6 research cards: 2 in PrimaryWorkRegion, 4 in ContextRail), and structure are all pinned.

Critically, the test **`keeps the Linear-style Home shell when there is no non-test history`**
mocks empty history, renders authenticated, and asserts the **full research console renders with
neutral `-` placeholders** — and explicitly forbids any zero-state/landing
(`home-bento-zero-state`, “待分析”, “等待输入” are all asserted absent).

➡️ The team has already decided the empty/first-run authenticated home **is** the console with
placeholders, not a separate landing page. A structural redesign (new landing, re-laid-out grid,
market module inside the console) would break this explicit contract, which the session
constraints forbid. So this pass is a **visual-system refinement within the frozen structure**.

The good news: the actual *rendered appearance* is driven by CSS in `index.css`
(`html[data-theme='spacex'] [data-testid='home-bento-dashboard'] …`), which the tests do **not**
assert (they check class/structure presence, not computed styles). That CSS is where the premium
gains were made.

## 2. What changed (all in `apps/dsa-web/src/index.css`, home-scoped)

- **Deeper, flatter canvas** behind the console so elevated panels read as crisp surfaces instead
  of muddy slabs on near-equal ground.
- **One surface vocabulary** across every panel (header / conclusion console / key-levels / chart
  workspace / events deck / rail cards): same radius (`--wolfy-radius-md`), hairline border, lift
  gradient, and elevation. Previously the conclusion console used a warmer greenish gradient while
  the rest were cool-blue — that mismatch was a big “scattered” contributor.
- **Consistent 12px vertical rhythm** between stacked primary-column panels (was 10/16/12px).
- **Clean header separation** — the header strip was flush-connected (flat bottom radius) to a
  fully-rounded card below it, reading as a broken seam; now a clean rounded card with a gap.
- **Calmer focal verdict** — the conclusion stance (e.g. “仅观察” / “待补充数据”) dropped from a 42px
  slab to a `clamp(30–36px)` premium scale; still the clear focal point, no longer dominating the
  empty state.
- **Command bar as the primary action** — more presence (52–54px) + a focus accent ring so
  “enter a ticker → 分析” reads as the main entry point.
- **Deliberate mobile (≤640px)** — proportional brand mark (54px vs 72px), comfortable panel
  insets, tighter rail rhythm, prominent command bar.

## 3. What intentionally stayed unchanged

- Console structure, all `data-testid`s, layout zones, copy, and the empty-state-as-console
  behavior (contract-frozen).
- The single canonical shell width/gutter vars (`--wolfy-consumer-shell-*`) — already unified and
  shared; not forked (narrowing globally would regress dense pages like Market Overview / Scanner).
- Other surfaces (Market Overview, Scanner, Portfolio, etc.) — all CSS here is home-scoped.
- Login/Register + primary-button improvements from Pass 1 (kept).

## 4. Validation

`npm run typecheck` ✓ · `npm run lint` ✓ · `npm run check:design` ✓ (0 violations) ·
`npm run build` ✓ · HomeSurfacePage suite **82/82** ✓ · Market Overview regression screenshot
unchanged.

Screenshot harness: `apps/dsa-web/_homeshot.mjs` (mocks auth + candles; no live backend).
Before/after montages: `/tmp/dsa-shots/compare/`.

## 5. Recommended next step for a *structural* redesign

If the product wants the deeper restructure (e.g. a true first-run workspace landing, an in-console
market/context module, a re-balanced grid), it requires **deliberately revising the
`HomeSurfacePage.test.tsx` contract** with product sign-off — a separate, clearly-scoped task.
That is the only way to legitimately move past the “console renders even when empty” lock.
