import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import WatchlistPage from '../WatchlistPage';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import type { WatchlistItem, WatchlistScannerLineageV1 } from '../../types/watchlist';
import type { RuleBacktestRunResponse } from '../../types/backtest';

const { listWatchlistItems, addWatchlistItem, removeWatchlistItem, refreshScores, getRefreshStatus, getResearchOverlay, runRuleBacktest, analyzeAsync, useProductSurfaceMock } = vi.hoisted(() => ({
  listWatchlistItems: vi.fn(),
  addWatchlistItem: vi.fn(),
  removeWatchlistItem: vi.fn(),
  refreshScores: vi.fn(),
  getRefreshStatus: vi.fn(),
  getResearchOverlay: vi.fn(),
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
    addWatchlistItem,
    removeWatchlistItem,
    refreshScores,
    getRefreshStatus,
    getResearchOverlay,
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
let resolvePendingListRules: Array<(value: ReturnType<typeof makeUserAlertRulesResponse>) => void> = [];

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
          <Route path="/zh/stocks/:stockCode/structure-decision" element={<><div>stock structure</div><LocationProbe /></>} />
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

function makeUserAlertRulesResponse(items: ReturnType<typeof makeUserAlertRule>[] = []) {
  return {
    contractVersion: 'user_alert_contract_v1',
    deliveryMode: 'in_app',
    inAppOnly: true,
    ownerScoped: true,
    items,
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
    resolvePendingListRules = [];
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
    getResearchOverlay.mockResolvedValue({
      schemaVersion: 'watchlist_research_overlay_v1',
      overlayState: 'ready',
      researchSummary: 'Saved symbols are ready for observation.',
      researchPriorityQueue: [],
      observationOnly: true,
      decisionGrade: false,
    });
    runRuleBacktest.mockResolvedValue(makeRuleBacktestRun());
    analyzeAsync.mockResolvedValue({ taskId: 'task-1' });
    listRules.mockImplementation(() => new Promise((resolve) => {
      resolvePendingListRules.push(resolve);
    }));
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
    const pendingListRules = resolvePendingListRules.splice(0);
    pendingListRules.forEach((resolve) => resolve(makeUserAlertRulesResponse()));
    await flushPendingUiWork();
    vi.restoreAllMocks();
  });

  it('renders tracked candidates from the watchlist API', async () => {
    renderWatchlist();

    expect(await screen.findByTestId('watchlist-row-NVDA')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '观察监控板' })).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-header-strip')).toHaveTextContent('监控队列');
    expect(screen.queryByText('紧凑观察队列')).not.toBeInTheDocument();
    expect(screen.queryByText(/Track scanner candidates/i)).not.toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-TSM')).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-600519')).toBeInTheDocument();
    expect(screen.queryByText('Details')).not.toBeInTheDocument();
    expect(screen.getByTestId('watchlist-filter-grid')).toHaveClass('grid', 'grid-cols-1', 'sm:grid-cols-2');
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

  it('keeps initial loading distinct from a confirmed empty watchlist', async () => {
    let resolveList: (response: { items: WatchlistItem[] }) => void = () => undefined;
    listWatchlistItems.mockImplementationOnce(() => new Promise<{ items: WatchlistItem[] }>((resolve) => {
      resolveList = resolve;
    }));

    renderWatchlist();

    expect(screen.getByText('正在加载观察列表...')).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-ledger-scroll-region')).toHaveAttribute('aria-busy', 'true');
    expect(screen.queryByTestId('watchlist-compact-empty-state')).not.toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-status-strip')).not.toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-conclusion-band')).not.toBeInTheDocument();

    await act(async () => {
      resolveList({ items: [] });
    });

    expect(await screen.findByTestId('watchlist-compact-empty-state')).toBeInTheDocument();
    expect(screen.queryByText('正在加载观察列表...')).not.toBeInTheDocument();
    expect(screen.getByTestId('watchlist-ledger-scroll-region')).toHaveAttribute('aria-busy', 'false');
    expect(screen.getByTestId('watchlist-status-strip')).toBeInTheDocument();
  });

  it('keeps a watchlist request failure separate from the successful empty state', async () => {
    listWatchlistItems.mockRejectedValue(Object.assign(new Error('watchlist unavailable'), {
      status: 503,
      parsedError: {
        title: 'backend error',
        message: 'watchlist unavailable',
        rawMessage: 'watchlist unavailable',
        status: 503,
        category: 'upstream_unavailable',
        isAuthError: false,
      },
    }));

    renderWatchlist();

    expect(await screen.findByText('观察列表暂不可用')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-compact-empty-state')).not.toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-status-strip')).not.toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-conclusion-band')).not.toBeInTheDocument();
    expect(screen.getByTestId('watchlist-ledger-scroll-region')).toHaveAttribute('aria-busy', 'false');
  });

  it('filters scanner handoff routes to existing watchlist records without writes', async () => {
    renderWatchlist('/watchlist?symbol=TSM&market=HK&source=scanner');

    const row = await screen.findByTestId('watchlist-row-TSM');
    expect(row).toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-row-NVDA')).not.toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-row-600519')).not.toBeInTheDocument();

    const panel = await screen.findByTestId('watchlist-research-workspace-flow');
    // G025: research handoff sits after the ledger (secondary deck), not above the task board.
    expect(screen.getByTestId('watchlist-secondary-deck')).toContainElement(panel);
    expect(screen.getByTestId('watchlist-header-strip')).toHaveAttribute(
      'data-watchlist-sequence',
      'needs-review-important-changes-ledger-handoff',
    );
    expect(panel).toHaveTextContent('TSM');
    expect(panel).not.toHaveTextContent(/Run #|Rank #|scannerRunId|watchlistItemId|provider|cache|runtime|debug/i);
    expect(within(panel).getByTestId('research-workspace-link-stock-structure')).toHaveAttribute('href', expect.stringContaining('/stocks/TSM/structure-decision?'));
    for (const link of within(panel).getAllByRole('link')) {
      expect(link).toHaveAttribute('href', expect.not.stringMatching(/scannerRunId|scannerRank|watchlistItemId|themeId|universeType|provider|cache|runtime|debug/i));
    }

    expect(addWatchlistItem).not.toHaveBeenCalled();
    expect(refreshScores).not.toHaveBeenCalled();
    expect(runRuleBacktest).not.toHaveBeenCalled();
    expect(analyzeAsync).not.toHaveBeenCalled();
    expect(createRule).not.toHaveBeenCalled();
    expect(updateRule).not.toHaveBeenCalled();
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
    expect(screen.getByRole('table', { name: '观察列表研究台账' })).toBe(screen.getByTestId('watchlist-candidate-list'));
    expect(screen.getByTestId('watchlist-candidate-list')).toHaveAttribute('data-linear-primitive', 'dense-rows');
    expect(screen.getByTestId('watchlist-candidate-list')).toHaveClass('min-w-0', 'lg:min-w-[860px]');
    const ledgerScrollRegion = screen.getByRole('region', { name: '观察列表台账横向滚动区域' });
    expect(ledgerScrollRegion).toBe(screen.getByTestId('watchlist-ledger-scroll-region'));
    expect(ledgerScrollRegion).toHaveAttribute('tabindex', '0');
    expect(ledgerScrollRegion).toHaveAttribute('aria-describedby', 'watchlist-ledger-scroll-help');
    expect(document.getElementById('watchlist-ledger-scroll-help')).toHaveTextContent('在较宽布局中，可横向滚动此台账以查看全部列和行操作。');
    expect(ledgerScrollRegion).toHaveClass('overflow-x-hidden', 'overscroll-x-contain', 'lg:overflow-x-auto');
    expect(screen.getByTestId('watchlist-list-header')).toHaveAttribute('role', 'row');
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
    expect(band).toHaveTextContent(/当前数据置信度较低|历史观察|不代表实时信号/);
    expect(band).not.toHaveTextContent(/fallback|proxy|备用\/代理|备用数据|代理证据|reasonFamilies|sourceAuthorityAllowed|scoreContributionAllowed/i);
    expect(band).not.toHaveTextContent(/买入|卖出|加仓|减仓|buy|sell|recommend(?:ation)?/i);
  });

  it('renders a compact consumer observation board with actionable partial states', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [
        makeItem({
          id: 41,
          symbol: 'AAPL',
          market: 'us',
          name: 'Apple',
          source: 'manual',
          scannerRunId: null,
          scannerRank: null,
          scannerScore: null,
          lastScoredAt: null,
          scoreSource: null,
          scoreStatus: null,
          intelligence: undefined,
          rowResearchPacket: {
            symbol: 'AAPL',
            market: 'us',
            identity: {
              name: 'Apple',
              exchange: 'NASDAQ',
              sector: 'Technology',
              industry: 'Consumer Electronics',
            },
            savedItemSource: 'manual',
            quote: {
              state: 'available',
              price: 190.25,
              changePercent: -0.42,
              asOf: '2026-05-01T11:00:00Z',
            },
            scannerLineage: {
              runId: null,
              rank: null,
              score: null,
              status: null,
              lastScoredAt: null,
            },
            researchStatus: 'partial',
            missingData: [
              'fundamentals',
              'filing_event_catalyst',
              'peer_benchmark',
              'provider_runtime_trace',
              'sourceAuthority',
              'buy setup',
            ],
            nextDataAction: 'Add fundamentals, filing/event/catalyst, and peer evidence before marking the packet ready.',
            observationOnly: true,
            noAdviceDisclosure: 'Observation-only research packet; not personalized financial advice and not an instruction.',
          },
          createdAt: '2026-04-10T08:00:00Z',
          updatedAt: '2026-05-01T10:05:00Z',
        }),
        makeItem({
          id: 42,
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

    const board = await screen.findByTestId('watchlist-consumer-observation-board');
    expect(board).toHaveTextContent('重要变化');
    expect(board).toHaveTextContent('观察列表');
    expect(board).toHaveTextContent('正在观察 2 个标的');
    expect(board).toHaveTextContent('可用报价 1');
    expect(board).toHaveTextContent('需补资料 2');
    expect(board).toHaveTextContent('AAPL');
    expect(board).toHaveTextContent('$190.3');
    expect(board).toHaveTextContent('-0.42%');
    expect(board).toHaveTextContent('研究包部分可用');
    expect(board).toHaveTextContent('复核缺口：基本面、事件、同业');
    expect(board).toHaveTextContent('查看个股结构');
    expect(board).toHaveTextContent('SHOP');
    expect(board).toHaveTextContent('报价暂缺');
    expect(board).toHaveTextContent('先打开个股结构页，仍可查看已保存信息。');
    expect(within(board).getByTestId('watchlist-observation-actions-SHOP').querySelectorAll('button')).toHaveLength(2);
    expect(board).not.toHaveTextContent(/打开研究雷达|Open Research Radar view/);
    expect(board).not.toHaveTextContent(/待补.*待补.*待补.*待补/s);
    expect(board).not.toHaveTextContent(/available|missing|not configured|provider_missing|blockedProductSurfaces|missingDataFamilies|sourceClass|sourcePath|contractVersion|inputSource|noExternalCalls|providerCallsEnabled|not_requested|provider|runtime|schema|requestId|traceId|raw|observationOnly|buy setup|buy|sell|hold|target price|position sizing|买入|卖出|持有|目标价|仓位/i);

    fireEvent.click(within(board).getByRole('button', { name: '查看 AAPL 详情' }));
    const detail = screen.getByTestId('watchlist-consumer-detail-panel');
    expect(detail).toHaveTextContent('AAPL');
    expect(detail).toHaveTextContent('Apple · US');
    expect(detail).toHaveTextContent('最新报价 $190.3');
    expect(detail).toHaveTextContent('资料缺口：基本面、事件、同业');
    expect(detail).toHaveTextContent('下一步：查看个股结构');
    expect(detail).not.toHaveTextContent(/provider|runtime|schema|observationOnly|buy setup|not personalized financial advice|instruction/i);
  });

  it('renders a compact research queue from the watchlist overlay without changing saved rows', async () => {
    getResearchOverlay.mockResolvedValue({
      schemaVersion: 'watchlist_research_overlay_v1',
      overlayState: 'degraded',
      researchSummary: 'Some saved symbols need evidence review.',
      researchPriorityQueue: [
        {
          symbol: 'MSFT',
          priorityTier: 'attention',
          priorityReasonSafeLabel: 'Missing evidence needs review.',
          evidenceAge: { state: 'no_evidence', lastReviewedAt: null },
          missingEvidence: ['Price-history evidence', 'Scanner score evidence'],
          suggestedResearchPath: [
            {
              label: 'Stock Structure',
              route: '/stocks/MSFT/structure-decision',
              section: 'watchlistResearchOverlay',
              reason: 'Open symbol structure detail.',
            },
          ],
          observationOnly: true,
        },
        {
          symbol: 'NVDA',
          priorityTier: 'follow_up',
          priorityReasonSafeLabel: 'Evidence needs refresh.',
          evidenceAge: { state: 'stale_or_cached', lastReviewedAt: '2026-05-01T12:30:00Z' },
          missingEvidence: ['Supporting evidence'],
          suggestedResearchPath: [
            {
              label: 'Stock Structure',
              route: '/stocks/NVDA/structure-decision',
              section: 'watchlistResearchOverlay',
              reason: 'Review structure detail.',
            },
          ],
          observationOnly: true,
        },
        {
          symbol: 'BABA',
          priorityTier: 'monitor',
          priorityReasonSafeLabel: 'Queue review pending from backend memo',
          evidenceAge: { state: 'provider_trace_pending', lastReviewedAt: null },
          missingEvidence: ['provider_runtime_trace', 'buy setup'],
          suggestedResearchPath: [
            {
              label: 'queue_debug_path',
              route: '/stocks/BABA/structure-decision',
              section: 'watchlistResearchOverlay',
              reason: 'provider_runtime_trace',
            },
          ],
          observationOnly: true,
        },
      ],
      observationOnly: true,
      decisionGrade: false,
    });

    renderWatchlist();

    await screen.findByTestId('watchlist-row-NVDA');
    const queue = await screen.findByTestId('watchlist-research-queue');
    expect(queue).toHaveTextContent('后续研究');
    expect(queue).toHaveTextContent('MSFT');
    expect(queue).toHaveTextContent('建议复核');
    expect(queue).toHaveTextContent('研究上下文待补');
    expect(queue).toHaveTextContent('缺少关键证据');
    expect(queue).toHaveTextContent('价格与历史数据待补');
    expect(queue).toHaveTextContent('扫描评分待更新');
    expect(queue).toHaveTextContent('查看个股结构');
    expect(queue).toHaveTextContent('待核对：价格与历史数据待补、扫描评分待更新');
    expect(queue).toHaveTextContent('先核对结构与资料完整性。');
    expect(queue).toHaveTextContent('NVDA');
    expect(queue).toHaveTextContent('持续跟进');
    expect(queue).toHaveTextContent('现有证据时效不足，建议先复核近期价格、同业与市场背景。');
    expect(queue).toHaveTextContent('研究上下文待补');
    expect(queue).toHaveTextContent('查看个股结构，补做资料核对。');
    expect(queue).toHaveTextContent('BABA');
    expect(queue).toHaveTextContent('继续观察');
    expect(queue).toHaveTextContent('当前条目的证据覆盖仍需复核。');
    expect(queue).toHaveTextContent('证据待确认');
    expect(queue).toHaveTextContent('部分外部数据暂不可用');
    expect(queue).not.toHaveTextContent(/证据缺口|仅作研究观察|不构成操作结论/);
    expect(queue).not.toHaveTextContent(/buy|sell|hold|recommend(?:ation)?|target|stop|position sizing|买入|卖出|持有|目标价|止损|仓位/i);
    expect(queue).not.toHaveTextContent(/Missing evidence needs review|Price-history evidence|Scanner score evidence|Queue review pending from backend memo|evidence_missing|attention|follow_up|provider|source|runtime|debug|request[_\s-]?id|trace[_\s-]?id|schemaVersion|raw|internal|cache|observationOnly|queue_debug_path/i);

    const rowIds = Array.from(document.querySelectorAll('[role="row"][data-testid^="watchlist-row-"]'))
      .map((row) => row.getAttribute('data-testid'));
    expect(rowIds).toEqual(['watchlist-row-NVDA', 'watchlist-row-TSM', 'watchlist-row-600519']);
    expect(addWatchlistItem).not.toHaveBeenCalled();
    expect(removeWatchlistItem).not.toHaveBeenCalled();
    expect(refreshScores).not.toHaveBeenCalled();
    expect(runRuleBacktest).not.toHaveBeenCalled();
    expect(analyzeAsync).not.toHaveBeenCalled();
  });

  it('shows a neutral research queue state when the overlay queue is empty', async () => {
    renderWatchlist();

    await screen.findByTestId('watchlist-row-NVDA');
    const queue = await screen.findByTestId('watchlist-research-queue');
    expect(queue).toHaveTextContent('研究队列');
    expect(queue).toHaveTextContent('暂无需要跟进的研究队列');
    expect(queue).toHaveTextContent('继续保持观察，不会自动创建任务或更改观察列表。');
    expect(queue).not.toHaveTextContent(/error|failed|错误|失败|买入|卖出|交易|下单|recommend/i);
  });

  it('shows overlay-specific unavailable state without hiding valid watchlist rows when overlay request fails', async () => {
    const overlayFailure = Object.assign(new Error('GET /api/v1/watchlist/research-overlay provider runtime requestId=req-1 stack trace'), {
      status: 503,
      parsedError: {
        title: 'backend error',
        message: 'GET /api/v1/watchlist/research-overlay provider runtime requestId=req-1 stack trace',
        rawMessage: 'provider runtime requestId=req-1 stack trace',
        status: 503,
        category: 'upstream_unavailable',
        isAuthError: false,
      },
    });
    getResearchOverlay.mockRejectedValue(overlayFailure);

    renderWatchlist();

    expect(await screen.findByTestId('watchlist-row-NVDA')).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-TSM')).toBeInTheDocument();
    const queue = await screen.findByTestId('watchlist-research-queue');
    expect(queue).toHaveTextContent('后续研究暂时无法读取');
    expect(queue).toHaveTextContent('观察列表仍可使用；稍后重试研究跟进视图。');
    expect(queue).not.toHaveTextContent('暂无需要跟进的研究队列');
    expect(queue).not.toHaveTextContent(/GET \/api\/v1|provider|runtime|requestId|stack|backend error|rawMessage|503|买入|卖出|交易|下单|recommend/i);
    expect(listWatchlistItems).toHaveBeenCalledTimes(1);
    expect(getResearchOverlay).toHaveBeenCalledTimes(1);
    expect(addWatchlistItem).not.toHaveBeenCalled();
    expect(removeWatchlistItem).not.toHaveBeenCalled();
    expect(refreshScores).not.toHaveBeenCalled();
    expect(runRuleBacktest).not.toHaveBeenCalled();
    expect(analyzeAsync).not.toHaveBeenCalled();
  });

  it('keeps manual overlay refresh failure separate from a legitimate empty queue', async () => {
    const overlayFailure = Object.assign(new Error('research overlay unavailable requestId=req-2'), {
      status: 503,
      parsedError: {
        title: 'backend error',
        message: 'research overlay unavailable requestId=req-2',
        rawMessage: 'research overlay unavailable requestId=req-2',
        status: 503,
        category: 'upstream_unavailable',
        isAuthError: false,
      },
    });
    getResearchOverlay
      .mockResolvedValueOnce({
        schemaVersion: 'watchlist_research_overlay_v1',
        overlayState: 'ready',
        researchSummary: 'Saved symbols are ready for observation.',
        researchPriorityQueue: [
          {
            symbol: 'NVDA',
            priorityTier: 'attention',
            priorityReasonSafeLabel: 'Research context needs attention.',
            evidenceAge: { state: 'unknown', lastReviewedAt: null },
            missingEvidence: ['Research context'],
            suggestedResearchPath: [],
            observationOnly: true,
          },
        ],
        observationOnly: true,
        decisionGrade: false,
      })
      .mockRejectedValueOnce(overlayFailure);

    renderWatchlist();

    expect(await screen.findByTestId('watchlist-row-NVDA')).toBeInTheDocument();
    const queue = await screen.findByTestId('watchlist-research-queue');
    expect(queue).toHaveTextContent('NVDA');

    fireEvent.click(screen.getByRole('button', { name: '刷新观察依据' }));

    await waitFor(() => expect(queue).toHaveTextContent('后续研究暂时无法读取'));
    expect(queue).not.toHaveTextContent('暂无需要跟进的研究队列');
    expect(screen.getByTestId('watchlist-row-NVDA')).toBeInTheDocument();
    expect(listWatchlistItems).toHaveBeenCalledTimes(2);
    expect(getResearchOverlay).toHaveBeenCalledTimes(2);
    expect(refreshScores).not.toHaveBeenCalled();
    expect(addWatchlistItem).not.toHaveBeenCalled();
    expect(removeWatchlistItem).not.toHaveBeenCalled();
    expect(queue).not.toHaveTextContent(/requestId|backend error|503|provider|runtime|stack|买入|卖出|交易|recommend/i);
  });

  it('keeps authentication failure handling when the overlay request returns auth required', async () => {
    const unauthorized = Object.assign(new Error('provider runtime requestId=req-1 token=bearer-secret unauthorized'), {
      status: 401,
      parsedError: {
        title: '登录已失效，请重新登录。',
        message: '登录已失效，请重新登录。',
        rawMessage: 'provider runtime requestId=req-1 token=bearer-secret unauthorized',
        status: 401,
        category: 'auth_required',
        isAuthError: true,
      },
    });
    getResearchOverlay.mockRejectedValue(unauthorized);

    renderWatchlist();

    expect(await screen.findByText('auth-guard:观察列表')).toBeInTheDocument();
    expect(document.body.textContent || '').not.toMatch(/provider runtime|requestId|bearer-secret|rawMessage|traceId|debug|stack/i);
    expect(addWatchlistItem).not.toHaveBeenCalled();
    expect(removeWatchlistItem).not.toHaveBeenCalled();
    expect(refreshScores).not.toHaveBeenCalled();
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
    expect(band).toHaveTextContent('证据待确认');
    expect(band).toHaveTextContent('需要留意');
    expect(band).toHaveTextContent('观察标的 2');
    expect(band).toHaveTextContent('最新0');
    expect(band).toHaveTextContent('需留意3');
    expect(band).toHaveTextContent('部分项目时效未知，先复核已保存研究上下文。');
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

    const rows = Array.from(screen.getByTestId('watchlist-candidate-list').querySelectorAll('[role="row"][data-testid^="watchlist-row-"]'));
    expect(within(rows[0] as HTMLElement).getByText('NVDA')).toBeInTheDocument();
    expect(within(rows[1] as HTMLElement).getByText('TSM')).toBeInTheDocument();
    expect(within(rows[2] as HTMLElement).getByText('600519')).toBeInTheDocument();
  });

  it('renders compact scanner, strategy simulation, and backtest intelligence chips in Chinese', async () => {
    renderWatchlist();
    const row = await screen.findByTestId('watchlist-row-NVDA');

    expect(within(row).getByText(/分数 94.0 · 历史 \+3.2% · 命中 56%/)).toBeInTheDocument();
    expect(within(row).getByText('价格暂缺')).toBeInTheDocument();
    expect(within(row).getByText('研究已更新')).toBeInTheDocument();
    expect(within(row).getByText('已回测')).toBeInTheDocument();
    expect(within(row).getByText(/更新 05\/01 13:30 · 命中 56% · 回测 \+24.6%/)).toBeInTheDocument();
    fireEvent.click(within(row).getByRole('button', { name: '更多操作 NVDA' }));
    fireEvent.click(within(row).getByRole('button', { name: /结果 33/ }));
    expect(screen.getByText('backtest result')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/zh/backtest/results/33');
  });

  it('keeps a 600519-style saved row useful when price and name are missing', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [makeItem({
        id: 18,
        symbol: '600519',
        market: 'cn',
        name: null,
        source: 'manual',
        scannerRunId: 39,
        scannerRank: 8,
        scannerScore: 77,
        lastScoredAt: null,
        scoreSource: 'scanner_run',
        scoreStatus: 'stale',
        intelligence: {
          scanner: {
            lastScore: 77,
            lastRank: 8,
            status: 'selected',
            theme: null,
            themeLabel: null,
            profile: null,
            reason: 'Latest scanner score.',
            lastScannedAt: '2026-05-01T10:10:00Z',
          },
          strategySimulation: { status: 'unknown' },
          backtest: {},
        },
        rowResearchPacket: {
          symbol: '600519',
          market: 'cn',
          identity: {
            name: null,
            exchange: null,
            sector: null,
            industry: null,
          },
          savedItemSource: 'manual',
          quote: {
            state: 'missing',
            price: null,
            changePercent: null,
            asOf: null,
          },
          scannerLineage: {
            runId: null,
            rank: null,
            score: null,
            status: null,
            lastScoredAt: null,
          },
          researchStatus: 'blocked',
          missingData: [
            'quote',
            'price_history',
            'fundamentals',
            'filing_event_catalyst',
            'peer_benchmark',
            'Missing evidence needs review',
            'Price-history evidence',
            'Scanner score evidence',
            'evidence_gap',
            'not_integrated',
          ],
          nextDataAction: 'Add quote and daily price history evidence before marking the packet ready.',
          observationOnly: true,
          noAdviceDisclosure: 'Observation-only research packet; not personalized financial advice and not an instruction.',
        },
        createdAt: '2026-04-10T08:00:00Z',
        updatedAt: '2026-05-01T10:05:00Z',
      })],
    });
    getResearchOverlay.mockResolvedValue({
      schemaVersion: 'watchlist_research_overlay_v1',
      overlayState: 'degraded',
      researchSummary: 'Missing evidence needs review.',
      researchPriorityQueue: [
        {
          symbol: '600519',
          priorityTier: 'attention',
          priorityReasonSafeLabel: 'Missing evidence needs review.',
          evidenceAge: { state: 'no_evidence', lastReviewedAt: null },
          missingEvidence: ['Price-history evidence', 'Scanner score evidence', 'Supporting evidence', 'provider_runtime_trace', 'insufficient_evidence'],
          suggestedResearchPath: [
            {
              label: 'Stock Structure',
              route: '/stocks/600519/structure-decision',
              section: 'watchlistResearchOverlay',
              reason: 'Open symbol structure detail.',
            },
          ],
          observationOnly: true,
        },
      ],
      observationOnly: true,
      decisionGrade: false,
    });

    renderWatchlist();

    const row = await screen.findByTestId('watchlist-row-600519');
    const primaryRegion = screen.getByTestId('watchlist-board-shell');
    expect(row).toHaveTextContent('600519');
    expect(row).toHaveTextContent('A股 600519');
    expect(row).toHaveTextContent('报价待补');
    expect(row).toHaveTextContent('数据待补');
    expect(row).toHaveTextContent('待扫描');
    expect(row).toHaveTextContent('报价与历史待补');
    expect(row).toHaveTextContent('基本面、事件、同业待补');
    expect(row).toHaveTextContent('下一步 补报价与历史');
    expect(row).toHaveTextContent('仅供观察');
    const queue = await screen.findByTestId('watchlist-research-queue');
    expect(queue).toHaveTextContent('研究上下文待补');
    expect(queue).toHaveTextContent('价格与历史数据待补');
    expect(queue).toHaveTextContent('扫描评分待更新');
    expect(within(row).getByRole('button', { name: '查看个股结构 600519' })).toBeInTheDocument();
    expect(within(row).getByRole('button', { name: '更多操作 600519' })).toHaveAttribute('aria-expanded', 'false');
    expect(within(row).queryByRole('button', { name: '打开扫描器 600519' })).not.toBeInTheDocument();
    fireEvent.click(within(row).getByRole('button', { name: '更多操作 600519' }));
    expect(within(row).getByRole('button', { name: '更多操作 600519' })).toHaveAttribute('aria-expanded', 'true');
    expect(within(row).getByRole('button', { name: '打开扫描器 600519' })).toBeInTheDocument();
    expect(within(row).getByRole('button', { name: '分析' })).toBeInTheDocument();
    expect(within(row).getByRole('button', { name: '回测' })).toBeInTheDocument();
    expect(within(row).getByRole('button', { name: '复制代码 600519' })).toBeInTheDocument();
    expect(within(row).getByRole('button', { name: '移除 600519' })).toBeInTheDocument();
    expect(row).not.toHaveTextContent('--');
    expect(primaryRegion).not.toHaveTextContent(/证据缺口|Missing evidence needs review|Price-history evidence|Scanner score evidence|evidence_gap|available|missing|stale|unknown|not_integrated|insufficient|ready|partial|blocked|observationOnly|noAdviceDisclosure|provider|cache|runtime|schema|requestId|traceId|fallback|proxy|sourceAuthority|score-grade|observation-only|insufficient_evidence|not personalized financial advice|not an instruction/i);
    expect(queue).not.toHaveTextContent(/Missing evidence needs review|Price-history evidence|Scanner score evidence|provider|cache|runtime|schema|requestId|traceId|fallback|proxy|sourceAuthority|score-grade|observation-only|insufficient_evidence/i);
    expect(primaryRegion).not.toHaveTextContent(/买入|卖出|持有|目标价|止损|仓位|建仓|加仓|减仓|buy|sell|hold|target price|stop-loss|position sizing/i);

    fireEvent.click(within(row).getByRole('button', { name: '查看个股结构 600519' }));
    expect(screen.getByText('stock structure')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/zh/stocks/600519/structure-decision');
  });

  it('renders row decision context for partial packets without raw diagnostics or advice wording', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [makeItem({
        id: 19,
        symbol: 'AAPL',
        market: 'us',
        name: 'Apple',
        source: 'manual',
        scannerRunId: null,
        scannerRank: null,
        scannerScore: null,
        lastScoredAt: null,
        scoreSource: null,
        scoreStatus: null,
        intelligence: undefined,
        rowResearchPacket: {
          symbol: 'AAPL',
          market: 'us',
          identity: {
            name: 'Apple',
            exchange: 'NASDAQ',
            sector: 'Technology',
            industry: 'Consumer Electronics',
          },
          savedItemSource: 'manual',
          quote: {
            state: 'stale',
            price: 190.25,
            changePercent: -0.42,
            asOf: '2026-05-01T11:00:00Z',
          },
          scannerLineage: {
            runId: null,
            rank: null,
            score: null,
            status: null,
            lastScoredAt: null,
          },
          researchStatus: 'partial',
          missingData: [
            'fundamentals',
            'filing_event_catalyst',
            'peer_benchmark',
            'provider_runtime_trace',
            'sourceAuthority',
            'buy setup',
          ],
          nextDataAction: 'Add fundamentals, filing/event/catalyst, and peer evidence before marking the packet ready.',
          observationOnly: true,
          noAdviceDisclosure: 'Observation-only research packet; not personalized financial advice and not an instruction.',
        },
        createdAt: '2026-04-10T08:00:00Z',
        updatedAt: '2026-05-01T10:05:00Z',
      })],
    });

    renderWatchlist();

    const row = await screen.findByTestId('watchlist-row-AAPL');
    const context = within(row).getByTestId('watchlist-row-decision-context-AAPL');

    expect(row).toHaveTextContent('$190.3');
    expect(context).toHaveTextContent('研究状态');
    expect(context).toHaveTextContent('报价可能延迟');
    expect(context).toHaveTextContent('研究包部分可用');
    expect(context).toHaveTextContent('证据部分可用');
    expect(context).toHaveTextContent('待补证据 3项');
    expect(context).toHaveTextContent('风险线索待补');
    expect(context).toHaveTextContent('评分待确认');
    expect(context).toHaveTextContent('仅观察');
    expect(context).toHaveTextContent('待补：基本面、事件、同业');
    expect(context).toHaveTextContent('查看证据栈');
    expect(within(row).getByRole('button', { name: '查看证据栈 AAPL' })).toBeInTheDocument();
    expect(row).not.toHaveTextContent(/provider|runtime|credential|sourceAuthority|fallback|debug|Alpaca|回退观察|buy setup|financial advice|instruction|买入建议|卖出建议|持有建议|目标价|止损|仓位建议|交易建议|操作建议/i);
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
    expect(within(row).getByText('研究暂不可用')).toBeInTheDocument();
    expect(within(row).getByText('样本不足')).toBeInTheDocument();
    expect(within(row).getByTestId('watchlist-row-note-MARA')).toHaveTextContent('价格暂缺，按下一步补充。');
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
    expect(within(row).getByText('价格暂缺')).toBeInTheDocument();
    expect(within(row).getByText('研究待补充')).toBeInTheDocument();
    expect(within(row).getByTestId('watchlist-row-note-MARA')).toHaveTextContent('价格、研究状态暂缺，按下一步补充。');
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
    expect(row).toHaveTextContent('研究待复核');
    expect(row).toHaveTextContent('价格暂缺，按下一步补充。');
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
    expect(row).toHaveTextContent('研究已更新');
    expect(row).toHaveTextContent('价格暂缺，按下一步补充。');
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
    expect(cachedRow).toHaveTextContent('研究待复核');
    expect(cachedRow).toHaveTextContent('价格暂缺，按下一步补充。');
    expect(blockedRow).toHaveTextContent('研究待复核');
    expect(blockedRow).toHaveTextContent('价格暂缺，按下一步补充。');
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
    expect(row).toHaveTextContent('研究待复核');
    expect(row).toHaveTextContent('价格暂缺，按下一步补充。');
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
    expect(row).toHaveTextContent('研究待补充');
    expect(row).toHaveTextContent('价格、研究状态暂缺，按下一步补充。');
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
    expect(row).toHaveTextContent('研究待复核');
    expect(row).toHaveTextContent('价格暂缺，按下一步补充。');
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
    expect(within(row).getByTestId('watchlist-row-note-SHOP')).toHaveTextContent('价格、研究状态暂缺，按下一步补充。');
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
    expect(page).toHaveTextContent(/历史观察|不代表实时信号/);
    expect(page).toHaveTextContent('置信度较低');
    expect(page).not.toHaveTextContent(/reasonFamilies|reasonCode|sourceAuthorityAllowed|scoreContributionAllowed|observationOnly|source_confidence|score_blocked|raw diagnostics|JSON|provider_down|provider_error|proxy_fallback|fallback|proxy|备用\/代理|刷新或重新扫描后再使用|来源未知 \/ 需要刷新/i);
  });

  it('sorts by backtest return and historical hit rate', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.change(screen.getByLabelText('排序'), { target: { value: 'backtestReturn' } });
    let rows = Array.from(screen.getByTestId('watchlist-candidate-list').querySelectorAll('[role="row"][data-testid^="watchlist-row-"]'));
    expect(within(rows[0] as HTMLElement).getByText('NVDA')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('排序'), { target: { value: 'historicalHitRate' } });
    rows = Array.from(screen.getByTestId('watchlist-candidate-list').querySelectorAll('[role="row"][data-testid^="watchlist-row-"]'));
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
    await waitFor(() => expect(screen.getByTestId('watchlist-detail-rail')).toHaveTextContent('NVDA'));
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
    await waitFor(() => expect(screen.getByTestId('watchlist-batch-progress')).toHaveTextContent('1 / 1'));
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
    fireEvent.click(within(row).getByRole('button', { name: '更多操作 NVDA' }));
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
    expect(screen.getByTestId('watchlist-filter-grid')).toHaveClass('grid-cols-1', 'sm:grid-cols-2');
  });

  it('announces a background research refresh without replacing usable watchlist rows', async () => {
    let resolveRefresh: (response: { items: WatchlistItem[] }) => void = () => undefined;
    listWatchlistItems
      .mockResolvedValueOnce({ items: watchlistItems })
      .mockImplementationOnce(() => new Promise<{ items: WatchlistItem[] }>((resolve) => {
        resolveRefresh = resolve;
      }));

    renderWatchlist();
    expect(await screen.findByTestId('watchlist-row-NVDA')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '刷新观察依据' }));

    expect(await screen.findByTestId('watchlist-ledger-refresh-status')).toHaveTextContent('正在刷新已保存的研究上下文…');
    expect(screen.getByRole('button', { name: '正在刷新已保存的研究上下文…' })).toBeDisabled();
    expect(screen.getByTestId('watchlist-ledger-scroll-region')).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByTestId('watchlist-row-NVDA')).toBeInTheDocument();

    await act(async () => {
      resolveRefresh({ items: watchlistItems });
    });

    await waitFor(() => expect(screen.queryByTestId('watchlist-ledger-refresh-status')).not.toBeInTheDocument());
    expect(screen.getByTestId('watchlist-ledger-scroll-region')).toHaveAttribute('aria-busy', 'false');
    expect(screen.getByTestId('watchlist-row-NVDA')).toBeInTheDocument();
  });

  it('keeps watchlist mobile rows wrap-safe instead of truncating stale research context at 390px', async () => {
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 390 });
    window.dispatchEvent(new Event('resize'));

    renderWatchlist();

    const row = await screen.findByTestId('watchlist-row-NVDA');
    expect(screen.getByTestId('watchlist-board-shell')).toHaveClass('grid', 'min-w-0');
    expect(screen.getByTestId('watchlist-candidate-list')).toHaveClass('min-w-0', 'lg:min-w-[860px]');
    expect(screen.getByTestId('watchlist-ledger-scroll-region')).toHaveClass('overflow-x-hidden', 'lg:overflow-x-auto');
    expect(screen.getByTestId('watchlist-selected-context-bar')).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-identity-NVDA')).toHaveClass('break-words', 'whitespace-normal');
    expect(screen.getByTestId('watchlist-row-origin-NVDA')).toHaveClass('break-words', 'whitespace-normal');
    expect(screen.getByTestId('watchlist-row-state-NVDA')).toHaveClass('break-words', 'whitespace-normal');
    expect(within(row).getByTestId('watchlist-row-actions-NVDA').querySelectorAll('[data-terminal-primitive="button"]')).toHaveLength(2);
    if (within(row).queryByTestId('watchlist-row-note-NVDA')) {
      expect(within(row).getByTestId('watchlist-row-note-NVDA')).toHaveClass('break-words');
    }
  });

  it('keeps inspector selection stable when secondary row actions are opened', async () => {
    renderWatchlist();
    const tsmRow = await screen.findByTestId('watchlist-row-TSM');
    fireEvent.click(within(tsmRow).getByRole('button', { name: '查看详情 TSM' }));
    await waitFor(() => expect(screen.getByTestId('watchlist-detail-rail')).toHaveTextContent('TSM'));

    const nvdaRow = screen.getByTestId('watchlist-row-NVDA');
    fireEvent.click(within(nvdaRow).getByRole('button', { name: '更多操作 NVDA' }));
    expect(within(nvdaRow).getByRole('button', { name: '更多操作 NVDA' })).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByTestId('watchlist-detail-rail')).toHaveTextContent('TSM');
    expect(within(nvdaRow).queryByRole('button', { name: '分析' })).toBeInTheDocument();
  });

  it('starts analysis for a candidate and navigates to the workspace', async () => {
    renderWatchlist();
    const row = await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.click(within(row).getByRole('button', { name: '更多操作 NVDA' }));
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

  it('navigates to backtest with consumer-safe scanner context only', async () => {
    renderWatchlist();
    const row = await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.click(within(row).getByRole('button', { name: '更多操作 NVDA' }));
    fireEvent.click(within(row).getByRole('button', { name: /回测/ }));

    expect(screen.getByText('backtest')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/zh/backtest?');
    expect(screen.getByTestId('location')).toHaveTextContent('symbol=NVDA');
    expect(screen.getByTestId('location')).toHaveTextContent('source=scanner');
    expect(screen.getByTestId('location')).toHaveTextContent('market=US');
    expect(screen.getByTestId('location')).not.toHaveTextContent(/origin|watchlistItemId|scannerRunId|scannerRank|themeId|universeType|provider|cache|runtime|debug/i);
  });

  it('keeps page load read-only and shows unknown freshness honestly with canonical handoff context', async () => {
    listWatchlistItems.mockResolvedValue({
      items: [
        makeItem({
          id: 51,
          symbol: 'AAPL',
          market: 'us',
          name: 'Apple Inc.',
          source: 'manual',
          scannerRunId: null,
          scannerRank: null,
          scannerScore: null,
          lastScoredAt: null,
          scoreSource: null,
          scoreStatus: null,
          intelligence: undefined,
          rowResearchPacket: {
            symbol: 'AAPL',
            market: 'us',
            identity: {
              name: 'Apple Inc.',
              exchange: 'NASDAQ',
              sector: 'Technology',
              industry: 'Consumer Electronics',
              canonicalSymbol: 'AAPL',
              displaySymbol: 'AAPL',
              displayName: 'Apple Inc.',
              identityState: 'resolved',
            },
            savedItemSource: 'manual',
            quote: {
              state: 'unknown',
              price: null,
              changePercent: null,
              asOf: null,
            },
            scannerLineage: {
              runId: null,
              rank: null,
              score: null,
              status: null,
              lastScoredAt: null,
            },
            researchStatus: 'unknown',
            researchReadiness: {
              state: 'unknown',
              freshnessState: 'unknown',
              identityState: 'resolved',
            },
            missingData: ['quote', 'price_history', 'scanner_score_evidence'],
            nextDataAction: 'Review stock research context before relying on this saved row.',
            observationOnly: true,
            noAdviceDisclosure: 'Observation-only research packet; no personalized action instruction.',
          } as WatchlistItem['rowResearchPacket'] & {
            researchReadiness: { state: string; freshnessState: string; identityState: string };
          },
          createdAt: '2026-05-01T08:00:00Z',
          updatedAt: '2026-05-01T08:00:00Z',
        }),
      ],
    });
    getResearchOverlay.mockResolvedValue({
      schemaVersion: 'watchlist_research_overlay_v1',
      overlayState: 'degraded',
      researchSummary: 'Watchlist entries need evidence review.',
      researchPriorityQueue: [
        {
          symbol: 'AAPL',
          priorityTier: 'attention',
          priorityReasonSafeLabel: 'Research context needs attention.',
          evidenceAge: { state: 'unknown', lastReviewedAt: null },
          missingEvidence: ['Research context', 'Price-history evidence'],
          suggestedResearchPath: [
            {
              label: 'Stock Structure',
              route: '/stocks/AAPL/structure-decision?symbol=AAPL&market=US&source=watchlist',
              section: 'watchlistResearchOverlay',
              reason: 'Open saved symbol research context.',
            },
          ],
          observationOnly: true,
        },
      ],
      observationOnly: true,
      decisionGrade: false,
    });

    renderWatchlist('/watchlist?symbol=aapl&market=us&source=watchlist');

    const row = await screen.findByTestId('watchlist-row-AAPL');
    expect(row).toHaveTextContent('AAPL');
    expect(row).toHaveTextContent('Apple Inc.');
    expect(row).toHaveTextContent('身份已确认');
    expect(row).toHaveTextContent('时效未知');
    expect(row).toHaveTextContent('研究状态未知');
    expect(row).toHaveTextContent('查看个股结构');
    expect(row).not.toHaveTextContent(/数据更新中|稍后将自动刷新|评分已刷新|已更新|当前焦点|最新1|fake|placeholder/i);

    const detailRail = screen.getByTestId('watchlist-detail-rail');
    expect(detailRail).toHaveTextContent('研究状态待确认');
    expect(detailRail).toHaveTextContent('时效未知');
    expect(detailRail).toHaveTextContent('研究状态待确认，未推断刷新进度。');
    expect(detailRail).not.toHaveTextContent(/数据更新中|稍后将自动刷新|自动刷新|刷新中/i);

    const panel = await screen.findByTestId('watchlist-research-workspace-flow');
    expect(screen.getByTestId('watchlist-secondary-deck')).toContainElement(panel);
    expect(within(panel).getByTestId('research-workspace-link-stock-structure')).toHaveAttribute(
      'href',
      expect.stringContaining('/stocks/AAPL/structure-decision?'),
    );
    expect(within(panel).getByTestId('research-workspace-link-stock-structure')).toHaveAttribute(
      'href',
      expect.stringContaining('symbol=AAPL'),
    );
    expect(within(panel).getByTestId('research-workspace-link-stock-structure')).toHaveAttribute(
      'href',
      expect.stringContaining('market=US'),
    );
    expect(within(panel).getByTestId('research-workspace-link-backtest')).toHaveAttribute(
      'href',
      expect.stringContaining('/backtest?'),
    );

    fireEvent.click(within(row).getByRole('button', { name: '查看个股结构 AAPL' }));
    expect(screen.getByText('stock structure')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/zh/stocks/AAPL/structure-decision?symbol=AAPL&market=US&source=watchlist');

    expect(listWatchlistItems).toHaveBeenCalledTimes(1);
    expect(getResearchOverlay).toHaveBeenCalledTimes(1);
    expect(addWatchlistItem).not.toHaveBeenCalled();
    expect(refreshScores).not.toHaveBeenCalled();
    expect(removeWatchlistItem).not.toHaveBeenCalled();
    expect(runRuleBacktest).not.toHaveBeenCalled();
    expect(analyzeAsync).not.toHaveBeenCalled();
  });

  it('removes a candidate through the delete API and drops the row', async () => {
    renderWatchlist();
    const row = await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.click(within(row).getByRole('button', { name: '更多操作 NVDA' }));
    fireEvent.click(within(row).getByRole('button', { name: '移除 NVDA' }));

    await waitFor(() => expect(removeWatchlistItem).toHaveBeenCalledWith(1));
    await waitFor(() => expect(screen.queryByTestId('watchlist-row-NVDA')).not.toBeInTheDocument());
  });

  it('copies the symbol to the clipboard', async () => {
    renderWatchlist();
    const row = await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.click(within(row).getByRole('button', { name: '更多操作 NVDA' }));
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
    expect(emptyState).toHaveTextContent('这里优先保留单标的研究与明确保存观察的路径。');
    expect(within(emptyState).queryByTestId('watchlist-empty-preview')).not.toBeInTheDocument();
    expect(emptyState).not.toHaveTextContent(/功能预览|示例预览|Demo sample|sample only/i);
    const researchPath = within(emptyState).getByTestId('watchlist-empty-manual-research');
    expect(researchPath).toHaveTextContent('首选研究路径');
    expect(researchPath).toHaveTextContent('手动研究代码');
    expect(researchPath).toHaveTextContent('首选路径：先启动一个个股研究任务，不会把代码加入观察名单。');
    const onboardingPanel = within(emptyState).getByTestId('watchlist-empty-onboarding-cta');
    expect(onboardingPanel).toHaveTextContent('先看市场概览');
    expect(onboardingPanel).toHaveTextContent('运行 Scanner');
    expect(onboardingPanel).toHaveTextContent('选择观察标的');
    expect(onboardingPanel).toHaveTextContent('查看研究雷达');
    expect(within(onboardingPanel).getByRole('button', { name: '先看市场概览' })).toHaveAttribute('href', '/zh/market-overview');
    expect(within(onboardingPanel).getByRole('button', { name: '打开扫描器' })).toHaveAttribute('href', '/zh/scanner');
    expect(within(onboardingPanel).getByRole('button', { name: '选择观察标的' })).toHaveAttribute('href', '/zh/watchlist');
    expect(within(onboardingPanel).getByRole('button', { name: '查看研究雷达' })).toHaveAttribute('href', '/zh/research/radar');
    expect(onboardingPanel).toHaveTextContent('不会自动保存代码。');
    expect(within(emptyState).getByLabelText('手动研究代码')).toBeInTheDocument();
    expect(emptyState).not.toHaveTextContent(/数据不足，禁止判断|买入|卖出|下单|交易|券商|broker/i);
    expect(within(headerStrip).queryByRole('button', { name: /打开扫描器|Open Scanner/i })).not.toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-compact-filter-bar')).not.toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-advanced-filters')).not.toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-list-header')).not.toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-secondary-deck')).not.toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-command-bar')).not.toBeInTheDocument();
    expect(within(emptyState).queryByRole('button', { name: /稍后打开扫描器|Open Scanner later/i })).not.toBeInTheDocument();
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
    expect(addWatchlistItem).not.toHaveBeenCalled();
    expect(refreshScores).not.toHaveBeenCalled();
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

  it('renders authenticated empty state for a logged-in admin without admin-only controls', async () => {
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: true,
      isAdminAccount: true,
      isAdminMode: true,
      currentUser: {
        isAdmin: true,
        isAuthenticated: true,
        adminCapabilities: ['ops:providers:read', 'users:read'],
        sessionId: 'raw-session-canary',
        debugToken: 'bearer-canary',
      },
    });
    listWatchlistItems.mockResolvedValue({ items: [] });

    renderWatchlist();

    const emptyState = await screen.findByTestId('watchlist-compact-empty-state');
    expect(emptyState).toHaveTextContent('还没有观察标的');
    expect(screen.queryByText('auth-guard:观察列表')).not.toBeInTheDocument();
    expect(listWatchlistItems).toHaveBeenCalledTimes(1);
    expect(document.body.textContent || '').not.toMatch(/adminCapabilities|sessionId|debugToken|raw-session-canary|bearer-canary|Provider Ops|admin|debug|requestId|traceId|token|cookie|bearer/i);
    expect(document.body.textContent || '').not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy now|sell now|hold this|recommended pick|target price|stop loss|position sizing/i);
  });

  it('renders authenticated empty state for a signed-in user without showing the login prompt', async () => {
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: false,
      isAdminAccount: false,
      currentUser: {
        isAdmin: false,
        isAuthenticated: true,
      },
    });
    listWatchlistItems.mockResolvedValue({ items: [] });

    renderWatchlist();

    const emptyState = await screen.findByTestId('watchlist-compact-empty-state');
    expect(emptyState).toHaveTextContent('还没有观察标的');
    expect(emptyState).toHaveTextContent('手动研究代码');
    expect(screen.queryByText('auth-guard:观察列表')).not.toBeInTheDocument();
    expect(listWatchlistItems).toHaveBeenCalledTimes(1);
  });

  it('fail-closes to the login-required state when the watchlist API returns 401', async () => {
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: true,
      currentUser: {
        isAdmin: true,
        isAuthenticated: true,
      },
    });
    const unauthorized = Object.assign(new Error('provider runtime requestId=req-1 token=bearer-secret unauthorized'), {
      status: 401,
      parsedError: {
        title: '登录已失效，请重新登录。',
        message: '登录已失效，请重新登录。',
        rawMessage: 'provider runtime requestId=req-1 token=bearer-secret unauthorized',
        status: 401,
        category: 'auth_required',
        isAuthError: true,
      },
    });
    listWatchlistItems.mockRejectedValue(unauthorized);

    renderWatchlist();

    expect(await screen.findByText('auth-guard:观察列表')).toBeInTheDocument();
    expect(screen.queryByTestId('watchlist-compact-empty-state')).not.toBeInTheDocument();
    expect(document.body.textContent || '').not.toMatch(/provider runtime|requestId|bearer-secret|rawMessage|traceId|debug|stack/i);
  });
});
