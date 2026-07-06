import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createApiError, createParsedApiError } from '../../api/error';
import UserScannerPage from '../UserScannerPage';
import { ScannerResultHistorySummary } from '../../components/scanner/ScannerDisplayPanels';
import { UiLanguageProvider, useI18n } from '../../contexts/UiLanguageContext';
import { expectNoRawI18nKeys } from '../../test-utils/i18nRawKeySentinel';
import type {
  ScannerCandidate,
  ScannerCandidateResearchPacket,
  ScannerRunDetail,
  ScannerRunHistoryItem,
  ScannerRunHistoryResponse,
} from '../../types/scanner';
import type { WatchlistItem } from '../../types/watchlist';
import type { RuleBacktestRunResponse } from '../../types/backtest';
import { findConsumerRawLeakage, textContentWithoutObservationBoundary } from '../../test-utils/consumerRawLeakageGuard';

const {
  getRuns,
  getRun,
  getStatus,
  getThemes,
  getStrategySimulation,
  createTheme,
  runScan,
  analyzeAsync,
  listWatchlistItems,
  addWatchlistItem,
  removeWatchlistItem,
  runRuleBacktest,
  loadScannerBacktestLabMock,
} = vi.hoisted(() => ({
  getRuns: vi.fn(),
  getRun: vi.fn(),
  getStatus: vi.fn(),
  getThemes: vi.fn(),
  getStrategySimulation: vi.fn(),
  createTheme: vi.fn(),
  runScan: vi.fn(),
  analyzeAsync: vi.fn(),
  listWatchlistItems: vi.fn(),
  addWatchlistItem: vi.fn(),
  removeWatchlistItem: vi.fn(),
  runRuleBacktest: vi.fn(),
  loadScannerBacktestLabMock: vi.fn(),
}));

const productSurfaceMock = vi.hoisted(() => ({
  state: {
    isAdminAccount: false,
    canReadProviders: false,
  },
}));

const writeTextMock = vi.fn();
const createObjectUrlMock = vi.fn(() => 'blob:scanner-export');
const revokeObjectUrlMock = vi.fn();
const anchorClickMock = vi.fn();

vi.mock('../../api/scanner', () => ({
  scannerApi: {
    getRuns,
    getRun,
    getStatus,
    getThemes,
    createTheme,
    getStrategySimulation,
    run: runScan,
  },
}));

vi.mock('../../api/watchlist', () => ({
  watchlistApi: {
    listWatchlistItems,
    addWatchlistItem,
    removeWatchlistItem,
  },
}));

vi.mock('../../api/analysis', () => ({
  analysisApi: {
    analyzeAsync,
  },
  DuplicateTaskError: class DuplicateTaskError extends Error {},
}));

vi.mock('../../api/backtest', () => ({
  backtestApi: {
    runRuleBacktest,
  },
}));

vi.mock('../../hooks/useProductSurface', () => ({
  useProductSurface: () => productSurfaceMock.state,
}));

vi.mock('../../components/scanner/ScannerBacktestLab', async () => {
  loadScannerBacktestLabMock();
  return vi.importActual<typeof import('../../components/scanner/ScannerBacktestLab')>(
    '../../components/scanner/ScannerBacktestLab',
  );
});

function makeCandidate(overrides: Partial<ScannerCandidate>): ScannerCandidate {
  return {
    symbol: 'NVDA',
    name: 'NVIDIA',
    companyName: 'Backend NVIDIA Label',
    rank: 1,
    score: 94,
    qualityHint: 'backend quality hint',
    reasonSummary: 'Backend reason: momentum and liquidity improved.',
    reasons: ['Backend secondary reason'],
    keyMetrics: [
      { label: 'Entry range', value: '900-920' },
      { label: 'Target price', value: '980' },
      { label: 'Stop loss', value: '880' },
      { label: 'Risk score', value: '22' },
      { label: 'Turnover', value: '2.8x' },
    ],
    featureSignals: [
      { label: 'Signal', value: 'Momentum expansion' },
      { label: 'Theme', value: 'Backend AI infrastructure' },
    ],
    riskNotes: ['Backend risk: gap fade below support.'],
    watchContext: [{ label: 'Watch plan', value: 'Watch first pullback.' }],
    boards: ['backend-board'],
    tags: [
      {
        name: 'Backend tag',
        description: 'Backend-provided tag description.',
        tone: 'indigo',
      },
    ],
    appearedInRecentRuns: 1,
    lastTradeDate: '2026-04-21',
    scanTimestamp: '2026-04-22T08:30:00',
    aiInterpretation: {
      available: false,
      status: 'not_configured',
      summary: null,
      opportunityType: null,
      riskInterpretation: null,
      watchPlan: null,
      reviewCommentary: null,
      provider: null,
      model: null,
      generatedAt: null,
      message: null,
    },
    realizedOutcome: {
      reviewStatus: 'pending',
      outcomeLabel: 'pending',
      thesisMatch: 'pending',
      reviewWindowDays: 3,
      anchorDate: '2026-04-21',
      windowEndDate: '2026-04-24',
      sameDayCloseReturnPct: null,
      nextDayReturnPct: null,
      reviewWindowReturnPct: null,
      maxFavorableMovePct: null,
      maxAdverseMovePct: null,
      benchmarkCode: null,
      benchmarkReturnPct: null,
      outperformedBenchmark: null,
    },
    diagnostics: {},
    ...overrides,
  };
}

function makeTrustDiagnostics(overrides: Record<string, unknown> = {}) {
  return {
    scoreExplainability: {
      rawScore: 81.6,
      finalScore: 40,
      capReason: 'fallback_source',
      degradationReason: 'fallback_source',
      scoreConfidence: 0.4,
      evidenceCoverage: 0.76,
      scoreGradeAllowed: false,
      sourceConfidence: {
        source: 'fallback_snapshot',
        sourceLabel: 'Fallback snapshot',
        freshness: 'fallback',
        isFallback: true,
        isPartial: true,
        confidenceWeight: 0.4,
        coverage: 0.76,
        capReason: 'fallback_source',
        degradationReason: 'fallback_source',
        scoreContributionAllowed: false,
        observationOnly: true,
      },
      reasonCodes: ['fallback_source'],
    },
    evidencePacket: {
      scoreConfidence: 0.4,
      capReason: 'fallback_source',
      degradationReason: 'fallback_source',
      freshnessState: 'fallback',
      dataQualityState: 'partial',
      freshnessDetail: {
        quoteState: 'fallback',
        historyState: 'stale',
      },
      userFacingLabels: ['仅观察', '数据源不足', 'Fallback'],
      warningFlags: ['仅观察', '需人工复核'],
    },
    ...overrides,
  };
}

function makeRunDetail(overrides: Partial<ScannerRunDetail> = {}): ScannerRunDetail {
  return {
    id: 11,
    market: 'cn',
    profile: 'cn_preopen_v1',
    profileLabel: 'A股盘前扫描 v1',
    status: 'completed',
    runAt: '2026-04-22T08:30:00',
    completedAt: '2026-04-22T08:31:00',
    watchlistDate: '2026-04-22',
    triggerMode: 'manual',
    universeName: 'cn_a_liquid_watchlist_v1',
    shortlistSize: 3,
    universeSize: 300,
    preselectedSize: 60,
    evaluatedSize: 40,
    sourceSummary: 'Backend source summary',
    headline: 'Backend manual scan: NVDA / AVGO / AMD',
    universeNotes: ['Using backend liquid universe note.'],
    scoringNotes: ['Backend scoring note: trend and liquidity are weighted.'],
    universeType: 'default',
    themeId: null,
    themeLabel: null,
    requestedSymbolsCount: 0,
    acceptedSymbolsCount: 0,
    rejectedSymbols: [],
    diagnostics: {
      universeSelection: {
        universeType: 'default',
        themeId: null,
        themeLabel: null,
        requestedSymbolsCount: 0,
        acceptedSymbolsCount: 0,
        rejectedSymbols: [],
        universeNotes: [],
      },
      coverageSummary: {
        inputUniverseSize: 300,
        eligibleAfterUniverseFetch: 280,
        eligibleAfterLiquidityFilter: 240,
        eligibleAfterDataAvailabilityFilter: 210,
        rankedCandidateCount: 40,
        shortlistedCount: 3,
        excludedTotal: 90,
        excludedByReason: [{ reason: 'missing_history', label: 'Missing history', count: 12 }],
        likelyBottleneck: 'data_availability',
        likelyBottleneckLabel: 'Data availability',
      },
      providerDiagnostics: {
        configuredPrimaryProvider: 'akshare',
        quoteSourceUsed: 'akshare_quote',
        snapshotSourceUsed: 'local_snapshot',
        historySourceUsed: 'parquet_history',
        providersUsed: ['akshare', 'parquet'],
        fallbackOccurred: false,
        fallbackCount: 0,
        providerFailureCount: 0,
        missingDataSymbolCount: 2,
        providerWarnings: ['stale snapshot warning'],
      },
      aiInterpretation: {
        available: true,
        status: 'generated',
        provider: 'gemini',
      },
    },
    theme: {
      id: null,
      name: null,
      universeCount: 300,
      symbols: [],
    },
    summary: {
      universeCount: 300,
      submittedCount: 300,
      evaluatedCount: 40,
      selectedCount: 3,
      rejectedCount: 37,
      dataFailedCount: 2,
      skippedCount: 0,
      errorCount: 0,
      limitedByResultCap: false,
    },
    selected: [],
    candidates: [],
    notification: {
      attempted: false,
      status: 'not_attempted',
      success: null,
      channels: [],
      message: null,
      reportPath: null,
      sentAt: null,
    },
    failureReason: null,
    comparisonToPrevious: {
      available: true,
      previousRunId: 10,
      previousWatchlistDate: '2026-04-21',
      newCount: 1,
      retainedCount: 2,
      droppedCount: 1,
      newSymbols: [{ symbol: 'NVDA', name: 'NVIDIA', currentRank: 1, previousRank: null, rankDelta: null }],
      retainedSymbols: [],
      droppedSymbols: [],
    },
    reviewSummary: {
      available: true,
      reviewWindowDays: 3,
      reviewStatus: 'reviewed',
      candidateCount: 3,
      reviewedCount: 2,
      pendingCount: 1,
      hitRatePct: 50,
      outperformRatePct: 25,
      avgSameDayCloseReturnPct: 0.8,
      avgReviewWindowReturnPct: 1.2,
      avgMaxFavorableMovePct: 3.5,
      avgMaxAdverseMovePct: -1.4,
      strongCount: 1,
      mixedCount: 1,
      weakCount: 0,
      bestSymbol: 'NVDA',
      bestReturnPct: 2.5,
      weakestSymbol: 'AMD',
      weakestReturnPct: -0.5,
    },
    shortlist: [
      makeCandidate({ symbol: 'NVDA', rank: 1, score: 94 }),
      makeCandidate({
        symbol: 'AVGO',
        name: 'Broadcom backend name',
        companyName: 'Backend Broadcom Label',
        rank: 2,
        score: 88,
        reasonSummary: 'Backend AVGO reason wins.',
        keyMetrics: [
          { label: 'Entry range', value: '1300-1320' },
          { label: 'Target price', value: '1420' },
          { label: 'Stop loss', value: '1268' },
          { label: 'Risk score', value: '35' },
        ],
        featureSignals: [{ label: 'Signal', value: 'Backend networking signal' }],
        riskNotes: ['Backend AVGO risk note.'],
        aiInterpretation: {
          available: true,
          status: 'generated',
          summary: 'Backend AI interpretation summary.',
          opportunityType: null,
          riskInterpretation: 'Backend AI risk interpretation.',
          watchPlan: 'Backend AI watch plan.',
          reviewCommentary: null,
          provider: 'gemini',
          model: 'gemini/gemini-2.5-flash',
          generatedAt: '2026-04-22T08:30:12',
          message: null,
        },
        realizedOutcome: {
          reviewStatus: 'reviewed',
          outcomeLabel: 'strong',
          thesisMatch: 'matched',
          reviewWindowDays: 3,
          anchorDate: '2026-04-21',
          windowEndDate: '2026-04-24',
          sameDayCloseReturnPct: 1.1,
          nextDayReturnPct: 1.8,
          reviewWindowReturnPct: 2.4,
          maxFavorableMovePct: 4.2,
          maxAdverseMovePct: -0.9,
          benchmarkCode: 'SPY',
          benchmarkReturnPct: 0.6,
          outperformedBenchmark: true,
        },
      }),
      makeCandidate({
        symbol: 'AMD',
        name: 'AMD',
        companyName: 'Backend AMD Label',
        rank: 3,
        score: 76,
        reasonSummary: 'Backend AMD reason.',
        keyMetrics: [
          { label: 'Entry range', value: '160-162' },
          { label: 'Target price', value: '172' },
          { label: 'Stop loss', value: '155' },
          { label: 'Risk score', value: '41' },
        ],
        featureSignals: [{ label: 'Signal', value: 'Backend GPU signal' }],
        riskNotes: ['Backend AMD risk note.'],
      }),
    ],
    ...overrides,
  };
}

function makeCryptoDiagnosticsRun(overrides: Partial<ScannerRunDetail> = {}): ScannerRunDetail {
  return makeRunDetail({
    market: 'us',
    profile: 'us_preopen_v1',
    profileLabel: 'US Pre-open Scanner v1',
    universeType: 'theme',
    themeId: 'crypto_miners',
    themeLabel: '加密矿企',
    requestedSymbolsCount: 11,
    acceptedSymbolsCount: 11,
    rejectedSymbols: [],
    universeNotes: ['Theme universe: 加密矿企 · 11 symbols.'],
    theme: {
      id: 'crypto_miners',
      name: '加密矿企',
      universeCount: 11,
      symbols: ['MARA', 'RIOT', 'CLSK', 'IREN', 'HUT', 'BITF', 'WULF', 'CIFR', 'BTDR', 'CORZ', 'HIVE'],
    },
    summary: {
      universeCount: 11,
      submittedCount: 11,
      evaluatedCount: 9,
      selectedCount: 1,
      rejectedCount: 8,
      dataFailedCount: 2,
      skippedCount: 0,
      errorCount: 0,
      limitedByResultCap: false,
    },
    shortlist: [
      makeCandidate({
        symbol: 'WULF',
        name: 'TeraWulf',
        companyName: 'TeraWulf',
        rank: 1,
        score: 60,
        diagnostics: makeTrustDiagnostics(),
      }),
    ],
    selected: [
      makeCandidate({
        symbol: 'WULF',
        name: 'TeraWulf',
        companyName: 'TeraWulf',
        rank: 1,
        score: 60,
        diagnostics: makeTrustDiagnostics(),
      }),
    ],
    candidates: [
      {
        symbol: 'WULF',
        name: 'TeraWulf',
        rank: 1,
        status: 'selected',
        score: 60,
        provider: 'alpaca',
        reason: 'passed',
        failedRules: [],
        missingFields: [],
        metrics: { return20d: 44.1, trend: 20 },
        metadata: makeTrustDiagnostics(),
      },
      {
        symbol: 'MARA',
        name: 'MARA Holdings',
        rank: 2,
        status: 'rejected',
        score: 55,
        provider: 'alpaca',
        reason: 'below liquidity threshold',
        failedRules: ['below_liquidity_threshold'],
        missingFields: [],
        metrics: { return20d: 3.1, trend: 8 },
      },
      {
        symbol: 'RIOT',
        name: 'Riot Platforms',
        rank: 3,
        status: 'rejected',
        score: 52,
        provider: 'alpaca',
        reason: null,
        failedRules: ['below_price_threshold'],
        missingFields: [],
        metrics: { return20d: -2.4, trend: 4 },
      },
      {
        symbol: 'CIFR',
        name: 'Cipher Mining',
        rank: 10,
        status: 'data_failed',
        score: null,
        provider: null,
        reason: 'missing price history',
        failedRules: ['not_enough_history'],
        missingFields: ['history'],
        metrics: {},
      },
      {
        symbol: 'HIVE',
        name: 'HIVE Digital',
        rank: 11,
        status: 'error',
        score: null,
        provider: 'alpaca',
        reason: null,
        failedRules: [],
        missingFields: ['quote'],
        metrics: {},
      },
    ],
    diagnostics: {
      universeSelection: {
        universeType: 'theme',
        themeId: 'crypto_miners',
        themeLabel: '加密矿企',
        requestedSymbolsCount: 11,
        acceptedSymbolsCount: 11,
        rejectedSymbols: [],
        universeNotes: ['Theme universe: 加密矿企 · 11 symbols.'],
      },
    },
    ...overrides,
  });
}

function makeScannerContextFrame(overrides: Partial<NonNullable<ScannerRunDetail['scannerContextFrame']>> = {}) {
  return {
    marketReadiness: {
      contractVersion: 'research_readiness_v1',
      researchReady: false,
      readinessState: 'observe_only',
      verdictLabel: '仅观察',
      blockingReasons: [],
      missingEvidence: [],
      evidenceCoverage: {
        scoreGradeCount: 2,
        observationOnlyCount: 1,
        missingCount: 0,
        totalCount: 3,
      },
      sourceAuthority: 'observationOnly',
      freshnessFloor: 'cached',
      consumerActionBoundary: 'no_advice',
      nextEvidenceNeeded: ['继续结合市场与主题框架观察'],
    },
    macroRegime: {
      state: 'supportive',
      label: 'Supportive macro regime',
      freshness: 'cached',
      blockers: [],
      observationOnly: false,
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
    },
    liquidityFrame: {
      state: 'supportive',
      label: 'Liquidity supports equity leadership',
      freshness: 'cached',
      blockers: [],
      observationOnly: false,
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
      proxyOnly: false,
    },
    assetClassBias: {
      state: 'supportive',
      label: 'Equities preferred',
      blockers: [],
      observationOnly: false,
    },
    themeFrame: {
      state: 'observe_only',
      label: 'AI leadership is still observation-only',
      freshness: 'cached',
      blockers: [],
      observationOnly: true,
      proxyOnly: true,
      themes: [
        { id: 'ai', label: 'AI', observationOnly: true, proxyOnly: true },
        { id: 'software', label: 'Software', observationOnly: true, proxyOnly: true },
      ],
    },
    universePolicy: {
      type: 'theme',
      label: 'Theme universe',
      blockers: [],
    },
    noAdviceBoundary: true,
    ...overrides,
  };
}

function makeCandidateEvidenceFrame(overrides: Record<string, unknown> = {}) {
  return {
    contractVersion: 'scanner_candidate_evidence_v1',
    coverageState: 'partial',
    domains: {
      technicals: { state: 'available', observationOnly: false, scoreGradeAllowed: true },
      priceHistory: { state: 'available', observationOnly: false, scoreGradeAllowed: true },
      liquidity: { state: 'available', observationOnly: false, scoreGradeAllowed: true },
      volume: { state: 'available', observationOnly: false, scoreGradeAllowed: true },
      trend: { state: 'available', observationOnly: false, scoreGradeAllowed: true },
      theme: { state: 'available', observationOnly: true, scoreGradeAllowed: false },
      fundamentals: { state: 'missing', observationOnly: false, scoreGradeAllowed: false },
      newsCatalyst: { state: 'missing', observationOnly: false, scoreGradeAllowed: false },
    },
    coverage: {
      availableCount: 6,
      partialCount: 0,
      observeOnlyCount: 1,
      missingCount: 2,
      totalCount: 8,
    },
    noAdviceBoundary: true,
    debugRef: 'scanner:candidate:NVDA',
    ...overrides,
  };
}

function makeCandidateResearchReadiness(overrides: Record<string, unknown> = {}) {
  return {
    contractVersion: 'research_readiness_v1',
    researchReady: false,
    readinessState: 'insufficient',
    verdictLabel: '证据不足',
    blockingReasons: ['source_authority_router_rejected', 'missing_required_evidence'],
    missingEvidence: ['fundamentals', 'news', 'catalyst'],
    evidenceCoverage: {
      scoreGradeCount: 5,
      observationOnlyCount: 1,
      missingCount: 3,
      totalCount: 9,
    },
    sourceAuthority: 'observationOnly',
    freshnessFloor: 'delayed',
    consumerActionBoundary: 'no_advice',
    nextEvidenceNeeded: ['补充基本面证据', '补充新闻证据'],
    debugRef: 'scanner:candidate:NVDA',
    noAdviceBoundary: true,
    ...overrides,
  };
}

function makeCandidateResearchSummaryFrame(overrides: Record<string, unknown> = {}) {
  return {
    contractVersion: 'scanner_candidate_research_summary_v1',
    frameState: 'insufficient',
    symbol: 'NVDA',
    rank: 1,
    scoreBand: 'limited',
    primaryResearchReason: 'Current signals support shortlist review, but fundamentals are still missing.',
    evidenceHighlights: [
      'Technicals available',
      'Price history available',
      'Liquidity available',
    ],
    missingEvidence: ['fundamentals', 'newsCatalyst'],
    blockingReasons: ['source_authority_router_rejected', 'missing_required_evidence'],
    topDownContextRefs: [
      { key: 'marketReadiness', state: 'observe_only', label: 'Top-down market context available' },
      { key: 'liquidityFrame', state: 'supportive', label: 'Liquidity context available' },
      { key: 'themeFrame', state: 'observe_only', label: 'Theme leadership context available' },
    ],
    sourceAuthority: 'observationOnly',
    freshness: 'delayed',
    nextResearchStep: 'Wait for more complete evidence.',
    noAdviceBoundary: true,
    debugRef: 'scanner:candidate_summary:NVDA',
    ...overrides,
  };
}

function makeCandidateResearchPacket(overrides: Partial<ScannerCandidateResearchPacket> & Record<string, unknown> = {}) {
  return {
    whySurfaced: '趋势与流动性线索使该标的进入本轮复核。',
    primaryEvidence: ['技术面可用', '流动性可用', '报价可用', '行业/ETF线索可用'],
    limitingEvidence: ['基本面证据待补', '新闻催化待补'],
    dataQualityNotes: ['证据部分可用', '报价可能延迟'],
    rejectedOrLimitedReasonSafeLabel: '已进入本轮观察名单',
    researchNextStep: '补充基本面与新闻催化证据后再复核。',
    observationOnly: true,
    sourceRefs: ['scanner:source:debug'],
    reasonCodes: ['source_authority_missing'],
    providerDiagnostics: { rawPayload: true },
    debugRef: 'scanner:candidate_packet:NVDA',
    ...overrides,
  };
}

function makeCandidateSourceProvenanceFrame(overrides: Record<string, unknown> = {}) {
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
    ...overrides,
  };
}

function makeHistoryItem(overrides: Partial<ScannerRunHistoryItem> = {}): ScannerRunHistoryItem {
  return {
    id: 11,
    market: 'cn',
    profile: 'cn_preopen_v1',
    profileLabel: 'A股盘前扫描 v1',
    status: 'completed',
    runAt: '2026-04-22T08:30:00',
    completedAt: '2026-04-22T08:31:00',
    watchlistDate: '2026-04-22',
    triggerMode: 'manual',
    universeName: 'cn_a_liquid_watchlist_v1',
    shortlistSize: 3,
    universeSize: 300,
    preselectedSize: 60,
    evaluatedSize: 40,
    sourceSummary: 'history source',
    headline: '历史扫描：NVDA / AVGO / AMD',
    universeType: 'default',
    themeId: null,
    themeLabel: null,
    requestedSymbolsCount: 0,
    acceptedSymbolsCount: 0,
    rejectedSymbols: [],
    topSymbols: ['NVDA', 'AVGO', 'AMD'],
    notificationStatus: 'not_attempted',
    failureReason: null,
    changeSummary: {
      available: true,
      previousRunId: 10,
      previousWatchlistDate: '2026-04-21',
      newCount: 1,
      retainedCount: 2,
      droppedCount: 1,
      newSymbols: [],
      retainedSymbols: [],
      droppedSymbols: [],
    },
    reviewSummary: {
      available: true,
      reviewWindowDays: 3,
      reviewStatus: 'reviewed',
      candidateCount: 3,
      reviewedCount: 2,
      pendingCount: 1,
      hitRatePct: 50,
      outperformRatePct: 25,
      avgSameDayCloseReturnPct: 0.8,
      avgReviewWindowReturnPct: 1.2,
      avgMaxFavorableMovePct: 3.5,
      avgMaxAdverseMovePct: -1.4,
      strongCount: 1,
      mixedCount: 1,
      weakCount: 0,
      bestSymbol: 'NVDA',
      bestReturnPct: 2.5,
      weakestSymbol: 'AMD',
      weakestReturnPct: -0.5,
    },
    ...overrides,
  };
}

function makePseudoResultHistoryItem(overrides: Partial<ScannerRunHistoryItem> = {}): ScannerRunHistoryItem {
  return makeHistoryItem({
    status: 'completed',
    runAt: '2026-04-22T08:30:00',
    completedAt: '2026-04-22T08:30:00',
    shortlistSize: 0,
    universeSize: 0,
    preselectedSize: 0,
    evaluatedSize: 0,
    headline: null,
    topSymbols: [],
    failureReason: null,
    ...overrides,
  });
}

