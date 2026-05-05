# Admin Data Schema Inventory

Date: 2026-05-06
Mode: docs-only inventory. No runtime behavior changed.

## 1. Purpose

This inventory supports the future Admin Data Control Center proposed in
`docs/audits/admin-data-control-center-design.md`. It maps the existing
user, security, session, activity, analysis, scanner, backtest, portfolio, LLM,
provider/runtime, and upload-adjacent data surfaces before any admin
user/business-data API is implemented.

This document is intentionally descriptive. It does not define migrations,
runtime behavior, authorization changes, frontend UI, or data changes. Future
admin APIs should expose least-privilege projections, never raw database rows.

## 2. Inventory summary

| Domain | Existing models/tables/classes | Owner/user fields | Current access pattern | Admin visibility recommendation | Sensitive fields | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| auth/users | `src/storage.py::AppUser`, `api/deps.py::CurrentUser`, `src/repositories/auth_repo.py::AuthRepository` | `AppUser.id`, `username`, `role`, `is_active`; `CurrentUser.user_id`, `role`, `is_admin` | Current-user resolution in `api/deps.py::resolve_current_user()`; admin gates use `require_admin_user()` | List/detail projection with user id, username, display name, role, active status, created/updated, session counts | `password_hash`, legacy `.admin_password_hash` contents | Confirmed no `/api/v1/admin/users` API in the inspected design scope. |
| sessions | `src/storage.py::AppUserSession`, `src/auth.py::SessionIdentity` | `AppUserSession.user_id`, `SessionIdentity.user_id`, `session_id` | Login creates sessions through `AuthRepository.create_app_user_session()`; logout/change-password revoke sessions | Show counts, timestamps, status, redacted handle only | raw `session_id`, signed `dsa_session` cookie, `.session_secret`, admin unlock token | `src/auth.py::COOKIE_NAME` is `dsa_session`; cookie value must never be returned. |
| execution logs/admin logs | `ExecutionLogSession`, `ExecutionLogEvent`, `api/v1/schemas/admin_logs.py`, `ExecutionLogService` | `summary.meta.actor_user_id` and business event `userId` are metadata-level, not first-class columns | Admin-only endpoints in `api/v1/endpoints/admin_logs.py` use `Depends(require_admin_user)` | Use as Admin Activity Timeline base with sanitized event/session projections | `summary_json`, `detail_json`, messages, URLs may carry secrets or raw context | `ExecutionLogService` calls `sanitize_metadata()`, `sanitize_message()`, and `sanitize_url()`. |
| analysis history | `src/storage.py::AnalysisHistory`, `src/repositories/analysis_repo.py::AnalysisRepository` | `owner_id`, `query_id` | API/task paths pass `owner_id` from `get_current_user_id()`; repository supports `include_all_owners` for privileged reads | Show stock/report metadata and summary; collapse raw payloads behind audited restricted detail | `raw_result`, `news_content`, `context_snapshot`, prompt/report internals | `to_dict()` includes raw fields, so admin APIs need explicit allowlist projection. |
| scanner runs/candidates | `MarketScannerRun`, `MarketScannerCandidate`, `ScannerRepository`, `MarketScannerService` | `MarketScannerRun.owner_id`, `scope`; candidates link by `run_id` | User routes read `scope=user`; admin operational routes exist for scanner status/run controls | Show run summary, profile, market, counts, top candidates, deterministic ranks/scores; sanitize diagnostics | `diagnostics_json`, `summary_json`, candidate diagnostics, AI interpretation metadata | Do not change ranking/scoring/selection/thresholds. |
| backtest/rule backtest | `BacktestRun`, `BacktestResult`, `BacktestSummary`, `RuleBacktestRun`, `RuleBacktestTrade` | `owner_id` on run/result/summary/rule run; trades link by `run_id` | `BacktestRepository` and `RuleBacktestRepository` enforce owner unless `include_all_owners=True` | Show status, metrics, code, windows, result ids, trade counts; collapse strategy text and raw summaries | `RuleBacktestRun.strategy_text`, `parsed_strategy_json`, `summary_json`, `ai_summary`, `equity_curve_json`, trade notes/signals | Do not change calculations or strategy parsing behavior. |
| portfolio/accounts/holdings/cash/trades/corporate actions/broker sync | `PortfolioAccount`, `PortfolioBrokerConnection`, sync state/positions/cash, `PortfolioTrade`, `PortfolioCashLedger`, `PortfolioCorporateAction`, `PortfolioPosition`, `PortfolioDailySnapshot`, `PortfolioService`, `PortfolioRepository` | `owner_id` on accounts/broker sync rows; event/position rows link by `account_id` | `api/v1/endpoints/portfolio.py::_get_portfolio_service()` builds `PortfolioService(owner_id=current_user.user_id)` | Read-only summary first: accounts, totals, holdings, cash, trade/cash/action counts, broker sync state | broker refs, `session_token` request field, `sync_metadata_json`, `payload_json`, notes, imported-file content | Broker session token is request-only for IBKR sync; do not persist or display it. |
| LLM usage | `src/storage.py::LLMUsage`, `src/services/llm_instrumentation.py` | No confirmed `owner_id` on `LLMUsage` | Usage table records call type/model/stock/tokens/time | Aggregate by model/call type/time; link to execution logs where possible | model names may be operationally sensitive; raw prompts are not in `LLMUsage` but may be in reports/log metadata | Owner attribution gap remains for per-user cost governance. |
| provider/runtime logs | `ExecutionLogService.record_market_overview_fetch()`, provider HTTP helpers, market provider operations endpoint | Actor metadata where supplied; provider logs often system-level | Admin provider surfaces use `require_admin_user()` and sanitized details | Show provider/cache/fallback status, sanitized endpoint, reason, counts | URLs, headers, API keys, provider raw payloads, error text | Existing sanitizers mask token/key/password-like strings. |
| uploaded files/images | `api/v1/endpoints/portfolio.py` `UploadFile` import routes; `src/services/image_stock_extractor.py`; `api/v1/schemas/analysis.py` image source label | Portfolio import is user-scoped by current user/account; image extraction has no confirmed persisted upload table | Uploads are request inputs; no inspected durable file/blob table for raw image uploads | Expose metadata only if future retention exists: file type, size bucket, hash, created time, owner | raw uploaded files, image bytes/base64, broker import rows, image data URL sent to LLM vision | Confirmed image extractor builds data URL for vision call; no raw image admin projection should be added without retention policy. |

