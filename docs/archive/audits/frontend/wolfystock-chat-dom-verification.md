# WolfyStock Chat DOM Verification

Date: 2026-05-05 Asia/Shanghai  
Repository: `/Users/yehengli/daily_stock_analysis`  
Branch: `main`  
Mode: read-only Chat DOM verification; no product code, tests, CSS, backend/API, package, config, runtime, or changelog changes

## 1. Executive Summary

Chat DOM verification status: **PASS with corrected contract-faithful mocks**.

`/zh/chat` rendered full authenticated Chat content at desktop `1440x1000` and mobile `390x844` through an isolated frontend preview on `127.0.0.1:5176`. The rendered route included the Chat bento page, main workspace, main panel, persisted two-message conversation, composer/input shell, AI engine section, analysis lens section, data context section, and the responsive console surface. No real LLM/provider calls were made.

Key selector findings:

| Selector | Rendered result | Conclusion |
| --- | ---: | --- |
| `workspace-page--chat` | 0 desktop / 0 mobile | Absent from the Chat root and all ancestors checked. Future deletion-trial candidate, but not approved for deletion by this report. |
| `gemini-bento-page` | 1 desktop / 1 mobile | Active Chat owner primitive. Do not delete without owner migration. |
| `glass-card` | 0 / 0 | Still absent in corrected Chat DOM. |
| `terminal-card` | 0 / 0 | Still absent in corrected Chat DOM. |
| `dashboard-card` | 0 / 0 | Still absent in corrected Chat DOM. |
| `gradient-border-card` | 0 / 0 | Still absent in corrected Chat DOM. |
| `stealth-scrollbar` | 0 / 0 | Absent as a class; active Chat scroll containers use `no-scrollbar`. |
| `backtest-entry-shell` | 0 / 0 | Absent and not Chat-owned. |
| `product-command-card` | 0 / 0 | Absent in Chat DOM, but still high-risk outside Chat. |

What remains inconclusive: this was not a live authenticated user-data session. It proves corrected mocked Chat rendering and DOM class ownership, not production backend availability, real provider health, real chat persistence, or streaming behavior.

No CSS was deleted, no product code was changed, and no selector is approved for deletion directly by this audit.

## 2. Methodology

Commands run:

```bash
cd /Users/yehengli/daily_stock_analysis
pwd
git branch --show-current
git status --short
git status --branch --short
git log --oneline -120
./scripts/task_preflight.sh || true

cd /Users/yehengli/daily_stock_analysis/apps/dsa-web
rg -n "ChatPage|chat|问股|gemini-bento-page|workspace-page--chat|conversation|messages|lens|console|assistant|prompt|history|forEach|workspace" src/pages src/components src/api src/types src/__tests__ | head -500
rg -n "workspace-page--chat|gemini-bento-page|glass-card|terminal-card|dashboard-card|gradient-border-card|stealth-scrollbar|backtest-entry-shell|product-command-card" src/index.css src --glob '!index.css' | head -300
npm run check:design
npm run lint
npm run build

cd /Users/yehengli/daily_stock_analysis
python3 -m compileall -q src api
```

Mandatory reading completed:

- `CODEX_FRONTEND_DESIGN_CONSTITUTION.md`
- `docs/checks/css-visual-regression-checklist.md`
- `docs/audits/archive/frontend/wolfystock-css-cleanup-closure-report.md`
- `docs/audits/wolfystock-frontend-design-conformance-audit.md`
- `docs/design/wolfystock-canonical-ui-primitives.md`
- `docs/operations/parallel-codex-playbook.md`
- `docs/checks/design-guard.md`

Playwright method:

- Temporary script: `/tmp/wolfystock_chat_dom_verification.mjs`
- Temporary JSON result: `/tmp/wolfystock_chat_dom_verification_results.json`
- Browser: headless Chromium via local `apps/dsa-web` Playwright install
- Route: `http://127.0.0.1:5176/zh/chat`
- Viewports: desktop `1440x1000`, mobile `390x844`
- Auth/data mode: corrected contract-faithful mocks based on `ChatPage.test.tsx`
- Session mode: `localStorage.dsa_chat_session_id=session-1` so the route rendered persisted conversation messages
- Safety: stream and standard chat endpoints were aborted; no send action was triggered

