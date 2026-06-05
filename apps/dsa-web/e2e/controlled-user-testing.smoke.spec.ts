import type { Locator, Page, Route } from '@playwright/test';
import { expect as appExpect, test as appTest } from './fixtures/appSmoke';

const desktopViewport = { width: 1440, height: 1000 };
const narrowViewport = { width: 390, height: 844 };
const timestamp = '2026-06-04T09:00:00Z';

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

const forbiddenInternalPattern =
  /raw\s+(payload|response|schema|prompt|trace)|debug\s+(payload|response|schema|prompt|panel)|provider\s+(route|payload|response)|cache\s+router|stack\s+trace|traceback|internal\s+reasoning|sourceAuthority|providerRoute|api[_\s-]?key\s*[=:]|password\s*[=:]|session[_\s-]?id\s*[=:]|secret\s*[=:]|bearer\s+[a-z0-9._-]+|sk-[a-z0-9_-]{12,}/i;
const forbiddenExecutionPattern =
  /买入按钮|建议买入|建议卖出|立即交易|提交订单|连接券商|连接经纪商|真实下单|必买|稳赚|保证收益|guaranteed|best contract|AI recommends you buy|must buy|must sell|buy now|sell now|place order|submit order|connect broker|broker CTA/i;

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installSignedInSessionRoutes(page: Page) {
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
}

async function expectNoHorizontalOverflow(page: Page) {
  await appExpect
    .poll(async () => page.evaluate(() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)))
    .toBeLessThanOrEqual(1);
}

async function expectConsumerSafeRegion(region: Locator) {
  const text = (await region.innerText())
    .replaceAll('仅做只读情景分析，不构成交易或下单指令。', '')
    .replaceAll('不构成交易/下单指令', '')
    .replaceAll('不构成交易或下单指令', '')
    .replaceAll('不构成买卖建议', '')
    .replaceAll('不会提交订单', '')
    .replaceAll('不连接经纪商', '')
    .replaceAll('不改动投资组合', '');
  appExpect(text).not.toMatch(forbiddenInternalPattern);
  appExpect(text).not.toMatch(forbiddenExecutionPattern);
}

function homeHistoryData() {
  return [
    { date: '2026-05-27', open: 120.0, high: 121.2, low: 119.4, close: 120.8, volume: 8100000, change_percent: 0.7 },
    { date: '2026-05-28', open: 120.9, high: 122.4, low: 120.1, close: 121.7, volume: 7900000, change_percent: 0.74 },
    { date: '2026-05-29', open: 121.8, high: 123.1, low: 121.0, close: 122.2, volume: 8400000, change_percent: 0.41 },
    { date: '2026-05-30', open: 122.0, high: 123.6, low: 121.4, close: 123.1, volume: 8600000, change_percent: 0.74 },
    { date: '2026-06-02', open: 123.2, high: 124.1, low: 122.7, close: 123.8, volume: 8050000, change_percent: 0.57 },
  ];
}

