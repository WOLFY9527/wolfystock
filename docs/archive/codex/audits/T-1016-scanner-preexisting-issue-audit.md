# T-1016 Scanner pre-existing issue audit

Task: T-1016-AUDIT Audit pre-existing Scanner design-guard issues

Mode: READ-ONLY-AUDIT prompt with one explicitly allowed docs-only audit artifact

Allowed artifact: `docs/codex/audits/T-1016-scanner-preexisting-issue-audit.md`

Observed HEAD during audit: `fa9ee9fe` (`fix(web): clarify admin system settings landing copy`)

Branch: `codex/t1016-scanner-preexisting-issue-audit`

## Scope boundary

- Source inspected, not changed.
- Tests inspected, not changed.
- No Scanner behavior, ranking, scoring, filter, selection, backend, API,
  config, lockfile, or changelog changes.
- This audit stays narrow to the two referenced `UserScannerPage.tsx` findings
  and their nearby display/test context.

## Executive summary

The prior handoff line references are not stale. Current
`apps/dsa-web/src/pages/UserScannerPage.tsx:1056` and `:1083` still point to
live UI code, and both references now resolve to the same kind of issue:
`observe_only` segments in the Scanner visual evidence summary are colored with
an amber warning tone.

This is a real current display issue, but it is narrow:

- still present;
- user-visible only when the visual evidence summary renders an
  `observe_only` segment;
- cosmetic/display-only rather than behavioral;
- not risky to Scanner ranking/scoring/filter/selection semantics;
- safe for one bounded future display-only write task.

No broader Scanner redesign is recommended from this audit.

## Evidence inspected

- `apps/dsa-web/src/pages/UserScannerPage.tsx:1029-1092`
- `apps/dsa-web/src/components/scanner/ScannerDisplayPanels.tsx:89-117`
- `apps/dsa-web/src/components/scanner/ScannerDisplayPanels.tsx:280-381`
- `apps/dsa-web/src/components/scanner/ScannerCandidateEvidenceStrip.tsx:75-81`
- `apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx:1287-1331`

## Findings

| Referenced issue | Current verdict | Why | Risk class | Future write status |
| --- | --- | --- | --- | --- |
| `UserScannerPage.tsx:1056` | Still present and user-visible; not stale | Candidate evidence coverage maps `observe_only` to `bg-amber-300/85`. This segment is rendered by `ScannerVisualEvidenceSummaryPanel` when `observeOnlyCount > 0`. | Cosmetic only; no ranking/scoring/filter/selection risk | Safe for display-only follow-up |
| `UserScannerPage.tsx:1083` | Still present and user-visible; not stale | Market evidence coverage maps `observe_only` to `bg-amber-300/85`. This segment is rendered when `observationOnlyCount > 0`. | Cosmetic only; no ranking/scoring/filter/selection risk | Safe for display-only follow-up |

## Why this is not a protected-domain behavior issue

Both referenced lines only populate `toneClassName` for display segments.
Counts, ordering, labels, filters, selected rows, and scanner result semantics
come from surrounding evidence/count fields and are not changed by this color
mapping.

Render path:

- `UserScannerPage.tsx:1029-1092` builds segment arrays and color classes.
- `ScannerDisplayPanels.tsx:89-117` renders each segment with width derived from
  count, not color.
- `ScannerDisplayPanels.tsx:335-380` renders the visual evidence summary panel
  without changing row order and explicitly describes it as compact distribution
  only.

## Consistency note

Nearby Scanner evidence UI already treats `observe_only` as an informational
blue tone, not an amber warning tone:

- `ScannerCandidateEvidenceStrip.tsx:80` maps `observe_only` to
  `border-blue-400/25 bg-blue-400/10 text-blue-100`.

That makes the current visual summary color choice inconsistent with the page's
existing observation-only presentation, but still cosmetic.

## Test coverage status

`apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx:1287-1331` verifies:

- the visual evidence summary renders;
- evidence labels such as `仅观察` / `待补` appear;
- row order and score labels remain unchanged;
- no raw provider/debug leakage appears.

Current gap:

- there is no focused assertion on the `observe_only` segment tone class in the
  visual summary bar or legend.

So the issue is real current UI behavior, but existing nearby tests would not
fail on it.

## Recommended next task

Recommend exactly one bounded future write task.

### Task: normalize Scanner visual-summary `observe_only` tone

Allowed files:

- `apps/dsa-web/src/pages/UserScannerPage.tsx`
- `apps/dsa-web/src/pages/__tests__/UserScannerPage.test.tsx`

Forbidden semantics:

- no Scanner ranking, scoring, shortlist, filter, selection, sorting, or result
  order changes;
- no data/count/label/copy changes beyond the narrow tone assertion/update;
- no backend, API, provider, cache, auth, or route changes;
- no Scanner redesign or layout rewrite.

Focused validation:

- `npm --prefix apps/dsa-web run test -- src/pages/__tests__/UserScannerPage.test.tsx --run`
- `npm --prefix apps/dsa-web run build`
- `npm --prefix apps/dsa-web run check:design`
- `git diff --check`
- `./scripts/release_secret_scan.sh`

Recommended outcome:

- align the visual-summary `observe_only` tone with the existing Scanner
  observation-only presentation;
- add one narrow regression assertion so the tone does not drift again.

## Decision

Verdict by referenced issue:

- `UserScannerPage.tsx:1056`: real current issue, user-visible, cosmetic,
  display-only safe.
- `UserScannerPage.tsx:1083`: real current issue, user-visible, cosmetic,
  display-only safe.

Not recommended:

- no broad Scanner redesign task;
- no task that touches ranking/scoring/filter/selection;
- no multi-file Scanner UX rewrite from this audit alone.
