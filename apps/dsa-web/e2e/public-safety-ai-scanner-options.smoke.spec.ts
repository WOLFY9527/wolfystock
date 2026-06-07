import type { Page, Route } from '@playwright/test';
import { expect, test as appTest } from './fixtures/appSmoke';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
] as const;

const rawInternalArtifactPattern = /raw\s+(payload|response|schema|prompt|trace)|debug\s+(payload|response|schema|prompt|panel)|provider\s+payload|stack\s+(trace|details)|traceback|internal\s+reasoning|api[_\s-]?key\s*[=:]|password\s*[=:]|session[_\s-]?id\s*[=:]|secret\s*[=:]|bearer\s+[a-z0-9._-]+|sk-[a-z0-9_-]{12,}|ghp_[a-z0-9_]{12,}|xox[baprs]-[a-z0-9-]{12,}/i;
const timestamp = '2026-05-06T09:45:00-04:00';
const expiration = '2026-06-19';

type ApiRequestLog = {
  calls: string[];
  count: (method: string, path: string) => number;
};

type OptionsHarness = {
  requests: ApiRequestLog;
};

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

function createRequestLog(calls: string[]): ApiRequestLog {
  return {
    calls,
    count: (method: string, path: string) => calls.filter((entry) => entry === `${method} ${path}`).length,
  };
}

function metadata() {
  return {
    read_only: true,
    no_external_calls_in_tests: true,
    limitations: ['mocked_playwright_product_auth'],
    source_label: 'Playwright Fixture',
    updated_at: timestamp,
  };
}

function underlying() {
  return {
    price: 52.34,
    change_pct: 1.2,
    source: 'playwright_fixture',
    as_of: timestamp,
    freshness: 'mock',
  };
}

function optionsSummary(symbol: string) {
  return {
    symbol,
    market: 'us',
    underlying: underlying(),
    options_availability: {
      supported: true,
      provider: 'playwright_fixture',
      limitations: ['mocked_product_route_harness'],
    },
    metadata: metadata(),
  };
}

function optionsExpirations(symbol: string) {
  return {
    symbol,
    expirations: [
      {
        date: expiration,
        dte: 44,
        type: 'monthly',
        chain_available: true,
        as_of: timestamp,
        source: 'playwright_fixture',
        warnings: ['mocked_chain'],
      },
    ],
    metadata: metadata(),
  };
}

function contract(symbol: string, side: 'call' | 'put', strike: number, mid: number) {
  return {
    contract_symbol: `${symbol}260619${side === 'call' ? 'C' : 'P'}${String(strike * 1000).padStart(8, '0')}`,
    side,
    strike,
    bid: mid - 0.1,
    ask: mid + 0.1,
    mid,
    volume: 500,
    open_interest: 3000,
    implied_volatility: 0.52,
    delta: side === 'call' ? 0.42 : -0.36,
    gamma: 0.04,
    theta: -0.05,
    vega: 0.11,
    spread_pct: 4.6,
    moneyness: strike === 55 ? 'atm' : 'otm',
    liquidity_score: 82,
    warnings: [],
  };
}

function optionsChain(symbol: string) {
  return {
    symbol,
    expiration,
    underlying: underlying(),
    calls: [contract(symbol, 'call', 55, 4.23), contract(symbol, 'call', 60, 2.28)],
    puts: [contract(symbol, 'put', 50, 2.42), contract(symbol, 'put', 45, 1.16)],
    filters_applied: { min_open_interest: 100, max_spread_pct: 25 },
    chain_as_of: timestamp,
    source: 'playwright_fixture',
    limitations: ['mocked_chain'],
    metadata: metadata(),
  };
}

function strategy(strategyType: string) {
  return {
    strategy_type: strategyType,
    legs: [
      {
        action: 'buy',
        side: strategyType.includes('put') ? 'put' : 'call',
        contract_symbol: `TEM260619${strategyType.includes('put') ? 'P' : 'C'}00055000`,
        expiration,
        strike: 55,
        mid: 4.23,
        quantity: 1,
      },
    ],
    net_debit: 423,
    max_loss: 423,
    max_gain: strategyType === 'long_call' ? null : 500,
    breakeven: 59.23,
    required_move_pct: 13.2,
    payoff_at_target: 577,
    risk_reward_ratio: 1.36,
    liquidity_warnings: [],
    iv_theta_notes: ['fixture_iv_only'],
    suitability_notes: ['scenario_analysis_only'],
    limitations: ['mocked_product_route_harness'],
    no_advice_disclosure: 'Scenario analysis only; not personalized financial advice.',
  };
}

