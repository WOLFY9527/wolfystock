# Broker Order Trade Redaction Release Evidence Checklist

Date: 2026-06-12
Validation profile: `PROFILE_BROKER_PROTECTED_SANITIZER`

This checklist records targeted release-review evidence for broker, order,
trade, account, and execution redaction boundaries. It is review support only:
it does not approve public launch, does not prove live broker connectivity, does
not add order placement, and does not change broker execution behavior.

Current release posture: **NO-GO** for broad/public broker, order, or trade
exposure until target-environment evidence is accepted separately.

## Scope

Covered by this evidence slice:

- Offline operator evidence artifact sanitization for broker/order/trade JSON.
- Portfolio import preview and commit API response redaction for broker file
  artifacts, including IBKR XML and legacy broker CSV imports.
- User-owned broker connection metadata redaction for secret-like sync metadata.
- Admin portfolio safe projections for summary, holdings, activity, account
  detail, and related audit metadata.
- Release documentation that keeps broker/order/trade launch posture gated.

Explicitly not covered:

- Live broker calls, live session validation, or broker credential inspection.
- Order placement, cancel, fill, routing, execution, or account mutation
  semantics.
- Provider ordering, fallback, cache behavior, auth/RBAC/session behavior,
  database migrations, frontend redesign, notification delivery, or public
  launch approval.
- Full browser-visible release-candidate proof, full log export proof,
  owner-visible broker connection/sync/ledger field classification, and final
  release-candidate export proof.

## Synthetic Fixture Policy

- Use synthetic values only.
- Do not copy real broker account IDs, order IDs, request IDs, execution IDs,
  account labels, broker URLs, tokens, raw broker payloads, or session material
  into tests, docs, logs, or artifacts.
- Synthetic values should include explicit `must-not-leak` or test-only labels
  so reviewers can distinguish fixtures from real broker material.
- Sanitized findings may expose bounded categories, reason codes, counts, and
  field labels only. Raw field names are redacted when they themselves indicate
  sensitive broker/order/account material.

## Tested Boundaries

| Surface | Evidence | Redaction guarantee |
| --- | --- | --- |
| Offline operator evidence JSON | `tests/test_evidence_artifact_sanitize.py::test_broker_order_artifact_ids_payloads_urls_and_tokens_are_redacted` | `brokerAccountRef`, `accountId`, `orderId`, `requestId`, `accountMetadata`, broker endpoint URL fields, `executionPayload`, and token/header fields are replaced with `<redacted>` or bounded findings; raw values and raw sensitive field names are absent from stdout and sanitized output. |
| Offline import/export artifact aliases | `tests/test_evidence_artifact_sanitize.py::test_broker_import_export_alias_fields_are_redacted`; `tests/test_evidence_artifact_sanitize.py::test_broker_import_export_freeform_identifiers_are_redacted`; `tests/test_evidence_safety.py::test_path_label_redacts_broker_order_account_artifact_names` | Broker import/export-style aliases such as `brokerApiUrl`, `accountNumber`, `orderRef`, `permId`, free-form broker/order/request/account-label text, and broker/order/account artifact filenames are redacted without echoing raw labels or values in sanitizer output. |
| Member portfolio import preview responses | `tests/test_portfolio_api.py::PortfolioApiTestCase::test_broker_import_preview_and_commit_redact_browser_artifact_identifiers`; `tests/test_portfolio_api.py::PortfolioApiTestCase::test_csv_import_preview_and_commit_redact_trade_ids_and_fingerprints` | `/api/v1/portfolio/imports/parse` and `/api/v1/portfolio/imports/csv/parse` preserve normalized trade/cash/corporate-action shape while redacting raw broker account refs, execution/order/request IDs, trade UIDs, dedup hashes, import fingerprints, broker URLs, tokens, and account labels from browser/API response artifacts. |
| Member portfolio import commit responses | `tests/test_portfolio_api.py::PortfolioApiTestCase::test_broker_import_preview_and_commit_redact_browser_artifact_identifiers`; `tests/test_portfolio_api.py::PortfolioApiTestCase::test_csv_import_preview_and_commit_redact_trade_ids_and_fingerprints` | `/api/v1/portfolio/imports/commit`, duplicate-import commit responses, and `/api/v1/portfolio/imports/csv/commit` redact commit metadata and errors/warnings without changing commit, dedup, broker-connection linking, or dry-run semantics. |
| User/member broker connection metadata | `tests/test_portfolio_api.py::PortfolioApiTestCase::test_broker_connection_read_payload_redacts_sensitive_metadata` | Secret-like `sync_metadata` values such as API key, nested token, and bearer text are masked in create/list responses. Existing member response contract still includes the user-provided `broker_account_ref`; that is not public-launch acceptance. |
| Member IBKR sync error path | `tests/test_portfolio_api.py::PortfolioApiTestCase::test_ibkr_sync_endpoint_sanitizes_secret_like_error_text` | Secret-like session text returned by the broker sync service is masked before API error output. |
| Admin portfolio safe projections | `tests/api/test_admin_portfolio.py::AdminPortfolioApiTestCase::test_admin_portfolio_export_redaction_matrix_excludes_raw_payloads_and_secrets` | Admin summary, holdings, activity, and account-detail outputs omit raw broker account refs, position refs, import fingerprints, trade UIDs, dedup hashes, raw payload JSON, sync metadata JSON, broker URLs, request/order IDs, execution payloads, tokens, and broker account labels. Broker account references are projected only as bounded hash handles such as `acct_<hash-prefix>`. |
| Admin audit metadata for portfolio views | `tests/api/test_admin_portfolio.py` safe JSON and audit assertions | Admin portfolio view audit rows include bounded actor/action context and exclude raw broker refs, sync metadata JSON, payload JSON, and secret-like fixture values. |

