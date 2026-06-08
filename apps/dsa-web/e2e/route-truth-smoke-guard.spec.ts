import { expect as baseExpect, type Page, type Route } from '@playwright/test';
import { expect as appExpect, test as appTest } from './fixtures/appSmoke';
import {
  expect as adminExpect,
  expectNoHorizontalOverflow as expectNoAdminHorizontalOverflow,
  expectNoRawSecretLikeText,
  openAdminRouteWithHarness,
  test as adminTest,
} from './fixtures/adminAuth';
import { installPortfolioSmokeHarness } from './fixtures/portfolioSmoke';
import { createMockAdminUser, createMockAuthStatus } from '../src/test-utils/adminAuthHarness';

const desktopViewport = { width: 1440, height: 1000 };
const mobileViewport = { width: 390, height: 844 };

const guestPublicRoutes = [
  {
    path: '/zh/market/liquidity-monitor',
    expectedUrl: /\/zh\/market\/liquidity-monitor$/,
    ready: (page: Page) => page.getByTestId('liquidity-monitor-guidance-panel'),
    heading: /流动性监测/,
  },
  {
    path: '/zh/market/rotation-radar',
    expectedUrl: /\/zh\/market\/rotation-radar$/,
    ready: (page: Page) => page.getByTestId('market-rotation-radar-page'),
    heading: /主题轮动雷达/,
  },
] as const;

const guestOverlayRoutes = [
  {
    path: '/zh/market-overview',
    expectedUrl: /\/zh\/market-overview$/,
    routeLabel: /市场总览/,
    hiddenTestId: 'market-overview-shell',
  },
  {
    path: '/zh/scanner',
    expectedUrl: /\/zh\/scanner$/,
    routeLabel: /扫描/,
    hiddenTestId: 'user-scanner-workspace',
  },
  {
    path: '/zh/watchlist',
    expectedUrl: /\/zh\/watchlist$/,
    routeLabel: /观察列表|watchlist/i,
    hiddenTestId: 'watchlist-page',
  },
  {
    path: '/zh/portfolio',
    expectedUrl: /\/zh\/portfolio$/,
    routeLabel: /持仓|Portfolio/i,
    hiddenTestId: 'portfolio-bento-page',
  },
  {
    path: '/zh/options-lab',
    expectedUrl: /\/zh\/options-lab$/,
    routeLabel: /期权实验室|Options Lab/i,
    hiddenTestId: 'options-lab-decision-engine',
  },
] as const;

const guestPreviewRoutes = [
  { path: '/zh/admin/market-providers', forbidden: /Provider 熔断诊断|数据源运维|市场数据源运维/i },
  { path: '/zh/settings/system', forbidden: /系统设置|通知中心|数据源运维/i },
  { path: '/zh/admin', forbidden: /系统设置|数据源运维|Provider 熔断诊断/i },
  { path: '/zh/settings', forbidden: /账户中心|通知中心|邮件与 Discord/i },
] as const;

