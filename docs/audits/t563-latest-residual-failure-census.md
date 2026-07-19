# T563 — Latest residual-failure census from landed main

## Release status

**NO_GO.** The fresh canonical gate is not green. This report is an audit only: it changes neither production/test behavior, topology, known baselines, provider order, nor market-source decisions.

## Canonical evidence

- Accepted base: `19a71d46a15a08c757ea32a243875283fca2a537`; tree: `3db79d919f8dd7c0f0d7f14a3315df97df07e2e9`.
- Command: `CI=true ./scripts/ci_gate.sh`; started `2026-07-19T07:10:47Z`, completed `2026-07-19T07:24:28Z`, exit `1`.
- Environment: Darwin arm64, CPython 3.11.15, `requirements-python311-dev.lock`, environment fingerprint `f706a3347b41e5598fad2068950a4fbd6ccd14ac43d0480f22f4df76f8ffa07a`; lock/network verification passed with network disabled.
- Complete console output was captured (9,062 lines; SHA-256 `256071a5d5a3590bc009ad7244d65141ebfaf06fdaf83ddb1cbcff32f6369760`). It is intentionally not embedded because it contains private local paths and fixture secret markers. The canonical collection JSON is machine-readable, sorted, has 8,142 IDs, and SHA-256 `744f35cac90fe8b83acc8888cb6d67b79615e40c8a3dfa8b6f993549f71d324b`.

| Measure | Count |
| --- | ---: |
| Collected | 8,142 |
| Passed | 8,077 |
| Failed collected pytest nodes | 42 |
| Skipped | 23 |
| Setup/collection errors | 0 |
| Console subtest failures | 4 |
| Console failure lines | 46 |
| Passed subtests | 717 |

Node arithmetic is `8,077 + 42 + 23 + 0 = 8,142`. Console arithmetic is `42 + 4 = 46`; the four `subTest` failure lines are not extra collected pytest nodes.

## Family and disposition census

| Family | Canonical nodes | Stable failed | Order-sensitive/non-reproducing | Dispositions |
| --- | ---: | ---: | ---: | --- |
| F04 | 7 | 0 | 7 | test-isolation or order defect: 7 |
| F11 | 3 | 3 | 0 | stale test expectation: 3 |
| F12 | 23 | 17 | 6 | confirmed product defect: 11, provider-order decision HOLD: 4, stale test expectation: 2, test-isolation or order defect: 6 |
| F17 | 1 | 0 | 1 | test-isolation or order defect: 1 |
| F19 | 8 | 5 | 3 | confirmed product defect: 2, stale test expectation: 3, test-isolation or order defect: 3 |

Disposition totals: confirmed product defect **13**; stale test expectation **8**; provider-order decision HOLD **4**; test-isolation/order defect **17**; unclassified **0**; duplicate assignment **0**.

F12/F19 separation: ME-01 market evidence defects **13**; stale market-evidence expectations **2**; stale normalized-adapter expectations **3**; explicit market-source decisions **0**; protected provider-order decisions **4**; new independent defects **0**.

## Determinism and order analysis

- Original order: 27 failed / 15 passed.
- Reverse order: 39 failed / 3 passed.
- Fresh family processes: F04 0/7, F11 3/0, F12 17/6, F17 0/1, F19 5/3 (failed/passed).
- Every state-changing node was run three times in its own fresh process: all 17 were `PPP`.

TI-01 therefore points to fixture/global-state or process-order leakage, likely involving authentication/runtime lifecycle and provider/cache state. The original canonical failures remain release blockers; later passes do not erase them.

The four official-macro deadline nodes are **PO-01 HOLD**. They require a product/provider-order decision; this audit does not change their provider order or test expectations.

## Complete node-level classification

