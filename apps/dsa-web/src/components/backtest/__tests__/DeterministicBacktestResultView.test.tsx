import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../../contexts/UiLanguageContext';
import { translate } from '../../../i18n/core';
import type { RuleBacktestRunResponse } from '../../../types/backtest';
import { DeterministicAuditTable, DeterministicBacktestResultView } from '../DeterministicBacktestResultView';
import { normalizeDeterministicBacktestResult } from '../normalizeDeterministicBacktestResult';
import { AssumptionList } from '../shared';

const CHART_IMPORT_TIMEOUT = 5000;

function makeViewerRun(overrides: Partial<RuleBacktestRunResponse> = {}): RuleBacktestRunResponse {
  const auditRows = Array.from({ length: 70 }, (_, index) => {
    const day = String(index + 1).padStart(2, '0');
    return {
      date: `2026-03-${day}`,
      symbolClose: 100 + index,
      benchmarkClose: 98 + index * 0.8,
      signalSummary: index === 10 ? 'MA5 > MA20' : null,
      targetPosition: index >= 10 && index < 40 ? 1 : 0,
      executedAction: index === 10 ? 'buy' : index === 40 ? 'sell' : null,
      fillPrice: index === 10 ? 110 : index === 40 ? 140 : null,
      sharesHeld: index >= 10 && index < 40 ? 1000 : 0,
      cash: index >= 10 && index < 40 ? 5000 : 100000,
      holdingsValue: index >= 10 && index < 40 ? 100000 + index * 100 : 0,
      totalPortfolioValue: 100000 + index * 500,
      dailyPnl: index === 0 ? 0 : 500,
      dailyReturnPct: index === 0 ? 0 : 0.5,
      cumulativeStrategyReturnPct: index * 0.8,
      cumulativeBenchmarkReturnPct: index * 0.6,
      cumulativeBuyAndHoldReturnPct: index * 0.55,
      drawdownPct: index < 10 ? 0 : -Math.min((index - 9) * 0.12, 4.3),
      fees: 0,
      slippage: 0,
      notes: null,
      unavailableReason: null,
    };
  });

  return {
    id: 101,
    code: 'ORCL',
    strategyText: 'MA cross',
    parsedStrategy: {} as RuleBacktestRunResponse['parsedStrategy'],
    strategyHash: 'hash',
    timeframe: 'daily',
    startDate: '2026-03-01',
    endDate: '2026-05-09',
    periodStart: '2026-03-01',
    periodEnd: '2026-05-09',
    lookbackBars: 252,
    initialCapital: 100000,
    feeBps: 0,
    slippageBps: 0,
    parsedConfidence: 0.97,
    needsConfirmation: false,
    warnings: [],
    runAt: '2026-05-10T08:00:00Z',
    completedAt: '2026-05-10T08:03:00Z',
    status: 'completed',
    statusMessage: '规则回测已完成，可查看交易明细与执行假设。',
    statusHistory: [
      { status: 'queued', at: '2026-05-10T08:00:00Z' },
      { status: 'completed', at: '2026-05-10T08:03:00Z' },
    ],
    noResultReason: null,
    noResultMessage: null,
    tradeCount: 2,
    winCount: 1,
    lossCount: 1,
    totalReturnPct: 12.4,
    annualizedReturnPct: 18.1,
    benchmarkMode: 'auto',
    benchmarkCode: null,
    benchmarkReturnPct: 9.2,
    excessReturnVsBenchmarkPct: 3.2,
    buyAndHoldReturnPct: 8.5,
    excessReturnVsBuyAndHoldPct: 3.9,
    winRatePct: 50,
    avgTradeReturnPct: 6.2,
    maxDrawdownPct: 4.3,
    avgHoldingDays: 8,
    avgHoldingBars: 8,
    avgHoldingCalendarDays: 9,
    finalEquity: 112400,
    summary: {},
    executionAssumptions: {
      signalEvaluationTiming: 'bar close',
      entryFillTiming: 'next bar open',
    },
    benchmarkCurve: [],
    benchmarkSummary: {
      label: 'QQQ',
      requestedMode: 'auto',
      resolvedMode: 'etf_qqq',
      method: 'benchmark_security',
      returnPct: 9.2,
    },
    buyAndHoldCurve: [],
    buyAndHoldSummary: {
      label: translate('zh', 'backtest.resultPage.buyAndHoldDefault'),
      requestedMode: 'same_symbol_buy_and_hold',
      resolvedMode: 'same_symbol_buy_and_hold',
      method: 'same_symbol_buy_and_hold',
      returnPct: 8.5,
    },
    auditRows,
    dailyReturnSeries: [],
    exposureCurve: [],
    aiSummary: null,
    equityCurve: [],
    trades: [],
    ...overrides,
  };
}