## 3. Auth/user/session models

Confirmed user fields:

- `src/storage.py::AppUser`: `id`, `username`, `display_name`, `password_hash`, `role`, `is_active`, `created_at`, `updated_at`.
- `api/deps.py::CurrentUser`: `user_id`, `username`, `display_name`, `role`, `is_admin`, `is_authenticated`, `transitional`, `auth_enabled`, `session_id`, `legacy_admin`.
- `src/storage.py::UserPreference`: `user_id`, `ui_preferences_json`, `notification_preferences_json`, `created_at`, `updated_at`.

Confirmed session fields:

- `src/storage.py::AppUserSession`: `session_id`, `user_id`, `created_at`, `last_seen_at`, `expires_at`, `revoked_at`.
- `src/auth.py::SessionIdentity`: `user_id`, `username`, `role`, `session_id`, `issued_at`, `expires_at`, `token_kind`, `legacy_admin`, `transitional`.

Sensitive fields:

- `AppUser.password_hash`.
- Legacy admin credential file contents managed by `src/auth.py::_get_credential_path()` and mirrored by `ensure_bootstrap_admin_user_password_hash()`.
- Signed cookie value under `src/auth.py::COOKIE_NAME` (`dsa_session`).
- Raw `AppUserSession.session_id`.
- Session signing secret loaded from `.session_secret`.
- Admin unlock tokens created by `src/auth.py::create_admin_unlock_token()`.

