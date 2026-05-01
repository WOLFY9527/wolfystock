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

const { getRuns, getRun, getThemes, createTheme, runScan, analyzeAsync, listWatchlistItems, addWatchlistItem, removeWatchlistItem } = vi.hoisted(() => ({
  getRuns: vi.fn(),
  getRun: vi.fn(),
  getThemes: vi.fn(),
  createTheme: vi.fn(),
  runScan: vi.fn(),
  analyzeAsync: vi.fn(),
  listWatchlistItems: vi.fn(),
  addWatchlistItem: vi.fn(),
  removeWatchlistItem: vi.fn(),
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

function LanguageSwitch() {
  const { setLanguage } = useI18n();
  return (
    <button type="button" onClick={() => setLanguage('en')}>
      switch-language-en
    </button>
  );
}

function renderUserScannerPage(withLanguageSwitch = false) {
  return render(
    <UiLanguageProvider>
      <MemoryRouter initialEntries={['/scanner']}>
        {withLanguageSwitch ? <LanguageSwitch /> : null}
        <Routes>
          <Route path="/scanner" element={<UserScannerPage />} />
          <Route path="/" element={<div>Home Landing</div>} />
          <Route path="/:locale" element={<div>Home Landing</div>} />
          <Route path="/backtest" element={<div>Backtest Landing</div>} />
          <Route path="/:locale/backtest" element={<div>Backtest Landing</div>} />
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

describe('UserScannerPage', () => {
  beforeEach(() => {
    window.localStorage.clear();
    getRuns.mockReset();
    getRun.mockReset();
    getThemes.mockReset();
    createTheme.mockReset();
    runScan.mockReset();
    analyzeAsync.mockReset();
    listWatchlistItems.mockReset();
    addWatchlistItem.mockReset();
    removeWatchlistItem.mockReset();
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
    listWatchlistItems.mockResolvedValue({ items: [] });
    addWatchlistItem.mockResolvedValue(makeWatchlistItem());
    removeWatchlistItem.mockResolvedValue({ deleted: 1 });
  });

  it('renders scanner score without misleading AI score copy for normal scanner scores', async () => {
    renderUserScannerPage();

    expect(await screen.findByText('扫描评分 94/100')).toBeInTheDocument();
    expect(screen.getByText('扫描评分 88/100')).toBeInTheDocument();
    expect(screen.queryByText(/AI score|AI 评分/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Annualized return forecast|年化收益预测/)).not.toBeInTheDocument();
    expect(screen.getByText(/AI 解读 · gemini/)).toBeInTheDocument();
  });

  it('renders compact scanner workspace without the old decorative hero', async () => {
    renderUserScannerPage();

    expect(await screen.findByTestId('user-scanner-workspace')).toBeInTheDocument();
    expect(screen.getByTestId('scanner-sidebar')).toContainElement(screen.getByTestId('scanner-run-button'));
    expect(screen.getByTestId('scanner-candidate-scroll-region')).toBeInTheDocument();
    expect(screen.queryByText('TACTICAL ROUTER')).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /MARKET SCANNER|市场扫描/ })).not.toBeInTheDocument();
  });

  it('keeps diagnostics collapsed so results stay primary', async () => {
    renderUserScannerPage();

    const diagnostics = await screen.findByTestId('scanner-diagnostics-panel');
    expect(diagnostics).not.toHaveAttribute('open');
    expect(screen.queryByTestId('scanner-quality-strip')).not.toBeInTheDocument();
    expect(await screen.findByTestId('scanner-result-card-NVDA')).toBeInTheDocument();
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
    expect(within(table).getByText('建仓区间')).toBeInTheDocument();
    expect(within(table).getByText('目标价')).toBeInTheDocument();
    expect(within(table).getByText('止损位')).toBeInTheDocument();
    expect(within(table).getByText('关键原因')).toBeInTheDocument();
    expect(within(table).getByText('风险摘要')).toBeInTheDocument();
    expect(within(table).getByText('数据/来源')).toBeInTheDocument();
    expect(within(table).getByText('操作')).toBeInTheDocument();
    expect(within(table).getByText('Backend Broadcom Label')).toBeInTheDocument();
    expect(within(table).getByText('1420')).toBeInTheDocument();
  });

  it('renders analyze and copy actions on candidate cards', async () => {
    renderUserScannerPage();

    const card = await screen.findByTestId('scanner-result-card-NVDA');
    expect(within(card).getByRole('button', { name: /分析|Analyze/i })).toBeInTheDocument();
    expect(within(card).getByRole('button', { name: /复制|Copy/i })).toBeInTheDocument();
  });

  it('copies a single candidate symbol to the clipboard', async () => {
    renderUserScannerPage();

    const card = await screen.findByTestId('scanner-result-card-NVDA');
    fireEvent.click(within(card).getByRole('button', { name: /复制|Copy/i }));

    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalledWith('NVDA');
    });
  });

  it('copies all current result symbols from run-level actions', async () => {
    renderUserScannerPage();

    fireEvent.click(await screen.findByRole('button', { name: /复制全部代码|Copy all symbols/i }));

    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalledWith('NVDA, AVGO, AMD');
    });
  });

  it('exports csv with expected scanner result headers', async () => {
    renderUserScannerPage();

    fireEvent.click(await screen.findByRole('button', { name: /导出 CSV|Export CSV/i }));

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
    fireEvent.click(within(card).getByRole('button', { name: /分析|Analyze/i }));

    await waitFor(() => {
      expect(analyzeAsync).toHaveBeenCalledWith(expect.objectContaining({
        stockCode: 'NVDA',
        originalQuery: 'NVDA',
        selectionSource: 'manual',
      }));
    });
    expect(await screen.findByText('Home Landing')).toBeInTheDocument();
  });

  it('enables backtest action with scanner handoff query params for candidates with symbol', async () => {
    renderUserScannerPage();

    const card = await screen.findByTestId('scanner-result-card-NVDA');
    const backtestLink = within(card).getByRole('link', { name: /回测|Backtest/i });
    expect(backtestLink).toHaveAttribute(
      'href',
      '/zh/backtest?symbol=NVDA&source=scanner&scannerRunId=11&scannerRank=1&market=CN&scannerProfile=cn_preopen_v1&universeType=default',
    );
  });

  it('shows backtest action as disabled when the candidate symbol is missing', async () => {
    getRun.mockResolvedValueOnce(makeRunDetail({
      shortlist: [
        makeCandidate({ symbol: '', name: 'Unknown candidate', companyName: 'Unknown candidate' }),
      ],
    }));
    renderUserScannerPage();

    const card = await screen.findByTestId('scanner-result-card-no-symbol-1');
    const backtestButton = within(card).getByRole('button', { name: /回测|Backtest/i });
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
    expect(within(card).getByRole('link', { name: /回测|Backtest/i })).toBeInTheDocument();
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

    await screen.findByTestId('scanner-result-card-NVDA');
    fireEvent.click(screen.getAllByRole('button', { name: /详情|Detail/i })[0]);

    const detail = await screen.findByTestId('scanner-result-detail-NVDA');
    expect(within(detail).getByText('关键指标')).toBeInTheDocument();
    expect(within(detail).getByRole('button', { name: /分析|Analyze/i })).toBeInTheDocument();
    expect(within(detail).getByRole('button', { name: /复制代码|Copy symbol/i })).toBeInTheDocument();
    expect(within(detail).getByRole('button', { name: /导出该候选|Export candidate/i })).toBeInTheDocument();
    expect(within(detail).getByRole('link', { name: /回测|Backtest/i })).toHaveAttribute(
      'href',
      '/zh/backtest?symbol=NVDA&source=scanner&scannerRunId=11&scannerRank=1&market=CN&scannerProfile=cn_preopen_v1&universeType=default',
    );
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

    fireEvent.click(await screen.findByTestId('user-scanner-bento-drawer-trigger'));
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

    expect(await screen.findByText('当前无匹配的扫描结果')).toBeInTheDocument();
    expect(screen.getByText('请调整左侧参数或稍后再试')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('user-scanner-bento-drawer-trigger'));

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getAllByText('当前无匹配的扫描结果').length).toBeGreaterThan(0);
  });

  it('keeps existing run button behavior and market defaults', async () => {
    renderUserScannerPage(true);

    expect(await screen.findByRole('button', { name: '300 只' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'switch-language-en' }));

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: '300 只' })).not.toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: '300' })).toBeInTheDocument();

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
    const themedRun = makeRunDetail({
      market: 'us',
      profile: 'us_preopen_v1',
      profileLabel: 'US Pre-open Scanner v1',
      universeType: 'theme',
      themeId: 'crypto_miners',
      themeLabel: '加密矿企',
      requestedSymbolsCount: 3,
      acceptedSymbolsCount: 3,
      rejectedSymbols: [],
      universeNotes: ['Theme universe: 加密矿企 · 3 symbols.'],
      diagnostics: {
        universeSelection: {
          universeType: 'theme',
          themeId: 'crypto_miners',
          themeLabel: '加密矿企',
          requestedSymbolsCount: 3,
          acceptedSymbolsCount: 3,
          rejectedSymbols: [],
          universeNotes: ['Theme universe: 加密矿企 · 3 symbols.'],
        },
      },
    });
    runScan.mockResolvedValueOnce(themedRun);
    getRun.mockResolvedValue(themedRun);
    renderUserScannerPage();

    fireEvent.click(await screen.findByRole('button', { name: 'US' }));
    fireEvent.click(screen.getByRole('button', { name: /主题标的池|Theme universe/i }));
    expect(screen.getByTestId('scanner-theme-select')).toHaveTextContent(/AI 半导体|AI semiconductors/);
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
    expect((await screen.findAllByText(/加密矿企/)).length).toBeGreaterThan(0);
    expect(screen.getByText(/入选 3|3 selected/)).toBeInTheDocument();
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
    fireEvent.click(screen.getByRole('button', { name: /Theme universe|主题标的池/i }));
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

  it('shows disabled unconfigured themes and sends custom symbol universes', async () => {
    runScan.mockResolvedValueOnce(makeRunDetail({
      universeType: 'symbols',
      requestedSymbolsCount: 3,
      acceptedSymbolsCount: 3,
      rejectedSymbols: [],
      universeNotes: ['Custom symbol universe: 3 accepted.'],
    }));
    renderUserScannerPage();

    fireEvent.click(await screen.findByRole('button', { name: /主题标的池|Theme universe/i }));
    const themeSelect = screen.getByTestId('scanner-theme-select') as HTMLSelectElement;
    expect(within(themeSelect).getByRole('option', { name: /Optical modules \/ CPO.*not configured|光模块 CPO.*未配置/ })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: /自定义标的|Custom symbols/i }));
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

    expect(await screen.findByText('A 股全市场快照不可用。')).toBeInTheDocument();
    expect(screen.queryByText('Tesla')).not.toBeInTheDocument();
    expect(screen.queryByText('Meta')).not.toBeInTheDocument();
    expect(screen.queryByText('Apple')).not.toBeInTheDocument();
  });
});
