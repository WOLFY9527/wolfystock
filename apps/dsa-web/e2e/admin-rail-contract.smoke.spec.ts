import type { Page, Route } from '@playwright/test';
import { expect, expectNoHorizontalOverflow, installAdminAuthHarness, test } from './fixtures/adminAuth';
import { createMockAdminUser, createMockAuthStatus } from '../src/test-utils/adminAuthHarness';
import type { CurrentUser } from '../src/api/auth';

const timestamp = '2026-06-06T10:30:00+08:00';

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
  for (const route of adminRailRoutes) {
    test(`${route.path} keeps the 1600px admin rail`, async ({ page }, testInfo) => {
        await installAdminRailMocks(page);
        await page.goto(route.path);
        await page.waitForLoadState('domcontentloaded');

        await expect(page).toHaveURL(new RegExp(`${route.path.replaceAll('/', '\\/')}$`));
        await expect(page.getByTestId(route.readyTestId)).toBeVisible({ timeout: 15_000 });
        await expectNoHorizontalOverflow(page);
      await expectAdminRailContract(page, page.viewportSize()!.width);
      if (route.path === '/zh/settings/system') {
        if (testInfo.project.name === 'chromium-mobile') {
          await runRecoveryMobileContract(page);
        } else {
          await runRecoveryDesktopContract(page);
        }
      }
    });
  }
});

type RecoverySessionKind = 'guest' | 'user' | 'admin';

const recoveryConsumerDirectLinks = [
  { label: '首页', path: '/' },
  { label: '观察列表', path: '/watchlist' },
  { label: '持仓', path: '/portfolio' },
] as const;

const recoveryConsumerGroups = [
  {
    key: 'market',
    children: [
      { label: '市场总览', path: '/market-overview' },
      { label: '流动性监测', path: '/market/liquidity-monitor' },
      { label: '板块轮动', path: '/market/rotation-radar' },
    ],
  },
  {
    key: 'research',
    children: [
      { label: '研究雷达', path: '/research/radar' },
      { label: '个股研究', path: '/stocks/structure-decision' },
      { label: '扫描器', path: '/scanner' },
    ],
  },
  {
    key: 'validate',
    children: [
      { label: '回测', path: '/backtest' },
      { label: '情景实验室', path: '/scenario-lab' },
      { label: '期权实验室', path: '/options-lab' },
    ],
  },
] as const;

const recoveryAdminDestinations = [
  { label: '运维总览/系统设置', path: '/settings/system' },
  { label: 'Launch Cockpit', path: '/admin/launch-cockpit' },
  { label: '系统日志', path: '/admin/logs' },
  { label: '证据复核', path: '/admin/evidence-workflow' },
  { label: '通知通道', path: '/admin/notifications' },
  { label: '数据源与就绪度', path: '/admin/market-providers' },
  { label: '熔断诊断', path: '/admin/provider-circuits' },
  { label: '用户治理', path: '/admin/users' },
  { label: '成本观测', path: '/admin/cost-observability' },
] as const;

const recoveryDesktopViewports = [
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
] as const;

function recoveryUserSession(): CurrentUser {
  return {
    id: 'shell-recovery-user',
    username: 'shell-user',
    displayName: 'Shell User',
    role: 'user',
    isAdmin: false,
    isAuthenticated: true,
    transitional: false,
    authEnabled: true,
  };
}

function recoverySessionStatus(session: RecoverySessionKind) {
  if (session === 'guest') return createMockAuthStatus(null);
  return createMockAuthStatus(session === 'admin' ? createMockAdminUser() : recoveryUserSession());
}

function recoveryUnavailableDashboardOverview() {
  const metric = { label: 'Unavailable', value: '--', change: '--', status: 'unavailable' };
  return {
    status: 'unavailable',
    as_of: '',
    market_pulse: {
      sp500: metric,
      nasdaq: metric,
      russell2000: metric,
      vix: metric,
      ten_year_yield: metric,
      dollar_index: metric,
      market_breadth: { summary: 'Unavailable', status: 'unavailable' },
      liquidity_state: 'unavailable',
    },
    market_brief: { headline: 'Unavailable', summary: 'Unavailable', status: 'unavailable' },
    money_flow: {
      top_inflows: [],
      top_outflows: [],
      style_bias: 'unavailable',
      offensive_defensive_bias: 'unavailable',
      source_status: 'unavailable',
      status: 'unavailable',
    },
    liquidity_risk: {
      summary: 'Unavailable',
      volatility_tone: 'unavailable',
      funding_stress: 'unavailable',
      dollar_rate_pressure: 'unavailable',
      status: 'unavailable',
    },
    sector_theme_rotation: {
      leading_themes: [],
      lagging_themes: [],
      diffusion: 'unavailable',
      summary: 'Unavailable',
      status: 'unavailable',
    },
    research_queue: { status: 'unavailable', items: [] },
    data_quality: { state: 'unavailable', label: 'Unavailable', summary: 'Unavailable', sections: {} },
    no_advice_disclosure: 'Unavailable',
  };
}

