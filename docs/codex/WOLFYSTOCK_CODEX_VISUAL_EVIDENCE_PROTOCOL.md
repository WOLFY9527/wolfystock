# WolfyStock Codex Visual Evidence Protocol

Purpose: prevent Codex from using stale screenshots, reference images, old Playwright artifacts, or old preview bundles as current UI evidence.

Use this file for all frontend UI implementation, redesign, and visual-audit tasks.

## Evidence classes

| Evidence type | Meaning | Allowed use |
| --- | --- | --- |
| Approved mockup | Visual target only | Compare fresh implementation against it. Never treat it as current UI. |
| Fresh browser screenshot | Current implementation evidence | Required for frontend visual acceptance. Must come from current HEAD and a task-owned preview server. |
| Old screenshots | Historical evidence only | Do not use as current UI proof. |
| Repo images/assets | Product assets or historical docs | Do not use as current UI proof. |
| Test screenshots/artifacts | Previous run output | Do not use as current UI proof unless generated during the current task from current HEAD. |

## Hard rule

Current UI evidence must come only from:

1. current HEAD;
2. fresh build;
3. fresh task-owned dev/preview server;
4. fresh browser capture during the current task.

Do not use existing images from:

```text
/tmp
screenshots/
artifacts/
apps/dsa-web/test-results/
apps/dsa-web/playwright-report/
apps/dsa-web/blob-report/
docs/
repo image files
uploaded/reference images
old visual snapshots
```

as current UI evidence.

## Required preflight for visual tasks

Run before relying on screenshots:

```bash
pwd
git fetch origin
git status --short --branch
git log --oneline -8
git diff --name-only
git diff --cached --name-only
lsof -i :5173 -i :4173 -i :4177 -i :4178 -i :4179 -i :4180 -i :4181 || true
npm --prefix apps/dsa-web run build
```

Start a task-owned preview port. Prefer a port not already in use:

```bash
cd apps/dsa-web
DSA_WEB_PLAYWRIGHT_PORT=4181 npx vite preview --host 127.0.0.1 --port 4181
```

Open only the task-owned URL, for example:

```text
http://127.0.0.1:4181/
```

## Required screenshot locations

Fresh before screenshots:

```text
/tmp/<task-id>-fresh-before/
```

Fresh after screenshots:

```text
/tmp/<task-id>-fresh-after/
```

Do not save current-task screenshots into tracked repo paths unless the task explicitly asks for visual artifacts to be committed.

## Required viewports

Default for Home and route-level UI:

```text
1440x1000
1920x1080
390x844
```

For dense boards/tables, also inspect horizontal overflow and row action behavior on mobile.

## Required report fields

Frontend final reports must state:

```text
Fresh screenshot source:
- URL:
- Port:
- Server ownership:
- Build command:
- Screenshot paths:
- Confirmation screenshots were captured live during this task:
```

And:

```text
Visual checks:
- no horizontal overflow
- no console/page errors
- no pure-black root gutters/gaps
- route follows its Linear OS surface taxonomy
- no stale/reference screenshot was used as current UI evidence
```

## Stop conditions

Stop and report instead of committing when:

- the task cannot start a fresh preview server;
- the route renders from an old port or stale bundle;
- browser screenshots cannot be captured;
- the page still visibly matches a forbidden old pattern;
- screenshot evidence came from old files or search results instead of a live browser;
- tests pass but visual gate fails.

## Stale screenshot cleanup

If stale images are found, do not delete broad directories unless the task explicitly scopes cleanup. For cleanup tasks, target only historical UI screenshots and report what was removed.

Safe historical UI screenshot patterns include:

```text
screenshots/desktop/
screenshots/mobile/
artifacts/**/frontend-visual-audit/
artifacts/**/browser-screenshots-*/
artifacts/**/auth-browser-screenshots-*/
apps/dsa-web/test-results/
apps/dsa-web/playwright-report/
apps/dsa-web/blob-report/
```

Do not delete product assets, logos, public images, or docs images that are not UI reference screenshots.