describe('DeterministicBacktestResultView', () => {
  it('keeps shared assumption labels useful without exposing unknown internal fields', () => {
    const { container } = render(
      <UiLanguageProvider>
        <AssumptionList
          emptyText="暂无执行假设。"
          assumptions={{
            entry_fill_timing: 'next bar open',
            provider_calls_executed: false,
            authorityScope: 'service-only',
            contractKind: 'backtest_parameter_grid_descriptor_request_bundle',
            diagnosticOnly: true,
            decisionGrade: false,
            payload: { trace: 'provider_calls_executed=false' },
            trace: ['provider_calls_executed=false'],
            stack: 'Traceback: provider_calls_executed',
            review_note: 'provider_calls_executed=false',
            friendly_note: 'manual review retained',
          }}
        />
      </UiLanguageProvider>,
    );

    const list = container.querySelector('.audit-grid');
    expect(list).toBeInTheDocument();
    expect(list).toHaveTextContent('入场成交时点');
    expect(list).toHaveTextContent('next bar open');
    expect(list).toHaveTextContent('执行假设');
    expect(list).toHaveTextContent('已记录，需结合复查材料确认');
    expect(list).toHaveTextContent('manual review retained');
    expect(list).not.toHaveTextContent(
      /provider_calls_executed|provider calls executed|authorityScope|authority scope|contractKind|contract kind/i,
    );
    expect(list).not.toHaveTextContent(
      /diagnosticOnly|diagnostic only|decisionGrade|decision grade|payload|trace|stack|Traceback|backtest_parameter_grid_descriptor_request_bundle/i,
    );
  });

  it('renders a non-empty KPI and chart-centered overview from normalized data', async () => {
    render(<DeterministicBacktestResultView run={makeViewerRun()} />);

    const resultView = screen.getByTestId('deterministic-backtest-result-view');
    const dashboard = screen.getByTestId('deterministic-result-dashboard');
    const workspace = await screen.findByTestId('deterministic-backtest-chart-workspace', undefined, { timeout: CHART_IMPORT_TIMEOUT });
    const chartCanvas = await screen.findByLabelText(
      translate('zh', 'backtest.resultPage.chartWorkspace.cumulativeReturnChartAria'),
      undefined,
      { timeout: CHART_IMPORT_TIMEOUT },
    );

    expect(resultView).toHaveAttribute('data-row-count', '70');
    expect(resultView).toHaveAttribute('data-main-series-length', '70');
    expect(resultView).toHaveAttribute('data-daily-pnl-series-length', '70');
    expect(resultView).toHaveAttribute('data-position-series-length', '70');
    expect(resultView).toHaveAttribute('data-kpi-count', '5');
    expect(resultView).toHaveAttribute('data-density', 'dense');
    expect(dashboard).toBeInTheDocument();
    expect(screen.getByTestId('deterministic-result-risk-strip')).toBeInTheDocument();
    expect(screen.getByTestId('deterministic-result-chart-shell')).toBeInTheDocument();
    expect(screen.getByText('研究结果可视化')).toBeInTheDocument();
    expect(screen.getByText('权益曲线 / 回撤 / 每日盈亏')).toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'backtest.resultPage.auditTable.title'))).not.toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'backtest.resultPage.tradeEventTable.title'))).not.toBeInTheDocument();
    expect(workspace).toHaveAttribute('data-row-count', '70');
    expect(workspace).toHaveAttribute('data-main-series-length', '70');
    expect(workspace).toHaveAttribute('data-daily-pnl-series-length', '70');
    expect(Number(workspace.getAttribute('data-position-series-length'))).toBeGreaterThanOrEqual(0);
    expect(workspace).toHaveAttribute('data-chart-engine', 'echarts');
    expect(chartCanvas).toBeInTheDocument();
  });

  it('applies one shared density level to KPI sizing and chart sizing together', async () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: 1680 });
    window.dispatchEvent(new Event('resize'));

    render(<DeterministicBacktestResultView run={makeViewerRun()} />);

    const resultView = screen.getByTestId('deterministic-backtest-result-view');
    const workspace = await screen.findByTestId('deterministic-backtest-chart-workspace', undefined, { timeout: CHART_IMPORT_TIMEOUT });

    expect(resultView).toHaveAttribute('data-density', 'comfortable');
    expect(workspace).toHaveAttribute('data-chart-engine', 'echarts');

    Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: 1024 });
    act(() => {
      window.dispatchEvent(new Event('resize'));
    });
  });

  it('renders the new sidebar and meta strip workspace shell', async () => {
    render(<DeterministicBacktestResultView run={makeViewerRun()} />);

    const workspace = await screen.findByTestId('deterministic-backtest-chart-workspace', undefined, { timeout: CHART_IMPORT_TIMEOUT });
    expect(screen.getByTestId('deterministic-chart-meta-strip')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /回测参数/ })).toBeInTheDocument();
    expect(screen.getByText('研究结果可视化')).toBeInTheDocument();
    expect(workspace).toHaveAttribute('data-chart-engine', 'echarts');
  });

  it('exports csv from stored audit rows instead of recomputed viewer rows', async () => {
    const createObjectUrlMock = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test');
    const revokeObjectUrlMock = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    const clickMock = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const run = makeViewerRun({
      auditRows: [
        {
          date: '2026-03-01',
          symbolClose: 101,
          benchmarkClose: 99,
          position: 1,
          shares: 100,
          cash: 90000,
          holdingsValue: 10100,
          totalPortfolioValue: 100100,
          dailyPnl: 100,
          dailyReturn: 0.1,
          cumulativeReturn: 0.1,
          benchmarkCumulativeReturn: 0.05,
          buyHoldCumulativeReturn: 0.04,
          action: 'buy',
          fillPrice: 101,
          signalSummary: 'stored-row',
          notes: 'stored-note',
        },
      ],
      equityCurve: [
        { date: '2026-03-01', close: 888, totalPortfolioValue: 999999, cumulativeReturnPct: 88 },
      ],
    });
    const normalized = normalizeDeterministicBacktestResult(run);

    render(<DeterministicAuditTable run={run} rows={normalized.rows} />);

    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'backtest.resultPage.statusCard.exportCsv') }));

    const blob = createObjectUrlMock.mock.calls[0]?.[0] as Blob;
    const content = await blob.text();
    expect(content).toContain('"101"');
    expect(content).toContain('"stored-note"');
    expect(content).not.toContain('"888"');

    createObjectUrlMock.mockRestore();
    revokeObjectUrlMock.mockRestore();
    clickMock.mockRestore();
  });

  it('renders the new workspace copy in English on localized routes', () => {
    window.history.replaceState(window.history.state, '', '/en/backtest/results/101');
    render(
      <MemoryRouter initialEntries={['/en/backtest/results/101']}>
        <UiLanguageProvider>
          <DeterministicBacktestResultView run={makeViewerRun()} />
        </UiLanguageProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText('Research result visuals')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Parameters/ })).toBeInTheDocument();
    expect(screen.getByText('Equity / Drawdown / Daily P&L')).toBeInTheDocument();
  });

  it('renders a fail-closed empty state when the completed run has no displayable result rows', () => {
    render(<DeterministicBacktestResultView run={makeViewerRun({
      auditRows: [],
      equityCurve: [],
      dailyReturnSeries: [],
      exposureCurve: [],
      benchmarkCurve: [],
      buyAndHoldCurve: [],
      totalReturnPct: null,
      annualizedReturnPct: null,
      winRatePct: null,
      maxDrawdownPct: null,
      sharpeRatio: null,
      finalEquity: null,
      noResultMessage: translate('zh', 'backtest.resultPage.noEntrySignal'),
    })} />);

    expect(screen.getByTestId('deterministic-result-empty-state')).toBeInTheDocument();
    expect(screen.getByText('暂无可视化结果')).toBeInTheDocument();
    expect(screen.getByText('回测窗口内没有触发任何入场信号。')).toBeInTheDocument();
    expect(screen.queryByTestId('deterministic-backtest-chart-workspace')).not.toBeInTheDocument();
  });
});