const signedInProductRoutes = [
  {
    path: '/zh/market-overview',
    expectedUrl: /\/zh\/market-overview$/,
    ready: (page: Page) => page.getByTestId('market-overview-shell'),
    heading: /市场总览/,
    forbiddenUrl: /\/zh\/market\/liquidity-monitor$/,
  },
  {
    path: '/zh/market/liquidity-monitor',
    expectedUrl: /\/zh\/market\/liquidity-monitor$/,
    ready: (page: Page) => page.getByTestId('liquidity-monitor-guidance-panel'),
    heading: /流动性监测/,
  },
  {
    path: '/zh/market/rotation-radar',
    expectedUrl: /\/zh\/market\/rotation-radar$/,
    ready: (page: Page) => page.getByTestId('market-rotation-radar-page'),
    heading: /主题轮动雷达/,
  },
  {
    path: '/zh/scanner',
    expectedUrl: /\/zh\/scanner$/,
    ready: (page: Page) => page.getByTestId('user-scanner-workspace'),
    heading: /扫描器/,
  },
  {
    path: '/zh/watchlist',
    expectedUrl: /\/zh\/watchlist$/,
    ready: (page: Page) => page.getByTestId('watchlist-page'),
    heading: /观察列表|watchlist/i,
    forbiddenText: /系统设置|确认重置系统设置/i,
  },
  {
    path: '/zh/options-lab',
    expectedUrl: /\/zh\/options-lab$/,
    ready: (page: Page) => page.getByTestId('options-lab-decision-engine'),
    heading: /期权实验室/,
  },
  {
    path: '/zh/settings',
    expectedUrl: /\/zh\/settings$/,
    ready: (page: Page) => page.getByTestId('personal-settings-workspace'),
    heading: /账户中心/,
  },
] as const;

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installSignedInSession(page: Page) {
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

  await page.route('**/api/v1/auth/preferences/notifications**', async (route) => {
    await fulfillJson(route, {
      channel: 'multi',
      enabled: false,
      email: null,
      emailEnabled: false,
      discordEnabled: false,
      discordWebhook: null,
      deliveryAvailable: false,
      emailDeliveryAvailable: false,
      discordDeliveryAvailable: false,
      updatedAt: '2026-06-07T00:00:00+08:00',
    });
  });
}

async function installAdminSession(page: Page) {
  const currentUser = createMockAdminUser({ displayName: 'Playwright Admin' });

  await page.route('**/api/v1/auth/status**', async (route) => {
    await fulfillJson(route, createMockAuthStatus(currentUser));
  });

  await page.route('**/api/v1/auth/me**', async (route) => {
    await fulfillJson(route, currentUser);
  });

  await page.route('**/api/v1/auth/preferences/notifications**', async (route) => {
    await fulfillJson(route, {
      channel: 'multi',
      enabled: false,
      email: null,
      emailEnabled: false,
      discordEnabled: false,
      discordWebhook: null,
      deliveryAvailable: false,
      emailDeliveryAvailable: false,
      discordDeliveryAvailable: false,
      updatedAt: '2026-06-07T00:00:00+08:00',
    });
  });
}

