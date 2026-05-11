import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
    vi.clearAllMocks();
    vi.useRealTimers();
    vi.stubGlobal('confirm', vi.fn(() => true));
    auditTablesImportGate.reset();
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
    vi.useRealTimers();
    vi.unstubAllGlobals();
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: originalClipboard,
    });
  });

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
    expect(screen.queryByTestId('deterministic-backtest-result-view')).not.toBeInTheDocument();

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
    expect(screen.getByTestId('deterministic-backtest-result-page')).toHaveAttribute('data-density', 'dense');
    expect(screen.getByTestId('deterministic-result-page-hero')).toBeInTheDocument();
    expect(screen.getByTestId('deterministic-result-dashboard')).toBeInTheDocument();
    expect(screen.queryByText('结果指标')).not.toBeInTheDocument();
    expect(screen.queryByText('联动结果图表')).not.toBeInTheDocument();
    expect(await screen.findByTestId('deterministic-backtest-chart-workspace')).toHaveAttribute('data-row-count', '3');
    expect(screen.getByRole('tab', { name: '概览' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.queryByText('日级审计 / 对账')).not.toBeInTheDocument();
    expect(screen.queryByText('交易 / 事件日志')).not.toBeInTheDocument();
    expect(screen.queryByText('同标的历史回测')).not.toBeInTheDocument();
    expect(screen.queryByText('参数快照')).not.toBeInTheDocument();
    expect(screen.getByText('已完成')).toBeInTheDocument();
    expect(screen.getByTestId('deterministic-result-kpi-bento')).toBeInTheDocument();
    expect(screen.getByTestId('deterministic-result-kpi-bento')).toHaveTextContent('年化收益');
    expect(screen.getByTestId('deterministic-result-kpi-bento')).not.toHaveTextContent('{value}');

    fireEvent.click(screen.getByRole('tab', { name: '审计明细' }));
    expect(await screen.findByTestId('deterministic-result-tab-panel-audit')).toBeInTheDocument();
    expect(screen.getByText('日级审计 / 对账')).toBeInTheDocument();
    expect(screen.getByText('执行轨迹')).toBeInTheDocument();
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

    expect(screen.getByText(translate('zh', 'backtest.resultPage.riskControls.robustnessDisclosure'))).toBeInTheDocument();
    expect(screen.getAllByText('可用').length).toBeGreaterThan(0);
    expect(screen.getByText('Walk-forward 窗口')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
    expect(screen.getByText('蒙特卡洛模拟')).toBeInTheDocument();
    expect(screen.getByText('200')).toBeInTheDocument();
    expect(screen.getByText('压力场景')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('Walk-forward 平均收益')).toBeInTheDocument();
    expect(screen.getByText('6.20%')).toBeInTheDocument();
    expect(screen.getByText('蒙特卡洛中位收益')).toBeInTheDocument();
    expect(screen.getByText('8.40%')).toBeInTheDocument();
    expect(screen.getByText('最差场景')).toBeInTheDocument();
    expect(screen.getByText('single_day_shock_down_15')).toBeInTheDocument();
    expect(screen.getByTestId('robustness-lens')).toBeInTheDocument();
    expect(screen.getByText(translate('zh', 'backtest.resultPage.riskControls.robustnessLens'))).toBeInTheDocument();
    expect(screen.getByTestId('robustness-coverage-overview')).toBeInTheDocument();
    expect(screen.getByText(translate('zh', 'backtest.resultPage.riskControls.coverageTrack'))).toBeInTheDocument();
    expect(screen.getByTestId('robustness-lens-row-walk-forward')).toHaveTextContent('4 窗口');
    expect(screen.getByTestId('robustness-lens-row-monte-carlo')).toHaveTextContent('200 路径');
    expect(screen.getByTestId('robustness-lens-row-stress-tests')).toHaveTextContent('3 场景');
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

    expect(screen.getByTestId('dashboard-risk-controls-hover-tooltip')).toHaveTextContent('止损阈值');
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
    expect(riskControlTooltip).toHaveTextContent('止损阈值');
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
    expect(await screen.findByTestId('deterministic-backtest-chart-workspace')).toHaveAttribute('data-row-count', '3');
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

    const parameterSummary = screen.getByText('展开 / 参数与指标');
    const parameterDisclosure = parameterSummary.closest('details');
    expect(parameterDisclosure).toHaveAttribute('open');
    fireEvent.click(parameterSummary.closest('summary') ?? parameterSummary);
    expect(parameterDisclosure).not.toHaveAttribute('open');
    fireEvent.click(parameterSummary.closest('summary') ?? parameterSummary);
    expect(parameterDisclosure).toHaveAttribute('open');

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

  it('runs lightweight scenario variants and exports the summary report', async () => {
    const currentRun = makeResultRun({ id: 99 });
    const scenarioRun = makeResultRun({
      id: 201,
      totalReturnPct: 5.6,
      excessReturnVsBenchmarkPct: 2.3,
      maxDrawdownPct: 2.1,
      tradeCount: 2,
      winRatePct: 100,
      status: 'completed',
    });

    getRuleBacktestRun.mockResolvedValue(currentRun);
    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [currentRun],
    });
    runRuleBacktest.mockResolvedValue(scenarioRun);

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
    fireEvent.click(screen.getByText('查看可导出的结果摘要'));
    fireEvent.click(screen.getByRole('button', { name: '导出 Markdown' }));

    await waitFor(() => {
      expect(createObjectUrlMock).toHaveBeenCalled();
      expect(clickMock).toHaveBeenCalled();
      expect(revokeObjectUrlMock).toHaveBeenCalled();
    });
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
    expect(screen.getByRole('button', { name: translate('en', 'backtest.resultPage.hero.backToConfig') })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: translate('en', 'backtest.resultPage.hero.refreshResult') })).toBeInTheDocument();
    expect(await screen.findByRole('tablist', { name: translate('en', 'backtest.resultPage.tabsAria') })).toBeInTheDocument();
    expect(await screen.findByRole('tab', { name: translate('en', 'backtest.resultPage.tabs.overview') })).toBeInTheDocument();
    expect(await screen.findByRole('tab', { name: translate('en', 'backtest.resultPage.tabs.history') })).toBeInTheDocument();
    expect(screen.getByText(translate('en', 'backtest.resultPage.overview.exportSummaryDisclosure'))).toBeInTheDocument();
  });
});