Safe admin projection:

- `id`, `username`, `displayName`, `role`, `isActive`, `createdAt`, `updatedAt`.
- Derived `status`: `active`, `disabled`, `transitional`, or `legacyAdmin` where applicable.
- Derived session counts: active, expired, revoked.
- Derived timestamps: last login/last seen/last activity when available.
- Redacted session handle such as `sha256(session_id)` prefix or `sess_...last4`; do not return the raw id.

Forbidden fields:

- `password_hash`, password hash salt/hash components, plaintext passwords, `.admin_password_hash`, `.session_secret`, signed cookies, raw `session_id`, reset/admin-unlock token values, and any request body password fields from `api/v1/endpoints/auth.py`.

## 4. Activity/log models

Confirmed storage fields:

- `src/storage.py::ExecutionLogSession`: `session_id`, `task_id`, `query_id`, `analysis_history_id`, `code`, `name`, `overall_status`, `truth_level`, `summary_json`, `started_at`, `ended_at`, `created_at`, `updated_at`.
- `src/storage.py::ExecutionLogEvent`: `session_id`, `event_at`, `phase`, `step`, `target`, `status`, `truth_level`, `message`, `error_code`, `detail_json`.

Confirmed API projection fields:

- `api/v1/schemas/admin_logs.py::ExecutionLogSessionSummaryModel`: session/task/query/analysis ids, code/name, status/truth level, timestamps, `summary`, `readable_summary`.
- `ExecutionLogEventModel`: event timestamp, level/category/event name/action/outcome/reason, target/status/truth level/message/error/detail.
- `BusinessEventModel`: category/type/status/summary/subject/symbol/market/actor labels/route/endpoint/provider/source/reason/error/trace ids, related scanner/backtest/request/user/record ids, timestamps, step counts, metadata.

Sanitization patterns:

- `src/utils/security.py::sanitize_metadata()` recursively masks secret-like keys.
- `sanitize_message()` masks secret-like URL/query/key-value fragments, Authorization headers, and Bearer tokens.
- `sanitize_url()` masks secret-like query params.
- `ExecutionLogService.list_sessions()`, `get_session_detail()`, `list_business_events()`, and `get_business_event_detail()` sanitize rows, summaries, details, and enriched events before returning.

Admin projection:

- Use `AdminActivityEvent` as a normalized event view: id, category, type, status, actor, target user/entity, redacted trace ids, route family, summary, timestamps, duration, safe metadata.
- Keep `summary_json` and `detail_json` collapsed; expose only sanitized allowlist fields by default.
- Sensitive admin view access should itself call a future audited admin-action recorder, similar in shape to `ExecutionLogService.record_admin_action()`.

## 5. Analysis/scanner/backtest models

Analysis:

- `src/storage.py::AnalysisHistory` confirmed fields: `id`, `owner_id`, `query_id`, `code`, `name`, `report_type`, `sentiment_score`, `operation_advice`, `trend_prediction`, `analysis_summary`, `raw_result`, `news_content`, `context_snapshot`, `ideal_buy`, `secondary_buy`, `stop_loss`, `take_profit`, `is_test`, `created_at`.
- `src/repositories/analysis_repo.py::AnalysisRepository` applies owner scoping through `owner_id` and has `include_all_owners` for privileged reads.
- Safe projection: id, owner id, query id, code/name/report type, sentiment/advice/trend, short summary, sniper point fields, test flag, created time.
- Restricted/collapsed fields: `raw_result`, `news_content`, `context_snapshot`, persisted report details, decision trace, model/provider metadata.

Scanner:

- `MarketScannerRun` fields: `id`, `owner_id`, `scope`, `market`, `profile`, `universe_name`, `status`, size counts, timestamps, `source_summary`, `summary_json`, `diagnostics_json`, `universe_notes_json`, `scoring_notes_json`.
- `MarketScannerCandidate` fields: `run_id`, `symbol`, `name`, `rank`, `score`, `quality_hint`, `reason_summary`, JSON fields for reasons, metrics, signals, risks, watch context, boards, diagnostics, `created_at`.
- `ScannerRepository._build_run_visibility_conditions()` is the owner/scope visibility seam for scanner run reads.
- Safe projection: run id, owner id, scope, market, profile, status, counts, timestamps, source summary, top symbols, ranks, scores, quality hints, compact reasons.
- Restricted/collapsed fields: diagnostics, provider diagnostics, AI interpretation metadata, generated theme prompt/criteria, rejected symbols detail where it may include user intent.

Backtest:

- Standard backtest confirmed models: `BacktestRun`, `BacktestResult`, `BacktestSummary`.
- Rule backtest confirmed models: `RuleBacktestRun`, `RuleBacktestTrade`.
- `BacktestRepository` and `RuleBacktestRepository` require `owner_id` unless `include_all_owners=True`.
- Safe projection: run id, owner id, code, status, run/completed timestamps, evaluation window, engine/timeframe, counts, return/win/drawdown metrics, result counts, linked analysis id.
- Restricted/collapsed fields: `strategy_text`, `parsed_strategy_json`, `warnings_json`, `summary_json`, `ai_summary`, `equity_curve_json`, trade entry/exit signal texts, rule JSON, notes.

## 6. Portfolio/holdings models

Confirmed account/broker fields:

- `PortfolioAccount`: `id`, `owner_id`, `name`, `broker`, `market`, `base_currency`, `is_active`, `created_at`, `updated_at`.
- `PortfolioBrokerConnection`: `owner_id`, `portfolio_account_id`, `broker_type`, `broker_name`, `connection_name`, `broker_account_ref`, `import_mode`, `status`, `last_imported_at`, `last_import_source`, `last_import_fingerprint`, `sync_metadata_json`, timestamps.

Confirmed sync/holding fields:

- `PortfolioBrokerSyncState`: owner/account/connection ids, broker/account refs, sync source/status/date/time, base currency, cash/market/equity/PnL totals, `fx_stale`, `payload_json`.
- `PortfolioBrokerSyncPosition`: owner/account/connection ids, broker position ref, symbol/market/currency, quantity/cost/price/value/PnL fields, `payload_json`.
- `PortfolioBrokerSyncCashBalance`: owner/account/connection ids, currency, amount, base amount.
- `PortfolioPosition`, `PortfolioPositionLot`, `PortfolioDailySnapshot`, and `PortfolioFxRate` hold replayed positions, lots, daily account snapshots, and cached FX rates.

Confirmed ledger fields:

- `PortfolioTrade`: `account_id`, `trade_uid`, symbol/market/currency/date/side/quantity/price/fee/tax/note, `dedup_hash`, active/void/timestamps.
- `PortfolioCashLedger`: `account_id`, `event_date`, `direction`, `amount`, `currency`, `note`, `created_at`.
- `PortfolioCorporateAction`: `account_id`, symbol/market/currency/effective date/action type, dividend/split fields, note, `created_at`.

Current ownership/access:

- `api/v1/endpoints/portfolio.py::_get_portfolio_service()` constructs `PortfolioService(owner_id=current_user.user_id)`.
- Request-level owner assertions are handled by `_assert_owned_request()`.
- `PortfolioRepository` filters accounts and broker connections by owner unless `include_all_owners=True`.
- Portfolio write paths call `_record_portfolio_audit()`, which delegates to `ExecutionLogService.record_portfolio_event()`.

Sensitive broker fields and redaction:

- `PortfolioIbkrSyncRequest.session_token` is a sensitive request-only token.
- `broker_account_ref` should be masked or partially displayed in broad admin views.
- `sync_metadata_json` and `payload_json` may include broker/provider payloads; default projection should expose status/count/timestamp summaries only.
- Import preview/commit responses can contain broker-import rows and notes; broad admin view should show counts and warnings first.

