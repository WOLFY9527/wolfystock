# T514 Backend Canonical Failure Census

> Release status: **NO_GO**. This is a failure census and remediation plan, not a release waiver.

## Scope and authority

- Base commit: `72a57aba7c96325a8d177d049469438526d104e1` (tree `69f8f563aaeab9e12b9c9e9fb9031775425a0524`)
- T512 comparison: `731a6624b88871f8ac616c6e2f430b9ed70ad90d` (tree `8cc98ca6ae2c8558ae60b2fa4c6cebd785017c6d`)
- Authoritative workflow: `Gate - backend-canonical` in `.github/workflows/release.yml`.
- Executed command: `CI=true ./scripts/ci_gate.sh`.
- Chain: `ci_gate.sh` re-enters through `./wolfy exec --profile test`; preflight, critical lint, syntax, `test.sh code`, `test.sh yfinance`, then `python -m pytest --domain-topology-verify-full`.
- Raw evidence remains outside the repository at `/tmp/t514-backend-canonical-census`; no raw logs, caches, JUnit, or private host paths are committed.

The wrapper replaces external `PYTEST_ADDOPTS` with its run-scoped cache option and has no canonical reporting passthrough. The capture has stdout/stderr, short tracebacks, warning summary, suite duration, timestamps, exit code, SHA/tree, and node IDs, but no JUnit XML or per-test duration ranking. The authoritative command was not substituted.

## Environment identity

| Identity | Value |
| --- | --- |
| environmentFingerprint | `30939cb3ec09cf379c387aa7fd118adf339479cb92a37e10148d396422318ae1` |
| pythonInputFingerprint | `c4aad7f7f24664933601d7513834f91dbbf0298a46159ec091a1f88174eaa448` |
| pythonInstalledFingerprint | `c6b6d2d8634383e4a9ff0aae054b7415d787b252542e50c3dc43c02dba5aa28a` |
| webInputFingerprint | `af3043eee3a5cdb342dc5f6c91a8ac82a9455dc6a3acd811fa50d317d6ad2f32` |
| webInstalledFingerprint | `00915a7ae081327351f3af9122bc0a0293d63c66c18184d34089f71c2173ad20` |
| pythonLockContentHash | `7a3c9f1c582c0efb5ae48ae4871cb4cae77db9c257558cbf9af2c454013a46f4` |
| selectedLock | `requirements-python311-dev.lock` |
| selectedTarget | `os=Darwin, architecture=arm64, implementation=CPython, pythonVersion=3.11, abi=cp311, platform=macosx_15_0_arm64` |
| selectedProfile | `development` |
| selectedProjection | `darwin-arm64-cpython311-development` |
| selectedProjectionHash | `00e4a8e4fe678f527848c22760acab441f410b8ebd5ba3cd2b7520d390bc0b89` |
| resolver | `implementation=uv, version=0.11.19` |
| bootstrapNetworkUsed | `false` |
| comparisonIdentityMatch | `true` |

Qualification sequence completed before both captures:

1. `./wolfy lock python --check`
2. `./wolfy bootstrap --ensure --offline`
3. `./wolfy env verify`
4. `./wolfy qualify-env`

## Canonical result

| Commit | Collected | Passed | Failed | Skipped | Errors | Warnings | Subtests passed | Exit | Pytest duration |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| T513/current | 8036 | 7629 | 396 | 23 | 6 | 11 | 705 | 1 | 620.23s |
| T512 | 7994 | 7587 | 396 | 23 | 6 | 11 | 705 | 1 | 599.61s |

- Current capture: `2026-07-18T07:46:39Z` to `2026-07-18T07:57:32Z`; 653 wall-clock seconds.
- Failure accounting: 378 failed collected nodes plus 18 failed subtests equals 396 failures; 6 fixture setup errors; 0 collection/import errors.
- Classification accounting: **19 families, 396 failures, 6 errors, 0 unclassified nodes, 0 duplicate assignments**.
- Topology context: `knownBaselineFailures` has 223 registry entries and 124 current outcomes match it. It is not a waiver; all 402 outcomes block release and the registry was not modified.

## Family summary

| Family | Category | Failures | Errors | Owner | Root-cause summary | Risk |
| --- | --- | ---: | ---: | --- | --- | --- |
| T514-F01 | environment/configuration contract | 46 | 0 | Python dependency and environment tooling | Tests and services write Parquet, but the selected reviewed development projection contains neither supported engine. | high |
| T514-F02 | provider/network-boundary failure | 105 | 0 | Provider adapters and shared UAT isolation boundary | The profile correctly denies live providers, but guard placement precedes unit mock/injection seams; caught guard errors also collapse into unavailable assertions. | high |
| T514-F03 | environment/configuration contract | 9 | 0 | Managed test environment and cache/readiness fixtures | The test profile fixes feature flags and settings are captured before tests attempt to vary them. | medium |
| T514-F04 | auth/RBAC expectation failure | 49 | 0 | Auth, RBAC, route access policy, and admin APIs | Tests assume coarse admin or guest access while current routes require explicit capabilities and fail closed earlier. | critical |
| T514-F05 | runtime/container ownership failure | 1 | 6 | Runtime composition and FastAPI lifecycle | Container ownership moved into explicit composition, but six fixtures patch the former api.app symbol and one caller uses dependencies before start. | high |
| T514-F06 | stale test and product readiness contract | 10 | 0 | Application routing and admin surface readiness | Routers are nested after composition while route tests and readiness inventory traverse only the outer layer. | medium |
| T514-F07 | database/storage isolation failure | 5 | 0 | SQLite storage lifecycle and identity fixtures | Tests reach a fresh or differently owned SQLite database without the schema and bootstrap rows expected by fixtures. | high |
| T514-F08 | environment/fixture contract | 17 | 0 | Restore drill fixtures and managed temp directories | pytest tmp_path is under the managed cache run root while the drill accepts only OS temp-like roots. | high |
| T514-F09 | stale documentation contract | 10 | 0 | Canonical operator and data-reliability documentation | Tests reference six canonical document targets that no longer exist at the asserted paths. | medium |
| T514-F10 | environment/tooling contract | 1 | 0 | Managed test environment PATH | The hermetic PATH excludes the available ripgrep executable required by this test. | medium |
| T514-F11 | stale governance contract | 16 | 0 | Architecture and validation ownership governance | New owner paths, schema imports, provider-heavy services, and registry entries lack reviewed inventory updates. | high |
| T514-F12 | genuine product behavior regression | 30 | 0 | Market overview, regime, rotation, and evidence services | Evidence and provider-port normalization changed labels, authority fields, freshness, reason codes, and readiness projections. | critical |
| T514-F13 | genuine product behavior regression | 22 | 0 | Scanner scoring and run diagnostics | Score caps, provenance tokens, empty-run reasons, and comparable-run readiness no longer match protected scanner contracts. | critical |
| T514-F14 | genuine product behavior regression | 7 | 0 | Backtest storage and support exports | Stored-first readback and support bundles disagree on lineage, live-storage fallback, export keys, and readiness. | critical |
| T514-F15 | genuine product behavior regression | 5 | 0 | Portfolio ownership and risk diagnostics | Owner selection and managed-disabled FX behavior no longer match isolation and readiness expectations. | critical |
| T514-F16 | release qualification contract | 11 | 0 | Operator evidence and staging qualification | Evidence categories and qualification scripts evolved without synchronized preflight, scorecard, and smoke expectations. | high |
| T514-F17 | genuine product behavior regression | 13 | 0 | Analysis orchestration and AI safety | Analysis/runtime refactors changed dispatch, default wording, error behavior, and public projection. | critical |
| T514-F18 | genuine product behavior regression | 7 | 0 | Homepage service contracts | Service/schema additions changed capability sets, section shape, labels, and sanitized text without synchronized contracts. | high |
| T514-F19 | stale test and product adapter contract | 32 | 0 | Stock service and normalized provider adapters | Provider-port normalization changed adapter calls, names, fallbacks, and public source fields beyond the established contract. | critical |

## Family evidence

### T514-F01 - Missing reviewed Parquet engine in the managed Python projection