async function installRecoverySessionHarness(page: Page, initialSession: RecoverySessionKind): Promise<void> {
  let session = initialSession;

  await page.addInitScript(() => {
    class TestEventSource {
      onopen: ((event: Event) => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;

      addEventListener() {}
      removeEventListener() {}
      close() {}
    }
    Object.defineProperty(window, 'EventSource', {
      value: TestEventSource,
      writable: true,
      configurable: true,
    });
  });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;

    if (request.method() === 'GET' && path === '/api/v1/auth/status') {
      return fulfillJson(route, recoverySessionStatus(session));
    }
    if (request.method() === 'GET' && path === '/api/v1/auth/me') {
      const currentUser = session === 'guest'
        ? null
        : session === 'admin'
          ? createMockAdminUser()
          : recoveryUserSession();
      return currentUser
        ? fulfillJson(route, currentUser)
        : fulfillJson(route, { error: 'not_authenticated' }, 401);
    }
    if (request.method() === 'GET' && path === '/api/v1/dashboard/market-intelligence-overview') {
      return fulfillJson(route, recoveryUnavailableDashboardOverview());
    }
    if (request.method() === 'POST' && path === '/api/v1/auth/login') {
      session = 'user';
      return fulfillJson(route, { ok: true });
    }
    if (request.method() === 'POST' && path === '/api/v1/auth/logout') {
      session = 'guest';
      return fulfillJson(route, { ok: true });
    }

    return fulfillJson(route, { detail: `fixture response for ${request.method()} ${path}` });
  });
}

async function expectRecoveryMenuPointerReachable(page: Page, testId: string) {
  const menu = page.getByTestId(testId);
  await expect(menu).toBeVisible();
  const metrics = await menu.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const style = window.getComputedStyle(element);
    const pointX = rect.left + Math.min(12, Math.max(1, rect.width / 2));
    const pointY = rect.top + Math.min(12, Math.max(1, rect.height / 2));
    const hit = document.elementFromPoint(pointX, pointY);
    return {
      width: rect.width,
      height: rect.height,
      top: rect.top,
      bottom: rect.bottom,
      viewportHeight: window.innerHeight,
      display: style.display,
      visibility: style.visibility,
      pointerEvents: style.pointerEvents,
      hitInsideMenu: Boolean(hit && element.contains(hit)),
    };
  });

  expect(metrics.width).toBeGreaterThan(0);
  expect(metrics.height).toBeGreaterThan(0);
  expect(metrics.top).toBeGreaterThanOrEqual(0);
  expect(metrics.bottom).toBeLessThanOrEqual(metrics.viewportHeight);
  expect(metrics.display).not.toBe('none');
  expect(metrics.visibility).not.toBe('hidden');
  expect(metrics.pointerEvents).not.toBe('none');
  expect(metrics.hitInsideMenu).toBe(true);
}

async function openRecoveryConsumerHome(page: Page) {
  await page.goto('/');
  await expect(page.getByTestId('shell-consumer-primary-nav')).toBeVisible({ timeout: 15_000 });
}

async function recoveryDocumentNavigationCount(page: Page) {
  return page.evaluate(() => performance.getEntriesByType('navigation').length);
}

