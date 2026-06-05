// @vitest-environment jsdom
import React from 'react';
import '@testing-library/jest-dom/vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import type {
  RuleBacktestCompareResponse,
  RuleBacktestRunResponse,
} from '../../types/backtest';
import DeterministicBacktestResultPage from '../DeterministicBacktestResultPage';

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

vi.mock('../../components/backtest/BacktestChartWorkspace', () => ({
  default: () => <div data-testid="mock-backtest-chart-workspace" />,
}));

vi.mock('../../components/backtest/BacktestResultReport', () => ({
  default: ({ parameterStabilityEvidence }: { parameterStabilityEvidence?: Record<string, unknown> | null }) => (
    <section
      data-testid="mock-backtest-result-report"
      data-parameter-state={String(parameterStabilityEvidence?.state || 'missing')}
    />
  ),
}));

function makeRun(id: number, overrides: Partial<RuleBacktestRunResponse> = {}): RuleBacktestRunResponse {
  return {
    id,
    code: 'ORCL',
    strategyText: 'MA cross',
    parsedStrategy: {
      version: 'v1',
      timeframe: 'daily',
      sourceText: 'MA cross',
      normalizedText: 'SMA5 上穿 SMA20 买入。',
      entry: { type: 'group', op: 'and', rules: [] },
      exit: { type: 'group', op: 'or', rules: [] },
      confidence: 0.96,
      needsConfirmation: false,
      ambiguities: [],
      summary: { strategy: '均线交叉策略' },
      maxLookback: 20,
      strategyKind: 'moving_average_crossover',
      executable: true,
      normalizationState: 'ready',
      assumptions: [],
      assumptionGroups: [],
      setup: {},
      strategySpec: {},
    },
    strategyHash: `hash-${id}`,
    timeframe: 'daily',
    startDate: '2026-03-01',
    endDate: '2026-03-05',
    periodStart: '2026-03-01',
    periodEnd: '2026-03-05',
    lookbackBars: 20,
    initialCapital: 100000,
    feeBps: 2,
    slippageBps: 1,
    parsedConfidence: 0.96,
    needsConfirmation: false,
    warnings: [],
    runAt: '2026-05-03T08:00:00Z',
    completedAt: '2026-05-03T08:03:00Z',
    status: 'completed',
    statusMessage: 'completed',
    statusHistory: [{ status: 'completed', at: '2026-05-03T08:03:00Z' }],
    noResultReason: null,
    noResultMessage: null,
    tradeCount: 1,
    winCount: 1,
    lossCount: 0,
    totalReturnPct: 4,
    annualizedReturnPct: 12,
    benchmarkMode: 'auto',
    benchmarkCode: null,
    benchmarkReturnPct: 2,
    excessReturnVsBenchmarkPct: 2,
    buyAndHoldReturnPct: 1,
    excessReturnVsBuyAndHoldPct: 3,
    winRatePct: 100,
    avgTradeReturnPct: 4,
    maxDrawdownPct: -1,
    avgHoldingDays: 2,
    avgHoldingBars: 2,
    avgHoldingCalendarDays: 2,
    finalEquity: 104000,
    sharpeRatio: 1.1,
    summary: {},
    executionAssumptions: {},
    benchmarkCurve: [],
    benchmarkSummary: {
      label: 'QQQ',
      requestedMode: 'auto',
      resolvedMode: 'etf_qqq',
      method: 'benchmark_security',
      returnPct: 2,
    },
    buyAndHoldCurve: [],
    buyAndHoldSummary: {
      label: 'Buy and hold',
      requestedMode: 'same_symbol_buy_and_hold',
      resolvedMode: 'same_symbol_buy_and_hold',
      method: 'same_symbol_buy_and_hold',
      returnPct: 1,
    },
    auditRows: [
      {
        date: '2026-03-01',
        symbolClose: 100,
        benchmarkClose: 98,
        dailyReturnPct: 0,
        cumulativeStrategyReturnPct: 0,
        cumulativeBenchmarkReturnPct: 0,
      },
    ],
    dailyReturnSeries: [],
    exposureCurve: [],
    equityCurve: [{ date: '2026-03-01', equity: 100000, cumulativeReturnPct: 0 }],
    trades: [],
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/backtest/results/99']}>
      <UiLanguageProvider>
        <Routes>
          <Route path="/backtest/results/:runId" element={<DeterministicBacktestResultPage />} />
          <Route path="/backtest/compare" element={<div data-testid="compare-route" />} />
        </Routes>
      </UiLanguageProvider>
    </MemoryRouter>,
  );
}

describe('DeterministicBacktestResultPage compare evidence', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.resetAllMocks();
    const currentRun = makeRun(99);
    const compareRun = makeRun(88, { totalReturnPct: 6, benchmarkReturnPct: 3 });
    getRuleBacktestRun.mockImplementation((id: number) => Promise.resolve(id === 88 ? compareRun : currentRun));
    getRuleBacktestRuns.mockResolvedValue({
      total: 2,
      page: 1,
      limit: 10,
      items: [currentRun, compareRun],
    });
    getRuleBacktestRunStatus.mockResolvedValue({
      id: 99,
      code: 'ORCL',
      status: 'completed',
      statusMessage: 'completed',
      statusHistory: [{ status: 'completed', at: '2026-05-03T08:03:00Z' }],
      tradeCount: 1,
      parsedConfidence: 0.96,
      needsConfirmation: false,
    });
  });

  it('does not call compare without selection, then requests selected runs and passes diagnostic evidence', async () => {
    const compareResponse: RuleBacktestCompareResponse = {
      comparisonSource: 'stored_compare_summary',
      readMode: 'stored_first',
      requestedRunIds: [99, 88],
      resolvedRunIds: [99, 88],
      comparableRunIds: [99, 88],
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
    };
    compareRuleBacktestRuns.mockResolvedValue(compareResponse);

    renderPage();
    expect(await screen.findByTestId('mock-backtest-result-report')).toHaveAttribute('data-parameter-state', 'missing');
    expect(compareRuleBacktestRuns).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('tab', { name: '历史结果' }));
    await act(async () => {
      await vi.dynamicImportSettled();
    });
    fireEvent.click(await screen.findByRole('checkbox'));

    await waitFor(() => {
      expect(compareRuleBacktestRuns).toHaveBeenCalledWith({ runIds: [99, 88] });
    });
    await waitFor(() => {
      expect(screen.getByTestId('mock-backtest-result-report')).toHaveAttribute('data-parameter-state', 'available');
    });
  });

  it('keeps parameter evidence missing when compare fails', async () => {
    compareRuleBacktestRuns.mockRejectedValue(new Error('compare unavailable'));

    renderPage();
    expect(await screen.findByTestId('mock-backtest-result-report')).toHaveAttribute('data-parameter-state', 'missing');

    fireEvent.click(screen.getByRole('tab', { name: '历史结果' }));
    await act(async () => {
      await vi.dynamicImportSettled();
    });
    fireEvent.click(await screen.findByRole('checkbox'));

    await waitFor(() => {
      expect(compareRuleBacktestRuns).toHaveBeenCalledWith({ runIds: [99, 88] });
    });
    expect(await screen.findByTestId('mock-backtest-result-report')).toHaveAttribute('data-parameter-state', 'missing');
  });
});
