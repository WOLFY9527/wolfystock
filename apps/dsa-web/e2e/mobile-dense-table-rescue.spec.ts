import { expect, test as base, type Page, type Route } from '@playwright/test';
import { installUxDensityPublicMocks } from './fixtures/uxDensity';
import {
  expect as adminExpect,
  installAdminAuthHarness,
  openAdminRouteWithHarness,
  test as adminTest,
} from './fixtures/adminAuth';
import { installPortfolioSmokeHarness } from './fixtures/portfolioSmoke';
import { expect as appExpect, test as appTest } from './fixtures/appSmoke';

const mobileViewport = { width: 390, height: 844 };
const timestamp = '2026-05-06T10:30:00+08:00';
const expiration = '2026-06-19';

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function expectNoDocumentOverflow(page: Page) {
  await expect.poll(async () => page.evaluate(() => {
    return Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth);
  })).toBeLessThanOrEqual(1);
}

async function expectBoxWithinViewport(page: Page, testId: string) {
  const box = await page.getByTestId(testId).boundingBox();
  expect(box).not.toBeNull();
  expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(mobileViewport.width + 1);
}

async function installAdminSessionForConsumerRoute(page: Page) {
  const currentUser = {
    id: 'pw-admin-user',
    username: 'playwright-admin',
    displayName: 'Playwright Admin',
    role: 'admin',
    isAdmin: true,
    isAuthenticated: true,
    transitional: false,
    authEnabled: true,
    adminCapabilities: ['ops:providers:read'],
    canReadProviders: true,
  };
  await page.addInitScript(() => {
    window.sessionStorage.setItem('dsa-admin-surface-mode', 'admin');
  });
  await page.route('**/api/v1/auth/status', (route) => fulfillJson(route, {
    authEnabled: true,
    loggedIn: true,
    passwordSet: true,
    passwordChangeable: true,
    setupState: 'enabled',
    currentUser,
  }));
  await page.route('**/api/v1/auth/me', (route) => fulfillJson(route, currentUser));
}

