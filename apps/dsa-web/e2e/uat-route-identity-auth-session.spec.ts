import { expect as baseExpect, type BrowserContext, type Page, type Route } from '@playwright/test';
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

type AuthSessionHarness = {
  requests: string[];
  getLoginState: () => boolean;
};

const protectedRoutes: RouteIdentity[] = [
  {
    label: '/market-overview',
    path: '/zh/market-overview',
    expectedUrl: /\/zh\/market-overview$/,
    readyTestId: 'market-overview-shell',
    heading: /市场状态概览/,
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
    label: '/stocks/structure-decision',
    path: '/zh/stocks/structure-decision',
    expectedUrl: /\/zh\/stocks\/structure-decision$/,
    readyTestId: 'stock-structure-entry-page',
  },
  {
    label: '/stocks/AAPL/structure-decision',
    path: '/zh/stocks/AAPL/structure-decision',
    expectedUrl: /\/zh\/stocks\/AAPL\/structure-decision$/,
    readyTestId: 'stock-structure-decision-page',
  },
  {
    label: '/watchlist',
    path: '/zh/watchlist',
    expectedUrl: /\/zh\/watchlist$/,
    readyTestId: 'watchlist-page',
    heading: /观察监控板/,
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
    label: '/scenario-lab',
    path: '/zh/scenario-lab',
    expectedUrl: /\/zh\/scenario-lab$/,
    readyTestId: 'scenario-lab-page',
    heading: /情景实验室/,
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

async function installAdminLoginSession(page: Page): Promise<AuthSessionHarness> {
  let isLoggedIn = false;
  const requests: string[] = [];

  await page.route('**/api/v1/auth/status**', async (route) => {
    requests.push('GET /api/v1/auth/status');
    await fulfillJson(route, createMockAuthStatus(isLoggedIn ? adminUser : null));
  });
  await page.route('**/api/v1/auth/me**', async (route) => {
    requests.push('GET /api/v1/auth/me');
    await (isLoggedIn
      ? fulfillJson(route, adminUser)
      : fulfillJson(route, { error: 'not_authenticated' }, 401));
  });
  await page.route('**/api/v1/auth/login**', async (route) => {
    requests.push('POST /api/v1/auth/login');
    isLoggedIn = true;
    await fulfillJson(route, { ok: true, currentUser: adminUser });
  });
  await page.route('**/api/v1/auth/logout**', async (route) => {
    requests.push('POST /api/v1/auth/logout');
    isLoggedIn = false;
    await fulfillJson(route, { ok: true });
  });

  return {
    requests,
    getLoginState: () => isLoggedIn,
  };
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
  await page.route('**/api/v1/stocks/*/validate', async (route) => {
    const symbol = decodeURIComponent(new URL(route.request().url()).pathname.split('/')[4] || 'ORCL');
    await fulfillJson(route, {
      stock_code: symbol,
      normalized_symbol: symbol,
      market: 'us',
      status: 'valid',
      valid: true,
      exists: true,
      stock_name: symbol,
    });
  });
  await page.route('**/api/v1/stocks/*/quote', async (route) => {
    const symbol = decodeURIComponent(new URL(route.request().url()).pathname.split('/')[4] || 'ORCL');
    await fulfillJson(route, {
      stock_code: symbol,
      stock_name: symbol,
      current_price: 211.32,
      change: 1.24,
      change_percent: 0.59,
      update_time: '2026-06-07T09:45:00-04:00',
      freshness: 'delayed',
      source_confidence: {
        source_label: 'Playwright Fixture',
        as_of: '2026-06-07T09:45:00-04:00',
        freshness: 'delayed',
        is_stale: false,
        is_partial: false,
        is_synthetic: false,
        is_unavailable: false,
      },
    });
  });
  await page.route('**/api/v1/stocks/*/research-packet', async (route) => {
    const symbol = decodeURIComponent(new URL(route.request().url()).pathname.split('/')[4] || 'ORCL');
    await fulfillJson(route, {
      symbol,
      market: 'us',
      identity: { name: symbol, exchange: 'NASDAQ', sector: 'Technology', industry: 'Software' },
      quote: { state: 'available', price: 211.32, change_percent: 0.59, as_of: '2026-06-07T09:45:00-04:00' },
      history: { state: 'available', bars: 90, period: 'daily', as_of: '2026-06-07' },
      structure: { state: 'available', label: 'Range-bound', confidence: 'medium', as_of: '2026-06-07' },
      fundamentals: { state: 'not_integrated', fields_available: [] },
      events: { state: 'missing', latest: [] },
      peer: { state: 'insufficient', benchmark: 'QQQ' },
      missing_data: ['peer evidence'],
      research_status: 'partial',
      next_data_action: 'Review comparable evidence before drawing conclusions.',
      observation_only: true,
      decision_grade: false,
      no_advice_disclosure: 'Research observation only.',
    });
  });
  await page.route('**/api/v1/stocks/*/history**', async (route) => {
    await fulfillJson(route, {
      symbol: 'ORCL',
      period: 'daily',
      data: [
        { date: '2026-06-05', open: 207, high: 213, low: 205, close: 211.32, volume: 14200000 },
        { date: '2026-06-06', open: 211, high: 214, low: 209, close: 212.56, volume: 11800000 },
      ],
      source_confidence: {
        source_label: 'Playwright Fixture',
        as_of: '2026-06-07T09:45:00-04:00',
        freshness: 'delayed',
        is_stale: false,
        is_partial: false,
        is_synthetic: false,
        is_unavailable: false,
      },
    });
  });
  await page.route('**/api/v1/stocks/*/technical-indicators', async (route) => {
    const symbol = decodeURIComponent(new URL(route.request().url()).pathname.split('/')[4] || 'ORCL');
    await fulfillJson(route, {
      contract_version: 'stock_technical_indicators_v1',
      symbol,
      status: 'available',
      timeframe: 'daily',
      as_of: '2026-06-07T09:45:00-04:00',
      freshness: 'fixture',
      source_label: 'Route identity fixture',
      data_quality: {
        status: 'available',
        required_bars: 200,
        observed_bars: 240,
        usable_bars: 240,
        missing_bars: 0,
        freshness: 'fixture',
      },
      indicators: {
        sma20: { value: 211.12 },
        sma50: { value: 207.34 },
        sma200: { value: 190.56 },
        ema12: { value: 212.45 },
        ema26: { value: 207.89 },
        rsi14: { value: 58.42 },
        macd: { value: 1.234 },
        macd_signal: { value: 0.987 },
        macd_histogram: { value: 0.247 },
        bollinger_upper: { value: 221.45 },
        bollinger_middle: { value: 210.12 },
        bollinger_lower: { value: 198.79 },
      },
      no_advice_disclosure: 'Research-only technical indicator context.',
    });
  });
  await page.route('**/api/v1/options/underlyings/*/structure', async (route) => {
    const symbol = decodeURIComponent(new URL(route.request().url()).pathname.split('/')[5] || 'ORCL');
    await fulfillJson(route, {
      contract_version: 'options-structure-summary-v1',
      symbol,
      status: 'not_available',
      calculation_state: 'not_available',
      observation_only: true,
      decision_grade: false,
      provider_configured: false,
      spot_price: null,
      as_of: null,
      freshness: 'unknown',
      snapshot: {
        contract_version: 'option-chain-snapshot-v1',
        symbol,
        spot_price: null,
        as_of: null,
        freshness: 'unknown',
        contracts: [],
        missing_inputs: ['authorized_options_structure_source'],
      },
      strike_summaries: [],
      expiration_summaries: [],
      nearest_expirations: [],
      zero_dte: {
        state: 'not_available',
        expiration: null,
        dte: null,
        contract_count: 0,
        call_open_interest: 0,
        put_open_interest: 0,
        call_volume: 0,
        put_volume: 0,
        open_interest_share: null,
        volume_share: null,
      },
      gamma_flip_level: {
        state: 'not_available',
        level: null,
        reason: 'authorized_structure_source_needed',
      },
      total_dealer_gamma_exposure: null,
      blocking_reasons: ['options_structure_unavailable'],
      warnings: [],
      next_evidence_needed: ['authorized_structure_source_needed'],
    });
  });
  await page.route('**/api/v1/stocks/*/evidence**', async (route) => {
    const symbol = decodeURIComponent(new URL(route.request().url()).pathname.split('/')[4] || 'ORCL');
    await fulfillJson(route, {
      symbol,
      evidence: [],
      missing_evidence: [{ kind: 'peer', message: 'Comparable evidence pending.' }],
      no_advice_disclosure: 'Research observation only.',
    });
  });
  await page.route('**/api/v1/stocks/*/structure-decision', async (route) => {
    const symbol = decodeURIComponent(new URL(route.request().url()).pathname.split('/')[4] || 'ORCL');
    await fulfillJson(route, {
      schema_version: 'uat_route_identity_stock_structure_fixture_v1',
      ticker: symbol,
      structure_state: 'range',
      confidence: 'medium',
      confidence_cap: { value: 55, label: 'Medium', reasons: ['Fixture route smoke evidence is bounded.'] },
      confidence_state: {
        status: 'partial',
        label: 'Evidence limited',
        reasons: ['Peer evidence remains incomplete.'],
      },
      component_scores: {
        trend: 58,
        relativeStrength: 52,
        evidenceQuality: 45,
      },
      explanation: {
        why_this_structure: 'Price evidence remains range-bound in the route smoke fixture.',
        what_confirms_it: ['Fresh price evidence remains available.'],
        what_invalidates_it: ['Evidence falls out of date.'],
        key_levels: [{ kind: 'support', value: 198.5, description: 'Fixture support level.' }],
      },
      research_notes: {
        watch_next: ['Refresh quote evidence before deeper review.'],
        needs_more_evidence: ['Comparable peer evidence.'],
        risk_flags: ['Evidence is partial.'],
      },
      data_quality: {
        status: 'partial',
        period: 'daily',
        requested_days: 120,
        observed_bars: 90,
        usable_bars: 90,
        reason: 'Fixture route smoke coverage.',
      },
      missing_evidence: [{ kind: 'peer', message: 'Comparable evidence pending.' }],
      no_advice_disclosure: 'Research observation only.',
    });
  });

  await page.route('**/api/v1/market/professional-data-capabilities', async (route) => {
    await fulfillJson(route, {
      contract_version: 'uat_route_identity_professional_data_capability_registry_v1',
      consumer_safe: true,
      summary: {
        total_capabilities: 0,
        live_count: 0,
        degraded_count: 0,
        entitlement_required_count: 0,
        configured_missing_count: 0,
        unavailable_count: 0,
        readiness_label: 'Fixture coverage only',
        operator_next_action: 'Use targeted UAT data fixtures for route verification.',
      },
      categories: [],
      capabilities: [],
      generated_at: '2026-06-07T09:45:00-04:00',
    });
  });
  await page.route('**/api/v1/market/professional-data-capabilities/admin', async (route) => {
    await fulfillJson(route, {
      contract_version: 'uat_route_identity_professional_data_capability_registry_v1',
      consumer_safe: true,
      summary: {
        total_capabilities: 0,
        live_count: 0,
        degraded_count: 0,
        entitlement_required_count: 0,
        configured_missing_count: 0,
        unavailable_count: 0,
        readiness_label: 'Admin fixture coverage only',
        operator_next_action: 'Use targeted provider UAT outside route identity coverage.',
      },
      categories: [],
      capabilities: [],
      generated_at: '2026-06-07T09:45:00-04:00',
    });
  });
  await page.route('**/api/v1/market/data-source-gap-registry', async (route) => {
    await fulfillJson(route, {
      contract_version: 'uat_route_identity_data_source_gap_registry_v1',
      diagnostic_only: true,
      provider_runtime_called: false,
      network_calls_enabled: false,
      score_authority_allowed: false,
      summary: {
        total_families: 0,
        ready_count: 0,
        partial_count: 0,
        missing_count: 0,
        blocked_count: 0,
        unavailable_count: 0,
        protected_review_count: 0,
      },
      families: [],
      acquisition_priority_queue: [],
    });
  });
  await page.route('**/api/v1/market/regime-read-model', async (route) => {
    await fulfillJson(route, {
      contract_version: 'uat_route_identity_market_regime_read_model_v1',
      status: 'partial',
      symbols: ['SPY', 'QQQ'],
      regime: {
        label: 'fixture_observation',
        status: 'partial',
        source: 'uat_route_identity_fixture',
      },
      product_summary: 'Route identity fixture keeps market overview data diagnostics bounded.',
      evidence_cards: [],
      symbol_context: [],
      surface_hints: [],
      missing_data_families: [],
      blocked_product_surfaces: [],
      readiness: {
        label: 'fixture_only',
        status: 'partial',
        missing_data_families: [],
        blocked_product_surfaces: [],
        next_operator_action: 'Run dedicated data UAT outside route identity coverage.',
      },
      data_quality: {
        adjusted_coverage_state: 'partial',
        ohlcv_coverage: { state: 'partial', required_bars: 60, available_symbols: ['SPY'], missing_symbols: [] },
        quote_snapshot_coverage: { state: 'partial', availability_state: 'partial', freshness_state: 'fixture', available_symbols: ['SPY'], missing_symbols: [], stale_symbols: [] },
        missing_data_families: [],
        blocked_product_surfaces: [],
      },
    });
  });
  await page.route('**/api/v1/market/decision-cockpit', async (route) => {
    await fulfillJson(route, {
      schema_version: 'market_decision_cockpit.v1',
      generated_at: '2026-06-07T09:45:00-04:00',
      market_regime_decision: {
        regime: 'riskOn',
        confidence: 'medium',
        confidence_score: 0.62,
        driver_scores: {
          breadth_participation: {
            score: 62,
            evidence_state: 'partial',
            reasons: ['Fixture keeps route identity checks bounded.'],
          },
        },
        explanation: {
          why_this_regime: ['Breadth is stable in the route fixture.'],
          what_confirms_it: ['Cross-asset fixture evidence is present.'],
          what_invalidates_it: ['Fixture evidence becomes unavailable.'],
        },
        invalidation_conditions: ['Fixture evidence becomes unavailable.'],
        research_priorities: {
          watch_today: ['Confirm route identity remains stable.'],
          needs_more_evidence: [],
          investigate_next: [],
        },
      },
      research_queue_preview: {
        top_candidates: [],
        queue_quality: 'mixed',
        evidence_gaps: [],
        preview_only: true,
      },
      options_structure_status: {
        gamma_evidence_status: 'unavailable',
        observation_only: true,
        decision_grade: false,
        missing_evidence: [],
        blocked_reason_codes: [],
      },
      cockpit_summary: {
        what_changed: ['Route fixture loaded.'],
        why_it_matters: ['Scenario Lab can render without provider access.'],
        what_to_watch: ['Navigation and auth state.'],
        confidence_limits: ['Fixture data only.'],
      },
      no_advice_disclosure: 'Research context only.',
      data_quality: {
        status: 'partial',
        reason: 'route_identity_fixture',
        reason_codes: [],
        freshness: 'fixture',
        as_of: '2026-06-07T09:45:00-04:00',
        blocking_modules: [],
        operator_action: 'Run data UAT separately.',
        consumer_safe_message: 'Route identity fixture is available.',
      },
    });
  });
  await page.route('**/api/v1/market/scenario-lab', async (route) => {
    await fulfillJson(route, {
      schema_version: 'market_scenario_lab_engine.v1',
      selected_scenario: {
        preset_id: 'volatilitySpike',
        name: 'volatilitySpike',
        label: 'Volatility spike',
      },
      base_market_context: {
        label: 'Fixture context',
        message: 'Route identity fixture keeps scenario data bounded.',
        evidence_state: 'partial',
        scoring_driver_count: 1,
      },
      base_regime: {
        regime: 'riskOn',
        confidence: 'medium',
        confidence_score: 0.62,
        status: 'partial',
      },
      scenario_regime: {
        regime: 'mixed',
        confidence: 'low',
        confidence_score: 0.42,
        status: 'partial',
      },
      baseline_readiness: {
        status: 'partial',
        baseline_snapshot: {
          state: 'partial',
          available: false,
          last_updated: '2026-06-07T09:45:00-04:00',
          affected_components: ['baselineSnapshot'],
        },
        market_frame: {
          state: 'available',
          available: true,
          last_updated: '2026-06-07T09:45:00-04:00',
          affected_components: [],
        },
        driver_inputs: {
          state: 'partial',
          available_driver_keys: ['breadthParticipation'],
          partial_driver_keys: ['breadthParticipation'],
          missing_driver_keys: [],
          affected_driver_keys: ['breadthParticipation'],
        },
        evidence_completeness: {
          state: 'partial',
          gaps: ['fixtureEvidence'],
        },
        data_state: 'request_supplied',
        sample_state: 'none',
        score_authority: 'observation_only',
        source_authority_allowed: false,
        authoritative: false,
        observation_only: true,
        ready: false,
        partial: true,
        blocked: false,
        affected_baseline_components: ['baselineSnapshot'],
        affected_driver_keys: ['breadthParticipation'],
        evidence_gaps: ['fixtureEvidence'],
        last_updated: '2026-06-07T09:45:00-04:00',
      },
      confidence_delta: -0.2,
      driver_deltas: { breadthParticipation: -12 },
      changed_drivers: ['breadthParticipation'],
      scenario_summary: ['Fixture scenario result loaded.'],
      what_would_confirm: ['Route identity remains stable.'],
      what_would_invalidate: ['Auth state changes unexpectedly.'],
      evidence_limits: ['Fixture data only.'],
      no_advice_disclosure: 'Research planning only.',
    });
  });
  await page.route('**/api/v1/scanner/status**', async (route) => {
    await fulfillJson(route, {
      status: 'ready',
      market: 'cn',
      profile: 'cn_preopen_v1',
      last_run_at: '2026-06-07T09:45:00-04:00',
      latest_run_id: 'uat-route-identity-scanner-run',
      data_readiness: {
        state: 'ready',
        market: 'cn',
        profile: 'cn_preopen_v1',
        universe_size: 0,
        scanner_universe_readiness: {
          contract_version: 'uat_route_identity_scanner_universe_readiness_v1',
          status: 'available',
          market: 'cn',
          universe_size: 0,
          freshness_state: 'fixture',
          required_data_classes: [],
          available_data_classes: [],
          missing_data_classes: [],
          blocked_product_surfaces: [],
          consumer_safe: true,
          consumer_safe_message: 'Scanner route identity fixture is available.',
        },
        candidate_evaluation_count: 0,
        selected_count: 0,
        rejected_count: 0,
        failed_count: 0,
        consumer_summary: 'Scanner route identity fixture is available.',
        next_data_action: 'Run scanner data UAT separately.',
      },
    });
  });
  await page.route('**/api/v1/watchlist/research-overlay', async (route) => {
    await fulfillJson(route, {
      schema_version: 'watchlist_research_overlay_v1',
      overlay_state: 'ready',
      research_summary: 'Route identity fixture keeps watchlist overlay bounded.',
      research_priority_queue: [],
      observation_only: true,
      decision_grade: false,
    });
  });

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
  await page.route('**/api/v1/portfolio/structure-review**', async (route) => {
    await fulfillJson(route, {
      schema_version: 'portfolio_structure_review_v1',
      as_of: '2026-06-07',
      account_id: null,
      cost_method: 'fifo',
      benchmark: 'SPY',
      holdings_structure: [],
      strongest_structures: [],
      weakest_evidence: [],
      common_risk_flags: [],
      missing_evidence: [],
      data_quality: {
        status: 'partial',
        holding_metadata_status: 'available',
        structure_evidence_status: 'available',
        read_only: true,
        fail_closed: false,
      },
      no_advice_disclosure: 'Observation-only research context; not personalized financial advice.',
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
  await page.route('**/api/v1/options/strategies/analyze', async (route) => {
    await fulfillJson(route, {
      symbol: 'TEM',
      expiration: '2026-06-19',
      scenario_prices: [45, 52.34, 65],
      analyses: [
        {
          strategy_type: 'long_strangle',
          legs: [],
          net_debit: 758,
          breakevens: [42.42, 62.58],
          payoff_table: [
            { underlying_price: 45, net_payoff: -258 },
            { underlying_price: 52.34, net_payoff: -758 },
            { underlying_price: 65, net_payoff: 242 },
          ],
          aggregate_greeks: {
            delta: 0.06,
            theta: -0.09,
            gamma: 0.02,
            vega: 0.18,
          },
          model_implied_probability: {
            model_implied_probability_of_profit: 0.4123,
            inputs: { risk_free_rate: 0.04 },
          },
          historical_win_rate: {
            state: 'unavailable',
            value: null,
            blockers: ['historical_options_chain_data_unavailable'],
          },
          readiness: {
            data_blockers: ['historical_options_chain_data_unavailable'],
          },
        },
      ],
      metadata: {
        read_only: true,
        no_order_placement: true,
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

  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page).toHaveURL(route.expectedUrl);
  await expectAuthenticatedAdminSession(page);
  await expect(page.getByTestId(route.readyTestId), `${route.label} after refresh`).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId('auth-guard-overlay')).toHaveCount(0);
}

async function expectAuthenticatedRouteState(
  page: Page,
  expectedUrl: RegExp,
  readyLocator: ReturnType<Page['locator']>,
) {
  await expect(page).toHaveURL(expectedUrl);
  await expectAuthenticatedAdminSession(page);
  await expect(readyLocator).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId('auth-guard-overlay')).toHaveCount(0);
  await expect(page).not.toHaveURL(/\/login(?:$|[?#/])/);
  await expect(page).not.toHaveURL(/\/guest(?:$|[?#/])/);
}

async function expectGuestProtectedGate(page: Page, expectedUrl: RegExp) {
  await expect(page).toHaveURL(expectedUrl);
  await expect(page.getByTestId('auth-guard-overlay')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId('auth-guard-overlay')).toContainText(/需要登录|Sign in/i);
  await baseExpect.poll(async () => page.locator('#root').evaluate((root) => root.textContent?.trim().length ?? 0)).toBeGreaterThan(0);
  await expect(page).not.toHaveURL(/about:blank/);
}

async function installFreshGuestContextMocks(context: BrowserContext) {
  await context.route('**/api/v1/auth/status**', async (route) => {
    await fulfillJson(route, createMockAuthStatus(null));
  });
  await context.route('**/api/v1/auth/me**', async (route) => {
    await fulfillJson(route, { error: 'not_authenticated' }, 401);
  });
}

async function clickPrimaryNav(page: Page, name: string | RegExp) {
  const desktopLink = page.getByTestId('shell-consumer-primary-nav').getByRole('link', { name }).first();
  if (await desktopLink.isVisible().catch(() => false)) {
    await desktopLink.click();
    return;
  }

  const moreButton = page.getByTestId('shell-consumer-primary-nav').getByRole('button', { name: '更多' }).first();
  if (await moreButton.isVisible().catch(() => false)) {
    await moreButton.click();
    const moreLink = page.getByTestId('shell-more-menu').getByRole('link', { name }).first();
    if (await moreLink.isVisible().catch(() => false)) {
      await moreLink.click();
      return;
    }
  }

  const mobileMenuButton = page.getByRole('button', { name: '打开导航菜单' });
  if (await mobileMenuButton.isVisible().catch(() => false)) {
    await mobileMenuButton.click();
    const drawerLink = page.getByRole('dialog', { name: '导航菜单' }).getByRole('link', { name }).first();
    if (await drawerLink.isVisible().catch(() => false)) {
      await drawerLink.click();
      return;
    }
  }

  const localizedRouteByName = new Map<string, string>([
    ['市场总览', '/zh/market-overview'],
    ['扫描器', '/zh/scanner'],
    ['个股结构', '/zh/stocks/structure-decision'],
    ['个股研究', '/zh/stocks/structure-decision'],
    ['观察列表', '/zh/watchlist'],
  ]);
  if (typeof name === 'string' && localizedRouteByName.has(name)) {
    await page.goto(localizedRouteByName.get(name)!);
    return;
  }

  throw new Error(`Navigation target not reachable in current shell: ${String(name)}`);
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

  test('keeps auth and route coherent across real browser history navigation', async ({ page }) => {
    await installAdminLoginSession(page);
    await installRouteIdentityMocks(page);

    await loginAsAdmin(page);
    await expectAuthenticatedRouteState(
      page,
      /\/zh\/market-overview$/,
      page.getByTestId('market-overview-shell'),
    );

    await clickPrimaryNav(page, '市场总览');
    await expectAuthenticatedRouteState(
      page,
      /\/zh\/market-overview$/,
      page.getByTestId('market-overview-shell'),
    );

    await clickPrimaryNav(page, '扫描器');
    await expectAuthenticatedRouteState(
      page,
      /\/zh\/scanner$/,
      page.getByTestId('user-scanner-workspace'),
    );

    await clickPrimaryNav(page, '个股结构');
    await expectAuthenticatedRouteState(
      page,
      /\/zh\/stocks\/structure-decision$/,
      page.getByTestId('stock-structure-entry-page'),
    );

    await clickPrimaryNav(page, '观察列表');
    await expectAuthenticatedRouteState(
      page,
      /\/zh\/watchlist$/,
      page.getByTestId('watchlist-page'),
    );

    await page.goBack();
    await expectAuthenticatedRouteState(
      page,
      /\/zh\/stocks\/structure-decision$/,
      page.getByTestId('stock-structure-entry-page'),
    );

    await page.goForward();
    await expectAuthenticatedRouteState(
      page,
      /\/zh\/watchlist$/,
      page.getByTestId('watchlist-page'),
    );
  });

  test('distinguishes navigation methods inside one authenticated browser context', async ({ page }) => {
    await installAdminLoginSession(page);
    await installRouteIdentityMocks(page);

    await loginAsAdmin(page);
    await expectAuthenticatedRouteState(
      page,
      /\/zh\/market-overview$/,
      page.getByTestId('market-overview-shell'),
    );

    await clickPrimaryNav(page, '扫描器');
    await expectAuthenticatedRouteState(
      page,
      /\/zh\/scanner$/,
      page.getByTestId('user-scanner-workspace'),
    );

    await page.goto('/zh/portfolio');
    await expectAuthenticatedRouteState(
      page,
      /\/zh\/portfolio$/,
      page.getByTestId('portfolio-bento-page'),
    );

    await page.evaluate(() => {
      window.location.assign('/zh/scenario-lab');
    });
    await expectAuthenticatedRouteState(
      page,
      /\/zh\/scenario-lab$/,
      page.getByTestId('scenario-lab-page'),
    );

    await page.reload({ waitUntil: 'domcontentloaded' });
    await expectAuthenticatedRouteState(
      page,
      /\/zh\/scenario-lab$/,
      page.getByTestId('scenario-lab-page'),
    );

    await page.goBack();
    await expectAuthenticatedRouteState(
      page,
      /\/zh\/portfolio$/,
      page.getByTestId('portfolio-bento-page'),
    );

    await page.goForward();
    await expectAuthenticatedRouteState(
      page,
      /\/zh\/scenario-lab$/,
      page.getByTestId('scenario-lab-page'),
    );

    await expect(page).not.toHaveURL(/\/settings\/system|about:blank|\/login|\/guest/);
  });

  test('treats a fresh browser context without cookies as guest, not session loss', async ({ browser }) => {
    const context = await browser.newContext();
    await installFreshGuestContextMocks(context);
    const page = await context.newPage();

    try {
      await page.goto('/zh/portfolio');
      await expectGuestProtectedGate(page, /\/zh\/portfolio$/);
    } finally {
      await context.close();
    }
  });

  test('logs out through the visible shell UI and blocks protected access afterward', async ({ page }) => {
    const session = await installAdminLoginSession(page);
    await installRouteIdentityMocks(page);

    await loginAsAdmin(page);
    await expectAuthenticatedRouteState(
      page,
      /\/zh\/market-overview$/,
      page.getByTestId('market-overview-shell'),
    );

    await page.getByTestId('shell-account-center-entry').getByRole('button', { name: '账户中心' }).click();
    await page.getByTestId('shell-account-center-menu').getByRole('menuitem', { name: '退出登录' }).click();
    await page.getByRole('button', { name: '确认退出' }).click();

    await expect(page).toHaveURL(/\/zh\/guest$/);
    expect(session.getLoginState()).toBe(false);
    expect(session.requests).toContain('POST /api/v1/auth/logout');

    await page.goto('/zh/portfolio');
    await expectGuestProtectedGate(page, /\/zh\/portfolio$/);
  });
});