- Count/phase: 46 failures, 0 errors; `call`.
- Representative nodes: `tests/test_market_regime_evidence_service.py::test_full_adjusted_ohlcv_and_quote_snapshot_returns_ok_risk_on_confirming`, `tests/api/test_market_regime_read_model_endpoint.py::test_market_regime_evidence_pack_endpoint_returns_ready_computed_contract`, `tests/api/test_market_regime_read_model_endpoint.py::test_market_regime_read_model_endpoint_resolves_configured_quote_snapshot_cache`.
- Affected test files (11): `tests/api/test_market_regime_read_model_endpoint.py`, `tests/scripts/test_data_chain_operator_verifier.py`, `tests/scripts/test_local_data_cache_schema_verifier.py`, `tests/scripts/test_market_regime_evidence_verifier.py`, `tests/scripts/test_market_regime_read_model_verifier.py`, `tests/test_backtest_service.py`, `tests/test_historical_ohlcv_readiness_service.py`, `tests/test_market_data_readiness_diagnostics.py`, `tests/test_market_regime_evidence_service.py`, `tests/test_market_regime_read_model_service.py`, `tests/test_market_scanner_service.py`.
- Exception mix: `ImportError`=46.
- Stable anchor: ImportError: no usable pyarrow or fastparquet engine.
- Shared fixtures/modules: `pandas parquet writer`, `requirements-python311-dev.lock`, `managed development snapshot`.
- Owner/root cause/confidence: Python dependency and environment tooling; Tests and services write Parquet, but the selected reviewed development projection contains neither supported engine. Confidence: `high`.
- Reproduction: isolation 1 failed with the Parquet engine ImportError; small batch 2 failed with the same ImportError; order: not indicated; isolation and batch matched the canonical anchor.
- External requirements: no network, real database, credentials, or external service.
- Fix layer: dependency intent, lock projection, and environment tooling.
- Protected semantics: Preserve hash-locked cross-target authority; no ad hoc install or weakened offline bootstrap.
- Validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/api/test_market_regime_read_model_endpoint.py tests/scripts/test_local_data_cache_schema_verifier.py`
- Risk: `high`.

### T514-F02 - No-live-provider guard preempts mock and injected transport seams

- Count/phase: 105 failures, 0 errors; `call`.
- Representative nodes: `tests/test_official_macro_transport.py::test_fetch_fred_observation_points_reports_timeout`, `tests/test_alpaca_fetcher.py::AlpacaFetcherTestCase::test_endpoint_reachability_classifies_proxy_timeout_without_message_leak`, `tests/test_alpaca_fetcher.py::AlpacaFetcherTestCase::test_endpoint_reachability_is_sanitized_and_payload_free`.
- Affected test files (19): `tests/test_alpaca_fetcher.py`, `tests/test_analysis_api_contract.py`, `tests/test_data_fetcher_manager_alpaca.py`, `tests/test_data_fetcher_manager_twelve_data.py`, `tests/test_fetcher_logging.py`, `tests/test_image_stock_extractor_litellm.py`, `tests/test_market_analyzer_generate_text.py`, `tests/test_market_overview_provider_deadlines.py`, `tests/test_official_macro_transport.py`, `tests/test_provider_runtime_contracts.py`, `tests/test_search_provider_fallbacks.py`, `tests/test_search_searxng.py`, `tests/test_search_tavily_provider.py`, `tests/test_stock_structure_decision_service.py`, `tests/test_stooq_fallback.py`, `tests/test_tushare_fetcher_followups.py`, `tests/test_twelve_data_fetcher.py`, `tests/test_us_fundamentals_provider.py`, `tests/test_yfinance_us_indices.py`.
- Exception mix: `AssertionError`=57, `src.services.uat_provider_isolation.UatProviderIsolationError`=37, `data_provider.base.DataFetchError`=5, `TypeError`=4, `ValueError`=2.
- Stable anchor: UAT no-live-provider mode blocked a provider capability before the mocked transport result.
- Shared fixtures/modules: `src.services.uat_provider_isolation`, `provider transports`, `search and vision adapters`.
- Owner/root cause/confidence: Provider adapters and shared UAT isolation boundary; The profile correctly denies live providers, but guard placement precedes unit mock/injection seams; caught guard errors also collapse into unavailable assertions. Confidence: `medium-high`.
- Reproduction: isolation 1 failed under the guard; the same node passed after unsetting only WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS; small batch 7 failed/63 passed under the guard; all 70 passed after the one-variable ablation; order: not indicated; isolation and batch matched the canonical anchor.
- External requirements: no network, real database, credentials, or external service.
- Fix layer: product adapter seams plus provider tests; one shared UAT owner.
- Protected semantics: Keep outbound denial, no-live-provider fail-closed behavior, provider authority, credential redaction, and no fake payloads.
- Validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_official_macro_transport.py`
- Risk: `high`.

### T514-F03 - Hermetic feature flags override test-controlled configuration contracts

- Count/phase: 9 failures, 0 errors; `call`.
- Representative nodes: `tests/api/test_market_cache_import_boundary.py::test_env_set_before_first_access_deterministically_builds_lazy_singleton`, `tests/test_akshare_cn_ohlcv_cache_runtime.py::test_stock_service_default_disabled_cn_history_skips_general_fetcher_manager`, `tests/test_historical_ohlcv_cache_preflight.py::test_disabled_default_preflight_is_dry_run_without_provider_or_mutation`.
- Affected test files (4): `tests/api/test_market_cache_import_boundary.py`, `tests/test_akshare_cn_ohlcv_cache_runtime.py`, `tests/test_historical_ohlcv_cache_preflight.py`, `tests/test_market_cache_fallback_contracts.py`.
- Exception mix: `AssertionError`=8, `TypeError`=1.
- Stable anchor: managed disabled state observed where a monkeypatched configured state was expected.
- Shared fixtures/modules: `scripts/environment/runtime.py`, `immutable settings snapshots`, `market cache singleton`.
- Owner/root cause/confidence: Managed test environment and cache/readiness fixtures; The test profile fixes feature flags and settings are captured before tests attempt to vary them. Confidence: `high`.
- Reproduction: isolation 1 failed; small batch 2 failed; both deterministic orders preserved the same one failure; order: not order-dependent in A-B and B-A deterministic runs.
- External requirements: no network, real database, credentials, or external service.
- Fix layer: environment tooling and test fixture construction.
- Protected semantics: Keep the canonical profile offline, deterministic, and fail closed; no compatibility defaults.
- Validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/api/test_market_cache_import_boundary.py tests/test_historical_ohlcv_cache_preflight.py tests/test_market_cache_fallback_contracts.py`
- Risk: `medium`.

### T514-F04 - Explicit capability and production-ingress authorization contract drift

- Count/phase: 49 failures, 0 errors; `call`.
- Representative nodes: `tests/api/test_admin_security.py::AdminSecurityApiTestCase::test_authenticated_admin_security_write_accepts_after_valid_reauth`, `tests/api/test_admin_cost_summary.py::AdminCostSummaryApiTestCase::test_duplicate_summary_requires_cost_observability_capability`, `tests/api/test_admin_cost_summary.py::AdminCostSummaryApiTestCase::test_llm_ledger_summary_requires_cost_observability_capability`.
- Affected test files (11): `tests/api/test_admin_cost_summary.py`, `tests/api/test_admin_provider_circuit_diagnostics.py`, `tests/api/test_admin_quota_dry_run.py`, `tests/api/test_admin_security.py`, `tests/api/test_cn_provider_health.py`, `tests/api/test_market_data_readiness.py`, `tests/api/test_public_api_surface_safety.py`, `tests/api/test_runtime_api_edge_contracts.py`, `tests/api/test_security_launch_preflight.py`, `tests/test_auth_api.py`, `tests/test_multi_user_phase3.py`.
- Exception mix: `AssertionError`=48, `TypeError`=1.
- Stable anchor: 403 versus expected 200/401; admin_capability_required versus admin_reauth_required.
- Shared fixtures/modules: `api.deps capability checks`, `route access policy`, `admin security fixtures`.
- Owner/root cause/confidence: Auth, RBAC, route access policy, and admin APIs; Tests assume coarse admin or guest access while current routes require explicit capabilities and fail closed earlier. Confidence: `high`.
- Reproduction: isolation 1 failed with 403 versus 200; small batch 2 failed across admin security and cost capability checks; order: not indicated; isolation and batch matched the canonical anchor.
- External requirements: no network, real database, credentials, or external service.
- Fix layer: product authorization policy and tests after an explicit security decision.
- Protected semantics: Do not weaken auth, RBAC, reauthentication, sessions, admin protection, or fail-closed ingress.
- Validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/api/test_admin_security.py tests/api/test_runtime_api_edge_contracts.py tests/test_auth_api.py`
- Risk: `critical`.

### T514-F05 - Explicit RuntimeContainer ownership left stale patch and startup contracts

- Count/phase: 1 failures, 6 errors; `call`, `setup`.
- Representative nodes: `tests/api/test_market_intelligence_payload_smoke.py::test_authenticated_us_breadth_payload_smoke_uses_polygon_contract_without_exchange_claim`, `tests/api/test_market_intelligence_payload_smoke.py::test_authenticated_cn_flows_payload_smoke_keeps_authorized_feed_diagnostic_only`, `tests/api/test_market_intelligence_payload_smoke.py::test_authenticated_crypto_payload_smoke_marks_sidecar_observation_unavailable_not_score_grade`.
- Affected test files (2): `tests/api/test_market_intelligence_payload_smoke.py`, `tests/test_multi_user_phase3.py`.
- Exception mix: `AttributeError`=6, `RuntimeError`=1.
- Stable anchor: api.app no longer owns should_auto_start_crypto_realtime; RuntimeContainer is not started.
- Shared fixtures/modules: `api.app`, `api.deps`, `src.runtime.composition`, `TestClient lifespan`.
- Owner/root cause/confidence: Runtime composition and FastAPI lifecycle; Container ownership moved into explicit composition, but six fixtures patch the former api.app symbol and one caller uses dependencies before start. Confidence: `high`.
- Reproduction: isolation 1 setup error; small batch 6 setup errors; order: not indicated; isolation and batch matched the canonical anchor.
- External requirements: no network, real database, credentials, or external service.
- Fix layer: test patch targets and product lifecycle ownership.
- Protected semantics: Keep explicit injection, start-before-use, rollback, idempotent close, and no lazy fallback container.
- Validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/api/test_market_intelligence_payload_smoke.py tests/test_multi_user_phase3.py::MultiUserAuthorizationApiTestCase::test_admin_only_surfaces_are_backend_protected`
- Risk: `high`.

### T514-F06 - Nested FastAPI router discovery and readiness inventory drift

- Count/phase: 10 failures, 0 errors; `call`.
- Representative nodes: `tests/api/test_cn_provider_health.py::test_cn_provider_health_route_is_exposed`, `tests/api/test_admin_surface_readiness.py::test_market_decision_cockpit_readiness_accepts_either_degraded_inputs_or_surface_summary`, `tests/api/test_admin_surface_readiness.py::test_market_decision_cockpit_readiness_fails_closed_when_degraded_state_shape_is_missing`.
- Affected test files (4): `tests/api/test_admin_surface_readiness.py`, `tests/api/test_cn_provider_health.py`, `tests/api/test_daily_intelligence_endpoint.py`, `tests/api/test_provider_fit_advisor.py`.
- Exception mix: `AssertionError`=10.
- Stable anchor: raw app.routes sees only docs routes, or readiness reports missing_contract.
- Shared fixtures/modules: `FastAPI included routers`, `API endpoints`, `admin surface readiness service`.
- Owner/root cause/confidence: Application routing and admin surface readiness; Routers are nested after composition while route tests and readiness inventory traverse only the outer layer. Confidence: `high`.
- Reproduction: isolation 1 failed; small batch 3 route-discovery failures; order: not indicated; isolation and batch matched the canonical anchor.
- External requirements: no network, real database, credentials, or external service.
- Fix layer: test route enumeration and product readiness traversal.
- Protected semantics: Preserve hidden-route OpenAPI policy, auth dependencies, read-only readiness, and endpoint ownership.
- Validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/api/test_cn_provider_health.py tests/api/test_daily_intelligence_endpoint.py tests/api/test_provider_fit_advisor.py tests/api/test_admin_surface_readiness.py`
- Risk: `medium`.

