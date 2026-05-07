import { expect, test as base, type Page, type Route } from '@playwright/test';

type AppSmokeFixtures = {
  consoleErrors: string[];
  unhandledApiRoutes: string[];
};

const timestamp = '2026-05-02T09:00:00Z';

function createScannerCandidate(index: number, overrides: Partial<Record<string, unknown>> = {}) {
  const symbol = typeof overrides.symbol === 'string' ? overrides.symbol : `MOCK${index}`;
  const name = typeof overrides.name === 'string' ? overrides.name : `Mock Candidate ${index}`;
  return {
    symbol,
    name,
    company_name: typeof overrides.company_name === 'string' ? overrides.company_name : `${name} Holdings`,
    rank: typeof overrides.rank === 'number' ? overrides.rank : index,
    score: typeof overrides.score === 'number' ? overrides.score : 95 - index,
    quality_hint: 'Liquid and trend-aligned',
    reason_summary: `${symbol} keeps relative strength and breadth support.`,
    reasons: [`${symbol} is holding above the recent breakout range.`],
    key_metrics: [
      { label: 'Entry range', value: `${100 + index}-${102 + index}` },
      { label: 'Target price', value: `${112 + index}` },
      { label: 'Stop loss', value: `${96 + index}` },
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
    last_trade_date: '2026-05-01',
    scan_timestamp: timestamp,
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
      anchor_date: '2026-05-01',
      window_end_date: '2026-05-04',
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
    ...overrides,
  };
}

const scannerShortlist = [
  createScannerCandidate(1, { symbol: 'NVDA', name: 'NVIDIA', company_name: 'NVIDIA Corp', score: 98 }),
  ...Array.from({ length: 17 }, (_, index) => createScannerCandidate(index + 2)),
];

const scannerRunDetail = {
  id: 11,
  market: 'cn',
  profile: 'cn_preopen_v1',
  profile_label: 'A-share Pre-open v1',
  status: 'completed',
  run_at: timestamp,
  completed_at: timestamp,
  watchlist_date: '2026-05-02',
  trigger_mode: 'manual',
  universe_name: 'cn_a_liquid_watchlist_v1',
  shortlist_size: scannerShortlist.length,
  universe_size: 320,
  preselected_size: 72,
  evaluated_size: 48,
  source_summary: 'Mocked scanner payload',
  headline: 'Mock scanner shortlist for Playwright smoke verification',
  universe_notes: ['Mocked universe for UI smoke tests.'],
  scoring_notes: ['Mocked scores keep scroll behavior stable.'],
  universe_type: 'default',
  theme_id: 'ai_semis',
  theme_label: 'AI Semiconductors',
  requested_symbols_count: 0,
  accepted_symbols_count: 0,
  rejected_symbols: [],
  diagnostics: {
    coverage_summary: {
      input_universe_size: 320,
      eligible_after_universe_fetch: 300,
      eligible_after_liquidity_filter: 244,
      eligible_after_data_availability_filter: 192,
      ranked_candidate_count: 48,
      shortlisted_count: scannerShortlist.length,
      excluded_total: 128,
      excluded_by_reason: [{ reason: 'missing_history', label: 'Missing history', count: 9 }],
      likely_bottleneck: 'data_availability',
      likely_bottleneck_label: 'Data availability',
    },
    provider_diagnostics: {
      configured_primary_provider: 'mock',
      quote_source_used: 'mock_quotes',
      snapshot_source_used: 'mock_snapshot',
      history_source_used: 'fallback_history',
      providers_used: ['mock'],
      fallback_occurred: true,
      fallback_count: 1,
      provider_failure_count: 1,
      missing_data_symbol_count: 2,
      provider_warnings: ['provider_unavailable_mocked_safety_state'],
    },
    universe_selection: {
      universe_type: 'default',
      theme_id: 'ai_semis',
      theme_label: 'AI Semiconductors',
      requested_symbols_count: 0,
      accepted_symbols_count: 0,
      rejected_symbols: [],
      universe_notes: ['Theme selection mocked for E2E smoke coverage.'],
    },
  },
  notification: {
    attempted: false,
    status: 'not_attempted',
    success: null,
    channels: [],
    message: null,
    report_path: null,
    sent_at: null,
  },
  failure_reason: null,
  comparison_to_previous: {
    available: true,
    previous_run_id: 10,
    previous_watchlist_date: '2026-05-01',
    new_count: 4,
    retained_count: 10,
    dropped_count: 2,
    new_symbols: [{ symbol: 'NVDA', name: 'NVIDIA', current_rank: 1, previous_rank: null, rank_delta: null }],
    retained_symbols: [],
    dropped_symbols: [],
  },
  review_summary: {
    available: true,
    review_window_days: 3,
    review_status: 'reviewed',
    candidate_count: scannerShortlist.length,
    reviewed_count: 12,
    pending_count: 6,
    hit_rate_pct: 58,
    outperform_rate_pct: 41,
    avg_same_day_close_return_pct: 0.8,
    avg_review_window_return_pct: 1.9,
    avg_max_favorable_move_pct: 3.7,
    avg_max_adverse_move_pct: -1.2,
    strong_count: 6,
    mixed_count: 5,
    weak_count: 1,
    best_symbol: 'NVDA',
    best_return_pct: 4.2,
    weakest_symbol: 'MOCK9',
    weakest_return_pct: -0.8,
  },
  shortlist: scannerShortlist,
};

const scannerRuns = {
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
      watchlist_date: '2026-05-02',
      trigger_mode: 'manual',
      universe_name: 'cn_a_liquid_watchlist_v1',
      shortlist_size: scannerShortlist.length,
      universe_size: 320,
      preselected_size: 72,
      evaluated_size: 48,
      source_summary: 'Mocked scanner payload',
      headline: 'Mock scanner shortlist for Playwright smoke verification',
      universe_type: 'default',
      theme_id: 'ai_semis',
      theme_label: 'AI Semiconductors',
      requested_symbols_count: 0,
      accepted_symbols_count: 0,
      rejected_symbols: [],
      top_symbols: scannerShortlist.slice(0, 6).map((candidate) => candidate.symbol),
      notification_status: 'not_attempted',
      failure_reason: null,
      change_summary: scannerRunDetail.comparison_to_previous,
      review_summary: scannerRunDetail.review_summary,
    },
  ],
};

