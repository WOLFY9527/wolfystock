import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import WatchlistPage from '../WatchlistPage';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import type { WatchlistItem, WatchlistScannerLineageV1 } from '../../types/watchlist';
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

const { listRules, createRule, updateRule } = vi.hoisted(() => ({
  listRules: vi.fn(),
  createRule: vi.fn(),
  updateRule: vi.fn(),
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

vi.mock('../../api/userAlerts', () => ({
  userAlertsApi: {
    listRules,
    createRule,
    updateRule,
    deleteRule: vi.fn(),
    listEvents: vi.fn(),
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
    scoreStatusContext: {
      scope: 'score_refresh_recency',
      freshMeans: 'persisted_scanner_score_refreshed',
      sourceFreshnessImplied: false,
      sourceAuthorityImplied: false,
    },
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

function makeUserAlertRule(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    contractVersion: 'user_alert_contract_v1',
    ruleType: 'watchlist_price_threshold',
    symbol: 'NVDA',
    direction: 'above',
    thresholdPrice: 1000,
    enabled: true,
    note: null,
    deliveryMode: 'in_app',
    inAppOnly: true,
    ownerScoped: true,
    createdAt: '2026-06-01T08:00:00Z',
    updatedAt: '2026-06-01T08:00:00Z',
    ...overrides,
  };
}

async function flushPendingUiWork() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await vi.dynamicImportSettled();
  });
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
    listRules.mockImplementation(() => new Promise(() => {}));
    createRule.mockResolvedValue(makeUserAlertRule());
    updateRule.mockResolvedValue(makeUserAlertRule());
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: writeTextMock,
      },
    });
    writeTextMock.mockResolvedValue(undefined);
  });

  afterEach(async () => {
    cleanup();
    await flushPendingUiWork();
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
    expect(screen.getByTestId('watchlist-filter-grid')).toHaveClass('grid', 'grid-cols-2');
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
    expect(within(statusStrip).getByText('需留意项目').nextElementSibling).toHaveTextContent('0');
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

    await screen.findByTestId('watchlist-row-NVDA');
    const band = await screen.findByTestId('watchlist-conclusion-band');
    expect(band).toHaveTextContent('监控状态');
    expect(band).toHaveTextContent('当前焦点 NVDA');
    expect(band).toHaveTextContent('需要留意');
    expect(band).toHaveTextContent('观察标的 3');
    expect(band).toHaveTextContent('最新1');
    expect(band).toHaveTextContent('需留意3');
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
    expect(band).toHaveTextContent('需要留意');
    expect(band).toHaveTextContent('观察标的 2');
    expect(band).toHaveTextContent('最新0');
    expect(band).toHaveTextContent('需留意3');
    expect(band).toHaveTextContent('部分项目需要刷新后再参考。');
  });

  it('renders the intelligence command bar, coverage summary, and selected scope controls', async () => {
    renderWatchlist();
    const row = await screen.findByTestId('watchlist-row-NVDA');

    expect(screen.getByTestId('watchlist-command-bar')).toHaveTextContent('刷新当前筛选');
    expect(screen.getByTestId('watchlist-command-bar')).toHaveTextContent('回测当前筛选');
    expect(screen.getByRole('button', { name: '仅选中' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '清除选择' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '刷新观察依据' })).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-action-scope')).toHaveTextContent('当前筛选 3 个标的');
    const statusStrip = screen.getByTestId('watchlist-status-strip');
    expect(within(statusStrip).getByText('观察标的数').nextElementSibling).toHaveTextContent('3');
    expect(within(statusStrip).getByText('需留意项目').nextElementSibling).toHaveTextContent('0');
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
    expect(commandBar).toHaveTextContent('刷新当前筛选');
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
    expect(screen.getByRole('button', { name: /刷新当前筛选/ })).toBeDisabled();
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
    fireEvent.change(screen.getByLabelText('加入路径'), { target: { value: 'scanner' } });
    fireEvent.change(screen.getByLabelText('主题 / 候选范围'), { target: { value: 'theme:semis' } });

    expect(screen.queryByTestId('watchlist-row-NVDA')).not.toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-TSM')).toBeInTheDocument();
  });

  it('sorts rows by scanner score', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.change(screen.getByLabelText('排序'), { target: { value: 'scannerScore' } });

    const rows = Array.from(screen.getByTestId('watchlist-candidate-list').querySelectorAll('article[data-testid^="watchlist-row-"]'));
    expect(within(rows[0] as HTMLElement).getByText('NVDA')).toBeInTheDocument();
    expect(within(rows[1] as HTMLElement).getByText('TSM')).toBeInTheDocument();
    expect(within(rows[2] as HTMLElement).getByText('600519')).toBeInTheDocument();
  });

  it('renders compact scanner, strategy simulation, and backtest intelligence chips in Chinese', async () => {
    renderWatchlist();
    const row = await screen.findByTestId('watchlist-row-NVDA');

    expect(within(row).getByText(/分数 94.0 · 历史 \+3.2% · 命中 56%/)).toBeInTheDocument();
    expect(within(row).getByText('已验证')).toBeInTheDocument();
    expect(within(row).getByText('已回测')).toBeInTheDocument();
    expect(within(row).getByText(/更新 05\/01 13:30 · 命中 56% · 回测 \+24.6%/)).toBeInTheDocument();
    fireEvent.click(within(row).getByRole('button', { name: /结果 33/ }));
    expect(screen.getByText('backtest result')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/zh/backtest/results/33');
  });

  it('renders derived workflow strips from watchlist item fields without durable or trading wording', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [
        makeItem({
          id: 30,
          symbol: 'NVDA',
          notes: '站内提醒已记录，仅用于观察。',
        }),
        makeItem({
          id: 31,
          symbol: 'SHOP',
          source: 'manual',
          scannerRunId: null,
          scannerRank: null,
          scannerScore: null,
          lastScoredAt: null,
          scoreSource: null,
          scoreStatus: 'unknown',
          themeId: null,
          universeType: null,
          intelligence: undefined,
        }),
      ],
    });

    renderWatchlist();

    const observingWorkflow = await screen.findByTestId('watchlist-row-workflow-NVDA');
    const pendingWorkflow = await screen.findByTestId('watchlist-row-workflow-SHOP');

    expect(observingWorkflow).toHaveTextContent('研究流程');
    expect(observingWorkflow).toHaveTextContent('已发现');
    expect(observingWorkflow).toHaveTextContent('观察中');
    expect(observingWorkflow).toHaveTextContent('提醒记录');
    expect(observingWorkflow).not.toHaveTextContent('待验证');
    expect(observingWorkflow).not.toHaveTextContent('需刷新');

    expect(pendingWorkflow).toHaveTextContent('研究流程');
    expect(pendingWorkflow).toHaveTextContent('待验证');
    expect(pendingWorkflow).toHaveTextContent('需刷新');
    expect(pendingWorkflow).not.toHaveTextContent('观察中');

    const detailWorkflow = screen.getByTestId('watchlist-detail-workflow');
    expect(detailWorkflow).toHaveTextContent('已发现');
    expect(detailWorkflow).toHaveTextContent('观察中');
    expect(detailWorkflow).toHaveTextContent('提醒记录');

    fireEvent.click(screen.getByRole('button', { name: '查看详情 SHOP' }));

    expect(detailWorkflow).toHaveTextContent('待验证');
    expect(detailWorkflow).toHaveTextContent('需刷新');
    expect(detailWorkflow).not.toHaveTextContent('观察中');

    [observingWorkflow, pendingWorkflow, detailWorkflow].forEach((strip) => {
      expect(strip).not.toHaveTextContent(/workflow_state|research_completed|invalidated|archived|source_confidence|reasonCode|reasonFamilies|provider|scannerRunId|raw diagnostics|JSON/i);
      expect(strip).not.toHaveTextContent(/买入|卖出|加仓|减仓|下单|立即交易|止损|止盈|目标价|仓位|guaranteed|best contract|AI recommends you buy|recommend(?:ation)?|buy|sell|stop|target|position/i);
    });
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
    expect(within(row).getAllByText('扫描失败').length).toBeGreaterThan(0);
    expect(within(row).getByText('样本不足')).toBeInTheDocument();
    expect(within(row).getByTestId('watchlist-row-note-MARA')).toHaveTextContent('当前信号暂不可用，刷新后再参考。');
    expect(row).not.toHaveTextContent(/provider_down|provider_error|unknown|critical|debug/i);
    expect(within(row).queryByText(/结果 /)).not.toBeInTheDocument();
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
    expect(within(row).getByText('未扫描')).toBeInTheDocument();
    expect(within(row).getByTestId('watchlist-row-note-MARA')).toHaveTextContent('数据更新中，稍后将自动刷新。');
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
    expect(row).toHaveTextContent('置信度较低');
    expect(row).toHaveTextContent('已使用最近一次可用数据。');
    expect(row).toHaveTextContent('下一步 补充回测');
    expect(row).not.toHaveTextContent(/proxy_fallback|proxy fallback|fallback|proxy|备用数据|代理证据|来源|扫描批次|source|scanner run|score source/i);
  });

  it('maps score_status_context freshness to score-refresh copy without source authority', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [makeItem({
        id: 14,
        symbol: 'AMD',
        source: 'scanner',
        scannerRunId: 88,
        scannerScore: 89,
        lastScoredAt: '2026-05-01T11:50:00Z',
        scoreSource: 'scanner_run',
        scoreStatus: 'fresh',
        scoreStatusContext: {
          scope: 'score_refresh_recency',
          freshMeans: 'persisted_scanner_score_refreshed',
          sourceFreshnessImplied: false,
          sourceAuthorityImplied: false,
        },
        createdAt: '2026-05-01T11:49:30Z',
        updatedAt: '2026-05-01T11:49:30Z',
        intelligence: {
          scanner: {
            lastScore: 89,
            lastRank: 2,
            status: 'selected',
            reason: 'Latest scanner score.',
            lastScannedAt: '2026-05-01T11:50:00Z',
          },
          strategySimulation: { status: 'ready' },
          backtest: {},
        },
      })],
    });

    renderWatchlist();

    const row = await screen.findByTestId('watchlist-row-AMD');
    const detailRail = screen.getByTestId('watchlist-detail-rail');
    expect(row).toHaveTextContent('评分已刷新');
    expect(row).toHaveTextContent('评分最近刷新；不代表来源实时或权威。');
    expect(detailRail).toHaveTextContent('评分最近刷新');
    expect(detailRail).toHaveTextContent('评分最近刷新；不代表来源实时或权威。');
    expect(row).not.toHaveTextContent(/信号最新|source_status_context|score_status_context|sourceFreshnessImplied|sourceAuthorityImplied|source_confidence|reason_families|scanner_run_id|scannerRunId/i);
  });

  it('maps cached and blocked score statuses to bounded consumer copy', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [
        makeItem({
          id: 18,
          symbol: 'CASH',
          source: 'portfolio',
          scannerRunId: 12,
          scannerScore: 72,
          lastScoredAt: '2026-05-01T09:30:00Z',
          scoreStatus: 'cached',
          createdAt: '2026-05-01T09:00:00Z',
          updatedAt: '2026-05-01T09:00:00Z',
        }),
        makeItem({
          id: 19,
          symbol: 'HOLD',
          source: 'scanner',
          scannerRunId: 13,
          scannerScore: 66,
          lastScoredAt: '2026-05-01T09:20:00Z',
          scoreStatus: 'blocked',
          scoreReason: 'score_blocked source_confidence sourceAuthorityAllowed=false',
          createdAt: '2026-05-01T09:20:00Z',
          updatedAt: '2026-05-01T09:20:00Z',
        }),
      ],
    });

    renderWatchlist();

    const cachedRow = await screen.findByTestId('watchlist-row-CASH');
    const blockedRow = await screen.findByTestId('watchlist-row-HOLD');
    expect(cachedRow).toHaveTextContent('已保存评分');
    expect(cachedRow).toHaveTextContent('已使用已保存评分；来源实时性未确认。');
    expect(blockedRow).toHaveTextContent('仅作观察');
    expect(blockedRow).toHaveTextContent('当前评分依据有限，先保持观察。');
    expect(screen.getByTestId('watchlist-page')).not.toHaveTextContent(/score_blocked|source_confidence|sourceAuthorityAllowed|score_status_context|reason_families|raw diagnostics|JSON/i);
  });

  it('shows a bounded scanner lineage cue only when post-add refresh fields support it', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [
        makeItem({
          id: 20,
          symbol: 'NVDA',
          source: 'scanner',
          scannerRunId: 90,
          lastScoredAt: '2026-05-01T11:50:00Z',
          createdAt: '2026-05-01T10:00:00Z',
          updatedAt: '2026-05-01T10:00:00Z',
        }),
        makeItem({
          id: 21,
          symbol: 'MSFT',
          source: 'scanner',
          scannerRunId: 91,
          lastScoredAt: '2026-05-01T11:40:00Z',
          createdAt: '2026-05-01T11:40:00Z',
          updatedAt: '2026-05-01T11:40:00Z',
        }),
      ],
    });

    renderWatchlist();

    const refreshedRow = await screen.findByTestId('watchlist-row-NVDA');
    const unchangedRow = await screen.findByTestId('watchlist-row-MSFT');
    expect(refreshedRow).toHaveTextContent('保存后更新');
    expect(refreshedRow).toHaveTextContent('研究评分在保存后更新，可视为较新的观察记录。');
    expect(unchangedRow).not.toHaveTextContent('保存后更新');
    fireEvent.click(within(refreshedRow).getByRole('button', { name: '查看详情 NVDA' }));
    expect(screen.getByTestId('watchlist-detail-rail')).toHaveTextContent('保存后更新');
    expect(screen.getByTestId('watchlist-page')).not.toHaveTextContent(/scannerRunId|scanner_run_id|扫描批次|source_confidence|reason_families|sourceAuthority|来源权限/i);
  });

  it('renders scannerLineageV1 in a collapsed detail block without diagnostics or action-grade copy', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [
        makeItem({
          id: 22,
          symbol: 'WULF',
          source: 'scanner',
          scannerRunId: 90,
          scannerRank: 2,
          scannerScore: 71.5,
          lastScoredAt: '2026-05-04T10:00:00Z',
          createdAt: '2026-05-01T09:00:00Z',
          updatedAt: '2026-05-04T10:00:00Z',
          intelligence: {
            scanner: {
              lastScore: 71.5,
              lastRank: 2,
              status: 'selected',
              reason: 'Latest scanner score.',
              lastScannedAt: '2026-05-04T10:00:00Z',
              scannerLineageV1: {
                contractVersion: 'scanner_watchlist_lineage_v1',
                source: 'scanner',
                scannerRunId: 90,
                symbol: 'WULF',
                market: 'us',
                rankAtScan: 2,
                scoreAtScan: 71.5,
                scoreSnapshotKind: 'post_add_refresh',
                runProfile: 'us_preopen_v1',
                runCompletedAt: '2026-05-04T10:00:00Z',
                watchlistAddedAt: '2026-05-01T09:00:00Z',
                themeId: 'crypto_miners',
                universeType: 'theme',
                researchReason: 'sourceAuthorityAllowed=false raw diagnostics JSON provider_down reasonCode=debug',
                researchNextStep: '补充证据后继续观察。',
                dataState: 'observation_only',
                freshnessLabel: '最近可用',
                noAdviceBoundary: true,
                observationOnly: true,
                scoreGradeAllowed: false,
                sourceAuthorityAllowed: false,
                sourceType: 'authorized_licensed_feed',
                sourceTier: 'internal_source_tier',
                rawDiagnostics: { reasonCode: 'debug' },
                providerObservation: [{ providerName: 'internal-provider' }],
              } as WatchlistScannerLineageV1 & Record<string, unknown>,
            },
            strategySimulation: { status: 'ready' },
            backtest: {},
          },
        }),
      ],
    });

    renderWatchlist();

    await screen.findByTestId('watchlist-row-WULF');
    const detailRail = screen.getByTestId('watchlist-detail-rail');
    const lineageBlock = within(detailRail).getByTestId('watchlist-scanner-lineage');
    const toggle = within(lineageBlock).getByRole('button', { name: '展开 研究流程记录' });

    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(lineageBlock).toHaveTextContent('研究流程记录 · 最近可用 · 仅作观察');
    expect(lineageBlock).not.toHaveTextContent(/sourceAuthorityAllowed|scoreContributionAllowed|sourceType|sourceTier|authorized_licensed_feed|internal_source_tier|reasonCode|raw diagnostics|JSON|provider_down|internal-provider|providerObservation/i);

    fireEvent.click(toggle);

    expect(within(lineageBlock).getByRole('button', { name: '收起 研究流程记录' })).toHaveAttribute('aria-expanded', 'true');
    expect(lineageBlock).toHaveTextContent('保存后更新');
    expect(lineageBlock).toHaveTextContent('候选序位 #2 · 研究评分 71.5');
    expect(lineageBlock).toHaveTextContent('补充证据后继续观察。');
    expect(lineageBlock).toHaveTextContent('研究窗口已记录');
    expect(lineageBlock).not.toHaveTextContent('us_preopen_v1');
    expect(screen.getByTestId('watchlist-page')).not.toHaveTextContent(/买入|卖出|加仓|减仓|下单|立即交易|止损|止盈|目标价|仓位|guaranteed|best contract|AI recommends you buy|recommend(?:ation)?|buy|sell|stop|target|position/i);
    expect(screen.getByTestId('watchlist-page')).not.toHaveTextContent(/sourceAuthorityAllowed|scoreContributionAllowed|sourceType|sourceTier|authorized_licensed_feed|internal_source_tier|reasonCode|source_confidence|reason_families|raw diagnostics|JSON|provider_down|internal-provider|providerObservation/i);
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
    expect(within(row).getByTestId('watchlist-row-note-SHOP')).toHaveTextContent('数据更新中，稍后将自动刷新。');
    expect(row).not.toHaveTextContent(/信号未知|来源未知|需要刷新|score source|source unknown/i);
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
    let rows = Array.from(screen.getByTestId('watchlist-candidate-list').querySelectorAll('article[data-testid^="watchlist-row-"]'));
    expect(within(rows[0] as HTMLElement).getByText('NVDA')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('排序'), { target: { value: 'historicalHitRate' } });
    rows = Array.from(screen.getByTestId('watchlist-candidate-list').querySelectorAll('article[data-testid^="watchlist-row-"]'));
    expect(within(rows[0] as HTMLElement).getByText('NVDA')).toBeInTheDocument();
  });

  it('shows the first filtered symbol in the detail rail and updates it when another row is focused', async () => {
    renderWatchlist();

    await screen.findByTestId('watchlist-row-NVDA');
    const detailRail = screen.getByTestId('watchlist-detail-rail');
    expect(within(detailRail).getByText('NVDA')).toBeInTheDocument();
    expect(within(detailRail).getByText('观察摘要')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '查看详情 TSM' }));

    await waitFor(() => expect(within(detailRail).getByText('TSM')).toBeInTheDocument());
    expect(within(detailRail).getByText('TSMC')).toBeInTheDocument();
  });

  it('renders the user alerts panel inside the detail rail for the selected symbol without route or nav changes', async () => {
    listRules.mockResolvedValue({
      contractVersion: 'user_alert_contract_v1',
      deliveryMode: 'in_app',
      inAppOnly: true,
      ownerScoped: true,
      items: [
        makeUserAlertRule({ symbol: 'NVDA', thresholdPrice: 1000.5, note: '突破后观察' }),
        makeUserAlertRule({ id: 2, symbol: 'TSM', thresholdPrice: 900.1, note: '不应显示' }),
      ],
    });

    renderWatchlist();

    await screen.findByTestId('watchlist-row-NVDA');
    const detailRail = screen.getByTestId('watchlist-detail-rail');
    const panel = await within(detailRail).findByTestId('user-alerts-rail-panel');

    expect(panel).toBeInTheDocument();
    fireEvent.click(within(panel).getByRole('button', { name: '展开 站内提醒' }));
    expect(within(panel).getByText('突破后观察')).toBeInTheDocument();
    expect(within(panel).queryByText('不应显示')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sidebar-nav')).not.toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/watchlist');
    expect(listRules).toHaveBeenCalledTimes(1);
  });

  it('renders saved watchlist notes inside the collapsed data notes rail without replacing existing evidence', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [
        makeItem({
          notes: 'Scanner observation: watch post-earnings follow-through.',
        }),
      ],
    });

    renderWatchlist();

    await screen.findByTestId('watchlist-row-NVDA');
    const detailRail = screen.getByTestId('watchlist-detail-rail');
    const dataNotes = within(detailRail).getByTestId('watchlist-data-notes');

    expect(dataNotes).not.toHaveAttribute('open');
    expect(within(dataNotes).getByRole('button', { name: '展开 数据备注' })).toHaveAttribute('aria-expanded', 'false');
    expect(within(dataNotes).queryByTestId('watchlist-saved-note')).not.toBeInTheDocument();

    fireEvent.click(within(dataNotes).getByRole('button', { name: '展开 数据备注' }));

    const savedNote = within(dataNotes).getByTestId('watchlist-saved-note');
    expect(savedNote).toHaveTextContent('保存备注');
    expect(savedNote).toHaveTextContent('Scanner observation: watch post-earnings follow-through.');
    expect(within(dataNotes).getByText('研究候选')).toBeInTheDocument();
    expect(within(dataNotes).getByText('最新研究评分。')).toBeInTheDocument();
    expect(within(dataNotes).getByText(/历史 \+3.2% · 命中 56%/)).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/watchlist');
    expect(listWatchlistItems).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(getRefreshStatus).toHaveBeenCalledTimes(1));
    expect(refreshScores).not.toHaveBeenCalled();
    expect(runRuleBacktest).not.toHaveBeenCalled();
    expect(analyzeAsync).not.toHaveBeenCalled();
    expect(removeWatchlistItem).not.toHaveBeenCalled();
  });

  it('omits saved watchlist notes for missing or empty notes while keeping data notes available', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [
        makeItem({
          id: 1,
          symbol: 'NVDA',
          notes: undefined,
        }),
        makeItem({
          id: 2,
          symbol: 'TSM',
          name: 'TSMC',
          notes: '   \n  ',
        }),
      ],
    });

    renderWatchlist();

    await screen.findByTestId('watchlist-row-NVDA');
    const detailRail = screen.getByTestId('watchlist-detail-rail');
    const dataNotes = within(detailRail).getByTestId('watchlist-data-notes');

    fireEvent.click(within(dataNotes).getByRole('button', { name: '展开 数据备注' }));

    expect(within(dataNotes).queryByTestId('watchlist-saved-note')).not.toBeInTheDocument();
    expect(within(dataNotes).queryByText('保存备注')).not.toBeInTheDocument();
    expect(within(dataNotes).getByText('研究候选')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '查看详情 TSM' }));

    expect(within(detailRail).getByText('TSM')).toBeInTheDocument();
    expect(within(dataNotes).queryByTestId('watchlist-saved-note')).not.toBeInTheDocument();
    expect(within(dataNotes).queryByText('保存备注')).not.toBeInTheDocument();
  });

  it('mounts the leveraged ETF mapper only inside the detail rail without changing existing rail blocks or routing', async () => {
    renderWatchlist();

    await screen.findByTestId('watchlist-row-NVDA');
    const detailRail = screen.getByTestId('watchlist-detail-rail');
    const primaryWorkRegion = screen.getByTestId('watchlist-primary-work-region');
    const secondaryDeck = screen.getByTestId('watchlist-secondary-deck');
    const mapper = screen.getByTestId('leveraged-etf-mapper');

    expect(screen.getAllByTestId('leveraged-etf-mapper')).toHaveLength(1);
    expect(detailRail).toContainElement(mapper);
    expect(primaryWorkRegion).not.toContainElement(mapper);
    expect(secondaryDeck).not.toContainElement(mapper);
    expect(within(mapper).getByRole('button', { name: '展开 杠杆 ETF 映射' })).toHaveAttribute('aria-expanded', 'false');
    expect(within(mapper).queryByLabelText('ETF 参考价')).not.toBeInTheDocument();
    expect(within(detailRail).getByText('评分已刷新')).toBeInTheDocument();
    expect(within(detailRail).getByText('观察摘要')).toBeInTheDocument();
    expect(screen.queryByTestId('sidebar-nav')).not.toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/watchlist');
  });

  it('renders investor signal as a collapsed persisted scanner observation with consumer-safe fields only', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [
        makeItem({
          symbol: 'NVDA',
          intelligence: {
            scanner: {
              lastScore: 94,
              lastRank: 1,
              status: 'selected',
              reason: 'Latest scanner score.',
              lastScannedAt: '2026-05-01T12:30:00',
              investorSignal: {
                contractVersion: 'investor_signal_contract_v1',
                diagnosticOnly: true,
                observationOnly: true,
                authorityGrant: false,
                decisionGrade: false,
                sourceAuthorityAllowed: false,
                scoreContributionAllowed: false,
                marketRegime: 'mixed',
                marketRegimeLabel: '信号分化',
                confidenceLabel: 'blocked',
                confidenceText: '禁止判断',
                freshness: 'cached',
                reasonCodes: ['source_authority_missing', 'score_rights_missing', 'source_tier_discount'],
                contradictionCodes: ['theme_rotation_mismatch'],
                explanation: '主题强弱仍然分化，当前只保留观察意义。',
              },
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
        }),
      ],
    });

    renderWatchlist();

    await screen.findByTestId('watchlist-row-NVDA');
    const detailRail = screen.getByTestId('watchlist-detail-rail');
    const disclosure = screen.getByTestId('watchlist-investor-signal');
    const toggle = within(disclosure).getByRole('button', { name: '展开 资金面观察信号' });

    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(disclosure).toHaveTextContent('来自已保存的研究观察');
    expect(within(detailRail).getByText('评分已刷新')).toBeInTheDocument();
    expect(within(disclosure).queryByText('禁止判断')).not.toBeInTheDocument();
    expect(within(disclosure).queryByText('最近可用')).not.toBeInTheDocument();

    fireEvent.click(toggle);

    expect(within(disclosure).getByRole('button', { name: '收起 资金面观察信号' })).toHaveAttribute('aria-expanded', 'true');
    expect(within(detailRail).getByText('评分已刷新')).toBeInTheDocument();
    expect(within(disclosure).getByText('信号分化')).toBeInTheDocument();
    expect(within(disclosure).getByText('禁止判断')).toBeInTheDocument();
    expect(within(disclosure).getByText('最近可用')).toBeInTheDocument();
    expect(within(disclosure).queryByText('信号最新')).not.toBeInTheDocument();
    expect(within(disclosure).getByText('证据仍待确认')).toBeInTheDocument();
    expect(within(disclosure).getByText('评分依据不足')).toBeInTheDocument();
    expect(within(disclosure).getByText('证据较弱')).toBeInTheDocument();
    expect(within(disclosure).getByText('主题轮动暂未同向')).toBeInTheDocument();
    expect(within(disclosure).queryByText('Theme Rotation Mismatch')).not.toBeInTheDocument();
    expect(within(disclosure).getByTestId('watchlist-investor-signal-explanation')).toHaveTextContent('主题强弱仍然分化，当前只保留观察意义。');
    expect(disclosure).not.toHaveTextContent(/contractVersion|diagnosticOnly|authorityGrant|decisionGrade|sourceAuthorityAllowed|scoreContributionAllowed|sourceTier|source_tier|theme_rotation_mismatch/i);
    expect(disclosure).not.toHaveTextContent(/来源权限|来源层级|当前不允许计分|已缓存|cache|runtime|buy|sell|recommend|provider|admin/i);
  });

  it('omits the investor signal disclosure when scanner observation is absent', async () => {
    renderWatchlist();

    await screen.findByTestId('watchlist-row-NVDA');

    expect(screen.queryByTestId('watchlist-investor-signal')).not.toBeInTheDocument();
  });

  it('renders catalyst exposures as a collapsed bounded detail-rail disclosure using safe labels only', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [
        makeItem({
          notes: 'Scanner observation: watch follow-through after the next catalyst.',
          intelligence: {
            scanner: {
              lastScore: 94,
              lastRank: 1,
              status: 'selected',
              reason: 'Latest scanner score.',
              lastScannedAt: '2026-05-01T12:30:00',
              investorSignal: {
                contractVersion: 'investor_signal_contract_v1',
                diagnosticOnly: true,
                observationOnly: true,
                authorityGrant: false,
                decisionGrade: false,
                sourceAuthorityAllowed: false,
                scoreContributionAllowed: false,
                marketRegime: 'mixed',
                marketRegimeLabel: '信号分化',
                confidenceLabel: 'blocked',
                confidenceText: '禁止判断',
                freshness: 'cached',
                reasonCodes: ['source_authority_missing', 'score_rights_missing'],
                contradictionCodes: ['theme_rotation_mismatch'],
                explanation: '主题强弱仍然分化，当前只保留观察意义。',
              },
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
            catalystExposures: [
              {
                id: 'catalyst:NVDA:us:fundamental',
                symbol: 'NVDA',
                market: 'us',
                category: 'earnings_fundamental_snapshot',
                title: 'Fundamental snapshot exposure',
                summary: 'Quarterly revenue and margin snapshot is available.',
                evidenceStatus: 'delayed',
                evidenceLabels: ['delayed', 'source_tier_discount'],
                asOf: '2026-05-17T20:00:00+00:00',
                timeframe: '2026Q2',
                reasonCodes: ['observation_only', 'delayed_evidence', 'not_earnings_calendar'],
                observationOnly: true,
                sourceAuthorityAllowed: false,
                scoreContributionAllowed: false,
                decisionGrade: false,
                calendarClaimAllowed: false,
              },
              {
                id: 'catalyst:NVDA:us:news:1',
                symbol: 'NVDA',
                market: 'us',
                category: 'stored_news_catalyst_proxy',
                title: 'Stored news catalyst proxy',
                summary: 'Stored article summary references a potential demand catalyst.',
                evidenceStatus: 'proxy',
                evidenceLabels: ['proxy', 'unverified'],
                asOf: '2026-05-17T20:00:00+00:00',
                publishedAt: '2026-05-17T13:00:00+00:00',
                reasonCodes: ['observation_only', 'proxy_evidence_not_authoritative'],
                observationOnly: true,
                sourceAuthorityAllowed: false,
                scoreContributionAllowed: false,
                decisionGrade: false,
                calendarClaimAllowed: false,
              },
              {
                id: 'catalyst:NVDA:us:macro',
                symbol: 'NVDA',
                market: 'us',
                category: 'official_macro_cache_status',
                title: 'Official macro cache/status exposure',
                summary: 'Official macro cache/status is stale as diagnostic context only; no scheduled macro calendar authority is inferred.',
                evidenceStatus: 'stale',
                evidenceLabels: ['stale'],
                asOf: '2026-05-17',
                reasonCodes: ['observation_only', 'stale_evidence'],
                observationOnly: true,
                sourceAuthorityAllowed: false,
                scoreContributionAllowed: false,
                decisionGrade: false,
                calendarClaimAllowed: false,
              },
              {
                id: 'catalyst:NVDA:us:news:2',
                symbol: 'NVDA',
                market: 'us',
                category: 'stored_news_catalyst_proxy',
                title: 'Extra hidden exposure',
                summary: 'This item should stay outside the bounded disclosure.',
                evidenceStatus: 'proxy',
                evidenceLabels: ['proxy'],
                asOf: '2026-05-17T21:00:00+00:00',
                reasonCodes: ['observation_only'],
                observationOnly: true,
                sourceAuthorityAllowed: false,
                scoreContributionAllowed: false,
                decisionGrade: false,
                calendarClaimAllowed: false,
              },
            ],
          },
        }),
      ],
    });

    renderWatchlist();

    await screen.findByTestId('watchlist-row-NVDA');
    const detailRail = screen.getByTestId('watchlist-detail-rail');
    const disclosure = screen.getByTestId('watchlist-catalyst-exposures');
    const toggle = within(disclosure).getByRole('button', { name: '展开 催化剂观察' });

    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(disclosure).toHaveTextContent('来自已保存的观察线索');
    expect(within(detailRail).getByTestId('watchlist-investor-signal')).toBeInTheDocument();
    expect(within(detailRail).getByTestId('leveraged-etf-mapper')).toBeInTheDocument();
    expect(within(detailRail).getByTestId('watchlist-data-notes')).toBeInTheDocument();
    expect(within(disclosure).queryByText('Fundamental snapshot exposure')).not.toBeInTheDocument();

    fireEvent.click(toggle);

    expect(within(disclosure).getByRole('button', { name: '收起 催化剂观察' })).toHaveAttribute('aria-expanded', 'true');
    expect(within(disclosure).getByText('基本面线索')).toBeInTheDocument();
    expect(within(disclosure).getByText('已保存新闻线索')).toBeInTheDocument();
    expect(within(disclosure).getByText('宏观背景线索')).toBeInTheDocument();
    expect(within(disclosure).getByText('已保存基本面线索，适合继续观察。')).toBeInTheDocument();
    expect(within(disclosure).getByText('已保存新闻线索，可作为观察背景。')).toBeInTheDocument();
    expect(within(disclosure).getByText('宏观背景较旧，阅读时降低置信度。')).toBeInTheDocument();
    expect(within(disclosure).queryByText('Extra hidden exposure')).not.toBeInTheDocument();
    expect(within(disclosure).getAllByText('更新延迟').length).toBeGreaterThan(0);
    expect(within(disclosure).getAllByText('线索待确认').length).toBeGreaterThan(0);
    expect(within(disclosure).getAllByText('较旧线索').length).toBeGreaterThan(0);
    expect(within(disclosure).getAllByText('仅供观察').length).toBeGreaterThan(0);
    expect(within(disclosure).getByText('仅作线索')).toBeInTheDocument();
    expect(within(disclosure).getByText('日程仍待确认')).toBeInTheDocument();
    expect(within(disclosure).queryByText('earnings_fundamental_snapshot')).not.toBeInTheDocument();
    expect(within(disclosure).queryByText('stored_news_catalyst_proxy')).not.toBeInTheDocument();
    expect(within(disclosure).queryByText(/Fundamental snapshot exposure|Stored news catalyst proxy|Official macro cache\/status exposure/i)).not.toBeInTheDocument();
    expect(within(disclosure).queryByText(/observation_only|proxy_evidence_not_authoritative|stale_evidence|not_earnings_calendar|source_tier_discount/i)).not.toBeInTheDocument();
    expect(disclosure).not.toHaveTextContent(/sourceAuthorityAllowed|scoreContributionAllowed|decisionGrade|calendarClaimAllowed|sourceTier|sourceType|provider|admin|debug|proxy|cache|runtime|exposure/i);
  });

  it('omits the catalyst exposure disclosure when saved catalyst evidence is absent', async () => {
    renderWatchlist();

    await screen.findByTestId('watchlist-row-NVDA');

    expect(screen.queryByTestId('watchlist-catalyst-exposures')).not.toBeInTheDocument();
    expect(screen.getByTestId('leveraged-etf-mapper')).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-data-notes')).toBeInTheDocument();
  });

  it('keeps saved notes, catalyst exposure, investor signal, and leveraged ETF mapper present alongside the user alerts panel', async () => {
    listRules.mockResolvedValue({
      contractVersion: 'user_alert_contract_v1',
      deliveryMode: 'in_app',
      inAppOnly: true,
      ownerScoped: true,
      items: [
        makeUserAlertRule({ symbol: 'NVDA', thresholdPrice: 1000.5, note: '突破后观察' }),
      ],
    });
    listWatchlistItems.mockResolvedValue({
      items: [
        makeItem({
          notes: 'Scanner observation: watch follow-through after the next catalyst.',
          intelligence: {
            scanner: {
              lastScore: 94,
              lastRank: 1,
              status: 'selected',
              reason: 'Latest scanner score.',
              lastScannedAt: '2026-05-01T12:30:00',
              investorSignal: {
                contractVersion: 'investor_signal_contract_v1',
                diagnosticOnly: true,
                observationOnly: true,
                authorityGrant: false,
                decisionGrade: false,
                sourceAuthorityAllowed: false,
                scoreContributionAllowed: false,
                marketRegime: 'mixed',
                marketRegimeLabel: '信号分化',
                confidenceLabel: 'blocked',
                confidenceText: '禁止判断',
                freshness: 'cached',
                reasonCodes: ['source_authority_missing', 'score_rights_missing'],
                contradictionCodes: ['theme_rotation_mismatch'],
                explanation: '主题强弱仍然分化，当前只保留观察意义。',
              },
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
            catalystExposures: [
              {
                id: 'catalyst:NVDA:us:fundamental',
                symbol: 'NVDA',
                market: 'us',
                category: 'earnings_fundamental_snapshot',
                title: 'Fundamental snapshot exposure',
                summary: 'Quarterly revenue and margin snapshot is available.',
                evidenceStatus: 'delayed',
                evidenceLabels: ['delayed'],
                asOf: '2026-05-17T20:00:00+00:00',
                timeframe: '2026Q2',
                reasonCodes: ['observation_only', 'delayed_evidence', 'not_earnings_calendar'],
                observationOnly: true,
                sourceAuthorityAllowed: false,
                scoreContributionAllowed: false,
                decisionGrade: false,
                calendarClaimAllowed: false,
              },
            ],
          },
        }),
      ],
    });

    renderWatchlist();

    await screen.findByTestId('watchlist-row-NVDA');
    const detailRail = screen.getByTestId('watchlist-detail-rail');

    expect(within(detailRail).getByTestId('user-alerts-rail-panel')).toBeInTheDocument();
    expect(within(detailRail).getByTestId('watchlist-data-notes')).toBeInTheDocument();
    expect(within(detailRail).getByTestId('watchlist-investor-signal')).toBeInTheDocument();
    expect(within(detailRail).getByTestId('watchlist-catalyst-exposures')).toBeInTheDocument();
    expect(within(detailRail).getByTestId('leveraged-etf-mapper')).toBeInTheDocument();
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

  it('falls back to the first filtered symbol when the focused detail row is filtered out', async () => {
    renderWatchlist();

    await screen.findByTestId('watchlist-row-NVDA');
    fireEvent.click(screen.getByRole('button', { name: '查看详情 TSM' }));
    await waitFor(() => expect(screen.getByTestId('watchlist-detail-rail')).toHaveTextContent('TSM'));

    fireEvent.change(screen.getByLabelText('市场'), { target: { value: 'us' } });

    await waitFor(() => expect(screen.queryByTestId('watchlist-row-TSM')).not.toBeInTheDocument());
    expect(screen.getByTestId('watchlist-detail-rail')).toHaveTextContent('NVDA');
    expect(screen.getByTestId('watchlist-action-scope')).toHaveTextContent('当前筛选 1 个标的');
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
    expect(within(row).getByText(/更新 05\/03 17:01 · 命中 56% · 回测 \+14.2%/)).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-detail-rail')).toHaveTextContent(/收益 \+14.2% · 回撤 -3.2% · Sharpe 1.50 · 交易 5/);
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
    expect(runtimeStatus).toHaveTextContent('定时更新');
    expect(runtimeStatus).toHaveTextContent('处理状态');
    expect(runtimeStatus).not.toHaveTextContent(/runtime|批量进度|自动刷新/i);
    expect(screen.getAllByText('评分已刷新').length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: /刷新评分/ }));

    await waitFor(() => expect(refreshScores).toHaveBeenCalledWith({ force: true }));
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('评分已刷新。 3/3'));
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

  it('renders a mobile-safe empty state with manual research as the primary path', async () => {
    listWatchlistItems.mockResolvedValue({ items: [] });

    renderWatchlist();

    const watchBoard = await screen.findByTestId('watchlist-watch-board');
    const headerStrip = screen.getByTestId('watchlist-header-strip');
    const primaryWorkRegion = screen.getByTestId('watchlist-primary-work-region');
    const emptyState = await screen.findByTestId('watchlist-compact-empty-state');
    expect(watchBoard).toContainElement(primaryWorkRegion);
    expect(primaryWorkRegion).toContainElement(emptyState);
    expect(emptyState).toHaveClass(
      'min-h-[168px]',
      'flex-col',
      'items-center',
      'justify-center',
      'sm:items-center',
      'rounded-none',
      'border-0',
      'max-w-3xl',
      'text-center',
    );
    expect(within(emptyState).getByText('还没有观察标的')).toBeInTheDocument();
    expect(emptyState).toHaveTextContent('当前已保存覆盖下还没有可用观察行。可先在这里手动研究一个代码，确认后再决定是否保存到观察列表。');
    expect(emptyState).toHaveTextContent('只有你明确保留观察后，已保存的候选证据与状态才会回到这里。');
    expect(emptyState).toHaveTextContent('如果后续需要批量筛选，扫描器仍可作为辅助入口。');
    const preview = within(emptyState).getByTestId('watchlist-empty-preview');
    expect(preview).toHaveTextContent('功能预览');
    expect(preview).toHaveTextContent('示例预览');
    expect(preview).toHaveTextContent('保存观察');
    expect(preview).toHaveTextContent('证据状态');
    expect(preview).toHaveTextContent('下一步研究');
    expect(preview).toHaveTextContent('不会持久化');
    expect(preview).toHaveTextContent('不计入观察名单数量');
    expect(preview).toHaveTextContent('不会进入扫描器官方排名');
    const researchPath = within(emptyState).getByTestId('watchlist-empty-manual-research');
    expect(researchPath).toHaveTextContent('首选研究路径');
    expect(researchPath).toHaveTextContent('手动研究代码');
    expect(researchPath).toHaveTextContent('首选路径：先启动一个个股研究任务，不会把代码加入观察名单。');
    expect(within(emptyState).getByLabelText('手动研究代码')).toBeInTheDocument();
    expect(emptyState).not.toHaveTextContent(/数据不足，禁止判断|买入|卖出|下单|交易|券商|broker/i);
    expect(within(headerStrip).queryByRole('button', { name: /打开扫描器/ })).not.toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-compact-filter-bar')).not.toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-advanced-filters')).not.toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-list-header')).not.toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-secondary-deck')).not.toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-command-bar')).not.toBeInTheDocument();

    const emptyStateScannerAction = within(emptyState).getByRole('button', { name: /稍后打开扫描器/ });
    expect(screen.getAllByRole('button', { name: /稍后打开扫描器/ })).toHaveLength(1);

    fireEvent.click(emptyStateScannerAction);
    expect(screen.getByText('scanner')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/zh/scanner');
  });

  it('starts manual research from the empty watchlist without creating a preview item', async () => {
    listWatchlistItems.mockResolvedValue({ items: [] });

    renderWatchlist();

    const emptyState = await screen.findByTestId('watchlist-compact-empty-state');
    expect(within(emptyState).getByTestId('watchlist-empty-manual-research')).toHaveTextContent('首选研究路径');
    fireEvent.change(within(emptyState).getByLabelText('手动研究代码'), { target: { value: 'tsla' } });
    fireEvent.click(within(emptyState).getByRole('button', { name: /研究 TSLA/ }));

    await waitFor(() => {
      expect(analyzeAsync).toHaveBeenCalledWith(expect.objectContaining({
        stockCode: 'TSLA',
        reportType: 'detailed',
        stockName: 'TSLA',
        originalQuery: 'TSLA',
        selectionSource: 'manual',
      }));
    });
    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/zh?symbol=TSLA');
    });
    expect(listWatchlistItems).toHaveBeenCalledTimes(1);
  });

  it('keeps batch actions and auto refresh in compact product-labeled rows', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    expect(screen.getByTestId('watchlist-command-bar')).toHaveTextContent('批量操作');
    expect(screen.getByTestId('watchlist-command-bar')).toHaveTextContent('处理状态');
    expect(screen.getByTestId('watchlist-command-bar')).toHaveTextContent('刷新当前筛选');
    expect(screen.getByTestId('watchlist-command-bar')).toHaveTextContent('回测当前筛选');
    expect(screen.getByRole('button', { name: '刷新观察依据' })).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-runtime-status')).toHaveTextContent('定时更新');
    expect(screen.getByTestId('watchlist-page')).not.toHaveTextContent(/runtime|批量进度|自动刷新/i);
  });

  it('renders the authentication guard for guests', () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: true });

    renderWatchlist();

    expect(screen.getByText('auth-guard:观察列表')).toBeInTheDocument();
    expect(listWatchlistItems).not.toHaveBeenCalled();
  });
});