### T514-F07 - Ephemeral SQLite bootstrap and storage isolation drift

- Count/phase: 5 failures, 0 errors; `call`.
- Representative nodes: `tests/api/test_admin_logs.py::AdminLogsApiTestCase::test_business_event_list_requires_auth_and_admin_can_read_classification_fields`, `tests/api/test_admin_real_auth_session_smoke.py::AdminRealAuthSessionSmokeTestCase::test_real_bootstrap_session_reaches_admin_route_and_logged_out_fails_closed`, `tests/api/test_admin_users.py::AdminUsersApiTestCase::test_user_directory_privacy_export_projection_is_read_only_and_sanitized`.
- Affected test files (4): `tests/api/test_admin_logs.py`, `tests/api/test_admin_real_auth_session_smoke.py`, `tests/api/test_admin_users.py`, `tests/test_postgres_phase_a.py`.
- Exception mix: `AssertionError`=4, `sqlalchemy.exc.OperationalError`=1.
- Stable anchor: sqlite no such table app_users or expected bootstrap rows absent.
- Shared fixtures/modules: `src.storage`, `SQLAlchemy session lifecycle`, `ephemeral test database`.
- Owner/root cause/confidence: SQLite storage lifecycle and identity fixtures; Tests reach a fresh or differently owned SQLite database without the schema and bootstrap rows expected by fixtures. Confidence: `medium-high`.
- Reproduction: isolation 1 failed with missing app_users; small batch 2 Phase A storage failures; order: not indicated; isolation and batch matched the canonical anchor.
- External requirements: no network, real database, credentials, or external service.
- Fix layer: storage fixture and lifecycle code.
- Protected semantics: No real PostgreSQL, no cross-test state; preserve owner scope and transactional cleanup.
- Validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/api/test_admin_logs.py tests/test_postgres_phase_a.py`
- Risk: `high`.

### T514-F08 - Managed run temp root conflicts with restore target safety allowlist

- Count/phase: 17 failures, 0 errors; `call`.
- Representative nodes: `tests/test_backup_restore_drill_check.py::test_backup_restore_drill_check_accepts_explicit_local_safe_test_dsn_without_leaking_value`, `tests/test_backup_restore_drill_check.py::test_backup_restore_drill_check_accepts_real_restore_evidence_artifact`, `tests/test_backup_restore_drill_check.py::test_backup_restore_drill_check_does_not_mutate_files`.
- Affected test files (1): `tests/test_backup_restore_drill_check.py`.
- Exception mix: `AssertionError`=17.
- Stable anchor: [FAIL] Unsafe restore target refused.
- Shared fixtures/modules: `scripts/backup_restore_drill_check.sh`, `pytest tmp_path`, `managed run root`.
- Owner/root cause/confidence: Restore drill fixtures and managed temp directories; pytest tmp_path is under the managed cache run root while the drill accepts only OS temp-like roots. Confidence: `high`.
- Reproduction: isolation 1 failed; small batch 2 failed with unsafe-target refusal; order: not indicated; isolation and batch matched the canonical anchor.
- External requirements: no network, real database, credentials, or external service.
- Fix layer: test fixture or managed temp-root placement.
- Protected semantics: Do not broaden restore safety, allow overwrite, expose DSNs, or touch a real database.
- Validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_backup_restore_drill_check.py`
- Risk: `high`.

### T514-F09 - Canonical documentation targets were removed or renamed

- Count/phase: 10 failures, 0 errors; `call`.
- Representative nodes: `tests/test_operator_evidence_command_docs.py::test_operator_evidence_docs_reference_existing_scripts`, `tests/test_data_coverage_matrix_consumer_projection_examples.py::test_consumer_projection_examples_doc_stays_product_language`, `tests/test_data_coverage_surface_fixtures.py::test_surface_fixture_doc_matches_catalog_and_stays_consumer_safe`.
- Affected test files (6): `tests/test_data_coverage_matrix_consumer_projection_examples.py`, `tests/test_data_coverage_surface_fixtures.py`, `tests/test_market_intelligence_smoke_checklist.py`, `tests/test_operator_evidence_command_docs.py`, `tests/test_provider_capability_matrix.py`, `tests/test_quant_duckdb_service.py`.
- Exception mix: `AssertionError`=5, `FileNotFoundError`=5.
- Stable anchor: expected repository-relative docs target is missing.
- Shared fixtures/modules: `documentation contract tests`, `audit/data-reliability/operations docs`.
- Owner/root cause/confidence: Canonical operator and data-reliability documentation; Tests reference six canonical document targets that no longer exist at the asserted paths. Confidence: `high`.
- Reproduction: isolation 1 failed; small batch 2 failed and 4 passed; order: not indicated; isolation and batch matched the canonical anchor.
- External requirements: no network, real database, credentials, or external service.
- Fix layer: canonical docs and tests after deciding the authoritative path.
- Protected semantics: No placeholder readiness, one-off reports, private links, or duplicate authorities.
- Validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_operator_evidence_command_docs.py tests/test_data_coverage_surface_fixtures.py tests/test_market_intelligence_smoke_checklist.py`
- Risk: `medium`.

### T514-F10 - Managed test PATH omits a repository-required static-analysis tool

- Count/phase: 1 failures, 0 errors; `call`.
- Representative nodes: `tests/services/test_home_source_provenance_sidecar.py::test_helper_runtime_integration_is_limited_to_home_response_assembly`.
- Affected test files (1): `tests/services/test_home_source_provenance_sidecar.py`.
- Exception mix: `FileNotFoundError`=1.
- Stable anchor: FileNotFoundError: rg.
- Shared fixtures/modules: `scripts/environment/runtime.py`, `home source provenance static check`.
- Owner/root cause/confidence: Managed test environment PATH; The hermetic PATH excludes the available ripgrep executable required by this test. Confidence: `high`.
- Reproduction: isolation 1 failed; small batch full file: 1 failed and 6 passed; order: not indicated; isolation and batch matched the canonical anchor.
- External requirements: no network, real database, credentials, or external service.
- Fix layer: environment tooling or repository-owned tool invocation.
- Protected semantics: Keep PATH hermetic; no private absolute paths or silent tool fallback.
- Validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/services/test_home_source_provenance_sidecar.py`
- Risk: `medium`.

### T514-F11 - Reviewed architecture, ownership, and provider inventories drifted

- Count/phase: 16 failures, 0 errors; `call`.
- Representative nodes: `tests/test_backend_modular_import_boundaries.py::test_provider_heavy_service_file_inventory_is_explicit`, `tests/scripts/test_validation_owner_manifest.py::test_exhaustive_tracked_path_inventory_has_no_mapping_gap`, `tests/scripts/test_validation_owner_manifest.py::test_shadow_owners_never_downgrade_any_tracked_legacy_escalation`.
- Affected test files (9): `tests/scripts/test_validation_owner_manifest.py`, `tests/test_backend_modular_import_boundaries.py`, `tests/test_contracts_namespace.py`, `tests/test_evidence_cli_contracts.py`, `tests/test_options_structure_contract.py`, `tests/test_professional_data_capability_registry_service.py`, `tests/test_provider_credential_inventory.py`, `tests/test_provider_fit_metadata.py`, `tests/test_provider_runtime_boundary.py`.
- Exception mix: `AssertionError`=16.
- Stable anchor: expected and found static inventory sets differ.
- Shared fixtures/modules: `validation owners`, `modular import tests`, `provider capability registries`.
- Owner/root cause/confidence: Architecture and validation ownership governance; New owner paths, schema imports, provider-heavy services, and registry entries lack reviewed inventory updates. Confidence: `high`.
- Reproduction: isolation 1 failed; small batch 2 failed across architecture and owner inventory; order: not indicated; isolation and batch matched the canonical anchor.
- External requirements: no network, real database, credentials, or external service.
- Fix layer: governance sources and tests after architecture review.
- Protected semantics: Do not blindly accept dependencies, downgrade escalation, change topology baseline, or broaden provider authority.
- Validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_backend_modular_import_boundaries.py tests/scripts/test_validation_owner_manifest.py tests/test_provider_fit_metadata.py`
- Risk: `high`.

### T514-F12 - Market evidence authority, freshness, and readiness contracts diverged

- Count/phase: 30 failures, 0 errors; `call`.
- Representative nodes: `tests/test_market_overview_evidence_snapshot.py::MarketOverviewEvidenceSnapshotTestCase::test_evidence_snapshot_reuses_shared_provider_helper_without_widening_contract`, `tests/api/test_market_cn_breadth.py::MarketCnBreadthApiTestCase::test_cn_breadth_falls_back_for_tickflow_guard_reason_codes::subtest(reason='tickflow_market_stats_empty')`, `tests/api/test_market_cn_breadth.py::MarketCnBreadthApiTestCase::test_cn_breadth_falls_back_for_tickflow_guard_reason_codes::subtest(reason='tickflow_market_stats_malformed')`.
- Affected test files (12): `tests/api/test_market_cn_breadth.py`, `tests/api/test_market_freshness.py`, `tests/api/test_market_futures.py`, `tests/api/test_market_fx_commodities.py`, `tests/api/test_market_rotation_radar.py`, `tests/api/test_market_temperature.py`, `tests/api/test_market_us_breadth.py`, `tests/test_market_overview_core_quote_repair.py`, `tests/test_market_overview_evidence_snapshot.py`, `tests/test_market_regime_projection_runtime_verifier.py`, `tests/test_market_rotation_radar_service.py`, `tests/test_market_temperature_input_snapshot.py`.
- Exception mix: `AssertionError`=27, `KeyError`=2, `unknown`=1.
- Stable anchor: source authority, freshness, readiness, or evidence projection differs.
- Shared fixtures/modules: `market overview services`, `source observation facts`, `evidence API schemas`.
- Owner/root cause/confidence: Market overview, regime, rotation, and evidence services; Evidence and provider-port normalization changed labels, authority fields, freshness, reason codes, and readiness projections. Confidence: `medium-high`.
- Reproduction: isolation 1 failed; small batch 2 failed; order: not indicated; isolation and batch matched the canonical anchor.
- External requirements: no network, real database, credentials, or external service.
- Fix layer: product market/evidence code and explicit contract tests.
- Protected semantics: Preserve source authority, immutable observation facts, field freshness, no fake data, and no trading advice.
- Validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_market_overview_evidence_snapshot.py tests/api/test_market_freshness.py tests/test_market_regime_projection_runtime_verifier.py`
- Risk: `critical`.

