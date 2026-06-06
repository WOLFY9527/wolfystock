# WFE-001 Options Lab 1440 responsive sanity audit

Task ID: WFE-001-AUDIT

Task title: Options Lab 1440 responsive sanity audit

Mode: READ-ONLY-AUDIT

Allowed artifact: `docs/codex/audits/WFE-001-optionslab-1440-responsive-sanity-audit.md`

Observed workspace:

- cwd: `C:/Users/leeyi/worktrees/wfe-001-optionslab-responsive-audit`
- branch: `codex/wfe-001-optionslab-responsive-audit`
- base commit inspected: `2937600c5197586ac6cae1103a13123fb20244cc`
- URL: `http://127.0.0.1:8000`

## Verdict

The reported `/zh/options-lab` 1440px narrow-width anomaly is tooling/runtime noise, not a real responsive layout issue in the current main state.

Fresh authenticated browser measurements at `1440x900` and `1440x1000` both rendered the Options Lab desktop surface with:

- `documentElement.clientWidth=1440`
- `documentElement.scrollWidth=1440`
- `main.shell-main-column` width `1382.4px`
- Options Lab page root width `1295.6px`
- Options Lab bento grid width `1239.6px`
- desktop option-chain tables visible
- no mobile cards/lists visible on desktop
- no horizontal overflow
- no console errors

The previous `~336px` main-width observation was not reproduced. A separate unauthenticated pass also showed the protected/auth gate at `1440px` using the normal `1382.4px` shell lane, so the specific `~336px` value is not explained by the current auth gate either. The most likely explanation is stale/delayed browser tooling, a measurement taken before the authenticated route settled, or a transient tool viewport/state mismatch.

Recommendation: no source work for Options Lab responsive layout.

## Method

- Built the current Web frontend once with `cd apps/dsa-web && npm run build` so FastAPI could serve the current static app from `http://127.0.0.1:8000`.
- Started local FastAPI on `127.0.0.1:8000` for the audit.
- Initial API login with the supplied credentials returned `400 auth_disabled` because the local runtime started with `authEnabled=false` and no stored password.
- Recorded an unauthenticated/protected-route pass to check whether the auth gate itself caused narrow width.
- Enabled the local bootstrap auth state with the supplied password only to create an authenticated browser session for measuring the real consumer route.
- Used fresh Playwright Chromium contexts per route/viewport.
- Compared `/zh/options-lab` with known-good consumer route `/zh/market-overview`.
- No screenshots, source edits, test/config edits, route/auth code edits, or generated assets are included in the final diff.

Runtime note: local `.env`, `data/`, `logs/`, `output/`, and `static/` files were generated/used only as ignored local runtime artifacts for serving and measuring the app. They are not part of the final diff.

## Auth Gate Check

Before authenticated measurement, `/api/v1/auth/status` reported:

- `authEnabled=false`
- `loggedIn=false`
- `passwordSet=false`
- `setupState=no_password`
- transitional bootstrap admin user available

With that state, direct login returned `400 auth_disabled`. The protected route still did not reproduce a narrow 1440px shell:

| Route | Viewport | Login status | Rendered state | Document client/scroll | Main width | Stuck narrow | Console errors |
| --- | --- | ---: | --- | --- | ---: | --- | ---: |
| `/zh/options-lab` | 1440x900 | 400 | auth gate | 1440 / 1440 | 1382.4 | no | 0 |
| `/zh/options-lab` | 1440x1000 | 400 | auth gate | 1440 / 1440 | 1382.4 | no | 0 |
| `/zh/options-lab` | 1920x1080 | 400 | auth gate | 1920 / 1920 | 1850.0 | no | 0 |
| `/zh/options-lab` | 390x844 | 400 | auth gate | 390 / 390 | 365.1 | no | 0 |

This confirms that the protected/auth overlay was present in the initial local state, but it did not create the previously reported `~336px` desktop measurement.

