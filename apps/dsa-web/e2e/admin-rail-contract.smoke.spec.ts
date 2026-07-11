import type { Page, Route } from '@playwright/test';
import { expect, expectNoHorizontalOverflow, installAdminAuthHarness, test } from './fixtures/adminAuth';

const timestamp = '2026-06-06T10:30:00+08:00';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 1920, height: 1080 },
] as const;

const adminRailRoutes = [
  { path: '/zh/settings/system', readyTestId: 'system-settings-page' },
  { path: '/zh/admin/logs', readyTestId: 'admin-logs-workspace' },
  { path: '/zh/admin/users', readyTestId: 'admin-users-page-shell' },
  { path: '/zh/admin/market-providers', readyTestId: 'market-provider-operations-page' },
] as const;

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

function adminLogHealthSummary() {
  return {
    total_events: 2,
    failed_events: 0,
    warning_events: 0,
    slow_events: 0,
    failure_rate: 0,
    status: 'ok',
    failures_by_category: [],
    failures_by_provider: [],
    failures_by_reason: [],
    top_recent_errors: [],
    actor_breakdown: [{ key: 'admin', label: 'admin', count: 2 }],
    latest_critical_error: null,
  };
}

function businessEventsPayload() {
  return {
    total: 1,
    limit: 20,
    offset: 0,
    has_more: false,
    health_summary: adminLogHealthSummary(),
    items: [
      {
        id: 'admin-rail-contract-event',
        event: 'AdminRailContract',
        category: 'ops',
        type: 'rail_contract_smoke',
        event_type: 'rail_contract_smoke',
        status: 'success',
        summary: 'Admin rail contract smoke fixture',
        actor_type: 'admin',
        actor_label: 'playwright-admin',
        context_label: 'admin-shell',
        provider: null,
        source: 'playwright',
        reason: null,
        error_summary: null,
        request_id: 'req-admin-rail-contract',
        trace_id: 'trace-admin-rail-contract',
        root_cause_summary: null,
        step_trace_available: false,
        started_at: timestamp,
        duration_ms: 42,
        step_count: 1,
        success_step_count: 1,
        failed_step_count: 0,
        skipped_step_count: 0,
        unknown_step_count: 0,
      },
    ],
  };
}

function adminLogStoragePayload() {
  return {
    total_log_count: 12,
    total_event_count: 24,
    oldest_log_timestamp: timestamp,
    newest_log_timestamp: timestamp,
    retention_days: 90,
    minimum_retention_days: 7,
    retention_cutoff: '2026-03-08T10:30:00+08:00',
    logs_older_than_retention_count: 0,
    storage_size_bytes: 1024,
    storage_size_label: '1 KB',
    storage_size_available: true,
    measurement_scope: 'playwright_fixture',
    measurement_status: 'available',
    storage_soft_limit_bytes: 536870912,
    storage_hard_limit_bytes: 1073741824,
    capacity_cleanup_recommended: false,
    auto_cleanup_enabled: false,
    auto_cleanup_performed: false,
    warning_threshold_count: 50000,
    critical_threshold_count: 100000,
    status: 'ok',
    status_reasons: [],
    recommended_cleanup_action: 'No cleanup needed.',
  };
}

function sessionsPayload() {
  return {
    total: 1,
    summary: { error_count: 0, warning_count: 0, data_source_failure_count: 0, slow_request_count: 0, health_summary: adminLogHealthSummary() },
    items: [
      {
        session_id: 'admin-rail-contract-session',
        code: 'ADMIN',
        name: 'Admin rail contract session',
        overall_status: 'success',
        truth_level: 'recorded',
        started_at: timestamp,
        ended_at: timestamp,
        readable_summary: {
          actor_display: 'playwright-admin',
          actor_role: 'admin',
          subsystem: 'ops',
          operation_category: 'shell_contract',
          operation_type: 'rail smoke',
          operation_target: 'admin rail',
          operation_status: 'success',
          top_failure_reason: null,
          summary_paragraph: 'Admin rail contract fixture.',
        },
      },
    ],
  };
}