### T514-F13 - Scanner scoring, diagnostics, and simulation semantics diverged

- Count/phase: 22 failures, 0 errors; `call`.
- Representative nodes: `tests/test_market_scanner_service.py::MarketScannerServiceTestCase::test_apply_score_caps_and_explainability_preserves_authorized_non_proxy_scores`, `tests/test_ai_evidence_cross_engine_contracts.py::test_reason_code_and_quality_flag_regressions_stay_stable_for_incomplete_evidence`, `tests/test_market_scanner_ops_service.py::MarketScannerOperationsServiceTestCase::test_manual_us_empty_run_persists_only_coarse_empty_reason_after_local_filters`.
- Affected test files (5): `tests/test_ai_evidence_cross_engine_contracts.py`, `tests/test_market_scanner_ops_service.py`, `tests/test_market_scanner_service.py`, `tests/test_scanner_strategy_simulation.py`, `tests/test_watchlist_score_refresh.py`.
- Exception mix: `AssertionError`=17, `KeyError`=4, `ValueError`=1.
- Stable anchor: score cap, source confidence, reason code, or simulation readiness differs.
- Shared fixtures/modules: `market scanner`, `scanner operations`, `strategy simulation`.
- Owner/root cause/confidence: Scanner scoring and run diagnostics; Score caps, provenance tokens, empty-run reasons, and comparable-run readiness no longer match protected scanner contracts. Confidence: `high`.
- Reproduction: isolation 1 failed; small batch 2 failed; order: not indicated; isolation and batch matched the canonical anchor.
- External requirements: no network, real database, credentials, or external service.
- Fix layer: scanner product code and tests.
- Protected semantics: Preserve scoring contributions, thresholds, ordering, live/fallback labels, and no fabricated returns.
- Validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_market_scanner_service.py tests/test_market_scanner_ops_service.py tests/test_scanner_strategy_simulation.py`
- Risk: `critical`.

### T514-F14 - Backtest stored-first evidence and readiness semantics diverged

- Count/phase: 7 failures, 0 errors; `call`.
- Representative nodes: `tests/test_rule_backtest_reopen_acceptance.py::RuleBacktestReopenAcceptanceTestCase::test_reopen_acceptance_legacy_fallback_surfaces_are_explicit_across_status_detail_history`, `tests/test_backtest_data_sufficiency_gate.py::BacktestDataSufficiencyGateTestCase::test_seeded_symbol_and_benchmark_adjusted_cache_unlocks_data110_execution`, `tests/test_backtest_regime_attribution_readiness.py::BacktestRegimeAttributionReadinessTestCase::test_support_export_index_discovers_readiness_export`.
- Affected test files (4): `tests/test_backtest_data_sufficiency_gate.py`, `tests/test_backtest_regime_attribution_readiness.py`, `tests/test_rule_backtest_reopen_acceptance.py`, `tests/test_rule_backtest_support_bundle_e2e.py`.
- Exception mix: `AssertionError`=7.
- Stable anchor: stored payload, support export, lineage, or readiness differs.
- Shared fixtures/modules: `rule backtest service`, `support exports`, `data sufficiency gate`.
- Owner/root cause/confidence: Backtest storage and support exports; Stored-first readback and support bundles disagree on lineage, live-storage fallback, export keys, and readiness. Confidence: `high`.
- Reproduction: isolation 1 failed; small batch 2 failed; order: not indicated; isolation and batch matched the canonical anchor.
- External requirements: no network, real database, credentials, or external service.
- Fix layer: backtest product code and stored-result tests.
- Protected semantics: Preserve fills, costs, metrics, benchmark, winner semantics, universe, and stored-result authority.
- Validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_rule_backtest_support_bundle_e2e.py tests/test_rule_backtest_reopen_acceptance.py tests/test_backtest_regime_attribution_readiness.py`
- Risk: `critical`.

### T514-F15 - Portfolio owner, FX, and readiness projections diverged

- Count/phase: 5 failures, 0 errors; `call`.
- Representative nodes: `tests/api/test_portfolio_owner_isolation.py::PortfolioOwnerIsolationApiTestCase::test_risk_drawdown_history_uses_authenticated_owner_context`, `tests/test_multi_user_phase3.py::MultiUserAuthorizationApiTestCase::test_portfolio_events_and_broker_connections_stay_owner_scoped`, `tests/test_portfolio_api_contract.py::PortfolioApiDiagnosticsContractTestCase::test_snapshot_endpoint_exposes_optional_diagnostics_fields`.
- Affected test files (4): `tests/api/test_portfolio_owner_isolation.py`, `tests/test_multi_user_phase3.py`, `tests/test_portfolio_api_contract.py`, `tests/test_portfolio_pr2.py`.
- Exception mix: `AssertionError`=5.
- Stable anchor: owner-scoped value, FX refresh status, or snapshot readiness differs.
- Shared fixtures/modules: `portfolio service`, `risk diagnostics`, `multi-user ownership`.
- Owner/root cause/confidence: Portfolio ownership and risk diagnostics; Owner selection and managed-disabled FX behavior no longer match isolation and readiness expectations. Confidence: `medium-high`.
- Reproduction: isolation 1 failed; small batch 2 failed; order: not indicated; isolation and batch matched the canonical anchor.
- External requirements: no network, real database, credentials, or external service.
- Fix layer: portfolio product code and owner fixtures.
- Protected semantics: Preserve accounts, cash, holdings, P&L, FX, cost basis, broker import, and ledger ownership.
- Validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/api/test_portfolio_owner_isolation.py tests/test_portfolio_api_contract.py tests/test_portfolio_pr2.py`
- Risk: `critical`.

### T514-F16 - Operator and release evidence contracts drifted

- Count/phase: 11 failures, 0 errors; `call`.
- Representative nodes: `tests/test_operator_evidence_preflight.py::test_synthetic_preflight_passes_with_review_required_non_approval_summary`, `tests/test_launch_acceptance_evidence.py::test_launch_acceptance_evidence_market_data_freshness_fallback_is_backed_by_repo_local_offline_anchors`, `tests/test_operator_evidence_gap_analyzer.py::test_complete_synthetic_fixture_produces_review_required_with_no_unsafe_leak`.
- Affected test files (7): `tests/test_launch_acceptance_evidence.py`, `tests/test_operator_evidence_gap_analyzer.py`, `tests/test_operator_evidence_preflight.py`, `tests/test_operator_evidence_workflow_smoke.py`, `tests/test_private_beta_acceptance_scorecard.py`, `tests/test_staging_ingress_smoke.py`, `tests/test_ws2_multi_instance_preflight.py`.
- Exception mix: `AssertionError`=11.
- Stable anchor: evidence category/count/status or dry-run assertion differs.
- Shared fixtures/modules: `operator preflight`, `private beta scorecard`, `staging ingress smoke`.
- Owner/root cause/confidence: Operator evidence and staging qualification; Evidence categories and qualification scripts evolved without synchronized preflight, scorecard, and smoke expectations. Confidence: `high`.
- Reproduction: isolation 1 failed; small batch 2 failed; order: not indicated; isolation and batch matched the canonical anchor.
- External requirements: no network, real database, credentials, or external service.
- Fix layer: release qualification scripts and tests.
- Protected semantics: Keep NO_GO default, synthetic-only evidence, redaction, bounded output, and no approval claims.
- Validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_operator_evidence_preflight.py tests/test_operator_evidence_workflow_smoke.py tests/test_staging_ingress_smoke.py`
- Risk: `high`.

### T514-F17 - Analysis orchestration, prompt, and public-safety contracts diverged