const scannerThemes = {
  items: [
    {
      id: 'ai_semis',
      label_zh: 'AI 半导体',
      label_en: 'AI Semiconductors',
      market: 'cn',
      description: 'Mocked theme for Playwright smoke coverage.',
      symbols: ['NVDA', 'MOCK2', 'MOCK3'],
      aliases: ['semis'],
      tags: ['ai', 'chips'],
      source: 'mock',
      version: '1',
      is_seed_list: true,
      requires_manual_maintenance: false,
      criteria_prompt: 'Mock prompt',
      generated_at: timestamp,
      updated_at: timestamp,
      refresh_policy: 'manual',
      ai_metadata: {},
    },
  ],
};

function panel(panelName: string, symbol: string, label: string, value: number, changePct: number) {
  return {
    panelName,
    lastRefreshAt: timestamp,
    status: 'success',
    source: 'mock',
    sourceLabel: 'Mock feed',
    updatedAt: timestamp,
    asOf: timestamp,
    freshness: 'mock',
    isFallback: false,
    isStale: false,
    items: [
      {
        symbol,
        label,
        value,
        unit: 'pts',
        changePct,
        riskDirection: changePct >= 0 ? 'decreasing' : 'increasing',
        trend: [value * 0.96, value * 0.98, value],
        source: 'mock',
        sourceLabel: 'Mock feed',
        updatedAt: timestamp,
        asOf: timestamp,
        freshness: 'mock',
        isFallback: false,
        isStale: false,
      },
    ],
  };
}

function marketSnapshot(panelName: string, items: Array<{ symbol: string; label: string; value: number; changePercent: number }>) {
  return {
    items: items.map((item) => ({
      symbol: item.symbol,
      label: item.label,
      value: item.value,
      changePercent: item.changePercent,
      unit: 'pts',
      sparkline: [item.value * 0.97, item.value * 0.985, item.value],
      source: 'mock',
      sourceLabel: 'Mock feed',
      sourceType: 'mock',
      updatedAt: timestamp,
      asOf: timestamp,
      freshness: 'mock',
      isFallback: false,
      isStale: false,
    })),
    lastUpdate: timestamp,
    updatedAt: timestamp,
    source: 'mock',
    sourceLabel: 'Mock feed',
    sourceType: 'mock',
    asOf: timestamp,
    freshness: 'mock',
    isFallback: false,
    isStale: false,
    isRefreshing: false,
    warning: null,
    logSessionId: `${panelName}-log`,
  };
}

