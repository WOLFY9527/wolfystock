import { expect as baseExpect, type Page, type Route } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';
import { createMockAdminUser, createMockAuthStatus } from '../src/test-utils/adminAuthHarness';

const adminUser = createMockAdminUser({
  displayName: 'UAT Route Admin',
  username: 'playwright-admin',
});

type RouteIdentity = {
  label: string;
  path: string;
  expectedUrl: RegExp;
  readyTestId: string;
  heading?: RegExp;
  extra?: (page: Page) => Promise<void>;
};

const protectedRoutes: RouteIdentity[] = [
  {
    label: '/market-overview',
    path: '/zh/market-overview',
    expectedUrl: /\/zh\/market-overview$/,
    readyTestId: 'market-overview-shell',
    heading: /市场总览/,
    extra: async (page) => {
      await expect(page.getByTestId('market-overview-card-indices')).toBeVisible();
      await expect(page.getByTestId('market-overview-decision-readiness')).toBeVisible();
      await expect(page.locator('body')).not.toContainText(/request timed out|timeout|请求超时|加载失败|无法加载|部分数据暂不可用|正在刷新，稍后自动更新/i);
    },
  },
  {
    label: '/scanner',
    path: '/zh/scanner',
    expectedUrl: /\/zh\/scanner$/,
    readyTestId: 'user-scanner-workspace',
    heading: /扫描器/,
  },
  {
    label: '/watchlist',
    path: '/zh/watchlist',
    expectedUrl: /\/zh\/watchlist$/,
    readyTestId: 'watchlist-page',
    heading: /观察列表|watchlist/i,
  },
  {
    label: '/portfolio',
    path: '/zh/portfolio',
    expectedUrl: /\/zh\/portfolio$/,
    readyTestId: 'portfolio-bento-page',
    heading: /组合总览|总资产|Portfolio/i,
  },
  {
    label: '/market/liquidity-monitor',
    path: '/zh/market/liquidity-monitor',
    expectedUrl: /\/zh\/market\/liquidity-monitor$/,
    readyTestId: 'liquidity-monitor-guidance-panel',
    heading: /流动性监测/,
  },
  {
    label: '/market/rotation-radar',
    path: '/zh/market/rotation-radar',
    expectedUrl: /\/zh\/market\/rotation-radar$/,
    readyTestId: 'market-rotation-radar-page',
    heading: /主题轮动雷达/,
  },
  {
    label: '/options-lab',
    path: '/zh/options-lab',
    expectedUrl: /\/zh\/options-lab$/,
    readyTestId: 'options-lab-decision-engine',
    heading: /期权实验室/,
  },
  {
    label: '/backtest',
    path: '/zh/backtest',
    expectedUrl: /\/zh\/backtest$/,
    readyTestId: 'backtest-bento-page',
    heading: /回测/,
  },
  {
    label: '/admin/market-providers',
    path: '/zh/admin/market-providers',
    expectedUrl: /\/zh\/admin\/market-providers$/,
    readyTestId: 'market-provider-operations-page',
    heading: /数据源维护路线图/,
    extra: async (page) => {
      await expect(page.getByTestId('guest-home-clean-search')).toHaveCount(0);
      await expect(page.locator('body')).not.toContainText(/Guest Research Console|游客预览|访客会话|Guest session|Bootstrap Admin/i);
    },
  },
];

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installAdminLoginSession(page: Page) {
  let isLoggedIn = false;

  await page.route('**/api/v1/auth/status**', async (route) => {
    await fulfillJson(route, createMockAuthStatus(isLoggedIn ? adminUser : null));
  });
  await page.route('**/api/v1/auth/me**', async (route) => {
    await (isLoggedIn
      ? fulfillJson(route, adminUser)
      : fulfillJson(route, { error: 'not_authenticated' }, 401));
  });
  await page.route('**/api/v1/auth/login**', async (route) => {
    isLoggedIn = true;
    await fulfillJson(route, { ok: true, currentUser: adminUser });
  });
  await page.route('**/api/v1/auth/logout**', async (route) => {
    isLoggedIn = false;
    await fulfillJson(route, { ok: true });
  });
}

async function loginAsAdmin(page: Page) {
  await page.goto('/zh/login?redirect=%2Fzh%2Fmarket-overview');
  await page.waitForLoadState('domcontentloaded');

  const username = page.locator('#username');
  if (await username.isVisible().catch(() => false)) {
    await username.fill('playwright-admin');
  }
  await expect(page.locator('#password')).toBeVisible({ timeout: 15_000 });
  await page.locator('#password').fill('mock-admin-password');

  const submitButton = page.getByRole('button', { name: /授权进入工作台|完成设置并登录|登录继续|Sign in|Set password/i });
  await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/v1/auth/login') && response.status() === 200),
    submitButton.click(),
  ]);
  await page.waitForLoadState('domcontentloaded');
}