Ports:

| Port | Status/use |
| --- | --- |
| `8000` | Existing Python backend listeners observed; not restarted or stopped. |
| `8001` | Free; not used. |
| `5173` | Existing Vite/Codex frontend listener observed; not touched. |
| `4173` | Free; not used. |
| `5174` | Free; not used. |
| `5175` | Free; not used. |
| `5176` | Free before task; started isolated `npm run preview`; used for Playwright; stopped after verification. |

Limitations:

- Live authenticated local browser/backend was not used; corrected mocks were safer for read-only DOM evidence and avoided real user-data mutation.
- Mock provider health and chat history prove route rendering shape, not actual provider connectivity.
- No external providers, real LLM calls, real chat sends, or user-data writes were triggered.
- Full `./scripts/ci_gate.sh` was not run because this was docs-only/report-only and the requested validation matrix did not require it.

## 3. Static Baseline

| Check | Result | Key output | Notes |
| --- | --- | --- | --- |
| `pwd` | PASS | `/Users/yehengli/daily_stock_analysis` | Required path. |
| Branch | PASS | `main` | Required branch. |
| Initial preflight | PASS | `origin/main`, ahead 0 / behind 0; dirty files 0 | No initial worktree conflict. |
| Port preflight | PASS | `8000` Python backend, `5173` node frontend; `8001`, `4173`, `5174`, `5175`, `5176` free | Existing servers were not touched. |
| `npm run check:design` | PASS | 216 files scanned; 0 blocking; 0 warnings | Design guard clean. |
| `npm run lint` | PASS | `eslint .` exited 0 | No lint output. |
| `npm run build` | PASS with warning | 3160 modules transformed; built in 9.71s | Vite warned that `DeterministicBacktestChartWorkspace-CqMcjVp7.js` is 532.42 kB after minification. |
| Backend compile | PASS | `python3 -m compileall -q src api` exited 0 | No output. |
| Markdown lint | Not available | `apps/dsa-web/package.json` has no markdown lint script | No markdown lint command was run. |
| `./scripts/ci_gate.sh` | Not run | Docs-only audit | Full CI was intentionally skipped for this report-only task. |

Parallel state note: after baseline/build, unrelated dirty files appeared in `apps/dsa-web/src/components/layout/PreviewShell.tsx`, `apps/dsa-web/src/components/report/ReportPriceChart.tsx`, `apps/dsa-web/src/components/report/StandardReportPanel.tsx`, `apps/dsa-web/src/index.css`, and `apps/dsa-web/src/pages/PreviewReportPage.tsx`. They were not touched, staged, or committed by this task. The dirty `index.css` limits claims about current parallel CSS deletion work, but not the captured corrected Chat DOM evidence.

## 4. Chat Source/Context Summary

Active Chat route classes and patterns from source:

| Owner | Evidence |
| --- | --- |
| Chat root | `ChatPage.tsx` renders `data-testid="chat-bento-page"` with `gemini-bento-page bento-surface-root gemini-bento-page--chat flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden bg-[#030303]`. |
| Chat workspace | `data-testid="chat-workspace"` uses `flex h-full min-h-0 w-full min-w-0 flex-1 overflow-hidden bg-transparent`. |
| Main shell/panel | `chat-main-shell` and `chat-main-panel` own the full-height Chat workspace split. |
| Message area | With persisted messages, `chat-main` uses `min-h-0 w-full flex-1 overflow-y-auto no-scrollbar`. |
| Console panel | `chat-strategy-panel` uses `hidden h-full min-h-0 w-full shrink-0 flex-col gap-5 overflow-y-auto border-l border-white/5 bg-gradient-to-b from-white/[0.01] to-transparent p-5 no-scrollbar lg:flex lg:w-[320px] xl:w-[360px]`. |
| Composer | `chat-composer-omnibar` uses `relative mx-auto w-full max-w-4xl rounded-3xl border border-white/[0.05] bg-white/[0.04] p-2 shadow-2xl backdrop-blur-2xl`. |
| Shell ancestors | `Shell.tsx` adds `shell-content-frame--chat`, `shell-main-column--chat`, and `theme-page-transition--chat` for `/chat`. |