async function installHomeResearchRoutes(page: Page) {
  await installSignedInSessionRoutes(page);

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
          },
        },
      ],
      meta: {
        generated_at: timestamp,
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
        as_of: timestamp,
        freshness: 'available',
        is_fallback: false,
        is_stale: false,
        is_partial: false,
        is_synthetic: false,
        is_unavailable: false,
        confidence_weight: 1,
        coverage: 1,
      },
      data: homeHistoryData(),
    });
  });

  await page.route('**/api/v1/history/3**', async (route) => {
    await fulfillJson(route, {
      meta: {
        id: 3,
        queryId: 'q3',
        stockCode: 'ORCL',
        stockName: 'Oracle',
        companyName: 'Oracle Corporation',
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
        operationAdvice: '数据不足，结论仅供观察。',
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
            buildStrategy: 'Use mocked data only to review the research surface.',
          },
          reasonLayer: {
            coreReasons: ['Institutional sponsorship remains intact after earnings.'],
          },
          technicalFields: [
            { label: 'MACD', value: 'Second expansion above zero' },
            { label: 'Moving Averages', value: 'MA20 lifting MA60' },
          ],
        },
        analysisResult: {
          singleStockEvidencePacket: {
            packetState: 'observe_only',
            priceHistory: { status: 'available' },
            technicals: { status: 'available' },
            fundamentals: { status: 'degraded' },
            earnings: { status: 'pending' },
            news: { status: 'missing' },
            catalysts: { status: 'blocked' },
            valuation: { status: 'waiting' },
            fundamentalsEarnings: {
              normalizerState: 'insufficient',
              missingEvidence: ['roe', 'pb'],
              blockingReasons: ['partial_coverage'],
              evidenceLabels: [],
            },
            newsCatalysts: {
              topNewsItems: [{ headline: 'Oracle cloud backlog remains stable.' }],
              topCatalystItems: [],
              blockingReasons: ['provider_timeout'],
            },
          },
          researchReadiness: {
            contractVersion: 'research_readiness_v1',
            researchReady: false,
            readinessState: 'observe_only',
            verdictLabel: '仅观察',
            blockingReasons: [],
            missingEvidence: ['fundamentals', 'news'],
            consumerActionBoundary: 'no_advice',
            noAdviceBoundary: true,
          },
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
        technicals: { status: 'available', missingReasons: [], nextEvidenceNeeded: [] },
        fundamentals: {
          status: 'degraded',
          missingReasons: ['partial_coverage'],
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
        valuation: { status: 'not_applicable', missingReasons: [], nextEvidenceNeeded: [] },
      },
      evidenceCitationFrame: {
        frameState: 'partial',
        noAdviceBoundary: true,
        citedEvidence: [
          {
            domain: 'technicals',
            id: 'price-history:orcl',
            summary: '价格历史与技术面样本已用于受控阅读验证。',
          },
        ],
        domainCoverage: [
          { domain: 'technicals', status: 'available' },
          { domain: 'fundamentals', status: 'degraded' },
          { domain: 'news', status: 'missing' },
        ],
        missingEvidence: ['fundamentals', 'news'],
        nextEvidenceNeeded: ['补充基本面证据', '补充新闻证据'],
      },
    });
  });
}

function marketActionabilityPayload() {
  return {
    source: 'computed',
    sourceLabel: '系统计算',
    updatedAt: timestamp,
    asOf: timestamp,
    freshness: 'cached',
    isFallback: false,
    isStale: false,
    confidence: 0.82,
    reliableInputCount: 12,
    requiredReliableInputCount: 5,
    reliablePanelCount: 5,
    requiredReliablePanelCount: 3,
    fallbackInputCount: 1,
    excludedInputCount: 1,
    isReliable: true,
    temperatureAvailable: true,
    disabledReason: null,
    unavailableReason: null,
    insufficientReliableInputs: false,
    trustLevel: 'reliable',
    sourceTier: 'unofficial_public_api',
    conclusionAllowed: true,
    marketActionabilityFrame: {
      contractVersion: 'market_intelligence_actionability_v1',
      verdict: 'observe_only',
      confidence: {
        value: 0.41,
        label: 'low',
        capReasons: ['observation_only'],
      },
      evidenceCoverage: {
        scoreGradeCount: 2,
        observationOnlyCount: 1,
        missingCount: 0,
        totalCount: 3,
      },
      missingEvidence: [],
      regimeContext: {
        primaryRegime: 'risk_on_liquidity_expansion',
        liquidityImpulse: 'expanding_liquidity',
        rotationPosture: 'leading',
        contradictionCount: 1,
        freshnessFloor: 'delayed',
      },
      sourceAuthority: 'observationOnly',
      freshness: 'delayed',
      noAdviceBoundary: true,
      nextResearchStep: '继续确认流动性是否保持扩张',
      debugRef: 'market:temperature:actionability',
    },
    marketIntelligenceEvidenceFrame: {
      contractVersion: 'market_intelligence_evidence_v1',
      frameState: 'observe_only',
      evidenceCoverage: {
        scoreGradeCount: 3,
        observationOnlyCount: 2,
        missingCount: 0,
        totalCount: 5,
      },
      regimeEvidence: {
        domain: 'macro',
        state: 'score_grade',
        freshness: 'delayed',
        primaryRegime: 'risk_on_liquidity_expansion',
        blockingReasons: [],
      },
      liquidityEvidence: {
        domain: 'liquidity',
        state: 'observation_only',
        freshness: 'delayed',
        likelyDestination: 'broad_equities',
        blockingReasons: ['observation_only'],
      },
      rotationEvidence: {
        domain: 'rotation',
        state: 'observation_only',
        freshness: 'delayed',
        leadingThemeCount: 2,
        blockingReasons: ['observation_only'],
      },
      breadthEvidence: {
        domain: 'breadth',
        state: 'score_grade',
        freshness: 'delayed',
        breadthValue: 1.7,
        blockingReasons: [],
      },
      scannerContextEvidence: {
        domain: 'scanner_context',
        state: 'score_grade',
        freshness: 'delayed',
        readinessState: 'ready',
        noAdviceBoundary: true,
        blockingReasons: [],
      },
      missingEvidence: [],
      blockingReasons: ['observation_only'],
      sourceAuthority: 'observationOnly',
      freshness: 'delayed',
      nextEvidenceNeeded: [],
      noAdviceBoundary: true,
      debugRef: 'market:temperature:evidence',
    },
    marketDecisionSemantics: {
      version: 'market_decision_semantics_v1',
      posture: 'offensive',
      exposureBias: 'risk_on_watch',
      claimBoundary: 'research_only',
      noAdviceBoundary: true,
      summary: '仅供研究观察，不构成交易指令。',
    },
    scores: {
      overall: { value: 62, label: '偏暖', trend: 'improving', description: '风险偏好改善，但宏观压力仍需关注。' },
      usRiskAppetite: { value: 68, label: '偏暖', trend: 'improving', description: '美股指数与风险情绪同步改善。' },
      cnMoneyEffect: { value: 55, label: '中性', trend: 'stable', description: '指数表现尚可，但市场宽度一般。' },
      macroPressure: { value: 58, label: '中性偏高', trend: 'rising', description: '美元与利率走强。' },
      liquidity: { value: 52, label: '中性', trend: 'stable', description: '资金环境整体平稳。' },
    },
  };
}

