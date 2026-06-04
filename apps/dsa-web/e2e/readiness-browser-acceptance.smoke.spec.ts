import { expect, type Page, type Route } from '@playwright/test';
import { expect as appExpect, test as appTest } from './fixtures/appSmoke';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
] as const;

const rawLeakPattern = /raw|debug|provider|schema|payload|trace|internal/i;
const tradingPattern = /buy|sell|order|trade|broker|买入|卖出|下单|交易|券商/i;
const safeVerdictPattern = /研究证据可用|仅观察|证据不足|等待证据更新|Research-ready|Observe only|Evidence insufficient|Waiting/i;
const internalEvidenceCoveragePattern =
  /provider_timeout|sourceauthority|source_authority|fallbackorproxy|fallback_or_proxy|router|cache|credential|providerroute|partial_coverage|coverage_not_assembled|env/i;
const optionsGateSummaryLeakPattern =
  /raw|internal|debug|provider|cache|router|env|sourceAuthority|providerRoute|provider_timeout/i;
const forbiddenUnsafeTradingPattern =
  /买入按钮|立即交易|必买|稳赚|保证收益|guaranteed|best contract|AI recommends you buy|must buy|must sell|buy now|sell now|place order|you should buy|you should sell/i;

const optionsReadinessSummaryFixture = {
  options_research_ready: false,
  readiness_state: 'blocked',
  data_quality_tier: 'synthetic_demo_only',
  decision_grade: false,
  provider_authority: 'observationOnly',
  liquidity_gate: 'manual_review',
  iv_greeks_gate: 'blocked',
  spread_gate: 'manual_review',
  scenario_coverage: 'strategy_compare_ready',
  no_trading_boundary: {
    analytical_only: true,
    no_broker_execution: true,
    no_order_placement: true,
    no_portfolio_mutation: true,
    no_trading_recommendation: true,
  },
  blocking_reasons: [
    'provider_authority_tier_observation_only',
    'missing_greeks',
    'wide_bid_ask_spread',
    'synthetic_demo_only',
  ],
  next_evidence_needed: [
    '补齐 provider authority 佐证',
    '补齐 Greeks',
    '补齐 OI/成交量与更紧价差',
  ],
};

const signedInUser = {
  id: 'user-1',
  username: 'wolfy-user',
  displayName: 'Wolfy User',
  role: 'user',
  isAdmin: false,
  isAuthenticated: true,
  transitional: false,
  authEnabled: true,
};