Test fixture evidence:

- `ChatPage.test.tsx` provides contract shapes for skills, models, provider health, chat sessions, stock evidence, watchlist, portfolio snapshot, scanner recent watchlists, and backtest runs.
- `ChatPage.test.tsx` explicitly expects `chat-bento-page` not to have `workspace-page--chat`, route padding classes, `overflow-y-auto`, or `no-scrollbar` on the root.
- The corrected Playwright mocks reused those shapes and added `localStorage.dsa_chat_session_id=session-1` to force persisted conversation rendering.

Candidate selector source evidence:

| Selector | Source evidence |
| --- | --- |
| `workspace-page--chat` | CSS-only route modifier blocks in `src/index.css`; test-only negative assertion in `ChatPage.test.tsx`; no production TSX owner found. |
| `gemini-bento-page` | Active in `ChatPage.tsx` and shared home bento chrome. |
| `glass-card` | No non-CSS production source hit in the required search. |
| `terminal-card` | No non-CSS production source hit in the required search. |
| `dashboard-card` | No non-CSS production source hit in the required search. |
| `gradient-border-card` | No non-CSS production source hit in the required search. |
| `stealth-scrollbar` | CSS plus test-only negative references; Chat uses `no-scrollbar`, not `stealth-scrollbar`. |
| `backtest-entry-shell` | CSS plus Backtest `data-testid`, not a Chat class. |
| `product-command-card` | CSS-only in search, with prior ownership docs warning that it remains high-risk outside Chat. |

## 5. Rendered DOM Evidence

| Viewport | Mode | Route render status | Active Chat selector counts | Candidate selector hit counts | Overflow | Page/console errors | Raw/debug leakage | Notes |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- |
| `1440x1000` | corrected mock/authenticated | Full Chat rendered: bento page, workspace, main shell, main panel, 2 messages, composer, desktop console, engine/lens/data sections | `gemini-bento-page=1`; substring `chat=4`, `bento=1`, `gemini=1` | `workspace-page--chat=0`, `glass-card=0`, `terminal-card=0`, `dashboard-card=0`, `gradient-border-card=0`, `stealth-scrollbar=0`, `backtest-entry-shell=0`, `product-command-card=0` | 0 | 0 page; 0 console | None detected by text scan | Ancestors included `theme-page-transition--chat`, `shell-main-column--chat`, `shell-content-frame--chat`, no `workspace-page--chat`. |
| `390x844` | corrected mock/authenticated | Full Chat rendered for narrow layout: bento page, workspace, main shell, main panel, 2 messages, composer, mobile console trigger; console content exists in DOM | `gemini-bento-page=1`; substring `chat=4`, `bento=1`, `gemini=1` | same all-zero candidate counts | 0 | 0 page; 0 console | None detected by text scan | Desktop console classes remain present but hidden by responsive classes; mobile body text showed conversation and composer controls. |

Representative rendered classes:

- `chat-bento-page`: `gemini-bento-page bento-surface-root gemini-bento-page--chat flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden bg-[#030303]`
- `chat-main`: `min-h-0 w-full flex-1 overflow-y-auto no-scrollbar`
- `chat-strategy-panel`: `hidden h-full min-h-0 w-full shrink-0 flex-col gap-5 overflow-y-auto border-l border-white/5 bg-gradient-to-b from-white/[0.01] to-transparent p-5 no-scrollbar lg:flex lg:w-[320px] xl:w-[360px]`
- `chat-composer-omnibar`: `relative mx-auto w-full max-w-4xl rounded-3xl border border-white/[0.05] bg-white/[0.04] p-2 shadow-2xl backdrop-blur-2xl`
- Chat ancestors: `theme-page-transition--chat`, `shell-main-column--chat`, `shell-content-frame--chat`, `shell-content-frame--wide`, `theme-shell--wide`