const mockCryptoStreamPayload = marketSnapshot('CryptoCard', [
  { symbol: 'BTC', label: 'Bitcoin', value: 98400, changePercent: 1.3 },
  { symbol: 'ETH', label: 'Ethereum', value: 3410, changePercent: 0.9 },
]);

function historyListPayload() {
  return {
    total: 3,
    page: 1,
    limit: 20,
    items: [
      { id: 3, queryId: 'q3', stockCode: 'ORCL', stockName: 'Oracle', companyName: 'Oracle', createdAt: '2026-04-27T08:00:00Z', generatedAt: '2026-04-27T08:03:00Z', isTest: false },
      { id: 2, queryId: 'q2', stockCode: 'TSLA', stockName: 'Tesla', companyName: 'Tesla', createdAt: '2026-04-27T07:00:00Z', generatedAt: '2026-04-27T07:05:00Z', isTest: false },
      { id: 1, queryId: 'q1', stockCode: 'NVDA', stockName: 'NVIDIA', companyName: 'NVIDIA', createdAt: '2026-04-27T06:00:00Z', generatedAt: '2026-04-27T06:04:00Z', isTest: false },
    ],
  };
}

function historyDetailPayload() {
  return {
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
  };
}

function historyNewsPayload() {
  return { total: 0, items: [] };
}

function historyMarkdownPayload() {
  return { content: '# ORCL\n\nFixture report.' };
}

function analysisTaskProgressPayload() {
  return {
    taskId: 'task-1',
    stockCode: 'ORCL',
    stockName: 'Oracle',
    status: 'processing',
    progress: 18,
    message: 'Running AI analysis',
    modules: [],
  };
}

function marketUsBreadthPayload() {
  return {
    panelName: 'UsBreadthCard',
    lastRefreshAt: timestamp,
    status: 'success',
    source: 'yahoo',
    sourceLabel: 'Yahoo Finance',
    updatedAt: timestamp,
    asOf: timestamp,
    freshness: 'delayed',
    isFallback: false,
    isStale: false,
    items: [
      {
        symbol: 'SECTORS_UP',
        label: 'Sectors Up',
        value: 8,
        unit: 'pts',
        changePct: 0,
        riskDirection: 'decreasing',
        trend: [7.5, 7.8, 8],
        source: 'yahoo',
        sourceLabel: 'Yahoo Finance',
        sourceType: 'market_snapshot',
        updatedAt: timestamp,
        asOf: timestamp,
        freshness: 'delayed',
        isFallback: false,
        isStale: false,
      },
      {
        symbol: 'STRONGEST_SECTOR',
        label: 'Strongest XLK',
        value: 1.8,
        unit: 'pts',
        changePct: 1.8,
        riskDirection: 'decreasing',
        trend: [1.6, 1.7, 1.8],
        source: 'yahoo',
        sourceLabel: 'Yahoo Finance',
        sourceType: 'market_snapshot',
        updatedAt: timestamp,
        asOf: timestamp,
        freshness: 'delayed',
        isFallback: false,
        isStale: false,
      },
    ],
  };
}

function analysisTasksPayload() {
  return {
    total: 1,
    pending: 0,
    processing: 1,
    tasks: [
      {
        taskId: 'task-1',
        stockCode: 'ORCL',
        stockName: 'Oracle',
        status: 'processing',
        progress: 18,
        message: 'Running AI analysis',
        reportType: 'detailed',
        createdAt: '2026-05-06T09:00:00Z',
        progressModules: [],
      },
    ],
  };
}

function agentSkillsPayload() {
  return {
    skills: [
      { id: 'bull_trend', name: '趋势分析', description: '测试技能' },
      { id: 'ma_cross', name: '均线金叉', description: '均线测试' },
      { id: 'volume_breakout', name: '放量突破', description: '突破测试' },
      { id: 'leader_strategy', name: '龙头策略', description: '龙头测试' },
    ],
    default_skill_id: 'bull_trend',
  };
}

function agentModelsPayload() {
  return {
    models: [
      { deployment_id: 'auto', model: 'deepseek-chat', provider: 'DeepSeek', source: 'env', is_primary: true },
    ],
  };
}

