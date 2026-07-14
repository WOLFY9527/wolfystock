import type { Page, Route } from '@playwright/test';
import { expect as appExpect, test as appTest } from './fixtures/appSmoke';
import { expect as adminExpect, installAdminAuthHarness, test as adminTest } from './fixtures/adminAuth';

const productRoutes = [
  { path: '/zh/scanner', canonical: '/zh/scanner', marker: 'scanner-ranking-board-page' },
  { path: '/zh/watchlist', canonical: '/zh/watchlist', marker: 'watchlist-page' },
  { path: '/zh/portfolio', canonical: '/zh/portfolio', marker: 'portfolio-bento-page' },
  { path: '/zh/options-lab', canonical: '/zh/options-lab', marker: 'options-lab-page-root' },
  { path: '/zh/market-overview', canonical: '/zh/market-overview', marker: 'market-overview-shell' },
  { path: '/zh/market/liquidity-monitor', canonical: '/zh/market/liquidity-monitor', marker: 'liquidity-monitor-guidance-panel' },
  { path: '/zh/market/rotation-radar', canonical: '/zh/market/rotation-radar', marker: 'market-rotation-radar-page' },
  { path: '/zh/backtest/compare', canonical: '/zh/backtest/compare', marker: 'rule-backtest-compare-page' },
] as const;

