import type { Page, Route } from '@playwright/test';
import { expect as appExpect, test as appTest } from './fixtures/appSmoke';
import { expect as adminExpect, expectNoHorizontalOverflow as expectNoAdminHorizontalOverflow, expectNoRawSecretLikeText, installAdminAuthHarness, openAdminRouteWithHarness, test as adminTest } from './fixtures/adminAuth';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
] as const;

const forbiddenAffordancePattern = /Bootstrap Admin|debug|internal|provider route|cache router|\benv\b|credential/i;

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

function marketProviderOperationsPayload() {
  return {
    generated_at: '2026-06-05T00:00:00Z',
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
        provider: 'sina',
        source_label: '新浪财经',
        source_type: 'public_api',
        domain: 'equity_index',
        endpoint: '/api/v1/market/cn-indices',
        card: 'ChinaIndicesCard',
        cache_key: 'cn_indices',
        status: 'live',
        freshness: 'live',
        as_of: '2026-06-05T00:00:00Z',
        updated_at: '2026-06-05T00:00:00Z',
        last_successful_at: '2026-06-05T00:00:00Z',
        last_known_good_age_minutes: 2,
        latency_ms: 128,
        is_fallback: false,
        is_stale: false,
        is_refreshing: false,
        is_from_snapshot: false,
        fallback_used: false,
        warning: null,
        error_summary: null,
        admin_log_drill_through: { label: '查看 Admin Logs', route: '/zh/admin/logs', query: { since: '24h', provider: 'sina' } },
      },
    ],
    event_rollups: [],
    cache_states: [],
    limitations: [],
    admin_log_drill_through: { label: '查看 Admin Logs', route: '/zh/admin/logs', query: { since: '24h' } },
    metadata: { source: 'mocked_playwright', read_only: true, external_provider_calls: false, cache_mutation: false },
  };
}

function providerOperationsMatrixPayload() {
  return {
    generated_at: '2026-06-05T00:00:00Z',
    diagnostic_only: true,
    rows: [
      {
        provider_id: 'market_fixture',
        provider_name: 'Market fixture',
        source_label: 'Local audit fixture',
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
        authority_basis: 'Local audit fixture for route alias smoke.',
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
      source: 'local_audit_fixture',
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
        id: 'market_fixture_ready',
        status: 'ready',
        severity: 'info',
        user_facing_message: '本地审核样例已覆盖市场数据读取。',
        remediation_hint: null,
        affects_surfaces: ['Market Overview'],
        product_affected_surfaces: ['Market Overview'],
        secret_configured: false,
        details: { read_only: true },
      },
    ],
  };
}

async function installSignedInProductSession(page: Page) {
  const currentUser = {
    id: 'user-1',
    username: 'wolfy-user',
    displayName: 'Wolfy User',
    role: 'user',
    isAdmin: false,
    isAuthenticated: true,
    transitional: false,
    authEnabled: true,
  };

  await page.route('**/api/v1/auth/status**', async (route) => {
    await fulfillJson(route, {
      authEnabled: true,
      loggedIn: true,
      passwordSet: true,
      passwordChangeable: true,
      setupState: 'enabled',
      currentUser,
    });
  });

  await page.route('**/api/v1/auth/me**', async (route) => {
    await fulfillJson(route, currentUser);
  });
}

async function installGuestProductSession(page: Page) {
  await page.route('**/api/v1/auth/status**', async (route) => {
    await fulfillJson(route, {
      authEnabled: true,
      loggedIn: false,
      passwordSet: true,
      passwordChangeable: false,
      setupState: 'enabled',
      currentUser: null,
    });
  });

  await page.route('**/api/v1/auth/me**', async (route) => {
    await fulfillJson(route, { error: 'not_authenticated' }, 401);
  });
}

