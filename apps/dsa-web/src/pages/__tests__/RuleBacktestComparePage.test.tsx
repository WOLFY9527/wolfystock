import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import RuleBacktestComparePage from '../RuleBacktestComparePage';

const { compareRuleBacktestRuns } = vi.hoisted(() => ({
  compareRuleBacktestRuns: vi.fn(),
}));

const { writeTextMock } = vi.hoisted(() => ({
  writeTextMock: vi.fn(),
}));

vi.mock('../../api/backtest', () => ({
  backtestApi: {
    compareRuleBacktestRuns,
  },
}));

function renderComparePage(initialEntry = '/backtest/compare?runIds=101,202') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/backtest/compare" element={<RuleBacktestComparePage />} />
        <Route path="/backtest/results/:runId" element={<div data-testid="rule-backtest-result-route">result route</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('RuleBacktestComparePage', () => {
  let originalClipboard: Navigator['clipboard'] | undefined;

  beforeEach(() => {
    vi.clearAllMocks();
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
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: originalClipboard,
    });
  });

  it('loads the compare API and renders the foundation workbench sections', async () => {
    compareRuleBacktestRuns.mockResolvedValue({
      comparisonSource: 'stored_rule_backtest_runs',
      readMode: 'stored_first',
      requestedRunIds: [101, 202],
      resolvedRunIds: [101, 202],
      comparableRunIds: [101, 202],
      missingRunIds: [],
      unavailableRuns: [],
      fieldGroups: ['market_code_comparison', 'period_comparison', 'comparison_summary'],
      marketCodeComparison: {
        baselineRunId: 101,
        selectionRule: 'first_comparable_run_by_request_order',
        relationship: 'same_code',
        state: 'direct',
        directlyComparable: true,
        diagnostics: ['same_normalized_code'],
      },
      periodComparison: {
        baselineRunId: 101,
        selectionRule: 'first_comparable_run_by_request_order',
        relationship: 'overlapping',
        state: 'comparable',
        meaningfullyComparable: true,
        diagnostics: ['overlapping_periods'],
      },
      comparisonSummary: {
        baseline: {
          runId: 101,
          selectionRule: 'first_comparable_run_by_request_order',
          code: 'ORCL',
          timeframe: 'daily',
          startDate: '2025-01-01',
          endDate: '2025-12-31',
          strategyFamily: 'moving_average_crossover',
          strategyType: 'moving_average_crossover',
        },
        context: {
          codeValues: ['ORCL'],
          timeframeValues: ['daily'],
          strategyFamilyValues: ['moving_average_crossover'],
          strategyTypeValues: ['moving_average_crossover'],
          dateRanges: [
            { runId: 101, startDate: '2025-01-01', endDate: '2025-12-31' },
            { runId: 202, startDate: '2025-03-01', endDate: '2025-12-31' },
          ],
          allSameCode: true,
          allSameTimeframe: true,
          allSameDateRange: false,
        },
        metricDeltas: {
          totalReturnPct: {
            label: 'total_return_pct',
            state: 'comparable',
            baselineRunId: 101,
            baselineValue: 12,
            availableRunIds: [101, 202],
            unavailableRunIds: [],
            deltas: [
              { runId: 101, value: 12, deltaVsBaseline: 0 },
              { runId: 202, value: 18, deltaVsBaseline: 6 },
            ],
          },
          annualizedReturnPct: {
            label: 'annualized_return_pct',
            state: 'partial',
            baselineRunId: 101,
            baselineValue: 10,
            availableRunIds: [101],
            unavailableRunIds: [202],
            deltas: [{ runId: 101, value: 10, deltaVsBaseline: 0 }],
          },
        },
      },
      robustnessSummary: {
        baselineRunId: 101,
        selectionRule: 'first_comparable_run_by_request_order',
        overallState: 'partially_comparable',
        directlyComparable: false,
        alignedDimensions: ['market_code'],
        partialDimensions: ['periods', 'metrics_baseline'],
        divergentDimensions: [],
        unavailableDimensions: [],
        dimensions: {
          marketCode: {
            state: 'aligned',
            sourceState: 'direct',
            relationship: 'same_code',
            directlyComparable: true,
            diagnostics: ['same_normalized_code'],
          },
          periods: {
            state: 'partial',
            sourceState: 'limited',
            relationship: 'partial',
            meaningfullyComparable: false,
            diagnostics: ['overlapping_periods'],
          },
        },
        diagnostics: ['partial_metric_deltas', 'overlapping_periods'],
      },
      comparisonProfile: {
        baselineRunId: 101,
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
        baselineRunId: 101,
        selectionRule: 'first_comparable_run_by_request_order',
        primaryProfile: 'same_code_different_periods',
        overallContextState: 'partially_comparable',
        highlights: {
          totalReturnPct: {
            metric: 'total_return_pct',
            preference: 'higher_is_better',
            state: 'limited_context_winner',
            winnerRunIds: [202],
            winnerValue: 18,
            availableRunIds: [101, 202],
            candidateCount: 2,
            diagnostics: ['partially_comparable_context'],
          },
          annualizedReturnPct: {
            metric: 'annualized_return_pct',
            preference: 'higher_is_better',
            state: 'unavailable',
            winnerRunIds: [],
            winnerValue: null,
            availableRunIds: [101],
            candidateCount: 1,
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
        missingParameterKeys: ['strategy_spec.signal.slow_type'],
        sharedParameters: {
          'strategy_spec.execution.signal_timing': 'bar_close',
        },
        differingParameters: {},
        missingParameters: {},
      },
      items: [
        {
          metadata: {
            id: 101,
            code: 'ORCL',
            status: 'completed',
            runAt: '2026-04-01T08:00:00Z',
            completedAt: '2026-04-01T08:02:00Z',
            timeframe: 'daily',
            startDate: '2025-01-01',
            endDate: '2025-12-31',
            periodStart: '2025-01-01',
            periodEnd: '2025-12-31',
            lookbackBars: 252,
            initialCapital: 100000,
            feeBps: 0,
            slippageBps: 0,
          },
          metrics: {
            tradeCount: 12,
            winCount: 8,
            lossCount: 4,
            totalReturnPct: 12,
            annualizedReturnPct: 10,
            benchmarkReturnPct: 8,
            excessReturnVsBenchmarkPct: 4,
            buyAndHoldReturnPct: 7,
            excessReturnVsBuyAndHoldPct: 5,
            winRatePct: 66.7,
            avgTradeReturnPct: 1.5,
            maxDrawdownPct: 8.5,
            avgHoldingDays: 6,
            avgHoldingBars: 6,
            avgHoldingCalendarDays: 8,
            finalEquity: 112000,
          },
          parsedStrategy: {
            strategySpec: {
              strategyFamily: 'moving_average_crossover',
              strategyType: 'moving_average_crossover',
            },
          },
          benchmark: {
            mode: 'auto',
            code: 'QQQ',
            returnPct: 8,
          },
        },
        {
          metadata: {
            id: 202,
            code: 'ORCL',
            status: 'completed',
            runAt: '2026-04-02T08:00:00Z',
            completedAt: '2026-04-02T08:03:00Z',
            timeframe: 'daily',
            startDate: '2025-03-01',
            endDate: '2025-12-31',
            periodStart: '2025-03-01',
            periodEnd: '2025-12-31',
            lookbackBars: 252,
            initialCapital: 100000,
            feeBps: 0,
            slippageBps: 0,
          },
          metrics: {
            tradeCount: 9,
            winCount: 6,
            lossCount: 3,
            totalReturnPct: 18,
            annualizedReturnPct: null,
            benchmarkReturnPct: 7,
            excessReturnVsBenchmarkPct: 11,
            buyAndHoldReturnPct: 8,
            excessReturnVsBuyAndHoldPct: 10,
            winRatePct: 66.7,
            avgTradeReturnPct: 2,
            maxDrawdownPct: 9.2,
            avgHoldingDays: 5,
            avgHoldingBars: 5,
            avgHoldingCalendarDays: 7,
            finalEquity: 118000,
          },
          parsedStrategy: {
            strategySpec: {
              strategyFamily: 'moving_average_crossover',
              strategyType: 'moving_average_crossover',
            },
          },
          benchmark: {
            mode: 'auto',
            code: 'QQQ',
            returnPct: 7,
          },
        },
      ],
    });

    renderComparePage();

    await waitFor(() => {
      expect(compareRuleBacktestRuns).toHaveBeenCalledWith({ runIds: [101, 202] });
    });

    expect(await screen.findByRole('heading', { name: '规则回测比较工作台' })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: '比较区块导航' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '比较摘要' })).toHaveAttribute('href', '#compare-summary');
    expect(screen.getByRole('link', { name: '指标条带' })).toHaveAttribute('href', '#compare-chart-strip');
    expect(screen.getByRole('link', { name: '比较亮点' })).toHaveAttribute('href', '#compare-highlights');
    expect(screen.getByRole('link', { name: '指标矩阵' })).toHaveAttribute('href', '#compare-metric-matrix');
    expect(screen.getByRole('link', { name: '稳健性画像' })).toHaveAttribute('href', '#compare-robustness');
    expect(screen.getByRole('link', { name: '市场与区间' })).toHaveAttribute('href', '#compare-market-period');
    expect(screen.getByRole('link', { name: '参数与指标' })).toHaveAttribute('href', '#compare-parameter-metrics');
    expect(screen.getByRole('link', { name: '参与运行' })).toHaveAttribute('href', '#compare-items');
    const parameterSummary = screen.getByText('展开 / 参数与指标');
    const parameterDisclosure = parameterSummary.closest('details');
    expect(parameterDisclosure).not.toBeNull();
    expect(parameterDisclosure).toHaveAttribute('open');
    expect(screen.getAllByText('同标的不同区间').length).toBeGreaterThan(0);
    expect(screen.getAllByText('部分可比').length).toBeGreaterThan(0);
    expect(screen.getAllByText('有限上下文领先').length).toBeGreaterThan(0);
    expect(screen.getByText('同类可比')).toBeInTheDocument();
    expect(screen.getAllByText('指标不可用').length).toBeGreaterThan(0);
    expect(screen.getByTestId('compare-metric-matrix')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /#101 基准/ })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /#202 候选/ })).toBeInTheDocument();
    expect(screen.getByText('差异 +6.00%')).toBeInTheDocument();
    expect(screen.getAllByText('不可用').length).toBeGreaterThan(0);
    expect(screen.getByTestId('compare-metric-summary-totalReturnPct')).toHaveAttribute('data-tone', 'limited');
    expect(screen.getByTestId('compare-metric-state-totalReturnPct-202')).toHaveAttribute('data-tone', 'best');
    expect(screen.getByTestId('compare-metric-delta-totalReturnPct-202')).toHaveAttribute('data-tone', 'positive');
    expect(screen.getByTestId('compare-metric-state-annualizedReturnPct-202')).toHaveAttribute('data-tone', 'unavailable');
    expect(screen.getByTestId('compare-chart-strip')).toBeInTheDocument();
    expect(screen.getByTestId('compare-chart-strip-totalReturnPct-101')).toHaveAttribute('data-role', 'baseline');
    expect(screen.getByTestId('compare-chart-strip-totalReturnPct-202')).toHaveAttribute('data-role', 'candidate');
    expect(screen.getByTestId('compare-chart-strip-annualizedReturnPct-202')).toHaveAttribute('data-state', 'unavailable');

    fireEvent.click(parameterSummary.closest('summary') ?? parameterSummary);
    expect(parameterDisclosure).not.toHaveAttribute('open');

    fireEvent.click(parameterSummary.closest('summary') ?? parameterSummary);
    expect(parameterDisclosure).toHaveAttribute('open');
  });

  it('shows an explicit empty state when fewer than two run ids are provided', async () => {
    renderComparePage('/backtest/compare?runIds=101');

    expect(await screen.findByText('至少需要 2 条已完成运行才能打开比较工作台。')).toBeInTheDocument();
    expect(compareRuleBacktestRuns).not.toHaveBeenCalled();
  });

  it('opens a single result page from the compare items table', async () => {
    compareRuleBacktestRuns.mockResolvedValue({
      comparisonSource: 'stored_rule_backtest_runs',
      readMode: 'stored_first',
      requestedRunIds: [101, 202],
      resolvedRunIds: [101, 202],
      comparableRunIds: [101, 202],
      missingRunIds: [],
      unavailableRuns: [],
      fieldGroups: ['market_code_comparison', 'period_comparison', 'comparison_summary'],
      marketCodeComparison: {
        baselineRunId: 101,
        selectionRule: 'first_comparable_run_by_request_order',
        relationship: 'same_code',
        state: 'direct',
        directlyComparable: true,
        diagnostics: ['same_normalized_code'],
      },
      periodComparison: {
        baselineRunId: 101,
        selectionRule: 'first_comparable_run_by_request_order',
        relationship: 'overlapping',
        state: 'comparable',
        meaningfullyComparable: true,
        diagnostics: ['overlapping_periods'],
      },
      comparisonSummary: {
        baseline: {
          runId: 101,
          selectionRule: 'first_comparable_run_by_request_order',
          code: 'ORCL',
          timeframe: 'daily',
          startDate: '2025-01-01',
          endDate: '2025-12-31',
          strategyFamily: 'moving_average_crossover',
          strategyType: 'moving_average_crossover',
        },
        context: {
          codeValues: ['ORCL'],
          timeframeValues: ['daily'],
          strategyFamilyValues: ['moving_average_crossover'],
          strategyTypeValues: ['moving_average_crossover'],
          dateRanges: [
            { runId: 101, startDate: '2025-01-01', endDate: '2025-12-31' },
            { runId: 202, startDate: '2025-03-01', endDate: '2025-12-31' },
          ],
          allSameCode: true,
          allSameTimeframe: true,
          allSameDateRange: false,
        },
        metricDeltas: {
          totalReturnPct: {
            label: 'total_return_pct',
            state: 'comparable',
            baselineRunId: 101,
            baselineValue: 12,
            availableRunIds: [101, 202],
            unavailableRunIds: [],
            deltas: [
              { runId: 101, value: 12, deltaVsBaseline: 0 },
              { runId: 202, value: 18, deltaVsBaseline: 6 },
            ],
          },
        },
      },
      robustnessSummary: {
        baselineRunId: 101,
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
        baselineRunId: 101,
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
        baselineRunId: 101,
        selectionRule: 'first_comparable_run_by_request_order',
        primaryProfile: 'same_code_different_periods',
        overallContextState: 'partially_comparable',
        highlights: {},
        diagnostics: [],
      },
      parameterComparison: {
        state: 'same_family_comparable',
        strategyFamilyValues: ['moving_average_crossover'],
        strategyTypeValues: ['moving_average_crossover'],
        sharedParameterKeys: [],
        differingParameterKeys: [],
        missingParameterKeys: [],
        sharedParameters: {},
        differingParameters: {},
        missingParameters: {},
      },
      items: [
        {
          metadata: {
            id: 101,
            code: 'ORCL',
            status: 'completed',
            runAt: '2026-04-01T08:00:00Z',
            completedAt: '2026-04-01T08:02:00Z',
            timeframe: 'daily',
            startDate: '2025-01-01',
            endDate: '2025-12-31',
            periodStart: '2025-01-01',
            periodEnd: '2025-12-31',
            lookbackBars: 252,
            initialCapital: 100000,
            feeBps: 0,
            slippageBps: 0,
          },
          metrics: {
            tradeCount: 12,
            totalReturnPct: 12,
            excessReturnVsBenchmarkPct: 4,
            maxDrawdownPct: 8.5,
          },
          parsedStrategy: {
            strategySpec: {
              strategyFamily: 'moving_average_crossover',
              strategyType: 'moving_average_crossover',
            },
          },
          benchmark: {
            mode: 'auto',
            code: 'QQQ',
            returnPct: 8,
          },
        },
        {
          metadata: {
            id: 202,
            code: 'ORCL',
            status: 'completed',
            runAt: '2026-04-02T08:00:00Z',
            completedAt: '2026-04-02T08:03:00Z',
            timeframe: 'daily',
            startDate: '2025-03-01',
            endDate: '2025-12-31',
            periodStart: '2025-03-01',
            periodEnd: '2025-12-31',
            lookbackBars: 252,
            initialCapital: 100000,
            feeBps: 0,
            slippageBps: 0,
          },
          metrics: {
            tradeCount: 9,
            totalReturnPct: 18,
            excessReturnVsBenchmarkPct: 11,
            maxDrawdownPct: 9.2,
          },
          parsedStrategy: {
            strategySpec: {
              strategyFamily: 'moving_average_crossover',
              strategyType: 'moving_average_crossover',
            },
          },
          benchmark: {
            mode: 'auto',
            code: 'QQQ',
            returnPct: 7,
          },
        },
      ],
    });

    renderComparePage();

    expect(await screen.findByRole('heading', { name: '规则回测比较工作台' })).toBeInTheDocument();

    fireEvent.click(await screen.findByRole('button', { name: '打开结果页 202' }));

    expect(await screen.findByTestId('rule-backtest-result-route')).toBeInTheDocument();
  });

  it('copies shareable compare values from the summary area', async () => {
    compareRuleBacktestRuns.mockResolvedValue({
      comparisonSource: 'stored_rule_backtest_runs',
      readMode: 'stored_first',
      requestedRunIds: [101, 202],
      resolvedRunIds: [101, 202],
      comparableRunIds: [101, 202],
      missingRunIds: [],
      unavailableRuns: [],
      fieldGroups: ['market_code_comparison', 'period_comparison', 'comparison_summary'],
      marketCodeComparison: {
        baselineRunId: 101,
        selectionRule: 'first_comparable_run_by_request_order',
        relationship: 'same_code',
        state: 'direct',
        directlyComparable: true,
        diagnostics: ['same_normalized_code'],
      },
      periodComparison: {
        baselineRunId: 101,
        selectionRule: 'first_comparable_run_by_request_order',
        relationship: 'overlapping',
        state: 'comparable',
        meaningfullyComparable: true,
        diagnostics: ['overlapping_periods'],
      },
      comparisonSummary: {
        baseline: {
          runId: 101,
          selectionRule: 'first_comparable_run_by_request_order',
          code: 'ORCL',
          timeframe: 'daily',
          startDate: '2025-01-01',
          endDate: '2025-12-31',
          strategyFamily: 'moving_average_crossover',
          strategyType: 'moving_average_crossover',
        },
        context: {
          codeValues: ['ORCL'],
          timeframeValues: ['daily'],
          strategyFamilyValues: ['moving_average_crossover'],
          strategyTypeValues: ['moving_average_crossover'],
          dateRanges: [
            { runId: 101, startDate: '2025-01-01', endDate: '2025-12-31' },
            { runId: 202, startDate: '2025-03-01', endDate: '2025-12-31' },
          ],
          allSameCode: true,
          allSameTimeframe: true,
          allSameDateRange: false,
        },
        metricDeltas: {
          totalReturnPct: {
            label: 'total_return_pct',
            state: 'comparable',
            baselineRunId: 101,
            baselineValue: 12,
            availableRunIds: [101, 202],
            unavailableRunIds: [],
            deltas: [
              { runId: 101, value: 12, deltaVsBaseline: 0 },
              { runId: 202, value: 18, deltaVsBaseline: 6 },
            ],
          },
        },
      },
      robustnessSummary: {
        baselineRunId: 101,
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
        baselineRunId: 101,
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
        baselineRunId: 101,
        selectionRule: 'first_comparable_run_by_request_order',
        primaryProfile: 'same_code_different_periods',
        overallContextState: 'partially_comparable',
        highlights: {},
        diagnostics: [],
      },
      parameterComparison: {
        state: 'same_family_comparable',
        strategyFamilyValues: ['moving_average_crossover'],
        strategyTypeValues: ['moving_average_crossover'],
        sharedParameterKeys: [],
        differingParameterKeys: [],
        missingParameterKeys: [],
        sharedParameters: {},
        differingParameters: {},
        missingParameters: {},
      },
      items: [
        {
          metadata: {
            id: 101,
            code: 'ORCL',
            status: 'completed',
            runAt: '2026-04-01T08:00:00Z',
            completedAt: '2026-04-01T08:02:00Z',
            timeframe: 'daily',
            startDate: '2025-01-01',
            endDate: '2025-12-31',
            periodStart: '2025-01-01',
            periodEnd: '2025-12-31',
            lookbackBars: 252,
            initialCapital: 100000,
            feeBps: 0,
            slippageBps: 0,
          },
          metrics: {
            tradeCount: 12,
            totalReturnPct: 12,
            excessReturnVsBenchmarkPct: 4,
            maxDrawdownPct: 8.5,
          },
          parsedStrategy: {
            strategySpec: {
              strategyFamily: 'moving_average_crossover',
              strategyType: 'moving_average_crossover',
            },
          },
          benchmark: {
            mode: 'auto',
            code: 'QQQ',
            returnPct: 8,
          },
        },
        {
          metadata: {
            id: 202,
            code: 'ORCL',
            status: 'completed',
            runAt: '2026-04-02T08:00:00Z',
            completedAt: '2026-04-02T08:03:00Z',
            timeframe: 'daily',
            startDate: '2025-03-01',
            endDate: '2025-12-31',
            periodStart: '2025-03-01',
            periodEnd: '2025-12-31',
            lookbackBars: 252,
            initialCapital: 100000,
            feeBps: 0,
            slippageBps: 0,
          },
          metrics: {
            tradeCount: 9,
            totalReturnPct: 18,
            excessReturnVsBenchmarkPct: 11,
            maxDrawdownPct: 9.2,
          },
          parsedStrategy: {
            strategySpec: {
              strategyFamily: 'moving_average_crossover',
              strategyType: 'moving_average_crossover',
            },
          },
          benchmark: {
            mode: 'auto',
            code: 'QQQ',
            returnPct: 7,
          },
        },
      ],
    });

    renderComparePage();

    expect(await screen.findByRole('heading', { name: '规则回测比较工作台' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '复制链接' }));
    await waitFor(() => {
      expect(writeTextMock).toHaveBeenNthCalledWith(1, 'http://localhost:3000/backtest/compare?runIds=101%2C202');
    });
    expect(await screen.findByText('已复制当前比较链接')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '复制运行 ID' }));
    await waitFor(() => {
      expect(writeTextMock).toHaveBeenNthCalledWith(2, '101,202');
    });
    expect(await screen.findByText('已复制当前运行 ID')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '复制摘要' }));
    await waitFor(() => {
      expect(writeTextMock).toHaveBeenNthCalledWith(3, '比较运行 101,202 | 基准 #101 ORCL | 整体 部分可比 | 画像 同标的不同区间 | 可比 2/2');
    });
    expect(await screen.findByText('已复制比较摘要')).toBeInTheDocument();
  });

  it('lets users remove a candidate run from the current compare selection', async () => {
    compareRuleBacktestRuns.mockResolvedValue({
      comparisonSource: 'stored_rule_backtest_runs',
      readMode: 'stored_first',
      requestedRunIds: [101, 202],
      resolvedRunIds: [101, 202],
      comparableRunIds: [101, 202],
      missingRunIds: [],
      unavailableRuns: [],
      fieldGroups: ['market_code_comparison', 'period_comparison', 'comparison_summary'],
      marketCodeComparison: {
        baselineRunId: 101,
        selectionRule: 'first_comparable_run_by_request_order',
        relationship: 'same_code',
        state: 'direct',
        directlyComparable: true,
        diagnostics: ['same_normalized_code'],
      },
      periodComparison: {
        baselineRunId: 101,
        selectionRule: 'first_comparable_run_by_request_order',
        relationship: 'overlapping',
        state: 'comparable',
        meaningfullyComparable: true,
        diagnostics: ['overlapping_periods'],
      },
      comparisonSummary: {
        baseline: {
          runId: 101,
          selectionRule: 'first_comparable_run_by_request_order',
          code: 'ORCL',
          timeframe: 'daily',
          startDate: '2025-01-01',
          endDate: '2025-12-31',
          strategyFamily: 'moving_average_crossover',
          strategyType: 'moving_average_crossover',
        },
        context: {
          codeValues: ['ORCL'],
          timeframeValues: ['daily'],
          strategyFamilyValues: ['moving_average_crossover'],
          strategyTypeValues: ['moving_average_crossover'],
          dateRanges: [
            { runId: 101, startDate: '2025-01-01', endDate: '2025-12-31' },
            { runId: 202, startDate: '2025-03-01', endDate: '2025-12-31' },
          ],
          allSameCode: true,
          allSameTimeframe: true,
          allSameDateRange: false,
        },
        metricDeltas: {
          totalReturnPct: {
            label: 'total_return_pct',
            state: 'comparable',
            baselineRunId: 101,
            baselineValue: 12,
            availableRunIds: [101, 202],
            unavailableRunIds: [],
            deltas: [
              { runId: 101, value: 12, deltaVsBaseline: 0 },
              { runId: 202, value: 18, deltaVsBaseline: 6 },
            ],
          },
        },
      },
      robustnessSummary: {
        baselineRunId: 101,
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
        baselineRunId: 101,
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
        baselineRunId: 101,
        selectionRule: 'first_comparable_run_by_request_order',
        primaryProfile: 'same_code_different_periods',
        overallContextState: 'partially_comparable',
        highlights: {},
        diagnostics: [],
      },
      parameterComparison: {
        state: 'same_family_comparable',
        strategyFamilyValues: ['moving_average_crossover'],
        strategyTypeValues: ['moving_average_crossover'],
        sharedParameterKeys: [],
        differingParameterKeys: [],
        missingParameterKeys: [],
        sharedParameters: {},
        differingParameters: {},
        missingParameters: {},
      },
      items: [
        {
          metadata: {
            id: 101,
            code: 'ORCL',
            status: 'completed',
            runAt: '2026-04-01T08:00:00Z',
            completedAt: '2026-04-01T08:02:00Z',
            timeframe: 'daily',
            startDate: '2025-01-01',
            endDate: '2025-12-31',
            periodStart: '2025-01-01',
            periodEnd: '2025-12-31',
            lookbackBars: 252,
            initialCapital: 100000,
            feeBps: 0,
            slippageBps: 0,
          },
          metrics: {
            tradeCount: 12,
            totalReturnPct: 12,
            excessReturnVsBenchmarkPct: 4,
            maxDrawdownPct: 8.5,
          },
          parsedStrategy: {
            strategySpec: {
              strategyFamily: 'moving_average_crossover',
              strategyType: 'moving_average_crossover',
            },
          },
          benchmark: {
            mode: 'auto',
            code: 'QQQ',
            returnPct: 8,
          },
        },
        {
          metadata: {
            id: 202,
            code: 'ORCL',
            status: 'completed',
            runAt: '2026-04-02T08:00:00Z',
            completedAt: '2026-04-02T08:03:00Z',
            timeframe: 'daily',
            startDate: '2025-03-01',
            endDate: '2025-12-31',
            periodStart: '2025-03-01',
            periodEnd: '2025-12-31',
            lookbackBars: 252,
            initialCapital: 100000,
            feeBps: 0,
            slippageBps: 0,
          },
          metrics: {
            tradeCount: 9,
            totalReturnPct: 18,
            excessReturnVsBenchmarkPct: 11,
            maxDrawdownPct: 9.2,
          },
          parsedStrategy: {
            strategySpec: {
              strategyFamily: 'moving_average_crossover',
              strategyType: 'moving_average_crossover',
            },
          },
          benchmark: {
            mode: 'auto',
            code: 'QQQ',
            returnPct: 7,
          },
        },
      ],
    });

    renderComparePage();

    expect(await screen.findByRole('heading', { name: '规则回测比较工作台' })).toBeInTheDocument();

    fireEvent.click(await screen.findByRole('button', { name: '移除运行 202' }));

    expect(await screen.findByText('至少需要 2 条已完成运行才能打开比较工作台。')).toBeInTheDocument();
    expect(compareRuleBacktestRuns).toHaveBeenCalledTimes(1);
  });

  it('switches the baseline by reordering runIds and keeps the rendered order aligned', async () => {
    const runFixtures = {
      101: {
        metadata: {
          id: 101,
          code: 'ORCL',
          status: 'completed',
          runAt: '2026-04-01T08:00:00Z',
          completedAt: '2026-04-01T08:02:00Z',
          timeframe: 'daily',
          startDate: '2025-01-01',
          endDate: '2025-12-31',
          periodStart: '2025-01-01',
          periodEnd: '2025-12-31',
          lookbackBars: 252,
          initialCapital: 100000,
          feeBps: 0,
          slippageBps: 0,
        },
        metrics: {
          tradeCount: 12,
          totalReturnPct: 12,
          excessReturnVsBenchmarkPct: 4,
          maxDrawdownPct: 8.5,
        },
        parsedStrategy: {
          strategySpec: {
            strategyFamily: 'moving_average_crossover',
            strategyType: 'moving_average_crossover',
          },
        },
        benchmark: {
          mode: 'auto',
          code: 'QQQ',
          returnPct: 8,
        },
      },
      202: {
        metadata: {
          id: 202,
          code: 'ORCL',
          status: 'completed',
          runAt: '2026-04-02T08:00:00Z',
          completedAt: '2026-04-02T08:03:00Z',
          timeframe: 'daily',
          startDate: '2025-03-01',
          endDate: '2025-12-31',
          periodStart: '2025-03-01',
          periodEnd: '2025-12-31',
          lookbackBars: 252,
          initialCapital: 100000,
          feeBps: 0,
          slippageBps: 0,
        },
        metrics: {
          tradeCount: 9,
          totalReturnPct: 18,
          excessReturnVsBenchmarkPct: 11,
          maxDrawdownPct: 9.2,
        },
        parsedStrategy: {
          strategySpec: {
            strategyFamily: 'moving_average_crossover',
            strategyType: 'moving_average_crossover',
          },
        },
        benchmark: {
          mode: 'auto',
          code: 'QQQ',
          returnPct: 7,
        },
      },
    } as const;

    compareRuleBacktestRuns.mockImplementation(async ({ runIds }: { runIds: number[] }) => {
      const baselineRunId = runIds[0];
      const candidateRunId = runIds.find((id) => id !== baselineRunId) || runIds[1];
      const baselineValue = runFixtures[baselineRunId as 101 | 202].metrics.totalReturnPct;

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
            code: 'ORCL',
            timeframe: 'daily',
            startDate: baselineRunId === 101 ? '2025-01-01' : '2025-03-01',
            endDate: '2025-12-31',
            strategyFamily: 'moving_average_crossover',
            strategyType: 'moving_average_crossover',
          },
          context: {
            codeValues: ['ORCL'],
            timeframeValues: ['daily'],
            strategyFamilyValues: ['moving_average_crossover'],
            strategyTypeValues: ['moving_average_crossover'],
            dateRanges: [
              { runId: 101, startDate: '2025-01-01', endDate: '2025-12-31' },
              { runId: 202, startDate: '2025-03-01', endDate: '2025-12-31' },
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
              baselineValue,
              availableRunIds: runIds,
              unavailableRunIds: [],
              deltas: [
                {
                  runId: baselineRunId,
                  value: runFixtures[baselineRunId as 101 | 202].metrics.totalReturnPct,
                  deltaVsBaseline: 0,
                },
                {
                  runId: candidateRunId,
                  value: runFixtures[candidateRunId as 101 | 202].metrics.totalReturnPct,
                  deltaVsBaseline: runFixtures[candidateRunId as 101 | 202].metrics.totalReturnPct - baselineValue,
                },
              ],
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
          highlights: {},
          diagnostics: [],
        },
        parameterComparison: {
          state: 'same_family_comparable',
          strategyFamilyValues: ['moving_average_crossover'],
          strategyTypeValues: ['moving_average_crossover'],
          sharedParameterKeys: [],
          differingParameterKeys: [],
          missingParameterKeys: [],
          sharedParameters: {},
          differingParameters: {},
          missingParameters: {},
        },
        items: [runFixtures[101], runFixtures[202]],
      };
    });

    renderComparePage();

    await waitFor(() => {
      expect(compareRuleBacktestRuns).toHaveBeenCalledWith({ runIds: [101, 202] });
    });
    expect(await screen.findByRole('columnheader', { name: /#101 基准/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '设为基准 202' }));

    await waitFor(() => {
      expect(compareRuleBacktestRuns).toHaveBeenLastCalledWith({ runIds: [202, 101] });
    });

    const leadingHeaders = screen.getAllByRole('columnheader').slice(0, 4).map((node) => node.textContent);
    expect(leadingHeaders).toEqual(['指标', '摘要', '#202 基准ORCL', '#101 候选ORCL']);
    expect(screen.getByRole('button', { name: '设为基准 101' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '设为基准 202' })).not.toBeInTheDocument();
  });
});