const productAliasRoutes = [
  { path: '/zh/cockpit', canonical: '/zh/market/decision-cockpit', marker: 'market-decision-cockpit-page' },
  { path: '/zh/research-radar', canonical: '/zh/research/radar', marker: 'research-radar-page' },
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

function portfolioStructureReviewPayload() {
  return {
    schema_version: 'portfolio_structure_review_v1',
    aggregate_summary: {
      as_of: '2026-05-06',
      account_count: 1,
      holding_count: 1,
      evaluated_count: 1,
      largest_holding: { ticker: 'AAPL', percent: 100 },
    },
    exposure_by_theme_or_sector: [
      {
        key: 'technology',
        label: 'Technology',
        market_value: 600,
        percent: 100,
        holding_count: 1,
      },
    ],
    counts_by_structure_state: { mixed: 1 },
    holdings_structure: [
      {
        ticker: 'AAPL',
        structure_state: 'mixed',
        confidence: 'medium',
        evidence_quality: { score: 70, status: 'partial' },
        risk_flags: [],
        research_notes: {
          watch_next: ['Review structure after the next close.'],
          needs_more_evidence: [],
          risk_flags: [],
        },
        missing_evidence: [],
      },
    ],
    strongest_structures: [],
    weakest_evidence: [],
    common_risk_flags: [],
    missing_evidence: [],
    data_quality: {
      status: 'partial',
      holding_metadata_status: 'available',
      structure_evidence_status: 'partial',
      read_only: true,
      fail_closed: false,
    },
    no_advice_disclosure: 'Research context only.',
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

function marketDecisionCockpitPayload() {
  return {
    schema_version: 'market_decision_cockpit.v1',
    generated_at: '2026-06-15T09:30:00Z',
    market_regime_decision: {
      regime: 'risk_on',
      confidence: 'medium',
      driver_scores: {
        breadth_participation: {
          score: 62,
          evidence_state: 'partial',
          reasons: ['Breadth requires continued confirmation.'],
        },
      },
      explanation: {
        why_this_regime: ['Breadth participation is improving.'],
        what_confirms_it: ['Cross-asset pressure remains contained.'],
      },
      invalidation_conditions: ['Breadth weakens quickly.'],
      research_priorities: {
        watch_today: ['Breadth participation'],
        needs_more_evidence: ['Options chain coverage'],
        investigate_next: ['Research queue'],
      },
    },
    research_queue_preview: {
      top_candidates: [
        {
          ticker: 'ALFA',
          priority: 'high',
          research_bias: 'strength_continuation',
          why_on_radar: ['Relative strength is improving.'],
        },
      ],
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
      what_changed: ['Breadth improved.'],
      what_to_watch: ['Follow-through confirmation.'],
      confidence_limits: ['Options evidence unavailable.'],
    },
    no_advice_disclosure: 'Research context only.',
    data_quality: { status: 'partial' },
  };
}

function dailyIntelligencePayload() {
  return {
    schema_version: 'daily_intelligence_briefing_v1',
    generated_at: '2026-06-15T09:30:00Z',
    briefing_date: '2026-06-15',
    session_label: 'pre_market',
    market_regime_summary: {
      regime: 'risk_on',
      confidence: 'medium',
      summary: 'Breadth and liquidity remain supportive for observation.',
      supporting_observations: ['Breadth remains stable.'],
      invalidation_observations: ['Breadth contraction would weaken the frame.'],
    },
    what_changed: ['Research queue leans toward relative strength follow-through.'],
    section_links: [
      {
        label: 'Research Radar',
        route: '/research/radar',
        section: 'topResearchPriorities',
        reason: 'research_queue_origin',
      },
      {
        label: 'Scanner',
        route: '/scanner',
        section: 'scannerHighlights',
        reason: 'scanner_candidates_origin',
      },
    ],
    top_research_priorities: [
      {
        label: 'ALFA research queue',
        source: 'research_radar',
        priority: 'high',
        ticker: 'ALFA',
        observations: ['Relative strength is improving.'],
        what_to_verify: ['Confirm follow-through.'],
        evidence_gaps: [],
        evidence_links: [
          {
            label: 'Research Radar',
            route: '/research/radar',
            section: 'topResearchPriorities',
            reason: 'research_queue_origin',
          },
        ],
      },
    ],
    scanner_highlights: [],
    watchlist_highlights: [],
    portfolio_structure_highlights: [],
    scenario_risks: [],
    evidence_gaps: [],
    degraded_inputs: [],
    observation_only: true,
    decision_grade: false,
  };
}

function researchRadarPayload() {
  return {
    schema_version: 'research_radar_api_v1',
    generated_at: '2026-06-15T09:30:00Z',
    research_queue: [
      {
        ticker: 'ALFA',
        priority: 'medium',
        research_bias: 'strength_continuation',
        driver_scores: { relative_strength: 70 },
        why_on_radar: ['Relative strength is improving.'],
        what_to_verify: ['Confirm follow-through.'],
        invalidation_observations: ['Strength fades.'],
        risk_flags: [],
      },
    ],
    aggregate_summary: {
      queue_quality: 'mixed',
      priority_counts: { medium: 1 },
    },
    evidence_gaps: [],
    market_context_fit: 'neutral',
    no_advice_disclosure: 'Research queue only.',
    data_quality: { status: 'partial' },
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
  await page.route('**/api/v1/portfolio/structure-review**', (route) => fulfillJson(route, portfolioStructureReviewPayload()));
  await page.route('**/api/v1/options/underlyings/*/summary', (route) => fulfillJson(route, optionsSummaryPayload(symbolFromOptionsRequest(route))));
  await page.route('**/api/v1/options/underlyings/*/expirations', (route) => fulfillJson(route, optionsExpirationsPayload(symbolFromOptionsRequest(route))));
  await page.route('**/api/v1/options/underlyings/*/chain**', (route) => fulfillJson(route, optionsChainPayload(symbolFromOptionsRequest(route))));
  await page.route('**/api/v1/options/strategies/compare', (route) => fulfillJson(route, optionsStrategyComparisonPayload('TEM')));
  await page.route('**/api/v1/options/decision/evaluate', (route) => fulfillJson(route, optionsDecisionPayload('TEM')));
}

async function installResearchIaMocks(page: Page) {
  await page.route('**/api/v1/market/decision-cockpit**', (route) => fulfillJson(route, marketDecisionCockpitPayload()));
  await page.route('**/api/v1/market/daily-intelligence**', (route) => fulfillJson(route, dailyIntelligencePayload()));
  await page.route('**/api/v1/research/radar**', (route) => fulfillJson(route, researchRadarPayload()));
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

function adminLogHealthSummary() {
  return {
    total_events: 1,
    failed_events: 0,
    warning_events: 0,
    slow_events: 0,
    failure_rate: 0,
    status: 'ok',
    failures_by_category: [],
    failures_by_provider: [],
    failures_by_reason: [],
    top_recent_errors: [],
    actor_breakdown: [{ key: 'admin', label: 'admin', count: 1 }],
    latest_critical_error: null,
  };
}

function adminLogBusinessEventsPayload() {
  return {
    total: 1,
    limit: 20,
    offset: 0,
    has_more: false,
    health_summary: adminLogHealthSummary(),
    items: [
      {
        id: 'route-canonicalization-admin-log',
        event: 'RouteCanonicalization',
        category: 'ops',
        type: 'admin_route_alias_smoke',
        event_type: 'admin_route_alias_smoke',
        status: 'success',
        summary: 'Admin system logs alias smoke fixture',
        actor_type: 'admin',
        actor_label: 'playwright-admin',
        context_label: 'admin-system-logs-alias',
        provider: null,
        source: 'playwright',
        reason: null,
        error_summary: null,
        request_id: 'req-admin-system-logs-alias',
        trace_id: 'trace-admin-system-logs-alias',
        root_cause_summary: null,
        step_trace_available: false,
        started_at: '2026-06-05T00:00:00Z',
        duration_ms: 12,
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
    total_log_count: 1,
    total_event_count: 1,
    oldest_log_timestamp: '2026-06-05T00:00:00Z',
    newest_log_timestamp: '2026-06-05T00:00:00Z',
    retention_days: 90,
    minimum_retention_days: 7,
    retention_cutoff: '2026-03-07T00:00:00Z',
    logs_older_than_retention_count: 0,
    storage_size_bytes: 512,
    storage_size_label: '512 B',
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

function adminLogSessionsPayload() {
  return {
    total: 1,
    summary: {
      error_count: 0,
      warning_count: 0,
      data_source_failure_count: 0,
      slow_request_count: 0,
      health_summary: adminLogHealthSummary(),
    },
    items: [
      {
        session_id: 'route-canonicalization-session',
        code: 'ADMIN',
        name: 'Admin system logs alias session',
        overall_status: 'success',
        truth_level: 'recorded',
        started_at: '2026-06-05T00:00:00Z',
        ended_at: '2026-06-05T00:00:00Z',
        readable_summary: {
          actor_display: 'playwright-admin',
          actor_role: 'admin',
          subsystem: 'ops',
          operation_category: 'route_alias_smoke',
          operation_type: 'system logs alias',
          operation_target: 'admin logs',
          operation_status: 'success',
          top_failure_reason: null,
          summary_paragraph: 'Admin system logs alias fixture.',
        },
      },
    ],
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

async function installAdminLogsMocks(page: Page) {
  await page.route('**/api/v1/admin/logs**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === 'POST') {
      return fulfillJson(route, {
        mode: 'retention',
        dry_run: true,
        matched_log_count: 0,
        matched_event_count: 0,
        deleted_log_count: 0,
        deleted_event_count: 0,
        additional_cleanup_needed: false,
      });
    }
    if (path === '/api/v1/admin/logs/storage/summary') {
      return fulfillJson(route, adminLogStoragePayload());
    }
    if (path === '/api/v1/admin/logs/sessions') {
      return fulfillJson(route, adminLogSessionsPayload());
    }
    return fulfillJson(route, adminLogBusinessEventsPayload());
  });
}

function expectCanonicalPath(page: Page, canonicalPath: string) {
  return appExpect.poll(() => new URL(page.url()).pathname).toBe(canonicalPath);
}

appTest.describe('viewport route canonicalization smoke', () => {
  for (const routeCheck of productRoutes) {
    appTest(`${routeCheck.path} stays canonical`, async ({ page }) => {
        await installSignedInProductSession(page);
        await installProductRouteApiMocks(page);
        await installLiquidityMonitorMock(page);

        await page.goto(routeCheck.path);
        await page.waitForLoadState('domcontentloaded');

        await expectCanonicalPath(page, routeCheck.canonical);
        await appExpect(page.getByTestId(routeCheck.marker)).toBeVisible({ timeout: 15_000 });
    });
  }
});

appTest.describe('viewport route legacy alias canonicalization smoke', () => {
  for (const routeCheck of productAliasRoutes) {
    appTest(`${routeCheck.path} redirects to ${routeCheck.canonical}`, async ({ page }) => {
        await installSignedInProductSession(page);
        await installProductRouteApiMocks(page);
        await installResearchIaMocks(page);

        await page.goto(routeCheck.path);
        await page.waitForLoadState('domcontentloaded');

        await expectCanonicalPath(page, routeCheck.canonical);
        await appExpect(page.getByTestId(routeCheck.marker)).toBeVisible({ timeout: 15_000 });
        await appExpect(page.getByTestId('scenario-lab-page')).toHaveCount(0);
    });
  }
});

adminTest.describe('viewport route alias canonicalization smoke', () => {
  adminTest('keeps expected admin provider alias stable', async ({ page }) => {
      await installAdminAuthHarness(page);
      await installProviderOpsMocks(page);

      await page.goto('/zh/admin/providers');
      await page.waitForLoadState('domcontentloaded');

      await adminExpect.poll(() => new URL(page.url()).pathname).toBe('/zh/admin/market-providers');
      await adminExpect(page.getByTestId('market-provider-operations-page')).toBeVisible({ timeout: 15_000 });
  });

  adminTest('redirects admin system logs alias to logs workspace', async ({ page }) => {
      await installAdminAuthHarness(page);
      await installAdminLogsMocks(page);

      await page.goto('/zh/admin/system-logs');
      await page.waitForLoadState('domcontentloaded');

      await adminExpect.poll(() => new URL(page.url()).pathname).toBe('/zh/admin/logs');
      await adminExpect(page.getByTestId('admin-logs-workspace')).toBeVisible({ timeout: 15_000 });
  });
});