| Node | Family | Cluster | Disposition | Isolated reproduction |
| --- | --- | --- | --- | --- |
| `tests/api/test_market_cn_breadth.py::MarketCnBreadthApiTestCase::test_cn_breadth_sanitizes_tickflow_failure_reason` | F12 | ME-01 | confirmed product defect | FFF |
| `tests/api/test_market_freshness.py::MarketFreshnessCacheTestCase::test_unavailable_breadth_fails_closed_without_live_freshness` | F12 | ME-01 | confirmed product defect | FFF |
| `tests/api/test_market_futures.py::MarketFuturesApiTestCase::test_get_futures_keeps_failed_proxy_symbol_on_item_level_fallback` | F12 | ME-01 | confirmed product defect | FFF |
| `tests/api/test_market_futures.py::MarketFuturesApiTestCase::test_get_futures_merges_delayed_proxy_items_onto_existing_fallback_card` | F12 | ME-01 | confirmed product defect | FFF |
| `tests/api/test_market_fx_commodities.py::test_fx_commodities_proxy_snapshot_keeps_item_level_fallback_on_symbol_failure` | F12 | ME-01 | confirmed product defect | FFF |
| `tests/api/test_market_fx_commodities.py::test_fx_commodities_proxy_snapshot_uses_delayed_yfinance_adapter_without_live_label` | F12 | ME-01 | confirmed product defect | FFF |
| `tests/api/test_market_rotation_radar.py::test_market_rotation_radar_api_preserves_enabled_etf_leadership_contract_without_broadening_headlines` | F12 | ME-01 | confirmed product defect | FFF |
| `tests/api/test_market_temperature.py::MarketTemperatureApiTestCase::test_market_overview_macro_api_preserves_official_authority_projection_fields` | F12 | ME-01 | confirmed product defect | FFF |
| `tests/api/test_market_temperature.py::MarketTemperatureApiTestCase::test_market_overview_official_macro_rows_keep_authority_metadata` | F12 | ME-01 | confirmed product defect | FFF |
| `tests/api/test_market_temperature.py::MarketTemperatureApiTestCase::test_market_temperature_route_response_model_preserves_consumed_subset_and_historical_extras` | F12 | ME-01 | confirmed product defect | FFF |
| `tests/api/test_market_us_breadth.py::test_market_us_breadth_current_proxy_snapshot_stays_proxy_not_exchange_breadth` | F12 | ME-01 | confirmed product defect | FFF |
| `tests/api/test_runtime_api_edge_contracts.py::test_backtest_internal_error_suppresses_raw_runtime_detail` | F04 | TI-01 | test-isolation or order defect | PPP |
| `tests/api/test_runtime_api_edge_contracts.py::test_consumer_runtime_api_routes_return_json_contracts[/api/v1/backtest/sample-status-required_keys7]` | F04 | TI-01 | test-isolation or order defect | PPP |
| `tests/api/test_runtime_api_edge_contracts.py::test_consumer_runtime_api_routes_return_json_contracts[/api/v1/research/radar-required_keys6]` | F04 | TI-01 | test-isolation or order defect | PPP |
| `tests/api/test_runtime_api_edge_contracts.py::test_consumer_runtime_api_routes_return_json_contracts[/api/v1/scanner/runs-required_keys4]` | F04 | TI-01 | test-isolation or order defect | PPP |
| `tests/api/test_runtime_api_edge_contracts.py::test_consumer_runtime_api_routes_return_json_contracts[/api/v1/scanner/status-required_keys3]` | F04 | TI-01 | test-isolation or order defect | PPP |
| `tests/api/test_runtime_api_edge_contracts.py::test_consumer_runtime_api_routes_return_json_contracts[/api/v1/watchlist/items-required_keys5]` | F04 | TI-01 | test-isolation or order defect | PPP |
| `tests/api/test_runtime_api_edge_contracts.py::test_unknown_api_route_remains_json_not_found` | F04 | TI-01 | test-isolation or order defect | PPP |
| `tests/test_ai_decision_public_safety.py::PublicPreviewSafetyTestCase::test_guest_preview_strips_raw_ai_details_and_uses_mocked_analysis` | F17 | TI-01 | test-isolation or order defect | PPP |
| `tests/test_market_overview_core_quote_repair.py::test_us10y_dxy_and_btc_keep_truthful_source_freshness_metadata` | F19 | ME-01 | confirmed product defect | FFF |
| `tests/test_market_overview_core_quote_repair.py::test_vix_fred_transport_overlay_is_consumed_when_fresh_enough` | F19 | ME-01 | confirmed product defect | FFF |
| `tests/test_market_overview_evidence_snapshot.py::MarketOverviewEvidenceSnapshotTestCase::test_evidence_snapshot_reuses_shared_provider_helper_without_widening_contract` | F11 | ST-01 | stale test expectation | FFF |
| `tests/test_market_overview_provider_boundaries.py::test_market_overview_transport_modules_stay_runtime_lightweight` | F11 | ST-01 | stale test expectation | FFF |
| `tests/test_market_overview_provider_deadlines.py::test_official_macro_points_attempt_fred_dgs10_dgs30_after_treasury_timeout` | F12 | PO-01 | provider-order decision HOLD | FFF |
| `tests/test_market_overview_provider_deadlines.py::test_official_macro_points_prioritize_vixcls_then_fred_dgs10_dgs30_after_treasury_miss` | F12 | PO-01 | provider-order decision HOLD | FFF |
| `tests/test_market_overview_provider_deadlines.py::test_official_macro_points_protect_fred_series_from_slow_treasury_fallback` | F12 | PO-01 | provider-order decision HOLD | FFF |
| `tests/test_market_overview_provider_deadlines.py::test_rates_macro_and_volatility_reuse_official_macro_observations_within_micro_cache_ttl` | F12 | PO-01 | provider-order decision HOLD | FFF |
| `tests/test_market_rotation_radar_service.py::MarketRotationRadarServiceTestCase::test_configured_provider_auth_failure_reports_actionable_window_diagnostics_without_secret_leak` | F12 | TI-01 | test-isolation or order defect | PPP |
| `tests/test_market_rotation_radar_service.py::MarketRotationRadarServiceTestCase::test_configured_provider_calendar_and_market_session_empty_bars_are_activation_blockers` | F12 | TI-01 | test-isolation or order defect | PPP |
| `tests/test_market_rotation_radar_service.py::MarketRotationRadarServiceTestCase::test_configured_provider_empty_all_windows_reports_empty_response_and_missing_windows` | F12 | TI-01 | test-isolation or order defect | PPP |
| `tests/test_market_rotation_radar_service.py::MarketRotationRadarServiceTestCase::test_configured_provider_interval_mapping_failure_is_first_class_activation_blocker` | F12 | TI-01 | test-isolation or order defect | PPP |
| `tests/test_market_rotation_radar_service.py::MarketRotationRadarServiceTestCase::test_configured_provider_symbol_failures_reduce_coverage_and_confidence` | F12 | TI-01 | test-isolation or order defect | PPP |
| `tests/test_market_rotation_radar_service.py::MarketRotationRadarServiceTestCase::test_partial_alpaca_credentials_report_missing_field_without_constructing_provider` | F12 | TI-01 | test-isolation or order defect | PPP |
| `tests/test_market_rotation_radar_service.py::MarketRotationRadarServiceTestCase::test_rotation_radar_yfinance_quote_provider_reuses_history_transport` | F19 | TI-01 | test-isolation or order defect | PPP |
| `tests/test_market_temperature_input_snapshot.py::test_temperature_input_builder_uses_internal_snapshots_without_public_wrapper_side_effects` | F12 | ST-ME-02 | stale test expectation | FFF |
| `tests/test_market_temperature_input_snapshot.py::test_temperature_inputs_preserve_official_macro_authority_metadata_after_rates_volatility_merge` | F12 | ST-ME-02 | stale test expectation | FFF |
| `tests/test_options_structure_contract.py::test_options_structure_api_returns_not_available_contract_without_leaks` | F19 | TI-01 | test-isolation or order defect | PPP |
| `tests/test_options_structure_contract.py::test_options_structure_api_routes_through_gateway_with_in_memory_provider` | F19 | TI-01 | test-isolation or order defect | PPP |
| `tests/test_provider_credential_inventory.py::test_provider_credential_inventory_freezes_configured_and_wired_sources_without_reading_values` | F11 | ST-01 | stale test expectation | FFF |
| `tests/test_stock_api_freshness_contract.py::test_quote_endpoint_allows_guest_access_without_auth_dependency` | F19 | ST-NA-01 | stale test expectation | FFF |
| `tests/test_stock_api_freshness_contract.py::test_quote_endpoint_can_surface_non_fresh_placeholder_metadata_without_404` | F19 | ST-NA-01 | stale test expectation | FFF |
| `tests/test_stock_api_freshness_contract.py::test_quote_endpoint_exposes_safe_source_label_and_market_timestamp_without_runtime_taxonomy` | F19 | ST-NA-01 | stale test expectation | FFF |