type ProductRouteHarness = {
  requests: {
    count: (method: string, path: string) => number;
  };
};

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function expectNoHorizontalOverflow(page: Page) {
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function expectRootNonEmpty(page: Page) {
  await expect.poll(async () => page.locator('#root').evaluate((root) => root.textContent?.trim().length ?? 0)).toBeGreaterThan(0);
}

async function expectForbiddenTradingWordingAbsent(page: Page) {
  const text = (await page.locator('body').innerText())
    .replaceAll('不构成交易指令', '')
    .replaceAll('不构成下单指令', '')
    .replaceAll('不构成交易或下单指令', '')
    .replaceAll('不构成交易/下单指令', '')
    .replaceAll('仅做只读情景分析，不构成交易或下单指令。', '')
    .replaceAll('控制区只记录假设；数据是否可判断以后续准备度和风险边界为准，不构成交易或下单指令。', '')
    .replaceAll('仅反映当前期权链的 IV / 行权价点位绘制，仅反映快照形状，不延伸为交易结论。', '')
    .replaceAll('仅做只读情景分析，不构成交易或下单指令。', '');
  expect(text).not.toMatch(forbiddenUnsafeTradingPattern);
}

async function installSignedInHomeRoutes(page: Page) {
  await page.route('**/api/v1/auth/status**', async (route) => {
    await fulfillJson(route, {
      authEnabled: true,
      loggedIn: true,
      passwordSet: true,
      passwordChangeable: true,
      setupState: 'enabled',
      currentUser: signedInUser,
    });
  });

  await page.route('**/api/v1/auth/me**', async (route) => {
    await fulfillJson(route, signedInUser);
  });

  await page.route('**/api/v1/stocks/*/evidence**', async (route) => {
    await fulfillJson(route, {
      symbols: ['ORCL'],
      items: [
        {
          symbol: 'ORCL',
          market: 'US',
          stock_evidence_packet: {
            schema_version: 'stock_evidence_packet_v1',
            not_investment_advice: true,
            observation_only: true,
            fundamentals_summary: {
              market_cap: 512300000000,
              period: 'TTM',
              source: 'financial_digest',
              freshness: 'partial',
              missing_fields: ['pe_ttm', 'pb', 'roe', 'roa'],
              not_investment_advice: true,
              observation_only: true,
              score_contribution_allowed: false,
              source_authority_allowed: false,
            },
          },
        },
      ],
      meta: {
        generated_at: '2026-06-02T00:00:00Z',
        source: 'read_only_evidence_v2',
      },
    });
  });

  await page.route('**/api/v1/stocks/ORCL/history**', async (route) => {
    await fulfillJson(route, {
      stock_code: 'ORCL',
      stock_name: 'Oracle',
      period: 'daily',
      source: 'fixture_history',
      source_confidence: {
        source: 'fixture_history',
        source_label: '本地审核样例',
        as_of: '2026-06-02T00:00:00Z',
        freshness: 'available',
        is_fallback: false,
        is_stale: false,
        is_partial: false,
        is_synthetic: false,
        is_unavailable: false,
        confidence_weight: 1,
        coverage: 1,
      },
      data: [
        { date: '2026-05-27', open: 120.0, high: 121.2, low: 119.4, close: 120.8, volume: 8100000, change_percent: 0.7 },
        { date: '2026-05-28', open: 120.9, high: 122.4, low: 120.1, close: 121.7, volume: 7900000, change_percent: 0.74 },
        { date: '2026-05-29', open: 121.8, high: 123.1, low: 121.0, close: 122.2, volume: 8400000, change_percent: 0.41 },
        { date: '2026-05-30', open: 122.0, high: 123.6, low: 121.4, close: 123.1, volume: 8600000, change_percent: 0.74 },
        { date: '2026-06-02', open: 123.2, high: 124.1, low: 122.7, close: 123.8, volume: 8050000, change_percent: 0.57 },
      ],
    });
  });

  await page.route('**/api/v1/history/3**', async (route) => {
    await fulfillJson(route, {
      meta: {
        id: 3,
        queryId: 'q3',
        stockCode: 'ORCL',
        stockName: 'Oracle',
        companyName: 'Oracle',
        reportType: 'detailed',
        createdAt: '2026-04-27T08:00:00Z',
        reportGeneratedAt: '2026-04-27T08:03:00Z',
        currentPrice: 130.2,
        changePct: -0.4,
        modelUsed: 'fixture-model',
        isTest: true,
      },
      summary: {
        analysisSummary: 'Oracle is holding its post-earnings platform.',
        operationAdvice: 'Wait for a controlled pullback before adding.',
        trendPrediction: 'Constructive for the next 72 hours.',
        sentimentScore: 78,
        sentimentLabel: 'Bullish',
      },
      strategy: {
        idealBuy: '121.80 - 124.60',
        stopLoss: '117.40',
        takeProfit: '133.50',
      },
      details: {
        dataQualityReport: {
          dataQualityTier: 'analysis_grade',
          dataQualityScore: 68,
          requiredAvailable: true,
          importantMissing: ['fundamentals.eps'],
          optionalMissing: ['optional_enrichment_pending'],
          staleSources: [],
          providerTimeouts: ['gnews:news'],
          providerCooldowns: ['fmp:fundamentals'],
          confidenceCap: 70,
          reasonCodes: ['important_data_missing', 'optional_enrichment_missing'],
          freshness: { marketSessionDate: '2026-05-05' },
          enrichmentStatus: 'pending',
          enrichmentSources: ['news', 'sentiment', 'detailed_fundamentals'],
          completedSources: ['sentiment'],
          pendingSources: ['news'],
          failedSources: [],
          skippedSources: ['detailed_fundamentals'],
          enrichmentReasons: { news: ['optional_news_timeout'] },
          enrichmentUpdatedAt: '2026-05-06T01:01:00Z',
          enrichmentAsOf: '2026-05-06T01:00:00Z',
        },
        standardReport: {
          summaryPanel: {
            stock: 'Oracle',
            ticker: 'ORCL',
            oneSentence: 'Cloud backlog keeps the medium-term floor intact.',
          },
          decisionContext: {
            shortTermView: 'Post-earnings strength still holds the upper rail',
          },
          decisionPanel: {
            idealEntry: '121.80 - 124.60',
            target: '133.50',
            stopLoss: '117.40',
            buildStrategy: 'Start light, then add only after the pullback stays orderly.',
          },
          reasonLayer: {
            coreReasons: ['Institutional sponsorship remains intact after earnings.'],
          },
          technicalFields: [
            { label: 'MACD', value: 'Second expansion above zero' },
            { label: 'Moving Averages', value: 'MA20 lifting MA60' },
          ],
          fundamentalFields: [
            { label: 'Revenue Growth', value: '+9.4%' },
            { label: 'Free Cash Flow', value: '$12.1B' },
          ],
        },
      },
      dataQualityReport: {
        dataQualityTier: 'analysis_grade',
        dataQualityScore: 68,
        requiredAvailable: true,
        importantMissing: ['fundamentals.eps'],
        optionalMissing: ['optional_enrichment_pending'],
        staleSources: [],
        providerTimeouts: ['gnews:news'],
        providerCooldowns: ['fmp:fundamentals'],
        confidenceCap: 70,
        reasonCodes: ['important_data_missing', 'optional_enrichment_missing'],
        freshness: { marketSessionDate: '2026-05-05' },
        enrichmentStatus: 'pending',
        enrichmentSources: ['news', 'sentiment', 'detailed_fundamentals'],
        completedSources: ['sentiment'],
        pendingSources: ['news'],
        failedSources: [],
        skippedSources: ['detailed_fundamentals'],
        enrichmentReasons: { news: ['optional_news_timeout'] },
        enrichmentUpdatedAt: '2026-05-06T01:01:00Z',
        enrichmentAsOf: '2026-05-06T01:00:00Z',
      },
      evidenceCoverageFrame: {
        technicals: {
          status: 'available',
          missingReasons: [],
          nextEvidenceNeeded: [],
        },
        fundamentals: {
          status: 'degraded',
          missingReasons: ['partial_coverage', 'provider_timeout'],
          nextEvidenceNeeded: ['补充基本面证据'],
        },
        news: {
          status: 'missing',
          missingReasons: ['evidence_missing'],
          nextEvidenceNeeded: ['补充新闻证据'],
        },
        catalysts: {
          status: 'blocked',
          missingReasons: ['provider_timeout'],
          nextEvidenceNeeded: ['补充催化证据'],
        },
        earnings: {
          status: 'pending',
          missingReasons: ['evidence_pending'],
          nextEvidenceNeeded: ['补充财报证据'],
        },
        valuation: {
          status: 'not_applicable',
          missingReasons: [],
          nextEvidenceNeeded: [],
        },
      },
      decisionTrace: {
        engineVersion: 'analysis_decision_trace_v1',
        mode: 'rule_scoring_with_llm_explanation',
        endpoint: '/api/v1/analysis/analyze',
        taskId: 'q3',
        symbol: 'ORCL',
        market: 'US',
        decisionFields: {
          action: { value: 'hold', source: 'rule', confidence: 0.78, notes: 'stabilized score path' },
          score: { value: 78, source: 'rule', scale: '0-100' },
          confidence: { value: '高', source: 'llm' },
          entry: { value: '121.80 - 124.60', source: 'llm' },
          target: { value: '133.50', source: 'llm' },
          stop: { value: '117.40', source: 'llm' },
        },
        dataSources: [
          { name: 'quote', status: 'used', provider: 'Yahoo Finance' },
          { name: 'fundamental', status: 'fallback', provider: 'FMP' },
          { name: 'news', status: 'missing', provider: null },
        ],
        signals: [
          { name: 'MA alignment', value: 'bullish', impact: 'positive', source: 'technical_rule' },
        ],
        llm: {
          used: true,
          provider: 'openai',
          model: 'openai/gpt-4.1-mini',
          template: 'decision_dashboard_v2',
          structuredOutput: true,
          schemaValidated: true,
          promptExposed: false,
        },
        conflicts: [
          {
            type: 'action_plan_mismatch',
            severity: 'warning',
            message: 'Action says sell but plan includes entry/accumulation.',
          },
        ],
        limitations: ['fundamental data partial'],
      },
    });
  });
}

function buildScannerRunDetailWithContext(
  overrides: Record<string, unknown> = {},
) {
  return {
    id: 11,
    market: 'cn',
    profile: 'cn_preopen_v1',
    profile_label: 'A-share Pre-open v1',
    status: 'completed',
    run_at: '2026-06-02T09:00:00Z',
    completed_at: '2026-06-02T09:00:10Z',
    watchlist_date: '2026-06-02',
    trigger_mode: 'manual',
    universe_name: 'cn_a_liquid_watchlist_v1',
    shortlist_size: 18,
    universe_size: 320,
    preselected_size: 72,
    evaluated_size: 48,
    source_summary: 'Mocked scanner payload',
    headline: 'Mock scanner shortlist for scanner top-down context smoke',
    universe_type: 'theme',
    theme_id: 'ai_semiconductors',
    theme_label: 'AI 半导体',
    requested_symbols_count: 0,
    accepted_symbols_count: 0,
    rejected_symbols: [],
    shortlist: [
      {
        symbol: 'NVDA',
        name: 'NVIDIA',
        company_name: 'NVIDIA Corp',
        rank: 1,
        score: 98,
        quality_hint: 'Liquid and trend-aligned',
        reason_summary: 'NVDA keeps relative strength and breadth support.',
        reasons: ['NVDA is holding above the recent breakout range.'],
        key_metrics: [
          { label: 'Entry range', value: '100-102' },
          { label: 'Target price', value: '112' },
          { label: 'Stop loss', value: '96' },
        ],
        feature_signals: [
          { label: 'Theme', value: 'AI infrastructure' },
          { label: 'Momentum', value: 'Improving' },
        ],
        risk_notes: ['Crowded trade if volume stalls.'],
        watch_context: [{ label: 'Plan', value: 'Wait for first controlled pullback.' }],
        boards: ['semis'],
        tags: [{ name: 'High conviction', description: 'Top-ranked mock setup.', tone: 'indigo' }],
        appeared_in_recent_runs: 2,
        last_trade_date: '2026-06-01',
        scan_timestamp: '2026-06-02T09:00:00Z',
        ai_interpretation: {
          available: false,
          status: 'not_configured',
          summary: null,
          opportunity_type: null,
          risk_interpretation: null,
          watch_plan: null,
          review_commentary: null,
          provider: null,
          model: null,
          generated_at: null,
          message: null,
        },
        realized_outcome: {
          review_status: 'pending',
          outcome_label: 'pending',
          thesis_match: 'pending',
          review_window_days: 3,
          anchor_date: '2026-06-01',
          window_end_date: '2026-06-04',
          same_day_close_return_pct: null,
          next_day_return_pct: null,
          review_window_return_pct: null,
          max_favorable_move_pct: null,
          max_adverse_move_pct: null,
          benchmark_code: null,
          benchmark_return_pct: null,
          outperformed_benchmark: null,
        },
        diagnostics: {},
      },
    ],
    summary: {
      selected_count: 18,
      rejected_count: 5,
      data_failed_count: 1,
      error_count: 0,
    },
    scanner_context_frame: {
      market_readiness: {
        contract_version: 'research_readiness_v1',
        research_ready: false,
        readiness_state: 'observe_only',
        verdict_label: '仅观察',
        blocking_reasons: [],
        missing_evidence: [],
        evidence_coverage: {
          score_grade_count: 2,
          observation_only_count: 1,
          missing_count: 0,
          total_count: 3,
        },
        source_authority: 'observationOnly',
        freshness_floor: 'cached',
        consumer_action_boundary: 'no_advice',
        next_evidence_needed: ['继续结合市场与主题框架观察'],
      },
      macro_regime: {
        state: 'supportive',
        label: 'Supportive macro regime',
        freshness: 'cached',
        blockers: [],
        observation_only: false,
        source_authority_allowed: true,
        score_contribution_allowed: true,
      },
      liquidity_frame: {
        state: 'supportive',
        label: 'Liquidity supports equity leadership',
        freshness: 'cached',
        blockers: [],
        observation_only: false,
        source_authority_allowed: true,
        score_contribution_allowed: true,
        proxy_only: false,
      },
      asset_class_bias: {
        state: 'supportive',
        label: 'Equities preferred',
        blockers: [],
        observation_only: false,
      },
      theme_frame: {
        state: 'observe_only',
        label: 'AI leadership is still observation-only',
        freshness: 'cached',
        blockers: [],
        observation_only: true,
        proxy_only: true,
        themes: [
          { id: 'ai', label: 'AI', observation_only: true, proxy_only: true },
          { id: 'software', label: 'Software', observation_only: true, proxy_only: true },
        ],
      },
      universe_policy: {
        type: 'theme',
        label: 'Theme universe',
        blockers: [],
      },
      no_advice_boundary: true,
    },
    ...overrides,
  };
}

function buildScannerRunsPayload(itemOverrides: Record<string, unknown> = {}) {
  return {
    total: 1,
    page: 1,
    limit: 10,
    items: [
      {
        id: 11,
        market: 'cn',
        profile: 'cn_preopen_v1',
        profile_label: 'A-share Pre-open v1',
        status: 'completed',
        run_at: '2026-06-02T09:00:00Z',
        completed_at: '2026-06-02T09:00:10Z',
        watchlist_date: '2026-06-02',
        trigger_mode: 'manual',
        universe_name: 'cn_a_liquid_watchlist_v1',
        shortlist_size: 18,
        universe_size: 320,
        preselected_size: 72,
        evaluated_size: 48,
        source_summary: 'Mocked scanner payload',
        headline: 'Mock scanner shortlist for scanner top-down context smoke',
        universe_type: 'theme',
        theme_id: 'ai_semiconductors',
        theme_label: 'AI 半导体',
        requested_symbols_count: 0,
        accepted_symbols_count: 0,
        rejected_symbols: [],
        top_symbols: ['NVDA'],
        notification_status: 'not_attempted',
        failure_reason: null,
        ...itemOverrides,
      },
    ],
  };
}

function createProductAuthStatus() {
  return {
    authEnabled: true,
    loggedIn: true,
    passwordSet: true,
    passwordChangeable: true,
    setupState: 'enabled',
    currentUser: signedInUser,
  };
}

function optionsSummary(symbol: string) {
  return {
    symbol,
    market: 'us',
    underlying: {
      price: 52.34,
      change_pct: 1.2,
      source: 'playwright_fixture',
      as_of: '2026-05-06T09:45:00-04:00',
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
      updated_at: '2026-05-06T09:45:00-04:00',
    },
  };
}

function optionsExpirations(symbol: string) {
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
      limitations: ['mocked_playwright_product_auth'],
      source_label: 'Playwright Fixture',
      updated_at: '2026-05-06T09:45:00-04:00',
    },
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

function optionsChain(symbol: string) {
  return {
    symbol,
    expiration: '2026-06-19',
    underlying: {
      price: 52.34,
      change_pct: 1.2,
      source: 'playwright_fixture',
      as_of: '2026-05-06T09:45:00-04:00',
      freshness: 'mock',
    },
    calls: [optionContract(symbol, 'call', 55, 4.23), optionContract(symbol, 'call', 60, 2.28)],
    puts: [optionContract(symbol, 'put', 50, 2.42), optionContract(symbol, 'put', 45, 1.16)],
    filters_applied: { min_open_interest: 100, max_spread_pct: 25 },
    chain_as_of: '2026-05-06T09:45:00-04:00',
    source: 'playwright_fixture',
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

function strategy(strategyType: string) {
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
    limitations: ['mocked_product_route_harness'],
    no_advice_disclosure: 'Scenario analysis only; not personalized financial advice.',
  };
}

function optionsScenarioFrame(symbol: string) {
  return {
    contractVersion: 'options-consumer-scenario-frame-v1',
    frameState: 'insufficient',
    underlying: { symbol },
    strategyType: 'bull_call_spread',
    expiration: '2026-06-19',
    scenarioCoverage: 'strategy_compare_ready',
    chainQuality: {
      hasChain: true,
      contractCount: 4,
      callCount: 2,
      putCount: 2,
      freshness: 'mock',
      sourceType: 'synthetic_fixture',
      coverageState: 'strategy_compare_ready',
    },
    liquidityGate: 'manual_review',
    ivGreeksGate: 'blocked',
    spreadGate: 'manual_review',
    payoffEvidence: {
      targetPrice: 65,
      payoffAtTarget: 577,
      expectedMoveAbs: 5.2,
      expectedMovePct: 9.9,
      expectedMoveSource: 'straddle_mid',
    },
    riskEvidence: {
      premiumAtRisk: 230,
      maxLoss: 230,
      maxGain: 500,
      breakeven: 57.3,
      requiredMovePct: 9.5,
    },
    assumptions: {
      inputMode: 'decision',
      direction: 'bullish',
      targetPrice: 65,
      targetDate: '2026-08-21',
    },
    missingEvidence: ['provider authority', 'iv greeks'],
    nextEvidenceNeeded: [
      '补充 provider authority 与 live chain 证据',
      '补充 Greeks 与 IV 证据',
      '补充 OI/成交量与更紧价差证据',
    ],
    noTradingBoundary: {
      analyticalOnly: true,
      noBrokerExecution: true,
      noOrderPlacement: true,
      noPortfolioMutation: true,
      noTradingRecommendation: true,
    },
  };
}

function optionsStrategyComparison(symbol: string) {
  return {
    symbol,
    underlying: {
      price: 52.34,
      change_pct: 1.2,
      source: 'playwright_fixture',
      as_of: '2026-05-06T09:45:00-04:00',
      freshness: 'mock',
    },
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
    optionsConsumerScenarioFrame: optionsScenarioFrame(symbol),
  };
}

function optionsDecision(symbol: string) {
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
      strategy_engine: 'playwright_fixture',
      force_refresh_ignored: true,
    },
    optionsConsumerScenarioFrame: optionsScenarioFrame(symbol),
  };
}

