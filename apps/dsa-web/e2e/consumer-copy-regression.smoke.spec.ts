import type { Locator, Page, Route } from '@playwright/test';
import { expect as baseExpect, expect as pwExpect } from '@playwright/test';
import { expect as appExpect, test as appTest } from './fixtures/appSmoke';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
] as const;

const forbiddenInternalPattern =
  /(?:^|[\s_-])(raw|debug|payload|prompt|env|trace|credential)(?:$|[\s_-])|providerRoute|sourceAuthority|provider\s+payload|cache\s+router|stack\s+trace/i;
const forbiddenTradingPattern =
  /小仓试错|第二笔|建仓|加仓|减仓|买入|卖出|下单|券商|\bbuy\b|\bsell\b|\border\b|\bbroker\b/i;
const optionsTimestamp = '2026-05-06T09:45:00-04:00';
const optionsExpiration = '2026-06-19';

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function openSignedInRoute(page: Page, path: string) {
  await page.goto(path);
  await page.waitForLoadState('domcontentloaded');
}

async function installSignedInSessionRoutes(page: Page) {
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

function sanitizeAllowedComplianceCopy(text: string): string {
  return text
    .replaceAll('不构成交易指令', '')
    .replaceAll('不构成下单指令', '')
    .replaceAll('不构成交易或下单指令', '')
    .replaceAll('不构成交易/下单指令', '')
    .replaceAll('仅供研究观察，不构成交易指令。', '')
    .replaceAll('仅做只读情景分析，不构成交易或下单指令。', '')
    .replaceAll('仅做只读情景分析，不构成交易/下单指令。', '')
    .replaceAll('控制区只记录假设；数据是否可判断以后续准备度和风险边界为准，不构成交易或下单指令。', '')
    .replaceAll('控制区只记录假设；数据是否可判断以后续准备度和风险边界为准，不构成交易/下单指令。', '')
    .replaceAll('仅做只读情景分析，。', '');
}

async function expectConsumerSafeSurface(surface: Locator) {
  const text = sanitizeAllowedComplianceCopy(await surface.innerText());
  pwExpect(text).not.toMatch(forbiddenInternalPattern);
  pwExpect(text).not.toMatch(forbiddenTradingPattern);
}

async function expectNoHorizontalOverflow(page: Page) {
  await baseExpect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function installAuthenticatedHomeEvidenceRoutes(page: Page) {
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

  await page.route('**/api/v1/history/3', async (route) => {
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
        },
      },
    });
  });
}

function actionabilityReadyPayload() {
  return {
    source: 'computed',
    sourceLabel: '系统计算',
    updatedAt: '2026-06-04T09:00:00Z',
    asOf: '2026-06-04T09:00:00Z',
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
    regimeSummary: {
      headline: '风险偏好改善但仍需确认',
      detail: '流动性与宽度改善，轮动仍偏观察。',
      riskLevel: 'medium',
    },
    marketRegimeSynthesis: {
      regime: 'risk_on_liquidity_expansion',
      summary: '流动性改善，风险偏好修复。',
      confidence: 0.64,
    },
    marketDecisionSemantics: {
      version: 'market_decision_semantics_v1',
      posture: 'offensive',
      postureConfidence: {
        value: 64,
        label: 'medium',
        capReasons: ['counter_evidence_present'],
      },
      exposureBias: 'risk_on_watch',
      directionReadiness: {
        status: 'direction_ready',
        confidenceLabel: 'medium',
        scoreGradePillars: {
          count: 3,
          items: [],
        },
      },
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

async function installTemperatureOverride(page: Page) {
  await page.route('**/api/v1/market/temperature', async (route) => {
    await fulfillJson(route, actionabilityReadyPayload());
  });
}

function buildScannerRunDetailWithContext() {
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
        candidate_research_summary_frame: {
          contract_version: 'scanner_candidate_research_summary_v1',
          frame_state: 'observe_only',
          symbol: 'NVDA',
          rank: 1,
          primary_research_reason: '当前线索仅供观察，先作为候选研究摘要记录。',
          evidence_highlights: ['technicals available', 'theme context partial'],
          missing_evidence: ['fundamentals', 'news_catalyst'],
          blocking_reasons: ['observation_only'],
          top_down_context_refs: [
            { key: 'market_readiness', state: 'observe_only', label: '市场' },
            { key: 'macro_regime', state: 'supportive', label: '宏观' },
            { key: 'liquidity_frame', state: 'supportive', label: '流动性' },
            { key: 'theme_frame', state: 'observe_only', label: '主题' },
          ],
          source_authority: 'observationOnly',
          freshness: 'cached',
          next_research_step: '先补充基本面与新闻催化，再复核当前候选。',
          no_advice_boundary: true,
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
  };
}

function buildScannerRunsPayload() {
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
      },
    ],
  };
}

async function installScannerContextRoutes(page: Page) {
  await installSignedInSessionRoutes(page);

  await page.route('**/api/v1/scanner/runs**', async (route) => {
    await fulfillJson(route, buildScannerRunsPayload());
  });

  await page.route('**/api/v1/scanner/watchlists/recent**', async (route) => {
    await fulfillJson(route, buildScannerRunsPayload());
  });

  await page.route('**/api/v1/scanner/runs/11**', async (route) => {
    await fulfillJson(route, buildScannerRunDetailWithContext());
  });
}