### Console subtest reconciliation

The four console-only failures are the TickFlow guard-reason cases `tickflow_market_stats_empty`, `tickflow_market_stats_malformed`, `tickflow_not_configured`, and `tickflow_permission_unavailable`, all under the same CN breadth test parent. They are recorded as F12 / ME-01 / confirmed product defect, but are not double-counted as collected pytest nodes.

## T495–T498 disposition

| Audit | Status against landed main | Worktree removal after T563 acceptance |
| --- | --- | --- |
| T495 | Fully superseded by landed financial/backtest/portfolio/scanner remediation. | Safe: clean; HEAD is an ancestor of the accepted base. |
| T496 | Fully superseded. F04 now proves TI-01, not a current auth defect. | Safe: clean; HEAD is an ancestor. |
| T497 | Fully superseded; no residual storage/transaction family remains. | Safe: clean; HEAD is an ancestor. |
| T498 | Partially reusable: gate-trust concern remains relevant, but old counts are superseded. | Safe: clean; HEAD is an ancestor; retain its external report historically. |

## Prioritized next wave

Safest high-confidence lane: **T565**, because it is confined to stable governance expectations and should not alter runtime/provider semantics.

Highest-risk semantic lane: **T568**, the protected official-macro provider-order decision. It is decision-blocked and must not start without an explicit authority decision.