## 6. Selector Conclusions

### `workspace-page--chat`

- Evidence: 0 rendered hits at both viewports; absent from `chat-bento-page`; absent from all collected ancestors from Chat root through `html`.
- Classification: Chat-specific future deletion-trial candidate.
- Future action: a separate CSS deletion trial can target this selector family only, with rollback and desktop/mobile `/zh/chat` proof. This report does not approve deletion directly.

### `gemini-bento-page`

- Evidence: 1 rendered hit at both viewports on `chat-bento-page`; root also includes `bento-surface-root` and `gemini-bento-page--chat`.
- Classification: active do-not-delete Chat owner primitive.
- Future action: document Chat owner classes and keep this selector until a deliberate owner migration exists.

### `glass-card`

- Evidence: 0 rendered hits at both Chat viewports; no non-CSS source hit in required search.
- Classification: remains absent for Chat, but deletion approval belongs to a broader selector trial.
- Future action: no Chat blocker found; keep separate from this report.

### `terminal-card`

- Evidence: 0 rendered hits at both Chat viewports; no non-CSS source hit in required search.
- Classification: remains absent for Chat.
- Future action: handle only in a separate selector-family deletion trial.

### `dashboard-card`

- Evidence: 0 rendered hits at both Chat viewports; no non-CSS source hit in required search.
- Classification: remains absent for Chat.
- Future action: no Chat-specific owner found.

### `gradient-border-card`

- Evidence: 0 rendered hits at both Chat viewports; no non-CSS source hit in required search.
- Classification: remains absent for Chat.
- Future action: no Chat-specific owner found; broader deletion trial still required.

### `stealth-scrollbar`

- Evidence: 0 rendered hits at both Chat viewports; active Chat scroll classes use `no-scrollbar` on `chat-main`, `chat-empty-state`, and `chat-strategy-panel`.
- Classification: absent in Chat DOM, but scrollbar behavior is a shared visual risk.
- Future action: if considered for deletion, verify active scroll containers route-wide and visible scrollbar behavior before any CSS edit.

### `backtest-entry-shell`

- Evidence: 0 rendered hits at both Chat viewports; not Chat-owned.
- Classification: unrelated to Chat route.
- Future action: keep Backtest proof separate.

### `product-command-card`

- Evidence: 0 rendered hits at both Chat viewports; no Chat source owner found.
- Classification: absent in Chat, but still high-risk as a product command primitive outside Chat.
- Future action: do not use Chat-only absence to justify deletion. Keep owner documentation and route-wide proof separate.

## 7. Recommended Next Tasks

1. Run a separate deletion trial for `workspace-page--chat` only, after confirming `apps/dsa-web/src/index.css` is not being edited by another active session.
2. Document Chat owner classes: `gemini-bento-page`, `bento-surface-root`, `gemini-bento-page--chat`, `shell-content-frame--chat`, `shell-main-column--chat`, `theme-page-transition--chat`, `chat-main`, `chat-strategy-panel`, `chat-composer-omnibar`.
3. Keep any Chat primitive migration deferred. The active bento/console/composer classes are current route owners and should not be folded into a CSS deletion task.
4. Add or preserve route-level Chat fixture coverage for both empty state and persisted-message state before future layout/CSS edits.
5. Keep `product-command-card`, `stealth-scrollbar`, and Backtest selectors out of a Chat-specific deletion trial.

Safe future audit tasks:

- Chat-only deletion-trial proof for `workspace-page--chat`.
- Chat owner-class documentation update.
- Corrected mock fixture script/check reuse for future read-only DOM audits.

Unsafe deletion tasks:

- Deleting `gemini-bento-page` or `gemini-bento-page--chat` from this evidence.
- Deleting `product-command-card` from Chat-only absence.
- Combining `workspace-page--chat` deletion with global card/scrollbar cleanup.
- Editing Chat product code, tests, CSS, backend/API, package, or config in the deletion proof step without an explicit implementation task.

## 8. Non-Goals

- No product code changed.
- No CSS changed.
- No tests changed.
- No backend/API changed.
- No package files or config changed.
- No `docs/CHANGELOG.md` changed.
- No real LLM call.
- No real chat message sent.
- No external provider call.
- No generated screenshots, videos, traces, Playwright reports, build artifacts, logs, coverage, sourcemaps, DuckDB files, or temp files committed.
- No selector deletion approved directly.

## 9. Appendix

Preflight:

- `pwd`: `/Users/yehengli/daily_stock_analysis`
- branch: `main`
- initial `git status --short`: clean
- initial `git status --branch --short`: `## main...origin/main`
- initial task preflight: branch `main`, upstream `origin/main` ahead 0 / behind 0, dirty files 0

Recent relevant commits observed in `git log --oneline -120`:

- `2446785 docs: document product command card ownership`
- `96503cf chore(css): remove unused gradient border card selectors`
- `89933dc docs: verify css selector dom usage`
- `2e97b39 docs: verify scanner dom shell classes`
- `3f68c7c docs: define canonical ui primitives`
- `6cfa4fe docs: audit frontend design conformance`

Port preflight:

- `lsof -i :8000`: Python backend listeners on localhost observed.
- `lsof -i :8001`: no listener.
- `lsof -i :5173`: node listener observed.
- `lsof -i :4173`: no listener.
- `lsof -i :5174`: no listener.
- `lsof -i :5175`: no listener.
- `lsof -i :5176`: no listener before isolated preview.

Static search highlights:

- `ChatPage.tsx` active root: `gemini-bento-page bento-surface-root gemini-bento-page--chat`.
- `Shell.tsx` active Chat shell modifiers: `shell-content-frame--chat`, `shell-main-column--chat`, `theme-page-transition--chat`.
- `ChatPage.test.tsx` asserts `chat-bento-page` does not have `workspace-page--chat` or old route padding/scroll classes.
- Required selector search found `workspace-page--chat`, `stealth-scrollbar`, `product-command-card`, `backtest-entry-shell`, and `gemini-bento-page` definitions in CSS; outside CSS, active Chat source hit was `ChatPage.tsx` for `gemini-bento-page`, while `workspace-page--chat` was only a test negative assertion.

Playwright route hit counts:

| Selector | Desktop | Mobile |
| --- | ---: | ---: |
| `.workspace-page--chat` | 0 | 0 |
| `.gemini-bento-page` | 1 | 1 |
| `.glass-card` | 0 | 0 |
| `.terminal-card` | 0 | 0 |
| `.dashboard-card` | 0 | 0 |
| `.gradient-border-card` | 0 | 0 |
| `.stealth-scrollbar` | 0 | 0 |
| `.backtest-entry-shell` | 0 | 0 |
| `.product-command-card` | 0 | 0 |

Validation commands:

- `npm run check:design`: PASS, 216 files scanned, no blocking violations or warnings.
- `npm run lint`: PASS, `eslint .` exited 0.
- `npm run build`: PASS with Vite chunk warning for `DeterministicBacktestChartWorkspace-CqMcjVp7.js`.
- `python3 -m compileall -q src api`: PASS.
- `sed -n '1,360p' docs/audits/archive/frontend/wolfystock-chat-dom-verification.md`: run after writing for report inspection.
- `git diff --check -- docs/audits/archive/frontend/wolfystock-chat-dom-verification.md`: run after writing.

Cleanup policy:

- Temporary Playwright script/results were kept under `/tmp` only during evidence collection and must not be committed.
- Generated `static/` build output, if present locally, is not part of this task and must not be staged.
- Unrelated dirty product/CSS files are parallel-session state and must remain unstaged.
