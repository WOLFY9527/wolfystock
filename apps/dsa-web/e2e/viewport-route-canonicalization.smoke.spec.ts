import type { Page, Route } from '@playwright/test';
import { expect as appExpect, test as appTest } from './fixtures/appSmoke';
import { expect as adminExpect, installAdminAuthHarness, test as adminTest } from './fixtures/adminAuth';

const viewports = [
  { name: 'desktop', size: { width: 1440, height: 1000 } },
  { name: 'mobile', size: { width: 390, height: 844 } },
] as const;

const productRoutes = [
  { path: '/zh/scanner', canonical: '/zh/scanner', marker: 'scanner-ranking-board-page' },
  { path: '/zh/watchlist', canonical: '/zh/watchlist', marker: 'watchlist-page' },
  { path: '/zh/portfolio', canonical: '/zh/portfolio', marker: 'portfolio-bento-page' },
  { path: '/zh/options-lab', canonical: '/zh/options-lab', marker: 'options-lab-page-root' },
  { path: '/zh/market-overview', canonical: '/zh/market-overview', marker: 'market-overview-shell' },
  { path: '/zh/market/liquidity-monitor', canonical: '/zh/market/liquidity-monitor', marker: 'liquidity-monitor-guidance-panel' },
  { path: '/zh/market/rotation-radar', canonical: '/zh/market/rotation-radar', marker: 'market-rotation-radar-page' },
] as const;

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
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

function portfolioAccountsPayload() {
  return {
    accounts: [
      {
        id: 1,
        owner_id: 'user-1',
        name: 'Route Smoke Main',
        broker: 'manual',
        market: 'us',
        base_currency: 'USD',
        is_active: true,
        created_at: '2026-05-06T09:45:00-04:00',
        updated_at: '2026-05-06T09:45:00-04:00',
      },
    ],
  };
}

function portfolioRiskPayload() {
  return {
    as_of: '2026-05-06',
    account_id: null,
    cost_method: 'fifo',
    currency: 'USD',
    thresholds: {},
    concentration: {
      total_market_value: 600,
      top_weight_pct: 100,
      alert: false,
      top_positions: [{ symbol: 'AAPL', market_value_base: 600, weight_pct: 100, is_alert: false }],
    },
    sector_concentration: {
      total_market_value: 0,
      top_weight_pct: 0,
      alert: false,
      top_sectors: [],
      coverage: {},
      errors: [],
    },
    drawdown: {
      series_points: 0,
      max_drawdown_pct: 0,
      current_drawdown_pct: 0,
      alert: false,
      fx_stale: false,
    },
    stop_loss: {
      near_alert: false,
      triggered_count: 0,
      near_count: 0,
      items: [],
    },
  };
}

function emptyPortfolioListPayload() {
  return { items: [], total: 0, page: 1, page_size: 20 };
}

function optionsUnderlyingPayload(symbol: string) {
  return {
    price: 52.34,
    change_pct: 1.2,
    source: 'playwright_fixture',
    as_of: '2026-05-06T09:45:00-04:00',
    freshness: 'mock',
    symbol,
  };
}

function optionsSummaryPayload(symbol: string) {
  return {
    symbol,
    market: 'us',
    underlying: optionsUnderlyingPayload(symbol),
    options_availability: {
      supported: true,
      provider: 'playwright_fixture',
      limitations: ['mocked_route_canonicalization_smoke'],
    },
    metadata: {
      read_only: true,
      no_external_calls_in_tests: true,
      source_label: 'Playwright Fixture',
      updated_at: '2026-05-06T09:45:00-04:00',
    },
  };
}

function optionsExpirationsPayload(symbol: string) {
  return {
    symbol,
    expirations: [
      {
        date: '2026-06-19',
        dte: 44,
        type: 'monthly',
        chain_available: true,
        as_of: '2026-05-06T09:45:00-04:00',
        source: 'playwright_fixture',
        warnings: ['mocked_chain'],
      },
    ],
    metadata: {
      read_only: true,
      no_external_calls_in_tests: true,
      source_label: 'Playwright Fixture',
      updated_at: '2026-05-06T09:45:00-04:00',
    },
  };
}

