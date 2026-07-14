import { expect as baseExpect, type Page, type Route } from '@playwright/test';
import { expect as adminExpect, expectNoHorizontalOverflow as expectNoAdminHorizontalOverflow, expectNoRawSecretLikeText, installAdminAuthHarness, openAdminRouteWithHarness, test as adminTest } from './fixtures/adminAuth';
import { expect as appExpect, test as appTest } from './fixtures/appSmoke';
import { installUxDensityAuthenticatedSession, installUxDensityPublicMocks } from './fixtures/uxDensity';

const desktopViewport = { width: 1440, height: 1000 };
const serverErrorShellPattern = /服务器暂时不可用|上游模型暂时不可用|Something went wrong|Server unavailable|Request timed out|请求超时/i;
const rawLeakagePattern = /raw\s+(payload|response|schema|prompt|trace)|debug\s+(payload|response|schema|panel)|provider\s+payload|provider\s+route|token\s*[=:]|session[_\s-]?id\s*[=:]|cookie\s*[=:]|secret\s*[=:]|bearer\s+[a-z0-9._-]+/i;
const consumerAuthorityLeakPattern = /\b(provider|cache|raw|debug|router|env|token|payload|credential)\b/i;
const guestLandingForbiddenTradingPattern = /buy now|sell now|place order|submit order|connect broker|broker CTA|guaranteed|必买|稳赚|保证收益|立即交易|提交订单|连接经纪商/i;
const adminLogsEnglishDegradedPattern = /Provider Issue Rollup|provider unavailable|fallback|stale|timeout|partial|raw English cache/i;

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installSignedInAppSmokeSession(page: Page) {
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

async function installGuestAppSmokeSession(page: Page) {
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

async function readBodyText(page: Page) {
  return page.locator('body').innerText();
}

async function expectNoGenericServerErrorShell(page: Page) {
  await baseExpect(await readBodyText(page)).not.toMatch(serverErrorShellPattern);
}

async function expectNoVisibleRawLeakage(page: Page) {
  await baseExpect(await readBodyText(page)).not.toMatch(rawLeakagePattern);
}

async function expectNoDefaultVisibleAuthorityLeakage(page: Page) {
  await baseExpect(await readBodyText(page)).not.toMatch(consumerAuthorityLeakPattern);
}

async function expectRootNonEmpty(page: Page) {
  await baseExpect.poll(async () => page.locator('#root').evaluate((root) => root.textContent?.trim().length ?? 0)).toBeGreaterThan(0);
}

async function expectNoHorizontalOverflow(page: Page) {
  await baseExpect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function expectGuestPreviewSurface(page: Page) {
  await appExpect(page).toHaveURL(/\/(zh|en)?\/guest$/);
  const guestSurface = page.getByTestId('guest-home-clean-search');
  await appExpect(guestSurface).toBeVisible({ timeout: 15_000 });
  await appExpect(page.getByTestId('guest-home-command-surface')).toBeVisible();
  await appExpect(page.getByTestId('guest-home-command-workflow')).toContainText(/搜索|Search/);
  await appExpect(guestSurface).toContainText(/股票研究工作区|stock research workspace/i);
  await appExpect(page.getByTestId('guest-home-market-preview-strip')).toContainText(/当前市场观察|Current market observation/);
  await appExpect(page.getByTestId('guest-home-preview-strip')).toContainText(/登录后可用|Available after sign-in/);
  await appExpect(page.getByTestId('guest-home-registration-link')).toBeVisible();
  await expectNoGenericServerErrorShell(page);
  await expectNoVisibleRawLeakage(page);
  await baseExpect(await guestSurface.innerText()).not.toMatch(guestLandingForbiddenTradingPattern);
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
          summary: '市场宽度对流动性读数形成支撑。',
          updated_at: '2026-05-09T10:30:00+08:00',
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

function optionsSummaryPayload(symbol: string) {
  return {
    symbol,
    market: 'us',
    underlying: {
      price: 52.34,
      change_pct: 1.2,
      source: 'ux_audit_fixture',
      as_of: '2026-05-06T09:45:00-04:00',
      freshness: 'mock',
    },
    options_availability: {
      supported: true,
      provider: 'ux_audit_fixture',
      limitations: ['mocked_product_route_harness'],
    },
    metadata: {
      read_only: true,
      no_external_calls_in_tests: true,
      limitations: ['mocked_playwright_product_auth'],
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
        source: 'ux_audit_fixture',
        warnings: ['mocked_chain'],
      },
    ],
    metadata: {
      read_only: true,
      no_external_calls_in_tests: true,
      limitations: ['mocked_playwright_product_auth'],
      source_label: 'Playwright Fixture',
      updated_at: '2026-05-06T09:45:00-04:00',
    },
  };
}

function optionsChainPayload(symbol: string) {
  return {
    symbol,
    expiration: '2026-06-19',
    underlying: {
      price: 52.34,
      change_pct: 1.2,
      source: 'ux_audit_fixture',
      as_of: '2026-05-06T09:45:00-04:00',
      freshness: 'mock',
    },
    calls: [
      {
        contract_symbol: `${symbol}260619C00055000`,
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
        contract_symbol: `${symbol}260619P00050000`,
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
    chain_as_of: '2026-05-06T09:45:00-04:00',
    source: 'ux_audit_fixture',
    limitations: ['mocked_chain'],
    metadata: {
      read_only: true,
      no_external_calls_in_tests: true,
      limitations: ['mocked_playwright_product_auth'],
      source_label: 'Playwright Fixture',
      updated_at: '2026-05-06T09:45:00-04:00',
    },
  };
}

function optionsStrategyComparisonPayload(symbol: string) {
  return {
    symbol,
    underlying: {
      price: 52.34,
      change_pct: 1.2,
      source: 'ux_audit_fixture',
      as_of: '2026-05-06T09:45:00-04:00',
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
            contract_symbol: `${symbol}260619C00055000`,
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
      strategy_engine: 'ux_audit_fixture',
      force_refresh_ignored: true,
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
      source_type: 'ux_audit_fixture',
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
    better_alternative: {
      strategy_type: 'bull_call_spread',
      reason: 'Defined-risk structure remains easier to bound in mocked verification.',
      max_loss: 230,
      risk_reward_ratio: 2.17,
    },
    no_advice_disclosure: 'Scenario analysis only; not personalized financial advice.',
    freshness: {
      source: 'ux_audit_fixture',
      freshness: 'mock',
      as_of: '2026-05-06T09:45:00-04:00',
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
      strategy_engine: 'ux_audit_fixture',
      force_refresh_ignored: true,
    },
  };
}

async function installOptionsLabMocks(page: Page, calls: string[]) {
  await page.route('**/api/v1/options/underlyings/*/summary', async (route) => {
    const path = new URL(route.request().url()).pathname;
    calls.push(`GET ${path}`);
    const symbol = decodeURIComponent(path.split('/')[5] || 'TEM').toUpperCase();
    await fulfillJson(route, optionsSummaryPayload(symbol));
  });
  await page.route('**/api/v1/options/underlyings/*/expirations', async (route) => {
    const path = new URL(route.request().url()).pathname;
    calls.push(`GET ${path}`);
    const symbol = decodeURIComponent(path.split('/')[5] || 'TEM').toUpperCase();
    await fulfillJson(route, optionsExpirationsPayload(symbol));
  });
  await page.route('**/api/v1/options/underlyings/*/chain**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    calls.push(`GET ${path}`);
    const symbol = decodeURIComponent(path.split('/')[5] || 'TEM').toUpperCase();
    await fulfillJson(route, optionsChainPayload(symbol));
  });
  await page.route('**/api/v1/options/strategies/compare', async (route) => {
    calls.push('POST /api/v1/options/strategies/compare');
    await fulfillJson(route, optionsStrategyComparisonPayload('TEM'));
  });
  await page.route('**/api/v1/options/decision/evaluate', async (route) => {
    calls.push('POST /api/v1/options/decision/evaluate');
    await fulfillJson(route, optionsDecisionPayload('TEM'));
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

async function installProviderOpsMocks(page: Page) {
  await page.route('**/api/v1/admin/providers/operations-matrix**', (route) => fulfillJson(route, providerOperationsMatrixPayload()));
  await page.route('**/api/v1/market/data-readiness**', (route) => fulfillJson(route, marketDataReadinessPayload()));
  await page.route('**/api/v1/admin/market-providers/operations**', (route) => fulfillJson(route, marketProviderOperationsPayload()));
}

function adminLogStoragePayload() {
  return {
    total_log_count: 12,
    total_event_count: 34,
    oldest_log_timestamp: '2026-05-01T10:30:00+08:00',
    newest_log_timestamp: '2026-06-05T10:30:00+08:00',
    retention_days: 90,
    minimum_retention_days: 7,
    retention_cutoff: '2026-03-07T10:30:00+08:00',
    logs_older_than_retention_count: 0,
    storage_size_bytes: 1048576,
    storage_size_label: '1 MB',
    storage_size_available: true,
    measurement_scope: 'sqlite_database_file',
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

function adminLogBusinessEventsPayload() {
  return {
    total: 1,
    limit: 20,
    offset: 0,
    has_more: false,
    health_summary: {
      total_events: 1,
      failed_events: 0,
      warning_events: 1,
      slow_events: 0,
      failure_rate: 0,
      status: 'warning',
      failures_by_category: [],
      failures_by_provider: [],
      failures_by_reason: [],
      top_recent_errors: [],
      actor_breakdown: [{ key: 'admin', label: 'admin', count: 1 }],
      latest_critical_error: null,
    },
    items: [
      {
        id: 'evt-provider-rollup',
        event: 'Provider Issue Rollup',
        category: 'data_source',
        type: 'system_operation',
        event_type: 'SystemOperation',
        status: 'partial',
        summary: 'Primary provider failed, fallback source served cached data',
        context_label: 'Market provider diagnostics',
        provider: 'mock-provider',
        source: 'raw English cache',
        reason: 'provider unavailable',
        error_summary: 'provider timeout',
        request_id: 'req-provider-rollup',
        trace_id: 'trace-provider-rollup',
        step_trace_available: false,
        started_at: '2026-06-05T10:30:00+08:00',
        duration_ms: 320,
        step_count: 1,
        success_step_count: 0,
        failed_step_count: 0,
        skipped_step_count: 0,
        unknown_step_count: 1,
      },
    ],
  };
}

function adminLogDataMissingPayload() {
  return {
    total: 1,
    items: [
      {
        affected_surface: 'Market Overview',
        symbol: 'SPX',
        market: 'US',
        missing_domain: 'sentiment',
        provider: 'mock-provider',
        source: 'raw English cache',
        freshness_status: 'stale',
        fallback_used: true,
        stale: true,
        partial: true,
        reason_code: 'provider unavailable',
        latest_seen_at: '2026-06-05T10:30:00+08:00',
        count: 1,
        sample_event_ids: ['evt-provider-rollup'],
        sample_session_ids: ['session-provider-rollup'],
        sample_business_event_ids: ['evt-provider-rollup'],
      },
    ],
  };
}

function adminLogOperatorIssueRollupPayload() {
  return {
    total: 1,
    items: [
      {
        issue_id: 'provider-issue-rollup',
        issue_class: 'operator_issue',
        issue_title: 'Provider Issue Rollup',
        severity: 'warning',
        count: 1,
        latest_timestamp: '2026-06-05T10:30:00+08:00',
        first_timestamp: '2026-06-05T10:00:00+08:00',
        sample_event_ids: ['evt-provider-rollup'],
        affected_surfaces: ['Market Overview'],
        affected_domains: ['sentiment'],
        provider: 'mock-provider',
        source: 'raw English cache',
        model: null,
        channel: null,
        reason_code: 'provider unavailable',
        event_type: 'SystemOperation',
        freshness_status: 'stale',
        status: 'fallback',
        operator_guidance: 'provider unavailable / fallback / stale / timeout / partial / raw English cache',
      },
    ],
  };
}

function adminLogSessionsPayload() {
  return {
    total: 1,
    summary: { error_count: 0, warning_count: 1, data_source_failure_count: 1, slow_request_count: 0 },
    items: [
      {
        session_id: 'session-provider-rollup',
        code: 'SPX',
        name: 'Provider Issue Rollup',
        overall_status: 'partial_success',
        truth_level: 'recorded',
        started_at: '2026-06-05T10:30:00+08:00',
        ended_at: '2026-06-05T10:31:00+08:00',
        readable_summary: {
          actor_display: 'admin',
          actor_role: 'admin',
          subsystem: 'market',
          operation_category: 'system_operation',
          operation_type: 'Provider Issue Rollup',
          operation_target: 'Market Overview',
          operation_status: 'partial',
          top_failure_reason: 'provider unavailable',
          summary_paragraph: 'Primary provider timeout, fallback source completed.',
        },
      },
    ],
  };
}

async function installAdminLogsMocks(page: Page) {
  await page.route('**/api/v1/admin/logs/storage/summary**', (route) => fulfillJson(route, adminLogStoragePayload()));
  await page.route('**/api/v1/admin/logs/data-missing-drilldown**', (route) => fulfillJson(route, adminLogDataMissingPayload()));
  await page.route('**/api/v1/admin/logs/operator-issue-rollup**', (route) => fulfillJson(route, adminLogOperatorIssueRollupPayload()));
  await page.route('**/api/v1/admin/logs/sessions**', (route) => fulfillJson(route, adminLogSessionsPayload()));
  await page.route('**/api/v1/admin/logs**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/admin/logs') {
      await fulfillJson(route, adminLogBusinessEventsPayload());
      return;
    }
    await route.fallback();
  });
}

appTest.describe('UX audit P0 route smoke', () => {
  appTest('consumer short aliases resolve to canonical surfaces without 404 fallback', async ({ page }) => {
    const publicAliases = [
      { path: '/zh/liquidity', canonical: /\/zh\/market\/liquidity-monitor$/, ready: () => page.getByRole('heading', { name: /流动性监测|Liquidity Monitor/i }) },
      { path: '/en/liquidity', canonical: /\/en\/market\/liquidity-monitor$/, ready: () => page.getByRole('heading', { name: /流动性监测|Liquidity Monitor/i }) },
      { path: '/zh/rotation', canonical: /\/zh\/market\/rotation-radar$/, ready: () => page.getByTestId('market-rotation-radar-page') },
      { path: '/en/rotation', canonical: /\/en\/market\/rotation-radar$/, ready: () => page.getByTestId('market-rotation-radar-page') },
    ] as const;

    await page.setViewportSize(desktopViewport);

    for (const alias of publicAliases) {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      if (alias.path.includes('liquidity')) {
        await installLiquidityMonitorMock(page);
      }
      await page.goto(alias.path);
      await page.waitForLoadState('domcontentloaded');
      await appExpect(page).toHaveURL(alias.canonical);
      await appExpect(alias.ready()).toBeVisible({ timeout: 15_000 });
      await expectNoGenericServerErrorShell(page);
      await expectNoVisibleRawLeakage(page);
    }
  });

  appTest('Liquidity Monitor and Rotation Radar keep consumer-safe authority boundary copy on canonical routes', async ({ page }) => {
    const routeChecks = [
      {
        path: '/zh/market/liquidity-monitor',
        ready: () => page.getByTestId('liquidity-monitor-guidance-panel'),
        boundaryTitle: page.getByTestId('liquidity-monitor-consumer-details'),
        expandButton: () => page.getByRole('button', { name: '展开 数据说明与限制' }),
        expandedCopy: [
          '数据说明与限制',
          '本页把流动性作为研究背景展示；当关键信号缺失、延迟或暂不可用时，状态会自动降级。',
        ],
      },
      {
        path: '/zh/market/rotation-radar',
        ready: () => page.getByTestId('market-rotation-radar-page'),
        boundaryTitle: page.getByTestId('rotation-radar-mechanics-details'),
        expandButton: () => page.getByRole('button', { name: '展开 查看轮动说明' }),
        expandedCopy: [
          '查看轮动说明',
          '当前主题/行业/概念主要依赖相对强弱、观察项或局部样本，尚不能证明扩散与连续性同时成立。',
        ],
      },
    ] as const;

    await page.setViewportSize(desktopViewport);

    for (const routeCheck of routeChecks) {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await installUxDensityAuthenticatedSession(page);
      await installUxDensityPublicMocks(page);
      await page.goto(routeCheck.path);
      await page.waitForLoadState('domcontentloaded');

      await appExpect(routeCheck.ready()).toBeVisible({ timeout: 15_000 });
      await appExpect(routeCheck.boundaryTitle).toBeVisible();
      for (const copy of routeCheck.visibleCopy || []) {
        await appExpect(page.locator('body')).toContainText(copy);
      }
      await expectNoGenericServerErrorShell(page);
      await expectNoVisibleRawLeakage(page);
      await expectNoDefaultVisibleAuthorityLeakage(page);
      await expectNoHorizontalOverflow(page);

      await routeCheck.expandButton().click();
      for (const copy of routeCheck.expandedCopy) {
        await appExpect(page.locator('body')).toContainText(copy);
      }
    }
  });

  appTest('guest direct portfolio entry stays explicit and does not leak protected content', async ({ page }) => {
    await page.setViewportSize(desktopViewport);
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await installGuestAppSmokeSession(page);
    await page.goto('/zh/portfolio');
    await page.waitForLoadState('domcontentloaded');

    await appExpect(page).toHaveURL(/\/zh\/portfolio$/);
    await appExpect(page.getByTestId('auth-guard-overlay')).toBeVisible({ timeout: 15_000 });
    await appExpect(page.getByRole('heading', { name: /登录后即可进入|Sign in to continue/i })).toContainText(/持仓|Portfolio/i);
    baseExpect(await readBodyText(page)).not.toMatch(/总资产|当前持仓|组合只读总览/i);
    await expectNoVisibleRawLeakage(page);
  });

  appTest('guest direct admin alias entry stays explicit and does not leak protected content', async ({ page }) => {
    await page.setViewportSize(desktopViewport);
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await installGuestAppSmokeSession(page);
    await page.goto('/zh/admin/providers');
    await page.waitForLoadState('domcontentloaded');

    await expectGuestPreviewSurface(page);
    baseExpect(await readBodyText(page)).not.toMatch(/数据源运维|系统设置|Provider 熔断诊断/i);
  });

  appTest('guest canonical admin entries redirect to guest preview without leaking admin content', async ({ page }) => {
    const canonicalAdminEntries = [
      { path: '/zh/settings/system', forbidden: /系统设置|数据源运维|通知中心/i },
      { path: '/zh/admin/logs', forbidden: /管理员日志|数据源健康摘要|Provider Issue Rollup/i },
      { path: '/zh/admin/users/user-123/activity', forbidden: /用户支持与治理|活动类型筛选|不可查看用户活动/i },
    ] as const;

    await page.setViewportSize(desktopViewport);

    for (const entry of canonicalAdminEntries) {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await installGuestAppSmokeSession(page);
      await page.goto(entry.path);
      await page.waitForLoadState('domcontentloaded');

      await expectGuestPreviewSurface(page);
      baseExpect(await readBodyText(page)).not.toMatch(entry.forbidden);
    }
  });

  appTest('representative protected consumer routes keep same-route guest overlay behavior', async ({ page }) => {
    const protectedRoutes = [
      { path: '/zh/watchlist', expectedUrl: /\/zh\/watchlist$/, hiddenCopy: /先从扫描器加入候选，也可以在扫描器手动补充代码/i },
      { path: '/zh/scanner', expectedUrl: /\/zh\/scanner$/, hiddenCopy: /Mock scanner shortlist|NVIDIA|AI 半导体/i },
      { path: '/zh/backtest/results/34', expectedUrl: /\/zh\/backtest\/results\/34$/, hiddenCopy: /Fixture analytical backtest completed|回测结果|绩效表现/i },
    ] as const;

    await page.setViewportSize(desktopViewport);

    for (const route of protectedRoutes) {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await installGuestAppSmokeSession(page);
      await page.goto(route.path);
      await page.waitForLoadState('domcontentloaded');

      await appExpect(page).toHaveURL(route.expectedUrl);
      await appExpect(page.getByTestId('auth-guard-overlay')).toBeVisible({ timeout: 15_000 });
      baseExpect(await readBodyText(page)).not.toMatch(route.hiddenCopy);
      await expectNoVisibleRawLeakage(page);
      await expectNoGenericServerErrorShell(page);
    }
  });

  appTest('market overview, scanner, and backtest do not show a generic server-error shell under the mock harness', async ({ page }) => {
    const signedInRoutes = [
      { path: '/zh/market-overview', ready: () => page.getByTestId('market-overview-shell') },
      { path: '/zh/scanner', ready: () => page.getByTestId('user-scanner-workspace') },
      {
        path: '/zh/backtest',
        ready: () => page.getByTestId('backtest-bento-page'),
        boundary: () => page.getByTestId('backtest-research-boundary'),
      },
    ] as const;

    await page.setViewportSize(desktopViewport);

    for (const route of signedInRoutes) {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await installSignedInAppSmokeSession(page);
      await page.goto(route.path);
      await page.waitForLoadState('domcontentloaded');
      await appExpect(route.ready()).toBeVisible({ timeout: 15_000 });
      if ('boundary' in route) {
        await appExpect(route.boundary()).toContainText('本工具仅用于回测分析与学习研究');
        await appExpect(route.boundary()).toContainText('不构成投资建议');
        await appExpect(route.boundary()).toContainText('过往表现不代表未来收益');
      }
      await expectNoGenericServerErrorShell(page);
      await expectNoVisibleRawLeakage(page);
    }
  });
});

appTest.describe('UX audit P0 protected-route smoke', () => {
  appTest('consumer options aliases resolve to the canonical protected surface for signed-in users', async ({ page }) => {
    const aliases = [
      { path: '/zh/options', canonical: /\/zh\/options-lab$/ },
      { path: '/en/options', canonical: /\/en\/options-lab$/ },
    ] as const;

    await page.setViewportSize(desktopViewport);

    for (const alias of aliases) {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      const optionApiCalls: string[] = [];
      await installSignedInAppSmokeSession(page);
      await installOptionsLabMocks(page, optionApiCalls);
      await page.goto(alias.path);
      await page.waitForLoadState('domcontentloaded');
      await appExpect(page).toHaveURL(alias.canonical);
      await appExpect(page.getByTestId('options-lab-decision-engine')).toBeVisible({ timeout: 15_000 });
      baseExpect(optionApiCalls).toContain('GET /api/v1/options/underlyings/TEM/summary');
      await expectRootNonEmpty(page);
      await expectNoHorizontalOverflow(page);
      await expectNoVisibleRawLeakage(page);
    }
  });

  appTest('guest direct options alias entry stays explicit and does not leak product content', async ({ page }) => {
    await page.setViewportSize(desktopViewport);
    const optionApiCalls: string[] = [];
    await installGuestAppSmokeSession(page);
    await installOptionsLabMocks(page, optionApiCalls);

    await page.goto('/zh/options');
    await page.waitForLoadState('domcontentloaded');

    await appExpect(page).toHaveURL(/\/zh\/options-lab$/);
    const authGate = page.getByTestId('auth-guard-overlay');
    await appExpect(authGate).toBeVisible({ timeout: 15_000 });
    await appExpect(authGate).toHaveAttribute('data-boundary-family', 'consumer-protected');
    await appExpect(page.getByRole('dialog', { name: /期权实验室|Options Lab/i })).toBeVisible();
    await appExpect(page.getByTestId('auth-guard-capability')).toContainText(/期权实验室|Options Lab/i);
    await appExpect(page.getByTestId('auth-guard-status-pill')).toContainText(/需要登录|Sign-in required/i);
    await appExpect(page.getByTestId('auth-guard-reason')).toContainText(/请先登录后继续访问该页面|Sign in before continuing to this page/i);
    await appExpect(page.getByTestId('auth-guard-primary-action')).toHaveAttribute(
      'href',
      '/zh/login?redirect=%2Fzh%2Foptions-lab',
    );
    await appExpect(page.getByTestId('options-lab-decision-engine')).toHaveCount(0);
    baseExpect(optionApiCalls).toEqual([]);
    await expectRootNonEmpty(page);
    await expectNoHorizontalOverflow(page);
    await expectNoVisibleRawLeakage(page);
  });
});

adminTest.describe('UX audit P0 admin smoke', () => {
  adminTest('admin short aliases resolve to their canonical protected surfaces', async ({ page }) => {
    const aliases = [
      { path: '/zh/admin/system', canonical: /\/zh\/settings\/system$/, readyTestId: 'system-settings-page' },
      { path: '/zh/admin/providers', canonical: /\/zh\/admin\/market-providers$/, readyTestId: 'market-provider-operations-page' },
      { path: '/zh/admin/evidence', canonical: /\/zh\/admin\/evidence-workflow$/, readyTestId: 'admin-evidence-workflow-page' },
      { path: '/zh/admin/costs', canonical: /\/zh\/admin\/cost-observability$/, readyTestId: 'admin-cost-observability-page' },
      { path: '/zh/admin/ai', canonical: /\/zh\/settings\/system$/, readyTestId: 'system-settings-page' },
    ] as const;

    await page.setViewportSize(desktopViewport);

    for (const alias of aliases) {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await installAdminAuthHarness(page, { displayName: 'Bootstrap Admin' });
      if (alias.path === '/zh/admin/providers') {
        await installProviderOpsMocks(page);
      }
      await page.goto(alias.path);
      await page.waitForLoadState('domcontentloaded');
      await adminExpect(page).toHaveURL(alias.canonical);
      await adminExpect(page.getByTestId(alias.readyTestId)).toBeVisible({ timeout: 15_000 });
      await expectNoAdminHorizontalOverflow(page);
      await expectNoRawSecretLikeText(page);
      await expectNoGenericServerErrorShell(page);
    }
  });

  adminTest('admin logs default-visible copy stays operator-safe after the audit fixes', async ({ page }) => {
    await page.setViewportSize(desktopViewport);
    await installAdminAuthHarness(page, { displayName: 'Bootstrap Admin' });
    await installAdminLogsMocks(page);

    await page.goto('/zh/admin/logs');
    await page.waitForLoadState('domcontentloaded');

    await adminExpect(page.getByTestId('admin-logs-page-shell')).toBeVisible({ timeout: 15_000 });
    await adminExpect(page.getByTestId('admin-logs-operator-issue-rollup')).toBeVisible();
    await adminExpect(page.getByRole('heading', { name: '数据源健康摘要' })).toBeVisible();
    baseExpect(await readBodyText(page)).not.toMatch(adminLogsEnglishDegradedPattern);
    await expectNoRawSecretLikeText(page);
    await expectNoGenericServerErrorShell(page);
  });

  adminTest('system settings default-visible copy stays token-safe and factory reset requires a confirmation step', async ({ page }) => {
    await page.setViewportSize(desktopViewport);
    const harness = await openAdminRouteWithHarness(page, '/zh/settings/system');

    await adminExpect(page.getByTestId('system-settings-page')).toBeVisible({ timeout: 15_000 });
    baseExpect(await readBodyText(page)).not.toMatch(/\btoken\b/i);
    await page.getByTestId('system-danger-zone').evaluate((node) => {
      (node as HTMLDetailsElement).open = true;
    });
    await adminExpect(page.getByRole('button', { name: '执行工厂重置' })).toBeVisible();

    await page.getByRole('button', { name: '执行工厂重置' }).click();

    await adminExpect(page.getByRole('heading', { name: '确认重置系统设置' })).toBeVisible();
    baseExpect(harness.requests.wasFetched('POST', '/api/v1/system/actions/factory-reset')).toBe(false);
    await expectNoRawSecretLikeText(page);
  });

  adminTest('system settings header reset requires an explicit confirmation step', async ({ page }) => {
    await page.setViewportSize(desktopViewport);
    const harness = await openAdminRouteWithHarness(page, '/zh/settings/system');
    const headerResetButton = page.getByTestId('settings-main-content').getByRole('button', { name: '重置', exact: true });

    await adminExpect(page.getByTestId('system-settings-page')).toBeVisible({ timeout: 15_000 });

    await headerResetButton.click();
    await adminExpect(page.getByRole('heading', { name: '确认重置？' })).toBeVisible();
    await adminExpect(page.getByText('所有未保存更改将丢失。')).toBeVisible();
    await page.getByRole('button', { name: '取消' }).last().click();

    baseExpect(harness.requests.wasFetched('PUT', '/api/v1/system/config')).toBe(false);

    await headerResetButton.click();
    await page.getByRole('button', { name: '确认重置' }).click();

    await adminExpect(page.getByRole('button', { name: /^保存配置$/ })).toBeVisible();
    baseExpect(harness.requests.wasFetched('PUT', '/api/v1/system/config')).toBe(false);
    await adminExpect(page.getByTestId('system-settings-page')).toBeVisible();
    await expectNoRawSecretLikeText(page);
  });

  adminTest('user activity route denies nested admin access without the activity capability', async ({ page }) => {
    await page.setViewportSize(desktopViewport);

    await page.unrouteAll({ behavior: 'ignoreErrors' });
    const deniedHarness = await installAdminAuthHarness(page, {
      capabilities: ['users:read'],
      displayName: 'Scoped Admin',
    });
    await page.goto('/zh/admin/users/user-123/activity');
    await page.waitForLoadState('domcontentloaded');

    await adminExpect(page).toHaveURL(/\/zh\/admin\/users\/user-123\/activity$/);
    await adminExpect(page.getByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeVisible({ timeout: 15_000 });
    baseExpect(deniedHarness.requests.count('GET', '/api/v1/admin/users/user-123/activity')).toBe(0);
    baseExpect(deniedHarness.requests.count('GET', '/api/v1/admin/users/user-123')).toBe(0);
    await expectNoRawSecretLikeText(page);
    await expectNoGenericServerErrorShell(page);
  });
});
