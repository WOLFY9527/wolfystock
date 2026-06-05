import { expect, type Locator } from '@playwright/test';

const homeFixtureTimestamp = '2026-06-02T00:00:00Z';
const scannerFixtureTimestamp = '2026-06-02T09:00:00Z';

export async function expectSurfaceTextSafe(
  surface: Locator,
  options: {
    allowedPhrases?: string[];
    forbiddenPatterns: RegExp[];
  },
) {
  const sanitizedText = (await surface.innerText()).trim();
  const text = (options.allowedPhrases ?? []).reduce(
    (current, phrase) => current.replaceAll(phrase, ''),
    sanitizedText,
  );

  for (const pattern of options.forbiddenPatterns) {
    expect(text).not.toMatch(pattern);
  }
}

export function buildHomeEvidencePacketShell(generatedAt = homeFixtureTimestamp) {
  return {
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
      generated_at: generatedAt,
      source: 'read_only_evidence_v2',
    },
  };
}

export function buildHomeHistoryData() {
  return [
    { date: '2026-05-27', open: 120.0, high: 121.2, low: 119.4, close: 120.8, volume: 8100000, change_percent: 0.7 },
    { date: '2026-05-28', open: 120.9, high: 122.4, low: 120.1, close: 121.7, volume: 7900000, change_percent: 0.74 },
    { date: '2026-05-29', open: 121.8, high: 123.1, low: 121.0, close: 122.2, volume: 8400000, change_percent: 0.41 },
    { date: '2026-05-30', open: 122.0, high: 123.6, low: 121.4, close: 123.1, volume: 8600000, change_percent: 0.74 },
    { date: '2026-06-02', open: 123.2, high: 124.1, low: 122.7, close: 123.8, volume: 8050000, change_percent: 0.57 },
  ];
}

export function buildHomeHistoryPayload(asOf = homeFixtureTimestamp) {
  return {
    stock_code: 'ORCL',
    stock_name: 'Oracle',
    period: 'daily',
    source: 'fixture_history',
    source_confidence: {
      source: 'fixture_history',
      source_label: '本地审核样例',
      as_of: asOf,
      freshness: 'available',
      is_fallback: false,
      is_stale: false,
      is_partial: false,
      is_synthetic: false,
      is_unavailable: false,
      confidence_weight: 1,
      coverage: 1,
    },
    data: buildHomeHistoryData(),
  };
}

export function buildHomeReportMeta() {
  return {
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
  };
}

export function buildHomeStrategyBase() {
  return {
    idealBuy: '121.80 - 124.60',
    stopLoss: '117.40',
    takeProfit: '133.50',
  };
}

export function buildHomeSingleStockEvidencePacketBase() {
  return {
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
  };
}

export function buildHomeSourceProvenanceFrame() {
  return [
    {
      contractVersion: 'source_provenance_v1',
      sourceId: 'polygon_us_grouped_daily',
      sourceLabel: 'Polygon Grouped Daily',
      evidenceDomain: 'market_data',
      authorityTier: 'score_grade',
      freshnessState: 'fresh',
      sourceTier: 'authorized_feed',
      fallbackOrProxy: false,
      observationOnly: false,
      scoreContributionAllowed: true,
      limitations: [],
      nextEvidenceNeeded: [],
      debugRef: 'analysis:orcl-price',
    },
    {
      contractVersion: 'source_provenance_v1',
      sourceId: 'fmp',
      sourceLabel: 'FMP',
      evidenceDomain: 'fundamentals',
      authorityTier: 'score_grade',
      freshnessState: 'cached',
      sourceTier: 'official_public',
      fallbackOrProxy: false,
      observationOnly: false,
      scoreContributionAllowed: true,
      limitations: [],
      nextEvidenceNeeded: [],
      debugRef: 'analysis:orcl-fundamentals',
    },
    {
      contractVersion: 'source_provenance_v1',
      sourceId: 'fallback_snapshot',
      sourceLabel: 'Fallback snapshot',
      evidenceDomain: 'news',
      authorityTier: 'observation_only',
      freshnessState: 'fallback',
      sourceTier: 'fallback',
      fallbackOrProxy: true,
      observationOnly: true,
      scoreContributionAllowed: false,
      limitations: ['fallback_or_proxy_source', 'observation_only'],
      nextEvidenceNeeded: ['authorized_primary_source'],
      debugRef: 'analysis:orcl-news',
    },
    {
      contractVersion: 'source_provenance_v1',
      sourceId: 'unknown_source',
      sourceLabel: '未知来源',
      evidenceDomain: 'research',
      authorityTier: 'unknown',
      freshnessState: 'unknown',
      sourceTier: 'unknown',
      fallbackOrProxy: true,
      observationOnly: true,
      scoreContributionAllowed: false,
      limitations: ['unknown_source'],
      nextEvidenceNeeded: ['verified_source_metadata'],
      debugRef: 'analysis:orcl-research',
    },
  ];
}