function metadata() {
  return {
    read_only: true,
    no_external_calls_in_tests: true,
    limitations: ['mocked_playwright_options_route'],
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

function optionContract(symbol: string, side: 'call' | 'put', strike: number, mid: number) {
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

function symbolFromPath(path: string) {
  const match = path.match(/\/api\/v1\/options\/underlyings\/([^/]+)/);
  return decodeURIComponent(match?.[1] || 'TEM').toUpperCase();
}

function optionsSummary(symbol: string) {
  return {
    symbol,
    market: 'us',
    underlying: underlying(),
    options_availability: {
      supported: true,
      provider: 'playwright_fixture',
      limitations: ['mocked_options_route'],
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

function optionsChain(symbol: string) {
  return {
    symbol,
    expiration,
    underlying: underlying(),
    calls: [optionContract(symbol, 'call', 55, 4.23), optionContract(symbol, 'call', 60, 2.28)],
    puts: [optionContract(symbol, 'put', 50, 2.42), optionContract(symbol, 'put', 45, 1.16)],
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
    limitations: ['mocked_options_route'],
    no_advice_disclosure: 'Scenario analysis only; not personalized financial advice.',
  };
}

function strategyComparison(symbol: string) {
  return {
    symbol,
    underlying: underlying(),
    assumptions: { direction: 'bullish', target_price: 65, target_date: '2026-08-21' },
    strategies: ['long_call', 'long_put', 'bull_call_spread', 'bear_put_spread'].map(strategy),
    limitations: ['mocked_options_route'],
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
      blocking_reasons: ['mocked_options_route'],
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
    primary_reasons: ['mocked_options_route'],
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

async function installOptionsMocks(page: Page) {
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
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (method === 'GET' && path === '/api/v1/auth/status') {
      return fulfillJson(route, {
        authEnabled: true,
        loggedIn: true,
        passwordSet: true,
        passwordChangeable: true,
        setupState: 'enabled',
        currentUser,
      });
    }
    if (method === 'GET' && path === '/api/v1/auth/me') {
      return fulfillJson(route, currentUser);
    }
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
    return fulfillJson(route, { error: `Unhandled options route: ${method} ${path}` }, 500);
  });
}

function adminLogHealthSummary() {
  return {
    total_events: 2,
    failed_events: 1,
    warning_events: 0,
    slow_events: 0,
    failure_rate: 0.5,
    status: 'degraded',
    failures_by_category: [{ key: 'data_source', label: 'data_source', count: 1 }],
    failures_by_provider: [{ key: 'newsapi', label: 'newsapi', count: 1 }],
    failures_by_reason: [{ key: 'timeout', label: 'timeout', count: 1 }],
    actor_breakdown: [{ key: 'user', label: 'user', count: 1 }],
    top_recent_errors: [],
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
        id: 'analysis-tsla',
        event: 'TSLA',
        category: 'analysis',
        type: 'stock_analysis',
        event_type: 'stock_analysis',
        status: 'partial',
        summary: 'TSLA 分析完成，数据源部分降级',
        symbol: 'TSLA',
        market: 'US',
        actor_type: 'user',
        actor_label: 'alice',
        context_label: 'TSLA',
        provider: 'newsapi',
        source: 'Yahoo',
        reason: 'timeout',
        error_summary: 'News API timeout（已脱敏）',
        request_id: 'req-tsla-123456789',
        trace_id: 'trace-tsla-abcdef',
        root_cause_summary: 'News API timeout（已脱敏）',
        step_trace_available: true,
        started_at: timestamp,
        duration_ms: 12345,
        step_count: 4,
        success_step_count: 2,
        failed_step_count: 1,
        skipped_step_count: 1,
        unknown_step_count: 0,
      },
    ],
  };
}

function sessionsPayload() {
  return {
    total: 1,
    items: [
      {
        session_id: 'session-tsla',
        task_id: 'task-tsla',
        overall_status: 'failed',
        truth_level: 'confirmed',
        started_at: timestamp,
        ended_at: timestamp,
        readable_summary: {
          log_level: 'WARNING',
          log_category: 'data_source',
          event_message: '数据源响应超时',
          context_label: 'TSLA',
          provider: 'newsapi',
          source: 'Yahoo',
          reason: 'timeout',
          error_summary: 'News API timeout（已脱敏）',
          request_id: 'req-tsla-123456789',
          trace_id: 'trace-tsla-abcdef',
        },
      },
    ],
    summary: {
      error_count: 1,
      warning_count: 1,
      data_source_failure_count: 1,
      slow_request_count: 0,
      latest_critical_at: timestamp,
      health_summary: adminLogHealthSummary(),
    },
  };
}

async function installAdminLogsMocks(page: Page) {
  await installAdminAuthHarness(page);
  await page.route('**/api/v1/admin/logs/storage/summary', (route) => fulfillJson(route, {
    total_log_count: 1,
    total_event_count: 1,
    session_count: 1,
    event_count: 1,
    retention_days: 90,
    minimum_retention_days: 7,
    status: 'ok',
  }));
  await page.route('**/api/v1/admin/logs/data-missing-drilldown**', (route) => fulfillJson(route, { total: 0, items: [] }));
  await page.route('**/api/v1/admin/logs/operator-issue-rollup**', (route) => fulfillJson(route, { total: 0, items: [] }));
  await page.route('**/api/v1/admin/logs/incident-timeline**', (route) => fulfillJson(route, {
    lookup: { limit: 20 },
    total: 0,
    items: [],
    hooks: [],
    empty_state: { read_only: true },
    metadata: { read_only: true },
  }));
  await page.route('**/api/v1/admin/logs**', (route) => {
    if (route.request().method() === 'GET') {
      return fulfillJson(route, businessEventsPayload());
    }
    return fulfillJson(route, { mode: 'retention', dry_run: true, matched_log_count: 0, matched_event_count: 0 });
  });
  await page.route('**/api/v1/admin/logs/sessions**', (route) => fulfillJson(route, sessionsPayload()));
}

base.describe('T-1168 liquidity mobile dense rescue', () => {
  base('keeps admin liquidity indicator details contained at 390px', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error' && !message.text().includes('favicon.ico')) {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => consoleErrors.push(error.message));

    await page.setViewportSize(mobileViewport);
    await installAdminSessionForConsumerRoute(page);
    await installUxDensityPublicMocks(page);
    await page.goto('/zh/market/liquidity-monitor');
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByRole('heading', { name: '流动性监测' })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('liquidity-monitor-guidance-panel')).toBeVisible();
    await expectNoDocumentOverflow(page);
    expect(consoleErrors).toEqual([]);
  });
});

base.describe('T-1168 options mobile dense rescue', () => {
  base('keeps options visuals and chain details contained at 390px', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error' && !message.text().includes('favicon.ico')) {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => consoleErrors.push(error.message));

    await page.setViewportSize(mobileViewport);
    await installOptionsMocks(page);
    await page.goto('/options-lab');
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByRole('heading', { name: '期权实验室' })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('options-lab-payoff-visual').locator('span[aria-hidden="true"]').last()).toHaveClass(/bg-gradient-to-l/);
    await expect(page.getByTestId('options-lab-iv-visual').locator('span[aria-hidden="true"]').last()).toHaveClass(/bg-gradient-to-l/);
    await expectNoDocumentOverflow(page);
    expect(consoleErrors).toEqual([]);
  });
});