- Count/phase: 13 failures, 0 errors; `call`.
- Representative nodes: `tests/test_analysis_integration.py::TestAnalysisIntegration::test_trigger_analysis_flow_manual_name`, `tests/test_agent_executor.py::TestBuildUserMessage::test_basic_message`, `tests/test_agent_pipeline.py::TestAgentFactorySkillBaseline::test_explicit_empty_request_falls_back_to_primary_default_skill`.
- Affected test files (6): `tests/test_agent_executor.py`, `tests/test_agent_pipeline.py`, `tests/test_ai_decision_public_safety.py`, `tests/test_analysis_integration.py`, `tests/test_multi_agent.py`, `tests/test_system_config_service.py`.
- Exception mix: `AssertionError`=13.
- Stable anchor: task submission, public response, or safety wording differs.
- Shared fixtures/modules: `analysis endpoint`, `agent pipeline`, `system config LLM channel`.
- Owner/root cause/confidence: Analysis orchestration and AI safety; Analysis/runtime refactors changed dispatch, default wording, error behavior, and public projection. Confidence: `medium-high`.
- Reproduction: isolation 1 failed; small batch 2 failed; order: not indicated; isolation and batch matched the canonical anchor.
- External requirements: no network, real database, credentials, or external service.
- Fix layer: analysis product code and safety tests.
- Protected semantics: No raw model/provider leakage, no trading advice, no real model calls, no weakened public safety.
- Validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_analysis_integration.py tests/test_ai_decision_public_safety.py tests/test_agent_pipeline.py`
- Risk: `critical`.

### T514-F18 - Homepage public schema, taxonomy, and copy contracts diverged

- Count/phase: 7 failures, 0 errors; `call`.
- Representative nodes: `tests/test_homepage_section_layout_service.py::test_default_layout_serializes_stable_frontend_uat_contract`, `tests/test_homepage_capabilities_service.py::test_homepage_capabilities_contract_serializes_stable_version_and_capabilities`, `tests/test_homepage_capabilities_service.py::test_homepage_capabilities_default_flags_are_bounded`.
- Affected test files (3): `tests/test_homepage_capabilities_service.py`, `tests/test_homepage_public_copy_consistency.py`, `tests/test_homepage_section_layout_service.py`.
- Exception mix: `AssertionError`=5, `KeyError`=1, `TypeError`=1.
- Stable anchor: homepage capability state, taxonomy, schema shape, or public copy differs.
- Shared fixtures/modules: `homepage capabilities`, `section layout schema`, `public copy sanitizer`.
- Owner/root cause/confidence: Homepage service contracts; Service/schema additions changed capability sets, section shape, labels, and sanitized text without synchronized contracts. Confidence: `high`.
- Reproduction: isolation 1 failed; small batch 2 failed; order: not indicated; isolation and batch matched the canonical anchor.
- External requirements: no network, real database, credentials, or external service.
- Fix layer: homepage product/schema code and tests.
- Protected semantics: Preserve bounded taxonomy, no internal diagnostics, no secrets, and no trading advice.
- Validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_homepage_capabilities_service.py tests/test_homepage_section_layout_service.py tests/test_homepage_public_copy_consistency.py`
- Risk: `high`.

### T514-F19 - Normalized provider ports and stock response contracts diverged

