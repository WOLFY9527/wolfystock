# T520 Latest Main Browser Requalification

## Outcome

**Status: BLOCKED_NOT_QUALIFIED.** The accepted source and managed environment
were verified, and the generated static artifact matches the current source.
The canonical runtime UAT did not reach `PASS`, and the required release
real-runtime Playwright project could not launch Chromium. No blocked browser
or accessibility behavior is represented as passed.

## Identity

| Field | Observed identity |
| --- | --- |
| Commit | `72a57aba7c96325a8d177d049469438526d104e1` |
| Tree | `69f8f563aaeab9e12b9c9e9fb9031775425a0524` |
| Runtime CWD | `$WORKTREE` |
| Runtime port | `8002` (task-owned UAT attempt) |
| Environment fingerprint | `30939cb3ec09cf379c387aa7fd118adf339479cb92a37e10148d396422318ae1` |
| Environment | Darwin arm64, CPython 3.11.15, Node 20.20.2, npm 10.8.2 |
| Static artifact | `wolfystock_web_build_artifact_v1`, fingerprint `4c466d9c1d3697a814564bc058812ad2a7e8015b08de903079d5b4898a4bab66` |
| Static source binding | candidate SHA/tree match; 145 assets; main JS `index-D6aH2d9V.js` |

`./wolfy lock python --check`, `./wolfy bootstrap --ensure --offline`,
`./wolfy env verify`, and `./wolfy qualify-env` all passed. The offline
bootstrap evidence records `bootstrapNetworkUsed=false`.

## Runtime UAT

The application was started through `./wolfy exec --profile test`. A listener
already owned port 8000; the harness rejected it and no unrelated process was
terminated. The retry on port 8001 failed before startup because `npm run build`
attempted to write TypeScript build-info under the immutable managed
`node_modules` snapshot.

The repository artifact builder subsequently produced and verified a current
static artifact. UAT on port 8002 passed direct health, readiness, root HTML,
served asset hashes, and no-live-provider isolation. It still failed its
aggregate because the canonical smoke does not establish a session for the
explicitly seeded local accounts: authenticated, admin-ops, and
surface-readiness checks remained `PARTIAL`. This is not a qualified canonical
UAT result.

## Browser Coverage

The release project was invoked with `--project=release-real-runtime` and
`--retries=0`; no product-route mocking was enabled. Results: **0 passed, 1
launch failure, 3 serially skipped, 0 retries, 0 flaky**.

Chromium 1208 was absent from the managed test profile. The launch failure
happened before navigation, so the following requested journeys are all
`blocked_from_verification`: guest home; sign-in/sign-out; authenticated
research; scanner; watchlist; stock structure; deterministic backtest;
portfolio; settings; admin allowed/denied routes; unknown route; locale switch;
and session refresh/reload.

Desktop (`1440x1000`), tablet (`1024x900`), and mobile (`390x844`) coverage is
also blocked. There are no browser screenshots, videos, traces, auth state, or
cache artifacts in this commit.

## Prior Findings Delta

| Prior finding | Current status | Evidence |
| --- | --- | --- |
| T-1082 Watchlist empty-state stacking and duplicate Scanner CTA at `390x844` | Blocked from verification | Real browser did not launch; no fixture/mock substituted for current behavior. |
| QW-003 low-contrast consumer labels | Blocked from verification | Deterministic browser contrast measurement did not run. |
| Shell focus recovery / narrow focus containment | Blocked from verification | Keyboard and focus inspection requires a launched browser. |

No prior finding can be marked fixed, still reproducible, or changed
manifestation from this run. Historical source material is traceable in Git,
but the canonical documents are no longer present in the current tree.

## Findings

1. `T520-F001` (P1, newly discovered): canonical UAT's default frontend build
   is incompatible with the immutable Wolfy `node_modules` snapshot. The build
   writes `node_modules/.tmp/tsconfig.*.tsbuildinfo` and fails with EACCES.
2. `T520-F002` (P1, newly discovered): when auth is enabled, canonical UAT
   seeds local accounts but creates no authenticated smoke session. The required
   authenticated/admin readiness checks remain `PARTIAL`.
3. `T520-F003` (P1, blocked): the managed test profile lacks its required
   Chromium 1208 executable. The release browser project fails at launch and
   cannot qualify product journeys.

Direct runtime requests returned 200 for health, readiness, root HTML, main JS,
and CSS. Anonymous admin/surface-readiness calls returned 401 under enabled
auth, as expected. No raw secret or stack trace was observed in the sanitized
runtime evidence. Browser console errors, failed browser requests, accessible
names, landmarks/headings, keyboard navigation, focus restoration, contrast,
overflow, and visual loading/empty/unavailable/error states are all blocked,
not passed.

## Evidence Boundaries

- `output/runtime-verification/uat-20260718T084116-e4be8393-evidence.json`:
  current UAT evidence, not committed.
- `output/t520-release-real-runtime.json`: release project result, not
  committed.
- `output/t520-playwright/<release-real-runtime-launch-failure>/trace.zip`:
  launch-failure trace, not committed.

All references are sanitized relative descriptions. No live financial provider
was used. No authenticated session was fabricated outside the repository's
explicit local test setup.

## Qualification Decision

The latest main cannot be qualified for the requested real-browser journeys
until the canonical UAT reaches `PASS` and the repository-owned real-runtime
Playwright project can launch its declared browser. Re-run the same report
after those two blockers are resolved.