base.describe('T-1168 portfolio mobile dense rescue', () => {
  base('keeps holdings cards contained at 390px', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error' && !message.text().includes('favicon.ico')) {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => consoleErrors.push(error.message));

    await page.setViewportSize(mobileViewport);
    await installPortfolioSmokeHarness(page);
    await page.goto('/zh/portfolio');
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByTestId('portfolio-bento-page')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('portfolio-holdings-mobile-list')).toBeVisible();
    await expect(page.getByTestId('portfolio-holding-mobile-card-AAPL')).toBeVisible();
    await expect(page.getByTestId('portfolio-current-holdings-panel').getByRole('table')).toBeHidden();
    await expectNoDocumentOverflow(page);
    await expectBoxWithinViewport(page, 'portfolio-holding-mobile-card-AAPL');
    expect(consoleErrors).toEqual([]);
  });
});

adminTest.describe('T-1168 admin mobile dense rescue', () => {
  adminTest('keeps admin user holdings cards contained at 390px', async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    await openAdminRouteWithHarness(page, '/zh/admin/users/user-123?tab=portfolio');

    await adminExpect(page.getByRole('heading', { name: '组合只读总览' })).toBeVisible({ timeout: 15_000 });
    await adminExpect(page.getByTestId('admin-users-holdings-mobile-list')).toBeVisible();
    await adminExpect(page.getByTestId('admin-users-holding-mobile-card-AAPL')).toBeVisible();
    await adminExpect(page.getByTestId('admin-users-holdings-mobile-list').locator('xpath=following-sibling::*').getByRole('table')).toBeHidden();
    await expectNoDocumentOverflow(page);
    await expectBoxWithinViewport(page, 'admin-users-holding-mobile-card-AAPL');
  });

  adminTest('keeps admin logs mobile list and raw local scroll contained at 390px', async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    await installAdminLogsMocks(page);
    await page.goto('/zh/admin/logs');
    await page.waitForLoadState('domcontentloaded');

    await adminExpect(page.getByTestId('business-events-mobile-list')).toBeVisible({ timeout: 15_000 });
    await adminExpect(page.getByTestId('business-events-table-shell')).toBeHidden();
    await expectNoDocumentOverflow(page);

    await page.getByRole('tab', { name: '原始日志' }).click();
    const rawShell = page.getByTestId('raw-logs-table-shell');
    const rawInner = page.getByTestId('raw-logs-table-inner');
    await adminExpect(rawShell).toBeVisible();
    await adminExpect(rawShell.locator('span[aria-hidden="true"]').last()).toHaveClass(/bg-gradient-to-l/);
    const shellBox = await rawShell.boundingBox();
    const innerBox = await rawInner.boundingBox();
    adminExpect(shellBox).not.toBeNull();
    adminExpect(innerBox).not.toBeNull();
    adminExpect(innerBox?.width ?? 0).toBeGreaterThan(shellBox?.width ?? Number.POSITIVE_INFINITY);
    await expectNoDocumentOverflow(page);
  });
});

appTest.describe('T-1168 scanner mobile dense rescue', () => {
  appTest('keeps scanner status strip affordance contained at 390px', async ({ page }) => {
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
    await page.route('**/api/v1/auth/status', (route) => fulfillJson(route, {
      authEnabled: true,
      loggedIn: true,
      passwordSet: true,
      passwordChangeable: true,
      setupState: 'enabled',
      currentUser,
    }));
    await page.route('**/api/v1/auth/me', (route) => fulfillJson(route, currentUser));
    await page.setViewportSize(mobileViewport);
    await page.goto('/zh/scanner');
    await page.waitForLoadState('domcontentloaded');

    await appExpect(page.getByTestId('scanner-status-strip-scroll-frame')).toBeVisible({ timeout: 15_000 });
    await appExpect(page.getByTestId('scanner-status-strip-scroll-frame').locator('span[aria-hidden="true"]').last()).toHaveClass(/bg-gradient-to-l/);
    await expectNoDocumentOverflow(page);
  });
});