function createSignedInUser() {
  return {
    id: 'user-1',
    username: 'wolfy-user',
    displayName: 'Wolfy User',
    role: 'user',
    isAdmin: false,
    isAuthenticated: true,
    transitional: false,
    authEnabled: true,
  };
}

function optionsUnderlying() {
  return {
    price: 52.34,
    change_pct: 1.2,
    source: 'playwright_fixture',
    as_of: optionsTimestamp,
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

function symbolFromPath(path: string) {
  const match = path.match(/\/api\/v1\/options\/underlyings\/([^/]+)/);
  return decodeURIComponent(match?.[1] || 'TEM').toUpperCase();
}

async function installOptionsRoutes(page: Page) {
  const signedInUser = createSignedInUser();
  const calls: string[] = [];

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

  await page.route('**/api/v1/options/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const symbol = symbolFromPath(path);
    calls.push(`${method} ${path}`);

    if (method === 'GET' && path.match(/^\/api\/v1\/options\/underlyings\/[^/]+\/summary$/)) {
      return fulfillJson(route, {
        symbol,
        market: 'us',
        underlying: optionsUnderlying(),
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
          updated_at: optionsTimestamp,
        },
      });
    }

    if (method === 'GET' && path.match(/^\/api\/v1\/options\/underlyings\/[^/]+\/expirations$/)) {
      return fulfillJson(route, {
        symbol,
        expirations: [
          {
            date: optionsExpiration,
            dte: 44,
            type: 'monthly',
            chain_available: true,
            as_of: optionsTimestamp,
            source: 'playwright_fixture',
            warnings: ['mocked_chain'],
          },
        ],
        metadata: {
          read_only: true,
          no_external_calls_in_tests: true,
          limitations: ['mocked_playwright_product_auth'],
          source_label: 'Playwright Fixture',
          updated_at: optionsTimestamp,
        },
      });
    }

    if (method === 'GET' && path.match(/^\/api\/v1\/options\/underlyings\/[^/]+\/chain$/)) {
      return fulfillJson(route, {
        symbol,
        expiration: optionsExpiration,
        underlying: optionsUnderlying(),
        calls: [optionContract(symbol, 'call', 55, 4.23), optionContract(symbol, 'call', 60, 2.28)],
        puts: [optionContract(symbol, 'put', 50, 2.42), optionContract(symbol, 'put', 45, 1.16)],
        filters_applied: { min_open_interest: 100, max_spread_pct: 25 },
        chain_as_of: optionsTimestamp,
        source: 'playwright_fixture',
        limitations: ['mocked_chain'],
        metadata: {
          read_only: true,
          no_external_calls_in_tests: true,
          limitations: ['mocked_playwright_product_auth'],
          source_label: 'Playwright Fixture',
          updated_at: optionsTimestamp,
        },
      });
    }

    if (method === 'POST' && path === '/api/v1/options/strategies/compare') {
      const payload = request.postDataJSON() as { symbol?: string; direction?: string; target_price?: number; target_date?: string } | null;
      const requestSymbol = (payload?.symbol || 'TEM').toUpperCase();
      return fulfillJson(route, {
        symbol: requestSymbol,
        underlying: optionsUnderlying(),
        assumptions: {
          direction: payload?.direction || 'bullish',
          target_price: payload?.target_price || 65,
          target_date: payload?.target_date || '2026-08-21',
        },
        strategies: ['long_call', 'long_put', 'bull_call_spread', 'bear_put_spread'].map((strategyType) => ({
          strategy_type: strategyType,
          legs: [
            {
              action: 'buy',
              side: strategyType.includes('put') ? 'put' : 'call',
              contract_symbol: `TEM260619${strategyType.includes('put') ? 'P' : 'C'}00055000`,
              expiration: optionsExpiration,
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
        })),
        limitations: ['mocked_product_route_harness'],
        metadata: optionsMetadata(),
      });
    }

    if (method === 'POST' && path === '/api/v1/options/decision/evaluate') {
      return fulfillJson(route, {
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
          as_of: optionsTimestamp,
        },
        metadata: optionsMetadata(),
      });
    }

    return fulfillJson(route, { error: `Unhandled options route: ${method} ${path}` }, 500);
  });

  return {
    count(method: string, path: string) {
      return calls.filter((entry) => entry === `${method} ${path}`).length;
    },
  };
}

appTest.describe('consumer copy regression smoke', () => {
  appTest('Home keeps citation, evidence, and no-advice copy consumer-safe', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await installAuthenticatedHomeEvidenceRoutes(page);
      await openSignedInRoute(page, '/zh');

      const dashboard = page.getByTestId('home-bento-dashboard');
      await appExpect(dashboard).toBeVisible({ timeout: 15_000 });
      const citationStrip = page.getByTestId('home-evidence-citation-strip');
      const evidenceStrip = page.getByTestId('home-evidence-packet-strip');
      await appExpect(evidenceStrip).toBeVisible();
      await appExpect(evidenceStrip).toContainText('证据包摘要');
      await appExpect(evidenceStrip).toContainText('数据不足，结论仅供观察');
      await appExpect(evidenceStrip).toContainText('仅供观察，不构成投资建议');
      if (await citationStrip.count()) {
        await appExpect(citationStrip).toContainText('证据引用');
        await appExpect(citationStrip).toContainText(/引用已整理|引用受限|引用待补/);
        await appExpect(citationStrip).toContainText('仅研究引用');
      }
      await expectConsumerSafeSurface(dashboard);
      await baseExpect(consoleErrors).toEqual([]);
      await baseExpect(unhandledApiRoutes).toEqual([]);
      await expectNoHorizontalOverflow(page);
    }
  });

  appTest('Market Overview keeps translated source labels and research-only copy bounded', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await installSignedInSessionRoutes(page);
      await installTemperatureOverride(page);
      await openSignedInRoute(page, '/zh/market-overview');

      const shell = page.getByTestId('market-overview-shell');
      await appExpect(shell).toBeVisible({ timeout: 15_000 });
      const strip = page.getByTestId('market-intelligence-actionability-strip');
      await appExpect(strip).toBeVisible();
      await appExpect(strip).toContainText('市场研判可用性');
      await appExpect(strip).toContainText('仅观察');
      await appExpect(strip).toContainText('来源级别');
      await appExpect(strip).toContainText('仅供研究观察，不作为执行依据');
      await appExpect(strip).toContainText('继续确认流动性是否保持扩张');
      await appExpect(shell).toContainText(/已使用最近一次可用数据|最近一次可用数据|更新中/);
      await strip.getByText('更多证据细节').click();
      await appExpect(strip).toContainText('来源级别 观察级');
      await expectConsumerSafeSurface(shell);
      await baseExpect(consoleErrors).toEqual([]);
      await baseExpect(unhandledApiRoutes).toEqual([]);
      await expectNoHorizontalOverflow(page);
    }
  });

  appTest('Scanner keeps candidate research summary and market drivers wording consumer-safe', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await installScannerContextRoutes(page);
      await page.goto('/zh/scanner');
      await page.waitForLoadState('domcontentloaded');

      const workspace = page.getByTestId('user-scanner-workspace');
      await appExpect(workspace).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('scanner-result-row-NVDA')).toBeVisible();
      const topDownStrip = page.getByTestId('scanner-top-down-context-strip');
      await appExpect(topDownStrip).toBeVisible();
      await appExpect(topDownStrip).toContainText('市场驱动因素');
      await appExpect(topDownStrip).toContainText('市场：仅观察');
      await appExpect(topDownStrip).toContainText('边界：仅研究观察');
      const candidateSummary = viewport.width >= 768
        ? page.getByTestId('scanner-candidate-summary-row-NVDA')
        : page.getByTestId('scanner-candidate-summary-mobile-row-NVDA');
      await appExpect(candidateSummary).toBeVisible();
      await appExpect(candidateSummary).toContainText('当前线索仅供观察');
      await appExpect(candidateSummary).toContainText('基本面 / 新闻催化');
      await appExpect(candidateSummary).toContainText(/观察级线索|缓存更新|仅研究观察/);
      await expectConsumerSafeSurface(workspace);
      await baseExpect(consoleErrors).toEqual([]);
      await baseExpect(unhandledApiRoutes).toEqual([]);
      await expectNoHorizontalOverflow(page);
    }
  });
  appTest('Options Lab keeps non-decision copy and read-only boundaries consumer-safe', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await installOptionsRoutes(page);
      await page.goto('/zh/options-lab');
      await page.waitForLoadState('domcontentloaded');

      const pageRoot = page.getByTestId('options-lab-page-root');
      await appExpect(pageRoot).toBeVisible({ timeout: 15_000 });
      const hero = page.getByTestId('options-lab-product-hero');
      const decisionEngine = page.getByTestId('options-lab-decision-engine');
      const boundaryPanel = page.getByTestId('options-lab-risk-boundary-panel');
      await appExpect(hero).toBeVisible();
      await appExpect(decisionEngine).toBeVisible();
      await appExpect(boundaryPanel).toBeVisible();
      await appExpect(decisionEngine).toContainText(/数据不足，暂不形成结论|情景分析已暂停/);
      await appExpect(boundaryPanel).toContainText('未达到可判断等级，仅供情景观察，暂不形成结论。');
      await appExpect(boundaryPanel).toContainText('仅供观察，不作为结论依据');
      await appExpect(pageRoot).toContainText('不构成交易或下单指令');
      await expectConsumerSafeSurface(pageRoot);
      pwExpect(harness.count('POST', '/api/v1/options/strategies/compare')).toBeGreaterThan(0);
      pwExpect(harness.count('POST', '/api/v1/options/decision/evaluate')).toBeGreaterThan(0);
      pwExpect(consoleErrors).toEqual([]);
      pwExpect(unhandledApiRoutes).toEqual([]);
      await expectNoHorizontalOverflow(page);
    }
  });
});