function makeHistoryResponse(items: ScannerRunHistoryItem[] = [makeHistoryItem()]): ScannerRunHistoryResponse {
  return {
    total: items.length,
    page: 1,
    limit: 8,
    items,
  };
}

function makeWatchlistItem(overrides: Partial<WatchlistItem> = {}): WatchlistItem {
  return {
    id: 101,
    symbol: 'NVDA',
    market: 'cn',
    name: 'NVIDIA',
    source: 'scanner',
    scannerRunId: 11,
    scannerRank: 1,
    scannerScore: 94,
    themeId: 'crypto_miners',
    universeType: 'default',
    notes: 'Backend reason: momentum and liquidity improved.',
    createdAt: '2026-04-22T08:31:00',
    updatedAt: '2026-04-22T08:31:00',
    ...overrides,
  };
}

function makeRuleBacktestRun(overrides: Partial<RuleBacktestRunResponse> = {}): RuleBacktestRunResponse {
  return {
    id: 27,
    code: 'WULF',
    strategyText: 'deterministic default',
    parsedStrategy: {
      executable: true,
      entry: { type: 'group', op: 'and', rules: [] },
      exit: { type: 'group', op: 'or', rules: [] },
      summary: 'default',
      assumptions: [],
      warnings: [],
      strategySpec: {},
    },
    strategyHash: 'hash-27',
    timeframe: '1d',
    startDate: '2025-05-03',
    endDate: '2026-05-03',
    lookbackBars: 252,
    initialCapital: 100000,
    feeBps: 0,
    slippageBps: 0,
    needsConfirmation: false,
    warnings: [],
    status: 'completed',
    statusHistory: [],
    tradeCount: 6,
    winCount: 4,
    lossCount: 2,
    totalReturnPct: 12.3,
    maxDrawdownPct: -8.1,
    summary: { sharpe: 1.2 },
    executionAssumptions: {},
    benchmarkCurve: [],
    benchmarkSummary: {},
    dailyReturnSeries: [],
    exposureCurve: [],
    equityCurve: [],
    trades: [],
    ...overrides,
  };
}

function LanguageSwitch() {
  const { setLanguage } = useI18n();
  return (
    <button type="button" onClick={() => setLanguage('en')}>
      switch-language-en
    </button>
  );
}

type RenderUserScannerPageOptions = {
  withLanguageSwitch?: boolean;
  initialEntry?: string;
  viewportWidth?: number;
};

function renderUserScannerPage(options: boolean | RenderUserScannerPageOptions = false) {
  const normalizedOptions = typeof options === 'boolean' ? { withLanguageSwitch: options } : options;
  const {
    withLanguageSwitch = false,
    initialEntry = '/scanner',
    viewportWidth,
  } = normalizedOptions;
  if (viewportWidth) {
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      writable: true,
      value: viewportWidth,
    });
    window.dispatchEvent(new Event('resize'));
  }
  return render(
    <UiLanguageProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        {withLanguageSwitch ? <LanguageSwitch /> : null}
        <Routes>
          <Route path="/scanner" element={<UserScannerPage />} />
          <Route path="/:locale/scanner" element={<UserScannerPage />} />
          <Route path="/" element={<div>Home Landing</div>} />
          <Route path="/:locale" element={<div>Home Landing</div>} />
          <Route path="/watchlist" element={<div>Watchlist Landing</div>} />
          <Route path="/:locale/watchlist" element={<div>Watchlist Landing</div>} />
          <Route path="/market-overview" element={<div>Market Overview Landing</div>} />
          <Route path="/:locale/market-overview" element={<div>Market Overview Landing</div>} />
          <Route path="/stocks/:symbol/structure-decision" element={<div>Stock Research Landing</div>} />
          <Route path="/:locale/stocks/:symbol/structure-decision" element={<div>Stock Research Landing</div>} />
          <Route path="/backtest" element={<div>Backtest Landing</div>} />
          <Route path="/:locale/backtest" element={<div>Backtest Landing</div>} />
          <Route path="/backtest/results/:runId" element={<div>Backtest Result</div>} />
          <Route path="/:locale/backtest/results/:runId" element={<div>Backtest Result</div>} />
        </Routes>
      </MemoryRouter>
    </UiLanguageProvider>,
  );
}

function orderedSymbolsFromRows(): string[] {
  return screen
    .getAllByTestId(/^scanner-result-row-/)
    .map((row) => row.getAttribute('data-testid')?.replace('scanner-result-row-', '') || '');
}