## Authenticated Measurement Table

| Route | Viewport | Login status | Document client/scroll | Main width | Page/root width | Visible content width | Shell mode | Desktop vs mobile content | Auth/loading overlay | Console errors |
| --- | --- | ---: | --- | ---: | ---: | ---: | --- | --- | --- | ---: |
| `/zh/options-lab` | 1440x900 | 200 | 1440 / 1440 | 1382.4 | 1295.6 | 1440.0 | desktop | 2 desktop tables, 0 mobile cards | no auth gate; settled content text includes demo/loading wording | 0 |
| `/zh/options-lab` | 1440x1000 | 200 | 1440 / 1440 | 1382.4 | 1295.6 | 1440.0 | desktop | 2 desktop tables, 0 mobile cards | no auth gate; settled content text includes demo/loading wording | 0 |
| `/zh/options-lab` | 1920x1080 | 200 | 1920 / 1920 | 1850.0 | 1763.2 | 1920.0 | desktop | 2 desktop tables, 0 mobile cards | no auth gate; settled content text includes demo/loading wording | 0 |
| `/zh/options-lab` | 390x844 | 200 | 390 / 390 | 365.1 | 320.3 | 390.0 | mobile | 0 desktop tables, 5 mobile cards, 2 mobile lists | no auth gate; settled content text includes demo/loading wording | 0 |
| `/zh/market-overview` | 1440x900 | 200 | 1440 / 1440 | 1382.4 | 1239.6 | 1440.0 | desktop | consumer desktop layout | no auth gate; fallback evidence text present | 0 |
| `/zh/market-overview` | 1440x1000 | 200 | 1440 / 1440 | 1382.4 | 1239.6 | 1440.0 | desktop | consumer desktop layout | no auth gate; fallback evidence text present | 0 |
| `/zh/market-overview` | 1920x1080 | 200 | 1920 / 1920 | 1850.0 | 1693.2 | 1920.0 | desktop | consumer desktop layout | no auth gate; fallback evidence text present | 0 |
| `/zh/market-overview` | 390x844 | 200 | 390 / 390 | 365.1 | 292.3 | 390.0 | mobile | consumer mobile layout | no auth gate; fallback evidence text present | 0 |

`loadingText=true` in the raw script output came from legitimate settled page copy such as `演示数据 · 实时链未启用`, `等待数据确认`, and fallback/readiness language, not a blocking loading overlay. The DOM had page content, desktop tables, and route-specific data visible during measurement.

## Comparison And Interpretation

Options Lab and Market Overview share the same desktop shell lane at 1440px:

- `/zh/options-lab`: main width `1382.4px`
- `/zh/market-overview`: main width `1382.4px`

Options Lab's inner page root is slightly wider than Market Overview at 1440px:

- `/zh/options-lab`: page/root width `1295.6px`
- `/zh/market-overview`: page/root width `1239.6px`

That difference is expected route-local content framing, not a breakpoint collapse. The important signals are consistent:

- desktop shell mode at 1440px
- desktop option-chain tables visible at 1440px
- no mobile cards/lists visible at 1440px
- no horizontal overflow
- no console errors
- no auth overlay after successful login

## Decision

Stop. Do not open a source-write task for Options Lab 1440 responsive layout.

If a future report reproduces a narrow desktop measurement, the next task should be another read-only browser evidence pass first, not a layout fix. That pass should capture:

- raw `window.innerWidth`
- `documentElement.clientWidth`
- `main.shell-main-column.getBoundingClientRect()`
- current route and auth status
- whether `data-layout` is `mobile` or `desktop`
- whether the route is still on the protected/auth gate
- console errors and chunk load status

No future source fix is recommended from this audit.

## Validation

Planned validation for this audit branch:

- `git diff --check`
- `G:\Git\bin\sh.exe ./scripts/release_secret_scan.sh`

Final delivery should confirm the final diff is docs-only.