- Count/phase: 32 failures, 0 errors; `call`.
- Representative nodes: `tests/test_stock_service_validation.py::StockServiceValidationTestCase::test_get_realtime_quote_maps_adapter_snapshot_without_provider_dto_leakage`, `tests/api/test_market_endpoint_provider_regressions.py::test_market_overview_macro_endpoint_returns_fallback_quickly_when_official_macro_hangs`, `tests/api/test_stock_history_endpoint.py::test_stock_history_endpoint_reads_cached_us_bars_without_provider_network`.
- Affected test files (12): `tests/api/test_market_endpoint_provider_regressions.py`, `tests/api/test_stock_history_endpoint.py`, `tests/api/test_stock_structure_decision_endpoint.py`, `tests/test_historical_ohlcv_readiness_service.py`, `tests/test_hk_realtime_routing.py`, `tests/test_market_overview_provider_boundaries.py`, `tests/test_market_overview_provider_deadlines.py`, `tests/test_stock_api_freshness_contract.py`, `tests/test_stock_service_intraday_boundary.py`, `tests/test_stock_service_validation.py`, `tests/test_stock_structure_decision_service.py`, `tests/test_yfinance_symbol_boundary.py`.
- Exception mix: `AssertionError`=32.
- Stable anchor: adapter returns None/unavailable, or source/freshness fields differ.
- Shared fixtures/modules: `stock service adapter`, `normalized provider ports`, `stock API mapping`.
- Owner/root cause/confidence: Stock service and normalized provider adapters; Provider-port normalization changed adapter calls, names, fallbacks, and public source fields beyond the established contract. Confidence: `medium-high`.
- Reproduction: isolation 1 failed; small batch 2 failed; order: not indicated; isolation and batch matched the canonical anchor.
- External requirements: no network, real database, credentials, or external service.
- Fix layer: stock/provider product adapters and explicit tests.
- Protected semantics: Preserve provider order, fallback trace, authority, freshness, credentials, cache behavior, and no raw payloads.
- Validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_stock_service_validation.py tests/test_provider_runtime_contracts.py tests/test_stock_api_freshness_contract.py`
- Risk: `critical`.

## Historical comparison

- Present on both: 396 failing IDs and 6 setup-error IDs.
- Only T512: 0 failures, 0 errors. Only T513: 0 failures, 0 errors.
- Outcome changes from inventory change: 0.
- T513 added 42 collected tests, all passing, and removed none: collected +42, passed +42, failed/skipped/errors 0.
- Environment, component, lock, target/profile/projection, resolver, and bootstrap-network identities match.

T513-added passing nodes:

- `tests/scripts/test_uat_runtime_harness.py::test_find_system_command_uses_reviewed_absolute_fallback`
- `tests/scripts/test_uat_runtime_harness.py::test_release_evidence_sanitizer_normalizes_reviewed_roots_and_rejects_unknown_private_path`
- `tests/scripts/test_web_build_artifact.py::test_release_typecheck_uses_non_incremental_configs_without_snapshot_writes`
- `tests/scripts/test_wolfy_runtime.py::test_release_projection_preserves_only_non_secret_identity_controls`
- `tests/test_qualified_release_integration.py::test_candidate_binds_environment_lock_web_workflow_and_multiarch_identities`
- `tests/test_qualified_release_integration.py::test_candidate_rejects_invalid_environment_or_lock_identity[environment_fingerprint]`
- `tests/test_qualified_release_integration.py::test_candidate_rejects_invalid_environment_or_lock_identity[lock_mismatch]`
- `tests/test_qualified_release_integration.py::test_candidate_rejects_invalid_environment_or_lock_identity[network_used]`
- `tests/test_qualified_release_integration.py::test_candidate_rejects_invalid_environment_or_lock_identity[top_status]`
- `tests/test_qualified_release_integration.py::test_oci_inspection_records_exact_index_and_platform_digests`
- `tests/test_qualified_release_integration.py::test_playwright_browser_install_survives_managed_run_cleanup`
- `tests/test_qualified_release_integration.py::test_release_runtime_evidence_requires_source_cwd_environment_and_asset_identity`
- `tests/test_qualified_release_integration.py::test_release_runtime_fixture_assigns_explicit_super_admin_without_secret_output`
- `tests/test_qualified_release_integration.py::test_release_workflows_use_managed_environment_and_digest_only_promotion`
- `tests/test_release_gate_summary.py::test_each_required_gate_failure_blocks_qualification[artifact-provenance]`
- `tests/test_release_gate_summary.py::test_each_required_gate_failure_blocks_qualification[auth-rbac]`
- `tests/test_release_gate_summary.py::test_each_required_gate_failure_blocks_qualification[authoritative-topology]`
- `tests/test_release_gate_summary.py::test_each_required_gate_failure_blocks_qualification[backend-canonical]`
- `tests/test_release_gate_summary.py::test_each_required_gate_failure_blocks_qualification[frontend-lint]`
- `tests/test_release_gate_summary.py::test_each_required_gate_failure_blocks_qualification[frontend-typecheck]`
- `tests/test_release_gate_summary.py::test_each_required_gate_failure_blocks_qualification[full-vitest]`
- `tests/test_release_gate_summary.py::test_each_required_gate_failure_blocks_qualification[operator-evidence]`
- `tests/test_release_gate_summary.py::test_each_required_gate_failure_blocks_qualification[playwright-real-runtime]`
- `tests/test_release_gate_summary.py::test_each_required_gate_failure_blocks_qualification[production-build]`
- `tests/test_release_gate_summary.py::test_each_required_gate_failure_blocks_qualification[runtime-uat]`
- `tests/test_release_gate_summary.py::test_each_required_gate_failure_blocks_qualification[secret-private-path-scan]`
- `tests/test_release_gate_summary.py::test_gate_identity_mismatch_blocks_qualification[candidateDigest]`
- `tests/test_release_gate_summary.py::test_gate_identity_mismatch_blocks_qualification[candidateSha]`
- `tests/test_release_gate_summary.py::test_gate_identity_mismatch_blocks_qualification[environmentFingerprint]`
- `tests/test_release_gate_summary.py::test_gate_identity_mismatch_blocks_qualification[imageIndexDigest]`
- `tests/test_release_gate_summary.py::test_gate_identity_mismatch_blocks_qualification[imagePlatformDigests]`
- `tests/test_release_gate_summary.py::test_gate_identity_mismatch_blocks_qualification[pythonLockContentHash]`
- `tests/test_release_gate_summary.py::test_non_pass_gate_states_never_qualify[CANCELLED]`
- `tests/test_release_gate_summary.py::test_non_pass_gate_states_never_qualify[FAIL]`
- `tests/test_release_gate_summary.py::test_non_pass_gate_states_never_qualify[MISSING]`
- `tests/test_release_gate_summary.py::test_non_pass_gate_states_never_qualify[NEUTRAL]`
- `tests/test_release_gate_summary.py::test_non_pass_gate_states_never_qualify[NOT-RUN]`
- `tests/test_release_gate_summary.py::test_non_pass_gate_states_never_qualify[SKIPPED]`
- `tests/test_release_gate_summary.py::test_non_pass_gate_states_never_qualify[UNKNOWN]`
- `tests/test_release_secret_scan.py::test_release_secret_scan_rejects_credentials_inside_candidate_archive`
- `tests/test_release_secret_scan.py::test_release_secret_scan_rejects_private_paths_in_generated_evidence`
- `tests/test_release_secret_scan.py::test_release_secret_scan_treats_only_topology_test_ids_as_reviewed_fixture_data`

Exact skipped nodes:

- `tests/api/test_admin_logs_real_pg.py::AdminLogsRealPgQuotaTestCase::test_storage_quota_warns_criticalizes_and_cleans_up_against_real_postgresql`
- `tests/scripts/test_uat_runtime_harness.py::test_stop_from_evidence_windows_can_terminate_owned_child_with_recorded_identity`
- `tests/test_postgres_phase_a_real_pg.py::PostgresPhaseARealPgTestCase::test_real_postgres_auth_disabled_bootstrap_admin_behavior`
- `tests/test_postgres_phase_a_real_pg.py::PostgresPhaseARealPgTestCase::test_real_postgres_bootstrap_auth_flow_and_docs_ddl_path`
- `tests/test_postgres_phase_a_real_pg.py::PostgresPhaseARealPgTestCase::test_real_postgres_lazy_backfill_and_factory_reset_mixed_storage`
- `tests/test_postgres_phase_a_real_pg.py::PostgresPhaseARealPgTestCase::test_real_postgres_notification_preferences_and_guest_preview_non_persistence`
- `tests/test_postgres_phase_b_real_pg.py::PostgresPhaseBRealPgTestCase::test_real_postgres_phase_b_shadow_writes_and_delete_paths`
- `tests/test_postgres_phase_b_real_pg.py::PostgresPhaseBRealPgTestCase::test_real_postgres_phase_b_store_exposes_models_to_same_runtime_db`
- `tests/test_postgres_phase_c_real_pg.py::PostgresPhaseCRealPgTestCase::test_real_postgres_phase_c_metadata_round_trip`
- `tests/test_postgres_phase_d_real_pg.py::PostgresPhaseDRealPgTestCase::test_real_postgres_phase_d_scanner_and_watchlist_round_trip`
- `tests/test_postgres_phase_e_real_pg.py::PostgresPhaseERealPgTestCase::test_real_postgres_phase_e_historical_eval_round_trip`
- `tests/test_postgres_phase_e_real_pg.py::PostgresPhaseERealPgTestCase::test_real_postgres_phase_e_rule_backtest_round_trip_and_factory_reset`
- `tests/test_postgres_phase_f_real_pg.py::PostgresPhaseFRealPgTestCase::test_real_postgres_phase_f_broker_connection_surface_falls_back_to_legacy_when_pg_tables_are_partial`
- `tests/test_postgres_phase_f_real_pg.py::PostgresPhaseFRealPgTestCase::test_real_postgres_phase_f_cash_ledger_comparison_collects_bounded_non_empty_evidence`
- `tests/test_postgres_phase_f_real_pg.py::PostgresPhaseFRealPgTestCase::test_real_postgres_phase_f_cash_ledger_comparison_respects_multi_user_account_scope`
- `tests/test_postgres_phase_f_real_pg.py::PostgresPhaseFRealPgTestCase::test_real_postgres_phase_f_corporate_actions_comparison_collects_bounded_non_empty_evidence`
- `tests/test_postgres_phase_f_real_pg.py::PostgresPhaseFRealPgTestCase::test_real_postgres_phase_f_latest_sync_surface_falls_back_to_legacy_when_pg_tables_are_partial`
- `tests/test_postgres_phase_f_real_pg.py::PostgresPhaseFRealPgTestCase::test_real_postgres_phase_f_portfolio_round_trip`
- `tests/test_postgres_phase_g_real_pg.py::PostgresPhaseGRealPgTestCase::test_real_postgres_phase_g_control_plane_round_trip`
- `tests/test_postgres_phase_g_real_pg.py::PostgresPhaseGRealPgTestCase::test_real_postgres_phase_g_execution_log_shadow_observability_round_trip`
- `tests/test_postgres_phase_g_real_pg.py::PostgresPhaseGRealPgTestCase::test_real_postgres_phase_g_factory_reset_nulls_deleted_user_refs`
- `tests/test_postgres_runtime_real_pg.py::PostgresRuntimeRealPgAuditTestCase::test_real_postgres_runtime_audit_reports_all_phase_slices_as_applied`
- `tests/test_postgres_runtime_real_pg.py::PostgresRuntimeRealPgAuditTestCase::test_real_postgres_runtime_audit_reports_skip_mode_without_losing_schema_visibility`

## Remediation lanes

| Task | Wave | Owner | Families | Expected reduction | Dependencies | Model | Commit |
| --- | ---: | --- | --- | ---: | --- | --- | --- |
| T515 | 1 | Python dependency and environment lock | T514-F01 | 46F | none | `gpt-5.6-sol` / `xhigh` | `fix(env): add reviewed parquet test engine` |
| T516 | 2 | Provider adapters and shared no-live-provider isolation | T514-F02 | 105F | T517 | `gpt-5.6-sol` / `xhigh` | `fix(provider): preserve offline mock transport seams` |
| T517 | 1 | Managed test environment | T514-F03, T514-F10 | 10F | none | `gpt-5.6-sol` / `xhigh` | `fix(test): align hermetic configuration contracts` |
| T518 | 2 | Auth and explicit RBAC capabilities | T514-F04 | 49F | none | `gpt-5.6-sol` / `xhigh` | `fix(auth): align explicit capability test contracts` |
| T519 | 3 | Runtime composition and application routing | T514-F05, T514-F06 | 11F+6E | T518 | `gpt-5.6-sol` / `xhigh` | `fix(runtime): align container lifecycle route discovery` |
| T520 | 2 | SQLite storage lifecycle | T514-F07 | 5F | none | `gpt-5.6-sol` / `xhigh` | `fix(storage): isolate canonical sqlite lifecycle` |
| T521 | 1 | Restore drill safety fixtures | T514-F08 | 17F | none | `gpt-5.6-sol` / `high` | `fix(restore): align drill fixtures with safe temp roots` |
| T522 | 1 | Canonical contract documentation | T514-F09 | 10F | none | `gpt-5.6-terra` / `high` | `docs(contracts): restore canonical audit references` |
| T523 | 1 | Architecture and validation ownership governance | T514-F11 | 16F | none | `gpt-5.6-sol` / `xhigh` | `test(architecture): review canonical ownership inventories` |
| T524 | 4 | Market evidence and normalized stock/provider contracts | T514-F12, T514-F19 | 62F | T516, T519 | `gpt-5.6-sol` / `xhigh` | `fix(market): align normalized evidence contracts` |
| T525 | 2 | Scanner scoring and diagnostics | T514-F13 | 22F | T515 | `gpt-5.6-sol` / `xhigh` | `fix(scanner): restore scoring and diagnostics contracts` |
| T526 | 2 | Backtest stored evidence | T514-F14 | 7F | T515 | `gpt-5.6-sol` / `xhigh` | `fix(backtest): restore stored evidence contracts` |
| T527 | 4 | Portfolio ownership and readiness | T514-F15 | 5F | T517, T519 | `gpt-5.6-sol` / `xhigh` | `fix(portfolio): restore owner and readiness contracts` |
| T528 | 1 | Operator and release evidence qualification | T514-F16 | 11F | none | `gpt-5.6-sol` / `high` | `fix(release): align operator evidence contracts` |
| T529 | 2 | Analysis orchestration and public safety | T514-F17 | 13F | T516 | `gpt-5.6-sol` / `xhigh` | `fix(analysis): restore orchestration safety contracts` |
| T530 | 2 | Homepage public contracts | T514-F18 | 7F | T523 | `gpt-5.6-sol` / `high` | `fix(homepage): align public schema and copy contracts` |

Lane arithmetic is 396 failures and 6 errors. Waves/dependencies serialize all overlapping owner surfaces; shared environment, lock, and no-live-provider infrastructure each has one owner.

### T515 - Python dependency and environment lock

- Families/reduction: T514-F01; 46 failures and 0 errors.
- Exact writable files/directories: `requirements-dev.txt`, `requirements-lock.json`, `requirements-python311-dev.lock`, `requirements-python311-runtime.lock`, `requirements-python312-dev.lock`, `requirements-python312-runtime.lock`, `tests/api/test_market_regime_read_model_endpoint.py`, `tests/scripts/test_data_chain_operator_verifier.py`, `tests/scripts/test_local_data_cache_schema_verifier.py`, `tests/scripts/test_market_regime_evidence_verifier.py`, `tests/scripts/test_market_regime_read_model_verifier.py`, `tests/test_backtest_service.py`, `tests/test_historical_ohlcv_readiness_service.py`, `tests/test_market_data_readiness_diagnostics.py`, `tests/test_market_regime_evidence_service.py`, `tests/test_market_regime_read_model_service.py`, `tests/test_market_scanner_service.py`.
- Protected: `production container install policy`, `requirements.txt runtime intent unless explicitly justified`, `validation/domain_test_topology.json`, `provider behavior`.
- Dependencies/conflict: none; high; sole lock owner.
- Focused validation: `./wolfy lock python --check && ./wolfy bootstrap --ensure --offline && ./wolfy exec --profile test -- python -m pytest -q --tb=short tests/api/test_market_regime_read_model_endpoint.py tests/scripts/test_local_data_cache_schema_verifier.py`
- Canonical regression: `CI=true ./scripts/ci_gate.sh`
- Agent: `gpt-5.6-sol`, reasoning `xhigh`.
- Commit: `fix(env): add reviewed parquet test engine`

### T516 - Provider adapters and shared no-live-provider isolation

- Families/reduction: T514-F02; 105 failures and 0 errors.
- Exact writable files/directories: `data_provider/`, `src/search_service.py`, `src/services/image_stock_extractor.py`, `src/services/official_macro_transport.py`, `src/services/uat_provider_isolation.py`, `tests/test_alpaca_fetcher.py`, `tests/test_analysis_api_contract.py`, `tests/test_data_fetcher_manager_alpaca.py`, `tests/test_data_fetcher_manager_twelve_data.py`, `tests/test_fetcher_logging.py`, `tests/test_image_stock_extractor_litellm.py`, `tests/test_market_analyzer_generate_text.py`, `tests/test_market_overview_provider_deadlines.py`, `tests/test_official_macro_transport.py`, `tests/test_provider_runtime_contracts.py`, `tests/test_search_provider_fallbacks.py`, `tests/test_search_searxng.py`, `tests/test_search_tavily_provider.py`, `tests/test_stock_structure_decision_service.py`, `tests/test_stooq_fallback.py`, `tests/test_tushare_fetcher_followups.py`, `tests/test_twelve_data_fetcher.py`, `tests/test_us_fundamentals_provider.py`, `tests/test_yfinance_us_indices.py`.
- Protected: `provider order/fallback authority`, `credentials`, `external network denial`, `validation/domain_test_topology.json`.
- Dependencies/conflict: T517; high; serialize before T524 because files overlap.
- Focused validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_official_macro_transport.py plus one-variable guard ablation with socket denial retained`
- Canonical regression: `CI=true ./scripts/ci_gate.sh`
- Agent: `gpt-5.6-sol`, reasoning `xhigh`.
- Commit: `fix(provider): preserve offline mock transport seams`