Safe admin projection:

- User-level totals: account count, active account count, base currencies, aggregate equity/cash/market value/PnL, FX stale flag, last sync/import timestamps.
- Account-level: account id/name, masked broker/account refs, market/base currency, active flag, created/updated.
- Holdings: symbol, market, currency, quantity, value, unrealized PnL, valuation currency, FX status.
- Ledger: trade/cash/action counts and last timestamps by account; detailed ledger rows only behind audited drilldown.

## 7. Sensitive-field classification

| Field/source | Risk | Admin projection | Redaction | Audit requirement |
| --- | --- | --- | --- | --- |
| `AppUser.password_hash` | Credential compromise/offline attack | Never returned | Omit entirely | Audit password reset/force-change actions only |
| Legacy `.admin_password_hash` | Bootstrap admin credential hash | Never returned | Omit entirely; mention configured state only | Audit admin credential changes |
| `.session_secret` | Signs sessions and unlock tokens | Never returned | Omit entirely | Audit rotation only |
| `AppUserSession.session_id` | Session takeover/linkability | Session count/status plus redacted handle | Hash/truncate; never raw | Audit view/revoke |
| `dsa_session` cookie and admin unlock tokens | Active auth bearer material | Never returned | Omit entirely | Audit creation/revocation/verification outcomes, not values |
| Request cookies / `Authorization` headers | Auth bearer material | Never returned | Use `sanitize_message()` and `sanitize_metadata()` | Audit access to raw request diagnostics if ever supported |
| API keys/tokens/secrets/env values | Third-party account compromise | Configured/unconfigured or masked status only | Env var names allowed; values omitted/masked | Audit test/rotate/update actions |
| Broker credentials and IBKR `session_token` | Broker account access | Request-only action status | Do not persist/display; mask if logged | Audit sync attempts and failures |
| `broker_account_ref` | Financial account identifier | Masked account reference | Prefix/suffix or hash | Audit portfolio drilldown |
| `sync_metadata_json`, broker `payload_json` | Raw broker/provider payloads | Counts/status/timestamps | Collapse and sanitize; restrict raw access | Audit any raw-payload access |
| `AnalysisHistory.raw_result` | Raw report/model/provider context | Summary fields only | Collapse; sanitize; role restrict | Audit report-detail/raw-context view |
| `AnalysisHistory.news_content` | Potentially copyrighted or sensitive context | Short excerpt/count/source summary | Collapse and truncate | Audit full detail access |
| `AnalysisHistory.context_snapshot` | Provider/market/LLM context payload | Safe metadata only | Collapse and sanitize | Audit raw context view |
| `RuleBacktestRun.strategy_text` | Prompt-like/user strategy text | Strategy hash/label/short preview | Collapse; restrict full text | Audit full strategy view |
| `parsed_strategy_json`, `entry_rule_json`, `exit_rule_json` | Strategy internals and prompts | Derived labels/counts | Collapse JSON | Audit detail view |
| Scanner diagnostics and AI interpretation metadata | Provider failures, user theme intent, model details | Status/count/source summary | Collapse and sanitize | Audit diagnostics drilldown |
| Raw provider/runtime payloads and URLs | Secrets, keys, PII, vendor details | Provider/status/reason only | `sanitize_url()` and `sanitize_message()` | Audit raw diagnostics access |
| Uploaded files/images/import files | Raw user/broker data | Metadata only: type, size bucket, hash, timestamps | Do not display raw content by default | Audit raw file access if retention exists |

## 8. Recommended admin projections

These are projection sketches only, not code or API contracts.

`AdminUserListItem`:

- `id`, `username`, `displayName`, `role`, `status`, `isActive`, `createdAt`, `updatedAt`, `lastSeenAt`, `lastActivityAt`, `sessionSummary`, `riskBadges`.

`AdminUserDetail`:

- `user`, `sessionSummary`, `recentSessions`, `activitySummary`, `analysisSummary`, `scannerSummary`, `backtestSummary`, `portfolioSummary`, `auditSummary`.
- Exclude password/session/token values.

`AdminSessionSummary`:

- `handle`, `userId`, `createdAt`, `lastSeenAt`, `expiresAt`, `revokedAt`, `status`, `legacyAdmin`, `transitional`, `actions`.
- `handle` must be hashed/truncated, not raw `session_id`.

`AdminActivityEvent`:

- `id`, `category`, `type`, `status`, `actor`, `target`, `subject`, `symbol`, `route`, `endpoint`, `provider`, `source`, `reason`, `summary`, `traceHandle`, `recordRefs`, `startedAt`, `finishedAt`, `durationMs`, `safeMetadata`.

`AdminPortfolioSummary`:

- `userId`, `accountCount`, `activeAccountCount`, `baseCurrencies`, `totalCash`, `totalMarketValue`, `totalEquity`, `realizedPnl`, `unrealizedPnl`, `fxStale`, `lastImportAt`, `lastSyncAt`, `ledgerCounts`, `brokerSyncSummary`.

`AdminHoldingItem`:

- `accountId`, `accountName`, `symbol`, `market`, `currency`, `quantity`, `avgCost`, `lastPrice`, `marketValueBase`, `unrealizedPnlBase`, `valuationCurrency`, `fxStatus`, `updatedAt`.

`AdminAnalysisSummary`:

- `id`, `ownerId`, `queryId`, `code`, `name`, `reportType`, `sentimentScore`, `operationAdvice`, `trendPrediction`, `analysisSummary`, `isTest`, `createdAt`, `rawAvailable`.

`AdminScannerRunSummary`:

- `id`, `ownerId`, `scope`, `market`, `profile`, `status`, `runAt`, `completedAt`, `universeName`, `shortlistSize`, `universeSize`, `preselectedSize`, `evaluatedSize`, `topSymbols`, `diagnosticsAvailable`.

`AdminBacktestSummary`:

- `id`, `ownerId`, `kind`, `code`, `status`, `runAt`, `completedAt`, `evalWindowDays`, `engineVersion`, `tradeCount`, `winRatePct`, `totalReturnPct`, `maxDrawdownPct`, `resultCount`, `strategyHash`, `rawAvailable`.

## 9. Gaps and follow-up questions

- No confirmed Admin User Directory API or user-detail aggregate API exists.
- `LLMUsage` has no confirmed `owner_id`; per-user cost/usage governance needs a correlation plan through task/query/execution metadata.
- `ExecutionLogSession` has no first-class actor/user columns; actor attribution is currently in sanitized summary/business-event metadata.
- `PortfolioTrade`, `PortfolioCashLedger`, `PortfolioCorporateAction`, positions, lots, snapshots, and FX rows are account-linked rather than directly user-linked; future admin reads must join through owner-scoped `PortfolioAccount`.
- Broker sync `payload_json` and `sync_metadata_json` need explicit schema classification before any raw admin drilldown.
- Analysis `raw_result`, `news_content`, and `context_snapshot` need product-specific retention/redaction rules.
- Scanner `summary_json`, `diagnostics_json`, and candidate JSON fields can be large and may need pagination, JSON-size caps, and indexes or materialized summaries.
- Rule backtest full `strategy_text` should be treated as prompt-like user content; support-admin visibility may need capability gates.
- Existing `include_all_owners` repository flags are implementation seams, not admin API authorization by themselves.
- Future admin access to user portfolio, raw report context, raw logs, or broker sync payloads should require reason capture and audit events.
- Performance concerns: user detail aggregation across sessions, activity, analysis, scanner, backtest, and portfolio should be paginated and count-first, not an eager full join.

## 10. Recommended next tasks

- Admin User Directory API implementation.
- Admin Activity Timeline API design/implementation.
- Admin Portfolio Visibility API design/implementation.
- Admin audit event model hardening.
- Frontend after backend contracts.
