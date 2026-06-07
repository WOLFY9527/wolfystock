# T-1175 WolfyStock Public Beta Candidate Progress

Status: RUNNING

Date: 2026-06-08
Workspace: `/Users/yehengli/worktrees/t1175-public-beta-candidate`
Branch: `codex/t1175-public-beta-candidate`
Base commit: `829249b2`

## Goal

Move WolfyStock toward a To-C public beta candidate where a first-time user
sees a finance research product rather than an AI demo or terminal prototype.

Target readiness:

- Public Beta Readiness: at least 85/100.
- P0 blockers: 0.
- No real deployment, production secret exposure, destructive DB operation,
  broker/trading action, provider runtime/order/cache/API/auth/RBAC/scoring
  semantic weakening, or consumer raw diagnostics leakage.

## Required Inputs Read

- `AGENTS.md`
- `docs/codex/WOLFYSTOCK_CODEX_STANDARD_GUARD.md`
- `docs/codex/WOLFYSTOCK_CODEX_TASK_RUNTIME_RULES.md`
- `docs/codex/WOLFYSTOCK_CODEX_FINAL_REPORT_TEMPLATE.md`
- `docs/codex/WOLFYSTOCK_BACKEND_PROTECTED_DOMAINS.md`
- `docs/data-reliability/provider-source-confidence-contract.md`
- `docs/data-reliability/evidence-readiness-matrix.md`
- `docs/frontend/WOLFYSTOCK_CONSUMER_DATA_QUALITY_UX.md`
- `docs/frontend/README.md`
- `docs/frontend/visual-system.md`
- `docs/frontend/validation-playbook.md`
- `docs/audits/public-launch-gap-register.md`

## Boundary Decision

This goal may improve public-beta maturity through page/component copy,
consumer-safe layout hierarchy, tests, and release evidence. It must not open
protected backend/runtime domains unless a later scoped task explicitly names
the allowed files and semantic delta.

Allowed current write families:

- `docs/codex/goals/T-1175_PROGRESS.md`
- Consumer UI/page/component/test files under `apps/dsa-web/` when changes are
  presentation-only and preserve API/auth/provider/cache/scoring semantics.
- Focused docs or tests that lock current public-beta boundaries.

Protected domains kept closed:

- Provider runtime order, live-call paths, fallback behavior, MarketCache TTL,
  SWR, cold-start behavior, cache keys, and payload meaning.
- `sourceAuthorityAllowed`, `scoreContributionAllowed`, `authorityGrant`, score
  contribution, ranking, filtering, scanner selection, and market scoring
  semantics.
- Auth/RBAC/security behavior and API response contract changes.
- Portfolio accounting, broker sync/import, cash, holdings, P&L, FX, cost basis,
  and all trading or order actions.
- DB migrations, production DB reads/writes, destructive cleanup, real
  notification/payment/quota writes, and real deployment.

## Baseline V0

Method: static repository/doc scan before fresh browser evidence.

Public Beta Readiness estimate: 58/100.

Scorecard estimate:

| Area | Points | V0 |
| --- | ---: | ---: |
| guest/auth/protected | 15 | 9 |
| Market/Liquidity/Rotation observation-mode | 15 | 8 |
| demo research loop | 20 | 11 |
| consumer UI de-AI/de-diagnostic | 15 | 8 |
| perceived speed/partial/last-good | 10 | 6 |
| admin health | 10 | 6 |
| deploy precheck | 15 | 10 |

Baseline blocker inventory:

- P0 candidate: first-fold route evidence is not yet proven at desktop and
  mobile for the core consumer journey.
- P0 candidate: Market/Liquidity/Rotation usefulness is still constrained by
  data qualification/authority boundaries; safe partial observation must remain
  consumer-language only.
- P0 candidate: release candidate precheck is not yet freshly validated in this
  branch.
- P1: public launch register still records full public multi-user launch as
  NO-GO; T-1175 can only move toward a bounded public beta candidate, not real
  production launch.
- P1: route-level raw diagnostic and no-advice checks need fresh proof for the
  requested journey.

## Milestone Plan

1. Baseline checkpoint and score.
2. Consumer-safe first-fold maturity for Market Overview, Liquidity Monitor,
   Rotation Radar, and the guest/auth journey.
3. Demo research loop and protected-route journey proof without buy/sell/order
   advice.
4. Admin health readiness proof with raw payloads closed by default.
5. Release precheck: secret scan, focused backend/Vitest, lint, build,
   design guard, and Playwright proof at `1440x1000` and `390x844`.

## Validation Plan

Baseline checkpoint:

- `git diff --check -- docs/codex/goals/T-1175_PROGRESS.md`
- `./scripts/release_secret_scan.sh`
- `git status --short --branch`

Implementation checkpoint:

- `git diff --check`
- `./scripts/release_secret_scan.sh`
- Focused backend tests around touched domains, if any.
- Focused Vitest for touched pages/adapters/components.
- `npm --prefix apps/dsa-web run lint`
- `npm --prefix apps/dsa-web run build`
- `npm --prefix apps/dsa-web run check:design`
- Focused Playwright routes at `1440x1000` and `390x844`:
  guest, login/register, market overview, liquidity, rotation, scanner,
  watchlist, portfolio, report/history, and admin health.

## Checkpoints

| Time | Commit | Scope | Validation |
| --- | --- | --- | --- |
| 2026-06-08 02:30 CST | pending | Initial baseline progress doc | pending |

## Running Notes

- Subagents are being used for read-only product, market/backend, frontend UX,
  auth/journey, admin/ops, and DB/safety scans. Main agent owns all writes,
  integration, validation, commits, and pushes.
- Performance and QA/release scans are currently handled by the main agent due
  to thread limit; they can be delegated after explorer slots close if useful.