async function installMarketActionabilityRoute(page: Page) {
  await installSignedInSessionRoutes(page);
  await page.route('**/api/v1/market/temperature', async (route) => {
    await fulfillJson(route, marketActionabilityPayload());
  });
}

function scannerRunsPayload() {
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
        run_at: timestamp,
        completed_at: timestamp,
        watchlist_date: '2026-06-04',
        trigger_mode: 'manual',
        universe_name: 'cn_a_liquid_watchlist_v1',
        shortlist_size: 1,
        universe_size: 320,
        preselected_size: 72,
        evaluated_size: 48,
        source_summary: 'Mocked scanner payload',
        headline: 'Mock scanner shortlist for controlled user testing',
        universe_type: 'theme',
        theme_id: 'ai_semiconductors',
        theme_label: 'AI 半导体',
        requested_symbols_count: 0,
        accepted_symbols_count: 0,
        rejected_symbols: [],
        top_symbols: ['NVDA'],
        notification_status: 'not_attempted',
        failure_reason: null,
      },
    ],
  };
}

function scannerRunDetailPayload() {
  return {
    id: 11,
    market: 'cn',
    profile: 'cn_preopen_v1',
    profile_label: 'A-share Pre-open v1',
    status: 'completed',
    run_at: timestamp,
    completed_at: timestamp,
    watchlist_date: '2026-06-04',
    trigger_mode: 'manual',
    universe_name: 'cn_a_liquid_watchlist_v1',
    shortlist_size: 1,
    universe_size: 320,
    preselected_size: 72,
    evaluated_size: 48,
    source_summary: 'Mocked scanner payload',
    headline: 'Mock scanner shortlist for controlled user testing',
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
        scan_timestamp: timestamp,
        diagnostics: {},
        candidateEvidenceFrame: {
          contractVersion: 'scanner_candidate_evidence_v1',
          coverageState: 'observe_only',
          domains: {
            technicals: { state: 'available', observationOnly: false },
            priceHistory: { state: 'available', observationOnly: false },
            liquidity: { state: 'partial', observationOnly: true },
            theme: { state: 'available', observationOnly: true },
            fundamentals: { state: 'missing', observationOnly: true },
            newsCatalyst: { state: 'missing', observationOnly: true },
          },
          coverage: {
            availableCount: 2,
            partialCount: 1,
            observeOnlyCount: 4,
            missingCount: 2,
            totalCount: 6,
          },
          noAdviceBoundary: true,
        },
        candidateResearchReadiness: {
          contractVersion: 'research_readiness_v1',
          researchReady: false,
          readinessState: 'observe_only',
          verdictLabel: '仅观察',
          blockingReasons: [],
          missingEvidence: ['fundamentals', 'newsCatalyst'],
          consumerActionBoundary: 'no_advice',
          noAdviceBoundary: true,
        },
      },
    ],
    summary: {
      selected_count: 1,
      rejected_count: 0,
      data_failed_count: 0,
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
        ],
      },
      universe_policy: {
        type: 'theme',
        label: 'Theme universe',
        blockers: [],
      },
      no_advice_boundary: true,
    },
  };
}