## Release Evidence Checklist

Before any broader release reviewer can consider this area ready, attach
sanitized evidence for all of the following:

- [x] Current automated evidence uses only synthetic broker/order/trade redaction
  fixtures in automated tests.
- [x] Offline artifact sanitizer rejects or redacts broker account IDs, order
  IDs, request IDs, execution IDs, account metadata, tokens, endpoint URLs, and
  raw broker/execution payloads.
- [x] Portfolio import preview and commit API responses redact broker refs,
  order/execution/request IDs, import fingerprints, raw payload markers,
  broker URLs, tokens, account labels, trade UIDs, and dedup hashes from
  response artifacts while preserving import execution semantics.
- [ ] User/member API surfaces are classified by response contract, including
  whether a field is owner-visible metadata or public/admin-safe metadata.
- [ ] Admin-safe broker/portfolio surfaces expose bounded hash handles or counts
  only, not raw broker account refs or payloads.
- [ ] Logs and operator evidence contain bounded reason codes, counts, and
  review labels only.
- [ ] Browser-visible panels and release-candidate exports have no raw broker
  account/order/request IDs, raw broker URLs, raw payloads, tokens, or account
  labels. Current API response redaction is browser-like evidence only, not a
  full DOM/release-candidate export pass.
- [ ] Sync/import failure paths sanitize exception text, request context, and
  broker payload summaries beyond the targeted import response warnings/errors
  covered here.
- [ ] `scripts/release_secret_scan.sh` passes on the release candidate.
- [ ] Any remaining raw owner-visible broker reference behavior is explicitly
  documented as not public/admin-safe and not a launch approval.

## Remaining NO-GO

This evidence slice does not close the broker/order/trade launch blocker.
Public launch remains **NO-GO** until reviewers accept target-environment,
release-candidate evidence for API, logs, reports, browser DOM, exports,
full sync/import failure paths, owner-visible field classification, and
operator evidence packets.

Stop future work and request a separate scoped decision if proving a boundary
would require real broker credentials, live broker payloads, a broad
execution-path refactor, product-owner judgment about safe field exposure, or
any change to order placement, cancel, fill, routing, or broker sync semantics.