export function buildScannerRunSummaryBase() {
  return {
    id: 11,
    market: 'cn',
    profile: 'cn_preopen_v1',
    profile_label: 'A-share Pre-open v1',
    status: 'completed',
    run_at: scannerFixtureTimestamp,
    completed_at: '2026-06-02T09:00:10Z',
    watchlist_date: '2026-06-02',
    trigger_mode: 'manual',
    universe_name: 'cn_a_liquid_watchlist_v1',
    shortlist_size: 1,
    universe_size: 320,
    preselected_size: 72,
    evaluated_size: 48,
    source_summary: 'Mocked scanner payload',
    universe_type: 'theme',
    theme_id: 'ai_semiconductors',
    theme_label: 'AI 半导体',
    requested_symbols_count: 0,
    accepted_symbols_count: 0,
    rejected_symbols: [],
    top_symbols: ['NVDA'],
    notification_status: 'not_attempted',
    failure_reason: null,
  };
}

export function buildScannerNvdaCandidateBase() {
  return {
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
    scan_timestamp: scannerFixtureTimestamp,
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
  };
}

export function buildScannerCandidateEvidenceFrame() {
  return {
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
  };
}

export function buildScannerCandidateResearchReadiness() {
  return {
    contractVersion: 'research_readiness_v1',
    researchReady: false,
    readinessState: 'observe_only',
    verdictLabel: '仅观察',
    blockingReasons: [],
    missingEvidence: ['fundamentals', 'newsCatalyst'],
    consumerActionBoundary: 'no_advice',
    noAdviceBoundary: true,
  };
}

export function buildScannerCandidateSourceProvenanceFrame() {
  return {
    contractVersion: 'source_provenance_v1',
    entryCount: 4,
    authorityTierCounts: {
      observation_only: 2,
      score_grade: 1,
      unknown: 1,
    },
    freshnessStateCounts: {
      cached: 1,
      fallback: 1,
      fresh: 1,
      unknown: 1,
    },
    evidenceDomainCounts: {
      fundamentals: 1,
      market_data: 1,
      news: 1,
      research: 1,
    },
    fallbackOrProxyCount: 2,
    observationOnlyCount: 3,
    scoreContributionAllowedCount: 1,
    entries: [
      {
        contractVersion: 'source_provenance_v1',
        sourceId: 'polygon_us_grouped_daily',
        sourceLabel: 'Polygon Grouped Daily',
        evidenceDomain: 'market_data',
        authorityTier: 'score_grade',
        freshnessState: 'fresh',
        sourceTier: 'authorized_feed',
        fallbackOrProxy: false,
        observationOnly: false,
        scoreContributionAllowed: true,
        limitations: [],
        nextEvidenceNeeded: [],
        debugRef: 'scanner:nvda-price',
      },
      {
        contractVersion: 'source_provenance_v1',
        sourceId: 'fallback_snapshot',
        sourceLabel: 'Fallback snapshot',
        evidenceDomain: 'news',
        authorityTier: 'observation_only',
        freshnessState: 'fallback',
        sourceTier: 'fallback',
        fallbackOrProxy: true,
        observationOnly: true,
        scoreContributionAllowed: false,
        limitations: ['fallback_or_proxy_source', 'observation_only'],
        nextEvidenceNeeded: ['authorized_primary_source'],
        debugRef: 'scanner:nvda-news',
      },
      {
        contractVersion: 'source_provenance_v1',
        sourceId: 'fmp',
        sourceLabel: 'FMP',
        evidenceDomain: 'fundamentals',
        authorityTier: 'observation_only',
        freshnessState: 'cached',
        sourceTier: 'official_public',
        fallbackOrProxy: false,
        observationOnly: true,
        scoreContributionAllowed: false,
        limitations: ['observation_only'],
        nextEvidenceNeeded: ['score_grade_authority_source'],
        debugRef: 'scanner:nvda-fundamentals',
      },
      {
        contractVersion: 'source_provenance_v1',
        sourceId: 'unknown_source',
        sourceLabel: '未知来源',
        evidenceDomain: 'research',
        authorityTier: 'unknown',
        freshnessState: 'unknown',
        sourceTier: 'unknown',
        fallbackOrProxy: true,
        observationOnly: true,
        scoreContributionAllowed: false,
        limitations: ['unknown_source'],
        nextEvidenceNeeded: ['verified_source_metadata'],
        debugRef: 'scanner:nvda-research',
      },
    ],
  };
}

export function buildScannerContextFrameBase() {
  return {
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
  };
}
