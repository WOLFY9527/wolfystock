# WolfyStock Final Admin / Security / Options QA

Date: 2026-05-06
Mode: verification/report. No runtime behavior changed.

## 1. Executive summary

- Status: PASS with warnings
- Release confidence: high for the verified surfaces
- Blockers: none found in this QA pass
- Warnings: known build chunk-size warning, local optional-tool warnings, and one `ci_gate` pydantic serialization warning
- Deferred items: RBAC/capability split, MFA, password KDF upgrade, Options scoring/scenario engine, and future admin nav refinement

## 2. Git and environment

- Branch: `main`
- Head commit at QA start: `80dde2c0` `feat(options): add fixture-backed option chain api`
- Dirty status at start: clean
- Dirty status at end: clean after docs-only report commit
- Python: `Python 3.11.9`
- Node: `v20.20.2`
- npm: `10.8.2`
- Ports observed: `8000` in use, `5173` in use, `8001` free, `4173` free, `5174` free, `5175` free, `5176` free before QA preview
- Ports used: `5176` for isolated Vite preview
- Servers stopped: only the QA-owned `5176` preview server

## 3. Backend/security verification

Commands run:

- `python3 -m py_compile api/v1/endpoints/options.py api/v1/schemas/options.py src/services/options_lab_service.py api/v1/endpoints/auth.py api/v1/endpoints/admin_security.py`
- `python3 -m pytest tests/api/test_options_lab.py tests/test_options_lab_service.py -q`
- `python3 -m pytest tests/test_auth.py tests/test_auth_api.py tests/api/test_admin_security.py tests/api/test_auth_security_hardening.py tests/test_api_app_cors.py -q`
- `python3 -m pytest tests/api/test_admin_users.py tests/api/test_admin_portfolio.py tests/api/test_admin_cost_summary.py tests/api/test_admin_logs.py -q`
- `python3 -m pytest tests/api/test_quant_duckdb.py tests/test_quant_duckdb_service.py -q`
- `python3 -m pytest tests/test_rule_backtest_reopen_acceptance.py tests/test_rule_backtest_service.py -q`

Results:

- Options backend and service tests: `14 passed`
- Auth / security hardening tests: `78 passed`
- Admin users / portfolio / cost / logs tests: `45 passed`
- Quant DuckDB tests: `24 passed`
- Rule backtest tests: `127 passed`

Auth hardening status:

- Generic login errors verified
- Durable IP/account throttling verified
- Failed-login audit verified
- Production Secure cookie behavior verified
- Origin/Referer rejection for unsafe cookie-authenticated methods verified
- Production CORS allowlist guardrails verified

Admin security controls status:

- `disable`, `enable`, and `revoke-sessions` remain the only active S1 controls
- reason + typed confirmation are required
- sanitized `auditEventId` is surfaced
- no reset-password / force-change / unlock active controls were exposed in the verified UI

No-secret findings:

- No password hash, plaintext password, raw session id, cookie, token, API key, secret, reset token, or stack trace was exposed in the verified API responses or browser DOM

## 4. Admin data control verification

Routes verified:

- `/zh/admin/users`
- `/zh/admin/users/user-123`
- `/zh/admin/users/user-123/activity`
- `/zh/admin/users/user-123?tab=portfolio`
- `/zh/admin/users/user-123?tab=security`

Findings:

- Admin gating worked
- Chinese labels rendered
- loading / empty / error states were covered by existing tests and mocked browser checks
- portfolio tab remained read-only
- no raw broker refs, `payload_json`, or `sync_metadata_json` were surfaced
- security tab required reason and typed confirmation
- security tab surfaced a sanitized `auditEventId`
- no reset-password / force-change / unlock active controls were exposed

## 5. Cost observability verification

Route verified:

- `/zh/admin/cost-observability`

Findings:

- Read-only posture verified
- `noExternalCalls` surfaced
- `observational_not_billing` surfaced
- LLM / provider / MarketCache / Scanner AI sections were visible
- limitations were visible
- developer details stayed collapsed by default
- no raw prompt, message, provider payload, raw URL, cache key, candidate payload, token, or secret text was surfaced

## 6. Options Lab verification

Backend routes verified:

- `/api/v1/options/underlyings/TEM/summary`
- `/api/v1/options/underlyings/TEM/expirations`
- `/api/v1/options/underlyings/TEM/chain`