async function installScannerControlledRoutes(page: Page) {
  await installSignedInSessionRoutes(page);

  await page.route('**/api/v1/scanner/runs**', async (route) => {
    await fulfillJson(route, scannerRunsPayload());
  });

  await page.route('**/api/v1/scanner/watchlists/recent**', async (route) => {
    await fulfillJson(route, scannerRunsPayload());
  });

  await page.route('**/api/v1/scanner/runs/11**', async (route) => {
    await fulfillJson(route, scannerRunDetailPayload());
  });
}

function optionsUnderlying() {
  return {
    price: 52.34,
    change_pct: 1.2,
    source: 'playwright_fixture',
    as_of: timestamp,
    freshness: 'mock',
  };
}

function optionsMetadata() {
  return {
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

function symbolFromOptionsPath(path: string) {
  const match = path.match(/\/api\/v1\/options\/underlyings\/([^/]+)/);
  return decodeURIComponent(match?.[1] || 'TEM').toUpperCase();
}

function optionsReadiness() {
  return {
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
}

function optionsSummary(symbol: string) {
  return {
    symbol,
    market: 'us',
    underlying: optionsUnderlying(),
    options_availability: {
      supported: true,
      provider: 'playwright_fixture',
      limitations: ['mocked_controlled_user_testing'],
    },
    metadata: {
      read_only: true,
      no_external_calls_in_tests: true,
      limitations: ['mocked_controlled_user_testing'],
      source_label: 'Playwright Fixture',
      updated_at: timestamp,
    },
    options_readiness: optionsReadiness(),
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
        as_of: timestamp,
        source: 'playwright_fixture',
        warnings: ['mocked_chain'],
      },
    ],
    metadata: optionsMetadata(),
  };
}

function optionsChain(symbol: string) {
  return {
    symbol,
    expiration: '2026-06-19',
    underlying: optionsUnderlying(),
    calls: [optionContract(symbol, 'call', 55, 4.23), optionContract(symbol, 'call', 60, 2.28)],
    puts: [optionContract(symbol, 'put', 50, 2.42), optionContract(symbol, 'put', 45, 1.16)],
    filters_applied: { min_open_interest: 100, max_spread_pct: 25 },
    chain_as_of: timestamp,
    source: 'playwright_fixture',
    limitations: ['mocked_chain'],
    metadata: optionsMetadata(),
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
    limitations: ['mocked_controlled_user_testing'],
    no_advice_disclosure: 'Scenario analysis only; not personalized financial advice.',
  };
}

function strategyComparison(symbol: string) {
  return {
    symbol,
    underlying: optionsUnderlying(),
    assumptions: { direction: 'bullish', target_price: 65, target_date: '2026-08-21' },
    strategies: ['long_call', 'long_put', 'bull_call_spread', 'bear_put_spread'].map(strategy),
    limitations: ['mocked_controlled_user_testing'],
    metadata: optionsMetadata(),
    optionsConsumerScenarioFrame: optionsScenarioEvidenceFrame(),
  };
}

function optionsScenarioEvidenceFrame() {
  return {
    contractVersion: 'options-consumer-scenario-frame-v1',
    frameState: 'blocked',
    scenarioCoverage: 'strategy_compare_ready',
    chainQuality: {
      hasChain: true,
      contractCount: 4,
      callCount: 2,
      putCount: 2,
      freshness: 'synthetic_delayed',
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
      candidateCount: 4,
      comparisonState: 'strategy_compare_ready',
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
      riskProfile: 'balanced',
      targetPriceStatus: 'target_above_breakeven',
    },
    missingEvidence: ['provider authority', 'iv greeks', 'bid ask'],
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

function decision(symbol: string) {
  return {
    symbol,
    strategy: 'bull_call_spread',
    data_quality: {
      data_quality_score: 62,
      data_quality_tier: 'synthetic_demo_only',
      source_type: 'playwright_fixture',
      as_of_age_minutes: 0,
      blocking_reasons: ['mocked_controlled_user_testing'],
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
          primary_reasons: ['mocked_controlled_user_testing'],
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
    primary_reasons: ['mocked_controlled_user_testing'],
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
    metadata: optionsMetadata(),
    optionsConsumerScenarioFrame: optionsScenarioEvidenceFrame(),
  };
}

async function installOptionsControlledRoutes(page: Page) {
  await installSignedInSessionRoutes(page);
  const calls: string[] = [];

  await page.route('**/api/v1/options/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const symbol = symbolFromOptionsPath(path);
    calls.push(`${method} ${path}`);

    if (method === 'GET' && path.match(/^\/api\/v1\/options\/underlyings\/[^/]+\/summary$/)) {
      return fulfillJson(route, optionsSummary(symbol));
    }
    if (method === 'GET' && path.match(/^\/api\/v1\/options\/underlyings\/[^/]+\/expirations$/)) {
      return fulfillJson(route, optionsExpirations(symbol));
    }
    if (method === 'GET' && path.match(/^\/api\/v1\/options\/underlyings\/[^/]+\/chain$/)) {
      return fulfillJson(route, optionsChain(symbol));
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

  return {
    count(method: string, path: string) {
      return calls.filter((entry) => entry === `${method} ${path}`).length;
    },
    wasFetched(method: string, path: string) {
      return calls.includes(`${method} ${path}`);
    },
  };
}

appTest.describe('controlled user testing smoke pack', () => {
  appTest('Home: user can read research evidence, provenance/trust boundary, and technical chart', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    await page.setViewportSize(desktopViewport);
    await installHomeResearchRoutes(page);
    await page.goto('/zh');
    await page.waitForLoadState('domcontentloaded');

    const dashboard = page.getByTestId('home-bento-dashboard');
    await appExpect(dashboard).toBeVisible({ timeout: 15_000 });
    await appExpect(page.getByTestId('home-research-console')).toBeVisible();
    await appExpect(page.getByTestId('home-research-readiness-strip')).toContainText(/研究就绪度|仅观察|证据受限/);
    await appExpect(page.getByTestId('home-evidence-packet-strip')).toContainText('证据包摘要');
    await appExpect(page.getByTestId('home-evidence-coverage-strip')).toContainText('证据覆盖');
    await appExpect(page.getByTestId('home-research-trust-strip')).toBeVisible();
    await appExpect(page.getByTestId('home-research-chart-section')).toBeVisible();
    await appExpect(page.getByTestId('home-linear-technical-chart')).toHaveAttribute('data-chart-engine', 'echarts');
    await appExpect(page.getByTestId('home-candlestick-echarts-node')).toBeVisible();
    await appExpect(page.getByTestId('home-candlestick-chart-fallback')).toHaveCount(0);
    await appExpect(page.getByTestId('home-candlestick-unavailable')).toHaveCount(0);

    await expectConsumerSafeRegion(page.getByTestId('home-research-conclusion-console'));
    await expectConsumerSafeRegion(page.getByTestId('home-research-chart-section'));
    await expectNoHorizontalOverflow(page);
    appExpect(consoleErrors).toEqual([]);
    appExpect(unhandledApiRoutes).toEqual([]);
  });

  appTest('Market Overview: user can read actionability/readiness and visual evidence strip', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    await page.setViewportSize(desktopViewport);
    await installMarketActionabilityRoute(page);
    await page.goto('/zh/market-overview');
    await page.waitForLoadState('domcontentloaded');

    const shell = page.getByTestId('market-overview-shell');
    const readiness = page.getByTestId('market-overview-research-readiness-strip');
    const actionability = page.getByTestId('market-intelligence-actionability-strip');
    const visualStrip = page.getByTestId('market-overview-visual-evidence-strip');
    await appExpect(shell).toBeVisible({ timeout: 15_000 });
    await appExpect(readiness).toBeVisible();
    await appExpect(actionability).toBeVisible();
    await appExpect(actionability).toContainText('市场研判可用性');
    await appExpect(actionability).toContainText('仅观察');
    await appExpect(actionability).toContainText('仅供研究观察，不作为执行依据');
    await appExpect(visualStrip).toBeVisible();
    await appExpect(visualStrip).toContainText('核心图表证据');
    await appExpect(page.getByTestId('market-overview-visual-card-core-trends')).toBeVisible();
    await appExpect(page.getByTestId('market-overview-visual-card-risk-pressure')).toBeVisible();
    await appExpect(page.getByTestId('market-overview-visual-card-flow-rotation')).toBeVisible();

    await expectConsumerSafeRegion(readiness);
    await expectConsumerSafeRegion(actionability);
    await expectConsumerSafeRegion(visualStrip);
    await expectNoHorizontalOverflow(page);
    appExpect(consoleErrors).toEqual([]);
    appExpect(unhandledApiRoutes).toEqual([]);
  });

  appTest('Scanner: user can follow top-down context into a candidate evidence summary on a narrow viewport', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    await page.setViewportSize(narrowViewport);
    await installScannerControlledRoutes(page);
    await page.goto('/zh/scanner');
    await page.waitForLoadState('domcontentloaded');

    const workspace = page.getByTestId('user-scanner-workspace');
    const readiness = page.getByTestId('scanner-research-readiness-strip');
    const topDown = page.getByTestId('scanner-top-down-context-strip');
    const visualSummary = page.getByTestId('scanner-visual-evidence-summary');
    const candidate = page.getByTestId('scanner-result-row-NVDA');
    const candidateEvidence = page.getByTestId('scanner-inline-candidate-evidence-NVDA');

    await appExpect(workspace).toBeVisible({ timeout: 15_000 });
    await appExpect(readiness).toBeVisible();
    await appExpect(topDown).toBeVisible();
    await appExpect(topDown).toContainText('市场驱动因素');
    await appExpect(topDown).toContainText('市场：仅观察');
    await appExpect(topDown).toContainText('宏观：支持');
    await appExpect(topDown).toContainText('流动性：支持');
    await appExpect(visualSummary).toBeVisible();
    await appExpect(candidate).toBeVisible();
    await appExpect(candidateEvidence).toBeVisible();
    await appExpect(candidateEvidence).toContainText('仅观察');
    await appExpect(candidateEvidence).toContainText('待补 基本面 / 新闻催化');
    await appExpect(candidateEvidence).toContainText('技术面');
    await appExpect(candidateEvidence).toContainText('价格历史');

    await expectConsumerSafeRegion(readiness);
    await expectConsumerSafeRegion(topDown);
    await expectConsumerSafeRegion(visualSummary);
    await expectConsumerSafeRegion(candidateEvidence);
    await expectNoHorizontalOverflow(page);
    appExpect(consoleErrors).toEqual([]);
    appExpect(unhandledApiRoutes).toEqual([]);
  });

  appTest('Backtest: user can open a deterministic result and inspect research simulation visuals', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    await page.setViewportSize(desktopViewport);
    await installSignedInSessionRoutes(page);
    await page.goto('/zh/backtest/results/34');
    await page.waitForLoadState('domcontentloaded');

    const pageRoot = page.getByTestId('deterministic-backtest-result-page');
    await appExpect(pageRoot).toBeVisible({ timeout: 15_000 });
    await appExpect(page.getByTestId('deterministic-result-page-hero')).toContainText(/研究级回测|回测完成|ORCL/);
    await appExpect(page.getByTestId('deterministic-result-kpi-strip')).toBeVisible();
    await appExpect(page.getByTestId('backtest-result-report')).toBeVisible({ timeout: 15_000 });
    await appExpect(page.getByTestId('backtest-report-summary')).toBeVisible();
    await appExpect(page.getByTestId('backtest-report-result-summary')).toContainText('研究结论');
    await appExpect(page.getByTestId('backtest-report-research-quality-review')).toContainText('研究复核清单');
    await appExpect(page.getByTestId('backtest-report-chart')).toBeVisible();
    await appExpect(page.getByTestId('deterministic-backtest-result-view')).toBeVisible();
    await appExpect(page.getByTestId('deterministic-backtest-chart-workspace')).toHaveAttribute('data-chart-engine', 'echarts');

    await expectConsumerSafeRegion(page.getByTestId('deterministic-result-page-hero'));
    await expectConsumerSafeRegion(page.getByTestId('backtest-report-summary'));
    await expectConsumerSafeRegion(page.getByTestId('backtest-report-chart'));
    await expectNoHorizontalOverflow(page);
    appExpect(consoleErrors).toEqual([]);
    appExpect(unhandledApiRoutes).toEqual([]);
  });
  appTest('Options Lab: user can inspect readiness, scenario evidence, payoff/IV visuals, and no-execution boundary', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    await page.setViewportSize(narrowViewport);
    const harness = await installOptionsControlledRoutes(page);
    await page.goto('/zh/options-lab');
    await page.waitForLoadState('domcontentloaded');

    const pageRoot = page.getByTestId('options-lab-page-root');
    const readiness = page.getByTestId('options-lab-research-readiness-strip');
    const gateSummary = page.getByTestId('options-lab-readiness-gate-summary');
    const scenarioEvidence = page.getByTestId('options-lab-scenario-evidence');
    const visualsPanel = page.getByTestId('options-lab-visuals-panel');
    const payoffVisual = page.getByTestId('options-lab-payoff-visual');
    const ivVisual = page.getByTestId('options-lab-iv-visual');
    const boundaryPanel = page.getByTestId('options-lab-risk-boundary-panel');

    await appExpect(pageRoot).toBeVisible({ timeout: 15_000 });
    await appExpect(readiness).toBeVisible();
    await appExpect(gateSummary).toBeVisible();
    await appExpect(gateSummary).toContainText('门控摘要');
    await appExpect(scenarioEvidence).toBeVisible();
    await appExpect(scenarioEvidence).toContainText('情景证据');
    await appExpect(scenarioEvidence).toContainText('已阻断');
    await appExpect(scenarioEvidence).toContainText('授权链路待补证');
    await appExpect(scenarioEvidence).toContainText('只读边界');
    await appExpect(visualsPanel).toBeVisible();
    await appExpect(visualsPanel).toContainText('收益边界与 IV 快照');
    await appExpect(payoffVisual).toBeVisible();
    await appExpect(ivVisual).toBeVisible();
    await appExpect(scenarioEvidence).toContainText(/不触发执行|不改动现有持仓/);
    await appExpect(boundaryPanel).toContainText(/仅供情景观察|暂不形成结论/);

    await expectConsumerSafeRegion(readiness);
    await expectConsumerSafeRegion(gateSummary);
    await expectConsumerSafeRegion(scenarioEvidence);
    await expectConsumerSafeRegion(visualsPanel);
    await expectConsumerSafeRegion(boundaryPanel);
    await appExpect
      .poll(async () => page.evaluate(() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)))
      .toBeLessThanOrEqual(1);
    appExpect(harness.count('POST', '/api/v1/options/strategies/compare')).toBeGreaterThan(0);
    appExpect(harness.count('POST', '/api/v1/options/decision/evaluate')).toBeGreaterThan(0);
    appExpect(harness.wasFetched('POST', '/api/v1/orders')).toBe(false);
    appExpect(harness.wasFetched('POST', '/api/v1/broker/connect')).toBe(false);
    appExpect(harness.wasFetched('POST', '/api/v1/portfolio/mutate')).toBe(false);
    appExpect(consoleErrors).toEqual([]);
    appExpect(unhandledApiRoutes).toEqual([]);
  });
});
