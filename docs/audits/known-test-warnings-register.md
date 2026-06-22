# Known Test Warnings Register

Status: Current
Date: 2026-05-07
Branch checked: `main`
Owner domain: Release readiness
Related docs: `docs/audits/public-launch-readiness-master.md`,
`docs/archive/audits/final-pre-push-audit.md`,
`docs/archive/audits/wolfystock-final-admin-security-options-qa.md`,
`docs/archive/qa/wolfystock-portfolio-populated-holdings-qa.md`,
`docs/archive/audits/frontend/wolfystock-echarts-chart-workspace-audit.md`

Mode: docs-only warning register. No warning filters, production code, tests,
scripts, frontend app files, provider configuration, or changelog files were
changed.

## Warning policy

This register separates known warning cleanup from public launch blockers.
Warnings marked non-blocking are not approval to ignore them indefinitely; they
are accepted only when the related gate still passes and the warning does not
hide a security, correctness, data-leakage, or financial-safety failure.

## Register

| Warning | Status | Owner domain | Current impact | Proposed cleanup path |
| --- | --- | --- | --- | --- |
| `websockets` / `lark_oapi` deprecation warning | Isolated / non-blocking | Notifications / Feishu integration | Feishu stream tests now isolate the third-party import-time deprecation warnings locally. Production warning behavior is unchanged, and the warning is not known to fail the local gate by itself. | During the next notification dependency pass, pinpoint the emitting package/version, upgrade or pin the compatible SDK stack, and keep focused Feishu stream smoke coverage with mocked transport before changing runtime notification behavior. |
| Pydantic serializer warning | Resolved | Backend schemas / backtest API contract | Backtest API contract coverage now asserts `RuleBacktestHistoryResponse.model_dump(by_alias=True)` emits no `PydanticSerializationUnexpectedValue` warnings. | Keep the regression assertion with backtest API contract tests. Reopen only if a future schema or fixture change reintroduces serializer warnings or response-shape drift. |
| Eastmoney unverified HTTPS warning | Isolated / non-blocking | Market data provider / Eastmoney adapter | Offline tests now mock the Eastmoney history helper boundary and assert the requests transport is not called, so this warning should not appear in deterministic test runs. Production/provider smoke calls may still surface the warning and should remain visible. | Keep deterministic tests on fixtures/mocks. For provider-smoke cleanup, reproduce against the real Eastmoney adapter without credentials, identify the exact library call stack, prefer verified HTTPS/certificate configuration, and only suppress the warning if the provider library cannot be changed and the risk is documented. |
| Existing Vite chunk-size warning for `DeterministicBacktestChartWorkspace` | Still open / non-blocking | Frontend performance / backtest chart workspace | Frontend builds have passed with a known lazy chunk around 532 kB; this is a performance/developer warning, not a functional failure. | Keep the warning visible. If route performance becomes a release issue, run a scoped ECharts/zrender bundle split or on-demand module registration trial with build evidence and browser chart interaction checks. |

## Blocking rules

Promote a warning to blocking if any of the following becomes true:

- The warning accompanies a failing test, build, smoke, or gate.
- The warning points to possible credential, cookie, session, provider payload,
  broker secret, or raw stack-trace exposure.
- The warning indicates a response schema mismatch visible to API, Web, Desktop,
  or notification consumers.
- The warning indicates financial data correctness, owner-isolation, or
  portfolio/backtest mutation risk.
- The warning makes launch validation ambiguous because the same log section
  also contains failures.

## Current summary

- Blocking warnings: none registered.
- Resolved warnings: 1.
- Open non-blocking warnings: 3.
- Isolated/non-blocking warnings: 2.
- Still-open/non-blocking warnings: 1.
- Launch impact: none of these warnings changes the current public launch
  verdict. Public launch remains **NO-GO** because readiness blockers remain in
  security/MFA/RBAC, WS2 multi-instance proof, portfolio/backtest safety,
  cost/quota/provider circuit enforcement, and deployment/backup/rollback.