function marketProviderOperationsPayload() {
  return {
    generated_at: timestamp,
    window: { key: '24h', since: '24h' },
    summary: {
      total_items: 1,
      live_count: 1,
      cache_count: 0,
      stale_count: 0,
      fallback_count: 0,
      partial_count: 0,
      unavailable_count: 0,
      error_count: 0,
      refreshing_count: 0,
      event_count: 0,
      failure_count: 0,
      fallback_event_count: 0,
      stale_event_count: 0,
      slow_event_count: 0,
    },
    items: [
      {
        provider: 'playwright',
        source_label: 'Playwright fixture',
        source_type: 'admin_fixture',
        domain: 'shell_contract',
        endpoint: '/api/v1/admin/market-providers/operations',
        card: 'AdminRailContract',
        cache_key: 'admin_rail_contract',
        status: 'live',
        freshness: 'live',
        as_of: timestamp,
        updated_at: timestamp,
        last_successful_at: timestamp,
        last_known_good_age_minutes: 1,
        latency_ms: 12,
        is_fallback: false,
        is_stale: false,
        is_refreshing: false,
        is_from_snapshot: false,
        fallback_used: false,
        warning: null,
        error_summary: null,
        admin_log_drill_through: { label: '查看 Admin Logs', route: '/zh/admin/logs', query: { since: '24h' } },
      },
    ],
    event_rollups: [],
    cache_states: [],
    limitations: [],
    admin_log_drill_through: { label: '查看 Admin Logs', route: '/zh/admin/logs', query: { since: '24h' } },
    metadata: { source: 'playwright_admin_rail_contract', read_only: true, external_provider_calls: false, cache_mutation: false },
  };
}

function providerOperationsMatrixPayload() {
  return {
    generated_at: timestamp,
    diagnostic_only: true,
    rows: [
      {
        provider_id: 'admin_rail_contract',
        provider_name: 'Admin rail contract',
        source_label: 'Playwright fixture',
        provider_category: 'market',
        source_type: 'admin_fixture',
        source_tier: 'local',
        trust_level: 'operator_check',
        freshness_expectation: 'same_day',
        runtime_state: 'ready',
        credential_state: 'not_required',
        dependency_state: 'ready',
        enabled_by_default: true,
        observation_only: false,
        score_contribution_allowed: true,
        source_authority_allowed: true,
        score_eligible: true,
        inert_metadata_only: false,
        paid_data_likely_required: false,
        key_required: false,
        no_default_live_http_calls: true,
        cache_required: false,
        supported_capabilities: ['market_overview'],
        affected_surfaces: ['Market Overview'],
        product_affected_surfaces: ['Market Overview'],
        router_reason_codes: [],
        reason_codes: [],
        fulfilled_metrics: ['readiness'],
        missing_metrics: [],
        authority_basis: 'Playwright fixture for admin rail contract smoke.',
        universe: 'US',
        coverage_count: 1,
        diagnostic_only: true,
      },
    ],
    summary: {
      total_rows: 1,
      observation_only_rows: 0,
      inert_metadata_only_rows: 0,
      missing_provider_rows: 0,
      score_eligible_rows: 1,
      paid_data_likely_required_rows: 0,
    },
    metadata: {
      source: 'playwright_admin_rail_contract',
      read_only: true,
      diagnostic_only: true,
      external_provider_calls: false,
      network_calls_enabled: false,
      cache_mutation: false,
      secret_values_included: false,
      raw_provider_payloads_included: false,
      readiness_status: 'ready',
      row_count: 1,
    },
  };
}

function marketDataReadinessPayload() {
  return {
    readiness_status: 'ready',
    diagnostic_only: true,
    provider_runtime_called: false,
    network_calls_enabled: false,
    representative_symbols: ['ORCL'],
    checks: [
      {
        id: 'admin_rail_contract_ready',
        status: 'ready',
        severity: 'info',
        user_facing_message: 'Admin rail contract fixture is ready.',
        remediation_hint: null,
        affects_surfaces: ['Market Overview'],
        product_affected_surfaces: ['Market Overview'],
        secret_configured: false,
        details: { read_only: true },
      },
    ],
  };
}

function providerActivationVerifierPayload() {
  return {
    generated_at: timestamp,
    status: 'ready',
    readiness_state: 'ready',
    supported_statuses: ['ready'],
    summary: {
      total_count: 1,
      ready_count: 1,
      blocked_count: 0,
      warning_count: 0,
      unknown_count: 0,
      blocked_product_surfaces: [],
    },
    capabilities: [
      {
        capability_id: 'admin_rail_contract',
        label: 'Admin rail contract fixture',
        status: 'ready',
        readiness_state: 'ready',
        source_label: 'Playwright fixture',
        freshness: 'same_day',
        reason: 'Read-only admin rail fixture is ready.',
        affected_surfaces: ['Market Overview'],
        product_affected_surfaces: ['Market Overview'],
      },
    ],
    metadata: {
      source: 'playwright_admin_rail_contract',
      read_only: true,
      external_provider_calls: false,
      cache_mutation: false,
      secret_values_included: false,
      raw_provider_payloads_included: false,
    },
  };
}