function agentProviderHealthPayload() {
  return {
    routingMode: 'AUTO',
    currentProvider: 'DeepSeek',
    currentModel: 'deepseek-chat',
    providers: [
      { id: 'deepseek', label: 'DeepSeek', status: 'available', model: 'deepseek-chat', selected: true },
      { id: 'openai', label: 'OpenAI', status: 'not_configured' },
      { id: 'gemini', label: 'Gemini', status: 'offline' },
      { id: 'local', label: 'Local', status: 'unknown' },
    ],
  };
}

function agentStockEvidencePayload() {
  return {
    symbols: ['ORCL'],
    items: [
      {
        symbol: 'ORCL',
        market: 'US',
        quote: {
          status: 'stale',
          price: 128.42,
          change_pct: 0.97,
          currency: 'USD',
          provider: 'playwright_fixture_stale_quote',
          updated_at: '2026-05-03T20:00:00Z',
        },
        technical: {
          status: 'fallback',
          trend: 'neutral',
          ma20: 123.4,
          rsi14: 58.2,
          provider: 'fallback_technical_fixture',
          updated_at: '2026-05-02',
        },
        fundamental: {
          status: 'partial',
          pe_ttm: 35.21,
          pb: 11.13,
          provider: 'analysis_history',
          missing_fields: ['marketCap', 'revenueTtm'],
          updated_at: '2026-05-02T12:00:00Z',
        },
        news: {
          status: 'error',
          provider: 'provider_unavailable',
        },
      },
    ],
    meta: { source: 'read_only_playwright_fixture', generated_at: timestamp },
  };
}

function portfolioSnapshotPayload() {
  return {
    as_of: '2026-05-06',
    accounts: [
      {
        account_id: 1,
        account_name: 'Main',
        positions: [
          { symbol: 'AAPL', market: 'us', quantity: 3, last_price: 200, market_value_base: 600 },
        ],
      },
    ],
  };
}