### T564 — TI-01 shared test-state leakage

- Nodes (17): `tests/api/test_runtime_api_edge_contracts.py::test_backtest_internal_error_suppresses_raw_runtime_detail`; `tests/api/test_runtime_api_edge_contracts.py::test_consumer_runtime_api_routes_return_json_contracts[/api/v1/backtest/sample-status-required_keys7]`; `tests/api/test_runtime_api_edge_contracts.py::test_consumer_runtime_api_routes_return_json_contracts[/api/v1/research/radar-required_keys6]`; `tests/api/test_runtime_api_edge_contracts.py::test_consumer_runtime_api_routes_return_json_contracts[/api/v1/scanner/runs-required_keys4]`; `tests/api/test_runtime_api_edge_contracts.py::test_consumer_runtime_api_routes_return_json_contracts[/api/v1/scanner/status-required_keys3]`; `tests/api/test_runtime_api_edge_contracts.py::test_consumer_runtime_api_routes_return_json_contracts[/api/v1/watchlist/items-required_keys5]`; `tests/api/test_runtime_api_edge_contracts.py::test_unknown_api_route_remains_json_not_found`; `tests/test_ai_decision_public_safety.py::PublicPreviewSafetyTestCase::test_guest_preview_strips_raw_ai_details_and_uses_mocked_analysis`; `tests/test_market_rotation_radar_service.py::MarketRotationRadarServiceTestCase::test_configured_provider_auth_failure_reports_actionable_window_diagnostics_without_secret_leak`; `tests/test_market_rotation_radar_service.py::MarketRotationRadarServiceTestCase::test_configured_provider_calendar_and_market_session_empty_bars_are_activation_blockers`; `tests/test_market_rotation_radar_service.py::MarketRotationRadarServiceTestCase::test_configured_provider_empty_all_windows_reports_empty_response_and_missing_windows`; `tests/test_market_rotation_radar_service.py::MarketRotationRadarServiceTestCase::test_configured_provider_interval_mapping_failure_is_first_class_activation_blocker`; `tests/test_market_rotation_radar_service.py::MarketRotationRadarServiceTestCase::test_configured_provider_symbol_failures_reduce_coverage_and_confidence`; `tests/test_market_rotation_radar_service.py::MarketRotationRadarServiceTestCase::test_partial_alpaca_credentials_report_missing_field_without_constructing_provider`; `tests/test_market_rotation_radar_service.py::MarketRotationRadarServiceTestCase::test_rotation_radar_yfinance_quote_provider_reuses_history_transport`; `tests/test_options_structure_contract.py::test_options_structure_api_returns_not_available_contract_without_leaks`; `tests/test_options_structure_contract.py::test_options_structure_api_routes_through_gateway_with_in_memory_provider`
- Owner: test runtime lifecycle and fixture isolation. Expected production paths: `api/app.py`, `api/deps.py`, `src/runtime/composition.py`. Test paths: `tests/conftest.py`, `tests/api/test_runtime_api_edge_contracts.py`, `tests/test_market_rotation_radar_service.py`, `tests/test_options_structure_contract.py`. Protected adjacent owners: auth/RBAC, provider runtime, market-source authority.
- Dependencies: none. Product decision required: no. Recommended: GPT-5.6-sol / xhigh. Commit: `fix(test): isolate canonical runtime state`.
### T565 — ST-01 governance expectation drift

