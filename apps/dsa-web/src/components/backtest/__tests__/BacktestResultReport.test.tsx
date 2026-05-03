import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { RuleBacktestRunResponse } from '../../../types/backtest';
import BacktestResultReport from '../BacktestResultReport';

function makeRun(overrides: Partial<RuleBacktestRunResponse> = {}): RuleBacktestRunResponse {
  const auditRows = Array.from({ length: 64 }, (_, index) => ({
    date: `2026-03-${String(index + 1).padStart(2, '0')}`,
    symbolClose: 100 + index,
    benchmarkClose: 98 + index * 0.7,
    signalSummary: index === 3 ? 'MA5 > MA20' : null,
    executedAction: index === 3 ? 'buy' : index === 40 ? 'sell' : null,
    fillPrice: index === 3 ? 103 : index === 40 ? 141 : null,
    sharesHeld: index >= 3 && index < 40 ? 900 : 0,
    cash: index >= 3 && index < 40 ? 7000 : 100000,
    holdingsValue: index >= 3 && index < 40 ? 90000 + index * 250 : 0,
    totalPortfolioValue: 100000 + index * 420,
    dailyPnl: index === 0 ? 0 : 420,
    dailyReturnPct: index === 0 ? 0 : 0.42,
    cumulativeStrategyReturnPct: index * 0.62,
    cumulativeBenchmarkReturnPct: index * 0.49,
    cumulativeBuyAndHoldReturnPct: index * 0.44,
    drawdownPct: index > 10 ? -Math.min((index - 10) * 0.1, 5.2) : 0,
    fees: index === 3 || index === 40 ? 8 : 0,
    slippage: index === 3 || index === 40 ? 3 : 0,
    notes: null,
    unavailableReason: null,
  }));

  return {
    id: 77,
    code: 'ORCL',
    strategyText: 'MA cross',
    parsedStrategy: {
      version: 'v1',
      timeframe: 'daily',
      sourceText: 'MA cross',
      normalizedText: 'MA cross',
      entry: { type: 'group', op: 'and', rules: [] },
      exit: { type: 'group', op: 'or', rules: [] },
      confidence: 0.97,
      needsConfirmation: false,
      ambiguities: [],
      summary: { strategy: 'MA cross' },
      maxLookback: 20,
      strategyKind: 'moving_average_crossover',
      executable: true,
      normalizationState: 'ready',
      assumptions: [],
      assumptionGroups: [],
      setup: {},
      strategySpec: {},
    } as RuleBacktestRunResponse['parsedStrategy'],
    strategyHash: 'hash',
    timeframe: 'daily',
    startDate: '2026-03-01',
    endDate: '2026-05-03',
    periodStart: '2026-03-01',
    periodEnd: '2026-05-03',
    lookbackBars: 252,
    initialCapital: 100000,
    feeBps: 2,
    slippageBps: 1,
    parsedConfidence: 0.97,
    needsConfirmation: false,
    warnings: [],
    runAt: '2026-05-03T08:00:00Z',
    completedAt: '2026-05-03T08:03:00Z',
    status: 'completed',
    statusMessage: 'completed',
    statusHistory: [],
    noResultReason: null,
    noResultMessage: null,
    tradeCount: 2,
    winCount: 1,
    lossCount: 1,
    totalReturnPct: 24.6,
    annualizedReturnPct: 17.2,
    benchmarkMode: 'auto',
    benchmarkCode: null,
    benchmarkReturnPct: 19.4,
    excessReturnVsBenchmarkPct: 5.2,
    buyAndHoldReturnPct: 18.3,
    excessReturnVsBuyAndHoldPct: 6.3,
    winRatePct: 50,
    avgTradeReturnPct: 4.1,
    maxDrawdownPct: -8.2,
    avgHoldingDays: 18,
    avgHoldingBars: 18,
    avgHoldingCalendarDays: 20,
    finalEquity: 124600,
    summary: {},
    executionAssumptions: {
      signalTiming: 'bar close',
      fillTiming: 'next bar open',
      priceBasis: 'open',
      feeBps: 2,
      slippageBps: 1,
    },
    benchmarkCurve: [],
    benchmarkSummary: {
      label: 'QQQ',
      requestedMode: 'auto',
      resolvedMode: 'etf_qqq',
      method: 'benchmark_security',
      priceBasis: 'close',
      returnPct: 19.4,
      startDate: '2026-03-01',
      endDate: '2026-05-03',
    },
    buyAndHoldCurve: [],
    buyAndHoldSummary: {
      label: 'Buy and hold',
      requestedMode: 'same_symbol_buy_and_hold',
      resolvedMode: 'same_symbol_buy_and_hold',
      method: 'same_symbol_buy_and_hold',
      returnPct: 18.3,
    },
    auditRows,
    dailyReturnSeries: [],
    exposureCurve: [],
    equityCurve: [],
    trades: [
      {
        code: 'ORCL',
        tradeIndex: 1,
        entryDate: '2026-03-04',
        exitDate: '2026-04-10',
        entryPrice: 103,
        exitPrice: 141,
        returnPct: 36.89,
        holdingDays: 37,
        holdingBars: 27,
        holdingCalendarDays: 37,
        entrySignal: 'MA5 > MA20',
        exitSignal: 'MA5 < MA20',
        entryRule: {},
        exitRule: {},
        entryIndicators: {},
        exitIndicators: {},
        feeBps: 2,
        slippageBps: 1,
      },
    ],
    ...overrides,
  };
}