function strategyComparison(symbol: string) {
  return {
    symbol,
    underlying: underlying(),
    assumptions: { direction: 'bullish', target_price: 65, target_date: '2026-08-21' },
    strategies: ['long_call', 'long_put', 'bull_call_spread', 'bear_put_spread'].map(strategy),
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
      force_refresh_ignored: true,
    },
  };
}

function decision(symbol: string) {
  return {
    symbol,
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
    better_alternative: {
      strategy_type: 'bull_call_spread',
      reason: 'Defined-risk structure remains easier to bound in mocked verification.',
      max_loss: 230,
      risk_reward_ratio: 2.17,
    },
    no_advice_disclosure: 'Scenario analysis only; not personalized financial advice.',
    freshness: {
      source: 'playwright_fixture',
      freshness: 'mock',
      as_of: timestamp,
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
      force_refresh_ignored: true,
    },
  };
}

function symbolFromPath(path: string): string {
  const match = path.match(/\/api\/v1\/options\/underlyings\/([^/]+)/);
  return decodeURIComponent(match?.[1] || 'TEM').toUpperCase();
}

async function installOptionsRoute(page: Page): Promise<OptionsHarness> {
  const calls: string[] = [];
  const requests = createRequestLog(calls);

  await page.route('**/api/v1/stocks/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    calls.push(`${method} ${path}`);

    if (method === 'GET' && path.match(/^\/api\/v1\/stocks\/[^/]+\/evidence$/)) {
      return fulfillJson(route, {
        stockEvidencePacket: null,
        items: [],
        metadata: { readOnly: true, noExternalCallsInTests: true },
      });
    }
    if (method === 'GET' && path.match(/^\/api\/v1\/stocks\/[^/]+\/history$/)) {
      return fulfillJson(route, {
        symbol: 'ORCL',
        period: 'daily',
        prices: [],
        metadata: { readOnly: true, noExternalCallsInTests: true },
      });
    }

    return route.fallback();
  });

  await page.route('**/api/v1/options/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    calls.push(`${method} ${path}`);

    if (method === 'GET' && path.match(/^\/api\/v1\/options\/underlyings\/[^/]+\/summary$/)) {
      return fulfillJson(route, optionsSummary(symbolFromPath(path)));
    }
    if (method === 'GET' && path.match(/^\/api\/v1\/options\/underlyings\/[^/]+\/expirations$/)) {
      return fulfillJson(route, optionsExpirations(symbolFromPath(path)));
    }
    if (method === 'GET' && path.match(/^\/api\/v1\/options\/underlyings\/[^/]+\/chain$/)) {
      return fulfillJson(route, optionsChain(symbolFromPath(path)));
    }
    if (method === 'POST' && path === '/api/v1/options/strategies/compare') {
      const payload = request.postDataJSON() as { symbol?: string } | null;
      return fulfillJson(route, strategyComparison((payload?.symbol || 'TEM').toUpperCase()));
    }
    if (method === 'POST' && path === '/api/v1/options/decision/evaluate') {
      const payload = request.postDataJSON() as { symbol?: string } | null;
      return fulfillJson(route, decision((payload?.symbol || 'TEM').toUpperCase()));
    }

    return fulfillJson(route, { error: `Unhandled options harness route: ${method} ${path}` }, 500);
  });

  return { requests };
}

async function signIn(page: Page, redirectPath: string) {
  await page.goto(`/login?redirect=${encodeURIComponent(redirectPath)}`);
  const username = page.locator('#username');
  if (await username.waitFor({ state: 'visible', timeout: 10_000 }).then(() => true).catch(() => false)) {
    await username.fill('wolfy-user');
    await page.locator('#password').fill('mock-password');
    await Promise.all([
      page.waitForResponse((response) => response.url().includes('/api/v1/auth/login') && response.status() === 200),
      page.getByRole('button', { name: /sign in|登录继续|授权进入工作台|完成设置并登录/i }).click(),
    ]);
    await page.waitForURL(/\/$/);
  }
  await page.goto(redirectPath);
  await page.waitForLoadState('domcontentloaded');
}