- Nodes (3): `tests/test_market_overview_evidence_snapshot.py::MarketOverviewEvidenceSnapshotTestCase::test_evidence_snapshot_reuses_shared_provider_helper_without_widening_contract`; `tests/test_market_overview_provider_boundaries.py::test_market_overview_transport_modules_stay_runtime_lightweight`; `tests/test_provider_credential_inventory.py::test_provider_credential_inventory_freezes_configured_and_wired_sources_without_reading_values`
- Owner: architecture and validation governance. Expected production paths: none. Test paths: `tests/test_market_overview_evidence_snapshot.py`, `tests/test_market_overview_provider_boundaries.py`, `tests/test_provider_credential_inventory.py`. Protected adjacent owners: provider credential handling, source authority.
- Dependencies: none. Product decision required: no. Recommended: GPT-5.6-sol / high. Commit: `test(governance): align provider ownership contracts`.
### T566 — ME-01 market evidence truth

- Nodes (13): `tests/api/test_market_cn_breadth.py::MarketCnBreadthApiTestCase::test_cn_breadth_sanitizes_tickflow_failure_reason`; `tests/api/test_market_freshness.py::MarketFreshnessCacheTestCase::test_unavailable_breadth_fails_closed_without_live_freshness`; `tests/api/test_market_futures.py::MarketFuturesApiTestCase::test_get_futures_keeps_failed_proxy_symbol_on_item_level_fallback`; `tests/api/test_market_futures.py::MarketFuturesApiTestCase::test_get_futures_merges_delayed_proxy_items_onto_existing_fallback_card`; `tests/api/test_market_fx_commodities.py::test_fx_commodities_proxy_snapshot_keeps_item_level_fallback_on_symbol_failure`; `tests/api/test_market_fx_commodities.py::test_fx_commodities_proxy_snapshot_uses_delayed_yfinance_adapter_without_live_label`; `tests/api/test_market_rotation_radar.py::test_market_rotation_radar_api_preserves_enabled_etf_leadership_contract_without_broadening_headlines`; `tests/api/test_market_temperature.py::MarketTemperatureApiTestCase::test_market_overview_macro_api_preserves_official_authority_projection_fields`; `tests/api/test_market_temperature.py::MarketTemperatureApiTestCase::test_market_overview_official_macro_rows_keep_authority_metadata`; `tests/api/test_market_temperature.py::MarketTemperatureApiTestCase::test_market_temperature_route_response_model_preserves_consumed_subset_and_historical_extras`; `tests/api/test_market_us_breadth.py::test_market_us_breadth_current_proxy_snapshot_stays_proxy_not_exchange_breadth`; `tests/test_market_overview_core_quote_repair.py::test_us10y_dxy_and_btc_keep_truthful_source_freshness_metadata`; `tests/test_market_overview_core_quote_repair.py::test_vix_fred_transport_overlay_is_consumed_when_fresh_enough`
- Owner: market overview evidence service and consumer projections. Expected production paths: `src/services/market_overview_service.py`, `api/v1/endpoints/market.py`, `api/v1/endpoints/market_overview.py`. Test paths: `tests/api/test_market_cn_breadth.py`, `tests/api/test_market_freshness.py`, `tests/api/test_market_futures.py`, `tests/api/test_market_fx_commodities.py`, `tests/api/test_market_temperature.py`, `tests/api/test_market_us_breadth.py`, `tests/test_market_overview_core_quote_repair.py`. Protected adjacent owners: provider order, source authority, cache/freshness.
- Dependencies: T564. Product decision required: no. Recommended: GPT-5.6-sol / xhigh. Commit: `fix(market): preserve evidence truth semantics`.
### T567 — ST-ME-02 and ST-NA-01 stale consumer expectations

