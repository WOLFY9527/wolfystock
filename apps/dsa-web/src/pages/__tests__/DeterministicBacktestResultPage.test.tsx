import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { translate } from '../../i18n/core';
import type { RuleBacktestRunResponse } from '../../types/backtest';
import DeterministicBacktestResultPage from '../DeterministicBacktestResultPage';
import RuleBacktestComparePage from '../RuleBacktestComparePage';

const {
  getRuleBacktestRun,
  getRuleBacktestRuns,
  getRuleBacktestRunStatus,
  cancelRuleBacktestRun,
  runRuleBacktest,
  compareRuleBacktestRuns,
} = vi.hoisted(() => ({
  getRuleBacktestRun: vi.fn(),
  getRuleBacktestRuns: vi.fn(),
  getRuleBacktestRunStatus: vi.fn(),
  cancelRuleBacktestRun: vi.fn(),
  runRuleBacktest: vi.fn(),
  compareRuleBacktestRuns: vi.fn(),
}));

const CHART_IMPORT_TIMEOUT = 5000;

const { writeTextMock } = vi.hoisted(() => ({
  writeTextMock: vi.fn(),
}));

const { auditTablesImportGate } = vi.hoisted(() => {
  let delayEnabled = false;
  let releaseResolver: (() => void) | null = null;
  let pendingPromise: Promise<void> | null = null;

  return {
    auditTablesImportGate: {
      enable() {
        delayEnabled = true;
      },
      reset() {
        delayEnabled = false;
        pendingPromise = null;
        const resolve = releaseResolver;
        releaseResolver = null;
        resolve?.();
      },
      release() {
        delayEnabled = false;
        pendingPromise = null;
        const resolve = releaseResolver;
        releaseResolver = null;
        resolve?.();
      },
      wait() {
        if (!delayEnabled) return Promise.resolve();
        if (!pendingPromise) {
          pendingPromise = new Promise<void>((resolve) => {
            releaseResolver = resolve;
          });
        }
        return pendingPromise;
      },
    },
  };
});

const { reportImportGate } = vi.hoisted(() => {
  let delayEnabled = false;
  let releaseResolver: (() => void) | null = null;
  let pendingPromise: Promise<void> | null = null;

  return {
    reportImportGate: {
      enable() {
        delayEnabled = true;
      },
      reset() {
        delayEnabled = false;
        pendingPromise = null;
        const resolve = releaseResolver;
        releaseResolver = null;
        resolve?.();
      },
      release() {
        delayEnabled = false;
        pendingPromise = null;
        const resolve = releaseResolver;
        releaseResolver = null;
        resolve?.();
      },
      wait() {
        if (!delayEnabled) return Promise.resolve();
        if (!pendingPromise) {
          pendingPromise = new Promise<void>((resolve) => {
            releaseResolver = resolve;
          });
        }
        return pendingPromise;
      },
    },
  };
});

vi.mock('../../api/backtest', () => ({
  backtestApi: {
    getRuleBacktestRun,
    getRuleBacktestRuns,
    getRuleBacktestRunStatus,
    cancelRuleBacktestRun,
    runRuleBacktest,
    compareRuleBacktestRuns,
  },
}));

vi.mock('../../components/backtest/BacktestAuditTables', async (importOriginal) => {
  await auditTablesImportGate.wait();
  return importOriginal<typeof import('../../components/backtest/BacktestAuditTables')>();
});

vi.mock('../../components/backtest/BacktestResultReport', async (importOriginal) => {
  await reportImportGate.wait();
  return importOriginal<typeof import('../../components/backtest/BacktestResultReport')>();
});

function renderResultPage(initialEntries: string[] = ['/backtest/results/99']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <UiLanguageProvider>
        <Routes>
          <Route path="/backtest/results/:runId" element={<DeterministicBacktestResultPage />} />
          <Route path="/:locale/backtest/results/:runId" element={<DeterministicBacktestResultPage />} />
          <Route path="/backtest/compare" element={<div data-testid="rule-backtest-compare-route">compare route</div>} />
          <Route path="/:locale/backtest/compare" element={<div data-testid="rule-backtest-compare-route">compare route</div>} />
        </Routes>
      </UiLanguageProvider>
    </MemoryRouter>,
  );
}

function renderResultPageWithCompareWorkbench(initialEntries: string[] = ['/backtest/results/99']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <UiLanguageProvider>
        <Routes>
          <Route path="/backtest/results/:runId" element={<DeterministicBacktestResultPage />} />
          <Route path="/:locale/backtest/results/:runId" element={<DeterministicBacktestResultPage />} />
          <Route path="/backtest/compare" element={<RuleBacktestComparePage />} />
          <Route path="/:locale/backtest/compare" element={<RuleBacktestComparePage />} />
        </Routes>
      </UiLanguageProvider>
    </MemoryRouter>
  );
}

function makeResultRun(overrides: Partial<RuleBacktestRunResponse> = {}): RuleBacktestRunResponse {
  const auditRows = Array.from({ length: 3 }, (_, index) => ({
    date: `2026-03-0${index + 1}`,
    symbolClose: 100 + index,
    benchmarkClose: 98 + index,
    signalSummary: index === 1 ? 'MA5 > MA20' : null,
    targetPosition: index === 1 ? 1 : 0,
    executedAction: index === 1 ? 'buy' : index === 2 ? 'sell' : null,
    fillPrice: index === 1 ? 101 : index === 2 ? 104 : null,
    sharesHeld: index === 1 ? 1000 : 0,
    cash: index === 1 ? 5000 : 100000,
    holdingsValue: index === 1 ? 101000 : 0,
    totalPortfolioValue: index === 0 ? 100000 : index === 1 ? 101500 : 104000,
    dailyPnl: index === 0 ? 0 : index === 1 ? 1500 : 2500,
    dailyReturnPct: index === 0 ? 0 : index === 1 ? 1.5 : 2.46,
    cumulativeStrategyReturnPct: index === 0 ? 0 : index === 1 ? 1.5 : 4,
    cumulativeBenchmarkReturnPct: index === 0 ? 0 : index === 1 ? 1.2 : 2.8,
    cumulativeBuyAndHoldReturnPct: index === 0 ? 0 : index === 1 ? 1 : 2.6,
    fees: 0,
    slippage: 0,
    notes: null,
    unavailableReason: null,
  }));

  return {
    id: 99,
    code: 'ORCL',
    strategyText: 'MA cross',
    parsedStrategy: {
      version: 'v1',
      timeframe: 'daily',
      sourceText: 'MA cross',
      normalizedText: 'SMA5 上穿 SMA20 买入，下穿卖出。',
      entry: { type: 'group', op: 'and', rules: [] },
      exit: { type: 'group', op: 'or', rules: [] },
      confidence: 0.97,
      needsConfirmation: false,
      ambiguities: [],
      summary: {
        entry: 'SMA5 上穿 SMA20',
        exit: 'SMA5 下穿 SMA20',
        strategy: '均线交叉策略',
      },
      maxLookback: 20,
      strategyKind: 'moving_average_crossover',
      executable: true,
      normalizationState: 'ready',
      assumptions: [],
      assumptionGroups: [],
      detectedStrategyFamily: 'moving_average_crossover',
      unsupportedReason: null,
      unsupportedDetails: [],
      unsupportedExtensions: [],
      coreIntentSummary: '已识别为均线交叉主规则。',
      interpretationConfidence: 0.97,
      supportedPortionSummary: '已识别为均线交叉主规则。',
      rewriteSuggestions: [],
      parseWarnings: [],
      setup: {
        symbol: 'ORCL',
        startDate: '2026-03-01',
        endDate: '2026-03-31',
        initialCapital: 100000,
      },
      strategySpec: {
        strategyType: 'moving_average_crossover',
        strategyFamily: 'moving_average_crossover',
        symbol: 'ORCL',
        timeframe: 'daily',
        dateRange: {
          startDate: '2026-03-01',
          endDate: '2026-03-31',
        },
        capital: {
          initialCapital: 100000,
          currency: 'USD',
        },
        signal: {
          indicatorFamily: 'moving_average',
          fastPeriod: 5,
          slowPeriod: 20,
          fastType: 'simple',
          slowType: 'simple',
          entryCondition: 'cross_above',
          exitCondition: 'cross_below',
        },
        execution: {
          frequency: 'daily',
          signalTiming: 'bar_close',
          fillTiming: 'next_bar_open',
        },
        positionBehavior: {
          direction: 'long_only',
          entrySizing: 'all_available_capital',
          maxPositions: 1,
          pyramiding: false,
        },
        endBehavior: {
          policy: 'liquidate_at_end',
          priceBasis: 'close',
        },
        costs: {
          feeBps: 0,
          slippageBps: 0,
        },
      },
    } as RuleBacktestRunResponse['parsedStrategy'],
    strategyHash: 'hash',
    timeframe: 'daily',
    startDate: '2026-03-01',
    endDate: '2026-03-31',
    periodStart: '2026-03-01',
    periodEnd: '2026-03-31',
    lookbackBars: 252,
    initialCapital: 100000,
    feeBps: 0,
    slippageBps: 0,
    parsedConfidence: 0.97,
    needsConfirmation: false,
    warnings: [],
    runAt: '2026-04-07T08:00:00Z',
    completedAt: '2026-04-07T08:02:00Z',
    status: 'completed',
    statusMessage: '规则回测已完成。',
    statusHistory: [
      { status: 'queued', at: '2026-04-07T08:00:00Z' },
      { status: 'completed', at: '2026-04-07T08:02:00Z' },
    ],
    noResultReason: null,
    noResultMessage: null,
    tradeCount: 1,
    winCount: 1,
    lossCount: 0,
    totalReturnPct: 4,
    annualizedReturnPct: 6.1,
    benchmarkMode: 'auto',
    benchmarkCode: null,
    benchmarkReturnPct: 2.8,
    excessReturnVsBenchmarkPct: 1.2,
    buyAndHoldReturnPct: 2.6,
    excessReturnVsBuyAndHoldPct: 1.4,
    winRatePct: 100,
    avgTradeReturnPct: 4,
    maxDrawdownPct: 1.3,
    avgHoldingDays: 3,
    avgHoldingBars: 3,
    avgHoldingCalendarDays: 4,
    finalEquity: 104000,
    summary: {},
    executionAssumptions: {
      signalEvaluationTiming: 'bar close',
      entryFillTiming: 'next bar open',
      positionSizing: 'all_available_capital',
    },
    benchmarkCurve: [],
    benchmarkSummary: {
      label: 'QQQ',
      requestedMode: 'auto',
      resolvedMode: 'etf_qqq',
      method: 'benchmark_security',
      priceBasis: 'close',
      returnPct: 2.8,
    },
    buyAndHoldCurve: [],
    buyAndHoldSummary: {
      label: '当前标的买入并持有',
      requestedMode: 'same_symbol_buy_and_hold',
      resolvedMode: 'same_symbol_buy_and_hold',
      method: 'same_symbol_buy_and_hold',
      priceBasis: 'close',
      returnPct: 2.6,
    },
    auditRows,
    executionTrace: {
      source: 'storedExecutionTrace',
      rows: auditRows.map((row) => ({
        date: row.date,
        symbolClose: row.symbolClose,
        benchmarkClose: row.benchmarkClose,
        signalSummary: row.signalSummary,
        action: row.executedAction,
        actionDisplay: row.executedAction === 'buy' ? '买入' : row.executedAction === 'sell' ? '卖出' : '持有',
        fillPrice: row.fillPrice,
        shares: row.sharesHeld,
        cash: row.cash,
        holdingsValue: row.holdingsValue,
        totalPortfolioValue: row.totalPortfolioValue,
        dailyPnl: row.dailyPnl,
        dailyReturn: row.dailyReturnPct,
        cumulativeReturn: row.cumulativeStrategyReturnPct,
        benchmarkCumulativeReturn: row.cumulativeBenchmarkReturnPct,
        buyHoldCumulativeReturn: row.cumulativeBuyAndHoldReturnPct,
        position: row.targetPosition,
        fees: row.fees,
        slippage: row.slippage,
        notes: row.notes,
        unavailableReason: row.unavailableReason,
        assumptionsDefaults: 'next bar open / long only',
        fallback: '',
      })),
      assumptionsDefaults: {
        summaryText: 'next bar open / long only',
      },
      fallback: {
        runFallback: false,
        traceRebuilt: false,
        note: '标准执行路径',
      },
    },
    dailyReturnSeries: [],
    exposureCurve: [],
    aiSummary: null,
    equityCurve: [],
    trades: [],
    ...overrides,
  };
}