function ruleBacktestRunsPayload() {
  return {
    total: 1,
    page: 1,
    limit: 1,
    items: [
      { id: 34, code: 'ORCL', status: 'completed', total_return_pct: 12.3, max_drawdown_pct: -4.2, completed_at: timestamp },
    ],
  };
}

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installMockApi(page: Page, unhandledApiRoutes: string[]) {
  let isLoggedIn = false;

  await page.addInitScript((eventSourcePayload) => {
    let clipboardText = '';
    Object.defineProperty(window.navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: async (text: string) => {
          clipboardText = text;
          (window as typeof window & { __pwClipboardText?: string }).__pwClipboardText = text;
        },
        readText: async () => clipboardText,
      },
    });

    class MockEventSource extends EventTarget {
      url: string;
      withCredentials: boolean;
      readyState: number;
      onopen: ((event: Event) => void) | null;
      onmessage: ((event: MessageEvent<string>) => void) | null;
      onerror: ((event: Event) => void) | null;

      constructor(url: string, init?: { withCredentials?: boolean }) {
        super();
        this.url = url;
        this.withCredentials = Boolean(init?.withCredentials);
        this.readyState = 1;
        this.onopen = null;
        this.onmessage = null;
        this.onerror = null;

        window.setTimeout(() => {
          const openEvent = new Event('open');
          this.onopen?.(openEvent);
          this.dispatchEvent(openEvent);

          const messageEvent = new MessageEvent('message', {
            data: JSON.stringify(eventSourcePayload),
          });
          this.onmessage?.(messageEvent);
          this.dispatchEvent(messageEvent);
        }, 50);
      }

      close() {
        this.readyState = 2;
      }
    }

    Object.defineProperty(window, 'EventSource', {
      configurable: true,
      writable: true,
      value: MockEventSource,
    });
  }, mockCryptoStreamPayload);

  await page.context().route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    if (method === 'GET' && path.startsWith('/api/v1/auth/status')) {
      return fulfillJson(route, {
        authEnabled: true,
        loggedIn: isLoggedIn,
        passwordSet: true,
        passwordChangeable: isLoggedIn,
        setupState: 'enabled',
        currentUser: isLoggedIn ? {
          id: 'user-1',
          username: 'wolfy-user',
          displayName: 'Wolfy User',
          role: 'user',
          isAdmin: false,
          isAuthenticated: true,
          transitional: false,
          authEnabled: true,
        } : null,
      });
    }

    if (method === 'POST' && path.startsWith('/api/v1/auth/logout')) {
      isLoggedIn = false;
      return fulfillJson(route, { ok: true });
    }

    if (method === 'POST' && path.startsWith('/api/v1/auth/login')) {
      isLoggedIn = true;
      return fulfillJson(route, { ok: true });
    }

    if (method === 'GET' && path === '/api/v1/agent/status') {
      return fulfillJson(route, { enabled: false });
    }

    if (method === 'GET' && path === '/api/v1/agent/skills') {
      return fulfillJson(route, agentSkillsPayload());
    }

    if (method === 'GET' && path === '/api/v1/agent/models') {
      return fulfillJson(route, agentModelsPayload());
    }

    if (method === 'GET' && path === '/api/v1/agent/provider-health') {
      return fulfillJson(route, agentProviderHealthPayload());
    }

    if (method === 'GET' && path === '/api/v1/agent/stock-evidence') {
      return fulfillJson(route, agentStockEvidencePayload());
    }

    if (method === 'GET' && path === '/api/v1/agent/chat/sessions') {
      return fulfillJson(route, {
        sessions: [
          { session_id: 'session-1', title: 'Fixture safety chat', message_count: 0, created_at: timestamp, last_active: timestamp },
        ],
      });
    }

    if (method === 'GET' && path === '/api/v1/agent/chat/sessions/session-1') {
      return fulfillJson(route, { messages: [] });
    }

    if (method === 'GET' && path === '/api/v1/scanner/themes') {
      return fulfillJson(route, scannerThemes);
    }

    if (method === 'POST' && path === '/api/v1/scanner/themes') {
      return fulfillJson(route, {
        theme: scannerThemes.items[0],
        suggestions: [],
        message: 'Mock theme created.',
      });
    }

    if (method === 'GET' && path === '/api/v1/scanner/runs') {
      return fulfillJson(route, scannerRuns);
    }

    if (method === 'GET' && path === '/api/v1/scanner/runs/11') {
      return fulfillJson(route, scannerRunDetail);
    }

    if (method === 'GET' && path === '/api/v1/scanner/watchlists/recent') {
      return fulfillJson(route, scannerRuns);
    }

    if (method === 'POST' && path === '/api/v1/scanner/run') {
      return fulfillJson(route, scannerRunDetail);
    }

    if (method === 'GET' && path === '/api/v1/watchlist/items') {
      return fulfillJson(route, { items: [] });
    }

    if (method === 'POST' && path === '/api/v1/watchlist/items') {
      return fulfillJson(route, {
        id: 2001,
        symbol: 'NVDA',
        market: 'cn',
        source: 'scanner',
        created_at: timestamp,
        updated_at: timestamp,
      });
    }

    if (method === 'DELETE' && path.startsWith('/api/v1/watchlist/items/')) {
      return fulfillJson(route, { deleted: 1 });
    }

    if (method === 'POST' && path === '/api/v1/analysis/analyze') {
      return fulfillJson(route, {
        taskId: 'task-mock-1',
        status: 'accepted',
        message: 'Accepted',
      }, 202);
    }

    if (method === 'GET' && path === '/api/v1/portfolio/snapshot') {
      return fulfillJson(route, portfolioSnapshotPayload());
    }

    if (method === 'GET' && path === '/api/v1/backtest/rule/runs') {
      return fulfillJson(route, ruleBacktestRunsPayload());
    }

    if (method === 'GET' && path === '/api/v1/history') {
      return fulfillJson(route, historyListPayload());
    }

    if (method === 'GET' && path === '/api/v1/history/3') {
      return fulfillJson(route, historyDetailPayload());
    }

    if (method === 'GET' && path === '/api/v1/history/3/news') {
      return fulfillJson(route, historyNewsPayload());
    }

    if (method === 'GET' && path === '/api/v1/history/3/markdown') {
      return fulfillJson(route, historyMarkdownPayload());
    }

    if (method === 'GET' && path === '/api/v1/analysis/tasks') {
      return fulfillJson(route, analysisTasksPayload());
    }

    if (method === 'GET' && path === '/api/v1/analysis/tasks/task-1/progress') {
      return fulfillJson(route, analysisTaskProgressPayload());
    }

    if (method === 'GET' && path === '/api/v1/market-overview/indices') {
      return fulfillJson(route, panel('IndexTrendsCard', 'SPX', 'S&P 500', 5302, 1.2));
    }

    if (method === 'GET' && path === '/api/v1/market-overview/volatility') {
      return fulfillJson(route, panel('VolatilityCard', 'VIX', 'VIX Volatility', 14.2, -3.5));
    }

    if (method === 'GET' && path === '/api/v1/market-overview/funds-flow') {
      return fulfillJson(route, panel('FundsFlowCard', 'FLOW', 'Funds Flow', 82, 0.7));
    }

    if (method === 'GET' && path === '/api/v1/market-overview/macro') {
      return fulfillJson(route, {
        ...panel('MacroIndicatorsCard', 'US10Y', 'US 10Y', 4.31, -0.2),
        items: [
          {
            symbol: 'US10Y',
            label: 'US 10Y',
            value: 4.31,
            unit: '%',
            changePct: -0.2,
            riskDirection: 'decreasing',
            trend: [4.42, 4.37, 4.31],
            source: 'mock',
            sourceLabel: 'Mock feed',
            updatedAt: timestamp,
            asOf: timestamp,
            freshness: 'mock',
          },
          {
            symbol: 'DXY',
            label: 'Dollar Index',
            value: 104.4,
            unit: 'pts',
            changePct: 0.3,
            riskDirection: 'increasing',
            trend: [103.8, 104.1, 104.4],
            source: 'mock',
            sourceLabel: 'Mock feed',
            updatedAt: timestamp,
            asOf: timestamp,
            freshness: 'mock',
          },
        ],
      });
    }

    if (method === 'GET' && path === '/api/v1/market/crypto') {
      return fulfillJson(route, marketSnapshot('CryptoCard', [
        { symbol: 'BTC', label: 'Bitcoin', value: 98210, changePercent: 1.1 },
        { symbol: 'ETH', label: 'Ethereum', value: 3380, changePercent: 0.8 },
      ]));
    }

    if (method === 'GET' && path === '/api/v1/market/sentiment') {
      return fulfillJson(route, marketSnapshot('MarketSentimentCard', [
        { symbol: 'PUTCALL', label: 'Put/Call', value: 0.82, changePercent: -2.1 },
      ]));
    }

    if (method === 'GET' && path === '/api/v1/market/cn-indices') {
      return fulfillJson(route, marketSnapshot('ChinaIndicesCard', [
        { symbol: 'SHCOMP', label: 'Shanghai Composite', value: 3142, changePercent: 0.6 },
        { symbol: 'SZCOMP', label: 'Shenzhen Component', value: 9824, changePercent: 0.9 },
      ]));
    }

    if (method === 'GET' && path === '/api/v1/market/cn-breadth') {
      return fulfillJson(route, marketSnapshot('ChinaBreadthCard', [
        { symbol: 'ADVDEC', label: 'Adv/Dec', value: 2.4, changePercent: 1.1 },
      ]));
    }

    if (method === 'GET' && path === '/api/v1/market/cn-flows') {
      return fulfillJson(route, marketSnapshot('ChinaFlowsCard', [
        { symbol: 'NORTHBOUND', label: 'Northbound Flow', value: 48, changePercent: 2.3 },
      ]));
    }

    if (method === 'GET' && path === '/api/v1/market/sector-rotation') {
      return fulfillJson(route, marketSnapshot('SectorRotationCard', [
        { symbol: 'AI', label: 'AI Hardware', value: 72, changePercent: 1.4 },
      ]));
    }

    if (method === 'GET' && path === '/api/v1/market/rates') {
      return fulfillJson(route, marketSnapshot('RatesCard', [
        { symbol: 'US2Y', label: 'US 2Y', value: 4.78, changePercent: -0.2 },
      ]));
    }

    if (method === 'GET' && path === '/api/v1/market/fx-commodities') {
      return fulfillJson(route, marketSnapshot('FxCommoditiesCard', [
        { symbol: 'XAUUSD', label: 'Gold', value: 2312, changePercent: 0.4 },
        { symbol: 'USDCNH', label: 'USD/CNH', value: 7.21, changePercent: -0.1 },
      ]));
    }

    if (method === 'GET' && path === '/api/v1/market/temperature') {
      return fulfillJson(route, {
        source: 'computed',
        sourceLabel: 'Mock model',
        updatedAt: timestamp,
        asOf: timestamp,
        freshness: 'mock',
        isFallback: false,
        isStale: false,
        isRefreshing: false,
        confidence: 0.84,
        reliableInputCount: 8,
        fallbackInputCount: 0,
        excludedInputCount: 0,
        isReliable: true,
        scores: {
          overall: { value: 72, label: 'Constructive', trend: 'improving', description: 'Breadth and flow are supportive.' },
          usRiskAppetite: { value: 68, label: 'Firm', trend: 'improving', description: 'US risk appetite remains healthy.' },
          cnMoneyEffect: { value: 75, label: 'Broadening', trend: 'improving', description: 'Domestic breadth is improving.' },
          macroPressure: { value: 41, label: 'Contained', trend: 'stable', description: 'Macro pressure is contained.' },
          liquidity: { value: 70, label: 'Supportive', trend: 'improving', description: 'Liquidity backdrop is supportive.' },
        },
      });
    }

    if (method === 'GET' && path === '/api/v1/market/market-briefing') {
      return fulfillJson(route, {
        source: 'computed',
        sourceLabel: 'Mock model',
        updatedAt: timestamp,
        asOf: timestamp,
        freshness: 'mock',
        isFallback: false,
        isStale: false,
        isRefreshing: false,
        confidence: 0.81,
        reliableInputCount: 7,
        fallbackInputCount: 0,
        excludedInputCount: 0,
        isReliable: true,
        items: [
          {
            title: 'Breadth improving',
            message: 'Global breadth and CN flow data remain constructive.',
            severity: 'positive',
            category: 'cn',
            confidence: 0.81,
          },
        ],
      });
    }

    if (method === 'GET' && path === '/api/v1/market/us-breadth') {
      return fulfillJson(route, marketUsBreadthPayload());
    }

    if (method === 'GET' && path === '/api/v1/market/futures') {
      return fulfillJson(route, {
        source: 'public',
        sourceLabel: 'Mock feed',
        updatedAt: timestamp,
        asOf: timestamp,
        freshness: 'mock',
        isFallback: false,
        isStale: false,
        isRefreshing: false,
        items: [
          {
            name: 'Nasdaq Futures',
            symbol: 'NQ',
            value: 18844,
            change: 122,
            changePercent: 0.65,
            market: 'US',
            session: 'pre',
            sparkline: [18720, 18790, 18844],
            source: 'mock',
            sourceLabel: 'Mock feed',
            updatedAt: timestamp,
            asOf: timestamp,
            freshness: 'mock',
          },
        ],
      });
    }

    if (method === 'GET' && path === '/api/v1/market/cn-short-sentiment') {
      return fulfillJson(route, {
        source: 'public',
        sourceLabel: 'Mock feed',
        updatedAt: timestamp,
        asOf: timestamp,
        freshness: 'mock',
        isFallback: false,
        isStale: false,
        isRefreshing: false,
        sentimentScore: 67,
        summary: 'Short-term sentiment remains constructive.',
        metrics: {
          limitUpCount: 52,
          limitDownCount: 3,
          failedLimitUpRate: 11,
          maxConsecutiveLimitUps: 4,
          yesterdayLimitUpPerformance: 2.4,
          firstBoardCount: 21,
          secondBoardCount: 12,
          highBoardCount: 4,
          twentyCmLimitUpCount: 7,
        },
      });
    }

    unhandledApiRoutes.push(`${method} ${path}${url.search}`);
    return fulfillJson(route, { error: `Unhandled mock API route: ${method} ${path}` }, 500);
  });
}

export const test = base.extend<AppSmokeFixtures>({
  consoleErrors: [async ({ page }, use) => {
    const consoleErrors: string[] = [];

    page.on('console', (message) => {
      if (message.type() === 'error' && !message.text().includes('favicon.ico')) {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => {
      consoleErrors.push(error.message);
    });

    await use(consoleErrors);

    expect(consoleErrors).toEqual([]);
  }, { auto: true }],

  unhandledApiRoutes: [async ({ page }, use) => {
    const unhandledApiRoutes: string[] = [];
    await installMockApi(page, unhandledApiRoutes);
    await use(unhandledApiRoutes);
    expect(unhandledApiRoutes).toEqual([]);
  }, { auto: true }],
});

export { expect } from '@playwright/test';