function historicalOhlcvCachePreflightPayload() {
  return {
    generated_at: timestamp,
    diagnostic_only: true,
    runtime_enabled: true,
    dependency_available: true,
    required_bars: 60,
    require_adjusted: true,
    markets: [
      {
        market: 'US',
        runtime_enabled: true,
        dependency_available: true,
        symbols: [
          {
            market: 'US',
            symbol: 'ORCL',
            runtime_state: 'ready',
            cache_state: 'ready',
            dependency_state: 'ready',
            dependency_available: true,
            cached_bars: 80,
            latest_bar_date: '2026-06-05',
            freshness_state: 'fresh',
            adjustment_state: 'adjusted',
            data_state: 'ready',
            seed_state: 'not_required',
            next_action: { state: 'ready', summary: 'Read-only fixture ready.' },
          },
        ],
      },
    ],
    limitations: ['playwright_admin_rail_contract_fixture'],
    metadata: {
      source: 'playwright_admin_rail_contract',
      read_only: true,
      external_provider_calls: false,
      cache_mutation: false,
      secret_values_included: false,
      raw_provider_payloads_included: false,
    },
  };
}

function dataSourceGapRegistryPayload() {
  return {
    generated_at: timestamp,
    diagnostic_only: true,
    summary: {
      total_families: 1,
      ready_families: 1,
      blocked_families: 0,
      warning_families: 0,
      unknown_families: 0,
    },
    groups: [
      {
        group_id: 'admin_rail_contract',
        title: 'Admin rail contract fixture',
        families: [
          {
            family_key: 'admin_rail_contract',
            label: 'Admin rail contract fixture',
            status: 'ready',
            authority_state: 'ready',
            freshness_state: 'ready',
            impact_state: 'ready',
            data_hydration_allowed: false,
            score_trading_authority_allowed: false,
            external_license_required: false,
            protected_review_required: false,
            affected_surfaces: ['Market Overview'],
            missing_evidence: [],
            action_plan: [],
          },
        ],
      },
    ],
    metadata: {
      source: 'playwright_admin_rail_contract',
      read_only: true,
      external_provider_calls: false,
      cache_mutation: false,
      secret_values_included: false,
      raw_provider_payloads_included: false,
    },
  };
}

function professionalDataCapabilitiesPayload() {
  return {
    generated_at: timestamp,
    diagnostic_only: true,
    summary: {
      total_count: 1,
      ready_count: 1,
      blocked_count: 0,
      warning_count: 0,
      unknown_count: 0,
    },
    capabilities: [
      {
        capability_id: 'admin_rail_contract',
        category: 'market',
        label: 'Admin rail contract fixture',
        status: 'ready',
        readiness_state: 'ready',
        source_label: 'Playwright fixture',
        freshness: 'same_day',
        reason: 'Read-only admin rail fixture is ready.',
        affected_surfaces: ['Market Overview'],
      },
    ],
    metadata: {
      source: 'playwright_admin_rail_contract',
      read_only: true,
      external_provider_calls: false,
      cache_mutation: false,
      secret_values_included: false,
      raw_provider_payloads_included: false,
    },
  };
}

async function installAdminRailMocks(page: Page) {
  await installAdminAuthHarness(page);

  await page.route('**/api/v1/admin/logs**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === 'POST') {
      return fulfillJson(route, { mode: 'retention', dry_run: true, matched_log_count: 0, matched_event_count: 0, deleted_log_count: 0, deleted_event_count: 0, additional_cleanup_needed: false });
    }
    if (path === '/api/v1/admin/logs/storage/summary') {
      return fulfillJson(route, adminLogStoragePayload());
    }
    if (path === '/api/v1/admin/logs/sessions') {
      return fulfillJson(route, sessionsPayload());
    }
    return fulfillJson(route, businessEventsPayload());
  });
  await page.route('**/api/v1/admin/providers/operations-matrix', (route) => fulfillJson(route, providerOperationsMatrixPayload()));
  await page.route('**/api/v1/admin/provider-activation-verifier', (route) => fulfillJson(route, providerActivationVerifierPayload()));
  await page.route('**/api/v1/admin/historical-ohlcv/cache-preflight**', (route) => fulfillJson(route, historicalOhlcvCachePreflightPayload()));
  await page.route('**/api/v1/admin/market-providers/operations**', (route) => fulfillJson(route, marketProviderOperationsPayload()));
  await page.route('**/api/v1/market/data-readiness**', (route) => fulfillJson(route, marketDataReadinessPayload()));
  await page.route('**/api/v1/market/data-source-gap-registry', (route) => fulfillJson(route, dataSourceGapRegistryPayload()));
  await page.route('**/api/v1/market/professional-data-capabilities/admin', (route) => fulfillJson(route, professionalDataCapabilitiesPayload()));
}