function expectElementBefore(first: HTMLElement, second: HTMLElement) {
  expect(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
}

function getActionButton(container: HTMLElement, name: RegExp) {
  return within(container).getAllByRole('button', { name })[0] as HTMLButtonElement;
}

function getRankedRow(symbol: string) {
  return screen.getByTestId(`scanner-ranked-row-${symbol}`);
}

async function openMoreActions() {
  const more = await screen.findByTestId('scanner-more-actions');
  const trigger = within(more).getByRole('button', { name: /更多|More/i });
  if (trigger.getAttribute('aria-expanded') !== 'true') {
    fireEvent.click(trigger);
  }
  return more;
}

async function openRowMore(rowTestId: string) {
  const row = await screen.findByTestId(rowTestId);
  fireEvent.click(getActionButton(row, /更多|More/i));
  const symbol = rowTestId.replace(/^scanner-(?:result|candidate)-row-/, '');
  return getRankedRow(symbol);
}

async function openAdvancedControls() {
  const advanced = await screen.findByTestId('scanner-advanced-controls');
  const trigger = within(advanced).getByRole('button', { name: /高级参数|Advanced controls/i });
  if (trigger.getAttribute('aria-expanded') !== 'true') {
    fireEvent.click(trigger);
  }
  return advanced;
}

describe('UserScannerPage', () => {
  beforeEach(() => {
    window.localStorage.clear();
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      writable: true,
      value: 1280,
    });
    getRuns.mockReset();
    getRun.mockReset();
    getThemes.mockReset();
    getStrategySimulation.mockReset();
    createTheme.mockReset();
    runScan.mockReset();
    analyzeAsync.mockReset();
    listWatchlistItems.mockReset();
    addWatchlistItem.mockReset();
    removeWatchlistItem.mockReset();
    runRuleBacktest.mockReset();
    writeTextMock.mockReset();
    createObjectUrlMock.mockClear();
    revokeObjectUrlMock.mockClear();
    anchorClickMock.mockClear();
    productSurfaceMock.state = {
      isAdminAccount: false,
      canReadProviders: false,
    };

    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: writeTextMock,
      },
    });
    URL.createObjectURL = createObjectUrlMock;
    URL.revokeObjectURL = revokeObjectUrlMock;
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(anchorClickMock);

    getThemes.mockResolvedValue({
      items: [
        {
          id: 'crypto_miners',
          labelZh: '加密矿企',
          labelEn: 'Crypto miners',
          market: 'us',
          description: 'Curated US crypto miner seed list.',
          symbols: ['MARA', 'RIOT', 'CLSK', 'IREN', 'CIFR', 'HUT', 'BTDR', 'WULF', 'CORZ', 'BITF', 'HIVE'],
          aliases: [],
          tags: ['crypto'],
          source: 'seed',
          version: '2026-05-01',
          isSeedList: true,
          requiresManualMaintenance: false,
        },
        {
          id: 'ai_semiconductors',
          labelZh: 'AI 半导体',
          labelEn: 'AI semiconductors',
          market: 'us',
          description: 'Curated US AI semiconductor seed list.',
          symbols: ['NVDA', 'AMD', 'AVGO', 'MRVL', 'ARM', 'TSM', 'ASML', 'AMAT', 'LRCX', 'KLAC'],
          aliases: [],
          tags: ['ai'],
          source: 'seed',
          version: '2026-05-01',
          isSeedList: true,
          requiresManualMaintenance: false,
        },
        {
          id: 'optical_module_cpo_cn',
          labelZh: '光模块 CPO',
          labelEn: 'Optical modules / CPO',
          market: 'cn',
          description: '待人工维护的 A 股主题占位池。',
          symbols: [],
          aliases: [],
          tags: ['cn'],
          source: 'placeholder',
          version: '2026-05-01',
          isSeedList: true,
          requiresManualMaintenance: true,
        },
      ],
    });
    getRuns.mockResolvedValue(makeHistoryResponse());
    getRun.mockResolvedValue(makeRunDetail());
    getStatus.mockResolvedValue({
      market: 'cn',
      profile: 'cn_preopen_v1',
      watchlistDate: '2026-04-22',
      todayTradingDay: true,
      scheduleEnabled: false,
      scheduleRunImmediately: false,
      notificationEnabled: false,
      qualitySummary: {
        available: false,
        reviewWindowDays: 5,
        runCount: 0,
        reviewedRunCount: 0,
        reviewedCandidateCount: 0,
        strongCount: 0,
        mixedCount: 0,
        weakCount: 0,
      },
      dataReadiness: {
        state: 'unknown',
        market: 'cn',
        profile: 'cn_preopen_v1',
        blockerBucket: 'unknown',
        quoteCoverage: 'unknown',
        historyCoverage: 'unknown',
        freshness: 'unknown',
      },
    });
    getStrategySimulation.mockResolvedValue({
      theme: 'crypto_miners',
      profile: 'us_preopen_v1',
      market: 'us',
      window: { lookbackDays: 90, forwardDays: 5, runCount: 2 },
      status: 'ready',
      summary: {
        historicalRuns: 2,
        selectionEvents: 3,
        avgSelectedPerRun: 1.5,
        hitRate: 0.67,
        avgForwardReturnPct: 3.2,
        medianForwardReturnPct: 1.8,
        avgBenchmarkReturnPct: 1.1,
        avgExcessReturnPct: 2.1,
        positiveSelectionRate: 0.67,
        bestSymbol: 'WULF',
        worstSymbol: 'MARA',
        dataCoverage: 0.83,
      },
      runs: [
        {
          runId: 11,
          runAt: '2026-05-01T08:45:00',
          selectedCount: 1,
          rejectedCount: 8,
          selectedSymbols: ['WULF'],
          avgForwardReturnPct: 2.5,
          benchmarkReturnPct: 0.8,
          excessReturnPct: 1.7,
        },
      ],
      symbols: [
        {
          symbol: 'WULF',
          selectionCount: 2,
          avgScore: 62,
          avgForwardReturnPct: 4.4,
          hitRate: 0.5,
          bestForwardReturnPct: 12.1,
          worstForwardReturnPct: -6.2,
        },
      ],
      warnings: ['1 selection events missing forward price data'],
    });
    createTheme.mockResolvedValue({
      theme: {
        id: 'custom_white_house_stocks',
        labelZh: 'White House Stocks',
        labelEn: 'White House Stocks',
        market: 'us',
        description: 'AI-generated custom scanner theme.',
        symbols: ['PLTR', 'LMT', 'RTX'],
        aliases: ['White House Stocks'],
        tags: ['custom', 'ai-generated', 'us'],
        source: 'ai_generated',
        version: '2026-05-02',
        isSeedList: false,
        requiresManualMaintenance: true,
        criteriaPrompt: 'Stocks associated with White House policy, federal contracts, and government decisions.',
        generatedAt: '2026-05-02T00:00:00Z',
        updatedAt: '2026-05-02T00:00:00Z',
        refreshPolicy: 'on_demand',
        aiMetadata: { status: 'generated' },
      },
      suggestions: [
        {
          symbol: 'PLTR',
          reason: 'Federal analytics and defense contracts.',
          confidence: 0.86,
          evidence: ['federal contracts'],
        },
      ],
      message: 'Generated 3 symbols.',
    });
    runScan.mockResolvedValue(makeRunDetail());
    analyzeAsync.mockResolvedValue({ taskId: 'task-1' });
    runRuleBacktest.mockImplementation(async (params: { code: string }) => makeRuleBacktestRun({
      id: params.code === 'WULF' ? 27 : params.code === 'MARA' ? 28 : params.code === 'RIOT' ? 29 : 30,
      code: params.code,
    }));
    listWatchlistItems.mockResolvedValue({ items: [] });
    addWatchlistItem.mockResolvedValue(makeWatchlistItem());
    removeWatchlistItem.mockResolvedValue({ deleted: 1 });
  });

  it('fetches scanner run history once on the initial zh desktop route load', async () => {
    renderUserScannerPage({ initialEntry: '/zh/scanner', viewportWidth: 1280 });

    expect(await screen.findByTestId('scanner-result-row-NVDA')).toBeInTheDocument();
    await waitFor(() => {
      expect(getRun).toHaveBeenCalledWith(11);
    });
    expect(getRuns).toHaveBeenCalledTimes(1);
    expect(getRuns).toHaveBeenCalledWith({
      market: 'cn',
      profile: 'cn_preopen_v1',
      page: 1,
      limit: 8,
    });
  });

  it('keeps page load passive while presenting scanner readiness as membership, market-data, and candidate-generation layers', async () => {
    const readinessRun = makeRunDetail();
    readinessRun.diagnostics = {
      ...(readinessRun.diagnostics || {}),
      dataReadiness: {
        state: 'blocked',
        market: 'cn',
        profile: 'cn_preopen_v1',
        universeSize: 320,
        scannerUniverseReadiness: {
          status: 'available',
          market: 'cn',
          universeSize: 320,
          consumerSafeMessage: '标的池已准备，仍需补齐市场数据。',
        },
        quoteCoverage: 'partial',
        historyCoverage: 'blocked',
        blockerBucket: 'missing_history',
        selectedCount: 0,
        rejectedCount: 0,
        failedCount: 18,
        nextDataAction: '补齐历史数据后再重试。',
      },
    };
    getRun.mockResolvedValue(readinessRun);

    renderUserScannerPage({ initialEntry: '/zh/scanner', viewportWidth: 1280 });

    await screen.findByTestId('scanner-result-row-NVDA');
    const firstViewport = screen.getByTestId('scanner-consumer-first-viewport');
    const hierarchy = screen.getByTestId('scanner-readiness-hierarchy');
    expect(firstViewport).toHaveClass('bg-[var(--wolfy-surface-input)]');
    expect(firstViewport).not.toHaveClass('bg-white/[0.025]');
    expect(hierarchy).toHaveTextContent('标的池成员');
    expect(hierarchy).toHaveTextContent('市场数据');
    expect(hierarchy).toHaveTextContent('候选生成');
    expect(hierarchy).not.toHaveTextContent(/source_missing|activationReady|candidate_generation_blocked|sourceClass|contractVersion|provider/i);
    expect(runScan).not.toHaveBeenCalled();
  });

  it('fetches scanner run history once on the initial zh narrow route load', async () => {
    renderUserScannerPage({ initialEntry: '/zh/scanner', viewportWidth: 390 });

    expect(await screen.findByTestId('scanner-result-row-NVDA')).toBeInTheDocument();
    await waitFor(() => {
      expect(getRun).toHaveBeenCalledWith(11);
    });
    expect(getRuns).toHaveBeenCalledTimes(1);
    expect(getRun).toHaveBeenCalledTimes(1);
  });

  it('keeps scanner mobile summary and recovery actions wrap-safe at 390px', async () => {
    const blockedRun = makeRunDetail();
    blockedRun.shortlist = [];
    blockedRun.selected = [];
    blockedRun.diagnostics = {
      ...(blockedRun.diagnostics || {}),
      dataReadiness: {
        state: 'blocked',
        blockerBucket: 'missing_history',
        nextDataAction: '补齐历史数据后再重试。',
      },
    };
    blockedRun.summary = {
      ...blockedRun.summary,
      selectedCount: 0,
      rejectedCount: 18,
      dataFailedCount: 22,
      errorCount: 0,
    };
    getRun.mockResolvedValue(blockedRun);

    renderUserScannerPage({ initialEntry: '/zh/scanner', viewportWidth: 390 });

    expect(await screen.findByTestId('scanner-workflow-next-steps')).toBeInTheDocument();
    expect(screen.getByTestId('scanner-consumer-control-summary')).toHaveClass('grid-cols-2');
    expect(screen.getByTestId('scanner-consumer-control-value-market')).toHaveClass('break-words', 'whitespace-normal');
    expect(screen.getByTestId('scanner-consumer-control-value-strategy')).toHaveClass('break-words', 'whitespace-normal');
    expect(screen.getByTestId('scanner-consumer-trust-value-universe')).toHaveClass('break-words', 'whitespace-normal');
    expect(screen.getByTestId('scanner-workflow-next-steps')).toHaveClass('overflow-x-hidden');
    expect(screen.getByTestId('scanner-secondary-route-copy')).toHaveClass('sm:ml-auto');
  });

  it('renders scanner score without misleading AI score copy for normal scanner scores', async () => {
    const { container } = renderUserScannerPage();

    expect(within(await screen.findByTestId('scanner-result-row-NVDA')).getAllByText('94/100').length).toBeGreaterThan(0);
    expect(within(screen.getByTestId('scanner-result-row-AVGO')).getAllByText('88/100').length).toBeGreaterThan(0);
    expect(screen.queryByText(/AI score|AI 评分/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Annualized return forecast|年化收益预测/)).not.toBeInTheDocument();
    expectNoRawI18nKeys(container);
  });

  it('keeps default scanner rows free of source-confidence diagnostics without trading-action wording', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    const { container } = renderUserScannerPage();

    const row = await screen.findByTestId('scanner-result-row-WULF');
    expect(within(row).getAllByText('60/100').length).toBeGreaterThan(0);
    expect(within(row).queryByTestId('scanner-score-trust-WULF')).not.toBeInTheDocument();
    expect(row).not.toHaveTextContent(/fallback|proxy|stale|source-confidence|sourceConfidence|provider|reasonCode|reasonFamilies/i);
    expect(textContentWithoutObservationBoundary(container)).not.toMatch(/买入|卖出|加仓|减仓|recommend(?:ation)?/i);
    expectNoRawI18nKeys(container);
  });

  it('renders a scanner conclusion band for the top candidate state', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    await screen.findByTestId('scanner-result-row-WULF');
    const band = await screen.findByTestId('scanner-conclusion-band');
    const readinessStrip = screen.getByTestId('scanner-research-readiness-strip');
    expect(band).toHaveTextContent('当前候选 WULF');
    expect(band).toHaveTextContent('候选 1');
    expect(band).toHaveTextContent('观察 WULF 的下一次更新');
    expect(band).toHaveTextContent('部分结果使用最近一次可用数据。');
    expect(readinessStrip).toHaveTextContent('研究就绪度');
    expect(readinessStrip).toHaveTextContent(/仅观察|证据不足|等待证据更新/);
    expect(band).not.toHaveTextContent(/Fallback|Proxy|Stale|Capped|Limited\s+1|受限\s+1|备用数据|代理|过期|封顶/i);
  });

  it('renders compact top-down context labels for mixed scanner context without mutating ranking or score order', async () => {
    getRun.mockResolvedValue(makeRunDetail({
      market: 'us',
      profile: 'us_preopen_v1',
      profileLabel: 'US Pre-open Scanner v1',
      universeType: 'theme',
      themeId: 'ai_semiconductors',
      themeLabel: 'AI 半导体',
      scannerContextFrame: makeScannerContextFrame(),
    }));

    renderUserScannerPage();

    await waitFor(() => expect(screen.getByTestId('scanner-page-profile-label')).toHaveTextContent('US Pre-open Scanner'));
    expect(screen.getByTestId('scanner-page-profile-label')).not.toHaveTextContent(/v1/);

    const strip = await screen.findByTestId('scanner-top-down-context-strip');
    expect(strip).toHaveTextContent('市场驱动因素');
    expect(strip).toHaveTextContent('混合');
    expect(strip).toHaveTextContent('市场：仅观察');
    expect(strip).toHaveTextContent('宏观：支持');
    expect(strip).toHaveTextContent('流动性：支持');
    expect(strip).toHaveTextContent('资产：支持');
    expect(strip).toHaveTextContent('主题：仅观察');
    expect(strip).toHaveTextContent('标的池：主题池');
    expect(strip).toHaveTextContent('边界：仅研究观察');
    expect(strip).toHaveTextContent('当前候选来自支持与观察并存的市场框架');

    expect(within(await screen.findByTestId('scanner-result-row-NVDA')).getAllByText('94/100').length).toBeGreaterThan(0);
    expect(within(screen.getByTestId('scanner-result-row-AVGO')).getAllByText('88/100').length).toBeGreaterThan(0);
    expect(orderedSymbolsFromRows()).toEqual(['NVDA', 'AVGO', 'AMD']);
  });

  it('keeps ranked rows ahead of compact scanner workflow summaries', async () => {
    const nvda = makeCandidate({ symbol: 'NVDA', rank: 1, score: 94 });
    (nvda as ScannerCandidate & Record<string, unknown>).candidateEvidenceFrame = makeCandidateEvidenceFrame();
    (nvda as ScannerCandidate & Record<string, unknown>).candidateResearchReadiness = makeCandidateResearchReadiness({
      readinessState: 'observe_only',
      verdictLabel: '仅观察',
    });
    (nvda as ScannerCandidate & Record<string, unknown>).candidateResearchSummaryFrame = makeCandidateResearchSummaryFrame();
    (nvda as ScannerCandidate & Record<string, unknown>).candidateSourceProvenanceFrame = makeCandidateSourceProvenanceFrame();

    getRun.mockResolvedValue(makeRunDetail({
      shortlist: [
        nvda,
        makeCandidate({ symbol: 'AVGO', rank: 2, score: 88 }),
        makeCandidate({ symbol: 'AMD', rank: 3, score: 76 }),
      ],
      selected: [nvda],
      scannerContextFrame: makeScannerContextFrame(),
    }));

    renderUserScannerPage();

    const topDown = await screen.findByTestId('scanner-top-down-context-strip');
    const workflow = await screen.findByTestId('scanner-workflow-summary');
    const rankedList = screen.getByTestId('scanner-ranked-list');
    const postTableSummaries = screen.getByTestId('scanner-post-table-summaries');

    expect(workflow).toHaveTextContent(/先看市场驱动|Start with market drivers/);
    expect(workflow).toHaveTextContent(/当前候选 NVDA|Focus candidate NVDA/);
    expect(workflow).toHaveTextContent(/仅观察/);
    expect(workflow).toHaveTextContent(/来源确认：含评分级/);
    expect(workflow).toHaveTextContent(/查看排名主表|Review ranked rows/);
    expect(workflow).toHaveTextContent(/94\/100/);
    expectElementBefore(topDown, rankedList);
    expectElementBefore(rankedList, postTableSummaries);
    expect(postTableSummaries).toContainElement(workflow);
    expectElementBefore(screen.getByTestId('scanner-workflow-step-topdown'), screen.getByTestId('scanner-workflow-step-focus-candidate'));
    expectElementBefore(screen.getByTestId('scanner-workflow-step-focus-candidate'), screen.getByTestId('scanner-workflow-step-ranked-rows'));
  });

  it('renders candidate evidence coverage without changing row order or score labels', async () => {
    const nvda = makeCandidate({ symbol: 'NVDA', rank: 1, score: 94 });
    (nvda as ScannerCandidate & Record<string, unknown>).candidateEvidenceFrame = makeCandidateEvidenceFrame();
    (nvda as ScannerCandidate & Record<string, unknown>).candidateResearchReadiness = makeCandidateResearchReadiness();

    getRun.mockResolvedValue(makeRunDetail({
      shortlist: [
        nvda,
        makeCandidate({ symbol: 'AVGO', rank: 2, score: 88 }),
        makeCandidate({ symbol: 'AMD', rank: 3, score: 76 }),
      ],
      selected: [nvda],
      scannerContextFrame: makeScannerContextFrame(),
    }));

    const { container } = renderUserScannerPage();

    const row = await screen.findByTestId('scanner-result-row-NVDA');
    const visualSummary = await screen.findByTestId('scanner-visual-evidence-summary');
    const candidateCoverage = screen.getByTestId('scanner-visual-candidate-coverage');
    const marketCoverage = screen.getByTestId('scanner-visual-market-coverage');
    expect(visualSummary).toHaveTextContent(/视觉证据|Visual evidence/);
    expect(screen.getByTestId('scanner-visual-score-distribution')).toBeInTheDocument();
    expect(candidateCoverage).toBeInTheDocument();
    expect(candidateCoverage.querySelector('.bg-blue-300\\/85')).toBeTruthy();
    expect(candidateCoverage.querySelector('.bg-amber-300\\/85')).toBeNull();
    expect(marketCoverage).toBeInTheDocument();
    expect(marketCoverage.querySelector('.bg-blue-300\\/85')).toBeTruthy();
    expect(marketCoverage.querySelector('.bg-amber-300\\/85')).toBeNull();
    expect(row).toHaveTextContent('证据不足');
    expect(row).toHaveTextContent('待补');
    expect(row).toHaveTextContent('基本面');
    expect(row).toHaveTextContent('新闻催化');

    const detail = screen.getAllByTestId('scanner-result-detail-NVDA')[0];
    expect(detail).toHaveTextContent('证据覆盖');
    expect(detail).toHaveTextContent('技术面');
    expect(detail).toHaveTextContent('价格历史');
    expect(detail).toHaveTextContent('流动性');
    expect(detail).toHaveTextContent('成交量');
    expect(detail).toHaveTextContent('趋势');
    expect(detail).toHaveTextContent('主题');
    expect(detail).toHaveTextContent('基本面');
    expect(detail).toHaveTextContent('新闻催化');
    expect(detail).toHaveTextContent('仅观察');
    expect(detail).toHaveTextContent('缺失');
    expect(detail).not.toHaveTextContent(/debugRef|source_authority_router_rejected|provider|router|cache|trace/i);

    expect(within(row).getAllByText('94/100').length).toBeGreaterThan(0);
    expect(within(screen.getByTestId('scanner-result-row-AVGO')).getAllByText('88/100').length).toBeGreaterThan(0);
    expect(orderedSymbolsFromRows()).toEqual(['NVDA', 'AVGO', 'AMD']);
    expect(textContentWithoutObservationBoundary(container)).not.toMatch(/买入|卖出|下单|trade|broker|order/i);
    expectNoRawI18nKeys(container);
  });

  it('renders candidate research summary additively without changing row order or score labels', async () => {
    const nvda = makeCandidate({ symbol: 'NVDA', rank: 1, score: 94 });
    (nvda as ScannerCandidate & Record<string, unknown>).candidateEvidenceFrame = makeCandidateEvidenceFrame();
    (nvda as ScannerCandidate & Record<string, unknown>).candidateResearchReadiness = makeCandidateResearchReadiness();
    (nvda as ScannerCandidate & Record<string, unknown>).candidateResearchSummaryFrame = makeCandidateResearchSummaryFrame();

    getRun.mockResolvedValue(makeRunDetail({
      shortlist: [
        nvda,
        makeCandidate({ symbol: 'AVGO', rank: 2, score: 88 }),
        makeCandidate({ symbol: 'AMD', rank: 3, score: 76 }),
      ],
      selected: [nvda],
      scannerContextFrame: makeScannerContextFrame(),
    }));

    const { container } = renderUserScannerPage();

    const row = await screen.findByTestId('scanner-result-row-NVDA');
    expect(screen.getByTestId('scanner-page-profile-label')).toHaveTextContent('A股盘前扫描');
    expect(screen.getByTestId('scanner-page-profile-label')).not.toHaveTextContent(/CN\s*·|v1/);
    expect(row).toHaveTextContent('当前候选进入研究列表');
    expect(row).toHaveTextContent('待补 基本面 / 新闻催化');
    expect(row).toHaveTextContent('仅研究观察');

    const detail = screen.getAllByTestId('scanner-result-detail-NVDA')[0];
    expect(detail).toHaveTextContent('研究摘要');
    expect(detail).toHaveTextContent('技术面可用');
    expect(detail).toHaveTextContent('价格历史可用');
    expect(detail).toHaveTextContent('流动性可用');
    expect(detail).toHaveTextContent('市场驱动因素');
    expect(detail).toHaveTextContent('市场：仅观察');
    expect(detail).toHaveTextContent('流动性：支持');
    expect(detail).toHaveTextContent('主题：仅观察');
    expect(detail).toHaveTextContent('仅研究观察线索');
    expect(detail).toHaveTextContent('延迟更新');
    expect(detail).toHaveTextContent('先补充基本面与新闻催化');
    expect(detail).not.toHaveTextContent(/debugRef|source_authority_router_rejected|missing_required_evidence|Top-down market context available/i);

    expect(within(row).getAllByText('94/100').length).toBeGreaterThan(0);
    expect(within(screen.getByTestId('scanner-result-row-AVGO')).getAllByText('88/100').length).toBeGreaterThan(0);
    expect(orderedSymbolsFromRows()).toEqual(['NVDA', 'AVGO', 'AMD']);
    expect(textContentWithoutObservationBoundary(container)).not.toMatch(/买入|卖出|下单|trade|broker|order/i);
    expectNoRawI18nKeys(container);
  });

  it('surfaces candidate research packets compactly without exposing raw diagnostics or changing ranking', async () => {
    const nvda = makeCandidate({ symbol: 'NVDA', rank: 1, score: 94 });
    (nvda as ScannerCandidate & Record<string, unknown>).candidateResearchPacket = makeCandidateResearchPacket();

    getRun.mockResolvedValue(makeRunDetail({
      shortlist: [
        nvda,
        makeCandidate({ symbol: 'AVGO', rank: 2, score: 88 }),
        makeCandidate({ symbol: 'AMD', rank: 3, score: 76 }),
      ],
      selected: [nvda],
    }));

    const { container } = renderUserScannerPage();

    const row = await screen.findByTestId('scanner-result-row-NVDA');
    const rowPacket = within(row).getByTestId('scanner-candidate-research-packet-row-NVDA');
    expect(rowPacket).toHaveTextContent('研究信号');
    expect(rowPacket).toHaveTextContent('研究包');
    expect(rowPacket).toHaveTextContent('趋势与流动性线索使该标的进入本轮复核。');
    expect(rowPacket).toHaveTextContent('证据可用 4');
    expect(rowPacket).toHaveTextContent('证据部分可用 1');
    expect(rowPacket).toHaveTextContent('待补证据 2');
    expect(rowPacket).toHaveTextContent('报价可能延迟');
    expect(rowPacket).toHaveTextContent('行业/ETF线索可用');
    expect(rowPacket).toHaveTextContent('研究包可用');
    expect(rowPacket).toHaveTextContent('技术面可用');
    expect(rowPacket).toHaveTextContent('基本面证据待补');
    expect(rowPacket).toHaveTextContent('仅研究观察');
    expect(rowPacket).toHaveTextContent('仅观察');
    expect(rowPacket).toHaveTextContent('评分待确认');

    const detailPacket = await screen.findByTestId('scanner-inline-candidate-research-packet-NVDA');
    expect(detailPacket).toHaveTextContent('研究信号');
    expect(detailPacket).toHaveTextContent('研究包');
    expect(detailPacket).toHaveTextContent('证据可用 4');
    expect(detailPacket).toHaveTextContent('证据部分可用 1');
    expect(detailPacket).toHaveTextContent('待补证据 2');
    expect(detailPacket).toHaveTextContent('报价可能延迟');
    expect(detailPacket).toHaveTextContent('行业/ETF线索可用');
    expect(detailPacket).toHaveTextContent('研究包可用');
    expect(detailPacket).toHaveTextContent('评分待确认');
    expect(detailPacket).toHaveTextContent('为什么出现');
    expect(detailPacket).toHaveTextContent('主要证据');
    expect(detailPacket).toHaveTextContent('限制因素');
    expect(detailPacket).toHaveTextContent('数据质量');
    expect(detailPacket).toHaveTextContent('下一步');
    expect(detailPacket).toHaveTextContent('补充基本面与新闻催化证据后再复核。');
    expect(detailPacket).toHaveTextContent('仅研究观察');
    expect(detailPacket).not.toHaveTextContent(/sourceRefs|reasonCodes|providerDiagnostics|rawPayload|debugRef|source_authority_missing|scanner:source:debug/i);

    expect(within(row).getAllByText('94/100').length).toBeGreaterThan(0);
    expect(within(screen.getByTestId('scanner-result-row-AVGO')).getAllByText('88/100').length).toBeGreaterThan(0);
    expect(orderedSymbolsFromRows()).toEqual(['NVDA', 'AVGO', 'AMD']);
    expect(textContentWithoutObservationBoundary(container)).not.toMatch(/买入|卖出|下单|交易建议|投资建议|position sizing/i);
    expectNoRawI18nKeys(container);
  });

  it('sanitizes WorkBuddy raw research-packet and scanner gap wording before rendering', async () => {
    const nvda = makeCandidate({ symbol: 'NVDA', rank: 1, score: 94 });
    (nvda as ScannerCandidate & Record<string, unknown>).candidateResearchPacket = makeCandidateResearchPacket({
      whySurfaced: 'Some symbol evidence is present, but the packet is not complete enough for a clean research handoff.',
      primaryEvidence: ['No verified local peer group metadata is available for AAPL.'],
      limitingEvidence: ['Missing or incomplete evidence families: quote, fundamental, news.'],
      dataQualityNotes: ['Load recent local daily OHLCV for the symbol and at least two verified peers.'],
      rejectedOrLimitedReasonSafeLabel: 'Observation-only research readiness; not personalized financial advice or an instruction.',
      researchNextStep: 'Add fundamental coverage before business-quality review.',
      observationOnly: true,
    });

    getRun.mockResolvedValue(makeRunDetail({
      shortlist: [nvda],
      selected: [nvda],
      scoringNotes: ['universe / historical ohlcv / quote snapshot'],
    }));

    const { container } = renderUserScannerPage();

    const rowPacket = await screen.findByTestId('scanner-candidate-research-packet-row-NVDA');
    expect(rowPacket).toHaveTextContent('支持证据仍待补');
    expect(rowPacket).toHaveTextContent('同业对比信息待确认');
    expect(rowPacket).toHaveTextContent('待补证据类别：行情、基本面、新闻资讯。');
    expect(rowPacket.textContent || '').not.toMatch(/clean research handoff|evidence families|business-quality review|peer group metadata|daily OHLCV|Observation-only research readiness|personalized financial advice/i);

    const detailPacket = await screen.findByTestId('scanner-inline-candidate-research-packet-NVDA');
    expect(detailPacket).toHaveTextContent('当前仅达到观察级，暂不形成判断。');
    expect(detailPacket.textContent || '').not.toMatch(/clean research handoff|evidence families|business-quality review|peer group metadata|daily OHLCV|Observation-only research readiness|personalized financial advice/i);

    expect(container.textContent || '').not.toMatch(/universe\s*\/\s*historical ohlcv\s*\/\s*quote snapshot/i);
  });

  it('sanitizes WorkBuddy scanner readiness wording from direct reason and scoring-note render paths', async () => {
    const nvda = makeCandidate({ symbol: 'NVDA', rank: 1, score: 94 });
    nvda.reasonSummary = 'universe / historical ohlcv / quote snapshot';
    nvda.reasons = [];
    nvda.featureSignals = [];

    getRun.mockResolvedValue(makeRunDetail({
      shortlist: [nvda],
      selected: [nvda],
      scoringNotes: ['universe / historical ohlcv / quote snapshot'],
    }));

    const { container } = renderUserScannerPage();

    const row = await screen.findByTestId('scanner-result-row-NVDA');
    expect(row).toHaveTextContent('数据缺口：标的池行情 / 历史日线 / 实时报价');
    expect(row).not.toHaveTextContent('universe / historical ohlcv / quote snapshot');

    const detail = await screen.findByTestId('scanner-result-detail-NVDA');
    expect(detail).toHaveTextContent('数据缺口：标的池行情 / 历史日线 / 实时报价');
    expect(detail).not.toHaveTextContent('universe / historical ohlcv / quote snapshot');

    expect(screen.getByTestId('scanner-consumer-next-action')).not.toHaveTextContent('universe / historical ohlcv / quote snapshot');
    expect(container.textContent || '').not.toMatch(/universe\s*\/\s*historical ohlcv\s*\/\s*quote snapshot/i);
    expect(container.textContent || '').not.toContain('OBSERVATION-ONLY 证据摘要');
  });

  it('renders candidate provenance additively inside evidence areas without changing row order or score labels', async () => {
    const nvda = makeCandidate({ symbol: 'NVDA', rank: 1, score: 94 });
    (nvda as ScannerCandidate & Record<string, unknown>).candidateEvidenceFrame = makeCandidateEvidenceFrame();
    (nvda as ScannerCandidate & Record<string, unknown>).candidateResearchReadiness = makeCandidateResearchReadiness();
    (nvda as ScannerCandidate & Record<string, unknown>).candidateSourceProvenanceFrame = makeCandidateSourceProvenanceFrame();

    getRun.mockResolvedValue(makeRunDetail({
      shortlist: [
        nvda,
        makeCandidate({ symbol: 'AVGO', rank: 2, score: 88 }),
        makeCandidate({ symbol: 'AMD', rank: 3, score: 76 }),
      ],
      selected: [nvda],
    }));

    const { container } = renderUserScannerPage();

    const row = await screen.findByTestId('scanner-result-row-NVDA');
    expect(row).toHaveTextContent('来源确认：含评分级');
    expect(row).toHaveTextContent('时效：含回退');
    expect(row).toHaveTextContent('观察级 3 项');

    const detail = screen.getAllByTestId('scanner-result-detail-NVDA')[0];
    expect(detail).toHaveTextContent('来源依据');
    expect(detail).toHaveTextContent('回退/代理 2 项');
    expect(detail).toHaveTextContent('待核验 1 项');
    expect(detail).not.toHaveTextContent(/debugRef|sourceId|provider|router|cache|trace|internal|raw/i);

    expect(within(row).getAllByText('94/100').length).toBeGreaterThan(0);
    expect(within(screen.getByTestId('scanner-result-row-AVGO')).getAllByText('88/100').length).toBeGreaterThan(0);
    expect(orderedSymbolsFromRows()).toEqual(['NVDA', 'AVGO', 'AMD']);
    expect(textContentWithoutObservationBoundary(container)).not.toMatch(/买入|卖出|下单|trade|broker|order/i);
    expectNoRawI18nKeys(container);
  });

  it('keeps legacy scanner responses rendering when candidate evidence fields are absent', async () => {
    const { container } = renderUserScannerPage();

    const row = await screen.findByTestId('scanner-result-row-NVDA');
    expect(within(row).getAllByText('94/100').length).toBeGreaterThan(0);
    expect(row).not.toHaveTextContent('待补');
    expect(screen.queryByTestId('scanner-candidate-research-packet-row-NVDA')).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-inline-candidate-research-packet-NVDA')).not.toBeInTheDocument();
    expect(screen.queryByText('证据覆盖')).not.toBeInTheDocument();
    expect(orderedSymbolsFromRows()).toEqual(['NVDA', 'AVGO', 'AMD']);
    expectNoRawI18nKeys(container);
  });

  it('fail closes missing scanner context as insufficient instead of supportive context', async () => {
    renderUserScannerPage();

    const strip = await screen.findByTestId('scanner-top-down-context-strip');
    expect(strip).toHaveTextContent('市场驱动因素');
    expect(strip).toHaveTextContent('证据不足');
    expect(strip).toHaveTextContent('市场：证据不足');
    expect(strip).toHaveTextContent('宏观：证据不足');
    expect(strip).toHaveTextContent('流动性：证据不足');
    expect(strip).toHaveTextContent('边界：仅研究观察');
    expect(strip).toHaveTextContent('市场、流动性或主题上下文仍有缺口');
    expect(strip).not.toHaveTextContent(/支持性上下文|supportive context/i);
  });

  it('marks unavailable cn context as blocked without leaking internal or trading terms', async () => {
    getRun.mockResolvedValue(makeRunDetail({
      market: 'cn',
      profile: 'cn_preopen_v1',
      scannerContextFrame: makeScannerContextFrame({
        marketReadiness: {
          contractVersion: 'research_readiness_v1',
          researchReady: false,
          readinessState: 'insufficient',
          verdictLabel: '证据不足',
          blockingReasons: ['source_authority_router_rejected'],
          missingEvidence: ['macro', 'liquidity'],
          evidenceCoverage: {
            scoreGradeCount: 0,
            observationOnlyCount: 1,
            missingCount: 2,
            totalCount: 3,
          },
          sourceAuthority: 'unavailable',
          freshnessFloor: 'unknown',
          consumerActionBoundary: 'no_advice',
          nextEvidenceNeeded: ['等待中国市场上下文恢复后再复核'],
        },
        macroRegime: {
          state: 'blocked',
          label: 'CN context unavailable',
          freshness: 'unknown',
          blockers: ['cn_context_unavailable'],
          observationOnly: true,
          sourceAuthorityAllowed: false,
          scoreContributionAllowed: false,
        },
        liquidityFrame: {
          state: 'blocked',
          label: 'CN liquidity context unavailable',
          freshness: 'unknown',
          blockers: ['cn_context_unavailable'],
          observationOnly: true,
          sourceAuthorityAllowed: false,
          scoreContributionAllowed: false,
          proxyOnly: false,
        },
        assetClassBias: {
          state: 'blocked',
          label: 'Bias unavailable',
          blockers: ['cn_context_unavailable'],
          observationOnly: true,
        },
        themeFrame: {
          state: 'blocked',
          label: 'Theme context unavailable',
          freshness: 'unknown',
          blockers: ['cn_context_unavailable'],
          observationOnly: true,
          proxyOnly: false,
          themes: [],
        },
        universePolicy: {
          type: 'default',
          label: 'Profile default universe',
          blockers: ['cn_context_unavailable'],
        },
      }),
    }));

    const { container } = renderUserScannerPage();

    const strip = await screen.findByTestId('scanner-top-down-context-strip');
    expect(strip).toHaveTextContent('阻断');
    expect(strip).toHaveTextContent('市场：证据不足');
    expect(strip).toHaveTextContent('宏观：阻断');
    expect(strip).toHaveTextContent('流动性：阻断');
    expect(strip).toHaveTextContent('资产：阻断');
    expect(strip).toHaveTextContent('主题：阻断');
    expect(strip).toHaveTextContent('标的池：默认池');
    expect(strip).toHaveTextContent('当前市场上下文暂不可用');
    expect(textContentWithoutObservationBoundary(container)).not.toMatch(/cn_context_unavailable|provider|cache|router|sourceAuthority|buy|sell|order|trade|broker|买入|卖出|下单/i);
  });

  it('renders a scanner conclusion band when no candidate is usable', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun({
      shortlist: [],
      selected: [],
      summary: {
        universeCount: 11,
        submittedCount: 11,
        evaluatedCount: 3,
        selectedCount: 0,
        rejectedCount: 3,
        dataFailedCount: 0,
        skippedCount: 0,
        errorCount: 0,
        limitedByResultCap: false,
      },
      candidates: [
        {
          symbol: 'MARA',
          name: 'MARA Holdings',
          rank: 1,
          status: 'rejected',
          score: 55,
          provider: 'alpaca',
          reason: 'below liquidity threshold',
          failedRules: ['below_liquidity_threshold'],
          missingFields: [],
          metrics: {},
        },
      ],
    }));

    renderUserScannerPage();

    const band = await screen.findByTestId('scanner-conclusion-band');
    await waitFor(() => expect(band).toHaveTextContent('本次未形成入选候选'));
    expect(band).toHaveTextContent('候选 0');
    expect(band).toHaveTextContent('覆盖与淘汰分布');
    expect(band).not.toHaveTextContent('不代表市场没有机会');
  });

  it('renders data readiness labels from run detail blocker buckets without raw strings', async () => {
    getRun.mockResolvedValue(makeRunDetail({
      status: 'empty',
      shortlist: [],
      selected: [],
      candidates: [],
      diagnostics: {
        dataReadiness: {
          state: 'blocked',
          market: 'cn',
          profile: 'cn_preopen_v1',
          universeSize: 0,
          quoteCoverage: 'unknown',
          historyCoverage: 'unknown',
          freshness: 'unknown',
          blockerBucket: 'missing_quote_snapshot',
          consumerSummary: '报价快照待补。',
          nextDataAction: '补充报价快照后重新运行。',
        },
      },
      summary: {
        universeCount: 0,
        submittedCount: 0,
        evaluatedCount: 0,
        selectedCount: 0,
        rejectedCount: 0,
        dataFailedCount: 0,
        skippedCount: 0,
        errorCount: 0,
        limitedByResultCap: false,
      },
    }));

    const { container } = renderUserScannerPage();

    const band = await screen.findByTestId('scanner-conclusion-band');
    expect(band).toHaveTextContent('数据待补');
    expect(band).toHaveTextContent('报价信息待补');
    expect(band).toHaveTextContent('补充报价快照后重新运行。');
    expect(container).not.toHaveTextContent(/missing_quote_snapshot|0ms|0\s*\/\s*0\s*\/\s*0/);
    expect(textContentWithoutObservationBoundary(container)).not.toMatch(/buy|sell|hold|target price|stop-loss|position sizing|买入|卖出|持有|目标价|止损|仓位|建仓|加仓|减仓/i);
  });

  it('uses scanner status data readiness when no run detail is available', async () => {
    getRuns.mockResolvedValue(makeHistoryResponse([]));
    getRun.mockResolvedValue(null as never);
    getStatus.mockResolvedValue({
      market: 'cn',
      profile: 'cn_preopen_v1',
      watchlistDate: '2026-04-22',
      todayTradingDay: true,
      scheduleEnabled: false,
      scheduleRunImmediately: false,
      notificationEnabled: false,
      qualitySummary: {
        available: false,
        reviewWindowDays: 5,
        runCount: 0,
        reviewedRunCount: 0,
        reviewedCandidateCount: 0,
        strongCount: 0,
        mixedCount: 0,
        weakCount: 0,
      },
      dataReadiness: {
        state: 'blocked',
        market: 'cn',
        profile: 'cn_preopen_v1',
        universeSize: 0,
        quoteCoverage: 'unknown',
        historyCoverage: 'unknown',
        freshness: 'unknown',
        blockerBucket: 'missing_history',
        consumerSummary: '历史数据待补。',
        nextDataAction: '补充历史数据后再扫描。',
      },
    });

    renderUserScannerPage();

    const band = await screen.findByTestId('scanner-conclusion-band');
    expect(band).toHaveTextContent('数据待补');
    expect(band).toHaveTextContent('历史数据待补');
    expect(band).toHaveTextContent('补充历史数据后再扫描。');
    expect(screen.getByTestId('scanner-status-strip')).toHaveTextContent('数据待补');
    expect(screen.getByTestId('scanner-status-strip')).toHaveTextContent('历史数据待补');
    expect(screen.getByTestId('scanner-workbench-empty-state')).toHaveTextContent('历史数据待补');
    expect(screen.getByTestId('scanner-workbench-empty-state')).not.toHaveTextContent(/missing_history|0ms|0\s*\/\s*0\s*\/\s*0/);
  });

  it('does not present a zero-duration empty payload as a completed scanner run', async () => {
    getRun.mockResolvedValue(makeRunDetail({
      status: 'completed',
      runAt: '2026-04-22T08:30:00',
      completedAt: '2026-04-22T08:30:00',
      universeSize: 300,
      preselectedSize: 300,
      evaluatedSize: 0,
      shortlistSize: 0,
      sourceSummary: null,
      headline: null,
      universeNotes: [],
      scoringNotes: [],
      diagnostics: {
        universeSelection: {
          universeType: 'default',
          themeId: null,
          themeLabel: null,
          requestedSymbolsCount: 0,
          acceptedSymbolsCount: 0,
          rejectedSymbols: [],
          universeNotes: [],
        },
      },
      summary: {
        universeCount: 300,
        submittedCount: 300,
        evaluatedCount: 0,
        selectedCount: 0,
        rejectedCount: 0,
        dataFailedCount: 0,
        skippedCount: 0,
        errorCount: 0,
        limitedByResultCap: false,
      },
      selected: [],
      candidates: [],
      shortlist: [],
    }));

    const { container } = renderUserScannerPage();

    const band = await screen.findByTestId('scanner-conclusion-band');
    expect(band).toHaveTextContent('扫描器尚未产出候选集');
    expect(band).toHaveTextContent('可稍后重试');
    const statusStrip = screen.getByTestId('scanner-status-strip');
    expect(statusStrip).toHaveTextContent('等待可用数据');
    expect(statusStrip).toHaveTextContent('候选集未产出');
    expect(statusStrip).not.toHaveTextContent(/0\s*\/\s*0\s*\/\s*0/);
    expect(screen.getByTestId('scanner-summary-counters')).toHaveTextContent('候选集');
    expect(screen.getByTestId('scanner-summary-counters')).toHaveTextContent('未产出');
    expect(screen.getByTestId('scanner-summary-counters')).not.toHaveTextContent(/\b0\b/);
    expect(screen.getByTestId('scanner-summary-rail-counts')).toHaveTextContent('未产出');
    expect(screen.getByTestId('scanner-summary-rail-counts')).not.toHaveTextContent(/\b0\b/);
    expect(screen.getByTestId('scanner-workbench-empty-state')).toHaveTextContent('候选表暂不展示');
    expect(screen.queryByTestId('scanner-empty-history-fallback')).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-empty-success-preview')).not.toBeInTheDocument();
    expect(textContentWithoutObservationBoundary(container)).not.toMatch(/0ms|已验证|Verified|provider|fallback|cache|runtime|schema|requestId|traceId|observation-only|Low-evidence filter active|evidence families/i);
    expect(textContentWithoutObservationBoundary(container)).not.toMatch(/买入|卖出|下单|交易建议|投资建议|止损|目标价|position sizing|target price|stop loss|buy now|sell now/i);
  });

  it('labels zero-count latest and previous summaries as unavailable instead of completed 0ms cards', async () => {
    const currentNoCandidateRun = makeCryptoDiagnosticsRun({
      id: 11,
      shortlist: [],
      selected: [],
      summary: {
        universeCount: 11,
        submittedCount: 11,
        evaluatedCount: 3,
        selectedCount: 0,
        rejectedCount: 3,
        dataFailedCount: 0,
        skippedCount: 0,
        errorCount: 0,
        limitedByResultCap: false,
      },
      candidates: [
        {
          symbol: 'MARA',
          name: 'MARA Holdings',
          rank: 1,
          status: 'rejected',
          score: 55,
          provider: 'alpaca',
          reason: 'below liquidity threshold',
          failedRules: ['below_liquidity_threshold'],
          missingFields: [],
          metrics: {},
        },
      ],
    });
    const previousPseudoRun = makeRunDetail({
      id: 10,
      status: 'completed',
      runAt: '2026-04-22T08:30:00',
      completedAt: '2026-04-22T08:30:00',
      universeSize: 0,
      preselectedSize: 0,
      evaluatedSize: 0,
      shortlistSize: 0,
      sourceSummary: null,
      headline: null,
      universeNotes: [],
      scoringNotes: [],
      diagnostics: {},
      summary: {
        universeCount: 0,
        submittedCount: 0,
        evaluatedCount: 0,
        selectedCount: 0,
        rejectedCount: 0,
        dataFailedCount: 0,
        skippedCount: 0,
        errorCount: 0,
        limitedByResultCap: false,
      },
      selected: [],
      candidates: [],
      shortlist: [],
    });
    getRuns.mockResolvedValue(makeHistoryResponse([
      makePseudoResultHistoryItem({
        id: 11,
        market: 'us',
        profile: 'us_preopen_v1',
        profileLabel: 'US Pre-open Scanner v1',
        universeType: 'theme',
        themeId: 'crypto_miners',
        themeLabel: '加密矿企',
      }),
      makePseudoResultHistoryItem({
        id: 10,
        market: 'us',
        profile: 'us_preopen_v1',
        profileLabel: 'US Pre-open Scanner v1',
        universeType: 'theme',
        themeId: 'crypto_miners',
        themeLabel: '加密矿企',
      }),
    ]));
    getRun.mockImplementation(async (runId: number) => (runId === 10 ? previousPseudoRun : currentNoCandidateRun));

    renderUserScannerPage();

    const comparisonDisclosure = await screen.findByTestId('scanner-run-comparison-strip');
    fireEvent.click(within(comparisonDisclosure).getByRole('button', { name: /展开 比较记录|Expand Comparison records/i }));
    const resultHistory = await within(comparisonDisclosure).findByTestId('scanner-result-history-summary');
    await waitFor(() => {
      expect(within(resultHistory).getByTestId('scanner-run-summary-上次扫描')).toBeInTheDocument();
    });

    const currentSummary = within(resultHistory).getByTestId('scanner-run-summary-本次扫描');
    expect(currentSummary).toHaveTextContent('无候选');
    expect(currentSummary).toHaveTextContent('淘汰数量');
    expect(currentSummary).toHaveTextContent('3');

    ['最近扫描', '上次扫描'].forEach((title) => {
      const summary = within(resultHistory).getByTestId(`scanner-run-summary-${title}`);
      expect(summary).toHaveTextContent('暂不可用');
      expect(summary).toHaveTextContent('候选集尚未产出');
      expect(summary).toHaveTextContent('数据不足，可重试、查看历史或打开市场概览');
      expect(summary).not.toHaveTextContent(/0ms|候选数量\s*0|淘汰数量\s*0|失败数量\s*0|完成/);
    });
    expect(resultHistory).not.toHaveTextContent(/0ms|0\s*\/\s*0\s*\/\s*0/);
  });

  it('marks all three scan summary cards unavailable for pseudo-complete zero-count summaries', () => {
    const unavailableSummary = (title: string) => ({
      title,
      statusLabel: '暂不可用',
      bestCandidate: '尚未产出',
      candidateCount: 0,
      rejectedCount: 0,
      failedCount: 0,
      dataStatusLabel: '运行数据暂不可用',
      durationLabel: '--',
      runTimeLabel: '04/22 08:30',
      errorSummary: null,
      unavailable: true,
      unavailableTitle: '候选集尚未产出',
      unavailableBody: '运行数据不足或暂不可用。下一步：重新运行扫描、查看历史，或打开 Watchlist / Market Overview。',
    });

    render(
      <ScannerResultHistorySummary
        currentSummary={unavailableSummary('本次扫描')}
        recentSummary={unavailableSummary('最近扫描')}
        previousSummary={unavailableSummary('上次扫描')}
        comparisonItems={[]}
        hasHistory
        language="zh"
      />,
    );

    const resultHistory = screen.getByTestId('scanner-result-history-summary');

    ['本次扫描', '最近扫描', '上次扫描'].forEach((title) => {
      const summary = within(resultHistory).getByTestId(`scanner-run-summary-${title}`);
      expect(summary).toHaveTextContent('暂不可用');
      expect(summary).toHaveTextContent('候选集尚未产出');
      expect(summary).toHaveTextContent('运行数据不足或暂不可用');
      expect(summary).not.toHaveTextContent(/0ms|候选数量\s*0|淘汰数量\s*0|失败数量\s*0|完成/);
    });
    expect(resultHistory).not.toHaveTextContent(/0ms|0\s*\/\s*0\s*\/\s*0/);
  });

  it('keeps completed-empty classification when history facts arrive before run detail', async () => {
    getRuns.mockResolvedValue(makeHistoryResponse([
      makeHistoryItem({
        shortlistSize: 0,
        topSymbols: [],
        headline: '历史扫描：本次无入选候选',
      }),
    ]));
    getRun.mockImplementation(() => new Promise(() => {}));

    renderUserScannerPage();

    await waitFor(() => {
      expect(screen.getByTestId('scanner-conclusion-band')).toHaveTextContent('本次未形成入选候选');
    });
    expect(screen.getByTestId('scanner-conclusion-band')).toHaveTextContent('候选 0');
    expect(screen.getByTestId('scanner-conclusion-band')).not.toHaveTextContent('首次使用：先运行一次扫描');
    expect(screen.getByTestId('scanner-workbench-empty-state')).toHaveTextContent('本次未形成入选候选');
    expect(screen.getByTestId('scanner-workbench-empty-state')).not.toHaveTextContent('尚未运行扫描');
  });

  it('uses a retry CTA with bounded no-candidate guidance while keeping the same run parameters', async () => {
    const noCandidateRun = makeCryptoDiagnosticsRun({
      shortlistSize: 8,
      universeSize: 180,
      preselectedSize: 40,
      shortlist: [],
      selected: [],
      summary: {
        universeCount: 11,
        submittedCount: 11,
        evaluatedCount: 3,
        selectedCount: 0,
        rejectedCount: 3,
        dataFailedCount: 0,
        skippedCount: 0,
        errorCount: 0,
        limitedByResultCap: false,
      },
      candidates: [
        {
          symbol: 'MARA',
          name: 'MARA Holdings',
          rank: 1,
          status: 'rejected',
          score: 55,
          provider: 'alpaca',
          reason: 'below liquidity threshold',
          failedRules: ['below_liquidity_threshold'],
          missingFields: [],
          metrics: {},
        },
      ],
    });
    getRun.mockResolvedValue(noCandidateRun);
    runScan.mockResolvedValueOnce(noCandidateRun);

    renderUserScannerPage();

    const band = await screen.findByTestId('scanner-conclusion-band');
    const nextSteps = await screen.findByTestId('scanner-workflow-next-steps');
    const runButton = await screen.findByRole('button', { name: '重新扫描' });
    expect(runButton).toBeEnabled();
    expect(runButton).toHaveClass('bg-[var(--wolfy-surface-input)]');
    expect(runButton).not.toHaveClass('bg-[var(--wolfy-accent)]');
    expect(band).toHaveTextContent('本次未形成入选候选');
    expect(band).toHaveTextContent('本次无可用候选，仅供观察。');
    expect(band).toHaveTextContent('当前无可用候选，先查看淘汰分布或历史记录，再决定是否重新扫描。');
    expect(band).not.toHaveTextContent('先使用候选行作为主证据');
    expect(nextSteps).toHaveTextContent('下一步');
    expect(nextSteps).toHaveTextContent('换市场或配置');
    expect(nextSteps).toHaveTextContent('查看历史');
    expect(nextSteps).toHaveTextContent('首选研究路径');
    expect(nextSteps).toHaveTextContent('可选保存路径');
    expect(nextSteps).toHaveTextContent('Market Overview');
    expect(nextSteps).not.toHaveTextContent('不代表市场没有机会');
    expect(nextSteps).toHaveTextContent('可手动研究单个代码');
    expect(nextSteps).toHaveTextContent('不会自动写入观察名单');
    expect(nextSteps).not.toHaveTextContent('功能预览');
    expect(nextSteps).not.toHaveTextContent('示例预览');
    expect(nextSteps).not.toHaveTextContent('预览候选');
    expect(within(nextSteps).queryByTestId('scanner-empty-success-preview')).not.toBeInTheDocument();
    expect(within(nextSteps).queryByTestId('scanner-next-step-preview')).not.toBeInTheDocument();
    expect(within(nextSteps).getByRole('link', { name: /打开观察列表视图|Open Watchlist view/i })).toHaveAttribute('href', '/zh/watchlist');
    expect(within(nextSteps).getByRole('link', { name: /打开 Market Overview/i })).toHaveAttribute('href', '/zh/market-overview');
    const runFacts = await screen.findByTestId('scanner-run-facts');
    expect(runFacts).toHaveTextContent('运行事实');
    expect(runFacts).toHaveTextContent('市场');
    expect(runFacts).toHaveTextContent('美股');
    expect(runFacts).toHaveTextContent('策略');
    expect(runFacts).toHaveTextContent('US Pre-open Scanner');
    expect(runFacts).toHaveTextContent('运行时间');
    expect(runFacts).toHaveTextContent('完成时间');
    expect(runFacts).toHaveTextContent('观察日期');
    expect(runFacts).toHaveTextContent('标的池');
    expect(runFacts).toHaveTextContent('180');
    expect(runFacts).toHaveTextContent('预筛');
    expect(runFacts).toHaveTextContent('40');
    expect(runFacts).toHaveTextContent('评估');
    expect(runFacts).toHaveTextContent('3');
    expect(runFacts).toHaveTextContent('入选');
    expect(runFacts).toHaveTextContent('0');
    expect(runFacts).not.toHaveTextContent(/provider|reasonCode|below_liquidity_threshold|raw/i);
    expect(screen.getByTestId('scanner-history-scope-hint')).toHaveTextContent('个人历史仅基于当前账号可访问的扫描记录');
    expect(screen.getByTestId('scanner-history-scope-hint')).toHaveTextContent('美股');

    fireEvent.click(within(nextSteps).getByRole('button', { name: '重新运行同参数' }));

    await waitFor(() => {
      expect(runScan).toHaveBeenCalledWith({
        market: 'us',
        profile: 'us_preopen_v1',
        shortlistSize: 8,
        universeLimit: 180,
        detailLimit: 40,
        universeType: 'theme',
        themeId: 'crypto_miners',
      });
    });
  });

  it('keeps manual symbol handoff from no-candidate states without preview handoff', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun({
      shortlist: [],
      selected: [],
      summary: {
        universeCount: 11,
        submittedCount: 11,
        evaluatedCount: 3,
        selectedCount: 0,
        rejectedCount: 3,
        dataFailedCount: 0,
        skippedCount: 0,
        errorCount: 0,
        limitedByResultCap: false,
      },
      candidates: [
        {
          symbol: 'MARA',
          name: 'MARA Holdings',
          rank: 1,
          status: 'rejected',
          score: 61,
          provider: 'alpaca',
          reason: 'below liquidity threshold',
          failedRules: ['below_liquidity_threshold'],
          missingFields: [],
          metrics: {},
        },
      ],
    }));
    addWatchlistItem.mockResolvedValueOnce(makeWatchlistItem({
      id: 401,
      symbol: 'TSLA',
      market: 'us',
      name: 'TSLA',
      scannerRunId: null,
      scannerRank: null,
      scannerScore: null,
    }));

    const { container } = renderUserScannerPage();

    const nextSteps = await screen.findByTestId('scanner-workflow-next-steps');
    expect(within(nextSteps).getByTestId('scanner-primary-research-path')).toHaveTextContent('首选研究路径');
    expect(nextSteps).not.toHaveTextContent('预览候选');
    expect(nextSteps).not.toHaveTextContent('预览不会改变官方入选或评分');
    expect(within(nextSteps).queryByTestId('scanner-empty-success-preview')).not.toBeInTheDocument();
    expect(within(nextSteps).queryByTestId('scanner-next-step-preview')).not.toBeInTheDocument();

    fireEvent.change(within(nextSteps).getByLabelText(/手动补充研究代码/), { target: { value: 'TSLA' } });
    fireEvent.click(within(nextSteps).getByRole('button', { name: /加入观察名单 TSLA/ }));

    await waitFor(() => {
      expect(addWatchlistItem).toHaveBeenCalledWith(expect.objectContaining({
        symbol: 'TSLA',
        market: 'us',
        name: 'TSLA',
        source: 'scanner',
        notes: expect.stringMatching(/Scanner recovery|手动补充/),
      }));
    });
    expect(await within(nextSteps).findByRole('button', { name: /已在观察名单|Already in Watchlist/ })).toBeInTheDocument();

    fireEvent.change(within(nextSteps).getByLabelText(/手动补充研究代码/), { target: { value: 'TSLA' } });
    fireEvent.click(within(nextSteps).getByRole('button', { name: /打开 TSLA|Open TSLA/ }));

    expect(await screen.findByText('Stock Research Landing')).toBeInTheDocument();
    expect(analyzeAsync).not.toHaveBeenCalled();
    expect(container).not.toHaveTextContent(/provider|reasonCode|fallback_source|below_liquidity_threshold|raw diagnostics|JSON/i);
  });

  it('renders a scanner conclusion band when evidence is insufficient', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun({
      status: 'failed',
      failureReason: 'not_enough_history',
      shortlist: [],
      selected: [],
      summary: {
        universeCount: 11,
        submittedCount: 11,
        evaluatedCount: 2,
        selectedCount: 0,
        rejectedCount: 0,
        dataFailedCount: 2,
        skippedCount: 0,
        errorCount: 0,
        limitedByResultCap: false,
      },
      candidates: [
        {
          symbol: 'CIFR',
          name: 'Cipher Mining',
          rank: 1,
          status: 'data_failed',
          score: null,
          provider: null,
          reason: 'missing price history',
          failedRules: ['not_enough_history'],
          missingFields: ['history'],
          metrics: {},
        },
      ],
    }));

    renderUserScannerPage();

    await waitFor(() => {
      expect(screen.getByTestId('scanner-conclusion-band')).toHaveTextContent('证据不足');
      expect(screen.getByTestId('scanner-conclusion-band')).toHaveTextContent('候选 0');
      expect(screen.getByTestId('scanner-conclusion-band')).toHaveTextContent('补齐行情或历史证据');
    });
  });

  it('uses a retry CTA with bounded insufficient-evidence guidance', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun({
      status: 'failed',
      failureReason: 'not_enough_history',
      shortlist: [],
      selected: [],
      summary: {
        universeCount: 11,
        submittedCount: 11,
        evaluatedCount: 2,
        selectedCount: 0,
        rejectedCount: 0,
        dataFailedCount: 2,
        skippedCount: 0,
        errorCount: 0,
        limitedByResultCap: false,
      },
      candidates: [
        {
          symbol: 'CIFR',
          name: 'Cipher Mining',
          rank: 1,
          status: 'data_failed',
          score: null,
          provider: null,
          reason: 'missing price history',
          failedRules: ['not_enough_history'],
          missingFields: ['history'],
          metrics: {},
        },
      ],
    }));

    renderUserScannerPage();

    const band = await screen.findByTestId('scanner-conclusion-band');
    const runButton = await screen.findByRole('button', { name: '重新扫描' });
    expect(runButton).toBeEnabled();
    expect(runButton).toHaveClass('bg-[var(--wolfy-surface-input)]');
    expect(runButton).not.toHaveClass('bg-[var(--wolfy-accent)]');
    expect(band).toHaveTextContent('数据不足，评分已暂停。');
    expect(band).toHaveTextContent('当前证据不足，重新扫描仅刷新候选观察，不代表可用候选。');
    expect(band).not.toHaveTextContent('先使用候选行作为主证据');
  });

  it('replaces actiony scanner labels with observation and risk-boundary copy', async () => {
    const { container } = renderUserScannerPage();

    await screen.findByTestId('scanner-result-row-NVDA');
    expect(container).toHaveTextContent('观察区');
    expect(container).toHaveTextContent('参考区间');
    expect(container).toHaveTextContent('风险边界');
    expect(container).not.toHaveTextContent(/建仓|止损|before acting|执行操作|Entry|Target|Stop/i);
    expect(textContentWithoutObservationBoundary(container)).not.toMatch(/买入|卖出|加仓|减仓|buy|sell|recommend(?:ation)?/i);
  });

  it('renders compact scanner workspace without the old decorative hero', async () => {
    renderUserScannerPage();

    expect(await screen.findByTestId('user-scanner-workspace')).toBeInTheDocument();
    await screen.findByTestId('scanner-result-row-NVDA');
    const observationBoundary = screen.getByTestId('observation-only-boundary');
    expect(observationBoundary).toHaveAttribute('data-observation-boundary-surface', 'scanner');
    expect(observationBoundary).toHaveTextContent('研究边界摘要');
    expect(observationBoundary).toHaveTextContent('受边界约束的模型或规则输出');
    expect(observationBoundary).toHaveTextContent('请独立核验适用性');
    expect(observationBoundary.textContent || '').not.toMatch(/observation-only|OBSERVATION-ONLY|交易建议|买入|卖出|持有/i);
    expect(screen.getByTestId('user-scanner-workspace').textContent || '').not.toMatch(/\bOBSERVATION-ONLY\b|OBSERVATION-ONLY 证据摘要/i);
    expect(screen.getByTestId('scanner-wide-workspace-scope')).toHaveAttribute('data-workspace-width', 'near-full');
    expect(screen.getByTestId('user-scanner-workspace')).toHaveAttribute('data-terminal-primitive', 'page-shell');
    expect(screen.getByTestId('scanner-page-heading')).toHaveAttribute('data-terminal-primitive', 'dense-page-header');
    expect(screen.getByTestId('scanner-status-strip')).toHaveAttribute('data-terminal-primitive', 'dense-status-strip');
    expect(screen.getByTestId('scanner-status-strip-scroll-frame')).toHaveClass('relative');
    expect(screen.getByTestId('scanner-status-strip-scroll-frame')).toContainElement(screen.getByTestId('scanner-status-strip'));
    expect(screen.getByTestId('scanner-status-strip-scroll-frame').querySelector('span[aria-hidden="true"]')).toHaveClass('bg-gradient-to-l');
    expect(screen.getByTestId('scanner-launch-bar')).toHaveAttribute('data-terminal-primitive', 'dense-table-shell');
    expect(screen.getByTestId('scanner-command-bar')).toHaveAttribute('data-terminal-primitive', 'dense-command-bar');
    expect(screen.getByTestId('scanner-launch-bar')).toHaveClass('rounded-xl', 'border', 'p-2');
    expect(screen.getByTestId('scanner-command-panel')).toHaveClass('rounded-xl', 'border');
    expect(screen.getByTestId('scanner-results-panel')).toHaveClass('rounded-xl', 'border');
    expect(screen.getByTestId('scanner-summary-rail')).toHaveAttribute('data-linear-primitive', 'surface');
    expect(screen.getByTestId('scanner-summary-rail')).toHaveAttribute('data-layout-zone', 'ContextRail');
    expect(screen.getByTestId('scanner-launch-bar')).not.toHaveClass('rounded-[14px]', 'shadow-[0_20px_80px_rgba(0,0,0,0.22)]');
    expect(screen.queryByTestId('scanner-control-rail')).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-sidebar')).not.toBeInTheDocument();
    expect(screen.getByTestId('scanner-launch-bar')).toContainElement(screen.getByTestId('scanner-run-button'));
    expect(screen.queryByTestId('scanner-results-stage')).not.toBeInTheDocument();
    expect(screen.queryByTestId('user-scanner-bento-hero')).not.toBeInTheDocument();
    expect(screen.getByTestId('scanner-candidate-scroll-region')).toBeInTheDocument();
    expect(screen.getByTestId('scanner-run-button')).toHaveTextContent('启动扫描');
    expect(screen.queryByText('TACTICAL ROUTER')).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /MARKET SCANNER|市场扫描/ })).not.toBeInTheDocument();
  });

  it('renders exactly one compact semantic scanner page heading without internal terms', async () => {
    renderUserScannerPage({ initialEntry: '/zh/scanner' });

    const heading = await screen.findByRole('heading', { level: 1, name: '发现 / 扫描器' });
    expect(heading).toHaveClass('text-xl', 'md:text-2xl');
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.queryByText(/provider_timeout|MarketCache|generatedCandidates|failedCandidates/i)).not.toBeInTheDocument();
  });

  it('uses terminal button variants for primary scanner controls and candidate actions', async () => {
    renderUserScannerPage({ initialEntry: '/zh/scanner' });

    const runButton = await screen.findByTestId('scanner-run-button');
    const moreActions = await screen.findByTestId('scanner-more-actions');
    const moreTrigger = within(moreActions).getByRole('button', { name: /更多|More/i });
    const row = await screen.findByTestId('scanner-result-row-NVDA');

    expect(runButton).toHaveAttribute('data-terminal-primitive', 'button');
    expect(moreTrigger).toHaveAttribute('data-terminal-primitive', 'button');
    expect(getActionButton(row, /详情|Detail/i)).toHaveAttribute('data-terminal-primitive', 'button');
    fireEvent.click(getActionButton(row, /更多|More/i));
    const rankedRow = getRankedRow('NVDA');
    expect(within(rankedRow).getByRole('button', { name: /打开个股研究|Open stock research/i })).toHaveAttribute('data-terminal-primitive', 'button');
    expect(within(rankedRow).getByRole('button', { name: /追踪|Track/i })).toHaveAttribute('data-terminal-primitive', 'button');

    fireEvent.click(moreTrigger);

    const morePanel = await screen.findByTestId('scanner-more-actions-panel');
    expect(within(morePanel).getByRole('button', { name: /导出 CSV|Export CSV/i })).toHaveAttribute('data-terminal-primitive', 'button');
    expect(screen.getByTestId('scanner-history-trigger')).toHaveAttribute('data-terminal-primitive', 'button');
  });

  it('loads scanner run history once on initial route entry', async () => {
    renderUserScannerPage();

    expect(await screen.findByTestId('scanner-result-row-NVDA')).toBeInTheDocument();
    await waitFor(() => {
      expect(getRun).toHaveBeenCalledWith(11);
    });
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(getRuns).toHaveBeenCalledTimes(1);
    expect(getRuns).toHaveBeenCalledWith({
      market: 'cn',
      profile: 'cn_preopen_v1',
      page: 1,
      limit: 8,
    });
  });

  it('keeps scanner diagnostics deferred and does not load the backtest lab on default scanner load', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    expect(await screen.findByTestId('scanner-result-row-WULF')).toBeInTheDocument();
    expect(screen.queryByTestId('scanner-score-trust-WULF')).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-backtest-lab')).not.toBeInTheDocument();
    expect(loadScannerBacktestLabMock).not.toHaveBeenCalled();
  });

  it('loads the backtest lab only after opening the strategy experiment disclosure', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    const experiment = await screen.findByTestId('scanner-strategy-experiment');
    expect(loadScannerBacktestLabMock).not.toHaveBeenCalled();

    fireEvent.click(within(experiment).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i }));

    expect(await screen.findByTestId('scanner-backtest-lab')).toBeInTheDocument();
    expect(loadScannerBacktestLabMock).toHaveBeenCalledTimes(1);
  });

  it('keeps scanner page wrappers document-scrollable while bounding candidates internally', async () => {
    renderUserScannerPage();

    await screen.findByTestId('scanner-run-button');
    const candidateScrollRegion = await screen.findByTestId('scanner-candidate-scroll-region');

    expect(screen.getByTestId('scanner-ranking-board-page')).not.toHaveClass('xl:overflow-hidden', 'xl:h-[calc(100vh-96px)]');
    expect(screen.getByTestId('user-scanner-workspace')).not.toHaveClass('h-full', 'overflow-hidden');
    expect(screen.queryByTestId('scanner-results-pane')).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-control-rail')).not.toBeInTheDocument();
    expect(screen.getByTestId('scanner-launch-bar')).not.toHaveClass('overflow-hidden', 'max-h-[calc(100vh-120px)]', 'xl:h-full', 'xl:max-h-[calc(100vh-120px)]', 'xl:sticky');
    expect(candidateScrollRegion).toHaveClass('max-h-[min(52vh,34rem)]', 'overflow-y-auto', 'overscroll-y-contain', 'ui-scroll-y-quiet');
    expect(candidateScrollRegion).not.toHaveClass('flex-1', 'order-1', 'overflow-x-auto');
    expect(screen.getByTestId('scanner-ranked-list')).toHaveClass('overflow-x-auto');
    expect(screen.getByTestId('scanner-ranked-list')).not.toHaveClass('overflow-hidden', 'overflow-y-auto', 'no-scrollbar');
    expect(screen.getByTestId('scanner-result-table')).toHaveClass('contents', 'md:block', 'md:min-w-[1220px]');
  });

  it('keeps the dense status strip and candidate table ahead of secondary diagnostics by default', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    const status = await screen.findByTestId('scanner-status-strip');
    const candidates = await screen.findByTestId('scanner-candidate-scroll-region');
    const table = await screen.findByTestId('scanner-result-table');
    expect(status).toHaveTextContent(/Top ranked row \(observation\)|排序首位（观察）/);
    expect(status).toHaveTextContent(/Candidate mix|候选分布/);
    expect(status).toHaveTextContent(/Signal state|信号状态/);
    expect(screen.queryByTestId('scanner-diagnostics-panel')).not.toBeInTheDocument();
    expectElementBefore(status, candidates);
    expectElementBefore(table, screen.getByTestId('scanner-diagnostics-disclosure'));
    expectElementBefore(table, screen.getByTestId('scanner-run-comparison-strip'));
    expectElementBefore(table, screen.getByTestId('scanner-strategy-experiment'));
    expectElementBefore(candidates, screen.getByTestId('scanner-secondary-sections'));

    const diagnostics = screen.getByTestId('scanner-diagnostics-disclosure');
    expect(within(diagnostics).getByRole('button', { name: /展开.*(?:查看扫描诊断|View scanner diagnostics)|Expand.*(?:查看扫描诊断|View scanner diagnostics)/i })).toHaveAttribute('aria-expanded', 'false');
    expect(within(screen.getByTestId('scanner-run-comparison-strip')).getByRole('button', { name: /^(?:展开|Expand).*?(?:比较记录|Comparison records|Compare records)$/i })).toHaveAttribute('aria-expanded', 'false');
    expect(within(screen.getByTestId('scanner-strategy-experiment')).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i })).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(within(diagnostics).getByRole('button', { name: /展开.*(?:查看扫描诊断|View scanner diagnostics)|Expand.*(?:查看扫描诊断|View scanner diagnostics)/i }));
    expect(await screen.findByTestId('scanner-diagnostics-panel')).toBeInTheDocument();
  });

  it('renders the controlled RankingBoard zones with compact filters, bounded detail, and a secondary deck', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    const headerStrip = await screen.findByTestId('scanner-header-strip');
    const primaryWorkRegion = await screen.findByTestId('scanner-primary-work-region');
    const compactFilterBar = screen.getByTestId('scanner-compact-filter-bar');
    const secondaryDeck = screen.getByTestId('scanner-secondary-deck');
    const contextRail = screen.getByTestId('scanner-context-rail');
    const summaryRail = screen.getByTestId('scanner-summary-rail');

    expect(headerStrip).toContainElement(screen.getByTestId('scanner-status-strip'));
    expectElementBefore(headerStrip, screen.getByTestId('scanner-command-bar'));
    expect(screen.getByTestId('scanner-command-panel')).toContainElement(screen.getByTestId('scanner-command-bar'));
    expect(screen.getByTestId('scanner-results-panel')).toContainElement(screen.getByTestId('scanner-ranked-list'));
    expect(compactFilterBar).toBeInTheDocument();
    expect(primaryWorkRegion).toContainElement(screen.getByTestId('scanner-ranked-list'));
    expect(primaryWorkRegion).toContainElement(screen.getByTestId('scanner-result-table'));
    expect(primaryWorkRegion).toContainElement(screen.getByTestId('scanner-candidate-scroll-region'));
    expect(screen.getByTestId('scanner-candidate-scroll-region')).toContainElement(screen.getByTestId('scanner-candidate-row-WULF'));
    expect(contextRail).toContainElement(screen.getByTestId('scanner-inline-detail-panel'));
    expect(contextRail).toContainElement(screen.getByTestId('scanner-candidate-inspector'));
    expect(summaryRail).toHaveTextContent(/工作区摘要|Workspace summary/i);
    expect(summaryRail).toHaveTextContent(/候选|Candidates/i);
    expect(summaryRail).toHaveTextContent(/淘汰|Rejected/i);
    expect(summaryRail).toHaveTextContent(/数据受限|Limited/i);
    expect(summaryRail).toHaveTextContent(/范围|Scope/i);
    expect(summaryRail).not.toHaveTextContent(/provider|reasonCode|schema|debug|raw|cache/i);
    expect(secondaryDeck).toContainElement(screen.getByTestId('scanner-diagnostics-disclosure'));
    expect(secondaryDeck).toContainElement(screen.getByTestId('scanner-run-comparison-strip'));
    expect(secondaryDeck).toContainElement(screen.getByTestId('scanner-strategy-experiment'));
    expect(screen.queryByTestId('scanner-bento-grid')).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-card-wall')).not.toBeInTheDocument();
  });

  it('keeps the secondary deck collapsed behind product labels without native details copy', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    const secondaryDeck = await screen.findByTestId('scanner-secondary-deck');

    expect(within(secondaryDeck).getByText(/查看扫描诊断|View scanner diagnostics/i)).toBeInTheDocument();
    expect(within(secondaryDeck).getByText(/运行状态|Run status/i)).toBeInTheDocument();
    expect(within(secondaryDeck).getByText(/比较记录|Compare records/i)).toBeInTheDocument();
    expect(within(secondaryDeck).getByText(/回测准备|Backtest setup/i)).toBeInTheDocument();
    expect(within(secondaryDeck).queryByText(/^Details$/i)).not.toBeInTheDocument();
    expect(within(secondaryDeck).queryByText(/Data status|Previous run|Backtest lab/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-diagnostics-panel')).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-result-history-summary')).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-strategy-preview')).not.toBeInTheDocument();
  });

  it('keeps first-fold scanner chrome compact and hides low-value counters from the primary flow', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    const status = await screen.findByTestId('scanner-status-strip');
    const command = screen.getByTestId('scanner-command-bar');
    const actions = screen.getByTestId('scanner-primary-actions');
    const table = await screen.findByTestId('scanner-result-table');

    expect(command).not.toHaveTextContent(/个评估|evaluated/i);
    expect(command).not.toHaveTextContent(/generated|attempted|failed candidate|AI-generated/i);
    expect(actions).not.toHaveClass('flex-col');
    expect(actions).toHaveClass('flex-row');
    expectElementBefore(actions, table);
    expect(status).not.toHaveTextContent(/provider_down|provider_error|unknown|parquet_history/i);
    expect(screen.getByTestId('scanner-candidate-scroll-region')).not.toHaveTextContent(/provider_down|provider_error|parquet_history|Evidence summary|证据摘要|fallback|proxy|stale|source-confidence|sourceConfidence/i);
  });

  it('does not expose raw diagnostic vocabulary in default consumer scanner surfaces', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    await screen.findByTestId('scanner-result-row-WULF');
    const forbiddenDiagnosticText = /fallback|proxy|stale|source-confidence|sourceConfidence|provider|reason code|reasonCode|reasonFamilies|backend field|raw diagnostics|JSON/i;
    const defaultSurfaces = [
      screen.getByTestId('scanner-status-strip'),
      screen.getByTestId('scanner-conclusion-band'),
      screen.getByTestId('scanner-primary-actions'),
      screen.getByTestId('scanner-candidate-scroll-region'),
      screen.getByTestId('scanner-inline-detail-panel'),
      screen.getByTestId('scanner-summary-rail'),
    ];

    defaultSurfaces.forEach((surface) => {
      expect(surface).not.toHaveTextContent(forbiddenDiagnosticText);
    });
    expect(screen.getByTestId('scanner-consumer-first-viewport')).not.toHaveTextContent(forbiddenDiagnosticText);
    expect(screen.getByTestId('scanner-conclusion-band')).toHaveTextContent('部分结果使用最近一次可用数据。');
    expect(screen.queryByTestId('scanner-diagnostics-panel')).not.toBeInTheDocument();
    expect(screen.getByTestId('scanner-diagnostics-disclosure')).toHaveTextContent('查看扫描诊断');
    expect(within(screen.getByTestId('scanner-diagnostics-disclosure')).getByRole('button', { name: /查看扫描诊断/ })).toHaveAttribute('aria-expanded', 'false');
    expect(document.body).not.toHaveTextContent(/providerDiagnostics|fallback_source|reasonCodes|sourceConfidence|fallback_snapshot|raw detail/i);
  });

  it('renders selected detail only after the ranked table and before secondary disclosures', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    const table = await screen.findByTestId('scanner-result-table');
    expect(screen.getByTestId('scanner-result-detail-WULF')).toBeInTheDocument();

    fireEvent.click(getActionButton(screen.getByTestId('scanner-result-row-WULF'), /详情|Detail/i));
    const detail = await screen.findByTestId('scanner-result-detail-WULF');

    expectElementBefore(table, detail);
    expectElementBefore(detail, screen.getByTestId('scanner-secondary-sections'));
  });

  it('keeps default row and detail rail data quality copy product-safe', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    const row = await screen.findByTestId('scanner-result-row-WULF');
    expect(within(row).getAllByText('60/100').length).toBeGreaterThan(0);
    expect(row).not.toHaveTextContent(/provider_timeout|fallback|proxy|stale|source-confidence|sourceConfidence|provider|reasonCode|reasonFamilies/i);
    expect(row).toHaveTextContent(/部分结果使用最近一次可用数据|Some results use the latest available data/);
    expect(row).not.toHaveTextContent(/已验证|Verified|Signal fresh|fully trusted|authority allowed/i);

    fireEvent.click(getActionButton(row, /详情|Detail/i));
    const detail = await screen.findByTestId('scanner-result-detail-WULF');
    expect(within(detail).queryByText('仅供观察')).not.toBeInTheDocument();
    expect(detail).not.toHaveTextContent(/provider_timeout|fallback|proxy|stale|source-confidence|sourceConfidence|provider|reasonCode|reasonFamilies/i);
    fireEvent.click(within(detail).getByRole('button', { name: /候选说明|Candidate notes/i }));
    expect(await within(detail).findByText(/关键指标|Key metrics/)).toBeInTheDocument();
    const secondary = await within(detail).findByTestId('scanner-result-detail-secondary-WULF');
    fireEvent.click(within(secondary).getByRole('button', { name: /展开.*次要说明|Expand.*Secondary notes|展开/i }));
    expect(within(detail).getByText('仅供观察')).toBeInTheDocument();
    expect(detail).not.toHaveTextContent(/fully trusted|authority allowed|sourceAuthorityAllowed|scoreContributionAllowed/i);
    expect(within(detail).queryByText(/provider_timeout/i)).not.toBeInTheDocument();
  });

  it('surfaces investor signal in candidate notes using consumer-safe labels only', async () => {
    const investorSignalCandidate = makeCandidate({
      symbol: 'WULF',
      name: 'TeraWulf',
      companyName: 'TeraWulf',
      rank: 1,
      score: 60,
      diagnostics: makeTrustDiagnostics(),
      consumerDiagnostics: {
        investorSignal: {
          contractVersion: 'investor_signal_contract_v1',
          diagnosticOnly: true,
          observationOnly: true,
          authorityGrant: false,
          decisionGrade: false,
          sourceAuthorityAllowed: false,
          scoreContributionAllowed: false,
          capitalFlowRegime: 'inflow',
          capitalFlowLabel: '资金净流入观察',
          confidence: 'medium',
          confidenceText: '中',
          freshness: 'partial',
          reasonCodes: ['source_authority_missing', 'score_rights_missing'],
          contradictionCodes: ['btc_not_confirming_growth_absorption'],
          explanation: 'Growth is absorbing more attention while BTC is not confirming the move.',
          likelyDestination: 'growth_ai_software_semis',
          sourceAssetPressure: [
            { asset: 'growth_ai_software_semis', pressure: 'absorbing', freshness: 'delayed', isPartial: true },
          ],
        },
      },
    });

    getRun.mockResolvedValue(makeCryptoDiagnosticsRun({
      shortlist: [investorSignalCandidate],
      selected: [investorSignalCandidate],
    }));
    renderUserScannerPage();

    const row = await screen.findByTestId('scanner-result-row-WULF');
    expect(row).toHaveTextContent('60/100');
    const detail = await screen.findByTestId('scanner-result-detail-WULF');
    expect(within(detail).queryByTestId('scanner-investor-signal-WULF')).not.toBeInTheDocument();
    fireEvent.click(within(detail).getByRole('button', { name: /候选说明|Candidate notes/i }));
    const secondary = await within(detail).findByTestId('scanner-result-detail-secondary-WULF');
    fireEvent.click(within(secondary).getByRole('button', { name: /展开.*次要说明|Expand.*Secondary notes|展开/i }));

    const signal = await within(detail).findByTestId('scanner-investor-signal-WULF');
    expect(within(detail).getByText(/投资者信号|Investor signal/i)).toBeInTheDocument();
    expect(signal).toHaveTextContent('资金净流入观察');
    expect(signal).toHaveTextContent(/置信度|Confidence/i);
    expect(signal).toHaveTextContent('中');
    expect(signal).toHaveTextContent(/时效|Freshness/i);
    expect(signal).toHaveTextContent(/部分|Partial/i);
    expect(signal).toHaveTextContent(/来源确认待补齐|Source confirmation pending/i);
    expect(signal).toHaveTextContent(/暂不进入评分|Score stays observational/i);
    expect(signal).toHaveTextContent(/BTC 未确认当前吸纳|BTC not confirming current absorption/i);
    expect(signal).toHaveTextContent('Growth is absorbing more attention while BTC is not confirming the move.');
    expect(signal).not.toHaveTextContent('60/100');
    expect(signal).not.toHaveTextContent(/已验证|Signal fresh/i);
    expect(signal).not.toHaveTextContent(
      /authorityGrant|decisionGrade|sourceAuthorityAllowed|scoreContributionAllowed|contractVersion|sourceAssetPressure|likelyDestination|raw/i,
    );
    expect(signal).not.toHaveTextContent(/source_authority_missing|score_rights_missing|btc_not_confirming_growth_absorption/i);
  });

  it('reveals rejection reasons from the diagnostics disclosure', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    expect(screen.queryByTestId('scanner-rejection-aggregate')).not.toBeInTheDocument();

    const diagnostics = await screen.findByTestId('scanner-diagnostics-disclosure');
    fireEvent.click(within(diagnostics).getByRole('button', { name: /展开.*(?:查看扫描诊断|View scanner diagnostics)|Expand.*(?:查看扫描诊断|View scanner diagnostics)/i }));
    const summary = await screen.findByTestId('scanner-diagnostics-summary');
    fireEvent.click(within(summary).getByRole('button', { name: /淘汰分布|Rejection mix/i }));
    expect(await screen.findByTestId('scanner-rejection-aggregate')).toBeInTheDocument();
  });

  it('keeps synthetic scanner diagnostics collapsed and sanitized for member view', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun({
      diagnostics: {
        coverageSummary: {
          inputUniverseSize: 300,
          eligibleAfterUniverseFetch: 280,
          eligibleAfterLiquidityFilter: 240,
          eligibleAfterDataAvailabilityFilter: 210,
          rankedCandidateCount: 40,
          shortlistedCount: 3,
          excludedTotal: 90,
          excludedByReason: [],
          likelyBottleneck: 'data_availability',
          likelyBottleneckLabel: 'universe / historical ohlcv / quote snapshot',
        },
        providerDiagnostics: {
          configuredPrimaryProvider: 'synthetic_provider_url=https://provider.example.invalid/options?token=secret',
          quoteSourceUsed: 'synthetic_cache_key=scanner:cn:2026-06-12',
          snapshotSourceUsed: 'synthetic_request_id=req-scanner-raw-123',
          historySourceUsed: 'synthetic_provider_payload_label=raw_payload',
          providersUsed: ['synthetic_provider_url'],
          fallbackOccurred: true,
          fallbackCount: 1,
          providerFailureCount: 1,
          missingDataSymbolCount: 1,
          providerWarnings: [
            'synthetic_debug_reason=Traceback stack trace',
            'synthetic_score_trace=score_debug_vector',
            'synthetic_diagnostic_window=operator-window',
          ],
        },
        aiInterpretation: {
          summary: 'universe / historical ohlcv / quote snapshot',
          synthetic_provider_url: 'https://provider.example.invalid/raw?token=secret',
          synthetic_cache_key: 'scanner:cn:cache-key',
          synthetic_request_id: 'req-scanner-raw-123',
          synthetic_debug_reason: 'Traceback synthetic stack',
          synthetic_score_trace: 'score_debug_vector',
          synthetic_diagnostic_window: 'operator-window',
          synthetic_provider_payload_label: 'raw_provider_payload',
        },
      },
    }));

    renderUserScannerPage();

    const forbiddenSyntheticMarkers = /synthetic_provider_url|synthetic_cache_key|synthetic_request_id|synthetic_debug_reason|synthetic_score_trace|synthetic_diagnostic_window|synthetic_provider_payload_label|provider\.example|req-scanner-raw-123|raw_provider_payload|Traceback|score_debug_vector|operator-window/i;
    expect(await screen.findByTestId('scanner-diagnostics-disclosure')).toBeInTheDocument();
    expect(screen.queryByTestId('scanner-diagnostics-panel')).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(forbiddenSyntheticMarkers);

    const diagnostics = screen.getByTestId('scanner-diagnostics-disclosure');
    fireEvent.click(within(diagnostics).getByRole('button', { name: /展开.*(?:查看扫描诊断|View scanner diagnostics)|Expand.*(?:查看扫描诊断|View scanner diagnostics)/i }));
    const panel = await screen.findByTestId('scanner-diagnostics-panel');
    const panelText = panel.textContent || '';

    expect(panel).toHaveTextContent(/诊断详情已保留|Diagnostic details retained/);
    expect(panel).toHaveTextContent('数据缺口：标的池行情 / 历史日线 / 实时报价');
    expect(panelText).not.toMatch(/universe\s*\/\s*historical\s+ohlcv\s*\/\s*quote\s+snapshot/i);
    expect(panel).not.toHaveTextContent(forbiddenSyntheticMarkers);
    expect(findConsumerRawLeakage(panelText, {
      extraForbiddenPatterns: [
        /synthetic_(?:provider_url|cache_key|request_id|debug_reason|score_trace|diagnostic_window|provider_payload_label)/i,
        /provider\.example|req-scanner-raw-123|Traceback|score_debug_vector|operator-window/i,
      ],
    })).toEqual([]);
  });

  it('keeps expanded scanner diagnostics free of raw provider and internal keys', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun({
      diagnostics: {
        providerDiagnostics: {
          configuredPrimaryProvider: 'raw_provider_debug',
          quoteSourceUsed: 'fallback_static',
          providerWarnings: ['sourceAuthorityAllowed raw_provider_trace'],
        },
      },
      candidates: [
        {
          symbol: 'MARA',
          name: 'MARA Holdings',
          rank: 2,
          status: 'rejected',
          score: 55,
          provider: 'raw_provider_debug',
          reason: 'below liquidity threshold',
          failedRules: ['source_authority_router_rejected', 'below_liquidity_threshold'],
          missingFields: ['raw_history_field'],
          metrics: { raw_score_delta: 12 },
          metadata: {
            sourceAuthorityAllowed: true,
            scoreContributionAllowed: true,
            debugRef: 'scanner:mara:debug',
          },
        },
        {
          symbol: 'CIFR',
          name: 'Cipher Mining',
          rank: 10,
          status: 'data_failed',
          score: null,
          provider: 'raw_provider_debug',
          reason: 'provider_timeout',
          failedRules: ['not_enough_history'],
          missingFields: ['history'],
          metrics: {},
        },
      ],
    }));
    renderUserScannerPage();

    const diagnostics = await screen.findByTestId('scanner-diagnostics-disclosure');
    fireEvent.click(within(diagnostics).getByRole('button', { name: /展开.*(?:查看扫描诊断|View scanner diagnostics)|Expand.*(?:查看扫描诊断|View scanner diagnostics)/i }));
    const panel = await screen.findByTestId('scanner-diagnostics-panel');
    const summary = await screen.findByTestId('scanner-diagnostics-summary');
    fireEvent.click(within(summary).getByRole('button', { name: /淘汰分布|Rejection mix/i }));
    const aggregate = await screen.findByTestId('scanner-rejection-aggregate');

    expect(aggregate).toHaveTextContent(/流动性不足|Liquidity weak|历史数据不足|Historical data insufficient|数据不足/);
    expect(panel).not.toHaveTextContent(
      /sourceAuthorityAllowed|scoreContributionAllowed|source_authority_router_rejected|raw_provider_debug|fallback_static|provider_timeout|raw_history_field|raw_score_delta|debugRef|scanner:mara:debug/i,
    );
    expect(aggregate).not.toHaveTextContent(
      /sourceAuthorityAllowed|scoreContributionAllowed|source_authority_router_rejected|raw_provider_debug|fallback_static|provider_timeout|raw_history_field|raw_score_delta|debugRef|scanner:mara:debug/i,
    );
  });

  it('keeps Scanner on the table-first path without card/table toggle chrome', async () => {
    renderUserScannerPage();

    expect(await screen.findByTestId('scanner-result-table')).toBeInTheDocument();
    expect(screen.getByTestId('scanner-result-row-NVDA')).toBeInTheDocument();
    expect(screen.getByTestId('scanner-ranked-list')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /卡片视图|Card view/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /表格视图|Table view/i })).not.toBeInTheDocument();
  });

  it('renders table columns from existing candidate fields', async () => {
    renderUserScannerPage();

    const table = await screen.findByTestId('scanner-result-table');
    expect(within(table).getAllByText('排名').length).toBeGreaterThan(0);
    expect(within(table).getAllByText('代码 / 名称').length).toBeGreaterThan(0);
    expect(within(table).getAllByText('评分').length).toBeGreaterThan(0);
    expect(within(table).getAllByText('状态').length).toBeGreaterThan(0);
    expect(within(table).getAllByText('关键原因').length).toBeGreaterThan(0);
    expect(within(table).getAllByText('数据质量').length).toBeGreaterThan(0);
    expect(within(table).getAllByText('观察 / 风险').length).toBeGreaterThan(0);
    expect(within(table).queryByText('数据/来源')).not.toBeInTheDocument();
    expect(within(table).getAllByText('操作').length).toBeGreaterThan(0);
    expect(within(table).getAllByText('Backend Broadcom Label').length).toBeGreaterThan(0);
    expect(within(table).queryByText('1420')).not.toBeInTheDocument();
  });

  it('keeps row actions close to table rows without card chrome', async () => {
    renderUserScannerPage();

    const row = await screen.findByTestId('scanner-result-row-NVDA');
    expect(getActionButton(row, /详情|Detail/i)).toBeInTheDocument();
    expect(within(row).queryByRole('button', { name: /打开个股研究|Open stock research/i })).not.toBeInTheDocument();
    fireEvent.click(getActionButton(row, /更多|More/i));
    const rankedRow = getRankedRow('NVDA');
    expect(within(rankedRow).getByRole('button', { name: /打开个股研究|Open stock research/i })).toBeInTheDocument();
    expect(within(rankedRow).getByRole('button', { name: /追踪|Track/i })).toBeInTheDocument();
    expect(screen.getByTestId('scanner-ranked-list')).toBeInTheDocument();
  });

  it('copies a single candidate symbol to the clipboard', async () => {
    renderUserScannerPage();

    const card = await screen.findByTestId('scanner-result-row-NVDA');
    fireEvent.click(getActionButton(card, /详情|Detail/i));
    const detail = await screen.findByTestId('scanner-result-detail-NVDA');
    fireEvent.click(within(detail).getByRole('button', { name: /复制代码|Copy symbol/i }));

    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalledWith('NVDA');
    });
  });

  it('copies all current result symbols from run-level actions', async () => {
    renderUserScannerPage();

    const more = await openMoreActions();
    fireEvent.click(within(more).getByRole('button', { name: /复制全部代码|Copy all symbols/i }));

    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalledWith('NVDA, AVGO, AMD');
    });
  });

  it('exports csv with expected scanner result headers', async () => {
    renderUserScannerPage();

    const more = await openMoreActions();
    fireEvent.click(within(more).getByRole('button', { name: /导出 CSV|Export CSV/i }));

    await waitFor(() => {
      expect(createObjectUrlMock).toHaveBeenCalledTimes(1);
      expect(anchorClickMock).toHaveBeenCalledTimes(1);
    });

    const exportBlob = createObjectUrlMock.mock.calls[0]?.[0] as Blob;
    const exportText = await exportBlob.text();
    expect(exportText).toContain('rank,symbol,name,scannerScore,observationZone,referenceRange,riskBoundary,reason,risk,universeType,theme,generatedAt,runId');
    expect(exportText).not.toContain('entryRange,target,stop');
    expect(exportText).toContain('1,NVDA');
  });

  it('candidate research action opens the stock research route without mutating analysis state', async () => {
    renderUserScannerPage();

    const card = await screen.findByTestId('scanner-result-row-NVDA');
    fireEvent.click(getActionButton(card, /详情|Detail/i));
    const detail = await screen.findByTestId('scanner-result-detail-NVDA');
    fireEvent.click(within(detail).getByRole('button', { name: /打开个股研究|Open stock research/i }));

    expect(await screen.findByText('Stock Research Landing')).toBeInTheDocument();
    expect(analyzeAsync).not.toHaveBeenCalled();
  });

  it('enables backtest action for candidates with symbol', async () => {
    renderUserScannerPage();

    const card = await screen.findByTestId('scanner-result-row-NVDA');
    fireEvent.click(getActionButton(card, /详情|Detail/i));
    expect(within(await screen.findByTestId('scanner-result-detail-NVDA')).getByRole('button', { name: /回测|Backtest/i })).toBeEnabled();
  });

  it('shows backtest action as disabled when the candidate symbol is missing', async () => {
    getRun.mockResolvedValueOnce(makeRunDetail({
      shortlist: [
        makeCandidate({ symbol: '', name: 'Unknown candidate', companyName: 'Unknown candidate' }),
      ],
    }));
    renderUserScannerPage();

    const [card] = await screen.findAllByTestId(/^scanner-result-row-/);
    fireEvent.click(getActionButton(card, /详情|Detail/i));
    const backtestButton = within(await screen.findByTestId('scanner-result-detail-no-symbol-1')).getByRole('button', { name: /回测|Backtest/i });
    expect(backtestButton).toBeDisabled();
    expect(backtestButton).toHaveAttribute('title', expect.stringMatching(/requires a candidate symbol|候选标的代码/i));
  });

  it('renders scanner watchlist tracking actions and tracked state', async () => {
    listWatchlistItems.mockResolvedValueOnce({
      items: [makeWatchlistItem()],
    });
    renderUserScannerPage();

    const card = await screen.findByTestId('scanner-result-row-NVDA');
    fireEvent.click(getActionButton(card, /更多|More/i));
    const rankedRow = getRankedRow('NVDA');
    expect(within(rankedRow).getByRole('button', { name: /Tracked|已追踪/ })).toBeDisabled();
    expect(within(rankedRow).getByRole('button', { name: /回测|Backtest/i })).toBeInTheDocument();
  });

  it('adds a scanner candidate to the watchlist and marks it tracked', async () => {
    addWatchlistItem.mockResolvedValueOnce(makeWatchlistItem({
      id: 202,
      symbol: 'AVGO',
      market: 'cn',
      name: 'Broadcom',
      scannerRunId: 11,
      scannerRank: 2,
      scannerScore: 88,
    }));

    renderUserScannerPage();

    const card = await openRowMore('scanner-result-row-AVGO');
    fireEvent.click(within(card).getByRole('button', { name: /Track|追踪/i }));

    await waitFor(() => {
      expect(addWatchlistItem).toHaveBeenCalledWith(expect.objectContaining({
        symbol: 'AVGO',
        market: 'cn',
        name: 'Backend Broadcom Label',
        source: 'scanner',
        scannerRunId: 11,
        scannerRank: 2,
        scannerScore: 88,
        universeType: 'default',
      }));
    });

    expect(await within(card).findByRole('button', { name: /Tracked|已追踪/ })).toBeDisabled();
    expect(screen.getByText(/Saved to your watchlist|已加入观察名单/)).toBeInTheDocument();
  });

  it('shows a friendly sign-in message when watchlist writes are blocked', async () => {
    addWatchlistItem.mockRejectedValueOnce(
      createApiError(
        createParsedApiError({
          title: '登录已失效',
          message: '请登录后再保存候选到你的观察名单。',
          rawMessage: 'Unauthorized',
          status: 401,
          code: 'unauthorized',
          category: 'auth_required',
          isAuthError: true,
        }),
      ),
    );

    renderUserScannerPage();

    const card = await openRowMore('scanner-result-row-NVDA');
    fireEvent.click(within(card).getByRole('button', { name: /Track|追踪/i }));

    expect(await screen.findByText(/Sign in to save candidates to your watchlist|请登录后再保存候选到你的观察名单/)).toBeInTheDocument();
  });

  it('sorts frontend-only by scanner score and symbol', async () => {
    renderUserScannerPage();

    await screen.findByTestId('scanner-result-row-NVDA');
    expect(orderedSymbolsFromRows()).toEqual(['NVDA', 'AVGO', 'AMD']);
    const getRunsCallsBeforeSort = getRuns.mock.calls.length;
    const getRunCallsBeforeSort = getRun.mock.calls.length;
    const sortbar = screen.getByTestId('scanner-ranked-sortbar');

    fireEvent.click(within(sortbar).getByRole('button', { name: /代码|symbol/i }));
    await waitFor(() => {
      expect(orderedSymbolsFromRows()).toEqual(['AMD', 'AVGO', 'NVDA']);
    });

    fireEvent.click(within(sortbar).getByRole('button', { name: /扫描评分|scanner score/i }));
    await waitFor(() => {
      expect(orderedSymbolsFromRows()).toEqual(['NVDA', 'AVGO', 'AMD']);
    });

    expect(getRuns).toHaveBeenCalledTimes(getRunsCallsBeforeSort);
    expect(getRun).toHaveBeenCalledTimes(getRunCallsBeforeSort);
  });

  it('expands result detail with metrics, signals, risks, notes, outcome, and provider data', async () => {
    renderUserScannerPage();

    const nvdaCard = await screen.findByTestId('scanner-result-row-NVDA');
    fireEvent.click(getActionButton(nvdaCard, /详情|Detail/i));

    const detail = await screen.findByTestId('scanner-result-detail-NVDA');
    expect(within(detail).getByText(/当前信号|Why now/)).toBeInTheDocument();
    expect(within(detail).getByRole('button', { name: /打开个股研究|Open stock research/i })).toBeInTheDocument();
    expect(within(detail).getByRole('button', { name: /复制代码|Copy symbol/i })).toBeInTheDocument();
    expect(within(detail).getByRole('button', { name: /导出|Export/i })).toBeInTheDocument();
    expect(within(detail).getByRole('button', { name: /回测|Backtest/i })).toBeEnabled();
    expect(within(detail).getByText('Backend risk: gap fade below support.')).toBeInTheDocument();
    expect(within(detail).queryByText(/Backend scoring note/)).not.toBeInTheDocument();
    fireEvent.click(within(detail).getByRole('button', { name: /候选说明|Candidate notes/i }));
    expect(await within(detail).findByText(/关键指标|Key metrics/)).toBeInTheDocument();
    expect(await within(detail).findByText('Turnover')).toBeInTheDocument();
    const nvdaSecondary = await within(detail).findByTestId('scanner-result-detail-secondary-NVDA');
    fireEvent.click(within(nvdaSecondary).getByRole('button', { name: /展开.*次要说明|Expand.*Secondary notes|展开/i }));
    expect(within(detail).getByText('Momentum expansion')).toBeInTheDocument();
  });

  it('loads and displays historical run detail when a history item is clicked', async () => {
    const historicalRun = makeRunDetail({
      id: 22,
      completedAt: '2026-04-20T08:31:00',
      shortlist: [
        makeCandidate({
          symbol: 'HIST',
          name: 'Historical result',
          companyName: 'Historical Backend Label',
          rank: 1,
          score: 91,
          reasonSummary: 'Historical replay backend reason.',
        }),
      ],
    });
    getRuns.mockResolvedValue(makeHistoryResponse([
      makeHistoryItem({ id: 11, headline: '当前扫描：NVDA / AVGO' }),
      makeHistoryItem({ id: 22, headline: '历史扫描：HIST', topSymbols: ['HIST'] }),
    ]));
    getRun.mockImplementation((runId: number) => Promise.resolve(runId === 22 ? historicalRun : makeRunDetail()));

    renderUserScannerPage();

    fireEvent.click(await screen.findByTestId('scanner-history-trigger'));
    const historyDialog = await screen.findByRole('dialog');
    fireEvent.click((await within(historyDialog).findAllByText(/HIST/))[0] as HTMLElement);

    expect((await screen.findAllByText('Historical Backend Label')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Historical replay backend reason.').length).toBeGreaterThan(0);
    expect(getRun).toHaveBeenCalledWith(22);
  });

  it('does not let hardcoded symbol context override backend-provided values', async () => {
    renderUserScannerPage();

    expect(within(await screen.findByTestId('scanner-result-row-AVGO')).getAllByText('Backend Broadcom Label').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Backend AVGO reason wins.').length).toBeGreaterThan(0);
    expect(screen.queryByText('Broadcom Inc.')).not.toBeInTheDocument();
    expect(screen.queryByText('AI 算力基建')).not.toBeInTheDocument();
  });

  it('does not synthesize metrics or signals when backend omits candidate evidence fields', async () => {
    const sparseCandidate = makeCandidate({
      symbol: 'SPARSE',
      name: 'Sparse Backend',
      companyName: 'Sparse Backend',
      rank: 1,
      score: 42,
      reasonSummary: null,
      reasons: [],
      keyMetrics: [],
      featureSignals: [],
      riskNotes: [],
      watchContext: [],
    });
    const baseRun = makeRunDetail();
    getRun.mockResolvedValue(makeRunDetail({
      headline: 'Backend sparse scan',
      shortlist: [sparseCandidate],
      selected: [sparseCandidate],
      candidates: [],
      scoringNotes: [],
      summary: {
        ...baseRun.summary,
        selectedCount: 1,
        rejectedCount: 0,
        dataFailedCount: 0,
        errorCount: 0,
      },
    }));

    renderUserScannerPage();

    const row = await screen.findByTestId('scanner-result-row-SPARSE');
    fireEvent.click(getActionButton(row, /详情|Detail/i));
    const detail = await screen.findByTestId('scanner-result-detail-SPARSE');
    fireEvent.click(within(detail).getByRole('button', { name: /候选说明|Candidate notes/i }));

    expect(await within(detail).findByText(/未提供关键指标|No key metrics provided/i)).toBeInTheDocument();
    expect(within(detail).queryByText(/特征信号|Feature signals/i)).not.toBeInTheDocument();
    expect(detail).not.toHaveTextContent(/Entry range|Target price|Stop loss|Momentum expansion|Backend AI infrastructure|Backend GPU signal|Backend networking signal|AI 算力基建|Broadcom Inc\.|Tesla|Meta|Apple/i);
  });

  it('keeps empty states clear when history and results are empty', async () => {
    getRuns.mockResolvedValue(makeHistoryResponse([]));

    const { container } = renderUserScannerPage({ viewportWidth: 1800 });

    expect(await screen.findByTestId('scanner-status-strip')).toHaveTextContent(/等待|Waiting/);
    expect(await screen.findByTestId('scanner-conclusion-band')).toHaveTextContent('首次使用：先运行一次扫描');
    expect(screen.getByTestId('scanner-conclusion-band')).toHaveTextContent('扫描器会先按当前范围筛出可继续观察的候选。');
    expect(screen.getByTestId('scanner-conclusion-band')).toHaveTextContent('A股 · 默认市场池 · 300 只 · 60 条详评');
    expect(await screen.findByTestId('scanner-workbench-empty-state')).toHaveTextContent('尚未运行扫描');
    expect(screen.getByTestId('scanner-workbench-empty-state')).toHaveTextContent('扫描器会先按当前范围整理候选与观察线索。');
    expect(screen.getByTestId('scanner-workbench-empty-state')).toHaveTextContent('A股 · 默认市场池 · 300 只 · 60 条详评');
    expect(screen.getByTestId('scanner-workbench-empty-state')).toHaveTextContent('先直接启动一次扫描');
    expect(screen.getByTestId('scanner-workbench-empty-state')).toHaveTextContent(/打开历史/);
    expect(screen.getAllByRole('button', { name: '启动扫描' })).toHaveLength(1);
    expect(screen.queryByTestId('scanner-candidate-scroll-region')).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-context-rail')).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-detail-rail')).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-inline-detail-panel')).not.toBeInTheDocument();
    expect(screen.getByTestId('scanner-workbench-detail-layout')).toHaveClass('grid-cols-1');
    expect(textContentWithoutObservationBoundary(container)).not.toMatch(/买入|卖出|加仓|减仓|buy|sell|recommend(?:ation)?/i);

    fireEvent.click(screen.getByTestId('scanner-history-trigger'));

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getAllByText('尚未运行扫描').length).toBeGreaterThan(0);
  });

  it('renders scanner-specific pre-run guidance before candidates are available', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun({
      shortlist: [],
      selected: [],
      summary: {
        universeCount: 11,
        submittedCount: 11,
        evaluatedCount: 4,
        selectedCount: 0,
        rejectedCount: 3,
        dataFailedCount: 1,
        skippedCount: 0,
        errorCount: 0,
        limitedByResultCap: false,
      },
      candidates: [
        {
          symbol: 'MARA',
          name: 'MARA Holdings',
          rank: 1,
          status: 'rejected',
          score: 55,
          provider: 'alpaca',
          reason: 'below liquidity threshold',
          failedRules: ['below_liquidity_threshold'],
          missingFields: [],
          metrics: {},
        },
        {
          symbol: 'CIFR',
          name: 'Cipher Mining',
          rank: 2,
          status: 'data_failed',
          score: null,
          provider: null,
          reason: 'missing price history',
          failedRules: ['not_enough_history'],
          missingFields: ['history'],
          metrics: {},
        },
      ],
    }));

    renderUserScannerPage();

    await waitFor(() => {
      expect(screen.getByTestId('scanner-workbench-empty-state')).toHaveTextContent('本次未形成入选候选');
    });
    expect(screen.getByRole('heading', { level: 1, name: '发现 / 扫描器' })).toBeInTheDocument();
    expect(screen.getByTestId('scanner-consumer-first-viewport')).toBeInTheDocument();
    expect(screen.getByTestId('scanner-consumer-status-sentence')).toHaveTextContent('本次未形成入选候选');
    expect(screen.getByTestId('scanner-consumer-control-summary')).toHaveTextContent('市场');
    expect(screen.getByTestId('scanner-consumer-control-summary')).toHaveTextContent('策略');
    expect(screen.getByTestId('scanner-consumer-control-summary')).toHaveTextContent('标的池');
    expect(screen.getByTestId('scanner-data-trust-row')).toHaveTextContent('标的池');
    expect(screen.getByTestId('scanner-data-trust-row')).toHaveTextContent('历史数据');
    expect(screen.getByTestId('scanner-data-trust-row')).toHaveTextContent('报价新鲜度');
    expect(screen.getByTestId('scanner-data-trust-row')).toHaveTextContent('候选输出');
    expect(screen.getByTestId('scanner-consumer-next-action')).toHaveTextContent(/未形成官方入选候选|手动研究单个代码/);
    const emptyState = screen.getByTestId('scanner-workbench-empty-state');
    expect(screen.getByTestId('scanner-empty-history-fallback')).toBeInTheDocument();
    expect(emptyState).toHaveTextContent('未形成入选候选，可重试、查看数据受限行或切换市场/策略');
    expect(emptyState).not.toHaveTextContent('不代表市场没有机会');
    expect(emptyState).toHaveTextContent('可重试');
    expect(emptyState).not.toHaveTextContent(/买入|卖出|下单|交易|券商|broker|provider|cache/i);
    expect(screen.getByTestId('scanner-candidate-filters')).toBeInTheDocument();
    expect(screen.getByTestId('scanner-ranked-sortbar')).toBeInTheDocument();
    expect(screen.getByTestId('scanner-more-actions')).toBeInTheDocument();
    expect(screen.getByTestId('scanner-run-button')).toBeInTheDocument();
    expect(screen.getByTestId('scanner-history-trigger')).toBeInTheDocument();
  });

  it('renders limited-data guidance when all rows lack usable evidence', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun({
      status: 'failed',
      failureReason: 'not_enough_history',
      shortlist: [],
      selected: [],
      summary: {
        universeCount: 11,
        submittedCount: 11,
        evaluatedCount: 2,
        selectedCount: 0,
        rejectedCount: 0,
        dataFailedCount: 2,
        skippedCount: 0,
        errorCount: 0,
        limitedByResultCap: false,
      },
      candidates: [
        {
          symbol: 'CIFR',
          name: 'Cipher Mining',
          rank: 1,
          status: 'data_failed',
          score: null,
          provider: null,
          reason: 'missing price history',
          failedRules: ['not_enough_history'],
          missingFields: ['history'],
          metrics: {},
        },
        {
          symbol: 'HIVE',
          name: 'HIVE Digital',
          rank: 2,
          status: 'error',
          score: null,
          provider: 'alpaca',
          reason: null,
          failedRules: [],
          missingFields: ['quote'],
          metrics: {},
        },
      ],
    }));

    renderUserScannerPage();

    await waitFor(() => {
      expect(screen.getByTestId('scanner-workbench-empty-state')).toHaveTextContent('数据/历史覆盖不足');
    });
    const emptyState = screen.getByTestId('scanner-workbench-empty-state');
    expect(emptyState).toHaveTextContent('未形成入选候选，可重试、查看数据受限行或切换市场/策略');
    expect(emptyState).not.toHaveTextContent('不代表市场没有机会');
    expect(emptyState).toHaveTextContent('查看数据受限行');
    expect(emptyState).not.toHaveTextContent(/not_enough_history|provider|raw|reasonCode/i);
  });

  it('renders fetch-failure guidance without exposing raw scanner details', async () => {
    getRun.mockRejectedValueOnce(
      createApiError(
        createParsedApiError({
          title: '请求超时',
          message: '请求超时，请稍后重试。',
          rawMessage: 'provider_timeout raw scanner detail',
          status: 504,
          code: 'upstream_timeout',
          category: 'upstream_timeout',
          isTimeoutError: true,
        }),
      ),
    );

    renderUserScannerPage();

    expect(await screen.findByTestId('scanner-page-error-summary')).toHaveTextContent('超时');
    const emptyState = await screen.findByTestId('scanner-workbench-empty-state');
    expect(emptyState).toHaveTextContent('扫描读取失败');
    expect(emptyState).toHaveTextContent(/稍后重试或打开历史/);
    expect(emptyState).not.toHaveTextContent(/provider_timeout|raw scanner/i);
  });

  it('keeps existing run button behavior and market defaults', async () => {
    renderUserScannerPage(true);

    expect(await within(screen.getByTestId('scanner-launch-controls')).findByRole('button', { name: '300 只' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'switch-language-en' }));

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: '300 只' })).not.toBeInTheDocument();
    });
    expect(within(screen.getByTestId('scanner-launch-controls')).getByRole('button', { name: '300' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'US' }));
    fireEvent.click(screen.getByRole('button', { name: 'Run scanner' }));

    await waitFor(() => {
      expect(runScan).toHaveBeenCalledWith({
        market: 'us',
        profile: 'us_preopen_v1',
        shortlistSize: 5,
        universeLimit: 180,
        detailLimit: 40,
      });
    });
  });

  it('runs with a selected theme universe and keeps results in the compact header', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    runScan.mockResolvedValueOnce(themedRun);
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    fireEvent.click(await within(screen.getByTestId('scanner-market-toggle')).findByRole('button', { name: /美股|US/ }));
    fireEvent.click(within(screen.getByTestId('scanner-scope-selector')).getByRole('button', { name: /主题标的池|Theme scope/i }));
    await openAdvancedControls();
    const themeSelect = await screen.findByTestId('scanner-theme-select');
    expect(themeSelect).toHaveTextContent(/AI 半导体|AI semiconductors/);
    expect(themeSelect).toHaveClass('select-surface', 'absolute', 'inset-0', 'opacity-0');
    expect(themeSelect.closest('.select-field__control')).toHaveClass('ui-control-shell', 'relative', 'min-w-0', 'w-full');
    expect(themeSelect.closest('.select-field__control')?.querySelector('.select-field__overlay')).toHaveAttribute('aria-hidden', 'true');
    expect(themeSelect.closest('.select-field__control')?.querySelector('.select-field__value')).toHaveTextContent(/加密矿企|Crypto miners/);
    expect(themeSelect.closest('.select-field__control')?.querySelector('.select-field__icon')).toHaveClass('ml-2', 'shrink-0');
    fireEvent.change(screen.getByTestId('scanner-theme-select'), { target: { value: 'crypto_miners' } });
    fireEvent.click(screen.getByRole('button', { name: /启动扫描|运行扫描|Run scanner/i }));

    await waitFor(() => {
      expect(runScan).toHaveBeenCalledWith(expect.objectContaining({
        market: 'us',
        profile: 'us_preopen_v1',
        universeType: 'theme',
        themeId: 'crypto_miners',
      }));
    });
    expect(screen.queryByTestId('scanner-diagnostics-summary')).not.toBeInTheDocument();
    expect(screen.getByTestId('scanner-status-strip')).toHaveTextContent(/1 \/ 8 \/ 2/);
    expect(screen.getByTestId('scanner-command-bar')).not.toHaveTextContent(/本次扫描：|Scan:/);
    expect(screen.getByTestId('scanner-result-row-WULF')).toBeInTheDocument();
    expect(screen.queryByTestId('scanner-candidate-preview')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /候选池|Candidate pool/i }));
    expect(await screen.findByTestId('scanner-candidate-row-WULF')).toHaveTextContent(/官方|Official/);
    expect(screen.getByTestId('scanner-candidate-row-WULF')).toHaveTextContent(/入选|Selected/);
    expect(screen.getByTestId('scanner-candidate-row-WULF')).toHaveTextContent(/部分结果使用最近一次可用数据|Some results use the latest available data/);
    expect(screen.getByTestId('scanner-candidate-row-MARA')).toHaveTextContent(/流动性不足|Liquidity weak/);
    expect(screen.getByTestId('scanner-candidate-row-RIOT')).toHaveTextContent(/价格低于阈值|Price below threshold/);
    expect(screen.getByTestId('scanner-candidate-row-CIFR')).toHaveTextContent(/历史数据不足|Historical data insufficient|数据不足/);
  });

  it('keeps advanced scanner actions out of the default top toolbar and available in disclosure', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    const actions = await screen.findByTestId('scanner-primary-actions');
    expect(within(actions).getByRole('button', { name: /更多|More/i })).toBeInTheDocument();
    expect(within(actions).queryByRole('button', { name: /查看 WULF|View WULF/i })).not.toBeInTheDocument();
    expect(within(actions).queryByRole('button', { name: /分析 WULF|Analyze WULF/i })).not.toBeInTheDocument();
    expect(within(actions).queryByRole('button', { name: /回测 WULF|Backtest WULF/i })).not.toBeInTheDocument();
    expect(within(actions).queryByRole('button', { name: /加入观察|Save to watchlist/i })).not.toBeInTheDocument();
    expect(within(actions).queryByRole('button', { name: /导出 CSV|Export CSV/i })).not.toBeInTheDocument();
    expect(within(actions).queryByRole('button', { name: /复制全部代码|Copy all symbols/i })).not.toBeInTheDocument();
    expect(within(actions).queryByRole('button', { name: /加入前 5 名|Add top 5/i })).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-more-actions-panel')).not.toBeInTheDocument();

    const more = screen.getByTestId('scanner-more-actions');
    fireEvent.click(within(more).getByRole('button', { name: /更多|More/i }));
    expect(screen.getByTestId('scanner-more-actions-panel')).toBeInTheDocument();
    expect(within(more).getByRole('button', { name: /导出 CSV|Export CSV/i })).toBeInTheDocument();
    expect(within(more).getByRole('button', { name: /复制全部代码|Copy all symbols/i })).toBeInTheDocument();
    expect(within(more).getByRole('button', { name: /复制前 5|Copy top 5/i })).toBeInTheDocument();
    expect(within(more).getByRole('button', { name: /加入全部入选|Add official selected/i })).toBeInTheDocument();
    expect(within(more).getByRole('button', { name: /加入预览入选|Add preview selected/i })).toBeInTheDocument();
    expect(within(more).getByRole('button', { name: /批量回测|Batch backtest/i })).toBeInTheDocument();
    expect(within(more).queryByRole('button', { name: /历史扫描回放|Historical replay/i })).not.toBeInTheDocument();
  });

  it('keeps strategy experiment collapsed by default and exposes Backtest Lab inside it', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    const experiment = await screen.findByTestId('scanner-strategy-experiment');
    expect(within(experiment).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i })).toHaveTextContent(/展开|Expand/i);
    expect(screen.queryByTestId('scanner-backtest-lab')).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-strategy-simulation')).not.toBeInTheDocument();

    fireEvent.click(within(experiment).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i }));
    expect(within(experiment).getByRole('button', { name: /收起.*(?:回测准备|Backtest setup)|Collapse.*(?:回测准备|Backtest setup)/i })).toHaveTextContent(/收起|Collapse/i);
    const lab = await screen.findByTestId('scanner-backtest-lab');

    expect(lab).toHaveTextContent(/候选单标的回测|Candidate single-symbol backtest/i);
    expect(lab).toHaveTextContent(/100000/);
    expect(lab).toHaveTextContent(/auto/i);
    expect(lab).toHaveTextContent(/fee\/slip|费用\/滑点/i);
  });

  it('keeps strategy historical simulation collapsed by default and exposes controls on expand', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    const experiment = await screen.findByTestId('scanner-strategy-experiment');
    fireEvent.click(within(experiment).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i }));
    const panel = await screen.findByTestId('scanner-strategy-simulation');

    expect(within(panel).getByRole('button', { name: '30D' })).toBeInTheDocument();
    expect(within(panel).getByRole('button', { name: '90D' })).toBeInTheDocument();
    expect(within(panel).getByRole('button', { name: '180D' })).toBeInTheDocument();
    expect(within(panel).getByRole('button', { name: '1D' })).toBeInTheDocument();
    expect(within(panel).getByRole('button', { name: '5D' })).toBeInTheDocument();
    expect(within(panel).getByRole('button', { name: '10D' })).toBeInTheDocument();
    expect(within(panel).getByRole('button', { name: '20D' })).toBeInTheDocument();
  });

  it('runs strategy historical simulation with current scanner theme profile and market', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    const experiment = await screen.findByTestId('scanner-strategy-experiment');
    fireEvent.click(within(experiment).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i }));
    const panel = await screen.findByTestId('scanner-strategy-simulation');
    fireEvent.click(within(panel).getByRole('button', { name: '30D' }));
    fireEvent.click(within(panel).getByRole('button', { name: '10D' }));
    fireEvent.click(within(panel).getByRole('button', { name: /运行模拟|Run sim/i }));

    await waitFor(() => {
      expect(getStrategySimulation).toHaveBeenCalledWith({
        theme: 'crypto_miners',
        profile: 'us_preopen_v1',
        market: 'us',
        lookbackDays: 30,
        forwardDays: 10,
        limit: 50,
      });
    });
  });

  it('renders strategy historical simulation loading insufficient ready tables and warnings compactly', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    getStrategySimulation.mockImplementationOnce(() => new Promise(() => {}));
    const loadingRender = renderUserScannerPage();

    const loadingExperiment = await screen.findByTestId('scanner-strategy-experiment');
    fireEvent.click(within(loadingExperiment).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i }));
    const loadingPanel = await screen.findByTestId('scanner-strategy-simulation');
    fireEvent.click(within(loadingPanel).getByRole('button', { name: /运行模拟|Run sim/i }));
    expect(await within(loadingPanel).findByRole('button', { name: /运行中|Running/i })).toBeDisabled();

    loadingRender.unmount();
    getStrategySimulation.mockResolvedValueOnce({
      theme: 'crypto_miners',
      profile: 'us_preopen_v1',
      market: 'us',
      window: { lookbackDays: 90, forwardDays: 5, runCount: 1 },
      status: 'insufficient_history',
      summary: {
        historicalRuns: 1,
        selectionEvents: 0,
        avgSelectedPerRun: null,
        hitRate: null,
        avgForwardReturnPct: null,
        medianForwardReturnPct: null,
        avgBenchmarkReturnPct: null,
        avgExcessReturnPct: null,
        positiveSelectionRate: null,
        bestSymbol: null,
        worstSymbol: null,
        dataCoverage: null,
      },
      runs: [],
      symbols: [],
      warnings: ['历史扫描不足 · 当前只有 1 次可比较运行'],
    });
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    const insufficientRender = renderUserScannerPage();
    const insufficientExperiment = await screen.findByTestId('scanner-strategy-experiment');
    fireEvent.click(within(insufficientExperiment).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i }));
    const insufficientPanel = await screen.findByTestId('scanner-strategy-simulation');
    fireEvent.click(within(insufficientPanel).getByRole('button', { name: /运行模拟|Run sim/i }));
    expect(await within(insufficientPanel).findByTestId('scanner-strategy-simulation-compact-message')).toHaveTextContent(/历史扫描不足/);
    expect(within(insufficientPanel).queryByTestId('scanner-strategy-simulation-runs')).not.toBeInTheDocument();

    insufficientRender.unmount();
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();
    const readyExperiment = await screen.findByTestId('scanner-strategy-experiment');
    fireEvent.click(within(readyExperiment).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i }));
    const readyPanel = await screen.findByTestId('scanner-strategy-simulation');
    fireEvent.click(within(readyPanel).getByRole('button', { name: /运行模拟|Run sim/i }));

    expect(await within(readyPanel).findByTestId('scanner-strategy-simulation-summary')).toHaveTextContent(/\+3\.2%/);
    expect(within(readyPanel).getByTestId('scanner-strategy-simulation-runs')).toHaveTextContent('WULF');
    expect(within(readyPanel).getByTestId('scanner-strategy-simulation-symbols')).toHaveTextContent('12.1%');
    expect(within(readyPanel).getByTestId('scanner-strategy-simulation-warnings')).toHaveTextContent(/missing forward price data/);
  });

  it('keeps strategy historical simulation mobile-safe with quiet horizontal tables', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    const experiment = await screen.findByTestId('scanner-strategy-experiment');
    fireEvent.click(within(experiment).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i }));
    const panel = await screen.findByTestId('scanner-strategy-simulation');
    fireEvent.click(within(panel).getByRole('button', { name: /运行模拟|Run sim/i }));

    const runsTable = await within(panel).findByTestId('scanner-strategy-simulation-runs');
    expect(runsTable).toHaveClass('overflow-x-auto', 'no-scrollbar');
    expect(screen.getByTestId('scanner-candidate-filters')).toHaveClass('ui-scroll-x-quiet');
  });

  it('runs an individual scanner candidate backtest and links to the shared result report', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    const card = await screen.findByTestId('scanner-result-row-WULF');
    fireEvent.click(getActionButton(card, /详情|Detail/i));
    const detail = await screen.findByTestId('scanner-result-detail-WULF');
    fireEvent.click(within(detail).getByRole('button', { name: /回测|Backtest/i }));
    fireEvent.click(within(detail).getByRole('button', { name: /候选说明|Candidate notes/i }));

    await waitFor(() => {
      expect(runRuleBacktest).toHaveBeenCalledWith(expect.objectContaining({
        code: 'WULF',
        initialCapital: 100000,
        feeBps: 0,
        slippageBps: 0,
        benchmarkMode: 'auto',
        confirmed: true,
        waitForCompletion: true,
      }));
    });
    expect(await within(detail).findByText(/\+12\.3%/)).toBeInTheDocument();
    expect(within(detail).getByText(/-8\.1%/)).toBeInTheDocument();
    expect(within(detail).getByText(/1\.20/)).toBeInTheDocument();
    expect(await within(detail).findByRole('link', { name: /查看报告|Report/i })).toHaveAttribute('href', expect.stringMatching(/\/(zh|en)\/backtest\/results\/27/));
  });

  it('batch backtests official selected symbols only and prevents duplicate clicks', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    const experiment = await screen.findByTestId('scanner-strategy-experiment');
    fireEvent.click(within(experiment).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i }));
    const lab = await screen.findByTestId('scanner-backtest-lab');
    const officialButton = within(lab).getByRole('button', { name: /回测官方入选|Official selected/i });
    fireEvent.click(officialButton);
    fireEvent.click(officialButton);

    await waitFor(() => {
      expect(runRuleBacktest).toHaveBeenCalledTimes(1);
      expect(runRuleBacktest).toHaveBeenCalledWith(expect.objectContaining({ code: 'WULF' }));
    });
    expect(await within(lab).findByText('WULF')).toBeInTheDocument();
    expect(within(lab).queryByText('MARA')).not.toBeInTheDocument();
  });

  it('batch backtests preview selected, top five, and current filtered candidate sets without rejected or data-failed rows', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    const previewRender = renderUserScannerPage();

    const experiment = await screen.findByTestId('scanner-strategy-experiment');
    fireEvent.click(within(experiment).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i }));
    const lab = await screen.findByTestId('scanner-backtest-lab');
    fireEvent.click(within(lab).getByRole('button', { name: /回测预览入选|Preview selected/i }));
    await waitFor(() => {
      expect(runRuleBacktest.mock.calls.map((call) => call[0].code)).toEqual(['WULF']);
    });

    previewRender.unmount();
    runRuleBacktest.mockClear();
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    const topRender = renderUserScannerPage();
    const topExperiment = await screen.findByTestId('scanner-strategy-experiment');
    fireEvent.click(within(topExperiment).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i }));
    const topLab = await screen.findByTestId('scanner-backtest-lab');
    fireEvent.click(within(topLab).getByRole('button', { name: /回测前 5 名|Top 5/i }));
    await waitFor(() => {
      expect(runRuleBacktest.mock.calls.map((call) => call[0].code)).toEqual(['WULF']);
    });

    topRender.unmount();
    runRuleBacktest.mockClear();
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();
    const filteredExperiment = await screen.findByTestId('scanner-strategy-experiment');
    fireEvent.click(within(filteredExperiment).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i }));
    const filteredLab = await screen.findByTestId('scanner-backtest-lab');
    fireEvent.click(screen.getByRole('button', { name: /候选池|Candidate pool/i }));
    fireEvent.click(within(filteredLab).getByRole('button', { name: /回测当前筛选|Filtered/i }));
    await waitFor(() => {
      expect(runRuleBacktest.mock.calls.map((call) => call[0].code)).toEqual(['WULF']);
    });

    runRuleBacktest.mockClear();
    fireEvent.click(within(screen.getByTestId('scanner-candidate-filters')).getByRole('button', { name: /数据受限|Limited data/i }));
    expect(within(filteredLab).getByRole('button', { name: /回测当前筛选|Filtered/i })).toBeDisabled();
    expect(runRuleBacktest).not.toHaveBeenCalled();
  });

  it('renders compact failed backtest errors without crashing old scanner responses', async () => {
    runRuleBacktest.mockRejectedValueOnce(new Error('sample unavailable'));
    getRun.mockResolvedValue(makeRunDetail({ candidates: [], shortlist: [], selected: [] }));
    renderUserScannerPage();

    expect(await screen.findByTestId('user-scanner-workspace')).toBeInTheDocument();

    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();
    const experiment = await screen.findByTestId('scanner-strategy-experiment');
    fireEvent.click(within(experiment).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i }));
    const lab = await screen.findByTestId('scanner-backtest-lab');
    fireEvent.click(within(lab).getByRole('button', { name: /回测官方入选|Official selected/i }));

    expect(await within(lab).findByText(/sample unavailable/i)).toBeInTheDocument();
  });

  it('renders strategy preview controls and updates preview count locally without rerunning scanner', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    const experiment = await screen.findByTestId('scanner-strategy-experiment');
    expect(screen.queryByTestId('scanner-strategy-preview')).not.toBeInTheDocument();
    fireEvent.click(within(experiment).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i }));
    const strategyPreview = await screen.findByTestId('scanner-strategy-preview');
    expect(strategyPreview).toHaveTextContent(/Official|官方/);
    expect(screen.getByTestId('scanner-strategy-preview')).toHaveTextContent(/Preview|预览/);
    const runCalls = runScan.mock.calls.length;
    const getRunCalls = getRun.mock.calls.length;

    fireEvent.click(within(screen.getByTestId('scanner-strategy-preview')).getByRole('button', { name: /60/ }));
    expect(screen.getByTestId('scanner-strategy-preview')).toHaveTextContent(/Preview\s*1|预览\s*1/);

    fireEvent.click(within(screen.getByTestId('scanner-strategy-preview')).getByRole('button', { name: /50/ }));
    expect(screen.getByTestId('scanner-strategy-preview')).toHaveTextContent(/Preview|预览/);
    expect(runScan).toHaveBeenCalledTimes(runCalls);
    expect(getRun).toHaveBeenCalledTimes(getRunCalls);
  });

  it('marks preview-selected candidates and keeps WULF as the official selected card', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    const wulfCard = await screen.findByTestId('scanner-result-row-WULF');
    expect(wulfCard).toHaveTextContent(/官方|Official/);
    expect(wulfCard).toHaveTextContent('WULF');
    fireEvent.click(screen.getByRole('button', { name: /候选池|Candidate pool/i }));
    expect(await screen.findByTestId('scanner-candidate-row-MARA')).toHaveTextContent(/预览|Preview/);
    expect(screen.getByTestId('scanner-candidate-row-RIOT')).toHaveTextContent(/预览|Preview/);
    expect(screen.getByTestId('scanner-candidate-row-CIFR')).toHaveTextContent(/数据受限|Limited data/);
  });

  it('sorts candidate pool by official selected, preview selected, score, and original rank', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    fireEvent.click(await screen.findByRole('button', { name: /候选池|Candidate pool/i }));

    const rows = screen.getAllByTestId(/^scanner-candidate-row-/).map((row) => row.getAttribute('data-testid'));
    expect(rows.slice(0, 4)).toEqual([
      'scanner-candidate-row-WULF',
      'scanner-candidate-row-MARA',
      'scanner-candidate-row-RIOT',
      'scanner-candidate-row-CIFR',
    ]);
  });

  it('opens inline detail from preview rows and keeps table visible', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    await screen.findByTestId('scanner-result-row-WULF');
    const filters = await screen.findByTestId('scanner-candidate-filters');
    fireEvent.click(within(filters).getByRole('button', { name: /候选池|Candidate pool/i }));
    fireEvent.click(await screen.findByTestId('scanner-candidate-row-MARA'));

    await waitFor(() => {
      expect(screen.getByTestId('scanner-candidate-detail-MARA')).toHaveTextContent(/流动性不足|Liquidity weak/);
    });
    expect(screen.getByTestId('scanner-ranked-list')).toBeInTheDocument();
    expect(screen.getByTestId('scanner-candidate-inspector')).toBeInTheDocument();
  });

  it('renders previous comparable run comparison and candidate deltas', async () => {
    const currentRun = makeCryptoDiagnosticsRun();
    const previousRun = makeCryptoDiagnosticsRun({
      id: 10,
      completedAt: '2026-04-21T08:31:00',
      candidates: [
        { symbol: 'WULF', name: 'TeraWulf', rank: 1, status: 'selected', score: 56, provider: 'alpaca', reason: 'passed', failedRules: [], missingFields: [], metrics: {} },
        { symbol: 'MARA', name: 'MARA Holdings', rank: 2, status: 'selected', score: 61, provider: 'alpaca', reason: 'passed', failedRules: [], missingFields: [], metrics: {} },
        { symbol: 'HUT', name: 'Hut 8', rank: 5, status: 'rejected', score: 41, provider: 'alpaca', reason: 'weak', failedRules: ['weak'], missingFields: [], metrics: {} },
      ],
    });
    getRuns.mockResolvedValue(makeHistoryResponse([
      makeHistoryItem({ id: 11, market: 'us', profile: 'us_preopen_v1', universeType: 'theme', themeId: 'crypto_miners', themeLabel: '加密矿企', topSymbols: ['WULF'] }),
      makeHistoryItem({ id: 10, market: 'us', profile: 'us_preopen_v1', universeType: 'theme', themeId: 'crypto_miners', themeLabel: '加密矿企', topSymbols: ['WULF', 'MARA'] }),
    ]));
    getRun.mockImplementation((runId: number) => Promise.resolve(runId === 10 ? previousRun : currentRun));
    renderUserScannerPage();

    const comparison = await screen.findByTestId('scanner-run-comparison-strip');
    fireEvent.click(within(comparison).getByRole('button', { name: /^(?:展开|Expand).*?(?:比较记录|Comparison records|Compare records)$/i }));
    const historySummary = await screen.findByTestId('scanner-result-history-summary');
    await waitFor(() => {
      expect(historySummary).toHaveTextContent(/本次扫描|Current scan/);
      expect(historySummary).toHaveTextContent(/最近扫描|Latest scan/);
      expect(historySummary).toHaveTextContent(/上次扫描|Previous scan/);
    });
    expect(screen.getByTestId('scanner-run-comparison-compact')).toHaveTextContent(/候选减少|排序首位（观察）变化|分数变化|候选变化|Candidates|Top-ranked row changed|Score|Candidate/);

    await waitFor(() => {
      expect(comparison).toHaveTextContent(/WULF.*连续入选|WULF.*Retained selected/i);
    });
    await waitFor(() => {
      expect(screen.getByTestId('scanner-run-comparison-strip')).toHaveTextContent(/WULF.*连续入选|WULF.*Retained selected/i);
      expect(screen.getByTestId('scanner-run-comparison-strip')).toHaveTextContent(/MARA.*上次入选|MARA.*Selected last run/i);
    });

    fireEvent.click(screen.getByRole('button', { name: /候选池|Candidate pool/i }));
    expect(await screen.findByTestId('scanner-candidate-row-WULF')).toHaveTextContent(/\+4/);
    expect(screen.getByTestId('scanner-candidate-row-WULF')).toHaveTextContent(/连续入选|Retained selected/i);
    expect(screen.getByTestId('scanner-candidate-row-MARA')).toHaveTextContent(/-6/);
    expect(screen.getByTestId('scanner-candidate-row-MARA')).toHaveTextContent(/上次入选|Selected last run/i);
  });

  it('shows compact empty comparison state when no previous comparable run exists', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRuns.mockResolvedValue(makeHistoryResponse([
      makeHistoryItem({ id: 11, market: 'us', profile: 'us_preopen_v1', universeType: 'theme', themeId: 'crypto_miners', themeLabel: '加密矿企', topSymbols: ['WULF'] }),
    ]));
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    const comparison = await screen.findByTestId('scanner-run-comparison-strip');
    expect(within(comparison).getByRole('button', { name: /^(?:展开|Expand).*?(?:比较记录|Comparison records|Compare records)$/i })).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(within(comparison).getByRole('button', { name: /^(?:展开|Expand).*?(?:比较记录|Comparison records|Compare records)$/i }));
    expect(comparison).toHaveTextContent(/暂无上次扫描对比|No previous comparable run/);
    expect(screen.getByTestId('scanner-previous-empty-state')).toHaveTextContent(/暂无历史扫描|No previous scan/);
  });

  it('maps scanner failure and no-data states to compact labels without raw provider enums by default', async () => {
    const failedRun = makeRunDetail({
      status: 'failed',
      failureReason: 'provider_error',
      shortlist: [],
      selected: [],
      candidates: [],
      summary: {
        universeCount: 20,
        submittedCount: 20,
        evaluatedCount: 0,
        selectedCount: 0,
        rejectedCount: 0,
        dataFailedCount: 20,
        skippedCount: 0,
        errorCount: 1,
        limitedByResultCap: false,
      },
      diagnostics: {
        providerDiagnostics: {
          configuredPrimaryProvider: 'provider_down',
          quoteSourceUsed: 'provider_down',
          snapshotSourceUsed: 'provider_error',
          historySourceUsed: 'unknown',
          providersUsed: ['provider_down', 'provider_error', 'unknown'],
          fallbackOccurred: true,
          fallbackCount: 1,
          providerFailureCount: 3,
          missingDataSymbolCount: 20,
          providerWarnings: ['provider_down raw detail'],
        },
      },
    });
    getRun.mockResolvedValue(failedRun);

    renderUserScannerPage();

    const summary = await screen.findByTestId('scanner-status-strip');
    await waitFor(() => expect(summary).toHaveTextContent(/失败|Failed/));
    expect(summary).toHaveTextContent(/数据暂不可用|Data unavailable/);
    expect(summary).not.toHaveTextContent(/20\/20/);
    expect(summary).not.toHaveTextContent('provider_down');
    expect(summary).not.toHaveTextContent('provider_error');
    expect(summary).not.toHaveTextContent('unknown');
    expect(screen.queryByTestId('scanner-diagnostics-panel')).not.toBeInTheDocument();
  });

  it('adds official candidates through batch watchlist actions without rejected or data-failed rows', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    listWatchlistItems.mockResolvedValueOnce({
      items: [makeWatchlistItem({ id: 301, symbol: 'WULF', market: 'us', scannerRunId: 9, scannerRank: 1, scannerScore: 60 })],
    });
    addWatchlistItem
      .mockResolvedValueOnce(makeWatchlistItem({ id: 302, symbol: 'MARA', market: 'us', scannerRank: 2, scannerScore: 55 }))
      .mockResolvedValueOnce(makeWatchlistItem({ id: 303, symbol: 'RIOT', market: 'us', scannerRank: 3, scannerScore: 52 }));
    renderUserScannerPage();

    const more = await screen.findByTestId('scanner-more-actions');
    fireEvent.click(within(more).getByRole('button', { name: /更多|More/i }));
    fireEvent.click(within(more).getByRole('button', { name: /加入全部入选|Add official selected/i }));
    expect(await screen.findByText(/已加入 0 个 · 已存在 1 个|Added 0 · already existed 1/i)).toBeInTheDocument();

    fireEvent.click(within(more).getByRole('button', { name: /加入预览入选|Add preview selected/i }));
    await waitFor(() => {
      expect(screen.getByText(/已加入 0 个 · 已存在 1 个|Added 0 · already existed 1/i)).toBeInTheDocument();
    });
    expect(addWatchlistItem).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /候选池|Candidate pool/i }));
    fireEvent.click(within(screen.getByTestId('scanner-candidate-filters')).getByRole('button', { name: /数据受限|Limited data/i }));
    expect(within(more).getByRole('button', { name: /加入当前筛选|Add filtered/i })).toBeDisabled();
    expect(addWatchlistItem).not.toHaveBeenCalled();
  });

  it('exposes scanner research handoff links without raw IDs or internal metadata', async () => {
    const themedRun = makeCryptoDiagnosticsRun({ id: 42 });
    getRun.mockResolvedValue(themedRun);

    renderUserScannerPage();

    const panel = await screen.findByTestId('scanner-research-workspace-flow');
    expect(panel).toHaveTextContent('WULF');
    expect(panel).not.toHaveTextContent(/Run #|Rank #|scannerRunId|watchlistItemId|provider|cache|runtime|debug/i);

    const watchlistLink = within(panel).getByTestId('research-workspace-link-watchlist');
    expect(watchlistLink).toHaveAttribute('href', expect.stringContaining('/watchlist?'));
    expect(watchlistLink).toHaveAttribute('href', expect.stringContaining('symbol=WULF'));
    expect(watchlistLink).toHaveAttribute('href', expect.stringContaining('market=US'));
    expect(watchlistLink).toHaveAttribute('href', expect.stringContaining('source=scanner'));

    const stockStructureLink = within(panel).getByTestId('research-workspace-link-stock-structure');
    expect(stockStructureLink).toHaveAttribute('href', expect.stringContaining('/stocks/WULF/structure-decision?'));
    expect(stockStructureLink).toHaveAttribute('href', expect.stringContaining('symbol=WULF'));
    expect(stockStructureLink).toHaveAttribute('href', expect.stringContaining('market=US'));
    expect(stockStructureLink).toHaveAttribute('href', expect.stringContaining('source=scanner'));

    for (const link of within(panel).getAllByRole('link')) {
      expect(link).toHaveAttribute('href', expect.not.stringMatching(/scannerRunId|scannerRank|watchlistItemId|themeId|universeType|provider|cache|runtime|debug/i));
    }
  });

  it('keeps action buttons from changing row inspector selection', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    fireEvent.click(await screen.findByRole('button', { name: /候选池|Candidate pool/i }));
    fireEvent.click(await screen.findByTestId('scanner-candidate-row-MARA'));
    expect(screen.getByTestId('scanner-candidate-detail-MARA')).toHaveTextContent(/流动性不足|Liquidity weak/);

    const riotRow = screen.getByTestId('scanner-candidate-row-RIOT');
    fireEvent.click(getActionButton(riotRow, /更多|More/i));
    fireEvent.click(await within(getRankedRow('RIOT')).findByRole('button', { name: /复制|Copy/i }));

    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalledWith('RIOT');
    });
    expect(screen.getByTestId('scanner-candidate-detail-MARA')).toBeInTheDocument();
  });

  it('keeps candidate rows to one primary action plus more actions', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    fireEvent.click(await screen.findByRole('button', { name: /候选池|Candidate pool/i }));
    const maraRow = await screen.findByTestId('scanner-candidate-row-MARA');
    const rankedRow = getRankedRow('MARA');
    expect(within(maraRow).getAllByRole('button').map((button) => button.textContent)).toEqual(
      expect.arrayContaining([expect.stringMatching(/详情|Detail/), expect.stringMatching(/更多|More/)]),
    );
    expect(within(rankedRow).queryByRole('button', { name: /回测|Backtest/i })).not.toBeInTheDocument();

    fireEvent.click(getActionButton(maraRow, /更多|More/i));
    expect(await within(rankedRow).findByRole('button', { name: /回测|Backtest/i })).toBeInTheDocument();
    expect(within(rankedRow).getByRole('button', { name: /复制|Copy/i })).toBeInTheDocument();
  });

  it('keeps strategy controls and batch actions available in the narrow/mobile structure', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    expect(await screen.findByTestId('scanner-primary-actions')).toHaveClass('flex');
    await screen.findByTestId('scanner-candidate-filters');
    expect(screen.queryByTestId('scanner-strategy-preview')).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-batch-actions')).not.toBeInTheDocument();
    expect(within(screen.getByTestId('scanner-strategy-experiment')).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i })).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByTestId('scanner-candidate-filters')).toHaveClass('ui-scroll-x-quiet');
    expect(screen.getByTestId('scanner-inline-detail-panel')).toBeInTheDocument();
  });

  it('keeps the theme select overflow-safe', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    expect(await screen.findByTestId('scanner-launch-bar')).toBeInTheDocument();
    expect(screen.queryByText(/基础扫描|Basic scan/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/高级参数|Advanced controls/i)).not.toBeInTheDocument();
    expect(screen.getByTestId('scanner-launch-controls')).toHaveTextContent(/候选上限.*评估深度|Scope cap.*Detailed review/i);
    fireEvent.click(within(screen.getByTestId('scanner-scope-selector')).getByRole('button', { name: /主题标的池|Theme scope/i }));
    await openAdvancedControls();
    const themeSelect = await screen.findByTestId('scanner-theme-select');
    expect(themeSelect).toHaveClass('absolute', 'inset-0', 'opacity-0');
    expect(themeSelect.closest('.select-field__control')?.querySelector('.select-field__value')).toHaveClass('min-w-0', 'flex-1', 'truncate');
  });

  it('updates the candidate inspector from selected, rejected, and data-failed rows', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    const selectedRow = await screen.findByTestId('scanner-result-row-WULF');
    fireEvent.click(getActionButton(selectedRow, /详情|Detail/i));
    const selectedDetail = await screen.findByTestId('scanner-result-detail-WULF');
    expect(selectedDetail).toHaveTextContent(/当前信号|Why now/);
    expect(selectedDetail).toHaveTextContent(/风险|Risk/);

    fireEvent.click(screen.getByRole('button', { name: /候选池|Candidate pool/i }));
    fireEvent.click(await screen.findByTestId('scanner-candidate-row-MARA'));

    expect(await screen.findByTestId('scanner-candidate-detail-MARA')).toHaveTextContent(/流动性不足|Liquidity weak/);

    fireEvent.click(within(screen.getByTestId('scanner-candidate-filters')).getByRole('button', { name: /数据受限|Limited data/i }));
    fireEvent.click(await screen.findByTestId('scanner-candidate-row-CIFR'));

    expect(await screen.findByTestId('scanner-candidate-detail-CIFR')).toHaveTextContent(/历史数据不足|Historical data insufficient|数据不足/);
    expect(screen.getByTestId('scanner-inline-detail-panel')).toBeInTheDocument();
  });

  it('keeps the chosen preview threshold and falls back to the first visible candidate when filters hide the current detail row', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    fireEvent.click(await screen.findByRole('button', { name: /候选池|Candidate pool/i }));
    const experiment = await screen.findByTestId('scanner-strategy-experiment');
    fireEvent.click(within(experiment).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i }));
    const previewPanel = await screen.findByTestId('scanner-strategy-preview');
    fireEvent.click(within(previewPanel).getByRole('button', { name: '60' }));
    fireEvent.click(await screen.findByTestId('scanner-candidate-row-MARA'));
    expect(await screen.findByTestId('scanner-candidate-detail-MARA')).toBeInTheDocument();

    fireEvent.click(within(screen.getByTestId('scanner-candidate-filters')).getByRole('button', { name: /数据受限|Limited data/i }));

    expect(await screen.findByTestId('scanner-candidate-detail-CIFR')).toBeInTheDocument();
    expect(within(previewPanel).getByRole('button', { name: '60' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('keeps inline candidate detail free of developer fields', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    fireEvent.click(await screen.findByRole('button', { name: /候选池|Candidate pool/i }));
    const wulfRow = await screen.findByTestId('scanner-candidate-row-WULF');
    fireEvent.click(wulfRow);
    const detail = await screen.findByTestId('scanner-candidate-detail-WULF');
    expect(detail).toHaveTextContent(/当前信号|Why now/);
    expect(detail).toHaveTextContent(/风险说明|Risk|风险/);
    expect(detail).not.toHaveTextContent(/开发者|Developer|raw metrics|原始指标|providerDiagnostics/i);
  });

  it('filters scanner diagnostics by rejected and data-failed candidates', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    expect(await screen.findByTestId('scanner-result-row-WULF')).toBeInTheDocument();
    expect(screen.queryByTestId('scanner-candidate-row-MARA')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /淘汰|Rejected/i }));
    expect(await screen.findByTestId('scanner-candidate-row-MARA')).toHaveTextContent(/流动性不足|Liquidity weak/);
    expect(screen.getByTestId('scanner-candidate-row-RIOT')).toHaveTextContent(/价格低于阈值|Price below threshold/);
    expect(screen.queryByTestId('scanner-candidate-row-CIFR')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /数据受限|Limited data/i }));
    expect(await screen.findByTestId('scanner-candidate-row-CIFR')).toHaveTextContent(/历史数据不足|Historical data insufficient|数据不足/);
    expect(screen.getByTestId('scanner-candidate-row-HIVE')).toHaveTextContent(/数据不足，结论仅供观察|Data insufficient, observe only|实时缺失|Realtime missing/);
    expect(screen.queryByTestId('scanner-candidate-row-MARA')).not.toBeInTheDocument();
  });

  it('expands candidate data notes without raw failed-rule codes or provider fields', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    fireEvent.click(await screen.findByRole('button', { name: /候选池|Candidate pool/i }));
    const cifrRow = await screen.findByTestId('scanner-candidate-row-CIFR');
    fireEvent.click(cifrRow);

    const detail = await screen.findByTestId('scanner-candidate-detail-CIFR');
    expect(within(detail).getAllByText(/历史数据不足|Historical data insufficient|数据不足/).length).toBeGreaterThan(0);
    expect(detail).not.toHaveTextContent('not_enough_history');
    expect(detail).not.toHaveTextContent(/^history$/);
    expect(detail).not.toHaveTextContent(/Provider|开发者|raw metrics|原始指标/i);
  });

  it('keeps old scanner responses on the selected-card workflow without diagnostics tabs', async () => {
    const legacyRun = {
      ...makeRunDetail(),
      theme: undefined,
      summary: undefined,
      selected: undefined,
      candidates: undefined,
    } as ScannerRunDetail;
    getRun.mockResolvedValue(legacyRun);
    renderUserScannerPage();

    expect(await screen.findByTestId('scanner-result-row-NVDA')).toBeInTheDocument();
    expect(screen.queryByTestId('scanner-candidate-filters')).not.toBeInTheDocument();
    expect(screen.getByTestId('scanner-status-strip')).toHaveTextContent(/Recent available data|最近可用数据/);
    expect(screen.getByTestId('scanner-candidate-inspector')).toBeInTheDocument();
    expect(screen.getByTestId('scanner-result-table')).toBeInTheDocument();
  });

  it('creates an AI custom theme, displays suggestions, and runs it as a theme universe', async () => {
    const themedRun = makeRunDetail({
      market: 'us',
      profile: 'us_preopen_v1',
      universeType: 'theme',
      themeId: 'custom_white_house_stocks',
      themeLabel: 'White House Stocks',
      diagnostics: {
        universeSelection: {
          universeType: 'theme',
          themeId: 'custom_white_house_stocks',
          themeLabel: 'White House Stocks',
          requestedSymbolsCount: 3,
          acceptedSymbolsCount: 3,
          acceptedSymbols: ['PLTR', 'LMT', 'RTX'],
          rejectedSymbols: [],
          universeNotes: [],
        },
      },
    });
    runScan.mockResolvedValueOnce(themedRun);
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    fireEvent.click(await screen.findByRole('button', { name: /美股|US/ }));
    fireEvent.click(within(screen.getByTestId('scanner-scope-selector')).getByRole('button', { name: /Theme scope|主题标的池/i }));
    await openAdvancedControls();
    fireEvent.change(await screen.findByTestId('scanner-ai-theme-label-input'), { target: { value: 'White House Stocks' } });
    fireEvent.change(screen.getByTestId('scanner-ai-theme-prompt-input'), {
      target: { value: 'Stocks associated with White House policy, federal contracts, and government decisions.' },
    });
    fireEvent.change(screen.getByTestId('scanner-ai-theme-manual-symbols-input'), { target: { value: 'PLTR' } });
    fireEvent.click(screen.getByRole('button', { name: /Generate theme|生成主题/i }));

    expect(await screen.findByTestId('scanner-ai-theme-suggestions')).toHaveTextContent('PLTR');
    expect(createTheme).toHaveBeenCalledWith({
      id: 'custom_white_house_stocks',
      label: 'White House Stocks',
      market: 'us',
      prompt: 'Stocks associated with White House policy, federal contracts, and government decisions.',
      manualSymbols: ['PLTR'],
    });

    fireEvent.click(screen.getByRole('button', { name: /启动扫描|运行扫描|Run scanner/i }));
    await waitFor(() => {
      expect(runScan).toHaveBeenCalledWith(expect.objectContaining({
        market: 'us',
        universeType: 'theme',
        themeId: 'custom_white_house_stocks',
      }));
    });
  });

  it('shows field-level validation for scanner scope inputs before sending requests', async () => {
    renderUserScannerPage();

    fireEvent.click(within(screen.getByTestId('scanner-scope-selector')).getByRole('button', { name: /自定义标的|Custom symbols/i }));
    await openAdvancedControls();
    fireEvent.click(screen.getByRole('button', { name: /启动扫描|运行扫描|Run scanner/i }));

    expect(await screen.findAllByText(/运行前请输入一个或多个标的代码|Enter one or more symbols before running/i)).not.toHaveLength(0);
    expect(runScan).not.toHaveBeenCalled();
  });

  it('shows field-level validation for AI theme generation before sending requests', async () => {
    renderUserScannerPage();

    fireEvent.click(within(screen.getByTestId('scanner-scope-selector')).getByRole('button', { name: /主题标的池|Theme scope/i }));
    await openAdvancedControls();
    fireEvent.change(screen.getByTestId('scanner-ai-theme-label-input'), { target: { value: 'A' } });
    fireEvent.change(screen.getByTestId('scanner-ai-theme-prompt-input'), { target: { value: 'too short' } });
    fireEvent.click(screen.getByRole('button', { name: /Generate theme|生成主题/i }));

    expect(await screen.findByText(/主题名称至少需要 2 个字符|Theme name must be at least 2 characters/i)).toBeInTheDocument();
    expect(screen.getByText(/筛选条件至少需要 12 个字符|Criteria must be at least 12 characters/i)).toBeInTheDocument();
    expect(createTheme).not.toHaveBeenCalled();
  });

  it('shows pending scanner feedback before resolving into a blocked no-candidate state', async () => {
    const blockedRun = makeRunDetail();
    blockedRun.shortlist = [];
    blockedRun.selected = [];
    blockedRun.diagnostics = {
      ...(blockedRun.diagnostics || {}),
      dataReadiness: {
        state: 'blocked',
        blockerBucket: 'missing_history',
        nextDataAction: '补齐历史数据后再重试。',
      },
    };
    blockedRun.summary = {
      ...blockedRun.summary,
      selectedCount: 0,
      rejectedCount: 18,
      dataFailedCount: 22,
      errorCount: 0,
    };

    let resolveRun: ((value: ScannerRunDetail) => void) | null = null;
    runScan.mockImplementationOnce(() => new Promise((resolve) => {
      resolveRun = resolve;
    }));
    getRun.mockResolvedValue(blockedRun);

    renderUserScannerPage();

    const runButton = await screen.findByRole('button', { name: /启动扫描|运行扫描|run scanner/i });
    fireEvent.click(runButton);

    expect(await screen.findByTestId('scanner-run-feedback')).toHaveTextContent(/扫描请求提交中|Scanner request submitted/i);
    expect(screen.getByTestId('scanner-run-feedback')).toHaveTextContent(/正在按当前市场、范围和数据就绪度检查|Checking the current market, scope, and data readiness/i);
    expect(runButton).toBeDisabled();
    expect(runButton).toHaveAttribute('aria-busy', 'true');
    expect(runButton).toHaveTextContent(/扫描中|Scanning/i);
    fireEvent.click(runButton);
    expect(runScan).toHaveBeenCalledTimes(1);

    resolveRun?.(blockedRun);

    await waitFor(() => {
      expect(screen.getByTestId('scanner-run-feedback')).toHaveTextContent(/本次未形成入选候选|No selected candidate in this run|History pending|历史数据待补/i);
    });
    expect(screen.getByTestId('scanner-run-feedback')).toHaveTextContent('补齐历史数据后再重试。');
    expect(screen.getByTestId('scanner-conclusion-band')).toHaveTextContent(/补齐历史数据后再重试|Check the rejection mix or history/i);
  });

  it('keeps Scanner primary controls accessible while exposing labeled AI theme and symbol inputs', async () => {
    renderUserScannerPage();

    expect(screen.getByRole('button', { name: /启动扫描|运行扫描|Run scanner/i })).toBeInTheDocument();
    expect(screen.getByTestId('scanner-history-trigger')).toBeInTheDocument();

    fireEvent.click(within(screen.getByTestId('scanner-scope-selector')).getByRole('button', { name: /主题标的池|Theme scope/i }));
    await openAdvancedControls();

    expect(screen.getByRole('textbox', { name: /AI 主题名称|AI theme name/i })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: /AI 主题筛选条件|AI theme criteria/i })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: /手动补充股票代码|Manual symbol additions/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Generate theme|生成主题/i })).toBeInTheDocument();

    fireEvent.click(within(screen.getByTestId('scanner-scope-selector')).getByRole('button', { name: /自定义标的|Custom symbols/i }));
    expect(screen.getByRole('textbox', { name: /自定义扫描标的|Custom scanner symbols/i })).toBeInTheDocument();
  });

  it('shows disabled unconfigured themes and sends custom symbol universes', async () => {
    runScan.mockResolvedValueOnce(makeRunDetail({
      universeType: 'symbols',
      requestedSymbolsCount: 3,
      acceptedSymbolsCount: 3,
      rejectedSymbols: [],
      universeNotes: ['Custom symbol universe: 3 accepted.'],
    }));
    renderUserScannerPage();

    fireEvent.click(within(screen.getByTestId('scanner-scope-selector')).getByRole('button', { name: /主题标的池|Theme scope/i }));
    await openAdvancedControls();
    const themeSelect = screen.getByTestId('scanner-theme-select') as HTMLSelectElement;
    expect(within(themeSelect).getByRole('option', { name: /Optical modules \/ CPO.*not configured|光模块 CPO.*未配置/ })).toBeDisabled();

    fireEvent.click(within(screen.getByTestId('scanner-scope-selector')).getByRole('button', { name: /自定义标的|Custom symbols/i }));
    fireEvent.change(screen.getByTestId('scanner-custom-symbols-input'), {
      target: { value: 'MARA RIOT\nCLSK' },
    });
    expect(screen.getByText(/已解析 3|Parsed 3/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /启动扫描|运行扫描|Run scanner/i }));

    await waitFor(() => {
      expect(runScan).toHaveBeenCalledWith(expect.objectContaining({
        universeType: 'symbols',
        symbols: ['MARA', 'RIOT', 'CLSK'],
      }));
    });
  });

  it('does not render placeholder candidates after a failed manual run', async () => {
    let rejectRun: ((error: unknown) => void) | null = null;
    runScan.mockImplementationOnce(() => new Promise((_resolve, reject) => {
      rejectRun = reject;
    }));

    renderUserScannerPage();

    fireEvent.click(await screen.findByRole('button', { name: /启动扫描|运行扫描|run scanner/i }));

    expect(await screen.findByTestId('scanner-run-feedback')).toHaveTextContent(/扫描请求提交中|Scanner request submitted/i);

    rejectRun?.({
      response: {
        status: 400,
        data: {
          detail: {
            error: 'validation_error',
            message: 'A 股全市场快照不可用。',
          },
        },
      },
    });

    expect(await screen.findByTestId('scanner-page-error-summary')).toHaveTextContent(/数据不足|Insufficient data/);
    expect(await screen.findByTestId('scanner-run-feedback')).toHaveTextContent(/扫描未完成|Scan did not complete/i);
    expect(screen.getByTestId('scanner-run-feedback')).toHaveTextContent(/数据不足|Insufficient data/);
    expect(screen.queryByText('A 股全市场快照不可用。')).not.toBeInTheDocument();
    expect(within(screen.getByTestId('scanner-page-error-summary')).queryByRole('button', { name: /开发者细节|Developer details/i })).not.toBeInTheDocument();
    expect(screen.getByTestId('scanner-page-error-summary')).toHaveTextContent(/数据不足|Insufficient data/);
    expect(screen.queryByText('Tesla')).not.toBeInTheDocument();
    expect(screen.queryByText('Meta')).not.toBeInTheDocument();
    expect(screen.queryByText('Apple')).not.toBeInTheDocument();
  });

  it('shows consumer-safe auth feedback after a scanner run click', async () => {
    runScan.mockRejectedValueOnce(
      createApiError(
        createParsedApiError({
          title: '登录已失效',
          message: '请先登录后再运行扫描。',
          rawMessage: 'Unauthorized token=secret provider_trace',
          status: 401,
          code: 'unauthorized',
          category: 'auth_required',
          isAuthError: true,
        }),
      ),
    );

    renderUserScannerPage();

    fireEvent.click(await screen.findByRole('button', { name: /启动扫描|运行扫描|run scanner/i }));

    const feedback = await screen.findByTestId('scanner-run-feedback');
    expect(feedback).toHaveTextContent(/扫描未完成|Scan did not complete/i);
    expect(feedback).toHaveTextContent(/登录|Sign in/i);
    expect(feedback).not.toHaveTextContent(/Unauthorized|token|provider_trace|raw|provider|trace/i);

    const pageError = await screen.findByTestId('scanner-page-error-summary');
    expect(pageError).toHaveTextContent(/扫描未完成|Scan did not complete/i);
    expect(pageError).toHaveTextContent(/登录|Sign in/i);
    expect(pageError).not.toHaveTextContent(/Unauthorized|token|provider_trace|raw|provider|trace/i);
  });

  it('shows stale scanner universe readiness without fake candidates or internal leakage', async () => {
    getRuns.mockResolvedValue(makeHistoryResponse([]));
    getRun.mockResolvedValue(null);
    getStatus.mockResolvedValue({
      market: 'cn',
      profile: 'cn_preopen_v1',
      watchlistDate: '2026-06-27',
      todayTradingDay: true,
      scheduleEnabled: false,
      scheduleRunImmediately: false,
      notificationEnabled: false,
      qualitySummary: {
        available: false,
        reviewWindowDays: 5,
        runCount: 0,
        reviewedRunCount: 0,
        reviewedCandidateCount: 0,
        strongCount: 0,
        mixedCount: 0,
        weakCount: 0,
      },
      dataReadiness: {
        state: 'blocked',
        market: 'cn',
        profile: 'cn_preopen_v1',
        universeSize: 320,
        blockerBucket: 'stale_universe',
        quoteCoverage: 'unknown',
        historyCoverage: 'unknown',
        freshness: 'stale',
        nextDataAction: '刷新扫描标的池后重新运行 Scanner。',
        scannerUniverseReadiness: {
          contractVersion: 'scanner_universe_readiness_v1',
          status: 'stale',
          market: 'CN',
          universeSize: 320,
          lastUpdatedAt: '2026-06-20T00:00:00+00:00',
          freshnessState: 'universe_modified:2026-06-20',
          requiredDataClasses: ['universe', 'historical_ohlcv', 'quote_snapshot'],
          availableDataClasses: ['universe'],
          missingDataClasses: ['historical_ohlcv', 'quote_snapshot'],
          blockedProductSurfaces: ['Scanner', 'Market Overview', 'Backtest'],
          consumerSafeMessage: '扫描标的池已过期，需要更新后再扫描。',
          operatorNextAction: 'Refresh the scanner local universe and rerun scanner readiness checks.',
          consumerSafe: true,
        },
      },
    });

    renderUserScannerPage();

    const conclusion = await screen.findByTestId('scanner-conclusion-band');
    expect(conclusion).toHaveTextContent(/标的池待更新|Scope stale/);
    expect(conclusion).toHaveTextContent(/扫描标的池已过期|Scope/);
    expect(conclusion).toHaveTextContent(/标的池状态|Scope readiness/);
    expect(conclusion).toHaveTextContent(/缺口|Missing/);
    expect(conclusion).toHaveTextContent(/历史日线|实时报价|Price history|Realtime quotes/);
    expect(screen.queryByTestId(/^scanner-result-row-/)).not.toBeInTheDocument();
    const emptyState = screen.getByTestId('scanner-workbench-empty-state');
    expect(emptyState).toHaveTextContent(/刷新扫描标的池|标的池已过期/);
    expect(conclusion).not.toHaveTextContent(/universe|historical_ohlcv|quote_snapshot|provider|raw|cacheKey|traceId|requestId|token|secret|buy|sell|hold|target|stop|position/i);
    expect(emptyState).not.toHaveTextContent(/provider|raw|cacheKey|traceId|requestId|token|secret|buy|sell|hold|target|stop|position/i);
  });

  it('distinguishes missing scanner universe readiness from stale universe readiness', async () => {
    getRuns.mockResolvedValue(makeHistoryResponse([]));
    getRun.mockResolvedValue(null);
    getStatus.mockResolvedValue({
      market: 'cn',
      profile: 'cn_preopen_v1',
      watchlistDate: '2026-06-27',
      todayTradingDay: true,
      scheduleEnabled: false,
      scheduleRunImmediately: false,
      notificationEnabled: false,
      qualitySummary: {
        available: false,
        reviewWindowDays: 5,
        runCount: 0,
        reviewedRunCount: 0,
        reviewedCandidateCount: 0,
        strongCount: 0,
        mixedCount: 0,
        weakCount: 0,
      },
      dataReadiness: {
        state: 'blocked',
        market: 'cn',
        profile: 'cn_preopen_v1',
        universeSize: 0,
        blockerBucket: 'universe_missing',
        quoteCoverage: 'unknown',
        historyCoverage: 'unknown',
        freshness: 'unknown',
        nextDataAction: '补充可扫描标的池后重新运行 Scanner。',
        scannerUniverseReadiness: {
          contractVersion: 'scanner_universe_readiness_v1',
          status: 'missing',
          market: 'CN',
          universeSize: 0,
          freshnessState: 'missing_universe',
          requiredDataClasses: ['universe', 'historical_ohlcv', 'quote_snapshot'],
          availableDataClasses: [],
          missingDataClasses: ['universe', 'historical_ohlcv', 'quote_snapshot'],
          blockedProductSurfaces: ['Scanner', 'Market Overview', 'Backtest'],
          consumerSafeMessage: '扫描标的池缺失，暂时无法生成候选。',
          consumerSafe: true,
        },
      },
    });

    renderUserScannerPage();

    const conclusion = await screen.findByTestId('scanner-conclusion-band');
    expect(conclusion).toHaveTextContent(/标的池缺失|Scope missing/);
    expect(conclusion).toHaveTextContent(/扫描标的池缺失|Scope/);
    expect(conclusion).not.toHaveTextContent(/标的池待更新|Scope stale/);
    expect(conclusion).not.toHaveTextContent(/universe|historical_ohlcv|quote_snapshot/i);
    expect(screen.queryByTestId(/^scanner-result-row-/)).not.toBeInTheDocument();
  });

  it('shows the operator data readiness link only for admin users with provider-read access', async () => {
    productSurfaceMock.state = {
      isAdminAccount: true,
      canReadProviders: true,
    };
    getRuns.mockResolvedValue(makeHistoryResponse([]));
    getRun.mockResolvedValue(null);
    getStatus.mockResolvedValue({
      market: 'cn',
      profile: 'cn_preopen_v1',
      watchlistDate: '2026-06-27',
      todayTradingDay: true,
      scheduleEnabled: false,
      scheduleRunImmediately: false,
      notificationEnabled: false,
      qualitySummary: {
        available: false,
        reviewWindowDays: 5,
        runCount: 0,
        reviewedRunCount: 0,
        reviewedCandidateCount: 0,
        strongCount: 0,
        mixedCount: 0,
        weakCount: 0,
      },
      dataReadiness: {
        state: 'blocked',
        market: 'cn',
        profile: 'cn_preopen_v1',
        blockerBucket: 'stale_universe',
        scannerUniverseReadiness: {
          contractVersion: 'scanner_universe_readiness_v1',
          status: 'stale',
          market: 'CN',
          universeSize: 10,
          requiredDataClasses: ['universe', 'historical_ohlcv', 'quote_snapshot'],
          availableDataClasses: ['universe'],
          missingDataClasses: ['historical_ohlcv', 'quote_snapshot'],
          blockedProductSurfaces: ['Scanner', 'Market Overview', 'Backtest'],
          consumerSafeMessage: '扫描标的池已过期，需要更新后再扫描。',
          consumerSafe: true,
        },
      },
    });

    renderUserScannerPage();

    const link = await screen.findByTestId('scanner-operator-readiness-link');
    await waitFor(() => {
      expect(link).toHaveAttribute('href', '/en/admin/market-providers');
    });
  });
});