async function expectNoHorizontalOverflow(page: Page) {
  await appExpect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function expectRootNonEmpty(page: Page) {
  await appExpect.poll(async () => page.locator('#root').evaluate((root) => root.textContent?.trim().length ?? 0)).toBeGreaterThan(0);
}

function normalizeText(text: string) {
  return text.replace(/\s+/g, ' ').trim();
}

async function expectNoForbiddenAffordanceText(text: string) {
  appExpect(text).not.toMatch(forbiddenAffordancePattern);
}

async function readVisibleText(page: Page) {
  return normalizeText(await page.locator('body').innerText());
}

async function expectMarketRedirectSurface(page: Page, isMobile: boolean) {
  await appExpect(page).toHaveURL(/\/zh\/market-overview$/);
  await appExpect(page.getByTestId('market-overview-shell')).toBeVisible({ timeout: 15_000 });
  await appExpect(page.getByRole('heading', { name: '市场总览' })).toBeVisible();
  await expectRootNonEmpty(page);
  await expectNoHorizontalOverflow(page);

  if (isMobile) {
    await appExpect(page.getByTestId('shell-mobile-active-route')).toHaveText('市场总览');
  } else {
    const nav = page.getByRole('navigation', { name: '导航菜单' });
    await appExpect(nav.getByRole('link', { name: '市场总览' })).toHaveClass(/is-active/);
    const accountEntry = page.getByTestId('shell-account-center-entry');
    await appExpect(accountEntry).toBeVisible();
    await appExpect(accountEntry).toContainText('Wolfy User');
    await expectNoForbiddenAffordanceText(await accountEntry.innerText());
  }

  await expectNoForbiddenAffordanceText(await readVisibleText(page));
}

async function expectGuestAdminGate(page: Page) {
  await appExpect(page).toHaveURL(/\/zh\/guest$/);
  await appExpect(page.getByTestId('guest-home-clean-search')).toBeVisible({ timeout: 15_000 });
  await appExpect(page.getByTestId('guest-home-command-surface')).toBeVisible();
  await appExpect(page.getByTestId('guest-home-market-preview-strip')).toContainText('当前市场观察');
  await appExpect(page.getByTestId('guest-home-command-workflow')).toContainText('搜索');
  await appExpect(page.getByTestId('guest-home-command-workflow')).toContainText('分析');
  await appExpect(page.getByTestId('guest-home-command-workflow')).toContainText('观察');
  await appExpect(page.getByTestId('guest-home-registration-link')).toBeVisible();
  await expectRootNonEmpty(page);
  await expectNoHorizontalOverflow(page);

  await expectNoForbiddenAffordanceText(await readVisibleText(page));
}

async function expectSignedInNonAdminAdminGate(page: Page, expectedPath: RegExp, isMobile: boolean) {
  await appExpect(page).toHaveURL(expectedPath);
  await appExpect(page.getByRole('heading', { name: '这个页面需要管理员账户' })).toBeVisible({ timeout: 15_000 });
  await appExpect(page.getByTestId('shell-admin-primary-nav')).toHaveCount(0);
  await appExpect(page.getByRole('button', { name: /独立控制台|Independent Console/i })).toHaveCount(0);
  await appExpect(page.getByRole('link', { name: '运维总览/系统设置' })).toHaveCount(0);
  await appExpect(page.getByRole('link', { name: '数据源与就绪度' })).toHaveCount(0);

  if (isMobile) {
    await appExpect(page.getByTestId('shell-mobile-active-route')).toBeVisible();
    await page.getByRole('button', { name: '打开导航菜单' }).click();
    await appExpect(page.getByRole('heading', { name: '导航菜单' })).toBeVisible();
    await appExpect(page.getByRole('button', { name: /独立控制台|Independent Console/i })).toHaveCount(0);
    await appExpect(page.getByRole('link', { name: '运维总览/系统设置' })).toHaveCount(0);
    await appExpect(page.getByRole('link', { name: '数据源与就绪度' })).toHaveCount(0);
  } else {
    const consumerNav = page.getByTestId('shell-consumer-primary-nav');
    await appExpect(consumerNav).toBeVisible();
    await appExpect(consumerNav.getByRole('link', { name: '首页' })).toBeVisible();
    await appExpect(consumerNav.getByRole('link', { name: '扫描器' })).toBeVisible();
    await appExpect(consumerNav.getByRole('link', { name: '持仓' })).toBeVisible();
  }

  await expectRootNonEmpty(page);
  await expectNoHorizontalOverflow(page);
  await expectNoForbiddenAffordanceText(await readVisibleText(page));
}

async function expectAdminRedirectSurface(page: Page, isMobile: boolean) {
  await adminExpect(page).toHaveURL(/\/zh\/settings\/system$/);
  await adminExpect(page.getByTestId('system-settings-page')).toBeVisible({ timeout: 15_000 });
  await adminExpect(page.getByRole('heading', { name: '系统设置' })).toBeVisible({ timeout: 15_000 });
  await adminExpect(page.getByRole('button', { name: 'AI 模型' })).toBeVisible();
  await adminExpect(page.getByRole('button', { name: '数据源' })).toBeVisible();
  await expectNoAdminHorizontalOverflow(page);
  await expectNoRawSecretLikeText(page);

  if (isMobile) {
    await adminExpect(page.getByTestId('shell-mobile-active-route')).toHaveText('运维总览/系统设置');
    await page.getByRole('button', { name: '打开导航菜单' }).click();
  } else {
    const accountEntry = page.getByTestId('shell-account-center-entry');
    await adminExpect(accountEntry).toBeVisible();
    await adminExpect(accountEntry).toContainText('管理员');
    await adminExpect(accountEntry).not.toContainText(/Bootstrap Admin/i);
    await expectNoForbiddenAffordanceText(await accountEntry.innerText());
    await adminExpect(page.getByTestId('shell-header-utility-island').getByRole('button', { name: /系统|System/i })).toHaveCount(0);
  }

  const adminNav = page.getByTestId('shell-admin-primary-nav');
  await adminExpect(adminNav).toBeVisible();
  await adminExpect(adminNav.getByRole('link', { name: '运维总览/系统设置' })).toHaveClass(/is-active/);
  await adminExpect(adminNav.getByRole('link', { name: '数据源与就绪度' })).toBeVisible();
  await adminExpect(adminNav.getByRole('link', { name: '熔断诊断' })).toBeVisible();
  await adminExpect(adminNav.getByRole('link', { name: '系统日志' })).toBeVisible();
  await adminExpect(adminNav.getByRole('link', { name: '成本观测' })).toBeVisible();
  await adminExpect(adminNav.getByRole('link', { name: '用户治理' })).toBeVisible();
  await adminExpect(adminNav.getByRole('link', { name: '证据复核' })).toBeVisible();
  await adminExpect(adminNav.getByRole('link', { name: '通知通道' })).toBeVisible();
  await adminExpect(adminNav.getByRole('link', { name: '首页' })).toHaveCount(0);
  await adminExpect(page.getByTestId('shell-consumer-primary-nav')).toHaveCount(0);
  await adminExpect(page.getByTestId('shell-admin-utility-menu')).toHaveCount(0);
  await expectNoForbiddenAffordanceText(await adminNav.innerText());
}

async function expectAdminAliasTarget(page: Page, targetPattern: RegExp, visibleTestId: string) {
  await adminExpect(page).toHaveURL(targetPattern);
  await adminExpect(page.getByTestId(visibleTestId)).toBeVisible({ timeout: 15_000 });
  await expectNoAdminHorizontalOverflow(page);
  await expectNoRawSecretLikeText(page);
  await expectNoForbiddenAffordanceText(await readVisibleText(page));
}

async function installProviderOpsMocks(page: Page) {
  await page.route('**/api/v1/admin/providers/operations-matrix', (route) => fulfillJson(route, providerOperationsMatrixPayload()));
  await page.route('**/api/v1/market/data-readiness**', (route) => fulfillJson(route, marketDataReadinessPayload()));
  await page.route('**/api/v1/admin/market-providers/operations**', (route) => fulfillJson(route, marketProviderOperationsPayload()));
}

appTest.describe('shell route clarity smoke', () => {
  appTest('redirects /zh/market to market overview with product-safe shell affordances', async ({ page }) => {
    for (const viewport of viewports) {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await page.setViewportSize(viewport);
      await installSignedInProductSession(page);
      await page.goto('/zh/market');
      await page.waitForLoadState('domcontentloaded');
      await expectMarketRedirectSurface(page, viewport.width < 768);
    }
  });

  appTest('redirects guest /zh/admin to understandable admin sign-in guidance', async ({ page }) => {
    for (const viewport of viewports) {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await page.setViewportSize(viewport);
      await installGuestProductSession(page);
      await page.goto('/zh/admin');
      await page.waitForLoadState('domcontentloaded');
      await expectGuestAdminGate(page);
    }
  });

  appTest('keeps signed-in non-admin admin aliases on clear generic gates without empty admin navigation', async ({ page }) => {
    const aliases = [
      { path: '/zh/admin/system', expectedPath: /\/zh\/settings\/system$/ },
      { path: '/zh/admin/providers', expectedPath: /\/zh\/admin\/market-providers$/ },
      { path: '/zh/admin/evidence', expectedPath: /\/zh\/admin\/evidence-workflow$/ },
      { path: '/zh/admin/costs', expectedPath: /\/zh\/admin\/cost-observability$/ },
      { path: '/zh/admin/ai', expectedPath: /\/zh\/settings\/system$/ },
    ] as const;

    for (const viewport of viewports) {
      for (const alias of aliases) {
        await page.unrouteAll({ behavior: 'ignoreErrors' });
        await page.setViewportSize(viewport);
        await installSignedInProductSession(page);
        await page.goto(alias.path);
        await page.waitForLoadState('domcontentloaded');
        await expectSignedInNonAdminAdminGate(page, alias.expectedPath, viewport.width < 768);
      }
    }
  });
});

adminTest.describe('admin redirect affordance smoke', () => {
  adminTest('redirects /zh/admin to system settings with product-safe admin affordances', async ({ page }) => {
    for (const viewport of viewports) {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await page.setViewportSize(viewport);
      await openAdminRouteWithHarness(page, '/zh/admin', { displayName: 'Bootstrap Admin' });
      await expectAdminRedirectSurface(page, viewport.width < 768);
    }
  });

  adminTest('redirects UX-audited admin short routes to canonical admin surfaces without leakage', async ({ page }) => {
    const aliases = [
      { path: '/zh/admin/system', url: /\/zh\/settings\/system$/, testId: 'system-settings-page' },
      { path: '/zh/admin/providers', url: /\/zh\/admin\/market-providers$/, testId: 'market-provider-operations-page' },
      { path: '/zh/admin/evidence', url: /\/zh\/admin\/evidence-workflow$/, testId: 'admin-evidence-workflow-page' },
      { path: '/zh/admin/costs', url: /\/zh\/admin\/cost-observability$/, testId: 'admin-cost-observability-page' },
      { path: '/zh/admin/ai', url: /\/zh\/settings\/system$/, testId: 'system-settings-page' },
    ] as const;

    for (const viewport of viewports) {
      for (const alias of aliases) {
        await page.unrouteAll({ behavior: 'ignoreErrors' });
        await page.setViewportSize(viewport);
        await installAdminAuthHarness(page, { displayName: 'Bootstrap Admin' });
        await installProviderOpsMocks(page);
        await page.goto(alias.path);
        await page.waitForLoadState('domcontentloaded');
        await adminExpect(page).not.toHaveURL(/\/guest(?:$|[/?#])/);
        await expectAdminAliasTarget(page, alias.url, alias.testId);
      }
    }
  });
});