describe('DeterministicBacktestResultPage', () => {
  let originalClipboard: Navigator['clipboard'] | undefined;

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.resetAllMocks();
    vi.useRealTimers();
    vi.stubGlobal('confirm', vi.fn(() => true));
    auditTablesImportGate.reset();
    reportImportGate.reset();
    writeTextMock.mockReset();
    writeTextMock.mockResolvedValue(undefined);
    originalClipboard = navigator.clipboard;
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: writeTextMock,
      },
    });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: originalClipboard,
    });
  });

  it('lazy-loads the completed report surface with a compact fallback', async () => {
    const currentRun = makeResultRun({ id: 99, runAt: '2026-04-07T08:00:00Z' });

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    reportImportGate.enable();
    renderResultPage();

    expect(await screen.findByTestId('deterministic-result-report-lazy-fallback')).toBeInTheDocument();
    expect(screen.getByTestId('deterministic-result-page-console-hero')).toBeInTheDocument();
    expect(screen.getByTestId('deterministic-result-page-tabs')).toBeInTheDocument();

    reportImportGate.release();

    await act(async () => {
      await vi.dynamicImportSettled();
    });

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toHaveAttribute('data-run-id', '99');
    await waitFor(() => {
      expect(screen.queryByTestId('deterministic-result-report-lazy-fallback')).not.toBeInTheDocument();
    });
  }, 10000);

  it('labels backtest timeline entries as simulated trade events', async () => {
    const currentRun = makeResultRun({
      id: 99,
      runAt: '2026-04-07T08:00:00Z',
      trades: [
        {
          code: 'ORCL',
          tradeIndex: 1,
          entryDate: '2026-03-04',
          exitDate: '2026-03-24',
          entryPrice: 103,
          exitPrice: 115,
          quantity: 900,
          returnPct: 11.5,
          entryReason: 'signal_entry',
          exitReason: 'signal_exit',
        },
      ],
    });

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    renderResultPage();

    const timeline = await screen.findByTestId('backtest-report-event-timeline');
    expect(timeline).toHaveTextContent('模拟正向信号事件 / 模拟反向信号事件');
    expect(timeline).toHaveTextContent('模拟事件仅用于回测复盘，不构成交易指令。');
    expect(within(timeline).getByText('模拟正向信号事件')).toBeInTheDocument();
    expect(within(timeline).getByText('模拟反向信号事件')).toBeInTheDocument();
    expect(within(timeline).queryByText('买入')).not.toBeInTheDocument();
    expect(within(timeline).queryByText('卖出')).not.toBeInTheDocument();
  }, 10000);

  it('polls processing runs on the result page and then renders the completed analysis workspace', async () => {
    const queuedRun = makeResultRun({
      status: 'queued',
      completedAt: null,
      statusMessage: '策略已提交，等待开始执行。',
      statusHistory: [{ status: 'queued', at: '2026-04-07T08:00:00Z' }],
      auditRows: [],
    });
    const completedRun = makeResultRun();

    getRuleBacktestRun
      .mockResolvedValueOnce(queuedRun)
      .mockResolvedValueOnce(completedRun);
    getRuleBacktestRunStatus.mockResolvedValueOnce({
      id: 99,
      code: 'ORCL',
      status: 'completed',
      statusMessage: '规则回测已完成。',
      statusHistory: [
        { status: 'queued', at: '2026-04-07T08:00:00Z' },
        { status: 'completed', at: '2026-04-07T08:02:00Z' },
      ],
      runAt: '2026-04-07T08:00:00Z',
      completedAt: '2026-04-07T08:02:00Z',
      noResultReason: null,
      noResultMessage: null,
      tradeCount: 1,
      parsedConfidence: 0.97,
      needsConfirmation: false,
    });
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [completedRun],
    });

    vi.useFakeTimers();
    renderResultPage();

    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByText('页面正在自动跟踪状态')).toBeInTheDocument();
    expect(screen.getByTestId('deterministic-backtest-result-view')).toBeInTheDocument();
    expect(screen.getByTestId('deterministic-result-page-pending-visualization')).toBeInTheDocument();
    expect(screen.getByTestId('deterministic-result-pending-state')).toBeInTheDocument();
    expect(screen.queryByTestId('deterministic-backtest-chart-workspace')).not.toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1800);
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      await vi.dynamicImportSettled();
    });

    expect(screen.getByTestId('deterministic-backtest-result-view')).toHaveAttribute('data-run-id', '99');
    expect(screen.getByTestId('deterministic-backtest-chart-workspace')).toHaveAttribute('data-row-count', '3');
    expect(screen.getByRole('tab', { name: '概览' })).toHaveAttribute('aria-selected', 'true');
    expect(getRuleBacktestRunStatus).toHaveBeenCalledTimes(1);
    expect(getRuleBacktestRun).toHaveBeenCalledTimes(2);
  }, 10000);

  it('lazy-loads inactive audit tabs without delaying the initial overview path', async () => {
    const currentRun = makeResultRun({ id: 99, runAt: '2026-04-07T08:00:00Z' });

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    auditTablesImportGate.enable();
    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toHaveAttribute('data-run-id', '99');
    expect(screen.getByRole('tab', { name: '概览' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.queryByTestId('deterministic-result-tab-lazy-fallback')).not.toBeInTheDocument();
    expect(screen.queryByTestId('deterministic-result-tab-panel-audit')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: '审计明细' }));

    expect(screen.getByRole('tab', { name: '审计明细' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByTestId('deterministic-result-tab-lazy-fallback')).toBeInTheDocument();
    expect(screen.queryByTestId('deterministic-result-tab-panel-audit')).not.toBeInTheDocument();

    auditTablesImportGate.release();

    await act(async () => {
      await vi.dynamicImportSettled();
    });

    expect(await screen.findByTestId('deterministic-result-tab-panel-audit')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByTestId('deterministic-result-tab-lazy-fallback')).not.toBeInTheDocument();
    });
  }, 10000);

  it('keeps the first screen compact and moves deep data into dedicated tabs', async () => {
    const currentRun = makeResultRun({ id: 99, runAt: '2026-04-07T08:00:00Z' });

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toHaveAttribute('data-run-id', '99');
    const pageShell = screen.getByTestId('deterministic-backtest-result-page');
    expect(pageShell).toHaveAttribute('data-density', 'dense');
    expect(pageShell).toHaveClass('w-full', 'max-w-[1600px]', 'mx-auto', 'px-4', 'xl:px-8', 'flex', 'flex-col', 'gap-5');
    expect(pageShell).not.toHaveClass('theme-page-transition', 'backtest-v1-page', 'workspace-page--backtest');
    expect(pageShell.querySelector('.workspace-page--backtest')).toBeNull();
    expect(pageShell.closest('main')).not.toHaveClass('py-4');
    expect(screen.getByTestId('deterministic-result-page-hero')).toBeInTheDocument();
    expect(screen.getByTestId('deterministic-result-dashboard')).toBeInTheDocument();
    expect(screen.queryByText('结果指标')).not.toBeInTheDocument();
    expect(screen.queryByText('联动结果图表')).not.toBeInTheDocument();
    expect(await screen.findByTestId('deterministic-backtest-chart-workspace', undefined, { timeout: CHART_IMPORT_TIMEOUT })).toHaveAttribute('data-row-count', '3');
    expect(screen.getByRole('tab', { name: '概览' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.queryByText('日级审计 / 对账')).not.toBeInTheDocument();
    expect(screen.queryByText('交易 / 事件日志')).not.toBeInTheDocument();
    expect(screen.queryByText('同标的历史回测')).not.toBeInTheDocument();
    expect(screen.queryByText('参数快照')).not.toBeInTheDocument();
    expect(screen.getAllByText('已完成').length).toBeGreaterThan(0);
    expect(screen.getByTestId('deterministic-result-kpi-strip')).toBeInTheDocument();
    expect(screen.getByTestId('deterministic-result-kpi-strip')).toHaveTextContent('年化收益');
    expect(screen.getByTestId('deterministic-result-kpi-strip')).not.toHaveTextContent('{value}');

    fireEvent.click(screen.getByRole('tab', { name: '审计明细' }));
    const auditPanel = await screen.findByTestId('deterministic-result-tab-panel-audit');
    expect(auditPanel).toBeInTheDocument();
    expect(screen.getByText('日级审计 / 对账')).toBeInTheDocument();
    expect(within(auditPanel).getByRole('heading', { name: '执行轨迹' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '关键节点' })).toHaveAttribute('aria-selected', 'true');

    fireEvent.click(screen.getByRole('tab', { name: '交易记录' }));
    expect(await screen.findByTestId('deterministic-result-tab-panel-trades')).toBeInTheDocument();
    expect(screen.getByText('交易 / 事件日志')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: '参数与假设' }));
    expect(await screen.findByTestId('deterministic-result-tab-panel-parameters')).toBeInTheDocument();
    expect(screen.getByText('参数快照')).toBeInTheDocument();
    expect(screen.getAllByText('实际执行内容').length).toBeGreaterThan(0);
    expect(screen.getByText('原始输入与解析')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: '历史结果' }));
    expect(await screen.findByTestId('deterministic-result-tab-panel-history')).toBeInTheDocument();
    expect(screen.getByText('同标的历史回测')).toBeInTheDocument();
  }, 10000);

  it('renders stored drawdown phase attribution in audit order without recomputing from audit rows', async () => {
    const currentRun = makeResultRun({
      summary: {
        drawdownRegimeAttribution: {
          version: 'v1',
          source: 'summary.drawdown_regime_attribution',
          state: 'available',
          bucketCounts: {
            peak: {
              count: 1,
              sharePct: 33.3333,
              avgDepthPct: null,
              worstDepthPct: null,
            },
            moderate: {
              count: 2,
              sharePct: 66.6667,
              avgDepthPct: 8.5,
              worstDepthPct: 9.2,
            },
          },
          contributionSummaries: {
            classifiedRows: {
              count: 3,
              sharePct: 100,
            },
            missingRows: {
              count: 0,
              sharePct: 0,
            },
          },
          unavailableReason: null,
        },
      },
    });

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: '审计明细' }));
    const auditPanel = await screen.findByTestId('deterministic-result-tab-panel-audit');
    const traceHeading = within(auditPanel).getByText('执行轨迹');
    const supportExportsHeading = within(auditPanel).getByText('技术支持导出');
    const attributionPanel = within(auditPanel).getByTestId('backtest-drawdown-attribution-panel');
    const attributionHeading = within(attributionPanel).getByText('回撤阶段归因');
    const auditTableHeading = within(auditPanel).getByText('日级审计 / 对账');

    expect(traceHeading.compareDocumentPosition(supportExportsHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(supportExportsHeading.compareDocumentPosition(attributionHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(attributionHeading.compareDocumentPosition(auditTableHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    expect(attributionPanel).toHaveTextContent('基于已存审计行的回撤区间汇总，用于解释回撤来源；不改变收益、回撤、交易或报告结论口径。');
    expect(attributionPanel).toHaveTextContent('可用');
    expect(attributionPanel).toHaveTextContent('已存审计行汇总');
    expect(attributionPanel).toHaveTextContent('2 / 3');
    expect(attributionPanel).toHaveTextContent('100.00%');
    expect(attributionPanel).toHaveTextContent('0.00%');
    expect(attributionPanel).toHaveTextContent('高点区间');
    expect(attributionPanel).toHaveTextContent('中度回撤');
    expect(attributionPanel).toHaveTextContent('8.50%');
    expect(attributionPanel).toHaveTextContent('9.20%');
    expect(attributionPanel).not.toHaveTextContent(/drawdown_regime_attribution|regimeAttribution|payload|schema|stored_audit_rows|market regime/i);
  });

  it('renders the partial drawdown phase attribution coverage copy from stored summary fields', async () => {
    const currentRun = makeResultRun({
      summary: {
        drawdownRegimeAttribution: {
          version: 'v1',
          source: 'summary.drawdown_regime_attribution',
          state: 'partial',
          bucketCounts: {
            peak: {
              count: 1,
              sharePct: 25,
              avgDepthPct: null,
              worstDepthPct: null,
            },
            moderate: {
              count: 1,
              sharePct: 25,
              avgDepthPct: 6.25,
              worstDepthPct: 6.25,
            },
            unknown: {
              count: 2,
              sharePct: 50,
              avgDepthPct: null,
              worstDepthPct: null,
            },
          },
          contributionSummaries: {
            classifiedRows: {
              count: 2,
              sharePct: 50,
            },
            missingRows: {
              count: 2,
              sharePct: 50,
            },
          },
          unavailableReason: null,
        },
      },
    });

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: '审计明细' }));
    const attributionPanel = within(await screen.findByTestId('deterministic-result-tab-panel-audit'))
      .getByTestId('backtest-drawdown-attribution-panel');

    expect(attributionPanel).toHaveTextContent('部分可用');
    expect(attributionPanel).toHaveTextContent('仅展示已存审计行覆盖到的区间；缺失区间不补算、不推断。');
    expect(attributionPanel).toHaveTextContent('3 / 2');
    expect(attributionPanel).toHaveTextContent('50.00%');
    expect(attributionPanel).toHaveTextContent('未归类');
  });

  it('renders a compact unavailable drawdown phase attribution state when no stored summary is provided', async () => {
    const currentRun = makeResultRun({
      summary: {},
    });

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: '审计明细' }));
    const attributionPanel = within(await screen.findByTestId('deterministic-result-tab-panel-audit'))
      .getByTestId('backtest-drawdown-attribution-panel');

    expect(attributionPanel).toHaveTextContent('未提供');
    expect(attributionPanel).toHaveTextContent('当前结果未提供回撤阶段归因。最大回撤、收益曲线与审计表仍是主要查看口径；前端不会重算归因。');
    expect(attributionPanel).toHaveTextContent('当前未提供');
  });

  it('aligns result-page strategy wording with the confirmation-page canonical spec language', async () => {
    const currentRun = makeResultRun();

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: '参数与假设' }));
    expect(await screen.findByTestId('deterministic-result-tab-panel-parameters')).toBeInTheDocument();

    expect(screen.getAllByText('策略族 · 均线交叉').length).toBeGreaterThan(0);
    expect(screen.getByText('规格来源 · 显式 strategy_spec')).toBeInTheDocument();
    expect(screen.getByText('归一化 · 已完成归一化')).toBeInTheDocument();
    expect(screen.getAllByText('SMA5 上穿 SMA20').length).toBeGreaterThan(0);
    expect(screen.getAllByText('收盘后判定').length).toBeGreaterThan(0);
    expect(screen.getAllByText('下一根开盘成交').length).toBeGreaterThan(0);

    expect(screen.getAllByText('策略族').length).toBeGreaterThan(0);
    expect(screen.getAllByText('均线交叉').length).toBeGreaterThan(0);
    expect(screen.getAllByText('已完成归一化').length).toBeGreaterThan(0);
  });

  it('renders robustness analysis from the real API shape in the parameters tab', async () => {
    const currentRun = makeResultRun({
      robustnessAnalysis: {
        state: 'available',
        configuration: {
          walkForward: {
            maxWindows: 6,
          },
          monteCarlo: {
            simulationCount: 250,
          },
          stressTests: {
            scenarioKeys: ['single_day_shock_down_15', 'volatility_whipsaw', 'gap_down_open'],
          },
        },
        walkForward: {
          windowCount: 4,
          aggregateMetrics: {
            meanTotalReturnPct: 6.2,
          },
        },
        monteCarlo: {
          state: 'available',
          simulationCount: 200,
          seed: 20260423,
          aggregateMetrics: {
            p05TotalReturnPct: -3.6,
            meanTotalReturnPct: 7.1,
            medianTotalReturnPct: 8.4,
            p95TotalReturnPct: 16.8,
            worstMaxDrawdownPct: 12.5,
          },
        },
        stressTests: {
          state: 'available',
          scenarioCount: 3,
          scenarios: [
            {
              scenarioKey: 'single_day_shock_down_15',
              label: 'Single-day shock down 15%',
              state: 'completed',
              metrics: {
                totalReturnPct: -18.4,
                sharpeRatio: -1.1,
                maxDrawdownPct: 21.3,
              },
            },
            {
              scenarioKey: 'volatility_whipsaw',
              label: 'Volatility whipsaw regime',
              state: 'completed',
              metrics: {
                totalReturnPct: -6.5,
                sharpeRatio: -0.4,
                maxDrawdownPct: 12.6,
              },
            },
          ],
          worstScenario: {
            scenarioKey: 'single_day_shock_down_15',
          },
        },
      },
    });

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: '参数与假设' }));
    const parametersPanel = await screen.findByTestId('deterministic-result-tab-panel-parameters');
    const panelWithin = within(parametersPanel);
    const robustnessSummary = panelWithin.getByText(translate('zh', 'backtest.resultPage.riskControls.robustnessDisclosure'));
    const robustnessDisclosure = robustnessSummary.closest('details');

    expect(robustnessDisclosure).not.toHaveAttribute('open');
    expect(panelWithin.getAllByText('可用').length).toBeGreaterThan(0);
    expect(panelWithin.getByText('Walk-forward 窗口')).toBeInTheDocument();
    expect(panelWithin.getByText('4')).toBeInTheDocument();
    expect(panelWithin.getAllByText('蒙特卡洛模拟').length).toBeGreaterThan(0);
    expect(panelWithin.getAllByText('200').length).toBeGreaterThan(0);
    expect(panelWithin.getAllByText('压力场景').length).toBeGreaterThan(0);
    expect(panelWithin.getAllByText('3').length).toBeGreaterThan(0);
    expect(panelWithin.getByText('Walk-forward 平均收益')).toBeInTheDocument();
    expect(panelWithin.getAllByText('6.20%').length).toBeGreaterThan(0);
    expect(panelWithin.getByText('蒙特卡洛中位收益')).toBeInTheDocument();
    expect(panelWithin.getAllByText('8.40%').length).toBeGreaterThan(0);
    expect(panelWithin.getAllByText('最差场景').length).toBeGreaterThan(0);
    expect(panelWithin.getAllByText('单日冲击下跌 15%').length).toBeGreaterThan(0);
    expect(panelWithin.queryByText('single_day_shock_down_15')).not.toBeInTheDocument();
    expect(panelWithin.getByText('蒙特卡洛分布')).toBeInTheDocument();
    expect(panelWithin.getByText('P05 总收益')).toBeInTheDocument();
    expect(panelWithin.getByText('-3.60%')).toBeInTheDocument();
    expect(panelWithin.getByText('平均总收益')).toBeInTheDocument();
    expect(panelWithin.getByText('7.10%')).toBeInTheDocument();
    expect(panelWithin.getByText('P95 总收益')).toBeInTheDocument();
    expect(panelWithin.getByText('16.80%')).toBeInTheDocument();
    expect(panelWithin.getByText('最差最大回撤')).toBeInTheDocument();
    expect(panelWithin.getByText('-12.50%')).toBeInTheDocument();
    expect(panelWithin.getByText('随机种子')).toBeInTheDocument();
    expect(panelWithin.getByText('20,260,423')).toBeInTheDocument();
    expect(panelWithin.getByText('压力场景明细')).toBeInTheDocument();
    expect(panelWithin.getByText('波动率来回扫')).toBeInTheDocument();
    expect(panelWithin.getByText(/收益 -18\.40%/)).toBeInTheDocument();
    expect(panelWithin.getByText(/Sharpe -1\.10/)).toBeInTheDocument();
    expect(panelWithin.getByText(/回撤 -21\.30%/)).toBeInTheDocument();
    expect(panelWithin.getAllByText('最差场景').length).toBeGreaterThan(0);
    expect(panelWithin.getByTestId('robustness-lens')).toBeInTheDocument();
    expect(panelWithin.getByText(translate('zh', 'backtest.resultPage.riskControls.robustnessLens'))).toBeInTheDocument();
    expect(panelWithin.getByTestId('robustness-coverage-overview')).toBeInTheDocument();
    expect(panelWithin.getByText(translate('zh', 'backtest.resultPage.riskControls.coverageTrack'))).toBeInTheDocument();
    expect(panelWithin.getByTestId('robustness-lens-row-walk-forward')).toHaveTextContent('4 窗口');
    expect(panelWithin.getByTestId('robustness-lens-row-monte-carlo')).toHaveTextContent('200 路径');
    expect(panelWithin.getByTestId('robustness-lens-row-stress-tests')).toHaveTextContent('3 场景');
  });

  it('renders compact Monte Carlo and stress placeholders when robustness details are missing', async () => {
    const currentRun = makeResultRun({
      robustnessAnalysis: {
        state: 'partial',
        monteCarlo: {
          state: 'partial',
        },
        stressTests: {
          state: 'insufficient_history',
          scenarioCount: 0,
        },
      },
    });

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: '参数与假设' }));
    const parametersPanel = await screen.findByTestId('deterministic-result-tab-panel-parameters');
    const panelWithin = within(parametersPanel);

    expect(panelWithin.getByText('蒙特卡洛分布')).toBeInTheDocument();
    expect(panelWithin.getByText('现有结果未提供可展示的蒙特卡洛分布摘要。')).toBeInTheDocument();
    expect(panelWithin.getByText('压力场景明细')).toBeInTheDocument();
    expect(panelWithin.getByText('样本不足，暂无可展示的压力场景明细。')).toBeInTheDocument();
  });

  it('renders compact walk-forward diagnostics in the overview tab from existing robustness analysis', async () => {
    const currentRun = makeResultRun({
      robustnessAnalysis: {
        state: 'available',
        walkForward: {
          state: 'available',
          windowCount: 4,
          aggregateMetrics: {
            meanTotalReturnPct: 6.2,
            maxDrawdownPct: -3.1,
          },
        },
      },
    });

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toBeInTheDocument();

    const overviewSummary = screen.getByTestId('overview-walk-forward-summary');
    expect(overviewSummary).toHaveTextContent('样本外稳健性');
    expect(overviewSummary).toHaveTextContent('固定窗口');
    expect(overviewSummary).toHaveTextContent('可用');
    expect(overviewSummary).toHaveTextContent('4 窗口');
    expect(overviewSummary).toHaveTextContent('6.20%');
    expect(overviewSummary).toHaveTextContent('-3.10%');
  });

  it('renders a compact insufficient-history state in the overview tab when walk-forward diagnostics cannot run', async () => {
    const currentRun = makeResultRun({
      robustnessAnalysis: {
        state: 'insufficient_history',
        walkForward: {
          state: 'insufficient_history',
        },
      },
    });

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toBeInTheDocument();

    const overviewSummary = screen.getByTestId('overview-walk-forward-summary');
    expect(overviewSummary).toHaveTextContent('样本外稳健性');
    expect(overviewSummary).toHaveTextContent('样本不足');
    expect(overviewSummary).not.toHaveTextContent('4 窗口');
  });

  it('surfaces additive robustness and risk-control panels in the unified dashboard stage', async () => {
    const baselineRun = makeResultRun();
    const currentRun = makeResultRun({
      parsedStrategy: {
        ...baselineRun.parsedStrategy,
        strategySpec: {
          ...(baselineRun.parsedStrategy?.strategySpec || {}),
          riskControls: {
            stopLossPct: 5,
            takeProfitPct: 10,
            trailingStopPct: 8,
          },
        },
      },
      robustnessAnalysis: {
        state: 'available',
        configuration: {
          walkForward: {
            maxWindows: 6,
          },
          monteCarlo: {
            simulationCount: 250,
          },
          stressTests: {
            scenarioKeys: ['single_day_shock_down_15', 'volatility_whipsaw', 'gap_down_open'],
          },
        },
        walkForward: {
          windowCount: 4,
          aggregateMetrics: {
            meanTotalReturnPct: 6.2,
          },
        },
        monteCarlo: {
          simulationCount: 200,
          aggregateMetrics: {
            medianTotalReturnPct: 8.4,
          },
        },
        stressTests: {
          scenarioCount: 3,
          worstScenario: {
            scenarioKey: 'single_day_shock_down_15',
          },
        },
      },
    });

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toBeInTheDocument();

    expect(screen.getByTestId('result-additive-dashboard')).toBeInTheDocument();
    expect(screen.getByTestId('dashboard-robustness-panel')).toBeInTheDocument();
    expect(screen.getByTestId('dashboard-robustness-panel')).toHaveAttribute('title', translate('zh', 'backtest.resultPage.riskControls.robustnessPanelTitle'));
    expect(screen.getByText(translate('zh', 'backtest.resultPage.riskControls.robustnessCard'))).toBeInTheDocument();
    expect(screen.getByTestId('dashboard-risk-controls-panel')).toBeInTheDocument();
    expect(screen.getByTestId('dashboard-risk-controls-panel')).toHaveAttribute('title', translate('zh', 'backtest.resultPage.riskControls.riskControlPanelTitle'));
    expect(screen.getByText(translate('zh', 'backtest.resultPage.riskControls.riskControlCard'))).toBeInTheDocument();
    expect(screen.getByText('已启用 3 项')).toBeInTheDocument();
  });

  it('adds hover tooltips and linked highlights for additive robustness and risk-control cards', async () => {
    const baselineRun = makeResultRun();
    const currentRun = makeResultRun({
      parsedStrategy: {
        ...baselineRun.parsedStrategy,
        strategySpec: {
          ...(baselineRun.parsedStrategy?.strategySpec || {}),
          riskControls: {
            stopLossPct: 5,
            takeProfitPct: 10,
            trailingStopPct: 8,
          },
        },
      },
      robustnessAnalysis: {
        state: 'available',
        configuration: {
          walkForward: {
            maxWindows: 6,
          },
          monteCarlo: {
            simulationCount: 250,
          },
          stressTests: {
            scenarioKeys: ['single_day_shock_down_15', 'volatility_whipsaw', 'gap_down_open'],
          },
        },
        walkForward: {
          windowCount: 4,
          aggregateMetrics: {
            meanTotalReturnPct: 6.2,
          },
        },
        monteCarlo: {
          simulationCount: 200,
          aggregateMetrics: {
            medianTotalReturnPct: 8.4,
          },
        },
        stressTests: {
          scenarioCount: 3,
          worstScenario: {
            scenarioKey: 'single_day_shock_down_15',
          },
        },
      },
    });

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: '参数与假设' }));
    expect(await screen.findByTestId('deterministic-result-tab-panel-parameters')).toBeInTheDocument();

    expect(screen.queryByTestId('dashboard-robustness-hover-tooltip')).not.toBeInTheDocument();
    fireEvent.mouseEnter(screen.getByTestId('dashboard-robustness-row-walk-forward'));

    expect(screen.getByTestId('dashboard-robustness-hover-tooltip')).toHaveTextContent('Walk-forward');
    expect(screen.getByTestId('robustness-lens-row-walk-forward')).toHaveAttribute('data-linked-highlight', 'true');

    fireEvent.mouseEnter(screen.getByTestId('dashboard-risk-controls-row-stop-loss'));

    expect(screen.getByTestId('dashboard-risk-controls-hover-tooltip')).toHaveTextContent('风险退出参考阈值');
    expect(screen.getByTestId('dashboard-risk-controls-threshold-summary')).toHaveAttribute('data-linked-highlight', 'true');
    expect(screen.getByTestId('result-risk-controls-row-stop-loss')).toHaveAttribute('data-linked-highlight', 'true');
  });

  it('supports keyboard focus tooltips and linked highlights for additive robustness and risk-control cards', async () => {
    const baselineRun = makeResultRun();
    const currentRun = makeResultRun({
      parsedStrategy: {
        ...baselineRun.parsedStrategy,
        strategySpec: {
          ...(baselineRun.parsedStrategy?.strategySpec || {}),
          riskControls: {
            stopLossPct: 5,
            takeProfitPct: 10,
            trailingStopPct: 8,
          },
        },
      },
      robustnessAnalysis: {
        state: 'available',
        configuration: {
          walkForward: {
            maxWindows: 6,
          },
          monteCarlo: {
            simulationCount: 250,
          },
          stressTests: {
            scenarioKeys: ['single_day_shock_down_15', 'volatility_whipsaw', 'gap_down_open'],
          },
        },
        walkForward: {
          windowCount: 4,
          aggregateMetrics: {
            meanTotalReturnPct: 6.2,
          },
        },
        monteCarlo: {
          simulationCount: 200,
          aggregateMetrics: {
            medianTotalReturnPct: 8.4,
          },
        },
        stressTests: {
          scenarioCount: 3,
          worstScenario: {
            scenarioKey: 'single_day_shock_down_15',
          },
        },
      },
    });

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: '参数与假设' }));
    expect(await screen.findByTestId('deterministic-result-tab-panel-parameters')).toBeInTheDocument();

    const robustnessRow = screen.getByTestId('dashboard-robustness-row-walk-forward');
    expect(robustnessRow).toHaveAttribute('tabindex', '0');
    fireEvent.focus(robustnessRow);

    const robustnessTooltip = screen.getByTestId('dashboard-robustness-hover-tooltip');
    expect(robustnessTooltip).toHaveTextContent('Walk-forward');
    expect(robustnessTooltip).toHaveAttribute('role', 'tooltip');
    expect(robustnessTooltip).toHaveAttribute('id', 'dashboard-robustness-hover-tooltip');
    expect(robustnessRow).toHaveAttribute('aria-describedby', 'dashboard-robustness-hover-tooltip');
    expect(screen.getByTestId('robustness-lens-row-walk-forward')).toHaveAttribute('data-linked-highlight', 'true');

    fireEvent.blur(robustnessRow);
    expect(screen.queryByTestId('dashboard-robustness-hover-tooltip')).not.toBeInTheDocument();
    expect(robustnessRow).not.toHaveAttribute('aria-describedby');

    const riskControlRow = screen.getByTestId('dashboard-risk-controls-row-stop-loss');
    expect(riskControlRow).toHaveAttribute('tabindex', '0');
    fireEvent.focus(riskControlRow);

    const riskControlTooltip = screen.getByTestId('dashboard-risk-controls-hover-tooltip');
    expect(riskControlTooltip).toHaveTextContent('风险退出参考阈值');
    expect(riskControlTooltip).toHaveAttribute('role', 'tooltip');
    expect(riskControlTooltip).toHaveAttribute('id', 'dashboard-risk-controls-hover-tooltip');
    expect(riskControlRow).toHaveAttribute('aria-describedby', 'dashboard-risk-controls-hover-tooltip');
    expect(screen.getByTestId('dashboard-risk-controls-threshold-summary')).toHaveAttribute('data-linked-highlight', 'true');
    expect(screen.getByTestId('result-risk-controls-row-stop-loss')).toHaveAttribute('data-linked-highlight', 'true');

    fireEvent.blur(riskControlRow);
    expect(screen.queryByTestId('dashboard-risk-controls-hover-tooltip')).not.toBeInTheDocument();
    expect(riskControlRow).not.toHaveAttribute('aria-describedby');
  });

  it('renders indicator risk controls as a read-only protection ladder in the parameters tab', async () => {
    const baselineRun = makeResultRun();
    const currentRun = makeResultRun({
      parsedStrategy: {
        ...baselineRun.parsedStrategy,
        strategySpec: {
          ...(baselineRun.parsedStrategy?.strategySpec || {}),
          riskControls: {
            stopLossPct: 5,
            takeProfitPct: 10,
            trailingStopPct: 8,
          },
        },
      },
    });

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: '参数与假设' }));
    expect(await screen.findByTestId('deterministic-result-tab-panel-parameters')).toBeInTheDocument();

    const riskControlsVisualization = screen.getByTestId('result-risk-controls-visualization');
    expect(riskControlsVisualization).toBeInTheDocument();
    expect(within(riskControlsVisualization).getByText(translate('zh', 'backtest.resultPage.riskControls.protectionLadder'))).toBeInTheDocument();
    expect(within(riskControlsVisualization).getByText('已启用 3 项')).toBeInTheDocument();
    expect(within(riskControlsVisualization).getByText(translate('zh', 'backtest.resultPage.riskControls.highestThreshold', { value: '10.00' }))).toBeInTheDocument();
    expect(screen.getByTestId('result-risk-controls-row-stop-loss')).toHaveTextContent('5.00%');
    expect(screen.getByTestId('result-risk-controls-row-take-profit')).toHaveTextContent('10.00%');
    expect(screen.getByTestId('result-risk-controls-row-trailing-stop')).toHaveTextContent('8.00%');
  });

  it('hides the robustness analysis section when legacy runs only expose an empty object', async () => {
    const currentRun = makeResultRun({
      robustnessAnalysis: {},
    });

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toBeInTheDocument();
    expect(screen.getByTestId('overview-walk-forward-summary')).toHaveTextContent('样本外稳健性');
    expect(screen.getByTestId('overview-walk-forward-summary')).toHaveTextContent('不可用');

    fireEvent.click(screen.getByRole('tab', { name: '参数与假设' }));
    expect(await screen.findByTestId('deterministic-result-tab-panel-parameters')).toBeInTheDocument();

    expect(screen.queryByText(translate('zh', 'backtest.resultPage.riskControls.robustnessDisclosure'))).not.toBeInTheDocument();
  });

  it('lets users cancel active runs from the result page', async () => {
    const queuedRun = makeResultRun({
      status: 'queued',
      completedAt: null,
      statusMessage: '策略已提交，等待开始执行。',
      statusHistory: [{ status: 'queued', at: '2026-04-07T08:00:00Z' }],
      auditRows: [],
      executionTrace: null,
    });
    const cancelledRun = makeResultRun({
      status: 'cancelled',
      completedAt: '2026-04-07T08:00:45Z',
      statusMessage: '规则回测已取消。',
      statusHistory: [
        { status: 'queued', at: '2026-04-07T08:00:00Z' },
        { status: 'cancelled', at: '2026-04-07T08:00:45Z' },
      ],
      auditRows: [],
      executionTrace: null,
    });

    getRuleBacktestRun
      .mockResolvedValueOnce(queuedRun)
      .mockResolvedValueOnce(cancelledRun);
    cancelRuleBacktestRun.mockResolvedValue({
      id: 99,
      code: 'ORCL',
      status: 'cancelled',
      statusMessage: '规则回测已取消。',
      statusHistory: cancelledRun.statusHistory,
      runAt: queuedRun.runAt,
      completedAt: cancelledRun.completedAt,
      noResultReason: 'cancelled',
      noResultMessage: '规则回测已取消。',
      tradeCount: 0,
      parsedConfidence: 0.97,
      needsConfirmation: false,
    });
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [cancelledRun],
    });

    renderResultPage();

    expect(await screen.findByText('取消运行')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '取消运行' }));

    await waitFor(() => {
      expect(cancelRuleBacktestRun).toHaveBeenCalledWith(99);
    });
    expect(await screen.findByText('回测已取消')).toBeInTheDocument();
  });

  it('renders a fail-closed empty visualization when a completed run has no result rows', async () => {
    const emptyRun = makeResultRun({
      auditRows: [],
      executionTrace: null,
      equityCurve: [],
      dailyReturnSeries: [],
      exposureCurve: [],
      benchmarkCurve: [],
      buyAndHoldCurve: [],
      trades: [],
      totalReturnPct: null,
      annualizedReturnPct: null,
      benchmarkReturnPct: null,
      excessReturnVsBenchmarkPct: null,
      buyAndHoldReturnPct: null,
      excessReturnVsBuyAndHoldPct: null,
      winRatePct: null,
      avgTradeReturnPct: null,
      maxDrawdownPct: null,
      finalEquity: null,
      noResultReason: 'no_entry_signal',
      noResultMessage: '回测窗口内没有触发任何入场信号。',
    });

    getRuleBacktestRun.mockResolvedValue(emptyRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [emptyRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-result-empty-state')).toBeInTheDocument();
    expect(screen.getByText('暂无可视化结果')).toBeInTheDocument();
    expect(screen.getByText('回测窗口内没有触发任何入场信号。')).toBeInTheDocument();
    expect(screen.queryByTestId('deterministic-backtest-chart-workspace')).not.toBeInTheDocument();
  });

  it('keeps historical navigation on the same result-page rendering path', async () => {
    const currentRun = makeResultRun({ id: 99, runAt: '2026-04-07T08:00:00Z' });
    const historyRun = makeResultRun({
      id: 123,
      runAt: '2026-04-08T08:00:00Z',
      completedAt: '2026-04-08T08:02:00Z',
      auditRows: [
        {
          date: '2026-02-01',
          targetPosition: 0,
          totalPortfolioValue: 100000,
          cumulativeStrategyReturnPct: 0,
          dailyPnl: 0,
          dailyReturnPct: 0,
        },
        {
          date: '2026-02-02',
          targetPosition: 1,
          executedAction: 'buy',
          fillPrice: 99,
          totalPortfolioValue: 101500,
          cumulativeStrategyReturnPct: 1.5,
          dailyPnl: 1500,
          dailyReturnPct: 1.5,
        },
        {
          date: '2026-02-03',
          targetPosition: 0,
          executedAction: 'sell',
          fillPrice: 104,
          totalPortfolioValue: 104000,
          cumulativeStrategyReturnPct: 4,
          dailyPnl: 2500,
          dailyReturnPct: 2.46,
        },
      ],
    });

    getRuleBacktestRun.mockImplementation(async (id: number) => (id === 123 ? historyRun : currentRun));
    getRuleBacktestRuns.mockResolvedValue({
      total: 2,
      page: 1,
      limit: 10,
      items: [currentRun, historyRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toHaveAttribute('data-run-id', '99');
    fireEvent.click(screen.getByRole('tab', { name: '历史结果' }));
    expect(await screen.findByText('同标的历史回测')).toBeInTheDocument();
    const historyButtons = await screen.findAllByRole('button', { name: '查看' });

    fireEvent.click(historyButtons[1]);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: '确定性回测结果 #123' })).toBeInTheDocument();
    });
    expect(screen.getByTestId('deterministic-backtest-result-view')).toHaveAttribute('data-run-id', '123');
    expect(await screen.findByTestId('deterministic-backtest-chart-workspace', undefined, { timeout: CHART_IMPORT_TIMEOUT })).toHaveAttribute('data-row-count', '3');
  }, 10000);

  it('supports side-by-side comparison from the history tab', async () => {
    const currentRun = makeResultRun({ id: 99 });
    const compareRun = makeResultRun({
      id: 123,
      totalReturnPct: 2.1,
      excessReturnVsBenchmarkPct: -0.8,
      maxDrawdownPct: 3.4,
      tradeCount: 2,
      winRatePct: 50,
    });

    getRuleBacktestRun.mockImplementation(async (id: number) => (id === 123 ? compareRun : currentRun));
    getRuleBacktestRuns.mockResolvedValue({
      total: 2,
      page: 1,
      limit: 10,
      items: [currentRun, compareRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: '历史结果' }));
    expect(await screen.findByText('运行比较')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('checkbox', { name: '比较运行 123' }));

    await waitFor(() => {
      expect(getRuleBacktestRun).toHaveBeenCalledWith(123);
    });
    expect(await screen.findByLabelText('回测比较收益进度图')).toBeInTheDocument();
    expect(screen.getAllByText('比较运行 #123').length).toBeGreaterThan(0);
  });

  it('opens the compare workbench from the history tab selection', async () => {
    const currentRun = makeResultRun({ id: 99 });
    const compareRun = makeResultRun({ id: 123 });

    getRuleBacktestRun.mockImplementation(async (id: number) => (id === 123 ? compareRun : currentRun));
    getRuleBacktestRuns.mockResolvedValue({
      total: 2,
      page: 1,
      limit: 10,
      items: [currentRun, compareRun],
    });

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: '历史结果' }));
    fireEvent.click(await screen.findByRole('checkbox', { name: '比较运行 123' }));

    await waitFor(() => {
      expect(getRuleBacktestRun).toHaveBeenCalledWith(123);
    });

    fireEvent.click(screen.getByRole('button', { name: '打开比较工作台' }));

    expect(await screen.findByTestId('rule-backtest-compare-route')).toBeInTheDocument();
  });

  it('supports the integrated compare workbench flow from history selection through key compare actions', async () => {
    const currentRun = makeResultRun({ id: 99 });
    const compareRun = makeResultRun({
      id: 123,
      totalReturnPct: 2.1,
      annualizedReturnPct: null,
      excessReturnVsBenchmarkPct: -0.8,
      maxDrawdownPct: 3.4,
      tradeCount: 2,
      winRatePct: 50,
      startDate: '2026-02-01',
      endDate: '2026-03-31',
      periodStart: '2026-02-01',
      periodEnd: '2026-03-31',
      completedAt: '2026-04-08T08:03:00Z',
    });
    const toCompareItem = (run: RuleBacktestRunResponse) => ({
      metadata: {
        id: run.id,
        code: run.code,
        status: run.status,
        runAt: run.runAt,
        completedAt: run.completedAt,
        timeframe: run.timeframe,
        startDate: run.startDate,
        endDate: run.endDate,
        periodStart: run.periodStart,
        periodEnd: run.periodEnd,
        lookbackBars: run.lookbackBars,
        initialCapital: run.initialCapital,
        feeBps: run.feeBps,
        slippageBps: run.slippageBps,
      },
      metrics: {
        tradeCount: run.tradeCount,
        winCount: run.winCount,
        lossCount: run.lossCount,
        totalReturnPct: run.totalReturnPct,
        annualizedReturnPct: run.annualizedReturnPct,
        benchmarkReturnPct: run.benchmarkReturnPct,
        excessReturnVsBenchmarkPct: run.excessReturnVsBenchmarkPct,
        buyAndHoldReturnPct: run.buyAndHoldReturnPct,
        excessReturnVsBuyAndHoldPct: run.excessReturnVsBuyAndHoldPct,
        winRatePct: run.winRatePct,
        avgTradeReturnPct: run.avgTradeReturnPct,
        maxDrawdownPct: run.maxDrawdownPct,
        avgHoldingDays: run.avgHoldingDays,
        avgHoldingBars: run.avgHoldingBars,
        avgHoldingCalendarDays: run.avgHoldingCalendarDays,
        finalEquity: run.finalEquity,
      },
      parsedStrategy: run.parsedStrategy,
      benchmark: {
        mode: run.benchmarkMode,
        code: run.benchmarkCode,
        returnPct: run.benchmarkReturnPct,
      },
    });

    getRuleBacktestRun.mockImplementation(async (id: number) => (id === 123 ? compareRun : currentRun));
    getRuleBacktestRuns.mockResolvedValue({
      total: 2,
      page: 1,
      limit: 10,
      items: [currentRun, compareRun],
    });
    compareRuleBacktestRuns.mockImplementation(async ({ runIds }: { runIds: number[] }) => {
      const baselineRunId = runIds[0];
      const candidateRunId = runIds.find((id) => id !== baselineRunId) || runIds[1];
      const baseline = baselineRunId === 99 ? currentRun : compareRun;
      const candidate = candidateRunId === 99 ? currentRun : compareRun;
      const baselineTotalReturn = baseline.totalReturnPct ?? 0;
      const candidateTotalReturn = candidate.totalReturnPct ?? 0;

      return {
        comparisonSource: 'stored_rule_backtest_runs',
        readMode: 'stored_first',
        requestedRunIds: runIds,
        resolvedRunIds: runIds,
        comparableRunIds: runIds,
        missingRunIds: [],
        unavailableRuns: [],
        fieldGroups: ['market_code_comparison', 'period_comparison', 'comparison_summary'],
        marketCodeComparison: {
          baselineRunId,
          selectionRule: 'first_comparable_run_by_request_order',
          relationship: 'same_code',
          state: 'direct',
          directlyComparable: true,
          diagnostics: ['same_normalized_code'],
        },
        periodComparison: {
          baselineRunId,
          selectionRule: 'first_comparable_run_by_request_order',
          relationship: 'overlapping',
          state: 'comparable',
          meaningfullyComparable: true,
          diagnostics: ['overlapping_periods'],
        },
        comparisonSummary: {
          baseline: {
            runId: baselineRunId,
            selectionRule: 'first_comparable_run_by_request_order',
            code: baseline.code,
            timeframe: baseline.timeframe,
            startDate: baseline.startDate,
            endDate: baseline.endDate,
            strategyFamily: baseline.parsedStrategy?.strategySpec?.strategyFamily || 'moving_average_crossover',
            strategyType: baseline.parsedStrategy?.strategySpec?.strategyType || 'moving_average_crossover',
          },
          context: {
            codeValues: [baseline.code || compareRun.code || currentRun.code],
            timeframeValues: ['daily'],
            strategyFamilyValues: ['moving_average_crossover'],
            strategyTypeValues: ['moving_average_crossover'],
            dateRanges: [
              { runId: currentRun.id, startDate: currentRun.startDate, endDate: currentRun.endDate },
              { runId: compareRun.id, startDate: compareRun.startDate, endDate: compareRun.endDate },
            ],
            allSameCode: true,
            allSameTimeframe: true,
            allSameDateRange: false,
          },
          metricDeltas: {
            totalReturnPct: {
              label: 'total_return_pct',
              state: 'comparable',
              baselineRunId,
              baselineValue: baselineTotalReturn,
              availableRunIds: runIds,
              unavailableRunIds: [],
              deltas: [
                { runId: baselineRunId, value: baselineTotalReturn, deltaVsBaseline: 0 },
                { runId: candidateRunId, value: candidateTotalReturn, deltaVsBaseline: candidateTotalReturn - baselineTotalReturn },
              ],
            },
            annualizedReturnPct: {
              label: 'annualized_return_pct',
              state: 'partial',
              baselineRunId,
              baselineValue: baseline.annualizedReturnPct,
              availableRunIds: baseline.annualizedReturnPct == null ? [] : [baselineRunId],
              unavailableRunIds: candidate.annualizedReturnPct == null ? [candidateRunId] : [],
              deltas: baseline.annualizedReturnPct == null ? [] : [{ runId: baselineRunId, value: baseline.annualizedReturnPct, deltaVsBaseline: 0 }],
            },
          },
        },
        robustnessSummary: {
          baselineRunId,
          selectionRule: 'first_comparable_run_by_request_order',
          overallState: 'partially_comparable',
          directlyComparable: false,
          alignedDimensions: ['market_code'],
          partialDimensions: ['periods'],
          divergentDimensions: [],
          unavailableDimensions: [],
          dimensions: {},
          diagnostics: ['partial_metric_deltas'],
        },
        comparisonProfile: {
          baselineRunId,
          selectionRule: 'first_comparable_run_by_request_order',
          primaryProfile: 'same_code_different_periods',
          alignedDimensions: ['market_code'],
          drivingDimensions: ['periods'],
          dimensionFlags: {
            sameCode: true,
            sameMarket: true,
            crossMarket: false,
            sameStrategyFamily: true,
            parameterDifferencesPresent: false,
            periodDifferencesPresent: true,
          },
          diagnostics: ['overlapping_periods'],
        },
        comparisonHighlights: {
          baselineRunId,
          selectionRule: 'first_comparable_run_by_request_order',
          primaryProfile: 'same_code_different_periods',
          overallContextState: 'partially_comparable',
          highlights: {
            totalReturnPct: {
              metric: 'total_return_pct',
              preference: 'higher_is_better',
              state: 'limited_context_winner',
              winnerRunIds: baselineTotalReturn >= candidateTotalReturn ? [baselineRunId] : [candidateRunId],
              winnerValue: Math.max(baselineTotalReturn, candidateTotalReturn),
              availableRunIds: runIds,
              candidateCount: 2,
              diagnostics: ['partially_comparable_context'],
            },
            annualizedReturnPct: {
              metric: 'annualized_return_pct',
              preference: 'higher_is_better',
              state: 'unavailable',
              winnerRunIds: [],
              winnerValue: null,
              availableRunIds: baseline.annualizedReturnPct == null ? [] : [baselineRunId],
              candidateCount: baseline.annualizedReturnPct == null ? 0 : 1,
              diagnostics: ['metric_unavailable'],
            },
          },
          diagnostics: ['partially_comparable_context', 'metric_unavailable'],
        },
        parameterComparison: {
          state: 'same_family_comparable',
          strategyFamilyValues: ['moving_average_crossover'],
          strategyTypeValues: ['moving_average_crossover'],
          sharedParameterKeys: ['strategy_spec.execution.signal_timing'],
          differingParameterKeys: ['strategy_spec.signal.fast_period'],
          missingParameterKeys: [],
          sharedParameters: {},
          differingParameters: {},
          missingParameters: {},
        },
        items: [toCompareItem(currentRun), toCompareItem(compareRun)],
      };
    });

    renderResultPageWithCompareWorkbench();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: '历史结果' }));
    fireEvent.click(screen.getByRole('checkbox', { name: '比较运行 123' }));

    await waitFor(() => {
      expect(getRuleBacktestRun).toHaveBeenCalledWith(123);
    });

    fireEvent.click(screen.getByRole('button', { name: '打开比较工作台' }));

    expect(await screen.findByRole('heading', { name: '规则回测比较工作台' })).toBeInTheDocument();
    expect(compareRuleBacktestRuns).toHaveBeenCalledWith({ runIds: [99, 123] });
    expect(screen.getByRole('navigation', { name: '比较区块导航' })).toBeInTheDocument();

    const parameterToggle = screen.getAllByRole('button', { name: '收起 参数与指标' })[0];
    const parameterDisclosure = parameterToggle.closest('[data-linear-primitive="disclosure"]');
    expect(parameterDisclosure).not.toBeNull();
    expect(parameterDisclosure).toHaveTextContent('参数差异与已校验指标差异放在同一工作台里读');
    fireEvent.click(parameterToggle);
    expect(within(parameterDisclosure as HTMLElement).getByRole('button', { name: '展开 参数与指标' })).toBeInTheDocument();
    fireEvent.click(within(parameterDisclosure as HTMLElement).getByRole('button', { name: '展开 参数与指标' }));
    expect(within(parameterDisclosure as HTMLElement).getByRole('button', { name: '收起 参数与指标' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '复制摘要' }));
    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalledWith('比较运行 99,123 | 基准 #99 ORCL | 整体 部分可比 | 画像 同标的不同区间 | 可比 2/2');
    });
    expect(screen.getByText('已复制比较摘要')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '设为基准 123' }));
    await waitFor(() => {
      expect(compareRuleBacktestRuns).toHaveBeenLastCalledWith({ runIds: [123, 99] });
    });
    expect(screen.getByRole('columnheader', { name: /#123 基准/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '移除运行 99' }));
    expect(await screen.findByText('至少需要 2 条已完成运行才能打开比较工作台。')).toBeInTheDocument();
  });

  it('updates the inline report when compare summary adds parameter stability evidence', async () => {
    const currentRun = makeResultRun({ id: 99 });
    const compareRun = makeResultRun({ id: 123, totalReturnPct: 26.8, benchmarkReturnPct: 20.1 });
    getRuleBacktestRun.mockImplementation(async (id: number) => (id === 123 ? compareRun : currentRun));
    getRuleBacktestRuns.mockResolvedValue({
      total: 2,
      page: 1,
      limit: 10,
      items: [currentRun, compareRun],
    });
    compareRuleBacktestRuns.mockResolvedValue({
      comparisonSource: 'stored_compare_summary',
      readMode: 'stored_first',
      requestedRunIds: [99, 123],
      resolvedRunIds: [99, 123],
      comparableRunIds: [99, 123],
      missingRunIds: [],
      unavailableRuns: [],
      fieldGroups: ['parameter_stability_evidence'],
      parameterStabilityEvidence: {
        contractKind: 'backtest_parameter_stability_diagnostic_evidence',
        state: 'available',
        diagnosticOnly: true,
        decisionGrade: false,
        source: 'stored_compare_summary',
      },
      items: [],
    });

    renderResultPage();

    const parameterRow = await screen.findByTestId('backtest-research-review-row-parameter');
    expect(parameterRow).toHaveTextContent('缺失 / 待验证');
    expect(compareRuleBacktestRuns).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('tab', { name: '历史结果' }));
    await act(async () => {
      await vi.dynamicImportSettled();
    });
    fireEvent.click(screen.getByRole('checkbox', { name: '比较运行 123' }));

    await waitFor(() => {
      expect(compareRuleBacktestRuns).toHaveBeenCalledWith({ runIds: [99, 123] });
    });
    await waitFor(() => {
      expect(screen.getByTestId('backtest-research-review-row-parameter')).toHaveTextContent('参数稳定性证据可用');
    });
  });

  it('keeps parameter evidence missing when compare summary loading fails', async () => {
    const currentRun = makeResultRun({ id: 99 });
    const compareRun = makeResultRun({ id: 123 });
    getRuleBacktestRun.mockImplementation(async (id: number) => (id === 123 ? compareRun : currentRun));
    getRuleBacktestRuns.mockResolvedValue({
      total: 2,
      page: 1,
      limit: 10,
      items: [currentRun, compareRun],
    });
    compareRuleBacktestRuns.mockRejectedValue(new Error('compare unavailable'));

    renderResultPage();

    expect(await screen.findByTestId('backtest-research-review-row-parameter')).toHaveTextContent('缺失 / 待验证');

    fireEvent.click(screen.getByRole('tab', { name: '历史结果' }));
    await act(async () => {
      await vi.dynamicImportSettled();
    });
    fireEvent.click(screen.getByRole('checkbox', { name: '比较运行 123' }));

    await waitFor(() => {
      expect(compareRuleBacktestRuns).toHaveBeenCalledWith({ runIds: [99, 123] });
    });
    expect(await screen.findByTestId('backtest-research-review-row-parameter')).toHaveTextContent('缺失 / 待验证');
  });

  it('runs lightweight scenario variants and exports the summary report with a robustness appendix', async () => {
    const currentRun = makeResultRun({
      id: 99,
      summary: {
        drawdownRegimeAttribution: {
          version: 'v1',
          source: 'summary.drawdown_regime_attribution',
          state: 'available',
          bucketCounts: {
            peak: {
              count: 1,
              sharePct: 33.3333,
              avgDepthPct: null,
              worstDepthPct: null,
            },
            moderate: {
              count: 2,
              sharePct: 66.6667,
              avgDepthPct: 8.5,
              worstDepthPct: 9.2,
            },
          },
          contributionSummaries: {
            classifiedRows: {
              count: 3,
              sharePct: 100,
            },
            missingRows: {
              count: 0,
              sharePct: 0,
            },
          },
          unavailableReason: null,
        },
      },
      robustnessAnalysis: {
        state: 'available',
        walkForward: {
          state: 'available',
          windowCount: 4,
          aggregateMetrics: {
            meanTotalReturnPct: 6.2,
            maxDrawdownPct: -3.1,
          },
        },
        monteCarlo: {
          state: 'available',
          simulationCount: 200,
          seed: 20260423,
          aggregateMetrics: {
            p05TotalReturnPct: -3.6,
            medianTotalReturnPct: 8.4,
            p95TotalReturnPct: 16.8,
            meanTotalReturnPct: 7.1,
            worstMaxDrawdownPct: 12.5,
          },
        },
        stressTests: {
          state: 'available',
          scenarioCount: 1,
          scenarios: [
            {
              scenarioKey: 'single_day_shock_down_15',
              metrics: {
                totalReturnPct: -18.4,
                sharpeRatio: -1.1,
                maxDrawdownPct: 21.3,
              },
            },
          ],
          worstScenario: {
            scenarioKey: 'single_day_shock_down_15',
          },
        },
      },
    });
    let nextScenarioRunId = 201;

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });
    runRuleBacktest.mockImplementation(async () =>
      makeResultRun({
        id: nextScenarioRunId++,
        totalReturnPct: 5.6,
        excessReturnVsBenchmarkPct: 2.3,
        maxDrawdownPct: 2.1,
        tradeCount: 2,
        winRatePct: 100,
        status: 'completed',
      }),
    );

    const createObjectUrlMock = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test-summary');
    const revokeObjectUrlMock = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    const clickMock = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    renderResultPage();

    expect(await screen.findByTestId('deterministic-backtest-result-view')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: '参数与假设' }));
    expect(await screen.findByTestId('deterministic-result-tab-panel-parameters')).toBeInTheDocument();

    fireEvent.click(screen.getByText('参数变体比较'));
    fireEvent.click(screen.getByRole('button', { name: '运行当前场景组' }));

    await waitFor(() => {
      expect(runRuleBacktest).toHaveBeenCalled();
    });
    expect(await screen.findByText('场景结果比较')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: '概览' }));
    fireEvent.click(screen.getByRole('button', { name: /查看可导出的结果摘要/ }));
    fireEvent.click(screen.getByRole('button', { name: '导出 Markdown' }));

    await waitFor(() => {
      expect(createObjectUrlMock).toHaveBeenCalled();
      expect(clickMock).toHaveBeenCalled();
      expect(revokeObjectUrlMock).toHaveBeenCalled();
    });

    const markdownBlob = createObjectUrlMock.mock.calls[0]?.[0] as Blob;
    const markdownText = await markdownBlob.text();
    expect(markdownText).toContain('## 稳健性附录');
    expect(markdownText).toContain('## 回撤阶段归因附录');
    expect(markdownText).toContain('Walk-forward / 样本外检验');
    expect(markdownText).toContain('模拟次数：200');
    expect(markdownText).toContain('单日冲击下跌 15%：收益 -18.40% · Sharpe -1.10 · 回撤 -21.30%');
    expect(markdownText).toContain('来源：已存审计行汇总');
    expect(markdownText).toContain('中度回撤：行数 2 · 占比 66.67% · 平均深度 -8.50% · 最深回撤 -9.20%');
    expect(markdownText).not.toMatch(/drawdown_regime_attribution|regimeAttribution|market regime|schema|payload|stored_audit_rows/i);

    fireEvent.click(screen.getByRole('button', { name: '导出 HTML' }));

    await waitFor(() => {
      expect(createObjectUrlMock).toHaveBeenCalledTimes(2);
    });

    const htmlBlob = createObjectUrlMock.mock.calls[1]?.[0] as Blob;
    const htmlText = await htmlBlob.text();
    expect(htmlText).toContain('<pre>');
    expect(htmlText).toContain('## 稳健性附录');
    expect(htmlText).toContain('## 回撤阶段归因附录');
    expect(htmlText).toContain('蒙特卡洛分布');
    expect(htmlText).toContain('高点区间：行数 1 · 占比 33.33% · 平均深度 -- · 最深回撤 --');
  });

  it('renders localized English result-shell actions and tabs', async () => {
    const currentRun = makeResultRun({ id: 99 });
    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });

    window.history.replaceState(window.history.state, '', '/en/backtest/results/99');
    renderResultPage(['/en/backtest/results/99']);

    expect(await screen.findByRole('heading', { name: /ORCL/i })).toBeInTheDocument();
    const hero = screen.getByTestId('deterministic-result-page-hero');
    expect(within(hero).getAllByRole('button', { name: translate('en', 'backtest.resultPage.hero.backToConfig') }).length).toBeGreaterThan(0);
    expect(within(hero).getAllByRole('button', { name: translate('en', 'backtest.resultPage.hero.refreshResult') }).length).toBeGreaterThan(0);
    expect(await screen.findByRole('tablist', { name: translate('en', 'backtest.resultPage.tabsAria') })).toBeInTheDocument();
    expect(await screen.findByRole('tab', { name: translate('en', 'backtest.resultPage.tabs.overview') })).toBeInTheDocument();
    expect(await screen.findByRole('tab', { name: translate('en', 'backtest.resultPage.tabs.history') })).toBeInTheDocument();
    expect(screen.getByText(translate('en', 'backtest.resultPage.overview.exportSummaryDisclosure'))).toBeInTheDocument();
  });
});
