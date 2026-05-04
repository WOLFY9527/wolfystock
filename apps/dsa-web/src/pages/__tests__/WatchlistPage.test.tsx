import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import WatchlistPage from '../WatchlistPage';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import type { WatchlistItem } from '../../types/watchlist';
import type { RuleBacktestRunResponse } from '../../types/backtest';

const { listWatchlistItems, removeWatchlistItem, refreshScores, getRefreshStatus, runRuleBacktest, analyzeAsync, useProductSurfaceMock } = vi.hoisted(() => ({
  listWatchlistItems: vi.fn(),
  removeWatchlistItem: vi.fn(),
  refreshScores: vi.fn(),
  getRefreshStatus: vi.fn(),
  runRuleBacktest: vi.fn(),
  analyzeAsync: vi.fn(),
  useProductSurfaceMock: vi.fn(),
}));

vi.mock('../../api/watchlist', () => ({
  watchlistApi: {
    listWatchlistItems,
    addWatchlistItem: vi.fn(),
    removeWatchlistItem,
    refreshScores,
    getRefreshStatus,
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
  useProductSurface: () => useProductSurfaceMock(),
}));

vi.mock('../../components/auth/AuthGuardOverlay', () => ({
  AuthGuardOverlay: ({ moduleName }: { moduleName: string }) => <div>{`auth-guard:${moduleName}`}</div>,
}));

const writeTextMock = vi.fn();

function makeItem(overrides: Partial<WatchlistItem>): WatchlistItem {
  return {
    id: 1,
    symbol: 'NVDA',
    market: 'us',
    name: 'NVIDIA',
    source: 'scanner',
    scannerRunId: 42,
    scannerRank: 1,
    scannerScore: 94,
    lastScoredAt: '2026-05-01T12:30:00',
    scoreSource: 'scanner_run',
    scoreProfile: 'us_preopen_v1',
    scoreReason: 'Latest scanner score.',
    scoreStatus: 'fresh',
    scoreError: null,
    intelligence: {
      scanner: {
        lastScore: 94,
        lastRank: 1,
        status: 'selected',
        theme: 'ai-momentum',
        themeLabel: 'AI Momentum',
        profile: 'us_preopen_v1',
        reason: 'Latest scanner score.',
        lastScannedAt: '2026-05-01T12:30:00',
      },
      strategySimulation: {
        lookbackDays: 90,
        forwardDays: 5,
        avgForwardReturnPct: 3.2,
        hitRate: 0.56,
        avgExcessReturnPct: 2.1,
        selectionCount: 5,
        dataCoverage: 0.83,
        status: 'ready',
      },
      backtest: {
        lastResultId: 33,
        totalReturnPct: 24.6,
        maxDrawdownPct: -8.2,
        sharpe: 1.34,
        tradeCount: 6,
        testedAt: '2026-05-01T13:30:00',
      },
    },
    themeId: 'ai-momentum',
    universeType: 'theme',
    notes: null,
    createdAt: '2026-04-30T08:00:00',
    updatedAt: '2026-04-30T09:00:00',
    ...overrides,
  };
}

const watchlistItems: WatchlistItem[] = [
  makeItem({
    id: 1,
    symbol: 'NVDA',
    market: 'us',
    name: 'NVIDIA',
    scannerRunId: 42,
    scannerRank: 1,
    scannerScore: 94,
    themeId: 'ai-momentum',
    universeType: 'theme',
    createdAt: '2026-04-30T08:00:00',
    updatedAt: '2026-04-30T09:00:00',
  }),
  makeItem({
    id: 2,
    symbol: 'TSM',
    market: 'hk',
    name: 'TSMC',
    scannerRunId: 41,
    scannerRank: 3,
    scannerScore: 88,
    themeId: 'semis',
    universeType: 'theme',
    createdAt: '2026-04-25T08:00:00',
    updatedAt: '2026-04-25T09:00:00',
  }),
  makeItem({
    id: 3,
    symbol: '600519',
    market: 'cn',
    name: '贵州茅台',
    scannerRunId: 39,
    scannerRank: 8,
    scannerScore: 77,
    themeId: null,
    universeType: 'default',
    createdAt: '2026-04-10T08:00:00',
    updatedAt: '2026-04-10T09:00:00',
  }),
];

function makeRuleBacktestRun(overrides: Partial<RuleBacktestRunResponse> = {}): RuleBacktestRunResponse {
  return {
    id: 501,
    code: 'NVDA',
    strategyText: '观察列表单标的回测',
    parsedStrategy: {} as RuleBacktestRunResponse['parsedStrategy'],
    strategyHash: 'hash-501',
    timeframe: 'daily',
    startDate: '2025-05-03',
    endDate: '2026-05-03',
    periodStart: '2025-05-03',
    periodEnd: '2026-05-03',
    lookbackBars: 252,
    initialCapital: 100000,
    feeBps: 0,
    slippageBps: 0,
    parsedConfidence: 1,
    needsConfirmation: false,
    warnings: [],
    runAt: '2026-05-03T09:00:00Z',
    completedAt: '2026-05-03T09:01:00Z',
    status: 'completed',
    statusHistory: [],
    runTiming: {},
    runDiagnostics: {},
    noResultReason: null,
    noResultMessage: null,
    tradeCount: 4,
    winCount: 3,
    lossCount: 1,
    totalReturnPct: 12.4,
    annualizedReturnPct: 12.4,
    sharpeRatio: 1.1,
    benchmarkMode: 'auto',
    benchmarkCode: null,
    benchmarkReturnPct: null,
    excessReturnVsBenchmarkPct: null,
    buyAndHoldReturnPct: null,
    excessReturnVsBuyAndHoldPct: null,
    winRatePct: 75,
    avgTradeReturnPct: 2.1,
    maxDrawdownPct: -4.5,
    avgHoldingDays: 6,
    avgHoldingBars: 6,
    avgHoldingCalendarDays: 6,
    finalEquity: 112400,
    summary: {},
    dataQuality: {},
    robustnessAnalysis: {},
    artifactAvailability: {},
    readbackIntegrity: {},
    executionModel: {},
    executionAssumptions: {},
    executionAssumptionsSnapshot: {},
    benchmarkCurve: [],
    benchmarkSummary: {},
    buyAndHoldCurve: [],
    buyAndHoldSummary: {},
    auditRows: [],
    dailyReturnSeries: [],
    exposureCurve: [],
    aiSummary: null,
    equityCurve: [],
    trades: [],
    executionTrace: null,
    resultAuthority: {},
    ...overrides,
  };
}

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>;
}

