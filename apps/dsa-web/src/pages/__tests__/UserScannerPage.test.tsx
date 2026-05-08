import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createApiError, createParsedApiError } from '../../api/error';
import UserScannerPage from '../UserScannerPage';
import { UiLanguageProvider, useI18n } from '../../contexts/UiLanguageContext';
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
      makeCandidate({ symbol: 'WULF', name: 'TeraWulf', companyName: 'TeraWulf', rank: 1, score: 60 }),
    ],
    selected: [
      makeCandidate({ symbol: 'WULF', name: 'TeraWulf', companyName: 'TeraWulf', rank: 1, score: 60 }),
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

async function openMoreActions() {
  const more = await screen.findByTestId('scanner-more-actions');
  const trigger = within(more).getByRole('button', { name: /更多|More/i });
  if (trigger.getAttribute('aria-expanded') !== 'true') {
    fireEvent.click(trigger);
  }
  return more;
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

    expect(await screen.findByTestId('scanner-result-card-NVDA')).toBeInTheDocument();
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

    expect(await screen.findByTestId('scanner-result-card-NVDA')).toBeInTheDocument();
    await waitFor(() => {
      expect(getRun).toHaveBeenCalledWith(11);
    });
    expect(getRuns).toHaveBeenCalledTimes(1);
    expect(getRun).toHaveBeenCalledTimes(1);
  });

  it('renders scanner score without misleading AI score copy for normal scanner scores', async () => {
    renderUserScannerPage();

    expect(await screen.findByText('扫描评分 94/100')).toBeInTheDocument();
    expect(screen.getByText('扫描评分 88/100')).toBeInTheDocument();
    expect(screen.queryByText(/AI score|AI 评分/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Annualized return forecast|年化收益预测/)).not.toBeInTheDocument();
    expect(screen.getByText(/AI 解读可用/)).toBeInTheDocument();
  });

  it('renders compact scanner workspace without the old decorative hero', async () => {
    renderUserScannerPage();

    expect(await screen.findByTestId('user-scanner-workspace')).toBeInTheDocument();
    expect(screen.getByTestId('scanner-sidebar')).toContainElement(screen.getByTestId('scanner-run-button'));
    expect(screen.getByTestId('scanner-candidate-scroll-region')).toBeInTheDocument();
    expect(screen.queryByText('TACTICAL ROUTER')).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /MARKET SCANNER|市场扫描/ })).not.toBeInTheDocument();
  });

  it('loads scanner run history once on initial route entry', async () => {
    renderUserScannerPage();

    expect(await screen.findByTestId('scanner-result-card-NVDA')).toBeInTheDocument();
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

  it('keeps scanner page wrappers scroll-safe for natural document scrolling', async () => {
    renderUserScannerPage();

    await screen.findByTestId('scanner-run-button');

    expect(screen.getByTestId('user-scanner-bento-page')).not.toHaveClass('xl:overflow-hidden', 'xl:h-[calc(100vh-96px)]');
    expect(screen.getByTestId('user-scanner-workspace')).not.toHaveClass('h-full', 'overflow-hidden');
    expect(screen.getByTestId('scanner-results-pane')).not.toHaveClass('overflow-hidden', 'xl:min-h-0');
    const sidebar = screen.getByTestId('scanner-sidebar');
    expect(sidebar).not.toHaveClass('overflow-hidden', 'max-h-[calc(100vh-120px)]', 'xl:h-full', 'xl:max-h-[calc(100vh-120px)]');
    expect(screen.getByTestId('scanner-sidebar-scroll-region')).not.toHaveClass('overflow-y-auto');
    expect(screen.getByTestId('scanner-candidate-scroll-region')).not.toHaveClass('overflow-y-auto', 'flex-1');

    fireEvent.click(screen.getByRole('button', { name: /表格视图|Table view/i }));
    expect(screen.getByTestId('scanner-result-table')).toHaveClass('overflow-x-auto', 'no-scrollbar');
  });

  it('keeps launch evidence and selected candidates ahead of diagnostics by default', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    const summary = await screen.findByTestId('scanner-launch-evidence-summary');
    const candidates = screen.getByTestId('scanner-candidate-scroll-region');
    expect(summary).toHaveTextContent(/证据置信|Evidence confidence/);
    expect(summary).toHaveTextContent(/数据就绪|Data readiness/);
    expect(summary).toHaveTextContent(/下一步观察|Next observation/);
    expect(screen.queryByTestId('scanner-diagnostics-panel')).not.toBeInTheDocument();
    expect(summary.compareDocumentPosition(candidates) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    const diagnostics = screen.getByTestId('scanner-diagnostics-disclosure');
    expect(diagnostics).not.toHaveAttribute('open');
    fireEvent.click(within(diagnostics).getByRole('button', { name: /展开.*诊断详情|Expand.*Diagnostic details/i }));
    expect(await screen.findByTestId('scanner-diagnostics-panel')).toBeInTheDocument();
  });

  it('reveals rejection reasons from the diagnostics disclosure', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    expect(screen.queryByTestId('scanner-rejection-aggregate')).not.toBeInTheDocument();

    const diagnostics = await screen.findByTestId('scanner-diagnostics-disclosure');
    fireEvent.click(within(diagnostics).getByRole('button', { name: /展开.*诊断详情|Expand.*Diagnostic details/i }));
    const summary = await screen.findByTestId('scanner-diagnostics-summary');
    fireEvent.click(within(summary).getByRole('button', { name: /查看淘汰原因|View rejection reasons/i }));
    expect(await screen.findByTestId('scanner-rejection-aggregate')).toBeInTheDocument();
  });

  it('toggles between card and table view', async () => {
    renderUserScannerPage();

    expect(await screen.findByTestId('scanner-result-card-NVDA')).toBeInTheDocument();
    expect(screen.queryByTestId('scanner-result-table')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /表格视图|Table view/i }));

    expect(screen.getByTestId('scanner-result-table')).toBeInTheDocument();
    expect(screen.queryByTestId('scanner-result-card-NVDA')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /卡片视图|Card view/i }));

    expect(screen.getByTestId('scanner-result-card-NVDA')).toBeInTheDocument();
  });

  it('renders table columns from existing candidate fields', async () => {
    renderUserScannerPage();

    fireEvent.click(await screen.findByRole('button', { name: /表格视图|Table view/i }));

    const table = screen.getByTestId('scanner-result-table');
    expect(within(table).getByText('排名')).toBeInTheDocument();
    expect(within(table).getByText('代码')).toBeInTheDocument();
    expect(within(table).getByText('名称')).toBeInTheDocument();
    expect(within(table).getByText('扫描评分')).toBeInTheDocument();
    expect(within(table).getByText('观察区间')).toBeInTheDocument();
    expect(within(table).getByText('上方观察')).toBeInTheDocument();
    expect(within(table).getByText('风险边界')).toBeInTheDocument();
    expect(within(table).getByText('关键原因')).toBeInTheDocument();
    expect(within(table).getByText('风险摘要')).toBeInTheDocument();
    expect(within(table).getByText('数据/来源')).toBeInTheDocument();
    expect(within(table).getByText('操作')).toBeInTheDocument();
    expect(within(table).getByText('Backend Broadcom Label')).toBeInTheDocument();
    expect(within(table).getByText('1420')).toBeInTheDocument();
  });

  it('renders observation-first actions on candidate cards', async () => {
    renderUserScannerPage();

    const card = await screen.findByTestId('scanner-result-card-NVDA');
    expect(within(card).getByRole('button', { name: /查看证据|View evidence/i })).toBeInTheDocument();
    expect(within(card).getByRole('button', { name: /追踪|Track/i })).toBeInTheDocument();
    expect(within(card).queryByRole('button', { name: /分析|Analyze/i })).not.toBeInTheDocument();
    expect(within(card).queryByRole('button', { name: /复制|Copy/i })).not.toBeInTheDocument();
  });

  it('copies a single candidate symbol to the clipboard', async () => {
    renderUserScannerPage();

    const card = await screen.findByTestId('scanner-result-card-NVDA');
    fireEvent.click(within(card).getByRole('button', { name: /查看证据|View evidence/i }));
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
    expect(exportText).toContain('rank,symbol,name,scannerScore,entryRange,target,stop,reason,risk,universeType,theme,generatedAt,runId');
    expect(exportText).toContain('1,NVDA');
  });

  it('analyze action triggers existing async analysis and routes to the home analysis surface', async () => {
    renderUserScannerPage();

    const card = await screen.findByTestId('scanner-result-card-NVDA');
    fireEvent.click(within(card).getByRole('button', { name: /查看证据|View evidence/i }));
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

    const card = await screen.findByTestId('scanner-result-card-NVDA');
    fireEvent.click(within(card).getByRole('button', { name: /查看证据|View evidence/i }));
    expect(within(await screen.findByTestId('scanner-result-detail-NVDA')).getByRole('button', { name: /回测|Backtest/i })).toBeEnabled();
  });

  it('shows backtest action as disabled when the candidate symbol is missing', async () => {
    getRun.mockResolvedValueOnce(makeRunDetail({
      shortlist: [
        makeCandidate({ symbol: '', name: 'Unknown candidate', companyName: 'Unknown candidate' }),
      ],
    }));
    renderUserScannerPage();

    const card = await screen.findByTestId('scanner-result-card-no-symbol-1');
    fireEvent.click(within(card).getByRole('button', { name: /查看证据|View evidence/i }));
    const backtestButton = within(await screen.findByTestId('scanner-result-detail-no-symbol-1')).getByRole('button', { name: /回测|Backtest/i });
    expect(backtestButton).toBeDisabled();
    expect(backtestButton).toHaveAttribute('title', expect.stringMatching(/requires a candidate symbol|候选标的代码/i));
  });

  it('renders scanner watchlist tracking actions and tracked state', async () => {
    listWatchlistItems.mockResolvedValueOnce({
      items: [makeWatchlistItem()],
    });
    renderUserScannerPage();

    const card = await screen.findByTestId('scanner-result-card-NVDA');
    expect(within(card).getAllByText(/Tracked|已追踪/).length).toBeGreaterThan(0);
    expect(within(card).getByRole('button', { name: /Tracked|已追踪/ })).toBeDisabled();
    expect(within(card).queryByRole('button', { name: /回测|Backtest/i })).not.toBeInTheDocument();
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

    const card = await screen.findByTestId('scanner-result-card-AVGO');
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

    const card = await screen.findByTestId('scanner-result-card-NVDA');
    fireEvent.click(within(card).getByRole('button', { name: /Track|追踪/i }));

    expect(await screen.findByText(/Sign in to save candidates to your watchlist|请登录后再保存候选到你的观察名单/)).toBeInTheDocument();
  });

  it('sorts frontend-only by scanner score and symbol', async () => {
    renderUserScannerPage();

    fireEvent.click(await screen.findByRole('button', { name: /表格视图|Table view/i }));

    expect(orderedSymbolsFromRows()).toEqual(['NVDA', 'AVGO', 'AMD']);
    const getRunsCallsBeforeSort = getRuns.mock.calls.length;
    const getRunCallsBeforeSort = getRun.mock.calls.length;

    fireEvent.click(screen.getAllByRole('button', { name: /代码|symbol/i }).at(-1) as HTMLElement);
    expect(orderedSymbolsFromRows()).toEqual(['AMD', 'AVGO', 'NVDA']);

    fireEvent.click(screen.getByRole('button', { name: /扫描评分|scanner score/i }));
    expect(orderedSymbolsFromRows()).toEqual(['NVDA', 'AVGO', 'AMD']);

    expect(getRuns).toHaveBeenCalledTimes(getRunsCallsBeforeSort);
    expect(getRun).toHaveBeenCalledTimes(getRunCallsBeforeSort);
  });

  it('expands result detail with metrics, signals, risks, notes, outcome, and provider data', async () => {
    renderUserScannerPage();

    const nvdaCard = await screen.findByTestId('scanner-result-card-NVDA');
    fireEvent.click(within(nvdaCard).getByRole('button', { name: /详情|Detail/i }));

    const detail = await screen.findByTestId('scanner-result-detail-NVDA');
    expect(within(detail).getByText('关键指标')).toBeInTheDocument();
    expect(within(detail).getByRole('button', { name: /分析|Analyze/i })).toBeInTheDocument();
    expect(within(detail).getByRole('button', { name: /复制代码|Copy symbol/i })).toBeInTheDocument();
    expect(within(detail).getByRole('button', { name: /导出该候选|Export candidate/i })).toBeInTheDocument();
    expect(within(detail).getByRole('button', { name: /回测|Backtest/i })).toBeEnabled();
    expect(within(detail).getByText('Turnover')).toBeInTheDocument();
    expect(within(detail).getByText('Momentum expansion')).toBeInTheDocument();
    expect(within(detail).getByText('Backend risk: gap fade below support.')).toBeInTheDocument();
    expect(within(detail).getByText(/Backend scoring note/)).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('scanner-result-card-AVGO').querySelector('button') as HTMLElement);
    const avgoDetail = await screen.findByTestId('scanner-result-detail-AVGO');
    expect(within(avgoDetail).getByText('Backend AI interpretation summary.')).toBeInTheDocument();
    expect(within(avgoDetail).getByText('strong')).toBeInTheDocument();
    expect(within(avgoDetail).getByText('SPY')).toBeInTheDocument();
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

    const moreActions = await screen.findByTestId('scanner-more-actions');
    fireEvent.click(within(moreActions).getByText(/更多|More/i));
    fireEvent.click(within(moreActions).getByTestId('user-scanner-bento-drawer-trigger'));
    fireEvent.click(await screen.findByText('历史扫描'));

    expect(await screen.findByText('Historical Backend Label')).toBeInTheDocument();
    expect(screen.getByText('Historical replay backend reason.')).toBeInTheDocument();
    expect(getRun).toHaveBeenCalledWith(22);
  });

  it('does not let hardcoded symbol context override backend-provided values', async () => {
    renderUserScannerPage();

    expect(await screen.findByText('Backend Broadcom Label')).toBeInTheDocument();
    expect(screen.getByText('Backend AVGO reason wins.')).toBeInTheDocument();
    expect(screen.queryByText('Broadcom Inc.')).not.toBeInTheDocument();
    expect(screen.queryByText('AI 算力基建')).not.toBeInTheDocument();
  });

  it('keeps empty states clear when history and results are empty', async () => {
    getRuns.mockResolvedValue(makeHistoryResponse([]));

    renderUserScannerPage();

    expect(await screen.findByTestId('scanner-launch-evidence-summary')).toHaveTextContent(/等待扫描|Waiting for scan/);
    expect(await screen.findByText('当前无匹配的扫描结果')).toBeInTheDocument();
    expect(screen.getByText('请调整左侧参数或稍后再试')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('user-scanner-bento-drawer-trigger'));

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getAllByText('当前无匹配的扫描结果').length).toBeGreaterThan(0);
  });

  it('keeps existing run button behavior and market defaults', async () => {
    renderUserScannerPage(true);

    let advanced = await openAdvancedControls();
    expect(await within(advanced).findByRole('button', { name: '300 只' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'switch-language-en' }));

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: '300 只' })).not.toBeInTheDocument();
    });
    advanced = await openAdvancedControls();
    expect(within(advanced).getByRole('button', { name: '300' })).toBeInTheDocument();

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

    fireEvent.click(await screen.findByRole('button', { name: 'US' }));
    const advanced = await openAdvancedControls();
    fireEvent.click(within(advanced).getByRole('button', { name: /主题标的池|Theme universe/i }));
    const themeSelect = screen.getByTestId('scanner-theme-select');
    expect(themeSelect).toHaveTextContent(/AI 半导体|AI semiconductors/);
    expect(themeSelect).toHaveClass('select-surface', 'absolute', 'inset-0', 'opacity-0');
    expect(themeSelect.closest('.select-field__control')).toHaveClass('ui-control-shell', 'relative', 'min-w-0', 'w-full');
    expect(themeSelect.closest('.select-field__control')?.querySelector('.select-field__overlay')).toHaveAttribute('aria-hidden', 'true');
    expect(themeSelect.closest('.select-field__control')?.querySelector('.select-field__value')).toHaveTextContent(/加密矿企|Crypto miners/);
    expect(themeSelect.closest('.select-field__control')?.querySelector('.select-field__icon')).toHaveClass('ml-2', 'shrink-0');
    fireEvent.change(screen.getByTestId('scanner-theme-select'), { target: { value: 'crypto_miners' } });
    fireEvent.click(screen.getByRole('button', { name: /运行扫描|Run scanner/i }));

    await waitFor(() => {
      expect(runScan).toHaveBeenCalledWith(expect.objectContaining({
        market: 'us',
        profile: 'us_preopen_v1',
        universeType: 'theme',
        themeId: 'crypto_miners',
      }));
    });
    expect(screen.getAllByText(/入选 1|1 selected/).length).toBeGreaterThan(0);
    expect(screen.getByTestId('scanner-diagnostic-summary')).toHaveTextContent(/候选范围|UNIVERSE/);
    expect(screen.getByTestId('scanner-diagnostic-summary')).toHaveTextContent(/11/);
    expect(screen.getByTestId('scanner-diagnostic-summary')).toHaveTextContent(/已评估|EVALUATED/);
    expect(screen.getByTestId('scanner-diagnostic-summary')).toHaveTextContent(/9/);
    expect(screen.getByTestId('scanner-diagnostic-summary')).toHaveTextContent(/数据失败|DATA FAILED/);
    expect(screen.getByTestId('scanner-diagnostic-summary')).toHaveTextContent(/跳过|SKIPPED/);
    expect(screen.getByTestId('scanner-summary-counters')).toHaveTextContent(/SELECTED/);
    expect(screen.getByTestId('scanner-summary-counters')).toHaveTextContent(/REJECTED/);
    expect(screen.getByTestId('scanner-decision-summary')).toHaveTextContent(/本次扫描：1 个入选 \/ 9 个评估|Scan: 1 selected \/ 9 evaluated/);
    expect(screen.getByTestId('scanner-decision-summary')).toHaveTextContent(/最佳候选：WULF · 60\/100|Best candidate: WULF · 60\/100/);
    expect(screen.getByTestId('scanner-decision-summary')).toHaveTextContent(/主要淘汰原因：流动性不足|Main rejection: Liquidity weak/);
    expect(screen.getByTestId('scanner-decision-summary')).toHaveTextContent(/数据状态：2 个数据失败|Data status: 2 data failed/);
    expect(screen.getByTestId('scanner-result-card-WULF')).toBeInTheDocument();
    expect(screen.getByTestId('scanner-candidate-preview')).toHaveTextContent(/其余 10 个候选未入选|10 other candidates were not selected/);
    expect(screen.getByTestId('scanner-candidate-preview')).toHaveTextContent(/MARA/);

    fireEvent.click(screen.getByRole('button', { name: /查看全部候选|View all candidates/i }));
    expect(await screen.findByTestId('scanner-candidate-row-WULF')).toHaveTextContent(/官方|Official/);
    expect(screen.getByTestId('scanner-candidate-row-WULF')).toHaveTextContent(/通过筛选|Passed screening/);
    expect(screen.getByTestId('scanner-candidate-row-WULF')).toHaveTextContent(/已验证|Verified/);
    expect(screen.getByTestId('scanner-candidate-row-MARA')).toHaveTextContent(/流动性不足|Liquidity weak/);
    expect(screen.getByTestId('scanner-candidate-row-RIOT')).toHaveTextContent(/价格低于阈值|Price below threshold/);
    expect(screen.getByTestId('scanner-candidate-row-CIFR')).toHaveTextContent(/数据不足|Data thin/);
  });

  it('keeps advanced scanner actions out of the default top toolbar and available in disclosure', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    const actions = await screen.findByTestId('scanner-primary-actions');
    expect(within(actions).getByRole('button', { name: /查看 WULF|View WULF/i })).toBeInTheDocument();
    expect(within(actions).getByRole('button', { name: /更多|More/i })).toBeInTheDocument();
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
    expect(within(more).getByRole('button', { name: /历史扫描回放|Historical replay/i })).toBeInTheDocument();
  });

  it('keeps strategy experiment collapsed by default and exposes Backtest Lab inside it', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    const experiment = await screen.findByTestId('scanner-strategy-experiment');
    expect(experiment).not.toHaveAttribute('open');
    expect(within(experiment).getByRole('button', { name: /展开.*策略实验区|Expand.*Strategy experiment/i })).toHaveTextContent(/展开|Expand/i);
    expect(screen.queryByTestId('scanner-backtest-lab')).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-strategy-simulation')).not.toBeInTheDocument();

    fireEvent.click(within(experiment).getByRole('button', { name: /展开.*策略实验区|Expand.*Strategy experiment/i }));
    expect(within(experiment).getByRole('button', { name: /收起.*策略实验区|Collapse.*Strategy experiment/i })).toHaveTextContent(/收起|Collapse/i);
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
    fireEvent.click(within(experiment).getByRole('button', { name: /展开.*策略实验区|Expand.*Strategy experiment/i }));
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
    fireEvent.click(within(experiment).getByRole('button', { name: /展开.*策略实验区|Expand.*Strategy experiment/i }));
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
    fireEvent.click(within(loadingExperiment).getByRole('button', { name: /展开.*策略实验区|Expand.*Strategy experiment/i }));
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
    fireEvent.click(within(insufficientExperiment).getByRole('button', { name: /展开.*策略实验区|Expand.*Strategy experiment/i }));
    const insufficientPanel = await screen.findByTestId('scanner-strategy-simulation');
    fireEvent.click(within(insufficientPanel).getByRole('button', { name: /运行模拟|Run sim/i }));
    expect(await within(insufficientPanel).findByTestId('scanner-strategy-simulation-compact-message')).toHaveTextContent(/历史扫描不足/);
    expect(within(insufficientPanel).queryByTestId('scanner-strategy-simulation-runs')).not.toBeInTheDocument();

    insufficientRender.unmount();
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();
    const readyExperiment = await screen.findByTestId('scanner-strategy-experiment');
    fireEvent.click(within(readyExperiment).getByRole('button', { name: /展开.*策略实验区|Expand.*Strategy experiment/i }));
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
    fireEvent.click(within(experiment).getByRole('button', { name: /展开.*策略实验区|Expand.*Strategy experiment/i }));
    const panel = await screen.findByTestId('scanner-strategy-simulation');
    fireEvent.click(within(panel).getByRole('button', { name: /运行模拟|Run sim/i }));

    const runsTable = await within(panel).findByTestId('scanner-strategy-simulation-runs');
    expect(runsTable).toHaveClass('overflow-x-auto', 'no-scrollbar');
    expect(screen.getByTestId('scanner-candidate-filters').firstElementChild).toHaveClass('ui-scroll-x-quiet');
  });

  it('runs an individual scanner candidate backtest and links to the shared result report', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    const card = await screen.findByTestId('scanner-result-card-WULF');
    fireEvent.click(within(card).getByRole('button', { name: /查看证据|View evidence/i }));
    const detail = await screen.findByTestId('scanner-result-detail-WULF');
    fireEvent.click(within(detail).getByRole('button', { name: /回测|Backtest/i }));

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
    expect(within(detail).getByRole('link', { name: /查看报告|Report/i })).toHaveAttribute('href', expect.stringMatching(/\/(zh|en)\/backtest\/results\/27/));
  });

  it('batch backtests official selected symbols only and prevents duplicate clicks', async () => {
    getRun.mockResolvedValue(makeCryptoDiagnosticsRun());
    renderUserScannerPage();

    const experiment = await screen.findByTestId('scanner-strategy-experiment');
    fireEvent.click(within(experiment).getByRole('button', { name: /展开.*策略实验区|Expand.*Strategy experiment/i }));
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
    fireEvent.click(within(experiment).getByRole('button', { name: /展开.*策略实验区|Expand.*Strategy experiment/i }));
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
    fireEvent.click(within(topExperiment).getByRole('button', { name: /展开.*策略实验区|Expand.*Strategy experiment/i }));
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
    fireEvent.click(within(filteredExperiment).getByRole('button', { name: /展开.*策略实验区|Expand.*Strategy experiment/i }));
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
    fireEvent.click(within(experiment).getByRole('button', { name: /展开.*策略实验区|Expand.*Strategy experiment/i }));
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
    fireEvent.click(within(experiment).getByRole('button', { name: /展开.*策略实验区|Expand.*Strategy experiment/i }));
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

    const wulfCard = await screen.findByTestId('scanner-result-card-WULF');
    expect(wulfCard).toHaveTextContent(/官方|Official/);
    expect(wulfCard).toHaveTextContent('WULF');
    expect(screen.getByTestId('scanner-preview-added-list')).toHaveTextContent('MARA');
    expect(screen.getByTestId('scanner-preview-added-list')).toHaveTextContent('RIOT');

    fireEvent.click(screen.getByRole('button', { name: /候选池|Candidate pool/i }));
    expect(await screen.findByTestId('scanner-candidate-row-MARA')).toHaveTextContent(/预览|Preview/);
    expect(screen.getByTestId('scanner-candidate-row-CIFR')).toHaveTextContent(/数据失败|Data failed/);
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

  it('updates inspector from preview rows and shows official versus preview status', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    fireEvent.click(await screen.findByTestId('scanner-preview-added-MARA'));

    await waitFor(() => {
      const inspector = screen.getByTestId('scanner-candidate-inspector');
      expect(inspector).toHaveTextContent('MARA');
      expect(inspector).toHaveTextContent(/官方淘汰|Official rejected/);
      expect(inspector).toHaveTextContent(/阈值 50 预览入选|Threshold 50 preview selected/);
    });
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
    fireEvent.click(within(comparison).getByRole('button', { name: /展开.*历史对比|Expand.*History comparison/i }));
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
    expect(comparison).not.toHaveAttribute('open');
    fireEvent.click(within(comparison).getByRole('button', { name: /展开.*历史对比|Expand.*History comparison/i }));
    expect(comparison).toHaveTextContent(/暂无上次扫描对比|No previous comparable run/);
    expect(screen.getByTestId('scanner-previous-empty-state')).toHaveTextContent(/暂无历史扫描|No previous scan/);
  });

  it('maps scanner failure and no-data states to compact Chinese labels without raw provider enums by default', async () => {
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

    const summary = await screen.findByTestId('scanner-launch-evidence-summary');
    expect(summary).toHaveTextContent(/失败|Failed/);
    expect(summary).toHaveTextContent(/数据源异常|Provider issue/);
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
    expect(screen.getByTestId('scanner-candidate-inspector')).toHaveTextContent('MARA');

    const riotRow = screen.getByTestId('scanner-candidate-row-RIOT');
    fireEvent.click(within(riotRow).getByRole('button', { name: /更多|More/i }));
    fireEvent.click(await within(riotRow).findByRole('button', { name: /复制|Copy/i }));

    expect(screen.getByTestId('scanner-candidate-inspector')).toHaveTextContent('MARA');
  });

  it('keeps candidate rows to one primary action plus more actions', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    fireEvent.click(await screen.findByRole('button', { name: /候选池|Candidate pool/i }));
    const maraRow = await screen.findByTestId('scanner-candidate-row-MARA');
    expect(within(maraRow).getAllByRole('button').map((button) => button.textContent)).toEqual(
      expect.arrayContaining([expect.stringMatching(/分析|Analyze|查看|View/), expect.stringMatching(/更多|More/)]),
    );
    expect(within(maraRow).queryByRole('button', { name: /回测|Backtest/i })).not.toBeInTheDocument();

    fireEvent.click(within(maraRow).getByRole('button', { name: /更多|More/i }));
    expect(await within(maraRow).findByRole('button', { name: /回测|Backtest/i })).toBeInTheDocument();
    expect(within(maraRow).getByRole('button', { name: /复制|Copy/i })).toBeInTheDocument();
  });

  it('keeps strategy controls and batch actions available in the narrow/mobile structure', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    expect(await screen.findByTestId('scanner-primary-actions')).toHaveClass('grid');
    expect(screen.queryByTestId('scanner-strategy-preview')).not.toBeInTheDocument();
    expect(screen.queryByTestId('scanner-batch-actions')).not.toBeInTheDocument();
    expect(screen.getByTestId('scanner-strategy-experiment')).not.toHaveAttribute('open');
    expect(screen.getByTestId('scanner-candidate-filters').firstElementChild).toHaveClass('ui-scroll-x-quiet');
    expect(screen.getByTestId('scanner-mobile-candidate-inspector')).toBeInTheDocument();
  });

  it('keeps the theme select overflow-safe', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    expect(await screen.findByText(/基础扫描|Basic scan/i)).toBeInTheDocument();
    expect(await screen.findByText(/高级参数|Advanced controls/i)).toBeInTheDocument();
    expect(screen.getByTestId('scanner-advanced-controls')).toHaveTextContent(/候选上限.*评估深度.*扫描范围|Candidate size.*evaluation depth.*scan scope/i);
    const advanced = await openAdvancedControls();
    fireEvent.click(within(advanced).getByRole('button', { name: /主题标的池|Theme universe/i }));
    const themeSelect = await screen.findByTestId('scanner-theme-select');
    expect(themeSelect).toHaveClass('absolute', 'inset-0', 'opacity-0');
    expect(themeSelect.closest('.select-field__control')?.querySelector('.select-field__value')).toHaveClass('min-w-0', 'flex-1', 'truncate');
  });

  it('updates the candidate inspector from selected, rejected, and data-failed rows', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    expect(await screen.findByTestId('scanner-result-card-WULF')).toBeInTheDocument();
    const selectedInspector = await screen.findByTestId('scanner-candidate-inspector');
    expect(selectedInspector).toHaveTextContent('WULF');
    expect(selectedInspector).toHaveTextContent(/入选|Selected/);
    expect(selectedInspector).toHaveTextContent('60/100');
    expect(selectedInspector).toHaveTextContent(/Alpaca/);
    expect(selectedInspector).toHaveTextContent(/为什么入选|Why selected/);
    expect(selectedInspector).toHaveTextContent(/通过当前筛选条件|Passed current screening/);
    expect(selectedInspector).not.toHaveTextContent(/^passed$/);
    expect(selectedInspector).toHaveTextContent(/主要风险|Main risks/);
    expect(selectedInspector).toHaveTextContent(/评分不算强信号|Score is not a strong signal/);
    expect(selectedInspector).toHaveTextContent(/本次只有 1 个候选，样本偏窄|Only one selected candidate/);
    expect(selectedInspector).toHaveTextContent(/下一步观察|Next observation/);

    fireEvent.click(screen.getByRole('button', { name: /候选池|Candidate pool/i }));
    fireEvent.click(await screen.findByTestId('scanner-candidate-row-MARA'));

    expect(await screen.findByTestId('scanner-candidate-inspector')).toHaveTextContent('MARA');
    expect(screen.getByTestId('scanner-candidate-inspector')).toHaveTextContent(/淘汰|Rejected/);
    expect(screen.getByTestId('scanner-candidate-inspector')).toHaveTextContent('55/100');
    expect(screen.getByTestId('scanner-candidate-inspector')).toHaveTextContent(/流动性不足|Liquidity weak/);

    fireEvent.click(screen.getByRole('button', { name: /数据失败|Data failed/i }));
    fireEvent.click(await screen.findByTestId('scanner-candidate-row-CIFR'));

    expect(await screen.findByTestId('scanner-candidate-inspector')).toHaveTextContent('CIFR');
    expect(screen.getByTestId('scanner-candidate-inspector')).toHaveTextContent(/数据失败|Data failed/);
    expect(screen.getByTestId('scanner-candidate-inspector')).toHaveTextContent(/数据不足|Data thin/);
    expect(screen.getByTestId('scanner-mobile-candidate-inspector')).toBeInTheDocument();
  });

  it('keeps inspector secondary diagnostics collapsed and expandable', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    const inspector = await screen.findByTestId('scanner-candidate-inspector');
    expect(within(inspector).getByRole('button', { name: /展开.*规则诊断|Expand.*Rule diagnostics/i })).toBeInTheDocument();
    expect(within(inspector).getByRole('button', { name: /展开.*数据质量|Expand.*Data quality/i })).toBeInTheDocument();
    expect(within(inspector).getByRole('button', { name: /展开.*开发者字段|Expand.*Developer fields/i })).toBeInTheDocument();

    fireEvent.click(within(inspector).getByRole('button', { name: /展开.*规则诊断|Expand.*Rule diagnostics/i }));
    expect(within(inspector).getAllByText(/passed/i).length).toBeGreaterThan(0);
    fireEvent.click(within(inspector).getByRole('button', { name: /展开.*数据质量|Expand.*Data quality/i }));
    expect(within(inspector).getAllByText(/Alpaca/).length).toBeGreaterThan(0);
  });

  it('filters scanner diagnostics by rejected and data-failed candidates', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    expect(await screen.findByTestId('scanner-result-card-WULF')).toBeInTheDocument();
    expect(screen.queryByTestId('scanner-candidate-row-MARA')).not.toBeInTheDocument();
    expect(screen.getByText(/其余 10 个候选未入选|10 other candidates were not selected/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /淘汰|Rejected/i }));
    expect(await screen.findByTestId('scanner-candidate-row-MARA')).toHaveTextContent(/流动性不足|Liquidity weak/);
    expect(screen.getByTestId('scanner-candidate-row-RIOT')).toHaveTextContent(/价格低于阈值|Price below threshold/);
    expect(screen.queryByTestId('scanner-candidate-row-CIFR')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /数据失败|Data failed/i }));
    expect(await screen.findByTestId('scanner-candidate-row-CIFR')).toHaveTextContent(/数据不足|Data thin/);
    expect(screen.getByTestId('scanner-candidate-row-HIVE')).toHaveTextContent(/实时缺失|Realtime missing/);
    expect(screen.queryByTestId('scanner-candidate-row-MARA')).not.toBeInTheDocument();
  });

  it('expands candidate diagnostics details with failed rules, missing fields, provider, and metrics', async () => {
    const themedRun = makeCryptoDiagnosticsRun();
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    fireEvent.click(await screen.findByRole('button', { name: /候选池|Candidate pool/i }));
    const cifrRow = await screen.findByTestId('scanner-candidate-row-CIFR');
    fireEvent.click(within(cifrRow).getByText('CIFR'));

    const detail = await screen.findByTestId('scanner-candidate-detail-CIFR');
    expect(within(detail).getByText('not_enough_history')).toBeInTheDocument();
    expect(within(detail).getByText('history')).toBeInTheDocument();
    expect(within(detail).getByText(/来源|Provider/)).toBeInTheDocument();
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

    expect(await screen.findByTestId('scanner-result-card-NVDA')).toBeInTheDocument();
    expect(screen.queryByTestId('scanner-candidate-filters')).not.toBeInTheDocument();
    expect(screen.getByTestId('scanner-decision-summary')).toHaveTextContent(/扫描完成|Scan completed/);
    expect(screen.queryByTestId('scanner-candidate-inspector')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /表格视图|Table view/i }));
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

    fireEvent.click(await screen.findByRole('button', { name: 'US' }));
    const advanced = await openAdvancedControls();
    fireEvent.click(within(advanced).getByRole('button', { name: /Theme universe|主题标的池/i }));
    fireEvent.change(screen.getByTestId('scanner-ai-theme-label-input'), { target: { value: 'White House Stocks' } });
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

    fireEvent.click(screen.getByRole('button', { name: /运行扫描|Run scanner/i }));
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

    const advanced = await openAdvancedControls();
    fireEvent.click(within(advanced).getByRole('button', { name: /自定义标的|Custom symbols/i }));
    fireEvent.click(screen.getByRole('button', { name: /运行扫描|Run scanner/i }));

    expect(await screen.findByText(/运行前请输入一个或多个标的代码|Enter one or more symbols before running/i)).toBeInTheDocument();
    expect(runScan).not.toHaveBeenCalled();
  });

  it('shows field-level validation for AI theme generation before sending requests', async () => {
    renderUserScannerPage();

    const advanced = await openAdvancedControls();
    fireEvent.click(within(advanced).getByRole('button', { name: /主题标的池|Theme universe/i }));
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

    const advanced = await openAdvancedControls();
    fireEvent.click(within(advanced).getByRole('button', { name: /主题标的池|Theme universe/i }));
    const themeSelect = screen.getByTestId('scanner-theme-select') as HTMLSelectElement;
    expect(within(themeSelect).getByRole('option', { name: /Optical modules \/ CPO.*not configured|光模块 CPO.*未配置/ })).toBeDisabled();

    fireEvent.click(within(advanced).getByRole('button', { name: /自定义标的|Custom symbols/i }));
    fireEvent.change(screen.getByTestId('scanner-custom-symbols-input'), {
      target: { value: 'MARA RIOT\nCLSK' },
    });
    expect(screen.getByText(/已解析 3|Parsed 3/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /运行扫描|Run scanner/i }));

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

    fireEvent.click(await screen.findByRole('button', { name: /run scanner|运行扫描/i }));

    expect(await screen.findByTestId('scanner-page-error-summary')).toHaveTextContent(/数据不足|Insufficient data/);
    expect(screen.queryByText('A 股全市场快照不可用。')).not.toBeInTheDocument();
    fireEvent.click(within(screen.getByTestId('scanner-page-error-summary')).getByRole('button', { name: /展开.*开发者细节|Expand.*Developer details/i }));
    expect(await screen.findByText('A 股全市场快照不可用。')).toBeInTheDocument();
    expect(screen.queryByText('Tesla')).not.toBeInTheDocument();
    expect(screen.queryByText('Meta')).not.toBeInTheDocument();
    expect(screen.queryByText('Apple')).not.toBeInTheDocument();
  });
});