function optionsContract(symbol: string, side: 'call' | 'put', strike: number, mid: number) {
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

function optionsChainPayload(symbol: string) {
  return {
    symbol,
    expiration: '2026-06-19',
    underlying: optionsUnderlyingPayload(symbol),
    calls: [optionsContract(symbol, 'call', 55, 4.23), optionsContract(symbol, 'call', 60, 2.28)],
    puts: [optionsContract(symbol, 'put', 50, 2.42), optionsContract(symbol, 'put', 45, 1.16)],
    filters_applied: { min_open_interest: 100, max_spread_pct: 25 },
    chain_as_of: '2026-05-06T09:45:00-04:00',
    source: 'playwright_fixture',
    limitations: ['mocked_chain'],
    metadata: {
      read_only: true,
      no_external_calls_in_tests: true,
      source_label: 'Playwright Fixture',
      updated_at: '2026-05-06T09:45:00-04:00',
    },
  };
}

function optionsStrategyPayload(strategyType: string) {
  return {
    strategy_type: strategyType,
    legs: [
      {
        action: 'buy',
        side: strategyType.includes('put') ? 'put' : 'call',
        contract_symbol: `TEM260619${strategyType.includes('put') ? 'P' : 'C'}00055000`,
        expiration: '2026-06-19',
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
    limitations: ['mocked_route_canonicalization_smoke'],
    no_advice_disclosure: 'Scenario analysis only; not personalized financial advice.',
  };
}

function optionsStrategyComparisonPayload(symbol: string) {
  return {
    symbol,
    underlying: optionsUnderlyingPayload(symbol),
    assumptions: { direction: 'bullish', target_price: 65, target_date: '2026-08-21' },
    strategies: ['long_call', 'long_put', 'bull_call_spread', 'bear_put_spread'].map(optionsStrategyPayload),
    limitations: ['mocked_route_canonicalization_smoke'],
    metadata: {
      read_only: true,
      fixture_backed: true,
      no_external_calls: true,
      no_order_placement: true,
      no_broker_connection: true,
      no_portfolio_mutation: true,
      no_trading_recommendation: true,
    },
  };
}

function optionsDecisionPayload(symbol: string) {
  return {
    symbol,
    strategy: 'bull_call_spread',
    data_quality: {
      data_quality_score: 62,
      data_quality_tier: 'synthetic_demo_only',
      source_type: 'playwright_fixture',
      as_of_age_minutes: 0,
      blocking_reasons: ['mocked_route_canonicalization_smoke'],
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
    primary_reasons: ['mocked_route_canonicalization_smoke'],
    risk_warnings: ['provider_validation_required', 'synthetic_demo_only'],
    better_alternative: null,
    no_advice_disclosure: 'Scenario analysis only; not personalized financial advice.',
    freshness: {
      source: 'playwright_fixture',
      freshness: 'mock',
      as_of: '2026-05-06T09:45:00-04:00',
    },
    metadata: {
      read_only: true,
      fixture_backed: true,
      no_external_calls: true,
      no_order_placement: true,
      no_broker_connection: true,
      no_portfolio_mutation: true,
      no_trading_recommendation: true,
    },
  };
}

function symbolFromOptionsRequest(route: Route) {
  const path = new URL(route.request().url()).pathname;
  return decodeURIComponent(path.split('/')[5] || 'TEM').toUpperCase();
}

async function installProductRouteApiMocks(page: Page) {
  await page.route('**/api/v1/portfolio/accounts**', (route) => fulfillJson(route, portfolioAccountsPayload()));
  await page.route('**/api/v1/portfolio/imports/brokers**', (route) => fulfillJson(route, { brokers: [] }));
  await page.route('**/api/v1/portfolio/broker-connections**', (route) => fulfillJson(route, { connections: [] }));
  await page.route('**/api/v1/portfolio/trades**', (route) => fulfillJson(route, emptyPortfolioListPayload()));
  await page.route('**/api/v1/portfolio/risk**', (route) => fulfillJson(route, portfolioRiskPayload()));
  await page.route('**/api/v1/options/underlyings/*/summary', (route) => fulfillJson(route, optionsSummaryPayload(symbolFromOptionsRequest(route))));
  await page.route('**/api/v1/options/underlyings/*/expirations', (route) => fulfillJson(route, optionsExpirationsPayload(symbolFromOptionsRequest(route))));
  await page.route('**/api/v1/options/underlyings/*/chain**', (route) => fulfillJson(route, optionsChainPayload(symbolFromOptionsRequest(route))));
  await page.route('**/api/v1/options/strategies/compare', (route) => fulfillJson(route, optionsStrategyComparisonPayload('TEM')));
  await page.route('**/api/v1/options/decision/evaluate', (route) => fulfillJson(route, optionsDecisionPayload('TEM')));
}

async function installLiquidityMonitorMock(page: Page) {
  await page.route('**/api/v1/market/liquidity-monitor**', async (route) => {
    await fulfillJson(route, {
      endpoint: '/api/v1/market/liquidity-monitor',
      generated_at: '2026-05-09T10:30:00+08:00',
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
        latest_as_of: '2026-05-09T10:30:00+08:00',
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
          updated_at: '2026-05-09T10:30:00+08:00',
        },
        {
          key: 'market_breadth',
          label: 'Market breadth',
          status: 'live',
          freshness: 'live',
          included_in_score: true,
          score_contribution: 0.26,
          score_weight: 0.5,
          summary: '市场宽度维持扩散。',
          updated_at: '2026-05-09T10:30:00+08:00',
        },
      ],
      liquidity_impulse_synthesis: {
        liquidity_impulse: 'expanding_liquidity',
        impulse_label: 'Liquidity appears to be expanding',
        subtype: 'policy_and_breadth',
        confidence: 0.76,
        confidence_label: 'medium',
        pillar_scores: {
          dollar_pressure: 0.55,
          equity_flow_proxy: 0.66,
          crypto_liquidity_beta: 0.5,
          funding_stress: 0.48,
        },
        direction_score: 0.64,
        dominant_drivers: [],
        counter_evidence: [],
        data_gaps: [],
        narrative_bullets: ['政策流动性与市场宽度共同支持观察。'],
        evidence_quality: {
          version: 'playwright_route_canonicalization',
          input_count: 2,
          scoring_evidence_count: 2,
          scoring_pillar_count: 2,
          covered_pillars: ['dollar_pressure', 'equity_flow_proxy'],
          missing_pillars: [],
          discounted_evidence_count: 0,
          observation_only_evidence_count: 0,
          score_blocked_evidence_count: 0,
          proxy_only_scoring_count: 0,
          real_scoring_evidence_count: 2,
          all_scoring_evidence_proxy_only: false,
          data_gap_count: 0,
        },
        not_investment_advice: true,
      },
      advisory_disclosure: '仅用于观察市场流动性环境，非买卖建议。',
      source_metadata: {
        external_provider_calls: false,
        provider_runtime_changed: false,
        market_cache_mutation: false,
      },
    });
  });
}

function marketProviderOperationsPayload() {
  const timestamp = '2026-06-05T00:00:00Z';

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
        provider: 'sina',
        source_label: '新浪财经',
        source_type: 'public_api',
        domain: 'equity_index',
        endpoint: '/api/v1/market/cn-indices',
        card: 'ChinaIndicesCard',
        cache_key: 'cn_indices',
        status: 'live',
        freshness: 'live',
        as_of: timestamp,
        updated_at: timestamp,
        last_successful_at: timestamp,
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
        source_label: 'Local smoke fixture',
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
        authority_basis: 'Local smoke fixture for route alias coverage.',
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
      source: 'local_smoke_fixture',
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
        user_facing_message: '本地测试样例已覆盖市场数据读取。',
        remediation_hint: null,
        affects_surfaces: ['Market Overview'],
        product_affected_surfaces: ['Market Overview'],
        secret_configured: false,
        details: { read_only: true },
      },
    ],
  };
}