Frontend route verified:

- `/zh/options-lab`

Findings:

- Route rendered
- nav label `期权实验室` was visible
- symbol input and assumption panel were visible
- calls / puts chain tables rendered from fixture-backed data
- risk warnings were visible
- no order-placement CTA was exposed
- no `buy-now` / `必买` / `稳赚` / `guaranteed` / `best contract` wording was visible
- no raw provider payload, API key, token, secret, or stack trace was visible
- freshness / developer details stayed collapsed by default

## 7. Layout verification

Audited routes:

- `/zh`
- `/zh/market-overview`
- `/zh/scanner`
- `/zh/backtest`
- `/zh/portfolio`
- `/zh/chat`
- `/zh/admin/users`
- `/zh/admin/cost-observability`
- `/zh/admin/market-providers`
- `/zh/admin/logs`
- `/zh/options-lab`

Results:

- Desktop viewport: `1440x1000`
- Mobile viewport: `390x844`
- Horizontal overflow: none
- Console/page errors: none in the final mocked browser pass
- No huge dead layout bands were observed on backtest or portfolio in the mocked browser pass
- Chinese labels were visible
- No raw secret-like strings were visible

Known warning:

- `vite build` emitted the existing large chunk-size warning for `DeterministicBacktestChartWorkspace`

## 8. Browser verification details

| Route | Viewport | Mocked/live API status | Result | Notes |
| --- | --- | --- | --- | --- |
| `/zh/admin/users` | `1440x1000` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/admin/users/user-123` | `1440x1000` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/admin/users/user-123/activity` | `1440x1000` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/admin/users/user-123?tab=portfolio` | `1440x1000` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/admin/users/user-123?tab=security` | `1440x1000` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/admin/cost-observability` | `1440x1000` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/options-lab` | `1440x1000` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/backtest` | `1440x1000` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/portfolio` | `1440x1000` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/admin/market-providers` | `1440x1000` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/admin/logs` | `1440x1000` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/scanner` | `1440x1000` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/market-overview` | `1440x1000` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/chat` | `1440x1000` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/admin/users` | `390x844` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/admin/users/user-123` | `390x844` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/admin/users/user-123/activity` | `390x844` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/admin/users/user-123?tab=portfolio` | `390x844` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/admin/users/user-123?tab=security` | `390x844` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/admin/cost-observability` | `390x844` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/options-lab` | `390x844` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/backtest` | `390x844` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/portfolio` | `390x844` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/admin/market-providers` | `390x844` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/admin/logs` | `390x844` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/scanner` | `390x844` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/market-overview` | `390x844` | mocked auth/admin API | PASS | `overflowX=0px` |
| `/zh/chat` | `390x844` | mocked auth/admin API | PASS | `overflowX=0px` |

## 9. Full gate result

- `npm run test -- AdminUsersPage AdminCostObservability OptionsLab AppRoutes`: `4 passed, 54 passed`
- `npm run check:design`: passed, `225 files scanned`
- `npm run lint`: passed
- `npm run build`: passed with the existing large chunk warning
- `./scripts/ci_gate.sh`: passed
- Full backend gate summary: `2069 passed, 3 skipped, 1 warning, 203 subtests passed`

## 10. Known warnings and deferred risks

- Existing large chunk warning in frontend build
- `flake8` not installed locally for `ci_gate`'s optional lint coverage
- `akshare` not installed locally for provider-dependent smoke paths
- One pydantic serialization warning appeared during `ci_gate`
- RBAC/capability split remains future work
- MFA remains future work
- password KDF upgrade remains future work
- Options scoring/scenario engine remains future work
- cache/reuse prototypes remain future work

## 11. Release checklist

- Backend pass: yes
- Frontend pass: yes
- Browser pass: yes
- No-secret pass: yes
- No-advice/no-order pass: yes
- Rollback command available: yes, `git revert <docs-only-qa-commit>`

## 12. Recommended next tasks

1. Security Phase 2: session/admin idle timeout + security headers/proxy template
2. RBAC schema compatibility implementation
3. Options Lab Phase 3 scoring/scenario engine
4. Options Lab final no-advice QA after scoring
5. Admin governance final RBAC-aware nav after backend capabilities exist
