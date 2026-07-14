import type { Locator, Page, Route } from '@playwright/test';
import { expect as baseExpect, expect as pwExpect } from '@playwright/test';
import { expect as appExpect, test as appTest } from './fixtures/appSmoke';
import {
  expectNoHorizontalOverflow,
  fulfillJson,
  installSignedInSessionRoutes,
  openSignedInRoute,
} from './fixtures/authenticatedRouteSmoke';
import {
  buildHomeEvidencePacketShell,
  buildHomeHistoryPayload,
  buildHomeReportMeta,
  buildHomeSingleStockEvidencePacketBase,
  buildHomeStrategyBase,
  buildScannerContextFrameBase,
  buildScannerNvdaCandidateBase,
  buildScannerRunSummaryBase,
  expectSurfaceTextSafe,
} from './fixtures/smokeEvidence';
import { installPortfolioSmokeHarness } from './fixtures/portfolioSmoke';

const forbiddenInternalPattern =
  /(?:^|[\s_-])(raw|debug|payload|prompt|env|trace|credential)(?:$|[\s_-])|providerRoute|sourceAuthority|provider\s+payload|cache\s+router|stack\s+trace/i;
const forbiddenDiagnosticVocabularyPattern =
  /provider\s+trace|provider_trace|raw\s+diagnostics?|raw_diagnostics?|raw\s+provider\s+payload|raw_provider_payload|sourceAuthorityAllowed|source_authority_allowed|scoreContributionAllowed|score_contribution_allowed|observationOnly|observation_only|reasonCode|reasonCodes|reason_code|reason_codes|contract_version|owner_scoped|delivery_mode|in_app_only|providerRoute|provider_route|cacheRouter|cache_router|cacheMutation|cache_mutation|runtimeStatus|runtime_status|runtimeChanged|runtime_changed|debugRef|debug_ref|sessionToken|session_token|accessToken|access_token|refreshToken|refresh_token/i;
const forbiddenTradingPattern =
  /小仓试错|第二笔|建仓|加仓|减仓|买入|卖出|下单|券商|\bbuy\b|\bsell\b|\border\b|\bbroker\b/i;
const optionsTimestamp = '2026-05-06T09:45:00-04:00';
const optionsExpiration = '2026-06-19';
const allowedComplianceCopy = [
  '不构成交易指令',
  '不构成下单指令',
  '不构成交易或下单指令',
  '不构成交易/下单指令',
  '不会触发外部执行',
  '不连接外部执行通道',
  '不触发执行动作',
  '不触发执行动作，不改动现有持仓。',
  '仅供研究观察，不构成交易指令。',
  '仅做只读情景分析，不构成执行指令。',
  '控制区只记录假设；数据是否可判断以后续准备度和风险边界为准，不构成执行指令。',
  '仅做只读情景分析，。',
];

async function expectConsumerSafeSurface(surface: Locator) {
  await expectSurfaceTextSafe(surface, {
    allowedPhrases: allowedComplianceCopy,
    forbiddenPatterns: [forbiddenInternalPattern, forbiddenDiagnosticVocabularyPattern, forbiddenTradingPattern],
  });
}