async function expectAuthenticatedAdminSession(page: Page) {
  const currentUser = await page.evaluate(async () => {
    const response = await fetch('/api/v1/auth/me');
    return {
      ok: response.ok,
      status: response.status,
      body: await response.json(),
    };
  });

  expect(currentUser.ok).toBe(true);
  expect(currentUser.status).toBe(200);
  expect(currentUser.body).toMatchObject({
    username: 'playwright-admin',
    role: 'admin',
    isAdmin: true,
    isAuthenticated: true,
  });
}

async function installRouteIdentityMocks(page: Page) {
  await page.route('**/api/v1/portfolio/accounts**', async (route) => {
    await fulfillJson(route, {
      accounts: [
        {
          id: 1,
          owner_id: 'pw-admin-user',
          name: 'UAT Route Portfolio',
          broker: 'IBKR',
          market: 'us',
          base_currency: 'USD',
          is_active: true,
          created_at: '2026-06-07T09:45:00-04:00',
          updated_at: '2026-06-07T09:45:00-04:00',
        },
      ],
    });
  });
  await page.route('**/api/v1/portfolio/imports/brokers**', async (route) => {
    await fulfillJson(route, { brokers: [] });
  });
  await page.route('**/api/v1/portfolio/broker-connections**', async (route) => {
    await fulfillJson(route, { connections: [] });
  });
  await page.route('**/api/v1/portfolio/trades**', async (route) => {
    await fulfillJson(route, { items: [], total: 0, page: 1, page_size: 20 });
  });
  await page.route('**/api/v1/portfolio/cash-ledger**', async (route) => {
    await fulfillJson(route, { items: [], total: 0, page: 1, page_size: 20 });
  });
  await page.route('**/api/v1/portfolio/corporate-actions**', async (route) => {
    await fulfillJson(route, { items: [], total: 0, page: 1, page_size: 20 });
  });
  await page.route('**/api/v1/portfolio/risk**', async (route) => {
    await fulfillJson(route, {
      as_of: '2026-06-07',
      account_id: null,
      cost_method: 'fifo',
      currency: 'USD',
      thresholds: {},
      concentration: { total_market_value: 0, top_weight_pct: 0, alert: false, top_positions: [] },
      sector_concentration: { total_market_value: 0, top_weight_pct: 0, alert: false, top_sectors: [], coverage: {}, errors: [] },
      drawdown: { series_points: 0, max_drawdown_pct: 0, current_drawdown_pct: 0, alert: false, fx_stale: false },
      stop_loss: { near_alert: false, triggered_count: 0, near_count: 0, items: [] },
    });
  });

  await page.route('**/api/v1/market/liquidity-monitor**', async (route) => {
    await fulfillJson(route, {
      endpoint: '/api/v1/market/liquidity-monitor',
      generated_at: '2026-06-07T10:30:00+08:00',
      score: { value: 64, regime: 'supportive', confidence: 0.76, included_indicator_count: 2, possible_indicator_weight: 2, included_indicator_weight: 2 },
      freshness: { status: 'live', weakest_indicator_freshness: 'live', latest_as_of: '2026-06-07T10:30:00+08:00' },
      indicators: [
        { key: 'policy_liquidity', label: 'Policy liquidity', status: 'live', freshness: 'live', included_in_score: true, score_contribution: 0.38, score_weight: 0.5, summary: '政策流动性保持稳定。', updated_at: '2026-06-07T10:30:00+08:00' },
      ],
      liquidity_impulse_synthesis: {
        liquidity_impulse: 'expanding',
        impulse_label: 'Liquidity is improving',
        subtype: 'broad_support',
        confidence: 0.76,
        confidence_label: 'medium',
        pillar_scores: { policy_liquidity: 66 },
        direction_score: 64,
        dominant_drivers: [],
        counter_evidence: [],
        data_gaps: [],
        narrative_bullets: ['流动性读数可用，当前适合观察。'],
        evidence_quality: {},
        not_investment_advice: true,
      },
      advisory_disclosure: '仅用于研究观察，不构成投资建议。',
      source_metadata: { external_provider_calls: false, provider_runtime_changed: false, market_cache_mutation: false },
    });
  });

  await page.route('**/api/v1/options/underlyings/*/summary', async (route) => {
    await fulfillJson(route, {
      symbol: 'TEM',
      market: 'us',
      underlying: { price: 52.34, change_pct: 1.2, source: 'uat_route_identity_fixture', as_of: '2026-06-07T09:45:00-04:00', freshness: 'mock' },
      options_availability: { supported: true, provider: 'uat_route_identity_fixture', limitations: ['mocked_route_identity_gate'] },
      metadata: { read_only: true, no_external_calls_in_tests: true, source_label: 'Playwright Fixture', updated_at: '2026-06-07T09:45:00-04:00' },
    });
  });
  await page.route('**/api/v1/options/underlyings/*/expirations', async (route) => {
    await fulfillJson(route, {
      symbol: 'TEM',
      expirations: [{ date: '2026-06-19', dte: 44, type: 'monthly', chain_available: true, as_of: '2026-06-07T09:45:00-04:00', source: 'uat_route_identity_fixture', warnings: [] }],
      metadata: { read_only: true, no_external_calls_in_tests: true },
    });
  });
  await page.route('**/api/v1/options/underlyings/*/chain**', async (route) => {
    await fulfillJson(route, {
      symbol: 'TEM',
      expiration: '2026-06-19',
      underlying: { price: 52.34, change_pct: 1.2, source: 'uat_route_identity_fixture', as_of: '2026-06-07T09:45:00-04:00', freshness: 'mock' },
      calls: [{ contract_symbol: 'TEM260619C00055000', side: 'call', strike: 55, bid: 4.13, ask: 4.33, mid: 4.23, volume: 500, open_interest: 3000, implied_volatility: 0.52, delta: 0.42, gamma: 0.04, theta: -0.05, vega: 0.11, spread_pct: 4.6, moneyness: 'atm', liquidity_score: 82, warnings: [] }],
      puts: [{ contract_symbol: 'TEM260619P00050000', side: 'put', strike: 50, bid: 2.32, ask: 2.52, mid: 2.42, volume: 500, open_interest: 3000, implied_volatility: 0.52, delta: -0.36, gamma: 0.04, theta: -0.05, vega: 0.11, spread_pct: 4.6, moneyness: 'otm', liquidity_score: 82, warnings: [] }],
      filters_applied: { min_open_interest: 100, max_spread_pct: 25 },
      chain_as_of: '2026-06-07T09:45:00-04:00',
      source: 'uat_route_identity_fixture',
      limitations: ['mocked_route_identity_gate'],
      metadata: { read_only: true, no_external_calls_in_tests: true },
    });
  });
  await page.route('**/api/v1/options/strategies/compare', async (route) => {
    await fulfillJson(route, {
      symbol: 'TEM',
      underlying: { price: 52.34, change_pct: 1.2, source: 'uat_route_identity_fixture', as_of: '2026-06-07T09:45:00-04:00', freshness: 'mock' },
      assumptions: { direction: 'bullish', target_price: 65, target_date: '2026-08-21' },
      strategies: [{
        strategy_type: 'bull_call_spread',
        legs: [{ action: 'buy', side: 'call', contract_symbol: 'TEM260619C00055000', expiration: '2026-06-19', strike: 55, mid: 4.23, quantity: 1 }],
        net_debit: 423,
        max_loss: 423,
        max_gain: 500,
        breakeven: 59.23,
        required_move_pct: 13.2,
        payoff_at_target: 577,
        risk_reward_ratio: 1.36,
        liquidity_warnings: [],
        iv_theta_notes: [],
        suitability_notes: ['scenario_analysis_only'],
        limitations: ['mocked_route_identity_gate'],
        no_advice_disclosure: 'Scenario analysis only; not personalized financial advice.',
      }],
      limitations: ['mocked_route_identity_gate'],
      metadata: { read_only: true, fixture_backed: true, no_external_calls: true, no_trading_recommendation: true },
    });
  });
  await page.route('**/api/v1/options/decision/evaluate', async (route) => {
    await fulfillJson(route, {
      symbol: 'TEM',
      strategy: 'bull_call_spread',
      data_quality: { data_quality_score: 62, data_quality_tier: 'synthetic_demo_only', source_type: 'uat_route_identity_fixture', as_of_age_minutes: 0, blocking_reasons: ['mocked_route_identity_gate'], warnings: [] },
      liquidity: { liquidity_score: 78, spread_pct: 4.6, liquidity_warnings: [] },
      iv_greeks: { iv_readiness: 55, iv_rank_status: 'unavailable', warnings: [], dte_bucket: '30_60' },
      expected_move: { expected_move_abs: 5.2, expected_move_pct: 9.9, expected_move_source: 'straddle_mid', expected_move_warnings: [] },
      optimizer: { preferred_strategy_key: 'bull_call_spread', optimizer_label: '数据不足，禁止判断', alternatives: [], no_trade_reason: 'data_quality_not_decision_grade' },
      ranked_alternatives: [],
      breakeven: { breakeven: 57.3, required_move_pct: 9.5, breakeven_pressure: 42 },
      risk_reward: { max_loss: 230, max_gain: 500, risk_reward_ratio: 2.17, score: 58 },
      trade_quality_score: 48,
      decision_label: '数据不足，禁止判断',
      primary_reasons: ['mocked_route_identity_gate'],
      risk_warnings: [],
      no_advice_disclosure: 'Scenario analysis only; not personalized financial advice.',
      freshness: { source: 'uat_route_identity_fixture', freshness: 'mock', as_of: '2026-06-07T09:45:00-04:00' },
      metadata: { read_only: true, fixture_backed: true, no_external_calls: true, no_trading_recommendation: true },
    });
  });

  await page.route('**/api/v1/market/data-readiness**', async (route) => {
    await fulfillJson(route, {
      readiness_status: 'ready',
      diagnostic_only: true,
      provider_runtime_called: false,
      network_calls_enabled: false,
      representative_symbols: ['ORCL'],
      checks: [],
    });
  });
  await page.route('**/api/v1/admin/providers/operations-matrix', async (route) => {
    await fulfillJson(route, {
      generated_at: '2026-06-05T00:00:00Z',
      diagnostic_only: true,
      rows: [],
      summary: { total_rows: 0, observation_only_rows: 0, inert_metadata_only_rows: 0, missing_provider_rows: 0, score_eligible_rows: 0, paid_data_likely_required_rows: 0 },
      metadata: { source: 'uat_route_identity_fixture', read_only: true, diagnostic_only: true, external_provider_calls: false, network_calls_enabled: false, cache_mutation: false, secret_values_included: false, raw_provider_payloads_included: false, readiness_status: 'ready', row_count: 0 },
    });
  });
  await page.route('**/api/v1/admin/market-providers/operations**', async (route) => {
    await fulfillJson(route, {
      generated_at: '2026-06-05T00:00:00Z',
      window: { key: '24h', since: '24h' },
      summary: { total_items: 0, live_count: 0, cache_count: 0, stale_count: 0, fallback_count: 0, partial_count: 0, unavailable_count: 0, error_count: 0, refreshing_count: 0, event_count: 0, failure_count: 0, fallback_event_count: 0, stale_event_count: 0, slow_event_count: 0 },
      items: [],
      event_rollups: [],
      cache_states: [],
      limitations: [],
      admin_log_drill_through: { label: '查看 Admin Logs', route: '/zh/admin/logs', query: { since: '24h' } },
      metadata: { source: 'uat_route_identity_fixture', read_only: true, external_provider_calls: false, cache_mutation: false },
    });
  });
  await page.route('**/api/v1/admin/**', async (route) => {
    await fulfillJson(route, {});
  });
}