async function installProviderOpsMocks(page: Page) {
  await page.route('**/api/v1/admin/providers/operations-matrix', (route) => fulfillJson(route, providerOperationsMatrixPayload()));
  await page.route('**/api/v1/market/data-readiness**', (route) => fulfillJson(route, marketDataReadinessPayload()));
  await page.route('**/api/v1/admin/market-providers/operations**', (route) => fulfillJson(route, marketProviderOperationsPayload()));
}

function expectCanonicalPath(page: Page, canonicalPath: string) {
  return appExpect.poll(() => new URL(page.url()).pathname).toBe(canonicalPath);
}

appTest.describe('viewport route canonicalization smoke', () => {
  for (const viewport of viewports) {
    appTest(`keeps product canonical routes stable at ${viewport.size.width}px`, async ({ page }) => {
      for (const routeCheck of productRoutes) {
        await page.unrouteAll({ behavior: 'ignoreErrors' });
        await page.setViewportSize(viewport.size);
        await installSignedInProductSession(page);
        await installProductRouteApiMocks(page);
        await installLiquidityMonitorMock(page);

        await page.goto(routeCheck.path);
        await page.waitForLoadState('domcontentloaded');

        await expectCanonicalPath(page, routeCheck.canonical);
        await appExpect(page.getByTestId(routeCheck.marker)).toBeVisible({ timeout: 15_000 });
      }
    });
  }
});

adminTest.describe('viewport route alias canonicalization smoke', () => {
  for (const viewport of viewports) {
    adminTest(`keeps expected admin provider alias stable at ${viewport.size.width}px`, async ({ page }) => {
      await page.setViewportSize(viewport.size);
      await installAdminAuthHarness(page);
      await installProviderOpsMocks(page);

      await page.goto('/zh/admin/providers');
      await page.waitForLoadState('domcontentloaded');

      await adminExpect.poll(() => new URL(page.url()).pathname).toBe('/zh/admin/market-providers');
      await adminExpect(page.getByTestId('market-provider-operations-page')).toBeVisible({ timeout: 15_000 });
    });
  }
});