function symbolFromOptionsPath(path: string) {
  const match = path.match(/\/api\/v1\/options\/underlyings\/([^/]+)/);
  return decodeURIComponent(match?.[1] || 'TEM').toUpperCase();
}

async function installOptionsProductHarness(page: Page): Promise<ProductRouteHarness> {
  const calls: string[] = [];

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    calls.push(`${method} ${path}`);

    if (method === 'GET' && path === '/api/v1/auth/status') {
      return fulfillJson(route, createProductAuthStatus());
    }
    if (method === 'GET' && path === '/api/v1/auth/me') {
      return fulfillJson(route, signedInUser);
    }
    if (method === 'GET' && path === '/api/v1/agent/status') {
      return fulfillJson(route, { enabled: false });
    }
    if (method === 'GET' && path === '/api/v1/history') {
      return fulfillJson(route, { total: 0, page: 1, limit: 20, items: [] });
    }
    if (method === 'GET' && path === '/api/v1/analysis/tasks') {
      return fulfillJson(route, { tasks: [], total: 0 });
    }
    if (method === 'GET' && path.match(/^\/api\/v1\/options\/underlyings\/[^/]+\/summary$/)) {
      return fulfillJson(route, optionsSummary(symbolFromOptionsPath(path)));
    }
    if (method === 'GET' && path.match(/^\/api\/v1\/options\/underlyings\/[^/]+\/expirations$/)) {
      return fulfillJson(route, optionsExpirations(symbolFromOptionsPath(path)));
    }
    if (method === 'GET' && path.match(/^\/api\/v1\/options\/underlyings\/[^/]+\/chain$/)) {
      return fulfillJson(route, optionsChain(symbolFromOptionsPath(path)));
    }
    if (method === 'POST' && path === '/api/v1/options/strategies/compare') {
      const payload = request.postDataJSON() as { symbol?: string } | null;
      return fulfillJson(route, optionsStrategyComparison((payload?.symbol || 'TEM').toUpperCase()));
    }
    if (method === 'POST' && path === '/api/v1/options/decision/evaluate') {
      const payload = request.postDataJSON() as { symbol?: string } | null;
      return fulfillJson(route, optionsDecision((payload?.symbol || 'TEM').toUpperCase()));
    }

    return fulfillJson(route, { error: `Unhandled options harness route: ${method} ${path}` }, 500);
  });

  return {
    requests: {
      count: (method: string, path: string) => calls.filter((entry) => entry === `${method} ${path}`).length,
    },
  };
}