function renderWatchlist(path = '/watchlist') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <UiLanguageProvider>
        <Routes>
          <Route path="/watchlist" element={<><WatchlistPage /><LocationProbe /></>} />
          <Route path="/zh" element={<><div>home</div><LocationProbe /></>} />
          <Route path="/zh/scanner" element={<div>scanner</div>} />
          <Route path="/zh/backtest" element={<div>backtest</div>} />
          <Route path="/zh/backtest/results/:runId" element={<div>backtest result</div>} />
          <Route path="/zh/login" element={<div>login</div>} />
        </Routes>
      </UiLanguageProvider>
    </MemoryRouter>,
  );
}

describe('WatchlistPage', () => {
  beforeEach(() => {
    vi.spyOn(Date, 'now').mockReturnValue(new Date('2026-05-01T12:00:00Z').getTime());
    vi.clearAllMocks();
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    listWatchlistItems.mockResolvedValue({ items: watchlistItems });
    removeWatchlistItem.mockResolvedValue({ deleted: 1 });
    refreshScores.mockResolvedValue({
      ok: true,
      updatedCount: 3,
      failedCount: 0,
      skippedCount: 0,
      startedAt: '2026-05-01T12:00:00Z',
      completedAt: '2026-05-01T12:00:01Z',
      markets: ['cn', 'hk', 'us'],
      results: [],
    });
    getRefreshStatus.mockResolvedValue({
      enabled: true,
      usTime: '08:45',
      cnTime: '09:00',
      hkTime: '09:00',
      maxSymbols: 250,
      running: false,
    });
    runRuleBacktest.mockResolvedValue(makeRuleBacktestRun());
    analyzeAsync.mockResolvedValue({ taskId: 'task-1' });
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: writeTextMock,
      },
    });
    writeTextMock.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders tracked candidates from the watchlist API', async () => {
    renderWatchlist();

    expect(await screen.findByTestId('watchlist-row-NVDA')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '观察列表' })).toBeInTheDocument();
    expect(screen.getByText('跟踪扫描候选，继续分析与回测')).toBeInTheDocument();
    expect(screen.queryByText(/Track scanner candidates/i)).not.toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-TSM')).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-600519')).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-filter-grid')).toHaveClass('min-w-0', 'grid-cols-1', 'md:grid-cols-2', 'xl:grid-cols-6');
    const marketSelect = screen.getByLabelText('市场');
    const contextSelect = screen.getByLabelText('主题 / 候选范围');
    expect(marketSelect).toHaveClass('select-surface', 'absolute', 'inset-0', 'opacity-0');
    expect(marketSelect.closest('.select-field__control')).toHaveClass('ui-control-shell', 'relative', 'min-w-0', 'w-full');
    expect(marketSelect.closest('.select-field__control')?.querySelector('.select-field__overlay')).toHaveAttribute('aria-hidden', 'true');
    expect(marketSelect.closest('.select-field__control')?.querySelector('.select-field__value')).toHaveTextContent('全部');
    expect(marketSelect.closest('.select-field__control')?.querySelector('.select-field__icon')).toHaveClass('ml-2', 'shrink-0');
    expect(contextSelect).toHaveClass('select-surface', 'absolute', 'inset-0', 'opacity-0');
    expect(contextSelect.closest('.select-field__control')).toHaveClass('ui-control-shell', 'relative', 'min-w-0', 'w-full');
    expect(contextSelect.closest('.select-field__control')?.querySelector('.select-field__overlay')).toHaveAttribute('aria-hidden', 'true');
    expect(contextSelect.closest('.select-field__control')?.querySelector('.select-field__value')).toHaveTextContent('全部');
    expect(listWatchlistItems).toHaveBeenCalledTimes(1);
  });

  it('shows intelligence coverage summary totals', async () => {
    renderWatchlist();

    await screen.findByTestId('watchlist-row-NVDA');
    expect(screen.getByText('观察标的数').nextElementSibling).toHaveTextContent('3');
    expect(screen.getByText('已有扫描结果').nextElementSibling).toHaveTextContent('3');
    expect(screen.getByText('已有回测结果').nextElementSibling).toHaveTextContent('3');
    expect(screen.getByText('情报过期').nextElementSibling).toHaveTextContent('0');
    expect(screen.getByText('失败 / 无数据').nextElementSibling).toHaveTextContent('0');
    expect(screen.getByText('最近更新时间').nextElementSibling).toHaveTextContent('05/01');
  });

  it('renders the intelligence command bar, coverage summary, and selected scope controls', async () => {
    renderWatchlist();
    const row = await screen.findByTestId('watchlist-row-NVDA');

    expect(screen.getByTestId('watchlist-command-bar')).toHaveTextContent('扫描当前筛选');
    expect(screen.getByTestId('watchlist-command-bar')).toHaveTextContent('回测当前筛选');
    expect(screen.getByRole('button', { name: '仅选中' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '清除选择' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '刷新情报' })).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-action-scope')).toHaveTextContent('当前筛选 3 个标的');
    expect(screen.getByText('观察标的数').nextElementSibling).toHaveTextContent('3');
    expect(screen.getByText('已有扫描结果').nextElementSibling).toHaveTextContent('3');
    expect(screen.getByText('已有回测结果').nextElementSibling).toHaveTextContent('3');
    expect(screen.getByText('情报过期').nextElementSibling).toHaveTextContent('0');
    expect(screen.getByText('失败 / 无数据').nextElementSibling).toHaveTextContent('0');
    expect(screen.getByText('最近更新时间').nextElementSibling).toHaveTextContent('05/01');

    fireEvent.click(within(row).getByRole('checkbox', { name: '选择 NVDA' }));

    expect(screen.getByRole('button', { name: '仅选中' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('watchlist-action-scope')).toHaveTextContent('已选中 1 个标的');
    expect(screen.getByRole('button', { name: '清除选择' })).not.toBeDisabled();
  });

  it('disables intelligence actions for an empty filtered set with a compact reason', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.change(screen.getByLabelText('搜索'), { target: { value: 'ZZZZ' } });

    expect(screen.getByTestId('watchlist-action-scope')).toHaveTextContent('当前筛选为空');
    expect(screen.getByRole('button', { name: /扫描当前筛选/ })).toBeDisabled();
    expect(screen.getByRole('button', { name: /回测当前筛选/ })).toBeDisabled();
    expect(screen.getByText('无匹配标的')).toBeInTheDocument();
  });

  it('filters rows by symbol or name search', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.change(screen.getByLabelText('搜索'), { target: { value: 'tsm' } });

    expect(screen.queryByTestId('watchlist-row-NVDA')).not.toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-TSM')).toBeInTheDocument();
  });

  it('filters rows by market', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.change(screen.getByLabelText('市场'), { target: { value: 'hk' } });

    expect(screen.queryByTestId('watchlist-row-NVDA')).not.toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-TSM')).toBeInTheDocument();
  });

  it('filters rows by source and theme or universe context', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.change(screen.getByLabelText('来源'), { target: { value: 'scanner' } });
    fireEvent.change(screen.getByLabelText('主题 / 候选范围'), { target: { value: 'theme:semis' } });

    expect(screen.queryByTestId('watchlist-row-NVDA')).not.toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-TSM')).toBeInTheDocument();
  });

  it('sorts rows by scanner score', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.change(screen.getByLabelText('排序'), { target: { value: 'scannerScore' } });

    const rows = Array.from(document.querySelectorAll('tbody tr'));
    expect(within(rows[0] as HTMLElement).getByText('NVDA')).toBeInTheDocument();
    expect(within(rows[1] as HTMLElement).getByText('TSM')).toBeInTheDocument();
    expect(within(rows[2] as HTMLElement).getByText('600519')).toBeInTheDocument();
  });

  it('renders compact scanner, strategy simulation, and backtest intelligence chips in Chinese', async () => {
    renderWatchlist();
    const row = await screen.findByTestId('watchlist-row-NVDA');

    expect(within(row).getByText('分数 94.0')).toBeInTheDocument();
    expect(within(row).getByText('已验证')).toBeInTheDocument();
    expect(within(row).getByText('排名 #1')).toBeInTheDocument();
    expect(within(row).getByText('Latest scanner score.')).toBeInTheDocument();
    expect(within(row).getAllByText('今日').length).toBeGreaterThan(0);
    expect(within(row).getByText(/HIST \+3.2% · HIT 56%/)).toBeInTheDocument();
    expect(within(row).getByText('已回测')).toBeInTheDocument();
    expect(within(row).getByText(/收益 \+24.6% · 回撤 -8.2% · Sharpe 1.34 · 交易 6/)).toBeInTheDocument();
    expect(within(row).getByRole('link', { name: /结果 33/ })).toHaveAttribute('href', '/zh/backtest/results/33');
  });

  it('maps raw scanner and backtest failure statuses to compact Chinese labels', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [
        makeItem({
          id: 9,
          symbol: 'MARA',
          scannerScore: null,
          scannerRank: null,
          lastScoredAt: null,
          scoreStatus: 'provider_down',
          scoreError: 'provider_down critical debug payload',
          intelligence: {
            scanner: {
              lastScore: null,
              lastRank: null,
              status: 'provider_error',
              reason: 'provider_down critical debug payload',
              lastScannedAt: null,
            },
            strategySimulation: { status: 'insufficient_history' },
            backtest: {
              lastResultId: null,
              totalReturnPct: null,
              maxDrawdownPct: null,
              sharpe: null,
              tradeCount: null,
              testedAt: null,
            },
          },
        }),
      ],
    });

    renderWatchlist();

    const row = await screen.findByTestId('watchlist-row-MARA');
    expect(within(row).getByText('扫描失败')).toBeInTheDocument();
    expect(within(row).getByText('样本不足')).toBeInTheDocument();
    expect(within(row).getByText('时间未知')).toBeInTheDocument();
    expect(within(row).getByText('服务暂不可用')).toBeInTheDocument();
    expect(row).not.toHaveTextContent(/provider_down|provider_error|unknown|critical|debug/i);
    expect(within(row).queryByText(/收益/)).not.toBeInTheDocument();
  });

  it('renders compact empty intelligence for old payloads without evidence', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [makeItem({
        id: 9,
        symbol: 'MARA',
        scannerRunId: null,
        scannerRank: null,
        scannerScore: null,
        scoreStatus: null,
        themeId: null,
        universeType: null,
        intelligence: undefined,
      })],
    });

    renderWatchlist();

    const row = await screen.findByTestId('watchlist-row-MARA');
    expect(within(row).getByText('暂无策略证据')).toBeInTheDocument();
  });

  it('sorts by backtest return and historical hit rate', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.change(screen.getByLabelText('排序'), { target: { value: 'backtestReturn' } });
    let rows = Array.from(document.querySelectorAll('tbody tr'));
    expect(within(rows[0] as HTMLElement).getByText('NVDA')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('排序'), { target: { value: 'historicalHitRate' } });
    rows = Array.from(document.querySelectorAll('tbody tr'));
    expect(within(rows[0] as HTMLElement).getByText('NVDA')).toBeInTheDocument();
  });

  it('filters rows with backtest evidence', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [
        makeItem({ id: 1, symbol: 'NVDA' }),
        makeItem({
          id: 4,
          symbol: 'MARA',
          scannerScore: 65,
          intelligence: {
            scanner: { lastScore: 65, status: 'selected' },
            strategySimulation: { status: 'unknown' },
            backtest: {},
          },
        }),
      ],
    });
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.change(screen.getByLabelText('证据筛选'), { target: { value: 'hasBacktest' } });

    expect(screen.getByTestId('watchlist-row-NVDA')).toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-row-MARA')).not.toBeInTheDocument();
  });

  it('runs batch backtest for the current filter, de-dupes duplicate clicks, and updates visible metrics', async () => {
    runRuleBacktest.mockImplementation(async ({ code }: { code: string }) => makeRuleBacktestRun({
      id: code === 'NVDA' ? 701 : 702,
      code,
      totalReturnPct: code === 'NVDA' ? 14.2 : 8.1,
      maxDrawdownPct: code === 'NVDA' ? -3.2 : -6.4,
      sharpeRatio: code === 'NVDA' ? 1.5 : 0.9,
      tradeCount: code === 'NVDA' ? 5 : 3,
    }));
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.change(screen.getByLabelText('市场'), { target: { value: 'us' } });
    const batchButton = screen.getByRole('button', { name: /回测当前筛选/ });
    fireEvent.click(batchButton);
    fireEvent.click(batchButton);

    await waitFor(() => expect(runRuleBacktest).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId('watchlist-batch-progress')).toHaveTextContent('1 / 1');
    expect(screen.getByTestId('watchlist-batch-progress')).toHaveTextContent('成功 1');
    expect(runRuleBacktest).toHaveBeenCalledWith(expect.objectContaining({
      code: 'NVDA',
      strategyText: '观察列表单标的回测',
      initialCapital: 100000,
      feeBps: 0,
      slippageBps: 0,
      benchmarkMode: 'auto',
      waitForCompletion: true,
    }));
    const row = await screen.findByTestId('watchlist-row-NVDA');
    expect(within(row).getByText(/收益 \+14.2% · 回撤 -3.2% · Sharpe 1.50 · 交易 5/)).toBeInTheDocument();
    expect(within(row).getByRole('link', { name: /结果 701/ })).toHaveAttribute('href', '/zh/backtest/results/701');
  });

  it('shows compact Chinese failure reasons during failed batch actions', async () => {
    runRuleBacktest.mockRejectedValue(new Error('provider_error timeout critical stack'));
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.change(screen.getByLabelText('市场'), { target: { value: 'us' } });
    fireEvent.click(screen.getByRole('button', { name: /回测当前筛选/ }));

    await waitFor(() => expect(screen.getByTestId('watchlist-batch-progress')).toHaveTextContent('失败 1'));
    const row = screen.getByTestId('watchlist-row-NVDA');
    expect(within(row).getByText('服务暂不可用')).toBeInTheDocument();
    expect(within(row).getByText('开发者细节')).toBeInTheDocument();
    expect(row).not.toHaveTextContent(/provider_error|critical|stack/i);
  });

  it('keeps the filter controls overflow-safe with long labels', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    const searchInput = screen.getByLabelText('搜索');
    expect(searchInput).toHaveClass('pr-12');
    expect(screen.getByTestId('watchlist-filter-grid').className).not.toContain('overflow-hidden');
  });

  it('starts analysis for a candidate and navigates to the workspace', async () => {
    renderWatchlist();
    const row = await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.click(within(row).getByRole('button', { name: /分析/ }));

    await waitFor(() => expect(analyzeAsync).toHaveBeenCalledWith(expect.objectContaining({
      stockCode: 'NVDA',
      reportType: 'detailed',
      stockName: 'NVIDIA',
      originalQuery: 'NVDA',
      selectionSource: 'manual',
    })));
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/zh?symbol=NVDA&task_id=task-1&source=watchlist&market=US'));
    expect(screen.getByText('home')).toBeInTheDocument();
  });

  it('renders score freshness and manually refreshes scores', async () => {
    const refreshedItems = [
      makeItem({
        id: 1,
        symbol: 'NVDA',
        scannerScore: 96,
        scannerRank: 1,
        lastScoredAt: '2026-05-01T13:00:00',
        scoreStatus: 'fresh',
      }),
    ];
    listWatchlistItems
      .mockResolvedValueOnce({ items: watchlistItems })
      .mockResolvedValueOnce({ items: refreshedItems });

    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    expect(screen.getByText('开盘前自动更新')).toBeInTheDocument();
    expect(screen.getAllByText('最新').length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: /刷新评分/ }));

    await waitFor(() => expect(refreshScores).toHaveBeenCalledWith({ force: true }));
    expect(await screen.findByText(/评分已刷新/)).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-NVDA')).toHaveTextContent('96.0');
  });

  it('links backtest with scanner and watchlist metadata', async () => {
    renderWatchlist();
    const row = await screen.findByTestId('watchlist-row-NVDA');

    const link = within(row).getByRole('link', { name: /回测/ });
    expect(link).toHaveAttribute('href', expect.stringContaining('/zh/backtest?'));
    expect(link).toHaveAttribute('href', expect.stringContaining('symbol=NVDA'));
    expect(link).toHaveAttribute('href', expect.stringContaining('source=scanner'));
    expect(link).toHaveAttribute('href', expect.stringContaining('origin=watchlist'));
    expect(link).toHaveAttribute('href', expect.stringContaining('watchlistItemId=1'));
    expect(link).toHaveAttribute('href', expect.stringContaining('scannerRunId=42'));
    expect(link).toHaveAttribute('href', expect.stringContaining('themeId=ai-momentum'));
  });

  it('removes a candidate through the delete API and drops the row', async () => {
    renderWatchlist();
    const row = await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.click(within(row).getByRole('button', { name: '移除 NVDA' }));

    await waitFor(() => expect(removeWatchlistItem).toHaveBeenCalledWith(1));
    expect(screen.queryByTestId('watchlist-row-NVDA')).not.toBeInTheDocument();
  });

  it('copies the symbol to the clipboard', async () => {
    renderWatchlist();
    const row = await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.click(within(row).getByRole('button', { name: '复制代码 NVDA' }));

    await waitFor(() => expect(writeTextMock).toHaveBeenCalledWith('NVDA'));
    expect(await screen.findByText('NVDA 已复制')).toBeInTheDocument();
  });

  it('renders an empty state with a scanner link', async () => {
    listWatchlistItems.mockResolvedValue({ items: [] });

    renderWatchlist();

    expect(await screen.findByText('暂无追踪候选。')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /打开扫描器/ })[1]).toHaveAttribute('href', '/zh/scanner');
  });

  it('renders the authentication guard for guests', () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: true });

    renderWatchlist();

    expect(screen.getByText('auth-guard:观察列表')).toBeInTheDocument();
    expect(listWatchlistItems).not.toHaveBeenCalled();
  });
});