async function installGuestSession(page: Page) {
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

async function installLiquidityMonitorMock(page: Page) {
  await page.route('**/api/v1/market/liquidity-monitor**', async (route) => {
    await fulfillJson(route, {
      endpoint: '/api/v1/market/liquidity-monitor',
      generated_at: '2026-06-07T10:30:00+08:00',
      score: {
        value: 64,
        regime: 'supportive',
        confidence: 0.76,
        included_indicator_count: 2,
        possible_indicator_weight: 2,
        included_indicator_weight: 2,
      },
      freshness: {
        status: 'live',
        weakest_indicator_freshness: 'live',
        latest_as_of: '2026-06-07T10:30:00+08:00',
      },
      indicators: [
        {
          key: 'policy_liquidity',
          label: 'Policy liquidity',
          status: 'live',
          freshness: 'live',
          included_in_score: true,
          score_contribution: 0.38,
          score_weight: 0.5,
          summary: '政策流动性保持稳定。',
          updated_at: '2026-06-07T10:30:00+08:00',
        },
        {
          key: 'market_breadth',
          label: 'Market breadth',
          status: 'live',
          freshness: 'live',
          included_in_score: true,
          score_contribution: 0.26,
          score_weight: 0.5,
          summary: '市场宽度对流动性读数形成支撑。',
          updated_at: '2026-06-07T10:30:00+08:00',
        },
      ],
      liquidity_impulse_synthesis: {
        liquidity_impulse: 'expanding',
        impulse_label: 'Liquidity is improving',
        subtype: 'broad_support',
        confidence: 0.76,
        confidence_label: 'medium',
        pillar_scores: { policy_liquidity: 66, market_breadth: 62 },
        direction_score: 64,
        dominant_drivers: [],
        counter_evidence: [],
        data_gaps: [],
        narrative_bullets: ['流动性读数可用，当前适合观察。'],
        evidence_quality: {},
        not_investment_advice: true,
      },
      advisory_disclosure: '仅用于研究观察，不构成投资建议。',
      source_metadata: {
        external_provider_calls: false,
        provider_runtime_changed: false,
        market_cache_mutation: false,
      },
    });
  });
}

async function installOptionsLabMocks(page: Page) {
  await page.route('**/api/v1/options/underlyings/*/summary', async (route) => {
    await fulfillJson(route, {
      symbol: 'TEM',
      market: 'us',
      underlying: {
        price: 52.34,
        change_pct: 1.2,
        source: 'route_truth_smoke_fixture',
        as_of: '2026-06-07T09:45:00-04:00',
        freshness: 'mock',
      },
      options_availability: {
        supported: true,
        provider: 'route_truth_smoke_fixture',
        limitations: ['mocked_product_route_harness'],
      },
      metadata: {
        read_only: true,
        no_external_calls_in_tests: true,
        source_label: 'Playwright Fixture',
        updated_at: '2026-06-07T09:45:00-04:00',
      },
    });
  });

  await page.route('**/api/v1/options/underlyings/*/expirations', async (route) => {
    await fulfillJson(route, {
      symbol: 'TEM',
      expirations: [
        {
          date: '2026-06-19',
          dte: 44,
          type: 'monthly',
          chain_available: true,
          as_of: '2026-06-07T09:45:00-04:00',
          source: 'route_truth_smoke_fixture',
          warnings: ['mocked_chain'],
        },
      ],
      metadata: {
        read_only: true,
        no_external_calls_in_tests: true,
        source_label: 'Playwright Fixture',
        updated_at: '2026-06-07T09:45:00-04:00',
      },
    });
  });

  await page.route('**/api/v1/options/underlyings/*/chain**', async (route) => {
    await fulfillJson(route, {
      symbol: 'TEM',
      expiration: '2026-06-19',
      underlying: {
        price: 52.34,
        change_pct: 1.2,
        source: 'route_truth_smoke_fixture',
        as_of: '2026-06-07T09:45:00-04:00',
        freshness: 'mock',
      },
      calls: [
        {
          contract_symbol: 'TEM260619C00055000',
          side: 'call',
          strike: 55,
          bid: 4.13,
          ask: 4.33,
          mid: 4.23,
          volume: 500,
          open_interest: 3000,
          implied_volatility: 0.52,
          delta: 0.42,
          gamma: 0.04,
          theta: -0.05,
          vega: 0.11,
          spread_pct: 4.6,
          moneyness: 'atm',
          liquidity_score: 82,
          warnings: [],
        },
      ],
      puts: [
        {
          contract_symbol: 'TEM260619P00050000',
          side: 'put',
          strike: 50,
          bid: 2.32,
          ask: 2.52,
          mid: 2.42,
          volume: 500,
          open_interest: 3000,
          implied_volatility: 0.52,
          delta: -0.36,
          gamma: 0.04,
          theta: -0.05,
          vega: 0.11,
          spread_pct: 4.6,
          moneyness: 'otm',
          liquidity_score: 82,
          warnings: [],
        },
      ],
      filters_applied: { min_open_interest: 100, max_spread_pct: 25 },
      chain_as_of: '2026-06-07T09:45:00-04:00',
      source: 'route_truth_smoke_fixture',
      limitations: ['mocked_chain'],
      metadata: {
        read_only: true,
        no_external_calls_in_tests: true,
        source_label: 'Playwright Fixture',
        updated_at: '2026-06-07T09:45:00-04:00',
      },
    });
  });

  await page.route('**/api/v1/options/strategies/compare', async (route) => {
    await fulfillJson(route, {
      symbol: 'TEM',
      underlying: {
        price: 52.34,
        change_pct: 1.2,
        source: 'route_truth_smoke_fixture',
        as_of: '2026-06-07T09:45:00-04:00',
        freshness: 'mock',
      },
      assumptions: { direction: 'bullish', target_price: 65, target_date: '2026-08-21' },
      strategies: [
        {
          strategy_type: 'bull_call_spread',
          legs: [
            {
              action: 'buy',
              side: 'call',
              contract_symbol: 'TEM260619C00055000',
              expiration: '2026-06-19',
              strike: 55,
              mid: 4.23,
              quantity: 1,
            },
          ],
          net_debit: 423,
          max_loss: 423,
          max_gain: 500,
          breakeven: 59.23,
          required_move_pct: 13.2,
          payoff_at_target: 577,
          risk_reward_ratio: 1.36,
          liquidity_warnings: [],
          iv_theta_notes: ['fixture_iv_only'],
          suitability_notes: ['scenario_analysis_only'],
          limitations: ['mocked_product_route_harness'],
          no_advice_disclosure: 'Scenario analysis only; not personalized financial advice.',
        },
      ],
      limitations: ['mocked_product_route_harness'],
      metadata: {
        read_only: true,
        fixture_backed: true,
        synthetic_data: true,
        no_external_calls: true,
        no_order_placement: true,
        no_broker_connection: true,
        no_portfolio_mutation: true,
        no_trading_recommendation: true,
      },
    });
  });

  await page.route('**/api/v1/options/decision/evaluate', async (route) => {
    await fulfillJson(route, {
      symbol: 'TEM',
      strategy: 'bull_call_spread',
      data_quality: {
        data_quality_score: 62,
        data_quality_tier: 'synthetic_demo_only',
        source_type: 'route_truth_smoke_fixture',
        as_of_age_minutes: 0,
        blocking_reasons: ['mocked_product_route_harness'],
        warnings: ['provider_validation_required'],
      },
      liquidity: {
        liquidity_score: 78,
        spread_pct: 4.6,
        liquidity_warnings: [],
      },
      iv_greeks: {
        iv_readiness: 55,
        iv_rank_status: 'unavailable',
        warnings: ['fixture_iv_only'],
        dte_bucket: '30_60',
      },
      expected_move: {
        expected_move_abs: 5.2,
        expected_move_pct: 9.9,
        expected_move_source: 'straddle_mid',
        expected_move_warnings: [],
      },
      optimizer: {
        preferred_strategy_key: 'bull_call_spread',
        optimizer_label: '数据不足，禁止判断',
        alternatives: [],
        no_trade_reason: 'data_quality_not_decision_grade',
      },
      ranked_alternatives: [],
      breakeven: {
        breakeven: 57.3,
        required_move_pct: 9.5,
        breakeven_pressure: 42,
      },
      risk_reward: {
        max_loss: 230,
        max_gain: 500,
        risk_reward_ratio: 2.17,
        score: 58,
      },
      trade_quality_score: 48,
      decision_label: '数据不足，禁止判断',
      primary_reasons: ['mocked_product_route_harness'],
      risk_warnings: ['provider_validation_required', 'synthetic_demo_only'],
      no_advice_disclosure: 'Scenario analysis only; not personalized financial advice.',
      freshness: {
        source: 'route_truth_smoke_fixture',
        freshness: 'mock',
        as_of: '2026-06-07T09:45:00-04:00',
      },
      metadata: {
        read_only: true,
        fixture_backed: true,
        synthetic_data: true,
        no_external_calls: true,
        no_order_placement: true,
        no_broker_connection: true,
        no_portfolio_mutation: true,
        no_trading_recommendation: true,
      },
    });
  });
}

async function readBodyText(page: Page) {
  return page.locator('body').innerText();
}

async function expectRootNonEmpty(page: Page) {
  await baseExpect.poll(async () => page.locator('#root').evaluate((root) => root.textContent?.trim().length ?? 0)).toBeGreaterThan(0);
}

async function expectNoHorizontalOverflow(page: Page) {
  await baseExpect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function expectGuestPreviewSurface(page: Page, forbidden: RegExp) {
  await appExpect(page).toHaveURL(/\/zh\/guest$/);
  await appExpect(page.getByTestId('guest-home-clean-search')).toBeVisible({ timeout: 15_000 });
  await appExpect(page.getByTestId('guest-home-command-surface')).toBeVisible();
  await appExpect(page.getByTestId('guest-home-market-preview-strip')).toContainText(/当前市场观察|Current market observation/);
  baseExpect(await readBodyText(page)).not.toMatch(forbidden);
  await expectRootNonEmpty(page);
  await expectNoHorizontalOverflow(page);
}

async function expectGuestOverlay(
  page: Page,
  expectedUrl: RegExp,
  routeLabel: RegExp,
  options: { hidden?: RegExp; hiddenTestId?: string } = {},
) {
  await appExpect(page).toHaveURL(expectedUrl);
  await appExpect(page.getByTestId('auth-guard-overlay')).toBeVisible({ timeout: 15_000 });
  await appExpect(page.getByTestId('auth-guard-overlay')).toContainText(routeLabel);
  if (options.hidden) {
    baseExpect(await readBodyText(page)).not.toMatch(options.hidden);
  }
  if (options.hiddenTestId) {
    await appExpect(page.getByTestId(options.hiddenTestId)).toHaveCount(0);
  }
  await expectRootNonEmpty(page);
  await expectNoHorizontalOverflow(page);
}

appTest.describe('route truth smoke guard - guest', () => {
  appTest('keeps public route identity, same-route overlays, and guest-preview redirects aligned', async ({ page }) => {
    await page.setViewportSize(desktopViewport);
    await installGuestSession(page);
    await installLiquidityMonitorMock(page);
    await installOptionsLabMocks(page);

    for (const route of guestPublicRoutes) {
      await page.goto(route.path);
      await page.waitForLoadState('domcontentloaded');
      await appExpect(page).toHaveURL(route.expectedUrl);
      await appExpect(route.ready(page)).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByRole('heading', { name: route.heading })).toBeVisible();
      await appExpect(page.getByTestId('auth-guard-overlay')).toHaveCount(0);
    }

    for (const route of guestOverlayRoutes) {
      await page.goto(route.path);
      await page.waitForLoadState('domcontentloaded');
      await expectGuestOverlay(page, route.expectedUrl, route.routeLabel, {
        hiddenTestId: 'hiddenTestId' in route ? route.hiddenTestId : undefined,
      });
    }

    for (const route of guestPreviewRoutes) {
      await page.goto(route.path);
      await page.waitForLoadState('domcontentloaded');
      await expectGuestPreviewSurface(page, route.forbidden);
    }
  });

  appTest('retains representative alias redirects without replacing canonical coverage', async ({ page }) => {
    await page.setViewportSize(desktopViewport);
    await installGuestSession(page);
    await installLiquidityMonitorMock(page);
    await installOptionsLabMocks(page);

    await page.goto('/zh/liquidity');
    await page.waitForLoadState('domcontentloaded');
    await appExpect(page).toHaveURL(/\/zh\/market\/liquidity-monitor$/);
    await appExpect(page.getByRole('heading', { name: /流动性监测/ })).toBeVisible();

    await page.goto('/zh/rotation');
    await page.waitForLoadState('domcontentloaded');
    await appExpect(page).toHaveURL(/\/zh\/market\/rotation-radar$/);
    await appExpect(page.getByRole('heading', { name: /主题轮动雷达/ })).toBeVisible();

    await page.goto('/zh/options');
    await page.waitForLoadState('domcontentloaded');
    await appExpect(page).toHaveURL(/\/zh\/options-lab$/);
    await appExpect(page.getByRole('heading', { name: /期权实验室/ })).toBeVisible();
  });

  appTest('preserves the same route classes on mobile where viewport-specific misreads are likely', async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    await installGuestSession(page);
    await installLiquidityMonitorMock(page);

    await page.goto('/zh/liquidity');
    await page.waitForLoadState('domcontentloaded');
    await appExpect(page).toHaveURL(/\/zh\/market\/liquidity-monitor$/);
    await appExpect(page.getByRole('heading', { name: /流动性监测/ })).toBeVisible();

    await page.goto('/zh/watchlist');
    await page.waitForLoadState('domcontentloaded');
    await expectGuestOverlay(page, /\/zh\/watchlist$/, /观察列表|watchlist/i, {
      hiddenTestId: 'watchlist-page',
    });

    await page.goto('/zh/admin');
    await page.waitForLoadState('domcontentloaded');
    await expectGuestPreviewSurface(page, /系统设置|数据源运维|Provider 熔断诊断/i);
  });
});