async function openOptionsRouteWithHarness(page: Page, path: string) {
  const harness = await installOptionsProductHarness(page);
  await page.goto(path);
  await page.waitForLoadState('domcontentloaded');
  await expect(page).not.toHaveURL(/\/guest(?:$|[/?#])/);
  return harness;
}

async function installScannerTopDownRoutes(page: Page) {
  const mixedRun = buildScannerRunDetailWithContext();
  const insufficientRun = buildScannerRunDetailWithContext({
    scanner_context_frame: {
      market_readiness: {
        contract_version: 'research_readiness_v1',
        research_ready: false,
        readiness_state: 'insufficient',
        verdict_label: '证据不足',
        blocking_reasons: ['market_context_missing'],
        missing_evidence: ['macro', 'liquidity'],
        evidence_coverage: {
          score_grade_count: 0,
          observation_only_count: 1,
          missing_count: 2,
          total_count: 3,
        },
        source_authority: 'unavailable',
        freshness_floor: 'unknown',
        consumer_action_boundary: 'no_advice',
        next_evidence_needed: ['补齐市场与流动性证据后再复核'],
      },
      macro_regime: {
        state: 'insufficient',
        label: 'Macro context missing',
        freshness: 'unknown',
        blockers: [],
        observation_only: true,
        source_authority_allowed: false,
        score_contribution_allowed: false,
      },
      liquidity_frame: {
        state: 'insufficient',
        label: 'Liquidity context missing',
        freshness: 'unknown',
        blockers: [],
        observation_only: true,
        source_authority_allowed: false,
        score_contribution_allowed: false,
        proxy_only: false,
      },
      asset_class_bias: {
        state: 'insufficient',
        label: 'Bias unavailable',
        blockers: [],
        observation_only: true,
      },
      theme_frame: {
        state: 'observe_only',
        label: 'Theme remains observation-only',
        freshness: 'cached',
        blockers: [],
        observation_only: true,
        proxy_only: true,
        themes: [{ id: 'ai', label: 'AI', observation_only: true, proxy_only: true }],
      },
      universe_policy: {
        type: 'theme',
        label: 'Theme universe',
        blockers: [],
      },
      no_advice_boundary: true,
    },
  });
  const blockedRun = buildScannerRunDetailWithContext({
    market: 'cn',
    scanner_context_frame: {
      market_readiness: {
        contract_version: 'research_readiness_v1',
        research_ready: false,
        readiness_state: 'insufficient',
        verdict_label: '证据不足',
        blocking_reasons: ['cn_context_unavailable'],
        missing_evidence: ['macro', 'liquidity'],
        evidence_coverage: {
          score_grade_count: 0,
          observation_only_count: 0,
          missing_count: 3,
          total_count: 3,
        },
        source_authority: 'unavailable',
        freshness_floor: 'unknown',
        consumer_action_boundary: 'no_advice',
        next_evidence_needed: ['等待中国市场上下文恢复后再复核'],
      },
      macro_regime: {
        state: 'blocked',
        label: 'CN context unavailable',
        freshness: 'unknown',
        blockers: ['cn_context_unavailable'],
        observation_only: true,
        source_authority_allowed: false,
        score_contribution_allowed: false,
      },
      liquidity_frame: {
        state: 'blocked',
        label: 'CN liquidity context unavailable',
        freshness: 'unknown',
        blockers: ['cn_context_unavailable'],
        observation_only: true,
        source_authority_allowed: false,
        score_contribution_allowed: false,
        proxy_only: false,
      },
      asset_class_bias: {
        state: 'blocked',
        label: 'Bias unavailable',
        blockers: ['cn_context_unavailable'],
        observation_only: true,
      },
      theme_frame: {
        state: 'blocked',
        label: 'Theme context unavailable',
        freshness: 'unknown',
        blockers: ['cn_context_unavailable'],
        observation_only: true,
        proxy_only: false,
        themes: [],
      },
      universe_policy: {
        type: 'default',
        label: 'Default universe',
        blockers: ['cn_context_unavailable'],
      },
      no_advice_boundary: true,
    },
  });
  let activeRun = mixedRun;

  await page.route('**/api/v1/scanner/runs**', async (route) => {
    await fulfillJson(route, buildScannerRunsPayload());
  });
  await page.route('**/api/v1/scanner/watchlists/recent**', async (route) => {
    await fulfillJson(route, buildScannerRunsPayload());
  });
  await page.route('**/api/v1/scanner/runs/11**', async (route) => {
    await fulfillJson(route, activeRun);
  });

  return {
    showMixed() {
      activeRun = mixedRun;
    },
    showInsufficient() {
      activeRun = insufficientRun;
    },
    showBlocked() {
      activeRun = blockedRun;
    },
  };
}

async function openSignedInHome(page: Page) {
  await installSignedInHomeRoutes(page);
  await page.goto('/zh');
  await page.waitForLoadState('domcontentloaded');
  await appExpect(page.getByTestId('home-bento-dashboard')).toBeVisible({ timeout: 15_000 });
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

async function expectSafeReadinessStrip(page: Page, testId: string) {
  const strip = page.getByTestId(testId);
  await appExpect(strip).toBeVisible({ timeout: 15_000 });
  await appExpect(strip).toContainText(/研究就绪度|Research readiness/);
  await appExpect(strip).toContainText(safeVerdictPattern);
  await appExpect(strip).not.toContainText(rawLeakPattern);
  await appExpect(strip).not.toContainText(tradingPattern);
}

async function expectSafeEvidenceCoverageStrip(page: Page) {
  const strip = page.getByTestId('home-evidence-coverage-strip');
  await appExpect(strip).toBeVisible({ timeout: 15_000 });
  await appExpect(strip).toContainText('证据覆盖');
  await appExpect(strip).toContainText('技术面 可用');
  await appExpect(strip).toContainText('基本面 降级');
  await appExpect(strip).toContainText('新闻 缺失');
  await appExpect(strip).toContainText('催化 阻断');
  await appExpect(strip).toContainText('财报 待补');
  await appExpect(strip).toContainText('补充基本面证据');
  await appExpect(strip).toContainText('补充新闻证据');
  await appExpect(strip).toContainText('补充催化证据');
  await appExpect(strip).toContainText('补充财报证据');
  await appExpect(strip).not.toContainText(internalEvidenceCoveragePattern);
  await appExpect(strip).not.toContainText(rawLeakPattern);
  await appExpect(strip).not.toContainText(tradingPattern);
}

async function installOptionsReadinessSummaryRoute(page: Page) {
  await page.route('**/api/v1/options/underlyings/*/summary', async (route) => {
    const url = new URL(route.request().url());
    const pathParts = url.pathname.split('/');
    const symbol = decodeURIComponent(pathParts[pathParts.length - 2] || 'TEM').toUpperCase();
    await fulfillJson(route, {
      symbol,
      market: 'us',
      underlying: {
        price: 52.34,
        change_pct: 1.2,
        source: 'playwright_fixture',
        as_of: '2026-05-06T09:45:00-04:00',
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
        updated_at: '2026-05-06T09:45:00-04:00',
      },
      options_readiness: optionsReadinessSummaryFixture,
    });
  });
}

appTest.describe('consumer research readiness browser acceptance', () => {
  appTest('Home readiness strip is visible and consumer-safe', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    await installSignedInHomeRoutes(page);
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await openSignedInHome(page);
      await expectRootNonEmpty(page);
      await expectNoHorizontalOverflow(page);
      await expectSafeReadinessStrip(page, 'home-research-readiness-strip');
      await expectSafeEvidenceCoverageStrip(page);
      expect(consoleErrors).toEqual([]);
      expect(unhandledApiRoutes).toEqual([]);
    }
  });

  appTest('Market Overview readiness strip is visible and consumer-safe', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    appTest.setTimeout(45_000);
    await installSignedInHomeRoutes(page);
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await signIn(page, '/market-overview');
      await appExpect(page.getByTestId('market-overview-shell')).toBeVisible({ timeout: 15_000 });
      await expectRootNonEmpty(page);
      await expectNoHorizontalOverflow(page);
      await expectSafeReadinessStrip(page, 'market-overview-research-readiness-strip');
      expect(consoleErrors).toEqual([]);
      expect(unhandledApiRoutes).toEqual([]);
    }
  });

  appTest('Scanner readiness strip is visible and consumer-safe', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const scannerRoutes = await installScannerTopDownRoutes(page);
      await page.route('**/api/v1/auth/status', async (route) => {
        await fulfillJson(route, {
          authEnabled: true,
          loggedIn: true,
          passwordSet: true,
          passwordChangeable: true,
          setupState: 'enabled',
          currentUser: signedInUser,
        });
      });
      await page.goto('/zh/scanner');
      await page.waitForLoadState('domcontentloaded');
      await appExpect(page.getByTestId('user-scanner-workspace')).toBeVisible({ timeout: 15_000 });
      await expectRootNonEmpty(page);
      await expectNoHorizontalOverflow(page);
      await expectSafeReadinessStrip(page, 'scanner-research-readiness-strip');
      const topDownStrip = page.getByTestId('scanner-top-down-context-strip');
      await appExpect(topDownStrip).toBeVisible({ timeout: 15_000 });
      await appExpect(topDownStrip).toContainText('市场驱动因素');
      await appExpect(topDownStrip).toContainText('混合');
      await appExpect(topDownStrip).toContainText('市场：仅观察');
      await appExpect(topDownStrip).toContainText('宏观：支持');
      await appExpect(topDownStrip).toContainText('流动性：支持');
      await appExpect(topDownStrip).toContainText('主题：仅观察');
      await appExpect(topDownStrip).toContainText('标的池：主题池');
      await appExpect(topDownStrip).toContainText('边界：仅研究观察');
      await appExpect(topDownStrip).not.toContainText(/raw|internal|debug|provider|cache|router|env|sourceAuthority|providerRoute|provider_timeout/i);
      await appExpect(topDownStrip).not.toContainText(tradingPattern);
      await appExpect(page.getByTestId('scanner-result-row-NVDA')).toBeVisible();

      scannerRoutes.showInsufficient();
      await page.goto('/zh/scanner');
      await page.waitForLoadState('domcontentloaded');
      const insufficientStrip = page.getByTestId('scanner-top-down-context-strip');
      await appExpect(insufficientStrip).toContainText('证据不足');
      await appExpect(insufficientStrip).toContainText('市场：证据不足');
      await appExpect(insufficientStrip).toContainText('宏观：证据不足');
      await appExpect(insufficientStrip).toContainText('流动性：证据不足');
      await appExpect(insufficientStrip).toContainText('边界：仅研究观察');
      await appExpect(insufficientStrip).not.toContainText(/buy|sell|order|trade|broker|买入|卖出|下单|交易|券商/i);

      scannerRoutes.showBlocked();
      await page.goto('/zh/scanner');
      await page.waitForLoadState('domcontentloaded');
      const blockedStrip = page.getByTestId('scanner-top-down-context-strip');
      await appExpect(blockedStrip).toContainText('阻断');
      await appExpect(blockedStrip).toContainText('市场：证据不足');
      await appExpect(blockedStrip).toContainText('宏观：阻断');
      await appExpect(blockedStrip).toContainText('流动性：阻断');
      await appExpect(blockedStrip).toContainText('边界：仅研究观察');
      await appExpect(blockedStrip).not.toContainText(/raw|internal|debug|provider|cache|router|env|sourceAuthority|providerRoute|provider_timeout/i);
      await appExpect(blockedStrip).not.toContainText(tradingPattern);
      expect(consoleErrors).toEqual([]);
      expect(unhandledApiRoutes).toEqual([]);
      await page.unroute('**/api/v1/scanner/runs**');
      await page.unroute('**/api/v1/scanner/watchlists/recent**');
      await page.unroute('**/api/v1/scanner/runs/11**');
    }
  });
});

