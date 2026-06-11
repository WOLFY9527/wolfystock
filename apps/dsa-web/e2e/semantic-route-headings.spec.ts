import type { Page, Route } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';

const TIMESTAMP = '2026-05-10T09:45:00Z';

const ROUTES = [
  { path: '/zh/scanner', heading: '扫描器' },
  { path: '/zh/market-overview', heading: '市场总览' },
  { path: '/zh/backtest', heading: '回测' },
  { path: '/zh/options-lab', heading: '期权实验室' },
  { path: '/zh/settings', heading: '账户中心' },
] as const;

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function signIn(page: Page, redirectPath: string) {
  await page.goto(`/login?redirect=${encodeURIComponent(redirectPath)}`);
  await page.locator('#username').fill('wolfy-user');
  await page.locator('#password').fill('mock-password');
  await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/v1/auth/login') && response.status() === 200),
    page.getByRole('button', { name: /sign in|登录继续|授权进入工作台|完成设置并登录/i }).click(),
  ]);
  await page.waitForURL(/\/$/);
}

async function installRouteSpecificMocks(page: Page) {
  await page.route('**/api/v1/auth/me', async (route) => {
    await fulfillJson(route, {
      id: 'user-1',
      username: 'wolfy-user',
      displayName: 'Wolfy User',
      role: 'user',
      isAdmin: false,
      isAuthenticated: true,
      transitional: false,
      authEnabled: true,
    });
  });

  await page.route('**/api/v1/auth/preferences/notifications', async (route) => {
    await fulfillJson(route, {
      channel: 'email',
      enabled: false,
      email: null,
      emailEnabled: false,
      discordEnabled: false,
      discordWebhook: null,
      deliveryAvailable: true,
      emailDeliveryAvailable: true,
      discordDeliveryAvailable: true,
      updatedAt: null,
    });
  });

  await page.route('**/api/v1/options/underlyings/*/summary', async (route) => {
    await fulfillJson(route, {
      symbol: 'TEM',
      market: 'us',
      underlying: {
        price: 52.34,
        change_pct: 1.2,
        source: 'playwright_fixture',
        as_of: TIMESTAMP,
        freshness: 'mock',
      },
      options_availability: {
        supported: true,
        provider: 'playwright_fixture',
        limitations: ['mocked_product_route_harness'],
      },
      metadata: {
        read_only: true,
        no_external_calls_in_tests: true,
        limitations: ['mocked_playwright_product_auth'],
        source_label: 'Playwright Fixture',
        updated_at: TIMESTAMP,
      },
    });
  });

  await page.route('**/api/v1/options/underlyings/*/expirations', async (route) => {
    await fulfillJson(route, {
      symbol: 'TEM',
      expirations: [
        {
          date: '2026-06-19',
          dte: 40,
          type: 'monthly',
          chain_available: true,
          as_of: TIMESTAMP,
          source: 'playwright_fixture',
          warnings: ['mocked_chain'],
        },
      ],
      metadata: {
        read_only: true,
        no_external_calls_in_tests: true,
        limitations: ['mocked_playwright_product_auth'],
        source_label: 'Playwright Fixture',
        updated_at: TIMESTAMP,
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
        source: 'playwright_fixture',
        as_of: TIMESTAMP,
        freshness: 'mock',
      },
      calls: [
        {
          contract_symbol: 'TEM260619C00055000',
          side: 'call',
          strike: 55,
          bid: 4.1,
          ask: 4.3,
          mid: 4.2,
          volume: 500,
          open_interest: 3200,
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
          bid: 2.3,
          ask: 2.5,
          mid: 2.4,
          volume: 440,
          open_interest: 2600,
          implied_volatility: 0.54,
          delta: -0.36,
          gamma: 0.04,
          theta: -0.04,
          vega: 0.1,
          spread_pct: 4.8,
          moneyness: 'otm',
          liquidity_score: 76,
          warnings: [],
        },
      ],
      filters_applied: {
        min_open_interest: 100,
        max_spread_pct: 25,
      },
      chain_as_of: TIMESTAMP,
      source: 'playwright_fixture',
      limitations: ['mocked_chain'],
      metadata: {
        read_only: true,
        no_external_calls_in_tests: true,
        limitations: ['mocked_playwright_product_auth'],
        source_label: 'Playwright Fixture',
        updated_at: TIMESTAMP,
      },
    });
  });

  await page.route('**/api/v1/options/strategies/compare', async (route) => {
    await fulfillJson(route, {
      symbol: 'TEM',
      underlying: {
        price: 52.34,
        change_pct: 1.2,
        source: 'playwright_fixture',
        as_of: TIMESTAMP,
        freshness: 'mock',
      },
      assumptions: {
        direction: 'bullish',
        target_price: 65,
        target_date: '2026-08-21',
      },
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
              mid: 4.2,
              quantity: 1,
            },
          ],
          net_debit: 420,
          max_loss: 420,
          max_gain: 600,
          breakeven: 59.2,
          required_move_pct: 13.1,
          payoff_at_target: 580,
          risk_reward_ratio: 1.38,
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
        no_llm_calls: true,
        no_order_placement: true,
        no_broker_connection: true,
        no_portfolio_mutation: true,
        no_trading_recommendation: true,
        strategy_engine: 'playwright_fixture',
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
        source_type: 'playwright_fixture',
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
        alternatives: [
          {
            strategy_key: 'bull_call_spread',
            data_quality_tier: 'synthetic_demo_only',
            liquidity_score: 78,
            breakeven_pressure: 42,
            max_loss: 230,
            max_gain: 500,
            risk_reward_ratio: 2.17,
            expected_move_alignment: 61,
            iv_readiness: 55,
            trade_quality_score: 48,
            decision_label: '数据不足，禁止判断',
            primary_reasons: ['mocked_product_route_harness'],
            risk_warnings: ['provider_validation_required'],
          },
        ],
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
        source: 'playwright_fixture',
        freshness: 'mock',
        as_of: TIMESTAMP,
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
        strategy_engine: 'playwright_fixture',
      },
    });
  });
}

async function assertCompactSemanticHeading(page: Page, path: string, expectedHeading: string) {
  await page.goto(path);
  await page.waitForLoadState('domcontentloaded');

  const heading = page.getByRole('heading', { level: 1, name: expectedHeading });
  await expect(heading).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('h1')).toHaveCount(1);

  const fontSize = await heading.evaluate((element) => Number.parseFloat(window.getComputedStyle(element).fontSize));
  expect(fontSize).toBeLessThanOrEqual(32);

  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function runViewportSweep(page: Page, viewport: { width: number; height: number }) {
  await page.setViewportSize(viewport);
  await installRouteSpecificMocks(page);
  await signIn(page, '/scanner');

  for (const route of ROUTES) {
    await assertCompactSemanticHeading(page, route.path, route.heading);
  }
}

test.describe('semantic route headings', () => {
  test('desktop user routes keep compact semantic h1 headings', async ({ page }) => {
    await runViewportSweep(page, { width: 1440, height: 1000 });
  });

  test('mobile user routes keep compact semantic h1 headings', async ({ page }) => {
    await runViewportSweep(page, { width: 390, height: 844 });
  });
});
