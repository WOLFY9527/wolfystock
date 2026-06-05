import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createApiError, createParsedApiError } from '../../api/error';
import UserScannerPage from '../UserScannerPage';
import { UiLanguageProvider, useI18n } from '../../contexts/UiLanguageContext';
import { expectNoRawI18nKeys } from '../../test-utils/i18nRawKeySentinel';
import type {
  ScannerCandidate,
  ScannerRunDetail,
  ScannerRunHistoryItem,
  ScannerRunHistoryResponse,
} from '../../types/scanner';
import type { WatchlistItem } from '../../types/watchlist';
import type { RuleBacktestRunResponse } from '../../types/backtest';

const {
  getRuns,
  getRun,
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

const writeTextMock = vi.fn();
const createObjectUrlMock = vi.fn(() => 'blob:scanner-export');
const revokeObjectUrlMock = vi.fn();
const anchorClickMock = vi.fn();

vi.mock('../../api/scanner', () => ({
  scannerApi: {
    getRuns,
    getRun,
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

  it('fetches scanner run history once on the initial zh narrow route load', async () => {
    renderUserScannerPage({ initialEntry: '/zh/scanner', viewportWidth: 390 });

    expect(await screen.findByTestId('scanner-result-row-NVDA')).toBeInTheDocument();
    await waitFor(() => {
      expect(getRun).toHaveBeenCalledWith(11);
    });
    expect(getRuns).toHaveBeenCalledTimes(1);
    expect(getRun).toHaveBeenCalledTimes(1);
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
    expect(container).not.toHaveTextContent(/买入|卖出|加仓|减仓|recommend(?:ation)?/i);
    expectNoRawI18nKeys(container);
  });

  it('renders a scanner conclusion band for the top candidate state', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

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

    expect(await screen.findByTestId('scanner-page-heading')).toHaveTextContent('US Pre-open Scanner');
    expect(screen.getByTestId('scanner-page-heading')).not.toHaveTextContent(/v1/);

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

  it('surfaces a compact scanner workflow from market drivers to focus evidence before ranked rows', async () => {
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

    expect(workflow).toHaveTextContent(/先看市场驱动|Start with market drivers/);
    expect(workflow).toHaveTextContent(/当前候选 NVDA|Focus candidate NVDA/);
    expect(workflow).toHaveTextContent(/仅观察/);
    expect(workflow).toHaveTextContent(/来源确认：含评分级/);
    expect(workflow).toHaveTextContent(/查看排名主表|Review ranked rows/);
    expect(workflow).toHaveTextContent(/94\/100/);
    expectElementBefore(topDown, workflow);
    expectElementBefore(workflow, rankedList);
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
    }));

    const { container } = renderUserScannerPage();

    const row = await screen.findByTestId('scanner-result-row-NVDA');
    const visualSummary = await screen.findByTestId('scanner-visual-evidence-summary');
    expect(visualSummary).toHaveTextContent(/视觉证据|Visual evidence/);
    expect(screen.getByTestId('scanner-visual-score-distribution')).toBeInTheDocument();
    expect(screen.getByTestId('scanner-visual-candidate-coverage')).toBeInTheDocument();
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
    expect(container).not.toHaveTextContent(/买入|卖出|下单|trade|broker|order/i);
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
    expect(screen.getByTestId('scanner-page-heading')).toHaveTextContent('A股盘前扫描');
    expect(screen.getByTestId('scanner-page-heading')).not.toHaveTextContent(/CN\s*·|v1/);
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
    expect(detail).toHaveTextContent('观察级线索');
    expect(detail).toHaveTextContent('延迟更新');
    expect(detail).toHaveTextContent('先补充基本面与新闻催化');
    expect(detail).not.toHaveTextContent(/debugRef|source_authority_router_rejected|missing_required_evidence|Top-down market context available/i);

    expect(within(row).getAllByText('94/100').length).toBeGreaterThan(0);
    expect(within(screen.getByTestId('scanner-result-row-AVGO')).getAllByText('88/100').length).toBeGreaterThan(0);
    expect(orderedSymbolsFromRows()).toEqual(['NVDA', 'AVGO', 'AMD']);
    expect(container).not.toHaveTextContent(/买入|卖出|下单|trade|broker|order/i);
    expectNoRawI18nKeys(container);
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
    expect(container).not.toHaveTextContent(/买入|卖出|下单|trade|broker|order/i);
    expectNoRawI18nKeys(container);
  });

  it('keeps legacy scanner responses rendering when candidate evidence fields are absent', async () => {
    const { container } = renderUserScannerPage();

    const row = await screen.findByTestId('scanner-result-row-NVDA');
    expect(within(row).getAllByText('94/100').length).toBeGreaterThan(0);
    expect(row).not.toHaveTextContent('待补');
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
    expect(container).not.toHaveTextContent(/cn_context_unavailable|provider|cache|router|sourceAuthority|buy|sell|order|trade|broker|买入|卖出|下单/i);
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
    expect(band).toHaveTextContent('本次无可用候选');
    expect(band).toHaveTextContent('候选 0');
    expect(band).toHaveTextContent('继续观察淘汰分布');
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

  it('replaces actiony scanner labels with observation and risk-boundary copy', async () => {
    const { container } = renderUserScannerPage();

    await screen.findByTestId('scanner-result-row-NVDA');
    expect(container).toHaveTextContent('观察区');
    expect(container).toHaveTextContent('参考区间');
    expect(container).toHaveTextContent('风险边界');
    expect(container).not.toHaveTextContent(/建仓|止损|before acting|执行操作|Entry|Target|Stop/i);
    expect(container).not.toHaveTextContent(/买入|卖出|加仓|减仓|buy|sell|recommend(?:ation)?/i);
  });

  it('renders compact scanner workspace without the old decorative hero', async () => {
    renderUserScannerPage();

    expect(await screen.findByTestId('user-scanner-workspace')).toBeInTheDocument();
    expect(screen.getByTestId('scanner-wide-workspace-scope')).toHaveAttribute('data-workspace-width', 'near-full');
    expect(screen.getByTestId('user-scanner-workspace')).toHaveAttribute('data-terminal-primitive', 'page-shell');
    expect(screen.getByTestId('scanner-page-heading')).toHaveAttribute('data-terminal-primitive', 'dense-page-header');
    expect(screen.getByTestId('scanner-status-strip')).toHaveAttribute('data-terminal-primitive', 'dense-status-strip');
    expect(screen.getByTestId('scanner-launch-bar')).toHaveAttribute('data-terminal-primitive', 'dense-table-shell');
    expect(screen.getByTestId('scanner-command-bar')).toHaveAttribute('data-terminal-primitive', 'dense-command-bar');
    expect(screen.getByTestId('scanner-launch-bar')).toHaveClass('border-y');
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

    const heading = await screen.findByRole('heading', { level: 1, name: '扫描器' });
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
    expect(within(rankedRow).getByRole('button', { name: /分析|Analyze/i })).toHaveAttribute('data-terminal-primitive', 'button');
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
    expect(status).toHaveTextContent(/Best candidate|最佳候选/);
    expect(status).toHaveTextContent(/Candidate mix|候选分布/);
    expect(status).toHaveTextContent(/Signal state|信号状态/);
    expect(screen.queryByTestId('scanner-diagnostics-panel')).not.toBeInTheDocument();
    expectElementBefore(status, candidates);
    expectElementBefore(table, screen.getByTestId('scanner-diagnostics-disclosure'));
    expectElementBefore(table, screen.getByTestId('scanner-run-comparison-strip'));
    expectElementBefore(table, screen.getByTestId('scanner-strategy-experiment'));
    expectElementBefore(candidates, screen.getByTestId('scanner-secondary-sections'));

    const diagnostics = screen.getByTestId('scanner-diagnostics-disclosure');
    expect(within(diagnostics).getByRole('button', { name: /展开.*(?:数据说明|Data notes)|Expand.*(?:数据说明|Data notes)/i })).toHaveAttribute('aria-expanded', 'false');
    expect(within(screen.getByTestId('scanner-run-comparison-strip')).getByRole('button', { name: /^(?:展开|Expand).*?(?:比较记录|Comparison records|Compare records)$/i })).toHaveAttribute('aria-expanded', 'false');
    expect(within(screen.getByTestId('scanner-strategy-experiment')).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i })).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(within(diagnostics).getByRole('button', { name: /展开.*(?:数据说明|Data notes)|Expand.*(?:数据说明|Data notes)/i }));
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

    expect(headerStrip).toContainElement(screen.getByTestId('scanner-status-strip'));
    expectElementBefore(headerStrip, screen.getByTestId('scanner-command-bar'));
    expect(compactFilterBar).toBeInTheDocument();
    expect(primaryWorkRegion).toContainElement(screen.getByTestId('scanner-ranked-list'));
    expect(primaryWorkRegion).toContainElement(screen.getByTestId('scanner-result-table'));
    expect(primaryWorkRegion).toContainElement(screen.getByTestId('scanner-candidate-scroll-region'));
    expect(screen.getByTestId('scanner-candidate-scroll-region')).toContainElement(screen.getByTestId('scanner-candidate-row-WULF'));
    expect(contextRail).toContainElement(screen.getByTestId('scanner-inline-detail-panel'));
    expect(contextRail).toContainElement(screen.getByTestId('scanner-candidate-inspector'));
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

    expect(within(secondaryDeck).getByText(/数据说明|Data notes/i)).toBeInTheDocument();
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
    ];

    defaultSurfaces.forEach((surface) => {
      expect(surface).not.toHaveTextContent(forbiddenDiagnosticText);
    });
    expect(screen.getByTestId('scanner-conclusion-band')).toHaveTextContent('部分结果使用最近一次可用数据。');
    expect(screen.queryByTestId('scanner-diagnostics-panel')).not.toBeInTheDocument();
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

    fireEvent.click(getActionButton(row, /详情|Detail/i));
    const detail = await screen.findByTestId('scanner-result-detail-WULF');
    expect(within(detail).queryByText('仅供观察')).not.toBeInTheDocument();
    expect(detail).not.toHaveTextContent(/provider_timeout|fallback|proxy|stale|source-confidence|sourceConfidence|provider|reasonCode|reasonFamilies/i);
    fireEvent.click(within(detail).getByRole('button', { name: /候选说明|Candidate notes/i }));
    expect(await within(detail).findByText(/关键指标|Key metrics/)).toBeInTheDocument();
    const secondary = await within(detail).findByTestId('scanner-result-detail-secondary-WULF');
    fireEvent.click(within(secondary).getByRole('button', { name: /展开.*次要说明|Expand.*Secondary notes|展开/i }));
    expect(within(detail).getByText('仅供观察')).toBeInTheDocument();
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
    fireEvent.click(within(diagnostics).getByRole('button', { name: /展开.*(?:数据说明|Data notes)|Expand.*(?:数据说明|Data notes)/i }));
    const summary = await screen.findByTestId('scanner-diagnostics-summary');
    fireEvent.click(within(summary).getByRole('button', { name: /淘汰分布|Rejection mix/i }));
    expect(await screen.findByTestId('scanner-rejection-aggregate')).toBeInTheDocument();
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
    expect(within(row).queryByRole('button', { name: /分析|Analyze/i })).not.toBeInTheDocument();
    fireEvent.click(getActionButton(row, /更多|More/i));
    const rankedRow = getRankedRow('NVDA');
    expect(within(rankedRow).getByRole('button', { name: /分析|Analyze/i })).toBeInTheDocument();
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

  it('analyze action triggers existing async analysis and routes to the home analysis surface', async () => {
    renderUserScannerPage();

    const card = await screen.findByTestId('scanner-result-row-NVDA');
    fireEvent.click(getActionButton(card, /详情|Detail/i));
    const detail = await screen.findByTestId('scanner-result-detail-NVDA');
    fireEvent.click(within(detail).getByRole('button', { name: /分析|Analyze/i }));

    await waitFor(() => {
      expect(analyzeAsync).toHaveBeenCalledWith(expect.objectContaining({
        stockCode: 'NVDA',
        originalQuery: 'NVDA',
        selectionSource: 'manual',
      }));
    });
    expect(await screen.findByText('Home Landing')).toBeInTheDocument();
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
    expect(within(detail).getByRole('button', { name: /分析|Analyze/i })).toBeInTheDocument();
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

  it('keeps empty states clear when history and results are empty', async () => {
    getRuns.mockResolvedValue(makeHistoryResponse([]));

    const { container } = renderUserScannerPage({ viewportWidth: 1800 });

    expect(await screen.findByTestId('scanner-status-strip')).toHaveTextContent(/等待|Waiting/);
    expect(await screen.findByTestId('scanner-workbench-empty-state')).toHaveTextContent('尚未运行扫描');
    expect(screen.getByTestId('scanner-workbench-empty-state')).toHaveTextContent(/顶部命令栏.*市场.*范围.*评估深度.*候选上限/);
    expect(screen.getByTestId('scanner-workbench-empty-state')).toHaveTextContent(/打开历史/);
    expect(screen.queryByTestId('scanner-candidate-scroll-region')).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-context-rail')).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-detail-rail')).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-inline-detail-panel')).not.toBeInTheDocument();
    expect(screen.getByTestId('scanner-workbench-detail-layout')).toHaveClass('grid-cols-1');
    expect(container).not.toHaveTextContent(/买入|卖出|加仓|减仓|buy|sell|recommend(?:ation)?/i);

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

    const emptyState = await screen.findByTestId('scanner-workbench-empty-state');
    expect(screen.getByTestId('scanner-empty-history-fallback')).toBeInTheDocument();
    expect(emptyState).toHaveTextContent(/本次无入选候选|尚未运行扫描/);
    expect(emptyState).toHaveTextContent(/切换候选视图到候选池或全部|先在顶部命令栏确认市场、范围、评估深度与候选上限/);
    expect(emptyState).toHaveTextContent(/查看淘汰与数据受限行|如需已有结果可打开历史记录/);
    expect(emptyState).toHaveTextContent(/顶部命令栏.*候选上限.*范围.*评估深度/);
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

    const emptyState = await screen.findByTestId('scanner-workbench-empty-state');
    expect(emptyState).toHaveTextContent(/数据受限或证据不足|尚未运行扫描/);
    expect(emptyState).toHaveTextContent(/切换候选视图到数据受限|先在顶部命令栏确认市场、范围、评估深度与候选上限/);
    expect(emptyState).toHaveTextContent(/查看行级说明|如需已有结果可打开历史记录/);
    expect(emptyState).toHaveTextContent(/稍后重试或打开历史/);
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

    fireEvent.click(await screen.findByRole('button', { name: /美股|US/ }));
    fireEvent.click(within(screen.getByTestId('scanner-scope-selector')).getByRole('button', { name: /主题标的池|Theme universe/i }));
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

  it('batch backtests preview selected, top five, and current filtered candidate sets', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    const previewRender = renderUserScannerPage();

    const experiment = await screen.findByTestId('scanner-strategy-experiment');
    fireEvent.click(within(experiment).getByRole('button', { name: /展开.*(?:回测准备|Backtest setup)|Expand.*(?:回测准备|Backtest setup)/i }));
    const lab = await screen.findByTestId('scanner-backtest-lab');
    fireEvent.click(within(lab).getByRole('button', { name: /回测预览入选|Preview selected/i }));
    await waitFor(() => {
      expect(runRuleBacktest.mock.calls.map((call) => call[0].code)).toEqual(['WULF', 'MARA', 'RIOT']);
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
      expect(runRuleBacktest.mock.calls.map((call) => call[0].code)).toEqual(['WULF', 'MARA', 'RIOT', 'CIFR', 'HIVE']);
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
      expect(runRuleBacktest.mock.calls.map((call) => call[0].code)).toEqual(['WULF', 'MARA', 'RIOT', 'CIFR', 'HIVE']);
    });
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
    expect(screen.getByTestId('scanner-run-comparison-compact')).toHaveTextContent(/候选减少|最佳候选变化|分数变化|候选变化|Candidates|Best changed|Score|Candidate/);

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

  it('adds official and preview candidates through batch watchlist actions with duplicate accounting', async () => {
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
      expect(addWatchlistItem).toHaveBeenCalledWith(expect.objectContaining({ symbol: 'MARA', market: 'us' }));
      expect(addWatchlistItem).toHaveBeenCalledWith(expect.objectContaining({ symbol: 'RIOT', market: 'us' }));
    });
    expect(await screen.findByText(/已加入 2 个 · 已存在 1 个|Added 2 · already existed 1/i)).toBeInTheDocument();
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
    expect(screen.getByTestId('scanner-launch-controls')).toHaveTextContent(/候选上限.*评估深度|Universe cap.*Detailed review/i);
    fireEvent.click(within(screen.getByTestId('scanner-scope-selector')).getByRole('button', { name: /主题标的池|Theme universe/i }));
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
    fireEvent.click(within(screen.getByTestId('scanner-scope-selector')).getByRole('button', { name: /Theme universe|主题标的池/i }));
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

    expect(await screen.findByText(/运行前请输入一个或多个标的代码|Enter one or more symbols before running/i)).toBeInTheDocument();
    expect(runScan).not.toHaveBeenCalled();
  });

  it('shows field-level validation for AI theme generation before sending requests', async () => {
    renderUserScannerPage();

    fireEvent.click(within(screen.getByTestId('scanner-scope-selector')).getByRole('button', { name: /主题标的池|Theme universe/i }));
    await openAdvancedControls();
    fireEvent.change(screen.getByTestId('scanner-ai-theme-label-input'), { target: { value: 'A' } });
    fireEvent.change(screen.getByTestId('scanner-ai-theme-prompt-input'), { target: { value: 'too short' } });
    fireEvent.click(screen.getByRole('button', { name: /Generate theme|生成主题/i }));

    expect(await screen.findByText(/主题名称至少需要 2 个字符|Theme name must be at least 2 characters/i)).toBeInTheDocument();
    expect(screen.getByText(/筛选条件至少需要 12 个字符|Criteria must be at least 12 characters/i)).toBeInTheDocument();
    expect(createTheme).not.toHaveBeenCalled();
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

    fireEvent.click(within(screen.getByTestId('scanner-scope-selector')).getByRole('button', { name: /主题标的池|Theme universe/i }));
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
    runScan.mockRejectedValueOnce({
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

    renderUserScannerPage();

    fireEvent.click(await screen.findByRole('button', { name: /启动扫描|运行扫描|run scanner/i }));

    expect(await screen.findByTestId('scanner-page-error-summary')).toHaveTextContent(/数据不足|Insufficient data/);
    expect(screen.queryByText('A 股全市场快照不可用。')).not.toBeInTheDocument();
    expect(within(screen.getByTestId('scanner-page-error-summary')).queryByRole('button', { name: /开发者细节|Developer details/i })).not.toBeInTheDocument();
    expect(screen.getByTestId('scanner-page-error-summary')).toHaveTextContent(/数据不足|Insufficient data/);
    expect(screen.queryByText('Tesla')).not.toBeInTheDocument();
    expect(screen.queryByText('Meta')).not.toBeInTheDocument();
    expect(screen.queryByText('Apple')).not.toBeInTheDocument();
  });
});