async function installAuthenticatedHomeEvidenceRoutes(page: Page) {
  await installSignedInSessionRoutes(page);

  await page.route('**/api/v1/stocks/*/evidence**', async (route) => {
    await fulfillJson(route, buildHomeEvidencePacketShell());
  });

  await page.route('**/api/v1/stocks/ORCL/history**', async (route) => {
    await fulfillJson(route, buildHomeHistoryPayload());
  });

  await page.route('**/api/v1/stocks/ORCL/structure-decision', async (route) => {
    await fulfillJson(route, {
      schema_version: 'stock_structure_decision_v1',
      ticker: 'ORCL',
      symbol: 'ORCL',
      structure_state: 'range_bound',
      confidence: 'medium',
      component_scores: {},
      explanation: {
        why_this_structure: 'Oracle remains inside the current review range.',
        what_confirms_it: [],
        what_invalidates_it: [],
        key_levels: [],
      },
      research_notes: {
        watch_next: [],
        needs_more_evidence: [],
        risk_flags: [],
      },
      data_quality: {
        status: 'available',
        source: 'fixture_history',
        period: 'daily',
        requested_days: 90,
        observed_bars: 60,
        usable_bars: 60,
        reason: 'history_available',
      },
      missing_evidence: [],
      no_advice_disclosure: 'Observation-only structure context.',
      peer_correlation_snapshot: {
        symbol: 'ORCL',
        peer_group: {
          status: 'available',
          label: 'Cloud software',
          symbols: ['MSFT'],
        },
        correlation_state: 'aligned',
        peer_evidence: [
          {
            symbol: 'MSFT',
            overlap_days: 22,
            state: 'aligned',
            summary: 'MSFT stayed broadly aligned with ORCL across the review window.',
          },
        ],
        divergence_evidence: [],
        stale_inputs: [],
        missing_inputs: [],
        confidence_cap: 'medium',
        observation_boundary: 'Observation-only peer movement context.',
        research_next_steps: ['Refresh peer closes before extending the read.'],
      },
    });
  });

  await page.route('**/api/v1/history/3', async (route) => {
    await fulfillJson(route, {
      meta: buildHomeReportMeta(),
      summary: {
        analysisSummary: 'Oracle is holding its post-earnings platform.',
        operationAdvice: 'Wait for a controlled pullback before adding.',
        trendPrediction: 'Constructive for the next 72 hours.',
        sentimentScore: 78,
        sentimentLabel: 'Bullish',
      },
      strategy: buildHomeStrategyBase(),
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
          singleStockEvidencePacket: buildHomeSingleStockEvidencePacketBase(),
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
      title: '风险偏好状态',
      label: '偏强观察',
      explanation: '研究观察用途，不构成交易或下单指令。',
      headline: '风险偏好改善但仍需确认',
      detail: '流动性与宽度改善，轮动仍偏观察。',
      riskLevel: 'medium',
    },
    marketRegimeSynthesis: {
      regime: 'risk_on_liquidity_expansion',
      summary: '流动性改善，风险偏好修复。',
      confidence: 0.64,
      notInvestmentAdvice: true,
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
      claimBoundaries: [
        { claim: 'market_direction_readiness_context', allowed: true, reasonCode: 'direction_ready' },
        { claim: 'trade_instruction', allowed: false, reasonCode: 'not_investment_advice' },
        { claim: 'allocation_or_suitability_guidance', allowed: false, reasonCode: 'not_investment_advice' },
      ],
      notInvestmentAdvice: true,
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
    ...buildScannerRunSummaryBase(),
    shortlist_size: 18,
    headline: 'Mock scanner shortlist for scanner top-down context smoke',
    shortlist: [
      {
        ...buildScannerNvdaCandidateBase(),
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
      ...buildScannerContextFrameBase(),
      theme_frame: {
        ...buildScannerContextFrameBase().theme_frame,
        themes: [
          { id: 'ai', label: 'AI', observation_only: true, proxy_only: true },
          { id: 'software', label: 'Software', observation_only: true, proxy_only: true },
        ],
      },
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
        ...buildScannerRunSummaryBase(),
        shortlist_size: 18,
        headline: 'Mock scanner shortlist for scanner top-down context smoke',
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

async function installLiquidityMonitorRoutes(page: Page) {
  await installSignedInSessionRoutes(page);

  await page.route('**/api/v1/market/liquidity-monitor', async (route) => {
    await fulfillJson(route, {
      endpoint: '/api/v1/market/liquidity-monitor',
      generatedAt: '2026-06-05T09:30:00+08:00',
      score: {
        value: 50,
        regime: 'neutral',
        confidence: 0.42,
        includedIndicatorCount: 1,
        possibleIndicatorWeight: 43,
        includedIndicatorWeight: 8,
      },
      freshness: {
        status: 'partial',
        weakestIndicatorFreshness: 'delayed',
        latestAsOf: '2026-06-05T09:30:00+08:00',
      },
      indicators: [
        {
          key: 'usd_pressure',
          label: 'DXY / 美元压力',
          status: 'partial',
          freshness: 'delayed',
          includedInScore: false,
          scoreContribution: 0,
          scoreWeight: 0,
          summary: '当前只有观察级样本，暂不形成方向结论。',
          updatedAt: '2026-06-05T09:30:00+08:00',
          sourceAuthorityAllowed: false,
          scoreContributionAllowed: false,
          observationOnly: true,
          reasonCode: 'observation_only',
          providerTrace: 'provider-trace-should-stay-hidden',
          rawDiagnostics: {
            cacheMutation: false,
            runtimeStatus: 'debug-only',
            payload: 'internal-only',
          },
        },
      ],
      liquidityImpulseSynthesis: {
        liquidityImpulse: 'neutral',
        impulseLabel: '无明显方向',
        subtype: 'insufficient_evidence',
        confidence: 0.12,
        confidenceLabel: 'low',
        pillarScores: {
          dollar_pressure: 0,
          equity_flow_proxy: 0,
          crypto_liquidity_beta: 0,
          funding_stress: 0,
        },
        directionScore: 0,
        dominantDrivers: [],
        counterEvidence: [],
        dataGaps: [
          {
            key: 'missing:equity_flow_proxy',
            label: 'Missing scoring evidence for equity_flow_proxy',
            pillar: 'equity_flow_proxy',
            reason: 'missing_scoring_evidence',
          },
        ],
        narrativeBullets: ['数据不足，暂不形成结论。'],
        evidenceQuality: {
          version: 'liquidity_impulse_synthesis_v1',
          inputCount: 1,
          scoringEvidenceCount: 0,
          scoringPillarCount: 0,
          coveredPillars: [],
          missingPillars: ['dollar_pressure', 'equity_flow_proxy', 'crypto_liquidity_beta', 'funding_stress'],
          discountedEvidenceCount: 0,
          observationOnlyEvidenceCount: 1,
          scoreBlockedEvidenceCount: 1,
          proxyOnlyScoringCount: 0,
          realScoringEvidenceCount: 0,
          allScoringEvidenceProxyOnly: false,
          dataGapCount: 1,
        },
        notInvestmentAdvice: true,
      },
      advisoryDisclosure: '仅用于观察市场流动性环境，不构成交易/下单指令。',
      sourceMetadata: {
        externalProviderCalls: false,
        providerRuntimeChanged: false,
        marketCacheMutation: false,
      },
    });
  });
}

async function installWatchlistDiagnosticRoutes(page: Page) {
  await installSignedInSessionRoutes(page);

  await page.route('**/api/v1/watchlist/items', async (route) => {
    await fulfillJson(route, {
      items: [
        {
          id: 1,
          symbol: 'NVDA',
          market: 'us',
          name: 'NVIDIA',
          source: 'scanner',
          scanner_run_id: 42,
          scanner_rank: 1,
          scanner_score: 94,
          last_scored_at: '2026-05-01T12:30:00Z',
          score_source: 'scanner_run',
          score_profile: 'us_preopen_v1',
          score_reason: 'Latest scanner score.',
          score_status: 'fresh',
          theme_id: 'ai-momentum',
          universe_type: 'theme',
          notes: 'Scanner observation: watch follow-through after the next catalyst.',
          intelligence: {
            scanner: {
              last_score: 94,
              last_rank: 1,
              status: 'selected',
              reason: 'Latest scanner score.',
              last_scanned_at: '2026-05-01T12:30:00Z',
              investor_signal: {
                contract_version: 'investor_signal_contract_v1',
                diagnostic_only: true,
                observation_only: true,
                authority_grant: false,
                decision_grade: false,
                source_authority_allowed: false,
                score_contribution_allowed: false,
                market_regime: 'mixed',
                market_regime_label: '信号分化',
                confidence_label: 'blocked',
                confidence_text: '禁止判断',
                freshness: 'cached',
                reason_codes: ['source_authority_missing', 'score_rights_missing'],
                explanation: '主题强弱仍然分化，当前只保留观察意义。',
                provider_trace: 'watchlist-provider-trace-should-not-render',
                debug_ref: 'watchlist:nvda:investor-signal',
              },
            },
            catalyst_exposures: [
              {
                id: 'catalyst:NVDA:us:news:1',
                symbol: 'NVDA',
                market: 'us',
                category: 'stored_news_catalyst_proxy',
                title: 'Stored news catalyst proxy',
                summary: 'Stored article summary references a potential demand catalyst.',
                evidence_status: 'proxy',
                evidence_labels: ['proxy', 'unverified'],
                as_of: '2026-05-17T20:00:00+00:00',
                published_at: '2026-05-17T13:00:00+00:00',
                reason_codes: ['observation_only', 'proxy_evidence_not_authoritative'],
                observation_only: true,
                source_authority_allowed: false,
                score_contribution_allowed: false,
                decision_grade: false,
                calendar_claim_allowed: false,
                provider_route: 'news.saved',
                raw_provider_payload: { unsafe: true },
                payload: 'watchlist-raw-payload-should-not-render',
              },
            ],
          },
          created_at: '2026-04-30T08:00:00Z',
          updated_at: '2026-04-30T09:00:00Z',
        },
      ],
    });
  });

  await page.route('**/api/v1/watchlist/refresh-status', async (route) => {
    await fulfillJson(route, {
      enabled: true,
      usTime: '08:45',
      cnTime: '09:00',
      hkTime: '09:00',
      status: 'idle',
      lastRunAt: null,
      nextRunAt: null,
    });
  });

  await page.route('**/api/v1/user-alerts/rules', async (route) => {
    await fulfillJson(route, {
      contract_version: 'user_alert_contract_v1',
      delivery_mode: 'in_app',
      in_app_only: true,
      owner_scoped: true,
      items: [],
    });
  });

  await page.route('**/api/v1/user-alerts/events', async (route) => {
    await fulfillJson(route, {
      contract_version: 'user_alert_contract_v1',
      delivery_mode: 'in_app',
      in_app_only: true,
      owner_scoped: true,
      total: 0,
      limit: 20,
      offset: 0,
      items: [],
    });
  });
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
  const calls: string[] = [];

  await installSignedInSessionRoutes(page);

  const handleOptionsRoute = async (route: Route) => {
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
  };

  await page.route('**/api/v1/options/underlyings/*/summary', handleOptionsRoute);
  await page.route('**/api/v1/options/underlyings/*/expirations', handleOptionsRoute);
  await page.route('**/api/v1/options/underlyings/*/chain**', handleOptionsRoute);
  await page.route('**/api/v1/options/strategies/compare', handleOptionsRoute);
  await page.route('**/api/v1/options/decision/evaluate', handleOptionsRoute);

  return {
    count(method: string, path: string) {
      return calls.filter((entry) => entry === `${method} ${path}`).length;
    },
  };
}

appTest.describe('consumer copy regression smoke', () => {
  appTest('Home keeps citation, evidence, and no-advice copy consumer-safe', async ({ page, consoleErrors, unhandledApiRoutes }) => {
      await installAuthenticatedHomeEvidenceRoutes(page);
      await openSignedInRoute(page, '/zh');

      const dashboard = page.getByTestId('home-bento-dashboard');
      await appExpect(dashboard).toBeVisible({ timeout: 15_000 });
      await page.getByRole('button', { name: '历史记录' }).click();
      await page.getByTestId('home-bento-history-item-3').click();
      await page.getByTestId('home-research-trust-strip').locator('summary').click();
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
    });

  appTest('Market Overview keeps translated source labels and research-only copy bounded', async ({ page, consoleErrors, unhandledApiRoutes }) => {
      await installSignedInSessionRoutes(page);
      await installTemperatureOverride(page);
      await openSignedInRoute(page, '/zh/market-overview');

      const shell = page.getByTestId('market-overview-shell');
      await appExpect(shell).toBeVisible({ timeout: 15_000 });
      const visualStrip = page.getByTestId('market-overview-visual-evidence-strip');
      await appExpect(visualStrip).toBeVisible();
      await appExpect(visualStrip).toContainText('核心图表证据');
      await appExpect(page.getByTestId('market-decision-semantics-strip')).toContainText(/不构成交易(?:或下单)?指令/);
      await appExpect(shell).toContainText(/已使用最近一次可用数据|最近一次可用数据|更新中/);
      await expectConsumerSafeSurface(visualStrip);
      await expectConsumerSafeSurface(shell);
      await baseExpect(consoleErrors).toEqual([]);
      await baseExpect(unhandledApiRoutes).toEqual([]);
      await expectNoHorizontalOverflow(page);
    });

  appTest('Scanner keeps candidate research summary and market drivers wording consumer-safe', async ({ page, consoleErrors, unhandledApiRoutes }) => {
      await installScannerContextRoutes(page);
      await openSignedInRoute(page, '/zh/scanner');

      const workspace = page.getByTestId('user-scanner-workspace');
      await appExpect(workspace).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('scanner-result-row-NVDA')).toBeVisible();
      const topDownStrip = page.getByTestId('scanner-top-down-context-strip');
      await appExpect(topDownStrip).toBeVisible();
      await appExpect(topDownStrip).toContainText('市场驱动因素');
      await appExpect(topDownStrip).toContainText('市场：仅观察');
      await appExpect(topDownStrip).toContainText('边界：仅研究观察');
      const candidateSummary = page.viewportSize()!.width >= 768
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
    });

  appTest('Liquidity Monitor keeps degraded copy consumer-safe without exposing diagnostic vocabulary', async ({ page, consoleErrors, unhandledApiRoutes }) => {
      await installLiquidityMonitorRoutes(page);
      await openSignedInRoute(page, '/zh/market/liquidity-monitor');

      const guidancePanel = page.getByTestId('liquidity-monitor-guidance-panel');
      const readiness = page.getByTestId('liquidity-decision-readiness').first();
      await appExpect(guidancePanel).toBeVisible({ timeout: 15_000 });
      await appExpect(readiness).toBeVisible();
      await appExpect(guidancePanel).toContainText(/数据不足，暂不形成结论|已使用最近一次可用数据|流动性格局仅观察|暂以观察为主/);
      await appExpect(readiness).toContainText(/数据说明与限制|最近更新|流动性状态/);
      await expectConsumerSafeSurface(guidancePanel);
      await expectConsumerSafeSurface(readiness);
      await baseExpect(consoleErrors).toEqual([]);
      await baseExpect(unhandledApiRoutes).toEqual([]);
      await expectNoHorizontalOverflow(page);
    });

  appTest('Rotation Radar keeps read-only consumer wording free of backend diagnostics', async ({ page, consoleErrors, unhandledApiRoutes }) => {
      await installSignedInSessionRoutes(page);
      await openSignedInRoute(page, '/zh/market/rotation-radar');

      const routeRoot = page.getByTestId('market-rotation-radar-page');
      const guidance = page.getByTestId('rotation-radar-guidance');
      const summaryBand = page.getByTestId('rotation-radar-summary-band');
      await appExpect(routeRoot).toBeVisible({ timeout: 15_000 });
      await appExpect(guidance).toBeVisible();
      await appExpect(summaryBand).toBeVisible();
      await appExpect(page.getByTestId('rotation-radar-visual-matrix')).toBeVisible();
      await appExpect(page.getByTestId('rotation-radar-leader-list')).toBeVisible();
      await appExpect(guidance).toContainText(/状态摘要|板块强弱|轮动方向/);
      await appExpect(summaryBand).toContainText(/当前市场|轮动方向|数据状态/);
      await expectConsumerSafeSurface(summaryBand);
      await expectConsumerSafeSurface(routeRoot);
      await baseExpect(consoleErrors).toEqual([]);
      await baseExpect(unhandledApiRoutes).toEqual([]);
      await expectNoHorizontalOverflow(page);
    });

  appTest('Watchlist keeps default-visible detail rails consumer-safe', async ({ page, consoleErrors, unhandledApiRoutes }) => {
      await installWatchlistDiagnosticRoutes(page);
      await openSignedInRoute(page, '/zh/watchlist');

      const routeRoot = page.getByTestId('watchlist-page');
      const detailRail = page.getByTestId('watchlist-detail-rail');
      await appExpect(routeRoot).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('watchlist-row-NVDA')).toBeVisible();
      await appExpect(detailRail).toBeVisible();
      await appExpect(detailRail).toContainText(/当前只保留观察意义|观察|数据说明/);
      await expectConsumerSafeSurface(detailRail);
      await expectConsumerSafeSurface(routeRoot);
      await baseExpect(consoleErrors).toEqual([]);
      await baseExpect(unhandledApiRoutes).toEqual([]);
      await expectNoHorizontalOverflow(page);
    });

  appTest('Portfolio keeps default-visible holdings and risk copy consumer-safe', async ({ page, consoleErrors, unhandledApiRoutes }) => {
      const harness = await installPortfolioSmokeHarness(page);
      await page.goto('/zh/portfolio');
      await page.waitForLoadState('domcontentloaded');

      const routeRoot = page.getByTestId('portfolio-bento-page');
      await appExpect(routeRoot).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('portfolio-total-assets-card')).toBeVisible();
      await appExpect(page.getByTestId('portfolio-current-holdings-panel')).toBeVisible();
      await expectConsumerSafeSurface(routeRoot);
      pwExpect(harness.requests.count('GET', '/api/v1/portfolio/snapshot')).toBeGreaterThan(0);
      pwExpect(harness.requests.count('GET', '/api/v1/portfolio/risk')).toBeGreaterThan(0);
      pwExpect(consoleErrors).toEqual([]);
      pwExpect(unhandledApiRoutes).toEqual([]);
      await expectNoHorizontalOverflow(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    });

  appTest('Options Lab keeps non-decision copy and read-only boundaries consumer-safe', async ({ page, consoleErrors, unhandledApiRoutes }) => {
      const harness = await installOptionsRoutes(page);
      await openSignedInRoute(page, '/zh/options-lab');

      const pageRoot = page.getByTestId('options-lab-page-root');
      await appExpect(pageRoot).toBeVisible({ timeout: 15_000 });
      const hero = page.getByTestId('options-lab-product-hero');
      const decisionEngine = page.getByTestId('options-lab-decision-engine');
      const boundaryPanel = page.getByTestId('options-lab-risk-boundary-panel');
      const visualsPanel = page.getByTestId('options-lab-visuals-panel');
      await appExpect(hero).toBeVisible();
      await appExpect(decisionEngine).toBeVisible();
      await appExpect(boundaryPanel).toBeVisible();
      await appExpect(visualsPanel).toBeVisible();
      await page.getByRole('button', { name: '运行结构比较' }).click();
      await pwExpect.poll(() => harness.count('POST', '/api/v1/options/strategies/compare')).toBeGreaterThan(0);
      await page.getByRole('button', { name: '评估情景准备度' }).click();
      await pwExpect.poll(() => harness.count('POST', '/api/v1/options/decision/evaluate')).toBeGreaterThan(0);
      await appExpect(decisionEngine).toContainText(/数据不足，暂不形成结论|情景分析已暂停/);
      await appExpect(boundaryPanel).toContainText('未达到可判断等级，仅供情景观察，暂不形成结论。');
      await appExpect(boundaryPanel).toContainText('仅供观察，不作为结论依据');
      await appExpect(visualsPanel).toContainText('收益边界与 IV 快照');
      await appExpect(visualsPanel).toContainText('非交易指令');
      await appExpect(pageRoot).toContainText('不作为官方实时权威或可执行判断依据');
      await expectConsumerSafeSurface(pageRoot);
      pwExpect(harness.count('POST', '/api/v1/options/strategies/compare')).toBeGreaterThan(0);
      pwExpect(harness.count('POST', '/api/v1/options/decision/evaluate')).toBeGreaterThan(0);
      pwExpect(consoleErrors).toEqual([]);
      pwExpect(unhandledApiRoutes).toEqual([]);
      await expectNoHorizontalOverflow(page);
  });
});
