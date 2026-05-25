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
          <Route path="/zh/scanner" element={<><div>scanner</div><LocationProbe /></>} />
          <Route path="/zh/backtest" element={<><div>backtest</div><LocationProbe /></>} />
          <Route path="/zh/backtest/results/:runId" element={<><div>backtest result</div><LocationProbe /></>} />
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
    expect(screen.queryByText('紧凑观察队列')).not.toBeInTheDocument();
    expect(screen.queryByText(/Track scanner candidates/i)).not.toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-TSM')).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-600519')).toBeInTheDocument();
    expect(screen.queryByText('Details')).not.toBeInTheDocument();
    expect(screen.getByTestId('watchlist-primary-filters')).toHaveClass('grid', 'grid-cols-2');
    const marketSelect = screen.getByLabelText('市场');
    expect(marketSelect).toHaveClass('select-surface', 'absolute', 'inset-0', 'opacity-0');
    expect(marketSelect.closest('.select-field__control')).toHaveClass('ui-control-shell', 'relative', 'min-w-0', 'w-full');
    expect(marketSelect.closest('.select-field__control')?.querySelector('.select-field__overlay')).toHaveAttribute('aria-hidden', 'true');
    expect(marketSelect.closest('.select-field__control')?.querySelector('.select-field__value')).toHaveTextContent('全部');
    expect(marketSelect.closest('.select-field__control')?.querySelector('.select-field__icon')).toHaveClass('ml-2', 'shrink-0');
    expect(screen.getByRole('button', { name: '高级筛选' })).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(screen.getByRole('button', { name: '高级筛选' }));
    const contextSelect = screen.getByLabelText('主题 / 候选范围');
    expect(contextSelect).toHaveClass('select-surface', 'absolute', 'inset-0', 'opacity-0');
    expect(contextSelect.closest('.select-field__control')).toHaveClass('ui-control-shell', 'relative', 'min-w-0', 'w-full');
    expect(contextSelect.closest('.select-field__control')?.querySelector('.select-field__overlay')).toHaveAttribute('aria-hidden', 'true');
    expect(contextSelect.closest('.select-field__control')?.querySelector('.select-field__value')).toHaveTextContent('全部');
    expect(listWatchlistItems).toHaveBeenCalledTimes(1);
  });

  it('uses terminal primitives for the page shell, command actions, and row status material', async () => {
    renderWatchlist();

    const row = await screen.findByTestId('watchlist-row-NVDA');
    const wideScope = screen.getByTestId('watchlist-wide-workspace-scope');
    expect(wideScope).toHaveAttribute('data-workspace-width', 'near-full');
    expect(wideScope).toHaveClass('workspace-width-near-full', 'overflow-x-hidden');
    expect(wideScope).toContainElement(screen.getByTestId('watchlist-page'));
    expect(screen.getByTestId('watchlist-page')).toHaveAttribute('data-terminal-primitive', 'page-shell');
    expect(screen.getByTestId('watchlist-header-strip')).toHaveAttribute('data-layout-zone', 'HeaderStrip');
    expect(document.querySelector('[data-terminal-primitive="dense-page-header"]')).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-status-strip')).toHaveAttribute('data-terminal-primitive', 'dense-status-strip');
    expect(screen.getByTestId('watchlist-watch-board')).toHaveAttribute('data-terminal-primitive', 'dense-table-shell');
    expect(screen.getByTestId('watchlist-compact-filter-bar')).toHaveAttribute('data-linear-primitive', 'compact-filter-bar');
    expect(screen.getByTestId('watchlist-compact-filter-bar')).toHaveAttribute('data-layout-zone', 'CommandBar');
    expect(screen.getByTestId('watchlist-command-bar')).toHaveAttribute('data-terminal-primitive', 'dense-command-bar');
    expect(screen.getByTestId('watchlist-candidate-list')).toHaveAttribute('data-linear-primitive', 'dense-rows');
    expect(screen.getByTestId('watchlist-primary-work-region')).toHaveAttribute('data-layout-zone', 'PrimaryWorkRegion');
    expect(screen.getByTestId('watchlist-detail-rail')).toHaveAttribute('data-linear-primitive', 'context-rail');
    expect(screen.getByTestId('watchlist-detail-rail')).toHaveAttribute('data-layout-zone', 'ContextRail');
    expect(screen.getByTestId('watchlist-secondary-deck')).toHaveAttribute('data-layout-zone', 'SecondaryDeck');
    expect(screen.getByTestId('watchlist-command-bar').querySelectorAll('[data-terminal-primitive="button"]')).toHaveLength(6);
    expect(row.querySelectorAll('[data-terminal-primitive="chip"]').length).toBeGreaterThan(0);
  });

  it('shows intelligence coverage in a compact status strip instead of metric cards', async () => {
    renderWatchlist();

    await screen.findByTestId('watchlist-row-NVDA');
    const statusStrip = screen.getByTestId('watchlist-status-strip');
    expect(statusStrip.querySelectorAll('[data-terminal-primitive="metric"]')).toHaveLength(0);
    expect(within(statusStrip).getByText('观察标的数').nextElementSibling).toHaveTextContent('3');
    expect(within(statusStrip).getByText('已有扫描结果').nextElementSibling).toHaveTextContent('3');
    expect(within(statusStrip).getByText('已有回测结果').nextElementSibling).toHaveTextContent('3');
    expect(within(statusStrip).getByText('最近可用').nextElementSibling).toHaveTextContent('0');
    expect(within(statusStrip).getByText('暂不可用').nextElementSibling).toHaveTextContent('0');
    expect(within(statusStrip).getByText('最近更新时间').nextElementSibling).toHaveTextContent('05/01');
  });

  it('renders the watchlist conclusion band with consumer-safe freshness and confidence summary', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [
        makeItem({
          id: 1,
          symbol: 'NVDA',
          scannerScore: 94,
          scoreStatus: 'fresh',
          scoreSource: 'scanner_run',
        }),
        makeItem({
          id: 2,
          symbol: 'BABA',
          scannerScore: 81,
          scoreStatus: 'stale',
          scoreSource: 'proxy_fallback',
          intelligence: {
            scanner: { lastScore: 81, status: 'selected', reason: 'Fallback score snapshot.', lastScannedAt: '2026-04-20T12:30:00Z' },
            strategySimulation: { status: 'unknown' },
            backtest: {},
          },
        }),
        makeItem({
          id: 3,
          symbol: 'SHOP',
          source: '',
          scannerRunId: null,
          scannerRank: null,
          scannerScore: null,
          lastScoredAt: null,
          scoreSource: null,
          scoreStatus: null,
          intelligence: undefined,
        }),
      ],
    });

    renderWatchlist();

    const band = await screen.findByTestId('watchlist-conclusion-band');
    expect(band).toHaveTextContent('当前焦点 NVDA');
    expect(band).toHaveTextContent('最新 1');
    expect(band).toHaveTextContent('最近可用 1');
    expect(band).toHaveTextContent('更新中 1');
    expect(band).toHaveTextContent('置信度低 1');
    expect(band).toHaveTextContent('当前信号置信度较低，仅供观察。');
    expect(band).not.toHaveTextContent(/fallback|proxy|备用\/代理|备用数据|代理证据|reasonFamilies|sourceAuthorityAllowed|scoreContributionAllowed/i);
    expect(band).not.toHaveTextContent(/买入|卖出|加仓|减仓|buy|sell|recommend(?:ation)?/i);
  });

  it('renders a watchlist conclusion band needs-refresh state when no fresh item is available', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [
        makeItem({
          id: 12,
          symbol: 'BABA',
          scannerScore: 81,
          scoreStatus: 'stale',
          scoreSource: 'proxy_fallback',
          intelligence: {
            scanner: { lastScore: 81, status: 'selected', reason: 'Fallback score snapshot.', lastScannedAt: '2026-04-20T12:30:00Z' },
            strategySimulation: { status: 'unknown' },
            backtest: {},
          },
        }),
        makeItem({
          id: 13,
          symbol: 'SHOP',
          source: '',
          scannerRunId: null,
          scannerRank: null,
          scannerScore: null,
          lastScoredAt: null,
          scoreSource: null,
          scoreStatus: null,
          intelligence: undefined,
        }),
      ],
    });

    renderWatchlist();

    const band = await screen.findByTestId('watchlist-conclusion-band');
    expect(band).toHaveTextContent('数据更新中');
    expect(band).toHaveTextContent('最新 0');
    expect(band).toHaveTextContent('最近可用 1');
    expect(band).toHaveTextContent('更新中 1');
    expect(band).toHaveTextContent('部分项目需要刷新后再参考。');
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
    const statusStrip = screen.getByTestId('watchlist-status-strip');
    expect(within(statusStrip).getByText('观察标的数').nextElementSibling).toHaveTextContent('3');
    expect(within(statusStrip).getByText('已有扫描结果').nextElementSibling).toHaveTextContent('3');
    expect(within(statusStrip).getByText('已有回测结果').nextElementSibling).toHaveTextContent('3');
    expect(within(statusStrip).getByText('最近可用').nextElementSibling).toHaveTextContent('0');
    expect(within(statusStrip).getByText('暂不可用').nextElementSibling).toHaveTextContent('0');
    expect(within(statusStrip).getByText('最近更新时间').nextElementSibling).toHaveTextContent('05/01');

    fireEvent.click(within(row).getByRole('checkbox', { name: '选择 NVDA' }));

    expect(screen.getByRole('button', { name: '仅选中' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('watchlist-action-scope')).toHaveTextContent('已选中 1 个标的');
    expect(screen.getByRole('button', { name: '清除选择' })).not.toBeDisabled();
  });

  it('keeps a compact filter bar above the board and batch actions in a secondary deck', async () => {
    renderWatchlist();
    const rows = await screen.findByTestId('watchlist-candidate-list');
    const shell = screen.getByTestId('watchlist-page');
    const watchBoard = screen.getByTestId('watchlist-watch-board');
    const compactFilterBar = screen.getByTestId('watchlist-compact-filter-bar');
    const primaryWorkRegion = screen.getByTestId('watchlist-primary-work-region');
    const commandBar = screen.getByTestId('watchlist-command-bar');
    const boardShell = screen.getByTestId('watchlist-board-shell');
    const detailRail = screen.getByTestId('watchlist-detail-rail');
    const secondaryDeck = screen.getByTestId('watchlist-secondary-deck');

    expect(rows).toContainElement(screen.getByTestId('watchlist-row-NVDA'));
    expect(commandBar).toHaveTextContent('扫描当前筛选');
    expect(watchBoard).toContainElement(compactFilterBar);
    expect(watchBoard).toContainElement(boardShell);
    expect(boardShell).toContainElement(primaryWorkRegion);
    expect(primaryWorkRegion).toContainElement(rows);
    expect(boardShell).toContainElement(detailRail);
    expect(compactFilterBar.compareDocumentPosition(boardShell) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(primaryWorkRegion.compareDocumentPosition(secondaryDeck) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(boardShell.compareDocumentPosition(secondaryDeck) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(shell).toHaveClass('flex', 'flex-col', 'gap-5', 'px-4', 'xl:px-8');
    expect(watchBoard.parentElement).toBe(shell);
  });

  it('keeps advanced filters collapsed until explicitly opened', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    const advancedFilters = screen.getByTestId('watchlist-advanced-filters');
    expect(advancedFilters.tagName).toBe('DIV');
    expect(screen.getByRole('button', { name: '高级筛选' })).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByLabelText('主题 / 候选范围')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('证据筛选')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '高级筛选' }));

    expect(screen.getByRole('button', { name: '高级筛选' })).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByLabelText('主题 / 候选范围')).toBeInTheDocument();
    expect(screen.getByLabelText('证据筛选')).toBeInTheDocument();
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

    fireEvent.click(screen.getByRole('button', { name: '高级筛选' }));
    fireEvent.change(screen.getByLabelText('加入方式'), { target: { value: 'scanner' } });
    fireEvent.change(screen.getByLabelText('主题 / 候选范围'), { target: { value: 'theme:semis' } });

    expect(screen.queryByTestId('watchlist-row-NVDA')).not.toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-TSM')).toBeInTheDocument();
  });

  it('sorts rows by scanner score', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.change(screen.getByLabelText('排序'), { target: { value: 'scannerScore' } });

    const rows = Array.from(screen.getByTestId('watchlist-candidate-list').querySelectorAll('[data-testid^="watchlist-row-"]'));
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
    expect(within(row).getByText(/历史 \+3.2% · 命中 56%/)).toBeInTheDocument();
    expect(within(row).getByText('已回测')).toBeInTheDocument();
    expect(within(row).getByText(/收益 \+24.6% · 回撤 -8.2% · Sharpe 1.34 · 交易 6/)).toBeInTheDocument();
    fireEvent.click(within(row).getByRole('button', { name: /结果 33/ }));
    expect(screen.getByText('backtest result')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/zh/backtest/results/33');
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
    expect(within(row).getByText('依据更新中')).toBeInTheDocument();
    expect(within(row).getByTestId('watchlist-no-evidence-note-MARA')).toHaveTextContent('数据更新中，稍后将自动刷新。');
  });

  it('shows stale trust state as consumer-safe freshness and confidence', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [makeItem({
        id: 10,
        symbol: 'BABA',
        source: 'portfolio',
        scannerRunId: 77,
        scannerRank: null,
        scannerScore: 81,
        lastScoredAt: '2026-04-20T12:30:00Z',
        scoreSource: 'proxy_fallback',
        scoreStatus: 'stale',
        intelligence: {
          scanner: {
            lastScore: 81,
            lastRank: null,
            status: 'selected',
            reason: 'Fallback score snapshot.',
            lastScannedAt: '2026-04-20T12:30:00Z',
          },
          strategySimulation: { status: 'unknown' },
          backtest: {},
        },
      })],
    });

    renderWatchlist();

    const row = await screen.findByTestId('watchlist-row-BABA');
    const trustStrip = within(row).getByTestId('watchlist-trust-strip-BABA');
    expect(trustStrip).toHaveTextContent('置信度较低');
    expect(row).toHaveTextContent('已使用最近一次可用数据。');
    expect(trustStrip.textContent).toMatch(/更新/);
    expect(trustStrip).not.toHaveTextContent(/proxy_fallback|proxy fallback|fallback|proxy|备用数据|代理证据|来源|扫描批次|source|scanner run|score source/i);
  });

  it('keeps stale inherited scanner scores from rendering as verified latest evidence', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [makeItem({
        id: 15,
        symbol: 'BABA',
        source: 'scanner',
        scannerRunId: 77,
        scannerRank: 2,
        scannerScore: 81,
        lastScoredAt: '2026-05-01T11:45:00',
        scoreSource: 'scanner_run',
        scoreStatus: 'stale',
        intelligence: {
          scanner: {
            lastScore: 81,
            lastRank: 2,
            status: 'selected',
            reason: 'Latest scanner score.',
            lastScannedAt: '2026-05-01T11:50:00',
          },
          strategySimulation: { status: 'ready' },
          backtest: {},
        },
      })],
    });

    renderWatchlist();

    const row = await screen.findByTestId('watchlist-row-BABA');
    expect(row).toHaveTextContent('已使用最近一次可用数据。');
    expect(row).toHaveTextContent('置信度较低');
    expect(row).not.toHaveTextContent(/历史评分|历史证据|刷新或重新扫描后再使用/);
    expect(within(row).queryByText('已验证')).not.toBeInTheDocument();
    expect(within(row).queryByText('最新')).not.toBeInTheDocument();
    expect(within(row).queryByText('今日')).not.toBeInTheDocument();
  });

  it('gives unknown no-score rows an explicit refresh or scanner next action', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [makeItem({
        id: 16,
        symbol: 'SHOP',
        source: '',
        scannerRunId: null,
        scannerRank: null,
        scannerScore: null,
        lastScoredAt: null,
        scoreSource: null,
        scoreStatus: 'unknown',
        themeId: null,
        universeType: null,
        intelligence: undefined,
      })],
    });

    renderWatchlist();

    const row = await screen.findByTestId('watchlist-row-SHOP');
    expect(row).toHaveTextContent('数据更新中，稍后将自动刷新。');
    expect(row).not.toHaveTextContent(/来源未知|评分待刷新|可刷新情报|返回扫描器补齐证据/);
    expect(within(row).queryByText('已验证')).not.toBeInTheDocument();
    expect(within(row).queryByText('最新')).not.toBeInTheDocument();
    expect(within(row).queryByText('今日')).not.toBeInTheDocument();
  });

  it('keeps fallback proxy score evidence degraded instead of verified', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [makeItem({
        id: 17,
        symbol: 'BILI',
        source: 'scanner',
        scannerRunId: 91,
        scannerRank: 4,
        scannerScore: 70,
        lastScoredAt: '2026-05-01T11:45:00',
        scoreSource: 'proxy_fallback',
        scoreStatus: 'fresh',
        intelligence: {
          scanner: {
            lastScore: 70,
            lastRank: 4,
            status: 'selected',
            reason: 'Fallback score snapshot.',
            lastScannedAt: '2026-05-01T11:50:00',
          },
          strategySimulation: { status: 'ready' },
          backtest: {},
        },
      })],
    });

    renderWatchlist();

    const row = await screen.findByTestId('watchlist-row-BILI');
    expect(row).toHaveTextContent('部分自选股数据暂不可用，已使用最近一次可用数据。');
    expect(row).toHaveTextContent('置信度较低');
    expect(row).not.toHaveTextContent(/备用\/代理|备用数据|代理证据|fallback|proxy|刷新或重新扫描后再使用/i);
    expect(within(row).queryByText('已验证')).not.toBeInTheDocument();
    expect(within(row).queryByText('信号最新')).not.toBeInTheDocument();
    expect(within(row).queryByText('今日')).not.toBeInTheDocument();
    const forbiddenActionCopy = /买入|卖出|加仓|减仓|下单|立即交易|必买|稳赚|保证收益|guaranteed|best contract|AI recommends you buy|recommend(?:ation)?|buy|sell/i;
    expect(row).not.toHaveTextContent(forbiddenActionCopy);
  });

  it('keeps maintainer remediation paths out of the default consumer watchlist', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [makeItem({
        id: 12,
        symbol: 'BILI',
        source: 'portfolio',
        scannerRunId: 91,
        scannerRank: null,
        scannerScore: 70,
        lastScoredAt: '2026-04-20T12:30:00Z',
        scoreSource: 'proxy_fallback',
        scoreStatus: 'stale',
        intelligence: {
          scanner: {
            lastScore: 70,
            lastRank: null,
            status: 'selected',
            reason: 'Fallback score snapshot.',
            lastScannedAt: '2026-04-20T12:30:00Z',
          },
          strategySimulation: { status: 'partial' },
          backtest: {},
        },
      })],
    });

    renderWatchlist();

    await screen.findByTestId('watchlist-row-BILI');
    expect(screen.queryByTestId('watchlist-setup-path')).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '查看 Provider Ops' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '前往数据源设置' })).not.toBeInTheDocument();
    expect(screen.getByTestId('watchlist-status-strip')).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-page')).not.toHaveTextContent(/Provider Ops|surface=scanner|surface=watchlist|provider|proxy|fallback/i);
  });

  it('shows unknown trust disclosure when source and freshness fields are absent', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [makeItem({
        id: 11,
        symbol: 'SHOP',
        source: '',
        scannerRunId: null,
        scannerRank: null,
        scannerScore: null,
        lastScoredAt: null,
        scoreSource: null,
        scoreStatus: null,
        themeId: null,
        universeType: null,
        intelligence: undefined,
      })],
    });

    renderWatchlist();

    const row = await screen.findByTestId('watchlist-row-SHOP');
    const trustStrip = within(row).getByTestId('watchlist-trust-strip-SHOP');
    expect(trustStrip).toHaveTextContent('数据更新中，稍后将自动刷新。');
    expect(trustStrip).not.toHaveTextContent(/信号未知|来源未知|需要刷新|score source|source unknown/i);
  });

  it('does not expose backend diagnostics or repeated refresh-remediation copy by default', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [makeItem({
        id: 18,
        symbol: 'SNOW',
        source: 'scanner',
        scannerRunId: 101,
        scannerRank: null,
        scannerScore: 62,
        lastScoredAt: '2026-04-20T12:30:00Z',
        scoreSource: 'proxy_fallback',
        scoreStatus: 'stale',
        scoreReason: 'reasonFamilies=[source_confidence,score_blocked] sourceAuthorityAllowed=false scoreContributionAllowed=false observationOnly=true raw diagnostics JSON',
        scoreError: 'provider_down reasonCode=source_confidence raw diagnostics JSON',
        intelligence: {
          scanner: {
            lastScore: 62,
            lastRank: null,
            status: 'provider_error',
            reason: 'reasonFamilies=[source_confidence,score_blocked] sourceAuthorityAllowed=false scoreContributionAllowed=false observationOnly=true raw diagnostics JSON',
            lastScannedAt: '2026-04-20T12:30:00Z',
          },
          strategySimulation: { status: 'partial' },
          backtest: {},
        },
      })],
    });

    renderWatchlist();

    const page = await screen.findByTestId('watchlist-page');
    expect(page).toHaveTextContent('已使用最近一次可用数据。');
    expect(page).toHaveTextContent('置信度较低');
    expect(page).not.toHaveTextContent(/reasonFamilies|reasonCode|sourceAuthorityAllowed|scoreContributionAllowed|observationOnly|source_confidence|score_blocked|raw diagnostics|JSON|provider_down|provider_error|proxy_fallback|fallback|proxy|备用\/代理|刷新或重新扫描后再使用|来源未知 \/ 需要刷新/i);
  });

  it('sorts by backtest return and historical hit rate', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.change(screen.getByLabelText('排序'), { target: { value: 'backtestReturn' } });
    let rows = Array.from(screen.getByTestId('watchlist-candidate-list').querySelectorAll('[data-testid^="watchlist-row-"]'));
    expect(within(rows[0] as HTMLElement).getByText('NVDA')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('排序'), { target: { value: 'historicalHitRate' } });
    rows = Array.from(screen.getByTestId('watchlist-candidate-list').querySelectorAll('[data-testid^="watchlist-row-"]'));
    expect(within(rows[0] as HTMLElement).getByText('NVDA')).toBeInTheDocument();
  });

  it('shows the first filtered symbol in the detail rail and updates it when another row is focused', async () => {
    renderWatchlist();

    await screen.findByTestId('watchlist-row-NVDA');
    const detailRail = screen.getByTestId('watchlist-detail-rail');
    expect(within(detailRail).getByText('NVDA')).toBeInTheDocument();
    expect(within(detailRail).getByText('观察摘要')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '查看详情 TSM' }));

    expect(within(detailRail).getByText('TSM')).toBeInTheDocument();
    expect(within(detailRail).getByText('TSMC')).toBeInTheDocument();
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

    fireEvent.click(screen.getByRole('button', { name: '高级筛选' }));
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
    fireEvent.click(within(row).getByRole('button', { name: /结果 701/ }));
    expect(screen.getByText('backtest result')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/zh/backtest/results/701');
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
    expect(within(row).queryByText('开发者细节')).not.toBeInTheDocument();
    expect(row).toHaveTextContent('错误详情已隐藏');
    expect(row).not.toHaveTextContent(/provider_error|critical|stack/i);
  });

  it('keeps the filter controls overflow-safe with long labels', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    const searchInput = screen.getByLabelText('搜索');
    expect(searchInput).toHaveClass('pr-12');
    expect(screen.getByTestId('watchlist-primary-filters').className).not.toContain('overflow-hidden');
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

    const runtimeStatus = screen.getByTestId('watchlist-runtime-status');
    expect(runtimeStatus).toHaveTextContent('自动刷新');
    expect(runtimeStatus).toHaveTextContent('运行状态');
    expect(screen.getAllByText('最新').length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: /刷新评分/ }));

    await waitFor(() => expect(refreshScores).toHaveBeenCalledWith({ force: true }));
    expect(await screen.findByText(/评分已刷新/)).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-NVDA')).toHaveTextContent('96.0');
  });

  it('navigates to backtest with scanner and watchlist metadata', async () => {
    renderWatchlist();
    const row = await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.click(within(row).getByRole('button', { name: /回测/ }));

    expect(screen.getByText('backtest')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/zh/backtest?');
    expect(screen.getByTestId('location')).toHaveTextContent('symbol=NVDA');
    expect(screen.getByTestId('location')).toHaveTextContent('source=scanner');
    expect(screen.getByTestId('location')).toHaveTextContent('origin=watchlist');
    expect(screen.getByTestId('location')).toHaveTextContent('watchlistItemId=1');
    expect(screen.getByTestId('location')).toHaveTextContent('scannerRunId=42');
    expect(screen.getByTestId('location')).toHaveTextContent('themeId=ai-momentum');
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

  it('renders an empty state with a scanner action', async () => {
    listWatchlistItems.mockResolvedValue({ items: [] });

    renderWatchlist();

    const watchBoard = await screen.findByTestId('watchlist-watch-board');
    const primaryWorkRegion = screen.getByTestId('watchlist-primary-work-region');
    const emptyState = await screen.findByTestId('watchlist-compact-empty-state');
    expect(watchBoard).toContainElement(primaryWorkRegion);
    expect(primaryWorkRegion).toContainElement(emptyState);
    expect(emptyState).toHaveClass('min-h-[64px]', 'rounded-none', 'border-x-0', 'border-t');
    expect(within(emptyState).getByText('暂无追踪候选。')).toBeInTheDocument();
    fireEvent.click(within(emptyState).getByRole('button', { name: /打开扫描器/ }));
    expect(screen.getByText('scanner')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/zh/scanner');
  });

  it('keeps batch actions and auto refresh in compact product-labeled rows', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    expect(screen.getByTestId('watchlist-command-bar')).toHaveTextContent('批量操作');
    expect(screen.getByTestId('watchlist-command-bar')).toHaveTextContent('运行状态');
    expect(screen.getByTestId('watchlist-command-bar')).toHaveTextContent('扫描当前筛选');
    expect(screen.getByTestId('watchlist-command-bar')).toHaveTextContent('回测当前筛选');
    expect(screen.getByRole('button', { name: '刷新情报' })).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-runtime-status')).toHaveTextContent('自动刷新');
  });

  it('renders the authentication guard for guests', () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: true });

    renderWatchlist();

    expect(screen.getByText('auth-guard:观察列表')).toBeInTheDocument();
    expect(listWatchlistItems).not.toHaveBeenCalled();
  });
});