appTest.describe('Options Lab readiness browser acceptance', () => {
  appTest('readiness verdict is visible and consumer-safe', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await openOptionsRouteWithHarness(page, '/zh/options-lab');
      await expectRootNonEmpty(page);
      await expectNoHorizontalOverflow(page);
      await expectSafeReadinessStrip(page, 'options-lab-research-readiness-strip');
      const summary = page.getByTestId('options-lab-readiness-gate-summary');
      await appExpect(summary).toBeVisible({ timeout: 15_000 });
      await appExpect(summary).toContainText('门控摘要');
      await appExpect(summary).toContainText('数据层级：证据不足');
      await appExpect(summary).toContainText('授权级别：待补证');
      await appExpect(summary).toContainText('流动性：已阻断');
      await appExpect(summary).toContainText('IV / Greeks：已阻断');
      await appExpect(summary).toContainText('价差：已阻断');
      await appExpect(summary).toContainText('情景覆盖：缺少链路');
      await appExpect(summary).toContainText('判断等级：未通过');
      await appExpect(summary).toContainText('执行边界：只读无执行');
      await appExpect(summary).toContainText('当前缺少就绪度回执，先按证据不足处理。');
      await appExpect(summary).not.toContainText(optionsGateSummaryLeakPattern);
      await appExpect(summary).not.toContainText(tradingPattern);
      await expectForbiddenTradingWordingAbsent(page);
      expect(consoleErrors).toEqual([]);
      expect(unhandledApiRoutes).toEqual([]);
    }
  });

  appTest('scenario evidence workflow is visible, bounded, and sanitized', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await openOptionsRouteWithHarness(page, '/zh/options-lab');
      await expectRootNonEmpty(page);
      await expectNoHorizontalOverflow(page);
      await expectSafeReadinessStrip(page, 'options-lab-research-readiness-strip');

      const summary = page.getByTestId('options-lab-readiness-gate-summary');
      await appExpect(summary).toBeVisible({ timeout: 15_000 });
      await appExpect(summary).toContainText('门控摘要');

      const scenarioEvidence = page.getByTestId('options-lab-scenario-evidence');
      await appExpect(scenarioEvidence).toBeVisible({ timeout: 15_000 });
      await appExpect(scenarioEvidence).toContainText('情景证据');
      await appExpect(scenarioEvidence).toContainText('先确认覆盖范围、链路质量与缺口');
      await appExpect(scenarioEvidence).toContainText('证据状态');
      await appExpect(scenarioEvidence).toContainText('证据不足');
      await appExpect(scenarioEvidence).toContainText('情景覆盖');
      await appExpect(scenarioEvidence).toContainText('策略比较覆盖');
      await appExpect(scenarioEvidence).toContainText('链路质量');
      await appExpect(scenarioEvidence).toContainText('链路已加载');
      await appExpect(scenarioEvidence).toContainText('4 份合约');
      await appExpect(scenarioEvidence).toContainText('Call 2 / Put 2');
      await appExpect(scenarioEvidence).toContainText('演示/延迟');
      await appExpect(scenarioEvidence).toContainText('流动性：人工复核');
      await appExpect(scenarioEvidence).toContainText('IV / Greeks：已阻断');
      await appExpect(scenarioEvidence).toContainText('价差：人工复核');
      await appExpect(scenarioEvidence).toContainText('假设摘要');
      await appExpect(scenarioEvidence).toContainText('当前来自判断回执');
      await appExpect(scenarioEvidence).toContainText('方向：上涨情景');
      await appExpect(scenarioEvidence).toContainText('目标价：$65.00');
      await appExpect(scenarioEvidence).toContainText('目标日：2026-08-21');
      await appExpect(scenarioEvidence).toContainText('收益证据');
      await appExpect(scenarioEvidence).toContainText('预期波动：$5.20');
      await appExpect(scenarioEvidence).toContainText('预期波动幅度：9.9%');
      await appExpect(scenarioEvidence).toContainText('目标情景收益：$577.00');
      await appExpect(scenarioEvidence).toContainText('波动来源：平值跨式中间价');
      await appExpect(scenarioEvidence).toContainText('风险证据');
      await appExpect(scenarioEvidence).toContainText('权利金风险：$230.00');
      await appExpect(scenarioEvidence).toContainText('最大亏损：$230.00');
      await appExpect(scenarioEvidence).toContainText('最大收益：$500.00');
      await appExpect(scenarioEvidence).toContainText('盈亏平衡：$57.30');
      await appExpect(scenarioEvidence).toContainText('缺失证据');
      await appExpect(scenarioEvidence).toContainText('授权链路待补证');
      await appExpect(scenarioEvidence).toContainText('波动率与敏感度待补证');
      await appExpect(scenarioEvidence).toContainText('下一步补证');
      await appExpect(scenarioEvidence).toContainText('补齐授权链路与实时链路证据');
      await appExpect(scenarioEvidence).toContainText('补齐波动率与敏感度证据');
      await appExpect(scenarioEvidence).toContainText('补齐成交深度与更紧价差证据');
      await appExpect(scenarioEvidence).toContainText('只读边界');
      await appExpect(scenarioEvidence).toContainText('仅观察');
      await appExpect(scenarioEvidence).toContainText('不触发执行动作');
      await appExpect(scenarioEvidence).toContainText('不改动现有持仓');
      await appExpect(scenarioEvidence).toContainText('结论仅用于研究记录');
      await appExpect(scenarioEvidence).not.toContainText(optionsGateSummaryLeakPattern);
      await appExpect(scenarioEvidence).not.toContainText(tradingPattern);

      const visualsPanel = page.getByTestId('options-lab-visuals-panel');
      await appExpect(visualsPanel).toBeVisible({ timeout: 15_000 });
      await appExpect(visualsPanel).toContainText('收益边界与 IV 快照');
      await appExpect(visualsPanel).toContainText('到期收益示意');
      await appExpect(visualsPanel).toContainText('IV 偏斜示意');
      await appExpect(visualsPanel).toContainText('不构成买卖建议');
      await appExpect(visualsPanel).not.toContainText(optionsGateSummaryLeakPattern);

      await expectForbiddenTradingWordingAbsent(page);
      expect(harness.requests.count('POST', '/api/v1/options/strategies/compare')).toBeGreaterThan(0);
      expect(harness.requests.count('POST', '/api/v1/options/decision/evaluate')).toBeGreaterThan(0);
      expect(consoleErrors).toEqual([]);
      expect(unhandledApiRoutes).toEqual([]);
    }
  });

  appTest('gate summary labels are visible and sanitized when readiness gates are present', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await installOptionsProductHarness(page);
      await installOptionsReadinessSummaryRoute(page);
      await page.goto('/zh/options-lab');
      await page.waitForLoadState('domcontentloaded');
      await expectRootNonEmpty(page);
      await expectNoHorizontalOverflow(page);
      await expectSafeReadinessStrip(page, 'options-lab-research-readiness-strip');
      const summary = page.getByTestId('options-lab-readiness-gate-summary');
      await appExpect(summary).toBeVisible({ timeout: 15_000 });
      await appExpect(summary).toContainText('门控摘要');
      await appExpect(summary).toContainText('数据层级：演示/延迟');
      await appExpect(summary).toContainText('授权级别：观察级');
      await appExpect(summary).toContainText('流动性：人工复核');
      await appExpect(summary).toContainText('IV / Greeks：已阻断');
      await appExpect(summary).toContainText('价差：人工复核');
      await appExpect(summary).toContainText('情景覆盖：策略对比');
      await appExpect(summary).toContainText('判断等级：未通过');
      await appExpect(summary).toContainText('执行边界：只读无执行');
      await appExpect(summary).toContainText('当前仍受授权、IV / Greeks 与流动性证据限制。');
      await appExpect(summary).toContainText('下一步：补齐授权链路、IV / Greeks、OI / 成交量与更紧价差证据。');
      await appExpect(summary).not.toContainText(optionsGateSummaryLeakPattern);
      await appExpect(summary).not.toContainText(tradingPattern);
      expect(consoleErrors).toEqual([]);
      expect(unhandledApiRoutes).toEqual([]);
    }
  });
});