- Nodes (5): `tests/test_market_temperature_input_snapshot.py::test_temperature_input_builder_uses_internal_snapshots_without_public_wrapper_side_effects`; `tests/test_market_temperature_input_snapshot.py::test_temperature_inputs_preserve_official_macro_authority_metadata_after_rates_volatility_merge`; `tests/test_stock_api_freshness_contract.py::test_quote_endpoint_allows_guest_access_without_auth_dependency`; `tests/test_stock_api_freshness_contract.py::test_quote_endpoint_can_surface_non_fresh_placeholder_metadata_without_404`; `tests/test_stock_api_freshness_contract.py::test_quote_endpoint_exposes_safe_source_label_and_market_timestamp_without_runtime_taxonomy`
- Owner: market and stock API contract tests. Expected production paths: none. Test paths: `tests/test_market_temperature_input_snapshot.py`, `tests/test_stock_api_freshness_contract.py`. Protected adjacent owners: market evidence source authority, normalized provider adapters.
- Dependencies: T566. Product decision required: no. Recommended: GPT-5.6-sol / high. Commit: `test(market): align evidence contract expectations`.
### T568 — PO-01 official-macro provider order

- Nodes (4): `tests/test_market_overview_provider_deadlines.py::test_official_macro_points_attempt_fred_dgs10_dgs30_after_treasury_timeout`; `tests/test_market_overview_provider_deadlines.py::test_official_macro_points_prioritize_vixcls_then_fred_dgs10_dgs30_after_treasury_miss`; `tests/test_market_overview_provider_deadlines.py::test_official_macro_points_protect_fred_series_from_slow_treasury_fallback`; `tests/test_market_overview_provider_deadlines.py::test_rates_macro_and_volatility_reuse_official_macro_observations_within_micro_cache_ttl`
- Owner: official macro provider runtime. Expected production paths: `src/services/official_macro_transport.py`, `src/services/market_overview_service.py`. Test paths: `tests/test_market_overview_provider_deadlines.py`. Protected adjacent owners: provider order, fallback, deadline budget, source authority.
- Dependencies: none. Product decision required: yes. Recommended: GPT-5.6-sol / xhigh. Commit: `fix(market): decide official macro fetch order`.

Run comprehensive QoderWork validation only after T564–T567 and, if PO-01 is changed, the approved T568 implementation; first re-run the canonical `CI=true ./scripts/ci_gate.sh`, then advance to release qualification only if it is green.

## Validation and rollback

- Evidence capture: canonical gate, sorted machine-readable collection, original/reverse reruns, five isolated family runs, and 17 × 3 fresh-process runs.
- Required final checks: JSON parse; Markdown link/path check where available; `git diff --check`; changed-file secret/private-path scan; any existing audit-schema validation.
- Rollback after commit: `git revert <T563-commit>`.
- This report itself is not release approval and does not validate browser/UAT anew.
