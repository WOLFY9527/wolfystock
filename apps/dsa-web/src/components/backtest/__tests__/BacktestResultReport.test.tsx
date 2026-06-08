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
    sharpeRatio: 1.24,
    summary: { volatilityPct: 18.6 },
    dataQuality: {
      symbol: 'ORCL',
      benchmarkSymbol: 'QQQ',
      provider: 'Local US Parquet',
      source: 'local_us_parquet',
      frequency: '1d',
      requestedStart: '2026-03-01',
      requestedEnd: '2026-05-03',
      actualStart: '2026-03-01',
      actualEnd: '2026-05-03',
      barCount: 64,
      expectedBarCount: 64,
      missingBarCount: 0,
      missingDates: [],
      anomalyCount: 0,
      anomalies: [],
      adjustmentMode: 'unknown',
      dividendsHandled: 'unknown',
      splitsHandled: 'unknown',
      timezone: 'America/New_York',
      currency: 'USD',
      market: 'US',
      isComplete: false,
      qualityScore: 0.92,
      warnings: [
        { code: 'adjustment_status_unknown', severity: 'info', message: 'Adjustment status unknown.' },
      ],
    },
    executionAssumptions: {
      engine: 'deterministic',
      signalTiming: 'bar_close',
      fillTiming: 'next_bar_open',
      fillPrice: 'open',
      allowFractionalShares: true,
      lotSize: 1,
      volumeParticipationLimit: null,
      limitUpDownHandling: 'not_modeled',
      haltHandling: 'not_modeled',
      shortSelling: 'disabled',
      feeModel: {
        type: 'bps',
        commissionBps: 2,
        minCommission: null,
      },
      slippageModel: {
        type: 'bps',
        slippageBps: 1,
      },
      market: 'US',
      currency: 'USD',
      warnings: [
        { code: 'market_rules_not_modeled', severity: 'info', message: 'Limit and halt handling are not modeled.' },
      ],
      priceBasis: 'open',
      feeBps: 2,
      slippageBps: 1,
    },
    professionalReadiness: {
      overall_state: 'research_prototype',
      professional_quant_ready: false,
      adjusted_data_state: 'unknown_or_mixed',
      corporate_action_state: 'not_ready',
      trading_calendar_state: 'available_bars_only',
      cost_model_state: 'baseline_bps_only',
      reproducibility_state: 'partial_without_dataset_lineage',
    },
    adjustedDataState: 'unknown_or_mixed',
    corporateActionState: 'not_ready',
    tradingCalendarState: 'available_bars_only',
    costModelState: 'baseline_bps_only',
    reproducibilityState: 'partial_without_dataset_lineage',
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
      quantity: 900,
      grossPnl: 34200,
      netPnl: 34184,
      fees: 16,
      slippage: 6,
      returnPct: 36.89,
      holdingDays: 37,
      holdingBars: 27,
      holdingCalendarDays: 37,
      entryReason: 'signal_entry',
      exitReason: 'signal_exit',
      signalReason: 'moving_average_crossover',
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
    expect(simpleReport).toHaveTextContent('核心指标');
    expect(simpleReport).toHaveTextContent('策略解读');
    expect(simpleReport).toHaveTextContent('基准收益');
    expect(simpleReport).toHaveTextContent('交易摘要');
    expect(simpleReport).toHaveTextContent('数据质量');
    expect(simpleReport).not.toHaveTextContent('Key Metrics');
    expect(simpleReport).not.toHaveTextContent('Trade Summary');
    expect(simpleReport).not.toHaveTextContent('Execution Assumptions');
    expect(simpleReport).not.toHaveTextContent('Advanced Details');

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
      dataQuality: undefined,
      executionAssumptions: {},
    })} mode="simple" />);

    expect(screen.getByText('ORCL · 回测完成')).toBeInTheDocument();
    expect(screen.getAllByText('--').length).toBeGreaterThan(4);
    expect(screen.getAllByText('暂无可比基准数据；仅展示策略自身历史曲线。').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByTestId('backtest-diagnosis-return')).toHaveTextContent('--');
    expect(screen.getByTestId('backtest-diagnosis-risk')).toHaveTextContent('--');
    fireEvent.click(screen.getByRole('button', { name: /数据质量/ }));
    fireEvent.click(screen.getByRole('button', { name: /执行假设/ }));
    expect(screen.getByText('数据质量信息不足：当前结果未返回复权/分红/拆股元数据。')).toBeInTheDocument();
    expect(screen.getByText('执行假设信息不足：当前结果未返回成交时点/撮合规则。')).toBeInTheDocument();
  });

  it('renders enriched data quality metadata and compact warnings', () => {
    render(<BacktestResultReport run={makeRun()} mode="simple" />);

    fireEvent.click(screen.getByRole('button', { name: /数据质量/ }));
    const panel = screen.getByTestId('backtest-report-data-quality');
    expect(within(panel).getByText('本地美股 Parquet')).toBeInTheDocument();
    expect(within(panel).getByText('日线')).toBeInTheDocument();
    expect(within(panel).getByText('64 / 64')).toBeInTheDocument();
    expect(within(panel).getByText('未提供 / 未提供 / 未提供')).toBeInTheDocument();
    expect(within(panel).getByTestId('backtest-data-quality-warning-0')).toHaveTextContent('复权状态未知');
  });

  it('renders enriched execution assumptions and compact warnings', () => {
    render(<BacktestResultReport run={makeRun()} mode="simple" />);

    fireEvent.click(screen.getByRole('button', { name: /执行假设/ }));
    const panel = screen.getByTestId('backtest-report-execution-assumptions');
    expect(within(panel).getByText('确定性引擎')).toBeInTheDocument();
    expect(within(panel).getByText('收盘信号 -> 次日开盘')).toBeInTheDocument();
    expect(within(panel).getByText('2bp / 1bp')).toBeInTheDocument();
    expect(within(panel).getByText('允许碎股 / lot 1')).toBeInTheDocument();
    expect(within(panel).getByTestId('backtest-execution-warning-0')).toHaveTextContent('涨跌停/停牌未建模');
  });

  it('renders diagnosis summary and benchmark comparisons from existing metrics', () => {
    const { rerender } = render(<BacktestResultReport run={makeRun()} mode="professional" />);

    expect(screen.getByTestId('backtest-report-result-summary')).toHaveTextContent('诊断结论');
    expect(screen.getByTestId('backtest-report-result-summary')).toHaveTextContent('总收益');
    expect(screen.getByTestId('backtest-report-result-summary')).toHaveTextContent('最大回撤');
    expect(screen.getByTestId('backtest-report-result-summary')).toHaveTextContent('交易次数');
    expect(screen.getByTestId('backtest-report-result-summary')).toHaveTextContent('诊断材料');
    expect(screen.getByTestId('backtest-report-diagnosis')).toHaveTextContent('收益质量');
    expect(screen.getByTestId('backtest-diagnosis-return')).toHaveTextContent('高于参照基准');
    expect(screen.getByTestId('backtest-diagnosis-return')).toHaveTextContent('+24.60%');
    expect(screen.getByTestId('backtest-diagnosis-risk')).toHaveTextContent('回撤受控');
    expect(screen.getByTestId('backtest-report-benchmark')).toHaveTextContent('高于参照基准');
    expect(screen.getByTestId('backtest-report-benchmark')).toHaveTextContent('策略 +24.60% · 参照基准 +19.40% · 差值 +5.20%');
    expect(screen.getByTestId('backtest-report-benchmark')).toHaveTextContent('基准可比性仍需复核');

    rerender(<BacktestResultReport run={makeRun({
      id: 79,
      totalReturnPct: 3,
      benchmarkReturnPct: 9,
      excessReturnVsBenchmarkPct: -6,
    })} mode="professional" />);

    expect(screen.getByTestId('backtest-report-benchmark')).toHaveTextContent('低于参照基准');
    expect(screen.getByTestId('backtest-diagnosis-return')).toHaveTextContent('低于参照基准');

    rerender(<BacktestResultReport run={makeRun({
      id: 80,
      benchmarkReturnPct: null,
      excessReturnVsBenchmarkPct: null,
      benchmarkSummary: { resolvedMode: 'none', unavailableReason: 'missing benchmark' },
    })} mode="professional" />);

    expect(screen.getByTestId('backtest-report-benchmark')).toHaveTextContent('参照基准待补');
    expect(screen.getByTestId('backtest-report-benchmark')).toHaveTextContent('仅展示策略自身历史曲线');
  });

  it('renders compact observe-only readiness chips without unsupported research-grade claims', () => {
    render(<BacktestResultReport run={makeRun()} mode="professional" />);

    const chips = screen.getByTestId('backtest-readiness-chips');
    expect(chips).toHaveTextContent('仅供观察');
    expect(chips).toHaveTextContent('观察级原型');
    expect(chips).toHaveTextContent('专业级条件未满足');
    expect(chips).toHaveTextContent('数据口径需复核');
    expect(chips).toHaveTextContent('交易日历待确认');
    expect(chips).toHaveTextContent('复权/公司行动待确认');
    expect(screen.getByTestId('backtest-report-result-summary')).toHaveTextContent('总收益');
    expect(screen.getByTestId('backtest-report-result-summary')).toHaveTextContent('最大回撤');
    expect(chips).not.toHaveTextContent(/研究级回测|research[-_\s]?grade|research_prototype|unknown_or_mixed|available_bars_only|baseline_bps_only|partial_without_dataset_lineage|professional_quant_ready/i);
  });

  it('renders a research-quality review checklist from complete diagnostic evidence', () => {
    render(<BacktestResultReport run={makeRun({
      executionTrace: {
        source: 'stored_execution_trace',
        rows: [
          {
            date: '2026-03-04',
            eventType: 'entry',
            actionDisplay: '模拟入场',
            totalPortfolioValue: 100800,
          },
        ],
        fallback: { runFallback: false, traceRebuilt: false },
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
        },
        stressTests: {
          state: 'available',
          scenarioCount: 3,
        },
        parameterStability: {
          state: 'available',
          availabilityReason: 'caller_supplied_compare_summary_present',
          evidence: {
            contractKind: 'backtest_parameter_stability_diagnostic_evidence',
          },
        },
      },
    })} mode="professional" />);

    const checklist = screen.getByTestId('backtest-report-research-quality-review');
    expect(checklist).toHaveTextContent('观察复核清单');
    expect(checklist).toHaveTextContent('诊断门禁');
    expect(within(checklist).getByTestId('backtest-research-review-row-readiness')).toHaveTextContent('仅供观察');
    expect(within(checklist).getByTestId('backtest-research-review-row-data-quality')).toHaveTextContent('数据质量');
    expect(within(checklist).getByTestId('backtest-research-review-row-assumptions')).toHaveTextContent('简化成本 / 滑点 2bp / 1bp');
    expect(within(checklist).getByTestId('backtest-research-review-row-trace')).toHaveTextContent('1 行');
    expect(within(checklist).getByTestId('backtest-research-review-row-benchmark')).toHaveTextContent('QQQ');
    expect(within(checklist).getByTestId('backtest-research-review-row-oos')).toHaveTextContent('Walk-forward 4 窗口');
    expect(within(checklist).getByTestId('backtest-research-review-row-parameter')).toHaveTextContent('参数稳定性');
    expect(within(checklist).getByTestId('backtest-research-review-row-parameter')).toHaveTextContent('参数稳定性证据可用');
    expect(within(checklist).getByTestId('backtest-research-review-row-robustness')).toHaveTextContent('Monte Carlo 200 次');
    expect(within(checklist).getAllByText('诊断可查').length).toBeGreaterThanOrEqual(5);
    expect(checklist).toHaveTextContent('不构成选模证明');
    expect(checklist).toHaveTextContent('不代表样本外验证已完成');
    expect(checklist).not.toHaveTextContent(/研究级回测|research[-_\s]?grade|专业就绪|benchmark-ready|professional-ready/i);
  });

  it('fails closed when OOS, parameter, or benchmark evidence is missing', () => {
    render(<BacktestResultReport run={makeRun({
      benchmarkReturnPct: null,
      excessReturnVsBenchmarkPct: null,
      benchmarkSummary: { resolvedMode: 'none', unavailableReason: 'missing benchmark' },
      robustnessAnalysis: undefined,
      executionTrace: null,
    })} mode="simple" />);

    const checklist = screen.getByTestId('backtest-report-research-quality-review');
    expect(within(checklist).getByTestId('backtest-research-review-overall')).toHaveTextContent('需补充复核');
    expect(within(checklist).getByTestId('backtest-research-review-row-benchmark')).toHaveTextContent('缺失 / 待验证');
    expect(within(checklist).getByTestId('backtest-research-review-row-oos')).toHaveTextContent('缺失 / 待验证');
    expect(within(checklist).getByTestId('backtest-research-review-row-parameter')).toHaveTextContent('缺失 / 待验证');
    expect(within(checklist).getByTestId('backtest-research-review-row-trace')).toHaveTextContent('缺失 / 待验证');
    expect(within(checklist).queryByText('复核材料较完整')).not.toBeInTheDocument();
  });

  it('does not hide existing report sections or introduce live trading advice wording', () => {
    render(<BacktestResultReport run={makeRun({
      robustnessAnalysis: {
        state: 'available',
        walkForward: { state: 'available', windowCount: 2 },
      },
    })} mode="professional" />);

    const report = screen.getByTestId('backtest-result-report');
    expect(screen.getByTestId('backtest-report-research-quality-review')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-report-key-metrics')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-report-risk-diagnostics')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-report-evidence-details')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-report-advanced-details')).toBeInTheDocument();
    expect(report).toHaveTextContent('稳健性');
    expect(report).toHaveTextContent('不构成投资建议');
    expect(report).not.toHaveTextContent(/safe to trade|deploy live|live trading|best parameter|strategy recommendation|交易建议|建议买入|建议卖出|实盘|上线|最佳参数|安全交易/i);
  });

  it('keeps default result surfaces observe-only and exposes execution realism gaps without changing numbers', () => {
    render(<BacktestResultReport run={makeRun({
      executionTrace: null,
      robustnessAnalysis: undefined,
    })} mode="professional" />);

    const report = screen.getByTestId('backtest-result-report');
    expect(report).toHaveTextContent('仅供观察');
    expect(report).toHaveTextContent('仅用于观察复盘，不构成投资建议。');
    expect(report).toHaveTextContent('+24.60%');
    expect(report).toHaveTextContent('+19.40%');
    expect(report).not.toHaveTextContent(/研究级回测|research[-_\s]?grade|benchmark-ready|professional-ready|专业就绪|可用于历史表现评估|跑赢基准|明显跑赢|复核材料较完整|安全交易|上线|实盘/i);

    const assumptions = screen.getByTestId('backtest-research-review-row-assumptions');
    fireEvent.click(within(assumptions).getByText('复核依据'));
    expect(assumptions).toHaveTextContent('简化成本 / 滑点 2bp / 1bp');
    expect(assumptions).toHaveTextContent('未建模 partial/no-fill、停牌/涨跌停、成交量上限、税费、冲击，除非结果明确返回支持。');

    const oos = screen.getByTestId('backtest-research-review-row-oos');
    expect(oos).toHaveTextContent('未返回样本外证据');
    expect(oos).toHaveTextContent('缺失 / 待验证');
  });

  it('keeps the default consumer reliability view product-safe when support evidence is incomplete', () => {
    const run = makeRun();

    render(<BacktestResultReport run={{
      ...run,
      dataQuality: {
        ...run.dataQuality!,
        provider: 'sourceAuthorityAllowed',
        source: 'fallback_static',
        warnings: [
          { code: 'provider_timeout', severity: 'warning', message: 'trace JSON helper metadata missing' },
        ],
      },
      executionAssumptions: {
        ...run.executionAssumptions,
        warnings: [
          { code: 'engine_math_changed', severity: 'warning', message: 'authority internals require remediation' },
        ],
      },
      executionTrace: {
        source: 'stored_execution_trace',
        fallback: { note: 'provider_timeout' },
        rows: [],
      } as RuleBacktestRunResponse['executionTrace'],
    }} mode="simple" />);

    const report = screen.getByTestId('backtest-result-report');
    expect(report).toHaveTextContent('本次回测结果可查看，但部分复现材料不完整，仅供观察复盘。');
    expect(report).toHaveTextContent('回测数据质量有限，结果仅供观察复盘。');
    expect(report).toHaveTextContent('部分辅助证据暂不可用，仅保留历史曲线观察。');
    expect(screen.queryByTestId('backtest-data-quality-grid')).not.toBeInTheDocument();
    expect(screen.queryByTestId('backtest-execution-assumptions-grid')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /导出执行明细 JSON/ })).not.toBeInTheDocument();
    expect(report).not.toHaveTextContent(/sourceAuthorityAllowed|fallback_static|provider_timeout|trace JSON|helper metadata|authority internals|remediation|stored_execution_trace|执行明细 JSON/i);
  });

  it('renders compact drawdown and risk explanation labels without inventing unavailable values', () => {
    render(<BacktestResultReport run={makeRun({
      maxDrawdownPct: null,
      summary: {},
      auditRows: [],
      trades: [],
    })} mode="professional" />);

    const risk = screen.getByTestId('backtest-report-risk-diagnostics');
    expect(within(risk).getByText('回撤与压力解释')).toBeInTheDocument();
    expect(within(risk).getByText('最大回撤')).toBeInTheDocument();
    expect(within(risk).getByText('波动压力')).toBeInTheDocument();
    expect(within(risk).getByText('极端亏损日')).toBeInTheDocument();
    expect(within(risk).getAllByText('--').length).toBeGreaterThanOrEqual(3);
    expect(within(risk).getByText(/不代表真实成交或未来表现/)).toBeInTheDocument();
  });

  it('marks report diagnostic panels as narrow-safe stacked grids', () => {
    render(<BacktestResultReport run={makeRun()} mode="simple" />);

    fireEvent.click(screen.getByRole('button', { name: /数据质量/ }));
    fireEvent.click(screen.getByRole('button', { name: /执行假设/ }));
    expect(screen.getByTestId('backtest-data-quality-grid')).toHaveClass('grid-cols-1', 'sm:grid-cols-2');
    expect(screen.getByTestId('backtest-execution-assumptions-grid')).toHaveClass('grid-cols-1', 'sm:grid-cols-2');
  });

  it('keeps daily ledger collapsed and bounded until expanded', () => {
    render(<BacktestResultReport run={makeRun()} mode="professional" />);

    expect(screen.getByTestId('backtest-report-ledger-summary')).toHaveTextContent('64');
    expect(screen.queryByTestId('backtest-ledger-row-0')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /账本与导出/ }));
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

  it('renders trade attribution, event timeline, and risk diagnostics from existing payloads', () => {
    render(<BacktestResultReport run={makeRun({
      trades: [
        {
          code: 'ORCL',
          tradeIndex: 1,
          entryDate: '2026-03-04',
          exitDate: '2026-03-24',
          entryPrice: 103,
          exitPrice: 115,
          quantity: 900,
          grossPnl: 10800,
          netPnl: 10784,
          fees: 16,
          slippage: 6,
          returnPct: 11.5,
          holdingDays: 20,
          entryReason: 'signal_entry',
          exitReason: 'signal_exit',
          signalReason: 'moving_average_crossover',
          entrySignal: 'MA5 > MA20',
          exitSignal: 'MA5 < MA20',
          entryRule: {},
          exitRule: {},
          entryIndicators: {},
          exitIndicators: {},
        },
        {
          code: 'ORCL',
          tradeIndex: 2,
          entryDate: '2026-04-01',
          exitDate: '2026-04-08',
          entryPrice: 120,
          exitPrice: 114,
          quantity: 500,
          grossPnl: -3000,
          netPnl: -3012,
          fees: 12,
          slippage: 4,
          returnPct: -5.02,
          holdingDays: 7,
          entryReason: 'signal_entry',
          exitReason: 'stop_loss',
          signalReason: 'moving_average_crossover',
          entrySignal: 'MA5 > MA20',
          exitSignal: 'FIXED_STOP_LOSS_5%',
          entryRule: {},
          exitRule: {},
          entryIndicators: {},
          exitIndicators: {},
        },
      ],
    })} mode="professional" />);

    expect(screen.getByTestId('backtest-report-attribution')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-attribution-exit-reason')).toHaveTextContent('信号离场');
    expect(screen.getByTestId('backtest-attribution-exit-reason')).toHaveTextContent('止损离场');
    expect(screen.getByTestId('backtest-attribution-month')).toHaveTextContent('2026-03');
    expect(screen.getByTestId('backtest-attribution-year')).toHaveTextContent('2026');
    expect(screen.getByTestId('backtest-attribution-holding-bucket')).toHaveTextContent('0-7 天');

    const timeline = screen.getByTestId('backtest-report-event-timeline');
    expect(timeline).toHaveAttribute('data-visible-events', '4');
    expect(timeline).toHaveTextContent('模拟买入事件 / 模拟卖出事件');
    expect(timeline).toHaveTextContent('模拟事件仅用于回测复盘，不构成交易指令。');
    expect(within(timeline).getAllByText('模拟买入事件')).toHaveLength(2);
    expect(within(timeline).getAllByText('模拟卖出事件')).toHaveLength(2);
    expect(within(timeline).queryByText('买入')).not.toBeInTheDocument();
    expect(within(timeline).queryByText('卖出')).not.toBeInTheDocument();

    const risk = screen.getByTestId('backtest-report-risk-diagnostics');
    expect(within(risk).getByText('最差交易')).toBeInTheDocument();
    expect(within(risk).getByText('-5.02%')).toBeInTheDocument();
    expect(within(risk).getByText('最大回撤区间')).toBeInTheDocument();
  });

  it('keeps secondary backtest details user-facing and hides raw enum copy in the default report', () => {
    render(<BacktestResultReport run={makeRun()} mode="professional" />);

    const report = screen.getByTestId('backtest-result-report');
    const evidence = screen.getByTestId('backtest-report-evidence-details');
    expect(evidence).not.toHaveAttribute('open');
    expect(evidence).toHaveTextContent('复查材料');
    expect(evidence).toHaveTextContent('数据质量、执行假设和每日账本默认折叠');
    expect(report).toHaveTextContent('诊断结论');
    expect(report).not.toHaveTextContent('signal_exit');
    expect(report).not.toHaveTextContent('stop_loss');
    expect(report).not.toHaveTextContent('Full metrics');
    expect(screen.queryByText(/扩展指标在上方折叠区展示/)).not.toBeInTheDocument();

    expect(report).not.toHaveTextContent(/开发者|Developer|Trace/);
    fireEvent.click(screen.getByRole('button', { name: /账本与导出/ }));
    expect(screen.getByText(/扩展指标在上方折叠区展示/)).toBeInTheDocument();
  });

  it('puts launch research conclusions before secondary exports and evidence controls', () => {
    render(<BacktestResultReport run={makeRun()} mode="professional" />);

    const summary = screen.getByTestId('backtest-report-summary');
    const keyMetrics = screen.getByTestId('backtest-report-key-metrics');
    const chart = screen.getByTestId('backtest-report-chart');
    const tradeTable = screen.getByTestId('backtest-report-trade-table');
    const evidence = screen.getByTestId('backtest-report-evidence-details');
    const dataQuality = screen.getByTestId('backtest-report-data-quality');
    const assumptions = screen.getByTestId('backtest-report-execution-assumptions');
    const advanced = screen.getByTestId('backtest-report-advanced-details');

    expect(summary).toHaveTextContent('诊断结论');
    expect(summary).toHaveTextContent('总收益');
    expect(summary).toHaveTextContent('最大回撤');
    expect(summary).toHaveTextContent('交易次数');
    expect(summary).toHaveTextContent('诊断材料');
    expect(Boolean(summary.compareDocumentPosition(chart) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(chart.compareDocumentPosition(keyMetrics) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(chart.compareDocumentPosition(tradeTable) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(tradeTable.compareDocumentPosition(evidence) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(evidence.compareDocumentPosition(dataQuality) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(dataQuality.compareDocumentPosition(assumptions) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(assumptions.compareDocumentPosition(advanced) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(screen.queryByTestId('backtest-report-ledger-table')).not.toBeInTheDocument();
  });

  it('productizes the report as summary, chart/risk, then collapsed detail tabs', () => {
    render(<BacktestResultReport run={makeRun()} mode="professional" />);

    const report = screen.getByTestId('backtest-result-report');
    const summary = screen.getByTestId('backtest-report-summary');
    const primaryGrid = screen.getByTestId('backtest-report-primary-grid');
    const chart = screen.getByTestId('backtest-report-chart');
    const sideRail = screen.getByTestId('backtest-report-risk-side-rail');
    const detailTabs = screen.getByTestId('backtest-report-detail-tabs');
    const tradeTable = screen.getByTestId('backtest-report-trade-table');

    expect(summary).toHaveTextContent('总收益');
    expect(summary).toHaveTextContent('最大回撤');
    expect(summary).toHaveTextContent('胜率');
    expect(summary).toHaveTextContent('交易次数');
    expect(primaryGrid).toContainElement(chart);
    expect(primaryGrid).toContainElement(sideRail);
    expect(chart).toHaveClass('xl:col-span-8');
    expect(sideRail).toHaveClass('xl:col-span-4');
    expect(Boolean(summary.compareDocumentPosition(primaryGrid) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(primaryGrid.compareDocumentPosition(detailTabs) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(detailTabs.compareDocumentPosition(tradeTable) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(screen.getByRole('tab', { name: '交易明细' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '风险分析' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '参数' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '可靠性' })).toBeInTheDocument();
    expect(screen.queryByTestId('backtest-data-quality-grid')).not.toBeInTheDocument();
    expect(screen.queryByTestId('backtest-execution-assumptions-grid')).not.toBeInTheDocument();
    expect(report).toHaveTextContent('回测数据质量有限，结果仅供观察复盘。');
    expect(report).not.toHaveTextContent(/developer|debug|raw|schema|trace|provider_timeout|not_enough_history|fundamentals_unavailable|optional_news_timeout|fallback|dry run|MarketCache/i);
  });
});