### T517 - Managed test environment

- Families/reduction: T514-F03, T514-F10; 10 failures and 0 errors.
- Exact writable files/directories: `scripts/environment/runtime.py`, `tests/api/test_market_cache_import_boundary.py`, `tests/services/test_home_source_provenance_sidecar.py`, `tests/test_akshare_cn_ohlcv_cache_runtime.py`, `tests/test_historical_ohlcv_cache_preflight.py`, `tests/test_market_cache_fallback_contracts.py`.
- Protected: `requirements and lock files`, `offline socket denial`, `validation/domain_test_topology.json`, `private host paths`.
- Dependencies/conflict: none; high; sole shared environment owner.
- Focused validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/api/test_market_cache_import_boundary.py tests/test_historical_ohlcv_cache_preflight.py tests/test_market_cache_fallback_contracts.py && ./wolfy exec --profile test -- python -m pytest -q --tb=short tests/services/test_home_source_provenance_sidecar.py`
- Canonical regression: `CI=true ./scripts/ci_gate.sh`
- Agent: `gpt-5.6-sol`, reasoning `xhigh`.
- Commit: `fix(test): align hermetic configuration contracts`

### T518 - Auth and explicit RBAC capabilities

- Families/reduction: T514-F04; 49 failures and 0 errors.
- Exact writable files/directories: `api/deps.py`, `api/route_access_policy.py`, `api/v1/endpoints/admin_security.py`, `api/v1/endpoints/auth.py`, `src/auth.py`, `tests/api/test_admin_cost_summary.py`, `tests/api/test_admin_provider_circuit_diagnostics.py`, `tests/api/test_admin_quota_dry_run.py`, `tests/api/test_admin_security.py`, `tests/api/test_cn_provider_health.py`, `tests/api/test_market_data_readiness.py`, `tests/api/test_public_api_surface_safety.py`, `tests/api/test_runtime_api_edge_contracts.py`, `tests/api/test_security_launch_preflight.py`, `tests/test_auth_api.py`, `tests/test_multi_user_phase3.py`.
- Protected: `auth/RBAC fail-closed policy`, `sessions/reauthentication`, `admin protection`, `security posture`.
- Dependencies/conflict: none; high; T519 waits because api/deps.py is shared.
- Focused validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/api/test_admin_security.py tests/api/test_runtime_api_edge_contracts.py tests/test_auth_api.py`
- Canonical regression: `CI=true ./scripts/ci_gate.sh`
- Agent: `gpt-5.6-sol`, reasoning `xhigh`.
- Commit: `fix(auth): align explicit capability test contracts`

### T519 - Runtime composition and application routing

- Families/reduction: T514-F05, T514-F06; 11 failures and 6 errors.
- Exact writable files/directories: `api/app.py`, `api/deps.py`, `api/v1/endpoints/admin_ops_status.py`, `api/v1/endpoints/market.py`, `src/runtime/composition.py`, `src/services/admin_surface_contract_readiness_service.py`, `tests/api/test_admin_surface_readiness.py`, `tests/api/test_cn_provider_health.py`, `tests/api/test_daily_intelligence_endpoint.py`, `tests/api/test_market_intelligence_payload_smoke.py`, `tests/api/test_provider_fit_advisor.py`, `tests/test_multi_user_phase3.py`.
- Protected: `explicit container ownership`, `lifespan rollback/close`, `hidden routes`, `auth dependencies`.
- Dependencies/conflict: T518; high; serialized after auth.
- Focused validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/api/test_market_intelligence_payload_smoke.py tests/test_multi_user_phase3.py::MultiUserAuthorizationApiTestCase::test_admin_only_surfaces_are_backend_protected && ./wolfy exec --profile test -- python -m pytest -q --tb=short tests/api/test_cn_provider_health.py tests/api/test_daily_intelligence_endpoint.py tests/api/test_provider_fit_advisor.py tests/api/test_admin_surface_readiness.py`
- Canonical regression: `CI=true ./scripts/ci_gate.sh`
- Agent: `gpt-5.6-sol`, reasoning `xhigh`.
- Commit: `fix(runtime): align container lifecycle route discovery`

### T520 - SQLite storage lifecycle

- Families/reduction: T514-F07; 5 failures and 0 errors.
- Exact writable files/directories: `api/v1/endpoints/admin_logs.py`, `api/v1/endpoints/admin_users.py`, `src/postgres_phase_a.py`, `src/storage.py`, `tests/api/test_admin_logs.py`, `tests/api/test_admin_real_auth_session_smoke.py`, `tests/api/test_admin_users.py`, `tests/test_postgres_phase_a.py`.
- Protected: `real PostgreSQL opt-in`, `transactions`, `owner scoping`, `migrations`.
- Dependencies/conflict: none; medium; no migration without separate authority.
- Focused validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/api/test_admin_logs.py tests/test_postgres_phase_a.py`
- Canonical regression: `CI=true ./scripts/ci_gate.sh`
- Agent: `gpt-5.6-sol`, reasoning `xhigh`.
- Commit: `fix(storage): isolate canonical sqlite lifecycle`

### T521 - Restore drill safety fixtures

- Families/reduction: T514-F08; 17 failures and 0 errors.
- Exact writable files/directories: `scripts/backup_restore_drill_check.sh`, `tests/test_backup_restore_drill_check.py`.
- Protected: `restore allowlist`, `no-overwrite`, `DSN redaction`, `real database boundary`.
- Dependencies/conflict: none; medium; fix fixture/root, not safety.
- Focused validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_backup_restore_drill_check.py`
- Canonical regression: `CI=true ./scripts/ci_gate.sh`
- Agent: `gpt-5.6-sol`, reasoning `high`.
- Commit: `fix(restore): align drill fixtures with safe temp roots`

### T522 - Canonical contract documentation

- Families/reduction: T514-F09; 10 failures and 0 errors.
- Exact writable files/directories: `docs/audits/operator-evidence-dry-run-handoff.md`, `docs/data-reliability/data-coverage-consumer-projection-examples.md`, `docs/data-reliability/data-coverage-surface-fixtures.md`, `docs/market-overview/market-intelligence-smoke-checklist.md`, `docs/operations/duckdb-operator-smoke-guide.md`, `docs/operations/provider-capability-metadata.md`, `tests/test_data_coverage_matrix_consumer_projection_examples.py`, `tests/test_data_coverage_surface_fixtures.py`, `tests/test_market_intelligence_smoke_checklist.py`, `tests/test_operator_evidence_command_docs.py`, `tests/test_provider_capability_matrix.py`, `tests/test_quant_duckdb_service.py`.
- Protected: `generated manual unless source changes`, `private URLs`, `placeholder readiness`, `duplicate authorities`.
- Dependencies/conflict: none; low; decide restore versus path update.
- Focused validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_operator_evidence_command_docs.py tests/test_data_coverage_surface_fixtures.py tests/test_market_intelligence_smoke_checklist.py && python scripts/build_ai_project_manual.py --check`
- Canonical regression: `CI=true ./scripts/ci_gate.sh`
- Agent: `gpt-5.6-terra`, reasoning `high`.
- Commit: `docs(contracts): restore canonical audit references`

### T523 - Architecture and validation ownership governance

