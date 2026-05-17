<!--
WolfyStock Reflect-Linear UI replacement document.
Source of truth image: docs/design/reference/wolfystock-reflect-linear-home-mockup.png
This document intentionally supersedes older deep-space / terminal / bento / generic Linear UI wording.
-->

# WolfyStock Frontend Validation Playbook

Status: validation procedure for Reflect-Linear frontend tasks.

## 1. Standard validation commands

For most frontend UI tasks, run:

```bash
npm --prefix apps/dsa-web run check:design
python3 scripts/check_frontend_design_constitution.py
npm --prefix apps/dsa-web run lint
npm --prefix apps/dsa-web run build
npm --prefix apps/dsa-web run test -- <focused-test-files>
git diff --check
./scripts/release_secret_scan.sh
```

Run broader tests only when the change scope warrants it.

## 2. Fresh screenshot rule

Screenshots must come from the current branch/build and a task-owned preview server. Do not reuse old mockup, stale browser state, or previous task screenshots as proof.

Reports must state:

- preview URL and port
- whether API/auth were live or mocked
- screenshot paths
- viewports
- console/page errors
- horizontal overflow status

## 3. Visual containment checks

For every migrated route, verify:

- primary work region visible in first viewport.
- filters are compact.
- rail is bounded.
- diagnostics/details collapsed or contained.
- no uncontrolled card wall.
- no raw `Details` copy.
- empty state is compact and attached to primary surface.
- mobile stacks primary task first.

## 4. Route-specific visual gates

### Home

- One dominant ResearchConsole.
- Chart is primary.
- Right rail is inside console rhythm.
- Events/catalysts attached as deck/rows.

### Scanner

- Ranking rows/table dominate.
- Selected detail bounded.
- Diagnostics/backtest collapsed.

### Watchlist

- Watch rows/list dominate.
- Filters do not own first viewport.
- Empty state compact.

### Chat

- Conversation ScrollPanel bounded.
- Composer anchored.
- Evidence/context rail collapsed or bounded.

### Market Overview

- Market monitor state is primary.
- Indicator boards equalized and contained.

### Portfolio

- Holdings ledger is primary.
- Risk rail bounded.

### Options

- Decision matrix/strategy rows primary.
- Chain/payoff details contained.

### Backtest

- Result/compare workspace primary.
- Parameters/details contained.

## 5. Visual failure wording

Final reports should honestly mark a route as visually weak when screenshots show:

- layout naming changed but visual card sprawl remains.
- secondary panels dominate the page.
- route still looks like a dashboard-kit clone.
- repeated cards make information hierarchy unclear.