async function expectAdminRailContract(page: Page, viewportWidth: number) {
  const pageShell = page.locator('[data-terminal-primitive="page-shell"]').first();
  await expect(pageShell).toBeVisible({ timeout: 15_000 });

  const metrics = await page.evaluate(() => {
    const parsePx = (value: string) => {
      const parsed = Number.parseFloat(value);
      return Number.isFinite(parsed) ? parsed : null;
    };
    const isVisible = (element: Element) => {
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
    };

    const contentFrame = document.querySelector('.shell-content-frame');
    const mainColumn = document.querySelector('.shell-main-column');
    const visiblePageShells = Array.from(document.querySelectorAll('[data-terminal-primitive="page-shell"]')).filter(isVisible);
    const shell = visiblePageShells[0];
    const shellStyle = shell ? window.getComputedStyle(shell) : null;
    const shellRect = shell?.getBoundingClientRect();
    const mainRect = mainColumn?.getBoundingClientRect();

    return {
      documentClientWidth: document.documentElement.clientWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      visiblePageShellCount: visiblePageShells.length,
      contentFrameClassName: contentFrame?.className || '',
      mainColumnClassName: mainColumn?.className || '',
      mainColumnWidth: mainRect?.width ?? null,
      pageShellWidth: shellRect?.width ?? null,
      pageShellMaxWidth: shellStyle?.maxWidth || '',
      pageShellMaxWidthPx: shellStyle ? parsePx(shellStyle.maxWidth) : null,
      consumerShellMax: shellStyle?.getPropertyValue('--wolfy-consumer-shell-max').trim() || '',
    };
  });

  expect(metrics.documentScrollWidth).toBeLessThanOrEqual(metrics.documentClientWidth + 1);
  expect(metrics.contentFrameClassName).toContain('shell-content-frame--system-control');
  expect(metrics.mainColumnClassName).toContain('shell-main-column--system-control');
  expect(metrics.mainColumnClassName.split(/\s+/)).toContain('p-0');
  expect(metrics.visiblePageShellCount).toBeGreaterThanOrEqual(1);
  expect(metrics.pageShellWidth).not.toBeNull();
  expect(metrics.pageShellMaxWidthPx).not.toBeNull();
  expect(metrics.pageShellMaxWidthPx ?? 0).toBeGreaterThanOrEqual(1500);
  expect(metrics.pageShellMaxWidthPx ?? 0).toBeLessThanOrEqual(1700);
  expect(metrics.pageShellMaxWidth).not.toContain('1880');
  expect(metrics.consumerShellMax).not.toContain('1880');
  expect(metrics.pageShellWidth ?? 0).toBeLessThanOrEqual(Math.min(viewportWidth, metrics.pageShellMaxWidthPx ?? 1600) + 2);

  if (viewportWidth >= 1900) {
    expect(metrics.mainColumnWidth).not.toBeNull();
    expect(metrics.pageShellWidth ?? 0).toBeLessThanOrEqual(1664);
    expect((metrics.mainColumnWidth ?? 0) - (metrics.pageShellWidth ?? 0)).toBeGreaterThanOrEqual(120);
  }
}

test.describe('admin system-control rail contract', () => {
  for (const viewport of viewports) {
    for (const route of adminRailRoutes) {
      test(`${route.path} keeps the 1600px admin rail at ${viewport.width}px`, async ({ page }) => {
        await page.setViewportSize(viewport);
        await installAdminRailMocks(page);
        await page.goto(route.path);
        await page.waitForLoadState('domcontentloaded');

        await expect(page).toHaveURL(new RegExp(`${route.path.replaceAll('/', '\\/')}$`));
        await expect(page.getByTestId(route.readyTestId)).toBeVisible({ timeout: 15_000 });
        await expectNoHorizontalOverflow(page);
        await expectAdminRailContract(page, viewport.width);
      });
    }
  }
});