- Families/reduction: T514-F11; 16 failures and 0 errors.
- Exact writable files/directories: `src/contracts/`, `src/services/professional_data_capability_registry_service.py`, `src/services/provider_fit_advisor_service.py`, `tests/scripts/test_validation_owner_manifest.py`, `tests/test_backend_modular_import_boundaries.py`, `tests/test_contracts_namespace.py`, `tests/test_evidence_cli_contracts.py`, `tests/test_options_structure_contract.py`, `tests/test_professional_data_capability_registry_service.py`, `tests/test_provider_credential_inventory.py`, `tests/test_provider_fit_metadata.py`, `tests/test_provider_runtime_boundary.py`, `validation/validation_owners.json`.
- Protected: `validation/domain_test_topology.json`, `knownBaselineFailures`, `provider authority`, `architecture escalation`.
- Dependencies/conflict: none; high; review, do not accept sets mechanically.
- Focused validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_backend_modular_import_boundaries.py tests/scripts/test_validation_owner_manifest.py tests/test_provider_fit_metadata.py && python scripts/check_ai_assets.py`
- Canonical regression: `CI=true ./scripts/ci_gate.sh`
- Agent: `gpt-5.6-sol`, reasoning `xhigh`.
- Commit: `test(architecture): review canonical ownership inventories`

### T524 - Market evidence and normalized stock/provider contracts

- Families/reduction: T514-F12, T514-F19; 62 failures and 0 errors.
- Exact writable files/directories: `api/v1/endpoints/market.py`, `api/v1/endpoints/market_overview.py`, `api/v1/endpoints/stocks.py`, `src/contracts/evidence/`, `src/services/market_overview_service.py`, `src/services/stock_service.py`, `src/services/stock_service_provider_adapter.py`, `tests/api/test_market_cn_breadth.py`, `tests/api/test_market_endpoint_provider_regressions.py`, `tests/api/test_market_freshness.py`, `tests/api/test_market_futures.py`, `tests/api/test_market_fx_commodities.py`, `tests/api/test_market_rotation_radar.py`, `tests/api/test_market_temperature.py`, `tests/api/test_market_us_breadth.py`, `tests/api/test_stock_history_endpoint.py`, `tests/api/test_stock_structure_decision_endpoint.py`, `tests/test_historical_ohlcv_readiness_service.py`, `tests/test_hk_realtime_routing.py`, `tests/test_market_overview_core_quote_repair.py`, `tests/test_market_overview_evidence_snapshot.py`, `tests/test_market_overview_provider_boundaries.py`, `tests/test_market_overview_provider_deadlines.py`, `tests/test_market_regime_projection_runtime_verifier.py`, `tests/test_market_rotation_radar_service.py`, `tests/test_market_temperature_input_snapshot.py`, `tests/test_stock_api_freshness_contract.py`, `tests/test_stock_service_intraday_boundary.py`, `tests/test_stock_service_validation.py`, `tests/test_stock_structure_decision_service.py`, `tests/test_yfinance_symbol_boundary.py`.
- Protected: `provider order/fallback/cache/freshness`, `source authority`, `immutable observation facts`, `no trading advice`.
- Dependencies/conflict: T516, T519; critical; serialize after provider and runtime work.
- Focused validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_market_overview_evidence_snapshot.py tests/api/test_market_freshness.py tests/test_market_regime_projection_runtime_verifier.py && ./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_stock_service_validation.py tests/test_provider_runtime_contracts.py tests/test_stock_api_freshness_contract.py`
- Canonical regression: `CI=true ./scripts/ci_gate.sh`
- Agent: `gpt-5.6-sol`, reasoning `xhigh`.
- Commit: `fix(market): align normalized evidence contracts`

### T525 - Scanner scoring and diagnostics

- Families/reduction: T514-F13; 22 failures and 0 errors.
- Exact writable files/directories: `src/core/scanner_profile.py`, `src/core/scanner_skip_reason.py`, `src/services/market_scanner_ops_service.py`, `src/services/market_scanner_service.py`, `tests/test_ai_evidence_cross_engine_contracts.py`, `tests/test_market_scanner_ops_service.py`, `tests/test_market_scanner_service.py`, `tests/test_scanner_strategy_simulation.py`, `tests/test_watchlist_score_refresh.py`.
- Protected: `score contributions/thresholds`, `sorting`, `live/fallback labels`, `stored runs`.
- Dependencies/conflict: T515; high; full file also contains F01.
- Focused validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_market_scanner_service.py tests/test_market_scanner_ops_service.py tests/test_scanner_strategy_simulation.py`
- Canonical regression: `CI=true ./scripts/ci_gate.sh`
- Agent: `gpt-5.6-sol`, reasoning `xhigh`.
- Commit: `fix(scanner): restore scoring and diagnostics contracts`

### T526 - Backtest stored evidence

- Families/reduction: T514-F14; 7 failures and 0 errors.
- Exact writable files/directories: `src/repositories/rule_backtest_repo.py`, `src/services/backtest_service.py`, `src/services/rule_backtest_service.py`, `src/services/rule_backtest_support_exports.py`, `tests/test_backtest_data_sufficiency_gate.py`, `tests/test_backtest_regime_attribution_readiness.py`, `tests/test_rule_backtest_reopen_acceptance.py`, `tests/test_rule_backtest_support_bundle_e2e.py`.
- Protected: `fills/costs`, `metrics/benchmark`, `winner semantics`, `stored result authority`.
- Dependencies/conflict: T515; critical; full files also contain F01.
- Focused validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_rule_backtest_support_bundle_e2e.py tests/test_rule_backtest_reopen_acceptance.py tests/test_backtest_regime_attribution_readiness.py`
- Canonical regression: `CI=true ./scripts/ci_gate.sh`
- Agent: `gpt-5.6-sol`, reasoning `xhigh`.
- Commit: `fix(backtest): restore stored evidence contracts`

### T527 - Portfolio ownership and readiness

- Families/reduction: T514-F15; 5 failures and 0 errors.
- Exact writable files/directories: `src/repositories/portfolio_repo.py`, `src/services/portfolio_risk_diagnostics.py`, `src/services/portfolio_risk_service.py`, `src/services/portfolio_service.py`, `tests/api/test_portfolio_owner_isolation.py`, `tests/test_multi_user_phase3.py`, `tests/test_portfolio_api_contract.py`, `tests/test_portfolio_pr2.py`.
- Protected: `accounts/cash/holdings/P&L`, `FX/cost basis`, `broker imports`, `owner ledger`.
- Dependencies/conflict: T517, T519; critical; protected portfolio semantics.
- Focused validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/api/test_portfolio_owner_isolation.py tests/test_portfolio_api_contract.py tests/test_portfolio_pr2.py`
- Canonical regression: `CI=true ./scripts/ci_gate.sh`
- Agent: `gpt-5.6-sol`, reasoning `xhigh`.
- Commit: `fix(portfolio): restore owner and readiness contracts`

### T528 - Operator and release evidence qualification

- Families/reduction: T514-F16; 11 failures and 0 errors.
- Exact writable files/directories: `scripts/launch_acceptance_evidence.py`, `scripts/operator_evidence_gap_analyzer.py`, `scripts/operator_evidence_preflight.py`, `scripts/operator_evidence_workflow_smoke.py`, `scripts/private_beta_acceptance_scorecard.py`, `scripts/staging_ingress_smoke.py`, `scripts/ws2_multi_instance_smoke.py`, `tests/test_launch_acceptance_evidence.py`, `tests/test_operator_evidence_gap_analyzer.py`, `tests/test_operator_evidence_preflight.py`, `tests/test_operator_evidence_workflow_smoke.py`, `tests/test_private_beta_acceptance_scorecard.py`, `tests/test_staging_ingress_smoke.py`, `tests/test_ws2_multi_instance_preflight.py`.
- Protected: `release workflow without separate authority`, `NO_GO default`, `secret redaction`, `synthetic-only evidence`.
- Dependencies/conflict: none; medium; no workflow changes.
- Focused validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_operator_evidence_preflight.py tests/test_operator_evidence_workflow_smoke.py tests/test_staging_ingress_smoke.py`
- Canonical regression: `CI=true ./scripts/ci_gate.sh`
- Agent: `gpt-5.6-sol`, reasoning `high`.
- Commit: `fix(release): align operator evidence contracts`

### T529 - Analysis orchestration and public safety

- Families/reduction: T514-F17; 13 failures and 0 errors.
- Exact writable files/directories: `api/v1/endpoints/analysis.py`, `src/agent/`, `src/analyzer.py`, `src/services/analysis_service.py`, `src/services/system_config_service.py`, `tests/test_agent_executor.py`, `tests/test_agent_pipeline.py`, `tests/test_ai_decision_public_safety.py`, `tests/test_analysis_integration.py`, `tests/test_multi_agent.py`, `tests/test_system_config_service.py`.
- Protected: `no trading advice`, `model/provider redaction`, `no real model calls`, `public safety`.
- Dependencies/conflict: T516; high; vision seam remains T516-owned.
- Focused validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_analysis_integration.py tests/test_ai_decision_public_safety.py tests/test_agent_pipeline.py`
- Canonical regression: `CI=true ./scripts/ci_gate.sh`
- Agent: `gpt-5.6-sol`, reasoning `xhigh`.
- Commit: `fix(analysis): restore orchestration safety contracts`

### T530 - Homepage public contracts

- Families/reduction: T514-F18; 7 failures and 0 errors.
- Exact writable files/directories: `api/v1/schemas/homepage_capabilities.py`, `api/v1/schemas/homepage_section_layout.py`, `src/services/homepage_capabilities_service.py`, `src/services/homepage_public_copy.py`, `src/services/homepage_section_layout_service.py`, `tests/test_homepage_capabilities_service.py`, `tests/test_homepage_public_copy_consistency.py`, `tests/test_homepage_section_layout_service.py`.
- Protected: `public taxonomy`, `secret/internal redaction`, `no trading advice`, `read-only behavior`.
- Dependencies/conflict: T523; medium; governance reviewed first.
- Focused validation: `./wolfy exec --profile test -- python -m pytest -q --tb=short tests/test_homepage_capabilities_service.py tests/test_homepage_section_layout_service.py tests/test_homepage_public_copy_consistency.py`
- Canonical regression: `CI=true ./scripts/ci_gate.sh`
- Agent: `gpt-5.6-sol`, reasoning `high`.
- Commit: `fix(homepage): align public schema and copy contracts`

## Access, residuals, and release decision

- Unexpected provider network access: none; the outbound deny hook remained active during guard ablation.
- Unexpected real database access: none; real PostgreSQL nodes remained skipped and no opt-in was supplied.
- Credentials, external services, active exploit probes: none.
- Private absolute paths in committed reports: none; raw traces were not copied.
- Detached T512 comparison worktree: removed; no branch, commit, or push.
- Residual reporting gap: no JUnit XML or per-test duration ranking because no compatible canonical passthrough exists.
- Residual causal gap: introducing commit not bisected; all 402 blocking IDs reproduce at T512.
- F02, F12, F17, and F19 need semantic-owner decisions; no node remains unclassified.
- Release status remains **NO_GO** until the exact canonical command exits zero.

The companion JSON is the machine authority for all 402 assignments, exact comparison ID sets, skips, family metadata, and lane surfaces.