async function expectNoHorizontalOverflow(page: Page) {
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function expectRootNonEmpty(page: Page) {
  await expect.poll(async () => page.locator('#root').evaluate((root) => root.textContent?.trim().length ?? 0)).toBeGreaterThan(0);
}

async function expectForbiddenTradingWordingAbsent(page: Page) {
  await expect(page.locator('body')).not.toContainText(
    /买入按钮|下单|立即交易|必买|稳赚|保证收益|guaranteed|best contract|AI recommends you buy|must buy|must sell|buy now|sell now|place order|you should buy|you should sell/i,
  );
}

async function expectNoRawInternalArtifacts(page: Page) {
  await expect(page.locator('body')).not.toContainText(rawInternalArtifactPattern);
  await expect(page.locator('details[open]')).toHaveCount(0);
}

async function expectSurfaceSafety(page: Page) {
  await expectRootNonEmpty(page);
  await expectNoHorizontalOverflow(page);
  await expectForbiddenTradingWordingAbsent(page);
  await expectNoRawInternalArtifacts(page);
}

async function expectNoOptionsTradingCta(page: Page) {
  const ctaPattern = /买入按钮|下单|立即交易|必买|稳赚|保证收益|best contract|AI recommends you buy|must buy|must sell|buy now|sell now|place order|you should buy|you should sell/i;
  await expect(page.getByRole('button', { name: ctaPattern })).toHaveCount(0);
  await expect(page.getByRole('link', { name: ctaPattern })).toHaveCount(0);
}

appTest.describe('AI and scanner public safety surfaces', () => {
  appTest('scanner exposes limited-data states while keeping diagnostics collapsed by default', async ({ page }) => {
    await installOptionsRoute(page);

    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await signIn(page, '/zh/scanner');

      await expect(page.getByTestId('user-scanner-workspace')).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('scanner-result-row-NVDA')).toBeVisible();
      await expect(page.getByTestId('scanner-status-strip')).toContainText(/数据暂不可用|数据不足|Provider issue|Fallback data|Insufficient data/);
      await expect(page.getByTestId('scanner-diagnostics-panel')).toHaveCount(0);
      await expect(page.getByTestId('scanner-result-history-summary')).toHaveCount(0);
      await expectSurfaceSafety(page);
    }
  });
});

appTest.describe('options public safety surface', () => {
  appTest('Options Lab labels synthetic data as non-decision-grade and keeps consumer details collapsed', async ({ page }) => {
    const harness = await installOptionsRoute(page);

    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await signIn(page, '/zh/options-lab');

      await expect(page.getByRole('heading', { name: '期权实验室' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('options-lab-consumer-availability')).toBeVisible();
      await expect(page.getByTestId('options-lab-consumer-availability')).toContainText('可用性');
      await expect(page.getByTestId('options-lab-decision-engine')).toBeVisible();
      await expect(page.getByTestId('options-lab-decision-engine')).toContainText('数据不足，暂不形成结论');
      await expect(page.getByTestId('options-lab-decision-engine')).toContainText('演示数据');
      await expect(page.locator('body')).toContainText('只读情景分析');
      await expect(page.locator('body')).toContainText('不构成执行指令');
      await expect(page.getByTestId('options-lab-summary-strip')).toContainText('首个观察结构');
      await expect(page.getByTestId('options-lab-summary-strip')).toContainText('假设价格');
      await expect(page.getByTestId('options-lab-strategy-comparison')).toContainText('观察结构样例');
      await expect(page.getByTestId('options-lab-strategy-comparison')).toContainText('样例顺序 #1');
      await expect(page.getByTestId('options-lab-strategy-comparison')).toContainText('专业结构：');
      await expect(page.getByTestId('options-lab-strategy-comparison')).toContainText('先把样例结构作为风险剖面阅读');
      await expect(page.locator('body')).not.toContainText('候选策略');
      await expect(page.locator('body')).not.toContainText('首个候选');
      await expect(page.locator('body')).not.toContainText('观察排序 #1');
      await expect(page.locator('body')).not.toContainText('先看排序靠前的结构');
      const analysisDetails = page.getByTestId('options-lab-analysis-details');
      await expect(analysisDetails).toBeVisible();
      await expect(analysisDetails.getByRole('button', { name: /展开/ })).toHaveAttribute('aria-expanded', 'false');
      await expect(page.locator('details[open]')).toHaveCount(0);
      await expectRootNonEmpty(page);
      await expectNoHorizontalOverflow(page);
      await expectNoRawInternalArtifacts(page);
      await expectNoOptionsTradingCta(page);

      expect(harness.requests.count('POST', '/api/v1/options/decision/evaluate')).toBeGreaterThan(0);
    }
  });
});