async function expectProtectedRouteIdentity(page: Page, route: RouteIdentity) {
  await page.goto(route.path);
  await page.waitForLoadState('domcontentloaded');

  await expect(page).toHaveURL(route.expectedUrl);
  await expectAuthenticatedAdminSession(page);
  await expect(page.getByTestId(route.readyTestId), route.label).toBeVisible({ timeout: 15_000 });
  if (route.heading) {
    await expect(page.getByRole('heading', { name: route.heading }).first()).toBeVisible();
  }
  await expect(page.getByTestId('auth-guard-overlay')).toHaveCount(0);
  await expect(page.locator('body')).not.toContainText(/登录后即可进入|登录解锁|登录继续|Sign in to unlock|Sign in to continue/i);
  await baseExpect.poll(async () => page.locator('#root').evaluate((root) => root.textContent?.trim().length ?? 0)).toBeGreaterThan(0);
  if (route.extra) {
    await route.extra(page);
  }
}

test.describe('UAT route identity auth-session gate', () => {
  test('proves admin session before trusting protected route identity', async ({ page }) => {
    await installAdminLoginSession(page);
    await installRouteIdentityMocks(page);

    await loginAsAdmin(page);
    await expectAuthenticatedAdminSession(page);

    for (const route of protectedRoutes) {
      await expectProtectedRouteIdentity(page, route);
    }
  });
});