appTest.describe('route truth smoke guard - signed-in product', () => {
  appTest('renders intended signed-in product headings and keeps route identity stable', async ({ page }) => {
    await page.setViewportSize(desktopViewport);
    await installSignedInSession(page);
    await installLiquidityMonitorMock(page);
    await installOptionsLabMocks(page);

    for (const route of signedInProductRoutes) {
      await page.goto(route.path);
      await page.waitForLoadState('domcontentloaded');
      await appExpect(page).toHaveURL(route.expectedUrl);
      if ('forbiddenUrl' in route) {
        baseExpect(page.url()).not.toMatch(route.forbiddenUrl);
      }
      await appExpect(route.ready(page)).toBeVisible({ timeout: 15_000 });
      if ('heading' in route) {
        await appExpect(page.getByRole('heading', { name: route.heading })).toBeVisible();
      }
      if ('text' in route) {
        await appExpect(page.locator('body')).toContainText(route.text);
      }
      if ('forbiddenText' in route) {
        baseExpect(await readBodyText(page)).not.toMatch(route.forbiddenText);
      }
      await expectRootNonEmpty(page);
      await expectNoHorizontalOverflow(page);
    }
  });

  appTest('keeps portfolio on its own route and out of admin provider content', async ({ page }) => {
    await page.setViewportSize(desktopViewport);
    await installPortfolioSmokeHarness(page);

    await page.goto('/zh/portfolio');
    await page.waitForLoadState('domcontentloaded');

    await appExpect(page).toHaveURL(/\/zh\/portfolio$/);
    await appExpect(page.getByTestId('portfolio-bento-page')).toBeVisible({ timeout: 15_000 });
    await appExpect(page.getByRole('heading', { name: /组合总览/ })).toBeVisible();
    await appExpect(page.getByTestId('market-provider-operations-page')).toHaveCount(0);
    baseExpect(await readBodyText(page)).not.toMatch(/Provider 熔断诊断|数据源运维/i);
    await expectRootNonEmpty(page);
    await expectNoHorizontalOverflow(page);
  });
});