async function runRecoveryDesktopContract(page: Page) {
  await page.unroute('**/api/v1/**');
  await installRecoverySessionHarness(page, 'user');
  for (const viewport of recoveryDesktopViewports) {
    await page.setViewportSize(viewport);
    await openRecoveryConsumerHome(page);
    for (const directLink of recoveryConsumerDirectLinks) {
      const navigationCount = await recoveryDocumentNavigationCount(page);
      await page.getByTestId('shell-consumer-primary-nav').getByRole('link', { name: directLink.label }).click();
      await expect(page).toHaveURL(new RegExp(`${directLink.path === '/' ? '\\/$' : `${directLink.path.replaceAll('/', '\\/')}$`}`));
      await expect(page.getByTestId('shell-consumer-primary-nav')).toBeVisible();
      expect(await recoveryDocumentNavigationCount(page)).toBe(navigationCount);
    }

    for (const group of recoveryConsumerGroups) {
      await openRecoveryConsumerHome(page);
      const trigger = page.getByTestId(`shell-nav-group-trigger-${group.key}`);
      await trigger.click();
      const menuTestId = `shell-nav-group-menu-${group.key}`;
      await expectRecoveryMenuPointerReachable(page, menuTestId);
      await page.keyboard.press('Escape');
      await expect(page.getByTestId(menuTestId)).toHaveCount(0);
      await expect(trigger).toBeFocused();
      await trigger.click();
      await expectRecoveryMenuPointerReachable(page, menuTestId);
      await page.mouse.click(4, 200);
      await expect(page.getByTestId(menuTestId)).toHaveCount(0);

      for (const child of group.children) {
        await openRecoveryConsumerHome(page);
        await page.getByTestId(`shell-nav-group-trigger-${group.key}`).click();
        await expectRecoveryMenuPointerReachable(page, menuTestId);
        const navigationCount = await recoveryDocumentNavigationCount(page);
        await page.getByTestId(menuTestId).getByRole('link', { name: child.label }).click();
        await expect(page).toHaveURL(new RegExp(`${child.path.replaceAll('/', '\\/')}$`));
        await expect(page.getByTestId(menuTestId)).toHaveCount(0);
        expect(await recoveryDocumentNavigationCount(page)).toBe(navigationCount);
      }
    }
  }

  await page.unroute('**/api/v1/**');
  await installRecoverySessionHarness(page, 'guest');
  await page.goto('/login?redirect=/');
  await page.locator('#username').fill('shell-user');
  await page.locator('#password').fill('fixture-password');
  await page.getByRole('button', { name: /登录继续|sign in/i }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId('shell-account-center-entry')).toContainText('Shell User');
  await expect(page.getByRole('link', { name: '登录' })).toHaveCount(0);
  await page.reload();
  await expect(page.getByTestId('shell-account-center-entry')).toContainText('Shell User');
  await page.goto('/portfolio');
  await expect(page.getByTestId('shell-account-center-entry')).toContainText('Shell User');
  await page.getByTestId('shell-account-center-entry').getByRole('button', { name: '账户中心' }).click();
  await page.getByTestId('shell-account-center-menu').getByRole('menuitem', { name: '退出登录' }).click();
  await page.getByRole('dialog', { name: '退出登录' }).getByRole('button', { name: '确认退出' }).click();
  await expect(page).toHaveURL(/\/guest$/);
  await expect(page.getByRole('link', { name: '登录' })).toBeVisible();

  await page.unroute('**/api/v1/**');
  await installRecoverySessionHarness(page, 'admin');
  for (const destination of recoveryAdminDestinations) {
    await openRecoveryConsumerHome(page);
    await page.getByRole('button', { name: '系统' }).click();
    const menu = page.getByTestId('shell-admin-utility-menu');
    await expect(menu).toBeVisible();
    const link = menu.getByRole('link', { name: destination.label });
    await expect(link).toHaveAttribute('href', destination.path);
    await link.click();
    await expect(page).toHaveURL(new RegExp(`${destination.path.replaceAll('/', '\\/')}$`));
  }

  await page.unroute('**/api/v1/**');
  await installRecoverySessionHarness(page, 'user');
  await openRecoveryConsumerHome(page);
  await expect(page.getByRole('button', { name: '系统' })).toHaveCount(0);
  await page.goto('/settings/system');
  await expect(page.getByRole('heading', { name: '这个页面需要管理员账户' })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId('shell-admin-primary-nav')).toHaveCount(0);
}

async function runRecoveryMobileContract(page: Page) {
  await page.unroute('**/api/v1/**');
  await installRecoverySessionHarness(page, 'user');
  await page.goto('/');
  await expect(page.locator('#shell-mobile-navigation-trigger')).toBeVisible({ timeout: 15_000 });
  await page.locator('#shell-mobile-navigation-trigger').click();
  const drawer = page.getByTestId('shell-mobile-navigation-menu');
  await expect(drawer).toBeVisible();
  for (const directLink of recoveryConsumerDirectLinks) {
    await expect(drawer.getByRole('link', { name: directLink.label })).toHaveAttribute('href', directLink.path);
  }
  for (const group of recoveryConsumerGroups) {
    for (const child of group.children) {
      await expect(drawer.getByRole('link', { name: child.label })).toHaveAttribute('href', child.path);
    }
  }
  await drawer.getByRole('link', { name: '市场总览' }).click();
  await expect(page).toHaveURL(/\/market-overview$/);
  await expect(drawer).toHaveCount(0);
}