describe('BacktestResultReport', () => {
  it('renders the same core sections for simple and professional modes', () => {
    render(<BacktestResultReport run={makeRun()} mode="simple" />);
    const simpleReport = screen.getByTestId('backtest-result-report');
    expect(simpleReport).toHaveAttribute('data-report-mode', 'simple');
    expect(screen.getByTestId('backtest-report-summary')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-report-key-metrics')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-report-chart')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-report-benchmark')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-report-trade-summary')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-report-trade-table')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-report-data-quality')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-report-execution-assumptions')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-report-advanced-details')).toBeInTheDocument();

    render(<BacktestResultReport run={makeRun({ id: 78 })} mode="professional" />);
    expect(screen.getAllByTestId('backtest-result-report')[1]).toHaveAttribute('data-report-mode', 'professional');
  });

  it('uses actual metrics and safe unavailable states without crashing on minimal payloads', () => {
    render(<BacktestResultReport run={makeRun({
      totalReturnPct: null,
      benchmarkReturnPct: null,
      excessReturnVsBenchmarkPct: null,
      annualizedReturnPct: null,
      winRatePct: null,
      maxDrawdownPct: null,
      benchmarkSummary: { resolvedMode: 'none', unavailableReason: 'missing benchmark' },
      auditRows: [],
      trades: [],
      executionAssumptions: {},
    })} mode="simple" />);

    expect(screen.getByText('ORCL · 回测完成')).toBeInTheDocument();
    expect(screen.getAllByText('--').length).toBeGreaterThan(4);
    expect(screen.getByText('基准数据不足，无法计算超额收益。')).toBeInTheDocument();
    expect(screen.getByText('数据质量信息不足：当前结果未返回复权/分红/拆股元数据。')).toBeInTheDocument();
    expect(screen.getByText('执行假设信息不足：当前结果未返回成交时点/撮合规则。')).toBeInTheDocument();
  });

  it('keeps daily ledger collapsed and bounded until expanded', () => {
    render(<BacktestResultReport run={makeRun()} mode="professional" />);

    expect(screen.getByTestId('backtest-report-ledger-summary')).toHaveTextContent('64');
    expect(screen.queryByTestId('backtest-ledger-row-0')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /展开每日账本/ }));
    const ledger = screen.getByTestId('backtest-report-ledger-table');
    expect(within(ledger).getByTestId('backtest-ledger-row-0')).toBeInTheDocument();
    expect(within(ledger).queryByTestId('backtest-ledger-row-30')).not.toBeInTheDocument();
    expect(ledger).toHaveAttribute('data-visible-rows', '30');
    expect(ledger).toHaveAttribute('data-total-rows', '64');
  });

  it('limits trade rows by default and exports only trade rows', () => {
    const createObjectUrlMock = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test');
    const clickMock = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const revokeObjectUrlMock = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    const trades = Array.from({ length: 34 }, (_, index) => ({
      code: 'ORCL',
      tradeIndex: index + 1,
      entryDate: `2026-03-${String((index % 20) + 1).padStart(2, '0')}`,
      exitDate: `2026-04-${String((index % 20) + 1).padStart(2, '0')}`,
      entryPrice: 100 + index,
      exitPrice: 105 + index,
      returnPct: index % 2 === 0 ? 5 : -2,
      holdingDays: 5,
      entryRule: {},
      exitRule: {},
      entryIndicators: {},
      exitIndicators: {},
    }));

    render(<BacktestResultReport run={makeRun({ trades })} mode="simple" />);

    const table = screen.getByTestId('backtest-report-trade-table');
    expect(table).toHaveAttribute('data-visible-rows', '20');
    expect(table).toHaveAttribute('data-total-rows', '34');
    expect(within(table).getByTestId('backtest-trade-row-0')).toBeInTheDocument();
    expect(within(table).queryByTestId('backtest-trade-row-20')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '导出交易CSV' }));
    expect(createObjectUrlMock).toHaveBeenCalledTimes(1);

    createObjectUrlMock.mockRestore();
    clickMock.mockRestore();
    revokeObjectUrlMock.mockRestore();
  });
});