appTest.describe('route truth smoke guard - signed-in admin provider alias', () => {
  appTest('keeps canonical and alias admin provider routes aligned for admins', async ({ page }) => {
    await page.setViewportSize(desktopViewport);
    await installAdminSession(page);
    await page.route('**/api/v1/admin/providers/operations-matrix', async (route) => {
      await fulfillJson(route, {
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
      });
    });
    await page.route('**/api/v1/market/data-readiness**', async (route) => {
      await fulfillJson(route, {
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
      });
    });
    await page.route('**/api/v1/admin/market-providers/operations**', async (route) => {
      await fulfillJson(route, {
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
      });
    });
    await page.route('**/api/v1/admin/**', async (route) => {
      const pathname = new URL(route.request().url()).pathname;
      if (
        pathname === '/api/v1/admin/providers/operations-matrix'
        || pathname === '/api/v1/admin/market-providers/operations'
        || pathname === '/api/v1/admin/logs/storage/summary'
        || pathname === '/api/v1/admin/logs/sessions'
        || pathname === '/api/v1/admin/logs'
      ) {
        await route.fallback();
        return;
      }
      await fulfillJson(route, {});
    });
    await page.goto('/zh/admin/market-providers');
    await page.waitForLoadState('domcontentloaded');
    await appExpect(page).toHaveURL(/\/zh\/admin\/market-providers$/);
    await appExpect(page.getByTestId('market-provider-operations-page')).toBeVisible({ timeout: 15_000 });
    await appExpect(page.getByRole('heading', { name: /数据源维护路线图/ })).toBeVisible();
    await expectNoHorizontalOverflow(page);
    baseExpect(await readBodyText(page)).not.toMatch(/raw payload|debug schema|session[_\s-]?id\s*[=:]|secret\s*[=:]/i);

    await page.goto('/zh/admin/providers');
    await page.waitForLoadState('domcontentloaded');
    await appExpect(page).toHaveURL(/\/zh\/admin\/market-providers$/);
    await appExpect(page.getByTestId('market-provider-operations-page')).toBeVisible({ timeout: 15_000 });
    await appExpect(page.getByRole('heading', { name: /数据源维护路线图/ })).toBeVisible();
    await expectNoHorizontalOverflow(page);
    baseExpect(await readBodyText(page)).not.toMatch(/raw payload|debug schema|session[_\s-]?id\s*[=:]|secret\s*[=:]/i);
  });

  appTest('keeps representative admin provider alias truth on mobile', async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    await installAdminSession(page);
    await page.route('**/api/v1/admin/providers/operations-matrix', async (route) => {
      await fulfillJson(route, {
        generated_at: '2026-06-05T00:00:00Z',
        diagnostic_only: true,
        rows: [],
        summary: {
          total_rows: 0,
          observation_only_rows: 0,
          inert_metadata_only_rows: 0,
          missing_provider_rows: 0,
          score_eligible_rows: 0,
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
          row_count: 0,
        },
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
    await page.route('**/api/v1/admin/market-providers/operations**', async (route) => {
      await fulfillJson(route, {
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
        items: [],
        event_rollups: [],
        cache_states: [],
        limitations: [],
        admin_log_drill_through: { label: '查看 Admin Logs', route: '/zh/admin/logs', query: { since: '24h' } },
        metadata: { source: 'mocked_playwright', read_only: true, external_provider_calls: false, cache_mutation: false },
      });
    });
    await page.route('**/api/v1/admin/**', async (route) => {
      const pathname = new URL(route.request().url()).pathname;
      if (
        pathname === '/api/v1/admin/providers/operations-matrix'
        || pathname === '/api/v1/admin/market-providers/operations'
      ) {
        await route.fallback();
        return;
      }
      await fulfillJson(route, {});
    });
    await page.goto('/zh/admin/providers');
    await page.waitForLoadState('domcontentloaded');
    await appExpect(page).toHaveURL(/\/zh\/admin\/market-providers$/);
    await appExpect(page.getByTestId('market-provider-operations-page')).toBeVisible({ timeout: 15_000 });
    await appExpect(page.getByTestId('market-provider-operations-page')).toContainText('数据源维护路线图');
    await expectNoHorizontalOverflow(page);
  });
});

adminTest.describe('route truth smoke guard - signed-in admin', () => {
  adminTest('keeps /zh/settings/system on the system settings route for admins', async ({ page }) => {
    await page.setViewportSize(desktopViewport);
    await openAdminRouteWithHarness(page, '/zh/settings/system', { displayName: 'Bootstrap Admin' });
    await adminExpect(page).toHaveURL(/\/zh\/settings\/system$/);
    await adminExpect(page.getByTestId('system-settings-page')).toBeVisible({ timeout: 15_000 });
    await adminExpect(page.getByRole('heading', { name: /^系统设置$/ })).toBeVisible();
    await expectNoAdminHorizontalOverflow(page);
    await expectNoRawSecretLikeText(page);
  });

  adminTest('keeps /zh/admin redirected to system settings for admins', async ({ page }) => {
    await page.setViewportSize(desktopViewport);
    await openAdminRouteWithHarness(page, '/zh/admin', { displayName: 'Bootstrap Admin' });
    await adminExpect(page).toHaveURL(/\/zh\/settings\/system$/);
    await adminExpect(page.getByTestId('system-settings-page')).toBeVisible({ timeout: 15_000 });
    await adminExpect(page.getByRole('heading', { name: /^系统设置$/ })).toBeVisible();
    await expectNoAdminHorizontalOverflow(page);
    await expectNoRawSecretLikeText(page);
  });
});
