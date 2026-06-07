// @vitest-environment jsdom
import React from 'react';
import '@testing-library/jest-dom/vitest';
import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { RuleBacktestRunResponse } from '../../../types/backtest';
import BacktestResultReport from '../BacktestResultReport';

function makeRun(): RuleBacktestRunResponse {
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
    },
    strategyHash: 'hash',
    timeframe: 'daily',
    startDate: '2026-03-01',
    endDate: '2026-03-05',
    periodStart: '2026-03-01',
    periodEnd: '2026-03-05',
    lookbackBars: 20,
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
    dataQuality: {
      symbol: 'ORCL',
      benchmarkSymbol: 'QQQ',
      barCount: 5,
      expectedBarCount: 5,
      isComplete: true,
      warnings: [],
    },
    executionAssumptions: {
      feeBps: 2,
      slippageBps: 1,
    },
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
  };
}

describe('BacktestResultReport compare evidence', () => {
  it('uses caller-supplied compare parameter stability evidence as diagnostic research evidence', () => {
    render(<BacktestResultReport
      run={makeRun()}
      mode="professional"
      parameterStabilityEvidence={{
        contractKind: 'backtest_parameter_stability_diagnostic_evidence',
        state: 'available',
        diagnosticOnly: true,
        decisionGrade: false,
        source: 'stored_compare_summary',
      }}
    />);

    const checklist = screen.getByTestId('backtest-report-research-quality-review');
    expect(within(checklist).getByTestId('backtest-research-review-row-parameter')).toHaveTextContent('诊断可查');
    expect(within(checklist).getByTestId('backtest-research-review-row-parameter')).toHaveTextContent('参数稳定性证据可用');
    expect(checklist).not.toHaveTextContent(/交易建议|实盘|安全交易|safe to trade|deploy live/i);
  });
});
